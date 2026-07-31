from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from punkt_b_admin_mcp.adapters import AdapterDispatcher
from punkt_b_admin_mcp.auth import SupabaseAdminTokenVerifier
from punkt_b_admin_mcp.config import Config
from punkt_b_admin_mcp.registry import REQUIRED_SERVICES, load_registry
from punkt_b_admin_mcp.security import (
    GatewayError,
    canonical_preview_hash,
    redact,
    validate_json_schema,
    validate_write_gates,
)


def config() -> Config:
    return Config(
        host="127.0.0.1",
        port=17443,
        contour="dev",
        supabase_url="https://api.intdata.pro",
        supabase_anon_key="test-only",
        oauth_issuer="https://api.intdata.pro/auth/v1",
        resource_url="http://127.0.0.1:17443/mcp",
        required_audience="http://127.0.0.1:17443/mcp",
        auth_timeout_seconds=1,
    )


class RegistryTests(unittest.TestCase):
    def test_registry_is_closed_and_covers_twelve_services(self) -> None:
        registry = load_registry()
        self.assertEqual(registry.contour, "dev")
        self.assertEqual({tool.service for tool in registry.tools}, REQUIRED_SERVICES)
        self.assertEqual(len(registry.by_name()), len(registry.tools))
        self.assertRegex(registry.sha256, r"^[0-9a-f]{64}$")

    def test_every_write_tool_has_confirmation_and_idempotency(self) -> None:
        writes = [tool for tool in load_registry().tools if tool.risk in {"write", "publish", "destructive"}]
        self.assertGreater(len(writes), 0)
        self.assertTrue(all(tool.confirmation_required and tool.idempotency_required for tool in writes))


class SecurityTests(unittest.TestCase):
    def test_write_gates_require_every_field_and_matching_hash(self) -> None:
        preview = {"action": "send", "recipient_count": 1}
        complete = {
            "confirm_write": True,
            "idempotency_key": "case-1",
            "target": "conversation:42",
            "preview": preview,
            "preview_hash": canonical_preview_hash(preview),
        }
        self.assertEqual(validate_write_gates(complete).target, "conversation:42")
        for field in complete:
            broken = dict(complete)
            broken.pop(field)
            with self.assertRaises(GatewayError, msg=field):
                validate_write_gates(broken)

    def test_redaction_removes_secret_and_pii_fields(self) -> None:
        result = redact({"access_token": "abc", "email": "a@example.test", "safe": {"count": 2}})
        self.assertEqual(result["access_token"], "***redacted***")
        self.assertEqual(result["email"], "***redacted***")
        self.assertEqual(result["safe"], {"count": 2})

    def test_write_effect_flag_is_disabled_before_adapter(self) -> None:
        entry = next(tool for tool in load_registry().tools if tool.risk == "write")
        preview = {"action": "test"}
        payload = {
            "confirm_write": True,
            "idempotency_key": "case-2",
            "target": "object:1",
            "preview": preview,
            "preview_hash": canonical_preview_hash(preview),
        }
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(GatewayError, "effect flag"):
                asyncio.run(AdapterDispatcher(config()).execute(entry, payload))

    def test_duplicate_idempotency_key_is_rejected_before_second_adapter_call(self) -> None:
        entry = replace(
            next(tool for tool in load_registry().tools if tool.risk == "write"),
            adapter="test.write",
        )
        preview = {"action": "test"}
        payload = {
            "confirm_write": True,
            "idempotency_key": "case-duplicate",
            "target": "object:1",
            "preview": preview,
            "preview_hash": canonical_preview_hash(preview),
        }
        calls = 0

        async def adapter(_payload: dict[str, object], _token: str) -> object:
            nonlocal calls
            calls += 1
            return {"accepted": True}

        dispatcher = AdapterDispatcher(config())
        dispatcher.register_for_test("test.write", adapter)
        effect_key = f"PUNKT_B_ADMIN_EFFECT_{entry.service}_{entry.risk}".upper()
        with patch.dict(os.environ, {effect_key: "true"}, clear=True):
            asyncio.run(dispatcher.execute(entry, payload))
            with self.assertRaisesRegex(GatewayError, "already used"):
                asyncio.run(dispatcher.execute(entry, payload))
        self.assertEqual(calls, 1)

    def test_registry_input_schema_rejects_unknown_and_out_of_range_values(self) -> None:
        entry = next(tool for tool in load_registry().tools if tool.tool_name == "punktb_umnico_chats_list")
        validate_json_schema({"limit": 25}, entry.input_schema)
        for payload in ({"limit": 26}, {"limit": True}, {"unknown": 1}):
            with self.assertRaisesRegex(GatewayError, "input"):
                validate_json_schema(payload, entry.input_schema)

    def test_unconfigured_read_adapter_fails_closed(self) -> None:
        entry = replace(
            next(tool for tool in load_registry().tools if tool.risk == "read"),
            adapter="provider.missing_read_adapter",
        )
        with self.assertRaisesRegex(GatewayError, "not configured"):
            asyncio.run(AdapterDispatcher(config()).execute(entry, {}))

    def test_canonical_service_clients_are_wired_without_nested_mcp(self) -> None:
        dispatcher = AdapterDispatcher(config())
        self.assertTrue({
            "provider.lk_admin_context",
            "provider.tilda_projects_list",
            "provider.amocrm_account_get",
            "provider.umnico_chats_list",
            "provider.getcourse_groups_list",
            "provider.bitrix24_profile_get",
            "provider.telegram_search",
            "provider.accounting_mail_threads_list",
            "provider.project_files_search",
        }.issubset(dispatcher._adapters))

    def test_deterministic_compute_is_bounded(self) -> None:
        entry = next(tool for tool in load_registry().tools if tool.adapter == "builtin.reporting_compute")
        result = asyncio.run(AdapterDispatcher(config()).execute(entry, {"values": [1, 2.5, 3]}))
        self.assertEqual(result, {"count": 3, "sum": 6.5, "minimum": 1, "maximum": 3})

    def test_adapter_output_schema_is_enforced(self) -> None:
        entry = replace(
            next(tool for tool in load_registry().tools if tool.risk == "read"),
            adapter="test.invalid_output",
            output_schema={"type": "object", "required": ["safe"], "additionalProperties": False,
                           "properties": {"safe": {"type": "boolean"}}},
        )

        async def adapter(_payload: dict[str, object], _token: str) -> object:
            return {"raw_remote_body": "must not escape"}

        dispatcher = AdapterDispatcher(config())
        dispatcher.register_for_test("test.invalid_output", adapter)
        with self.assertRaisesRegex(GatewayError, "output"):
            asyncio.run(dispatcher.execute(entry, {}))


class ConfigTests(unittest.TestCase):
    def test_non_loopback_bind_is_rejected(self) -> None:
        with patch.dict(os.environ, {
            "PUNKT_B_ADMIN_HOST": "0.0.0.0",
            "PUNKT_B_ADMIN_SUPABASE_ANON_KEY": "test",
        }, clear=True):
            with self.assertRaisesRegex(ValueError, "loopback"):
                Config.load()


class AuthTests(unittest.TestCase):
    @staticmethod
    def token(**claims: object) -> str:
        def encode(value: object) -> str:
            return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")

        return f"{encode({'alg': 'none'})}.{encode(claims)}.test-signature"

    def test_admin_oauth_token_requires_separate_audience_and_client_id(self) -> None:
        verifier = SupabaseAdminTokenVerifier(config())
        calls: list[str] = []

        def request_json(path: str, _token: str, _body: bytes | None = None) -> object:
            calls.append(path)
            return {"id": "10000000-0000-4000-8000-000000000001"} if path == "/auth/v1/user" else True

        verifier._request_json = request_json  # type: ignore[method-assign]
        accepted = asyncio.run(verifier.verify_token(self.token(
            aud=config().required_audience,
            client_id="native-codex-dev",
            scope="email",
            exp=2_000_000_000,
        )))
        self.assertIsNotNone(accepted)
        self.assertEqual(accepted.client_id, "10000000-0000-4000-8000-000000000001")
        self.assertIn("users:manage", accepted.scopes)
        self.assertEqual(calls, ["/auth/v1/user", "/rest/v1/rpc/current_user_has_perm"])

        calls.clear()
        self.assertIsNone(asyncio.run(verifier.verify_token(self.token(
            aud="authenticated",
            client_id="specialist-client",
        ))))
        self.assertEqual(calls, [], "wrong audience must fail before any provider request")
        self.assertIsNone(asyncio.run(verifier.verify_token(self.token(aud=config().required_audience))))

    def test_revoked_users_manage_is_rechecked_on_every_request(self) -> None:
        verifier = SupabaseAdminTokenVerifier(config())
        permission = {"allowed": True}

        def request_json(path: str, _token: str, _body: bytes | None = None) -> object:
            if path == "/auth/v1/user":
                return {"id": "10000000-0000-4000-8000-000000000001"}
            return permission["allowed"]

        verifier._request_json = request_json  # type: ignore[method-assign]
        token = self.token(aud=config().required_audience, client_id="native-hermes-dev")
        self.assertIsNotNone(asyncio.run(verifier.verify_token(token)))
        permission["allowed"] = False
        self.assertIsNone(asyncio.run(verifier.verify_token(token)))


class ServerTests(unittest.TestCase):
    def test_server_registers_exact_registry_inventory_and_metadata_routes(self) -> None:
        from punkt_b_admin_mcp.server import create_server

        server = create_server(config())
        tool_names = {tool.name for tool in asyncio.run(server.list_tools())}
        self.assertEqual(tool_names, set(load_registry().by_name()))
        advertised = {tool.name: tool.inputSchema for tool in asyncio.run(server.list_tools())}
        for name, entry in load_registry().by_name().items():
            self.assertEqual(advertised[name], entry.input_schema)
        route_paths = {getattr(route, "path", None) for route in server.streamable_http_app().routes}
        self.assertIn("/.well-known/oauth-protected-resource/mcp", route_paths)
        self.assertIn("/mcp/.well-known/oauth-protected-resource", route_paths)


if __name__ == "__main__":
    unittest.main()

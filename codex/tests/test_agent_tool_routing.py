#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTER_ROOT = REPO_ROOT / "codex" / "bin"
if str(ROUTER_ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROUTER_ROOT))

import agent_tool_routing as routing  # noqa: E402
import int_ssh_resolve as ssh_resolve  # noqa: E402
EXPECTED_V1_CAPABILITIES = {
    "int_ssh_resolve",
    "firefox-default",
    "assess-firefox-client",
    "assess-firefox-specialist-v1",
    "assess-firefox-specialist-v2",
    "assess-firefox-admin",
    "assess-firefox-specialist-restricted",
    "dba",
    "codex-host-bootstrap",
    "codex-host-verify",
    "codex-recovery-bundle",
}


class AgentToolRoutingTest(unittest.TestCase):
    maxDiff = None

    def _load_registry(self) -> dict:
        return routing.load_registry(str(REPO_ROOT / "codex" / "config" / "agent-tool-routing.v1.json"))

    def _write_temp_registry(self, payload: dict) -> str:
        temp_dir = Path(tempfile.mkdtemp(prefix="agent_tool_routing_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(temp_dir, ignore_errors=True))
        registry_path = temp_dir / "agent-tool-routing.v1.json"
        registry_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(registry_path)

    def test_validate_registry_succeeds(self) -> None:
        result = routing.validate_registry(str(REPO_ROOT / "codex" / "config" / "agent-tool-routing.v1.json"))
        self.assertTrue(result["ok"], result["errors"])

    def test_intdata_routes_use_dev_identity(self) -> None:
        for logical_host in ("dev-intdata", "dev-runtime"):
            spec = ssh_resolve.build_spec(logical_host)
            self.assertIsNotNone(spec)
            self.assertEqual(spec.user, "dev")
            self.assertEqual(spec.public_host, "intdata.pro")
            self.assertEqual(spec.identity_file, "~/.ssh/id_ed25519_vds_intdata_dev")

    def test_all_v1_capabilities_are_present(self) -> None:
        payload = self._load_registry()
        declared = {item["capability_id"] for item in payload["capabilities"]}
        self.assertEqual(declared, EXPECTED_V1_CAPABILITIES)

    def test_coordctl_is_no_longer_owned_by_int_tools_routing(self) -> None:
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.resolve_capability("coordctl:cli", platform="linux")
        self.assertEqual(ctx.exception.code, "UNKNOWN_INTENT")

    def test_sync_gate_intent_is_removed(self) -> None:
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.resolve_capability("sync-gate:start", platform="linux")
        self.assertEqual(ctx.exception.code, "UNKNOWN_INTENT")

    def test_ssh_host_intent_is_merged_into_resolve(self) -> None:
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.resolve_capability("ssh:host", platform="windows")
        self.assertEqual(ctx.exception.code, "UNKNOWN_INTENT")

    def test_lockctl_mcp_is_removed_from_active_routing(self) -> None:
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.resolve_capability("lockctl:mcp", platform="windows")
        self.assertEqual(ctx.exception.code, "UNKNOWN_INTENT")

    def test_lockctl_cli_is_removed_from_active_routing(self) -> None:
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.resolve_capability("lockctl:cli", platform="windows")
        self.assertEqual(ctx.exception.code, "UNKNOWN_INTENT")

    def test_describe_rejects_removed_lockctl_capability(self) -> None:
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.describe_capability("lockctl-cli")
        self.assertEqual(ctx.exception.code, "UNKNOWN_CAPABILITY")

    def test_describe_rejects_removed_coordctl_capability(self) -> None:
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.describe_capability("coordctl-cli")
        self.assertEqual(ctx.exception.code, "UNKNOWN_CAPABILITY")

    def test_unknown_intent_blocks(self) -> None:
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.resolve_capability("does-not-exist", platform="windows")
        self.assertEqual(ctx.exception.code, "UNKNOWN_INTENT")

    def test_host_capabilities_resolve_on_windows(self) -> None:
        for capability_id, expected in (
            ("codex-host-bootstrap", "codex/bin/codex-host-bootstrap.cmd"),
            ("codex-host-verify", "codex/bin/codex-host-verify.cmd"),
            ("codex-recovery-bundle", "codex/bin/codex-recovery-bundle.cmd"),
        ):
            payload = routing.resolve_capability(capability_id, platform="windows")
            self.assertEqual(payload["selected_binding"]["binding_origin"], expected)

    def test_firefox_capabilities_resolve_to_platform_wrappers(self) -> None:
        for capability_id, expected_windows, expected_linux in (
            ("firefox-default", "codex/bin/mcp-firefox-default.cmd", "codex/bin/mcp-firefox-default"),
            ("assess-firefox-client", "codex/bin/firefox_mcp_launcher.py", "codex/bin/firefox_mcp_launcher.py"),
            ("assess-firefox-specialist-v1", "codex/bin/firefox_mcp_launcher.py", "codex/bin/firefox_mcp_launcher.py"),
            ("assess-firefox-specialist-v2", "codex/bin/firefox_mcp_launcher.py", "codex/bin/firefox_mcp_launcher.py"),
            ("assess-firefox-admin", "codex/bin/firefox_mcp_launcher.py", "codex/bin/firefox_mcp_launcher.py"),
            ("assess-firefox-specialist-restricted", "codex/bin/firefox_mcp_launcher.py", "codex/bin/firefox_mcp_launcher.py"),
        ):
            self.assertEqual(routing.resolve_capability(capability_id, platform="windows")["selected_binding"]["binding_origin"], expected_windows)
            self.assertEqual(routing.resolve_capability(capability_id, platform="linux")["selected_binding"]["binding_origin"], expected_linux)

    def test_missing_engine_blocks(self) -> None:
        payload = self._load_registry()
        for capability in payload["capabilities"]:
            if capability["capability_id"] == "codex-host-bootstrap":
                capability["canonical_engine"] = "codex/bin/missing_codex_host_bootstrap.py"
                for binding in capability["runtime_bindings"]:
                    if binding["binding_kind"] == "engine":
                        binding["binding_origin"] = "codex/bin/missing_codex_host_bootstrap.py"
                    elif binding["adapter_targets_engine"] == "codex/bin/codex_host_bootstrap.py":
                        binding["adapter_targets_engine"] = "codex/bin/missing_codex_host_bootstrap.py"
        registry_path = self._write_temp_registry(payload)
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.resolve_capability("codex-host-bootstrap", platform="windows", registry_path=registry_path)
        self.assertEqual(ctx.exception.code, "MISSING_ENGINE")

    def test_missing_adapter_blocks(self) -> None:
        payload = self._load_registry()
        for capability in payload["capabilities"]:
            if capability["capability_id"] == "codex-host-bootstrap":
                for binding in capability["runtime_bindings"]:
                    if binding["binding_origin"] == "codex/bin/codex-host-bootstrap.cmd":
                        binding["binding_origin"] = "codex/bin/missing-codex-host-bootstrap.cmd"
        registry_path = self._write_temp_registry(payload)
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.resolve_capability("codex-host-bootstrap", platform="windows", registry_path=registry_path)
        self.assertEqual(ctx.exception.code, "MISSING_ADAPTER")

    def test_adapter_drift_blocks(self) -> None:
        payload = self._load_registry()
        for capability in payload["capabilities"]:
            if capability["capability_id"] == "codex-host-bootstrap":
                for binding in capability["runtime_bindings"]:
                    if binding["binding_origin"] == "codex/bin/codex-host-bootstrap.cmd":
                        binding["adapter_targets_engine"] = "codex/bin/codex_host_verify.py"
        registry_path = self._write_temp_registry(payload)
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.resolve_capability("codex-host-bootstrap", platform="windows", registry_path=registry_path)
        self.assertEqual(ctx.exception.code, "ADAPTER_DRIFT")

    def test_ambiguous_intent_blocks(self) -> None:
        payload = self._load_registry()
        for capability in payload["capabilities"]:
            if capability["capability_id"] == "codex-host-verify":
                capability["logical_intents"].append("host:bootstrap")
        registry_path = self._write_temp_registry(payload)
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.resolve_capability("host:bootstrap", platform="windows", registry_path=registry_path)
        self.assertEqual(ctx.exception.code, "AMBIGUOUS_INTENT")

    def test_fallbacks_are_reported_but_not_executed(self) -> None:
        payload = self._load_registry()
        for capability in payload["capabilities"]:
            if capability["capability_id"] == "codex-host-bootstrap":
                capability["approved_fallback_skills"] = ["playwright"]
        registry_path = self._write_temp_registry(payload)
        with self.assertRaises(routing.RoutingError) as ctx:
            routing.resolve_capability("codex-host-bootstrap", platform="macos", registry_path=registry_path)
        self.assertEqual(ctx.exception.payload["approved_fallback_skills"], ["playwright"])
        self.assertNotIn("executed_fallback_skill", ctx.exception.payload)

    def test_firefox_overlays_use_neutral_launchers(self) -> None:
        int_overlay = json.loads((REPO_ROOT / "codex" / "projects" / "int" / ".mcp.json").read_text(encoding="utf-8"))
        assess_overlay = json.loads((REPO_ROOT / "codex" / "projects" / "assess" / ".mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(int_overlay["mcpServers"]["firefox-default"]["command"], "mcp-firefox-default")
        self.assertNotIn("assess-firefox-client", assess_overlay["mcpServers"])
        firefox_servers = [
            int_overlay["mcpServers"]["firefox-default"],
        ]
        for server in firefox_servers:
            self.assertNotIn("cmd.exe", server["command"])
            self.assertNotIn("D:\\int\\tools\\", server["command"])
            self.assertNotIn("npx", server["command"])
            self.assertNotIn("args", server)


if __name__ == "__main__":
    unittest.main()

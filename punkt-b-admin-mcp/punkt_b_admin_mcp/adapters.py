from __future__ import annotations

import asyncio
import email
import imaplib
import json
import os
import ssl
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from punkt_b_admin_mcp.config import Config
from punkt_b_admin_mcp.registry import ToolEntry
from punkt_b_admin_mcp.security import (
    GatewayError,
    IdempotencyGuard,
    redact,
    validate_json_schema,
    validate_write_gates,
)


Adapter = Callable[[dict[str, Any], str], Awaitable[Any]]


class AdapterDispatcher:
    """Closed adapter map: no arbitrary module, executable, URL or shell dispatch."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._idempotency = IdempotencyGuard()
        self._adapters: dict[str, Adapter] = {
            "provider.lk_admin_context": self._lk_admin_context,
            "provider.tilda_projects_list": self._tilda_projects_list,
            "provider.amocrm_account_get": self._amocrm_account_get,
            "provider.umnico_chats_list": self._umnico_chats_list,
            "provider.getcourse_groups_list": self._getcourse_groups_list,
            "provider.bitrix24_profile_get": self._bitrix24_profile_get,
            "provider.telegram_search": self._telegram_search,
            "provider.accounting_mail_threads_list": self._accounting_mail_threads_list,
            "provider.project_files_search": self._project_files_search,
            "builtin.vakas_manifest_validate": self._vakas_manifest_validate,
            "builtin.reporting_compute": self._deterministic_compute,
            "builtin.sales_analytics_compute": self._deterministic_compute,
        }

    def register_for_test(self, name: str, adapter: Adapter) -> None:
        if not name.startswith("test."):
            raise ValueError("Only test adapters can be injected")
        self._adapters[name] = adapter

    async def execute(self, entry: ToolEntry, payload: dict[str, Any], *, caller_token: str = "") -> Any:
        validate_json_schema(payload, entry.input_schema)
        if entry.risk in {"write", "publish", "destructive"}:
            approval = validate_write_gates(payload)
            if not self.config.effect_enabled(entry.service, entry.risk):
                raise GatewayError("EFFECT_DISABLED", "Runtime effect flag is disabled")
            self._idempotency.reserve(entry.tool_name, approval)
        adapter = self._adapters.get(entry.adapter)
        if adapter is None:
            raise GatewayError("ADAPTER_NOT_CONFIGURED", "Canonical service adapter is not configured")
        try:
            result = redact(await asyncio.wait_for(adapter(payload, caller_token), timeout=entry.timeout_seconds))
            validate_json_schema(result, entry.output_schema, path="output")
            return result
        except TimeoutError as exc:
            raise GatewayError("ADAPTER_TIMEOUT", "Service adapter timed out", retryable=True) from exc

    @staticmethod
    async def _amocrm_account_get(payload: dict[str, Any], _caller_token: str) -> Any:
        try:
            from amocrm_mcp.auth import AuthManager
            from amocrm_mcp.client import AmoClient
            from amocrm_mcp.config import Config as AmoConfig
        except ImportError as exc:
            raise GatewayError("ADAPTER_NOT_CONFIGURED", "amocrm-mcp service library is not installed") from exc
        try:
            service_config = AmoConfig()
            client = AmoClient(AuthManager(service_config), service_config.base_url)
            try:
                raw = await client.request("GET", "/api/v4/account")
                if not isinstance(raw, dict):
                    raise GatewayError("PROVIDER_REQUEST_FAILED", "amoCRM returned invalid data")
                return {key: str(raw[key])[:200] for key in ("id", "name", "subdomain", "country") if key in raw}
            finally:
                await client.close()
        except Exception as exc:
            raise GatewayError("PROVIDER_REQUEST_FAILED", "amoCRM read failed", retryable=True) from exc

    @staticmethod
    async def _umnico_chats_list(payload: dict[str, Any], _caller_token: str) -> Any:
        try:
            from amocrm_mcp.umnico_client import UmnicoClient
        except ImportError as exc:
            raise GatewayError("ADAPTER_NOT_CONFIGURED", "amocrm-mcp Umnico service library is not installed") from exc
        api_key = os.getenv("UMNICO_API_KEY", "").strip()
        if not api_key:
            raise GatewayError("ADAPTER_NOT_CONFIGURED", "Umnico runtime secret is not configured")
        section = "active"
        limit = min(25, max(1, int(payload.get("limit", 25))))
        client = UmnicoClient(api_key=api_key, base_url=os.getenv("UMNICO_BASE_URL", "https://api.umnico.com/v1.3"))
        try:
            raw = await client.request("GET", f"/leads/{section}", params={"offset": 0, "limit": limit})
            leads = raw if isinstance(raw, list) else raw.get("leads", []) if isinstance(raw, dict) else []
            items = []
            for lead in leads[:limit]:
                if isinstance(lead, dict):
                    items.append({key: str(lead[key])[:200] for key in ("id", "status", "created_at", "updated_at") if key in lead})
            return {"count": len(items), "leads": items}
        except Exception as exc:
            raise GatewayError("PROVIDER_REQUEST_FAILED", "Umnico read failed", retryable=True) from exc
        finally:
            await client.close()

    @staticmethod
    async def _getcourse_groups_list(payload: dict[str, Any], _caller_token: str) -> Any:
        try:
            from getcourse_mcp.client import GetCourseClient
            from getcourse_mcp.config import Config as GetCourseConfig
        except ImportError as exc:
            raise GatewayError("ADAPTER_NOT_CONFIGURED", "getcourse-mcp service library is not installed") from exc
        service_config = GetCourseConfig.load()
        if not service_config.account_domain or not service_config.has_api_key:
            raise GatewayError("ADAPTER_NOT_CONFIGURED", "GetCourse runtime credentials are not configured")
        client = GetCourseClient(service_config)
        try:
            data = await client.get("/pl/api/account/groups")
            if isinstance(data, dict) and (data.get("success") is False or data.get("error")):
                raise GatewayError("PROVIDER_REQUEST_FAILED", "GetCourse returned an error", retryable=False)
            groups = []
            candidates = data.get("groups", data.get("result", [])) if isinstance(data, dict) else []
            if isinstance(candidates, dict):
                candidates = candidates.get("groups", [])
            for group in candidates[:100] if isinstance(candidates, list) else []:
                if isinstance(group, dict):
                    groups.append({key: str(group[key])[:200] for key in ("id", "name", "title") if key in group})
            return {"count": len(groups), "groups": groups}
        except GatewayError:
            raise
        except Exception as exc:
            raise GatewayError("PROVIDER_REQUEST_FAILED", "GetCourse read failed", retryable=True) from exc
        finally:
            await client.close()

    @staticmethod
    async def _bitrix24_profile_get(payload: dict[str, Any], _caller_token: str) -> Any:
        try:
            from bitrix24_mcp.client import Bitrix24Client
            from bitrix24_mcp.config import Config as Bitrix24Config
        except ImportError as exc:
            raise GatewayError("ADAPTER_NOT_CONFIGURED", "bitrix24-mcp service library is not installed") from exc
        service_config = Bitrix24Config.load()
        if not service_config.has_webhook_url:
            raise GatewayError("ADAPTER_NOT_CONFIGURED", "Bitrix24 runtime webhook is not configured")
        client = Bitrix24Client(service_config)
        try:
            raw = await client.call("profile")
            profile = raw.get("result", raw) if isinstance(raw, dict) else {}
            if not isinstance(profile, dict):
                raise GatewayError("PROVIDER_REQUEST_FAILED", "Bitrix24 returned invalid data")
            return {key: str(profile[key])[:200] for key in ("ID", "ACTIVE", "ADMIN", "TIME_ZONE") if key in profile}
        except Exception as exc:
            raise GatewayError("PROVIDER_REQUEST_FAILED", "Bitrix24 read failed", retryable=True) from exc
        finally:
            await client.close()

    @staticmethod
    async def _vakas_manifest_validate(payload: dict[str, Any], _caller_token: str) -> Any:
        try:
            from vakas_mcp.api_manifest import load_manifest
        except ImportError as exc:
            raise GatewayError("ADAPTER_NOT_CONFIGURED", "vakas-mcp service library is not installed") from exc
        manifest = load_manifest()
        result = {"valid": True, "surfaces": len(manifest.get("surfaces", []))}
        if isinstance(manifest.get("official_source"), str):
            result["source"] = manifest["official_source"][:1000]
        return result

    @staticmethod
    async def _deterministic_compute(payload: dict[str, Any], _caller_token: str) -> Any:
        values = payload.get("values", [])
        if not isinstance(values, list) or len(values) > 500 or any(not isinstance(v, (int, float)) for v in values):
            raise GatewayError("INVALID_INPUT", "values must be a bounded numeric array")
        return {"count": len(values), "sum": sum(values), "minimum": min(values) if values else None, "maximum": max(values) if values else None}

    def _caller_request_json(self, path: str, caller_token: str, body: dict[str, Any] | None = None) -> Any:
        if not caller_token:
            raise GatewayError("ACCESS_DENIED", "Caller token is unavailable")
        request = Request(
            f"{self.config.supabase_url}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": f"Bearer {caller_token}",
                "apikey": self.config.supabase_anon_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST" if body is not None else "GET",
        )
        try:
            with urlopen(request, timeout=self.config.auth_timeout_seconds) as response:
                return json.loads(response.read(65536))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise GatewayError("PROVIDER_REQUEST_FAILED", "LK admin read failed", retryable=True) from exc

    async def _lk_admin_context(self, payload: dict[str, Any], caller_token: str) -> Any:
        user = await asyncio.to_thread(self._caller_request_json, "/auth/v1/user", caller_token)
        allowed = await asyncio.to_thread(
            self._caller_request_json,
            "/rest/v1/rpc/current_user_has_perm",
            caller_token,
            {"p_perm_code": "users:manage"},
        )
        if not isinstance(user, dict) or not isinstance(user.get("id"), str) or allowed is not True:
            raise GatewayError("ACCESS_DENIED", "Current users:manage authority is required")
        return {"actor_id": user["id"], "effective_permission": "users:manage", "allowed": True}

    @staticmethod
    async def _tilda_projects_list(payload: dict[str, Any], _caller_token: str) -> Any:
        public_key = os.getenv("TILDA_PUBLIC_KEY", "").strip()
        secret_key = os.getenv("TILDA_SECRET_KEY", "").strip()
        if not public_key or not secret_key:
            raise GatewayError("ADAPTER_NOT_CONFIGURED", "Tilda runtime credentials are not configured")

        def read() -> Any:
            query = urlencode({"publickey": public_key, "secretkey": secret_key})
            request = Request(f"https://api.tildacdn.info/v1/getprojectslist/?{query}", method="GET")
            try:
                with urlopen(request, timeout=8) as response:
                    data = json.loads(response.read(1_048_576))
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                raise GatewayError("PROVIDER_REQUEST_FAILED", "Tilda read failed", retryable=True) from exc
            if not isinstance(data, dict) or data.get("status") != "FOUND":
                raise GatewayError("PROVIDER_REQUEST_FAILED", "Tilda returned an error")
            projects = []
            candidates = data.get("result", [])
            for project in candidates[:100] if isinstance(candidates, list) else []:
                if isinstance(project, dict):
                    projects.append({key: str(project[key])[:500] for key in ("id", "title", "descr") if key in project})
            return {"count": len(projects), "projects": projects}

        return await asyncio.to_thread(read)

    @staticmethod
    async def _telegram_search(payload: dict[str, Any], _caller_token: str) -> Any:
        query = str(payload["query"]).casefold()
        executable = Path("/home/agents/.local/bin/tdl-work")
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise GatewayError("ADAPTER_NOT_CONFIGURED", "Canonical tdl-work executable is unavailable")
        try:
            process = await asyncio.create_subprocess_exec(
                str(executable),
                "--limit", "1",
                "--threads", "1",
                "chat", "ls",
                "--output", "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # tdl requires the real account home to locate its protected
                # session. No caller-controlled environment reaches it.
                env={"PATH": "/usr/bin:/bin", "HOME": "/home/agents"},
            )
            stdout, _stderr = await asyncio.wait_for(process.communicate(), timeout=18)
        except (OSError, TimeoutError) as exc:
            raise GatewayError("PROVIDER_REQUEST_FAILED", "Telegram chat read failed", retryable=True) from exc
        if process.returncode != 0 or len(stdout) > 1_048_576:
            raise GatewayError("PROVIDER_REQUEST_FAILED", "Telegram chat read failed", retryable=True)
        try:
            decoded = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise GatewayError("PROVIDER_REQUEST_FAILED", "Telegram returned invalid data") from exc
        chats = decoded if isinstance(decoded, list) else decoded.get("chats", []) if isinstance(decoded, dict) else []
        matches = []
        for chat in chats[:500]:
            if not isinstance(chat, dict):
                continue
            title = str(chat.get("name") or chat.get("title") or "")
            username = str(chat.get("username") or "")
            if query not in f"{title}\n{username}".casefold():
                continue
            matches.append({
                "id": str(chat.get("id", ""))[:64],
                "title": title[:200],
            })
            if len(matches) == 25:
                break
        return {"matched": len(matches), "chats": matches, "account": "@intData_agent"}

    @staticmethod
    async def _accounting_mail_threads_list(payload: dict[str, Any], _caller_token: str) -> Any:
        limit = min(25, max(1, int(payload.get("limit", 20))))
        password = os.getenv("ACCOUNTING_MAIL_APP_PASSWORD", "").strip()
        if not password:
            secret_path = Path(os.getenv(
                "PUNKT_B_ACCOUNTING_MAIL_SECRET_FILE",
                "/int/.runtime/codex-secrets/punktb-accounting-mail.env",
            ))
            try:
                for raw_line in secret_path.read_text(encoding="utf-8").splitlines():
                    key, separator, value = raw_line.partition("=")
                    if separator and key.strip() == "ACCOUNTING_MAIL_APP_PASSWORD":
                        password = value.strip().strip("'\"")
                        break
            except (OSError, UnicodeError):
                pass
        if not password:
            raise GatewayError("ADAPTER_NOT_CONFIGURED", "Accounting mail runtime secret is unavailable")

        def read() -> Any:
            client = imaplib.IMAP4_SSL("imap.yandex.ru", 993, ssl_context=ssl.create_default_context())
            try:
                client.login("accounting@punkt-b.pro", password)
                status, _ = client.select("INBOX", readonly=True)
                if status != "OK":
                    raise GatewayError("PROVIDER_REQUEST_FAILED", "Accounting mailbox is unavailable")
                status, data = client.uid("search", None, "ALL")
                if status != "OK":
                    raise GatewayError("PROVIDER_REQUEST_FAILED", "Accounting mailbox read failed")
                uids = (data[0] or b"").decode("ascii", errors="ignore").split()[-limit:]
                threads = []
                for uid in reversed(uids):
                    status, fetched = client.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (DATE MESSAGE-ID)])")
                    if status != "OK":
                        continue
                    raw = next((part[1] for part in fetched if isinstance(part, tuple)), b"")
                    message = email.message_from_bytes(raw)
                    threads.append({"uid": uid, "date": str(message.get("Date", ""))[:200]})
                return {"account": "accounting@punkt-b.pro", "readonly": True, "threads": threads}
            except (imaplib.IMAP4.error, OSError, ssl.SSLError) as exc:
                raise GatewayError("PROVIDER_REQUEST_FAILED", "Accounting mailbox read failed", retryable=True) from exc
            finally:
                try:
                    client.logout()
                except Exception:
                    pass

        return await asyncio.to_thread(read)

    @staticmethod
    async def _project_files_search(payload: dict[str, Any], _caller_token: str) -> Any:
        query = str(payload["query"]).casefold()
        root = Path("/int/cloud/gdrive")
        if not root.is_dir():
            raise GatewayError("ADAPTER_NOT_CONFIGURED", "Canonical project-files VFS is unavailable")

        def read() -> Any:
            matches = []
            scanned = 0
            for current_root, directories, filenames in os.walk(root, followlinks=False):
                directories[:] = sorted(directories)[:200]
                for filename in sorted(filenames):
                    scanned += 1
                    if scanned > 5000:
                        return {"query": payload["query"], "truncated": True, "files": matches}
                    if query not in filename.casefold():
                        continue
                    path = Path(current_root, filename)
                    try:
                        stat = path.stat(follow_symlinks=False)
                        relative = path.relative_to(root)
                    except (OSError, ValueError):
                        continue
                    matches.append({
                        "path": str(relative)[:1000],
                        "size": stat.st_size,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    })
                    if len(matches) == 25:
                        return {"query": payload["query"], "truncated": True, "files": matches}
            return {"query": payload["query"], "truncated": False, "files": matches}

        return await asyncio.to_thread(read)

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any


RISK_CLASSES = {"read", "compute", "draft", "write", "publish", "destructive"}
WRITE_RISKS = {"write", "publish", "destructive"}
REQUIRED_ANNOTATIONS = {"readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"}
REQUIRED_SERVICES = {
    "lk", "tilda", "amocrm", "umnico", "getcourse", "bitrix24", "vakas",
    "telegram", "accounting_mail", "reporting", "project_files", "sales_analytics",
}
REQUIRED_TOOL_NAMES = {
    "punktb_lk_admin_context", "punktb_tilda_projects_list", "punktb_amocrm_account_get",
    "punktb_umnico_chats_list", "punktb_getcourse_groups_list", "punktb_bitrix24_profile_get",
    "punktb_vakas_manifest_validate", "punktb_telegram_search", "punktb_accounting_mail_threads_list",
    "punktb_reporting_summary_compute", "punktb_project_files_search", "punktb_sales_analytics_summary_compute",
    "punktb_amocrm_entity_update", "punktb_umnico_message_send", "punktb_getcourse_user_import",
    "punktb_bitrix24_entity_update", "punktb_vakas_dispatch", "punktb_telegram_message_send",
    "punktb_accounting_mail_message_send",
}
WRITE_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "confirm_write": {"type": "boolean"},
        "idempotency_key": {"type": "string", "minLength": 1, "maxLength": 200},
        "target": {"type": "string", "minLength": 1, "maxLength": 500},
        "preview": {},
        "preview_hash": {"type": "string", "minLength": 64, "maxLength": 64},
    },
    "required": ["confirm_write", "idempotency_key", "target", "preview", "preview_hash"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class ToolEntry:
    tool_name: str
    service: str
    operation: str
    adapter: str
    risk: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    required_permission: str
    required_secrets: tuple[str, ...]
    timeout_seconds: float
    rate_limit_per_minute: int
    idempotency_required: bool
    confirmation_required: bool
    annotations: dict[str, bool]
    source_adapter_version: str


@dataclass(frozen=True)
class Registry:
    version: str
    contour: str
    tools: tuple[ToolEntry, ...]
    sha256: str

    def by_name(self) -> dict[str, ToolEntry]:
        return {tool.tool_name: tool for tool in self.tools}


def load_registry() -> Registry:
    raw = files("punkt_b_admin_mcp").joinpath("capability_registry.json").read_bytes()
    payload = json.loads(raw)
    output_raw = files("punkt_b_admin_mcp").joinpath("output_schemas.json").read_bytes()
    output_schemas = json.loads(output_raw)
    if not isinstance(output_schemas, dict):
        raise ValueError("Output schema registry must be an object")
    if payload.get("contour") != "dev":
        raise ValueError("Capability registry must be dev-only")
    entries: list[ToolEntry] = []
    names: set[str] = set()
    for item in payload.get("tools", []):
        name = item.get("tool_name")
        service = item.get("service")
        operation = item.get("operation")
        risk = item.get("risk")
        annotations = item.get("annotations")
        if not isinstance(name, str) or not name.startswith("punktb_"):
            raise ValueError("Every tool name must start with punktb_")
        if name in names:
            raise ValueError(f"Duplicate tool name: {name}")
        if not isinstance(service, str) or not isinstance(operation, str) or name != f"punktb_{service}_{operation}":
            raise ValueError(f"Tool name does not match service/operation: {name}")
        if risk not in RISK_CLASSES:
            raise ValueError(f"Invalid risk for {name}")
        if not isinstance(item.get("input_schema"), dict) or not isinstance(output_schemas.get(name), dict):
            raise ValueError(f"Missing schema for {name}")
        if item.get("required_permission") != "users:manage":
            raise ValueError(f"Invalid permission for {name}")
        if not isinstance(annotations, dict) or set(annotations) != REQUIRED_ANNOTATIONS:
            raise ValueError(f"Missing annotations for {name}")
        if risk in WRITE_RISKS and not (item.get("idempotency_required") and item.get("confirmation_required")):
            raise ValueError(f"Write-capable tool lacks gates: {name}")
        read_only = risk in {"read", "compute"}
        if bool(annotations["readOnlyHint"]) != read_only:
            raise ValueError(f"Risk/readOnlyHint mismatch for {name}")
        if bool(annotations["destructiveHint"]) != (risk == "destructive"):
            raise ValueError(f"Risk/destructiveHint mismatch for {name}")
        if bool(annotations["idempotentHint"]) != (read_only or bool(item.get("idempotency_required"))):
            raise ValueError(f"Risk/idempotentHint mismatch for {name}")
        input_schema = WRITE_INPUT_SCHEMA if risk in WRITE_RISKS else item["input_schema"]
        entry = ToolEntry(
            tool_name=name,
            service=service,
            operation=operation,
            adapter=str(item.get("adapter", "")),
            risk=risk,
            input_schema=input_schema,
            output_schema=output_schemas[name],
            required_permission=item["required_permission"],
            required_secrets=tuple(item.get("required_secrets", [])),
            timeout_seconds=float(item.get("timeout_seconds", 10)),
            rate_limit_per_minute=int(item.get("rate_limit_per_minute", 30)),
            idempotency_required=bool(item.get("idempotency_required")),
            confirmation_required=bool(item.get("confirmation_required")),
            annotations={key: bool(annotations[key]) for key in REQUIRED_ANNOTATIONS},
            source_adapter_version=str(item.get("source_adapter_version", "")),
        )
        if not entry.adapter or not entry.source_adapter_version or entry.rate_limit_per_minute < 1:
            raise ValueError(f"Incomplete adapter policy for {name}")
        names.add(name)
        entries.append(entry)
    service_inventory = {entry.service for entry in entries}
    if service_inventory != REQUIRED_SERVICES:
        raise ValueError("Service inventory must exactly match the approved 12 namespaces")
    if names != REQUIRED_TOOL_NAMES:
        raise ValueError("Tool inventory must exactly match the approved registry")
    if set(output_schemas) != names:
        raise ValueError("Output schema registry must exactly match the tool inventory")
    if any(schema.get("type") != "object" or schema.get("additionalProperties") is not False for schema in output_schemas.values()):
        raise ValueError("Every output schema must be a closed object")
    canonical = json.dumps(
        {"capabilities": payload, "output_schemas": output_schemas, "write_input_schema": WRITE_INPUT_SCHEMA},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return Registry(str(payload["version"]), "dev", tuple(entries), hashlib.sha256(canonical).hexdigest())

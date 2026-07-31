#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_tool_routing import assert_binding  # noqa: E402


VALID_MODES = {"auto", "tailnet", "public"}


@dataclass(frozen=True)
class TargetSpec:
    logical_host: str
    user: str
    identity_file: str
    public_host: str
    tailnet_host: str
    public_alias: str
    tailnet_alias: str


def get_mode(raw: str | None = None) -> str:
    mode = (raw or os.getenv("INT_SSH_MODE", "auto")).strip().lower()
    return mode if mode in VALID_MODES else "auto"


def get_probe_timeout_sec(raw: str | None = None) -> int:
    source = raw if raw is not None else os.getenv("INT_SSH_PROBE_TIMEOUT_SEC", "4")
    try:
        parsed = int(source.strip())
    except ValueError:
        return 4
    return max(1, min(30, parsed))


def get_config_path() -> Path | None:
    override = os.getenv("INT_SSH_CONFIG_PATH", "").strip()
    if override:
        path = Path(override).expanduser()
    else:
        path = (Path(__file__).resolve().parent / ".." / "config" / "int_ssh_config").resolve()
    return path if path.exists() else None


def resolve_logical_host(requested_host: str) -> str | None:
    mapping = {
        "vds-intdata-intdata": "dev-intdata",
        "vds-intdata-agents": "dev-agents",
        "prod": "prod-leon",
        "vds.punkt-b.pro": "prod-leon",
        "dev-intdata": "dev-intdata",
        "dev-agents": "dev-agents",
        "dev-codex": "dev-agents",
        "dev-openclaw": "dev-agents",
        "prod-leon": "prod-leon",
    }
    return mapping.get(requested_host.strip())


def get_suffix() -> str:
    return os.getenv("INT_SSH_TAILNET_SUFFIX", "tailf0f164.ts.net").strip() or "tailf0f164.ts.net"


def build_spec(logical_host: str) -> TargetSpec | None:
    suffix = get_suffix()
    if logical_host == "dev-intdata":
        public_host = os.getenv("INT_SSH_DEV_PUBLIC_HOST", "vds.intdata.pro").strip() or "vds.intdata.pro"
        tail_node = os.getenv("INT_SSH_DEV_TAILNET_NODE", "vds-intdata-pro").strip() or "vds-intdata-pro"
        tailnet_host = os.getenv("INT_SSH_DEV_TAILNET_HOST", "").strip() or f"{tail_node}.{suffix}"
        return TargetSpec(
            logical_host=logical_host,
            user="intdata",
            identity_file="~/.ssh/id_ed25519_vds_intdata_intdata",
            public_host=public_host,
            tailnet_host=tailnet_host,
            public_alias="int-dev-intdata-public",
            tailnet_alias="int-dev-intdata-tailnet",
        )
    if logical_host == "dev-agents":
        public_host = os.getenv("INT_SSH_DEV_PUBLIC_HOST", "vds.intdata.pro").strip() or "vds.intdata.pro"
        tail_node = os.getenv("INT_SSH_DEV_TAILNET_NODE", "vds-intdata-pro").strip() or "vds-intdata-pro"
        tailnet_host = os.getenv("INT_SSH_DEV_TAILNET_HOST", "").strip() or f"{tail_node}.{suffix}"
        return TargetSpec(
            logical_host=logical_host,
            user="agents",
            identity_file="~/.ssh/id_ed25519_vds_intdata_agents",
            public_host=public_host,
            tailnet_host=tailnet_host,
            public_alias="int-dev-agents-public",
            tailnet_alias="int-dev-agents-tailnet",
        )
    if logical_host == "prod-leon":
        public_host = os.getenv("INT_SSH_PROD_PUBLIC_HOST", "vds.punkt-b.pro").strip() or "vds.punkt-b.pro"
        tail_node = os.getenv("INT_SSH_PROD_TAILNET_NODE", "vds-punkt-b-pro").strip() or "vds-punkt-b-pro"
        tailnet_host = os.getenv("INT_SSH_PROD_TAILNET_HOST", "").strip() or f"{tail_node}.{suffix}"
        return TargetSpec(
            logical_host=logical_host,
            user="leon",
            identity_file="~/.ssh/id_ed25519",
            public_host=public_host,
            tailnet_host=tailnet_host,
            public_alias="int-prod-leon-public",
            tailnet_alias="int-prod-leon-tailnet",
        )
    return None


def resolve_ssh_executable() -> str:
    if os.name == "nt":
        for candidate in ("ssh.cmd", "ssh.bat", "ssh.exe", "ssh"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
    return shutil.which("ssh") or "ssh"


def endpoint_to_args(spec: TargetSpec, transport: str, config_path: Path | None, probe_timeout_sec: int) -> tuple[list[str], str]:
    args = [
        "-o", "BatchMode=yes",
        "-o", "PasswordAuthentication=no",
        "-o", "KbdInteractiveAuthentication=no",
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"ConnectTimeout={probe_timeout_sec}",
    ]
    if config_path is not None:
        alias = spec.tailnet_alias if transport == "tailnet" else spec.public_alias
        args.extend(["-F", str(config_path), alias])
        return args, alias

    host = spec.tailnet_host if transport == "tailnet" else spec.public_host
    args.extend(["-o", "IdentitiesOnly=yes", "-i", spec.identity_file, f"{spec.user}@{host}"])
    return args, f"{spec.user}@{host}"


def probe_endpoint(spec: TargetSpec, config_path: Path | None, probe_timeout_sec: int) -> bool:
    args, _ = endpoint_to_args(spec, "tailnet", config_path, probe_timeout_sec)
    completed = subprocess.run(
        [resolve_ssh_executable(), *args, "true"],
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def resolve_target(requested_host: str, *, mode: str | None = None, probe_timeout_sec: int | None = None) -> dict[str, object]:
    resolved_mode = get_mode(mode)
    resolved_timeout = get_probe_timeout_sec(str(probe_timeout_sec) if probe_timeout_sec is not None else None)
    logical_host = resolve_logical_host(requested_host)

    if logical_host is None:
        return {
            "requested_host": requested_host,
            "logical_host": None,
            "resolved_mode": "legacy",
            "transport": "legacy",
            "destination": requested_host,
            "ssh_args": [requested_host],
            "probe_succeeded": None,
            "fallback_used": False,
            "tailnet_host": None,
            "public_host": None,
        }

    spec = build_spec(logical_host)
    if spec is None:
        raise RuntimeError(f"no SSH target spec found for logical host '{logical_host}'")

    config_path = get_config_path()
    probe_succeeded: bool | None = None
    fallback_used = False

    if resolved_mode == "public":
        transport = "public"
    elif resolved_mode == "tailnet":
        transport = "tailnet"
    else:
        probe_succeeded = probe_endpoint(spec, config_path, resolved_timeout)
        transport = "tailnet" if probe_succeeded else "public"
        fallback_used = not probe_succeeded

    ssh_args, destination = endpoint_to_args(spec, transport, config_path, resolved_timeout)
    return {
        "requested_host": requested_host,
        "logical_host": logical_host,
        "resolved_mode": resolved_mode,
        "transport": transport,
        "destination": destination,
        "ssh_args": ssh_args,
        "probe_succeeded": probe_succeeded,
        "fallback_used": fallback_used,
        "tailnet_host": spec.tailnet_host,
        "public_host": spec.public_host,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve canonical SSH target metadata for /int tooling")
    parser.add_argument("--requested-host", required=True)
    parser.add_argument("--mode", default="")
    parser.add_argument("--probe-timeout-sec", type=int, default=0)
    parser.add_argument("--capability", default="int_ssh_resolve")
    parser.add_argument("--binding-origin", default="")
    parser.add_argument("--destination-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    binding_origin = args.binding_origin or "codex/bin/int_ssh_resolve.py"
    assert_binding(args.capability, binding_origin)
    payload = resolve_target(
        args.requested_host,
        mode=args.mode or None,
        probe_timeout_sec=args.probe_timeout_sec or None,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    elif args.destination_only:
        print(payload["destination"])
    else:
        print(payload["destination"])
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


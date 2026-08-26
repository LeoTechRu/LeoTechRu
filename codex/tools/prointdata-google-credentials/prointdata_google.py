#!/usr/bin/env python3
"""Replicate one ProIntData Google OAuth bundle into protected native stores."""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib
from typing import Any


SCHEMA_VERSION = 1
ACCOUNT = "prointdata@gmail.com"
CLIENT_ID_SHA256_12 = "9544e2cb1dc9"
TOKEN_URI = "https://oauth2.googleapis.com/token"
USERINFO_URI = "https://www.googleapis.com/oauth2/v2/userinfo"
WINDOWS_CREDENTIAL_TARGET = "intdata/google/prointdata/oauth-bundle-v1"
SYSTEMD_CREDENTIAL_NAME = "prointdata-google-oauth-bundle-v1"
WINDOWS_CREDENTIAL_BLOB_MAX = 5 * 512
REQUIRED_FIELDS = ("client_id", "client_secret", "refresh_token", "token_uri", "scopes")
DEFAULT_SERVICES = (
    "gmail",
    "calendar",
    "drive",
    "contacts",
    "sheets",
    "docs",
    "slides",
    "tasks",
    "forms",
    "chat",
    "classroom",
)
DEFAULT_HERMES_PROFILES = ("intbrain", "intbridge")


class CredentialError(RuntimeError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _redacted_error(exc: BaseException) -> str:
    if isinstance(exc, CredentialError):
        return f"{type(exc).__name__}: {str(exc)[:160]}"
    return f"{type(exc).__name__}: credential operation failed"


def _normalize_scopes(value: Any) -> list[str]:
    if isinstance(value, str):
        scopes = value.split()
    elif isinstance(value, list):
        scopes = [str(item) for item in value]
    else:
        raise CredentialError("scopes must be a string or list")
    normalized = sorted({scope.strip() for scope in scopes if scope.strip()})
    if not normalized:
        raise CredentialError("scopes are empty")
    return normalized


def bundle_from_authorized_user(payload: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if not payload.get(field)]
    if missing:
        raise CredentialError(f"authorized-user payload misses: {', '.join(missing)}")
    if payload["token_uri"] != TOKEN_URI:
        raise CredentialError("unexpected OAuth token endpoint")
    if _fingerprint(str(payload["client_id"])) != CLIENT_ID_SHA256_12:
        raise CredentialError("unexpected OAuth client")

    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "bundle_version": f"{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}",
        "account": ACCOUNT,
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "oauth": {
            "client_id": str(payload["client_id"]),
            "client_secret": str(payload["client_secret"]),
            "refresh_token": str(payload["refresh_token"]),
            "token_uri": str(payload["token_uri"]),
            "scopes": _normalize_scopes(payload["scopes"]),
        },
    }
    validate_bundle(bundle)
    return bundle


def validate_bundle(bundle: dict[str, Any]) -> None:
    if bundle.get("schema_version") != SCHEMA_VERSION:
        raise CredentialError("unsupported schema_version")
    if bundle.get("account") != ACCOUNT:
        raise CredentialError("unexpected Google account")
    if not bundle.get("bundle_version"):
        raise CredentialError("bundle_version is missing")
    oauth = bundle.get("oauth")
    if not isinstance(oauth, dict):
        raise CredentialError("oauth object is missing")
    missing = [field for field in REQUIRED_FIELDS if not oauth.get(field)]
    if missing:
        raise CredentialError(f"bundle misses: {', '.join(missing)}")
    if oauth["token_uri"] != TOKEN_URI:
        raise CredentialError("unexpected OAuth token endpoint")
    if _fingerprint(str(oauth["client_id"])) != CLIENT_ID_SHA256_12:
        raise CredentialError("unexpected OAuth client")
    oauth["scopes"] = _normalize_scopes(oauth["scopes"])


def safe_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    validate_bundle(bundle)
    oauth = bundle["oauth"]
    return {
        "schema_version": bundle["schema_version"],
        "bundle_version": bundle["bundle_version"],
        "account": bundle["account"],
        "client_id_fp": _fingerprint(oauth["client_id"]),
        "credential_fp": _fingerprint(oauth["refresh_token"]),
        "scope_count": len(oauth["scopes"]),
    }


def _http_json(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    request = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        exc.read()
        raise CredentialError(f"OAuth HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise CredentialError(f"OAuth network failure: {type(exc).__name__}") from None


def refresh_and_verify(bundle: dict[str, Any]) -> dict[str, Any]:
    validate_bundle(bundle)
    oauth = bundle["oauth"]
    form = urllib.parse.urlencode(
        {
            "client_id": oauth["client_id"],
            "client_secret": oauth["client_secret"],
            "refresh_token": oauth["refresh_token"],
            "grant_type": "refresh_token",
        }
    ).encode("ascii")
    token = _http_json(oauth["token_uri"], data=form)
    access_token = token.get("access_token")
    if not access_token:
        raise CredentialError("OAuth response has no access token")
    identity = _http_json(
        USERINFO_URI,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if str(identity.get("email", "")).lower() != ACCOUNT:
        raise CredentialError("OAuth token belongs to another account")
    if token.get("refresh_token") and token["refresh_token"] != oauth["refresh_token"]:
        bundle = json.loads(json.dumps(bundle))
        bundle["oauth"]["refresh_token"] = token["refresh_token"]
        bundle["bundle_version"] = (
            dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + uuid.uuid4().hex[:8]
        )
    expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
        seconds=int(token.get("expires_in", 3600))
    )
    return {
        "bundle": bundle,
        "access_token": access_token,
        "expiry": expires_at.isoformat(),
    }


def _windows_local_appdata() -> pathlib.Path:
    value = os.environ.get("LOCALAPPDATA")
    if not value:
        raise CredentialError("LOCALAPPDATA is not set")
    return pathlib.Path(value)


def default_hermes_home() -> pathlib.Path:
    explicit = os.environ.get("HERMES_HOME")
    if explicit:
        return pathlib.Path(explicit)
    if os.name == "nt":
        return _windows_local_appdata() / "hermes"
    return pathlib.Path.home() / ".hermes"


def default_hermes_homes() -> list[pathlib.Path]:
    main = default_hermes_home()
    homes = [main]
    if os.name != "nt":
        for profile in DEFAULT_HERMES_PROFILES:
            profile_home = main / "profiles" / profile
            if profile_home.is_dir():
                homes.append(profile_home)
    return homes


def default_state_path() -> pathlib.Path:
    if os.name == "nt":
        return _windows_local_appdata() / "intdata" / "prointdata-google" / "state.json"
    return pathlib.Path.home() / ".config" / "prointdata-google" / "state.json"


def default_systemd_credential_path() -> pathlib.Path:
    return (
        pathlib.Path.home()
        / ".config"
        / "credentials"
        / f"{SYSTEMD_CREDENTIAL_NAME}.cred"
    )


def _atomic_write(path: pathlib.Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = pathlib.Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":
            os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _write_state(path: pathlib.Path, bundle: dict[str, Any], consumers: list[str]) -> None:
    state = safe_summary(bundle)
    state["consumers"] = sorted(consumers)
    state["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    _atomic_write(path, json.dumps(state, indent=2).encode("utf-8"))


def _load_state(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


if os.name == "nt":
    from ctypes import wintypes

    class _CREDENTIALW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]


def _windows_store_write(bundle: dict[str, Any]) -> None:
    compressed = zlib.compress(_canonical_json(bundle), level=9)
    if len(compressed) > WINDOWS_CREDENTIAL_BLOB_MAX:
        raise CredentialError("credential bundle exceeds Windows native-store limit")
    blob = (ctypes.c_ubyte * len(compressed)).from_buffer_copy(compressed)
    credential = _CREDENTIALW()
    credential.Type = 1
    credential.TargetName = WINDOWS_CREDENTIAL_TARGET
    credential.Comment = "ProIntData Google OAuth bundle shared by local Codex and Hermes"
    credential.CredentialBlobSize = len(compressed)
    credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
    credential.Persist = 2
    credential.UserName = ACCOUNT
    advapi32 = ctypes.WinDLL("Advapi32.dll")
    advapi32.CredWriteW.argtypes = [ctypes.POINTER(_CREDENTIALW), wintypes.DWORD]
    advapi32.CredWriteW.restype = wintypes.BOOL
    if not advapi32.CredWriteW(ctypes.byref(credential), 0):
        raise ctypes.WinError()


def _windows_store_read() -> dict[str, Any]:
    pointer = ctypes.POINTER(_CREDENTIALW)()
    advapi32 = ctypes.WinDLL("Advapi32.dll")
    advapi32.CredReadW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(_CREDENTIALW)),
    ]
    advapi32.CredReadW.restype = wintypes.BOOL
    advapi32.CredFree.argtypes = [ctypes.c_void_p]
    if not advapi32.CredReadW(
        WINDOWS_CREDENTIAL_TARGET, 1, 0, ctypes.byref(pointer)
    ):
        raise ctypes.WinError()
    try:
        item = pointer.contents
        raw = ctypes.string_at(item.CredentialBlob, item.CredentialBlobSize)
        bundle = json.loads(zlib.decompress(raw))
        validate_bundle(bundle)
        return bundle
    finally:
        advapi32.CredFree(pointer)


def _systemd_store_write(bundle: dict[str, Any], path: pathlib.Path) -> None:
    result = subprocess.run(
        [
            "systemd-creds",
            "encrypt",
            "--user",
            f"--name={SYSTEMD_CREDENTIAL_NAME}",
            "-",
            "-",
        ],
        input=_canonical_json(bundle),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise CredentialError("systemd-creds encrypt failed")
    _atomic_write(path, result.stdout)


def _systemd_store_read(path: pathlib.Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "systemd-creds",
            "decrypt",
            "--user",
            f"--name={SYSTEMD_CREDENTIAL_NAME}",
            str(path),
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise CredentialError("systemd-creds decrypt failed")
    bundle = json.loads(result.stdout)
    validate_bundle(bundle)
    return bundle


def store_write(bundle: dict[str, Any], credential_path: pathlib.Path | None) -> None:
    validate_bundle(bundle)
    if os.name == "nt":
        _windows_store_write(bundle)
    else:
        _systemd_store_write(bundle, credential_path or default_systemd_credential_path())


def store_read(credential_path: pathlib.Path | None) -> dict[str, Any]:
    if os.name == "nt":
        return _windows_store_read()
    return _systemd_store_read(credential_path or default_systemd_credential_path())


def _authorized_user_payload(
    bundle: dict[str, Any], access_token: str, expiry: str
) -> dict[str, Any]:
    oauth = bundle["oauth"]
    return {
        "type": "authorized_user",
        "token": access_token,
        "refresh_token": oauth["refresh_token"],
        "token_uri": oauth["token_uri"],
        "client_id": oauth["client_id"],
        "client_secret": oauth["client_secret"],
        "scopes": oauth["scopes"],
        "expiry": expiry,
    }


def _materialize_hermes(
    bundle: dict[str, Any],
    access_token: str,
    expiry: str,
    homes: list[pathlib.Path],
) -> list[str]:
    payload = _authorized_user_payload(bundle, access_token, expiry)
    consumers: list[str] = []
    for home in homes:
        token_path = home / "google_token.json"
        _atomic_write(token_path, json.dumps(payload, indent=2).encode("utf-8"))
        consumers.append(f"hermes:{home}")
    return consumers


def _snapshot_token_files(homes: list[pathlib.Path]) -> dict[pathlib.Path, bytes | None]:
    snapshots: dict[pathlib.Path, bytes | None] = {}
    for home in homes:
        path = home / "google_token.json"
        try:
            snapshots[path] = path.read_bytes()
        except FileNotFoundError:
            snapshots[path] = None
    return snapshots


def _restore_token_files(snapshots: dict[pathlib.Path, bytes | None]) -> None:
    for path, content in snapshots.items():
        if content is None:
            path.unlink(missing_ok=True)
        else:
            _atomic_write(path, content)


def _gog_import(bundle: dict[str, Any], gog_bin: str) -> str:
    if not shutil.which(gog_bin):
        raise CredentialError(f"gog executable not found: {gog_bin}")
    envelope = {
        "email": ACCOUNT,
        "client": "default",
        "services": list(DEFAULT_SERVICES),
        "created_at": bundle["created_at"],
        "refresh_token": bundle["oauth"]["refresh_token"],
    }
    result = subprocess.run(
        [gog_bin, "auth", "tokens", "import", "-", "--json", "--no-input"],
        input=_canonical_json(envelope),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise CredentialError("gog native token import failed")
    return "gog:keyring"


def apply_consumers(
    bundle: dict[str, Any],
    *,
    homes: list[pathlib.Path],
    gog_bin: str,
    state_path: pathlib.Path,
) -> dict[str, Any]:
    verified = refresh_and_verify(bundle)
    current_bundle = verified["bundle"]
    snapshots = _snapshot_token_files(homes)
    try:
        consumers = _materialize_hermes(
            current_bundle, verified["access_token"], verified["expiry"], homes
        )
        consumers.append(_gog_import(current_bundle, gog_bin))
    except Exception:
        _restore_token_files(snapshots)
        raise
    _write_state(state_path, current_bundle, consumers)
    return {
        "summary": safe_summary(current_bundle),
        "consumers": consumers,
        "_bundle": current_bundle,
    }


def _public_apply_result(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if not key.startswith("_")}


def _read_json_input(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _homes(values: list[str] | None) -> list[pathlib.Path]:
    return [pathlib.Path(value) for value in values] if values else default_hermes_homes()


def _remote_receive(
    ssh_target: str, remote_command: str, bundle: dict[str, Any], check_only: bool
) -> dict[str, Any]:
    command = ["ssh", ssh_target, remote_command, "receive"]
    if check_only:
        command.append("--check-only")
    result = subprocess.run(
        command,
        input=_canonical_json(bundle),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise CredentialError(f"remote {'check' if check_only else 'apply'} failed")
    return json.loads(result.stdout)


def _run_gws(
    bundle: dict[str, Any],
    *,
    gws_bin: str,
    gws_args: list[str],
    credential_path: pathlib.Path | None,
) -> int:
    if not shutil.which(gws_bin):
        raise CredentialError(f"gws executable not found: {gws_bin}")
    verified = refresh_and_verify(bundle)
    current_bundle = verified["bundle"]
    if current_bundle["bundle_version"] != bundle["bundle_version"]:
        store_write(current_bundle, credential_path)
    environment = os.environ.copy()
    environment["GOOGLE_WORKSPACE_CLI_TOKEN"] = verified["access_token"]
    return subprocess.run([gws_bin, *gws_args], env=environment).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prointdata-google")
    parser.add_argument("--credential-path", type=pathlib.Path)
    parser.add_argument("--state-path", type=pathlib.Path, default=default_state_path())
    parser.add_argument("--hermes-home", action="append")
    parser.add_argument("--gog-bin", default="gog")
    parser.add_argument("--gws-bin", default="gws")
    subcommands = parser.add_subparsers(dest="command", required=True)

    create = subcommands.add_parser("create")
    create.add_argument("--input", default="-")
    create.add_argument("--check-only", action="store_true")

    subcommands.add_parser("status")
    subcommands.add_parser("apply")
    gws = subcommands.add_parser("gws")
    gws.add_argument("gws_args", nargs=argparse.REMAINDER)

    receive = subcommands.add_parser("receive")
    receive.add_argument("--check-only", action="store_true")

    replicate = subcommands.add_parser("replicate")
    replicate.add_argument("--ssh-target", default="vds")
    replicate.add_argument(
        "--remote-command",
        default="/int/tools/codex/tools/prointdata-google-credentials/prointdata-google",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "create":
            source = _read_json_input(args.input)
            bundle = bundle_from_authorized_user(source)
            verified = refresh_and_verify(bundle)
            bundle = verified["bundle"]
            if not args.check_only:
                store_write(bundle, args.credential_path)
            print(json.dumps({"ok": True, **safe_summary(bundle)}))
            return 0

        if args.command == "status":
            bundle = store_read(args.credential_path)
            state = _load_state(args.state_path)
            print(json.dumps({"ok": True, "bundle": safe_summary(bundle), "state": state}))
            return 0

        if args.command == "apply":
            bundle = store_read(args.credential_path)
            result = apply_consumers(
                bundle,
                homes=_homes(args.hermes_home),
                gog_bin=args.gog_bin,
                state_path=args.state_path,
            )
            current_bundle = result["_bundle"]
            if current_bundle["bundle_version"] != bundle["bundle_version"]:
                store_write(current_bundle, args.credential_path)
            print(json.dumps({"ok": True, **_public_apply_result(result)}))
            return 0

        if args.command == "gws":
            bundle = store_read(args.credential_path)
            return _run_gws(
                bundle,
                gws_bin=args.gws_bin,
                gws_args=args.gws_args,
                credential_path=args.credential_path,
            )

        if args.command == "receive":
            bundle = json.load(sys.stdin)
            verified = refresh_and_verify(bundle)
            bundle = verified["bundle"]
            if args.check_only:
                print(json.dumps({"ok": True, **safe_summary(bundle)}))
                return 0
            result = apply_consumers(
                bundle,
                homes=_homes(args.hermes_home),
                gog_bin=args.gog_bin,
                state_path=args.state_path,
            )
            store_write(result["_bundle"], args.credential_path)
            print(json.dumps({"ok": True, **_public_apply_result(result)}))
            return 0

        if args.command == "replicate":
            bundle = store_read(args.credential_path)
            local = apply_consumers(
                bundle,
                homes=_homes(args.hermes_home),
                gog_bin=args.gog_bin,
                state_path=args.state_path,
            )
            current_bundle = local["_bundle"]
            if current_bundle["bundle_version"] != bundle["bundle_version"]:
                store_write(current_bundle, args.credential_path)
            _remote_receive(args.ssh_target, args.remote_command, current_bundle, True)
            remote = _remote_receive(
                args.ssh_target, args.remote_command, current_bundle, False
            )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "local": _public_apply_result(local),
                        "remote": remote,
                    }
                )
            )
            return 0
    except Exception as exc:
        print(
            json.dumps({"ok": False, "error": _redacted_error(exc)}),
            file=sys.stderr,
        )
        return 1
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())

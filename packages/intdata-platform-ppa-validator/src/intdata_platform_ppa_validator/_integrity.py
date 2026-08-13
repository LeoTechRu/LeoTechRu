"""Closed integrity checks for the packaged published PPA corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
PLATFORM_ROOT = PACKAGE_ROOT / "platform"
PPA_AGGREGATE_SHA256 = "fa09e94feb956e1f837e1e62082c0d0c694cf07bfa1c2ae7fafb0084ab536277"
TERMINAL_AGGREGATE_SHA256 = "94843c3f5b83b207aa6e3b45cf3c02f8f6f66350c64dce00fc71d9fb2b2072c6"
AGGREGATE_ENCODING = (
    "For each artifact in listed path order: lowercase SHA-256, two ASCII spaces, "
    "path, LF; SHA-256 the concatenated UTF-8 bytes."
)
RAW_SHA256 = {
    "schemas/platform-product-assertion.schema.json": "97c6cd64c9f8b9b79c3889b47b05d567353af4efb8618ede7e8ec5ca1ebd441b",
    "conformance/platform-product-assertion-v1.vectors.json": "6517584d65b3c8bcb7be1b50e0de8806a199f20c7f290f2986a7f08d71b5fa46",
    "conformance/platform-product-assertion-v1.digests.json": "3e821076803b3bac76a1021fe2919690596d340af1c474edd08328ef8c6dff3a",
    "conformance/bridge-oauth-registration-uri-v1.profile.json": "24ce608e4f000206e97d6e50bcfb16055064049675434629ba8e85560f7fe070",
    "conformance/bridge-oauth-registration-uri-v1.vectors.json": "2712a642ff85abf7e7caac42123afe01639413963bb5ca92c667dcc735c37c89",
    "conformance/terminal-dependency-digests.json": "000e868d2b972d8ad11af021f7df052fbf81fb3d60f09ed1373ed114e273a9e4",
    "conformance/validate-terminal-dependencies.py": "9eb7ce0eac565585adcab4958da95678e62ba5b34f23d5cd6fcbdc9c5ca22d43",
}


class IntegrityError(ValueError):
    """The fixed embedded corpus is incomplete, altered, or internally inconsistent."""


def _read(relative_path: str) -> bytes:
    if relative_path not in RAW_SHA256:
        raise IntegrityError("undeclared-resource")
    try:
        return (PLATFORM_ROOT / relative_path).read_bytes()
    except OSError as error:
        raise IntegrityError(f"missing-resource:{relative_path}") from error


def _load_manifest(relative_path: str) -> dict[str, object]:
    try:
        value = json.loads(_read(relative_path).decode("utf-8", "strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IntegrityError(f"invalid-manifest:{relative_path}") from error
    if not isinstance(value, dict):
        raise IntegrityError(f"invalid-manifest:{relative_path}")
    return value


def _verify_manifest(
    manifest: dict[str, object],
    expected: tuple[str, tuple[str, ...], str],
) -> None:
    manifest_name, expected_paths, expected_aggregate = expected
    if manifest.get("algorithm") != "sha256" or manifest.get("aggregate_encoding") != AGGREGATE_ENCODING:
        raise IntegrityError(f"manifest-metadata:{manifest_name}")
    entries = manifest.get("artifacts")
    paths = [entry.get("path") if isinstance(entry, dict) else None for entry in entries] if isinstance(entries, list) else []
    if paths != list(expected_paths):
        raise IntegrityError(f"manifest-paths:{manifest_name}")
    lines: list[str] = []
    for entry, relative_path in zip(entries, expected_paths, strict=True):
        if not isinstance(entry, dict) or set(entry) - {"path", "id", "sha256"} or entry.get("sha256") != RAW_SHA256[relative_path]:
            raise IntegrityError(f"manifest-entry:{manifest_name}")
        lines.append(f"{RAW_SHA256[relative_path]}  {relative_path}\n")
    aggregate = "".join(lines).encode("utf-8")
    if (
        manifest.get("aggregate_manifest_utf8_hex") != aggregate.hex()
        or manifest.get("aggregate_sha256") != expected_aggregate
        or hashlib.sha256(aggregate).hexdigest() != expected_aggregate
    ):
        raise IntegrityError(f"manifest-aggregate:{manifest_name}")


def verify_embedded() -> None:
    """Verify every embedded raw byte plus both published aggregate semantics."""
    for relative_path, expected_hash in RAW_SHA256.items():
        if hashlib.sha256(_read(relative_path)).hexdigest() != expected_hash:
            raise IntegrityError(f"raw-sha256:{relative_path}")
    _verify_manifest(
        _load_manifest("conformance/platform-product-assertion-v1.digests.json"),
        (
            "ppa",
            (
                "conformance/platform-product-assertion-v1.vectors.json",
                "schemas/platform-product-assertion.schema.json",
            ),
            PPA_AGGREGATE_SHA256,
        ),
    )
    _verify_manifest(
        _load_manifest("conformance/terminal-dependency-digests.json"),
        (
            "terminal",
            (
                "conformance/bridge-oauth-registration-uri-v1.profile.json",
                "conformance/bridge-oauth-registration-uri-v1.vectors.json",
                "conformance/platform-product-assertion-v1.vectors.json",
                "schemas/platform-product-assertion.schema.json",
            ),
            TERMINAL_AGGREGATE_SHA256,
        ),
    )

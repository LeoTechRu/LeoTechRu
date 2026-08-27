"""Closed integrity checks for the packaged published PPA corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
PLATFORM_ROOT = PACKAGE_ROOT / "platform"
PPA_AGGREGATE_SHA256 = "968b42e2a14995f37f4b74bcbca841b861002864d39e05ed3d856b3176d7d1dc"
TERMINAL_AGGREGATE_SHA256 = "a1125f44984203c3231ecaa4ea6e9ea77624d0d003eb9e1cef09edd5f60b5f0f"
AGGREGATE_ENCODING = (
    "For each artifact in listed path order: lowercase SHA-256, two ASCII spaces, "
    "path, LF; SHA-256 the concatenated UTF-8 bytes."
)
RAW_SHA256 = {
    "schemas/platform-product-assertion.schema.json": "449498ec8705c29b0aa8729d32a458f447118027c511b12b211fff9b453dc4b7",
    "conformance/platform-product-assertion-v1.vectors.json": "f2a75d414428aeed9b18a3d4ee4a8f6e6daa2b397644bb0a7f5372a68ac75ebd",
    "conformance/platform-product-assertion-v1.digests.json": "4b435607939fd194a902c58aec315aaf8affd0140d53ba09bdc2003a7fed9a8f",
    "conformance/bridge-oauth-registration-uri-v1.profile.json": "24ce608e4f000206e97d6e50bcfb16055064049675434629ba8e85560f7fe070",
    "conformance/bridge-oauth-registration-uri-v1.vectors.json": "2712a642ff85abf7e7caac42123afe01639413963bb5ca92c667dcc735c37c89",
    "conformance/terminal-dependency-digests.json": "e8f76456fd50faf89788f47c3c79b47ed18bb9f92c0983f4e68f7ceb2d9ac63c",
    "conformance/validate-terminal-dependencies.py": "4a007f921eeae3e790974d901eae8d7f3b46143dca584b6dec6d4444b83d51df",
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

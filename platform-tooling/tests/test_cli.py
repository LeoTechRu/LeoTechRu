import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from intdata_tooling._schemas import (
    DRAFT_2020_12,
    EXPECTED_CONFORMANCE_VECTOR_FILENAME,
    EXPECTED_CONFORMANCE_VECTOR_ID,
    EXPECTED_PROFILE_DOCUMENT,
    EXPECTED_PROFILE_FILENAME,
    EXPECTED_PROFILE_ID,
    EXPECTED_PROFILE_VECTORS_FILENAME,
    EXPECTED_SCHEMA_IDS,
    EXPECTED_SCHEMA_REGISTRY,
)


def _pretty(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _schema(name: str, kind: str) -> dict:
    return {
        "$schema": DRAFT_2020_12,
        "$id": f"urn:intdata:schema:{name}:v1",
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "value"],
        "properties": {
            "kind": {"const": kind},
            "value": {"type": "string"},
        },
    }


@pytest.fixture
def schema_set(tmp_path: Path) -> Path:
    special = {
        "module-manifest": "module",
        "installation-manifest": "installation",
        "installation-lock": "lock",
    }
    entries = []
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    for schema_id in sorted(EXPECTED_SCHEMA_IDS):
        name = schema_id.removeprefix("urn:intdata:schema:").removesuffix(":v1")
        if name in special:
            schema = _schema(name, special[name])
        else:
            schema = {
                "$schema": DRAFT_2020_12,
                "$id": schema_id,
                "type": "object",
                "additionalProperties": False,
            }
        raw = _pretty(schema)
        entry_name, filename = EXPECTED_SCHEMA_REGISTRY[schema_id]
        (tmp_path / filename).write_bytes(raw)
        entries.append(
            {
                "name": entry_name,
                "version": "v1",
                "id": schema["$id"],
                "filename": filename,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    profile_raw = _pretty(deepcopy(EXPECTED_PROFILE_DOCUMENT))
    profile_path = tmp_path / EXPECTED_PROFILE_FILENAME
    profile_path.parent.mkdir()
    profile_path.write_bytes(profile_raw)
    profile_vectors_raw = _pretty(
        {
            "vector_set_id": EXPECTED_PROFILE_ID,
            "version": "v1",
            "uri_cases": [],
            "redirect_array_cases": [],
            "token_array_cases": [],
        }
    )
    (tmp_path / EXPECTED_PROFILE_VECTORS_FILENAME).write_bytes(profile_vectors_raw)
    vectors_raw = _pretty({"vector_set_version": "1.0.0"})
    (tmp_path / EXPECTED_CONFORMANCE_VECTOR_FILENAME).write_bytes(vectors_raw)
    set_path = tmp_path / "schema-set.json"
    set_path.write_bytes(
        _pretty(
            {
                "schema_set_version": "1.0.0",
                "draft": DRAFT_2020_12,
                "schemas": entries,
                "profiles": [
                    {
                        "id": EXPECTED_PROFILE_ID,
                        "version": "v1",
                        "filename": EXPECTED_PROFILE_FILENAME,
                        "sha256": hashlib.sha256(profile_raw).hexdigest(),
                        "vectors_filename": EXPECTED_PROFILE_VECTORS_FILENAME,
                        "vectors_sha256": hashlib.sha256(
                            profile_vectors_raw
                        ).hexdigest(),
                    }
                ],
                "vectors": [
                    {
                        "id": EXPECTED_CONFORMANCE_VECTOR_ID,
                        "version": "1.0.0",
                        "filename": EXPECTED_CONFORMANCE_VECTOR_FILENAME,
                        "sha256": hashlib.sha256(vectors_raw).hexdigest(),
                    }
                ],
            }
        )
    )
    return set_path


def _run(*arguments: object, input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    environment = os.environ.copy()
    return subprocess.run(
        [sys.executable, "-m", "intdata_tooling", *(str(item) for item in arguments)],
        input=input_bytes,
        capture_output=True,
        check=False,
        env=environment,
    )


def test_command_inventory_is_closed_to_wave_one() -> None:
    result = _run("--help")
    assert result.returncode == 0
    output = result.stdout.decode("utf-8")
    assert "{schema,module,installation,lock}" in output
    for forbidden in ("release", "sign", "family", "publish", "activate"):
        assert forbidden not in output


@pytest.mark.parametrize(
    ("group", "kind"),
    [("module", "module"), ("installation", "installation")],
)
def test_named_validate_commands(group: str, kind: str, schema_set: Path) -> None:
    document = schema_set.parent / f"{kind}.json"
    document.write_bytes(f'{{"kind":"{kind}","value":"ok"}}'.encode())
    result = _run(group, "validate", "--schema-set", schema_set, document)
    assert result.returncode == 0
    assert result.stdout == b"valid\n"
    assert result.stderr == b""


def test_generic_canonicalize_and_digest_are_exact(schema_set: Path) -> None:
    document = schema_set.parent / "module.json"
    document.write_bytes(b'{"value":"ok","kind":"module"}')
    base = (
        "schema",
        "canonicalize",
        "--schema-set",
        schema_set,
        "--schema",
        "urn:intdata:schema:module-manifest:v1",
        document,
    )
    canonical = _run(*base)
    expected = b'{"kind":"module","value":"ok"}'
    assert canonical.returncode == 0
    assert canonical.stdout == expected
    assert canonical.stderr == b""

    digest = _run(
        "schema",
        "digest",
        "--schema-set",
        schema_set,
        "--schema",
        "urn:intdata:schema:module-manifest:v1",
        document,
    )
    assert digest.returncode == 0
    assert digest.stdout == hashlib.sha256(expected).hexdigest().encode() + b"\n"


def test_generic_validate_accepts_stdin(schema_set: Path) -> None:
    result = _run(
        "schema",
        "validate",
        "--schema-set",
        schema_set,
        "--schema",
        "urn:intdata:schema:module-manifest:v1",
        "-",
        input_bytes=b'{"kind":"module","value":"stdin"}',
    )
    assert result.returncode == 0
    assert result.stdout == b"valid\n"


def test_lock_verify_compares_expected_digest(schema_set: Path) -> None:
    document = schema_set.parent / "lock.json"
    document.write_bytes(b'{"kind":"lock","value":"bound"}')
    expected_bytes = b'{"kind":"lock","value":"bound"}'
    expected_digest = hashlib.sha256(expected_bytes).hexdigest()
    result = _run(
        "lock",
        "verify",
        "--schema-set",
        schema_set,
        "--expected-digest",
        expected_digest,
        document,
    )
    assert result.returncode == 0
    assert result.stdout == expected_digest.encode() + b"\n"

    mismatch = _run(
        "lock",
        "verify",
        "--schema-set",
        schema_set,
        "--expected-digest",
        "0" * 64,
        document,
    )
    assert mismatch.returncode == 2
    assert b"lock digest mismatch" in mismatch.stderr


def test_unknown_field_and_outer_whitespace_fail_closed(schema_set: Path) -> None:
    unknown = schema_set.parent / "unknown.json"
    unknown.write_bytes(b'{"kind":"module","value":"ok","extra":true}')
    result = _run("module", "validate", "--schema-set", schema_set, unknown)
    assert result.returncode == 2
    assert b"Additional properties" in result.stderr

    whitespace = schema_set.parent / "whitespace.json"
    whitespace.write_bytes(b'{"kind":"module","value":"ok"}\n')
    result = _run("module", "validate", "--schema-set", schema_set, whitespace)
    assert result.returncode == 2
    assert b"leading or trailing" in result.stderr


def test_schema_set_is_always_explicit() -> None:
    result = _run("module", "validate", "module.json")
    assert result.returncode == 2
    assert b"--schema-set" in result.stderr

import hashlib
import json
import socket
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
    SchemaSet,
    SchemaSetError,
)


ROOT = Path(__file__).resolve().parents[2]


def _pretty(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _write_set(tmp_path: Path, schemas: list[tuple[str, dict]]) -> Path:
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    supplied = {schema["$id"]: (name, schema) for name, schema in schemas}
    entries = []
    for schema_id in sorted(EXPECTED_SCHEMA_IDS):
        slug = schema_id.removeprefix("urn:intdata:schema:").removesuffix(":v1")
        _, schema = supplied.pop(
            schema_id,
            (
                slug,
                _schema(slug, type="object", additionalProperties=False),
            ),
        )
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
    for name, schema in supplied.values():
        raw = _pretty(schema)
        filename = f"schemas/{name}.schema.json"
        (tmp_path / filename).write_bytes(raw)
        entries.append(
            {
                "name": name,
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


def _schema(name: str, **keywords: object) -> dict:
    return {
        "$schema": DRAFT_2020_12,
        "$id": f"urn:intdata:schema:{name}:v1",
        **keywords,
    }


def test_schema_set_v1_identity_is_exact() -> None:
    assert len(EXPECTED_SCHEMA_IDS) == 13
    assert (
        "urn:intdata:schema:platform-product-assertion:v1"
        in EXPECTED_SCHEMA_IDS
    )


def test_tracked_schema_set_matches_tooling_profile_authority() -> None:
    SchemaSet.load(ROOT / "contracts/platform/v1/schema-set.json")


@pytest.mark.parametrize("version", ["6", "7", "8"])
def test_platform_product_assertion_accepts_uuid_versions_6_through_8(
    version: str,
) -> None:
    schema_set = SchemaSet.load(ROOT / "contracts/platform/v1/schema-set.json")
    document = json.loads(
        (
            ROOT
            / "contracts/platform/v1/fixtures/valid/platform-product-assertion-user.json"
        ).read_text(encoding="utf-8")
    )
    document["claims"]["sub"] = f"123e4567-e89b-{version}2d3-a456-426614174000"
    document["claims"]["organization_id"] = (
        f"123e4567-e89b-{version}2d3-b456-426614174001"
    )

    schema_set.validate_value(
        document, "urn:intdata:schema:platform-product-assertion:v1"
    )


@pytest.mark.parametrize(
    "uuid",
    [
        "123e4567-e89b-02d3-a456-426614174000",
        "123e4567-e89b-72d3-7456-426614174000",
    ],
)
def test_platform_product_assertion_rejects_invalid_uuid_version_or_variant(
    uuid: str,
) -> None:
    schema_set = SchemaSet.load(ROOT / "contracts/platform/v1/schema-set.json")
    document = json.loads(
        (
            ROOT
            / "contracts/platform/v1/fixtures/valid/platform-product-assertion-user.json"
        ).read_text(encoding="utf-8")
    )
    document["claims"]["sub"] = uuid

    with pytest.raises(SchemaSetError, match="does not match"):
        schema_set.validate_value(
            document, "urn:intdata:schema:platform-product-assertion:v1"
        )


def test_schema_registry_binds_exact_canonical_type_name(tmp_path: Path) -> None:
    set_path = _write_set(tmp_path, [])
    document = json.loads(set_path.read_text(encoding="utf-8"))
    document["schemas"][0]["name"] = "module-manifest"
    set_path.write_bytes(_pretty(document))
    with pytest.raises(SchemaSetError, match="name must be"):
        SchemaSet.load(set_path)


def test_offline_registry_resolves_tracked_urn_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    leaf = _schema(
        "scan-attestation",
        type="object",
        additionalProperties=False,
        required=["value"],
        properties={"value": {"type": "string"}},
    )
    root = _schema(
        "module-manifest",
        type="object",
        additionalProperties=False,
        required=["leaf"],
        properties={"leaf": {"$ref": leaf["$id"]}},
    )
    schema_set = SchemaSet.load(
        _write_set(
            tmp_path,
            [("scan-attestation", leaf), ("module-manifest", root)],
        )
    )
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    schema_set.validate_raw(b'{"leaf":{"value":"offline"}}', root["$id"])


def test_unknown_field_is_rejected_by_closed_schema(tmp_path: Path) -> None:
    schema = _schema(
        "module-manifest",
        type="object",
        additionalProperties=False,
        properties={"known": {"type": "string"}},
    )
    schema_set = SchemaSet.load(_write_set(tmp_path, [("module-manifest", schema)]))
    with pytest.raises(SchemaSetError, match="Additional properties"):
        schema_set.validate_raw(b'{"known":"ok","unknown":true}', schema["$id"])


def test_validate_value_rejects_floating_point_integer(tmp_path: Path) -> None:
    schema = _schema("module-manifest", type="integer")
    schema_set = SchemaSet.load(_write_set(tmp_path, [("module-manifest", schema)]))

    with pytest.raises(SchemaSetError, match="floating-point value"):
        schema_set.validate_value(1.0, schema["$id"])


def test_validation_error_order_is_deterministic(tmp_path: Path) -> None:
    messages = []
    for directory, required in (
        ("forward", ["zeta", "alpha"]),
        ("reverse", ["alpha", "zeta"]),
    ):
        root = tmp_path / directory
        root.mkdir()
        schema = _schema(
            "module-manifest",
            type="object",
            additionalProperties=False,
            required=required,
            properties={
                "alpha": {"type": "string"},
                "zeta": {"type": "string"},
            },
        )
        schema_set = SchemaSet.load(
            _write_set(root, [("module-manifest", schema)])
        )
        with pytest.raises(SchemaSetError) as caught:
            schema_set.validate_raw(b"{}", schema["$id"])
        messages.append(str(caught.value))

    assert messages[0] == messages[1]
    assert messages[0].endswith("'alpha' is a required property")


def test_unknown_or_remote_reference_fails_before_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    schema = _schema(
        "module-manifest", **{"$ref": "https://example.invalid/schema.json"}
    )
    set_path = _write_set(tmp_path, [("module-manifest", schema)])
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    with pytest.raises(SchemaSetError, match="unavailable offline resource"):
        SchemaSet.load(set_path)


def test_raw_schema_digest_is_verified(tmp_path: Path) -> None:
    schema = _schema("module-manifest", type="object")
    set_path = _write_set(tmp_path, [("module-manifest", schema)])
    (tmp_path / "schemas/module-manifest.schema.json").write_bytes(
        _pretty(schema) + b" "
    )
    with pytest.raises(SchemaSetError, match="schema digest mismatch"):
        SchemaSet.load(set_path)


@pytest.mark.parametrize("orphan", ["orphan.schema.json", "nested"])
def test_schema_directory_rejects_unregistered_files_and_directories(
    tmp_path: Path, orphan: str
) -> None:
    set_path = _write_set(tmp_path, [])
    orphan_path = tmp_path / "schemas" / orphan
    if orphan.endswith(".json"):
        orphan_path.write_bytes(b"{}\n")
    else:
        orphan_path.mkdir()
    with pytest.raises(SchemaSetError, match="schema inventory mismatch"):
        SchemaSet.load(set_path)


def test_registered_schema_on_disk_case_mismatch_is_rejected(tmp_path: Path) -> None:
    set_path = _write_set(tmp_path, [])
    source = tmp_path / "schemas/module-manifest.schema.json"
    source.rename(source.with_name("Module-Manifest.schema.json"))
    with pytest.raises(SchemaSetError, match="on-disk case mismatch"):
        SchemaSet.load(set_path)


def test_unregistered_conformance_vectors_remain_allowed(tmp_path: Path) -> None:
    set_path = _write_set(tmp_path, [])
    conformance = tmp_path / "conformance"
    (conformance / "extra-vectors.json").write_bytes(b"{}\n")
    nested = conformance / "adverse"
    nested.mkdir()
    (nested / "case.json").write_bytes(b"{}\n")
    SchemaSet.load(set_path)


def test_schema_set_and_entries_are_closed(tmp_path: Path) -> None:
    schema = _schema("module-manifest", type="object")
    set_path = _write_set(tmp_path, [("module-manifest", schema)])
    document = json.loads(set_path.read_text(encoding="utf-8"))
    document["unexpected"] = True
    set_path.write_bytes(_pretty(document))
    with pytest.raises(SchemaSetError, match="unknown"):
        SchemaSet.load(set_path)


def test_unknown_schema_id_fails_closed(tmp_path: Path) -> None:
    schema = _schema("module-manifest", type="object")
    schema_set = SchemaSet.load(
        _write_set(tmp_path, [("module-manifest", schema)])
    )
    with pytest.raises(SchemaSetError, match="unknown schema id"):
        schema_set.validate_raw(b"{}", "urn:intdata:schema:missing:v1")


def test_missing_or_extra_schema_identity_fails_closed(tmp_path: Path) -> None:
    set_path = _write_set(tmp_path, [])
    document = json.loads(set_path.read_text(encoding="utf-8"))
    document["schemas"].pop()
    set_path.write_bytes(_pretty(document))
    with pytest.raises(SchemaSetError, match="identity mismatch"):
        SchemaSet.load(set_path)

    other = tmp_path / "other"
    other.mkdir()
    extra = _schema("unexpected", type="object")
    with pytest.raises(SchemaSetError, match="identity mismatch"):
        SchemaSet.load(_write_set(other, [("unexpected", extra)]))


def test_missing_unknown_or_changed_profile_fails_closed(tmp_path: Path) -> None:
    set_path = _write_set(tmp_path, [])
    document = json.loads(set_path.read_text(encoding="utf-8"))
    document["profiles"] = []
    set_path.write_bytes(_pretty(document))
    with pytest.raises(SchemaSetError, match="exactly one profile"):
        SchemaSet.load(set_path)

    other = tmp_path / "other"
    other.mkdir()
    other_set = _write_set(other, [])
    document = json.loads(other_set.read_text(encoding="utf-8"))
    document["profiles"][0]["id"] = "unknown-profile/v1"
    other_set.write_bytes(_pretty(document))
    with pytest.raises(SchemaSetError, match="unknown profile id"):
        SchemaSet.load(other_set)

    changed = tmp_path / "changed"
    changed.mkdir()
    changed_set = _write_set(changed, [])
    (changed / EXPECTED_PROFILE_FILENAME).write_bytes(b"{}\n")
    with pytest.raises(SchemaSetError, match="profile digest mismatch"):
        SchemaSet.load(changed_set)


def _replace_profile(tmp_path: Path, set_path: Path, profile: dict) -> None:
    raw = _pretty(profile)
    (tmp_path / EXPECTED_PROFILE_FILENAME).write_bytes(raw)
    document = json.loads(set_path.read_text(encoding="utf-8"))
    document["profiles"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
    set_path.write_bytes(_pretty(document))


@pytest.mark.parametrize(
    "mutation,error",
    [
        (lambda profile: profile.update({"unknown": True}), "closed v1 identity"),
        (lambda profile: profile.update({"profile_id": "other/v1"}), "closed v1 identity"),
        (lambda profile: profile.update({"$ref": "urn:foreign:profile"}), "forbidden link"),
        (
            lambda profile: profile["output"].update(
                {"form": "https://example.invalid"}
            ),
            "foreign link",
        ),
    ],
)
def test_profile_document_is_closed_self_describing_and_link_free(
    tmp_path: Path, mutation, error: str
) -> None:
    set_path = _write_set(tmp_path, [])
    profile = deepcopy(EXPECTED_PROFILE_DOCUMENT)
    mutation(profile)
    _replace_profile(tmp_path, set_path, profile)
    with pytest.raises(SchemaSetError, match=error):
        SchemaSet.load(set_path)


def test_registered_profile_on_disk_case_mismatch_is_rejected(tmp_path: Path) -> None:
    set_path = _write_set(tmp_path, [])
    source = tmp_path / EXPECTED_PROFILE_FILENAME
    source.rename(source.with_name("Bridge-OAuth-Registration-URI-v1.profile.json"))
    with pytest.raises(SchemaSetError, match="on-disk case mismatch"):
        SchemaSet.load(set_path)


def test_profile_vectors_linkage_digest_and_identity_fail_closed(tmp_path: Path) -> None:
    set_path = _write_set(tmp_path, [])
    document = json.loads(set_path.read_text(encoding="utf-8"))
    document["profiles"][0]["vectors_filename"] = "conformance/other.json"
    set_path.write_bytes(_pretty(document))
    with pytest.raises(SchemaSetError, match="vectors_filename is not canonical"):
        SchemaSet.load(set_path)

    digest_root = tmp_path / "digest"
    digest_root.mkdir()
    digest_set = _write_set(digest_root, [])
    (digest_root / EXPECTED_PROFILE_VECTORS_FILENAME).write_bytes(b"{}\n")
    with pytest.raises(SchemaSetError, match="profile vectors digest mismatch"):
        SchemaSet.load(digest_set)

    identity_root = tmp_path / "identity"
    identity_root.mkdir()
    identity_set = _write_set(identity_root, [])
    vectors = {
        "vector_set_id": "other/v1",
        "version": "v1",
        "uri_cases": [],
        "redirect_array_cases": [],
        "token_array_cases": [],
    }
    raw = _pretty(vectors)
    (identity_root / EXPECTED_PROFILE_VECTORS_FILENAME).write_bytes(raw)
    document = json.loads(identity_set.read_text(encoding="utf-8"))
    document["profiles"][0]["vectors_sha256"] = hashlib.sha256(raw).hexdigest()
    identity_set.write_bytes(_pretty(document))
    with pytest.raises(SchemaSetError, match="vector_set_id"):
        SchemaSet.load(identity_set)


def test_registered_profile_vectors_on_disk_case_mismatch_is_rejected(
    tmp_path: Path,
) -> None:
    set_path = _write_set(tmp_path, [])
    source = tmp_path / EXPECTED_PROFILE_VECTORS_FILENAME
    source.rename(source.with_name("Bridge-OAuth-Registration-URI-v1.vectors.json"))
    with pytest.raises(SchemaSetError, match="on-disk case mismatch"):
        SchemaSet.load(set_path)

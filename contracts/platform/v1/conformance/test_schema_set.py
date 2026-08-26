from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from typing import Any, Callable

import pytest


MODULE_PATH = Path(__file__).with_name("validate.py")
SPEC = importlib.util.spec_from_file_location("platform_v1_conformance", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
CONFORMANCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONFORMANCE)


def test_schema_set_binds_canonical_public_names() -> None:
    schemas, _ = CONFORMANCE._schema_registry()

    CONFORMANCE.validate_schema_set(schemas)


def test_schema_set_rejects_public_name_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    schemas, _ = CONFORMANCE._schema_registry()
    schema_set = copy.deepcopy(CONFORMANCE.load_source_json(CONFORMANCE.SCHEMA_SET_PATH))
    schema_set["schemas"][0]["name"] = "WrongModuleManifestV1"
    original_load_source_json = CONFORMANCE.load_source_json

    def load_source_json(path: Path, enforce_data_policy: bool = True) -> object:
        if path == CONFORMANCE.SCHEMA_SET_PATH:
            return schema_set
        return original_load_source_json(path, enforce_data_policy)

    monkeypatch.setattr(CONFORMANCE, "load_source_json", load_source_json)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^schema-set"):
        CONFORMANCE.validate_schema_set(schemas)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda schema_set: schema_set.__setitem__(
            "draft", "https://json-schema.org/draft/2019-09/schema"
        ),
        lambda schema_set: schema_set.__setitem__("unknown", True),
        lambda schema_set: schema_set["schemas"][0].__setitem__("unknown", True),
        lambda schema_set: schema_set["profiles"][0].__setitem__("unknown", True),
        lambda schema_set: schema_set["vectors"][0].__setitem__("unknown", True),
    ],
)
def test_schema_set_rejects_closed_registry_drift(
    monkeypatch: pytest.MonkeyPatch, mutate: Callable[[Any], None]
) -> None:
    schemas, _ = CONFORMANCE._schema_registry()
    schema_set = copy.deepcopy(CONFORMANCE.load_source_json(CONFORMANCE.SCHEMA_SET_PATH))
    mutate(schema_set)
    original_load_source_json = CONFORMANCE.load_source_json

    def load_source_json(path: Path, enforce_data_policy: bool = True) -> object:
        if path == CONFORMANCE.SCHEMA_SET_PATH:
            return schema_set
        return original_load_source_json(path, enforce_data_policy)

    monkeypatch.setattr(CONFORMANCE, "load_source_json", load_source_json)

    with pytest.raises(CONFORMANCE.ConformanceError, match=r"^schema-set"):
        CONFORMANCE.validate_schema_set(schemas)

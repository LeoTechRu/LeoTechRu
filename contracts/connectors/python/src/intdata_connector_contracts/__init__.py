"""Public, release-neutral connector contract carrier."""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
import hashlib
from importlib import resources
import json
from typing import Any, Final

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import best_match


__version__ = "0.1.0"
CONTRACT_VERSION: Final = "connectors-experimental-v0"
SOURCE_COMMIT: Final = "1101cdfb743e5819f07b5b0b2b042f5a4aea6aa4"
SOURCE_ROOT_TREE: Final = "87efdc5d8aa3b877c7242a1e40f895688da2fab6"
SOURCE_SUBTREE_TREE: Final = "9da7afaacc8068c9d90baec85ffd08983af70461"
SCHEMA_SIZE: Final = 20_048
SCHEMA_SHA256: Final = "dbdcfad02126360ae50fee98c64bdcb3d2e6a8d91373a6f7e239da5664a79e90"
REFERENCE_SIZE: Final = 15_143
REFERENCE_SHA256: Final = "ba37a5a7ad9c0aacc9a6c5ff7a15d8df645bff8b0b75a4d2e896b44da6dc2f12"

_REASON_CODES = frozenset(
    {
        "invalid_document",
        "schema_violation",
        "canonicalization_error",
        "contract_resource_error",
    }
)


def _pointer(path: tuple[str | int, ...]) -> str:
    if not path:
        return ""
    return "/" + "/".join(
        str(segment).replace("~", "~0").replace("/", "~1") for segment in path
    )


class ContractValidationError(ValueError):
    """Closed validation failure without document values or validator messages."""

    __slots__ = ("reason_code", "path")

    def __init__(
        self, reason_code: str, path: tuple[str | int, ...] = ()
    ) -> None:
        if reason_code not in _REASON_CODES:
            raise ValueError("unknown contract validation reason")
        self.reason_code = reason_code
        self.path = tuple(path)
        super().__init__(self._public_message())

    @property
    def json_pointer(self) -> str:
        return _pointer(self.path)

    def _public_message(self) -> str:
        pointer = self.json_pointer
        return self.reason_code if not pointer else f"{self.reason_code} at {pointer}"

    def __str__(self) -> str:
        return self._public_message()

    def __repr__(self) -> str:
        return f"ContractValidationError({self._public_message()!r})"


def _resource_bytes(name: str, size: int, digest: str) -> bytes:
    try:
        value = (
            resources.files("intdata_connector_contracts") / "_resources" / name
        ).read_bytes()
    except (FileNotFoundError, OSError) as error:
        raise ContractValidationError("contract_resource_error") from error
    if len(value) != size or hashlib.sha256(value).hexdigest() != digest:
        raise ContractValidationError("contract_resource_error")
    return value


def schema_bytes() -> bytes:
    return _resource_bytes("schema.json", SCHEMA_SIZE, SCHEMA_SHA256)


def reference_bytes() -> bytes:
    return _resource_bytes("reference.py.txt", REFERENCE_SIZE, REFERENCE_SHA256)


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    try:
        schema = json.loads(schema_bytes())
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, format_checker=FormatChecker())
    except ContractValidationError:
        raise
    except Exception as error:
        raise ContractValidationError("contract_resource_error") from error


def _error_key(error: Any) -> tuple[bytes, bytes, bytes]:
    path = tuple(error.absolute_path)
    schema_path = "/".join(str(segment) for segment in error.absolute_schema_path)
    return (
        _pointer(path).encode("utf-8"),
        str(error.validator).encode("utf-8"),
        schema_path.encode("utf-8"),
    )


def _actionable_error(error: Any) -> Any:
    if error.validator not in {"oneOf", "anyOf"} or not error.context:
        return error
    branches: dict[object, list[Any]] = {}
    for child in error.context:
        relative_schema_path = tuple(child.relative_schema_path)
        branch = relative_schema_path[0] if relative_schema_path else None
        branches.setdefault(branch, []).append(child)
    candidates = min(
        branches.values(),
        key=lambda branch_errors: (
            len(branch_errors),
            tuple(_error_key(item) for item in sorted(branch_errors, key=_error_key)),
        ),
    )
    selected = best_match(sorted(candidates, key=_error_key))
    return _actionable_error(selected) if selected is not None else error


def validate_document(document: Mapping[str, object]) -> None:
    if not isinstance(document, Mapping):
        raise ContractValidationError("invalid_document")
    errors = sorted(_validator().iter_errors(dict(document)), key=_error_key)
    if errors:
        selected = best_match(errors)
        if selected is None:
            raise ContractValidationError("schema_violation")
        selected = _actionable_error(selected)
        raise ContractValidationError(
            "schema_violation", tuple(selected.absolute_path)
        )


def _json_value(value: Any, path: tuple[str | int, ...]) -> Any:
    if value is None or type(value) in (bool, int, str):
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise ContractValidationError("canonicalization_error", path)
        return {
            key: _json_value(value[key], path + (key,))
            for key in sorted(value, key=lambda item: item.encode("utf-8"))
        }
    if isinstance(value, (list, tuple)):
        return [_json_value(item, path + (index,)) for index, item in enumerate(value)]
    raise ContractValidationError("canonicalization_error", path)


def canonical_json(document: Mapping[str, object]) -> bytes:
    if not isinstance(document, Mapping):
        raise ContractValidationError("invalid_document")
    normalized = _json_value(document, ())
    validate_document(normalized)
    try:
        return json.dumps(
            normalized,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise ContractValidationError("canonicalization_error") from error


def canonical_sha256(document: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_json(document)).hexdigest()


__all__ = [
    "CONTRACT_VERSION",
    "ContractValidationError",
    "REFERENCE_SHA256",
    "REFERENCE_SIZE",
    "SCHEMA_SHA256",
    "SCHEMA_SIZE",
    "SOURCE_COMMIT",
    "SOURCE_ROOT_TREE",
    "SOURCE_SUBTREE_TREE",
    "__version__",
    "canonical_json",
    "canonical_sha256",
    "reference_bytes",
    "schema_bytes",
    "validate_document",
]

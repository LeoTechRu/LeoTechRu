"""Strict JSON input and RFC 8785 canonicalization."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

import rfc8785

MAX_SAFE_INTEGER = 9_007_199_254_740_991
_BOM = b"\xef\xbb\xbf"
_JSON_WHITESPACE = " \t\r\n"


class StrictJSONError(ValueError):
    """Raised when bytes are not an accepted strict JSON document."""


def _reject_float(token: str) -> None:
    raise StrictJSONError(f"floating-point number is forbidden: {token}")


def _reject_constant(token: str) -> None:
    raise StrictJSONError(f"non-JSON numeric constant is forbidden: {token}")


def _parse_int(token: str) -> int:
    if token == "-0":
        raise StrictJSONError("negative zero is forbidden")
    value = int(token)
    if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
        raise StrictJSONError(f"integer is outside the safe range: {token}")
    return value


def _object_from_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJSONError(f"duplicate object key: {key!r}")
        result[key] = value
    return result


def _validate_value(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise StrictJSONError(f"integer at {path} is outside the safe range")
        return
    if isinstance(value, float):
        raise StrictJSONError(f"floating-point value at {path} is forbidden")
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise StrictJSONError(f"lone surrogate at {path} is forbidden")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise StrictJSONError(f"non-string object key at {path} is forbidden")
            _validate_value(key, f"{path}.<key>")
            _validate_value(child, f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        for index, child in enumerate(value):
            _validate_value(child, f"{path}[{index}]")
        return
    raise StrictJSONError(f"value at {path} is not representable in JSON")


def strict_loads(raw: bytes, *, allow_outer_whitespace: bool = False) -> Any:
    """Parse UTF-8 JSON while rejecting ambiguous or non-canonical primitives.

    ``allow_outer_whitespace`` exists only for tracked schema source files, which
    are pretty-printed with a final LF. Contract inputs must use the default.
    """

    if not isinstance(raw, bytes):
        raise TypeError("strict_loads expects bytes")
    if not raw:
        raise StrictJSONError("empty input is not JSON")
    if raw.startswith(_BOM):
        raise StrictJSONError("UTF-8 BOM is forbidden")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise StrictJSONError(f"input is not valid UTF-8 at byte {error.start}") from error

    if allow_outer_whitespace:
        text = text.strip(_JSON_WHITESPACE)
        if not text:
            raise StrictJSONError("input contains only whitespace")
    elif text[0] in _JSON_WHITESPACE or text[-1] in _JSON_WHITESPACE:
        raise StrictJSONError("leading or trailing JSON whitespace is forbidden")

    decoder = json.JSONDecoder(
        object_pairs_hook=_object_from_pairs,
        parse_float=_reject_float,
        parse_int=_parse_int,
        parse_constant=_reject_constant,
        strict=True,
    )
    try:
        value, end = decoder.raw_decode(text)
    except StrictJSONError:
        raise
    except json.JSONDecodeError as error:
        raise StrictJSONError(
            f"invalid JSON at character {error.pos}: {error.msg}"
        ) from error
    if end != len(text):
        raise StrictJSONError(f"trailing bytes after JSON value at character {end}")
    _validate_value(value)
    return value


def canonicalize(value: Any) -> bytes:
    """Return RFC 8785 JCS bytes with no trailing newline."""

    _validate_value(value)
    try:
        canonical = rfc8785.dumps(value)
    except rfc8785.CanonicalizationError as error:
        raise StrictJSONError(f"RFC 8785 canonicalization failed: {error}") from error
    if canonical.endswith(b"\n"):
        raise AssertionError("rfc8785 unexpectedly emitted a trailing newline")
    return canonical


def canonical_sha256(value: Any) -> str:
    """Return the lowercase SHA-256 of RFC 8785 canonical bytes."""

    return hashlib.sha256(canonicalize(value)).hexdigest()


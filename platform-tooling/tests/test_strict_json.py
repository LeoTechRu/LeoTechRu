import pytest

from intdata_tooling import MAX_SAFE_INTEGER, strict_loads
from intdata_tooling._json import StrictJSONError


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b" {}",
        b"{} ",
        b"{}\n",
        b"\xef\xbb\xbf{}",
        b'{"a":1,"a":2}',
        b'{"\\u0061":1,"a":2}',
        b"{}{}",
        b"{}\x00",
        b"\x80",
        b'"\xed\xa0\x80"',
        b'"\\ud800"',
        b'"\\udfff"',
        b"1.0",
        b"1e0",
        b"1E+2",
        b"-0",
        b"-0.0",
        b"NaN",
        b"Infinity",
        str(MAX_SAFE_INTEGER + 1).encode(),
        str(-MAX_SAFE_INTEGER - 1).encode(),
    ],
)
def test_strict_parser_rejects_ambiguous_or_unsafe_input(raw: bytes) -> None:
    with pytest.raises(StrictJSONError):
        strict_loads(raw)


def test_safe_integer_boundaries_are_accepted() -> None:
    raw = f'{{"max":{MAX_SAFE_INTEGER},"min":{-MAX_SAFE_INTEGER}}}'.encode()
    assert strict_loads(raw) == {"max": MAX_SAFE_INTEGER, "min": -MAX_SAFE_INTEGER}


def test_tracked_schema_source_may_have_outer_json_whitespace() -> None:
    assert strict_loads(b'\n {"schema":true}\n', allow_outer_whitespace=True) == {
        "schema": True
    }


def test_parser_requires_bytes() -> None:
    with pytest.raises(TypeError):
        strict_loads("{}")  # type: ignore[arg-type]


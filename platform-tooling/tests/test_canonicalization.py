import hashlib
import importlib.metadata
import platform

import pytest

from intdata_tooling import canonical_sha256, canonicalize, strict_loads


@pytest.mark.parametrize("reported_platform", ["Windows", "Linux"])
def test_utf16_non_bmp_key_order_is_an_independent_exact_vector(
    monkeypatch: pytest.MonkeyPatch, reported_platform: str
) -> None:
    monkeypatch.setattr(platform, "system", lambda: reported_platform)
    value = strict_loads('{"\ue000":1,"𐀀":2}'.encode("utf-8"))
    expected = b'{"\xf0\x90\x80\x80":2,"\xee\x80\x80":1}'
    assert canonicalize(value) == expected
    assert canonical_sha256(value) == hashlib.sha256(expected).hexdigest()


@pytest.mark.parametrize("reported_platform", ["Windows", "Linux"])
def test_safe_integer_vector_has_identical_bytes_without_newline(
    monkeypatch: pytest.MonkeyPatch, reported_platform: str
) -> None:
    monkeypatch.setattr(platform, "system", lambda: reported_platform)
    raw = b'{"min":-9007199254740991,"max":9007199254740991}'
    expected = b'{"max":9007199254740991,"min":-9007199254740991}'
    assert canonicalize(strict_loads(raw)) == expected
    assert not expected.endswith(b"\n")


def test_rfc8785_dependency_is_the_reviewed_version() -> None:
    assert importlib.metadata.version("rfc8785") == "0.1.4"


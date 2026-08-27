from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("validate-terminal-dependencies.py")
SPEC = importlib.util.spec_from_file_location("terminal_dependencies", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
CONFORMANCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONFORMANCE)


def test_uri_format_is_fail_closed_without_optional_jsonschema_formats() -> None:
    for value in (
        "https://bridge.intdata.pro\\v1",
        "https://bridge.intdata.pro/v1 ",
        "https://bridge.intdata.pro/v1\x01",
        "https://bridge.intdata.pro/vé",
        "https://bridge.intdata.pro/v%",
        "https://bridge.intdata.pro/v1|",
    ):
        assert CONFORMANCE.is_rfc3986_uri(value) is False


def test_uri_format_leaves_canonical_profile_rules_to_semantic_validation() -> None:
    assert CONFORMANCE.is_rfc3986_uri("https://api.intdata.pro") is True
    assert CONFORMANCE.is_rfc3986_uri("https://bridge.intdata.pro/v%2f") is True


def test_platform_assertion_vectors_pass_with_pinned_dependencies() -> None:
    assert CONFORMANCE.validate_ppa() == 106

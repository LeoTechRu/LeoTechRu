#!/usr/bin/env python3
"""Focused offline validator for the #889 terminal PPA and Bridge URI artifacts."""

from __future__ import annotations

import argparse
import copy
import hashlib
import ipaddress
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "platform-product-assertion.schema.json"
PPA_VECTORS_PATH = ROOT / "conformance" / "platform-product-assertion-v1.vectors.json"
PPA_DIGEST_PATH = ROOT / "conformance" / "platform-product-assertion-v1.digests.json"
URI_PROFILE_PATH = ROOT / "conformance" / "bridge-oauth-registration-uri-v1.profile.json"
URI_VECTORS_PATH = ROOT / "conformance" / "bridge-oauth-registration-uri-v1.vectors.json"
DIGEST_PATH = ROOT / "conformance" / "terminal-dependency-digests.json"
SAFE_INTEGER = 9007199254740991
URI_PROFILE_ID = "bridge-oauth-registration-uri/v1"
PPA_SCHEMA_ID = "urn:intdata:schema:platform-product-assertion:v1"
PPA_VECTOR_ID = "urn:intdata:conformance:platform-product-assertion:v1"
HOSTED_ISSUER = "https://api.intdata.pro/functions/v1/platform-identity"
PPA_DIGEST_ID = "urn:intdata:conformance:platform-product-assertion:v1:digests"
AGGREGATE_ENCODING = "For each artifact in listed path order: lowercase SHA-256, two ASCII spaces, path, LF; SHA-256 the concatenated UTF-8 bytes."


class ConformanceError(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


def require_keys(value: Any, keys: set[str], where: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ConformanceError("closed-shape", where)


def load_json_bytes(raw: bytes, source: str) -> Any:
    if raw.startswith(b"\xef\xbb\xbf") or not raw.endswith(b"\n") or b"\r\n" in raw:
        raise ConformanceError("source-encoding", source)

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in items:
            if key in result:
                raise ConformanceError("duplicate-key", key)
            result[key] = item
        return result

    try:
        return json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConformanceError("source-json", source) from error


def load_json(path: Path) -> Any:
    return load_json_bytes(path.read_bytes(), path.as_posix())


def assert_number_policy(value: Any) -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, int):
        if abs(value) > SAFE_INTEGER:
            raise ConformanceError("integer-policy")
        return
    if isinstance(value, float):
        raise ConformanceError("number-policy")
    if isinstance(value, list):
        for item in value:
            assert_number_policy(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if any(0xD800 <= ord(char) <= 0xDFFF for char in key):
                raise ConformanceError("unicode-policy")
            assert_number_policy(item)
        return
    raise ConformanceError("json-type")


def jcs(value: Any) -> bytes:
    assert_number_policy(value)
    if value is None:
        return b"null"
    if value is True:
        return b"true"
    if value is False:
        return b"false"
    if isinstance(value, int):
        return str(value).encode("ascii")
    if isinstance(value, str):
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ConformanceError("unicode-policy")
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if isinstance(value, list):
        return b"[" + b",".join(jcs(item) for item in value) + b"]"
    if isinstance(value, dict):
        members = []
        for key in sorted(value, key=lambda item: item.encode("utf-16-be")):
            members.append(jcs(key) + b":" + jcs(value[key]))
        return b"{" + b",".join(members) + b"}"
    raise ConformanceError("canonicalization")


def apply_mutation(document: Any, mutation: dict[str, Any]) -> None:
    operation = mutation.get("op")
    expected_keys = {"op", "pointer"} if operation == "remove" else {"op", "pointer", "value"}
    require_keys(mutation, expected_keys, "mutation")
    if operation not in {"add", "replace", "remove"}:
        raise ConformanceError("mutation-op")
    tokens = [
        token.replace("~1", "/").replace("~0", "~")
        for token in mutation["pointer"].split("/")[1:]
    ]
    target = document
    for token in tokens[:-1]:
        target = target[int(token)] if isinstance(target, list) else target[token]
    last = tokens[-1]
    if operation == "remove":
        if isinstance(target, list):
            del target[int(last)]
        else:
            del target[last]
    elif isinstance(target, list):
        target[int(last)] = mutation["value"]
    else:
        target[last] = mutation["value"]


def validate_header(header: Any, contract: dict[str, Any]) -> None:
    if not isinstance(header, dict) or set(header) != {"typ", "alg", "kid"}:
        raise ConformanceError("closed_header")
    if header["typ"] != contract["typ"]:
        raise ConformanceError("typ")
    if header["alg"] != contract["alg"]:
        raise ConformanceError("alg")
    if not isinstance(header["kid"], str) or not re.fullmatch(contract["kid_pattern"], header["kid"]):
        raise ConformanceError("kid")


def canonical_schema_reason(error: Any) -> str:
    tokens = [str(token).replace("~", "~0").replace("/", "~1") for token in error.absolute_path]
    pointer = "/" + "/".join(tokens) if tokens else "/"
    keyword = str(error.validator)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", keyword):
        raise ConformanceError("schema-keyword")
    return f"{pointer}#{keyword}"


def is_rfc3986_uri(value: object) -> bool:
    if not isinstance(value, str):
        return True
    try:
        raw = value.encode("ascii", "strict")
    except UnicodeEncodeError:
        return False
    if (
        not raw
        or any(byte <= 0x20 or byte == 0x7F for byte in raw)
        or b"\\" in raw
        or not re.fullmatch(r"[A-Za-z0-9:/?#\[\]@!$&'()*+,;=._~%-]+", value)
    ):
        return False
    return all(
        re.fullmatch(r"[0-9A-Fa-f]{2}", suffix[:2])
        for suffix in value.split("%")[1:]
    )


def validate_verifier(verifier: Any) -> None:
    require_keys(verifier, {"issuer", "audience", "product_id", "verifier_now", "clock_skew_seconds"}, "verifier")
    if not isinstance(verifier["issuer"], str) or not isinstance(verifier["audience"], str):
        raise ConformanceError("verifier_authority")
    if not isinstance(verifier["product_id"], str) or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", verifier["product_id"]):
        raise ConformanceError("verifier_product_id")
    try:
        canonical_ppa_resource_uri(verifier["issuer"])
        canonical_ppa_resource_uri(verifier["audience"])
    except ConformanceError as error:
        raise ConformanceError("verifier_authority") from error
    now = verifier["verifier_now"]
    if isinstance(now, bool) or not isinstance(now, int) or not 0 <= now <= SAFE_INTEGER:
        raise ConformanceError("verifier_now")
    skew = verifier["clock_skew_seconds"]
    if isinstance(skew, bool) or not isinstance(skew, int) or not 0 <= skew <= 30:
        raise ConformanceError("clock_skew_seconds")


def validate_ppa_semantics(claims: dict[str, Any], verifier: dict[str, Any]) -> None:
    validate_verifier(verifier)
    canonical_ppa_resource_uri(claims["iss"])
    canonical_ppa_resource_uri(claims["aud"])
    if claims["iss"] != HOSTED_ISSUER:
        raise ConformanceError("issuer")
    if claims["product_id"] != verifier["product_id"]:
        raise ConformanceError("product_id")
    expected_audiences = {f"https://{verifier['product_id']}.intdata.pro/v1", f"https://{verifier['product_id']}.intdata.pro/mcp"}
    if verifier["issuer"] != HOSTED_ISSUER or verifier["audience"] not in expected_audiences or claims["aud"] != verifier["audience"]:
        raise ConformanceError("audience")
    if claims["iss"] != verifier["issuer"]:
        raise ConformanceError("issuer")
    if claims["aud"] != verifier["audience"]:
        raise ConformanceError("audience")
    if claims["scopes"] != sorted(set(claims["scopes"]), key=lambda item: item.encode("utf-8")):
        raise ConformanceError("scope_order")
    skew = verifier["clock_skew_seconds"]
    now = verifier["verifier_now"]
    iat, nbf, exp = claims["iat"], claims["nbf"], claims["exp"]
    if not iat - skew <= nbf <= iat + skew:
        raise ConformanceError("iat_nbf_skew")
    if exp <= max(iat, nbf):
        raise ConformanceError("chronology")
    if exp > iat + 60:
        raise ConformanceError("ttl")
    if iat > now + skew:
        raise ConformanceError("future_iat")
    if nbf > now + skew:
        raise ConformanceError("future_nbf")
    if exp <= now - skew:
        raise ConformanceError("expired")


def evaluate_ppa_adverse(
    document: dict[str, Any],
    verifier_context: dict[str, Any],
    validator: Draft202012Validator,
    header_contract: dict[str, Any],
) -> tuple[str, str]:
    try:
        assert_number_policy(document)
    except ConformanceError as error:
        return error.reason, error.reason
    try:
        validate_header(document["protected_header"], header_contract)
    except ConformanceError as error:
        return "header", error.reason
    schema_errors = sorted(validator.iter_errors(document), key=lambda error: (canonical_schema_reason(error), str(error.message)))
    if schema_errors:
        return "schema", canonical_schema_reason(schema_errors[0])
    try:
        validate_ppa_semantics(document["claims"], verifier_context)
    except ConformanceError as error:
        return "semantic", error.reason
    return "accepted", "accepted"


def validate_ppa() -> int:
    schema = load_json(SCHEMA_PATH)
    require_keys(schema, {"$schema", "$id", "title", "$comment", "type", "additionalProperties", "required", "properties", "$defs"}, "ppa-schema")
    if schema["$id"] != PPA_SCHEMA_ID:
        raise ConformanceError("schema-id")
    Draft202012Validator.check_schema(schema)
    format_checker = FormatChecker()
    format_checker.checks("uri")(is_rfc3986_uri)
    validator = Draft202012Validator(schema, format_checker=format_checker)
    vectors = load_json(PPA_VECTORS_PATH)
    require_keys(vectors, {"vector_set_id", "version", "schema_id", "protected_header_contract", "base", "positive_cases", "adverse_cases", "raw_json_cases"}, "ppa-vectors")
    if vectors["vector_set_id"] != PPA_VECTOR_ID or vectors["version"] != "v1" or vectors["schema_id"] != PPA_SCHEMA_ID:
        raise ConformanceError("vector-identity")
    contract = vectors["protected_header_contract"]
    require_keys(contract, {"typ", "alg", "kid_pattern"}, "header-contract")
    base = vectors["base"]
    require_keys(base, {"schema_version", "protected_header", "claims", "canonical_claims_utf8_hex", "canonical_claims_sha256"}, "ppa-base")
    if base["schema_version"] != "PlatformProductAssertionV1":
        raise ConformanceError("schema-version")
    canonical = jcs(base["claims"])
    if canonical.hex() != base["canonical_claims_utf8_hex"] or hashlib.sha256(canonical).hexdigest() != base["canonical_claims_sha256"]:
        raise ConformanceError("ppa-jcs")
    if not isinstance(vectors["positive_cases"], list) or len(vectors["positive_cases"]) != 17:
        raise ConformanceError("positive-count")
    if not isinstance(vectors["adverse_cases"], list) or len(vectors["adverse_cases"]) != 87:
        raise ConformanceError("adverse-count")
    case_names = [case.get("name") for case in vectors["positive_cases"] + vectors["adverse_cases"] if isinstance(case, dict)]
    if len(case_names) != 104 or any(not isinstance(name, str) or not name for name in case_names) or len(set(case_names)) != len(case_names):
        raise ConformanceError("case-names")
    checked = 0
    for positive in vectors["positive_cases"]:
        require_keys(positive, {"name", "mutations", "verifier", "expected"}, "positive-case")
        require_keys(positive["expected"], {"valid", "canonical_claims_utf8_hex", "canonical_claims_sha256"}, "positive-expected")
        if positive["expected"]["valid"] is not True:
            raise ConformanceError("positive-expected")
        document = copy.deepcopy({"schema_version": base["schema_version"], "protected_header": base["protected_header"], "claims": base["claims"]})
        for mutation in positive["mutations"]:
            apply_mutation(document, mutation)
        assert_number_policy(document)
        validate_header(document["protected_header"], contract)
        errors = list(validator.iter_errors(document))
        if errors:
            raise ConformanceError("positive-schema", positive["name"])
        validate_ppa_semantics(document["claims"], positive["verifier"])
        positive_jcs = jcs(document["claims"])
        if positive_jcs.hex() != positive["expected"]["canonical_claims_utf8_hex"] or hashlib.sha256(positive_jcs).hexdigest() != positive["expected"]["canonical_claims_sha256"]:
            raise ConformanceError("positive-jcs", positive["name"])
        checked += 1
    for adverse in vectors["adverse_cases"]:
        require_keys(adverse, {"name", "mutations", "verifier", "expected"}, "adverse-case")
        require_keys(adverse["expected"], {"valid", "stage", "reason"}, "adverse-expected")
        if adverse["expected"]["valid"] is not False:
            raise ConformanceError("adverse-expected-valid", adverse["name"])
        document = copy.deepcopy({"schema_version": base["schema_version"], "protected_header": base["protected_header"], "claims": base["claims"]})
        for mutation in adverse["mutations"]:
            apply_mutation(document, mutation)
        expected = adverse["expected"]
        failed_stage, failed_reason = evaluate_ppa_adverse(document, adverse["verifier"], validator, contract)
        if failed_stage != expected["stage"] or failed_reason != expected["reason"]:
            raise ConformanceError("adverse-case", f"{adverse['name']} got {failed_stage}/{failed_reason}")
        checked += 1
    raw_cases = vectors["raw_json_cases"]
    if not isinstance(raw_cases, list) or len(raw_cases) != 5:
        raise ConformanceError("raw-json-count")
    raw_names = [case.get("name") for case in raw_cases if isinstance(case, dict)]
    if len(raw_names) != 5 or any(not isinstance(name, str) or not name for name in raw_names) or len(set(raw_names)) != 5:
        raise ConformanceError("raw-json-names")
    for raw_case in raw_cases:
        require_keys(raw_case, {"name", "raw_utf8_hex", "expected"}, "raw-json-case")
        require_keys(raw_case["expected"], {"ok", "reason"}, "raw-json-expected")
        if raw_case["expected"]["ok"] is not False or not re.fullmatch(r"[0-9a-f]*", raw_case["raw_utf8_hex"]):
            raise ConformanceError("raw-json-expected")
        try:
            load_json_bytes(bytes.fromhex(raw_case["raw_utf8_hex"]), raw_case["name"])
        except ConformanceError as error:
            if error.reason != raw_case["expected"]["reason"]:
                raise ConformanceError("raw-json-case", raw_case["name"]) from error
        else:
            raise ConformanceError("raw-json-case", raw_case["name"])
        checked += 1
    oracle_document = copy.deepcopy({"schema_version": base["schema_version"], "protected_header": base["protected_header"], "claims": base["claims"]})
    oracle_document["claims"]["__oracle_extra_claim"] = True
    oracle_stage, oracle_reason = evaluate_ppa_adverse(
        oracle_document,
        vectors["positive_cases"][0]["verifier"],
        validator,
        contract,
    )
    if (oracle_stage, oracle_reason) != ("schema", "/claims#additionalProperties"):
        raise ConformanceError("adverse-oracle", f"{oracle_stage}/{oracle_reason}")
    verifier_policy_cases = [
        ({"issuer": HOSTED_ISSUER, "audience": "https://bridge.intdata.pro/v1", "product_id": "Bridge", "verifier_now": 0, "clock_skew_seconds": 30}, "verifier_product_id"),
        ({"issuer": HOSTED_ISSUER, "audience": "https://bridge.intdata.pro/v1", "product_id": "bridge", "verifier_now": 0, "clock_skew_seconds": 30, "extra": True}, "closed-shape"),
        ({"issuer": "https://api.intdata.pro/functions/v1/platform-identity", "audience": "https://bridge.intdata.pro/v1", "product_id": "bridge", "verifier_now": True, "clock_skew_seconds": 30}, "verifier_now"),
        ({"issuer": "https://api.intdata.pro/functions/v1/platform-identity", "audience": "https://bridge.intdata.pro/v1", "product_id": "bridge", "verifier_now": 1.5, "clock_skew_seconds": 30}, "verifier_now"),
        ({"issuer": "https://api.intdata.pro/functions/v1/platform-identity", "audience": "https://bridge.intdata.pro/v1", "product_id": "bridge", "verifier_now": -1, "clock_skew_seconds": 30}, "verifier_now"),
        ({"issuer": "https://api.intdata.pro/functions/v1/platform-identity", "audience": "https://bridge.intdata.pro/v1", "product_id": "bridge", "verifier_now": SAFE_INTEGER + 1, "clock_skew_seconds": 30}, "verifier_now"),
        ({"issuer": "https://api.intdata.pro/functions/v1/platform-identity", "audience": "https://bridge.intdata.pro/v1", "product_id": "bridge", "verifier_now": 0, "clock_skew_seconds": True}, "clock_skew_seconds"),
        ({"issuer": "https://api.intdata.pro/functions/v1/platform-identity", "audience": "https://bridge.intdata.pro/v1", "product_id": "bridge", "verifier_now": 0, "clock_skew_seconds": 1.5}, "clock_skew_seconds"),
        ({"issuer": "https://api.intdata.pro/functions/v1/platform-identity", "audience": "https://bridge.intdata.pro/v1", "product_id": "bridge", "verifier_now": 0, "clock_skew_seconds": -1}, "clock_skew_seconds"),
        ({"issuer": "https://api.intdata.pro/functions/v1/platform-identity", "audience": "https://bridge.intdata.pro/v1", "product_id": "bridge", "verifier_now": 0, "clock_skew_seconds": 31}, "clock_skew_seconds"),
    ]
    for verifier, reason in verifier_policy_cases:
        try:
            validate_verifier(verifier)
        except ConformanceError as error:
            if error.reason != reason:
                raise ConformanceError("verifier-policy", reason) from error
        else:
            raise ConformanceError("verifier-policy", reason)
    return checked


def parse_port(text: str | None, scheme: str) -> int | None:
    if text is None:
        return None
    if not re.fullmatch(r"[1-9][0-9]{0,4}", text):
        raise ConformanceError("invalid_port")
    port = int(text)
    if port > 65535:
        raise ConformanceError("invalid_port")
    if (scheme == "https" and port == 443) or (scheme == "http" and port == 80):
        raise ConformanceError("default_port_forbidden")
    return port


def canonical_host(authority: str, scheme: str) -> tuple[str, int | None, bool]:
    if "@" in authority:
        raise ConformanceError("userinfo_forbidden")
    port_text: str | None = None
    if authority.startswith("["):
        end = authority.find("]")
        if end < 0:
            raise ConformanceError("invalid_host")
        host_text, suffix = authority[1:end], authority[end + 1 :]
        if suffix:
            if not suffix.startswith(":"):
                raise ConformanceError("invalid_authority")
            port_text = suffix[1:]
        try:
            address = ipaddress.IPv6Address(host_text)
        except ipaddress.AddressValueError as error:
            raise ConformanceError("invalid_host") from error
        canonical = address.compressed.lower()
        if host_text != canonical:
            raise ConformanceError("noncanonical_ip")
        return f"[{canonical}]", parse_port(port_text, scheme), address == ipaddress.IPv6Address("::1"), True
    if authority.count(":") > 1:
        raise ConformanceError("invalid_host")
    host_text, separator, port_text_value = authority.rpartition(":")
    if separator:
        port_text = port_text_value
    else:
        host_text = authority
    if not host_text or host_text.endswith("."):
        raise ConformanceError("invalid_host")
    loopback = False
    is_ip = False
    if re.fullmatch(r"[0-9.]+", host_text):
        try:
            address4 = ipaddress.IPv4Address(host_text)
        except ipaddress.AddressValueError as error:
            raise ConformanceError("invalid_host") from error
        host = str(address4)
        if host_text != host:
            raise ConformanceError("noncanonical_ip")
        loopback = address4 == ipaddress.IPv4Address("127.0.0.1")
        is_ip = True
    else:
        labels = host_text.split(".")
        if any(not label or len(label) > 63 or not re.fullmatch(r"[a-z0-9-]+", label) or label.startswith("-") or label.endswith("-") for label in labels):
            raise ConformanceError("invalid_host")
        host = host_text
    return host, parse_port(port_text, scheme), loopback, is_ip


UNRESERVED = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


def normalize_component(component: str) -> str:
    output: list[str] = []
    decoded = bytearray()
    index = 0
    while index < len(component):
        char = component[index]
        code = ord(char)
        if code > 0x7F:
            raise ConformanceError("ascii_required")
        if char == "%":
            if index + 2 >= len(component) or not re.fullmatch(r"[0-9A-Fa-f]{2}", component[index + 1 : index + 3]):
                raise ConformanceError("invalid_percent_encoding")
            escape = component[index + 1 : index + 3]
            if escape != escape.upper():
                raise ConformanceError("lowercase_percent_encoding")
            byte = int(escape, 16)
            if byte in UNRESERVED or byte in {0x2F, 0x5C} or byte <= 0x20 or byte == 0x7F:
                raise ConformanceError("encoded_byte_forbidden")
            decoded.append(byte)
            output.append(f"%{byte:02X}")
            index += 3
            continue
        decoded.append(code)
        output.append(char)
        index += 1
    try:
        decoded_text = decoded.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise ConformanceError("invalid_utf8") from error
    if any(unicodedata.category(char) in {"Cc", "Cf", "Zs", "Zl", "Zp"} for char in decoded_text):
        raise ConformanceError("unicode_category_forbidden")
    return "".join(output)


def normalize_uri(value: str, admit_nondefault_port: bool = False, reparse: bool = True) -> str:
    try:
        raw = value.encode("ascii", "strict")
    except UnicodeEncodeError as error:
        raise ConformanceError("ascii_required") from error
    if not 1 <= len(raw) <= 2048:
        raise ConformanceError("length")
    if any(byte <= 0x20 or byte == 0x7F for byte in raw) or b"\\" in raw:
        raise ConformanceError("forbidden_character")
    if "#" in value:
        raise ConformanceError("fragment_forbidden")
    match = re.fullmatch(r"(https|http)://([^/?#]+)(/[^?#]*)?(\?[^#]*)?", value)
    if not match:
        raise ConformanceError("invalid_scheme")
    scheme, authority, path, query_part = match.groups()
    host, port, loopback, _ = canonical_host(authority, scheme)
    if scheme == "http" and not loopback:
        raise ConformanceError("invalid_scheme")
    if scheme == "http" and port is None:
        raise ConformanceError("loopback_port_required")
    if port is not None and not loopback and not admit_nondefault_port:
        raise ConformanceError("policy_admission_required")
    path = path or "/"
    if "//" in path:
        raise ConformanceError("path_normalization_forbidden")
    for segment in path.split("/"):
        if re.sub(r"(?i:%2e)", ".", segment) in {".", ".."}:
            raise ConformanceError("path_normalization_forbidden")
    normalized_path = normalize_component(path)
    normalized_query = ""
    if query_part is not None:
        query = query_part[1:]
        if not query:
            raise ConformanceError("empty_query")
        normalized_query = "?" + normalize_component(query)
    result = f"{scheme}://{host}{f':{port}' if port is not None else ''}{normalized_path}{normalized_query}"
    if reparse and normalize_uri(result, admit_nondefault_port, False) != result:
        raise ConformanceError("non_idempotent_output")
    return result



def canonical_ppa_resource_uri(value: str) -> str:
    try:
        raw = value.encode("ascii", "strict")
    except UnicodeEncodeError as error:
        raise ConformanceError("ppa_uri") from error
    if not 1 <= len(raw) <= 2048 or any(byte <= 0x20 or byte == 0x7F for byte in raw) or b"\\" in raw:
        raise ConformanceError("ppa_uri")
    match = re.fullmatch(r"https://([^/?#]+)(/[^?#]+)", value)
    if not match:
        raise ConformanceError("ppa_uri")
    authority, path = match.groups()
    try:
        host, port, _, is_ip = canonical_host(authority, "https")
    except ConformanceError as error:
        raise ConformanceError("ppa_uri") from error
    if is_ip or port is not None or host != authority or "//" in path:
        raise ConformanceError("ppa_uri")
    for segment in path.split("/"):
        if not re.fullmatch(r"[A-Za-z0-9._~!$&\'()*+,;=:@%-]*", segment):
            raise ConformanceError("ppa_uri")
        if segment in {".", ".."} or re.sub(r"(?i:%2e)", ".", segment) in {".", ".."}:
            raise ConformanceError("ppa_uri")
    try:
        normalized = normalize_component(path)
    except ConformanceError as error:
        raise ConformanceError("ppa_uri") from error
    result = f"https://{host}{normalized}"
    if result != value:
        raise ConformanceError("ppa_uri")
    return result

def normalize_redirects(values: list[str], admit: bool) -> list[str]:
    inputs: dict[str, str] = {}
    for value in values:
        normalized = normalize_uri(value, admit)
        if normalized in inputs and inputs[normalized] != value:
            raise ConformanceError("normalized_collision")
        inputs[normalized] = value
    return sorted(inputs, key=lambda item: item.encode("utf-8"))


def normalize_tokens(kind: str, values: list[str]) -> list[str]:
    if kind == "grant_types":
        if any(value not in {"authorization_code", "client_credentials", "refresh_token"} for value in values):
            raise ConformanceError("token_grammar")
    elif kind == "scopes":
        if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value) for value in values):
            raise ConformanceError("token_grammar")
    else:
        raise ConformanceError("token_grammar")
    return sorted(set(values), key=lambda item: item.encode("utf-8"))


def validate_uri() -> int:
    profile = load_json(URI_PROFILE_PATH)
    require_keys(profile, {"profile_id", "version", "input", "scheme_and_authority", "path", "percent_encoding", "query", "output", "arrays"}, "uri-profile")
    require_keys(profile["input"], {"encoding", "min_bytes", "max_bytes", "reject"}, "uri-profile-input")
    require_keys(profile["scheme_and_authority"], {"https", "http", "dns", "ip", "port", "default_ports", "non_loopback_non_default_port"}, "uri-profile-authority")
    require_keys(profile["path"], {"empty_input_path", "output", "reject"}, "uri-profile-path")
    require_keys(profile["percent_encoding"], {"hex_output", "forbid_encoded", "utf8", "reserved"}, "uri-profile-percent")
    require_keys(profile["query"], {"order", "duplicates", "percent_rules", "empty_question_mark", "plus"}, "uri-profile-query")
    require_keys(profile["output"], {"form", "idempotence"}, "uri-profile-output")
    require_keys(profile["arrays"], {"redirect_uris", "grant_types", "scopes"}, "uri-profile-arrays")
    if profile["profile_id"] != URI_PROFILE_ID or profile["version"] != "v1":
        raise ConformanceError("uri-profile-id")
    vectors = load_json(URI_VECTORS_PATH)
    require_keys(vectors, {"vector_set_id", "version", "uri_cases", "redirect_array_cases", "token_array_cases"}, "uri-vectors")
    if vectors["vector_set_id"] != URI_PROFILE_ID or vectors["version"] != "v1":
        raise ConformanceError("uri-vector-id")
    groups = [vectors["uri_cases"], vectors["redirect_array_cases"], vectors["token_array_cases"]]
    if any(not isinstance(group, list) for group in groups):
        raise ConformanceError("uri-vector-groups")
    all_vectors = [vector for group in groups for vector in group]
    case_names = [vector.get("name") for vector in all_vectors if isinstance(vector, dict)]
    if len(all_vectors) != 35 or len(case_names) != 35 or any(not isinstance(name, str) or not name for name in case_names) or len(set(case_names)) != 35:
        raise ConformanceError("uri-vector-count-or-names")
    checked = 0
    for vector in vectors["uri_cases"]:
        require_keys(vector, {"name", "input", "admit_nondefault_port", "expected"}, "uri-case")
        expected = vector["expected"]
        require_keys(expected, {"ok", "normalized"} if expected.get("ok") else {"ok", "reason"}, "uri-expected")
        try:
            normalized = normalize_uri(vector["input"], vector["admit_nondefault_port"])
        except ConformanceError as error:
            if expected["ok"] or error.reason != expected["reason"]:
                raise ConformanceError("uri-case", vector["name"]) from error
        else:
            if not expected["ok"] or normalized != expected["normalized"]:
                raise ConformanceError("uri-case", vector["name"])
        checked += 1
    for vector in vectors["redirect_array_cases"]:
        require_keys(vector, {"name", "inputs", "admit_nondefault_port", "expected"}, "redirect-case")
        expected = vector["expected"]
        require_keys(expected, {"ok", "normalized"} if expected.get("ok") else {"ok", "reason"}, "redirect-expected")
        try:
            normalized = normalize_redirects(vector["inputs"], vector["admit_nondefault_port"])
        except ConformanceError as error:
            if expected["ok"] or error.reason != expected["reason"]:
                raise ConformanceError("redirect-case", vector["name"]) from error
        else:
            if not expected["ok"] or normalized != expected["normalized"]:
                raise ConformanceError("redirect-case", vector["name"])
        checked += 1
    for vector in vectors["token_array_cases"]:
        require_keys(vector, {"name", "kind", "inputs", "expected"}, "token-case")
        require_keys(vector["expected"], {"ok", "normalized"}, "token-expected")
        normalized = normalize_tokens(vector["kind"], vector["inputs"])
        if not vector["expected"]["ok"] or normalized != vector["expected"]["normalized"]:
            raise ConformanceError("token-case", vector["name"])
        checked += 1
    return checked


def validate_ppa_digests() -> int:
    manifest = load_json(PPA_DIGEST_PATH)
    require_keys(manifest, {"digest_set_id", "digest_set_version", "algorithm", "aggregate_encoding", "artifacts", "aggregate_manifest_utf8_hex", "aggregate_sha256"}, "ppa-digest-manifest")
    if manifest["digest_set_id"] != PPA_DIGEST_ID or manifest["digest_set_version"] != "1.0.0" or manifest["algorithm"] != "sha256" or manifest["aggregate_encoding"] != AGGREGATE_ENCODING:
        raise ConformanceError("ppa-digest-metadata")
    entries = manifest["artifacts"]
    expected = [
        ("conformance/platform-product-assertion-v1.vectors.json", PPA_VECTOR_ID),
        ("schemas/platform-product-assertion.schema.json", PPA_SCHEMA_ID),
    ]
    if not isinstance(entries, list) or [(entry.get("path"), entry.get("id")) for entry in entries] != expected:
        raise ConformanceError("ppa-digest-paths")
    lines = []
    for entry in entries:
        require_keys(entry, {"path", "id", "sha256"}, "ppa-digest-entry")
        actual = hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest()
        if entry["sha256"] != actual:
            raise ConformanceError("ppa-digest-entry", entry["path"])
        lines.append(f"{actual}  {entry['path']}\n")
    aggregate = "".join(lines).encode("utf-8")
    if aggregate.hex() != manifest["aggregate_manifest_utf8_hex"] or hashlib.sha256(aggregate).hexdigest() != manifest["aggregate_sha256"]:
        raise ConformanceError("ppa-digest-aggregate")
    return len(entries)


def validate_digests() -> int:
    manifest = load_json(DIGEST_PATH)
    require_keys(manifest, {"digest_set_version", "algorithm", "aggregate_encoding", "artifacts", "aggregate_manifest_utf8_hex", "aggregate_sha256"}, "digest-manifest")
    if manifest["digest_set_version"] != "1.0.0" or manifest["algorithm"] != "sha256" or manifest["aggregate_encoding"] != AGGREGATE_ENCODING:
        raise ConformanceError("digest-metadata")
    entries = manifest["artifacts"]
    expected_paths = [
        "conformance/bridge-oauth-registration-uri-v1.profile.json",
        "conformance/bridge-oauth-registration-uri-v1.vectors.json",
        "conformance/platform-product-assertion-v1.vectors.json",
        "schemas/platform-product-assertion.schema.json",
    ]
    if not isinstance(entries, list) or [entry.get("path") for entry in entries] != expected_paths:
        raise ConformanceError("digest-paths")
    lines = []
    for entry in entries:
        require_keys(entry, {"path", "sha256"}, "digest-entry")
        actual = hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest()
        if entry["sha256"] != actual:
            raise ConformanceError("digest-entry", entry["path"])
        lines.append(f"{actual}  {entry['path']}\n")
    aggregate_bytes = "".join(lines).encode("utf-8")
    if aggregate_bytes.hex() != manifest["aggregate_manifest_utf8_hex"] or hashlib.sha256(aggregate_bytes).hexdigest() != manifest["aggregate_sha256"]:
        raise ConformanceError("digest-aggregate")
    return len(entries)


def run() -> dict[str, int]:
    return {
        "ppa_vectors": validate_ppa(),
        "uri_vectors": validate_uri(),
        "ppa_artifact_digests": validate_ppa_digests(),
        "terminal_artifact_digests": validate_digests(),
    }


def main() -> int:
    argparse.ArgumentParser().parse_args()
    print(json.dumps({"ok": True, "checked": run()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

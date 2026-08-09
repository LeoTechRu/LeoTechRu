from __future__ import annotations

import copy
import unittest

from jsonschema import ValidationError

from validate_provider_contract import (
    ContractError,
    canonical_sha256,
    load_fixture,
    validate_artifact_for_invocation,
    validate_document,
    validate_provider_pair,
)


class ProviderContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.codex = load_fixture("codex-descriptor.json")
        self.hermes = load_fixture("hermes-descriptor.json")
        self.invocation = load_fixture("codex-invocation.json")
        self.artifact = load_fixture("codex-artifact.json")

    def test_valid_fixtures_round_trip(self) -> None:
        for document in (self.codex, self.hermes, self.invocation, self.artifact):
            validate_document(document)
        validate_provider_pair(self.codex, self.invocation)
        validate_artifact_for_invocation(self.invocation, self.artifact)
        assert self.artifact["invocation_sha256"] == canonical_sha256(self.invocation)

    def test_contract_only_hermes_cannot_start(self) -> None:
        invocation = copy.deepcopy(self.invocation)
        invocation["provider_id"] = "hermes"
        with self.assertRaisesRegex(ContractError, "provider unavailable"):
            validate_provider_pair(self.hermes, invocation)
        forged = copy.deepcopy(self.hermes)
        forged.update(
            runtime_status="available",
            requires_external_sandbox=False,
            supported_modes=["disposable_coding"],
            verifier_profiles=["slugify-unittest"],
        )
        with self.assertRaises((ValidationError, ContractError)):
            validate_provider_pair(forged, invocation)

    def test_arbitrary_argv_env_and_command_are_rejected(self) -> None:
        for field, value in (("argv", ["sh"]), ("env", {"TOKEN": "x"}), ("command", "id")):
            invocation = copy.deepcopy(self.invocation)
            invocation[field] = value
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_document(invocation)

    def test_absolute_parent_and_windows_paths_are_rejected(self) -> None:
        for path in ("/etc/passwd", "../secret", "src/../../secret", "C:/Users/secret", "a\\b"):
            invocation = copy.deepcopy(self.invocation)
            invocation["allowed_paths"] = [path]
            with self.subTest(path=path), self.assertRaises(ValidationError):
                validate_document(invocation)

    def test_missing_runtime_pin_is_rejected(self) -> None:
        invocation = copy.deepcopy(self.invocation)
        del invocation["runtime_pin"]
        with self.assertRaises(ValidationError):
            validate_document(invocation)

    def test_provider_and_runtime_mismatch_are_rejected(self) -> None:
        invocation = copy.deepcopy(self.invocation)
        invocation["provider_id"] = "other"
        with self.assertRaisesRegex(ContractError, "provider mismatch"):
            validate_provider_pair(self.codex, invocation)
        artifact = copy.deepcopy(self.artifact)
        artifact["runtime"]["sha256"] = "9" * 64
        with self.assertRaisesRegex(ContractError, "runtime pin mismatch"):
            validate_artifact_for_invocation(self.invocation, artifact)
        artifact = copy.deepcopy(self.artifact)
        artifact["invocation_sha256"] = "f" * 64
        with self.assertRaisesRegex(ContractError, "invocation digest mismatch"):
            validate_artifact_for_invocation(self.invocation, artifact)

    def test_changed_path_and_patch_limits_are_enforced(self) -> None:
        artifact = copy.deepcopy(self.artifact)
        artifact["changed_paths"][0]["path"] = "test_slugify.py"
        with self.assertRaisesRegex(ContractError, "outside allowlist"):
            validate_artifact_for_invocation(self.invocation, artifact)
        artifact = copy.deepcopy(self.artifact)
        artifact["patch"]["size_bytes"] = self.invocation["limits"]["max_patch_bytes"] + 1
        with self.assertRaisesRegex(ContractError, "patch exceeds"):
            validate_artifact_for_invocation(self.invocation, artifact)

    def test_raw_output_and_credentials_are_not_artifact_fields(self) -> None:
        for field in ("prompt", "stdout", "stderr", "credentials", "absolute_path"):
            artifact = copy.deepcopy(self.artifact)
            artifact[field] = "secret"
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_document(artifact)

    def test_secret_like_metadata_and_control_values_are_rejected(self) -> None:
        for value in ("sk-abcdefghijklmnopqrstuvwx", "api_key-value", "bad\nversion"):
            artifact = copy.deepcopy(self.artifact)
            artifact["runtime"]["version"] = value
            with self.subTest(value=value), self.assertRaises((ValidationError, ContractError)):
                validate_document(artifact)

    def test_verifier_duplicates_and_event_order_fail_closed(self) -> None:
        artifact = copy.deepcopy(self.artifact)
        artifact["verifier"].update(passed=True, exit_code=1)
        with self.assertRaisesRegex(ContractError, "verifier result"):
            validate_artifact_for_invocation(self.invocation, artifact)
        artifact = copy.deepcopy(self.artifact)
        duplicate = copy.deepcopy(artifact["changed_paths"][0])
        duplicate["after_sha256"] = "a" * 64
        artifact["changed_paths"].append(duplicate)
        with self.assertRaisesRegex(ContractError, "duplicate changed path"):
            validate_artifact_for_invocation(self.invocation, artifact)
        artifact = copy.deepcopy(self.artifact)
        artifact["provider_events"][0]["sequence"] = 2
        with self.assertRaisesRegex(ContractError, "event sequence"):
            validate_artifact_for_invocation(self.invocation, artifact)
        artifact = copy.deepcopy(self.artifact)
        artifact["provider_output"]["event_count"] = 2
        with self.assertRaisesRegex(ContractError, "event count"):
            validate_artifact_for_invocation(self.invocation, artifact)
        artifact = copy.deepcopy(self.artifact)
        artifact["provider_events"][0]["size_bytes"] = 2048
        invocation = copy.deepcopy(self.invocation)
        invocation["limits"]["max_line_bytes"] = 1024
        artifact["invocation_sha256"] = canonical_sha256(invocation)
        with self.assertRaisesRegex(ContractError, "line limit"):
            validate_artifact_for_invocation(invocation, artifact)
        artifact = copy.deepcopy(self.artifact)
        artifact["provider_events"][0]["size_bytes"] = 127
        with self.assertRaisesRegex(ContractError, "contradict total"):
            validate_artifact_for_invocation(self.invocation, artifact)


if __name__ == "__main__":
    unittest.main()

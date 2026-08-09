from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from validate_contract import (
    CONTRACT_ROOT,
    ConformanceError,
    assert_redacted,
    load_json,
    run_fixture_suite,
    request_wire_digest,
    validate_artifact,
    validate_completed_response,
    validate_document,
    validate_event_sequence,
    validate_replay_receipt,
)


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        fixtures = CONTRACT_ROOT / "fixtures"
        self.request = load_json(fixtures / "request-start.json")
        self.event = load_json(fixtures / "event-terminal.json")
        self.receipt = load_json(fixtures / "receipt-terminal.json")

    def test_declared_fixtures(self) -> None:
        self.assertEqual(run_fixture_suite(), {"valid": 5, "invalid": 5})

    def test_schema_rejects_unknown_protocol_operation_bad_task_and_missing_fence(self) -> None:
        cases = []
        unknown_protocol = copy.deepcopy(self.request)
        unknown_protocol["protocol_version"] = "experimental-v99"
        cases.append(unknown_protocol)
        unknown_operation = copy.deepcopy(self.request)
        unknown_operation["operation"] = "execute-shell"
        cases.append(unknown_operation)
        bad_task = copy.deepcopy(self.request)
        del bad_task["task_ref"]["issue"]["digest"]
        cases.append(bad_task)
        missing_fence = copy.deepcopy(self.request)
        del missing_fence["fence_token"]
        cases.append(missing_fence)
        for document in cases:
            with self.subTest(document=document):
                with self.assertRaises(ConformanceError):
                    validate_document(document)

    def test_event_sequence_is_contiguous_fenced_and_terminal(self) -> None:
        events = []
        for sequence, name in enumerate(("accepted", "started", "artifact", "terminal"), 1):
            event = copy.deepcopy(self.event)
            event["sequence"], event["event"] = sequence, name
            events.append(event)
        validate_event_sequence(events)
        validate_completed_response(events, self.receipt)
        duplicate = copy.deepcopy(events)
        duplicate[2]["sequence"] = 2
        with self.assertRaises(ConformanceError):
            validate_event_sequence(duplicate)
        stale = copy.deepcopy(events)
        stale[2]["fence_token"] = "stale-fence"
        with self.assertRaises(ConformanceError):
            validate_event_sequence(stale)
        after_terminal = copy.deepcopy(events)
        extra = copy.deepcopy(after_terminal[-1])
        extra["sequence"], extra["event"] = 5, "output"
        after_terminal.append(extra)
        with self.assertRaises(ConformanceError):
            validate_event_sequence(after_terminal)

        mismatched_receipt = copy.deepcopy(self.receipt)
        mismatched_receipt["fence_token"] = "stale-fence"
        with self.assertRaises(ConformanceError):
            validate_completed_response(events, mismatched_receipt)

    def test_terminal_event_and_receipt_outcome_must_match(self) -> None:
        event = copy.deepcopy(self.event)
        event["sequence"] = 1

        completed = copy.deepcopy(self.receipt)
        validate_completed_response([event], completed)

        failed = copy.deepcopy(self.receipt)
        failed["outcome"] = "failed"
        validate_completed_response([event], failed)

        cancelled_event = copy.deepcopy(event)
        cancelled_event["event"] = "cancelled"
        cancelled_receipt = copy.deepcopy(self.receipt)
        cancelled_receipt["outcome"] = "cancelled"
        validate_completed_response([cancelled_event], cancelled_receipt)
        with self.assertRaises(ConformanceError):
            validate_completed_response([cancelled_event], completed)

        terminal_with_cancelled = copy.deepcopy(self.receipt)
        terminal_with_cancelled["outcome"] = "cancelled"
        with self.assertRaises(ConformanceError):
            validate_completed_response([event], terminal_with_cancelled)

        indeterminate_event = copy.deepcopy(event)
        indeterminate_event["event"] = "indeterminate"
        indeterminate_receipt = copy.deepcopy(self.receipt)
        indeterminate_receipt["status"] = "indeterminate"
        indeterminate_receipt["outcome"] = "indeterminate"
        indeterminate_receipt["ended_at"] = None
        validate_completed_response([indeterminate_event], indeterminate_receipt)
        with self.assertRaises(ConformanceError):
            validate_completed_response([indeterminate_event], completed)

    def test_receipt_replay_is_immutable_and_indeterminate_is_fail_closed(self) -> None:
        validate_replay_receipt(self.receipt, copy.deepcopy(self.receipt))
        changed = copy.deepcopy(self.receipt)
        changed["outcome"] = "failed"
        with self.assertRaises(ConformanceError):
            validate_replay_receipt(self.receipt, changed)
        indeterminate = copy.deepcopy(self.receipt)
        indeterminate["status"], indeterminate["ended_at"] = "indeterminate", None
        with self.assertRaises(ConformanceError):
            validate_document(indeterminate)
        indeterminate["outcome"] = "indeterminate"
        validate_document(indeterminate)

    def test_process_identity_is_required_only_for_proven_process_outcomes(self) -> None:
        completed_without_process = copy.deepcopy(self.receipt)
        completed_without_process["process_identity"] = None
        with self.assertRaises(ConformanceError):
            validate_document(completed_without_process)

        cancelled_without_process = copy.deepcopy(completed_without_process)
        cancelled_without_process["outcome"] = "cancelled"
        with self.assertRaises(ConformanceError):
            validate_document(cancelled_without_process)

        failed_without_process = copy.deepcopy(completed_without_process)
        failed_without_process["outcome"] = "failed"
        validate_document(failed_without_process)

        indeterminate_without_process = copy.deepcopy(completed_without_process)
        indeterminate_without_process["status"] = "indeterminate"
        indeterminate_without_process["outcome"] = "indeterminate"
        indeterminate_without_process["ended_at"] = None
        validate_document(indeterminate_without_process)

    def test_artifact_digest_and_size(self) -> None:
        content = b'{"fixture":"agent-host"}\n'
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "artifact.json"
            artifact.write_bytes(content)
            validate_artifact(artifact, hashlib.sha256(content).hexdigest(), len(content))
            with self.assertRaises(ConformanceError):
                validate_artifact(artifact, "0" * 64)

    def test_request_digest_uses_exact_wire_line_without_delimiter(self) -> None:
        wire = b'{"message_type":"request","request_id":"request-001"}'
        expected = hashlib.sha256(wire).hexdigest()
        self.assertEqual(request_wire_digest(wire + b"\r\n"), expected)
        self.assertNotEqual(request_wire_digest(wire + b" "), expected)
        with self.assertRaises(ConformanceError):
            request_wire_digest(b"{}\n{}")

    def test_secret_like_fields_and_values_are_rejected(self) -> None:
        with self.assertRaises(ConformanceError):
            assert_redacted({"api_key": "redacted"})
        with self.assertRaises(ConformanceError):
            assert_redacted({"output": "sk-" + "A" * 20})


if __name__ == "__main__":
    unittest.main()

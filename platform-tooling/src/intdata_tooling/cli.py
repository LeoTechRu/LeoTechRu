"""Command-line interface for Wave 1 platform contract tooling."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Sequence

from ._json import StrictJSONError
from ._schemas import SchemaSet, SchemaSetError

MODULE_SCHEMA = "urn:intdata:schema:module-manifest:v1"
INSTALLATION_SCHEMA = "urn:intdata:schema:installation-manifest:v1"
LOCK_SCHEMA = "urn:intdata:schema:installation-lock:v1"
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def _add_input(parser: argparse.ArgumentParser, *, schema: bool = False) -> None:
    parser.add_argument(
        "--schema-set",
        type=Path,
        required=True,
        help="tracked contracts/platform/v1/schema-set.json",
    )
    if schema:
        parser.add_argument("--schema", required=True, help="exact schema $id")
    parser.add_argument("document", help="strict UTF-8 JSON file, or - for stdin")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intdata-tools",
        description="Offline intData platform contract validation and RFC 8785 tooling.",
    )
    groups = parser.add_subparsers(dest="group", required=True)

    schema_parser = groups.add_parser("schema", help="generic schema operations")
    schema_commands = schema_parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("validate", "strictly parse and validate a document"),
        ("canonicalize", "write validated RFC 8785 bytes"),
        ("digest", "write validated canonical SHA-256"),
    ):
        leaf = schema_commands.add_parser(command, help=help_text)
        _add_input(leaf, schema=True)

    module_parser = groups.add_parser("module", help="ModuleManifestV1 operations")
    module_commands = module_parser.add_subparsers(dest="command", required=True)
    module_validate = module_commands.add_parser("validate")
    _add_input(module_validate)

    installation_parser = groups.add_parser(
        "installation", help="InstallationManifestV1 operations"
    )
    installation_commands = installation_parser.add_subparsers(
        dest="command", required=True
    )
    installation_validate = installation_commands.add_parser("validate")
    _add_input(installation_validate)

    lock_parser = groups.add_parser("lock", help="InstallationLockV1 operations")
    lock_commands = lock_parser.add_subparsers(dest="command", required=True)
    lock_verify = lock_commands.add_parser(
        "verify", help="validate a lock and verify its canonical digest"
    )
    _add_input(lock_verify)
    lock_verify.add_argument(
        "--expected-digest",
        help="optional lowercase canonical SHA-256 to compare",
    )
    return parser


def _read_document(path: str) -> bytes:
    if path == "-":
        return sys.stdin.buffer.read()
    try:
        return Path(path).read_bytes()
    except OSError as error:
        raise SchemaSetError(f"cannot read document {path!r}: {error}") from error


def _write_stdout_line(value: str) -> None:
    sys.stdout.buffer.write(value.encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def _write_stderr_line(value: str) -> None:
    sys.stderr.buffer.write(value.encode("utf-8") + b"\n")
    sys.stderr.buffer.flush()


def _schema_id(args: argparse.Namespace) -> str:
    if args.group == "schema":
        return args.schema
    if args.group == "module":
        return MODULE_SCHEMA
    if args.group == "installation":
        return INSTALLATION_SCHEMA
    return LOCK_SCHEMA


def run(args: argparse.Namespace) -> int:
    schema_set = SchemaSet.load(args.schema_set)
    raw = _read_document(args.document)
    schema_id = _schema_id(args)

    if args.group == "schema" and args.command == "canonicalize":
        sys.stdout.buffer.write(schema_set.canonicalize_raw(raw, schema_id))
        sys.stdout.buffer.flush()
        return 0
    if args.group == "schema" and args.command == "digest":
        _write_stdout_line(schema_set.digest_raw(raw, schema_id))
        return 0
    if args.group == "lock":
        digest = schema_set.digest_raw(raw, schema_id)
        if args.expected_digest is not None:
            if _DIGEST.fullmatch(args.expected_digest) is None:
                raise SchemaSetError("expected digest must be lowercase SHA-256")
            if digest != args.expected_digest:
                raise SchemaSetError(
                    f"lock digest mismatch: expected {args.expected_digest}, got {digest}"
                )
        _write_stdout_line(digest)
        return 0

    schema_set.validate_raw(raw, schema_id)
    _write_stdout_line("valid")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (SchemaSetError, StrictJSONError) as error:
        _write_stderr_line(f"error: {error}")
        return 2

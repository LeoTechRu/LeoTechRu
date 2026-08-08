#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


SCHEMA = "intdata.plugin-pack/v1"
SECRET_NAMES = {
    ".env",
    "auth.json",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
    "token.json",
}
SECRET_SUFFIXES = {".key", ".p12", ".pfx", ".pem"}
GENERATED_PARTS = {
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "logs",
    "sessions",
}
GENERATED_SUFFIXES = {".log", ".pyc", ".pyo"}


class PackError(ValueError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _repository(source: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise PackError(f"source is not inside a Git repository: {source}")
    return Path(result.stdout.strip()).resolve()


def _is_secret(relative: Path) -> bool:
    name = relative.name.lower()
    return (
        name in SECRET_NAMES
        or name.startswith(".env.")
        or relative.suffix.lower() in SECRET_SUFFIXES
    )


def _is_generated(relative: Path) -> bool:
    return (
        any(part in GENERATED_PARTS for part in relative.parts)
        or relative.suffix.lower() in GENERATED_SUFFIXES
    )


def tracked_files(source: Path) -> list[tuple[Path, str]]:
    source = source.resolve(strict=True)
    repository = _repository(source)
    try:
        relative_source = source.relative_to(repository)
    except ValueError as exc:
        raise PackError("source must be contained by its Git repository") from exc
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "ls-files",
            "--stage",
            "-z",
            "--",
            relative_source.as_posix(),
        ],
        check=True,
        capture_output=True,
    )
    files: list[tuple[Path, str]] = []
    for entry in result.stdout.split(b"\0"):
        if not entry:
            continue
        metadata, separator, raw_path = entry.partition(b"\t")
        if not separator:
            raise PackError("unexpected git ls-files output")
        mode = metadata.split(maxsplit=1)[0].decode("ascii")
        path = repository / os.fsdecode(raw_path)
        relative = path.relative_to(source)
        if mode == "120000" or path.is_symlink():
            raise PackError(f"refusing tracked symlink: {relative.as_posix()}")
        if mode not in {"100644", "100755"}:
            raise PackError(f"refusing non-file Git mode {mode}: {relative.as_posix()}")
        if _is_secret(relative):
            raise PackError(f"refusing secret-shaped tracked file: {relative.as_posix()}")
        if _is_generated(relative):
            continue
        resolved = path.resolve(strict=True)
        try:
            resolved.relative_to(source)
        except ValueError as exc:
            raise PackError(f"refusing file outside source: {relative.as_posix()}") from exc
        if not resolved.is_file():
            raise PackError(f"tracked path is not a regular file: {relative.as_posix()}")
        files.append((resolved, mode))
    return sorted(files, key=lambda item: item[0].relative_to(source).as_posix())


def manifest(source: Path) -> dict[str, Any]:
    source = source.resolve(strict=True)
    entries = []
    tree = hashlib.sha256()
    for path, mode in tracked_files(source):
        relative = path.relative_to(source).as_posix()
        content = path.read_bytes()
        encoded_path = relative.encode("utf-8")
        encoded_mode = mode.encode("ascii")
        tree.update(len(encoded_path).to_bytes(4, "big"))
        tree.update(encoded_path)
        tree.update(encoded_mode)
        tree.update(len(content).to_bytes(8, "big"))
        tree.update(content)
        entries.append(
            {
                "path": relative,
                "mode": mode,
                "size": len(content),
                "sha256": _sha256(content),
            }
        )
    return {
        "schema": SCHEMA,
        "source": source.name,
        "files": entries,
        "tree_sha256": tree.hexdigest(),
    }


def write_manifest(path: Path, value: dict[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise PackError(f"refusing to overwrite manifest: {path}")
    path.write_text(_canonical_json(value), encoding="utf-8")


def pack(source: Path, output: Path, manifest_path: Path) -> dict[str, Any]:
    source = source.resolve(strict=True)
    output = output.resolve()
    manifest_path = manifest_path.resolve()
    if output == source or output in source.parents or source in output.parents:
        raise PackError("source and output must not contain each other")
    if manifest_path == output or output in manifest_path.parents:
        raise PackError("manifest must be outside output")
    if output.exists():
        raise PackError(f"refusing to overwrite output: {output}")
    value = manifest(source)
    output.mkdir(parents=True)
    by_path = {entry["path"]: entry for entry in value["files"]}
    try:
        for path, mode in tracked_files(source):
            relative = path.relative_to(source)
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with path.open("rb") as source_file, target.open("xb") as target_file:
                shutil.copyfileobj(source_file, target_file)
            target.chmod(0o755 if mode == "100755" else 0o644)
            if _sha256(target.read_bytes()) != by_path[relative.as_posix()]["sha256"]:
                raise PackError(f"copy verification failed: {relative.as_posix()}")
        write_manifest(manifest_path, value)
    except Exception:
        if output.exists():
            shutil.rmtree(output)
        raise
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pack or hash a plugin from tracked regular files only"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("pack", "hash"):
        child = subparsers.add_parser(command)
        child.add_argument("--source", type=Path, required=True)
        child.add_argument("--manifest", type=Path, required=True)
        if command == "pack":
            child.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "pack":
            value = pack(args.source, args.output, args.manifest)
        else:
            value = manifest(args.source)
            write_manifest(args.manifest, value)
    except (OSError, PackError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc)) from exc
    print(_canonical_json(value), end="")


if __name__ == "__main__":
    main()

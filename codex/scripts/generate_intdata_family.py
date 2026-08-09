#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover - packaging failure
    raise SystemExit("jsonschema>=4.20 is required") from exc


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "codex" / "family" / "intdata-family.json"
DEFAULT_SCHEMA = ROOT / "codex" / "family" / "intdata-family.schema.json"
EXPECTED_SKILLS = {
    "intbridge": (
        "probe-operator", "fleet-diagnostics", "client-control",
        "incident-response", "probe-administration",
        "dba-health", "doctor-status", "local-smoke", "migrations", "sql-apply",
    ),
    "intagent": (
        "agent-control", "environment-detection", "mode-resolution", "mode-router",
        "host-diagnostics", "hypothesis-diagnosis", "ssh",
        "firefox-devtools-testing", "vault-maintenance",
    ),
    "intdev": (
        "approval-guidance", "coordctl", "delivery-acceptance", "issues",
        "openspec-read", "openspec-mutation", "review-find", "review-fix",
        "routing", "scope-drift-router",
    ),
}
EXPECTED_COMPONENTS = {
    "intbridge": (
        {
            "id": "probe",
            "display_name": "intData Bridge Probe",
            "skills": (
                "probe-operator", "fleet-diagnostics", "client-control",
                "incident-response", "probe-administration",
            ),
            "runtime_access": "owner-only",
            "mcp_resource": "probe",
            "oauth_resource": "https://intdata.pro/mcp/probe",
            "scopes": (),
            "approval_policy": "probe-confirmation",
            "credential_boundary": "probe",
            "service_boundary": "probe",
            "state_boundary": "probe",
        },
        {
            "id": "dba",
            "display_name": "intData Bridge DBA",
            "skills": (
                "dba-health", "doctor-status", "local-smoke", "migrations", "sql-apply",
            ),
            "runtime_access": "policy-gated",
            "mcp_resource": None,
            "oauth_resource": None,
            "scopes": (),
            "approval_policy": "route-specific",
            "credential_boundary": "dba",
            "service_boundary": "dba",
            "state_boundary": "dba",
        },
    ),
    "intagent": (),
    "intdev": (),
}
LEGACY_PLUGIN_IDS = {"dba", "intprobe", "intdba", "intdata-control", "intdata-runtime"}
EXPECTED_RESOURCE_IDS = {"platform", "punkt-b", "crm", "cms", "brain", "probe", "lms", "agent"}
PROVENANCE_FIELDS = ("commit", "tree_sha256", "manifest_sha256")
EXPECTED_PLUGIN_ACCESS = {
    "intbridge": ("private", "authenticated", "component-gated", None),
    "intagent": ("private", "authenticated", "owner-only", "https://intdata.pro/mcp/agent"),
    "intdev": ("public", "public", "authenticated", None),
}
EXPECTED_PLUGIN_REPOSITORIES = {
    "intbridge": "https://github.com/LeoTechPro/intData-bridge.git",
    "intagent": "https://github.com/LeoTechPro/intData-agent.git",
    "intdev": "https://github.com/LeoTechPro/intData-tools.git",
}
EXPECTED_PLUGIN_MANIFEST_PATHS = {
    plugin_id: f"{subdir}/.codex-plugin/plugin.json"
    for plugin_id, subdir in {
        "intbridge": "plugins/intbridge",
        "intagent": "plugins/intagent",
        "intdev": "codex/plugins/intdev",
    }.items()
}
EXPECTED_PLUGIN_LICENSE_PATHS = {
    plugin_id: f"{PurePosixPath(path).parents[1].as_posix()}/LICENSE"
    for plugin_id, path in EXPECTED_PLUGIN_MANIFEST_PATHS.items()
}
EXPECTED_RESOURCE_REPOSITORIES = {
    "agent": "https://github.com/LeoTechPro/intData-agent.git",
    "brain": "https://github.com/LeoTechPro/intData-brain.git",
    "probe": "https://github.com/LeoTechPro/intData-bridge.git",
    "platform": "https://github.com/LeoTechPro/intData-backend.git",
    "punkt-b": "https://github.com/LeoTechPro/punkt-b.git",
    "crm": "https://github.com/LeoTechPro/intData-CRM.git",
    "cms": "https://github.com/LeoTechPro/intData-CMS.git",
    "lms": "https://github.com/LeoTechPro/intData-LMS.git",
}
EXPECTED_RESOURCE_RUNTIME_ACCESS = {
    "agent": "owner-only",
    "brain": "authenticated",
    "probe": "owner-only",
    "platform": "owner-only",
    "punkt-b": "authenticated",
    "crm": "authenticated",
    "cms": "authenticated",
    "lms": "authenticated",
}
EXPECTED_RESOURCE_MANIFEST_PATHS = {
    resource_id: f"mcp/resources/{resource_id}.json"
    for resource_id in EXPECTED_RESOURCE_IDS
}
EXPECTED_RESOURCE_LICENSE_PATHS = {
    resource_id: (
        "LICENSE" if resource_id in {"agent", "platform"} else "mcp/resources/LICENSE"
    )
    for resource_id in EXPECTED_RESOURCE_IDS
}
SCOPED_PROPRIETARY_RESOURCE_IDS = {"brain", "probe", "punkt-b", "crm", "cms", "lms"}
APPROVED_PROPRIETARY_RESOURCE_LICENSE = (
    b"Copyright (c) 2026 intData. All rights reserved.\n\n"
    b"This software and its accompanying documentation are proprietary to intData.\n"
    b"No permission is granted to use, copy, modify, distribute, sublicense, or sell\n"
    b"them without prior written permission from intData.\n"
)
APPROVED_PROPRIETARY_RESOURCE_LICENSE_SHA256 = (
    "3031748e7e11ef3e1772738704df5e3e83d949085e04a8a9fc54206758791bb0"
)
CATALOG_FILENAME = "intdata.family-catalog.v1.json"
CATALOG_SCHEMA_FILENAME = "intdata.family-catalog.v1.schema.json"
LOCK_FILENAME = "intdata.family-release-lock.v1.json"
MARKETPLACE_FILENAME = "marketplace.json"
ACTIVATION_FILENAME = "intdata.family-activation.v1.json"


class FamilyManifestError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise FamilyManifestError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    if not isinstance(value, dict):
        raise FamilyManifestError(f"{path}: root must be an object")
    return value


def normalized_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(manifest)
    value.pop("$schema", None)
    value["mcp_resources"] = sorted(value["mcp_resources"], key=lambda item: item["id"])
    value["plugins"] = sorted(value["plugins"], key=lambda item: item["id"])
    return value


def safe_repo_path(value: str, *, field: str, allow_dot: bool = True) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "" in path.parts:
        raise FamilyManifestError(f"{field} must be a contained repository-relative path")
    if not allow_dot and value in {"", "."}:
        raise FamilyManifestError(f"{field} must name a file")
    if value != path.as_posix():
        raise FamilyManifestError(f"{field} must be normalized POSIX syntax")
    return path


def validate_generated_at(value: str) -> None:
    try:
        parsed = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise FamilyManifestError("generated_at must be a valid UTC RFC3339 timestamp") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise FamilyManifestError("generated_at must use canonical UTC RFC3339 serialization")


def projection_schema(
    schema: dict[str, Any], definition: str, *, schema_id: str, title: str
) -> dict[str, Any]:
    if definition not in schema.get("$defs", {}):
        raise FamilyManifestError(f"canonical schema lacks $defs/{definition}")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_id,
        "title": title,
        "$ref": f"#/$defs/{definition}",
        "$defs": copy.deepcopy(schema["$defs"]),
    }


def validate_projection(value: dict[str, Any], schema: dict[str, Any], definition: str) -> None:
    validator = jsonschema.Draft202012Validator(
        projection_schema(
            schema,
            definition,
            schema_id=f"https://intdata.pro/schemas/{definition.replace('_', '-')}-v1.json",
            title=definition.replace("_", " "),
        )
    )
    errors = sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    if errors:
        formatted = "; ".join(
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise FamilyManifestError(f"generated {definition} is invalid: {formatted}")


def run_git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise FamilyManifestError(f"git {' '.join(args)} failed in {repo}: {message}")
    return result.stdout


def tree_digest(repo: Path, commit: str, subdir: str) -> str:
    treeish = commit if subdir == "." else f"{commit}:{subdir}"
    listing = run_git(repo, "ls-tree", "-r", "--full-tree", treeish)
    return sha256_bytes(listing)


def blob_bytes(repo: Path, commit: str, path: str) -> bytes:
    listing = run_git(repo, "ls-tree", commit, "--", path).decode("utf-8", errors="replace").strip()
    if not listing:
        raise FamilyManifestError(f"{path} is absent at {commit}")
    mode, object_type, _rest = listing.split(maxsplit=2)
    if object_type != "blob" or mode not in {"100644", "100755"}:
        raise FamilyManifestError(f"{path} must be an ordinary Git blob, got {mode} {object_type}")
    return run_git(repo, "show", f"{commit}:{path}")


def canonical_remote(value: str) -> tuple[str, str, str]:
    cleaned = value.strip().removesuffix("/").removesuffix(".git")
    if cleaned.startswith("git@github.com:"):
        path = cleaned.removeprefix("git@github.com:")
        host = "github.com"
    else:
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"https", "ssh"} or parsed.hostname != "github.com":
            raise FamilyManifestError(f"unsupported canonical GitHub remote: {value}")
        host = parsed.hostname
        path = parsed.path.lstrip("/")
    parts = path.split("/")
    if len(parts) != 2 or not all(parts):
        raise FamilyManifestError(f"invalid canonical GitHub repository identity: {value}")
    return host.lower(), parts[0], parts[1]


def load_json_blob(repo: Path, commit: str, path: str) -> dict[str, Any]:
    try:
        value = json.loads(
            blob_bytes(repo, commit, path).decode("utf-8"),
            object_pairs_hook=unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FamilyManifestError(f"{path} must be a UTF-8 JSON object at {commit}") from exc
    if not isinstance(value, dict):
        raise FamilyManifestError(f"{path} must be a JSON object at {commit}")
    return value


def skill_names_at_commit(repo: Path, commit: str, subdir: str) -> tuple[str, ...]:
    prefix = "skills" if subdir == "." else f"{subdir}/skills"
    paths = run_git(repo, "ls-tree", "-r", "--name-only", commit, "--", prefix).decode().splitlines()
    skill_paths: dict[str, str] = {}
    for path in paths:
        relative = PurePosixPath(path).relative_to(PurePosixPath(prefix))
        if relative.name != "SKILL.md":
            continue
        if len(relative.parts) != 2:
            raise FamilyManifestError(f"{path} is a non-canonical skill entrypoint")
        skill_paths[relative.parts[0]] = path
    for directory, path in skill_paths.items():
        content = blob_bytes(repo, commit, path).decode("utf-8")
        if not content.startswith("---\n"):
            raise FamilyManifestError(f"{path} lacks leading YAML frontmatter")
        frontmatter = content.split("---", 2)
        if len(frontmatter) < 3:
            raise FamilyManifestError(f"{path} lacks YAML frontmatter")
        names = [
            line.removeprefix("name:").strip()
            for line in frontmatter[1].splitlines()
            if line.startswith("name:")
        ]
        if names != [directory]:
            raise FamilyManifestError(f"{path} frontmatter name must be {directory}")
    return tuple(sorted(skill_paths))


def validate_source_manifest(
    entry: dict[str, Any], repo: Path, commit: str, manifest_path: str, license_path: str
) -> None:
    source = load_json_blob(repo, commit, manifest_path)
    if entry["id"] in EXPECTED_SKILLS:
        if "aliases" in source:
            raise FamilyManifestError(f"{entry['id']} source plugin aliases are forbidden")
        expected = {
            "name": entry["id"],
            "version": entry["release_version"],
            "license": entry["provenance"]["license"],
            "skills": "./skills",
        }
        for field, value in expected.items():
            if source.get(field) != value:
                raise FamilyManifestError(f"{entry['id']} source plugin {field} differs from family manifest")
        interface = source.get("interface")
        if not isinstance(interface, dict):
            raise FamilyManifestError(f"{entry['id']} source plugin interface is required")
        if interface.get("displayName") != entry["display_name"]:
            raise FamilyManifestError(f"{entry['id']} source plugin displayName differs from family manifest")
        if interface.get("category") != entry["category"]:
            raise FamilyManifestError(f"{entry['id']} source plugin category differs from family manifest")
        actual_skills = skill_names_at_commit(repo, commit, entry["provenance"]["subdir"])
        if actual_skills != tuple(sorted(EXPECTED_SKILLS[entry["id"]])):
            raise FamilyManifestError(f"{entry['id']} source plugin skills differ from the canonical map")
    else:
        expected = {key: value for key, value in entry.items() if key != "provenance"}
        expected["license"] = entry["provenance"]["license"]
        for field, value in expected.items():
            if source.get(field) != value:
                raise FamilyManifestError(f"{entry['id']} source resource {field} differs from family manifest")
        extra_fields = sorted(set(source) - set(expected))
        if extra_fields:
            raise FamilyManifestError(
                f"{entry['id']} source resource has unsupported fields: {extra_fields}"
            )

    license_bytes = blob_bytes(repo, commit, license_path)
    try:
        license_blob = license_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise FamilyManifestError(f"{entry['id']} license file must be UTF-8 text") from exc
    license_markers = {
        "Proprietary": ("proprietary", "all rights reserved"),
        "MIT": ("mit license", "permission is hereby granted, free of charge"),
        "Apache-2.0": ("apache license", "version 2.0"),
    }
    license_id = entry["provenance"]["license"]
    markers = license_markers.get(license_id)
    if markers is None:
        raise FamilyManifestError(f"{entry['id']} uses unsupported license identifier: {license_id}")
    normalized_license = license_blob.lower()
    if not all(marker in normalized_license for marker in markers):
        raise FamilyManifestError(
            f"{entry['id']} license file does not match the {license_id} contract"
        )
    if (
        entry["id"] in SCOPED_PROPRIETARY_RESOURCE_IDS
        and sha256_bytes(license_bytes) != APPROVED_PROPRIETARY_RESOURCE_LICENSE_SHA256
    ):
        raise FamilyManifestError(
            f"{entry['id']} license file differs from the exact owner-approved carrier"
        )


def verify_provenance(
    entry: dict[str, Any], source_roots: dict[str, Path]
) -> None:
    provenance = entry["provenance"]
    repository = provenance["repository"]
    repo = source_roots.get(repository)
    if repo is None:
        raise FamilyManifestError(f"{entry['id']} lacks a trusted source checkout for {repository}")
    try:
        repo = repo.expanduser().resolve(strict=True)
    except OSError as exc:
        raise FamilyManifestError(f"{entry['id']} trusted source checkout is unavailable: {repo}") from exc
    if run_git(repo, "rev-parse", "--is-inside-work-tree").strip() != b"true":
        raise FamilyManifestError(f"{repo} is not a Git worktree")
    remote_lines = [line.decode("utf-8").strip() for line in run_git(repo, "remote", "get-url", "--all", "origin").splitlines()]
    if len(remote_lines) != 1:
        raise FamilyManifestError(f"{entry['id']} source checkout must have exactly one origin fetch URL")
    if canonical_remote(repository) != canonical_remote(remote_lines[0]):
        raise FamilyManifestError(f"{entry['id']} source checkout origin does not match {repository}")

    commit = provenance["commit"]
    run_git(repo, "cat-file", "-e", f"{commit}^{{commit}}")
    subdir = safe_repo_path(provenance["subdir"], field=f"{entry['id']} provenance.subdir")
    manifest_path = safe_repo_path(
        provenance["manifest_path"], field=f"{entry['id']} provenance.manifest_path", allow_dot=False
    )
    license_path = safe_repo_path(
        provenance["license_path"], field=f"{entry['id']} provenance.license_path", allow_dot=False
    )
    if subdir != PurePosixPath(".") and subdir not in manifest_path.parents:
        raise FamilyManifestError(f"{entry['id']} manifest_path must be within provenance.subdir")

    actual_tree = tree_digest(repo, commit, subdir.as_posix())
    if actual_tree != provenance["tree_sha256"]:
        raise FamilyManifestError(f"{entry['id']} tree_sha256 does not match the exact commit/subdir")
    actual_manifest = sha256_bytes(blob_bytes(repo, commit, manifest_path.as_posix()))
    if actual_manifest != provenance["manifest_sha256"]:
        raise FamilyManifestError(f"{entry['id']} manifest_sha256 does not match the exact commit")
    actual_license = sha256_bytes(blob_bytes(repo, commit, license_path.as_posix()))
    if actual_license != provenance["license_sha256"]:
        raise FamilyManifestError(f"{entry['id']} license_sha256 does not match the exact commit")
    validate_source_manifest(
        entry, repo, commit, manifest_path.as_posix(), license_path.as_posix()
    )


def validate_manifest(
    manifest: dict[str, Any],
    schema: dict[str, Any],
    *,
    require_release: bool,
    source_roots: dict[str, Path] | None = None,
) -> None:
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(manifest), key=lambda item: list(item.absolute_path))
    if errors:
        formatted = "; ".join(
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise FamilyManifestError(formatted)

    validate_generated_at(manifest["generated_at"])

    plugins = {entry["id"]: entry for entry in manifest["plugins"]}
    if set(plugins) != set(EXPECTED_SKILLS):
        raise FamilyManifestError(f"plugin IDs must be exactly {sorted(EXPECTED_SKILLS)}")
    if set(plugins) & LEGACY_PLUGIN_IDS:
        raise FamilyManifestError("legacy plugin IDs are forbidden")
    probe_resource = next(
        (resource for resource in manifest["mcp_resources"] if resource["id"] == "probe"),
        None,
    )
    if probe_resource is None:
        raise FamilyManifestError(f"MCP resource IDs must be exactly {sorted(EXPECTED_RESOURCE_IDS)}")
    probe_component = next(
        (
            component
            for component in plugins["intbridge"]["components"]
            if component["id"] == "probe"
        ),
        None,
    )
    if probe_component is None:
        raise FamilyManifestError("intbridge component mapping must include probe")
    if probe_component["scopes"] != probe_resource["scopes"]:
        raise FamilyManifestError("probe component scopes must match probe resource scopes")
    if plugins["intbridge"]["display_name"] != "intData Bridge":
        raise FamilyManifestError("intbridge display_name must be intData Bridge")
    if plugins["intbridge"]["owner"] != "intData Bridge":
        raise FamilyManifestError("intbridge owner must be intData Bridge")
    for plugin_id, expected in EXPECTED_SKILLS.items():
        plugin = plugins[plugin_id]
        actual = tuple(plugins[plugin_id]["skills"])
        if actual != expected:
            raise FamilyManifestError(f"{plugin_id} skill mapping differs from the canonical map")
        expected_components = [
            {
                **component,
                "skills": list(component["skills"]),
                "scopes": list(component["scopes"]),
            }
            for component in EXPECTED_COMPONENTS[plugin_id]
        ]
        if plugin_id == "intbridge":
            next(
                component for component in expected_components if component["id"] == "probe"
            )["scopes"] = list(probe_resource["scopes"])
        if plugin["components"] != expected_components:
            raise FamilyManifestError(f"{plugin_id} component mapping differs from the canonical map")
        component_skills = tuple(
            skill
            for component in plugin["components"]
            for skill in component["skills"]
        )
        if plugin["components"] and component_skills != actual:
            raise FamilyManifestError(f"{plugin_id} component skills differ from the plugin skill map")
        actual_access = (
            plugin["source_access"], plugin["install_access"],
            plugin["runtime_access"], plugin["oauth_resource"],
        )
        if actual_access != EXPECTED_PLUGIN_ACCESS[plugin_id]:
            raise FamilyManifestError(f"{plugin_id} access/OAuth contract differs from the canonical matrix")
        if plugin["provenance"]["repository"] != EXPECTED_PLUGIN_REPOSITORIES[plugin_id]:
            raise FamilyManifestError(f"{plugin_id} source repository differs from the canonical repository")
        if plugin["provenance"]["manifest_path"] != EXPECTED_PLUGIN_MANIFEST_PATHS[plugin_id]:
            raise FamilyManifestError(f"{plugin_id} source manifest path differs from the canonical path")
        if plugin["provenance"]["license_path"] != EXPECTED_PLUGIN_LICENSE_PATHS[plugin_id]:
            raise FamilyManifestError(f"{plugin_id} license path differs from the canonical path")
        safe_repo_path(plugin["provenance"]["subdir"], field=f"{plugin_id} provenance.subdir")
        safe_repo_path(
            plugin["provenance"]["manifest_path"],
            field=f"{plugin_id} provenance.manifest_path",
            allow_dot=False,
        )
        safe_repo_path(
            plugin["provenance"]["license_path"],
            field=f"{plugin_id} provenance.license_path",
            allow_dot=False,
        )

    if manifest["routing_policy"] != {
        "probe_failure_scope": "probe-route-only",
        "alternative_routes": "independently-authorized",
        "probe_mutations": "fail-closed",
        "os_aware": True,
    }:
        raise FamilyManifestError("routing policy weakens the route-local Probe invariant")

    resource_ids = [entry["id"] for entry in manifest["mcp_resources"]]
    if len(resource_ids) != len(set(resource_ids)):
        raise FamilyManifestError("MCP resource IDs must be unique")
    if set(resource_ids) != EXPECTED_RESOURCE_IDS:
        raise FamilyManifestError(f"MCP resource IDs must be exactly {sorted(EXPECTED_RESOURCE_IDS)}")
    resources = {entry["id"]: entry for entry in manifest["mcp_resources"]}
    probe = resources["probe"]
    if (probe["display_name"], probe["owner"]) != ("intData Bridge Probe", "intData Bridge"):
        raise FamilyManifestError("probe resource identity must belong to intData Bridge")
    agent = resources.get("agent")
    if not agent:
        raise FamilyManifestError("agent MCP resource is required")
    if agent["runtime_access"] != "owner-only" or agent["scopes"] != [
        "agent.read", "agent.mutate", "agent.admin"
    ]:
        raise FamilyManifestError("agent resource access/scopes differ from the owner-only v1 contract")
    endpoints = []
    metadata_uris = []
    for resource_id, resource in resources.items():
        endpoint = f"https://intdata.pro/mcp/{resource_id}"
        metadata_uri = f"https://intdata.pro/.well-known/oauth-protected-resource/mcp/{resource_id}"
        if resource["endpoint"] != endpoint or resource["oauth_resource"] != endpoint:
            raise FamilyManifestError(f"{resource_id} endpoint/OAuth audience differs from the exact contract")
        if resource["metadata_uri"] != metadata_uri:
            raise FamilyManifestError(f"{resource_id} metadata URI differs from the exact contract")
        if resource["runtime_access"] != EXPECTED_RESOURCE_RUNTIME_ACCESS[resource_id]:
            raise FamilyManifestError(f"{resource_id} runtime access differs from the canonical matrix")
        authorization = resource["authorization"]
        if authorization["audience"] != endpoint:
            raise FamilyManifestError(f"{resource_id} authorization audience differs from the exact contract")
        if authorization["external_bearer_forwarding"] is not False:
            raise FamilyManifestError(f"{resource_id} external bearer forwarding is forbidden")
        if authorization["state"] == "unconfigured":
            if resource["availability"] != "unavailable":
                raise FamilyManifestError(f"{resource_id} cannot be available with unconfigured authorization")
        else:
            if authorization["downstream_credential"]["audience"] == endpoint:
                raise FamilyManifestError(f"{resource_id} internal assertion audience must not equal the external audience")
            if not resource["scopes"]:
                raise FamilyManifestError(f"{resource_id} configured authorization requires explicit scopes")
        if resource["provenance"]["repository"] != EXPECTED_RESOURCE_REPOSITORIES[resource_id]:
            raise FamilyManifestError(f"{resource_id} source repository differs from the canonical repository")
        if resource["provenance"]["manifest_path"] != EXPECTED_RESOURCE_MANIFEST_PATHS[resource_id]:
            raise FamilyManifestError(f"{resource_id} source manifest path differs from the canonical path")
        if resource["provenance"]["license_path"] != EXPECTED_RESOURCE_LICENSE_PATHS[resource_id]:
            raise FamilyManifestError(f"{resource_id} license path differs from the canonical path")
        safe_repo_path(resource["provenance"]["subdir"], field=f"{resource_id} provenance.subdir")
        safe_repo_path(
            resource["provenance"]["manifest_path"],
            field=f"{resource_id} provenance.manifest_path",
            allow_dot=False,
        )
        safe_repo_path(
            resource["provenance"]["license_path"],
            field=f"{resource_id} provenance.license_path",
            allow_dot=False,
        )
        endpoints.append(endpoint)
        metadata_uris.append(metadata_uri)
    if len(endpoints) != len(set(endpoints)) or len(metadata_uris) != len(set(metadata_uris)):
        raise FamilyManifestError("MCP endpoint, audience and metadata URIs must be unique")

    if require_release or manifest["release_state"] == "released":
        if manifest["release_state"] != "released":
            raise FamilyManifestError("release projections require release_state=released")
        for plugin in manifest["plugins"]:
            if plugin["availability"] != "available" or plugin["maturity"] == "planned":
                raise FamilyManifestError(
                    f"released plugin {plugin['id']} must be installable and beyond planned maturity"
                )
        for entry in [*manifest["mcp_resources"], *manifest["plugins"]]:
            missing = [
                field for field in (*PROVENANCE_FIELDS, "license_sha256")
                if not entry["provenance"].get(field)
            ]
            if missing:
                raise FamilyManifestError(f"{entry['id']} lacks immutable provenance: {missing}")
        if source_roots is None:
            raise FamilyManifestError("release validation requires trusted source checkouts")
        for entry in [*manifest["mcp_resources"], *manifest["plugins"]]:
            verify_provenance(entry, source_roots)


def build_catalog(manifest: dict[str, Any], family_hash: str) -> dict[str, Any]:
    return {
        "schema_version": "intdata.family-catalog/v1",
        "release_id": manifest["release_id"],
        "revision": manifest["revision"],
        "generated_at": manifest["generated_at"],
        "family_hash": family_hash,
        "mcp_resources": manifest["mcp_resources"],
        "plugins": manifest["plugins"],
    }


def build_marketplace(manifest: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for plugin in sorted(manifest["plugins"], key=lambda item: item["id"]):
        provenance = plugin["provenance"]
        entries.append(
            {
                "name": plugin["id"],
                "source": {
                    "source": "git-subdir",
                    "url": provenance["repository"],
                    "path": f"./{provenance['subdir']}",
                    "ref": provenance["commit"],
                },
                "policy": {
                    "installation": "INSTALLED_BY_DEFAULT",
                    "authentication": (
                        "ON_USE" if plugin["install_access"] == "public" else "ON_INSTALL"
                    ),
                },
                "category": plugin["category"],
            }
        )
    return {
        "name": manifest["marketplace"]["id"],
        "interface": {"displayName": manifest["marketplace"]["display_name"]},
        "plugins": entries,
    }


def build_outputs(
    manifest: dict[str, Any],
    schema: dict[str, Any] | None = None,
    *,
    source_roots: dict[str, Path] | None = None,
) -> dict[str, bytes]:
    canonical_schema = load_json(DEFAULT_SCHEMA)
    if schema is not None and canonical_bytes(schema) != canonical_bytes(canonical_schema):
        raise FamilyManifestError("release generation requires the canonical family Schema")
    schema = canonical_schema
    validate_manifest(
        manifest,
        schema,
        require_release=True,
        source_roots=source_roots,
    )
    normalized = normalized_manifest(manifest)
    manifest_bytes = canonical_bytes(normalized)
    family_hash = sha256_bytes(manifest_bytes)
    catalog = build_catalog(normalized, family_hash)
    validate_projection(catalog, schema, "family_catalog")
    catalog_bytes = canonical_bytes(catalog)
    catalog_schema_bytes = canonical_bytes(
        projection_schema(
            schema,
            "family_catalog",
            schema_id="https://intdata.pro/schemas/intdata-family-catalog-v1.json",
            title="intData family catalog v1",
        )
    )
    marketplace_bytes = canonical_bytes(build_marketplace(normalized))
    lock = {
        "schema_version": "intdata.family-release-lock/v1",
        "release_id": normalized["release_id"],
        "revision": normalized["revision"],
        "generated_at": normalized["generated_at"],
        "family_hash": family_hash,
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "catalog_sha256": sha256_bytes(catalog_bytes),
        "catalog_schema_sha256": sha256_bytes(catalog_schema_bytes),
        "marketplace_sha256": sha256_bytes(marketplace_bytes),
        "mcp_resources": [
            {"id": item["id"], "version": item["release_version"], **item["provenance"]}
            for item in normalized["mcp_resources"]
        ],
        "plugins": [
            {"id": item["id"], "version": item["release_version"], **item["provenance"]}
            for item in normalized["plugins"]
        ],
    }
    lock_bytes = canonical_bytes(lock)
    activation = {
        "schema_version": "intdata.family-activation/v1",
        "release_id": normalized["release_id"],
        "revision": normalized["revision"],
        "generated_at": normalized["generated_at"],
        "family_hash": family_hash,
        "projections": {
            "catalog": {"path": CATALOG_FILENAME, "sha256": sha256_bytes(catalog_bytes)},
            "catalog_schema": {
                "path": CATALOG_SCHEMA_FILENAME,
                "sha256": sha256_bytes(catalog_schema_bytes),
            },
            "release_lock": {"path": LOCK_FILENAME, "sha256": sha256_bytes(lock_bytes)},
            "marketplace": {
                "path": MARKETPLACE_FILENAME,
                "sha256": sha256_bytes(marketplace_bytes),
            },
        },
    }
    validate_projection(activation, schema, "family_activation")
    return {
        CATALOG_FILENAME: catalog_bytes,
        CATALOG_SCHEMA_FILENAME: catalog_schema_bytes,
        MARKETPLACE_FILENAME: marketplace_bytes,
        LOCK_FILENAME: lock_bytes,
        ACTIVATION_FILENAME: canonical_bytes(activation),
    }


def write_outputs(output_dir: Path, outputs: dict[str, bytes], *, check: bool) -> None:
    assert_safe_output_dir(output_dir)
    if not check:
        output_dir.mkdir(parents=True, exist_ok=True)
    failures = []
    for name, expected in outputs.items():
        path = output_dir / name
        if check:
            if path.is_symlink():
                raise FamilyManifestError(f"refusing unsafe output path: {path}")
            if not path.exists() or path.read_bytes() != expected:
                failures.append(name)
        else:
            if path.is_symlink():
                raise FamilyManifestError(f"refusing unsafe output path: {path}")
            temporary: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=output_dir,
                    prefix=f".{name}.",
                    suffix=".tmp",
                    delete=False,
                ) as stream:
                    temporary = Path(stream.name)
                    stream.write(expected)
                    stream.flush()
                    os.fsync(stream.fileno())
                temporary.chmod(0o644)
                if path.is_symlink():
                    raise FamilyManifestError(f"refusing unsafe output path: {path}")
                os.replace(temporary, path)
                temporary = None
            except OSError as exc:
                raise FamilyManifestError(f"failed writing generated projection {path}: {exc}") from exc
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
    if failures:
        raise FamilyManifestError(f"generated projections differ: {', '.join(failures)}")


def assert_safe_output_dir(output_dir: Path) -> None:
    resolved = output_dir.expanduser().resolve(strict=False)
    protected = {Path.home().joinpath(".codex").resolve(strict=False)}
    if value := os.environ.get("CODEX_HOME"):
        protected.add(Path(value).expanduser().resolve(strict=False))
    for root in protected:
        if resolved == root or root in resolved.parents:
            raise FamilyManifestError(f"output directory is inside Codex-owned state: {root}")


def parse_source_roots(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        repository, separator, path = value.partition("=")
        if not separator or not repository or not path:
            raise FamilyManifestError("--source-repo must use REPOSITORY=PATH")
        if repository in result:
            raise FamilyManifestError(f"duplicate --source-repo for {repository}")
        result[repository] = Path(path)
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Validate and generate intData family projections")
    result.add_argument("command", choices=("validate", "generate", "check"))
    result.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    result.add_argument("--output-dir", type=Path)
    result.add_argument("--source-repo", action="append", default=[], metavar="REPOSITORY=PATH")
    return result


def main() -> int:
    args = parser().parse_args()
    manifest = load_json(args.manifest)
    schema = load_json(DEFAULT_SCHEMA)
    require_release = args.command in {"generate", "check"}
    source_roots = parse_source_roots(args.source_repo)
    validate_manifest(
        manifest,
        schema,
        require_release=require_release,
        source_roots=source_roots or None,
    )
    if args.command == "validate":
        print(json.dumps({"ok": True, "release_state": manifest["release_state"]}, sort_keys=True))
        return 0
    if args.output_dir is None:
        raise FamilyManifestError("--output-dir is required for generate/check")
    assert_safe_output_dir(args.output_dir)
    write_outputs(
        args.output_dir,
        build_outputs(manifest, source_roots=source_roots or None),
        check=args.command == "check",
    )
    print(json.dumps({"ok": True, "output_dir": str(args.output_dir)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FamilyManifestError as exc:
        print(f"family manifest error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

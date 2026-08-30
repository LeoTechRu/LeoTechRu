from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "codex" / "scripts" / "generate_intdata_family.py"
MANIFEST = ROOT / "codex" / "family" / "intdata-family.json"
SCHEMA = ROOT / "codex" / "family" / "intdata-family.schema.json"
CHECKED_MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
LEGACY_MARKETPLACE = ROOT / ".codex" / "plugins" / "marketplace.json"

SPEC = importlib.util.spec_from_file_location("generate_intdata_family", SCRIPT)
assert SPEC and SPEC.loader
family = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(family)
sys.modules["generate_intdata_family"] = family

VERIFIER_SCRIPT = ROOT / "codex" / "scripts" / "verify_int_tools_plugins.py"
VERIFIER_SPEC = importlib.util.spec_from_file_location(
    "verify_int_tools_plugins", VERIFIER_SCRIPT
)
assert VERIFIER_SPEC and VERIFIER_SPEC.loader
plugin_verifier = importlib.util.module_from_spec(VERIFIER_SPEC)
VERIFIER_SPEC.loader.exec_module(plugin_verifier)


def load_inputs() -> tuple[dict, dict]:
    return family.load_json(MANIFEST), family.load_json(SCHEMA)


def test_intnode_marketplace_uses_public_tools_distribution() -> None:
    manifest, _schema = load_inputs()
    intnode = next(plugin for plugin in manifest["plugins"] if plugin["id"] == "intnode")
    entry = next(
        plugin for plugin in family.build_marketplace(manifest)["plugins"]
        if plugin["name"] == "intnode"
    )

    assert intnode["provenance"]["repository"] == "https://github.com/LeoTechPro/intData-node.git"
    assert entry["source"] == {
        "source": "git-subdir",
        "url": "https://github.com/LeoTechPro/Tools.git",
        "path": "./codex/plugins/intnode",
        "ref": "f548a8727546473005627ba8480b037db4c0d0cc",
    }
    assert entry["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_USE",
    }


def test_intnode_without_public_distribution_is_rejected() -> None:
    manifest, schema = load_inputs()
    intnode = next(plugin for plugin in manifest["plugins"] if plugin["id"] == "intnode")
    intnode.pop("distribution", None)

    with pytest.raises(family.FamilyManifestError, match="distribution"):
        family.validate_manifest(manifest, schema, require_release=False)


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture(autouse=True)
def advertise_test_repository_heads(monkeypatch: pytest.MonkeyPatch) -> None:
    def advertised_refs(repo: Path) -> tuple[tuple[str, str], ...]:
        return ((run_git(repo, "rev-parse", "HEAD"), "refs/heads/main"),)

    monkeypatch.setattr(family, "advertised_remote_refs", advertised_refs)


def test_run_git_forces_noninteractive_auth_and_isolated_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    class FakeJob:
        @classmethod
        def create(cls) -> "FakeJob":
            return cls()

        def assign_and_resume(self, _process: object) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeProcess:
        returncode = 0
        pid = 12345

        def __init__(self, command: list[str], **kwargs: object) -> None:
            captured["command"] = command
            captured["kwargs"] = kwargs

        def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
            captured["timeout"] = timeout
            return b"ok", b""

        def poll(self) -> int | None:
            return self.returncode

    monkeypatch.setenv("GIT_ASKPASS", "malicious-git-askpass")
    monkeypatch.setenv("SSH_ASKPASS", "malicious-ssh-askpass")
    monkeypatch.setenv("GCM_INTERACTIVE", "Always")
    monkeypatch.setenv("GIT_SSH_COMMAND", "ssh -o StrictHostKeyChecking=no")
    if family.IS_WINDOWS:
        monkeypatch.setattr(family, "WindowsKillOnCloseJob", FakeJob)
    monkeypatch.setattr(family.subprocess, "Popen", FakeProcess)

    assert family.run_git(tmp_path, "status") == b"ok"

    command = captured["command"]
    assert command[:5] == [
        "git",
        "-c",
        "credential.interactive=never",
        "-c",
        "core.askPass=",
    ]
    environment = captured["kwargs"]["env"]
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    assert environment["GCM_INTERACTIVE"] == "Never"
    assert environment["SSH_ASKPASS_REQUIRE"] == "never"
    assert "GIT_ASKPASS" not in environment
    assert "SSH_ASKPASS" not in environment
    assert "BatchMode=yes" in environment["GIT_SSH_COMMAND"]
    assert "StrictHostKeyChecking=yes" in environment["GIT_SSH_COMMAND"]
    if family.IS_WINDOWS:
        assert captured["kwargs"]["creationflags"] == (
            family.WINDOWS_CREATE_NEW_PROCESS_GROUP | family.WINDOWS_CREATE_SUSPENDED
        )
    else:
        assert captured["kwargs"]["start_new_session"] is True
    assert captured["timeout"] == family.GIT_TIMEOUT_SECONDS


def test_run_git_timeout_terminates_the_process_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    terminated: list[int] = []

    class FakeJob:
        @classmethod
        def create(cls) -> "FakeJob":
            return cls()

        def assign_and_resume(self, _process: object) -> None:
            pass

        def close(self) -> None:
            pass

    class TimedOutProcess:
        returncode = None
        pid = 54321
        calls = 0

        def __init__(self, _command: list[str], **_kwargs: object) -> None:
            pass

        def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired("git", timeout)
            self.returncode = -1
            return b"", b""

        def poll(self) -> int | None:
            return self.returncode

    if family.IS_WINDOWS:
        monkeypatch.setattr(family, "WindowsKillOnCloseJob", FakeJob)
    monkeypatch.setattr(family.subprocess, "Popen", TimedOutProcess)
    monkeypatch.setattr(
        family,
        "terminate_process_tree",
        lambda process, windows_job: terminated.append(process.pid),
    )

    with pytest.raises(family.FamilyManifestError, match="timed out"):
        family.run_git(tmp_path, "ls-remote", "origin")

    assert terminated == [54321]


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group regression")
def test_run_git_timeout_kills_descendant_after_parent_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_git = tmp_path / "git"
    fake_git.write_text("#!/bin/sh\nsleep 30 &\nexit 0\n", encoding="utf-8")
    fake_git.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(family, "GIT_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(family, "GIT_REAP_TIMEOUT_SECONDS", 1)

    started = time.monotonic()
    with pytest.raises(family.FamilyManifestError, match="timed out"):
        family.run_git(tmp_path, "status")

    assert time.monotonic() - started < 2


def test_run_git_windows_assigns_job_before_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    class FakeJob:
        @classmethod
        def create(cls) -> "FakeJob":
            events.append("job-created")
            return cls()

        def assign_and_resume(self, _process: object) -> None:
            events.append("job-assigned-and-resumed")

        def close(self) -> None:
            events.append("job-closed")

    class FakeProcess:
        returncode = 0
        pid = 12345
        stdout = None
        stderr = None

        def __init__(self, _command: list[str], **kwargs: object) -> None:
            events.append("process-created-suspended")
            assert kwargs["creationflags"] == (
                family.WINDOWS_CREATE_NEW_PROCESS_GROUP
                | family.WINDOWS_CREATE_SUSPENDED
            )

        def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
            events.append("communicated")
            return b"ok", b""

    monkeypatch.setattr(family, "IS_WINDOWS", True)
    monkeypatch.setattr(family, "WindowsKillOnCloseJob", FakeJob)
    monkeypatch.setattr(family.subprocess, "Popen", FakeProcess)

    assert family.run_git(tmp_path, "status") == b"ok"
    assert events == [
        "job-created",
        "process-created-suspended",
        "job-assigned-and-resumed",
        "communicated",
        "job-closed",
    ]


def test_run_git_windows_job_setup_failure_kills_suspended_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    class FakeJob:
        @classmethod
        def create(cls) -> "FakeJob":
            return cls()

        def assign_and_resume(self, _process: object) -> None:
            raise OSError("assignment failed")

        def close(self) -> None:
            events.append("job-closed")

    class FakeProcess:
        returncode = None
        pid = 54321
        stdout = None
        stderr = None

        def __init__(self, _command: list[str], **_kwargs: object) -> None:
            pass

        def kill(self) -> None:
            events.append("process-killed")
            self.returncode = -1

        def communicate(self, timeout: float | None = None) -> tuple[bytes, bytes]:
            events.append(f"reaped:{timeout}")
            return b"", b""

    monkeypatch.setattr(family, "IS_WINDOWS", True)
    monkeypatch.setattr(family, "WindowsKillOnCloseJob", FakeJob)
    monkeypatch.setattr(family.subprocess, "Popen", FakeProcess)

    with pytest.raises(family.FamilyManifestError, match="contain and resume"):
        family.run_git(tmp_path, "status")

    assert events == [
        "job-closed",
        "process-killed",
        f"reaped:{family.GIT_REAP_TIMEOUT_SECONDS}",
    ]


def materialized_release(tmp_path: Path) -> tuple[dict, dict, dict[str, Path]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    manifest, schema = load_inputs()
    release = copy.deepcopy(manifest)
    release["release_state"] = "released"
    release["release_id"] = "intdata-family-2026.08.05.1"
    for plugin in release["plugins"]:
        plugin["maturity"] = "dev"
        plugin["availability"] = "available"
    entries = [*release["mcp_resources"], *release["plugins"]]
    repositories = sorted({entry["provenance"]["repository"] for entry in entries})
    source_roots: dict[str, Path] = {}
    for index, repository in enumerate(repositories):
        repo = tmp_path / f"source-{index}"
        repo.mkdir()
        run_git(repo, "init", "-q")
        run_git(repo, "config", "user.name", "intData tests")
        run_git(repo, "config", "user.email", "tests@intdata.pro")
        run_git(repo, "remote", "add", "origin", repository)
        for entry in entries:
            provenance = entry["provenance"]
            if provenance["repository"] != repository:
                continue
            license_path = repo / provenance["license_path"]
            license_path.parent.mkdir(parents=True, exist_ok=True)
            license_fixtures = {
                "Proprietary": family.APPROVED_PROPRIETARY_RESOURCE_LICENSE.decode("utf-8"),
                "MIT": "MIT License\nPermission is hereby granted, free of charge.\n",
                "Apache-2.0": "Apache License\nVersion 2.0\n",
            }
            license_path.write_text(
                license_fixtures[provenance["license"]], encoding="utf-8"
            )
            manifest_path = repo / provenance["manifest_path"]
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            if entry["id"] in family.EXPECTED_SKILLS:
                source_manifest = {
                    "name": entry["id"],
                    "version": entry["release_version"],
                    "license": provenance["license"],
                    "skills": "./skills",
                    "interface": {
                        "displayName": entry["display_name"],
                        "category": entry["category"],
                    },
                }
                for skill in entry["skills"]:
                    skill_path = manifest_path.parents[1] / "skills" / skill / "SKILL.md"
                    skill_path.parent.mkdir(parents=True, exist_ok=True)
                    skill_path.write_text(
                        f"---\nname: {skill}\ndescription: Test fixture.\n---\n\n# {skill}\n",
                        encoding="utf-8",
                    )
            else:
                source_manifest = {
                    key: copy.deepcopy(value)
                    for key, value in entry.items()
                    if key != "provenance"
                }
                source_manifest["license"] = provenance["license"]
            manifest_path.write_text(json.dumps(source_manifest) + "\n", encoding="utf-8")
        run_git(repo, "add", ".")
        run_git(repo, "commit", "-q", "-m", "test fixture")
        source_roots[repository] = repo

    for entry in entries:
        provenance = entry["provenance"]
        repo = source_roots[provenance["repository"]]
        commit = run_git(repo, "rev-parse", "HEAD")
        provenance["commit"] = commit
        provenance["tree_sha256"] = family.tree_digest(repo, commit, provenance["subdir"])
        provenance["manifest_sha256"] = family.sha256_bytes(
            family.blob_bytes(repo, commit, provenance["manifest_path"])
        )
        provenance["license_sha256"] = family.sha256_bytes(
            family.blob_bytes(repo, commit, provenance["license_path"])
        )
    source_roots[family.PUBLIC_DISTRIBUTION_REPOSITORY] = ROOT
    return release, schema, source_roots


def commit_and_rebind(entry: dict, repo: Path) -> None:
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-q", "-m", "mutate fixture")
    provenance = entry["provenance"]
    commit = run_git(repo, "rev-parse", "HEAD")
    provenance["commit"] = commit
    provenance["tree_sha256"] = family.tree_digest(repo, commit, provenance["subdir"])
    provenance["manifest_sha256"] = family.sha256_bytes(
        family.blob_bytes(repo, commit, provenance["manifest_path"])
    )
    provenance["license_sha256"] = family.sha256_bytes(
        family.blob_bytes(repo, commit, provenance["license_path"])
    )


def test_checked_in_candidate_is_schema_valid_but_not_releasable() -> None:
    manifest, schema = load_inputs()
    family.validate_manifest(manifest, schema, require_release=False)

    with pytest.raises(family.FamilyManifestError, match="release_state=released"):
        family.validate_manifest(manifest, schema, require_release=True)

    with pytest.raises(family.FamilyManifestError, match="release_state=released"):
        family.build_outputs(manifest)


def test_checked_in_marketplace_is_exact_family_projection() -> None:
    manifest, _ = load_inputs()
    marketplace = family.load_json(CHECKED_MARKETPLACE)

    assert marketplace == family.build_marketplace(manifest)
    assert [entry["name"] for entry in marketplace["plugins"]] == ["intnode"]
    assert {
        entry["name"]: entry["policy"]["installation"]
        for entry in marketplace["plugins"]
    } == {
        "intnode": "AVAILABLE",
    }
    assert {
        entry["name"]: entry["source"]["url"]
        for entry in marketplace["plugins"]
    } == {
        "intnode": "https://github.com/LeoTechPro/Tools.git",
    }
    assert not LEGACY_MARKETPLACE.exists()


def test_resource_repository_identities_match_current_owning_repositories() -> None:
    manifest, _ = load_inputs()
    repositories = {
        entry["id"]: entry["provenance"]["repository"]
        for entry in manifest["mcp_resources"]
    }

    assert repositories["brain"] == "https://github.com/LeoTechPro/intData-brain.git"
    assert repositories["crm"] == "https://github.com/LeoTechPro/intData-CRM.git"
    assert repositories["cms"] == "https://github.com/LeoTechPro/intData-CMS.git"
    assert repositories["lms"] == "https://github.com/LeoTechPro/intData-LMS.git"
    assert repositories == family.EXPECTED_RESOURCE_REPOSITORIES


def test_resource_licenses_match_current_owning_repository_licenses() -> None:
    manifest, _ = load_inputs()
    licenses = {
        entry["id"]: entry["provenance"]["license"]
        for entry in manifest["mcp_resources"]
    }

    assert licenses["agent"] == "MIT"
    assert licenses["platform"] == "Apache-2.0"


def test_resource_license_paths_are_scoped_without_relicensing_repositories() -> None:
    manifest, _ = load_inputs()
    license_paths = {
        entry["id"]: entry["provenance"]["license_path"]
        for entry in manifest["mcp_resources"]
    }

    assert license_paths["agent"] == "LICENSE"
    assert license_paths["platform"] == "LICENSE"
    assert {
        resource_id: path
        for resource_id, path in license_paths.items()
        if resource_id not in {"agent", "platform"}
    } == {
        resource_id: "mcp/resources/LICENSE"
        for resource_id in {"brain", "probe", "punkt-b", "crm", "cms", "lms"}
    }


def test_intdev_is_retired_and_absent_from_the_family() -> None:
    manifest, _ = load_inputs()

    assert "intdev" in family.LEGACY_PLUGIN_IDS
    assert "intdev" not in {entry["id"] for entry in manifest["plugins"]}


def test_public_family_contains_only_intnode() -> None:
    manifest, schema = load_inputs()
    family.validate_manifest(manifest, schema, require_release=False)
    assert [entry["id"] for entry in manifest["plugins"]] == ["intnode"]
    assert manifest["plugins"][0]["skills"] == ["coord"]
    assert manifest["marketplace"] == {
        "id": "inttools",
        "display_name": "intData Tools",
        "repository": "https://github.com/LeoTechPro/Tools.git",
    }


def test_release_builder_rejects_schema_override_and_unverified_sources(tmp_path: Path) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    alternate_schema = copy.deepcopy(schema)
    alternate_schema["title"] = "Untrusted alternate Schema"

    with pytest.raises(family.FamilyManifestError, match="canonical family Schema"):
        family.build_outputs(
            release,
            alternate_schema,
            source_roots=source_roots,
        )
    with pytest.raises(family.FamilyManifestError, match="trusted source checkouts"):
        family.build_outputs(release)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("display_name", "intData Probe"),
        ("owner", "intData Probe"),
    ],
)
def test_probe_resource_identity_cannot_restore_legacy_brand(field: str, value: str) -> None:
    manifest, schema = load_inputs()
    probe = next(item for item in manifest["mcp_resources"] if item["id"] == "probe")
    probe[field] = value
    with pytest.raises(family.FamilyManifestError):
        family.validate_manifest(manifest, schema, require_release=False)


def test_probe_resource_repository_is_bridge_owned() -> None:
    manifest, schema = load_inputs()
    probe = next(item for item in manifest["mcp_resources"] if item["id"] == "probe")
    probe["provenance"]["repository"] = "https://github.com/LeoTechPro/intProbe-server.git"
    with pytest.raises(family.FamilyManifestError):
        family.validate_manifest(manifest, schema, require_release=False)


def test_probe_failure_policy_is_route_local_and_os_aware() -> None:
    manifest, _ = load_inputs()
    assert manifest["routing_policy"] == {
        "probe_failure_scope": "probe-route-only",
        "alternative_routes": "independently-authorized",
        "probe_mutations": "fail-closed",
        "os_aware": True,
    }


def test_agent_resource_is_owner_only_and_audience_isolated() -> None:
    manifest, _ = load_inputs()
    resources = {entry["id"]: entry for entry in manifest["mcp_resources"]}
    assert resources["agent"]["runtime_access"] == "owner-only"
    assert resources["agent"]["oauth_resource"] == "https://intdata.pro/mcp/agent"
    assert resources["agent"]["scopes"] == ["agent.read", "agent.mutate", "agent.admin"]
    assert len({resources[name]["oauth_resource"] for name in ("agent", "brain", "probe")}) == 3


def test_release_outputs_are_deterministic_and_bound_by_one_hash(tmp_path: Path) -> None:
    release, schema, source_roots = materialized_release(tmp_path / "sources")
    family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)

    first = family.build_outputs(release, source_roots=source_roots)
    second = family.build_outputs(copy.deepcopy(release), source_roots=source_roots)
    assert first == second

    output_dir = tmp_path / "release"
    family.write_outputs(output_dir, first, check=False)
    family.write_outputs(output_dir, second, check=True)
    assert all(path.stat().st_mode & 0o444 == 0o444 for path in output_dir.iterdir())

    catalog = json.loads(first["intdata.family-catalog.v1.json"])
    lock = json.loads(first["intdata.family-release-lock.v1.json"])
    marketplace = json.loads(first["marketplace.json"])
    activation = json.loads(first["intdata.family-activation.v1.json"])
    assert catalog["family_hash"] == lock["family_hash"]
    assert lock["marketplace_sha256"] == family.sha256_bytes(first["marketplace.json"])
    assert lock["catalog_schema_sha256"] == family.sha256_bytes(
        first["intdata.family-catalog.v1.schema.json"]
    )
    assert activation["family_hash"] == catalog["family_hash"]
    assert activation["release_id"] == catalog["release_id"] == lock["release_id"]
    assert activation["revision"] == catalog["revision"] == lock["revision"]
    assert activation["projections"]["catalog"]["sha256"] == family.sha256_bytes(
        first["intdata.family-catalog.v1.json"]
    )
    assert activation["projections"]["release_lock"]["sha256"] == family.sha256_bytes(
        first["intdata.family-release-lock.v1.json"]
    )
    assert marketplace["name"] == "inttools"
    assert [entry["name"] for entry in marketplace["plugins"]] == ["intnode"]
    assert all(len(entry["source"]["ref"]) == 40 for entry in marketplace["plugins"])
    assert all(entry["source"]["source"] == "git-subdir" for entry in marketplace["plugins"])
    assert all(
        entry["policy"]["installation"] == "INSTALLED_BY_DEFAULT"
        for entry in marketplace["plugins"]
    )
    authentication = {
        entry["name"]: entry["policy"]["authentication"]
        for entry in marketplace["plugins"]
    }
    assert authentication == {
        "intnode": "ON_USE",
    }
    locked_intnode = next(entry for entry in lock["plugins"] if entry["id"] == "intnode")
    manifest_intnode = next(entry for entry in release["plugins"] if entry["id"] == "intnode")
    assert locked_intnode["repository"] == manifest_intnode["provenance"]["repository"]
    assert locked_intnode["distribution"] == manifest_intnode["distribution"]


def test_generated_at_is_an_immutable_hash_input(tmp_path: Path) -> None:
    release, _, source_roots = materialized_release(tmp_path)
    original = json.loads(family.build_outputs(release, source_roots=source_roots)["intdata.family-catalog.v1.json"])["family_hash"]
    changed = copy.deepcopy(release)
    changed["generated_at"] = "2026-08-05T20:00:01Z"
    updated = json.loads(family.build_outputs(changed, source_roots=source_roots)["intdata.family-catalog.v1.json"])["family_hash"]
    assert updated != original


def test_wrong_skill_owner_and_missing_provenance_fail_closed(tmp_path: Path) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    release["plugins"][0]["skills"].append("private-skill")
    with pytest.raises(family.FamilyManifestError, match="skill mapping|plugins/0/skills"):
        family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)

    release, schema, source_roots = materialized_release(tmp_path / "second")
    release["plugins"][0]["provenance"]["commit"] = None
    with pytest.raises(family.FamilyManifestError, match="immutable provenance"):
        family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)


def test_check_detects_projection_drift(tmp_path: Path) -> None:
    release, schema, source_roots = materialized_release(tmp_path / "sources")
    family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)
    outputs = family.build_outputs(release, source_roots=source_roots)
    output_dir = tmp_path / "release"
    family.write_outputs(output_dir, outputs, check=False)
    (output_dir / "marketplace.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(family.FamilyManifestError, match="marketplace.json"):
        family.write_outputs(output_dir, outputs, check=True)


@pytest.mark.parametrize(
    "timestamp",
    ["2026-99-99T99:99:99Z", "2026-08-05T20:00:00+00:00", "2026-08-05T20:00Z"],
)
def test_generated_at_requires_real_canonical_utc(timestamp: str) -> None:
    manifest, schema = load_inputs()
    manifest["generated_at"] = timestamp
    with pytest.raises(family.FamilyManifestError, match="generated_at"):
        family.validate_manifest(manifest, schema, require_release=False)


def test_schema_override_is_not_a_cli_surface(tmp_path: Path) -> None:
    fake_schema = tmp_path / "schema.json"
    fake_schema.write_text("{}\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "validate", "--schema", str(fake_schema)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert result.returncode != 0
    assert "unrecognized arguments: --schema" in result.stderr


def test_duplicate_json_keys_fail_closed(tmp_path: Path) -> None:
    manifest = tmp_path / "duplicate.json"
    manifest.write_text('{"schema_version":"one","schema_version":"two"}\n', encoding="utf-8")
    with pytest.raises(family.FamilyManifestError, match="duplicate JSON object key"):
        family.load_json(manifest)


def test_plugin_verifier_strictly_rejects_duplicate_marketplace_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marketplace_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    marketplace_path.parent.mkdir(parents=True)
    duplicate = CHECKED_MARKETPLACE.read_text(encoding="utf-8").replace(
        '  "name": "inttools",',
        '  "name": "inttools",\n  "name": "inttools",',
        1,
    )
    marketplace_path.write_text(duplicate, encoding="utf-8")
    monkeypatch.setattr(plugin_verifier, "ROOT", tmp_path)
    report: dict = {"manifest_errors": []}

    plugin_verifier.verify_manifests(report)

    assert any(
        "duplicate JSON object key" in str(error)
        for error in report["manifest_errors"]
    )


def test_schema_rejects_duplicate_public_plugin() -> None:
    manifest, schema = load_inputs()
    duplicate = copy.deepcopy(manifest)
    duplicate["plugins"].append(copy.deepcopy(duplicate["plugins"][0]))
    duplicate_errors = list(family.jsonschema.Draft202012Validator(schema).iter_errors(duplicate))
    assert any(list(error.absolute_path) == ["plugins"] for error in duplicate_errors)



def test_schema_requires_exact_canonical_resource_ids() -> None:
    manifest, schema = load_inputs()
    validator = family.jsonschema.Draft202012Validator(schema)

    missing = copy.deepcopy(manifest)
    missing["mcp_resources"].pop()
    assert any(
        list(error.absolute_path) == ["mcp_resources"]
        for error in validator.iter_errors(missing)
    )

    duplicate = copy.deepcopy(manifest)
    duplicate["mcp_resources"][-1] = copy.deepcopy(duplicate["mcp_resources"][0])
    assert any(
        list(error.absolute_path) == ["mcp_resources"]
        for error in validator.iter_errors(duplicate)
    )


def test_catalog_schema_requires_exact_canonical_resource_ids() -> None:
    manifest, schema = load_inputs()
    catalog = family.build_catalog(manifest, "0" * 64)
    missing = copy.deepcopy(catalog)
    missing["mcp_resources"].pop()
    duplicate = copy.deepcopy(catalog)
    duplicate["mcp_resources"][-1] = copy.deepcopy(duplicate["mcp_resources"][0])
    wrong = copy.deepcopy(catalog)
    wrong["mcp_resources"][0]["id"] = "unknown"
    validator = family.jsonschema.Draft202012Validator(
        family.projection_schema(
            schema,
            "family_catalog",
            schema_id="https://intdata.pro/schemas/test-catalog-resources.json",
            title="test",
        )
    )

    for candidate in (missing, duplicate, wrong):
        assert list(validator.iter_errors(candidate))


def test_activation_schema_rejects_projection_path_permutation() -> None:
    manifest, schema = load_inputs()
    activation = {
        "schema_version": "intdata.family-activation/v1",
        "release_id": manifest["release_id"],
        "revision": manifest["revision"],
        "generated_at": manifest["generated_at"],
        "family_hash": "0" * 64,
        "projections": {
            "catalog": {"path": "marketplace.json", "sha256": "0" * 64},
            "catalog_schema": {"path": "intdata.family-catalog.v1.schema.json", "sha256": "0" * 64},
            "release_lock": {"path": "intdata.family-release-lock.v1.json", "sha256": "0" * 64},
            "marketplace": {"path": "intdata.family-catalog.v1.json", "sha256": "0" * 64},
        },
    }
    errors = list(
        family.jsonschema.Draft202012Validator(
            family.projection_schema(
                schema,
                "family_activation",
                schema_id="https://intdata.pro/schemas/test-activation.json",
                title="test",
            )
        ).iter_errors(activation)
    )
    assert errors


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value["plugins"].append(copy.deepcopy(value["plugins"][0])), "plugin IDs|plugins"),
        (lambda value: value["plugins"][0].__setitem__("aliases", ["dba"]), "Additional properties"),
        (lambda value: value["plugins"][0]["provenance"].__setitem__("repository", "file:///tmp/local"), "does not match"),
        (lambda value: value["plugins"][0]["provenance"].__setitem__("commit", "main"), "not valid"),
        (lambda value: value["plugins"][0]["provenance"].__setitem__("subdir", "../../outside"), "contained repository-relative"),
    ],
)
def test_release_identity_and_source_shape_fail_closed(
    tmp_path: Path, mutation, message: str
) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    mutation(release)
    with pytest.raises(family.FamilyManifestError, match=message):
        family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)


def test_agent_brain_probe_audiences_and_metadata_cannot_collapse() -> None:
    manifest, schema = load_inputs()
    resources = {item["id"]: item for item in manifest["mcp_resources"]}
    resources["brain"]["endpoint"] = resources["agent"]["endpoint"]
    resources["brain"]["oauth_resource"] = resources["agent"]["oauth_resource"]
    resources["agent"]["metadata_uri"] = resources["probe"]["metadata_uri"]
    with pytest.raises(family.FamilyManifestError, match="exact contract|metadata URI"):
        family.validate_manifest(manifest, schema, require_release=False)


def test_unconfigured_authorization_is_dark_and_never_forwards_bearer() -> None:
    manifest, schema = load_inputs()
    for resource in manifest["mcp_resources"]:
        assert resource["availability"] == "unavailable"
        assert resource["authorization"] == {
            "state": "unconfigured",
            "audience": resource["oauth_resource"],
            "external_bearer_forwarding": False,
            "downstream_credential": "none",
        }

    changed = copy.deepcopy(manifest)
    changed["mcp_resources"][0]["availability"] = "available"
    with pytest.raises(family.FamilyManifestError, match="unconfigured authorization"):
        family.validate_manifest(changed, schema, require_release=False)


def test_released_plugins_must_be_installable_and_beyond_planned_maturity() -> None:
    manifest, schema = load_inputs()
    release = copy.deepcopy(manifest)
    release["release_state"] = "released"
    release["plugins"][0]["maturity"] = "planned"

    with pytest.raises(family.FamilyManifestError, match="must be installable"):
        family.validate_manifest(release, schema, require_release=True)


def test_scoped_proprietary_resource_requires_exact_owner_approved_carrier(
    tmp_path: Path,
) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    brain = next(entry for entry in release["mcp_resources"] if entry["id"] == "brain")
    repo = source_roots[brain["provenance"]["repository"]]
    (repo / brain["provenance"]["license_path"]).write_text(
        "Different proprietary terms. All rights reserved.\n",
        encoding="utf-8",
    )
    commit_and_rebind(brain, repo)

    with pytest.raises(family.FamilyManifestError, match="exact owner-approved carrier"):
        family.validate_manifest(
            release,
            schema,
            require_release=True,
            source_roots=source_roots,
        )


def test_activation_record_has_exact_projection_paths_and_hashes(tmp_path: Path) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)
    outputs = family.build_outputs(release, schema, source_roots=source_roots)
    activation = json.loads(outputs[family.ACTIVATION_FILENAME])

    expected_paths = {
        "catalog": family.CATALOG_FILENAME,
        "catalog_schema": family.CATALOG_SCHEMA_FILENAME,
        "release_lock": family.LOCK_FILENAME,
        "marketplace": family.MARKETPLACE_FILENAME,
    }
    assert {
        name: projection["path"]
        for name, projection in activation["projections"].items()
    } == expected_paths
    for name, path in expected_paths.items():
        assert activation["projections"][name]["sha256"] == family.sha256_bytes(outputs[path])

    activation["projections"]["catalog"]["path"] = "previous/catalog.json"
    with pytest.raises(family.FamilyManifestError, match="generated family_activation"):
        family.validate_projection(activation, schema, "family_activation")


def test_release_provenance_requires_real_commit_and_matching_digests(tmp_path: Path) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    target = release["plugins"][0]["provenance"]
    target["commit"] = "f" * 40
    with pytest.raises(family.FamilyManifestError, match="cat-file"):
        family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)

    release, schema, source_roots = materialized_release(tmp_path / "digest")
    for field in ("tree_sha256", "manifest_sha256", "license_sha256"):
        changed = copy.deepcopy(release)
        changed["plugins"][0]["provenance"][field] = "0" * 64
        with pytest.raises(family.FamilyManifestError, match=field):
            family.validate_manifest(
                changed, schema, require_release=True, source_roots=source_roots
            )


def test_output_dir_cannot_enter_codex_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    codex_home = tmp_path / "codex-owned"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    with pytest.raises(family.FamilyManifestError, match="Codex-owned"):
        family.assert_safe_output_dir(codex_home / "plugins")


def test_output_file_symlink_into_codex_home_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    codex_home = tmp_path / "codex-owned"
    codex_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    output_dir = tmp_path / "release"
    output_dir.mkdir()
    protected = codex_home / "marketplace.json"
    protected.write_bytes(b"protected\n")
    (output_dir / "marketplace.json").symlink_to(protected)

    with pytest.raises(family.FamilyManifestError, match="unsafe output path"):
        family.write_outputs(output_dir, {"marketplace.json": b"overwrite\n"}, check=False)
    assert protected.read_bytes() == b"protected\n"


def test_release_lock_binds_resource_versions(tmp_path: Path) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)
    lock = json.loads(family.build_outputs(release, source_roots=source_roots)["intdata.family-release-lock.v1.json"])
    assert all(item["version"] for item in lock["mcp_resources"])


def test_commit_bound_resource_contract_must_match_family(tmp_path: Path) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    crm = next(item for item in release["mcp_resources"] if item["id"] == "crm")
    repo = source_roots[crm["provenance"]["repository"]]
    path = repo / crm["provenance"]["manifest_path"]
    source = json.loads(path.read_text(encoding="utf-8"))
    source["oauth_resource"] = "https://intdata.pro/mcp/agent"
    path.write_text(json.dumps(source) + "\n", encoding="utf-8")
    commit_and_rebind(crm, repo)
    with pytest.raises(family.FamilyManifestError, match="source resource oauth_resource"):
        family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)


@pytest.mark.parametrize("field", ["display_name", "owner", "visibility", "maturity", "availability", "authorization"])
def test_commit_bound_resource_full_contract_must_match_family(
    tmp_path: Path, field: str
) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    crm = next(item for item in release["mcp_resources"] if item["id"] == "crm")
    repo = source_roots[crm["provenance"]["repository"]]
    path = repo / crm["provenance"]["manifest_path"]
    source = json.loads(path.read_text(encoding="utf-8"))
    source[field] = "tampered" if field != "authorization" else {"state": "tampered"}
    path.write_text(json.dumps(source) + "\n", encoding="utf-8")
    commit_and_rebind(crm, repo)
    with pytest.raises(family.FamilyManifestError, match=f"source resource {field}"):
        family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)


def intnode_snapshot_errors(root: Path, monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    monkeypatch.setattr(plugin_verifier, "ROOT", root)
    report: dict = {"intnode_snapshot_errors": []}
    plugin_verifier.verify_intnode_public_snapshot(report)
    return report["intnode_snapshot_errors"]


@pytest.fixture
def intnode_snapshot_root(tmp_path: Path) -> Path:
    target = tmp_path / "codex" / "plugins" / "intnode"
    shutil.copytree(ROOT / "codex" / "plugins" / "intnode", target)
    return tmp_path


def test_intnode_public_snapshot_is_exact_and_discoverable(
    intnode_snapshot_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert intnode_snapshot_errors(intnode_snapshot_root, monkeypatch) == []
    plugin_dir = intnode_snapshot_root / "codex" / "plugins" / "intnode"
    manifest = json.loads(
        (plugin_dir / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert manifest["license"] == "MIT"
    license_text = (plugin_dir / "LICENSE").read_text(encoding="utf-8")
    assert "Permission is hereby granted, free of charge" in license_text


@pytest.mark.parametrize(
    ("mutate", "error_key"),
    [
        (
            lambda root: (root / "codex" / "plugins" / "intnode" / "unexpected.txt").write_text(
                "extra\n", encoding="utf-8"
            ),
            "snapshot_files",
        ),
        (
            lambda root: (root / "codex" / "plugins" / "intnode" / "LICENSE").unlink(),
            "missing_snapshot_file",
        ),
        (
            lambda root: (root / "codex" / "plugins" / "intnode" / "LICENSE").write_text(
                "tampered\n", encoding="utf-8"
            ),
            "snapshot_digest",
        ),
        (
            lambda root: (root / "codex" / "plugins" / "intnode" / ".codex-plugin" / "plugin.json").write_text(
                '{"name":"wrong","skills":"./skills"}\n', encoding="utf-8"
            ),
            "manifest_name",
        ),
        (
            lambda root: (root / "codex" / "plugins" / "intnode" / ".codex-plugin" / "plugin.json").write_text(
                '{"name":"intnode","skills":"./wrong"}\n', encoding="utf-8"
            ),
            "manifest_skills",
        ),
        (
            lambda root: (root / "codex" / "plugins" / "intnode" / ".codex-plugin" / "plugin.json").write_text(
                (root / "codex" / "plugins" / "intnode" / ".codex-plugin" / "plugin.json")
                .read_text(encoding="utf-8")
                .replace('"license": "MIT"', '"license": "Proprietary"'),
                encoding="utf-8",
            ),
            "manifest_license",
        ),
        (
            lambda root: (root / "codex" / "plugins" / "intnode" / ".codex-plugin" / "plugin.json").write_text(
                '{"name":"intnode","skills":"./skills","mcpServers":{}}\n', encoding="utf-8"
            ),
            "forbidden_manifest_declaration",
        ),
        (
            lambda root: (root / "codex" / "plugins" / "intnode" / "skills" / "coord" / "SKILL.md").write_text(
                "---\nname: wrong\n---\n", encoding="utf-8"
            ),
            "skill_namespace",
        ),
        (
            lambda root: (root / "codex" / "plugins" / "intnode" / "skills" / "coord" / "SKILL.md").write_text(
                "---\nname: coord\n---\ncoordctl\n", encoding="utf-8"
            ),
            "forbidden_snapshot_content",
        ),
    ],
)
def test_intnode_public_snapshot_rejects_any_contract_deviation(
    intnode_snapshot_root: Path, monkeypatch: pytest.MonkeyPatch, mutate, error_key: str
) -> None:
    mutate(intnode_snapshot_root)
    errors = intnode_snapshot_errors(intnode_snapshot_root, monkeypatch)
    assert any(error_key in error for error in errors)

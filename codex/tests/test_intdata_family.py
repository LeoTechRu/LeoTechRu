from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "codex" / "scripts" / "generate_intdata_family.py"
MANIFEST = ROOT / "codex" / "family" / "intdata-family.json"
SCHEMA = ROOT / "codex" / "family" / "intdata-family.schema.json"

SPEC = importlib.util.spec_from_file_location("generate_intdata_family", SCRIPT)
assert SPEC and SPEC.loader
family = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(family)


def load_inputs() -> tuple[dict, dict]:
    return family.load_json(MANIFEST), family.load_json(SCHEMA)


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def materialized_release(tmp_path: Path) -> tuple[dict, dict, dict[str, Path]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    manifest, schema = load_inputs()
    release = copy.deepcopy(manifest)
    release["release_state"] = "released"
    release["release_id"] = "intdata-family-2026.08.05.1"
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
            license_path.write_text(
                "Proprietary test fixture. All rights reserved.\n", encoding="utf-8"
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
                    "id": entry["id"],
                    "release_version": entry["release_version"],
                    "endpoint": entry["endpoint"],
                    "metadata_uri": entry["metadata_uri"],
                    "runtime_access": entry["runtime_access"],
                    "oauth_resource": entry["oauth_resource"],
                    "scopes": entry["scopes"],
                    "license": provenance["license"],
                }
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


def test_canonical_family_membership_and_skill_map() -> None:
    manifest, schema = load_inputs()
    family.validate_manifest(manifest, schema, require_release=False)
    plugins = {entry["id"]: entry for entry in manifest["plugins"]}

    assert set(plugins) == {"intbridge", "intagent", "intdev"}
    assert [len(plugins[name]["skills"]) for name in ("intbridge", "intagent", "intdev")] == [10, 9, 10]
    assert plugins["intbridge"]["display_name"] == "intData Bridge"
    assert plugins["intbridge"]["owner"] == "intData Bridge"
    assert plugins["intbridge"]["runtime_access"] == "component-gated"
    assert plugins["intbridge"]["oauth_resource"] is None
    assert plugins["intbridge"]["components"] == [
        {
            "id": "probe",
            "display_name": "intData Bridge Probe",
            "skills": ["probe-operator", "fleet-diagnostics", "client-control", "incident-response", "probe-administration"],
            "runtime_access": "owner-only",
            "mcp_resource": "probe",
            "oauth_resource": "https://intdata.pro/mcp/probe",
            "scopes": [],
            "approval_policy": "probe-confirmation",
            "credential_boundary": "probe",
            "service_boundary": "probe",
            "state_boundary": "probe",
        },
        {
            "id": "dba",
            "display_name": "intData Bridge DBA",
            "skills": ["dba-health", "doctor-status", "local-smoke", "migrations", "sql-apply"],
            "runtime_access": "policy-gated",
            "mcp_resource": None,
            "oauth_resource": None,
            "scopes": [],
            "approval_policy": "route-specific",
            "credential_boundary": "dba",
            "service_boundary": "dba",
            "state_boundary": "dba",
        },
    ]
    assert plugins["intagent"]["components"] == []
    assert plugins["intdev"]["components"] == []
    assert "probe-operator" in plugins["intbridge"]["skills"]
    assert "intprobe-operator" not in plugins["intbridge"]["skills"]
    assert "dba" not in plugins
    resources = {entry["id"]: entry for entry in manifest["mcp_resources"]}
    assert set(resources) == family.EXPECTED_RESOURCE_IDS
    assert resources["probe"]["display_name"] == "intData Bridge Probe"
    assert resources["probe"]["owner"] == "intData Bridge"
    assert resources["probe"]["provenance"]["repository"] == "https://github.com/LeoTechPro/intData-bridge.git"


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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("oauth_resource", "https://intdata.pro/mcp/probe"),
        ("mcp_resource", "probe"),
        ("scopes", ["probe.admin"]),
        ("credential_boundary", "probe"),
        ("state_boundary", "probe"),
    ],
)
def test_intbridge_dba_component_cannot_cross_probe_boundary(field: str, value) -> None:
    manifest, schema = load_inputs()
    dba = next(item for item in manifest["plugins"] if item["id"] == "intbridge")["components"][1]
    dba[field] = value
    with pytest.raises(family.FamilyManifestError, match="component mapping|plugins/0/components/1"):
        family.validate_manifest(manifest, schema, require_release=False)


def test_intbridge_component_skill_reassignment_is_rejected_even_with_flat_union() -> None:
    manifest, schema = load_inputs()
    components = next(item for item in manifest["plugins"] if item["id"] == "intbridge")["components"]
    components[0]["skills"][0], components[1]["skills"][0] = components[1]["skills"][0], components[0]["skills"][0]
    assert sorted(skill for component in components for skill in component["skills"]) == sorted(
        next(item for item in manifest["plugins"] if item["id"] == "intbridge")["skills"]
    )
    with pytest.raises(family.FamilyManifestError, match="component mapping|components/0/skills"):
        family.validate_manifest(manifest, schema, require_release=False)


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
    assert marketplace["name"] == "intdata"
    assert [entry["name"] for entry in marketplace["plugins"]] == ["intagent", "intbridge", "intdev"]
    assert all(len(entry["source"]["ref"]) == 40 for entry in marketplace["plugins"])
    assert all(entry["source"]["source"] == "git-subdir" for entry in marketplace["plugins"])


def test_generated_at_is_an_immutable_hash_input(tmp_path: Path) -> None:
    release, _, source_roots = materialized_release(tmp_path)
    original = json.loads(family.build_outputs(release, source_roots=source_roots)["intdata.family-catalog.v1.json"])["family_hash"]
    changed = copy.deepcopy(release)
    changed["generated_at"] = "2026-08-05T20:00:01Z"
    updated = json.loads(family.build_outputs(changed, source_roots=source_roots)["intdata.family-catalog.v1.json"])["family_hash"]
    assert updated != original


def test_wrong_skill_owner_and_missing_provenance_fail_closed(tmp_path: Path) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    release["plugins"][0]["skills"] = list(reversed(release["plugins"][0]["skills"]))
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
        ["python3", str(SCRIPT), "validate", "--schema", str(fake_schema)],
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


def test_schema_rejects_duplicate_plugin_ids_and_nonempty_agent_components() -> None:
    manifest, schema = load_inputs()
    duplicate = copy.deepcopy(manifest)
    duplicate["plugins"][1] = copy.deepcopy(duplicate["plugins"][0])
    duplicate_errors = list(family.jsonschema.Draft202012Validator(schema).iter_errors(duplicate))
    assert any(list(error.absolute_path) == ["plugins"] for error in duplicate_errors)

    nonempty = copy.deepcopy(manifest)
    nonempty["plugins"][1]["components"] = [copy.deepcopy(nonempty["plugins"][0]["components"][0])]
    nonempty_errors = list(family.jsonschema.Draft202012Validator(schema).iter_errors(nonempty))
    assert any(
        list(error.absolute_path) == ["plugins", 1, "components"]
        for error in nonempty_errors
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["plugins"][0]["components"][1].__setitem__("mcp_resource", "probe"),
        lambda value: value["plugins"][0]["components"][1].__setitem__("runtime_access", "public"),
        lambda value: value["plugins"][0]["components"][0]["skills"].__setitem__(0, "dba-health"),
    ],
)
def test_schema_rejects_noncanonical_intbridge_component_mutations(mutation) -> None:
    manifest, schema = load_inputs()
    mutation(manifest)
    errors = list(family.jsonschema.Draft202012Validator(schema).iter_errors(manifest))
    assert errors


def test_catalog_schema_rejects_duplicate_intagent_plugin() -> None:
    manifest, schema = load_inputs()
    catalog = family.build_catalog(manifest, "0" * 64)
    intagent = next(item for item in catalog["plugins"] if item["id"] == "intagent")
    catalog["plugins"] = [copy.deepcopy(intagent) for _ in range(3)]
    errors = list(
        family.jsonschema.Draft202012Validator(
            family.projection_schema(
                schema,
                "family_catalog",
                schema_id="https://intdata.pro/schemas/test-catalog.json",
                title="test",
            )
        ).iter_errors(catalog)
    )
    assert errors


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


def test_probe_component_scopes_must_match_probe_resource() -> None:
    manifest, schema = load_inputs()
    probe = next(item for item in manifest["mcp_resources"] if item["id"] == "probe")
    probe["scopes"] = ["probe.read"]
    probe["availability"] = "available"
    probe["authorization"] = {
        "state": "configured",
        "audience": probe["oauth_resource"],
        "issuer": "https://issuer.intdata.pro",
        "verification": {"method": "jwks", "jwks_uri": "https://issuer.intdata.pro/.well-known/jwks.json"},
        "token_type": "jwt",
        "subject_claim": "sub",
        "entitlement_claim": "scope",
        "entitlement_max_age_seconds": 300,
        "external_bearer_forwarding": False,
        "downstream_credential": {
            "kind": "bounded-internal-assertion",
            "issuer": "intdata-family",
            "audience": "https://intdata.pro/internal/probe",
            "algorithm": "EdDSA",
            "key_id": "probe-dev",
            "ttl_seconds": 30,
        },
    }
    with pytest.raises(family.FamilyManifestError, match="probe component scopes"):
        family.validate_manifest(manifest, schema, require_release=False)
    manifest["plugins"][0]["components"][0]["scopes"] = ["probe.read"]
    family.validate_manifest(manifest, schema, require_release=False)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
            (lambda value: value["plugins"].__setitem__(1, copy.deepcopy(value["plugins"][0])), "plugin IDs|plugins"),
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


@pytest.mark.parametrize("display_name", [None, "Wrong Bridge"])
def test_commit_bound_plugin_display_name_must_match_family(
    tmp_path: Path, display_name: str | None
) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    intbridge = next(item for item in release["plugins"] if item["id"] == "intbridge")
    repo = source_roots[intbridge["provenance"]["repository"]]
    path = repo / intbridge["provenance"]["manifest_path"]
    source = json.loads(path.read_text(encoding="utf-8"))
    if display_name is None:
        source.pop("interface")
        expected = "interface is required"
    else:
        source["interface"]["displayName"] = display_name
        expected = "displayName differs"
    path.write_text(json.dumps(source) + "\n", encoding="utf-8")
    commit_and_rebind(intbridge, repo)
    with pytest.raises(family.FamilyManifestError, match=expected):
        family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)


@pytest.mark.parametrize(
    ("plugin_id", "field", "value"),
    [
        ("intbridge", "source_access", "public"),
        ("intbridge", "runtime_access", "public"),
        ("intagent", "install_access", "public"),
        ("intagent", "oauth_resource", "https://intdata.pro/mcp/probe"),
        ("intdev", "runtime_access", "public"),
        ("intdev", "oauth_resource", "https://intdata.pro/mcp/agent"),
    ],
)
def test_plugin_access_contracts_cannot_be_weakened(
    plugin_id: str, field: str, value
) -> None:
    manifest, schema = load_inputs()
    plugin = next(item for item in manifest["plugins"] if item["id"] == plugin_id)
    plugin[field] = value
    with pytest.raises(family.FamilyManifestError, match="access/OAuth contract"):
        family.validate_manifest(manifest, schema, require_release=False)


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


def test_arbitrary_source_manifest_and_license_paths_are_rejected(tmp_path: Path) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    intbridge = next(item for item in release["plugins"] if item["id"] == "intbridge")
    intbridge["provenance"]["manifest_path"] = "plugins/intbridge/skills/dba-health/SKILL.md"
    intbridge["provenance"]["license_path"] = "plugins/intbridge/skills/sql-apply/SKILL.md"
    with pytest.raises(family.FamilyManifestError, match="source manifest path|license path"):
        family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)


@pytest.mark.parametrize(
    ("field", "value"),
    [("name", "dba"), ("version", "9.9.9"), ("license", "MIT")],
)
def test_commit_bound_plugin_manifest_must_match_family(
    tmp_path: Path, field: str, value: str
) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    intbridge = next(item for item in release["plugins"] if item["id"] == "intbridge")
    repo = source_roots[intbridge["provenance"]["repository"]]
    path = repo / intbridge["provenance"]["manifest_path"]
    source = json.loads(path.read_text(encoding="utf-8"))
    source[field] = value
    path.write_text(json.dumps(source) + "\n", encoding="utf-8")
    commit_and_rebind(intbridge, repo)
    with pytest.raises(family.FamilyManifestError, match=f"source plugin {field}"):
        family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)


def test_commit_bound_plugin_skills_cannot_add_legacy_alias(tmp_path: Path) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    intbridge = next(item for item in release["plugins"] if item["id"] == "intbridge")
    repo = source_roots[intbridge["provenance"]["repository"]]
    alias = repo / "plugins" / "intbridge" / "skills" / "dba" / "SKILL.md"
    alias.parent.mkdir(parents=True)
    alias.write_text("---\nname: dba\ndescription: Legacy alias.\n---\n", encoding="utf-8")
    commit_and_rebind(intbridge, repo)
    with pytest.raises(family.FamilyManifestError, match="source plugin skills"):
        family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)


def test_commit_bound_plugin_manifest_cannot_declare_aliases(tmp_path: Path) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    intbridge = next(item for item in release["plugins"] if item["id"] == "intbridge")
    repo = source_roots[intbridge["provenance"]["repository"]]
    path = repo / intbridge["provenance"]["manifest_path"]
    source = json.loads(path.read_text(encoding="utf-8"))
    source["aliases"] = ["dba"]
    path.write_text(json.dumps(source) + "\n", encoding="utf-8")
    commit_and_rebind(intbridge, repo)
    with pytest.raises(family.FamilyManifestError, match="aliases are forbidden"):
        family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)


def test_noncanonical_nested_skill_entrypoint_is_rejected(tmp_path: Path) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    intbridge = next(item for item in release["plugins"] if item["id"] == "intbridge")
    repo = source_roots[intbridge["provenance"]["repository"]]
    nested = repo / "plugins" / "intbridge" / "skills" / "legacy" / "nested" / "SKILL.md"
    nested.parent.mkdir(parents=True)
    nested.write_text("---\nname: dba\ndescription: Legacy.\n---\n", encoding="utf-8")
    commit_and_rebind(intbridge, repo)
    with pytest.raises(family.FamilyManifestError, match="non-canonical skill entrypoint"):
        family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)


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


@pytest.mark.parametrize(
    "scopes",
    [None, ["*"], ["agent.admin", "agent.mutate", "agent.read"], ["probe.admin"]],
)
def test_commit_bound_agent_scopes_must_match_exactly(
    tmp_path: Path, scopes: list[str] | None
) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    agent = next(item for item in release["mcp_resources"] if item["id"] == "agent")
    repo = source_roots[agent["provenance"]["repository"]]
    path = repo / agent["provenance"]["manifest_path"]
    source = json.loads(path.read_text(encoding="utf-8"))
    if scopes is None:
        source.pop("scopes")
    else:
        source["scopes"] = scopes
    path.write_text(json.dumps(source) + "\n", encoding="utf-8")
    commit_and_rebind(agent, repo)
    intagent = next(item for item in release["plugins"] if item["id"] == "intagent")
    intagent["provenance"]["commit"] = agent["provenance"]["commit"]
    intagent["provenance"]["tree_sha256"] = family.tree_digest(
        repo, agent["provenance"]["commit"], intagent["provenance"]["subdir"]
    )
    with pytest.raises(family.FamilyManifestError, match="source resource scopes"):
        family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)


def test_license_blob_must_match_declared_contract(tmp_path: Path) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    intbridge = next(item for item in release["plugins"] if item["id"] == "intbridge")
    repo = source_roots[intbridge["provenance"]["repository"]]
    (repo / intbridge["provenance"]["license_path"]).write_text("MIT\n", encoding="utf-8")
    commit_and_rebind(intbridge, repo)
    with pytest.raises(family.FamilyManifestError, match="Proprietary contract"):
        family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)


def test_single_ssh_github_origin_matches_canonical_https_identity(tmp_path: Path) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    repository = family.EXPECTED_PLUGIN_REPOSITORIES["intbridge"]
    run_git(source_roots[repository], "remote", "set-url", "origin", "git@github.com:LeoTechPro/intData-bridge.git")
    family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)


def test_multiple_origin_urls_are_rejected_as_ambiguous(tmp_path: Path) -> None:
    release, schema, source_roots = materialized_release(tmp_path)
    repository = family.EXPECTED_PLUGIN_REPOSITORIES["intbridge"]
    run_git(
        source_roots[repository],
        "config",
        "--add",
        "remote.origin.url",
        "git@github.com:LeoTechPro/intData-bridge.git",
    )
    with pytest.raises(family.FamilyManifestError, match="exactly one origin"):
        family.validate_manifest(release, schema, require_release=True, source_roots=source_roots)

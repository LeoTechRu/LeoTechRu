from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
CLEANUP = ROOT / "repo-ops" / "bin" / "agent_lock_cleanup.py"
FIX_PIPELINE = (
    ROOT
    / "codex"
    / "assets"
    / "codex-home"
    / "skills"
    / "review-sql-fix"
    / "scripts"
    / "fix_pipeline.py"
)
HOOK = ROOT / ".githooks" / "pre-commit"


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def write_fake_intnode(path: Path) -> None:
    path.write_text(
        """\
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
log_path = os.environ.get("INTNODE_TEST_LOG")
if log_path:
    with Path(log_path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(args) + "\\n")
if args[:2] == ["coord", "begin"]:
    print(json.dumps({"ok": True, "session": {"session_id": "session-1"}}))
else:
    print(json.dumps({"ok": True, "argv": args}))
""",
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("option", "mode"),
    [("--dry-run", "--dry-run"), (None, "--apply")],
)
def test_cleanup_delegates_gc_to_intnode_coord(
    tmp_path: Path, option: str | None, mode: str
) -> None:
    fake = tmp_path / "intnode.py"
    write_fake_intnode(fake)
    env = os.environ.copy()
    env["INTNODE_BIN"] = str(fake)
    env["COORDCTL_BIN"] = str(tmp_path / "must-not-run-coordctl")
    command = [sys.executable, str(CLEANUP)]
    if option:
        command.append(option)

    result = subprocess.run(command, capture_output=True, text=True, env=env)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["argv"] == [
        "coord",
        "gc",
        mode,
        "--format",
        "json",
    ]


def load_fix_pipeline(monkeypatch: pytest.MonkeyPatch, intnode: Path, log: Path):
    monkeypatch.setenv("INTNODE_BIN", str(intnode))
    monkeypatch.setenv("COORDCTL_BIN", str(intnode.parent / "must-not-run-coordctl"))
    monkeypatch.setenv("INTNODE_TEST_LOG", str(log))
    spec = importlib.util.spec_from_file_location("test_fix_pipeline", FIX_PIPELINE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_repo_fix_acquires_and_releases_exact_intnode_coord_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = tmp_path / "intnode.py"
    log = tmp_path / "intnode.log"
    write_fake_intnode(fake)
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init")
    run_git(repo, "config", "user.name", "Test")
    run_git(repo, "config", "user.email", "test@example.invalid")
    target = repo / "target.sql"
    target.write_text("select old;\n", encoding="utf-8")
    run_git(repo, "add", "target.sql")
    run_git(repo, "commit", "-m", "initial", "--no-verify")
    module = load_fix_pipeline(monkeypatch, fake, log)
    monkeypatch.setattr(module, "_allowed_roots", lambda: [tmp_path.resolve()])
    policy = module.PolicyDecision(
        environment="dev",
        scope="custom",
        source="section_summaries",
        requested_fix_mode="apply",
        effective_mode="apply",
        allow_apply=True,
        allow_dangerous=False,
    )

    result = module.apply_repo_lane(
        {
            "repo_targets": [str(repo)],
            "repo_fixes": [
                {
                    "finding_id": "finding-1",
                    "path": "target.sql",
                    "search": "old",
                    "replace": "new",
                }
            ],
        },
        {"finding-1": "confirmed"},
        policy,
    )

    assert target.read_text(encoding="utf-8") == "select new;\n"
    assert result[0]["status"] == "applied"
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert calls == [
        [
            "coord",
            "begin",
            "--repo-root",
            str(repo),
            "--owner",
            "codex:review-sql-fix",
            "--base",
            run_git(repo, "rev-parse", "HEAD").stdout.strip(),
            "--path",
            "target.sql",
            "--format",
            "json",
        ],
        ["coord", "release", "--session-id", "session-1", "--format", "json"],
    ]


def test_pre_commit_hook_is_non_blocking_when_intnode_is_absent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init")
    run_git(repo, "config", "user.name", "Test")
    run_git(repo, "config", "user.email", "test@example.invalid")
    hook = repo / ".git" / "hooks" / "pre-commit"
    shutil.copyfile(HOOK, hook)
    tracked = repo / "tracked.txt"
    tracked.write_text("initial\n", encoding="utf-8")
    run_git(repo, "add", "tracked.txt")
    run_git(repo, "commit", "-m", "initial", "--no-verify")
    tracked.write_text("changed\n", encoding="utf-8")
    run_git(repo, "add", "tracked.txt")

    result = run_git(repo, "commit", "-m", "exercise hook", check=False)

    assert result.returncode == 0, result.stderr

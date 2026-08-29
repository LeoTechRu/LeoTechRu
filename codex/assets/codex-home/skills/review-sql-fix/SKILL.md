---
name: review-sql-fix
description: 'Deterministic SQL remediation pipeline after review-sql-find. Use this skill to ingest findings/sections, re-validate each claim against current state, apply safe runtime and repo SQL fixes in dev/stage only, and produce remediation evidence artifacts: verdict, applied runtime SQL, applied repo changes, postcheck report, and rollback guide.'
---

# Review SQL Fix

## Goal

Remediate SQL findings from `review-sql-find` with the enforced sequence:
`backup -> precheck -> apply -> postcheck -> artifacts`.

## Input Contract

Provide JSON with required fields:

- `environment`: `dev | stage | prod`
- `scope`: `int/data | int/assess | custom`
- `fix_mode`: `apply | plan_only` (default `apply`)
- `source`: `live_sql | section_summaries`
- `findings_bundle`: normalized sections or report paths from `review-sql-find`

Optional fields:

- `repo_targets`: list of repo roots for file-level remediation
- `runtime_actions`: explicit runtime SQL actions
- `repo_fixes`: explicit file-level fix actions
- `allow_dangerous`: `false` by default; allows dangerous SQL override
- `runtime_executor`: live SQL executor settings (`type=psql`)
- `role_snapshot` / `settings_snapshot` / `ddl_snapshot`: runtime backup metadata inputs
- `pg_dump_path`: path to a pg_dump/DDL archive copied into snapshot if present

## Output Contract

Always generate 5 artifacts in `output_dir`:

1. `fix-verdict.md`
2. `applied-runtime-sql.md`
3. `applied-repo-changes.md`
4. `postcheck-report.md`
5. `rollback-guide.md`

## Workflow

1. Apply policy guard.
- `environment=prod` + `fix_mode=apply` => force `effective_mode=plan_only`.
- SQL mutations are forbidden in `prod`.

2. Run backup phase.
- Create snapshot in `/int/.tmp/<UTC>/review-sql-fix/`.
- Save runtime metadata and copies of target repo paths before edits.

3. Run precheck.
- Normalize findings from `findings_bundle`.
- Classify each claim with one status:
  - `confirmed`
  - `partially confirmed`
  - `not confirmed`
  - `outdated`
  - `architecture opinion`

4. Run apply (if policy allows).
- Runtime DB lane: only `confirmed` / `partially confirmed`, in small groups.
- If `runtime_executor` is configured, execute live SQL; otherwise record `applied_simulated`.
- Repo SQL lane: mutate only inside `repo_targets`, coordinate each file with `intnode coord`, no unrelated refactors.
- Reject dangerous SQL unless `allow_dangerous=true`.

5. Run postcheck.
- Record runtime/repo check results.
- On failure, stop pipeline and produce partial artifacts + rollback guide.

6. Build artifacts.
- Always write all 5 markdown outputs, including partial/failure state.

## Script Usage

```bash
python scripts/fix_pipeline.py --input /path/to/fix-input.json --output-dir /path/to/out
```

## References

- `references/fix-playbook.md` for safety rules, SQL risk policy, and confirmation criteria.

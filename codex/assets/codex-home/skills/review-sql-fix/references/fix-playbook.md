# Review SQL Fix Playbook

## Policy

- Default input mode: `fix_mode=apply`.
- Effective apply is allowed only for `environment in {dev, stage}`.
- For `environment=prod`, force `effective_mode=plan_only`.

## Safety Gates

Mandatory sequence:

1. `backup`
2. `precheck`
3. `apply`
4. `postcheck`
5. `artifacts`

Any failure before `apply` blocks all mutations.

## Backup Snapshot Content

- runtime metadata always includes: environment/scope/source/fix_mode.
- if provided, include `role_snapshot`, `settings_snapshot`, `ddl_snapshot`.
- if `pg_dump_path` exists under allowed roots, copy file into runtime snapshot.
- repo snapshots are copied only for explicit `repo_targets`.

## Confirmation Statuses

Allowed finding verdict statuses:

- `confirmed`
- `partially confirmed`
- `not confirmed`
- `outdated`
- `architecture opinion`

Only `confirmed` and `partially confirmed` are eligible for apply.

## Dangerous SQL Policy

Reject runtime SQL by default when statement matches risk patterns:

- `DROP DATABASE`
- `DROP SCHEMA`
- `DROP TABLE`
- `TRUNCATE`
- `VACUUM FULL`
- `REINDEX DATABASE`
- `ALTER SYSTEM RESET ALL`
- `DELETE` without `WHERE`

Allow only with explicit `allow_dangerous=true` in input.

## Repo Lane Policy

- `repo_fixes` can mutate only paths inside explicit `repo_targets`.
- Acquire an `intnode coord` intent lease before each file write.
- Release the `intnode coord` session after write (or on failure in finally block).
- No unrelated refactors.
- When SQL is auto-derived from section recommendations, section with multiple findings must use explicit `runtime_actions` mapping (`finding_id` per action).

## Runtime Lane Policy

- If `runtime_executor` is configured (`type=psql`), execute SQL statements live with `ON_ERROR_STOP=1`.
- If executor is not configured, mark runtime actions as `applied_simulated` and include reason/evidence.

## Postcheck Command Policy

- In `prod` and in any `plan_only` run, shell commands from `postcheck_commands` are not executed.
- Such commands are reported as `skipped_by_policy` in `postcheck-report.md`.

## Handoff from review-sql-find

`findings_bundle` may contain either:

1. normalized sections (`sections` list/map)
2. report paths from `review-sql-find` outputs (`security_report`, `performance_report`, `executive_summary`)

If sections are absent, parse markdown reports and reconstruct section records.

## Artifacts

Always produce:

- `fix-verdict.md`
- `applied-runtime-sql.md`
- `applied-repo-changes.md`
- `postcheck-report.md`
- `rollback-guide.md`

If pipeline fails, artifacts must explicitly show partial execution state and rollback notes.

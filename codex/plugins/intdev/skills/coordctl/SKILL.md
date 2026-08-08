---
name: coordctl
description: Координируй repository work через Probe-owned coordctl sessions, intents, leases и pre-commit scope checks.
---

# coordctl

Перед нетривиальной tracked mutation выбери наблюдаемый маршрут:

- `local-direct` — локальный Probe-owned `coordctl` в owning repository;
- `cloud-relay` — target-bound typed capability enrolled client с опубликованными `repo_id` и `path_id`.

Прочитай status/sessions/intents/neighbors/scope, начни или переиспользуй точную task session, зарегистрируй file/hunk intents и поддерживай heartbeat. Intent координирует, но не разрешает запись. Перед commit выполни whole-file `commit-scope-check`; stop на реальном overlap, `STALE_BASE`, ambiguous caller или изменившемся base.

`cleanup` и `gc` destructive и требуют exact preview/approval. Remote route не принимает arbitrary path. Release должен быть связан с exact session; не подменяй его owner-wide `release --mine`.

Ошибка выбранного coordctl adapter блокирует только coordination-dependent mutation через этот route. Она не запрещает другой отдельно разрешённый coordctl adapter или read-only работу. Если действующая workspace policy требует coordctl evidence, shell сам по себе не заменяет это доказательство и не даёт authority обходить overlap.

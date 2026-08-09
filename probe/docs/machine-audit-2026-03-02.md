# Machine Audit 2026-03-02: Probe Monitor + openclaw

Scope: `Probe Monitor` + `openclaw gateway`.

Этот snapshot сохранён как historical reference после выноса audit-артефактов из `/int/bridge` во внешний tooling-контур. Исторические пути ниже намеренно оставлены в старом виде `/int/scripts/...`; канонический путь после миграции — `/int/tools/...`.

| Asset | Current Location | Git Status | Risk | Mitigation |
|---|---|---|---|---|
| Orphan cleaner logic | `/int/tools/codex/scripts/cleanup_agent_orphans.sh` | Tracked | Script can be lost on host failure | Keep canonical script in `codex/scripts` and install cron from repo |
| Orphan cleaner schedule | `crontab -l` (`probe-agent-orphan-cleaner`) | Outside git | Manual drift, duplicates, loss after rebuild | Manage via `/int/tools/codex/scripts/install_orphan_cleaner_cron.sh` |
| OpenClaw gateway unit | `~/.config/systemd/user/openclaw-gateway.service` | Outside git (generated) | Unit drift and non-reproducible setup | Keep canonical drop-ins and runbooks in `/int/tools/openclaw`; restart via systemd |
| OpenClaw runtime config | `~/.openclaw/openclaw.json` | Outside git (runtime) | Wrong ACL/runtimes can break bot routing | Keep live config in `~/.openclaw` and sync versioned tooling from `/int/tools/openclaw` |
| OpenClaw runtime state | `~/.openclaw/state` | Outside git (runtime) | Session memory loss on disk failure | Include in runtime backup checklist |
| Probe Monitor compose stack | `/int/bridge/config/docker-compose.yml` | Tracked | Path hardcode blocks portability | Use env-driven runtime mounts and external state roots |
| Fleet runtime data | `~/.local/share/probe-monitor/**` | Ignored (runtime) | Runtime loss on disk failure | Keep runtime artifacts outside git and document backup/restore |
| Alert bridge state map | `~/.local/state/probe-monitor/topic_map.json` | Ignored (runtime) | Alert routing memory loss | Keep canonical state outside git and back it up separately |
| Secrets (`.env`) | `/int/bridge/.env`, `~/.openclaw/secrets/*` | Mixed: tracked + runtime | Secret exposure if repo leaked or runtime backup is lost | Probe `.env` tracked by owner decision; OpenClaw secrets keep only in `~/.openclaw/secrets/` |

## Out of Scope Backlog

- Orbit machine-level config/runtime: `/etc/default/orbit`, `/opt/orbit/**`
- Global codex binary baseline outside `.codex`

## Acceptance Snapshot (2026-03-02)

- Probe Monitor compose working dir: `/int/bridge`
- Runtime mounts: external state/runtime roots via `.env`
- `openclaw-gateway.service` active
- Legacy `telegram-bridge*` units removed

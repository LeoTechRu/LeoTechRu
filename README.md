# intData-tools

`/int/tools` is the public `intData-tools` marketplace/catalog of first-party
open-source tools and MCP servers from intData, plus recommended external tools.

This repository is not a machine-wide ops/runtime warehouse. Public source here
must be reusable, installable or reviewable as a tool, adapter, sanitized
template, or catalog entry. External recommendations are catalog links by
default: `/int/tools` stores the card and upstream URL, not a vendored source
copy.

## Public Catalog Model

Every tracked non-hidden top-level directory must be classified in `tools.catalog.v1.json`.

Allowed statuses:

- `public-tool` - installable or reusable first-party code.
- `public-adapter` - reusable adapter with non-secret configuration.
- `catalog-link` - external or recommended tool listed in catalog metadata only.
- `master-private` - material that belongs to master governance or another private contour.
- `runtime-state` - machine-local state that must not be tracked.
- `legacy-remove` - compatibility/reference material scheduled for removal after recorded destination and dry-run approval.

`/int/tools` remains the compatibility source path for now. Hardcoded absolute-path contracts are technical debt and should be removed per tool as packaging matures.

Human-readable third-party recommendations live in `EXTERNAL_TOOLS.md`; the
machine-readable registry remains `tools.catalog.v1.json`.

## Current Public Tools

- `amocrm-mcp/` - agent-agnostic MCP connector for the complete documented amoCRM HTTP API surface (REST/Webhooks, Chats, Files and telephony) plus Umnico messaging; runtime secrets remain external.
- `bitrix24-mcp/` - agent-agnostic manifest-backed MCP connector for the documented Bitrix24 public REST API; events, browser APIs and outdated pages remain explicit exclusions.
- `getcourse-mcp/` - agent-agnostic manifest-backed MCP connector for the documented GetCourse Import/Export API with guarded writes and bounded exports.
- `vakas-mcp/` - agent-agnostic manifest-backed MCP connector for guarded Vakas ingress webhooks; cabinet management remains browser-only.
- `dba/` - `intDBA`, a public first-party CLI for guarded Postgres/Supabase operator workflows.
- `lockctl/` - removed; fully retired, historical coordination state was migrated to intData Node.
- `connectors/` - reusable connector SDK and cookbook examples salvaged from retired `intNexus`.
- `agent_plane/` - reusable tool-plane runtime, policy-aware dispatch, and local harness.
- `repo-ops/` - reusable repository operations helpers.
- `vault/` - public sanitizer and runtime garbage-collection helpers only.

## Public Adapters and Migration Queue

- `codex/` - public wrappers, packaged plugins, and sanitized operator entrypoints. Codex home, secrets, private policy, runtime state, and legacy overlays are not public source.
- `delivery/` - sanitized delivery templates and reusable helpers. Live host configs, credentials, logs, and environment-specific deploy machinery must live outside public tools.
- `openclaw/` - generalized integration helpers and templates only.
- `roistat/` - audit-pending domain adapter; it remains public only if no private client coupling is present.
- `chatgpt-apps/` - legacy mixed bridge. IntBrain is outside intData-tools and must not be preserved here as search/fetch MCP.
- `gemini-openai-proxy/` - vendor/reference copy; target is a master read-only reference submodule or a catalog link.
- `web/` - legacy copy of site files; public site source belongs under master `web/tools`.
- `misc/` - no top-level miscellaneous bucket; each file must move to an owning tool or be removed.
- `probe/` - belongs to the `D:/int/bridge` contour unless generalized.

Legacy Codex-home overlays, project overlays, vendored `node_modules`, private OpenSpec/governance content, live `.env`, logs, SQLite/db runtime, and `.runtime` content must not be added as public source.

## Validation

Classification and manifest coverage gate:

```powershell
python D:\int\tools\repo-ops\bin\validate_tools_catalog.py --root D:\int\tools --skip-forbidden
```

Full public-cleanliness gate after approved legacy cleanup:

```powershell
python D:\int\tools\repo-ops\bin\validate_tools_catalog.py --root D:\int\tools
```

The validator checks that every tracked non-hidden top-level directory is present in `tools.catalog.v1.json`. The full mode also rejects forbidden public-repo artifacts. It is expected to fail while previously tracked legacy artifacts such as vendored `node_modules` and legacy Codex overlays remain in the public repository awaiting owner-approved cleanup.

## OpenSpec governance

- Для любых tracked-мутаций repo-owned tooling в `/int/tools/**` канонический process source-of-truth живёт в master/manifest репозитории `/int`, вне публичного `intData-tools`.
- OpenSpec управляется через канонический глобальный CLI `openspec` (@fission-ai/openspec), а агенты в MCP-enabled рантаймах используют `intdata-control` OpenSpec tools.
- Agents resolve `INT-*` through authenticated `gh` against `LeoTechPro/int`; legacy numbers use the tracked workspace mapping and all API/auth/mapping failures fail closed for outward gates.
- Перед первой правкой обязателен owner-approved change package в master-level `openspec/changes/<change-id>/`:
  - `proposal.md`
  - `tasks.md`
  - релевантный `spec.md` delta в `specs/**`
  - `design.md`, если меняется архитектура enforcement/runtime/resolver.
- Каждый active OpenSpec package должен быть связан с GitHub issue: в change указываем `GitHub issue: INT-*`, а в issue указываем `OpenSpec change: openspec/changes/<change-id>/`.
- OpenSpec является source-of-truth по requirements/spec/acceptance; `LeoTechPro/int` Issues хранят scope/status/links/material evidence. В issue не дублируем полный OpenSpec, prompts или reasoning.
- `AGENTS.md`, `README.md` и managed governance docs в этом repo должны обновляться только вместе с соответствующим OpenSpec change, а не отдельно от него.

## Codex и OpenClaw

- runtime Codex живёт в `~/.codex`, а versioned overlay и bootstrap-утилиты — в `codex/`;
- self-authored/versioned Codex wrappers и tooling живут только в `codex/`, в первую очередь в `codex/bin/`; `~/.codex` не используем как source-of-truth для таких скриптов;
- `codex/projects/` хранит legacy project overlay references; repo scripts больше не зеркалят их в `~/.codex/projects/`;
- reusable browser tooling, Firefox MCP launcher-ы и profile-aware wrapper-скрипты живут только в `codex/bin/`;
- Codex v2rayA recovery source lives in `codex/bin/v2raya-codex-health.sh` and `codex/bin/v2raya-core-hook-remove-quic.sh`; canonical runbook: `codex/docs/runbooks/v2raya-codex-recovery.md`;
- tracked Firefox MCP overlays для конкретных контуров живут только в `codex/projects/*/.mcp.json`;
- machine-readable routing registry для repo-owned high-risk capabilities живёт в `codex/config/agent-tool-routing.v1.json`, а resolver/validator CLI — в `codex/bin/agent_tool_routing.py`;
- canonical runtime layout dedicated Firefox MCP: `/int/tools/.runtime/firefox-mcp/profiles/<profile>/`, `/int/tools/.runtime/firefox-mcp/logs/<profile>/`, `/int/tools/.runtime/firefox-mcp/run/<profile>.json`;
- `codex/tools/mcp-obsidian-memory/` содержит локальный MCP-сервер для vault `/2brain`;
- `codex/tools/obsidian-desktop/` хранит repo-managed launcher и desktop config для Obsidian;
- `codex/assets/codex-home/skills/javascript/` хранит repo-managed resources, scripts и templates для JavaScript skill assets;
- runtime OpenClaw живёт в `~/.openclaw`, а versioned overlay и runbooks — в `openclaw/`.
- На `vds.intdata.pro` canonical host-user split такой: IntData automation/deploy, Codex и Hermes/OpenClaw runtime — `dev`; `agents` не используется на этом хосте. Automation под `leon` для этого хоста не является допустимым default-path.

### Firefox browser testing

- Canonical local browser-proof workflow: `intbridge:firefox-devtools-testing`; tracked source `/int/bridge/plugins/intbridge/skills/firefox-devtools-testing/SKILL.md`.
- Use configured `firefox-devtools` MCP for local persistent/authenticated Firefox sessions, screenshots, console/network checks, privileged scripts, prefs, and extension diagnostics.
- Legacy dedicated Firefox MCP wrappers and profile overlays remain source-controlled compatibility/remote fallback tooling; do not introduce new raw `npx` browser-proof wrappers.
- Remote, VDS, CI, headless, and reproducible E2E checks may continue to use Playwright or existing remote browser tools.

## Markdown context policy

- Каноническая политика сжатия markdown-контекста хранится в `codex/config/markdown-context-policy.json`.
- Для `.md` индексаторов и RAG-проходов используем единый denylist-контур: `max_bytes`, `exclude_exact_paths`, `exclude_globs`.
- Политика по формулировкам `missing/not found/отсутствует`: оставляем только behavior-critical контекст (контракты API, коды ошибок, диагностические инциденты).

## Полезные команды

- `intnode coord --help` — справка по Git-aware coordination sessions, intents, cleanup и merge dry-run;
- `python /int/tools/vault/installers/vault_sanitize.py --dry-run --profile strict` — dry-run санитарной миграции vault;
- `python /int/tools/vault/installers/runtime_vault_gc.py --dry-run --brain-root /int/brain` — dry-run архивации и очистки canonical runtime-root (`/int/.tmp/brain-runtime-vault`);
- `python /int/tools/vault/installers/runtime_vault_gc.py --dry-run --runtime-root /int/brain/runtime/vault` — compatibility-режим для legacy runtime-path (с deprecation warning);
- `python /int/tools/dba/lib/dba.py doctor --profile intdata-dev` — проверка native PostgreSQL CLI, TCP и SQL для локально настроенного DB profile;
- `ssh dev@vds.intdata.pro 'cd /int/tools && python /int/tools/dba/lib/dba.py migrate status --target intdata-dev'` — сравнение remote `schema_migrations` и `migration_manifest.lock` из `dev@vds.intdata.pro:/int/data`;
- В owner-facing командах `commit/push/publish/выкатывай/публикуй` агент обязан сначала проверить `git status --short --branch`; при неожиданных или чужих modified/untracked файлах нужно остановиться и спросить владельца. Самостоятельно `stash`/`restore`/`checkout --`/`reset --hard`/`clean`/скрывать/откладывать "чужие" правки из publication-state запрещено.
- `ssh vds-intdata-intdata` — canonical remote shell для IntData deploy/apply/smoke на `vds.intdata.pro`;
- `ssh vds` — canonical remote shell для Codex/Hermes runtime на `vds.intdata.pro` (`dev`);
- Для dev backend intdata с локальной Windows-машины не используйте `D:\int\data`; рабочий checkout — `dev@vds.intdata.pro:/int/data`.
- `python -m agent_plane.server --host 127.0.0.1 --port 9192` — локальный запуск neutral Agent Tool Plane;
- `python -m agent_plane.local_harness --help` — local smoke через neutral plane;
- `/int/tools/codex/bin/codex-host-bootstrap` — bootstrap рабочего минимума Codex/OpenClaw/cloud tooling;
- `pwsh -File /int/tools/codex/scripts/bootstrap_windows_toolchain.ps1 -AllowUserFallback` — idempotent bootstrap Windows CLI-toolchain (`rg`, `fd`, `yq`, `uv`, `pnpm`, `terraform`, `make`, PATH-normalization, fallback для `cmake/7z`);
- `pwsh -File /int/tools/codex/scripts/codex_preflight.ps1` — preflight-проверка ключевых CLI с machine-readable режимом `-Json`;
- `openspec --version` — канонический CLI OpenSpec (@fission-ai/openspec);
- Native git sync/publish path: `git status --short --branch`, `git fetch --prune origin`, `git pull --ff-only` only on a clean checkout when behind, and owner-approved `ALLOW_MAIN_PUSH=1 git push origin main:main` for `main`;
- `python /int/tools/codex/bin/agent_tool_routing.py validate --strict --json` — validate registry и blocker-rules для V1 high-risk tooling;
- `bash /int/tools/codex/bin/register-intdata-mcp.sh` или `pwsh -File D:\int\tools\codex\bin\register-intdata-mcp.ps1` — read-only проверка двух host-native регистраций `intdata-control` и `intdata-runtime`;
- те же команды с `--apply` создают отсутствующие регистрации через `codex mcp add`; замена drift требует `--replace`, а восстановление выполняется как `--rollback <backup.json> --apply`;
- `python -m unittest discover -s agent_plane/tests -p test_*.py -v` — unit/integration smoke neutral Agent Tool Plane;
- `pwsh -File /int/tools/codex/bin/mcp-firefox-devtools.ps1 -ProfileKey firefox-default -StartUrl http://127.0.0.1:8080/ -DryRun` — dry-run канонического Firefox DevTools MCP launcher-а;
- `bash /int/tools/openclaw/ops/verify.sh` — проверка overlay OpenClaw;
- `AUTH_TYPE=oauth-personal HOST=127.0.0.1 PORT=11434 npm start` из `gemini-openai-proxy/` — локальный запуск proxy.

## Tailscale Private Admin Channel (v1)

- Tailscale используется как приватный ops/admin канал между `local PC`, `vds.intdata.pro` и `vds.punkt-b.pro`, а не как замена публичного ingress.
- Канонический runbook: `/int/tools/codex/docs/runbooks/tailscale-tailnet-v1.md`.
- Для `vds.intdata.pro` canonical user — `dev`; учётная запись `agents` относится только к production `vds.punkt-b.pro`.
- Для `prod` действует stricter policy: default-path только read-first и отдельный restricted SSH user; full root workflow не открывается автоматически.

### Tailnet-First SSH Transport (repo-managed)

- Канонический SSH transport-слой находится в:
  - `/int/tools/codex/bin/int_ssh_resolve.py`
  - `/int/tools/codex/bin/int_ssh_resolve.ps1`
  - `/int/tools/codex/bin/int_ssh_resolve.sh`
  - `/int/tools/codex/bin/int_ssh_host.sh` (compatibility destination-only adapter; not a separate capability)
  - `/int/tools/codex/config/int_ssh_config`
- User-home `~/.ssh/config`/`C:\Users\intData\.ssh\config` этим rollout-ом не редактируется.
- Контракт режима:
  - `INT_SSH_MODE=auto|tailnet|public` (default `auto`)
  - `auto`: сначала tailnet probe, потом fallback в public с явным логом выбранного канала;
  - `tailnet`: только tailnet endpoint (без fallback);
  - `public`: только публичный endpoint.
- Контракт host-map/suffix:
  - `INT_SSH_TAILNET_SUFFIX`
  - `INT_SSH_DEV_PUBLIC_HOST`, `INT_SSH_PROD_PUBLIC_HOST`
  - `INT_SSH_DEV_TAILNET_NODE/HOST`, `INT_SSH_PROD_TAILNET_NODE/HOST`
- Короткий probe timeout: `INT_SSH_PROBE_TIMEOUT_SEC`.

## IntBrain Boundary

IntBrain lives in its own contour and is not a public intData-tools tool.

Do not add IntBrain memory/search/fetch, people graph, PM, or context tools to an intData-tools-wide MCP. Tool-specific intData-tools MCP surfaces must stay scoped to their owning public tool, and any future catalog MCP must be read-only over catalog metadata only.

## intData Codex Plugins

- Marketplace source-of-truth: `.codex/plugins/marketplace.json`.
- Product-owned plugins are referenced from their owning repositories; accepted candidates use `AVAILABLE` + `ON_INSTALL`, while unavailable family members remain dark.
- Local marketplace identity: `intdata` / `intData`.
- Public marketplace family is exactly `intbridge`, `intagent`, and `intnode`, as defined in `codex/family/intdata-family.json`; Bridge control/runtime workflow skills live only in the canonical `intbridge` plugin.
- `intnode@intdata` exposes only the Node-owned `coord` skill, which routes coordination through the existing `intnode coord` CLI. It ships no binary, standalone `coordctl`, MCP runtime, or OpenSpec skill.
- Active plugin category: `Developer Tools`.
- Removed active plugin IDs: `coordctl`, `agent-plane`, `dba`, `intprobe`, `intdba`, `lockctl`, `multica`, `openspec`, `intdata-governance`, `intdata-vault`, `mempalace`, `cabinet`.
- Cabinet-related inventory/import tooling is outside public intData-tools; old standalone local product directories are not deleted without count-check and owner acceptance.
- `intdata-control` и `intdata-runtime` являются только host-native MCP-профилями, а не plugin-пакетами. Каждая ОС отдельно регистрирует эти два MCP-профиля через native `codex mcp add` с абсолютными путями к проверенному Python и `codex/bin/mcp-intdata-cli.py`; standalone plugin ID `dba` удалён.
- Установка или переустановка plugin-пакета сама по себе не создаёт и не заменяет MCP-регистрации. Default registration mode только сравнивает inventory; apply всегда оставляет rollback backup и не переносит env/cwd из существующих записей.
- CLI-backed MCP profiles принимают только structured command args; arbitrary shell strings не поддерживаются.
- Mutating commands require `confirm_mutation: true` and `issue_context` in `INT-*` format.
- Hard migration note: old plugin IDs `intdata-routing`, `intdata-delivery`, `intdata-host`, `intdata-ssh`, `intdata-browser` removed; tools renamed to consolidated governance/runtime surface without aliases.

## Git Branch Policy

- для каждого checkout/worktree локально включаем `git config core.hooksPath .githooks`, чтобы активировать tracked guardrail из `.githooks/pre-push`;
- для multi-machine работы в `/int/*` используются explicit native git commands и repo hooks; локальный `int_git_sync_gate` удалён/запрещён;
- tracked `.githooks/pre-push` проверяет env-policy и owner approval для push в `main`; non-main push этим guardrail не блокируется;
- любой push в удалённый `main` требует явный `ALLOW_MAIN_PUSH=1` и допускается только из локальной `main`;
- push в `dev` и другие non-main branches этим repo-local guardrail не ограничивается.

## Подкаталоги и локальные инструкции

Ниже восстановлено содержимое удалённых repo-owned `README.md` из предыдущего состояния репозитория.

### `codex/`

#### Codex Scripts

`codex/` хранит versioned host-tooling для Codex CLI и смежного MCP-окружения.
Канонические wrapper'ы и install/runbook-обвязка живут здесь; live runtime OpenClaw вынесен в `~/.openclaw`, а versioned overlay лежит в `/int/tools/openclaw`. Codex home остаётся Codex-owned state и не синхронизируется из repo scripts.

##### Контракт

- Канонические Codex-facing wrapper'ы и install/ops-обвязка живут в `/int/tools/codex`.
- Legacy managed assets для старого Codex home overlay могут оставаться только как historical/read-only reference; они не являются active sync source.
- Project overlays для старого `~/.codex/projects/*` не синхронизируются repo scripts; используйте native Codex plugin/skill/config mechanisms.
- Runtime/log/tmp/state repo-owned tooling живут вне git, в `/int/tools/.runtime/**`.
- Секретные env-файлы MCP живут не в `~/.codex/var`, а в `/int/tools/.runtime/codex-secrets/`; active helpers не используют legacy Codex-home fallback.
- Любые cron/systemd записи должны ссылаться на файлы из этого каталога, а не на продуктовые репозитории.
- Канонический cron entrypoint для orphan cleaner: `/int/tools/codex/cleanup_agent_orphans.sh`; lock/log writes go to `/int/tools/.runtime/codex/**`.
- `~/.codex/scripts/cleanup-agent-orphans.sh` допустим только как legacy compatibility wrapper для старых вызовов, без source-of-truth логики.
- Codex-home sync/detach scripts were removed: Codex home changes require native Codex mechanisms or explicit manual owner action.
- Для clean-room восстановления используйте `/int/tools/codex/bin/codex-host-bootstrap`, `/int/tools/codex/bin/codex-host-verify` и `/int/tools/codex/bin/codex-recovery-bundle`.

##### Канонические runtime-path

- логи repo-owned tooling: `/int/tools/.runtime/codex/log/`
- временные файлы repo-owned tooling: `/int/tools/.runtime/codex/tmp/`
- OpenClaw runtime: `~/.openclaw/`
- OpenClaw overlay/runbooks: `/int/tools/openclaw/`
- прочий Codex runtime/state: Codex-owned `~/.codex/`, изменяется только native Codex mechanisms или explicit manual owner action
- Codex MCP secrets runtime: `/int/tools/.runtime/codex-secrets/`
- Cloud runtime: `/int/tools/.runtime/cloud-access/`

##### Текущие утилиты

- `duplex_bridge.py` — debate-bridge; по умолчанию пишет лог в `/int/tools/.runtime/codex/log/debate/duplex_bridge.log`
- `cleanup_agent_orphans.sh` — уборка осиротевших MCP/agent процессов
- `install_orphan_cleaner_cron.sh` — установка канонической cron-записи на `/int/tools/codex/cleanup_agent_orphans.sh`
- `cloud_access.sh` — ленивый доступ к `gdrive`/`yadisk` через `rclone mount` и единый runtime `RCLONE_CONFIG=/int/tools/.runtime/cloud-access/rclone.conf`
- `install_cloud_access.sh` — развёртывание runtime-каталогов `/int/tools/.runtime/cloud-access`, mountpoints `/int/cloud/*` и user-level symlink units
- `bin/` — MCP entrypoints и прочие Codex-facing launcher'ы
- Local delivery publish wrappers were removed; use explicit native commands and the target repo's current documented process for owner-requested push/deploy work.
- `bin/agent_tool_routing.py` + `../config/agent-tool-routing.v1.json` — routing contract для repo-owned high-risk capabilities; blocked path не подменяется verified skill автоматически, fallback допустим только как explicit approved metadata.
- `tools/` — repo-managed helper trees (`mcp-obsidian-memory`, `obsidian-desktop`, `openspec`)
- `assets/codex-home/` — legacy reference для старого Codex home overlay; не active sync source
- `projects/` — legacy reference для старых project-specific overlay-файлов; не синхронизируется repo scripts
- Codex-home sync/detach entrypoints were removed; use native Codex mechanisms or explicit manual owner action.
- `bin/codex-host-bootstrap` — bootstrap рабочего минимума `/int/tools/.runtime/**`, OpenClaw/cloud tooling; не пишет в Codex home
- `bin/codex-host-verify` — проверка clean layout и целостности ссылок
- `bin/codex-recovery-bundle` — export/import шифрованного recovery-бандла с секретным runtime-слоем

##### Recovery Layout

- `~/.codex` должен содержать только Codex-generated runtime/state и файлы, созданные native documented Codex mechanisms или explicit manual owner action.
- Наши wrapper'ы, templates и policy остаются в `/int/tools/codex`.
- Самописные helper scripts для Codex не храним в `~/.codex/scripts`; home-контур допускается только для native tools и обязательных runtime instructions/compat wrappers, если их нельзя вынести из home-layout.
- Живые секреты для MCP храним в `/int/tools/.runtime/codex-secrets/`.
- `OpenClaw` runtime живёт в `~/.openclaw`, а versioned overlay остаётся в `/int/tools/openclaw`.
- Секретный слой OpenClaw для recovery bundle берётся из `~/.openclaw/secrets/`.
- Repo scripts do not synchronize `assets/codex-home` or tracked `projects/` into Codex home.
- dedicated Firefox MCP runtime использует repo-managed launcher'ы и project overlays отсюда; owner browser profile не является source-of-truth для automated browser-proof.

###### Базовая процедура восстановления

1. Установить `codex-cli`.
2. Восстановить секретный слой через `codex-recovery-bundle import`.
3. Запустить `/int/tools/codex/bin/codex-host-bootstrap` для repo-local runtime bootstrap без изменения Codex home.
4. При необходимости выполнить `codex login`.
5. Проверить контур через `/int/tools/codex/bin/codex-host-verify` и `/int/tools/openclaw/ops/verify.sh`.

##### Cloud Access

- Канонические unit-файлы лежат в `/int/tools/codex/systemd/` и подключаются в `~/.config/systemd/user/` через symlink.
- Исключение для этого контура согласовано отдельно: runtime mountpoints и `rclone` config живут внутри `/int`, а не в `~/.codex`, чтобы Codex/OpenClaw работали с облаками через уже разрешённый файловый корень.
- Основной runtime:
  - config: `/int/tools/.runtime/cloud-access/rclone.conf`
  - cache: `/int/tools/.runtime/cloud-access/cache`
  - logs: `/int/tools/.runtime/cloud-access/log`
  - mounts: `/int/cloud/gdrive`, `/int/cloud/yadisk`
- После настройки remotes используйте:
  - `/int/tools/codex/cloud_access.sh config`
  - `systemctl --user start rclone-mount-gdrive.service`
  - `systemctl --user start rclone-mount-yadisk.service`

### `codex/assets/codex-home/skills/javascript/resources/`

#### Resources for javascript

### `codex/assets/codex-home/skills/javascript/scripts/`

#### Scripts for javascript

### `codex/assets/codex-home/skills/javascript/templates/`

#### Templates for javascript

### `codex/projects/`

#### Codex Project Overlays

Здесь лежат tracked project-specific overlay-файлы для Codex runtime.

Правила:
- этот каталог — legacy reference для project overlays; active Codex project config должен идти через native Codex mechanisms;
- repo scripts не синхронизируют этот каталог в Codex home;
- в tracked overlay не храним секреты;
- реальные env-файлы живут в `/int/tools/.runtime/codex-secrets/`.
- browser-proof overlays для dedicated Firefox MCP обязаны вызывать только repo-managed wrapper'ы из `/int/tools/codex/bin/**`, а не raw `npx`.

### `codex/tools/mcp-obsidian-memory/`

#### mcp-obsidian-memory

Локальный MCP сервер для vault `/2brain`.

Сервер работает с root-vault `2brain`; индекс OpenClaw при этом может использовать более узкий include-набор директорий, чтобы не тащить архивный и служебный шум в memory search.

##### Tools
- `vault_status`
- `list_notes`
- `read_note`
- `search_notes`
- `upsert_note`
- `move_note_para`
- `link_notes`
- `audit_links`
- `suggest_links`

##### Run

```bash
cd /int/tools/codex/tools/mcp-obsidian-memory
npm start
```

##### Smoke

```bash
node /int/tools/codex/tools/mcp-obsidian-memory/scripts/smoke-client.mjs
```

### `codex/tools/obsidian-desktop/`

#### Obsidian Desktop Config (Repo-managed)

Все канонические конфиги и инструкции для desktop-интеграции Obsidian хранятся в `/int/tools/codex/tools/obsidian-desktop`.
Они открывают root-vault агента `/2brain`.

##### Файлы
- `launcher.sh` — запуск Obsidian на vault `/2brain`
- `obsidian-memory.desktop` — desktop entry
- `obsidian.json` — канонический список vault-ов
- `install.sh` — ставит симлинки в `~/.local` и `~/.config`

Этот helper остаётся owner-manual exception и не входит в automation/runtime migration для `vds.intdata.pro`.

##### Применение
```bash
bash /int/tools/codex/tools/obsidian-desktop/install.sh
```

После запуска:
- `~/.local/bin/obsidian -> /int/tools/codex/tools/obsidian-desktop/launcher.sh`
- `~/.local/share/applications/obsidian-memory.desktop -> /int/tools/codex/tools/obsidian-desktop/obsidian-memory.desktop`
- `~/.config/obsidian/obsidian.json -> /int/tools/codex/tools/obsidian-desktop/obsidian.json`

Это гарантирует, что конфиги и launcher'ы не зависят от `~/.codex/tools`.

### `dba/`

#### intDBA

`/int/tools/dba` — self-contained operator CLI `intDBA` для remote Postgres/Supabase профилей с этой машины.

##### Контракт

- tracked bootstrap живёт рядом с инструментом: `README.md`, `AGENTS.md`, `.env.example`, launchers и tests;
- локальный `.env` допустим только как untracked runtime-файл рядом с инструментом;
- временные dump/log/CSV-артефакты живут только в ignored путях `.tmp/` и `logs/`;
- `DBA_DATA_REPO` может задаваться как через process env, так и через локальный `dba/.env`; типовые runtime-ошибки должны выходить как обычные `intDBA:` сообщения без traceback;
- на Windows `dba` не должен автоматически подхватывать `D:\int\data`; для dev backend работы используется `dev@vds.intdata.pro:/int/data`, а локальный disposable flow требует явный `--repo`/`DBA_DATA_REPO`;
- native migration-path тоже должен быть самодостаточным: `bootstrap` использует тот же profile-password, а `incremental` при необходимости сам прокидывает найденный PostgreSQL `bin` в `PATH` дочернего `bash`;
- для `/int/data` tool не дублирует schema ownership и migration engine, а переиспользует owner flow через `init/010_supabase_migrate.sh`, `init/schema.sql` и `migration_manifest.lock`.

##### Основные команды

- `doctor` — проверка native PostgreSQL CLI, TCP и SQL для профиля;
- `sql` / `file` — ad-hoc SQL и SQL-файлы, по умолчанию в read-only режиме;
- `dump` / `restore` / `clone` / `copy` — перенос данных между профилями через локальную машину;
- `migrate status` / `migrate data` — remote-операции для migration flow `/int/data`.

##### Safety

- mutating-команды требуют `--approve-target <profile>`;
- для `WRITE_CLASS=prod` дополнительно обязателен `--force-prod-write`;
- `intDBA` доступен как самостоятельный CLI через `/int/tools/dba`; совместимый adapter `dba` в `mcp-intdata-cli.py` не регистрируется и не является устанавливаемым plugin ID. `codex/bin/intdb.*` compatibility wrappers не считаются активными поверхностями.

### `delivery/`

#### Delivery Ops

`/int/tools/delivery` — внешний host-config, devops, docops, monitoring и delivery contour для intData-family сервисов.

##### Что живёт здесь

- host-level configs и proxy/systemd templates, которые не являются product-core;
- devops/docops/dev helpers для инфраструктурных и release задач;
- cross-repo and machine-wide scripts, которые обслуживают delivery/runtime контуры.

##### Что не живёт здесь

- canonical schema/functions/contracts backend-core;
- runtime-state и секреты;
- исходники отдельных продуктовых сервисов.

##### Структура

- `configs/` — host-level configs и templates;
- `devops/` — ops helpers;
- `devs/` — developer helpers;
- `docops/` — docs/process helpers;
- `monitoring/` — monitoring templates.

`/int/data` остаётся owner только backend-core. Всё, что является внешним tooling, host-config или rollout слоем, должно жить в `delivery/`.

### `delivery/configs/`

#### intdata host configs

Этот каталог хранит внешний host-config слой для `intdata` и соседних family-сервисов.

##### Что находится здесь

- apache/nginx/systemd/fail2ban/docker helper configs
- generated vhost templates и ops reference files

##### Что не находится здесь

- canonical backend migrations/contracts/functions
- runtime-state и живые секреты

Если конфиг обслуживает хост, reverse proxy, systemd или внешний rollout path, его место здесь, а не в `/int/data`.

### `delivery/configs/nginx/`

#### Конфигурации nginx (reverse proxy перед Apache)

Каталог содержит итоговые конфиги `nginx`, сформированные на основе действующих `apache2` vhost'ов.
Исключения:
- [`api.intdata.pro.conf`](/int/tools/delivery/configs/nginx/api.intdata.pro.conf) ведётся отдельно как host-level custom vhost для Supabase API и не генерируется из Apache.
- [`tools.intdata.pro.conf`](/int/tools/delivery/configs/nginx/tools.intdata.pro.conf) обслуживает статический публичный frontend из [`web/`](/int/tools/web/index.html).

###### Назначение

- nginx принимает внешние HTTP/HTTPS-подключения (80/443), выполняет TLS-терминацию, безопасные заголовки и лимиты.
- Apache остаётся backend-сервером и слушает только на `127.0.0.1:8080` / `127.0.0.1:8443`.
- Конфиги генерируются скриптом `delivery/devops/generate_nginx_from_apache.py`, который подтягивает `ServerName`, `ServerAlias`, TLS-сертификаты и формирует пару `server {}` блоков (HTTP/HTTPS) для каждого vhost'а.

###### Процесс обновления

1. Убедитесь, что `/etc/apache2/sites-available/` содержит актуальные конфиги.
2. Запустите генератор из корня репозитория:
   ```bash
   python3 delivery/devops/generate_nginx_from_apache.py
   ```
   Файлы появятся в `configs/nginx/generated/`.
3. Примените конфиги на хосте:
   ```bash
    sudo cp configs/nginx/generated/*.conf /etc/nginx/sites-available/
    sudo ln -sf /etc/nginx/sites-available/<vhost>.conf /etc/nginx/sites-enabled/<vhost>.conf
    sudo nginx -t
    sudo systemctl reload nginx
   ```
4. После выпуска/продления сертификатов `certbot` необходимо выполнить `systemctl reload nginx`.

###### Дополнительно

- Общие сниппеты (`/etc/nginx/snippets/ssl-params.conf`) должны содержать жёсткие TLS-настройки и заголовки безопасности.
- Временное использование портов и сервисов фиксируйте в issue/worklog и сопровождайте machine-wide `intnode coord` session/intent по изменяемым файлам. При оффлайне допускается запись в `AGENTS/issues.json` (`offline_queue`); после синхронизации с GitHub удалите черновик и отметьте время `Synced on <UTC>`. Постоянные изменения инфраструктуры отражайте в паспорте объектов `AGENTS/object_passport.yaml`.

###### Перевыпуск сертификатов через snap `certbot`

1. Убедитесь, что установлен snap-пакет:
   ```bash
   sudo snap install core; sudo snap refresh core
   sudo snap install --classic certbot
   sudo ln -sf /snap/bin/certbot /usr/bin/certbot
   ```
2. Для каждого нового домена пропишите webroot (см. конфиги — `/var/www/<domain>`):
   ```bash
   sudo mkdir -p /var/www/bot.intdata.pro
   sudo mkdir -p /var/www/id.intdata.pro
   sudo mkdir -p /var/www/id.intdata.pro
   sudo mkdir -p /var/www/nexus.intdata.pro
   sudo mkdir -p /var/www/sso.intdata.pro
   ```
3. Выпустите сертификаты (пример для одного домена, перечислите нужные `-d`; переменная `CERTBOT_EMAIL` обязательна). Проще всего использовать автоматизированный скрипт:
   ```bash
   export CERTBOT_EMAIL=ops@intdata.pro
   sudo delivery/devops/issue_intdata_certs.sh
   ```
   Либо вызвать вручную:
   ```bash
   sudo certbot certonly --webroot -w /var/www/bot.intdata.pro -d bot.intdata.pro
   sudo certbot certonly --webroot -w /var/www/id.intdata.pro -d id.intdata.pro
   sudo certbot certonly --webroot -w /var/www/id.intdata.pro -d id.intdata.pro
   sudo certbot certonly --webroot -w /var/www/nexus.intdata.pro -d nexus.intdata.pro
   sudo certbot certonly --webroot -w /var/www/sso.intdata.pro -d sso.intdata.pro
   ```
4. После успешного выпуска перезагрузите nginx:
   ```bash
   sudo nginx -t && sudo systemctl reload nginx
   ```

При необходимости можно объединять несколько доменов в один сертификат (`-d` через пробел), однако удобно поддерживать отдельные связки, чтобы разграничить сроки продления.

### `delivery/configs/systemd/`

#### configs/systemd

Шаблоны systemd-юнитов и вспомогательные обёртки. См. раздел `delivery/configs/` ниже и [delivery/AGENTS.md](/int/tools/delivery/AGENTS.md) за регламент.

##### Новые юниты
- `meta-intdata-mailpit-dev.service` — orchestrator для docker-compose Mailpit (QA SMTP/UI).

### `delivery/devops/`

#### [delivery/devops](/int/tools/delivery/devops)

Скрипты DevOps-цикла (rebuild, restart, smoke) и инфраструктурные инструменты. Общие принципы описаны в разделах `delivery/` и `delivery/devops/` ниже.

- **configure_erp_sso.sh** — настраивает Keycloak-провайдеры для Odoo/ERPNext. Требует заполненного `erp/.env` и запущенных контейнеров (`docker compose -f erp/docker-compose.yaml up -d`).

##### Keycloak + Kill Bill (IAM биллинг/подписки)

- **/int/id/docker-compose.yaml** с профилем `keycloak` — standalone стек Keycloak + Kill Bill + Kaui + PostgreSQL.
- **setup_keycloak_killbill.sh** — управляющий скрипт (`start|stop|restart|logs|down|status`), принимает `--env` для указания файла переменных, проверяет обязательные секреты и автоматически бутстрапит Realm/тенант после запуска.
- Дополнительные флаги: `--clear-theme-cache` (очищает `kc-gzip-cache` в контейнере Keycloak после `up/restart`) и `--selenium-smoke` (запускает `delivery/devops/run_selenium_smoke.sh` для браузерного smoke).
- **killbill.overrides/killbill.properties.example** — пример overrides для Kill Bill (скопируйте в `killbill.properties` и подставьте секреты).
- **/int/id/scripts/devops/run_selenium_smoke.sh** — опциональный Selenium UI smoke для standalone repo Identity; выполняется только если selenium tests добавлены локально.

###### Быстрый старт

```bash
#### 1. Подготовьте env-файл (.env.dev) и заполните обязательные переменные:
####    ID_KEYCLOAK_DB_NAME, ID_KEYCLOAK_DB_USER, ID_KEYCLOAK_DB_PASSWORD,
####    ID_KEYCLOAK_ADMIN, ID_KEYCLOAK_ADMIN_PASSWORD,
####    ID_KEYCLOAK_ADMIN_CLIENT_ID, ID_KEYCLOAK_ADMIN_CLIENT_SECRET,
####    ID_KEYCLOAK_LOGIN_THEME (по умолчанию intdata),
####    ID_KEYCLOAK_DISPLAY_NAME (по умолчанию "intData SSO"),
####    ID_KEYCLOAK_DISPLAY_NAME_HTML (по умолчанию "intData SSO"),
####    ID_KILLBILL_DB_NAME, ID_KILLBILL_DB_USER, ID_KILLBILL_DB_PASSWORD,
####    ID_KILLBILL_ADMIN_USER, ID_KILLBILL_ADMIN_PASSWORD,
####    ID_KILLBILL_DEFAULT_API_KEY, ID_KILLBILL_DEFAULT_API_SECRET,
####    ID_KILLBILL_WEBHOOK_SECRET
####    ID_KEYCLOAK_REALM (опционально, по умолчанию intdata)
####    ID_KILLBILL_TENANT_NAME (опционально, по умолчанию "IntData Dev")
####    SSO клиенты модулей (см. id/.env.example):
####      BRAIN_SSO_*/BRAIN_ADMIN_SSO_*/BRAIN_API_SSO_*
####      CRM_SSO_*/CRM_ADMIN_SSO_*/CRM_API_SSO_*
#####      NEXUS_SSO_*/NEXUS_ADMIN_SSO_*/NEXUS_API_SSO_*
####      SUITE_SSO_*/SUITE_ADMIN_SSO_*/SUITE_API_SSO_*
####      ID_ADMIN_SSO_*, ID_API_SSO_*
####      BOT_ADMIN_SSO_*, BOT_API_SSO_*
####    (redirect/web_origins задаются CSV, по умолчанию используются dev-домены и localhost-порты)
#
#### 2. (опционально) Скопируйте killbill.overrides/killbill.properties.example в
####    killbill.overrides/killbill.properties и обновите значения.
#
#### 3. Запустите стек:
/int/id/scripts/devops/setup_keycloak_killbill.sh start --env /int/id/.env
#### при изменении тем Keycloak добавьте --clear-theme-cache, чтобы сбросить кеш статических ресурсов
#### для end-to-end smoke можно дополнительно указать --selenium-smoke
#### при старте выполняются проверки env и bootstrap Keycloak/Kill Bill (можно отключить, установив ID_BOOTSTRAP_DISABLED=1)

#### 4. Проверить состояние:
/int/id/scripts/devops/setup_keycloak_killbill.sh status

#### 5. Логи конкретного сервиса:
/int/id/scripts/devops/setup_keycloak_killbill.sh logs keycloak
```

> **Примечание:** `docker compose down` удаляет контейнеры/volume’ы; используйте опцию `down` скрипта только при необходимости.
>
> При bootstrap Keycloak создаётся (или обновляется) realm `intdata`, а также полный набор OIDC-клиентов для модулей платформы (`<module>-web`, `<module>-admin`, `<module>-api`). Конфигурация (client id, redirect-uri, web origins, client secret) считывается из переменных `*_SSO_*`/`*_ADMIN_SSO_*`/`*_API_SSO_*`. Значения по умолчанию ориентированы на домены `*.intdata.pro` и локальные порты; перед запуском продакшн-стека обязательно синхронизируйте их через OpenBao.
>
> Сессия bootstrap также применяет тему `ID_KEYCLOAK_LOGIN_THEME` и отображаемое имя Realm (`ID_KEYCLOAK_DISPLAY_NAME`, `ID_KEYCLOAK_DISPLAY_NAME_HTML`). Для брендовой темы `intdata` убедитесь, что в репозитории обновлены файлы `id/keycloak/themes/intdata`, затем выполните `restart` + `logs` + smoke.

###### Selenium UI smoke (standalone)

- Скрипт `delivery/devops/run_selenium_smoke.sh` выполняет headless smoke веб-интерфейсов (маркер `selenium`):
  1. создаёт/переиспользует виртуальное окружение `venv/`;
  2. устанавливает зависимости из `tests/requirements.txt`;
  3. запускает `pytest -m selenium tests/web/test_ui_selenium_smoke.py`, передавая дополнительные аргументы pytest из командной строки.
- Параметры через переменные окружения:
  - `CHROME_BINARY` — путь к Chromium/Chrome (по умолчанию `/usr/bin/chromium`);
  - `SELENIUM_URL_<MODULE>` — переопределённые хосты для smoke;
  - `SELENIUM_WAIT_TIMEOUT` — таймаут ожидания (секунды, дефолт 20).
- Примеры:

  ```bash
  /int/id/scripts/devops/run_selenium_smoke.sh -q
  CHROME_BINARY=/opt/google/chrome/chrome /int/id/scripts/devops/run_selenium_smoke.sh --maxfail=1
  ```

- Скриншоты и другие артефакты сохраняются в `tests/web/screenshots/`; не коммитим чувствительные данные.
- Флаг `setup_keycloak_killbill.sh --selenium-smoke` вызывает этот скрипт автоматически в конце DevOps-цикла.

###### Что делает стек

- **Keycloak** на `https://localhost:${ID_KEYCLOAK_HTTP_PORT:-8443}` — единый IdP для /id.
- **Kill Bill** на `http://localhost:${ID_KILLBILL_HTTP_PORT:-8081}` — биллинг/подписки.
- **KAUI** (админ Kill Bill) на `http://localhost:${ID_KAUI_HTTP_PORT:-9091}` — опционально (profile `kaui`).

###### DevOps задачи

- Создать секреты в vault/1Password (настоящие пароли не коммитить).
- Подготовить инфраструктурные БД (prod/stage) через команды DBA.
- Настроить systemd unit или orchestrator (k8s) на базе compose-файла.
- Добавить health-check в `delivery/devops/smoke.sh` после интеграции с /id.
- После обновления smoke (`delivery/devops/smoke.sh`) будет проверять Keycloak (`/.well-known/openid-configuration`) и Kill Bill (`/1.0/healthcheck`). Убедитесь, что переменные `ID_KEYCLOAK_HTTP_PORT_LEGACY`, `ID_KEYCLOAK_REALM`, `ID_KILLBILL_HTTP_PORT` заданы при запуске.

##### Mailpit (единый SMTP шлюз)

- **/int/id/docker-compose.yaml** с профилем `mailpit` — standalone манифест SMTP/UI сервиса (`mail.intdata.pro`, `smtp.intdata.pro`).
```
docker compose -f /int/id/docker-compose.yaml --profile mailpit ps
```
- **run-mailpit.sh** — zero-wait цикл (`rebuild → restart → logs → log-scan → smoke`), готовит каталоги и проверяет API `/api/v1/info` через `mail.intdata.pro`.
- **meta-intdata-mailpit-dev.service** — systemd-юнит (см. `configs/systemd/`) для автономного рестарта. Optional host-local env читается из `/etc/intdata/mailpit/mailpit.env`.

###### Быстрый старт

```bash
#### 1. Создайте директории и секреты:
####    sudo mkdir -p /var/lib/intdata/mailpit /etc/intdata/mailpit/tls /var/log/intdata/mailpit
####    sudo htpasswd -bc /etc/intdata/mailpit/users.htpasswd intdata-smtp '<smtp-password>'
####    sudo htpasswd -bc /etc/intdata/mailpit/ui.htpasswd intdata-ui '<ui-password>'
####    # TLS сертификаты mail.intdata.pro / smtp.intdata.pro поместите в /etc/intdata/mailpit/tls/
#
#### 2. Экспортируйте переменные (или заполните /etc/intdata/mailpit/mailpit.env для systemd):
export SMTP_PASSWORD='<smtp-password>'
export MAILPIT_SMTP_USER='intdata-smtp'
export MAILPIT_UI_USER='intdata-ui'
export MAILPIT_DATA_DIR='/var/lib/intdata/mailpit'
export MAILPIT_CONFIG_DIR='/etc/intdata/mailpit'
export MAILPIT_LOG_DIR='/var/log/intdata/mailpit'

#### 3. Запустите цикл:
delivery/devops/run-mailpit.sh

#### 4. Убедитесь, что mailpit работает:
docker compose -f id/docker-compose.yaml --profile mailpit ps
```

> **Важно:** файлы `users.htpasswd`, `ui.htpasswd`, TLS-ключи и пароли не попадают в git. Управляйте ими через секрет-хранилище Владельца.

###### Сертификаты mail.intdata.pro / smtp.intdata.pro
- Фронт: `nginx` (80/443) → `apache2` (8080/8443) → `mailpit`.
- Сертификат Let's Encrypt выпускаем через snap `certbot`:

```bash
sudo certbot certonly \
  --webroot -w /var/www/letsencrypt \
  --cert-name mail.intdata.pro \
  -d mail.intdata.pro -d smtp.intdata.pro \
  --agree-tos --no-eff-email -m prointdata@ya.ru
```

- Симлинки в `/etc/intdata/mailpit/tls/` должны указывать на `/etc/letsencrypt/live/mail.intdata.pro-0001/{fullchain,privkey}.pem` для UI и SMTP (`mail.*`, `smtp.*`).
- После выпуска выполните `systemctl reload nginx apache2` и `delivery/devops/run-mailpit.sh` для обновления контейнера.

###### SMTP (Яндекс Почта)
- Проектные сервисы отправляют письма через `smtp.yandex.ru` (порт `465`, SSL), аккаунт `prointdata@yandex.ru`, пароль приложения задаёт владелец.
- Минимальные переменные `.env`: `SMTP_HOST=smtp.yandex.ru`, `SMTP_PORT=465`, `SMTP_USE_SSL=true`, `SMTP_USER=prointdata@yandex.ru`, `SMTP_PASSWORD=<yandex_app_password>`, `EMAIL_FROM=prointdata@yandex.ru`.
- Smoke-проверка отправки:

```bash
python - <<'PY'
import smtplib, ssl
from email.message import EmailMessage
msg = EmailMessage()
msg['Subject'] = 'Yandex SMTP smoke'
msg['From'] = 'prointdata@yandex.ru'
msg['To'] = 'prointdata@yandex.ru'
msg.set_content('Smoke delivery через smtp.yandex.ru')
context = ssl.create_default_context()
with smtplib.SMTP_SSL('smtp.yandex.ru', 465, context=context, timeout=15) as smtp:
    smtp.login('prointdata@yandex.ru', '<yandex_app_password>')
    smtp.send_message(msg)
print('sent')
PY
```

- Mailpit (`https://mail.intdata.pro`) используется только для QA/наблюдения; реальные письма уходят напрямую через Яндекс. Пароль приложения держим в секрет‑хранилище владельца, а в `.env` подставляем при деплое.

###### OpenBao (self-host)
- Конфиг объединён в `id/docker-compose.yaml` (profile `openbao`); переменные читаются из корневого `.env` (`OPENBAO_*`). Отдельный `.env.infisical УДАЛЁН` больше не используется.
- Запуск/перезапуск:

```bash
OPENBAO_ENV_FILE=.env \
delivery/devops/run-openbao.sh
```

- После старта выполните `python -m id.api.cli sync-openbao --env-file .env`, чтобы выгрузить секреты модулей в OpenBao и обновить секцию `OPENBAO SYNC` в `.env`.
- Проверка доступности:

```bash
```

- Root token (`ID_OPENBAO_TOKEN`) хранится только во внешнем секрет-хранилище. При ротации токена сначала обновите `.env`, затем повторно выполните `sync-openbao`.

##### Утилиты и вспомогательные скрипты

- **check_duplicates.py** — ищет дубликаты файлов по SHA-1. По умолчанию сканирует `/int/brain/web/static/diagnostics`, игнорируя `.git`, `node_modules`, build-артефакты. Код возврата `0`, если дублей нет, и `1`, если найдены совпадения. Пример:\
  `python3 delivery/devops/check_duplicates.py shared/assets -e build -e cache`.

- **dev-redeploy.sh** — стандартный DevOps-цикл для ветки `dev`: подтягивает `.env`, запускает rebuild/restart сервисов, собирает логи в `logs/devops/<UTC>/`, прогоняет `log-scan.py`, выполняет HTTP-smoke и дополнительно запускает [`smoke.sh`](/int/tools/delivery/devops/smoke.sh) (включая OpenBao). Использование:\
  `delivery/devops/dev-redeploy.sh`.

- **generate_nginx_from_apache.py** — миграционная утилита: читает активные Apache vhost’ы и генерирует эквивалентные прокси-конфиги nginx (HTTP+HTTPS) в `configs/nginx/generated/`. Требует root-доступ. Запуск:\
  `sudo python3 delivery/devops/generate_nginx_from_apache.py`.

- **import_archive_to_project.py** — импортирует оффлайн-черновики из `AGENTS/issues.json` (`offline_queue`) в GitHub Project V2: создаёт Draft Issue, переносит статус и основные поля (Status/Role/Module/Type) и очищает запись в зеркале. Нужен `GITHUB_TOKEN` (или `gh auth token`). Пример:\
  `python3 delivery/devops/import_archive_to_project.py --project-number 1`.

- **install_services.sh** — устанавливает/обновляет systemd unit’ы из `configs/systemd/` (копирование в `/etc/systemd/system`, `daemon-reload`, `enable`). Запуск только от root:\
  `sudo delivery/devops/install_services.sh`.

- **local-redeploy.sh** — локальный перезапуск dev-стека без полного DevOps-цикла: обновляет зависимости, кэширует фронт, перезапускает docker-compose сервисы. Применяется во время разработки:\
  `delivery/devops/local-redeploy.sh`.

- **log-scan.py** — ищет критические записи в логах (паттерн `ERROR|FATAL|CRITICAL|Traceback|...`). Используется внутри `dev-redeploy.sh`, но может запускаться отдельно:\
  `python3 delivery/devops/log-scan.py logs/devops/<timestamp>`.

- **project_deadline_guardian.py** — контролирует дедлайны карточек GitHub Project: переводит просроченные элементы в статус `Expired` и уведомляет указанных пользователей (см. workflow `project_deadline_guardian.yml`).

- **rebuild_service.sh** — точечный пересбор docker-compose сервиса: вызовет `docker compose build <service>` + `up -d`. Указываем compose-name из корневого `docker-compose.yml`:\
  `delivery/devops/rebuild_service.sh nexus-web`.

- **rebuild_smart_sidebar.sh** — пересборка фронтенда Nexus из canonical repo `/int/brain/web`, затем синхронизация артефактов в target web-root. Использование:\
  `delivery/devops/rebuild_smart_sidebar.sh`.

- **run_task_reminder_worker.py** — entrypoint для фонового воркера напоминаний (используется в systemd/cron). Интервал опроса берёт из `TASK_REMINDER_INTERVAL` (секунды). Запуск:\
  `python3 delivery/devops/run_task_reminder_worker.py`.

- **sync_discussions_mirror.py** — выгружает GitHub Discussions по категориям в JSON (например, `AGENTS/announcements.json`, `AGENTS/research.json`). По умолчанию берёт только активные обсуждения; флаг `--include-closed` добавляет закрытые. Примеры:\
  `python3 delivery/devops/sync_discussions_mirror.py --slug announcements --output AGENTS/announcements.json`\
  `python3 delivery/devops/sync_discussions_mirror.py --slug research --output AGENTS/research.json --include-closed`.

- **run-openbao.sh**, **run-mailpit.sh**, **run_selenium_smoke.sh**, **setup_keycloak_killbill.sh**, **smoke.sh** — описаны в разделах выше (OpenBao, Mailpit, Selenium smoke, IAM стек, DevOps smoke).

### `gemini-openai-proxy/`

#### Gemini ↔ OpenAI Proxy

Этот каталог теперь живёт внутри `/int/tools` как internal-vendor copy, а не как
самостоятельный git-репозиторий. Источник происхождения:
`https://inthub.com/Brioch/gemini-openai-proxy` (MIT License, см. `LICENSE`).

Что это означает на практике:

- upstream reference фиксируется в этом README, а не через `origin` в отдельном checkout;
- в `tools` храним только versioned исходники и документацию;
- `.git`, `node_modules/`, `dist/` и прочий runtime/build слой сюда не переносим;
- все локальные доработки дальше ведём уже как часть `LeoTechPro/intData-tools`.

Локальный OpenAI-compatible proxy для Gemini с опорой на current
`@google/gemini-cli`/`@google/gemini-cli-core` и существующую OAuth-сессию в
`~/.gemini`.

Целевой режим этого репозитория сейчас один:

- ручной запуск;
- только `127.0.0.1`;
- `AUTH_TYPE=oauth-personal`;
- совместимость с chat-completions клиентами уровня Cline/OpenWebUI/curl;
- поддержка text, stream, vision и tool calling.

##### Требования

- Node.js 24+;
- валидная локальная Gemini OAuth-сессия, обычно файл
  `~/.gemini/oauth_creds.json`;
- установленный доступ к Gemini через Google account.

##### Установка

```bash
npm install
```

##### Поддержанный запуск

```bash
AUTH_TYPE=oauth-personal \
HOST=127.0.0.1 \
PORT=11434 \
MODEL=gemini-3-flash-preview \
MODEL_FALLBACK_CHAIN=gemini-2.5-pro,gemini-2.5-flash,gemini-2.5-flash-lite \
npm start
```

Переменные окружения:

- `HOST` — по умолчанию `127.0.0.1`
- `PORT` — по умолчанию `11434`
- `AUTH_TYPE` — по умолчанию `oauth-personal`
- `MODEL` — primary model, по умолчанию `gemini-3-flash-preview`
- `MODEL_FALLBACK_CHAIN` — CSV-цепочка фолбэка, по умолчанию `gemini-2.5-pro,gemini-2.5-flash,gemini-2.5-flash-lite`

Текущая policy этого прокси:

- primary request model: `gemini-3-flash-preview`
- fallback chain: `gemini-2.5-pro -> gemini-2.5-flash -> gemini-2.5-flash-lite`
- если клиент передаёт `body.model`, прокси сначала пробует именно его, затем идёт по configured chain
- фолбэк срабатывает только на ошибки доступности модели: quota/capacity/429/not found

Проверка на этом хосте показала, что `auto`, `auto-gemini-2.5`, `pro`, `flash`
и `flash-lite` для `AUTH_TYPE=oauth-personal` использовать как model id не стоит.

Прокси на этом этапе не предназначен для внешней сети. Если нужен внешний
доступ, это отдельная задача с bind/reverse-proxy/auth/hardening.

##### Endpoints

- `GET /healthz`
- `GET /v1/models`
- `POST /v1/chat/completions`

##### Быстрые проверки

Проверка здоровья:

```bash
curl http://127.0.0.1:11434/healthz
```

Простой chat completion:

```bash
curl -X POST http://127.0.0.1:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3-flash-preview",
    "messages": [
      {"role": "user", "content": "Hello Gemini"}
    ]
  }'
```

Stream:

```bash
curl -N -X POST http://127.0.0.1:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3-flash-preview",
    "stream": true,
    "messages": [
      {"role": "user", "content": "Say hello in one short sentence"}
    ]
  }'
```

Tool calling roundtrip:

```bash
curl -X POST http://127.0.0.1:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3-flash-preview",
    "messages": [
      {"role": "user", "content": "What is the weather in Paris?"}
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "get_weather",
          "description": "Get weather by city",
          "parameters": {
            "type": "object",
            "properties": {
              "city": {"type": "string"}
            },
            "required": ["city"]
          }
        }
      }
    ]
  }'
```

Следующий ход после получения `tool_calls`:

```json
{
  "model": "gemini-3-flash-preview",
  "messages": [
    {"role": "user", "content": "What is the weather in Paris?"},
    {
      "role": "assistant",
      "content": null,
      "tool_calls": [
        {
          "id": "call_123",
          "type": "function",
          "function": {
            "name": "get_weather",
            "arguments": "{\"city\":\"Paris\"}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "call_123",
      "content": "{\"temperature\":18,\"conditions\":\"Cloudy\"}"
    }
  ]
}
```

##### Как работает фолбэк

Для каждого запроса прокси собирает chain:

1. `body.model`, если клиент его передал
2. primary model из `MODEL`
3. модели из `MODEL_FALLBACK_CHAIN`

Дубликаты убираются. При ошибках вида quota/capacity/not found прокси
моментально пробует следующую модель. В успешном ответе поле `model`
содержит фактически использованную модель.

### `lockctl/` (removed)

`lockctl` has been fully retired and removed from this repository. Its runtime
history was imported into the Node-owned coordination runtime. Active
coordination is available only through `intnode coord`. Do not reintroduce
lockctl wrappers, MCP tools or runtime surfaces.

### Coordination (external intData Node CLI)

#### `intnode coord`

`intnode coord` is the Git-aware coordination runtime for parallel agent edits.
It is owned by `/int/node`; the `intnode@intdata` plugin contributes only usage guidance for this existing CLI and does not bundle its runtime.

##### Shell UX

Use the canonical Node entrypoint:

```bash
intnode coord
intnode coord --help
```

Implementation/core lives in `/int/node/internal/coordctl`. `/int/tools` owns
no coordination source, installer, runtime alias, or MCP tool; its marketplace
entry only points to the Node-owned `coord` guidance skill.

##### Runtime model

- One active session per owner/branch/base work unit.
- Region leases are scoped by `repo_root + path + base_blob + region`.
- `hunk` is the default v1 region kind; `file` is the fallback for unsafe files.
- `symbol`, `json_path`, and `section` are schema-compatible future region kinds.
- `COORD_CONFLICT` and `STALE_BASE` are blockers; agents stop and ask for owner decision.
- Cleanup is explicit: `cleanup --dry-run` first, then `--apply` only for known final states.
- `delete-worktree` and `delete-branch` are opt-in cleanup actions, never implicit.

##### Common examples

```bash
intnode coord begin --path README.md
intnode coord intent --path README.md
intnode coord status
intnode coord commit-scope-check
intnode coord release --mine
```

### `openclaw/`

#### openclaw tools overlay

`/int/tools/openclaw` — versioned overlay для локального OpenClaw.

Legacy in-tree runtime root decommissioned и больше не является runtime-источником; исторические артефакты сохранены в отчётах decommission.

Канонический runtime теперь должен жить вне git:

- binary: `openclaw` из глобального install (`npm/pnpm/bun`)
- home/state: `~/.openclaw`
- config: `~/.openclaw/openclaw.json`
- workspace: `~/.openclaw/workspace`

Этот каталог хранит только versioned tooling:

- `bin/` — helper wrapper'ы для доменных запросов;
- `ops/` — install/verify/restart helper'ы вокруг official install;
- `systemd/` — versioned drop-in templates;
- `docs/` — runbook'и и исторические audit-артефакты по migration/decommission.

Инварианты:

- `node_modules/`, `state/`, `workspace/`, `secrets/` и live `openclaw.json` не хранятся в git;
- `openclaw gateway install --force` остаётся базовым способом переустановки user service;
- versioned файлы не должны содержать live token, секреты каналов или machine-specific runtime state.
- на этой машине OpenClaw требует Node 22.12+; overlay-скрипты по умолчанию подхватывают `$HOME/.nvm/versions/node/v24.8.0/bin`, если он установлен.

Быстрые команды:

```bash
bash /int/tools/openclaw/ops/install.sh
bash /int/tools/openclaw/ops/verify.sh
```

Основной runbook:

- [reinstall-and-restore.md](/int/tools/openclaw/docs/reinstall-and-restore.md)
- [openclaw-concurrency-audit-2026-03-09.md](/int/tools/openclaw/docs/openclaw-concurrency-audit-2026-03-09.md)
- [decommission-openclaw-2026-03-15.md](/int/tools/openclaw/reports/decommission-openclaw-2026-03-15.md)

### `probe/`

#### Bridge Probe Scripts

`probe/` хранит versioned maintenance и audit-утилиты для мониторинга intData Bridge Probe, которые не входят в prod-core репозиторий `/int/bridge`.

##### Контракт

- `/int/bridge` содержит только код, deploy-конфиг и проверки.
- Versioned maintenance scripts и исторические audit snapshots мониторинга intData Bridge Probe живут здесь.
- Mutable state и runtime-data мониторинга живут вне git: `~/.local/state/probe-monitor` и `~/.local/share/probe-monitor`.
- Migration/cutover идёт через `/int/bridge/ops/migrate_runtime.sh`, затем `ops/cutover.sh --install-units --restart-services` и `ops/verify.sh --runtime`.

##### Состав

- `collect_audit.sh` — сбор audit snapshot по текущему checkout `/int/bridge`
- `docs/critical_assets.txt` — список must-survive assets и внешних runtime-path
- `docs/machine-audit-2026-03-02.md` — исторический audit snapshot, перенесённый из `probe`

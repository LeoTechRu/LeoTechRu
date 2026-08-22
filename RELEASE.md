# Релизлог

Этот файл фиксирует понятные записи по каждому локальному commit репозитория `/int/tools`. Запись готовится перед commit и входит в тот же commit.

## 2026-08-22
### Публичный каталог и совместимость пакетов восстановлены
- Каталог публичной поверхности синхронизирован с фактическими top-level модулями; отсутствующий `openclaw` удалён, а contracts, validators, tests, OpenSpec и MCP-контуры классифицированы явно.
- Catalog gate теперь допускает публичные `AGENTS.md` и product-local OpenSpec, но по-прежнему блокирует private `.codex`-артефакты.
- MCP-пакеты на legacy `mcp.server.fastmcp` ограничены совместимой major-версией `mcp<2`; metadata amoCRM MCP приведена к актуальному PEP 639/setuptools.
- Python carrier connector contracts стабильно выбирает actionable schema error внутри `oneOf`/`anyOf` на актуальных `jsonschema`, сохраняя закрытые reason/path envelopes.
- DBA корректно формирует Windows `PATH` и каталог `psql` независимо от ОС, на которой выполняется regression suite.

## 2026-07-19
### amoCRM MCP: agent-agnostic root и полный публичный HTTP API registry
- Канонический source перенесён из `codex/tools/amocrm-mcp/` в top-level [amocrm-mcp/](/int/tools/amocrm-mcp), чтобы один пакет использовался Codex, Hermes и другими MCP-host'ами.
- Добавлен committed manifest 236 документированных endpoint'ов amoCRM REST/Webhooks, Chats, Files и telephony с официальными source URL, host/auth metadata и воспроизводимым генератором.
- Новый `amocrm_api_call` маршрутизирует любой endpoint из manifest, включая HMAC-SHA1 Chats API и binary/base64 Files API; `amocrm_api_endpoints` и `amocrm_api_manifest` дают машинно-проверяемую инвентаризацию.
- Connector-level `confirm_send` удалён: внешние approval-политики остаются ответственностью Codex/Hermes, а коннектор передаёт API буквально.
- Добавлены parity/client tests, обновлены runner, sanitized env example, public catalog и инструкции skill-коммуникаций без устаревшего параметра `confirm_send`.

## 2026-04-12
### delivery publish: канонический engine вынесен из `codex/` в cross-platform Python contour
- Добавлен нейтральный publish contour `delivery/bin/` с cross-platform engine [delivery/bin/publish_repo.py](/int/tools/delivery/bin/publish_repo.py) и canonical wrapper [delivery/bin/publish_data.py](/int/tools/delivery/bin/publish_data.py) для `/int/data`.
- [codex/bin/publish_repo.ps1](/int/tools/codex/bin/publish_repo.ps1) и [codex/bin/publish_data.ps1](/int/tools/codex/bin/publish_data.ps1) переведены в compatibility shims: они больше не владеют publish-логикой, а только делегируют её в Python engine.
- Regression suite перенесён из `codex/tests` в [delivery/tests/test_publish_repo.py](/int/tools/delivery/tests/test_publish_repo.py), а `.githooks/pre-push` теперь проверяет именно delivery smoke без зависимости от `pwsh`.
- В [README.md](/int/tools/README.md), [AGENTS.md](/int/tools/AGENTS.md) и policy соседнего `/int/data` обновлён canonical контракт: publish для `/int/data` теперь должен идти через `python .../delivery/bin/publish_data.py`, а `codex/bin/publish_*.ps1` считаются только legacy/Windows shims.

## 2026-04-05
### codex publish: main-only smoke gate и graceful PowerShell degradation
- В [.githooks/pre-push](/int/tools/.githooks/pre-push) publish smoke теперь запускается только для push в `refs/heads/main`, поэтому non-main pushes снова не зависят от `publish_repo.ps1` regression suite и не конфликтуют с repo-policy.
- Для push в `main` hook теперь отдельно требует PowerShell до запуска smoke и печатает явную ошибку, вместо скрытого import-time падения Python suite на хостах без `pwsh`/`powershell`.
- В [codex/tests/test_publish_repo.py](/int/tools/codex/tests/test_publish_repo.py) убран import-time `assert` на PowerShell: manual smoke на PowerShell-less host теперь корректно помечает tests как skipped, а не валится до старта.

## 2026-04-05
### codex publish: deploy-smoke герметизирован и подключён в pre-push gate
- В [codex/tests/test_publish_repo.py](/int/tools/codex/tests/test_publish_repo.py) deploy-failure branch больше не зависит от реального DNS/SSH: тест подменяет `ssh` локальным shim в temp `PATH` и запускает wrapper с явным `timeout`, сохраняя проверку `partial_state` и stderr-контракта.
- В [.githooks/pre-push](/int/tools/.githooks/pre-push) добавлен tracked smoke-gate `python -m unittest codex.tests.test_publish_repo -q` (с fallback на `python3`), чтобы publish-wrapper regression больше не оставался только ручной README-командой.
- В новой [.gitattributes](/int/tools/.gitattributes) зафиксирован `LF` для [.githooks/pre-push](/int/tools/.githooks/pre-push), чтобы bash-hook с этим smoke-gate не ломался на Windows checkout из-за `CRLF`.
- В [README.md](/int/tools/README.md) синхронизировано, что publish smoke герметичен и автоматически запускается tracked pre-push hook'ом.

## 2026-04-05
### codex publish: smoke cleanup temp-root после прогона
- В [codex/tests/test_publish_repo.py](/int/tools/codex/tests/test_publish_repo.py) `publish_repo_test_*` temp-root теперь регистрируется через `addCleanup(...)` с принудительным снятием readonly-атрибутов на Windows git object files, чтобы regression smoke действительно удалял временные bare repos и working trees из `%TEMP%`.

## 2026-04-05
### codex publish: stderr deploy-ошибок и regression smoke для `publish_repo.ps1`
- В [codex/bin/publish_repo.ps1](/int/tools/codex/bin/publish_repo.ps1) `Invoke-SshChecked` теперь сохраняет stderr `ssh` и включает его в сообщение об ошибке, чтобы post-push deploy failure было диагностируемо без повторного ручного воспроизведения.
- Добавлен versioned smoke [codex/tests/test_publish_repo.py](/int/tools/codex/tests/test_publish_repo.py) на три критичных ветки `publish_repo.ps1`: `-NoDeploy` success, dirty-tree rejection и `push completed / deploy failed` с `partial_state`.
- В [README.md](/int/tools/README.md) добавлена canonical команда запуска этого smoke через стандартный `python -m unittest codex.tests.test_publish_repo -v`, без внешней test-зависимости.

## 2026-04-05
### intdb: review-fix по native migration path
- В [intdb/lib/intdb.py](/int/tools/intdb/lib/intdb.py) `migrate data --mode bootstrap` снова использует profile-level `PGPASSWORD`, поэтому native `psql --no-password` больше не ломается на password-auth профилях.
- В incremental-ветке `intdb` теперь добавляет найденный PostgreSQL `bin` в `PATH` дочернего `bash`, чтобы [init/010_supabase_migrate.sh](/int/data/init/010_supabase_migrate.sh) находил `psql` даже до обновления глобального Windows PATH.
- В [intdb/tests/test_intdb.py](/int/tools/intdb/tests/test_intdb.py), [intdb/README.md](/int/tools/intdb/README.md) и [README.md](/int/tools/README.md) добавлены точечные проверки и doc-sync под эти два подтверждённых migration-finding.

## 2026-04-05
### intdb: runtime переведён с Docker на native PostgreSQL CLI
- В [intdb/lib/intdb.py](/int/tools/intdb/lib/intdb.py) удалён Docker transport layer: `intdb` теперь запускает системные `psql`, `pg_dump` и `pg_restore` напрямую, а `doctor` сначала проверяет наличие native CLI, затем TCP и SQL-доступ.
- `migrate data --mode incremental` теперь запускает локальный `bash` для [init/010_supabase_migrate.sh](/int/data/init/010_supabase_migrate.sh), а bootstrap-ветка исполняет [schema.sql](/int/data/init/schema.sql) и [seed_business.sql](/int/data/init/seed_business.sql) через native `psql`.
- В [intdb/tests/test_intdb.py](/int/tools/intdb/tests/test_intdb.py), [intdb/README.md](/int/tools/intdb/README.md), [intdb/.env.example](/int/tools/intdb/.env.example) и [README.md](/int/tools/README.md) синхронизирован новый контракт без Docker-зависимости.

## 2026-04-05
### codex publish: `/int/data` push-default закреплён как wrapper `publish_data.ps1`
- В [codex/bin/publish_repo.ps1](/int/tools/codex/bin/publish_repo.ps1) failure-contract усилен: при падении после успешного push wrapper теперь печатает уже выполненные шаги и явный `partial_state`, что `origin/main` обновлён, а deploy не завершён.
- В [README.md](/int/tools/README.md) и policy соседнего контура `/int/data` синхронизирован canonical owner-facing контракт: команда на `push/publish/выкатывай` для `/int/data` должна приводить к запуску `publish_data.ps1`, который уже включает и push, и deploy.

### intdb: review-fix по runtime error handling и local env data repo
- В [intdb/lib/intdb.py](/int/tools/intdb/lib/intdb.py) `doctor`, Docker-launch path и TCP-проверка теперь переводят типовые `OSError`/`FileNotFoundError` в обычные `IntDbError`, чтобы CLI не печатал raw Python traceback на отсутствие `docker` или отказ подключения.
- `INTDB_DATA_REPO` теперь читается тем же merged-контуром, что и profile-переменные: значение можно задавать как через process env, так и через локальный untracked [intdb/.env](/int/tools/intdb/.env).
- В [intdb/tests/test_intdb.py](/int/tools/intdb/tests/test_intdb.py) добавлены точечные тесты на чтение `INTDB_DATA_REPO` из локального `.env`, а также на wrapping ошибок `docker` и TCP-connect.

## 2026-04-05
### intdb: review-fix по confirmed findings
- В [intdb/lib/intdb.py](/int/tools/intdb/lib/intdb.py) передача `PGPASSWORD` и `POSTGRES_PASSWORD` в `docker run` переведена с `-e KEY=value` на проброс через env текущего процесса, чтобы не светить секреты в локальной командной строке.
- `migrate status` и `migrate data` больше не привязаны к жёсткому `D:\int\data`: добавлен auto-discovery через `INTDB_DATA_REPO` и sibling repo `..\..\data`, а при отсутствии обоих вариантов CLI даёт явную ошибку с требованием `--repo`.
- `migrate status` теперь корректно обрабатывает target без `public.schema_migrations` и считает такую БД pristine-состоянием с пустым списком applied versions.
- В [intdb/tests/test_intdb.py](/int/tools/intdb/tests/test_intdb.py) добавлены точечные unit-тесты на скрытие секретов в argv Docker, auto-discovery data repo и fallback при отсутствии `schema_migrations`.

## 2026-04-05
### Добавлен self-contained `intdb` для remote Postgres/Supabase профилей
- Создан новый machine-wide модуль [intdb/README.md](/int/tools/intdb/README.md), [intdb/AGENTS.md](/int/tools/intdb/AGENTS.md), [intdb/.env.example](/int/tools/intdb/.env.example) и локальные launchers [intdb/intdb.ps1](/int/tools/intdb/intdb.ps1), [intdb/intdb.cmd](/int/tools/intdb/intdb.cmd).
- Python core [intdb/lib/intdb.py](/int/tools/intdb/lib/intdb.py) реализует `doctor`, `sql`, `file`, `dump`, `restore`, `clone`, `copy`, `migrate status` и `migrate data` через Docker-backed PostgreSQL client.
- Для mutating-операций добавлены target-guard'ы `--approve-target` и `--force-prod-write` по `WRITE_CLASS` профиля.
- Для `/int/data` migration flow не дублируется: `intdb` переиспользует owner scripts `init/010_supabase_migrate.sh`, `init/schema.sql` и `migration_manifest.lock`.
- Добавлены thin wrappers [codex/bin/intdb.ps1](/int/tools/codex/bin/intdb.ps1) и [codex/bin/intdb.cmd](/int/tools/codex/bin/intdb.cmd), а корневой [README.md](/int/tools/README.md) обновлён под новый модуль и публичные команды.

## 2026-04-04
### review-fix: tighten `review-sql-fix` safety and deterministic mapping
- В `review-sql-fix/scripts/fix_pipeline.py` запрещено выполнение shell-команд из `postcheck_commands` в `prod` и в любом `plan_only` запуске; в отчёте такие команды фиксируются как `skipped_by_policy`.
- В `fix_pipeline.py` убрана неоднозначная автопривязка SQL-рекомендаций к `section:1`: для секций с несколькими findings теперь требуется явный `runtime_actions` с `finding_id`, иначе apply прерывается с явной ошибкой.
- В `review-sql-fix/scripts/backup_snapshot.py` исправлен default backup root на Windows: теперь используется явный `D:/int/.tmp` (fallback `C:/int/.tmp`), и `backup_base` дополнительно валидируется по allowed roots.
- `review-sql-fix/SKILL.md` переведён в ASCII-only формат, чтобы `quick_validate.py` проходил в стандартной Windows-локали без `PYTHONUTF8=1`.
- Обновлён `review-sql-fix/references/fix-playbook.md` под новые правила postcheck и explicit mapping для multi-finding секций.

### Skills: `review-sql-find` + `review-sql-fix` для read-only аудита и controlled remediation
- Добавлен новый skill `codex/assets/codex-home/skills/review-sql-find` с контрактом аудита PostgreSQL и детерминированным компилятором отчётов `scripts/compile_report.py`.
- Добавлен новый skill `codex/assets/codex-home/skills/review-sql-fix` с pipeline `scripts/fix_pipeline.py`, guard'ами `scripts/safety_guard.py`, backup-модулем `scripts/backup_snapshot.py` и playbook `references/fix-playbook.md`.
- Зафиксирована policy-логика: `fix_mode=apply` по умолчанию, но для `environment=prod` apply принудительно блокируется (`effective_mode=plan_only`).
- В remediation-пайплайне закреплены обязательные стадии `backup -> precheck -> apply -> postcheck -> artifacts`, INCOMPLETE/truncation-блокировка precheck и выпуск 5 артефактов (`fix-verdict`, runtime/repo apply, postcheck, rollback).
- Для repo lane добавлен file-level lockctl workflow и ограничение правок только путями внутри `repo_targets`; runtime lane поддерживает `runtime_executor(type=psql)` и fallback `applied_simulated`, если live executor не передан.

## 2026-04-03
### Publish tooling: ssh deploy helper no longer collides with PowerShell `$Host`
- В `codex/bin/publish_repo.ps1` параметр helper-функции `Invoke-SshChecked` переименован с `$Host` на `$SshHost`, чтобы strict-mode publish wrappers не падали на read-only built-in переменной PowerShell при deploy-шаге.
- `publish_data.ps1` и остальные repo-specific wrappers снова могут доходить до `ssh-fast-forward` deploy без ложного падения после успешного `git push`.

### Codex layout: publish tooling moved from loose repo root into `codex/bin`
- Publish wrappers перенесены из вне-контурного `publish/` в versioned Codex contour `codex/bin/`, чтобы Codex-facing tooling жил там же, где остальные managed wrapper'ы и bootstrap entrypoints.
- `README.md` и `AGENTS.md` закрепляют новое глобальное правило: самописный Codex tooling хранится только в `/int/tools/codex/**`, а `~/.codex` используется только для native/runtime state и обязательных home-level инструкций.

### Publish tooling: repo-local wrappers вместо общего bundle-gate
- Добавлен versioned publish contour в `codex/bin/` с общим engine `publish_repo.ps1` и repo-specific wrappers `publish_data.ps1`, `publish_assess.ps1`, `publish_crm.ps1`, `publish_id.ps1`, `publish_nexus.ps1`.
- Для `/int/data` wrapper закреплён под `main` + deploy на `vds.intdata.pro:/int/data`, для `/int/assess` wrapper поддерживает `dev` + fast-forward deploy на `vds.intdata.pro:/int/assess`, а остальные repos больше не проверяются пакетом по умолчанию.
- Добавлен manual bulk utility `codex/bin/publish_bundle_dint.ps1`; user-home entrypoint `C:\Users\intData\.codex\scripts\publish_dev_dint.ps1` позже удалён из runtime и не является canonical multi-repo gate.

## 2026-04-02
### Docs+Policy: markdown-context compression wave A-C
- Добавлен канонический policy-файл [codex/config/markdown-context-policy.json](/int/tools/codex/config/markdown-context-policy.json) с общими правилами контекст-фильтрации (`max_bytes`, `exclude_exact_paths`, `exclude_globs`) для `/int`.
- В [README.md](/int/tools/README.md) добавлен отдельный раздел `Markdown context policy` с единым контуром denylist и правилом лексической чистки по `missing/not found/отсутствует`.
- В [AGENTS.md](/int/tools/AGENTS.md) git-gate переписан в компактную позитивную формулировку без шумовой риторики про отсутствие upstream.

## 2026-03-31
### review-fix: drop-сопоставление PATH канонизирует разделители
- В `codex/scripts/bootstrap_windows_toolchain.ps1` добавлена канонизация ключей сравнения в `Normalize-UserPath` (`/` -> `\`, схлопывание повторных `\`) для `candidate`, `compareKey` и `DropEntries`.
- Исправлен подтверждённый кейс, когда `%LOCALAPPDATA%/OpenAI/Codex/bin` не отбрасывался при `DropEntries` с backslash-форматом.
- Scope изменения ограничен только remediation по подтверждённому `review-find` пункту.

### intbrain-mcp: ownership moved to /int/brain
- Canonical IntBrain MCP server moved to `/int/brain/mcp/intbrain`.
- Added brain-owned stdio entrypoints:
  - `/int/brain/mcp/intbrain/bin/mcp-intbrain --stdio`
  - `python /int/brain/mcp/intbrain/bin/mcp-intbrain.py`
- `/int/tools/codex/bin/mcp-intdata-cli.py --profile intbrain` is now a thin compatibility wrapper that delegates to `/int/brain`.
- `/int/tools/codex/plugins/intbrain/.mcp.json` now points to `D:\int\brain\mcp\intbrain\bin\mcp-intbrain.py`.
- IntBrain Codex plugin source and skills source-of-truth moved to `/int/brain/codex/plugins/intbrain/`.

### finalize: закрыт pending server-state по `mcp-intbrain` и `mcp-memory-bank`
- В `codex/bin/mcp-intbrain.py` добавлена нормализация PM date-алиасов (`today|tomorrow|yesterday`) с учётом timezone для `pm/*` инструментов (`dashboard/tasks/health/constraints/task_create/task_patch`).
- Для `pm_task_create/pm_task_patch` добавлен `due_at=\"today\"` alias (текущий timestamp в указанной timezone).
- В `.gitignore` добавлен `mcp-memory-bank/`, чтобы локальные unpacked/wheel артефакты не попадали в git-индекс и не держали рабочее дерево грязным на хостах.

### review-fix: PATH normalizer сохраняет env-токены и не теряет валидные записи
- В `codex/scripts/bootstrap_windows_toolchain.ps1` обновлён `Normalize-UserPath`: для `%ENV%`-путей проверка существования идёт через `ExpandEnvironmentVariables()`, но в итоговый PATH сохраняется исходный raw-токен.
- Если `%VAR%` не раскрывается (например, `%UNKNOWN_VAR%`), запись больше не удаляется автоматически при нормализации.
- Drop-сравнение сделано безопасным для raw/expanded вариантов, чтобы исключить ложное удаление валидных PATH-элементов.
- Контракт bootstrap (`code=0/10/20`) не менялся; при stale process PATH всё ещё нужен перезапуск терминала/Codex-сессии.

### review-fix: унифицирован launcher `lockctl-mcp.cmd` и исправлен Linux exec-bit
- В `lockctl/install_lockctl.sh` добавлены alias-линки `lockctl.cmd` и `lockctl-mcp.cmd` для Linux, чтобы Windows-style launcher имя было доступно кроссплатформенно.
- MCP-конфиги переведены на явный `lockctl-mcp.cmd`: `codex/templates/config.toml.tmpl`, `codex/plugins/lockctl/.mcp.json`, `codex/projects/punkt-b/.mcp.json`, `openclaw/.mcp.json`.
- В `codex/bin/codex-host-verify` добавлена совместимая проверка двух вариантов launcher (`lockctl-mcp` и `lockctl-mcp.cmd`), чтобы не ломать существующие runtime-конфиги.
- Для `codex/bin/mcp-lockctl.sh` и `openclaw/bin/mcp-lockctl.sh` выставлен executable mode (`100755`), чтобы Linux launcher можно было исполнять напрямую.

### review-fix: устранены cross-drive сбои `/int/...` на Windows для lockctl-интеграций
- В legacy governance и `punkt-b`-утилитах (`lock_issue_resolver.py`, `lock_release_by_issue.py`, `agent_lock_cleanup.py`) обновлён `LOCKCTL_BIN` resolver: `/int/...` корректно резолвится на фактический диск Windows.
- В legacy governance и `punkt-b`-утилитах добавлен py-launch fallback: если `LOCKCTL_BIN` указывает на `lockctl.py`, команда запускается через `sys.executable`, чтобы на Windows не возникал `WinError 193`.

### review-fix: точечные правки bootstrap/preflight по подтверждённым findings
- В `codex/scripts/codex_preflight.ps1` удалена принудительная перезапись process `PATH` (`User + Machine`): preflight больше не искажает фактический runtime-резолв бинарей в текущей сессии.
- В `codex/scripts/bootstrap_windows_toolchain.ps1` убран user-specific hardcode (`C:\\Users\\intData\\...`) и введены вычисления путей через `$env:LOCALAPPDATA`/`$PSScriptRoot`, чтобы скрипт был переносимым между профилями.
- В `bootstrap_windows_toolchain.ps1` добавлен reuse существующего portable CMake (`Resolve-PortableCMakeBin`) до сетевой установки, что устраняет повторную переустановку при повторном запуске.

### Windows Codex toolchain bootstrap + preflight
- Добавлены скрипты `codex/scripts/bootstrap_windows_toolchain.ps1` и `codex/scripts/codex_preflight.ps1` для воспроизводимой настройки Windows CLI-инструментов и быстрой диагностики статуса (`ok|missing|blocked|fix_suggested`, таблица/JSON).
- `bootstrap_windows_toolchain.ps1` фиксирует контракт exit-codes: `0` (готово), `10` (нужен elevated shell), `20` (частичные ошибки), пишет PATH snapshot/results в `/int/.tmp/toolchain-bootstrap/<UTC>/`.
- Реализована mixed-логика установки: `winget` для основного стека, `choco -> winget` fallback для `make`, portable fallback для `cmake`, alias fallback для `7z` через `M2Team.NanaZip` в user-scope.
- Реализована PATH-normalization: приоритет `WinGet\Links`/`WindowsApps`, очистка несуществующих user PATH entries, удаление stale `OpenAI\\Codex\\bin`.
- Обновлён `README.md` разделом полезных команд для bootstrap/preflight.

### lockctl installer: Windows PATH launcher delegation
- В `lockctl/install_lockctl.ps1` исправлен Windows installer: вместо копирования `.cmd` без соседних `.py` теперь генерируются delegating-launchers с абсолютным путём к исходным wrapper'ам в `/int/tools`.
- Installer выбирает install-dir с приоритетом PATH-aware (`%APPDATA%\npm`/`%USERPROFILE%\bin`) и при необходимости дописывает выбранный путь в user PATH.

### lockctl: кроссплатформенное ядро + MCP + adapters для Codex/OpenClaw
- `lockctl` переработан в модульное ядро `lockctl/lockctl_core.py` с сохранением CLI-контракта (`acquire|renew|release-path|release-issue|status|gc`) через совместимый entrypoint `lockctl/lockctl.py`.
- Добавлены Windows launcher'ы `lockctl/lockctl.ps1` и `lockctl/lockctl.cmd`, поддержан `python -m lockctl` через `lockctl/__main__.py`, обновлён POSIX wrapper `lockctl/lockctl`.
- Добавлен state resolver: `LOCKCTL_STATE_DIR` -> `$CODEX_HOME/memories/lockctl` -> platform default (`~/.codex/...`/`%USERPROFILE%\.codex\...`) и one-time Windows migration legacy state `D:\home\leon\.codex\memories\lockctl` с backup marker.
- Исправлена нормализация путей: корректная обработка Windows absolute-path в `--path` и хранение `path_rel` строго относительно `repo_root`.
- Добавлен MCP server `codex/bin/mcp-lockctl.py` + launcher'ы (`.sh`/`.cmd`) и OpenClaw adapters (`openclaw/bin/mcp-lockctl.sh`, `openclaw/bin/mcp-lockctl.cmd`, `openclaw/.mcp.json`).
- Обновлены legacy governance интеграции и `punkt-b` (`lock_issue_resolver.py`, `lock_release_by_issue.py`, `agent_lock_cleanup.py`) для Windows-style `LOCKCTL_BIN` path resolution.
- Обновлены runtime/config контракты: `codex/templates/config.toml.tmpl`, `codex/layout-policy.json`, `codex/bin/codex-host-verify`, `codex/projects/punkt-b/.mcp.json`, `codex/tools/install_tools.sh`.
- Добавлен skill `codex/assets/codex-home/skills/lockctl/SKILL.md`, plugin scaffold `codex/plugins/lockctl/.codex-plugin/plugin.json` и marketplace entry `.agents/plugins/marketplace.json`.
- Обновлена документация lockctl/openclaw/process: `README.md`, `codex/assets/codex-home/AGENTS.md`, `punkt-b/docs/process/issue-commit-flow.md`, `openclaw/docs/reinstall-and-restore.md`, `openclaw/docs/lockctl-mcp.md`.
- Добавлен unit test `lockctl/tests/test_lockctl_core.py` для path/state behavior.

## 2026-03-29
### ngt-memory moved to external reference mode
- `ngt-memory` удалён из индекса `/int/tools` как gitlink и больше не участвует в репозиторных change-цепочках этого контура.
- В `.gitignore` добавлен `ngt-memory/`, чтобы локальный reference clone не загрязнял статус `intData-tools`.
- В `README.md` добавлен явный external-reference статус с upstream-ссылкой `https://github.com/ngt-memory/ngt-memory`.

### ngt-memory gitlink updated in intData-tools
- В `ngt-memory` зафиксирован новый gitlink commit `34aa4e2cb6c8b57441549dd2c32748f0de4260ad` в составе дерева `/int/tools`.
- Обновление включает прокидку `OPENAI_BASE_URL` в API/session flow и поддержку `base_url` в `NGTMemoryLLMWrapper` для OpenAI-compatible провайдеров.

### intbrain-mcp: canonical PM tools surfaced in MCP wrapper
- В [codex/bin/mcp-intbrain.py](/int/tools/codex/bin/mcp-intbrain.py) добавлен полный canonical PM набор в `TOOLS`:
  - `intbrain_pm_dashboard`
  - `intbrain_pm_tasks`
  - `intbrain_pm_task_create`
  - `intbrain_pm_task_patch`
  - `intbrain_pm_para`
  - `intbrain_pm_health`
  - `intbrain_pm_constraints_validate`
  - `intbrain_import_vault_pm`
- В `_call_tool` добавлена маршрутизация на `pm/*` и `import/vault/pm` без изменения существующих tool names/контрактов.
- Для `intbrain_import_vault_pm` введён отдельный env-контур `INTBRAIN_CORE_ADMIN_TOKEN`:
  - при наличии токена отправляется `X-Core-Admin-Token`;
  - при отсутствии MCP возвращает локальную ошибку `config_error` без лишнего HTTP roundtrip.
- В [README.md](/int/tools/README.md) обновлён публичный список `intbrain-mcp` tools, добавлены требования по `INTBRAIN_CORE_ADMIN_TOKEN` и напоминание о перезапуске MCP runtime для refresh `tools/list`.

## 2026-03-28
### intbrain-mcp: people/group/jobs policy toolset expansion
- В [codex/bin/mcp-intbrain.py](/int/tools/codex/bin/mcp-intbrain.py) расширен универсальный MCP toolset новыми инструментами:
  - `intbrain_people_policy_tg_get`
  - `intbrain_group_policy_get`
  - `intbrain_group_policy_upsert`
  - `intbrain_jobs_list`
  - `intbrain_jobs_get`
  - `intbrain_job_policy_upsert`
  - `intbrain_jobs_sync_runtime`
  - `intbrain_policy_events_list`
- Обновлён роутинг MCP-адаптера на новые generic endpoints `groups/*`, `jobs/*`, `policies/events` без vendor-specific ветвлений.
- В [README.md](/int/tools/README.md) обновлён публичный список `intbrain-mcp` tools для OpenClaw/Codex и любых других agent profiles.

### Generic `intbrain-mcp` + OpenClaw thin adapter
- Добавлен универсальный MCP-адаптер `codex/bin/mcp-intbrain.py` и launcher `codex/bin/mcp-intbrain.sh` с единым toolset для memory-core `intbrain`.
- MCP toolset agent-agnostic: `intbrain_context_pack`, `intbrain_people_resolve`, `intbrain_people_get`, `intbrain_graph_neighbors`, `intbrain_context_store`, `intbrain_graph_link`.
- Добавлен `openclaw/bin/openclaw-intbrain-query.sh` как thin consumer-overlay: только трансляция в generic `/api/core/v1/context/pack` без OpenClaw-ветвлений в `intbrain`.
- Добавлен общий skill `codex/assets/codex-home/skills/intbrain-memory/SKILL.md` для DB-first retrieval/write-back по универсальному контракту.

### Canonical `.tmp` runtime-root для vault tooling
- `vault_sanitize.py` и `runtime_vault_gc.py` переведены на новый default runtime-root: `D:\int\.tmp\brain-runtime-vault` (VDS: `/int/.tmp/brain-runtime-vault`).
- В обоих скриптах добавлен единый override `--runtime-root`; при явном legacy path (`.../brain/runtime/vault`) выводится deprecation warning, но режим совместимости сохранён.
- `runtime_vault_gc.py` расширен: в `--apply` отдельно архивирует legacy path в `.tmp/<timestamp>/brain-runtime-vault-legacy` и очищает legacy-контур без удаления родительских `runtime/` каталогов.
- Обновлены `vault/installers/README.md` и корневой `README.md` с новым CLI-контрактом и примерами для local/VDS.

### Принят canonical vault tooling из `/int/brain`
- Добавлен новый machine-wide модуль `vault/installers/` с переносом installer-контента из `agents@vds.intdata.pro:/int/brain/tools/vault/installers`.
- `vault_sanitize.py` переведён на canonical контур `/int/tools`: добавлены `--tools-root`, профили whitelist (`strict|balanced|permissive`, default `strict`) и legacy-алиас `--enforce-whitelist`.
- Добавлен `runtime_vault_gc.py` для архивирования и очистки `runtime/vault` с поддержкой `--dry-run`/`--apply`.
- Обновлён `vault/installers/README.md` под новый путь запуска и профильную политику.
- Корневой `README.md` обновлён: `vault/installers/` зафиксирован как canonical machine-wide tooling для vault cleanup.

## 2026-03-27
### Введена строгая env-политика и repo-guard
- В `.gitignore` добавлен единый блок `ENV POLICY (strict)`: в git разрешены только `*.env.example`/`*.example`, любые `*.env` и `config/runtime/*.env` игнорируются.
- В `.githooks/pre-push` добавлен `ENV POLICY GUARD`, который блокирует push, если в индекс попали запрещённые env-файлы.
- В `AGENTS.md` зафиксировано обязательное правило хранения runtime-секретов только вне git.

### Убраны non-example env из индекса
- `codex/debate.env` удалён из git-индекса (локальная копия оставлена в рабочем дереве как ignored).
- Изменение сделано без переписывания истории и без ротации секретов по отдельному указанию владельца.

## 2026-03-23
### Добавлен owner-gate на push в удалённый main
- В repo добавлен tracked `.githooks/pre-push`, который проверяет только target `refs/heads/main`: для такого push нужен `ALLOW_MAIN_PUSH=1`, а source branch должен быть локальной `main`.
- В `AGENTS.md`, `README.md` и `GEMINI.md` явно зафиксирован локальный bootstrap `git config core.hooksPath .githooks`, потому что tracked hook не активируется автоматически в новом checkout/worktree.

### В корневой README возвращён полный исторический контент
- В корневой `README.md` перенесено полное содержимое удалённых repo-owned вложенных `README.md` из предыдущего состояния репозитория, без сокращения технических деталей.
- Для каждого бывшего файла добавлен отдельный подраздел в блоке `Подкаталоги и локальные инструкции`, при этом сами вложенные `README.md` не возвращались.
- При переносе нормализованы только заголовки и ссылки, чтобы корневая документация сохранила полноту и не содержала битых переходов.

### README, AGENTS и RELEASE приведены к единому стандарту
- Корневой релизлог переименован в `RELEASE.md` и закреплён как единственный repo-local source-of-truth для релизлога.
- Корневой `README.md` оставлен единственной repo-owned документацией и инструкцией, а вложенные repo-owned `README.md` в active owner-зонах больше не используются.
- `AGENTS.md` теперь явно разводит роли `README.md`, `AGENTS.md` и `RELEASE.md`, а также требует обновлять `README.md` в том же commit, если меняется задокументированная поверхность.

### Codex-home больше не требует отдельного owner-approval на `git pull`
- В `codex/assets/codex-home/AGENTS.md` убрано требование спрашивать владельца перед обычным `git pull`.
- Ограничение на `git push` без ведома владельца сохранено.

### Pre-work sync стал auto-fast-forward шагом
- `AGENTS.md` теперь разрешает выполнять `git pull --ff-only` автоматически на чистой ветке с валидным upstream, без отдельного вопроса владельцу.
- Автосинхронизация `git pull --ff-only` выполняется только на чистом дереве с корректным upstream; при блокере агент обязан остановиться и запросить дальнейшие действия с краткими вариантами решения.

### Инициализирован корневой релизлог
- В корне репозитория создан `RELEASE.md` как единый repo-local журнал изменений по локальным commit.
- `AGENTS.md` закрепляет обязательное обновление `RELEASE.md` перед каждым локальным commit.
- Альтернативные пути для релизлога, включая исторический `docs/`-путь, больше не считаются рабочими.

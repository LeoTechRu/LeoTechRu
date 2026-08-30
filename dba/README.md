# intDBA

`intDBA` — self-contained operator CLI для remote Postgres/Supabase профилей с этой Windows-машины без SSH на DB-host.

## Что умеет v1

- `doctor` — проверить native PostgreSQL CLI, TCP и SQL-доступ к профилю;
- `sql` — выполнить ad-hoc SQL;
- `file` — выполнить SQL-файл;
- `dump` / `restore` — выгрузить и залить dump;
- `clone` — перенести dump из одной БД в другую через локальную машину;
- `copy` — выгрузить query в CSV и залить в target table;
- `migrate status` — сравнить `migration_manifest.lock` из `/int/data` с remote `public.schema_migrations`;
- `migrate data` — применить incremental или bootstrap migration flow `/int/data`.
- `project-migrate punktb-legacy-assess` — перенести legacy PunktB assessment data между профилями через `psql` staging flow.
- `project-migrate punktb-prod-dev-refresh` — перезалить `assess.specialists`, `assess.clients`, `assess.diag_results` из `punkt_b_prod` в `intdata` dev со strict read-only source и dev-side `auth` bootstrap.
- `local-test run` — поднять temporary local Supabase runtime под owner-контролем, применить `/int/data` migrations + `init/seed.sql` и опционально прогнать SQL smoke.
- `local-test stop` — остановить temporary local Supabase runtime без backup.

## Layout

- `dba.ps1` / `dba.cmd` — основные launchers;
- `lib/dba.py` — Python core;
- `.env.example` — bootstrap-шаблон профилей;
- `.env` — локальный untracked runtime-файл;
- `/int/.tmp/tools/dba/` (`D:\int\.tmp\tools\dba\` локально) и `logs/` — runtime-артефакты, не идут в git.

## Требования

- Windows PowerShell;
- `python` или `py` в `PATH`;
- `psql`, `pg_dump`, `pg_restore` в `PATH` или в стандартном каталоге `C:\Program Files\PostgreSQL\<version>\bin`;
- сетевой доступ до нужных PostgreSQL endpoint'ов;
- для `migrate *`: на Windows локальный `D:\int\data` не является default; dev backend work выполняется через `dev@intdata.pro:/int/data`, а disposable/local flow требует явный `--repo` или `DBA_DATA_REPO`;
- на Linux remote host допускается sibling checkout `/int/data`;
- для `migrate data --mode incremental`: `bash` из Git for Windows или иной совместимый `bash`.

## Профили

Формат переменных:

```env
DBA_PROFILE__INTDATA_DEV__PGHOST=api.intdata.pro
DBA_PROFILE__INTDATA_DEV__PGPORT=5432
DBA_PROFILE__INTDATA_DEV__PGDATABASE=intdatadb-dev
DBA_PROFILE__INTDATA_DEV__PGUSER=intdata_dev
DBA_PROFILE__INTDATA_DEV__PGPASSWORD=<secret>
DBA_PROFILE__INTDATA_DEV__PGSSLMODE=require
DBA_PROFILE__INTDATA_DEV__WRITE_CLASS=nonprod
```

CLI обращается к такому профилю как `intdata-dev`.

`WRITE_CLASS`:

- `nonprod` — достаточно `--approve-target <profile>`;
- `prod` — дополнительно требуется `--force-prod-write`.

## Guardrail entrypoints (Punkt-B)

Для безопасной модели доступа используйте Python wrappers из `D:\int\tools\dba\bin`:

- `pg-prod-ro.py` -> `punktb-prod-ro` (`db_readonly_prod`)
- `pg-legacy-ro.py` -> `punktb-legacy-ro` (`db_readonly_prod` on `punkt_b_legacy_prod`)
- `pg-dev-ro.py` -> `intdata-dev-ro` (`db_readonly_dev`)
- `pg-prod-migrate.py` -> `punktb-prod-migrator` (`db_migrator_prod`)
- `pg-dev-migrate.py` -> `intdata-dev-migrator` (`db_migrator_dev`)
- `pg-prod-admin.py` -> `punktb-prod-admin` (`agents`, breakglass)
- `pg-dev-admin.py` -> `intdata-dev-admin` (`agents`, breakglass)
- `pg-test-bootstrap.py` -> retired stop-signal; remote disposable test contour больше не поддерживается

Запуск одинаковый на Windows и Linux:

```bash
python /int/tools/dba/bin/pg-prod-ro.py --doctor
python /int/tools/dba/bin/pg-dev-migrate.py --path /path/to/change.sql --write --confirm-target intdata
```

### Важно

- Supabase system roles (`authenticator`, `anon`, `authenticated`, `service_role`, `supabase_*`) в этой модели считаются immutable.
- Wrappers должны использовать только custom роли.
- Raw `psql` с ad-hoc DSN для agent workflow запрещен process-policy.
- `vds.intdata.pro` больше не используется как disposable test contour для `/int/data`; live remote contour остаётся только `intdata`.
- Для dev backend intdata не используйте локальный `D:\int\data`; заходите в `dev@intdata.pro:/int/data` и запускайте owner flow там.

## Local disposable Supabase runner

Canonical disposable workflow для `/int/data` smoke/bootstrap с нуля:

```bash
pwsh -File D:\int\tools\dba\dba.ps1 local-test run --confirm-owner-control I_ACKNOWLEDGE_LOCAL_ONLY
```

Основные свойства:

- нужен Docker;
- нужен Supabase CLI (`supabase`) или fallback через `npx supabase`;
- workspace создаётся в ignored `/int/.tmp/tools/dba/local-supabase/<stamp>`;
- после `supabase start` tool применяет owner scripts из явно переданного локального repo (`--repo`/`DBA_DATA_REPO`), затем `init/seed.sql`;
- SQL smoke можно передать через `--smoke-file`;
- по умолчанию runtime останавливается сам; для ручной диагностики используйте `--keep-running` и затем `local-test stop`.

## PunktB legacy assessment migrator

Core workflow lives in `dba`; project-specific PunktB launch parameters are thin wrappers.

Rehearsal against dev target:

```bash
python D:\int\tools\dba\lib\dba.py project-migrate punktb-legacy-assess --dry-run --source punktb-legacy-ro --target intdata-dev-migrator
```

Release apply target remains guarded:

```bash
python D:\int\tools\dba\lib\dba.py project-migrate punktb-legacy-assess --apply --source punktb-legacy-ro --target punktb-prod-migrator --approve-target punktb-prod-migrator --force-prod-write
```

Properties:

- source profile is executed read-only;
- target apply uses the existing `--approve-target` and `--force-prod-write` gates;
- dry-run stages target changes and rolls them back;
- clients are matched by normalized email, not numeric legacy ids;
- duplicate legacy client rows with the same normalized email merge into one target client;
- legacy `public.clients.results` JSONB array entries are staged into `assess.diag_results` with deterministic ids and `_import.legacy_punktb` metadata.

## PunktB prod -> intdata dev refresh

Dry-run against the approved dev admin target:

```bash
python D:\int\tools\dba\lib\dba.py project-migrate punktb-prod-dev-refresh --dry-run --source punktb-prod-ro --target intdata-dev-admin
```

Apply with full replace semantics in the approved dev scope:

```bash
python D:\int\tools\dba\lib\dba.py project-migrate punktb-prod-dev-refresh --apply --source punktb-prod-ro --target intdata-dev-admin --approve-target intdata-dev-admin
```

Properties:

- source export stays read-only and uses `psql \copy (SELECT row_to_json(...))`, not `pg_dump`;
- fallback source `punktb-prod-migrator` is allowed only when the session is still forced into `default_transaction_read_only=on`;
- target requires `intdata-dev-admin` (`agents` on `intdata`), because the workflow fully replaces the approved dev rows;
- target bootstraps only the required `auth.users` and `auth.identities` rows for imported emails and does not read prod auth tables.

## Safety

- Все mutating-команды требуют явный `--approve-target`.
- Для профилей класса `prod` обязателен `--force-prod-write`.
- `sql` и `file` по умолчанию запускаются в `default_transaction_read_only=on`.
- `local-test run` требует `--confirm-owner-control I_ACKNOWLEDGE_LOCAL_ONLY` и не имеет unattended default path.
- Типовые runtime-ошибки `psql/pg_dump/pg_restore`, `bash` и TCP-доступа переводятся в обычные `intDBA:` сообщения без Python traceback.
- Типовые runtime-ошибки `docker` и `supabase` для local runner тоже переводятся в обычные `intDBA:` сообщения.
- Секреты профиля передаются внешним PostgreSQL CLI через окружение процесса и не вшиваются в argv.
- Для `migrate data --mode incremental` `dba` сам добавляет найденный PostgreSQL `bin` в `PATH` дочернего `bash`, если глобальный `PATH` на машине ещё не обновлён.
- Временные dump/CSV-файлы складываются в `/int/.tmp/tools/dba/`.
- `.env` не должен попадать в git.

# INT-798: единый ProIntData Google credential bundle

## Why

`prointdata@gmail.com` сейчас обслуживается несколькими независимыми OAuth
копиями: `gws`, `gog`, Hermes и профильные Hermes-инстансы на ПК и VDS.
Потребители читают разные реальные stores: JSON, encrypted credentials,
keyring и rclone config. Повторная авторизация обновляет только часть копий,
из-за чего остальные получают `invalid_grant` или revoked token.

## Decision

Использовать один versioned credential bundle и атомарно реплицировать его в
защищённые host-local stores на ПК и VDS. Выбор владельца: репликация stores,
а не обязательная зависимость каждого локального вызова от доступности VDS.

Плагин `leonid-private` содержит только private routing и runbook. Refresh
token, client secret и access token не входят в плагин, Git, OpenSpec,
GitHub Issues, Codex home или логи.

## What Changes

- Добавить в `/int/tools` cross-platform CLI для:
  - проверки и нормализации bundle;
  - refresh-based preflight без вывода секретов;
  - атомарного apply в Windows Credential Manager и systemd-creds;
  - materialization Hermes token и native `gog` import;
  - redacted status/fingerprint и read-only smoke;
  - однокомандного fan-out с ПК на VDS по существующему SSH route.
- Маршрутизировать `gws` через Hermes `gws_bridge`, который получает access
  token из актуального bundle без отдельного `gws auth login`.
- Добавить в `leonid-private` один навык ProIntData Google, который требует
  preflight и использует только tracked wrappers.
- Считать rclone отдельным consumer: обновление его config допустимо только
  явным subcommand; перезапуск VFS не является скрытой частью Google preflight.
- Исправить Windows OpenSpec launcher, который сейчас возвращает success при
  нулевом `node_modules/.bin/openspec`.

## Safety Boundaries

- Никакого revoke/logout в автоматическом repair.
- Никаких секретов в argv, stdout/stderr, временных repo-файлах или issue.
- Apply выполняется только после offline validation и успешного OAuth refresh.
- Partial apply завершается ошибкой с матрицей consumer status; предыдущий
  host-local bundle сохраняется до успешной атомарной замены.
- Старые credential/state файлы не удаляются в рамках change.
- Push `/int`, production и unmanaged infrastructure остаются owner-gated.

## Acceptance

- Одна bundle version и один refresh-token fingerprint подтверждены на ПК/VDS.
- `gog`, `gws_bridge` и Hermes read paths проходят реальные read-only API
  проверки без рестарта Codex или Hermes.
- Повторный apply идемпотентен.
- Временная недоступность VDS не ломает уже синхронизированный ПК.
- Secrets scan и focused tests проходят.
- Auth/security diff получает независимый review до runtime rollout.

# Punkt B Unisender MCP

Минимальный MCP-инструмент для Unisender email API Пункт Б.

## Инструменты

- `unisender_health` — конфигурация без вывода ключа;
- `unisender_lists_get`, `unisender_contact_total` — чтение списков и размера базы;
- `unisender_api_read` — allowlist быстрых read-методов;
- `unisender_api_call` — полный UniSender API; для всех изменяющих методов обязателен `confirm_mutation=true`;
- `unisender_email_send` — одно письмо только с `confirm_send=true`.

Массовые кампании и изменение базы доступны через `unisender_api_call` только с явным подтверждением в вызове.

## Секреты и запуск

Ключ не хранится в репозитории или MCP-конфигурации. ПК runner читает Windows Credential Manager через `.runtime/credentials/unisender-api-credential.ps1`, VDS — зашифрованный `systemd-creds` credential через `.runtime/credentials/unisender-api-credential`.

ПК Codex: `codex mcp add unisender -- cmd /c D:\int\tools\unisender-mcp\run-unisender-mcp.cmd`

VDS Codex: `codex mcp add unisender -- /int/tools/.runtime/mcp-launchers/unisender.sh`

Hermes использует те же launchers.

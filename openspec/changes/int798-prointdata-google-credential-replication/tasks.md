- [x] Зафиксировать inventory реальных Google credential stores без вывода
      секретов.
- [x] Получить решение владельца: защищённая репликация stores.
- [x] Создать `INT-798` и связать OpenSpec change.
- [ ] Реализовать bundle schema, validation, refresh preflight и redacted
      fingerprint.
- [ ] Реализовать Windows Credential Manager adapter и POSIX systemd-creds
      adapter.
- [ ] Реализовать atomic consumer apply для Hermes, `gog` и `gws_bridge`.
- [ ] Реализовать fan-out ПК -> VDS по SSH без secret argv/temp/log exposure.
- [ ] Добавить focused unit/integration tests и secrets scan.
- [ ] Добавить private routing skill в `leonid-private`; secret-free validate.
- [ ] Получить независимый auth/security review точного commit range.
- [ ] Выполнить owner-authorized runtime rollout без revoke/logout/cleanup.
- [ ] Проверить реальные read-only API calls в матрице Codex/Hermes x ПК/VDS.
- [ ] Записать final evidence в `INT-798`; push `/int` оставить NOT RUN без
      отдельного разрешения.

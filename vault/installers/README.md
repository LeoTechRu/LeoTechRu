# Vault Installers / Sanitize

## `vault_sanitize.py`

Idempotent cleanup script that keeps Obsidian vault content in `/2brain` (or `D:\Yandex.Disk\2brain`) and moves operational artifacts into canonical runtime root `.tmp/brain-runtime-vault` and installer paths in `int/tools`.

### Local

```powershell
python d:\int\tools\vault\installers\vault_sanitize.py --dry-run
python d:\int\tools\vault\installers\vault_sanitize.py --apply
python d:\int\tools\vault\installers\vault_sanitize.py --dry-run --runtime-root D:\int\.tmp\brain-runtime-vault
```

### VDS

```bash
python3 /int/tools/vault/installers/vault_sanitize.py --vault-root /2brain --brain-root /int/brain --tools-root /int/tools --dry-run
python3 /int/tools/vault/installers/vault_sanitize.py --vault-root /2brain --brain-root /int/brain --tools-root /int/tools --apply
python3 /int/tools/vault/installers/vault_sanitize.py --vault-root /2brain --brain-root /int/brain --tools-root /int/tools --runtime-root /int/.tmp/brain-runtime-vault --dry-run
```

### Whitelist profile

```powershell
python d:\int\tools\vault\installers\vault_sanitize.py --profile strict --dry-run
python d:\int\tools\vault\installers\vault_sanitize.py --profile strict --apply
```

`--enforce-whitelist` is kept as a deprecated alias for `--profile strict`.

`--runtime-root` is optional. By default scripts use:
- Local: `D:\int\.tmp\brain-runtime-vault`
- VDS: `/int/.tmp/brain-runtime-vault`

Legacy path `/int/brain/runtime/vault` (when already on VDS) is supported only as explicit override and emits a deprecation warning.

## `runtime_vault_gc.py`

Archives and resets generated vault runtime artifacts in canonical `.tmp` root and can archive legacy `brain/runtime/vault`.

```powershell
python d:\int\tools\vault\installers\runtime_vault_gc.py --dry-run
python d:\int\tools\vault\installers\runtime_vault_gc.py --apply
python d:\int\tools\vault\installers\runtime_vault_gc.py --dry-run --runtime-root D:\int\.tmp\brain-runtime-vault
```

VDS:

```bash
python3 /int/tools/vault/installers/runtime_vault_gc.py --brain-root /int/brain --archive-root /int/.tmp --dry-run
python3 /int/tools/vault/installers/runtime_vault_gc.py --brain-root /int/brain --archive-root /int/.tmp --apply

# explicit legacy override (compatibility mode, prints warning)
python3 /int/tools/vault/installers/runtime_vault_gc.py --brain-root /int/brain --runtime-root /int/brain/runtime/vault --dry-run
```

# Repo Ops

`repo-ops/` is the neutral home for reusable repository operations helpers.

It exists to prevent product adapters from becoming dumping grounds for generic scripts. Product-specific wrappers and profiles belong outside this public reusable tools repo; reusable implementation code belongs here or in a more specific top-level tool.

## Current Scope

- Safe cleanup utilities for repo/runtime artifacts.
- Future home for parameterized issue, gate, release and hook helpers that are not tied to one product.

## Boundaries

- No secrets or host-local runtime state.
- No product-specific endpoints, credentials, private hostnames or local machine paths.
- No product-core code.
- No replacement for Node-owned coordination (`intnode coord`), `dba` or `delivery` when those tools already own the capability.

## Commands

```powershell
python repo-ops/bin/agent_tmp_cleanup.py --dir .runtime/repo-ops/tmp --dry-run
python repo-ops/bin/agent_lock_cleanup.py --dry-run
```

Older product-adapter wrappers should call these entrypoints instead of carrying duplicated cleanup logic.

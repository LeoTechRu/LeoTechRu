# ProIntData Google credentials

INT-798 runtime helper for one versioned Google OAuth bundle replicated into
protected local stores on Windows and Linux.

## Security model

- Windows source: Credential Manager target
  `intdata/google/prointdata/oauth-bundle-v1`.
- Linux source: user-scoped systemd encrypted credential
  `~/.config/credentials/prointdata-google-oauth-bundle-v1.cred`.
- Secret input and SSH replication use stdin. Tokens are never command-line
  arguments or diagnostic output.
- `status` prints only bundle version, account, scope count and truncated
  SHA-256 fingerprints.
- `create` and `receive` perform a real OAuth refresh and verify
  `prointdata@gmail.com` before storing.
- No command revokes grants, logs out consumers, removes legacy state or
  restarts services.

## Commands

```powershell
# Validate an authorized-user token and store it in Windows Credential Manager.
Get-Content -Raw $tokenPath |
  .\prointdata-google.ps1 create

# Apply the protected bundle to Hermes and gog.
.\prointdata-google.ps1 apply

# Redacted status.
.\prointdata-google.ps1 status

# Run gws with an in-memory access token from the protected bundle.
.\prointdata-google.ps1 gws drive files list

# Check and replicate the current protected bundle to VDS, then apply locally.
.\prointdata-google.ps1 replicate --ssh-target vds
```

```bash
# VDS status.
./prointdata-google status

# The VDS defaults include the main Hermes home and existing intbrain/intbridge
# profile homes. Explicit --hermes-home values replace that default set.
./prointdata-google apply
```

`gws` must be invoked through `prointdata-google gws ...` or the existing
Hermes `gws_bridge.py`. Both refresh an access token for each command instead
of using the legacy gws refresh store. `gog` is updated through its native
`auth tokens import -` interface.

Runtime rollout overwrites credential consumer files and therefore remains an
explicit, exact-path approval step. rclone is intentionally outside implicit
apply because a live VFS mount may require a separately approved service
restart.

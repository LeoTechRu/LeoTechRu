# ProIntData Google credentials

## ADDED Requirements

### Requirement: One logical bundle MUST govern every supported consumer

The system MUST represent the ProIntData Google OAuth authority as one
versioned bundle with a stable account, OAuth client, refresh token, granted
scopes, creation timestamp and non-secret fingerprint.

#### Scenario: Consumers are synchronized

- **WHEN** status is collected on PC and VDS
- **THEN** every supported consumer reports the same bundle version
- **AND** every refresh-token fingerprint matches without exposing the token.

### Requirement: Replication MUST preserve protected host-local storage

The system MUST keep the canonical host copies in Windows Credential Manager
and systemd-creds and MUST NOT store secrets in plugins, Git, Codex home,
issues, memory, logs or command arguments.

#### Scenario: A bundle is applied

- **WHEN** a validated bundle is replicated
- **THEN** secret transport uses stdin over the existing authenticated SSH
  channel
- **AND** host-local writes are atomic and owner-only
- **AND** diagnostics contain only version, status, field presence and
  truncated cryptographic fingerprints.

### Requirement: Apply MUST validate before replacing working credentials

The system MUST reject malformed, wrong-account, wrong-client, missing-scope
or non-refreshable bundles before replacing a protected store.

#### Scenario: OAuth refresh fails

- **WHEN** Google returns `invalid_grant`, revoked or another refresh failure
- **THEN** apply fails closed
- **AND** no consumer is changed
- **AND** the error is redacted.

### Requirement: Supported consumers MUST update without agent restart

The system MUST make updated credentials available to Hermes Google scripts,
`gws_bridge` and `gog` without restarting Codex or Hermes.

#### Scenario: Bundle version changes

- **WHEN** the new bundle is successfully applied
- **THEN** Hermes reads the atomically replaced token file on the next command
- **AND** `gws_bridge` derives an access token from that file
- **AND** `gog` receives the same refresh token through its native stdin import.

### Requirement: Fan-out MUST be idempotent and observable

The replication command MUST safely repeat the same bundle and MUST report a
per-host/per-consumer result matrix.

#### Scenario: The same version is applied again

- **WHEN** all target fingerprints already match
- **THEN** the command performs no unnecessary credential mutation
- **AND** reports `CURRENT` for each matching consumer.

### Requirement: Host independence MUST survive VDS unavailability

The selected replicated-store design MUST allow an already synchronized PC to
continue Google operations while VDS is temporarily unavailable.

#### Scenario: VDS cannot be reached

- **WHEN** local preflight finds a current valid bundle and SSH fan-out is not
  requested
- **THEN** local `gog`, `gws_bridge` and Hermes operations remain available
- **AND** status explicitly reports remote state as not verified.

### Requirement: Revocation and cleanup MUST stay explicit

Automated preflight and repair MUST NOT revoke OAuth grants, call logout,
delete old stores, restart rclone VFS or remove runtime state.

#### Scenario: A stale legacy credential exists

- **WHEN** the new bundle is active
- **THEN** the legacy file may be reported as stale
- **AND** remains untouched until an exact destructive command is separately
  approved.

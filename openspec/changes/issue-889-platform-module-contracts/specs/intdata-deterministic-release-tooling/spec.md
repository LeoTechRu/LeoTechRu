# intData Deterministic Release Tooling Specification

## Purpose

Define the public reference CLI and immutable release projections without granting
publication, activation, DB or runtime authority.

## ADDED Requirements

### Requirement: CLI MUST expose a closed non-effectful command surface

Distribution `intdata-platform-tooling` MUST expose `intdata-tools` commands for
schema validate/canonicalize/digest, module/installation validate, lock verify,
release pack/sign/verify, connector conformance and family validate/generate/check.
It MUST NOT expose publish, deploy, activate, DB apply or runtime commands.

#### Scenario: Command inventory is inspected

- **WHEN** installed CLI help is enumerated
- **THEN** only the declared command families exist
- **AND** validation and verification perform no outward effect

### Requirement: Release packaging MUST be deterministic and tracked-input only

The release packager MUST produce deterministic artifacts from an explicit input
boundary. Development validation MAY inspect explicit worktree input. Installable
release pack MUST accept only clean tracked commit-bound source with canonical origin and
advertised-remote reachability. It MUST reject links, traversal, devices, path
collisions, Windows reserved paths, ambient host paths, secret-like bytes, output
inside source/managed state/`CODEX_HOME`, missing license/SBOM/scan evidence and
nondeterministic metadata.

#### Scenario: Identical releases are packed on Windows and Linux

- **WHEN** exact tracked input and source epoch are used
- **THEN** archive entries, modes, ownership, timestamps and bytes are identical
- **AND** SHA-256 is identical

#### Scenario: Malicious input is packed

- **WHEN** input contains traversal, symlink, hardlink, device, case collision,
  reserved Windows name, secret fixture or nested output
- **THEN** packing fails before any installable artifact is emitted

### Requirement: Production signing MUST use a bounded external signer

`release sign` MUST implement standard DSSE v1 with Ed25519 over exact
`PAE(payloadType, payload)` bytes. Payload type MUST be
`application/vnd.intdata.release-manifest.v1+json`; payload MUST be canonical
ReleaseManifest bytes. The argv-only bounded signer MUST receive public PAE bytes
through closed stdin/stdout protocol, MUST NOT invoke a shell and MUST return one
raw Ed25519 signature. CLI MUST construct a closed envelope with standard padded
RFC 4648 base64 payload/signature, exactly one signature and non-authoritative
`keyid`, then verify PAE/signature/trust before writing. Digest-only binding MUST be
a separately versioned input and MUST NOT be labelled DSSE. Production key material
MUST NOT enter Tools. File private keys MUST be forbidden for production signing
and available only through an explicitly named development path.

#### Scenario: Signer is invalid or unavailable

- **WHEN** signer times out, emits excess output, uses wrong/revoked/expired role,
  signs another PAE or returns malformed/multiple/non-canonical envelope data
- **THEN** signing fails closed and no trusted envelope is written

### Requirement: TrustBundle MUST be pinned and anti-rollback

`TrustBundleV1` MUST be the only source of key material, roles, validity and
revocation. Verification MUST start from a separately pinned trusted root/bundle,
MUST bind bundle ID/version/digest, MUST reject decreasing revision and MUST apply
an exact trusted-time policy. RegistrySnapshot MUST contain only accepted
role/key IDs and trust-bundle reference; DSSE `keyid` MUST be only a hint. Registry,
module/release and installation-actor roles MUST be distinct.

#### Scenario: Release supplies its own or older trust bundle

- **WHEN** a release replaces the pinned bundle or rolls revision/revocation back
- **THEN** offline verification fails before trusting any release signature

### Requirement: Offline verification MUST bind all release evidence

`release verify` MUST operate without network and bind ReleaseManifest source,
artifacts, sizes, SBOM, ScanAttestation, compatibility, rollback predecessor,
signature role, pinned TrustBundle revision/digest and trusted-time decision.

#### Scenario: A release artifact is altered

- **WHEN** any manifest, artifact, SBOM, scan evidence, signature or trust entry is
  changed after signing
- **THEN** offline verification fails with a closed reason

### Requirement: Family release MUST be one immutable snapshot

A release MUST contain catalog, schema, marketplace, release lock, activation,
SHA256SUMS, SPDX SBOM, release manifest, DSSE envelope and scan attestation with
one release ID and mutually consistent hashes. Tools MUST only generate/verify
activation; switching the active pointer requires separate authority.

#### Scenario: Release projections disagree

- **WHEN** any ID, hash, source provenance or activation pointer differs
- **THEN** family check fails and publication/activation remains unavailable

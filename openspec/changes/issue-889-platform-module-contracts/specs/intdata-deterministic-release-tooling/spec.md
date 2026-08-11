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

### Requirement: Trust authorities MUST be pinned, anti-rollback and non-overlapping

`TrustBundleV1` MUST be the only source of non-release registry, module,
installation-actor and JWT key material, roles, validity and revocation. It MUST
carry only a pinned `ReleaseVerificationKeySetV1` ID/revision/digest and bootstrap
root-set digest reference and MUST NOT duplicate `release.artifact.signing` public
keys or lifecycle. The KeySet MUST exclusively own online release artifact keys.
Verification MUST start from separately pinned trust, bind every applicable
ID/version/revision/digest, reject rollback and apply exact trusted time.
RegistrySnapshot MUST contain only accepted IDs/references; DSSE `keyid` is only a
hint. Registry, module, installation-actor, JWT, release root and release artifact
roles MUST remain non-overlapping.

#### Scenario: Release supplies its own or older trust bundle

- **WHEN** a release replaces the pinned bundle or rolls revision/revocation back
- **THEN** offline verification fails before trusting any release signature

### Requirement: Release verification key lifecycle MUST require offline root quorum

Tools MUST define closed `ReleaseVerificationKeySetV1` schema plus canonical and
adverse vectors and MUST NOT contain production keys. Its RFC 8785 canonical
payload MUST be wrapped in standard DSSE v1 with payload type
`application/vnd.intdata.release-keyset.v1+json`. Acceptance MUST require valid
Ed25519 signatures from at least two cryptographically verified pairwise-distinct
root public-key fingerprints in one immutable three-key offline root set with
role `release.trust.root`; `keyid` MUST be only a hint and duplicate IDs or public
key aliases MUST NOT count toward quorum.

The exact bootstrap root public-set digest MUST be pinned out of band in
installer/bootstrap trust and repeated in accepted `InstallationLockV1`; a lock
MUST NOT bootstrap a different root set by itself. The pinned digest MUST be
`sha256:` plus lowercase SHA-256 of RFC 8785 bytes for a closed
`ReleaseBootstrapRootSetV1` descriptor containing exactly `schema_version=1`,
`role=release.trust.root`, `threshold=2` and `keys`. `keys` MUST contain exactly
three entries with pairwise-unique `key_id` and pairwise-unique decoded Ed25519
public-key bytes, sorted ascending by unsigned UTF-8 `key_id`; each entry MUST
contain exactly `key_id` matching `[A-Za-z0-9._-]{1,128}`,
`algorithm=Ed25519` and standard padded RFC 4648 `public_key_base64` decoding to
exactly 32 bytes. No other root-set serialization may establish the pin.

Bootstrap KeySet MUST have `revision=1` and null `previous_digest`. Every later
KeySet MUST have `revision = previous revision + 1` and `previous_digest` equal to
`sha256:` plus lowercase SHA-256 of the exact previous RFC 8785 payload bytes.
`generated_at` and lifecycle times MUST use UTC `YYYY-MM-DDTHH:MM:SSZ`. The closed payload MUST bind
exact `schema_version`, monotonic `revision`, `previous_digest` (null only at
bootstrap), `generated_at`, `bootstrap_root_set_digest` and the complete canonical
active/retired/revoked lifecycle of every online key. Each key entry MUST bind
`key_id`, `role`, public key, state, validity window and retirement or revocation
time and reason and MUST contain no private material.

Online keys with role `release.artifact.signing` MUST sign artifacts only. They
MUST NOT advance or revoke trust, sign key sets or change root quorum. A consumer
MUST verify canonical payload/digest, 2-of-3 distinct root quorum, root roles,
bootstrap pin, prior digest, exact revision increment by one and every lifecycle
transition before atomic persistence. Fork, rollback, skipped revision, key
resurrection, unknown role/field and insufficient quorum MUST fail closed without
fallback.

An online key's `key_id`, role, public key and initial validity start MUST remain
immutable across revisions. Keys MUST never be deleted, reused or aliased: the
same decoded public-key bytes MUST NOT appear under another `key_id`. State MAY move
from active to retired or revoked and from retired to revoked, never backward.
A retired key MUST remain published indefinitely and verify only manifests whose
trusted signed time is within its admitted validity interval and no later than
`retired_at`. A revoked key MUST remain listed indefinitely and invalidate every
release signed by that key regardless of signing time. Retirement/revocation times
and non-empty reasons MUST match state; ambiguous or contradictory lifecycle
fields MUST fail closed.

Root-set replacement and emergency recovery MUST NOT be v1 rotation. They require
a separate full owner-approved ceremony and new installer/bootstrap and
InstallationLock trust anchor. Offline external root signers MUST receive only
public standard DSSE PAE bytes no larger than 262144 bytes plus an opaque key
reference and MUST independently verify payload type, schema, previous digest,
revision and root-set pin before signing. Oversize PAE MUST fail before signer
invocation. Root private material MUST NOT enter Tools or Backend runtime.

#### Scenario: Two distinct offline roots advance the key set

- **WHEN** revision N+1 has the exact prior digest and two valid signatures from
  distinct admitted `release.trust.root` keys
- **THEN** the consumer accepts one atomic new online-key lifecycle snapshot
- **AND** the accepted bootstrap root-set digest remains the out-of-band pin

#### Scenario: Trust history or quorum is invalid

- **WHEN** a key set has one signer repeated or aliased by another `key_id`, fewer than two valid roots, wrong
  role, another root-set digest, a fork, rollback, skipped revision, resurrection,
  unknown field, deleted/reused/aliased key material, invalid root descriptor/digest or invalid
  retired/revoked lifecycle transition
- **THEN** verification fails before persistent trust state changes


### Requirement: Offline verification MUST bind all release evidence

`release verify` MUST operate without network and bind ReleaseManifest source,
artifacts, sizes, SBOM, ScanAttestation, compatibility, rollback predecessor,
signature role, pinned TrustBundle revision/digest, pinned
ReleaseVerificationKeySet ID/revision/digest/bootstrap-root reference and
trusted-time decision, without duplicated release key material.

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

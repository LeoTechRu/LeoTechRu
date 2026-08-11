# intData Public Contracts Specification

## Purpose

Define stable language-neutral platform composition and release contracts owned by
Tools and consumed by Backend and standalone installations.

## ADDED Requirements

### Requirement: Platform v1 schema set MUST be closed and offline

Tools MUST publish `contracts/platform/v1/schema-set.json` and schemas for Module,
Installation, Registry, Resolver input/result, InstallationLock, Release,
Signature, Trust and Scan. Every schema MUST have stable
`urn:intdata:schema:<type>:v1`, filename, version and SHA-256 linkage. Remote schema
resolution and unknown schema/fields MUST be rejected.

#### Scenario: A consumer loads the schema set offline

- **WHEN** network access is disabled and a valid fixture is validated
- **THEN** all references resolve from the tracked schema set
- **AND** every schema digest matches its registry entry
- **AND** removing, replacing or adding an unknown schema fails closed

### Requirement: Signed JSON MUST use one canonical byte representation

Input MUST be strict UTF-8 JSON without BOM, duplicate keys, trailing bytes,
invalid Unicode, floating values, unsafe integers or unknown fields. Signed
integers MUST be within `[-9007199254740991, 9007199254740991]`; larger exact
values MUST use canonical decimal strings. Schema validation MUST precede
canonicalization. Canonical bytes MUST follow RFC 8785 JCS without trailing
newline; digests MUST be lowercase SHA-256.

#### Scenario: Windows and Linux canonicalize the same document

- **WHEN** exact schema/input/tool versions are used on both hosts
- **THEN** canonical bytes and SHA-256 are byte-identical
- **AND** safe integer boundaries and UTF-16 non-BMP key ordering match vectors
- **AND** `±9007199254740992`, lone surrogates, duplicate keys, floats, invalid
  Unicode and trailing bytes fail closed

### Requirement: Module and installation authority MUST remain separated

`ModuleManifestV1` MUST describe immutable module provenance, capabilities,
dependencies, artifacts, migrations, routes, web modules, runtime units,
configuration and compatibility. `InstallationManifestV1` MUST describe desired
modules/capabilities/origins/policies without secrets or inferred internal units.
`InstallationLockV1` MUST bind exact Installation revision/digest,
RegistrySnapshot digest, resolver version, solver-policy version, policy-input
digest, resolved graph and runtime bindings. Accepted lock MUST have a detached
signature from TrustBundle role `installation-actor` after Registry/Module/Release
signature verification.

#### Scenario: Desired state resolves to a lock

- **WHEN** Backend resolves an accepted registry and installation manifest
- **THEN** result binds exact module/artifact/route/migration/MCP/runtime entries
- **AND** no secret value is copied into public contracts
- **AND** changing a bound artifact changes the lock digest
- **AND** plan/apply/recovery rejects an unsigned or wrong-role lock

### Requirement: Resolver contract MUST be transport-neutral

Tools MUST define `ResolverInputV1` and `ResolverResultV1` plus black-box fixtures;
it MUST NOT implement or own Backend graph resolution, policy, persistence, API,
installation actor or plan/apply/rollback. Conformance MUST require a minimal
transitive solution, exact deterministic tie-breaking, byte-identical lock and
reverse-dependency disable rejection.

#### Scenario: An incompatible graph is resolved

- **WHEN** a fixture has missing capability, conflict, route collision, broken
  migration lineage, missing secret custody, unbound MCP, artifact drift or unsafe
  reverse-dependency disable
- **THEN** resolver conformance requires one deterministic closed error
- **AND** no partial result is returned

#### Scenario: Several valid solutions exist

- **WHEN** exact input and policy versions admit more than one compatible graph
- **THEN** minimal transitive set and exact tie-break select one byte-identical lock

### Requirement: Platform Lite MUST have no hidden central dependency

The same contracts MUST support customer origins, a local registry snapshot and a
local artifact mirror. Artifact identity MUST be digest/size rather than URL.

#### Scenario: Lite acceptance runs offline

- **WHEN** `intdata.pro`, GitHub and central release storage are blocked
- **THEN** resolution and artifact verification succeed from local inputs
- **AND** any attempted central network dependency fails the suite

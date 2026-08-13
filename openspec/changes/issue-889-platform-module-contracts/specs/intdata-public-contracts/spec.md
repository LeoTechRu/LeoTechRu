# intData Public Contracts Specification

## Purpose

Define stable language-neutral platform composition and release contracts owned by
Tools and consumed by Backend and standalone installations.

## ADDED Requirements

### Requirement: Platform v1 schema set MUST be closed and offline

Tools MUST publish `contracts/platform/v1/schema-set.json` and schemas for Module,
Installation, Registry, Resolver input/result, InstallationLock, Release,
Signature, Trust, Scan, `PlatformProductAssertionV1`,
`ReleaseVerificationKeySetV1` and `BridgeOAuthRegistrationApprovalReceiptV1`. Every schema MUST have stable
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

### Requirement: Platform product assertion MUST have one closed schema and vector set

Tools MUST publish `PlatformProductAssertionV1` with schema ID
`urn:intdata:schema:platform-product-assertion:v1` and positive/adverse
cross-language vectors. The decoded JWT protected header MUST contain exactly
`alg="ES256"`, `typ="at+jwt"` and `kid` matching `[A-Za-z0-9._-]{1,128}`.
All claims MUST be required, non-null and closed to `iss`, scalar `aud`, `sub`,
`principal_type`, `organization_id`, `product_id`, `client_id`, `session_id`,
`scopes`, `entitlement_revision`, `membership_revision`, `jti`, `iat`, `nbf` and
`exp`. Array audience and alternate header or claim forms MUST fail closed.

Compatible V1 fix-forward replaces the historical origin-only tuple with one
canonical path-bearing profile; it does not create V2, an alias or a dual-read
window. `iss` and scalar `aud` MUST be strict ASCII canonical absolute HTTPS
identifier/resource URIs of 1..2048 bytes with lowercase scheme and LDH DNS host,
a nonempty absolute path, and byte-exact parse/re-serialization. The canonical
issuer is `https://api.intdata.pro/functions/v1/platform-identity`; REST audience
is `https://<product>.intdata.pro/v1`; MCP audience is
`https://<product>.intdata.pro/mcp`. IP literals and every explicit port,
including a non-default port for Lite, are excluded. Userinfo, query, fragment,
backslash, control/whitespace/non-ASCII, trailing-dot or empty DNS labels,
default ports, repeated slash, literal or encoded dot segments, normalization,
uppercase scheme/host, and noncanonical percent encodings MUST fail closed.
Percent escapes MUST be uppercase; encoded unreserved bytes, slash, backslash,
NUL and controls MUST fail closed. Semantic verification MUST byte-compare only
its exact configured issuer and audience: origin/prefix/suffix/redirect matching,
normalization, REST-MCP substitution and central Lite fallback are forbidden.
Hosted verification additionally requires a trusted configured `product_id`, matching
the existing exact product-ID grammar. The verifier MUST first require
`claims.product_id` to byte-equal that trusted value, then derive its only allowed
audiences as `https://<trusted-product_id>.intdata.pro/v1` and
`https://<trusted-product_id>.intdata.pro/mcp`; configured audience and claim
`aud` MUST each byte-equal the selected derived endpoint. No derivation from a
claim may select verifier configuration, so a matched malicious claim/audience
cannot broaden this binding. URI path characters MUST use RFC 3986 `pchar` grammar. Any
percent-decoded UTF-8 code point in categories Cc, Cf, Zs, Zl or Zp MUST fail
closed. Every accepted positive vector MUST carry independently checked canonical
JCS claim bytes and lowercase SHA-256. The combined corpus MUST also include
raw-byte pre-parse rejection cases for duplicate keys, BOM, trailing bytes,
invalid UTF-8 and malformed JSON. Schema errors are deterministically ordered
before reporting, so an implementation never depends on validator iteration order.

The old exact tuple is withdrawn and non-admissible historical evidence:
schema `cb9304062759c10d8e068bf20386616c431acca49041816a8ff5190cf71c7e77`,
vectors `36431fc32257713473059bffefe76caa5fd93aaa36c39c0da17cd6dbfb996304`,
terminal aggregate
`d14d2be588c704aec03b5925a8176a9848c076e1ce35c86bfde9f6608b46ab3d` and the terminal manifest file SHA-256
`4389a70a1c6d7af47f9d66884c1da5267bd62ba361059e0d8ee4b0742e4f3d27`. No consumer may admit that tuple or read both old and corrected
artifacts. A PPA-only manifest atomically pins the schema and combined corpus
with raw lowercase SHA-256 and a separately defined deterministic aggregate; the
existing terminal manifest remains a four-artifact aggregate and is not a PPA
aggregate.

`sub` and `organization_id` MUST match lowercase canonical UUID regex
`[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}`.
`principal_type` MUST be `user` or `service_account`; `product_id` MUST match
`[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?`; `client_id` and `session_id` MUST match
`[A-Za-z0-9._:-]{1,128}`. `scopes` MUST be a non-empty lexicographically sorted
unique array of at most 64 strings matching
`[a-z][a-z0-9.-]{0,31}:[a-z][a-z0-9.-]{0,63}`. Both revisions MUST be integers
in `0..9007199254740991`; `jti` MUST match `[A-Za-z0-9_-]{16,128}`.

`iat`, `nbf` and `exp` MUST be integer NumericDate seconds in the I-JSON range.
Each vector MUST bind explicit integer `verifier_now`; verification MUST require
clock skew no greater than 30 seconds, `iat-30 <= nbf <= iat+30`,
`exp > max(iat,nbf)`, `exp <= iat+60`, `iat <= verifier_now+30`,
`nbf <= verifier_now+30` and `exp > verifier_now-30`. Vector documents MUST be
strict UTF-8 JSON and MUST bind RFC 8785 JCS bytes of accepted canonical claims;
this projection MUST NOT define an alternate JWT signing serialization.

#### Scenario: Assertion vectors are evaluated across languages

- **WHEN** Tools, Backend and a product consumer evaluate the pinned vector set
- **THEN** they produce the same accept/reject result and canonical claim bytes
- **AND** expired/future assertions, duplicate or unknown fields/keys, nulls,
  array audience, invalid/overlength identifiers, empty/unsorted/duplicate scopes,
  unsafe revisions and out-of-range NumericDate/skew/TTL fail closed
- **AND** every consumer pins exact schema and aggregate vector digests

### Requirement: Bridge OAuth registration approval receipt MUST be one closed profile

Tools MUST define `BridgeOAuthRegistrationApprovalReceiptV1` and accepted/adverse
vectors. Its JWT header MUST contain exact
`typ=bridge-oauth-registration-approval+jwt`, `alg=ES256` and an admitted `kid`
whose TrustBundle role is `bridge.oauth.registration-approval`. Central `iss`
MUST be `https://bridge.intdata.pro/oauth`; central `aud` MUST be
`https://api.intdata.pro/internal/platform-identity/v1/bridge/software-statements`.
Platform Lite MUST substitute both the exact customer Bridge issuer and private
Platform API audience from signed active `InstallationLockV1` and MUST NOT fall
back to either central value.
Claims MUST be closed to `iss`, `aud`, `sub`, `principal_type`,
`organization_id`, `session_id`, `membership_revision`,
`entitlement_revision`, `registration_metadata_digest`, `jti`, `iat`, `nbf` and
`exp`; `principal_type` MUST equal `user`. `iat`, `nbf` and `exp` MUST be integer,
non-boolean NumericDate values satisfying `iat <= nbf < exp <= iat+60`.
`sub`, `session_id`, `organization_id`, `membership_revision` and
`entitlement_revision` MUST be exact projections of the verified Platform
assertion plus durable owner approval; Backend MUST recheck the current durable
identity, membership, entitlement and exact revisions before use.
No alternate typ, claim, audience or dual acceptance is allowed.

`registration_metadata_digest` MUST equal `sha256:` plus lowercase SHA-256 over
RFC 8785/JCS bytes of an object with exactly `software_id`, `client_name`,
`redirect_uris`, `grant_types`, `token_endpoint_auth_method`, `scopes` and
`organization_id`. `redirect_uris`, `grant_types` and `scopes` MUST be
canonicalized, deduplicated and sorted before JCS; URI normalization collision
MUST fail closed.
The public software statement MUST remain inside the private Bridge/Backend
control plane; Tools MUST publish only schema and fixtures and MUST NOT persist,
transport or expose statement bytes.
`bridge-oauth-registration-uri/v1` MUST be the sole redirect URI normalization
profile. Inputs and outputs MUST be strict ASCII URI strings of 1..2048 bytes.
The profile MUST reject controls, whitespace, backslash, raw non-ASCII/Unicode,
invalid UTF-8 before parsing, userinfo, fragment, trailing-dot host, empty DNS
labels and any parse/re-serialize mismatch outside the exact rules below.

Scheme MUST be lowercase `https`. Lowercase `http` MUST be accepted only for
exact loopback hosts `127.0.0.1` or `[::1]`. DNS hosts MUST be lowercase LDH
ASCII labels; Unicode/IDNA input MUST be rejected rather than converted. IPv4
and IPv6 MUST use canonical textual form, and IPv6 MUST use brackets. Default
ports `:443` for HTTPS and `:80` for HTTP MUST be rejected rather than removed.
A port MUST be absent or canonical decimal `1..65535`; loopback HTTP MUST have an
explicit port. A non-loopback non-default port additionally requires admission
by signed installation policy.

Path MUST be absolute, begin with `/` and be non-empty; an initially empty path
MAY become `/` only before validation. Literal or percent-encoded `.`/`..`
segments, repeated slash and path normalization MUST be rejected. Percent escapes
MUST use uppercase hexadecimal. Percent-encoding RFC 3986 unreserved bytes MUST
be rejected because those bytes must be literal. Encoded slash, backslash, NUL,
control or malformed UTF-8 MUST be rejected; reserved-byte escapes MUST remain
byte-exact.

Query MAY be present and MUST preserve byte order and duplicates. It uses the
same uppercase-percent and unreserved-byte rules; an empty query marker `?` MUST
be rejected and `+` MUST NOT be converted as form-urlencoded space. Canonical
output MUST contain lowercase scheme/host, canonical IP and decimal port, exact
validated path and optional exact query. Re-parsing output MUST reproduce the
same bytes.

Redirect URIs MUST be canonicalized first. If distinct inputs yield the same
canonical string, the whole request MUST fail; otherwise exact normalized strings
MUST be unique and sorted ascending by unsigned UTF-8 bytes. `grant_types` and
`scopes` MUST use their own closed ASCII grammar and the same bytewise
collision/unique/sort rule. Tools MUST publish positive, adverse and collision
vectors plus immutable profile and vector digests; Bridge, Backend and Tools MUST
pin both digests. No alternate URL-library normalization is allowed.

#### Scenario: URI profile is applied consistently

- **WHEN** Bridge and Backend evaluate the same accepted or adverse vector
- **THEN** they produce the exact Tools-published canonical bytes or closed error
- **AND** a digest/profile mismatch blocks registration before any mutation

#### Scenario: Backend consumes a valid receipt

- **WHEN** Backend receives a registration request and approval receipt
- **THEN** it recomputes the exact metadata digest
- **AND** verifies the admitted Bridge workload, receipt signature, audience,
  trusted time and receipt `jti`
- **AND** rechecks current durable organization membership, owner authorization,
  Bridge entitlement and exact membership/entitlement revisions
- **AND** atomically consumes both receipt `jti` and request `jti` once

#### Scenario: Receipt or metadata is replayed or normalized differently

- **WHEN** any claim/profile/issuer/audience differs, a NumericDate is boolean or
  unordered, TTL exceeds 60 seconds, the Lite issuer falls back to central, a URI
  normalization collision occurs, metadata digest differs or either `jti` was used
- **THEN** validation fails before registration mutation
- **AND** vectors cover sorted/deduplicated arrays, digest mismatch, alternate
  typ/audience, extra claim and Lite audience substitution without central fallback

### Requirement: Platform Lite MUST have no hidden central dependency

The same contracts MUST support customer origins, a local registry snapshot and a
local artifact mirror. Artifact identity MUST be digest/size rather than URL.

#### Scenario: Lite acceptance runs offline

- **WHEN** `intdata.pro`, GitHub and central release storage are blocked
- **THEN** resolution and artifact verification succeed from local inputs
- **AND** any attempted central network dependency fails the suite

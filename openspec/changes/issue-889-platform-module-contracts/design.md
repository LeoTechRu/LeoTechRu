# Design

## Context

Tools `main` содержит candidate family v1, exact three-plugin marketplace,
experimental connector v0 и unpublished #875 Python carrier. Новая программа
объединяет публичные contracts и tooling, не присваивая runtime authority.
Root umbrella #887 хранит cross-repo ownership/rollout; этот package хранит только
точные Tools interfaces и acceptance.

## Goals / Non-Goals

**Goals:** offline versioned schemas, canonical bytes, deterministic packaging,
external signing boundary, connector conformance, family v2, immutable release
lock, Windows/Linux parity и Platform Lite offline proof.

**Non-Goals:** Backend solver/runtime, DB, product auth, Bridge provider cut,
Web/Client UI, Node runtime/installers, marketplace activation, production cutover
и перенос private governance в public source.

## Decisions

### 1. Authority and source topology

`contracts/platform/v1/schema-set.json` является закрытым offline registry всех
platform schemas. Каждый `$id` имеет вид `urn:intdata:schema:<type>:v1` и связан с
filename/version/SHA-256. JSON Schema — semantic authority; Python/TypeScript/Go
types являются generated или verified projections. Unknown schemas/fields fail
closed.

`platform-tooling/` является отдельным MIT distribution
`intdata-platform-tooling`; CLI name — `intdata-tools`. Public connector source
остаётся в `contracts/connectors/**` и `connectors/sdk`; private provider/runtime
source не импортируется.

### 2. Canonical serialization

Input — strict UTF-8 JSON без BOM, duplicate keys, trailing bytes, invalid Unicode
или non-schema fields. Validation предшествует hashing/signing. Canonical bytes —
RFC 8785 JCS без trailing newline. Signed platform contracts запрещают floating
values и ограничивают integers диапазоном
`[-9007199254740991, 9007199254740991]`; большие IDs/counters/sizes являются
canonical decimal strings. Timestamps используют UTC `YYYY-MM-DDTHH:MM:SSZ`.
Connector events сохраняют отдельное правило `1..6` fractional digits. Digests —
lowercase SHA-256. Одинаковые schema/input/tool versions обязаны давать
byte-identical Windows/Linux output; vectors включают safe-integer boundaries,
UTF-16 ordering non-BMP keys и lone-surrogate rejection.

### 3. Platform types

Stable v1 включает `ModuleManifest`, `InstallationManifest`, `RegistrySnapshot`,
`ResolverInput`, `ResolverResult`, `InstallationLock`, `ReleaseManifest`,
`SignatureEnvelope`, `TrustBundle` и `ScanAttestation`. Module описывает
capabilities/dependencies/artifacts/migrations/routes/web modules/runtime units и
configuration requirements. Installation — owner-authored desired state без
secrets/internal unit list. Lock содержит exact resolved graph/bindings/artifacts.

`TrustBundleV1` является единственным источником non-release public key material,
roles, validity и revocation для registry, module, installation actor и JWT.
Он хранит только pinned `ReleaseVerificationKeySetV1` ID/revision/digest и
bootstrap-root-set digest, но не дублирует `release.artifact.signing` keys или их
lifecycle. `RegistrySnapshotV1` хранит допустимые role/key IDs и exact trust
references без duplicated key material. DSSE `keyid` — hint, а не authority.
TrustBundle и KeySet имеют непересекающиеся роли; release verification обязана
проверить обе применимые authorities.

`ReleaseVerificationKeySetV1` specializes release-artifact verification trust.
Its RFC 8785 payload is wrapped in standard DSSE v1 with payload type
`application/vnd.intdata.release-keyset.v1+json` and requires at least two
cryptographically verified signatures from pairwise-distinct Ed25519 public-key
fingerprints in an immutable three-key offline root set whose role is
`release.trust.root`; `keyid` is only a hint and aliases never count. The exact
bootstrap root public-set digest is pinned out of band by installer/bootstrap
trust and repeated, but never bootstrapped, by `InstallationLockV1`.

The closed payload binds schema version, monotonic revision, previous digest,
generated time, bootstrap root-set digest and the complete active/retired/revoked
lifecycle of online keys. Online role `release.artifact.signing` can sign only
artifacts and cannot advance trust. Consumers verify canonical bytes/digest,
2-of-3 quorum, roles, root pin, previous digest, revision+1 and lifecycle before
atomic persistence. Root-set replacement and emergency recovery are outside v1
and require a separate full owner ceremony and new bootstrap/lock anchor. Offline
root signers receive public standard DSSE PAE of at most 262144 bytes plus opaque key ref;
production root private material never enters Tools or Backend runtime. For
release keys this KeySet is authoritative over the generic TrustBundle lifecycle.

Bootstrap revision is exactly `1` with null `previous_digest`; every later
revision increments by one and references `sha256:<lowercase-hex>` of the exact
previous RFC 8785 payload. The out-of-band root digest covers one canonical
descriptor `{schema_version,role,threshold,keys}` with role
`release.trust.root`, threshold `2` and exactly three pairwise-distinct Ed25519
public-key byte strings sorted by unsigned UTF-8 `key_id`. Release key IDs and
public-key material are never deleted or reused under aliases. Retired keys
verify only their admitted historical signing interval; revoked keys remain listed
and invalidate every release they signed.

`ResolverInputV1` связывает Installation revision/digest, RegistrySnapshot digest,
resolver version, solver-policy version и policy-input digest. Accepted
`InstallationLockV1` требует detached acceptance signature роли
`installation-actor`; Registry/Module/Release signatures проверяются до
plan/apply/recovery.
`PlatformProductAssertionV1` is the Tools-owned closed schema/vector projection
of root #887. Its schema ID is
`urn:intdata:schema:platform-product-assertion:v1`. It validates decoded exact
JWT header and claims, while vector files use strict UTF-8 JSON and RFC 8785 JCS
for `expected_canonical_claims`; it does not invent an alternate JWT signing
serialization. Header, closed claim set, scalar audience, identifier/scope
grammars, safe-integer revisions and verifier-time predicates remain byte-for-byte
aligned with #887. Positive/adverse vectors bind explicit `verifier_now` and cover
expired/future assertions, duplicate/unknown/null fields and keys, alternate
header/audience forms, regex and length boundaries, unsorted/duplicate scopes,
unsafe revisions and NumericDate/skew/TTL boundaries. Backend and every product
consumer pin the exact schema/vector set digests; Tools owns no assertion issuer
or verifier runtime.

`BridgeOAuthRegistrationApprovalReceiptV1` является закрытым ES256 JWT
consumer-contract для Backend registration handler. Header имеет только
`typ=bridge-oauth-registration-approval+jwt`, `alg=ES256` и exact admitted `kid`
роли `bridge.oauth.registration-approval`. Central issuer/audience равны
`https://bridge.intdata.pro/oauth` и
`https://api.intdata.pro/internal/platform-identity/v1/bridge/software-statements`;
Lite подставляет exact customer Bridge issuer и private Platform API audience из
signed active `InstallationLockV1` без central fallback. Claims закрыты exact набором
`iss,aud,sub,principal_type,organization_id,session_id,membership_revision,
entitlement_revision,registration_metadata_digest,jti,iat,nbf,exp`,
`principal_type=user`, TTL не превышает 60 секунд. Metadata digest имеет вид
`sha256:<lowercase-hex>` над RFC 8785/JCS bytes объекта с exact полями
`software_id,client_name,redirect_uris,grant_types,token_endpoint_auth_method,
scopes,organization_id`; массивы canonicalized, deduplicated и sorted до JCS,
а URI normalization collision fail closed. Tools владеет schema/vectors;
Backend повторно вычисляет digest, проверяет workload/receipt/time/jti, durable
membership/owner/entitlement и exact revisions, затем атомарно consume receipt
`jti` и request `jti` single-use. Alternate profile или dual acceptance запрещены.
Public software statement remains only in the private Bridge/Backend control plane;
Tools publishes schema/vectors and never stores statement bytes or runtime.
Receipt times are integer non-boolean NumericDate and require
`iat <= nbf < exp <= iat+60`; identity, session, organization and revisions are
projections of the verified Platform assertion plus durable owner approval and
are rechecked by Backend before atomic use.
Bridge owns exact URI semantics under `bridge-oauth-registration-uri/v1`; Tools
owns its language-neutral positive/adverse/collision vectors and profile/vector
digests. All parties pin both digests. Redirect URIs are normalized by that
profile, collision of distinct inputs fails the whole request, and surviving
strings are sorted ascending by unsigned UTF-8 bytes. `grant_types` and `scopes`
use their own ASCII grammar and the same collision/unique/sort rule.

### 4. CLI and packaging

CLI предоставляет schema validate/canonicalize/digest, module/installation
validate, lock verify, release pack/sign/verify, connector conformance и family
validate/generate/check. В CLI нет publish/deploy/activate/DB/runtime commands.

Worktree validation разрешена, но release pack принимает только clean tracked
commit-bound source с canonical origin и remote reachability. Packager запрещает
links/traversal/devices/case-fold collisions/Windows reserved paths/ambient host
paths/secrets и output внутри source, managed state или `CODEX_HOME`. Archive
ordering, uid/gid/mode/time фиксированы. SBOM и scan attestation обязательны.

Production signing использует standard DSSE v1 + Ed25519. CLI canonicalizes the
public release manifest, строит exact PAE из payload type
`application/vnd.intdata.release-manifest.v1+json` и payload bytes и передаёт
bounded public PAE bytes внешнему argv-only signer через закрытый stdin/stdout
protocol без shell. Signer возвращает raw Ed25519 signature; CLI формирует closed
single-signature envelope, повторно проверяет PAE/signature/trust до записи.
Manifest digest binding является отдельным versioned input и никогда не называется
DSSE. Production key material никогда не входит в Tools. File key допускается
только отдельной development-командой и никогда не `release sign`.

### 5. Resolver and Platform Lite boundary

Tools владеет wire contracts, fixtures и black-box conformance. Backend владеет
graph resolution, compatible-version selection, policy, persistence, API,
installation actor и plan/apply/rollback. Resolver result обязан выбирать minimal
transitive set по exact deterministic tie-break, отвергать reverse-dependency
disable и не возвращать partial lock. Canonical unsigned result/lock digest отделён
от acceptance signature installation actor и byte-identical при одинаковых
versioned inputs.

Platform Lite использует те же contracts с customer origins, local registry и
local artifact mirror. Offline acceptance блокирует `intdata.pro`, GitHub и
central release storage. URL является transport location; artifact identity —
digest/size.

### 6. Connector reconciliation

#875 experimental-v0 и carrier `0.1.0` сначала публикуются неизменяемо. Stable v1
добавляет `ConnectorCapabilityV1`, `ReadInvocationV1`, `ActionPlanV1`,
`EffectGrantV1`, `EffectReceiptV1`, `EventEnvelopeV1`, `ConnectorErrorV1`.
Reads/effects разделены. Grant связывает exact ActionPlan digest,
connector/version, operation, arguments digest, principal/role, audience/contour,
expiry, revocation, fence и idempotency key. Stale/wrong/revoked grant отвергается
до effect; повтор key возвращает тот же immutable receipt без redispatch. Receipt
связывает grant/action/input/output/artifact digests; события монотонны, terminal
immutable, secret-like values redacted. Unknown outcome становится
`indeterminate` и не retry автоматически. Credentials/runtime policy исключены.
TypeScript package переименовывается в `@intdata/connector-sdk`; до v1 он остаётся
`0.x`. Public SDK использует exact MIT LICENSE/package metadata и сохраняет все
third-party LICENSE/NOTICE в каждом archive.

### 7. Family v2 and Probe hard cut

Plugin IDs остаются ровно `intbridge`, `intagent`, `intdev`. `intdev` public/MIT;
два остальных private/authenticated с safe public metadata. Resource IDs v2:
`agent,brain,bridge,platform,punkt-b,crm,cms,lms`. Target endpoints exact:
`https://bridge.intdata.pro/mcp`, `https://brain.intdata.pro/mcp`,
`https://crm.intdata.pro/mcp`, `https://cms.intdata.pro/mcp`,
`https://api.intdata.pro/mcp`. Неподтверждённые resources typed unavailable с null
endpoint/metadata/oauth resource/audience и `authorization.state=unconfigured`.
Bridge остаётся unavailable до terminal #898 provider/runtime/auth evidence.

Public `probe`, `/mcp/probe`, `mcp/resources/probe.json`, Probe OAuth/resource и
component identity удаляются атомарно. `intbridge` получает component `observer`,
source record `mcp/resources/bridge.json`, resource `bridge`, audience
`https://bridge.intdata.pro/mcp`, exact
`credential_boundary=service_boundary=state_boundary=bridge-observer` и Bridge
Observer skills. Node internal `node.internal.probe-collector/v1` разрешён только как
`visibility=internal`; validator запрещает его во всех public projections.

### 8. Release and activation

Immutable family release содержит catalog/schema/marketplace/release-lock/
activation/SHA256SUMS/SBOM/release manifest/DSSE/scan attestation. Candidate
marketplace сохраняет три IDs с `policy.installation=NOT_AVAILABLE`; installable
marketplace возникает только в signed immutable release после terminal #898.
Terminal receipt связывает remotely reachable Bridge/Tools/all-consumer SHAs,
zero active Probe scan и successful atomic rollback rehearsal. Zero-scan имеет
tracked scope и отдельный historical/generic/internal allowlist. Tools генерирует
и проверяет activation record, но runtime pointer переключает отдельный owner.

### 9. Reconciliation with existing contracts

- #842 сохраняется целиком: Tools владеет schemas/conformance, Backend #888 —
  runtime resolver/registry/delivery.
- До terminal #898 #862 v1 остаётся единственным действующим non-installable
  candidate. После #898 superseded все конфликтующие v1
  domain/path/resource/audience clauses, включая legacy centralized `/mcp/agent`,
  старые `https://intdata.pro/mcp/*`, family/catalog/activation version и
  Probe-specific clauses. Для not-yet-accepted resources v2 authoritative state —
  null identity URLs и `authorization.state=unconfigured`.
- #862 audience isolation после настройки, no bearer forwarding, fail-closed
  authorization, provenance/access, `NOT_AVAILABLE`, remote reachability,
  `CODEX_HOME`, VDS/Windows parity и outward gates сохраняются.
- #875 остаётся immutable predecessor и блокирует stable connector v1 до exact
  published `0.1.0` handoff.
- Pre-cut v1 и post-cut v2 не могут одновременно быть installable или active.

## Migration Plan

Waves: authority → schemas/canonicalization → pack/sign/verify → #875+connector
v1 → family v2+atomic provider/consumer cut → resolver/Lite → signed acceptance.
Перед publication safe stop оставляет candidate неактивным. После immutable
publication исправление — новый version/release ID. Dev rollback переключает весь
предыдущий signed snapshot; aliases, redirects, dual-run и partial rollback
запрещены. Два root checkpoints выполняются отдельно coordinator-owned contour.

## Rollback / Safe Stop

## Risks / Trade-offs

Главные риски: дублирование schema authority, platform-specific canonicalization,
archive/signing vulnerabilities, утечка private governance, неполный Probe
consumer inventory и hidden central dependency в Lite. Они закрываются strict
fixtures, property/fuzz tests, independent security review, full consumer freeze и
offline rehearsal до installable release.

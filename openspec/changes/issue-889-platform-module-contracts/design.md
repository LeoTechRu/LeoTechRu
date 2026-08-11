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

`TrustBundleV1` является единственным источником public key material, roles,
validity и revocation. Он имеет pinned root, monotonic revision, explicit trusted
time policy и anti-rollback. `RegistrySnapshotV1` хранит только допустимые
role/key IDs и exact trust-bundle ID/version/digest, но не дублирует key material.
DSSE `keyid` — hint, а не authority. Роли как минимум разделяют registry,
module/release и installation-actor.

`ResolverInputV1` связывает Installation revision/digest, RegistrySnapshot digest,
resolver version, solver-policy version и policy-input digest. Accepted
`InstallationLockV1` требует detached acceptance signature роли
`installation-actor`; Registry/Module/Release signatures проверяются до
plan/apply/recovery.

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

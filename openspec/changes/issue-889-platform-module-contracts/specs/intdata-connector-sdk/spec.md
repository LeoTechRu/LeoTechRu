# intData Connector SDK Specification

## Purpose

Define the migration from #875 experimental connector carrier to a stable public
language-neutral contract and SDK.

## ADDED Requirements

### Requirement: Experimental carrier MUST be completed before stable v1

The protected `contracts/connectors/python/**` write-set MUST be inventoried,
generated outputs removed through an owned commit, independently reviewed and
published as immutable `intdata-connector-contracts==0.1.0` according to #875.
Stable v1 MUST NOT silently rewrite experimental-v0 resources or release tag.

#### Scenario: Stable work begins

- **WHEN** connector v1 source is accepted
- **THEN** #875 has exact source commit, immutable artifact hash and terminal handoff
- **AND** generated build/egg-info/cache files are absent from Git and ignored

### Requirement: Connector v1 MUST separate reads, plans, grants and effects

The schema MUST define `ConnectorCapabilityV1`, `ReadInvocationV1`,
`ActionPlanV1`, `EffectGrantV1`, `EffectReceiptV1`, `EventEnvelopeV1` and
`ConnectorErrorV1`. `EffectGrantV1` MUST bind exact ActionPlan digest,
connector/version, operation, arguments digest, principal/role, audience/contour,
expiry, revocation state, fence and idempotency key. Stale, wrong or revoked grant
MUST be rejected before effect. Repeated idempotency key MUST return the same
immutable terminal receipt and MUST NOT dispatch twice. `EffectReceiptV1` MUST bind
grant/action/input/output/artifact digests and terminal or `indeterminate` outcome.
Event sequence MUST be monotonic and terminal event/receipt MUST be immutable.
Unknown outcome MUST become `indeterminate` and MUST NOT retry automatically.
Receipts/events/errors MUST redact secret-like values. Provider credentials,
secret custody, runtime hosting and private policy MUST NOT be part of the public
contract.

#### Scenario: Effect result is lost

- **WHEN** dispatch may have occurred but no terminal receipt is proven
- **THEN** outcome is `indeterminate`
- **AND** conformance rejects automatic redispatch or fabricated success

#### Scenario: A grant is stale or an idempotency key repeats

- **WHEN** grant binding/fence/expiry/revocation is invalid or a completed key repeats
- **THEN** invalid grant is rejected before dispatch
- **AND** repeated completed key returns the same receipt without a second effect
- **AND** fixture output exposes no secret-like value

### Requirement: JSON Schema MUST be semantic authority

Language bindings MUST conform to the tracked schema and MUST NOT introduce wire
semantics such as JavaScript `Date`, ambient secret storage or implementation-only
fields. Event timestamps MAY use one through six UTC fractional digits.

#### Scenario: Python and TypeScript encode the same event

- **WHEN** both bindings consume a golden fixture
- **THEN** canonical wire bytes and validation outcome are identical
- **AND** unsupported language-native values fail before serialization

### Requirement: Public TypeScript SDK MUST use stable intData identity

Current `@inttools/connector-sdk` MUST migrate after consumer inventory to
`@intdata/connector-sdk`. It MUST remain `0.x` before stable schema acceptance and
MUST reach `1.0.0` only after schema/SDK/conformance parity. No private connector,
provider process/network management or runtime policy may enter the package. The
public package MUST use MIT with exact root/package/archive LICENSE metadata and
MUST preserve every third-party LICENSE/NOTICE attribution in each archive.

#### Scenario: SDK package is inspected

- **WHEN** its exports, dependencies and built artifact are scanned
- **THEN** only public types/helpers/conformance integration are present
- **AND** there are no private source imports, credentials or hosting surfaces

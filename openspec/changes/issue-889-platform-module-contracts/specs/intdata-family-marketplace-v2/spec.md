# intData Family Marketplace v2 Specification

## Purpose

Define the exact public family catalog, immutable release lock and Tools side of
the atomic Probe→Bridge Observer hard cut.

## ADDED Requirements

### Requirement: Public family MUST expose only intnode

Public marketplace MUST use ID `inttools`, display name `intData Tools` and
contain exactly MIT `intnode` with `AVAILABLE` and `ON_USE`. Concrete private or
proprietary plugin records, manifests, commits and release pins MUST be rejected.
Generic schemas and MCP resource descriptors MAY remain metadata only.

#### Scenario: Candidate catalog is generated

- **WHEN** marketplace and tracked plugin tree are validated
- **THEN** exact selector is `intnode@inttools`
- **AND** tracked `codex/plugins/**` contains exactly `intnode`

### Requirement: Public resource identity MUST hard-cut from Probe to Bridge

Resource IDs MUST be exactly `agent,brain,bridge,platform,punkt-b,crm,cms,lms`.
Public `probe`, `/probe/**`, `/mcp/probe`, Probe OAuth/resource/issuer metadata,
`mcp/resources/probe.json` and product-facing Probe identity MUST be rejected with
no alias, redirect or dual-run. Bridge source record MUST be
`mcp/resources/bridge.json` and target resource MUST be
`https://bridge.intdata.pro/mcp`.

#### Scenario: Family and source are scanned after cut

- **WHEN** v2 release candidate is built after terminal #898 provider/consumer cut
- **THEN** tracked repository-wide scan finds zero active public Probe identity
- **AND** terminal receipt binds exact remotely reachable provider/consumer SHAs
- **AND** historical Git evidence is not rewritten

### Requirement: intbridge MUST expose Bridge Observer semantics

The `intbridge` component MUST use `id=observer`, display name
`intData Bridge Observer`, resource `bridge`, OAuth audience
`https://bridge.intdata.pro/mcp`, approval policy
`bridge-observer-confirmation` and exact
`credential_boundary=service_boundary=state_boundary=bridge-observer`.
Its public skills MUST be exactly `bridge-observer`, `fleet-diagnostics`,
`client-control`, `incident-response`, `observer-administration`, `dba-health`,
`doctor-status`, `local-smoke`, `migrations`, `sql-apply`.

#### Scenario: Plugin family is validated

- **WHEN** intbridge metadata and package tree are scanned
- **THEN** exact component/resource/skill membership passes
- **AND** `probe-operator` and `probe-administration` aliases fail

### Requirement: Internal Node collector MUST remain non-public

The family validator MUST keep every internal Node collector outside public
projections. A capability named `node.internal.probe-collector/v1` MAY exist only
with `visibility=internal`. It MUST NOT enter public catalog, marketplace, REST/MCP
routes, UI, downloads, health, binary/service/package names or OAuth identities.

#### Scenario: Internal capability is projected

- **WHEN** generator encounters the internal collector descriptor
- **THEN** no public projection contains it
- **AND** any attempted public projection fails validation

### Requirement: Unavailable resources MUST remain explicit

The family catalog MUST represent readiness explicitly and MUST NOT invent
endpoints. Target first-wave endpoints are exactly Bridge, Brain, CRM, CMS and
Platform at `https://bridge.intdata.pro/mcp`, `https://brain.intdata.pro/mcp`,
`https://crm.intdata.pro/mcp`, `https://cms.intdata.pro/mcp` and
`https://api.intdata.pro/mcp`; readiness MUST still come from accepted evidence.
Bridge MUST remain unavailable until terminal #898. Agent, Punkt B and LMS MUST
remain typed unavailable until their own contracts are accepted. Every unavailable
entry MUST set endpoint, metadata URI, OAuth resource and audience to null and
`authorization.state=unconfigured`. Punkt B MUST NOT gain a Web module.

#### Scenario: A not-ready resource is generated

- **WHEN** no accepted endpoint exists
- **THEN** catalog carries typed unavailable state with all identity URLs null
- **AND** marketplace remains non-installable

### Requirement: Installable marketplace MUST exist only in immutable release

Candidate checked-in marketplace MUST contain only public `intnode` with
`AVAILABLE` and `ON_USE`. Immutable release projections MUST preserve the same
public-only membership and exact remotely reachable Tools source commit; private
plugin publication MUST NOT be reconstructed here.

#### Scenario: Candidate or mismatched release is generated

- **WHEN** state is candidate, source is local-only, or any projection differs
- **THEN** installable marketplace generation fails closed
- **AND** no activation pointer is changed

### Requirement: Family v1 and v2 MUST never be active together

Pre-cut #862 v1 MUST remain the only non-installable candidate until #898 terminal
acceptance. Post-cut v2 MUST replace the whole signed snapshot atomically and MUST
be authoritative for domain/path/resource/audience records. Legacy centralized
`/mcp/agent` and old `https://intdata.pro/mcp/*` identities MUST NOT survive unless
the corresponding v2 resource is accepted at that exact origin; unavailable
resources MUST use null identity URLs. Aliases, redirects, dual-run and partial
plugin/resource rollback MUST be rejected.

#### Scenario: A mixed generation is proposed

- **WHEN** activation references both v1 and v2 or mismatched cut generation
- **THEN** family validation fails before any runtime pointer can change

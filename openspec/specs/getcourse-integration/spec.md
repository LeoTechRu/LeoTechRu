# getcourse-integration Specification

## Purpose

Defines the bounded, secret-safe GetCourse connector capability and its reproducible public API coverage for shared agent runtimes.

## Requirements

### Requirement: GetCourse MCP MUST declare complete public API coverage

The system MUST keep a machine-readable manifest of every distinct Import API
and Export API surface documented by the canonical GetCourse API article, with
its method, path template, action, risk and MCP coverage.

#### Scenario: Coverage is validated

- **WHEN** connector tests load the committed manifest
- **THEN** every manifest surface maps to an implemented typed or guarded tool
- **AND** duplicate identifiers and unexplained implementation endpoints fail.

### Requirement: Read operations MUST be bounded and endpoint-safe

The system MUST keep host and API key in runtime configuration and MUST expose
only documented account API reads, including the fields directory POST with a
fixed `action=get`.

#### Scenario: Additional fields are requested

- **WHEN** the caller invokes the fields directory tool
- **THEN** the connector posts only to `/pl/api/account/fields`
- **AND** sends only the configured key plus fixed `action=get`
- **AND** never accepts a caller-controlled host, path, key or action.

#### Scenario: An export is requested

- **WHEN** the caller starts an Export API job
- **THEN** at least one documented object filter is required
- **AND** polling attempts and intervals remain bounded
- **AND** limits and transient status are returned without automatic parallel retry.

### Requirement: Import writes MUST require explicit confirmation

The system MUST reject every users or deals Import API mutation unless the
individual tool call contains exact `confirm_write=true`.

#### Scenario: Confirmation is absent

- **WHEN** a caller attempts user, group membership, deal or deal status import
  without exact confirmation
- **THEN** the connector rejects the operation before network access.

### Requirement: Diagnostics MUST NOT echo credentials or personal payloads

The system MUST omit API keys, request payloads and personal values from health,
errors and logs while preserving safe status and documented error codes.

#### Scenario: GetCourse rejects a request

- **WHEN** a remote or local validation error occurs
- **THEN** the MCP returns a bounded safe envelope
- **AND** does not echo the key, account payload, email, phone or arbitrary server body.

### Requirement: Runtime acceptance MUST not create jobs or writes

The system MUST validate runtime with discovery, health and a proven read-only
request that does not create an Export API job.

#### Scenario: A host contour is accepted

- **WHEN** Codex or Hermes validates GetCourse MCP
- **THEN** no export, import, callback, message or browser mutation is performed
- **AND** the contour resolves to the same top-level package version.

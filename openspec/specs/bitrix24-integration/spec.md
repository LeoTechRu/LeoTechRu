# bitrix24-integration Specification

## Purpose

Defines the manifest-backed, secret-safe Bitrix24 connector capability and the runtime parity contract shared by agent hosts.

## Requirements

### Requirement: Bitrix24 MCP MUST have a reproducible official API manifest

The system MUST derive its active Bitrix24 server method registry from the
official `bitrix24/b24restdocs` repository and MUST record the upstream commit
and source path for every classified entry.

#### Scenario: The parity manifest is generated

- **WHEN** the manifest generator reads a pinned official documentation checkout
- **THEN** every discovered active server method is represented exactly once
- **AND** events, browser JavaScript APIs and outdated pages are classified as
  exclusions rather than callable server methods
- **AND** unexplained discovered pages fail validation.

### Requirement: Every active documented server method MUST be addressable

The system MUST expose every active manifest server method through a
manifest-backed universal MCP call or an equivalent typed tool.

#### Scenario: A documented method is requested

- **WHEN** the caller provides an active manifest method and parameters
- **THEN** the MCP routes the request to the configured Bitrix24 account
- **AND** preserves the method name and documented parameter shape
- **AND** never permits caller-controlled host, webhook URL or auth path.

#### Scenario: An unregistered surface is requested

- **WHEN** the caller provides an unknown, event-only, browser-only, private or
  outdated entry
- **THEN** the MCP rejects it before network access
- **AND** returns only redacted classification metadata.

### Requirement: Capability MUST remain separate from account authorization

The system MUST NOT claim that manifest coverage grants scopes, tariff features
or data permissions that the configured Bitrix24 webhook user does not have.

#### Scenario: The account denies a method

- **WHEN** Bitrix24 returns a scope, permission, tariff or availability error
- **THEN** the MCP returns a bounded redacted error envelope
- **AND** records the limitation as an external account blocker rather than a
  missing connector capability.

### Requirement: Bitrix24 secrets and response data MUST be constrained

The system MUST keep webhook credentials outside Git and MUST redact auth paths,
tokens, secret-like fields and personal values from diagnostics and errors.

#### Scenario: Diagnostics or transport fails

- **WHEN** configuration or a Bitrix24 request fails
- **THEN** logs and tool output omit the full webhook URL and credentials
- **AND** expose only safe status, method classification and bounded remediation
  metadata.

### Requirement: Runtime validation MUST be read-only

The system MUST validate live runtime only with methods proven read-only for the
smoke scenario.

#### Scenario: The package is accepted on a host

- **WHEN** Codex or Hermes discovery and live smoke are executed
- **THEN** no write, delete, message, call, batch mutation or external event is
  performed
- **AND** write-capable manifest entries are covered by contract/mock tests only
  until a separate exact owner authorization names the action and target.

### Requirement: All agent runtimes MUST use one canonical package version

The system MUST use the top-level agent-agnostic `bitrix24-mcp` package as the
canonical source for PC and VDS Codex and Hermes registrations.

#### Scenario: Runtime parity is checked

- **WHEN** the four runtime contours are inventoried
- **THEN** each available contour resolves to the same canonical source/version
- **AND** unavailable hosts or missing credentials are reported as exact
  blockers without copying secrets between stores.

## ADDED Requirements

### Requirement: intTools MUST be a public first-party tool catalog
The system MUST treat `/int/tools` as a public open-source catalog for reusable first-party tools, public adapters, sanitized templates, and catalog metadata.

#### Scenario: Public source is classified
- **WHEN** a tracked non-hidden top-level directory exists in `/int/tools`
- **THEN** it is classified in `tools.catalog.v1.json`
- **AND** it has a clear public status, owner, public surface, runtime-state boundary, target home, and migration action

### Requirement: Private and runtime material MUST leave public tools
The system MUST NOT treat private governance, runtime state, live host machinery, legacy Codex-home overlays, vendor/reference copies, or product-private content as public intTools source.

#### Scenario: Non-public material remains during migration
- **WHEN** non-public material has not yet been removed from `/int/tools`
- **THEN** it is marked as `master-private`, `runtime-state`, or `legacy-remove`
- **AND** its target home and migration action are recorded before any destructive cleanup

### Requirement: IntBrain MUST NOT be exposed through intTools
The system MUST keep IntBrain memory/search capabilities outside `/int/tools`.

#### Scenario: MCP or search adapter is evaluated
- **WHEN** a tool surface exposes IntBrain search, fetch, memory, context, or people graph behavior
- **THEN** it belongs to the IntBrain contour or plugin
- **AND** it is not presented as an intTools public catalog MCP

### Requirement: Public catalog validation MUST block unclassified source
The system MUST provide a validation command that blocks newly tracked public top-level directories unless they are added to `tools.catalog.v1.json`.

#### Scenario: A top-level directory is added
- **WHEN** validation runs in `/int/tools`
- **THEN** every tracked non-hidden top-level directory is present in the manifest
- **AND** manifest roots that are missing on disk are rejected unless their status is `catalog-link`
- **AND** forbidden public artifacts such as private governance, `node_modules`, live env files, logs, SQLite/db runtime, and `.runtime` tracked content are rejected

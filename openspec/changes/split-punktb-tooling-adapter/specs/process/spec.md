## ADDED Requirements

### Requirement: Product adapters MUST NOT own reusable repo workflow utilities
The system MUST keep product adapter directories focused on product-specific wrappers, profiles, smoke scenarios, runbooks, and compatibility glue.

#### Scenario: Reusable scripts are found under a product adapter
- **WHEN** a script under a product adapter does not require product-specific data, endpoints, schema names, credentials, or runtime assumptions
- **THEN** it is moved or re-exposed from a neutral top-level tool such as `repo-ops/`
- **AND** the product adapter may keep only a compatibility wrapper or profile-specific entrypoint
- **AND** public documentation describes the neutral tool, not the product adapter, as the reusable owner

### Requirement: PunktB adapter MUST remain product-specific
The system MUST treat `punkt-b/` as the PunktB product adapter, not as a generic repository operations toolbox.

#### Scenario: PunktB tooling is reviewed
- **WHEN** `punkt-b/` contains gates, release helpers, issue workflow scripts, browser smoke scripts, DBA plans, or cleanup utilities
- **THEN** product-specific scripts remain in `punkt-b/`
- **AND** reusable scripts are extracted in safe slices after their PunktB assumptions are parameterized
- **AND** legacy wrappers remain available until documented consumers are migrated

### Requirement: Extracted utilities MUST keep compatibility entrypoints during migration
The system MUST preserve stable product-adapter commands while reusable implementations are moved to neutral tools.

#### Scenario: A utility moves from `punkt-b/` to `repo-ops/`
- **WHEN** an existing PunktB command path is replaced by a neutral implementation
- **THEN** the old PunktB path remains as a compatibility wrapper in the same change
- **AND** the wrapper delegates to the neutral implementation without duplicating business logic
- **AND** tests or smoke checks cover both the neutral entrypoint and the compatibility path

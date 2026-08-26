## ADDED Requirements

### Requirement: intdb MUST refresh intdata dev from PunktB prod using read-only source access
The system MUST provide a guarded project migration workflow that refreshes intdata dev client test state from `punkt_b_prod` without any source writes.

#### Scenario: Operator refreshes intdata dev from PunktB prod
- **WHEN** the operator runs the PunktB prod dev refresh workflow
- **THEN** the source profile SHOULD be `punktb-prod-ro` when that role has sufficient read grants
- **AND** the source profile MAY be `punktb-prod-migrator` only when intdb forces the export session into `default_transaction_read_only=on`
- **AND** the source database MUST be `punkt_b_prod`
- **AND** the source user MUST be either `db_readonly_prod` or `db_migrator_prod`
- **AND** source export MUST use read-only PostgreSQL tooling
- **AND** the target profile MUST be `intdata-dev-admin`
- **AND** the target database MUST be `intdata`
- **AND** the target user MUST be `db_admin_dev`
- **AND** target writes MUST require `--approve-target intdata-dev-admin`

#### Scenario: Operator dry-runs the refresh
- **WHEN** the operator runs the refresh in dry-run mode
- **THEN** intdb MUST export the source table set
- **AND** intdb MUST stage the target reload inside a transaction
- **AND** intdb MUST roll back target changes before exit
- **AND** intdb MUST report source and staged target counts

#### Scenario: Operator applies the refresh
- **WHEN** the operator runs the refresh in apply mode
- **THEN** intdb MUST load the exported production rows into the whitelisted target client-state tables
- **AND** intdb MUST create or update the required dev `auth.users` and `auth.identities` rows for imported specialist/client emails without reading prod auth tables
- **AND** intdb MUST commit the target transaction only after the load succeeds

#### Scenario: Full replace refresh removes dev-only rows in the approved scope
- **WHEN** the operator runs the refresh with the approved dev admin target
- **THEN** intdb MUST fully replace rows in `assess.specialists`, `assess.clients`, and `assess.diag_results`
- **AND** extra dev-only rows inside that approved scope MUST be removed
- **AND** dependent dev rows that would otherwise keep foreign-key references to the replaced rows MUST be cleaned before the reload commits

#### Scenario: Production read grants are limited
- **WHEN** production read grants do not include auth, ACL, credential, or result-access tables
- **THEN** intdb MUST NOT escalate source privileges or issue source grants
- **AND** the refresh MUST stay limited to tables readable through the source profile

#### Scenario: Local pg_dump version is older than production
- **WHEN** the local `pg_dump` cannot dump the production server version
- **THEN** the refresh workflow MUST still support export through read-only `psql` queries

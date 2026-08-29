# punkt-b-plugin-tooling Specification

## Purpose

Defines reusable, product-independent and secret-safe tooling used by Punkt B plugin identities across Codex and Hermes runtimes.

## Requirements

### Requirement: Reusable Punkt B plugin tooling MUST remain product-independent

Reusable MCP implementations, launchers, validators and credential helpers
MUST live in Tools without Punkt B private policy or credential values.

#### Scenario: A product plugin invokes a shared connector

- **WHEN** a Punkt B identity routes to a shared service connector
- **THEN** it invokes the canonical Tools implementation
- **AND** product-specific routing and action policy stays in the product layer.

### Requirement: Runtime registration helpers MUST be native and secret-safe

Helpers MUST use documented native Codex and Hermes registration mechanisms
and protected credential stores or pointers. They MUST NOT patch runtime-owned
home state or reveal credential values in validation output.

#### Scenario: A supported runtime is registered

- **WHEN** the helper installs a plugin on PC or VDS
- **THEN** it records identity and source status without secret material
- **AND** it does not copy credentials between runtime stores.

### Requirement: Reusable write tooling MUST preserve action gates

Write-capable connectors MUST preserve confirmation, idempotency, exact target,
preview hash and effect-flag gates independently of the product composition.

#### Scenario: A write gate is absent

- **WHEN** a write-capable connector call lacks any required gate
- **THEN** it fails before external network access.

## Purpose

Defines one updateable intData UI/UX skill that combines maintained design knowledge with live component and motion sources across Codex and Hermes.

## ADDED Requirements

### Requirement: The skill SHALL have one permanent identity and source

The permanent skill ID, directory and frontmatter name MUST be `intdata-ui-ux`. `/int/tools/codex/assets/codex-home/skills/intdata-ui-ux/**` SHALL be its sole updateable source. Active source and accepted installations MUST NOT retain `ui-ux-pro-max` or `ui-mvp-sources` as aliases or parallel skills after their cell migration succeeds.

#### Scenario: Identity migration succeeds
- **WHEN** a target cell has verified `intdata-ui-ux` discovery and artifact equality
- **THEN** that cell exposes only the permanent `intdata-ui-ux` identity
- **AND** predecessor skill identities are absent.

### Requirement: The catalog SHALL identify the five live UI sources and their roles

The skill SHALL identify Beautiful UI, beUI, Rare UI, Transitions.dev and shadcn/ui by canonical HTTPS URL and explain the distinct role of each source. The agent MUST inspect the current source rather than treating remembered catalog content as current.

#### Scenario: Agent needs a component or interaction pattern
- **WHEN** an agent needs a stronger component, agent interface or transition
- **THEN** it selects the relevant live source through `intdata-ui-ux`
- **AND** inspects the current component or artifact before adapting it.

### Requirement: Adaptation SHALL optimize for the requested MVP

The skill SHALL permit an agent to copy, adapt, combine or reimplement useful concepts, layouts, interactions, transitions, snippets, components and assets. Existing project primitives and dependencies MUST be considered but MUST NOT veto a materially better bounded result. Implementation MUST preserve accessibility, responsive behavior, framework compatibility and material security properties.

#### Scenario: Existing and external primitives both fit
- **WHEN** the current project and a live source offer viable implementations
- **THEN** the agent compares them against the requested user outcome
- **AND** uses or combines the option that produces the stronger bounded MVP without unnecessary dependencies.

### Requirement: All supported agent cells SHALL derive from one published artifact

Codex and Hermes `default`/`intfall` installations on VDS and Windows VM MUST derive from the same published commit-bound skill directory. Source publication and each cell's installation, discovery and normalized hash SHALL be verified independently.

#### Scenario: One cell is unavailable
- **WHEN** a host, runtime or profile cannot be reached or verified
- **THEN** that cell remains `NOT_VERIFIED`
- **AND** completed source or sibling-cell acceptance is reported separately rather than inferred.

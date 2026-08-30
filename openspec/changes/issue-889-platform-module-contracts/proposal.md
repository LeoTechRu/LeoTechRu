# Production-ready public tooling layer

## Why

Issue [#889](https://github.com/LeoTechPro/int/issues/889) является Tools-owned
частью umbrella [#887](https://github.com/LeoTechPro/int/issues/887). Платформе
нужны language-neutral Module/Installation/release/connector contracts,
детерминированная supply-chain CLI и единый проверяемый marketplace snapshot.
Сейчас эти обязанности распределены между candidate family v1, experimental
connector contract и ad-hoc packagers, поэтому Backend resolver, Platform Lite и
внешние consumers не имеют одного стабильного публичного boundary.

Уровень change — **full**: пакет вводит публичные cross-repository schemas,
подпись и trust model, immutable release contract и атомарный Probe→Bridge hard
cut. Он forward-supersedes только конфликтующие активные требования #862/#875 и
не переписывает их исторические packages.

## What Changes

- Добавляется offline schema set `contracts/platform/v1/**` для Module,
  Installation, Registry, Resolver, Lock, Release, Signature, Trust и Scan.
- Добавляется публичный Python distribution `intdata-platform-tooling` и команда
  `intdata-tools` с validate/canonicalize/digest/pack/sign/verify/conformance.
- Backend получает transport-neutral resolver input/result и black-box
  conformance; runtime solver, persistence, DB и apply остаются Backend-owned.
- #875 carrier доводится до immutable `0.1.0`, затем connector semantic authority
  закрепляется в stable v1 и public TypeScript SDK `@intdata/connector-sdk`.
- Public family projection использует `inttools` / `intData Tools` и содержит
  единственный MIT plugin `intnode`; private distribution records исключаются,
  а generic schemas/MCP resource descriptors остаются metadata.
- Tools создаёт immutable release lock/activation projection, но не публикует,
  не активирует и не переключает runtime самостоятельно.

## Capabilities

### New Capabilities

- `intdata-public-contracts`: versioned schemas и canonical serialization.
- `intdata-deterministic-release-tooling`: deterministic pack/sign/verify CLI.
- `intdata-connector-sdk`: stable connector contract, SDK и conformance.
- `intdata-family-marketplace-v2`: public-only catalog/release lock с `intnode`.

### Modified Capabilities

- #842 composition использует эти schemas по exact version/digest.
- #862 остаётся действующим non-installable v1 contract до terminal #898. После
  атомарного cut superseded все конфликтующие v1 domain/path/resource/audience
  clauses, включая legacy centralized `/mcp/agent`, старые
  `https://intdata.pro/mcp/*`, family/catalog/activation version и Probe-specific
  clauses. Сохраняются audience isolation после настройки, no bearer forwarding,
  fail-closed authorization, provenance/access, `NOT_AVAILABLE`, host parity,
  `CODEX_HOME` и outward gates.
- Pre-cut v1 и post-cut v2 никогда не бывают одновременно installable или active.
- #875 experimental carrier остаётся immutable predecessor; stable connector v1
  блокируется до exact `0.1.0` release handoff.

## Impact

Source owner — только `/int/tools`. Consumers: Backend resolver, Platform Lite,
Bridge, Agent, Node и public connector authors через опубликованные contracts.
Исключены: product runtime, DB/RLS, OAuth issuer, UI, private plugins/connectors,
Node services/installers, `CODEX_HOME`, root governance/gitlinks, production и
Punkt B feature/UI. Production cutover этим change не разрешается.

## 1. Specification
- [x] 1.1 Define guarded prod-readonly to dev refresh requirements.

## 2. Implementation
- [x] 2.1 Add `intdb project-migrate punktb-prod-dev-refresh`.
- [x] 2.2 Enforce source/target profile guardrails.
- [x] 2.3 Reload whitelisted client-state tables in a single target transaction.

## 3. Verification
- [x] 3.1 Add focused unit tests.
- [x] 3.2 Run intdb unit tests.
- [ ] 3.3 Run dry-run against `punktb-prod-ro -> intdata-dev-admin`.
- [ ] 3.4 Apply refresh against intdata dev and verify counts.

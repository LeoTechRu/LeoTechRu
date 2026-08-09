# Connector contracts experimental v0

Release-neutral public contract fixtures for the experimental Bridge connector
boundary. This directory contains no private connector implementation, provider
credential, host path, network endpoint, signing key or runtime activation.

The contract keeps provider reads and effects separate:

- `read_snapshot` operations are GET-only and never accept an effect grant;
- `provider_effect` operations produce an immutable `ActionPlanV1` and require
  an exact `EffectGrantV1` before a connector may dispatch;
- an unknown external result is `indeterminate` and is reconciled rather than
  retried automatically.

`schema.json` is a closed JSON Schema 2020-12 envelope for
`EventEnvelopeV1`, `ActionPlanV1`, `EffectGrantV1`, `EffectReceiptV1`,
`ConnectorCapabilityV1` and `ConnectorErrorV1`. `reference.py` is a stdlib-only
Protocol and deterministic in-memory mock. It performs no I/O.

This `experimental-v0` contour has no semver or deprecation promise. Consumers
must negotiate the exact `connectors-experimental-v0` version and fail closed
when no exact version is shared.

Run the self-contained conformance checks from this directory:

```bash
python -m unittest discover -s conformance -p 'test_*.py'
python conformance/validate_contract.py
```

The conformance validator uses the repository's existing `jsonschema`
development dependency. The reference Protocol itself uses only Python's
standard library.

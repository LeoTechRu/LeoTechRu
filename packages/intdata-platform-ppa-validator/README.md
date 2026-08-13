# intdata-platform-ppa-validator

`intdata-ppa-validate` is a single-command, offline verifier for the published
intData Platform Product Assertion v1 and Bridge OAuth registration URI v1
conformance corpus.

The distribution embeds an exact, closed set of published schema, vectors and
digest manifests. It makes no network request, does not inspect a repository,
and has no Backend, runtime, credential or private-configuration dependency.

Run it with no arguments:

```console
intdata-ppa-validate
```

Exit status is `0` for a valid embedded corpus, `1` when the published
validator rejects it, `2` for missing or modified embedded bytes, and `64` for
invalid invocation. Normal success output is byte-for-byte the published
validator summary.

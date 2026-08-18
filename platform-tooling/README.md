# intdata-platform-tooling

Public, MIT-licensed Python tooling for the closed intData platform v1 schema
set. The installed command is `intdata-tools` and all validation is offline.

## Guarantees

- strict UTF-8 contract input: no BOM, duplicate keys, leading/trailing
  whitespace, trailing bytes, invalid Unicode, floats, exponents, negative zero,
  or integers outside `[-9007199254740991, 9007199254740991]`;
- digest-verified `schema-set.json`, its exact 13 Draft 2020-12 resources, and
  the single `bridge-oauth-registration-uri/v1` conformance profile;
- no remote `$ref` retrieval and no fallback schema discovery;
- schema validation before RFC 8785 canonicalization or SHA-256;
- canonical UTF-8 bytes without a trailing newline;
- the same byte vectors on Windows and Linux.

Tracked schema source files may be pretty-printed with one final LF. Their
registry SHA-256 covers those exact raw bytes. The stricter no-outer-whitespace
rule applies to contract inputs and raw conformance vectors.

## Commands

Every leaf command requires an explicit `--schema-set`; there is no implicit
checkout, environment, bundled registry, or network fallback.

```text
intdata-tools schema validate \
  --schema-set ../contracts/platform/v1/schema-set.json \
  --schema urn:intdata:schema:module-manifest:v1 module.json

intdata-tools schema canonicalize \
  --schema-set ../contracts/platform/v1/schema-set.json \
  --schema urn:intdata:schema:module-manifest:v1 module.json > module.jcs.json

intdata-tools schema digest \
  --schema-set ../contracts/platform/v1/schema-set.json \
  --schema urn:intdata:schema:module-manifest:v1 module.json

intdata-tools module validate \
  --schema-set ../contracts/platform/v1/schema-set.json module.json

intdata-tools installation validate \
  --schema-set ../contracts/platform/v1/schema-set.json installation.json

intdata-tools lock verify \
  --schema-set ../contracts/platform/v1/schema-set.json \
  --expected-digest <lowercase-sha256> installation-lock.json
```

`schema canonicalize` is the only command that writes raw bytes to stdout and
does not append a newline. `schema digest` and `lock verify` write the lowercase
canonical SHA-256. Other validation commands write `valid`. Validation errors go
to stderr and return exit status 2. A document path of `-` reads stdin.

## Development

```text
python -m pip install -e ".[test]"
python -m pytest
python -m build
```

The pinned direct dependencies and their licenses are recorded in `NOTICE` and
`third_party/`. Built archives include the project MIT license, notice, and both
third-party license texts.

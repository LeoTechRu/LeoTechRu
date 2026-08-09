# intData family release source

`intdata-family.json` and `intdata-family.schema.json` are the canonical source for the unified intData MCP/plugin storefront and Codex marketplace.

The checked-in manifest remains `candidate` until all product packages and MCP resources have immutable commit, tree, entry-manifest and license-file hashes. Candidate state is discoverable and schema-valid, but the generator refuses to emit release projections from it. This prevents mutable branches, local paths and placeholder provenance from entering a released marketplace.

Release validation always uses the checked-in canonical Schema. For every distinct canonical repository, pass a trusted local checkout as `--source-repo REPOSITORY=PATH`. Its `origin`, exact commit, contained subdirectory and actual Git-bound hashes must match the manifest; shape-valid synthetic hashes are rejected.

Each protected MCP resource also carries an authorization profile. `unconfigured` is valid only for a typed `unavailable` resource, forbids bearer forwarding and issues no downstream credential. A live resource requires an immutable configured issuer/verifier/claims/internal-assertion profile; the generator never infers one from another resource or from the outbound #858 bridge.

Release projections:

```bash
python3 codex/scripts/generate_intdata_family.py validate
python3 codex/scripts/generate_intdata_family.py generate \
  --manifest <pinned-release-manifest> \
  --source-repo https://github.com/LeoTechPro/intData-tools.git=/int/tools \
  --source-repo <canonical-repository>=<trusted-checkout> \
  --output-dir <empty-output-dir>
python3 codex/scripts/generate_intdata_family.py check \
  --manifest <pinned-release-manifest> \
  --source-repo https://github.com/LeoTechPro/intData-tools.git=/int/tools \
  --source-repo <canonical-repository>=<trusted-checkout> \
  --output-dir <generated-output-dir>
```

Repeat `--source-repo` for every repository in the release. `generated_at` is an immutable canonical UTC manifest input. It must come from the approved release metadata or equivalent `SOURCE_DATE_EPOCH`, never from the generator clock. Output inside the active or default `CODEX_HOME` is rejected, including through resolved symlinks.

One release emits exactly:

- `intdata.family-catalog.v1.json`;
- `intdata.family-catalog.v1.schema.json`;
- `marketplace.json`;
- `intdata.family-release-lock.v1.json`;
- `intdata.family-activation.v1.json`.

The activation record binds the exact filenames and SHA-256 bytes of the other four projections. It is immutable release metadata, not authorization to switch the public active pointer.

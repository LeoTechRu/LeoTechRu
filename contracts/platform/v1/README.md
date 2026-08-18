# Platform contracts v1

This directory is the offline, language-neutral contract bundle for platform module resolution, installation locking, release verification, Bridge OAuth approval receipts and product-scoped assertions.

## Loading rules

- Load exactly the 13 `$id` values listed in `schema-set.json`; a missing, duplicate or additional schema ID fails closed.
- Resolve `$ref` only from the local registry assembled from that exact set. Network retrieval is forbidden. The Draft 2020-12 meta-schema URI identifies the dialect and is not an application reference.
- Verify each registry entry against the SHA-256 of the raw source file bytes. Sources in this bundle are UTF-8, pretty-printed with LF and one final LF.
- Contract inputs use strict UTF-8 JSON: no BOM, duplicate object member, outer whitespace, floating-point number, unsafe integer, lone surrogate or non-JSON numeric constant. RFC 8785/JCS canonicalization preserves Unicode code points and orders object names by UTF-16 code units.
- Integers on interoperable numeric surfaces are limited to `[-9007199254740991, 9007199254740991]`; sizes that may exceed this range are canonical decimal strings.

Run `python3 conformance/validate.py` with Python 3, `jsonschema` and `referencing` installed. It checks the meta-schemas, offline references, exact schema-set hashes, positive/adverse fixtures, JCS vectors, URI normalization and cross-document semantic vectors.

`conformance/digests.json` is the platform-v1 umbrella manifest. It pins the
exact `schema-set.json` plus the immutable domain manifests
`terminal-dependency-digests.json` and `approval-receipt-digests.json`; each
domain manifest remains the authority for its own per-file hashes. The umbrella
and domain aggregates use the same explicit language-neutral byte recipe, so a
consumer must name the manifest path and digest kind rather than use an
ambiguous "terminal aggregate" label.

## Signatures and release trust

`SignatureEnvelopeV1` is the standard DSSE v1 object with `payloadType`, padded-RFC4648 `payload` and `signatures`. The `keyid` is only a hint; algorithm, role, trust state, validity and payload digest binding are verified separately.

`ReleaseVerificationKeySetV1` is the canonical payload for `application/vnd.intdata.release-keyset.v1+json`. Bootstrap uses revision 1 and `previous_digest: null`; each later revision is exactly previous+1 and binds `sha256:` plus the digest of the exact prior JCS payload. Acceptance requires at least two cryptographically verified, distinct public-key fingerprints from the immutable three-key `ReleaseBootstrapRootSetV1`. The bootstrap root-set JCS bytes/digest and lifecycle adverse vectors are in `conformance/vectors.json`. Offline signers receive only standard DSSE PAE plus an opaque key reference, capped at exactly 262144 bytes. Private material never enters Tools or Backend.

`TrustBundleV1` does not carry release artifact key material. It pins a complete `ReleaseVerificationKeySetV1` by ID, revision, digest and immutable bootstrap-root-set digest; the key set alone owns active, retired and revoked online release keys. `RegistrySnapshotV1.accepted_signers` likewise excludes release keys and carries only non-release registry/module/installation/scan admissions.

## Bridge receipt and URI profile

`BridgeOAuthRegistrationApprovalReceiptV1` is a public decoded conformance representation. Compact software-statement JWT bytes stay inside the private Bridge/Backend control plane and never leave it through Tools. Both `iss` and scalar `aud` are exact projections from the signed `InstallationLockV1`; Lite substitutes both customer-private values and has no central fallback. Identity and revision claims are checked against a verified `PlatformProductAssertionV1`, durable approval state and current Backend state before issuance/use.

The receipt metadata digest is `sha256:` plus SHA-256 over the exact RFC 8785 object `{software_id,client_name,redirect_uris,grant_types,token_endpoint_auth_method,scopes,organization_id}`. Normalize by `bridge-oauth-registration-uri/v1`, reject distinct-input normalization collisions, otherwise deduplicate exact normalized strings and sort ascending unsigned UTF-8 bytes. Grant types and scopes use identity normalization with their closed ASCII grammars. Do not substitute another URL library's normalization behavior.

## Product assertion

`PlatformProductAssertionV1` is the decoded conformance representation for the ES256 `at+jwt` contract delegated from issue #887. Its claims object is closed, `aud` is scalar, IDs/scopes are canonical, revision bounds include zero through the safe-integer maximum, and time vectors carry an explicit `verifier_now` and clock skew. Compact JWT bytes and private signing stay outside this public bundle.

JSON Schema deliberately covers structure. Semantic checks that require trusted time, signed locks, prior key-set state, signature verification, durable approval or configured issuer/audience are specified by the language-neutral vectors and performed by consumers; this directory does not add a Tools runtime.

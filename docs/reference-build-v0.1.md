# Reproducible reference builds v0.1

The `reference_cds` profile packages one independently selected whole DNA-CDS or
RNA-CDS reference after accepted Components → Construct → Molecular passes. It
retains the exact spelling, checks and all remaining obligations. It does not
compile arbitrary intent programs or establish biological refinement.

From the repository, with CellWeave installed, one command builds a package:

```sh
cellweave reference-build --alphabet RNA \
  --reference-dir data/references/fap_car --output fap-rna.cwb
```

For a source checkout without installing the package, use
`PYTHONPATH=src python -m cellweave` instead of `cellweave`. Choose `DNA` to reproduce
the separately pinned DNA reference. The command uses only retained local files;
it performs no network fetch or authoring-code execution. The output parent must
already exist. Unknown modalities, incomplete sources and failed checks produce a
nonzero exit and cannot publish a success package.

The supported reference is the reviewed FAP-CAR coding sequence set. Manifest,
record and source/review identities are independently fixed in
`registry/reference_builds.py`; they are never inferred from the emitted output.
The reference directory includes `manifest.json`, `source-excerpts.html` and
`independent-audit.json`. Referenced upstream archives not retained locally keep
their original hashes and locators; the package does not invent their contents.

## Frozen authority and output

`prepare_reference_build("RNA", reference_directory)` returns an immutable
`ReferenceBuildRequest`. `build_reference_package(request, reference_directory)`
returns package bytes and a manifest; `publish_reference_package(package, output)`
rechecks current evidence and publishes atomically. `--request request.json` accepts
a previously frozen reference request instead of `--alphabet`.

This profile starts at selected components. Its explicit `ReferenceBuildRequest`
wraps the authoritative `ConstructRequest` and export policy. The intent-root
`BuildRequest` remains supported by the separate abstract/synthetic pipelines;
there is no established intent-to-FAP behavioral realization to package here.
The reference build therefore records `upstream_intent: null` and explains that
boundary instead of fabricating an upstream request or proof. Only the supported
whole-CDS layout can pass; changed target, reference, selection or layout must
satisfy the existing independent checkers.

A `.cwb` file is a canonical stored ZIP archive containing:

- `manifest.json`: canonical build identity inputs, file sizes/hashes, accepted
  stage identities and locked tool versions.
- `request.json`, `inputs/registry.json` and `references/`: frozen authority,
  components and independently pinned retained source/review bytes.
- `stages/`: accepted component, construct and molecular records, including their
  payloads, checks, dependencies and pass/source correspondence.
- `molecular.json` and `sequence.fasta`: the exact molecular specification and CDS.
- `checks/`: independent composition, construct and molecular reports.
- `result.json`: selected alternative, feature/source maps, completion scope and
  unresolved obligations. Dynamic model locks are explicitly empty because this
  reference supplies no molecular behavior model.
- Optional `run.json`: machine label, timestamp and local source locations.

`complete_payload_features` and `molecular_behavior` remain unresolved. An accepted
package is a digital CDS specification, not a complete delivered molecule or
verified expression, delivery, same-cell coexistence or therapeutic effect.

## Reproducibility and identity

The manifest's `build_fingerprint` is derived from its complete canonical JSON.
It includes every core file hash and size, request identity, stage identity and
tool version. It excludes `run.json` and has no recursive self-hash field. The
archive SHA-256 identifies every byte, including optional run metadata. The
canonical nucleotide SHA-256 identifies only the exact sequence symbols.

For identical supported requests, reference content, tools and export policy,
repeated builds and relocated input directories reproduce identical core files,
build fingerprints and archive bytes when run metadata is absent or unchanged.
ZIP entries use sorted names, fixed timestamps and permissions, and no compression.
Canonical JSON and LF FASTA conventions are fixed. Harmless source manifest JSON
formatting is canonicalized; retained source and review files remain byte-exact.

Core source locations must be portable logical paths, such as `design/reference.py`.
Host absolute paths, traversal and platform-specific separators are rejected.
Record host paths only through optional `RunMetadata.locations`; changing them,
the timestamp or machine label does not change the canonical build fingerprint.
Source lineage is retained; it is not silently stripped or rewritten. Changes to
logical source identities, export wrapping or supported tools can change the build
identity even when nucleotide identity is unchanged.

## Inspection and independent reconstruction

```sh
cellweave reference-inspect fap-rna.cwb
cellweave reference-verify fap-rna.cwb --expected-build TRUSTED_BUILD_FINGERPRINT
```

Retain the expected fingerprint independently from the original successful build.
Alternatively, use `--expected-request trusted-request.json`. The API is
`verify_reference_package(data, expected_request=...)` or
`verify_reference_package(data, expected_build_fingerprint=...)`.

Inspection validates the strict manifest/container shape, canonical serialization,
file inventory, sizes and hashes. It labels the result historical. It does not
promote stored PASS labels into current acceptance. Fresh verification requires
caller-supplied authority, reconstructs the pinned offline reference directory in
a temporary location, reruns all accepted stages with current tools, and compares
every core byte and evidence identity. Edited sequences, forged reports, missing
obligations and stale tool versions fail even if the attacker recomputes file
hashes. No import path executes authoring Python or downloads dependencies.

## Atomic publication and validation

Publication completes independent reconstruction before touching the output. It
writes one bounded sibling temporary archive, flushes and syncs it, then atomically
replaces the destination. Errors before replacement preserve the prior complete
archive and remove the temporary file. A process killed before cleanup can leave
an unreferenced temporary file; it cannot expose a partial success archive at the
requested destination. This is single-file atomic visibility, not a multi-output
transaction or a power-loss durability guarantee for the parent directory.

Strict import rejects duplicate members, unsafe paths, symlink/executable members,
unsupported compression/metadata, extra files, noncanonical bytes, truncated data
and oversized inputs. Limits are 64 MiB total, 16 MiB per payload file, 1 MiB per
manifest/run document and 128 entries. Reference files are independently bounded
and must be regular local files without symlinks.

Hosted CI installs the package on Python 3.11 and 3.14, exercises the CLI, reconstructs
both modalities offline, compares relocated/repeated build bytes and retains
reference-build logs on failure. It reports the tested revision/platform. See the
[manifest schema](build-manifest-v0.1.md) and
[exact-CDS pipeline](exact-cds-pipeline-v0.1.md) for the underlying contracts.

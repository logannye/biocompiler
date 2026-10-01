# Checked molecular design and packaging v0.1

The `software_molecular_design` workflow constructs one complete structural
`mature_linear_rna` specification from independently supplied fragment and layout
authority. It implements multi-region assembly, independent generated-candidate
checking and reproducible package export. The request, examples and results carry
fixed `software_fixture`, `software_test`, `not_promoted` and `not_admitted`
labels. No functional component or biological reference is supplied by this profile.

This is a Components → Construct → Molecular software pipeline. Its Components
entry consists of selected literal sequence fragments. It has no upstream intent,
digital-mechanism assignment or biological composition proof. General `compile()`
and human therapeutic admission remain unavailable. M13's human-reference and
biological acceptance obligations remain open.

## Frozen authority and supported scope

`MolecularDesignRequest` retains the complete ordered fragment inventory, selected
source slices, destination layout, independently specified CDS protein spelling,
chemistry/end features and generic RNA target. Each `SequenceFragment` has exact
canonical uppercase symbols, a sequence hash and a source locator. Each
`FragmentPlacement` separately pins the entire fragment record and supplies
source and destination coordinates. A locator declares the supplied fixture's
provenance; it does not establish that an external source was extracted or reviewed.
The checker recomputes hashes and compares against the complete request authority.

Coordinates are zero-based and half-open. Supported placements form an ordered,
gap-free partition: nonempty 5′ UTR, one CDS, nonempty 3′ UTR and an optional exact
poly(A) region. Source coordinates need not equal destination coordinates.
Every selected fragment must be accounted for. Orientation is forward, frame zero,
with no inferred junction bases, reverse complementation, alphabet conversion,
sequence optimization, additional coding regions or co-payloads. Region names
are fixture annotations and confer no biological function.

The molecule is single-stranded linear RNA. The existing readiness profile's
explicit cap, terminal chemistry, modification and tail conventions apply.
Unsupported feature values cannot be accepted, and unknown required features
block completion. Chemistry is never inferred from nucleotide letters. Input
limits bound each fragment to 100,000 symbols and the inventory to 16 records;
the structural profile further restricts supported region layouts.

## Generation and independent acceptance

`generate_molecular_design_construct` produces layout without emitted sequence.
The RNA emitter uses that explicit construct to propose a `MolecularDesignArtifact`,
which wraps a `PayloadMolecule` and exact fragment source maps.

Independent request, construct and molecule checks live in
`verification/molecular_design.py`; they import neither generator nor emitter.
The caller supplies `expected_request_fingerprint` from independent authority.
Checks reconcile selected fragment identities, hashes, coordinates, ordering,
membership, source locators, chemistry and emitted nucleotide slices. CDS start,
termination and standard-code translation are checked against the supplied protein
expectation. Preserving protein identity never excuses a nucleotide substitution.

The pass manager registers the selected fragment root and both transformations.
Its completion profile requires fresh request, layout and molecular checks.
Results retain request, construct, candidate, target, policy and tool dependencies;
changing an upstream dependency invalidates affected downstream receipts.
Layout requirement IDs express provenance only, not behavioral refinement.
Biological function, expression, delivery and experimental-material obligations
remain unresolved after structural completion.

Candidate checking and exact-reference reproduction have different authorities.
An explicitly revised fragment/layout request may produce a valid new structural
candidate. The same substitution fails under the original request and cannot
pass exact-reference equality merely because its protein is unchanged. Existing
`check_payload` and the exact DNA/RNA CDS pipelines keep their original contracts.

## Build, inspect and reconstruct

With the package installed:

```sh
python examples/molecular_design.py --output generated/molecular-design
biocompiler molecular-design-build \
  --request generated/molecular-design/request.json \
  --output generated/molecular-design/cli.bcb
biocompiler molecular-design-inspect generated/molecular-design/cli.bcb
biocompiler molecular-design-verify generated/molecular-design/cli.bcb \
  --expected-request generated/molecular-design/request.json
```

From a source checkout, prefix example commands with `PYTHONPATH=src` and use
`PYTHONPATH=src python -m biocompiler` for the CLI. Verification also accepts an
independently retained `--expected-build` identity. Neither authority may be
borrowed from the package being verified. Commands perform no external fetches
or authoring-code execution.

The API is `build_molecular_design_package(request)`,
`verify_molecular_design_package(data, expected_request=request)` and
`publish_molecular_design_package(package, output)`. Optional `run_metadata`
stays outside canonical build identity. FASTA has a versioned fixed 80-column
layout; complete chemistry and provenance remain in structured records.

The canonical `.bcb` archive contains exactly 16 core files:

- `request.json`, `inputs/fragments.json`, `inputs/layout.json` retain authority.
- `construct.json`, `candidate.json`, `molecular.json`, `sequence.fasta` and
  `source-map.json` retain layout, full candidate, molecule and exact spelling.
- `checks/request.json`, `checks/construct.json`, `checks/molecular.json` and
  `stages/components.json`, `stages/construct.json`, `stages/molecular.json`
  retain independent checks and accepted stage records.
- `handoff.json` and `result.json` retain nominal design identity, completion
  scope and unresolved obligations.

`manifest.json` pins every core byte and tool version; optional `run.json` records
execution metadata. Inspection is historical content/integrity inspection only.
Fresh verification reconstructs every core artifact with current trusted tools
and compares the complete archive against independent request/build authority.
Rehashing edited evidence, chemistry, source maps or sequence cannot establish
acceptance. Repeated builds and relocated requests reproduce canonical identities.

Publication uses the existing bounded canonical ZIP format and single-file atomic
replacement, after fresh verification. Invalid builds and failed publication
preserve an existing destination. CLI output cannot overwrite its input request
or run-metadata authority. Existing package families remain separately identified.

## Design handoff and scope

`MolecularDesignHandoff` binds the exact nominal molecule, sequence, features and
design/candidate identities. Actual manufactured material identity, quality and
potency remain unestablished. Clinical authorization remains external. The handoff
contains no production procedure, invented assay result or promise of function.

The integrated example uses a literal 17-base, four-region nonfunctional fixture
with independently fixed expected output. A second authorized synonymous coding
fragment produces a distinct reproducible design. The same edit under the first
request fails despite a recomputed sequence hash. Tests additionally cover source
and coordinate changes, unsupported/unknown chemistry, stale dependencies,
cross-request substitution, human-use rejection and rehashed package tampering.
Hosted CI installs the package and exercises the full build/inspect/verify path
on Python 3.11 and 3.14. These checks establish software implementation behavior,
not molecular-model validity or biological profile admission.

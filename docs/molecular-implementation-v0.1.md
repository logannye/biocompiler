# Checked molecular implementation v0.1

This profile connects a therapeutic source request to a declared molecular plan,
its supplied coding segments, a derived construct and an exact RNA sequence. The
first supported family is one RNA encoding a declared secreted-product precursor.
It adds explicit precursor, processing, product and transport relationships to the
earlier [product-cassette compiler](intent-candidate-v0.1.md).

Completion means `secreted_precursor_structure`. Physical function remains
`unestablished`, therapeutic implementation remains `partial`, and human
therapeutic admission remains `not_admitted`. A matching translation and a
consistent processing boundary do not demonstrate expression, cleavage or
secretion. The [example](../examples/molecular_implementation.py) uses artificial,
nonfunctional sequences and declared host assumptions throughout.

## Start with the example

From a source checkout:

```sh
PYTHONPATH=src python examples/molecular_implementation.py --output generated/molecular-implementation
```

The example saves the original source, requirement analysis, independent request
authority and build records. It exercises these cases:

| Case | Expected result |
| --- | --- |
| `compact` | The shorter eligible supplied precursor architecture is selected. |
| `extended` | An explicit architecture allowlist selects the longer supplied prefix. |
| `strict` | No molecule: complete implementation was required, but behavioral and physical obligations remain unresolved. |
| `exhausted` | No molecule: no supplied architecture fits the maximum nucleotide length. |
| `missing_host` | No molecule: the required providers are absent from the supplied library. |

The example's compact RNA is 20 nucleotides; the extended RNA is 23. Those small
sizes are deliberate software fixtures, not functional payload designs. Its
`mature_protein` is the single artificial residue `F`; the two declared precursor
spellings are `MAF*` and `MAAF*`, including the terminal translation stop.

The Python entry point exposes the retained artifacts:

```python
import biocompiler as bc
from examples.molecular_implementation import make_implementation_request

request = make_implementation_request()
requirements = bc.analyze_implementation_requirements(request.source)
bc.verify_implementation_requirements(
    requirements, expected_source=request.source
)

compilation = bc.compile(request)
record = compilation.record
bc.verify_implementation_build(record, expected_request=request)

print(record.selection.selected_architecture_id)
print(record.construct.precursor_protein)
print(record.construct.mature_protein)
print(record.molecule.sequence)
fasta = bc.export_implementation_fasta(record, expected_request=request)
```

`bc.compile(ImplementationRequest(...))` returns `ImplementationCompilation`,
which contains `record`, `manager` and `pipeline_result`. Inspect
`record.status` before accessing optional construct or molecule fields:
`candidate_built` contains the molecular stages; `no_candidate_found` retains the
analysis and selection record with those stages absent. A correspondence check
can pass for an accurately reported empty search without producing a molecule.

## What enters the compiler

`ImplementationRequest(source, library, constraints)` freezes the three input
authorities. `source` is an existing `BuildRequest`, `HumanBehaviorRequest`,
`HumanDeploymentRequest` or `HumanAcceptanceRequest`. The full original source,
provenance, target, parameter bindings and wrapped contracts remain retained.
An explicit target is required for molecular selection. A human target stays
human; the compiler does not change its context to obtain eligibility.

The bounded source profile contains one role, one secretion declaration, one
ongoing secretion action and one condition rule installing that action. A bare
declaration is insufficient. The action identifies the requested product and may
include a typed production-rate expression. Such a rate remains a requirement;
the structural compiler does not infer how the emitted RNA achieves it.

The separate `analyze_implementation_requirements(source)` entry point accepts
broader existing source graphs, including designs outside that bounded family.
It preserves every source node and returns inspectable unsupported or unresolved
requirements instead of silently omitting extra behavior. Empty sources and
missing targets can be analyzed, but do not imply a usable molecular design.
Malformed documents and inputs outside the bounded import limits are errors.

The resulting `ImplementationRequirements` contains:

- The complete original source, its fingerprint and ordered source-node inventory.
- Typed `ProductRequirement` records with product, role, declaration, action,
  rule, guard and optional rate references.
- `ImplementationObligation` records classified as encoding,
  localization/processing, sensing, control, temporal/state, quantitative, action,
  host/deployment, evidence/admission or other source semantics.
- Diagnostics distinguished as `unsupported_semantics`, `missing_refinement` or
  `contradiction`.

Each obligation retains immutable operation arguments, source IDs and target/
contract context. Source-node obligations contain the entire semantic node;
wrapped-contract obligations contain the full contract. All obligations retain
`status="unresolved"` and
`evidence_boundary="specification_only_no_physical_function"`.
`supported_profile` is computed from the original source shape. It does not mean
the requirements are implemented or that the analysis has been independently
verified.

A known negative constant secretion rate or contradictory declared deployment
timing can produce a contradiction diagnostic. Missing observations and unknown
delivery bounds are not automatically contradictions. Healthy-context labels
remain evaluator-only; shutdown and input loss require explicit control
refinements and actuators. Analysis never adds an implicit priority that overrides
the original activation guard.

## Supply an explicit molecular library

The compiler searches a finite caller-supplied `ImplementationLibrary`. It does
not retrieve biological parts, invent a targeting peptide, optimize codons or
authenticate an external reference. The library can be constructed with the
exported Python records or loaded with `ImplementationLibrary.from_json(...)`.
The complete authored example is
[`fixture_library`](../examples/molecular_implementation.py).

| Record | What the caller supplies |
| --- | --- |
| `SequenceAuthority` | Exact uppercase RNA bases, SHA-256, source locator, provenance category and optional pinned reference identity. |
| `CodingSegment` | One supplied sequence and its expected peptide, labeled `signal_peptide`, optional `junction`, `mature_product` or `terminal_stop`. |
| `CodingJunction` | Each adjacent segment pair in order, with the supported `concatenate_in_frame` policy. |
| `SecretedRNAArchitecture` | Product identity, exact target fingerprint, UTRs, ordered segments/junctions, precursor and mature proteins, declared cleavage boundary, dependencies, bindings and molecule features. |
| `Provider` | Declared host or external capability, recipient role, scope, compartment and supported target identities. |
| `ImplementationLibrary` | Versioned architecture and provider inventories. |

`SequenceAuthority.provenance` is `software_fixture`, `supplied_sequence` or
`supplied_reference`. The last requires a `PinnedIdentity` of kind `reference`.
This is caller-supplied attribution, not independent source extraction, reference
promotion or evidence of biological performance. Existing software-fragment
schemas keep their original evidence restrictions.

The current family requires this order:

```text
5′ UTR → [signal-peptide coding segment → optional coding junction
          → mature-product coding segment → terminal stop] → 3′ UTR → optional poly(A)
```

The bracketed segments form one continuous CDS, not separate translated products.
Each adjacent junction is explicit. All segments must preserve the reading frame
and match their supplied peptide expectations. The whole CDS must translate to
the declared precursor. The supplied `cleavage_after_aa` must identify the
boundary after the signal prefix and optional junction, and the remaining
precursor residues must equal `mature_protein`. These checks establish consistency
of the declared processing design; they do not predict physical cleavage.

Libraries contain at most 32 architectures and 32 providers. Each assembled
architecture is bounded to 100,000 supplied nucleotide positions. Reusing a
sequence-authority ID requires exactly the same record throughout the library.
Every architecture with the same product identity must declare the same
`mature_protein` spelling. Different mature-product variants need distinct
product identities; a shorter but different protein cannot win the search for
the original product. Architectures may vary their precursor prefixes or use
different supplied encodings while retaining that mature-protein expectation.

## Dependencies are part of the design

Every architecture declares these required capabilities for the selected source
role, at cell scope:

| Capability | Required compartment |
| --- | --- |
| `host_translation` | `cytoplasm` |
| `secretory_translocation` | `secretory_pathway` |
| `precursor_processing` | `secretory_pathway` |
| `secretion_transport` | `secretory_pathway` |

Every dependency has exactly one `ImplementationDependencyBinding`, including an
explicit unresolved binding when no provider is supplied. A usable declaration
must match capability, role, scope, compartment and exact target context. Host
providers also require the capability in the original target; human targets
require the corresponding dependency in their human contract. Provider
prerequisites remain unsupported in this bounded family. An absent, unresolved
or incompatible provider prevents that architecture from being selected.

The target must declare `cytoplasm`, `secretory_pathway` and `extracellular`, which
are used by the plan. Passing dependency checks confirms declaration consistency.
`ImplementationDependency.functional_support` remains `unestablished`; named
host capabilities and evidence references are not measurements of cell function.

## Selection, plan and emitted coordinates

`ImplementationConstraints` separates hard requirements from ranking:

- `allowed_architecture_ids`: an empty tuple permits all supplied architectures.
- `max_length`: an optional nonnegative maximum for the entire RNA.
- `preference`: `shortest` ranks by length, then architecture ID; `lexical` ranks
  by architecture ID.
- `require_implementation_complete`: controls whether a partial structural result
  is acceptable as a research artifact.

Opaque constraints or preferences already stored in a `BuildRequest` cannot be
ignored. They remain visible in analysis, and an `ImplementationRequest` rejects
them instead of guessing how to translate them into this family's constraints.

Selection enumerates every supplied architecture for the exact product, retains
each rejection reason, and ranks only eligible options. Checks cover target and
modality, declared contradictions, length/allowlists, sequence pins, segment and
precursor translation, processing correspondence, explicit RNA chemistry and
dependency compatibility. Library ordering does not decide ties. A missing
product binding, unsupported source and exhausted bounded search are distinct
outcomes; none demonstrates general biological infeasibility.

The selected `ImplementationPlan` records translation, precursor, processing,
mature-product and extracellular-destination roles with explicit relationships.
It links the source product requirement to coding segments and retains every
unresolved obligation. `ImplementationComponents` carries the exact selected
architecture and sequence authority.

`ImplementationConstruct` derives contiguous whole-segment placements, nucleotide
junction offsets, amino-acid ranges and the nucleotide processing boundary. All
machine-readable `SequenceRange` coordinates are zero-based and half-open.
`cleavage_after_aa` counts precursor residues before the declared boundary;
`cleavage_after_nt` identifies the corresponding boundary in the entire RNA,
including its 5′ UTR. The terminal stop is retained as coding sequence but does
not add an amino-acid residue to these ranges.

Emission creates a `PayloadMolecule` with profile `mature_linear_rna`, RNA
alphabet, linear topology, one strand, exact bases and annotated regions. Here
“mature RNA” describes the requested RNA artifact; “mature protein” describes the
declared product remaining after precursor processing. Neither term establishes
that a cellular processing event occurred.

## Chemistry and sequence are separate

The architecture carries explicit `PayloadFeature` declarations for `cap`,
`poly_a_tail`, `nucleotide_modifications`, `end_structure`, `five_prime_end` and
`three_prime_end`. The structural checker requires the supported feature inventory,
known supported values, cap/end consistency and exact agreement between a
declared poly(A) length and its placed bases. It does not fill missing chemistry
with defaults. This version supports canonical RNA spelling and declares
nucleotide modifications as `none`; other modification profiles are unsupported.

FASTA contains bases and a scope/build header. It cannot encode all terminal
chemistry, dependency assumptions, source requirements or unresolved obligations.
Keep the build JSON and original request alongside every FASTA export.

## Partial and strict requests

The default `require_implementation_complete=False` permits a checked structural
research candidate while preserving its unresolved behavioral requirements.
It never turns a constitutive encoding structure into an implementation of the
source condition.

```python
from dataclasses import replace

strict_request = replace(
    request,
    constraints=bc.ImplementationConstraints(
        require_implementation_complete=True
    ),
)
strict_record = bc.compile(strict_request).record
assert strict_record.status == "no_candidate_found"
assert strict_record.molecule is None
```

The current family cannot meet strict completeness. Its alternatives retain an
`implementation_incomplete` rejection rather than emitting an apparently complete
therapy. Setting the flag does not change human admission or establish evidence.

## Independent checking and reuse

The pass manager admits the chain
source → requirements → selection/plan → components → construct → molecule only
after independent correspondence checks. The checker reconstructs source
requirements, alternatives, declared relationships, segment coordinates and
emitted bases against the frozen request. It does not import the requirements
analyzer, selector, construct generator or emitter as acceptance oracles.
Normative schemas, translation utilities and the structural RNA checking kernel
are shared specification infrastructure.

`ImplementationBuildRecord` retains the request, analysis, all bounded
alternatives, optional molecular stages, checks and tool identities. Reading a
saved record only inspects historical claims. Fresh
`verify_implementation_build(record, expected_request=request)` requires the
independently retained complete request, reruns current checks and compares the
saved assessments. Changed inputs, tool identities, bases, coordinates or claims
invalidate verification. `export_implementation_fasta` performs the same fresh
verification before exporting a selected molecule.

The corresponding CLI workflow is:

```sh
PYTHONPATH=src python -m biocompiler implementation-analyze --request generated/molecular-implementation/source.json --output generated/molecular-implementation/analysis.json
PYTHONPATH=src python -m biocompiler implementation-build --request generated/molecular-implementation/compact.request.json --output generated/molecular-implementation/cli.build.json
PYTHONPATH=src python -m biocompiler implementation-verify generated/molecular-implementation/cli.build.json --expected-request generated/molecular-implementation/compact.request.json
PYTHONPATH=src python -m biocompiler implementation-fasta generated/molecular-implementation/cli.build.json --expected-request generated/molecular-implementation/compact.request.json
PYTHONPATH=src python -m biocompiler inspect generated/molecular-implementation/cli.build.json
```

With an installed package, replace `PYTHONPATH=src python -m biocompiler` with
`biocompiler`. Analysis returns exit code 0 when the report was successfully
produced, even if the source is unsupported. Build/verify return 0 for a checked
molecule and 1 for an accurately retained empty selection; input or verification
errors return 2. FASTA goes to stdout and requires a selected molecule. These
commands produce JSON/FASTA artifacts, not `.bcb` archives. JSON import is strict
and does not execute authoring Python or retrieve external sequence records.

## What remains outside this profile

This family implements no sensing, conditional regulation, quantitative secretion
rate, memory, shutdown, delivery, manufacturing or therapeutic-effect model. It
does not establish that a supplied signal peptide targets a compartment, that a
declared site is cleaved, or that a mature product is functional. DNA generation,
multi-molecule payloads, general mechanism search, codon optimization and automatic
natural-language authoring remain outside this profile.

Changing a product against a frozen library must select a corresponding supplied
architecture or explain why none exists. Changing a guard changes the retained
requirements/build identity; the RNA may remain unchanged because that guard is
still unimplemented. Future sensing/control families must add their own checked
molecular correspondence. Quantitative models must bind to the selected parts,
sequences and context rather than infer behavior from a structural PASS.

The local GUI continues to show the earlier product-cassette workflow until it is
explicitly extended for these new records. See the
[architecture decision](decisions/0004-checked-molecular-implementation.md),
[toolchain contracts](toolchain-contracts.md) and
[human admission policy](human-admission-v0.1.md) for the wider boundaries.

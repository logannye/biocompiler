# Checked supplied circuit construction v0.1

R4 adds `CircuitConstructionRequest` and checked construction from independently
supplied roots and explicit operations. Its claim is **correspondence to the
supplied construction authority**. It does not select a molecular mechanism or
establish published-source fidelity, cellular processing, circuit function,
experimental support or human admission. The entire original `CircuitRequest`,
human target and unresolved behavior/deployment obligations remain attached.

The [example](../examples/circuit_construction.py) uses six-symbol artificial
software fixtures. None of its fragments or feature names is a functional part
or published experimental record. R1's metadata draft remains unmerged; no R4
fixture closes source-dependent R5–R13 acceptance.

## Authority and independent replay

A request contains root records, an ordered acyclic operation graph,
sequence-free output ports, explicit chemistry/feature transitions, final
molecules/complexes, required roles, experimental amounts and payload-region
contracts. Root records are authority supplied by the caller; their provenance
labels are not independent review of external source bytes. Output ports contain
no expected sequence, length or generated fingerprint.

The producer constructs intermediate values with residue correspondence and
consumed terminal-stop records. Final members have their own coordinate frames;
the derivation chain retains every source coordinate. A noncovalent complex names
its constituents and stoichiometry without inventing a concatenated sequence.
Required payloads, helpers, encoded products, host providers, experimental inputs,
controls and assay references remain separate. Amounts stay outside nominal
molecular identity, but fresh verification compares their exact authority too.

The checker reconstructs each operation independently from the separately
supplied complete request. It imports neither producer nor generator as an
acceptance oracle. Only immutable schemas, parsing and normative codon-table data
are shared. It compares intermediate values, derivations, consumed coordinates,
feature/chemistry correspondence, complete member inventory, amounts and final
bundle. Recomputing a changed artifact's self-hashes does not establish authority.
Saved assessments must equal a fresh current replay; a stored PASS cannot be
reused after request, candidate, checker or profile changes.

## Primitive capability map

| Operation | Checked software contract and limits |
| --- | --- |
| Slice / concatenate | Explicit ordered source paths and exact residue coverage; no hidden literal output. |
| Orientation | Declared reversal/complement mapping with source coordinates retained. |
| Transcription | Explicit coding-strand DNA-to-RNA mapping over a supported path; no inferred transcript ends. |
| RNA or protein cleavage | Explicit products and boundaries in the correct alphabet; all outputs of a step publish together. |
| RNA or protein splicing | Explicit ordered forward source spans; current execution requires increasing, nonoverlapping spans within each source and complete allocation across declared products. Reordered or repeated spans are rejected, not silently sorted. |
| Circularization | Declared junction, topology and coordinate correspondence; the nominated source origin is preserved. |
| Base editing | Canonical substitutions and chemical changes are separate. A chemical inosine declaration retains its canonical parent A; it does not silently emit G. |
| Ordinary translation | Forward contiguous RNA region, literal AUG, standard code, frame and terminal stop; no alternative initiation inferred. |
| Conditional translation | Explicit codon outcomes bound to declared assumptions; these are conditional structural checks, not a derived sensor mechanism. No-product branch semantics remain unsupported. |
| Multiple ORFs | Each independently selected region has its own translation policy and product. |
| Ribosomal skipping | A complete nonoverlapping residue allocation across products, including actual retained residues; distinct from proteolytic cleavage. |
| Noncovalent complexes | Exact declared constituents and stoichiometry; no inferred binding, complementarity, assembly efficiency or co-delivery. |

The public translation policy is `CircuitTranslationPolicy`; the older
`TranslationPolicy` API and ordinary-CDS profile remain unchanged. Family-specific
translation and absence semantics require later mechanism authority. R4 provides
the bounded primitives, not a biological family implementation.

Chemistry inheritance is allowed only for unchanged complete declarations with
identity correspondence. Other transformations explicitly dispose of every
incoming chemistry facet and feature. A declared replacement specifies product
chemistry; it does not prove the material's biochemical fate. Unknown chemistry
cannot acquire a complete nominal identity from matching bases alone.

## Payload forms and completeness

| Requested form | Topology | Required alphabet |
| --- | --- | --- |
| `delivered_rna` | linear or circular | RNA |
| `delivered_dna` | linear or circular | DNA |

Each distinct covalent requested payload needs its own
`PayloadStructureContract`, with explicit required feature identities/kinds and
boundary provenance. Nucleotide complexes expand to their covalent constituents.
Contracts do not infer a universal list of regulatory regions or prove their
function. Missing authority, incomplete extent/chemistry, unsupported form or
unknown complex stoichiometry prevents a complete structural handoff. A template
or opposite alphabet cannot stand in for a requested delivered form.

`strict` and `diagnostic` retain the same assessment and missing-member evidence.
Diagnostic builds may be inspected even when partial; they cannot use the
complete-set handoff. A strict PASS requires all supplied structural obligations.
It does not discharge the original therapeutic obligations.

## Python and CLI

```python
import biocompiler as bc
from examples.circuit_construction import make_construction_request

authority = make_construction_request()  # Artificial bookkeeping example only.
build = bc.compile(authority)
fresh = bc.verify_circuit_construction(build, expected_request=authority)
record = bc.verified_circuit_molecules(build, expected_request=authority)
```

The example helper requires a checkout. The public API accepts a typed request
or one parsed from retained JSON; production use never loads example fixtures
implicitly. Keep the independent request separately from candidate artifacts.

```sh
PYTHONPATH=src python examples/circuit_construction.py --output generated/construction
PYTHONPATH=src python -m biocompiler circuit-build --request generated/construction/request.json --output generated/construction/cli.build.json
PYTHONPATH=src python -m biocompiler circuit-verify generated/construction/cli.build.json --expected-request generated/construction/request.json
PYTHONPATH=src python -m biocompiler circuit-export generated/construction/cli.build.json --expected-request generated/construction/request.json --output generated/construction/export.json
PYTHONPATH=src python -m biocompiler inspect generated/construction/export.json
```

`circuit-export` freshly checks strict completeness and atomically publishes the
full build JSON, retaining original authority and derivations. It is not yet the
R12 multi-format archive/FASTA or guided-workspace export. Nonpassing builds are
retained for inspection and return a nonzero CLI status. A verified complete
structural record carries no synthesis, administration or human-use admission.

## Bounds and validation

Requests allow at most 64 roots, 256 steps/products, 64 covalent final members,
64 complexes and 256 required-member declarations. Source residues, cumulative
attempted output work and final member residues each have a 1,000,000-residue
ceiling. Failed materialization still consumes reserved work. Step outputs are
atomic; a failing sibling never leaves an apparently complete partial operation.
Diagnostics have bounded count and byte budgets and preserve failure severity.

Preflight ordering is part of deterministic replay: common input/path checks
precede operation checks; output alphabet/topology precede editing or translation
allocation. Translation checks path/frame/AUG and known modification inventory
before reserving work, then skipping allocation and codon/stop interpretation.
Editing reserves after source/port form checks and before modification inventory
and edit-symbol validation. Tests combine malformed inputs with exhausted budgets
to keep producer/checker behavior aligned without sharing their executor.

Validation includes independently specified artificial cases, altered candidate
and external-authority records, omitted members, feature/chemistry errors,
resource limits, producer-disabled fresh checking, Python/CLI replay and atomic
publication failures. Hosted CI installs the package and runs its construction
workflow outside the checkout on Python 3.11 and 3.14, alongside all existing
tests, audit, examples, package and browser gates. Exact-revision receipts are
recorded in the milestone PR and session handoff; the profile is provisional
until the source-backed R6 interface review.

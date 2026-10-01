# Intent-driven RNA candidates v0.1

This profile connects one authored product requirement to an exact RNA cassette
through explicit supplied parts and architecture choices. It is the first
source-driven molecular compiler path: the caller supplies no nucleotide
placements, and supported source edits change the emitted bases or yield an
explained rejection. Its completion scope is `product_cassette_structure`.
Therapeutic implementation remains `partial`, biological support is
`unestablished` and human therapeutic admission is `not_admitted`.

## Source and library authority

`CandidateRequest(source, library, constraints)` freezes all authority. `source`
is a `BuildRequest`, `HumanBehaviorRequest`, `HumanDeploymentRequest` or
`HumanAcceptanceRequest`; the original target and complete wrapped contracts are
retained. The supported graph has one role, one secretion declaration, one ongoing
secretion action and a condition rule installing that action. A declaration alone
does not request expression. Additional actions, event-triggered rules and other
unsupported source structures receive diagnostics.

Requirements extraction identifies the exact product string and retains every
source node. The guard, secretion mechanism, response rates, biological function,
goals, applicability and relevant wrapped-contract requirements remain explicit
obligations. No hypothetical sensor or conditional-control sequence is inserted.
The emitted cassette does not discharge those obligations.

The bounded library contains:

- `MolecularPart`: an identity, region kind and exact pinned RNA `SequenceFragment`.
- `ProductBinding`: a source product identity, CDS part identity and expected protein.
- `RNAArchitecture`: a versioned identity, 5′ UTR and 3′ UTR part identities,
  optional poly(A) part and explicit whole-molecule chemistry/features.

These declarations do not establish function or human applicability. The bundled
library uses short artificial, nonfunctional fragments and proteins. This release
adds no characterized biological-part catalog or external-part admission policy.
DNA conversion, sequence optimization, implicit chemistry and partial-fragment
selection are unsupported.

## Selection and automatic assembly

`CandidateConstraints` separates hard architecture/CDS allowlists and maximum
nucleotide length from the `shortest` or `lexical` preference. Empty allowlists
permit all supplied identities. Libraries are capped at 32 entries in each
inventory and 256 product-binding/architecture combinations.

Selection enumerates every supplied architecture paired with each binding for the
exact requested product. It retains all alternatives, including hard-constraint,
fragment-integrity, translation and chemistry rejection reasons. Eligible options
are ordered by `(length, architecture_id, cds_part_id)` for `shortest`, or
`(architecture_id, cds_part_id)` for `lexical`. Catalog order does not break ties.
The result is deterministic within this finite library; it makes no claim of
global biological optimality or infeasibility. Missing product bindings and an
exhausted bounded search are distinct outcomes.

The selected parts form 5′ UTR → CDS → 3′ UTR → optional poly(A). The compiler
derives each full-fragment source range and contiguous destination range, retains
the supplied fragment identity and locator, and attaches the declared protein to
the CDS. It emits the exact concatenated RNA spelling in a mature, linear,
single-stranded `PayloadMolecule`, with the selected architecture's explicit
features. Source maps distinguish product encoding from architectural support.

## Checked compilation and reuse

`bc.compile(candidate_request)` returns
`CandidateCompilation(record, manager, pipeline_result)`. The pass manager checks
source → requirements → selection → components → layout → molecule. Independent
validators reconstruct each stage against original authority without importing
the requirements lowerer, selector, layout generator or emitter. They share
normative schemas and the structural RNA checker. A correspondence PASS for an
accurately reported empty search does not mean a molecule was produced.

`CandidateBuildRecord` retains the full request, requirements, alternatives,
selected parts, layout, molecule, source maps, checks and tool/profile identities.
When no eligible option exists, the record has `no_candidate_found` status and no
molecule. When one exists, structural completion does not complete the retained
therapeutic requirements. Human targets remain unchanged; they are never relabeled
as generic software targets to obtain admission. General `bc.compile(BuildRequest)`
still raises `CompilationUnavailableError`.

For the artificial example, from the repository root:

```python
import biocompiler as bc
from examples.intent_candidate import make_candidate_request

request = make_candidate_request()
compilation = bc.compile(request)
record = compilation.record
bc.verify_candidate_build(record, expected_request=request)
fasta = bc.export_candidate_fasta(record, expected_request=request)
```

The example helper supplies fixtures; normal callers construct `CandidateRequest`
from their frozen source and explicit library. Fresh verification requires the
complete independently retained request, compares all stored checks with current
assessments and rejects changed authority or tool semantics. FASTA export performs
the same verification, wraps bases at 80 columns and labels the build identity,
structural scope, partial therapeutic implementation and absent human admission.
A FASTA sequence alone omits structured chemistry and unresolved requirements;
retain its corresponding JSON record.

## Reproducible example and CLI

```sh
python examples/intent_candidate.py --output generated/intent-candidate
biocompiler candidate-build --request generated/intent-candidate/product_a.request.json --output generated/intent-candidate/cli.build.json
biocompiler candidate-verify generated/intent-candidate/cli.build.json --expected-request generated/intent-candidate/product_a.request.json
biocompiler candidate-fasta generated/intent-candidate/cli.build.json --expected-request generated/intent-candidate/product_a.request.json
```

`candidate-build` writes a JSON record; `candidate-fasta` writes verified FASTA to
stdout. These commands do not produce `.bcb` archives. The example's product edit
selects a different CDS, its architecture constraint selects a longer 5′ fragment,
and an impossible length bound produces an empty search. A guard edit remains an
unimplemented requirement and may leave the cassette sequence unchanged, while
changing the request/build identity. Tests also mutate source correspondence,
ranking, coordinates, bases, chemistry and saved checks.

Future molecular families must add checked implementation rules for their source
obligations. Quantitative models should bind the selected parts and sequence
versions to explicit observations and response claims; neither rates nor
empirical support can be inferred from these fixtures. See the
[architecture](architecture.md), [molecular-design profile](molecular-design-v0.1.md)
and [human admission policy](human-admission-v0.1.md) for the separate boundaries.

# biocompiler

biocompiler is an experimental compiler for translating **high-level Python
therapeutic policies into exact mRNA payload specifications**. Its product target
is human immune cells engineered in vivo. A policy describes observations,
conditions, state, actions and required outcomes; supplied implementation
contracts and sequence-construction rules describe how to realize its supported
meaning.

The compiler's obligation is to preserve that meaning through operational
semantics, implementation graphs, component bindings and exact nucleotide
construction—or explain why compilation cannot proceed. A capability name,
plausible sequence or successful structural check cannot stand in for that chain.

The current focus is **internal compiler correctness under explicit supplied
contracts**. Those contracts are premises, not experimental findings. Biological
viability and therapeutic efficacy are separate questions and are outside this
phase's compiler acceptance criteria. Artifacts retain their conditional scope
and unresolved empirical status.

## Current capabilities and status

The bounded Python-policy → mRNA compiler has source implementations and hosted
development validation. **Complete release acceptance and production-wide native
cutover remain pending.** The newest public selection check/replay/export
increment still awaits hosted acceptance; selection compilation is not available.
The [semantic mRNA development plan](docs/semantic-mrna-development-plan.md) is
the maintained source of implementation, validation and release status.

| Stage | Implemented boundary |
| --- | --- |
| Python authoring | `biocompiler.policy` provides typed declarations, builders, composition patterns, immutable documents, unresolved design slots, structural diagnostics and bounded JSON serialization. |
| Operational semantics and IR | OCaml admits an explicit subset, binds versioned executable definitions, lowers to a dedicated behavior IR and independently checks correspondence with the original source. Bounded execution preserves identity, three-valued evidence, scoped state, deterministic event handling and correlated effect attempts. |
| Implementation lowering and checking | A bounded truth-policy family lowers to supplied typed primitives and connections. Independent source and candidate runtimes compare observable behavior over the complete declared finite domain; separate requirement checks retain every original obligation. |
| Material and context binding | Supplied whole-graph contracts and a separate reusable-component composition path connect implementations to sequence templates. Checks retain model identities, interfaces, recipient and timing contracts, resource capacities and payload cardinality. The current component family joins two components into one RNA member. |
| Exact construction and export | Independent checking reconstructs sequence derivation, coordinates, coding regions, chemistry and material correspondence. Fresh export publishes the exact RNA FASTA and complete manifest together. |
| Finite material selection | The new source increment checks every supplied alternative under one common policy, then applies a length predicate and deterministic ranking. A failed or omitted alternative cannot become a convenient exclusion. Public hosted acceptance is pending; metered candidate generation remains the next prerequisite for compilation. |

The authoring language is intentionally broader than the executable subset.
Coordination, quantification, complex spatial relationships and inheritance are
not executable merely because they can be declared. Operational execution also
does not imply that every supported state machine or expression has a molecular
lowering. Unsupported required meaning blocks a complete compilation claim.

Start with the [policy language](docs/policy-language-v0.1.md),
[operational semantics](docs/policy-operational-v0.1.md),
[implementation contracts](docs/policy-realization-contracts-v0.1.md),
[bounded preservation](docs/policy-bounded-preservation-v0.1.md) and
[policy-to-mRNA acceptance contract](docs/policy-material-acceptance.md).

## Meaning, checking and artifact identity

Python runs at **construction time**: loops and functions can assemble a
declarative program. They are not the program's cellular runtime. Runtime guards,
uncertainty, state transitions, timeouts and effect feedback must have explicit
semantics in the supported native profile. Definition prose does not supply an
executable interpretation.

Core produces candidates. Standalone **Verify** independently checks supported
profiles against separately supplied original inputs and does not link the
producer implementations. It reconstructs correspondence and executes the
specified checks; it does not accept a producer's success label as evidence.
Fresh replay repeats those checks under the complete current authority.

Original source, definitions, finite domains, requirements, model libraries,
component records and construction rules remain bound through the artifacts.
Exported manifests retain their identities, the checked candidate, assessment
and exact material members. Source edits, changed contracts and altered bases
must be checked again, even when the selected sequence happens to stay the same.
Keep the original inputs alongside the FASTA/manifest pair.

## Getting started

The Python package requires **Python 3.11 or newer** and has no mandatory runtime
dependencies. From a source checkout:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
biocompiler --version
biocompiler policy --help
```

Authoring and inspection work without a native executable. This small example
uses a bundled abstract authoring fixture; it does not supply a molecular
implementation or demonstrate therapeutic behavior:

```python
import biocompiler.policy as bp
from biocompiler.policy.examples import build_example

program = build_example("context_gated_response")
report = bp.check(program)
print(report.status, report.semantic_status)
bp.dump(program, "example.policy.json")
```

```sh
biocompiler policy check example.policy.json
biocompiler policy inspect example.policy.json
```

Without installing, the equivalent CLI starts with
`PYTHONPATH=src python3 -m biocompiler policy`.

Native operations require an explicitly selected compatible Core or Verify
executable. Installing the Python package alone does not establish native
availability or select a backend. For a **complete supplied whole-graph material
request** and its matching preservation limits, the existing CLI separates
candidate production from fresh checked export:

```sh
biocompiler policy compile-material-native material-request.json \
  --core /path/to/biocompiler-core --limits preservation-limits.json \
  --output candidate.json

biocompiler policy export-material-native material-request.json \
  --verify /path/to/biocompiler-verify --limits preservation-limits.json \
  --candidate candidate.json --output program.zip
```

These filenames represent supplied inputs, not files created by the authoring
example. See the [material workflow](docs/policy-material-acceptance.md) for their
complete authority and resource requirements. Component composition uses the
dedicated Python `policy.component_material` API; selection has its own
check/replay/export API. Neither is an implicit conversion from an arbitrary
authored policy.

## Existing workflows and remaining scope

The earlier [RNA architecture compiler](docs/payload-architecture-v0.1.md) and
[per-operator payload profile](docs/executable-rna-payload-v0.1.md) remain separate
workflows over the legacy Behavior representations. They support their own
supplied contracts, RNA partitions, controls and deployment assumptions. Their
capabilities do not automatically extend the rich-policy language, and the new
policy IR does not silently reinterpret legacy requests.

[Reference builds and packages](docs/reference-build-v0.1.md) reproduce retained
sequence authority and support independent artifact review. The native
reference-package route has source implementations; completing compatibility and
hosted acceptance remains part of the migration.
Supporting DNA/reference utilities do not add another therapeutic product target.

Next work follows the [development plan](docs/semantic-mrna-development-plan.md):
finish release acceptance, meter selection candidate generation, close remaining
semantic and public API coverage, and extend complete profiles for additional
state-machine lowering, helpers and multiple RNA members. **Rich-policy Studio
and conversational authoring are deferred.** Existing Studio workflows belong to
their documented legacy profiles.

## Repository and development

| Path | Contents |
| --- | --- |
| [`src/biocompiler/policy/`](src/biocompiler/policy/) | Declarative authoring, serialization, inspection and native workflow adapters. |
| [`core/`](core/) | OCaml representations, operational semantics, producers, independent checkers, services and native tests. |
| [`src/biocompiler/`](src/biocompiler/) | Python SDK, explicit native transports and existing compiler workflows. |
| [`protocol/`](protocol/) | Versioned wire formats, schemas and checked source/coverage inventories. |
| [`examples/`](examples/README.md) | Runnable examples with explicit profile and evidence boundaries. |
| [`tests/`](tests/README.md) | Python, regression, mutation and integration checks. |
| [`docs/`](docs/) | Semantic contracts, architecture, migration and acceptance plans. |

Follow [development validation](docs/development-validation.md). Keep editing and
focused static/Python checks local; run native compilation, executable tests and
packaging on hosted CI. A source checkpoint or development run does not replace
the complete release and fresh-main gates. The
[migration roadmap](docs/language-migration-roadmap.md) tracks native routing and
distribution separately from the supported semantics.

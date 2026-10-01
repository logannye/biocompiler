# biocompiler

biocompiler translates **therapeutic program design into corresponding RNA payload specifications for human immune cells engineered in vivo**. Exact sequences come from supplied component templates and assembly rules.

This is its **only product target**. Human-cell studies provide supporting
reference benchmarks; they do not create a general cell-culture or non-human
compiler product. Source-experiment context and component origin remain distinct
from the intended human immune-cell deployment and its evidence requirements.

An engineer should be able to describe which cells to engineer, what those cells should recognize, how they should respond, and which outcomes they must avoid. The compiler should turn those requirements into explicit molecular implementation choices and exact nucleotide sequences, accompanied by molecular features, deployment assumptions, source maps and evidence. Python is the current authoring language; natural-language authoring is part of the longer-term vision.

The central idea is to keep three things connected: **what a cell should do**, **how a proposed implementation is described**, and **what experimental evidence supports**. Typed descriptions and independent checks make those relationships inspectable throughout a design.

The current [RNA architecture compiler](docs/payload-architecture-v0.1.md), in
`0.1.0.dev28`, connects full source behavior to supplied composite implementations,
RNA partitions, recipient assignments and exact complete molecule sets. Behavior,
components, RNAs and cell roles have explicit many-to-many correspondence. It
supports finite state, temporal control, quantitative rate branches, sampled
activity budgets and coupled roles under declared transport contracts. Independent
checks establish translation under those contracts; biological function remains
a separate empirical question. The earlier
[per-operator payload profile](docs/executable-rna-payload-v0.1.md) remains available.

## What works today

| Workflow | What it provides |
| --- | --- |
| Select a complete RNA architecture | `bc.compile(PayloadArchitectureRequest(...))` selects supplied composite behavior contracts and RNA partitions, checks control independence, helpers, recipient delivery and channels, and emits freshly verified RNA plus a complete manifest. |
| Compile a contract-based RNA program | `bc.compile(PayloadCompilationRequest(...))` preserves source semantics, selects and connects supplied executable contracts, constructs every required RNA member, and independently checks source/component/sequence correspondence. |
| Author intent and context | Typed Python descriptions of recognition, actions, timing and goals, with frozen human target, behavior, deployment and prohibited-outcome contracts. |
| Check circuit scope | Human immune-recipient declarations bound to the exact target, separate human study context, and fresh checking against retained request authority; scope checking alone supplies no molecular implementation. |
| Start in a guided workspace | A local browser GUI explains the example, lets you choose product and architecture constraints, and runs the real compiler with verified downloads. |
| Analyze implementation requirements | Retain the complete source and human contracts, classify sensing, control, product, timing and deployment obligations, and identify missing refinements or contradictions. |
| Compile a declared precursor implementation | `bc.compile(ImplementationRequest(...))` selects a supplied signal-prefix/product architecture, checks declared host dependencies and processing relationships, derives a composite CDS and emits exact RNA with base-level correspondence. |
| Compile an RNA cassette candidate | `bc.compile(CandidateRequest(...))` selects supplied product-coding parts and an architecture, derives the layout, and emits independently checked exact bases. |
| Explain and reproduce a build | Retained source requirements, alternatives, rejection reasons, part identities, molecular features and checks; JSON records and verified FASTA under independent request authority. |
| Check abstract behavior | Bounded digital models, temporal execution, component linking, supplied-trace checks and reproducible failure analysis. |
| Check molecular structure and references | Exact DNA/RNA coding-sequence reproduction, multi-region RNA construction and structural molecule checks, with separate reference/design packages. |
| Inspect circuit authority and retained artifacts | Strict source metadata imports, nominal requirement/role bindings, stale evidence detection, and read-only construction inspection with lossless JSON save/reopen. |
| Check supplied molecule-set construction | Explicit bounded transformations from retained roots, independent coordinate/chemistry replay, required-member and payload-region checks, and strict structural JSON export. |

The [molecular implementation compiler](docs/molecular-implementation-v0.1.md) connects intent to declared precursor structure. Its first family handles one conditionally requested secreted product using a finite, caller-supplied library. It retains the source guard as unresolved while checking the declared precursor, mature product, processing boundary, host dependencies and RNA structure. Changing a product or architecture constraint changes the sequence or produces an explained rejection. The compiler derives all nucleotide coordinates and independently verifies the proposed artifacts against the original request.

Its bundled examples use **artificial, nonfunctional fragments and protein strings**. A caller can also supply exact sequence authorities with declared provenance; those records do not establish physical processing, secretion or therapeutic behavior. A structural result retains all unresolved functional obligations. Setting `require_implementation_complete=True` withholds molecular output under the current family. General therapeutic compilation from a `BuildRequest` still raises `CompilationUnavailableError`.

The GUI continues to use the earlier [intent-candidate profile](docs/intent-candidate-v0.1.md). The new precursor workflow is available through Python and the CLI, ready for later GUI integration.

## What remains to build

The [human circuit profile](docs/human-circuit-profile-v0.1.md) implements R0 of
the [RNA-circuit plan](docs/rna-circuit-reproduction-plan.md). Its Python and CLI
checks establish declared scope and preserve independent evidence dimensions.
The [R2 circuit intent API](docs/circuit-intent-v0.1.md) adds nominal observations,
composable Boolean tables, explicit products/lifecycles/providers and complete
reference locks alongside the original human request. Independent checking
retains every source obligation. Neither layer reconstructs a published circuit
or emits a circuit payload. The [R3 molecular declaration layer](docs/circuit-molecules-v0.1.md)
represents named molecule sets, exact coordinate frames, overlapping annotations,
chemistry and uncertainty without promoting them to checked assembly or biology.
The [R4 construction workflow](docs/circuit-construction-v0.1.md) now constructs
and independently checks explicit supplied operations and complete nominal sets.
It preserves the original human request but does not derive a molecular mechanism
from its truth table. Published-source curation, family correspondence and human
admission remain open; its examples are artificial software controls.

The [circuit authority infrastructure](docs/circuit-infrastructure-v0.1.md) adds bounded support for R1/R5/R11/R12/R13. Software implementation, reviewed reference correspondence and human biological applicability are tracked separately. Actual family semantics and the first admissible R6a case remain open.

[Portable review bundles](docs/circuit-review-bundles-v0.1.md) retain existing construction, source metadata, nominal binding and evidence records for offline replay against separately supplied authority. Studio's saved-construction view shows source gaps, binding diagnostics and evidence freshness. These software checks do not establish a biological mechanism, reviewed publication fidelity or human applicability.

The next compiler capabilities extend the supplied-contract path to additional implementation families, mapped resource/operating-domain contracts and broader quantitative models. Finite-state behavior, typed rate expressions, sampled integral budgets and explicitly coupled roles already connect to selected RNA architectures. Quantitative models and observation mappings should evaluate those selected implementations under explicit assumptions. Translation correctness and exact RNA construction can be checked without biological evidence. Establishing therapeutic function and deployment compatibility requires independently supported human biology; those empirical claims remain open and are not established by the software fixtures.

The [roadmap](docs/roadmap.md) tracks that path. biocompiler keeps exact artifact identity, structural consistency, model-conditional behavior and experimental evidence separate. A passing check applies only to its stated scope and dependencies. Physical manufacture, administration and clinical authorization remain external activities; their constraints must inform the eventual compiler.

See the [human target contract](docs/human-target-contract-v0.1.md) and
[human admission policy](docs/human-admission-v0.1.md) for the current evidence and
use boundaries.

## Quick start

Requires **Python 3.11 or newer** and has no runtime dependencies. From a source checkout, in a POSIX shell:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
biocompiler --version
biocompiler studio
```

You can also run directly from the repository without installing:

```sh
PYTHONPATH=src python3 -m biocompiler studio
```

The [guided workspace](docs/studio-v0.1.md) opens locally in your browser. Start
with its artificial example, compile a candidate, inspect the selected parts and
download verified results. You can also import an existing candidate request.
Keep the terminal running; press Ctrl+C to stop the workspace. Use `--port 0` if
the default port is occupied, or `--no-open` to print the URL without opening it.

### Describe an intended response in Python

```python
import biocompiler as bc

therapy = bc.Therapy("contextual_response")
cells = therapy.engineer("responders", cell_type="T_cell")
recognized = cells.contact.marker("A").high()
context = cells.environment.signal("disease_context").present()
cells.when(recognized & context).do(cells.eliminate(cells.contact))

program = therapy.freeze()
print(program.summary())
```

This builds an inspectable program description. Names such as `A` and `disease_context` are symbolic requirements; Python does not execute the cellular response. See the [intent API](docs/intent-api-v0.1.md) for the authoring vocabulary.

### Compile a complete supplied RNA architecture

```sh
PYTHONPATH=src python3 -m examples.payload_architectures --case all --output generated/architectures
PYTHONPATH=src python3 -m biocompiler architecture-verify generated/architectures/a/build.json --expected-request generated/architectures/a/request.json
PYTHONPATH=src python3 -m biocompiler architecture-export generated/architectures/a/build.json --expected-request generated/architectures/a/request.json --output generated/architectures/a/export.json
```

The six artificial examples cover shared activation and independent shutdown,
state/reset/timeout, clamped rate branches with sampled budgets, coupled roles,
alternative RNA partitions and their combination. The example writes paired RNA
FASTA and manifest files. CLI export returns both in one JSON artifact; keep the
independent request as verification authority. See the
[architecture profile](docs/payload-architecture-v0.1.md) for supported bounds and
Python APIs. Production shutdown does not imply effector inactivation, and
sampled budget checks do not imply a continuous physiological ceiling.

### Compile a declared molecular implementation

This example retains a complete human source request, selects between two artificial precursor architectures and demonstrates rejected strict, size-limited and missing-provider cases:

```sh
python examples/molecular_implementation.py --output generated/molecular-implementation
biocompiler implementation-analyze --request generated/molecular-implementation/source.json --output generated/molecular-implementation/analysis.json
biocompiler implementation-build --request generated/molecular-implementation/compact.request.json --output generated/molecular-implementation/cli.build.json
biocompiler implementation-verify generated/molecular-implementation/cli.build.json --expected-request generated/molecular-implementation/compact.request.json
biocompiler implementation-fasta generated/molecular-implementation/cli.build.json --expected-request generated/molecular-implementation/compact.request.json
```

The build retains typed requirements, every bounded alternative, the selected plan and sequence authorities, derived coding/processing coordinates, molecular features and independent checks. FASTA export rechecks the complete build against the separately retained request. The [implementation guide](docs/molecular-implementation-v0.1.md) explains how to supply a library and interpret the result.

### Use the earlier product-cassette profile

The integrated example supplies two artificial products and two explicit architectures, preserving its human source request and all unresolved behavior:

```sh
python examples/intent_candidate.py --output generated/intent-candidate
biocompiler candidate-build --request generated/intent-candidate/product_a.request.json --output generated/intent-candidate/cli.build.json
biocompiler candidate-verify generated/intent-candidate/cli.build.json --expected-request generated/intent-candidate/product_a.request.json
biocompiler candidate-fasta generated/intent-candidate/cli.build.json --expected-request generated/intent-candidate/product_a.request.json
```

The JSON build record contains the frozen request, alternatives, selected parts, derived layout, molecule and independent checks. FASTA export rechecks the record against the separately retained request and labels its structural scope, partial therapeutic implementation and absent human admission. See the [candidate profile](docs/intent-candidate-v0.1.md) for the supported source subset and Python API.

### Explore the supporting workflows

The [example guide](examples/README.md) provides runnable commands and explains each workflow's evidence boundaries.

| Example | Purpose |
| --- | --- |
| [RNA architecture designs](examples/payload_architectures.py) | Compile and export A–F supplied-contract examples with independently authored models, exact RNA partitions, helpers and recipient/channel assignments. |
| [Synthetic design loop](examples/synthetic_design.py) | Select a bounded digital implementation, reconstruct its component assembly and check supplied histories. See [selection](docs/synthetic-selection-v0.1.md) and [verification](docs/synthetic-verification-v0.1.md). |
| [Molecular design](examples/molecular_design.py) | Assemble supplied RNA fragments under explicit layout authority and independently check a complete structural specification. See the [design profile](docs/molecular-design-v0.1.md). |
| [Reference builds](examples/reference_build.py) | Reproduce independently pinned DNA/RNA coding sequences and verify portable `.bcb` packages. See [reference-build commands](docs/reference-build-v0.1.md). |
| [Human profile cases](examples/human_profile_cases.py) | Inspect required/prohibited observations, deployment assumptions and admission refusal separately. See the [proposed human profile](docs/human-profile-v0.1.md). |

A **coding sequence (CDS)** is the protein-coding portion of a construct. The bundled murine FAP-CAR reference supports exact CDS reproduction as a software regression; it does not establish a complete delivered molecule or an admitted human therapy. The digital and molecular examples test distinct compiler obligations and do not establish biological behavior.

## Repository guide

| Path | Contents |
| --- | --- |
| [`src/biocompiler/`](src/biocompiler/) | Authoring, intermediate representations, compiler passes, models, independent checkers, registries, DNA/RNA backends, and artifact packaging. |
| [`examples/`](examples/README.md) | Runnable workflows and explanations of their scope. |
| [`data/references/`](data/references/) | Small curated coding-sequence references with retained source and review records. |
| [`tests/`](tests/README.md) | Unit, semantic, mutation, and integration tests. |
| [`docs/`](docs/) | Architecture, semantic profiles, evidence requirements, and design decisions. |

To run the test suite from the repository root:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Hosted CI checks package installation, tests, examples, and the CLI on Python 3.11 and 3.14. These checks validate software behavior within the documented profiles; biological performance requires separate evidence.

For deeper reading, start with the [architecture](docs/architecture.md), [behavior semantics](docs/behavior-semantics-v0.1.md), [molecular contracts](docs/molecular-behavior-v0.1.md), and [payload profiles](docs/payload-profiles-v0.1.md). Contributors should also read [AGENTS.md](AGENTS.md).

This release uses the `biocompiler` package, CLI and artifact namespace. See the
[rename and artifact migration notes](docs/biocompiler-migration.md) before reusing historical builds.

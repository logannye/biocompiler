# biocompiler

biocompiler is an experimental Python compiler toolkit for describing engineered immune-cell behavior and producing inspectable DNA/RNA reference artifacts. It is intended for cell engineers, synthetic biologists, computational biologists, and scientific software developers who need to connect design requirements with explicit assumptions, checks, and evidence.

The central idea is to keep three things connected: **what a cell should do**, **how a proposed implementation is described**, and **what the supporting evidence establishes**. Typed descriptions and independent checks make those relationships inspectable throughout a design.

This release uses the `biocompiler` package, CLI and artifact namespace. See the
[rename and artifact migration notes](docs/biocompiler-migration.md) before reusing historical builds.

## What you can do

| Workflow | What it provides |
| --- | --- |
| Describe cellular intent | Python authoring for recognition, actions, timing, memory, states, and communication, saved as immutable typed graphs. |
| Declare a human target | Explicit cell/state, tissue/disease, population, host dependencies, operating conditions and evidence gaps, preserved in frozen build requests. |
| Specify conditional secretion | Source-linked physical readouts, explicit thresholds, rate ranges and lifecycle deadlines, with bounded checks of supplied traces and separate cellular/evaluator observations. |
| Check required and prohibited observations | One acceptance authority for source responses, healthy-context inactivity, background/peak limits, response duration, input-access loss and external shutdown assumptions. |
| Freeze deployment requirements | Pinned delivery specification, recipient and exposure assumptions, distinct expression/behavior clocks, and explicit unsupported co-payload obligations. |
| Evaluate and check abstract behavior | Execution against supplied observation histories, a limited automatic synthetic candidate generator, and independent checks with counterexamples and explicit coverage. |
| Compare digital implementations | Two bounded conjunction strategies, authored operator/gate constraints, independent candidate checks, deterministic ranking and retained rejection reasons. |
| Stress-check and replay a design | JSON-driven checks, mixed cell/contact exploration and selected-failure reduction with exact bounds, explicit unknowns and independent replay authority. |
| Inspect proposed profile cases | Positive, negative, conflicting, underspecified and unsupported requests, with separate admission and bounded-search outcomes. |
| Enforce human-profile admission | Fresh gates at planning, selection, verification and export; existing artifacts are software-only and no human therapeutic profile is admitted. |
| Link and execute digital components | Versioned stateless/temporal contracts, explicit events and values, actual assembly reconstruction, checked providers/resources and independent behavior checks. |
| Reproduce a reference coding sequence | Checked single-CDS assembly, exact DNA or RNA emission, sequence/translation checks, and reproducible offline build packages. |
| Assemble a structural RNA design | Explicit sequence fragments and layout, independent generated-candidate checks, complete structured specification and reproducible packages under a software-only profile. |
| Record molecular correspondence | Contracts connecting requested observations and responses to selected CDS components, with separate parameter, context, and evidence records. |
| Check a supplied molecule specification | Structural profiles for mature linear RNA, linear DNA, and circular plasmids, checked against independently pinned references and retained source/review records. |

A **coding sequence (CDS)** is the protein-coding portion of a genetic construct. The bundled FAP-CAR reference supports exact CDS reproduction. Its record does not establish the complete delivered molecule.

## Understanding the results

biocompiler keeps exact sequence identity, structural consistency, model-conditional behavior, and empirical biological evidence separate. A passing check applies to its stated scope, assumptions, dependencies, and observation history. Changed inputs can invalidate an earlier result; saved reports retain their history but require fresh checks before reuse.

The authoring language is broader than the executable profiles. Unsupported behavior produces explicit diagnostics. General intent-to-molecular compilation through `bc.compile(...)` is unavailable; exact CDS builds use a separate, independently pinned reference workflow. Calibrated biological simulation and complete therapeutic-payload generation are outside the supported workflows.

Molecular correspondence checks can establish source/CDS linkage while leaving biological behavior `UNKNOWN`. Whole-molecule structural checks do not establish functional performance or authorize a human payload build. A separate software molecular-design profile assembles explicit fragments into one complete structural RNA specification. Its examples use artificial, nonfunctional fixtures; source-to-biological implementation and human admission remain unestablished.

The [human target contract](docs/human-target-contract-v0.1.md) fixes human in-vivo
recipient scope while preserving explicit unresolved applicability. It records
requirements and evidence citations; it does not validate a human biological
implementation or admit a therapeutic payload.

The [human admission policy](docs/human-admission-v0.1.md) enforces this boundary
through selection and export. Reference and synthetic artifacts carry fixed
software-use labels. Release `0.1.0.dev12` changes affected artifact identities;
rebuild from independent authority instead of relabeling an old PASS.

## Quick start

Requires **Python 3.11 or newer** and has no runtime dependencies. From a source checkout, in a POSIX shell:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
biocompiler --version
python examples/intent_programs.py
```

You can also run directly from the repository without installing:

```sh
PYTHONPATH=src python3 -m biocompiler --version
PYTHONPATH=src python3 examples/intent_programs.py
```

### Describe an intended response

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

### Explore checks and artifacts

With the package installed, run:

```sh
python examples/behavior_trace.py
python examples/checked_pipeline.py
python examples/temporal_pipeline.py
python examples/synthetic_build.py --output generated/synthetic
python examples/molecular_contract.py
python examples/payload_readiness.py
```

These examples cover abstract execution, independent combinational/temporal synthetic checks, reproducible workflow packages, molecular correspondence, and whole-molecule structural checks. The [example guide](examples/README.md) explains each example and its evidence boundaries. The [temporal profile](docs/synthetic-temporal-v0.1.md) supports sustained conditions, pulses and resettable memory; [synthetic packages](docs/synthetic-build-v0.1.md) provide offline build/verify commands without molecular or human-admission claims.

For the integrated offline design loop:

```sh
python examples/synthetic_design.py --output generated/design
biocompiler synthetic-select --request generated/design/request.json
biocompiler synthetic-verify generated/design/design.bcb --expected-request generated/design/request.json
biocompiler synthetic-explore --request generated/design/campaign-request.json --output generated/design/rechecked.json
biocompiler synthetic-replay generated/design/rechecked.json --expected-request generated/design/campaign-request.json
```

This selects an implementation under a frozen operator constraint, packages its
checked component assembly and explores 100 declared mixed-input histories.
[Selection](docs/synthetic-selection-v0.1.md), [temporal composition](docs/temporal-components-v0.1.md)
and [verification](docs/synthetic-verification-v0.1.md) preserve the requirements,
implementation choices and evidence boundaries needed by future molecular profiles.
They use software fixtures and require no outside data or laboratory access.

For checked multi-region molecular construction:

```sh
python examples/molecular_design.py --output generated/molecular-design
biocompiler molecular-design-build --request generated/molecular-design/request.json --output generated/molecular-design/cli.bcb
biocompiler molecular-design-inspect generated/molecular-design/cli.bcb
biocompiler molecular-design-verify generated/molecular-design/cli.bcb --expected-request generated/molecular-design/request.json
```

The [molecular-design workflow](docs/molecular-design-v0.1.md) independently checks
every emitted region against frozen fragment/layout authority and retains chemistry,
provenance and a nominal-design handoff. The example shows an authorized alternate
design and rejection of an unauthorized synonymous edit. Structural completion
supplies no biological function, experimental-material identity or clinical authority.

To build and inspect a package containing the bundled RNA-CDS reference:

```sh
mkdir -p generated
biocompiler reference-build --alphabet RNA \
  --reference-dir data/references/fap_car --output generated/fap-rna.bcb
biocompiler reference-inspect generated/fap-rna.bcb
```

The `.bcb` package retains the exact sequence, frozen inputs, checks, and unresolved obligations. Choose `--alphabet DNA` for the separately pinned DNA reference. [Reference-build documentation](docs/reference-build-v0.1.md) explains fresh offline verification using independently retained authority. `biocompiler inspect artifact.json` inspects supported JSON artifacts without executing authoring code.

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

The [proposed human profile](docs/human-profile-v0.1.md) documents the first
conditional-secretion scope and its unresolved biological choices. Run
`python examples/human_profile_cases.py --output generated/profile-cases` to
retain the ten request cases, then use `--verify generated/profile-cases` to
recompute them from current example authority. Every case remains unavailable
for human payload compilation.

For deeper reading, start with the [architecture](docs/architecture.md), [behavior semantics](docs/behavior-semantics-v0.1.md), [molecular contracts](docs/molecular-behavior-v0.1.md), and [payload profiles](docs/payload-profiles-v0.1.md). Contributors should also read [AGENTS.md](AGENTS.md).

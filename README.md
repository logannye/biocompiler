# CellWeave

CellWeave is an experimental Python compiler toolkit for describing engineered immune-cell behavior and producing inspectable DNA/RNA reference artifacts. It is intended for cell engineers, synthetic biologists, computational biologists, and scientific software developers who need to connect design requirements with explicit assumptions, checks, and evidence.

The central idea is to keep three things connected: **what a cell should do**, **how a proposed implementation is described**, and **what the supporting evidence establishes**. Typed descriptions and independent checks make those relationships inspectable throughout a design.

## What you can do

| Workflow | What it provides |
| --- | --- |
| Describe cellular intent | Python authoring for recognition, actions, timing, memory, states, and communication, saved as immutable typed graphs. |
| Declare a human target | Explicit cell/state, tissue/disease, population, host dependencies, operating conditions and evidence gaps, preserved in frozen build requests. |
| Specify conditional secretion | Source-linked physical readouts, explicit thresholds, rate ranges and lifecycle deadlines, with bounded checks of supplied traces and separate cellular/evaluator observations. |
| Evaluate and check abstract behavior | Execution against supplied observation histories, a limited automatic synthetic candidate generator, and independent checks with counterexamples and explicit coverage. |
| Link components | Versioned component contracts with checked interfaces, operating assumptions, providers, resources, and dependency identities. |
| Reproduce a reference coding sequence | Checked single-CDS assembly, exact DNA or RNA emission, sequence/translation checks, and reproducible offline build packages. |
| Record molecular correspondence | Contracts connecting requested observations and responses to selected CDS components, with separate parameter, context, and evidence records. |
| Check a supplied molecule specification | Structural profiles for mature linear RNA, linear DNA, and circular plasmids, checked against independently pinned references and retained source/review records. |

A **coding sequence (CDS)** is the protein-coding portion of a genetic construct. The bundled FAP-CAR reference supports exact CDS reproduction. Its record does not establish the complete delivered molecule.

## Understanding the results

CellWeave keeps exact sequence identity, structural consistency, model-conditional behavior, and empirical biological evidence separate. A passing check applies to its stated scope, assumptions, dependencies, and observation history. Changed inputs can invalidate an earlier result; saved reports retain their history but require fresh checks before reuse.

The authoring language is broader than the executable profiles. Unsupported behavior produces explicit diagnostics. General intent-to-molecular compilation through `cw.compile(...)` is unavailable; exact CDS builds use a separate, independently pinned reference workflow. Calibrated biological simulation and complete therapeutic-payload generation are outside the supported workflows.

Molecular correspondence checks can establish source/CDS linkage while leaving biological behavior `UNKNOWN`. Whole-molecule structural checks do not establish functional performance or authorize a complete-payload compiler build. Their included examples use explicitly artificial software fixtures.

The [human target contract](docs/human-target-contract-v0.1.md) fixes human in-vivo
recipient scope while preserving explicit unresolved applicability. It records
requirements and evidence citations; it does not validate a human biological
implementation or admit a therapeutic payload.

## Quick start

Requires **Python 3.11 or newer** and has no runtime dependencies. From a source checkout, in a POSIX shell:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
cellweave --version
python examples/intent_programs.py
```

You can also run directly from the repository without installing:

```sh
PYTHONPATH=src python3 -m cellweave --version
PYTHONPATH=src python3 examples/intent_programs.py
```

### Describe an intended response

```python
import cellweave as cw

therapy = cw.Therapy("contextual_response")
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
python examples/molecular_contract.py
python examples/payload_readiness.py
```

These examples cover abstract execution, independent synthetic checks, molecular correspondence, and whole-molecule structural checks. The [example guide](examples/README.md) explains each example and its evidence boundaries.

To build and inspect a package containing the bundled RNA-CDS reference:

```sh
mkdir -p generated
cellweave reference-build --alphabet RNA \
  --reference-dir data/references/fap_car --output generated/fap-rna.cwb
cellweave reference-inspect generated/fap-rna.cwb
```

The `.cwb` package retains the exact sequence, frozen inputs, checks, and unresolved obligations. Choose `--alphabet DNA` for the separately pinned DNA reference. [Reference-build documentation](docs/reference-build-v0.1.md) explains fresh offline verification using independently retained authority. `cellweave inspect artifact.json` inspects supported JSON artifacts without executing authoring code.

## Repository guide

| Path | Contents |
| --- | --- |
| [`src/cellweave/`](src/cellweave/) | Authoring, intermediate representations, compiler passes, models, independent checkers, registries, DNA/RNA backends, and artifact packaging. |
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

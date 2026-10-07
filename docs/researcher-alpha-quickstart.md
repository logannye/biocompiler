# Researcher alpha quickstart

This workflow freezes complete caller-supplied contracts, compiles them with
Core, independently checks them with Verify, and publishes the exact
`program.fasta` / `manifest.json` pair. It supports the existing bounded
component-material and component-selection request profiles. It does not infer
missing parts, implementation mechanisms, provider contracts or biological
validity from a sequence or project description.

**Release status:** the researcher facade and standalone examples are an
integration candidate. This guide is not evidence that matching packages are
publicly available or that installed validation has passed. Distribution needs
the accepted SDK/native wheel pair for the exact validated revision and platform,
plus the example and input files below. Current release and real-project
qualification gates remain separate.

The included examples are artificial engineering references. Their 17-base and
18-base RNAs do not represent functional reporters or immune-cell therapies.
See [reference qualification](researcher-alpha-reference-qualification.md) for
their exact scope and the remaining real researcher project requirements.

## Installation and independent workspace

The alpha handoff must supply:

- Matching `biocompiler` and `biocompiler-core` wheels from the accepted hosted
  build, with revision, platform and digest records. The native wheel contains
  both Core and Verify.
- The standalone [`researcher_alpha.py`](../examples/researcher_alpha.py) and
  [`author_staged_research_project.py`](../examples/author_staged_research_project.py) scripts.
- The complete [`data/researcher_alpha`](../data/researcher_alpha/) directory,
  including its pinned originals, expected values and qualification record.
- The installed receipt at `evidence/researcher-alpha.json` and its complete
  `evidence/researcher-alpha/` directory: 30 observation sidecars, three original
  projects, three verified bundles and four declared mutation bundles. Receipt
  paths resolve relative to the `evidence` directory; the negative-control
  diagnostics are retained alongside the positive results.

The candidate starter contains 58 copied files and a separate manifest. Each
file is pinned to the already checked comparison and inputs. Its manifest still
marks overall and actual-main release acceptance as pending; copying the
evidence does not establish a later release gate.

Do not substitute a package from an unverified name on a public index. After
receiving the accepted wheels, install their exact files into a clean Python
environment. `SDK_WHEEL` and `CORE_WHEEL` below mean the absolute paths supplied
with that handoff:

```sh
python3 -m venv /absolute/path/to/alpha-environment
/absolute/path/to/alpha-environment/bin/python -m pip install \
  --no-index --no-deps --only-binary=:all: "$SDK_WHEEL" "$CORE_WHEEL"
```

The intended validated matrix is Python 3.11 and 3.14 on Linux x86_64 with glibc
2.39 or newer, and macOS 14 or newer on arm64. Only platforms with a completed
exact-release receipt should be offered.
No native compiler or editable source install is required for researchers.
Contributors keep native compilation and execution on hosted CI according to the
workspace development instructions.

Place both scripts and a directory named `corpus` containing the supplied input
files in a new working directory **outside the repository checkout**. Use the
installed environment's Python as `python` below, with no `PYTHONPATH` pointing
at a checkout. The scripts read only the files you name and import the installed
public SDK. They do not import `tools/` or retrieve test fixtures at runtime.

## Prepare and inspect a project

Run from that independent working directory:

```sh
python researcher_alpha.py prepare \
  corpus/staged-input.json staged.project.json \
  --project-id alpha.staged.software \
  --title "Artificial staged engineering reference" \
  --version 1 \
  --reuse-terms "Project-authored artificial declarations; see corpus/provenance.json"

python researcher_alpha.py preflight staged.project.json
```

Preparation requires exactly `request` and `limits` in the original JSON. It
preserves both completely, records the original file's SHA-256 and your explicit
source metadata, and writes an immutable project description. Missing request
authority, duplicate JSON keys, unsupported request shapes and unsafe input or
output aliases are rejected. Existing project files are preserved.

Preflight reports `structurally_ready`, `native_status: not_run`,
`biological_status: unassessed` and `provenance_status: caller_declared` when the
transport structure is complete. This is **not native semantic acceptance** or
authentication of a cited publication. Source locators are recorded without
being followed or executed.

## Author a staged policy in Python

The second script constructs the source through the public typed DSL: two
separate effect attempts, explicit initiation requirements, lifecycle feedback,
and encounter-scoped ordering for the same abstract product. It retains the
reference project's complete implementation and material contracts unchanged.

```sh
python author_staged_research_project.py staged.project.json authored.project.json
python researcher_alpha.py preflight authored.project.json
python researcher_alpha.py compile authored.project.json authored.payload.zip
python researcher_alpha.py verify authored.project.json authored.payload.zip
```

Preparation is pure Python and reports native checking as `not_run`. Edit
`build_request()` in the authoring script to express a different policy. The
saved project carries that complete new source and source-map coordinates;
compilation must assess it afresh against the independently supplied contracts.
Changed requirements or catalog identities cannot silently rewrite those
contracts to make the new program acceptable. A completion requirement without
sufficient feedback or an unauthorized catalog version must not publish a
payload. The hosted checks exercise these rejection cases; a saved project or
preflight result alone does not demonstrate that they passed for a release.

The reusable `ComponentMaterialInputs` package separates a typed `BuildRequest`
from all supplied nonsource authority. It can be extracted through
`reference.component_inputs`, loaded with `ComponentMaterialInputs.load`, or
frozen with `ComponentMaterialInputs.from_data`, then passed to
`ResearchProject.from_build_request`. It preserves definitions, operating
domain, implementation models and bindings, component library, composition
rule, material/context bindings, and every budget. It never invents missing
contracts, repairs their pins, or infers a mechanism from sequence. Loaded
original inputs remain protected from accidental overwrite. Selection projects
retain the existing complete-request path; extracting only one alternative's
component inputs is explicitly rejected.

This authoring example still uses the artificial same-product staged case.
It does not supply components for arbitrary stage-specific therapeutic products.
The intended source meaning, the selected profile's support, and the physical
validity of its supplied contracts remain separate questions.

## Compile and independently verify

With the matching installed native package available:

```sh
python researcher_alpha.py compile staged.project.json staged.payload.zip
python researcher_alpha.py verify staged.project.json staged.payload.zip
```

The default resolver checks the owned installed SDK/native pairing and selects
the required executable roles. Compilation uses Core generation followed by
fresh Verify export. A failed or unsupported native result cannot produce an
accepted publication. The output contains exactly:

- `program.fasta`: canonical RNA spelling.
- `manifest.json`: the candidate, full request and limits, nominal molecule
  annotations, supplied contracts and verification records.

Keep the independently retained `staged.project.json` beside your original
input and provenance. Verification requires that current independent project;
the request or PASS labels embedded in an untrusted bundle cannot authorize
themselves. It checks the candidate afresh with Verify and compares the exact
returned FASTA and manifest bytes with the bundle. Verify has no producer role.

The example refuses to overwrite existing output files. Use a new output name
for a revised project. The Python API has an explicit replacement option when
replacement is intended; failed validation must preserve the old destination.

If Core returns a nonaccepted assessment, the command exits with status 1 and
prints a JSON object to standard error containing the full `report`, its
`status`, `artifact: absent` and `biological_status: unassessed`. Inspect the
report's failed or unsupported stages, requirements and diagnostics; the
workflow does not reduce a semantic failure to a missing output file. In Python,
catch `ResearchProjectRejected` and inspect its immutable `compiled` result or
detached `report` property. Input and transport errors also exit with status 1,
with their error message on standard error.

For a development or externally supplied executable pair, the example also
accepts explicit **absolute** paths and independently obtained exact digests:

```sh
python researcher_alpha.py compile staged.project.json staged.payload.zip \
  --core "$CORE_EXECUTABLE" --core-sha256 "$CORE_SHA256" \
  --verify "$VERIFY_EXECUTABLE" --verify-sha256 "$VERIFY_SHA256"
```

These variables are supplied release authority, not hashes extracted from the
candidate being verified. Missing path/digest pairs are rejected. The ordinary
researcher workflow should use the owned installed resolver.

## Use the public Python API

The same workflow can be called directly without the standalone script:

```python
import hashlib
from pathlib import Path

from biocompiler.core_client import decode_json
from biocompiler.policy.research_project import ResearchProject, SourceRecord

input_path = Path("corpus/staged-input.json")
raw = input_path.read_bytes()
original = decode_json(raw)
project = ResearchProject.from_request(
    project_id="alpha.staged.software",
    title="Artificial staged engineering reference",
    request=original["request"],
    limits=original["limits"],
    sources=[SourceRecord(
        id="original-input",
        locator=input_path.name,
        version="1",
        sha256=hashlib.sha256(raw).hexdigest(),
        role="caller_supplied_complete_contract",
        reuse_terms="Project-authored artificial declarations; see provenance.json",
    )],
    assumptions=[
        "Supplied implementation contracts are premises; biological validity is unassessed.",
    ],
)
print(project.preflight())
project.dump("python.project.json")

# Reload independent authority so publication also protects its file path.
current = ResearchProject.load("python.project.json")
built = current.compile(output="python.payload.zip")
verified = current.verify_bundle("python.payload.zip")
print(verified.status)
```

The `from_request` path packages an already complete supported request. The
typed `from_build_request` path accepts a newly authored source and an immutable
`ComponentMaterialInputs` package; the staged script demonstrates it without
editing internal request JSON. Builders for every internal authority remain a
separate development item. Neither route establishes unrestricted therapeutic
regimen compilation. For
untrusted input files, use the bounded standalone `prepare` command or a prepared
project through `ResearchProject.load`, rather than an unbounded application
file read.

## Check transferability and review the handoff

Repeat preparation, compilation and verification using
`corpus/comparison-input.json` with distinct project and bundle names. This case
uses a state-reading policy and a different declared leader. Its expected RNA
length and CDS position differ, so the workflow cannot succeed by returning the
first example's bytes. Both cases and their coordinate conventions are frozen
in `corpus/expected.json`. The freshly authored staged source uses the staged
case's independently supplied contracts and expected RNA; its complete source
and actual source map are checked separately. It is a third user workflow,
not a third biological reference.

Compare the emitted sequence, annotations and supported claim scope with that
independent oracle. Use `corpus/negative-controls.json` when reviewing rejection
coverage. It specifies altered sequence and manifest, wrong original project,
missing machine capacity, unsupported completion guarantees and publication
failures. The control list itself is not evidence that the current release ran
those tests; retain the corresponding hosted receipt.

For a real project, replace the entire input with the researcher's complete
original specification and explicit contracts. Changing only these examples'
CDS cannot establish that their artificial controller contracts apply to the
replacement product. Exact chemistry, full molecule context, source rights and
an independently specified expected result must be resolved before qualifying
that project. The existing FAP-CAR reference is CDS-only and remains an explicit
incomplete-reference control.

A completed handoff review should record who performed the clean-install
walkthrough, the exact project and package versions, the independently verified
bundle identity, whether the task is useful, and every unresolved biological or
implementation premise. No external researcher walkthrough or experimental
validation is implied by the software examples.

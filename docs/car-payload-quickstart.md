# Nominal CAR RNA payload quickstart

The standalone [`car_payload.py`](../examples/car_payload.py) prepares an
editable, typed expression project from the complete public RM_61461 CAR RNA
reference. Core generates the candidate; independent Verify checks it against
the original project before publishing a FASTA/manifest pair.

**Validation status:** this CAR path is a source candidate. Native, installed
package and release acceptance remain pending until the corresponding checks
pass for its exact revision. The commands below describe the intended workflow;
pure Python preparation or mocked command tests do not establish those gates.

The design preserves the listed 1,776 RNA bases and their nominal correspondence
to the 485-amino-acid CAR2 product, with the source-declared Cap-AG and uridine
replacement chemistry. The publication does not fully specify its physical
3′ end. Preparation therefore requires the explicit design choice
`designer_supplied_hydroxyl`; it is recorded separately from source facts.
This is a nominal design under supplied expression, localization and delivery
premises, not an exact reproduction of a historical physical batch.

The intended recipient remains a human T cell in a human in-vivo environment.
The source's ex-vivo human-cell experiments do not establish in-vivo delivery,
expression, therapeutic function, safety or human-use permission. See the
[reference qualification](car-rm61461-qualification.md) for exact sequence
joins, source context and unresolved applicability and reuse questions.

## Use the installed SDK

The release handoff must provide matching SDK and native wheels for the exact
accepted revision and platform, their digest records, and `car_payload.py`.
The SDK wheel must include its pinned factual reference pack; the external
publication PDF and XML are not required for ordinary preparation and are not
downloaded by this script. Their original locators and hashes remain in the
project. Loading the pack does not authenticate the publication or grant reuse
rights.

After that handoff is validated, install only those exact wheels in a clean
environment. Here `SDK_WHEEL` and `CORE_WHEEL` are the supplied absolute paths:

```sh
python3 -m venv /absolute/path/to/car-environment
/absolute/path/to/car-environment/bin/python -m pip install \
  --no-index --no-deps --only-binary=:all: "$SDK_WHEEL" "$CORE_WHEEL"
```

Copy `car_payload.py` to a new working directory outside the repository. Use the
installed environment's Python as `python` below, without a repository
`PYTHONPATH` or an editable install. No native build is needed by the researcher.
Contributors keep native compilation and execution hosted under the workspace
validation policy.

## Prepare and inspect

```sh
python car_payload.py prepare rm61461.project.json \
  --three-prime-end designer_supplied_hydroxyl \
  --max-rna-nt 1776

python car_payload.py preflight rm61461.project.json
```

Both flags are mandatory. Preparation copies the complete reference without
sequence optimization and records the explicit RNA-length requirement. It
writes a `biocompiler.research_project.v0.2` expression project with `limits:
null`: this route has no temporal machine, controller or inferred cellular
runtime behavior. Existing output files are preserved.

Successful preparation and preflight report `structurally_ready`,
`native_status: not_run`, `biological_status: unassessed` and
`provenance_status: caller_declared`. These describe transport readiness only.
No source locator is followed and no native executable is invoked.

The same preparation through the public typed Python API is:

```python
from biocompiler.policy.car_reference import rm61461_request
from biocompiler.policy.research_project import ResearchProject

request = rm61461_request(
    maximum_rna_nt=1776,
    three_prime_end="designer_supplied_hydroxyl",
)
project = ResearchProject.from_expression(request)
project.dump("rm61461.project.json")
```

## Compile and independently verify

Once the exact installed release has passed its gates:

```sh
python car_payload.py compile rm61461.project.json rm61461.payload.zip
python car_payload.py verify rm61461.project.json rm61461.payload.zip
```

The default resolver checks the installed SDK/native pairing and chooses the
separate Core and Verify executable roles. Compilation generates with Core,
then requests a fresh Verify export. The ZIP contains exactly `program.fasta`
and `manifest.json`. The manifest preserves the complete original project
context, request, candidate, chemistry provenance, supplied premises and
checking evidence. It is a design artifact, not a manufacturing or experimental
protocol. Biological realization remains unassessed after software acceptance.

An authorized validation environment can select explicit executables instead:

```sh
python car_payload.py compile rm61461.project.json rm61461.payload.zip \
  --core "$CORE" --core-sha256 "$CORE_SHA256" \
  --verify "$VERIFY" --verify-sha256 "$VERIFY_SHA256"

python car_payload.py verify rm61461.project.json rm61461.payload.zip \
  --verify "$VERIFY" --verify-sha256 "$VERIFY_SHA256"
```

Each explicit path requires its matching SHA-256. Verify never performs a
producer operation. Keep the independently retained project: an archive's own
request, source labels or saved PASS cannot authorize that archive. Reopening
it requires fresh Verify checking and comparison with the exact published
FASTA and manifest bytes.

## Revise the requirement without changing the reference

Projects are editable, but every edit changes the original authority and must
be checked afresh. For example, prepare a second project with the complete RNA
bound one nucleotide below the reference length:

```sh
python car_payload.py prepare rm61461-too-short.project.json \
  --three-prime-end designer_supplied_hydroxyl \
  --max-rna-nt 1775
```

This preserves the same complete reference material and changes the length
requirement. Structural preflight can succeed; fresh native checking must
reject this incompatible bound and publish no accepted payload. That
distinction is a required validation control, not a claimed local native test.
Use a new output name for each revision. Changing project metadata also
requires a matching change in the request's complete `project_context`;
one-sided edits fail before compilation. An old bundle cannot be reused as
acceptance for the changed project.

A nonaccepted native assessment exits with status 1 and retains its report on
standard error. No accepted bundle is published. Existing destinations remain
intact when validation fails. Preparation failures and incomplete explicit
executable selections likewise produce a nonzero exit.

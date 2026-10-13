# Editable controlled two-RNA workflow

This development starter connects a saved program, complete RNA authority,
construction, independent material and finite-behavior checking, and a freshly
verified two-member publication. Its tiny `MA` / `MG` products and 17-nucleotide
RNAs are artificial software fixtures. Their supplied receptor-activity model
is not evidence of expression, cell killing, delivery, safety or clinical use.
A real two-RNA reference and empirical qualification remain open.

The RC6 installed rehearsal uses Linux x86-64 and Python 3.11. Four-slot release
acceptance is a separate RC7 gate. Native executables in this starter belong to
its recorded source, hosted run and attempt; they are not portable executables.
The SDK wheel is pure Python. Start in the extracted starter directory and use
an existing compatible Python environment:

```sh
python -m pip install --no-deps --no-index wheels/biocompiler-0.1.0.dev29-py3-none-any.whl
python examples/controlled_composition.py prepare data/controlled_composition/baseline-input.json my-project.json
python examples/controlled_composition.py preflight my-project.json
python examples/controlled_composition.py explain my-project.json
```

Preparation and inspection do not execute native code or claim acceptance.
The saved project retains the whole original request, component contracts,
complete material authority, observation evidence, domain and exact limits.
Its metadata comes from the original source context.

Use the authenticated starter download and retain its original
`starter-manifest.json`. Artifact extraction may remove executable permissions.
From the starter directory, compare both binary hashes against that manifest,
and restore owner execute permission only if both comparisons pass:

```sh
python -c 'import json; m=json.load(open("starter-manifest.json")); print("\n".join("{}  {}".format(m["files"][p]["sha256"], p) for p in ("bin/biocompiler-core", "bin/biocompiler-verify")))' |
  sha256sum --check &&
  chmod u+x bin/biocompiler-core bin/biocompiler-verify
```

This permission change preserves the exact binary bytes and their hashes. The
comparison verifies agreement with the supplied manifest; the separately
recorded authenticated download establishes its provenance. Read the two hashes
from that manifest and supply them explicitly (replace the placeholders below):

```sh
python examples/controlled_composition.py compile my-project.json my-pair.zip \
  --core bin/biocompiler-core --core-sha256 CORE_SHA256 \
  --verify bin/biocompiler-verify --verify-sha256 VERIFY_SHA256
python examples/controlled_composition.py verify my-project.json my-pair.zip \
  --verify bin/biocompiler-verify --verify-sha256 VERIFY_SHA256
```

The compile route constructs and freshly checks material and behavior. Verify
freshly checks them again before atomic publication. The ZIP contains exactly
`program.fasta` and `manifest.json`; both RNAs and the complete original request
are published together. Failed, unknown, cancelled or limit-rejected work does
not publish a partial accepted pair. Reopening requires the independent saved
project and a fresh Verify result; a saved report cannot grant acceptance.

Use a new output name for every edit and retain the original project:

```sh
python examples/controlled_composition.py edit my-project.json tight-project.json \
  --max-member-rna-nt 17 --max-total-rna-nt 34
python examples/controlled_composition.py edit my-project.json short-project.json \
  --max-member-rna-nt 16 --max-total-rna-nt 34
python examples/controlled_composition.py edit my-project.json deadlines-project.json \
  --onset-ticks 1 --controller-off-ticks 1 --antigen-off-ticks 1 \
  --component-off-ticks 1 --reactivation-ticks 1
python examples/controlled_composition.py edit my-project.json longer-horizon-project.json \
  --horizon-input data/controlled_composition/horizon-eleven-input.json
python examples/controlled_composition.py edit my-project.json longer-rna-project.json \
  --material-input data/controlled_composition/material-longer-input.json
```

Compile each edited project with the same explicit native arguments. The
independent literal cases define these expected outcomes; the retained hosted
rehearsal records their actual checks:

| Edit | Expected conditional result |
| --- | --- |
| Per-member 17, total 34 | Accepted, unchanged two 17-nt RNAs |
| Per-member 16, total 34 | Admission rejects the supplied 17-nt RNA members before construction |
| Per-member 17, total 33 | Admission rejects the supplied 34-nt total before construction |
| Five requested deadlines of one tick | Accepted against actual one-tick delays |
| Horizon 11 with explicitly supplied additional evidence | Accepted over both complete histories |
| Horizon 9 | Rejected: insufficient hold suffix for original obligations |
| Complete supplied second RNA extended to 18 nt in its 3′ UTR | Accepted with changed exact RNA bytes and unchanged `MG` product |
| Supplied onset delay 3, requested onset deadline 2 | Behavioral failure; no pair |
| Same onset-3 model, requested onset deadline 3 and horizon 11 | Accepted |
| Missing activity readout at tick 3 | Unknown evidence; no pair |

Complete original RNAs must fit the supplied resource ceilings. The two
undersized-limit cases return `controlled_authority_admission` with
`Original RNA length exceeds supplied per-member/total resources.` They produce
no candidate, material assessment or accepted pair.

Requested deadlines are source demands. Editing them does not rewrite actual
mechanism delays. Extending a horizon requires explicit evidence and retains all
domain factors; the helper invents no measurements. Material edits require a
complete supported authority, not a free sequence patch. The controller is one
executor-scoped external dependency; it is not copied into either RNA member.
The interpretation is same-recipient under supplied assumptions.

Equivalent public Python authoring is available without the example:

```python
from biocompiler.policy.controlled_workflow import ControlledWorkflowRequest
from biocompiler.policy.research_project import ResearchProject

build = ControlledWorkflowRequest.from_request(complete_original)
edited = build.with_rna_limits(max_member_rna_nt=17, max_total_rna_nt=34)
project = ResearchProject.from_controlled(edited)
project.dump("edited-project.json")
# project.compile(output=..., core=pinned_core, verify=pinned_verify)
# ResearchProject.load(...).verify_bundle(..., verify=pinned_verify)
```

The hosted rehearsal also reopens the baseline in an outside-checkout consumer
with only Verify and a closed set of unchanged SDK authority codecs. Actual
Python producers and native Core are absent from that staged tree; a launch
guard allows only the pinned Verify executable and kernel policy denies its
network access. The host filesystem is not isolated. The copied codec set
includes record modules in `compiler` and `semantics`; this is not a claim that
all files with those namespace names are absent.

`evidence/installed.json` and its retained files record exact originals,
mutations, native requests/results, file hashes and elapsed milestones. Timing
covers an automated maintainer rehearsal and excludes installation. It does not
measure a novice human study. Human use remains unassessed and therapeutic
export remains withheld, including for accepted artificial cases.

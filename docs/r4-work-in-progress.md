# Historical R4 checkpoint for the next session

The user resumed this checkpoint on 2026-09-30. See the current
[session handoff](session-handoff.md) and [R4 guide](circuit-construction-v0.1.md).
The failures and stop instruction below describe the saved checkpoint, not the
current implementation or current authorization. Final hosted validation remains
required before milestone merge.

The user requested stopping for a fresh session on 2026-09-30. R2 and R3 were
already merged before that request. This branch is an unfinished checkpoint,
not a completed milestone, and must not be merged until its outstanding work
and exact-revision hosted validation are complete.

## Completed baseline

- R2: [PR #29](https://github.com/logannye/biocompiler/pull/29), merge
  `307beacb344473327f227e52fb71cb6e0c92c142`, version `0.1.0.dev22`.
  Final head `427a4efb98dc2580f9e21efc62ffe000a1ce1397`; tested PR merge
  `17ca7676f05fd0f7c14611907abce2d92e3c42c2`.
  [Hosted CI](https://github.com/logannye/biocompiler/actions/runs/36785228119)
  passed all 1,206 tests, package and browser gates.
- R3: [PR #30](https://github.com/logannye/biocompiler/pull/30), merge
  `e67149b3fc045b1704aef998afe756a5907a08eb`, version `0.1.0.dev23`.
  Final head `ff82266f4a9dbf5e927d6d2452cf54f542ed8d25`; tested PR merge
  `2e086dd56d45c6659f04f6d21f070d233b2c6397`.
  [Hosted CI](https://github.com/logannye/biocompiler/actions/runs/36788492877)
  passed all 1,296 tests, package and browser gates.
- Both hosted runs used Python 3.11.16/3.14.7 on Linux x86_64. Each merged
  tree was checked against its tested head. External exact-revision receipts
  are `work/r2-ci-final.json` and `work/r3-ci-final.json` in the parent workspace.

## Scope and constraints

The sole product target remains human DNA/RNA payloads for in-vivo immune-cell
deployment. Preserve the original human request and every wrapped obligation.
The R1 metadata-only draft PR #28 remains unmerged and incomplete. A prior
source-reconstruction task encountered a safety-control restriction; do not
retry or reroute that restricted reconstruction. No actual source corpus or
published sequence reconstruction was added here. All new fixtures are tiny,
explicitly artificial software controls. Source-dependent milestones remain
open. No structural result grants biological function or human admission.

Do not run local native compilation, package installation or implicit builds.
Pure Python checks and static tools are allowed locally; package/native and
required integration gates belong on hosted CI. Preserve all existing gates.

## Saved implementation

Branch `codex/r4-checked-transformations` is based on merged R3. Its provisional
version is `0.1.0.dev24`; this is not a released or validated milestone.

- `ir/circuit_construction.py`: strict full-source construction requests, root
  authority, sequence-free output ports, an ordered acyclic operation graph,
  required roles, final molecules, complexes and experimental amounts. Includes
  slicing, concatenation, orientation, transcription, RNA/protein processing,
  circularization, editing and translation-family operation declarations.
- `ir/circuit_transitions.py` and `verification/circuit_transitions.py`:
  exhaustive chemistry and feature dispositions, independent coordinate
  correspondence and explicit unknown/unsupported outcomes.
- `ir/circuit_recoding.py`: canonical versus chemical edits, exact conditional
  codon declarations and a standard immutable codon table. The public alias is
  `CircuitTranslationPolicy`; the existing `TranslationPolicy` is unchanged.
- `ir/circuit_payloads.py` and `verification/circuit_payloads.py`: explicit
  required-region contracts for linear/circular DNA/RNA payloads, including
  declared nucleotide-complex constituents. No regulatory regions are inferred.
- `artifacts/circuit_construction.py`: actual candidate values, per-residue
  source maps, explicit consumed terminal stops, final inventory and quantities.
- `backends/circuit_construction.py` and `backends/circuit_recoding.py`:
  construction from supplied authority with cumulative work budgets and atomic
  multi-output operations. No expected output strings are supplied by ports.
- `verification/circuit_construction.py`: separately implemented reconstruction,
  exact candidate comparison, transition checks and strict payload checks.
  It must remain independent of the producer implementation.
- `artifacts/circuit_construction_build.py` and
  `compiler/circuit_construction.py`: retained build, fresh replay against a
  separately supplied complete request and strict complete-set handoff.
- Public Python dispatch, CLI `circuit-build`, `circuit-verify`,
  `circuit-export`, and artifact inspection are wired but need workflow tests.
  Export retains the full build; it is not yet the R12 complete export system.
- `examples/circuit_construction.py` is a tiny artificial construction example.
  The last local execution and `bc.compile()` dispatch produced a passing
  structural assessment. This is not evidence that all R4 gates pass.

Conditional no-product branches remain explicitly unsupported in the assessment;
their absence semantics require later mechanism-family authority. Splicing
execution currently requires increasing source spans; document and review that
restriction against the IR's preserved explicit path order. Translation requires
an explicit forward contiguous RNA region, AUG and a terminal stop; alternative
initiation and family-specific behavior are not inferred.

## Known failures and immediate fixes

Producer and checker currently disagree about recoding preflight order. Fix
the producer's phase ordering and rerun the saved edge regressions:

1. Check output alphabet/topology before translation or edit allocation. The
   producer currently checks some ports late, yielding `invalid_translation`
   where the checker reports `unsupported_alphabet`.
2. For translation, validate the selected path/frame, literal AUG and declared
   modification inventory before reserving work. The checker does this; the
   producer currently reserves before those latter checks. At zero remaining
   work, malformed starts can therefore produce different diagnostics.
3. For ribosomal skipping, validate the complete residue allocation after work
   reservation but before translating, matching the checker. A malformed
   allocation combined with a missing stop currently differs in diagnostic order.

The checker reserves attempted work even when materialization later fails.
For editing, source/port alphabet and topology precede reservation; modification
inventory and edit-symbol checks follow it. For translation, port/path/frame/AUG
and known inventory precede reservation; codon/recoding/stop checks follow it.
Keep failed-step outputs atomic. Final alias length preflight and exact sequence
extent preservation have already been added to both implementations.

`tests/test_circuit_construction_edges.py` contains 12 regressions. Its last
execution was before the final two additions: 9 of 10 passed, with the output-port
preflight case failing. Do not relabel this suite as passing.

## Validation checkpoint and remaining acceptance

Separate focused checkpoints passed: 62 construction-IR tests, 51 independent
checker tests, 33 transition tests, 14 recoding-schema tests, 15 payload tests,
6 core producer tests, 6 processing producer tests and 11 recoding producer
tests. These were not a single final-revision full-suite run. Individual Ruff
checks passed at their checkpoints. No complete R4 hosted validation is claimed.

Before completing or merging R4:

1. Resolve the known preflight differences; inspect the final checker diagnostic
   budget work and complex/amount replay tests saved at the checkpoint. These
   additions passed the 51-test owned checker suite (53.212 seconds) and Ruff;
   the independent cross-implementation edge suite still has the failures above.
2. Run all new focused tests together. Check malformed inputs, budget boundaries,
   output atomicity, chemistry/feature correspondence, complex quantities and
   fresh replay under tampering and changed external authority.
3. Add public build/verify/export and CLI tests, including strict versus diagnostic
   mode, stale/rehashed records, input/output collisions and atomic publication.
4. Review bounds and independent checker coverage. Saved PASS records must never
   replace fresh verification against complete external request authority.
5. Update decision 0006 (currently an earlier core-only draft), write the R4 guide,
   and update architecture, roadmap, README, plan and session handoff accurately.
   R4 checkboxes remain open. No fixture closes R1, R5 or source-backed R6 gates.
6. Extend hosted installed CLI/example gates for R4, retaining all older gates and
   artifacts. Run the full pure Python suite, Ruff, audit and diff checks locally;
   existing localhost HTTP tests require the already-authorized escalation.
7. Commit/push the final implementation, create and attach its PR, and require all
   exact-head hosted tests/package/browser gates before squash merge. Record head,
   tested merge revision, platform and results; verify the merged tree matches.

Resume only when the user begins the next session. The stopping request takes
precedence over the earlier instruction to continue through R13 in this session.

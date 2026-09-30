# Session handoff and current resumption point

## Current resumption point — after M11.1

Updated **2026-09-29 (America/Los_Angeles)** in [PR #19](https://github.com/logannye/biocompiler/pull/19).
M11.1's [bounded audit](m11-human-benchmark-audit.md) is complete with a justified
deferral of a complete therapeutic benchmark. The [roadmap](roadmap.md) records
the exact tested revision/platform and hosted validation. Nine candidates,
sixteen source records, eight claim-blocking gaps and a small locked audit trail
are retained. The profile, compiler admission and biological capabilities are unchanged.

Resume with exact material/source correspondence for the prioritized Roybal
secretion-observation and Allen component/context leads before M11.2 reference
reconciliation. Roybal's indexed supplemental attachment returned challenge HTML;
Allen's correction and full-record correspondence remain unresolved. Retain
Equalizer as a separate scoped reporter/model candidate. Do not substitute its
evidence for therapeutic secretion, primary-T-cell applicability or patient delivery.
M11.2–M11.6 remain open; no human therapeutic profile is admitted.

## Historical M10 closing snapshot

Session closed on **2026-09-29 (America/Los_Angeles)** after M10.6. This is a
handoff snapshot; [the development roadmap](roadmap.md) remains authoritative
as later work advances.

## Repository and completed work

- Repository: [logannye/biocompiler](https://github.com/logannye/biocompiler).
- Package and CLI: `biocompiler`; current release version: `0.1.0.dev13`.
- Implementation baseline: `8fe7922db9ca3183eee6a97b2eefee3d979ee39d` on `main`,
  containing [M10.6 PR #17](https://github.com/logannye/biocompiler/pull/17).
- M10.1–M10.6 software contracts, admission enforcement, request cases and
  completion-scope documentation are implemented. M11.1 is the next unchecked
  roadmap item. M11 work has not been started as part of this handoff.
- [Merged-main validation](https://github.com/logannye/biocompiler/actions/runs/36653457950)
  passed. The final M10.6 PR validation passed all **783 tests**, package
  installation, examples, archive reconstruction, CLI checks and retained profile
  evidence on Python **3.11.16 and 3.14.7**, Linux x86_64. Exact tested revision
  and platform are recorded in [the roadmap](roadmap.md).

The actual therapeutic objective remains a precise, complete RNA or DNA
molecular specification for in-vivo deployment into a human patient. Current
capabilities cover typed intent/contracts, abstract software execution and
independently checked reference CDS reproduction. **Human therapeutic compilation
is unavailable; no human profile or complete therapeutic payload is admitted.**

## Historical opening actions at M10 close

1. Start from current `main` in the canonical `biocompiler` repository and read
   [AGENTS.md](../AGENTS.md), [the roadmap](roadmap.md), and
   [the proposed human profile](human-profile-v0.1.md).
2. Review [the human admission policy](human-admission-v0.1.md),
   [the acceptance contract](human-acceptance-contract-v0.1.md),
   [the M9 evidence review](m9-evidence-review.md), and
   [reference benchmark notes](reference-benchmarks.md).
3. Begin **M11.1: audit candidate human benchmarks** for exact sequences,
   complete molecule definitions, quantitative measurements, models, biological
   context and reuse terms. Earlier candidate leads and retrieval failures are
   historical evidence to reassess against current M10/M11 obligations.
4. Produce a reviewable candidate comparison, supported/unsupported-claim
   inventory, source locators and versions, access/reuse limitations and a
   justified selection or deferral decision. Link each missing input to the
   compiler claim it prevents. Record findings in the repository and update the
   roadmap only when the relevant completion criteria are met.

## Questions the audit must resolve

The proposed first behavior family is **reversible conditional secretion**.
The current example proposes RNA and one human recipient-cell role, with a
CD8-positive T-cell family label. Precise cell subtype/state, tissue/disease,
population applicability, cue/product identities, delivery platform and
biological response bounds remain unresolved. All example measurements and
timing values are artificial software fixtures.

For each candidate, determine which source material is actually identified:
CDS, production template, complete mature molecule, delivered artifact or
experimental preparation. Establish whether exact sequence, chemistry,
measurements and executable model refer to the same material and context.
Where correspondence is unsupported, retain separate benchmark identities.
Identify measured data versus fitted values or assumptions, uncertainty, and
what could support independent evaluation rather than calibration alone.

Human cell-line, primary-human-cell and human in-vivo evidence remain distinct.
Nonhuman evidence retains its species and translation limitations. The bundled
murine FAP CDS remains a software regression reference. A source citation,
sequence identity check, observed-trace PASS or structural-readiness result
cannot establish human implementation admission.

M11.1 is an evidence and profile-decision milestone. Complete reference curation,
model implementation/validation, molecular construction and intent-root compiler
admission have separate M11–M14 gates. Missing evidence can justify deferring a
candidate; it does not establish that a resource does not exist or that the
therapeutic goal is biologically infeasible.

## Working preferences and verification

- Keep unknown, failed, unsupported, search-exhausted and demonstrated-infeasible
  outcomes distinct. The M10.6 mathematical rate contradiction has an explicit
  condition and does not prove biological reachability or feasibility.
- Use independent authority and fresh checks; saved PASS reports are historical
  records. The examples can be regenerated with
  `python examples/human_profile_cases.py --output generated/profile-cases` and
  rechecked with `--verify generated/profile-cases`.
- Keep patient data, credentials and generated scratch artifacts outside version
  control. Retained public evidence must carry appropriate identity, provenance
  and reuse information.
- Keep native/Rust compilation and packaging on hosted CI by default. Local
  Rust compilation or implicit native rebuilds require explicit authorization.
  Pure-Python and documentation checks can run locally.
- Continue the established branch/PR workflow, record tested revisions/platforms,
  and merge only after required checks pass.

Historical opening prompt: **“Resume biocompiler at M11.1. Read
`docs/session-handoff.md`, `AGENTS.md` and the roadmap, then begin the human
benchmark and evidence audit.”**

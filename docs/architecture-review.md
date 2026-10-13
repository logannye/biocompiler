# Architecture review

Status: review procedure adopted 2026-10-13. Apply the
[architecture charter](architecture-charter.md) to changes in proportion to their
effect on source-to-RNA behavior. The [capability matrix](capability-matrix.md)
records current support; the [refactoring roadmap](architecture-refactoring-roadmap.md)
records the target migration. Reviewing a design does not mark its implementation
or exact-revision validation complete.

## Scope and proportionality

Use the normal change description and existing review process. A wording fix,
renaming or local implementation cleanup generally needs only a sentence naming
the affected contract, or explaining why semantics are unchanged. Do not require
a separate architecture document, new tests or an external reviewer for every
change.

A change to semantics, source/IR shape, composition, selection, authority,
material emission, export or checking needs the relevant answers below. Existing
evidence can supply those answers when its scope still applies. Add targeted
distinguishing controls for changed behavior; preserve the project's required
integration gates. Follow [development validation](development-validation.md)
for local static feedback and hosted native validation.

## Questions that must have answers

| Principle | Review question | Useful evidence |
| --- | --- | --- |
| AC-01 Semantic adequacy | What therapeutic distinction does the change express, and where is its meaning defined? Are host code, cellular behavior and external protocol actions distinct? | Source example, typed rules, scope/lifecycle cases, unsupported diagnostics |
| AC-02 End-to-end soundness | How does the accepted RNA implement the original supported request under stated premises? What permitted behavior/refinement relation is checked? | Positive end-to-end witness, meaningful source edit, counterexample, non-vacuous progress coverage |
| AC-03 Composition | Which interfaces, assumptions, ownership and shared resources make the parts valid together? | Interference/aliasing controls, context and capacity checks, bounded whole-program comparison |
| AC-04 Realization-aware synthesis | Can material or context failure cause reconsideration of a prior choice? What is known about a winner versus the search? | Feasible and infeasible alternatives, ordering controls, retained rejection/unknown outcomes |
| AC-05 Uncertainty/time | What do physical state, observations and evidence mean, and which clock/event/freshness rules apply? | Missing/stale/conflicting or erroneous observations, boundary ticks, reset and persistence controls |
| AC-06 Independent checking | What must be trusted? Can Verify reconstruct this claim without the producer's claim-defining algorithm? | Dependency boundary, independent expected values, tampered-candidate rejection, checked-type interfaces |
| AC-07 Provenance | Can the result be traced to complete original authority and freshly rechecked after reopening? Which edits invalidate it? | Source/IR/material lineage, dependency mutations, paired export/replay, exact validation receipt |
| AC-08 Extensibility | Does this extend reusable semantics or add another special case? Are supported feature combinations discoverable? | Capability-matrix update, cross-feature witness, version/adaptation plan |
| AC-09 Scale/diagnostics | Are all phases bounded and failures attributable to an actionable cause? What was measured? | Work/publication limits, exhaustion/cancellation controls, source-linked diagnostics, relevant timing evidence |

Not every row needs a new test or a paragraph in every PR. State which principles
are materially affected and make those answers reviewable. Do not manufacture
unrelated concerns to fill the table.

## Distinguishing controls for substantial changes

Select controls that would expose the actual failure being prevented. Useful
examples include:

- A supported positive case and a source edit that changes the checked
  implementation/material, or produces a precise rejection.
- A valid alternative added to a catalog without hiding an existing feasible
  solution; separate candidate validity from completeness or optimality claims.
- Two individually supported features combined, including ownership, timing or
  resource interaction that an isolated fixture would miss.
- A physical input distinct from missing evidence or a differing observation;
  an event at the exact timeout/freshness boundary; residual activity after RNA
  or production loss.
- A corrupted candidate, changed original authority or untrusted PASS report
  rejected by fresh independent checking.
- An exhausted or cancelled invocation that publishes no unsupported acceptance
  and retains the affected stage, bounds and useful failure information.

These are design-review examples, not a mandatory new suite for every change.
Tests must challenge behavior with independently stated expectations, rather
than merely mirror the implementation. A rejection-only campaign cannot close
a claimed new compilation capability. A successful example alone cannot close
all combinations represented by a broader API.

## Decision and deviation records

Use an ADR under `docs/decisions/` for a lasting change to source meaning, the
trust boundary, public acceptance contracts or the target IR/pass organization.
Also use an ADR when deliberately deviating from a charter principle, including
a temporary specialized route that adds another acceptance family. Routine
implementation choices within an existing contract do not need a new ADR.

The record must identify:

1. The decision, affected AC identifiers and concrete user/compiler problem.
2. The alternatives considered and why the selected scope is justified.
3. Preserved invariants, changed meanings, explicit assumptions and known risks.
4. The supported surface, distinguishing acceptance evidence, migration/version
   impact and any dependent claims that require fresh checking.
5. For a temporary deviation, an owner or owning workstream, a revisit trigger
   and a concrete convergence or retirement condition in the roadmap.

Do not label a restriction an unavoidable biological limitation when the
obstruction is an implementation family, data representation or search policy.
Do not relax an integrity check merely to make a candidate pass; first distinguish
invalid authority from valid but infeasible or unresolved alternatives.

An ADR documents a technical decision; it does not automatically require another
user confirmation. Continue within existing authorization and normal repository
review. Escalate to the user only when a decision actually changes the authorized
product scope, makes an unresolved material choice that requires the user, or
needs permission under the applicable execution rules. An outstanding future
refactor does not block an independently useful, correctly scoped increment.

## Completion and reporting

For a substantial architecture change, the review record should let a reader
identify the problem, resulting behavior, affected AC identifiers, checked
contracts, support changes, deviations and validation scope. A concise PR
description with links is sufficient; avoid duplicate governance artifacts.

Update the capability matrix when support changes, including combinations,
limits and explicitly unsupported meanings. Update the roadmap when an exit is
met or its scope changes. Keep proposed, implemented, locally checked, hosted
validated, integrated and released states distinct, with exact evidence where
applicable. Architecture approval is neither empirical qualification nor runtime
acceptance, and a historical passing revision cannot validate a changed one.

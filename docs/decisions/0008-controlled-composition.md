# ADR 0008: Supplied controlled composition with a distinct activity endpoint

- Status: accepted design for the implementation increment; native acceptance pending
- Date: 2026-10-12
- Source baseline: `0b19ef68ad029de1c10245008fddf81a3a4bfddd`
- Specification: [controlled composition v0.1](../controlled-composition-v0.1.md)
- Delivery plan: [CAR composition and reversible control roadmap](../car-composition-reversible-control-roadmap-2026-10-12.md)

## Context

The next research example supplies two complete RNA members encoding a paired
split CAR and a separate small-molecule controller. Both proteins cooperate in
the same human T cell. Antigen engagement and cell-local controller exposure
jointly enable a named activity. The intended deployment is human immune cells
engineered in vivo; the original experiment's context remains separate.

The existing static-expression route admits one RNA and one product without
temporal behavior. Existing finite-machine and multi-member component routes
have different, deliberately closed source and realization families. Their
feature switches cannot be combined to establish this mechanism. Existing
product-bearing effects also do not describe receptor activity, and the current
operational executor rejects lifecycle stop/cancellation.

The reusable foundation is substantial: typed source, original definition and
catalog authority, source admission/lowering, supplied component realization,
independent source/candidate execution, bounded domain traversal, construction,
material/context checking, and fresh ResearchProject publication. This increment
connects and extends those passes rather than adding a CAR-specific compiler.

## Decision

1. Add one closed `controlled_composition` family to the component-material
   toolchain. It admits exactly one human T-cell executor, one encounter slot,
   two RNA members, two encoded products, one controlled activity, one external
   controller, and finite sampled execution. Preserve every legacy profile's
   canonical records, semantics and rejection behavior.
2. Add a typed `ControlledActivity` source declaration and an `activity_band`
   expression. The activity is neither product generation, secretion, killing,
   nor a generic effect attempt. Its state is executor owned; antigen evidence
   and engagement are encounter owned. The declaration's gate is exactly antigen
   AND controller. Functional product availability is separately bound original
   deployment/mechanism authority, not an invented cell sensor.
3. Specify the source as an allowed activity relation and a set of independently
   evaluated requirements. Source deadlines are maximum allowed response times.
   A supplied model has its own actual delays. Earlier compliant activation or
   cessation is allowed; equality with one preferred source output trace is
   neither necessary nor sufficient.
4. Initially admit only a deterministic delayed-control mechanism with positive
   integral onset, cessation and reactivation delays and an explicit initial
   background state. Reject stochastic or nondeterministic mechanism contracts
   in v0.1. Enumerate every admitted physical-input/evidence history; deterministic
   mechanism semantics do not mean that only one environment history is checked.
5. Preserve physical state separately from evidence. Activity has exactly the
   physical bands `background` and `active`; missing, stale, invalid and
   conflicting evidence never become physical OFF. V0.1 conservatively returns
   unknown for unresolved evidence needed to discharge a demanded requirement.
   This is software uncertainty, not a cellular safety action or an empirical
   qualification requirement.
6. Use the exact tick and priority rules in the specification. A loss while
   active commits to cessation; a restored gate cannot cancel or postpone it.
   Reactivation starts after background has been reached. Encounter reset/end
   invalidates encounter-owned activation but preserves executor-owned activity,
   protein availability and cessation timers.
7. Check every history through an explicit decision cutoff and a declared
   hold-last-inputs suffix long enough to discharge the remaining obligations.
   Preserve that restriction in the original request and report. Require active,
   inactive, independently disabled, and complete on/off/on coverage. Empty
   domains, omitted branches, unknown requirements and resource exhaustion do
   not receive complete behavioral acceptance.
8. Keep all original authority: source and definitions, paired material, component
   models/wiring, availability and controller contracts, readout map, deployment,
   project provenance, domain, execution limits and publication budgets. Fresh
   replay compares the independently retained request and limits before accepting
   any candidate or report. Local rehashing cannot make foreign material original.
9. Use an independently versioned source specification first, followed by Python
   conformance and additive generated native shapes. The old 45-record language
   specification and its canonical generated table stay unchanged. Representation
   work grants no native source, realization, material or behavioral acceptance.

## Version and implementation boundary

The source root is `biocompiler.policy_controlled_composition_source.v0.1`.
The component-material request is
`biocompiler.policy_component_material_request.v0.14`, with profile
`biocompiler.policy_controlled_composition_mrna.v0.1`. It uses the existing
`compile/check/replay/export-policy-component-material` operation family and new
explicit capability metadata. A compatible implementation must admit the whole
family; an old executable must reject it rather than falling back.

The new `BuildRequest` and contained `PolicyProgram` use the new source profile.
Their `SemanticBundle` uses the existing record profile. Old-profile standalone
programs, drafts, submissions and request roots reject the new declaration and
expression. Standalone new-profile program/draft/submission entry points are not
part of this increment. Existing Python record classes and exact codecs remain
shared infrastructure; widening the runtime registry alone must not widen any
entry point's acceptance.

Source reference execution, candidate primitive execution and requirement
checking have distinct responsibilities. The candidate evaluator must not call
the source evaluator. Verify reconstructs candidate behavior and molecular
content from complete original contracts; it never trusts producer-reported
outcomes. The operating-domain decoder/enumerator and source reference adapter
must be extended for executor-local inputs and activity bands, not only the
execution engine and monitor. Shared codecs, arithmetic and canonicalization
remain declared trusted infrastructure, not independent corroboration.

## Consequences and exclusions

The software can establish bounded source satisfaction, supplied-model
realization and exact material correspondence under explicit contracts. Complete
conditional support does not require a biological experiment. Whether the
contract holds in human cells, whether the selected reference was faithfully
reconstructed, and whether any human use is permitted remain separate results.

A real paired reference still needs complete original product and RNA records.
The existing full-length CAR references cannot be silently split or relabeled.
Artificial fixtures can complete software validation while the named reference
acquisition remains open. No mechanism search, sequence optimization, continuous
pharmacology, dosing policy, delivery guarantee or clinical conclusion follows.

Native admission, producer/checker implementation, complete installed acceptance
and release gates remain required work. This decision does not transfer acceptance
from the base or another checkout and does not authorize local native builds.

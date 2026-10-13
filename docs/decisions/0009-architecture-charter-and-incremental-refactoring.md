# ADR 0009: Architecture charter and incremental refactoring

- Status: accepted design direction; implementation milestones remain open
- Date: 2026-10-13
- Basis: user-requested adversarial architecture audit and repository codification
- Baseline: `ae683603dfbac95aeee1b1bc15efa3f873d0c630`

Number 0008 is reserved by the separately owned controlled-composition branch;
this decision uses 0009 to avoid an integration collision.

## Context

Biocompiler needs to grow from bounded source-to-RNA profiles into a coherent
therapeutic compiler. Its independent checking, explicit obligations, immutable
authority and exact molecular correspondence are assets to preserve. Profile
proliferation, overly structural matching, disconnected material selection and
uneven report meanings constrain that growth. Rewriting the entire compiler
would put the existing assurance machinery at risk and obscure regressions.

## Decision

Adopt the [architecture charter](../architecture-charter.md) as the enduring
design contract and the [refactoring roadmap](../architecture-refactoring-roadmap.md)
as the phased migration plan. Keep the [capability matrix](../capability-matrix.md)
as a dated editorial inventory, with the existing native admission and protocol
catalog remaining runtime authority. Apply the [review criteria](../architecture-review.md)
proportionally to future changes.

Use shared typed representations, explicit capability constraints and checked
adapters. Migrate one useful vertical slice at a time; keep old and new behavior
distinguishable and independently checked. Separate implementation validity,
requirement satisfaction, search completeness, exact artifact identity and
empirical applicability. Correct report meanings before expanding their scope.

Add an offline documentation-integrity check to existing CI preflight and
development feedback, and surface the review in AGENTS.md and the PR template.
This checker does not prove architecture compliance. Existing semantic,
adversarial, native, installed and release gates remain required.

## Consequences and limits

The guidance becomes discoverable and mechanically checked for missing links
and principle references. Architectural changes still require substantive
review and evidence. A deliberate departure records rationale, affected
principles/capabilities, bounded scope, compatibility, compensating tests and a
review checkpoint in an ADR; it cannot relabel unknowns as verified or bypass
the user's scope and validation requirements.

No compiler behavior changes in this governance increment. Known defects and
planned architecture changes remain open until their milestone criteria pass.
Historical validation records and the separately owned CAR branches are not
rewritten or qualified by this decision.

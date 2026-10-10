# Therapeutic specifications as checked programs

Python is the authoring language. The versioned policy language is the semantic
contract. A Python class layout, callback or package version is not that contract:
the closed wire specification identifies the records and their fields, while
native admission resolves names, sorts, scopes and semantic definitions before
lowering. The typed facade helps authors construct valid source; native admission
remains responsible for accepting untrusted source from any frontend.

## Meaning before implementation

A program describes observations, subjects, encounters, clocks, persistent state,
machines, effects, arbitration and requirements. Unknown observations have an
explicit meaning. State has ownership, lifetime and capacity. An effect request,
authorization, activation, cancellation and feedback are separate events. These
distinctions matter because a payload must implement the complete interaction,
including unsuccessful attempts and missing information.

Semantic modules add reusable interfaces to this vocabulary. Their inputs and
outputs carry complete nominal types and access rights. Private state and effects
are declared explicitly. Instantiation renames private identities hygienically;
composition checks bindings, ownership and conflicting writes. The opt-in
[native module-linking profile](policy-module-linking-v0.1.md) independently
reconstructs the proposed flattened source from the complete original module
bundle. Its checked relation is exact elaboration; module guarantees remain
original requirements to check. Linked material export preserves provenance
while freshly checking the complete program. Native execution of this addition
remains pending.

OCaml's role is to make the admitted language and checking boundaries explicit:
closed variants enumerate permitted operations, and abstract module interfaces
hide constructors for admitted and checked values. A decoded record and a checked
result have different types. This helps prevent accidentally treating a stored
report as permission to export. It does not prove the implementation correct;
the independent checkers, adversarial tests and native validation remain needed.

## Intermediate representations with distinct responsibilities

The original source remains available alongside the typed admitted IR. Lowering
produces operational behavior whose source occurrences are checked independently.
A supplied implementation library provides precise primitive models. The finite
machine lowering selects and connects them; an independent binding checker
reconstructs the required graph from the original program and proposed anchors.

Source and candidate then execute separately over the original finite operating
domain. Checking compares their observable behavior and monitors the original
hard requirements. Bounds constrain the claim explicitly. Running out of checking
resources yields incomplete evidence, not a smaller silently accepted domain.

Reusable component fragments give local graph and molecular declarations.
Assembly establishes the ordered graph correspondence, component identities,
interfaces, carriers and exact material construction. Context and prerequisite
checking connect the selected components to the supplied providers and resource
contracts. Export requires fresh completion of the whole chain and publishes the
exact paired FASTA and manifest. The component-to-material premise remains a
supplied model of realization; compiler checking does not establish empirical
function or therapeutic efficacy.

The generic finite-machine family is deliberately versioned separately. Retry
cycles, guarded branches and observation-update forks use the same lowering and
checking machinery within its declared bounds. Existing specialized profiles
retain their established meanings. New expressive features must either have an
explicit supported lowering/checking relation or remain visibly unsupported.

## Extension principles

Language growth should preserve original meaning, provenance and diagnostics.
New frontends should target the stable language rather than share Python object
internals. New transformations should name the relation they preserve: exact
source correspondence, bounded observable correspondence, conditional material
construction, or an explicitly defined quantitative relation. These are different
claims and should remain distinguishable when combined.

Evidence composition must bind the same endpoints, domain, assumptions and
limits. It should preserve every premise and reject incompatible identities.
An optimizer may propose a transformation, but the authority to accept it belongs
to the checker of the named relation. A JSON report is a reproducible record of
checking; it is not itself a native checked capability.

The implemented [named refinement interface](policy-refinement-v0.1.md) provides
ten closed relation kinds and retains eighteen original or freshly checked
premises. Its three directional composition rules distinguish exact source/graph
correspondence, bounded observable correspondence, and conditional source/material
correspondence. Composition rejects mismatched endpoints, domains, limits and
material requests. Fresh check/replay calls expose these claims without changing
the established material export authority.

Quantitative extensions need an independent original law, exact units, sampling
semantics and a complete state interpretation. A number attached to a machine
state is insufficient. The chosen component must declare the same quantitative
contract, its local interfaces must map to the checked graph, and the resulting
material must remain bound to that component's complete identity. Physical rate
calibration, stochastic error models and continuous dynamics would require new
explicit premises and checking relations.

The first implemented [quantitative profile](policy-quantitative-v0.1.md) is an
exact sampled reservoir. A known sample adds or subtracts one quantum with
saturation; an upward threshold crossing requests an effect. Unknown and absent
updates hold the quantity. The checker independently derives every grid transition
from the original law, binds its state and observation models to the selected
component and checked graph, and requires its fresh result before material
acceptance. The paired molecular construction remains exact under the supplied
component contract. This deliberately bounded profile connects quantitative
meaning to the existing compiler path; it does not establish physical calibration.

## What should grow next

The architecture separates frontend convenience from semantic authority. The
[stable source specification](policy-language-specification-v0.1.md), typed admission, module
interfaces, generic finite lowering, named evidence and sampled quantitative
profile now have explicit boundaries. Native execution of this implementation
batch is still pending; the session record distinguishes implemented controls
from executed checks.

The approved [next four milestones](semantic-next-roadmap-2026-10-09.md) begin
with the implemented native module-elaboration route, whose validation remains
pending. Next come bounded networks of machines and observations, explicit
target capabilities and obligation planning, and broader quantitative semantics
with experimental provenance. Separate behavioral verification of modules and
additional refinement relations for approximation still require explicit
justification. Each extension needs an
independent checker and rejection controls before its claim can reach export.
Avoid expanding the trusted core merely to accommodate frontend ergonomics or
producer search strategies. OCaml's private types support that boundary, while
the versioned wire language leaves other frontends possible.

The long-term aim is a small, stable semantic core with extensible frontends,
profiles and checked transformations. Expressiveness grows by adding precisely
specified meanings and evidence, while unsupported biology and incomplete checks
remain visible to the author.

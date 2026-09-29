# Component contracts v0.1

M4 adds immutable, content-addressed component records and a deliberately small
contract language. A successful link establishes consistency of declared
contracts and provider/resource assignments. It is not empirical evidence or a
proof that a biological mechanism implements an intent program.

## Record identity and classification

`ComponentRecord` pins a stable component ID and version, implementation role,
supported targets, concrete ports, operating domain, model/reference identities,
assumptions, guarantees, evidence references and parameter provenance. Its
SHA-256 fingerprint covers all these fields and every declared dependency,
capability and resource reservation. Arrays and maps are defensively copied;
import rejects unknown schema versions, missing fields and additional fields.
IDs and versions remain author-assigned names. Exact locks include the content
fingerprint, so reusing a version string cannot hide changed content.

The classification controls what may be claimed:

- `synthetic_model` describes a digital fixture and requires a pinned model.
- `modeled_component` also requires a pinned model; its guarantees remain
  conditional on that model and its assumptions.
- `sequence_reference` requires a pinned reference and explicit reference
  metadata. It cannot carry a dynamic port, model identity, capability,
  dependency or resource claim. The supported reference scope is
  `CDS-reference-only`, with artifact class, sequence length and unknown features
  retained in the fingerprint. A coding reference cannot satisfy a dynamic
  implementation request merely because its name describes a biological part.

Pinned identities carry kind, ID, version and content fingerprint. Evidence is a
reference to a specific artifact; its presence does not establish that a claim
was experimentally verified. Parameters carry a typed value/domain, pinned
source and provenance method. A source's identity does not establish its truth.
The initial catalog keeps FAP nucleotide/protein/source identities separate from
the synthetic operator models.

## Values and operating domains

`ValueDomain` supports exactly three forms:

1. A nonempty subset of `{false, true}`, with an explicit Boolean type.
2. A closed scalar interval `[lower, upper]` with finite numeric endpoints,
   semantic `TypeSpec`, physical dimensions and explicit units.
3. An explicit unknown domain with type, unit and reason.

No symbolic expressions, open or unbounded intervals, statistical distributions,
unit conversions, correlations or inferred biological validity are implemented.
Equal dimensions do not erase differing semantic type names. Units must agree
exactly; for example seconds and minutes require an explicit conversion before
linking. Numeric bounds alone never establish compatibility.

`domain_subset(required, supported)` returns `pass`, `fail` or `unknown`.
Boolean inclusion is ordinary set inclusion. Scalar inclusion checks both closed
bounds, after exact type and unit agreement. Any unknown operand yields unknown
unless an independent mismatch already disproves compatibility. Two equal
unknown records do not establish inclusion. Unsupported language forms are
rejected during import rather than silently approximated.

The component `OperatingDomain` is a conjunction of named value constraints.
Both sides must specify each mentioned coordinate; an omitted coordinate yields
unknown. An empty domain declares no operating coordinates for that record; it
is appropriate for context-free synthetic primitives and exact sequence identity,
not evidence of universal biological applicability. A known failure takes
precedence over other unknown constraints. This component algebra is separate
from the existing finite-history realization `OperatingDomain`.

## Ports, timing and initialization

A `PortContract` has an ID and direction, semantic meaning, exact type and units,
role, cell/contact scope, compartment, timing profile, initialization domain and
runtime domain. Known initial values must fit inside the runtime domain.

`ports_compatible(producer, consumer)` requires an output-to-input connection and
exact agreement in meaning, type, units, role, scope and compartment. It then
checks producer runtime guarantees ⊆ consumer accepted inputs, and producer
initial values ⊆ consumer accepted initial values. Equal port IDs or numeric
ranges alone are insufficient. A contact-scoped signal retains its contacted
object binding; a cell-scoped port cannot implicitly aggregate it.

The sole known timing profile is `atomic_snapshot_stateless.v0.1`: outputs settle
from the complete atomic snapshot, including initialization. `unknown` timing
cannot establish a compatible connection. Other timing profiles require an
explicit language extension. Cyclic wiring is unsupported: matching output
domains cannot establish the existence of a stateless feedback solution.
Temporal biological dynamics are outside v0.1.

## Declared obligations and composition

Dependencies name a required semantic capability, role, scope and compartment.
Provided capabilities use those same explicit coordinates. Human-readable
assumption/guarantee text is preserved but is not parsed to invent providers or
to discharge dependencies. Every required dependency in a selected component
must be accounted for by the linker. Capability grounding cannot rely on a
cycle of components asserting one another's assumptions.

Resources have a semantic resource identity, exact scalar type/dimensions,
units, role, cell/contact scope, compartment, amount and explicit reuse policy.
The provider's resource capability must match the reservation's context; a
similarly named resource in another compartment cannot imply transport.
`None` amount is unknown, not zero.
Provider capacities, assignment and lifecycle belong to the composition schema;
resource reuse is only valid when the composition establishes the required
lifetime separation. Unmeasured capacity is never unlimited capacity.

Registry selection first checks hard constraints and records every alternative
and reason. Preferences can rank only alternatives that satisfy hard
constraints. Selection pins the full frozen target and checks payload format
and declared interface compartments. Provider grounding and shared resource
accounting remain obligations of the linker; selection alone cannot establish
those composition properties.
The accepted composition records exact registry/component/model/
reference content identities and is reconstructed offline. Synthetic adapters
instantiate concrete contracts from the frozen realization request and selected
mechanism; their independent behavioral check remains required separately.

## Verification boundary

`tests/test_component_contracts.py` exercises inclusion direction, closed
boundaries, semantic type/unit differences, port meaning/scope/compartment,
initialization, unknown propagation, strict serialization, caller mutation,
content identity changes, resource unknowns and sequence/model separation.
Composition and catalog tests additionally exercise provider grounding,
resource capacities and stale locks. These are exact software checks over this
finite contract language, not biological calibration or molecular refinement.

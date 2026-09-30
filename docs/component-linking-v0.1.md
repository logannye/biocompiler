# Component linking v0.1

M4 links frozen component selections against exact offline registry records. A
passing result establishes structural compatibility under the declared component,
target, model, provider and lifecycle assumptions. It does not establish empirical
function, biological efficacy, sequence production or universal refinement.

`biocompiler.check_composition(request, registry)` independently recomputes these
checks. It accepts a `CompositionRequest`, not a producer's acceptance report.
Its `CompositionResult` has `pass`, `fail`, `unknown` or `unsupported` outcome,
explicit claim scope, requirement correspondence, provider resolutions, resource
usage, diagnostics and dependency identities. Only `pass` permits acceptance.

## Frozen inputs and authority

`CompositionRequest` contains the complete `TargetContext`, the registry lock,
selected instances, port connections, explicit supply assumptions, dependency
bindings, shared resource pools and reservation bindings. All collections are
copied into immutable structures and serialized canonically. Request identities
cover instance sources, requirement IDs and lifecycle intervals as well as the
selected records and full target context.

Every instance's component lock must equal its entry in the registry lock. The
registry snapshot, record versions/content hashes, model identities and reference
identities must resolve exactly before checking. Edited records cannot be rescued
by an old model version label. The checker reads required dependencies and resource
reservations from those records, so omitting an obligation from producer output
cannot discharge it. Every requested requirement must map to a selected instance;
the result reports only represented requirement IDs.

`result.freshness(request, registry)` compares the exact request, target, registry,
lock, identity inventory and checker version with the historical report. Passing
reports are not reusable certificates for changed inputs. Deserializing a report
never runs or replaces the independent checker.

## Port and domain compatibility

Required operating domains must be subsets of selected component supported domains.
The first contract language supports finite Boolean value sets and closed finite
scalar intervals. Missing coordinates, unknown bounds and unknown timing remain
unknown. There are no implicit unit conversions or inferred relationships between
similarly named signals.

Every input port has exactly one producer. Producer and consumer must agree on
direction, meaning, exact type, explicit units, role, contact scope, compartment
and supported timing profile. Discrete-event interfaces require an explicit
closed synthetic transition model; event and level interfaces cannot be substituted.
Producer runtime guarantees and initial values must
be subsets of the consumer's accepted values. Port compartments must exist in the
target. Cyclic wiring is unsupported by the stateless timing profile; matching
interface declarations cannot establish a feedback solution. The temporal
software profile also remains acyclic.

## Explicit providers and grounding

Provider resolutions record one of five categories:

- `encoded_here`: capabilities from a selected instance in the primary payload.
- `co_payload`: capabilities from another declared payload instance.
- `host`: a declared provider whose capabilities must also appear in the target.
- `external`: an explicit supply assumption.
- `unresolved`: missing or otherwise unestablished supply.

Payload capabilities come exclusively from the selected component records.
Callers cannot substitute their own provider capability list for an instance.
Host/external declarations retain provenance references but remain assumptions;
their presence does not convert those references into empirical evidence.

Resolution matches exact capability meaning, role, contact scope and compartment.
One matching provider may be selected automatically. Multiple matches require an
explicit `DependencyBinding`; an explicit incompatible binding fails. Required
missing, ambiguous and unresolved providers block acceptance. An optional unmet
dependency remains visible in the result without claiming that it was supplied.

Every required dependency and resource supply of a selected component is a
prerequisite for its capabilities. External providers may also declare provider
prerequisites. The checker computes a least fixed point starting with valid
providers that have no unmet prerequisites. Self-dependency, two-component cycles,
cycles through resource supplies and external prerequisite cycles cannot establish
their own guarantees. Textual assumptions or guarantees never create a provider.
A separate independent provider breaks a cycle only when the actual chosen
dependency binds to that provider.

Selected provider instances must be available for the consumer's required
lifetime. Consumed resources require availability at acquisition; reusable
reservations require availability through the reservation lifetime. Unsupported
lifecycle units cannot prove availability.

## Shared resources and lifecycle

Each `ResourceReservation` fixes resource meaning, exact scalar type, explicit
unit, amount, role, contact scope, compartment and whether reuse is permitted.
Every reservation must bind to exactly one `ResourcePool`. Pool declarations fix
one provider, resource, type, unit and capacity. The provider must have a grounded
capability matching the reservation's complete context. A cytoplasmic reservation
cannot consume an extracellular supply without an explicit supported interface.

`None` represents unknown demand or capacity. Omitted pools or capacities never
mean unlimited resources. For host resources, pool type/unit/capacity must fit the
target's declared resource assumption; missing host capacity remains unknown.

All selected instances charge the same bound physical pool. Reservations default
to simultaneous acquisition at zero with no known release. Explicit instance
lifetimes are half-open `[start, end)` intervals in seconds. A finite end releases
only reservations explicitly declared reusable; consumed quantities accumulate.
Ending and starting reusable reservations at the same instant may share capacity.
These intervals are declared schedule assumptions, not inferred timing guarantees.
Unsupported schedules remain unsupported.

The checker uses exact rational accounting of supplied decimal quantities before
comparing peak reservation with capacity. It does not use a tolerance that could
hide over-allocation. Unrepresentably large report totals remain unresolved while
the exact capacity comparison is retained. Multiple pool IDs for the same
provider/resource are unsupported because partitioning semantics are not yet
defined. Renaming a host provider does not multiply one target host's capacity.

## Checked pipeline integration

`biocompiler.run_component_pipeline(...)` extends the checked synthetic pipeline
through `Stage.COMPONENTS` with the `synthetic_components` scope. It preserves the
upstream immutable request, source and requirement correspondence, and exact
synthetic registry/model identities. The manager reruns independent acceptance;
it does not accept a serialized producer success flag.

`manager.result("components", scope="synthetic_components")` is available only
while its required checks and dependency identities remain fresh. Upstream changes
invalidate downstream acceptance. Synthetic behavior evidence remains restricted
to the independently checked finite input history and horizon; structural component
linking does not broaden that claim into molecular or empirical validation.

The [temporal component profile](temporal-components-v0.1.md) additionally
reconstructs executable models from actual locked records, wiring and explicit
observation bindings. `ComponentBuild.behavior_result` retains the independent
finite-history check separately from `link_result`. Exact source operation and
parameter correspondence remains mandatory; passing interface checks alone does
not establish preserved behavior.

Sequence reference components are separately classified. Their passing selection
or linking claim concerns only pinned CDS identity/structure and recorded unknown
features. They cannot provide dynamic ports, capabilities or biological guarantees.
The [reference construct pipeline](reference-construct-pipeline-v0.1.md) now checks
one whole selected CDS layout. The [exact-CDS pipeline](exact-cds-pipeline-v0.1.md) adds separately checked
reference emission; general molecular realization remains unsupported.

## Current human admission gate

The v0.2 linker/result checks [human use admission](human-admission-v0.1.md) from the current target and resolved component inventory. Manually supplied exact locks cannot bypass registry admission. Unsupported human use produces `human_profile_not_admitted`; other independent diagnostics are retained. The dependency snapshot includes the admission policy version, and construct/molecular verification reruns the gate. Software fixture consistency remains the supported scope.

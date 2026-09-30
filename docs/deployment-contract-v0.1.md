# Human deployment contract v0.1

M10.3 freezes delivery assumptions before future human mechanism selection.
`HumanDeploymentRequest` contains the complete `HumanBehaviorRequest` and a
versioned `DeploymentContract`. It defines required delivery context; it does not
choose a delivery technology, formulation, route, dose or clinical procedure.
The example is an artificial software fixture with explicit unresolved evidence.

## Frozen authority

The contract pins the entire human target fingerprint, exact recipient role,
DNA/RNA modality and the target's full population inclusion/exclusion claims.
Changing the target requires a newly bound deployment contract. Cell subtype,
state, tissue/disease context and target evidence remain available through the
enclosing request; they are not reduced to a population label.

Request identity includes the full behavior and deployment identities. Platform
pins, exposure bounds, timing, unintended-recipient claims, co-payload obligations
and evidence changes invalidate earlier assessments. Source locations retain
the existing inspectable-but-nonsemantic treatment. No source goal or requirement
is rewritten, and the source secretion predicate remains unchanged.

| Required declaration | Meaning and boundary |
| --- | --- |
| `platform` | `DeliveryPlatformSpec` with a versioned content pin for the platform specification, explicit modality, administration context, delivery targeting and support |
| `intended_population`, `excluded_population` | Exact target inclusion/exclusion claims, preventing independent delivery-scope drift |
| `intracellular_destination` | Declared target compartment in which the primary payload must be available |
| `exposure_window` | Finite typed time interval beginning at the deployment origin |
| `exposures` | Nonempty inventory of named scalar exposure domains, compartments and support; unknown bounds carry a reason |
| `timing` | Expression-competence onset/duration bounds, the behavior clock offset and support; missing bounds remain explicit |
| `unintended_recipients` | Explicit account of other potential recipient cells/populations and its limitations; missing characterization is not absence |
| `co_payloads` | Explicit inventory of required additional payload references, capabilities, destinations and same-cell overlap obligations; an empty inventory asserts none are declared |

Platform identity uses a pinned source/reference specification. A hash identifies
declared bytes; it does not fetch them, authenticate a review or prove delivery
performance. The example retains its exact artificial specification bytes so its
pin can be reproduced. Real platform characterization belongs to the evidence
work, not to a constructor accepting a fingerprint-shaped string.

Delivery targeting and disease recognition are separate declarations. Targeting
concerns which cells receive a payload. The M10.2 predicate concerns when the
engineered cell requests secretion. Recognition of a disease cue does not
establish targeted delivery or exclude exposure of other recipients. The schema
cannot be relabeled to equate the two.

Exposure assumptions use the existing finite scalar/unknown domain algebra with
explicit type and units. Bounds are nonnegative; no implicit unit conversion or
relationship between dose, local exposure, uptake, release and expression is
inferred. Endpoint identity includes its observable name and compartment;
duplicate aliases cannot conceal incompatible bounds. Domains are declared
requirements, not calibrated pharmacokinetics or probability distributions.

## Separate deployment and behavior clocks

Deployment time zero is the start of the declared exposure window. Expression
onset and duration are typed duration intervals relative to that origin; the
behavior's time zero occurs at the explicit `behavior_start` offset. Expression
competence means the requested behavior machinery is assumed available, not that
the secreted product is already at its active rate.

For onset interval `[a, b]`, duration interval `[d, e]`, behavior start `s` and
behavior horizon `H`, declared availability must satisfy:

```text
b <= s           latest onset is no later than behavior initialization
a + d >= s + H   earliest loss is no earlier than the final behavior observation
```

The intervals describe independent allowed ranges. These are conservative checks
over all combinations, not an inferred correlation or probability of success.
Availability is closed through its declared end, so equality is permitted.
Arithmetic compares canonical seconds using exact rational representations of
their finite decimal values; there is no hidden numerical tolerance.

The secretion activation and recovery delays remain relative to changes in the
cellular input. They cannot compensate for expression beginning after behavior
initialization. Expression may be declared to outlast extracellular exposure;
the checker assumes no decay, translation or uptake law. It does not derive
expression bounds from exposure bounds. Return to the M10.2 inactive secretion
range does not mean expression cessation, payload clearance or cell removal.

An unknown onset or duration requires a reason and yields unresolved window
coverage. A known contradiction, such as onset after initialization, remains a
failure even if another timing dimension is unknown. The existing behavior
contract still requires an initially inactive input/output and its complete
finite horizon; deployment adds no prehistory or post-horizon guarantee.

## Co-payload dependencies and supported declaration profiles

Each `CoPayloadRequirement` identifies a pinned reference, required capability,
declared destination and positive-duration overlap window on the deployment
clock. Its scope is fixed to **the same selected recipient cell** and the
dependency is required. Same-patient exposure, a shared formulation, a manifest
entry or simultaneous administration cannot substitute for same-cell coexistence.

The current checker recognizes RNA/cytoplasm and DNA/nucleus declaration pairs.
These are narrow software profiles for the current expression-oriented scope,
not universal statements about possible molecular modalities. Other declared
destinations are `unsupported`, not demonstrated biologically impossible.

Every co-payload requirement is retained but reports
`same_cell_co_payload_delivery_unsupported`, including requirements with citations.
No supported co-delivery or multi-molecule acceptance rule exists yet. The human
compile entry reruns the assessment and rejects this dependency explicitly;
caller-authored claims cannot turn it into a provider or accepted mechanism.
Undeclared destinations, stale target pins and conflicting recipient/modality
bindings reject construction/import before assessment.

## Independent assessment and integration

`check_deployment(request)` reparses the frozen request and recomputes declaration
compatibility. It takes authoritative inputs, never a producer's acceptance label.
`DeploymentAssessment.compatibility` has four outcomes:

- `pass`: this narrow declaration profile has known exposure bounds, compatible
  timing and no unsupported co-payload dependency.
- `fail`: known timing contradicts the required behavior window.
- `unsupported`: an unimplemented destination or co-payload dependency remains.
- `unknown`: required exposure or timing bounds are absent.

Precedence is fail, unsupported, unknown, then pass; all applicable diagnostics
remain retained. This checks declared compatibility only. Every assessment keeps
`biological_applicability="unestablished"` and `mechanism_selection="blocked"`,
including a compatibility pass. Every target, behavior and delivery evidence
claim remains listed as unresolved. Cited IDs must resolve against the pinned
human-target evidence inventory; citations do not become validated support.

`is_current(request)` compares exact dependency identity only. Imported results
and freshness matches are not independent acceptance; rerun the checker with
separately retained authority. `biocompiler inspect` states these limits.

Human planning and compilation without a deployment request report
`deployment_contract_missing`. `compile(HumanDeploymentRequest(...))` rechecks
deployment and preserves unresolved human-target, behavior, delivery and payload
obligations. It enables no mechanism search or sequence generation. Existing
synthetic/reference workflows retain their software-only scopes. Global human
admission at all registry, verification and export boundaries remains M10.5.

## Example, validation and completion scope

```sh
PYTHONPATH=src python examples/human_deployment.py --output generated/deployment
PYTHONPATH=src python -m biocompiler inspect generated/deployment/request-unknown.json
PYTHONPATH=src python -m biocompiler inspect generated/deployment/assessment-pass.json
```

The example starts with unestablished exposure/timing, then uses artificial bounds
to demonstrate pass, fail and unsupported outcomes. It retains every request and
assessment plus the platform fixture bytes. No delivery platform or therapeutic
regimen is selected or recommended by those values.

Tests cover exact target/recipient/modality binding, evidence provenance, unknown
and conflicting windows, deadline separation, co-payload rejection, identity
invalidation, immutable collections and strict imports. Hosted Python 3.11/3.14
checks retain existing package/test/example/CLI gates and add deployment example
inspection with archived evidence.

M10.3 completion covers this frozen contract and its checks. Biological delivery
characterization, prohibited behavior, global admission and human realization
remain M10.4–M10.5 and M11–M15 work. A valid declaration is no substitute for the
missing evidence or an implemented mechanism-selection profile.

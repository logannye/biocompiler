# Target capability and obligation planning v0.1

The explicit target planner explains a source program's first compilation blocker
before finite-history exploration. It is a bounded producer-side dry run using
fresh source admission, exact supplied model selection and independent source-to-
graph binding. A plan is inert diagnostic data. No compiler, checker or exporter
accepts a saved plan as authority or skips a subsequent check because of it.

## Installed vocabulary

`protocol/policy-target-capabilities-v0.1.json` records fifteen installed targets:
four implementation targets (legacy, finite machine, machine network, multiple request sites) and eleven
component-material targets (legacy, named instances, prerequisites, two
observations, multiple members, grounded helper, finite machine, quantitative,
machine network, sampled step reservoir, and conservative transfer pair). Each descriptor names exact request/realization profiles,
source-shape alternatives, features, limits, required original inputs, limitations
and deferred obligations. The independently retained JSON fixture and installed
native catalog must have identical complete canonical identities. Python embeds
reviewed descriptor pins and needs no source-tree catalog file when installed.

These descriptors describe bounded compiler profiles, not biological targets.
Counts and feature names are necessary descriptive conditions, not a promise that
arbitrary combinations lower. Existing exact pathways keep their original profile
identities and acceptance meanings. The older caller-declared
`BackendCapabilities`/handoff interface is unchanged.

## Python interface

Use `biocompiler.policy.planning` to prepare a typed `TargetId` request with
`PlanningLimits`, then call `PolicyTargetPlanningClient` from
`biocompiler.core_policy_planning` using a core-role `CoreClient`. Preparation
snapshots data only. It does not evaluate source validity or reproduce native
admission in Python. `PolicyTargetPlan` retains an immutable result snapshot;
accessors return fresh decoded copies. Cancellation and native protocol failures
remain transport failures, not source or requirement verdicts.

For an existing typed build request and original supplied material authority:

```python
from biocompiler.policy.planning import prepare_request
from biocompiler.core_policy_planning import PolicyTargetPlanningClient

request = prepare_request(
    build_request,
    target="network_material",
    material_request=original_material_request,
)
client = PolicyTargetPlanningClient(core_client)  # An existing core-role CoreClient.
plan = client.plan(request)
print(plan.status, plan.report["diagnostics"])
replayed = client.replay(request, report=plan.result)
```

The native producer operations are `plan-policy-target` with `{request}` and
`replay-policy-target-plan` with `{request, report}`. The replay input is the
complete retained wrapper, including its complete report and fingerprints. Replay
performs fresh bounded planning and compares the whole canonical wrapper; it is
not an independent material verifier. `bioc-verify` refuses both operations.
Capability negotiation requires the exact `policy_target_planning` profile and
`policy-target-planning-v0.1` validation scope.

## Original input boundary

The exact `biocompiler.policy_target_plan_request.v0.1` fields are:

- `schema_version`, `target`, and raw `document`;
- explicit nullable `definitions`, `realization_request`, and `material_request`;
- `limits`: `max_work`, `max_report_bytes`, `max_report_nodes`.

Raw invalid documents reach native diagnostic planning. Missing definitions may
be read from an explicitly supplied realization request. Material authority
requires that explicit realization request; the native planner does not synthesize
one. The facade may snapshot the complete nested realization request from supplied
material authority before forming this explicit wire envelope.

Supplied realization source must equal the complete original document, including
source maps and provenance. Supplied definitions must agree exactly. A material
request's complete nested realization request must equal the explicit original.
Selected targets require their exact schema/profile pairs. Model selection matches
configuration, replication and original catalog membership; a primitive name
alone cannot satisfy a model obligation.

## Diagnostic stages and statuses

The ordered stages are `source_contracts`, `operational_admission`,
`realization_inputs`, `model_lowering`, `source_binding`, `component_arrangement`,
and `provider_dependencies`. Each is `not_run`, `completed`, `blocked`, or
`not_applicable`. Implementation targets skip material stages. Legacy material
profiles skip provider-prerequisite analysis. Completed provider analysis may
retain an unresolved dependency graph and make the overall plan blocked.

The overall status is one of:

- `planned`: all applicable diagnostic stages completed;
- `invalid_source`: document decoding or source contract checking failed;
- `unsupported_target`: the installed profile lacks an interpretation;
- `missing_inputs`: original descriptors/requests, exact supplied model
  configurations, or provider dependencies are missing;
- `incompatible_inputs`: supplied profile, original identity, domain, catalog,
  component arrangement or provider relationships disagree.

The report declares `diagnostic_completeness: first_blocker`. A missing model can
hide a later unsupported construct, so a blocked plan makes no exhaustive support
or missing-component claim. Model failures name the supplied model-configuration
family; they are not an exhaustive mechanism search or biological infeasibility
finding. Unanticipated producer/checker failures escape without a diagnostic plan.
Resource and search exhaustion also escape; they never become unsupported-source
or failed-requirement findings.

Fresh source assessment retains its own complete source-contract diagnostics.
The planner's first diagnostic includes category, stage, native code, message,
source path and matching declaration identity when available. The complete original request remains authoritative. Ordered declaration
identities and paths, and complete requirement records and occurrence paths, are
retained.
A source-decode failure has no claimed complete census.

Requirements are always `unassessed`. In particular, a well-typed safety condition
that is literally false can produce `planned`; only actual later checking may
establish its failure. Each target's deferred software obligations stays
`required` at `full_pipeline`. No planning stage discharges these obligations.

## Result and claim boundary

The `biocompiler.core.policy_target_plan.v1` wrapper contains exactly
`schema_version`, `implementation`, `validation_scope`, `resource_profile`,
`request_fingerprint`, `report_fingerprint`, and `report`.

The `biocompiler.policy_target_plan.v0.1` report contains target/catalog and full
original request/document/realization/material fingerprints, fresh nullable
`source_assessment`, ordered `declarations`, `requirements`, `obligations`,
`missing_inputs`, `stages`, `selected_models`, `selected_components`, nullable
`provider_dependencies`, `diagnostics`, `claims`, and `usage`, as well as its
`schema_version` and overall `status`. Absent original R/M inputs have null pins.
Selected model rows retain node identity, exact original model pin, configuration
digest and primitive. They appear only after independent source binding. Component
rows are the exact original material catalog bindings and appear only after
arrangement and repeated independent binding succeed.

Claims are closed: planning is `diagnostic_only`, completeness is `first_blocker`,
execution is `not_performed`, preservation/requirements/resource feasibility/
material/empirical function are `unassessed`, and artifact/export are `withheld`.
The report contains no candidate, payload or accepted capability. Provider graphs
establish only bounded syntax, identity and reachability; physical capacity,
availability, mechanism function and clinical suitability are not checked.

## Resource and architecture boundary

Requests have fixed ceilings of 8 MiB, 250,000 JSON values/keys, and depth 128.
The caller sets positive limits up to 100,000,000 logical work units, 2 MiB for
the complete result wrapper and 100,000 publication values/keys. Envelope decoding
is bounded before limits are readable, then its entire measured charge is debited
to the planning invocation. Fresh admission, lowering, independent binding and
arrangement share that invocation's accounting. Existing nested limits still
apply. The older binding checker is an opaque fixed-profile pass preceded by full
input preflight; logical data-work accounting is not a CPU-instruction or wall-time
ceiling. No history enumerator or runtime is called.

Report publication conservatively reserves using the largest possible work-count
spelling, charges bounded serialization/hash passes, freezes `usage.work`, and
checks the complete actual wrapper again. Work or publication exhaustion returns
an error and no partial plan. Replay framing/comparison uses separate fixed input
and result bounds so fresh planning usage remains identical to the original run.

Only `bioc_producer_service` imports lowering. The standalone service/checker
libraries remain independent of the compiler. Planning composes existing source
and binding checks; it does not alter any exact preservation, requirement,
quantitative refinement, material or export relation.

## Validation boundary

Native controls cover network and several finite-machine shapes, complete source
and requirement census, supplied model/configuration and component identity,
source-invalid versus target-unsupported versus missing/incompatible input cases,
false safety requirements remaining unassessed, source-map/order changes, replay
forgery, exhausted resources and verifier refusal. Python controls use inert
transport replies and separately validate closed reports, pins and immutable
snapshots. Native execution and installed acceptance are separate pending gates;
see the implementation checkpoint for the checks actually performed.

# Bounded human behavior contract v0.1

M10.2 defines **reversible conditional secretion** as the first human behavior
observation profile. It specifies what a future implementation must do, using
physical readouts and explicit bounds. This is a software contract definition;
it does not select a biological cue, therapeutic product, assay, mechanism or
clinically justified numerical values. The example values are artificial fixtures.

## Source authority and supported shape

`HumanBehaviorRequest` contains the original frozen `BuildRequest` and a
`ConditionalSecretionContract`. Its target must be a `HumanTargetContext`.
The complete original intent, source locations, requirement identities, target,
parameters and provenance remain retained. Semantic identity includes the frozen
build identity and the entire observation contract. Source locations remain
inspectable without entering semantic identity, as in the existing build profile.

This version accepts exactly one in-vivo role, one symbolic goal, one scalar
external signal, one qualitative predicate (`high`, `present` or `low`), and one
ongoing condition-triggered secretion action for one named product. All nodes,
roots, roles, source IDs and product identity must match. Additional goals,
rules, explicit rate expressions, contact bindings, temporal guards, controllers,
memory and unmapped nodes are rejected rather than silently omitted.

The contract's `goal_refinement` records the proposed relationship between the
original goal and the readout, with evidence references and limitations. This is
an explicit design refinement, not an equivalence proof for free-text goals.
Goal attainment, causal relevance and therapeutic benefit require independent
evidence. The source goal is not deleted to make legacy Behavior lowering pass;
that lowering still rejects unrefined symbolic goals. This separate profile does
not broaden the legacy Behavior IR or molecular realization machinery.

## Required observations

| Declaration | Required meaning and check |
| --- | --- |
| `input_measurement` | Scalar readout for the exact source signal and role; explicit meaning, physical compartment, method/interpretation and evidence limitations; access must be `cell` |
| `input_range` | Finite typed closed operating interval that contains both qualifying and nonqualifying values |
| `predicate` | Exact source predicate ID, explicit comparison operator, typed threshold and support; `high`/`present` require `>` or `>=`, `low` requires `<` or `<=` |
| `product` | Exact source secretion product identity |
| `output_measurement` | Separate scalar endpoint measuring exported product amount/time from the selected cell; access is `external_evaluator` |
| `response` | Existing `ResponseRequirement`: exact rule/action IDs, closed active/inactive rate intervals, activation and recovery deadlines |
| `initial_range` | Required initial output interval contained within the inactive interval |
| `horizon` | Positive finite duration sufficient to permit activation and recovery intervals |
| `goal_refinement`, `response_support` | Explicit rationale and evidence limitations for the goal mapping, numerical bounds and lifecycle assumptions |

Inputs and outputs must use the same role, distinct endpoint IDs, and target
compartments that are explicitly declared. The output uses `ProductionRate`
(amount/time) per selected cell, not a population average. Bulk accumulated
concentration cannot be substituted for secretion rate by relabeling units.
An input marked cell-accessible is a requested observation; it supplies no
receptor, sensor or validated sensing model. Evaluator-only measurements cannot
drive the cellular guard. The output assay does not become feedback available to
the cell.

The existing typed scalar unit conversions are reused. Threshold type must match
the source input, and response/initial ranges must match the output endpoint.
Active rates must exceed nonnegative inactive rates. Source predicate direction
cannot be reversed by a refinement. Threshold equality follows the chosen
operator; no hidden hysteresis or inferred qualitative threshold is introduced.

## Lifecycle and timing semantics

Time begins at zero with a nonqualifying input and output inside `initial_range`.
There is no inferred prehistory. The profile uses one selected cell and a finite
declared horizon; it states no post-horizon or population claim.

Let `q(t)` be the refined predicate and `y(t)` the supplied secretion rate. At an
inactive-to-active transition at time `a`, the active range becomes mandatory at
`a + max_activation_delay`, inclusive, if the input still qualifies. It remains
mandatory while that qualifying episode continues. At an active-to-inactive
transition at time `b`, the inactive range becomes mandatory at
`b + max_deactivation_delay`, inclusive, and persists until reactivation.
Before the first activation, the inactive range is required throughout.

The latest input transition replaces the pending deadline. A short qualifying
episode may end before activation is required. At a coincident input change and
deadline, the new input takes effect first; there is no transient latch or stale
deadline obligation. Repeated samples with the same predicate value do not reset
the deadline. Zero delays enforce the new range at the transition itself.

During a response grace interval, finite nonnegative output is allowed without
an additional peak or dose bound. Earlier entry into the requested range does
not shorten the declared grace interval. M10.4 must add prohibited behavior,
transient limits and control/shutdown obligations; this version grants none of
those guarantees. Termination means return to the declared inactive secretion
range, not payload clearance, recipient-cell elimination or an external actuator.

## Bounded trace checking

`check_secretion_trace(request, samples)` freshly validates source correspondence
and evaluates the contract. Each `SecretionSample` has an explicit typed time,
input value and output value. Samples are complete, strictly increasing and begin
at zero. They assert right-continuous, piecewise-constant values up to the next
timestamp. Sparse experimental measurements alone do not justify this assertion;
no interpolation, uncertainty distribution or assay calibration is inferred.

The checker visits every supplied change and relevant deadline, including
deadlines between samples. It never extends the last sample to an unseen final
horizon. A trace must explicitly reach the requested horizon for a pass.

- `pass`: all applicable ranges/initialization constraints hold, the full horizon
  is supplied, and active, inactive and recovered states each have positive-duration
  constrained coverage. This applies only to the supplied mathematical trace.
- `fail`: an in-domain trace violates a required range, initialization or
  nonnegative output constraint. A permanently silent output fails when activation
  is exercised.
- `unknown`: input leaves the declared domain, the horizon is incomplete, or a
  required coverage phase is not exercised. An always-inactive input cannot pass.
- Malformed samples, missing measurements, wrong dimensions or invalid timestamps
  are input errors, not default zero/false values or biological failures.

Results pin the complete request, supplied trace and checker version. Imported
result labels are inspection records, never independent acceptance authority;
rerun the checker with separately retained request/trace inputs. Every result
retains `biological_applicability="unestablished"`. No model runner, molecular
candidate or empirical prediction is introduced by this checker.

## Evidence, integration and completion boundary

Each observation, threshold, response and goal-refinement claim uses the M10.1
`TargetClaim` vocabulary. Cited evidence IDs must resolve against the enclosing
human target's pinned evidence inventory. Human, non-human and software evidence
categories remain distinct. Even cited assertions stay unresolved until relevant
independent review; schema validity and a trace pass cannot certify biology.

All records are immutable and use strict versioned JSON. Unknown fields,
duplicate keys and incompatible profile versions are rejected. Contract changes
alter request identity and invalidate previous trace-result dependencies.
`biocompiler inspect` describes scope and unresolved evidence. `compile(request)`
retains the human applicability, behavioral evidence and payload admission
diagnostics and remains unavailable.

Run the source-preserving example and inspect its request:

```sh
PYTHONPATH=src python examples/human_behavior.py --output generated/human-behavior
PYTHONPATH=src python -m biocompiler inspect generated/human-behavior/human-behavior-request.json
```

The example retains the request, supplied passing trace and pass/fail/unknown
records. Hosted Python 3.11/3.14 jobs run the full existing gates, execute this
example, inspect its artifacts and retain the generated evidence. Tests cover
source mismatches, invalid observations, unit boundaries, deadline collisions,
persistence, recovery, vacuity, identity changes and unsupported compilation.

M10.2 completion is limited to this defined and tested behavior contract. The
[M10.3 deployment contract](deployment-contract-v0.1.md) adds delivery declarations
and expression-window checks without admitting delivery biology. M10.4 prohibited
behavior, M10.5 global human admission, the M11 evidence audit and M12 biological
realization remain separate work. Choosing supported
biological identities and numerical values requires that evidence; fixture values
must not be reused as human therapeutic recommendations.

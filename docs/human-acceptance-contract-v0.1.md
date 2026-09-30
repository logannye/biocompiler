# Human acceptance contract v0.1

M10.4 puts required conditional secretion and prohibited observations under one
immutable `HumanAcceptanceRequest`. It binds the complete
[deployment request](deployment-contract-v0.1.md), including its original
[source-linked behavior](human-behavior-contract-v0.1.md), to a
`HumanAcceptanceContract`. Changing any target, source requirement, deployment
assumption or acceptance bound changes request identity.

This implements a bounded observation specification and checker. It does not
select a human biological profile, predict patient outcomes or implement a
controller. All example numbers and classifications are invented software-test
values. Applicable healthy-context definitions, measurements, limits, input-loss
detection and controllability still require evidence.

## Contract and authority

The contract requires these declarations together:

| Declaration | Meaning and evidence obligation |
| --- | --- |
| Required behavior fingerprint | Exact `HumanBehaviorRequest` authority, retaining the source goal, predicate, product, ranges and lifecycle |
| Healthy-context measurement | A separate, typed, externally evaluated readout for the same recipient cell and physical target compartment; not a new cellular guard |
| Context domain and healthy range | Explicit subset defining the healthy cases being requested; other values are not automatically disease evidence |
| Background ceiling | Refines the source inactive range; applies immediately in a healthy context, after ordinary recovery, after declared input-access loss recovery and after shutdown |
| Peak ceiling | Maximum secretion rate at every observed time, including activation and recovery grace intervals |
| Maximum response duration | Longest continuous bout strictly above the background ceiling; changing cue magnitude or output magnitude cannot restart the timer |
| Input availability | How loss of cell access is observed, its required recovery deadline and explicit observability/controllability claims |
| External shutdown | Externally observed request definition, observation method, response deadline and explicit observability/controllability claims |

All rates have the source output's amount/time units **per selected cell**.
These are not bulk concentrations, doses or tissue-wide exposure bounds. The
contract covers the same product and cell as the source behavior. It does not
cover accumulated product, product clearance, bystander-cell responses or
post-horizon persistence.

Evidence IDs must resolve in the frozen human target inventory. A citation, an
assumption or a passing supplied trace never discharges the evidence obligation.
The request rejects stale behavior pins, observation endpoint aliases, different
roles, undeclared compartments, incompatible units and internally impossible
rate bounds. Context classification remains evaluator-only.

## Observation semantics

`AcceptanceSample` contains time, cell input availability, optional typed input,
output and context values, and external control status. A non-null value asserts
a right-continuous, piecewise-constant observation through the next timestamp.
The final timestamp is checked but never extrapolated. Sparse experimental
measurements alone cannot justify this interpolation.

Input statuses are distinct:

- `available` requires a measured input value. The original source predicate,
  activation deadline, inactive recovery deadline and active persistence apply.
- `cell_unavailable` requires a null input. It asserts a loss of access **at the
  cell**, with a separate requested return to background by the loss deadline.
  It does not assert a zero-valued input. Predicate timing is undefined during
  this failure scenario; reacquisition starts a new predicate timing epoch.
- `unobserved` requires a null input and means the evaluator cannot determine
  input availability/value. It produces UNKNOWN, rather than satisfying the
  cell-loss requirement or assuming an inactive guard.

The access-loss policy is an explicit extension to the observation requirements,
not an implemented source sensor or recovery mechanism. It needs a supported
mechanism mapping before human compilation can be enabled. No source recovery
coverage is credited merely for crossing an unknown or unavailable epoch.

External control statuses are `clear`, `shutdown` and `unobserved`. The first
observed shutdown request latches for the remaining horizon. Later `clear` values
and repeated shutdown requests cannot cancel it or restart its deadline.
Unobserved control produces UNKNOWN; the checker does not infer that no request
occurred. A shutdown observation establishes neither request delivery to the
cell nor causal control of secretion. `ExternalShutdownSpec` fixes actuator
support to `unimplemented`.

Initialization retains inactive input and the source initial output range, and
requires clear external control at time zero. A trace starting with unavailable
cell access, active input or an asserted shutdown violates this initialization
profile. Missing initial observations remain UNKNOWN. No prehistory is inferred.

## Conjunction, timing and conflicts

Healthy-context inactivity and external shutdown do not override a known source
guard. If a qualifying cue requires an active rate while a healthy-context or
shutdown requirement demands background, the checker reports an explicit
required/prohibited conflict, even if the output is unobserved. It never inserts
a priority rule or imagines a control actuator. Resolving such a conflict needs
revised source requirements and a separately supported implementation profile.

The background bound is immediate when healthy context is asserted. Other
background obligations begin at their declared deadlines. Peak and nonnegative
rate bounds apply throughout grace intervals. Ordinary cue changes preserve the
M10.2 rule: only predicate transitions restart deadlines; an input transition at
a coincident deadline is evaluated using the new predicate. Access reacquisition
is explicitly a new timing epoch. Clearing a lost-input condition stops that
loss-specific obligation; latched shutdown remains independent.

The checker evaluates all sample times and deadlines, including deadlines
between samples. Duration arithmetic uses exact rational values of canonical
decimal times. Continuous above-background duration is integrated across
piecewise-constant intervals. Returning to or below background ends a bout.
A bout of exactly the declared maximum duration is permitted; a longer observed
bout fails. Missing output breaks what can be inferred about bout continuity and
produces UNKNOWN, while known violations in other intervals still fail.

## Results and non-vacuity

`check_human_acceptance(request, samples)` freshly reparses authority, reruns
deployment compatibility and checks the supplied observations. PASS requires the
full declared horizon and positive-duration coverage of all six situations:
active, inactive, ordinary recovered, healthy, input-loss recovered and shutdown.
Silent/nonresponding traces cannot pass by satisfying only prohibitions. A
shutdown request only at the last timestamp cannot supply shutdown coverage.

Known failures take precedence over unsupported deployment dependencies, which
take precedence over insufficient evidence/coverage. Diagnostics retain all
categories. Missing output, context, input or control observations and out-of-domain
values remain UNKNOWN unless another known obligation fails. Co-payload
dependencies still report UNSUPPORTED. Malformed schemas, types and time order
are input errors, distinct from these assessment outcomes.

Results pin the complete request and supplied trace, checker version, horizon,
coverage and unresolved evidence. Their scope is declared deployment consistency
plus this finite mathematical trace. `is_current()` compares identities only;
imported PASS labels require fresh checking against independently retained
request/trace authority. Result metadata fixes biological applicability to
`unestablished`, actuator support to `unimplemented`, and mechanism selection to
`blocked`.

`compile(HumanAcceptanceRequest(...))` continues to reject general human payload
generation and reports missing acceptance evidence, input-loss response mapping
and shutdown actuator support. A successful fixture assessment does not enable
compilation, establish safety or show therapeutic benefit.

Run `python examples/human_acceptance.py --output generated/acceptance` for
reproducible PASS, FAIL, UNKNOWN and UNSUPPORTED fixtures. Inspect saved contracts
and results with `biocompiler inspect`. See the [rename notes](biocompiler-migration.md)
for the artifact namespace break in this release.

The [M10.6 request suite](human-profile-v0.1.md) exercises these contracts alongside deployment and admission. It includes an explicit source/healthy-context conflict, unknown measurements, missing deployment bounds and unsupported dependencies, with independent status dimensions and fresh saved-evidence comparison.

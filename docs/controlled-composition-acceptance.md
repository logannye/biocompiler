# Controlled-composition acceptance examples

This is the RC1 declarative acceptance corpus for the
[controlled-composition roadmap](car-composition-reversible-control-roadmap-2026-10-12.md).
Its machine-readable companion is
[acceptance-cases.json](../data/controlled_composition_v01/acceptance-cases.json).
The examples are independently authored artificial software inputs and expected
requirement outcomes. They are not native execution results, a biological model
validation, complete molecular authority, or a release receipt.

The corpus declares `status: declarative_unexecuted`, `acceptance: false` and
`native_status: not_run`. Its coverage explicitly remains named examples with
exhaustive domain execution pending. An expected `satisfies` value is a test
expectation, never evidence that the compiler, checker or a physical system has
passed. The checked case inventory is the ordered list of actual case IDs;
future native action, observation and file inventories are not inferred from
this list.

## Scope and authority

The source profile is
`biocompiler.policy_controlled_composition_source.v0.1`; the material profile is
`biocompiler.policy_controlled_composition_mrna.v0.1`. The separately versioned
[profile specification](../protocol/controlled-composition-profile-v0.1.json)
owns the admitted interface. These examples do not broaden an older static
expression, finite-machine or multi-member profile.

Each original scenario has one executor instance, one encounter slot, two
required RNA member IDs, and one artificial activity endpoint
`fixture.car_activity`. The external controller is an executor-local input.
Antigen is an encounter-local input. RNA and functional protein availability
are retained separately for A and B. The same-recipient declaration is a
deployment premise; it is not inferred from co-packaging, population presence or
the two-member inventory.

The source's onset, cessation and reactivation deadlines are separate from the
supplied mechanism's delays. Altering a source bound does not rewrite those
delays. A mechanism response before the deadline can satisfy the requirement;
the source does not demand one exact output trace. Exact candidate/model
correspondence will be checked separately against the supplied model authority.

All ticks and bands here are artificial. No biological numerical threshold,
clock duration, pharmacological exposure or clinical behavior is implied.
The RNA member IDs are inventory declarations, not literal molecule records.
RC2/RC4 must still provide complete independently pinned RNA and product
authority before molecular reconstruction or export can qualify.

## Frozen timing and lifecycle examples

The baseline model has onset, cessation and reactivation delays of two ticks;
the baseline source deadlines are also two ticks. Initial activity is
`background`. A qualified gate requires a live encounter, physical antigen
presence, an enabled physical controller, and both functionally available
proteins. A reported physical band is always `background` or `active`.

At the first qualified enabling tick, an onset timer begins. Activity becomes
active at its supplied completion tick if the gate remains true. Gate loss
before completion cancels pending onset. A new qualified interval starts a new
onset timer. This is cancellation of a pending transition, not a claim that an
already completed effect was undone.

Gate loss while active starts cessation. Once started, cessation cannot be
canceled or postponed by restoration or another loss. After activity reaches
background, a true gate can begin reactivation at that same tick. Restoration
while cessation is pending therefore does not permit the candidate to skip the
background interval. All source deadlines are inclusive.

The baseline history is:

| Tick | Controller | Activity example | Requirement boundary |
| --- | --- | --- | --- |
| 0 | enabled | background | Encounter starts with antigen; onset begins. |
| 1 | enabled | background | Onset remains pending. |
| 2 | enabled | active | Inclusive onset deadline. |
| 3 | disabled | active | Cessation begins; residual activity is modeled. |
| 4 | disabled | active | Cessation remains pending. |
| 5 | disabled | background | Inclusive cessation deadline. |
| 6 | enabled | background | Reactivation begins. |
| 7 | enabled | background | Reactivation remains pending. |
| 8 | enabled | active | Inclusive reactivation deadline. |
| 9–10 | enabled | active | Held-input suffix is still checked. |

The intervention cutoff is tick 6, with four held-input suffix ticks, giving
the final sample at tick 10. Physical antigen/controller/availability values
after the cutoff remain the last physical values, and no new encounter event
occurs. The suffix must accommodate cessation followed by onset/reactivation:
at least the cessation deadline plus the greater of onset and reactivation
deadlines. Every suffix sample remains part of checking. A shorter suffix is
an explicit invalid-domain perturbation; it cannot hide an open obligation.

Encounter reset clears the target-local antigen for that boundary tick and
cancels pending encounter-owned onset. It preserves the executor-local
controller, physical availability, active state and in-flight cessation timer.
Reengagement may occur at the next tick. Encounter end likewise starts any
required cessation without erasing executor state; a later start can admit
antigen at its own boundary tick. `wrong_scope_controller_reset` retains an
unchanged controller history and a candidate that fails after resetting the
wrong state owner.

The bounded encounter slot is reusable. It starts idle; `start` is valid only
while idle, including after an `end`. `end` and `reset` require a live encounter,
and their boundary rows declare antigen absent. Each start/reset establishes a
fresh antigen generation; it does not create a second concurrent slot or reset
executor state. A reset keeps the slot live, whereas end makes it idle.

The explicit supplied availability-loss contract covers confirmed physical
protein loss with the same cessation/reactivation rules. The
`protein_loss_and_recovery` case reaches activity at tick 2, loses B at tick 3,
reaches background at tick 5, restores B at tick 6 and reactivates at tick 8.
`rna_loss_protein_persistence` keeps both proteins physically present: absence
of RNA A alone does not force activity into background. Availability behavior
outside a supplied contract must remain unsupported or domain-invalid rather
than being invented by these examples.

## Evidence and expected verdicts

Physical values and evidence are different fields. Each input has an evidence
state: `valid`, `missing`, `stale`, `invalid` or `conflicting`. The activity
readout has its own evidence state. Non-valid evidence never replaces a physical
input or activity band. In particular, there is no physical `unknown` band and
missing controller evidence is not a disabled controller.

For these conservative v1 examples, unresolved demanded input, availability or
readout evidence withholds complete behavioral assurance for the trace/domain.
The independently specified physical evolution remains unchanged and can still
be inspected separately. Future reports must distinguish model correspondence,
conditional physical behavior, observation evidence and empirical applicability.

| Expected verdict | Meaning in this corpus |
| --- | --- |
| `satisfies` | The declared example meets its conditional source requirements within its stated domain; this remains an unexecuted expectation. |
| `violates` | A concrete candidate activity history contradicts a supported source requirement. |
| `unknown` | Demanded evidence or complete exploration is unavailable; no safe-OFF inference or acceptance is allowed. |
| `unsupported` | The requested endpoint or initial state is outside this first admitted profile. |
| `reject` | Original authority, material membership, deployment precondition or domain shape cannot qualify. |

Each `expected_reason` is an RC1 diagnostic intent. It is not a claim that the
current native services already emit that code. Before RC3/RC5 acceptance, map
each intent to the versioned service/monitor result and retain the complete
actual diagnostic rather than matching only a display label.

These expectations belong to the indicated assessment stage; they do not
prescribe a full pipeline's first diagnostic or top-level result precedence.
In particular, constant-ON, forever-OFF, irreversible-stop and wrong-scope
activity histories can differ from both the source requirements and the supplied
model's exact delays. Their requirement-monitor expectations remain useful
independent counterexamples, while a complete pipeline may reject model
correspondence earlier. Exact model/candidate checking must never be weakened
to force execution to reach a later expected reason.

| Case family or case | Assessment stage of the declared expectation |
| --- | --- |
| `basic`, `reversibility`, `latency`, `scope` | Source requirement monitor over the literal activity/input history; scope cases additionally identify the state-ownership requirement. |
| Confirmed protein loss and RNA/protein persistence | Conditional activity/availability requirement monitor under the explicit supplied loss contract. |
| `unknown` | Demanded evidence completeness; physical evolution/model correspondence remains a separate result. |
| `different_recipient` | Original deployment precondition admission. |
| `material` | Complete member-inventory authority checking. |
| `authority` | Original request/candidate/report/bundle identity checking at the named boundary. |
| `unsupported` | Closed source-profile admission. |
| `domain` | Complete finite-domain admission before exhaustive checking. |
| `resource` | Exploration completion/resource accounting; exhausted work cannot qualify as complete checking. |

Later joined fixtures must preserve this distinction: independently test the
monitor with its declared trace, independently test model/candidate
correspondence, and then check the complete pipeline's actual ordered rejection
path. This corpus does not assert that a fabricated trace was generated by the
supplied model or that any current producer can emit it.

## Checkable file structure

The top-level record contains exactly `schema_version`, `status`, `acceptance`,
`native_status`, `fixture_kind`, `source_profile`, `material_profile`, `coverage`,
`case_inventory` and `cases`. `coverage` contains `mode`,
`exhaustive_domain_execution` and the ordered unique `families` appearing in the
actual cases. `case_inventory` equals the complete ordered case-ID list without
duplicates or undeclared cases.

Every case contains exactly:

| Field | Declared content |
| --- | --- |
| `id`, `family`, `purpose` | Stable case identity, inventory family and explanatory intent. |
| `original_conditions` | Executor/encounter counts, endpoint, initial activity, same-recipient premise, material members, source deadlines, model delays and availability-loss contract. |
| `domain` | Intervention cutoff, suffix length, final tick and held-input suffix policy. |
| `input_history` | Every sample from tick zero through the final tick in order. |
| `candidate_activity` | One physical band and separate readout evidence state at each corresponding tick. |
| `obligations` | Explicit onset/cessation/reactivation trigger and inclusive deadline records. |
| `perturbation` | The declared negative-control target, operation and value, or three null fields when absent. |
| `expected_verdict`, `expected_reason` | Independently authored, unexecuted requirement/authority expectations. |

`original_conditions.source_deadlines` and `.model_delays` both use the exact
keys `onset_ticks`, `cessation_ticks` and `reactivation_ticks`.
In this corpus, source `cessation_ticks` explicitly assigns that same value to
all three independently named source deadlines: `controller_off_ticks`,
`antigen_off_ticks` and `component_off_ticks`. It is an equal-bound fixture
shorthand, not the wire shape of `ActivityDeadlines` and not a constraint that
those source bounds must always agree. Model `cessation_ticks` remains the
separate actual mechanism delay. Fixtures with unequal source off deadlines
belong to RC3/RC5 and must retain each independently requested value.
`domain` uses `intervention_cutoff_tick`, `suffix_ticks`, `horizon_tick` and
`suffix_policy`. Ticks are bounded nonnegative integers, never booleans.

An input row contains `tick`, `encounter_event`, `antigen`, `controller`,
`availability` and `evidence`. Events are `none`, `start`, `end` or `reset`;
antigen and availability are `present`/`absent`; controller is
`enabled`/`disabled`. Availability has exactly `rna_a`, `rna_b`, `protein_a` and
`protein_b`. Input evidence names those four fields plus `antigen` and
`controller`. An activity row contains exactly `tick`, `band` and `evidence`.

An obligation contains `kind`, `trigger_tick`, `deadline_tick`, `required_band`,
`disposition` and `cancelled_at_tick`. Kinds are `onset`,
`controller_cessation`, `antigen_cessation`, `availability_cessation`,
`encounter_cessation` and `reactivation`. Disposition is `required` or
`cancelled`; only a canceled obligation has a non-null cancellation tick.
These are source-monitor obligations, not an exact required source-output
trace or generated execution log.

Negative originals remain structurally well-formed corpus records. For example,
`incomplete_suffix` retains the complete baseline history and separately declares
replacement of `verification_domain.suffix_ticks` with one. Endpoint, initial
state and same-recipient violations likewise use explicit perturbation records.
A structural corpus checker validates the declaration and inventory; it does
not apply perturbations or evaluate the expected semantic outcome. The later
native fixture must construct and retain each actual changed original/candidate.

## Acceptance families and pending execution

The corpus includes these required contrasts:

- All four antigen/controller combinations; constant-ON and forever-OFF
  candidates; an explicit non-vacuous inactive/active/inactive/active history.
- Reversible response versus irreversible stop; restoration during cessation;
  repeated losses that cannot postpone an existing stop; direct antigen-loss
  cessation and restoration.
- Early, exact-boundary and one-tick-late responses; a tighter source deadline
  with unchanged mechanism; incomplete suffix rejection.
- Reset during onset, reset during activity, encounter end/restart and a
  candidate that incorrectly clears executor-local controller state.
- Confirmed protein loss/restoration versus RNA loss with protein persistence;
  same-recipient deployment failure; missing, stale, invalid and conflicting
  demanded evidence without physical OFF substitution.
- Missing/extra material members; foreign candidate, fully locally repinned
  foreign candidate, saved report and bundle; changed original controller.
- Unsupported killing and initial-active requests; incomplete exploration under
  a work-budget perturbation.

The current list is a source-controlled RC1 example inventory. It is not an
exhaustive state/history enumeration and does not claim that every future
native/installed mutation is already represented. RC3–RC7 must attach complete
request, model, candidate, material and result fixtures to these cases; implement
independent source/model execution and monitors; check the entire admitted
bounded domain; and retain complete actual result/action/file inventories.

Pure parsing and inventory checks establish only that this declaration is
complete and internally structured. Inert peers establish transport and
orchestration only. Native compilation/execution, installed-package testing and
release validation remain hosted and pending. Existing first-MVP/E1 artifacts
and acceptance records are not modified or reused as acceptance for this profile.

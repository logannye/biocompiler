# Executable synthetic component composition v0.1

The `synthetic_components` pipeline now accepts the explicitly selected temporal
synthetic profile. It lowers an accepted digital mechanism into locked component
records, links their declared interfaces, reconstructs a new executable mechanism
from the actual assembly, and checks that mechanism against the authored behavior
and finite input history. These are software-model results; molecular behavior
remains unresolved and human therapeutic use remains unadmitted.

```python
from biocompiler.compiler.components import run_component_pipeline
from biocompiler.registry.synthetic import TEMPORAL_PROFILE_VERSION
from biocompiler.synthesis.synthetic import SyntheticGeneratorConfig

build = run_component_pipeline(
    request, history, until=9,
    config=SyntheticGeneratorConfig(profile_version=TEMPORAL_PROFILE_VERSION),
)
assert build.link_result.passed       # declared composition contracts
assert build.behavior_result.passed   # actual reconstructed model execution
```

## Closed executable contracts

Each adapted `ComponentRecord` carries a `SyntheticOperatorModel`: the exact
operation, immutable typed attributes, ordered input-port names, output-port name
and transition-policy identity. Constants, comparison operators, positive timer
durations and optional memory expiry are therefore executable record contents,
not information silently recovered from a source graph. Duration provenance pins
the frozen realization request; permanent memory has an explicit null duration.
The policy admits only the existing synthetic operators. It cannot contain Python,
load a model plugin, fetch a URL or enable a biological implementation. Every executable
port uses the runner's canonical units (for example seconds `s`, never silently
interpreted minutes); conversion requires a separately supported operation.
Generic non-executable component contracts retain their declared-unit language.

Temporal ports explicitly distinguish `atomic_discrete_event_level.v0.1` from
`atomic_discrete_event_event.v0.1`. Events are instantaneous Boolean occurrences;
levels are right-continuous values between changes. An event can only feed a
pulse trigger, memory-set trigger, or explicit event aggregation. It cannot become
a public level readout, reset level or ordinary Boolean operand. Producer and
consumer timing profiles must match. Existing stateless interfaces remain valid;
unknown timing or a temporal component without an executable model cannot pass.

The transition policy fixes no prehistory, external snapshots before coincident
timers, acyclic causal settlement, pulse intervals with exclusive expiry, and
memory reset before set before expiry. It fixes independent contact episodes:
contact removal clears its timers/onsets/pulses; cell pulses and memories survive
until their own expiry/reset. Feedback remains unsupported. The independent
runner rejects non-finite and non-advancing deadlines.

Internal state initialization and settled port initialization are distinct.
`held_for` starts with a false output. A pulse or initially false memory may
already produce true after a startup event at time zero, so its conservative
initial output domain can include both Boolean values. A memory set only through
a fresh sustained-input timer is instead necessarily false at startup. Closed
operator contracts check conservative local runtime and initialization bounds
against their actual operation, typed parameters and input domains. Declarations
cannot exclude possible values: a held timer cannot claim an initially true output,
a constant cannot exclude its literal, and a Boolean gate cannot narrow away
possible outcomes. Unknown bounds remain UNKNOWN in linking and component behavior
acceptance. These bounds are declared sets, not trajectory guarantees or inferred
correlations.

## Independent reconstruction and acceptance

`models.components.reconstruct_component_mechanism(assembly)` reads only the
locked registry records, their ordered port bindings, actual composition
connections and the assembly's explicit observation map. It never consults a
source mechanism or calls a synthesis adapter. Every model input/output must have
exactly one observation binding. Missing models, missing/duplicate connections,
unknown operations and invalid event wiring are rejected.

`compiler.components.check_component_behavior(request, assembly, history, until=...)`
executes that reconstructed mechanism through the existing independent synthetic
runner and checks the authored contract. The runner does not invoke the Behavior
evaluator; the realization checker independently evaluates the authored Behavior
as its reference. Both active and inactive response coverage remain necessary.

`check_component_assembly` additionally rechecks authoritative source identity,
operation attributes, endpoint meanings, ordered edges, source lineage and
registry correspondence. Compatible wiring alone is insufficient: a rehashed
component with a changed timer can link structurally while failing behavioral
checking, and any changed source parameters fail exact correspondence. Imported
PASS reports provide no authority. Model, adapter, checker, catalog, request,
history and horizon identities invalidate downstream acceptance when changed.

The component stage retains its structural and behavioral reports separately.
A finite-history PASS does not establish universal equivalence, sequence identity,
biological resource sufficiency, molecular behavior or clinical applicability.
No biological resource demand is invented for these digital operators.

## Versions and validation

Component-record, port and assembly schemas are v0.2; the component linker and
link-result schema are v0.3. Adapter policy is `synthetic_components.v0.2`, and
operator transition policy and reconstruction policy start at v0.1. Previously
serialized component artifacts must be regenerated from their independent frozen
authority, not relabeled. Existing stateless and sequence-reference construction
APIs retain their semantics; non-executable component records use a null model.

Focused regressions cover actual rehashed duration and wiring mutations, startup
memory, contact loss, reset, event/level misuse, exact observation inventories,
missing models, stale locks/dependencies, immutable strict parsing and separate
source/structural/behavioral checks. Existing temporal runner tests retain their
literal exact-boundary and causal-memory timelines.

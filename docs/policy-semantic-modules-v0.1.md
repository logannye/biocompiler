# Policy semantic modules v0.1

`biocompiler.policy.modules` composes reusable policy source through explicit
nominal interfaces. A `ModuleTemplate` contains immutable ordinary declarations,
typed input and output ports, private ownership, and complete assumption and
guarantee requirements. `instantiate` records the original template and bindings;
`compose_modules` revalidates those originals and expands them into an ordinary
`PolicyProgram`. The existing compiler and independent checker receive that
complete source through their existing routes.

This is an authoring contract, not an assume-guarantee proof system. Composition
does not prove the requirements, admit an executable profile, select a molecular
implementation, or establish therapeutic or biological evidence. A source
structural check remains separate from native admission and assessment.

## Interface and ownership

Each `InputPort(name, declaration, access)` provides the complete formal
declaration, including its nominal kind, value type, exact unit/reference, scope,
contracts and effect lifecycle. At composition, formal references are relocated
through the explicit bindings, then the entire expected declaration must equal
the supplied actual declaration. Only identities and declared reference locations
are relocated; this is not structural subtyping or implicit unit conversion.

`OutputPort` identifies a complete local declaration to export. Access modes are:

| Access | Declaration kinds | Allowed operations |
| --- | --- | --- |
| `context` | Role, Subject, Encounter, SpatialScope, Clock, Channel | Nominal context references |
| `read` | Observation, StateStore, Parameter, Effect, Message | Context and expression reads |
| `write` | StateStore, Machine | Context, reads and state assignments/transitions |
| `request` | Effect, Message | Context, reads and effect requests/message emissions |

Every unexported local StateStore, Machine and Effect requires an explicit
`private=(Ref(...), ...)` entry. Other local declarations are also inaccessible
outside their interfaces. An input signature may depend only on formal input
identities. An output signature may depend only on formal inputs or other
exported identities; a private dependency cannot escape inside a public type,
reset expression or lifecycle declaration. These restrictions deliberately reject
some otherwise valid whole-program source.

Bindings name either an ordinary external `Ref`, or `ModuleOutput(instance,
port)`. `instance.output("port")` constructs the latter after checking that the
output exists. Connections require both the full relocated signature and
compatible access permissions. A read output cannot authorize a write input.
Module output dependency cycles are rejected in this profile.

Ordinary context declarations cannot manually address any instance namespace,
including exported identities. This also covers semantic references in
`Arbitration.order` and context source-map claims. To consume an output, declare
an input in a consuming module and connect it through `ModuleOutput`. Prefixing
a private identity by hand does not create an interface.

## Example

This artificial example demonstrates source construction only. It introduces no
biological operation or implementation contract.

```python
from biocompiler.policy import model as m
from biocompiler.policy.logic import TRUE
from biocompiler.policy.modules import (
    InputPort, OutputPort, ModuleBinding, ModuleTemplate,
    compose_modules, instantiate,
)

semantics = m.SemanticBundle("example", "1")
formal_role = m.Role("executor", ())
role_ref = m.Ref("executor", "Role")
seen = m.StateStore(
    "seen", m.TRUTH, m.Scope("executor", role_ref), False,
    1, "reject", "persistent", None, "reset",
)
remember = m.Rule(
    "remember", role_ref, m.Expr("rising", m.EVENT, (TRUE,)), TRUE,
    "defer", (), assignments=(m.Assignment(m.Ref("seen", "StateStore"), TRUE),),
    arbitration=m.Arbitration("exclusive", "reject", "reject", "forbidden", "none"),
)
template = ModuleTemplate(
    "remember_once", "1", semantics,
    inputs=(InputPort("executor", formal_role, "context"),),
    outputs=(OutputPort("seen", seen, "read"),),
    declarations=(seen, remember),
)
actual_role = m.Role("immune_executor", ())
bindings = (ModuleBinding("executor", m.Ref(actual_role.id, "Role")),)
left = instantiate(template, "left", bindings=bindings)
right = instantiate(template, "right", bindings=bindings)
program = compose_modules(
    "two_memories", semantics=semantics, declarations=(actual_role,),
    instances=(left, right),
)
# Separate left/seen and right/seen state, both scoped to immune_executor.
left_output = left.output("seen")
```

The typed authoring facade can provide its ordinary declarations and expressions
via `.to_source()`. Module elaboration uses no Python callbacks to supply cellular
behavior.

## Hygiene, footprints and requirements

Expansion deterministically prefixes local declaration identities with the
instance name. It rewrites nominal `Ref` values, `Arbitration.order` identities,
and source-map declaration identities. Free text, state labels, unit reference
labels, attempt-feedback contracts and `DefinitionRef` pins retain their exact
meaning. Internal scoped references relocate together, so repeated local names
in independent instances cannot capture each other.

Semantic definitions remain complete and pinned. Lexical definition parameters
are not captured by same-named program declarations. A definition that captures
program-local references is rejected rather than rewritten under stale pins.
Definitions with the same identity must have exactly equal content when merged.

`template.footprint()` recomputes conservative syntactic reads, writes and
requests from the original body and requirements. Assignments and machine
transitions count as writes; explicit state reset predicates also make their
state declaration an owner of writes. Initialization and lifetime semantics are
retained in the full declaration, rather than represented as additional action
requests. Context writes participate in the same conflict check. Two different
owners cannot write the same state, and distinct writable inputs cannot alias
the same state. Multiple local rules still require the ordinary policy's
arbitration checks. Shared effect requests require an explicit request-capable
input and, for module outputs, a request-capable output; the ordinary source
checker remains responsible for whole-program arbitration and executor rules.

Requirements must be explicitly separated into `assumptions` and `guarantees`.
An assumption must already be a complete `Requirement(kind="assumption")`.
Instantiation requires the exact original assumption records in its
`assumptions=` argument; missing, additional or changed premises fail. This
acknowledges the premise, never proves it. A guarantee retains its original
non-assumption requirement kind. Both sets are emitted, with their identities,
expressions, bounds, scope and applicability preserved under relocation. Free
text assumptions on requirements and definitions also remain explicit and
unresolved. Composition never converts a hard requirement into an assumption or
discharges a guarantee.

## Bounds and trust boundary

Records are frozen, and composition repeats validation against the original
template, bindings and complete assumptions. `ModuleInstance` has no replaceable
accepted expansion cache. Replacing or forging instance fields does not bypass
composition checks. Closed-policy snapshots reject arbitrary objects, callbacks,
cycles, malformed source fields and unsupported record shapes before expansion.

`ModuleLimits` permits lowering fixed ceilings for aggregate traversal work,
aggregate scanned bytes, depth, instances, declarations and ports. Defaults are
1,000,000 traversal units, 8 MiB of cumulatively scanned scalar data, depth 64,
64 instances, 4,096 combined declarations, and 256 ports per template. Repeated
scans consume work and bytes. The existing closed source codec imposes its own
per-document limits as well. These authoring limits are not native compiler
budget receipts. Failure returns no partial program.

Module privacy is enforced by this authoring expansion. Flattened source does
not carry a native module-interface proof or a versioned module provenance
receipt. Preserve original templates and instance bindings separately when
reproducible module composition matters. The complete flattened source is the
native authority; a caller who subsequently edits it must obtain fresh native
assessment, and cannot claim that such edits were checked by this composition.

The pure Python regression suite is `tests/test_policy_modules.py`. It compares
expansion against independently authored source examples and covers repeated
instances, output connections, private dependency and arbitration escapes,
capabilities, write conflicts, exact premises, lexical definitions, forged
records, deterministic output and bounded rejection. Native admission and
execution remain separate validation obligations.

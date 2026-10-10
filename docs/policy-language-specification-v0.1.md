# Policy language specification v0.1

This is the normative source-language contract for
`biocompiler.policy.v0.1`. The independent
[`policy-language-v0.1.schema.json`](../protocol/policy-language-v0.1.schema.json)
defines its closed record vocabulary. Python authoring and native consumers are
implementations of this contract; Python class layout does not define the
language. This specification adopts the existing v0.1 representation and source
meaning without changing any field, literal alternative, frozen document byte,
or document digest.

The language has three distinct levels: representation, source contracts, and
admitted execution. A valid representation is not necessarily a well-formed
source contract. A well-formed source contract is not necessarily executable in
a selected profile. Representation conformance does not establish therapeutic,
implementation, biological, deployment, or export acceptance.

## Representation authority

The schema's `$defs` contains all 45 record kinds. Each record has its exact
`$type` discriminator, named fields, field types, and literal alternatives. Every
field listed in `required` MUST be present, including fields whose value is
`null`, `false`, or an empty array. No additional field, unknown record, missing
field, duplicate JSON key, implicit conversion, or dynamic class lookup is
allowed. Integer and Boolean values are distinct even in host languages where
their ordinary equality compares them as equal.

There are **no wire defaults**. Python constructor defaults are authoring
conveniences that produce explicit values before serialization. A reader MUST
NOT fill an omitted field from a constructor, catalog, backend, or previous
document. A changed convenience default changes newly authored programs and is
subject to public API review, even when the wire grammar is unchanged.

The schema's top-level `oneOf` describes the three ordinary document roots:
`PolicyDraft`, `PolicyProgram`, and `BuildRequest`. Other explicitly named
protocol entry points may select a `$defs` root, for example
`CompilationSubmission`. Their presence in `$defs` does not admit them at every
entry point. `BackendCapabilities` is a caller declaration, not installed-code
authority or proof of execution.

Strings MUST be valid UTF-8. Raw floating-point JSON values and nonfinite
numbers are forbidden; exact decimal quantities use `Quantity.amount` strings.
Authoring may normalize exact decimal input before freezing. Frozen native
`Quantity.amount` MUST use fixed decimal spelling, without exponent aliases,
trailing fractional zeros, or negative zero. `Unit.scale` retains its supplied
bounded decimal spelling. The quantity's dimension, quantity kind, nominal
reference, and scale remain distinct. These numeric predicates supplement
JSON Schema; a generic JSON Schema validator alone does not enforce them.

Canonical bytes are UTF-8 JSON with object keys sorted, no insignificant
whitespace, non-ASCII characters retained, and separators `,` and `:`. Arrays
retain their complete order and multiplicity. Record field order in the
schema's `required` arrays fixes the compatible native shape table; it does not
authorize sorting declaration arrays or commutative-expression operands.

Document identity is SHA-256 of those canonical bytes after recursively
excluding keys named `source_map` and `provenance`. No other key or matching
string value is excluded. Full artifact identity includes the complete original
document. Equal document digests establish identity under this projection, not
semantic equivalence. A request's program, deployment, catalog, assurance,
definitions, and assumptions are all authoritative content. Complete definition
bodies MUST match their supplied identity, version, and digest.

The default wire limits are 2 MiB of canonical JSON, depth 64, 100,000 visited
keys/values, 262,144 UTF-8 bytes per string, 256 characters per numeric spelling,
and decimal exponent magnitude at most 1,024. Native entry points retain their
additional semantic work and envelope limits. Python's configurable ingress
limits do not change a native profile's limits or permit unsupported records.
Resource exhaustion MUST be an explicit incomplete/error result, never a
semantic success or proof that no implementation exists.

## Source meaning and obligations

The following rules bind the source vocabulary independently of an authoring
language. They preserve the interpretation in the
[authoring language contract](policy-language-v0.1.md). A backend MUST either
admit these meanings under an explicit supported profile or report the relevant
unsupported obligation. It MUST NOT weaken a declaration to make it executable.

1. **Nominal identity.** Executors, subjects, encounters, observations, effect
   declarations, dynamic attempts, and message emissions have distinct roles.
   Equal values do not establish equal identities. An encounter-bound subject
   does not become a stable cross-encounter identity. Bound quantifier subjects
   remain lexical to their predicates. Cross-subject authorization requires an
   explicit relationship contract; the existence of that contract does not
   prove its biological applicability.
2. **Evidence and access.** Observations retain observer, subject, type, units,
   clock, cell/evaluator access, coverage, coherence, freshness, and interpretation
   contract. Evaluator-only knowledge MUST NOT drive cellular behavior. Missing,
   stale, invalid, and conflicting observations remain distinguishable. Malformed
   values are errors. Availability time and observation time require their
   declared mapping; a coherence name alone cannot establish simultaneous evidence.
3. **Three-valued truth.** Logical expressions use Strong Kleene truth. Negation
   preserves unknown; `false AND unknown` is false, `true AND unknown` is unknown,
   `true OR unknown` is true, and `false OR unknown` is unknown. Comparisons with
   unavailable evidence are unknown. An unresolved `Hole`, runtime unknown, and
   an unproved requirement are separate concepts.
4. **Events and time.** Event expressions and truth guards are different types.
   `rising(C)` requires observed false-to-true evidence; unknown-to-true is not a
   rising edge. `holds(C,d)` concerns `[t-d,t]`; `recently(C,d)` concerns
   `(t-d,t]`. `followed_by` and `after` require strict order; `within` admits
   correlated completion at its anchor and through its inclusive deadline.
   Coverage sufficient for a sampled statement MUST NOT be promoted to continuous
   coverage. Silence does not suspend expiry, timers, or deadlines. Sampled
   integration retains its reconstruction, quadrature, and derived-unit obligations.
5. **State and concurrency.** State retains scope, initialization, capacity,
   overflow, lifetime, reset, and inheritance. Simultaneous events use the declared
   logical atomic-batch contract: guards and updates read pre-update state and
   writes commit under explicit conflict/arbitration rules. Declaration order
   supplies no implicit priority. A declared exclusive policy is an obligation,
   not proof that its guards cannot overlap. Unbounded capacity may be requested
   by source but MUST NOT be silently realized by finite storage.
6. **Effect lifecycle.** Request, initiation, completion, modeled outcome,
   failure, timeout, cancellation request/acknowledgment, and cessation are
   separate events. Every request creates a new attempt. Feedback MUST retain
   the matching attempt/executor/subject correlation and applicable encounter
   generation. Continuous authorization retains the originating guard and
   bindings. `defer` withholds a new action; it does not stop existing activity.
   Requesting stop/cancel does not prove cessation or reverse consequences.
7. **Coordination.** A message is emitted only by an explicit rule/transition
   emission. Each emission has a new dynamic identity, retained across retries.
   Equal content or static subject correlation cannot deduplicate different
   emissions. Sender/receiver ownership, loss, ordering, duplication,
   acknowledgment, retries, and latency remain separate contracts. A declared
   channel or population state does not prove a physical communication mechanism.
8. **Requirements.** Safety, progress, bounds, observability, external control,
   and approximation remain separate from assumptions, preferences, and unrefined
   objectives. Timed progress retains trigger, enabling guard, clock, response,
   deadline, and correlation. An absent enabled request cannot count as completed
   response. Selecting an assurance subset MUST NOT waive other hard source
   requirements. Unsupported or unknown obligations cannot become PASS.
9. **Deployment and realization.** Program behavior, human immune chassis,
   environment, RNA constraints, delivery, and implementation catalog are distinct
   records. Arrival, expression, activation, and same-recipient co-delivery are
   separate. `None` means unconstrained, not zero. Design/member/helper/ORF/product
   counts and dose are different quantities. Supplied capability or sequence
   identity does not establish a behavior, biological evidence, or human admission.
10. **Extensions.** Semantic definitions are pinned data with signatures, clauses,
    meanings, and assumptions. Arbitrary prose, operation names, imported code,
    Python callbacks, or capability labels MUST NOT supply executable meaning.
    A custom definition needs an explicit admitted interpretation. Pattern
    expansion emits ordinary source declarations and cannot silently add proof,
    completion, cancellation, or molecular guarantees.

## Binding to executable profiles

The source profile is intentionally broader than each implemented execution
profile. The following documents are normative companions for their named
profiles; their implementation or historical status paragraphs do not establish
current revision acceptance.

| Stage | Normative meaning and admission boundary |
| --- | --- |
| Source assessment | [Native front end](policy-native-front-end-v0.1.md): exact source contracts, reference/type/scope/ownership checks and complete ledgers; no execution, lowering, or artifact authorization from source validity. |
| Source execution | [Operational v0.1](policy-operational-v0.1.md): `biocompiler.policy_operational.v0.1`, pinned executable descriptors, exact phase order, scoped state/attempts, and one bounded supplied timeline. Unsupported executable constructs fail admission. |
| Original causal domain and models | [Realization contracts](policy-realization-contracts-v0.1.md): independent original request/catalog/domain/model authority; silence and eligible causal feedback retained; finite semantic bounds separated from traversal budgets. |
| Candidate preservation | [Bounded preservation](policy-bounded-preservation-v0.1.md): independent candidate execution and source correspondence at every explored prefix, all hard requirements and global nonvacuity; incomplete exploration cannot pass. |
| Staged machine execution | [Staged contract](policy-staged-execution-v0.1.md): `biocompiler.policy_staged_primitives.v0.1` and `biocompiler.policy_staged_observables.v0.1`, explicit transition/attempt correlation, atomic commit and finite capacity. |
| Components and RNA | [Component composition](policy-component-composition-v0.1.md) and its explicitly selected extensions: complete model/material/deployment authority, independent reconstruction, and fresh paired export. Behavior contracts remain supplied premises. |

For example, an admitted staged transition reads its source state, current event,
and guard at the specified microstep. Only known true enables it. A false or
unknown completion-time handoff guard does not queue a future handoff. The
original source must explicitly declare failure and timeout transitions. A
terminal transition clears retained correlation; reset/end invalidates old
generation attempts. A frontend MUST NOT change these behaviors through Python
control flow, a convenience default, or a pattern name.

A profile-specific analysis result MUST identify the complete original source,
descriptors, domain, bounds, assumptions, candidate, and selected semantic
profiles. Bounded trace agreement, bounded all-history preservation, requirement
satisfaction, material reconstruction, and empirical validity are different
claims. A general source construct outside those admitted profiles remains
representable with its obligation retained; the shape schema does not make it
executable.

Executable value positions now require scalar expressions: event equality and
event-valued effect arguments reject at operational admission, including
unreachable occurrences. Earlier admission could retain them, but evaluation
had no value semantics and failed if reached. Ordinary event triggers and
retained source requirement expressions are unchanged. This is a narrow
unsupported-input correction; it does not add event-comparison semantics. Only
previously defined executable paths retain their exact behavior: an untriggered
timeline that previously avoided an undefined value expression does not grant
that source admission under the corrected boundary.

## Conformance and version changes

`tools/generate_policy_wire_schema.py` reads the independent JSON schema and
emits the native record table. It does not import the Python SDK. Its separate
inert AST conformance check compares the Python record census, serialized fields,
primitive types, literal/union alternatives, and document alias against that
authority. Source drift fails both checking and regeneration; neither operation
rewrites the language specification from the SDK. Unsupported annotation syntax
fails closed. This source check does not certify arbitrary Python method bodies.

The public Python `serialization.schema()` remains a convenience representation
export. The conformance tests require exact equality with the normative schema
after removing only its authority identity/metadata fields. It is not a second
source of language authority. Existing source/semantic census checks and native
tests continue to cover behaviors outside annotation conformance.

`Policy_schema.language_sha256` hashes the canonical complete **representation
schema**. It is not a hash of this semantic document, an executable identity, or
an acceptance receipt. Compatibility tests independently pin the old native
shape-table payload and the 24 pre-existing frozen program/request/submission
documents, including their exact canonical bytes and identities.

A change to a record, field, literal meaning, required/optional rule, canonical
encoding, identity projection, or source interpretation requires an explicit
profile/version decision before code generation. A behavior change under an
existing profile is not a compatible clarification merely because JSON still
parses. New semantics MUST use a new versioned semantic profile or a reviewed
source-language version, with explicit admission and migration rules. Unsupported
versions MUST be rejected rather than silently upgraded.

Editorial clarification that leaves existing meaning unchanged may update this
document without changing wire v0.1. New authoring conveniences may elaborate to
the existing language, but must preserve explicit source correspondence and have
their default/expansion behavior reviewed. A future frontend in another language
implements the same specification and conformance corpus; it does not clone
Python classes as its authority.

Native compilation and executable validation remain hosted. Pure-Python schema,
mutation, and canonical-identity tests establish the stated representation
properties only. Fresh native, cross-platform, installed, and actual-main gates
remain necessary for the exact integration revision.

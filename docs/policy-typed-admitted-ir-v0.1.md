# Typed admitted policy representation

The existing policy source and operational wire formats remain unchanged. Fresh
`Policy_admission` now resolves the executable subset into
`Policy_admitted_ir` before returning its abstract admission token. This is an
internal representation change, not a broader realization or biological claim.

The typed representation separates truth predicates, integer/text/quantity
values, and event triggers. Comparisons carry same-category operands. Rules and
transitions carry event triggers and truth guards; finite-state assignments carry
the destination's scalar category. References resolve to distinct role, subject,
encounter, clock, observation, state, effect, machine, transition and parameter
symbol types with positions in the original declaration ledger. Lifecycle,
arbitration, coverage and clock alternatives are closed variants. Callers cannot
construct an admitted token, resolved symbol or expression by assembling records.

The domain elaborator is a codec and supplies no admission authority. Only the
checker runs the original source and operational admission checks and then owns
the typed result. Lowering consumes those typed declarations and reconstructs
executable operands from typed expressions, resolved references and closed
alternatives. It retains original quantity spelling, source coordinates,
contracts and other source fields. The independent correspondence checker still
reconstructs its expectations directly from independently supplied original
source; it does not call the typed encoder or the producer.

Every Requirement remains an explicit retained obligation with its complete
original body. Unsupported requirement expressions do not become executable
expressions and do not disappear. This separation is necessary because an
admitted operational program can still have unsupported assurance obligations.

Two previously late failures now receive precise operational-admission errors:
comparisons with event-valued operands, and event-valued Effect arguments. The
generic source language still permits these typed declarations, but the current
operational runtime has only scalar comparison and scalar effect-argument
execution. Previously these could pass admission and then fail scalar evaluation.
They now return `policy_operational_unsupported` at the comparison operands or
actual argument. Requirements retain their separate support assessment. This
correction adds no new executable operation. It rejects these forms even when a
particular timeline would leave their occurrence unreachable, untriggered or
suppressed; evaluating them had no scalar value semantics. Ordinary supported
scalar-program traces retain their existing meaning.

Typed elaboration and reconstruction are charged work in the same existing
logical-data-work model. Complete-source preflight precedes elaboration; field
scans, symbol-map comparisons, recursive expression construction, nominal unit
comparisons and reconstruction searches charge the enclosing invocation. A
callback failure stops the operation without returning a partial typed program.
New work changes measured usage and may exhaust a previously sufficient work
budget; it does not reduce semantic bounds or reuse an old acceptance result.
Exact revision and fresh hosted receipts remain required.

The native `test_policy_admitted_ir` suite uses the existing operational,
staged-regimen and implementation-binding fixtures as independent source
authority. It checks exact original declaration reconstruction, resolved symbol
indices, producer-independent correspondence, unsupported-obligation retention,
typed rejection, source-valid early event-as-value rejection, and terminal
metering failures. Existing execution, generation, realization and export suites
remain required. No local native execution is part of this source change.

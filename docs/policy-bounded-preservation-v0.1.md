# Bounded implementation preservation and requirements

This is the source specification for the initial SM-04 implementation. Native
validation and complete hosted acceptance remain required. A checked
implementation is an intermediate compiler result; component, material, target
and export acceptance remain separate obligations.

## Producer and independent authority

`Policy_implementation_lowering` proposes a typed primitive graph and source
anchors from independently admitted original inputs. It chooses only exact
models in the supplied library and original catalog membership, using stable
ordering for eligible layouts/models. It neither invents a missing model nor
calls the graph-binding checker to generate its proposal. The initial family is
the one/two-rule exclusive family documented in
[primitive execution](policy-primitive-execution-v0.1.md).

`Policy_preservation_check` freshly repeats source admission and independent
source-to-graph binding. Proposed anchors and producer identities are untrusted.
The checker links source semantics and candidate execution but imports no
producer. The candidate runtime imports neither source semantics nor a source
trace. Changing the producer cannot change these acceptance rules.

## Complete finite-domain traversal

The original operating-domain contract defines all eligible causal input
histories, including silence. The checker uses depth-first enumeration with no
state merging, branch pruning, representative sampling or candidate-dependent
input choice. Only actual source-created attempts extend the eligible feedback
alphabet. A fixed injective creation correspondence translates those inputs to
the candidate, including feedback about previous generations.

Every prefix independently replays source meaning, executes the actual candidate
graph, checks exact observable correspondence and monitors original hard
requirements. Microsteps and clocks are exact; this profile introduces no hidden
latency tolerance. Both missing and extra observables reject. A terminal history
includes every tick through the declared inclusive horizon. An impossible
reachable continuation, violated logical source bound, resource exhaustion and
behavioral counterexample have distinct diagnostics. None may disappear from
the explored domain.

The receipt records started/matched prefixes, transitions, completed histories,
traversal identity, actual resource use and the exact stopped input prefix when
one exists. Complete coverage is necessary for preservation PASS. A small,
separately authored domain is valid authority for its own request; it cannot
substitute for complete coverage of a larger original domain.

## Independent requirement monitoring

`Policy_requirement_monitor` reconstructs requirement outcomes from original
requirements and actual candidate ports, events, actions and state. It does not
consume the source evaluator's requirement ledger. Original binding fixes which
ports denote source expressions; actual edge outputs supply rising events.

The phase schedule handles incoming events and enabling conditions, opening
obligations, pre/post-atomic responses, settled safety samples and deadlines.
Reset/end closes affected pending obligations without inventing a response.
Uncertainty, no trigger, unsupported properties, failure and incomplete horizon
remain distinct. At each completed history, the whole-domain checker also
compares the independently produced requirement ledger with fresh source
evaluation after normalizing only the fixed event/attempt identity map.

Global acceptance requires every original hard requirement to pass. An unknown,
unsupported or failing history prevents that result. A progress requirement may
be unexercised in individual histories, but needs a real eligible trigger and a
passing witness somewhere in the complete domain. Safety needs relevant samples
and both active and inactive effect witnesses. Independently of requirement
kind, this first compilation profile also requires an actual created attempt and
active/inactive program prefixes. A never-activated implementation cannot earn
compilation acceptance from vacuous requirements.

Requirement failure does not erase otherwise complete preservation evidence:
an implementation can faithfully execute a source program whose original hard
requirements fail. The returned checked-implementation value is absent in that
case. Unsupported requirements preserve their original identity and meaning;
unsupported monitor results never become PASS.

## Resources and immutable acceptance

Original request budgets bound total prefixes, transitions, work and retained
trace items. Explicit execution limits separately bound each source replay,
candidate path, monitor and publication. Source replay charges repeated work;
failed unreported calls consume their reservation. Candidate/monitor successor
states are immutable, and exhausted calls cannot partially advance a branch.
The checker reserves execution capacity, accounts for live ancestor traces and
retained witnesses, and charges serialization visits. These are conservative
profile counters, not wall-clock complexity proofs.

Resource limits affect whether checking completes, never which input histories
the request means. If even a failure receipt cannot fit its publication/work
allowance, checking raises an explicit diagnostic and returns no checked value.
Reports cannot deserialize into accepted state. Only a fresh complete invocation
can return the abstract `checked_implementation` value, with original authority,
complete preservation, all hard requirements and nonvacuity evidence bound
together. Material and export fields remain unassessed/withheld.

## Required controls

Tests pair frozen graphs with independently authored complete finite domains,
literal traversal censuses and explicit positive/unknown/failing requirements.
Controls cover silent expiry, correlated feedback/deadline ordering, old attempt
identity, reset/end, uncertain enabling, no-trigger and no-effect vacuity,
unsupported properties, original-input edits, candidate corruption, resource
exhaustion and publication failure. Existing source and primitive mutation suites
remain required. Hosted tests and full installed release gates retain their
existing scope; source/static evidence does not close them.

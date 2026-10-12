# Controlled composition operating domain v0.1

This is the closed RC3 input-domain specification, frozen before its decoder.
It refines sections 4, 5 and 7 of [the controlled composition specification](controlled-composition-v0.1.md).
The domain is original supplied authority. Enumeration is not a requirement
verdict, mechanism execution, material proof or biological evidence.

## Wire inventory

Every object has exactly the fields below; unknown fields and duplicate keys
are rejected. Names are nonempty strings of at most 256 UTF-8 bytes. Integers
are JSON integers, never floats, strings or Booleans. Array order is retained.

The root fields are `schema_version`, `profile`, `clock`, `executor`,
`encounter`, `inputs`, `source_deadlines`, `intervention_cutoff_tick`,
`horizon_tick`, `suffix_policy`, `initial`, `physical_factors`,
`evidence_factors`, `lifecycle_factors`, `fixed_inputs`, and `limits`.

* `schema_version` is `biocompiler.policy_controlled_composition_domain.v0.1`.
  `profile` is `biocompiler.policy_controlled_composition_mrna.v0.1`.
* `clock` is `{id, resolution}`. Resolution is the complete original
  `{"$type":"Quantity","amount":DECIMAL,"unit":UNIT}` record. UNIT has
  exactly `$type`, `id`, `dimension`, `quantity_kind`, `scale`, `reference`;
  its type is `Unit`, dimension `time`, kind `duration`, reference null, and
  amount and scale are positive exact decimals. The complete nominal record
  must equal the admitted source clock record; conversion/rounding is absent.
* `executor` is `{role, identity}`. `encounter` is
  `{slot, declaration, subject}`. All five identities bind to the independently
  admitted source/context supplied by the caller.
* `inputs` contains exactly six rows, in order: `antigen`, `controller`,
  `rna_a`, `rna_b`, `protein_a`, `protein_b`. Each row is
  `{key, reference, scope, freshness_ticks}`. A reference has exactly `$type`
  (`Ref`), `id`, and `kind`. The first two kinds are `Observation`, RNA kinds
  are `MaterialMember`, and protein kinds are `Parameter`. Antigen scope is
  `encounter`; every other scope is `executor`. Availability does not invent
  additional source observations. Freshness is an integer from 0 through 64.
  Antigen/controller freshness must equal their original source observation
  bounds; availability freshness remains explicit supplied domain authority.
* `source_deadlines` has exactly five positive integer fields: `onset_ticks`,
  `controller_off_ticks`, `antigen_off_ticks`, `component_off_ticks`, and
  `reactivation_ticks`. Each is at most 64 and equals its admitted source bound.
* `intervention_cutoff_tick` C is 0..32; `horizon_tick` H is 1..64.
  C < H and H-C is at least
  `max(controller_off, antigen_off, component_off) + max(onset, reactivation)`.
  The source horizon must equal H. Tick zero and every suffix tick are included.
* `suffix_policy` is `hold_last_physical_inputs_no_encounter_events`.
* `initial` is `{physical, evidence}` and describes the predecessor of tick 0.
  The slot is initially idle, generation 0. Antigen must be absent. Each initial
  evidence record must be missing. Initial activity is outside this domain;
  the activity profile separately requires background.
* `limits` is `{max_generations, max_prefixes, max_transitions, max_histories,
  max_work}`. All are positive integers. Profile ceilings respectively are
  16, 1000000, 1000000, 65536 and 16000000. These are explicit finite software
  limits, not statements about clinical operating coverage.

`physical` is an object with exactly the six input keys. Controller has value
`disabled` or `enabled`; all other factors have value `absent` or `present`.
RNA absence does not change either protein factor. There is no activity or
unknown physical value in this grammar.

`evidence` is an object with exactly the six input keys. Each value is
`{status, observed_tick, generation}`. Status is `valid`, `missing`, `invalid`
or `conflicting`. Missing requires both other fields null. Otherwise
`observed_tick` is an integer from 0 through the frame tick. Executor evidence
has null generation. Antigen evidence has an integer generation from 0 through
the current generation. A future generation is a contradiction. Generation 0
identifies the initial idle context and is never usable live antigen evidence.
The effective status of a nonmissing antigen record is stale if the slot is
idle, its generation differs from the live generation, or its observed tick
precedes that generation's start. Any nonmissing record is stale if its age
exceeds its declared freshness. Otherwise its supplied status is retained.
Staleness is derived, not authored as a physical value. Raw evidence is always
retained. Old-generation records remain unusable evidence; they do not rewrite
physical antigen, controller, protein or activity.

## Factor grammar and tick order

`physical_factors` contains rows `{input, ticks, values}`. Each input appears at
most once; ticks are nonempty, strictly ascending, unique integers in 0..C.
Values are a nonempty unique list in that input's physical alphabet. At each
listed tick, choices are the held value first and then authored values in their
original order, with equal values deduplicated. Unlisted inputs hold.
There are at most six physical factors, six evidence factors, 33 lifecycle
factors and 65 fixed frames; their per-tick uniqueness further bounds them.

`evidence_factors` contains rows `{input, ticks, statuses, age_ticks}`. Each
input appears at most once. Ticks are nonempty ascending integers in 0..H,
including explicitly declared suffix refreshes. Statuses are a nonempty unique
list from the authored status alphabet. Ages are nonempty ascending integers
in 0..64; every age must be at most every listed tick. At each tick the held raw
record is first. Then, in status/age array order, each nonmissing status is
sampled at `tick-age`, with current generation for antigen and null generation
for executor inputs. Missing contributes one canonical null/null record. Equal
records are deduplicated. Stale records are retained as choices.

`lifecycle_factors` contains rows `{ticks, actions}`. Ticks are nonempty
ascending integers in 0..C and cannot overlap another lifecycle factor. Actions
are a nonempty unique list from `start`, `end`, `reset`; implicit `none` is
first. Start is eligible only while idle; end/reset only while live. This sole
lifecycle eligibility rule is structural and independent of a candidate,
activity, evidence or requirement verdict.

`fixed_inputs` contains complete rows `{tick, event, physical, evidence}`, in
strictly ascending tick order. Event is `none`, `start`, `end` or `reset`.
Its tick cannot overlap any factor tick. A fixed row supplies exactly one
original restriction; it is not expanded with implicit hold alternatives.
Rows can therefore express a fixed enabling intervention as well as a suffix
evidence refresh. Reports retain the fixed-row and all factor counts, so a
fixed demonstration cannot be represented as broader varying coverage.

Lifecycle is applied first. Start/reset increment generation and record its
start tick; end sets the slot idle. Reset remains live. End/reset set antigen
absent before physical choices; their resulting boundary must keep antigen
absent. Executor factors and evidence are held, including across end/start.
The physical factor Cartesian product follows in the six-key inventory order;
the evidence Cartesian product follows in that same order. Every distinct
declared combination is retained. Idle antigen present, an ineligible fixed
event, a future timestamp/generation, or a boundary antigen contradiction
invalidates the domain, even if only one reachable prefix exposes it. These
contradictions never prune a branch or create a completed receipt.

After C, lifecycle must be none and all physical factors must hold their C
values. Evidence holds or changes only as explicitly declared. A fixed suffix
row that changes physical state on any prefix is a contradiction. A generation
limit exceeded by an eligible declared start/reset is a diagnostic, not a rule
for removing that history. Arbitrary source output or activity state never
influences domain choices.

## Native boundary and accounting

`of_json` bounds and decodes original JSON, preserving exact bytes semantically
through `to_json` and a canonical full-domain fingerprint. The input preflight
allows at most 1 MiB, 100000 nodes and depth 32. `validate_for` compares every
typed binding, complete clock record, all five source deadlines and horizon
against independently admitted caller inputs. It cannot establish those inputs'
source authority itself. The validated cursor carries only environment state.

`choices` is lazy and complete for one prefix. `advance` accepts only a batch
issued for that exact domain/prefix; batches cannot be substituted between
domains or prior states. A history contains exactly H+1 frames. Enumeration is
depth-first in deterministic choice order. `prefixes` includes the initial
pre-tick-0 cursor and each advanced cursor; `transitions` counts traversed batch
edges; `histories` counts completed H+1-frame paths. Every original factor
combination is accounted even where later fixed rows converge to equal states.

`enumerate` returns `Complete`, `Exhausted`, or `Cancelled`, each with usage.
Exhaustion and cancellation never mean admission or PASS. A contradiction or
callback failure propagates and prevents a complete result. History callbacks
are provisional until the entire traversal completes. No accumulated partial
history can substitute for a universal check.

Optional `charge : int -> unit` callbacks on decoding, validation and traversal
debit the enclosing operation before bounded work. Enumeration also enforces
its own cumulative work/prefix/transition/history limits and checks cancellation
at every charged step. Enclosing budget/guard exceptions propagate unchanged;
local domain limits do not bypass the enclosing whole-operation budget. A
caller manually consuming choices must supply its own budget and cannot claim
complete enumeration from a stopped sequence. A completed domain receipt still
requires separate source, model, material and requirement checking.

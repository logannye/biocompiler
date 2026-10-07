# Metered selection generation: narrow next increment

Read-only design against `af062c5505ffda0b0746115bb974abf5b0e612d1`.
Not implemented or accepted. No native execution was performed for this review.

## Reuse the current path

`Policy_component_material_producer.compile` already performs source admission,
operational lowering, realization admission, implementation lowering, component
arrangement, template construction, and the independent child service check.
Extract only its candidate-producing portion as `construct_candidate`, keeping
the existing six-field candidate JSON and old compile operation unchanged.
Selection calls that candidate-only function for every original, then invokes
the independent outer checker once. Do not call the old child compile service
as a generation shortcut: that would perform extra checks and publication on
separate owners before the mandatory complete outer census.

Existing design context: `generated/selection-service-design/scope-and-publication-proposal.md`,
especially its deferred-compile section. Its original check/replay/export work
is now source-implemented; that draft's implementation-status introduction is
historical. The generation warning remains applicable.

## Minimal service interface

Prefer a producer-free, Core-only `prepare_generated` entry in
`Policy_component_selection_service`:

```ocaml
val prepare_generated :
  executable:Protocol.executable -> request:Protocol.request ->
  produce:(charge:(int -> unit) -> R.t -> Json.t) ->
  Json.t * (Json.t -> unit)
```

It accepts only `compile-policy-component-selection`, requires `Core`, and
decodes exactly `{request, limits}`. It creates the same original-bound scope
as the current service; the callback receives only its count-only outer charge
function and the immutable complete typed original. Returned JSON is untrusted.
Decode it with the existing neutral candidate codec, call `check_in`, and reuse
the current wrapper and one-shot actual-frame guard. Factor the common internal
continuation from `prepare`; never fabricate a check request or reset the scope.
This avoids adding a raw budget getter or new public scope lifecycle state.

Core's new `Producer_service.scoped_handle` handles compile and delegates all
other requests to `Base.scoped_handle`. Core's entrypoint supplies that handler;
Verify remains linked only to the existing producer-free service. Advertise a
separate Core producer capability/profile, preserving the existing three-route
selection verification profile. The Python client adds an explicitly negotiated
Core compile method; fresh Verify check/replay/export continue unchanged.

## Metering closure that must be implemented

Use optional count-only callbacks with no-op defaults, retaining every old hard
cap and diagnostic. Define logical work as explicit traversals, comparisons,
search attempts and scalar/serialization bytes, not elapsed time or an estimate
of CPU instructions. Precharge before variable-size allocation or a bounded
decoder/encoder pass; charge every retry and repeated occurrence.

For functions with only labeled arguments (`Policy_admission.admit`,
`Policy_realization_admission.admit`, implementation `lower`), prefer a separate
`*_metered ~charge` entry and an old-signature no-op wrapper. Adding an optional
argument without a final positional argument risks OCaml's unerasable-optional
warning and changes old call behavior. Positional APIs can use `?charge` directly.

| Existing source | Required charging |
| --- | --- |
| `checker/policy_check.ml` | Forward the existing 8M local analysis counter; cover index/definition construction and canonical definition/report passes outside that counter. Preserve its local 8M ceiling. |
| `checker/policy_admission.ml` | Document redecoding, source assessment, declaration/descriptor maps, expression and binding recursion, list searches, complete comparisons, coherence/arbitration scans, and report hashing. |
| `checker/policy_correspondence.ml` | Repeated admission, complete-value equality, per-declaration/operand correspondence, and candidate fingerprint. |
| `checker/policy_realization_admission.ml` | Both repeated admissions through correspondence, assurance/catalog/model membership traversals, complete reference comparisons, domain validation and report digests. `require_model` must propagate the same meter. |
| `domain/policy_operating_domain.ml` (`validate_for` only) | Domain/behavior compatibility loops and its complete behavior/domain fingerprint. No exploration or executor work is added to the producer. |
| `compiler/policy_lowering.ml` | Every declaration and operand visited/copied; complete derived behavior decoder and descriptor digest. |
| `compiler/policy_implementation_lowering.ml` | Every attempted layout, library scan/model comparator, declaration lookup, expression recursion and memo key, graph/ledger append, wiring/port search, requirement walk, sort comparator, generated graph/binding decoder and fingerprint. Failed-layout searches still consume work. |
| `compiler/policy_component_lowering.ml` | Forward the existing 1M search counter and retain it. Charge currently uncovered rule-list/index scans, key/signature construction before encoding, every matching/backtracking/comparison step, rewritten graph/binding/assembly objects and decoders. |
| `compiler/construction_producer.ml` + `recoding_producer.ml` | Keep the existing 50M construction budget, residue/staging caps and protected exhaustion. Add a narrow optional charge callback bridge so existing actual work charges debit the selection scope without exposing its raw owner. Account for reserve-output/staging traversals and final content serialization as real additional passes; a final-size charge alone is insufficient. |
| Component/selection producer | Complete per-child candidate serialization, ID ordering, raw candidate inventory inspection, length/predicate comparisons, rank/ASCII-ID proposal, outer candidate construction/decoding. |

The operational admission is currently executed **three times per child**:
direct admission, realization admission, and realization's correspondence check.
Do not accidentally count just one. The optional callbacks propagate through
these existing calls; no assessment/report reuse is needed for this increment.
Bounded preflights before opaque decoders are legitimate declared data-visit
passes; they do not cover variable-count searches or recursive generation loops.

The construction budget already wraps all work/output failures in its private
`Budget_exhausted` exception and restores the original diagnostic at the public
entrypoint. Preserve that mechanism so the outer callback's work exhaustion is
never converted into a recoverable malformed-material diagnostic.

## Original budgets, failures and proposals

Generation consumes the same **1B outer** and **17B total** owners as checking,
formatting and actual-frame admission. The independent checker still reserves
each child's full original `max_work` before its fresh check, without refunds,
clipping or use of serialized child usage. Generation must not consume or
rewrite those original child-check allowances. Smaller supplied outer totals
and publication ceilings remain binding. Existing v0.1/v0.2 publication limits
and individual frame/input bounds remain unchanged.

Generate in ASCII-ID order, retaining the complete original raw array and every
child request. Propose a winner using untrusted produced material lengths and
the existing rank/ASCII-ID rule; only the later private child capabilities can
validate those lengths and authorize the winner. Never check once with a null
winner and reopen a scope to check again. Any unsupported generation or resource
exception aborts the complete invocation; no omitted child becomes ineligible.
If construction returns an incomplete candidate, retain it in the complete
census and let independent checking reject it. If all children pass but none
meets the predicate, return the existing no-eligible report with no artifact.
Compile itself does not export.

Keep `usage.charged_work` as the existing checking-phase delta so fresh check and
replay of a produced candidate remain byte-identical. Generation still debits
the private shared scope before that phase and cannot disappear from final
admission. Document that distinction rather than adding caller-reported usage
as an authority or changing old report identity.

## Coherent files and distinguishing controls

Production changes are the listed passes and their `.mli` interfaces; the
candidate-only component producer; a small new selection producer; the shared
selection service continuation; producer scoped dispatch/Core entrypoint;
separate producer capability; and the thin Python compile adapter/helper.
Update closed inventories and witnesses after independent review of the exact
additive/shared-source projection. No new schema for child candidates or broad
component/material redesign is needed.

Required controls: absent callback preserves old candidate bytes/diagnostics;
injected failure before each pass's dynamic allocation/search never publishes;
late failed-layout/backtracking work is not refunded; construction's local50M
and arrangement's local1M remain binding with a larger outer allowance; smaller
outer/total caps fail across generation plus checking plus final frame; caught
exhaustion remains terminal; identical deterministic output regardless of input
array order with distinct original fingerprint; every loser generated/checked;
missing model/invalid losing material/no eligible cases; exact17/18-RNA winners;
Core compile equals fresh Verify check on the produced complete candidate;
loser edit invalidates saved replay despite unchanged winner; and Verify compile
remains unsupported with a producer-free dependency graph.

The current Core-compile-unsupported witness and Python compile-absent assertions
must be explicitly superseded only for the new Core producer API. The Verify
negative and all current check/replay/export controls remain. Treat this as a
reviewed contract change, not an automatic re-pin to make coverage pass.

No architectural blocker was found. The important scope constraint is that
candidate factoring alone is not a complete metered compile implementation:
the admission/correspondence/decoder and serialization passes above are part of
its accounting boundary. Keep the public compile route withheld until that
closure and the shared-scope failure controls pass hosted validation.

## Independent review refinements

The meter has two deliberately distinct paths. Forward every **existing** local
charge to the new outer callback while preserving its current local accounting.
Charge newly covered staging/output/serialization traversals and other uncovered
visits **only** to that outer callback; do not also introduce new debits against
the old construction50M, arrangement1M or source-analysis8M local counters. With
no callback, the old thresholds, diagnostics and behavior remain unchanged.
With a callback, those same local caps remain active alongside the additional
outer/total limits. No child-check allowance or conservative reservation changes.

For array permutation controls, generated candidate ordering and the selected
winner may remain identical because generation/evaluation use ASCII-ID order.
The complete original request preserves its authored array order, so its request
fingerprint and the full result wrapper must change; the corresponding invocation
and assessment bindings must follow that changed authority. A saved wrapper from
the other original order must fail replay even when candidate and RNA are equal.

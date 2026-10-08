# Core architecture implementation checkpoint

Checkpoint: 2026-10-08. Continue the approved
[ordered implementation plan](core-architecture-session-priorities-2026-10-08.md).
The user authorized working through its items, keeping native builds hosted and
local feedback focused. Do not restart completed architecture work or transfer
acceptance between revisions. The workspace root contains separately owned
checkouts; unrelated researcher-authoring/encoding work remains separate.

## Current source and validation boundaries

| Increment | Checkout under `work/` | State at this checkpoint |
| --- | --- | --- |
| Named component instances | `core-instance-composition` | PR99 at `a38174303f0806a84c4800df0040041c96190e5e`; integration run `37799164508` remains active; Python 3.14 unit shard 0 failed stale public API inventory (14 failures, one error). Correction is being reviewed separately; healthy jobs continue. |
| Provider prerequisite closure | `core-prerequisite-closure` | Development revision `a34ebd6bc557b52e9e253e8fe7e4fbce8ae1f9a4`; run `37798264346` and independent inert artifact audit passed (35 native suites, 182 SDK observations). |
| Two independent observations | `core-two-observation-composition` | First development run `37801697083` at `22e1f0ed1` compiled and passed 35 of 36 native suites. One new negative control expected the wrong rejection stage; corrected source `6feb332688ec838031e4cab9de2f2ee498c7f4b5` has passed the native step and is executing eight SDK campaigns in run `37803803945`; independent audit remains pending. |
| Multiple products/members/helpers | `core-multi-member-composition` | Two-product/two-member domain, lowering, checker, SDK and independent fixtures/campaigns are present; independent source review and local static controls passed; preparing the first hosted development run. No native validation or acceptance. Helpers follow this subincrement. |
| Modular assurance | Not yet created | Measurement and checked proof-rule design remain outstanding. |

The earlier instance development revision `c0366fc92` passed run `37788462656`:
33 native suites and all 156 observations across six SDK campaigns. Independent
inert audit checked complete original authority, exact logs and both new-profile
paired archives. This is development evidence for that revision only.

Instance run `37792192989` at `4b5d0b535` passed both full 173-suite native jobs but
failed the direct-core capability census on both platforms. The current PR fixes
the missing instance scope/profile census and adds preflight mutation controls.
New synthetic merge `fc21eccab03c74897c3d36133fd336652d5f7a21` has parents main
`e253ed5b3370af9a7d8b9ba96af2e7f8f025798a` and source `a38174303…`, with matching
source/merge tree `00bf061709bbb28825e3456863ded74b07451e79`.
Retained evidence is under each checkout's `generated/hosted-feedback/<run>/`.
Complete installed/cross-platform gates, independent audit, normal merge and
fresh actual-main validation remain required.

The first prerequisite run `37796094341` failed an OCaml documentation warning
before native testing. Its corrected run is separate; preserve the original
failure evidence. The correction also updates independent capability censuses.

## Two-observation batch

The [new contract](policy-two-observation-composition-v0.1.md) defines exact
request/context/binding profile pairing, two ordered source/bank identities,
original input/provider mapping, independent freshness and uncertainty, and the
unchanged whole-program/private-closure/material acceptance chain. Its domain-only
fixture retains all nine source inputs. A/B declarations independently specify
36 histories, 42 transitions, 43 prefixes, 24 obligations and the exact artificial
17-base RNA. The 36-cell uncertainty table, timing and initial binding mutations passed in
run `37801697083`. The same-coherence negative control was correctly rejected by
`policy_operational_unsupported` before lowering; its expected diagnostic is
corrected without changing production semantics. The corrected run has now completed its native step and is exercising the SDK campaigns; complete retained evidence still needs independent audit. The original failure
log and digest-verified inert archive are retained.

Local feedback includes both CI-pinned strict typing gates (34 core and 31 policy
modules); 58 new SDK/transport/evidence mock tests and 14 capability controls;
84 existing SDK regressions; 54 development/bundle orchestration tests; 45 CI/plan
tests; four historical source-scope tests; and 35 rule-inventory tests. The full
33-test dependency-boundary run found one stale suite-count expectation, corrected
and passed in a focused rerun. Other boundary cases passed in that run.

The rule inventory adds the 24th component family with 95 production sources
and 99 witnesses. Projection preserves the exact previous 23-family metadata
hash `8da4c54d70fa5ceec3c5f50fef539e80681bd7f8dabb1e0e5a21d786ec35f4b1` and all
original 62 rule meanings. Migration inventory has 3,847 entries. Historical
workflow sources remain unchanged; six excluded SDK source hashes were reviewed
and updated. These are static/source checks, not semantic acceptance.

Required hosted development is 36 native suites and eight complete SDK campaigns
(208 observations), using one build and two bounded worker lanes. Required full
native inventory is 176 suites, 182 executable bundle members and 26 distinct
original fixtures. Sparse local checkouts omit much of the historical corpus;
the full filesystem fixture-wiring check must run against the complete hosted
checkout. Do not silently treat sparse missing fixtures as passing.

## Next work

Finish and audit each active hosted gate, preserving exact source and run identity.
Fix concrete failures in coherent batches. Continue the separately versioned
two-product/two-member design, then one explicitly grounded static helper, with
per-member construction, recipient/availability, shared capacity and transport
contracts. Co-delivery alone is not a cross-member transport proof. Dynamic helper
behavior requires an explicit preservation relation. Measure whole-program
checking before selecting a narrow modular assurance rule; saved PASS records
cannot replace fresh proof checking.

## Multi-member work in progress

The [bounded contract](policy-multi-member-composition-v0.1.md) specifies exactly
two distinct fixed source products, the existing staged machine, two complete RNA
roots and zero helpers. Each inter-member link requires a provider selected by an
original catalog dependency and an exact complete-signal transport premise. Two
placements retain one checked shared delivery window. Independent review corrected a producer proposal schema-routing mismatch and tightened SDK effect-anchor order. Transport recipient/window controls now coherently repin their original authority and assert the intended context diagnostics. This review is not a soundness proof.

The new source fixture has three original inputs and A/B product-edit witnesses.
Core/Verify must independently check the full 25-history staged domain and both
complete molecules. Local mocked orchestration checks passed after updating the
37-suite inventory; native execution was mocked throughout. Capability mutation
checks passed with the new profile and unchanged historical contract projections.
The fixed hosted registrations will require 37 native suites and nine SDK
campaigns; full native inventory is expected to be 177 suites, 184 executable
bundle members and 26 distinct original fixtures. These counts still require
source-bound native and full integration verification.

Local P4 feedback includes 25 new SDK controls, 96 previous SDK regressions and both strict typing scopes; 47 campaign/fixture/installed/prebuilt inert controls; 46 boundary/bundle tests; 76 development/SDK/fixture tests plus two capability controls; 49 source-scope/CI-plan controls; and 38 rule-inventory tests. None ran native executables. The rule inventory now has 25 families, 97 production sources and 112 witnesses; its projection preserves all previous 24 meanings and all 62 original material rules. The API inventory adds only 51 private dependencies/protocol constants, preserving all 845 previous classifications and 138 witness meanings. Migration inventory has 3,872 entries. Both inventory gates are now early preflight checks, including the opt-in hosted development lane.

The 39 public API inventory controls pass, including all historical projections. The final 82-test orchestration/rule batch passed 81 controls and exposed one stale workflow-text expectation after moving source gates ahead of native setup; the corrected focused control passed. The early gates now explicitly precede OCaml setup. This is local inert feedback only.

First P4 development run `37807263696` at `705f6adb3` passed its early source gates, then failed native compilation before tests. OCaml 5.4 rejected the new local variable named `effect`; an adjacent interface documentation comment was ambiguous (warning 50). The corrective batch renames only that local variable and separates the doc comment, refreshes source inventory pins and retains the authenticated diagnostic archive. Native tests and SDK campaigns remain pending a fresh corrected run.

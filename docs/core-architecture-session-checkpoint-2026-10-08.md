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
| Modular assurance | `core-modular-assurance` | Implementing a bounded candidate-transition congruence rule and an enabled/disabled hosted comparison. Every original domain history, source execution, correspondence and requirement monitor remains fresh; no global-domain pruning is claimed. |

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

## Grounded-helper implementation checkpoint

The separately versioned helper increment is being built in
`codex/dev-policy/grounded-helper-composition`, based on P4 source `705f6adb3`.
Both subsequent P4 native corrections are carried forward explicitly; the
helper checkout is not an accepted descendant of a passing P4 run. Source
implementation, independent three-member fixtures and SDK/installed orchestration
are in progress. See the [helper contract](policy-grounded-helper-composition-v0.1.md).

P3 development run `37803803945` at `6feb332688ec838031e4cab9de2f2ee498c7f4b5`
passed 36 native suites and eight SDK campaigns (208 observations); its independent
inert audit passed, SHA-256
`fa18db1b150cbe158f38fb38d8568ad5c250e6533bf8d83d3842973042b2ea89`.
The P2 audit for `37798264346` remains separate at source `a34ebd6bc`.
Neither replaces installed, cross-platform or actual-main validation.

P4 corrected source `a459a234f34fe0128fb994d22aca2de9fecff599` is under fresh
hosted development run `37809478943`. Prior run `37807975704` compiled and passed
35/37 suites, with no SDK campaign execution. Its authenticated artifact
`11563489280` has SHA-256
`07f0568f5de9148b983d5fa50fbea14ef917ae8aba4dcdaad3f98256e46daa02`;
only inert diagnostics were inspected locally. The correction adds the missing
producer census entry and keeps the original renaming work exhaustion as a
negative control before a separate larger-budget check.

P1 PR99 integration run `37799164508` at `a38174303` still has useful healthy
checks running. Its API inventory correction is prepared in the P1 checkout;
unit-accounting failures follow the two API-inventory unit failures. Preserve
the active run, batch all concrete corrections, and require a fresh full gate.

Local helper feedback: 60 earlier profile SDK controls and both CI-pinned strict
typing scopes (34 core files and 31 policy files) pass. The new helper SDK has
24 inert tests. Native helper compilation/execution, final inventories and
installed/integration/main acceptance are not yet established.

The helper batch now has independent A/B three-member originals and 36 native
negative controls registered, with explicit candidate work budget 2,000,000.
Both alternatives retain the same two therapeutic products and complete source
graph/domain; only the supplied helper product changes from MA to MG. This is a
software fixture under supplied contracts. Source authoring and native test
registration do not establish executed acceptance.

The 125-test local wiring/boundary/transport batch passed 123 controls; two
stale expected pass-counts were corrected and their focused rerun passed. The
new campaign/installed/prebuilt batch passed 40 inert controls, and the source-
scope/CI-plan batch passed 28. The supported hosted development census is now
38 native suites and ten SDK campaigns (260 observations). Full native
integration has 178 suites, 186 executable bundle members, 26 original fixture
files and 212 total bundle members. No native command ran locally.

The final helper campaign review added complete third-manifest-row/hash checks;
the complete campaign/fixture/installed/prebuilt rerun passed 50 inert controls
(12 + 7 + 13 + 18) in 1.448 seconds. An independent source review of the native
helper witnesses and original oracle found no concrete mismatch; hosted
compilation and native behavior still require fresh execution.

Final helper source gates pass: 83 inventory controls, 26 component rule families
with 103 production sources and 125 witnesses, 62 unchanged material rule
meanings, and 905 API classifications. Independent comparison retained all
previous 25 component meanings, all previous 896 API classifications, all 138
witness meanings and all 359 syntax links. Nine new private dependencies and
protocol constants carry no independent executed-coverage claim. Migration
inventory is current at 3,888 entries. The final SDK regression rerun passed
84 controls; the two strict typing scopes remain passing.

Independent review of the helper SDK, original provenance, installed ownership
and CI wiring found no correctness blocker. The five-original-input description
and early capability test registration were corrected during that review.
This coherent source checkpoint is ready for its first hosted development run;
no helper native, installed, integration or actual-main acceptance is claimed.

## Grounded-helper first hosted correction

Source `cb7bc7037abf42f9a6b997ec7f119d93b61bfdc6` was submitted to development
run `37811166797`, attempt 1. Compilation stopped before any native suite or SDK
campaign executed: the new helper literal module needed its own `open Bioc_wire`
namespace import. The independently reviewed correction adds that import and
refreshes only its witness source hash; all rule meanings remain unchanged.
Authenticated inert artifact `11565461025` retains the failure; its build log
has SHA-256 `eb18600f7be8c9d7c6e297e10bb371b4aa16d4324b63e17fcd50a7c11aa6b667`.
A fresh corrected-source run is required. Development documentation now matches
the registered 38 native suites and ten SDK campaigns (260 observations).

## Candidate-transition congruence work in progress

The P5 checkout starts from helper source `cb7bc7037` with its reviewed namespace
correction carried forward as `8074da442`. The helper correction itself is under
run `37811917435` at `ac6150c4eacdc972c8842861d2017ef6b37fd882`; neither its
acceptance nor P5 acceptance is established. The [narrow assurance contract](policy-candidate-transition-congruence-v0.1.md)
records measured historical logical work separately from CPU timing and states
the exact candidate congruence premises. The implementation will compare
complete private runtime state, input and resource guards within one fresh
verification invocation. Source, trace correspondence, requirements, all original
obligations and logical resource charges remain unchanged.

The native diagnostic checker API now separates CPU phases from canonical
evidence. Private transition witnesses and independent convergence/budget
controls are being implemented. Ordinary production calls retain the unshared
algorithm pending measured validation. This is a bounded transition reuse rule,
not independent component acceptance or a theorem that arbitrary compositions
need no whole-program checking. Full integration and actual-main gates remain
open for all increments.

The helper canonical-inventory correction was independently reviewed and
submitted as `b712322d62a849e1a7216bcc8f516bbd8de992d2` in run `37813464181`.
Its five source/witness changes and exact ledger pins are explicitly carried
into P5; no acceptance is inherited. The helper now distinguishes canonical
template inventories from declared delivery order, with 38 native negative
controls.

Local P5 source feedback currently passes 44 rule-inventory controls, the
unchanged 905-entry public API inventory and 3,888-entry migration inventory.
The additive 27th rule preserves all 26 earlier component and 62 material rule
meanings. Both new native suites are registered: development now requires
40 suites and the unchanged ten SDK campaigns (260 observations); full native
integration requires 180 suites and a bundle of 188 executables plus 26 original
fixtures. Hosted P5 execution is not yet established.

P4 development is now complete: run `37809478943`, attempt 1, at
`a459a234f34fe0128fb994d22aca2de9fecff599` passed all 37 native suites and nine SDK
campaigns (234 observations). Independent inert audit passed with SHA-256
`05d45efd26fb758deb5be2d6411e9951af605c6946ae85bf0262872251075493`, authenticating
1,243 source files and artifact `11565722888` (7,527,004 bytes; SHA-256
`ca3ff6e3eb3fc736991ecff4e3ced455576d7c2e6053fc4ce38267460c8074cf`). Its
23-obligation, 25-history/86-transition/87-prefix original domain and both exact
RNA archives remain Linux development evidence only.

P5 independent proof review clarified that `proof_work` measures declared
auxiliary accounting units, not every CPU/byte visit: canonical key sorting is
finite under the independent data bounds but not separately charged by that
counter. Measured candidate CPU includes it. The fixed budget and ordinary
semantic/resource behavior are unchanged.

The helper corrected run `37813464181` has passed all 38 native suites and is
executing ten SDK campaigns. Its final independent audit remains pending.

P5 source is ready for its first hosted development run. Independent review
found no blocking soundness or obvious OCaml API/type issue in the private
transition rule, full-state key, finite preflight/fallback, fresh source/monitor
path, staged controls or finite-domain benchmark. This is source review, not a
machine-checked proof or executed native validation. The final local combined
run passed 117 Python/static tests in 104.407 seconds; every native subprocess
in those orchestration tests was mocked. The source boundary and both inventory
gates pass. There are 19 basic plus six staged runtime negative controls and
nine full-checker negative controls registered for hosted execution. Canonical
reports and logical charges are compared across fresh enabled/disabled calls.
The final 27-rule metadata SHA-256 is
`e9a16f88aaf74c370fda146574f5e5d90e93a7fe37c540e79be69e2ccd5ea45a`;
all 26 prior component and 62 material rule meanings remain unchanged.

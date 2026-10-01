# Circuit authority infrastructure v0.1

Version `0.1.0.dev25` adds a bounded software increment supporting R1, R5,
R11, R12 and R13. It does not complete those milestones. The sole product target
remains DNA/RNA payloads for in-vivo immune-cell deployment in humans.

## Three independent acceptance tracks

| Track | What can pass here | What remains open |
| --- | --- | --- |
| Software implementation | Strict imports, nominal bindings, fresh independent structural checks, metadata invalidation, inspection and lossless save/reopen | Actual molecular-family rules, independently derived responses, integrated selection and family exports |
| Reviewed reference correspondence | Metadata consistency and explicit coverage gaps | Source bytes, independent review, complete requested molecular forms, separate construction and final comparison authorities, experiment/material mapping |
| Human biological applicability | Preservation of the original target and deployment obligations; explicit refusal | Functional evidence in the intended immune-cell state and in-vivo context; therapeutic admission |

A scoped engineering PR can advance the first track while the others remain open.
PASS means only the declared check passed. It never promotes artificial controls,
a supplied fingerprint or a human-attributed review label to biological evidence.

## R1 support: metadata and gap inspection

`SourceDocument`, `SourceGap`, `SourceReview`, `CircuitSourceCase` and
`CircuitSourceInventory` retain provenance, access/reuse/correction status,
content pins, review identity and all nine required coverage fields. Importers
reject unknown fields, duplicate keys, invalid identities, stale profile versions
and resource-limit violations. `check_circuit_sources` checks relationships and
review freshness; `verify_circuit_sources` freshly replays against an independent
inventory. Review labels do not authenticate reviewers or fetch source bytes.

`inspect_circuit_source_readiness` produces a bounded gap report for all cases or
one case. Missing fields, declaration-only coverage, receipt/reuse/correction gaps,
review status and source-context limitations remain explicit. Even an all-provided
inventory is `not_established` for R6a: metadata alone cannot establish the separate
source-byte, authority, full-form, experiment-context and family acceptance gates.
The empty inventory remains empty; no placeholder becomes an actual study case.

```sh
python examples/circuit_sources.py --output generated/circuit-sources
biocompiler circuit-sources-check --inventory generated/circuit-sources/inventory.json --output generated/circuit-sources/checked.json
biocompiler circuit-sources-verify generated/circuit-sources/checked.json --expected-inventory generated/circuit-sources/inventory.json
biocompiler circuit-sources-readiness generated/circuit-sources/inventory.json
```

These examples are artificial metadata controls. The incomplete R1 draft PR28
remains unmerged; this increment selectively integrates its reusable metadata
software. See the [first-case readiness record](r6a-reference-readiness.md).

## R5 support: supplied nominal bindings

`CircuitBindingRequest` contains the full independent construction request,
`CircuitEntityBinding` records and explicit assumptions. Bindings identify the
original requirement and its input observation, output product or dependency,
then an exact construction requirement and role. Material bindings may identify
a final feature/path; external bindings retain exact provider identity and scope.

`check_circuit_bindings(candidate, expected_request=...)` independently replays
construction before looking up final members. It checks complete once-only
coverage, categories, roles, observation mapping, compartment declarations and
final feature frames. Missing, conflicting or unsupported bindings cannot pass.
`verify_circuit_binding_assessment` compares the complete fresh assessment with
the retained result. Changing the request, assumptions, candidate or claimed
outcome invalidates that result.

This is nominal correspondence. An alphabet match, entity name, asserted feature
or external fingerprint does not establish physical molecular identity, sensing,
translation, function, provider availability or colocation. Those claims stay
unestablished; molecular implementation stays unimplemented. No family semantics,
regulatory interactions, kinetics or response table is fabricated by this API.

## R11 support: dependency receipts and unsupported predictions

`CircuitEvidenceRequest` combines independently supplied construction authority
with bounded `CircuitEvidenceSource` descriptors. Observations have exact
requirement/observation mappings and distinct calibration, held-out or unassigned
uses. Model descriptors have prediction use; reference descriptors are reference
only. These categories cannot substitute for one another.

`capture_circuit_evidence` requires a freshly checked strict complete build and
records the current circuit, construction, material, context and external metadata
identities. `check_circuit_evidence` compares the receipt against a current build
and separately supplied evidence request after fresh reconstruction. Changes to
sources, observations, target/context, roles, material chemistry or amounts produce
explicit stale/missing dependency rows. Incomplete and diagnostic constructions
remain unsupported. A forged or internally inconsistent build is rejected.

The receipt is an identity snapshot, not proof of data quality or independent
review. `verify_circuit_evidence_assessment` replays all current dependencies.
Prediction is always `unsupported`, empirical validation `unknown`, applicability
`unassessed`, and human admission `not_admitted`. No model is run and no external
source is retrieved. Missing evidence remains explicit even when other identities
are current.

## R12 support: retained-record inspection

`inspect_circuit_construction` shows the original request, required roles, roots,
operations, intermediate maps, final chemistry/features, complexes, amounts and
missing obligations. It labels stored assessment as historical. An optional
complete independent request triggers fresh replay; self-contained hashes never
replace it. Long base strings are represented by spelling identities in the view;
the original artifact retains every base and field.

`diff_circuit_constructions` compares exact typed identities and changed fields,
including ordered coordinate paths and int/float distinctions. Sequence changes
report their enclosing changed interval after a common-prefix/suffix scan; this
is not sequence alignment. The bounded change list reports omitted counts. With
authority supplied, both sides require their own complete request and replay.

```sh
python examples/circuit_infrastructure.py --output generated/circuit-infrastructure
biocompiler circuit-inspect generated/circuit-infrastructure/build.json --expected-request generated/circuit-infrastructure/request.json
biocompiler circuit-diff generated/circuit-infrastructure/build.json generated/circuit-infrastructure/comparison-build.json
biocompiler studio
```

Choose **Inspect a saved circuit construction** in Studio, or open `/construction`
on the printed loopback address. This read-only view accepts a retained build and
optional independently retained construction request. It shows historical and
fresh structural outcomes separately, uses labeled keyboard-accessible controls,
and saves the original JSON unchanged. Input edits invalidate pending inspection
and save operations. Save does not export an admitted payload. The browser never
parses authority JSON, preserving numeric precision and the original spelling.
Each input is limited to 1 MiB and the encoded operation to 2 MiB. CLI/Python
support the underlying artifact bounds. Host/origin/session protections apply to
both new routes. No server path or remote URL is opened from imported metadata.

Public CLI commands also provide `circuit-bindings-check`,
`circuit-bindings-verify`, `circuit-evidence-capture`, `circuit-evidence-check` and
`circuit-evidence-verify`; `--help` documents explicit independent authority inputs.
Output publication is atomic and cannot overwrite an input. Generic `inspect`
identifies all new typed artifacts without upgrading saved claims.

## R13 support and remaining acceptance

Regression tests cover adversarial imports, forged assessments, source corrections,
missing/changed bindings, chemistry/context/amount edits, independent replay with
producers disabled, exact save/reopen and late-result refusal. A dependency audit
enforces checker import boundaries. Hosted CI retains all existing package,
Python 3.11/3.14, example, CLI, audit and browser gates and adds installed-package
infrastructure examples outside the checkout plus construction browser acceptance
at 320, 768, 1024 and 1440 pixels. Cross-version artifact identity comparison is a
release check. No local native compilation or implicit package rebuild is required.

Actual family semantics and integrated R6–R13 workflows still require R6a and
each family's own reviewed evidence. The [continuation boundary](r5-r13-continuation-boundary.md)
tracks this separately from the software increment. Neither fixture coverage nor
this guide closes the full-case matrix or researcher walkthrough.

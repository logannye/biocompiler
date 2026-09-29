# Human target contract v0.1

M10.1 specifies and implements the first **target-declaration profile** for human
in-vivo engineering. It records the context a future implementation must satisfy,
including missing evidence. It does not choose the first therapeutic behavior,
delivery platform, admitted biological benchmark or patient population. Those
decisions and their acceptance belong to M10.2–M10.6 and M11–M15.

`HumanTargetContext` extends `TargetContext` under the new
`cellweave.human_target_context.v0.1` schema. It combines the existing explicit
DNA/RNA modality, compartments, capability/resource assumptions and context
identity with a mandatory `HumanTargetContract`. The nested contract fixes
`recipient_taxon_id=9606` and `engineering="in_vivo"`; import rejects any other
recipient or engineering mode. These are design constraints, not evidence that a
payload reaches or functions in a human cell.

## Required declarations

The contract has no optional applicability dimensions or universal defaults.
Every field below must be supplied, even when its evidence is unestablished.

| Field | Required meaning | Evidence needed for a future applicability claim |
| --- | --- | --- |
| `cell_subtype` | Intended human recipient subtype and identity criteria | Source-linked human cell identity and relevance to the requested recipient |
| `cell_state` | Required activation, differentiation or other relevant state | Context-matched characterization and the limits of state dependence |
| `tissue_context` | Relevant tissue/compartment environment | Evidence for the environment in which the claimed behavior applies |
| `disease_context` | Intended disease context or explicitly described absence | Source-linked disease conditions and applicability limits |
| `population_inclusion` | Explicit eligible population description | Support for the declared population and any extrapolation |
| `population_exclusion` | Explicit exclusions or a justified statement that none is established | Review of exclusions, scope limits and unresolved criteria |
| `host_dependencies` | Nonempty named capability inventory with compartments | Context-matched support for each required host capability |
| `operating_conditions` | Nonempty named observables with compartments and typed domains | Measurements or justified bounds, units, uncertainty and domain applicability |
| `evidence` | Explicit collection of pinned source assertions, possibly empty | Independently reviewed source/context/material correspondence before any biological admission |

Each scope is a `TargetClaim` with a nonempty description, explicit `basis`,
evidence IDs and nonempty limitations. Host dependencies and operating conditions
carry the same support record. `basis` is exactly one of:

- `unestablished`: no supporting evidence is established; evidence IDs are empty.
- `assumed`: an explicit design assumption; evidence IDs are empty.
- `cited`: nonempty evidence IDs refer to records in this contract. This means
  references were supplied, not that their truth or applicability was verified.

Missing records, blank descriptions/limitations, duplicate IDs, dangling evidence
references and self-declared `verified`/`pass` bases are rejected. An empty
evidence inventory is valid and visibly unresolved; an empty host or operating
inventory cannot silently mean that all environments are supported. The caller
must explicitly describe what remains unknown. The schema cannot establish that
the supplied inventory is scientifically exhaustive.

`HumanHostDependency` declares ID, capability, compartment and support.
`HumanOperatingCondition` declares ID, observable, compartment, `ValueDomain` and
support. The existing domain algebra supplies Boolean sets, finite closed scalar
intervals with types/units, and explicitly unknown domains with reasons. This
profile does not add probability distributions, correlations, unit conversion or
automatic inference of physical bounds. Population criteria and cell descriptions
are reviewed declarations, not executable cohort-selection predicates.

Human targets require declared physical compartments; `abstract` is rejected.
Every host dependency and operating condition must reference a declared
compartment. Inherited capability/resource declarations remain assumptions; they
do not certify available biological capacity or resolve molecular dependencies.

## Evidence and human applicability

`TargetEvidence` records an ID, pinned `source` or `evidence` identity, source
locator, declared source context, limitations, taxon and system classification.
The allowed systems preserve these distinctions:

| System | Taxon declaration | Interpretation |
| --- | --- | --- |
| `human_in_vivo` | 9606 | Caller-declared human in-vivo context; independently unvalidated |
| `primary_human_cells` | 9606 | Primary-cell context, without automatic transfer to patient in-vivo behavior |
| `human_cell_line` | 9606 | Exact cell-line context, without automatic primary-cell or patient applicability |
| `nonhuman_in_vivo`, `nonhuman_cells` | Positive non-human taxon | Supporting source context only; cannot substitute for the human target |
| `cell_free`, `software_fixture` | null | No recipient taxon or automatic human applicability |

Mixed-context sources require separately classified records and locators for
their relevant subsets. A source hash pins bytes; the schema does not fetch the
source, authenticate a reviewer or establish that an experiment occurred.
Adding human-context labels or citation IDs never upgrades a claim to empirical
support. Non-human references may be retained as contextual evidence; this does
not select them as admitted human components. Global selection/export admission
rules remain M10.5 work.

`HumanTargetContract.unresolved_evidence` returns stable paths for **every**
applicability assertion in this version, including cited assertions. Independent
human-context review, exact-material correspondence, model validation and in-vivo
transfer evidence remain outstanding where required. No target record exposes a
biological PASS or compiler-admission flag.

## Identity, compatibility and integration

All records use strict versioned JSON, reject unknown fields and duplicate JSON
keys, and defensively freeze collections. Invalid UTF-8 and invalid domain values
are rejected. Inventories and citation IDs are canonically ordered. Changes to
claims, limitations, evidence pins, modality, host requirements or operating
conditions change target identity and therefore enclosing build-request identity.

Legacy `TargetContext` v0.1 bytes and fingerprints are unchanged. The shared
`TargetContext.from_dict/from_json` entry point explicitly dispatches the new
human schema. `BuildRequest`, realization and composition consumers that import
targets through that entry point retain the entire nested human contract. An
unknown version or a human document relabeled as legacy with extra fields fails;
there is no permissive downgrade or discarded applicability field.

`plan()` and `compile()` retain the diagnostic
`human_target_applicability_unestablished` for these targets. General molecular
compilation remains unavailable. Target declarations neither select a biological
implementation nor change the exact-CDS reference completion scope.

Run the deliberately unresolved example from a source checkout:

```sh
PYTHONPATH=src python examples/human_target.py --output generated/human-target
PYTHONPATH=src python -m cellweave inspect generated/human-target/human-target.json
```

The example names an illustrative human T-cell recipient but supplies no empirical
evidence and leaves biological applicability unresolved. It is not a selected
therapeutic profile. CLI inspection identifies this limitation explicitly.

## Validation and completion scope

`tests/test_human_target.py` checks required-field and species/mode failures,
invalid evidence labels and taxonomy, legacy identity preservation, immutable
inventories, compartment consistency, nested build identity, strict imports and
unresolved planning/CLI behavior. Hosted Python 3.11/3.14 checks retain the existing
package/test/example/CLI gates and run the new target example and inspection.

M10.1 completion means the contract, evidence requirements and integration are
specified and tested. M10 as a whole, a chosen therapeutic profile, delivery
realization, independently validated biology and patient deployment remain open.

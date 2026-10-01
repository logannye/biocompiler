# Circuit intent v0.1 (R2)

R2 adds precise Python circuit requirements and independent consistency checking.
The API remains provisional until a complete R6 source-backed vertical slice
exercises it. It emits no RNA or DNA. A consistency result establishes neither
mechanism correspondence, reference fidelity, empirical function nor therapeutic
admission. Human in-vivo immune-cell deployment remains the sole product target.

## Authoring and original source authority

Use `cells.circuit(name)` on an existing `Therapy.engineer` role, or construct
`CircuitBuilder(name, profile, role_id=...)` from a frozen product profile. A
reference builder uses the same class and requirement schemas with a
`human_reference` profile and no role or deployment identity. Both paths preserve
R0's human-only scope. The reference path requires original human-experiment
metadata and an explicit exact-reproduction lock.

```python
circuit = cells.circuit("response")
a = circuit.observe(input_a)
b = circuit.observe(input_b)
circuit.require(
    "regulated_product",
    a & ~b,
    output_product,
    lifecycle=CircuitLifecycle("production_control"),
    dependencies=provider_requirements,
)
request = circuit.freeze(
    profile=human_profile,
    requested_form="delivered_rna",
    fidelity_scope="complete_nominal",
    deployment_id="declared_deployment",
)
```

`input_a`, `input_b`, `output_product`, providers and `human_profile` must be
explicit typed declarations. The complete runnable example is
[`examples/circuit_intent.py`](../examples/circuit_intent.py); it deliberately uses
software-only observations and reference authority with no published experiment.

Builder operations do not mutate or root the source graph. Circuit requirements
are additional obligations; they cannot replace a source guard, action,
prohibition, shutdown condition or deployment contract. This allows existing
strict human behavior wrappers to remain unchanged. A live builder freezes only
when the entire current source graph, including source locations, matches the
profile's original `BuildRequest` or complete human wrapper. A frozen builder
rejects a different supplied profile. Each requirement has an explicit identity,
role, source-node inventory, per-observation source bindings and captured authoring
location. `observe(observation, source=handle)` retains the exact observation-to-node
association; swapping two associations changes request identity. Frozen builders
accept existing node IDs for these associations. The builder's name
is a display label; requirement IDs are exactly the supplied strings.

The product requires the original source, typed immune-recipient binding,
explicit target state/tissue/physical compartments and deployment ID. A wrapped
deployment must retain the same ID and executing recipient. An unwrapped build
can declare the intended ID, but receives an unresolved deployment-contract
obligation. Free-text cell names are not an empirical immune-cell classifier;
the typed recipient declaration binds the original target and subtype claim.
Human nonimmune cell-line context can describe source experiments, never replace
the intended immune-cell target.

## Observations and output requirements

`CircuitObservation` binds all of the following into one nominal identity:

- `ObservationEntity(namespace, accession, version, isoform)`. Literal `unknown`
  is an unresolved value, not a wildcard or a database lookup.
- `QuantityKind`: miRNA activity, RNA abundance, protein abundance, ligand
  concentration, translation rate, fluorescence or downstream activity.
- Physical compartment and `ObservationScope`: cell-accessible, evaluator or
  external. Circuit inputs require cell-accessible declarations. Accessibility
  still needs an implementation and evidence.
- `ObservationWindow`: reference, relative bounds, time unit and aggregation,
  or an explicitly unreported window. Negative relative times are permitted;
  reversed or invalid windows are rejected.
- `ObservationEncoding`: qualitative HIGH/LOW/UNKNOWN, or disjoint numeric LOW
  and HIGH intervals with explicit units and an optional allowed range.

Units are exact nominal symbols. The compiler performs no automatic unit
conversion or inference of experimental calibration. In particular, input mimic
dose, intracellular miRNA activity and output fluorescence are different
quantities. A `CircuitProduct` distinguishes protein expression (translation
rate), mature protein abundance, reporter fluorescence, downstream biological
activity and an RNA product. `report()` remains an independent source action.

`ObservationSample` repeats its complete observation authority. Classification
rejects a different entity, isoform, quantity, compartment, scope, window, unit or
encoding, even if the scalar value looks compatible. Missing and ambiguous
samples, gaps between numeric intervals and values outside a declared allowed
range classify UNKNOWN. No thresholds are invented for qualitative states.

`CircuitLifecycle` specifies production, abundance, activity or readout control,
consistent with the product kind, with optional onset, cessation and clearance
windows. Unreported windows remain unresolved. Provider requirements declare
exact entities, host/co-delivered/external origin, compartment and colocation
group. Availability labels do not establish physical availability or functional
compatibility. Provider and lifecycle declarations are retained as obligations.

## Boolean requirements

`CircuitSignal` binds an observation ID and its complete fingerprint. `~`, `&`,
`|`, `^`, `nand`, `nor`, `xnor`, `parity` and `all_equal` compose `BooleanSpec`
truth tables. Arbitrary tables, constants, projections and asymmetric functions
are supported. Python truthiness is forbidden for signals, tables and
`LogicValue`; loops operate only while authoring.

Tables are canonical: signal IDs are sorted and the first input is the
most-significant bit. Two-input rows are 00, 01, 10, 11. A caller-supplied input
permutation is accompanied by the corresponding table permutation. Unused input
bindings survive constants and simplification. The same ID cannot acquire a
different observation binding during composition.

`parity` is odd parity (XOR reduction); zero operands is false. `xnor` is its
complement for two or more inputs. `all_equal` means all input values agree and
is a separate operation for two or more inputs. These differ for three or more
inputs. Evaluation considers all table rows compatible with observed inputs;
a value is definite only when every completion agrees. Thus FALSE AND UNKNOWN
is FALSE; UNKNOWN does not generally collapse to FALSE.

Within one role, each output product and output observation ID belongs to one
requirement. Combine conditions for that output into a single BooleanSpec;
duplicate output obligations are rejected. Shared input IDs within a role must
retain the same complete observation contract. Different nominal IDs do not
prove different physical quantities, and general physical satisfiability across
requirements remains unresolved.

The response's TRUE/FALSE requests the output observation's declared HIGH/LOW.
The table is input requirement authority, not a claim about an unimplemented
molecular circuit. No hidden expression tree is used to manufacture evidence.

## Modes, fidelity and fresh replay

A candidate request can declare a selected realization, but cannot carry an
exact-reference lock. Exact reproduction requires `CircuitReferenceLock` with
complete expected behaviors, selected realization identity, source/evidence
pins, original experiment context, requested form and fidelity scope. Source
pins declare authority; they do not prove retrieval, review or source bytes.
The lock must retain the experiment's source pins and cover every requirement.
Changing locked AND to OR, or altering a bound observation/output/lifecycle/
provider, is rejected. Changing the expected authority itself constitutes a new
request, not verification of the old one.

Forms are `delivered_dna`, `dna_expression_template`, `primary_rna`,
`delivered_rna`, `processed_rna` and `circular_rna`. DNA/RNA modality must agree
with the profile and original target. No transcription, processing or topology
conversion occurs here. Fidelity scopes `base_identity`, `source_nominal` and
`complete_nominal` record requested precision; R2 establishes none of them.

`check_circuit_intent(request)` independently inventories every original node,
source location, graph structure, build context and wrapper contract. It checks
complete nominal behavior/table/lock correspondence without importing an
authoring builder, compiler, mechanism generator or emitter. Unsupported sensing,
source operations, feedback/state, secretion, lifecycle and delivery remain
explicit unresolved diagnostics. The assessment is `consistent` only as typed
intent; implementation outcome remains `unsupported`, molecular implementation
`unimplemented`, empirical validation `unknown` and admission `not_admitted`.

```sh
python examples/circuit_intent.py --output generated/circuit-intent
biocompiler circuit-intent-check --request generated/circuit-intent/product.request.json --output generated/circuit-intent/check.json
biocompiler circuit-intent-verify generated/circuit-intent/check.json --expected-request generated/circuit-intent/product.request.json
```

Fresh verification requires the independently retained **complete original
request**, rechecks current policy and recomputes all receipts and diagnostics.
An imported report or output hash cannot supply its own expected authority.
CLI inspection explicitly labels historical records; publication is atomic and
cannot overwrite an input or follow an output symlink. `compile(CircuitRequest)`
raises `CompilationUnavailableError` with the retained obligations.

## Bounded scope and validation

The profile supports up to eight Boolean inputs (256 rows), 32 requirements,
32 providers per requirement and 128 source-node references per requirement.
Strict versioned JSON rejects unknown fields, duplicate keys, invalid types,
nonfinite values, excessive text, nesting and record counts. The complete
request shares R0's 1 MB published JSON budget, including the final newline;
assessment reports have a separate 4 MB budget. Bounds are checked before
unbounded expansion, and default pretty serialization must round-trip.

Regression coverage includes all 16 binary functions, ternary permutations and
partial assignments, exact nominal binding edits, locked AND-to-OR rejection,
wrapper/source-location/prohibition preservation, cross-role and stale-source
rejection, independent checker mutation tests, replay tampering and CLI atomic
publication. Hosted CI installs the package on Python 3.11 and 3.14 and retains
example request/check artifacts. Existing regression and browser gates remain.
R1 source inventory and source-backed reconstruction remain separate, unfinished
work. R2 uses existing pin schemas without promoting the unmerged R1 draft.

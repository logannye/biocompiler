# Therapeutic program to RNA under supplied contracts

This document specifies the earlier **per-operator** `PayloadCompilationRequest`
profile. Package `0.1.0.dev28` also implements the
[composite RNA architecture profile](payload-architecture-v0.1.md), which uses the
same source language and construction engine with full Behavior subgraphs,
many-to-many component/RNA/recipient bindings, state, quantitative branches,
sampled integration, channels and coupled execution. Its
`PayloadArchitectureRequest` and paired FASTA/manifest export are the current
architecture-selection path. The narrower limits below apply to this earlier
profile, not to the compiler as a whole.

The executable payload profile connects original therapeutic source meaning to
selected component contracts and precise RNA sequences. Its product target is
**human immune cells engineered in vivo, with RNA payloads**. It does not require
biological evidence to check translation. A declaration that supplied molecules
fulfill an executable contract remains an explicit assumption.

`compile(PayloadCompilationRequest(...))` performs one connected operation:

1. Retain the full original source and derive its installed actions, products,
   guards and executable activation graph. Preserve every unsupported source
   requirement and wrapped contract.
2. Check explicit source-to-circuit mappings. A contradictory Boolean table or
   changed product cannot replace the program's meaning. Temporal behavior is
   never reduced to a stateless table.
3. Match supplied component operations, parameters, input/output types and scope;
   connect matching signal interfaces; resolve declared dependencies and physical
   compartments; enumerate bounded compatible alternatives before ranking.
4. Derive a namespaced construction request from every selected template. Reuse
   the existing construction engine for all required RNA members, helper members,
   regulatory regions, processing declarations and chemistry.
5. Independently reconstruct source behavior, selected component behavior,
   construction authority and every emitted molecule against the complete
   independently supplied request. Export RNA only after a fresh check.

## Authoritative inputs

`PayloadCompilationRequest` contains the original human `CircuitRequest`, a
`PayloadContractLibrary`, explicit `PayloadCircuitBinding` records and bounded
selection constraints. The circuit retains its original `BuildRequest` or human
request wrappers. No compiler step changes the target to an abstract software
target, discards the original source, fetches sequences, or invents bases from
Boolean meaning.

Each `PayloadComponentContract` declares a closed executable operator through
the existing `ComponentRecord`, exact supplied construction authority through a
`PayloadTemplate`, bindings from ports/capabilities to material members and
compartments, and explicit assumptions. Output contracts additionally bind the
original action kind, attributes and product identity. This prevents an activation
bit from being mistaken for a complete description of what the output does.
For an explicitly bound circuit output, the selected contract also pins its full
`CircuitProduct` and `CircuitLifecycle`, including readout kind, quantity,
observation encoding and timing declarations. Changing that declaration requires
a compatible supplied contract. Supplementary circuit provider requirements need
an explicit correspondence to implementation providers; until supplied, each is
retained as an unresolved mapping rather than counted as implemented.

External observation adapters may omit an encoded template. All other selected
operators require supplied molecular templates. All encoded and delivered helper
members belong to those templates and are included in the complete construction.
Host and external capabilities are declarations with explicit prerequisites;
cyclic declarations cannot bootstrap their own availability.

Logical source nodes use the existing abstract execution representation; selected
contracts bind those nodes to declared physical compartments in the original
human target. That intermediate representation does not substitute a different
organism or deployment target. DNA roots or construction intermediates may occur
in supplied templates, but final nucleotide members in this profile must be RNA.
Every delivered payload or helper must also be RNA, including each constituent
of a delivered complex. Declared encoded protein products may remain in the
complete JSON specification without becoming additional delivered payloads.

## Supported execution and retained limits

The profile supports multiple installed ongoing outputs, Boolean guards,
comparisons with typed constants, sustained conditions, onset events, timed
pulses, permanent or expiring memory, explicit reset and explicitly authored
shutdown guards. It reuses the current digital execution semantics, including
per-contact aggregation and timer/reset precedence. An external shutdown
requirement never silently overrides the source program.

In this per-operator profile, quantitative rate implementation, arbitrary
finite-state machines, unsupported temporal operators, source goals without
executable refinements, resource accounting and physiological operating-domain
refinements remain explicit unsupported requirements. The composite architecture
profile supports finite state, typed rate branches and its bounded v0.2 operators
through independently supplied full Behavior contracts. Existing human deployment/acceptance wrappers remain
retained and unresolved. This profile does not infer sensors, transport mechanisms,
processing performance, intracellular concentrations or clinical thresholds.

The original supplementary `CircuitBehavior` schema carries a stateless table. If a
source guard is temporal, its exact temporal graph is checked, and the inability
to reconcile that supplementary table is retained separately. Such a build is
partial even when its selected executable graph and complete RNA set check. The
architecture profile uses `ExecutableCircuitBehavior` with the complete source
Behavior and action identities, so state/temporal meaning need not become a
stateless projection.

`require_complete=True` refuses sequence emission while source or circuit
refinements remain unresolved. Without that flag, supported partial construction
may be returned with its exact unresolved obligations. A `compiled` result means
translation within these supplied contracts; it does not mean that the contracts
have been demonstrated in human cells.

## Selection and result semantics

Hard constraints precede preferences. Selection checks every combination within
the declared budget, ranks eligible sets by preferred contract identities, total
nucleotide count and stable identity, and retains rejection reasons. If the budget
does not cover the full supplied search space, the result is `search_exhausted`
and emits no selected molecule set. `no_solution` refers only to the supplied
bounded library. It never establishes biological infeasibility.

The build stores full requirement semantics, selected contract identities,
executable graph, construction request/candidate/checks, alternatives, assumptions
and diagnostics. A verification PASS describes artifact correspondence to the
independent request; translation completeness and molecule-set completeness are
separate fields. Imported PASS labels and a candidate's own hashes are not authority.

The independently implemented checker reads original source expressions and
action contracts directly, reconstructs component behavior and all selected
templates, and invokes the existing independent construction checker. It does
not call the requirements generator, selector, template merger or emitter to
obtain its expected answer.

Search status and optimality are not independently replayed by this first
checker. Receipts explicitly retain `search_verified=False`; unsuccessful builds
add `search_outcome_not_independently_replayed`. Independent verification covers
retained source semantics and, when selected, the implementation and all molecules.
Search regressions separately test hard constraints, preferences, bounded
exhaustion and rejection diagnostics. The diagnostic inventory has a fixed 2,048
record budget; exhausting it also emits no selected molecule set.

## Python and CLI

The [runnable example](../examples/executable_payload.py) uses tiny artificial
sequences as software controls. Its contracts do not describe working biological
parts. Run it from a source checkout:

```sh
PYTHONPATH=src python examples/executable_payload.py --output generated/executable-payload
```

```python
import biocompiler as bc

request = bc.PayloadCompilationRequest.from_json(request_json)
build = bc.compile(request)
check = bc.check_payload_build(build, expected_request=request)
rna_fasta = bc.export_payload_fasta(build, expected_request=request)
```

```sh
biocompiler payload-build --request request.json --output build.json
biocompiler payload-verify build.json --expected-request request.json
biocompiler payload-fasta build.json --expected-request request.json > payload.fasta
biocompiler inspect build.json
```

Keep `request.json` separately as authority. Keep `build.json` alongside FASTA:
FASTA alone cannot represent chemistry, processing relationships, helper
dispositions, coordinate provenance, assumptions or unresolved requirements.

The evidence boundary remains explicit: exact translation under supplied
contracts is checked by code; whether those components fulfill those contracts
in human immune cells requires subsequent biological evidence.

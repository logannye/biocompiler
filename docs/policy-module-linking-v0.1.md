# Native checked module linking v0.1

The implementation and local source review are recorded in
[the checkpoint](semantic-module-linking-checkpoint-2026-10-09.md). Native validation
is pending. This profile checks
exact module elaboration; it does not separately prove module behavior or
discharge assumptions. Ordinary complete-program preservation and material
checking remain required.

## Original module authority

The closed source bundle has `schema_version` equal to
`biocompiler.policy_module_bundle.v0.1`, `profile` equal to
`biocompiler.policy_module_linking.v0.1`, and exactly the additional fields
`context`, `templates`, `instances`, and `limits`.

`context` is a complete ordinary `PolicyProgram` record. Its identity, semantics,
external declarations and source map seed the expanded program. `templates` is
an ordered list of complete records with exactly `id`, `version`, `semantics`,
`inputs`, `outputs`, `declarations`, `private`, `assumptions`, `guarantees`, and
`source_map`. These fields retain the meaning of the existing semantic-module
authoring interface. Ports have exactly `name`, `declaration`, and `access`.
All embedded source records use the independent policy-language specification.

Each instance has exactly `name`, `template`, `bindings`, and `assumptions`.
`template` is a closed pin with `id`, `version`, and `content_fingerprint`, the
SHA-256 of the complete canonical template record, including its source map.
Every template must be used, and each id/version pair has one complete body.
Bindings have exactly `port` and `target`. A context target has `kind="context"`
and `reference` (a complete source `Ref`); an output target has `kind="output"`,
`instance`, and `port`. Ordered instances determine flattened declaration order;
dependency expansion may resolve providers earlier without changing that order.

`limits` has exactly `max_work`, `max_bytes`, `max_depth`, `max_instances`,
`max_declarations`, and `max_ports`. Positive integer caller limits may only lower
fixed ceilings: 16,000,000 logical work units, 8 MiB cumulative inspected and
encoded bytes, depth 64, 64 instances, 4096 expanded declarations and 256 ports
per template. Input preflight bounds the complete bundle before decoding or
hashing; repeated traversals and emitted records are charged. Limits do not
authorize execution. The resulting ordinary source must also fit the existing
policy-document limits.

## Checked relation and diagnostics

The native checker derives interface compatibility, private ownership, reference
relocation, conservative read/write/request footprints, assumption retention,
semantic-definition merging and source-map relocation from the original bundle.
It independently reconstructs the whole `PolicyProgram` and compares every field
with the supplied proposed program. Full original source checking is required.
Only that checker constructs the opaque checked-linkage value. Raw programs can
still use existing routes but acquire no module-linkage claim from doing so.

The report uses `biocompiler.policy_module_linkage.v0.1`, implementation
`biocompiler.ocaml.policy_module_linking_check.v0.1`, relation
`exact_module_elaboration`, and fields `schema_version`, `implementation`,
`relation`, `bundle_fingerprint`, `program_fingerprint`, `lineage`, `usage`,
`behavior`, and `empirical`. The final two values are `unassessed`. Each lineage
row has `source_path`, `flat_path`, `instance`, `template`, `declaration`, and
`expanded`; instance/template are null for context declarations. Paths are JSON
pointers into the original `/modules` bundle and `/program` respectively. The
template value is its complete pin. Usage has `unit="logical_module_work"`,
`charged_work`, and `scanned_bytes`. These report views grant no native capability.

Errors retain the stable wire diagnostic code/message/path representation, with
original instance, port or template paths and relevant expected/actual identities.
Proposed declaration mismatches identify the first differing field and map it
back to the original template or context, retaining instance identity in the
message. Thrown downstream declaration diagnostics can be mapped through freshly
checked lineage. Child material reports remain unchanged, including their
embedded issue paths; the complete lineage provides the corresponding source
locations. This profile does not yet rewrite every nested report diagnostic.
Unsupported executable profiles remain distinct from invalid module linking.

## Service and material boundary

`check-policy-module-linking` accepts `modules` and `program`;
`replay-policy-module-linking` additionally accepts the complete saved `report`.
Fresh replay performs all checks again. A linked material envelope accepts
`modules`, the existing complete component-material `request`, its `candidate`
and preservation `limits`. `check-policy-module-material`,
`replay-policy-module-material`, and `export-policy-module-material` freshly
check linkage against the complete program inside that request before using the
existing material checker. The producer operation
`compile-policy-module-material` accepts `modules`, `request`, and `limits`.

The material wrapper retains the exact module bundle, linkage, and unchanged
underlying material result. The module-aware export binds the module bundle and
linkage to the original material manifest and exact FASTA. Existing raw material
profiles, reports and exports retain their meanings and bytes. Removal of the
module envelope removes the module claim; it cannot be reconstructed from a
stored PASS report.

The standalone wrapper has `schema_version="biocompiler.core.policy_module_linking.v1"`,
`implementation="biocompiler.ocaml.policy_module_linking.v0.1"`,
`validation_scope="policy-exact-module-elaboration-v0.1"`, `modules`, `program`,
`linkage`, and `invocation_fingerprint` (the complete `{modules, program}` object).
Its negotiated profile key is `policy_module_linking`.

The material wrapper has `schema_version="biocompiler.core.policy_module_material.v1"`,
`implementation="biocompiler.ocaml.policy_module_material.v0.1"`,
`validation_scope="policy-module-component-mrna-v0.1"`, `modules`, `linkage`,
`material` (the unchanged full material-service result), `invocation_fingerprint`
(the complete `{modules, request, candidate, limits}` object), and `artifact`.
Profile keys are `policy_module_material` and `policy_module_material_producer`.
Replay compares the complete non-export wrapper against fresh checking.

The linked export has `schema_version="biocompiler.policy_module_mrna_export.v0.1"`,
`fasta`, `fasta_sha256`, `manifest`, and `manifest_sha256`. Its manifest has exactly
`schema_version="biocompiler.policy_module_mrna_manifest.v0.1"`, `modules`,
`linkage`, `material_manifest`, `material_manifest_sha256`, `fasta_sha256`,
`claim_scope="exact_module_elaboration_and_bounded_conditional_component_material"`,
and `empirical="unassessed"`. The material manifest and FASTA are retained exactly
from the freshly accepted underlying export. Bundle, template, program and
manifest fingerprints include all their corresponding fields and source maps;
the FASTA hash covers the exact FASTA bytes. No module constructor or saved
report authorizes export.

The profiles advertise their operation lists, wrapper `schema_version`,
`implementation`, `validation_scope`, `bundle_schema`, `max_result_bytes=8388608`,
`max_result_nodes=250000`, `artifact`, and `empirical="unassessed"`. The standalone
artifact field is `none`; both material profiles use
`fresh_exact_mrna_with_module_lineage`. Service hashing and publication have
separate bounded accounting. Detailed execution evidence remains pending.

## Python interface and current limits

`biocompiler.policy.module_linking.ModuleBundle` holds the complete context,
instances and `ModuleLinkingLimits`. `prepare(bundle)` snapshots its original wire
bundle and proposed ordinary source. `bundle_from_data` is a closed data codec;
it grants no checked capability. Local composition keeps its existing 1,000,000
work ceiling separately from native checking's 16,000,000-unit ceiling.

```python
from biocompiler import policy
from biocompiler.core_policy_module_linking import PolicyModuleLinkingClient

# context and these instances retain their complete original declarations.
bundle = policy.module_linking.ModuleBundle(context, (sense, control, actuator))
proposal = policy.module_linking.prepare(bundle)
checked = policy.module_linking.check(
    proposal, client=PolicyModuleLinkingClient(transport)
)
```

Here `transport` is an explicitly configured `CoreClient`; preparing the proposal
is pure Python, while `check` requires the negotiated native executable.

The explicit `PolicyModuleLinkingClient` checks and freshly replays source
linkage. `PolicyModuleMaterialClient` compiles, checks, replays and exports with
the complete component-material request. Returned Python objects are descriptive
snapshots. Their validation checks response structure, original-input pins,
ordered source lineage and the unchanged complete material child; semantic
authority remains in the fresh native operations.

The module-aware paired export has a new manifest schema. Generic Python pair
publication can write its exact validated FASTA and manifest. The existing
installed offline archive consumer has not been extended to this manifest;
this addition does not claim installed archive verification or release
qualification. Fresh linked native check/replay/export requires the complete
original bundle and component-material authority.

The three-module fixture separates sensing, control and effector declarations
within the existing single-machine execution profile. Handwritten source-only
examples exercise repeated private stores, ownership, assumptions and lexical
definitions. These do not expand executable machine-network support, which is
the next roadmap item.

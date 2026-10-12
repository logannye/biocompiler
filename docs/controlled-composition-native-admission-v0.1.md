# Controlled composition native admission, RC3

RC3 implements original-input admission and the controlled operating domain.
It does not construct a candidate or execute the receptor activity mechanism.
The source, complete material originals, deployment, mechanism, finite domain,
project context and resource bounds must agree before admission succeeds.

## Native operation and compatibility

The read-only operation is `admit-policy-component-material`, initially supported
only for component-material request v0.14 and the controlled-composition profile.
Its exact payload is `{"request": <complete original request>}`. Core and Verify
both support this operation; it does not require producer authority or publish
artifacts. An older executable must reject negotiation without Python fallback.

This is a deliberate addition to the RC1 operation plan: RC3 needs an independently
callable admission boundary before RC4 construction and RC5 behavior checking
exist. It remains part of the component-material toolchain. The existing
compile/check/replay/export operations do not advertise controlled-composition
support at this checkpoint. The later complete profile retains its separately
reserved validation scope.

The capability key is `policy_controlled_composition_admission`. Its closed
record has the following fields:

| Field | Value |
| --- | --- |
| `operations` | `["admit-policy-component-material"]` |
| `request_schema` | `biocompiler.policy_component_material_request.v0.14` |
| `request_profile` | `biocompiler.policy_controlled_composition_mrna.v0.1` |
| `source_profile` | `biocompiler.policy_controlled_composition_source.v0.1` |
| `schema_version` | `biocompiler.core.policy_controlled_composition.v1` |
| `implementation` | `biocompiler.ocaml.policy_controlled_composition.v0.1` |
| `resource_profile` | `biocompiler.policy_controlled_composition_resources.v0.1` |
| `validation_scope` | `policy-controlled-composition-admission-v0.1` |
| `stage` | `admission` |
| `artifact` | `none` |
| `empirical` | `unassessed` |
| `max_result_bytes`, `max_result_nodes` | Exact service publication ceilings, also checked by the client. |

The complete native response has exactly `schema_version`, `implementation`,
`resource_profile`, `validation_scope`, `request_fingerprint`,
`report_fingerprint`, `report`, `artifact` and `usage`. `artifact` is always null.
Both fingerprints use canonical JSON over the complete original or report.
The usage record has exactly `unit`, `preparation_charged_work`,
`request_decoding_work` and `publication`; the unit is
`logical_data_visits_and_child_semantic_work`. Publication is marked
`requires_original_one_shot_frame_guard`. The preparation count excludes the
later exact-frame publication work. A one-shot guard retains the original work
owner, binds the request ID, executable, operation and entire result, and charges
and admits the complete protocol frame before transport encoding. Guard reuse or
a changed frame fails. All work and publication remain bounded by the original
request's budgets.

The report exposes the exact source correspondence, original authority inventory,
complete domain counters, fixed-frame/factor inventories and requested budgets. It reports admission separately
from construction, behavior, empirical function and human use. Any unsupported
source clause, incomplete authority, contradiction, truncated enumeration,
cancellation or resource exhaustion prevents an admitted response. A valid
request whose supplied model may violate a source deadline is not silently
repaired; behavior satisfaction belongs to RC5.

## Closed interfaces and independent fixtures

Native source representation uses an abstract controlled-document type and an
explicit codec. It cannot be passed accidentally to the legacy policy checker.
The controlled source checker produces typed symbols and original paths for the
one executor, encounter, clock, observations, two products, activity and all six
requirements. Every source definition reference resolves to its complete body.

The operating domain uses finite factors with complete Cartesian choices at
their declared ticks. Fixed frames are explicit original restrictions. Input
eligibility depends only on the declared lifecycle grammar, never on a candidate
state or a favorable requirement result. Physical input state and evidence remain
separate; encounter changes preserve executor-owned inputs and invalidate old
antigen evidence. The hold suffix changes neither physical inputs nor lifecycle;
explicit evidence refresh can continue. All exclusions and bounds remain original
authority and are retained through the domain identity.

Independent literal fixtures precede the corresponding decoders. Artificial
source definitions and complete artificial RNA originals are software inputs,
not reconstructions of the acquired patent pair. The source and domain native
tests include rejection cases and independently expected bindings/counts.

## Validation boundary

Keep native builds and execution hosted. Local tests exercise descriptions,
transport and static registrations only. The coherent development workflow keeps
its complete existing suite and campaign inventory and adds the RC3 tests.
Record the exact source, hosted run and attempt before claiming native admission
or enumeration has passed. Cross-platform installed and release gates remain RC7
and RC8; biological evidence and real paired RNA inputs remain separate.

## Admitted source vocabulary

The source has exactly fifteen declarations: one Role, Subject, Encounter and
Clock; two Observations (encounter antigen and executor controller); two fixed
product Parameters; one ControlledActivity; and six Requirements. The source
owns five independent positive integer deadlines: onset, controller cessation,
antigen cessation, component cessation and reactivation. They need not equal
one another or the supplied model's actual delays.

Each interpreted definition has one `postcondition` SemanticClause containing a
complete typed nullary TEXT literal with value
`biocompiler.controlled_source.<tag>.v0.1`. The admitted tags are `human_t_cell`,
`encounter`, `antigen`, `controller`, `activity`, `readout`,
`no_unauthorized_activation`, `initial_activation`, `controller_cessation`,
`antigen_cessation`, `component_cessation` and `reactivation`. The complete clause
and original definition body are pinned; the decoder rejects additional or
uninterpreted clauses instead of dropping them. The literal names identify
native meanings; they do not assert that biological components realize them.

Each product definition additionally carries exactly three fixed TEXT
Parameters: `product_identity`, `product_version` and `product_sha256`, bound to
the complete supplied expected protein identity and sequence body. Admission
checks this correspondence without claiming RNA translation. All original
meaning prose, source maps and provenance remain retained in the response.

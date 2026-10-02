# Persistent pipeline session scaffold — incomplete draft

**NONEXECUTABLE, INCOMPLETE DESIGN DRAFT.** This document preserves unfinished
work paused to prioritize the GitHub checkpoint. It is not an implemented
protocol, advertised capability, validated native service, or public SDK route.
No session engine (`session.ml`), native session tests, Python session client,
Dune registration, executable dispatch, or installed campaign was completed.
The four task-created source drafts below were removed from the build tree only
after their exact UTF-8 bytes were checked against this document.

The proposed service keeps one actual native manager and fixed build in one
persistent Core process. One lifetime work ancestor covers framing, parsing,
imports, native execution, and publication. Existing one-shot protocols remain
unchanged. Serialized accepted records, validator decisions, and provider
identities cannot establish authority. Remote callback transport and full generic
manager integration remain separate, unfinished work.

## Continue from this checkpoint

1. Review and freeze the proposed declaration against the actual native and
   Python implementations. The proposed 1,000,000-key/value parser limit requires
   a matching bounded Python decoder; the existing direct client's 250,000-node
   decoder does not satisfy it. None of the proposed limits below are validated
   session capabilities.
2. Implement the native session engine with exact envelope and sequence checks,
   actual retained partial managers, ordered dependencies, immutable artifact
   access, and one lifetime budget. Account for input prefix work before limit
   reduction, complete retained closure authority and build artifacts in addition
   to manager retention, and bounded prepaid terminal diagnostics.
3. Complete and review the framing loop, then add Core-only executable dispatch
   and Dune dependencies while keeping the verifier free of producer linkage.
   EOF, malformed frames, cancellation, exhaustion, and internal failures must
   invalidate the process-local authority; no reconnect or receipt import route
   is proposed.
4. Implement the strict persistent Python client, native session tests, and
   installed campaigns covering all 126 eligible original fixed calls, 121
   return-boundary rechecks, and 563 supported live-manager continuations.
   Preserve complete original outputs, states, errors, identities and explicit
   pending callback-dependent coverage. Run native validation on hosted CI.
5. Update architecture, capability and boundary inventories and the language
   migration roadmap only for implemented and validated behavior. Persistent
   sessions do not by themselves satisfy the separate 64 MiB artifact obligation.

## Exact saved source drafts

Each fenced block contains the complete original file bytes, including its
trailing newline. SHA-256 values identify the saved bytes, not native acceptance.

### `protocol/pipeline-session-v1.json`

SHA-256: `0efb75e507d8aa72c0ef74077096634d07c6cfcdb81a557072ea536675450feb`. Bytes: 3920.

<!-- BEGIN EXACT FILE: protocol/pipeline-session-v1.json -->
```json
{"argument":"--pipeline-session-v1","artifacts":{"components":["candidate","pipeline_result","selection_result","assembly","link_result","behavior_result"],"synthetic":["candidate","pipeline_result","selection_result"]},"budget":"one_lifetime_ancestor_including_hello_prefix_parse_import_execution_and_publication_no_per_command_reset","callback_scope":"native_fixed_providers_only_no_wire_callbacks_registration_decisions_or_accepted_record_import","claim_scope":"live_native_manager_scoped_acceptance_under_supplied_software_contracts_no_empirical_or_human_use_acceptance","dependencies_encoding":"ordered_unique_string_identity_pairs","exception_fields":["module","type","message","attributes"],"executable":"core","failure":"expected_logical_errors_keep_actual_partial_manager; framing_identity_budget_or_internal_errors_close","fixed_limits":{"max_depth":128,"max_number_chars":4300,"max_string_bytes":4194304,"terminal_reserve_bytes":8192,"terminal_reserve_work":1000000},"framing":"eight_lowercase_hex_body_bytes_then_lf_then_exact_utf8_json","hello_fields":["profile","limits","manager_limits"],"initialization_fields":["kind","manager","artifacts"],"limits":{"max_commands":10000,"max_frame_bytes":33554432,"max_json_nodes":1000000,"max_retained_bytes":134217728,"max_total_bytes":268435456,"max_work":1000000000000},"limits_encoding":"null_defaults_or_exact_all_positive_integer_reductions","manager_limits":{"max_ancestor_depth":128,"max_call_depth":128,"max_document_bytes":16777216,"max_document_nodes":250000,"max_providers":10000,"max_records":10000,"max_retained_bytes":67108864,"max_retained_items":1000000},"operations":{"add-build-request":{"fields":["identity","requirements","obligations","request"],"result":"complete_stage_record"},"add-input":{"fields":["identity","stage","requirements","obligations","document"],"result":"complete_stage_record"},"artifact":{"fields":["name"],"result":"complete_immutable_build_artifact"},"close":{"fields":[],"result":"null"},"get":{"fields":["identity"],"result":"fresh_complete_stage_record"},"hello":{"fields":["profile","limits","manager_limits"],"result":"exact_profile_and_effective_limits"},"initialize-components":{"fields":["request","history","until","config"],"result":"initialization"},"initialize-empty":{"fields":["target","dependencies","completion_profiles"],"result":"initialization"},"initialize-synthetic":{"fields":["request","history","until","config"],"result":"initialization"},"inspect":{"fields":[],"result":"complete_historical_manager_snapshot_with_process_local_provider_labels"},"register-completion-profile":{"fields":["profile"],"result":"null"},"result":{"fields":["identity","scope"],"result":"fresh_complete_pipeline_result"},"run":{"fields":["pass_id","input_id","output_id","configuration"],"result":"fresh_complete_stage_record"},"set-dependency":{"fields":["key","identity"],"result":"null"},"target":{"fields":[],"result":"complete_target"}},"profile":"biocompiler.core.pipeline_session.v1","protocol":"biocompiler.pipeline_session.v1","request_fields":["protocol","session_id","sequence","operation","payload"],"request_identity":"sha256_exact_utf8_body_without_frame_header","response_fields":["protocol","profile","session_id","sequence","operation","request_sha256","status","result","diagnostics","exception","closed","usage","core"],"retention":"conservative_cumulative_service_authorities_and_build_artifacts_separate_from_manager_limits_no_refund","schema_version":"biocompiler.pipeline_session_declaration.v1","sequence":"hello_zero_then_exact_successor_including_logical_errors","session_identity":"client_canonical_lowercase_uuid_bound_to_one_process_no_reconnect","terminal_reserve":"prepaid_work_and_byte_capacity_counted_before_reduced_limits; fatal_reply_may_exceed_reduced_frame_ceiling_up_to8192","usage_fields":["work_charged","work_remaining","input_bytes","output_bytes","commands","retained_bytes"]}
```
<!-- END EXACT FILE: protocol/pipeline-session-v1.json -->

### `core/lib/pipeline_service/session.mli`

SHA-256: `70e79f2a0d4c2320325b0871cba17cd82063344da7b76ea754a47f2b7b57e2cb`. Bytes: 724.

<!-- BEGIN EXACT FILE: core/lib/pipeline_service/session.mli -->
```ocaml
(* One live native manager and fixed build per process-local session. Historical
   records cannot install acceptance. Every command uses one lifetime budget. *)
val declaration : Bioc_wire.Json.t
val profile : string
val protocol : string
val maximum_frame_bytes : int
type t
type response = {bytes:string;closed:bool}
val create : unit -> t
val is_closed : t -> bool
(* Reserve the complete input body and nine-byte prefix before allocating or
   reading that body. Exactly one matching handle_frame must follow. *)
val reserve_frame : t -> int -> unit
val handle_frame : t -> string -> response
(* A bounded, prepaid terminal response. It never makes a failed command valid. *)
val abort : ?unbound:bool -> t -> response
```
<!-- END EXACT FILE: core/lib/pipeline_service/session.mli -->

### `core/lib/pipeline_service/session_io.ml`

SHA-256: `50184838a041fa4a7de73fb8c463f1985bb3243ddf592c73e8566f099a6a797c`. Bytes: 1722.

<!-- BEGIN EXACT FILE: core/lib/pipeline_service/session_io.ml -->
```ocaml
let header_size = 9
let read_header () =
  let header=Bytes.create header_size in
  let rec loop offset =
    if offset=header_size then Some (Bytes.to_string header)
    else match input stdin header offset (header_size-offset) with
      | 0 when offset=0 -> None
      | 0 -> Bioc_wire.Diagnostic.fail "pipeline_session_frame" "Incomplete session frame header."
      | count -> loop (offset+count) in
  loop 0
let length header =
  Bioc_wire.Diagnostic.require (String.length header=9 && header.[8]='\n')
    "pipeline_session_frame" "Invalid session frame header.";
  let value=ref 0 in
  for index=0 to 7 do
    let digit=match header.[index] with
      | '0'..'9' as value -> Char.code value-Char.code '0'
      | 'a'..'f' as value -> Char.code value-Char.code 'a'+10
      | _ -> Bioc_wire.Diagnostic.fail "pipeline_session_frame" "Invalid session frame length." in
    value:= !value*16+digit
  done;
  !value
let publish (response:Session.response) =
  Printf.fprintf stdout "%08x\n" (String.length response.bytes);
  output_string stdout response.bytes;flush stdout
let run () =
  let session=Session.create () in
  let rec loop () =
    if not (Session.is_closed session) then
      match read_header () with
      | None -> ()
      | Some header ->
        let size=length header in
        Session.reserve_frame session size;
        let raw=really_input_string stdin size in
        publish (Session.handle_frame session raw);loop () in
  try loop () with
  | End_of_file | Sys_error _ | Bioc_wire.Diagnostic.Error _ ->
    (try publish (Session.abort ~unbound:true session) with Sys_error _ -> ())
  | Stack_overflow | Out_of_memory ->
    (try publish (Session.abort ~unbound:true session) with _ -> ())
```
<!-- END EXACT FILE: core/lib/pipeline_service/session_io.ml -->

### `core/lib/pipeline_service/session_io.mli`

SHA-256: `0c7793cf424260c2b6dbe3eac8e133dda4f67d8e2fc578a4caf404f31f2631cb`. Bytes: 181.

<!-- BEGIN EXACT FILE: core/lib/pipeline_service/session_io.mli -->
```ocaml
(* Core-only persistent entry point. Standard and artifact one-shot modes are
   unchanged. EOF releases authority; there is no reconnect or import route. *)
val run : unit -> unit
```
<!-- END EXACT FILE: core/lib/pipeline_service/session_io.mli -->

open Bioc_wire
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module A = Bioc_checker.Policy_admission
module L = Bioc_compiler.Policy_lowering
module C = Bioc_checker.Policy_correspondence
let require condition message = if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get = O.get
let text = O.text
let items = O.list
let replace key replacement value = obj (List.map (fun (name,item) -> name,(if key=name then replacement else item)) (Json.object_fields value))
let remove key value = obj (List.filter (fun (name,_) -> key<>name) (Json.object_fields value))
let change_index index transform values = List.mapi (fun i value -> if i=index then transform value else value) values
let change_node index transform value = replace "nodes" (arr (change_index index transform (items "nodes" value))) value
let rejected = ref 0
let rejects label action =
  match action () with
  | () -> failwith ("Operational mutant accepted: " ^ label)
  | exception Diagnostic.Error _ -> incr rejected
let read path =
  let channel=open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size=in_channel_length channel in
    require (size <= 2*1024*1024) "Operational fixture too large";
    Json.parse (really_input_string channel size))
let run fixture =
  let raw=get "document" fixture and descriptor_json=get "definitions" fixture in
  let document=D.of_json ~path:"/document" raw and descriptors=O.descriptors_of_json descriptor_json in
  List.iter2 (fun (descriptor:O.descriptor) wire ->
    require (O.semantic_tag descriptor.semantics = text "semantics" wire) "Closed semantic descriptor variant lost its versioned tag";
    require (Json.equal (O.definition_ref_to_json descriptor.definition) (get "definition" wire)) "Typed definition identity did not preserve all source pin fields";
    require (String.length descriptor.definition.definition_digest = 64) "Typed definition pin has an invalid SHA-256 length")
    (O.descriptors descriptors) (items "definitions" descriptor_json);
  let admitted=A.admit ~document ~descriptors in
  let behavior=L.lower admitted in
  let initial=O.behavior_to_json behavior in
  let checked=C.check ~expected_document:document ~descriptors behavior in
  require (text "status" checked = "valid") "Literal operational lowering was not checked";
  require (text "target_status" checked = "unassessed" && text "artifact" checked = "withheld") "Operational check inflated realization claims";
  require (List.length behavior.nodes = List.length (D.declarations document)) "Lowering omitted declarations";
  require (List.length behavior.requirements = 2) "Lowering omitted requirements";
  require (text "semantic_status" (A.source_assessment admitted) = "unresolved") "Admission changed PR88 source-only claims";
  require (O.behavior_to_json (O.behavior_of_json initial) = initial) "Behavior JSON roundtrip differs";
  require (O.value_of_json O.Truth_type (str "unknown") = O.Truth O.Unknown) "Explicit source UNKNOWN was not retained";
  rejects "malformed null truth evidence" (fun () -> ignore (O.value_of_json O.Truth_type Json.Null));
  let check candidate = ignore (C.check ~expected_document:document ~descriptors (O.behavior_of_json candidate)) in
  let deep=List.fold_left (fun value _ -> arr [value]) Json.Null (List.init 70 Fun.id) in
  let extra_operand key value = change_node 0 (fun node ->
    replace "data" (obj ((key,value)::Json.object_fields (get "data" node))) node) initial in
  (match O.behavior_of_json (extra_operand "deep_operand" deep) with
   | _ -> failwith "Programmatic deep candidate bypassed ingress measurement"
   | exception Diagnostic.Error diagnostic -> require (diagnostic.code = "policy_operational_limit") "Deep candidate failed after resource ingress";incr rejected);
  rejects "raw float candidate ingress" (fun () -> ignore (O.behavior_of_json (extra_operand "float_operand" (Json.Float 0.5))));
  rejects "oversized candidate string ingress" (fun () -> ignore (O.behavior_of_json (extra_operand "long_operand" (str (String.make 262_145 'x')))));
  List.iteri (fun index node ->
    List.iter (fun key -> rejects ("instruction metadata "^key) (fun () ->
      check (change_node index (replace key (str "tampered")) initial))) ["id";"kind";"source_path"];
    let operands=get "data" node in
    List.iter (fun (field,_) ->
      rejects ("removed operand "^field) (fun () -> check (change_node index (replace "data" (remove field operands)) initial));
      let replacement=if get field operands = Json.Null then str "tampered" else Json.Null in
      rejects ("changed operand "^field) (fun () -> check (change_node index (replace "data" (replace field replacement operands)) initial)))
      (Json.object_fields operands)) (items "nodes" initial);
  rejects "missing instruction" (fun () -> check (replace "nodes" (arr (List.tl (items "nodes" initial))) initial));
  rejects "instruction reordering" (fun () -> check (replace "nodes" (arr (List.rev (items "nodes" initial))) initial));
  rejects "duplicated instruction" (fun () -> check (replace "nodes" (arr (items "nodes" initial @ [List.hd (items "nodes" initial)])) initial));
  List.iter (fun key -> rejects ("lost ledger "^key) (fun () -> check (replace key (arr []) initial)))
    ["source_ledger";"requirements_ledger";"unresolved_obligations"];
  rejects "invented assumption" (fun () -> check (replace "assumptions" (arr [str "invented"]) initial));
  let map=get "source_map" raw in
  let altered_map=match Json.array map with
    | first::rest -> arr (replace "line" (Json.int 999) first :: rest)
    | [] -> arr [obj ["$type",str "SourceSpan";"declaration_id",str "executor";"file",str "mutant.py";
        "line",Json.int 999;"column",Json.int 0;"pattern",Json.Null]] in
  let changed_source=replace "source_map" altered_map raw in
  require (D.document_digest changed_source = D.document_digest raw) "Source map must not change semantic document identity";
  let changed_document=D.of_json ~path:"/document" changed_source in
  let forged=initial |> replace "source_document" changed_source |> replace "source_artifact_digest" (str (D.artifact_digest changed_document)) in
  ignore (Canonical.fingerprint forged);
  rejects "rehashed source correspondence" (fun () -> check forged);
  let changed_id=replace "id" (str "forged.program") raw in
  let changed_document=D.of_json ~path:"/document" changed_id in
  let self_consistent=L.lower (A.admit ~document:changed_document ~descriptors) in
  rejects "self-consistent candidate against wrong source" (fun () -> ignore (C.check ~expected_document:document ~descriptors self_consistent));
  let definition_values=items "definitions" descriptor_json in
  let admit_definitions raw_definitions = ignore (A.admit ~document ~descriptors:(O.descriptors_of_json raw_definitions)) in
  rejects "missing semantics" (fun () -> admit_definitions (replace "definitions" (arr (List.tl definition_values)) descriptor_json));
  rejects "duplicate semantics" (fun () -> admit_definitions (replace "definitions" (arr (List.hd definition_values :: definition_values)) descriptor_json));
  let edit_first transform=replace "definitions" (arr (change_index 0 transform definition_values)) descriptor_json in
  List.iter (fun digest -> rejects "malformed SHA-256 descriptor ingress" (fun () ->
    ignore (O.descriptors_of_json (edit_first (fun descriptor ->
      replace "definition" (replace "digest" (str digest) (get "definition" descriptor)) descriptor)))))
    [String.make 63 'a';String.make 65 'a';String.make 64 'g';String.make 64 'A'];
  rejects "unknown semantic tag" (fun () -> admit_definitions (edit_first (replace "semantics" (str "infer.from.prose"))));
  rejects "contextually wrong semantics" (fun () -> admit_definitions (edit_first (replace "semantics" (str "effect.abstract_attempt.v1"))));
  List.iter (fun field -> rejects ("wrong complete definition identity "^field) (fun () ->
    admit_definitions (edit_first (fun descriptor -> replace "definition" (replace field (str "changed") (get "definition" descriptor)) descriptor))))
    ["id";"version";"digest"];
  let source_defs=items "definitions" (get "semantics" raw) in
  let unused_definition=List.hd source_defs |> replace "id" (str "unused.definition") |> replace "meaning" (str "Unreachable source definition remains unproved.") in
  let unused_source=replace "semantics" (replace "definitions" (arr (source_defs @ [unused_definition])) (get "semantics" raw)) raw in
  let unused_document=D.of_json ~path:"/document" unused_source in
  ignore (C.check ~expected_document:unused_document ~descriptors (L.lower (A.admit ~document:unused_document ~descriptors)));
  let unused_pin=obj ["$type",str "DefinitionRef";"id",str "unused.definition";"version",get "version" unused_definition;"digest",str (D.document_digest unused_definition)] in
  let extra=replace "definitions" (arr (definition_values @ [obj ["definition",unused_pin;"semantics",str "capability.deferred.v1"]])) descriptor_json in
  rejects "unreachable descriptor authority" (fun () -> ignore (A.admit ~document:unused_document ~descriptors:(O.descriptors_of_json extra)));
  let change_declaration identity transform source = replace "declarations" (arr (List.map (fun declaration ->
    if text "id" declaration = identity then transform declaration else declaration) (items "declarations" source))) source in
  let unsupported label source =
    let document=D.of_json ~path:"/document" source in
    require (text "status" (Bioc_checker.Policy_check.check document) = "valid") ("Unsupported control lost source validity: "^label);
    match A.admit ~document ~descriptors with
    | _ -> failwith ("Unsupported operational control admitted: "^label)
    | exception Diagnostic.Error diagnostic ->
        require (diagnostic.code = "policy_operational_unsupported") ("Wrong operational support outcome: "^label);
        incr rejected in
  unsupported "observation-based clock" (change_declaration "clock" (replace "basis" (str "observation")) raw);
  unsupported "continuous observation coverage" (change_declaration "condition" (replace "coverage" (str "continuous")) raw);
  unsupported "omitted uncertainty class" (change_declaration "condition" (replace "invalidity" (arr [str "missing";str "stale";str "invalid"])) raw);
  unsupported "zero freshness" (change_declaration "condition" (fun observation ->
    replace "freshness" (replace "amount" (str "0") (get "freshness" observation)) observation) raw);
  unsupported "persistent encounter storage" (change_declaration "seen" (replace "lifetime" (str "persistent")) raw);
  unsupported "unbounded storage" (change_declaration "seen" (replace "capacity" (str "unbounded_requested")) raw);
  unsupported "effect stop requests" (change_declaration "response" (fun effect_value ->
    replace "lifecycle" (replace "on_loss" (str "request_stop") (get "lifecycle" effect_value)) effect_value) raw);
  unsupported "unknown rule stop requests" (change_declaration "respond" (replace "unknown" (str "request_stop")) raw);
  let observation=List.find (fun declaration -> text "id" declaration = "condition") (items "declarations" raw) in
  let same_frame=replace "declarations" (arr (items "declarations" raw @ [replace "id" (str "same_frame_observation") observation])) raw in
  unsupported "unimplemented multi-observation frame join" same_frame;
  let named id=List.find (fun declaration -> text "id" declaration = id) (items "declarations" raw) in
  let reference kind id=obj ["$type",str "Ref";"kind",str kind;"id",str id] in
  let role_ref=reference "Role" "executor" and encounter_ref=reference "Encounter" "encounter" in
  let executor_scope=obj ["$type",str "Scope";"kind",str "executor";"subject",role_ref] in
  let append declarations source=replace "declarations" (arr (items "declarations" source @ declarations)) source in
  let rule=named "respond" in
  let literal=get "value" (List.hd (items "assignments" rule)) in
  let executor_reset=named "seen" |> replace "id" (str "executor_reset") |> replace "scope" executor_scope
    |> replace "lifetime" (str "executor") |> replace "reset" (get "when" rule) in
  unsupported "executor reset reads encounter evidence" (append [executor_reset] raw);
  let global_observation=observation |> replace "id" (str "executor_observation") |> replace "subject" role_ref
    |> replace "coherence" (str "executor_frame") in
  let global_event=get "on" rule |> replace "op" (str "updated") |> replace "args" (arr [])
    |> replace "ref" (reference "Observation" "executor_observation") |> replace "scope" role_ref in
  let machine=obj ["$type",str "Machine";"id",str "executor_machine";"executor",role_ref;"scope",executor_scope;
    "states",arr [str "idle";str "done"];"initial",str "idle";"terminal",arr [str "done"];
    "lifetime",str "executor";"arbitration",get "arbitration" rule] in
  let transition=obj ["$type",str "Transition";"id",str "machine_step";"machine",reference "Machine" "executor_machine";
    "source",str "idle";"destination",str "done";"on",get "on" rule;"when",literal;"unknown",str "defer";
    "effects",arr [];"assignments",arr [];"unknown_target",Json.Null;"emissions",arr []] in
  unsupported "executor machine reads encounter event" (append [machine;transition] raw);
  let assignment_transition=transition |> replace "on" global_event |> replace "assignments" (get "assignments" rule) in
  unsupported "executor machine writes encounter destination" (append [global_observation;machine;assignment_transition] raw);
  let destination_rule=rule |> replace "id" (str "unbound_destination") |> replace "on" global_event
    |> replace "when" literal |> replace "effects" (arr []) in
  unsupported "rule destination cannot introduce encounter binding" (append [global_observation;destination_rule] raw);
  let encounter_state=literal |> replace "op" (str "state") |> replace "value" Json.Null
    |> replace "ref" (reference "StateStore" "seen") |> replace "scope" encounter_ref in
  let executor_effect=named "response" |> replace "id" (str "executor_response") |> replace "subject" role_ref in
  let mismatched_rule=rule |> replace "id" (str "mixed_retained_binding") |> replace "on" global_event
    |> replace "when" encounter_state |> replace "assignments" (arr [])
    |> replace "effects" (arr [reference "Effect" "executor_response"]) in
  unsupported "effect subject differs from retained encounter environment" (append [global_observation;executor_effect;mismatched_rule] raw);
  let executor_state=named "seen" |> replace "id" (str "executor_state") |> replace "scope" executor_scope
    |> replace "lifetime" (str "executor") in
  let global_state=encounter_state |> replace "ref" (reference "StateStore" "executor_state") |> replace "scope" role_ref in
  let reads_global=raw |> append [executor_state] |> change_declaration "respond" (replace "when" global_state) in
  let reads_global_document=D.of_json ~path:"/document" reads_global in
  ignore (C.check ~expected_document:reads_global_document ~descriptors
    (L.lower (A.admit ~document:reads_global_document ~descriptors)));
  Printf.printf "policy operational: literal lowering and %d independent mutation rejections\n" !rejected
let () = if Array.length Sys.argv <> 2 then failwith "expected operational fixture" else run (read Sys.argv.(1))

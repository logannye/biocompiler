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
let descriptor_identity_controls raw descriptor_json =
  let before= !rejected in
  let unsupported label ~source ~definitions ~path ~message =
    (* Source validity and descriptor decoding are outside the rejection
       catcher: an earlier malformed-input failure cannot satisfy this test. *)
    let document=D.of_json ~path:"/document" source in
    require (text "status" (Bioc_checker.Policy_check.check document) = "valid")
      ("Descriptor control lost generic source validity: "^label);
    let descriptors=O.descriptors_of_json definitions in
    require (Json.equal (O.descriptors_to_json descriptors) definitions)
      ("Descriptor control changed during decoding: "^label);
    match A.admit ~document ~descriptors with
    | _ -> failwith ("Unsupported descriptor admitted: "^label)
    | exception Diagnostic.Error diagnostic ->
        require (diagnostic.code = "policy_operational_unsupported" &&
          diagnostic.path = Some path && diagnostic.message = message)
          ("Descriptor control failed outside its exact admission guard: "^label);
        incr rejected in
  let descriptors=items "definitions" descriptor_json in
  let first=List.hd descriptors in
  let pin=get "definition" first in
  let digest=text "digest" pin in
  require (String.length digest = 64) "Original descriptor digest lost its fixed width";
  let stale_digest=(if digest.[0] = '0' then "1" else "0")^String.sub digest 1 63 in
  let stale=replace "definitions"
    (arr (replace "definition" (replace "digest" (str stale_digest) pin) first :: List.tl descriptors))
    descriptor_json in
  unsupported "well-formed stale descriptor digest" ~source:raw ~definitions:stale
    ~path:"/definitions"
    ~message:"Operational descriptor is not bound to the complete source DefinitionRef.";
  let source_definitions=items "definitions" (get "semantics" raw) in
  let with_definition identity field replacement =
    let original=List.find (fun value -> text "id" value = identity) source_definitions in
    let changed=replace field replacement original in
    let digest=D.document_digest changed in
    require (digest <> D.document_digest original)
      "Descriptor signature edit retained its original definition identity";
    let rec repin value = match value with
      | Json.Object fields ->
          let value=obj (List.map (fun (key,value) -> key,repin value) fields) in
          if List.assoc_opt "$type" fields = Some (str "DefinitionRef") &&
             List.assoc_opt "id" fields = Some (str identity)
          then replace "digest" (str digest) value else value
      | Json.Array values -> arr (List.map repin values)
      | value -> value in
    let source=replace "semantics"
      (replace "definitions" (arr (List.map (fun value ->
        if text "id" value = identity then changed else value) source_definitions))
        (get "semantics" raw)) raw |> repin in
    source,repin descriptor_json in
  let truth_type=obj ["$type",str "TypeSpec";"kind",str "truth";
    "unit",Json.Null;"entity_kind",Json.Null] in
  let formal=obj ["$type",str "Parameter";"id",str "unused_descriptor_argument";
    "value_type",truth_type;"selection",str "fixed";
    "value",Json.Null;"lower",Json.Null;"upper",Json.Null] in
  let source,definitions=with_definition "fixture.observation" "parameters" (arr [formal]) in
  unsupported "observation formal has no executable argument interpretation" ~source ~definitions
    ~path:"/document/declarations/4/contract"
    ~message:"This primitive descriptor takes no formal parameters.";
  let source,definitions=with_definition "fixture.effect" "result" truth_type in
  unsupported "abstract effect cannot silently discard a supplied result" ~source ~definitions
    ~path:"/document/declarations/6/contract"
    ~message:"This primitive descriptor does not return a value.";
  require (!rejected = before + 3) "Descriptor identity/signature control census differs"
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
  List.iter (fun ingress ->
    let external_document=D.of_json ~path:ingress raw in
    let relocated=L.lower(A.admit ~document:external_document ~descriptors) in
    require(Json.equal initial(O.behavior_to_json relocated))
      "Ingress diagnostic prefix changed the authored operational artifact";
    require(Json.equal checked(C.check ~expected_document:external_document ~descriptors relocated))
      "Independent correspondence changed under an ingress diagnostic prefix";
    require(Json.equal raw(D.to_json(A.document(A.admit ~document:external_document ~descriptors))))
      "Canonical occurrence coordinates changed original authored source")
    ["";"/document";"/payload/document"];
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
  descriptor_identity_controls raw descriptor_json;
  let source_defs=items "definitions" (get "semantics" raw) in
  let effect_source=List.find (fun declaration -> text "$type" declaration = "Effect") (items "declarations" raw) in
  let effect_definition_id=text "id" (get "contract" effect_source) in
  let rec repin_definition digest value = match value with
    | Json.Object fields ->
        let value=obj (List.map (fun (key,value) -> key,repin_definition digest value) fields) in
        if List.assoc_opt "$type" fields = Some (str "DefinitionRef") && List.assoc_opt "id" fields = Some (str effect_definition_id)
        then replace "digest" (str digest) value else value
    | Json.Array values -> arr (List.map (repin_definition digest) values)
    | value -> value in
  let signature kind argument_value change =
    let value_type=obj ["$type",str "TypeSpec";"kind",str kind;"unit",Json.Null;"entity_kind",Json.Null] in
    let parameter=obj ["$type",str "Parameter";"id",str "product";"value_type",value_type;
      "value",Json.Null;"lower",Json.Null;"upper",Json.Null;"selection",str "fixed"] |> change in
    let definition=List.find (fun definition -> text "id" definition = effect_definition_id) source_defs
      |> replace "parameters" (arr [parameter]) in
    let expression=obj ["$type",str "Expr";"op",str "literal";"value_type",value_type;"args",arr [];
      "value",argument_value;"ref",Json.Null;"scope",Json.Null;"contract",Json.Null;"duration",Json.Null;
      "clock",Json.Null;"coverage",Json.Null;"binding",Json.Null] in
    let source=raw |> replace "semantics" (replace "definitions" (arr (List.map (fun original ->
      if text "id" original = effect_definition_id then definition else original) source_defs)) (get "semantics" raw))
      |> replace "declarations" (arr (List.map (fun declaration ->
        if text "id" declaration = text "id" effect_source then replace "parameters"
          (arr [obj ["$type",str "Argument";"name",str "product";"value",expression]]) declaration
        else declaration) (items "declarations" raw))) in
    let digest=D.document_digest definition in
    repin_definition digest source,O.descriptors_of_json (repin_definition digest descriptor_json),expression in
  let signature_document label source =
    let document=D.of_json ~path:"/document" source in
    require (text "status" (Bioc_checker.Policy_check.check document) = "valid")
      ("Effect formal control lost generic source validity: "^label);document in
  List.iter (fun (kind,value) ->
    let source,descriptors,expression=signature kind value Fun.id in
    let document=signature_document (kind^" signature") source in
    let behavior=L.lower (A.admit ~document ~descriptors) in
    ignore (C.check ~expected_document:document ~descriptors behavior);
    require ((List.hd behavior.effects).parameters = ["product",O.expression_of_json expression])
      "Signature-only effect changed its exact supplied argument";
    require (Json.equal behavior.source_document source && Json.equal (O.descriptors_to_json descriptors) (get "descriptor_bundle" (O.behavior_to_json behavior)))
      "Signature-only effect discarded original source or descriptor authority")
    ["text",str "fixture.product.alpha";"integer",Json.int 3];
  let count_bound amount=obj ["$type",str "Quantity";"amount",str amount;
    "unit",obj ["$type",str "Unit";"id",str "count";"dimension",str "count";
      "quantity_kind",str "count";"scale",str "1";"reference",Json.Null]] in
  List.iter (fun (label,kind,value,field,replacement) ->
    let source,descriptors,_=signature kind value (replace field replacement) in
    let document=signature_document label source in
    let assessment=Bioc_checker.Policy_check.check document in
    let unsupported_signature action = match action () with
      | () -> failwith ("Unsupported effect formal admitted: "^label)
      | exception Diagnostic.Error diagnostic ->
          require (diagnostic.code = "policy_operational_unsupported" &&
            Option.fold ~none:false ~some:(String.ends_with ~suffix:("/parameters/0/"^field)) diagnostic.path)
            ("Effect formal failed outside its exact admission guard: "^label);
          incr rejected in
    unsupported_signature (fun () -> ignore (A.admit ~document ~descriptors));
    (* Refresh every original source/descriptor pin and complete ledger. A
       candidate cannot use independent correspondence to bypass admission. *)
    let nodes=List.map2 (fun node (declaration:D.declaration) ->
      replace "data" (remove "$type" declaration.value) node) (items "nodes" initial) (D.declarations document) in
    let candidate=initial |> replace "source_document" source
      |> replace "source_artifact_digest" (str (D.artifact_digest document))
      |> replace "descriptor_bundle" (O.descriptors_to_json descriptors)
      |> replace "descriptors_digest" (str (O.descriptors_digest descriptors))
      |> replace "nodes" (arr nodes) |> replace "source_ledger" (get "declarations" assessment)
      |> replace "requirements_ledger" (get "requirements" assessment)
      |> replace "assumptions" (get "assumptions" assessment)
      |> replace "unresolved_obligations" (get "unresolved_obligations" assessment) in
    let candidate=O.behavior_of_json candidate in
    unsupported_signature (fun () -> ignore (C.check ~expected_document:document ~descriptors candidate)))
    ["formal design selection","text",str "fixture.product.alpha","selection",str "design";
     "formal measured selection","text",str "fixture.product.alpha","selection",str "measured";
     "formal uncertain selection","text",str "fixture.product.alpha","selection",str "uncertain";
     "formal supplied value","text",str "fixture.product.alpha","value",str "fixture.product.different";
     "formal lower refinement","integer",Json.int 3,"lower",count_bound "1";
     "formal upper refinement","integer",Json.int 3,"upper",count_bound "5"];
  require (Json.equal initial (O.behavior_to_json (L.lower (A.admit ~document ~descriptors))))
    "Signature-only admission narrowing changed the ordinary operational artifact";
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
  let rec change_field path transform value = match path with
    | [] -> transform value
    | key::rest -> replace key (change_field rest transform (get key value)) value in
  let timed_fields=["clock",["resolution"],"1000";"condition",["freshness"],"2000";
    "response",["lifecycle";"timeout"],"2000";"completion",["deadline"],"2000";
    "completion",["horizon"],"4000";"scoped_memory",["horizon"],"4000"] in
  List.iter (fun (identity,path,_) ->
    let label=identity^"/"^String.concat "/" path^" nominal time reference" in
    let changed=change_declaration identity (change_field (path@["unit";"reference"])
      (fun _ -> str "recipient-relative-time")) raw in
    unsupported label changed;
    let changed_document=D.of_json ~path:"/document" changed in
    let assessment=Bioc_checker.Policy_check.check changed_document in
    require (D.artifact_digest changed_document <> D.artifact_digest document)
      "Nominal time-reference edit did not change original authority";
    (* Rebuild every source pin, operand and ledger without invoking admission.
       Fresh correspondence must reject the unsupported original itself. *)
    let nodes=List.map2 (fun node (declaration:D.declaration) ->
      replace "data" (remove "$type" declaration.value) node)
      (items "nodes" initial) (D.declarations changed_document) in
    let forged=initial |> replace "source_document" changed
      |> replace "source_artifact_digest" (str (D.artifact_digest changed_document))
      |> replace "nodes" (arr nodes) |> replace "source_ledger" (get "declarations" assessment)
      |> replace "requirements_ledger" (get "requirements" assessment)
      |> replace "assumptions" (get "assumptions" assessment)
      |> replace "unresolved_obligations" (get "unresolved_obligations" assessment) in
    let candidate=O.behavior_of_json forged in
    match C.check ~expected_document:changed_document ~descriptors candidate with
    | _ -> failwith ("Re-pinned unsupported nominal time was checked: "^label)
    | exception Diagnostic.Error diagnostic ->
        require (diagnostic.code = "policy_operational_unsupported")
          ("Re-pinned time reference failed for an unrelated reason: "^label);
        require (Option.fold ~none:false ~some:(String.ends_with ~suffix:"/unit/reference") diagnostic.path)
          "Time-reference diagnostic omitted the unsupported original field";
        incr rejected) timed_fields;
  let milliseconds=List.fold_left (fun source (identity,path,amount) ->
    change_declaration identity (change_field path (fun quantity ->
      quantity |> replace "amount" (str amount) |> replace "unit"
        (get "unit" quantity |> replace "id" (str "ms") |> replace "scale" (str "0.001")))) source)
    raw timed_fields in
  let millisecond_document=D.of_json ~path:"/document" milliseconds in
  let millisecond_behavior=L.lower(A.admit ~document:millisecond_document ~descriptors) in
  ignore(C.check ~expected_document:millisecond_document ~descriptors millisecond_behavior);
  require (Json.equal millisecond_behavior.source_document milliseconds)
    "Equivalent unit conversion discarded the original source spelling";
  require (D.artifact_digest millisecond_document <> D.artifact_digest document)
    "Equivalent units reused the old full source identity";
  require (List.map (fun (value:O.clock) -> value.resolution) millisecond_behavior.clocks =
    List.map (fun (value:O.clock) -> value.resolution) behavior.clocks &&
    List.map (fun (value:O.observation) -> value.freshness) millisecond_behavior.observations =
    List.map (fun (value:O.observation) -> value.freshness) behavior.observations &&
    List.map (fun (value:O.effect_spec) -> value.lifecycle.timeout) millisecond_behavior.effects =
    List.map (fun (value:O.effect_spec) -> value.lifecycle.timeout) behavior.effects &&
    List.map (fun (value:O.requirement) -> value.deadline,value.horizon) millisecond_behavior.requirements =
    List.map (fun (value:O.requirement) -> value.deadline,value.horizon) behavior.requirements)
    "Equivalent seconds/milliseconds changed exact clock, freshness, timeout or requirement bounds";
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

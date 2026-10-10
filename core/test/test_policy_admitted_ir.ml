open Bioc_wire
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module T = Bioc_domain.Policy_admitted_ir
module A = Bioc_checker.Policy_admission
module C = Bioc_checker.Policy_correspondence
module L = Bioc_compiler.Policy_lowering
module R = Bioc_domain.Policy_realization_request
let require condition message = if not condition then failwith message
let get key value=Json.field key (Json.object_fields value)
let text key value=Json.string (get key value)
let items key value=Json.array (get key value)
let str value=Json.String value
let replace key replacement value=Json.Object (List.map (fun (name,value) ->
  name,(if name=key then replacement else value)) (Json.object_fields value))
let read path=let input=open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr input) (fun () ->
    Json.parse_bounded ~max_bytes:(4*1024*1024) ~max_nodes:200000
      (really_input_string input (in_channel_length input)))
let no_charge _=()
let count=ref 0
let reject label action=match action () with
  | _ -> failwith (label^": invalid typed policy accepted")
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code="policy_typed_ir" || diagnostic.code="policy_operational_type")
        (label^": failed outside typed elaboration: "^diagnostic.code)
let source_program value=match text "$type" value with
  | "PolicyProgram" -> value | "BuildRequest" -> get "program" value
  | _ -> get "program" (get "request" value)
let change_declaration identity f value=
  let program=source_program value in
  let program=replace "declarations" (Json.Array (List.map (fun declaration ->
    if text "id" declaration=identity then f declaration else declaration) (items "declarations" program))) program in
  match text "$type" value with
  | "PolicyProgram" -> program | "BuildRequest" -> replace "program" program value
  | _ -> replace "request" (replace "program" program (get "request" value)) value
let roundtrip document descriptors=
  let admitted=A.admit ~document ~descriptors in
  let typed=A.typed admitted in
  let original=D.declarations document and instructions=T.instructions typed in
  require (List.length instructions=List.length original) "Typed ledger lost a source occurrence";
  List.iter2 (fun (source:D.declaration) instruction ->
    require (T.name (T.declaration instruction)=source.id) "Nominal identity changed";
    (* Independent oracle is the complete original, never a typed re-encoding. *)
    require (Json.equal source.value (T.wire_declaration ~charge:no_charge instruction))
      ("Typed reconstruction changed original declaration: "^source.id);
    require (Json.equal source.value (T.original_declaration instruction)) "Original authority was changed";
    match T.declaration instruction with
    | T.Rule_declaration rule ->
        require (T.Role.index rule.executor < List.length original) "Executor has no resolved symbol slot";
        require ((List.nth original (T.Role.index rule.executor)).id=T.Role.name rule.executor)
          "Resolved executor points at another declaration";
        (match T.event_term rule.on with
         | T.Rising predicate -> ignore (T.truth_term predicate)
         | T.Updated observation -> require ((List.nth original (T.Observation.index observation)).kind=D.Observation)
             "Updated event resolved a non-observation"
         | T.Effect_event (effect_value,_) -> require ((List.nth original (T.Effect.index effect_value)).kind=D.Effect)
             "Lifecycle event resolved a non-effect")
    | T.Transition_declaration transition ->
        require ((List.nth original (T.Machine.index transition.machine)).kind=D.Machine)
          "Transition did not resolve a machine"
    | T.Retained_requirement id ->
        require ((List.nth original (T.Requirement.index id)).kind=D.Requirement) "Obligation identity changed"
    | _ -> ()) original instructions;
  let behavior=L.lower admitted in
  require (text "status" (C.check ~expected_document:document ~descriptors behavior)="valid")
    "Typed lowering failed independent source correspondence";
  let raw=O.behavior_to_json behavior in
  List.iter2 (fun (source:D.declaration) candidate ->
    let expected=Json.Object (List.filter (fun (key,_) -> key<>"$type") (Json.object_fields source.value)) in
    require (Json.equal expected (get "data" candidate)) "Producer operands differ from original authority")
    original (items "nodes" raw);
  List.iter (fun key -> require (Json.equal (get key raw) (get key (A.source_assessment admitted)))
    ("Lowering dropped source assessment ledger: "^key)) ["assumptions";"unresolved_obligations"];
  incr count
let mutation_controls document =
  let raw=D.to_json document in
  let declarations=items "declarations" (source_program raw) in
  let rule=List.find (fun declaration -> text "$type" declaration="Rule") declarations in
  let observation=List.find (fun declaration -> text "$type" declaration="Observation") declarations in
  let guard=get "when" rule in
  let identity=text "id" rule in
  let check label transform=reject label (fun () ->
    let changed=change_declaration identity transform raw in
    T.elaborate ~charge:no_charge (D.of_json changed)) in
  check "wrong predicate category" (fun rule -> replace "when" (get "on" rule) rule);
  check "wrong trigger category" (fun rule -> replace "on" guard rule);
  check "unsupported executable opcode" (fun rule -> replace "when" (replace "op" (str "add") guard) rule);
  check "wrong arity" (fun rule -> replace "when" (replace "args" (Json.Array [guard]) guard) rule);
  let observation_expression=replace "ref" (get "executor" rule) guard in
  check "reference kind" (fun rule -> replace "when" observation_expression rule);
  (* A typed scalar read must agree with the resolved declaration, even without
     invoking source admission. Different scalar categories cannot be encoded. *)
  let integer_type=replace "kind" (str "integer") (get "value_type" observation) in
  let bad_type=replace "value_type" integer_type guard in
  check "resolved scalar category" (fun rule -> replace "when" bad_type rule)
let exhaustion document =
  let charges=ref [] in
  ignore (T.elaborate ~charge:(fun n -> require (n>=0) "Negative typed charge";charges:=n::!charges) document);
  let total=List.length !charges in
  require (total>20 && List.exists (fun n -> n>1) !charges) "Typed work is not metered";
  List.iter (fun stop ->
    let calls=ref 0 in
    let marker={Diagnostic.code="typed_stop";message="injected exhaustion";path=None} in
    match T.elaborate ~charge:(fun _ -> incr calls;if !calls=stop then raise (Diagnostic.Error marker)) document with
    | _ -> failwith "Exhaustion returned a partial typed value"
    | exception Diagnostic.Error actual -> require (actual==marker && !calls=stop) "Typed elaboration swallowed or delayed exhaustion")
    [1;total/2;total]
let retained_obligation document descriptors =
  let raw=D.to_json document in
  let requirement=List.find (fun declaration -> text "$type" declaration="Requirement" &&
    get "response" declaration<>Json.Null) (items "declarations" (source_program raw)) in
  let response=get "response" requirement in
  let changed=change_declaration (text "id" requirement)
    (replace "response" (replace "value" (str "outcome") response)) raw in
  let document=D.of_json changed in
  (* This valid source obligation is intentionally outside the executable
     lifecycle selector subset. Admission retains it for requirement checking. *)
  require (text "status" (Bioc_checker.Policy_check.check document)="valid")
    "Unsupported obligation control lost generic source validity";
  roundtrip document descriptors
let event_value_rejections document descriptors =
  let raw=D.to_json document in
  let declarations=items "declarations" (source_program raw) in
  let rule=List.find (fun value -> text "$type" value="Rule") declarations in
  let effect_value=List.find (fun value -> text "$type" value="Effect") declarations in
  let check label raw definitions expected_path expected_message =
    let document=D.of_json raw in
    require (text "status" (Bioc_checker.Policy_check.check document)="valid")
      (label^": control is not independently source-valid");
    match A.admit ~document ~descriptors:(O.descriptors_of_json definitions) with
    | _ -> failwith (label^": runtime-unusable event-as-value source was admitted")
    | exception Diagnostic.Error diagnostic ->
        require (diagnostic.code="policy_operational_unsupported" && diagnostic.path=Some expected_path &&
          diagnostic.message=expected_message) (label^": rejection occurred outside the explicit scalar admission guard") in
  let event=get "on" rule in
  let comparison=get "when" rule |> replace "op" (str "eq") |> replace "args" (Json.Array [event;event])
    |> replace "ref" Json.Null |> replace "scope" Json.Null in
  let changed=change_declaration (text "id" rule) (replace "when" comparison) raw in
  let path_of identity=(List.find (fun (d:D.declaration) -> d.id=identity) (D.declarations (A.document (A.admit ~document ~descriptors)))).path in
  check "event comparison" changed (O.descriptors_to_json descriptors) (path_of (text "id" rule)^"/when/args")
    "Operational comparisons require scalar operands; events are triggers, not scalar values.";
  (* Change both the explicit formal signature and actual argument, and freshly
     pin that complete supplied definition. Thus source validity cannot be
     satisfied by an earlier type/signature mismatch. *)
  let definition_id=text "id" (get "contract" effect_value) in
  let semantics=get "semantics" (source_program raw) in
  let definitions=items "definitions" semantics in
  let definition=List.find (fun value -> text "id" value=definition_id) definitions in
  let formal=Json.Object ["$type",str "Parameter";"id",str "event_argument";
    "value_type",get "value_type" event;"selection",str "fixed";
    "value",Json.Null;"lower",Json.Null;"upper",Json.Null] in
  let definition=replace "parameters" (Json.Array [formal]) definition in
  let digest=D.document_digest definition in
  let rec repin value=match value with
    | Json.Object fields ->
        let updated=Json.Object (List.map (fun (key,value) -> key,repin value) fields) in
        if List.assoc_opt "$type" fields=Some (str "DefinitionRef") && List.assoc_opt "id" fields=Some (str definition_id)
        then replace "digest" (str digest) updated else updated
    | Json.Array values -> Json.Array (List.map repin values)
    | value -> value in
  let semantics=replace "definitions" (Json.Array (List.map (fun value ->
    if text "id" value=definition_id then definition else value) definitions)) semantics in
  let updated=replace "semantics" semantics raw in
  let argument=Json.Object ["$type",str "Argument";"name",str "event_argument";"value",event] in
  let updated=change_declaration (text "id" effect_value)
    (replace "parameters" (Json.Array [argument])) updated |> repin in
  check "event effect argument" updated (repin (O.descriptors_to_json descriptors))
    (path_of (text "id" effect_value)^"/parameters/0/value")
    "Operational effect arguments require scalar values; event-valued arguments have no execution semantics."
let ()=
  require (Array.length Sys.argv=4) "Supply operational, staged and binding fixture authorities";
  let basic=read Sys.argv.(1) and staged=read Sys.argv.(2) and binding=read Sys.argv.(3) in
  let document=D.of_json (get "document" basic) and descriptors=O.descriptors_of_json (get "definitions" basic) in
  roundtrip document descriptors;
  mutation_controls document;
  exhaustion document;
  retained_obligation document descriptors;
  event_value_rejections document descriptors;
  roundtrip (D.of_json (get "document" staged)) (O.descriptors_of_json (get "definitions" staged));
  List.iter (fun row -> let request=R.of_json (get "request" row) in
    roundtrip (R.document request) (R.definitions request)) (items "cases" binding);
  Printf.printf "Closed typed policy admission/lowering: %d original-source reconstructions, resolved references, typed rejection and metered exhaustion\n" !count

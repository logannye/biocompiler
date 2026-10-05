open Bioc_wire
module D = Bioc_domain.Policy_document
module C = Bioc_checker.Policy_check
let require condition message = if not condition then failwith message
let str x = Json.String x
let obj x = Json.Object x
let arr x = Json.Array x
let field key value = Json.field key (Json.object_fields value)
let text key value = Json.string (field key value)
let items key value = Json.array (field key value)
let replace key replacement value = obj (List.map (fun (name,x) -> name,(if name=key then replacement else x)) (Json.object_fields value))
let add items value = replace "declarations" (arr (Json.array (field "declarations" value) @ items)) value
let change identity key replacement program = replace "declarations" (arr (List.map (fun d -> if text "id" d = identity then replace key replacement d else d) (items "declarations" program))) program
let named identity program = List.find (fun d -> text "id" d = identity) (items "declarations" program)
let reference kind identity = obj ["$type",str "Ref";"kind",str kind;"id",str identity]
let type_spec kind unit = obj ["$type",str "TypeSpec";"kind",str kind;"unit",unit;"entity_kind",Json.Null]
let expr op value_type args = obj ["$type",str "Expr";"op",str op;"value_type",value_type;"args",arr args;
  "ref",Json.Null;"value",Json.Null;"scope",Json.Null;"contract",Json.Null;"duration",Json.Null;"clock",Json.Null;"coverage",Json.Null;"binding",Json.Null]
let truth = type_spec "truth" Json.Null
let yes = replace "value" (Json.Bool true) (expr "literal" truth [])
let analyze raw = C.check (D.of_json ~path:"/document" raw)
let valid raw = let result = analyze raw in
  require (field "status" result = str "valid") ("Unexpected invalid native source: " ^ Canonical.encode (field "diagnostics" result)); result
let rejects code raw =
  let result = analyze raw in
  require (field "status" result = str "invalid") ("Accepted mutation: " ^ code);
  require (List.exists (fun d -> field "code" d = str code) (items "diagnostics" result)) ("Missing independent diagnostic: " ^ code);
  List.iter (fun d -> require (String.starts_with ~prefix:"/document" (text "path" d)) "Diagnostic path lost its source root") (items "diagnostics" result)
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size = in_channel_length channel in require (size <= 8 * 1024 * 1024) "Fixture too large";
    Json.parse_bounded ~max_bytes:(8*1024*1024) ~max_nodes:1_000_000 (really_input_string channel size))
let run request submission corpus =
  let program = field "program" request in
  let initial = valid request in
  require (field "schema_version" initial = str "biocompiler.policy_assessment.v0.1") "Assessment schema differs";
  require (field "document_digest" initial = str "36f9b303bfc869a1a7ce8c72f11eca1a86a5a75ac67c4e55078e2b5db874667a") "Frozen literal request identity differs";
  List.iter (fun (name,value) -> require (field name initial = str value) ("Inflated native claim: " ^ name))
    ["semantic_status","unresolved";"target_status","unassessed";"lowering","unsupported";"artifact","withheld"];
  require (List.map (text "id") (items "declarations" initial) = ["executor";"available_time";"encounter/target";"encounter";"disease";"exclusion";"effect";"gate/respond";"permission";"response_progress"]) "Ordered declaration ledger differs";
  require (List.map (text "id") (items "requirements" initial) = ["permission";"response_progress"]) "Requirement ledger omits or reorders obligations";
  List.iter2 (fun source ledger -> require (Json.equal source (field "value" ledger)) "Ledger changed a source declaration";
    require (items "sources" ledger <> []) "Ledger dropped source correspondence") (items "declarations" program) (items "declarations" initial);
  require (List.mem (str "policy_execution_and_lowering") (items "unresolved_obligations" initial)) "Execution obligation disappeared";
  require (List.mem (str "requirement_satisfaction:response_progress") (items "unresolved_obligations" initial)) "Progress was promoted into proof";
  ignore (valid submission);
  let hidden_obligations = valid (replace "outstanding_obligations" (arr []) submission) in
  require (Json.equal (field "unresolved_obligations" hidden_obligations) (field "unresolved_obligations" initial)) "Caller erased independently reconstructed semantic obligations";
  rejects "submission_features" (replace "required_features" (arr []) submission);
  rejects "submission_assumptions" (replace "assumptions" (arr [str "forged authority"]) submission);
  rejects "duplicate_declaration" (add [List.hd (items "declarations" program)] program);
  rejects "missing_reference" (change "gate/respond" "effects" (arr [reference "Effect" "missing"]) program);
  rejects "observation_access" (change "disease" "access" (str "external_evaluator") program);
  rejects "expression_scope" (change "gate/respond" "when" (replace "scope" (reference "Role" "executor") (replace "ref" (reference "Observation" "disease") (expr "observe" truth []))) program);
  rejects "guard_type" (change "gate/respond" "when" (expr "rising" (type_spec "event" Json.Null) [yes]) program);
  let effect_value = named "effect" program in
  let lifecycle = field "lifecycle" effect_value |> replace "cancellation" (str "unsupported") |> replace "on_loss" (str "request_cancel") in
  rejects "cancellation_contract" (change "effect" "lifecycle" lifecycle program);
  let req = named "response_progress" program in
  rejects "requirement_deadline_anchor" (change "response_progress" "clock" Json.Null program);
  rejects "requirement_trigger" (change "response_progress" "trigger" yes program);
  require (field "deadline" req <> Json.Null) "Deadline mutation lacks its precondition";
  let deployment = field "deployment" request |> replace "bindings" (arr []) in
  rejects "deployment_role_coverage" (replace "deployment" deployment request);
  let semantics = field "semantics" program in
  let defs = items "definitions" semantics in
  let altered = replace "meaning" (str "Changed supplied meaning under stale pin") (List.hd defs) in
  rejects "definition_identity" (replace "semantics" (replace "definitions" (arr (altered :: List.tl defs)) semantics) program);
  let formal = obj ["$type",str "Parameter";"id",str "private";"value_type",truth;"value",Json.Null;"lower",Json.Null;"upper",Json.Null;"selection",str "fixed"] in
  let private_definition = List.hd defs |> replace "id" (str "gate/respond") |> replace "parameters" (arr [formal]) in
  let with_private = replace "semantics" (replace "definitions" (arr (defs @ [private_definition])) semantics) program in
  ignore (valid with_private);
  rejects "missing_reference" (change "gate/respond" "when" (replace "ref" (reference "Parameter" "private") (expr "parameter" truth [])) with_private);
  let second = field "unit" (field "resolution" (named "available_time" program)) in
  let minute = second |> replace "id" (str "min") |> replace "scale" (str "60") in
  let amount n unit = obj ["$type",str "Quantity";"amount",str n;"unit",unit] in
  let parameter = formal |> replace "id" (str "elapsed") |> replace "value_type" (type_spec "quantity" second)
    |> replace "value" (amount "120" second) |> replace "lower" (amount "2" minute) |> replace "upper" (amount "3" minute) in
  ignore (valid (add [parameter] program));
  rejects "parameter_bound_value" (add [replace "lower" (amount "3" minute) parameter] program);
  let subject id identity entity_kind domain = obj ["$type",str "Subject";"id",str id;"entity_kind",str entity_kind;"identity",str identity;"executor",Json.Null;"encounter",Json.Null;"domain",domain] in
  let domain = reference "Subject" "population" and binding = reference "Subject" "member" in
  let observation = named "disease" program |> replace "id" (str "member_observation") |> replace "subject" binding in
  let member_expr = expr "observe" truth [] |> replace "ref" (reference "Observation" "member_observation") |> replace "scope" binding in
  let quantified = expr "exists" truth [member_expr] |> replace "scope" domain |> replace "binding" binding in
  let quantifier_program = add [subject "population" "aggregate" "population" Json.Null;subject "member" "bound" "cell" domain;observation] program in
  ignore (valid (change "gate/respond" "when" quantified quantifier_program));
  rejects "unbound_subject" (change "gate/respond" "when" member_expr quantifier_program);
  rejects "unused_quantifier_binding" (change "gate/respond" "when" (replace "args" (arr [yes]) quantified) quantifier_program);
  let rule = named "gate/respond" program in
  let policy = field "arbitration" rule in
  let scope = obj ["$type",str "Scope";"kind",str "executor";"subject",reference "Role" "executor"] in
  let store = obj ["$type",str "StateStore";"id",str "store";"value_type",truth;"scope",scope;"initial",Json.Bool false;"capacity",Json.int 1;
    "overflow",str "reject";"lifetime",str "executor";"reset",Json.Null;"inheritance",str "not_applicable";"duration",Json.Null;"contract",Json.Null;"coordination",Json.Null] in
  let assignment = obj ["$type",str "Assignment";"state",reference "StateStore" "store";"value",yes] in
  ignore (valid (change "gate/respond" "assignments" (arr [assignment]) (add [store] program)));
  rejects "duplicate_assignment" (change "gate/respond" "assignments" (arr [assignment;assignment]) (add [store] program));
  let machine = obj ["$type",str "Machine";"id",str "machine";"executor",reference "Role" "executor";"scope",scope;"states",arr [str "ready";str "done"];"initial",str "ready";"terminal",arr [str "done"];"lifetime",str "executor";"arbitration",policy] in
  let transition = obj ["$type",str "Transition";"id",str "start";"machine",reference "Machine" "machine";"source",str "ready";"destination",str "done";"on",field "on" rule;"when",field "when" rule;"unknown",str "defer";"effects",field "effects" rule;"assignments",arr [];"unknown_target",Json.Null;"emissions",arr []] in
  ignore (valid (add [machine;transition] program));
  rejects "missing_arbitration" (add [machine;transition] (change "gate/respond" "arbitration" Json.Null program));
  rejects "arbitration_order" (change "gate/respond" "arbitration" (replace "mode" (str "priority") policy) program);
  let empty = program |> replace "declarations" (arr []) |> replace "source_map" (arr []) in
  let empty_result = valid empty in require (items "unresolved_obligations" empty_result <> []) "Empty source gained executable acceptance";
  let cases = items "cases" corpus in
  require (List.length cases = 24) "Missing frozen program/request/submission controls";
  List.iter (fun case -> ignore (valid (field "document" case))) cases;
  let coordinated = List.find (fun case -> text "name" case = "coordinated_populations" && text "kind" case = "program") cases |> field "document" in
  let private_store = store |> replace "scope" (replace "subject" (reference "Role" "receiver") scope) in
  rejects "executor_ownership" (change "message" "correlation" (reference "StateStore" "store") (add [private_store] coordinated));
  Printf.printf "policy checker: ordered source ledger, exact quantities, binding/access/arbitration/deadline mutations, claim tampering and 24 retained documents checked\n"
let () = match Array.to_list Sys.argv with
  | [_;request;submission;corpus] -> run (read request) (read submission) (read corpus)
  | _ -> failwith "Usage: test_policy_check.exe request.json submission.json policy_documents_v01.json"

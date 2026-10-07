open Bioc_wire
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module A = Bioc_checker.Policy_admission
module L = Bioc_compiler.Policy_lowering
module C = Bioc_checker.Policy_correspondence
module E = Bioc_semantics.Policy_execution
module S = Bioc_service.Policy_operational_service

let require condition message = if not condition then failwith message
let str value = Json.String value
let obj fields = Json.Object fields
let arr values = Json.Array values
let get name value = Json.field name (Json.object_fields value)
let text name value = Json.string (get name value)
let items name value = Json.array (get name value)
let named identity values = List.find (fun value -> text "id" value = identity) values
let replace name replacement value = obj (List.map (fun (key,item) ->
  key,if key=name then replacement else item) (Json.object_fields value))
let rejects code action = match action () with
  | _ -> failwith ("Expected native rejection: " ^ code)
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code=code) ("Wrong native rejection: " ^ diagnostic.code ^ " expected " ^ code)

let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size = in_channel_length channel in
    require (size <= 2*1024*1024) "Realization source fixture exceeds its bound";
    Json.parse_bounded ~max_bytes:(2*1024*1024) ~max_nodes:100000
      (really_input_string channel size))

let rec at_path value = function
  | [] -> value
  | Json.String key::rest -> at_path (get key value) rest
  | Json.Int index::rest -> at_path (List.nth (Json.array value) (Z.to_int index)) rest
  | _ -> failwith "Invalid source-edit literal path"
let rec edit_path value path replacement = match path with
  | [] -> replacement
  | Json.String key::rest -> replace key (edit_path (get key value) rest replacement) value
  | Json.Int index::rest -> arr (List.mapi (fun number child ->
      if number=Z.to_int index then edit_path child rest replacement else child) (Json.array value))
  | _ -> failwith "Invalid source-edit literal path"

let source_only_report report =
  List.iter (fun (key,expected) -> require (text key report=expected)
    ("Source-only realization witness upgraded " ^ key))
    ["artifact","withheld";"target_status","unassessed";"realization","unassessed"];
  let assessment = get "source_assessment" report in
  require (text "semantic_status" assessment="unresolved") "Reference execution changed source-assessment meaning";
  require (List.mem (str "requested_assurance_not_established") (items "unresolved_obligations" assessment))
    "Bounded timeline execution discharged original requested assurance"

let checked raw definitions =
  let document = D.of_json ~path:"/document" raw in
  require (D.kind document=D.Request) "Realization source witness lost its complete BuildRequest";
  let assessment = Bioc_checker.Policy_check.check document in
  require (text "status" assessment="valid") "Realization witness failed native source checking";
  let descriptors = O.descriptors_of_json definitions in
  let behavior = L.lower (A.admit ~document ~descriptors) in
  let correspondence = C.check ~expected_document:document ~descriptors behavior in
  require (text "status" correspondence="valid") "Source lowering lost independently checked correspondence";
  let candidate = O.behavior_to_json behavior in
  require (Json.equal (get "source_document" candidate) raw) "Candidate replaced complete original authority";
  List.iter (fun key -> require (Json.equal (get key (get "source_document" candidate)) (get key raw))
    ("Candidate lost original request field: " ^ key)) ["program";"deployment";"implementations";"assurance"];
  require (text "source_artifact_digest" candidate=D.artifact_digest document) "Candidate lost full source-artifact identity";
  require (List.length (items "nodes" candidate)=List.length (D.declarations document)) "Candidate dropped a source occurrence";
  let payload = obj ["document",raw;"definitions",definitions;"candidate",candidate] in
  let result = S.handle ~operation:"check-policy-lowering" payload in
  source_only_report (get "report" result);
  require (Json.equal (get "correspondence" (get "report" result)) correspondence) "Service replaced independent correspondence";
  document,descriptors,behavior

let execute raw definitions behavior timeline =
  let candidate = O.behavior_to_json behavior in
  let fields = ["document",raw;"definitions",definitions;"candidate",candidate;"timeline",timeline] in
  let result = S.handle ~operation:"execute-policy" (obj fields) in
  let report = get "report" result in
  source_only_report report;
  let execution = get "execution" report in
  require (text "claim" execution="bounded_supplied_timeline_only") "Timeline witness became a whole-domain proof";
  require (text "timeline_digest" execution=Canonical.fingerprint timeline) "Execution lost literal timeline authority";
  require (text "behavior_digest" execution=Canonical.fingerprint candidate) "Execution lost full candidate authority";
  require (Json.equal execution (E.execute behavior timeline)) "Service changed direct reference execution";
  let replayed = S.handle ~operation:"replay-policy-execution" (obj (fields @ ["report",report])) in
  require (Json.equal result replayed) "Fresh source-witness replay changed its complete report";
  execution

let frame time execution = List.find (fun value -> text "time" value=time) (items "frames" execution)
let requirement identity execution = named identity (items "requirements" execution)
let events kind execution = List.concat_map (fun current ->
  List.filter_map (fun event -> if text "kind" event=kind then Some (current,event) else None)
    (items "events" current)) (items "frames" execution)
let request_projection execution = arr (List.map (fun attempt -> obj [
  "encounter",get "encounter" (get "binding" attempt);"subject",get "subject" attempt;
  "time",get "started_at" attempt;"product",get "product" (get "parameters" attempt)]) (items "attempts" execution))

let check_timeline raw definitions behavior case =
  let expected = get "literal_expectations" case in
  require (text "status" expected="unvalidated_source_semantics_expectation") "Fixture expectations grant prior acceptance";
  let execution = execute raw definitions behavior (get "timeline" case) in
  require (Json.equal (request_projection execution) (get "requests" expected)) ("Request literals differ: " ^ text "id" case);
  let attempts = items "attempts" execution in
  List.iteri (fun index attempt ->
    require (text "id" attempt="attempt/" ^ string_of_int (index+1)) "Fresh correlated attempt identity differs";
    require (text "effect" attempt="response" && text "executor" attempt="cell-1") "Literal request used wrong effect/executor") attempts;
  List.iter (fun phase ->
    let phase_events = events phase execution in
    require (List.length phase_events=List.length attempts) ("Missing or extra effect event: " ^ phase);
    List.iter2 (fun (current,event) attempt ->
      require (get "attempt" event=get "id" attempt && text "declaration" event="response") "Lifecycle event lost correlated attempt";
      require (Json.equal (get "binding" event) (get "binding" attempt)) "Lifecycle event crossed encounter bindings";
      require (get "time" current=get "started_at" attempt) "Request/initiation moved from its expected tick") phase_events attempts)
    ["requested";"initiated"];
  require (Json.equal (arr (List.map (fun (current,_) -> get "time" current) (events "initiated" execution)))
    (get "initiations" expected)) "Initiation timeline differs";
  require (Json.equal (arr (List.map (get "status") attempts)) (get "terminal_outcomes" expected)) "Terminal feedback/timeout literals differ";
  let expected_requirements = Json.object_fields (get "requirements" expected) in
  require (List.length (items "requirements" execution)=List.length expected_requirements) "Execution omitted/added source requirements";
  List.iter (fun (identity,status) -> require (get "status" (requirement identity execution)=status)
    ("Literal requirement result differs: " ^ text "id" case ^ "/" ^ identity)) expected_requirements;
  (match List.assoc_opt "settled_memory_at_one" (Json.object_fields expected) with
   | None ->
       require (Z.sign (Json.integer (get "unknown" (get "coverage" (requirement "scoped_memory" execution))))>0)
         "Unknown-before-response history silently became fully known";
       List.iter (fun identity -> require (get "triggers" (get "coverage" (requirement identity execution))=Json.int 0)
         "No-trigger history manufactured progress coverage") ["request_progress";"initiation_progress";"request_authorization"]
   | Some states ->
       let snapshot = frame "1" execution in
       List.iter (fun (encounter,value) ->
         let state = List.find (fun state -> text "state" state="seen" &&
           get "encounter" (get "binding" state)=str encounter) (items "states" snapshot) in
         require (get "value" state=value) "Encounter-scoped settled memory differs") (Json.object_fields states);
       let obligations = items "obligations" (requirement "request_authorization" execution) in
       require (Json.equal (arr (List.map (get "closed_at") obligations)) (get "authorization_closed_at" expected))
         "Positive authorization witness did not close at the literal tick";
       List.iter (fun obligation -> require (get "opened_at" obligation=get "closed_at" obligation)
         "Positive authorization witness was satisfied only by later evidence") obligations;
       List.iter (fun identity -> require (get "triggers" (get "coverage" (requirement identity execution))=Json.int 2)
         "Positive progress witness was vacuous or duplicated") ["request_progress";"initiation_progress";"request_authorization"]);
  execution

let check_edits fixture baseline_document baseline_descriptors baseline_behavior baseline_execution =
  let raw = get "document" fixture and definitions = get "definitions" fixture in
  let base_timeline = get "timeline" (named "completion_and_timeout" (items "timelines" fixture)) in
  let edits = items "source_edits" fixture in
  require (List.sort String.compare (List.map (text "id") edits)=
    List.sort String.compare ["opposite_guard";"lost_memory_write";"different_product";"longer_assurance";
                              "unknown_assurance_requirement";"stale_effect_definition"]) "Source-edit census changed";
  List.iter (fun case ->
    let identity = text "id" case and path = items "path" case in
    require (Json.equal (at_path raw path) (get "before" case)) "Source-edit original value changed";
    let changed = edit_path raw path (get "after" case) in
    require (Json.equal changed (get "document" case)) "Source edit changed more than its declared operand";
    let document = D.of_json changed in
    require (D.artifact_digest document<>D.artifact_digest baseline_document) "Source edit retained original artifact identity";
    let assessment = Bioc_checker.Policy_check.check document in
    if text "expected_authoring_status" case="invalid" then (
      require (text "status" assessment="invalid") ("Native source-invalid edit was accepted: " ^ identity);
      let actual_codes = List.map (text "code") (items "diagnostics" assessment) in
      List.iter (fun code -> require (List.mem (Json.string code) actual_codes)
        ("Source-invalid signature differs: " ^ identity)) (items "required_diagnostics" case);
      rejects "policy_operational_source_invalid" (fun () -> A.admit ~document ~descriptors:baseline_descriptors))
    else (
      require (text "status" assessment="valid") ("Source-valid edit became invalid: " ^ identity);
      rejects "policy_correspondence" (fun () -> C.check ~expected_document:document ~descriptors:baseline_descriptors baseline_behavior);
      let _,_,behavior = checked changed definitions in
      let execution = execute changed definitions behavior base_timeline in
      match identity with
      | "opposite_guard" ->
          require (items "attempts" execution=[]) "Opposite guard still requested the product";
          List.iter (fun requirement_id -> require (text "status" (requirement requirement_id execution)="fail")
            "Opposite guard hid required response/state violations") ["request_progress";"scoped_memory"]
      | "lost_memory_write" ->
          require (Json.equal (request_projection execution) (request_projection baseline_execution)) "Memory-only mutation changed literal requests";
          require (text "status" (requirement "scoped_memory" execution)="fail") "Lost memory assignment passed safety"
      | "different_product" ->
          require (List.length (items "attempts" execution)=2) "Product edit lost its positive request witnesses";
          List.iter (fun attempt -> require (get "product" (get "parameters" attempt)=str "fixture.product.beta")
            "Changed fixed product failed to reach actual attempt parameters") (items "attempts" execution)
      | "longer_assurance" ->
          require (text "amount" (get "horizon" (get "assurance" changed))="5") "Longer assurance was truncated";
          List.iter (fun key -> require (Json.equal (get key execution) (get key baseline_execution))
            "Assurance-only edit changed reference behavior") ["frames";"attempts";"requirements"]
      | _ -> failwith "Unclassified source-valid edit")) edits

let () =
  require (Array.length Sys.argv=2) "Supply the independent complete realization-source fixture";
  let fixture = read Sys.argv.(1) in
  require (text "fixture_version" fixture="biocompiler.policy_realization_source_literals.v0.1") "Wrong realization-source fixture profile";
  require (text "stage" fixture="source_authority_only" && text "artifact" fixture="withheld") "Source fixture acquired material authority";
  List.iter (fun pending -> require (List.mem (str pending) (items "pending_authorities" fixture))
    ("Missing downstream authority was hidden: " ^ pending))
    ["closed_executable_operating_domain";"independent_implementation_models";"complete_mrna_template_roots_and_chemistry"];
  require (List.length (items "coverage_limits" fixture)=3) "Source/domain/authorization limits were dropped";
  let raw = get "document" fixture and definitions = get "definitions" fixture in
  require (items "implementations" (get "implementations" raw)=[]) "Source fixture silently supplied implementation models";
  let document,descriptors,behavior = checked raw definitions in
  let cases = items "timelines" fixture in
  require (List.sort String.compare (List.map (text "id") cases)=List.sort String.compare
    ["completion_and_timeout";"failure_and_timeout";"both_timeout";"stale_before_response";"invalid_before_response"])
    "Literal timeline census changed";
  let results = List.map (fun case -> text "id" case,check_timeline raw definitions behavior case) cases in
  check_edits fixture document descriptors behavior (List.assoc "completion_and_timeout" results);
  print_endline "Complete policy request, bounded source witnesses and edits passed; implementation/material authority remains unassessed"

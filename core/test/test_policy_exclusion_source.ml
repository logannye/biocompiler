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
let get key value = Json.field key (Json.object_fields value)
let text key value = Json.string (get key value)
let items key value = Json.array (get key value)
let named identity values = List.find (fun value -> text "id" value=identity) values
let rejects code action = match action () with
  | _ -> failwith ("Expected exclusion control rejection: " ^ code)
  | exception Diagnostic.Error diagnostic -> require (diagnostic.code=code)
      ("Wrong exclusion control diagnostic: " ^ diagnostic.code ^ " expected " ^ code)
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size = in_channel_length channel in
    require (size <= 2*1024*1024) "Exclusion source fixture exceeds its bound";
    Json.parse_bounded ~max_bytes:(2*1024*1024) ~max_nodes:100000 (really_input_string channel size))
let scope report =
  List.iter (fun (key,value) -> require (text key report=value) ("Exclusion source witness upgraded " ^ key))
    ["artifact","withheld";"target_status","unassessed";"realization","unassessed"];
  require (List.mem (str "requested_assurance_not_established")
    (items "unresolved_obligations" (get "source_assessment" report))) "Literal timelines established full assurance"
let compile raw definitions =
  let document = D.of_json raw and descriptors = O.descriptors_of_json definitions in
  require (D.kind document=D.Request) "Exclusion witness omitted original BuildRequest";
  require (text "status" (Bioc_checker.Policy_check.check document)="valid") "Exclusion source lost native validity";
  let behavior = L.lower (A.admit ~document ~descriptors) in
  let correspondence = C.check ~expected_document:document ~descriptors behavior in
  require (text "status" correspondence="valid") "Exclusion lowering failed independent correspondence";
  let candidate = O.behavior_to_json behavior in
  require (Json.equal (get "source_document" candidate) raw) "Exclusion lowering dropped full original authority";
  scope (S.lowering_report ~document ~correspondence);
  document,descriptors,behavior
let execute raw definitions behavior timeline =
  let fields = ["document",raw;"definitions",definitions;"candidate",O.behavior_to_json behavior;"timeline",timeline] in
  let result = S.handle ~operation:"execute-policy" (obj fields) in
  let report = get "report" result in
  scope report;
  let execution = get "execution" report in
  require (text "claim" execution="bounded_supplied_timeline_only") "Exclusion witness became whole-domain proof";
  require (Json.equal execution (E.execute behavior timeline)) "Service changed direct exclusion execution";
  require (Json.equal result (S.handle ~operation:"replay-policy-execution" (obj (fields @ ["report",report]))))
    "Fresh exclusion replay changed complete authority or results";
  execution
let frame time execution = List.find (fun value -> text "time" value=time) (items "frames" execution)
let state name encounter snapshot = List.find (fun value -> text "state" value=name &&
  get "encounter" (get "binding" value)=str encounter) (items "states" snapshot)
let requirement identity execution = named identity (items "requirements" execution)
let requests execution = arr (List.map (fun attempt -> obj ["encounter",get "encounter" (get "binding" attempt);
  "subject",get "subject" attempt;"time",get "started_at" attempt;"product",get "product" (get "parameters" attempt)]) (items "attempts" execution))
let events phase execution = List.concat_map (fun current -> List.filter_map (fun event ->
  if text "kind" event=phase then Some (current,event) else None) (items "events" current)) (items "frames" execution)

let check_case raw definitions behavior case =
  let execution = execute raw definitions behavior (get "timeline" case) in
  let expected = get "literal_expectations" case in
  require (text "status" expected="unvalidated_source_semantics_expectation") "Fixture expectations supplied prior acceptance";
  require (Json.equal (requests execution) (get "requests" expected)) ("Exclusion requests differ: " ^ text "id" case);
  let attempts = items "attempts" execution in
  require (Json.equal (arr (List.map (get "status") attempts)) (get "terminal_outcomes" expected)) "Failure/timeout outcomes differ";
  List.iter (fun phase ->
    let observed = events phase execution in
    require (List.length observed=List.length attempts) "Exclusion created or lost request/initiation events";
    List.iter2 (fun (current,event) attempt ->
      require (get "attempt" event=get "id" attempt && get "time" current=get "started_at" attempt)
        "Request/initiation lost attempt or tick correlation";
      require (Json.equal (get "binding" event) (get "binding" attempt)) "Request/initiation changed encounter identity") observed attempts)
    ["requested";"initiated"];
  List.iter (fun literal ->
    let snapshot = frame (text "time" literal) execution in
    List.iter (fun encounter -> List.iter (fun name ->
      require (get "value" (state name encounter snapshot)=get name (get encounter literal))
        ("State literal differs: " ^ text "id" case ^ "/" ^ encounter ^ "/" ^ name)) ["selected";"excluded"])
      ["e1";"e2"]) (items "state_frames" expected);
  List.iter (fun snapshot -> List.iter (fun encounter ->
    let selected = Json.boolean (get "value" (state "selected" encounter snapshot))
    and excluded = Json.boolean (get "value" (state "excluded" encounter snapshot)) in
    require (not (selected && excluded)) "Positive exclusion witness has simultaneously true flags") ["e1";"e2"])
    (items "frames" execution);
  require (Json.equal (get "active_attempts" (frame "2" execution)) (get "active_at_two" expected))
    "Exclusion incorrectly stopped or created an active product attempt";
  List.iter (fun evidence -> require (get "value" evidence=Json.Null)
    "Quiet/invalid final evidence was silently kept known") (items "evidence" (frame "6" execution));
  let statuses = Json.object_fields (get "requirements" expected) in
  require (List.length (items "requirements" execution)=List.length statuses) "Exclusion requirement ledger is incomplete";
  List.iter (fun (identity,status) -> require (get "status" (requirement identity execution)=status)
    ("Exclusion requirement differs: " ^ text "id" case ^ "/" ^ identity)) statuses;
  let coverage = get "coverage" (requirement "exclusive_selection" execution) in
  require (get "unknown" coverage=Json.int 0 && get "false" coverage=Json.int 0 && get "true" coverage=Json.int 14)
    "Defined state exclusion became uncertain or incompletely sampled";
  List.iter (fun identity -> require (get "triggers" (get "coverage" (requirement identity execution))=Json.int (List.length attempts))
    "Exclusion progress manufactured/dropped trigger coverage") ["request_progress";"initiation_progress"]

let () =
  require (Array.length Sys.argv=2) "Supply the independent exclusion source fixture";
  let fixture = read Sys.argv.(1) in
  require (text "fixture_version" fixture="biocompiler.policy_exclusion_source_literals.v0.1") "Wrong exclusion fixture profile";
  require (text "stage" fixture="source_authority_only" && text "artifact" fixture="withheld") "Exclusion fixture acquired material authority";
  List.iter (fun pending -> require (List.mem (str pending) (items "pending_authorities" fixture))
    "Exclusion witness hid missing downstream authority")
    ["closed_executable_operating_domain";"independent_implementation_models";"complete_mrna_template_roots_and_chemistry"];
  let raw = get "document" fixture and definitions = get "definitions" fixture in
  require (items "implementations" (get "implementations" raw)=[]) "Exclusion witness supplied an unreviewed implementation";
  let _,descriptors,behavior = compile raw definitions in
  let cases = items "timelines" fixture in
  require (List.sort String.compare (List.map (text "id") cases)=List.sort String.compare
    ["failure_and_timeouts";"exclusion_preserves_live_attempt";"invalid_after_selection";"missing_without_selection";"invalid_without_selection"])
    "Exclusion timeline census changed";
  List.iter (check_case raw definitions behavior) cases;
  let timeline = get "timeline" (named "failure_and_timeouts" cases) in
  let edits = items "source_edits" fixture in
  require (List.sort String.compare (List.map (text "id") edits)=List.sort String.compare
    ["select_sets_both";"exclude_sets_both";"opposite_select_guard";"simultaneous_opposed_writes"])
    "Exclusion mutation census changed";
  List.iter (fun case ->
    let changed = get "document" case in
    let document,_,candidate = compile changed definitions in
    rejects "policy_correspondence" (fun () -> C.check ~expected_document:document ~descriptors behavior);
    let expected = get "expected_native_result" case in
    match text "kind" expected with
    | "execution_rejection" -> rejects (text "diagnostic" expected) (fun () -> execute changed definitions candidate timeline)
    | "requirement_failure" ->
        let execution = execute changed definitions candidate timeline in
        require (get "status" (requirement (text "id" expected) execution)=get "status" expected)
          ("Exclusion mutation escaped its distinguishing failure: " ^ text "id" case)
    | _ -> failwith "Unclassified exclusion mutation") edits;
  print_endline "Separate state-exclusion source witnesses passed; original safety semantics and material authority remain unchanged"

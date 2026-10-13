open Bioc_wire
module R = Bioc_domain.Policy_controlled_workflow_request
module C = Bioc_domain.Policy_controlled_workflow_candidate
module Original = Bioc_domain.Policy_controlled_composition_request
module BR = Bioc_domain.Policy_controlled_behavior_request
module MC = Bioc_domain.Policy_controlled_material_candidate
module BC = Bioc_domain.Policy_controlled_behavior_candidate
let checks = ref 0
let require condition message = incr checks; if not condition then failwith message
let obj fields = Json.Object fields
let str value = Json.String value
let get key raw = Json.field key (Json.object_fields raw)
let text key raw = Json.string (get key raw)
let set key value raw = obj ((key,value)::List.remove_assoc key (Json.object_fields raw))
let rec edit path change raw = match path with
  | [] -> change raw
  | key::rest -> match raw with
    | Json.Array values -> Json.Array (List.mapi (fun i value ->
        if string_of_int i=key then edit rest change value else value) values)
    | _ -> set key (edit rest change (get key raw)) raw
let put path value = edit path (fun _ -> value)
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    Json.parse_bounded ~max_bytes:4_000_000 ~max_nodes:100_000
      (really_input_string channel (in_channel_length channel)))
let rejects code action = incr checks; match action () with
  | _ -> failwith ("Expected rejection " ^ code)
  | exception Diagnostic.Error diagnostic ->
      if diagnostic.code<>code then failwith ("Expected " ^ code ^ ", got " ^ diagnostic.code)
let refresh raw =
  let behavior = BR.of_json (get "behavior_request" raw) in
  set "limits" (R.project_limits behavior) raw
let proposal request material_fixture behavior_fixture =
  let material = get "literal_candidate" material_fixture
    |> set "request_fingerprint" (str (Original.fingerprint (R.original request))) in
  let behavior = get "literal_candidate" behavior_fixture
    |> set "request_fingerprint" (str (BR.fingerprint (R.behavior request))) in
  C.of_json (obj ["schema_version",str C.schema_version;
    "request_fingerprint",str (R.fingerprint request);
    "material_candidate",material;"behavior_candidate",behavior])

let rebind_material_roles raw =
  let module N = Bioc_domain.Molecule in
  let material=get "material_candidate" raw in
  let inventory=get "inventory"(get "construction" material)in
  let molecules=List.map N.of_json(Json.array(get "molecules" inventory))in
  edit ["material_candidate";"construction";"inventory";"role_instances"](fun rows->
    Json.Array(List.map(fun row->
      let id=text "subject_id" row in
      let molecule=List.find(fun (value:N.t)->N.id value=id)molecules in
      set "subject_fingerprint"(str(N.fingerprint molecule))row)(Json.array rows)))raw

module Check = Bioc_realization_checker.Policy_controlled_workflow_check
module Material = Bioc_checker.Policy_controlled_material_check
module Behavior = Bioc_realization_checker.Policy_controlled_behavior_check
module W = Bioc_checker.Work_budget
let accepted result = Option.is_some(Check.accepted result)
let () =
  require (Array.length Sys.argv=4) "Supply workflow and independent child literals";
  let raw=read Sys.argv.(1) and material=read Sys.argv.(2) and behavior=read Sys.argv.(3) in
  let request=R.of_json raw in
  let candidate=proposal request material behavior in
  let result=Check.check ~request ~candidate () in
  let report=Check.report result in
  require (accepted result && text "status" report="controlled_workflow_accepted" && text "outcome" report="pass")
    "Both fresh original children did not join";
  let m=Material.check ~request:(R.original request) ~candidate:(C.material candidate) () in
  let b=Behavior.check ~request:(R.behavior request) ~candidate:(C.behavior candidate) () in
  require (Json.equal(get "material" report)(Material.report m) && Json.equal(get "behavior" report)(Behavior.report b))
    "Joining altered the original child assessments";
  require (get "project_context" report=get "project_context"(get "source_authority"(Original.raw(R.original request))) &&
    get "limits" report=R.limits request && text "empirical_status" report="unassessed" &&
    text "human_use" report="unassessed" && text "therapeutic_export" report="withheld")
    "Joining lost complete context/limits or upgraded empirical authority";
  require (accepted(Check.replay ~request ~candidate report)) "Fresh joined replay failed";
  rejects "controlled_workflow_assessment_mismatch" (fun()->Check.replay ~request ~candidate
    (set "empirical_status" (str "validated") report));
  let foreign=raw |> put ["behavior_request";"original";"source_authority";"project_context";"title"]
      (str "Foreign project") |> refresh |> R.of_json in
  rejects "controlled_workflow_request_binding" (fun()->Check.check ~request:foreign ~candidate ());
  let outer_repin=C.of_json(set "request_fingerprint" (str(R.fingerprint foreign)) (C.to_json candidate)) in
  rejects "controlled_material_request_binding" (fun()->Check.check ~request:foreign ~candidate:outer_repin ());
  let behavior_foreign=C.to_json candidate |> put ["behavior_candidate";"request_fingerprint"]
      (str(BR.fingerprint(R.behavior foreign))) |> C.of_json in
  rejects "controlled_behavior_request_binding" (fun()->Check.check ~request ~candidate:behavior_foreign ());
  let damaged=C.to_json candidate |> put
    ["material_candidate";"construction";"inventory";"molecules";"0";"sequence"]
    (str "GCAUGGCUUAAGGAAAA") |> rebind_material_roles |> C.of_json in
  let failed=Check.check ~request ~candidate:damaged () in
  require (not(accepted failed) && text "outcome"(Check.report failed)="fail" &&
    text "outcome"(get "behavior"(Check.report failed))="pass" &&
    text "content_outcome"(get "structure"(get "material"(Check.report failed)))="fail" &&
    text "structural_outcome"(get "structure"(get "material"(Check.report failed)))="pass")
    "Behavior PASS hid independently reconstructed material failure";
  let missing=raw |> edit ["behavior_request";"readout_evidence";"samples";"3"]
      (fun row->row |> set "status" (str "missing") |> set "observed_tick" Json.Null) |> refresh |> R.of_json in
  let missing_candidate=proposal missing material behavior in
  let unknown=Check.check ~request:missing ~candidate:missing_candidate () in
  require (not(accepted unknown) && text "outcome"(Check.report unknown)="unknown" &&
    text "outcome"(get "material"(Check.report unknown))="pass")
    "Material PASS hid independently checked behavior unknown";
  let unsupported_candidate=C.to_json candidate |> put
    ["behavior_candidate";"implementation";"primitives";"6";"onset_ticks"] (Json.int 3) |> C.of_json in
  rejects "controlled_behavior_assembly_binding" (fun()->Check.check ~request ~candidate:unsupported_candidate ());
  let used_m=(R.budgets request).max_work-W.remaining(Material.budget m)
  and used_b=(R.budgets request).max_work-W.remaining(Behavior.budget b) in
  let maximum=max used_m used_b+1 in
  let parent ()=W.create ~profile:"independent-test-parent" ~error_code:"joined_parent_limit" ~maximum () in
  ignore(Material.check ~parent:(parent()) ~request:(R.original request) ~candidate:(C.material candidate) ());
  ignore(Behavior.check ~parent:(parent()) ~request:(R.behavior request) ~candidate:(C.behavior candidate) ());
  let cumulative=parent() in
  rejects "joined_parent_limit" (fun()->Check.check ~parent:cumulative ~request ~candidate ());
  require (W.exhausted cumulative) "Joined work exhaustion was not retained by original owner";
  rejects "controlled_workflow_work_limit" (fun()->Check.check ~parent:cumulative ~request ~candidate ());
  let retained=W.create ~retain_bytes:(fun _->()) ~profile:"retained-parent"
    ~error_code:"retained_parent_limit" ~maximum:1 () in
  rejects "retained_parent_limit" (fun()->W.charge retained 2);
  rejects "retained_parent_limit" (fun()->Check.check ~parent:retained ~request ~candidate ());
  rejects "controlled_workflow_cancelled" (fun()->Check.check ~cancelled:(fun()->true) ~request ~candidate ());
  Printf.printf "controlled workflow checker: %d checks\n" !checks

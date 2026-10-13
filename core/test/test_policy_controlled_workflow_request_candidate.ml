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

module P = Bioc_compiler.Policy_controlled_workflow_producer
let () =
  require (Array.length Sys.argv=4) "Supply workflow, independent material and behavior literals";
  let raw=read Sys.argv.(1) and material=read Sys.argv.(2) and behavior=read Sys.argv.(3) in
  let request=R.of_json raw in
  require (Json.equal (R.to_json request) raw && R.fingerprint request=Canonical.fingerprint raw)
    "Complete original request identity changed";
  let literal=proposal request material behavior in
  let charged=ref 0 in
  let actual=P.construct_candidate ~charge:(fun n->charged:= !charged+n) request in
  require (Canonical.encode(C.to_json actual)=Canonical.encode(C.to_json literal))
    "Joined producer differs from independent original child literals";
  require (!charged>C.decoding_work actual) "Construction work is absent";
  require (C.fingerprint(C.of_json(C.to_json literal))=C.fingerprint literal)
    "Candidate roundtrip changed exact bytes";
  List.iter(fun path ->
    let changed=edit ("limits"::path) (fun value ->
      match value with Json.Int n -> Json.Int(Z.succ n) | _ -> failwith "Expected integer limit") raw in
    rejects "controlled_workflow_limits_binding" (fun()->R.of_json changed))
    [["budgets";"max_work"];["budgets";"max_report_bytes"];["budgets";"max_report_nodes"];
     ["domain_limits";"max_work"];["domain_limits";"max_histories"];
     ["horizon_tick"];["intervention_cutoff_tick"];["resources";"max_total_rna_nt"]];
  rejects "unknown_field" (fun()->R.of_json(set "saved_pass" (Json.Bool true) raw));
  rejects "missing_field" (fun()->R.of_json(obj(List.remove_assoc "limits" (Json.object_fields raw))));
  rejects "unknown_field" (fun()->C.of_json(set "report" (obj[]) (C.to_json literal)));
  rejects "controlled_workflow_candidate" (fun()->C.of_json
    (set "request_fingerprint" (str "not-a-digest") (C.to_json literal)));
  let horizon=get "horizon_tick" (R.limits request) in
  let horizon_float=Json.parse (Canonical.encode horizon ^ ".0") in
  rejects "controlled_workflow_limits_binding" (fun()->R.of_json
    (put ["limits";"horizon_tick"] horizon_float raw));
  let changed=raw |> put ["behavior_request";"original";"source_authority";"project_context";"title"]
      (str "Another independent original project") |> refresh |> R.of_json in
  let next=P.construct_candidate ~charge:(fun _->()) changed in
  require (R.fingerprint changed<>R.fingerprint request && C.fingerprint next<>C.fingerprint actual &&
    MC.request_fingerprint(C.material next)=Original.fingerprint(R.original changed) &&
    BC.request_fingerprint(C.behavior next)=BR.fingerprint(R.behavior changed))
    "Complete project original did not bind all candidate layers";
  let cancelled=try ignore(P.construct_candidate ~charge:(fun _->raise Exit) request);false with Exit->true in
  require cancelled "Producer swallowed the shared owner's cancellation";
  Printf.printf "controlled workflow request/candidate: %d checks\n" !checks

open Bioc_wire
open Bioc_policy_component_test_support.Literals
open Bioc_policy_component_test_support.Requests
module Candidate = Bioc_domain.Policy_component_material_candidate
module O = Bioc_domain.Policy_operational
module D = Bioc_domain.Policy_document
module U = Bioc_domain.Policy_implementation_binding
module Q = Bioc_domain.Policy_component_assembly_proposal
module K = Bioc_domain.Construction_content

(* A syntactically complete, deliberately unproved candidate. Its graph,
   binding and material are retained literal fixture data; the empty behavior
   ledger intentionally has no source-preservation claim. No producer/checker
   supplies expected values or a token to these domain codec controls. *)
let literal fixture =
  let child=fst (request_literal fixture false) in
  let original=RR.of_json (get "implementation_request" child) in
  let document=RR.document original and definitions=RR.definitions original in
  let behavior=obj ["schema_version",str "biocompiler.policy_behavior.v0.1";
    "profile",str "biocompiler.policy_operational.v0.1";
    "source_document",D.to_json document;"descriptor_bundle",O.descriptors_to_json definitions;
    "source_artifact_digest",str (D.artifact_digest document);
    "descriptors_digest",str (O.descriptors_digest definitions);
    "nodes",arr [];"source_ledger",arr [];"requirements_ledger",arr [];
    "assumptions",arr [];"unresolved_obligations",arr [str "literal_codec_requires_fresh_check"]] in
  let assembly=obj ["schema_version",str "biocompiler.policy_component_assembly_proposal.v0.1";
    "profile",str "biocompiler.policy_exact_component_assembly.v0.1";
    "rule",at ["composition_rule";"identity"] child;
    "nodes",arr (List.map (fun reference -> add "actual" (get "node" reference) reference) (global_nodes false))] in
  let parts=get "candidate_parts" fixture in
  RR.implementation_library original,obj [
    "schema_version",str "biocompiler.policy_component_material_candidate.v0.1";
    "behavior",behavior;"implementation",get "implementation" parts;
    "binding",get "binding" parts;"assembly_proposal",assembly;"construction",get "construction" parts]
let omit key raw = obj (List.filter (fun (name,_) -> name<>key) (Json.object_fields raw))
let rejected_at code expected_path label run =
  incr checks;
  match run () with
  | _ -> failwith ("Mutation accepted: "^label)
  | exception Diagnostic.Error value ->
      if value.code<>code || value.path<>Some expected_path then
        failwith ("Wrong candidate diagnostic: "^label^": "^value.code)
let positive library raw =
  let charged=ref 0 in
  let decoded=Candidate.of_json ~charge:(fun amount -> charged := !charged+amount) ~library raw in
  require (Candidate.to_json decoded=raw) "Neutral candidate codec replaced the complete original raw value";
  require (!charged>0 && !charged=Candidate.decoding_work decoded) "Candidate child decoding bypassed outer charge owner";
  List.iter (fun (key,value) -> require (Json.equal value (get key raw)) ("Typed candidate field changed: "^key))
    ["behavior",O.behavior_to_json (Candidate.behavior decoded);
     "implementation",I.to_json (Candidate.implementation decoded);
     "binding",U.to_json (Candidate.binding decoded);
     "assembly_proposal",Q.to_json (Candidate.assembly_proposal decoded);
     "construction",K.to_json (Candidate.construction decoded)];
  require ((Candidate.behavior decoded).nodes=[] &&
    (Candidate.behavior decoded).unresolved_obligations=["literal_codec_requires_fresh_check"])
    "Domain codec supplied missing semantic authority or removed an unresolved obligation";
  let reversed=obj (List.rev (Json.object_fields raw)) in
  let roundtrip=Candidate.of_json ~library reversed in
  require (Candidate.to_json roundtrip=reversed && Json.equal (Candidate.to_json roundtrip) raw)
    "Object field ordering lost retained raw input or changed canonical JSON meaning";
  let unordered=put ["construction";"diagnostics"] (arr [str "z.unresolved";str "a.unresolved"]) raw in
  let retained=Candidate.of_json ~library unordered in
  require (Candidate.to_json retained=unordered &&
    get "diagnostics" (K.to_json (Candidate.construction retained))=arr [str "a.unresolved";str "z.unresolved"])
    "Typed child normalization must not replace the original candidate envelope"
let controls fixture library raw =
  let decode=Candidate.of_json ~library in
  List.iter (fun field -> rejected_at "missing_field" "/payload/candidate" ("Missing candidate "^field)
    (fun () -> decode (omit field raw)))
    ["schema_version";"behavior";"implementation";"binding";"assembly_proposal";"construction"];
  List.iter (fun field -> rejected_at "unknown_field" "/payload/candidate" ("Candidate cannot embed "^field)
    (fun () -> decode (add field (Json.Bool true) raw))) ["accepted";"report";"request";"winner"];
  rejected_at "duplicate_key" "/payload/candidate" "Repeated candidate schema"
    (fun () -> decode (add "schema_version" (get "schema_version" raw) raw));
  rejected "policy_component_material_candidate" "Whole-graph candidate schema cannot coerce component data"
    (fun () -> decode (replace "schema_version" (str "biocompiler.policy_material_candidate.v0.1") raw));
  rejected "policy_operational_representation" "Stale behavior source pin remains rejected"
    (fun () -> decode (put ["behavior";"source_artifact_digest"] (str (String.make 64 '0')) raw));
  rejected "policy_implementation_contract" "Candidate cannot replace the independently supplied library"
    (fun () -> decode (put ["implementation";"authority";"library_digest"] (str (String.make 64 '0')) raw));
  let different_library=original_library fixture |> replace "version" (str "2") |> I.library_of_json in
  rejected "policy_implementation_contract" "Actual supplied child library is mandatory"
    (fun () -> Candidate.of_json ~library:different_library raw);
  rejected "policy_component_assembly_proposal" "Invalid assembly slot is not opaque transport"
    (fun () -> decode (put ["assembly_proposal";"nodes";"0";"slot"] (str "helper") raw));
  rejected "missing_field" "Opaque construction fingerprint cannot replace complete material"
    (fun () -> decode (replace "construction" (obj ["fingerprint",str (Canonical.fingerprint (get "construction" raw))]) raw));
  rejected "literal_charge_denied" "Enclosing checker may deny tiny candidate decoding budget" (fun () ->
    let remaining=ref 1 in Candidate.of_json ~library ~charge:(fun amount ->
      if amount> !remaining then Diagnostic.fail "literal_charge_denied" "One unit is insufficient.";
      remaining := !remaining-amount) raw);
  let rec cyclic=Json.Array [cyclic] in
  rejected "policy_material_input_limit" "Cyclic candidate is bounded before typed decoding" (fun () -> decode cyclic)
let () =
  try
    require (Array.length Sys.argv=2) "Supply the independent A original fixture with literal candidate parts";
    let fixture=read Sys.argv.(1) in
    let library,raw=literal fixture in positive library raw;controls fixture library raw;
    Printf.printf "component material candidate: %d independent codec controls passed\n" !checks
  with Diagnostic.Error value ->
    Printf.eprintf "Diagnostic.Error(code=%s,path=%s,message=%s)\n" value.code
      (Option.value ~default:"<none>" value.path) value.message; exit 1

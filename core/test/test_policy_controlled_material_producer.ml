(* Exact proposal comparisons use independent retained literals, never an
   expected value obtained from the producer or private checker reconstruction. *)
open Bioc_wire
module R = Bioc_domain.Policy_controlled_composition_request
module C = Bioc_domain.Policy_controlled_material_candidate
module K = Bioc_domain.Construction_content
module N = Bioc_domain.Molecule
module P = Bioc_compiler.Policy_controlled_material_producer
module Limits = Bioc_compiler.Construction_producer.Limits
module W = Bioc_checker.Work_budget
let checks = ref 0
let require condition message = incr checks; if not condition then failwith message
let str value = Json.String value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let set key value raw = Json.Object ((key,value)::List.remove_assoc key (Json.object_fields raw))
let rec edit path change raw = match path with [] -> change raw | key::rest ->
  match raw with
  | Json.Array values -> arr (List.mapi (fun index value -> if index = int_of_string key then edit rest change value else value) values)
  | _ -> set key (edit rest change (get key raw)) raw
let put path value = edit path (fun _ -> value)
let reject code action = incr checks; match action () with
  | _ -> failwith ("Expected resource failure: " ^ code)
  | exception Diagnostic.Error diagnostic ->
      if diagnostic.code <> code then failwith ("Expected " ^ code ^ "; got " ^ diagnostic.code)
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size = in_channel_length channel in require (size > 0 && size < 1000000) "Fixture read bound";
    Json.parse (really_input_string channel size))
let contents (value:C.t) = C.construction value
let molecules (value:C.t) = K.Inventory.molecules (Option.get (K.inventory (contents value)))
let run request_path fixture_path =
  let raw = read request_path and fixture = read fixture_path in
  let request = R.of_json raw in
  require (str (R.fingerprint request) = get "request_sha256" fixture) "Independent complete request changed";
  let generated = P.construct_candidate request in
  require (Canonical.encode (C.to_json generated) = Canonical.encode (get "literal_candidate" fixture))
    "Producer differs from the independently declared complete two-member candidate";
  require (str (C.fingerprint generated) = get "candidate_sha256" fixture) "Exact material candidate digest differs";
  require (List.map N.id (molecules generated) = ["rna-a";"rna-b"] &&
      List.map N.sequence (molecules generated) = ["CCAUGGCUUAAGGAAAA";"CCAUGGGUUAAGGAAAA"])
    "Complete literal RNA members or order differ";
  require (List.fold_left (fun total molecule -> total + String.length (N.sequence molecule)) 0 (molecules generated) = 34)
    "Literal aggregate RNA length differs";
  require (K.values (contents generated) = [] && K.missing_members (contents generated) = [] &&
      K.diagnostics (contents generated) = [] && K.experimental_amounts (contents generated) = [])
    "Direct roots invented transforms, amounts or missing material";
  require (C.fingerprint (P.construct_candidate request) = C.fingerprint generated) "Deterministic proposal changed";
  require (Json.equal raw (R.to_json request)) "Producer changed caller authority";
  List.iter (fun (label,changed) ->
    let next_request = R.of_json changed in
    let next = P.construct_candidate next_request in
    require (C.request_fingerprint next = R.fingerprint next_request && C.fingerprint next <> C.fingerprint generated)
      (label ^ " failed to bind complete independent request identity");
    require (K.fingerprint (contents next) = K.fingerprint (contents generated))
      (label ^ " needlessly changed unchanged material")) [
    "project title",put ["source_authority";"project_context";"title"] (str "Distinct original project") raw;
    "publication bound",put ["budgets";"max_report_bytes"] (Json.int 999999) raw;
    "domain work bound",put ["operating_domain";"limits";"max_work"] (Json.int 999999) raw
  ];
  let reversed = raw |> put ["material_authority";"member_order"] (arr [str "rna-b";str "rna-a"])
      |> edit ["material_authority";"members"] (fun value -> arr (List.rev (Json.array value)))
      |> put ["assembly";"member_order"] (arr [str "rna-b";str "rna-a"]) in
  let reverse = P.construct_candidate (R.of_json reversed) in
  require (List.map N.id (molecules reverse) = ["rna-b";"rna-a"] && K.member_order (contents reverse) = ["rna-b";"rna-a"])
    "Explicit original order was normalized to template IDs";
  require (K.authority (contents reverse) <> K.authority (contents generated)) "Member order omitted from construction authority";
  let baseline_by_id = List.map (fun molecule -> N.id molecule,N.fingerprint molecule) (molecules generated) in
  require (List.for_all (fun molecule -> List.assoc (N.id molecule) baseline_by_id = N.fingerprint molecule) (molecules reverse))
    "Reordering altered complete molecular identity";
  let charged = ref 0 in
  let metered = P.construct_candidate ~charge:(fun amount -> charged := !charged + amount) request in
  require (C.fingerprint metered = C.fingerprint generated && !charged > C.decoding_work metered)
    "Construction work was omitted or changed exact bytes";
  let cancelled = try ignore (P.construct_candidate ~charge:(fun _ -> raise Exit) request); false with Exit -> true in
  require cancelled "Enclosing cancellation was swallowed";
  let parent = W.create ~profile:"controlled-test-parent" ~error_code:"outer_work" ~maximum:1 () in
  reject "outer_work" (fun () -> P.construct_candidate ~charge:(W.charge parent) request);
  require (W.exhausted parent) "Enclosing work owner did not retain exhaustion";
  reject "construction_producer_limit" (fun () -> P.construct_candidate ~limits:(Limits.make ~work:0 ()) request);
  let exact = P.construct_candidate ~limits:(Limits.make ~final_residues:34 ()) request in
  require (C.fingerprint exact = C.fingerprint generated) "Exact total residue bound rejected the complete pair";
  let short = P.construct_candidate ~limits:(Limits.make ~final_residues:33 ()) request in
  require (K.inventory (contents short) = None && K.missing_members (contents short) = ["rna-a";"rna-b"] &&
      K.diagnostics (contents short) = ["bundle:residue_budget"])
    "Aggregate residue limit fabricated a partial published pair";
  Printf.printf "controlled material producer: %d checks\n" !checks
let () =
  if Array.length Sys.argv <> 3 then failwith "Expected independent request and material literal fixtures";
  run Sys.argv.(1) Sys.argv.(2)

(* Independent literal codec tests. No producer or acceptance checker dependency. *)
open Bioc_wire
module C = Bioc_domain.Policy_controlled_material_candidate
module K = Bioc_domain.Construction_content
module N = Bioc_domain.Molecule
let checks = ref 0
let require condition message = incr checks; if not condition then failwith message
let str value = Json.String value
let get key value = Json.field key (Json.object_fields value)
let set key value raw = Json.Object ((key,value)::List.remove_assoc key (Json.object_fields raw))
let reject label action = incr checks; match action () with
  | _ -> failwith ("Unexpected candidate decode: " ^ label)
  | exception Diagnostic.Error _ -> ()
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size = in_channel_length channel in
    require (size > 0 && size < 200000) "Independent fixture exceeds read bound";
    Json.parse (really_input_string channel size))
let run path =
  let fixture = read path in
  let raw = get "literal_candidate" fixture in
  let value = C.of_json raw in
  require (Json.equal raw (C.to_json value)) "Neutral codec changed original candidate fields";
  require (str (C.fingerprint value) = get "candidate_sha256" fixture) "Independent candidate digest changed";
  require (str (C.request_fingerprint value) = get "request_sha256" fixture) "Complete request identity changed";
  let content = C.construction value in
  require (str (K.authority content) = get "construction_authority_sha256" fixture) "Independent template/order identity changed";
  require (K.member_order content = ["rna-a";"rna-b"]) "Original member order changed";
  let molecules = K.Inventory.molecules (Option.get (K.inventory content)) in
  require (List.map N.sequence molecules = ["CCAUGGCUUAAGGAAAA";"CCAUGGGUUAAGGAAAA"])
    "Independent whole RNA spellings changed";
  require (C.fingerprint (C.of_json (C.to_json value)) = C.fingerprint value) "Candidate round-trip changed identity";
  List.iter (fun (label,changed) -> reject label (fun () -> C.of_json changed)) [
    "wrong profile",set "schema_version" (str "biocompiler.policy_controlled_composition_candidate.v0.1") raw;
    "extra behavioral claim",set "behavior_status" (str "pass") raw;
    "extra checked token",set "checked_structure" (Json.Object []) raw;
    "nonstring request digest",set "request_fingerprint" (Json.int 1) raw;
    "short request digest",set "request_fingerprint" (str (String.make 63 'a')) raw;
    "uppercase request digest",set "request_fingerprint" (str (String.make 64 'A')) raw;
    "nonhex request digest",set "request_fingerprint" (str (String.make 64 'g')) raw;
    "absent construction",set "construction" Json.Null raw;
    "missing field",Json.Object (List.remove_assoc "request_fingerprint" (Json.object_fields raw));
    "duplicate field",Json.Object (("request_fingerprint",get "request_fingerprint" raw)::Json.object_fields raw)
  ];
  (* Syntax decoding cannot establish the independent request identity. A
     well-shaped foreign pin is retained for the fresh checker to reject. *)
  let foreign = C.of_json (set "request_fingerprint" (str (String.make 64 '0')) raw) in
  require (C.request_fingerprint foreign = String.make 64 '0' && C.fingerprint foreign <> C.fingerprint value)
    "Neutral codec fabricated independent request correspondence";
  let incomplete = C.of_json (set "construction" (set "inventory" Json.Null (get "construction" raw)) raw) in
  require (K.inventory (C.construction incomplete) = None) "Neutral codec promoted or repaired absent material";
  let charged = ref 0 in
  let metered = C.of_json ~charge:(fun amount -> charged := !charged + amount) raw in
  require (!charged = C.decoding_work metered && !charged > String.length (Canonical.encode raw))
    "Candidate decode/serialization/hash work was omitted";
  let cancelled = try ignore (C.of_json ~charge:(fun _ -> raise Exit) raw); false with Exit -> true in
  require cancelled "Caller cancellation was swallowed";
  let calls = ref 0 in
  let stopped = try
      ignore (C.of_json ~charge:(fun _ -> incr calls; if !calls = 10 then Diagnostic.fail "outer_work" "Stopped") raw);
      false
    with Diagnostic.Error diagnostic -> diagnostic.code = "outer_work" in
  require (stopped && !calls = 10) "Caller resource failure did not propagate at its exact charge";
  let rec cyclic = Json.Array [cyclic] in
  reject "cyclic native JSON" (fun () -> C.of_json cyclic);
  let rec nested count item = if count = 0 then item else nested (count - 1) (Json.Array [item]) in
  reject "excessive depth" (fun () -> C.of_json (nested 100 Json.Null));
  Printf.printf "controlled material candidate: %d checks\n" !checks
let () =
  if Array.length Sys.argv <> 2 then failwith "Expected independent controlled material literal fixture";
  run Sys.argv.(1)

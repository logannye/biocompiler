(* Complete independent literal; no compiler, checker or evaluator dependency. *)
open Bioc_wire
module C = Bioc_domain.Policy_controlled_behavior_candidate
module I = Bioc_domain.Policy_controlled_activity_implementation
let checks = ref 0
let require value message = incr checks; if not value then failwith message
let str value = Json.String value
let get key raw = Json.field key (Json.object_fields raw)
let set key value raw = Json.Object ((key,value)::List.remove_assoc key (Json.object_fields raw))
let rec edit path change raw = match path with [] -> change raw | key::rest ->
  match raw with
  | Json.Array rows -> Json.Array (List.mapi (fun i row -> if i = int_of_string key then edit rest change row else row) rows)
  | _ -> set key (edit rest change (get key raw)) raw
let put path value = edit path (fun _ -> value)
let reject label action = incr checks; match action () with
  | _ -> failwith ("Unexpected decode: " ^ label)
  | exception Diagnostic.Error _ -> ()
let read path = let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    Json.parse_bounded ~max_bytes:200000 ~max_nodes:100000
      (really_input_string channel (in_channel_length channel)))
let run path =
  let fixture = read path in
  let raw = get "literal_candidate" fixture in
  let candidate = C.of_json raw in
  require (Json.equal (C.to_json candidate) raw) "Candidate codec changed a complete original field";
  require (str (C.fingerprint candidate) = get "candidate_sha256" fixture) "Independent candidate identity changed";
  require (str (C.request_fingerprint candidate) = get "request_sha256" fixture) "Original wrapper identity changed";
  let implementation = C.implementation candidate in
  require (str (I.fingerprint implementation) = get "implementation_sha256" fixture) "Complete implementation identity changed";
  let delays = I.delays implementation in
  require (delays.onset_ticks = 1 && delays.cessation_ticks = 1 && delays.reactivation_ticks = 1)
    "Primitive parameters were replaced by source deadlines";
  require (C.fingerprint (C.of_json (C.to_json candidate)) = C.fingerprint candidate) "Roundtrip lost candidate identity";
  let changed path value = put ("implementation"::path) value raw in
  List.iter (fun (label,body) -> reject label (fun () -> C.of_json body)) [
    "legacy/full schema",set "schema_version" (str "biocompiler.policy_candidate.v0.1") raw;
    "material wrapper",set "construction" (Json.Object []) raw;
    "candidate verdict",set "status" (str "pass") raw;
    "missing request",Json.Object (List.remove_assoc "request_fingerprint" (Json.object_fields raw));
    "duplicate request",Json.Object (("request_fingerprint",get "request_fingerprint" raw)::Json.object_fields raw);
    "uppercase digest",set "request_fingerprint" (str (String.make 64 'A')) raw;
    "short digest",set "request_fingerprint" (str (String.make 63 '0')) raw;
    "wrong graph schema",changed ["schema_version"] (str "unknown");
    "incomplete copied model",changed ["mechanism_model"] Json.Null;
    "extra graph claim",edit ["implementation"] (set "accepted" (Json.Bool true)) raw;
    "missing node",changed ["primitives"] (Json.Array (List.tl (Json.array (get "primitives" (I.to_json implementation)))));
    "RNA gate substitution",changed ["primitives";"3";"key"] (str "rna_a");
    "evidence as physical",changed ["primitives";"1";"key"] (str "antigen_evidence");
    "unknown physical band",changed ["primitives";"6";"initial_band"] (str "unknown");
    "initial active",changed ["primitives";"6";"initial_band"] (str "active");
    "encounter-owned timer",changed ["primitives";"6";"timer_scope"] (str "encounter_generation");
    "unowned activation",changed ["primitives";"6";"activation_scope"] (str "executor");
    "zero onset",changed ["primitives";"6";"onset_ticks"] (Json.int 0);
    "negative off",changed ["primitives";"6";"cessation_ticks"] (Json.int (-1));
    "unbounded restart",changed ["primitives";"6";"reactivation_ticks"] (Json.int 10001);
    "floating delay",changed ["primitives";"6";"onset_ticks"] (Json.Float 1.);
    "gate disconnect",changed ["wires";"2";"from"] (str "antigen");
    "duplicate wire",changed ["wires"] (Json.Array (List.init 7 (fun _ -> List.hd (Json.array (get "wires" (I.to_json implementation))))));
    "extra wire field",edit ["implementation";"wires";"0"] (set "trusted" (Json.Bool true)) raw
  ];
  (* Syntactically valid foreign authority and delay changes remain untrusted.
     The neutral codec must neither repair them nor manufacture correspondence. *)
  let foreign = C.of_json (set "request_fingerprint" (str (String.make 64 '0')) raw) in
  require (C.request_fingerprint foreign = String.make 64 '0') "Codec invented original identity";
  let changed_delay = C.of_json (changed ["primitives";"6";"onset_ticks"] (Json.int 2)) in
  require ((I.delays (C.implementation changed_delay)).onset_ticks = 2 &&
    C.fingerprint changed_delay <> C.fingerprint candidate) "Candidate delay change was normalized away";
  (* Actual supplied mechanism delays have their own 10000-tick ceiling;
     the finite observation horizon and requested source bounds stay separate. *)
  List.iter (fun key -> List.iter (fun ticks ->
    let body = changed ["primitives";"6";key] (Json.int ticks) in
    let decoded = C.of_json body in
    require (Json.equal (C.to_json decoded) body &&
      C.fingerprint decoded <> C.fingerprint candidate)
      "Valid actual mechanism delay was limited by the observation horizon")
    [65;10000]) ["onset_ticks";"cessation_ticks";"reactivation_ticks"];
  let changed_body = C.of_json (changed ["semantics";"definitions";"17";"meaning"] (str "Foreign complete declared dependency")) in
  require (C.fingerprint changed_body <> C.fingerprint candidate) "Complete semantic bodies were omitted from identity";
  let charged = ref 0 in
  let metered = C.of_json ~charge:(fun n -> charged := !charged + n) raw in
  require (!charged = C.decoding_work metered && !charged > I.decoding_work implementation)
    "Nested graph decode/hash work escaped the caller";
  let cancelled = try ignore (C.of_json ~charge:(fun _ -> raise Exit) raw); false with Exit -> true in
  require cancelled "Caller cancellation was swallowed";
  let rec cyclic = Json.Array [cyclic] in
  reject "cyclic native JSON" (fun () -> C.of_json cyclic);
  Printf.printf "controlled behavior candidate: %d checks\n" !checks
let () =
  if Array.length Sys.argv <> 2 then failwith "Expected independent behavior candidate literal fixture";
  run Sys.argv.(1)

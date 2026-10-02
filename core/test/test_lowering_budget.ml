open Bioc_wire
module D = Bioc_domain
module L = Bioc_compiler.Lowering
module W = Bioc_checker.Work_budget
let require condition message = if not condition then failwith message
let get key raw = Json.field key (Json.object_fields raw)
let budget maximum = W.create ~profile:"lowering-parent-test"
    ~error_code:"caller_lowering_exhausted" ~maximum ()
(* Measurement allowance, not a production default. Every subsequent run uses
   the exact measured total or the adjacent failing boundary. *)
let measurement_allowance = 1_000_000_000_000
let exhausted parent action =
  match action () with
  | _ -> failwith "Exhausted caller admitted lowering"
  | exception Diagnostic.Error value ->
      require (value.code = "caller_lowering_exhausted" && W.is_exhaustion parent value)
        ("Wrong caller exhaustion identity: " ^ value.code)
let read path =
  let channel = open_in_bin path in
  let bytes = Fun.protect ~finally:(fun () -> close_in channel)
      (fun () -> really_input_string channel (in_channel_length channel)) in
  Json.parse bytes
let () =
  require (Array.length Sys.argv = 2) "Expected original lowering corpus path";
  let cases = Json.array (get "cases" (read Sys.argv.(1))) in
  require (List.length cases >= 31) "Incomplete original lowering cases";
  let checked = ref 0 in
  List.iter (fun case ->
    let request = D.Build_request.of_json (get "request" case) in
    let parent = budget measurement_allowance in
    let actual = L.lower_with_budget ~parent request in
    require (Json.equal (D.Behavior.to_json actual) (get "expected_behavior" case))
      (Json.string (get "id" case) ^ ": shared-budget lowering changed complete output");
    let used = measurement_allowance - W.remaining parent in
    require (used > 0) "Producer did not charge caller";
    let checker = budget measurement_allowance in
    ignore (Bioc_checker.Lowering_check.check_with_budget ~parent:checker
        ~expected_request:request ~behavior:actual ());
    require (used > measurement_allowance - W.remaining checker)
      "Producer materialization and transformations were not charged beyond checking";
    let exact = budget used in
    require (Json.equal (D.Behavior.to_json (L.lower_with_budget ~parent:exact request))
        (D.Behavior.to_json actual) && W.remaining exact = 0)
      "Exact caller work boundary changed";
    let short = budget (used - 1) in
    exhausted short (fun () -> L.lower_with_budget ~parent:short request);
    let repeated = budget (2 * used - 1) in
    ignore (L.lower_with_budget ~parent:repeated request);
    exhausted repeated (fun () -> L.lower_with_budget ~parent:repeated request);
    let empty = budget 0 in
    exhausted empty (fun () -> L.lower_with_budget ~parent:empty request);
    incr checked) cases;
  Printf.printf "Shared lowering budget: %d original complete outputs, exact/short/repeated ancestor boundaries passed\n" !checked

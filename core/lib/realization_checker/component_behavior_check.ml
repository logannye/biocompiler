open Bioc_wire
open Bioc_domain
module B = Realization_budget
module W = Bioc_checker.Work_budget
module Q = Checked_request
module A = Component_assembly
module E = Realization_evidence
module L = Composition_evidence
module C = Bioc_candidate_runtime.Components
let implementation_version = "biocompiler.ocaml.component_behavior_checker.v0.1"
type limits = { common : B.limits; realization : Realization_check.limits;
  composition : Bioc_checker.Composition_check.limits }
let make_limits ?max_work ?max_monitor_items ?max_request_bytes ?max_report_bytes ?max_report_nodes () =
  {common=B.make_limits ?max_work ?max_monitor_items ?max_request_bytes ?max_report_bytes ?max_report_nodes ();
   realization=Realization_check.make_limits ?max_work ?max_monitor_items ?max_request_bytes ?max_report_bytes ?max_report_nodes ();
   composition=Bioc_checker.Composition_check.make_limits ?max_work ?max_items:max_monitor_items
     ?max_input_bytes:max_request_bytes ?max_report_bytes ?max_report_nodes ()}
let default_limits = make_limits ()
let limits_json limits = Json.Object ["profile", Json.String "biocompiler.component_behavior_checker.resources.v1";
  "shared", B.limits_json limits.common; "realization", Realization_check.limits_json limits.realization;
  "composition", Bioc_checker.Composition_check.limits_json limits.composition]
type usage = { work_charged : int; reconstruction_work : int }
let field key value = Json.field key (Json.object_fields value)
let replace key value raw = Json.Object ((key, value) :: List.remove_assoc key (Json.object_fields raw))
(* This one historical authority relation is Python dataclass equality. Its
   numeric equality does not replace either target's exact artifact identity. *)
let target_equal budget left right =
  let pending = ref [left, right] and same = ref true in
  let rec levels n = if n <= 1 then 1 else 1 + levels (n / 2) in
  let numeric = function Json.Bool value -> Some (Json.int (if value then 1 else 0))
    | (Json.Int _ | Json.Float _) as value -> Some value | _ -> None in
  let ordered values =
    let size = List.fold_left (fun total (key, _) -> total + String.length key + 1) 0 values in
    B.charge budget (size * (1 + levels (List.length values)));
    List.sort (fun (a, _) (b, _) -> String.compare a b) values in
  while !same && !pending <> [] do
    B.charge budget 1;
    let a, b = List.hd !pending in pending := List.tl !pending;
    match numeric a, numeric b, a, b with
    | Some a, Some b, _, _ ->
        B.charge budget (String.length (Canonical.encode a) + String.length (Canonical.encode b) + 1);
        same := Json.number_compare a b = 0
    | _, _, Json.Array a, Json.Array b ->
        B.charge budget (List.length a + List.length b);
        if List.length a <> List.length b then same := false
        else List.iter2 (fun a b -> pending := (a, b) :: !pending) a b
    | _, _, Json.Object a, Json.Object b ->
        let a = ordered a and b = ordered b in
        if List.length a <> List.length b then same := false
        else List.iter2 (fun (key_a, a) (key_b, b) ->
          if key_a <> key_b then same := false else pending := (a, b) :: !pending) a b
    | _, _, Json.Null, Json.Null -> ()
    | _, _, Json.String a, Json.String b -> B.charge budget (String.length a + String.length b); same := a = b
    | _ -> same := false
  done;
  !same
let check_with_usage ?until ?(limits=default_limits) ?parent request assembly history =
  let budget = B.create ?parent ~limits:limits.common () in
  let work = B.work budget in
  let initial = W.remaining work in
  B.reserve_request budget (Json.Object ["request", Json.Null; "assembly", Json.Null;
      "history", Json.Array []; "until", (match until with None -> Json.Null | Some value -> Runtime_number.to_json value)]);
  B.reserve_request budget (Realization_request.to_json request);
  B.reserve_request budget (A.to_json assembly);
  let history = B.bounded_list budget history in
  List.iter (fun frame -> B.reserve_request budget (Execution_data.Input_frame.to_json frame)) history;
  let request = Q.check ~parent:work request in
  let target = Q.target request in
  Diagnostic.require (A.request_fingerprint assembly = Q.fingerprint request &&
      target_equal budget (Build_request.Target.to_json (Composition.target (A.composition assembly)))
        (Build_request.Target.to_json target)) "component_behavior"
    "Component behavior authority or target differs from the assembly.";
  (* The candidate reconstruction library deliberately has no checker edge.
     Constrain its private allowance to the same remaining parent capacity and
     charge actual successful work, or burn the allocated capacity on failure.
     A failed reconstruction never returns a partial mechanism or receipt. *)
  let allowance = min 50_000_000 (B.remaining budget) in
  (* Report exhaustion through the participating parent before entering the
     runtime's independent allowance, which has its own diagnostic identity. *)
  if allowance = 0 then B.charge budget 1;
  let mechanism, reconstruction_work =
    match C.reconstruct_with_usage ~limits:(C.make_limits ~max_preparation_work:allowance ()) assembly with
    | result -> result
    | exception error -> B.burn_failure budget allowance; raise error in
  B.charge budget reconstruction_work;
  let raw_request = Q.request request in
  let checked = Realization_check.check ?until ~limits:limits.realization ~parent:work
      (Realization_request.behavior raw_request) (Realization_request.contract raw_request)
      (Realization_request.domain raw_request) target mechanism (A.observation_map assembly) history in
  let linked = Bioc_checker.Composition_check.check ~parent:work ~limits:limits.composition
      ~request:(A.composition assembly) ~registry:(A.registry assembly) () in
  let raw = E.Check_result.to_json checked in
  let raw = if L.Result.passed linked then raw else (
    let outcomes = [E.Check_result.outcome checked; L.Result.outcome linked] in
    let outcome = List.find (fun value -> List.mem value outcomes) [E.Fail; E.Unsupported; E.Unknown] in
    let diagnostics = List.map (fun diagnostic ->
        let raw = Json.Object ["code", Json.String ("component_" ^ L.Link_diagnostic.code diagnostic);
          "message", Json.String (L.Link_diagnostic.message diagnostic);
          "node_id", (match L.Link_diagnostic.instance_id diagnostic with None -> Json.Null | Some id -> Json.String id);
          "requirement_id", Json.Null; "source", Json.Null] in
        B.reserve_report budget raw;
        E.Check_diagnostic.of_json raw |> E.Check_diagnostic.to_json) (L.Result.diagnostics linked) in
    let name = match outcome with E.Fail -> "fail" | E.Unsupported -> "unsupported"
      | E.Unknown -> "unknown" | E.Pass -> assert false in
    raw |> replace "outcome" (Json.String name)
      |> replace "diagnostics" (Json.Array (Json.array (field "diagnostics" raw) @ diagnostics))) in
  let dependencies = field "dependencies" raw in
  let settings = field "settings" dependencies in
  let settings = List.fold_left (fun result (key, value) -> replace key (Json.String value) result) settings
      ["component_reconstruction", C.reconstruction_version;
       "component_assembly", A.fingerprint assembly;
       "component_registry", Component_registry.fingerprint (A.registry assembly);
       "component_composition", Composition.fingerprint (A.composition assembly)] in
  let raw = replace "dependencies" (replace "settings" settings dependencies) raw in
  B.reserve_report budget raw;
  let result = E.Check_result.of_json raw in
  result, {work_charged=initial - W.remaining work; reconstruction_work}
let check ?until ?limits ?parent request assembly history =
  fst (check_with_usage ?until ?limits ?parent request assembly history)

open Bioc_wire
open Bioc_domain
module B = Realization_budget
module W = Bioc_checker.Work_budget
module S = Synthetic_authority.Candidate
module A = Component_assembly
module E = Realization_evidence
module L = Composition_evidence
module M = Mechanism
module C = Bioc_candidate_runtime.Components
module Authority = Synthetic_component_authority
let implementation_version = "biocompiler.ocaml.component_assembly_checker.v0.1"
type limits = { common : B.limits; synthetic : Synthetic_candidate_check.limits;
  behavior : Component_behavior_check.limits; composition : Bioc_checker.Composition_check.limits }
let make_limits ?max_work ?max_monitor_items ?max_request_bytes ?max_report_bytes ?max_report_nodes () =
  {common=B.make_limits ?max_work ?max_monitor_items ?max_request_bytes ?max_report_bytes ?max_report_nodes ();
   synthetic=Synthetic_candidate_check.make_limits ?max_work ?max_monitor_items ?max_request_bytes ?max_report_bytes ?max_report_nodes ();
   behavior=Component_behavior_check.make_limits ?max_work ?max_monitor_items ?max_request_bytes ?max_report_bytes ?max_report_nodes ();
   composition=Bioc_checker.Composition_check.make_limits ?max_work ?max_items:max_monitor_items
     ?max_input_bytes:max_request_bytes ?max_report_bytes ?max_report_nodes ()}
let default_limits = make_limits ()
let limits_json limits = Json.Object ["profile",Json.String "biocompiler.component_assembly_checker.resources.v1";
  "shared",B.limits_json limits.common;"synthetic",Synthetic_candidate_check.limits_json limits.synthetic;
  "behavior",Component_behavior_check.limits_json limits.behavior;
  "composition",Bioc_checker.Composition_check.limits_json limits.composition;
  "private_authority",Json.String "cumulative_derived_fragments_share_report_bytes_nodes_and_work"]
type usage = { work_charged : int; reconstruction_work : int; authority_work : int;
  request_bytes : int; report_bytes : int; retained_peak : int }
let field key raw = Json.field key (Json.object_fields raw)
let require condition message = Diagnostic.require condition "component_assembly" message
let source_json values = Json.Object (List.map (fun (key,values) -> key,Json.Array (List.map (fun value -> Json.String value) values)) values)
let rec levels n = if n <= 1 then 1 else 1 + levels (n / 2)
let reserve_items budget values =
  let values = B.bounded_list budget values in
  let count = List.length values in
  B.charge budget count;
  B.retain_monitor budget count
let mapped budget encode values =
  reserve_items budget values;
  List.map encode values
let sorted budget values =
  (* Callers reserve each transformed item before allocation. Sorting transfers
     that reservation to the ordered inventory rather than charging it twice. *)
  let bytes = List.fold_left (fun total value -> total + String.length value + 1) 0 values in
  let factor = 1 + levels (List.length values) in
  if bytes > B.remaining budget / factor then B.charge budget (B.remaining budget + 1);
  B.charge budget (bytes * factor);
  List.sort_uniq String.compare values
let edge_key budget a b c d =
  B.charge budget (6 * (String.length a + String.length b + String.length c + String.length d) + 16);
  Canonical.encode (Json.Array (List.map (fun value -> Json.String value) [a;b;c;d]))
let check_with_usage ?until ?(limits=default_limits) ?parent request candidate assembly history =
  let budget = B.create ?parent ~limits:limits.common () in
  let work = B.work budget in
  let initial_work = W.remaining work in
  B.reserve_request budget (Json.Object ["request",Json.Null;"candidate",Json.Null;"assembly",Json.Null;
      "history",Json.Array [];"until",(match until with None -> Json.Null | Some value -> Runtime_number.to_json value)]);
  B.reserve_request budget (Realization_request.to_json request);
  B.reserve_request budget (S.to_json candidate);
  B.reserve_request budget (A.to_json assembly);
  let history = B.bounded_list budget history in
  List.iter (fun frame -> B.reserve_request budget (Execution_data.Input_frame.to_json frame)) history;
  (* The original adapter first required fresh current synthetic PASS. Preserve
     this precedence even when the supplied assembly is obviously different. *)
  let accepted = Synthetic_candidate_check.check ?until ~limits:limits.synthetic ~parent:work request candidate history in
  Diagnostic.require (E.Check_result.outcome accepted = E.Pass) "synthetic_component_acceptance"
    "Component adaptation requires passing synthetic acceptance for the current request, candidate and history.";
  let checked_request = Checked_request.check ~parent:work request in
  let before_authority = W.remaining work in
  let authority = Authority.derive ~budget checked_request candidate in
  let authority_work = before_authority - W.remaining work in
  (* Exact imported pins are compared to independently reconstructed content.
     Canonical correspondence comparison preserves ordered lineage values. *)
  B.charge budget (A.canonical_size assembly + S.canonical_size candidate);
  require (A.request_fingerprint assembly = Checked_request.fingerprint checked_request &&
    A.candidate_fingerprint assembly = S.fingerprint candidate &&
    Component_registry.fingerprint (A.registry assembly) = Component_registry.fingerprint (Authority.registry authority) &&
    Composition.fingerprint (A.composition assembly) = Composition.fingerprint (Authority.composition authority) &&
    Canonical.fingerprint (source_json (A.behavior_sources assembly)) = Canonical.fingerprint (source_json (S.source_map candidate)) &&
    Observation_map.fingerprint (A.observation_map assembly) = Observation_map.fingerprint (S.observation_map candidate))
    "Component assembly changed its authoritative source correspondence.";
  let actual_edges = Composition.connections (A.composition assembly) |> mapped budget (fun edge ->
      edge_key budget (Composition.Connection.producer_instance edge) (Composition.Connection.producer_port edge)
        (Composition.Connection.consumer_instance edge) (Composition.Connection.consumer_port edge)) |> sorted budget in
  let mechanism = S.mechanism candidate in
  let nodes = B.bounded_list budget (M.nodes mechanism) in
  (* Reserve the complete flattened inventory before constructing any edge.
     Folding directly into one reverse list avoids temporary mapped edge lists;
     the subsequent set ordering does not depend on this construction order. *)
  List.iter (fun node -> reserve_items budget (M.Node.inputs node)) nodes;
  let expected_edges = List.fold_left (fun edges node ->
      snd (List.fold_left (fun (index,edges) input ->
          index + 1,edge_key budget input "out" (M.Node.id node) ("in:" ^ string_of_int index) :: edges)
        (0,edges) (M.Node.inputs node))) [] nodes |> sorted budget in
  let actual_ids = Composition.instances (A.composition assembly) |> mapped budget Composition.Instance.id |> sorted budget in
  let expected_ids = nodes |> mapped budget M.Node.id |> sorted budget in
  require (actual_edges = expected_edges && actual_ids = expected_ids) "Component assembly changed the mechanism graph.";
  let allowance = min 50_000_000 (B.remaining budget) in
  if allowance = 0 then B.charge budget 1;
  let reconstructed,reconstruction_work =
    match C.reconstruct_with_usage ~limits:(C.make_limits ~max_preparation_work:allowance ()) assembly with
    | value -> value
    | exception error -> B.burn_failure budget allowance; raise error in
  B.charge budget reconstruction_work;
  let node_count = List.length (M.nodes mechanism) in
  List.iter (fun node ->
    (* Mechanism.get currently searches the declaration inventory. Account for
       its complete worst-case scan, not merely the successful endpoint. *)
    let per_node = String.length (M.Node.id node) + 1 in
    if node_count > B.remaining budget / per_node then B.charge budget (B.remaining budget + 1);
    B.charge budget (node_count * per_node);
    let actual = match M.get reconstructed (M.Node.id node) with Some value -> value | None ->
      Diagnostic.fail "component_assembly" "Component assembly changed source operation parameters or wiring." in
    let expected_raw = M.Node.to_json node and actual_raw = M.Node.to_json actual in
    let reserve raw = B.reserve_report budget raw; raw in
    let expected_raw = reserve expected_raw and actual_raw = reserve actual_raw in
    require (M.Node.kind actual = M.Node.kind node &&
      Json.equal (field "output" actual_raw) (field "output" expected_raw) &&
      M.Node.inputs actual = M.Node.inputs node &&
      Canonical.fingerprint (field "attributes" actual_raw) = Canonical.fingerprint (field "attributes" expected_raw))
      "Component assembly changed source operation parameters or wiring.") (M.nodes mechanism);
  let linked = Bioc_checker.Composition_check.check ~limits:limits.composition ~parent:work
      ~request:(A.composition assembly) ~registry:(A.registry assembly) () in
  if L.Result.passed linked then (
    let behavior = Component_behavior_check.check ?until ~limits:limits.behavior ~parent:work request assembly history in
    let name = match E.Check_result.outcome behavior with E.Pass -> "pass" | E.Fail -> "fail"
      | E.Unknown -> "unknown" | E.Unsupported -> "unsupported" in
    require (E.Check_result.outcome behavior = E.Pass) ("Reconstructed component behavior did not pass: " ^ name));
  B.reserve_report budget (L.Result.to_json linked);
  let usage = B.usage budget in
  linked,{work_charged=initial_work - W.remaining work;reconstruction_work;authority_work;
    request_bytes=usage.request_bytes;report_bytes=usage.report_bytes;retained_peak=usage.monitor_peak}
let check ?until ?limits ?parent request candidate assembly history =
  fst (check_with_usage ?until ?limits ?parent request candidate assembly history)

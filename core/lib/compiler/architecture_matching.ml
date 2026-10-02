open Bioc_wire
open Bioc_domain
module A = Architecture_contract
module R = Architecture_refinement
module Names = Map.Make (String)
module Ids = Set.Make (String)
module Work = Bioc_checker.Work_budget
let implementation_version = "biocompiler.ocaml.architecture_matching.v0.1"
let resource_profile = "biocompiler.architecture_matching.resources.v1"
let max_work = 50_000_000
let str value = Json.String value
let node_id node = Identity.Node.to_string (Behavior.node_id node)
let node_inputs node = List.map Identity.Node.to_string (Behavior.inputs node)
let node_role node = Option.map Identity.Role.to_string (Behavior.role node)
let mapping bindings = List.map (fun (local, remote) -> Identity.Node.to_string local, Identity.Node.to_string remote) bindings
let native_bindings bindings = List.map (fun (local, remote) -> Identity.Node.of_string local, Identity.Node.of_string remote) bindings
let hash = Canonical.fingerprint
let raw_field key raw = Json.field key (Json.object_fields raw)
type result = { values : A.Instance.t list; states : int; limited : bool; messages : string list }
let instances value = value.values
let states_examined value = value.states
let exhausted value = value.limited
let diagnostics value = value.messages
let result ?(states=0) ?(limited=false) ?(values=[]) messages = { values; states; limited; messages }
let instance_id refinement bindings = match R.match_policy refinement with
  | None -> R.id refinement
  | Some _ -> R.id refinement ^ ".match." ^ hash (Json.Object ["refinement", str (R.fingerprint refinement);
      "source_bindings", Json.Object (mapping bindings |> List.map (fun (local, remote) -> local, str remote))])
let instantiate refinement instance =
  Diagnostic.require (A.Instance.refinement_id instance = R.id refinement) "invalid_architecture_instance" "Instance refers to different supplied authority.";
  R.to_json refinement |> Json.object_fields |> List.map (fun (key, value) -> key,
      match key with
      | "id" -> str (A.Instance.id instance)
      | "source_bindings" -> Json.Object (mapping (A.Instance.source_bindings instance) |> List.map (fun (local, remote) -> local, str remote))
      | "match_policy" -> Json.Null
      | _ -> value) |> fun fields -> R.of_json (Json.Object fields)
let signature node = hash (Json.Object ["kind", str (Behavior.kind_name (Behavior.operation node));
    "attributes", Behavior.attributes node; "data_type", raw_field "data_type" (Behavior.node_json node);
    "contact_bound", Json.Bool (Behavior.contact_bound node); "input_count", Json.int (List.length (Behavior.inputs node));
    "has_role", Json.Bool (Behavior.role node <> None)])

let output_constraints ~charge ~reserve refinement source circuit =
  let outputs = R.output_contracts refinement in
  match outputs, circuit with
  | [], _ -> Names.empty, [], []
  | _, None -> Names.empty, [], ["matching_output_authority_missing"]
  | _, Some circuit ->
      let requirements = List.fold_left (fun map item -> Names.add (Circuit_request.Requirement.id item) item map)
          Names.empty (Circuit_request.requirements circuit) in
      let nodes = List.fold_left (fun map node -> Names.add (node_id node) node map) Names.empty (Behavior.nodes source) in
      let allowed = ref Names.empty and obligations = ref [] and diagnostics = ref [] in
      List.iter (fun output ->
          let requirement_id = Identity.Requirement.to_string (A.Output_binding.requirement_id output) in
          let reject code = diagnostics := (code ^ ":" ^ requirement_id) :: !diagnostics in
          match Names.find_opt requirement_id requirements with
          | None -> reject "matching_output_requirement_absent"
          | Some requirement ->
              charge 1;
              if Circuit_request.Product.fingerprint (A.Output_binding.product output) <> Circuit_request.Product.fingerprint (Circuit_request.Requirement.product requirement)
                || Circuit_request.Lifecycle.fingerprint (A.Output_binding.lifecycle output) <> Circuit_request.Lifecycle.fingerprint (Circuit_request.Requirement.lifecycle requirement)
              then reject "matching_output_contract_mismatch"
              else (
                let members = Circuit_request.Requirement.source_nodes requirement |> List.map Identity.Node.to_string |> Ids.of_list in
                let installed = List.fold_left (fun found node -> charge 1;
                    if Behavior.kind_name (Behavior.operation node) = "rule" && Ids.mem (node_id node) members then
                      match node_inputs node with _ :: _ :: actions -> List.fold_left (fun values item -> Ids.add item values) found actions
                        | _ -> found
                    else found) Ids.empty (Behavior.nodes source) in
                let role = Option.map Identity.Role.to_string (Circuit_request.Requirement.role requirement) in
                let candidates = Ids.filter (fun identity -> charge 1;
                    Ids.mem identity members && node_role (Names.find identity nodes) = role) installed in
                let local_ids = A.Output_binding.action_ids output |> List.map Identity.Node.to_string in
                let exact = Option.map (fun _ -> Circuit_request.Requirement.action_ids requirement |> List.map Identity.Node.to_string |> Ids.of_list)
                    (Circuit_request.Requirement.executable_behavior requirement) in
                let valid = match exact with None -> List.length local_ids = 1
                  | Some values -> Ids.cardinal values = List.length local_ids in
                if not valid then reject "matching_output_action_inventory"
                else (
                  let candidates = match exact with None -> candidates | Some exact -> Ids.inter candidates exact in
                  List.iter (fun local ->
                      let values = match Names.find_opt local !allowed with None -> candidates | Some old -> Ids.inter old candidates in
                      reserve (Json.Array (Ids.elements values |> List.map str));
                      allowed := Names.add local values !allowed) local_ids;
                  obligations := (local_ids, exact) :: !obligations))) outputs;
      !allowed, List.rev !obligations, List.rev !diagnostics

exception Exhausted
exception Complete of result
let match_refinement ?budget ?circuit ?(max_states=100_000) ?(max_instances=A.max_records) refinement source =
  Diagnostic.require (max_states >= 0 && max_states <= A.max_match_states) "invalid_architecture_matching_budget" "Invalid remaining architecture matching work.";
  Diagnostic.require (max_instances >= 0 && max_instances <= A.max_records) "invalid_architecture_matching_budget" "Invalid remaining architecture matching instances.";
  let budget = match budget with None -> Work.create ~profile:resource_profile ~error_code:"architecture_matching_limit" ~maximum:max_work ()
    | Some parent -> Work.nested ~parent ~profile:resource_profile ~error_code:"architecture_matching_limit" ~maximum:max_work () in
  let output = Work.create_output ~profile:resource_profile ~error_code:"architecture_matching_output_limit" ~max_bytes:(16 * 1024 * 1024) ~max_nodes:250_000 () in
  let reserve = Work.reserve_json output and charge = Work.charge budget in
  let model_behavior = R.behavior refinement in
  if Behavior.profile model_behavior <> Behavior.profile source || hash (Behavior.policies model_behavior) <> hash (Behavior.policies source)
  then result ["matching_execution_policy_mismatch"]
  else (
    let model = List.fold_left (fun map node -> Names.add (node_id node) node map) Names.empty (Behavior.nodes model_behavior)
    and original = List.fold_left (fun map node -> Names.add (node_id node) node map) Names.empty (Behavior.nodes source) in
    let allowed, obligations, diagnostics = output_constraints ~charge ~reserve refinement source circuit in
    if diagnostics <> [] then result diagnostics else (
      let signatures nodes = Names.map (fun node -> charge 1; signature node) nodes in
      let model_signatures = signatures model and source_signatures = signatures original in
      let source_index = Names.fold (fun identity signature map ->
          let existing = Option.value ~default:[] (Names.find_opt signature map) in
          Names.add signature (identity :: existing) map) source_signatures Names.empty |> Names.map List.rev in
      let anchors = R.source_bindings refinement |> mapping |> List.to_seq |> Names.of_seq in
      let candidates = Names.mapi (fun identity _ ->
          let options = Option.value ~default:[] (Names.find_opt (Names.find identity model_signatures) source_index) in
          let options = match Names.find_opt identity anchors with None -> options
            | Some anchor -> if List.mem anchor options then [anchor] else [] in
          let options = match Names.find_opt identity allowed with None -> options
            | Some permitted -> List.filter (fun identity -> charge 1; Ids.mem identity permitted) options in
          reserve (Json.Array (List.map str options)); options) model in
      if Names.exists (fun _ options -> options = []) candidates then result ["no_semantic_graph_match"] else (
        let order = Names.bindings candidates |> List.sort (fun (left, a) (right, b) ->
            let comparison = Int.compare (List.length a) (List.length b) in if comparison = 0 then String.compare left right else comparison) |> List.map fst in
        let bindings = ref Names.empty and inverse = ref Ids.empty and trail = ref [] and trail_length = ref 0
        and matches = ref [] and examined = ref 0 and match_count = ref 0 in
        let current ?(limited=false) messages = result ~states:!examined ~limited ~values:(List.rev !matches) messages in
        let rollback mark = while !trail_length > mark do
            let identity = List.hd !trail in trail := List.tl !trail; decr trail_length;
            inverse := Ids.remove (Names.find identity !bindings) !inverse; bindings := Names.remove identity !bindings
          done in
        let assign identity target =
          let pending = ref [identity, target] and valid = ref true in
          while !pending <> [] && !valid do
            let local, remote = List.hd !pending in pending := List.tl !pending;
            if !examined >= max_states then raise Exhausted;
            incr examined; charge 1;
            match Names.find_opt local !bindings with
            | Some previous -> if previous <> remote then valid := false
            | None ->
                if Ids.mem remote !inverse || not (Names.mem remote original)
                   || Names.find local model_signatures <> Names.find remote source_signatures
                   || (match Names.find_opt local anchors with Some anchor -> anchor <> remote | None -> false)
                   || (match Names.find_opt local allowed with Some values -> not (Ids.mem remote values) | None -> false)
                then valid := false
                else (
                  bindings := Names.add local remote !bindings; inverse := Ids.add remote !inverse;
                  trail := local :: !trail; incr trail_length;
                  let left = Names.find local model and right = Names.find remote original in
                  let edges = List.combine (node_inputs left) (node_inputs right) in
                  let edges = match node_role left, node_role right with Some left, Some right -> edges @ [left, right] | _ -> edges in
                  pending := edges @ !pending)
          done;
          !valid in
        let retain () =
          let allowed_output = List.for_all (fun (local_ids, exact) -> match exact with None -> true
              | Some expected -> Ids.equal expected (List.map (fun identity -> Names.find identity !bindings) local_ids |> Ids.of_list)) obligations in
          if not allowed_output then true
          else if !match_count >= max_instances then false
          else (
            let source_bindings = native_bindings (Names.bindings !bindings) in
            let instance = A.Instance.make ~id:(instance_id refinement source_bindings) ~refinement_id:(R.id refinement) ~source_bindings in
            reserve (A.Instance.to_json instance); matches := instance :: !matches; incr match_count; true) in
        try
          Names.iter (fun identity target -> if not (assign identity target) then raise (Complete (result ~states:!examined ["no_semantic_graph_match"]))) anchors;
          if Names.cardinal !bindings = Names.cardinal model then (
            let complete = retain () in current ~limited:(not complete) (if complete then [] else ["architecture_matching_instance_budget_exhausted"]))
          else (
            let first () = List.find (fun identity -> not (Names.mem identity !bindings)) order in
            let identity = first () in
            let stack = ref [identity, Names.find identity candidates, !trail_length] in
            while !stack <> [] do
              let identity, choices, mark = List.hd !stack in
              rollback mark;
              match choices with
              | [] -> stack := List.tl !stack
              | target :: remaining ->
                  stack := (identity, remaining, mark) :: List.tl !stack;
                  if assign identity target then (
                    if Names.cardinal !bindings = Names.cardinal model then (
                      if not (retain ()) then raise (Complete (current ~limited:true ["architecture_matching_instance_budget_exhausted"])))
                    else (
                      let identity = first () in
                      stack := (identity, Names.find identity candidates, !trail_length) :: !stack))
            done;
            result ~states:!examined ~values:(List.sort (fun left right -> String.compare (A.Instance.id left) (A.Instance.id right)) !matches)
              (if !matches = [] then ["no_semantic_graph_match"] else []))
        with Exhausted -> current ~limited:true ["architecture_matching_work_budget_exhausted"]
           | Complete value -> value)))

open Bioc_wire
module I = Bioc_domain.Policy_implementation
module A = Bioc_domain.Policy_component_assembly_rule
module C = Bioc_domain.Policy_component_material
module F = Bioc_domain.Policy_component_fragment
module U = Bioc_domain.Policy_implementation_binding
module Q = Bioc_domain.Policy_component_assembly_proposal
module Pin = Bioc_domain.Pinned_identity
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let slot = A.slot_name
(* Structured keys are internal matching labels, never implementation names or
   a replacement whole-graph material contract. *)
let endpoint_json (value:I.endpoint) = obj ["node",str value.node_id;"port",str value.port_id]
let wire_json (value:I.wire) = obj ["producer",endpoint_json value.producer;"consumer",endpoint_json value.consumer]
let input_json (value:I.external_input) = obj ["id",str value.input_id;
  "kind",str (match value.input_kind with I.Evidence_input -> "evidence" | I.Feedback_input -> "feedback");
  "consumer",endpoint_json value.consumer]
type local = { reference:A.node_ref; key:string; model:I.model }
type proposal = { implementation:I.t; binding:U.t; assembly:Q.t }
let arrange ?(charge=Bioc_checker.Policy_generation_meter.no_charge) ?source_inputs ~library ~rule (lowered:Policy_implementation_lowering.proposal) =
  let module Meter = Bioc_checker.Policy_generation_meter.Make (struct let charge = charge end) in
  let module List = Meter.List in
  let module String = Meter.String in
  let module Json = Meter.Json in
  let module Canonical = Meter.Canonical in
  let outer_charge = charge in
  let get key raw = Json.field key (Json.object_fields raw) in
  let set key value raw = obj ((key,value)::List.remove_assoc key (Json.object_fields raw)) in
  let key owner id = Canonical.encode (arr [str (slot owner);str id]) in
  let group_json (value:I.atomic_group) = obj ["id",str value.group_id;
    "arbiter",str value.arbiter;"commits",arr (List.map str value.commits)] in
  Meter.serialization (A.to_json rule);
  Meter.serialization (I.to_json lowered.implementation);
  Meter.serialization (U.to_json lowered.binding);

  let supported condition message = Diagnostic.require condition "policy_component_lowering_unsupported" message in
  let remaining = ref 1000000 in
  let charge amount = Diagnostic.require (amount>=0 && amount<= !remaining)
    "policy_component_lowering_search_exhausted" "Bounded component graph matching exhausted its work allowance.";
    outer_charge amount;
    remaining := !remaining-amount in
  let fragment owner = C.fragment (A.component rule owner) in
  let local = List.map (fun (reference:A.node_ref) ->
    let nodes = F.nodes (fragment reference.slot) in charge (List.length nodes);
    let node = List.find (fun (node:F.node) -> node.node_id=reference.node_id) nodes in
    {reference;key=key reference.slot reference.node_id;model=node.model}) (A.node_order rule) in
  let implementation = lowered.implementation and actual = I.nodes lowered.implementation in
  supported (List.length local=List.length actual && List.length actual<=64)
    "The original component union and source-produced graph need equal bounded primitive inventories.";
  let layout = I.slot_layout implementation and original_layout = A.layout rule in
  supported (layout.layout_id=original_layout.layout_id && layout.slots=original_layout.slots)
    "The original component union has a different complete replication layout.";
  let local_endpoint owner (value:I.endpoint) : I.endpoint =
    {node_id=key owner value.node_id;port_id=value.port_id} in
  let boundary (reference:A.boundary_ref) =
    let ports = F.boundary_ports (fragment reference.slot) in charge (List.length ports);
    let port = List.find (fun (port:F.boundary_port) -> port.boundary_id=reference.boundary_id) ports in
    local_endpoint reference.slot port.endpoint in
  let wanted_wires = List.map (function
    | A.Local_wire {slot;index} -> let row = List.nth (F.wires (fragment slot)) index in
      ({producer=local_endpoint slot row.producer;consumer=local_endpoint slot row.consumer}:I.wire)
    | A.Cross_link kind -> let row = List.find (fun (row:A.link) -> row.kind=kind) (A.links rule) in
      ({producer=boundary row.producer;consumer=boundary row.consumer}:I.wire)) (A.wire_order rule) in
  let wanted_inputs = List.map (fun (row:A.input_ref) ->
    let input = List.find (fun (value:F.external_slot) -> value.slot_id=row.external_slot)
      (F.external_slots (fragment row.slot)) in
    ({input_id=row.input_id;input_kind=input.input_kind;consumer=local_endpoint row.slot input.consumer}:I.external_input))
      (A.input_order rule) in
  (* The new family can contain graph-symmetric evidence banks. Original source
     channels constrain this search; matching primitive shapes alone cannot
     decide which original observation feeds which supplied component input. *)
  let required_inputs=match source_inputs with
    |None->supported(not(U.is_network lowered.binding || U.is_finite_machine lowered.binding || U.is_two_observation lowered.binding || U.is_multi_product lowered.binding))
        (if U.is_network lowered.binding then "Network arrangement requires the original source-to-input inventory."
         else if U.is_finite_machine lowered.binding then "Finite-machine arrangement requires the original source-to-input inventory."
         else if U.is_multi_product lowered.binding then "Multi-product arrangement requires the original source-to-input inventory."
         else "Two-observation arrangement requires the original source-to-input inventory.");None
    |Some requested->
      supported(U.is_network lowered.binding || U.is_finite_machine lowered.binding || U.is_two_observation lowered.binding || U.is_multi_product lowered.binding)
        "Original source-to-input arrangement requires an explicit observation-composition or multi-product family.";
      let originals=List.map(fun(value:U.observation)->value.source,value.input)(U.observations lowered.binding) @
        List.map(fun(value:U.effect_binding)->value.source,value.feedback)(U.effects lowered.binding) in
      let names pairs=List.sort String.compare(List.map fst pairs) in
      let targets pairs=List.sort String.compare(List.map snd pairs) in
      supported(List.length requested=List.length originals && names requested=names originals &&
        List.length(List.sort_uniq String.compare(List.map fst requested))=List.length requested &&
        targets requested=List.sort String.compare(List.map(fun(value:I.external_input)->value.input_id)wanted_inputs) &&
        List.length(List.sort_uniq String.compare(List.map snd requested))=List.length requested)
        "Original source-to-input inventory must bind every observation and effect exactly once to the supplied complete input inventory.";
      Some(List.map(fun(source,input)->input,List.assoc source requested)originals) in
  let wanted_groups = List.map (fun (row:A.group_ref) ->
    let group = List.find (fun (value:I.atomic_group) -> value.group_id=row.group_id)
      (F.atomic_groups (fragment row.slot)) in
    ({group_id=group.group_id;arbiter=key row.slot group.arbiter;
      commits=List.map (key row.slot) group.commits}:I.atomic_group)) (A.group_order rule) in
  let wanted_exports = List.map (fun (row:A.endpoint_ref) ->
    ({node_id=key row.node.slot row.node.node_id;port_id=row.port_id}:I.endpoint)) (A.export_order rule) in
  let signature (model:I.model) =
    let encoded = Canonical.encode (obj ["identity",Pin.to_json model.identity;
      "configuration_digest",str model.configuration_digest;"body",I.model_body_to_json model]) in
    charge (String.length encoded); encoded in
  let actual_models = List.map (fun (value:I.node) -> value,signature value.model) actual in
  let local_models = List.map (fun value -> value,signature value.model) local in
  (* Coupled circuits can have 49 nodes: repeatedly charging every complete
     signature, including already-used nodes, exceeds the fixed search budget
     even on a successful path without backtracking. Exact immutable keys
     select candidates; collisions still compare every signature byte. *)
  let module Exact_index = Hashtbl.Make(struct
    type t = string
    let hash value = charge (1+Stdlib.String.length value);Hashtbl.hash value
    let equal left right = charge (1+Stdlib.String.length left+Stdlib.String.length right);
      Stdlib.String.equal left right
  end) in
  let model_index = if U.is_coupled lowered.binding then (
    charge 64;
    let index = Exact_index.create 64 in
    List.iter (fun ((_,encoded) as entry) -> charge 1;
      let previous=Option.value (Exact_index.find_opt index encoded) ~default:[] in
      Exact_index.replace index encoded (entry::previous)) actual_models;
    Some index) else None in
  let candidates_for wanted = match model_index with
    | None -> actual_models
    | Some index ->
      let reversed=Option.value (Exact_index.find_opt index wanted) ~default:[] in
      charge (1+List.length reversed);List.rev reversed in
  let original_wires = I.wires implementation in
  (* Resolve immutable endpoint names once. Each index key still compares the
     complete name or port; integer positions only name this invocation's
     already-checked, ordered node inventories. *)
  let module Wire_index = Hashtbl.Make(struct
    type t = int * string * int * string
    let hash ((_,producer_port,_,consumer_port) as value) =
      charge (3+Stdlib.String.length producer_port+Stdlib.String.length consumer_port);
      Hashtbl.hash value
    let equal (a,ap,b,bp) (c,cp,d,dp) =
      charge (4+Stdlib.String.length ap+Stdlib.String.length bp+
        Stdlib.String.length cp+Stdlib.String.length dp);
      a=c && b=d && Stdlib.String.equal ap cp && Stdlib.String.equal bp dp
  end) in
  let indexed_wires=match model_index with None->None|Some _->
    charge (128+List.length wanted_wires);
    let actual_positions=Exact_index.create 64 and local_positions=Exact_index.create 64 in
    List.iteri(fun ordinal (value:I.node)->charge 1;Exact_index.add actual_positions value.node_id ordinal)actual;
    List.iteri(fun ordinal value->charge 1;Exact_index.add local_positions value.key ordinal)local;
    let position index id=match Exact_index.find_opt index id with Some value->value|None->assert false in
    let actual_wires=List.map(fun(value:I.wire)->charge 1;
      position actual_positions value.producer.node_id,value.producer.port_id,
      position actual_positions value.consumer.node_id,value.consumer.port_id)original_wires in
    let expected=Wire_index.create(List.length wanted_wires)in
    List.iter(fun(value:I.wire)->charge 1;
      Wire_index.replace expected
        (position local_positions value.producer.node_id,value.producer.port_id,
         position local_positions value.consumer.node_id,value.consumer.port_id)())wanted_wires;
    Some(actual_positions,local_positions,actual_wires,expected)in
  let lookup pairs id = charge (List.length pairs);
    List.find_map (fun (candidate,value) -> if String.equal id candidate then Some value else None) pairs in
  let same_multiset inspect left right =
    charge (List.length left*List.length left+List.length right*List.length right);
    let compared left right = inspect left; inspect right; compare left right in
    let left=List.sort compared left and right=List.sort compared right in
    List.iter inspect left; List.iter inspect right; left=right in
  let inspect_wire value = Meter.preflight (wire_json value) in
  let inspect_endpoint value = Meter.preflight (endpoint_json value) in
  let inspect_text value = outer_charge (1+String.length value) in
  let inspect_group (arbiter,commits) = inspect_text arbiter; List.iter inspect_text commits in
  let partial pairs coordinates = match indexed_wires with
    |Some(_,_,wires,expected)->
      let count=List.length actual in charge count;
      let mapped=Array.make count None in
      List.iter(fun(candidate,target)->charge 1;mapped.(candidate)<-Some target)coordinates;
      List.for_all(fun(producer,producer_port,consumer,consumer_port)->charge 3;
        match mapped.(producer),mapped.(consumer)with
        |Some before,Some after->Wire_index.mem expected(before,producer_port,after,consumer_port)
        |_->true)wires
    |None->List.for_all (fun (value:I.wire) -> charge 1;
      match lookup pairs value.producer.node_id,lookup pairs value.consumer.node_id with
      | Some producer,Some consumer ->
        let mapped:I.wire = {producer={node_id=producer;port_id=value.producer.port_id};
          consumer={node_id=consumer;port_id=value.consumer.port_id}} in
        charge (List.length wanted_wires); List.exists (fun expected -> inspect_wire mapped; inspect_wire expected; mapped=expected) wanted_wires
      | _ -> true) original_wires in
  let finish pairs =
    let local_id id = match lookup pairs id with Some value -> value | None -> assert false in
    let endpoint (value:I.endpoint) : I.endpoint = {node_id=local_id value.node_id;port_id=value.port_id} in
    let wires = List.map (fun (value:I.wire) -> charge 1;
      ({producer=endpoint value.producer;consumer=endpoint value.consumer}:I.wire)) original_wires in
    if not (same_multiset inspect_wire wires wanted_wires) then None else
    if not (same_multiset inspect_endpoint (List.map endpoint (I.semantic_exports implementation)) wanted_exports) then None else
    let inputs = List.filter_map (fun (value:I.external_input) ->
      let consumer = endpoint value.consumer in charge (List.length wanted_inputs);
      match List.filter (fun (target:I.external_input) -> target.input_kind=value.input_kind && target.consumer=consumer &&
        (match required_inputs with None->true|Some bindings->List.assoc_opt value.input_id bindings=Some target.input_id)) wanted_inputs with
      | [target] -> Some (value.input_id,target.input_id) | _ -> None) (I.inputs implementation) in
    if List.length inputs<>List.length (I.inputs implementation) ||
      not (same_multiset inspect_text (List.map snd inputs) (List.map (fun (value:I.external_input) -> value.input_id) wanted_inputs)) then None else
    let groups = List.map (fun (value:I.atomic_group) -> charge 1;local_id value.arbiter,List.map local_id value.commits)
      (I.atomic_groups implementation) in
    if not (same_multiset inspect_group groups (List.map (fun (value:I.atomic_group) -> value.arbiter,value.commits) wanted_groups)) then None
    else Some (pairs,inputs) in
  let rec search pairs coordinates used candidates = outer_charge 1;match candidates with
    | [] -> finish pairs
    | (target,wanted)::rest ->
      let rec choose candidates = outer_charge 1;match candidates with
        | [] -> None
        | ((candidate:I.node),provided)::remaining_candidates ->
          charge (1+String.length wanted+String.length provided);
          if List.exists (String.equal candidate.node_id) used || wanted<>provided then choose remaining_candidates else
          let next = (candidate.node_id,target.key)::pairs in
          let next_coordinates=match indexed_wires with None->[]|Some(actual_positions,local_positions,_,_)->
            charge 1;
            (Exact_index.find actual_positions candidate.node_id,Exact_index.find local_positions target.key)::coordinates in
          if not (partial next next_coordinates) then choose remaining_candidates else
          match search next next_coordinates (candidate.node_id::used) rest with Some _ as result -> result | None -> choose remaining_candidates in
      choose (candidates_for wanted) in
  let pairs,input_pairs = match search [] [] [] local_models with Some value -> value | None ->
    Diagnostic.fail "policy_component_lowering_unsupported"
      "No complete model, wiring, input, group and export bijection matches the original component composition." in
  let actual_id local = charge (List.length pairs);
    match List.find_opt (fun (_,value) -> String.equal value local) pairs with Some (actual,_) -> actual | None -> assert false in
  let endpoint (value:I.endpoint) : I.endpoint = {node_id=actual_id value.node_id;port_id=value.port_id} in
  let nodes = List.map (fun value -> outer_charge (1+String.length value.key); obj ["id",str (actual_id value.key);
    "model",Pin.to_json value.model.identity;"configuration_digest",str value.model.configuration_digest]) local in
  let wires = List.map (fun (value:I.wire) -> wire_json {producer=endpoint value.producer;consumer=endpoint value.consumer}) wanted_wires in
  let inputs = List.map (fun (value:I.external_input) -> input_json {value with consumer=endpoint value.consumer}) wanted_inputs in
  let groups = List.map (fun (value:I.atomic_group) -> group_json {value with arbiter=actual_id value.arbiter;
    commits=List.map actual_id value.commits}) wanted_groups in
  let raw = I.to_json implementation |> set "nodes" (arr nodes) |> set "wires" (arr wires)
    |> set "inputs" (arr inputs) |> set "atomic_groups" (arr groups)
    |> set "semantic_exports" (arr (List.map (fun value -> endpoint_json (endpoint value)) wanted_exports)) in
  let rename_input field raw =
    match List.assoc_opt (Json.string (get field raw)) input_pairs with
    | Some after -> set field (str after) raw | None -> assert false in
  let binding = U.to_json lowered.binding in
  let binding = binding
    |> set "observations" (arr (List.map (rename_input "input") (Json.array (get "observations" binding))))
    |> set "effects" (arr (List.map (rename_input "feedback") (Json.array (get "effects" binding)))) in
  let assembly_raw = obj ["schema_version",str (if A.is_multi_site rule then Q.multi_site_schema_version else if A.is_grounded_helper rule then Q.grounded_helper_schema_version
      else if A.is_multi_member rule then Q.multi_member_schema_version
      else if A.is_instanced rule then Q.instance_schema_version else Q.schema_version);
    "profile",str (if A.is_multi_site rule then Q.multi_site_profile else if A.is_grounded_helper rule then Q.grounded_helper_profile
      else if A.is_multi_member rule then Q.multi_member_profile
      else if A.is_instanced rule then A.instance_profile else Q.profile);
    "rule",Pin.to_json (A.identity rule);"nodes",arr (List.map (fun value ->
      obj ["slot",str (slot value.reference.slot);"node",str value.reference.node_id;
        "actual",str (actual_id value.key)]) local)] in
  Meter.serialization assembly_raw;
  let assembly = Q.of_json assembly_raw in
  Meter.serialization raw; Meter.serialization binding;
  Meter.serialization (I.library_to_json library);
  {implementation=I.of_json ~library raw;binding=U.of_json binding;assembly}

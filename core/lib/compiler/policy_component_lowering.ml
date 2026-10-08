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
let arrange ?(charge=Bioc_checker.Policy_generation_meter.no_charge) ~library ~rule (lowered:Policy_implementation_lowering.proposal) =
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
  let original_wires = I.wires implementation in
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
  let partial pairs = List.for_all (fun (value:I.wire) -> charge 1;
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
      match List.filter (fun (target:I.external_input) -> target.input_kind=value.input_kind && target.consumer=consumer) wanted_inputs with
      | [target] -> Some (value.input_id,target.input_id) | _ -> None) (I.inputs implementation) in
    if List.length inputs<>List.length (I.inputs implementation) ||
      not (same_multiset inspect_text (List.map snd inputs) (List.map (fun (value:I.external_input) -> value.input_id) wanted_inputs)) then None else
    let groups = List.map (fun (value:I.atomic_group) -> charge 1;local_id value.arbiter,List.map local_id value.commits)
      (I.atomic_groups implementation) in
    if not (same_multiset inspect_group groups (List.map (fun (value:I.atomic_group) -> value.arbiter,value.commits) wanted_groups)) then None
    else Some (pairs,inputs) in
  let rec search pairs used candidates = outer_charge 1;match candidates with
    | [] -> finish pairs
    | (target,wanted)::rest ->
      let rec choose candidates = outer_charge 1;match candidates with
        | [] -> None
        | ((candidate:I.node),provided)::remaining_candidates ->
          charge (1+String.length wanted+String.length provided);
          if List.exists (String.equal candidate.node_id) used || wanted<>provided then choose remaining_candidates else
          let next = (candidate.node_id,target.key)::pairs in
          if not (partial next) then choose remaining_candidates else
          match search next (candidate.node_id::used) rest with Some _ as result -> result | None -> choose remaining_candidates in
      choose actual_models in
  let pairs,input_pairs = match search [] [] local_models with Some value -> value | None ->
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
  let assembly_raw = obj ["schema_version",str (if A.is_instanced rule then Q.instance_schema_version else Q.schema_version);
    "profile",str (if A.is_instanced rule then A.instance_profile else Q.profile);
    "rule",Pin.to_json (A.identity rule);"nodes",arr (List.map (fun value ->
      obj ["slot",str (slot value.reference.slot);"node",str value.reference.node_id;
        "actual",str (actual_id value.key)]) local)] in
  Meter.serialization assembly_raw;
  let assembly = Q.of_json assembly_raw in
  Meter.serialization raw; Meter.serialization binding;
  Meter.serialization (I.library_to_json library);
  {implementation=I.of_json ~library raw;binding=U.of_json binding;assembly}

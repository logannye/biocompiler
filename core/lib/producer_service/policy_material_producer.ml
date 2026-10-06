open Bioc_wire
module R=Bioc_domain.Policy_material_request
module S=Bioc_domain.Policy_realization_request
module O=Bioc_domain.Policy_operational
module I=Bioc_domain.Policy_implementation
module U=Bioc_domain.Policy_implementation_binding
module C=Bioc_domain.Policy_material_contract
module PM=Bioc_domain.Policy_mrna_structure
module K=Bioc_domain.Construction_content
module Service=Bioc_service.Policy_material_service
module Pin=Bioc_domain.Pinned_identity
let str value=Json.String value
let obj value=Json.Object value
let arr value=Json.Array value
let get key raw=Json.field key(Json.object_fields raw)
let set key value raw=Json.Object((key,value)::List.remove_assoc key(Json.object_fields raw))
let endpoint_json(value:I.endpoint)=obj["node",str value.node_id;"port",str value.port_id]
let wire_json(value:I.wire)=obj["producer",endpoint_json value.producer;"consumer",endpoint_json value.consumer]
let input_json(value:I.external_input)=obj["id",str value.input_id;
  "kind",str(match value.input_kind with I.Evidence_input->"evidence"|I.Feedback_input->"feedback");
  "consumer",endpoint_json value.consumer]
let group_json(value:I.atomic_group)=obj["id",str value.group_id;"arbiter",str value.arbiter;
  "commits",arr(List.map str value.commits)]

(* This is an untrusted bounded graph arrangement producer. Complete model
   bodies and whole graph relations must match before order or external names
   are changed. Fresh source/graph/material checking remains authoritative. *)
let arrange ~library ~(contract:C.t) (lowered:Bioc_compiler.Policy_implementation_lowering.proposal)=
  let kernel=C.kernel contract and implementation=lowered.implementation in
  let local=C.nodes kernel and actual=I.nodes implementation in
  let supported condition message=Diagnostic.require condition "policy_material_lowering_unsupported" message in
  supported(List.length local=List.length actual && List.length actual<=64)
    "The supplied case and produced graph need equal bounded primitive inventories.";
  let layout=I.slot_layout implementation in
  supported(layout.layout_id=C.layout_id kernel && layout.slots=C.slots kernel)
    "The supplied material case has a different complete model replication layout.";
  let remaining=ref 1000000 in
  let charge amount=Diagnostic.require(amount>=0 && amount<= !remaining)
      "policy_material_lowering_search_exhausted" "Bounded complete material graph matching exhausted its work allowance.";
    remaining:= !remaining-amount in
  let signature(model:I.model)=
    let raw=obj["identity",Pin.to_json model.identity;"configuration_digest",str model.configuration_digest;
      "body",I.model_body_to_json model]in
    let encoded=Canonical.encode raw in charge(String.length encoded);encoded in
  let actual_models=List.map(fun(value:I.node)->value,signature value.model)actual in
  let local_models=List.map(fun(value:C.local_node)->value,signature value.model)local in
  let original_wires=I.wires implementation and wanted_wires=C.wires kernel in
  let lookup pairs id=charge(List.length pairs);List.assoc_opt id pairs in
  let same_multiset left right=
    charge(List.length left*List.length left+List.length right*List.length right);
    List.sort compare left=List.sort compare right in
  let partial pairs=
    List.for_all(fun(value:I.wire)->charge 1;
      match lookup pairs value.producer.node_id,lookup pairs value.consumer.node_id with
      |Some producer,Some consumer->
        let mapped:I.wire={producer={node_id=producer;port_id=value.producer.port_id};
          consumer={node_id=consumer;port_id=value.consumer.port_id}}in
        charge(List.length wanted_wires);List.mem mapped wanted_wires
      |_->true)original_wires in
  let finish pairs=
    let local_id id=match lookup pairs id with Some value->value|None->assert false in
    let mapped_endpoint(value:I.endpoint):I.endpoint={node_id=local_id value.node_id;port_id=value.port_id}in
    let mapped_wires=List.map(fun(value:I.wire)->charge 1;
      ({producer=mapped_endpoint value.producer;consumer=mapped_endpoint value.consumer}:I.wire))original_wires in
    if not(same_multiset mapped_wires wanted_wires)then None else
    let mapped_exports=List.map mapped_endpoint(I.semantic_exports implementation)in
    if not(same_multiset mapped_exports(C.semantic_exports kernel))then None else
    let input_pairs=List.filter_map(fun(value:I.external_input)->
      let consumer=mapped_endpoint value.consumer in
      charge(List.length(C.inputs kernel));
      match List.filter(fun(target:I.external_input)->target.input_kind=value.input_kind && target.consumer=consumer)(C.inputs kernel)with
      |[target]->Some(value.input_id,target.input_id)|_->None)(I.inputs implementation)in
    if List.length input_pairs<>List.length(I.inputs implementation) ||
      not(same_multiset(List.map snd input_pairs)(List.map(fun(value:I.external_input)->value.input_id)(C.inputs kernel)))then None else
    let groups=List.map(fun(value:I.atomic_group)->charge 1;local_id value.arbiter,List.map local_id value.commits)(I.atomic_groups implementation)
    and wanted_groups=List.map(fun(value:I.atomic_group)->value.arbiter,value.commits)(C.atomic_groups kernel)in
    if not(same_multiset groups wanted_groups)then None else Some(pairs,input_pairs)in
  let rec search pairs used=function
    |[]->finish pairs
    |((target:C.local_node),wanted)::rest->
      let rec choose=function
        |[]->None
        |((candidate:I.node),provided)::remaining_candidates->
          charge(1+String.length wanted+String.length provided);
          if List.mem candidate.node_id used || wanted<>provided then choose remaining_candidates else
          let next=(candidate.node_id,target.local_id)::pairs in
          if not(partial next)then choose remaining_candidates else
          match search next(candidate.node_id::used)rest with Some _ as found->found|None->choose remaining_candidates in
      choose actual_models in
  let pairs,input_pairs=match search [] [] local_models with Some value->value|None->
    Diagnostic.fail "policy_material_lowering_unsupported"
      "No complete model, wiring, input, atomic-group and export bijection matches the supplied material case."in
  let actual_id id=charge(List.length pairs);match List.find_opt(fun(_,local)->local=id)pairs with
    |Some(actual,_)->actual|None->assert false in
  let actual_endpoint(value:I.endpoint):I.endpoint={node_id=actual_id value.node_id;port_id=value.port_id}in
  let nodes=List.map(fun(value:C.local_node)->obj["id",str(actual_id value.local_id);
    "model",Pin.to_json value.model.identity;"configuration_digest",str value.model.configuration_digest])local in
  let wires=List.map(fun(value:I.wire)->wire_json{producer=actual_endpoint value.producer;consumer=actual_endpoint value.consumer})wanted_wires in
  let inputs=List.map(fun(value:I.external_input)->input_json{value with consumer=actual_endpoint value.consumer})(C.inputs kernel)in
  let groups=List.map(fun(value:I.atomic_group)->group_json{value with arbiter=actual_id value.arbiter;
    commits=List.map actual_id value.commits})(C.atomic_groups kernel)in
  let exports=List.map(fun value->endpoint_json(actual_endpoint value))(C.semantic_exports kernel)in
  let raw=I.to_json implementation|>set "nodes"(arr nodes)|>set "wires"(arr wires)|>set "inputs"(arr inputs)
    |>set "atomic_groups"(arr groups)|>set "semantic_exports"(arr exports)in
  let rename_input key raw=let before=Json.string(get key raw)in
    match List.assoc_opt before input_pairs with Some after->set key(str after)raw|None->assert false in
  let binding=U.to_json lowered.binding
    |>fun raw->set "observations"(arr(List.map(rename_input "input")(Json.array(get "observations" raw))))raw
    |>fun raw->set "effects"(arr(List.map(rename_input "feedback")(Json.array(get "effects" raw))))raw in
  let proposal=C.proposal_of_json(obj["schema_version",str C.proposal_schema;
    "contract_digest",str(C.fingerprint contract);"nodes",arr(List.map(fun(value:C.local_node)->
      obj["local_id",str value.local_id;"node_id",str(actual_id value.local_id)])local)])in
  I.of_json ~library raw,U.of_json binding,proposal

let compile payload=
  let fields=Json.object_fields ~path:"/payload" payload in
  Json.exact_fields ~path:"/payload"["request";"limits"]fields;
  let raw=Json.field "request" fields in
  let request=R.of_json raw in
  let original=R.implementation_request request in
  let source=Bioc_checker.Policy_admission.admit ~document:(S.document original) ~descriptors:(S.definitions original)in
  let behavior=Bioc_compiler.Policy_lowering.lower source in
  let admitted=Bioc_checker.Policy_realization_admission.admit ~request:original ~behavior in
  let lowered=Bioc_compiler.Policy_implementation_lowering.lower ~admitted ~library:(S.implementation_library original)in
  let contract=R.material_contract request in
  let actual,binding,proposed=arrange ~library:(S.implementation_library original) ~contract lowered in
  let authority=C.structure_authority contract in
  let content=Bioc_compiler.Construction_producer.construct_template ~member_order:(PM.member_order authority)(PM.template authority)in
  let candidate=Json.Object["schema_version",Json.String Service.candidate_schema;
    "behavior",O.behavior_to_json behavior;"implementation",I.to_json actual;
    "binding",U.to_json binding;"material_binding",C.proposal_to_json proposed;"construction",K.to_json content]in
  Service.check ~export:false ~request:raw ~candidate ~limits:(Json.field "limits" fields)

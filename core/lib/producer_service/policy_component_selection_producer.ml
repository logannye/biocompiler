open Bioc_wire
module R = Bioc_domain.Policy_component_selection_request
module V = Bioc_domain.Policy_component_selection_candidate
module C = Bioc_domain.Policy_component_material_candidate
module CR = Bioc_domain.Policy_component_material_request
module I = Bioc_domain.Policy_realization_request
module K = Bioc_domain.Construction_content
module N = Bioc_domain.Molecule
module Input = Bioc_domain.Policy_material_request
let str value=Json.String value
let obj fields=Json.Object fields
let arr values=Json.Array values

(* Length and rank here are an untrusted proposal. Only the subsequent complete
   independent child checks may authorize material, eligibility or the winner. *)
let produce ~charge original =
  let winner=ref None in
  let maximum=(R.predicate original).max_total_nt in
  let rows=List.map (fun (alternative:R.alternative) ->
    charge (1+String.length alternative.id);
    let raw=Policy_component_material_producer.construct_candidate ~charge alternative.request in
    let library=I.implementation_library (CR.implementation_request alternative.request) in
    let candidate=C.of_json ~charge ~library raw in
    let length=match K.inventory (C.construction candidate) with
      | None -> None
      | Some inventory ->
          let molecules=K.Inventory.molecules inventory in
          List.iter (fun molecule -> charge (1+String.length (N.sequence molecule))) molecules;
          (match molecules with [molecule] -> Some (String.length (N.sequence molecule)) | _ -> None) in
    (match length with
     | Some length ->
         charge 1;
         if length<=maximum then (match !winner with
           | None -> winner:=Some alternative
           | Some (previous:R.alternative) ->
               charge (1+String.length alternative.id+String.length previous.id);
               if alternative.rank<previous.rank ||
                 (alternative.rank=previous.rank && String.compare alternative.id previous.id<0)
               then winner:=Some alternative)
     | None -> ());
    charge 3;
    obj ["id",str alternative.id;"candidate",raw]) (R.evaluation_order original) in
  charge 4;
  let raw=obj ["schema_version",str V.schema_version;"alternatives",arr rows;
    "selected_id",(match !winner with None->Json.Null | Some value->str value.id)] in
  let bytes=Input.preflight ~max_bytes:R.max_input_bytes ~max_nodes:R.max_input_nodes
    ~max_depth:R.max_input_depth ~charge raw in
  charge bytes;
  ignore (Canonical.encode_bounded ~max_bytes:R.max_input_bytes raw);
  raw

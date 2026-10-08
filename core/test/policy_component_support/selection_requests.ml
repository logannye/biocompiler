open Bioc_wire
open Literals

(* Independently authored ORIGINALS for the one-A-program selection witness.
   The leader's two possible strings and all concatenate fates are supplied
   premises. Neither a candidate nor a producer/checker constructs expected data.
   In particular Long is not the existing state-reading B program. *)
type variant = Short | Long | Equal_length
type case = { id:string; rank:int; request:Json.t; expected_sequence:string }

let leader = function Short -> "CC" | Long -> "CGC" | Equal_length -> "GG"
let offset = function Short | Equal_length -> 2 | Long -> 3
let expected_sequence = function
  | Short -> "CCAUGGCUUAAGGAAAA"
  | Long -> "CGCAUGGCUUAAGGAAAA"
  | Equal_length -> "GGAUGGCUUAAGGAAAA"

(* The same root/template/member/feature identities and supplied chemistry are
   retained for both alternatives. Only the leader extent, adjacent join and
   resulting driver-feature/tail positions change. The 15-base driver is an
   independently declared literal, not a slice of the expected output string. *)
let material_authority variant =
  let leader_sequence=leader variant and join_offset=offset variant in
  let p=M.Provenance.of_json provenance in
  let output_chemistry frame=chemistry frame true
    |> put ["terminal_tail";"path"] (path frame (join_offset+11) (join_offset+15)) in
  let facets=["cap";"start_end";"finish_end";"terminal_tail";"modification_inventory"] in
  let dispositions source copied=List.map (fun facet ->
    let component=T.Component.of_string facet and carry=List.mem facet copied in
    T.Chemistry_disposition.make ~source_id:source ~component
      ~decision:(if carry then T.Chemistry_disposition.Mapped_copy else T.Chemistry_disposition.Not_carried)
      ~destination_components:(if carry then [component] else []) ~provenance:p) facets in
  let chemistry_transition=T.Chemistry.make ~mode:T.Chemistry.Explicit_output
    ~output:(Some (H.of_json (output_chemistry "join.frame")))
    ~dispositions:(dispositions "leader_A" ["cap";"start_end";"modification_inventory"] @
      dispositions "driver_body" ["finish_end";"terminal_tail";"modification_inventory"])
    ~provenance:p in
  let placed source id kind first last reading_frame=
    T.Feature_disposition.make ~source_id:source ~feature_id:id ~decision:T.Feature_disposition.Exact
      ~outputs:[N.Feature.of_json (feature "join.frame" id kind first last reading_frame)] ~provenance:p in
  let feature_transition=T.Feature.make ~dispositions:[
    placed "leader_A" "utr5" "five_prime_utr" 0 join_offset Json.Null;
    placed "driver_body" "cds" "coding_sequence" join_offset (join_offset+9) (Json.int 0);
    placed "driver_body" "utr3" "three_prime_utr" (join_offset+9) (join_offset+11) Json.Null;
    placed "driver_body" "poly_a" "poly_a_tail" (join_offset+11) (join_offset+15) Json.Null]
    ~added:[] ~provenance:p in
  let whole id=CT.Selection.make (CT.Value_ref.make ~kind:CT.Value_ref.Root ~id) in
  let step=CT.Transform_step.make ~id:"join" ~operation:(CT.Operation.make
    (CT.Operation.Concatenate [whole "leader_A";whole "driver_body"]))
    ~ports:[CT.Product_port.make ~id:"joined" ~space_id:"join.frame" ~alphabet:G.Rna ~topology:G.Linear
      ~chemistry_transition ~feature_transition] ~assumptions:[] ~provenance:p in
  let output=CT.Output_member.make ~id:"payload" ~value:(CT.Value_ref.make ~kind:CT.Value_ref.Product ~id:"joined")
    ~space_id:"payload.frame" ~form:N.Delivered_rna ~sequence_extent:H.Complete ~coding_status:N.Coding ~provenance:p in
  let requirement=CT.Member_requirement.make ~id:"payload" ~category:CT.Member_requirement.Payload
    ~subject:(CT.Member_requirement.Materialized "payload")
    ~roles:[CT.Role.make ~id:"payload.role" ~role:"payload" ~purpose:N.Role.Requested_payload ~compartment:"cytoplasm"] in
  let structure=PS.make ~member_id:"payload" ~form:PS.Delivered_rna ~topology:G.Linear
    ~regions:(List.map (fun (id,kind) -> PS.Region.make ~feature_id:id ~kind)
      ["utr5","five_prime_utr";"cds","coding_sequence";"utr3","three_prime_utr";"poly_a","poly_a_tail"])
    ~provenance:p in
  let template=PT.make ~id:"fixture.join.A"
    ~sources:[CT.Root_source.of_json (root "leader_A" leader_sequence false);
              CT.Root_source.of_json (root "driver_body" "AUGGCUUAAGGAAAA" true)]
    ~steps:[step] ~output_members:[output] ~requirements:[requirement] ~payload_structures:[structure] () in
  obj ["schema_version",str "biocompiler.policy_mrna_structure_authority.v0.1";
    "profile",str "biocompiler.policy_mrna_completeness.v0.1";"template",PT.to_json template;
    "member_order",arr [str "payload"];"members",arr [obj ["id",str "payload";
      "regions",obj ["utr5",str "utr5";"cds",str "cds";"utr3",str "utr3";"poly_a",str "poly_a"];
      "product",expected_product;"chemistry",output_chemistry "payload.frame"]]]

let component_request_literal fixture variant =
  let original,_=Requests.request_literal fixture false in
  let models=original_library fixture and leader_sequence=leader variant and join_offset=offset variant in
  let carriers=List.map (fun disposition -> obj ["target",disposition;
    "sites",arr [site "leader_A" "utr5" 0 join_offset]]) (decision_targets false) in
  let decision_raw=component "fixture.decision.exclusion.material" (decision models false)
    (root "leader_A" leader_sequence false) carriers [] decision_prerequisites in
  let driver_raw=driver_component models in
  let composition_rule=rule false decision_raw driver_raw
    |> put ["body";"join";"offset"] (Json.int join_offset)
    |> put ["body";"material_authority"] (material_authority variant) |> repin in
  let rule_identity=get "identity" composition_rule in
  let context=get "context" original
    |> put ["delivery_group";"max_total_bases"] (Json.int 18)
    |> put ["record_layout";"rule"] rule_identity |> Requests.refresh_layout_pins in
  let catalog=get "catalog_binding" original
    |> replace "components" (at ["body";"components"] composition_rule)
    |> replace "rule" rule_identity in
  original |> replace "component_library" (library [decision_raw;driver_raw])
    |> replace "composition_rule" composition_rule |> replace "catalog_binding" catalog
    |> replace "context" context

let cases fixture = [
  {id="short";rank=1;request=component_request_literal fixture Short;expected_sequence=expected_sequence Short};
  {id="long";rank=0;request=component_request_literal fixture Long;expected_sequence=expected_sequence Long}]

let selection_literal ?(max_total_nt=17) fixture =
  obj ["schema_version",str "biocompiler.policy_component_selection_request.v0.1";
    "profile",str "biocompiler.policy_component_material_selection.v0.1";
    "alternatives",arr (List.map (fun row -> obj ["id",str row.id;"rank",Json.int row.rank;"request",row.request]) (cases fixture));
    "predicate",obj ["max_total_nt",Json.int max_total_nt];
    "budgets",obj ["profile",str "biocompiler.policy_component_selection_resources.v0.1";
      "max_work",Json.int 17000000000;"max_report_bytes",Json.int 8323072;"max_report_nodes",Json.int 249968]]

(* Original declarations and literal molecular/graph oracles only. No producer,
   checker, operational lowering or candidate/source evaluator is linked here. *)
open Bioc_wire
let require condition message=if not condition then failwith message
let str value=Json.String value
let obj values=Json.Object values
let arr values=Json.Array values
let get key value=Json.field key(Json.object_fields value)
let items key value=Json.array(get key value)
let text key value=Json.string(get key value)
let replace key item value=obj(List.map(fun(name,value)->name,if name=key then item else value)(Json.object_fields value))
let add key item value=obj((key,item)::List.remove_assoc key(Json.object_fields value))
let remove key value=obj(List.remove_assoc key(Json.object_fields value))
let rec at path value=match path with []->value|key::rest->
  at rest(match value with Json.Array values->List.nth values(int_of_string key)|_->get key value)
let rec edit path transform value=match path with []->transform value|key::rest->
  match value with Json.Array values->arr(List.mapi(fun index value->if index=int_of_string key then edit rest transform value else value)values)
  |_->replace key(edit rest transform(get key value))value
let put path item=edit path(fun _->item)
let repin value=put ["identity";"content_fingerprint"](str(Canonical.fingerprint(get "body" value)))value
let pin kind id body=obj ["schema_version",str "biocompiler.component_identity.v0.1";"id",str id;
  "version",str "1";"kind",str kind;"content_fingerprint",str(Canonical.fingerprint body)]
let named id body=obj ["identity",pin "model" id body;"body",body]
let reference definition=obj ["$type",str "DefinitionRef";"id",get "id" definition;"version",get "version" definition;
  "digest",str(Bioc_domain.Policy_document.document_digest definition)]
let material_profile="biocompiler.policy_multi_member_prerequisite_mrna.v0.1"
let assembly_profile="biocompiler.policy_multi_member_component_assembly.v0.1"
let transport_definition=obj ["$type",str "SemanticDefinition";"id",str "fixture.inter_member_transport";
  "version",str "1";"category",str "interface";
  "meaning",str "Supplied complete identity transfer between two coavailable RNA members; no empirical claim.";
  "parameters",arr [];"result",Json.Null;"clauses",arr [];"assumptions",arr [];
  "executor_kind",Json.Null;"subject_kind",Json.Null]
let transport_reference=reference transport_definition
let second_symbol alternate=if alternate then "fixture.product.gamma" else "fixture.product.beta"
let peptide slot alternate=if slot="controller_a" then "MA" else if alternate then "MG" else "MP"
let sequence slot alternate=if slot="controller_a" then "CCAUGGCUUAAGGAAAA"
  else if alternate then "CCAUGGGUUAAGGAAAA" else "CCAUGCCUUAAGGAAAA"
let member_id slot=if slot="controller_a" then "payload_a" else "payload_b"
let root_id slot=if slot="controller_a" then "root_a" else "root_b"
let source_id slot=if slot="controller_a" then "source_a" else "source_b"
let slots=["controller_a";"stage_b"]
let ep node port=obj ["node",str node;"port",str port]
let nr slot node=obj ["slot",str slot;"node",str node]
let er slot node port=add "port"(str port)(nr slot node)
let wire from_node from_port to_node to_port=obj ["producer",ep from_node from_port;"consumer",ep to_node to_port]
let model_body model=get "body" model
let product_model model id symbol=
  let body=replace "configuration"(obj["product",str symbol])(model_body model) in
  model |> replace "body" body |> replace "identity"(pin "model" id body)
  |> replace "configuration_digest"(str(Canonical.fingerprint(get "configuration" body)))
let source_literal fixture alternate=
  let original=at ["request";"implementation_request"]fixture in
  let declarations=at ["document";"program";"declarations"]original |> Json.array in
  let declarations=List.concat_map(fun declaration->
    match text "$type" declaration with
    |"Parameter"->[declaration |> replace "id"(str "product_a");
      declaration |> replace "id"(str "product_b") |> replace "value"(str(second_symbol alternate))]
    |"Effect"->[declaration |> put ["parameters";"0";"value";"ref";"id"]
        (str(if text "id" declaration="stage_one" then "product_a" else "product_b"))]
    |_->[declaration])declarations in
  let library=get "implementation_library" original in
  let model=List.find(fun row->at["body";"primitive"]row=str "product_constant")(items "models" library)in
  let extra=product_model model "multi_member.primitive.product_b"(second_symbol alternate)in
  let models=items "models" library @ [extra]in
  let library=replace "models"(arr models)library in
  let entry=at ["document";"implementations";"implementations";"0"]original
    |> replace "id"(str "multi_member.staged.primitives") |> replace "dependencies"(arr [transport_reference])in
  let bridge=at ["catalog_bindings";"0"]original |> replace "entry_id"(get "id" entry)
    |> replace "entry_digest"(str(Canonical.fingerprint entry)) |> replace "models"(arr(List.map(get "identity")models))in
  original |> replace "schema_version"(str "biocompiler.policy_realization_request.v0.4")
  |> replace "profile"(str "biocompiler.policy_multi_product_prerequisite_inputs.v0.1")
  |> put ["document";"program";"declarations"](arr declarations)
  |> put ["document";"program";"source_map"](arr(List.mapi(fun index declaration->
      let id=text "id" declaration in obj["$type",str "SourceSpan";"declaration_id",str id;
        "file",str "policy_multi_member_source_literal.py";"line",Json.int(index+1);"column",Json.int 0;
        "pattern",(if String.starts_with ~prefix:"regimen/" id then str "regimen" else Json.Null)])declarations))
  |> edit ["document";"program";"semantics";"definitions"](fun rows->arr(Json.array rows @ [transport_definition]))
  |> edit ["document";"deployment";"payload"](fun payload->List.fold_left(fun payload field->replace field(Json.int 2)payload)
      payload ["member_count";"orf_count";"product_count"])
  |> put ["document";"implementations";"implementations";"0"]entry
  |> replace "catalog_bindings"(arr [bridge]) |> replace "implementation_library" library
let old_components fixture=at["request";"component_library";"components"]fixture |> Json.array
let old_fragment fixture index=at ["body";"fragment"](List.nth(old_components fixture)index)
let first_nodes=["first";"first_completed";"first_failed";"first_timed_out"]
let second_nodes=["second";"second_completed";"second_failed";"second_timed_out"]
let owned slot id=List.mem id(if slot="controller_a" then first_nodes else second_nodes)
let slot_for_node id=if List.mem id second_nodes || id="product_b" then "stage_b" else "controller_a"
let node_models fixture original slot=
  let decision=old_fragment fixture 0 and driver=old_fragment fixture 1 in
  let models=at["implementation_library";"models"]original |> Json.array in
  let product=List.find(fun model->at["identity";"id"]model=str
    (if slot="controller_a" then "staged.primitive.product" else "multi_member.primitive.product_b"))models in
  (if slot="controller_a" then items "nodes" decision else []) @
  [obj["id",str(if slot="controller_a" then "product_a" else "product_b");"model",product]] @
  List.filter(fun node->owned slot(text "id" node))(items "nodes" driver)
let local_wires fixture slot=
  if slot="stage_b" then List.filter(fun row->text "node"(get "producer" row)="second")(items "wires"(old_fragment fixture 1))
  else items "wires"(old_fragment fixture 0) @
    List.filter(fun row->text "node"(get "producer" row)="first")(items "wires"(old_fragment fixture 1)) @ [
      wire "product_a" "out" "t0_commit" "product0";wire "t0_commit" "request0" "first" "request";
      wire "evidence" "value" "first" "authorization";wire "first_completed" "selected" "t1_gate" "on";
      wire "first_failed" "selected" "t3_gate" "on";wire "first_timed_out" "selected" "t5_gate" "on"]
let fragment fixture original slot=
  let decision=old_fragment fixture 0 and driver=old_fragment fixture 1 in
  let base=if slot="controller_a" then decision else driver in
  let nodes=node_models fixture original slot in
  let exports=(if slot="controller_a" then items "semantic_exports" decision else []) @
    [ep(if slot="controller_a" then "product_a" else "product_b")"out"] @
    List.filter(fun row->owned slot(text "node" row))(items "semantic_exports" driver)in
  let boundaries=if slot="controller_a" then List.filter(fun row->String.starts_with ~prefix:"stage1."(text "id" row))(items "boundary_ports" decision)
    else List.filter(fun row->text "id" row="product" || String.starts_with ~prefix:"stage1."(text "id" row))(items "boundary_ports" driver)
      |> List.map(fun row->if text "id" row="product" then replace "endpoint"(ep "product_b" "out")row else row)in
  let inputs=(if slot="controller_a" then items "external_slots" decision else []) @
    List.filter(fun row->text "id" row=(if slot="controller_a" then "first_feedback" else "second_feedback"))(items "external_slots" driver)in
  base |> replace "id"(str("multi_member."^slot^".fragment")) |> replace "nodes"(arr nodes)
  |> replace "wires"(arr(local_wires fixture slot)) |> replace "semantic_exports"(arr exports)
  |> replace "external_slots"(arr inputs) |> replace "boundary_ports"(arr boundaries)
  |> replace "atomic_groups"(if slot="controller_a" then get "atomic_groups" decision else arr [])
let local_requirements fixture slot=
  let all=List.concat_map(fun row->at["body";"provider_requirements"]row |> Json.array)(old_components fixture)in
  let inputs=if slot="controller_a" then ["condition";"first_feedback"]else["second_feedback"]in
  let nodes=if slot="controller_a" then ["evidence";"machine";"edge";"first"]else["second"]in
  List.map(fun id->List.find(fun row->get "kind" row=str "input" && get "external_slot" row=str id)all)inputs @
  List.concat_map(fun id->List.filter(fun row->get "kind" row=str "capacity" &&
    at["owner";"kind"]row=str "external_slot" && at["owner";"id"]row=str id)all)inputs @
  List.concat_map(fun id->List.filter(fun row->get "kind" row=str "capacity" &&
    at["owner";"kind"]row=str "node" && at["owner";"id"]row=str id)all)nodes
let reframe frame raw=
  let rec walk value=match value with
  |Json.Object fields->obj(List.map(fun(key,value)->key,if key="space_id" then str frame else walk value)fields)
  |Json.Array values->arr(List.map walk values)|value->value in walk raw
let molecule_literal fixture slot alternate ~output=
  let baseline=at["expected";"molecule"]fixture in
  let id=if output then member_id slot else root_id slot in
  let frame=id^".frame" and root_frame=root_id slot^".frame" in
  let original=baseline |> reframe frame |> replace "id"(str id)
    |> replace "form"(str(if output then "delivered_rna" else "primary_rna"))
    |> put ["space";"id"](str frame) |> replace "sequence"(str(sequence slot alternate))in
  let path=at["assembly";"0";"destination"]original in
  let origin=at["assembly";"0"]original |> replace "id"(str(id^(if output then ".origin" else ".self")))
    |> replace "destination" path |> replace "source_path"(reframe root_frame path)
    |> replace "source_space"(get "space" original |> replace "id"(str root_frame))in
  replace "assembly"(arr [origin])original
let root fixture slot alternate=
  at["body";"root"](List.hd(old_components fixture)) |> replace "id"(str(root_id slot))
    |> replace "molecule"(molecule_literal fixture slot alternate ~output:false)
let product fixture slot alternate=
  let base=at["request";"composition_rule";"body";"material_authority";"members";"0";"product"]fixture in
  let sequence=peptide slot alternate in
  let content=obj["schema_version",str "biocompiler.policy_mrna_product_content.v0.1";"alphabet",str "protein";
    "sequence_extent",str "complete";"sequence",str sequence]in
  base |> replace "identity"(pin "source"(member_id slot^".artificial.product")content) |> replace "sequence"(str sequence)
let targets fragment=
  List.concat_map(fun node->List.map(fun kind->obj["kind",str kind;"id",get "id" node])
    ["primitive";"configuration";"replication"])(items "nodes" fragment) @
  List.mapi(fun index _->obj["kind",str "local_wire";"index",Json.int index])(items "wires" fragment) @
  List.map(fun row->obj["kind",str "external_slot";"id",get "id" row])(items "external_slots" fragment) @
  List.map(fun row->obj["kind",str "boundary_port";"id",get "id" row])(items "boundary_ports" fragment) @
  List.map(fun row->obj["kind",str "atomic_group";"id",get "id" row])(items "atomic_groups" fragment) @
  List.mapi(fun index _->obj["kind",str "semantic_export";"index",Json.int index])(items "semantic_exports" fragment) @ [obj["kind",str "slot_layout"]]
let component fixture original slot alternate=
  let fragment=fragment fixture original slot in
  let root=root fixture slot alternate in
  let cds=List.find(fun feature->get "id" feature=str "cds")(at["molecule";"features"]root |> Json.array)in
  let site=obj["root",str(root_id slot);"feature",str "cds";"path",get "path" cds]in
  let body=obj["fragment",fragment;"root",root;
    "carriers",arr(List.map(fun target->obj["target",target;"sites",arr[site]])(targets fragment));
    "products",arr[obj["node",str(if slot="controller_a" then "product_a"else "product_b");
      "symbol",str(if slot="controller_a" then "fixture.product.alpha"else second_symbol alternate);
      "root",str(root_id slot);"cds_feature",str "cds";"expected",product fixture slot alternate]];
    "provider_requirements",arr(local_requirements fixture slot)]in
  named("multi_member."^slot^".material")body |> add "schema_version"(str "biocompiler.policy_component_material.v0.1")
    |> add "profile"(str "biocompiler.policy_exact_local_material.v0.1")

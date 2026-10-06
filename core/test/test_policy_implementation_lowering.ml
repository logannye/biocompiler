open Bioc_wire
let () = Printexc.register_printer (function
  | Diagnostic.Error diagnostic -> Some (Printf.sprintf "Diagnostic.Error(code=%s, path=%s, message=%s)"
      diagnostic.code (Option.value ~default:"<none>" diagnostic.path) diagnostic.message)
  | _ -> None)
module O = Bioc_domain.Policy_operational
module R = Bioc_domain.Policy_realization_request
module I = Bioc_domain.Policy_implementation
module B = Bioc_domain.Policy_implementation_binding
module A = Bioc_checker.Policy_realization_admission
module S = Bioc_checker.Policy_admission
module C = Bioc_checker.Policy_implementation_binding_check
module L = Bioc_compiler.Policy_lowering
module G = Bioc_compiler.Policy_implementation_lowering
let require condition message=if not condition then failwith message
let get=O.get
let text=O.text
let items=O.list
let str value=Json.String value
let obj value=Json.Object value
let arr value=Json.Array value
let rec at path value=match path,value with
  |[],_->value|key::rest,Json.Object _->at rest(get key value)
  |index::rest,Json.Array values->at rest(List.nth values(int_of_string index))
  |_->failwith "Test fixture path is absent"
let rec set path replacement value=match path,value with
  |[],_->replacement
  |key::rest,Json.Object fields->require(List.mem_assoc key fields)("Unknown mutation field "^key);
      obj(List.map(fun(name,value)->name,if name=key then set rest replacement value else value)fields)
  |index::rest,Json.Array values->arr(List.mapi(fun i value->if i=int_of_string index then set rest replacement value else value)values)
  |_->failwith "Mutation left literal fixture"
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:(2*1024*1024) ~max_nodes:100000(really_input_string channel(in_channel_length channel)))
let controls=ref 0
let rejects label code f=incr controls;match f()with
  |_->failwith("Producer negative control accepted: "^label)
  |exception Diagnostic.Error diagnostic->require(diagnostic.code=code)(label^": wrong diagnostic "^diagnostic.code)
let admission raw=let request=R.of_json raw in
  let behavior=L.lower(S.admit ~document:(R.document request) ~descriptors:(R.definitions request))in
  A.admit ~request ~behavior
let produce admitted=G.lower ~admitted ~library:(R.implementation_library(A.request admitted))
let source_path raw id=
  let rec index i=function
    |row::_ when text "id" row=id->["document";"program";"declarations";string_of_int i]
    |_::rest->index(i+1)rest|[]->failwith("Source declaration absent "^id)in
  index 0(Json.array(at["document";"program";"declarations"]raw))
let drop_model raw id=
  let keep model=text "id"(get "identity" model)<>id in
  let raw=set["implementation_library";"models"](arr(List.filter keep(Json.array(at["implementation_library";"models"]raw))))raw in
  set["catalog_bindings";"0";"models"](arr(List.filter(fun pin->text "id" pin<>id)(Json.array(at["catalog_bindings";"0";"models"]raw))))raw
let library_with_extra raw model=
  let raw=set["implementation_library";"models"](arr(Json.array(at["implementation_library";"models"]raw)@[model]))raw in
  set["catalog_bindings";"0";"models"](arr(Json.array(at["catalog_bindings";"0";"models"]raw)@[get "identity" model]))raw
let altered_model model id key value=
  let model=set["body";"configuration";key]value model in
  let identity=set["content_fingerprint"](str(Canonical.fingerprint(get "body" model)))
    (set["id"](str id)(get "identity" model))in
  set["identity"]identity(set["configuration_digest"]
    (str(Canonical.fingerprint(get "configuration"(get "body" model))))model)
let check_scope checked=
  List.iter(fun(key,value)->require(text key(C.report checked)=value)("Producer/checker promoted "^key))
    ["status","source_graph_bound";"execution","not_performed";"preservation","unassessed";
     "requirements","unassessed";"material","unassessed";"artifact","withheld";"export","withheld"]
let fresh_checked raw=
  let admitted=admission raw in let proposal=produce admitted in
  let checked=C.check ~admitted ~implementation:proposal.implementation ~proposed:proposal.binding in
  check_scope checked;admitted,proposal,checked
let normalized_graph graph=Json.Object(List.filter(fun(key,_)->key<>"authority")(Json.object_fields(I.to_json graph)))
let ()=
  require(Array.length Sys.argv=2)"Supply independent one-rule/exclusion source and graph fixture";
  let fixture=read Sys.argv.(1)in let cases=items "cases" fixture in
  require(List.length cases=2)"Missing independent source family";
  List.iter(fun case->
    let raw=get "request" case and expected=get "expected" case in
    let admitted,proposal,checked=fresh_checked raw in
    let repeated=produce admitted in
    require(Json.equal(I.to_json proposal.implementation)(I.to_json repeated.implementation) &&
      Json.equal(B.to_json proposal.binding)(B.to_json repeated.binding))"Producer is nondeterministic under exact supplied authority";
    require(List.length(I.nodes proposal.implementation)=List.length(items "nodes"(get "implementation" case)))
      "Produced primitive inventory differs from separately authored literal family";
    require(List.map(fun(occurrence:I.occurrence)->occurrence.source_path)(I.occurrences proposal.implementation)=
      List.map(fun value->text "source_path" value)(items "occurrences"(get "implementation" case)))
      "Producer lost or added original source occurrences";
    require(List.length(I.occurrences proposal.implementation)=Z.to_int(Json.integer(get "occurrence_count" expected)))
      "Produced complete source ledger differs from literal independent count";
    require(List.map(fun(value:O.requirement)->str value.requirement_id)(A.behavior admitted).requirements=items "requirements" expected)
      "Producer omitted an original hard requirement";
    require(text "request_fingerprint"(C.report checked)=R.fingerprint(A.request admitted))"Source binding receipt omitted original full authority";
    List.iter(fun(node:I.node)->A.require_model admitted ~entry_id:(B.catalog_entry proposal.binding)node.model.identity)(I.nodes proposal.implementation);
    let reordered=set["implementation_library";"models"](arr(List.rev(Json.array(at["implementation_library";"models"]raw))))raw in
    let _,reordered_proposal,_=fresh_checked reordered in
    require(Json.equal(normalized_graph proposal.implementation)(normalized_graph reordered_proposal.implementation) &&
      Json.equal(B.to_json proposal.binding)(B.to_json reordered_proposal.binding))
      "Library listing order changed selected semantics or graph allocation";
    require((I.authority proposal.implementation).library_digest<>(I.authority reordered_proposal.implementation).library_digest)
      "Reordered external library retained obsolete complete artifact authority")cases;
  let raw=get "request"(List.hd cases)in
  let admitted,proposal,checked=fresh_checked raw in
  List.iter(fun model->
    let id=text "id"(get "identity" model)in
    let incomplete=admission(drop_model raw id)in
    rejects("missing authorized primitive "^id)"policy_implementation_lowering_missing_model"(fun()->produce incomplete))
    (Json.array(at["implementation_library";"models"]raw));
  let stale_library=I.library_of_json(set["id"](str "foreign.library")(get "implementation_library" raw))in
  rejects "external library cannot override admitted root" "policy_implementation_lowering_authority"
    (fun()->G.lower ~admitted ~library:stale_library);
  let no_catalog=set["document";"implementations";"implementations"](arr[])raw in
  rejects "empty original catalog cannot reach implementation production" "policy_realization_catalog"(fun()->admission no_catalog);
  let observed=at(source_path raw "respond"@["when"])raw in
  List.iter(fun(label,changed)->let admitted=admission changed in
    rejects label "policy_implementation_lowering_unsupported"(fun()->produce admitted))[
      "predicate resets",set(source_path raw "seen"@["reset"])observed raw;
      "sampled observation profile",set(source_path raw "condition"@["coverage"])(str "sampled")raw;
      "identical-only write conflicts",set(source_path raw "respond"@["arbitration";"write_conflict"])(str "identical_only")raw];
  let second=get "request"(List.nth cases 1)in
  let duplicated=set(source_path second "exclude"@["effects"])(at(source_path second "select"@["effects"])second)second in
  let duplicate_admitted=admission duplicated in
  rejects "two initiating gates require another bank contract" "policy_implementation_lowering_unsupported"(fun()->produce duplicate_admitted);
  let negative=at(source_path raw "scoped_memory"@["condition";"args";"0"])raw in
  let monitor=set["args"](arr[negative])(at(source_path raw "respond"@["on"])raw)in
  let monitor_admitted=admission(set(source_path raw "initiation_progress"@["trigger"])monitor raw)in
  rejects "monitor-only rising memory cannot disappear" "policy_implementation_lowering_unsupported"(fun()->produce monitor_admitted);
  let changed_product=set(source_path raw "product"@["value"])(str "fixture.product.beta")raw in
  let unavailable=admission changed_product in
  rejects "source edit has no supplied alternate product model" "policy_implementation_lowering_missing_model"(fun()->produce unavailable);
  let product_model=List.find(fun model->text "primitive"(get "body" model)="product_constant")
    (Json.array(at["implementation_library";"models"]raw))in
  let beta_model=altered_model product_model "fixture.primitive.beta" "product"(str "fixture.product.beta")in
  let resolved_beta=library_with_extra changed_product beta_model in
  let _,beta_proposal,beta_checked=fresh_checked resolved_beta in
  require(List.exists(fun(node:I.node)->node.model.primitive=I.Product_constant "fixture.product.beta")(I.nodes beta_proposal.implementation))
    "Producer ignored independently supplied alternate product model";
  require(I.fingerprint proposal.implementation<>I.fingerprint beta_proposal.implementation &&
    text "request_fingerprint"(C.report checked)<>text "request_fingerprint"(C.report beta_checked))
    "Source edit retained obsolete request/implementation identity";
  let original_with_unused=library_with_extra raw beta_model in
  let _,unused_proposal,_=fresh_checked original_with_unused in
  require(not(List.exists(fun(node:I.node)->node.model.primitive=I.Product_constant "fixture.product.beta")(I.nodes unused_proposal.implementation)))
    "An authorized but semantically wrong alternate product was selected";
  let true_expression=at(source_path raw "respond"@["assignments";"0";"value"])raw in
  let changed_guard=set(source_path raw "respond"@["when"])true_expression raw in
  let _,guard_proposal,_=fresh_checked changed_guard in
  require(not(Json.equal(get "wires"(I.to_json proposal.implementation))(get "wires"(I.to_json guard_proposal.implementation))))
    "Changing original authorization did not change actual implementation wiring";
  let metadata=set["document";"program";"source_map";"0";"file"](str "independent_new_location.py")raw in
  let _,metadata_proposal,metadata_checked=fresh_checked metadata in
  require(Json.equal(normalized_graph proposal.implementation)(normalized_graph metadata_proposal.implementation))
    "Metadata-only source edit altered runtime graph semantics";
  require((I.authority proposal.implementation).source_artifact_digest<>(I.authority metadata_proposal.implementation).source_artifact_digest &&
    text "request_fingerprint"(C.report checked)<>text "request_fingerprint"(C.report metadata_checked))
    "Metadata-only source edit escaped original authority invalidation";
  (* Producer output is still untrusted. This altered graph is structurally
     decoded first; external source binding must reject the semantic change. *)
  let graph=I.to_json proposal.implementation in
  let gate=(List.hd(B.rules proposal.binding)).gate in
  let true_node=List.find(fun(node:I.node)->node.model.primitive=I.Truth_constant I.True)(I.nodes proposal.implementation)in
  let mutated_wires=List.map(fun wire->let consumer=get "consumer" wire in
    if text "node" consumer=gate && text "port" consumer="guard"then
      set["producer"](obj["node",str true_node.node_id;"port",str "out"])wire else wire)(items "wires" graph)in
  let mutated=I.of_json ~library:(R.implementation_library(A.request admitted))(set["wires"](arr mutated_wires)graph)in
  rejects "external checker rejects altered produced authorization" "policy_implementation_source_binding"
    (fun()->C.check ~admitted ~implementation:mutated ~proposed:proposal.binding);
  Printf.printf "Untrusted policy implementation producer: two externally checked literal families and %d rejection controls; no execution/requirement/material/export claim.\n" !controls

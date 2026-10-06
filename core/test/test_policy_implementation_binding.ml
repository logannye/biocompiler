open Bioc_wire
let () = Printexc.register_printer (function
  | Diagnostic.Error diagnostic -> Some (Printf.sprintf "Diagnostic.Error(code=%s, path=%s, message=%s)"
      diagnostic.code (Option.value ~default:"<none>" diagnostic.path) diagnostic.message)
  | _ -> None)
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module R = Bioc_domain.Policy_realization_request
module I = Bioc_domain.Policy_implementation
module B = Bioc_domain.Policy_implementation_binding
module A = Bioc_checker.Policy_realization_admission
module C = Bioc_checker.Policy_implementation_binding_check
module L = Bioc_compiler.Policy_lowering
module S = Bioc_checker.Policy_admission
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
  |_->failwith "Literal fixture path is absent"
let rec set path replacement value=match path,value with
  |[],_->replacement
  |key::rest,Json.Object fields->require(List.mem_assoc key fields)("Missing mutation field "^key);
      obj(List.map(fun(name,value)->name,if name=key then set rest replacement value else value)fields)
  |index::rest,Json.Array values->arr(List.mapi(fun i value->if i=int_of_string index then set rest replacement value else value)values)
  |_->failwith "Mutation path is outside fixture"
let append path value raw=set path(arr(Json.array(at path raw)@[value]))raw
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:(2*1024*1024) ~max_nodes:100000(really_input_string channel(in_channel_length channel)))
let controls=ref 0
let rejects label codes action=incr controls;match action()with
  |_->failwith("Rejected-control unexpectedly bound: "^label)
  |exception Diagnostic.Error d->require(List.mem d.code codes)(label^": unexpected diagnostic "^d.code)
let admitted raw=let request=R.of_json raw in
  let behavior=L.lower(S.admit ~document:(R.document request) ~descriptors:(R.definitions request))in
  A.admit ~request ~behavior
let inputs case=
  let a=admitted(get "request" case)in
  let graph=I.of_json ~library:(R.implementation_library(A.request a))(get "implementation" case)
  and proposed=B.of_json(get "proposed" case)in a,graph,proposed
let check case=let a,graph,proposed=inputs case in C.check ~admitted:a ~implementation:graph ~proposed
(* Decoding/admission occur OUTSIDE the rejection assertion. These controls
   must remain valid graphs before the independent source checker rejects. *)
let reject_binding ?(code="policy_implementation_source_binding") label case=
  let a,graph,proposed=inputs case in
  rejects label [code](fun()->C.check ~admitted:a ~implementation:graph ~proposed)
let repin_authority case=
  let request=R.of_json(get "request" case)in
  let authority=obj[
    "source_artifact_digest",str(D.artifact_digest(R.document request));
    "descriptors_digest",str(O.descriptors_digest(R.definitions request));
    "domain_digest",str(Bioc_domain.Policy_operating_domain.digest(R.operating_domain request));
    "implementation_catalog_digest",str(Canonical.fingerprint(get "implementations"(D.to_json(R.document request))));
    "library_digest",str(I.library_digest(R.implementation_library request))]in
  set["implementation";"authority"]authority case
let declaration_path case identity=
  let rec find index=function
    |value::_ when text "id" value=identity->["request";"document";"program";"declarations";string_of_int index]
    |_::rest->find(index+1)rest|[]->failwith("No source declaration "^identity)in
  find 0 (Json.array(at["request";"document";"program";"declarations"]case))
let source_edit case identity path replacement=
  repin_authority(set(declaration_path case identity@path)replacement case)
let endpoint node port=obj["node",str node;"port",str port]
let map_wires f case=set["implementation";"wires"]
  (arr(List.map f(Json.array(at["implementation";"wires"]case))))case
let redirect consumer producer case=map_wires(fun wire->
  if Json.equal(get "consumer" wire)consumer then set["producer"]producer wire else wire)case
let model_edit case node_id path replacement=
  let graph=get "implementation" case in
  let selected=List.find(fun n->text "id" n=node_id)(items "nodes" graph)in
  let model_id=text "id"(get "model" selected)in
  let models=Json.array(at["request";"implementation_library";"models"]case)in
  let old=List.find(fun m->text "id"(get "identity" m)=model_id)models in
  let changed=set("body"::path)replacement old in
  let pin=set["content_fingerprint"](str(Canonical.fingerprint(get "body" changed)))(get "identity" changed)in
  let config=str(Canonical.fingerprint(get "configuration"(get "body" changed)))in
  let changed=set["configuration_digest"]config(set["identity"]pin changed)in
  let case=set["request";"implementation_library";"models"]
    (arr(List.map(fun m->if text "id"(get "identity" m)=model_id then changed else m)models))case in
  let case=set["request";"catalog_bindings";"0";"models"]
    (arr(List.map(fun p->if text "id" p=model_id then pin else p)
      (Json.array(at["request";"catalog_bindings";"0";"models"]case))))case in
  let case=set["implementation";"nodes"](arr(List.map(fun n->
    if text "id"(get "model" n)=model_id then set["configuration_digest"]config(set["model"]pin n)else n)(items "nodes" graph)))case in
  repin_authority case
let check_scope bound=
  let report=C.report bound in require(text "status" report="source_graph_bound")"Static correspondence was upgraded to acceptance";
  List.iter(fun(k,v)->require(text k report=v)("Binding upgraded "^k))
    ["execution","not_performed";"preservation","unassessed";"requirements","unassessed";
     "material","unassessed";"target_status","unassessed";"artifact","withheld";"export","withheld"]
let positive case=
  let bound=check case and expected=get "expected" case in check_scope bound;
  let report=C.report bound and request=A.request(C.admitted_inputs bound)in
  require(text "request_fingerprint" report=text "request_fingerprint" expected &&
    text "request_fingerprint" report=R.fingerprint request)"Full original request identity is absent";
  require(text "implementation_fingerprint" report=text "implementation_fingerprint" expected &&
    I.fingerprint(C.implementation bound)=text "implementation_fingerprint" expected)"Graph was changed while binding";
  require(text "catalog_bindings_digest" report=R.catalog_bindings_digest request)"Catalog bridge identity is absent";
  require(List.length(I.occurrences(C.implementation bound))=Z.to_int(Json.integer(get "occurrence_count" expected)))
    "Independent complete occurrence count differs from literal fixture";
  require(List.map(fun(r:O.requirement)->str r.requirement_id)(A.behavior(C.admitted_inputs bound)).requirements=
    items "requirements" expected)"Binding dropped an original hard requirement";
  let env=C.environment bound in
  require(env.executor="cell-1" && List.map(fun(s:C.slot)->s.identity,s.target,s.start_tick)env.slots=
    ["e1","target-1",0;"e2","target-2",0])"Checked runtime environment lost recipient or slot order";
  require(List.map(fun(o:C.observation)->o.source,o.bank,o.input)(C.observations bound)=
    ["condition","evidence","condition"])"Checked observation map differs from literal";
  require(List.map(fun(e:C.effect_binding)->e.source,e.bank,e.feedback,e.product_parameter)(C.effects bound)=
    ["response","attempt","feedback","product"])"Checked effect/feedback/product map differs from literal";
  List.iter(fun(r:C.rule)->require(r.source_trigger.op="rising" && r.trigger.port_id="events")
    "Checked rule omitted actual event endpoint or original trigger")(C.rules bound);
  bound
let ()=
  require(Array.length Sys.argv=4)"Supply binding fixture, original resolved request, and unchanged exclusion source fixture";
  let fixture=read Sys.argv.(1)and original_request=read Sys.argv.(2)and exclusion_source=read Sys.argv.(3)in
  let cases=items "cases" fixture in require(List.length cases=2)"Lost independent source family";
  let first=List.nth cases 0 and second=List.nth cases 1 in
  require(Json.equal(get "request" first)original_request)"Binding fixture changed original unresolved safety source";
  List.iter(fun path->require(Json.equal(at("request"::"document"::path)second)(at("document"::path)exclusion_source))
    "Resolved sibling weakened original declarations/deployment/assurance")
    [["program";"declarations"];["deployment"];["assurance"]];
  require(items "implementations"(get "implementations"(get "document" exclusion_source))=[])
    "Binding fixture silently rewrote original empty catalog";
  let first_bound=positive first and second_bound=positive second in
  List.iter(fun(case,bound)->
    let original_request=A.request(C.admitted_inputs bound) in
    let original_behavior=O.behavior_to_json(A.behavior(C.admitted_inputs bound))in
    let signature_definitions=Json.array(at["request";"document";"program";"semantics";"definitions"]case)in
    let operation=at(declaration_path case "response"@["contract"])case in
    let operation_id=text "id" operation in
    let definition_index=List.find_index(fun definition->text "id" definition=operation_id)signature_definitions |> Option.get in
    let formal_path=["request";"document";"program";"semantics";"definitions";string_of_int definition_index;"parameters";"0"]in
    require(text "selection"(at formal_path case)="fixed" &&
      List.for_all(fun key->get key(at formal_path case)=Json.Null)["value";"lower";"upper"])
      "Ordinary accepted effect signature acquired a refinement";
    List.iter(fun(label,field,replacement)->
      let edited=set(formal_path@[field])replacement case in
      let changed_definition=at["request";"document";"program";"semantics";"definitions";string_of_int definition_index]edited in
      let digest=D.document_digest changed_definition in
      let rec repin value=match value with
        |Json.Object fields->let value=obj(List.map(fun(key,value)->key,repin value)fields)in
            if List.assoc_opt "$type" fields=Some(str "DefinitionRef") && List.assoc_opt "id" fields=Some(str operation_id)
            then set["digest"](str digest)value else value
        |Json.Array values->arr(List.map repin values)
        |value->value in
      let edited=repin edited in
      let entries=Json.array(at["request";"document";"implementations";"implementations"]edited)in
      let bridges=Json.array(at["request";"catalog_bindings"]edited)|>List.map(fun bridge->
        let entry=List.find(fun entry->text "id" entry=text "entry_id" bridge)entries in
        set["entry_digest"](str(Canonical.fingerprint entry))bridge)in
      let edited=repin_authority(set["request";"catalog_bindings"](arr bridges)edited)in
      let request=R.of_json(get "request" edited)in
      let document=R.document request and descriptors=R.definitions request in
      let assessment=Bioc_checker.Policy_check.check document in
      require(text "status" assessment="valid")("Full request formal control lost generic source validity: "^label);
      require(R.fingerprint request<>R.fingerprint original_request &&
        D.artifact_digest document<>D.artifact_digest(R.document original_request) &&
        O.descriptors_digest descriptors<>O.descriptors_digest(R.definitions original_request))
        "Effect formal mutation retained stale original authority";
      List.iter(fun(bridge:R.catalog_binding)->
        let entry=List.find(fun entry->text "id" entry=bridge.entry_id)entries in
        require(bridge.entry_digest=Canonical.fingerprint entry && Json.equal bridge.operation(get "operation" entry))
          "Effect formal mutation retained stale catalog membership") (R.catalog_bindings request);
      let nodes=List.map2(fun node(declaration:D.declaration)->
        set["data"](obj(List.remove_assoc "$type"(Json.object_fields declaration.value)))node)
        (items "nodes" original_behavior)(D.declarations document)in
      let behavior=original_behavior |>set["source_document"](D.to_json document)
        |>set["source_artifact_digest"](str(D.artifact_digest document))
        |>set["descriptor_bundle"](O.descriptors_to_json descriptors)
        |>set["descriptors_digest"](str(O.descriptors_digest descriptors))
        |>set["nodes"](arr nodes)|>set["source_ledger"](get "declarations" assessment)
        |>set["requirements_ledger"](get "requirements" assessment)
        |>set["assumptions"](get "assumptions" assessment)
        |>set["unresolved_obligations"](get "unresolved_obligations" assessment)
        |>O.behavior_of_json in
      (* Decode the unchanged concrete graph and proposed source mapping outside
         rejection. Only the original effect signature makes this unsupported. *)
      let graph=I.of_json ~library:(R.implementation_library request)(get "implementation" edited)
      and proposed=B.of_json(get "proposed" edited)in
      require((I.authority graph).source_artifact_digest=D.artifact_digest document &&
        (I.authority graph).descriptors_digest=O.descriptors_digest descriptors &&
        (I.authority graph).implementation_catalog_digest=Canonical.fingerprint(get "implementations"(D.to_json document)))
        "Full request formal control retained stale candidate authority";
      incr controls;
      match A.admit ~request ~behavior with
      |admitted->ignore(C.check ~admitted ~implementation:graph ~proposed);
          failwith("Full request accepted unsupported effect formal: "^label)
      |exception Diagnostic.Error diagnostic->
          require(diagnostic.code="policy_operational_unsupported" &&
            diagnostic.path=Some("/document/program/semantics/definitions/"^string_of_int definition_index^"/parameters/0/"^field))
            ("Full request formal failed outside its exact admission guard: "^label))
      ["full request formal design selection","selection",str "design";
       "full request formal measured selection","selection",str "measured";
       "full request formal uncertain selection","selection",str "uncertain";
       "full request formal supplied value","value",str "fixture.product.different"])
    [first,first_bound;second,second_bound];
  let negative_controls=items "negative_controls" fixture in
  require(List.length negative_controls=1)"Original chassis mismatch rejection authority was lost";
  List.iter(fun control->
    require(text "name" control="original_exclusion_catalog_chassis_mismatch")"Unexpected original mismatch witness";
    rejects "original catalog/chassis mismatch" [text "expected_diagnostic" control]
      (fun()->check(get "case" control)))negative_controls;
  require(List.exists(fun(r:O.requirement)->r.requirement_id="scoped_memory")
    (A.behavior(C.admitted_inputs first_bound)).requirements)"Unknown hard safety was discarded";
  let renamed=set(declaration_path first "product"@["id"])(str "cargo")first in
  let renamed=set(declaration_path first "response"@["parameters";"0";"value";"ref";"id"])(str "cargo")renamed in
  let renamed=set["request";"document";"program";"source_map";"6";"declaration_id"](str "cargo")renamed in
  let renamed_bound=check(repin_authority renamed)in
  require((List.hd(C.effects renamed_bound)).product_parameter="product")
    "Renaming a source Parameter changed the effect Argument.name projected to runtime";
  check_scope renamed_bound;

  reject_binding "known-true shortcut guard is not observed authorization"
    (redirect(endpoint "gate" "guard")(endpoint "true" "out")first);
  reject_binding "authorization channel must be the exact initiating guard"
    (redirect(endpoint "attempt" "authorization")(endpoint "true" "out")first);
  reject_binding "assignment source expression cannot be replaced by observed truth"
    (redirect(endpoint "commit" "value0")(endpoint "evidence" "value")first);
  reject_binding "negative branch cannot observe the positive trigger"
    (redirect(endpoint "exclude_gate" "on")(endpoint "select_edge" "events")second);
  let swapped=map_wires(fun wire->let target=get "consumer" wire in
    if List.mem(text "node" target)["selected";"excluded"]then
      set["consumer";"node"](str(if text "node" target="selected"then "excluded"else "selected"))wire else wire)second in
  reject_binding "well-typed opposite state destinations" swapped;
  let gate_nodes=items "nodes"(get "implementation" second)in
  let reordered=List.map(fun n->if text "id" n="select_gate"then List.find(fun n->text "id" n="exclude_gate")gate_nodes
    else if text "id" n="exclude_gate"then List.find(fun n->text "id" n="select_gate")gate_nodes else n)gate_nodes in
  let exports_for nodes=List.concat_map(fun n->List.filter(fun e->text "node" e=text "id" n)
    (items "semantic_exports"(get "implementation" second)))nodes in
  reject_binding "actual gate node order is source order"
    (set["implementation";"semantic_exports"](arr(exports_for reordered))(set["implementation";"nodes"](arr reordered)second));
  let reordered_edges=List.map(fun n->if text "id" n="select_edge"then List.find(fun n->text "id" n="exclude_edge")gate_nodes
    else if text "id" n="exclude_edge"then List.find(fun n->text "id" n="select_edge")gate_nodes else n)gate_nodes in
  reject_binding "actual rising node order is source event order"
    (set["implementation";"semantic_exports"](arr(exports_for reordered_edges))(set["implementation";"nodes"](arr reordered_edges)second));
  List.iter(fun(label,node,path,replacement)->reject_binding label(model_edit first node path replacement))[
    "freshly authorized wrong product","product",["configuration";"product"],str "fixture.product.beta";
    "freshly authorized stale evidence window","evidence",["configuration";"freshness_ticks"],Json.int 3;
    "freshly authorized wrong deadline","attempt",["configuration";"timeout_ticks"],Json.int 3;
    "freshly authorized wrong uncertainty response","attempt",["configuration";"on_unknown"],str "continue";
    "freshly authorized wrong authorization duration","attempt",["configuration";"authorization"],str "initiation";
    "freshly authorized insufficient capacity","attempt",["configuration";"capacity"],Json.int 1;
    "freshly authorized wrong initial memory","seen",["configuration";"initial"],str "true";
    "freshly authorized wrong assignment constant","true",["configuration";"value"],str "false"];
  let true_source=at(declaration_path first "respond"@["assignments";"0";"value"])first in
  reject_binding "fresh source guard edit invalidates old graph"(source_edit first "respond"["when"]true_source);
  reject_binding "fresh source product edit invalidates old graph"(source_edit first "product"["value"](str "fixture.product.beta"));
  reject_binding "fresh source initial value invalidates old graph"(source_edit first "seen"["initial"](Json.Bool true));
  reject_binding "fresh source timeout invalidates old graph"
    (source_edit first "response"["lifecycle";"timeout";"amount"](str "3"));
  reject_binding "fresh source freshness invalidates old graph"
    (source_edit first "condition"["freshness";"amount"](str "3"));
  reject_binding "fresh source uncertainty response invalidates old graph"
    (source_edit first "response"["lifecycle";"on_unknown"](str "continue"));
  let observed=at(declaration_path first "respond"@["when"])first in
  reject_binding "predicate-reset state has no primitive interpretation in this family"
    (source_edit first "seen"["reset"]observed);
  reject_binding "identical-only writes need a separately implemented arbitration profile"
    (source_edit first "respond"["arbitration";"write_conflict"](str "identical_only"));
  reject_binding "sampled coverage cannot acquire an event-only graph binding"
    (source_edit first "condition"["coverage"](str "sampled"));
  let response_reference=at(declaration_path second "select"@["effects"])second in
  reject_binding "multiple gates cannot initiate one attempt bank"
    (source_edit second "exclude"["effects"]response_reference);
  let select_on=at(declaration_path second "select"@["on"])second in
  reject_binding "identical source edges cannot allocate distinct memories"(source_edit second "exclude"["on"]select_on);
  let negative=at(declaration_path first "scoped_memory"@["condition";"args";"0"])first in
  let monitor_only=set["args"](arr[negative])(at(declaration_path first "respond"@["on"])first)in
  reject_binding "requirement-only rising events cannot disappear from candidate trace"
    (source_edit first "initiation_progress"["trigger"]monitor_only);
  reject_binding "wrong external feedback input"
    (set["proposed";"effects";"0";"feedback"](str "condition")first);
  reject_binding "wrong source effect identity"
    (set["proposed";"effects";"0";"source"](str "foreign")first);
  reject_binding "state anchors cannot omit original memory"
    (set["proposed";"states"](arr[])first);
  reject_binding "rule anchors cannot omit behavior"
    (set["proposed";"rules"](arr[])first);
  rejects "collapsed state anchors" ["policy_implementation_binding"](fun()->
    B.of_json(get "proposed"(set["proposed";"states";"1";"register"](str "selected")second)));
  rejects "duplicate rule anchors" ["policy_implementation_binding"](fun()->
    B.of_json(get "proposed"(set["proposed";"rules";"1";"source"](str "select")second)));
  let original_occurrences=items "occurrences"(get "implementation" first)in
  let forged=List.map(fun o->if text "source_path" o="/document/program/declarations/6"then
    set["targets"](arr[endpoint "true" "out"])o else o)original_occurrences in
  reject_binding "constant source-path label cannot license wrong target"
    (set["implementation";"occurrences"](arr forged)first);
  reject_binding ~code:"policy_implementation_contract" "missing retained hard requirement occurrence"
    (set["implementation";"occurrences"](arr(List.filter(fun o->text "source_path" o<>"/document/program/declarations/12")original_occurrences))first);
  reject_binding ~code:"policy_implementation_contract" "forged source-path inventory"
    (set["implementation";"occurrences";"0";"source_path"](str "/unrelated/source")first);
  let extra_node=set["id"](str "orphan")(List.find(fun n->text "id" n="true")(items "nodes"(get "implementation" first)))in
  let orphan=append["implementation";"nodes"]extra_node first in
  let orphan=append["implementation";"semantic_exports"](endpoint "orphan" "out")orphan in
  let orphan=append["implementation";"occurrences"]
    (obj["source_path",str "/orphan";"role",str "declaration";"disposition",str "constant";"targets",arr[endpoint "orphan" "out"]])orphan in
  reject_binding "fully typed and exported orphan behavior" orphan;
  let metadata=set["request";"document";"program";"source_map";"0";"file"](str "independent_location.py")first in
  let metadata_request=R.of_json(get "request" metadata)in
  require(D.fingerprint(R.document metadata_request)=D.fingerprint(R.document(A.request(C.admitted_inputs first_bound))))
    "Metadata-only edit changed semantic source identity";
  reject_binding ~code:"policy_implementation_contract" "metadata-only source edit invalidates old graph artifact" metadata;
  let rebound=check(repin_authority metadata)in check_scope rebound;
  require(text "request_fingerprint"(C.report rebound)<>text "request_fingerprint"(C.report first_bound))
    "Fresh metadata authority reused an old full root receipt";
  let budget_changed=set["request";"budgets";"max_work"](Json.int 9999999)first in
  let budget_bound=check budget_changed in check_scope budget_bound;
  require(text "request_fingerprint"(C.report budget_bound)<>text "request_fingerprint"(C.report first_bound))
    "Full request budget was excluded from static binding receipt";
  let bridge_models=List.rev(Json.array(at["request";"catalog_bindings";"0";"models"]first))in
  let bridge_changed=set["request";"catalog_bindings";"0";"models"](arr bridge_models)first in
  let bridge_bound=check bridge_changed in
  require(text "catalog_bindings_digest"(C.report bridge_bound)<>text "catalog_bindings_digest"(C.report first_bound) &&
    text "request_fingerprint"(C.report bridge_bound)<>text "request_fingerprint"(C.report first_bound))
    "Equivalent membership with a distinct full bridge reused an old receipt";
  Printf.printf "Policy source/graph binding: 2 literal families, %d rejection controls; requirements/preservation/material/export unassessed.\n" !controls

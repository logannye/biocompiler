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
let rec map_json transform value=
  let value=match value with
    |Json.Object fields->obj(List.map(fun(key,value)->key,map_json transform value)fields)
    |Json.Array values->arr(List.map(map_json transform)values)
    |value->value in
  transform value
let repin_source_definitions case=
  let definitions=Json.array(at["request";"document";"program";"semantics";"definitions"]case)in
  let digests=List.map(fun definition->text "id" definition,D.document_digest definition)definitions in
  let case=map_json(function
    |Json.Object fields as value when List.assoc_opt "$type" fields=Some(str "DefinitionRef")->
        set["digest"](str(List.assoc(text "id" value)digests))value
    |value->value)case in
  let entries=Json.array(at["request";"document";"implementations";"implementations"]case)in
  let bridges=Json.array(at["request";"catalog_bindings"]case)|>List.map(fun bridge->
    let entry=List.find(fun entry->text "id" entry=text "entry_id" bridge)entries in
    set["entry_digest"](str(Canonical.fingerprint entry))bridge)in
  repin_authority(set["request";"catalog_bindings"](arr bridges)case)
let rejects_exact label code path message action=
  incr controls;
  match action()with
  |_->failwith("Exact source control unexpectedly accepted: "^label)
  |exception Diagnostic.Error diagnostic->
      require(diagnostic.code=code && diagnostic.path=path && diagnostic.message=message)
        (label^": rejected outside the intended boundary: "^diagnostic.code^" at "^
          Option.value ~default:"<none>" diagnostic.path^": "^diagnostic.message)
let valid_source_case label case=
  let request=R.of_json(get "request" case)in
  let assessment=Bioc_checker.Policy_check.check(R.document request)in
  require(text "status" assessment="valid")
    (label^": generic source is invalid: "^Canonical.encode assessment);
  (* An old candidate identity or an invalid graph must not satisfy these
     source restrictions. Only source fields change; concrete models stay put. *)
  require(Json.equal(at["implementation";"authority"]case)
    (at["implementation";"authority"](repin_authority case)))
    (label^": candidate authority was not completely refreshed");
  ignore(I.of_json ~library:(R.implementation_library request)(get "implementation" case));
  ignore(B.of_json(get "proposed" case));
  request
let reject_source_binding label ?(path=None) message case=
  ignore(valid_source_case label case);
  let admitted,implementation,proposed=inputs case in
  rejects_exact label "policy_implementation_source_binding" path message
    (fun()->C.check ~admitted ~implementation ~proposed)
let reject_source_operational label path message case=
  let request=valid_source_case label case in
  rejects_exact label "policy_operational_unsupported" (Some path) message
    (fun()->S.admit ~document:(R.document request) ~descriptors:(R.definitions request))
let reject_source_domain label message case=
  let request=valid_source_case label case in
  let document=R.document request and descriptors=R.definitions request in
  let behavior=L.lower(S.admit ~document ~descriptors)in
  ignore(Bioc_checker.Policy_correspondence.check ~expected_document:document ~descriptors behavior);
  rejects_exact label "policy_domain_unsupported" None message(fun()->A.admit ~request ~behavior)
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
let source_profile_controls case=
  let initial_controls= !controls in
  let declarations_path=["request";"document";"program";"declarations"]in
  let source identity=at(declaration_path case identity)case in
  let edit identity path replacement value=set(declaration_path value identity@path)replacement value in
  let clone identity renamed=source identity|>set["id"](str renamed)in
  let add value original=append declarations_path value original in
  let remove identities original=
    let original=set declarations_path(arr(List.filter(fun value->not(List.mem(text "id" value)identities))
      (Json.array(at declarations_path original))))original in
    let spans=["request";"document";"program";"source_map"]in
    set spans(arr(List.filter(fun value->not(List.mem(text "declaration_id" value)identities))
      (Json.array(at spans original))))original in
  let binding label message changed=reject_source_binding label message(repin_authority changed)in
  let cardinality="This source/graph family has one or two exclusive rules/stores and no machines or transitions."in
  let singleton name="This source/graph profile requires exactly one "^name^"."in
  let type_spec kind=obj["$type",str "TypeSpec";"kind",str kind;"unit",Json.Null;"entity_kind",Json.Null]in
  let truth_literal=at["assignments";"0";"value"](source "select")in
  let literal kind value=truth_literal|>set["value_type"](type_spec kind)|>set["value"]value in
  let equal left right=truth_literal|>set["op"](str "eq")|>set["value"]Json.Null
    |>set["args"](arr[left;right])in
  binding "source family has zero rules" cardinality(remove["select";"exclude"]case);
  binding "source family has three rules" cardinality(add(clone "exclude" "third_rule")case);
  let no_stores=case|>remove["selected";"excluded"]
    |>edit "select"["assignments"](arr[])|>edit "exclude"["assignments"](arr[])
    |>edit "exclusive_selection"["condition"](literal "truth"(Json.Bool true))in
  (* This is a distinct rejected source, not a weakened accepted requirement. *)
  binding "source family has zero stores" cardinality no_stores;
  binding "source family has three stores" cardinality(add(clone "selected" "third_store")case);
  binding "source family has two independent observations" (singleton "truth observation")
    (add(clone "condition" "condition2"|>set["coherence"](str "independent_frame"))case);
  binding "source family has two same-operation effects" (singleton "product-bearing effect")
    (add(clone "response" "response2")case);
  binding "source family has two fixed parameters" (singleton "fixed product parameter")
    (add(clone "product" "other_product")case);
  let product_literal=literal "text"(get "value"(source "product"))in
  let literal_argument=edit "response"["parameters";"0";"value"]product_literal case in
  binding "source family has zero parameters with a typed literal actual" (singleton "fixed product parameter")
    (remove["product"]literal_argument);
  binding "source family has two encounter declarations" (singleton "encounter declaration")
    (add(clone "encounter" "encounter2")case);
  let reference kind identity=obj["$type",str "Ref";"kind",str kind;"id",str identity]in
  let machine=obj["$type",str "Machine";"id",str "idle_machine";"executor",reference "Role" "executor";
    "scope",get "scope"(source "selected");"states",arr[str "idle";str "done"];"initial",str "idle";
    "terminal",arr[str "done"];"lifetime",str "encounter";"arbitration",get "arbitration"(source "select")]in
  let transition=obj["$type",str "Transition";"id",str "machine_step";"machine",reference "Machine" "idle_machine";
    "source",str "idle";"destination",str "done";"on",get "on"(source "select");
    "when",literal "truth"(Json.Bool true);"unknown",str "defer";"effects",arr[];"assignments",arr[];
    "unknown_target",Json.Null;"emissions",arr[]]in
  binding "source family has a correctly scoped machine and transition" cardinality(case|>add machine|>add transition);
  binding "source encounter contact loss needs another graph profile"
    "Encounter ownership, target or termination differs from the explicit slot profile."
    (edit "encounter"["termination"](str "contact_loss")case);
  reject_source_operational "second original logical clock" "/document"
    "Bounded operational profile requires exactly one shared logical clock."
    (repin_authority(add(clone "clock" "clock2")case));
  let role_binding=at["request";"document";"deployment";"bindings";"0"]case
    |>set["role"](reference "Role" "executor2")in
  let another_role=case|>add(clone "executor" "executor2")
    |>append["request";"document";"deployment";"bindings"]role_binding
    |>append["request";"document";"deployment";"delivery";"intended_recipients"](reference "Role" "executor2")in
  reject_source_operational "second fully deployed original executor" "/document"
    "Bounded operational profile requires one executor role."(repin_authority another_role);
  let definitions_path=["request";"document";"program";"semantics";"definitions"]in
  let definition_path identity=
    let index=List.find_index(fun definition->text "id" definition=identity)
      (Json.array(at definitions_path case))|>Option.get in definitions_path@[string_of_int index]in
  let effect_definition=definition_path(text "id"(get "contract"(source "response")))in
  let integer_product=case|>edit "product"["value_type"](type_spec "integer")|>edit "product"["value"](Json.int 3)
    |>edit "response"["parameters";"0";"value";"value_type"](type_spec "integer")
    |>set(effect_definition@["parameters";"0";"value_type"])(type_spec "integer")|>repin_source_definitions in
  binding "fixed integer product is outside the text product profile"
    "Source type is outside this exact truth/product profile." integer_product;
  let count amount=obj["$type",str "Quantity";"amount",str amount;"unit",obj[
    "$type",str "Unit";"id",str "count";"dimension",str "count";"quantity_kind",str "count";
    "scale",str "1";"reference",Json.Null]]in
  List.iter(fun(field,amount)->
    binding ("fixed actual product "^field^" refinement")
      ("Source field "^field^" needs semantics outside this graph-binding profile.")
      (edit "product"[field](count amount)integer_product))["lower","1";"upper","5"];
  let expression_references operator identity value=match value with
    |Json.Object fields->List.assoc_opt "$type" fields=Some(str "Expr") &&
        List.assoc_opt "op" fields=Some(str operator) &&
        (match List.assoc_opt "ref" fields with Some(Json.Object reference_fields)->
          List.assoc_opt "id" reference_fields=Some(str identity)|_->false)
    |_->false in
  List.iter(fun(kind,initial,assigned)->
    let changed=case|>edit "selected"["value_type"](type_spec kind)|>edit "selected"["initial"]initial in
    let changed=List.fold_left(fun changed identity->
      let assignments=items "assignments"(at(declaration_path changed identity)changed)|>List.map(fun assignment->
        if text "id"(get "state" assignment)="selected"then set["value"](literal kind assigned)assignment else assignment)in
      edit identity["assignments"](arr assignments)changed)changed["select";"exclude"]in
    let changed=map_json(fun value->if expression_references "state" "selected" value then
      equal(set["value_type"](type_spec kind)value)(literal kind assigned)else value)changed in
    reject_source_domain (kind^" dynamic source state is outside the finite truth domain")
      "Dynamic state in this profile is three-valued truth; fixed text product parameters remain unchanged."
      (repin_authority changed)) ["integer",Json.int 0,Json.int 1;"text",str "off",str "on"];
  let observation_definition=definition_path(text "id"(get "contract"(source "condition")))in
  List.iter(fun(kind,expected)->
    let changed=case|>edit "condition"["value_type"](type_spec kind)
      |>set(observation_definition@["result"])(type_spec kind)in
    let changed=map_json(fun value->if expression_references "observe" "condition" value then
      equal(set["value_type"](type_spec kind)value)(literal kind expected)else value)changed in
    reject_source_domain (kind^" dynamic source observation is outside the finite truth domain")
      "The finite domain supports truth-valued dynamic observations only."
      (repin_source_definitions changed)) ["integer",Json.int 1;"text",str "true"];
  let comparison=equal(literal "integer"(Json.int 1))(literal "integer"(Json.int 1))in
  reject_source_binding "exact integer comparison has no primitive graph operator"
    ~path:(Some "/document/program/declarations/9/when")
    "Source expression operation is outside this graph-binding family."
    (repin_authority(edit "select"["when"]comparison case));
  reject_source_operational "actual product design selection remains unresolved"
    "/document/program/declarations/7" "Only explicitly fixed operational parameters are executable."
    (repin_authority(edit "product"["selection"](str "design")case));
  binding "equal text literal cannot replace the fixed parameter operand"
    "This effect requires exactly the fixed typed product argument." literal_argument;
  require(!controls-initial_controls=23)"First-profile source restriction control census changed";
  Printf.printf "First-profile original-source restrictions: 16 graph-binding, 3 operational, 4 domain controls.\n"
let source_boundary_controls case=
  let initial_controls= !controls in
  let source identity=at(declaration_path case identity)case in
  let edit identity path replacement value=set(declaration_path value identity@path)replacement value in
  let binding label message changed=reject_source_binding label message(repin_authority changed)in
  let operational label path message changed=
    reject_source_operational label path message(repin_authority changed)in
  let definitions_path=["request";"document";"program";"semantics";"definitions"]in
  let observation_definition=text "id"(get "contract"(source "condition"))in
  let definition_index=List.find_index(fun definition->text "id" definition=observation_definition)
    (Json.array(at definitions_path case))|>Option.get in
  let definition_path=definitions_path@[string_of_int definition_index]in
  (* The definition body, every complete reference, descriptor bundle, catalog
     bridge and graph authority are refreshed before generic validity is checked.
     The original model bodies remain unchanged; their names cannot discharge
     newly supplied source clauses or nominal executor/subject constraints. *)
  List.iter(fun field->
    let changed=set(definition_path@[field])(str "cell")case|>repin_source_definitions in
    reject_source_operational ("reachable observation definition "^field) "/definitions"
      "Nominal executor/subject-kind constraints need a supplied typed interpretation and cannot be silently ignored."
      changed)["executor_kind";"subject_kind"];
  let clause=obj["$type",str "ContractClause";"kind",str "precondition";
    "description",str "Require the supplied truth condition.";
    "expression",get "condition"(source "request_progress")]in
  let clauses=set(definition_path@["clauses"])(arr[clause])case|>repin_source_definitions in
  reject_source_operational "reachable observation definition executable clause" "/definitions"
    "Definition clauses need an executable interpretation and cannot be silently discarded." clauses;
  operational "source lineage role needs lifecycle semantics" "/document/program/declarations/0"
    "Population and lineage roles remain unsupported."
    (edit "executor"["lineage_role"](Json.Bool true)case);
  binding "source subject omits the explicit material executor"
    "Encounter ownership, target or termination differs from the explicit slot profile."
    (edit "encounter/target"["executor"]Json.Null case);
  binding "source event evidence has a different coherence identity"
    "Only encounter-local event evidence with frame coherence is supported by this graph profile."
    (edit "condition"["coherence"](str "other_frame")case);
  binding "source reset inheritance needs another graph profile"
    "State lifetime, scope, capacity, reset or writer semantics are outside this family."
    (edit "selected"["inheritance"](str "reset")case);
  let writerless=List.fold_left(fun changed identity->
    let assignments=items "assignments"(at(declaration_path changed identity)changed)
      |>List.filter(fun assignment->text "id"(get "state" assignment)<>"excluded")in
    edit identity["assignments"](arr assignments)changed)case["select";"exclude"]in
  binding "source retains an original store without any writer"
    "State lifetime, scope, capacity, reset or writer semantics are outside this family." writerless;
  let state=at["condition";"args";"0";"args";"0"](source "exclusive_selection")in
  operational "source state-only rising has no observation boundary" "/document/program/declarations/9/on"
    "Rising requires an observed predicate; missing-to-true and state-only edges are unsupported."
    (edit "select"["on";"args"](arr[state])case);
  let updated=get "on"(source "select")|>set["op"](str "updated")|>set["args"](arr[])
    |>set["ref"](obj["$type",str "Ref";"kind",str "Observation";"id",str "condition"])
    |>set["scope"](get "subject"(source "condition"))in
  binding "source updated trigger needs another activation primitive"
    "This rule family triggers only on an observed rising event."
    (edit "select"["on"]updated case);
  binding "source omits the attempt timeout"
    "An attempt bank requires an explicit source timeout."
    (edit "response"["lifecycle";"timeout"]Json.Null case);
  let priority=get "arbitration"(source "select")|>set["mode"](str "priority")
    |>set["tie"](str "declared_order")|>set["order"](arr[str "select";str "exclude"])in
  binding "source coherent priority order needs another graph profile"
    "Rule, arbitration mode, tie/write conflict or lane order changes source semantics."
    (case|>edit "select"["arbitration"]priority|>edit "exclude"["arbitration"]priority);
  (* Three definition constraints + lineage + state-only rising are operational
     exclusions; the seven remaining source-valid controls reach the binder. *)
  require(!controls-initial_controls=12)"First-profile contextual boundary control census changed";
  Printf.printf "First-profile contextual source boundaries: 7 graph-binding and 5 operational controls.\n"
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
  source_profile_controls second;
  source_boundary_controls second;
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

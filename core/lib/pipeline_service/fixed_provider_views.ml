open Bioc_wire
module S = Bioc_pipeline.Synthetic_pipeline
type origin = Host of string * Json.t list | Fresh of string | Retained of string
type site = {kind:string;path:Json.t list;origin:origin;value:Json.t}
let str value=Json.String value
let fail message=Diagnostic.fail "pipeline_callback_manager_protocol" message
let require condition message=if not condition then fail message
let source_kind="biocompiler.ir.intent.SourceLocation"
let type_kind="biocompiler.semantics.types.TypeSpec"
let observable_kind="biocompiler.semantics.realization.Observable"
let domain_kind="biocompiler.semantics.component_contracts.ValueDomain"
let operating_kind="biocompiler.semantics.component_contracts.OperatingDomain"
let pin_kind="biocompiler.ir.component_contracts.PinnedIdentity"
let lock_kind="biocompiler.ir.components.ComponentLock"
let lifetime_kind="biocompiler.ir.composition.LifecycleInterval"
let aliases ~charge ~reserve ~request ~candidate ~role proposal=
  (* Prepay the fixed closures and the small literal path/envelope skeletons.
     Variable lists, strings and site tables are paid below before allocation. *)
  reserve 4096;
  let get key raw=
    match List.find_opt(fun(name,_)->charge(String.length name+String.length key+1);name=key)(Json.object_fields raw) with
    | Some(_,value)->value | None->fail "Typed provider construction field is absent." in
  let text key raw=let value=Json.string(get key raw) in charge(String.length value+1);value in
  let array key raw=Json.array(get key raw) in
  let sites=ref [] in
  let append path parts=charge(List.length path+List.length parts+1);
    reserve(32*(List.length path+List.length parts+1));path@parts in
  let key prefix name=charge(String.length prefix+String.length name+24);
    reserve(String.length prefix+String.length name+24);
    prefix^"/"^string_of_int(String.length name)^":"^name in
  let concatenate values=
    let size=List.fold_left(fun total value->charge(String.length value+1);total+String.length value)0 values in
    reserve(size+64);String.concat "" values in
  let emit kind path origin value=
    charge 1;reserve(128+32*List.length path);
    sites:={kind;path;origin;value}::!sites in
  let find predicate values=List.find_opt(fun value->charge 1;predicate value) values in
  let equal_text left right=charge(String.length left+String.length right+1);left=right in
  let find_id id values=match find(fun value->equal_text(text "id" value)id) values with
    | Some value->value | None->fail "Typed provider origin references an absent node." in
  let indexed values=List.mapi(fun index value->charge 1;reserve 32;index,value) values in
  let request_inputs=array "inputs"(get "domain" request) in
  let responses=array "requirements"(get "contract" request) in
  let input_index signal field=match find(fun(_,item)->
    equal_text(text "signal_id" item) signal && equal_text(text "field" item) field)(indexed request_inputs) with
    | Some(index,_)->index | None->fail "Typed provider origin has no authored input." in
  let response_index id=match find(fun(_,item)->equal_text(text "id" item) id)(indexed responses) with
    | Some(index,_)->index | None->fail "Typed provider origin has no authored response." in
  let input_path index=[str "domain";str "inputs";Json.int index;str "observable"] in
  let response_path index=[str "contract";str "requirements";Json.int index;str "observable"] in
  let rec dtype path origin value=
    emit type_kind path origin value;
    List.iteri(fun index item->charge 1;
      let parts=[str "arguments";Json.int index] in
      let child=match origin with
        | Host(root,origin_path)->Host(root,append origin_path parts)
        | Fresh name->Fresh(key name(string_of_int index))
        | Retained name->Retained(key name(string_of_int index)) in
      dtype(append path parts)child item)(array "arguments" value) in
  let observable path origin_path value=
    emit observable_kind path(Host("request",origin_path))value;
    dtype(append path[str "dtype"])(Host("request",append origin_path[str "dtype"]))(get "dtype" value) in
  let global_type path name value=dtype path(Host(name,[]))value in
  let output=get "output" proposal in
  (match role with
  | S.Intent_to_behavior_producer->
      (* Each lowering reparses its intent. Source objects are fresh per parsed
         node, then reused by that node's lowered requirement; equal locations
         on two different nodes are deliberately not coalesced. *)
      List.iteri(fun index node->charge 1;
        match List.assoc_opt "source"(Json.object_fields node) with
        | None | Some Json.Null->()
        | Some value->emit source_kind [str "output";str "nodes";Json.int index;str "source"]
            (Fresh(key "source"(text "id" node)))value)(array "nodes" output);
      List.iteri(fun index requirement->charge 1;
        match List.assoc_opt "source"(Json.object_fields requirement) with
        | None | Some Json.Null->()
        | Some value->emit source_kind [str "output";str "requirements";Json.int index;str "source"]
            (Fresh(key "source"(text "source_node_id" requirement)))value)(array "requirements" output)
  | S.Behavior_to_synthetic_producer _->
      let observations=get "observation_map" output in
      List.iteri(fun index node->charge 1;
        let path=[str "output";str "mechanism";str "nodes";Json.int index;str "output"] in
        let value=get "output" node and id=text "id" node in
        let type_path=append path[str "dtype"] in
        match text "kind" node with
        | "input"->
            let item=match find(fun item->equal_text(text "mechanism_input_id" item)id)(array "inputs" observations) with
              | Some item->item | None->fail "Synthetic input lacks its observation origin." in
            observable path(input_path(input_index(text "signal_id" item)(text "field" item)))value
        | "output"->
            let item=match find(fun item->equal_text(text "mechanism_output_id" item)id)(array "outputs" observations) with
              | Some item->item | None->fail "Synthetic output lacks its response origin." in
            observable path(response_path(response_index(text "requirement_id" item)))value
        | "constant" when String.starts_with ~prefix:"expression:" id->()
        | "constant" | "select" when List.exists(fun prefix->String.starts_with ~prefix id)["active:";"inactive:";"select:"]->
            let ids=array "requirement_ids" node in
            let requirement=match ids with [Json.String value]->value | _->fail "Synthetic witness lacks its unique response origin." in
            dtype type_path(Host("request",append(response_path(response_index requirement))[str "dtype"]))(get "dtype" value)
        | "constant" | "and" | "or" | "not" | "compare" | "held_for" | "onset" | "memory" | "any_contact" | "pulse"->
            global_type type_path "BOOLEAN"(get "dtype" value)
        | _->fail "Synthetic provider type origin is not in the closed construction profile.")
        (array "nodes"(get "mechanism" output))
  | S.Synthetic_to_components_producer _->
      let candidate=match candidate with Some value->value | None->fail "Component provider lacks its captured adapter input." in
      let nodes=array "nodes"(get "mechanism" candidate) in
      let node_count=List.fold_left(fun count _->charge 1;count+1)0 nodes in
      let registry=get "registry" output and composition=get "composition" output in
      let components=array "components" registry in
      let component_for id=find_id(concatenate["synthetic.instance:";id])components in
      let output_port id=match find(fun item->equal_text(text "id" item)"out")(array "ports"(component_for id)) with
        | Some value->value | None->fail "Adapted node lacks its output port." in
      let input_origin id=
        let item=match find(fun item->equal_text(text "mechanism_input_id" item)id)
            (array "inputs"(get "observation_map" candidate)) with
          | Some value->value | None->fail "Adapted input lacks its observation origin." in
        input_index(text "signal_id" item)(text "field" item) in
      let mode initial=if initial then "initialization" else "domain" in
      let rec domain_origin depth initial id=
        charge 1;require(depth<=node_count) "Domain origin contains a cycle.";
        let node=find_id id nodes in
        let operation=text "kind" node in
        if operation="input" then `Input(input_origin id)
        else
          let inputs=List.map(fun value->charge 1;reserve 32;let value=Json.string value in charge(String.length value+1);value)(array "inputs" node) in
          let known=List.for_all(fun source->charge 1;text "kind"(get(mode initial)(output_port source))<>"unknown")inputs in
          if known && (operation="output" || (initial && (operation="onset" || operation="pulse"))) then
            match inputs with first::_->domain_origin(depth+1)initial first | []->fail "Domain alias lacks an operand."
          else `Node id in
      let typed_domain path origin value=
        emit domain_kind path(Retained origin)value in
      let domain initial id path value=
        let origin=domain_origin 0 initial id in
        let prefix=if initial then "initial" else "runtime" in
        let name=match origin with `Input index->key(prefix^"-input")(string_of_int index)
          | `Node source->key(prefix^"-node")source in
        typed_domain path name value;
        let dtype_path=append path[str "dtype"] in
        if text "kind" value="boolean" then global_type dtype_path "BOOLEAN"(get "dtype" value)
        else match origin with
          | `Input index->dtype dtype_path(Host("request",append(input_path index)[str "dtype"]))(get "dtype" value)
          | `Node source->dtype dtype_path(Retained(key "port-type" source))(get "dtype" value) in
      let required path value=
        emit operating_kind path(Retained "required-domain")value;
        List.iter(fun(name,item)->charge 1;
          let path=append path[str "constraints";str name] in
          typed_domain path(key "required-coordinate" name)item;
          let type_path=append path[str "dtype"] in
          if name="concurrent_contacts" then global_type type_path "LEVEL"(get "dtype" item)
          else if text "kind" item="boolean" then global_type type_path "BOOLEAN"(get "dtype" item)
          else
            let index=match find(fun(_,input)->equal_text name(concatenate["observation:";text "signal_id" input;":";text "field" input]))(indexed request_inputs) with
              | Some(index,_)->index | None->fail "Required coordinate lacks an authored origin." in
            dtype type_path(Host("request",append(input_path index)[str "dtype"]))(get "dtype" item))
          (Json.object_fields(get "constraints" value)) in
      let pin_origin node value=
        match text "kind" value,text "id" value with
        | "source","realization_request"->"common-source"
        | "model","synthetic.program"->"common-model"
        | "registry","synthetic.catalog"->"common-catalog"
        | _->key "operator-pin" node in
      let pins=ref [] in
      let pin_key value=reserve 256;List.map(fun name->str(text name value))["kind";"id";"version"] in
      let remember_pin node value=
        let key_value=pin_key value in
        charge 1;reserve 128;
        pins:=(key_value,pin_origin node value)::!pins in
      (* Registry.lock iterates the original mechanism inventory, then retains
         the last object at each explicit (kind,id,version) key. This is the
         audited constructor's overwrite rule, not content-based interning. *)
      List.iter(fun node->charge 1;let id=text "id" node in let component=component_for id in
        List.iter(remember_pin id)(array "identities" component);
        List.iter(remember_pin id)(array "evidence" component);
        List.iter(fun parameter->charge 1;remember_pin id(get "source" parameter))(array "parameters" component))nodes;
      List.iteri(fun index component->charge 1;
        let prefix="synthetic.instance:" in let component_id=text "id" component in
        require(String.starts_with ~prefix component_id) "Component is outside the fixed adapter construction profile.";
        reserve(String.length component_id+32);
        let id=String.sub component_id(String.length prefix)(String.length component_id-String.length prefix) in
        let node=find_id id nodes in
        let path=[str "output";str "registry";str "components";Json.int index] in
        required(append path[str "supported_domain"])(get "supported_domain" component);
        List.iteri(fun port_index port->charge 1;
          let port_path=append path[str "ports";Json.int port_index] in
          let port_id=text "id" port in
          let source=if port_id="out" then id else
            let inputs=array "inputs" node in
            let index=match find(fun(index,_)->equal_text port_id("in:"^string_of_int index))(indexed inputs) with
              | Some(index,_)->index | None->fail "Input port has no original operand slot." in
            Json.string(List.nth inputs index) in
          dtype(append port_path[str "dtype"])(Retained(key "port-type" source))(get "dtype" port);
          domain false source(append port_path[str "domain"])(get "domain" port);
          domain true source(append port_path[str "initialization"])(get "initialization" port))
          (array "ports" component);
        List.iteri(fun pin_index value->charge 1;
          emit pin_kind(append path[str "identities";Json.int pin_index])(Retained(pin_origin id value))value)
          (array "identities" component);
        List.iteri(fun parameter_index parameter->charge 1;
          let path=append path[str "parameters";Json.int parameter_index] in
          emit pin_kind(append path[str "source"])(Retained "common-source")(get "source" parameter);
          let value=get "value" parameter in
          if text "id" parameter="value" then domain false id(append path[str "value"])value
          else (
            require(text "id" parameter="duration") "Unknown fixed parameter construction origin.";
            global_type(append path[str "value";str "dtype"])"DURATION"(get "dtype" value)))
          (array "parameters" component))components;
      let lock=get "registry_lock" composition in
      List.iteri(fun index value->charge 1;
        emit lock_kind[str "output";str "composition";str "registry_lock";str "components";Json.int index]
          (Retained(key "lock"(text "node_id" value)))value)(array "components" lock);
      List.iteri(fun index value->charge 1;
        let actual=pin_key value in
        let origin=match find(fun(previous,_)->
          charge 1;List.for_all2(fun left right->equal_text(Json.string left)(Json.string right))previous actual) !pins with
          | Some(_,origin)->origin | None->fail "Registry lock identity has no constructor origin." in
        emit pin_kind[str "output";str "composition";str "registry_lock";str "identities";Json.int index]
          (Retained origin)value)(array "identities" lock);
      let authored_nodes=indexed(array "nodes"(get "behavior" request)) in
      List.iteri(fun index instance->charge 1;
        let id=text "id" instance in
        let path=[str "output";str "composition";str "instances";Json.int index] in
        emit lock_kind(append path[str "component"])(Retained(key "lock" id))(get "component" instance);
        required(append path[str "required_domain"])(get "required_domain" instance);
        emit lifetime_kind(append path[str "lifetime"])(Host("defaultLifecycle",[]))(get "lifetime" instance);
        let lineage=Json.array(get id(get "source_map" candidate)) in
        let rec first=function
          | []->None
          | reference::rest->
              let index,node=match find(fun(_,node)->equal_text(text "id" node)(Json.string reference))authored_nodes with
                | Some item->item | None->fail "Component source origin references an absent behavior node." in
              (match List.assoc_opt "source"(Json.object_fields node) with
               | None | Some Json.Null->first rest | Some _->Some index) in
        match first lineage,get "source" instance with
        | None,Json.Null->()
        | Some source_index,value when value<>Json.Null->
            emit source_kind(append path[str "source"])
              (Host("request",[str "behavior";str "nodes";Json.int source_index;str "source"]))value
        | _->fail "Component source origin disagrees with its native result.")
        (array "instances" composition)
  | S.Intent_to_behavior_validator | S.Behavior_to_synthetic_validator | S.Synthetic_to_components_validator->
      fail "A validator cannot supply producer alias metadata.");
  List.iter(fun _->charge 1;reserve 32) !sites;List.rev !sites

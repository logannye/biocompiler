open Bioc_wire
module B=Bioc_domain.Policy_module_bundle
module D=Bioc_domain.Policy_document
type lineage={source_path:string;flat_path:string;instance:string option;
  template:B.pin option;declaration:string;expanded:string}
type checked_linkage={bundle_value:B.t;program_value:D.t;evidence_value:Json.t;lineage_value:lineage list}
let evidence value=value.evidence_value
let bundle value=value.bundle_value
let program value=value.program_value
let str value=Json.String value
let arr value=Json.Array value
let obj value=Json.Object value
let schema_version="biocompiler.policy_module_linkage.v0.1"
let implementation="biocompiler.ocaml.policy_module_linking_check.v0.1"

module Make(Invocation:sig val budget:B.meter val limits:B.limits end)=struct
  let budget=Invocation.budget
  let charge=B.charge budget
  let scan=B.scan budget
  module Meter=Policy_generation_meter.Make(struct let charge=charge end)
  module List=Meter.List
  module String=struct
    include Meter.String
    let equal left right=B.inspect budget(Stdlib.String.length left+Stdlib.String.length right);Stdlib.String.equal left right
    let compare left right=B.inspect budget(Stdlib.String.length left+Stdlib.String.length right);Stdlib.String.compare left right
    let starts_with ~prefix value=B.inspect budget(Stdlib.String.length prefix);Stdlib.String.starts_with ~prefix value
  end
  module Names_base=Map.Make(String)
  module Names=struct
    include Names_base
    let iter f values=Names_base.iter(fun key value->charge 1;f key value)values
    let cardinal values=Names_base.fold(fun _ _ count->charge 1;count+1)values 0
    let union f left right=iter(fun _ _->())left;iter(fun _ _->())right;Names_base.union f left right
  end
  module Seen_base=Set.Make(String)
  module Seen=struct
    include Seen_base
    let cardinal values=Seen_base.fold(fun _ count->charge 1;count+1)values 0
    let equal left right=ignore(cardinal left);ignore(cardinal right);Seen_base.equal left right
  end
  let fail path condition message=Diagnostic.require ~path condition "policy_module_linking" message
  let count condition=Diagnostic.require ~path:"/modules/limits" condition "policy_module_limit"
    "Expanded module data exceeds its original count allowance."
  let same left right=scan left;scan right;Json.equal left right
  let get key raw=
    let fields=Json.object_fields raw in
    List.iter(fun(name,_)->B.inspect budget(Stdlib.String.length name+Stdlib.String.length key))fields;
    Json.field key fields
  let text key raw=Json.string(get key raw)
  let items key raw=Json.array(get key raw)
  let tag raw=match raw with Json.Object fields->
    (match List.find_opt(fun(name,_)->String.equal name "$type")fields with
      |Some(_,Json.String value)->value|_->"")|_->""
  let set key value raw=obj(List.map(fun(name,old)->name,if String.equal name key then value else old)(Json.object_fields raw))
  let id raw=text "id" raw
  let ref_of raw=obj["$type",str "Ref";"id",str(id raw);"kind",str(tag raw)]
  let ref_parts raw=fail "/modules" (tag raw="Ref")"Expected a complete nominal Ref.";text "id" raw,text "kind" raw
  let mem name names=Seen.mem name names
  let set_of names=List.fold_left(fun set name->charge 1;Seen.add name set)Seen.empty names
  let unique path label names=
    ignore(List.fold_left(fun seen name->fail path(not(mem name seen))("Duplicate "^label^": "^name);Seen.add name seen)Seen.empty names)
  let find path label name rows=match Names.find_opt name rows with
    |Some value->value|None->Diagnostic.fail ~path "policy_module_linking" (label^" is absent: "^name)
  let at_path path f=try f()with Diagnostic.Error error when error.path=None->
    raise(Diagnostic.Error{error with path=Some path})
  let index path label values=List.fold_left(fun map value->let name=at_path path(fun()->id value)in
    fail path(not(Names.mem name map))("Duplicate "^label^": "^name);Names.add name value map)Names.empty values
  let walk f raw=
    let rec visit path raw=charge 1;f path raw;match raw with
      |Json.Array values->List.iteri(fun i value->visit(path^"/"^string_of_int i)value)values
      |Json.Object fields->List.iter(fun(key,value)->visit(path^"/"^key)value)fields
      |_->()in visit "" raw
  let references f raw=walk(fun path value->if tag value="Ref"then f path value)raw
  let allowed access kind=List.mem kind(match access with
    |B.Context->["Role";"Subject";"Encounter";"SpatialScope";"Clock";"Channel"]
    |B.Read->["Observation";"StateStore";"Parameter";"Effect";"Message"]
    |B.Write->["StateStore";"Machine"]|B.Request->["Effect";"Message"])
  let permits access operation=operation="context" || match access,operation with
    |(B.Read|B.Write|B.Request),"read"|B.Write,"write"|B.Request,"request"->true|_->false
  let port_valid(port:B.port)=fail port.path(allowed port.access(tag port.declaration))
    "The declaration kind does not support the declared port access mode."
  let port_index path ports=List.fold_left(fun map(port:B.port)->port_valid port;
    fail path(not(Names.mem port.name map))("Duplicate port: "^port.name);Names.add port.name port map)Names.empty ports
  type footprint={reads:Json.t list;writes:Json.t list;requests:Json.t list}
  let footprint body=
    let reads=ref [] and writes=ref [] and requests=ref []in
    walk(fun _ item->match tag item with
      |"Expr" when List.mem(text "op" item)["observe";"state";"parameter";"updated";"effect_event";"message_event"]->
        if get "ref" item<>Json.Null then reads:=get "ref" item:: !reads
      |"Assignment"->writes:=get "state" item:: !writes
      |"StateStore" when get "reset" item<>Json.Null->writes:=ref_of item:: !writes
      |"Rule"|"Transition"->requests:=List.append(items "effects" item)(List.append(items "emissions" item)!requests);
        if tag item="Transition"then(reads:=get "machine" item:: !reads;writes:=get "machine" item:: !writes)
      |_->())(arr body);
    let order left right=let c=String.compare(text "kind" left)(text "kind" right)in
      if c=0 then String.compare(id left)(id right)else c in
    {reads=List.sort_uniq order !reads;writes=List.sort_uniq order !writes;requests=List.sort_uniq order !requests}
  let source_path path=if String.equal path "/document"then ""
    else if String.starts_with ~prefix:"/document/"path then String.sub path 9(String.length path-9)else path
  let source_error remap (error:Diagnostic.t)=raise(Diagnostic.Error{error with path=Option.map(fun path->remap(source_path path))error.path})
  let checked_source remap raw=
    scan raw;
    let document=try Meter.Document.of_json raw with Diagnostic.Error error->source_error remap error in
    let report=try Policy_check.check ~charge document with Diagnostic.Error error->source_error remap error in
    scan report;
    if text "status" report<>"valid" then(match items "diagnostics" report with
      |first::_->let path=match get "path" first with Json.String value->Some(remap(source_path value))|_->None in
        raise(Diagnostic.Error{code=text "code" first;message=text "message" first;path})
      |[]->Diagnostic.fail "policy_module_linking" "Invalid source lacked an original diagnostic.");document
  let prefix_remap rows fallback path=
    let rec search=function []->fallback^path|(flat,original)::rest->
      if String.equal path flat then original
      else if String.starts_with ~prefix:(flat^"/")path then original^String.sub path(String.length flat)(String.length path-String.length flat)
      else search rest in search rows
  type template_data={original:B.template;input_ports:B.port Names.t;
    formal:Json.t Names.t;body:(Json.t*string)list;footprint:footprint}
  let validate_template(template:B.template)=
    let path=template.path in
    let inputs=port_index(path^"/inputs")template.inputs in
    ignore(port_index(path^"/outputs")template.outputs);
    let formal=index(path^"/inputs")"input declaration"(List.map(fun(port:B.port)->port.declaration)template.inputs)in
    let located field values=List.mapi(fun i value->value,path^"/"^field^"/"^string_of_int i)values in
    let body=List.concat[located "declarations" template.declarations;located "assumptions" template.assumptions;located "guarantees" template.guarantees]in
    count(List.length body+List.length template.inputs<=Invocation.limits.max_declarations);
    let body_values=List.map fst body in
    let local=index path "local declaration"body_values in
    Names.iter(fun name _->charge 1;fail path(not(Names.mem name formal))("Local declaration captures formal identity: "^name))local;
    List.iteri(fun i value->fail(path^"/declarations/"^string_of_int i)(tag value<>"Requirement")
      "Requirements belong in explicit assumptions or guarantees.")template.declarations;
    List.iteri(fun i value->fail(path^"/assumptions/"^string_of_int i)(tag value="Requirement" && text "kind" value="assumption")
      "A premise must retain its complete assumption Requirement.")template.assumptions;
    List.iteri(fun i value->fail(path^"/guarantees/"^string_of_int i)(tag value="Requirement" && text "kind" value<>"assumption")
      "A guarantee must retain its non-assumption Requirement kind.")template.guarantees;
    let formal_values=List.map(fun(port:B.port)->port.declaration)template.inputs in
    let synthetic=obj["$type",str "PolicyProgram";"id",str template.pin.id;"profile",str D.profile;
      "semantics",template.semantics;"declarations",arr(List.append formal_values body_values);"source_map",arr template.source_map]in
    let original_paths=List.append(List.map(fun(port:B.port)->port.path^"/declaration")template.inputs)(List.map snd body)in
    let locations=List.mapi(fun i original->"/declarations/"^string_of_int i,original)original_paths in
    let remap=prefix_remap locations path in
    (* Decode every embedded source field before inspecting its contents. Run
       semantic checking after the module-specific interface/privacy checks so
       those failures retain their original contract location. *)
    (try ignore(Meter.Document.of_json synthetic)with Diagnostic.Error error->source_error remap error);
    List.iteri(fun i definition->
      let lexical=set_of(List.map id(items "parameters" definition))in
      references(fun suffix reference->let identity,kind=ref_parts reference in
        fail(path^"/semantics/definitions/"^string_of_int i^suffix)(kind="Parameter" && mem identity lexical)
          "Module semantic definitions cannot capture ambient declarations.")definition)(items "definitions" template.semantics);
    List.iter(fun(port:B.port)->references(fun suffix reference->fail(port.path^"/declaration"^suffix)
      (Names.mem(id reference)formal)"Input signature depends on a hidden local declaration.")port.declaration)template.inputs;
    List.iter(fun(port:B.port)->let actual=find port.path "Output declaration"(id port.declaration)local in
      fail port.path(same actual port.declaration)"Output signature differs from its complete original local declaration.")template.outputs;
    let exported_names=List.map(fun(port:B.port)->id port.declaration)template.outputs in
    unique(path^"/outputs")"exported declaration"exported_names;
    let exported=set_of exported_names in
    let private_ids=List.mapi(fun i ref_raw->let at=path^"/private/"^string_of_int i in
      scan ref_raw;Json.exact_fields ~path:at["$type";"id";"kind"](Json.object_fields ~path:at ref_raw);
      fail at(tag ref_raw="Ref")"Private ownership requires a complete Ref.";
      let identity,kind=ref_parts ref_raw in
      let declaration=find at "Private declaration"identity local in
      fail at(String.equal kind(tag declaration) && not(mem identity exported))"Private kind differs or identity is exported.";
      identity)template.private_refs in
    unique(path^"/private")"private identity"private_ids;
    let private_names=set_of private_ids in
    List.iter(fun(value,at)->if List.mem(tag value)["StateStore";"Machine";"Effect"]then
      fail at(mem(id value)exported || mem(id value)private_names)"Unexported state, machine and effect need explicit private ownership.")body;
    List.iter(fun(port:B.port)->references(fun suffix reference->let identity=id reference in
      fail(port.path^"/declaration"^suffix)(Names.mem identity formal || mem identity exported)
        "Output signature exposes a private or undeclared dependency.")port.declaration)template.outputs;
    let known=Names.union(fun _ _ _->assert false)formal local in
    List.iter(fun(value,at)->references(fun suffix reference->let identity,kind=ref_parts reference in
      let actual=find(at^suffix)"Module reference"identity known in
      fail(at^suffix)(String.equal kind(tag actual))"Module reference has the wrong nominal kind.")value;
      walk(fun suffix item->if tag item="Arbitration"then List.iter(fun raw->let identity=Json.string raw in
        let actual=find(at^suffix^"/order")"Local arbitration participant"identity local in
        fail(at^suffix^"/order")(List.mem(tag actual)["Rule";"Transition"])"Arbitration names a non-participant.")(items "order" item))value)body;
    let footprint=footprint body_values in
    let by_identity=List.fold_left(fun map(port:B.port)->Names.add(id port.declaration)port map)Names.empty template.inputs in
    List.iter(fun(operation,refs)->List.iter(fun reference->match Names.find_opt(id reference)by_identity with
      |None->()|Some port->fail port.path(permits port.access operation)("Input does not authorize "^operation^": "^id reference))refs)
      ["read",footprint.reads;"write",footprint.writes;"request",footprint.requests];
    List.iteri(fun i span->fail(path^"/source_map/"^string_of_int i)(tag span="SourceSpan" && Names.mem(text "declaration_id" span)local)
      "Template source map names an input or absent declaration.")template.source_map;
    ignore(checked_source remap synthetic);
    {original=template;input_ports=inputs;formal;body;footprint}
  let rewrite mapping path ~declaration raw=
    let rec visit raw=charge 1;match tag raw with
      |"Ref"->find path "Relocated nominal reference"(id raw)mapping
      |"DefinitionRef"|"SemanticDefinition"|"SemanticBundle"->raw
      |kind->match raw with
        |Json.Array values->arr(List.map visit values)
        |Json.Object fields->
          let result=obj(List.map(fun(key,value)->key,visit value)fields)in
          if kind="Arbitration"then set "order"(arr(List.map(fun value->str(id(find path "Relocated arbitration participant"(Json.string value)mapping)))(items "order" raw)))result
          else if kind="SourceSpan"then set "declaration_id"(str(id(find path "Relocated source span"(text "declaration_id" raw)mapping)))result
          else result
        |_->raw in
    let result=visit raw in
    let result=if declaration then set "id"(str(id(find path "Relocated declaration"(id raw)mapping)))result else result in
    scan result;result
  type expanded={body:(Json.t*string)list;outputs:(B.port*Json.t)Names.t;mapping:Json.t Names.t}
  let first_difference left right=
    let rec visit path left right=charge 1;match left,right with
      |Json.Array left,Json.Array right->array path 0 left right
      |Json.Object left,Json.Object right->
        let sort=List.sort(fun(a,_)(b,_)->String.compare a b)in fields path(sort left)(sort right)
      |_->if same left right then None else Some path
    and array path index left right=match left,right with
      |[],[]->None
      |a::left,b::right->(match visit(path^"/"^string_of_int index)a b with
        |None->array path(index+1)left right|difference->difference)
      |_->Some(path^"/"^string_of_int index)
    and fields path left right=match left,right with
      |[],[]->None
      |(a,x)::left,(b,y)::right when String.equal a b->
        (match visit(path^"/"^a)x y with None->fields path left right|difference->difference)
      |_->Some path in
    visit "/program" left right
  let reconstruct bundle=
    let context=B.context bundle in scan context;
    let context_document=Meter.Document.of_json ~path:"/modules/context" context in
    fail "/modules/context" (D.kind context_document=D.Program)"Module context must be a complete PolicyProgram.";
    let base=items "declarations" context and base_semantics=get "semantics" context in
    let identity=text "id" context in
    (* The context is the original compose_modules program identity. *)
    let simple value=String.length value>=1 && String.length value<=64 &&
      (match value.[0]with 'A'..'Z'|'a'..'z'->true|_->false) &&
      String.for_all(function 'A'..'Z'|'a'..'z'|'0'..'9'|'_'|'-'->true|_->false)value in
    fail "/modules/context/id" (simple identity)"Composition identity must use the simple module name grammar.";
    count(List.length base<=Invocation.limits.max_declarations);
    let base_map=index "/modules/context/declarations" "context declaration"base in
    let templates=B.templates bundle and instances=B.instances bundle in
    unique "/modules/instances" "instance namespace"(List.map(fun(instance:B.instance)->instance.name)instances);
    let template_key(pin:B.pin)=pin.id^"\000"^pin.version in
    unique "/modules/templates" "template id/version"(List.map(fun(template:B.template)->template_key template.pin)templates);
    let template_map=List.fold_left(fun result(template:B.template)->
      Names.add(template_key template.pin)(at_path template.path(fun()->validate_template template))result)Names.empty templates in
    let used=ref Seen.empty in
    let instance_map=List.fold_left(fun result(instance:B.instance)->
      let key=template_key instance.template in
      let data=find(instance.path^"/template")"Original template pin"key template_map in
      fail(instance.path^"/template")(same(B.pin_to_json instance.template)(B.pin_to_json data.original.pin))
        ("Complete template pin differs for "^instance.template.id^" version "^instance.template.version);
      used:=Seen.add key !used;
      unique(instance.path^"/bindings")"input binding"(List.map(fun(binding:B.binding)->binding.port)instance.bindings);
      let bound=set_of(List.map(fun(binding:B.binding)->binding.port)instance.bindings)
      and required=set_of(List.map(fun(port:B.port)->port.name)data.original.inputs)in
      fail(instance.path^"/bindings")(Seen.equal bound required)"Every declared input requires exactly one explicit binding.";
      let assumptions=index(instance.path^"/assumptions")"acknowledged assumption"instance.assumptions in
      fail(instance.path^"/assumptions")(Names.cardinal assumptions=List.length data.original.assumptions)
        "Missing or extra complete assumption acknowledgments.";
      List.iter(fun assumption->let supplied=find(instance.path^"/assumptions")"Original premise"(id assumption)assumptions in
        fail(instance.path^"/assumptions")(same assumption supplied)"Acknowledgment differs from its complete original assumption body.")data.original.assumptions;
      Names.add instance.name(instance,data)result)Names.empty instances in
    fail "/modules/templates" (Seen.cardinal !used=List.length templates)"Every original template must be used by an instance.";
    let total=List.fold_left(fun total(instance:B.instance)->let _,data=find instance.path "Instance"instance.name instance_map in
      total+List.length data.body)(List.length base)instances in
    count(total<=Invocation.limits.max_declarations);
    let prefixes=List.map(fun(instance:B.instance)->instance.name^"/")instances in
    let external_identity path identity=fail path(not(List.exists(fun prefix->String.starts_with ~prefix identity)prefixes))
      ("Raw context identity cannot cross an instance interface: "^identity)in
    List.iteri(fun i value->let path="/modules/context/declarations/"^string_of_int i in
      external_identity(path^"/id")(id value);
      walk(fun suffix item->if tag item="Ref"then external_identity(path^suffix)(id item)
        else if tag item="Arbitration"then List.iter(fun name->external_identity(path^suffix^"/order")(Json.string name))(items "order" item))value)base;
    references(fun suffix reference->external_identity("/modules/context/semantics"^suffix)(id reference))base_semantics;
    List.iteri(fun i span->external_identity("/modules/context/source_map/"^string_of_int i)(text "declaration_id" span))(items "source_map" context);
    let expanded=ref Names.empty and visiting=ref Seen.empty in
    let rec expand depth name=
      charge 1;count(depth<=Invocation.limits.max_instances);
      match Names.find_opt name !expanded with Some value->value|None->
      let instance,data=find "/modules/instances" "Output provider instance"name instance_map in
      fail instance.path(not(mem name !visiting))"Cyclic module output connections are unsupported.";
      visiting:=Seen.add name !visiting;
      let mapping=ref(List.fold_left(fun result(value,_)->Names.add(id value)
        (obj["$type",str "Ref";"id",str(name^"/"^id value);"kind",str(tag value)])result)Names.empty data.body)in
      let actuals=ref Names.empty in
      List.iter(fun(binding:B.binding)->
        let port=find binding.path "Input port"binding.port data.input_ports in
        let actual=match binding.target with
          |B.Context_ref reference->external_identity(binding.path^"/target")(id reference);
            let actual=find(binding.path^"/target")"Context binding target"(id reference)base_map in
            fail(binding.path^"/target")(String.equal(text "kind" reference)(tag actual))
              ("Nominal binding kind differs for "^id reference^": expected "^tag port.declaration^", actual "^tag actual);actual
          |B.Output_ref target->
            fail(binding.path^"/target")(Names.mem target.instance instance_map)("Output provider is absent: "^target.instance);
            let provider=expand(depth+1)target.instance in
            let output,actual=find(binding.path^"/target")"Declared output port"target.port provider.outputs in
            fail binding.path(List.for_all(fun operation->not(permits port.access operation)||permits output.access operation)
              ["context";"read";"write";"request"])"Output interface does not authorize requested input access.";actual in
        mapping:=Names.add(id port.declaration)(ref_of actual)!mapping;
        actuals:=Names.add port.name actual !actuals)instance.bindings;
      let writes=List.filter_map(fun reference->if Names.mem(id reference)data.formal then
        Some(id(find instance.path "Writable input"(id reference)!mapping))else None)data.footprint.writes in
      unique(instance.path^"/bindings")"aliased writable input"writes;
      List.iter(fun(port:B.port)->
        let expected=rewrite !mapping port.path ~declaration:true port.declaration in
        let actual=find instance.path "Bound input"port.name !actuals in
        fail(instance.path^"/bindings")(same expected actual)
          ("Full input signature differs at "^name^"/"^port.name^": expected "^tag expected^" "^id expected^", actual "^tag actual^" "^id actual))data.original.inputs;
      let body=List.map(fun(value,path)->rewrite !mapping path ~declaration:true value,path)data.body in
      let by_id=index instance.path "expanded declaration"(List.map fst body)in
      let outputs=List.fold_left(fun result(port:B.port)->let identity=id(find port.path "Output relocation"(id port.declaration)!mapping)in
        Names.add port.name(port,find port.path "Expanded output"identity by_id)result)Names.empty data.original.outputs in
      let result={body;outputs;mapping= !mapping}in
      expanded:=Names.add name result !expanded;visiting:=Seen.remove name !visiting;result in
    List.iter(fun(instance:B.instance)->ignore(expand 0 instance.name))instances;
    let context_body=List.mapi(fun i value->value,"/modules/context/declarations/"^string_of_int i)base in
    let definitions=ref(index "/modules/context/semantics/definitions" "semantic definition"(items "definitions" base_semantics))in
    let definition_order=ref(List.map id(items "definitions" base_semantics))in
    let spans=ref(items "source_map" context)and combined=ref context_body and lineage=ref[]and offset=ref 0 in
    let add_lineage instance template body=List.iter(fun(value,path)->
      let original=match instance with None->id value|Some name->String.sub(id value)(String.length name+1)(String.length(id value)-String.length name-1)in
      lineage:={source_path=path;flat_path="/program/declarations/"^string_of_int !offset;instance;template;declaration=original;expanded=id value}:: !lineage;incr offset)body in
    add_lineage None None context_body;
    let writers=ref Names.empty in
    let ownership owner path body=List.iter(fun reference->let identity=id reference in
      (match Names.find_opt identity !writers with None->()|Some previous->fail path(String.equal previous owner)
        ("Conflicting shared writes across owners "^previous^" and "^owner^": "^identity));
      writers:=Names.add identity owner !writers)(footprint body).writes in
    ownership "<context>" "/modules/context" base;
    List.iter(fun(instance:B.instance)->let data=find instance.path "Template"(template_key instance.template)template_map in
      let expanded=find instance.path "Expanded instance"instance.name !expanded in
      ownership instance.name instance.path(List.map fst expanded.body);
      combined:=List.append !combined expanded.body;
      add_lineage(Some instance.name)(Some instance.template)expanded.body;
      spans:=List.append !spans(List.map(rewrite expanded.mapping instance.path ~declaration:false)data.original.source_map);
      List.iter(fun definition->let identity=id definition in
        (match Names.find_opt identity !definitions with
         |None->definition_order:=List.append !definition_order[identity]
         |Some original->fail(data.original.path^"/semantics/definitions")(same original definition)
           ("Conflicting complete semantic definition: "^identity));
        definitions:=Names.add identity definition !definitions)(items "definitions" data.original.semantics))instances;
    let semantics=set "definitions"(arr(List.map(fun name->find "/modules" "Merged semantic definition"name !definitions)!definition_order))base_semantics in
    let result=context|>set "semantics" semantics|>set "declarations"(arr(List.map fst !combined))|>set "source_map"(arr !spans)in
    let lineage=List.rev !lineage in
    let remap=prefix_remap(List.map(fun(row:lineage)->
      String.sub row.flat_path 8(String.length row.flat_path-8),row.source_path)lineage)"/modules/context"in
    ignore(checked_source remap result);result,lineage
end

let lineage_json(value:lineage)=obj["source_path",str value.source_path;"flat_path",str value.flat_path;
  "instance",(match value.instance with None->Json.Null|Some value->str value);
  "template",(match value.template with None->Json.Null|Some value->B.pin_to_json value);
  "declaration",str value.declaration;"expanded",str value.expanded]
let check ~bundle ~program=
  let budget=B.meter bundle in
  let module Check=Make(struct let budget=budget let limits=B.limits bundle end)in
  Check.fail "/program" (D.kind program=D.Program)"Proposed module elaboration must be an ordinary complete PolicyProgram.";
  let expected,lineage_value=Check.reconstruct bundle in
  Check.scan expected;Check.scan(D.to_json program);
  (match Check.first_difference expected(D.to_json program)with None->()|Some path->
    let row=Check.List.find_opt(fun(row:lineage)->Check.String.equal path row.flat_path ||
      Check.String.starts_with ~prefix:(row.flat_path^"/")path)lineage_value in
    let path,description=match row with None->path,"complete Program"|Some row->
      let suffix=Check.String.sub path(Check.String.length row.flat_path)(Check.String.length path-Check.String.length row.flat_path)in
      let owner=match row.instance,row.template with
        |Some instance,Some template->"instance "^instance^", template "^template.id^" version "^template.version
        |_->"context"in
      row.source_path^suffix,owner^", declaration "^row.declaration^" expanded as "^row.expanded in
    Check.fail path false("Proposed elaboration differs from independent reconstruction at "^description^"."));
  let program_fingerprint=B.hash budget expected in
  let fields=["schema_version",str schema_version;"implementation",str implementation;"relation",str "exact_module_elaboration";
    "bundle_fingerprint",str(B.fingerprint bundle);"program_fingerprint",str program_fingerprint;
    "lineage",arr(List.map lineage_json lineage_value);"behavior",str "unassessed";"empirical",str "unassessed"]in
  let usage work bytes=obj["unit",str "logical_module_work";"charged_work",Json.int work;"scanned_bytes",Json.int bytes]in
  (* Reserve the complete emitted report before exposing any capability. *)
  ignore(B.encode budget(obj(fields@["usage",usage(B.limits bundle).max_work(B.limits bundle).max_bytes])));
  let evidence_value=obj(fields@["usage",usage(B.work budget)(B.bytes budget)])in
  {bundle_value=bundle;program_value=program;evidence_value;lineage_value}
let remap_diagnostic checked(error:Diagnostic.t)=
  let budget=B.meter checked.bundle_value in
  let module Check=Make(struct let budget=budget let limits=B.limits checked.bundle_value end)in
  let rows=Check.List.concat_map(fun(row:lineage)->
    [row.flat_path,row.source_path;
     String.sub row.flat_path 8(String.length row.flat_path-8),row.source_path;
     "/request"^row.flat_path,row.source_path])checked.lineage_value in
  {error with path=Option.map(fun path->
    let normalized=Check.source_path path in
    let mapped=Check.prefix_remap rows "" normalized in
    if String.equal mapped normalized then path else mapped)error.path}

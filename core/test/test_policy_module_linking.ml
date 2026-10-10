open Bioc_wire
module Bundle = Bioc_domain.Policy_module_bundle
module Document = Bioc_domain.Policy_document
module Link = Bioc_checker.Policy_module_linking_check
module Source = Bioc_checker.Policy_check
module Service = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service

let ()=Printexc.register_printer(function
  |Diagnostic.Error d->Some(Printf.sprintf "Diagnostic.Error(%s, %s, %s)" d.code
      (Option.value ~default:"<none>" d.path) d.message)
  |_->None)
let s value=Json.String value
let a values=Json.Array values
let o fields=Json.Object fields
let get key value=Json.field key(Json.object_fields value)
let rows key value=Json.array(get key value)
let text key value=Json.string(get key value)
let rec at path value=match path with []->value|key::rest->at rest(get key value)
let set key item value=o(List.map(fun(name,value)->name,if name=key then item else value)(Json.object_fields value))
let remove key value=o(List.filter(fun(name,_)->name<>key)(Json.object_fields value))
let rec edit path f value=match path with []->f value|key::rest->set key(edit rest f(get key value))value
let append key values=edit[key](fun original->a(Json.array original@values))
let require condition message=if not condition then failwith message
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_artifact ~max_bytes:(8*1024*1024) ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let call handler role operation payload=
  let request:Protocol.request={request_id="module-linking-literal";operation;payload}in
  match handler role request with
  |Protocol.Ok,Some result,[]->result
  |_,_,diagnostics->failwith(operation^": "^String.concat "; "
      (List.map(fun(d:Diagnostic.t)->d.code^": "^d.message)diagnostics))
let controls=ref 0
let rejects ?code ?prefix label action=match action()with
  |_->failwith("Module adversary accepted: "^label)
  |exception Diagnostic.Error diagnostic->
      require(Option.fold ~none:true ~some:((=)diagnostic.code)code)
        ("Module adversary failed at the wrong boundary: "^label^"/"^diagnostic.code);
      require(Option.fold ~none:true ~some:(fun prefix->Option.fold ~none:false
        ~some:(String.starts_with ~prefix)diagnostic.path)prefix)
        ("Module adversary lost its original source path: "^label);
      incr controls
let rejected_service label operation payload=
  let request:Protocol.request={request_id="module-linking-mutant";operation;payload}in
  match Service.handle Protocol.Verify request with
  |Protocol.Error,None,(_::_)->incr controls
  |_->failwith("Module service adversary accepted: "^label)
  |exception Diagnostic.Error _->incr controls
let checked modules program=Link.check ~bundle:(Bundle.of_json modules)
  ~program:(Document.of_json ~path:"/program" program)
let ref_ kind id=o["$type",s "Ref";"id",s id;"kind",s kind]
let type_ kind=o["$type",s "TypeSpec";"kind",s kind;"unit",Json.Null;"entity_kind",Json.Null]
let parameter id value_type value selection=o["$type",s "Parameter";"id",s id;"value_type",value_type;
  "value",value;"lower",Json.Null;"upper",Json.Null;"selection",s selection]
let expr op value_type args reference value scope=o[
  "$type",s "Expr";"op",s op;"value_type",value_type;"args",a args;"ref",reference;
  "value",value;"scope",scope;"contract",Json.Null;"duration",Json.Null;"clock",Json.Null;
  "coverage",Json.Null;"binding",Json.Null]
let truth=expr "literal"(type_ "truth")[] Json.Null(Json.Bool true)Json.Null
let scope=o["$type",s "Scope";"kind",s "executor";"subject",ref_ "Role" "executor"]
let state id=o["$type",s "StateStore";"id",s id;"value_type",type_ "truth";"scope",scope;
  "initial",Json.Bool false;"capacity",Json.int 1;"overflow",s "reject";"lifetime",s "persistent";
  "reset",Json.Null;"inheritance",s "reset";"duration",Json.Null;"contract",Json.Null;"coordination",Json.Null]
let rule id target=o["$type",s "Rule";"id",s id;"executor",ref_ "Role" "executor";
  "on",expr "rising"(type_ "event")[truth]Json.Null Json.Null Json.Null;"when",truth;
  "unknown",s "defer";"effects",a[];"assignments",a[o["$type",s "Assignment";"state",ref_ "StateStore" target;"value",truth]];
  "arbitration",o["$type",s "Arbitration";"mode",s "exclusive";"tie",s "reject";
    "write_conflict",s "reject";"preemption",s "forbidden";"fairness",s "none";"order",a[s id];"contract",Json.Null];
  "unknown_target",Json.Null;"emissions",a[]]
let requirement kind id=o["$type",s "Requirement";"id",s id;"kind",s kind;
  "description",s "Explicit memory source premise and guarantee";"scope",scope;"condition",truth;
  "response",Json.Null;"deadline",Json.Null;"lower",Json.Null;"upper",Json.Null;"horizon",Json.Null;
  "assumptions",a[];"applies_to",a[];"contract",Json.Null;"trigger",Json.Null;"clock",Json.Null]
let span id line=o["$type",s "SourceSpan";"declaration_id",s id;"file",s "memory.py";
  "line",Json.int line;"column",Json.int 0;"pattern",Json.Null]
let port name access declaration=o["name",s name;"access",s access;"declaration",declaration]
let context_binding port kind id=o["port",s port;"target",o["kind",s "context";"reference",ref_ kind id]]
let output_binding port instance output=o["port",s port;"target",o["kind",s "output";"instance",s instance;"port",s output]]
let pin template=o["id",get "id" template;"version",get "version" template;
  "content_fingerprint",s(Canonical.fingerprint template)]
let instance template name bindings assumptions=o["name",s name;"template",pin template;
  "bindings",a bindings;"assumptions",a assumptions]
(* Every semantic template mutation updates the full original pin. These controls
   therefore reach linking rules rather than only stale-fingerprint rejection. *)
let change_template modules id change=
  let original=List.find(fun value->text "id" value=id)(rows "templates" modules)in
  let replacement=change original in
  modules|>edit["templates"](fun values->a(List.map(fun value->if Json.equal value original then replacement else value)(Json.array values)))
    |>edit["instances"](fun values->a(List.map(fun value->if Json.equal(get "template" value)(pin original)
      then set "template"(pin replacement)value else value)(Json.array values)))
let change_instance modules name change=edit["instances"](fun values->a(List.map(fun value->
  if text "name" value=name then change value else value)(Json.array values)))modules
let change_port kind name change=edit[kind](fun values->a(List.map(fun value->
  if text "name" value=name then change value else value)(Json.array values)))
let modules_like base context templates instances=base|>set "context" context|>set "templates"(a templates)|>set "instances"(a instances)
let template_like base id role declarations private_=List.hd(rows "templates" base)
  |>set "id"(s id)|>set "version"(s "1")|>set "semantics"(at["context";"semantics"]base)
  |>set "inputs"(a[port "executor" "context" role])|>set "outputs"(a[])
  |>set "declarations"(a declarations)|>set "private"(a private_)
  |>set "assumptions"(a[])|>set "guarantees"(a[])|>set "source_map"(a[])

let source_only_controls original=
  let role=List.find(fun value->text "$type" value="Role" && text "id" value="executor")
    (rows "declarations"(get "context" original))in
  let context=get "context" original|>set "id"(s "two_memories")|>set "declarations"(a[role])|>set "source_map"(a[])in
  let template=template_like original "memory" role[state "memory";rule "remember" "memory"][ref_ "StateStore" "memory"]
    |>set "source_map"(a[span "memory" 10;span "remember" 11])in
  let bindings=[context_binding "executor" "Role" "executor"]in
  let modules=modules_like original context[template]
    [instance template "left" bindings[];instance template "right" bindings[]]in
  (* The expected expansion is handwritten, not obtained from either linker. *)
  let program=context|>set "declarations"(a[role;state "left/memory";rule "left/remember" "left/memory";
    state "right/memory";rule "right/remember" "right/memory"])
    |>set "source_map"(a[span "left/memory" 10;span "left/remember" 11;span "right/memory" 10;span "right/remember" 11])in
  let linked=checked modules program in
  require(get "behavior"(Link.evidence linked)=s "unassessed" &&
    get "empirical"(Link.evidence linked)=s "unassessed")"Source module linking promoted behavior or biological evidence";
  let source=Source.check(Document.of_json program)in
  require(get "status" source=s "valid")"Independently authored two-store module example is not valid source";
  let negative label changed=rejects ~prefix:"/modules" label(fun()->checked changed program)in
  negative "private state ownership omitted"(change_template modules "memory"(set "private"(a[])));
  negative "private state also exported"(change_template modules "memory"(set "outputs"(a[port "memory" "read"(state "memory")])));
  negative "hidden reference into sibling namespace"(change_template modules "memory"
    (edit["declarations"](fun values->a(List.map(fun value->if text "$type" value="Rule"
      then set "when"(expr "state"(type_ "truth")[](ref_ "StateStore" "right/memory")Json.Null(ref_ "Role" "executor"))value else value)(Json.array values)))));
  negative "arbitration identity escapes local interface"(change_template modules "memory"
    (edit["declarations"](fun values->a(List.map(fun value->if text "$type" value="Rule"
      then edit["arbitration";"order"](fun _->a[s "right/remember"])value else value)(Json.array values)))));
  negative "context source map claims instance declaration"(edit["context";"source_map"](fun _->a[span "left/memory" 1])modules);
  negative "template source map claims external declaration"(change_template modules "memory"(set "source_map"(a[span "executor" 1])));
  rejects ~code:"assignment_type" ~prefix:"/modules/templates/0/declarations/1"
    "native source diagnostic maps back to template declaration"(fun()->checked
      (change_template modules "memory"(edit["declarations"](fun values->a(List.map(fun value->
        if text "$type" value="Rule"then edit["assignments"](fun assignments->a(List.map
          (set "value"(expr "literal"(type_ "integer")[]Json.Null(Json.int 1)Json.Null))(Json.array assignments)))value
        else value)(Json.array values)))))program);
  negative "duplicate instance identity"(edit["instances"](fun values->a(List.hd(Json.array values)::Json.array values))modules);
  negative "external context shadows namespace"(edit["context";"declarations"](fun values->a(Json.array values@[state "left/reserved"]))modules);
  let premise=requirement "assumption" "premise" and guarantee=requirement "safety" "guarantee" in
  let assumed=change_template modules "memory"(fun value->value|>set "assumptions"(a[premise])|>set "guarantees"(a[guarantee]))
    |>edit["instances"](fun values->a(List.map(set "assumptions"(a[premise]))(Json.array values)))in
  let assumed_program=program|>set "declarations"(a[role;state "left/memory";rule "left/remember" "left/memory";
    set "id"(s "left/premise")premise;set "id"(s "left/guarantee")guarantee;
    state "right/memory";rule "right/remember" "right/memory";
    set "id"(s "right/premise")premise;set "id"(s "right/guarantee")guarantee])in
  ignore(checked assumed assumed_program);
  let assessment=Source.check(Document.of_json assumed_program)in
  require(List.mem(get "description" premise)(rows "assumptions" assessment))"Original acknowledged premise was silently discharged";
  negative "missing exact acknowledged premise"(change_instance assumed "left"(set "assumptions"(a[])));
  negative "changed acknowledged premise body"(change_instance assumed "left"
    (set "assumptions"(a[set "description"(s "Different premise")premise])));
  negative "guarantee recast as an assumption"(change_template assumed "memory"(set "guarantees"(a[premise])));
  let writer=template_like original "writer" role[rule "write" "memory"][]
    |>append "inputs"[port "memory" "write"(state "memory")]in
  let shared_context=context|>set "declarations"(a[role;state "shared"])in
  let write_bindings=bindings@[context_binding "memory" "StateStore" "shared"]in
  let writing=modules_like original shared_context[writer]
    [instance writer "first" write_bindings[];instance writer "second" write_bindings[]]in
  negative "two instance owners write one state" writing;
  negative "read capability does not permit assignments"(change_template writing "writer"(change_port "inputs" "memory"(set "access"(s "read"))));
  let reset_state id=state id|>set "reset" truth in
  let resetting_writer=writer|>change_port "inputs" "memory"(set "declaration"(reset_state "memory"))in
  negative "context reset is an independent state writer"(modules_like original
    (context|>set "declarations"(a[role;reset_state "shared"]))[resetting_writer]
    [instance resetting_writer "writer" write_bindings[]]);
  let alias=writer|>append "inputs"[port "other" "write"(state "other")]
    |>edit["declarations"](fun values->a(List.map(append "assignments"
      [o["$type",s "Assignment";"state",ref_ "StateStore" "other";"value",truth]])(Json.array values)))in
  negative "distinct writable formals alias one state"(modules_like original shared_context[alias]
    [instance alias "writer"(write_bindings@[context_binding "other" "StateStore" "shared"])[]]);
  let exported=template|>set "private"(a[])|>set "outputs"(a[port "memory" "read"(state "memory")])in
  let hidden=state "hidden"in
  let leaking=state "memory"|>set "reset"
    (expr "state"(type_ "truth")[](ref_ "StateStore" "hidden")Json.Null(ref_ "Role" "executor"))in
  let leaking_template=exported|>set "declarations"(a[leaking;rule "remember" "memory";hidden])
    |>set "outputs"(a[port "memory" "read" leaking])|>set "private"(a[ref_ "StateStore" "hidden"])in
  negative "private dependency escapes within complete output signature"(modules_like original context[leaking_template]
    [instance leaking_template "producer" bindings[]]);
  let connecting=modules_like original context[exported;writer]
    [instance exported "producer" bindings[];instance writer "consumer"(bindings@[output_binding "memory" "producer" "memory"])[]]in
  negative "read output does not grant write input" connecting;
  let cyclic=exported|>append "inputs"[port "incoming" "read"(state "incoming")]in
  negative "output binding cycle"(modules_like original context[cyclic]
    [instance cyclic "first"(bindings@[output_binding "incoming" "second" "memory"])[];
     instance cyclic "second"(bindings@[output_binding "incoming" "first" "memory"])[]]);
  (* Nominal units and free text are not declaration references. Their exact
     original strings survive expansion even when they equal private names. *)
  let unit=o["$type",s "Unit";"id",s "memory";"dimension",s "count";"quantity_kind",s "count";
    "scale",s "1";"reference",s "memory"]in
  let quantity=o["$type",s "Quantity";"amount",s "1";"unit",unit]in
  let quantity_type=type_ "quantity"|>set "unit" unit in
  let nominal=parameter "nominal" quantity_type quantity "fixed"in
  let described=requirement "safety" "description"|>set "description"(s "memory remember executor")
    |>set "assumptions"(a[s "memory remains an explicit textual premise"])in
  let nominal_template=template|>append "declarations"[nominal]|>set "guarantees"(a[described])in
  let nominal_modules=modules_like original context[nominal_template][instance nominal_template "left" bindings[]]in
  let nominal_program=context|>set "declarations"(a[role;state "left/memory";rule "left/remember" "left/memory";
    set "id"(s "left/nominal")nominal;set "id"(s "left/description")described])
    |>set "source_map"(a[span "left/memory" 10;span "left/remember" 11])in
  ignore(checked nominal_modules nominal_program);
  let formal=parameter "memory"(type_ "truth")Json.Null "design"in
  let definition=o["$type",s "SemanticDefinition";"id",s "lexical";"version",s "1";
    "category",s "operation";"meaning",s "Lexical formal shares a local state name";"parameters",a[formal];
    "result",type_ "truth";"clauses",a[o["$type",s "ContractClause";"kind",s "precondition";
      "description",s "Lexical read";"expression",expr "parameter"(type_ "truth")[](ref_ "Parameter" "memory")Json.Null Json.Null]];
    "assumptions",a[];"executor_kind",Json.Null;"subject_kind",Json.Null]in
  let lexical=change_template modules "memory"(edit["semantics";"definitions"](fun values->a(Json.array values@[definition])))in
  let lexical_program=edit["semantics";"definitions"](fun values->a(Json.array values@[definition]))program in
  ignore(checked lexical lexical_program);
  negative "semantic definition captures program state"(change_template lexical "memory"
    (edit["semantics";"definitions"](fun values->a(List.map(fun value->if text "id" value="lexical"then
      edit["clauses"](fun clauses->a(List.map(set "expression"
        (expr "state"(type_ "truth")[](ref_ "StateStore" "memory")Json.Null Json.Null))(Json.array clauses)))value
      else value)(Json.array values)))));
  let context_definition=List.hd(rows "definitions"(get "semantics" context))in
  negative "same definition identity has a changed complete body"(change_template modules "memory"
    (edit["semantics";"definitions"](fun values->a(List.map(fun value->if get "id" value=get "id" context_definition
      then set "meaning"(s "Different semantic meaning under the same identity")value else value)(Json.array values)))));
  List.iter(fun name->rejects ~code:"policy_module_limit" ("lowered "^name)(fun()->
    checked(edit["limits";name](fun _->Json.int 1)modules)program))
    ["max_work";"max_bytes";"max_depth";"max_instances";"max_declarations"];
  rejects ~code:"policy_module_limit" "lowered port bound"(fun()->checked
    (edit["limits";"max_ports"](fun _->Json.int 1)writing)program);
  let rec cyclic_json=Json.Array[cyclic_json]in
  rejects ~code:"policy_module_limit" "cyclic native data before canonicalization"(fun()->Bundle.of_json cyclic_json);
  (* Source locations are not declarations: a lowered declaration allowance
     must still admit two independent locations for its one expanded value. *)
  let constant=parameter "constant"(type_ "integer")(Json.int 1)"fixed"in
  let tiny_context=context|>set "id"(s "tiny")|>set "declarations"(a[])in
  let tiny=template_like original "tiny" role[constant][]|>set "inputs"(a[])
    |>set "source_map"(a[span "constant" 1;span "constant" 2])in
  let tiny_modules=modules_like original tiny_context[tiny][instance tiny "one"[][]]
    |>edit["limits";"max_declarations"](fun _->Json.int 1)in
  let tiny_program=tiny_context|>set "declarations"(a[set "id"(s "one/constant")constant])
    |>set "source_map"(a[span "one/constant" 1;span "one/constant" 2])in
  ignore(checked tiny_modules tiny_program);
  modules,program

let fixture_controls modules program request limits=
  let negative label altered=rejects ~prefix:"/modules" label(fun()->checked altered program)in
  negative "read effect input cannot request effects"(change_template modules "controller"
    (change_port "inputs" "response"(set "access"(s "read"))));
  negative "complete lifecycle mismatch across connected ports"(change_template modules "controller"
    (change_port "inputs" "response"(edit["declaration";"lifecycle";"timeout";"amount"](fun _->s "3"))));
  negative "complete nominal clock unit mismatch"(change_template modules "controller"
    (change_port "inputs" "clock"(edit["declaration";"resolution";"unit";"scale"](fun _->s "2"))));
  negative "output signature differs from original declaration"(change_template modules "sensor"
    (change_port "outputs" "condition"(edit["declaration";"freshness";"amount"](fun _->s "2"))));
  negative "private Ref has undeclared wire fields"(change_template modules "controller"
    (edit["private"](fun values->a(List.map(fun value->o(("trusted",Json.Bool true)::Json.object_fields value))(Json.array values)))));
  negative "raw binding bypasses declared exported interface"(change_instance modules "control"
    (edit["bindings"](fun values->a(List.map(fun value->if text "port" value="response"
      then context_binding "response" "Effect" "actuator/response" else value)(Json.array values)))));
  negative "output binding names undeclared port"(change_instance modules "control"
    (edit["bindings"](fun values->a(List.map(fun value->if text "port" value="response"
      then output_binding "response" "actuator" "missing" else value)(Json.array values)))));
  let subject=List.find(fun value->text "$type" value="Subject")(rows "declarations"(get "context" modules))in
  let other=subject|>set "id"(s "other_target")|>set "identity"(s "stable")|>set "encounter" Json.Null in
  negative "source-valid wrong nominal subject binding"(modules
    |>edit["context";"declarations"](fun values->a(Json.array values@[other]))
    |>fun value->change_instance value "control"(edit["bindings"](fun values->a(List.map(fun value->
      if text "port" value="subject"then context_binding "subject" "Subject" "other_target"else value)(Json.array values)))));
  let dropped=change_template modules "effector"(fun value->value|>set "guarantees"(a[])
    |>edit["source_map"](fun values->a(List.filter(fun value->text "declaration_id" value<>"response_initiation")(Json.array values))))in
  rejects ~code:"policy_module_linking" "complete original guarantee missing from expansion"(fun()->checked dropped program);
  let unused=List.hd(rows "templates" modules)|>set "id"(s "unused")in
  negative "unused original template"(append "templates"[unused]modules);
  let changed_map values=a(List.mapi(fun i value->if i=0 then set "line"(Json.int 99)value else value)(Json.array values))in
  let mapped=edit["context";"source_map"]changed_map modules and mapped_program=edit["source_map"]changed_map program in
  let linked=checked mapped mapped_program in
  require(Document.fingerprint(Document.of_json mapped_program)=Document.fingerprint(Document.of_json program) &&
    get "program_fingerprint"(Link.evidence linked)<>s(Canonical.fingerprint program))
    "Source maps were either treated as behavior or omitted from complete linkage identity";
  (* An additional ordinary fixed parameter is valid source and valid module
     linking, but the current finite realization family admits exactly one. *)
  let extra=parameter "extra"(type_ "integer")(Json.int 1)"fixed"in
  let extended=edit["context";"declarations"](fun values->a(Json.array values@[extra]))modules in
  let context_count=List.length(rows "declarations"(get "context" modules))in
  let extended_program=edit["declarations"](fun values->a(List.concat_map(fun(i,value)->
    if i=context_count then[extra;value]else[value])(List.mapi(fun i value->i,value)(Json.array values))))program in
  ignore(checked extended extended_program);
  rejects ~code:"policy_realization_finite_machine" "valid linked source remains outside finite executable profile"(fun()->
    let request=edit["implementation_request";"document";"program"](fun _->extended_program)request in
    Bioc_producer_service.Policy_module_material_producer.compile(o["modules",extended;"request",request;"limits",limits]));
  mapped,mapped_program

let ()=
  require(Array.length Sys.argv=2)"Expected independent module linking originals";
  let fixture=read Sys.argv.(1)in
  let modules=get "modules" fixture and program=get "program" fixture
  and request=get "request" fixture and limits=get "limits" fixture and expected=get "expected" fixture in
  require(Json.equal program(get "program" expected) &&
    Json.equal program(at["implementation_request";"document";"program"]request))
    "Expected linked source differs from independently authored material originals";
  let linked=checked modules program in
  let linkage=Link.evidence linked in
  require(get "relation" linkage=s "exact_module_elaboration" && get "behavior" linkage=s "unassessed" &&
    get "empirical" linkage=s "unassessed" && get "bundle_fingerprint" linkage=s(Canonical.fingerprint modules) &&
    get "program_fingerprint" linkage=s(Canonical.fingerprint program))
    "Opaque linkage lost complete original identity or widened its claim";
  require(get "unit"(get "usage" linkage)=s "logical_module_work" &&
    Z.sign(Json.integer(at["usage";"charged_work"]linkage))>0 &&
    Z.compare(Json.integer(at["usage";"scanned_bytes"]linkage))(Z.of_int(String.length(Canonical.encode modules)))>0 &&
    Z.leq(Json.integer(at["usage";"charged_work"]linkage))(Json.integer(at["limits";"max_work"]modules)) &&
    Z.leq(Json.integer(at["usage";"scanned_bytes"]linkage))(Json.integer(at["limits";"max_bytes"]modules)))
    "Module report failed to account for bounded repeated inspection and emitted evidence";
  require(List.length(rows "lineage" linkage)=List.length(rows "declarations" program))
    "Linkage does not account for every original context and expanded declaration";
  let standalone=call Service.handle Protocol.Verify "check-policy-module-linking"(o["modules",modules;"program",program])in
  require(Json.equal(get "linkage" standalone)linkage &&
    get "invocation_fingerprint" standalone=s(Canonical.fingerprint(o["modules",modules;"program",program])))
    "Standalone module wrapper replaced original invocation or fresh capability evidence";
  let replay=call Service.handle Protocol.Verify "replay-policy-module-linking"
    (o["modules",modules;"program",program;"report",standalone])in
  require(Json.equal replay standalone)"Fresh module replay changed exact checked evidence";
  ignore(source_only_controls modules);
  let mapped,mapped_program=fixture_controls modules program request limits in
  rejected_service "source map changes require fresh linkage evidence" "replay-policy-module-linking"
    (o["modules",mapped;"program",mapped_program;"report",standalone]);
  List.iter(fun row->
    let original=text "source_path" row and flat=text "flat_path" row in
    let diagnostic:Diagnostic.t={code="native_probe";message="Exact downstream source location";path=Some(flat^"/id")}in
    require((Link.remap_diagnostic linked diagnostic).path=Some(original^"/id"))
      "Fresh lineage failed to relocate a downstream declaration diagnostic";
    List.iter(fun prefix->let path=prefix^flat^"/id"in
      require((Link.remap_diagnostic linked{diagnostic with path=Some path}).path=Some(original^"/id"))
        "Fresh lineage failed to normalize a supported downstream document path")["/document";"/request"])
    (rows "lineage" linkage);
  let unmatched:Diagnostic.t={code="native_probe";message="No declaration mapping";path=Some "/document/program/declarations/9999/id"}in
  require(Link.remap_diagnostic linked unmatched=unmatched)"Lineage captured an unrelated declaration-path prefix";
  List.iter(fun field->rejects ~prefix:"/modules" ("missing bundle field "^field)
    (fun()->Bundle.of_json(remove field modules)))
    ["schema_version";"profile";"context";"templates";"instances";"limits"];
  rejects ~prefix:"/modules" "unknown bundle field"(fun()->Bundle.of_json(o(("accepted",Json.Bool true)::Json.object_fields modules)));
  rejects "unknown policy source record"(fun()->checked(edit["context";"declarations"]
    (fun values->a(o["$type",s "OpaqueNativePass"]::Json.array values))modules)program);
  rejects ~code:"policy_module_linking" "proposed flattened source changed"(fun()->checked modules(set "id"(s "changed_program")program));
  rejects ~code:"policy_module_linking" ~prefix:"/modules/templates/1/declarations/1/destination"
    "proposed transition mismatch identifies original owning template"(fun()->checked modules
      (edit["declarations"](fun values->a(List.map(fun value->if text "id" value="control/launch"
        then set "destination"(s "ready")value else value)(Json.array values)))program));
  rejected_service "saved linkage cannot replace changed original source" "replay-policy-module-linking"
    (o["modules",modules;"program",set "id"(s "changed_program")program;"report",standalone]);
  let produced=call Producer.handle Protocol.Core "compile-policy-module-material"
    (o["modules",modules;"request",request;"limits",limits])in
  let material=get "material" produced in
  let candidate=get "candidate" material in
  let invocation=o["modules",modules;"request",request;"candidate",candidate;"limits",limits]in
  let verified=call Service.handle Protocol.Verify "check-policy-module-material" invocation in
  require(Json.equal produced verified && Json.equal(get "modules" verified)modules &&
    Json.equal(get "linkage" verified)linkage && at["material";"report";"status"]verified=s "checked_component_material")
    "Complete module material did not fresh-check the exact native link and original material";
  let ordinary=call Service.handle Protocol.Verify "check-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",limits])in
  require(Json.equal ordinary material)"Module envelope changed the existing raw material report";
  let replayed=call Service.handle Protocol.Verify "replay-policy-module-material"
    (o(("report",verified)::Json.object_fields invocation))in
  require(Json.equal replayed verified)"Fresh linked material replay changed complete originals";
  let exported=call Service.handle Protocol.Verify "export-policy-module-material" invocation in
  let artifact=get "artifact" exported in
  let child=at["material";"artifact"]exported in
  let manifest=get "manifest" artifact in
  let exact_fasta=">rna_0001 alphabet=RNA\n"^text "sequence" expected^"\n"in
  require(get "fasta" artifact=get "fasta" child && get "fasta_sha256" artifact=get "fasta_sha256" child &&
    get "fasta" artifact=s exact_fasta && get "fasta_sha256" artifact=s(Canonical.sha256 exact_fasta) &&
    get "manifest_sha256" artifact=s(Canonical.fingerprint manifest) &&
    Json.equal(get "modules" manifest)modules && Json.equal(get "linkage" manifest)linkage &&
    Json.equal(get "material_manifest" manifest)(get "manifest" child) &&
    get "material_manifest_sha256" manifest=get "manifest_sha256" child &&
    get "empirical" manifest=s "unassessed")"Linked export lost exact paired payload or original module authority";
  let molecules=rows "molecules"(at["construction";"inventory"]candidate)in
  require(List.length molecules=1 && get "sequence"(List.hd molecules)=get "sequence" expected &&
    Json.equal(List.hd molecules)(get "molecule" expected))"Module realization differs from independent exact RNA oracle";
  let changed=edit["candidate";"construction";"inventory";"molecules"](fun values->a(List.map(fun value->
    let sequence=text "sequence" value in set "sequence"(s("A"^String.sub sequence 1(String.length sequence-1)))value)(Json.array values)))invocation in
  rejected_service "exact RNA tamper" "export-policy-module-material" changed;
  let incomplete=call Service.handle Protocol.Verify "check-policy-module-material"
    (edit["limits";"max_step_work"](fun _->Json.int 1)invocation)in
  require(get "artifact" incomplete=Json.Null && at["material";"artifact"]incomplete=Json.Null &&
    at["material";"report";"status"]incomplete=s "not_accepted")"Checked linkage minted incomplete material acceptance";
  incr controls;
  rejected_service "saved module material pass substitutes for incomplete fresh checking" "replay-policy-module-material"
    (o(("report",verified)::Json.object_fields(edit["limits";"max_step_work"](fun _->Json.int 1)invocation)));
  require(!controls=54)"Module semantic rejection census is incomplete";
  Printf.printf "policy_module_linking: independent elaboration, complete linked material/export, %d rejection controls\n" !controls

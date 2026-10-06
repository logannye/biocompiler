open Bioc_wire
module A = Bioc_checker.Policy_realization_admission
module I = Bioc_domain.Policy_implementation
module B = Bioc_domain.Policy_implementation_binding
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module R = Bioc_domain.Policy_realization_request
module F = Bioc_domain.Policy_operating_domain
module P = Bioc_domain.Pinned_identity

type proposal = { implementation:I.t; binding:B.t }
let get=O.get
let text=O.text
let list=O.list
let s value=Json.String value
let o value=Json.Object value
let a value=Json.Array value
let supported condition message=Diagnostic.require condition "policy_implementation_lowering_unsupported" message
let one label=function [value]->value|_->Diagnostic.fail "policy_implementation_lowering_unsupported"
  ("Initial implementation producer requires one "^label^".")
let endpoint node port=o["node",s node;"port",s port]
let reference kind id=o["$type",s "Ref";"kind",s kind;"id",s id]
let absent keys value=List.iter(fun key->supported(get key value=Json.Null)
  ("Source "^key^" requires an unsupported interpretation."))keys
let type_is kind value=supported(text "kind" value=kind && get "unit" value=Json.Null && get "entity_kind" value=Json.Null)
  "Only exact truth/event/product types are supported by the initial producer."
let truth=function O.True->I.True|O.False->I.False|O.Unknown->I.Unknown
let primitive_equal expected actual=match expected,actual with
  |I.Attempt_bank wanted,I.Attempt_bank supplied->wanted.timeout_ticks=supplied.timeout_ticks &&
      wanted.authorization=supplied.authorization && wanted.on_unknown=supplied.on_unknown && supplied.capacity>=wanted.capacity
  |_->expected=actual
let model_order (left:I.model)(right:I.model)=
  let capacity=function I.Attempt_bank value->value.capacity|_->0 in
  let by_capacity=compare(capacity left.primitive)(capacity right.primitive)in
  if by_capacity<>0 then by_capacity else String.compare(P.fingerprint left.identity)(P.fingerprint right.identity)

let lower ~admitted ~library =
  let request=A.request admitted and behavior=A.behavior admitted in
  Diagnostic.require(I.library_digest library=I.library_digest(R.implementation_library request))
    "policy_implementation_lowering_authority" "Supplied library differs from independently admitted original authority.";
  let bridge=one "original catalog membership bridge"(R.catalog_bindings request)
  and executor=one "executor role" behavior.roles and encounter=one "encounter declaration" behavior.encounters
  and subject=one "encounter subject" behavior.subjects and clock=one "clock" behavior.clocks
  and observed=one "truth observation" behavior.observations and operation=one "effect" behavior.effects
  and product=one "fixed product parameter" behavior.parameters in
  let document=R.document request and domain=F.specification(A.operating_domain admitted)in
  let declarations=D.declarations document in
  let declaration identity=List.find(fun(d:D.declaration)->d.id=identity)declarations in
  let source identity=(declaration identity).value and path identity=(declaration identity).path in
  supported(behavior.machines=[] && behavior.transitions=[] && List.mem(List.length behavior.rules)[1;2] &&
    List.mem(List.length behavior.stores)[1;2])"Initial producer supports one/two rules and encounter truth stores only.";
  supported(encounter.executor=executor.role_id && encounter.target=subject.subject_id && encounter.termination="explicit_event" &&
    subject.encounter=Some encounter.encounter_id && subject.executor=Some executor.role_id)
    "Source requires a different encounter identity or lifetime profile.";
  absent["domain"](source subject.subject_id);
  supported(clock.clock_id=domain.clock && executor.role_id=domain.executor_role &&
    List.for_all(fun(slot:F.encounter)->slot.declaration=encounter.encounter_id)domain.encounters)
    "Source and domain require distinct executor/encounter/clock bindings.";
  supported(text "simultaneous"(source clock.clock_id)="atomic_batch" &&
    List.mem(text "basis"(source clock.clock_id))["logical";"availability"])
    "Source requires different simultaneous-event or clock phases.";
  supported(observed.value_type=O.Truth_type && observed.observer=executor.role_id && observed.subject=subject.subject_id &&
    observed.clock=clock.clock_id && observed.coverage="event" && observed.coherence="frame")
    "Source observation requires a different evidence profile.";
  type_is "truth"(get "value_type"(source observed.observation_id));
  supported(Json.equal bridge.operation(get "contract"(source operation.effect_id)))
    "The original catalog bridge does not name this source effect operation.";
  supported(operation.executor=executor.role_id && operation.subject=subject.subject_id && operation.lifecycle.on_loss="continue")
    "Source effect changes the executor, recipient or cancellation profile.";
  let product_source=source product.parameter_id in
  supported(text "selection" product_source="fixed")"Product is not a fixed parameter.";
  absent["lower";"upper"]product_source;type_is "text"(get "value_type" product_source);
  let product_symbol=match product.value with O.Text value->value|_->Diagnostic.fail "policy_implementation_lowering_unsupported" "Product parameter is not text."in
  let argument=one "product argument"(list "parameters"(source operation.effect_id))in
  supported(text "name" argument="product" && text "op"(get "value" argument)="parameter")
    "Effect does not use the supported fixed product argument.";
  let initiation=one "effect-initiating rule"(List.filter(fun(rule:O.rule)->rule.effects<>[])behavior.rules)in
  supported(initiation.effects=[operation.effect_id])"Effect initiator has extra or different requested operations.";
  let ticks duration=let exact=Q.div duration clock.resolution in
    supported(Q.sign exact>0 && Z.equal(Q.den exact)Z.one && Z.compare(Q.num exact)(Z.of_int 10000)<=0)
      "Source duration is outside positive bounded clock ticks.";Z.to_int(Q.num exact)in
  let timeout=match operation.lifecycle.timeout with Some duration->ticks duration|None->
    Diagnostic.fail "policy_implementation_lowering_unsupported" "Effect has no finite source timeout."in
  let authorization=match operation.lifecycle.authorization with "continuous"->I.Continuous|"initiation"->I.At_initiation
    |_->Diagnostic.fail "policy_implementation_lowering_unsupported" "Unsupported authorization lifetime."in
  let on_unknown=match operation.lifecycle.on_unknown with "defer"->I.Defer|"continue"->I.Continue
    |_->Diagnostic.fail "policy_implementation_lowering_unsupported" "Unsupported authorization uncertainty response."in
  let writers=List.concat_map(fun(rule:O.rule)->List.mapi(fun index(assignment:O.assignment)->
    rule.rule_id,index,assignment.state)rule.assignments)behavior.rules in
  List.iter(fun(store:O.state_store)->let raw=source store.state_id in
    supported(store.value_type=O.Truth_type && store.scope=O.Encounter encounter.encounter_id &&
      store.lifetime="encounter" && store.reset=None && store.capacity>=List.length domain.encounters &&
      text "overflow" raw="reject" && text "inheritance" raw="not_applicable")
      "Source storage needs a different scope, capacity, reset or inheritance implementation.";
    absent["duration";"contract";"coordination"]raw;type_is "truth"(get "value_type" raw);
    supported(List.exists(fun(_,_,id)->id=store.state_id)writers)"Unwritten stores are outside the initial producer family.")behavior.stores;
  List.iter(fun(rule:O.rule)->
    supported(rule.executor=executor.role_id && rule.on.op="rising" && rule.arbitration.mode="exclusive" &&
      rule.arbitration.tie="reject" && rule.arbitration.write_conflict="reject" && rule.arbitration.order=[])
      "Source rules need a different activation or arbitration profile.";
    let destinations=List.map(fun(assignment:O.assignment)->assignment.state)rule.assignments in
    supported(List.length destinations=List.length(List.sort_uniq String.compare destinations))
      "Repeated state destinations in one atomic source action are unsupported.")behavior.rules;
  let slots=List.length domain.encounters in
  let layouts=I.models library|>List.filter_map(fun(model:I.model)->match model.replication with
    |I.Encounter_slots value when value.slots=slots->Some value.layout_id|_->None)|>List.sort_uniq String.compare in
  let build layout_id=
    let replication=I.Encounter_slots{layout_id;slots}in
    let selected=ref [] and wires=ref [] and occurrences=ref [] and proposal_rules=ref [] and memo=Hashtbl.create 32
    and edges=ref [] and parameter_outputs=ref [] and next_expression=ref 0 in
    let model primitive=
      let matching scope=List.filter(fun(model:I.model)->model.replication=scope && primitive_equal primitive model.primitive)(I.models library)
        |>List.sort model_order in
      let choices=match primitive with
        |I.Truth_constant _|I.Product_constant _->let immutable=matching I.Executor in if immutable=[]then matching replication else immutable
        |_->matching replication in
      let value=match choices with value::_->value|[]->Diagnostic.fail "policy_implementation_lowering_missing_model"
        ("No authorized supplied model matches "^I.primitive_name primitive^" in layout "^layout_id^".")in
      A.require_model admitted ~entry_id:bridge.entry_id value.identity;value in
    let allocate id primitive=let chosen=model primitive in
      Diagnostic.require(List.length !selected<256)"policy_implementation_lowering_resource"
        "Produced graph exceeds the closed primitive-node bound.";
      selected:= !selected@[id,chosen];id in
    let connect from destination=
      Diagnostic.require(List.length !wires<2048)"policy_implementation_lowering_resource"
        "Produced graph exceeds the closed wire bound.";
      wires:= !wires@[o["producer",from;"consumer",destination]]in
    let out id port=endpoint id port in
    let exports id=let selected_model=List.assoc id !selected in
      I.ports selected_model.primitive|>List.filter_map(fun(port:I.port)->if port.direction=I.Output then Some(out id port.port_id)else None)in
    let occurrence source_path role disposition targets=
      Diagnostic.require(List.length !occurrences<2048)"policy_implementation_lowering_resource"
        "Produced correspondence ledger exceeds the closed occurrence bound.";
      occurrences:=o["source_path",s source_path;"role",s role;"disposition",s disposition;"targets",a targets]::!occurrences in
    let observation_node=allocate "observation/0"(I.Evidence_bank{freshness_ticks=ticks observed.freshness})in
    let state_nodes=List.mapi(fun index(store:O.state_store)->
      let initial=match store.initial with O.Truth value->truth value|_->Diagnostic.fail "policy_implementation_lowering_unsupported" "Non-truth store initial value."in
      let count=List.length(List.filter(fun(_,_,id)->id=store.state_id)writers)in
      let id=allocate("state/"^string_of_int index)(I.Truth_register{initial;writers=count})in store.state_id,id)behavior.stores in
    let attempt_node=allocate "attempt/0"(I.Attempt_bank{capacity=domain.logical_limits.max_source_attempts;timeout_ticks=timeout;authorization;on_unknown})in
    let arbiter=allocate "arbitration/0"(I.Exclusive_arbiter(List.length behavior.rules))in
    let expression_node primitive=let ordinal= !next_expression in incr next_expression;
      allocate("expression/"^string_of_int ordinal)primitive in
    let rec emit role location raw=
      absent["contract";"duration";"clock";"coverage";"binding"]raw;
      let expression=O.expression_of_json raw and args=list "args" raw in
      let pure_shape ()=absent["ref";"scope";"value"]raw in
      let key=Canonical.encode raw in
      let children=List.mapi(fun index value->emit role(location^"/args/"^string_of_int index)value)args in
      let new_output primitive port input_ports=
        match Hashtbl.find_opt memo key with
        |Some output->output
        |None->let node=expression_node primitive in
            List.iter2(fun from port->connect from(out node port))children input_ports;
            let result=out node port in Hashtbl.add memo key result;result in
      let result=match expression.op with
        |"observe"->type_is "truth"(get "value_type" raw);
            supported(args=[] && get "value" raw=Json.Null &&
              Json.equal(get "ref" raw)(reference "Observation" observed.observation_id) &&
              Json.equal(get "scope" raw)(reference "Subject" subject.subject_id))"Observation expression changes source evidence identity.";
            out observation_node "value"
        |"state"->type_is "truth"(get "value_type" raw);
            let identity=O.ref_id(get "ref" raw)in
            supported(args=[] && get "value" raw=Json.Null && List.mem_assoc identity state_nodes &&
              Json.equal(get "ref" raw)(reference "StateStore" identity) &&
              Json.equal(get "scope" raw)(reference "Encounter" encounter.encounter_id))"State expression changes source encounter scope.";
            out(List.assoc identity state_nodes)"value"
        |"literal"->type_is "truth"(get "value_type" raw);absent["ref";"scope"]raw;
            supported(args=[])"Literal has unexpected operands.";
            let value=match expression.value with Some(O.Truth value)->truth value|_->
              Diagnostic.fail "policy_implementation_lowering_unsupported" "Only truth literals can drive truth wires."in
            new_output(I.Truth_constant value)"out"[]
        |"parameter"->type_is "text"(get "value_type" raw);absent["scope";"value"]raw;
            supported(args=[] && Json.equal(get "ref" raw)(reference "Parameter" product.parameter_id))
              "Effect parameter does not name the original fixed product.";
            let output=new_output(I.Product_constant product_symbol)"out"[]in
            if not(List.exists(Json.equal output)!parameter_outputs)then parameter_outputs:= !parameter_outputs@[output];output
        |"not"->type_is "truth"(get "value_type" raw);pure_shape();supported(List.length args=1)"Negation arity changed.";
            new_output I.Truth_not "out"["in"]
        |"all"|"any"->type_is "truth"(get "value_type" raw);pure_shape();
            supported(args<>[] && List.length args<=64)"Truth conjunction/disjunction arity is outside the primitive bound.";
            let primitive=if expression.op="all"then I.Truth_all(List.length args)else I.Truth_any(List.length args)in
            new_output primitive "out"(List.mapi(fun index _->"in"^string_of_int index)args)
        |"rising"->type_is "event"(get "value_type" raw);pure_shape();supported(List.length args=1)"Rising arity changed.";
            let rec evidence value=List.mem(text "op" value)["observe";"literal";"not";"all";"any"] && List.for_all evidence(list "args" value)in
            let rec has_observation value=text "op" value="observe" || List.exists has_observation(list "args" value)in
            supported(evidence(List.hd args) && has_observation(List.hd args))"Rising must use observed truth-only evidence once per tick.";
            let output=new_output I.Observed_rising "events"["in"]in
            if not(List.mem key !edges)then edges:= !edges@[key];output
        |_->Diagnostic.fail "policy_implementation_lowering_unsupported" "Control expression lacks an initial primitive interpretation."in
      occurrence location role(if List.mem expression.op["literal";"parameter"]then "constant"else "executable")[result];result in
    let commits=List.mapi(fun rule_index(rule:O.rule)->
      let prefix="rule/"^string_of_int rule_index and raw=source rule.rule_id and location=path rule.rule_id in
      let on=emit "predicate"(location^"/on")(get "on" raw)in
      let guard=emit "predicate"(location^"/when")(get "when" raw)in
      let gate=allocate(prefix^"/gate")I.Activation_gate in
      let commit=allocate(prefix^"/commit")(I.Atomic_commit{writes=List.length rule.assignments;requests=List.length rule.effects})in
      connect on(out gate "on");connect guard(out gate "guard");
      connect(out gate "candidate")(out arbiter("in"^string_of_int rule_index));
      connect(out arbiter("out"^string_of_int rule_index))(out commit "grant");
      List.iteri(fun assignment_index(assignment:O.assignment)->
        let row=List.nth(list "assignments" raw)assignment_index in
        let assignment_path=location^"/assignments/"^string_of_int assignment_index in
        let value=emit "state_write"(assignment_path^"/value")(get "value" row)in
        connect value(out commit("value"^string_of_int assignment_index));
        let targets=List.filter(fun(_,_,id)->id=assignment.state)writers in
        let rec position count=function
          |(id,index,_)::_ when id=rule.rule_id && index=assignment_index->count
          |_::rest->position(count+1)rest|[]->assert false in
        connect(out commit("write"^string_of_int assignment_index))
          (out(List.assoc assignment.state state_nodes)("write"^string_of_int(position 0 targets)));
        occurrence assignment_path "state_write" "executable"[out commit("write"^string_of_int assignment_index)])rule.assignments;
      if rule.effects<>[]then(
        let product_output=emit "effect_parameter"(path operation.effect_id^"/parameters/0/value")(get "value" argument)in
        connect product_output(out commit "product0");connect(out commit "request0")(out attempt_node "request");
        connect guard(out attempt_node "authorization"));
      occurrence location "declaration" "executable"([out gate "candidate";out arbiter("out"^string_of_int rule_index)]@exports commit);
      occurrence(location^"/arbitration")"declaration" "executable"[out arbiter("out"^string_of_int rule_index)];
      proposal_rules:= !proposal_rules@[o["source",s rule.rule_id;"gate",s gate;"arbiter",s arbiter;"lane",Json.int rule_index;"commit",s commit]];
      commit)behavior.rules in
    let rec obligations location value=match value with
      |Json.Object fields->
          (match List.assoc_opt "$type" fields with Some(Json.String "Expr")->
            supported(text "op" value<>"rising" || List.mem(Canonical.encode value)!edges)
              "A requirement introduces additional rising-event memory absent from control rules.";
            occurrence location "requirement" "obligation"[]|_->());
          List.iter(fun(key,value)->obligations(location^"/"^key)value)fields
      |Json.Array values->List.iteri(fun index value->obligations(location^"/"^string_of_int index)value)values|_->()in
    List.iter(fun(declaration:D.declaration)->let location=declaration.path in match declaration.kind with
      |D.Role|D.Subject|D.Encounter->occurrence location "declaration" "retained_metadata"[]
      |D.Clock->occurrence location "clock" "retained_metadata"[]
      |D.Observation->occurrence location "declaration" "executable"(exports observation_node)
      |D.State_store->occurrence location "declaration" "executable"[out(List.assoc declaration.id state_nodes)"value"]
      |D.Parameter->occurrence location "effect_parameter" "constant" !parameter_outputs
      |D.Effect->occurrence location "lifecycle" "executable"(exports attempt_node);
          occurrence(location^"/lifecycle")"lifecycle" "executable"(exports attempt_node)
      |D.Rule->()
      |D.Requirement->occurrence location "requirement" "obligation"[];obligations location declaration.value
      |_->Diagnostic.fail "policy_implementation_lowering_unsupported" "Declaration has no interpretation in the initial graph family.")declarations;
    let authority=o["source_artifact_digest",s(D.artifact_digest document);"descriptors_digest",s(O.descriptors_digest(R.definitions request));
      "domain_digest",s(F.digest(R.operating_domain request));"implementation_catalog_digest",s(Canonical.fingerprint(get "implementations"(D.to_json document)));
      "library_digest",s(I.library_digest library)]in
    let graph=o["schema_version",s I.candidate_schema;"profile",s I.profile;"observable_profile",s I.observable_profile;
      "authority",authority;"slot_layout",o["id",s layout_id;"encounter",s encounter.encounter_id;"slots",Json.int slots];
      "nodes",a(List.map(fun(id,(model:I.model))->o["id",s id;"model",P.to_json model.identity;
        "configuration_digest",s model.configuration_digest])!selected);
      "wires",a !wires;"inputs",a[
        o["id",s "evidence/0";"kind",s "evidence";"consumer",out observation_node "samples"];
        o["id",s "feedback/0";"kind",s "feedback";"consumer",out attempt_node "feedback"]];
      "atomic_groups",a[o["id",s "exclusive/0";"arbiter",s arbiter;"commits",a(List.map s commits)]];
      "semantic_exports",a(List.concat_map(fun(id,_)->exports id)!selected);
      "occurrences",a(List.sort(fun left right->String.compare(text "source_path" left)(text "source_path" right))!occurrences)]in
    let binding=o["schema_version",s B.schema_version;"profile",s B.profile;"catalog_entry",s bridge.entry_id;
      "observations",a[o["source",s observed.observation_id;"bank",s observation_node;"input",s "evidence/0"]];
      "states",a(List.map(fun(source,register)->o["source",s source;"register",s register])state_nodes);
      "effects",a[o["source",s operation.effect_id;"bank",s attempt_node;"feedback",s "feedback/0"]];
      "rules",a !proposal_rules]in
    {implementation=I.of_json ~library graph;binding=B.of_json binding}in
  let rec choose=function
    |[]->Diagnostic.fail "policy_implementation_lowering_missing_model" "No complete authorized supplied model set matches the source and encounter layout."
    |layout::remaining->(try build layout with Diagnostic.Error diagnostic when diagnostic.code="policy_implementation_lowering_missing_model"->choose remaining)in
  choose layouts

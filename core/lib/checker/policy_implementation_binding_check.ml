open Bioc_wire
module I = Bioc_domain.Policy_implementation
module B = Bioc_domain.Policy_implementation_binding
module A = Policy_realization_admission
module R = Bioc_domain.Policy_realization_request
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module F = Bioc_domain.Policy_operating_domain
module Names = Set.Make(String)
let profile = B.profile

type slot = { identity:string; target:string; start_tick:int }
type environment = { executor:string; slots:slot list; horizon_ticks:int }
type observation = { source:string; bank:string; input:string; observer:string; subject:string }
type state = { source:string; register:string }
type effect_site = { initiating_rule:string; gate:string; guard:I.endpoint }
type effect_binding = { source:string; bank:string; feedback:string; initiating_rule:string;
  gate:string; guard:I.endpoint; product_parameter:string; machine:string option; request_sites:effect_site list }
type rule = { source:string; gate:string; arbiter:string; lane:int; commit:string;
  trigger:I.endpoint; source_trigger:O.expression }
type machine = { source:string; bank:string }
type transition = { source:string; machine:string; gate:string; arbiter:string; lane:int; commit:string;
  trigger:I.endpoint; source_trigger:O.expression }
type expression = { source_path:string; source_expression:Json.t; endpoint:I.endpoint }
type checked_binding = { admitted_value:A.admitted_inputs; implementation_value:I.t; environment_value:environment;
  observation_values:observation list; state_values:state list; effect_values:effect_binding list;
  rule_values:rule list; machine_values:machine list; transition_values:transition list;
  expression_values:expression list; report_value:Json.t }
let get=O.get
let text=O.text
let items=O.list
let str value=Json.String value
let obj value=Json.Object value
let arr value=Json.Array value
let require ?path condition message=Diagnostic.require ?path condition "policy_implementation_source_binding" message
let ep node_id port_id : I.endpoint={node_id;port_id}
let endpoint_json (value:I.endpoint)=obj["node",str value.node_id;"port",str value.port_id]
let endpoint_key (value:I.endpoint)=value.node_id^"/"^value.port_id
let singleton label = function [value]->value|_->Diagnostic.fail "policy_implementation_source_binding"
  ("This source/graph profile requires exactly one "^label^".")
let truth = function O.True->I.True|O.False->I.False|O.Unknown->I.Unknown
let nulls ?path fields value=List.iter(fun key->require ?path (get key value=Json.Null)
  ("Source field "^key^" needs semantics outside this graph-binding profile."))fields
let source_type ?path kind value =
  require ?path (text "kind" value=kind && get "unit" value=Json.Null && get "entity_kind" value=Json.Null)
    "Source type is outside this exact truth/product profile."
let outputs (node:I.node)=List.filter_map(fun(p:I.port)->
  if p.direction=I.Output then Some(ep node.node_id p.port_id)else None)(I.ports node.model.primitive)
let expression_identity expression = Canonical.encode expression

let check_legacy ~admitted ~implementation ~proposed =
  let request=A.request admitted and behavior=A.behavior admitted in
  let two_observation=R.is_two_observation request in
  let document=R.document request and domain=F.specification(A.operating_domain admitted)in
  (* Re-decode the actual graph against original external authority. Neither
     graph-carried pins nor a prior producer receipt can select its models. *)
  let implementation=I.of_json ~library:(R.implementation_library request)(I.to_json implementation)in
  require(I.implementation_profile implementation=I.profile)
    "Legacy source bindings require the original truth primitive profile.";
  let authority:I.authority={source_artifact_digest=D.artifact_digest document;
    descriptors_digest=O.descriptors_digest(R.definitions request);
    domain_digest=F.digest(R.operating_domain request);
    implementation_catalog_digest=Canonical.fingerprint(get "implementations"(D.to_json document));
    library_digest=I.library_digest(R.implementation_library request)}in
  I.check_authority ~expected:authority implementation;
  let role=singleton "executor role" behavior.roles
  and encounter=singleton "encounter declaration" behavior.encounters
  and subject=singleton "encounter subject" behavior.subjects
  and clock=singleton "logical clock" behavior.clocks
  and effect_source=singleton "product-bearing effect" behavior.effects
  and parameter=singleton "fixed product parameter" behavior.parameters in
  require(behavior.machines=[] && behavior.transitions=[] &&
    List.mem(List.length behavior.rules)[1;2] && List.mem(List.length behavior.stores)[1;2])
    "This source/graph family has one or two exclusive rules/stores and no machines or transitions.";
  let declarations=D.declarations document in
  let declaration identity=match List.find_opt(fun(d:D.declaration)->d.id=identity)declarations with
    |Some value->value|None->Diagnostic.fail "policy_implementation_source_binding" "Source anchor is absent from original document."in
  let raw identity=(declaration identity).value in
  let path identity=(declaration identity).path in
  require(encounter.executor=role.role_id && encounter.target=subject.subject_id &&
    subject.encounter=Some encounter.encounter_id && subject.executor=Some role.role_id &&
    encounter.termination="explicit_event")"Encounter ownership, target or termination differs from the explicit slot profile.";
  nulls ["domain"](raw subject.subject_id);
  require(clock.clock_id=domain.clock && role.role_id=domain.executor_role &&
    List.for_all(fun(s:F.encounter)->s.declaration=encounter.encounter_id)domain.encounters)
    "Runtime slot/domain ownership differs from original source.";
  let clock_raw=raw clock.clock_id in
  require(List.mem(text "basis" clock_raw)["availability";"logical"] &&
    text "simultaneous" clock_raw="atomic_batch")"Clock phase or simultaneous-event semantics are unsupported.";
  let layout=I.slot_layout implementation in
  require(layout.encounter_id=encounter.encounter_id && layout.slots=List.length domain.encounters)
    "Implementation slot layout differs from complete original encounter domain.";
  let bridge=match List.find_opt(fun(b:R.catalog_binding)->b.entry_id=B.catalog_entry proposed)(R.catalog_bindings request)with
    |Some value->value|None->Diagnostic.fail "policy_implementation_source_binding" "Selected catalog entry is not original authority."in
  require(Json.equal bridge.operation(get "contract"(raw effect_source.effect_id)))
    "Selected catalog entry does not implement the original effect operation.";
  let nodes=I.nodes implementation and used_nodes=ref Names.empty and used_wires=ref Names.empty
  and used_inputs=ref Names.empty and occurrences=ref [] and expressions=ref [] in
  let node identity=match List.find_opt(fun(n:I.node)->n.node_id=identity)nodes with
    |Some value->used_nodes:=Names.add identity !used_nodes;value
    |None->Diagnostic.fail "policy_implementation_source_binding" "Anchor names an absent actual graph node."in
  List.iter(fun(n:I.node)->
    A.require_model admitted ~entry_id:bridge.entry_id n.model.identity;
    require(match n.model.replication with
      |I.Encounter_slots s->s.layout_id=layout.layout_id && s.slots=layout.slots
      |I.Executor->(match n.model.primitive with I.Truth_constant _|I.Product_constant _|I.Truth_not|I.Truth_all _|I.Truth_any _->true|_->false))
      "Source mutable/control state is not replicated by the exact encounter layout.")nodes;
  let primitive identity=(node identity).model.primitive in
  let incoming consumer =
    match List.find_opt(fun(w:I.wire)->w.consumer=consumer)(I.wires implementation)with
    |Some wire->used_wires:=Names.add(endpoint_key consumer)!used_wires;wire.producer
    |None->Diagnostic.fail "policy_implementation_source_binding" "A source input has no actual primitive wire."in
  let wire producer consumer=require(incoming consumer=producer)"Actual producer/consumer wiring changes a source operation or binding."in
  let external_input identity kind consumer=
    let selected=List.filter(fun(i:I.external_input)->i.input_id=identity)(I.inputs implementation)in
    let input=singleton "external input anchor" selected in
    require(input.input_kind=kind && input.consumer=consumer)"External input kind or destination differs from source anchor.";
    used_inputs:=Names.add identity !used_inputs in
  let record ?(disposition=I.Executable) role source_path targets=
    require(not(List.exists(fun(o:I.occurrence)->o.source_path=source_path)!occurrences))
      "Independent source traversal produced a duplicate occurrence.";
    occurrences:=({I.source_path=source_path;role;disposition;targets}:I.occurrence)::!occurrences in
  let add_expression role source_path source_expression endpoint =
    let disposition=if List.mem(text "op" source_expression)["literal";"parameter"]then I.Constant else I.Executable in
    record ~disposition role source_path [endpoint];
    expressions:=({source_path;source_expression;endpoint}:expression)::!expressions in
  let ticks duration=let ticks=Q.div duration clock.resolution in
    require(Z.equal(Q.den ticks)Z.one && Q.sign ticks>0 && Z.compare(Q.num ticks)(Z.of_int 10000)<=0)
      "Source duration is not a positive bounded number of exact clock ticks.";Z.to_int(Q.num ticks)in
  let observation_sources=if two_observation then (
    require(List.length behavior.observations=2)
      "Two-observation source binding requires exactly two original observations.";
    behavior.observations)else [singleton "truth observation" behavior.observations] in
  let observation_anchors=B.observations proposed
  and effect_anchor=singleton "effect anchor"(B.effects proposed)in
  require(List.map(fun(value:B.observation)->value.source)observation_anchors=
    List.map(fun(value:O.observation)->value.observation_id)observation_sources &&
    effect_anchor.source=effect_source.effect_id)
    (if two_observation then "Source observation/effect inventory differs from proposed anchors or original declaration order."
     else "Source observation/effect inventory differs from proposed anchors.");
  if two_observation then (
    let banks=List.map(fun(value:B.observation)->value.bank)observation_anchors
    and inputs=List.map(fun(value:B.observation)->value.input)observation_anchors in
    require(List.length(List.sort_uniq String.compare banks)=2 &&
      List.length(List.sort_uniq String.compare inputs)=2)
      "Distinct original observations require distinct evidence banks and external inputs.";
    require(List.filter_map(fun(value:I.node)->match value.model.primitive with
      |I.Evidence_bank _->Some value.node_id|_->None)nodes=banks)
      "Actual evidence-bank node order differs from original observation declaration order.";
    require(List.length(List.sort_uniq String.compare
      (List.map(fun(value:O.observation)->value.coherence)observation_sources))=2)
      "Two-observation source binding requires distinct original coherence groups.");
  List.iter2(fun(observation_source:O.observation)(observation_anchor:B.observation)->
    require(observation_source.value_type=O.Truth_type && observation_source.observer=role.role_id &&
      observation_source.subject=subject.subject_id && observation_source.clock=clock.clock_id &&
      observation_source.coverage="event" && (two_observation || observation_source.coherence="frame"))
      (if two_observation then "Source observation changes its encounter-local event evidence profile."
       else "Only encounter-local event evidence with frame coherence is supported by this graph profile.");
    source_type "truth"(get "value_type"(raw observation_source.observation_id));
    require(primitive observation_anchor.bank=I.Evidence_bank{freshness_ticks=ticks observation_source.freshness})
      "Evidence-bank freshness or operation differs from original observation.";
    external_input observation_anchor.input I.Evidence_input(ep observation_anchor.bank "samples");
    record I.Declaration(path observation_source.observation_id)(outputs(node observation_anchor.bank)))
    observation_sources observation_anchors;
  let observation_anchor identity=match List.find_opt(fun(value:B.observation)->value.source=identity)observation_anchors with
    |Some value->value
    |None->Diagnostic.fail "policy_implementation_source_binding" "Expression references an unmapped original observation." in
  require(List.map(fun(s:B.state)->s.source)(B.states proposed)=List.map(fun(s:O.state_store)->s.state_id)behavior.stores)
    "State anchors must cover every original state exactly once in declaration order.";
  require(List.map(fun(r:B.rule)->r.source)(B.rules proposed)=List.map(fun(r:O.rule)->r.rule_id)behavior.rules)
    "Rule anchors must cover every original rule exactly once in declaration order.";
  let state_anchor identity=List.find(fun(s:B.state)->s.source=identity)(B.states proposed)in
  let assignments=List.concat_map(fun(r:O.rule)->List.mapi(fun index(a:O.assignment)->r.rule_id,index,a.state)r.assignments)behavior.rules in
  List.iter(fun(s:O.state_store)->
    let anchor=state_anchor s.state_id and source=raw s.state_id in
    let writers=List.filter(fun(_,_,identity)->identity=s.state_id)assignments in
    require(s.value_type=O.Truth_type && s.scope=O.Encounter encounter.encounter_id && s.lifetime="encounter" &&
      s.reset=None && s.capacity>=layout.slots && text "overflow" source="reject" &&
      text "inheritance" source="not_applicable" && writers<>[])
      "State lifetime, scope, capacity, reset or writer semantics are outside this family.";
    nulls ["duration";"coordination";"contract"]source;
    source_type "truth"(get "value_type" source);
    let initial=match s.initial with O.Truth value->truth value|_->Diagnostic.fail "policy_implementation_source_binding" "Register initial state is not truth-valued."in
    require(primitive anchor.register=I.Truth_register{initial;writers=List.length writers})
      "Register initial value or complete writer inventory differs from original state.";
    record I.Declaration(path s.state_id)[ep anchor.register "value"])behavior.stores;
  let parameter_raw=raw parameter.parameter_id in
  require(text "selection" parameter_raw="fixed")"Product parameter is not a fixed source value.";
  nulls ["lower";"upper"]parameter_raw;
  source_type "text"(get "value_type" parameter_raw);
  let product=match parameter.value with O.Text value->value|_->Diagnostic.fail "policy_implementation_source_binding" "Product parameter must be fixed text."in
  let parameter_targets=ref [] and edges=ref [] in
  let raw_expr_fields source_path source=
    nulls ~path:source_path ["contract";"duration";"clock";"coverage";"binding"]source in
  let ref_matches source key kind identity=
    let value=get key source in value<>Json.Null && text "kind" value=kind && O.ref_id value=identity in
  let rec check_expression role source_path source (endpoint:I.endpoint) =
    raw_expr_fields source_path source;
    let expression=O.expression_of_json source in
    let operator=expression.op and args=items "args" source in
    let actual=primitive endpoint.I.node_id in
    let plain ()=nulls ~path:source_path ["ref";"scope";"value"]source in
    let output port=require(endpoint.port_id=port)"Expression is bound to the wrong primitive output."in
    (match operator with
    |"observe"->source_type ~path:source_path "truth"(get "value_type" source);
        let identity=O.ref_id(get "ref" source)in
        let anchor=observation_anchor identity in
        require(args=[] && get "value" source=Json.Null &&
          ref_matches source "ref" "Observation" identity &&
          ref_matches source "scope" "Subject" subject.subject_id && endpoint=ep anchor.bank "value")
          "Observed expression loses its exact source observation/subject bank."
    |"state"->source_type ~path:source_path "truth"(get "value_type" source);
        let identity=O.ref_id(get "ref" source)in
        require(List.exists(fun(s:B.state)->s.source=identity)(B.states proposed))"Expression references an unmapped state.";
        require(args=[] && get "value" source=Json.Null && ref_matches source "ref" "StateStore" identity &&
          ref_matches source "scope" "Encounter" encounter.encounter_id && endpoint=ep(state_anchor identity).register "value")
          "State expression loses its exact encounter register."
    |"literal"->source_type ~path:source_path "truth"(get "value_type" source);
        nulls ~path:source_path ["ref";"scope"]source;require(args=[])"Literal expression carries operands.";
        let expected=match expression.value with Some(O.Truth value)->truth value|_->Diagnostic.fail "policy_implementation_source_binding" "Only exact truth literals are graph operands."in
        output "out";require(actual=I.Truth_constant expected)"Truth literal primitive differs from source."
    |"parameter"->source_type ~path:source_path "text"(get "value_type" source);
        require(args=[] && ref_matches source "ref" "Parameter" parameter.parameter_id &&
          get "scope" source=Json.Null && get "value" source=Json.Null)
          "Product operand differs from the sole fixed original parameter.";
        output "out";require(actual=I.Product_constant product)"Product identity primitive differs from exact original parameter.";
        if not(List.mem endpoint !parameter_targets)then parameter_targets:= !parameter_targets@[endpoint]
    |"not"|"all"|"any"->source_type ~path:source_path "truth"(get "value_type" source);plain();output "out";
        require(match operator,actual with "not",I.Truth_not->List.length args=1
          |"all",I.Truth_all n|"any",I.Truth_any n->List.length args=n|_->false)
          "Truth operator or ordered arity differs from original expression.";
        List.iteri(fun index arg->let port=if operator="not"then "in"else "in"^string_of_int index in
          check_expression role (source_path^"/args/"^string_of_int index)arg(incoming(ep endpoint.node_id port)))args
    |"rising"->source_type ~path:source_path "event"(get "value_type" source);plain();output "events";
        require(actual=I.Observed_rising && List.length args=1)"Source rising event has no exact observed-edge primitive.";
        let rec evidence_only value = List.mem(text "op" value)["observe";"literal";"not";"all";"any"] &&
          List.for_all evidence_only(items "args" value)in
        let rec observed value=text "op" value="observe"||List.exists observed(items "args" value)in
        require(evidence_only(List.hd args) && observed(List.hd args))"Once-per-tick rising must depend only on observed truth evidence.";
        let identity=expression_identity source in
        (match List.assoc_opt identity !edges with
        |Some prior->require(prior=endpoint.node_id)"One nominal rising expression is split across independent edge memories."
        |None->require(not(List.exists(fun(_,node)->node=endpoint.node_id)!edges))"Distinct rising expressions share one edge memory.";
            edges:= !edges@[identity,endpoint.node_id]);
        check_expression role(source_path^"/args/0")(List.hd args)(incoming(ep endpoint.node_id "in"))
    |_->Diagnostic.fail ~path:source_path "policy_implementation_source_binding" "Source expression operation is outside this graph-binding family.");
    add_expression role source_path source endpoint in
  let anchors=B.rules proposed in
  let arbiter=(List.hd anchors).arbiter in
  require(List.for_all(fun(r:B.rule)->r.arbiter=arbiter)anchors && primitive arbiter=I.Exclusive_arbiter(List.length anchors))
    "Source exclusive group does not have one exact lane per original rule.";
  let source_gates=List.map(fun(r:B.rule)->r.gate)anchors in
  let actual_gates=List.filter_map(fun(n:I.node)->if n.model.primitive=I.Activation_gate then Some n.node_id else None)nodes in
  require(actual_gates=source_gates)"Actual gate-node order changes original rule/attempt ordering.";
  let initiators=List.filter(fun(r:O.rule)->r.effects<>[])behavior.rules in
  let initiator=singleton "effect-initiating rule" initiators in
  require(initiator.effects=[effect_source.effect_id])"Effect initiator changes the original requested-effect inventory.";
  let initiating_anchor=List.find(fun(r:B.rule)->r.source=initiator.rule_id)anchors in
  require(effect_source.executor=role.role_id && effect_source.subject=subject.subject_id &&
    effect_source.lifecycle.on_loss="continue")"Effect executor, recipient or loss behavior differs from the explicit profile.";
  let timeout=match effect_source.lifecycle.timeout with Some value->ticks value|None->Diagnostic.fail "policy_implementation_source_binding" "An attempt bank requires an explicit source timeout."in
  let authorization=match effect_source.lifecycle.authorization with "initiation"->I.At_initiation|"continuous"->I.Continuous
    |_->Diagnostic.fail "policy_implementation_source_binding" "Unsupported source authorization lifetime."in
  let on_unknown=match effect_source.lifecycle.on_unknown with "continue"->I.Continue|"defer"->I.Defer
    |_->Diagnostic.fail "policy_implementation_source_binding" "Unsupported source uncertainty response."in
  require(match primitive effect_anchor.bank with I.Attempt_bank b->b.timeout_ticks=timeout &&
    b.authorization=authorization && b.on_unknown=on_unknown && b.capacity>=domain.logical_limits.max_source_attempts|_->false)
    "Attempt bank timeout, uncertainty, authorization or capacity changes original bounded behavior.";
  external_input effect_anchor.feedback I.Feedback_input(ep effect_anchor.bank "feedback");
  let effect_raw=raw effect_source.effect_id in
  let arguments=items "parameters" effect_raw in
  let argument=singleton "effect product argument" arguments in
  require(text "name" argument="product" && text "op"(get "value" argument)="parameter")
    "This effect requires exactly the fixed typed product argument.";
  record I.Lifecycle(path effect_source.effect_id)(outputs(node effect_anchor.bank));
  record I.Lifecycle(path effect_source.effect_id^"/lifecycle")(outputs(node effect_anchor.bank));
  let guards=ref [] in
  List.iteri(fun index (source_rule:O.rule)->
    let anchor=List.nth anchors index and source=raw source_rule.rule_id and source_path=path source_rule.rule_id in
    require(source_rule.executor=role.role_id && anchor.lane=index && primitive anchor.gate=I.Activation_gate &&
      source_rule.arbitration.mode="exclusive" && source_rule.arbitration.tie="reject" &&
      source_rule.arbitration.write_conflict="reject" && source_rule.arbitration.order=[])
      "Rule, arbitration mode, tie/write conflict or lane order changes source semantics.";
    require(text "op"(get "on" source)="rising")"This rule family triggers only on an observed rising event.";
    require(primitive anchor.commit=I.Atomic_commit{writes=List.length source_rule.assignments;requests=List.length source_rule.effects})
      "Atomic commit does not retain every source assignment and effect.";
    wire(ep anchor.gate "candidate")(ep arbiter("in"^string_of_int index));
    wire(ep arbiter("out"^string_of_int index))(ep anchor.commit "grant");
    check_expression I.Predicate(source_path^"/on")(get "on" source)(incoming(ep anchor.gate "on"));
    let guard=incoming(ep anchor.gate "guard")in
    check_expression I.Predicate(source_path^"/when")(get "when" source)guard;
    guards:= !guards@[source_rule.rule_id,guard];
    List.iteri(fun assignment_index (assignment:O.assignment)->
      let assignment_path=source_path^"/assignments/"^string_of_int assignment_index in
      let register=(state_anchor assignment.state).register in
      let writers=List.filter(fun(_,_,identity)->identity=assignment.state)assignments in
      let rec writer_index index=function
        |(rule,index_in_rule,_)::_ when rule=source_rule.rule_id && index_in_rule=assignment_index->index
        |_::rest->writer_index(index+1)rest|[]->Diagnostic.fail "policy_implementation_source_binding" "Missing original writer."in
      let writer=writer_index 0 writers in
      wire(ep anchor.commit("write"^string_of_int assignment_index))(ep register("write"^string_of_int writer));
      record I.State_write assignment_path [ep anchor.commit("write"^string_of_int assignment_index)];
      check_expression I.State_write(assignment_path^"/value")
        (get "value"(List.nth(items "assignments" source)assignment_index))
        (incoming(ep anchor.commit("value"^string_of_int assignment_index))))source_rule.assignments;
    if source_rule.effects<>[]then(
      wire(ep anchor.commit "request0")(ep effect_anchor.bank "request");
      wire guard(ep effect_anchor.bank "authorization");
      check_expression I.Effect_parameter(path effect_source.effect_id^"/parameters/0/value")
        (get "value" argument)(incoming(ep anchor.commit "product0")));
    record I.Declaration source_path ([ep anchor.gate "candidate";ep arbiter("out"^string_of_int index)]@outputs(node anchor.commit));
    record I.Declaration(source_path^"/arbitration")[ep arbiter("out"^string_of_int index)])behavior.rules;
  let actual_edges=List.filter_map(fun(n:I.node)->if n.model.primitive=I.Observed_rising then Some n.node_id else None)nodes in
  require(actual_edges=List.map snd !edges)"Actual rising-memory order differs from independently derived source event order.";
  let group=singleton "atomic group"(I.atomic_groups implementation)in
  require(group.arbiter=arbiter && group.commits=List.map(fun(r:B.rule)->r.commit)anchors)
    "Atomic group changes original rule membership or order.";
  require(!parameter_targets<>[])"Fixed source product has no interpreted graph use.";
  record ~disposition:I.Constant I.Effect_parameter(path parameter.parameter_id)!parameter_targets;
  (* Every requirement remains an obligation, not a claim about its truth. Its
     nested expressions are inventoried, and monitor-only rising memory is
     explicitly rejected because it would add source events absent the graph. *)
  let rec requirement_expressions source_path value=match value with
    |Json.Object fields->
        if List.assoc_opt "$type" fields=Some(str "Expr")then(
          if text "op" value="rising"then require(List.mem_assoc(expression_identity value)!edges)
            "Requirement-only rising memory needs a separate source/graph profile.";
          record ~disposition:I.Obligation I.Requirement source_path []);
        List.iter(fun(key,value)->requirement_expressions(source_path^"/"^key)value)fields
    |Json.Array values->List.iteri(fun i value->requirement_expressions(source_path^"/"^string_of_int i)value)values
    |_->()in
  List.iter(fun(d:D.declaration)->match d.kind with
    |D.Role|D.Subject|D.Encounter->record ~disposition:I.Retained_metadata I.Declaration d.path []
    |D.Clock->record ~disposition:I.Retained_metadata I.Clock d.path []
    |D.Requirement->record ~disposition:I.Obligation I.Requirement d.path [];
        requirement_expressions d.path d.value
    |D.Observation|D.State_store|D.Effect|D.Rule|D.Parameter->()
    |_->Diagnostic.fail "policy_implementation_source_binding" "Original declaration has no interpreted disposition in this family.")declarations;
  require(Names.cardinal !used_nodes=List.length nodes && Names.cardinal !used_wires=List.length(I.wires implementation) &&
    Names.cardinal !used_inputs=List.length(I.inputs implementation))
    "Actual graph has an orphan node, wire or external input outside reconstructed source behavior.";
  let expected=List.sort(fun(a:I.occurrence)(b:I.occurrence)->String.compare a.source_path b.source_path)!occurrences in
  I.check_occurrence_inventory ~expected:(List.map(fun(o:I.occurrence)->o.source_path)expected)implementation;
  require(I.occurrences implementation=expected)"Candidate occurrence roles, dispositions or targets differ from independently reconstructed source.";
  let environment_value={executor=domain.executor_identity;
    slots=List.map(fun(s:F.encounter)->({identity=s.identity;target=s.target;start_tick=s.start_tick}:slot))domain.encounters;
    horizon_ticks=domain.horizon_ticks}in
  let observation_values=List.map(fun(value:B.observation)->
    ({source=value.source;bank=value.bank;input=value.input;observer=role.role_id;subject=subject.subject_id}:observation))observation_anchors
  and state_values=List.map(fun(s:B.state)->({source=s.source;register=s.register}:state))(B.states proposed)
  and rule_values=List.map(fun(r:B.rule)->
    let source=List.find(fun(s:O.rule)->s.rule_id=r.source)behavior.rules in
    ({source=r.source;gate=r.gate;arbiter=r.arbiter;lane=r.lane;commit=r.commit;
      trigger=incoming(ep r.gate "on");source_trigger=source.on}:rule))anchors in
  let effect_values=[{source=effect_source.effect_id;bank=effect_anchor.bank;feedback=effect_anchor.feedback;
    initiating_rule=initiator.rule_id;gate=initiating_anchor.gate;guard=List.assoc initiator.rule_id !guards;
    request_sites=[{initiating_rule=initiator.rule_id;gate=initiating_anchor.gate;guard=List.assoc initiator.rule_id !guards}];
    product_parameter=text "name" argument;machine=None}]in
  let expression_values=List.sort(fun(a:expression)(b:expression)->String.compare a.source_path b.source_path)!expressions in
  let report_value=obj[
    "schema_version",str(if two_observation then "biocompiler.policy_implementation_binding_report.v0.3"
      else "biocompiler.policy_implementation_binding_report.v0.1");
    "profile",str(if two_observation then B.two_observation_profile else profile);
    "observable_profile",str I.observable_profile;"status",str "source_graph_bound";
    "request_fingerprint",str(R.fingerprint request);"catalog_bindings_digest",str(R.catalog_bindings_digest request);
    "catalog_entry",str bridge.entry_id;"catalog_entry_digest",str bridge.entry_digest;
    "source_artifact_digest",str authority.source_artifact_digest;"descriptors_digest",str authority.descriptors_digest;
    "operating_domain_digest",str authority.domain_digest;"implementation_catalog_digest",str authority.implementation_catalog_digest;
    "implementation_library_digest",str authority.library_digest;"implementation_fingerprint",str(I.fingerprint implementation);
    "proposed_binding_fingerprint",str(B.fingerprint proposed);"source_admission",A.report admitted;
    "source_occurrences",get "occurrences"(I.to_json implementation);
    "interpreted_outputs",arr(List.map(fun(n:I.node)->obj["node",str n.node_id;
      "operation",str(I.primitive_name n.model.primitive);"outputs",arr(List.map endpoint_json(outputs n))])nodes);
    "execution",str "not_performed";"preservation",str "unassessed";"requirements",str "unassessed";
    "material",str "unassessed";"target_status",str "unassessed";"artifact",str "withheld";"export",str "withheld"]in
  {admitted_value=admitted;implementation_value=implementation;environment_value;observation_values;state_values;effect_values;
   rule_values;machine_values=[];transition_values=[];expression_values;report_value}
let check_staged ~admitted ~implementation ~proposed =
  let request=A.request admitted and behavior=A.behavior admitted in
  let multi_product=R.is_multi_product request in
  let finite_machine=R.is_finite_machine request and multi_site=R.is_multi_site request in
  let document=R.document request and domain=F.specification(A.operating_domain admitted)in
  let implementation=I.of_json ~library:(R.implementation_library request)(I.to_json implementation)in
  require(I.implementation_profile implementation=(if multi_site then I.multi_site_profile else I.staged_profile) &&
    I.implementation_observable_profile implementation=(if multi_site then I.multi_site_observable_profile else I.staged_observable_profile))
    "Staged source needs its exact explicit primitive and observable profiles.";
  let authority:I.authority={source_artifact_digest=D.artifact_digest document;
    descriptors_digest=O.descriptors_digest(R.definitions request);domain_digest=F.digest(R.operating_domain request);
    implementation_catalog_digest=Canonical.fingerprint(get "implementations"(D.to_json document));
    library_digest=I.library_digest(R.implementation_library request)}in
  I.check_authority ~expected:authority implementation;
  let role=singleton "executor role" behavior.roles and encounter=singleton "encounter declaration" behavior.encounters
  and subject=singleton "encounter subject" behavior.subjects and clock=singleton "clock" behavior.clocks
  and observation_source=singleton "truth observation" behavior.observations
  and parameter=(if multi_product then None else Some(singleton "fixed product parameter" behavior.parameters))
  and source_machine=singleton "encounter machine" behavior.machines in
  (if finite_machine then
    require(behavior.rules=[] && behavior.stores=[] &&
      List.length behavior.effects>=1 && List.length behavior.effects<=8 &&
      List.length behavior.transitions>=1 && List.length behavior.transitions<=32 &&
      List.length source_machine.states>=2 && List.length source_machine.states<=16)
      "Finite-machine source requires two to sixteen states, one to thirty-two transitions, one to eight effects and no separate rules/stores."
  else
    require(behavior.rules=[] && behavior.stores=[] && List.length behavior.effects=2 &&
      List.length behavior.transitions=7 && List.length source_machine.states=5 && List.length source_machine.terminal=2)
      "Staged source requires one five-state machine, two effects, seven transitions and no separate rules/stores.");
  let declarations=D.declarations document in
  let declaration identity=match List.find_opt(fun(d:D.declaration)->d.id=identity)declarations with
    |Some value->value|None->Diagnostic.fail "policy_implementation_source_binding" "Original staged declaration is absent."in
  let raw identity=(declaration identity).value and path identity=(declaration identity).path in
  require(encounter.executor=role.role_id && encounter.target=subject.subject_id &&
    subject.encounter=Some encounter.encounter_id && subject.executor=Some role.role_id && encounter.termination="explicit_event")
    "Staged encounters must retain their exact executor, target and explicit lifetime.";
  nulls ["domain"](raw subject.subject_id);
  require(clock.clock_id=domain.clock && role.role_id=domain.executor_role &&
    List.for_all(fun(s:F.encounter)->s.declaration=encounter.encounter_id)domain.encounters &&
    List.mem(text "basis"(raw clock.clock_id))["availability";"logical"] && text "simultaneous"(raw clock.clock_id)="atomic_batch")
    "Staged clock/domain ownership or phase differs from original source.";
  let layout=I.slot_layout implementation in
  require(layout.encounter_id=encounter.encounter_id && layout.slots=2 && layout.slots=List.length domain.encounters)
    "Staged machine replication must retain both original encounter slots.";
  require(source_machine.executor=role.role_id && source_machine.scope=O.Encounter encounter.encounter_id &&
    source_machine.lifetime="encounter" && source_machine.arbitration.mode="exclusive" &&
    source_machine.arbitration.tie="reject" && source_machine.arbitration.write_conflict="reject" &&
    source_machine.arbitration.order=[])
    "Staged machine requires encounter lifetime and exact exclusive arbitration.";
  let bridge=match List.find_opt(fun(b:R.catalog_binding)->b.entry_id=B.catalog_entry proposed)(R.catalog_bindings request)with
    |Some value->value|None->Diagnostic.fail "policy_implementation_source_binding" "Staged catalog entry is not original authority."in
  let machine_anchor=singleton "machine anchor"(B.machines proposed)
  and observation_anchor=singleton "observation anchor"(B.observations proposed)in
  let anchors=B.transitions proposed in
  require(machine_anchor.source=source_machine.machine_id && observation_anchor.source=observation_source.observation_id &&
    B.rules proposed=[] && B.states proposed=[] &&
    List.map(fun(t:B.transition)->t.source)anchors=List.map(fun(t:O.transition)->t.transition_id)behavior.transitions &&
    List.map(fun(e:B.effect_binding)->e.source)(B.effects proposed)=List.map(fun(e:O.effect_spec)->e.effect_id)behavior.effects)
    "Staged anchors must cover exact original declarations once and in declaration order.";
  let transition_anchor identity=List.find(fun(t:B.transition)->t.source=identity)anchors in
  let effect_anchor identity=List.find(fun(e:B.effect_binding)->e.source=identity)(B.effects proposed)in
  (if finite_machine then
    require(List.for_all(fun(t:O.transition)->t.machine=source_machine.machine_id && t.assignments=[] &&
      List.length t.effects<=1 && not(List.mem t.source source_machine.terminal))behavior.transitions)
      "Finite-machine transitions must retain their sole machine, have at most one effect request and no assignments or terminal reentry."
  else (
  let event_is effect_id phase (t:O.transition)=t.on.op="effect_event" && t.on.reference=Some effect_id && t.on.phase=Some phase in
  let requesting=List.filter(fun(t:O.transition)->t.effects<>[])behavior.transitions in
  let first=singleton "rising-triggered first stage"(List.filter(fun(t:O.transition)->t.on.op="rising")requesting)in
  let first_effect=singleton "first-stage effect" first.effects in
  let second=singleton "completion-triggered second stage"(List.filter(event_is first_effect "completed")requesting)in
  let second_effect=singleton "second-stage effect" second.effects in
  let finish=singleton "second-stage completion"(List.filter(event_is second_effect "completed")behavior.transitions)in
  require(List.length requesting=2 && first_effect<>second_effect && first.source=source_machine.initial &&
    second.source=first.destination && finish.source=second.destination && finish.effects=[] &&
    List.mem finish.destination source_machine.terminal)
    "Staged source must request stage two only on its retained first-stage completion and then terminate.";
  let failures=List.concat_map(fun(effect_id,state)->List.map(fun phase->
    let t=singleton (phase^" stage transition")(List.filter(event_is effect_id phase)behavior.transitions)in
    require(t.source=state && t.effects=[] && List.mem t.destination source_machine.terminal)
      "Stage failure/timeout must terminate its own active stage without requesting another effect.";t)
    ["failed";"timed_out"])[first_effect,first.destination;second_effect,second.destination]in
  let failed=(List.hd failures).destination in
  require(List.for_all(fun(t:O.transition)->t.destination=failed)failures && failed<>finish.destination &&
    List.length(List.sort_uniq String.compare [source_machine.initial;first.destination;second.destination;finish.destination;failed])=5 &&
    List.sort String.compare source_machine.states=List.sort String.compare
      [source_machine.initial;first.destination;second.destination;finish.destination;failed] &&
    List.for_all(fun(t:O.transition)->t.machine=source_machine.machine_id && t.assignments=[] &&
      not(List.mem t.source source_machine.terminal))behavior.transitions)
    "Staged topology, finite states, terminal non-reentry or assignment scope differs from the two-stage family."));
  let nodes=I.nodes implementation and used_nodes=ref Names.empty and used_wires=ref Names.empty
  and used_inputs=ref Names.empty and occurrences=ref [] and expressions=ref [] in
  let node identity=match List.find_opt(fun(n:I.node)->n.node_id=identity)nodes with
    |Some value->used_nodes:=Names.add identity !used_nodes;value
    |None->Diagnostic.fail "policy_implementation_source_binding" "Staged anchor names an absent actual node."in
  let primitive identity=(node identity).model.primitive in
  List.iter(fun(n:I.node)->A.require_model admitted ~entry_id:bridge.entry_id n.model.identity;
    require(match n.model.replication with
      |I.Encounter_slots s->s.layout_id=layout.layout_id && s.slots=layout.slots
      |I.Executor->(match n.model.primitive with I.Truth_constant _|I.Product_constant _|I.Truth_not|I.Truth_all _|I.Truth_any _->true|_->false))
      "Staged mutable and control state must have exact encounter replication.")nodes;
  let incoming consumer=match List.find_opt(fun(w:I.wire)->w.consumer=consumer)(I.wires implementation)with
    |Some value->used_wires:=Names.add(endpoint_key consumer)!used_wires;value.producer
    |None->Diagnostic.fail "policy_implementation_source_binding" "Staged source operation lacks an actual wire."in
  let wire producer consumer=require(incoming consumer=producer)"Staged wiring changes an original operand or owner."in
  let external_input identity kind consumer=
    let input=singleton "staged external input"(List.filter(fun(i:I.external_input)->i.input_id=identity)(I.inputs implementation))in
    require(input.input_kind=kind && input.consumer=consumer)"Staged external input kind or destination differs.";
    used_inputs:=Names.add identity !used_inputs in
  let record ?(disposition=I.Executable) role source_path targets=
    require(not(List.exists(fun(o:I.occurrence)->o.source_path=source_path)!occurrences))"Duplicate reconstructed staged source occurrence.";
    occurrences:=({I.source_path=source_path;role;disposition;targets}:I.occurrence)::!occurrences in
  let ticks duration=let value=Q.div duration clock.resolution in
    require(Z.equal(Q.den value)Z.one && Q.sign value>0 && Z.compare(Q.num value)(Z.of_int 10000)<=0)
      "Staged duration needs positive bounded exact clock ticks.";Z.to_int(Q.num value)in
  require(observation_source.value_type=O.Truth_type && observation_source.observer=role.role_id &&
    observation_source.subject=subject.subject_id && observation_source.clock=clock.clock_id &&
    observation_source.coverage="event" && observation_source.coherence="frame")"Staged observation changes source evidence semantics.";
  source_type "truth"(get "value_type"(raw observation_source.observation_id));
  require(primitive observation_anchor.bank=I.Evidence_bank{freshness_ticks=ticks observation_source.freshness})
    "Staged evidence freshness differs from the original observation.";
  external_input observation_anchor.input I.Evidence_input(ep observation_anchor.bank "samples");
  record I.Declaration(path observation_source.observation_id)(outputs(node observation_anchor.bank));
  require(match primitive machine_anchor.bank with I.Machine_bank value->
    value.states=source_machine.states && value.initial=source_machine.initial && value.terminal=source_machine.terminal &&
    value.writers=List.length behavior.transitions && value.retained_capacity>=1|_->false)
    "Machine bank must retain exact ordered state labels, initial/terminal states, writers and attempt capacity.";
  record I.Declaration(path source_machine.machine_id)[ep machine_anchor.bank "snapshot"];
  let fixed_product (parameter:O.parameter) =
    let parameter_raw=raw parameter.parameter_id in
    require(text "selection" parameter_raw="fixed")"Staged product must be fixed.";
    nulls ["lower";"upper"]parameter_raw;source_type "text"(get "value_type" parameter_raw);
    match parameter.value with O.Text value->value|_->Diagnostic.fail "policy_implementation_source_binding" "Staged product is not fixed text."in
  let products=match parameter with
    |Some parameter->[parameter.parameter_id,fixed_product parameter]
    |None->
      require(List.length behavior.parameters=2)"Multi-product staged bindings need exactly two fixed source parameters.";
      let values=List.map(fun(parameter:O.parameter)->parameter.parameter_id,fixed_product parameter)behavior.parameters in
      require(List.length(List.sort_uniq String.compare(List.map snd values))=2)
        "The two original products must have distinct symbols.";
      let uses=List.map(fun(effect_spec:O.effect_spec)->
        let argument=singleton "staged product argument"(items "parameters"(raw effect_spec.effect_id))in
        let value=get "value" argument in
        require(text "name" argument="product" && text "op" value="parameter")
          "Every stage must name one fixed original product.";
        O.ref_id(get "ref" value))behavior.effects in
      require(List.sort String.compare uses=List.sort String.compare(List.map fst values))
        "Each original stage must consume its own fixed product exactly once.";values in
  let parameter_id,product=match products with first::_->first|[]->assert false in
  let parameter_targets=ref [] and product_targets=ref [] and edges=ref [] in
  let ref_matches source key kind identity=let value=get key source in
    value<>Json.Null && text "kind" value=kind && O.ref_id value=identity in
  let rec expression role source_path source (endpoint:I.endpoint)=
    nulls ~path:source_path ["contract";"duration";"clock";"coverage";"binding"]source;
    let operator=text "op" source and args=items "args" source in
    let decoded=O.expression_of_json source and actual=primitive endpoint.node_id in
    let output port=require(endpoint.port_id=port)"Staged source expression names the wrong output."in
    let plain ()=nulls ~path:source_path ["ref";"scope";"value"]source in
    (match operator with
    |"observe"->source_type "truth"(get "value_type" source);
        require(args=[] && get "value" source=Json.Null && ref_matches source "ref" "Observation" observation_source.observation_id &&
          ref_matches source "scope" "Subject" subject.subject_id && endpoint=ep observation_anchor.bank "value")
          "Staged observed expression changes its original subject/bank."
    |"updated" when finite_machine->source_type "event"(get "value_type" source);
        require(args=[] && get "value" source=Json.Null && ref_matches source "ref" "Observation" observation_source.observation_id &&
          ref_matches source "scope" "Subject" subject.subject_id && endpoint=ep observation_anchor.bank "updated")
          "Finite-machine update event must retain its exact observation, subject and evidence-bank update output."
    |"literal"->source_type "truth"(get "value_type" source);nulls ["ref";"scope"]source;require(args=[])"Literal has operands.";
        let value=match decoded.value with Some(O.Truth value)->truth value|_->Diagnostic.fail "policy_implementation_source_binding" "Staged literal must be truth."in
        output "out";require(actual=I.Truth_constant value)"Staged truth literal differs."
    |"parameter"->source_type "text"(get "value_type" source);
        if multi_product then (
          let matched=List.find_opt(fun(id,_)->ref_matches source "ref" "Parameter" id)products in
          require(args=[] && Option.is_some matched && get "scope" source=Json.Null && get "value" source=Json.Null)
            "Staged effect product differs from its original fixed parameter.";
          let id,symbol=Option.get matched in
          output "out";require(actual=I.Product_constant symbol)"Staged product constant differs.";
          let previous=Option.value(List.assoc_opt id !product_targets)~default:[]in
          let targets=if List.mem endpoint previous then previous else previous@[endpoint]in
          product_targets:=(id,targets)::List.remove_assoc id !product_targets)
        else (
          require(args=[] && ref_matches source "ref" "Parameter" parameter_id && get "scope" source=Json.Null && get "value" source=Json.Null)
            "Staged effect product does not use the same fixed original parameter.";
          output "out";require(actual=I.Product_constant product)"Staged product constant differs.";
          if not(List.mem endpoint !parameter_targets)then parameter_targets:= !parameter_targets@[endpoint])
    |"not"|"all"|"any"->source_type "truth"(get "value_type" source);plain();output "out";
        require(match operator,actual with "not",I.Truth_not->List.length args=1
          |"all",I.Truth_all n|"any",I.Truth_any n->List.length args=n|_->false)"Staged truth operation or arity differs.";
        List.iteri(fun index arg->let port=if operator="not"then "in"else "in"^string_of_int index in
          expression role(source_path^"/args/"^string_of_int index)arg(incoming(ep endpoint.node_id port)))args
    |"rising"->source_type "event"(get "value_type" source);plain();output "events";
        require(actual=I.Observed_rising && List.length args=1)"Staged observed edge differs.";
        let rec evidence value=List.mem(text "op" value)["observe";"literal";"not";"all";"any"] && List.for_all evidence(items "args" value)in
        let rec observed value=text "op" value="observe" || List.exists observed(items "args" value)in
        require(evidence(List.hd args) && observed(List.hd args))"Staged rising must depend only on observed evidence.";
        let key=expression_identity source in
        (match List.assoc_opt key !edges with Some prior->require(prior=endpoint.node_id)"Staged rising expression has split edge memory."
         |None->require(not(List.exists(fun(_,id)->id=endpoint.node_id)!edges))"Distinct staged rising expressions share edge memory.";
             edges:= !edges@[key,endpoint.node_id]);
        expression role(source_path^"/args/0")(List.hd args)(incoming(ep endpoint.node_id "in"))
    |"effect_event"->source_type "event"(get "value_type" source);output "selected";
        let effect_id=match decoded.reference with Some value->value|None->Diagnostic.fail "policy_implementation_source_binding" "Missing effect event reference."in
        require(List.exists(fun(e:O.effect_spec)->e.effect_id=effect_id)behavior.effects && args=[] &&
          ref_matches source "ref" "Effect" effect_id && ref_matches source "scope" "Subject" subject.subject_id)
          "Staged event changes its original effect/subject.";
        let phase=match decoded.phase with Some "completed"->I.Completed|Some "failed"->I.Failed|Some "timed_out"->I.Timed_out
          |_->Diagnostic.fail "policy_implementation_source_binding" "Unsupported staged transition effect phase."in
        require(actual=I.Event_select phase)"Staged event selector differs from the exact source phase.";
        wire(ep(effect_anchor effect_id).bank "events")(ep endpoint.node_id "events")
    |_->Diagnostic.fail ~path:source_path "policy_implementation_source_binding" "Unsupported staged source expression.");
    let disposition=if List.mem operator["literal";"parameter"]then I.Constant else I.Executable in
    record ~disposition role source_path [endpoint];
    expressions:=({source_path;source_expression=source;endpoint}:expression)::!expressions in
  let arbiter=(List.hd anchors).arbiter in
  let lane_count=if finite_machine then List.length behavior.transitions else 7 in
  require(List.for_all(fun(t:B.transition)->t.arbiter=arbiter)anchors && primitive arbiter=I.Exclusive_arbiter lane_count)
    "Staged machine requires one exact exclusive lane per source transition.";
  record I.Declaration(path source_machine.machine_id^"/arbitration")
    (List.mapi(fun index _->ep arbiter("out"^string_of_int index))anchors);
  let guards=ref [] in
  List.iteri(fun index(t:O.transition)->
    let anchor=List.nth anchors index and source=raw t.transition_id and source_path=path t.transition_id in
    let correlation=if t.on.op="effect_event"then I.Retained_attempt else I.Unbound in
    require(anchor.lane=index && primitive anchor.gate=I.Transition_gate{source=t.source;correlation} &&
      primitive anchor.commit=I.Transition_commit{destination=t.destination;writes=0;requests=List.length t.effects})
      "Staged gate/commit changes source state, correlation, destination or effect count.";
    wire(ep machine_anchor.bank "snapshot")(ep anchor.gate "machine");
    wire(ep anchor.gate "candidate")(ep arbiter("in"^string_of_int index));
    wire(ep arbiter("out"^string_of_int index))(ep anchor.commit "grant");
    wire(ep anchor.commit "machine_write")(ep machine_anchor.bank("write"^string_of_int index));
    expression I.Predicate(source_path^"/on")(get "on" source)(incoming(ep anchor.gate "on"));
    let guard=incoming(ep anchor.gate "guard")in
    expression I.Predicate(source_path^"/when")(get "when" source)guard;guards:= !guards@[t.transition_id,guard];
    record I.Declaration source_path ([ep anchor.gate "candidate";ep arbiter("out"^string_of_int index)]@outputs(node anchor.commit)))behavior.transitions;
  let effect_values=List.map(fun(source_effect:O.effect_spec)->
    let anchor=effect_anchor source_effect.effect_id and source=raw source_effect.effect_id in
    let initiators=List.filter(fun(t:O.transition)->List.mem source_effect.effect_id t.effects)behavior.transitions in
    require((if multi_site then initiators<>[] else List.length initiators=1) &&
      List.for_all(fun(t:O.transition)->t.effects=[source_effect.effect_id] && t.machine=source_machine.machine_id)initiators &&
      source_effect.executor=role.role_id && source_effect.subject=subject.subject_id &&
      source_effect.lifecycle.on_loss="continue" && Json.equal bridge.operation(get "contract" source))
      "Effects must retain their exact profile-authorized initiating sites, machine and original product-operation contract.";
    let timeout=match source_effect.lifecycle.timeout with Some value->ticks value|None->Diagnostic.fail "policy_implementation_source_binding" "Staged effect requires a timeout."in
    let authorization=match source_effect.lifecycle.authorization with "continuous"->I.Continuous|"initiation"->I.At_initiation
      |_->Diagnostic.fail "policy_implementation_source_binding" "Unsupported staged authorization."in
    let on_unknown=match source_effect.lifecycle.on_unknown with "continue"->I.Continue|"defer"->I.Defer
      |_->Diagnostic.fail "policy_implementation_source_binding" "Unsupported staged authorization uncertainty."in
    require(match primitive anchor.bank with
      |I.Attempt_bank value when not multi_site->value.timeout_ticks=timeout && value.authorization=authorization &&
        value.on_unknown=on_unknown && value.capacity>=domain.logical_limits.max_source_attempts
      |I.Attempt_bank_sites value when multi_site->value.sites=List.length initiators && value.timeout_ticks=timeout &&
        value.authorization=authorization && value.on_unknown=on_unknown && value.capacity>=domain.logical_limits.max_source_attempts
      |_->false)
      "Attempt bank sites, lifecycle or shared bounded capacity differ from the original effect.";
    external_input anchor.feedback I.Feedback_input(ep anchor.bank "feedback");
    let argument=singleton "staged product argument"(items "parameters" source)in
    require(text "name" argument="product" && text "op"(get "value" argument)="parameter")"Staged effect must use one fixed product argument.";
    let product_output=ref None in
    let request_sites=List.mapi(fun index(initiator:O.transition)->
      let action=transition_anchor initiator.transition_id and guard=List.assoc initiator.transition_id !guards in
      let suffix=if multi_site then string_of_int index else ""in
      wire(ep action.commit "request0")(ep anchor.bank("request"^suffix));
      wire guard(ep anchor.bank("authorization"^suffix));
      let output=incoming(ep action.commit "product0")in
      (match !product_output with
       |None->expression I.Effect_parameter(path source_effect.effect_id^"/parameters/0/value")(get "value" argument)output;
         product_output:=Some output
       |Some expected->require(output=expected)"Repeated request sites must read the same original fixed product endpoint.");
      ({initiating_rule=initiator.transition_id;gate=action.gate;guard}:effect_site))initiators in
    let first=List.hd request_sites in
    record I.Lifecycle(path source_effect.effect_id)(outputs(node anchor.bank));
    record I.Lifecycle(path source_effect.effect_id^"/lifecycle")(outputs(node anchor.bank));
    ({source=source_effect.effect_id;bank=anchor.bank;feedback=anchor.feedback;initiating_rule=first.initiating_rule;
      gate=first.gate;guard=first.guard;request_sites;product_parameter=text "name" argument;
      machine=Some source_machine.machine_id}:effect_binding))behavior.effects in
  require(List.filter_map(fun(n:I.node)->match n.model.primitive with I.Transition_gate _->Some n.node_id|_->None)nodes=
    List.map(fun(t:B.transition)->t.gate)anchors)"Staged gate-node order changes original transition/attempt order.";
  require(List.filter_map(fun(n:I.node)->if n.model.primitive=I.Observed_rising then Some n.node_id else None)nodes=List.map snd !edges)
    "Staged rising-memory order differs from original event order.";
  let group=singleton "staged atomic group"(I.atomic_groups implementation)in
  require(group.arbiter=arbiter && group.commits=List.map(fun(t:B.transition)->t.commit)anchors)
    "Staged atomic group changes source transition membership/order.";
  (if multi_product then List.iter(fun(id,_)->
    let targets=Option.value(List.assoc_opt id !product_targets)~default:[]in
    require(List.length targets=1)"Every fixed original product must retain its own one graph output.";
    record ~disposition:I.Constant I.Effect_parameter(path id)targets)products
  else (
    require(!parameter_targets<>[])"Staged product parameter has no actual use.";
    record ~disposition:I.Constant I.Effect_parameter(path parameter_id)!parameter_targets));
  let rec requirement_expressions source_path value=match value with
    |Json.Object fields->
        if List.assoc_opt "$type" fields=Some(str "Expr")then(
          if text "op" value="rising"then require(List.mem_assoc(expression_identity value)!edges)
            "Requirement-only rising memory is outside the staged family.";
          record ~disposition:I.Obligation I.Requirement source_path []);
        List.iter(fun(key,value)->requirement_expressions(source_path^"/"^key)value)fields
    |Json.Array values->List.iteri(fun index value->requirement_expressions(source_path^"/"^string_of_int index)value)values
    |_->()in
  List.iter(fun(d:D.declaration)->match d.kind with
    |D.Role|D.Subject|D.Encounter->record ~disposition:I.Retained_metadata I.Declaration d.path []
    |D.Clock->record ~disposition:I.Retained_metadata I.Clock d.path []
    |D.Requirement->record ~disposition:I.Obligation I.Requirement d.path [];requirement_expressions d.path d.value
    |D.Observation|D.Effect|D.Machine|D.Transition|D.Parameter->()
    |_->Diagnostic.fail "policy_implementation_source_binding" "Original declaration lacks a staged interpretation.")declarations;
  require(Names.cardinal !used_nodes=List.length nodes && Names.cardinal !used_wires=List.length(I.wires implementation) &&
    Names.cardinal !used_inputs=List.length(I.inputs implementation))"Staged actual graph has orphan nodes, wires or external inputs.";
  let expected=List.sort(fun(a:I.occurrence)(b:I.occurrence)->String.compare a.source_path b.source_path)!occurrences in
  I.check_occurrence_inventory ~expected:(List.map(fun(o:I.occurrence)->o.source_path)expected)implementation;
  require(I.occurrences implementation=expected)"Staged source occurrences differ from independent reconstruction.";
  let environment_value={executor=domain.executor_identity;horizon_ticks=domain.horizon_ticks;
    slots=List.map(fun(s:F.encounter)->({identity=s.identity;target=s.target;start_tick=s.start_tick}:slot))domain.encounters}in
  let observation_values=[{source=observation_source.observation_id;bank=observation_anchor.bank;input=observation_anchor.input;
    observer=role.role_id;subject=subject.subject_id}]in
  let machine_values=[{source=source_machine.machine_id;bank=machine_anchor.bank}]in
  let transition_values=List.map(fun(t:O.transition)->let anchor=transition_anchor t.transition_id in
    ({source=t.transition_id;machine=t.machine;gate=anchor.gate;arbiter=anchor.arbiter;lane=anchor.lane;commit=anchor.commit;
      trigger=incoming(ep anchor.gate "on");source_trigger=t.on}:transition))behavior.transitions in
  let expression_values=List.sort(fun(a:expression)(b:expression)->String.compare a.source_path b.source_path)!expressions in
  let report_value=obj["schema_version",str(if multi_site then "biocompiler.policy_implementation_binding_report.v0.7"
      else if finite_machine then "biocompiler.policy_implementation_binding_report.v0.5"
      else if multi_product then "biocompiler.policy_implementation_binding_report.v0.4" else "biocompiler.policy_implementation_binding_report.v0.2");
    "profile",str(if multi_site then B.multi_site_profile else if finite_machine then B.finite_machine_profile else if multi_product then B.multi_product_profile else B.staged_profile);
    "observable_profile",str(if multi_site then I.multi_site_observable_profile else I.staged_observable_profile);"status",str "source_graph_bound";
    "request_fingerprint",str(R.fingerprint request);"catalog_bindings_digest",str(R.catalog_bindings_digest request);
    "catalog_entry",str bridge.entry_id;"catalog_entry_digest",str bridge.entry_digest;
    "source_artifact_digest",str authority.source_artifact_digest;"descriptors_digest",str authority.descriptors_digest;
    "operating_domain_digest",str authority.domain_digest;"implementation_catalog_digest",str authority.implementation_catalog_digest;
    "implementation_library_digest",str authority.library_digest;"implementation_fingerprint",str(I.fingerprint implementation);
    "proposed_binding_fingerprint",str(B.fingerprint proposed);"source_admission",A.report admitted;
    "source_occurrences",get "occurrences"(I.to_json implementation);
    "interpreted_outputs",arr(List.map(fun(n:I.node)->obj["node",str n.node_id;"operation",str(I.primitive_name n.model.primitive);
      "outputs",arr(List.map endpoint_json(outputs n))])nodes);
    "state_encoding",str "exact_ordered_source_labels";"execution",str "not_performed";"preservation",str "unassessed";
    "requirements",str "unassessed";"material",str "unassessed";"target_status",str "unassessed";
    "artifact",str "withheld";"export",str "withheld"]in
  {admitted_value=admitted;implementation_value=implementation;environment_value;observation_values;
   state_values=[];effect_values;rule_values=[];machine_values;transition_values;expression_values;report_value}

let check_network_metered ~charge:parent_charge ~admitted ~implementation ~proposed =
  (* This independent reconstruction has its own finite work ceiling even when
     reached through the historical unmetered [check] interface. *)
  let budget=Work_budget.create ~profile:B.network_profile
    ~error_code:"policy_network_binding_resource_limit" ~maximum:16000000 () in
  let charge value=parent_charge value;Work_budget.charge budget value in
  let module Meter=Policy_generation_meter.Make(struct let charge=charge end) in
  let module List=Meter.List in
  let module String=Meter.String in
  let module Json=Meter.Json in
  let module Canonical=Meter.Canonical in
  let module D=Meter.Document in
  let module O=Meter.Operational in
  let module Names=Meter.Seen in
  let ( ^ )=Meter.append_string and ( @ )=List.append in
  let get=O.get and text=O.text and items=O.list in
  let nulls ?path fields value=List.iter(fun key->require ?path (get key value=Json.Null)
    ("Network source field needs separately implemented semantics: "^key))fields in
  let source_type kind value=require(text "kind" value=kind && get "unit" value=Json.Null && get "entity_kind" value=Json.Null)
    "Network source requires exact truth/event/fixed-product types." in
  let outputs (node:I.node)=List.filter_map(fun(p:I.port)->
    if p.direction=I.Output then Some(ep node.node_id p.port_id)else None)(I.ports node.model.primitive) in
  let request=A.request admitted and behavior=A.behavior admitted in
  require(R.is_network request && B.is_network proposed)"Network request and binding families must agree.";
  let document=R.document request and domain=F.specification(A.operating_domain admitted)in
  Meter.preflight(I.to_json implementation);Meter.preflight(I.library_to_json(R.implementation_library request));
  Meter.preflight(B.to_json proposed);Meter.preflight(O.behavior_to_json behavior);
  let implementation=I.of_json ~library:(R.implementation_library request)(I.to_json implementation)in
  require(I.implementation_profile implementation=I.staged_profile &&
    I.implementation_observable_profile implementation=I.staged_observable_profile)
    "Network binding requires the unchanged staged primitive and observable profiles.";
  let authority:I.authority={source_artifact_digest=D.artifact_digest document;
    descriptors_digest=O.descriptors_digest(R.definitions request);domain_digest=Canonical.fingerprint(F.to_json(R.operating_domain request));
    implementation_catalog_digest=Canonical.fingerprint(get "implementations"(D.to_json document));
    library_digest=Canonical.fingerprint(I.library_to_json(R.implementation_library request))}in
  I.check_authority ~expected:authority implementation;
  let role=singleton "network executor" behavior.roles and encounter=singleton "network encounter" behavior.encounters
  and subject=singleton "network subject" behavior.subjects and clock=singleton "network clock" behavior.clocks
  and parameter=singleton "network fixed product" behavior.parameters in
  let bounded low high values=let count=List.length values in count>=low && count<=high in
  require(behavior.rules=[] && bounded 2 4 behavior.observations && bounded 2 4 behavior.machines &&
    bounded 0 4 behavior.stores && bounded 1 8 behavior.effects && bounded 1 32 behavior.transitions)
    "Network source cardinalities differ from the closed bounded family.";
  let declarations=D.declarations document in
  let declaration identity=match List.find_opt(fun(d:D.declaration)->String.equal d.id identity)declarations with
    |Some value->value|None->Diagnostic.fail "policy_implementation_source_binding" "Network source declaration is absent."in
  let raw identity=(declaration identity).value and path identity=(declaration identity).path in
  require(encounter.executor=role.role_id && encounter.target=subject.subject_id && encounter.termination="explicit_event" &&
    subject.executor=Some role.role_id && subject.encounter=Some encounter.encounter_id)
    "Network source changes executor, subject or encounter ownership.";
  nulls ["domain"](raw subject.subject_id);
  require(clock.clock_id=domain.clock && role.role_id=domain.executor_role && List.length domain.encounters=2 &&
    List.for_all(fun(s:F.encounter)->s.declaration=encounter.encounter_id)domain.encounters &&
    List.mem(text "basis"(raw clock.clock_id))["logical";"availability"] &&
    text "simultaneous"(raw clock.clock_id)="atomic_batch")"Network clock or ordered encounter domain differs.";
  let layout=I.slot_layout implementation in
  require(layout.encounter_id=encounter.encounter_id && layout.slots=2)"Network graph must preserve both encounter slots.";
  let bridge=singleton "network catalog bridge"(R.catalog_bindings request)in
  require(bridge.entry_id=B.catalog_entry proposed)"Network source binding selects another catalog entry.";
  let observations=B.observations proposed and states=B.states proposed and machines=B.machines proposed
  and transitions=B.transitions proposed and effects=B.effects proposed in
  require(B.rules proposed=[] &&
    List.map(fun(a:B.observation)->a.source)observations=List.map(fun(a:O.observation)->a.observation_id)behavior.observations &&
    List.map(fun(a:B.state)->a.source)states=List.map(fun(a:O.state_store)->a.state_id)behavior.stores &&
    List.map(fun(a:B.machine)->a.source)machines=List.map(fun(a:O.machine)->a.machine_id)behavior.machines &&
    List.map(fun(a:B.transition)->a.source)transitions=List.map(fun(a:O.transition)->a.transition_id)behavior.transitions &&
    List.map(fun(a:B.effect_binding)->a.source)effects=List.map(fun(a:O.effect_spec)->a.effect_id)behavior.effects)
    "Network anchors must cover each complete source inventory once in original declaration order.";
  let machine_source id=List.find(fun(m:O.machine)->String.equal m.machine_id id)behavior.machines in
  let machine_anchor id=List.find(fun(m:B.machine)->String.equal m.source id)machines
  and observation_anchor id=List.find(fun(v:B.observation)->String.equal v.source id)observations
  and state_anchor id=List.find(fun(v:B.state)->String.equal v.source id)states
  and transition_anchor id=List.find(fun(v:B.transition)->String.equal v.source id)transitions
  and effect_anchor id=List.find(fun(v:B.effect_binding)->String.equal v.source id)effects in
  let own_transitions id=List.filter(fun(t:O.transition)->String.equal t.machine id)behavior.transitions in
  let policy_key id=Canonical.encode(get "arbitration"(raw id))in
  let group_keys=List.fold_left(fun keys(m:O.machine)->let key=policy_key m.machine_id in
    if List.mem key keys then keys else keys@[key])[]behavior.machines in
  let group_transitions key=List.filter(fun(t:O.transition)->String.equal(policy_key t.machine)key)behavior.transitions in
  let nodes=I.nodes implementation and used_nodes=ref Names.empty and used_wires=ref Names.empty
  and used_inputs=ref Names.empty and occurrences=ref [] and expressions=ref []in
  require(List.length nodes<=64)"Network graph exceeds its sixty-four-node bound.";
  let node id=match List.find_opt(fun(n:I.node)->String.equal n.node_id id)nodes with
    |Some value->used_nodes:=Names.add id !used_nodes;value
    |None->Diagnostic.fail "policy_implementation_source_binding" "Network anchor names an absent actual node."in
  let primitive id=(node id).model.primitive in
  List.iter(fun(n:I.node)->A.require_model admitted ~entry_id:bridge.entry_id n.model.identity;
    require(match n.model.replication with
      |I.Encounter_slots value->value.layout_id=layout.layout_id && value.slots=2
      |I.Executor->(match n.model.primitive with I.Truth_constant _|I.Product_constant _|I.Truth_not|I.Truth_all _|I.Truth_any _->true|_->false))
      "Network mutable/control nodes require exact encounter replication.")nodes;
  let incoming consumer=match List.find_opt(fun(w:I.wire)->w.consumer=consumer)(I.wires implementation)with
    |Some wire->used_wires:=Names.add(endpoint_key consumer)!used_wires;wire.producer
    |None->Diagnostic.fail "policy_implementation_source_binding" "Network source operand has no actual wire."in
  let wire producer consumer=require(incoming consumer=producer)"Network wiring changes an original operand, writer or owner."in
  let external_input id kind consumer=
    let value=singleton "network external input"(List.filter(fun(i:I.external_input)->String.equal i.input_id id)(I.inputs implementation))in
    require(value.input_kind=kind && value.consumer=consumer)"Network external input changes its source kind or bank.";
    used_inputs:=Names.add id !used_inputs in
  let record ?(disposition=I.Executable) role source_path targets=
    require(not(List.exists(fun(o:I.occurrence)->String.equal o.source_path source_path)!occurrences))
      "Duplicate independently reconstructed network occurrence.";
    occurrences:=({I.source_path=source_path;role;disposition;targets}:I.occurrence)::!occurrences in
  let ticks duration=let exact=Q.div duration clock.resolution in
    require(Q.sign exact>0 && Z.equal(Q.den exact)Z.one && Z.compare(Q.num exact)(Z.of_int 10000)<=0)
      "Network durations require bounded positive integral clock ticks.";Z.to_int(Q.num exact)in
  require(List.length(List.sort_uniq String.compare(List.map(fun(o:O.observation)->o.coherence)behavior.observations))=
    List.length behavior.observations)"Network observations require distinct original coherence groups without frame joining.";
  List.iter2(fun(o:O.observation)(anchor:B.observation)->
    require(o.value_type=O.Truth_type && o.observer=role.role_id && o.subject=subject.subject_id &&
      o.clock=clock.clock_id && o.coverage="event")"Network observation ownership, truth type or event coverage differs.";
    source_type "truth"(get "value_type"(raw o.observation_id));
    require(primitive anchor.bank=I.Evidence_bank{freshness_ticks=ticks o.freshness})"Network observation freshness differs.";
    external_input anchor.input I.Evidence_input(ep anchor.bank "samples");
    record I.Declaration(path o.observation_id)(outputs(node anchor.bank)))behavior.observations observations;
  List.iter2(fun(m:O.machine)(anchor:B.machine)->let own=own_transitions m.machine_id in
    require(bounded 2 16 m.states && own<>[] && m.executor=role.role_id && m.scope=O.Encounter encounter.encounter_id &&
      m.lifetime="encounter" && m.arbitration.mode="priority" && m.arbitration.tie="declared_order" && m.arbitration.write_conflict="reject")
      "Network machine requires bounded states, owned transitions, encounter lifetime and explicit priority arbitration.";
    require(match primitive anchor.bank with I.Machine_bank value->value.states=m.states && value.initial=m.initial &&
      value.terminal=m.terminal && value.writers=List.length own && value.retained_capacity>=1|_->false)
      "Network machine bank changes source state labels, initial/terminal states or local writer count.";
    record I.Declaration(path m.machine_id)[ep anchor.bank "snapshot"])behavior.machines machines;
  let assignments=List.concat_map(fun(t:O.transition)->List.mapi(fun index(a:O.assignment)->t.transition_id,index,a.state)t.assignments)behavior.transitions in
  List.iter2(fun(s:O.state_store)(anchor:B.state)->
    let writers=List.filter(fun(_,_,id)->String.equal id s.state_id)assignments in
    let owners=List.sort_uniq String.compare(List.map(fun(id,_,_)->
      (List.find(fun(t:O.transition)->String.equal t.transition_id id)behavior.transitions).machine)writers)in
    require(writers<>[] && List.length owners=1 && s.value_type=O.Truth_type &&
      s.scope=O.Encounter encounter.encounter_id && s.lifetime="encounter" && s.capacity>=2 && s.reset=None &&
      text "overflow"(raw s.state_id)="reject" && text "inheritance"(raw s.state_id)="not_applicable")
      "Network truth stores require exactly one writer machine, encounter capacity/lifetime and no reset predicate.";
    nulls ["duration";"coordination";"contract"](raw s.state_id);source_type "truth"(get "value_type"(raw s.state_id));
    let initial=match s.initial with O.Truth O.True->I.True | O.Truth O.False->I.False
      |_->Diagnostic.fail "policy_implementation_source_binding" "Network truth stores require a known initial Boolean."in
    require(primitive anchor.register=I.Truth_register{initial;writers=List.length writers})
      "Network register changes original initial value or complete ordered writer inventory.";
    record I.Declaration(path s.state_id)[ep anchor.register "value"])behavior.stores states;
  let parameter_raw=raw parameter.parameter_id in
  require(text "selection" parameter_raw="fixed")"Network product must be fixed.";
  nulls ["lower";"upper"]parameter_raw;source_type "text"(get "value_type" parameter_raw);
  let product=match parameter.value with O.Text value->value|_->Diagnostic.fail "policy_implementation_source_binding" "Network product must be text."in
  let parameter_targets=ref [] and edges=ref []in
  let ref_matches source key kind id=let value=get key source in
    value<>Json.Null && text "kind" value=kind && String.equal(O.ref_id value)id in
  let rec expression role source_path source (endpoint:I.endpoint)=
    charge 1;nulls ~path:source_path ["contract";"duration";"clock";"coverage";"binding"]source;
    let operator=text "op" source and args=items "args" source in
    let decoded=O.expression_of_json source and actual=primitive endpoint.node_id in
    let output port=require(endpoint.port_id=port)"Network expression names the wrong primitive output."in
    let plain ()=nulls ["ref";"scope";"value"]source in
    (match operator with
    |"observe"|"updated"->source_type (if operator="observe"then "truth"else "event")(get "value_type" source);
      let id=O.ref_id(get "ref" source)in
      require(List.exists(fun(v:B.observation)->String.equal v.source id)observations)"Network expression names an unmapped observation.";
      let anchor=observation_anchor id in
      require(args=[] && get "value" source=Json.Null && ref_matches source "ref" "Observation" id &&
        ref_matches source "scope" "Subject" subject.subject_id && endpoint=ep anchor.bank(if operator="observe"then "value"else "updated"))
        "Network observation expression changes its exact nominal source or endpoint."
    |"state"->source_type "truth"(get "value_type" source);let id=O.ref_id(get "ref" source)in
      require(List.exists(fun(v:B.state)->String.equal v.source id)states)"Network expression names an unmapped truth store.";
      require(args=[] && get "value" source=Json.Null && ref_matches source "ref" "StateStore" id &&
        ref_matches source "scope" "Encounter" encounter.encounter_id && endpoint=ep(state_anchor id).register "value")
        "Network state read changes its exact store or encounter."
    |"literal"->source_type "truth"(get "value_type" source);nulls ["ref";"scope"]source;require(args=[])"Network literal has operands.";
      let value=match decoded.value with Some(O.Truth value)->truth value|_->Diagnostic.fail "policy_implementation_source_binding" "Network literal must be truth."in
      output "out";require(actual=I.Truth_constant value)"Network truth constant differs."
    |"parameter"->source_type "text"(get "value_type" source);
      require(args=[] && ref_matches source "ref" "Parameter" parameter.parameter_id && get "scope" source=Json.Null && get "value" source=Json.Null)
        "Network effect changes the fixed original product parameter.";
      output "out";require(actual=I.Product_constant product)"Network fixed product differs.";
      if not(List.mem endpoint !parameter_targets)then parameter_targets:= !parameter_targets@[endpoint]
    |"not"|"all"|"any"->source_type "truth"(get "value_type" source);plain();output "out";
      require(match operator,actual with "not",I.Truth_not->List.length args=1
        |"all",I.Truth_all count|"any",I.Truth_any count->List.length args=count|_->false)
        "Network truth operation changes its source operator or arity.";
      List.iteri(fun index arg->expression role(source_path^"/args/"^string_of_int index)arg
        (incoming(ep endpoint.node_id(if operator="not"then "in"else "in"^string_of_int index))))args
    |"rising"->source_type "event"(get "value_type" source);plain();output "events";
      require(actual=I.Observed_rising && List.length args=1)"Network observed-edge primitive differs.";
      let rec evidence value=charge 1;List.mem(text "op" value)["observe";"literal";"not";"all";"any"] && List.for_all evidence(items "args" value)in
      let rec observed value=charge 1;text "op" value="observe" || List.exists observed(items "args" value)in
      require(evidence(List.hd args) && observed(List.hd args))"Network rising must depend only on observed truth evidence.";
      let key=Canonical.encode source in
      (match List.assoc_opt key !edges with Some prior->require(prior=endpoint.node_id)"Network rising expression has split edge memory."
       |None->require(not(List.exists(fun(_,id)->id=endpoint.node_id)!edges))"Distinct network rising expressions share edge memory.";
         edges:= !edges@[key,endpoint.node_id]);
      expression role(source_path^"/args/0")(List.hd args)(incoming(ep endpoint.node_id "in"))
    |"effect_event"->source_type "event"(get "value_type" source);output "selected";
      let id=O.ref_id(get "ref" source)in
      require(List.exists(fun(v:B.effect_binding)->String.equal v.source id)effects && args=[] &&
        ref_matches source "ref" "Effect" id && ref_matches source "scope" "Subject" subject.subject_id)
        "Network effect event changes its original effect or subject.";
      let phase=match decoded.phase with Some "completed"->I.Completed|Some "failed"->I.Failed|Some "timed_out"->I.Timed_out
        |_->Diagnostic.fail "policy_implementation_source_binding" "Unsupported network feedback phase."in
      require(actual=I.Event_select phase)"Network event selector changes the original phase.";
      wire(ep(effect_anchor id).bank "events")(ep endpoint.node_id "events")
    |_->Diagnostic.fail ~path:source_path "policy_implementation_source_binding" "Unsupported network source expression.");
    record ~disposition:(if List.mem operator["literal";"parameter"]then I.Constant else I.Executable)role source_path [endpoint];
    expressions:=({source_path;source_expression=source;endpoint}:expression)::!expressions in
  let groups=List.map(fun key->let members=group_transitions key in
    let first=List.hd members in let policy=(machine_source first.machine).arbitration in
    let ids=List.map(fun(t:O.transition)->t.transition_id)members in
    require(List.sort String.compare policy.order=List.sort String.compare ids)
      "Network priority order must cover its complete policy group exactly once.";
    let arbiter=(transition_anchor first.transition_id).arbiter in
    let lane id=let rec find index=function
      |[]->Diagnostic.fail "policy_implementation_source_binding" "Network priority participant is absent."
      |value::rest->if String.equal value id then index else find(index+1)rest in find 0 ids in
    require(List.for_all(fun(t:O.transition)->(transition_anchor t.transition_id).arbiter=arbiter)members &&
      primitive arbiter=I.Priority_arbiter(List.map lane policy.order))"Network arbitration topology changes complete source policy equality or priority.";
    key,arbiter,members)group_keys in
  require(List.length(List.sort_uniq String.compare(List.map(fun(_,arbiter,_)->arbiter)groups))=List.length groups)
    "Distinct network arbitration policies cannot share a primitive arbiter.";
  List.iter(fun(m:O.machine)->let _,arbiter,members=List.find(fun(key,_,_)->String.equal key(policy_key m.machine_id))groups in
    record I.Declaration(path m.machine_id^"/arbitration")
      (List.mapi(fun index _->ep arbiter("out"^string_of_int index))members))behavior.machines;
  let guards=ref []in
  List.iter(fun(t:O.transition)->let anchor=transition_anchor t.transition_id and source=raw t.transition_id and source_path=path t.transition_id in
    let machine=machine_source t.machine and bank=(machine_anchor t.machine).bank in
    require(not(List.mem t.source machine.terminal) && List.length t.effects<=1 && List.length t.assignments<=4 &&
      List.length(List.sort_uniq String.compare(List.map(fun(a:O.assignment)->a.state)t.assignments))=List.length t.assignments &&
      List.mem t.on.op["rising";"updated";"effect_event"])
      "Network transition changes terminal non-reentry, event subset or atomic action bounds.";
    (if t.on.op="effect_event"then let id=Option.get t.on.reference in
      let initiator=singleton "network feedback initiator"(List.filter(fun(v:O.transition)->List.mem id v.effects)behavior.transitions)in
      require(initiator.machine=t.machine)"Network feedback may only advance its initiating machine.");
    let _,arbiter,members=List.find(fun(key,_,_)->String.equal key(policy_key t.machine))groups in
    let index values=let rec find position=function
      |[]->Diagnostic.fail "policy_implementation_source_binding" "Network transition lacks its source writer/lane."
      |(value:O.transition)::rest->if value.transition_id=t.transition_id then position else find(position+1)rest in find 0 values in
    let lane=index members and writer=index(own_transitions t.machine)in
    let correlation=if t.on.op="effect_event"then I.Retained_attempt else I.Unbound in
    require(anchor.lane=lane && primitive anchor.gate=I.Transition_gate{source=t.source;correlation} &&
      primitive anchor.commit=I.Transition_commit{destination=t.destination;writes=List.length t.assignments;requests=List.length t.effects})
      "Network transition gate/commit changes state, correlation, destination or atomic action count.";
    wire(ep bank "snapshot")(ep anchor.gate "machine");wire(ep anchor.gate "candidate")(ep arbiter("in"^string_of_int lane));
    wire(ep arbiter("out"^string_of_int lane))(ep anchor.commit "grant");
    wire(ep anchor.commit "machine_write")(ep bank("write"^string_of_int writer));
    expression I.Predicate(source_path^"/on")(get "on" source)(incoming(ep anchor.gate "on"));
    let guard=incoming(ep anchor.gate "guard")in expression I.Predicate(source_path^"/when")(get "when" source)guard;
    guards:= !guards@[t.transition_id,guard];
    List.iteri(fun index(a:O.assignment)->let assignment_path=source_path^"/assignments/"^string_of_int index in
      let writers=List.filter(fun(_,_,id)->String.equal id a.state)assignments in
      let rec rank position=function
        |[]->Diagnostic.fail "policy_implementation_source_binding" "Network assignment writer is absent."
        |(id,ordinal,_)::rest->if id=t.transition_id && ordinal=index then position else rank(position+1)rest in
      wire(ep anchor.commit("write"^string_of_int index))(ep(state_anchor a.state).register("write"^string_of_int(rank 0 writers)));
      record I.State_write assignment_path [ep anchor.commit("write"^string_of_int index)];
      expression I.State_write(assignment_path^"/value")(get "value"(List.nth(items "assignments" source)index))
        (incoming(ep anchor.commit("value"^string_of_int index))))t.assignments;
    record I.Declaration source_path([ep anchor.gate "candidate";ep arbiter("out"^string_of_int lane)]@outputs(node anchor.commit)))behavior.transitions;
  let effect_values=List.map(fun(e:O.effect_spec)->let anchor=effect_anchor e.effect_id and source=raw e.effect_id in
    let initiator=singleton "network effect initiator"(List.filter(fun(t:O.transition)->List.mem e.effect_id t.effects)behavior.transitions)in
    require(initiator.effects=[e.effect_id] && e.executor=role.role_id && e.subject=subject.subject_id && e.lifecycle.on_loss="continue" &&
      Json.equal bridge.operation(get "contract" source))"Network effect changes its unique initiating site, recipient or original operation.";
    let timeout=match e.lifecycle.timeout with Some value->ticks value|None->Diagnostic.fail "policy_implementation_source_binding" "Network effects require explicit timeouts."in
    let authorization=match e.lifecycle.authorization with "initiation"->I.At_initiation|"continuous"->I.Continuous
      |_->Diagnostic.fail "policy_implementation_source_binding" "Unsupported network authorization."in
    let on_unknown=match e.lifecycle.on_unknown with "defer"->I.Defer|"continue"->I.Continue
      |_->Diagnostic.fail "policy_implementation_source_binding" "Unsupported network authorization uncertainty."in
    require(match primitive anchor.bank with I.Attempt_bank value->value.timeout_ticks=timeout && value.authorization=authorization &&
      value.on_unknown=on_unknown && value.capacity>=domain.logical_limits.max_source_attempts|_->false)
      "Network attempt lifecycle or capacity differs from its original source.";
    external_input anchor.feedback I.Feedback_input(ep anchor.bank "feedback");
    let action=transition_anchor initiator.transition_id and guard=List.assoc initiator.transition_id !guards in
    wire(ep action.commit "request0")(ep anchor.bank "request");wire guard(ep anchor.bank "authorization");
    let argument=singleton "network product argument"(items "parameters" source)in
    require(text "name" argument="product" && text "op"(get "value" argument)="parameter")"Network effect requires the original fixed product argument.";
    expression I.Effect_parameter(path e.effect_id^"/parameters/0/value")(get "value" argument)(incoming(ep action.commit "product0"));
    record I.Lifecycle(path e.effect_id)(outputs(node anchor.bank));record I.Lifecycle(path e.effect_id^"/lifecycle")(outputs(node anchor.bank));
    ({source=e.effect_id;bank=anchor.bank;feedback=anchor.feedback;initiating_rule=initiator.transition_id;
      gate=action.gate;guard;request_sites=[{initiating_rule=initiator.transition_id;gate=action.gate;guard}];
      product_parameter=text "name" argument;machine=Some initiator.machine}:effect_binding))behavior.effects in
  require(List.filter_map(fun(n:I.node)->match n.model.primitive with I.Evidence_bank _->Some n.node_id|_->None)nodes=List.map(fun(v:B.observation)->v.bank)observations &&
    List.filter_map(fun(n:I.node)->match n.model.primitive with I.Truth_register _->Some n.node_id|_->None)nodes=List.map(fun(v:B.state)->v.register)states &&
    List.filter_map(fun(n:I.node)->match n.model.primitive with I.Machine_bank _->Some n.node_id|_->None)nodes=List.map(fun(v:B.machine)->v.bank)machines &&
    List.filter_map(fun(n:I.node)->match n.model.primitive with I.Attempt_bank _->Some n.node_id|_->None)nodes=List.map(fun(v:B.effect_binding)->v.bank)effects &&
    List.filter_map(fun(n:I.node)->match n.model.primitive with I.Transition_gate _->Some n.node_id|_->None)nodes=List.map(fun(v:B.transition)->v.gate)transitions)
    "Network mutable/control node order differs from complete source declaration order.";
  require(List.filter_map(fun(n:I.node)->if n.model.primitive=I.Observed_rising then Some n.node_id else None)nodes=List.map snd !edges)
    "Network rising-memory order differs from original event order.";
  let atomic=I.atomic_groups implementation in
  require(List.length atomic=List.length groups)"Network atomic-group inventory differs from complete source policies.";
  List.iter2(fun(g:I.atomic_group)(_,arbiter,members)->require(g.arbiter=arbiter &&
    g.commits=List.map(fun(t:O.transition)->(transition_anchor t.transition_id).commit)members)
    "Network atomic groups change source policy membership or declaration order.")atomic groups;
  require(!parameter_targets<>[])"Network fixed product has no interpreted use.";
  record ~disposition:I.Constant I.Effect_parameter(path parameter.parameter_id)!parameter_targets;
  let rec requirement_expressions source_path value=charge 1;match value with
    |Json.Object fields->
      (if List.assoc_opt "$type" fields=Some(str "Expr")then(
        if text "op" value="rising"then require(List.mem_assoc(Canonical.encode value)!edges)"Network requirement adds unimplemented rising memory.";
        record ~disposition:I.Obligation I.Requirement source_path []));
      List.iter(fun(key,value)->requirement_expressions(source_path^"/"^key)value)fields
    |Json.Array values->List.iteri(fun index value->requirement_expressions(source_path^"/"^string_of_int index)value)values
    |_->()in
  List.iter(fun(d:D.declaration)->match d.kind with
    |D.Role|D.Subject|D.Encounter->record ~disposition:I.Retained_metadata I.Declaration d.path []
    |D.Clock->record ~disposition:I.Retained_metadata I.Clock d.path []
    |D.Requirement->record ~disposition:I.Obligation I.Requirement d.path [];requirement_expressions d.path d.value
    |D.Observation|D.State_store|D.Effect|D.Machine|D.Transition|D.Parameter->()
    |_->Diagnostic.fail "policy_implementation_source_binding" "Original declaration lacks a network interpretation.")declarations;
  require(Names.cardinal !used_nodes=List.length nodes && Names.cardinal !used_wires=List.length(I.wires implementation) &&
    Names.cardinal !used_inputs=List.length(I.inputs implementation))"Network actual graph has orphan nodes, wires or external inputs.";
  let expected=List.sort(fun(a:I.occurrence)(b:I.occurrence)->String.compare a.source_path b.source_path)!occurrences in
  Meter.preflight(I.to_json implementation);
  I.check_occurrence_inventory ~expected:(List.map(fun(o:I.occurrence)->o.source_path)expected)implementation;
  require(I.occurrences implementation=expected)"Network source occurrences differ from independent reconstruction.";
  let environment_value={executor=domain.executor_identity;horizon_ticks=domain.horizon_ticks;
    slots=List.map(fun(s:F.encounter)->({identity=s.identity;target=s.target;start_tick=s.start_tick}:slot))domain.encounters}in
  let observation_values=List.map2(fun(o:O.observation)(v:B.observation)->
    ({source=o.observation_id;bank=v.bank;input=v.input;observer=o.observer;subject=o.subject}:observation))behavior.observations observations
  and state_values=List.map(fun(v:B.state)->({source=v.source;register=v.register}:state))states
  and machine_values=List.map(fun(v:B.machine)->({source=v.source;bank=v.bank}:machine))machines in
  let transition_values=List.map(fun(t:O.transition)->let v=transition_anchor t.transition_id in
    ({source=t.transition_id;machine=t.machine;gate=v.gate;arbiter=v.arbiter;lane=v.lane;commit=v.commit;
      trigger=incoming(ep v.gate "on");source_trigger=t.on}:transition))behavior.transitions in
  let expression_values=List.sort(fun(a:expression)(b:expression)->String.compare a.source_path b.source_path)!expressions in
  let report_value=obj["schema_version",str "biocompiler.policy_implementation_binding_report.v0.6";
    "profile",str B.network_profile;"observable_profile",str I.staged_observable_profile;"status",str "source_graph_bound";
    "request_fingerprint",str(R.fingerprint request);"catalog_bindings_digest",str(R.catalog_bindings_digest request);
    "catalog_entry",str bridge.entry_id;"catalog_entry_digest",str bridge.entry_digest;
    "source_artifact_digest",str authority.source_artifact_digest;"descriptors_digest",str authority.descriptors_digest;
    "operating_domain_digest",str authority.domain_digest;"implementation_catalog_digest",str authority.implementation_catalog_digest;
    "implementation_library_digest",str authority.library_digest;"implementation_fingerprint",str(Canonical.fingerprint(I.to_json implementation));
    "proposed_binding_fingerprint",str(Canonical.fingerprint(B.to_json proposed));"source_admission",A.report admitted;
    "source_occurrences",get "occurrences"(I.to_json implementation);
    "interpreted_outputs",arr(List.map(fun(n:I.node)->obj["node",str n.node_id;"operation",str(I.primitive_name n.model.primitive);
      "outputs",arr(List.map endpoint_json(outputs n))])nodes);
    "state_encoding",str "exact_ordered_source_labels";"execution",str "not_performed";"preservation",str "unassessed";
    "requirements",str "unassessed";"material",str "unassessed";"target_status",str "unassessed";
    "artifact",str "withheld";"export",str "withheld"]in
  Meter.preflight report_value;
  {admitted_value=admitted;implementation_value=implementation;environment_value;observation_values;state_values;
    effect_values;rule_values=[];machine_values;transition_values;expression_values;report_value}

let check ~admitted ~implementation ~proposed =
  require(R.is_network(A.request admitted)=B.is_network proposed)
    "Original realization and proposed binding must use the same explicit network family.";
  require(R.is_multi_site(A.request admitted)=B.is_multi_site proposed)
    "Original realization and proposed binding must use the same explicit multi-site family.";
  require(R.is_finite_machine(A.request admitted)=B.is_finite_machine proposed)
    "Original realization and proposed binding must use the same explicit finite-machine family.";
  require(R.is_multi_product(A.request admitted)=B.is_multi_product proposed)
    "Original realization and proposed binding must use the same explicit multi-product staged family.";
  require(R.is_two_observation(A.request admitted)=B.is_two_observation proposed)
    "Original realization and proposed binding must use the same explicit two-observation family.";
  if B.is_network proposed then check_network_metered ~charge:Policy_generation_meter.no_charge ~admitted ~implementation ~proposed
  else if B.is_staged proposed then check_staged ~admitted ~implementation ~proposed
  else check_legacy ~admitted ~implementation ~proposed

let implementation value=value.implementation_value
let admitted_inputs value=value.admitted_value
let environment value=value.environment_value
let observations value=value.observation_values
let states value=value.state_values
let effects value=value.effect_values
let rules value=value.rule_values
let machines value=value.machine_values
let transitions value=value.transition_values
let activations value=value.rule_values @ List.map(fun(t:transition)->
  ({source=t.source;gate=t.gate;arbiter=t.arbiter;lane=t.lane;commit=t.commit;
    trigger=t.trigger;source_trigger=t.source_trigger}:rule))value.transition_values
let expressions value=value.expression_values
let report value=value.report_value

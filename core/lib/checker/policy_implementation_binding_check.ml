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
type effect_binding = { source:string; bank:string; feedback:string; initiating_rule:string;
  gate:string; guard:I.endpoint; product_parameter:string }
type rule = { source:string; gate:string; arbiter:string; lane:int; commit:string;
  trigger:I.endpoint; source_trigger:O.expression }
type expression = { source_path:string; source_expression:Json.t; endpoint:I.endpoint }
type checked_binding = { admitted_value:A.admitted_inputs; implementation_value:I.t; environment_value:environment;
  observation_values:observation list; state_values:state list; effect_values:effect_binding list;
  rule_values:rule list; expression_values:expression list; report_value:Json.t }
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

let check ~admitted ~implementation ~proposed =
  let request=A.request admitted and behavior=A.behavior admitted in
  let document=R.document request and domain=F.specification(A.operating_domain admitted)in
  (* Re-decode the actual graph against original external authority. Neither
     graph-carried pins nor a prior producer receipt can select its models. *)
  let implementation=I.of_json ~library:(R.implementation_library request)(I.to_json implementation)in
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
  and observation_source=singleton "truth observation" behavior.observations
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
  let observation_anchor=singleton "observation anchor"(B.observations proposed)
  and effect_anchor=singleton "effect anchor"(B.effects proposed)in
  require(observation_anchor.source=observation_source.observation_id && effect_anchor.source=effect_source.effect_id)
    "Source observation/effect inventory differs from proposed anchors.";
  require(observation_source.value_type=O.Truth_type && observation_source.observer=role.role_id &&
    observation_source.subject=subject.subject_id && observation_source.clock=clock.clock_id &&
    observation_source.coverage="event" && observation_source.coherence="frame")
    "Only encounter-local event evidence with frame coherence is supported by this graph profile.";
  source_type "truth"(get "value_type"(raw observation_source.observation_id));
  require(primitive observation_anchor.bank=I.Evidence_bank{freshness_ticks=ticks observation_source.freshness})
    "Evidence-bank freshness or operation differs from original observation.";
  external_input observation_anchor.input I.Evidence_input(ep observation_anchor.bank "samples");
  record I.Declaration(path observation_source.observation_id)(outputs(node observation_anchor.bank));
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
  let rec check_expression role source_path source endpoint =
    raw_expr_fields source_path source;
    let expression=O.expression_of_json source in
    let operator=expression.op and args=items "args" source in
    let actual=primitive endpoint.I.node_id in
    let plain ()=nulls ~path:source_path ["ref";"scope";"value"]source in
    let output port=require(endpoint.port_id=port)"Expression is bound to the wrong primitive output."in
    (match operator with
    |"observe"->source_type ~path:source_path "truth"(get "value_type" source);
        require(args=[] && get "value" source=Json.Null &&
          ref_matches source "ref" "Observation" observation_source.observation_id &&
          ref_matches source "scope" "Subject" subject.subject_id && endpoint=ep observation_anchor.bank "value")
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
  let observation_values=[{source=observation_source.observation_id;bank=observation_anchor.bank;input=observation_anchor.input;
    observer=role.role_id;subject=subject.subject_id}]
  and state_values=List.map(fun(s:B.state)->({source=s.source;register=s.register}:state))(B.states proposed)
  and rule_values=List.map(fun(r:B.rule)->
    let source=List.find(fun(s:O.rule)->s.rule_id=r.source)behavior.rules in
    ({source=r.source;gate=r.gate;arbiter=r.arbiter;lane=r.lane;commit=r.commit;
      trigger=incoming(ep r.gate "on");source_trigger=source.on}:rule))anchors in
  let effect_values=[{source=effect_source.effect_id;bank=effect_anchor.bank;feedback=effect_anchor.feedback;
    initiating_rule=initiator.rule_id;gate=initiating_anchor.gate;guard=List.assoc initiator.rule_id !guards;
    product_parameter=text "name" argument}]in
  let expression_values=List.sort(fun(a:expression)(b:expression)->String.compare a.source_path b.source_path)!expressions in
  let report_value=obj[
    "schema_version",str "biocompiler.policy_implementation_binding_report.v0.1";"profile",str profile;
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
   rule_values;expression_values;report_value}
let implementation value=value.implementation_value
let admitted_inputs value=value.admitted_value
let environment value=value.environment_value
let observations value=value.observation_values
let states value=value.state_values
let effects value=value.effect_values
let rules value=value.rule_values
let expressions value=value.expression_values
let report value=value.report_value

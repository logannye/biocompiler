open Bioc_wire
module A = Bioc_checker.Policy_realization_admission
module I = Bioc_domain.Policy_implementation
module B = Bioc_domain.Policy_implementation_binding
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module R = Bioc_domain.Policy_realization_request
module F = Bioc_domain.Policy_operating_domain
module P = Bioc_domain.Pinned_identity
module Typed = Bioc_domain.Policy_admitted_ir
type finite_expression =
  | Finite_truth of Typed.truth_expression
  | Finite_integer of Typed.integer_expression
  | Finite_text of Typed.text_expression
  | Finite_quantity of Typed.quantity_expression
  | Finite_event of Typed.event_expression
let s value=Json.String value
let o value=Json.Object value
let a value=Json.Array value
let supported condition message=Diagnostic.require condition "policy_staged_lowering_unsupported" message
let one label=function [value]->value|_->Diagnostic.fail "policy_staged_lowering_unsupported" ("Staged lowering requires one "^label^".")
let endpoint node port=o["node",s node;"port",s port]
let reference kind id=o["$type",s "Ref";"kind",s kind;"id",s id]
let truth=function O.True->I.True|O.False->I.False|O.Unknown->I.Unknown

let lower_metered ~charge ~admitted ~library =
  let module Meter = Bioc_checker.Policy_generation_meter.Make (struct let charge = charge end) in
  let module List = Meter.List in
  let module String = Meter.String in
  let module Json = Meter.Json in
  let module Canonical = Meter.Canonical in
  let module O = Meter.Operational in
  let ( ^ ) = Meter.append_string and ( @ ) = List.append in
  let get key raw=Json.field key(Json.object_fields raw)in
  let text key raw=Json.string(get key raw)in
  let rows key raw=Json.array(get key raw)in
  let absent keys raw=List.iter(fun key->supported(get key raw=Json.Null)("Unsupported staged source field: "^key))keys in
  let type_is kind raw=supported(text "kind" raw=kind && get "unit" raw=Json.Null && get "entity_kind" raw=Json.Null)
    "Staged lowering needs exact truth/event/product types."in
  charge 1;
  let request=A.request admitted and behavior=A.behavior admitted in
  let finite_program=A.finite_program admitted in
  let typed_declaration id=match finite_program with
    |None->None
    |Some program->Some(Typed.declaration(List.find(fun instruction->
        String.equal(Typed.name(Typed.declaration instruction))id)(Typed.instructions program)))in
  let scalar_expression=function
    |Typed.Truth value->Finite_truth value|Typed.Integer value->Finite_integer value
    |Typed.Text value->Finite_text value|Typed.Quantity value->Finite_quantity value in
  let typed_roots=match finite_program with None->[]|Some program->
    List.concat_map(fun instruction->let location=Typed.source_path instruction in
      match Typed.declaration instruction with
      |Typed.Transition_declaration value->
          [location^"/on",Finite_event value.on;location^"/when",Finite_truth value.guard]
      |Typed.Effect_declaration value->List.mapi(fun index(_,value)->
          location^"/parameters/"^string_of_int index^"/value",scalar_expression value)value.parameters
      |_->[])(Typed.instructions program)in
  let multi_product=R.is_multi_product request and finite_machine=R.is_finite_machine request
  and multi_site=R.is_multi_site request and coupled=R.is_coupled request in
  let library_pin=Canonical.fingerprint(I.library_to_json library) in
  let original_library_pin=Canonical.fingerprint(I.library_to_json(R.implementation_library request)) in
  supported(library_pin=original_library_pin)"Original supplied library changed.";
  let bridge=one "catalog bridge"(R.catalog_bindings request)
  and executor=one "executor" behavior.roles and encounter=one "encounter" behavior.encounters
  and subject=one "subject" behavior.subjects and clock=one "clock" behavior.clocks
  and observation=one "observation" behavior.observations
  and product=(if multi_product then None else Some(one "fixed product" behavior.parameters))
  and machine=one "machine" behavior.machines in
  let transition_count=match finite_program with None->List.length behavior.transitions
    |Some program->List.fold_left(fun count instruction->match Typed.declaration instruction with
      |Typed.Transition_declaration _->count+1|_->count)0(Typed.instructions program)in
  (if finite_machine then (
    let states=List.length machine.states and effects=List.length behavior.effects in
    supported(behavior.rules=[] && (if coupled then List.length behavior.stores>=2 && List.length behavior.stores<=4 else behavior.stores=[]) && states>=2 && states<=16 &&
      transition_count>=1 && transition_count<=32 && effects>=1 && effects<=8)
      "Finite-machine lowering requires 2-16 states, 1-32 transitions and 1-8 effects without rules or independent stores.")
  else supported(behavior.rules=[] && behavior.stores=[] && List.length behavior.effects=2 &&
    transition_count=7 && List.length machine.states=5 && List.length machine.terminal=2)
    "This staged profile requires five states, seven transitions and two effects without rules or truth stores.");
  let document=R.document request and domain=F.specification(A.operating_domain admitted)in
  Meter.serialization(D.to_json document);Meter.serialization(F.to_json(R.operating_domain request));
  Meter.serialization(O.descriptors_to_json(R.definitions request));
  let declarations=D.declarations document in
  let declaration id=List.find(fun(value:D.declaration)->String.equal value.id id)declarations in
  let source id=(declaration id).value and path id=(declaration id).path in
  supported(encounter.executor=executor.role_id && encounter.target=subject.subject_id && encounter.termination="explicit_event" &&
    subject.executor=Some executor.role_id && subject.encounter=Some encounter.encounter_id)
    "Staged encounter ownership or lifetime changed.";
  absent["domain"](source subject.subject_id);
  supported(clock.clock_id=domain.clock && executor.role_id=domain.executor_role && List.length domain.encounters=2 &&
    List.for_all(fun(slot:F.encounter)->slot.declaration=encounter.encounter_id)domain.encounters)
    "Staged lowering requires two independent slots with one exact original clock.";
  supported(text "simultaneous"(source clock.clock_id)="atomic_batch" &&
    List.mem(text "basis"(source clock.clock_id))["logical";"availability"])"Unsupported clock phases.";
  supported(observation.value_type=O.Truth_type && observation.observer=executor.role_id && observation.subject=subject.subject_id &&
    observation.clock=clock.clock_id && observation.coverage="event" && observation.coherence="frame")"Unsupported staged evidence contract.";
  type_is "truth"(get "value_type"(source observation.observation_id));
  supported(machine.executor=executor.role_id && machine.scope=O.Encounter encounter.encounter_id && machine.lifetime="encounter" &&
    machine.arbitration.mode="exclusive" && machine.arbitration.tie="reject" &&
    machine.arbitration.write_conflict="reject" && machine.arbitration.order=[])"Unsupported machine scope or arbitration.";
  let validate_product (parameter:Bioc_domain.Policy_operational.parameter) =
    let product_raw=source parameter.parameter_id in
    supported(text "selection" product_raw="fixed")"Staged product must be fixed.";
    absent["lower";"upper"]product_raw;type_is "text"(get "value_type" product_raw);
    let value=match typed_declaration parameter.parameter_id with
      |Some(Typed.Parameter_declaration value)->value.value
      |Some _->assert false|None->parameter.value in
    match value with O.Text value->value|_->Diagnostic.fail "policy_staged_lowering_unsupported" "Product is not text."in
  let product_symbols=match product with
    |Some parameter->[parameter.parameter_id,validate_product parameter]
    |None->
      supported(List.length behavior.parameters=2)"Multi-product staged lowering requires exactly two fixed original products.";
      let pairs=List.map(fun(parameter:Bioc_domain.Policy_operational.parameter)->parameter.parameter_id,validate_product parameter)behavior.parameters in
      supported(List.length(List.sort_uniq String.compare(List.map snd pairs))=2)
        "Multi-product staged lowering requires two distinct original product symbols.";pairs in
  let product_id,product_symbol=match product_symbols with first::_->first|[]->assert false in
  let resolution=match typed_declaration clock.clock_id with
    |Some(Typed.Clock_declaration value)->value.resolution|Some _->assert false|None->clock.resolution in
  let ticks duration=let exact=Q.div duration resolution in
    supported(Q.sign exact>0 && Z.equal(Q.den exact)Z.one && Z.compare(Q.num exact)(Z.of_int 10000)<=0)
      "Duration is not a bounded positive exact tick count.";Z.to_int(Q.num exact)in
  let initiators effect_id=List.filter(fun(value:O.transition)->List.mem effect_id value.effects)behavior.transitions in
  let attempt_primitive (operation:O.effect_spec)=
    let timeout,typed_lifecycle=match typed_declaration operation.effect_id with
      |Some(Typed.Effect_declaration value)->value.lifecycle.timeout,Some value.lifecycle
      |Some _->assert false|None->operation.lifecycle.timeout,None in
    let timeout_ticks=match timeout with Some value->ticks value|None->
      Diagnostic.fail "policy_staged_lowering_unsupported" "Each stage requires a finite explicit timeout."in
    let authorization=match typed_lifecycle with
      |Some value->(match value.authorization with Typed.At_initiation->I.At_initiation|Typed.Continuous->I.Continuous)
      |None->(match operation.lifecycle.authorization with "initiation"->I.At_initiation|"continuous"->I.Continuous
        |_->Diagnostic.fail "policy_staged_lowering_unsupported" "Unsupported authorization lifetime.")in
    let on_unknown=match typed_lifecycle with
      |Some value->(match value.on_unknown with Typed.Defer->I.Defer|Typed.Continue->I.Continue)
      |None->(match operation.lifecycle.on_unknown with "defer"->I.Defer|"continue"->I.Continue
        |_->Diagnostic.fail "policy_staged_lowering_unsupported" "Unsupported unknown authorization behavior.")in
    if multi_site then I.Attempt_bank_sites{sites=List.length(initiators operation.effect_id);
      capacity=domain.logical_limits.max_source_attempts;timeout_ticks;authorization;on_unknown}
    else I.Attempt_bank{capacity=domain.logical_limits.max_source_attempts;timeout_ticks;authorization;on_unknown}in
  List.iter(fun(operation:O.effect_spec)->
    supported(operation.executor=executor.role_id && operation.subject=subject.subject_id && operation.lifecycle.on_loss="continue" &&
      Json.equal bridge.operation(get "contract"(source operation.effect_id)))"Stage operation changed original operation or recipient.";
    let argument=one "product argument"(rows "parameters"(source operation.effect_id))in
    supported(text "name" argument="product" && text "op"(get "value" argument)="parameter")"Unsupported stage parameter.";
    let sites=initiators operation.effect_id in
    supported(if multi_site then sites<>[] &&
      List.for_all(fun(value:O.transition)->value.effects=[operation.effect_id])sites
      else List.length sites=1 && (List.hd sites).effects=[operation.effect_id])
      "Every effect must have the profile-authorized original single-operation initiating sites.";
    ignore(attempt_primitive operation))behavior.effects;
  (if multi_product then (
    let used=List.map(fun(operation:O.effect_spec)->
      let argument=one "product argument"(rows "parameters"(source operation.effect_id))in
      O.ref_id(get "ref"(get "value" argument)))behavior.effects in
    supported(List.sort String.compare used=List.sort String.compare(List.map fst product_symbols))
      "Each original staged effect must use its own distinct original fixed product exactly once."));
  if coupled then List.iter(fun(store:O.state_store)->let raw=source store.state_id in
    supported(store.value_type=O.Truth_type && store.scope=O.Encounter encounter.encounter_id &&
      store.lifetime="encounter" && store.reset=None && store.capacity>=2 &&
      text "overflow" raw="reject" && text "inheritance" raw="not_applicable")
      "Coupled stores require bounded encounter-local truth state and encounter reset only.";
    absent["duration";"contract";"coordination"]raw;type_is "truth"(get "value_type" raw);
    supported((match store.initial with O.Truth(O.True|O.False)->true|_->false))
      "Coupled stores require a known boolean initial value.")behavior.stores;
  List.iter(fun(value:O.transition)->supported(value.machine=machine.machine_id &&
    (if coupled then List.map(fun(a:O.assignment)->a.state)value.assignments=List.map(fun(s:O.state_store)->s.state_id)behavior.stores
     else value.assignments=[]) &&
    (not finite_machine || not(List.mem value.source machine.terminal)) &&
    List.length value.effects<=1 && List.mem value.on.op
      (if finite_machine then ["rising";"updated";"effect_event"] else ["rising";"effect_event"]))
    "Unsupported transition action or event.")behavior.transitions;
  (* A transition replaces retained attempts only when it starts requests.
     Under this profile's one-request bound, one retained slot is sufficient,
     including retries through cycles; derive it from the actual source. *)
  let retained_capacity=match finite_program with
    |Some program->List.fold_left(fun capacity instruction->match Typed.declaration instruction with
        |Typed.Transition_declaration value->max capacity(List.length value.effects)|_->capacity)1(Typed.instructions program)
    |None->if finite_machine then
        List.fold_left(fun capacity(value:O.transition)->max capacity(List.length value.effects))1 behavior.transitions
      else 1 in
  let layouts=I.models library|>List.filter_map(fun(model:I.model)->match model.replication with
    |I.Encounter_slots value when value.slots=2->Some value.layout_id|_->None)|>List.sort_uniq String.compare in
  let build layout_id=
    let replication=I.Encounter_slots{layout_id;slots=2}in
    let nodes=ref [] and wires=ref [] and occurrences=ref [] and memo=Hashtbl.create 32 and next=ref 0 and edges=ref [] in
    let precharge_model (model:I.model)=
      charge 256;
      (match model.primitive with
       |I.Product_constant value->charge(String.length value)
       |I.Machine_bank value->List.iter(fun name->charge(1+String.length name))(value.states@value.terminal);
         charge(String.length value.initial)
       |I.Transition_gate value->charge(String.length value.source)
       |I.Transition_commit value->charge(String.length value.destination)
       |I.Priority_arbiter order->List.iter(fun _->charge 1)order
       |_->());
      (match model.replication with I.Executor->()|I.Encounter_slots value->charge(String.length value.layout_id)) in
    let matching primitive (model:I.model)=
      precharge_model model;
      Meter.preflight(I.model_body_to_json model);
      let config=match primitive,model.primitive with
        |I.Attempt_bank wanted,I.Attempt_bank supplied->wanted.timeout_ticks=supplied.timeout_ticks &&
          wanted.authorization=supplied.authorization && wanted.on_unknown=supplied.on_unknown && supplied.capacity>=wanted.capacity
        |I.Attempt_bank_sites wanted,I.Attempt_bank_sites supplied->wanted.sites=supplied.sites &&
          wanted.timeout_ticks=supplied.timeout_ticks && wanted.authorization=supplied.authorization &&
          wanted.on_unknown=supplied.on_unknown && supplied.capacity>=wanted.capacity
        |I.Machine_bank wanted,I.Machine_bank supplied->wanted.states=supplied.states && wanted.initial=supplied.initial &&
          wanted.terminal=supplied.terminal && wanted.writers=supplied.writers && supplied.retained_capacity>=wanted.retained_capacity
        |_->primitive=model.primitive in
      config && (model.replication=replication || (model.replication=I.Executor &&
        match primitive with I.Truth_constant _|I.Product_constant _->true|_->false))in
    let allocate id primitive=
      let choices=List.filter(matching primitive)(I.models library)|>List.sort(fun(left:I.model)(right:I.model)->
        Meter.serialization(P.to_json left.identity);Meter.serialization(P.to_json right.identity);
        String.compare(P.fingerprint left.identity)(P.fingerprint right.identity))in
      let chosen=match choices with value::_->value|[]->Diagnostic.fail "policy_staged_lowering_missing_model"
        ("No authorized supplied model for "^I.primitive_name primitive^".")in
      A.require_model admitted ~entry_id:bridge.entry_id chosen.identity;
      supported(List.length !nodes<64)"Staged primitive inventory exceeds the bounded composition family.";
      nodes:= !nodes@[id,chosen];id in
    let out=endpoint in
    let connect producer consumer=supported(List.length !wires<2048)"Staged wire bound exceeded.";
      wires:= !wires@[o["producer",producer;"consumer",consumer]]in
    let outputs id=let model=List.assoc id !nodes in I.ports model.primitive|>List.filter_map(fun(port:I.port)->
      if port.direction=I.Output then Some(out id port.port_id)else None)in
    let occurrence location role disposition targets=
      supported(List.length !occurrences<2048)"Staged occurrence bound exceeded.";
      occurrences:=o["source_path",s location;"role",s role;"disposition",s disposition;"targets",a targets]:: !occurrences in
    let freshness=match typed_declaration observation.observation_id with
      |Some(Typed.Observation_declaration value)->value.freshness|Some _->assert false|None->observation.freshness in
    let evidence=allocate "observation/0"(I.Evidence_bank{freshness_ticks=ticks freshness})in
    let states=List.mapi(fun index(store:O.state_store)->
      let initial=match store.initial with O.Truth value->truth value|_->assert false in
      store.state_id,allocate("state/"^string_of_int index)(I.Truth_register{initial;writers=transition_count}))behavior.stores in
    let machine_states,machine_initial,machine_terminal=match typed_declaration machine.machine_id with
      |Some(Typed.Machine_declaration value)->value.states,value.initial,value.terminal
      |Some _->assert false|None->machine.states,machine.initial,machine.terminal in
    let machine_bank=allocate "machine/0"(I.Machine_bank{states=machine_states;initial=machine_initial;terminal=machine_terminal;
      writers=transition_count;retained_capacity})in
    let attempts=List.mapi(fun index(operation:O.effect_spec)->
      let identity=match typed_declaration operation.effect_id with
        |Some(Typed.Effect_declaration value)->Typed.Effect.name value.id|Some _->assert false|None->operation.effect_id in
      identity,allocate("attempt/"^string_of_int index)(attempt_primitive operation))behavior.effects in
    let arbiter=allocate "arbitration/0"(I.Exclusive_arbiter transition_count)in
    let expression_node primitive=let ordinal= !next in incr next;allocate("expression/"^string_of_int ordinal)primitive in
    let module Expression_keys=Hashtbl.Make(struct
      type t=string
      let hash value=charge(1+Stdlib.String.length value);Hashtbl.hash value
      let equal left right=charge(1+Stdlib.String.length left+Stdlib.String.length right);
        Stdlib.String.equal left right
    end)in
    let structural=if coupled then (
      charge 64;Some(Expression_keys.create 32,Expression_keys.create 32,ref 0))else None in
    let memo_find key=match structural with None->Hashtbl.find_opt memo key
      |Some(_,outputs,_)->Expression_keys.find_opt outputs key in
    let memo_add key output=match structural with None->Hashtbl.add memo key output
      |Some(_,outputs,_)->Expression_keys.add outputs key output in
    let rec emit_with_identity role location raw=
      if not coupled then Meter.serialization raw;
      absent["contract";"duration";"clock";"coverage";"binding"]raw;
      let op,literal=if coupled then (
        (* Every original occurrence is still visited. Read only this node's
           already-admitted scalar fields instead of rebuilding its entire
           typed subtree before recursively visiting those same children. *)
        let kind=get "value_type" raw in Meter.serialization kind;
        let value_type=if text "kind" kind="event"then None else Some(O.value_type kind)in
        let op=text "op" raw in
        let literal=if op="literal"then (
          let value=get "value" raw in Meter.serialization value;
          Option.map(fun kind->O.value_of_json kind value)value_type)else None in
        op,literal)
      else let expression=O.expression_of_json raw in expression.op,expression.value in
      let args=rows "args" raw in
      let children=List.mapi(fun index value->emit_with_identity role(location^"/args/"^string_of_int index)value)args in
      let key,identity=match structural with
        |None->let key=Canonical.encode raw in charge(String.length key);key,0
        |Some(identities,_,next_identity)->
          (* Inductively, child IDs agree exactly when the complete original
             child JSON agrees. Retaining every other original field and the
             ordered child IDs therefore preserves full-expression equality.
             These invocation-local keys never replace published authority. *)
          let shell=o(List.map(fun(name,value)->name,
            if name="args"then a(List.map(fun(_,id)->Json.int id)children)else value)(Json.object_fields raw))in
          let key=Canonical.encode shell in charge(String.length key);
          let identity=match Expression_keys.find_opt identities key with Some value->value
            |None->charge 1;let value= !next_identity in incr next_identity;
              Expression_keys.add identities key value;value in
          key,identity in
      let children=if coupled then List.map fst children else Stdlib.List.map fst children in
      let new_output primitive port input_ports=
        match memo_find key with Some value->value|None->
          let id=expression_node primitive in List.iter2(fun child port->connect child(out id port))children input_ports;
          let value=out id port in memo_add key value;value in
      let pure ()=absent["ref";"scope";"value"]raw in
      let result=match op with
        |"observe"->type_is "truth"(get "value_type" raw);
          supported(args=[] && get "value" raw=Json.Null && Json.equal(get "ref" raw)(reference "Observation" observation.observation_id) &&
            Json.equal(get "scope" raw)(reference "Subject" subject.subject_id))"Observation identity changed.";out evidence "value"
        |"updated"->type_is "event"(get "value_type" raw);
          supported(finite_machine && args=[] && get "value" raw=Json.Null &&
            Json.equal(get "ref" raw)(reference "Observation" observation.observation_id) &&
            Json.equal(get "scope" raw)(reference "Subject" subject.subject_id))
            "Observation updates require the finite-machine profile and exact original observation/subject.";
          out evidence "updated"
        |"state" when coupled->type_is "truth"(get "value_type" raw);
          let identity=O.ref_id(get "ref" raw)in
          supported(args=[] && get "value" raw=Json.Null && List.mem_assoc identity states &&
            Json.equal(get "ref" raw)(reference "StateStore" identity) &&
            Json.equal(get "scope" raw)(reference "Encounter" encounter.encounter_id))"Coupled state changes its original owner.";
          out(List.assoc identity states)"value"
        |"literal"->type_is "truth"(get "value_type" raw);absent["ref";"scope"]raw;supported(args=[])"Literal operands.";
          let value=match literal with Some(O.Truth value)->truth value|_->Diagnostic.fail "policy_staged_lowering_unsupported" "Expected truth literal."in
          new_output(I.Truth_constant value)"out"[]
        |"parameter"->type_is "text"(get "value_type" raw);absent["scope";"value"]raw;
          if multi_product then (
            let selected=List.find_opt(fun(id,_)->Json.equal(get "ref" raw)(reference "Parameter" id))product_symbols in
            supported(args=[] && Option.is_some selected)"Fixed multi-product identity changed.";
            let _,symbol=Option.get selected in new_output(I.Product_constant symbol)"out"[])
          else (
            supported(args=[] && Json.equal(get "ref" raw)(reference "Parameter" product_id))"Fixed product identity changed.";
            new_output(I.Product_constant product_symbol)"out"[])
        |"not"->type_is "truth"(get "value_type" raw);pure();supported(List.length args=1)"Negation arity.";new_output I.Truth_not "out"["in"]
        |"all"|"any"->type_is "truth"(get "value_type" raw);pure();supported(args<>[] && List.length args<=64)"Truth arity.";
          new_output(if op="all"then I.Truth_all(List.length args)else I.Truth_any(List.length args))"out"
            (List.mapi(fun index _->"in"^string_of_int index)args)
        |"rising"->type_is "event"(get "value_type" raw);pure();supported(List.length args=1)"Rising arity.";
          let rec evidence_only value=charge 1;List.mem(text "op" value)["observe";"literal";"not";"all";"any"] && List.for_all evidence_only(rows "args" value)in
          let rec observed value=charge 1;text "op" value="observe" || List.exists observed(rows "args" value)in
          supported(evidence_only(List.hd args)&&observed(List.hd args))"Rising needs observed truth evidence.";
          let value=new_output I.Observed_rising "events"["in"]in
          let edge_key=if coupled then Canonical.encode raw else key in
          if not(List.mem edge_key !edges)then edges:=edge_key:: !edges;value
        |"effect_event"->type_is "event"(get "value_type" raw);
          let identity=O.ref_id(get "ref" raw)in
          supported(args=[] && List.mem_assoc identity attempts && Json.equal(get "ref" raw)(reference "Effect" identity) &&
            Json.equal(get "scope" raw)(reference "Subject" subject.subject_id))"Effect event identity changed.";
          let kind=match text "value" raw with "completed"->I.Completed|"failed"->I.Failed|"timed_out"->I.Timed_out
            |_->Diagnostic.fail "policy_staged_lowering_unsupported" "Only completion, failure and timeout drive stage feedback."in
          (match memo_find key with Some value->value|None->let id=expression_node(I.Event_select kind)in
            connect(out(List.assoc identity attempts)"events")(out id "events");let value=out id "selected"in memo_add key value;value)
        |_->Diagnostic.fail "policy_staged_lowering_unsupported" "Expression lacks a staged primitive interpretation."in
      occurrence location role(if List.mem op["literal";"parameter"]then "constant"else "executable")[result];result,identity in
    (* The exact finite-machine path never decodes executable operands back
       from JSON. Raw bodies below supply only original metadata restrictions,
       structural sharing identity and occurrence lineage. Other profiles keep
       their original emitter and work path above. *)
    let finite_source=function
      |Finite_truth value->Typed.truth_source value|Finite_integer value->Typed.integer_source value
      |Finite_text value->Typed.text_source value|Finite_quantity value->Typed.quantity_source value
      |Finite_event value->Typed.event_source value in
    let finite_children=function
      |Finite_truth value->(match Typed.truth_term value with
        |Typed.All values|Typed.Any values->List.map(fun value->Finite_truth value)values
        |Typed.Not value->[Finite_truth value]
        |Typed.Truth_equal(_,left,right)->[Finite_truth left;Finite_truth right]
        |Typed.Text_equal(_,left,right)->[Finite_text left;Finite_text right]
        |Typed.Integer_compare(_,left,right)->[Finite_integer left;Finite_integer right]
        |Typed.Quantity_compare(_,left,right)->[Finite_quantity left;Finite_quantity right]
        |Typed.Truth_literal _|Typed.Truth_read _->[])
      |Finite_event value->(match Typed.event_term value with Typed.Rising value->[Finite_truth value]
        |Typed.Updated _|Typed.Effect_event _->[])
      |Finite_integer _|Finite_text _|Finite_quantity _->[]in
    let exact_observation symbol=match typed_declaration observation.observation_id with
      |Some(Typed.Observation_declaration value)->Typed.Observation.index value.id=Typed.Observation.index symbol
      |_->assert false in
    let rec finite_evidence_only value=charge 1;match Typed.truth_term value with
      |Typed.Truth_literal _|Typed.Truth_read(Typed.Observation_read _)->true
      |Typed.Not value->finite_evidence_only value
      |Typed.All values|Typed.Any values->List.for_all finite_evidence_only values
      |_->false in
    let rec finite_observed value=charge 1;match Typed.truth_term value with
      |Typed.Truth_read(Typed.Observation_read _)->true
      |Typed.Not value->finite_observed value
      |Typed.All values|Typed.Any values->List.exists finite_observed values
      |_->false in
    let rec emit_finite role location expression=
      charge 1;
      let raw=finite_source expression in
      Meter.serialization raw;
      absent["contract";"duration";"clock";"coverage";"binding"]raw;
      let terms=finite_children expression in
      let children=List.mapi(fun index value->emit_finite role(location^"/args/"^string_of_int index)value)terms in
      let key=Canonical.encode raw in charge(String.length key);
      let new_output primitive port input_ports=match memo_find key with Some value->value|None->
        let id=expression_node primitive in List.iter2(fun child port->connect child(out id port))children input_ports;
        let value=out id port in memo_add key value;value in
      let pure ()=absent["ref";"scope";"value"]raw in
      let unsupported ()=Diagnostic.fail "policy_staged_lowering_unsupported" "Expression lacks a staged primitive interpretation."in
      let unsupported_type kind=type_is kind(get "value_type" raw);unsupported()in
      let unsupported_read=function
        |Typed.Observation_read _->unsupported_type "truth"
        |Typed.Parameter_read _->unsupported_type "text"
        |Typed.State_read _->unsupported()in
      let result,constant=match expression with
        |Finite_truth value->(match Typed.truth_term value with
          |Typed.Truth_read(Typed.Observation_read symbol)->
              type_is "truth"(get "value_type" raw);
              supported(exact_observation symbol && get "value" raw=Json.Null &&
                Json.equal(get "scope" raw)(reference "Subject" subject.subject_id))"Observation identity changed.";
              out evidence "value",false
          |Typed.Truth_literal value->type_is "truth"(get "value_type" raw);absent["ref";"scope"]raw;
              new_output(I.Truth_constant(truth value))"out"[],true
          |Typed.Not _->type_is "truth"(get "value_type" raw);pure();new_output I.Truth_not "out"["in"],false
          |Typed.All values|Typed.Any values->type_is "truth"(get "value_type" raw);pure();
              let arity=List.length values in supported(arity>0 && arity<=64)"Truth arity.";
              let primitive=match Typed.truth_term value with Typed.All _->I.Truth_all arity|_->I.Truth_any arity in
              new_output primitive "out"(List.mapi(fun index _->"in"^string_of_int index)values),false
          |Typed.Truth_read read->unsupported_read read
          |_->unsupported())
        |Finite_text value->(match Typed.text_term value with
          |Typed.Text_read(Typed.Parameter_read symbol)->
              type_is "text"(get "value_type" raw);absent["scope";"value"]raw;
              let exact=match typed_declaration product_id with
                |Some(Typed.Parameter_declaration parameter)->Typed.Parameter.index parameter.id=Typed.Parameter.index symbol
                |_->assert false in
              supported exact "Fixed product identity changed.";
              new_output(I.Product_constant product_symbol)"out"[],true
          |Typed.Text_literal _->unsupported_type "truth"
          |Typed.Text_read read->unsupported_read read)
        |Finite_event value->(match Typed.event_term value with
          |Typed.Updated symbol->type_is "event"(get "value_type" raw);
              supported(exact_observation symbol && get "value" raw=Json.Null &&
                Json.equal(get "scope" raw)(reference "Subject" subject.subject_id))
                "Observation updates require the finite-machine profile and exact original observation/subject.";
              out evidence "updated",false
          |Typed.Rising predicate->type_is "event"(get "value_type" raw);pure();
              supported(finite_evidence_only predicate && finite_observed predicate)"Rising needs observed truth evidence.";
              let value=new_output I.Observed_rising "events"["in"]in
              if not(List.mem key !edges)then edges:=key:: !edges;value,false
          |Typed.Effect_event(symbol,phase)->type_is "event"(get "value_type" raw);
              let identity=Typed.Effect.name symbol in
              supported(List.mem_assoc identity attempts &&
                Json.equal(get "scope" raw)(reference "Subject" subject.subject_id))"Effect event identity changed.";
              let kind=match phase with Typed.Completed->I.Completed|Typed.Failed->I.Failed|Typed.Timed_out->I.Timed_out
                |Typed.Requested|Typed.Initiated->Diagnostic.fail "policy_staged_lowering_unsupported"
                    "Only completion, failure and timeout drive stage feedback."in
              let output=match memo_find key with Some value->value|None->
                let id=expression_node(I.Event_select kind)in
                connect(out(List.assoc identity attempts)"events")(out id "events");
                let value=out id "selected"in memo_add key value;value in output,false)
        |Finite_integer value->(match Typed.integer_term value with
            |Typed.Integer_literal _->unsupported_type "truth"|Typed.Integer_read read->unsupported_read read)
        |Finite_quantity value->(match Typed.quantity_term value with
            |Typed.Quantity_literal _->unsupported_type "truth"|Typed.Quantity_read read->unsupported_read read)in
      occurrence location role(if constant then "constant"else "executable")[result];result in
    let emit role location raw=match finite_program with
      |None->fst(emit_with_identity role location raw)
      |Some _->emit_finite role location(snd(List.find(fun(path,_)->String.equal path location)typed_roots))in
    let anchors=ref [] and product_outputs=ref [] and product_targets=ref [] and effect_products=ref [] in
    let product_output effect_id argument=
      if not multi_site then emit "effect_parameter"(path effect_id^"/parameters/0/value")(get "value" argument)
      else match List.assoc_opt effect_id !effect_products with
        |Some output->output
        |None->let output=emit "effect_parameter"(path effect_id^"/parameters/0/value")(get "value" argument)in
          effect_products:= !effect_products@[effect_id,output];output in
    let commits=List.mapi(fun index(transition:O.transition)->
      let raw=source transition.transition_id and location=path transition.transition_id and prefix="transition/"^string_of_int index in
      let on=emit "predicate"(location^"/on")(get "on" raw)and guard=emit "predicate"(location^"/when")(get "when" raw)in
      let transition_id,source_state,destination,correlation,effects,writes=match typed_declaration transition.transition_id with
        |Some(Typed.Transition_declaration value)->
            Typed.Transition.name value.id,value.source,value.destination,
            (match Typed.event_term value.on with Typed.Effect_event _->I.Retained_attempt|_->I.Unbound),
            List.map Typed.Effect.name value.effects,Some(List.length value.assignments)
        |Some _->assert false|None->transition.transition_id,transition.source,transition.destination,
            (if transition.on.op="effect_event"then I.Retained_attempt else I.Unbound),transition.effects,None in
      let gate=allocate(prefix^"/gate")(I.Transition_gate{source=source_state;correlation})in
      let commit=allocate(prefix^"/commit")(I.Transition_commit{destination;
        writes=(match writes with Some count->count|None->List.length transition.assignments);requests=List.length effects})in
      connect(out machine_bank "snapshot")(out gate "machine");connect on(out gate "on");connect guard(out gate "guard");
      connect(out gate "candidate")(out arbiter("in"^string_of_int index));connect(out arbiter("out"^string_of_int index))(out commit "grant");
      connect(out commit "machine_write")(out machine_bank("write"^string_of_int index));
      List.iteri(fun ordinal(assignment:O.assignment)->
        let assignment_path=location^"/assignments/"^string_of_int ordinal in
        let value=emit "state_write"(assignment_path^"/value")
          (get "value"(List.nth(rows "assignments" raw)ordinal))in
        connect value(out commit("value"^string_of_int ordinal));
        connect(out commit("write"^string_of_int ordinal))(out(List.assoc assignment.state states)("write"^string_of_int index));
        occurrence assignment_path "state_write" "executable"[out commit("write"^string_of_int ordinal)])transition.assignments;
      List.iter(fun effect_id->let effect_raw=source effect_id in let argument=one "stage argument"(rows "parameters" effect_raw)in
        let output=product_output effect_id argument in
        (if multi_product then (
          let id=O.ref_id(get "ref"(get "value" argument))in
          let previous=Option.value(List.assoc_opt id !product_targets)~default:[] in
          let targets=if List.exists(Json.equal output)previous then previous else previous@[output]in
          product_targets:=(id,targets)::List.remove_assoc id !product_targets));
        if not(List.exists(Json.equal output)!product_outputs)then product_outputs:= !product_outputs@[output];
        let request_port,authorization_port=if multi_site then
          let ordered=initiators effect_id in
          let rec index ordinal=function
            |[]->assert false
            |(site:O.transition)::rest->if site.transition_id=transition.transition_id then ordinal else index(ordinal+1)rest in
          let suffix=string_of_int(index 0 ordered)in "request"^suffix,"authorization"^suffix
          else "request","authorization"in
        connect output(out commit "product0");connect(out commit "request0")(out(List.assoc effect_id attempts)request_port);
        connect guard(out(List.assoc effect_id attempts)authorization_port))effects;
      occurrence location "declaration" "executable"([out gate "candidate";out arbiter("out"^string_of_int index)]@outputs commit);
      anchors:= !anchors@[o["source",s transition_id;"gate",s gate;"arbiter",s arbiter;"lane",Json.int index;"commit",s commit]];commit)behavior.transitions in
    let rec obligations location raw=charge(1+String.length location);match raw with
      |Json.Object fields->(match List.assoc_opt "$type" fields with Some(Json.String "Expr")->
          supported(text "op" raw<>"rising" || List.mem(Canonical.encode raw)!edges)"Requirement adds unimplemented edge memory.";
          occurrence location "requirement" "obligation"[]|_->());
        List.iter(fun(key,value)->obligations(location^"/"^key)value)fields
      |Json.Array values->List.iteri(fun index value->obligations(location^"/"^string_of_int index)value)values|_->()in
    List.iter(fun(value:D.declaration)->let location=value.path in match value.kind with
      |D.Role|D.Subject|D.Encounter->occurrence location "declaration" "retained_metadata"[]
      |D.Clock->occurrence location "clock" "retained_metadata"[]
      |D.State_store when coupled->occurrence location "declaration" "executable"(outputs(List.assoc value.id states))
      |D.Observation->occurrence location "declaration" "executable"(outputs evidence)
      |D.Parameter->
        if multi_product then (
          let targets=Option.value(List.assoc_opt value.id !product_targets)~default:[]in
          supported(List.length targets=1)"Each source product requires exactly its own interpreted product output.";
          occurrence location "effect_parameter" "constant" targets)
        else occurrence location "effect_parameter" "constant" !product_outputs
      |D.Effect->let ports=outputs(List.assoc value.id attempts)in occurrence location "lifecycle" "executable" ports;
        occurrence(location^"/lifecycle")"lifecycle" "executable" ports
      |D.Machine->occurrence location "declaration" "executable"(outputs machine_bank);
        occurrence(location^"/arbitration")"declaration" "executable"(outputs arbiter)
      |D.Transition->()
      |D.Requirement->occurrence location "requirement" "obligation"[];obligations location value.value
      |_->Diagnostic.fail "policy_staged_lowering_unsupported" "Declaration is outside the staged source family.")declarations;
    let authority=o["source_artifact_digest",s(D.artifact_digest document);"descriptors_digest",s(O.descriptors_digest(R.definitions request));
      "domain_digest",s(Canonical.fingerprint(F.to_json(R.operating_domain request)));"implementation_catalog_digest",s(Canonical.fingerprint(get "implementations"(D.to_json document)));
      "library_digest",s library_pin]in
    let inputs=o["id",s "evidence/0";"kind",s "evidence";"consumer",out evidence "samples"]::
      List.mapi(fun index(_,bank)->o["id",s("feedback/"^string_of_int index);"kind",s "feedback";"consumer",out bank "feedback"])attempts in
    let graph=o["schema_version",s I.candidate_schema;"profile",s(if multi_site then I.multi_site_profile else I.staged_profile);
      "observable_profile",s(if multi_site then I.multi_site_observable_profile else I.staged_observable_profile);
      "authority",authority;"slot_layout",o["id",s layout_id;"encounter",s encounter.encounter_id;"slots",Json.int 2];
      "nodes",a(List.map(fun(id,(model:I.model))->o["id",s id;"model",P.to_json model.identity;"configuration_digest",s model.configuration_digest])!nodes);
      "wires",a !wires;"inputs",a inputs;"atomic_groups",a[o["id",s "exclusive/0";"arbiter",s arbiter;"commits",a(List.map s commits)]];
      "semantic_exports",a(List.concat_map(fun(id,_)->outputs id)!nodes);
      "occurrences",a(List.sort(fun left right->String.compare(text "source_path" left)(text "source_path" right))!occurrences)]in
    let binding=o["schema_version",s(if coupled then B.coupled_schema_version else if multi_site then B.multi_site_schema_version else if finite_machine then B.finite_machine_schema_version else if multi_product then B.multi_product_schema_version else B.staged_schema_version);
      "profile",s(if coupled then B.coupled_profile else if multi_site then B.multi_site_profile else if finite_machine then B.finite_machine_profile else if multi_product then B.multi_product_profile else B.staged_profile);"catalog_entry",s bridge.entry_id;
      "observations",a[o["source",s observation.observation_id;"bank",s evidence;"input",s "evidence/0"]];"states",a(List.map(fun(source,register)->o["source",s source;"register",s register])states);"rules",a[];
      "effects",a(List.mapi(fun index(source,bank)->o["source",s source;"bank",s bank;"feedback",s("feedback/"^string_of_int index)])attempts);
      "machines",a[o["source",s machine.machine_id;"bank",s machine_bank]];"transitions",a !anchors]in
    Meter.serialization graph;Meter.serialization binding;Meter.serialization(I.library_to_json library);
    I.of_json ~library graph,B.of_json binding in
  let rec choose= function []->Diagnostic.fail "policy_staged_lowering_missing_model" "No complete supplied staged model family matches the original source."
    |layout::remaining->charge 1;try build layout with Diagnostic.Error error when error.code="policy_staged_lowering_missing_model"->choose remaining in
  choose layouts

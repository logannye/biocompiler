open Bioc_wire
module Names = Set.Make(String)

let profile = "biocompiler.policy_truth_primitives.v0.1"
let observable_profile = "biocompiler.policy_truth_observables.v0.1"
let staged_profile = "biocompiler.policy_staged_primitives.v0.1"
let staged_observable_profile = "biocompiler.policy_staged_observables.v0.1"
let library_schema = "biocompiler.policy_implementation_library.v0.1"
let model_schema = "biocompiler.policy_primitive_model.v0.1"
let candidate_schema = "biocompiler.policy_implementation.v0.1"
let resource_profile = "biocompiler.policy_implementation.resources.v0.1"
type truth = True | False | Unknown
type replication = Executor | Encounter_slots of { layout_id : string; slots : int }
type event_kind = Updated | Rising | Requested | Initiated | Completed | Failed | Timed_out
type authorization = At_initiation | Continuous
type unknown_response = Continue | Defer
type correlation = Unbound | Retained_attempt
type primitive =
  | Truth_constant of truth | Product_constant of string
  | Evidence_bank of { freshness_ticks : int }
  | Truth_not | Truth_all of int | Truth_any of int | Truth_equal
  | Truth_register of { initial : truth; writers : int }
  | Observed_rising | Event_select of event_kind | Activation_gate
  | Exclusive_arbiter of int | Priority_arbiter of int list
  | Atomic_commit of { writes : int; requests : int }
  | Attempt_bank of { capacity : int; timeout_ticks : int;
      authorization : authorization; on_unknown : unknown_response }
  | Machine_bank of { states : string list; initial : string; terminal : string list;
      writers : int; retained_capacity : int }
  | Transition_gate of { source : string; correlation : correlation }
  | Transition_commit of { destination : string; writes : int; requests : int }
type signal_type = Truth_value | Product_symbol | Evidence_batch | Feedback_batch
  | Event_batch | Activation_batch | Truth_write | Effect_request | Attempt_snapshot
  | Machine_snapshot | Machine_write
type direction = Input | Output
type port = { port_id : string; direction : direction; signal_type : signal_type }
type endpoint = { node_id : string; port_id : string }
type wire = { producer : endpoint; consumer : endpoint }
type external_kind = Evidence_input | Feedback_input
type external_input = { input_id : string; input_kind : external_kind; consumer : endpoint }
type occurrence_role = Declaration | Predicate | State_write | Effect_parameter
  | Clock | Lifecycle | Requirement | Metadata
type occurrence_disposition = Executable | Constant | Obligation | Retained_metadata
type occurrence = { source_path : string; role : occurrence_role;
  disposition : occurrence_disposition; targets : endpoint list }
type atomic_group = { group_id : string; arbiter : string; commits : string list }
type slot_layout = { layout_id : string; encounter_id : string; slots : int }
type authority = { source_artifact_digest : string; descriptors_digest : string;
  domain_digest : string; implementation_catalog_digest : string; library_digest : string }
type model = { identity : Pinned_identity.t; configuration_digest : string;
  primitive : primitive; replication : replication }
type library = { library_raw : Json.t; model_values : model list }
type node = { node_id : string; model : model }
type t = { raw : Json.t; authority_value : authority; layout_value : slot_layout;
  node_values : node list; wire_values : wire list; input_values : external_input list;
  group_values : atomic_group list; export_values : endpoint list; occurrence_values : occurrence list }

let fail message = Diagnostic.fail "policy_implementation_contract" message
let require condition message = if not condition then fail message
let profile_for_primitive = function
  | Machine_bank _ | Transition_gate _ | Transition_commit _ -> staged_profile
  | _ -> profile
let observable_profile_for value =
  if value=profile then observable_profile else if value=staged_profile then staged_observable_profile
  else fail "Unknown implementation profile."
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let text key value = Json.string (get key value)
let exact keys value = Json.exact_fields keys (Json.object_fields value)
let name ?(maximum=128) value =
  let value=Json.name value in
  require (String.length value <= maximum) "Implementation identifier exceeds its declared bound.";value
let integer ~minimum ~maximum value =
  let n=Json.integer value in
  require (Z.compare n (Z.of_int minimum)>=0 && Z.compare n (Z.of_int maximum)<=0)
    "Implementation integer is outside its finite contract.";Z.to_int n
let sha value =
  let value=Json.string value in
  require (String.length value=64 && String.for_all(function '0'..'9'|'a'..'f'->true|_->false)value)
    "Implementation authority requires a complete lowercase SHA-256 digest.";value
let measure raw =
  let maximum=2*1024*1024 and count=ref 0 and bytes=ref 0 in
  let limit value=Diagnostic.require value "policy_implementation_limit"
      "Implementation contract exceeds its 2 MiB/100000-node/48-depth resource profile." in
  let visit depth=incr count;limit(!count<=100_000 && depth<=48) in
  let charge n=limit(n<=maximum - !bytes);bytes:= !bytes+n in
  let string value=limit(String.length value<=65_536);Json.validate_utf8 value;charge(String.length value) in
  let rec walk depth = function
    | Json.Null->visit depth;charge 4 | Json.Bool b->visit depth;charge(if b then 4 else 5)
    | Json.Int n->visit depth;limit(Z.numbits n<=256);charge(String.length(Z.to_string n))
    | Json.Float _->fail "Raw floats cannot enter an exact implementation contract."
    | Json.String value->visit depth;string value
    | Json.Array values->visit depth;List.iter(walk(depth+1))values
    | Json.Object fields->
        visit depth;
        let seen=Hashtbl.create 16 in
        List.iter(fun(key,value)->visit(depth+1);string key;
          require(not(Hashtbl.mem seen key))"Duplicate implementation object key.";
          Hashtbl.add seen key ();walk(depth+1)value)fields in
  walk 0 raw;ignore(Canonical.encode_bounded ~max_bytes:maximum raw)
let bounded_list ~maximum value =
  let values=Json.array value in require(List.length values<=maximum)"Implementation array exceeds its bound.";values
let unique label values =
  let seen=ref Names.empty in
  List.iter(fun value->require(not(Names.mem value !seen))("Duplicate "^label^" identity.");seen:=Names.add value !seen)values
let truth_of_json = function
  | Json.String "true"->True | Json.String "false"->False | Json.String "unknown"->Unknown
  | _->fail "Primitive truth requires true, false or unknown, without coercion."
let truth_name = function True->"true"|False->"false"|Unknown->"unknown"
let event_name = function Updated->"updated"|Rising->"rising"|Requested->"requested"|Initiated->"initiated"
  | Completed->"completed"|Failed->"failed"|Timed_out->"timed_out"
let event_of_json value = match Json.string value with
  | "updated"->Updated|"rising"->Rising|"requested"->Requested|"initiated"->Initiated
  | "completed"->Completed|"failed"->Failed|"timed_out"->Timed_out
  | _->fail "Event selector has no primitive semantics in this profile."
let replication_of_json value = match text "kind" value with
  | "executor"->exact["kind"]value;Executor
  | "encounter_slots"->exact["kind";"layout_id";"slots"]value;
      Encounter_slots{layout_id=name(get "layout_id" value);slots=integer ~minimum:1 ~maximum:16(get "slots" value)}
  | _->fail "Unsupported implementation replication."
let replication_json = function
  | Executor->obj["kind",str "executor"]
  | Encounter_slots{layout_id;slots}->obj["kind",str "encounter_slots";"layout_id",str layout_id;"slots",Json.int slots]
let primitive_name = function
  | Truth_constant _->"truth_constant"|Product_constant _->"product_constant"|Evidence_bank _->"evidence_bank"
  | Truth_not->"truth_not"|Truth_all _->"truth_all"|Truth_any _->"truth_any"|Truth_equal->"truth_equal"
  | Truth_register _->"truth_register"|Observed_rising->"observed_rising"|Event_select _->"event_select"
  | Activation_gate->"activation_gate"|Exclusive_arbiter _->"exclusive_arbiter"|Priority_arbiter _->"priority_arbiter"
  | Atomic_commit _->"atomic_commit"|Attempt_bank _->"attempt_bank"
  | Machine_bank _->"machine_bank"|Transition_gate _->"transition_gate"|Transition_commit _->"transition_commit"
let configuration = function
  | Truth_constant value->obj["value",str(truth_name value)]
  | Product_constant value->obj["product",str value]
  | Evidence_bank{freshness_ticks}->obj["freshness_ticks",Json.int freshness_ticks]
  | Truth_all arity|Truth_any arity->obj["arity",Json.int arity]
  | Truth_register{initial;writers}->obj["initial",str(truth_name initial);"writers",Json.int writers]
  | Event_select kind->obj["event_kind",str(event_name kind)]
  | Exclusive_arbiter lanes->obj["lanes",Json.int lanes]
  | Priority_arbiter order->obj["order",arr(List.map Json.int order)]
  | Atomic_commit{writes;requests}->obj["writes",Json.int writes;"requests",Json.int requests]
  | Machine_bank{states;initial;terminal;writers;retained_capacity}->obj[
      "states",arr(List.map str states);"initial",str initial;"terminal",arr(List.map str terminal);
      "writers",Json.int writers;"retained_capacity",Json.int retained_capacity]
  | Transition_gate{source;correlation}->obj["source",str source;
      "correlation",str(match correlation with Unbound->"unbound"|Retained_attempt->"retained_attempt")]
  | Transition_commit{destination;writes;requests}->obj[
      "destination",str destination;"writes",Json.int writes;"requests",Json.int requests]
  | Attempt_bank{capacity;timeout_ticks;authorization;on_unknown}->obj[
      "capacity",Json.int capacity;"timeout_ticks",Json.int timeout_ticks;
      "authorization",str(match authorization with At_initiation->"initiation"|Continuous->"continuous");
      "on_loss",str "continue";"on_unknown",str(match on_unknown with Continue->"continue"|Defer->"defer")]
  | Truth_not|Truth_equal|Observed_rising|Activation_gate->obj[]
let primitive_of_json tag value =
  let positive key=integer ~minimum:1 ~maximum:64(get key value) in
  match tag with
  | "truth_constant"->exact["value"]value;Truth_constant(truth_of_json(get "value" value))
  | "product_constant"->exact["product"]value;Product_constant(name ~maximum:256(get "product" value))
  | "evidence_bank"->exact["freshness_ticks"]value;Evidence_bank{freshness_ticks=integer ~minimum:1 ~maximum:10000(get "freshness_ticks" value)}
  | "truth_not"->exact[]value;Truth_not|"truth_equal"->exact[]value;Truth_equal
  | "truth_all"->exact["arity"]value;Truth_all(positive "arity")
  | "truth_any"->exact["arity"]value;Truth_any(positive "arity")
  | "truth_register"->exact["initial";"writers"]value;
      Truth_register{initial=truth_of_json(get "initial" value);writers=integer ~minimum:0 ~maximum:64(get "writers" value)}
  | "observed_rising"->exact[]value;Observed_rising
  | "event_select"->exact["event_kind"]value;Event_select(event_of_json(get "event_kind" value))
  | "activation_gate"->exact[]value;Activation_gate
  | "exclusive_arbiter"->exact["lanes"]value;Exclusive_arbiter(positive "lanes")
  | "priority_arbiter"->exact["order"]value;
      let order=List.map(integer ~minimum:0 ~maximum:63)(bounded_list ~maximum:64(get "order" value))in
      require(order<>[] && List.sort compare order=List.init(List.length order)Fun.id)"Priority order must be a complete lane permutation.";
      Priority_arbiter order
  | "atomic_commit"->exact["writes";"requests"]value;
      let writes=integer ~minimum:0 ~maximum:64(get "writes" value)and requests=integer ~minimum:0 ~maximum:16(get "requests" value)in
      require(writes+requests>0)"Empty atomic actions are not implemented.";Atomic_commit{writes;requests}
  | "machine_bank"->exact["states";"initial";"terminal";"writers";"retained_capacity"]value;
      let states=List.map(name ~maximum:256)(bounded_list ~maximum:16(get "states" value))
      and terminal=List.map(name ~maximum:256)(bounded_list ~maximum:16(get "terminal" value))
      and initial=name ~maximum:256(get "initial" value)in
      require(states<>[])"Machine state alphabet must not be empty.";
      unique "machine state" states;unique "terminal machine state" terminal;
      require(List.mem initial states && List.for_all(fun state->List.mem state states)terminal)
        "Initial and terminal machine states must belong to the declared alphabet.";
      Machine_bank{states;initial;terminal;writers=positive "writers";
        retained_capacity=integer ~minimum:1 ~maximum:16(get "retained_capacity" value)}
  | "transition_gate"->exact["source";"correlation"]value;
      let correlation=match text "correlation" value with
        |"unbound"->Unbound|"retained_attempt"->Retained_attempt|_->fail "Unknown transition correlation."in
      Transition_gate{source=name ~maximum:256(get "source" value);correlation}
  | "transition_commit"->exact["destination";"writes";"requests"]value;
      Transition_commit{destination=name ~maximum:256(get "destination" value);
        writes=integer ~minimum:0 ~maximum:64(get "writes" value);
        requests=integer ~minimum:0 ~maximum:16(get "requests" value)}
  | "attempt_bank"->exact["capacity";"timeout_ticks";"authorization";"on_loss";"on_unknown"]value;
      let authorization=match text "authorization" value with "initiation"->At_initiation|"continuous"->Continuous|_->fail "Unknown attempt authorization." in
      let on_unknown=match text "on_unknown" value with "continue"->Continue|"defer"->Defer|_->fail "Unknown attempt uncertainty response." in
      require(text "on_loss" value="continue")"Stopping and cancellation need another primitive profile.";
      Attempt_bank{capacity=integer ~minimum:1 ~maximum:1024(get "capacity" value);
        timeout_ticks=integer ~minimum:1 ~maximum:10000(get "timeout_ticks" value);authorization;on_unknown}
  | _->fail "Unknown primitive; source interpreter nodes and operation aliases are forbidden."
let ports primitive =
  let p direction signal_type port_id : port ={port_id;direction;signal_type}in
  let ins typ prefix count=List.init count(fun i->p Input typ(prefix^string_of_int i))
  and outs typ prefix count=List.init count(fun i->p Output typ(prefix^string_of_int i))in
  match primitive with
  | Truth_constant _->[p Output Truth_value "out"]|Product_constant _->[p Output Product_symbol "out"]
  | Evidence_bank _->[p Input Evidence_batch "samples";p Output Truth_value "value";p Output Event_batch "updated"]
  | Truth_not->[p Input Truth_value "in";p Output Truth_value "out"]
  | Truth_all n|Truth_any n->ins Truth_value "in" n@[p Output Truth_value "out"]
  | Truth_equal->[p Input Truth_value "left";p Input Truth_value "right";p Output Truth_value "out"]
  | Truth_register{writers;_}->ins Truth_write "write" writers@[p Output Truth_value "value"]
  | Observed_rising->[p Input Truth_value "in";p Output Event_batch "events"]
  | Event_select _->[p Input Event_batch "events";p Output Event_batch "selected"]
  | Activation_gate->[p Input Event_batch "on";p Input Truth_value "guard";p Output Activation_batch "candidate"]
  | Transition_gate _->[p Input Machine_snapshot "machine";p Input Event_batch "on";
      p Input Truth_value "guard";p Output Activation_batch "candidate"]
  | Exclusive_arbiter n->ins Activation_batch "in" n@outs Activation_batch "out" n
  | Priority_arbiter order->let n=List.length order in ins Activation_batch "in" n@outs Activation_batch "out" n
  | Atomic_commit{writes;requests}->[p Input Activation_batch "grant"]@ins Truth_value "value" writes@
      ins Product_symbol "product" requests@outs Truth_write "write" writes@outs Effect_request "request" requests
  | Transition_commit{writes;requests;_}->[p Input Activation_batch "grant"]@ins Truth_value "value" writes@
      ins Product_symbol "product" requests@outs Truth_write "write" writes@outs Effect_request "request" requests@
      [p Output Machine_write "machine_write"]
  | Machine_bank{writers;_}->ins Machine_write "write" writers@[p Output Machine_snapshot "snapshot"]
  | Attempt_bank _->[p Input Effect_request "request";p Input Truth_value "authorization";p Input Feedback_batch "feedback";
      p Output Event_batch "events";p Output Attempt_snapshot "snapshot"]
let model_body_to_json (value:model) = obj["schema_version",str model_schema;"profile",str(profile_for_primitive value.primitive);
    "primitive",str(primitive_name value.primitive);"configuration",configuration value.primitive;
    "replication",replication_json value.replication]
let model_of_json value : model =
  exact["identity";"configuration_digest";"body"]value;
  let identity=Pinned_identity.of_json(get "identity" value)and body=get "body" value in
  exact["schema_version";"profile";"primitive";"configuration";"replication"]body;
  require(text "schema_version" body=model_schema && List.mem(text "profile" body)[profile;staged_profile])"Unknown supplied primitive model profile.";
  require(Pinned_identity.kind identity=Pinned_identity.Model)"Primitive model requires a Model identity.";
  let configuration_value=get "configuration" body in
  let configuration_digest=sha(get "configuration_digest" value)in
  require(configuration_digest=Canonical.fingerprint configuration_value)"Supplied configuration digest differs from its complete body.";
  require(Pinned_identity.content_fingerprint identity=Canonical.fingerprint body)"Supplied model identity differs from its complete body.";
  let primitive=primitive_of_json(text "primitive" body)configuration_value and replication=replication_of_json(get "replication" body)in
  require(text "profile" body=profile_for_primitive primitive)"Primitive body does not use its declared semantic profile.";
  (match primitive,replication with
   |(Truth_constant _|Product_constant _|Truth_not|Truth_all _|Truth_any _|Truth_equal),_->()
   |_,Encounter_slots _->()
   |_,Executor->fail "Stateful and control primitives require distinct encounter-slot replication in this profile.");
  {identity;configuration_digest;primitive;replication}
let library_of_json raw : library =
  measure raw;exact["schema_version";"profile";"id";"version";"models"]raw;
  require(text "schema_version" raw=library_schema && List.mem(text "profile" raw)[profile;staged_profile])"Unknown implementation library profile.";
  ignore(name(get "id" raw));ignore(name(get "version" raw));
  let model_values=List.map model_of_json(bounded_list ~maximum:64(get "models" raw))in
  require(model_values<>[])"Concrete model library must not be empty.";
  require(text "profile" raw=staged_profile || List.for_all(fun(m:model)->profile_for_primitive m.primitive=profile)model_values)
    "Legacy library cannot contain staged primitive models.";
  unique "model id/version"(List.map(fun(m:model)->Canonical.encode(arr[str(Pinned_identity.id m.identity);str(Pinned_identity.version m.identity)]))model_values);
  {library_raw=raw;model_values}
let library_to_json (value:library)=value.library_raw
let library_profile (value:library)=text "profile" value.library_raw
let library_digest (value:library)=Canonical.fingerprint value.library_raw
let models (value:library)=value.model_values
let endpoint_of_json value : endpoint =exact["node";"port"]value;{node_id=name(get "node" value);port_id=name(get "port" value)}
let endpoint_key (value:endpoint)=Canonical.encode(arr[str value.node_id;str value.port_id])
let authority_of_json value : authority =
  exact["source_artifact_digest";"descriptors_digest";"domain_digest";"implementation_catalog_digest";"library_digest"]value;
  {source_artifact_digest=sha(get "source_artifact_digest" value);descriptors_digest=sha(get "descriptors_digest" value);
   domain_digest=sha(get "domain_digest" value);implementation_catalog_digest=sha(get "implementation_catalog_digest" value);
   library_digest=sha(get "library_digest" value)}
let source_pointer value =
  let value=name ~maximum:2048 value in
  require(String.length value>1 && value.[0]='/')"Source occurrences require nonempty absolute JSON pointers.";
  let rec valid i=if i=String.length value then true else if value.[i]='~'then
      i+1<String.length value && (value.[i+1]='0'||value.[i+1]='1') && valid(i+2)else valid(i+1)in
  require(valid 0)"Source occurrence pointer has an invalid escape.";value
let occurrence_of_json value : occurrence =
  exact["source_path";"role";"disposition";"targets"]value;
  let source_path=source_pointer(get "source_path" value)in
  let role=match text "role" value with "declaration"->Declaration|"predicate"->Predicate|"state_write"->State_write
    |"effect_parameter"->Effect_parameter|"clock"->Clock|"lifecycle"->Lifecycle|"requirement"->Requirement|"metadata"->Metadata
    |_->fail "Unknown source occurrence role."in
  let disposition=match text "disposition" value with "executable"->Executable|"constant"->Constant
    |"obligation"->Obligation|"retained_metadata"->Retained_metadata|_->fail "Unknown occurrence disposition."in
  let targets=List.map endpoint_of_json(bounded_list ~maximum:16(get "targets" value))in
  unique "occurrence target"(List.map endpoint_key targets);
  require(match disposition,role with
    |(Executable|Constant),(Requirement|Metadata)->false
    |(Executable|Constant),_->targets<>[]
    |Obligation,Requirement->targets=[]
    |Retained_metadata,(Metadata|Declaration|Clock)->targets=[]
    |_->false)"Occurrence role, disposition and execution targets disagree.";
  {source_path;role;disposition;targets}
let arbiter_lanes = function Exclusive_arbiter n->Some n|Priority_arbiter order->Some(List.length order)|_->None
let validate_graph (value:t) =
  let node_index=Hashtbl.create 32 in
  List.iter(fun(n:node)->Hashtbl.add node_index n.node_id n)value.node_values;
  let node identity=match Hashtbl.find_opt node_index identity with Some n->n|None->fail "Endpoint names an absent implementation node."in
  let port direction (endpoint:endpoint)=
    let n=node endpoint.node_id in
    match List.find_opt(fun(p:port)->p.port_id=endpoint.port_id)(ports n.model.primitive)with
    |Some p when p.direction=direction->p
    |_->fail "Endpoint names an absent port or reverses its direction."in
  let drivers=Hashtbl.create 32 and consumers=Hashtbl.create 32 in
  let drive (endpoint:endpoint)=let key=endpoint_key endpoint in
    require(not(Hashtbl.mem drivers key))"An input has multiple drivers or an aliased binding.";Hashtbl.add drivers key ()in
  List.iter(fun(w:wire)->
    let output=port Output w.producer and input=port Input w.consumer in
    require(output.signal_type=input.signal_type)"Wire signal types differ.";
    let producer=node w.producer.node_id and consumer=node w.consumer.node_id in
    require(producer.model.replication=consumer.model.replication ||
      (producer.model.replication=Executor && (match producer.model.primitive with Truth_constant _|Product_constant _->true|_->false)))
      "Wire scope differs; only immutable constants may broadcast to encounter slots.";
    drive w.consumer;
    let key=endpoint_key w.producer in
    Hashtbl.replace consumers key(w.consumer::Option.value(Hashtbl.find_opt consumers key)~default:[]))value.wire_values;
  List.iter(fun(input:external_input)->let p=port Input input.consumer in
    require(p.signal_type=(match input.input_kind with Evidence_input->Evidence_batch|Feedback_input->Feedback_batch))
      "External input kind differs from its closed receiving port.";drive input.consumer)value.input_values;
  List.iter(fun(n:node)->List.iter(fun(p:port)->if p.direction=Input then
    require(Hashtbl.mem drivers(endpoint_key{node_id=n.node_id;port_id=p.port_id}))"Implementation input is undriven.")(ports n.model.primitive))value.node_values;
  let expected_exports=List.concat_map(fun(n:node)->List.filter_map(fun(p:port)->if p.direction=Output then
    Some{node_id=n.node_id;port_id=p.port_id}else None)(ports n.model.primitive))value.node_values in
  require(value.export_values=expected_exports)"Semantic exports must contain every output in profile-fixed node/port order; hidden projections are forbidden.";
  let member_groups=Hashtbl.create 16 in
  List.iter(fun(g:atomic_group)->
    let a=node g.arbiter in
    let lanes=match arbiter_lanes a.model.primitive with Some n->n|None->fail "Atomic group does not name an arbiter."in
    require(List.length g.commits=lanes)"Atomic group must own every arbiter lane.";
    List.iter(fun id->require(not(Hashtbl.mem member_groups id))"Atomic node belongs to multiple groups.";Hashtbl.add member_groups id g.group_id)(g.arbiter::g.commits);
    List.iteri(fun lane identity->let commit=node identity in
      require(commit.model.replication=a.model.replication)"Atomic group has inconsistent scope.";
      let writes,requests=match commit.model.primitive with Atomic_commit{writes;requests}|Transition_commit{writes;requests;_}->writes,requests|_->fail "Atomic group member is not a commit."in
      let expected={node_id=identity;port_id="grant"}in
      let actual=Option.value(Hashtbl.find_opt consumers(endpoint_key{node_id=g.arbiter;port_id="out"^string_of_int lane}))~default:[]in
      require(actual=[expected])"Arbiter lane must drive exactly its corresponding atomic commit.";
      let destinations=ref []in
      List.iter(fun(prefix,count)->for i=0 to count-1 do
        match Hashtbl.find_opt consumers(endpoint_key{node_id=identity;port_id=prefix^string_of_int i})with
        |Some[destination]->destinations:=destination.node_id:: !destinations
        |_->fail "Atomic writes/requests must have exactly one concrete bank destination."
      done)["write",writes;"request",requests];
      (match commit.model.primitive with Transition_commit _->
        (match Hashtbl.find_opt consumers(endpoint_key{node_id=identity;port_id="machine_write"})with
         |Some[destination]->destinations:=destination.node_id:: !destinations
         |_->fail "Machine transition requires one concrete machine-bank destination.")|_->());
      unique "atomic destination" !destinations)g.commits)value.group_values;
  List.iter(fun(n:node)->match n.model.primitive with
    |Exclusive_arbiter _|Priority_arbiter _|Atomic_commit _|Transition_commit _->require(Hashtbl.mem member_groups n.node_id)"Atomic node lacks group ownership."
    |Truth_register _|Attempt_bank _|Machine_bank _->
        let groups=value.wire_values|>List.filter_map(fun(w:wire)->if w.consumer.node_id=n.node_id &&
          (match(node w.producer.node_id).model.primitive with Atomic_commit _|Transition_commit _->true|_->false)
          then Hashtbl.find_opt member_groups w.producer.node_id else None)|>List.sort_uniq String.compare in
        require(List.length groups<=1)"Bank writers require one common arbitration group in this profile."
    |_->())value.node_values;
  (* Only state writes and newly created attempt events cross a declared phase
     boundary. Every remaining dependency must be a DAG. *)
  let instantaneous=List.filter(fun(w:wire)->match(node w.consumer.node_id).model.primitive with
    |Truth_register _|Machine_bank _->false|Attempt_bank _ when w.consumer.port_id="request"->false|_->true)value.wire_values in
  let done_ids=ref Names.empty in
  let rec order remaining=match remaining with []->()|_->
    let ready,blocked=List.partition(fun(n:node)->List.for_all(fun(w:wire)->w.consumer.node_id<>n.node_id||Names.mem w.producer.node_id !done_ids)instantaneous)remaining in
    require(ready<>[])"Implementation contains an instantaneous or undeclared scheduling cycle.";
    List.iter(fun(n:node)->done_ids:=Names.add n.node_id !done_ids)ready;order blocked in
  order value.node_values;
  let covered=ref Names.empty in
  List.iter(fun(o:occurrence)->List.iter(fun target->ignore(port Output target);
    if o.disposition=Constant then require(match(node target.node_id).model.primitive with Truth_constant _|Product_constant _->true|_->false)
      "Constant disposition must identify an actual constant primitive.";
    covered:=Names.add target.node_id !covered)o.targets)value.occurrence_values;
  require(List.for_all(fun(n:node)->Names.mem n.node_id !covered)value.node_values)"Implementation node lacks any source occurrence disposition."
let of_json ~library raw : t =
  measure raw;exact["schema_version";"profile";"observable_profile";"authority";"slot_layout";"nodes";"wires";"inputs";"atomic_groups";"semantic_exports";"occurrences"]raw;
  require(text "schema_version" raw=candidate_schema && List.mem(text "profile" raw)[profile;staged_profile] &&
    text "observable_profile" raw=observable_profile_for(text "profile" raw))
    "Unknown implementation or observable profile.";
  let authority_value=authority_of_json(get "authority" raw)in
  require(authority_value.library_digest=library_digest library)"Candidate names a different independently supplied library.";
  let layout=get "slot_layout" raw in exact["id";"encounter";"slots"]layout;
  let layout_value={layout_id=name(get "id" layout);encounter_id=name(get "encounter" layout);slots=integer ~minimum:1 ~maximum:16(get "slots" layout)}in
  let node_values=List.map(fun value->exact["id";"model";"configuration_digest"]value;
    let node_id=name(get "id" value)and pin=Pinned_identity.of_json(get "model" value)in
    let model=match List.find_opt(fun(m:model)->Json.equal(Pinned_identity.to_json m.identity)(Pinned_identity.to_json pin))library.model_values with
      |Some model->model|None->fail "Candidate model identity is absent from the complete supplied library."in
    require(sha(get "configuration_digest" value)=model.configuration_digest)"Candidate configuration differs from the exact supplied model.";
    (match model.replication with Executor->()|Encounter_slots{layout_id;slots}->
      require(layout_id=layout_value.layout_id && slots=layout_value.slots)"Model replication differs from the declared ordered slot layout.");
    {node_id;model})(bounded_list ~maximum:256(get "nodes" raw))in
  require(node_values<>[])"Implementation graph cannot be empty.";unique "node"(List.map(fun(n:node)->n.node_id)node_values);
  require(text "profile" raw=staged_profile || List.for_all(fun(n:node)->profile_for_primitive n.model.primitive=profile)node_values)
    "Legacy graph cannot contain staged primitive nodes.";
  let wire_values=List.map(fun value->exact["producer";"consumer"]value;
    {producer=endpoint_of_json(get "producer" value);consumer=endpoint_of_json(get "consumer" value)})
    (bounded_list ~maximum:2048(get "wires" raw))in
  let input_values=List.map(fun value->exact["id";"kind";"consumer"]value;
    let input_kind=match text "kind" value with "evidence"->Evidence_input|"feedback"->Feedback_input|_->fail "Unknown external input kind."in
    {input_id=name(get "id" value);input_kind;consumer=endpoint_of_json(get "consumer" value)})
    (bounded_list ~maximum:64(get "inputs" raw))in
  unique "external input"(List.map(fun(i:external_input)->i.input_id)input_values);
  let group_values=List.map(fun value->exact["id";"arbiter";"commits"]value;
    let commits=List.map(fun value->name value)(bounded_list ~maximum:64(get "commits" value))in unique "atomic commit" commits;
    {group_id=name(get "id" value);arbiter=name(get "arbiter" value);commits})
    (bounded_list ~maximum:64(get "atomic_groups" raw))in
  unique "atomic group"(List.map(fun(g:atomic_group)->g.group_id)group_values);
  let export_values=List.map endpoint_of_json(bounded_list ~maximum:2048(get "semantic_exports" raw))in
  let occurrence_values=List.map occurrence_of_json(bounded_list ~maximum:2048(get "occurrences" raw))in
  unique "source occurrence"(List.map(fun(o:occurrence)->o.source_path)occurrence_values);
  let result={raw;authority_value;layout_value;node_values;wire_values;input_values;group_values;export_values;occurrence_values}in
  validate_graph result;result
let to_json (value:t)=value.raw
let implementation_profile (value:t)=text "profile" value.raw
let implementation_observable_profile (value:t)=text "observable_profile" value.raw
let fingerprint (value:t)=Canonical.fingerprint value.raw
let authority (value:t)=value.authority_value
let slot_layout (value:t)=value.layout_value
let nodes (value:t)=value.node_values
let wires (value:t)=value.wire_values
let inputs (value:t)=value.input_values
let atomic_groups (value:t)=value.group_values
let semantic_exports (value:t)=value.export_values
let occurrences (value:t)=value.occurrence_values
let check_authority ~expected (value:t)=require(expected=value.authority_value)"Candidate differs from independently supplied original authority."
let check_occurrence_inventory ~expected (value:t)=
  let rec preflight count seen = function
    |[]->()
    |path::remaining->
        require(count<2048)"External occurrence inventory exceeds its bound.";
        ignore(source_pointer(str path));
        require(not(Names.mem path seen))"Duplicate expected occurrence identity.";
        preflight(count+1)(Names.add path seen)remaining in
  preflight 0 Names.empty expected;
  require(expected=List.map(fun(o:occurrence)->o.source_path)value.occurrence_values)
    "Candidate occurrence inventory differs from independently derived original source."

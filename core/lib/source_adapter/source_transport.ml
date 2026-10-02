open Bioc_wire
open Bioc_domain
module B=Behavior
module D=Execution_data
module N=Runtime_number
module C=Architecture_contract.Channel
module A=Architecture_build
module T=Source_transport_data
module R=Bioc_semantics.Reference
module W=Bioc_checker.Work_budget
module K=Bioc_checker.Architecture_check
module Names=Map.Make(String)
module Ids=Set.Make(String)
module Times=Map.Make(Z)
let implementation_version="biocompiler.ocaml.source_transport.v0.1"
let resource_profile="biocompiler.source_transport.resources.v1"
let max_work=50_000_000
let max_queued_deliveries=100_000
let max_replayed_frames=100_000
let max_replayed_trace_items=1_000_000
let require=Diagnostic.require
let fail=Diagnostic.fail
let obj values=Json.Object values
let arr values=Json.Array values
let str value=Json.String value
let field key raw=Json.field key (Json.object_fields raw)
type budget={work:W.t;mutable frames:int;mutable trace_items:int;mutable enqueues:int}
let make_budget ?parent ?(maximum=max_work) ()=
  require (maximum>=0 && maximum<=max_work) "invalid_work_budget" "Source transport work allowance exceeds its fixed ceiling.";
  let work=match parent with
    | None->W.create ~profile:resource_profile ~error_code:"source_transport_work_limit" ~maximum ()
    | Some parent->W.nested ~parent ~profile:resource_profile ~error_code:"source_transport_work_limit" ~maximum () in
  {work;frames=0;trace_items=0;enqueues=0}
let remaining_work budget=W.remaining budget.work
let spend budget amount=W.charge budget.work amount
let output ()=W.create_output ~profile:resource_profile ~error_code:"source_transport_output_limit"
  ~max_bytes:Limits.max_response_bytes ~max_nodes:Limits.max_json_nodes ()
let checked_output budget raw=
  W.reserve_json (output ()) raw;
  let pending=ref [raw] and count=ref 0 in
  while !pending<>[] do
    let raw=List.hd !pending in pending:=List.tl !pending;incr count;
    (match raw with Json.Array values->pending:=values @ !pending
     | Json.Object fields->count:= !count+List.length fields;pending:=List.map snd fields @ !pending
     | _->())
  done;
  spend budget !count
let duration=Type_spec.of_json (obj ["kind",str "scalar";"name",str "Duration";
  "dimensions",obj ["time",Json.int 1];"arguments",arr []])
let seconds raw label=
  let raw=match raw with
    | Json.Object _ ->
        (try
          let dtype=Type_spec.of_json (field "type" raw) in
          require (Type_spec.kind dtype=Type_spec.Scalar && Type_spec.compatible dtype duration)
            "source_transport_seconds" (label ^ " must have duration units.");
          field "canonical_value" (Type_spec.normalize_binding ~expected:duration raw)
        with Diagnostic.Error error when error.code<>"source_transport_seconds" ->
          fail "source_transport_seconds" (label ^ " must have duration units."))
    | value->value in
  let message=label ^ " must be an integer number of canonical seconds." in
  match raw with
  | Json.Int value ->
      require (Z.sign value>=0 && Float.is_finite (Z.to_float value)) "source_transport_seconds" message;value
  | Json.Float value when Float.is_finite value && value>=0. && Float.floor value=value -> Z.of_float value
  | _->fail "source_transport_seconds" message
let node_id node=Identity.Node.to_string (B.node_id node)
let input_ids node=List.map Identity.Node.to_string (B.inputs node)
let node nodes identity=match Names.find_opt identity nodes with
  | Some value->value|None->fail "source_transport_channel" "Selected transport references an absent source node."
let channel_text getter channel=Identity.Node.to_string (getter channel)
let role_text getter channel=Identity.Role.to_string (getter channel)
let all_unique values=List.length values=List.length (List.sort_uniq String.compare values)
let in_grid ~step ~horizon time=Z.compare time horizon<=0 && Z.equal (Z.rem time step) Z.zero
let last values=List.hd (List.rev values)
type channel={declaration:C.t;identity:string;sender_role:string;receiver_role:string;sender:string;receiver:string;
  delay:Z.t;persistence:N.t option;pulse:bool}
type receiver={role:string;observation:string;channels:channel list;baseline:N.t;aggregation:C.aggregation}
let evaluate ?budget ~expected_request build input=
  let budget=Option.value ~default:(make_budget ()) budget in
  let assessment=K.check ~budget:(K.make_budget ~parent:budget.work ()) ~expected_request build in
  require (Architecture_assessment.passed assessment && Architecture_assessment.translation_complete assessment &&
    Architecture_assessment.construction_complete assessment && A.status build=A.Compiled && A.plan build<>None &&
    Source_execution_manifest.behavior (A.execution build)<>None) "source_transport_authority"
    "Coupled execution requires fresh complete independent architecture verification.";
  let plan=Option.get (A.plan build) and behavior=Option.get (Source_execution_manifest.behavior (A.execution build)) in
  let step=seconds (T.Input.step input) "Transport step" and horizon=seconds (T.Input.until input) "Execution horizon" in
  require (Z.sign step>0 && Z.equal (Z.rem horizon step) Z.zero) "source_transport_grid"
    "Step must be positive and the horizon must lie on its grid.";
  let max_samples=match T.Input.max_samples input with
    | Json.Int value when Z.compare value Z.one>=0 && Z.compare value (Z.of_int 1000)<=0->Z.to_int value
    | _->fail "source_transport_samples" "max_samples must be an integer from 1 to 1000." in
  let samples=Z.succ (Z.div horizon step) in
  require (Z.compare samples (Z.of_int max_samples)<=0) "source_transport_samples" "Transport grid exceeds declared max_samples.";
  let sample_count=Z.to_int samples in
  let nodes=List.fold_left (fun nodes value->spend budget 1;Names.add (node_id value) value nodes) Names.empty (B.nodes behavior) in
  let role_nodes=List.filter (fun node->match B.operation node with B.Role _->true|_->false) (B.nodes behavior) in
  let roles=List.map node_id role_nodes in
  require (List.length roles<=10000/sample_count) "source_transport_roles" "Transport execution exceeds 10000 role evaluations.";
  let aliases=List.fold_left (fun values node->match B.operation node with
    | B.Role {name;_}->Names.add name (node_id node) values|_->values) Names.empty role_nodes in
  let external_snapshots=List.fold_left (fun values (key,frames)->
    spend budget 1;
    let role=if List.mem key roles then Some key else Names.find_opt key aliases in
    require (role<>None && not (Names.mem (Option.get role) values)) "source_transport_history" "Unknown or duplicate external role history.";
    require (frames<>[] && List.length frames<=max_samples) "source_transport_history" "Each role needs bounded InputFrame snapshots.";
    let first=List.hd frames in
    require (N.equal (D.Input_frame.time first) N.zero) "source_transport_history" "External histories must start at zero and strictly increase.";
    ignore (List.fold_left (fun prior frame->
      spend budget 1;
      let now=D.Input_frame.time frame in
      Option.iter (fun previous->require (N.compare previous now<0) "source_transport_history" "External histories must start at zero and strictly increase.") prior;
      let time=seconds (N.to_json now) "External input timestamp" in
      require (in_grid ~step ~horizon time) "source_transport_grid" "External observations must lie on the declared transport grid.";
      Some now) None frames);
    Names.add (Option.get role) (Array.of_list frames) values) Names.empty (T.Input.histories input) in
  require (List.sort String.compare roles=List.map fst (Names.bindings external_snapshots)) "source_transport_history" "Supply exactly one external history for every source role.";
  let declarations=List.map C.of_json (A.Plan.channels plan) in
  let ids=List.map C.id declarations in
  require (all_unique ids) "source_transport_channel" "Duplicate selected channel identities.";
  let failures=List.fold_left (fun values (identity,times)->
    spend budget 1;
    require (List.mem identity ids) "source_transport_failure" "Failure flags must identify selected channels.";
    require (List.length times<=max_samples) "source_transport_failure" "Invalid channel failure history.";
    let resolved=List.map (fun value->spend budget 1;seconds value "Channel failure timestamp") times in
    let sorted=List.sort_uniq Z.compare resolved in
    require (List.length resolved=List.length sorted && List.for_all (in_grid ~step ~horizon) resolved)
      "source_transport_failure" "Channel failure timestamps must be unique grid points within the horizon.";
    Names.add identity sorted values) Names.empty (T.Input.failed_channels input) in
  let groups=ref [] in
  let channels=List.map (fun declaration->
    spend budget (1+List.length (B.nodes behavior));
    let delay=seconds (Architecture_deployment.Time.to_json (C.latency_seconds declaration)) "Channel latency" in
    require (Z.sign delay>0 && Z.equal (Z.rem delay step) Z.zero) "source_transport_latency" "Zero-delay feedback and off-grid channel latency are unsupported.";
    let persistence=Option.map (fun time->
      let raw=Architecture_deployment.Time.to_json time in let count=seconds raw "Channel persistence" in
      require (Z.sign count>0 && Z.equal (Z.rem count step) Z.zero) "source_transport_persistence" "Channel persistence must be positive and lie on the grid.";
      N.of_json raw) (C.persistence_seconds declaration) in
    let receiver=channel_text C.receiver_node_id declaration and sender=channel_text C.sender_node_id declaration in
    require (not (List.exists (fun value->match B.operation value,input_ids value with
      | B.Qualitative _,first::_->first=receiver|_->false) (B.nodes behavior))) "source_transport_encoding" "Numeric channel transport cannot invent qualitative observation encoding.";
    let source=node nodes sender in let pulse=B.operation source=B.Action_pulse in
    let emitter=if pulse then node nodes (List.hd (input_ids source)) else source in
    require (B.operation emitter=B.Action_emit B.Expression) "source_transport_emission" "Channel transport requires an explicit numeric source emission value.";
    let dtype=match B.data_type (node nodes (channel_text C.source_channel_id declaration)) with
      | Some value->value|None->fail "source_transport_channel" "Source channel requires a scalar data type." in
    let binding=Type_spec.normalize_binding ~expected:dtype (C.initial_value declaration) in
    let baseline=N.of_json (field "canonical_value" binding) in
    let channel={declaration;identity=C.id declaration;sender_role=role_text C.sender_role declaration;
      receiver_role=role_text C.receiver_role declaration;sender;receiver;delay;persistence;pulse} in
    let key=channel.receiver_role,receiver in
    (match List.assoc_opt key !groups with
     | None->groups:= !groups@[key,{role=channel.receiver_role;observation=receiver;channels=[channel];baseline;aggregation=C.aggregation declaration}]
     | Some group->
         require (group.aggregation=C.aggregation declaration && N.equal group.baseline baseline) "source_transport_aggregation"
           "All contributions to one receiver must agree on aggregation and initial value.";
         groups:=List.map (fun (found,group)->if found=key then found,{group with channels=group.channels@[channel];baseline} else found,group) !groups);
    channel) declarations in
  List.iter (fun (_,group)->require (group.aggregation<>C.Single_sender || List.length group.channels=1)
    "source_transport_aggregation" "single_sender transport cannot combine multiple sender declarations.") !groups;
  let observed=List.fold_left (fun set channel->Ids.add channel.receiver set) Ids.empty channels in
  let source_observed=List.fold_left (fun set value->if B.operation value=B.Channel_observation then Ids.add (node_id value) set else set) Ids.empty (B.nodes behavior) in
  require (Ids.equal observed source_observed) "source_transport_channel" "Every source channel observation needs selected transport authority.";
  Names.iter (fun _ frames->Array.iter (fun frame->
    let check (identity,_)=spend budget 1;require (not (Ids.mem identity observed)) "source_transport_override" "External histories cannot override generated channel observations." in
    List.iter check (D.Input_frame.signals frame);List.iter (fun (_,samples)->List.iter check samples) (D.Input_frame.contacts frame)) frames) external_snapshots;
  let merged=ref (List.fold_left (fun map role->Names.add role [] map) Names.empty roles) in
  let indexes=Hashtbl.create (List.length roles) and results=ref Names.empty and queue=ref Times.empty and retained=Hashtbl.create (List.length channels) in
  List.iter (fun role->Hashtbl.add indexes role 0) roles;
  List.iter (fun channel->Hashtbl.add retained channel.identity None) channels;
  let trace=ref [] in
  let held_check candidate_results candidate_trace=
    let raw=obj ["histories",obj (Names.bindings !merged |> List.map (fun (role,frames)->role,arr (List.map D.Input_frame.to_json frames)));
      "results",obj (Names.bindings candidate_results |> List.map (fun (role,value)->role,D.Result.to_json value));
      "channel_frames",arr (List.map T.Channel_frame.to_json candidate_trace);
      "channels",arr (List.map C.to_json declarations);"assumptions",arr (List.map str (A.Plan.assumptions plan))] in
    checked_output budget raw in
  for sample=0 to sample_count-1 do
    spend budget 1;
    let time=Z.mul (Z.of_int sample) step in
    let delivered=Option.value ~default:Names.empty (Times.find_opt time !queue) in
    queue:=Times.remove time !queue;
    let failed identity=
      let ticks=Option.value ~default:[] (Names.find_opt identity failures) in
      spend budget (1+List.length ticks);List.exists (Z.equal time) ticks in
    List.iter (fun channel->spend budget 1;
      if failed channel.identity then (
        require (C.failure_mode channel.declaration<>C.Unknown) "source_transport_failure" "An unknown channel failure has no executable numeric observation.";
        if C.failure_mode channel.declaration=C.Clear then Hashtbl.replace retained channel.identity None)
      else match Names.find_opt channel.identity delivered with
        | Some value->
            let expiry=Option.map (fun duration->N.add (N.Integer time) duration) channel.persistence in
            Hashtbl.replace retained channel.identity (Some (value,expiry))
        | None->(match Hashtbl.find retained channel.identity with
          | Some (_,Some expiry) when N.compare (N.Integer time) expiry>=0->Hashtbl.replace retained channel.identity None
          | _->())) channels;
    let generated=ref Names.empty and receiver_values=ref [] in
    List.iter (fun (_,group)->
      spend budget (1+List.length group.channels);
      let contributions=List.filter_map (fun channel->Option.map fst (Hashtbl.find retained channel.identity)) group.channels in
      let value=match contributions with []->group.baseline|first::rest->(match group.aggregation with
        | C.Sum->N.fsum contributions|C.Max->List.fold_left N.max first rest|C.Single_sender->first) in
      require (Float.is_finite (N.to_float value)) "source_transport_aggregation" "Channel aggregation produced a non-finite observation.";
      let prior=Option.value ~default:[] (Names.find_opt group.role !generated) in
      generated:=Names.add group.role (prior@[group.observation,D.Sample.make ~value ()]) !generated;
      receiver_values:= !receiver_values@[group.observation,value]) !groups;
    List.iter (fun role->
      spend budget 1;
      let frames=Names.find role external_snapshots in let index=ref (Hashtbl.find indexes role) in
      while !index+1<Array.length frames && N.compare (D.Input_frame.time frames.(!index+1)) (N.Integer time)<=0 do
        spend budget 1;incr index done;
      Hashtbl.replace indexes role !index;
      let frame=frames.(!index) in
      let signals=D.Input_frame.signals frame @ Option.value ~default:[] (Names.find_opt role !generated) in
      let next=D.Input_frame.make ~time:(N.Integer time) ~signals ~contacts:(D.Input_frame.contacts frame) () in
      let history=Names.find role !merged @ [next] in
      merged:=Names.add role history !merged;
      held_check !results !trace;
      require (budget.frames<max_replayed_frames && budget.trace_items<max_replayed_trace_items && remaining_work budget>0)
        "source_transport_work_limit" "Cumulative source prefix replay allowance exhausted.";
      let allowance=R.make_budget ~max_work:(remaining_work budget)
        ~max_frames:(min 10000 (max_replayed_frames-budget.frames))
        ~max_trace_items:(min 100000 (max_replayed_trace_items-budget.trace_items)) () in
      let result,usage =
        match R.evaluate_with_usage ~role ~until:(N.Integer time) ~budget:allowance behavior history with
        | value -> value
        | exception error ->
            (* Failed reference execution publishes no usage or partial trace.
               Retire its entire reserved remainder so a shared caller cannot
               repeat expensive failures without consuming the parent limit. *)
            spend budget (remaining_work budget);
            raise error in
      spend budget usage.work;budget.frames<-budget.frames+usage.frames;budget.trace_items<-budget.trace_items+usage.trace_items;
      let next_results=Names.add role result !results in held_check next_results !trace;results:=next_results) roles;
    let sent=ref [] in
    List.iter (fun channel->
      spend budget 1;
      let result=Names.find channel.sender_role !results in
      let actions=D.Frame.actions (last (D.Result.frames result)) in
      spend budget (List.length actions);
      let matches=List.filter (fun action->(if channel.pulse then D.Action.specification_id action else D.Action.action_id action)=channel.sender) actions in
      require (List.length matches<=1) "source_transport_emission" "Multiple active emitter requests need an explicit within-sender aggregation contract.";
      match matches with []->()|action::_->
        require (D.Action.contact_id action=None) "source_transport_emission" "Contact-scoped emitter transport requires an identity policy.";
        let value=match List.assoc_opt "value" (Json.object_fields (D.Action.values action)) with
          | Some (Json.Int _ as raw)|Some (Json.Float _ as raw)->N.of_json raw
          | _->fail "source_transport_emission" "Emission must supply a finite canonical scalar value." in
        require (Float.is_finite (N.to_float value)) "source_transport_emission" "Emission must supply a finite canonical scalar value.";
        let arrival=Z.add time channel.delay in
        if Z.compare arrival horizon<=0 then (
          require (budget.enqueues<max_queued_deliveries) "source_transport_queue_limit" "Cumulative queued transport delivery limit exceeded.";
          budget.enqueues<-budget.enqueues+1;
          let existing=Option.value ~default:Names.empty (Times.find_opt arrival !queue) in
          queue:=Times.add arrival (Names.add channel.identity value existing) !queue);
        sent:= !sent@[channel.identity,{T.Channel_frame.value;delivery_time=arrival}]) channels;
    let failed_channel_ids=Names.bindings failures |> List.filter_map (fun (identity,_)->if failed identity then Some identity else None) in
    let frame=T.Channel_frame.make ~time ~receiver_values:!receiver_values ~sent:!sent ~failed_channel_ids in
    let next_trace= !trace@[frame] in held_check !results next_trace;trace:=next_trace
  done;
  let result=T.Result.make ~request_fingerprint:(Architecture_request.fingerprint expected_request)
    ~build_fingerprint:(A.fingerprint build) ~step_seconds:step ~horizon_seconds:horizon ~histories:(Names.bindings !merged)
    ~results:(Names.bindings !results) ~channel_frames:!trace ~channels:declarations ~failed_channels:(Names.bindings failures)
    ~assumptions:(A.Plan.assumptions plan) ~max_samples in
  checked_output budget (T.Result.to_json result);result

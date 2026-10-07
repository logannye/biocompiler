open Bioc_wire
module R = Bioc_domain.Policy_realization_request
module I = Bioc_domain.Policy_implementation
module U = Bioc_domain.Policy_implementation_binding
module Admission = Bioc_checker.Policy_admission
module Realization = Bioc_checker.Policy_realization_admission
module Lower = Bioc_compiler.Policy_lowering
module Staged = Bioc_compiler.Policy_staged_lowering
module Meter = Bioc_checker.Policy_generation_meter
let require condition message=if not condition then failwith message
let s value=Json.String value
let a values=Json.Array values
let get key value=Json.field key(Json.object_fields value)
let rows key value=Json.array(get key value)
let text key value=Json.string(get key value)
let set key item value=Json.Object(List.map(fun(name,value)->name,if name=key then item else value)(Json.object_fields value))
let rec edit path change value=match path with []->change value|key::rest->set key(edit rest change(get key value))value
let read path=let channel=open_in_bin path in
  Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
    Json.parse_bounded ~max_bytes:(8*1024*1024) ~max_nodes:400000
      (really_input_string channel(in_channel_length channel)))

(* Source and realization admission happen before measurement. The forwarding
   callback also meters later exact catalog membership checks, without charging
   preparation to the staged generation interval or changing its authority. *)
type prepared={request:R.t;admitted:Realization.admitted_inputs;meter:(int->unit)ref}
let prepare raw=
  let request=R.of_json raw in
  let source=Admission.admit ~document:(R.document request) ~descriptors:(R.definitions request)in
  let behavior=Lower.lower source and meter=ref Meter.no_charge in
  let admitted=Realization.admit_metered ~charge:(fun amount->(!meter)amount) ~request ~behavior in
  {request;admitted;meter}
let generate prepared charge=
  prepared.meter:=charge;
  Fun.protect ~finally:(fun()->prepared.meter:=Meter.no_charge)(fun()->
    Staged.lower_metered ~charge ~admitted:prepared.admitted ~library:(R.implementation_library prepared.request))
let result_json(implementation,binding)=Json.Object[
  "implementation",I.to_json implementation;"binding",U.to_json binding]
type usage={work:int;calls:int}
let measured prepared=
  let work=ref 0 and calls=ref 0 in
  let result=generate prepared(fun amount->require(amount>=0)"Negative generation debit";
    incr calls;work:= !work+amount)in
  require(!work>0 && !calls>1)"Generation did not expose its work through the callback";
  result,{work= !work;calls= !calls}
let controls=ref 0
let injected_code="literal_staged_generation_limit"
let exhaustion ()=Diagnostic.fail injected_code "Injected staged generation exhaustion."
let rejects code action=
  incr controls;
  match action()with
  |_->failwith("Staged generation unexpectedly completed: "^code)
  |exception Diagnostic.Error diagnostic->
      require(diagnostic.code=code)("Staged generation replaced the injected rejection: "^diagnostic.code)
let budget maximum=
  let spent=ref 0 and calls=ref 0 in
  (fun amount->require(amount>=0)"Negative bounded generation debit";incr calls;
    if amount>maximum - !spent then exhaustion();spent:= !spent+amount),spent,calls
let stable prepared expected expected_usage=
  let actual,usage=measured prepared in
  require(usage=expected_usage)"The same original inputs changed the deterministic generation count";
  require(Json.equal(result_json expected)(result_json actual))"Count-only metering changed the generated candidate"
let bounded_controls prepared baseline usage=
  let callback,spent,calls=budget 0 in
  rejects injected_code(fun()->generate prepared callback);
  require(!spent=0 && !calls=1)"Zero budget was not rejected at the first generation charge";
  let calls=ref 0 in
  rejects injected_code(fun()->generate prepared(fun amount->incr calls;
    require(amount=1)"The first staged generation charge moved after variable work";exhaustion()));
  require(!calls=1)"First-charge exhaustion was caught or retried";
  (* Early input passes, middle model/search passes and final staging passes.
     These are callback positions, not producer-provided semantic expectations. *)
  let positions=List.sort_uniq Int.compare[2;usage.calls/4;usage.calls/2;3*usage.calls/4;usage.calls-1;usage.calls]in
  List.iter(fun position->
    let calls=ref 0 and debited=ref 0 in
    rejects injected_code(fun()->generate prepared(fun amount->
      require(amount>=0)"Negative injected generation debit";
      incr calls;debited:= !debited+amount;
      if !calls=position then exhaustion()));
    require(!calls=position && !debited>0)"A post-charge exhaustion was retried, refunded or swallowed")positions;
  let callback,spent,_=budget(usage.work-1)in
  rejects injected_code(fun()->generate prepared callback);
  require(!spent>0 && !spent<usage.work)"Final output reservation bypassed the remaining outer allowance";
  let callback,spent,_=budget usage.work in
  let exact=generate prepared callback in
  require(!spent=usage.work && Json.equal(result_json exact)(result_json baseline))
    "The exact measured allowance failed or changed the candidate";
  stable prepared baseline usage

let repin_model id body model=
  model|>set "body" body
    |>set "configuration_digest"(s(Canonical.fingerprint(get "configuration" body)))
    |>set "identity"(get "identity" model|>set "id"(s id)
      |>set "content_fingerprint"(s(Canonical.fingerprint body)))
let with_alternatives raw ~models:extra_models ~layouts=
  let library=get "implementation_library" raw in
  let originals=rows "models" library in
  let evidence=List.find(fun model->text "primitive"(get "body" model)="evidence_bank")originals in
  let original_body=get "body" evidence in
  let misses=List.init extra_models(fun index->
    let body=edit["configuration";"freshness_ticks"](fun _->Json.int(100+index))original_body in
    repin_model("meter.unmatched.model."^string_of_int index)body evidence)in
  (* Each earlier layout has a valid evidence bank and then lacks the machine
     model. Reaching the original layout must retain every failed attempt. *)
  let partials=List.init layouts(fun index->
    let body=edit["replication";"layout_id"](fun _->s("0.incomplete."^string_of_int index))original_body in
    repin_model("meter.incomplete.layout."^string_of_int index)body evidence)in
  let additions=misses@partials in
  raw|>set "implementation_library"(set "models"(a(originals@additions))library)
    |>set "catalog_bindings"(a(List.map(fun bridge->set "models"
      (a(rows "models" bridge@List.map(get "identity")additions))bridge)(rows "catalog_bindings" raw)))
let unchanged_selection baseline actual=
  let original_graph,original_binding=baseline and actual_graph,actual_binding=actual in
  let original=I.to_json original_graph and actual=I.to_json actual_graph in
  let original_pin=get "library_digest"(get "authority" original)in
  require(get "library_digest"(get "authority" actual)<>original_pin)"Alternative models did not change original library authority";
  let comparable=edit["authority";"library_digest"](fun _->original_pin)actual in
  require(Json.equal original comparable && Json.equal(U.to_json original_binding)(U.to_json actual_binding))
    "Unmatched alternatives changed the selected original nodes, source mapping or binding"
let alternatives raw baseline baseline_usage=
  let model_input=prepare(with_alternatives raw ~models:3 ~layouts:0)in
  let model_result,model_usage=measured model_input in
  unchanged_selection baseline model_result;
  require(model_usage.work>baseline_usage.work)"Rejected supplied model scans were uncharged";
  let one_layout=prepare(with_alternatives raw ~models:3 ~layouts:1)in
  let one_result,one_usage=measured one_layout in
  unchanged_selection baseline one_result;
  require(one_usage.work>model_usage.work)"An incomplete earlier layout was uncharged";
  let several=prepare(with_alternatives raw ~models:3 ~layouts:3)in
  let several_result,several_usage=measured several in
  unchanged_selection baseline several_result;
  require(several_usage.work>one_usage.work)"Repeated incomplete layouts refunded earlier search work";
  let callback,spent,_=budget baseline_usage.work in
  rejects injected_code(fun()->generate several callback);
  require(!spent>0)"Rejected alternatives failed without retaining previous work";
  stable several several_result several_usage;
  several_usage.work
let unsupported_topology raw=
  let altered=edit["document";"program";"declarations"](fun declarations->
    a(List.map(fun declaration->if text "$type" declaration="Machine"then
      set "states"(a(rows "states" declaration@[s "unused.sixth.state"]))declaration else declaration)(Json.array declarations)))raw in
  let admitted=prepare altered in
  rejects "policy_staged_lowering_unsupported"(fun()->generate admitted(fun _->()))
let ()=
  require(Array.length Sys.argv=2)"Supply the independent staged realization request";
  let raw=read Sys.argv.(1)in
  let prepared=prepare raw in
  let baseline,usage=measured prepared in
  stable prepared baseline usage;
  bounded_controls prepared baseline usage;
  let expanded_work=alternatives raw baseline usage in
  unsupported_topology raw;
  Printf.printf "Staged generation metering: %d controls; baseline=%d/%d calls; alternatives=%d work.\n"
    !controls usage.work usage.calls expanded_work

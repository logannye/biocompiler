open Bioc_wire
module I = Bioc_domain.Policy_implementation
let require condition message = if not condition then failwith message
let s value=Json.String value
let o value=Json.Object value
let a value=Json.Array value
let get key value=Json.field key(Json.object_fields value)
let rows key value=Json.array(get key value)
let text key value=Json.string(get key value)
let replace key item value=o(List.map(fun(name,value)->name,if name=key then item else value)(Json.object_fields value))
let endpoint node port=o["node",s node;"port",s port]
let wire from_node from_port to_node to_port=o["producer",endpoint from_node from_port;"consumer",endpoint to_node to_port]
(* Literal graph authority, independent of every lowering producer and source
   interpreter. Every output is listed here, not discovered from I.ports. *)
let fixture ?(retained_capacity=1) ?(wide=false) ?(foreign=false) () =
  let replica=o["kind",s "encounter_slots";"layout_id",s "slots";"slots",Json.int 2]in
  let spec id tag configuration outputs = id,tag,configuration,outputs in
  let transitions=[
    "start","ready","first","edge","events",false,(if wide then ["first";"second"]else ["first"]);
    "handoff","first","second",(if foreign then "foreign_completed"else "first_completed"),"selected",true,(if wide then []else ["second"]);
    "finish","second","completed","second_completed","selected",true,[];
    "first_fail","first","failed","first_failed","selected",true,[];
    "second_fail","second","failed","second_failed","selected",true,[];
    "first_timeout","first","failed","first_timed_out","selected",true,[];
    "second_timeout","second","failed","second_timed_out","selected",true,[]]in
  let stages=["first";"second"]@(if foreign then ["foreign"]else [])in
  let selectors=List.concat_map(fun stage->List.map(fun event->
    spec(stage^"_"^event)"event_select"(o["event_kind",s event])["selected"])
    (if stage="foreign"then ["completed"]else ["completed";"failed";"timed_out"]))stages in
  let specs=[
    spec "evidence" "evidence_bank"(o["freshness_ticks",Json.int 20])["value";"updated"];
    spec "edge" "observed_rising"(o[])["events"];
    spec "product" "product_constant"(o["product",s "fixture.product.same"])["out"];
    spec "true" "truth_constant"(o["value",s "true"])["out"];
    spec "machine" "machine_bank"(o["states",a(List.map s["ready";"first";"second";"completed";"failed"]);
      "initial",s "ready";"terminal",a[s "completed";s "failed"];"writers",Json.int 7;
      "retained_capacity",Json.int retained_capacity])["snapshot"]]@
    List.map(fun stage->spec stage "attempt_bank"(o["capacity",Json.int 2;"timeout_ticks",Json.int 2;
      "authorization",s "continuous";"on_loss",s "continue";"on_unknown",s "defer"])["events";"snapshot"])stages@
    selectors@
    List.map(fun(id,source,_,_,_,correlate,_)->spec(id^"_gate")"transition_gate"
      (o["source",s source;"correlation",s(if correlate then "retained_attempt"else "unbound")])["candidate"])transitions@
    [spec "arbiter" "exclusive_arbiter"(o["lanes",Json.int 7])(List.init 7(fun i->"out"^string_of_int i))]@
    List.map(fun(id,_,destination,_,_,_,requests)->spec(id^"_commit")"transition_commit"
      (o["destination",s destination;"writes",Json.int 0;"requests",Json.int(List.length requests)])
      (List.mapi(fun i _->"request"^string_of_int i)requests@["machine_write"]))transitions@
    (if foreign then [spec "foreign_gate" "activation_gate"(o[])["candidate"];
      spec "foreign_arbiter" "exclusive_arbiter"(o["lanes",Json.int 1])["out0"];
      spec "foreign_commit" "atomic_commit"(o["writes",Json.int 0;"requests",Json.int 1])["request0"]]else [])in
  let models=List.map(fun(id,tag,configuration,_)->
    let staged=List.mem tag["machine_bank";"transition_gate";"transition_commit"]in
    let body=o["schema_version",s "biocompiler.policy_primitive_model.v0.1";
      "profile",s(if staged then "biocompiler.policy_staged_primitives.v0.1"else "biocompiler.policy_truth_primitives.v0.1");
      "primitive",s tag;"configuration",configuration;"replication",replica]in
    id,o["identity",o["schema_version",s "biocompiler.component_identity.v0.1";
      "id",s("fixture.staged."^id);"version",s "1";"kind",s "model";
      "content_fingerprint",s(Canonical.fingerprint body)];
      "configuration_digest",s(Canonical.fingerprint configuration);"body",body])specs in
  let library=o["schema_version",s "biocompiler.policy_implementation_library.v0.1";
    "profile",s "biocompiler.policy_staged_primitives.v0.1";"id",s "fixture.staged";"version",s "1";
    "models",a(List.map snd models)]in
  let wires=[wire "evidence" "value" "edge" "in"]@
    List.map(fun stage->wire "true" "out" stage "authorization")stages@
    List.concat_map(fun stage->List.map(fun event->wire stage "events"(stage^"_"^event)"events")
      (if stage="foreign"then ["completed"]else ["completed";"failed";"timed_out"]))stages@
    List.concat(List.mapi(fun index(id,_,_,event,port,_,requests)->
      let gate=id^"_gate"and commit=id^"_commit"in
      [wire "machine" "snapshot" gate "machine";wire event port gate "on";wire "true" "out" gate "guard";
       wire gate "candidate" "arbiter"("in"^string_of_int index);
       wire "arbiter"("out"^string_of_int index)commit "grant";
       wire commit "machine_write" "machine"("write"^string_of_int index)]@
      List.concat(List.mapi(fun request bank->[wire "product" "out" commit("product"^string_of_int request);
        wire commit("request"^string_of_int request)bank "request"])requests))transitions)@
    (if foreign then [wire "edge" "events" "foreign_gate" "on";wire "true" "out" "foreign_gate" "guard";
      wire "foreign_gate" "candidate" "foreign_arbiter" "in0";wire "foreign_arbiter" "out0" "foreign_commit" "grant";
      wire "product" "out" "foreign_commit" "product0";wire "foreign_commit" "request0" "foreign" "request"]else [])in
  let graph=o["schema_version",s "biocompiler.policy_implementation.v0.1";
    "profile",s "biocompiler.policy_staged_primitives.v0.1";"observable_profile",s "biocompiler.policy_staged_observables.v0.1";
    "authority",o(List.map(fun key->key,s(String.make 64 'a'))
      ["source_artifact_digest";"descriptors_digest";"domain_digest";"implementation_catalog_digest"]@
      ["library_digest",s(Canonical.fingerprint library)]);
    "slot_layout",o["id",s "slots";"encounter",s "encounter";"slots",Json.int 2];
    "nodes",a(List.map(fun(id,model)->o["id",s id;"model",get "identity" model;
      "configuration_digest",get "configuration_digest" model])models);
    "wires",a wires;
    "inputs",a(o["id",s "condition";"kind",s "evidence";"consumer",endpoint "evidence" "samples"]::
      List.map(fun stage->o["id",s(stage^"_feedback");"kind",s "feedback";"consumer",endpoint stage "feedback"])stages);
    "atomic_groups",a([o["id",s "machine_group";"arbiter",s "arbiter";
      "commits",a(List.map(fun(id,_,_,_,_,_,_)->s(id^"_commit"))transitions)]]@
      (if foreign then [o["id",s "foreign_group";"arbiter",s "foreign_arbiter";"commits",a[s "foreign_commit"]]]else []));
    "semantic_exports",a(List.concat_map(fun(id,_,_,outputs)->List.map(endpoint id)outputs)specs);
    "occurrences",a(List.map(fun(id,_,_,outputs)->o["source_path",s("/literal/"^id);"role",s "declaration";
      "disposition",s "executable";"targets",a(List.map(endpoint id)outputs)])specs)]in
  library,graph
let decode library graph=I.of_json ~library:(I.library_of_json library)graph
let rewire node port producer graph=replace "wires"(a(List.map(fun value->
  if get "consumer" value=endpoint node port then replace "producer" producer value else value)(rows "wires" graph)))graph
let reconfigure library graph node configuration=
  let model=List.assoc node(List.map2(fun node model->text "id" node,model)(rows "nodes" graph)(rows "models" library))in
  let body=replace "configuration" configuration(get "body" model)in
  let changed=model|>replace "body" body|>replace "configuration_digest"(s(Canonical.fingerprint configuration))
    |>replace "identity"(replace "content_fingerprint"(s(Canonical.fingerprint body))(get "identity" model))in
  let library=replace "models"(a(List.map(fun value->if value=model then changed else value)(rows "models" library)))library in
  let graph=graph|>replace "authority"(replace "library_digest"(s(Canonical.fingerprint library))(get "authority" graph))
    |>replace "nodes"(a(List.map(fun value->if text "id" value=node then value|>replace "model"(get "identity" changed)
      |>replace "configuration_digest"(get "configuration_digest" changed)else value)(rows "nodes" graph)))in
  library,graph

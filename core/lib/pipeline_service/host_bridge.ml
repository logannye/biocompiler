open Bioc_wire
module M = Bioc_compiler.Pass_manager
module W = Bioc_checker.Work_budget
module C = Bioc_domain.Pipeline_contract
type t = {budget:W.t;invoke:action:string -> arguments:Json.t -> Json.t;
  max_handles:int;max_actions:int;max_retained_bytes:int;
  mutable values:(string * M.host_value) list;mutable tuples:(M.host_value list * M.host_value) list;
  mutable handles:int;mutable tuple_count:int;mutable actions:int;
  mutable retained_bytes:int;mutable closed:bool}
let obj fields=Json.Object fields
let str value=Json.String value
let require condition message=Diagnostic.require condition "pipeline_host_bridge_limit" message
let guard (state:t) action =
  try action () with Diagnostic.Error _ as cause -> state.closed<-true;raise cause
let ensure (state:t) work=guard state (fun ()->
  require (not state.closed) "Host bridge is closed.";
  require (work==state.budget) "Host bridge must use the manager lifetime budget.";
  require (not (W.exhausted work)) "Host bridge lifetime budget has already exhausted.";
  W.charge work 1)
let measure (state:t) raw=guard state (fun ()->
  let size=C.Codec.measure ~limits:(C.Codec.make_limits ~max_bytes:33_554_432
    ~max_nodes:1_000_000 ~charge:(W.charge state.budget) ()) raw in
  require (size.bytes<=state.max_retained_bytes-state.retained_bytes)
    "Host bridge cumulative JSON retention exhausted.";
  state.retained_bytes<-state.retained_bytes+size.bytes)
let create ~budget ?(max_handles=100_000) ?(max_actions=1_000_000)
    ?(max_retained_bytes=134_217_728) ~invoke ()=
  require (max_handles>0 && max_handles<=100_000 && max_actions>0 && max_actions<=1_000_000 &&
    max_retained_bytes>0 && max_retained_bytes<=134_217_728) "Invalid host bridge limits.";
  {budget;invoke;max_handles;max_actions;max_retained_bytes;values=[];tuples=[];handles=0;tuple_count=0;actions=0;retained_bytes=0;closed=false}
let close (state:t)=state.closed<-true;state.values<-[];state.tuples<-[]
let execute (state:t) work action fields=
  ensure state work;
  guard state (fun ()->require (state.actions<state.max_actions) "Host bridge action limit exhausted.");
  let arguments=obj fields in measure state arguments;state.actions<-state.actions+1;
  (* A host exception belongs to the original callable. It propagates unchanged
     through the actual native stack; it is not converted into a new error. *)
  let result=state.invoke ~action ~arguments in
  ensure state work;measure state result;result
let boolean (state:t) raw=guard state (fun ()->Json.boolean raw)
let handle (state:t) raw=guard state (fun ()->
  let fields=Json.object_fields raw in Json.exact_fields ["handle"] fields;
  let value=Json.string (Json.field "handle" fields) in
  let prefix="object/" in
  require (String.starts_with ~prefix value && String.length value<=32) "Invalid host object reference.";
  let suffix=String.sub value (String.length prefix) (String.length value-String.length prefix) in
  require (String.length suffix>0 && (String.length suffix=1 || suffix.[0]<>'0') &&
    String.for_all (fun c->c>='0' && c<='9') suffix) "Invalid host object reference.";value)
let reference (state:t) value=
  ensure state state.budget;
  let rec find=function
    | []->guard state (fun ()->Diagnostic.fail "pipeline_host_bridge_limit" "Foreign host capability.")
    | (identity,previous)::tail->W.charge state.budget 1;
        if previous==value then obj["handle",str identity] else find tail in
  guard state (fun ()->find state.values)
let map_bounded (state:t) transform values=
  let rec loop count acc=function
    | []->List.rev acc
    | value::tail->guard state (fun ()->W.charge state.budget 1;
        require (count<state.max_handles) "Host capability collection limit exhausted.");
        let result=transform value in loop (count+1) (result::acc) tail in
  loop 0 [] values
let class_name=function M.Pass_result->"PassResult" | M.Source_link->"SourceLink"
  | M.Check_decision->"CheckDecision" | M.Mapping->"Mapping" | M.String->"str"
let comparison_name=function M.Eq->"eq" | M.Ne->"ne" | M.Is->"is"
let rec of_reference (state:t) raw=
  ensure state state.budget;
  let identity=handle state raw in
  let rec find=function []->None | (name,value)::tail->
    W.charge state.budget 1;if name=identity then Some value else find tail in
  match guard state (fun ()->find state.values) with
  | Some value->value
  | None->
    guard state (fun ()->require (state.handles<state.max_handles) "Host capability handle limit exhausted.");
    measure state raw;
    let action work name fields=execute state work name (("object",raw)::fields) in
    let boxed work name fields=of_reference state (action work name fields) in
    let to_json work value=execute state work "json" ["object",reference state value] in
    let iterator work value=
      let iter=execute state work "iter" ["object",value] in ignore(of_reference state iter);
      {M.next=(fun work->
        let next=execute state work "next" ["object",iter] in
        guard state (fun ()->
          let fields=Json.object_fields next in Json.exact_fields ["exhausted";"object"] fields;
          if Json.boolean(Json.field "exhausted" fields) then (
            require (Json.field "object" fields=Json.Null) "Exhausted host iterator returned an object.";None)
          else Some(of_reference state (Json.field "object" fields))))} in
    let value={M.attribute=(fun work name->boxed work "attr" ["name",str name]);
      attribute_default=(fun work name default->ensure state work;
        let default=literal state default in boxed work "attr-default" ["name",str name;"default",reference state default]);
      is_instance=(fun work kind->boolean state (action work "is-instance" ["type",str(class_name kind)]));
      is_none=(fun work->boolean state(action work "is-none" []));
      truth=(fun work->boolean state(action work "truth" []));
      compare=(fun work comparison constant->ensure state work;
        let other=literal state constant in boolean state (execute state work "compare"
          ["left",raw;"right",reference state other;"operator",str(comparison_name comparison)]));
      contains=(fun work constant->ensure state work;
        let container=literal state constant in boolean state(execute state work "contains"
          ["container",reference state container;"item",raw]));
      attribute_set_equal=(fun work values ~attribute constant->ensure state work;
        let members=match constant with M.Json_set values->values
          | _->guard state (fun ()->Diagnostic.fail "pipeline_host_bridge_limit" "Host attribute-set comparison requires a literal set.") in
        boolean state(execute state work "set-attribute-equal"
          ["objects",Json.Array(map_bounded state (reference state) values);"name",str attribute;"values",Json.Array members]));
      source_link_set_equal=(fun work values expected->ensure state work;
        boolean state(execute state work "source-link-set-equal"
          ["objects",Json.Array(map_bounded state (reference state) values);
           "expected",Json.Array(map_bounded state C.Source_link.to_json expected)]));
      lookup=(fun work entries->ensure state work;
        let entries=map_bounded state (fun (key,value)->Json.Array[str key;value]) entries in
        to_json work (boxed work "lookup" ["entries",Json.Array entries]));
      get_item=(fun work constant->ensure state work;
        let key=literal state constant in boxed work "get-item" ["key",reference state key]);
      get=(fun work name->
        let method_value=boxed work "attr" ["name",str "get"] in
        let key=literal state (M.Json_value(str name)) in method_value.call work [key]);
      tuple=(fun work->
        let tuple=action work "tuple" [] in let tuple_value=of_reference state tuple in
        let cursor=iterator work tuple in
        let rec collect count acc=match cursor.next work with
          | None->List.rev acc
          | Some value->guard state (fun ()->require (count<state.max_handles) "Host tuple item limit exhausted.");
            collect (count+1) (value::acc) in
        let values=collect 0 [] in
        measure state (Json.Array(map_bounded state (reference state) values));
        guard state (fun ()->require (state.tuple_count<state.max_actions) "Host tuple retention limit exhausted.");
        state.tuple_count<-state.tuple_count+1;state.tuples<-(values,tuple_value)::state.tuples;values);
      iter=(fun work->iterator work raw);
      call=(fun work values->ensure state work;of_reference state(execute state work "call"
        ["callable",raw;"args",Json.Array(map_bounded state (reference state) values);"kwargs",obj []]));
      merge=(fun work ~before ~after->boxed work "merge" ["before",before;"after",after]);
      document=(fun work->boxed work "document" []);
      freeze=(fun work->to_json work (boxed work "freeze-json" []));
      vars=(fun work->boxed work "vars" [])} in
    state.values<-(identity,value)::state.values;state.handles<-state.handles+1;value
and literal (state:t) constant=
  let action,fields=match constant with
    | M.Json_value value->"literal",["kind",str "json";"value",value]
    | M.Json_set values->"literal",["kind",str "set";"value",Json.Array values]
    | M.Evidence_kind kind->"enum",["type",str "EvidenceKind";"value",str(C.evidence_kind_name kind)]
    | M.Check_outcome kind->"enum",["type",str "CheckOutcome";"value",str(C.outcome_name kind)] in
  of_reference state(execute state state.budget action fields)
let counts (state:t)=ensure state state.budget;
  obj["handles",Json.int state.handles;"actions",Json.int state.actions;
    "retained_bytes",Json.int state.retained_bytes]

let tuple_origin (state:t) values=
  ensure state state.budget;
  let rec find=function []->None | (items,tuple)::tail->
    W.charge state.budget 1;if items==values then Some tuple else find tail in
  guard state (fun ()->find state.tuples)

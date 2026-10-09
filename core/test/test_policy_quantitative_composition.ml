open Bioc_wire
module R = Bioc_domain.Policy_realization_request
module M = Bioc_domain.Policy_component_material_request
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module F = Bioc_domain.Policy_operating_domain
module Composition_contract = Bioc_domain.Policy_quantitative_composition_contract
module K = Bioc_domain.Construction_content
module U = Bioc_domain.Policy_component_assembly_proposal
module RA = Bioc_checker.Policy_realization_admission
module B = Bioc_checker.Policy_implementation_binding_check
module S = Bioc_semantics.Policy_domain_reference
module Runtime = Bioc_candidate_runtime.Policy_primitives
module T = Bioc_realization_checker.Policy_trace_correspondence
module P = Bioc_realization_checker.Policy_preservation_check
module A = Bioc_realization_checker.Policy_component_assembly_check
module C = Bioc_realization_checker.Policy_component_context_check
module Check = Bioc_realization_checker.Policy_component_material_check
module Quant = Bioc_realization_checker.Policy_quantitative_check
module Composition = Bioc_realization_checker.Policy_quantitative_composition_check
module Outcome = Bioc_domain.Construction_assessment
module Material = Bioc_service.Policy_component_material_service
module Service = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service
module Arrange = Bioc_compiler.Policy_component_lowering
module Lower = Bioc_compiler.Policy_implementation_lowering
module Binding = Bioc_domain.Policy_implementation_binding
module Wire = Bioc_domain.Policy_coupled_wire
module Correspondence = Bioc_checker.Policy_correspondence
module Source_check = Bioc_checker.Policy_check
module Admission = Bioc_checker.Policy_admission
module Monitor = Bioc_realization_checker.Policy_requirement_monitor
module Refinement = Bioc_realization_checker.Policy_refinement_check
module Named = Bioc_domain.Policy_refinement
module Approximation = Bioc_realization_checker.Policy_approximation_check
module Approximation_contract = Bioc_domain.Policy_approximation_contract

let ()=Printexc.register_printer(function
  |Diagnostic.Error d->Some(Printf.sprintf "Diagnostic.Error(%s, %s)" d.code d.message)
  |_->None)
let s value=Json.String value
let o fields=Json.Object fields
let a values=Json.Array values
let get key value=Json.field key(Json.object_fields value)
let rows key value=Json.array(get key value)
let text key value=Json.string(get key value)
let rec at path value=match path with []->value|key::rest->at rest(get key value)
let set key item value=o(List.map(fun(name,value)->name,if name=key then item else value)(Json.object_fields value))
let rec edit path f value=match path with []->f value|key::rest->set key(edit rest f(get key value))value
let require condition message=if not condition then failwith message
let accepted label=function Some value->value|None->failwith(label^" withheld its checked capability")
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_artifact ~max_bytes:(8*1024*1024) ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let call handler role operation payload=
  let payload=if operation="plan-policy-target"then payload else Wire.encode payload in
  let request:Protocol.request={request_id="quantitative-literal";operation;payload}in
  match handler role request with
  |Protocol.Ok,Some result,[]->if Wire.is_packet result then Wire.decode result else result
  |_,_,diagnostics->failwith(operation^": "^String.concat "; "(List.map(fun(d:Diagnostic.t)->d.code^": "^d.message)diagnostics))
let controls=ref 0
let rejects label action=match action()with
  |_->failwith("Quantitative adversary accepted: "^label)
  |exception Diagnostic.Error _->incr controls
let rejected_service label operation payload=
  let request:Protocol.request={request_id="quantitative-mutant";operation;payload=Wire.encode payload}in
  match Service.handle Protocol.Verify request with
  |Protocol.Error,None,(_::_)->incr controls
  |_->failwith("Quantitative service adversary accepted: "^label)
  |exception Diagnostic.Error _->incr controls

let wire_controls previous=
  let rec cyclic_fields=("other",Json.Null)::cyclic_fields in
  require(not(Wire.is_packet(Json.Object cyclic_fields)))"Coupled packet dispatch must be bounded before preflight";
  let logical=o["b",a[Json.int 1;Json.int 1];"a",a[Json.int 1;Json.int 1]]in
  let golden=o["schema_version",s Wire.schema_version;"expanded_sha256",
    s "d0b48ae3cfa37127402304d220cab43c3b9b3ae27a73c3f80a4f41228056db53";
    "root",Json.int 2;"nodes",a[o["kind",s "integer";"value",Json.int 1];
      o["kind",s "array";"items",a[Json.int 0;Json.int 0]];
      o["kind",s "object";"fields",a[a[s "a";Json.int 1];a[s "b";Json.int 1]]]]]in
  require(Json.equal(Wire.encode logical)golden && Json.equal(Wire.decode golden)logical)
    "Coupled transport differs from the independent literal cross-language DAG";
  require(Wire.preflight logical=String.length(Canonical.encode logical))
    "Coupled transport lost complete canonical byte accounting";
  let scalars=a[Json.Null;Json.Bool true;Json.Bool false;Json.int 1;Json.Float 1.;Json.Float(-0.);
    s "\195\169\000\n";a[];o[]]in
  require(Canonical.encode(Wire.decode(Wire.encode scalars))=Canonical.encode scalars)
    "Typed transport conflated numbers, signed zero, Unicode, escapes or empty containers";
  let denied=ref 0 in
  let reject ?code label action=match action()with
    |_->failwith("Coupled wire adversary accepted: "^label)
    |exception Diagnostic.Error diagnostic->
      Option.iter(fun expected->require(diagnostic.code=expected)(label^": wrong diagnostic "^diagnostic.code))code;
      incr denied in
  let packet rows=o["schema_version",s Wire.schema_version;"expanded_sha256",s(String.make 64 '0');
    "root",Json.int(List.length rows-1);"nodes",a rows]in
  let null=o["kind",s "null"] and boolean=o["kind",s "boolean";"value",Json.Bool true]in
  let array refs=o["kind",s "array";"items",a(List.map Json.int refs)]in
  reject "changed expanded fingerprint"(fun()->Wire.decode(set "expanded_sha256"(s(String.make 64 '0'))golden));
  reject "non-final root"(fun()->Wire.decode(set "root"(Json.int 1)golden));
  reject "forward reference"(fun()->Wire.decode(packet[array[1];null]));
  reject "negative reference"(fun()->Wire.decode(packet[null;array[-1]]));
  reject "duplicate interned row"(fun()->Wire.decode(packet[null;null;array[0;1]]));
  reject "unreachable row"(fun()->Wire.decode(packet[null;boolean;array[0]]));
  reject "noncanonical reachable postorder"(fun()->Wire.decode(packet[null;boolean;array[1;0]]));
  reject "scalar kind mismatch"(fun()->Wire.decode(packet[o["kind",s "boolean";"value",Json.int 1]]));
  reject "unknown node field"(fun()->Wire.decode(packet[o["kind",s "null";"value",Json.Null]]));
  reject "unknown packet field"(fun()->Wire.decode(o(("extra",Json.Null)::Json.object_fields golden)));
  let object_node fields=o["kind",s "object";"fields",a(List.map(fun key->a[s key;Json.int 0])fields)]in
  reject "unsorted object keys"(fun()->Wire.decode(packet[null;object_node["b";"a"]]));
  reject "duplicate object keys"(fun()->Wire.decode(packet[null;object_node["a";"a"]]));
  let bomb=packet(null::List.init 20(fun index->array[index;index]))in
  let work=ref 0 in
  reject ~code:"policy_coupled_wire_limit" "exponential expanded inventory"(fun()->
    Wire.decode ~charge:(fun amount->work:= !work+amount)bomb);
  require(!work<100000)"Expanded-size rejection traversed the exponential logical value";
  reject ~code:"policy_coupled_wire_limit" "expanded canonical byte bound"(fun()->
    Wire.decode(packet[o["kind",s "string";"value",s(String.make 65536 'x')];
      array(List.init 128(fun _->0))]));
  reject ~code:"policy_coupled_wire_limit" "expanded depth"(fun()->
    Wire.decode(packet(null::List.init 129(fun index->array[index]))));
  reject ~code:"policy_coupled_wire_limit" "integer decimal bound"(fun()->Wire.encode(Json.Int(Z.pow(Z.of_int 10)4300)));
  reject "nonfinite float"(fun()->Wire.encode(Json.Float infinity));
  let rec cyclic=Json.Array[cyclic]in
  reject "cyclic logical JSON"(fun()->Wire.encode cyclic);
  reject "duplicate logical keys"(fun()->Wire.encode(o["a",Json.Null;"a",Json.Bool true]));
  reject ~code:"wire_test_budget" "charged codec work"(fun()->Wire.encode
    ~charge:(fun _->Diagnostic.fail "wire_test_budget" "No codec work remains.")logical);
  reject ~code:"policy_coupled_wire_profile" "packet cannot promote an older material family"(fun()->
    Material.unpack_payload ~assurance:false(Wire.encode(o["request",get "request" previous;
      "limits",get "limits" previous])));
  require(!denied=21)"Coupled codec adversarial control census changed"
let edge_ids=["a_to_b";"b_to_c";"a_to_c";"b_to_a";"c_to_a"]
let table_row source input destination request before after allocations=o[
  "source",s source;"input",s input;"destination",s destination;"request",Json.Bool request;
  "before",a(List.map Json.int before);"after",a(List.map Json.int after);
  "flows",a(List.map2(fun transfer quanta->o["transfer",s transfer;"quanta",Json.int quanta])edge_ids allocations)]

(* Independent literal oracle. The edge order is A->B, B->C, A->C on True,
   B->A, C->A on False. q100 distinguishes reuse of incoming stock. The
   separate network suite tests a repinned B->C-first variant for freed
   headroom; this suite adds actual selected allocation and owner-write ports. *)
let expected_table=a[
  table_row "q000" "true" "q000" false [0;0;0] [0;0;0] [0;0;0;0;0];
  table_row "q000" "false" "q000" false [0;0;0] [0;0;0] [0;0;0;0;0];
  table_row "q000" "unknown" "q000" false [0;0;0] [0;0;0] [0;0;0;0;0];
  table_row "q001" "true" "q001" false [0;0;1] [0;0;1] [0;0;0;0;0];
  table_row "q001" "false" "q100" false [0;0;1] [1;0;0] [0;0;0;0;1];
  table_row "q001" "unknown" "q001" false [0;0;1] [0;0;1] [0;0;0;0;0];
  table_row "q010" "true" "q001" false [0;1;0] [0;0;1] [0;1;0;0;0];
  table_row "q010" "false" "q100" false [0;1;0] [1;0;0] [0;0;0;1;0];
  table_row "q010" "unknown" "q010" false [0;1;0] [0;1;0] [0;0;0;0;0];
  table_row "q011" "true" "q011" false [0;1;1] [0;1;1] [0;0;0;0;0];
  table_row "q011" "false" "q101" false [0;1;1] [1;0;1] [0;0;0;1;0];
  table_row "q011" "unknown" "q011" false [0;1;1] [0;1;1] [0;0;0;0;0];
  table_row "q100" "true" "q010" true [1;0;0] [0;1;0] [1;0;0;0;0];
  table_row "q100" "false" "q100" false [1;0;0] [1;0;0] [0;0;0;0;0];
  table_row "q100" "unknown" "q100" false [1;0;0] [1;0;0] [0;0;0;0;0];
  table_row "q101" "true" "q011" true [1;0;1] [0;1;1] [1;0;0;0;0];
  table_row "q101" "false" "q101" false [1;0;1] [1;0;1] [0;0;0;0;0];
  table_row "q101" "unknown" "q101" false [1;0;1] [1;0;1] [0;0;0;0;0];
  table_row "q110" "true" "q101" false [1;1;0] [1;0;1] [0;1;0;0;0];
  table_row "q110" "false" "q110" false [1;1;0] [1;1;0] [0;0;0;0;0];
  table_row "q110" "unknown" "q110" false [1;1;0] [1;1;0] [0;0;0;0;0];
  table_row "q111" "true" "q111" false [1;1;1] [1;1;1] [0;0;0;0;0];
  table_row "q111" "false" "q111" false [1;1;1] [1;1;1] [0;0;0;0;0];
  table_row "q111" "unknown" "q111" false [1;1;1] [1;1;1] [0;0;0;0;0]]
let conservation=o[
  "scope",s "accepted_samples_within_encounter_generation";
  "quantity",s "sum_all_reservoirs";"reset",s "restore_declared_initial_vector";
  "checked_rows",Json.int 24]

let refresh_context request=
  let layout=Canonical.fingerprint(at["context";"record_layout"]request)in
  edit["context";"providers"](fun providers->a(List.map(fun provider->
    let body=get "body" provider in
    let body=if text "kind" body="environment" then
      set "grammar"(at["implementation_request";"operating_domain"]request)body else body in
    let body=edit["capacities"](fun capacities->a(List.map(fun capacity->
      set "record_layout_digest"(s layout)capacity)(Json.array capacities)))body in
    provider|>set "body" body|>edit["identity";"content_fingerprint"](fun _->s(Canonical.fingerprint body)))
    (Json.array providers)))request
let change_component request instance change=
  let selected=List.find(fun row->text "slot" row=instance)(rows "components"(at["composition_rule";"body"]request))|>get "component" in
  let components=rows "components"(get "component_library" request)in
  let component=List.find(fun value->Json.equal(get "identity" value)selected)components in
  let body=change(get "body" component)in
  let identity=set "content_fingerprint"(s(Canonical.fingerprint body))(get "identity" component)in
  let component=component|>set "body" body|>set "identity" identity in
  let selected_rows values=a(List.map(fun value->
    if Json.equal(get "component" value)selected then set "component" identity value else value)(Json.array values))in
  let rule=get "composition_rule" request|>edit["body";"components"]selected_rows in
  let rule=set "identity"(set "content_fingerprint"(s(Canonical.fingerprint(get "body" rule)))(get "identity" rule))rule in
  let request=request|>edit["component_library";"components"](fun _->a(List.map(fun value->
      if Json.equal(get "identity" value)selected then component else value)components))
    |>set "composition_rule" rule|>edit["catalog_binding";"components"]selected_rows
    |>edit["catalog_binding";"rule"](fun _->get "identity" rule)
    |>edit["quantitative";"owners"]selected_rows
    |>edit["context";"record_layout";"rule"](fun _->get "identity" rule)in
  let request=if instance="control" then edit["quantitative";"network";"selection";"component"](fun _->identity)request else request in
  refresh_context request
let change_contract request instance change=
  change_component request instance(edit["quantitative_contracts"](fun values->a(List.map change(Json.array values))))
let candidate_for request candidate=
  edit["assembly_proposal";"rule"](fun _->at["composition_rule";"identity"]request)candidate
let quant_check preservation request candidate=
  let request=M.of_json request in
  let assembly=A.check ~original:(M.implementation_request request) ~components:(M.component_library request)
    ~rule:(M.composition_rule request) ~implementation:preservation
    ~proposed:(U.of_json(get "assembly_proposal" candidate))
    ~candidate:(K.of_json(get "construction" candidate))() in
  let assembly=accepted "Fresh repinned assembly"(A.accepted assembly)in
  let context=C.check ~request ~assembly () in
  let context=accepted "Fresh repinned context"(C.accepted context)in
  Quant.check ~request ~context ()
let quantitative_failure preservation label request candidate=
  let result=quant_check preservation request(candidate_for request candidate)in
  require(Quant.accepted result=None && Quant.outcome result=Outcome.Fail &&
    get "table"(Quant.report result)=a[] &&
    get "bindings"(Quant.report result)=Json.Null && get "conservation"(Quant.report result)=Json.Null)
    ("Quantitative semantic mutant did not fail at the quantitative checker: "^label);
  incr controls

let source_bounds=S.execution_bounds_of_json(o(List.map(fun(k,v)->k,Json.int v)
  ["max_ticks",32;"max_inputs",1000;"max_encounters",4;"max_attempts",32;
   "max_work",8_000_000;"max_trace_items",100000;"max_microsteps",30]))
let initialize bound=
  let admitted=B.admitted_inputs bound and environment=B.environment bound in
  S.create ~behavior:(RA.behavior admitted) ~domain:(R.operating_domain(RA.request admitted)) ~bounds:source_bounds,
  Runtime.initialize ~implementation:(B.implementation bound)
    ~environment:{Runtime.executor=environment.executor;horizon_ticks=environment.horizon_ticks;
      slots=List.map(fun(slot:B.slot)->{Runtime.slot_id=slot.identity;target=slot.target;start_tick=slot.start_tick})environment.slots}
    ~limits:{Runtime.max_work=20_000_000;max_events=200000;max_attempts=32;max_microsteps=30},T.create bound
let select source reset=
  let rec scan count sequence=
    require(count<100)"Quantitative literal selection exceeded its independent search bound";
    match sequence()with
    |Seq.Nil->failwith "Original finite domain lacks the handwritten quantitative witness"
    |Seq.Cons(value,rest)->
      if List.for_all(fun(_,action)->action=(if reset && value.F.tick=7 then F.Reset else F.Keep))value.lifecycle
      then value else scan(count+1)rest in
  scan 0(S.choices source)
let expected_state reset tick=
  List.nth (if reset then
    ["q101";"q011";"q011";"q101";"q011";"q011";"q011";"q110";"q101";"q011";"q011";"q101";"q101"]
    else ["q101";"q011";"q011";"q101";"q011";"q011";"q011";"q101";"q011";"q011";"q011";"q101";"q101"]) tick
let selected_trace bound reset=
  let source,runtime,correspondence=initialize bound in
  let created=ref 0 in
  let rec loop source runtime correspondence=
    if S.finished source then correspondence else
    let batch=select source reset in
    let runtime,frame=Runtime.step runtime(T.input correspondence batch)in
    let advanced=match S.step source batch with S.Advanced value->value
      |S.Stopped stopped->failwith("Quantitative literal source stopped: "^stopped.diagnostic.code)in
    let matched=T.advance correspondence ~batch ~source_frame:advanced.frame
      ~source_attempts:(rows "attempts"(Option.get advanced.receipt.execution))
      ~source_creations:advanced.creations ~candidate:frame in
    let expected=expected_state reset frame.tick in
    List.iter(fun slot->
      let machine=List.find(fun(value:Runtime.machine_snapshot)->value.binding.slot=Some slot)frame.machines in
      require(machine.state=expected && machine.binding.generation=(if reset && frame.tick>=7 then 1 else 0))
        ("Literal reserved network candidate state/generation differs at "^string_of_int frame.tick);
      List.iteri(fun coordinate (state:B.state)->
        let port=List.find(fun(value:Runtime.port_value)->value.endpoint.node_id=state.register &&
          value.endpoint.port_id="value" && value.binding.slot=Some slot)frame.outputs in
        let wanted=if expected.[coordinate+1]='1' then I.True else I.False in
        require((match port.signal with Runtime.Truth signal->signal.value=Some wanted|_->false))
          "Separate selected reservoir register differs from its atomic machine coordinate") (B.states bound);
      let source_machine=List.find(fun row->at["binding";"encounter"]row=s slot)(rows "machines" advanced.frame)in
      require(get "state" source_machine=s expected)
        "Literal quantitative source state differs from the independent amount trajectory")["e1";"e2"];
    let new_requests=if frame.tick=1 || frame.tick=4 || frame.tick=(if reset then 9 else 8) then 2 else 0 in
    require(List.length frame.creations=new_requests && List.length advanced.creations=new_requests)
      "Threshold crossing created missing or extra abstract effect attempts";
    created:= !created+List.length frame.creations;
    let expected_initiator="forward5"in
    List.iter(fun(attempt:Runtime.attempt)->
      let transition=List.find(fun(value:B.transition)->value.gate=attempt.gate)(B.transitions bound)in
      require(transition.source=expected_initiator)
        "Shared effect bank lost the actual initiating transition identity")frame.creations;
    if frame.tick=2 || (reset && frame.tick=10) then (
      require(frame.creations=[] && List.length(List.filter(fun(value:Runtime.attempt)->
        value.status=Runtime.Active && value.authorization=I.Unknown)frame.attempts)=2)
        "Unknown sample cancelled old active attempts or created a new request";
      require(List.length(List.filter(fun(event:Runtime.event)->event.kind=Runtime.Primitive_event I.Updated)frame.events)=2)
        "Unknown sample lost its update event");
    if frame.tick=6 then require(not(List.exists(fun(event:Runtime.event)->
      event.kind=Runtime.Primitive_event I.Updated)frame.events) && frame.creations=[])
        "No-update interval produced a quantitative sample step";
    loop advanced.next runtime matched in
  let matched=loop source runtime correspondence in
  require(!created=6 && text "claim"(T.report matched)="matched_prefix_only")
    "Selected quantitative trace changed request count or broadened its prefix scope"

let structural_lowering_controls original=
  let library=R.implementation_library(M.implementation_request original)in
  let raw=R.to_json(M.implementation_request original)in
  let prepare ?(charge=Bioc_checker.Policy_generation_meter.no_charge) raw=
    let request=R.of_coupled_json raw in
    let source=Bioc_checker.Policy_admission.admit ~document:(R.document request)~descriptors:(R.definitions request)in
    let behavior=Bioc_compiler.Policy_lowering.lower source in
    RA.admit_metered ~charge ~request ~behavior in
  (* Measure this lowering phase, including model-authorization callbacks into
     its fresh admission, separately from independent source preparation. *)
  let work=ref 0 and measuring=ref false in
  let charge amount=if !measuring then (
    require(amount>=0 && amount<=100_000_000- !work)
      "Coupled lowering repeated whole expression subtrees under its fixture work bound";
    work:= !work+amount)in
  let admitted=prepare ~charge raw in
  (* The invocation-local correspondence result cannot be replaced by a saved
     report. Its legacy report adapter retains exactly the same fresh checks,
     charges and bytes; a changed ledger or denied first charge still fails. *)
  let document=R.document(RA.request admitted) and descriptors=R.definitions(RA.request admitted)
  and behavior=RA.behavior admitted in
  let scoped_work=ref 0 and duplicate_work=ref 0 and escaped=ref None in
  let scoped=Source_check.with_assessment ~charge:(fun amount->scoped_work:= !scoped_work+amount)
    ~document(fun checked->
      escaped:=Some checked;
      Admission.admit_assessed ~source:checked ~descriptors)in
  (* Reproduce the former planner's source-check then operational-admission
     sequence independently, using the same immutable original and descriptors. *)
  let prior=Source_check.check ~charge:(fun amount->duplicate_work:= !duplicate_work+amount)document in
  let legacy=Admission.admit_metered ~charge:(fun amount->duplicate_work:= !duplicate_work+amount)
    ~document ~descriptors in
  require(Json.equal prior(Admission.source_assessment scoped) &&
    Json.equal(Admission.report scoped)(Admission.report legacy) &&
    Json.equal(Bioc_domain.Policy_document.to_json(Admission.document scoped))
      (Bioc_domain.Policy_document.to_json(Admission.document legacy)) &&
    !duplicate_work- !scoped_work>=7_000_000)
    "Scoped source admission changed complete source authority or report bytes";
  Printf.printf "coupled source checking work: previous %d; scoped %d\n%!" !duplicate_work !scoped_work;
  let reject_scope action=match action()with
    |_->failwith "An escaped source assessment survived its original invocation"
    |exception Diagnostic.Error diagnostic->require(diagnostic.code="policy_source_assessment_scope")
       "Escaped source assessment changed its scope diagnostic"in
  let checked=Option.get !escaped in
  reject_scope(fun()->Source_check.assessed_report checked);
  reject_scope(fun()->Admission.admit_assessed ~source:checked ~descriptors);
  (match Source_check.with_assessment ~charge:(fun _->()) ~document(fun checked->
    escaped:=Some checked;
    let altered=O.descriptors_of_json(edit["definitions"](fun values->a(List.tl(Json.array values)))
      (O.descriptors_to_json descriptors))in
    (match Admission.admit_assessed ~source:checked ~descriptors:altered with
     |_->failwith "Scoped source validity admitted a missing original descriptor"
     |exception Diagnostic.Error diagnostic->require(diagnostic.code="policy_operational_unsupported")
        "Changed descriptors escaped the original operational guards");
    Diagnostic.fail "source_scope_test_exit" "Exceptional callback exit.")with
   |_->failwith "Scoped source test lost its explicit exceptional exit"
   |exception Diagnostic.Error diagnostic->require(diagnostic.code="source_scope_test_exit")
      "Scoped source test changed the callback failure");
  reject_scope(fun()->Source_check.charge_assessed(Option.get !escaped)1);
  let fresh_work=ref 0 and legacy_work=ref 0 in
  let fresh=Correspondence.check_fresh ~charge:(fun amount->fresh_work:= !fresh_work+amount)
    ~expected_document:document ~descriptors behavior in
  let legacy=Correspondence.check ~charge:(fun amount->legacy_work:= !legacy_work+amount)
    ~expected_document:document ~descriptors behavior in
  require(!fresh_work= !legacy_work && Json.equal(Correspondence.report fresh)legacy &&
    Json.equal(Correspondence.source_assessment fresh)(get "source_assessment" legacy))
    "Fresh correspondence reuse changed independent checking, work or report bytes";
  let changed_ledger=O.behavior_of_json(set "source_ledger"(a[])(O.behavior_to_json behavior))in
  (match Correspondence.check_fresh ~expected_document:document ~descriptors changed_ledger with
   |_->failwith "Fresh correspondence reused source validity for a changed behavior ledger"
   |exception Diagnostic.Error diagnostic->require(diagnostic.code="policy_correspondence")
      "Fresh correspondence ledger control failed before independent comparison");
  (match Correspondence.check_fresh
    ~charge:(fun _->Diagnostic.fail "correspondence_test_budget" "No fresh checking work remains.")
    ~expected_document:document ~descriptors behavior with
   |_->failwith "Fresh correspondence bypassed its parent work callback"
   |exception Diagnostic.Error diagnostic->require(diagnostic.code="correspondence_test_budget")
      "Fresh correspondence changed the original parent work failure");
  measuring:=true;
  let lowered=Lower.lower_metered ~charge ~admitted ~library in
  measuring:=false;
  let bind admitted (value:Lower.proposal)=ignore(B.check ~admitted
    ~implementation:value.implementation ~proposed:value.binding)in
  bind admitted lowered;
  let graph=I.to_json lowered.implementation in
  let source implementation node port=
    (List.find(fun(wire:I.wire)->wire.consumer.node_id=node && wire.consumer.port_id=port)
      (I.wires implementation)).producer in
  let original_roots=List.init 3(fun ordinal->source lowered.implementation "transition/0/commit"("value"^string_of_int ordinal))in
  List.iteri(fun ordinal root->for transition=1 to 6 do
    require(source lowered.implementation ("transition/"^string_of_int transition^"/commit")
      ("value"^string_of_int ordinal)=root)"Identical original expressions lost sharing across atomic writers"
  done)original_roots;
  (* Read every source occurrence independently of the producer's memo table.
     Repeated expression identity never erases a source path from the ledger. *)
  let declarations=rows "declarations"(at["document";"program"]raw)in
  let paths=ref []in
  let rec visit path value=
    paths:=path:: !paths;
    List.iteri(fun index child->visit(path^"/args/"^string_of_int index)child)(rows "args" value)in
  List.iteri(fun index declaration->let path="/document/program/declarations/"^string_of_int index in
    if text "$type" declaration="Transition"then(
      visit(path^"/on")(get "on" declaration);visit(path^"/when")(get "when" declaration);
      List.iteri(fun ordinal assignment->visit(path^"/assignments/"^string_of_int ordinal^"/value")(get "value" assignment))
        (rows "assignments" declaration))
    else if text "$type" declaration="Effect"then
      visit(path^"/parameters/0/value")(get "value"(List.hd(rows "parameters" declaration))))declarations;
  require(List.length !paths=977 && List.for_all(fun path->
    List.length(List.filter(fun row->text "source_path" row=path)(rows "occurrences" graph))=1)!paths)
    "Structural expression keys dropped or duplicated original occurrence paths";
  let lower raw=
    let admitted=prepare raw in
    let result=Lower.lower ~admitted ~library in bind admitted result;result in
  let rec reorder=function
    |Json.Object fields->o(List.rev_map(fun(key,value)->key,reorder value)fields)
    |Json.Array values->a(List.map reorder values)|value->value in
  let reordered=lower(reorder raw)in
  require(Canonical.encode(I.to_json reordered.implementation)=Canonical.encode graph &&
    Canonical.encode(Binding.to_json reordered.binding)=Canonical.encode(Binding.to_json lowered.binding))
    "Expression interning made complete output bytes depend on JSON field order";
  (* These nearby expressions keep valid source typing and available models,
     but change child order, child identity/multiplicity, and arity. Each must
     retain a distinct root while unchanged later writers keep their sharing. *)
  let changed=edit["document";"program";"declarations"](fun values->a(List.map(fun declaration->
    if text "id" declaration<>"reverse1"then declaration else
    edit["assignments"](fun assignments->a(List.mapi(fun ordinal assignment->
      edit["value";"args"](fun children->match ordinal,Json.array children with
        |0,[x;y;z]->a[y;x;z]
        |1,[x;_]->a[x;x]
        |2,[x;y;_]->a[x;y]
        |_->failwith "Structural-key adversaries no longer match the independent source shape")assignment)
      (Json.array assignments)))declaration)(Json.array values)))raw in
  let changed=lower changed in
  require(List.length(I.nodes lowered.implementation)=49 && List.length(I.nodes changed.implementation)=52)
    "Different complete expression keys were merged or changed unrelated nodes";
  List.iteri(fun ordinal _->
    let root=source changed.implementation "transition/0/commit"("value"^string_of_int ordinal)
    and original=source changed.implementation "transition/1/commit"("value"^string_of_int ordinal)in
    require(root<>original)"Near-matching expression incorrectly reused an original output";
    let input (endpoint:I.endpoint) port=source changed.implementation endpoint.node_id port in
    (match ordinal with
    |0->require(input root "in0"=input original "in1" && input root "in1"=input original "in0" &&
      input root "in2"=input original "in2")"Ordered child identities were normalized away"
    |1->require(input root "in0"=input original "in0" && input root "in1"=input original "in0" &&
      input original "in0"<>input original "in1")"Repeated child identity was confused with a different operand"
    |_->let node=List.find(fun(node:I.node)->node.node_id=root.node_id)(I.nodes changed.implementation)in
      require(node.model.primitive=I.Truth_any 2 && input root "in0"=input original "in0" &&
        input root "in1"=input original "in1")"Expression configuration or original operands were dropped"))original_roots;
  Printf.printf "coupled model lowering work: %d\n%!" !work


let ()=
  require(Array.length Sys.argv=3)"Expected coupled and unchanged single-owner network fixtures";
  let fixture=read Sys.argv.(1) and previous=read Sys.argv.(2)in
  wire_controls previous;
  let previous_request=M.of_json(get "request" previous)in
  require(M.is_transfer_network previous_request && not(M.is_quantitative_composition previous_request))
    "Coupled profile changed the existing exact single-owner network route";
  require(text "schema_version" fixture="biocompiler.policy_quantitative_composition_literals.v0.1" &&
    Json.equal(at["expected";"table"]fixture)expected_table)
    "Coupled fixture changed its independent full-grid allocation oracle";
  let request=get "request" fixture and limits=get "limits" fixture in
  let original=M.of_json request in
  require(M.is_quantitative_composition original && M.is_multi_site original &&
    R.is_coupled(M.implementation_request original) && Option.is_some(M.network_quantitative original))
    "Partitioned composition lost its explicit source and selected-network authority";
  structural_lowering_controls original;
  let realization=get "implementation_request" request in
  let plan_request=o["schema_version",s "biocompiler.policy_target_plan_request.v0.1";
    "target",s "coupled_quantitative_material";"document",get "document" realization;
    "definitions",get "definitions" realization;"realization_request",realization;"material_request",request;
    "limits",o["max_work",Json.int 100000000;"max_report_bytes",Json.int 2097152;"max_report_nodes",Json.int 100000]]in
  let planned=call Producer.handle Protocol.Core "plan-policy-target"(o["request",plan_request])in
  require(at["report";"status"]planned=s "planned" && List.length(rows "selected_components"(get "report" planned))=4 &&
    at["report";"claims";"execution"]planned=s "not_performed" && at["report";"claims";"export"]planned=s "withheld")
    "Coupled planning omitted selected owners or promoted diagnostic planning into acceptance";
  require(at["report";"material_request_fingerprint"]planned=
    s "6d09390250496a62a92ce75a46c05f4578d5614650102e03d461c8eb20839acf" &&
    at["report";"material_request_fingerprint"]planned=s(Canonical.fingerprint request) &&
    at["report";"realization_request_fingerprint"]planned=
      s "69c81b3e33e4237c24bf535dd02d30cbc82d6f3b2b6dd8c23f8d6315c7c0a6c8" &&
    at["report";"realization_request_fingerprint"]planned=s(Canonical.fingerprint realization) &&
    at["report";"document_fingerprint"]planned=
      s "3e34345f6542091ab38f494b1567d487beec7d3fdc22f65003a2d67642b53048" &&
    at["report";"document_fingerprint"]planned=s(Canonical.fingerprint(get "document" realization)))
    "Coupled planning reused an identity other than the complete original material body";
  let publication_request:Protocol.request={request_id="coupled-plan-publication-limit";
    operation="plan-policy-target";payload=o["request",edit["limits";"max_report_nodes"](fun _->Json.int 1)plan_request]}in
  let publication_failure(diagnostic:Diagnostic.t)=
    require(diagnostic.code="policy_target_plan_publication_limit" &&
      List.mem " operation: report_publication"(String.split_on_char ';' diagnostic.message))
      "Final report publication failure lost its exact resource code or phase context"in
  (match Producer.handle Protocol.Core publication_request with
   |Protocol.Error,None,diagnostic::_->publication_failure diagnostic
   |exception Diagnostic.Error diagnostic->publication_failure diagnostic
   |_->failwith "A coupled plan published beyond its original report inventory allowance");
  let changed_request=edit["budgets";"max_work"](fun _->Json.int 499999999)request in
  let changed_plan=call Producer.handle Protocol.Core "plan-policy-target"
    (o["request",set "material_request" changed_request plan_request])in
  require(at["report";"status"]changed_plan=s "planned" &&
    at["report";"material_request_fingerprint"]changed_plan=
      s "63b9d1e492cb4ae9affa9e5cc6a953f758415881d855ffdf4defdb202f42d60d" &&
    at["report";"material_request_fingerprint"]changed_plan=s(Canonical.fingerprint changed_request) &&
    at["report";"material_request_fingerprint"]changed_plan<>
      at["report";"material_request_fingerprint"]planned)
    "Coupled planning retained a prior invocation's material identity after an original-body change";
  let produced=call Producer.handle Protocol.Core "compile-policy-component-material"(o["request",request;"limits",limits])in
  let candidate=get "candidate" produced in
  let _,result=Material.fresh_check ~request ~candidate ~limits in
  let checked=accepted "Complete partitioned quantitative material"(Check.accepted result)in
  let report=Check.report result and contextual=Check.context checked in
  let unchanged=Canonical.encode(Check.evidence checked)in
  let refinement=Refinement.of_material checked in
  let repeated_refinement=Refinement.of_material checked in
  require(Canonical.encode(Refinement.to_json refinement)=Canonical.encode(Refinement.to_json repeated_refinement) &&
    Refinement.fingerprint refinement=Canonical.fingerprint(Refinement.to_json refinement) &&
    List.length(Refinement.premises refinement)=18)
    "Fresh coupled refinement changed complete evidence or original premise identities";
  let endpoint stage=List.find_map(fun(row:Named.claim)->
    if row.source.stage=stage then Some row.source.fingerprint else
    if row.target.stage=stage then Some row.target.fingerprint else None)(Refinement.claims refinement)in
  List.iter(fun(stage,raw)->require(endpoint stage=Some(Canonical.fingerprint raw))
    "Coupled refinement lost a complete original endpoint")
    [Named.Source_document,at["implementation_request";"document"]request;
      Named.Operational_behavior,get "behavior" candidate;Named.Implementation_graph,get "implementation" candidate;
      Named.Construction_content,get "construction" candidate;Named.Deployment_context,get "context" request];
  (match Refinement.of_material ~maximum:0 checked with
  |_->failwith "A new refinement invocation reused a prior invocation's paid identity"
  |exception Diagnostic.Error error->require(error.code="policy_refinement_resource_limit")
      "Fresh refinement zero-work rejection changed");
  let mechanism=at["quantitative";"network";"mechanism"]request in
  let coordinates=a(List.map(get "compartment")(rows "reservoirs" mechanism))in
  let approximate_endpoint=o["mechanism",mechanism;"observation",coordinates]in
  let zero=o["numerator",s "0";"denominator",s "1";"unit",get "unit" mechanism]in
  let horizon=Z.to_int(Json.integer(at["implementation_request";"operating_domain";"horizon_ticks"]request))+1 in
  let approximate_raw=o["schema_version",s Approximation_contract.schema_version;
    "profile",s Approximation_contract.profile;"horizon_steps",Json.int horizon;
    "metric",s "coordinatewise_absolute_prefix_error";"coordinates",coordinates;
    "unit",get "unit" mechanism;"maximum_error",zero;
    "links",a[o["id",s "coupled_identity";"source",approximate_endpoint;"target",approximate_endpoint;
      "uncertainty",a[];"maximum_error",zero]]]in
  let approximate_contract=Approximation_contract.of_json approximate_raw in
  let approximation=Approximation.check ~material:checked ~contract:approximate_contract ()in
  let repeated_approximation=Approximation.check ~material:checked ~contract:approximate_contract ()in
  let approximate_report=Approximation.report approximation in
  require(Option.is_some(Approximation.accepted approximation) &&
    Canonical.encode approximate_report=Canonical.encode(Approximation.report repeated_approximation) &&
    get "material_request_fingerprint" approximate_report=s(Canonical.fingerprint request) &&
    get "material_report_fingerprint" approximate_report=s(Canonical.fingerprint report) &&
    at["composition";"material_request_fingerprint"]approximate_report=get "material_request_fingerprint" approximate_report &&
    at["composition";"material_report_fingerprint"]approximate_report=get "material_report_fingerprint" approximate_report)
    "Coupled approximation lost fresh complete material identities";
  (match Approximation.check ~maximum:0 ~material:checked ~contract:approximate_contract ()with
  |_->failwith "A new approximation invocation reused a prior invocation's paid identity"
  |exception Diagnostic.Error error->require(error.code="policy_approximation_resource_limit")
      "Fresh approximation zero-work rejection changed");
  let short_contract=Approximation_contract.of_json(set "horizon_steps"(Json.int(horizon-1))approximate_raw)in
  let short=Approximation.check ~material:checked ~contract:short_contract ()in
  require(Approximation.accepted short=None && Approximation.outcome short=Outcome.Fail &&
    get "composition"(Approximation.report short)=Json.Null &&
    Canonical.encode(Check.evidence checked)=unchanged)
    "Fresh approximation reused semantic acceptance or altered its material evidence";
  let context_report=C.evidence contextual in
  let truth_demands=List.filter(fun row->text "unit" row="truth_cells")(rows "derived_demands" context_report)in
  let expected_truth_demands=List.map(fun slot->o["owner",o["kind",s "node";"slot",s slot;"node",s "amount"];
    "unit",s "truth_cells";"scope",s "per_encounter_slot";"quantity",Json.int 1])["owner_a";"owner_b";"owner_c"]in
  require(text "implementation_version" context_report="biocompiler.ocaml.policy_component_context_check.v0.10" &&
    Json.equal(a truth_demands)(a expected_truth_demands) &&
    at["minimum_record_layout";"ordered_reason_slots"]context_report=Json.int 9)
    "Coupled context omitted the three distinct private truth-storage owners";
  let aliased_truth=edit["resource_bindings"](fun values->a(List.map(fun row->
    if text "unit" row="truth_cells" && at["owner";"slot"]row=s "owner_b"then
      set "capacity"(s "owner_a.amount.truth_cells.per_encounter_slot")row else row)(Json.array values)))request in
  let exhausted_truth=C.check ~request:(M.of_json aliased_truth) ~assembly:(C.assembly contextual)()in
  require(C.accepted exhausted_truth=None && C.outcome exhausted_truth=Outcome.Fail &&
    get "diagnostics"(C.report exhausted_truth)=a[s "shared_capacity_sum_exceeded"])
    "Two private truth stores incorrectly shared one unit of original capacity";
  let narrow_reasons=request|>edit["context";"record_layout";"ordered_reason_slots"](fun _->Json.int 8)
    |>refresh_context in
  let exhausted_reasons=C.check ~request:(M.of_json narrow_reasons) ~assembly:(C.assembly contextual)()in
  require(C.accepted exhausted_reasons=None && C.outcome exhausted_reasons=Outcome.Fail &&
    get "diagnostics"(C.report exhausted_reasons)=a[s "finite_record_bound:ordered_reason_slots"])
    "Coupled context admitted fewer reason slots than the original actual graph requires";
  let preservation=A.implementation(C.assembly contextual)in
  let bound=P.binding preservation in
  let monitor_limits=get "monitor" limits in
  let int key=Z.to_int(Json.integer(get key monitor_limits))in
  let monitor=Monitor.create ~binding:bound ~limits:{Monitor.max_work=int "max_work";
    max_obligations=int "max_obligations";max_samples=int "max_samples"}in
  Printf.printf "coupled monitor initialization work: %d; binding bytes: %d\n%!"
    (Monitor.usage monitor).work(String.length(Canonical.encode(B.report bound)));
  (* Repeated identical configurations retain every distinct candidate node;
     different register configurations remain separate. Independently bind
     the complete result of repeated deterministic arrangement. *)
  let library=R.implementation_library(M.implementation_request original)in
  let input_pairs=List.map(fun(value:M.input_binding)->value.source,value.input_id)(M.input_bindings original)in
  let binding=Binding.of_json(get "binding" candidate)in
  let rearrange implementation=Arrange.arrange ~source_inputs:input_pairs ~library
    ~rule:(M.composition_rule original)({Lower.implementation;binding}:Lower.proposal)in
  let supplied=I.of_json ~library(get "implementation" candidate)in
  require(List.length(List.filter(fun(value:I.node)->match value.model.primitive with
    I.Truth_register{initial=I.True;_}->true|_->false)(I.nodes supplied))=2 &&
    List.length(List.filter(fun(value:I.node)->match value.model.primitive with
    I.Truth_register{initial=I.False;_}->true|_->false)(I.nodes supplied))=1)
    "Arrangement witness omitted repeated or distinct full configurations";
  let first=rearrange supplied and second=rearrange supplied in
  require(Json.equal(I.to_json first.implementation)(I.to_json second.implementation) &&
    Json.equal(Binding.to_json first.binding)(Binding.to_json second.binding) &&
    Json.equal(U.to_json first.assembly)(U.to_json second.assembly))
    "Exact-signature indexing changed deterministic complete arrangement";
  ignore(B.check ~admitted:(B.admitted_inputs bound) ~implementation:first.implementation ~proposed:first.binding);
  let raw_library=I.library_to_json library in
  let old_model=List.find(fun row->text "primitive"(get "body" row)="evidence_bank")(rows "models" raw_library)in
  let body=edit["configuration";"freshness_ticks"](fun _->Json.int 2)(get "body" old_model)in
  let changed_model=old_model|>set "body" body
    |>set "configuration_digest"(s(Canonical.fingerprint(get "configuration" body)))
    |>edit["identity";"content_fingerprint"](fun _->s(Canonical.fingerprint body))in
  let changed_library=I.library_of_json(edit["models"](fun values->a(List.map(fun row->
    if Json.equal row old_model then changed_model else row)(Json.array values)))raw_library)in
  let changed=I.of_json ~library:changed_library(get "implementation" candidate
    |>edit["authority";"library_digest"](fun _->s(I.library_digest changed_library))
    |>edit["nodes"](fun values->a(List.map(fun row->
      if Json.equal(get "model" row)(get "identity" old_model)then row
        |>set "model"(get "identity" changed_model)
        |>set "configuration_digest"(get "configuration_digest" changed_model)else row)(Json.array values))))in
  (match Arrange.arrange ~source_inputs:input_pairs ~library:changed_library
    ~rule:(M.composition_rule original)({Lower.implementation=changed;binding}:Lower.proposal)with
  |_->failwith "Arrangement accepted a repinned same-primitive configuration mismatch"
  |exception Diagnostic.Error d->
    require(d.code="policy_component_lowering_unsupported")"Signature mismatch did not fail closed before search exhaustion";
    incr controls);
  let quantitative=Quant.check ~request:original ~context:contextual ()in
  let composition=Composition.check ~request:original ~context:contextual ()in
  let summary=Quant.report quantitative in
  require(Option.is_some(Quant.accepted quantitative) && Option.is_some(Composition.accepted composition) &&
    Json.equal summary(Composition.report composition) && Json.equal summary(get "quantitative" report) &&
    Json.equal(get "table" summary)expected_table && Json.equal(get "conservation" summary)conservation &&
    get "schema_version" summary=s "biocompiler.policy_quantitative_assessment.v0.5" &&
    get "claim_scope" summary=s "exact_atomic_component_transfer_network_under_supplied_coordination_contract" &&
    get "synchronization" summary=s "one_prestate_one_atomic_commit" &&
    get "ownership" summary=s "partitioned_reservoir_storage_single_atomic_writer" &&
    get "transport_scope" summary=s "selected_boolean_allocation_signals_under_supplied_component_contracts" &&
    get "empirical" summary=s "unassessed" &&
    get "schema_version" report=s "biocompiler.policy_component_material_assessment.v0.9")
    "Fresh composition evidence changed its actual signal checks or conditional scope";
  let bindings=get "bindings" summary in
  require(List.map(text "compartment")(rows "owners" bindings)=["a";"b";"c"] &&
    List.map(text "source_state")(rows "owners" bindings)=["amount_a";"amount_b";"amount_c"] &&
    List.map(text "transfer")(rows "transfers" bindings)=edge_ids &&
    List.map(text "source_state")(rows "crossing_sites" bindings)=["q100";"q101"] &&
    List.length(B.states bound)=3 && List.length(B.transitions bound)=7 &&
    List.length(I.nodes(B.implementation bound))=49)
    "Selected distinct private owners or complete counterfactual crossing/flow census changed";
  selected_trace bound false;selected_trace bound true;
  let selected=get "quantitative" request in
  rejects "undeclared coordination premise"(fun()->Composition_contract.selection_of_json
    (set "synchronization"(s "eventual_commit")selected));
  rejects "owner coordinate permutation"(fun()->Composition_contract.selection_of_json
    (edit["owners"](fun values->a(List.rev(Json.array values)))selected));
  rejects "missing private owner"(fun()->Composition_contract.selection_of_json
    (edit["owners"](fun values->a(List.tl(Json.array values)))selected));
  rejects "aliased private store"(fun()->Composition_contract.selection_of_json
    (edit["owners"](fun values->a(List.map(fun row->set "state"(s "amount_a")row)(Json.array values)))selected));
  rejects "aliased component instance"(fun()->Composition_contract.selection_of_json
    (edit["owners"](fun values->a(List.map(fun row->set "instance"(s "control")row)(Json.array values)))selected));
  rejects "nonbinary selected reservoir"(fun()->Composition_contract.selection_of_json
    (edit["network";"mechanism";"reservoirs"](fun values->a(List.mapi(fun index row->
      if index=0 then edit["capacity";"amount"](fun _->s "2")row else row)(Json.array values)))selected));
  rejects "legacy realization route cannot own state"(fun()->
    let legacy=R.of_multi_site_json(get "implementation_request" request|>set "schema_version"(s R.multi_site_schema_version)|>set "profile"(s R.multi_site_profile))in
    RA.admit ~request:legacy ~behavior:(O.behavior_of_json(get "behavior" candidate)));
  rejects "single-owner material route cannot consume partitioned components"(fun()->M.of_json
    (request|>set "schema_version"(s M.transfer_network_schema_version)|>set "profile"(s M.transfer_network_profile)));
  rejects "zero composition checking work"(fun()->Composition.check ~maximum:0 ~request:original ~context:contextual ());
  let components=rows "components"(get "component_library" request)in
  let component instance=List.find(fun value->text "id"(get "identity" value)="coupled."^instance)components in
  let owner_local=List.hd(rows "quantitative_contracts"(get "body"(component "owner_a")))in
  rejects "empty atomic writer inventory"(fun()->Composition_contract.local_of_json(set "writes"(a[])owner_local));
  rejects "duplicate owner incident flow"(fun()->Composition_contract.local_of_json(edit["flows"]
    (fun values->let first=List.hd(Json.array values)in a[first;first])owner_local));
  let localchange label instance change=
    quantitative_failure preservation label(change_contract request instance change)candidate in
  localchange "owner next signal falsely claims the snapshot model" "owner_a"
    (edit["next";"model"](fun _->at["state";"model"]owner_local));
  localchange "owner next endpoint is old snapshot" "owner_a"(fun contract->contract
    |>edit["next";"boundary"](fun _->get "snapshot_boundary" contract)
    |>edit["next";"model"](fun _->at["state";"model"]contract));
  localchange "omitted source atomic writer" "owner_a"(edit["writes"](fun values->a(List.tl(Json.array values))));
  localchange "permuted source write lanes" "owner_b"(edit["writes"](fun values->a(List.rev(Json.array values))));
  localchange "omitted explicit edge incidence" "owner_c"(edit["flows"](fun values->a(List.tl(Json.array values))));
  localchange "permuted explicit edge incidence" "owner_a"(edit["flows"](fun values->a(List.rev(Json.array values))));
  localchange "selected initial register model mismatched" "owner_a"
    (edit["state";"model"](fun _->at["next";"model"]owner_local));
  localchange "unreachable crossing omitted" "control"(edit["network";"outputs"]
    (fun values->a(List.filter(fun row->text "source_state" row<>"q100")(Json.array values))));
  localchange "false crossing polarity" "control"(edit["network";"outputs"]
    (fun values->a(List.map(fun row->set "input"(Json.Bool false)row)(Json.array values))));
  localchange "same-node-kind actual edge ports swapped" "control"(edit["flows"](fun values->match Json.array values with
    |first::second::rest->a(set "boundary"(get "boundary" second)first::set "boundary"(get "boundary" first)second::rest)
    |_->failwith "Missing flow pair"));
  let reverse=edit["transfers"](fun values->a(List.rev(Json.array values)))in
  let wrong_law=edit["quantitative";"network";"mechanism"]reverse request in
  quantitative_failure preservation "different original reserved network" wrong_law candidate;
  let invocation=o["request",request;"candidate",candidate;"limits",limits]in
  let verified=call Service.handle Protocol.Verify "check-policy-component-material" invocation in
  require(Json.equal(get "report" verified)report)"Fresh independent material service changed coupled evidence";
  let replayed=call Service.handle Protocol.Verify "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",limits;"report",produced])in
  require(Json.equal replayed produced)"Fresh composition replay changed complete wrapper";
  let exported=call Service.handle Protocol.Verify "export-policy-component-material" invocation in
  let artifact=get "artifact" exported in
  require(get "fasta" artifact=s(">rna_0001 alphabet=RNA\n"^text "sequence"(get "expected" fixture)^"\n"))
    "Four selected component roots lost exact payload sequence construction";
  let manifest=get "manifest" artifact in
  require(Json.equal(get "request" manifest)request && Json.equal(get "candidate" manifest)candidate &&
    Json.equal(get "assessment" manifest)report && get "manifest_sha256" artifact=s(Canonical.sha256(Canonical.encode manifest)))
    "Export omitted original owners, coupling, components or fresh assessment";
  let named=call Service.handle Protocol.Verify "check-policy-refinement" invocation in
  require(Json.equal(at["material_report";"quantitative"]named)summary)
    "Named refinement erased selected composition evidence";
  rejected_service "saved PASS cannot bypass checking work" "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",edit["max_step_work"](fun _->Json.int 1)limits;"report",produced]);
  let saved=edit["report";"quantitative";"bindings";"owners"](fun values->a(List.rev(Json.array values)))produced in
  rejected_service "saved owner provenance permutation" "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",limits;"report",saved]);
  let saved=edit["report";"quantitative";"synchronization"](fun _->s "physical_distributed_guarantee")produced in
  rejected_service "saved report broadens atomic coordination premise" "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",limits;"report",saved]);
  require(!controls=26)"Coupled quantitative rejection census is incomplete";
  Printf.printf "policy_quantitative_composition: independent 24-row actual-circuit law, three private material owners, atomic reset/state invariant, four-root exact RNA, %d rejection controls\n" !controls

open Bioc_wire
open Bioc_domain
module C = Pipeline_contract
module W = Bioc_checker.Work_budget
module X = C.Codec
module PC = C.Pass_contract
module IC = C.Component_input_contract
module SR = C.Stage_record
module SO = C.Scoped_obligation
module CS = C.Check_spec
module CD = C.Check_decision
module PR = C.Pass_result
module SL = C.Source_link
module PO = C.Producer_obligation
module CP = C.Completion_profile
let implementation_version = "biocompiler.ocaml.pass_manager.v0.1"
let resource_profile = "biocompiler.pass_manager.resources.v1"
type limits = {max_records:int;max_providers:int;max_retained_items:int;max_retained_bytes:int;max_call_depth:int;
  max_ancestor_depth:int;max_document_bytes:int;max_document_nodes:int}
let make_limits ?(max_records=10_000) ?(max_providers=10_000) ?(max_retained_items=1_000_000)
    ?(max_retained_bytes=67_108_864) ?(max_call_depth=128) ?(max_ancestor_depth=128) ?(max_document_bytes=16_777_216)
    ?(max_document_nodes=250_000) () =
  List.iter (fun (value,maximum)->Diagnostic.require (value>0 && value<=maximum)
    "pipeline_limits" "Pipeline limits must be positive reductions of the native profile.")
    [max_records,10_000;max_providers,10_000;max_retained_items,1_000_000;max_retained_bytes,67_108_864;max_call_depth,128;
     max_ancestor_depth,128;max_document_bytes,16_777_216;max_document_nodes,250_000];
  {max_records;max_providers;max_retained_items;max_retained_bytes;max_call_depth;max_ancestor_depth;max_document_bytes;max_document_nodes}
let default_limits=make_limits ()
let str value=Json.String value
let obj values=Json.Object values
let limits_json x=obj ["profile",str resource_profile;"max_records",Json.int x.max_records;
  "max_providers",Json.int x.max_providers;"max_retained_items",Json.int x.max_retained_items;
  "max_retained_bytes",Json.int x.max_retained_bytes;
  "max_call_depth",Json.int x.max_call_depth;"max_ancestor_depth",Json.int x.max_ancestor_depth;
  "max_document_bytes",Json.int x.max_document_bytes;"max_document_nodes",Json.int x.max_document_nodes;
  "work",str "one_caller_owned_lifetime_ancestor_including_reentrant_callbacks";
  "retention",str "conservative_cumulative_state_reservations_no_refund" ]
type callback_result=Proposal of PR.t | Decision of CD.t | Invalid_return of Json.t
type provider=W.t -> C.Pass_context.t -> callback_result
type validator_equivalent=W.t -> provider -> provider -> bool
type no_candidate={pass_id:string;configuration:Json.t;dependencies:(string*string) list;message:string}
exception No_candidate_found of no_candidate
type registration={contract:PC.t;producer:provider;validators:(string*provider) list}
type admission={admission_contract:IC.t;admission_validators:(string*provider) list}
type t={budget:W.t;limits:limits;validator_equivalent:validator_equivalent;
  target_value:Build_request.Target.t;target_identity:string;
  mutable dependencies:(string*string) list;mutable passes:(string*registration) list;
  mutable admissions:(string*admission) list;mutable provider_history:(string*registration) list;
  mutable admission_history:(string*admission) list;mutable providers:provider list;
  mutable records:(string*SR.t) list;mutable profiles:(string*CP.t) list;
  mutable retained:int;mutable retained_bytes:int;mutable calls:int}
let fail message=Diagnostic.fail "pipeline_error" message
let require condition message=Diagnostic.require condition "pipeline_serialization" message
let charge t amount=W.charge t.budget amount
let codec t=X.make_limits ~max_bytes:t.limits.max_document_bytes ~max_nodes:t.limits.max_document_nodes
  ~charge:(charge t) ()
let measure t raw=X.measure ~limits:(codec t) raw
let fingerprint t raw=X.fingerprint ~limits:(codec t) raw
let text t value=charge t (String.length value+1);Json.validate_utf8 value
let name t label value=text t value;
  try ignore (Json.name (str value)) with Diagnostic.Error _->require false (label^" must be a nonempty string.")
let same_text t left right=charge t (String.length left+String.length right+1);left=right
let repr t value=text t value;Diagnostic_text.repr value
let retain t amount=
  Diagnostic.require (amount>=0 && amount<=t.limits.max_retained_items-t.retained)
    "pipeline_retention_limit" "Retained pipeline state exceeds its native inventory limit.";
  charge t amount;t.retained<-t.retained+amount
let retain_json t raw=
  let size=measure t raw in
  Diagnostic.require (size.bytes<=t.limits.max_retained_bytes-t.retained_bytes)
    "pipeline_retention_limit" "Retained pipeline state exceeds its native byte limit.";
  retain t size.nodes;t.retained_bytes<-t.retained_bytes+size.bytes
let bounded t values=
  let rec visit count=function []->() | _::rest->charge t 1;
    Diagnostic.require (count<t.limits.max_document_nodes) "pipeline_inventory_limit"
      "Pipeline collection exceeds its native inventory limit.";visit (count+1) rest in
  visit 0 values;values
let lookup t key values=
  let rec find=function []->None | (other,value)::rest->
    if same_text t key other then Some value else find rest in find (bounded t values)
let contains t key values=Option.is_some (lookup t key values)
let replace t key value values=
  let rec update prefix=function []->List.rev_append prefix [key,value] | (other,old)::rest->
    if same_text t key other then List.rev_append prefix ((other,value)::rest)
    else update ((other,old)::prefix) rest in update [] (bounded t values)
let member t key values=List.exists (same_text t key) (bounded t values)
let unique t values=
  let rec add seen=function []->List.rev seen | value::rest->
    if member t value seen then add seen rest else add (value::seen) rest in add [] (bounded t values)
let sorted t values=
  List.sort (fun a b->charge t (String.length a+String.length b+1);String.compare a b) (unique t values)
let subset t left right=List.for_all (fun key->member t key right) (bounded t left)
let names t label values=
  let values=bounded t values in List.iter (name t label) values;
  require (List.length (unique t values)=List.length values) (label^" must be unique.");values
let assoc_json values=obj (List.map (fun (key,value)->key,str value) values)
let field raw key=match raw with Json.Object fields->Option.value ~default:Json.Null (List.assoc_opt key fields) | _->Json.Null
let document t raw=
  ignore (measure t raw);
  require (match raw with Json.Object _->true|_->false) "A pipeline artifact must be an object.";
  (match field raw "schema_version" with Json.String value->name t "Artifact schema" value
   | _->require false "Artifact schema must be a nonempty string.");raw
let with_call t action=
  charge t 1;
  Diagnostic.require (t.calls<t.limits.max_call_depth) "pipeline_recursion_limit"
    "Pipeline callback reentrancy exceeds its native depth limit.";
  t.calls<-t.calls+1;Fun.protect action ~finally:(fun ()->t.calls<-t.calls-1)
let target t=with_call t (fun ()->t.target_value)
let register_completion_profile t profile=with_call t (fun ()->
  ignore (measure t (CP.to_json profile));let scope=CP.scope profile in
  if contains t scope t.profiles then fail ("Completion profile "^repr t scope^" is already registered.");
  retain_json t (CP.to_json profile);t.profiles<-replace t scope profile t.profiles)
let set_dependency t key identity=with_call t (fun ()->
  name t "Dependency name" key;name t "Dependency identity" identity;
  require (String.length identity=64 && String.for_all (function '0'..'9'|'a'..'f'->true|_->false) identity)
    "Dependencies require canonical SHA-256 identities.";
  if key="target" && not (same_text t identity t.target_identity) then
    fail "Target dependency must match the pipeline context; create a new manager.";
  retain_json t (obj [key,str identity]);t.dependencies<-replace t key identity t.dependencies)
let create ~budget ?(limits=default_limits) ?(validator_equivalent=(fun _ left right->left==right))
    ~target ~dependencies ?(completion_profiles=[]) ()=
  let input=X.make_limits ~max_bytes:limits.max_document_bytes ~max_nodes:limits.max_document_nodes
    ~charge:(W.charge budget) () in
  let target_identity=X.fingerprint ~limits:input (Build_request.Target.to_json target) in
  let t={budget;limits;validator_equivalent;target_value=target;target_identity;dependencies=[];passes=[];admissions=[];
    provider_history=[];admission_history=[];providers=[];records=[];profiles=[];retained=0;retained_bytes=0;calls=0} in
  retain_json t (Build_request.Target.to_json target);
  List.iter (register_completion_profile t) (bounded t completion_profiles);
  List.iter (fun (key,value)->set_dependency t key value) (bounded t dependencies);
  if not (contains t "request" t.dependencies) then fail "Missing authoritative request dependency.";
  set_dependency t "target" target_identity;t
let remember_provider t provider=
  if not (List.exists (fun previous->charge t 1;previous==provider) (bounded t t.providers)) then begin
    Diagnostic.require (List.length t.providers<t.limits.max_providers) "pipeline_provider_limit"
      "Registered pipeline providers exceed their native inventory limit.";
    retain t 1;t.providers<-t.providers@[provider]
  end
let provider_map t validators=
  let keys=List.map fst (bounded t validators) in
  List.iter (text t) keys;
  require (List.length (unique t keys)=List.length keys) "Invalid pass providers.";validators
let same_providers t left right=
  List.length left=List.length right && List.for_all (fun (key,provider)->
    match lookup t key right with None->false|Some other->
      charge t 1;provider==other || t.validator_equivalent t.budget provider other) (bounded t left)
let register t contract ~producer ~validators=with_call t (fun ()->
  ignore (measure t (PC.to_json contract));let id=PC.id contract in
  if contains t id t.admissions then fail "Pass ID collides with a component admission policy.";
  let validators=provider_map t validators in
  let expected=List.map CS.id (PC.checks contract) in
  if not (subset t expected (List.map fst validators) && subset t (List.map fst validators) expected) then
    fail "Every contracted check needs exactly one independent provider.";
  if List.exists (fun (_,validator)->charge t 1;validator==producer) validators then
    fail "Candidate generation cannot certify itself.";
  let identity=PC.fingerprint contract in text t identity;
  (match lookup t identity t.provider_history with
   | Some previous when previous.producer!=producer || not (same_providers t previous.validators validators)->
       fail "Changed pass/check providers must increment the contract version."
   | _->());
  retain_json t (PC.to_json contract);
  retain_json t (Json.Array(List.map (fun (key,_)->str key) validators));remember_provider t producer;
  List.iter (fun (_,provider)->remember_provider t provider) validators;
  let registration={contract;producer;validators} in
  t.passes<-replace t id registration t.passes;
  t.provider_history<-replace t identity registration t.provider_history)
let register_component_input t contract ~validators=with_call t (fun ()->
  ignore (measure t (IC.to_json contract));let validators=provider_map t validators in
  let id=IC.id contract in
  if contains t id t.passes then fail "Component admission ID collides with a pass.";
  let expected=List.map CS.id (IC.checks contract) in
  if not (subset t expected (List.map fst validators) && subset t (List.map fst validators) expected) then
    fail "Every admission check needs an independent provider.";
  let identity=IC.fingerprint contract in text t identity;
  (match lookup t identity t.admission_history with
   | Some previous when not (same_providers t previous.admission_validators validators)->
       fail "Changed admission providers must increment the contract version."
   | _->());
  retain_json t (IC.to_json contract);
  retain_json t (Json.Array(List.map (fun (key,_)->str key) validators));
  List.iter (fun (_,provider)->remember_provider t provider) validators;
  let admission={admission_contract=contract;admission_validators=validators} in
  t.admissions<-replace t id admission t.admissions;
  t.admission_history<-replace t identity admission t.admission_history)
let store_record t identity record=
  Diagnostic.require (contains t identity t.records || List.length t.records<t.limits.max_records)
    "pipeline_record_limit" "Pipeline stage records exceed their native inventory limit.";
  retain_json t (SR.to_json record);t.records<-replace t identity record t.records
let current_dependency t key=Option.value ~default:"" (lookup t key t.dependencies)
let rec get_in t visited identity=
  text t identity;charge t 1;
  Diagnostic.require (List.length visited<t.limits.max_ancestor_depth && not (member t identity visited))
    "pipeline_ancestry_limit" "Pipeline ancestry is cyclic or exceeds its native depth limit.";
  let record=match lookup t identity t.records with Some record->record
    | None->fail ("Missing artifact/provider: "^repr t identity^".") in
  if not (SR.accepted record) then fail ("Artifact "^repr t identity^" has not passed its acceptance checks.");
  if not (same_text t (current_dependency t "target") t.target_identity) then fail "Target context changed after pipeline creation.";
  let changes=List.filter_map (fun (key,value)->if same_text t (current_dependency t key) value then None else Some key)
    (bounded t (SR.dependencies record)) in
  if changes<>[] then fail ("Stale artifact "^repr t identity^"; changed dependencies: "^String.concat ", " changes^".");
  (match SR.parent record,SR.pass_id record with
   | Some parent,pass_id->
       ignore (get_in t (identity::visited) parent);
       let registration=Option.bind pass_id (fun id->lookup t id t.passes) in
       if not (match registration,SR.pass_identity record with Some value,Some expected->same_text t (PC.fingerprint value.contract) expected|_->false) then
         fail ("Stale artifact "^repr t identity^"; pass contract/provider changed.")
   | None,Some pass_id->
       let registration=lookup t pass_id t.admissions in
       if not (match registration,SR.pass_identity record with Some value,Some expected->same_text t (IC.fingerprint value.admission_contract) expected|_->false) then
         fail ("Stale artifact "^repr t identity^"; component admission policy changed.")
   | None,None->());record
let get t identity=with_call t (fun ()->get_in t [] identity)
let add_input_in t ~identity ~stage ~requirements ~obligations ~source_identity payload=
  name t "Input artifact id" identity;
  require (stage=C.Intent) "Only authoritative intent inputs can enter a pipeline.";
  if contains t identity t.records then fail ("Artifact "^repr t identity^" already exists.");
  let requirements=names t "Requirements" requirements in
  let obligations=bounded t obligations in
  require (List.length (unique t (List.map SO.id obligations))=List.length obligations) "Invalid input obligations.";
  let document=document t payload in
  let actual=match source_identity with None->fingerprint t document|Some value->text t value;value in
  if not (same_text t actual (current_dependency t "request")) then fail "Input artifact does not match the authoritative request identity.";
  let declared_target=field document "target" in
  if declared_target<>Json.Null && not (same_text t (fingerprint t declared_target) t.target_identity) then
    fail "Input request target differs from the pipeline target.";
  let record=SR.make ~limits:(codec t) ~id:identity ~stage ~payload:document ~requirements ~obligations ~discharged:[]
    ~dependencies:t.dependencies ~parent:None ~pass_id:None ~pass_identity:None ~checks:(obj [])
    ~provenance:(obj ["authority",str "frozen_input"]) ~accepted:true () in
  store_record t identity record;record
let add_input t ~identity ?(stage=C.Intent) ?(requirements=[]) ?(obligations=[]) payload=with_call t (fun ()->
  add_input_in t ~identity ~stage ~requirements ~obligations ~source_identity:None payload)
let add_build_request t ~identity ?(requirements=[]) ?(obligations=[]) request=with_call t (fun ()->
  let payload=Build_request.to_json request in
  (* Computing a semantic request identity is delegated to its native authority
     codec; there is no externally supplied fingerprint override. *)
  ignore (measure t payload);charge t (4*(String.length (X.encode ~limits:(codec t) payload)+1));
  let source_identity=Some (Build_request.fingerprint request) in
  add_input_in t ~identity ~stage:C.Intent ~requirements ~obligations ~source_identity payload)
let at_path t document path=
  List.fold_left (fun value key->text t key;field value key) document (bounded t path)
let missing t keys=sorted t (List.filter (fun key->not (contains t key t.dependencies)) (bounded t keys))
let callback t provider context=
  charge t 1;
  let value=provider t.budget context in
  (* Even explicitly invalid return data is bounded before diagnostics inspect
     it. This variant represents trusted native fixture/provider failure, not
     a public wire callback or an accepted serialized record. *)
  (match value with Proposal value->ignore (measure t (PR.to_json value))
   | Decision value->ignore (measure t (CD.to_json value))
   | Invalid_return value->ignore (measure t value));value
let decision_json t spec decision document dependencies=
  let spec_fields=Json.object_fields (CS.to_json spec) and decision_fields=Json.object_fields (CD.to_json decision) in
  obj (spec_fields@decision_fields@["subject",str (fingerprint t document);"dependencies",assoc_json dependencies])
let accepted t checks=List.for_all (fun (_,value)->charge t 1;field value "outcome"=str "pass") (bounded t checks)
let context t ~input ~output ~configuration ~dependencies ~requirements ?(source_links=[]) ?(observation_map=obj []) ()=
  C.Pass_context.make ~limits:(codec t) ~input ~output ~target:t.target_value ~configuration ~dependencies
    ~requirements ~source_links ~observation_map ()
let admit_component_input t ~contract_id ~identity payload=with_call t (fun ()->
  name t "Input artifact id" identity;
  if t.records<>[] then fail "Component admission requires a new pipeline with no existing records.";
  let registration=match lookup t contract_id t.admissions with Some value->value
    | None->fail "Missing component admission policy." in
  let contract=registration.admission_contract and validators=registration.admission_validators in
  let unresolved=missing t (IC.dependency_keys contract) in
  if unresolved<>[] then fail ("Missing admission dependencies: "^String.concat ", " unresolved);
  let document=document t payload in
  if field document "schema_version"<>str (IC.schema contract) then fail "Component input schema does not match admission policy.";
  if not (same_text t (fingerprint t document) (current_dependency t "request")) then
    fail "Component input does not match authoritative request identity.";
  if not (same_text t (fingerprint t (field document "target")) t.target_identity) then
    fail "Component input target differs from the pipeline target.";
  let nodes=field (at_path t document (IC.operation_path contract)) "nodes" in
  let valid,ids=match nodes with
    | Json.Array (_::_ as nodes)->
        let ids=List.map (fun node->charge t 1;
          match node,field node "kind",field node "id" with
          | Json.Object _,Json.String "component_instance",Json.String id->
              (try ignore (Json.name (str id));Some id with Diagnostic.Error _->None)
          | _->None) (bounded t nodes) in
        List.for_all Option.is_some ids,List.filter_map Fun.id ids
    | _->false,[] in
  if not valid || List.length (unique t ids)<>List.length ids then
    fail "Component admission requires a unique component inventory.";
  let dependencies=t.dependencies in
  let context=context t ~input:document ~output:None ~configuration:(obj []) ~dependencies
    ~requirements:(IC.requirements contract) () in
  let checks,discharged=List.fold_left (fun (checks,discharged) spec->
    let provider=match lookup t (CS.id spec) validators with Some value->value|None->assert false in
    let decision=match callback t provider context with Decision value->value|_->
      fail "Admission validator must return an explicit CheckDecision." in
    let checks=checks@[CS.id spec,decision_json t spec decision document dependencies] in
    let discharged=if CD.outcome decision=Realization_evidence.Pass then unique t (discharged@CS.discharges spec) else discharged in
    checks,discharged) ([],[]) (bounded t (IC.checks contract)) in
  let is_accepted=accepted t checks in
  let record=SR.make ~limits:(codec t) ~id:identity ~stage:C.Components ~payload:document ~requirements:(IC.requirements contract)
    ~obligations:(IC.obligations contract) ~discharged:(sorted t discharged) ~dependencies ~parent:None
    ~pass_id:(Some (IC.id contract)) ~pass_identity:(Some (IC.fingerprint contract)) ~checks:(obj checks)
    ~provenance:(obj ["authority",str "independently_checked_component_input";"contract",IC.to_json contract])
    ~accepted:is_accepted () in
  store_record t identity record;if is_accepted then ignore (get_in t [] identity);record)
let node_ids t raw=
  match field raw "nodes" with
  | Json.Array nodes->List.map (fun value->charge t 1;field value "id") (bounded t nodes)
  | _->[]
let json_member t expected values=
  List.exists (fun value->
    let left=measure t expected and right=measure t value in
    charge t (88*(left.bytes+right.bytes)+4608*(left.nodes+right.nodes)+2);
    Json.equal value expected) (bounded t values)
let run t ~pass_id ~input_id ~output_id ?(configuration=obj []) ()=with_call t (fun ()->
  let source=get_in t [] input_id in
  name t "Output artifact id" output_id;
  if contains t output_id t.records then fail ("Artifact "^repr t output_id^" already exists; use a new identity.");
  let registration=match lookup t pass_id t.passes with Some value->value
    | None->fail ("Missing pass provider: "^repr t pass_id^".") in
  let contract=registration.contract and producer=registration.producer and validators=registration.validators in
  if SR.stage source<>PC.input_stage contract || field (SR.payload source) "schema_version"<>str (PC.input_schema contract) then
    fail "Pass ordering or input schema does not match the accepted stage.";
  if not (member t (Build_request.Target.payload_format t.target_value) (PC.targets contract)) then
    fail "Pass does not support the requested target.";
  if not (subset t (PC.required_capabilities contract) (Build_request.Target.capabilities t.target_value)) then
    fail "Target lacks required pass capabilities.";
  let unresolved=missing t (PC.dependency_keys contract) in
  if unresolved<>[] then fail ("Unresolved dependency providers: "^String.concat ", " unresolved^".");
  if not (subset t (PC.consumes_requirements contract) (SR.requirements source)) then
    fail "Pass consumes requirements absent from its authoritative input.";
  let configuration=if configuration=Json.Null then obj [] else configuration in
  ignore (measure t configuration);
  require (match configuration with Json.Object _->true|_->false) "Pass configuration must be an object.";
  let dependencies=t.dependencies in
  let before=context t ~input:(SR.payload source) ~output:None ~configuration ~dependencies ~requirements:(SR.requirements source) () in
  let proposal=match callback t producer before with Proposal value->value|_->fail "Pass must return a candidate PassResult." in
  let search_status=PR.search_status proposal in
  if search_status<>"candidate" && search_status<>"no_candidate_found" then
    fail "Unknown search outcome; no-candidate results cannot prove infeasibility.";
  if search_status="no_candidate_found" then begin
    if Option.is_some (PR.output proposal) then fail "A no-candidate search cannot contain candidate output.";
    let message="No candidate found within search "^repr t pass_id^"; infeasibility is not established." in
    raise (No_candidate_found {pass_id;configuration;dependencies;message})
  end;
  let document=match PR.output proposal with Some raw->document t raw
    | None->fail "A successful search must supply a candidate." in
  if field document "schema_version"<>str (PC.output_schema contract) then
    fail "Candidate output schema does not match the destination profile.";
  let raw_nodes=field (at_path t document (PC.operation_path contract)) "nodes" in
  let nodes=match raw_nodes with Json.Array nodes when List.for_all (function
      | Json.Object fields->List.mem_assoc "kind" fields|_->false) (bounded t nodes)->nodes
    | _->fail "This pipeline profile requires an explicit operation inventory in nodes." in
  let kinds=List.map (fun node->match field node "kind" with Json.String value->value
    | _->fail "This pipeline profile requires string operation kinds in nodes.") nodes in
  let unsupported=sorted t (List.filter (fun kind->not (member t kind (PC.supported_operations contract))) kinds) in
  if unsupported<>[] then fail ("Unsupported destination operations: "^String.concat ", " unsupported^".");
  let links=bounded t (PR.source_links proposal) in
  if not (List.for_all (fun link->same_text t (SL.pass_name link) (PC.id contract)) links) then
    fail "Invalid source correspondence or pass identity.";
  let required=SR.requirements source and output_ids=List.map (fun node->field node "id") nodes in
  let input_inventory=match SR.pass_id source with
    | Some id->
        let path=match SR.parent source with
          | Some _->(match lookup t id t.passes with Some registration->PC.operation_path registration.contract
            | None->fail "Missing accepted parent pass provider.")
          | None->(match lookup t id t.admissions with Some registration->IC.operation_path registration.admission_contract
            | None->fail "Missing accepted parent admission provider.") in
        (* The same trusted path is used for its accepted parent wrapper. *)
        at_path t (SR.payload source) path
    | None->let raw=SR.payload source in
        (match raw with Json.Object fields when List.mem_assoc "intent" fields->field raw "intent"|_->raw) in
  let input_ids=node_ids t input_inventory in
  if List.exists (fun link->not (member t (SL.requirement_id link) required) ||
      not (json_member t (str (SL.target_node_id link)) output_ids) ||
      not (json_member t (str (SL.source_node_id link)) input_ids)) links then
    fail "Source map refers to an unknown requirement or node.";
  let linked=List.map SL.requirement_id links in
  if PC.requires_source_map contract && not (subset t linked required && subset t required linked) then
    fail "Candidate must retain source correspondence for every input requirement.";
  let observation_map=PR.observation_map proposal in
  if not (match observation_map with Json.Object _->true|_->false) then fail "Observation mapping must be an object.";
  if PC.requires_observation_map contract && observation_map=obj [] then fail "Candidate is missing its contracted observation mapping.";
  let obligations=List.map (fun value->SO.id value,value) (bounded t (SR.obligations source)) in
  let introduced=List.map (fun value->SO.id value,value) (bounded t (PC.introduces contract)) in
  if List.exists (fun (key,_)->contains t key obligations) introduced then fail "Pass cannot redefine an upstream obligation.";
  let obligations=obligations@introduced in
  if List.exists (fun value->match lookup t (PO.requirement_id value) obligations with
      | None->true
      | Some obligation->PO.evidence_kind value<>SO.evidence_kind obligation ||
          not (same_text t (PO.description value) (SO.description obligation)) || PO.evidence_refs value<>[])
      (bounded t (PR.obligations proposal)) then
    fail "Candidate changed an authoritative obligation or supplied self-certifying evidence.";
  let context=context t ~input:(SR.payload source) ~output:(Some document) ~configuration ~dependencies
    ~requirements:required ~source_links:links ~observation_map () in
  let invalidated=PC.invalidated_analyses contract in
  if not (subset t invalidated (List.map fst obligations)) then fail "Invalidation names an unknown obligation.";
  let discharged=List.filter (fun key->not (member t key invalidated)) (bounded t (SR.discharged source)) in
  let checks,discharged=List.fold_left (fun (checks,discharged) spec->
    List.iter (fun id->match lookup t id obligations with
      | Some obligation when SO.evidence_kind obligation=CS.evidence_kind spec->()
      | _->fail "Check scope or evidence kind cannot discharge the claimed obligation.") (bounded t (CS.discharges spec));
    let provider=match lookup t (CS.id spec) validators with Some value->value|None->assert false in
    let decision=match callback t provider context with Decision value->value|_->
      fail "Independent validator must return an explicit CheckDecision." in
    let checks=checks@[CS.id spec,decision_json t spec decision document dependencies] in
    let discharged=if CD.outcome decision=Realization_evidence.Pass then unique t (discharged@CS.discharges spec) else discharged in
    checks,discharged) ([],discharged) (bounded t (PC.checks contract)) in
  let is_accepted=accepted t checks in
  let record=SR.make ~limits:(codec t) ~id:output_id ~stage:(PC.output_stage contract) ~payload:document ~requirements:required
    ~obligations:(List.map snd obligations) ~discharged:(sorted t discharged) ~dependencies ~parent:(Some input_id)
    ~pass_id:(Some (PC.id contract)) ~pass_identity:(Some (PC.fingerprint contract)) ~checks:(obj checks)
    ~provenance:(obj ["contract",PC.to_json contract;"configuration",configuration;
      "source_links",Json.Array (List.map SL.to_json links);"observation_map",observation_map;
      "search",str "deterministic; no inference of infeasibility"]) ~accepted:is_accepted () in
  store_record t output_id record;if is_accepted then ignore (get_in t [] output_id);record)
let result t ~identity ~scope=with_call t (fun ()->
  let artifact=get_in t [] identity in
  let profile=match lookup t scope t.profiles with Some value->value
    | None->fail ("Unsupported completion profile: "^repr t scope^".") in
  let discharged=SR.discharged artifact in
  let unresolved=List.filter (fun value->not (member t (SO.id value) discharged)) (bounded t (SR.obligations artifact)) in
  let required=CP.obligations profile@List.filter_map (fun value->
    if same_text t (SO.scope value) scope then Some (SO.id value) else None) (bounded t (SR.obligations artifact)) in
  let complete=SR.stage artifact=CP.stage profile && field (SR.payload artifact) "schema_version"=str (CP.schema profile) &&
    subset t required discharged in
  C.Pipeline_result.make ~limits:(codec t) ~status:(if complete then C.Complete else C.Partial) ~artifact ~scope ~unresolved ())
let inspect t ~provider_identity=with_call t (fun ()->
  let provider value=charge t 1;let id=provider_identity value in name t "Provider inspection identity" id;str id in
  let validators values=obj (List.map (fun (key,value)->key,provider value) (bounded t values)) in
  let registration value=obj ["contract",PC.to_json value.contract;"producer",provider value.producer;"validators",validators value.validators] in
  let admission value=obj ["contract",IC.to_json value.admission_contract;"validators",validators value.admission_validators] in
  let map encode values=obj (List.map (fun (key,value)->text t key;key,encode value) (bounded t values)) in
  let raw=obj ["target",Build_request.Target.to_json t.target_value;"dependencies",assoc_json t.dependencies;
    "passes",map registration t.passes;"component_inputs",map admission t.admissions;
    "provider_history",map registration t.provider_history;"component_input_history",map admission t.admission_history;
    "records",map SR.to_json t.records;"profiles",map CP.to_json t.profiles] in
  ignore (measure t raw);raw)

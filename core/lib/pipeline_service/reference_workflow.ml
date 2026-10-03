open Bioc_wire
open Bioc_domain
module M=Bioc_compiler.Pass_manager
module C=Pipeline_contract
module W=Bioc_checker.Work_budget
module Construct=Bioc_pipeline.Reference_construct_pipeline
module Molecular=Bioc_pipeline.Reference_molecular_pipeline

type phase=Fresh|Initializing|Construct_created|Admission_available
  |Admission_registered|Admission_returned|Admission_checked
  |Construct_registration_available|Construct_registered|Construct_ran
  |Construct_result|Construct_finished|Molecular_dependencies
  |Molecular_profile_available|Molecular_profile_registered
  |Molecular_registration_available|Molecular_registered|Molecular_ran
  |Molecular_result|Molecular_finished|Interrupted|Closed

type operation=
  |Input_registered of C.Component_input_contract.t*(string*M.provider) list
  |Admitted of {contract_id:string;identity:string;record:C.Stage_record.t}
  |Got of {identity:string;record:C.Stage_record.t}
  |Pass_registered of C.Pass_contract.t*M.provider*(string*M.provider) list
  |Ran of {pass_id:string;input_id:string;output_id:string;
      default_configuration:bool;record:C.Stage_record.t}
  |Result_returned of {identity:string;scope:string;result:C.Pipeline_result.t}
  |Dependency_set of string*string
  |Profile_registered of C.Completion_profile.t

type t={work:W.t;retain:int->unit;limits:M.limits;codec:C.Codec.limits;
  mutable phase_value:phase;mutable owner_value:M.t option;
  mutable initialized:Construct.initialized option;
  mutable admission:Construct.admission option;
  mutable admitted:C.Stage_record.t option;
  mutable construct_registration:Construct.registration option;
  mutable construct_host_comparison:bool;
  mutable construct_run:C.Stage_record.t option;
  mutable construct_result_value:(int*C.Pipeline_result.t) option;
  mutable construct_value:Construct.t option;
  mutable molecular_prepared:Molecular.prepared option;
  mutable pending_dependencies:(string*string) list;
  mutable molecular_profile:Molecular.profiled option;
  mutable molecular_registration:Molecular.registration option;
  mutable molecular_host_comparison:bool;
  mutable molecular_run:C.Stage_record.t option;
  mutable molecular_result_value:(int*C.Pipeline_result.t) option;
  mutable molecular_value:Molecular.t option;
  sequences:(int,unit) Hashtbl.t}
let failure message=Diagnostic.fail "reference_workflow_phase" message
let required=function Some value->value|None->failure "Reference workflow capability is unavailable."
let setting limits name=Z.to_int(Json.integer(Json.field name(Json.object_fields(M.limits_json limits))))
let reserve (state:t) bytes=
  Diagnostic.require(state.phase_value<>Closed) "reference_workflow_closed" "Reference workflow is closed.";
  Diagnostic.require(not(W.exhausted state.work)) "reference_workflow_limit" "Reference workflow lifetime budget is exhausted.";
  Diagnostic.require(bytes>=0) "reference_workflow_limit" "Invalid reference workflow reservation.";
  W.charge state.work 1;state.retain bytes;
  Diagnostic.require(state.phase_value<>Closed) "reference_workflow_closed" "Reference workflow was closed during reservation."
let retain_document (state:t) raw=
  Diagnostic.require(state.phase_value<>Closed) "reference_workflow_closed" "Reference workflow is closed.";
  let size=C.Codec.measure ~limits:state.codec raw in
  Diagnostic.require(size.nodes<=(max_int-size.bytes-128)/32) "reference_workflow_limit"
    "Reference workflow retained representation exceeds its native bound.";
  reserve state(size.bytes+32*size.nodes+128)
let check (state:t) budget=
  Diagnostic.require(budget==state.work) "reference_workflow_budget" "Reference workflow received a foreign lifetime budget.";
  Diagnostic.require(state.phase_value<>Closed) "reference_workflow_closed" "Reference workflow is closed.";
  Diagnostic.require(not(W.exhausted budget)) "reference_workflow_limit" "Reference workflow lifetime budget is exhausted.";
  W.charge budget 1
let require_phase (state:t) expected=
  if state.phase_value<>expected then failure "Reference workflow operation is not available in the current phase."
let equality (state:t) left right=
  let a=C.Codec.encode ~limits:state.codec left in
  let b=C.Codec.encode ~limits:state.codec right in
  W.charge state.work(String.length a+String.length b+1);String.equal a b
let create ~budget ~retain_bytes ?(manager_limits=M.default_limits) ()=
  W.charge budget 1;retain_bytes 2048;
  let codec=C.Codec.make_limits ~max_bytes:(setting manager_limits "max_document_bytes")
    ~max_nodes:(setting manager_limits "max_document_nodes") ~charge:(W.charge budget) () in
  {work=budget;retain=retain_bytes;limits=manager_limits;codec;phase_value=Fresh;owner_value=None;
   initialized=None;admission=None;admitted=None;construct_registration=None;
   construct_host_comparison=false;construct_run=None;construct_result_value=None;construct_value=None;
   molecular_prepared=None;pending_dependencies=[];molecular_profile=None;molecular_registration=None;
   molecular_host_comparison=false;molecular_run=None;molecular_result_value=None;molecular_value=None;
   sequences=Hashtbl.create 16}
let owner (state:t)=state.owner_value
let phase (state:t)=state.phase_value
let close (state:t)=
  state.phase_value<-Closed;state.owner_value<-None;state.initialized<-None;
  state.admission<-None;state.admitted<-None;state.construct_registration<-None;
  state.construct_run<-None;state.construct_result_value<-None;state.construct_value<-None;
  state.molecular_prepared<-None;state.pending_dependencies<-[];state.molecular_profile<-None;
  state.molecular_registration<-None;state.molecular_run<-None;
  state.molecular_result_value<-None;state.molecular_value<-None;Hashtbl.clear state.sequences
(* An explicit preparation/finish is one-shot even if its callback throws. The
   actual published manager and all already performed mutations remain owned. *)
let attempt (state:t) action=
  state.phase_value<-Interrupted;
  action()
let initialize_construct (state:t) ~budget ?validator_equivalent ?observer ?manager_created
    ~request ~registry ~manifests ()=
  check state budget;require_phase state Fresh;state.phase_value<-Initializing;
  try
    retain_document state(Reference_construct.Request.to_json request);
    retain_document state(Component_registry.to_json registry);
    List.iter(fun(key,value)->W.charge budget(String.length key+1);
      reserve state(String.length key+64);retain_document state(Reference_manifest.to_json value)) manifests;
    (* Reserve shallow phase/closure cells separately from every variable
       authority/declaration tree retained by those capabilities. *)
    reserve state 2048;
    let prepared=Construct.prepare ~budget ~manager_limits:state.limits ~request ~registry ~manifests () in
    List.iter(fun(key,identity)->reserve state(String.length key+String.length identity+128))(Construct.dependencies prepared);
    List.iter(fun value->retain_document state(C.Scoped_obligation.to_json value))(Construct.obligations prepared);
    retain_document state(C.Completion_profile.to_json(Construct.completion_profile prepared));
    let publish actual manager=
      Diagnostic.require(actual==budget && state.owner_value=None) "reference_workflow_owner"
        "Reference manager publication changed its owner or lifetime.";
      reserve state 128;state.owner_value<-Some manager;
      Option.iter(fun callback->callback actual manager) manager_created in
    let initialized=Construct.create ~budget ?validator_equivalent ?observer ~manager_created:publish prepared in
    let manager=Construct.initialized_manager initialized in
    check state budget;
    Diagnostic.require(manager==required state.owner_value) "reference_workflow_owner" "Reference manager publication was not retained.";
    reserve state 128;state.initialized<-Some initialized;state.phase_value<-Construct_created;manager
  with error->if state.phase_value<>Closed then state.phase_value<-Interrupted;raise error
let prepare_admission (state:t) ~budget ?provider_observer ()=
  check state budget;require_phase state Construct_created;
  attempt state(fun()->
    reserve state 512;
    let value=Construct.prepare_admission ~budget ?provider_observer(required state.initialized) in
    retain_document state(C.Component_input_contract.to_json(Construct.admission_contract value));
    state.admission<-Some value;state.phase_value<-Admission_available;value)
let prepare_construct_registration (state:t) ~budget ?provider_observer ?generator_bridge ?host_links_equal ()=
  check state budget;require_phase state Admission_checked;
  attempt state(fun()->
    reserve state 512;
    let value=Construct.prepare_registration ~budget ?provider_observer ?generator_bridge ?host_links_equal
      (required state.admission) ~admitted:(required state.admitted) in
    retain_document state(C.Pass_contract.to_json(Construct.contract value));
    state.construct_registration<-Some value;state.construct_host_comparison<-Option.is_some host_links_equal;
    state.phase_value<-Construct_registration_available;value)
let allow_matching (state:t) actual expected enabled=
  let manager=required state.owner_value in
  List.iter(fun(name,native)->W.charge state.work(String.length name+1);
    if enabled name then match List.assoc_opt name actual with
      |Some registered when registered==native->M.allow_host_source_links manager native
      |_->())expected
let remember_record (state:t) record=retain_document state(C.Stage_record.to_json record)
let valid_record record ~identity ~stage ~parent ~pass_id=
  C.Stage_record.id record=identity && C.Stage_record.stage record=stage &&
  C.Stage_record.parent record=parent && C.Stage_record.pass_id record=pass_id
let result_matches record result scope=
  C.Pipeline_result.scope result=scope && C.Pipeline_result.artifact result==record
let notice (state:t) ~budget ~owner:manager ~sequence operation=
  check state budget;
  Diagnostic.require(manager==required state.owner_value) "reference_workflow_owner" "Reference operation belongs to another manager.";
  Diagnostic.require(sequence>=0 && not(Hashtbl.mem state.sequences sequence)) "reference_workflow_sequence"
    "Reference operation sequence was already observed or is invalid.";
  reserve state 64;Hashtbl.add state.sequences sequence ();
  match state.phase_value,operation with
  |Admission_available,Input_registered(contract,validators)->
      let admission=required state.admission in
      if equality state(C.Component_input_contract.to_json contract)
          (C.Component_input_contract.to_json(Construct.admission_contract admission)) then begin
        allow_matching state validators(Construct.admission_validators admission)(fun _->true);
        state.phase_value<-Admission_registered
      end
  |Admission_registered,Admitted{contract_id;identity;record}
      when contract_id="reference_components" && identity="components" &&
        valid_record record ~identity ~stage:C.Components ~parent:None ~pass_id:(Some "reference_components")->
      remember_record state record;state.admitted<-Some record;state.phase_value<-Admission_returned
  |Admission_returned,Got{identity="components";record} when record==required state.admitted->
      state.phase_value<-Admission_checked
  |Construct_registration_available,Pass_registered(contract,_,validators)->
      let registration=required state.construct_registration in
      if equality state(C.Pass_contract.to_json contract)(C.Pass_contract.to_json(Construct.contract registration)) then begin
        allow_matching state validators(Construct.validators registration)
          (fun name->name="layout_composition" || state.construct_host_comparison);
        state.phase_value<-Construct_registered
      end
  |Construct_registered,Ran{pass_id="components_to_construct";input_id="components";output_id="construct";
      default_configuration=true;record} when valid_record record ~identity:"construct" ~stage:C.Construct
        ~parent:(Some "components") ~pass_id:(Some "components_to_construct")->
      remember_record state record;state.construct_run<-Some record;state.phase_value<-Construct_ran
  |Construct_ran,Result_returned{identity="construct";scope="reference_construct";result}->
      if result_matches(required state.construct_run)result "reference_construct" then begin
        retain_document state(C.Pipeline_result.to_json result);
        state.construct_result_value<-Some(sequence,result);state.phase_value<-Construct_result
      end
  |Molecular_dependencies,Dependency_set(key,identity)->
      (match state.pending_dependencies with
       |(expected_key,expected_identity)::rest->
           W.charge budget(String.length key+String.length identity+String.length expected_key+String.length expected_identity+1);
           if key=expected_key && identity=expected_identity then state.pending_dependencies<-rest
       |[]->())
  |Molecular_profile_available,Profile_registered profile->
      if equality state(C.Completion_profile.to_json profile)
          (C.Completion_profile.to_json(Molecular.completion_profile(required state.molecular_profile))) then
        state.phase_value<-Molecular_profile_registered
  |Molecular_registration_available,Pass_registered(contract,_,validators)->
      let registration=required state.molecular_registration in
      if equality state(C.Pass_contract.to_json contract)(C.Pass_contract.to_json(Molecular.contract registration)) then begin
        allow_matching state validators(Molecular.validators registration)
          (fun name->name="encoding_composition" || state.molecular_host_comparison);
        state.phase_value<-Molecular_registered
      end
  |Molecular_registered,Ran{pass_id="construct_to_molecular";input_id="construct";output_id="molecular";
      default_configuration=true;record} when valid_record record ~identity:"molecular" ~stage:C.Molecular
        ~parent:(Some "construct") ~pass_id:(Some "construct_to_molecular")->
      remember_record state record;state.molecular_run<-Some record;state.phase_value<-Molecular_ran
  |Molecular_ran,Result_returned{identity="molecular";scope="exact_cds";result}->
      if result_matches(required state.molecular_run)result "exact_cds" then begin
        retain_document state(C.Pipeline_result.to_json result);
        state.molecular_result_value<-Some(sequence,result);state.phase_value<-Molecular_result
      end
  |_->()
let finish_construct (state:t) ~budget ~record ~result_sequence=
  check state budget;require_phase state Construct_result;
  let sequence,result=required state.construct_result_value in
  Diagnostic.require(sequence=result_sequence && record==required state.construct_run) "reference_workflow_capability"
    "Construct finish requires its exact observed run and result capabilities.";
  attempt state(fun()->
    reserve state 256;
    let value=Construct.finish ~budget(required state.construct_registration)~record ~result in
    retain_document state(Reference_construct.Candidate.to_json(Construct.candidate value));
    retain_document state(Reference_construct_evidence.Result.to_json(Construct.check_result value));
    state.construct_value<-Some value;state.phase_value<-Construct_finished;value)
let prepare_molecular (state:t) ~budget ()=
  check state budget;require_phase state Construct_finished;
  attempt state(fun()->
    reserve state 1024;
    let value=Molecular.prepare ~budget(required state.construct_value) in
    let dependencies=Molecular.dependencies value in
    List.iter(fun(key,identity)->reserve state(String.length key+String.length identity+64))dependencies;
    state.molecular_prepared<-Some value;state.pending_dependencies<-dependencies;
    state.phase_value<-Molecular_dependencies;value)
let prepare_molecular_profile (state:t) ~budget ()=
  check state budget;require_phase state Molecular_dependencies;
  if state.pending_dependencies<>[] then failure "Molecular profile requires all six actual dependency writes in order.";
  attempt state(fun()->
    reserve state 256;
    let value=Molecular.prepare_profile ~budget(required state.molecular_prepared) in
    retain_document state(C.Completion_profile.to_json(Molecular.completion_profile value));
    state.molecular_profile<-Some value;state.phase_value<-Molecular_profile_available;value)
let prepare_molecular_registration (state:t) ~budget ?provider_observer ?emitter_bridge ?host_links_equal ()=
  check state budget;require_phase state Molecular_profile_registered;
  attempt state(fun()->
    reserve state 512;
    let value=Molecular.prepare_registration ~budget ?provider_observer ?emitter_bridge ?host_links_equal
      (required state.molecular_profile) in
    retain_document state(C.Pass_contract.to_json(Molecular.contract value));
    state.molecular_registration<-Some value;state.molecular_host_comparison<-Option.is_some host_links_equal;
    state.phase_value<-Molecular_registration_available;value)
let finish_molecular (state:t) ~budget ~record ~result_sequence=
  check state budget;require_phase state Molecular_result;
  let sequence,result=required state.molecular_result_value in
  Diagnostic.require(sequence=result_sequence && record==required state.molecular_run) "reference_workflow_capability"
    "Molecular finish requires its exact observed run and result capabilities.";
  attempt state(fun()->
    reserve state 256;
    let value=Molecular.finish ~budget(required state.molecular_registration)~record ~result in
    retain_document state(Reference_molecular.Artifact.to_json(Molecular.candidate value));
    retain_document state(Reference_molecular_evidence.Result.to_json(Molecular.check_result value));
    state.molecular_value<-Some value;state.phase_value<-Molecular_finished;value)
let construct_build (state:t)=state.construct_value
let molecular_build (state:t)=state.molecular_value
let construct_result_sequence (state:t)=Option.map fst state.construct_result_value
let molecular_result_sequence (state:t)=Option.map fst state.molecular_result_value

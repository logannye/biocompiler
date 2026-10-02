open Bioc_wire
module X=Verification_exploration
module C=X.Codec
module E=Realization_evidence
module N=Runtime_number
module A=Synthetic_authority
let str value=Json.String value
let obj value=Json.Object value
let optional parse=function Json.Null->None|value->Some(parse value)
let option_json parse=function None->Json.Null|Some value->parse value
let require ?path condition message=Diagnostic.require ?path condition "verification_workflow" message
let workflow_version="biocompiler.synthetic_verification_workflow.v0.1"
let claim_scope="Historical finite-history software-model verification record; fresh replay requires independent complete operation authority. No universal, biological or human therapeutic claim."
type operation=Check|Explore|Reduce
type mode=Candidate|Model
let operation_name=function Check->"check"|Explore->"explore"|Reduce->"reduce"
let mode_name=function Candidate->"candidate"|Model->"model"
let record limits path label keys raw =
  C.preflight ~limits ~path raw;
  match raw with Json.Object fields->
    C.charge limits(256*(List.length keys+1));
    require ~path(List.sort String.compare(List.map fst fields)=List.sort String.compare keys)("Invalid fields in "^label^"."); fields
  |_->Diagnostic.fail ~path "verification_workflow" ("Invalid fields in "^label^".")
let schema path expected actual=Diagnostic.require ~path(actual=str expected) "unsupported_schema" "Unsupported exploration schema."
let field path fields key=Json.field ~path:(path^"/"^key)key fields
let string_or_empty=function Json.String value->value|_->""
let until_value path=function Json.Int value->N.Integer value|Json.Float value->N.Real value
  |_->Diagnostic.fail ~path "verification_exploration" "Exploration times must be finite nonnegative numbers."
let budget_value path=function Json.Int value when Z.compare value Z.one>=0 && Z.compare value(Z.of_int 100000)<=0->Z.to_int value
  |_->Diagnostic.fail ~path "verification_exploration" "Invalid reduction evaluation budget."
type packed={json:Json.t;fingerprint:string;size:int}
let pack limits json=let text=C.encode ~limits json in C.charge limits(String.length text);
  {json;fingerprint=Canonical.sha256 text;size=String.length text}
module Request=struct
  type t={packed:packed;realization:Realization_request.t;candidate:A.Candidate.t;operation:operation;mode:mode;
    history:Execution_data.Input_frame.t list;until:N.t option;bounds:X.Bounds.t option;
    signature:X.Failure_signature.t option;max_evaluations:int option}
  let schema_version="biocompiler.synthetic_verification_request.v0.1"
  let make ?(limits=C.default_limits) ~realization ~candidate ~operation ?(mode=Candidate) ?(history=[]) ?until ?bounds
      ?signature ?max_evaluations () =
    C.charge limits(Realization_request.canonical_size realization+A.Candidate.canonical_size candidate+1);
    (match operation with
    |Explore->require(bounds<>None) "Exploration needs explicit Boolean bounds.";
      require(history=[] && until=None && signature=None && max_evaluations=None)
        "Exploration authority must contain bounds only, not separate history/reduction controls."
    |Check|Reduce->require(bounds=None) "Check/reduction authority cannot include unused exploration bounds.";
      let horizon=match until with Some value->value|None->until_value "" Json.Null in
      X.validate_history ~limits history horizon;
      (match operation with Check->require(signature=None && max_evaluations=None) "A check cannot contain unused reduction controls."
      |Reduce->require(signature<>None) "Reduction needs an explicit selected failure.";
        require(match max_evaluations with Some value->value>=1 && value<=100000|None->false) "Invalid reduction evaluation budget."
      |Explore->assert false));
    let packed=pack limits(obj["schema_version",str schema_version;"realization",Realization_request.to_json realization;
      "candidate",A.Candidate.to_json candidate;"operation",str(operation_name operation);"mode",str(mode_name mode);
      "history",X.history_json history;"until",option_json N.to_json until;"bounds",option_json X.Bounds.to_json bounds;
      "signature",option_json X.Failure_signature.to_json signature;"max_evaluations",option_json Json.int max_evaluations]) in
    {packed;realization;candidate;operation;mode;history;until;bounds;signature;max_evaluations}
  let decode_with_realization ?(limits=C.default_limits) ?(path="") ~decode_realization raw =
    let fields=record limits path "SyntheticVerificationRequest" ["schema_version";"realization";"candidate";"operation";"mode";
      "history";"until";"bounds";"signature";"max_evaluations"]raw in
    let get=field path fields in schema path schema_version(get "schema_version");
    (* Nested decoders run in dataclass field order before constructor checks. *)
    let realization=decode_realization ~path:(path^"/realization")(get "realization") in
    let candidate=A.Candidate.of_json ~path:(path^"/candidate")(get "candidate") in
    let history=X.frames_of_json ~limits ~path:(path^"/history")(get "history") in
    let bounds=optional(X.Bounds.of_json ~limits ~path:(path^"/bounds"))(get "bounds") in
    let signature=optional(X.Failure_signature.of_json ~limits ~path:(path^"/signature"))(get "signature") in
    let operation=match get "operation" with Json.String "check"->Check|Json.String "explore"->Explore|Json.String "reduce"->Reduce
      |_->Diagnostic.fail ~path "verification_workflow" "Unsupported verification operation." in
    let mode=match get "mode" with Json.String "candidate"->Candidate|Json.String "model"->Model
      |_->Diagnostic.fail ~path "verification_workflow" "Unsupported verification mode." in
    let until,max_evaluations=match operation with
    |Explore->require(bounds<>None) "Exploration needs explicit Boolean bounds.";
      require(history=[] && get "until"=Json.Null && signature=None && get "max_evaluations"=Json.Null)
        "Exploration authority must contain bounds only, not separate history/reduction controls."; None,None
    |Check|Reduce->require(bounds=None) "Check/reduction authority cannot include unused exploration bounds.";
      let until=until_value(path^"/until")(get "until") in X.validate_history ~limits history until;
      let max_evaluations=match operation with
      |Check->require(signature=None && get "max_evaluations"=Json.Null) "A check cannot contain unused reduction controls."; None
      |Reduce->require(signature<>None) "Reduction needs an explicit selected failure."; Some(budget_value(path^"/max_evaluations")(get "max_evaluations"))
      |Explore->assert false in Some until,max_evaluations in
    make ~limits ~realization ~candidate ~operation ~mode ~history ?until ?bounds ?signature ?max_evaluations ()
  let of_json ?limits ?path raw=decode_with_realization ?limits ?path
    ~decode_realization:(fun ~path raw->Realization_request.of_json ~path raw) raw
  let to_json value=value.packed.json
  let fingerprint value=value.packed.fingerprint
  let canonical_size value=value.packed.size
  let realization value=value.realization
  let candidate value=value.candidate
  let operation value=value.operation
  let mode value=value.mode
  let history value=value.history
  let until value=value.until
  let bounds value=value.bounds
  let signature value=value.signature
  let max_evaluations value=value.max_evaluations
end
type result=Checked of E.Check_result.t|Explored of X.Report.t|Reduced of X.Reduction.t
let result_to_json=function Checked value->E.Check_result.to_json value|Explored value->X.Report.to_json value|Reduced value->X.Reduction.to_json value
let result_size=function Checked value->E.Check_result.canonical_size value|Explored value->X.Report.canonical_size value|Reduced value->X.Reduction.canonical_size value
let result_of_json ?(limits=C.default_limits) ?(path="") raw =
  C.preflight ~limits ~path raw;
  let fields=match raw with Json.Object fields->fields|_->Diagnostic.fail ~path "verification_workflow" "Verification result must be an object." in
  let schema=match List.assoc_opt "schema_version" fields with Some(Json.String value)->value
    |_->Diagnostic.fail ~path "verification_workflow" "Verification result schema must be text." in
  if schema=E.Check_result.schema_version then Checked(X.check_of_json ~limits ~path raw)
  else if schema="biocompiler.boolean_exploration_report.v0.1" then Explored(X.Report.contact_of_json ~limits ~path raw)
  else if schema="biocompiler.boolean_input_exploration_report.v0.1" then Explored(X.Report.input_of_json ~limits ~path raw)
  else if schema=X.Reduction.schema_version then Reduced(X.Reduction.of_json ~limits ~path raw)
  else Diagnostic.fail ~path "unsupported_schema" "Unsupported verification result schema."
module Record=struct
  type t={packed:packed;request:Request.t;result:result;workflow_version:string;claim_scope:string}
  let schema_version="biocompiler.synthetic_verification_record.v0.1"
  let make ?(limits=C.default_limits) ~request ~result ?workflow_version:version ?claim_scope:scope () =
    let version=Option.value version ~default:workflow_version and scope=Option.value scope ~default:claim_scope in
    require(version=workflow_version && scope=claim_scope) "Unsupported workflow version or claim scope.";
    C.charge limits(Request.canonical_size request+result_size result+1);
    (match Request.operation request,result with
    |Check,Checked value->X.validate_result ~limits value(Request.history request)(Option.get(Request.until request))
    |Check,_->require false "Check operation requires CheckResult."
    |Explore,Explored value->require(X.Bounds.fingerprint(X.Report.config value)=X.Bounds.fingerprint(Option.get(Request.bounds request)))
      "Exploration result changed the independently declared bounds."
    |Explore,_->require false "Explore operation requires ExplorationReport."
    |Reduce,Reduced value->
      require(C.fingerprint ~limits(X.history_json(X.Reduction.original_history value))=C.fingerprint ~limits(X.history_json(Request.history request)) &&
        C.fingerprint ~limits(N.to_json(X.Reduction.until value))=C.fingerprint ~limits(N.to_json(Option.get(Request.until request))) &&
        X.Failure_signature.fingerprint(X.Reduction.signature value)=X.Failure_signature.fingerprint(Option.get(Request.signature request)) &&
        X.Reduction.evaluations value<=Option.get(Request.max_evaluations request))
        "Reduction result changed its original history, horizon, selected failure or budget."
    |Reduce,_->require false "Reduce operation requires ReductionResult.");
    let packed=pack limits(obj["schema_version",str schema_version;"request",Request.to_json request;
      "result",result_to_json result;"workflow_version",str version;"claim_scope",str scope]) in
    {packed;request;result;workflow_version=version;claim_scope=scope}
  let decode_with_request ?(limits=C.default_limits) ?(path="") ~decode_request raw =
    let fields=record limits path "SyntheticVerificationRecord" ["schema_version";"request";"result";"workflow_version";"claim_scope"]raw in
    let get=field path fields in schema path schema_version(get "schema_version");
    let request=decode_request ~path:(path^"/request")(get "request") in
    let result=result_of_json ~limits ~path:(path^"/result")(get "result") in
    make ~limits ~request ~result ~workflow_version:(string_or_empty(get "workflow_version")) ~claim_scope:(string_or_empty(get "claim_scope")) ()
  let of_json ?(limits=C.default_limits) ?path raw=decode_with_request ~limits ?path
    ~decode_request:(fun ~path raw->Request.of_json ~limits ~path raw)raw
  let to_json value=value.packed.json
  let fingerprint value=value.packed.fingerprint
  let canonical_size value=value.packed.size
  let request value=value.request
  let result value=value.result
  let workflow_version value=value.workflow_version
  let claim_scope value=value.claim_scope
end

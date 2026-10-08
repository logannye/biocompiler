open Bioc_wire
open Bioc_policy_component_test_support.Literals
module Originals=Bioc_policy_component_test_support.Selection_requests
module R=Bioc_domain.Policy_component_selection_request
module V=Bioc_domain.Policy_component_selection_candidate
module P=Bioc_realization_checker.Policy_preservation_check
module Check=Bioc_realization_checker.Policy_component_selection_check
module W=Bioc_checker.Work_budget
module Producer=Bioc_producer_service.Policy_component_material_producer

(* Producer output is only the subject of fresh scoped checking. The original
   same-program census and the short/long expectations remain independent. *)
let proposed original limits=
  obj ["schema_version",str "biocompiler.policy_component_selection_candidate.v0.1";
    "alternatives",arr (List.map (fun row ->
      let value=Producer.compile (obj ["request",get "request" row;"limits",limits]) in
      obj ["id",get "id" row;"candidate",get "candidate" value]) (items "alternatives" original));
    "selected_id",str "short"]
let scope ?parent raw=Check.create_scope ?parent ~request:(R.of_json raw) ()
let checked ?parent original candidate limits=
  let request=R.of_json original in
  let scope=Check.create_scope ?parent ~request () in
  let pending=Check.check_in ~scope ~candidate:(V.of_json ~request candidate) ~limits:(P.limits_of_json limits) in
  scope,pending
let envelope ?(id="literal.selection.scope") result:Protocol.request=
  {request_id=id;operation="check-policy-component-selection";payload=result}
let frame executable request result=Protocol.response ~executable ~request:(Some request)
  ~status:Protocol.Ok ~result:(Some result) []
let failure code label action=
  incr checks;
  match action () with
  | _ -> failwith ("Expected failure: "^label)
  | exception (Diagnostic.Error diagnostic as error) ->
      require (diagnostic.code=code) ("Wrong scope failure: "^label^": "^diagnostic.code);error
let same_failure first label action=
  incr checks;
  match action () with
  | _ -> failwith ("Poisoned scope resumed: "^label)
  | exception error -> require (error==first) ("Scope replaced its original failure: "^label)
let parent maximum=W.create ~profile:"literal.selection.parent"
  ~error_code:"literal_selection_parent" ~maximum ()

let isolated_guards original=
  let generous=parent 20000000000 in
  ignore (failure "policy_component_selection_work_limit" "Large parent cannot raise the original total allowance" (fun () ->
    let owner=scope ~parent:generous (put ["budgets";"max_work"] (Json.int 1) original) in
    Check.charge_outer owner 2));
  let owner=scope ~parent:(parent 20000000000) original in
  let first=failure "policy_component_selection_outer_work_limit" "Large ancestor cannot raise the one-billion outer cap"
    (fun () -> Check.charge_outer owner 1000000001) in
  same_failure first "Caught outer work failure cannot resume at zero" (fun () -> Check.charge_outer owner 0);
  same_failure first "Caught outer failure cannot hash" (fun () -> Check.fingerprint owner Json.Null);
  ignore (failure "literal_selection_parent" "Small parent constrains original import and every later action" (fun () ->
    let owner=scope ~parent:(parent 1) original in Check.charge_outer owner 2));
  let inherited=parent 20000000000 in
  let owner=scope ~parent:inherited original in
  ignore (failure "literal_selection_parent" "An externally caught ancestor failure remains sticky"
    (fun () -> W.charge inherited 20000000001));
  let first=failure "policy_component_selection_scope" "Scope must observe caught ancestor exhaustion"
    (fun () -> Check.charge_outer owner 0) in
  same_failure first "Observed ancestor exhaustion permanently poisons the scope" (fun () -> Check.charge_outer owner 0);
  let owner=scope (put ["budgets";"max_report_bytes"] (Json.int 1) original) in
  let first=failure "policy_component_selection_publication_limit" "Original byte ceiling cannot be replaced by a service ceiling"
    (fun () -> Check.reserve_publication owner (str "x")) in
  same_failure first "Partial output debit cannot be hidden by catching the exception"
    (fun () -> Check.reserve_publication owner Json.Null);
  same_failure first "Output failure poisons otherwise available work" (fun () -> Check.charge_outer owner 0);
  let owner=scope (put ["budgets";"max_report_nodes"] (Json.int 1) original) in
  let first=failure "policy_component_selection_publication_limit" "Object keys count toward original node ceiling"
    (fun () -> Check.reserve_publication owner (obj ["key",Json.Null])) in
  same_failure first "Caught node failure cannot encode a smaller value" (fun () -> Check.encode_json owner Json.Null);
  let owner=scope (put ["budgets";"max_report_bytes"] (Json.int 6) original) in
  Check.reserve_publication owner (str "xx");
  ignore (failure "policy_component_selection_publication_limit" "Repeated identical publication is charged again"
    (fun () -> Check.reserve_publication owner (str "xx")));
  let owner=scope original in
  let rec cyclic=Json.Array [cyclic] in
  let first=failure "policy_material_input_limit" "Bounded hash preflight cannot traverse cyclic input"
    (fun () -> Check.fingerprint owner cyclic) in
  same_failure first "Failed hash preflight is terminal" (fun () -> Check.equal_json owner Json.Null Json.Null);
  let owner=scope original in
  let first=Failure "literal abort preserves exception" in
  same_failure first "Explicit preparation abort retains its exception" (fun () -> Check.abort_scope owner first);
  same_failure first "Aborted scope cannot publish" (fun () -> Check.reserve_publication owner Json.Null)

let cumulative_profile original=
  let explicit=original
    |> put ["budgets";"profile"] (str "biocompiler.policy_component_selection_resources.v0.2")
    |> put ["budgets";"max_report_nodes"] (Json.int 1000000) in
  let owner=scope explicit in
  let publication=arr (List.init 100000 (fun _ -> Json.Null)) in
  (* Each publication has 100,001 nodes and fits the unchanged individual
     250,000-node guard. The tenth reaches 1,000,010 cumulative nodes. *)
  for _=1 to 9 do Check.reserve_publication owner publication done;
  let first=failure "policy_component_selection_publication_limit" "Explicit v0.2 cumulative node ceiling is finite"
    (fun () -> Check.reserve_publication owner publication) in
  same_failure first "Caught cumulative v0.2 failure cannot publish a smaller result"
    (fun () -> Check.reserve_publication owner Json.Null);
  let owner=scope explicit in
  let too_many=arr (List.init 250000 (fun _ -> Json.Null)) in
  let first=failure "policy_material_input_limit" "Larger cumulative allowance cannot raise one publication's node bound"
    (fun () -> Check.reserve_publication owner too_many) in
  same_failure first "Per-publication bound remains sticky under v0.2"
    (fun () -> Check.reserve_publication owner Json.Null);
  let owner=scope (put ["budgets";"max_report_nodes"] (Json.int 1) explicit) in
  ignore (failure "policy_component_selection_publication_limit" "Choosing v0.2 never replaces the supplied smaller allowance"
    (fun () -> Check.reserve_publication owner (obj ["key",Json.Null])))

let positive original candidate limits=
  let request=R.of_json original in
  let typed=V.of_json ~request candidate and limits_t=P.limits_of_json limits in
  let standalone=Check.check ~request ~candidate:typed ~limits:limits_t in
  require (Option.is_some (Check.accepted standalone)) "Independent baseline lacks fresh selection acceptance";
  let ancestor=parent 3000000000 in W.charge ancestor 123456;
  let owner,pending=checked ~parent:ancestor original candidate limits in
  let report=Check.pending_report ~scope:owner pending in
  require (Json.equal report (Check.report standalone))
    "Scoped assessment changed standalone evidence or counted unrelated parent usage as owned work";
  require (match Check.pending_selected_material ~scope:owner pending with Some ("short",_) -> true | _ -> false)
    "Scoped preparation lacks the freshly checked short child";
  require (Check.equal_json owner (obj ["b",Json.int 2;"a",Json.int 1]) (obj ["a",Json.int 1;"b",Json.int 2]))
    "Metered equality changed canonical object semantics";
  let literal=obj ["retained",arr [str "A";Json.int 17]] in
  require (Check.encode_json owner literal=Canonical.encode literal &&
    Check.fingerprint owner literal=Canonical.fingerprint literal) "Metered encoding or hashing changed exact bytes";
  let result=obj ["report",report] in
  let protocol_request=envelope (obj ["request",original;"candidate",candidate;"limits",limits]) in
  let finalize=Check.prepare_response ~scope:owner pending ~executable:Protocol.Verify ~protocol_request ~result in
  finalize (frame Protocol.Verify protocol_request result);
  let first=failure "policy_component_selection_scope" "A prepared response can finalize only once"
    (fun () -> finalize (frame Protocol.Verify protocol_request result)) in
  same_failure first "No charging after finalization misuse" (fun () -> Check.charge_outer owner 0)

let lifecycle original candidate limits=
  let owner,pending=checked original candidate limits in
  let other=scope original in
  let first=failure "policy_component_selection_scope" "Identical originals do not permit pending transfer across owners"
    (fun () -> Check.pending_report ~scope:other pending) in
  same_failure first "Foreign pending misuse poisons recipient scope" (fun () -> Check.charge_outer other 0);
  require (get "selected_id" (Check.pending_report ~scope:owner pending)=str "short")
    "Foreign-scope misuse changed the original pending owner";
  let request=R.of_json original in
  ignore (failure "policy_component_selection_scope" "A scope may evaluate its complete census only once"
    (fun () -> Check.check_in ~scope:owner ~candidate:(V.of_json ~request candidate) ~limits:(P.limits_of_json limits)));
  let owner=scope original in
  let changed=R.of_json (put ["predicate";"max_total_nt"] (Json.int 18) original) in
  ignore (failure "policy_component_selection_identity" "Complete original fingerprint is fixed at scope creation"
    (fun () -> Check.check_in ~scope:owner ~candidate:(V.of_json ~request:changed candidate) ~limits:(P.limits_of_json limits)));
  let owner,pending=checked original candidate limits in
  let result=obj ["report",Check.pending_report ~scope:owner pending] in
  let protocol_request=envelope result in
  let finalize=Check.prepare_response ~scope:owner pending ~executable:Protocol.Verify ~protocol_request ~result in
  let first=failure "policy_component_selection_scope" "Preparing a frame seals all subsequent preparation access"
    (fun () -> Check.pending_selected_material ~scope:owner pending) in
  same_failure first "Invalid Ready-phase access cannot be repaired by finalization"
    (fun () -> finalize (frame Protocol.Verify protocol_request result))

let frame_controls original candidate limits=
  List.iter (fun (label,mutate) ->
    let owner,pending=checked original candidate limits in
    let result=obj ["report",Check.pending_report ~scope:owner pending] in
    let protocol_request=envelope result in
    let finalize=Check.prepare_response ~scope:owner pending ~executable:Protocol.Verify ~protocol_request ~result in
    let actual=frame Protocol.Verify protocol_request result in
    let first=failure "policy_component_selection_identity" ("Actual full protocol identity: "^label)
      (fun () -> finalize (mutate actual)) in
    same_failure first "Changed frame cannot retry with its captured correct frame" (fun () -> finalize actual)) [
      "request ID",replace "request_id" (str "foreign");
      "operation",replace "operation" (str "export-policy-component-selection");
      "executable",put ["core";"executable"] (str "core");
      "protocol",replace "protocol" (str "foreign");
      "status",replace "status" (str "unsupported");
      "diagnostics",replace "diagnostics" (arr [obj ["code",str "foreign";"message",str "foreign";"path",Json.Null]]);
      "result",put ["result";"report";"selected_id"] (str "long")];
  (* The result is actually reserved on each live owner. A small complete frame
     still fits; replacing only its request ID by a valid one-million-byte name
     exceeds the same cumulative cap. No estimated result-only wrapper is used. *)
  let bounded=put ["budgets";"max_report_bytes"] (Json.int 2000000) original in
  let small_owner,small_pending=checked bounded candidate limits in
  let small_result=obj ["report",Check.pending_report ~scope:small_owner small_pending] in
  Check.reserve_publication small_owner small_result;
  let small_request=envelope small_result in
  let small_finalize=Check.prepare_response ~scope:small_owner small_pending ~executable:Protocol.Verify
    ~protocol_request:small_request ~result:small_result in
  small_finalize (frame Protocol.Verify small_request small_result);
  let owner,pending=checked bounded candidate limits in
  let result=obj ["report",Check.pending_report ~scope:owner pending] in
  require (String.length (Canonical.encode result)<2000000) "Result-only frame control exceeds its individual ceiling";
  Check.reserve_publication owner result;
  let protocol_request=envelope ~id:(String.make 1000000 'r') result in
  let finalize=Check.prepare_response ~scope:owner pending ~executable:Protocol.Verify ~protocol_request ~result in
  ignore (failure "policy_component_selection_publication_limit" "The actual protocol frame exceeds a fitting result-only value"
    (fun () -> finalize (frame Protocol.Verify protocol_request result)));
  let explicit=original
    |> put ["budgets";"profile"] (str "biocompiler.policy_component_selection_resources.v0.2")
    |> put ["budgets";"max_report_nodes"] (Json.int 1000000) in
  let owner,pending=checked explicit candidate limits in
  let result=arr (List.init 249980 (fun _ -> Json.Null)) in
  (* 249,981 result nodes fit, but the real protocol identity adds 22 more.
     The explicit cumulative million-node budget cannot enlarge this frame. *)
  Check.reserve_publication owner result;
  let protocol_request=envelope Json.Null in
  let first=failure "policy_material_input_limit" "The complete actual frame keeps its independent 250,000-node bound"
    (fun () -> Check.prepare_response ~scope:owner pending ~executable:Protocol.Verify ~protocol_request ~result) in
  same_failure first "Frame preflight failure cannot revive the scope" (fun () -> Check.charge_outer owner 0)

let ()=
  try
    require (Array.length Sys.argv=2) "Supply the independent A original fixture";
    let fixture=read Sys.argv.(1) in
    let original=Originals.selection_literal fixture and limits=get "limits" fixture in
    let candidate=proposed original limits in
    isolated_guards original;cumulative_profile original;positive original candidate limits;lifecycle original candidate limits;
    frame_controls original candidate limits;
    Printf.printf "component selection scope: %d independent ownership/work/publication controls passed\n" !checks
  with Diagnostic.Error value ->
    Printf.eprintf "Diagnostic.Error(code=%s,path=%s,message=%s)\n" value.code
      (Option.value ~default:"<none>" value.path) value.message;exit 1

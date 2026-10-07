open Bioc_wire
open Bioc_policy_component_test_support.Literals
module Originals=Bioc_policy_component_test_support.Selection_requests
module Requests=Bioc_policy_component_test_support.Requests
module R=Bioc_domain.Policy_component_selection_request
module S=Bioc_service.Policy_component_selection_service
module Service=Bioc_service.Service
module Producer=Bioc_producer_service.Policy_component_material_producer

(* Producers supply only candidate SUBJECTS. Both RNA strings, the unchanged
   A program, original requirements and complete expected manifest are declared
   independently below. The long alternative never borrows the B policy. *)
let short_rna="CCAUGGCUUAAGGAAAA"
let long_rna="CGCAUGGCUUAAGGAAAA"
let resource_v2="biocompiler.policy_component_selection_resources.v0.2"
let publication_original original=original
  |> put ["budgets";"profile"] (str resource_v2)
  |> put ["budgets";"max_report_nodes"] (Json.int 1000000)
let row id value=List.find (fun item -> get "id" item=str id) (items "alternatives" value)
let change_row id transform=edit ["alternatives"] (fun rows -> arr (List.map (fun value ->
  if get "id" value=str id then transform value else value) (Json.array rows)))
let reverse=edit ["alternatives"] (fun rows -> arr (List.rev (Json.array rows)))
let payload original candidate limits=obj ["request",original;"candidate",candidate;"limits",limits]
let proposed original limits=obj ["schema_version",str "biocompiler.policy_component_selection_candidate.v0.1";
  "alternatives",arr (List.map (fun item ->
    let produced=Producer.compile (obj ["request",get "request" item;"limits",limits]) in
    obj ["id",get "id" item;"candidate",get "candidate" produced]) (items "alternatives" original));
  "selected_id",str "short"]
let protocol ?(id="literal.selection.service") operation payload:Protocol.request=
  {request_id=id;operation;payload}
let actual_frame role request (reply:Service.scoped_reply)=Protocol.response ~executable:role ~request:(Some request)
  ~status:reply.status ~result:reply.result reply.diagnostics
let call role operation input=
  let request=protocol operation input in
  match Service.scoped_handle role request with
  | Some reply ->
      let actual=actual_frame role request reply in
      reply.before_encode actual;
      require (reply.status=Protocol.Ok && reply.diagnostics=[])
        "Fresh selection route returned an invalid success shape";
      (match reply.result with Some result -> result | None -> failwith "Selection lacks result")
  | None -> failwith ("Selection route fell through: "^operation)
let check=call Protocol.Verify "check-policy-component-selection"
let export=call Protocol.Verify "export-policy-component-selection"
let replay saved input=call Protocol.Verify "replay-policy-component-selection" (add "report" saved input)

let independent_molecule is_long=
  let offset,length,sequence=if is_long then 3,18,long_rna else 2,17,short_rna in
  let frame="payload.frame" and provenance=M.Provenance.of_json provenance in
  N.make ~id:"payload" ~form:N.Delivered_rna ~space:(G.Space.of_json (space frame length))
    ~sequence ~sequence_extent:H.Complete ~coding_status:N.Coding
    ~assembly:[N.Assembly_origin.make ~id:"payload.origin"
      ~destination:(G.Path.of_json (path frame 0 length))
      ~source_space:(G.Space.of_json (space "join.frame" length))
      ~source_path:(G.Path.of_json (path "join.frame" 0 length)) ~provenance]
    ~features:(List.map N.Feature.of_json [feature frame "cds" "coding_sequence" offset (offset+9) (Json.int 0);
      feature frame "poly_a" "poly_a_tail" (offset+11) length Json.Null;
      feature frame "utr3" "three_prime_utr" (offset+9) (offset+11) Json.Null;
      feature frame "utr5" "five_prime_utr" 0 offset Json.Null])
    ~chemistry:(H.of_json (chemistry frame true |> put ["terminal_tail";"path"] (path frame (offset+11) length)))
    ~provenance

let complete_child fixture report id sequence eligible=
  let item=row id report in
  require (get "total_nt" item=Json.int (String.length sequence) &&
    get "sequence_sha256" item=str (Canonical.sha256 sequence) && get "eligible" item=Json.Bool eligible)
    "Service eligibility did not come from the literal child's exact RNA";
  let inner=get "inner" item in
  require (get "status" inner=str "checked_component_material" &&
    get "all_original_obligations_discharged" inner=Json.Bool true &&
    List.length (items "obligations" inner)=23 &&
    List.map (get "obligation") (items "obligations" inner)=items "obligations" (get "expected" fixture) &&
    List.for_all (fun obligation -> get "status" obligation=str "discharged") (items "obligations" inner))
    "A losing or winning child lost complete original obligation evidence";
  let preservation=get "preservation" inner in
  List.iter (fun (key,count) -> require (at ["coverage";key] preservation=Json.int count)
    ("Service omitted original domain coverage: "^key))
    ["histories",9;"transitions",47;"prefixes_started",48;"matched_prefixes",48];
  require (at ["coverage";"complete"] preservation=Json.Bool true &&
    List.map (get "id") (items "requirements" preservation)=
      List.map str ["request_progress";"initiation_progress";"exclusive_selection"] &&
    List.for_all (fun requirement -> get "status" requirement=str "pass" &&
      at ["histories";"pass"] requirement=Json.int 9) (items "requirements" preservation))
    "Complete original requirements were weakened at the public boundary"

let assert_export original candidate limits winner is_long result=
  let report=get "report" result and molecule=independent_molecule is_long in
  let sequence=if is_long then long_rna else short_rna in
  let fasta=">rna_0001 alphabet=RNA\n"^sequence^"\n" in
  let original_child=get "request" (row winner original) and proposed_child=get "candidate" (row winner candidate) in
  let inner=get "inner" (row winner report) in
  let manifest=obj ["schema_version",str "biocompiler.policy_component_selection_mrna_manifest.v0.1";
    "profile",str "biocompiler.policy_component_material_selection.v0.1";
    "claim_scope",str "bounded_complete_supplied_catalog_selection_to_exact_mrna";
    "premise",str "supplied_component_composition_and_provider_contracts";
    "request",original;"candidate",candidate;"limits",limits;"assessment",report;
    "bindings",obj ["request_fingerprint",str (Canonical.fingerprint original);
      "candidate_fingerprint",str (Canonical.fingerprint candidate);
      "invocation_fingerprint",str (Canonical.fingerprint (payload original candidate limits));
      "assessment_fingerprint",str (Canonical.fingerprint report)];
    "selected",obj ["id",str winner;"request_fingerprint",str (Canonical.fingerprint original_child);
      "candidate_fingerprint",str (Canonical.fingerprint proposed_child);
      "assessment_fingerprint",str (Canonical.fingerprint inner)];
    "members",arr [obj ["fasta_id",str "rna_0001";"member_id",str "payload";"molecule",N.to_json molecule;
      "sequence_sha256",str (Canonical.sha256 sequence)]];
    "fasta_sha256",str (Canonical.sha256 fasta);"empirical",str "unassessed";
    "original_authority",str "retain_original_inputs_separately"] in
  let artifact=obj ["schema_version",str "biocompiler.policy_component_selection_mrna_export.v0.1";
    "fasta",str fasta;"fasta_sha256",str (Canonical.sha256 fasta);"manifest",manifest;
    "manifest_sha256",str (Canonical.sha256 (Canonical.encode manifest))] in
  require (Json.equal (get "artifact" result) artifact)
    "Fresh outer artifact differs from the independently declared RNA/geometry, full losing authority, or exact paired hashes";
  require (get "resource_profile" result=at ["budgets";"profile"] original &&
    get "resource_profile" report=at ["budgets";"profile"] original)
    "The service silently changed the original publication resource version"

let positives fixture original candidate limits=
  let input=payload original candidate limits in
  let checked=check input in
  require (get "artifact" checked=Json.Null && at ["report";"status"] checked=str "checked_selection" &&
    at ["report";"selected_id"] checked=str "short") "Fresh check exported prematurely or changed the winner";
  require (Json.equal checked (call Protocol.Core "check-policy-component-selection" input) &&
    Json.equal checked (replay checked input) &&
    Json.equal checked (call Protocol.Core "replay-policy-component-selection" (add "report" checked input)))
    "Core/Verify or fresh complete replay changed the selection result";
  complete_child fixture (get "report" checked) "short" short_rna true;
  complete_child fixture (get "report" checked) "long" long_rna false;
  let exported=export input in
  require (Json.equal exported (call Protocol.Core "export-policy-component-selection" input) &&
    Json.equal (get "report" exported) (get "report" checked)) "Fresh Core/Verify export changed the checked conjunction";
  assert_export original candidate limits "short" false exported;
  let eighteen=put ["predicate";"max_total_nt"] (Json.int 18) original in
  let long=replace "selected_id" (str "long") candidate in
  let longer=export (payload eighteen long limits) in
  assert_export eighteen long limits "long" true longer;
  complete_child fixture (get "report" longer) "short" short_rna true;
  complete_child fixture (get "report" longer) "long" long_rna true;
  let sixteen=put ["predicate";"max_total_nt"] (Json.int 16) original in
  let none=replace "selected_id" Json.Null candidate in
  let empty=check (payload sixteen none limits) in
  require (at ["report";"status"] empty=str "no_eligible_alternative" &&
    at ["report";"census_complete"] empty=Json.Bool true && at ["report";"all_inner_accepted"] empty=Json.Bool true &&
    at ["report";"selected_id"] empty=Json.Null && get "artifact" empty=Json.Null)
    "Complete finite no-selection became acceptance or incomplete search";
  complete_child fixture (get "report" empty) "short" short_rna false;
  complete_child fixture (get "report" empty) "long" long_rna false;
  rejected "policy_component_selection_export_not_accepted" "No eligible member cannot produce RNA"
    (fun () -> export (payload sixteen none limits));
  checked,exported

let stale_controls original candidate limits checked exported=
  let input=payload original candidate limits in
  List.iter (fun saved -> rejected "policy_component_selection_replay" "Every saved wrapper field is fresh evidence"
    (fun () -> replay saved input))
    [exported;get "report" checked;replace "implementation" (str "foreign") checked;
     put ["report";"alternatives";"0";"inner";"empirical"] (str "validated") checked;
     replace "artifact" (obj ["accepted",Json.Bool true]) checked];
  rejected "unknown_field" "Fresh export never imports serialized acceptance"
    (fun () -> export (add "report" checked input));
  List.iter (fun (changed,proposed) ->
    let input=payload changed proposed limits in
    let fresh=export input in
    require (at ["artifact";"fasta"] fresh=at ["artifact";"fasta"] exported &&
      at ["artifact";"manifest_sha256"] fresh<>at ["artifact";"manifest_sha256"] exported)
      "Unchanged winning RNA erased changed complete selection authority";
    assert_export changed proposed limits "short" false fresh;
    rejected "policy_component_selection_replay" "Rank, predicate and original/candidate order cannot reuse old evidence"
      (fun () -> replay checked input)) [
        change_row "long" (replace "rank" (Json.int 2)) original,candidate;
        put ["predicate";"max_total_nt"] (Json.int 19)
          (change_row "short" (replace "rank" (Json.int 0))
            (change_row "long" (replace "rank" (Json.int 1)) original)),candidate;
        reverse original,candidate;original,reverse candidate]

(* Independently change one losing material premise, then re-pin its declared
   references. No producer/checker decides what changed or supplies expectations. *)
let changed_loser original=
  change_row "long" (edit ["request"] (fun request ->
    let decision=at ["component_library";"components";"0"] request
      |> put ["body";"root";"molecule";"sequence"] (str "GGC") |> repin in
    let root=at ["body";"root"] decision in
    let rule=get "composition_rule" request
      |> put ["body";"components";"0";"component"] (get "identity" decision)
      |> edit ["body";"material_authority";"template";"sources"] (fun sources -> arr (List.map (fun source ->
        if get "id" source=str "leader_A" then root else source) (Json.array sources))) |> repin in
    let identity=get "identity" rule in
    request |> put ["component_library";"components";"0"] decision
      |> replace "composition_rule" rule
      |> put ["catalog_binding";"components"] (at ["body";"components"] rule)
      |> put ["catalog_binding";"rule"] identity
      |> edit ["context"] (fun context -> context |> put ["record_layout";"rule"] identity
        |> Requests.refresh_layout_pins))) original

let losing_controls fixture original candidate limits checked exported=
  let changed=changed_loser original in
  let fresh_candidate=proposed changed limits in
  let fresh=export (payload changed fresh_candidate limits) in
  require (at ["artifact";"fasta"] fresh=at ["artifact";"fasta"] exported &&
    at ["artifact";"manifest_sha256"] fresh<>at ["artifact";"manifest_sha256"] exported)
    "Changing an ineligible losing material failed to bind the fresh complete manifest";
  complete_child fixture (get "report" fresh) "long" "GGCAUGGCUUAAGGAAAA" false;
  assert_export changed fresh_candidate limits "short" false fresh;
  rejected "policy_component_selection_replay" "A changed losing original cannot borrow prior selection evidence"
    (fun () -> replay checked (payload changed fresh_candidate limits));
  let invalid=change_row "long" (edit ["candidate"] (fun child ->
    let child=put ["construction";"inventory";"molecules";"0";"sequence"] (str "AGCAUGGCUUAAGGAAAA") child in
    put ["construction";"inventory";"role_instances";"0";"subject_fingerprint"]
      (str (Canonical.fingerprint (at ["construction";"inventory";"molecules";"0"] child))) child)) candidate in
  let rejected_loser=check (payload original invalid limits) in
  require (at ["report";"status"] rejected_loser=str "inner_not_accepted" &&
    at ["report";"all_inner_accepted"] rejected_loser=Json.Bool false && get "artifact" rejected_loser=Json.Null)
    "An invalid ineligible child was silently discarded";
  rejected "policy_component_selection_export_not_accepted" "All losing candidates must independently pass"
    (fun () -> export (payload original invalid limits));
  let wrong_feedback=change_row "long" (edit ["candidate"]
    (put ["binding";"effects";"0";"feedback"] (str "wrong_feedback"))) candidate in
  rejected "policy_implementation_source_binding" "Wrong feedback on an ineligible loser blocks the entire export"
    (fun () -> export (payload original wrong_feedback limits));
  List.iter (fun selected ->
    let wrong=replace "selected_id" selected candidate in
    require (at ["report";"status"] (check (payload original wrong limits))=str "proposed_winner_mismatch")
      "Wrong/null proposed winner became fresh acceptance";
    rejected "policy_component_selection_export_not_accepted" "Proposed winner is never export authority"
      (fun () -> export (payload original wrong limits))) [str "long";Json.Null];
  rejected "policy_component_selection_candidate" "Complete losing-candidate census is mandatory"
    (fun () -> check (payload original (replace "alternatives" (arr [row "short" candidate]) candidate) limits))

let publication_controls original_v1 original candidate limits=
  require (R.resources (R.of_json original_v1)="biocompiler.policy_component_selection_resources.v0.1" &&
    (R.budgets (R.of_json original_v1)).max_report_nodes=249968)
    "The old original publication allowance was silently upgraded";
  rejected "policy_component_selection_request" "Old resource version cannot claim the new cumulative ceiling"
    (fun () -> R.of_json (put ["budgets";"max_report_nodes"] (Json.int 1000000) original_v1));
  rejected "policy_component_selection_request" "New cumulative ceiling remains finite"
    (fun () -> R.of_json (put ["budgets";"max_report_nodes"] (Json.int 1000001) original));
  let old_checked=check (payload original_v1 candidate limits) in
  require (get "resource_profile" old_checked=str "biocompiler.policy_component_selection_resources.v0.1")
    "Old check lost its exact resource version";
  let late limited=
    let request=protocol "export-policy-component-selection" (payload limited candidate limits) in
    let prepared,before_encode=S.prepare ~executable:Protocol.Verify ~request in
    let frame=Protocol.response ~executable:Protocol.Verify ~request:(Some request)
      ~status:Protocol.Ok ~result:(Some prepared) [] in
    require (String.length (Canonical.encode frame)<3000000)
      "Late cumulative control's individual frame exceeds the smallest supplied byte ceiling";
    rejected "policy_component_selection_publication_limit" "Individually fitting final frame exceeds cumulative publication"
      (fun () -> before_encode frame);
    rejected "policy_component_selection_publication_limit" "Failed publication cannot resume with the same complete frame"
      (fun () -> before_encode frame)
  in
  late original_v1;
  late (put ["budgets";"max_report_bytes"] (Json.int 3000000) original)

let modes_variable="BIOCOMPILER_SELECTION_SERVICE_TEST_MODE"
let child_mode mode=
  let role=if mode="core" then Protocol.Core else Protocol.Verify in
  if mode="core" || mode="verify" then Service.run ~handler:Service.handle role
  else (
    let count=ref 0 in
    let scoped _ (request:Protocol.request)=
      require (request.operation="literal-selection-guard") "Unexpected injected-runner operation";
      let before_encode actual=
        incr count;require (!count=1) "Runner invoked a success hook twice";
        require (get "request_id" actual=str request.request_id && get "operation" actual=str request.operation &&
          at ["core";"executable"] actual=str "verify" && get "status" actual=str "ok")
          "Runner hook received an approximate result instead of the actual protocol frame";
        match mode with
        | "guard-success" -> ()
        | "guard-diagnostic" -> Diagnostic.fail "literal_guard_failure" "No artifact may be published."
        | "guard-oversize" -> Diagnostic.fail "literal_guard_failure" (String.make (Limits.max_string_bytes+1) 'x')
        | "guard-invalid-utf8" -> Diagnostic.fail "literal_guard_failure" "\255"
        | "guard-resource" -> raise Out_of_memory
        | "guard-internal" -> failwith "literal injected guard failure"
        | _ -> failwith "Unknown closed runner test mode" in
      Some {Service.status=Protocol.Ok;result=Some (obj ["unpublished_sentinel",Json.Bool true]);
        diagnostics=[];before_encode} in
    Service.run ~scoped_handler:scoped Protocol.Verify)

(* Hosted-only subprocess controls run this same test executable with no argv,
   a closed test-mode variable and bounded pipes. No shell, runtime discovery,
   package install, environment dump or unbounded captured output is involved. *)
let run_process mode (request:Protocol.request)=
  let raw=Canonical.encode (obj ["protocol",str Protocol.version;"request_id",str request.request_id;
    "operation",str request.operation;"payload",request.payload]) in
  require (String.length raw<Limits.max_request_bytes) "Runner test input exceeds the exact wire cap";
  let prefix=modes_variable^"=" in
  let environment=Array.of_list ((prefix^mode)::(Array.to_list (Unix.environment ())
    |> List.filter (fun value -> not (String.starts_with ~prefix value)))) in
  let input_read,input_write=Unix.pipe () and output_read,output_write=Unix.pipe ()
    and error_read,error_write=Unix.pipe () in
  List.iter Unix.set_close_on_exec [input_read;input_write;output_read;output_write;error_read;error_write];
  let pid=Unix.create_process_env Sys.executable_name [|Sys.executable_name|] environment input_read output_write error_write in
  let close fd=try Unix.close fd with Unix.Unix_error _ -> () in
  List.iter close [input_read;output_write;error_write];
  List.iter Unix.set_nonblock [input_write;output_read;error_read];
  let output=Buffer.create 4096 and errors=Buffer.create 256 and chunk=Bytes.create 65536 in
  let position=ref 0 and input_open=ref true and output_open=ref true and error_open=ref true in
  let deadline=Unix.gettimeofday ()+.120. in
  let status=ref None in
  let cleanup ()=
    List.iter close [input_write;output_read;error_read];
    if Option.is_none !status then (try Unix.kill pid Sys.sigkill with Unix.Unix_error _ -> ());
    if Option.is_none !status then (try ignore (Unix.waitpid [] pid) with Unix.Unix_error _ -> ()) in
  Fun.protect ~finally:cleanup (fun () ->
    while !input_open || !output_open || !error_open || Option.is_none !status do
      if Unix.gettimeofday ()>=deadline then failwith "Hosted runner subprocess exceeded its bounded timeout";
      let readable=(if !output_open then [output_read] else [])@(if !error_open then [error_read] else []) in
      let writable=if !input_open then [input_write] else [] in
      let ready,write_ready,_=Unix.select readable writable [] 0.1 in
      if List.mem input_write write_ready then (
        let count=Unix.write_substring input_write raw !position (min 65536 (String.length raw- !position)) in
        position:= !position+count;
        if !position=String.length raw then (close input_write;input_open:=false));
      List.iter (fun (fd,active,buffer,maximum) -> if List.mem fd ready then
        let count=Unix.read fd chunk 0 (Bytes.length chunk) in
        if count=0 then (close fd;active:=false) else (
          if Buffer.length buffer+count>maximum then failwith "Hosted runner exceeded a captured-output bound";
          Buffer.add_subbytes buffer chunk 0 count))
        [output_read,output_open,output,Limits.max_response_bytes;error_read,error_open,errors,65536];
      if Option.is_none !status then (match Unix.waitpid [Unix.WNOHANG] pid with
        | 0,_ -> () | _,value -> status:=Some value)
    done;
    let bytes=Buffer.contents output in
    require (String.length bytes>1 && bytes.[String.length bytes-1]='\n' &&
      List.length (String.split_on_char '\n' bytes)=2) "Runner emitted partial, repeated or unframed JSON";
    Option.get !status,Json.parse (String.sub bytes 0 (String.length bytes-1)))

let runner_controls original candidate limits=
  let literal=protocol "literal-selection-guard" (obj []) in
  List.iter (fun (mode,code) ->
    let status,response=run_process mode literal in
    require (status=Unix.WEXITED 2 && get "status" response=str "error" && get "result" response=Json.Null &&
      List.map (get "code") (items "diagnostics" response)=[str code])
      "A failing success hook emitted an artifact, escaped error bounds, or changed its diagnostic")
    ["guard-diagnostic","literal_guard_failure";"guard-oversize","internal_error";
     "guard-invalid-utf8","internal_error";"guard-resource","resource_exhausted";"guard-internal","internal_error"];
  let status,response=run_process "guard-success" literal in
  require (status=Unix.WEXITED 0 && at ["result";"unpublished_sentinel"] response=Json.Bool true)
    "Valid actual-frame callback was not run once before success";
  let input=payload original candidate limits in
  let status,response=run_process "verify" (protocol "export-policy-component-selection" input) in
  require (status=Unix.WEXITED 0 && get "status" response=str "ok" &&
    at ["core";"executable"] response=str "verify") "Actual Verify scoped runner could not export";
  assert_export original candidate limits "short" false (get "result" response);
  let status,response=run_process "core" (protocol "check-policy-component-selection" input) in
  require (status=Unix.WEXITED 0 && at ["core";"executable"] response=str "core" &&
    at ["result";"report";"selected_id"] response=str "short" && at ["result";"artifact"] response=Json.Null)
    "Actual Core scoped runner bypassed the fresh non-export selection path";
  let limited=put ["budgets";"max_report_bytes"] (Json.int 3000000) original in
  let status,response=run_process "verify" (protocol "export-policy-component-selection" (payload limited candidate limits)) in
  require (status=Unix.WEXITED 2 && get "result" response=Json.Null &&
    List.map (get "code") (items "diagnostics" response)=[str "policy_component_selection_publication_limit"])
    "Late cumulative publication failure leaked a prepared artifact through stdout";
  let status,response=run_process "verify" (protocol "canonicalize" (obj ["b",Json.int 2;"a",Json.int 1])) in
  require (status=Unix.WEXITED 0 && at ["result";"canonical_json"] response=str "{\"a\":1,\"b\":2}")
    "Optional scoped dispatch changed an existing legacy route"

let route_controls ()=
  require (S.operations=["check-policy-component-selection";"replay-policy-component-selection";"export-policy-component-selection"])
    "A generation route was advertised without metered producer support";
  List.iter (fun role ->
    let status,result,_=Service.handle role (protocol "capabilities" (obj [])) in
    let capabilities=Option.get result in
    require (status=Protocol.Ok && not (List.mem (str "compile-policy-component-selection") (items "operations" capabilities)) &&
      Json.equal (at ["profiles";"policy_component_selection"] capabilities) S.profile)
      "Core/Verify capabilities lost the checked selection profile boundary";
    require (Service.scoped_handle role (protocol "canonicalize" (obj []))=None)
      "Scoped selection dispatch swallowed an unrelated legacy route";
    let status,result,diagnostics=Service.handle role (protocol "compile-policy-component-selection" (obj [])) in
    require (status=Protocol.Unsupported && result=None && List.map (fun (d:Diagnostic.t) -> d.code) diagnostics=["unsupported_operation"])
      "Unsupported selection generation became a success or fallback";
    let status,result,_=Service.handle role (protocol "check-policy-component-selection" (obj [])) in
    require (status=Protocol.Unsupported && result=None)
      "The unguarded legacy handler bypassed actual-frame admission for selection";
    rejected "missing_field" "Malformed recognized selection must not fall through"
      (fun () -> Service.scoped_handle role (protocol "check-policy-component-selection" (obj [])))) [Protocol.Core;Protocol.Verify]

let ()=
  match Sys.getenv_opt modes_variable with
  | Some mode -> child_mode mode
  | None -> try
      require (Array.length Sys.argv=2) "Supply the independent A original fixture";
      let fixture=read Sys.argv.(1) in
      let original_v1=Originals.selection_literal fixture and limits=get "limits" fixture in
      let original=publication_original original_v1 in
      let candidate=proposed original limits in
      route_controls ();
      let checked,exported=positives fixture original candidate limits in
      stale_controls original candidate limits checked exported;
      losing_controls fixture original candidate limits checked exported;
      publication_controls original_v1 original candidate limits;
      runner_controls original candidate limits;
      Printf.printf "component selection service: %d independent service/manifest/actual-frame controls passed\n" !checks
    with Diagnostic.Error value ->
      Printf.eprintf "Diagnostic.Error(code=%s,path=%s,message=%s)\n" value.code
        (Option.value ~default:"<none>" value.path) value.message;exit 1

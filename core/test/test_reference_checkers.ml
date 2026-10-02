open Bioc_wire
open Bioc_domain
open Bioc_checker
module C=Reference_construct
module Q=Reference_molecular
module E=Reference_construct_evidence
module N=Reference_molecular_evidence
module Check=Reference_construct_check
module Molecular=Reference_molecular_check
let require condition message=if not condition then failwith message
let load directory identity=
  let path=Filename.concat directory(identity^".json") in
  let channel=open_in_bin path in
  let raw=Fun.protect ~finally:(fun()->close_in channel)(fun()->really_input_string channel(in_channel_length channel)) in
  let value=Json.parse_artifact ~max_bytes:Limits.max_request_bytes ~max_nodes:Limits.max_json_nodes raw in
  require(Canonical.fingerprint value=identity)"Focused checker authority changed";value
let changed key value raw=Json.Object(List.map(fun(name,old)->name,if name=key then value else old)(Json.object_fields raw))
let resource run=try ignore(run());failwith "Expected bounded resource rejection" with
  |Diagnostic.Error error->
    require (List.mem error.code ["reference_check_work_limit";"reference_check_item_limit";"reference_check_report_limit";
      "verification_exploration_limit";"composition_work_limit";"composition_input_limit";"composition_report_limit";
      "composition_item_limit";"reference_construct_limit";"reference_molecular_limit"])
      ("Resource failure was changed into a semantic outcome: "^error.code)
let parent maximum=Work_budget.create ~profile:"focused.reference.ancestor" ~error_code:"focused_reference_work_limit" ~maximum ()
let shared_work run=
  let maximum=50_000_000 in let ancestor=parent maximum in
  ignore(run ancestor);let consumed=maximum-Work_budget.remaining ancestor in
  require(consumed>1)"Checker work was not charged to its parent";
  let exact=parent consumed in ignore(run exact);require(Work_budget.remaining exact=0)"Work accounting is not deterministic";
  let short=parent(consumed-1) in
  (try ignore(run short);failwith "One-short parent budget accepted" with Diagnostic.Error error->
    require(error.code="focused_reference_work_limit" && Work_budget.is_exhaustion short error)
      "Nested work exhaustion was caught as a semantic diagnostic");
  require(Work_budget.exhausted short)"Ancestor exhaustion did not remain observable"
let ()=
  require(Array.length Sys.argv=2)"Expected frozen reference-contract document directory";
  let load=load Sys.argv.(1) in
  (* Complete original caller inputs, not accepted output records or reports. *)
  let request=C.Request.of_json(load "6260b3a9fac1f1df4a7941ee60bfe9672fd73e1be66ded1c0f46d9ddd9880f1f") in
  let construct=C.Candidate.of_json(load "783a33d2e9628e3ce06c4ecc3bb2535d2220e4a0edda11e0e54f65c7f1a682b1") in
  let candidate=Q.Artifact.of_json(load "33ebe83f86a62978d011d8f2e0f40655f2d214728bc8370ac6f3bf16b8c706cd") in
  let registry=Component_registry.of_json(load "15d4a9b57ec16b43ddc5297802ea974662ef5af54a4be17fd4f393fe008c49d9") in
  let manifests=Json.object_fields(load "f6119eba928e760f8201011028e007d9d46bdda0b599e946b0ea4f068663562b")
    |>List.map(fun(key,value)->key,Reference_manifest.of_json value) in
  let check ?parent ?limits ()=Check.check ?parent ?limits ~request ~candidate:construct ~registry ~manifests () in
  let molecular ?parent ?limits ()=Molecular.check ?parent ?limits ~request ~construct ~candidate ~registry ~manifests () in
  let result=check() and molecular_result=molecular() in
  require(E.Result.passed result && N.Result.passed molecular_result)"Original exact reference authority did not pass";
  require(List.length(N.Result.checks molecular_result)=4)"Independent comparisons were omitted";
  require(Check.replay ~request ~candidate:construct ~registry ~manifests result)"Complete construct report failed fresh replay";
  require(Molecular.replay ~request ~construct ~candidate ~registry ~manifests molecular_result)"Complete molecular report failed fresh replay";
  require(Realization_evidence.Freshness_report.fresh(Check.freshness ~request ~candidate:construct ~registry ~manifests result))
    "Unchanged construct authority was stale";
  let changed_construct=C.Candidate.of_json(changed "request_fingerprint"(Json.String(String.make 64 'b'))(C.Candidate.to_json construct)) in
  let rejected=Check.check ~request ~candidate:changed_construct ~registry ~manifests () in
  require(not(E.Result.passed rejected))"Changed request identity retained acceptance";
  require(List.map E.Diagnostic.code(E.Result.diagnostics rejected)=["request_identity"])"Construct mismatch diagnostic ordering changed";
  require(not(Check.replay ~request ~candidate:changed_construct ~registry ~manifests result))"Imported passing report conferred acceptance";
  let stale=Check.freshness ~request ~candidate:changed_construct ~registry ~manifests result in
  require(Realization_evidence.Freshness_report.changed_dependencies stale=["candidate"])"Freshness did not pin the entire candidate";
  let changed_candidate=Q.Artifact.of_json(changed "request_fingerprint"(Json.String(String.make 64 'b'))(Q.Artifact.to_json candidate)) in
  let rejected=Molecular.check ~request ~construct ~candidate:changed_candidate ~registry ~manifests () in
  require(not(N.Result.passed rejected) && List.length(N.Result.checks rejected)=4)"Molecular identity failure suppressed independent comparisons";
  require(not(Molecular.replay ~request ~construct ~candidate:changed_candidate ~registry ~manifests molecular_result))
    "Historical molecular acceptance was reused";
  let report=E.Result.to_json result in
  let forged=E.Result.of_json(changed "checked_requirement_ids"(Json.Array[Json.String "unproved"] )report) in
  require(not(Check.replay ~request ~candidate:construct ~registry ~manifests forged))"Replay compared only pass/fail";
  shared_work(fun parent->check ~parent());shared_work(fun parent->molecular ~parent());
  resource(fun()->check ~limits:(Check.make_limits ~max_work:1 ())());
  resource(fun()->check ~limits:(Check.make_limits ~max_input_bytes:1 ())());
  resource(fun()->check ~limits:(Check.make_limits ~max_items:1 ())());
  resource(fun()->check ~limits:(Check.make_limits ~max_report_bytes:1 ())());
  resource(fun()->molecular ~limits:(Molecular.make_limits ~max_work:1 ())());
  resource(fun()->molecular ~limits:(Molecular.make_limits ~max_input_bytes:1 ())());
  resource(fun()->molecular ~limits:(Molecular.make_limits ~max_report_nodes:1 ())());
  (* An extra caller manifest remains authority even when unused by selection. *)
  let key,manifest=List.hd manifests in
  let expanded=(key^".unused",manifest)::manifests in
  let stale=Molecular.freshness ~request ~construct ~candidate ~registry ~manifests:expanded molecular_result in
  require(Realization_evidence.Freshness_report.changed_dependencies stale=["references"])
    "Unused supplied authority disappeared from freshness";
  print_endline "Reference checkers: fresh authority, complete replay, diagnostic order and shared resource bounds passed."

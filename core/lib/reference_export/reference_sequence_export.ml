open Bioc_wire
open Bioc_domain
module B=Bioc_artifact.Archive_budget
module R=Reference_construct
module Q=Reference_molecular
module E=Reference_molecular_evidence
module C=Verification_exploration.Codec
module Check=Bioc_checker.Reference_molecular_check
module Construct_check=Bioc_checker.Reference_construct_check
module Composition_check=Bioc_checker.Composition_check
let field key value=Json.field key(Json.object_fields value)
let setting key raw=Z.to_int(Json.integer(field key raw))
let molecular_limits=Check.default_limits
let checker_limits()=
  let molecular=Check.limits_json molecular_limits in
  (* These are the actual closed argument-forwarding recipes in
     Reference_molecular_check.construct_limits and
     Reference_construct_check.request_checks. Do not use an unrelated child
     default or reduce an inner ceiling to fit an existing owner's resources. *)
  let construct_limits=Construct_check.make_limits
    ~max_work:(setting "max_work" molecular)
    ~max_items:(setting "max_retained_intermediate_items" molecular)
    ~max_input_bytes:(setting "max_input_bytes" molecular)
    ~max_report_bytes:(setting "max_report_bytes" molecular)
    ~max_report_nodes:(setting "max_report_nodes" molecular)() in
  let construct=Construct_check.limits_json construct_limits in
  let composition_limits=Composition_check.make_limits
    ~max_work:(setting "max_work" construct)
    ~max_items:(setting "max_retained_intermediate_items" construct)
    ~max_input_bytes:(setting "max_input_bytes" construct)
    ~max_report_bytes:(setting "max_report_bytes" construct)
    ~max_report_nodes:(setting "max_report_nodes" construct)() in
  ["molecular",molecular;"construct",construct;"composition",Composition_check.limits_json composition_limits]
let checker_limits_json()=Json.Object(checker_limits())
let checker_reservation_bytes()=
  (* Molecular->Construct->Composition each retains its own complete report and
     bounded intermediate inventory. These configured ceilings are unchanged.
     This is conservative cumulative accounting, with no refund after the call. *)
  List.fold_left(fun total(_,limits)->total+setting "max_report_bytes" limits+
    64*setting "max_report_nodes" limits+256*setting "max_retained_intermediate_items" limits)0(checker_limits())
let codec budget=let limits=B.limits budget in C.make_limits
  ~max_bytes:(min limits.max_member_bytes Limits.max_request_bytes)
  ~max_nodes:(min limits.max_json_nodes Limits.max_json_nodes) ~charge:(B.charge budget)()
let input budget raw=
  let size=C.measure ~limits:(codec budget) raw in
  let rec depth level value=B.charge budget 1;
    Diagnostic.require(level<=(B.limits budget).max_json_depth)"reference_export_depth_limit"
      "Reference export JSON exceeds its depth limit.";
    match value with Json.Array values->List.iter(depth(level+1))values
    |Json.Object values->List.iter(fun(_,value)->depth(level+1)value)values|_->() in
  depth 0 raw;
  B.reserve budget(size.bytes+64*size.nodes+128);size
let export budget ~request ~construct ~artifact ~registry ~manifests ~line_width ()=
  B.charge budget 1;
  Diagnostic.require(line_width>=1 && line_width<=10000)"reference_sequence_export"
    "FASTA line width must be an integer from 1 to 10000.";
  let target=R.Request.target request in
  let size=input budget(Build_request.Target.to_json target) in
  B.product budget(size.bytes+size.nodes+1)128;B.reserve budget(16*size.bytes+128*size.nodes+8192);
  ignore(Bioc_checker.Admission_check.require_software_use ~target ~boundary:Admission.Export ~components:[]);
  ignore(input budget(R.Request.to_json request));ignore(input budget(R.Candidate.to_json construct));
  ignore(input budget(Q.Artifact.to_json artifact));ignore(input budget(Component_registry.to_json registry));
  let rec authorities count=function []->()|(key,value)::rest->
    B.charge budget(String.length key+1);
    Diagnostic.require(count<(B.limits budget).max_json_nodes)"reference_export_collection_limit"
      "Reference export authority collection exceeds its node limit.";
    ignore(input budget(Json.Object[key,Reference_manifest.to_json value]));authorities(count+1)rest in
  authorities 0 manifests;
  B.reserve budget(checker_reservation_bytes());
  let checked=Check.check ~parent:(B.work budget) ~limits:molecular_limits ~request ~construct ~candidate:artifact ~registry ~manifests () in
  if not(E.Result.passed checked)then begin
    let codes=List.map(fun value->Json.string(field "code"(E.Diagnostic.to_json value)))(E.Result.diagnostics checked) in
    B.charge budget(E.Result.canonical_size checked+1);
    Diagnostic.fail "reference_sequence_export"
      ("Sequence export requires a currently passing independent molecular check: "^String.concat "; " codes)
  end;
  Reference_sequence_codec.encode budget ~line_width artifact

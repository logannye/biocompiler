open Bioc_wire
let ()=Printexc.register_printer(function
  |Diagnostic.Error value->Some(Printf.sprintf "Diagnostic.Error(code=%s, path=%s, message=%s)"
    value.code(Option.value ~default:"<none>" value.path)value.message)
  |_->None)
module S=Bioc_service.Policy_material_service
module Service=Bioc_service.Service
module Producer=Bioc_producer_service.Producer_service
let require condition message=if not condition then failwith message
let obj values=Json.Object values
let arr values=Json.Array values
let str value=Json.String value
let get key raw=Json.field key(Json.object_fields raw)
let text key raw=Json.string(get key raw)
let items key raw=Json.array(get key raw)
let set key value raw=obj((key,value)::List.remove_assoc key(Json.object_fields raw))
let rec at path raw=match path with []->raw|key::rest->at rest(match raw with
  |Json.Array values->List.nth values(int_of_string key)|_->get key raw)
let rec put path replacement raw=match path with []->replacement|key::rest->match raw with
  |Json.Array values->let index=int_of_string key in
      require(index>=0 && index<List.length values)"Mutation escaped literal array";
      arr(List.mapi(fun i value->if i=index then put rest replacement value else value)values)
  |_->set key(put rest replacement(get key raw))raw
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:4000000 ~max_nodes:100000(really_input_string channel(in_channel_length channel)))
let rejects label codes action=match action()with
  |_->failwith("Service accepted "^label)
  |exception Diagnostic.Error diagnostic->require(List.mem diagnostic.code codes)(label^": wrong diagnostic "^diagnostic.code)
let run handler role operation payload=
  let request:Protocol.request={request_id="material-literal";operation;payload}in
  match handler role request with
  |Protocol.Ok,Some result,[]->result
  |_->failwith("Registered material operation failed: "^operation)
let ()=
  require(Array.length Sys.argv=2)"Supply complete original material request fixture";
  let fixture=read Sys.argv.(1)in
  let request=get "request" fixture and limits=get "limits" fixture and expected=get "expected" fixture in
  let compile request=run Producer.handle Protocol.Core "compile-policy-material"(obj["request",request;"limits",limits])in
  let compiled=compile request in
  let candidate=get "candidate" compiled in
  let payload=obj["request",request;"candidate",candidate;"limits",limits]in
  let checked=run Service.handle Protocol.Verify "check-policy-material"payload in
  require(Json.equal checked compiled)"Generic producer and independent standalone material checker differ";
  require(Json.equal checked(run Producer.handle Protocol.Core "check-policy-material"payload))
    "Core and standalone material checkers changed fresh evidence";
  require(get "artifact" compiled=Json.Null)"Compilation published an unrequested artifact";
  let report=get "report" compiled in
  require(text "status" report="checked_material")("Material producer failed the fresh full conjunction: "^Canonical.encode report);
  require(text "request_fingerprint" compiled=Canonical.fingerprint request &&
    text "candidate_fingerprint" compiled=Canonical.fingerprint candidate &&
    text "invocation_fingerprint" compiled=Canonical.fingerprint payload &&
    text "report_fingerprint" compiled=Canonical.fingerprint report)"Wrapper omits complete original identities";
  List.iter(fun key->require(at["preservation";"coverage";key]report=get key expected)("Changed source-domain census "^key))
    ["histories";"transitions";"prefixes_started"];
  require(List.map(get "obligation")(items "obligations" report)=items "obligations" expected)
    "Producer dropped original obligations";
  let replay saved=run Service.handle Protocol.Verify "replay-policy-material"
    (set "report" saved payload)in
  require(Json.equal compiled(replay compiled))"Full wrapper replay changed exact fresh evidence";
  List.iter(fun(label,forged)->rejects label["policy_material_replay"](fun()->replay forged))[
    "inner report used as wrapper",report;
    "wrapper implementation",set "implementation"(str "foreign")compiled;
    "wrapper invocation",set "invocation_fingerprint"(str(String.make 64 '0'))compiled;
    "rehash changed evidence",(let changed=set "empirical"(str "validated")report in
      compiled|>set "report"changed|>set "report_fingerprint"(str(Canonical.fingerprint changed)));
    "forged artifact",set "artifact"(obj["status",str "pass"])compiled];
  let export=run Service.handle Protocol.Verify "export-policy-material"payload in
  require(Json.equal export(run Producer.handle Protocol.Core "export-policy-material"payload))
    "Core and standalone fresh material exports differ";
  require(Json.equal report(get "report" export))"Fresh export rewrote its underlying assessment";
  let artifact=get "artifact" export in
  let fasta=text "fasta" artifact and manifest=get "manifest" artifact in
  let expected_fasta=">rna_0001 alphabet=RNA\n"^text "sequence" expected^"\n"in
  require(fasta=expected_fasta)"Exported exact bases/order/header/newlines differ from independent literal";
  require(text "fasta_sha256" artifact=Canonical.sha256 fasta &&
    text "fasta_sha256" manifest=Canonical.sha256 fasta &&
    text "manifest_sha256" artifact=Canonical.sha256(Canonical.encode manifest))
    "Exact published pair lost its byte fingerprints";
  require(Json.equal(get "request" manifest)request && Json.equal(get "candidate" manifest)candidate &&
    Json.equal(get "limits" manifest)limits && Json.equal(get "assessment" manifest)report)
    "Manifest omitted an original authority, candidate, invocation or fresh assessment";
  require(List.map(get "molecule")(items "members" manifest)=items "molecules" expected)
    "Manifest lost exact molecular chemistry, coordinates, products or derivation";
  require(text "empirical" manifest="unassessed" && text "claim_scope" manifest="bounded_conditional_policy_to_exact_mrna" &&
    text "original_authority" manifest="retain_original_inputs_separately")"Export widened conditional claim or reused manifest as authority";
  let binding=get "bindings" manifest in
  require(text "assessment_fingerprint" binding=Canonical.fingerprint report &&
    get "request_fingerprint" binding=get "request_fingerprint" compiled &&
    get "candidate_fingerprint" binding=get "candidate_fingerprint" compiled &&
    get "invocation_fingerprint" binding=get "invocation_fingerprint" compiled)"Manifest bindings differ from checked originals";
  rejects "saved export wrapper used as check receipt"["policy_material_replay"](fun()->replay export);
  rejects "saved acceptance authority supplied to export"["unknown_field"](fun()->
    S.handle ~operation:"export-policy-material"(set "report" compiled payload));
  let altered_limits=put["monitor";"max_work"](Json.int 1)limits in
  let incomplete=S.check ~export:false ~request ~candidate ~limits:altered_limits in
  require(text "status"(get "report" incomplete)="not_accepted" && get "artifact" incomplete=Json.Null)
    "Insufficient fresh work inherited previous material acceptance";
  rejects "fresh export after budget edit"["policy_material_export_not_accepted"](fun()->
    S.check ~export:true ~request ~candidate ~limits:altered_limits);
  let mutated_material=put["construction";"inventory";"molecules";"0";"sequence"](str "GCAUGGCUUAAGGAAAA")candidate in
  let mutated_material=put["construction";"inventory";"role_instances";"0";"subject_fingerprint"]
    (str(Canonical.fingerprint(at["construction";"inventory";"molecules";"0"]mutated_material)))mutated_material in
  rejects "fresh export after material edit"["policy_material_export_not_accepted"](fun()->
    S.check ~export:true ~request ~candidate:mutated_material ~limits);
  let wrong_recipient=put["context";"recipient";"identity"](str "target-1")request in
  rejects "fresh export after recipient edit"["policy_material_export_not_accepted"](fun()->
    S.check ~export:true ~request:wrong_recipient ~candidate ~limits);
  (* A changed original material graph still has complete updated local pins;
     the producer must find an actual matching graph, never attach the name. *)
  let repin_contract request=
    let contract=get "material_contract" request in
    let contract=put["identity";"content_fingerprint"](str(Canonical.fingerprint(get "body" contract)))contract in
    request|>set "material_contract" contract|>put["catalog_binding";"material_contract"](get "identity" contract)in
  let guard_index=at["material_contract";"body";"kernel";"wires"]request|>Json.array
    |>List.mapi(fun index wire->index,wire)|>List.find(fun(_,wire)->
      at["to";"node"]wire=str "local.select_gate" && at["to";"port"]wire=str "guard")|>fst in
  let wrong_wire=put["material_contract";"body";"kernel";"wires";string_of_int guard_index;"from"]
    (obj["node",str "local.not";"port",str "out"])request|>repin_contract in
  rejects "different complete material wiring"["policy_material_lowering_unsupported"](fun()->compile wrong_wire);
  let bad_configuration=put["implementation";"nodes";"0";"configuration_digest"](str(String.make 64 '0'))candidate in
  rejects "changed implementation parameter pin"["policy_implementation_contract"](fun()->
    S.check ~export:false ~request ~candidate:bad_configuration ~limits);
  rejects "unexpected producer authority"["unknown_field"](fun()->
    run Producer.handle Protocol.Core "compile-policy-material"(set "candidate" candidate(obj["request",request;"limits",limits])));
  let verifier_request:Protocol.request={request_id="verify-material-producer";operation="compile-policy-material";
    payload=obj["request",request;"limits",limits]}in
  (match Service.handle Protocol.Verify verifier_request with
   |Protocol.Unsupported,None,_::_->()|_->failwith "Standalone Verify acquired material producer authority");
  let capabilities=run Service.handle Protocol.Verify "capabilities"(obj[])in
  require(Json.equal(get "policy_material"(get "profiles" capabilities))S.profile)"Missing exact checker capability profile";
  require(not(List.mem_assoc "policy_material_producer"(Json.object_fields(get "profiles" capabilities))))
    "Standalone Verify advertises material production";
  rejects "whole wrapper nodes"["policy_material_service_publication_limit"](fun()->
    S.validate_publication(arr(List.init Limits.max_json_nodes(fun _->Json.Null))));
  rejects "whole wrapper bytes"["policy_material_service_publication_limit"](fun()->
    S.validate_publication(str(String.make(9*1024*1024)'x')));
  let nested=List.fold_left(fun value _->arr[value])Json.Null(List.init 129 Fun.id)in
  rejects "whole wrapper depth"["policy_material_service_publication_limit"](fun()->S.validate_publication nested);
  print_endline "Policy material generic production, standalone conjunction, full replay and fresh paired RNA export passed."

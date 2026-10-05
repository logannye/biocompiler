open Bioc_wire
open Bioc_domain
module B=Bioc_artifact.Archive_budget
module D=Bioc_reference_artifact.Reference_package_manifest
module A=Bioc_reference_artifact.Reference_package_container
module I=Bioc_reference_input.Reference_inputs
module P=Bioc_artifact.Utf8_pretty
module C=Pipeline_contract
module R=Reference_construct
module Q=Reference_molecular
module E=Realization_evidence
module X=Verification_exploration.Codec
module Link=Bioc_checker.Composition_check
module Layout=Bioc_checker.Reference_construct_check
module Molecular=Bioc_checker.Reference_molecular_check
module Export=Bioc_reference_export.Reference_sequence_export
module Sequence=Bioc_reference_export.Reference_sequence_codec
let profile="biocompiler.reference_package_check.v1"
(* Closed declarative identities, checked against the source inventory by the
   foundation suite. Reading these strings never invokes their producers. *)
let construct_pipeline="biocompiler.reference_construct_pipeline.v0.2"
let molecular_pipeline="biocompiler.exact_cds_pipeline.v0.1"
let construct_generator="biocompiler.reference_construct_generator.v0.1"
let sequence_emitter="biocompiler.reference_sequence_emitter.v0.2"
let tool_ids=["reference_build";"human_admission_policy";"reference_inputs";"archive";
  "sequence_export";"sequence_emitter";"construct_pipeline";"molecular_pipeline";
  "reference_adapter";"construct_generator";"component_checker";"construct_checker";"molecular_checker"]
let require condition message=Diagnostic.require condition "reference_package_check" message
let str value=Json.String value
let obj values=Json.Object values
let arr values=Json.Array values
let field key value=Json.field key(Json.object_fields value)
let codec budget=let limits=B.limits budget in X.make_limits
  ~max_bytes:(min limits.max_member_bytes Limits.max_request_bytes)
  ~max_nodes:(min limits.max_json_nodes Limits.max_json_nodes) ~charge:(B.charge budget)()
let retain budget raw=let size=X.measure ~limits:(codec budget) raw in
  B.reserve budget(size.bytes+128*size.nodes+512)
let fingerprint budget value=X.fingerprint ~limits:(codec budget)value
let same budget left right=
  let l=X.encode ~limits:(codec budget)left and r=X.encode ~limits:(codec budget)right in
  B.charge budget(String.length l+String.length r+1);String.equal l r
let equal budget message left right=require(same budget left right)message
let text_equal budget message left right=B.charge budget(String.length left+String.length right+1);
  require(String.equal left right)message
let lookup budget key values=
  let rec loop=function []->None|(name,value)::rest->B.charge budget(String.length key+String.length name+1);
    if String.equal key name then Some value else loop rest in loop values
let member budget key values=match lookup budget key values with Some value->value
  |None->Diagnostic.fail "reference_package_check" ("Missing package member: "^key)
let parse budget raw=
  let limits=B.limits budget in
  require(String.length raw<=limits.max_member_bytes)"Package JSON member exceeds its byte bound.";
  B.product budget(String.length raw+1)32;B.reserve budget(64*String.length raw+128);
  Legacy_json.parse ~on_node:(fun()->B.charge budget 1) ~max_bytes:limits.max_member_bytes
    ~max_nodes:(min limits.max_json_nodes Limits.max_json_nodes) ~profile:Legacy_json.Artifact raw
let pretty budget raw=P.encode budget ~max_bytes:(B.limits budget).max_member_bytes raw
let json_member budget files name expected=
  let actual=member budget name files in
  text_equal budget ("Package member differs from fresh native evidence: "^name) actual(pretty budget expected)
let shape_names budget actual expected message=
  let raw=arr(List.map str actual) in ignore(X.measure ~limits:(codec budget)raw);
  require(List.length actual=List.length expected)message;
  List.iter(fun key->B.charge budget(String.length key+1);
    require(List.length(List.filter(fun other->B.charge budget(String.length key+String.length other+1);String.equal key other)actual)=1
      && List.exists(fun other->B.charge budget(String.length key+String.length other+1);String.equal key other)expected)message)actual

type authority={owner:B.t;package_version:string;tools:(string*string)list;pins:D.Tool.t list option;raw:Json.t;identity:string}
let authority budget ~package_version ~tool_versions=
  B.guard budget;
  (* Preflight also rejects cyclic/unbounded lists before inspecting any keys. *)
  let rec bounded count reversed=function
    |[]->List.rev reversed
    |(key,value)::rest->
        B.charge budget 1;
        require(count<13)"Current tool authority must contain exactly thirteen unique tool identities.";
        require(String.length key<=(B.limits budget).max_path_bytes &&
          String.length value<=(B.limits budget).max_member_bytes)
          "Current tool authority exceeds its string bound.";
        B.charge budget(String.length key+String.length value+1);
        B.reserve budget(String.length key+String.length value+128);
        bounded(count+1)((key,value)::reversed)rest in
  let tool_versions=bounded 0 [] tool_versions in
  require(String.length package_version<=(B.limits budget).max_member_bytes)
    "Package version authority exceeds its string bound.";
  let raw=obj["package_version",str package_version;
    "tool_versions",arr(List.map(fun(key,value)->arr[str key;str value])tool_versions)] in
  ignore(X.measure ~limits:(codec budget)raw);
  shape_names budget(List.map fst tool_versions)tool_ids "Current tool authority must contain exactly thirteen unique tool identities.";
  ignore(Json.name(str package_version));
  List.iter(fun(_,version)->ignore(Json.name(str version)))tool_versions;
  retain budget raw;
  {owner=budget;package_version;tools=tool_versions;pins=None;raw;identity=fingerprint budget raw}
let authority_pins budget ~package_version ~tool_pins=
  B.guard budget;
  let rec bounded count=function
    |[]->()
    |pin::rest->B.charge budget 1;
      require(count<13)"Current tool authority must contain exactly thirteen unique tool identities.";
      retain budget(D.Tool.to_json pin);bounded(count+1)rest in
  bounded 0 tool_pins;
  shape_names budget(List.map D.Tool.id tool_pins)tool_ids "Current tool authority must contain exactly thirteen unique tool identities.";
  require(String.length package_version<=(B.limits budget).max_member_bytes)"Package version authority exceeds its string bound.";
  ignore(Json.name(str package_version));
  let raw=obj["package_version",str package_version;"tool_pins",arr(List.map D.Tool.to_json tool_pins)] in
  retain budget raw;
  {owner=budget;package_version;tools=[];pins=Some tool_pins;raw;identity=fingerprint budget raw}
let authority_json value=value.raw
let check_authority budget value=B.guard budget;
  require(value.owner==budget)"Package metadata authority belongs to another lifetime owner."
let expected_tools budget value=match value.pins with Some pins->pins|None->
  List.map(fun id->let version=member budget id value.tools in
    D.Tool.make budget ~id ~version ~content_fingerprint:(fingerprint budget(str version))())tool_ids
let verify_tools budget authority manifest=
  check_authority budget authority;
  text_equal budget "Package version differs from independent current authority." (D.Manifest.package_version manifest) authority.package_version;
  let expected=expected_tools budget authority in
  let actual=D.Manifest.toolchain manifest in
  shape_names budget(List.map D.Tool.id actual)tool_ids "Package toolchain differs from the complete current tool inventory.";
  List.iter(fun value->let wanted=List.find(fun other->B.charge budget 1;D.Tool.id other=D.Tool.id value)expected in
    equal budget "Package tool identity differs from independent current authority." (D.Tool.to_json value)(D.Tool.to_json wanted))actual
let reference_files budget files=
  let prefix="references/"^Pinned_identity.id I.manifest_pin^"/" in
  B.reserve budget(128*List.length files+128);
  List.filter_map(fun(name,bytes)->B.charge budget(String.length name+1);
    if String.starts_with ~prefix name then begin
      let length=String.length name-String.length prefix in B.reserve budget(length+64);
      Some(String.sub name(String.length prefix)length,bytes)
    end else None)files
let registry budget alphabet reference=
  let limits=codec budget in
  let size=X.measure ~limits(Reference_manifest.to_json reference) in
  B.product budget(size.bytes+size.nodes+1)256;
  B.reserve budget(128*size.bytes+512*size.nodes+32768);
  let selection=Reference_components.Selection.make ~limits ~manifest:I.manifest_pin
    ~reference:(I.reference_pin budget alphabet)() in
  let component=Reference_components.adapt_reference_component ~limits reference selection in
  Component_registry.make ~id:"reviewed-cds" ~version:"1" ~components:[component]
let obligation budget id scope evidence_kind description=C.Scoped_obligation.make ~limits:(codec budget)
  ~id ~scope ~evidence_kind ~description()
let obligations budget=[
  obligation budget "reference_authority" "reference_construct" E.Exact
    "Selected component and supported layout agree with independently pinned reference records.";
  obligation budget "component_linkage" "reference_construct" E.Model_conditional
    "Current selected components satisfy their declared composition contracts.";
  obligation budget "emitted_sequence_identity" "exact_cds" E.Exact
    "Emit the selected nucleotide spelling and independently verify its exact reference identity.";
  obligation budget "complete_payload_features" "complete_payload" E.Exact
    "Delivered molecule boundaries, regulatory context and other unknown payload features remain unresolved.";
  obligation budget "molecular_behavior" "complete_payload" E.Empirical
    "Molecular behavior and same-cell coexistence are not established by a reference layout.";
  obligation budget "construct_layout" "reference_construct" E.Exact
    "Construct preserves exact selected membership, reference coordinates and source requirements."]
let dependencies budget request registry reference=
  let fp value=fingerprint budget(str value) in
  let composition=R.Request.composition request in
  ["human_admission_policy",fp Admission.policy_version;"request",R.Request.fingerprint request;
   "composition",Composition.fingerprint composition;"component_registry",Component_registry.fingerprint registry;
   "component_lock",Component_registry.Lock.fingerprint(Composition.registry_lock composition);
   "layout",R.Request.layout_fingerprint request;
   "references",fingerprint budget(obj[Reference_manifest.reference_set_id reference,str(Reference_manifest.fingerprint reference)]);
   "reference_adapter",fp Reference_components.adapter_version;"component_checker",fp Link.checker_version;
   "construct_checker",fp Layout.checker_version;"construct_generator",fp construct_generator;
   "construct_pipeline",fp construct_pipeline]
let molecular_dependencies budget request=
  let fp value=fingerprint budget(str value) in
  ["molecular_emitter",fp sequence_emitter;"molecular_checker",fp Molecular.checker_version;
   "molecular_profile",fp(Build_request.Target.payload_format(R.Request.target request)^"-CDS");
   "encoding_policy",Q.Encoding_policy.fingerprint(Q.Encoding_policy.default ~limits:(codec budget)());
   "molecular_pipeline",fp molecular_pipeline]
let spec budget id evidence_kind discharges=C.Check_spec.make ~limits:(codec budget) ~id ~evidence_kind ~discharges()
let admission_contract budget request dependencies obligations=
  C.Component_input_contract.make ~limits:(codec budget) ~id:"reference_components" ~version:construct_pipeline
    ~schema:R.Request.schema_version
    ~checks:[spec budget "reference_authority" E.Exact["reference_authority"];
      spec budget "component_linkage" E.Model_conditional["component_linkage"]]
    ~requirements:(Composition.requirement_ids(R.Request.composition request)) ~obligations
    ~dependency_keys:(List.map fst dependencies)()
let construct_contract budget request dependencies layout=
  C.Pass_contract.make ~limits:(codec budget) ~id:"components_to_construct" ~version:construct_generator
    ~input_stage:C.Components ~output_stage:C.Construct ~input_schema:R.Request.schema_version ~output_schema:R.Candidate.schema_version
    ~profile:"reference_construct" ~profile_version:construct_pipeline ~supported_operations:["component_placement"]
    ~checks:[spec budget "layout" E.Exact["construct_layout"];
      spec budget "layout_composition" E.Model_conditional["component_linkage"]]
    ~dependency_keys:(List.map fst dependencies) ~consumes_requirements:(Composition.requirement_ids(R.Request.composition request))
    ~introduces:[layout] ~changed_properties:["layout";"molecule_membership";"orientation";"regulatory_context"]
    ~invalidated_analyses:["component_linkage";"molecular_behavior"]()
let molecular_contract budget request dependencies=
  C.Pass_contract.make ~limits:(codec budget) ~id:"construct_to_molecular" ~version:sequence_emitter
    ~input_stage:C.Construct ~output_stage:C.Molecular ~input_schema:R.Candidate.schema_version ~output_schema:Q.Artifact.schema_version
    ~profile:"exact_cds" ~profile_version:molecular_pipeline ~supported_operations:["cds_record"]
    ~checks:[spec budget "sequence_identity" E.Exact["emitted_sequence_identity";"construct_layout"];
      spec budget "encoding_composition" E.Model_conditional["component_linkage"]]
    ~dependency_keys:("human_admission_policy"::List.map fst dependencies)
    ~consumes_requirements:(Composition.requirement_ids(R.Request.composition request))
    ~changed_properties:["sequence_spelling";"molecular_feature_declarations"]
    ~invalidated_analyses:["construct_layout";"component_linkage";"molecular_behavior"]()
let check_entry budget spec ~detail ~evidence ~subject ~dependencies=
  let decision=C.Check_decision.make ~limits:(codec budget) ~outcome:E.Pass ~detail ~evidence() in
  obj(Json.object_fields(C.Check_spec.to_json spec)@Json.object_fields(C.Check_decision.to_json decision)@
    ["subject",str(fingerprint budget subject);"dependencies",obj(List.map(fun(key,value)->key,str value)dependencies)])
let checks budget specs values subject dependencies=
  obj(List.map2(fun spec (detail,evidence)->C.Check_spec.id spec,
    check_entry budget spec ~detail ~evidence ~subject ~dependencies)specs values)
let links budget pass_name rows=
  arr(List.concat_map(fun(id,requirements)->List.map(fun requirement_id->
    C.Source_link.to_json(C.Source_link.make ~limits:(codec budget) ~requirement_id ~source_node_id:id
      ~target_node_id:id ~pass_name()))requirements)rows)
let provenance contract source_links=obj["contract",C.Pass_contract.to_json contract;"configuration",obj[];
  "source_links",source_links;"observation_map",obj[];"search",str "deterministic; no inference of infeasibility"]
let stage budget ~id ~stage ~payload ~requirements ~obligations ~discharged ~dependencies ~parent
    ~pass_id ~pass_identity ~checks ~provenance=
  let value=C.Stage_record.make ~limits:(codec budget) ~id ~stage ~payload ~requirements ~obligations ~discharged
    ~dependencies ~parent ~pass_id:(Some pass_id) ~pass_identity:(Some pass_identity) ~checks ~provenance ~accepted:true() in
  retain budget(C.Stage_record.to_json value);value
let source_equal budget left right=
  ignore(X.measure ~limits:(codec budget)left);ignore(X.measure ~limits:(codec budget)right);
  let number=function Json.Bool value->Some(Json.int(if value then 1 else 0))
    |(Json.Int _|Json.Float _)as value->Some value|_->None in
  let rec visit left right=B.charge budget 1;
    match number left,number right,left,right with
    |Some a,Some b,_,_->B.product budget 128 (String.length(X.encode ~limits:(codec budget)a)+String.length(X.encode ~limits:(codec budget)b)+1);Json.number_compare a b=0
    |_,_,Json.Null,Json.Null->true
    |_,_,Json.String a,Json.String b->B.charge budget(String.length a+String.length b+1);String.equal a b
    |_,_,Json.Array a,Json.Array b->List.length a=List.length b && List.for_all2 visit a b
    |_,_,Json.Object a,Json.Object b->List.length a=List.length b &&
        List.for_all(fun(key,value)->match lookup budget key b with Some other->visit value other|None->false)a
    |_->false in visit left right
let summaries budget request artifact records unresolved=
  let first=match Q.Artifact.records artifact with value::_->Q.Record.to_json value|[]->
    Diagnostic.fail "reference_package_check" "Freshly checked molecular artifact has no records." in
  let result=obj[
    "schema_version",str "biocompiler.reference_build_summary.v0.2";
    "intended_use",str "software_test";"human_therapeutic_admission",str "not_admitted";
    "status",str "complete";"scope",str "exact_cds";
    "request_fingerprint",str(D.Request.fingerprint request);
    "selected_alternatives",field "references"(R.Request.to_json(D.Request.construct request));
    "feature_map",field "feature_statuses" first;
    "source_maps",obj(List.map(fun value->C.Stage_record.id value,C.Stage_record.provenance value)records);
    "unresolved",arr(List.map C.Scoped_obligation.to_json unresolved);"model_locks",arr[];
    "model_scope",str "Sequence-reference components supply no dynamic model or biological refinement evidence.";
    "upstream_intent",Json.Null;
    "upstream_scope",str "This component-root reference request has no accepted upstream intent or behavior realization."] in
  retain budget result;result
let check_inventory budget manifest reference_snapshot=
  let expected=D.required_files@List.map(fun(path,_)->
    "references/"^Reference_manifest.reference_set_id(I.manifest reference_snapshot)^"/"^path,"reference-input")
    (I.files reference_snapshot) in
  let actual=D.Manifest.files manifest in
  shape_names budget(List.map D.File.path actual)(List.map fst expected)
    "Package inventory differs from the complete checked reference workflow.";
  List.iter(fun value->text_equal budget "Package member role differs from its checked workflow role."
    (D.File.role value)(member budget(D.File.path value)expected))actual
let inspect_records budget request registry reference files=
  let bound=D.Request.construct request and limits=codec budget in
  let raw_record id=parse budget(member budget("stages/"^id^".json")files) in
  (* Imported stage envelopes are parsed as bounded data. Independent checks
     below operate on their literal payloads, without consulting accepted bits. *)
  let imported=List.map(fun id->C.Stage_record.of_json ~limits(raw_record id))["components";"construct";"molecular"] in
  let component,construction,molecule=match imported with [a;b;c]->a,b,c|_->assert false in
  equal budget "Components payload differs from the independent construct request." (C.Stage_record.payload component)(R.Request.to_json bound);
  let construct=R.Candidate.of_json ~limits(C.Stage_record.payload construction) in
  let artifact=Q.Artifact.of_json ~limits(C.Stage_record.payload molecule) in
  let manifests=[Reference_manifest.reference_set_id reference,reference] in
  let layout=Layout.check ~parent:(B.work budget) ~request:bound ~candidate:construct ~registry ~manifests() in
  let linkage=Link.check ~parent:(B.work budget) ~request:(R.Request.composition bound) ~registry() in
  require(Reference_construct_evidence.Result.passed layout && Composition_evidence.Result.passed linkage)
    "A fresh independent component or construct check rejected the package.";
  let exported=Export.export_checked_owned budget ~request:bound ~construct ~artifact ~registry ~manifests
    ~line_width:(D.Request.fasta_line_width request)() in
  let molecular=Export.checked_report exported in
  let layout_json=Reference_construct_evidence.Result.to_json layout
  and linkage_json=Composition_evidence.Result.to_json linkage
  and molecular_json=Reference_molecular_evidence.Result.to_json molecular in
  List.iter(retain budget)[layout_json;linkage_json;molecular_json];
  (* Admission is separately rechecked; a final report cannot stand in for the
     exact admission evidence embedded in the component record. *)
  let diagnostics=Layout.check_request ~parent:(B.work budget) ~request:bound ~registry ~manifests() in
  require(List.for_all(fun value->B.charge budget 1;Reference_construct_evidence.Diagnostic.status value=E.Pass)diagnostics)
    "A fresh independent reference admission check rejected the package.";
  let authority_json=obj["diagnostics",arr(List.map Reference_construct_evidence.Diagnostic.to_json diagnostics)] in
  retain budget authority_json;
  let root_dependencies=dependencies budget bound registry reference in
  let stage_dependencies=root_dependencies@["target",fingerprint budget(Build_request.Target.to_json(R.Request.target bound))] in
  let more=molecular_dependencies budget bound in
  let final_dependencies=stage_dependencies@more in
  let all_obligations=obligations budget in
  let initial_obligations,layout_obligation=match all_obligations with[a;b;c;d;e;f]->[a;b;c;d;e],f|_->assert false in
  let input_contract=admission_contract budget bound root_dependencies initial_obligations in
  let layout_contract=construct_contract budget bound root_dependencies layout_obligation in
  let sequence_contract=molecular_contract budget bound more in
  let requirements=Composition.requirement_ids(R.Request.composition bound) in
  let linkage_detail=Composition_evidence.claim_scope in
  let components=stage budget ~id:"components" ~stage:C.Components ~payload:(R.Request.to_json bound) ~requirements
    ~obligations:initial_obligations ~discharged:["component_linkage";"reference_authority"] ~dependencies:stage_dependencies ~parent:None
    ~pass_id:(C.Component_input_contract.id input_contract) ~pass_identity:(C.Component_input_contract.fingerprint input_contract)
    ~checks:(checks budget(C.Component_input_contract.checks input_contract)
      ["Checked frozen reference selection and supported layout authority.",authority_json;linkage_detail,linkage_json]
      (R.Request.to_json bound)stage_dependencies)
    ~provenance:(obj["authority",str "independently_checked_component_input";"contract",C.Component_input_contract.to_json input_contract]) in
  let construct_links=links budget(C.Pass_contract.id layout_contract)
    (List.map(fun instance->Composition.Instance.id instance,Composition.Instance.requirement_ids instance)
      (Composition.instances(R.Request.composition bound))) in
  let constructed=stage budget ~id:"construct" ~stage:C.Construct ~payload:(R.Candidate.to_json construct) ~requirements
    ~obligations:all_obligations ~discharged:["component_linkage";"construct_layout";"reference_authority"]
    ~dependencies:stage_dependencies ~parent:(Some "components") ~pass_id:(C.Pass_contract.id layout_contract)
    ~pass_identity:(C.Pass_contract.fingerprint layout_contract)
    ~checks:(checks budget(C.Pass_contract.checks layout_contract)
      [Reference_construct_evidence.claim_scope,layout_json;linkage_detail,linkage_json](R.Candidate.to_json construct)stage_dependencies)
    ~provenance:(provenance layout_contract construct_links) in
  let molecular_links=links budget(C.Pass_contract.id sequence_contract)
    (List.map(fun placement->R.Placement.instance_id placement,R.Placement.requirement_ids placement)(R.Candidate.placements construct)) in
  let emitted=stage budget ~id:"molecular" ~stage:C.Molecular ~payload:(Q.Artifact.to_json artifact) ~requirements
    ~obligations:all_obligations ~discharged:["component_linkage";"construct_layout";"emitted_sequence_identity";"reference_authority"]
    ~dependencies:final_dependencies ~parent:(Some "construct") ~pass_id:(C.Pass_contract.id sequence_contract)
    ~pass_identity:(C.Pass_contract.fingerprint sequence_contract)
    ~checks:(checks budget(C.Pass_contract.checks sequence_contract)
      [Reference_molecular_evidence.claim_scope,molecular_json;linkage_detail,linkage_json](Q.Artifact.to_json artifact)final_dependencies)
    ~provenance:(provenance sequence_contract molecular_links) in
  let records=[components;constructed;emitted] in
  List.iter(fun record->json_member budget files("stages/"^C.Stage_record.id record^".json")(C.Stage_record.to_json record))records;
  json_member budget files "checks/composition.json" linkage_json;
  json_member budget files "checks/construct.json" layout_json;
  json_member budget files "checks/molecular.json" molecular_json;
  let bundle=Export.checked_bundle exported in
  text_equal budget "Packaged FASTA differs from fresh checked sequence export."(member budget "sequence.fasta" files)(Sequence.fasta bundle);
  text_equal budget "Packaged molecular specification differs from fresh checked sequence export."(member budget "molecular.json" files)(Sequence.specification bundle);
  let unresolved=List.filter(fun value->not(List.mem(C.Scoped_obligation.id value)(C.Stage_record.discharged emitted)))all_obligations in
  json_member budget files "result.json"(summaries budget request artifact records unresolved);
  records
let accepted_stages budget manifest records=
  let expected=List.map(fun value->let stage=match C.Stage_record.stage value with
      |C.Components->D.Accepted_stage.Components|C.Construct->D.Accepted_stage.Construct
      |C.Molecular->D.Accepted_stage.Molecular|_->assert false in
    D.Accepted_stage.make budget ~stage ~artifact_fingerprint:(fingerprint budget(C.Stage_record.payload value))
      ~record_fingerprint:(C.Stage_record.fingerprint value)
      ~artifact_schema:(Json.string(field "schema_version"(C.Stage_record.payload value)))())records in
  equal budget "Manifest stage claims differ from the complete freshly checked stage records."
    (arr(List.map D.Accepted_stage.to_json(D.Manifest.accepted_stages manifest)))
    (arr(List.map D.Accepted_stage.to_json expected))
type checked={owner:B.t;authority_identity:string;data:string;archive_identity:string;build_identity:string;
  request_value:D.Request.t;expected_request_identity:string option;expected_build_identity:string option;report_value:Json.t}
let verify ?runtime budget ~authority:current ?expected_request ?expected_build_fingerprint data=
  B.guard budget;check_authority budget current;
  require(B.owns_retention budget)"Independent package checking requires one configured retained-data owner.";
  require(Option.is_some expected_request || Option.is_some expected_build_fingerprint)
    "Fresh package checking requires an independently trusted request or build fingerprint.";
  let parsed=A.read ?runtime budget data in
  let manifest=A.manifest parsed and files=A.files parsed in
  verify_tools budget current manifest;
  let request=D.Request.of_json_text budget(member budget "request.json" files) in
  Option.iter(fun expected->require(source_equal budget(D.Request.to_json request)(D.Request.to_json expected))
    "Packaged request differs from independent authority.")expected_request;
  Option.iter(fun expected->text_equal budget "Packaged build differs from independent authority."
    (D.Manifest.fingerprint manifest)expected)expected_build_fingerprint;
  text_equal budget "Packaged request fingerprint mismatch."(D.Manifest.request_fingerprint manifest)(D.Request.fingerprint request);
  json_member budget files "request.json"(D.Request.to_json request);
  let bound=D.Request.construct request in
  let target=R.Request.target bound in
  let target_size=X.measure ~limits:(codec budget)(Build_request.Target.to_json target) in
  B.product budget(target_size.bytes+target_size.nodes+1)128;
  B.reserve budget(16*target_size.bytes+128*target_size.nodes+8192);
  ignore(Bioc_checker.Admission_check.require_software_use ~target ~boundary:Admission.Verification ~components:[]);
  let alphabet=match Build_request.Target.payload_format target with "DNA"->Reference_manifest.DNA|"RNA"->Reference_manifest.RNA
    |_->Diagnostic.fail "reference_package_check" "Reference packages support only declared DNA or RNA." in
  let snapshot=I.validate_snapshot budget ~files:(reference_files budget files) in
  check_inventory budget manifest snapshot;
  let reference=I.manifest snapshot in
  let registry=registry budget alphabet reference in
  json_member budget files "inputs/registry.json"(Component_registry.to_json registry);
  let records=inspect_records budget request registry reference files in
  accepted_stages budget manifest records;
  B.charge budget(String.length data+1);let archive_identity=Canonical.sha256 data in
  let report_value=obj["schema_version",str profile;"outcome",str "pass";
    "archive_sha256",str archive_identity;"build_fingerprint",str(D.Manifest.fingerprint manifest);
    "request_fingerprint",str(D.Request.fingerprint request);"metadata_authority",str current.identity;
    "claim_scope",str "Exact reference package, stage evidence and sequence consistency for software use; no biological or therapeutic claim.";
    "core_reconstruction_required",Json.Bool true] in
  retain budget report_value;B.reserve budget(String.length data+768);
  {owner=budget;authority_identity=current.identity;data;archive_identity;build_identity=D.Manifest.fingerprint manifest;
   request_value=request;expected_request_identity=Option.map D.Request.fingerprint expected_request;
   expected_build_identity=expected_build_fingerprint;report_value}
let require_checked budget (value:checked) ~authority:current ?expected_request ?expected_build_fingerprint data=
  B.guard budget;check_authority budget current;
  require(value.owner==budget)"Checked package belongs to another resource lifetime.";
  text_equal budget "Checked package metadata authority changed."value.authority_identity current.identity;
  require(value.expected_request_identity=Option.map D.Request.fingerprint expected_request &&
    value.expected_build_identity=expected_build_fingerprint)"Checked package independent authority changed.";
  text_equal budget "Checked package bytes changed."value.data data
let report value=value.report_value
let archive_sha256 value=value.archive_identity
let build_fingerprint value=value.build_identity
let request value=value.request_value

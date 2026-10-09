open Bioc_wire
module Contract=Bioc_domain.Policy_realization_evidence_contract
module Evidence=Bioc_realization_checker.Policy_realization_evidence_check
module Material=Bioc_realization_checker.Policy_component_material_check
module Service=Bioc_service.Policy_component_material_service
module Producer=Bioc_producer_service.Producer_service
let s value=Json.String value
let o value=Json.Object value
let a value=Json.Array value
let get key raw=Json.field key(Json.object_fields raw)
let rows key raw=Json.array(get key raw)
let rec at path raw=match path with []->raw|key::rest->at rest(get key raw)
let set key value raw=o(List.map(fun(name,old)->name,if name=key then value else old)(Json.object_fields raw))
let rec edit path change raw=match path with []->change raw|key::rest->set key(edit rest change(get key raw))raw
let first change raw=match Json.array raw with value::rest->a(change value::rest)|_->failwith "Missing fixture row"
let require condition message=if not condition then failwith message
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_artifact ~max_bytes:(8*1024*1024) ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let repin raw=edit["identity";"content_fingerprint"](fun _->s(Canonical.fingerprint(get "body" raw)))raw
let change_protocol change raw=
  let protocol=repin(edit["body"]change(List.hd(rows "protocols"(get "dossier" raw))))in
  let raw=edit["dossier";"protocols"](first(fun _->protocol))raw in
  let dataset=repin(edit["body";"protocol"](fun _->get "identity" protocol)(List.hd(rows "datasets"(get "dossier" raw))))in
  let raw=edit["dossier";"datasets"](first(fun _->dataset))raw in
  edit["dossier";"analyses"](first(fun row->repin(edit["body";"dataset"](fun _->get "identity" dataset)row)))raw
let change_dataset change raw=
  let dataset=repin(edit["body"]change(List.hd(rows "datasets"(get "dossier" raw))))in
  let raw=edit["dossier";"datasets"](first(fun _->dataset))raw in
  edit["dossier";"analyses"](first(fun row->repin(edit["body";"dataset"](fun _->get "identity" dataset)row)))raw
let change_analysis change=edit["dossier";"analyses"](first(fun row->repin(edit["body"]change row)))
let criterion change=edit["requirements"](first change)
let checked label=function Some value->value|None->failwith(label^" missing fresh checked capability")
let negatives=ref 0
let rejects label action=match action()with
  |_->failwith("Evidence decoder accepted "^label)
  |exception Diagnostic.Error _->incr negatives
let ()=
  Printexc.register_printer(function Diagnostic.Error d->Some(d.code^": "^d.message)|_->None);
  require(Array.length Sys.argv=3)"Expected evidence and original network fixture paths";
  let fixture=read Sys.argv.(1)and network=read Sys.argv.(2)in
  require(get "material_fixture_fingerprint" fixture=s(Canonical.fingerprint network))"Evidence drifted from independent material fixture";
  let request=get "request" network and limits=get "limits" network in
  let response={Protocol.request_id="realization-evidence";operation="compile-policy-component-material";
    payload=o["request",request;"limits",limits]}in
  let produced=match Producer.handle Protocol.Core response with
    |Protocol.Ok,Some value,[]->value|_->failwith "Could not construct evidence's exact material baseline"in
  let _,result=Service.fresh_check ~request ~candidate:(get "candidate" produced) ~limits in
  let material=checked "Material"(Material.accepted result)in
  let original=Material.evidence material and raw=get "contract" fixture in
  let run raw=Evidence.check ~material ~contract:(Contract.of_json raw)()in
  let baseline=run raw in
  require(Evidence.status baseline=Evidence.Supported && Evidence.export_permitted baseline &&
    Option.is_some(Evidence.accepted baseline))"Independent off-grid intervals did not support supplied criterion";
  let report=Evidence.report baseline and token=checked "Evidence"(Evidence.accepted baseline)in
  require(Json.equal(Material.evidence(Evidence.material token))original &&
    Json.equal(Contract.to_json(Evidence.contract token))raw && Json.equal(Evidence.evidence token)report)
    "Fresh evidence capability lost exact original material or contract";
  let row=List.hd(rows "requirements" report)in
  require(Json.equal(get "recomputed_envelope" row)(at["expected";"recomputed_envelope"]fixture) &&
    get "origins" row=a[s "synthetic_fixture"] && get "empirical" report=s "unassessed" &&
    get "authenticity" report=s "unassessed" && get "artifact_contents" report=s "unassessed" &&
    get "statistical_coverage" report=s "not_inferred" && get "formal_prerequisites_discharged" report=a[])
    "Synthetic compatibility upgraded empirical or formal evidence";
  require(get "material_assessment_fingerprint" report=s(Canonical.fingerprint original) &&
    get "contract_fingerprint" report=s(Canonical.fingerprint raw) &&
    Json.equal(get "applicability" report)(at["requirements"]raw|>Json.array|>List.hd|>get "applicability"))
    "Evidence failed to retain exact original applicability and fresh formal assessment";
  let expect label status raw=
    let result=run raw in
    require(Evidence.status result=status)("Incorrect evidence status: "^label);
    require(Evidence.export_permitted result=(not(Contract.require_compatibility(Contract.of_json raw)) || status=Evidence.Supported))
      ("Incorrect evidence export gate: "^label);
    require(Option.is_some(Evidence.accepted result)=(status=Evidence.Supported))("Evidence capability escaped status: "^label);
    incr negatives;result in
  ignore(expect "missing dossier" Evidence.Unassessed(set "dossier" Json.Null raw));
  ignore(expect "partial empty dossier" Evidence.Unassessed(set "dossier"(o["protocols",a[];"datasets",a[];"analyses",a[]])raw));
  ignore(expect "missing protocol" Evidence.Unassessed(edit["dossier";"protocols"](fun _->a[])raw));
  ignore(expect "missing analysis" Evidence.Unassessed(edit["dossier";"analyses"](fun _->a[])raw));
  ignore(expect "missing dataset while retaining analysis" Evidence.Unassessed(edit["dossier";"datasets"](fun _->a[])raw));
  ignore(expect "insufficient replicates" Evidence.Unassessed(criterion(set "minimum_replicates"(Json.int 4))raw));
  let stale=s(String.make 64 '0')in
  ignore(expect "stale selected component" Evidence.Incompatible(criterion(edit["component";"content_fingerprint"](fun _->stale))raw));
  ignore(expect "stale mechanism" Evidence.Incompatible(criterion(set "mechanism_fingerprint" stale)raw));
  ignore(expect "wrong selected instance" Evidence.Incompatible(criterion(set "instance"(s "actuator"))raw));
  ignore(expect "wrong parameter" Evidence.Incompatible(criterion(edit["parameter";"transfer"](fun _->s "absent"))raw));
  ignore(expect "wrong nominal" Evidence.Incompatible(criterion(edit["nominal";"amount"](fun _->s "2"))raw));
  List.iter(fun key->ignore(expect("stale target "^key)Evidence.Incompatible
    (criterion(edit["applicability";key](fun _->stale))raw)))
    ["recipient_fingerprint";"deployment_fingerprint";"clock_fingerprint";"operating_domain_fingerprint"];
  ignore(expect "stale target environment" Evidence.Incompatible
    (criterion(edit["applicability";"environment_fingerprints"](fun _->a[stale]))raw));
  ignore(expect "nonapplicable dataset" Evidence.Unassessed
    (change_dataset(edit["applicability";"recipient_fingerprint"](fun _->stale))raw));
  ignore(expect "nonapplicable protocol clock" Evidence.Unassessed
    (change_protocol(edit["sample_period";"amount"](fun _->s "2"))raw));
  ignore(expect "wrong but repinned independent envelope" Evidence.Incompatible
    (change_analysis(edit["envelope";"lower";"amount"](fun _->s "0.96"))raw));
  ignore(expect "analysis replicate omission" Evidence.Incompatible(change_analysis(set "replicate_ids"(a[s "r1";s "r2"]))raw));
  ignore(expect "analysis replicate reordering" Evidence.Incompatible(change_analysis(set "replicate_ids"(a[s "r3";s "r2";s "r1"]))raw));
  let measured lower upper=
    let raw=change_dataset(edit["replicates"](fun rows->a(List.map(fun row->
      edit["interval";"lower";"amount"](fun _->s lower)(edit["interval";"upper";"amount"](fun _->s upper)row))(Json.array rows))))raw in
    change_analysis(edit["envelope";"lower";"amount"](fun _->s lower))
      (change_analysis(edit["envelope";"upper";"amount"](fun _->s upper))raw)in
  ignore(expect "disjoint measurements" Evidence.Incompatible(measured "1.2" "1.3"));
  ignore(expect "overlapping inconclusive measurements" Evidence.Unassessed(measured "0.8" "1"));
  ignore(expect "nonapplicable disjoint measurements" Evidence.Unassessed
    (change_dataset(edit["applicability";"clock_fingerprint"](fun _->stale))(measured "1.2" "1.3")));
  ignore(expect "nominal outside tolerance" Evidence.Incompatible(criterion(edit["accepted_interval";"upper";"amount"](fun _->s "0.95"))raw));
  ignore(expect "mismatched complete measurement units" Evidence.Incompatible
    (change_dataset(edit["replicates"](first(edit["interval"](fun value->value|>
      edit["lower";"unit";"reference"](fun _->s "other")|>edit["upper";"unit";"reference"](fun _->s "other")))))raw));
  ignore(expect "unmatched criterion dataset" Evidence.Incompatible(change_dataset(set "requirement"(s "absent"))raw));
  let gated=run(set "require_compatibility"(Json.Bool true)(set "dossier" Json.Null raw))in
  require(Evidence.status gated=Evidence.Unassessed && not(Evidence.export_permitted gated))"Explicit evidence export gate was ignored";
  require(Evidence.export_permitted(run(set "require_compatibility"(Json.Bool true)raw)))"Supported compatibility did not satisfy explicit gate";
  let reported=change_dataset(edit["provenance";"origin"](fun _->s "supplied_experiment"))raw in
  let reported=run reported in
  require(Evidence.status reported=Evidence.Supported && get "empirical"(Evidence.report reported)=s "unassessed" &&
    get "origins"(List.hd(rows "requirements"(Evidence.report reported)))=a[s "supplied_experiment";s "synthetic_fixture"])
    "Declared experimental origin became authenticated empirical evidence";
  List.iter(fun(label,value)->rejects label(fun()->ignore(Contract.of_json value)))[
    "missing declared requirements",set "requirements"(a[])raw;
    "old unknown schema",set "schema_version"(s "old")raw;
    "duplicate requirements",edit["requirements"](fun rows->a(Json.array rows@Json.array rows))raw;
    "float quantity",criterion(edit["nominal";"amount"](fun _->Json.int 1))raw;
    "stale raw dataset pin",edit["dossier";"datasets"](first(edit["body";"provenance";"producer"](fun _->s "mutated")))raw;
    "duplicate replicate",change_dataset(edit["replicates"](fun rows->let values=Json.array rows in a(values@[List.hd values])))raw;
    "invalid interval order",change_dataset(edit["replicates"](first(edit["interval";"lower";"amount"](fun _->s "2"))))raw;
    "rate mistaken for amount per sample",change_protocol(set "quantity_semantics"(s "continuous_rate"))raw;
    "absent sample period",change_protocol(set "sample_period" Json.Null)raw;
    "unrecognized analysis method",change_analysis(set "method"(s "trusted_score"))raw;
    "unsupported empirical status",change_dataset(edit["provenance";"origin"](fun _->s "proven"))raw;
    "unbounded required replicates",criterion(set "minimum_replicates"(Json.int 33))raw];
  rejects "zero work allowance"(fun()->ignore(Evidence.check ~maximum:0 ~material ~contract:(Contract.of_json raw)()));
  let parent=Bioc_checker.Work_budget.create ~profile:"evidence-test" ~error_code:"evidence_parent_limit" ~maximum:1()in
  rejects "nested parent work allowance"(fun()->ignore(Evidence.check ~parent ~material ~contract:(Contract.of_json raw)()));
  require(Json.equal(Material.evidence material)original && get "empirical" original=s "unassessed")
    "Experimental evidence changed original exact formal material acceptance";
  Printf.printf "realization evidence: supported synthetic off-grid intervals, %d negative/status controls, separate export gate and unchanged formal material\n" !negatives

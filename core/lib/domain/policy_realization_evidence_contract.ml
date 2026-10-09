open Bioc_wire
module Pin = Pinned_identity
let schema_version="biocompiler.policy_realization_evidence_contract.v0.1"
let profile="biocompiler.policy_parameter_measurement_evidence.v0.1"
type quantity={raw:Json.t;amount:Q.t;unit:Json.t}
type interval={raw:Json.t;lower:quantity;upper:quantity}
type applicability={raw:Json.t;recipient:string;deployment:string;clock:string;domain:string;environments:string list}
type artifact={raw:Json.t;id:string;digest:string;media_type:string;locator:string}
type origin=Synthetic_fixture|Supplied_experiment
let origin_name=function Synthetic_fixture->"synthetic_fixture"|Supplied_experiment->"supplied_experiment"
type provenance={raw:Json.t;origin:origin;producer:string;recorded_at:string;artifact:artifact}
type requirement={raw:Json.t;id:string;instance:string;component:Pin.t;mechanism_fingerprint:string;
  transfer:string;nominal:quantity;accepted:interval;minimum_replicates:int;applicability:applicability}
type protocol={raw:Json.t;identity:Pin.t;period:quantity;procedure:string;provenance:provenance}
type replicate={id:string;interval:interval}
type dataset={raw:Json.t;identity:Pin.t;requirement:string;protocol:Pin.t;applicability:applicability;
  replicates:replicate list;provenance:provenance}
type software={raw:Json.t;name:string;version:string;artifact:artifact}
type analysis={raw:Json.t;identity:Pin.t;dataset:Pin.t;replicate_ids:string list;envelope:interval option;
  software:software;provenance:provenance}
type dossier={protocols:protocol list;datasets:dataset list;analyses:analysis list}
type t={raw:Json.t;compatibility:bool;requirements_value:requirement list;dossier_value:dossier option}
let str value=Json.String value
let get key raw=Json.field key(Json.object_fields raw)
let exact keys raw=Json.exact_fields keys(Json.object_fields raw)
let require condition message=Diagnostic.require condition "policy_realization_evidence_contract" message
let text ?(maximum=256) raw=let value=Json.name raw in
  require(String.length value<=maximum)"Evidence text exceeds its explicit bound.";value
let hash raw=let value=Json.string raw in
  require(String.length value=64 && String.for_all(function '0'..'9'|'a'..'f'->true|_->false)value)
    "Evidence references require lowercase SHA-256 identities.";value
let rows maximum raw=Molecular_record.array ~maximum raw
let unique label values=require(List.length(List.sort_uniq String.compare values)=List.length values)
  ("Duplicate "^label^" identity.")
let decimal raw=let value=Json.string raw in
  require(String.length value<=256)"Evidence decimal exceeds its bound.";Policy_document.exact_decimal value
let unit raw=
  exact["$type";"id";"dimension";"quantity_kind";"scale";"reference"]raw;
  require(get "$type" raw=str "Unit")"Evidence intervals require complete policy Unit identities.";
  List.iter(fun key->ignore(text(get key raw)))["id";"dimension";"quantity_kind"];
  require(Q.sign(decimal(get "scale" raw))>0)"Evidence unit scale must be positive.";
  (match get "reference" raw with Json.Null->()|value->ignore(text value));raw
let quantity raw=
  exact["$type";"amount";"unit"]raw;
  require(get "$type" raw=str "Quantity")"Evidence values require exact policy Quantity records.";
  {raw;amount=decimal(get "amount" raw);unit=unit(get "unit" raw)}
let interval raw=
  exact["lower";"upper"]raw;
  let lower=quantity(get "lower" raw)and upper=quantity(get "upper" raw)in
  require(Json.equal lower.unit upper.unit && Q.compare lower.amount upper.amount<=0)
    "Measurement interval endpoints require identical complete units and ordered exact bounds.";
  {raw;lower;upper}
let applicability_of_json raw=
  exact["recipient_fingerprint";"deployment_fingerprint";"clock_fingerprint";"operating_domain_fingerprint";"environment_fingerprints"]raw;
  let environments=List.map hash(rows 8(get "environment_fingerprints" raw))in
  unique "environment fingerprint" environments;
  {raw;recipient=hash(get "recipient_fingerprint" raw);deployment=hash(get "deployment_fingerprint" raw);
    clock=hash(get "clock_fingerprint" raw);domain=hash(get "operating_domain_fingerprint" raw);environments}
let artifact raw=
  exact["id";"sha256";"media_type";"locator"]raw;
  {raw;id=text(get "id" raw);digest=hash(get "sha256" raw);media_type=text(get "media_type" raw);
    locator=text ~maximum:2048(get "locator" raw)}
let provenance raw=
  exact["origin";"producer";"recorded_at";"artifact"]raw;
  let origin=match Json.string(get "origin" raw)with
    |"synthetic_fixture"->Synthetic_fixture|"supplied_experiment"->Supplied_experiment
    |_->Diagnostic.fail "policy_realization_evidence_contract" "Unknown declared evidence origin."in
  {raw;origin;producer=text(get "producer" raw);recorded_at=text(get "recorded_at" raw);artifact=artifact(get "artifact" raw)}
let pin kind raw=let value=Pin.of_json raw in
  require(Pin.kind value=kind)"Evidence references changed their required complete identity kind.";
  ignore(text(str(Pin.id value)));ignore(text(str(Pin.version value)));value
let supplied raw=
  exact["identity";"body"]raw;
  let identity=pin Pin.Source(get "identity" raw)and body=get "body" raw in
  require(Pin.content_fingerprint identity=Canonical.fingerprint body)
    "Supplied protocol, dataset and analysis identities must pin their complete independent bodies.";
  identity,body
let requirement raw=
  exact["id";"instance";"component";"mechanism_fingerprint";"parameter";"nominal";"accepted_interval";
    "minimum_replicates";"applicability"]raw;
  let parameter=get "parameter" raw in exact["kind";"transfer"]parameter;
  require(get "kind" parameter=str "transfer_amount")"Evidence targets are explicitly per-sample transfer amount parameters.";
  let minimum=Json.integer(get "minimum_replicates" raw)in
  require(Z.geq minimum(Z.of_int 2) && Z.leq minimum(Z.of_int 32))"Require two-to-thirty-two supplied replicate records.";
  {raw;id=text(get "id" raw);instance=text(get "instance" raw);component=pin Pin.Model(get "component" raw);
    mechanism_fingerprint=hash(get "mechanism_fingerprint" raw);transfer=text(get "transfer" parameter);
    nominal=quantity(get "nominal" raw);accepted=interval(get "accepted_interval" raw);
    minimum_replicates=Z.to_int minimum;applicability=applicability_of_json(get "applicability" raw)}
let protocol raw=
  let identity,body=supplied raw in
  exact["quantity_semantics";"sample_period";"procedure";"provenance"]body;
  require(get "quantity_semantics" body=str "amount_per_accepted_sample")
    "Measurement protocols must distinguish amount per accepted sample from continuous rates.";
  let period=quantity(get "sample_period" body)in
  require(Q.sign period.amount>0 && get "dimension" period.unit=str "time" &&
    get "quantity_kind" period.unit=str "duration" && get "reference" period.unit=Json.Null)
    "Measurement protocols require an exact positive unreferenced sample duration.";
  {raw;identity;period;procedure=text ~maximum:4096(get "procedure" body);provenance=provenance(get "provenance" body)}
let dataset raw=
  let identity,body=supplied raw in
  exact["requirement";"protocol";"applicability";"replicates";"provenance"]body;
  let replicates=List.map(fun raw->exact["id";"interval"]raw;
    {id=text(get "id" raw);interval=interval(get "interval" raw)})(rows 32(get "replicates" body))in
  unique "replicate"(List.map(fun(value:replicate)->value.id)replicates);
  {raw;identity;requirement=text(get "requirement" body);protocol=pin Pin.Source(get "protocol" body);
    applicability=applicability_of_json(get "applicability" body);replicates;provenance=provenance(get "provenance" body)}
let software raw=
  exact["name";"version";"artifact"]raw;
  {raw;name=text(get "name" raw);version=text(get "version" raw);artifact=artifact(get "artifact" raw)}
let analysis raw=
  let identity,body=supplied raw in
  exact["dataset";"method";"replicate_ids";"envelope";"software";"provenance"]body;
  require(get "method" body=str "replicate_interval_envelope.v0.1")"Unknown independently recomputable analysis method.";
  let replicate_ids=List.map text(rows 32(get "replicate_ids" body))in
  unique "analysis replicate" replicate_ids;
  {raw;identity;dataset=pin Pin.Source(get "dataset" body);replicate_ids;
    envelope=(match get "envelope" body with Json.Null->None|value->Some(interval value));
    software=software(get "software" body);provenance=provenance(get "provenance" body)}
let of_json ?(charge=fun _->()) raw=
  ignore(Policy_material_request.preflight ~max_bytes:1048576 ~max_nodes:32768 ~max_depth:48 ~charge raw);
  exact["schema_version";"profile";"require_compatibility";"requirements";"dossier"]raw;
  require(get "schema_version" raw=str schema_version && get "profile" raw=str profile)"Unknown realization evidence contract profile.";
  let requirements_value=List.map requirement(rows 8(get "requirements" raw))in
  require(requirements_value<>[])"Evidence assessment requires an independently declared parameter criterion.";
  unique "requirement"(List.map(fun(value:requirement)->value.id)requirements_value);
  let dossier_value=match get "dossier" raw with Json.Null->None|value->
    exact["protocols";"datasets";"analyses"]value;
    let protocols=List.map protocol(rows 8(get "protocols" value))
    and datasets=List.map dataset(rows 8(get "datasets" value))
    and analyses=List.map analysis(rows 8(get "analyses" value))in
    unique "protocol"(List.map(fun(value:protocol)->Pin.id value.identity)protocols);
    unique "dataset"(List.map(fun(value:dataset)->Pin.id value.identity)datasets);
    unique "analysis"(List.map(fun(value:analysis)->Pin.id value.identity)analyses);
    unique "dataset requirement"(List.map(fun(value:dataset)->value.requirement)datasets);
    unique "analysis dataset"(List.map(fun(value:analysis)->Pin.fingerprint value.dataset)analyses);
    Some{protocols;datasets;analyses}in
  {raw;compatibility=Json.boolean(get "require_compatibility" raw);requirements_value;dossier_value}
let to_json(value:t)=value.raw
let fingerprint(value:t)=Canonical.fingerprint value.raw
let require_compatibility value=value.compatibility
let requirements value=value.requirements_value
let dossier value=value.dossier_value
let applicability_to_json(value:applicability)=value.raw
let interval_to_json(value:interval)=value.raw

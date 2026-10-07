open Bioc_wire
module C=Policy_material_contract
module M=Molecular_record
module F=Policy_operating_domain
module P=Pinned_identity
module A=Architecture_contract
let schema_version="biocompiler.policy_material_context.v0.1"
let profile="biocompiler.policy_truth_mrna.v0.1"
let provider_schema="biocompiler.policy_material_provider.v0.1"
let record_profile="biocompiler.policy_material_complete_records.v0.1"
let delivery_group_schema="biocompiler.policy_delivery_group.v0.1"
let require condition message=Diagnostic.require condition "policy_material_context" message
let str value=Json.String value
let obj value=Json.Object value
let arr value=Json.Array value
let get key value=Json.field key(Json.object_fields value)
let exact keys raw=Json.exact_fields keys(Json.object_fields raw)
let text raw=M.text ~maximum:4096 raw
let rows maximum raw=M.array ~maximum raw
let integer minimum maximum raw=let value=Json.integer raw in
  require(Z.geq value(Z.of_int minimum)&&Z.leq value(Z.of_int maximum))"Context integer exceeds its closed bound.";Z.to_int value
let pin raw=let value=Json.string raw in
  require(String.length value=64 && String.for_all(function '0'..'9'|'a'..'f'->true|_->false)value)"Expected lowercase SHA-256 identity.";value
let unique label values=require(List.length values=List.length(List.sort_uniq String.compare values))("Duplicate "^label^" identity.")
let record_shapes=let fields values=arr(List.map str values)in
  let attempt=["bank";"scope_slot_generation";"ordinal";"executor";"subject";"gate";"guard_endpoint";
    "ordered_cause_ids";"product_symbol";"started_tick";"deadline_tick";"ended_tick";"status";"authorization_truth"]in
  obj["truth_cells",fields["defined";"three_valued_truth";"ordered_reasons_with_duplicates"];
    "evidence_records",fields["bank";"scope_slot_generation";"status";"known_value";"observed_tick";"available_tick";"ordered_occurrence_ids"];
    "edge_history_cells",fields["node";"scope_slot_generation";"previous_truth"];
    "generation_counters",fields["slot";"target";"generation";"generation_start_tick";"active";"event_ordinal"];
    "active_attempt_records",fields attempt;"retained_correlation_records",fields attempt;
    "timer_cells",fields["owner";"scope_slot_generation";"deadline_tick";"active"];
    "control_event_records",fields["event_activation_write_or_request";"event_id";"origin_endpoint";"kind";"scope_slot_generation";
      "attempt_ordinal";"tick";"microstep";"gate";"guard_endpoint";"ordered_cause_ids";"commit";"destination";"truth";"product_symbol"];
    "input_rows_per_tick",fields["observation_or_feedback";"occurrence_id";"input";"slot";"generation";"observed_tick";
      "status";"known_value";"attempt_ordinal";"executor";"subject";"outcome"]]
type time={spelling:string;seconds:Q.t}
let time raw=let spelling=Json.string raw in let seconds=Policy_document.exact_decimal spelling in
  require(Q.sign seconds>=0)"Deployment seconds must be nonnegative.";{spelling;seconds}
let time_json(value:time)=str value.spelling
type interval={earliest:time;latest:time}
let interval_json(value:interval)=obj["earliest",time_json value.earliest;"latest",time_json value.latest]
let interval raw=exact["earliest";"latest"]raw;
  let earliest=time(get "earliest" raw)and latest=time(get "latest" raw)in
  require(Q.leq earliest.seconds latest.seconds)"Reversed phase interval.";{earliest;latest}
type availability={onset_min:time;onset_max:time;duration_min:time;duration_max:time}
let availability_to_json(value:availability)=obj["onset_min",time_json value.onset_min;"onset_max",time_json value.onset_max;
  "duration_min",time_json value.duration_min;"duration_max",time_json value.duration_max]
let availability raw=exact["onset_min";"onset_max";"duration_min";"duration_max"]raw;
  let value={onset_min=time(get "onset_min" raw);onset_max=time(get "onset_max" raw);
    duration_min=time(get "duration_min" raw);duration_max=time(get "duration_max" raw)}in
  require(Q.leq value.onset_min.seconds value.onset_max.seconds && Q.leq value.duration_min.seconds value.duration_max.seconds)
    "Availability interval bounds are reversed.";value
type recipient={role:string;identity:string;compartment:string}
let recipient_to_json(value:recipient)=obj["role",str value.role;"identity",str value.identity;"compartment",str value.compartment]
let parse_recipient raw=exact["role";"identity";"compartment"]raw;
  {role=text(get "role" raw);identity=text(get "identity" raw);compartment=text(get "compartment" raw)}
type clock={original_clock:Json.t;period:time;origin:time;deployment_clock:string}
let clock_json(value:clock)=obj["original_clock",value.original_clock;"period_seconds",time_json value.period;
  "origin_seconds",time_json value.origin;"deployment_clock",str value.deployment_clock]
let parse_clock raw=exact["original_clock";"period_seconds";"origin_seconds";"deployment_clock"]raw;
  let value={original_clock=get "original_clock" raw;period=time(get "period_seconds" raw);
    origin=time(get "origin_seconds" raw);deployment_clock=text(get "deployment_clock" raw)}in
  exact["$type";"id";"basis";"resolution";"simultaneous"]value.original_clock;
  require(get "$type" value.original_clock=str "Clock")"Original clock must retain its typed source declaration.";
  require(Q.sign value.period.seconds>0 && value.deployment_clock="declared_exposure_start")"Unsupported exact clock relation.";value
type record_layout={kernel_digest:string;domain_digest:string;slots:int;generations:int;attempts:int;
  horizon:int;maximum_tick:int;ordered_reasons:int;ordered_causes:int;identifier_bytes:int}
let record_layout_to_json(value:record_layout)=obj["profile",str record_profile;
  "record_shapes",record_shapes;
  "kernel_digest",str value.kernel_digest;"domain_digest",str value.domain_digest;
  "slots",Json.int value.slots;"generations",Json.int value.generations;"attempts",Json.int value.attempts;
  "horizon_ticks",Json.int value.horizon;"maximum_tick",Json.int value.maximum_tick;
  "ordered_reason_slots",Json.int value.ordered_reasons;"ordered_cause_slots",Json.int value.ordered_causes;
  "identifier_bytes",Json.int value.identifier_bytes]
let record_layout_fingerprint value=Canonical.fingerprint(record_layout_to_json value)
let parse_layout raw=
  exact["profile";"record_shapes";"kernel_digest";"domain_digest";"slots";"generations";"attempts";"horizon_ticks";
    "maximum_tick";"ordered_reason_slots";"ordered_cause_slots";"identifier_bytes"]raw;
  require(get "profile" raw=str record_profile)"Unsupported complete-record interpretation.";
  require(Json.equal(get "record_shapes" raw)record_shapes)"Incomplete or altered semantic record fields.";
  let number minimum key=integer minimum 1000000(get key raw)in
  {kernel_digest=pin(get "kernel_digest" raw);domain_digest=pin(get "domain_digest" raw);
   slots=number 1 "slots";generations=number 1 "generations";attempts=number 1 "attempts";
   horizon=number 0 "horizon_ticks";maximum_tick=number 0 "maximum_tick";
   ordered_reasons=number 0 "ordered_reason_slots";ordered_causes=number 1 "ordered_cause_slots";
   identifier_bytes=number 1 "identifier_bytes"}
type capacity={capacity_id:string;pool_id:string;unit:C.resource_unit;scope:C.resource_scope;quantity:int;
  slots:string list;record_layout_digest:string;available:availability}
let capacity_json(value:capacity)=obj["id",str value.capacity_id;"pool_id",str value.pool_id;
  "unit",str(C.resource_unit_name value.unit);"scope",str(C.resource_scope_name value.scope);
  "quantity",Json.int value.quantity;"slots",arr(List.map str value.slots);
  "record_layout_digest",str value.record_layout_digest;"availability",availability_to_json value.available]
let parse_capacity raw=exact["id";"pool_id";"unit";"scope";"quantity";"slots";"record_layout_digest";"availability"]raw;
  let slots=List.map text(rows 4(get "slots" raw))in unique "capacity slot" slots;
  {capacity_id=text(get "id" raw);pool_id=text(get "pool_id" raw);unit=C.resource_unit_of_json(get "unit" raw);
   scope=C.resource_scope_of_json(get "scope" raw);quantity=integer 1 1000000(get "quantity" raw);slots;
   record_layout_digest=pin(get "record_layout_digest" raw);available=availability(get "availability" raw)}
type channel_kind=Observation|Feedback
type channel={channel_id:string;kind:channel_kind;source:string;observer:string;subject:string;available:availability}
let channel_json(value:channel)=obj["id",str value.channel_id;"kind",str(match value.kind with Observation->"observation"|Feedback->"feedback");
  "source",str value.source;"observer",str value.observer;"subject",str value.subject;"availability",availability_to_json value.available]
let parse_channel raw=exact["id";"kind";"source";"observer";"subject";"availability"]raw;
  let kind=match get "kind" raw with Json.String "observation"->Observation|Json.String "feedback"->Feedback
    |_->Diagnostic.fail "policy_material_context" "Unknown input boundary interpretation."in
  {channel_id=text(get "id" raw);kind;source=text(get "source" raw);observer=text(get "observer" raw);
   subject=text(get "subject" raw);available=availability(get "availability" raw)}
type body=Chassis of Json.t|Environment of F.t|Interface of{environment:C.provider_ref;channels:channel list}
  |Delivery of{arrival:interval;expression:interval;activation:interval}
type provider={identity:P.t;definition:C.provider_ref;recipient:recipient;available:availability;capacities:capacity list;body:body}
let provider_body_to_json(value:provider)=
  let fields=match value.body with
    |Chassis chassis->["kind",str "chassis";"chassis",chassis]
    |Environment domain->["kind",str "environment";"grammar_profile",str "exact_finite_policy_grammar_v1";"grammar",F.to_json domain]
    |Interface value->["kind",str "interface";"environment",C.provider_ref_to_json value.environment;"channels",arr(List.map channel_json value.channels)]
    |Delivery value->["kind",str "delivery";"arrival",interval_json value.arrival;"expression",interval_json value.expression;"activation",interval_json value.activation]in
  obj(fields@["definition",C.provider_ref_to_json value.definition;"recipient",recipient_to_json value.recipient;
    "availability",availability_to_json value.available;"capacities",arr(List.map capacity_json value.capacities)])
let provider_to_json(value:provider)=obj["schema_version",str provider_schema;"identity",P.to_json value.identity;"body",provider_body_to_json value]
let parse_provider raw=exact["schema_version";"identity";"body"]raw;
  require(get "schema_version" raw=str provider_schema)"Unknown provider schema.";
  let body=get "body" raw and identity=P.of_json(get "identity" raw)in
  require(P.kind identity=P.Model)"Executable provider bodies require model identities.";
  let common=["kind";"definition";"recipient";"availability";"capacities"]in
  let body_value=match get "kind" body with
    |Json.String "chassis"->exact(common@["chassis"])body;
      let chassis=get "chassis" body in
      exact["$type";"id";"version";"species";"recipient_class";"lineage";"subtype";
        "differentiation_states";"activation_states";"capabilities";"interfaces";"environment";"operational_model"]chassis;
      require(get "$type" chassis=str "ChassisProfile")"Original chassis must retain its typed source declaration.";
      List.iter(fun key->ignore(text(get key chassis)))["id";"version";"species";"recipient_class";"lineage";"subtype"];
      List.iter(fun key->List.iter(fun raw->ignore(text raw))(rows 128(get key chassis)))["differentiation_states";"activation_states"];
      List.iter(fun key->List.iter(fun raw->ignore(C.provider_ref_of_json raw))(rows 128(get key chassis)))["capabilities";"interfaces";"environment"];
      ignore(C.provider_ref_of_json(get "operational_model" chassis));Chassis chassis
    |Json.String "environment"->exact(common@["grammar_profile";"grammar"])body;
      require(get "grammar_profile" body=str "exact_finite_policy_grammar_v1")"Unsupported environment grammar.";
      Environment(F.of_json(get "grammar" body))
    |Json.String "interface"->exact(common@["environment";"channels"])body;
      let channels=List.map parse_channel(rows 256(get "channels" body))in
      unique "channel"(List.map(fun(value:channel)->value.channel_id)channels);
      Interface{environment=C.provider_ref_of_json(get "environment" body);channels}
    |Json.String "delivery"->exact(common@["arrival";"expression";"activation"])body;
      Delivery{arrival=interval(get "arrival" body);expression=interval(get "expression" body);activation=interval(get "activation" body)}
    |_->Diagnostic.fail "policy_material_context" "Unsupported provider body kind."in
  let capacities=List.map parse_capacity(rows 4096(get "capacities" body))in
  unique "capacity"(List.map(fun(value:capacity)->value.capacity_id)capacities);
  let value={identity;definition=C.provider_ref_of_json(get "definition" body);recipient=parse_recipient(get "recipient" body);
    available=availability(get "availability" body);capacities;body=body_value}in
  require(P.content_fingerprint identity=Canonical.fingerprint(provider_body_to_json value))"Provider identity does not pin its full typed body.";
  value
type delivery_mode=Co_delivered|Independent
type delivery_group={group_id:string;recipient_roles:string list;mode:delivery_mode;same_recipient:bool;
  assumptions:string list;exact_count:int option;max_count:int option;max_total_bases:int option}
let delivery_group_json(value:delivery_group)=
  let optional=function None->Json.Null|Some number->Json.int number in
  obj["schema_version",str delivery_group_schema;"id",str value.group_id;
    "recipient_roles",arr(List.map str value.recipient_roles);
    "mode",str(match value.mode with Co_delivered->"co_delivered"|Independent->"independent");
    "same_recipient",Json.Bool value.same_recipient;"assumptions",arr(List.map str value.assumptions);
    "exact_count",optional value.exact_count;"max_count",optional value.max_count;
    "max_total_bases",optional value.max_total_bases]
let parse_delivery_group raw=
  exact["schema_version";"id";"recipient_roles";"mode";"same_recipient";"assumptions";
    "exact_count";"max_count";"max_total_bases"]raw;
  require(get "schema_version" raw=str delivery_group_schema)"Unsupported policy delivery group schema.";
  let recipient_roles=List.map text(rows 4096(get "recipient_roles" raw))
  and assumptions=List.map text(rows 64(get "assumptions" raw))in
  require(recipient_roles<>[])"Policy delivery needs an explicit recipient role inventory.";
  unique "delivery recipient" recipient_roles;unique "delivery assumption" assumptions;
  let mode=match get "mode" raw with Json.String "co_delivered"->Co_delivered|Json.String "independent"->Independent
    |_->Diagnostic.fail "policy_material_context" "Unknown policy delivery mode."in
  let optional maximum key=match get key raw with Json.Null->None|value->Some(integer 0 maximum value)in
  let exact_count=optional 4096 "exact_count" and max_count=optional 4096 "max_count"in
  require(match exact_count,max_count with Some exact,Some maximum->exact<=maximum|_->true)
    "Exact policy RNA count exceeds the maximum count.";
  {group_id=text(get "id" raw);recipient_roles;mode;same_recipient=Json.boolean(get "same_recipient" raw);
    assumptions;exact_count;max_count;max_total_bases=optional M.max_residues "max_total_bases"}
type t={clock:clock;recipient:recipient;record_layout:record_layout;placement:A.Placement.t;
  delivery_group:delivery_group;helpers:A.Helper.t list;providers:provider list}
let to_json(value:t)=obj["schema_version",str schema_version;"profile",str profile;
  "clock",clock_json value.clock;"recipient",recipient_to_json value.recipient;
  "record_layout",record_layout_to_json value.record_layout;"placement",A.Placement.to_json value.placement;
  "delivery_group",delivery_group_json value.delivery_group;"helpers",arr(List.map A.Helper.to_json value.helpers);
  "providers",arr(List.map provider_to_json value.providers)]
let of_json raw=
  M.check_resources raw;
  exact["schema_version";"profile";"clock";"recipient";"record_layout";"placement";"delivery_group";"helpers";"providers"]raw;
  require(get "schema_version" raw=str schema_version && get "profile" raw=str profile)"Unsupported material context profile.";
  let providers=List.map parse_provider(rows 128(get "providers" raw))in
  unique "provider definition"(List.map(fun(value:provider)->Canonical.encode(C.provider_ref_to_json value.definition))providers);
  unique "provider identity"(List.map(fun(value:provider)->P.kind_name value.identity^":"^P.id value.identity^":"^P.version value.identity)providers);
  unique "capacity pool"(List.concat_map(fun(value:provider)->List.map(fun(capacity:capacity)->capacity.pool_id)value.capacities)providers);
  let value={clock=parse_clock(get "clock" raw);recipient=parse_recipient(get "recipient" raw);
    record_layout=parse_layout(get "record_layout" raw);placement=A.Placement.of_json(get "placement" raw);
    delivery_group=parse_delivery_group(get "delivery_group" raw);
    helpers=List.map(fun raw->A.Helper.of_json raw)(rows 128(get "helpers" raw));providers}in
  M.check_resources(to_json value);value
let fingerprint value=Canonical.fingerprint(to_json value)
let clock(value:t)=value.clock
let recipient(value:t)=value.recipient
let record_layout(value:t)=value.record_layout
let placement(value:t)=value.placement
let delivery_group(value:t)=value.delivery_group
let helpers(value:t)=value.helpers
let providers(value:t)=value.providers

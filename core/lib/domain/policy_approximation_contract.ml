open Bioc_wire
module Network = Policy_quantitative_network_contract
let schema_version="biocompiler.policy_approximation_contract.v0.1"
let profile="biocompiler.policy_bounded_sampled_network_approximation.v0.1"
type rational={raw:Json.t;value:Q.t;unit:Json.t}
type endpoint={raw:Json.t;mechanism:Network.mechanism;observation:string list}
type parameter=Initial|Transfer_amount
type interval={parameter:parameter;id:string;lower:int;upper:int}
type link={raw:Json.t;id:string;source:endpoint;target:endpoint;uncertainty:interval list;maximum_error:rational}
type t={raw:Json.t;horizon_steps:int;coordinates:string list;unit:Json.t;maximum_error:rational;links:link list}
let str value=Json.String value
let obj fields=Json.Object fields
let get key raw=Json.field key(Json.object_fields raw)
let exact keys raw=Json.exact_fields keys(Json.object_fields raw)
let require condition message=Diagnostic.require condition "policy_approximation_contract" message
let name raw=let value=Json.name raw in require(String.length value<=256)"Approximation identity exceeds its bound.";value
let parameter_name=function Initial->"initial"|Transfer_amount->"transfer_amount"
let rational_to_json ~unit value=obj["numerator",str(Z.to_string(Q.num value));"denominator",str(Z.to_string(Q.den value));"unit",unit]
let integer raw=
  let text=Json.string raw in
  require(String.length text>0 && String.length text<=256 &&
    (String.length text=1 || text.[0]<>'0') && String.for_all(fun ch->ch>='0'&&ch<='9')text)
    "Rational integers require bounded canonical nonnegative decimal digits.";
  Z.of_string text
let rational unit raw=
  exact["numerator";"denominator";"unit"]raw;
  let numerator=integer(get "numerator" raw)and denominator=integer(get "denominator" raw)in
  require(Z.sign denominator>0 && Z.equal(Z.gcd numerator denominator)Z.one)
    "Rational bounds require a positive denominator and a normalized numerator/denominator.";
  require(Json.equal unit(get "unit" raw))"Error bounds must preserve the complete nominal quantity unit.";
  {raw;value=Q.make numerator denominator;unit}
let count label low high raw=let value=Json.integer raw in
  require(Z.compare value(Z.of_int low)>=0 && Z.compare value(Z.of_int high)<=0)label;Z.to_int value
let endpoint charge unit coordinates raw=
  exact["mechanism";"observation"]raw;
  let mechanism=Network.of_json ~charge(get "mechanism" raw)in
  require(Json.equal unit mechanism.unit)"Approximation endpoints must use the complete common nominal unit.";
  let observation=List.map name(Molecular_record.array ~maximum:4(get "observation" raw))in
  require(List.length observation=List.length coordinates && List.length(List.sort_uniq String.compare observation)=List.length observation)
    "Observation maps must retain one distinct named reservoir for every semantic coordinate.";
  require(List.for_all(fun compartment->List.exists(fun(r:Network.reservoir)->r.compartment=compartment)mechanism.reservoirs)observation)
    "Observation maps may only name reservoirs in their complete endpoint mechanism.";
  {raw;mechanism;observation}
let interval (source:endpoint) raw=
  exact["parameter";"id";"lower_quanta";"upper_quanta"]raw;
  let parameter=match Json.string(get "parameter" raw)with
    |"initial"->Initial|"transfer_amount"->Transfer_amount|_->Diagnostic.fail "policy_approximation_contract" "Unsupported continuous or unbounded uncertainty parameter."in
  let id=name(get "id" raw)in
  let lower=count "Uncertainty lower quantum bound is outside the finite grid." 0 15(get "lower_quanta" raw)
  and upper=count "Uncertainty upper quantum bound is outside the finite grid." 0 15(get "upper_quanta" raw)in
  let mechanism=source.mechanism in
  let nominal,maximum=match parameter with
    |Initial->(match List.find_opt(fun(r:Network.reservoir)->r.compartment=id)mechanism.reservoirs with
      |Some reservoir->reservoir.initial.amount,reservoir.levels-1
      |None->Diagnostic.fail "policy_approximation_contract" "Initial uncertainty names an absent reservoir.")
    |Transfer_amount->(match List.find_opt(fun(e:Network.transfer)->e.id=id)mechanism.transfers with
      |Some edge->let donor=List.find(fun(r:Network.reservoir)->r.compartment=edge.source)mechanism.reservoirs in
        edge.amount.amount,donor.levels-1
      |None->Diagnostic.fail "policy_approximation_contract" "Amount uncertainty names an absent transfer.")in
  let nominal=Z.to_int(Q.num(Q.div nominal mechanism.quantum.amount))in
  require(lower<=nominal && nominal<=upper && lower<=upper && upper<=maximum &&
    (parameter<>Transfer_amount || lower>0))
    "Closed uncertainty intervals must include the nominal parameter and every quantum must remain in its original grid.";
  {parameter;id;lower;upper}
let of_json ?(charge=fun _->()) raw=
  ignore(Policy_material_request.preflight ~max_bytes:1048576 ~max_nodes:65536 ~max_depth:64 ~charge raw);
  exact["schema_version";"profile";"horizon_steps";"metric";"coordinates";"unit";"maximum_error";"links"]raw;
  require(get "schema_version" raw=str schema_version && get "profile" raw=str profile &&
    get "metric" raw=str "coordinatewise_absolute_prefix_error")"Unknown bounded approximation contract or metric.";
  let horizon_steps=count "Approximation horizon must contain one to sixty-four complete sample rounds." 1 64(get "horizon_steps" raw)in
  let coordinates=List.map name(Molecular_record.array ~maximum:4(get "coordinates" raw))in
  require(coordinates<>[] && List.length(List.sort_uniq String.compare coordinates)=List.length coordinates)
    "Approximation coordinates must be a nonempty unique ordered census.";
  let unit=get "unit" raw in
  let links=List.mapi(fun index raw->
    exact["id";"source";"target";"uncertainty";"maximum_error"]raw;
    let source=endpoint charge unit coordinates(get "source" raw)and target=endpoint charge unit coordinates(get "target" raw)in
    require(source.mechanism.substance=target.mechanism.substance &&
      Json.equal source.mechanism.sample_period.raw target.mechanism.sample_period.raw)
      "Each approximation link must preserve substance identity and the complete sampling clock.";
    let uncertainty=List.map(interval source)(Molecular_record.array ~maximum:8(get "uncertainty" raw))in
    require(index=0 || uncertainty=[])"Only the original reference endpoint may introduce uncertainty in this chain profile.";
    require(List.length(List.sort_uniq compare(List.map(fun(v:interval)->v.parameter,v.id)uncertainty))=List.length uncertainty)
      "An uncertainty parameter may occur only once.";
    let cases=List.fold_left(fun total(v:interval)->charge 1;let next=total*(v.upper-v.lower+1)in
      require(next<=8)"The complete Cartesian uncertainty census exceeds eight; sampling or clipping is forbidden.";next)1 uncertainty in
    ignore cases;
    {raw;id=name(get "id" raw);source;target;uncertainty;maximum_error=rational unit(get "maximum_error" raw)})
    (Molecular_record.array ~maximum:4(get "links" raw))in
  require(links<>[] && List.length(List.sort_uniq String.compare(List.map(fun(v:link)->v.id)links))=List.length links)
    "Approximation chains require one to four uniquely named links.";
  let rec connected=function
    |first::(second::_ as rest)->require(Json.equal first.target.raw second.source.raw)
        "Approximation composition requires byte-equivalent complete middle laws and observation maps.";connected rest
    |_->()in connected links;
  {raw;horizon_steps;coordinates;unit;maximum_error=rational unit(get "maximum_error" raw);links}
let set key item raw=obj(List.map(fun(name,value)->name,if name=key then item else value)(Json.object_fields raw))
let exact_decimal value=
  let denominator=Q.den value in
  let rec decimal places power=
    require(places<=1024)"Uncertainty quantum is outside the finite decimal scale.";
    if Z.equal(Z.rem power denominator)Z.zero then places,power else decimal(places+1)(Z.mul power(Z.of_int 10))in
  let places,power=decimal 0 Z.one in
  let numerator=Z.mul(Q.num value)(Z.div power denominator)in
  if places=0 then Z.to_string numerator else
  let digits=Z.to_string numerator in
  let digits=if String.length digits<=places then String.make(places+1-String.length digits)'0'^digits else digits in
  let split=String.length digits-places in
  let text=String.sub digits 0 split^"."^String.sub digits split places in
  let last=ref(String.length text)in
  while !last>0 && text.[!last-1]='0' do decr last done;
  if !last>0 && text.[!last-1]='.' then decr last;
  String.sub text 0 !last
let cases ?(charge=fun _->()) (link:link)=
  let expand raw (range:interval) amount=
    charge 1;
    let quantum=link.source.mechanism.quantum.amount in
    let quantity=obj["$type",str "Quantity";"amount",str(exact_decimal(Q.mul quantum(Q.of_int amount)));"unit",link.source.mechanism.unit]in
    let field,key,target=match range.parameter with Initial->"reservoirs","compartment","initial"|Transfer_amount->"transfers","id","amount"in
    let values=List.map(fun row->charge 1;if get key row=str range.id then set target quantity row else row)(Json.array(get field raw))in
    set field(Json.Array values)raw in
  let originals=List.fold_left(fun raws range->List.concat_map(fun raw->List.init(range.upper-range.lower+1)(fun index->expand raw range(range.lower+index)))raws)
    [Network.to_json link.source.mechanism]link.uncertainty in
  List.map(Network.of_json ~charge)originals
let to_json(value:t)=value.raw

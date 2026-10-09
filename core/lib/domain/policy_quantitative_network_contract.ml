open Bioc_wire
module Pin = Pinned_identity
let schema_version="biocompiler.policy_sampled_transfer_network.v0.1"
let profile="biocompiler.policy_sampled_reserved_transfer_network.v0.1"
type quantity={raw:Json.t;amount:Q.t;unit:Json.t}
type reservoir={compartment:string;capacity:quantity;initial:quantity;levels:int}
type transfer={id:string;source:string;destination:string;amount:quantity;enabled_when:bool}
type threshold={compartment:string;amount:quantity}
type arbitration=Declared_order_prestate_reservation
type ownership=Single_atomic_state_owner
let arbitration_name Declared_order_prestate_reservation="declared_order_prestate_reservation"
let ownership_name Single_atomic_state_owner="single_atomic_state_owner"
type mechanism={raw:Json.t;substance:string;unit:Json.t;quantum:quantity;
  reservoirs:reservoir list;transfers:transfer list;threshold:threshold;
  sample_period:quantity;arbitration:arbitration;ownership:ownership;levels:int}
type state_value={state:string;amounts:quantity list}
type output_site={source_state:string;input:bool;boundary:string;model:Pin.t}
type local_contract={raw:Json.t;id:string;mechanism:mechanism;
  state_node:string;state_model:Pin.t;values:state_value list;
  input_node:string;input_model:Pin.t;value_port:string;updated_port:string;outputs:output_site list}
type selection={raw:Json.t;mechanism:mechanism;instance:string;component:Pin.t;
  contract:string;machine:string;observation:string;effect:string}
let get key raw=Json.field key(Json.object_fields raw)
let exact keys raw=Json.exact_fields keys(Json.object_fields raw)
let str value=Json.String value
let require condition message=Diagnostic.require condition "policy_quantitative_network_contract" message
let name raw=let value=Json.name raw in
  require(String.length value<=256)"Network identity exceeds its bound.";value
let preflight charge raw=ignore(Policy_material_request.preflight
  ~max_bytes:131072 ~max_nodes:8192 ~max_depth:32 ~charge raw)
let decimal raw=let value=Json.string raw in
  require(String.length value<=256)"Exact network decimal exceeds its bound.";
  Policy_document.exact_decimal value
let unit raw=
  exact["$type";"id";"dimension";"quantity_kind";"scale";"reference"]raw;
  require(get "$type" raw=str "Unit")"Network units require complete policy Unit records.";
  ignore(name(get "id" raw));ignore(name(get "dimension" raw));ignore(name(get "quantity_kind" raw));
  require(Q.sign(decimal(get "scale" raw))>0)"Network unit scale must be exact and positive.";
  (match get "reference" raw with Json.Null->()|value->ignore(name value));raw
let quantity expected raw=
  exact["$type";"amount";"unit"]raw;
  require(get "$type" raw=str "Quantity")"Network amounts require complete policy Quantity records.";
  let actual=unit(get "unit" raw)in
  require(Json.equal expected actual)"Network amounts preserve the complete nominal unit; conversion is unsupported.";
  {raw;amount=decimal(get "amount" raw);unit=actual}
let integral value=Z.equal(Q.den value)Z.one
let unit_of_json raw=unit raw
let mechanism raw=
  exact["schema_version";"profile";"substance";"unit";"quantum";"reservoirs";"transfers";
    "threshold";"sample_period";"arbitration";"ownership"]raw;
  require(get "schema_version" raw=str schema_version && get "profile" raw=str profile)
    "Unknown reserved transfer network profile.";
  require(get "arbitration" raw=str(arbitration_name Declared_order_prestate_reservation) &&
    get "ownership" raw=str(ownership_name Single_atomic_state_owner))
    "Network transfers require explicit declared-order prestate reservations and one atomic state owner.";
  let unit=unit(get "unit" raw)in
  require(List.mem(Json.string(get "dimension" unit),Json.string(get "quantity_kind" unit))
    ["count","count";"amount","amount"])
    "Networks use explicit count/count or amount/amount units.";
  let quantum=quantity unit(get "quantum" raw)in
  require(Q.sign quantum.amount>0)"The shared network quantum must be positive.";
  let on_grid(value:quantity)=integral(Q.div value.amount quantum.amount)in
  let reservoir raw=
    exact["compartment";"capacity";"initial"]raw;
    let capacity=quantity unit(get "capacity" raw)and initial=quantity unit(get "initial" raw)in
    let intervals=Q.div capacity.amount quantum.amount in
    require(on_grid capacity && Q.compare intervals(Q.of_int 1)>=0 && Q.compare intervals(Q.of_int 15)<=0 &&
      on_grid initial && Q.sign initial.amount>=0 && Q.compare initial.amount capacity.amount<=0)
      "Each network reservoir requires two-to-sixteen exact grid levels and an in-range initial amount.";
    {compartment=name(get "compartment" raw);capacity;initial;levels=1+Z.to_int(Q.num intervals)}in
  let reservoirs=List.map reservoir(Molecular_record.array ~maximum:4(get "reservoirs" raw))in
  require(List.length reservoirs>=2)"A transfer network requires two-to-four named reservoirs.";
  let compartments=List.map(fun(value:reservoir)->value.compartment)reservoirs in
  require(List.length(List.sort_uniq String.compare compartments)=List.length compartments)
    "Network compartments must be distinct nominal identities.";
  let levels=List.fold_left(fun total(value:reservoir)->total*value.levels)1 reservoirs in
  require(levels<=16)"The complete Cartesian network grid exceeds sixteen states.";
  let lookup identity=match List.find_opt(fun(value:reservoir)->value.compartment=identity)reservoirs with
    |Some value->value|None->Diagnostic.fail "policy_quantitative_network_contract" "Network transfer or threshold names an absent compartment."in
  let transfers=List.map(fun raw->exact["id";"source";"destination";"amount";"when"]raw;
    let source=name(get "source" raw)and destination=name(get "destination" raw)in
    let donor=lookup source in ignore(lookup destination);
    require(source<>destination)"Network transfers must name distinct donor and receiver compartments.";
    let amount=quantity unit(get "amount" raw)in
    require(on_grid amount && Q.sign amount.amount>0 && Q.compare amount.amount donor.capacity.amount<=0)
      "Every transfer requires a positive donor-bounded grid amount.";
    {id=name(get "id" raw);source;destination;amount;enabled_when=Json.boolean(get "when" raw)})
    (Molecular_record.array ~maximum:8(get "transfers" raw))in
  require(transfers<>[] && List.length(List.sort_uniq String.compare(List.map(fun(value:transfer)->value.id)transfers))=List.length transfers)
    "Networks require one-to-eight transfers with distinct identities in declared priority order.";
  let threshold_raw=get "threshold" raw in exact["compartment";"amount"]threshold_raw;
  let compartment=name(get "compartment" threshold_raw)in
  let owner=lookup compartment and amount=quantity unit(get "amount" threshold_raw)in
  require(on_grid amount && Q.sign amount.amount>0 && Q.compare amount.amount owner.capacity.amount<=0)
    "The named threshold must be a positive in-range grid amount.";
  let threshold={compartment;amount}in
  let period_raw=get "sample_period" raw in
  let period_unit=unit_of_json(get "unit" period_raw)in
  require(get "dimension" period_unit=str "time" && get "quantity_kind" period_unit=str "duration" &&
    get "reference" period_unit=Json.Null)"Network sampling requires an unreferenced time-duration unit.";
  let sample_period=quantity period_unit period_raw in
  require(Q.sign sample_period.amount>0)"Network sample period must be positive.";
  {raw;substance=name(get "substance" raw);unit;quantum;reservoirs;transfers;threshold;sample_period;
    arbitration=Declared_order_prestate_reservation;ownership=Single_atomic_state_owner;levels}
let of_json ?(charge=fun _->()) raw=preflight charge raw;mechanism raw
let model raw=let value=Pin.of_json raw in
  require(Pin.kind value=Pin.Model)"Network bindings require complete model identities.";value
let local_of_json ?(charge=fun _->()) raw=
  preflight charge raw;exact["id";"mechanism";"state";"input";"outputs"]raw;
  let mechanism=mechanism(get "mechanism" raw)in
  let state=get "state" raw and input=get "input" raw in
  exact["node";"model";"values"]state;exact["node";"model";"value_port";"updated_port"]input;
  let rows=Molecular_record.array ~maximum:16(get "values" state)in
  require(List.length rows=mechanism.levels)"The local map must retain the complete Cartesian network grid.";
  let values=List.mapi(fun index raw->exact["state";"amounts"]raw;
    let amounts=List.map(quantity mechanism.unit)(Molecular_record.array ~maximum:4(get "amounts" raw))in
    require(List.length amounts=List.length mechanism.reservoirs)"Each network state requires all reservoir coordinates.";
    let rec aligned divisor reservoirs amounts=match reservoirs,amounts with
      |[],[]->()
      |(reservoir:reservoir)::rest,(amount:quantity)::tail->
        let divisor=divisor/reservoir.levels in
        require(Q.equal amount.amount(Q.mul(Q.of_int((index/divisor)mod reservoir.levels))mechanism.quantum.amount))
          "Network states must enumerate the exact first-coordinate-major Cartesian grid without projection.";
        aligned divisor rest tail
      |_->assert false in
    aligned mechanism.levels mechanism.reservoirs amounts;
    {state=name(get "state" raw);amounts})rows in
  require(List.length(List.sort_uniq String.compare(List.map(fun(value:state_value)->value.state)values))=List.length values)
    "Network state labels must be unique.";
  let outputs=List.map(fun raw->exact["source_state";"input";"boundary";"model"]raw;
    {source_state=name(get "source_state" raw);input=Json.boolean(get "input" raw);
      boundary=name(get "boundary" raw);model=model(get "model" raw)})
    (Molecular_record.array ~maximum:32(get "outputs" raw))in
  require(outputs<>[])"The network contract requires all threshold-crossing outputs.";
  require(List.length(List.sort_uniq compare(List.map(fun(value:output_site)->value.source_state,value.input)outputs))=List.length outputs &&
    List.length(List.sort_uniq String.compare(List.map(fun(value:output_site)->value.boundary)outputs))=List.length outputs)
    "Network crossing coordinates and output boundaries must be unique.";
  {raw;id=name(get "id" raw);mechanism;state_node=name(get "node" state);state_model=model(get "model" state);values;
    input_node=name(get "node" input);input_model=model(get "model" input);value_port=name(get "value_port" input);
    updated_port=name(get "updated_port" input);outputs}
let selection_of_json ?(charge=fun _->()) raw=
  preflight charge raw;exact["mechanism";"selection";"source"]raw;
  let selected=get "selection" raw and source=get "source" raw in
  exact["instance";"component";"contract"]selected;exact["machine";"observation";"effect"]source;
  {raw;mechanism=mechanism(get "mechanism" raw);instance=name(get "instance" selected);
    component=model(get "component" selected);contract=name(get "contract" selected);
    machine=name(get "machine" source);observation=name(get "observation" source);effect=name(get "effect" source)}
let to_json(value:mechanism)=value.raw
let local_to_json(value:local_contract)=value.raw
let selection_to_json(value:selection)=value.raw

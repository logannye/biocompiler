open Bioc_wire
module Pin = Pinned_identity
let schema_version="biocompiler.policy_sampled_transfer_pair.v0.1"
let profile="biocompiler.policy_sampled_conservative_transfer_pair.v0.1"
type quantity={raw:Json.t;amount:Q.t;unit:Json.t}
type reservoir={compartment:string;capacity:quantity;initial:quantity;levels:int}
type mechanism={raw:Json.t;substance:string;unit:Json.t;quantum:quantity;
  source:reservoir;destination:reservoir;forward:quantity;reverse:quantity;
  threshold:quantity;sample_period:quantity;levels:int}
type state_value={state:string;source:quantity;destination:quantity}
type output_site={source_state:string;input:bool;boundary:string;model:Pin.t}
type local_contract={raw:Json.t;id:string;mechanism:mechanism;
  state_node:string;state_model:Pin.t;values:state_value list;
  input_node:string;input_model:Pin.t;value_port:string;updated_port:string;outputs:output_site list}
type selection={raw:Json.t;mechanism:mechanism;instance:string;component:Pin.t;
  contract:string;machine:string;observation:string;effect_value:string}
let get key raw=Json.field key(Json.object_fields raw)
let exact keys raw=Json.exact_fields keys(Json.object_fields raw)
let str value=Json.String value
let require condition message=Diagnostic.require condition "policy_quantitative_transfer_contract" message
let name raw=let value=Json.name raw in
  require(String.length value<=256)"Transfer identity exceeds its bound.";value
let preflight charge raw=ignore(Policy_material_request.preflight
  ~max_bytes:131072 ~max_nodes:8192 ~max_depth:32 ~charge raw)
let decimal raw=let value=Json.string raw in
  require(String.length value<=256)"Exact transfer decimal exceeds its bound.";
  Policy_document.exact_decimal value
let unit raw=
  exact["$type";"id";"dimension";"quantity_kind";"scale";"reference"]raw;
  require(get "$type" raw=str "Unit")"Transfer units require complete policy Unit records.";
  ignore(name(get "id" raw));ignore(name(get "dimension" raw));ignore(name(get "quantity_kind" raw));
  require(Q.sign(decimal(get "scale" raw))>0)"Transfer unit scale must be exact and positive.";
  (match get "reference" raw with Json.Null->()|value->ignore(name value));raw
let quantity expected raw=
  exact["$type";"amount";"unit"]raw;
  require(get "$type" raw=str "Quantity")"Transfer amounts require complete policy Quantity records.";
  let actual=unit(get "unit" raw)in
  require(Json.equal expected actual)"Transfer amounts preserve the complete nominal unit; conversion is unsupported.";
  {raw;amount=decimal(get "amount" raw);unit=actual}
let integral value=Z.equal(Q.den value)Z.one
let unit_of_json raw=unit raw
let mechanism raw=
  exact["schema_version";"profile";"substance";"unit";"quantum";"source";"destination";
    "forward";"reverse";"threshold";"sample_period"]raw;
  require(get "schema_version" raw=str schema_version && get "profile" raw=str profile)
    "Unknown reversible transfer mechanism profile.";
  let unit=unit(get "unit" raw)in
  require(List.mem(Json.string(get "dimension" unit),Json.string(get "quantity_kind" unit))
    ["count","count";"amount","amount"])
    "Transfer uses explicit count/count or amount/amount units.";
  let quantum=quantity unit(get "quantum" raw)in
  require(Q.sign quantum.amount>0)"The shared transfer quantum must be positive.";
  let on_grid(value:quantity)=integral(Q.div value.amount quantum.amount)in
  let reservoir raw=
    exact["compartment";"capacity";"initial"]raw;
    let capacity=quantity unit(get "capacity" raw)and initial=quantity unit(get "initial" raw)in
    let intervals=Q.div capacity.amount quantum.amount in
    require(on_grid capacity && Q.compare intervals(Q.of_int 1)>=0 && Q.compare intervals(Q.of_int 15)<=0 &&
      on_grid initial && Q.sign initial.amount>=0 && Q.compare initial.amount capacity.amount<=0)
      "Each transfer reservoir requires two-to-sixteen exact grid levels and an in-range initial amount.";
    {compartment=name(get "compartment" raw);capacity;initial;levels=1+Z.to_int(Q.num intervals)}in
  let source=reservoir(get "source" raw)and destination=reservoir(get "destination" raw)in
  require(source.compartment<>destination.compartment)"Transfer compartments must be distinct nominal identities.";
  let levels=source.levels*destination.levels in
  require(levels<=16)"The complete Cartesian transfer grid exceeds sixteen states.";
  let forward=quantity unit(get "forward" raw)and reverse=quantity unit(get "reverse" raw)
  and threshold=quantity unit(get "threshold" raw)in
  List.iter(fun((value:quantity),(capacity:quantity))->require(on_grid value && Q.sign value.amount>0 &&
    Q.compare value.amount capacity.amount<=0)"Transfer bounds and the destination threshold must be positive in-range grid amounts.")
    [forward,source.capacity;reverse,destination.capacity;threshold,destination.capacity];
  let period_raw=get "sample_period" raw in
  let period_unit=unit_of_json(get "unit" period_raw)in
  require(get "dimension" period_unit=str "time" && get "quantity_kind" period_unit=str "duration" &&
    get "reference" period_unit=Json.Null)"Transfer sampling requires an unreferenced time-duration unit.";
  let sample_period=quantity period_unit period_raw in
  require(Q.sign sample_period.amount>0)"Transfer sample period must be positive.";
  {raw;substance=name(get "substance" raw);unit;quantum;source;destination;forward;reverse;threshold;sample_period;levels}
let of_json ?(charge=fun _->()) raw=preflight charge raw;mechanism raw
let model raw=let value=Pin.of_json raw in
  require(Pin.kind value=Pin.Model)"Transfer bindings require complete model identities.";value
let local_of_json ?(charge=fun _->()) raw=
  preflight charge raw;exact["id";"mechanism";"state";"input";"outputs"]raw;
  let mechanism=mechanism(get "mechanism" raw)in
  let state=get "state" raw and input=get "input" raw in
  exact["node";"model";"values"]state;exact["node";"model";"value_port";"updated_port"]input;
  let rows=Molecular_record.array ~maximum:16(get "values" state)in
  require(List.length rows=mechanism.levels)"The local map must retain the complete Cartesian transfer grid.";
  let values=List.mapi(fun index raw->exact["state";"source";"destination"]raw;
    let source=quantity mechanism.unit(get "source" raw)and destination=quantity mechanism.unit(get "destination" raw)in
    require(Q.equal source.amount(Q.mul(Q.of_int(index/mechanism.destination.levels))mechanism.quantum.amount) &&
      Q.equal destination.amount(Q.mul(Q.of_int(index mod mechanism.destination.levels))mechanism.quantum.amount))
      "Transfer states must enumerate the exact source-major Cartesian grid without projection.";
    {state=name(get "state" raw);source;destination})rows in
  require(List.length(List.sort_uniq String.compare(List.map(fun(value:state_value)->value.state)values))=List.length values)
    "Transfer state labels must be unique.";
  let outputs=List.map(fun raw->exact["source_state";"input";"boundary";"model"]raw;
    {source_state=name(get "source_state" raw);input=Json.boolean(get "input" raw);
      boundary=name(get "boundary" raw);model=model(get "model" raw)})
    (Molecular_record.array ~maximum:16(get "outputs" raw))in
  require(outputs<>[])"The transfer contract requires all threshold-crossing outputs.";
  require(List.length(List.sort_uniq compare(List.map(fun(value:output_site)->value.source_state,value.input)outputs))=List.length outputs &&
    List.length(List.sort_uniq String.compare(List.map(fun(value:output_site)->value.boundary)outputs))=List.length outputs)
    "Transfer crossing coordinates and output boundaries must be unique.";
  {raw;id=name(get "id" raw);mechanism;state_node=name(get "node" state);state_model=model(get "model" state);values;
    input_node=name(get "node" input);input_model=model(get "model" input);value_port=name(get "value_port" input);
    updated_port=name(get "updated_port" input);outputs}
let selection_of_json ?(charge=fun _->()) raw=
  preflight charge raw;exact["mechanism";"selection";"source"]raw;
  let selected=get "selection" raw and source=get "source" raw in
  exact["instance";"component";"contract"]selected;exact["machine";"observation";"effect"]source;
  {raw;mechanism=mechanism(get "mechanism" raw);instance=name(get "instance" selected);
    component=model(get "component" selected);contract=name(get "contract" selected);
    machine=name(get "machine" source);observation=name(get "observation" source);effect_value=name(get "effect" source)}
let to_json(value:mechanism)=value.raw
let local_to_json(value:local_contract)=value.raw
let selection_to_json(value:selection)=value.raw

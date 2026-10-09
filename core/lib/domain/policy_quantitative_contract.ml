open Bioc_wire
module Pin = Pinned_identity
let schema_version = "biocompiler.policy_sampled_reservoir.v0.1"
let profile = "biocompiler.policy_sampled_saturating_reservoir.v0.1"
let step_schema_version = "biocompiler.policy_sampled_reservoir.v0.2"
let step_profile = "biocompiler.policy_sampled_saturating_step_reservoir.v0.1"
type quantity = {raw:Json.t;amount:Q.t;unit:Json.t}
type mechanism = {raw:Json.t;unit:Json.t;substance:string;compartment:string;
  quantum:quantity;capacity:quantity;threshold:quantity;initial:quantity;sample_period:quantity;
  rise:quantity;fall:quantity;multi_site:bool;levels:int}
type state_value = {state:string;quantity:quantity}
type output_site = {source_state:string;input:bool;boundary:string;model:Pin.t}
type local_contract = {raw:Json.t;id:string;mechanism:mechanism;
  state_node:string;state_model:Pin.t;values:state_value list;
  input_node:string;input_model:Pin.t;value_port:string;updated_port:string;
  output_boundary:string;output_model:Pin.t;outputs:output_site list}
type selection = {raw:Json.t;mechanism:mechanism;instance:string;component:Pin.t;
  contract:string;machine:string;observation:string;effect_value:string}
let get key raw=Json.field key(Json.object_fields raw)
let exact keys raw=Json.exact_fields keys(Json.object_fields raw)
let str value=Json.String value
let require condition message=Diagnostic.require condition "policy_quantitative_contract" message
let name raw=let value=Json.name raw in
  require(String.length value<=256)"Quantitative nominal identifier exceeds its bound.";value
let preflight charge raw=
  ignore(Policy_material_request.preflight ~max_bytes:131072 ~max_nodes:8192 ~max_depth:32 ~charge raw)
let decimal raw=
  let value=Json.string raw in
  require(String.length value<=256)"Exact quantitative decimal exceeds its bound.";
  Policy_document.exact_decimal value
let unit raw=
  exact["$type";"id";"dimension";"quantity_kind";"scale";"reference"]raw;
  require(get "$type" raw=str "Unit")"Quantitative units require the complete policy Unit record.";
  ignore(name(get "id" raw));ignore(name(get "dimension" raw));ignore(name(get "quantity_kind" raw));
  require(Q.sign(decimal(get "scale" raw))>0)"Quantitative unit scale must be exact and positive.";
  (match get "reference" raw with Json.Null->()|value->ignore(name value));raw
let quantity expected raw=
  exact["$type";"amount";"unit"]raw;
  require(get "$type" raw=str "Quantity")"Quantitative amounts require complete exact policy Quantity records.";
  let actual=unit(get "unit" raw) in
  require(Json.equal expected actual)"Quantitative amounts must preserve every nominal unit field exactly; conversion is unsupported.";
  {raw;amount=decimal(get "amount" raw);unit=actual}
let integral value=Z.equal(Q.den value)Z.one
let unit_of_period raw=
  let value=unit(get "unit" raw) in
  require(get "dimension" value=str "time" && get "quantity_kind" value=str "duration" && get "reference" value=Json.Null)
    "Sample period requires a time-duration Unit without a nominal reference.";value
let mechanism raw=
  let multi_site=get "schema_version" raw=str step_schema_version && get "profile" raw=str step_profile in
  let fields=["schema_version";"profile";"substance";"compartment";"unit";"quantum";"capacity";"threshold";"initial";"sample_period"]in
  exact(if multi_site then fields@["rise";"fall"]else fields)raw;
  require(multi_site || (get "schema_version" raw=str schema_version && get "profile" raw=str profile))
    "Unknown quantitative mechanism profile.";
  let unit=unit(get "unit" raw) in
  require(List.mem(Json.string(get "dimension" unit),Json.string(get "quantity_kind" unit))
    ["count","count";"amount","amount"])
    "Reservoir units are restricted to explicit count/count or amount/amount dimensions and kinds.";
  let quantum=quantity unit(get "quantum" raw) and capacity=quantity unit(get "capacity" raw)
  and threshold=quantity unit(get "threshold" raw) and initial=quantity unit(get "initial" raw) in
  require(Q.sign quantum.amount>0 && Q.sign capacity.amount>0 &&
    Q.sign threshold.amount>0 && Q.compare threshold.amount capacity.amount<=0 &&
    Q.sign initial.amount>=0 && Q.compare initial.amount capacity.amount<=0)
    "Reservoir quantum/capacity/threshold must be positive and initial/threshold within capacity.";
  let intervals=Q.div capacity.amount quantum.amount in
  require(integral intervals && Q.compare intervals(Q.of_int 1)>=0 && Q.compare intervals(Q.of_int 15)<=0 &&
    integral(Q.div threshold.amount quantum.amount) && integral(Q.div initial.amount quantum.amount))
    "Reservoir capacity, threshold and initial must lie on the complete two-to-sixteen-level exact grid.";
  let rise=if multi_site then quantity unit(get "rise" raw)else quantum
  and fall=if multi_site then quantity unit(get "fall" raw)else quantum in
  List.iter(fun value->require(Q.sign value.amount>0 && Q.compare value.amount capacity.amount<=0 &&
    integral(Q.div value.amount quantum.amount))
    "Sample rise and fall must be positive exact grid multiples no larger than capacity.")[rise;fall];
  let period_raw=get "sample_period" raw in
  let period_unit=unit_of_period period_raw in
  let sample_period=quantity period_unit period_raw in
  require(Q.sign sample_period.amount>0)"The sampled clock period must be positive.";
  {raw;unit;substance=name(get "substance" raw);compartment=name(get "compartment" raw);
    quantum;capacity;threshold;initial;sample_period;rise;fall;multi_site;levels=1+Z.to_int(Q.num intervals)}
let of_json ?(charge=fun _->()) raw=preflight charge raw;mechanism raw
let model raw=let pin=Pin.of_json raw in
  require(Pin.kind pin=Pin.Model)"Quantitative bindings require complete model identities.";pin
let local_of_json ?(charge=fun _->()) raw=
  preflight charge raw;
  let mechanism=mechanism(get "mechanism" raw) in
  exact["id";"mechanism";"state";"input";(if mechanism.multi_site then "outputs" else "output")]raw;
  let state=get "state" raw and input=get "input" raw in
  exact["node";"model";"values"]state;exact["node";"model";"value_port";"updated_port"]input;
  let rows=Molecular_record.array ~maximum:16(get "values" state) in
  require(List.length rows=mechanism.levels)"Local state map must retain the complete quantitative grid.";
  let values=List.mapi(fun index raw->exact["state";"quantity"]raw;
    let quantity=quantity mechanism.unit(get "quantity" raw) in
    require(Q.equal quantity.amount(Q.mul(Q.of_int index)mechanism.quantum.amount))
      "Local state map must list every ascending grid level exactly once.";
    {state=name(get "state" raw);quantity})rows in
  require(List.length(List.sort_uniq String.compare(List.map(fun value->value.state)values))=List.length values)
    "Local state labels must be unique.";
  let outputs,output_boundary,output_model=if mechanism.multi_site then
    let outputs=List.map(fun raw->exact["source_state";"input";"boundary";"model"]raw;
      let input=match get "input" raw with Json.Bool value->value|_->
        Diagnostic.fail "policy_quantitative_contract" "A quantitative output input must be a Boolean sample."in
      {source_state=name(get "source_state" raw);input;boundary=name(get "boundary" raw);model=model(get "model" raw)})
      (Molecular_record.array ~maximum:16(get "outputs" raw))in
    require(outputs<>[])"A step reservoir requires the complete nonempty crossing output inventory.";
    require(List.length(List.sort_uniq compare(List.map(fun value->value.source_state,value.input)outputs))=List.length outputs &&
      List.length(List.sort_uniq String.compare(List.map(fun value->value.boundary)outputs))=List.length outputs)
      "Step reservoir crossing sources and output boundaries must be unique.";
    let first=List.hd outputs in outputs,first.boundary,first.model
    else let output=get "output" raw in exact["boundary";"model"]output;
      [],name(get "boundary" output),model(get "model" output)in
  {raw;id=name(get "id" raw);mechanism;state_node=name(get "node" state);state_model=model(get "model" state);values;
    input_node=name(get "node" input);input_model=model(get "model" input);value_port=name(get "value_port" input);
    updated_port=name(get "updated_port" input);output_boundary;output_model;outputs}
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

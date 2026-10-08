open Bioc_wire
let schema_version = "biocompiler.policy_implementation_binding.v0.1"
let profile = "biocompiler.policy_exclusive_source_graph.v0.1"
let staged_schema_version = "biocompiler.policy_implementation_binding.v0.2"
let staged_profile = "biocompiler.policy_staged_source_graph.v0.1"
type observation = { source:string; bank:string; input:string }
type state = { source:string; register:string }
type effect_binding = { source:string; bank:string; feedback:string }
type rule = { source:string; gate:string; arbiter:string; lane:int; commit:string }
type machine = { source:string; bank:string }
type transition = rule
type t = { raw:Json.t; entry:string; observation_values:observation list;
  state_values:state list; effect_values:effect_binding list; rule_values:rule list;
  machine_values:machine list; transition_values:transition list; staged:bool }
let get key value = Json.field key(Json.object_fields value)
let text key value = Json.string(get key value)
let require condition message = Diagnostic.require condition "policy_implementation_binding" message
let exact keys value = Json.exact_fields keys(Json.object_fields value)
let name key value = let result=Json.name(get key value)in
  require(String.length result<=256)"Source/graph anchor name exceeds its bound.";result
let decode maximum keys parse value =
  let values=Json.array value in
  require(List.length values<=maximum)"Source/graph anchor inventory exceeds its bound.";
  List.map(fun value->exact keys value;parse value)values
let unique label values = require(List.length values=List.length(List.sort_uniq String.compare values))
  ("Duplicate source/graph "^label^" anchor.")
let of_json raw =
  ignore(Policy_document.document_digest raw);
  let fields=Json.object_fields raw in
  let staged=List.assoc_opt "schema_version" fields=Some(Json.String staged_schema_version) &&
    List.assoc_opt "profile" fields=Some(Json.String staged_profile) in
  exact(["schema_version";"profile";"catalog_entry";"observations";"states";"effects";"rules"] @
    (if staged then ["machines";"transitions"] else []))raw;
  require(staged || (text "schema_version" raw=schema_version && text "profile" raw=profile))
    "Unsupported source/graph binding schema/profile.";
  let observation_values=decode 1 ["source";"bank";"input"](fun v->
    ({source=name "source" v;bank=name "bank" v;input=name "input" v}:observation))(get "observations" raw)
  and state_values=decode 2 ["source";"register"](fun v->
    ({source=name "source" v;register=name "register" v}:state))(get "states" raw)
  and effect_values=decode (if staged then 2 else 1) ["source";"bank";"feedback"](fun v->
    ({source=name "source" v;bank=name "bank" v;feedback=name "feedback" v}:effect_binding))(get "effects" raw)
  and rule_values=decode 2 ["source";"gate";"arbiter";"lane";"commit"](fun v->
    let lane=Json.integer(get "lane" v)in
    require(Z.sign lane>=0 && Z.compare lane (Z.of_int 1)<=0)"Arbiter lane exceeds this profile.";
    ({source=name "source" v;gate=name "gate" v;arbiter=name "arbiter" v;lane=Z.to_int lane;
      commit=name "commit" v}:rule))(get "rules" raw)in
  let machine_values=if staged then decode 1 ["source";"bank"]
      (fun v->({source=name "source" v;bank=name "bank" v}:machine))(get "machines" raw) else [] in
  let transition_values=if staged then decode 7 ["source";"gate";"arbiter";"lane";"commit"](fun v->
      let lane=Json.integer(get "lane" v)in
      require(Z.sign lane>=0 && Z.compare lane (Z.of_int 6)<=0)"Staged arbiter lane exceeds this profile.";
      ({source=name "source" v;gate=name "gate" v;arbiter=name "arbiter" v;lane=Z.to_int lane;
        commit=name "commit" v}:transition))(get "transitions" raw) else [] in
  unique "observation" (List.map(fun(v:observation)->v.source)observation_values);
  unique "state" (List.map(fun(v:state)->v.source)state_values);
  unique "effect" (List.map(fun(v:effect_binding)->v.source)effect_values);
  unique "rule" (List.map(fun(v:rule)->v.source)rule_values);
  unique "register" (List.map(fun(v:state)->v.register)state_values);
  unique "gate" (List.map(fun(v:rule)->v.gate)rule_values);
  unique "commit" (List.map(fun(v:rule)->v.commit)rule_values);
  unique "machine" (List.map(fun(v:machine)->v.source)machine_values);
  unique "machine bank" (List.map(fun(v:machine)->v.bank)machine_values);
  unique "transition" (List.map(fun(v:transition)->v.source)transition_values);
  unique "activation gate" (List.map(fun(v:rule)->v.gate)(rule_values@transition_values));
  unique "activation commit" (List.map(fun(v:rule)->v.commit)(rule_values@transition_values));
  if staged then (
    require(state_values=[] && rule_values=[]) "Staged binding has no separate rules or truth stores.";
    unique "effect bank" (List.map(fun(v:effect_binding)->v.bank)effect_values);
    unique "effect feedback" (List.map(fun(v:effect_binding)->v.feedback)effect_values));
  {raw;entry=name "catalog_entry" raw;observation_values;state_values;effect_values;rule_values;
   machine_values;transition_values;staged}
let to_json value=value.raw
let fingerprint value=Canonical.fingerprint value.raw
let catalog_entry value=value.entry
let observations value=value.observation_values
let states value=value.state_values
let effects value=value.effect_values
let rules value=value.rule_values
let machines value=value.machine_values
let transitions value=value.transition_values
let is_staged value=value.staged

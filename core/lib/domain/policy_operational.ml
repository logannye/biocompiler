(** Dedicated bounded operational-policy representation. Decoding is not admission,
    source correspondence, realization or biological evidence. *)
open Bioc_wire

type truth = True | False | Unknown
type value = Truth of truth | Integer of Z.t | Text of string | Quantity of Q.t * Json.t
type value_type = Truth_type | Integer_type | Text_type | Quantity_type of Json.t
type expression = {
  op : string; value_type : value_type option; args : expression list;
  reference : string option; value : value option; phase : string option;
  scope : string option;
}
type scope = Executor of string | Encounter of string
type arbitration = { mode : string; tie : string; write_conflict : string; order : string list }
type assignment = { state : string; value : expression }
type role = { role_id : string }
type subject = { subject_id : string; encounter : string option; executor : string option }
type encounter = { encounter_id : string; executor : string; target : string; termination : string }
type clock = { clock_id : string; resolution : Q.t }
type observation = {
  observation_id : string; observer : string; subject : string; value_type : value_type;
  clock : string; coverage : string; coherence : string; freshness : Q.t;
}
type state_store = {
  state_id : string; value_type : value_type; scope : scope; initial : value;
  capacity : int; reset : expression option; lifetime : string;
}
type lifecycle = {
  authorization : string; on_loss : string; on_unknown : string;
  timeout : Q.t option;
}
type effect = {
  effect_id : string; executor : string; subject : string; lifecycle : lifecycle;
  parameters : (string * expression) list;
}
type rule = {
  rule_id : string; executor : string; on : expression; guard : expression;
  effects : string list; assignments : assignment list; arbitration : arbitration;
}
type machine = {
  machine_id : string; executor : string; scope : scope; states : string list;
  initial : string; terminal : string list; lifetime : string; arbitration : arbitration;
}
type transition = {
  transition_id : string; machine : string; source : string; destination : string;
  on : expression; guard : expression; effects : string list; assignments : assignment list;
}
type requirement = {
  requirement_id : string; kind : string; scope : scope option;
  condition : expression option; response : expression option; trigger : expression option;
  deadline : Q.t option; horizon : Q.t option; assumptions : string list;
  source : Json.t;
}
type parameter = { parameter_id : string; value : value }
type semantic = Encounter_explicit | Observation_external_evidence | Effect_abstract_attempt
  | Lifecycle_correlated_feedback | Capability_deferred
type definition_ref = {
  definition_id : string; definition_version : string; definition_digest : string;
  definition_json : Json.t;
}
type descriptor = { definition : definition_ref; semantics : semantic }
type descriptor_bundle = { descriptor_raw : Json.t; descriptor_values : descriptor list }
type node = { id : string; kind : string; source_path : string; data : Json.t }
type behavior = {
  raw : Json.t; source_document : Json.t; definitions : descriptor_bundle;
  nodes : node list; source_ledger : Json.t; requirements_ledger : Json.t;
  assumptions : string list; unresolved_obligations : string list;
  roles : role list; subjects : subject list; encounters : encounter list;
  clocks : clock list; observations : observation list; stores : state_store list;
  effects : effect list; rules : rule list; machines : machine list;
  transitions : transition list; requirements : requirement list; parameters : parameter list;
}

let profile = "biocompiler.policy_operational.v0.1"
let descriptor_schema = "biocompiler.policy_operational_definitions.v0.1"
let behavior_schema = "biocompiler.policy_behavior.v0.1"
let get key value = Json.field key (Json.object_fields value)
let text key value = Json.string (get key value)
let list key value = Json.array (get key value)
let ref_id value = text "id" value
let option f = function Json.Null -> None | value -> Some (f value)
let strings key value = List.map Json.string (list key value)
let refs key value = List.map ref_id (list key value)
let require condition message = Diagnostic.require condition "policy_operational_representation" message
let exact fields value = Json.exact_fields fields (Json.object_fields value)
let duration value =
  Q.mul (Policy_document.exact_decimal (text "amount" value))
    (Policy_document.exact_decimal (text "scale" (get "unit" value)))
let value_type value = match text "kind" value with
  | "truth" -> Truth_type | "integer" -> Integer_type | "text" -> Text_type
  | "quantity" -> Quantity_type (get "unit" value)
  | _ -> Diagnostic.fail "policy_operational_type" "Value type has no bounded operational interpretation."
let value_of_json kind value = match kind, value with
  | Truth_type, Json.Bool true -> Truth True
  | Truth_type, Json.Bool false -> Truth False
  | Truth_type, Json.String "unknown" -> Truth Unknown
  | Integer_type, Json.Int value -> Integer value
  | Text_type, Json.String value -> Text value
  | Quantity_type unit, Json.Object _ ->
      exact ["$type";"amount";"unit"] value;
      require (text "$type" value = "Quantity") "Quantity values require the closed Quantity discriminator.";
      let actual=get "unit" value in
      exact ["$type";"id";"dimension";"quantity_kind";"scale";"reference"] actual;
      require (text "$type" actual = "Unit" && Q.sign (Policy_document.exact_decimal (text "scale" actual)) > 0)
        "Quantity unit is malformed or has a nonpositive scale.";
      require (List.for_all (fun field -> Json.equal (get field unit) (get field actual)) ["dimension";"quantity_kind";"reference"])
        "Quantity dimension, quantity kind or nominal reference differs from its declared operational type.";
      Quantity (duration value, unit)
  | _ -> Diagnostic.fail "policy_operational_value" "Malformed value for bounded operational type."
let value_to_json = function
  | Truth True -> Json.Bool true | Truth False -> Json.Bool false | Truth Unknown -> Json.String "unknown"
  | Integer value -> Json.Int value | Text value -> Json.String value
  | Quantity (value, unit) -> Json.Object ["numerator",Json.String (Z.to_string (Q.num value));
      "denominator",Json.String (Z.to_string (Q.den value));"unit",unit]
let rec expression_of_json value =
  let kind = get "value_type" value in
  let value_type = if text "kind" kind = "event" then None else Some (value_type kind) in
  let op = text "op" value in
  let literal = if op = "literal" then Option.map (fun kind -> value_of_json kind (get "value" value)) value_type else None in
  { op; value_type; args=List.map expression_of_json (list "args" value);
    reference=option ref_id (get "ref" value); value=literal;
    phase=(if op = "effect_event" then Some (text "value" value) else None);
    scope=option ref_id (get "scope" value) }
let scope value = match text "kind" value with
  | "executor" -> Executor (ref_id (get "subject" value))
  | "encounter" -> Encounter (ref_id (get "subject" value))
  | _ -> Diagnostic.fail "policy_operational_scope" "Scope is outside finite executor/encounter state."
let arbitration value =
  {mode=text "mode" value;tie=text "tie" value;write_conflict=text "write_conflict" value;order=strings "order" value}
let assignment value : assignment = {state=ref_id (get "state" value);value=expression_of_json (get "value" value)}
let assignments value = List.map assignment (list "assignments" value)
let semantic_tag = function
  | Encounter_explicit -> "encounter.explicit.v1"
  | Observation_external_evidence -> "observation.external_evidence.v1"
  | Effect_abstract_attempt -> "effect.abstract_attempt.v1"
  | Lifecycle_correlated_feedback -> "lifecycle.correlated_feedback.v1"
  | Capability_deferred -> "capability.deferred.v1"
let semantic_of_tag = function
  | "encounter.explicit.v1" -> Encounter_explicit
  | "observation.external_evidence.v1" -> Observation_external_evidence
  | "effect.abstract_attempt.v1" -> Effect_abstract_attempt
  | "lifecycle.correlated_feedback.v1" -> Lifecycle_correlated_feedback
  | "capability.deferred.v1" -> Capability_deferred
  | _ -> Diagnostic.fail "policy_operational_unsupported"
      "Unknown executable semantic descriptor; names and prose cannot supply operational meaning."
let definition_ref_to_json value = value.definition_json
let definition_ref_of_json value =
  exact ["$type";"id";"version";"digest"] value;
  require (text "$type" value = "DefinitionRef") "Descriptor must carry complete DefinitionRef identity.";
  let definition_id=Json.name (get "id" value) and definition_version=Json.name (get "version" value)
  and definition_digest=Json.name (get "digest" value) in
  require (String.length definition_digest = 64 && String.for_all (function
    | '0'..'9' | 'a'..'f' -> true | _ -> false) definition_digest)
    "Definition digest must contain exactly 64 lowercase hexadecimal SHA-256 characters.";
  {definition_id;definition_version;definition_digest;definition_json=value}
let descriptors_of_json raw =
  ignore (Policy_document.document_digest raw);
  exact ["schema_version";"profile";"definitions"] raw;
  require (text "schema_version" raw = descriptor_schema && text "profile" raw = profile) "Unsupported operational descriptor profile.";
  let definitions = list "definitions" raw in
  require (List.length definitions <= 4096) "Operational definition bound exceeded.";
  let descriptor_values = List.map (fun value ->
    exact ["definition";"semantics"] value;
    let definition=definition_ref_of_json (get "definition" value) in
    {definition;semantics=semantic_of_tag (Json.name (get "semantics" value))}) definitions in
  {descriptor_raw=raw;descriptor_values}
let descriptors_to_json value = value.descriptor_raw
let descriptors value = value.descriptor_values
let descriptors_digest value = Canonical.fingerprint value.descriptor_raw
let measure_behavior raw =
  let max_bytes=8*1024*1024 and max_nodes=400_000 and max_depth=64
  and max_string=262_144 and max_number=256 in
  let nodes=ref 0 and payload=ref 0 in
  let limit condition = Diagnostic.require ~path:"/candidate" condition
      "policy_operational_limit" "Operational candidate exceeds its closed resource profile." in
  let visit depth = incr nodes;limit (!nodes <= max_nodes && depth <= max_depth) in
  let scalar bytes = limit (bytes <= max_bytes - !payload);payload:= !payload+bytes in
  let string value = limit (String.length value <= max_string);Json.validate_utf8 value;scalar (String.length value) in
  let rec walk depth = function
    | Json.Null -> visit depth;scalar 4
    | Json.Bool value -> visit depth;scalar (if value then 4 else 5)
    | Json.Int value ->
        visit depth;limit (Z.numbits value <= 4*max_number);
        let bytes=String.length (Z.to_string value) in limit (bytes <= max_number);scalar bytes
    | Json.Float _ -> Diagnostic.fail ~path:"/candidate" "policy_operational_representation"
        "Raw floats are forbidden in exact operational candidates."
    | Json.String value -> visit depth;string value
    | Json.Array values ->
        visit depth;
        let rec items = function [] -> () | value::rest -> walk (depth+1) value;items rest in
        items values
    | Json.Object fields ->
        visit depth;
        let keys=Hashtbl.create 16 in
        let rec items = function [] -> () | (key,value)::rest ->
          visit (depth+1);string key;
          Diagnostic.require ~path:"/candidate" (not (Hashtbl.mem keys key))
            "policy_operational_representation" "Duplicate candidate object key.";
          Hashtbl.add keys key ();walk (depth+1) value;items rest in
        items fields
  in
  (* The first walk bounds every occurrence, including shared DAGs and cyclic
     caller-constructed list spines, before encoding or recursive typed decode. *)
  walk 0 raw;
  match Canonical.encode_bounded ~max_bytes raw with
  | _ -> ()
  | exception Diagnostic.Error diagnostic when diagnostic.code = "response_too_large" -> limit false
let behavior_of_json raw =
  measure_behavior raw;
  exact ["schema_version";"profile";"source_document";"descriptor_bundle";"source_artifact_digest";
    "descriptors_digest";"nodes";"source_ledger";"requirements_ledger";"assumptions";"unresolved_obligations"] raw;
  require (text "schema_version" raw = behavior_schema && text "profile" raw = profile) "Unsupported operational behavior profile.";
  let source_document=get "source_document" raw in
  let document=Policy_document.of_json source_document in
  let definitions=descriptors_of_json (get "descriptor_bundle" raw) in
  require (text "source_artifact_digest" raw = Policy_document.artifact_digest document) "Behavior source artifact pin mismatch.";
  require (text "descriptors_digest" raw = descriptors_digest definitions) "Behavior descriptor pin mismatch.";
  let nodes=List.map (fun value ->
    exact ["id";"kind";"source_path";"data"] value;
    {id=Json.name (get "id" value);kind=text "kind" value;source_path=text "source_path" value;data=get "data" value}) (list "nodes" raw) in
  require (List.length nodes <= 4096) "Operational instruction bound exceeded.";
  let selected kind f = List.filter_map (fun (node:node) -> if node.kind = kind then Some (f node.data) else None) nodes in
  let roles=selected "Role" (fun v -> {role_id=ref_id v}) in
  let subjects=selected "Subject" (fun v -> {subject_id=ref_id v;encounter=option ref_id (get "encounter" v);executor=option ref_id (get "executor" v)}) in
  let encounters=selected "Encounter" (fun v -> {encounter_id=ref_id v;executor=ref_id (get "executor" v);target=ref_id (get "target" v);termination=text "termination" v}) in
  let clocks=selected "Clock" (fun v -> {clock_id=ref_id v;resolution=duration (get "resolution" v)}) in
  let observations=selected "Observation" (fun v -> {observation_id=ref_id v;observer=ref_id (get "observer" v);subject=ref_id (get "subject" v);
    value_type=value_type (get "value_type" v);clock=ref_id (get "clock" v);coverage=text "coverage" v;coherence=text "coherence" v;freshness=duration (get "freshness" v)}) in
  let stores=selected "StateStore" (fun v -> let kind=value_type (get "value_type" v) in
    let capacity=Json.integer (get "capacity" v) in
    require (Z.fits_int capacity) "State capacity cannot be represented.";
    {state_id=ref_id v;value_type=kind;scope=scope (get "scope" v);initial=value_of_json kind (get "initial" v);
      capacity=Z.to_int capacity;reset=option expression_of_json (get "reset" v);lifetime=text "lifetime" v}) in
  let effects=selected "Effect" (fun v -> let lifecycle=get "lifecycle" v in
    {effect_id=ref_id v;executor=ref_id (get "executor" v);subject=ref_id (get "subject" v);
      lifecycle={authorization=text "authorization" lifecycle;on_loss=text "on_loss" lifecycle;on_unknown=text "on_unknown" lifecycle;timeout=option duration (get "timeout" lifecycle)};
      parameters=List.map (fun p -> text "name" p, expression_of_json (get "value" p)) (list "parameters" v)}) in
  let rules=selected "Rule" (fun v -> {rule_id=ref_id v;executor=ref_id (get "executor" v);on=expression_of_json (get "on" v);
    guard=expression_of_json (get "when" v);effects=refs "effects" v;assignments=assignments v;arbitration=arbitration (get "arbitration" v)}) in
  let machines=selected "Machine" (fun v -> {machine_id=ref_id v;executor=ref_id (get "executor" v);scope=scope (get "scope" v);
    states=strings "states" v;initial=text "initial" v;terminal=strings "terminal" v;lifetime=text "lifetime" v;arbitration=arbitration (get "arbitration" v)}) in
  let transitions=selected "Transition" (fun v -> {transition_id=ref_id v;machine=ref_id (get "machine" v);source=text "source" v;destination=text "destination" v;
    on=expression_of_json (get "on" v);guard=expression_of_json (get "when" v);effects=refs "effects" v;assignments=assignments v}) in
  let requirements=selected "Requirement" (fun v ->
    (* Unproved requirement forms stay in their original, complete ledger. *)
    let parse_expression key = match get key v with Json.Null -> None | expression ->
      (try Some (expression_of_json expression) with Diagnostic.Error _ -> None) in
    {requirement_id=ref_id v;kind=text "kind" v;
      scope=(try Some (scope (get "scope" v)) with Diagnostic.Error _ -> None);
      condition=parse_expression "condition";response=parse_expression "response";trigger=parse_expression "trigger";
      deadline=option duration (get "deadline" v);horizon=(match get "horizon" v with Json.Object _ as q -> Some (duration q) | _ -> None);
      assumptions=strings "assumptions" v;source=Json.Object (("$type",Json.String "Requirement") :: Json.object_fields v)}) in
  let parameters=selected "Parameter" (fun v -> {parameter_id=ref_id v;value=value_of_json (value_type (get "value_type" v)) (get "value" v)}) in
  {raw;source_document;definitions;nodes;source_ledger=get "source_ledger" raw;requirements_ledger=get "requirements_ledger" raw;
    assumptions=strings "assumptions" raw;unresolved_obligations=strings "unresolved_obligations" raw;
    roles;subjects;encounters;clocks;observations;stores;effects;rules;machines;transitions;requirements;parameters}
let behavior_to_json value = value.raw

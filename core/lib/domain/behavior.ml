open Bioc_wire

module Names = Map.Make (String)
module Name_set = Set.Make (String)

type profile = V0_1 | V0_2
type number = Integer of Z.t | Real of float
type state_value = Text of string | Boolean of bool | State_integer of Z.t | State_real of float
type source_location = { file : string; line : Z.t; function_name : string }
type scope = Contact | Environment | Internal | External
type observation = Signal_observation | Marker_observation
type band = Present | High | Low
type comparison = Lt | Le | Gt | Ge | Eq | Ne
type arithmetic = Add | Subtract | Multiply | Divide | Negate
type trigger = Condition_trigger | Event_trigger
type memory_input = Owner | Set_when | Reset_when | Duration_input
type value_mode = Unspecified | Expression
type signature_binding =
  | Bound_input of int
  | Bound_literal of Json.t
  | Bound_object of (string * signature_binding) list
  | Bound_array of signature_binding list
type scalar_binding = { binding_raw : Json.t; canonical_value : number }
let binding_json value = value.binding_raw
let binding_value value = value.canonical_value

type operation =
  | Role of { name : string; cell_type : string }
  | Scope of scope
  | Signal of { name : string; scope : scope; observation : observation }
  | Channel of { name : string; scope : string }
  | Channel_observation
  | Qualitative of band
  | Literal of scalar_binding
  | Parameter of { name : string; default : scalar_binding }
  | And | Or | Not | At_least of int
  | Arithmetic of arithmetic | Compare of comparison
  | Held_for | Recently | Became_true | Followed_by | Integrated
  | Memory of { name : string; input_names : memory_input list }
  | Memory_is_set
  | State of { name : string; values : state_value list; initial : state_value }
  | State_is of state_value
  | Signature of { name : string; module_name : string; qualname : string;
                   bindings : (string * signature_binding) list }
  | Secretion of { name : string; product : string; default : bool }
  | Rule of { trigger : trigger; name : string option }
  | Action_state_set of state_value
  | Action_report of string | Action_pulse | Action_eliminate | Action_engulf
  | Action_secrete of value_mode | Action_emit of value_mode
  | Action_present of string | Action_retain of string option
  | Action_expand | Action_rest | Action_differentiate of string

let kind_name = function
  | Role _ -> "role" | Scope _ -> "scope" | Signal _ -> "signal"
  | Channel _ -> "channel" | Channel_observation -> "channel_observation"
  | Qualitative _ -> "qualitative" | Literal _ -> "literal" | Parameter _ -> "parameter"
  | And -> "and" | Or -> "or" | Not -> "not" | At_least _ -> "at_least"
  | Arithmetic Add -> "add" | Arithmetic Subtract -> "subtract"
  | Arithmetic Multiply -> "multiply" | Arithmetic Divide -> "divide"
  | Arithmetic Negate -> "negate" | Compare _ -> "compare"
  | Held_for -> "held_for" | Recently -> "recently" | Became_true -> "became_true"
  | Followed_by -> "followed_by" | Integrated -> "integrated"
  | Memory _ -> "memory" | Memory_is_set -> "memory.is_set"
  | State _ -> "state" | State_is _ -> "state.is" | Signature _ -> "signature"
  | Secretion _ -> "secretion" | Rule _ -> "rule"
  | Action_state_set _ -> "action.state_set" | Action_report _ -> "action.report"
  | Action_pulse -> "action.pulse" | Action_eliminate -> "action.eliminate"
  | Action_engulf -> "action.engulf" | Action_secrete _ -> "action.secrete"
  | Action_emit _ -> "action.emit" | Action_present _ -> "action.present"
  | Action_retain _ -> "action.retain" | Action_expand -> "action.expand"
  | Action_rest -> "action.rest" | Action_differentiate _ -> "action.differentiate"

type node = {
  node_identity : Identity.Node.t;
  opcode : operation;
  node_inputs : Identity.Node.t list;
  node_attributes : Json.t;
  node_type : Type_spec.t option;
  node_role : Identity.Role.t option;
  node_source : source_location option;
  node_contact : bool;
  node_requirements : Identity.Requirement.t list;
  node_raw : (string * Json.t) list;
}
let node_id value = value.node_identity
let operation value = value.opcode
let inputs value = value.node_inputs
let attributes value = value.node_attributes
let data_type value = value.node_type
let role value = value.node_role
let source value = value.node_source
let contact_bound value = value.node_contact
let requirement_ids value = value.node_requirements
let node_json ?(include_source = true) value =
  Json.Object (if include_source then value.node_raw else List.remove_assoc "source" value.node_raw)

type requirement_kind = Rule_requirement | State_requirement | Memory_requirement
type requirement = {
  req_identity : Identity.Requirement.t;
  req_kind : requirement_kind;
  req_source_node : Identity.Node.t;
  req_lineage : Identity.Node.t list;
  req_source : source_location option;
  req_raw : (string * Json.t) list;
}
let requirement_id value = value.req_identity
let requirement_kind value = value.req_kind
let requirement_source_node value = value.req_source_node
let requirement_lineage value = value.req_lineage
let requirement_source value = value.req_source
let requirement_json ?(include_source = true) value =
  Json.Object (if include_source then value.req_raw else List.remove_assoc "source" value.req_raw)

type t = {
  program_name : string;
  program_profile : profile;
  program_nodes : node list;
  program_roots : Identity.Node.t list;
  node_map : node Names.t;
  program_source_fingerprint : string;
  program_requirements : requirement list;
  program_source_links : (Identity.Node.t * Identity.Node.t list) list;
  program_policies : Json.t;
  program_parameters : (string * Json.t) list;
  constants : number option Names.t;
}
let name value = value.program_name
let profile value = value.program_profile
let nodes value = value.program_nodes
let roots value = value.program_roots
let get value identity = Names.find_opt (Identity.Node.to_string identity) value.node_map
let source_fingerprint value = value.program_source_fingerprint
let requirements value = value.program_requirements
let source_links value = value.program_source_links
let policies value = value.program_policies
let parameter_bindings value = value.program_parameters
let constant_value value identity =
  Option.join (Names.find_opt (Identity.Node.to_string identity) value.constants)

let require = Diagnostic.require
let fail = Diagnostic.fail
let str value = Json.String value
let arr_names values = Json.Array (List.map str values)
let schema_version = function V0_1 -> "biocompiler.behavior.v0.1" | V0_2 -> "biocompiler.behavior.v0.2"
let max_integral_samples = 10_000
let number = function
  | Json.Int value -> Integer value
  | Json.Float value when Float.is_finite value -> Real value
  | _ -> fail "behavior_constant" "Expected a finite scalar number."
let number_json = function Integer value -> Json.Int value | Real value -> Json.Float value
let number_float value = Json.number_to_float (number_json value)
let number_positive value = Json.number_compare (number_json value) (Json.int 0) > 0
let scalar_type name dimensions = Type_spec.of_json (Json.Object [
    "kind", str "scalar"; "name", str name; "dimensions", Json.Object dimensions;
    "arguments", Json.Array []])
let duration_type = scalar_type "Duration" ["time", Json.int 1]
let production_rate_type = scalar_type "ProductionRate" ["amount", Json.int 1; "time", Json.int (-1)]
let condition_type = Type_spec.of_json (Json.Object ["kind", str "condition"; "name", str "Condition"])
let event_type = Type_spec.of_json (Json.Object ["kind", str "event"; "name", str "Event"])
let binding ~path ~expected raw =
  Type_spec.validate_binding ~path ~expected raw;
  require ~path (Type_spec.kind expected = Type_spec.Scalar) "behavior_type" "Behavior constants must be scalar.";
  let canonical_value = number (Json.field ~path "canonical_value" (Json.object_fields ~path raw)) in
  { binding_raw = raw; canonical_value }

let legacy_policies = Json.Object [
    "profile", str "abstract_single_cell.v0.1";
    "time", str "nonnegative_seconds_piecewise_constant"; "initial_time", Json.int 0;
    "simultaneous_inputs", str "atomic_snapshot";
    "contact_binding", str "same_object_before_existential_aggregation";
    "local_action_binding", str "existential_aggregate_then_onset";
    "targeted_action_binding", str "per_contact_object";
    "memory_binding", str "any_contact_onset_sets_cell_local_memory";
    "contact_disappearance", str "clear_episode_history_and_contact_pulses";
    "observation_missing", str "error"; "qualitative_observations", str "explicit_boolean";
    "state_reads", str "shared_pre_update_state"; "state_writes", str "coalesce_identical_else_error";
    "state_propagation", str "atomic_microsteps_until_stable";
    "condition_ongoing", str "level"; "condition_impulses", str "onset";
    "event_ongoing", str "explicit_duration_required"; "initial_true", str "rising_event";
    "held_for", str "full_continuous_interval"; "recently", str "includes_present_excludes_expiry";
    "followed_by", str "strictly_later_inclusive_window_nonconsuming";
    "memory_initial", Json.Bool false;
    "memory_visibility", str "settled_controls_before_rule_effects";
    "memory_dependencies", str "causal_topological_settlement";
    "memory_setting", str "onset_latest_refresh";
    "memory_precedence", str "reset_then_new_onset_then_expiry";
    "pulse_interval", str "closed_start_open_end"; "pulse_retrigger", str "extend_from_latest_trigger";
    "timer_input_precedence", str "external_snapshot_before_due_timers";
    "history", str "since_initialization"; "outputs", str "abstract_requests_no_input_side_effects"]

let execution_policies ?(integral_step = Json.Null) = function
  | V0_1 ->
      require (integral_step = Json.Null) "behavior_policy" "Legacy Behavior has no integral sampling policy.";
      legacy_policies
  | V0_2 ->
      let step = match integral_step with
        | Json.Null -> Json.Null
        | value ->
            let normalized = Type_spec.normalize_binding ~path:"/policies/integral_step" ~expected:duration_type value in
            let typed = binding ~path:"/policies/integral_step" ~expected:duration_type normalized in
            require (number_positive typed.canonical_value) "behavior_policy" "Integral sampling step must be positive.";
            normalized
      in
      Json.Object (List.remove_assoc "profile" (Json.object_fields legacy_policies) @ [
          "profile", str "abstract_multirole_sampled.v0.2";
          "channel_observations", str "explicit_receiver_local_snapshots_no_implicit_transport";
          "channel_emissions", str "abstract_channel_value_requests_no_input_side_effects";
          "integrated", str "exact_rolling_area_of_nonnegative_cell_signal";
          "integral_observation_times", str "declared_grid_plus_input_and_timer_events";
          "integral_threshold_claim", str "sampled_events_only_not_continuous_threshold_detection";
          "integral_step", step; "integral_sample_limit", Json.int max_integral_samples])

let parse_source ~path = function
  | Json.Null -> None
  | value ->
      let fields = Json.object_fields ~path value in
      Json.exact_fields ~path ["file"; "line"; "function"] fields;
      let line = Json.integer ~path (Json.field "line" fields) in
      require ~path (Z.sign line > 0) "invalid_source" "Source line must be positive.";
      Some { file = Json.name ~path (Json.field "file" fields); line;
             function_name = Json.name ~path (Json.field "function" fields) }

let state_value ~path = function
  | Json.String value -> Text value | Json.Bool value -> Boolean value
  | Json.Int value -> State_integer value
  | Json.Float value when Float.is_finite value -> State_real value
  | _ -> fail ~path "behavior_state" "State values must be finite strings, Booleans, integers or floats."
let state_key = function
  | Text value -> "s:" ^ value | Boolean value -> "b:" ^ string_of_bool value
  | State_integer value -> "i:" ^ Z.to_string value
  | State_real value -> "f:" ^ Int64.to_string (Int64.bits_of_float (if value = 0. then 0. else value))
let state_equal left right = state_key left = state_key right

let parse_scope ~path = function
  | Json.String "contact" -> Contact | Json.String "environment" -> Environment
  | Json.String "internal" -> Internal | Json.String "external" -> External
  | _ -> fail ~path "behavior_operation" "Unknown observation scope."
let scope_name = function Contact -> "contact" | Environment -> "environment" | Internal -> "internal" | External -> "external"
let parse_mode ~path = function
  | Json.String "unspecified" -> Unspecified | Json.String "expression" -> Expression
  | _ -> fail ~path "behavior_operation" "Unknown action value mode."
let optional_name ~path key attributes = Option.map (Json.name ~path) (List.assoc_opt key attributes)

let parse_operation ~path ~dtype ~input_count kind raw_attributes =
  let a = Json.object_fields ~path raw_attributes in
  let field key = Json.field ~path key a in
  let named key = Json.name ~path (field key) in
  let fields required = Json.exact_fields ~path required a in
  let allowed required optional = Json.allowed_fields ~path ~required ~optional a in
  let check condition message = require ~path condition "behavior_operation" message in
  let exact expected = check (Json.equal raw_attributes (Json.Object expected)) "Unsupported operation policy." in
  let flag key expected = check (field key = Json.Bool expected) ("Invalid " ^ key ^ " policy.") in
  let scalar key =
    let expected = match dtype with Some value -> value | None -> fail ~path "behavior_type" "Constant has no declared type." in
    binding ~path ~expected (field key)
  in
  match kind with
  | "role" ->
      fields ["name"; "cell_type"; "engineering"];
      check (field "engineering" = str "in_vivo") "Unsupported engineering mode.";
      Role { name = named "name"; cell_type = named "cell_type" }
  | "scope" ->
      fields ["name"; "scope"];
      let scope = parse_scope ~path (field "scope") in
      check (field "name" = str (scope_name scope)) "Scope name and kind disagree.";
      Scope scope
  | "signal" ->
      fields ["name"; "scope"; "observation"];
      let scope = parse_scope ~path (field "scope") in
      let observation = match field "observation" with
        | Json.String "signal" -> Signal_observation
        | Json.String "marker" when scope = Contact -> Marker_observation
        | _ -> fail ~path "behavior_operation" "Invalid signal observation mode."
      in Signal { name = named "name"; scope; observation }
  | "channel" -> fields ["name"; "scope"]; Channel { name = named "name"; scope = named "scope" }
  | "channel_observation" ->
      exact ["scope", str "receiver_local"; "delivery", str "biological_signal"]; Channel_observation
  | "qualitative" ->
      fields ["band"];
      Qualitative (match field "band" with
          | Json.String "present" -> Present | Json.String "high" -> High | Json.String "low" -> Low
          | _ -> fail ~path "behavior_operation" "Invalid qualitative observation band.")
  | "literal" -> fields ["value"]; Literal (scalar "value")
  | "parameter" ->
      fields ["name"; "bound"; "default"]; flag "bound" true;
      Parameter { name = named "name"; default = scalar "default" }
  | "and" -> fields []; And | "or" -> fields []; Or | "not" -> fields []; Not
  | "at_least" ->
      fields ["count"];
      let count = Json.integer ~path (field "count") in
      check (input_count > 0 && Z.sign count >= 0 && Z.compare count (Z.of_int input_count) <= 0) "Invalid Boolean threshold.";
      At_least (Z.to_int count)
  | "add" -> fields []; Arithmetic Add | "subtract" -> fields []; Arithmetic Subtract
  | "multiply" -> fields []; Arithmetic Multiply | "divide" -> fields []; Arithmetic Divide
  | "negate" -> fields []; Arithmetic Negate
  | "compare" ->
      fields ["operator"];
      Compare (match field "operator" with
          | Json.String "lt" -> Lt | Json.String "le" -> Le | Json.String "gt" -> Gt
          | Json.String "ge" -> Ge | Json.String "eq" -> Eq | Json.String "ne" -> Ne
          | _ -> fail ~path "behavior_operation" "Unknown comparison operator.")
  | "held_for" -> exact ["history", str "since_initialization"; "requires_full_interval", Json.Bool true]; Held_for
  | "recently" -> exact ["history", str "since_initialization"; "includes_present", Json.Bool true]; Recently
  | "became_true" -> exact ["initially_true_emits", Json.Bool true]; Became_true
  | "followed_by" -> exact ["emits_at", str "second_event"; "history", str "since_initialization"]; Followed_by
  | "integrated" -> exact ["window", str "rolling"; "history", str "since_initialization"]; Integrated
  | "memory" ->
      fields ["name"; "input_names"; "initial"; "setting"; "initial_true_is_onset"; "reset_priority"; "expiry"];
      let names = Json.array ~path (field "input_names") |> List.map (Json.string ~path) in
      check (List.mem names [["owner"; "set_when"]; ["owner"; "set_when"; "reset_when"];
                            ["owner"; "set_when"; "duration"]; ["owner"; "set_when"; "reset_when"; "duration"]]) "Invalid memory input inventory.";
      flag "initial" false; flag "initial_true_is_onset" true; flag "reset_priority" true;
      check (field "setting" = str "onset") "Unsupported memory setting policy.";
      check (field "expiry" = str (if List.mem "duration" names then "latest_setting_onset" else "until_reset")) "Invalid memory expiry policy.";
      Memory { name = named "name"; input_names = List.map (function
          | "owner" -> Owner | "set_when" -> Set_when | "reset_when" -> Reset_when
          | "duration" -> Duration_input | _ -> assert false) names }
  | "memory.is_set" -> fields []; Memory_is_set
  | "state" ->
      fields ["name"; "values"; "initial"; "observation"; "arbitration"];
      let values = Json.array ~path (field "values") |> List.map (state_value ~path) in
      check (values <> []) "A state requires at least one declared value.";
      let keys = List.fold_left (fun seen value ->
          let key = state_key value in
          check (not (Name_set.mem key seen)) "Duplicate typed state value.";
          Name_set.add key seen) Name_set.empty values in
      let initial = state_value ~path (field "initial") in
      check (Name_set.mem (state_key initial) keys) "Undeclared initial state value.";
      check (field "observation" = str "shared_pre_update_state"
             && field "arbitration" = str "coalesce_identical_else_error") "Unsupported state policy.";
      State { name = named "name"; values; initial }
  | "state.is" -> fields ["value"]; State_is (state_value ~path (field "value"))
  | "action.state_set" ->
      fields ["value"; "idempotent"; "ongoing"]; flag "idempotent" true; flag "ongoing" false;
      Action_state_set (state_value ~path (field "value"))
  | "signature" ->
      fields ["definition"; "bindings"];
      let definition = Json.object_fields ~path (field "definition") in
      Json.exact_fields ~path ["name"; "module"; "qualname"] definition;
      let rec descriptor = function
        | Json.Object [("input", value)] ->
            let index = Json.integer ~path value in
            check (Z.compare index Z.one >= 0 && Z.compare index (Z.of_int input_count) < 0) "Invalid signature input reference.";
            Bound_input (Z.to_int index)
        | Json.Object [("literal", value)] -> Bound_literal value
        | Json.Object fields -> Bound_object (List.map (fun (key, value) -> key, descriptor value) fields)
        | Json.Array values -> Bound_array (List.map descriptor values)
        | _ -> fail ~path "behavior_operation" "Invalid signature binding descriptor."
      in
      Signature { name = Json.name ~path (Json.field "name" definition);
                  module_name = Json.name ~path (Json.field "module" definition);
                  qualname = Json.name ~path (Json.field "qualname" definition);
                  bindings = Json.object_fields ~path (field "bindings") |> List.map (fun (key, value) -> key, descriptor value) }
  | "secretion" ->
      fields ["name"; "product"; "default"; "activity"];
      check (field "activity" = str "requires_rule_or_controller") "Invalid secretion activity policy.";
      Secretion { name = named "name"; product = named "product"; default = Json.boolean ~path (field "default") }
  | "rule" ->
      allowed ["trigger"; "execution"; "priority"; "ongoing_activation"; "impulse_activation"; "state_assignment"] ["name"; "ongoing_duration"];
      let trigger = match field "trigger" with
        | Json.String "condition" -> Condition_trigger | Json.String "event" -> Event_trigger
        | _ -> fail ~path "behavior_operation" "Invalid rule trigger."
      in
      check (field "execution" = str "concurrent" && field "priority" = str "none") "Unsupported rule concurrency.";
      let ongoing, impulse, assignment = match trigger with
        | Condition_trigger -> "level", "onset", "level"
        | Event_trigger -> "explicit_duration", "event", "event"
      in
      check (field "ongoing_activation" = str ongoing && field "impulse_activation" = str impulse
             && field "state_assignment" = str assignment) "Invalid rule activation policy.";
      check (match trigger with Condition_trigger -> not (List.mem_assoc "ongoing_duration" a)
                               | Event_trigger -> List.assoc_opt "ongoing_duration" a = Some (str "explicit")) "Invalid event duration policy.";
      Rule { trigger; name = optional_name ~path "name" a }
  | "action.pulse" -> exact ["ongoing", Json.Bool true; "retrigger", str "extend_from_latest_trigger"]; Action_pulse
  | "action.secrete" -> fields ["ongoing"; "rate"]; flag "ongoing" true; Action_secrete (parse_mode ~path (field "rate"))
  | "action.emit" -> fields ["ongoing"; "value"]; flag "ongoing" true; Action_emit (parse_mode ~path (field "value"))
  | "action.report" -> fields ["ongoing"; "label"]; flag "ongoing" false; Action_report (named "label")
  | "action.present" -> fields ["ongoing"; "antigen"]; flag "ongoing" true; Action_present (named "antigen")
  | "action.differentiate" -> fields ["ongoing"; "phenotype"]; flag "ongoing" true; Action_differentiate (named "phenotype")
  | "action.retain" -> allowed ["ongoing"] ["location"]; flag "ongoing" true; Action_retain (optional_name ~path "location" a)
  | "action.eliminate" -> fields ["ongoing"]; flag "ongoing" true; Action_eliminate
  | "action.engulf" -> fields ["ongoing"]; flag "ongoing" true; Action_engulf
  | "action.expand" -> fields ["ongoing"]; flag "ongoing" true; Action_expand
  | "action.rest" -> fields ["ongoing"]; flag "ongoing" true; Action_rest
  | _ -> fail ~path "unsupported_behavior_operation" ("Unsupported Behavior operation: " ^ kind)

let node_of_fields ~index fields =
  let path = "/nodes/" ^ string_of_int index in
  let field key = Json.field ~path key fields in
  let node_type = match field "data_type" with Json.Null -> None | value -> Some (Type_spec.of_json ~path value) in
  let node_inputs = Json.array ~path (field "inputs") |> List.map (fun value -> Identity.Node.of_string (Json.name ~path value)) in
  let node_attributes = field "attributes" in
  let opcode = parse_operation ~path ~dtype:node_type ~input_count:(List.length node_inputs)
      (Json.string ~path (field "kind")) node_attributes in
  let raw_requirements = Json.array ~path (field "requirement_ids") |> List.map (Json.name ~path) in
  require ~path (Name_set.cardinal (Name_set.of_list raw_requirements) = List.length raw_requirements)
    "behavior_requirements" "Duplicate requirement references.";
  { node_identity = Identity.Node.of_string (Json.name ~path (field "id")); opcode; node_inputs;
    node_attributes; node_type;
    node_role = (match field "role" with Json.Null -> None | value -> Some (Identity.Role.of_string (Json.name ~path value)));
    node_source = parse_source ~path (field "source");
    node_contact = Json.boolean ~path (field "contact_bound");
    node_requirements = List.map Identity.Requirement.of_string raw_requirements;
    node_raw = fields }

let parse_requirement ~index raw =
  let path = "/requirements/" ^ string_of_int index in
  let fields = Json.object_fields ~path raw in
  Json.allowed_fields ~path ~required:["id"; "kind"; "source_node_id"; "lineage"] ~optional:["source"] fields;
  let source = Option.value ~default:Json.Null (List.assoc_opt "source" fields) in
  let fields = ("source", source) :: List.remove_assoc "source" fields in
  let req_kind = match Json.field "kind" fields with
    | Json.String "rule" -> Rule_requirement | Json.String "state" -> State_requirement
    | Json.String "memory" -> Memory_requirement
    | _ -> fail ~path "behavior_requirements" "Unknown Behavior requirement kind."
  in
  let lineage = Json.array ~path (Json.field "lineage" fields) |> List.map (Json.name ~path) in
  require ~path (Name_set.cardinal (Name_set.of_list lineage) = List.length lineage)
    "behavior_requirements" "Duplicate requirement lineage reference.";
  { req_identity = Identity.Requirement.of_string (Json.name ~path (Json.field "id" fields));
    req_kind; req_source_node = Identity.Node.of_string (Json.name ~path (Json.field "source_node_id" fields));
    req_lineage = List.map Identity.Node.of_string lineage; req_source = parse_source ~path source; req_raw = fields }

let type_product left right sign =
  let dimensions value = Type_spec.to_json value |> Json.object_fields |> Json.field "dimensions" |> Json.object_fields in
  let powers = List.fold_left (fun map (key, value) -> Names.add key (Json.integer value) map)
      Names.empty (dimensions left) in
  let powers = List.fold_left (fun map (key, value) ->
      let current = Option.value ~default:Z.zero (Names.find_opt key map) in
      Names.add key (Z.add current (Z.mul (Z.of_int sign) (Json.integer value))) map) powers (dimensions right) in
  let dimensions = Names.bindings powers |> List.filter_map (fun (key, value) ->
      if Z.equal value Z.zero then None else Some (key, Json.Int value)) in
  (* Compatibility ignores the display name. Raw declared result type is never
     replaced with this temporary dimension product. *)
  scalar_type "Behavior dimensional product" dimensions

let is_action = function
  | Action_state_set _ | Action_report _ | Action_pulse | Action_eliminate | Action_engulf
  | Action_secrete _ | Action_emit _ | Action_present _ | Action_retain _
  | Action_expand | Action_rest | Action_differentiate _ -> true
  | _ -> false
let is_ongoing = function
  | Action_pulse | Action_eliminate | Action_engulf | Action_secrete _ | Action_emit _
  | Action_present _ | Action_retain _ | Action_expand | Action_rest | Action_differentiate _ -> true
  | _ -> false
let is_declaration = function
  | Role _ | Parameter _ | Memory _ | State _ | Secretion _ | Rule _ | Channel _ -> true
  | _ -> false
let requirement_of_operation = function
  | Rule _ -> Some Rule_requirement | State _ -> Some State_requirement | Memory _ -> Some Memory_requirement
  | _ -> None
let extension = function Integrated | Channel _ | Channel_observation | Action_emit _ -> true | _ -> false

let validate_operation profile map node =
  let path = "/nodes/" ^ Identity.Node.to_string node.node_identity in
  let check condition message = require ~path condition "behavior_operation" message in
  let typed_check condition message = require ~path condition "behavior_type" message in
  let refs = Array.of_list node.node_inputs in
  let arguments = Array.map (fun identity -> Names.find (Identity.Node.to_string identity) map) refs in
  let arity count = check (Array.length refs = count) ("Expected " ^ string_of_int count ^ " inputs.") in
  let actual index = match arguments.(index).node_type with
    | Some dtype -> dtype | None -> fail ~path "behavior_type" "Input has no semantic type."
  in
  let typed index expected =
    let value = actual index in
    typed_check (Type_spec.compatible value expected) "Input semantic type is incompatible.";
    value
  in
  let scalar index =
    let value = actual index in
    typed_check (Type_spec.kind value = Type_spec.Scalar) "Input must have a scalar type.";
    value
  in
  let returns expected = match node.node_type, expected with
    | None, None -> ()
    | Some actual, Some expected -> typed_check (Type_spec.compatible actual expected) "Result semantic type is incompatible."
    | _ -> fail ~path "behavior_type" "Incorrect result type presence."
  in
  let returns_scalar () = match node.node_type with
    | Some dtype when Type_spec.kind dtype = Type_spec.Scalar -> dtype
    | _ -> fail ~path "behavior_type" "Result must have a scalar type."
  in
  let owner () = check (match node.node_role, arguments.(0).opcode with
      | Some role, Role _ -> Identity.Role.to_string role = Identity.Node.to_string refs.(0)
      | _ -> false) "Invalid owning role input." in
  require ~path (profile = V0_2 || not (extension node.opcode)) "unsupported_behavior_profile"
    "Operation requires Behavior v0.2; its policies cannot be relabeled v0.1.";
  (match node.opcode with
   | Role _ | Channel _ | Literal _ | Parameter _ -> check (node.node_role = None) "Global declarations and constants must be role-free."
   | other ->
       let role_optional = match other with
         | Arithmetic _ | Compare _ | And | Or | Not | At_least _ | Held_for | Recently
         | Became_true | Followed_by | Signature _ -> true
         | _ -> false
       in
       check (node.node_role <> None || role_optional) "Operation requires a cell role.";
       Array.iter (fun input -> check (input.node_role = None || input.node_role = node.node_role)
                      "Cross-role input is not allowed.") arguments);
  match node.opcode with
  | Role _ -> arity 0; returns None
  | Channel _ | Literal _ | Parameter _ -> arity 0; ignore (returns_scalar ())
  | Scope _ -> arity 1; owner (); returns None
  | Signal signal ->
      arity 1; ignore (returns_scalar ());
      check (match arguments.(0).opcode with Scope scope -> scope = signal.scope | _ -> false) "Signal and scope disagree."
  | Channel_observation ->
      arity 2; let dtype = returns_scalar () in
      check (arguments.(0).opcode = Scope Environment && match arguments.(1).opcode with Channel _ -> true | _ -> false)
        "Channel observation requires environment scope and shared channel.";
      ignore (typed 1 dtype)
  | Qualitative _ ->
      arity 1; returns (Some condition_type); ignore (scalar 0);
      check (match arguments.(0).opcode with Signal _ | Channel_observation -> true | _ -> false)
        "Qualitative observation must directly observe a signal."
  | Integrated ->
      arity 2; let signal_type = scalar 0 in ignore (typed 1 duration_type);
      returns (Some (type_product signal_type duration_type 1));
      check ((match arguments.(0).opcode with Signal _ | Channel_observation -> true | _ -> false)
             && not arguments.(0).node_contact) "Integration requires a direct cell-local signal."
  | And | Or | Not | At_least _ ->
      (match node.opcode with And | Or -> arity 2 | Not -> arity 1 | _ -> ());
      returns (Some condition_type); Array.iteri (fun index _ -> ignore (typed index condition_type)) arguments
  | Arithmetic arithmetic ->
      arity (if arithmetic = Negate then 1 else 2);
      let left = scalar 0 in
      let right = if arithmetic = Negate then left else scalar 1 in
      (match arithmetic with
       | Add | Subtract -> typed_check (Type_spec.compatible left right) "Operand dimensions disagree."
       | _ -> ());
      returns (Some (match arithmetic with
          | Multiply -> type_product left right 1 | Divide -> type_product left right (-1)
          | Add | Subtract | Negate -> left))
  | Compare _ ->
      arity 2; let left = scalar 0 and right = scalar 1 in
      typed_check (Type_spec.compatible left right) "Comparison dimensions disagree."; returns (Some condition_type)
  | Held_for | Recently | Became_true | Followed_by ->
      arity (match node.opcode with Became_true -> 1 | Followed_by -> 3 | _ -> 2);
      ignore (typed 0 (if node.opcode = Followed_by then event_type else condition_type));
      if node.opcode = Followed_by then ignore (typed 1 event_type);
      if node.opcode <> Became_true then ignore (typed (Array.length refs - 1) duration_type);
      returns (Some (match node.opcode with Became_true | Followed_by -> event_type | _ -> condition_type))
  | Memory memory ->
      arity (List.length memory.input_names); owner (); returns (Some condition_type);
      List.iteri (fun index -> function
          | Owner -> () | Set_when | Reset_when -> ignore (typed index condition_type)
          | Duration_input -> ignore (typed index duration_type)) memory.input_names
  | Memory_is_set ->
      arity 1; returns (Some condition_type);
      check (match arguments.(0).opcode with Memory _ -> true | _ -> false) "Expected a memory declaration."
  | State _ -> arity 1; owner (); returns None
  | State_is value | Action_state_set value ->
      arity 1;
      check (match arguments.(0).opcode with State state -> List.exists (state_equal value) state.values | _ -> false)
        "Expected a state declaration and a declared value of the same primitive type.";
      returns (match node.opcode with State_is _ -> Some condition_type | _ -> None)
  | Signature _ ->
      check (Array.length refs > 0) "Signature requires an expression.";
      ignore (typed 0 condition_type); returns (Some condition_type)
  | Secretion _ -> arity 1; owner (); returns None
  | Rule rule ->
      check (Array.length refs >= 3) "Rule requires owner, trigger and actions.";
      owner (); returns None;
      ignore (typed 1 (if rule.trigger = Condition_trigger then condition_type else event_type));
      for index = 2 to Array.length arguments - 1 do
        let action = arguments.(index).opcode in
        check (is_action action) "Rule inputs must be actions.";
        check (rule.trigger <> Event_trigger || not (is_ongoing action) || action = Action_pulse)
          "Event-triggered ongoing actions require explicit duration."
      done
  | Action_pulse ->
      arity 2; returns None; ignore (typed 1 duration_type);
      check (is_action arguments.(0).opcode && is_ongoing arguments.(0).opcode && arguments.(0).opcode <> Action_pulse)
        "Pulse requires a primitive ongoing action."
  | Action_emit mode ->
      arity (if mode = Unspecified then 2 else 3); owner (); returns None;
      check (match arguments.(1).opcode with Channel _ -> true | _ -> false) "Emission must identify a shared channel.";
      if mode = Expression then ignore (typed 2 (actual 1))
  | Action_secrete mode ->
      arity (if mode = Unspecified then 1 else 2); returns None;
      check (match arguments.(0).opcode with Secretion _ -> true | _ -> false) "Secretion action must identify a secretion declaration.";
      if mode = Expression then ignore (typed 1 production_rate_type)
  | Action_report _ | Action_eliminate | Action_engulf | Action_present _ | Action_retain _
  | Action_expand | Action_rest | Action_differentiate _ ->
      arity (match node.opcode with Action_eliminate | Action_engulf | Action_retain None -> 2 | _ -> 1);
      owner (); returns None;
      if Array.length refs = 2 then (
        check (match arguments.(1).opcode with Scope _ -> true | _ -> false) "Expected target scope.";
        match node.opcode with
        | Action_eliminate | Action_engulf -> check (arguments.(1).opcode = Scope Contact) "Action requires a contacted object."
        | _ -> ())

let structural_dependencies node =
  let inputs = List.map Identity.Node.to_string node.node_inputs in
  match node.node_role with None -> inputs | Some role -> Identity.Role.to_string role :: inputs

let topological_order map nodes =
  (* Intent has already established a DAG. Iterative postorder avoids making
     language graph depth depend on the OCaml call stack. *)
  let seen = ref Name_set.empty and ordered = ref [] in
  let pending = ref (List.map (fun node -> Identity.Node.to_string node.node_identity, false) nodes) in
  while !pending <> [] do
    let identity, closing = List.hd !pending in
    pending := List.tl !pending;
    if closing then ordered := identity :: !ordered
    else if not (Name_set.mem identity !seen) then (
      seen := Name_set.add identity !seen;
      let dependencies = structural_dependencies (Names.find identity map) in
      pending := List.map (fun dependency -> dependency, false) dependencies @ ((identity, true) :: !pending))
  done;
  List.rev !ordered

let number_negate = function Integer value -> Integer (Z.neg value) | Real value -> Real (-.value)
let number_binary arithmetic left right =
  match arithmetic, left, right with
  | Add, Integer a, Integer b -> Integer (Z.add a b)
  | Subtract, Integer a, Integer b -> Integer (Z.sub a b)
  | Multiply, Integer a, Integer b -> Integer (Z.mul a b)
  | Divide, Integer a, Integer b ->
      require (not (Z.equal b Z.zero)) "behavior_constant" "Constant division by zero.";
      (* Q.to_float uses exact rational rounding. Converting the two operands
         separately can differ from Python integer true division. Q erases the
         sign of zero, so retain Python's zero/negative-denominator result. *)
      Real (if Z.equal a Z.zero && Z.sign b < 0 then -0. else Q.to_float (Q.make a b))
  | arithmetic, _, _ ->
      let a = number_float left and b = number_float right in
      Real (match arithmetic with
          | Add -> a +. b | Subtract -> a -. b | Multiply -> a *. b
          | Divide -> require (b <> 0.) "behavior_constant" "Constant division by zero."; a /. b
          | Negate -> assert false)

let derive_graph_facts map order =
  let contacts = ref Names.empty and constants = ref Names.empty and lineages = ref Names.empty in
  let lineage_size = ref 0 in
  List.iter (fun identity ->
      let node = Names.find identity map in
      let input_ids = List.map Identity.Node.to_string node.node_inputs in
      let contact = match node.opcode with
        | Scope scope -> scope = Contact
        | Role _ | State _ | State_is _ | Memory _ | Memory_is_set | Literal _ | Parameter _
        | Secretion _ | Action_state_set _ -> false
        | Signature _ -> Names.find (List.hd input_ids) !contacts
        | _ -> List.exists (fun reference -> Names.find reference !contacts) input_ids
      in
      contacts := Names.add identity contact !contacts;
      require (contact = node.node_contact) "behavior_contact" ("Incorrect contact binding at " ^ identity);
      let constant = match node.opcode with
        | Literal value -> Some value.canonical_value
        | Parameter parameter -> Some parameter.default.canonical_value
        | Arithmetic Negate -> Option.map number_negate (Names.find (List.hd input_ids) !constants)
        | Arithmetic arithmetic ->
            (match input_ids with
             | [left; right] ->
                 (match Names.find left !constants, Names.find right !constants with
                  | Some a, Some b -> Some (number_binary arithmetic a b) | _ -> None)
             | _ -> assert false)
        | _ -> None
      in
      Option.iter (fun value -> ignore (number_float value)) constant;
      constants := Names.add identity constant !constants;
      let ancestry = List.fold_left (fun ancestry dependency ->
          Name_set.union ancestry (Names.find dependency !lineages))
          (Name_set.singleton identity) (structural_dependencies node) in
      lineage_size := !lineage_size + Name_set.cardinal ancestry;
      require (!lineage_size <= Limits.max_json_nodes) "behavior_lineage_limit"
        "Complete Behavior ancestry exceeds the wire document node budget.";
      lineages := Names.add identity ancestry !lineages) order;
  !constants, !lineages

let duration_reference node =
  match node.opcode with
  | Held_for | Recently | Action_pulse | Integrated -> Some (List.nth node.node_inputs 1)
  | Followed_by -> Some (List.nth node.node_inputs 2)
  | Memory memory ->
      let rec find inputs refs = match inputs, refs with
        | Duration_input :: _, reference :: _ -> Some reference
        | _ :: inputs, _ :: refs -> find inputs refs
        | _ -> None
      in find memory.input_names node.node_inputs
  | _ -> None

let source_json = function
  | None -> Json.Null
  | Some value -> Json.Object ["file", str value.file; "line", Json.Int value.line; "function", str value.function_name]

let of_json raw =
  (* Json.t is also constructible by native callers. Validate lexical invariants
     before projection can hide duplicate keys, invalid UTF-8 or nonfinite data. *)
  ignore (Canonical.encode raw);
  let fields = Json.object_fields raw in
  Json.exact_fields ["schema_version"; "name"; "nodes"; "roots"; "source_fingerprint";
                     "requirements"; "source_links"; "policies"; "parameter_bindings"] fields;
  let program_profile = match Json.field "schema_version" fields with
    | Json.String "biocompiler.behavior.v0.1" -> V0_1
    | Json.String "biocompiler.behavior.v0.2" -> V0_2
    | _ -> fail "unsupported_behavior_profile" "Unsupported Behavior schema."
  in
  let raw_nodes = Json.array ~path:"/nodes" (Json.field "nodes" fields) in
  let behavior_fields = List.mapi (fun index raw ->
      let path = "/nodes/" ^ string_of_int index in
      let fields = Json.object_fields ~path raw in
      Json.allowed_fields ~path ~required:["id"; "kind"; "inputs"; "attributes"; "data_type";
                                          "role"; "contact_bound"; "requirement_ids"] ~optional:["source"] fields;
      fields) raw_nodes in
  (* This projection does only Intent's existing structural DAG/reference and
     literal validation. It neither lowers source nor supplies any Behavior
     operation, policy, contact or preservation answer. Behavior-specific
     fields are retained separately and all are validated below. *)
  let graph = Intent.of_json (Json.Object [
      "schema_version", str Intent.schema_version; "name", Json.field "name" fields;
      "roots", Json.field "roots" fields;
      "nodes", Json.Array (List.map (fun fields -> Json.Object
          (List.remove_assoc "contact_bound" (List.remove_assoc "requirement_ids" fields))) behavior_fields)]) in
  let normalized = Intent.to_json graph |> Json.object_fields in
  let normalized_nodes = Json.field "nodes" normalized |> Json.array in
  let program_nodes = List.map2 (fun normalized original ->
      ("contact_bound", Json.field "contact_bound" original) ::
      ("requirement_ids", Json.field "requirement_ids" original) :: Json.object_fields normalized)
      normalized_nodes behavior_fields |> List.mapi (fun index fields -> node_of_fields ~index fields) in
  let node_map = List.fold_left (fun map node -> Names.add (Identity.Node.to_string node.node_identity) node map)
      Names.empty program_nodes in
  let program_name = Json.name (Json.field "name" normalized) in
  let program_roots = Json.array (Json.field "roots" normalized) |> List.map (fun value -> Identity.Node.of_string (Json.name value)) in
  let program_source_fingerprint = Json.string (Json.field "source_fingerprint" fields) in
  require (String.length program_source_fingerprint = 64 && String.for_all (function '0' .. '9' | 'a' .. 'f' -> true | _ -> false) program_source_fingerprint)
    "behavior_source_fingerprint" "Source fingerprint must be lowercase SHA-256 hex.";
  let program_policies = Json.field "policies" fields in
  let policy_fields = Json.object_fields ~path:"/policies" program_policies in
  let integral_step = Option.value ~default:Json.Null (List.assoc_opt "integral_step" policy_fields) in
  require (Json.equal program_policies (execution_policies ~integral_step program_profile))
    "behavior_policy" "Unknown or modified Behavior execution policies.";
  let program_parameters = Json.object_fields ~path:"/parameter_bindings" (Json.field "parameter_bindings" fields) in
  let program_requirements = Json.array ~path:"/requirements" (Json.field "requirements" fields)
      |> List.mapi (fun index raw -> parse_requirement ~index raw) in
  let program_source_links = Json.object_fields ~path:"/source_links" (Json.field "source_links" fields)
      |> List.map (fun (key, value) -> Identity.Node.of_string key,
                   Json.array ~path:"/source_links" value |> List.map (fun value -> Identity.Node.of_string (Json.name ~path:"/source_links" value))) in
  List.iter (validate_operation program_profile node_map) program_nodes;
  require (integral_step <> Json.Null || not (List.exists (fun node -> node.opcode = Integrated) program_nodes))
    "behavior_policy" "Integrated Behavior requires an explicitly pinned sampling step.";
  let constants, lineages = derive_graph_facts node_map (topological_order node_map program_nodes) in
  List.iter (fun node -> match duration_reference node with
      | None -> ()
      | Some reference ->
          let value = Names.find (Identity.Node.to_string reference) constants in
          require (match value with Some value -> number_positive value | None -> false)
            "behavior_duration" "Duration must be a positive design-time constant.") program_nodes;
  let declarations = List.filter (fun node -> is_declaration node.opcode) program_nodes
      |> List.map (fun node -> Identity.Node.to_string node.node_identity) |> Name_set.of_list in
  require (Name_set.equal declarations (Name_set.of_list (List.map Identity.Node.to_string program_roots)))
    "behavior_roots" "Behavior roots must include exactly all executable declarations.";
  let expected_links = Names.bindings lineages |> List.map (fun (identity, lineage) -> identity, arr_names (Name_set.elements lineage)) in
  require (Json.equal (Json.field "source_links" fields) (Json.Object expected_links))
    "behavior_lineage" "Incomplete or inconsistent source lineage.";
  let expected_requirements = List.filter_map (fun node ->
      match requirement_of_operation node.opcode with
      | None -> None
      | Some _ ->
          let identity = Identity.Node.to_string node.node_identity in
          Some (Json.Object ["id", str ("requirement:" ^ identity); "kind", str (kind_name node.opcode);
                             "source_node_id", str identity; "lineage", arr_names (Name_set.elements (Names.find identity lineages));
                             "source", source_json node.node_source])) program_nodes in
  require (Json.equal (Json.Array (List.map (requirement_json ~include_source:true) program_requirements))
             (Json.Array expected_requirements)) "behavior_requirements"
    "Requirements must retain every rule, state and memory, in declaration order with exact lineage and source.";
  (* Invert the retained ancestry once. Scanning every requirement for every
     node would turn many independent declarations into quadratic work. *)
  let inherited_requirements = List.fold_left (fun map requirement ->
      List.fold_left (fun map reference ->
          let identity = Identity.Node.to_string reference in
          let previous = Option.value ~default:[] (Names.find_opt identity map) in
          Names.add identity (requirement.req_identity :: previous) map) map requirement.req_lineage)
      Names.empty program_requirements in
  List.iter (fun node ->
      let identity = Identity.Node.to_string node.node_identity in
      let expected = List.rev (Option.value ~default:[] (Names.find_opt identity inherited_requirements)) in
      require (node.node_requirements = expected) "behavior_requirements"
        ("Incorrect requirement mapping at " ^ identity)) program_nodes;
  let expected_parameters = List.filter_map (fun node -> match node.opcode with
      | Parameter parameter -> Some (parameter.name, binding_json parameter.default) | _ -> None) program_nodes in
  require (Json.equal (Json.Object program_parameters) (Json.Object expected_parameters)) "behavior_bindings"
    "Parameter bindings disagree with the executable graph.";
  { program_name; program_profile; program_nodes; program_roots; node_map; program_source_fingerprint;
    program_requirements; program_source_links; program_policies; program_parameters; constants }

let to_json ?(include_source = true) value = Json.Object [
    "schema_version", str (schema_version value.program_profile); "name", str value.program_name;
    "nodes", Json.Array (List.map (node_json ~include_source) value.program_nodes);
    "roots", arr_names (List.map Identity.Node.to_string value.program_roots);
    "source_fingerprint", str value.program_source_fingerprint;
    "requirements", Json.Array (List.map (requirement_json ~include_source) value.program_requirements);
    "source_links", Json.Object (List.map (fun (identity, lineage) -> Identity.Node.to_string identity,
        arr_names (List.map Identity.Node.to_string lineage)) value.program_source_links);
    "policies", value.program_policies; "parameter_bindings", Json.Object value.program_parameters]
let fingerprint value = Canonical.fingerprint (to_json ~include_source:false value)
let summary value =
  let counts = List.fold_left (fun counts node ->
      let kind = kind_name node.opcode in
      Names.add kind (1 + Option.value ~default:0 (Names.find_opt kind counts)) counts) Names.empty value.program_nodes in
  let count kind = Json.int (Option.value ~default:0 (Names.find_opt kind counts)) in
  Json.Object ["name", str value.program_name; "schema_version", str (schema_version value.program_profile);
               "node_count", Json.int (List.length value.program_nodes); "roles", count "role"; "rules", count "rule";
               "requirements", Json.int (List.length value.program_requirements);
               "kinds", Json.Object (List.map (fun (kind, count) -> kind, Json.int count) (Names.bindings counts));
               "fingerprint", str (fingerprint value); "source_fingerprint", str value.program_source_fingerprint]

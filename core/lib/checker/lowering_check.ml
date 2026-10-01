open Bioc_wire
open Bioc_domain

module Names = Map.Make (String)
module Name_set = Set.Make (String)

type preservation_check = { check_property : string; check_detail : string }
let property value = value.check_property
let detail value = value.check_detail
type report = {
  request_fingerprint : string;
  request_artifact_fingerprint : string;
  source_fingerprint : string;
  behavior_fingerprint : string;
  behavior_artifact_fingerprint : string;
  behavior_profile : string;
  preservation_checks : preservation_check list;
  remaining_obligations : string list;
}
let schema_version = "biocompiler.lowering_verification.v0.1"
let checker_version = "biocompiler.ocaml.lowering_check.v0.1"
let validation_scope = "source-to-behavior-correspondence-v1"
let claim_scope =
  "Exact frozen source-to-Behavior correspondence only; no source execution, molecular realization, empirical component function, human therapeutic admission, or complete architecture acceptance."
let passed (_ : report) = true
let checks value = value.preservation_checks
let unimplemented_obligations value = value.remaining_obligations
let str value = Json.String value
let names values = Json.Array (List.map str values)
let fail = Diagnostic.fail
let require = Diagnostic.require
let pointer value = String.concat "~1" (String.split_on_char '/' (String.concat "~0" (String.split_on_char '~' value)))

(* Python verify_lowering deliberately uses Mapping equality for policies and
   raw TypeSpec mappings, unlike its JSON-exact attribute/binding comparison.
   Keep that narrow compatibility rule explicit. In particular, JSON identity
   still distinguishes 1/1.0 and false/0 everywhere using Json.equal below. *)
let rec python_mapping_equal left right =
  match left, right with
  | (Json.Int _ | Json.Float _ | Json.Bool _), (Json.Int _ | Json.Float _ | Json.Bool _) ->
      let numeric = function Json.Bool value -> Json.int (if value then 1 else 0) | value -> value in
      Json.number_compare (numeric left) (numeric right) = 0
  | Json.Array left, Json.Array right ->
      List.length left = List.length right && List.for_all2 python_mapping_equal left right
  | Json.Object left, Json.Object right ->
      let sort = List.sort (fun (a, _) (b, _) -> String.compare a b) in
      let left, right = sort left, sort right in
      List.length left = List.length right
      && List.for_all2 (fun (a, av) (b, bv) -> a = b && python_mapping_equal av bv) left right
  | _ -> Json.equal left right

type source_node = {
  identity : string;
  kind : string;
  inputs : string list;
  attributes : (string * Json.t) list;
  data_type : Json.t;
  role : string option;
  source : Json.t;
}
let source_node raw =
  let fields = Json.object_fields raw in
  { identity = Json.string (Json.field "id" fields);
    kind = Json.string (Json.field "kind" fields);
    inputs = Json.array (Json.field "inputs" fields) |> List.map Json.string;
    attributes = Json.object_fields (Json.field "attributes" fields);
    data_type = Json.field "data_type" fields;
    role = (match Json.field "role" fields with Json.Null -> None | value -> Some (Json.string value));
    source = Json.field "source" fields }
let attribute node key = Option.value ~default:Json.Null (List.assoc_opt key node.attributes)
let source_path node = "/expected_request/intent/nodes/" ^ pointer node.identity
let unsupported node code detail = fail ~path:(source_path node) code detail
let lookup nodes reference = match Names.find_opt reference nodes with
  | Some value -> value
  | None -> fail "invalid_lowering_source" "Source graph contains a missing reference."
let input node index = match List.nth_opt node.inputs index with
  | Some value -> value
  | None -> fail ~path:(source_path node) "invalid_lowering_source" "Source operation is missing a required input."

let supported = Name_set.of_list [
    "role"; "scope"; "signal"; "qualitative"; "literal"; "parameter";
    "and"; "or"; "not"; "at_least"; "add"; "subtract"; "multiply"; "divide"; "negate"; "compare";
    "held_for"; "recently"; "became_true"; "followed_by"; "memory"; "memory.is_set"; "state"; "state.is";
    "signature"; "secretion"; "rule"; "action.state_set"; "action.report"; "action.pulse";
    "action.eliminate"; "action.engulf"; "action.secrete"; "action.present"; "action.retain";
    "action.expand"; "action.rest"; "action.differentiate"]
let extensions = Name_set.of_list ["integrated"; "channel"; "channel_observation"; "action.emit"]
let truthy = function
  | Json.Null | Json.Bool false -> false
  | (Json.Int _ | Json.Float _) as value -> Json.number_compare value (Json.int 0) <> 0
  | Json.String "" | Json.Array [] | Json.Object [] -> false
  | _ -> true

let source_profile profile nodes ordered =
  List.iter (fun node ->
      if not (Name_set.mem node.kind supported || profile = Build_request.V2 && Name_set.mem node.kind extensions) then
        unsupported node "unsupported_lowering_operation" "Source operation needs an additional execution profile or refinement.";
      if List.mem node.kind ["literal"; "parameter"] then (
        let dtype = Type_spec.of_json ~path:(source_path node ^ "/data_type") node.data_type in
        if Type_spec.kind dtype <> Type_spec.Scalar then
          unsupported node "unsupported_lowering_value_kind" "Behavior lowering supports bound scalar design values only.");
      match node.kind with
      | "state" ->
          if attribute node "observation" <> str "prior_state" || attribute node "arbitration" <> str "unspecified" then
            unsupported node "unsupported_lowering_state_policy" "Unknown source state-read or arbitration semantics."
      | "integrated" ->
          if List.length node.inputs <> 2 then
            unsupported node "unsupported_lowering_integration" "Integration requires a direct cell-local numeric observation and a window.";
          let observed = lookup nodes (input node 0) in
          if not (List.mem observed.kind ["signal"; "channel_observation"]) then
            unsupported node "unsupported_lowering_integration" "Integration requires a direct cell-local numeric observation.";
          if observed.kind = "signal" && attribute (lookup nodes (input observed 0)) "scope" = str "contact" then
            unsupported node "unsupported_lowering_integration" "Contact integration needs an explicit identity/history profile."
      | "rule" ->
          if attribute node "execution" <> str "concurrent" || attribute node "priority" <> str "unspecified" then
            unsupported node "unsupported_lowering_rule_policy" "Unknown source rule execution or priority semantics.";
          let trigger = attribute node "trigger" in
          if trigger <> str "condition" && trigger <> str "event" then
            unsupported node "unsupported_lowering_rule_policy" "Unknown source trigger semantics.";
          let allowed = ["trigger"; "execution"; "priority"; "name"] in
          let allowed = if trigger = str "event" then (
              if attribute node "ongoing_duration" <> str "explicit_or_design_choice" then
                unsupported node "unsupported_lowering_event_duration" "Unknown source event-duration semantics.";
              List.iteri (fun index reference -> if index >= 2 then (
                  let action = lookup nodes reference in
                  if truthy (attribute action "ongoing") && action.kind <> "action.pulse" then
                    unsupported node "unsupported_lowering_event_duration" "Event-triggered ongoing actions require an explicit pulse duration.")) node.inputs;
              "ongoing_duration" :: allowed) else allowed in
          if List.exists (fun (key, _) -> not (List.mem key allowed)) node.attributes then
            unsupported node "unsupported_lowering_rule_policy" "Unrecognized source rule policy fields."
      | "action.pulse" ->
          (match node.inputs with first :: _ when (lookup nodes first).kind = "action.pulse" ->
             unsupported node "unsupported_lowering_nested_pulse" "Nested pulses need an explicit duration-composition policy."
           | _ -> ())
      | _ -> ()) ordered

let expected_step request ordered =
  match Build_request.behavior_profile request with
  | Build_request.V1 -> Json.Null
  | Build_request.V2 ->
      let specification = Option.value ~default:(Json.Object [])
          (List.assoc_opt "execution" (Build_request.implementation_constraints request)) in
      let fields = match specification with Json.Object fields -> fields
        | _ -> fail ~path:"/expected_request/implementation_constraints/execution"
                 "invalid_lowering_execution_policy" "Frozen execution policy must be an object." in
      require (List.for_all (fun (key, _) -> key = "integral_step") fields)
        "invalid_lowering_execution_policy" "Unknown frozen execution policy fields.";
      let step = Option.value ~default:Json.Null (List.assoc_opt "integral_step" fields) in
      (match List.find_opt (fun node -> node.kind = "integrated") ordered with
       | Some node when step = Json.Null ->
           unsupported node "unsupported_lowering_integral_step" "Integration requires frozen execution.integral_step authority."
       | _ -> ());
      match step with
      | Json.Null -> Json.Null
      | value ->
          let dtype = Type_spec.of_json (Json.Object ["kind", str "scalar"; "name", str "Duration";
              "dimensions", Json.Object ["time", Json.int 1]; "arguments", Json.Array []]) in
          let normalized = Type_spec.normalize_binding ~path:"/expected_request/implementation_constraints/execution/integral_step"
              ~expected:dtype value in
          require (Json.number_compare (Json.field "canonical_value" (Json.object_fields normalized)) (Json.int 0) > 0)
            "invalid_lowering_execution_policy" "Integral sampling step must be positive.";
          normalized

let permitted_attributes bindings node =
  let replace key value fields = (key, value) :: List.remove_assoc key fields in
  let fields = match node.kind with
    | "parameter" ->
        let name = Json.string (attribute node "name") in
        let binding = match Names.find_opt name bindings with
          | Some value -> value | None -> fail "invalid_lowering_source" "Frozen source omits a declared parameter binding." in
        node.attributes |> replace "bound" (Json.Bool true) |> replace "default" binding
    | "state" -> node.attributes |> replace "observation" (str "shared_pre_update_state")
                                 |> replace "arbitration" (str "coalesce_identical_else_error")
    | "rule" ->
        let event = attribute node "trigger" = str "event" in
        let fields = node.attributes |> replace "priority" (str "none")
            |> replace "ongoing_activation" (str (if event then "explicit_duration" else "level"))
            |> replace "impulse_activation" (str (if event then "event" else "onset"))
            |> replace "state_assignment" (str (if event then "event" else "level")) in
        if event then replace "ongoing_duration" (str "explicit") fields else fields
    | _ -> node.attributes
  in Json.Object fields

let dependencies node = match node.role with None -> node.inputs | Some role -> role :: node.inputs
let source_facts nodes ordered =
  (* Derive directly from the independently supplied source. Neither the
     Behavior validator's cached facts nor any lowering producer supplies this
     expected ancestry/contact answer. The DAG is guaranteed by Intent.t. *)
  let seen = ref Name_set.empty and pending = ref (List.map (fun node -> node.identity, false) ordered) in
  let ancestry = ref Names.empty and contacts = ref Names.empty and retained = ref 0 in
  while !pending <> [] do
    let identity, closing = List.hd !pending in
    pending := List.tl !pending;
    let node = lookup nodes identity in
    if closing then (
      let lineage = List.fold_left (fun result reference -> Name_set.union result (Names.find reference !ancestry))
          (Name_set.singleton identity) (dependencies node) in
      retained := !retained + Name_set.cardinal lineage;
      require (!retained <= Limits.max_json_nodes) "lowering_lineage_limit" "Complete source ancestry exceeds the wire document budget.";
      ancestry := Names.add identity lineage !ancestry;
      let contact = match node.kind with
        | "scope" -> attribute node "scope" = str "contact"
        | "role" | "state" | "state.is" | "memory" | "memory.is_set" | "literal" | "parameter"
        | "secretion" | "action.state_set" -> false
        | "signature" -> Names.find (input node 0) !contacts
        | _ -> List.exists (fun reference -> Names.find reference !contacts) node.inputs in
      contacts := Names.add identity contact !contacts)
    else if not (Name_set.mem identity !seen) then (
      seen := Name_set.add identity !seen;
      pending := List.map (fun reference -> reference, false) (dependencies node) @ ((identity, true) :: !pending))
  done;
  !ancestry, !contacts

let remaining request =
  let constraints = Build_request.implementation_constraints request in
  let constraints = match Build_request.behavior_profile request with
    | Build_request.V1 -> constraints | Build_request.V2 -> List.remove_assoc "execution" constraints in
  ["source_behavior_execution"; "molecular_realization"; "source_to_candidate_preservation";
   "candidate_acceptance"; "empirical_component_function"; "human_therapeutic_admission"]
  @ (if constraints = [] then [] else ["implementation_constraint_enforcement"])
  @ (if Build_request.preferences request = [] then [] else ["preference_evaluation"])
  @ (if Build_request.target request = None then [] else ["target_assumption_validation"; "biological_evidence_admission"])

let check ~expected_request ~behavior =
  let source = Build_request.intent expected_request in
  let source_fields = Intent.to_json source |> Json.object_fields in
  let ordered = Json.field "nodes" source_fields |> Json.array |> List.map source_node in
  (* Each check contributes four JSON values. Reserve ample room for the
     report and protocol envelope before allocating the per-node census. *)
  require (7 + (3 * List.length ordered) <= (Limits.max_json_nodes - 256) / 4)
    "lowering_report_limit" "Complete preservation-check report exceeds the JSON value budget.";
  let source_nodes = List.fold_left (fun map node -> Names.add node.identity node map) Names.empty ordered in
  source_profile (Build_request.behavior_profile expected_request) source_nodes ordered;
  let checks = ref [] in
  let record ?path property code condition detail =
    require ?path condition code detail;
    checks := { check_property = property; check_detail = detail } :: !checks in
  let profile = match Build_request.behavior_profile expected_request with Build_request.V1 -> Behavior.V0_1 | Build_request.V2 -> Behavior.V0_2 in
  let step = expected_step expected_request ordered in
  let candidate_step = Option.value ~default:Json.Null
      (List.assoc_opt "integral_step" (Json.object_fields (Behavior.policies behavior))) in
  record "execution_profile" "lowering_execution_profile"
    (Behavior.profile behavior = profile && python_mapping_equal candidate_step step)
    "Execution profile and sampled-integration policy match the frozen source authority.";
  (* Behavior.t already requires every other field of the closed policy version.
     Only the request-selected integral step can vary within that language. *)
  record "source_identity" "lowering_source_identity"
    (Behavior.source_fingerprint behavior = Intent.fingerprint source
     && Behavior.name behavior = Json.string (Json.field "name" source_fields))
    "Source semantic fingerprint and program identity match.";
  let emitted = Behavior.nodes behavior in
  record "complete_graph" "lowering_complete_graph"
    (List.map (fun node -> node.identity) ordered = List.map (fun node -> Identity.Node.to_string (Behavior.node_id node)) emitted
     && Json.equal (Json.field "roots" source_fields) (names (List.map Identity.Node.to_string (Behavior.roots behavior))))
    "Every source node and root is retained in deterministic order.";
  let declared_parameters = List.filter (fun node -> node.kind = "parameter") ordered in
  let declared_names = List.map (fun node -> Json.string (attribute node "name")) declared_parameters |> Name_set.of_list in
  let reported_bindings = Behavior.parameter_bindings behavior in
  record "parameter_inventory" "lowering_parameter_inventory"
    (Name_set.equal declared_names (Name_set.of_list (List.map fst reported_bindings)))
    "Bindings cover exactly the declared design parameters.";
  let bindings = Build_request.resolved_bindings expected_request in
  record "authoritative_bindings" "lowering_authoritative_bindings"
    (Json.equal (Json.Object reported_bindings) (Json.Object bindings))
    "Output bindings exactly match the frozen input defaults and explicit overrides.";
  let bindings = List.fold_left (fun map (key, value) -> Names.add key value map) Names.empty bindings in
  List.iter2 (fun original target ->
      let target_fields = Behavior.node_json target |> Json.object_fields in
      let path = "/behavior/nodes/" ^ pointer original.identity in
      record ~path ("operation:" ^ original.identity) "lowering_operation"
        (original.kind = Behavior.kind_name (Behavior.operation target)
         && original.inputs = List.map Identity.Node.to_string (Behavior.inputs target)
         && original.role = Option.map Identity.Role.to_string (Behavior.role target)
         && python_mapping_equal original.data_type (Json.field "data_type" target_fields))
        "Operation, ordered dependencies, role and raw semantic type are preserved.";
      record ~path ("semantics:" ^ original.identity) "lowering_semantics"
        (Json.equal (Behavior.attributes target) (permitted_attributes bindings original))
        "Only declared parameter substitution and state/rule execution-policy normalization change attributes.";
      record ~path ("source:" ^ original.identity) "lowering_source_location"
        (Json.equal original.source (Json.field "source" target_fields))
        "Original authoring source location is retained.") ordered emitted;
  let ancestry, contacts = source_facts source_nodes ordered in
  let expected_requirements = List.filter (fun node -> List.mem node.kind ["rule"; "state"; "memory"]) ordered
      |> List.map (fun node -> Json.Object [
          "id", str ("requirement:" ^ node.identity); "kind", str node.kind; "source_node_id", str node.identity;
          "lineage", names (Name_set.elements (Names.find node.identity ancestry)); "source", node.source]) in
  let expected_links = Names.bindings ancestry |> List.map (fun (key, values) -> key, names (Name_set.elements values)) in
  let observed_links = Behavior.source_links behavior |> List.map (fun (key, values) ->
      Identity.Node.to_string key, names (List.map Identity.Node.to_string values)) in
  record "requirements_and_lineage" "lowering_requirements_and_lineage"
    (Json.equal (Json.Array expected_requirements)
       (Json.Array (List.map (Behavior.requirement_json ~include_source:true) (Behavior.requirements behavior)))
     && Json.equal (Json.Object expected_links) (Json.Object observed_links))
    "Every source rule/state/memory requirement and sorted complete ancestor lineage survives.";
  record "identity_binding" "lowering_identity_binding"
    (List.for_all (fun node -> Behavior.contact_bound node = Names.find (Identity.Node.to_string (Behavior.node_id node)) contacts) emitted)
    "Contact-object correlation and cell-local state boundaries are retained.";
  { request_fingerprint = Build_request.fingerprint expected_request;
    request_artifact_fingerprint = Build_request.artifact_fingerprint expected_request;
    source_fingerprint = Intent.fingerprint source;
    behavior_fingerprint = Behavior.fingerprint behavior;
    behavior_artifact_fingerprint = Canonical.fingerprint (Behavior.to_json behavior);
    behavior_profile = Behavior.schema_version (Behavior.profile behavior);
    preservation_checks = List.rev !checks; remaining_obligations = remaining expected_request }

let to_json value = Json.Object [
    "schema_version", str schema_version; "checker_version", str checker_version;
    "validation_scope", str validation_scope; "claim_scope", str claim_scope; "passed", Json.Bool true;
    "request_fingerprint", str value.request_fingerprint; "request_artifact_fingerprint", str value.request_artifact_fingerprint;
    "source_fingerprint", str value.source_fingerprint; "behavior_fingerprint", str value.behavior_fingerprint;
    "behavior_artifact_fingerprint", str value.behavior_artifact_fingerprint; "behavior_profile", str value.behavior_profile;
    "checks", Json.Array (List.map (fun check -> Json.Object ["property", str check.check_property;
        "passed", Json.Bool true; "detail", str check.check_detail]) value.preservation_checks);
    "unimplemented_obligations", names value.remaining_obligations]

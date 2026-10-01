open Bioc_wire
module M = Measurement_contract
module S = M.Scalar
module I = M.Interval
module O = M.Observable
module R = M.Response
module N = Runtime_number
module Claim = Build_request.Target_claim
let str value = Json.String value
let field = M.field
let check ?path condition message = Diagnostic.require ?path condition "invalid_human_contract" message
let schema path version keys fixed value =
  let fields = M.record ~path version (keys @ List.map fst fixed) value in
  List.iter (fun (key, expected) -> check ~path:(path ^ "/" ^ key) (Json.equal (Json.field key fields) expected) "Fixed human contract semantics cannot be relabelled.") fixed;
  fields
let record path version keys value = schema path version keys [] value
let finish fields = M.finish (Json.Object fields)
let get path fields key = Json.field ~path:(path ^ "/" ^ key) key fields
let name path fields key = Json.name ~path:(path ^ "/" ^ key) (get path fields key)
let optional decode = function Json.Null -> None | value -> Some (decode value)
let option_json encode = function None -> Json.Null | Some value -> encode value
let hash path value =
  let value = Json.string ~path value in
  check ~path (String.length value = 64 && String.for_all (function '0' .. '9' | 'a' .. 'f' -> true | _ -> false) value)
    "Expected a lowercase SHA-256 identity."; value
let claim path key fields = Claim.of_json ~path:(path ^ "/" ^ key) (get path fields key)
let claims_json fields claims = List.fold_left (fun fields (key, claim) -> M.replace key (Claim.to_json claim) fields) fields claims
let normalized_type_equal = M.type_equal
let le a b = N.compare a b <= 0
let lt a b = N.compare a b < 0

module Measurement = struct
  type access = Cell | External_evaluator
  type t = { json : Json.t; observable : O.t; access : access; support : Claim.t }
  let schema_version = "biocompiler.measurement_spec.v0.1"
  let of_json ?(path = "") value =
    let fields = record path schema_version ["observable"; "meaning"; "access"; "method"; "support"] value in
    let observable = O.of_json ~path:(path ^ "/observable") (get path fields "observable") in
    check ~path (Type_spec.kind (O.dtype observable) = Type_spec.Scalar && O.scope observable = O.Cell)
      "Human measurements require scalar single-cell observables.";
    let access = match Json.string (get path fields "access") with "cell" -> Cell | "external_evaluator" -> External_evaluator
      | _ -> Diagnostic.fail ~path "invalid_human_contract" "Unknown measurement access." in
    ignore (name path fields "meaning"); ignore (name path fields "method");
    let support = claim path "support" fields in
    {json = finish (fields |> M.replace "observable" (O.to_json observable) |> M.replace "support" (Claim.to_json support)); observable; access; support}
  let to_json value = value.json
  let fingerprint value = Canonical.fingerprint value.json
  let observable value = value.observable
  let access value = value.access
  let support value = value.support
end
module Predicate = struct
  type operator = Greater | Greater_equal | Less | Less_equal
  type t = {json : Json.t; id : string; operator : operator; threshold : S.t; support : Claim.t}
  let schema_version = "biocompiler.predicate_refinement.v0.1"
  let of_json ?(path = "") value =
    let fields = record path schema_version ["predicate_id"; "operator"; "threshold"; "support"] value in
    let id = name path fields "predicate_id" in
    let operator = match Json.string (get path fields "operator") with ">" -> Greater | ">=" -> Greater_equal | "<" -> Less | "<=" -> Less_equal
      | _ -> Diagnostic.fail ~path "invalid_human_contract" "Unsupported predicate threshold operator." in
    let threshold = S.of_json ~path:(path ^ "/threshold") (get path fields "threshold") and support = claim path "support" fields in
    {json = finish (fields |> M.replace "threshold" (S.to_json threshold) |> M.replace "support" (Claim.to_json support)); id; operator; threshold; support}
  let to_json value = value.json
  let fingerprint value = Canonical.fingerprint value.json
  let id value = value.id
  let operator value = value.operator
  let threshold value = value.threshold
  let support value = value.support
  let accepts value candidate =
    let candidate = S.of_json ~expected:(S.dtype value.threshold) (S.to_json candidate) |> S.canonical in
    let order = N.compare candidate (S.canonical value.threshold) in
    match value.operator with Greater -> order > 0 | Greater_equal -> order >= 0 | Less -> order < 0 | Less_equal -> order <= 0
end
module Conditional_secretion = struct
  type t = {json : Json.t; input : Measurement.t; output : Measurement.t; predicate : Predicate.t;
            response : R.t; horizon : S.t; claims : (string * Claim.t) list}
  let schema_version = "biocompiler.conditional_secretion_contract.v0.1"
  let fixed = List.map (fun (k,v) -> k,str v) ["profile", "human_conditional_secretion.v0.1";
      "initialization", "inactive_input_and_output_at_zero_no_prehistory"; "persistence", "active_range_after_deadline_while_input_qualifies";
      "termination", "inactive_range_after_recovery_deadline"; "retrigger", "latest_input_transition_replaces_pending_deadline"]
  let of_json ?(path = "") value =
    let fields = schema path schema_version ["id"; "goal_id"; "product"; "input_signal_id"; "input_measurement"; "input_range";
        "predicate"; "output_measurement"; "response"; "initial_range"; "horizon"; "goal_refinement"; "response_support"] fixed value in
    List.iter (fun key -> ignore (name path fields key)) ["id"; "goal_id"; "product"; "input_signal_id"];
    let input = Measurement.of_json ~path:(path ^ "/input_measurement") (get path fields "input_measurement")
    and output = Measurement.of_json ~path:(path ^ "/output_measurement") (get path fields "output_measurement")
    and predicate = Predicate.of_json ~path:(path ^ "/predicate") (get path fields "predicate")
    and response = R.of_json ~path:(path ^ "/response") (get path fields "response") in
    check ~path (Measurement.access input = Measurement.Cell && Measurement.access output = Measurement.External_evaluator)
      "Input access must be cellular and output access external evaluator.";
    let incoming = Measurement.observable input and outgoing = Measurement.observable output in
    check ~path (O.id incoming <> O.id outgoing && O.role incoming = O.role outgoing) "Measurement endpoints must be distinct and share their executing role.";
    check ~path (normalized_type_equal (O.dtype outgoing) M.production_rate_type) "Output requires the exact ProductionRate type.";
    check ~path (Json.equal (O.to_json (R.observable response)) (O.to_json outgoing)) "Response must bind the complete output measurement.";
    check ~path (normalized_type_equal (S.dtype (Predicate.threshold predicate)) (O.dtype incoming)) "Threshold type must equal the measured input type.";
    let bounds = I.of_json ~path:(path ^ "/input_range") ~expected:(O.dtype incoming) (get path fields "input_range") in
    let threshold = S.canonical (Predicate.threshold predicate) in
    check ~path (le (I.lower bounds) threshold && le threshold (I.upper bounds)
                 && Predicate.accepts predicate (I.lower_scalar bounds) <> Predicate.accepts predicate (I.upper_scalar bounds))
      "Input domain must include the threshold and exercise both predicate values.";
    let initial = I.of_json ~path:(path ^ "/initial_range") ~expected:(O.dtype outgoing) (get path fields "initial_range") in
    let inactive = R.inactive response in
    check ~path (le N.zero (I.lower initial) && le (I.lower inactive) (I.lower initial) && le (I.upper initial) (I.upper inactive))
      "Initial output must be a nonnegative subset of the inactive range.";
    check ~path (le N.zero (I.lower inactive) && lt (I.upper inactive) (I.lower (R.active response))) "Active rates must exceed nonnegative inactive rates.";
    let horizon = S.duration ~path:(path ^ "/horizon") ~positive:true (get path fields "horizon") in
    check ~path (lt (N.add (S.canonical (R.activation response)) (S.canonical (R.deactivation response))) (S.canonical horizon))
      "Horizon must exceed the activation and recovery delay sum.";
    let goal = claim path "goal_refinement" fields and support = claim path "response_support" fields in
    let claims = ["input_measurement", Measurement.support input; "predicate", Predicate.support predicate;
      "output_measurement", Measurement.support output; "goal_refinement", goal; "response_support", support] in
    let json = fields |> M.replace "input_measurement" (Measurement.to_json input) |> M.replace "output_measurement" (Measurement.to_json output)
      |> M.replace "predicate" (Predicate.to_json predicate) |> M.replace "response" (R.to_json response)
      |> M.replace "input_range" (I.to_json bounds) |> M.replace "initial_range" (I.to_json initial) |> M.replace "horizon" (S.to_json horizon)
      |> M.replace "goal_refinement" (Claim.to_json goal) |> M.replace "response_support" (Claim.to_json support) |> finish in
    {json; input; output; predicate; response; horizon; claims}
  let to_json value = value.json
  let fingerprint value = Canonical.fingerprint value.json
  let input value = value.input
  let output value = value.output
  let predicate value = value.predicate
  let response value = value.response
  let horizon value = value.horizon
  let goal_id value = Json.string (field "goal_id" value.json)
  let product value = Json.string (field "product" value.json)
  let input_signal_id value = Json.string (field "input_signal_id" value.json)
  let claims value = value.claims
end
module Platform = struct
  type t = {json : Json.t; claims : (string * Claim.t) list}
  let schema_version = "biocompiler.delivery_platform_spec.v0.1"
  let of_json ?(path = "") value =
    let keys = ["administration_context"; "recipient_targeting"; "support"] in
    let fields = record path schema_version ("identity" :: "payload_format" :: keys) value in
    let identity = Pinned_identity.of_json ~path:(path ^ "/identity") (get path fields "identity") in
    check ~path (List.mem (Pinned_identity.kind identity) [Pinned_identity.Source; Pinned_identity.Reference]) "Delivery platform requires a source or reference pin.";
    check ~path (List.mem (Json.string (get path fields "payload_format")) ["DNA"; "RNA"]) "Delivery modality must be explicit DNA or RNA.";
    let claims = List.map (fun key -> key, claim path key fields) keys in
    {json = claims_json fields claims |> M.replace "identity" (Pinned_identity.to_json identity) |> finish; claims}
  let to_json value = value.json
  let payload_format value = Json.string (field "payload_format" value.json)
  let claims value = value.claims
end
module Exposure = struct
  type t = {json : Json.t; id : string; observable : string; compartment : string; support : Claim.t}
  let schema_version = "biocompiler.exposure_assumption.v0.1"
  let of_json ?(path = "") value =
    let fields = record path schema_version ["id"; "observable"; "compartment"; "domain"; "support"] value in
    let id = name path fields "id" and observable = name path fields "observable" and compartment = name path fields "compartment" in
    let domain = Component_contract.Value_domain.of_json ~path:(path ^ "/domain") (get path fields "domain") in
    let module V = Component_contract.Value_domain in
    check ~path (Type_spec.kind (V.dtype domain) = Type_spec.Scalar && List.mem (V.kind domain) [V.Scalar_interval; V.Unknown_domain]) "Exposure requires a scalar interval or explicitly unknown domain.";
    Option.iter (fun value -> check ~path (le N.zero value) "Exposure lower bound must be nonnegative.") (V.lower domain);
    let support = claim path "support" fields in
    {json = fields |> M.replace "domain" (V.to_json domain) |> M.replace "support" (Claim.to_json support) |> finish; id; observable; compartment; support}
  let to_json value = value.json
  let id value = value.id
  let observable value = value.observable
  let compartment value = value.compartment
  let support value = value.support
end
module Expression_timing = struct
  type t = {json : Json.t; support : Claim.t}
  let schema_version = "biocompiler.expression_timing.v0.1"
  let of_json ?(path = "") value =
    let fields = schema path schema_version ["onset"; "duration"; "behavior_start"; "unknown_reason"; "support"]
      ["clock", str "start_of_declared_exposure"; "availability", str "closed_window_from_onset_through_onset_plus_duration"] value in
    let window key = optional (I.of_json ~path:(path ^ "/" ^ key) ~expected:M.duration_type) (get path fields key) in
    let onset = window "onset" and duration = window "duration" in
    Option.iter (fun value -> check ~path (le N.zero (I.lower value)) "Expression onset must be nonnegative.") onset;
    Option.iter (fun value -> check ~path (lt N.zero (I.lower value)) "Expression duration must be positive.") duration;
    if onset = None || duration = None then ignore (name path fields "unknown_reason")
    else check ~path (get path fields "unknown_reason" = Json.Null) "Known expression timing cannot have an unknown reason.";
    let start = S.duration ~path:(path ^ "/behavior_start") (get path fields "behavior_start") and support = claim path "support" fields in
    {json = fields |> M.replace "onset" (option_json I.to_json onset) |> M.replace "duration" (option_json I.to_json duration)
       |> M.replace "behavior_start" (S.to_json start) |> M.replace "support" (Claim.to_json support) |> finish; support}
  let to_json value = value.json
  let support value = value.support
end
module Co_payload = struct
  type t = {json : Json.t; id : string; destination : string; support : Claim.t}
  let schema_version = "biocompiler.co_payload_requirement.v0.1"
  let of_json ?(path = "") value =
    let fields = schema path schema_version ["id"; "payload_identity"; "capability"; "destination"; "required_overlap"; "support"]
      ["recipient_scope", str "same_selected_recipient_cell"; "required", Json.Bool true] value in
    let id = name path fields "id" and destination = name path fields "destination" in ignore (name path fields "capability");
    let identity = Pinned_identity.of_json ~path:(path ^ "/payload_identity") (get path fields "payload_identity") in
    check ~path (Pinned_identity.kind identity = Pinned_identity.Reference) "Co-payload requires a reference pin.";
    let overlap = I.of_json ~path:(path ^ "/required_overlap") ~expected:M.duration_type (get path fields "required_overlap") in
    check ~path (le N.zero (I.lower overlap) && lt (I.lower overlap) (I.upper overlap)) "Same-cell overlap must have nonnegative start and positive extent.";
    let support = claim path "support" fields in
    {json = fields |> M.replace "payload_identity" (Pinned_identity.to_json identity) |> M.replace "required_overlap" (I.to_json overlap)
       |> M.replace "support" (Claim.to_json support) |> finish; id; destination; support}
  let to_json value = value.json
  let id value = value.id
  let destination value = value.destination
  let support value = value.support
end
let collection path decode identity value =
  let values = Json.array ~path value |> M.bounded_list ~path |> List.mapi (fun index -> decode ~path:(path ^ "/" ^ string_of_int index)) in
  let values = List.sort (fun a b -> String.compare (identity a) (identity b)) values in
  check ~path (List.length values = List.length (List.sort_uniq String.compare (List.map identity values))) "Duplicate human contract inventory identities.";
  values
module Deployment = struct
  type t = {json : Json.t; platform : Platform.t; exposures : Exposure.t list; co_payloads : Co_payload.t list; claims : (string * Claim.t) list}
  let schema_version = "biocompiler.deployment_contract.v0.1"
  let of_json ?(path = "") value =
    let fields = schema path schema_version ["id"; "target_fingerprint"; "recipient_role"; "platform"; "intended_population"; "excluded_population";
      "intracellular_destination"; "exposure_window"; "exposures"; "timing"; "unintended_recipients"; "co_payloads"]
      ["time_origin", str "start_of_declared_exposure"; "delivery_targeting_is_disease_recognition", Json.Bool false] value in
    List.iter (fun key -> ignore (name path fields key)) ["id"; "recipient_role"; "intracellular_destination"];
    ignore (hash (path ^ "/target_fingerprint") (get path fields "target_fingerprint"));
    let platform = Platform.of_json ~path:(path ^ "/platform") (get path fields "platform")
    and timing = Expression_timing.of_json ~path:(path ^ "/timing") (get path fields "timing") in
    let declarations = List.map (fun key -> key, claim path key fields) ["intended_population"; "excluded_population"; "unintended_recipients"] in
    let window = I.of_json ~path:(path ^ "/exposure_window") ~expected:M.duration_type (get path fields "exposure_window") in
    check ~path (N.equal (I.lower window) N.zero && lt N.zero (I.upper window)) "Exposure window must start at zero and have positive extent.";
    let exposures = collection (path ^ "/exposures") (fun ~path value -> Exposure.of_json ~path value) Exposure.id (get path fields "exposures")
    and co_payloads = collection (path ^ "/co_payloads") (fun ~path value -> Co_payload.of_json ~path value) Co_payload.id (get path fields "co_payloads") in
    check ~path (exposures <> []) "Deployment requires a nonempty explicit exposure inventory.";
    let endpoints = List.map (fun value -> Exposure.observable value, Exposure.compartment value) exposures in
    check ~path (List.length endpoints = List.length (List.sort_uniq Stdlib.compare endpoints)) "Exposure endpoints must be unique.";
    let claims = List.map (fun (key,value) -> "platform." ^ key,value) (Platform.claims platform)
      @ ["intended_population", List.assoc "intended_population" declarations; "excluded_population", List.assoc "excluded_population" declarations;
         "timing", Expression_timing.support timing; "unintended_recipients", List.assoc "unintended_recipients" declarations]
      @ List.map (fun value -> "exposures." ^ Exposure.id value, Exposure.support value) exposures
      @ List.map (fun value -> "co_payloads." ^ Co_payload.id value, Co_payload.support value) co_payloads in
    {json = claims_json fields declarations |> M.replace "platform" (Platform.to_json platform) |> M.replace "timing" (Expression_timing.to_json timing)
       |> M.replace "exposure_window" (I.to_json window) |> M.replace "exposures" (Json.Array (List.map Exposure.to_json exposures))
       |> M.replace "co_payloads" (Json.Array (List.map Co_payload.to_json co_payloads)) |> finish; platform; exposures; co_payloads; claims}
  let to_json value = value.json
  let fingerprint value = Canonical.fingerprint value.json
  let target_fingerprint value = Json.string (field "target_fingerprint" value.json)
  let recipient_role value = Json.string (field "recipient_role" value.json)
  let platform value = value.platform
  let exposures value = value.exposures
  let co_payloads value = value.co_payloads
  let destination value = Json.string (field "intracellular_destination" value.json)
  let intended_population value = List.assoc "intended_population" value.claims
  let excluded_population value = List.assoc "excluded_population" value.claims
  let claims value = value.claims
end
module Input_availability = struct
  type t = {json : Json.t; delay : S.t; observability : Claim.t; controllability : Claim.t}
  let schema_version = "biocompiler.input_availability_spec.v0.1"
  let of_json ?(path = "") value =
    let fields = schema path schema_version ["id"; "observation_method"; "response_delay"; "observability"; "controllability"]
      ["loss_requirement", str "background_after_deadline_while_cell_access_unavailable"; "reacquisition", str "restart_predicate_timing_without_inferred_prehistory";
       "implementation", str "unestablished"] value in
    ignore (name path fields "id"); ignore (name path fields "observation_method");
    let delay = S.duration ~path:(path ^ "/response_delay") (get path fields "response_delay")
    and observability = claim path "observability" fields and controllability = claim path "controllability" fields in
    {json = claims_json fields ["observability", observability; "controllability", controllability] |> M.replace "response_delay" (S.to_json delay) |> finish;
     delay; observability; controllability}
  let to_json value = value.json
  let delay value = value.delay
  let claims value = ["observability", value.observability; "controllability", value.controllability]
end
module External_shutdown = struct
  type t = {json : Json.t; delay : S.t; observability : Claim.t; controllability : Claim.t}
  let schema_version = "biocompiler.external_shutdown_spec.v0.1"
  let of_json ?(path = "") value =
    let fields = schema path schema_version ["id"; "request_definition"; "observation_method"; "response_delay"; "observability"; "controllability"]
      ["request_access", str "external_evaluator"; "persistence", str "latched_for_remaining_horizon"; "requirement", str "background_after_deadline";
       "overrides_source_guard", Json.Bool false; "actuator_support", str "unimplemented"] value in
    List.iter (fun key -> ignore (name path fields key)) ["id"; "request_definition"; "observation_method"];
    let delay = S.duration ~path:(path ^ "/response_delay") (get path fields "response_delay")
    and observability = claim path "observability" fields and controllability = claim path "controllability" fields in
    {json = claims_json fields ["observability", observability; "controllability", controllability] |> M.replace "response_delay" (S.to_json delay) |> finish;
     delay; observability; controllability}
  let to_json value = value.json
  let delay value = value.delay
  let claims value = ["observability", value.observability; "controllability", value.controllability]
end
module Acceptance = struct
  type t = {json : Json.t; healthy : Measurement.t; background : S.t; peak : S.t;
            availability : Input_availability.t; shutdown : External_shutdown.t; claims : (string * Claim.t) list}
  let schema_version = "biocompiler.human_acceptance_contract.v0.1"
  let of_json ?(path = "") value =
    let fixed = List.map (fun (key,value) -> key,str value) ["combination", "conjunction_no_priority_override";
      "healthy_inactivity", "immediate_background_bound"; "peak_scope", "all_observed_times_including_transition_grace";
      "response_duration", "continuous_bout_strictly_above_background_ceiling"; "scope", "single_recipient_cell_finite_horizon"] in
    let fields = schema path schema_version ["id"; "behavior_fingerprint"; "healthy_measurement"; "context_domain"; "healthy_range";
      "background_ceiling"; "peak_ceiling"; "max_response_duration"; "bounds_support"; "input_availability"; "shutdown"] fixed value in
    ignore (name path fields "id"); ignore (hash (path ^ "/behavior_fingerprint") (get path fields "behavior_fingerprint"));
    let healthy = Measurement.of_json ~path:(path ^ "/healthy_measurement") (get path fields "healthy_measurement") in
    check ~path (Measurement.access healthy = Measurement.External_evaluator) "Healthy context requires evaluator measurement.";
    let dtype = O.dtype (Measurement.observable healthy) in
    let domain = I.of_json ~path:(path ^ "/context_domain") ~expected:dtype (get path fields "context_domain")
    and range = I.of_json ~path:(path ^ "/healthy_range") ~expected:dtype (get path fields "healthy_range") in
    check ~path (le (I.lower domain) (I.lower range) && le (I.upper range) (I.upper domain)
      && not (N.equal (I.lower domain) (I.lower range) && N.equal (I.upper domain) (I.upper range)))
      "Context must contain the healthy interval and permit nonhealthy observations.";
    let rate key = S.of_json ~path:(path ^ "/" ^ key) ~expected:M.production_rate_type (get path fields key) in
    let background = rate "background_ceiling" and peak = rate "peak_ceiling" in
    check ~path (le N.zero (S.canonical background) && lt (S.canonical background) (S.canonical peak)) "Peak must exceed a nonnegative background ceiling.";
    let duration = S.duration ~path:(path ^ "/max_response_duration") ~positive:true (get path fields "max_response_duration")
    and support = claim path "bounds_support" fields
    and availability = Input_availability.of_json ~path:(path ^ "/input_availability") (get path fields "input_availability")
    and shutdown = External_shutdown.of_json ~path:(path ^ "/shutdown") (get path fields "shutdown") in
    let claims = ["healthy_measurement", Measurement.support healthy; "bounds_support", support]
      @ List.map (fun (key,value) -> "input_availability." ^ key,value) (Input_availability.claims availability)
      @ List.map (fun (key,value) -> "shutdown." ^ key,value) (External_shutdown.claims shutdown) in
    {json = fields |> M.replace "healthy_measurement" (Measurement.to_json healthy) |> M.replace "context_domain" (I.to_json domain)
       |> M.replace "healthy_range" (I.to_json range) |> M.replace "background_ceiling" (S.to_json background) |> M.replace "peak_ceiling" (S.to_json peak)
       |> M.replace "max_response_duration" (S.to_json duration) |> M.replace "bounds_support" (Claim.to_json support)
       |> M.replace "input_availability" (Input_availability.to_json availability) |> M.replace "shutdown" (External_shutdown.to_json shutdown) |> finish;
     healthy; background; peak; availability; shutdown; claims}
  let to_json value = value.json
  let fingerprint value = Canonical.fingerprint value.json
  let behavior_fingerprint value = Json.string (field "behavior_fingerprint" value.json)
  let healthy_measurement value = value.healthy
  let background value = value.background
  let peak value = value.peak
  let input_availability value = value.availability
  let shutdown value = value.shutdown
  let claims value = value.claims
end

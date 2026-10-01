open Bioc_wire
module M = Measurement_contract
module H = Human_contract
module O = M.Observable
module S = M.Scalar
module I = M.Interval
module R = M.Response
module N = Runtime_number
module Names = Set.Make (String)
module Nodes = Map.Make (String)
let field = M.field
let str value = Json.String value
let named key value = Json.string (field key value)
let check ?path condition message = Diagnostic.require ?path condition "invalid_human_request" message
let inputs value = Json.array (field "inputs" value) |> List.map Json.string
let attribute key value = List.assoc_opt key (Json.object_fields (field "attributes" value))
let human_target request =
  check (Build_request.target_kind request = Some Build_request.Human_target) "Human wrappers require the complete versioned human target.";
  match Build_request.target request with Some value -> Build_request.Target.of_json value | None -> assert false
let physical target compartment = compartment <> "abstract" && List.mem compartment (Build_request.Target.compartments target)
let evidence target claims =
  let ids = Json.array (field "evidence" (field "human_target" (Build_request.Target.to_json target)))
    |> List.map (named "id") |> Names.of_list in
  List.iter (fun (path, claim) -> check ~path (List.for_all (fun id -> Names.mem id ids) (H.Claim.evidence_ids claim))
      "Human contract cites an absent target evidence identity.") claims
let chain version child_key child_id contract_key contract_id = Canonical.fingerprint (Json.Object [
    "schema_version", str version; child_key, str child_id; contract_key, str contract_id])

module Behavior_request = struct
  type t = {request : Build_request.t; contract : H.Conditional_secretion.t; target : Build_request.Target.t; json : Json.t}
  let schema_version = "biocompiler.human_behavior_request.v0.1"
  let make ~build_request:request ~contract =
    let target = human_target request in
    let module C = H.Conditional_secretion in
    let incoming = H.Measurement.observable (C.input contract) and outgoing = H.Measurement.observable (C.output contract) in
    let source = Build_request.intent request |> Intent.to_json in
    let nodes = Json.array (field "nodes" source) |> List.fold_left (fun result node -> Nodes.add (named "id" node) node result) Nodes.empty in
    let find id kind = match Nodes.find_opt id nodes with
      | Some node when named "kind" node = kind -> node
      | _ -> Diagnostic.fail ~path:("/build_request/intent/nodes/" ^ id) "invalid_human_request" ("Human contract source must be " ^ kind ^ ".") in
    let role = find (O.role incoming) "role" and goal = find (C.goal_id contract) "goal"
    and signal = find (C.input_signal_id contract) "signal" and predicate = find (H.Predicate.id (C.predicate contract)) "qualitative"
    and rule = find (R.rule_id (C.response contract)) "rule" and action = find (R.specification_id (C.response contract)) "action.secrete" in
    check (List.length (inputs signal) = 1 && List.length (inputs action) = 1) "Human profile requires one signal and an unspecified secretion rate.";
    let scope = find (List.hd (inputs signal)) "scope" and secretion = find (List.hd (inputs action)) "secretion" in
    let expected = List.map (named "id") [role; goal; signal; predicate; rule; action; scope; secretion] |> Names.of_list in
    check (Names.equal expected (Nodes.fold (fun id _ result -> Names.add id result) nodes Names.empty)) "Every source node must belong to the exact human observation profile.";
    let role_id = named "id" role in
    check (List.for_all (fun node -> field "role" node = str role_id) [signal; predicate; rule; action; scope; secretion]) "Human source nodes must share the selected role.";
    check (attribute "engineering" role = Some (str "in_vivo")) "Human source role must declare in-vivo engineering.";
    check (inputs scope = [role_id] && attribute "scope" scope = Some (str "external") && attribute "scope" signal = Some (str "external"))
      "Human source requires an external cell-accessible signal without contact binding.";
    check (M.type_equal (Type_spec.of_json (field "data_type" signal)) (O.dtype incoming)) "Human measurement must preserve the exact source signal type.";
    check (inputs predicate = [named "id" signal]) "Predicate must bind the exact source signal.";
    let direction = match attribute "band" predicate, H.Predicate.operator (C.predicate contract) with
      | Some (Json.String ("high" | "present")), (H.Predicate.Greater | H.Predicate.Greater_equal) -> true
      | Some (Json.String "low"), (H.Predicate.Less | H.Predicate.Less_equal) -> true
      | _ -> false in
    check direction "Threshold direction conflicts with the source qualitative predicate.";
    check (inputs rule = [role_id; named "id" predicate; named "id" action]
      && attribute "trigger" rule = Some (str "condition") && attribute "execution" rule = Some (str "concurrent")
      && attribute "priority" rule = Some (str "unspecified")) "Unsupported human source guard, action or rule policy.";
    check (attribute "ongoing" action = Some (Json.Bool true) && attribute "rate" action = Some (str "unspecified")) "Human source requires ongoing secretion with an explicitly refined rate.";
    check (inputs secretion = [role_id] && attribute "product" secretion = Some (str (C.product contract))) "Human product differs from source secretion.";
    let roots = Json.array (field "roots" source) |> List.map Json.string |> Names.of_list in
    check (Names.equal roots (Names.of_list [role_id; named "id" goal; named "id" secretion; named "id" rule])) "Human source roots cannot be omitted or reinterpreted.";
    check (List.for_all (fun endpoint -> physical target (O.compartment endpoint)) [incoming; outgoing]) "Human measurements require declared physical target compartments.";
    evidence target (C.claims contract);
    let json = M.finish (Json.Object ["schema_version", str schema_version; "build_request", Build_request.to_json request; "contract", C.to_json contract]) in
    {request; contract; target; json}
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["build_request"; "contract"] value in
    make ~build_request:(Build_request.of_json (Json.field "build_request" fields))
      ~contract:(H.Conditional_secretion.of_json ~path:(path ^ "/contract") (Json.field "contract" fields))
  let to_json value = value.json
  let fingerprint value = chain schema_version "build_request" (Build_request.fingerprint value.request) "contract" (H.Conditional_secretion.fingerprint value.contract)
  let artifact_fingerprint value = Canonical.fingerprint value.json
  let build_request value = value.request
  let target value = value.target
  let contract value = value.contract
end
module Deployment_request = struct
  type t = {behavior : Behavior_request.t; deployment : H.Deployment.t; json : Json.t}
  let schema_version = "biocompiler.human_deployment_request.v0.1"
  let make ~behavior_request:behavior ~deployment =
    let target = Behavior_request.target behavior in
    let module D = H.Deployment in
    let target_json = Build_request.Target.to_json target in
    check (D.target_fingerprint deployment = Build_request.Target.fingerprint target) "Deployment binds stale or different target authority.";
    check (D.recipient_role deployment = O.role (H.Measurement.observable (H.Conditional_secretion.input (Behavior_request.contract behavior))))
      "Deployment must bind the exact source recipient role.";
    check (H.Platform.payload_format (D.platform deployment) = Build_request.Target.payload_format target) "Deployment modality must preserve the source target.";
    let target_contract = field "human_target" target_json in
    check (Json.equal (H.Claim.to_json (D.intended_population deployment)) (field "population_inclusion" target_contract)
      && Json.equal (H.Claim.to_json (D.excluded_population deployment)) (field "population_exclusion" target_contract))
      "Deployment must preserve complete inclusion and exclusion claims.";
    let compartments = D.destination deployment :: List.map H.Exposure.compartment (D.exposures deployment)
      @ List.map H.Co_payload.destination (D.co_payloads deployment) in
    check (List.for_all (physical target) compartments) "Deployment destinations and exposures require declared physical target compartments.";
    evidence target (D.claims deployment);
    let json = M.finish (Json.Object ["schema_version", str schema_version; "behavior_request", Behavior_request.to_json behavior; "deployment", D.to_json deployment]) in
    {behavior; deployment; json}
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["behavior_request"; "deployment"] value in
    make ~behavior_request:(Behavior_request.of_json ~path:(path ^ "/behavior_request") (Json.field "behavior_request" fields))
      ~deployment:(H.Deployment.of_json ~path:(path ^ "/deployment") (Json.field "deployment" fields))
  let to_json value = value.json
  let fingerprint value = chain schema_version "behavior_request" (Behavior_request.fingerprint value.behavior) "deployment" (H.Deployment.fingerprint value.deployment)
  let artifact_fingerprint value = Canonical.fingerprint value.json
  let behavior_request value = value.behavior
  let build_request value = Behavior_request.build_request value.behavior
  let target value = Behavior_request.target value.behavior
  let deployment value = value.deployment
end
module Acceptance_request = struct
  type t = {deployment : Deployment_request.t; acceptance : H.Acceptance.t; json : Json.t}
  let schema_version = "biocompiler.human_acceptance_request.v0.1"
  let make ~deployment_request:deployment ~acceptance =
    let target = Deployment_request.target deployment and behavior = Deployment_request.behavior_request deployment in
    let module A = H.Acceptance in
    let contract = Behavior_request.contract behavior in
    check (A.behavior_fingerprint acceptance = Behavior_request.fingerprint behavior) "Acceptance binds stale or different required behavior.";
    let observation = H.Measurement.observable (A.healthy_measurement acceptance)
    and input = H.Measurement.observable (H.Conditional_secretion.input contract)
    and output = H.Measurement.observable (H.Conditional_secretion.output contract) in
    check (O.role observation = O.role input && physical target (O.compartment observation)) "Healthy context must bind the same recipient and a physical target compartment.";
    check (O.id observation <> O.id input && O.id observation <> O.id output) "Healthy context must use a distinct measurement endpoint.";
    let response = H.Conditional_secretion.response contract in
    let background = S.canonical (A.background acceptance) in
    check (N.compare (I.lower (R.inactive response)) background <= 0 && N.compare background (I.upper (R.inactive response)) <= 0)
      "Acceptance background must refine the source inactive range.";
    check (N.compare (S.canonical (A.peak acceptance)) (I.lower (R.active response)) >= 0) "Acceptance peak excludes all required active rates.";
    List.iter (fun delay -> check (N.compare (S.canonical delay) (S.canonical (H.Conditional_secretion.horizon contract)) < 0)
        "Acceptance recovery and control deadlines must precede the horizon.")
      [H.Input_availability.delay (A.input_availability acceptance); H.External_shutdown.delay (A.shutdown acceptance)];
    evidence target (A.claims acceptance);
    let json = M.finish (Json.Object ["schema_version", str schema_version; "deployment_request", Deployment_request.to_json deployment; "acceptance", A.to_json acceptance]) in
    {deployment; acceptance; json}
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["deployment_request"; "acceptance"] value in
    make ~deployment_request:(Deployment_request.of_json ~path:(path ^ "/deployment_request") (Json.field "deployment_request" fields))
      ~acceptance:(H.Acceptance.of_json ~path:(path ^ "/acceptance") (Json.field "acceptance" fields))
  let to_json value = value.json
  let fingerprint value = chain schema_version "deployment_request" (Deployment_request.fingerprint value.deployment) "acceptance" (H.Acceptance.fingerprint value.acceptance)
  let artifact_fingerprint value = Canonical.fingerprint value.json
  let deployment_request value = value.deployment
  let behavior_request value = Deployment_request.behavior_request value.deployment
  let build_request value = Deployment_request.build_request value.deployment
  let target value = Deployment_request.target value.deployment
  let acceptance value = value.acceptance
end

type kind = Build | Behavior | Deployment | Acceptance
type t = Plain of Build_request.t | Behavioral of Behavior_request.t | Deployable of Deployment_request.t | Acceptable of Acceptance_request.t
let validation_scope = "complete-source-wrapper-structure-and-declared-correspondence-v1"
let of_json value =
  M.preflight value;
  match named "schema_version" value with
  | "biocompiler.build_request.v0.1" -> Plain (Build_request.of_json value)
  | "biocompiler.human_behavior_request.v0.1" -> Behavioral (Behavior_request.of_json value)
  | "biocompiler.human_deployment_request.v0.1" -> Deployable (Deployment_request.of_json value)
  | "biocompiler.human_acceptance_request.v0.1" -> Acceptable (Acceptance_request.of_json value)
  | _ -> Diagnostic.fail "unsupported_schema" "Unsupported complete source request schema."
let to_json = function Plain value -> Build_request.to_json value | Behavioral value -> Behavior_request.to_json value
  | Deployable value -> Deployment_request.to_json value | Acceptable value -> Acceptance_request.to_json value
let fingerprint = function Plain value -> Build_request.fingerprint value | Behavioral value -> Behavior_request.fingerprint value
  | Deployable value -> Deployment_request.fingerprint value | Acceptable value -> Acceptance_request.fingerprint value
let artifact_fingerprint value = Canonical.fingerprint (to_json value)
let kind = function Plain _ -> Build | Behavioral _ -> Behavior | Deployable _ -> Deployment | Acceptable _ -> Acceptance
let build_request = function Plain value -> value | Behavioral value -> Behavior_request.build_request value
  | Deployable value -> Deployment_request.build_request value | Acceptable value -> Acceptance_request.build_request value
let deployment = function
  | Deployable value -> Some (Deployment_request.deployment value)
  | Acceptable value -> Some (Deployment_request.deployment (Acceptance_request.deployment_request value))
  | Plain _ | Behavioral _ -> None
let target value = match Build_request.target (build_request value) with None -> None | Some value -> Some (Build_request.Target.of_json value)
let unimplemented_obligations value =
  Build_request.unimplemented_obligations (build_request value)
  @ (match kind value with Build -> [] | Behavior | Deployment | Acceptance -> ["human_behavior_observation_assessment"; "human_mechanism_implementation"])
  @ (match kind value with Build | Behavior -> [] | Deployment | Acceptance -> ["human_deployment_compatibility"; "human_delivery_implementation"])
  @ (match kind value with Acceptance -> ["human_acceptance_prohibitions"; "human_input_availability_implementation"; "human_shutdown_actuator"] | _ -> [])
let unresolved_evidence value =
  let paths prefix claims = List.map (fun (path, _) -> prefix ^ path) claims in
  let behavior value = paths "behavior.contract." (H.Conditional_secretion.claims (Behavior_request.contract value)) in
  let deployment value = behavior (Deployment_request.behavior_request value) @ paths "deployment." (H.Deployment.claims (Deployment_request.deployment value)) in
  match value with Plain _ -> [] | Behavioral value -> behavior value | Deployable value -> deployment value
  | Acceptable value -> deployment (Acceptance_request.deployment_request value) @ paths "acceptance." (H.Acceptance.claims (Acceptance_request.acceptance value))

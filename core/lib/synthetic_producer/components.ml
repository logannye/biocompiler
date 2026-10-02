open Bioc_wire
open Bioc_domain
module B = Bioc_realization_checker.Realization_budget
module W = Bioc_checker.Work_budget
module Check = Bioc_realization_checker.Synthetic_candidate_check
module S = Synthetic_authority
module M = Mechanism
module V = Component_contract.Value_domain
module O = Measurement_contract.Observable
module D = Realization_contract.Input_domain
module Dict = Map.Make (String)
let adapter_version = "biocompiler.synthetic_components.v0.2"
type t = { registry_value : Component_registry.t; composition_value : Composition.t;
  acceptance_value : Realization_evidence.Check_result.t }
let registry value = value.registry_value
let composition value = value.composition_value
let acceptance value = value.acceptance_value
let to_json value = Json.Object ["registry",Component_registry.to_json value.registry_value;
  "composition",Composition.to_json value.composition_value;
  "acceptance",Realization_evidence.Check_result.to_json value.acceptance_value]
type limits = { common : B.limits; check : Check.limits }
let make_limits ?max_work ?max_monitor_items ?max_request_bytes ?max_report_bytes ?max_report_nodes () =
  {common=B.make_limits ?max_work ?max_monitor_items ?max_request_bytes ?max_report_bytes ?max_report_nodes ();
   check=Check.make_limits ?max_work ?max_monitor_items ?max_request_bytes ?max_report_bytes ?max_report_nodes ()}
let default_limits = make_limits ()
let limits_json limits = Json.Object ["profile",Json.String "biocompiler.synthetic_component_adapter.resources.v1";
  "shared",B.limits_json limits.common;"acceptance",Check.limits_json limits.check;
  "allocation",Json.String "cumulative_ASCII_fragments_and_typed_constructors_share_work"]
type usage = { work_charged : int; request_bytes : int; report_bytes : int; retained_peak : int }
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let field key value = Json.field key (Json.object_fields value)
let rec levels count = if count <= 1 then 1 else 1 + levels (count / 2)
let charge_product budget a b =
  if a > 0 && b > B.remaining budget / a then B.charge budget (B.remaining budget + 1);
  B.charge budget (a * b)
let key_work budget key = charge_product budget (String.length key + 1) (2 + levels Limits.max_json_nodes)
let put budget key value dictionary =
  key_work budget key; B.retain_monitor budget 1; Dict.add key value dictionary
let find budget key dictionary =
  key_work budget key;
  match Dict.find_opt key dictionary with Some value -> value | None ->
    Diagnostic.fail "synthetic_component_adapter" "Accepted candidate contains an unresolved component declaration."
let map budget f values =
  let values = B.bounded_list budget values in
  B.retain_monitor budget (List.length values); List.map f values
let strings budget values = arr (map budget str values)
let reserve budget raw =
  B.reserve_report budget raw;
  let size = Legacy_ascii.measure raw in
  charge_product budget (size.bytes + size.nodes + 1) (1 + levels size.nodes);
  raw
let decode budget decoder raw = decoder (reserve budget raw)
let sorted_names budget values =
  let values = B.bounded_list budget values in
  B.retain_monitor budget (List.length values);
  let bytes = List.fold_left (fun count value -> count + String.length value + 1) 0 values in
  charge_product budget (bytes + 1) (1 + levels (List.length values));
  List.sort_uniq String.compare values
let pair_key budget a b =
  B.charge budget (String.length a + String.length b + 24);
  string_of_int (String.length a) ^ ":" ^ a ^ b
let pin budget kind id version fingerprint =
  decode budget (fun raw -> Pinned_identity.of_json raw)
    (obj ["schema_version",str Pinned_identity.schema_version;"kind",str kind;
      "id",str id;"version",str version;"content_fingerprint",str fingerprint])
let interval_json dtype unit lower upper =
  obj ["schema_version",str V.schema_version;"kind",str "scalar_interval";
    "dtype",Type_spec.to_json dtype;"unit",str unit;"values",arr [];
    "lower",lower;"upper",upper;"reason",Json.Null]
let input_domain budget input =
  let observable = D.observable input in
  let raw = match D.allowed input with
    | D.Booleans values -> obj ["schema_version",str V.schema_version;"kind",str "boolean";
        "dtype",Type_spec.to_json (Type_spec.of_json (obj ["kind",str "condition";"name",str "Condition"]));"unit",str "1";
        "values",arr (map budget (fun value -> Json.Bool value) values);
        "lower",Json.Null;"upper",Json.Null;"reason",Json.Null]
    | D.Range range -> interval_json (O.dtype observable)
        (Component_contract.canonical_synthetic_unit (O.dtype observable))
        (Runtime_number.to_json (Measurement_contract.Interval.lower range))
        (Runtime_number.to_json (Measurement_contract.Interval.upper range)) in
  decode budget (fun raw -> V.of_json raw) raw
type slot = { node : M.Node.t; attributes : Json.t; mutable runtime : V.t option;
  mutable initial : V.t option; mutable event : bool }
let required_domain_value = function Some value -> value | None ->
  Diagnostic.fail "synthetic_component_adapter" "Accepted mechanism has an unresolved topological domain."
let source_json (source : Behavior.source_location) = obj ["file",str source.file;
  "line",Json.Int source.line;"function",str source.function_name]
let adapt_with_usage ?until ?(limits=default_limits) ?parent request candidate history =
  let budget = B.create ~limits:limits.common ?parent () in
  let work = B.work budget in
  let initial_work = W.remaining work in
  B.reserve_request budget (obj ["request",Json.Null;"candidate",Json.Null;"history",arr [];
    "until",(match until with None -> Json.Null | Some value -> Runtime_number.to_json value)]);
  B.reserve_request budget (Realization_request.to_json request);
  B.reserve_request budget (S.Candidate.to_json candidate);
  let history = B.bounded_list budget history in
  List.iter (fun frame -> B.reserve_request budget (Execution_data.Input_frame.to_json frame)) history;
  let profile = S.Config.profile_version (S.Candidate.generator_config candidate) in
  let catalog = S.catalog_for_profile profile in
  let acceptance_value = Check.check ?until ~limits:limits.check ~parent:work request candidate history in
  Diagnostic.require (Realization_evidence.Check_result.outcome acceptance_value = Realization_evidence.Pass)
    "synthetic_component_acceptance"
    "Component adaptation requires passing synthetic acceptance for the current request, candidate and history.";
  (* Only the fresh call above permits contextual source/target access. No saved
     CheckResult can be supplied in place of that call. *)
  let target = match Realization_request.target request with Some value -> value | None ->
    Diagnostic.fail "synthetic_component_adapter" "Accepted request has no target." in
  let mechanism = S.Candidate.mechanism candidate in
  B.charge budget (M.canonical_size mechanism + Realization_request.canonical_size request);
  let nodes = M.nodes mechanism in
  let count = List.length nodes in
  B.retain_monitor budget (5 * count);
  let slots = Array.of_list (List.map (fun node ->
      {node;attributes=field "attributes" (M.Node.to_json node);runtime=None;initial=None;event=false}) nodes) in
  let positions = ref Dict.empty in
  Array.iteri (fun index slot -> positions := put budget (M.Node.id slot.node) index !positions) slots;
  let locate id = find budget id !positions in
  let authored = List.fold_left (fun values input ->
      put budget (pair_key budget (D.signal_id input) (D.field_name input)) (input_domain budget input) values)
      Dict.empty (Realization_contract.Operating_domain.inputs (Realization_request.domain request)) in
  let inputs = List.fold_left (fun values binding ->
      let key = pair_key budget (Observation_map.Input_binding.signal_id binding)
          (Observation_map.Input_binding.field_name binding) in
      put budget (Observation_map.Input_binding.mechanism_input_id binding) (find budget key authored) values)
      Dict.empty (Observation_map.inputs (S.Candidate.observation_map candidate)) in
  let max_contacts = match Realization_contract.Operating_domain.max_contacts (Realization_request.domain request) with
    | Some value -> value
    | None -> Diagnostic.fail "synthetic_component_adapter" "Accepted request has no finite contact bound." in
  let topological = map budget (fun node -> locate (M.Node.id node)) (M.topological_nodes mechanism) in
  let infer initialization =
    List.iter (fun index ->
      B.charge budget 1;
      let slot = slots.(index) in
      let value = match M.Node.operation slot.node with
        | M.Input -> find budget (M.Node.id slot.node) inputs
        | _ ->
            let arguments = map budget (fun id ->
                let input = slots.(locate id) in
                required_domain_value (if initialization then input.initial else input.runtime))
                (M.Node.inputs slot.node) in
            ignore (reserve budget (obj ["operation",str (M.Node.kind slot.node);"attributes",slot.attributes;
              "dtype",Type_spec.to_json (M.Node.dtype slot.node);"inputs",arr (map budget V.to_json arguments)]));
            (* The any-contact abstraction tests zero only. The full original
               integer remains in the domain constructed after both passes. *)
            let bound = Runtime_number.of_int (if Z.equal max_contacts Z.zero then 0 else 1) in
            let operation = Component_contract.synthetic_operation_of_string (M.Node.kind slot.node) in
            (match Component_contract.synthetic_output_domain ~operation ~attributes:slot.attributes
                ~inputs:arguments ~dtype:(M.Node.dtype slot.node) ~initialization ~max_contacts:bound () with
             | Some value -> value
             | None -> Diagnostic.fail "synthetic_component_adapter" "An executable operator has no output domain.") in
      ignore (reserve budget (V.to_json value));
      if initialization then slot.initial <- Some value else slot.runtime <- Some value) topological in
  infer false; infer true;
  List.iter (fun index ->
      B.charge budget 1;
      let slot = slots.(index) in
      slot.event <- match M.Node.operation slot.node,M.Node.inputs slot.node with
        | M.Onset,_ -> true
        | M.Any_contact,[id] -> slots.(locate id).event
        | _ -> false) topological;
  let coordinates = map budget (fun input ->
      let key = pair_key budget (D.signal_id input) (D.field_name input) in
      B.charge budget (String.length (D.signal_id input) + String.length (D.field_name input) + 14);
      "observation:" ^ D.signal_id input ^ ":" ^ D.field_name input, V.to_json (find budget key authored))
      (Realization_contract.Operating_domain.inputs (Realization_request.domain request)) in
  let level_type = Type_spec.of_json (obj ["kind",str "scalar";"name",str "Level";
    "dimensions",obj [];"arguments",arr []]) in
  let contacts = decode budget (fun raw -> V.of_json raw)
      (interval_json level_type "1" (Json.int 0) (Json.Int max_contacts)) in
  let required = decode budget (fun raw -> Component_contract.Operating_domain.of_json raw)
      (obj ["schema_version",str Component_contract.Operating_domain.schema_version;
        "constraints",obj (("concurrent_contacts",V.to_json contacts)::coordinates)]) in
  let required_raw = Component_contract.Operating_domain.to_json required in
  let source_pin = pin budget "source" "realization_request" Realization_request.schema_version
      (Realization_request.fingerprint request) in
  let common_pins = [source_pin;
    pin budget "model" "synthetic.program" S.model_runner_version (M.fingerprint mechanism);
    pin budget "registry" "synthetic.catalog" (S.Catalog.version catalog) (S.Catalog.fingerprint catalog)] in
  let port ref_id id direction =
    let slot = slots.(locate ref_id) in
    let observable = M.Node.output slot.node in
    let runtime = required_domain_value slot.runtime and initial = required_domain_value slot.initial in
    let timing = if profile = S.combinational_profile then "atomic_snapshot_stateless.v0.1"
      else if slot.event then "atomic_discrete_event_event.v0.1" else "atomic_discrete_event_level.v0.1" in
    decode budget (fun raw ->
      (* Python's Boolean domain constructor fixes the Condition name. A
         compatible named observable can pass synthetic acceptance yet fail
         this exact interface check; compatibility does not replace equality. *)
      List.iter (fun (key,value) ->
        Diagnostic.require
          (Json.equal (Type_spec.to_json (V.dtype value)) (Type_spec.to_json (O.dtype observable))
           && V.unit value = V.unit runtime)
          "component_contract" ("Port " ^ key ^ " type/unit disagrees with its interface."))
        ["initialization",initial; "domain",runtime];
      Component_contract.Port.of_json raw)
      (obj ["schema_version",str Component_contract.Port.schema_version;"id",str id;
        "direction",str direction;"meaning",str (O.id observable);"dtype",Type_spec.to_json (O.dtype observable);
        "unit",str (V.unit runtime);"role",str (O.role observable);
        "scope",str (match O.scope observable with O.Cell -> "cell" | O.Contact -> "contact");
        "compartment",str (O.compartment observable);"timing",str timing;
        "initialization",V.to_json initial;"domain",V.to_json runtime]) in
  let parameter id value method_name =
    decode budget (fun raw -> Component.Parameter.of_json raw)
      (obj ["schema_version",str Component.Parameter.schema_version;"id",str id;
        "value",V.to_json value;"source",Pinned_identity.to_json source_pin;"method",str method_name]) in
  B.retain_monitor budget count;
  let records = map budget (fun slot ->
      let node = slot.node in
      let operator = match S.Catalog.for_operation catalog (M.Node.kind node) with
        | Some value -> value
        | None -> Diagnostic.fail "synthetic_catalog_operation" "Accepted operation is absent from its catalog." in
      let parameters = match M.Node.operation node with
        | M.Constant _ -> [parameter "value" (required_domain_value slot.runtime)
            (if String.starts_with ~prefix:"expression:" (M.Node.id node) then "authored_bound_literal"
             else "contract_band_lower_endpoint_witness")]
        | M.Held_for duration | M.Pulse duration | M.Memory (Some duration) ->
            let duration = Measurement_contract.Scalar.canonical duration in
            let value = decode budget (fun raw -> V.of_json raw)
                (interval_json Measurement_contract.duration_type "s"
                  (Runtime_number.to_json duration) (Runtime_number.to_json duration)) in
            [parameter "duration" value "authored_bound_duration"]
        | _ -> [] in
      let input_ids = map budget Fun.id (M.Node.inputs node) in
      B.retain_monitor budget (2 * List.length input_ids + 1);
      let indexed = List.mapi (fun index id -> id,"in:" ^ string_of_int index) input_ids in
      let ports = port (M.Node.id node) "out" "output" ::
        List.map (fun (id,name) -> port id name "input") indexed in
      let model = decode budget (fun raw -> Component.Synthetic_operator.of_json raw)
        (obj ["schema_version",str Component.Synthetic_operator.schema_version;"operation",str (M.Node.kind node);
          "attributes",slot.attributes;"input_ports",strings budget (map budget snd indexed);
          "output_port",str "out";"policy",str Component.Synthetic_operator.transition_policy]) in
      let identity = pin budget "source" (S.Component.id operator) (S.Component.version operator)
          (S.Component.fingerprint operator) in
      let assumptions = S.Component.assumptions operator @ ["Adapter policy: " ^ adapter_version;
        "No biological resource demand or capacity is declared by this software profile."] in
      B.charge budget (String.length (M.Node.id node) + 20);
      decode budget (fun raw -> Component.of_json raw)
        (obj ["schema_version",str Component.schema_version;"id",str ("synthetic.instance:" ^ M.Node.id node);
          "version",str "1";"classification",str "synthetic_model";"implementation_role",str (M.Node.kind node);
          "supported_targets",strings budget [Build_request.Target.payload_format target];
          "ports",arr (map budget Component_contract.Port.to_json ports);"supported_domain",required_raw;
          "identities",arr (map budget Pinned_identity.to_json (common_pins @ [identity]));
          "assumptions",strings budget assumptions;"guarantees",strings budget (S.Component.guarantees operator);
          "evidence",arr [];"parameters",arr (map budget Component.Parameter.to_json parameters);
          "dependencies",arr [];"capabilities",arr [];"resources",arr [];
          "reference_metadata",Json.Null;"synthetic_model",Component.Synthetic_operator.to_json model]))
      (Array.to_list slots) in
  let registry_value = decode budget (fun raw -> Component_registry.of_json raw)
      (obj ["schema_version",str Component_registry.schema_version;
        "id",str ("synthetic.components:" ^ S.Candidate.fingerprint candidate);"version",str adapter_version;
        "components",arr (map budget Component.to_json records)]) in
  (* Pre-reserve the complete uncollapsed dependency inventory that the domain
     lock constructor traverses, including repeated parameter-source pins. *)
  B.retain_monitor budget count;
  let selections = List.map2 (fun node component -> M.Node.id node,component) nodes records in
  let pins = ref [] in
  let prospective = map budget (fun (node_id,component) ->
      List.iter (fun identity -> B.retain_monitor budget 1;
        let raw = reserve budget (Pinned_identity.to_json identity) in pins := raw :: !pins)
        (Component.identities component @ Component.evidence component @
          List.map Component.Parameter.source (Component.parameters component));
      reserve budget (obj ["schema_version",str Component_registry.Component_lock.schema_version;
        "node_id",str node_id;"component_id",str (Component.id component);"version",str (Component.version component);
        "content_fingerprint",str (Component.fingerprint component)])) selections in
  ignore (reserve budget (obj ["schema_version",str Component_registry.Lock.schema_version;
    "registry_id",str (Component_registry.id registry_value);"registry_version",str adapter_version;
    "registry_fingerprint",str (Component_registry.fingerprint registry_value);
    "components",arr prospective;"identities",arr !pins]));
  let lock = Component_registry.lock registry_value selections in
  let locks = List.fold_left (fun values item ->
      put budget (Component_registry.Component_lock.node_id item) item values) Dict.empty
      (Component_registry.Lock.components lock) in
  let source_nodes = List.fold_left (fun values node ->
      put budget (Identity.Node.to_string (Behavior.node_id node)) (Behavior.source node) values)
      Dict.empty (Behavior.nodes (Realization_request.behavior request)) in
  let lineage = List.fold_left (fun values (key,value) -> put budget key value values) Dict.empty
      (S.Candidate.source_map candidate) in
  let carried = List.fold_left (fun values (key,value) -> put budget key value values) Dict.empty
      (S.Candidate.behavior_requirement_ids candidate) in
  let instances = map budget (fun node ->
      let id = M.Node.id node in
      let rec first_source = function [] -> None | ref_id :: rest ->
        match find budget ref_id source_nodes with Some _ as source -> source | None -> first_source rest in
      let source = first_source (find budget id lineage) in
      let carried_ids = find budget id carried in
      B.retain_monitor budget (List.length (M.Node.requirement_ids node));
      let requirements = sorted_names budget (M.Node.requirement_ids node @ carried_ids) in
      decode budget (fun raw -> Composition.Instance.of_json raw)
        (obj ["id",str id;"component",Component_registry.Component_lock.to_json (find budget id locks);
          "required_domain",required_raw;"placement",str "encoded_here";
          "lifetime",obj ["start",Json.int 0;"end",Json.Null;"unit",str "s"];
          "requirement_ids",strings budget requirements;
          "source",(match source with None -> Json.Null | Some value -> source_json value)])) nodes in
  let connections = ref [] in
  List.iter (fun node -> List.iteri (fun index input ->
      B.retain_monitor budget 1;
      let edge = decode budget (fun raw -> Composition.Connection.of_json raw)
        (obj ["producer_instance",str input;"producer_port",str "out";
          "consumer_instance",str (M.Node.id node);"consumer_port",str ("in:" ^ string_of_int index)]) in
      connections := edge :: !connections) (M.Node.inputs node)) nodes;
  let requirements = sorted_names budget
      (map budget (fun requirement -> Identity.Requirement.to_string (Behavior.requirement_id requirement))
         (Behavior.requirements (Realization_request.behavior request)) @
       map budget Realization_contract.Response.id
         (Realization_contract.Behavior_contract.requirements (Realization_request.contract request))) in
  let composition_value = decode budget (fun raw -> Composition.of_json raw)
      (obj ["schema_version",str Composition.schema_version;"target",Build_request.Target.to_json target;
        "registry_lock",Component_registry.Lock.to_json lock;"instances",arr (map budget Composition.Instance.to_json instances);
        "connections",arr (map budget Composition.Connection.to_json !connections);"providers",arr [];
        "dependency_bindings",arr [];"resource_pools",arr [];"resource_bindings",arr [];
        "requirement_ids",strings budget requirements]) in
  let result = {registry_value;composition_value;acceptance_value} in
  ignore (reserve budget (to_json result));
  let usage = B.usage budget in
  result,{work_charged=initial_work - W.remaining work;request_bytes=usage.request_bytes;
    report_bytes=usage.report_bytes;retained_peak=usage.monitor_peak}
let adapt ?until ?limits ?parent request candidate history =
  fst (adapt_with_usage ?until ?limits ?parent request candidate history)

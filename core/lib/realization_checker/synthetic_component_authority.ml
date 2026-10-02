open Bioc_wire
open Bioc_domain
module B = Realization_budget
module S = Synthetic_authority
module A = S.Candidate
module M = Mechanism
module V = Component_contract.Value_domain
module O = Measurement_contract.Observable
module D = Realization_contract.Input_domain
module By_name = Map.Make (String)
module Names = Set.Make (String)
type 'a index = { entries : 'a By_name.t; count : int }
let empty = { entries = By_name.empty; count = 0 }
let adapter_version = "biocompiler.synthetic_components.v0.2"
type t = { registry : Component_registry.t; composition : Composition.t }
let registry value = value.registry
let composition value = value.composition
let str value = Json.String value
let arr value = Json.Array value
let obj value = Json.Object value
let field key raw = Json.field key (Json.object_fields raw)
let strings values = arr (List.map str values)
let rec levels value = if value <= 1 then 1 else 1 + levels (value / 2)
let product budget values =
  let amount = List.fold_left (fun total factor ->
    let remaining = B.remaining budget in
    if factor > 0 && total > remaining / factor then B.charge budget (remaining + 1);
    total * factor) 1 values in
  B.charge budget amount
let lookup budget key values =
  product budget [String.length key + 1; 2; 1 + levels values.count];
  match By_name.find_opt key values.entries with Some value -> value | None ->
    Diagnostic.fail "synthetic_component_authority" "Fresh synthetic authority contains an unresolved declaration."
let insert budget key value values =
  product budget [String.length key + 1; 2; 1 + levels (values.count + 1)];
  B.retain_monitor budget 1;
  let count = if By_name.mem key values.entries then values.count else values.count + 1 in
  {entries = By_name.add key value values.entries; count}
let sorted_names budget values =
  let values = B.bounded_list budget values in
  let bytes = List.fold_left (fun total value -> total + String.length value + 1) 0 values in
  product budget [bytes + 1; 1 + levels (List.length values)];
  List.sort_uniq String.compare values
(* Every derived fragment is reserved cumulatively before typed construction.
   Its full size also reserves sorting/normalization work. This is a conservative
   private allocation profile, not a change to artifact identity or authority. *)
let checked budget decode raw =
  B.reserve_report budget raw;
  let bytes,nodes = S.measure raw in
  product budget [bytes + nodes + 1; 1 + levels nodes];
  B.retain_monitor budget 1;
  decode raw
let observation_key budget signal field_name =
  B.charge budget (String.length signal + String.length field_name + 24);
  string_of_int (String.length signal) ^ ":" ^ signal ^ ":" ^ field_name
let domain_json budget value =
  let raw = V.to_json value in B.reserve_report budget raw; raw
let input_domain budget item =
  let observable = D.observable item in
  let value = match D.allowed item with
    | D.Booleans values -> V.boolean ~values ()
    | D.Range range -> V.interval ~lower:(Measurement_contract.Interval.lower range)
        ~upper:(Measurement_contract.Interval.upper range) ~dtype:(O.dtype observable)
        ~unit:(Component_contract.canonical_synthetic_unit (O.dtype observable)) in
  ignore (domain_json budget value); value
let pin budget kind id version content =
  checked budget (fun raw -> Pinned_identity.of_json raw)
    (obj ["schema_version",str Pinned_identity.schema_version;"kind",str kind;"id",str id;
      "version",str version;"content_fingerprint",str content])
let derive ~budget checked_request candidate =
  let request = Checked_request.request checked_request in
  let target = Checked_request.target checked_request in
  let operating = Realization_request.domain request in
  let profile = S.Config.profile_version (A.generator_config candidate) in
  let catalog = S.catalog_for_profile profile in
  let mechanism = A.mechanism candidate in
  let nodes = M.nodes mechanism in
  let count = List.length nodes in
  B.charge budget (M.canonical_size mechanism);
  B.retain_monitor budget count;
  let node_index = List.fold_left (fun values node -> insert budget (M.Node.id node) node values)
      empty nodes in
  let authored = List.fold_left (fun values item ->
      let key = observation_key budget (D.signal_id item) (D.field_name item) in
      insert budget key (input_domain budget item) values) empty
      (Realization_contract.Operating_domain.inputs operating) in
  let inputs = List.fold_left (fun values binding ->
      let key = observation_key budget (Observation_map.Input_binding.signal_id binding)
          (Observation_map.Input_binding.field_name binding) in
      insert budget (Observation_map.Input_binding.mechanism_input_id binding)
        (lookup budget key authored) values) empty (Observation_map.inputs (A.observation_map candidate)) in
  let contact_bound = match Realization_contract.Operating_domain.max_contacts operating with
    | Some value -> value
    | None -> Diagnostic.fail "synthetic_component_authority" "Fresh synthetic authority has no contact bound." in
  (* The current local abstraction asks only whether this integer is zero.
     Preserve its full original value in the required coordinate below; do not
     force a huge integer through binary64 before the original domain check. *)
  let max_contacts = Runtime_number.of_int (if Z.equal contact_bound Z.zero then 0 else 1) in
  let topological = M.topological_nodes mechanism in
  let attributes node = field "attributes" (M.Node.to_json node) in
  let output_domains initialization =
    List.fold_left (fun values node ->
      B.charge budget 1;
      let value = match M.Node.operation node with
        | M.Input -> lookup budget (M.Node.id node) inputs
        | _ ->
            let arguments = List.map (fun key -> lookup budget key values) (M.Node.inputs node) in
            let raw = obj ["operation",str (M.Node.kind node);"attributes",attributes node;
                "inputs",arr (List.map V.to_json arguments);"dtype",Type_spec.to_json (M.Node.dtype node)] in
            B.reserve_report budget raw;
            (* Scalar intervals/Boolean products and string/type normalization
               are charged against actual argument content before inference. *)
            let bytes,items = S.measure raw in product budget [bytes + items + 1; 4];
            let operation = Component_contract.synthetic_operation_of_string (M.Node.kind node) in
            (match Component_contract.synthetic_output_domain ~operation ~attributes:(attributes node)
                ~inputs:arguments ~dtype:(M.Node.dtype node) ~initialization ~max_contacts () with
             | Some value -> value
             | None -> Diagnostic.fail "synthetic_component_authority" "Synthetic output domain could not be reconstructed.") in
      ignore (domain_json budget value);
      insert budget (M.Node.id node) value values) empty topological in
  let runtime = output_domains false in
  let initial = output_domains true in
  let events = List.fold_left (fun values node ->
      product budget [String.length (M.Node.id node) + 1; 1 + levels count];
      let event = match M.Node.operation node,M.Node.inputs node with
        | M.Onset,_ -> true
        | M.Any_contact,[input] ->
            product budget [String.length input + 1; 1 + levels count]; Names.mem input values
        | _ -> false in
      if event then Names.add (M.Node.id node) values else values) Names.empty topological in
  let coordinates = List.map (fun item ->
      let key = observation_key budget (D.signal_id item) (D.field_name item) in
      B.charge budget (String.length (D.signal_id item) + String.length (D.field_name item) + 14);
      "observation:" ^ D.signal_id item ^ ":" ^ D.field_name item, V.to_json (lookup budget key authored))
      (Realization_contract.Operating_domain.inputs operating) in
  let scalar_type = Type_spec.of_json (obj ["kind",str "scalar";"name",str "Level";"dimensions",obj [];"arguments",arr []]) in
  let contacts = checked budget (fun raw -> V.of_json raw) (obj ["schema_version",str V.schema_version;"kind",str "scalar_interval";
    "dtype",Type_spec.to_json scalar_type;"unit",str "1";"values",arr [];"lower",Json.int 0;
    "upper",Json.Int contact_bound;"reason",Json.Null]) in
  let required_raw = obj ["schema_version",str Component_contract.Operating_domain.schema_version;
      "constraints",obj (("concurrent_contacts",V.to_json contacts) :: coordinates)] in
  let required = checked budget (fun raw -> Component_contract.Operating_domain.of_json raw) required_raw in
  let request_pin = pin budget "source" "realization_request" Realization_request.schema_version (Checked_request.fingerprint checked_request) in
  let common_pins = [request_pin;
    pin budget "model" "synthetic.program" S.model_runner_version (M.fingerprint mechanism);
    pin budget "registry" "synthetic.catalog" (S.Catalog.version catalog) (S.Catalog.fingerprint catalog)] in
  let port ref_id id direction =
    let source = lookup budget ref_id node_index in
    let observable = M.Node.output source in
    let runtime_domain = lookup budget ref_id runtime and initial_domain = lookup budget ref_id initial in
    product budget [String.length ref_id + 1; 1 + levels count];
    let timing = if profile = S.combinational_profile then "atomic_snapshot_stateless.v0.1"
      else if Names.mem ref_id events then "atomic_discrete_event_event.v0.1"
      else "atomic_discrete_event_level.v0.1" in
    let raw = obj ["schema_version",str Component_contract.Port.schema_version;"id",str id;"direction",str direction;
      "meaning",str (O.id observable);"dtype",Type_spec.to_json (O.dtype observable);"unit",str (V.unit runtime_domain);
      "role",str (O.role observable);"scope",str (match O.scope observable with O.Cell -> "cell" | O.Contact -> "contact");
      "compartment",str (O.compartment observable);"timing",str timing;
      "initialization",V.to_json initial_domain;"domain",V.to_json runtime_domain] in
    checked budget (fun raw -> Component_contract.Port.of_json raw) raw in
  let records = List.map (fun node ->
      let id = M.Node.id node and operation = M.Node.kind node in
      B.charge budget (String.length operation + S.Catalog.canonical_size catalog);
      let operator = match S.Catalog.for_operation catalog operation with Some value -> value | None ->
        Diagnostic.fail "synthetic_catalog_operation" operation in
      let parameters = match M.Node.operation node with
        | M.Constant _ ->
            let method_name = if String.starts_with ~prefix:"expression:" id then "authored_bound_literal"
              else "contract_band_lower_endpoint_witness" in
            [checked budget (fun raw -> Component.Parameter.of_json raw) (obj ["schema_version",str Component.Parameter.schema_version;
              "id",str "value";"value",V.to_json (lookup budget id runtime);"source",Pinned_identity.to_json request_pin;
              "method",str method_name])]
        | M.Held_for duration | M.Pulse duration | M.Memory (Some duration) ->
            let value = Measurement_contract.Scalar.canonical duration in
            let domain = V.interval ~lower:value ~upper:value ~dtype:Measurement_contract.duration_type ~unit:"s" in
            [checked budget (fun raw -> Component.Parameter.of_json raw) (obj ["schema_version",str Component.Parameter.schema_version;
              "id",str "duration";"value",V.to_json domain;"source",Pinned_identity.to_json request_pin;
              "method",str "authored_bound_duration"])]
        | _ -> [] in
      let inputs = M.Node.inputs node in
      let input_ports = List.mapi (fun index _ -> "in:" ^ string_of_int index) inputs in
      B.retain_monitor budget (List.length inputs);
      let ports = port id "out" "output" :: List.map2 (fun source id -> port source id "input") inputs input_ports in
      let operator_pin = pin budget "source" (S.Component.id operator) (S.Component.version operator) (S.Component.fingerprint operator) in
      let model = checked budget (fun raw -> Component.Synthetic_operator.of_json raw)
        (obj ["schema_version",str Component.Synthetic_operator.schema_version;"operation",str operation;
          "attributes",attributes node;"input_ports",strings input_ports;"output_port",str "out";
          "policy",str Component.Synthetic_operator.transition_policy]) in
      let raw = obj ["schema_version",str Component.schema_version;"id",str ("synthetic.instance:" ^ id);"version",str "1";
        "classification",str "synthetic_model";"implementation_role",str operation;
        "supported_targets",strings [Build_request.Target.payload_format target];"ports",arr (List.map Component_contract.Port.to_json ports);
        "supported_domain",Component_contract.Operating_domain.to_json required;
        "identities",arr (List.map Pinned_identity.to_json (common_pins @ [operator_pin]));
        "assumptions",strings (S.Component.assumptions operator @ ["Adapter policy: " ^ adapter_version;
          "No biological resource demand or capacity is declared by this software profile."]);
        "guarantees",strings (S.Component.guarantees operator);"evidence",arr [];
        "parameters",arr (List.map Component.Parameter.to_json parameters);"dependencies",arr [];"capabilities",arr [];
        "resources",arr [];"reference_metadata",Json.Null;"synthetic_model",Component.Synthetic_operator.to_json model] in
      (* Contextual model validation looks up ordered ports and operating
         coordinates. Charge its possible pairwise comparisons before import. *)
      let maximum_name = List.fold_left (fun maximum port ->
          max maximum (String.length (Component_contract.Port.id port))) 1 ports in
      product budget [List.length ports + 1; List.length ports + List.length coordinates + 2; maximum_name + 1];
      id,checked budget (fun raw -> Component.of_json raw) raw) nodes in
  let registry_raw = obj ["schema_version",str Component_registry.schema_version;
      "id",str ("synthetic.components:" ^ A.fingerprint candidate);"version",str adapter_version;
      "components",arr (List.map (fun (_,record) -> Component.to_json record) records)] in
  let registry = checked budget (fun raw -> Component_registry.of_json raw) registry_raw in
  let selected = List.map (fun (id,record) ->
      checked budget (fun raw -> Component_registry.Component_lock.of_json raw)
        (obj ["schema_version",str Component_registry.Component_lock.schema_version;
          "node_id",str id;"component_id",str (Component.id record);"version",str (Component.version record);
          "content_fingerprint",str (Component.fingerprint record)])) records in
  let identities = List.concat_map (fun (_,record) ->
      let values = Component.identities record @ Component.evidence record @
          List.map Component.Parameter.source (Component.parameters record) in
      List.map (fun value -> let raw = Pinned_identity.to_json value in B.reserve_report budget raw; raw) values) records in
  let lock = checked budget (fun raw -> Component_registry.Lock.of_json raw)
    (obj ["schema_version",str Component_registry.Lock.schema_version;
      "registry_id",str (Component_registry.id registry);"registry_version",str (Component_registry.version registry);
      "registry_fingerprint",str (Component_registry.fingerprint registry);
      "components",arr (List.map Component_registry.Component_lock.to_json selected);"identities",arr identities]) in
  let locks = List.fold_left (fun values lock ->
      insert budget (Component_registry.Component_lock.node_id lock) lock values)
      empty (Component_registry.Lock.components lock) in
  let behavior = Realization_request.behavior request in
  let source_nodes = List.fold_left (fun values node ->
      insert budget (Identity.Node.to_string (Behavior.node_id node)) node values)
      empty (Behavior.nodes behavior) in
  let sources = List.fold_left (fun values (key,items) -> insert budget key items values) empty (A.source_map candidate) in
  let requirements = List.fold_left (fun values (key,items) -> insert budget key items values)
      empty (A.behavior_requirement_ids candidate) in
  let instances = List.map (fun node ->
      let id = M.Node.id node in
      let rec source = function [] -> None | ref_id :: rest ->
        match Behavior.source (lookup budget ref_id source_nodes) with Some value -> Some value | None -> source rest in
      let source = source (lookup budget id sources) in
      let source_json = match source with None -> Json.Null | Some source ->
        obj ["file",str source.Behavior.file;"line",Json.Int source.line;"function",str source.function_name] in
      let raw = obj ["id",str id;"component",Component_registry.Component_lock.to_json (lookup budget id locks);
        "required_domain",Component_contract.Operating_domain.to_json required;"placement",str "encoded_here";
        "lifetime",obj ["start",Json.int 0;"end",Json.Null;"unit",str "s"];
        "requirement_ids",strings (sorted_names budget (M.Node.requirement_ids node @ lookup budget id requirements));"source",source_json] in
      checked budget (fun raw -> Composition.Instance.of_json raw) raw) nodes in
  let connections = List.concat_map (fun node ->
      List.mapi (fun index input ->
        checked budget (fun raw -> Composition.Connection.of_json raw) (obj ["producer_instance",str input;"producer_port",str "out";
          "consumer_instance",str (M.Node.id node);"consumer_port",str ("in:" ^ string_of_int index)]))
        (M.Node.inputs node)) nodes in
  let requirement_ids = sorted_names budget
    (List.map (fun value -> Identity.Requirement.to_string (Behavior.requirement_id value)) (Behavior.requirements behavior) @
     List.map Measurement_contract.Response.id (Realization_contract.Behavior_contract.requirements (Realization_request.contract request))) in
  let raw = obj ["schema_version",str Composition.schema_version;"target",Build_request.Target.to_json target;
    "registry_lock",Component_registry.Lock.to_json lock;"instances",arr (List.map Composition.Instance.to_json instances);
    "connections",arr (List.map Composition.Connection.to_json connections);"providers",arr [];"dependency_bindings",arr [];
    "resource_pools",arr [];"resource_bindings",arr [];"requirement_ids",strings requirement_ids] in
  let composition = checked budget (fun raw -> Composition.of_json raw) raw in
  {registry;composition}

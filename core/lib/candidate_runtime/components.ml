open Bioc_wire
open Bioc_domain
module A = Component_assembly
module C = Component
module R = Component_registry
module P = Component_contract.Port
module E = Composition.Connection
module O = Observation_map
module M = Mechanism
let implementation_version = "biocompiler.ocaml.component_model_reconstruction.v0.1"
let reconstruction_version = "biocompiler.component_model_reconstruction.v0.1"
let resource_profile = "biocompiler.component_model_reconstruction.resources.v1"
let max_preparation_work = 50_000_000
type limits = { preparation_limit : int; execution_limits : Synthetic.limits }
let make_limits ?(max_preparation_work=max_preparation_work)
    ?(execution_limits=Synthetic.default_limits) () =
  Diagnostic.require (max_preparation_work >= 0 && max_preparation_work <= 50_000_000)
    "component_model_limits" "Preparation work can only reduce the fixed component-model limit.";
  {preparation_limit=max_preparation_work; execution_limits}
let default_limits = make_limits ()
let limits_json (limits:limits) = Json.Object ["resource_profile",Json.String resource_profile;
    "max_preparation_work",Json.int limits.preparation_limit;
    "execution",Synthetic.limits_json limits.execution_limits]
type usage = { preparation_work : int; execution : Synthetic.usage }
let require condition message = Diagnostic.require condition "component_model" message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let model record = match C.synthetic_model record with
  | Some value -> value
  | None -> Diagnostic.fail "component_model" "A selected component lacks an executable synthetic model."
let observable port =
  Measurement_contract.Observable.of_json (obj [
      "schema_version",str Measurement_contract.Observable.schema_version;
      "id",str (P.meaning port); "dtype",Type_spec.to_json (P.dtype port);
      "role",str (P.role port); "scope",str (match P.scope port with P.Cell -> "cell" | P.Contact -> "contact");
      "compartment",str (P.compartment port)])
let reconstruct_with_usage ?(limits=default_limits) assembly =
  let work = ref 0 in
  let charge amount =
    Diagnostic.require (amount >= 0 && amount <= limits.preparation_limit - !work)
      "component_model_limit" "Locked component reconstruction exhausted its preparation allowance.";
    work := !work + amount in
  let registry = A.registry assembly and composition = A.composition assembly in
  let declared_instances = Composition.instances composition in
  let rec levels count = if count <= 1 then 1 else 1 + levels (count / 2) in
  (* All containers were bounded before becoming abstract values. Reserve full
     authority and conservative comparison work before registry resolution. *)
  let size = A.canonical_size assembly in
  let population = List.length (R.components registry) + List.length declared_instances
      + List.length (Composition.connections composition) in
  charge (size * levels (population + 1));
  let record_sizes = Hashtbl.create 32 in
  List.iter (fun record ->
      let bytes = String.length (Canonical.encode (C.to_json record)) in
      Hashtbl.add record_sizes (C.id record,C.version record) bytes) (R.components registry);
  let records = R.resolve registry (Composition.registry_lock composition) in
  let sorted_ids values = List.sort String.compare values in
  require (sorted_ids (List.map fst records) = sorted_ids (List.map Composition.Instance.id declared_instances))
    "Assembly instance inventory differs from its lock.";
  let by_id = Hashtbl.create (List.length records) in
  List.iter (fun (id,record) -> Hashtbl.add by_id id record) records;
  let connections = Hashtbl.create 32 in
  List.iter (fun edge ->
      charge 1;
      let producer = E.producer_instance edge and consumer = E.consumer_instance edge in
      let key = consumer,E.consumer_port edge in
      require (not (Hashtbl.mem connections key)) "An executable input has multiple producers.";
      require (Hashtbl.mem by_id producer && Hashtbl.mem by_id consumer)
        "An executable connection names an unknown instance.";
      let producer_model = model (Hashtbl.find by_id producer) in
      let consumer_model = model (Hashtbl.find by_id consumer) in
      require (E.producer_port edge = C.Synthetic_operator.output_port producer_model
          && List.mem (E.consumer_port edge) (C.Synthetic_operator.input_ports consumer_model))
        "A connection disagrees with executable port bindings.";
      Hashtbl.add connections key producer) (Composition.connections composition);
  let responses = Hashtbl.create 16 in
  let observations = A.observation_map assembly in
  List.iter (fun binding ->
      charge 1;
      let id = O.Output_binding.mechanism_output_id binding in
      let current = Option.value (Hashtbl.find_opt responses id) ~default:[] in
      Hashtbl.replace responses id (O.Output_binding.requirement_id binding :: current)) (O.outputs observations);
  let node_bytes = ref 0 in
  let nodes = List.map (fun (identity,record) ->
      charge (Hashtbl.find record_sizes (C.id record,C.version record) + String.length identity + 1);
      let selected = model record in
      require (List.exists (fun pin -> Pinned_identity.kind pin = Pinned_identity.Model
          && Pinned_identity.version pin = Synthetic.runner_version) (C.identities record))
        "Executable components require the current independent runner identity.";
      let ports = C.Synthetic_operator.input_ports selected in
      require (List.for_all (fun port -> Hashtbl.mem connections (identity,port)) ports)
        "An executable input is unconnected.";
      let output = match C.port record (C.Synthetic_operator.output_port selected) with
        | Some output -> output
        | None -> Diagnostic.fail "component_model" "An executable output port is absent from its selected record." in
      let requirements = Option.value (Hashtbl.find_opt responses identity) ~default:[] |> List.rev in
      let node = M.Node.of_json (obj ["id",str identity;
          "kind",str (Component_contract.synthetic_operation_name (C.Synthetic_operator.operation selected));
          "output",Measurement_contract.Observable.to_json (observable output);
          "inputs",arr (List.map (fun port -> str (Hashtbl.find connections (identity,port))) ports);
          "attributes",C.Synthetic_operator.attributes selected;
          "requirement_ids",arr (List.map str requirements)]) in
      let bytes = String.length (Canonical.encode (M.Node.to_json node)) in
      charge bytes;
      Diagnostic.require (bytes <= Limits.max_request_bytes - !node_bytes)
        "component_model_limit" "Expanded component mechanism exceeds its complete record budget.";
      node_bytes := !node_bytes + bytes;
      node) records in
  let input_ids = List.map O.Input_binding.mechanism_input_id (O.inputs observations) in
  let output_ids = List.map O.Output_binding.mechanism_output_id (O.outputs observations) in
  let node_ids kind = List.filter (fun node -> M.Node.kind node = kind) nodes |> List.map M.Node.id |> sorted_ids in
  let complete bindings kind =
    let sorted = sorted_ids bindings in
    List.length sorted = List.length (List.sort_uniq String.compare bindings) && sorted = node_ids kind in
  require (complete input_ids "input") "Assembly observation bindings must cover every executable input exactly once.";
  require (complete output_ids "output") "Assembly observation bindings must cover every executable output exactly once.";
  let result = M.make ~name:"locked_component_assembly" ~nodes ~outputs:output_ids
      ~required_capabilities:["synthetic_signal_graph"] () in
  result,!work
let reconstruct ?limits assembly = fst (reconstruct_with_usage ?limits assembly)
let run_with_usage ?until ?(limits=default_limits) assembly history =
  let mechanism,preparation_work = reconstruct_with_usage ~limits assembly in
  let trace,execution = Synthetic.run_with_usage ?until ~limits:limits.execution_limits mechanism history in
  trace,{preparation_work;execution}
let run ?until ?limits assembly history = fst (run_with_usage ?until ?limits assembly history)

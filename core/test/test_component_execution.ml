open Bioc_wire
open Bioc_domain
module X = Bioc_candidate_runtime.Components
module S = Bioc_candidate_runtime.Synthetic
module A = Component_assembly
module C = Component
module R = Component_registry
module O = Observation_map
module P = Component_contract.Port
module V = Component_contract.Value_domain
module M = Mechanism
module D = Model_execution_data
let require value message = if not value then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let set key value raw = obj ((key,value) :: List.remove_assoc key (Json.object_fields raw))
let rejected ?message code action = match action () with
  | _ -> failwith ("Unexpected component execution success: " ^ code)
  | exception Diagnostic.Error error ->
      require (error.code = code) ("Expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message);
      Option.iter (fun expected -> require (error.message = expected) "Changed component rejection text") message
let boolean = Type_spec.of_json (Json.parse {|{"kind":"condition","name":"Condition"}|})
let target = Build_request.Target.of_json (Json.parse
    {|{"schema_version":"biocompiler.target.v0.1","context_id":"abstract","context_version":"1","payload_format":"RNA","compartments":["abstract"],"resources":{},"capabilities":[]}|})
let port id direction = P.make ~id ~direction ~meaning:"meaning" ~dtype:boolean ~unit:"1"
    ~role:"role" ~scope:P.Cell ~compartment:"abstract" ~timing:P.Stateless
    ~initialization:(V.boolean ()) ~domain:(V.boolean ())
let record ?(version=S.runner_version) ?(attributes=obj []) id operation inputs =
  let selected = C.Synthetic_operator.make ~operation ~attributes ~input_ports:inputs ~output_port:"out" in
  C.make ~id ~version:"1" ~classification:C.Synthetic_model
    ~implementation_role:(Component_contract.synthetic_operation_name operation)
    ~supported_targets:["RNA"] ~ports:(port "out" P.Output :: List.map (fun id -> port id P.Input) inputs)
    ~supported_domain:(Component_contract.Operating_domain.make [])
    ~identities:[Pinned_identity.make ~kind:Pinned_identity.Model ~id:"arbitrary-declared-model-id" ~version
      ~content_fingerprint:(String.make 64 'a')]
    ~assumptions:[] ~guarantees:[] ~evidence:[] ~parameters:[] ~dependencies:[]
    ~capabilities:[] ~resources:[] ~reference_metadata:None ~synthetic_model:(Some selected)
let edge producer consumer port = Composition.Connection.make ~producer_instance:producer ~producer_port:"out"
    ~consumer_instance:consumer ~consumer_port:port
let bindings ?(inputs=["a";"b"]) ?(outputs=["output"]) () = O.make
    ~inputs:(List.map (fun id -> O.Input_binding.make ~signal_id:("source:" ^ id) ~field:O.Value ~mechanism_input_id:id) inputs)
    ~outputs:(List.map (fun id -> O.Output_binding.make ~requirement_id:"response" ~mechanism_output_id:id) outputs)
let assemble records connections observation_map =
  let registry = R.make ~id:"runtime-literal" ~version:"1" ~components:(List.map snd records) in
  let lock = R.lock registry records in
  let instances = List.map (fun component -> Composition.Instance.make ~id:(R.Component_lock.node_id component)
      ~component ~required_domain:(Component_contract.Operating_domain.make []) ()) (R.Lock.components lock) in
  let composition = Composition.make ~target ~registry_lock:lock ~instances ~connections () in
  A.make ~registry ~composition ~request_fingerprint:(String.make 64 'b') ~candidate_fingerprint:(String.make 64 'c')
    ~behavior_sources:(List.map (fun (id,_) -> id,["source"]) records) ~observation_map
let gate ?(version=S.runner_version) operation =
  let records = ["output",record "output-record" Component_contract.Output ["receive"];
      "b",record "b-record" Component_contract.Input [];
      "gate",record ~version "gate-record" operation ["second";"first"];
      "a",record "a-record" Component_contract.Input []] in
  records,[edge "a" "gate" "first";edge "b" "gate" "second";edge "gate" "output" "receive"]
let input time a b = D.Input_frame.make ~time:(Runtime_number.of_int time)
    ~values:["a",D.Boolean a;"b",D.Boolean b] ()
let exact_trace label assembly expected =
  let trace = X.run ~until:(Runtime_number.of_int 3) assembly [input 0 false true;input 1 true true;input 2 true false] in
  let mechanism = X.reconstruct assembly in
  let frames = List.mapi (fun time value -> obj ["time",Json.int time;
      "values",obj ["output",Json.Bool value];"contacts",obj []]) expected in
  let complete = obj ["schema_version",str D.Trace.schema_version;"model_version",str S.runner_version;
      "program_fingerprint",str (M.fingerprint mechanism);"horizon",Json.int 3;"frames",arr frames] in
  require (Canonical.encode (D.Trace.to_json trace) = Canonical.encode complete) (label ^ ": full independent timeline differs")
let () =
  let records,connections = gate Component_contract.And in
  let assembly = assemble records connections (bindings ()) in
  let mechanism,work = X.reconstruct_with_usage assembly in
  require (M.name mechanism = "locked_component_assembly" && M.required_capabilities mechanism = ["synthetic_signal_graph"])
    "Reconstructed profile identity changed";
  require (List.map M.Node.id (M.nodes mechanism) = ["a";"b";"gate";"output"]) "Registry instance order changed";
  require (M.Node.inputs (Option.get (M.get mechanism "gate")) = ["b";"a"])
    "Connection order replaced executable model input order";
  require (M.Node.requirement_ids (Option.get (M.get mechanism "output")) = ["response"])
    "Observation requirement lineage was lost";
  exact_trace "actual AND contents" assembly [false;true;false;false];
  let or_records,or_connections = gate Component_contract.Or in
  exact_trace "coherently relocked OR contents" (assemble or_records or_connections (bindings ())) [true;true;true;true];
  let changed = A.to_json assembly |> set "request_fingerprint" (str (String.make 64 'd')) |> A.of_json in
  require (M.fingerprint (X.reconstruct changed) = M.fingerprint mechanism)
    "Source request supplied candidate operations";
  rejected ~message:"Executable components require the current independent runner identity." "component_model" (fun () ->
      let records,edges = gate ~version:"older" Component_contract.And in X.reconstruct (assemble records edges (bindings ())));
  rejected ~message:"An executable input has multiple producers." "component_model" (fun () ->
      X.reconstruct (assemble records (edge "b" "gate" "first" :: connections) (bindings ())));
  rejected ~message:"An executable connection names an unknown instance." "component_model" (fun () ->
      X.reconstruct (assemble records [edge "absent" "gate" "first"] (bindings ())));
  rejected ~message:"A connection disagrees with executable port bindings." "component_model" (fun () ->
      X.reconstruct (assemble records [edge "a" "gate" "absent"] (bindings ())));
  rejected ~message:"An executable input is unconnected." "component_model" (fun () ->
      X.reconstruct (assemble records [] (bindings ())));
  List.iter (fun ids -> rejected ~message:"Assembly observation bindings must cover every executable input exactly once."
      "component_model" (fun () -> X.reconstruct (assemble records connections (bindings ~inputs:ids ())))) [["a"];["a";"b";"a"]];
  rejected ~message:"Assembly observation bindings must cover every executable output exactly once." "component_model" (fun () ->
      X.reconstruct (assemble records connections (bindings ~outputs:[] ())));
  let duplicate_output = bindings ~outputs:["output";"output"] () in
  rejected "invalid_mechanism" (fun () -> X.reconstruct (assemble records connections duplicate_output));
  require (work > 0) "Preparation work was not recorded";
  let exact = X.make_limits ~max_preparation_work:work () in
  require (M.fingerprint (X.reconstruct ~limits:exact assembly) = M.fingerprint mechanism) "Exact preparation boundary changed";
  rejected "component_model_limit" (fun () -> X.reconstruct ~limits:(X.make_limits ~max_preparation_work:(work-1) ()) assembly);
  rejected "component_model_limits" (fun () -> X.make_limits ~max_preparation_work:(-1) ());
  rejected "component_model_limit" (fun () -> X.run ~limits:(X.make_limits ~max_preparation_work:0 ()) assembly []);
  let _,usage = X.run_with_usage assembly [input 0 false true] in
  require (usage.preparation_work = work && usage.execution.work > 0) "Independent stage usage was conflated";
  let changed_nodes = get "nodes" (M.to_json mechanism) |> Json.array |> List.map (fun value ->
      if Json.string (get "id" value) = "gate" then set "inputs" (arr [str "a";str "b"]) value else value) in
  require (Canonical.encode (arr changed_nodes) <> Canonical.encode (get "nodes" (M.to_json mechanism)))
    "Literal port-order mutant did not alter the complete graph";
  print_endline "locked component execution: actual relocked contents, full timelines, declared port order, authority boundaries, exact contextual failures and separate resource allowances checked"

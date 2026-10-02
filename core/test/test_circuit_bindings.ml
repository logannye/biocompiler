open Bioc_wire
open Bioc_domain
module B = Payload_circuit_binding
module K = Bioc_checker.Circuit_binding_check
module W = Bioc_checker.Work_budget
let require condition message = if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let field key value = Json.field key (Json.object_fields value)
let set key value raw = obj ((key,value) :: List.remove_assoc key (Json.object_fields raw))
let rejected label code run = match run () with _ -> failwith (label ^ ": intended rejection accepted")
  | exception Diagnostic.Error error -> require (error.code = code) (label ^ ": expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message)
(* A complete artificial single-input source and supplementary table. The literal
   expectation is [false,true], not a producer or candidate-derived approval. *)
let fixture = Json.parse {|{"source":{"schema_version":"biocompiler.build_request.v0.1","intent":{"schema_version":"biocompiler.intent.v0.1","name":"binding_fixture","nodes":[{"id":"n000001","kind":"role","inputs":[],"attributes":{"cell_type":"human_T_cell","engineering":"in_vivo","name":"recipient"},"data_type":null,"role":null,"source":{"file":"fixtures/human_wrappers.py","line":11,"function":"artificial_human_source"}},{"id":"n000002","kind":"scope","inputs":["n000001"],"attributes":{"scope":"environment","name":"environment"},"data_type":null,"role":"n000001","source":{"file":"fixtures/human_wrappers.py","line":11,"function":"artificial_human_source"}},{"id":"n000003","kind":"signal","inputs":["n000002"],"attributes":{"observation":"signal","scope":"environment","name":"s0"},"data_type":{"kind":"scalar","name":"Level","dimensions":{},"arguments":[]},"role":"n000001","source":{"file":"fixtures/human_wrappers.py","line":11,"function":"artificial_human_source"}},{"id":"n000004","kind":"qualitative","inputs":["n000003"],"attributes":{"band":"present"},"data_type":{"kind":"condition","name":"Condition","dimensions":{},"arguments":[]},"role":"n000001","source":{"file":"fixtures/human_wrappers.py","line":11,"function":"artificial_human_source"}},{"id":"n000005","kind":"secretion","inputs":["n000001"],"attributes":{"product":"artificial_product","default":true,"activity":"requires_rule_or_controller","name":"artificial_product"},"data_type":null,"role":"n000001","source":{"file":"fixtures/human_wrappers.py","line":11,"function":"artificial_human_source"}},{"id":"n000006","kind":"action.secrete","inputs":["n000005"],"attributes":{"ongoing":true,"rate":"unspecified"},"data_type":null,"role":"n000001","source":{"file":"fixtures/human_wrappers.py","line":11,"function":"artificial_human_source"}},{"id":"n000007","kind":"rule","inputs":["n000001","n000004","n000006"],"attributes":{"trigger":"condition","execution":"concurrent","priority":"unspecified"},"data_type":null,"role":"n000001","source":{"file":"fixtures/human_wrappers.py","line":11,"function":"artificial_human_source"}}],"roots":["n000001","n000005","n000007"]},"explicit_overrides":{},"resolved_defaults":{},"resolved_bindings":{},"target":null,"artifact_scope":"abstract_behavior","behavior_profile":"biocompiler.behavior.v0.1","implementation_constraints":{},"preferences":{},"parameter_metadata":{},"provenance":{"schema_version":"biocompiler.elaboration_provenance.v0.1","source_identities":{},"dependency_identities":{},"external_inputs":{},"locations":{},"recorded_at":null}},"requirement":{"schema_version":"biocompiler.circuit_requirement.v0.1","id":"r","behavior":{"schema_version":"biocompiler.circuit_behavior.v0.1","inputs":[{"schema_version":"biocompiler.circuit_observation.v0.1","id":"i0","entity":{"schema_version":"biocompiler.observation_entity.v0.1","namespace":"software_fixture","accession":"i0","version":"1","isoform":"unknown"},"quantity":"mirna_activity","compartment":"cytoplasm","scope":"cell_accessible","window":{"schema_version":"biocompiler.observation_window.v0.1","reference":"unknown","start":null,"end":null,"unit":"unknown","aggregation":"unknown"},"encoding":{"schema_version":"biocompiler.observation_encoding.v0.1","mode":"qualitative","unit":"qualitative","low":null,"high":null,"allowed_range":null}}],"response":{"schema_version":"biocompiler.boolean_spec.v0.1","inputs":[{"schema_version":"biocompiler.circuit_signal.v0.1","id":"i0","observation_fingerprint":"9948315695eb79d8cf45dcb51275510d8522871de424e8b0bfcdebda849d7122"}],"outputs":[false,true]},"output":{"schema_version":"biocompiler.circuit_product.v0.1","id":"artificial_product","kind":"protein_expression","observation":{"schema_version":"biocompiler.circuit_observation.v0.1","id":"readout","entity":{"schema_version":"biocompiler.observation_entity.v0.1","namespace":"software_fixture","accession":"readout","version":"1","isoform":"unknown"},"quantity":"translation_rate","compartment":"cytoplasm","scope":"evaluator","window":{"schema_version":"biocompiler.observation_window.v0.1","reference":"unknown","start":null,"end":null,"unit":"unknown","aggregation":"unknown"},"encoding":{"schema_version":"biocompiler.observation_encoding.v0.1","mode":"qualitative","unit":"qualitative","low":null,"high":null,"allowed_range":null}}},"lifecycle":{"schema_version":"biocompiler.circuit_lifecycle.v0.1","mode":"production_control","onset":null,"cessation":null,"clearance":null},"dependencies":[]},"role_id":"n000001","source_node_ids":["n000001","n000003","n000006","n000007"],"source_location":{"file":"tools/freeze_circuit_bindings.py","line":62,"function":"authored"},"input_bindings":[{"schema_version":"biocompiler.circuit_input_binding.v0.1","observation_id":"i0","source_node_id":"n000003"}]},"binding":{"schema_version":"biocompiler.payload_circuit_binding.v0.1","requirement_id":"r","rule_id":"n000007","action_id":"n000006","signals":{"i0":"n000003"}}}|}
let literal = Json.parse {|{"schema_version":"biocompiler.payload_circuit_binding.v0.1","requirement_id":"r","rule_id":"rule","action_id":"a","signals":{"z":"same","a":"same"}}|}
let literals () =
  let binding = B.of_json literal in
  require (Json.equal (B.to_json binding) literal && B.signals binding = ["a","same";"z","same"] &&
    B.requirement_id binding = "r" && B.rule_id binding = "rule" && B.action_id binding = "a") "Literal correspondence was interpreted or lost";
  let make signals = B.make ~requirement_id:"r" ~rule_id:"rule" ~action_id:"a" ~signals in
  ignore (make []); ignore (make (List.init 256 (fun index -> string_of_int index,"same")));
  rejected "mapping count" "molecular_resource_limit" (fun () -> make (List.init 257 (fun index -> string_of_int index,"same")));
  let rec spine = ("x","x") :: spine in
  rejected "native map list cycle" "molecular_resource_limit" (fun () -> make spine);
  rejected "duplicate mapping keys" "duplicate_key" (fun () -> make ["x","a";"x","b"]);
  rejected "invalid UTF8" "invalid_utf8" (fun () -> make ["x",String.make 1 (Char.chr 255)]);
  rejected "text byte boundary" "invalid_molecular_text" (fun () -> make ["x",String.make 4097 'x']);
  let cycle = let rec value = Json.Array [value] in value in
  rejected "cyclic raw record" "molecular_cycle" (fun () -> B.of_json (set "signals" cycle literal));
  let rec fields = ("x",Json.Null) :: fields in
  rejected "cyclic raw object spine" "molecular_resource_limit" (fun () -> B.of_json (set "signals" (obj fields) literal));
  let source = Human_request.of_json (field "source" fixture) and requirement = Circuit_request.Requirement.of_json (field "requirement" fixture)
  and binding = B.of_json (field "binding" fixture) in
  require (K.check ~source ~requirements:[requirement] ~bindings:[binding] () = []) "Literal Boolean source correspondence differs";
  let response = Option.get (Circuit_request.Requirement.boolean_response requirement) in
  require (response = (["i0"],[false;true])) "Literal table row convention differs";
  require (Circuit_request.Product.id (Circuit_request.Requirement.product requirement) = "artificial_product" &&
    Circuit_request.Lifecycle.mode (Circuit_request.Requirement.lifecycle requirement) = "production_control") "Typed supplementary getters differ";
  require (K.check ~source ~requirements:[requirement] ~bindings:[] () = ["unsupported:circuit_binding_missing:r"])
    "Missing binding became acceptance";
  let raw_requirement=field "requirement" fixture in
  let raw_behavior=field "behavior" raw_requirement in
  let entity=field "entity" (field "observation" (field "output" raw_behavior)) in
  let providers=List.init 32 (fun index -> obj ["schema_version",str "biocompiler.circuit_provider_requirement.v0.1";
    "id",str ("provider_" ^ string_of_int index);"entity",entity;"kind",str "host";"compartment",str "cytoplasm";
    "colocation_group",str "declared";"availability",str "declared"]) in
  let amplified=List.init 12 (fun index -> raw_requirement
    |> set "id" (str (String.make 12_000 'r' ^ string_of_int index))
    |> set "behavior" (set "dependencies" (Json.Array providers) raw_behavior)
    |> Circuit_request.Requirement.of_json) in
  require (List.length (K.check ~source ~requirements:(List.filteri (fun index _ -> index<8) amplified) ~bindings:[] ())=264)
    "Bounded long-ID provider obligations were lost";
  rejected "provider diagnostic amplification" "circuit_binding_output_limit"
    (fun () -> K.check ~source ~requirements:amplified ~bindings:[] ());
  rejected "duplicate expected requirements" "invalid_circuit_binding_check" (fun () -> K.check ~source ~requirements:[requirement;requirement] ~bindings:[binding] ());
  rejected "duplicate bindings" "invalid_circuit_binding_check" (fun () -> K.check ~source ~requirements:[requirement] ~bindings:[binding;binding] ());
  rejected "unknown requirement" "invalid_circuit_binding_check" (fun () -> K.check ~source ~requirements:[] ~bindings:[binding] ());
  let rec requirements = requirement :: requirements in
  rejected "cyclic context" "molecular_resource_limit" (fun () -> K.check ~source ~requirements ~bindings:[] ());
  let raw_source = field "source" fixture in
  let intent = field "intent" raw_source in
  let count = List.length (Json.array (field "nodes" intent)) in
  let exact = K.make_budget ~max_work:count () in
  require (K.check ~budget:exact ~source ~requirements:[] ~bindings:[] () = []) "Exact source scan work bound failed";
  rejected "one below work boundary" "circuit_binding_resource_limit" (fun () -> K.check ~budget:(K.make_budget ~max_work:(count-1) ()) ~source ~requirements:[] ~bindings:[] ());
  rejected "cumulative local work" "circuit_binding_resource_limit" (fun () -> K.check ~budget:exact ~source ~requirements:[] ~bindings:[] ());
  let parent = W.create ~profile:"literal.architecture.resources.v1" ~error_code:"architecture_resource_limit" ~maximum:count () in
  let one = K.make_budget ~parent () and two = K.make_budget ~parent () in
  ignore (K.check ~budget:one ~source ~requirements:[] ~bindings:[] ());
  rejected "shared parent bound" "architecture_resource_limit" (fun () -> K.check ~budget:two ~source ~requirements:[] ~bindings:[] ());
  (* Repeated shared children double recursive work, but never change Boolean
     meaning. Reverse declarations also prevent an accidental declaration-order
     evaluator from passing. Flat 2,000-node graphs stay below JSON depth limits. *)
  let nodes = Json.array (field "nodes" intent) in
  let rule = List.find (fun value -> field "id" value = str (B.rule_id binding)) nodes in
  let guard = Json.string (List.nth (Json.array (field "inputs" rule)) 1) in
  let initial = List.find (fun value -> field "id" value = str guard) nodes in
  let previous = ref guard in
  let extras = List.init 2000 (fun index ->
    let id = "shared_" ^ string_of_int index in
    let value = initial |> set "id" (str id) |> set "kind" (str "and") |> set "attributes" (obj [])
      |> set "inputs" (Json.Array [str !previous;str !previous]) in previous := id; value) in
  let rule = set "inputs" (Json.Array (List.mapi (fun index value -> if index=1 then str !previous else value)
    (Json.array (field "inputs" rule)))) rule in
  let nodes = List.rev extras @ List.map (fun value -> if field "id" value = str (B.rule_id binding) then rule else value) nodes in
  let source = Human_request.of_json (set "intent" (set "nodes" (Json.Array nodes) intent) raw_source) in
  require (K.check ~source ~requirements:[requirement] ~bindings:[binding] () = []) "Explicit stack or shared DAG memoization changed predicate semantics";
  rejected "bounded DAG work" "circuit_binding_resource_limit" (fun () -> K.check ~budget:(K.make_budget ~max_work:5000 ()) ~source ~requirements:[requirement] ~bindings:[binding] ());
  print_endline "circuit bindings: complete literals, native cycles/UTF8/bounds, exact/shared work budgets and deep repeated DAG passed"
let read_json path =
  require (not (Filename.is_relative path)) "Circuit binding corpus requires an absolute path";
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let length = in_channel_length channel in require (length <= Limits.max_request_bytes) "Circuit binding fixture read budget";
    Json.parse (really_input_string channel length))
let retained path =
  let corpus = read_json path in
  require (field "schema_version" corpus = str "biocompiler.circuit_bindings_conformance.v1") "Wrong binding corpus schema";
  let records = Json.array (field "records" corpus) and failures = Json.array (field "rejections" corpus)
  and checks = Json.array (field "checks" corpus) in
  require (List.length records=5 && List.length failures=31 && List.length checks=53) "Circuit binding exact census drift";
  let inventory = obj (List.map (fun key -> key,field key corpus) ["records";"rejections";"checks";"literal_expectations";"compatibility"]) in
  let expected = "eb5f4d4693cd8c1f1d722a9d56b89d4ea5df9ec0588ac351112b98377a4f3e32" in
  require (Canonical.fingerprint inventory = expected && field "inventory_sha256" corpus = str expected) "Binding full inventory or intended signatures drift";
  List.iter (fun rows -> let ids = List.map (fun item -> Json.string (field "id" item)) rows in
    require (List.length ids = List.length (List.sort_uniq String.compare ids)) "Duplicate binding fixture ID") [records;failures;checks];
  let documents = field "documents" corpus in
  List.iter (fun (digest,raw) -> require (Canonical.fingerprint raw=digest) "Binding retained document pin mismatch") (Json.object_fields documents);
  let doc ref = field (Json.string ref) documents in
  List.iter (fun item -> let value = B.of_json (doc (field "document" item)) in
    require (Json.equal (B.to_json value) (doc (field "normalized" item)) && B.fingerprint value = Json.string (field "fingerprint" item))
      (Json.string (field "id" item) ^ ": full binding identity differs")) records;
  List.iter (fun item -> rejected (Json.string (field "id" item)) (Json.string (field "expected_code" item))
    (fun () -> B.of_json (doc (field "document" item)))) failures;
  List.iter (fun item ->
    let source = Human_request.of_json (doc (field "source" item)) in
    let requirements = Json.array (field "requirements" item) |> List.map (fun ref -> Circuit_request.Requirement.of_json (doc ref))
    and bindings = Json.array (field "bindings" item) |> List.map (fun ref -> B.of_json (doc ref)) in
    require (Human_request.fingerprint source=Json.string (field "source_fingerprint" item) &&
      Human_request.artifact_fingerprint source=Json.string (field "source_artifact_fingerprint" item)) "Full source wrapper authority drift";
    let expected = Json.array (field "expected" item) |> List.map Json.string in
    let actual = K.check ~source ~requirements ~bindings () in
    require (actual=expected) (Json.string (field "id" item) ^ ": expected " ^ String.concat "," expected ^ "; got " ^ String.concat "," actual)) checks;
  Printf.printf "circuit binding corpus: %d full declarations, %d intended import failures, %d ordered correspondence/obligation cases passed\n"
    (List.length records) (List.length failures) (List.length checks)
let () = match Array.to_list Sys.argv with [_] -> literals () | [_;path] -> literals (); retained path
  | _ -> failwith "usage: test_circuit_bindings.exe [<absolute-circuit-bindings-v1.json>]"

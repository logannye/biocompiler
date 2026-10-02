open Bioc_wire
open Bioc_domain
module C = Composition
module R = Component_registry
module O = Component_contract.Operating_domain
module N = Runtime_number
let checks = ref 0
let check condition message = incr checks; if not condition then failwith message
let reject code run =
  incr checks;
  match run () with
  | _ -> failwith ("Composition accepted invalid input: " ^ code)
  | exception Diagnostic.Error error ->
      if error.code <> code then failwith ("Expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message)
let str value = Json.String value
let obj values = Json.Object values
let arr values = Json.Array values
let get key value = Json.field key (Json.object_fields value)
let set key item value = obj ((key, item) :: List.remove_assoc key (Json.object_fields value))
let remove key value = obj (List.remove_assoc key (Json.object_fields value))
let number value = N.of_int value
let lock id component hash = R.Component_lock.make ~node_id:id ~component_id:component ~version:"1"
    ~content_fingerprint:(String.make 64 hash)
let alpha_lock = lock "alpha" "z-component" 'a'
let zeta_lock = lock "zeta" "a-component" 'b'
let registry = R.Lock.make ~registry_id:"fixture-registry" ~registry_version:"1" ~registry_fingerprint:(String.make 64 'c')
    ~components:[alpha_lock; zeta_lock] ~identities:[]
let domain = O.make []
let source : Behavior.source_location = {file = "relative/β.py"; line = Z.of_string "9007199254740993"; function_name = "compose"}
let lifecycle = C.Lifecycle.make ~start:(N.Real (-0.)) ~end_time:(N.Real 1.) ~unit:"min" ()
let alpha = C.Instance.make ~id:"alpha" ~component:alpha_lock ~required_domain:domain ~lifetime:lifecycle
    ~requirement_ids:["é"; "a"] ~source ()
let zeta = C.Instance.make ~id:"zeta" ~component:zeta_lock ~required_domain:domain ~placement:C.Instance.Co_payload ()
let connection = C.Connection.make ~producer_instance:"zeta" ~producer_port:"out" ~consumer_instance:"alpha" ~consumer_port:"in"
let capability id scope compartment = Component.Capability.make ~id ~role:"role" ~scope ~compartment
let provider = C.Provider.make ~id:"supply" ~kind:C.Provider.External
    ~capabilities:[capability "z-cap" Component.Contact "membrane"; capability "a-cap" Component.Cell "cytoplasm"]
    ~supported_targets:["z-target"; "a-target"] ~depends_on:["unresolved-provider"] ~evidence_refs:["citation:z"; "citation:a"] ()
let dependency = C.Dependency_binding.make ~instance_id:"alpha" ~requirement_id:"dependency" ~provider_id:"supply"
let pool = C.Resource_pool.make ~id:"pool" ~resource:"energy" ~unit:"arbitrary-unit" ~capacity:None ~provider_id:"supply" ()
let resource = C.Resource_binding.make ~instance_id:"alpha" ~reservation_id:"reservation" ~pool_id:"pool"
let target_json = Json.parse {|{"capabilities":["sensing","translation"],"compartments":["cytoplasm","membrane"],"context_id":"fixture","context_version":"1","payload_format":"RNA","resources":{"energy":{"canonical_value":-0.0,"kind":"scalar","type":{"arguments":[],"dimensions":{},"kind":"scalar","name":"Level"},"unit":"1","value":-0.0}},"schema_version":"biocompiler.target.v0.1"}|}
let target = Build_request.Target.of_json target_json
let complete () = C.make ~target ~registry_lock:registry ~instances:[alpha; zeta]
    ~connections:[connection; connection] ~providers:[provider] ~dependency_bindings:[dependency]
    ~resource_pools:[pool] ~resource_bindings:[resource] ~requirement_ids:["é"; "z"; "a"] ()
let minimal ?(connections = []) ?(providers = []) ?(dependency_bindings = []) ?(resource_pools = [])
    ?(resource_bindings = []) () =
  C.make ~target ~registry_lock:registry ~instances:[zeta] ~connections ~providers ~dependency_bindings
    ~resource_pools ~resource_bindings ()

let complete_literals () =
  (* Literal fingerprints were independently checked against the eight original
     Python classes; no component resolver, producer or execution is involved. *)
  List.iter (fun (actual, expected) -> check (actual = expected) "Complete literal record identity changed")
    [C.Lifecycle.fingerprint lifecycle, "537b106fc9acc0bd07dcaa8155ec6d92c3a8dc160510f742f2e6a3c686e6b965";
     C.Instance.fingerprint alpha, "6ab5e1658615ef8e51879bf69476340de0a6ec2b48ba895877dc6b760314dd45";
     C.Connection.fingerprint connection, "766b57413d51910013a6aef274e1d1d2532f7b09933adf3f1827658013a0eda1";
     C.Provider.fingerprint provider, "c5960f677ac3b21569b18a16df0dd4f95bb072b0829d1c649aa323c11926aa3d";
     C.Dependency_binding.fingerprint dependency, "4c437b6244e20e854fe22ff9e1d0133417e7f78bb2369494dad04ed7ed83626f";
     C.Resource_pool.fingerprint pool, "974783a7a06a09c19811814dfc5a7f2a3c6335989fe3474a0b391dba6198ba94";
     C.Resource_binding.fingerprint resource, "87e6ebabffc81da7d7881ce95d26c9b6f2f63b30c02ddb421984e2c54a07b307"];
  let request = complete () in
  check (C.fingerprint request = "5ba5f4b7aeffde6b3ce2a88d1d44b129314adb8db2c056bd2d1a388ecbc80400") "Complete composition literal identity changed";
  check (C.canonical_size request = 3119 && C.canonical_size request = String.length (Canonical.encode (C.to_json request)))
    "Cached canonical composition size changed";
  check (Json.equal (C.to_json (C.of_json (C.to_json request))) (C.to_json request)) "Full composition import changed fields";
  check (Json.equal (Build_request.Target.to_json (C.target request)) target_json) "Complete target assumptions disappeared";
  check (R.Lock.fingerprint (C.registry_lock request) = R.Lock.fingerprint registry) "Exact registry lock disappeared";
  check (List.map C.Instance.id (C.instances request) = ["zeta"; "alpha"]) "Instance sorting must use the full record, not its id";
  check (C.requirement_ids request = ["a"; "z"; "é"] && C.Instance.requirement_ids alpha = ["é"; "a"])
    "Request requirement sorting or instance requirement order changed";
  check (List.length (C.connections request) = 2) "Structural import must retain duplicate connections for contextual checking";
  check (C.Instance.placement_name alpha = "encoded_here" && C.Instance.placement zeta = C.Instance.Co_payload)
    "Placement declarations changed";
  check (C.Instance.source alpha = Some source && C.Instance.source zeta = None) "Source location or absent source changed";
  check (C.Lifecycle.start lifecycle = N.Real (-0.) && C.Lifecycle.end_time lifecycle = Some (N.Real 1.)
         && C.Lifecycle.unit lifecycle = "min") "Half-open lifetime declaration changed";
  check (C.Lifecycle.end_time (C.Instance.lifetime zeta) = None) "Unknown release time was invented";
  check (C.Provider.kind provider = C.Provider.External && C.Provider.kind_name provider = "external"
         && C.Provider.depends_on provider = ["unresolved-provider"]
         && C.Provider.evidence_refs provider = ["citation:z"; "citation:a"]
         && C.Provider.supported_targets provider = ["z-target"; "a-target"]
         && List.map Component.Capability.id (C.Provider.capabilities provider) = ["z-cap"; "a-cap"])
    "Provider order or explicit assumptions were silently normalized away";
  check (C.Resource_pool.capacity pool = None && C.Resource_pool.unit pool = "arbitrary-unit")
    "Unknown capacity or explicit unit was converted";
  check (C.Dependency_binding.requirement_id dependency = "dependency" && C.Resource_binding.reservation_id resource = "reservation")
    "Dependency and resource requirements were conflated";
  let moved = C.Instance.make ~id:"alpha" ~component:alpha_lock ~required_domain:domain ~lifetime:lifecycle
      ~requirement_ids:["é"; "a"] ~source:{source with line = Z.succ source.line} () in
  check (C.Instance.fingerprint moved <> C.Instance.fingerprint alpha) "Composition source coordinates are part of complete identity"

let ordering_and_scope () =
  let values = ["unknown", None; "ten", Some (number 10); "floatone", Some (N.Real 1.);
                "floatzero", Some (N.Real 0.); "large", Some (N.Real 1e20); "intone", Some (number 1);
                "intzero", Some N.zero; "negzero", Some (N.Real (-0.))] in
  let pools = List.map (fun (id, capacity) -> C.Resource_pool.make ~id ~capacity ~resource:"fixture"
      ~unit:"1" ~provider_id:"unresolved" ()) values in
  let request = minimal ~resource_pools:pools () in
  check (List.map C.Resource_pool.id (C.resource_pools request) =
         ["negzero"; "intzero"; "floatzero"; "intone"; "floatone"; "ten"; "large"; "unknown"])
    "Spaced JSON numeric sorting key changed";
  check (C.fingerprint (minimal ~resource_pools:(List.rev pools) ()) = C.fingerprint request) "Record input permutation changes normalized identity";
  let connections = List.map (fun id -> C.Connection.make ~producer_instance:"not-selected" ~producer_port:"x,:\\\""
      ~consumer_instance:id ~consumer_port:"in") ["𐀀"; "é"; "a"; "a\n"] in
  let dependencies = List.map (fun id -> C.Dependency_binding.make ~instance_id:id ~requirement_id:"not-declared" ~provider_id:"missing") ["é"; "a"] in
  let resources = List.map (fun id -> C.Resource_binding.make ~instance_id:id ~reservation_id:"not-declared" ~pool_id:"missing") ["é"; "a"] in
  let value = minimal ~connections ~dependency_bindings:dependencies ~resource_bindings:resources () in
  check (List.map C.Connection.consumer_instance (C.connections value) = ["a"; "a\n"; "é"; "𐀀"])
    "Unicode/escaped JSON ordering changed";
  check (List.map C.Dependency_binding.instance_id (C.dependency_bindings value) = ["a"; "é"]
         && List.map C.Resource_binding.instance_id (C.resource_bindings value) = ["a"; "é"])
    "Binding record ordering changed";
  check (List.length (C.connections value) = 4) "Import improperly performed later endpoint/link acceptance";
  let unknown_lock = R.Lock.make ~registry_id:"different" ~registry_version:"1" ~registry_fingerprint:(String.make 64 'd')
      ~components:[] ~identities:[] in
  ignore (C.make ~target ~registry_lock:unknown_lock ~instances:[zeta] ());
  let partial_type = obj ["kind", str "scalar"; "name", str "FixtureScalar"] in
  let changed = C.Resource_pool.to_json pool |> set "dtype" partial_type |> C.Resource_pool.of_json in
  check (Json.equal (get "dtype" (C.Resource_pool.to_json changed))
      (obj ["kind", str "scalar"; "name", str "FixtureScalar"; "dimensions", obj []; "arguments", arr []]))
    "Imported optional type fields were not normalized"

let human_target () =
  let claim = Json.parse {|{"schema_version":"biocompiler.target_claim.v0.1","description":"Artificial declaration","basis":"assumed","evidence_ids":[],"limitations":"Not empirical evidence"}|} in
  let host = obj ["schema_version", str "biocompiler.human_host_dependency.v0.1"; "id", str "host";
      "capability", str "translation"; "compartment", str "cytoplasm"; "support", claim] in
  let condition = obj ["schema_version", str "biocompiler.human_operating_condition.v0.1"; "id", str "condition";
      "observable", str "fixture-observable"; "compartment", str "cytoplasm";
      "domain", Component_contract.Value_domain.to_json (Component_contract.Value_domain.boolean ()); "support", claim] in
  let contract = obj (["schema_version", str "biocompiler.human_target_contract.v0.1"; "recipient_taxon_id", Json.int 9606;
      "engineering", str "in_vivo"; "evidence", arr []; "host_dependencies", arr [host]; "operating_conditions", arr [condition]]
      @ List.map (fun key -> key, claim) ["cell_subtype"; "cell_state"; "tissue_context"; "disease_context"; "population_inclusion"; "population_exclusion"]) in
  let target_json = obj ["schema_version", str "biocompiler.human_target_context.v0.1"; "context_id", str "human-fixture";
      "context_version", str "1"; "payload_format", str "RNA"; "capabilities", arr []; "compartments", arr [str "cytoplasm"];
      "resources", obj []; "human_target", contract] in
  let target = Build_request.Target.of_json target_json in
  check (Build_request.Target.fingerprint target = "711fae5509aea52cdfc92caa446475f59159506e0b40a46a8a25face0b122078")
    "Human target literal does not match independent source identity";
  let request = C.make ~target ~registry_lock:registry ~instances:[zeta] () |> C.to_json |> C.of_json in
  check (Build_request.Target.kind (C.target request) = Build_request.Human_target
         && Json.equal (Build_request.Target.to_json (C.target request)) target_json)
    "Composition import projected away original human declarations"

let rejections () =
  let raw = C.to_json (complete ()) in
  reject "unknown_field" (fun () -> C.of_json (set "hidden" Json.Null raw));
  reject "missing_field" (fun () -> C.of_json (remove "providers" raw));
  reject "unsupported_schema" (fun () -> C.of_json (set "schema_version" (str "future") raw));
  reject "invalid_type" (fun () -> C.of_json (set "connections" Json.Null raw));
  reject "composition_record" (fun () -> C.of_json (set "instances" (arr []) raw));
  reject "composition_record" (fun () -> C.of_json (set "instances" (arr [C.Instance.to_json alpha; C.Instance.to_json alpha]) raw));
  reject "composition_record" (fun () -> C.of_json (set "providers" (arr [C.Provider.to_json provider; C.Provider.to_json provider]) raw));
  reject "composition_record" (fun () -> C.of_json (set "resource_pools" (arr [C.Resource_pool.to_json pool; C.Resource_pool.to_json pool]) raw));
  reject "composition_record" (fun () -> C.of_json (set "providers" (arr [set "id" (str "alpha") (C.Provider.to_json provider)]) raw));
  reject "composition_record" (fun () -> C.of_json (set "requirement_ids" (arr [str "a"]) raw));
  reject "composition_record" (fun () -> C.of_json (set "requirement_ids" (arr [str "a"; str "a"]) raw));
  let instance = C.Instance.to_json alpha in
  reject "composition_record" (fun () -> C.Instance.of_json (set "id" (str "different") instance));
  reject "composition_record" (fun () -> C.Instance.of_json (set "placement" (str "host") instance));
  reject "composition_record" (fun () -> C.Instance.of_json (set "requirement_ids" (arr [str "a"; str "a"]) instance));
  reject "invalid_source" (fun () -> C.Instance.of_json (set "source" (set "line" (Json.int 0) (get "source" instance)) instance));
  reject "invalid_type" (fun () -> C.Instance.of_json (set "source" (set "line" (Json.Bool true) (get "source" instance)) instance));
  reject "unknown_field" (fun () -> C.Instance.of_json (set "source" (set "unknown" Json.Null (get "source" instance)) instance));
  List.iter (fun value -> reject "composition_record" (fun () -> C.Lifecycle.make ~start:value ());
      reject "composition_record" (fun () -> C.Resource_pool.make ~id:"p" ~resource:"r" ~unit:"1" ~provider_id:"s" ~capacity:(Some value) ()))
    [number (-1); N.Real infinity; N.Real nan; N.Integer (Z.pow (Z.of_int 10) 1000)];
  reject "composition_record" (fun () -> C.Lifecycle.make ~start:(number 1) ~end_time:(N.Real 1.) ());
  reject "composition_record" (fun () -> C.Lifecycle.of_json (Json.parse {|{"start":false,"end":null,"unit":"s"}|}));
  reject "composition_record" (fun () -> C.Resource_pool.of_json (set "capacity" (Json.Bool true) (C.Resource_pool.to_json pool)));
  let provider_json = C.Provider.to_json provider in
  List.iter (fun value -> reject "invalid_type" (fun () -> C.Provider.of_json (set "capabilities" value provider_json)))
    [Json.Null; Json.Bool false; obj []; str "wrong"];
  reject "composition_record" (fun () -> C.Provider.of_json (set "kind" (str "payload") provider_json));
  reject "composition_record" (fun () -> C.Provider.of_json (set "supported_targets" (arr []) provider_json));
  reject "composition_record" (fun () -> C.Provider.of_json (set "depends_on" (arr [str "same"; str "same"]) provider_json));
  let cap = List.hd (Json.array (get "capabilities" provider_json)) in
  reject "composition_record" (fun () -> C.Provider.of_json (set "capabilities" (arr [cap; cap]) provider_json));
  let boolean = Type_spec.of_json (Json.parse {|{"kind":"condition","name":"Condition"}|}) in
  reject "composition_record" (fun () -> C.Resource_pool.make ~id:"p" ~resource:"r" ~unit:"1" ~capacity:None ~provider_id:"s" ~dtype:boolean ());
  reject "missing_field" (fun () -> C.Resource_pool.of_json (set "dtype" (obj ["name", str "Level"]) (C.Resource_pool.to_json pool)));
  reject "invalid_name" (fun () -> C.Connection.make ~producer_instance:"a" ~producer_port:"b" ~consumer_instance:"c" ~consumer_port:"\194\160");
  reject "invalid_name" (fun () -> C.Dependency_binding.make ~instance_id:"a" ~requirement_id:"" ~provider_id:"b");
  reject "invalid_name" (fun () -> C.Resource_binding.make ~instance_id:"a" ~reservation_id:"b" ~pool_id:"\n");
  List.iter (fun kind -> ignore (C.Provider.make ~id:"declared" ~kind ~capabilities:[] ~supported_targets:["fixture"] ()))
    [C.Provider.Host; C.Provider.External; C.Provider.Unresolved]

let resources () =
  let rec cycle = Json.Array [cycle] in
  reject "composition_json_cycle" (fun () -> C.of_json cycle);
  let rec spine = Json.Null :: spine in
  reject "composition_resource_limit" (fun () -> C.of_json (arr spine));
  let rec fields = ("x", Json.Null) :: fields in
  reject "composition_resource_limit" (fun () -> C.of_json (obj fields));
  let rec instances = zeta :: instances in
  reject "composition_resource_limit" (fun () -> C.make ~target ~registry_lock:registry ~instances ());
  let rec names = "same" :: names in
  reject "composition_resource_limit" (fun () -> C.Provider.make ~id:"p" ~kind:C.Provider.Host ~capabilities:[] ~supported_targets:names ());
  let cap = capability "c" Component.Cell "cytoplasm" in
  let rec capabilities = cap :: capabilities in
  reject "composition_resource_limit" (fun () -> C.Provider.make ~id:"p" ~kind:C.Provider.Host ~capabilities ~supported_targets:["fixture"] ());
  let deep = List.fold_left (fun value _ -> arr [value]) Json.Null (List.init (Limits.max_depth + 1) Fun.id) in
  reject "composition_resource_limit" (fun () -> C.of_json deep);
  reject "invalid_type" (fun () -> C.of_json (arr (List.init (Limits.max_json_nodes - 1) (fun _ -> Json.Null))));
  reject "composition_resource_limit" (fun () -> C.of_json (arr (List.init Limits.max_json_nodes (fun _ -> Json.Null))));
  reject "composition_resource_limit" (fun () -> C.of_json (Json.Int (Z.pow (Z.of_int 10) Limits.max_number_chars)));
  let large = String.make Limits.max_string_bytes 'x' in
  ignore (C.Lifecycle.make ~unit:large ());
  reject "composition_resource_limit" (fun () -> C.Lifecycle.make ~unit:(large ^ "x") ());
  let connection = C.Connection.make ~producer_instance:large ~producer_port:"out" ~consumer_instance:"target" ~consumer_port:"in" in
  reject "composition_resource_limit" (fun () -> minimal ~connections:[connection; connection; connection; connection] ());
  let empty_shape = obj ["producer_instance", str ""; "producer_port", str ""; "consumer_instance", str ""; "consumer_port", str ""] in
  let overhead = String.length (Canonical.encode empty_shape) in
  let last = String.make (Limits.max_string_bytes - overhead) 'y' in
  let exact = C.Connection.make ~producer_instance:large ~producer_port:large ~consumer_instance:large ~consumer_port:last in
  check (String.length (Canonical.encode (C.Connection.to_json exact)) = Limits.max_request_bytes) "Exact byte boundary was not tested";
  reject "composition_resource_limit" (fun () -> C.Connection.make ~producer_instance:large ~producer_port:large
      ~consumer_instance:large ~consumer_port:(last ^ "y"));
  reject "invalid_utf8" (fun () -> C.Lifecycle.make ~unit:"\255" ());
  reject "duplicate_key" (fun () -> C.of_json (obj ["x", Json.Null; "x", Json.Null]));
  reject "nonfinite_number" (fun () -> C.of_json (obj ["x", Json.Float infinity]));
  check (C.fingerprint (complete ()) = "5ba5f4b7aeffde6b3ce2a88d1d44b129314adb8db2c056bd2d1a388ecbc80400")
    "A failed bounded constructor leaked state into later decoding"

let () =
  if Array.length Sys.argv <> 1 then failwith "test_composition accepts no arguments; complete captured corpus has a separate mandatory reader";
  complete_literals (); ordering_and_scope (); human_target (); rejections (); resources ();
  Printf.printf "Composition: %d complete domain, ordering, context and resource checks passed\n" !checks

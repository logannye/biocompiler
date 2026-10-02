open Bioc_wire
module R = Bioc_domain.Component_registry
module C = Bioc_domain.Component
module P = Bioc_domain.Pinned_identity
let count = ref 0
let check condition message = incr count; if not condition then failwith message
let reject code run =
  incr count;
  match run () with
  | _ -> failwith ("Expected registry rejection " ^ code)
  | exception Diagnostic.Error diagnostic -> if diagnostic.code <> code then
      failwith ("Expected " ^ code ^ ", received " ^ diagnostic.code ^ ": " ^ diagnostic.message)
let str value = Json.String value
let obj value = Json.Object value
let set key replacement value = obj ((key,replacement) :: List.remove_assoc key (Json.object_fields value))
let pin ?(kind=P.Model) ?(hash='a') id = P.make ~kind ~id ~version:"1" ~content_fingerprint:(String.make 64 hash)
let component ?(version="1") ?(identities=[pin "model"]) ?(evidence=[]) ?(parameters=[]) ?(assumptions=[]) id =
  C.make ~id ~version ~classification:C.Synthetic_model ~implementation_role:"historical"
    ~supported_targets:["RNA"] ~ports:[] ~supported_domain:(Bioc_domain.Component_contract.Operating_domain.make [])
    ~identities ~assumptions ~guarantees:[] ~evidence ~parameters ~dependencies:[] ~capabilities:[] ~resources:[]
    ~reference_metadata:None ~synthetic_model:None
let literal_tests () =
  let empty = R.make ~id:"empty" ~version:"1" ~components:[] in
  let empty_literal = Json.parse {|{"components":[],"id":"empty","schema_version":"biocompiler.component_registry.v0.2","version":"1"}|} in
  check (Json.equal (R.to_json empty) empty_literal && R.canonical_size empty = 99) "Empty registry literal differs";
  check (R.fingerprint empty = "797f8779d1a0cc8b64f1d97eb3ec8d959e0d402a877435e2ecb13a22b521b8bc") "Independent registry hash differs";
  check (R.resolve empty (R.lock empty []) = []) "An empty selection was invented or forbidden";
  let literal = Json.parse {|{"schema_version":"biocompiler.component_lock.v0.1","node_id":"node","component_id":"component","version":"v","content_fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}|} in
  let selection = R.Component_lock.make ~node_id:"node" ~component_id:"component" ~version:"v" ~content_fingerprint:(String.make 64 'a') in
  check (Json.equal (R.Component_lock.to_json selection) literal) "Complete component-lock literal differs";
  check (R.Component_lock.node_id selection = "node" && R.Component_lock.component_id selection = "component" &&
         R.Component_lock.version selection = "v" && R.Component_lock.content_fingerprint selection = String.make 64 'a') "Component-lock getters differ";
  let model = pin "same" and evidence = pin ~kind:P.Evidence "same" and source = pin ~kind:P.Source "source" in
  let parameter = C.Parameter.make ~id:"parameter" ~value:(Bioc_domain.Component_contract.Value_domain.boolean ())
      ~source ~method_name:"declared" in
  let a = component ~identities:[model] ~evidence:[evidence] ~parameters:[parameter] "a" in
  let z = component "z" in
  let registry = R.make ~id:"registry" ~version:"2" ~components:[z;a] in
  check (List.map C.id (R.components registry) = ["a";"z"]) "Registry component sorting changed";
  check (R.id registry = "registry" && R.version registry = "2") "Registry ID/version getters differ";
  check (R.fingerprint registry = R.fingerprint (R.make ~id:"registry" ~version:"2" ~components:[a;z])) "Registry input order changed identity";
  let locked = R.lock registry ["β",z;"a",a;"again",a] in
  check (List.map R.Component_lock.node_id (R.Lock.components locked) = ["a";"again";"β"]) "Lock instance order changed";
  check (List.map (fun item -> P.kind_name item,P.id item) (R.Lock.identities locked) =
         ["evidence","same";"model","model";"model","same";"source","source"]) "Complete dependency inventory was not sorted/deduplicated";
  check (List.map fst (R.resolve registry locked) = ["a";"again";"β"]) "Resolved instance order changed";
  check (Json.equal (R.to_json (R.of_json (R.to_json registry))) (R.to_json registry)) "Registry normalized roundtrip differs";
  check (R.Lock.fingerprint locked = R.Lock.fingerprint (R.Lock.of_json (R.Lock.to_json locked)) &&
         R.Lock.canonical_size locked = String.length (Canonical.encode (R.Lock.to_json locked))) "Lock roundtrip/cached size differs";
  let reordered = R.Lock.make ~registry_id:"registry" ~registry_version:"2" ~registry_fingerprint:(R.fingerprint registry)
      ~components:(List.rev (R.Lock.components locked)) ~identities:(model :: List.rev (R.Lock.identities locked)) in
  check (Json.equal (R.Lock.to_json reordered) (R.Lock.to_json locked)) "Same dependency repetitions were incorrectly rejected";
  let missing = R.Lock.make ~registry_id:"registry" ~registry_version:"2" ~registry_fingerprint:(R.fingerprint registry)
      ~components:(R.Lock.components locked) ~identities:[model] in
  reject "component_registry" (fun () -> R.resolve registry missing);
  let extra = R.Lock.make ~registry_id:"registry" ~registry_version:"2" ~registry_fingerprint:(R.fingerprint registry)
      ~components:(R.Lock.components locked) ~identities:(pin ~kind:P.Reference "unused" :: R.Lock.identities locked) in
  reject "component_registry" (fun () -> R.resolve registry extra);
  let changed_unselected = R.make ~id:"registry" ~version:"2" ~components:[a;component ~assumptions:["changed"] "z"] in
  reject "component_registry" (fun () -> R.resolve changed_unselected (R.lock registry ["a",a]));
  reject "component_registry" (fun () -> R.lock registry ["a",component ~assumptions:["changed"] "a"]);
  reject "component_registry" (fun () -> R.lock registry ["same",a;"same",z]);
  reject "component_registry" (fun () -> R.make ~id:"duplicates" ~version:"1" ~components:[a;a]);
  let newer = component ~version:"2" "a" in
  ignore (R.make ~id:"versions" ~version:"1" ~components:[newer;a]);
  let conflict = component ~identities:[pin ~hash:'b' "same"] "conflict" in
  reject "component_registry" (fun () -> R.make ~id:"conflict" ~version:"1" ~components:[a;conflict]);
  let bad_parameter = C.Parameter.make ~id:"p" ~value:(Bioc_domain.Component_contract.Value_domain.boolean ())
      ~source:(pin ~kind:P.Evidence ~hash:'b' "same") ~method_name:"declared" in
  reject "component_registry" (fun () -> R.make ~id:"conflict" ~version:"1" ~components:[a;component ~parameters:[bad_parameter] "b"]);
  let stale = R.Component_lock.make ~node_id:"a" ~component_id:"a" ~version:"1" ~content_fingerprint:(String.make 64 '0') in
  let stale_lock = R.Lock.make ~registry_id:"registry" ~registry_version:"2" ~registry_fingerprint:(R.fingerprint registry)
      ~components:[stale] ~identities:[] in
  reject "component_registry" (fun () -> R.resolve registry stale_lock);
  reject "component_registry" (fun () -> R.Lock.make ~registry_id:"registry" ~registry_version:"2" ~registry_fingerprint:(R.fingerprint registry)
      ~components:[selection;selection] ~identities:[]);
  reject "component_registry" (fun () -> R.Lock.make ~registry_id:"registry" ~registry_version:"2" ~registry_fingerprint:(R.fingerprint registry)
      ~components:[] ~identities:[model;pin ~hash:'b' "same"])
let boundary_tests () =
  let raw = R.to_json (R.make ~id:"empty" ~version:"1" ~components:[]) in
  reject "unsupported_schema" (fun () -> R.of_json (set "schema_version" (str "old") raw));
  reject "unknown_field" (fun () -> R.of_json (set "admitted" (Json.Bool true) raw));
  reject "missing_field" (fun () -> R.of_json (obj (List.remove_assoc "components" (Json.object_fields raw))));
  reject "duplicate_key" (fun () -> R.of_json (obj (("id",str "other") :: Json.object_fields raw)));
  reject "invalid_utf8" (fun () -> R.of_json (set "id" (str "\255") raw));
  reject "nonfinite_number" (fun () -> R.of_json (set "components" (Json.Float nan) raw));
  reject "component_registry" (fun () -> R.Component_lock.make ~node_id:"n" ~component_id:"c" ~version:"1" ~content_fingerprint:(String.make 64 'A'));
  let rec cycle = Json.Array [cycle] in
  reject "component_registry_cycle" (fun () -> R.of_json cycle);
  let rec values = Json.Null :: values in
  reject "component_registry_limit" (fun () -> R.of_json (Json.Array values));
  let rec fields = ("same",Json.Null) :: fields in
  reject "component_registry_limit" (fun () -> R.of_json (obj fields));
  let c = component "c" in
  let rec components = c :: components in
  reject "component_registry_limit" (fun () -> R.make ~id:"cycle" ~version:"1" ~components);
  let rec selections = ("n",c) :: selections in
  reject "component_registry_limit" (fun () -> R.lock (R.make ~id:"r" ~version:"1" ~components:[c]) selections);
  let huge = component ~assumptions:[String.make Limits.max_string_bytes 'x'] "large" in
  reject "component_registry_limit" (fun () -> R.make ~id:"aggregate" ~version:"1" ~components:[huge;huge;huge;huge]);
  let long = R.Component_lock.make ~node_id:(String.make Limits.max_string_bytes 'x') ~component_id:"c" ~version:"1" ~content_fingerprint:(String.make 64 'a') in
  reject "component_registry_limit" (fun () -> R.Lock.make ~registry_id:"aggregate" ~registry_version:"1" ~registry_fingerprint:(String.make 64 'a')
      ~components:[long;long;long;long] ~identities:[])
let () = literal_tests (); boundary_tests (); Printf.printf "component registry: %d literal checks passed\n" !count

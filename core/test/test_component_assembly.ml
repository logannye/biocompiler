open Bioc_wire
open Bioc_domain
module A = Component_assembly
module R = Component_registry
module C = Component
module O = Observation_map
let require value message = if not value then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let set key value raw = obj ((key,value) :: List.remove_assoc key (Json.object_fields raw))
let rejected code action = match action () with
  | _ -> failwith ("Unexpected assembly success: " ^ code)
  | exception Diagnostic.Error error -> require (error.code = code)
      ("Expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message)
let record id = C.make ~id ~version:"1" ~classification:C.Synthetic_model
    ~implementation_role:"historical" ~supported_targets:["RNA"] ~ports:[]
    ~supported_domain:(Component_contract.Operating_domain.make [])
    ~identities:[Pinned_identity.make ~kind:Pinned_identity.Model ~id:"model" ~version:"1"
      ~content_fingerprint:(String.make 64 'a')]
    ~assumptions:[] ~guarantees:[] ~evidence:[] ~parameters:[] ~dependencies:[]
    ~capabilities:[] ~resources:[] ~reference_metadata:None ~synthetic_model:None
let target = Build_request.Target.of_json (Json.parse
    {|{"schema_version":"biocompiler.target.v0.1","context_id":"abstract","context_version":"1","payload_format":"RNA","compartments":["abstract"],"resources":{},"capabilities":[]}|})
let () =
  let selected = record "selected" in
  let registry = R.make ~id:"registry" ~version:"1" ~components:[record "unused";selected] in
  let lock = R.lock registry ["instance",selected] in
  let instance = Composition.Instance.make ~id:"instance" ~component:(List.hd (R.Lock.components lock))
      ~required_domain:(Component_contract.Operating_domain.make []) ~requirement_ids:["source"] () in
  let composition = Composition.make ~target ~registry_lock:lock ~instances:[instance]
      ~requirement_ids:["source"] () in
  let observation_map = O.make ~inputs:[] ~outputs:[] in
  let make behavior_sources = A.make ~registry ~composition
      ~request_fingerprint:(String.make 64 'b') ~candidate_fingerprint:(String.make 64 'c')
      ~behavior_sources ~observation_map in
  let assembly = make ["instance",["second";"first"]] in
  let raw = A.to_json assembly in
  require (A.fingerprint (A.of_json raw) = A.fingerprint assembly) "Complete assembly identity changed on import";
  require (A.canonical_size assembly = String.length (Canonical.encode raw)) "Assembly size omitted fields";
  require (A.behavior_sources assembly = ["instance",["second";"first"]]) "Lineage order changed";
  require (Canonical.encode (get "nodes" raw) = {|[{"id":"instance","kind":"component_instance"}]|})
    "Derived component inventory changed";
  require (R.fingerprint (A.registry assembly) = R.fingerprint registry
      && Composition.fingerprint (A.composition assembly) = Composition.fingerprint composition
      && O.fingerprint (A.observation_map assembly) = O.fingerprint observation_map)
    "Assembly discarded supplied authority";
  require (A.request_fingerprint assembly = String.make 64 'b'
      && A.candidate_fingerprint assembly = String.make 64 'c') "Source/candidate pins were conflated";
  rejected "component_assembly" (fun () -> make []);
  rejected "component_assembly" (fun () -> make ["instance",[]]);
  rejected "component_assembly" (fun () -> make ["instance",["same";"same"]]);
  rejected "component_assembly" (fun () -> A.of_json (set "candidate_fingerprint" (str "short") raw));
  List.iter (fun invalid ->
      rejected "component_assembly" (fun () -> A.of_json (set "nodes" invalid raw)))
    [Json.Null; Json.Bool false; str "instance"; obj []; arr []];
  rejected "component_assembly" (fun () -> A.of_json (set "nodes"
      (arr [obj ["id",str "instance";"kind",str "accepted_component"]]) raw));
  rejected "component_registry" (fun () -> A.of_json (set "registry"
      (R.to_json (R.make ~id:"registry" ~version:"1" ~components:[selected])) raw));
  rejected "missing_field" (fun () -> A.of_json (obj (List.remove_assoc "nodes" (Json.object_fields raw))));
  rejected "unsupported_schema" (fun () -> A.of_json (set "schema_version" (str "other") raw));
  rejected "duplicate_key" (fun () -> make ["instance",["source"];"instance",["source"]]);
  let rec cyclic = Json.Object ["next",cyclic] in
  rejected "component_assembly_cycle" (fun () -> A.of_json (set "behavior_sources" cyclic raw));
  let rec cyclic_names = "source" :: cyclic_names in
  rejected "component_assembly_limit" (fun () -> make ["instance",cyclic_names]);
  let large = String.make Limits.max_string_bytes 'x' in
  rejected "component_assembly_limit" (fun () -> make ["instance",List.init 9 (fun _ -> large)]);
  print_endline "component assembly: exact complete authority, lineage and derived inventories, stale locks, duplicate fields and bounded native cycles checked"

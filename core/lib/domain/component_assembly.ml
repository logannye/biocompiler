open Bioc_wire
module R = Component_registry
module C = Composition
module O = Observation_map
let schema_version = "biocompiler.component_assembly.v0.2"
let resource_profile = "biocompiler.component_assembly.resources.v1"
let require ?path condition message = Diagnostic.require ?path condition "component_assembly" message
let limit ?path condition = Diagnostic.require ?path condition "component_assembly_limit"
    "Locked component assembly exceeds its native resource limit."
let preflight ?(path="") value =
  try Measurement_contract.preflight ~path value with
  | Diagnostic.Error error when error.code = "human_record_limit" -> limit ~path false
  | Diagnostic.Error error when error.code = "human_record_cycle" ->
      Diagnostic.fail ~path "component_assembly_cycle" "Cyclic locked component assembly."
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let field path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let hash ~path value =
  let value = Json.string ~path value in
  require ~path (String.length value = 64 && String.for_all
    (function '0'..'9' | 'a'..'f' -> true | _ -> false) value)
    "An assembly must pin its source request and candidate.";
  value
let ids values = List.map C.Instance.id values |> List.sort String.compare
let inventory values = arr (List.map (fun item ->
    obj ["id",str (C.Instance.id item); "kind",str "component_instance"]) values)
type t = { json : Json.t; identity : string; bytes : int; registry : R.t;
           composition : C.t; request : string; candidate : string;
           sources : (string * string list) list; observations : O.t }
let of_json ?(path="") raw =
  preflight ~path raw;
  let fields = Json.object_fields ~path raw in
  Json.exact_fields ~path ["schema_version";"registry";"composition";
    "request_fingerprint";"candidate_fingerprint";"behavior_sources";"observation_map";"nodes"] fields;
  let get key = field path key fields in
  Diagnostic.require ~path (Json.string (get "schema_version") = schema_version)
    "unsupported_schema" "Unsupported component assembly schema.";
  let registry = R.of_json ~path:(path ^ "/registry") (get "registry") in
  let composition = C.of_json ~path:(path ^ "/composition") (get "composition") in
  let observations = O.of_json ~path:(path ^ "/observation_map") (get "observation_map") in
  let request = hash ~path:(path ^ "/request_fingerprint") (get "request_fingerprint") in
  let candidate = hash ~path:(path ^ "/candidate_fingerprint") (get "candidate_fingerprint") in
  let sources = Json.object_fields ~path:(path ^ "/behavior_sources") (get "behavior_sources") in
  let instances = C.instances composition in
  require ~path (List.sort String.compare (List.map fst sources) = ids instances)
    "Every component requires source lineage.";
  let sources = List.map (fun (id,values) ->
      let path = path ^ "/behavior_sources/" ^ id in
      let values = Json.array ~path values |> List.map (Json.name ~path) in
      require ~path (List.length values = List.length (List.sort_uniq String.compare values))
        "Behavior source IDs must be unique.";
      require ~path (values <> []) "Component source lineage cannot be empty.";
      id,values) sources in
  let resolved = R.resolve registry (C.registry_lock composition) in
  require ~path (List.sort String.compare (List.map fst resolved) = ids instances)
    "The assembly lock must cover exactly its instances.";
  let nodes = inventory instances in
  ignore (Json.array ~path:(path ^ "/nodes") (get "nodes"));
  require ~path (Canonical.fingerprint (get "nodes") = Canonical.fingerprint nodes)
    "The component inventory must match the locked composition.";
  let json = obj ["schema_version",str schema_version; "registry",R.to_json registry;
      "composition",C.to_json composition; "request_fingerprint",str request;
      "candidate_fingerprint",str candidate; "observation_map",O.to_json observations;
      "behavior_sources",obj (List.map (fun (id,values) -> id,arr (List.map str values)) sources);
      "nodes",nodes] in
  preflight ~path json;
  let canonical = Canonical.encode json in
  {json; identity=Canonical.sha256 canonical; bytes=String.length canonical;
   registry; composition; request; candidate; sources; observations}

(* Reserve child encodings and every supplied list/string before materializing
   the constructor's JSON. The final preflight accounts for escaping and keys;
   prefix reservations also stop cyclic native list spines. *)
let make ~registry ~composition ~request_fingerprint ~candidate_fingerprint
    ~behavior_sources ~observation_map =
  let bytes = ref 0 and items = ref 0 in
  let reserve amount = limit (amount <= Limits.max_request_bytes - !bytes); bytes := !bytes + amount in
  let item () = limit (!items < Limits.max_json_nodes); incr items in
  let text value =
    limit (String.length value <= Limits.max_string_bytes);
    reserve (String.length value + 2); item (); str value in
  List.iter reserve [R.canonical_size registry; C.canonical_size composition;
                     O.canonical_size observation_map];
  let list encode values =
    let rec walk reverse = function
      | [] -> List.rev reverse
      | value :: rest -> item (); reserve 1; walk (encode value :: reverse) rest in
    reserve 2; walk [] values in
  let sources = list (fun (id,values) ->
      ignore (text id); id,arr (list text values)) behavior_sources in
  let nodes = list (fun instance -> obj ["id",text (C.Instance.id instance);
      "kind",text "component_instance"]) (C.instances composition) in
  of_json (obj ["schema_version",str schema_version; "registry",R.to_json registry;
      "composition",C.to_json composition; "request_fingerprint",text request_fingerprint;
      "candidate_fingerprint",text candidate_fingerprint; "observation_map",O.to_json observation_map;
      "behavior_sources",obj sources; "nodes",arr nodes])
let to_json value = value.json
let fingerprint value = value.identity
let canonical_size value = value.bytes
let registry value = value.registry
let composition value = value.composition
let request_fingerprint value = value.request
let candidate_fingerprint value = value.candidate
let behavior_sources value = value.sources
let observation_map value = value.observations

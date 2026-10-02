open Bioc_wire
module P = Pinned_identity
module Keys = Map.Make (struct type t = string * string * string let compare = Stdlib.compare end)
let resource_profile = "biocompiler.component_registry.resources.v1"
let require ?path condition message = Diagnostic.require ?path condition "component_registry" message
let limit ?path condition = Diagnostic.require ?path condition "component_registry_limit"
    "Component registry exceeds its native resource boundary."
let str value = Json.String value
let field path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let bounded values =
  let rec loop count = function [] -> values | _ :: rest ->
    limit (count < Limits.max_json_nodes); loop (count + 1) rest in
  loop 0 values
let preflight ?(path = "") value =
  try Measurement_contract.preflight ~path value with
  | Diagnostic.Error diagnostic when diagnostic.code = "human_record_limit" -> limit ~path false
  | Diagnostic.Error diagnostic when diagnostic.code = "human_record_cycle" ->
      Diagnostic.fail ~path "component_registry_cycle" "Cyclic component registry record."
(* The full preflight has already bounded depth, list spines, repeated subtrees,
   string escaping and numeric spelling before this finite occurrence census. *)
let weight value =
  preflight value;
  let pending = ref [value] and nodes = ref 0 in
  while !pending <> [] do
    let value = List.hd !pending in pending := List.tl !pending; incr nodes;
    match value with
    | Json.Array values -> List.iter (fun value -> pending := value :: !pending) values
    | Json.Object fields -> List.iter (fun (_,value) -> pending := value :: !pending) fields
    | _ -> ()
  done;
  String.length (Canonical.encode value), !nodes
type budget = { mutable bytes : int; mutable nodes : int }
let budget () = {bytes = 0; nodes = 0}
let reserve budget value =
  let bytes, nodes = weight value in
  limit (bytes <= Limits.max_request_bytes - budget.bytes && nodes <= Limits.max_json_nodes - budget.nodes);
  budget.bytes <- budget.bytes + bytes; budget.nodes <- budget.nodes + nodes; value
let array budget encode values =
  let first = ref true in
  Json.Array (List.map (fun value ->
      if !first then first := false else begin
        limit (budget.bytes < Limits.max_request_bytes); budget.bytes <- budget.bytes + 1
      end;
      reserve budget (encode value)) (bounded values))
let record ~path schema keys value =
  preflight ~path value;
  let fields = Json.object_fields ~path value in
  Json.exact_fields ~path ("schema_version" :: keys) fields;
  Diagnostic.require ~path (Json.string (field path "schema_version" fields) = schema)
    "unsupported_schema" "Unsupported registry schema.";
  fields
let hash ~path value =
  let value = Json.string ~path value in
  require ~path (String.length value = 64 && String.for_all
    (function '0'..'9' | 'a'..'f' -> true | _ -> false) value) "Registry content identity must be a lowercase SHA-256 hash.";
  value
let identity_key value = P.kind_name value, P.id value, P.version value
let identities ~path values =
  let result = List.fold_left (fun result value ->
      let key = identity_key value in
      (match Keys.find_opt key result with None -> () | Some previous ->
          require ~path (P.content_fingerprint previous = P.content_fingerprint value)
            "Ambiguous dependency identity: one kind/ID/version has different hashes.");
      Keys.add key value result) Keys.empty (bounded values) in
  List.map snd (Keys.bindings result)
let each_identity f component =
  List.iter f (Component.identities component); List.iter f (Component.evidence component);
  List.iter (fun parameter -> f (Component.Parameter.source parameter)) (Component.parameters component)

module Component_lock = struct
  type t = { json : Json.t; node_id : string; component_id : string; version : string; content_fingerprint : string }
  let schema_version = "biocompiler.component_lock.v0.1"
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["node_id"; "component_id"; "version"; "content_fingerprint"] value in
    let name key = Json.name ~path:(path ^ "/" ^ key) (field path key fields) in
    let node_id = name "node_id" and component_id = name "component_id" and version = name "version" in
    let content_fingerprint = hash ~path:(path ^ "/content_fingerprint") (field path "content_fingerprint" fields) in
    {json = value; node_id; component_id; version; content_fingerprint}
  let make ~node_id ~component_id ~version ~content_fingerprint = of_json (Json.Object [
      "schema_version",str schema_version; "node_id",str node_id; "component_id",str component_id;
      "version",str version; "content_fingerprint",str content_fingerprint])
  let to_json value = value.json
  let fingerprint value = Canonical.fingerprint value.json
  let node_id value = value.node_id
  let component_id value = value.component_id
  let version value = value.version
  let content_fingerprint value = value.content_fingerprint
end

module Lock = struct
  type t = { json : Json.t; fingerprint : string; size : int; registry_id : string; registry_version : string;
             registry_fingerprint : string; components : Component_lock.t list; identities : P.t list }
  let schema_version = "biocompiler.component_registry_lock.v0.1"
  let encode ~registry_id ~registry_version ~registry_fingerprint ~components ~identities =
    let budget = budget () in
    ignore (reserve budget (Json.Object ["schema_version",str schema_version; "registry_id",str registry_id;
        "registry_version",str registry_version; "registry_fingerprint",str registry_fingerprint;
        "components",Json.Array []; "identities",Json.Array []]));
    let components = array budget Component_lock.to_json components in
    let identities = array budget P.to_json identities in
    Json.Object ["schema_version",str schema_version; "registry_id",str registry_id; "registry_version",str registry_version;
        "registry_fingerprint",str registry_fingerprint; "components",components; "identities",identities]
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["registry_id"; "registry_version"; "registry_fingerprint"; "components"; "identities"] value in
    let get key = field path key fields in
    let registry_id = Json.name ~path:(path ^ "/registry_id") (get "registry_id") in
    let registry_version = Json.name ~path:(path ^ "/registry_version") (get "registry_version") in
    let registry_fingerprint = hash ~path:(path ^ "/registry_fingerprint") (get "registry_fingerprint") in
    let components = Json.array (get "components") |> List.mapi (fun index ->
        Component_lock.of_json ~path:(path ^ "/components/" ^ string_of_int index))
      |> List.sort (fun a b -> String.compare (Component_lock.node_id a) (Component_lock.node_id b)) in
    let previous = ref None in
    List.iter (fun value ->
        require ~path (!previous <> Some (Component_lock.node_id value)) "Registry lock instance IDs must be unique.";
        previous := Some (Component_lock.node_id value)) components;
    let identities = Json.array (get "identities") |> List.mapi (fun index ->
        P.of_json ~path:(path ^ "/identities/" ^ string_of_int index)) |> identities ~path in
    let json = encode ~registry_id ~registry_version ~registry_fingerprint ~components ~identities in
    preflight ~path json;
    let canonical = Canonical.encode json in
    {json; fingerprint = Canonical.sha256 canonical; size = String.length canonical;
     registry_id; registry_version; registry_fingerprint; components; identities}
  let make ~registry_id ~registry_version ~registry_fingerprint ~components ~identities =
    of_json (encode ~registry_id ~registry_version ~registry_fingerprint ~components ~identities)
  let to_json value = value.json
  let fingerprint value = value.fingerprint
  let canonical_size value = value.size
  let registry_id value = value.registry_id
  let registry_version value = value.registry_version
  let registry_fingerprint value = value.registry_fingerprint
  let components value = value.components
  let identities value = value.identities
end

type t = { json : Json.t; fingerprint : string; size : int; id : string; version : string;
           components : Component.t list; known : Component.t Keys.t }
let schema_version = "biocompiler.component_registry.v0.2"
let component_key value = Component.id value, Component.version value, Component.fingerprint value
let encode ~id ~version ~components =
  let budget = budget () in
  ignore (reserve budget (Json.Object ["schema_version",str schema_version; "id",str id; "version",str version;
      "components",Json.Array []]));
  let children = array budget Component.to_json components in
  Json.Object ["schema_version",str schema_version; "id",str id; "version",str version; "components",children]
let of_json ?(path = "") value =
  let fields = record ~path schema_version ["id"; "version"; "components"] value in
  let id = Json.name ~path:(path ^ "/id") (field path "id" fields) in
  let version = Json.name ~path:(path ^ "/version") (field path "version" fields) in
  let components = Json.array (field path "components" fields) |> List.mapi (fun index ->
      Component.of_json ~path:(path ^ "/components/" ^ string_of_int index)) in
  let entries = List.map (fun value -> component_key value, value) components
    |> List.sort (fun (a,_) (b,_) -> Stdlib.compare a b) in
  let previous = ref None and known = ref Keys.empty and all_identities = ref Keys.empty in
  List.iter (fun (((id,version,_) as key), component) ->
      require ~path (!previous <> Some (id,version)) "Duplicate or ambiguous component ID/version in registry.";
      previous := Some (id,version); known := Keys.add key component !known;
      each_identity (fun pin ->
          let key = identity_key pin in
          (match Keys.find_opt key !all_identities with None -> () | Some previous ->
              require ~path (P.content_fingerprint previous = P.content_fingerprint pin)
                "Ambiguous dependency identity: one kind/ID/version has different hashes.");
          all_identities := Keys.add key pin !all_identities) component) entries;
  let components = List.map snd entries in
  let json = encode ~id ~version ~components in
  preflight ~path json;
  let canonical = Canonical.encode json in
  {json; fingerprint = Canonical.sha256 canonical; size = String.length canonical; id; version; components; known = !known}
let make ~id ~version ~components = of_json (encode ~id ~version ~components)
let to_json value = value.json
let fingerprint value = value.fingerprint
let canonical_size value = value.size
let id value = value.id
let version value = value.version
let components value = value.components
let lock value instances =
  let budget = budget () and seen = Hashtbl.create 16 in
  let dependencies = ref [] in
  let components = List.map (fun (node_id,component) ->
      preflight (str node_id);
      ignore (Json.name (str node_id));
      require (not (Hashtbl.mem seen node_id)) "Registry lock instance IDs must be unique.";
      Hashtbl.add seen node_id ();
      require (Keys.mem (component_key component) value.known) "Selected component is absent or stale in this registry.";
      let selection = Component_lock.make ~node_id ~component_id:(Component.id component)
          ~version:(Component.version component) ~content_fingerprint:(Component.fingerprint component) in
      ignore (reserve budget (Component_lock.to_json selection));
      each_identity (fun pin -> ignore (reserve budget (P.to_json pin)); dependencies := pin :: !dependencies) component;
      selection) (bounded instances) in
  Lock.make ~registry_id:value.id ~registry_version:value.version ~registry_fingerprint:value.fingerprint
    ~components ~identities:(List.rev !dependencies)
let resolve value expected =
  require (Lock.registry_id expected = value.id && Lock.registry_version expected = value.version &&
           Lock.registry_fingerprint expected = value.fingerprint) "Registry identity/version/content lock mismatch.";
  let resolved = List.map (fun selection ->
      let key = Component_lock.component_id selection, Component_lock.version selection, Component_lock.content_fingerprint selection in
      match Keys.find_opt key value.known with
      | Some component -> Component_lock.node_id selection, component
      | None -> Diagnostic.fail "component_registry" "Selected component identity/version/content lock mismatch.") (Lock.components expected) in
  require (Json.equal (Lock.to_json (lock value resolved)) (Lock.to_json expected))
    "Model/reference/evidence dependency lock mismatch.";
  resolved

open Bioc_wire
module N = Runtime_number
module O = Component_contract.Operating_domain
module L = Component_registry.Component_lock
module Names = Set.Make (String)

let resource_profile = "biocompiler.composition.resources.v1"
let resource_limits = Json.Object ["profile", Json.String resource_profile;
    "max_bytes", Json.int Limits.max_request_bytes; "max_nodes", Json.int Limits.max_json_nodes;
    "max_depth", Json.int Limits.max_depth; "max_string_bytes", Json.int Limits.max_string_bytes;
    "max_number_chars", Json.int Limits.max_number_chars]
let str value = Json.String value
let obj value = Json.Object value
let require ?path condition message = Diagnostic.require ?path condition "composition_record" message
let limit ?path condition = Diagnostic.require ?path condition "composition_resource_limit"
    "Composition declaration exceeds its native resource profile."
let bounded_list ?path values =
  let rec count left = function [] -> () | _ :: rest -> limit ?path (left > 0); count (left - 1) rest in
  count Limits.max_json_nodes values; values

type visit = Enter of Json.t * int | Leave of Json.t
(* Wire-compatible values/bytes accounting, before recursive domain decoding or
   sorting. Every occurrence of shared JSON consumes the aggregate allowance. *)
let measure ?(path = "") value =
  let bytes = ref 0 and nodes = ref 0 and queued = ref 1 in
  let add amount = limit ~path (amount <= Limits.max_request_bytes - !bytes); bytes := !bytes + amount in
  let quoted text =
    limit ~path (String.length text <= Limits.max_string_bytes); add (String.length text + 2);
    String.iter (function '"' | '\\' | '\b' | '\012' | '\n' | '\r' | '\t' -> add 1
      | c when Char.code c < 32 -> add 5 | _ -> ()) text;
    Json.validate_utf8 text in
  let length maximum values =
    let rec count seen = function [] -> seen | _ :: rest -> limit ~path (seen < maximum); count (seen + 1) rest in
    count 0 values in
  let pending = ref [Enter (value, 0)] and active = ref [] in
  while !pending <> [] do
    let current = List.hd !pending in pending := List.tl !pending;
    match current with
    | Leave value -> active := List.filter (fun item -> item != value) !active
    | Enter (value, depth) ->
        decr queued; incr nodes;
        limit ~path (!nodes <= Limits.max_json_nodes && depth <= Limits.max_depth);
        let enter children count =
          Diagnostic.require ~path (not (List.exists (fun item -> item == value) !active))
            "composition_json_cycle" "Cyclic composition JSON record.";
          active := value :: !active; pending := Leave value :: !pending;
          List.iter (fun child -> pending := Enter (child, depth + 1) :: !pending) children;
          queued := !queued + count in
        (match value with
         | Json.Null -> add 4
         | Json.Bool value -> add (if value then 4 else 5)
         | Json.Int value ->
             limit ~path (Z.numbits value <= 4 * Limits.max_number_chars);
             let text = Z.to_string value in limit ~path (String.length text <= Limits.max_number_chars); add (String.length text)
         | Json.Float value ->
             Diagnostic.require ~path (Float.is_finite value) "nonfinite_number" "Nonfinite composition JSON number.";
             add (String.length (Canonical.float_string value))
         | Json.String value -> quoted value
         | Json.Array values ->
             let count = length (Limits.max_json_nodes - !nodes - !queued) values in
             add (2 + max 0 (count - 1)); enter values count
         | Json.Object fields ->
             let count = length (Limits.max_json_nodes - !nodes - !queued) fields in
             add (2 + count + max 0 (count - 1));
             let seen = Hashtbl.create 16 in
             List.iter (fun (key, _) -> quoted key;
                 Diagnostic.require ~path (not (Hashtbl.mem seen key)) "duplicate_key" "Duplicate composition field.";
                 Hashtbl.add seen key ()) fields;
             enter (List.map snd fields) count)
  done;
  !bytes, !nodes

let finish value = ignore (measure value); value
let record ~path keys value =
  ignore (measure ~path value);
  let fields = Json.object_fields ~path value in Json.exact_fields ~path keys fields; fields
let field path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let name path key fields = Json.name ~path:(path ^ "/" ^ key) (field path key fields)
let names ~path value =
  let seen = Hashtbl.create 16 in
  Json.array ~path value |> List.mapi (fun index value ->
      let path = path ^ "/" ^ string_of_int index in
      let value = Json.name ~path value in
      require ~path (not (Hashtbl.mem seen value)) "Composition names must be unique.";
      Hashtbl.add seen value (); value)
let records ~path decode value = Json.array ~path value |> List.mapi
    (fun index value -> decode ?path:(Some (path ^ "/" ^ string_of_int index)) value)
let unique ~path id values =
  let seen = Hashtbl.create 16 in
  List.iter (fun value -> let id = id value in
      require ~path (not (Hashtbl.mem seen id)) "Duplicate composition inventory identity.";
      Hashtbl.add seen id ()) values
let quantity ~path value =
  let number = try N.of_json ~path value with Diagnostic.Error _ ->
      Diagnostic.fail ~path "composition_record" "Composition quantity must be a finite nonnegative number." in
  require ~path (N.compare number N.zero >= 0) "Composition quantity must be a finite nonnegative number.";
  number
let quantity_json ~path = function
  | N.Integer number -> let value = Json.Int number in ignore (quantity ~path value); value
  | N.Real number -> let value = Json.Float number in ignore (quantity ~path value); value
let optional decode = function Json.Null -> None | value -> Some (decode value)
let option_json encode = function None -> Json.Null | Some value -> encode value

(* Shared reservation across all typed constructor fields. A repeated large
   child cannot allocate an unbounded expanded array before aggregate rejection. *)
type budget = { mutable bytes : int; mutable nodes : int }
let add (budget : budget) bytes nodes =
  limit (bytes <= Limits.max_request_bytes - budget.bytes && nodes <= Limits.max_json_nodes - budget.nodes);
  budget.bytes <- budget.bytes + bytes; budget.nodes <- budget.nodes + nodes
let leaf value (budget : budget) = let bytes, nodes = measure value in add budget bytes nodes; value
let array encode values (budget : budget) =
  let values = bounded_list values in add budget 2 1;
  Json.Array (List.mapi (fun index value ->
      if index > 0 then add budget 1 0;
      leaf (encode value) budget) values)
let strings values = array str values
let document fields =
  let budget = {bytes = 2; nodes = 1} in
  obj (List.mapi (fun index (key, encode) ->
      let bytes, _ = measure (str key) in add budget (bytes + 1 + if index = 0 then 0 else 1) 0;
      key, encode budget) fields) |> finish

let source_json (source : Behavior.source_location) = obj ["file", str source.file;
    "line", Json.Int source.line; "function", str source.function_name]
let source ~path value =
  let fields = record ~path ["file"; "line"; "function"] value in
  let file = name path "file" fields and function_name = name path "function" fields in
  let line = Json.integer ~path:(path ^ "/line") (field path "line" fields) in
  Diagnostic.require ~path (Z.compare line Z.zero > 0) "invalid_source" "Source line must be a positive integer.";
  {Behavior.file; line; function_name}

module Lifecycle = struct
  type t = {json : Json.t; start : N.t; end_time : N.t option; unit : string}
  let of_json ?(path = "") value =
    let fields = record ~path ["start"; "end"; "unit"] value in
    let start = quantity ~path:(path ^ "/start") (field path "start" fields) in
    let end_time = optional (quantity ~path:(path ^ "/end")) (field path "end" fields) in
    require ~path (match end_time with None -> true | Some ending -> N.compare ending start > 0)
      "A lifecycle must have positive duration.";
    let unit = name path "unit" fields in
    {json = value; start; end_time; unit}
  let to_json (value : t) = value.json
  let fingerprint value = Canonical.fingerprint (to_json value)
  let make ?(start = N.zero) ?end_time ?(unit = "s") () =
    of_json (obj ["start", quantity_json ~path:"/start" start;
        "end", option_json (quantity_json ~path:"/end") end_time; "unit", str unit])
  let start (value : t) = value.start
  let end_time (value : t) = value.end_time
  let unit (value : t) = value.unit
end

module Instance = struct
  type placement = Encoded_here | Co_payload
  type t = {json : Json.t; id : string; component : L.t; required_domain : O.t;
            placement : placement; lifetime : Lifecycle.t; requirements : string list;
            source : Behavior.source_location option}
  let placement_string = function Encoded_here -> "encoded_here" | Co_payload -> "co_payload"
  let encode ~id ~component ~required_domain ~placement ~lifetime ~requirement_ids ~source =
    document ["id", leaf (str id); "component", leaf (L.to_json component);
        "required_domain", leaf (O.to_json required_domain); "placement", leaf (str (placement_string placement));
        "lifetime", leaf (Lifecycle.to_json lifetime); "requirement_ids", strings requirement_ids;
        "source", leaf (option_json source_json source)]
  let of_json ?(path = "") value =
    let fields = record ~path ["id"; "component"; "required_domain"; "placement"; "lifetime"; "requirement_ids"; "source"] value in
    let component = L.of_json ~path:(path ^ "/component") (field path "component" fields) in
    let required_domain = O.of_json ~path:(path ^ "/required_domain") (field path "required_domain" fields) in
    let lifetime = Lifecycle.of_json ~path:(path ^ "/lifetime") (field path "lifetime" fields) in
    let source = optional (source ~path:(path ^ "/source")) (field path "source" fields) in
    let id = name path "id" fields in
    require ~path (L.node_id component = id) "An instance must carry its own exact component lock.";
    let placement = match Json.string ~path:(path ^ "/placement") (field path "placement" fields) with
      | "encoded_here" -> Encoded_here | "co_payload" -> Co_payload
      | _ -> Diagnostic.fail ~path "composition_record" "Invalid instance placement." in
    let requirements = names ~path:(path ^ "/requirement_ids") (field path "requirement_ids" fields) in
    let json = encode ~id ~component ~required_domain ~placement ~lifetime ~requirement_ids:requirements ~source in
    {json; id; component; required_domain; placement; lifetime; requirements; source}
  let to_json (value : t) = value.json
  let fingerprint value = Canonical.fingerprint (to_json value)
  let make ~id ~component ~required_domain ?(placement = Encoded_here) ?(lifetime = Lifecycle.make ())
      ?(requirement_ids = []) ?source () =
    encode ~id ~component ~required_domain ~placement ~lifetime ~requirement_ids ~source |> of_json
  let id (value : t) = value.id
  let component (value : t) = value.component
  let required_domain (value : t) = value.required_domain
  let placement (value : t) = value.placement
  let placement_name (value : t) = placement_string value.placement
  let lifetime (value : t) = value.lifetime
  let requirement_ids (value : t) = value.requirements
  let source (value : t) = value.source
end

module Connection = struct
  type t = {json : Json.t; producer_instance : string; producer_port : string;
            consumer_instance : string; consumer_port : string}
  let of_json ?(path = "") value =
    let fields = record ~path ["producer_instance"; "producer_port"; "consumer_instance"; "consumer_port"] value in
    {json = value; producer_instance = name path "producer_instance" fields; producer_port = name path "producer_port" fields;
     consumer_instance = name path "consumer_instance" fields; consumer_port = name path "consumer_port" fields}
  let to_json (value : t) = value.json
  let fingerprint value = Canonical.fingerprint (to_json value)
  let make ~producer_instance ~producer_port ~consumer_instance ~consumer_port =
    of_json (obj ["producer_instance", str producer_instance; "producer_port", str producer_port;
        "consumer_instance", str consumer_instance; "consumer_port", str consumer_port])
  let producer_instance (value : t) = value.producer_instance
  let producer_port (value : t) = value.producer_port
  let consumer_instance (value : t) = value.consumer_instance
  let consumer_port (value : t) = value.consumer_port
end

module Provider = struct
  type kind = Host | External | Unresolved
  type t = {json : Json.t; id : string; kind : kind; capabilities : Component.Capability.t list;
            supported_targets : string list; depends_on : string list; evidence_refs : string list}
  let kind_string = function Host -> "host" | External -> "external" | Unresolved -> "unresolved"
  let encode ~id ~kind ~capabilities ~supported_targets ~depends_on ~evidence_refs =
    document ["id", leaf (str id); "kind", leaf (str (kind_string kind));
        "capabilities", array Component.Capability.to_json capabilities; "supported_targets", strings supported_targets;
        "depends_on", strings depends_on; "evidence_refs", strings evidence_refs]
  let of_json ?(path = "") value =
    let fields = record ~path ["id"; "kind"; "capabilities"; "supported_targets"; "depends_on"; "evidence_refs"] value in
    let capabilities = records ~path:(path ^ "/capabilities") Component.Capability.of_json (field path "capabilities" fields) in
    let id = name path "id" fields in
    let kind = match Json.string ~path:(path ^ "/kind") (field path "kind" fields) with
      | "host" -> Host | "external" -> External | "unresolved" -> Unresolved
      | _ -> Diagnostic.fail ~path "composition_record" "Invalid explicit provider kind." in
    unique ~path Component.Capability.id capabilities;
    let supported_targets = names ~path:(path ^ "/supported_targets") (field path "supported_targets" fields) in
    let depends_on = names ~path:(path ^ "/depends_on") (field path "depends_on" fields) in
    let evidence_refs = names ~path:(path ^ "/evidence_refs") (field path "evidence_refs" fields) in
    require ~path (supported_targets <> []) "A provider must declare supported targets.";
    let json = encode ~id ~kind ~capabilities ~supported_targets ~depends_on ~evidence_refs in
    {json; id; kind; capabilities; supported_targets; depends_on; evidence_refs}
  let to_json (value : t) = value.json
  let fingerprint value = Canonical.fingerprint (to_json value)
  let make ~id ~kind ~capabilities ~supported_targets ?(depends_on = []) ?(evidence_refs = []) () =
    encode ~id ~kind ~capabilities ~supported_targets ~depends_on ~evidence_refs |> of_json
  let id (value : t) = value.id
  let kind (value : t) = value.kind
  let kind_name (value : t) = kind_string value.kind
  let capabilities (value : t) = value.capabilities
  let supported_targets (value : t) = value.supported_targets
  let depends_on (value : t) = value.depends_on
  let evidence_refs (value : t) = value.evidence_refs
end

module Dependency_binding = struct
  type t = {json : Json.t; instance_id : string; requirement_id : string; provider_id : string}
  let of_json ?(path = "") value =
    let fields = record ~path ["instance_id"; "requirement_id"; "provider_id"] value in
    {json = value; instance_id = name path "instance_id" fields; requirement_id = name path "requirement_id" fields;
     provider_id = name path "provider_id" fields}
  let to_json (value : t) = value.json
  let fingerprint value = Canonical.fingerprint (to_json value)
  let make ~instance_id ~requirement_id ~provider_id =
    of_json (obj ["instance_id", str instance_id; "requirement_id", str requirement_id; "provider_id", str provider_id])
  let instance_id (value : t) = value.instance_id
  let requirement_id (value : t) = value.requirement_id
  let provider_id (value : t) = value.provider_id
end

module Resource_pool = struct
  type t = {json : Json.t; id : string; resource : string; unit : string; capacity : N.t option;
            provider_id : string; dtype : Type_spec.t}
  let default_dtype = Type_spec.of_json (Json.parse {|{"kind":"scalar","name":"Level","dimensions":{},"arguments":[]}|})
  let encode ~id ~resource ~unit ~capacity ~provider_id ~dtype =
    obj ["id", str id; "resource", str resource; "unit", str unit; "capacity", option_json (quantity_json ~path:"/capacity") capacity;
         "provider_id", str provider_id; "dtype", Type_spec.to_json dtype] |> finish
  let of_json ?(path = "") value =
    let fields = record ~path ["id"; "resource"; "unit"; "capacity"; "provider_id"; "dtype"] value in
    (* Python's importer decodes the contract type before calling its record
       constructor. Preserve that distinction from a scalar pool's own check. *)
    let dtype = Type_spec.of_json ~path:(path ^ "/dtype") (field path "dtype" fields) |> Component_contract.contract_type in
    let id = name path "id" fields and resource = name path "resource" fields in
    let unit = name path "unit" fields and provider_id = name path "provider_id" fields in
    let capacity = optional (quantity ~path:(path ^ "/capacity")) (field path "capacity" fields) in
    require ~path (Type_spec.kind dtype = Type_spec.Scalar) "Resource pools require a scalar type.";
    let json = encode ~id ~resource ~unit ~capacity ~provider_id ~dtype in
    {json; id; resource; unit; capacity; provider_id; dtype}
  let to_json (value : t) = value.json
  let fingerprint value = Canonical.fingerprint (to_json value)
  let make ~id ~resource ~unit ~capacity ~provider_id ?(dtype = default_dtype) () =
    encode ~id ~resource ~unit ~capacity ~provider_id ~dtype |> of_json
  let id (value : t) = value.id
  let resource (value : t) = value.resource
  let unit (value : t) = value.unit
  let capacity (value : t) = value.capacity
  let provider_id (value : t) = value.provider_id
  let dtype (value : t) = value.dtype
end

module Resource_binding = struct
  type t = {json : Json.t; instance_id : string; reservation_id : string; pool_id : string}
  let of_json ?(path = "") value =
    let fields = record ~path ["instance_id"; "reservation_id"; "pool_id"] value in
    {json = value; instance_id = name path "instance_id" fields; reservation_id = name path "reservation_id" fields;
     pool_id = name path "pool_id" fields}
  let to_json (value : t) = value.json
  let fingerprint value = Canonical.fingerprint (to_json value)
  let make ~instance_id ~reservation_id ~pool_id =
    of_json (obj ["instance_id", str instance_id; "reservation_id", str reservation_id; "pool_id", str pool_id])
  let instance_id (value : t) = value.instance_id
  let reservation_id (value : t) = value.reservation_id
  let pool_id (value : t) = value.pool_id
end

(* Python JsonArtifact.to_json(indent=None) uses spaced separators. Reproduce
   that exact compatibility key independently from compact identity encoding,
   inserting spaces only outside quoted strings. UTF-8 byte order matches
   Unicode scalar order for the validated strings. *)
let spaced_json value =
  let compact = Canonical.encode value in
  let output = Buffer.create (String.length compact) in
  let quoted = ref false and escaped = ref false in
  String.iter (fun character ->
      Buffer.add_char output character;
      if !quoted then (
        if !escaped then escaped := false
        else if character = '\\' then escaped := true
        else if character = '"' then quoted := false)
      else if character = '"' then quoted := true
      else if character = ',' || character = ':' then Buffer.add_char output ' ') compact;
  Buffer.contents output
let sorted encode values =
  List.map (fun value -> spaced_json (encode value), value) values
  |> List.stable_sort (fun (left, _) (right, _) -> String.compare left right)
  |> List.map snd

type t = {json : Json.t; fingerprint : string; canonical_size : int; target : Build_request.Target.t;
          registry_lock : Component_registry.Lock.t; instances : Instance.t list; connections : Connection.t list;
          providers : Provider.t list; dependency_bindings : Dependency_binding.t list;
          resource_pools : Resource_pool.t list; resource_bindings : Resource_binding.t list; requirements : string list}
let schema_version = "biocompiler.composition_request.v0.1"
let encode ~target ~registry_lock ~instances ~connections ~providers ~dependency_bindings ~resource_pools ~resource_bindings ~requirement_ids =
  document ["schema_version", leaf (str schema_version); "target", leaf (Build_request.Target.to_json target);
      "registry_lock", leaf (Component_registry.Lock.to_json registry_lock); "instances", array Instance.to_json instances;
      "connections", array Connection.to_json connections; "providers", array Provider.to_json providers;
      "dependency_bindings", array Dependency_binding.to_json dependency_bindings;
      "resource_pools", array Resource_pool.to_json resource_pools; "resource_bindings", array Resource_binding.to_json resource_bindings;
      "requirement_ids", strings requirement_ids]
let of_json ?(path = "") value =
  let fields = record ~path ["schema_version"; "target"; "registry_lock"; "instances"; "connections";
                            "providers"; "dependency_bindings"; "resource_pools"; "resource_bindings"; "requirement_ids"] value in
  Diagnostic.require ~path (Json.string (field path "schema_version" fields) = schema_version)
    "unsupported_schema" "Unsupported composition schema.";
  let target = Build_request.Target.of_json ~path:(path ^ "/target") (field path "target" fields) in
  let registry_lock = Component_registry.Lock.of_json ~path:(path ^ "/registry_lock") (field path "registry_lock" fields) in
  let instances = records ~path:(path ^ "/instances") Instance.of_json (field path "instances" fields) in
  let connections = records ~path:(path ^ "/connections") Connection.of_json (field path "connections" fields) in
  let providers = records ~path:(path ^ "/providers") Provider.of_json (field path "providers" fields) in
  let dependency_bindings = records ~path:(path ^ "/dependency_bindings") Dependency_binding.of_json (field path "dependency_bindings" fields) in
  let resource_pools = records ~path:(path ^ "/resource_pools") Resource_pool.of_json (field path "resource_pools" fields) in
  let resource_bindings = records ~path:(path ^ "/resource_bindings") Resource_binding.of_json (field path "resource_bindings" fields) in
  let requirements = names ~path:(path ^ "/requirement_ids") (field path "requirement_ids" fields) in
  (* Bound the fully normalized representation before allocating sort keys. *)
  ignore (encode ~target ~registry_lock ~instances ~connections ~providers ~dependency_bindings ~resource_pools ~resource_bindings
            ~requirement_ids:requirements);
  let instances = sorted Instance.to_json instances and connections = sorted Connection.to_json connections in
  let providers = sorted Provider.to_json providers and dependency_bindings = sorted Dependency_binding.to_json dependency_bindings in
  let resource_pools = sorted Resource_pool.to_json resource_pools and resource_bindings = sorted Resource_binding.to_json resource_bindings in
  require ~path (instances <> []) "A composition requires at least one selected instance.";
  unique ~path Instance.id instances; unique ~path Provider.id providers; unique ~path Resource_pool.id resource_pools;
  let selected = List.fold_left (fun set value -> Names.add (Instance.id value) set) Names.empty instances in
  require ~path (not (List.exists (fun value -> Names.mem (Provider.id value) selected) providers))
    "Explicit providers cannot replace selected component providers.";
  let requirements = List.sort String.compare requirements in
  let declared = List.fold_left (fun set id -> Names.add id set) Names.empty requirements in
  require ~path (List.for_all (fun item -> List.for_all (fun id -> Names.mem id declared) (Instance.requirement_ids item)) instances)
    "Instance requirements must belong to the request.";
  let json = encode ~target ~registry_lock ~instances ~connections ~providers ~dependency_bindings ~resource_pools ~resource_bindings
      ~requirement_ids:requirements in
  let canonical = Canonical.encode json in
  {json; fingerprint = Canonical.sha256 canonical; canonical_size = String.length canonical; target; registry_lock;
   instances; connections; providers; dependency_bindings; resource_pools; resource_bindings; requirements}
let to_json (value : t) = value.json
let fingerprint (value : t) = value.fingerprint
let canonical_size (value : t) = value.canonical_size
let make ~target ~registry_lock ~instances ?(connections = []) ?(providers = []) ?(dependency_bindings = [])
    ?(resource_pools = []) ?(resource_bindings = []) ?(requirement_ids = []) () =
  encode ~target ~registry_lock ~instances ~connections ~providers ~dependency_bindings ~resource_pools ~resource_bindings ~requirement_ids |> of_json
let target (value : t) = value.target
let registry_lock (value : t) = value.registry_lock
let instances (value : t) = value.instances
let connections (value : t) = value.connections
let providers (value : t) = value.providers
let dependency_bindings (value : t) = value.dependency_bindings
let resource_pools (value : t) = value.resource_pools
let resource_bindings (value : t) = value.resource_bindings
let requirement_ids (value : t) = value.requirements

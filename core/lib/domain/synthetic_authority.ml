open Bioc_wire
module Names = Set.Make (String)
module By_name = Map.Make (String)
module Lock = Component_registry.Component_lock
let resource_profile = "biocompiler.synthetic_authority.resources.v1"
let combinational_profile = "biocompiler.synthetic.combinational.v0.1"
let temporal_profile = "biocompiler.synthetic.temporal.v0.1"
let catalog_version = "biocompiler.synthetic.catalog.v0.2"
let generator_version = "biocompiler.synthetic.generator.v0.4"
let model_runner_version = "biocompiler.synthetic.runner.v0.2"
let checker_version = "biocompiler.synthetic.acceptance.v0.5"
let require ?path condition message = Diagnostic.require ?path condition "synthetic_authority" message
let limit ?path condition = Diagnostic.require ?path condition "synthetic_authority_limit"
    "Synthetic authority exceeds its native resource boundary."
let str value = Json.String value
let bounded values =
  let rec loop count = function [] -> values | _ :: rest ->
    limit (count < Limits.max_json_nodes); loop (count + 1) rest in
  loop 0 values

type visit = Enter of Json.t * int | Leave of Json.t
let measure ?(path = "") ?(maximum = Limits.max_request_bytes) value =
  limit ~path (maximum > 0 && maximum <= Limits.max_request_bytes);
  let bytes = ref 0 and nodes = ref 0 and queued = ref 1 in
  let add amount = limit ~path (amount <= maximum - !bytes); bytes := !bytes + amount in
  let quoted value =
    limit ~path (String.length value <= Limits.max_string_bytes); add (String.length value + 2);
    String.iter (function '"' | '\\' | '\b' | '\012' | '\n' | '\r' | '\t' -> add 1
      | value when Char.code value < 32 -> add 5 | _ -> ()) value;
    Json.validate_utf8 value in
  let length maximum values =
    let rec loop count = function [] -> count | _ :: rest ->
      limit ~path (count < maximum); loop (count + 1) rest in
    loop 0 values in
  let pending = ref [Enter (value, 0)] and active = ref [] in
  while !pending <> [] do
    let next = List.hd !pending in pending := List.tl !pending;
    match next with
    | Leave value -> active := List.filter (fun item -> item != value) !active
    | Enter (value, depth) ->
        decr queued; incr nodes; limit ~path (!nodes <= Limits.max_json_nodes && depth <= Limits.max_depth);
        let enter children count =
          Diagnostic.require ~path (not (List.exists (fun item -> item == value) !active))
            "synthetic_authority_cycle" "Cyclic synthetic authority record.";
          active := value :: !active; pending := Leave value :: !pending;
          List.iter (fun child -> pending := Enter (child, depth + 1) :: !pending) children;
          queued := !queued + count in
        (match value with
        | Json.Null -> add 4
        | Json.Bool value -> add (if value then 4 else 5)
        | Json.Int value ->
            limit ~path (Z.numbits value <= 4 * Limits.max_number_chars);
            let text = Z.to_string value in
            limit ~path (String.length text <= Limits.max_number_chars); add (String.length text)
        | Json.Float value ->
            Diagnostic.require ~path (Float.is_finite value) "nonfinite_number" "Synthetic authority requires finite JSON numbers.";
            add (String.length (Canonical.float_string value))
        | Json.String value -> quoted value
        | Json.Array values ->
            let count = length (Limits.max_json_nodes - !nodes - !queued) values in
            add (2 + max 0 (count - 1)); enter values count
        | Json.Object fields ->
            let count = length ((Limits.max_json_nodes - !nodes - !queued) / 2) fields in
            nodes := !nodes + count; add (2 + count + max 0 (count - 1));
            let seen = Hashtbl.create 16 in
            List.iter (fun (key, _) -> quoted key;
              Diagnostic.require ~path (not (Hashtbl.mem seen key)) "duplicate_key" "Duplicate synthetic authority field.";
              Hashtbl.add seen key ()) fields;
            enter (List.map snd fields) count)
  done;
  !bytes, !nodes

type budget = { mutable bytes : int; mutable nodes : int }
let budget () = {bytes = 0; nodes = 0}
let reserve budget value =
  let bytes,nodes = measure value in
  limit (bytes <= Limits.max_request_bytes - budget.bytes && nodes <= Limits.max_json_nodes - budget.nodes);
  budget.bytes <- budget.bytes + bytes; budget.nodes <- budget.nodes + nodes; value
let separator budget =
  limit (budget.bytes < Limits.max_request_bytes); budget.bytes <- budget.bytes + 1
let array budget encode values =
  let first = ref true in
  Json.Array (List.map (fun value ->
    if !first then first := false else separator budget;
    reserve budget (encode value)) (bounded values))
(* Empty object/array roots are reserved in the enclosing skeleton. This
   reserves keys and every repeated value before building each populated map. *)
let name_map budget values =
  let first = ref true in
  Json.Object (List.map (fun (key,values) ->
    if !first then first := false else separator budget;
    ignore (reserve budget (str key)); separator budget;
    ignore (reserve budget (Json.Array []));
    key,array budget str values) (bounded values))
let field path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let record ~path schema keys raw =
  ignore (measure ~path raw);
  let fields = Json.object_fields ~path raw in
  Json.exact_fields ~path ("schema_version" :: keys) fields;
  Diagnostic.require ~path (Json.string (field path "schema_version" fields) = schema)
    "unsupported_schema" "Unsupported synthetic authority schema.";
  fields
let hash ~path ~label raw =
  let value = Json.string ~path raw in
  require ~path (String.length value = 64 && String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) value)
    (label ^ " must be a SHA-256 identity."); value
let names ~path ~label raw =
  let values = Json.array ~path raw |> List.map (Json.name ~path) in
  let seen = ref Names.empty in
  List.iter (fun value -> require ~path (not (Names.mem value !seen)) (label ^ " must be unique.");
    seen := Names.add value !seen) values;
  values
let finish raw =
  ignore (measure raw); let canonical = Canonical.encode raw in
  Canonical.sha256 canonical,String.length canonical

module Component = struct
  type t = {json:Json.t; fingerprint:string; size:int; id:string; version:string; operation:string;
    interface:string; model_version:string; assumptions:string list; guarantees:string list; supported_profile:string}
  let schema_version = "biocompiler.component.synthetic.v0.1"
  let encode ~id ~version ~operation ~interface ~model_version ~assumptions ~guarantees ~supported_profile =
    let budget = budget () in
    let skeleton = ["schema_version",str schema_version; "id",str id; "version",str version;
      "operation",str operation; "interface",str interface; "model_version",str model_version;
      "assumptions",Json.Array []; "guarantees",Json.Array []; "supported_profile",str supported_profile] in
    ignore (reserve budget (Json.Object skeleton));
    let assumptions = array budget str assumptions and guarantees = array budget str guarantees in
    Json.Object (("assumptions",assumptions) :: ("guarantees",guarantees) ::
      List.filter (fun (key,_) -> key <> "assumptions" && key <> "guarantees") skeleton)
  let of_json ?(path = "") raw =
    let fields = record ~path schema_version
      ["id";"version";"operation";"interface";"model_version";"assumptions";"guarantees";"supported_profile"] raw in
    let get key = field path key fields in
    let name key = Json.name ~path:(path ^ "/" ^ key) (get key) in
    let id = name "id" in
    let version = name "version" in
    let operation = name "operation" in
    let interface = name "interface" in
    let model_version = name "model_version" in
    let supported_profile = name "supported_profile" in
    let assumptions = names ~path:(path ^ "/assumptions") ~label:"assumptions" (get "assumptions") in
    let guarantees = names ~path:(path ^ "/guarantees") ~label:"guarantees" (get "guarantees") in
    let json = encode ~id ~version ~operation ~interface ~model_version ~assumptions ~guarantees ~supported_profile in
    let fingerprint,size = finish json in
    {json;fingerprint;size;id;version;operation;interface;model_version;assumptions;guarantees;supported_profile}
  let make ~id ~version ~operation ~interface ~model_version ~assumptions ~guarantees ~supported_profile =
    of_json (encode ~id ~version ~operation ~interface ~model_version ~assumptions ~guarantees ~supported_profile)
  let to_json value = value.json
  let fingerprint value = value.fingerprint
  let canonical_size value = value.size
  let id value = value.id
  let version value = value.version
  let operation value = value.operation
  let interface value = value.interface
  let model_version value = value.model_version
  let assumptions value = value.assumptions
  let guarantees value = value.guarantees
  let supported_profile value = value.supported_profile
end

module Catalog = struct
  type t = {json:Json.t;fingerprint:string;size:int;version:string;components:Component.t list;
    operations:Component.t By_name.t}
  let schema_version = "biocompiler.synthetic_catalog.v0.1"
  let encode ~version components =
    let budget = budget () in
    let skeleton = ["schema_version",str schema_version;"version",str version;"components",Json.Array []] in
    ignore (reserve budget (Json.Object skeleton));
    Json.Object (("components",array budget Component.to_json components) :: List.remove_assoc "components" skeleton)
  let of_json ?(path = "") raw =
    let fields = record ~path schema_version ["version";"components"] raw in
    let get key = field path key fields in
    (* Match import order: children are decoded before constructor version and
       inventory checks, although all raw input is bounded before either. *)
    let components = Json.array ~path:(path ^ "/components") (get "components") |> List.mapi
      (fun index -> Component.of_json ~path:(path ^ "/components/" ^ string_of_int index)) in
    let version = Json.string ~path:(path ^ "/version") (get "version") in
    require ~path (version = catalog_version) "Unsupported synthetic catalog version.";
    require ~path (components <> []) "A catalog requires synthetic component records.";
    let components = List.sort (fun a b -> String.compare (Component.id a) (Component.id b)) components in
    let ids = ref Names.empty and operations = ref By_name.empty in
    List.iter (fun component ->
      require ~path (not (Names.mem (Component.id component) !ids) &&
        not (By_name.mem (Component.operation component) !operations))
        "Catalog component IDs and operation providers must be unique.";
      ids := Names.add (Component.id component) !ids;
      operations := By_name.add (Component.operation component) component !operations) components;
    let json = encode ~version components in
    let fingerprint,size = finish json in
    {json;fingerprint;size;version;components;operations = !operations}
  let make ?(version = catalog_version) components = of_json (encode ~version components)
  let to_json value = value.json
  let fingerprint value = value.fingerprint
  let canonical_size value = value.size
  let version value = value.version
  let components value = value.components
  let for_operation value operation = By_name.find_opt operation value.operations
  let lock value mechanism =
    let budget = budget () in
    ignore (reserve budget (Json.Array []));
    let first = ref true in
    Mechanism.nodes mechanism
    |> List.sort (fun a b -> String.compare (Mechanism.Node.id a) (Mechanism.Node.id b))
    |> List.map (fun node ->
      let operation = Mechanism.Node.kind node in
      let component = match for_operation value operation with
        | Some component -> component
        | None -> Diagnostic.fail "synthetic_catalog_operation" operation in
      let lock = Lock.make ~node_id:(Mechanism.Node.id node) ~component_id:(Component.id component)
        ~version:(Component.version component) ~content_fingerprint:(Component.fingerprint component) in
      if !first then first := false else separator budget;
      ignore (reserve budget (Lock.to_json lock)); lock)
end

let interfaces = [
  "input","External Boolean or canonical scalar observation -> identical typed port.";
  "constant","Explicit typed Boolean or canonical scalar literal -> identical typed port.";
  "and","At least two Boolean ports -> Boolean conjunction, preserving contact binding.";
  "or","At least two Boolean ports -> Boolean disjunction, preserving contact binding.";
  "not","One Boolean port -> Boolean negation, preserving contact binding.";
  "compare","Two dimension-compatible scalar ports -> Boolean comparison.";
  "select","Boolean condition and two dimension-compatible values -> branch value of that type.";
  "any_contact","One Boolean contact port -> Boolean existential reduction at cell scope.";
  "output","One port -> identical type and exact declared observable endpoint."]
let temporal_interfaces = [
  "held_for","Boolean input -> true after uninterrupted positive duration; false immediately on input loss; no prehistory.";
  "onset","Boolean input -> event on false-to-true transition, including initially true; per binding and contact episode.";
  "pulse","Event trigger -> true until exclusive expiry; every trigger refreshes expiry, including at the old deadline.";
  "memory","Cell event-set and level-reset -> initially false latch; reset dominates set/expiry, set wins expiry; optional duration."]
let catalog profile interfaces =
  Catalog.make (List.map (fun (operation,interface) ->
    Component.make ~id:("synthetic." ^ operation) ~version:"2" ~operation ~interface
      ~model_version:model_runner_version ~supported_profile:profile
      ~assumptions:["Complete atomic snapshots with explicit contact identities and canonical units.";
        "One role and one abstract compartment; no cross-role or compartment transport."]
      ~guarantees:[(if profile = temporal_profile then
        "Atomic right-continuous digital evaluation, including startup and internal deadlines; external changes precede due timers."
        else "Stateless right-continuous digital evaluation, including the initial snapshot.");
        "No quantitative biological guarantee or empirical evidence is supplied."]) interfaces)
let combinational_catalog = catalog combinational_profile interfaces
let temporal_catalog = catalog temporal_profile (interfaces @ temporal_interfaces)
let catalog_for_profile profile =
  if profile = combinational_profile then combinational_catalog
  else if profile = temporal_profile then temporal_catalog
  else Diagnostic.fail "synthetic_authority" "Unsupported synthetic generation profile."

module Config = struct
  type t = {json:Json.t;fingerprint:string;size:int;profile_version:string;generator_version:string;
    catalog_fingerprint:string;witness_selection:string;conjunction_strategy:string}
  let schema_version = "biocompiler.synthetic_generator_config.v0.3"
  let expected_generator_version = generator_version
  let encode ~profile_version ~generator_version ~catalog_fingerprint ~witness_selection ~conjunction_strategy =
    Json.Object ["schema_version",str schema_version;"profile_version",str profile_version;
      "generator_version",str generator_version;"catalog_fingerprint",str catalog_fingerprint;
      "witness_selection",str witness_selection;"conjunction_strategy",str conjunction_strategy]
  let of_json ?(path = "") raw =
    let fields = record ~path schema_version
      ["profile_version";"generator_version";"catalog_fingerprint";"witness_selection";"conjunction_strategy"] raw in
    let get key = field path key fields in
    let catalog_fingerprint = hash ~path:(path ^ "/catalog_fingerprint") ~label:"Catalog fingerprint" (get "catalog_fingerprint") in
    let profile_version = Json.string ~path:(path ^ "/profile_version") (get "profile_version") in
    let catalog = catalog_for_profile profile_version in
    let configuration_generator = Json.string ~path:(path ^ "/generator_version") (get "generator_version") in
    require ~path (configuration_generator = expected_generator_version) "Unsupported synthetic generator version.";
    require ~path (catalog_fingerprint = Catalog.fingerprint catalog) "The selected synthetic catalog is unavailable or stale.";
    let witness_selection = Json.string ~path:(path ^ "/witness_selection") (get "witness_selection") in
    require ~path (witness_selection = "closed_band_lower_endpoint") "Unsupported response witness selection policy.";
    let conjunction_strategy = Json.string ~path:(path ^ "/conjunction_strategy") (get "conjunction_strategy") in
    require ~path (List.mem conjunction_strategy ["native";"de_morgan"]) "Unsupported conjunction strategy.";
    let generator_version = configuration_generator in
    let json = encode ~profile_version ~generator_version ~catalog_fingerprint ~witness_selection ~conjunction_strategy in
    let fingerprint,size = finish json in
    {json;fingerprint;size;profile_version;generator_version;catalog_fingerprint;witness_selection;conjunction_strategy}
  let make ?(profile_version = combinational_profile) ?(generator_version = expected_generator_version)
      ?catalog_fingerprint ?(witness_selection = "closed_band_lower_endpoint") ?(conjunction_strategy = "native") () =
    let catalog = catalog_for_profile profile_version in
    let catalog_fingerprint = match catalog_fingerprint with Some value -> value | None -> Catalog.fingerprint catalog in
    (* The Python constructor supplies a missing catalog pin and checks version
       before catalog equality; imported JSON first checks SHA syntax. Preserve
       that distinction rather than exposing the stricter import's precedence. *)
    require (generator_version = expected_generator_version) "Unsupported synthetic generator version.";
    require (catalog_fingerprint = Catalog.fingerprint catalog) "The selected synthetic catalog is unavailable or stale.";
    require (witness_selection = "closed_band_lower_endpoint") "Unsupported response witness selection policy.";
    require (List.mem conjunction_strategy ["native";"de_morgan"]) "Unsupported conjunction strategy.";
    of_json (encode ~profile_version ~generator_version ~catalog_fingerprint ~witness_selection ~conjunction_strategy)
  let to_json value = value.json
  let fingerprint value = value.fingerprint
  let canonical_size value = value.size
  let profile_version value = value.profile_version
  let generator_version value = value.generator_version
  let catalog_fingerprint value = value.catalog_fingerprint
  let witness_selection value = value.witness_selection
  let conjunction_strategy value = value.conjunction_strategy
end

module Candidate = struct
  type t = {json:Json.t;fingerprint:string;size:int;request_fingerprint:string;mechanism:Mechanism.t;
    observation_map:Observation_map.t;source_map:(string * string list) list;
    behavior_requirement_ids:(string * string list) list;component_locks:Lock.t list;generator_config:Config.t}
  let schema_version = "biocompiler.synthetic_candidate.v0.4"
  let encode ~request_fingerprint ~mechanism ~observation_map ~source_map ~behavior_requirement_ids ~component_locks ~generator_config =
    let budget = budget () in
    let skeleton = ["schema_version",str schema_version;"intended_use",str "software_test";
      "human_therapeutic_admission",str "not_admitted";"request_fingerprint",str request_fingerprint;
      "mechanism",Mechanism.to_json mechanism;"observation_map",Observation_map.to_json observation_map;
      "source_map",Json.Object [];"behavior_requirement_ids",Json.Object [];"component_locks",Json.Array [];
      "generator_config",Config.to_json generator_config] in
    ignore (reserve budget (Json.Object skeleton));
    let source_map = name_map budget source_map in
    let behavior_requirement_ids = name_map budget behavior_requirement_ids in
    let component_locks = array budget Lock.to_json component_locks in
    Json.Object (["source_map",source_map;"behavior_requirement_ids",behavior_requirement_ids;"component_locks",component_locks] @
      List.filter (fun (key,_) -> not (List.mem key ["source_map";"behavior_requirement_ids";"component_locks"])) skeleton)
  let of_json ?(path = "") raw =
    let fields = record ~path schema_version ["intended_use";"human_therapeutic_admission";"request_fingerprint";
      "mechanism";"observation_map";"source_map";"behavior_requirement_ids";"component_locks";"generator_config"] raw in
    let get key = field path key fields in
    Diagnostic.require ~path (get "intended_use" = str "software_test" && get "human_therapeutic_admission" = str "not_admitted")
      "unsupported_schema" "Unsupported candidate schema.";
    let raw_locks = Json.array ~path:(path ^ "/component_locks") (get "component_locks") in
    let mechanism = Mechanism.of_json ~path:(path ^ "/mechanism") (get "mechanism") in
    let observation_map = Observation_map.of_json ~path:(path ^ "/observation_map") (get "observation_map") in
    let component_locks = List.mapi (fun index -> Lock.of_json ~path:(path ^ "/component_locks/" ^ string_of_int index)) raw_locks in
    let generator_config = Config.of_json ~path:(path ^ "/generator_config") (get "generator_config") in
    let request_fingerprint = hash ~path:(path ^ "/request_fingerprint") ~label:"Request fingerprint" (get "request_fingerprint") in
    let node_ids = List.fold_left (fun result node -> Names.add (Mechanism.Node.id node) result) Names.empty (Mechanism.nodes mechanism) in
    let correspondence key =
      let values = Json.object_fields ~path:(path ^ "/" ^ key) (get key) in
      let keys = List.fold_left (fun result (key,_) -> Names.add key result) Names.empty values in
      require ~path (Names.equal keys node_ids) (key ^ " must cover every mechanism node exactly once.");
      let values = List.map (fun (ref,raw) -> ref,names ~path:(path ^ "/" ^ key ^ "/" ^ ref) ~label:key raw) values in
      if key = "source_map" then require ~path (List.for_all (fun (_,items) -> items <> []) values)
        "Every mechanism node needs source correspondence.";
      values in
    let source_map = correspondence "source_map" in
    let behavior_requirement_ids = correspondence "behavior_requirement_ids" in
    let component_locks = List.sort (fun a b -> String.compare (Lock.node_id a) (Lock.node_id b)) component_locks in
    let lock_ids = List.fold_left (fun result item -> Names.add (Lock.node_id item) result) Names.empty component_locks in
    require ~path (Names.cardinal lock_ids = List.length component_locks && Names.equal lock_ids node_ids)
      "Component locks must cover every mechanism node exactly once.";
    let json = encode ~request_fingerprint ~mechanism ~observation_map ~source_map ~behavior_requirement_ids ~component_locks ~generator_config in
    let fingerprint,size = finish json in
    {json;fingerprint;size;request_fingerprint;mechanism;observation_map;source_map;behavior_requirement_ids;component_locks;generator_config}
  let make ~request_fingerprint ~mechanism ~observation_map ~source_map ~behavior_requirement_ids ~component_locks ~generator_config =
    of_json (encode ~request_fingerprint ~mechanism ~observation_map ~source_map ~behavior_requirement_ids ~component_locks ~generator_config)
  let to_json value = value.json
  let fingerprint value = value.fingerprint
  let canonical_size value = value.size
  let request_fingerprint value = value.request_fingerprint
  let mechanism value = value.mechanism
  let observation_map value = value.observation_map
  let source_map value = value.source_map
  let behavior_requirement_ids value = value.behavior_requirement_ids
  let component_locks value = value.component_locks
  let generator_config value = value.generator_config
end

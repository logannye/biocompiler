open Bioc_wire
module M = Molecular_record
module D = Architecture_deployment
let max_records = 256
let max_nodes = 4096
let max_match_states = 1_000_000
let require ?path condition message = Diagnostic.require ?path condition "invalid_architecture_contract" message
let str value = Json.String value
let obj value = Json.Object value
let optional encode = function None -> Json.Null | Some value -> encode value
let nullable decode = function Json.Null -> None | value -> Some (decode value)
let array_json maximum encode values =
  ignore (M.bounded_length ~maximum values);
  Json.Array (List.map encode values)
let finish ~path json value = M.check_resources ~path json; value
let choose ~path options value =
  match List.assoc_opt (Json.string ~path value) options with
  | Some value -> value
  | None -> Diagnostic.fail ~path "invalid_architecture_contract" "Unsupported architecture declaration choice."
let limit ~path ~minimum ~maximum value =
  let number = Json.integer ~path value in
  require ~path (Z.compare number (Z.of_int minimum) >= 0 && Z.compare number (Z.of_int maximum) <= 0)
    "Architecture integer declaration exceeds its permitted range.";
  Z.to_int number
let names ~path ~maximum ~nonempty value =
  let values = M.array ~path ~maximum value |> List.map (M.text ~path) in
  require ~path (not nonempty || values <> []) "Architecture inventory must be nonempty.";
  let sorted = List.sort_uniq String.compare values in
  require ~path (List.length values = List.length sorted) "Duplicate architecture inventory identity.";
  sorted
let assumptions ~path value = names ~path ~maximum:64 ~nonempty:true value
let count_limits ~path exact maximum =
  require ~path (match exact, maximum with Some exact, Some maximum -> exact <= maximum | _ -> true)
    "Exact RNA count exceeds its maximum count."
let records ~path decode identity value =
  let values = M.array ~path ~maximum:max_records value
    |> List.mapi (fun index -> decode ~path:(path ^ "/" ^ string_of_int index)) in
  let sorted = List.sort (fun a b -> String.compare (identity a) (identity b)) values in
  let rec distinct = function
    | first :: (second :: _ as rest) ->
        require ~path (identity first <> identity second) "Duplicate architecture record identity."; distinct rest
    | _ -> () in
  distinct sorted; sorted
let mapping ~path value =
  let fields = Json.object_fields ~path value in
  ignore (M.bounded_length ~path ~maximum:max_nodes fields);
  let values = List.map (fun (key, value) ->
      let key = M.text ~path (str key) and value = M.text ~path value in
      Identity.Node.of_string key, Identity.Node.of_string value) fields in
  require ~path (values <> []) "Instances require nonempty source correspondence.";
  let destinations = List.map (fun (_, value) -> Identity.Node.to_string value) values in
  require ~path (List.length destinations = List.length (List.sort_uniq String.compare destinations))
    "Instance source correspondence must be injective.";
  List.sort (fun (a, _) (b, _) -> Identity.Node.compare a b) values
let mapping_json values =
  ignore (M.bounded_length ~maximum:max_nodes values);
  obj (List.map (fun (key, value) -> Identity.Node.to_string key, str (Identity.Node.to_string value)) values)

type control_kind = Activation | Production_adjustment | Activity_control | Memory_reset
  | Shutdown | Physical_separation | Dependency_disjointness
let control_kind_name = function
  | Activation -> "activation" | Production_adjustment -> "production_adjustment"
  | Activity_control -> "activity_control" | Memory_reset -> "memory_reset" | Shutdown -> "shutdown"
  | Physical_separation -> "physical_separation" | Dependency_disjointness -> "dependency_disjointness"
let control_kind_of_json ~path = choose ~path ["activation", Activation; "production_adjustment", Production_adjustment;
    "activity_control", Activity_control; "memory_reset", Memory_reset; "shutdown", Shutdown;
    "physical_separation", Physical_separation; "dependency_disjointness", Dependency_disjointness]

module Binding = struct
  type t = { id : string; behavior_node_ids : Identity.Node.t list; component_ids : Identity.Component.t list; template_ids : string list; placement_ids : string list }
  let schema_version = "biocompiler.architecture_binding.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version;
      "id", (let v = value.id in str v);
      "behavior_node_ids", (let v = value.behavior_node_ids in array_json max_nodes (fun value -> str (Identity.Node.to_string value)) v);
      "component_ids", (let v = value.component_ids in array_json max_nodes (fun value -> str (Identity.Component.to_string value)) v);
      "template_ids", (let v = value.template_ids in array_json max_nodes str v);
      "placement_ids", (let v = value.placement_ids in array_json max_nodes str v)]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "behavior_node_ids"; "component_ids"; "template_ids"; "placement_ids"] raw in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let id = let raw = get "id" and path = path ^ "/id" in M.text ~path raw in
    let behavior_node_ids = let raw = get "behavior_node_ids" and path = path ^ "/behavior_node_ids" in names ~path ~maximum:max_nodes ~nonempty:true raw |> List.map Identity.Node.of_string in
    let component_ids = let raw = get "component_ids" and path = path ^ "/component_ids" in names ~path ~maximum:max_nodes ~nonempty:true raw |> List.map Identity.Component.of_string in
    let template_ids = let raw = get "template_ids" and path = path ^ "/template_ids" in names ~path ~maximum:max_nodes ~nonempty:true raw in
    let placement_ids = let raw = get "placement_ids" and path = path ^ "/placement_ids" in names ~path ~maximum:max_nodes ~nonempty:true raw in
    let value = { id; behavior_node_ids; component_ids; template_ids; placement_ids } in
    finish ~path (to_json value) value
  let make ~id ~behavior_node_ids ~component_ids ~template_ids ~placement_ids =
    of_json (to_json { id; behavior_node_ids; component_ids; template_ids; placement_ids })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let behavior_node_ids (value : t) = value.behavior_node_ids
  let component_ids (value : t) = value.component_ids
  let template_ids (value : t) = value.template_ids
  let placement_ids (value : t) = value.placement_ids
end

module Connection = struct
  type t = { id : string; producer_component_id : Identity.Component.t; producer_port_id : string; consumer_component_id : Identity.Component.t; consumer_port_id : string }
  let schema_version = "biocompiler.architecture_connection.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version;
      "id", (let v = value.id in str v);
      "producer_component_id", (let v = value.producer_component_id in str (Identity.Component.to_string v));
      "producer_port_id", (let v = value.producer_port_id in str v);
      "consumer_component_id", (let v = value.consumer_component_id in str (Identity.Component.to_string v));
      "consumer_port_id", (let v = value.consumer_port_id in str v)]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "producer_component_id"; "producer_port_id"; "consumer_component_id"; "consumer_port_id"] raw in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let id = let raw = get "id" and path = path ^ "/id" in M.text ~path raw in
    let producer_component_id = let raw = get "producer_component_id" and path = path ^ "/producer_component_id" in Identity.Component.of_string (M.text ~path raw) in
    let producer_port_id = let raw = get "producer_port_id" and path = path ^ "/producer_port_id" in M.text ~path raw in
    let consumer_component_id = let raw = get "consumer_component_id" and path = path ^ "/consumer_component_id" in Identity.Component.of_string (M.text ~path raw) in
    let consumer_port_id = let raw = get "consumer_port_id" and path = path ^ "/consumer_port_id" in M.text ~path raw in
    let value = { id; producer_component_id; producer_port_id; consumer_component_id; consumer_port_id } in
    finish ~path (to_json value) value
  let make ~id ~producer_component_id ~producer_port_id ~consumer_component_id ~consumer_port_id =
    of_json (to_json { id; producer_component_id; producer_port_id; consumer_component_id; consumer_port_id })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let producer_component_id (value : t) = value.producer_component_id
  let producer_port_id (value : t) = value.producer_port_id
  let consumer_component_id (value : t) = value.consumer_component_id
  let consumer_port_id (value : t) = value.consumer_port_id
end

module Placement = struct
  type t = { id : string; template_id : string; member_id : string; recipient_role : Identity.Role.t; compartment : string; delivery_group : string }
  let schema_version = "biocompiler.architecture_placement.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version;
      "id", (let v = value.id in str v);
      "template_id", (let v = value.template_id in str v);
      "member_id", (let v = value.member_id in str v);
      "recipient_role", (let v = value.recipient_role in str (Identity.Role.to_string v));
      "compartment", (let v = value.compartment in str v);
      "delivery_group", (let v = value.delivery_group in str v)]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "template_id"; "member_id"; "recipient_role"; "compartment"; "delivery_group"] raw in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let id = let raw = get "id" and path = path ^ "/id" in M.text ~path raw in
    let template_id = let raw = get "template_id" and path = path ^ "/template_id" in M.text ~path raw in
    let member_id = let raw = get "member_id" and path = path ^ "/member_id" in M.text ~path raw in
    let recipient_role = let raw = get "recipient_role" and path = path ^ "/recipient_role" in Identity.Role.of_string (M.text ~path raw) in
    let compartment = let raw = get "compartment" and path = path ^ "/compartment" in M.text ~path raw in
    let delivery_group = let raw = get "delivery_group" and path = path ^ "/delivery_group" in M.text ~path raw in
    let value = { id; template_id; member_id; recipient_role; compartment; delivery_group } in
    finish ~path (to_json value) value
  let make ~id ~template_id ~member_id ~recipient_role ~compartment ~delivery_group =
    of_json (to_json { id; template_id; member_id; recipient_role; compartment; delivery_group })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let template_id (value : t) = value.template_id
  let member_id (value : t) = value.member_id
  let recipient_role (value : t) = value.recipient_role
  let compartment (value : t) = value.compartment
  let delivery_group (value : t) = value.delivery_group
end

module Control = struct
  type t = { id : string; kind : control_kind; behavior_node_ids : Identity.Node.t list; controlling_node_ids : Identity.Node.t list; component_ids : Identity.Component.t list; domain_id : string; assumptions : string list }
  let schema_version = "biocompiler.architecture_control.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version;
      "id", (let v = value.id in str v);
      "kind", (let v = value.kind in str (control_kind_name v));
      "behavior_node_ids", (let v = value.behavior_node_ids in array_json max_nodes (fun value -> str (Identity.Node.to_string value)) v);
      "controlling_node_ids", (let v = value.controlling_node_ids in array_json max_nodes (fun value -> str (Identity.Node.to_string value)) v);
      "component_ids", (let v = value.component_ids in array_json max_nodes (fun value -> str (Identity.Component.to_string value)) v);
      "domain_id", (let v = value.domain_id in str v);
      "assumptions", (let v = value.assumptions in array_json 64 str v)]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "kind"; "behavior_node_ids"; "controlling_node_ids"; "component_ids"; "domain_id"; "assumptions"] raw in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let id = let raw = get "id" and path = path ^ "/id" in M.text ~path raw in
    let kind = let raw = get "kind" and path = path ^ "/kind" in control_kind_of_json ~path raw in
    let behavior_node_ids = let raw = get "behavior_node_ids" and path = path ^ "/behavior_node_ids" in names ~path ~maximum:max_nodes ~nonempty:true raw |> List.map Identity.Node.of_string in
    let controlling_node_ids = let raw = get "controlling_node_ids" and path = path ^ "/controlling_node_ids" in names ~path ~maximum:max_nodes ~nonempty:false raw |> List.map Identity.Node.of_string in
    let component_ids = let raw = get "component_ids" and path = path ^ "/component_ids" in names ~path ~maximum:max_nodes ~nonempty:true raw |> List.map Identity.Component.of_string in
    let domain_id = let raw = get "domain_id" and path = path ^ "/domain_id" in M.text ~path raw in
    let assumptions = let raw = get "assumptions" and path = path ^ "/assumptions" in assumptions ~path raw in
    let value = { id; kind; behavior_node_ids; controlling_node_ids; component_ids; domain_id; assumptions } in
    finish ~path (to_json value) value
  let make ~id ~kind ~behavior_node_ids ~controlling_node_ids ~component_ids ~domain_id ~assumptions =
    of_json (to_json { id; kind; behavior_node_ids; controlling_node_ids; component_ids; domain_id; assumptions })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let kind (value : t) = value.kind
  let behavior_node_ids (value : t) = value.behavior_node_ids
  let controlling_node_ids (value : t) = value.controlling_node_ids
  let component_ids (value : t) = value.component_ids
  let domain_id (value : t) = value.domain_id
  let assumptions (value : t) = value.assumptions
end

module Control_requirement = struct
  type relation = Shared | Independent
  let relation_name = function
    | Shared -> "shared"
    | Independent -> "independent"
  let relation_of_json ~path = choose ~path ["shared", Shared; "independent", Independent]
  type t = { id : string; kind : control_kind; behavior_node_ids : Identity.Node.t list; relation : relation; forbidden_shared_dependencies : string list }
  let schema_version = "biocompiler.architecture_control_requirement.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version;
      "id", (let v = value.id in str v);
      "kind", (let v = value.kind in str (control_kind_name v));
      "behavior_node_ids", (let v = value.behavior_node_ids in array_json max_nodes (fun value -> str (Identity.Node.to_string value)) v);
      "relation", (let v = value.relation in str (relation_name v));
      "forbidden_shared_dependencies", (let v = value.forbidden_shared_dependencies in array_json max_nodes str v)]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "kind"; "behavior_node_ids"; "relation"; "forbidden_shared_dependencies"] raw in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let id = let raw = get "id" and path = path ^ "/id" in M.text ~path raw in
    let kind = let raw = get "kind" and path = path ^ "/kind" in control_kind_of_json ~path raw in
    let behavior_node_ids = let raw = get "behavior_node_ids" and path = path ^ "/behavior_node_ids" in names ~path ~maximum:max_nodes ~nonempty:true raw |> List.map Identity.Node.of_string in
    let relation = let raw = get "relation" and path = path ^ "/relation" in relation_of_json ~path raw in
    let forbidden_shared_dependencies = let raw = get "forbidden_shared_dependencies" and path = path ^ "/forbidden_shared_dependencies" in names ~path ~maximum:max_nodes ~nonempty:false raw in
    let value = { id; kind; behavior_node_ids; relation; forbidden_shared_dependencies } in
    finish ~path (to_json value) value
  let make ~id ~kind ~behavior_node_ids ~relation ~forbidden_shared_dependencies =
    of_json (to_json { id; kind; behavior_node_ids; relation; forbidden_shared_dependencies })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let kind (value : t) = value.kind
  let behavior_node_ids (value : t) = value.behavior_node_ids
  let relation (value : t) = value.relation
  let forbidden_shared_dependencies (value : t) = value.forbidden_shared_dependencies
end

module Helper = struct
  type availability = Same_rna | Other_rna | Host | External
  let availability_name = function
    | Same_rna -> "same_rna"
    | Other_rna -> "other_rna"
    | Host -> "host"
    | External -> "external"
  let availability_of_json ~path = choose ~path ["same_rna", Same_rna; "other_rna", Other_rna; "host", Host; "external", External]
  type initialization = Available_at_start | After_expression | After_trigger
  let initialization_name = function
    | Available_at_start -> "available_at_start"
    | After_expression -> "after_expression"
    | After_trigger -> "after_trigger"
  let initialization_of_json ~path = choose ~path ["available_at_start", Available_at_start; "after_expression", After_expression; "after_trigger", After_trigger]
  type sharing = Exclusive | Shared
  let sharing_name = function
    | Exclusive -> "exclusive"
    | Shared -> "shared"
  let sharing_of_json ~path = choose ~path ["exclusive", Exclusive; "shared", Shared]
  type t = { id : string; capability : string; consumer_component_ids : Identity.Component.t list; recipient_role : Identity.Role.t; compartment : string; availability : availability; initialization : initialization; sharing : sharing; capacity : int; assumptions : string list; placement_id : string option; provider_component_id : Identity.Component.t option; depends_on : string list }
  let schema_version = "biocompiler.architecture_helper.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version;
      "id", (let v = value.id in str v);
      "capability", (let v = value.capability in str v);
      "consumer_component_ids", (let v = value.consumer_component_ids in array_json max_nodes (fun value -> str (Identity.Component.to_string value)) v);
      "recipient_role", (let v = value.recipient_role in str (Identity.Role.to_string v));
      "compartment", (let v = value.compartment in str v);
      "availability", (let v = value.availability in str (availability_name v));
      "initialization", (let v = value.initialization in str (initialization_name v));
      "sharing", (let v = value.sharing in str (sharing_name v));
      "capacity", (let v = value.capacity in Json.int v);
      "assumptions", (let v = value.assumptions in array_json 64 str v);
      "placement_id", (let v = value.placement_id in optional (fun v -> str v) v);
      "provider_component_id", (let v = value.provider_component_id in optional (fun v -> str (Identity.Component.to_string v)) v);
      "depends_on", (let v = value.depends_on in array_json max_nodes str v)]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "capability"; "consumer_component_ids"; "recipient_role"; "compartment"; "availability"; "initialization"; "sharing"; "capacity"; "assumptions"; "placement_id"; "provider_component_id"; "depends_on"] raw in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let id = let raw = get "id" and path = path ^ "/id" in M.text ~path raw in
    let capability = let raw = get "capability" and path = path ^ "/capability" in M.text ~path raw in
    let consumer_component_ids = let raw = get "consumer_component_ids" and path = path ^ "/consumer_component_ids" in names ~path ~maximum:max_nodes ~nonempty:true raw |> List.map Identity.Component.of_string in
    let recipient_role = let raw = get "recipient_role" and path = path ^ "/recipient_role" in Identity.Role.of_string (M.text ~path raw) in
    let compartment = let raw = get "compartment" and path = path ^ "/compartment" in M.text ~path raw in
    let availability = let raw = get "availability" and path = path ^ "/availability" in availability_of_json ~path raw in
    let initialization = let raw = get "initialization" and path = path ^ "/initialization" in initialization_of_json ~path raw in
    let sharing = let raw = get "sharing" and path = path ^ "/sharing" in sharing_of_json ~path raw in
    let capacity = let raw = get "capacity" and path = path ^ "/capacity" in limit ~path ~minimum:1 ~maximum:max_nodes raw in
    let assumptions = let raw = get "assumptions" and path = path ^ "/assumptions" in assumptions ~path raw in
    let placement_id = let raw = get "placement_id" and path = path ^ "/placement_id" in nullable (fun raw -> M.text ~path raw) raw in
    let provider_component_id = let raw = get "provider_component_id" and path = path ^ "/provider_component_id" in nullable (fun raw -> Identity.Component.of_string (M.text ~path raw)) raw in
    let depends_on = let raw = get "depends_on" and path = path ^ "/depends_on" in names ~path ~maximum:max_nodes ~nonempty:false raw in
    let value = { id; capability; consumer_component_ids; recipient_role; compartment; availability; initialization; sharing; capacity; assumptions; placement_id; provider_component_id; depends_on } in
    require ~path (Option.is_some value.placement_id = List.mem value.availability [Same_rna; Other_rna])
      "Encoded helpers require a placement; host/external helpers cannot claim one.";
    finish ~path (to_json value) value
  let make ~id ~capability ~consumer_component_ids ~recipient_role ~compartment ~availability ~initialization ~sharing ~capacity ~assumptions ~placement_id ~provider_component_id ~depends_on =
    of_json (to_json { id; capability; consumer_component_ids; recipient_role; compartment; availability; initialization; sharing; capacity; assumptions; placement_id; provider_component_id; depends_on })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let capability (value : t) = value.capability
  let consumer_component_ids (value : t) = value.consumer_component_ids
  let recipient_role (value : t) = value.recipient_role
  let compartment (value : t) = value.compartment
  let availability (value : t) = value.availability
  let initialization (value : t) = value.initialization
  let sharing (value : t) = value.sharing
  let capacity (value : t) = value.capacity
  let assumptions (value : t) = value.assumptions
  let placement_id (value : t) = value.placement_id
  let provider_component_id (value : t) = value.provider_component_id
  let depends_on (value : t) = value.depends_on
end

module Channel = struct
  type failure_mode = Retain_last | Clear | Unknown
  let failure_mode_name = function
    | Retain_last -> "retain_last"
    | Clear -> "clear"
    | Unknown -> "unknown"
  let failure_mode_of_json ~path = choose ~path ["retain_last", Retain_last; "clear", Clear; "unknown", Unknown]
  type aggregation = Single_sender | Sum | Max
  let aggregation_name = function
    | Single_sender -> "single_sender"
    | Sum -> "sum"
    | Max -> "max"
  let aggregation_of_json ~path = choose ~path ["single_sender", Single_sender; "sum", Sum; "max", Max]
  type t = { id : string; source_channel_id : Identity.Node.t; sender_role : Identity.Role.t; receiver_role : Identity.Role.t; sender_node_id : Identity.Node.t; receiver_node_id : Identity.Node.t; latency_seconds : Architecture_deployment.Time.t; persistence_seconds : Architecture_deployment.Time.t option; failure_mode : failure_mode; aggregation : aggregation; initial_value : Json.t; assumptions : string list }
  let schema_version = "biocompiler.architecture_channel.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version;
      "id", (let v = value.id in str v);
      "source_channel_id", (let v = value.source_channel_id in str (Identity.Node.to_string v));
      "sender_role", (let v = value.sender_role in str (Identity.Role.to_string v));
      "receiver_role", (let v = value.receiver_role in str (Identity.Role.to_string v));
      "sender_node_id", (let v = value.sender_node_id in str (Identity.Node.to_string v));
      "receiver_node_id", (let v = value.receiver_node_id in str (Identity.Node.to_string v));
      "latency_seconds", (let v = value.latency_seconds in D.Time.to_json v);
      "persistence_seconds", (let v = value.persistence_seconds in optional D.Time.to_json v);
      "failure_mode", (let v = value.failure_mode in str (failure_mode_name v));
      "aggregation", (let v = value.aggregation in str (aggregation_name v));
      "initial_value", (let v = value.initial_value in v);
      "assumptions", (let v = value.assumptions in array_json 64 str v)]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "source_channel_id"; "sender_role"; "receiver_role"; "sender_node_id"; "receiver_node_id"; "latency_seconds"; "persistence_seconds"; "failure_mode"; "aggregation"; "initial_value"; "assumptions"] raw in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let id = let raw = get "id" and path = path ^ "/id" in M.text ~path raw in
    let source_channel_id = let raw = get "source_channel_id" and path = path ^ "/source_channel_id" in Identity.Node.of_string (M.text ~path raw) in
    let sender_role = let raw = get "sender_role" and path = path ^ "/sender_role" in Identity.Role.of_string (M.text ~path raw) in
    let receiver_role = let raw = get "receiver_role" and path = path ^ "/receiver_role" in Identity.Role.of_string (M.text ~path raw) in
    let sender_node_id = let raw = get "sender_node_id" and path = path ^ "/sender_node_id" in Identity.Node.of_string (M.text ~path raw) in
    let receiver_node_id = let raw = get "receiver_node_id" and path = path ^ "/receiver_node_id" in Identity.Node.of_string (M.text ~path raw) in
    let latency_seconds = let raw = get "latency_seconds" and path = path ^ "/latency_seconds" in D.Time.of_json ~path raw in
    let persistence_seconds = let raw = get "persistence_seconds" and path = path ^ "/persistence_seconds" in nullable (D.Time.of_json ~path) raw in
    let failure_mode = let raw = get "failure_mode" and path = path ^ "/failure_mode" in failure_mode_of_json ~path raw in
    let aggregation = let raw = get "aggregation" and path = path ^ "/aggregation" in aggregation_of_json ~path raw in
    let initial_value = get "initial_value" in
    let assumptions = let raw = get "assumptions" and path = path ^ "/assumptions" in assumptions ~path raw in
    let value = { id; source_channel_id; sender_role; receiver_role; sender_node_id; receiver_node_id; latency_seconds; persistence_seconds; failure_mode; aggregation; initial_value; assumptions } in
    require ~path (Identity.Role.compare value.sender_role value.receiver_role <> 0)
      "Architecture transport must cross recipient roles.";
    finish ~path (to_json value) value
  let make ~id ~source_channel_id ~sender_role ~receiver_role ~sender_node_id ~receiver_node_id ~latency_seconds ~persistence_seconds ~failure_mode ~aggregation ~initial_value ~assumptions =
    M.bounded_tree initial_value;
    of_json (to_json { id; source_channel_id; sender_role; receiver_role; sender_node_id; receiver_node_id; latency_seconds; persistence_seconds; failure_mode; aggregation; initial_value; assumptions })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let source_channel_id (value : t) = value.source_channel_id
  let sender_role (value : t) = value.sender_role
  let receiver_role (value : t) = value.receiver_role
  let sender_node_id (value : t) = value.sender_node_id
  let receiver_node_id (value : t) = value.receiver_node_id
  let latency_seconds (value : t) = value.latency_seconds
  let persistence_seconds (value : t) = value.persistence_seconds
  let failure_mode (value : t) = value.failure_mode
  let aggregation (value : t) = value.aggregation
  let initial_value (value : t) = value.initial_value
  let assumptions (value : t) = value.assumptions
end

module Output_binding = struct
  type t = { id : string; requirement_id : Identity.Requirement.t; action_ids : Identity.Node.t list; product : Circuit_request.Product.t; lifecycle : Circuit_request.Lifecycle.t }
  let schema_version = "biocompiler.architecture_output_binding.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version;
      "id", (let v = value.id in str v);
      "requirement_id", (let v = value.requirement_id in str (Identity.Requirement.to_string v));
      "action_ids", (let v = value.action_ids in array_json max_nodes (fun value -> str (Identity.Node.to_string value)) v);
      "product", (let v = value.product in Circuit_request.Product.to_json v);
      "lifecycle", (let v = value.lifecycle in Circuit_request.Lifecycle.to_json v)]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "requirement_id"; "action_ids"; "product"; "lifecycle"] raw in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let id = let raw = get "id" and path = path ^ "/id" in M.text ~path raw in
    let requirement_id = let raw = get "requirement_id" and path = path ^ "/requirement_id" in Identity.Requirement.of_string (M.text ~path raw) in
    let action_ids = let raw = get "action_ids" and path = path ^ "/action_ids" in names ~path ~maximum:max_nodes ~nonempty:true raw |> List.map Identity.Node.of_string in
    let product = let raw = get "product" and path = path ^ "/product" in Circuit_request.Product.of_json ~path raw in
    let lifecycle = let raw = get "lifecycle" and path = path ^ "/lifecycle" in Circuit_request.Lifecycle.of_json ~path raw in
    let value = { id; requirement_id; action_ids; product; lifecycle } in
    finish ~path (to_json value) value
  let make ~id ~requirement_id ~action_ids ~product ~lifecycle =
    of_json (to_json { id; requirement_id; action_ids; product; lifecycle })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let requirement_id (value : t) = value.requirement_id
  let action_ids (value : t) = value.action_ids
  let product (value : t) = value.product
  let lifecycle (value : t) = value.lifecycle
end

module Delivery_group = struct
  type mode = Co_delivered | Independent
  let mode_name = function
    | Co_delivered -> "co_delivered"
    | Independent -> "independent"
  let mode_of_json ~path = choose ~path ["co_delivered", Co_delivered; "independent", Independent]
  type t = { id : string; recipient_roles : Identity.Role.t list; mode : mode; same_recipient : bool; assumptions : string list; exact_count : int option; max_count : int option; max_total_bases : int option }
  let schema_version = "biocompiler.recipient_delivery_group.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version;
      "id", (let v = value.id in str v);
      "recipient_roles", (let v = value.recipient_roles in array_json max_nodes (fun value -> str (Identity.Role.to_string value)) v);
      "mode", (let v = value.mode in str (mode_name v));
      "same_recipient", (let v = value.same_recipient in Json.Bool v);
      "assumptions", (let v = value.assumptions in array_json 64 str v);
      "exact_count", (let v = value.exact_count in optional Json.int v);
      "max_count", (let v = value.max_count in optional Json.int v);
      "max_total_bases", (let v = value.max_total_bases in optional Json.int v)]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "recipient_roles"; "mode"; "same_recipient"; "assumptions"; "exact_count"; "max_count"; "max_total_bases"] raw in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let id = let raw = get "id" and path = path ^ "/id" in M.text ~path raw in
    let recipient_roles = let raw = get "recipient_roles" and path = path ^ "/recipient_roles" in names ~path ~maximum:max_nodes ~nonempty:true raw |> List.map Identity.Role.of_string in
    let mode = let raw = get "mode" and path = path ^ "/mode" in mode_of_json ~path raw in
    let same_recipient = let raw = get "same_recipient" and path = path ^ "/same_recipient" in Json.boolean ~path raw in
    let assumptions = let raw = get "assumptions" and path = path ^ "/assumptions" in assumptions ~path raw in
    let exact_count = let raw = get "exact_count" and path = path ^ "/exact_count" in nullable (limit ~path ~minimum:0 ~maximum:max_nodes) raw in
    let max_count = let raw = get "max_count" and path = path ^ "/max_count" in nullable (limit ~path ~minimum:0 ~maximum:max_nodes) raw in
    let max_total_bases = let raw = get "max_total_bases" and path = path ^ "/max_total_bases" in nullable (limit ~path ~minimum:0 ~maximum:M.max_residues) raw in
    let value = { id; recipient_roles; mode; same_recipient; assumptions; exact_count; max_count; max_total_bases } in
    count_limits ~path value.exact_count value.max_count;
    finish ~path (to_json value) value
  let make ~id ~recipient_roles ~mode ~same_recipient ~assumptions ~exact_count ~max_count ~max_total_bases =
    of_json (to_json { id; recipient_roles; mode; same_recipient; assumptions; exact_count; max_count; max_total_bases })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let recipient_roles (value : t) = value.recipient_roles
  let mode (value : t) = value.mode
  let same_recipient (value : t) = value.same_recipient
  let assumptions (value : t) = value.assumptions
  let exact_count (value : t) = value.exact_count
  let max_count (value : t) = value.max_count
  let max_total_bases (value : t) = value.max_total_bases
end

module Constraints = struct
  type t = { exact_count : int option; max_count : int option; max_member_bases : int option; max_total_bases : int option; delivery_groups : Delivery_group.t list; control_requirements : Control_requirement.t list; preferred_refinement_ids : string list; max_combinations : int; require_complete : bool; max_match_states : int; max_match_instances : int; deployment_requirements : Architecture_deployment.Requirement.t list }
  let schema_version = "biocompiler.rna_architecture_constraints.v0.2"
  let to_json (value : t) = obj ["schema_version", str schema_version;
      "exact_count", (let v = value.exact_count in optional Json.int v);
      "max_count", (let v = value.max_count in optional Json.int v);
      "max_member_bases", (let v = value.max_member_bases in optional Json.int v);
      "max_total_bases", (let v = value.max_total_bases in optional Json.int v);
      "delivery_groups", (let v = value.delivery_groups in array_json max_records Delivery_group.to_json v);
      "control_requirements", (let v = value.control_requirements in array_json max_records Control_requirement.to_json v);
      "preferred_refinement_ids", (let v = value.preferred_refinement_ids in array_json max_records str v);
      "max_combinations", (let v = value.max_combinations in Json.int v);
      "require_complete", (let v = value.require_complete in Json.Bool v);
      "max_match_states", (let v = value.max_match_states in Json.int v);
      "max_match_instances", (let v = value.max_match_instances in Json.int v);
      "deployment_requirements", (let v = value.deployment_requirements in array_json max_records D.Requirement.to_json v)]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["exact_count"; "max_count"; "max_member_bases"; "max_total_bases"; "delivery_groups"; "control_requirements"; "preferred_refinement_ids"; "max_combinations"; "require_complete"; "max_match_states"; "max_match_instances"; "deployment_requirements"] raw in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let exact_count = let raw = get "exact_count" and path = path ^ "/exact_count" in nullable (limit ~path ~minimum:0 ~maximum:max_nodes) raw in
    let max_count = let raw = get "max_count" and path = path ^ "/max_count" in nullable (limit ~path ~minimum:0 ~maximum:max_nodes) raw in
    let max_member_bases = let raw = get "max_member_bases" and path = path ^ "/max_member_bases" in nullable (limit ~path ~minimum:0 ~maximum:M.max_residues) raw in
    let max_total_bases = let raw = get "max_total_bases" and path = path ^ "/max_total_bases" in nullable (limit ~path ~minimum:0 ~maximum:M.max_residues) raw in
    let delivery_groups = let raw = get "delivery_groups" and path = path ^ "/delivery_groups" in records ~path (fun ~path raw -> Delivery_group.of_json ~path raw) Delivery_group.id raw in
    let control_requirements = let raw = get "control_requirements" and path = path ^ "/control_requirements" in records ~path (fun ~path raw -> Control_requirement.of_json ~path raw) Control_requirement.id raw in
    let preferred_refinement_ids = let raw = get "preferred_refinement_ids" and path = path ^ "/preferred_refinement_ids" in names ~path ~maximum:max_records ~nonempty:false raw in
    let max_combinations = let raw = get "max_combinations" and path = path ^ "/max_combinations" in limit ~path ~minimum:1 ~maximum:max_nodes raw in
    let require_complete = let raw = get "require_complete" and path = path ^ "/require_complete" in Json.boolean ~path raw in
    let max_match_states = let raw = get "max_match_states" and path = path ^ "/max_match_states" in limit ~path ~minimum:1 ~maximum:max_match_states raw in
    let max_match_instances = let raw = get "max_match_instances" and path = path ^ "/max_match_instances" in limit ~path ~minimum:1 ~maximum:max_records raw in
    let deployment_requirements = let raw = get "deployment_requirements" and path = path ^ "/deployment_requirements" in records ~path (fun ~path raw -> D.Requirement.of_json ~path raw) D.Requirement.id raw in
    let value = { exact_count; max_count; max_member_bases; max_total_bases; delivery_groups; control_requirements; preferred_refinement_ids; max_combinations; require_complete; max_match_states; max_match_instances; deployment_requirements } in
    count_limits ~path value.exact_count value.max_count;
    finish ~path (to_json value) value
  let make ~exact_count ~max_count ~max_member_bases ~max_total_bases ~delivery_groups ~control_requirements ~preferred_refinement_ids ~max_combinations ~require_complete ~max_match_states ~max_match_instances ~deployment_requirements =
    of_json (to_json { exact_count; max_count; max_member_bases; max_total_bases; delivery_groups; control_requirements; preferred_refinement_ids; max_combinations; require_complete; max_match_states; max_match_instances; deployment_requirements })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let exact_count (value : t) = value.exact_count
  let max_count (value : t) = value.max_count
  let max_member_bases (value : t) = value.max_member_bases
  let max_total_bases (value : t) = value.max_total_bases
  let delivery_groups (value : t) = value.delivery_groups
  let control_requirements (value : t) = value.control_requirements
  let preferred_refinement_ids (value : t) = value.preferred_refinement_ids
  let max_combinations (value : t) = value.max_combinations
  let require_complete (value : t) = value.require_complete
  let max_match_states (value : t) = value.max_match_states
  let max_match_instances (value : t) = value.max_match_instances
  let deployment_requirements (value : t) = value.deployment_requirements
end

module Match_policy = struct
  type mode = Exact_semantic_subgraph
  let mode_name = function
    | Exact_semantic_subgraph -> "exact_semantic_subgraph"
  let mode_of_json ~path = choose ~path ["exact_semantic_subgraph", Exact_semantic_subgraph]
  type t = { mode : mode }
  let schema_version = "biocompiler.architecture_match_policy.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version;
      "mode", (let v = value.mode in str (mode_name v))]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["mode"] raw in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let mode = let raw = get "mode" and path = path ^ "/mode" in mode_of_json ~path raw in
    let value = { mode } in
    finish ~path (to_json value) value
  let make ~mode =
    of_json (to_json { mode })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let mode (value : t) = value.mode
end

module Instance = struct
  type t = { id : string; refinement_id : string; source_bindings : (Identity.Node.t * Identity.Node.t) list }
  let schema_version = "biocompiler.architecture_refinement_instance.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version;
      "id", (let v = value.id in str v);
      "refinement_id", (let v = value.refinement_id in str v);
      "source_bindings", (let v = value.source_bindings in mapping_json v)]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "refinement_id"; "source_bindings"] raw in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let id = let raw = get "id" and path = path ^ "/id" in M.text ~path raw in
    let refinement_id = let raw = get "refinement_id" and path = path ^ "/refinement_id" in M.text ~path raw in
    let source_bindings = let raw = get "source_bindings" and path = path ^ "/source_bindings" in mapping ~path raw in
    let value = { id; refinement_id; source_bindings } in
    finish ~path (to_json value) value
  let make ~id ~refinement_id ~source_bindings =
    of_json (to_json { id; refinement_id; source_bindings })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let refinement_id (value : t) = value.refinement_id
  let source_bindings (value : t) = value.source_bindings
end

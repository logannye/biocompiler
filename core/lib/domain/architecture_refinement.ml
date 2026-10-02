open Bioc_wire
module A = Architecture_contract
module M = Molecular_record
module C = Construction
module P = Component_contract.Port
module D = Architecture_deployment.Availability
module Names = Map.Make (String)
module Ids = Set.Make (String)
module Pairs = Set.Make (struct type t = string * string let compare = Stdlib.compare end)
module Triples = Set.Make (struct type t = string * string * string let compare = Stdlib.compare end)
let code = "invalid_architecture_refinement"
let require ?path condition message = Diagnostic.require ?path condition code message
let str value = Json.String value
let array encode values = Json.Array (List.map encode values)
let optional encode = function None -> Json.Null | Some value -> encode value
let option decode = function Json.Null -> None | value -> Some (decode value)
let node_name = Identity.Node.to_string
let role_name = Identity.Role.to_string
let component_name = Identity.Component.to_string
let strings values = array str values
let set values = List.fold_left (fun result value -> Ids.add value result) Ids.empty values
let sorted ?(code = code) ~path ?(nonempty = false) key values =
  Diagnostic.require ~path (not nonempty || values <> []) code "Required architecture inventory is empty.";
  let sorted = List.sort (fun left right -> String.compare (key left) (key right)) values in
  let rec unique = function first :: (second :: _ as rest) ->
      Diagnostic.require ~path (key first <> key second) code "Duplicate architecture inventory identity."; unique rest
    | _ -> () in
  unique sorted; sorted
let names ?(code = code) ~path ~maximum ~nonempty raw =
  M.array ~path ~maximum raw |> List.map (M.text ~path) |> sorted ~code ~path ~nonempty Fun.id
let records ?(code = code) ~path ~nonempty (decode : ?path:string -> Json.t -> 'a) key raw =
  M.array ~path ~maximum:A.max_records raw
  |> List.mapi (fun index -> decode ~path:(path ^ "/" ^ string_of_int index))
  |> sorted ~code ~path ~nonempty key
let mapping ~path raw =
  let fields = Json.object_fields ~path raw in
  ignore (M.bounded_length ~path ~maximum:A.max_nodes fields);
  let values = List.map (fun (key,value) ->
      Identity.Node.of_string (M.text ~path (str key)), Identity.Node.of_string (M.text ~path value)) fields in
  let targets = List.map (fun (_,value) -> node_name value) values in
  require ~path (List.length targets = Ids.cardinal (set targets)) "Source correspondence must be injective.";
  List.sort (fun (left,_) (right,_) -> Identity.Node.compare left right) values
let mapping_json values = Json.Object (List.map (fun (key,value) -> node_name key,str (node_name value)) values)
(* Reserve each already checked child before retaining an expanded parent. *)
let budget () = ref 1,ref 2
let reserve (nodes,bytes) raw =
  bytes := !bytes + M.pretty_size raw;
  Diagnostic.require (!bytes <= M.max_json_bytes) "molecular_resource_limit" "Architecture children exceed aggregate publication budget.";
  let pending = ref [raw] in
  while !pending <> [] do
    let raw = List.hd !pending in pending := List.tl !pending; incr nodes;
    Diagnostic.require (!nodes <= M.max_items) "molecular_resource_limit" "Architecture children exceed aggregate item budget.";
    match raw with
    | Json.Object fields -> nodes := !nodes + List.length fields; pending := List.rev_append (List.map snd fields) !pending
    | Json.Array values -> pending := List.rev_append values !pending
    | _ -> ()
  done
let reserve_children budget encode values = List.iter (fun value -> reserve budget (encode value)) values
type t = {
  id:string; version:string; behavior:Behavior.t;
  source_bindings:(Identity.Node.t * Identity.Node.t) list;
  owned_node_ids:Identity.Node.t list; components:Component.t list;
  templates:Payload_template.t list; bindings:A.Binding.t list;
  placements:A.Placement.t list; assumptions:string list;
  connections:A.Connection.t list; controls:A.Control.t list; helpers:A.Helper.t list;
  channels:A.Channel.t list; output_contracts:A.Output_binding.t list;
  match_policy:A.Match_policy.t option; availability:D.t list;
}
let schema_version = "biocompiler.payload_architecture_refinement.v0.2"
let to_json (value : t) = Json.Object ["schema_version",str schema_version; "id",str value.id; "version",str value.version;
    "behavior",Behavior.to_json value.behavior; "source_bindings",mapping_json value.source_bindings;
    "owned_node_ids",array (fun value -> str (node_name value)) value.owned_node_ids;
    "components",array Component.to_json value.components; "templates",array Payload_template.to_json value.templates;
    "bindings",array A.Binding.to_json value.bindings; "placements",array A.Placement.to_json value.placements;
    "assumptions",strings value.assumptions; "connections",array A.Connection.to_json value.connections;
    "controls",array A.Control.to_json value.controls; "helpers",array A.Helper.to_json value.helpers;
    "channels",array A.Channel.to_json value.channels; "output_contracts",array A.Output_binding.to_json value.output_contracts;
    "match_policy",optional A.Match_policy.to_json value.match_policy; "availability",array D.to_json value.availability]
let validate ~path value =
  let nodes = List.fold_left (fun result node -> Names.add (node_name (Behavior.node_id node)) node result) Names.empty (Behavior.nodes value.behavior) in
  let node_ids = Names.fold (fun key _ result -> Ids.add key result) nodes Ids.empty in
  require ~path (Names.cardinal nodes > 0 && Names.cardinal nodes <= A.max_nodes) "Invalid refinement graph size.";
  let anchors = set (List.map (fun (key,_) -> node_name key) value.source_bindings) in
  (match value.match_policy with
   | None -> require ~path (Ids.equal anchors node_ids) "Every model node needs exact source correspondence."
   | Some _ ->
       ignore (M.text ~path ~maximum:4000 (str value.id));
       require ~path (Ids.subset anchors node_ids) "Source anchor refers to an absent model node.");
  require ~path (Ids.subset (set (List.map node_name value.owned_node_ids)) node_ids) "Owned node is absent from the supplied model.";
  let components = List.fold_left (fun result item -> Names.add (Component.id item) item result) Names.empty value.components in
  let component_ids = Names.fold (fun key _ result -> Ids.add key result) components Ids.empty in
  let placement_ids = set (List.map A.Placement.id value.placements) in
  List.iter (fun item -> require ~path (Ids.mem (D.placement_id item) placement_ids) "Availability contract references an absent placement.") value.availability;
  require ~path (List.length value.availability = Ids.cardinal (set (List.map D.placement_id value.availability)))
    "Every placement can have only one supplied availability contract.";
  let destinations = ref Pairs.empty in
  List.iter (fun connection ->
      let find_port component port = match Names.find_opt (component_name component) components with
        | None -> Diagnostic.fail ~path code "Connection references absent component."
        | Some value -> (match Component.port value port with Some port -> port
            | None -> Diagnostic.fail ~path code "Connection references absent port.") in
      let producer = find_port (A.Connection.producer_component_id connection) (A.Connection.producer_port_id connection)
      and consumer = find_port (A.Connection.consumer_component_id connection) (A.Connection.consumer_port_id connection) in
      require ~path (P.direction producer = P.Output && P.direction consumer = P.Input) "Connection must join a producer output to a consumer input.";
      let destination = component_name (A.Connection.consumer_component_id connection),A.Connection.consumer_port_id connection in
      require ~path (not (Pairs.mem destination !destinations)) "A constituent input cannot have multiple drivers.";
      destinations := Pairs.add destination !destinations) value.connections;
  let templates = set (List.map Payload_template.id value.templates) in
  let owned = ref Ids.empty and bound_components = ref Ids.empty and bound_templates = ref Ids.empty in
  List.iter (fun binding ->
      let behavior_ids = set (List.map node_name (A.Binding.behavior_node_ids binding))
      and component_refs = set (List.map component_name (A.Binding.component_ids binding))
      and template_refs = set (A.Binding.template_ids binding) in
      require ~path (Ids.subset behavior_ids node_ids) "Material binding references absent model nodes.";
      require ~path (Ids.subset component_refs component_ids) "Material binding references absent components.";
      require ~path (Ids.subset template_refs templates) "Material binding references absent templates.";
      owned := Ids.union behavior_ids !owned; bound_components := Ids.union component_refs !bound_components;
      bound_templates := Ids.union template_refs !bound_templates) value.bindings;
  require ~path (Ids.subset (set (List.map node_name value.owned_node_ids)) !owned) "Every owned behavior node needs material correspondence.";
  require ~path (Ids.equal !bound_components component_ids && Ids.equal !bound_templates templates)
    "Every supplied component and template needs explicit material correspondence.";
  let members = List.fold_left (fun members template ->
      let identities = List.map C.Output_member.id (Payload_template.output_members template)
        @ List.map C.Complex_member.id (Payload_template.complex_members template) in
      List.fold_left (fun result identity -> Pairs.add (Payload_template.id template,identity) result) members identities)
      Pairs.empty value.templates in
  let placed = ref Pairs.empty and placement_keys = ref Triples.empty in
  let node_is identity expected = match Names.find_opt identity nodes with
    | None -> false | Some node -> Behavior.kind_name (Behavior.operation node) = expected in
  List.iter (fun placement ->
      let key = A.Placement.template_id placement,A.Placement.member_id placement in
      require ~path (Pairs.mem key members) "Placement references an absent member.";
      let recipient = role_name (A.Placement.recipient_role placement) in
      require ~path (node_is recipient "role") "Placement recipient must name a local model role.";
      let triple = fst key,snd key,recipient in
      require ~path (not (Triples.mem triple !placement_keys)) "Duplicate member placement in the same recipient role.";
      placement_keys := Triples.add triple !placement_keys; placed := Pairs.add key !placed) value.placements;
  require ~path (Pairs.equal !placed members) "Every emitted member needs an explicit recipient placement.";
  let placements = List.fold_left (fun result value -> Names.add (A.Placement.id value) value result) Names.empty value.placements in
  List.iter (fun binding -> List.iter (fun identity ->
      require ~path (match Names.find_opt identity placements with
        | Some placement -> List.mem (A.Placement.template_id placement) (A.Binding.template_ids binding) | None -> false)
        "Binding placements must exist within its supplied templates.") (A.Binding.placement_ids binding)) value.bindings;
  let helper_ids = set (List.map A.Helper.id value.helpers) in
  List.iter (fun control ->
      require ~path (List.for_all (fun identity -> Ids.mem (node_name identity) node_ids)
          (A.Control.behavior_node_ids control @ A.Control.controlling_node_ids control)
        && List.for_all (fun identity -> Ids.mem (component_name identity) component_ids) (A.Control.component_ids control))
        "Control references absent model or component authority.") value.controls;
  List.iter (fun helper ->
      require ~path (node_is (role_name (A.Helper.recipient_role helper)) "role") "Helper recipient must name a local model role.";
      require ~path (List.for_all (fun identity -> Ids.mem (component_name identity) component_ids) (A.Helper.consumer_component_ids helper)
        && Option.fold ~none:true ~some:(fun identity -> Ids.mem (component_name identity) component_ids) (A.Helper.provider_component_id helper))
        "Helper references absent components.";
      require ~path (Option.fold ~none:true ~some:(fun identity -> Names.mem identity placements) (A.Helper.placement_id helper))
        "Helper references an absent material placement.";
      require ~path (List.for_all (fun identity -> Ids.mem identity helper_ids) (A.Helper.depends_on helper))
        "Helper prerequisite is absent from the refinement.") value.helpers;
  List.iter (fun channel ->
      require ~path (node_is (role_name (A.Channel.sender_role channel)) "role" && node_is (role_name (A.Channel.receiver_role channel)) "role")
        "Channel recipients must name local model roles.";
      require ~path (node_is (node_name (A.Channel.source_channel_id channel)) "channel") "Channel source must name a local model channel.";
      require ~path (Ids.mem (node_name (A.Channel.sender_node_id channel)) node_ids && Ids.mem (node_name (A.Channel.receiver_node_id channel)) node_ids)
        "Channel boundary references absent model nodes.") value.channels;
  List.iter (fun output -> List.iter (fun identity ->
      require ~path (match Names.find_opt (node_name identity) nodes with
        | None -> false | Some node -> String.starts_with ~prefix:"action." (Behavior.kind_name (Behavior.operation node)))
        "Output binding requires present action nodes.") (A.Output_binding.action_ids output)) value.output_contracts;
  require ~path (List.length value.output_contracts = Ids.cardinal (set (List.map (fun item -> Identity.Requirement.to_string (A.Output_binding.requirement_id item)) value.output_contracts)))
    "Supplementary output requirements can be bound only once per refinement."
let of_json ?(path = "") raw =
  let fields = M.record ~path schema_version ["id";"version";"behavior";"source_bindings";"owned_node_ids";"components";"templates";"bindings";"placements";"assumptions";"connections";"controls";"helpers";"channels";"output_contracts";"match_policy";"availability"] raw in
  let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
  let behavior = Behavior.of_json (get "behavior") in
  let source_bindings = mapping ~path:(path ^ "/source_bindings") (get "source_bindings") in
  let owned_node_ids = names ~path:(path ^ "/owned_node_ids") ~maximum:A.max_nodes ~nonempty:true (get "owned_node_ids") |> List.map Identity.Node.of_string in
  let components = records ~path:(path ^ "/components") ~nonempty:true Component.of_json Component.id (get "components")
  and templates = records ~path:(path ^ "/templates") ~nonempty:true Payload_template.of_json Payload_template.id (get "templates")
  and bindings = records ~path:(path ^ "/bindings") ~nonempty:true A.Binding.of_json A.Binding.id (get "bindings")
  and placements = records ~path:(path ^ "/placements") ~nonempty:true A.Placement.of_json A.Placement.id (get "placements")
  and connections = records ~path:(path ^ "/connections") ~nonempty:false A.Connection.of_json A.Connection.id (get "connections")
  and controls = records ~path:(path ^ "/controls") ~nonempty:false A.Control.of_json A.Control.id (get "controls")
  and helpers = records ~path:(path ^ "/helpers") ~nonempty:false A.Helper.of_json A.Helper.id (get "helpers")
  and channels = records ~path:(path ^ "/channels") ~nonempty:false A.Channel.of_json A.Channel.id (get "channels")
  and output_contracts = records ~path:(path ^ "/output_contracts") ~nonempty:false A.Output_binding.of_json A.Output_binding.id (get "output_contracts")
  and availability = records ~path:(path ^ "/availability") ~nonempty:false D.of_json D.id (get "availability") in
  let assumptions = names ~path:(path ^ "/assumptions") ~maximum:64 ~nonempty:true (get "assumptions") in
  let match_policy = option (A.Match_policy.of_json ~path:(path ^ "/match_policy")) (get "match_policy") in
  let value = {id=M.text ~path (get "id");version=M.text ~path (get "version");behavior;source_bindings;owned_node_ids;components;templates;bindings;placements;assumptions;connections;controls;helpers;channels;output_contracts;match_policy;availability} in
  validate ~path value; M.check_resources ~path (to_json value); value
let make ?(connections = []) ?(controls = []) ?(helpers = []) ?(channels = []) ?(output_contracts = []) ?match_policy ?(availability = [])
    ~id ~version ~behavior ~source_bindings ~owned_node_ids ~components ~templates ~bindings ~placements ~assumptions () =
  ignore (M.bounded_length ~maximum:A.max_nodes (Behavior.nodes behavior));
  ignore (M.bounded_length ~maximum:A.max_nodes source_bindings); ignore (M.bounded_length ~maximum:A.max_nodes owned_node_ids);
  ignore (M.bounded_length ~maximum:64 assumptions);
  let preflight (budget : int ref * int ref) encode values =
    ignore (M.bounded_length ~maximum:A.max_records values); reserve_children budget encode values in
  let budget = budget () in
  reserve budget (Behavior.to_json behavior); reserve budget (mapping_json source_bindings);
  reserve budget (array (fun value -> str (node_name value)) owned_node_ids); reserve budget (strings assumptions);
  preflight budget Component.to_json components; preflight budget Payload_template.to_json templates;
  preflight budget A.Binding.to_json bindings; preflight budget A.Placement.to_json placements;
  preflight budget A.Connection.to_json connections; preflight budget A.Control.to_json controls;
  preflight budget A.Helper.to_json helpers; preflight budget A.Channel.to_json channels;
  preflight budget A.Output_binding.to_json output_contracts; preflight budget D.to_json availability;
  of_json (to_json {id;version;behavior;source_bindings;owned_node_ids;components;templates;bindings;placements;assumptions;connections;controls;helpers;channels;output_contracts;match_policy;availability})
let fingerprint value = Canonical.fingerprint (to_json value)
let id (value : t) = value.id
let version (value : t) = value.version
let behavior (value : t) = value.behavior
let source_bindings (value : t) = value.source_bindings
let owned_node_ids (value : t) = value.owned_node_ids
let components (value : t) = value.components
let templates (value : t) = value.templates
let bindings (value : t) = value.bindings
let placements (value : t) = value.placements
let assumptions (value : t) = value.assumptions
let connections (value : t) = value.connections
let controls (value : t) = value.controls
let helpers (value : t) = value.helpers
let channels (value : t) = value.channels
let output_contracts (value : t) = value.output_contracts
let match_policy (value : t) = value.match_policy
let availability (value : t) = value.availability
module Library = struct
  type refinement = t
  let refinement_json = to_json
  let refinement_of_json = of_json
  let refinement_id = id
  type t = {id:string; refinements:refinement list; assumptions:string list}
  let schema_version = "biocompiler.payload_architecture_library.v0.1"
  let code = "invalid_architecture_library"
  let to_json (value : t) = Json.Object ["schema_version",str schema_version;"id",str value.id;
      "refinements",array refinement_json value.refinements;"assumptions",strings value.assumptions]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id";"refinements";"assumptions"] raw in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let refinements = records ~code ~path:(path ^ "/refinements") ~nonempty:false refinement_of_json refinement_id (get "refinements") in
    let assumptions = names ~code ~path:(path ^ "/assumptions") ~maximum:64 ~nonempty:false (get "assumptions") in
    let meanings = Hashtbl.create A.max_records in
    List.iter (fun refinement -> List.iter (fun component ->
        let key = Component.id component,Component.version component and meaning = Component.fingerprint component in
        Diagnostic.require ~path (match Hashtbl.find_opt meanings key with None -> true | Some previous -> previous = meaning)
          code "One component identity/version cannot carry contradictory architecture authority.";
        Hashtbl.replace meanings key meaning) (components refinement)) refinements;
    let value = {id=M.text ~path (get "id");refinements;assumptions} in
    M.check_resources ~path (to_json value); value
  let make ?(assumptions = []) ~id ~refinements () =
    ignore (M.bounded_length ~maximum:A.max_records refinements); ignore (M.bounded_length ~maximum:64 assumptions);
    let budget = budget () in reserve_children budget refinement_json refinements; reserve budget (strings assumptions);
    of_json (to_json {id;refinements;assumptions})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let refinements (value : t) = value.refinements
  let assumptions (value : t) = value.assumptions
end

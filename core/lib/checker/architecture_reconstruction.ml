open Bioc_wire
open Bioc_domain
module Names = Map.Make (String)
module Ids = Set.Make (String)
module F = Architecture_refinement
module C = Architecture_contract
module B = Architecture_build
let str value = Json.String value
let arr values = Json.Array values
let obj values = Json.Object values
let strings values = arr (List.map str values)
let field key raw = Json.field key (Json.object_fields raw)
let text key raw = Json.string (field key raw)
let texts raw = Json.array raw |> List.map Json.string
let set values = List.fold_left (fun set value -> Ids.add value set) Ids.empty values
let union_values values = List.fold_left Ids.union Ids.empty values
let replace fields raw = obj (fields @ List.filter (fun (key,_) -> not (List.mem_assoc key fields)) (Json.object_fields raw))
let map_string pairs id = match List.assoc_opt id pairs with Some value -> value
  | None -> Diagnostic.fail "invalid_architecture_authority" ("Unmapped architecture reference: " ^ id ^ ".")
let mapping refinement = F.source_bindings refinement |> List.map (fun (key,value) -> Identity.Node.to_string key,Identity.Node.to_string value)
let output_budget () = Work_budget.create_output ~profile:"biocompiler.architecture_check.resources.v1"
    ~error_code:"architecture_output_limit" ~max_bytes:Molecular_record.max_json_bytes ~max_nodes:Molecular_record.max_items ()
let charge_json budget raw =
  let rec visit = function
    | [] -> ()
    | value :: rest ->
        Work_budget.charge budget 1;
        (match value with
         | Json.String value -> Work_budget.charge budget (String.length value); visit rest
         | Json.Array values -> visit (List.rev_append values rest)
         | Json.Object fields -> List.iter (fun (key,_) -> Work_budget.charge budget (String.length key + 1)) fields;
             visit (List.rev_append (List.map snd fields) rest)
         | _ -> visit rest) in
  visit [raw]
type node = { id : string; kind : string; inputs : string list; role : string option;
              attributes : Json.t; data_type : Json.t; contact_bound : bool; semantics : Json.t }
type graph = { ordered : node list; by_id : node Names.t; budget : Work_budget.t;
               lineages : (string,string list) Hashtbl.t; cached_output : Work_budget.output }
let graph ~budget raw_nodes =
  let ordered = List.map (fun raw ->
      charge_json budget raw;
      let fields = Json.object_fields raw in
      {id=text "id" raw;kind=text "kind" raw;inputs=texts (field "inputs" raw);
       role=(match field "role" raw with Json.Null -> None | value -> Some (Json.string value));
       attributes=field "attributes" raw;data_type=field "data_type" raw;
       contact_bound=(match List.assoc_opt "contact_bound" fields with None -> false | Some value -> Json.boolean value);
       semantics=obj (List.remove_assoc "source" fields)}) raw_nodes in
  {ordered;by_id=List.fold_left (fun values node -> Names.add node.id node values) Names.empty ordered;
   budget;lineages=Hashtbl.create (List.length ordered);cached_output=output_budget ()}
let source_graph ~budget source = Human_request.build_request source |> Build_request.intent |> Intent.to_json |> field "nodes" |> Json.array |> graph ~budget
let behavior_graph ~budget behavior = List.map (Behavior.node_json ~include_source:false) (Behavior.nodes behavior) |> graph ~budget
let nodes graph = graph.ordered
let find graph id = Work_budget.charge graph.budget 1; Names.find_opt id graph.by_id
let lookup graph id = match find graph id with Some value -> value
  | None -> Diagnostic.fail "invalid_architecture_authority" ("Missing architecture graph reference: " ^ id ^ ".")
let input node index = match List.nth_opt node.inputs index with Some value -> value
  | None -> Diagnostic.fail "invalid_architecture_authority" ("Missing operand in architecture source node: " ^ node.id ^ ".")
let runtime node = List.mem node.kind ["rule";"state";"memory"] || String.starts_with ~prefix:"action." node.kind
let lineage graph id = match Hashtbl.find_opt graph.lineages id with Some values -> values | None ->
  let rec walk found = function
    | [] -> Ids.elements found
    | id :: rest when Ids.mem id found -> Work_budget.charge graph.budget 1; walk found rest
    | id :: rest -> let node = lookup graph id in
        let parents = match node.role with None -> node.inputs | Some role -> role :: node.inputs in
        walk (Ids.add id found) (List.rev_append parents rest) in
  let result = walk Ids.empty [id] in
  let raw = strings result in charge_json graph.budget raw; Work_budget.reserve_json graph.cached_output raw;
  Hashtbl.add graph.lineages id result; result
let causal_nodes graph identities =
  let installations = List.fold_left (fun installed rule ->
      Work_budget.charge graph.budget 1;
      if rule.kind <> "rule" then installed else
        let actions = match rule.inputs with _ :: _ :: values -> values | _ -> [] in
        List.fold_left (fun installed id ->
            let add id map = Names.add id (Ids.add rule.id (Option.value ~default:Ids.empty (Names.find_opt id map))) map in
            let installed = add id installed in
            let action = lookup graph id in if action.kind = "action.pulse" then add (input action 0) installed else installed) installed actions)
      Names.empty graph.ordered in
  let installed id = Option.value ~default:Ids.empty (Names.find_opt id installations) |> Ids.elements in
  let causal = ref Ids.empty in
  let include_lineage id = causal := Ids.union !causal (set (lineage graph id)) in
  List.iter (fun id -> include_lineage id; List.iter include_lineage (installed id)) identities;
  let rec extend visited_states visited_channels =
    let states = ref Ids.empty and channels = ref Ids.empty in
    Ids.iter (fun id -> let node = lookup graph id in
        if node.kind = "state" then states := Ids.add id !states;
        if node.kind = "channel_observation" then channels := Ids.add (input node 1) !channels) !causal;
    let states = Ids.diff !states visited_states and channels = Ids.diff !channels visited_channels in
    if not (Ids.is_empty states && Ids.is_empty channels) then (
      List.iter (fun node -> Work_budget.charge graph.budget 1;
          if (node.kind = "action.state_set" && Ids.mem (input node 0) states) ||
             (node.kind = "action.emit" && Ids.mem (input node 1) channels) then List.iter include_lineage (installed node.id)) graph.ordered;
      extend (Ids.union visited_states states) (Ids.union visited_channels channels)) in
  extend Ids.empty Ids.empty; Ids.elements !causal
type channel = { channel_id : string; sender_ids : string list; receiver_ids : string list }
let source_channels graph =
  List.filter (fun node -> node.kind = "channel") graph.ordered |> List.map (fun channel ->
      let sender_ids = List.filter (fun node -> node.kind = "rule") graph.ordered |> List.concat_map (fun rule ->
          let actions = match rule.inputs with _ :: _ :: values -> values | _ -> [] in
          List.filter (fun id -> let action = lookup graph id in
              let primitive = if action.kind = "action.pulse" then lookup graph (input action 0) else action in
              primitive.kind = "action.emit" && input primitive 1 = channel.id) actions) in
      let receiver_ids = List.filter (fun node -> Work_budget.charge graph.budget 1;
          node.kind = "channel_observation" && input node 1 = channel.id) graph.ordered |> List.map (fun node -> node.id) in
      {channel_id=channel.id;sender_ids;receiver_ids})
let selected_instances ~budget build request =
  let plan = match B.plan build with Some value -> value | None -> Diagnostic.fail "invalid_architecture_authority" "Selection requires a retained plan." in
  let library = Architecture_request.library request |> F.Library.refinements |> List.fold_left (fun values item -> Names.add (F.id item) item values) Names.empty in
  let instances = B.Plan.instances plan |> List.fold_left (fun values item -> Names.add (C.Instance.id item) item values) Names.empty in
  let census = B.match_instances build |> List.fold_left (fun values item -> Names.add (C.Instance.id item) item values) Names.empty in
  let failures = ref [] in let fail code = Work_budget.charge budget 1; failures := code :: !failures in
  let keys map = Names.bindings map |> List.map fst |> set in
  if not (Ids.equal (keys instances) (set (B.Plan.selected_refinement_ids plan))) then fail "selected_instance_inventory";
  let selected = List.filter_map (fun id ->
      Work_budget.charge budget 1;
      match Names.find_opt id instances with None -> None | Some instance ->
        match Names.find_opt (C.Instance.refinement_id instance) library with
        | None -> fail ("selected_refinement_authority:" ^ id); None
        | Some original ->
            (match Names.find_opt id census with Some retained when C.Instance.fingerprint instance = C.Instance.fingerprint retained -> ()
             | _ -> fail ("selected_instance_census:" ^ id));
            let bindings = C.Instance.source_bindings instance |> List.map (fun (key,value) -> Identity.Node.to_string key,Identity.Node.to_string value) in
            let actual_keys = List.map fst bindings |> set and expected_keys = Behavior.nodes (F.behavior original) |> List.map (fun node -> Identity.Node.to_string (Behavior.node_id node)) |> set in
            if not (Ids.equal actual_keys expected_keys) then (fail ("selected_instance_mapping_inventory:" ^ id); None)
            else if Ids.cardinal (set (List.map snd bindings)) <> List.length bindings then (fail ("selected_instance_mapping_not_injective:" ^ id); None)
            else (
              if List.exists (fun (key,value) -> List.assoc_opt key bindings <> Some value) (mapping original) then fail ("selected_instance_anchor_authority:" ^ id);
              let bindings_json = obj (List.map (fun (key,value) -> key,str value) bindings) in
              let expected_id = match F.match_policy original with
                | None -> if not (Json.equal bindings_json (field "source_bindings" (F.to_json original))) then fail ("explicit_instance_mapping_authority:" ^ id); F.id original
                | Some _ -> F.id original ^ ".match." ^ Canonical.fingerprint (obj ["refinement",str (F.fingerprint original);"source_bindings",bindings_json]) in
              if id <> expected_id then fail ("selected_instance_identity:" ^ id);
              let raw = replace ["id",str id;"source_bindings",bindings_json;"match_policy",Json.Null] (F.to_json original) in
              charge_json budget raw; Some (F.of_json raw))) (B.Plan.selected_refinement_ids plan) in
  selected,List.rev !failures
type inventories = { placements : Json.t list; helpers : Json.t list; channels : Json.t list;
                     control_domains : Json.t list; availability : Json.t list }
let namespace_template ~budget template prefix =
  let frames = List.map (fun source -> Construction.Root_source.molecule source |> Molecule.space |> Molecule_coordinates.Space.id |> Molecule_coordinates.Space_id.to_string) (Payload_template.sources template)
      @ List.concat_map (fun step -> List.map Construction.Product_port.space_id (Construction.Transform_step.ports step)) (Payload_template.steps template)
      @ List.map Construction.Output_member.space_id (Payload_template.output_members template) |> set in
  let local = ["payload_template";"construction_root_source";"circuit_molecule";"construction_transform_step";
    "construction_product_port";"construction_value_ref";"construction_output_member";"construction_member_requirement";
    "construction_role_declaration";"construction_complex_member";"construction_amount_declaration"] in
  let kind schema =
    let name = if String.starts_with ~prefix:"biocompiler." schema then String.sub schema 12 (String.length schema - 12) else schema in
    let boundary = ref (String.length name) in
    for index = 0 to String.length name - 2 do if name.[index] = '.' && name.[index + 1] = 'v' then boundary := index done;
    String.sub name 0 !boundary in
  let rec transform = function
    | Json.Array values -> arr (List.map transform values)
    | Json.Object fields as raw ->
        Work_budget.charge budget (List.length fields + 1);
        let kind = match List.assoc_opt "schema_version" fields with Some (Json.String value) -> kind value | _ -> "" in
        if kind = "molecular_declaration_provenance" then raw else
          let fields = List.map (fun (key,value) -> key,transform value) fields in
          let get key = Option.value ~default:Json.Null (List.assoc_opt key fields) in
          let member value = match value with Json.String value -> Ids.mem value frames | _ -> false in
          let rename key predicate fields = if predicate then (key,str (prefix ^ Json.string (get key))) :: List.remove_assoc key fields else fields in
          let fields = rename "id" (List.mem kind local || kind = "molecule_coordinate_space" && member (get "id")) fields in
          let fields = rename "space_id" (member (get "space_id")) fields in
          let fields = List.fold_left (fun fields key -> rename key (get key <> Json.Null) fields) fields ["member_id";"port_id"] in
          let fields = rename "source_id" (List.mem kind ["chemistry_disposition";"feature_disposition"]) fields in
          let fields = if kind <> "construction_amount_declaration" then fields else
              let fields = List.fold_left (fun fields key -> rename key true fields) fields ["subject_id";"preparation_id"] in
              ("role_instance_ids",strings (List.map (fun value -> prefix ^ value) (texts (get "role_instance_ids")))) :: List.remove_assoc "role_instance_ids" fields in
          obj fields
    | value -> value in
  let raw = Payload_template.to_json template in charge_json budget raw; transform raw
let inventories ~budget selected =
  let placements = ref [] and helpers = ref [] and channels = ref [] and controls = ref [] and availability = ref [] and templates = ref [] in
  let output = output_budget () in
  let add target raw = charge_json budget raw; Work_budget.reserve_json output raw; target := raw :: !target in
  List.iteri (fun index refinement ->
      let prefix = Printf.sprintf "a%03d_" index and remap = mapping refinement in
      let sorted = List.sort (fun a b -> String.compare (Payload_template.id a) (Payload_template.id b)) (F.templates refinement) in
      let prefixes = List.mapi (fun index template -> Payload_template.id template, prefix ^ Printf.sprintf "t%03d_" index) sorted in
      let template_prefix id = map_string prefixes id in
      let mapped id = map_string remap id in
      let local_roles = Behavior.nodes (F.behavior refinement) |> List.filter (fun node -> Behavior.kind_name (Behavior.operation node) = "role")
          |> List.map (fun node -> Identity.Node.to_string (Behavior.node_id node)) |> set in
      List.iter (fun template ->
          let document = namespace_template ~budget template (template_prefix (Payload_template.id template)) in
          let requirements = field "requirements" document |> Json.array |> List.map (fun requirement ->
              let roles = field "roles" requirement |> Json.array |> List.map (fun role ->
                  let value = text "role" role in if Ids.mem value local_roles then replace ["role",str (mapped value)] role else role) in
              replace ["roles",arr roles] requirement) in
          add templates (replace ["requirements",arr requirements] document)) sorted;
      List.iter (fun item -> add placements (replace ["id",str (prefix ^ C.Placement.id item);
          "template_id",str (template_prefix (C.Placement.template_id item) ^ C.Placement.template_id item);
          "member_id",str (template_prefix (C.Placement.template_id item) ^ C.Placement.member_id item);
          "recipient_role",str (mapped (Identity.Role.to_string (C.Placement.recipient_role item)))] (C.Placement.to_json item))) (F.placements refinement);
      List.iter (fun item -> let option f = function None -> Json.Null | Some value -> str (prefix ^ f value) in
          add helpers (replace ["id",str (prefix ^ C.Helper.id item);"recipient_role",str (mapped (Identity.Role.to_string (C.Helper.recipient_role item)));
            "consumer_component_ids",strings (List.map (fun id -> prefix ^ Identity.Component.to_string id) (C.Helper.consumer_component_ids item));
            "provider_component_id",option Identity.Component.to_string (C.Helper.provider_component_id item);
            "placement_id",option Fun.id (C.Helper.placement_id item);"depends_on",strings (List.map (fun id -> prefix ^ id) (C.Helper.depends_on item))] (C.Helper.to_json item))) (F.helpers refinement);
      List.iter (fun item -> let raw = C.Channel.to_json item in
          add channels (replace (("id",str (prefix ^ C.Channel.id item)) :: List.map (fun key -> key,str (mapped (text key raw)))
            ["source_channel_id";"sender_role";"receiver_role";"sender_node_id";"receiver_node_id"]) raw)) (F.channels refinement);
      List.iter (fun item -> add controls (replace ["id",str (prefix ^ C.Control.id item);"domain_id",str (prefix ^ C.Control.domain_id item);
          "behavior_node_ids",strings (List.map (fun id -> mapped (Identity.Node.to_string id)) (C.Control.behavior_node_ids item));
          "controlling_node_ids",strings (List.map (fun id -> mapped (Identity.Node.to_string id)) (C.Control.controlling_node_ids item));
          "component_ids",strings (List.map (fun id -> prefix ^ Identity.Component.to_string id) (C.Control.component_ids item))] (C.Control.to_json item))) (F.controls refinement);
      List.iter (fun item -> add availability (replace ["id",str (prefix ^ Architecture_deployment.Availability.id item);
          "placement_id",str (prefix ^ Architecture_deployment.Availability.placement_id item)] (Architecture_deployment.Availability.to_json item))) (F.availability refinement))
    (List.sort (fun a b -> String.compare (F.id a) (F.id b)) selected);
  {placements=List.rev !placements;helpers=List.rev !helpers;channels=List.rev !channels;control_domains=List.rev !controls;availability=List.rev !availability},List.rev !templates
let expected_construction ~budget request documents =
  let keys = ["sources";"steps";"output_members";"requirements";"complex_members";"amounts";"payload_structures"] in
  let fields = List.map (fun key -> key,arr (List.concat_map (fun document -> Json.array (field key document)) documents)) keys in
  let raw = obj (["schema_version",str Construction.Request.schema_version;"id",str (Architecture_request.id request ^ ".construction");
    "circuit",Circuit_request.to_json (Architecture_request.circuit request);"mode",str "strict"] @ fields) in
  charge_json budget raw; Construction.Request.of_json raw
let assumptions request selected =
  let constraints = Architecture_request.constraints request in
  F.Library.assumptions (Architecture_request.library request)
  @ List.concat_map C.Delivery_group.assumptions (C.Constraints.delivery_groups constraints)
  @ List.concat_map Architecture_deployment.Requirement.assumptions (C.Constraints.deployment_requirements constraints)
  @ List.concat_map (fun refinement -> F.assumptions refinement @ List.concat_map Component.assumptions (F.components refinement)
      @ List.concat_map C.Control.assumptions (F.controls refinement) @ List.concat_map C.Helper.assumptions (F.helpers refinement)
      @ List.concat_map C.Channel.assumptions (F.channels refinement)
      @ List.concat_map Architecture_deployment.Availability.assumptions (F.availability refinement)) selected
  |> List.sort_uniq String.compare
let expected_ledger ~budget request graph selected ~assumptions ~source_complete =
  let output = output_budget () in
  let retain value = let raw = B.Requirement_realization.to_json value in
    charge_json budget raw; Work_budget.reserve_json output raw; value in
  let add key value map = Names.add key (Ids.add value (Option.value ~default:Ids.empty (Names.find_opt key map))) map in
  let owners = ref Names.empty and covered = ref Names.empty in
  List.iter (fun refinement -> let bindings = mapping refinement in
      List.iter (fun (_,node) -> Work_budget.charge budget 1; covered := add node (F.id refinement) !covered) bindings;
      List.iter (fun id -> Work_budget.charge budget 1; owners := add (map_string bindings (Identity.Node.to_string id)) (F.id refinement) !owners) (F.owned_node_ids refinement)) selected;
  let get map key = Option.value ~default:Ids.empty (Names.find_opt key map) in
  let entries = List.map (fun node -> "source:" ^ node.id,[node.id]) graph.ordered @ ["source:complete_authority",List.map (fun node -> node.id) graph.ordered] in
  let ledger = List.map (fun (id,refs) ->
      Work_budget.charge budget (List.length refs + 1);
      let candidates = List.map (get !covered) refs |> union_values in
      let fulfilled = List.for_all (fun id -> Names.mem id !covered && (not (runtime (lookup graph id)) || Ids.cardinal (get !owners id) = 1)) refs in
      let authority = id = "source:complete_authority" in
      let fulfilled = fulfilled && (not authority || source_complete) in
      let item_assumptions = List.filter (fun item -> Ids.mem (F.id item) candidates) selected |> List.concat_map F.assumptions |> List.sort_uniq String.compare in
      retain (B.Requirement_realization.make ~id ~source_node_ids:refs ~refinement_ids:(Ids.elements candidates)
        ~status:(if fulfilled then B.Requirement_realization.Implemented else B.Requirement_realization.Unresolved)
        ~assumptions:item_assumptions ~reasons:(if fulfilled then [] else [if authority && not source_complete then "unresolved_source_obligations" else "uncovered_source_requirements"]))) entries in
  let constraints = Architecture_request.constraints request and ids = List.map F.id selected in
  let implemented id refs = Work_budget.charge budget (List.length refs + 1);
    retain (B.Requirement_realization.make ~id ~source_node_ids:refs ~refinement_ids:ids ~status:B.Requirement_realization.Implemented ~assumptions ~reasons:[]) in
  let constraint_keys = C.Constraints.to_json constraints |> Json.object_fields |> List.filter_map (fun (key,_) -> if key = "schema_version" then None else Some key) in
  let ledger = ledger @ List.map (fun key -> implemented ("constraint:" ^ key) []) constraint_keys
    @ List.map (fun item -> implemented ("constraint:control:" ^ C.Control_requirement.id item) (List.map Identity.Node.to_string (C.Control_requirement.behavior_node_ids item))) (C.Constraints.control_requirements constraints)
    @ List.map (fun item -> implemented ("constraint:delivery:" ^ C.Delivery_group.id item) (List.map Identity.Role.to_string (C.Delivery_group.recipient_roles item))) (C.Constraints.delivery_groups constraints)
    @ List.map (fun item -> implemented ("constraint:deployment:" ^ Architecture_deployment.Requirement.id item) [Architecture_deployment.Requirement.recipient_role item]) (C.Constraints.deployment_requirements constraints) in
  ledger,(Names.bindings !owners |> List.map (fun (key,values) -> key,Ids.elements values))

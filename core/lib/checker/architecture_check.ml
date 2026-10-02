open Bioc_wire
open Bioc_domain
module R = Architecture_reconstruction
module F = Architecture_refinement
module C = Architecture_contract
module B = Architecture_build
module E = Architecture_assessment
module Names = Map.Make (String)
module Ids = Set.Make (String)
let implementation_version = "biocompiler.ocaml.architecture_check.v0.1"
let resource_profile = "biocompiler.architecture_check.resources.v1"
let max_work = 50_000_000
let output_budget () = Work_budget.create_output ~profile:resource_profile ~error_code:"architecture_output_limit"
    ~max_bytes:Molecular_record.max_json_bytes ~max_nodes:Molecular_record.max_items ()
let make_budget ?parent ?(maximum = max_work) () =
  Diagnostic.require (maximum >= 0 && maximum <= max_work) "invalid_work_budget" "Architecture budget exceeds its fixed profile.";
  match parent with
  | None -> Work_budget.create ~profile:resource_profile ~error_code:"architecture_resource_limit" ~maximum ()
  | Some parent -> Work_budget.nested ~parent ~profile:resource_profile ~error_code:"architecture_resource_limit" ~maximum ()
let str value = Json.String value
let arr values = Json.Array values
let obj values = Json.Object values
let strings values = arr (List.map str values)
let field key value = Json.field key (Json.object_fields value)
let text key value = Json.string (field key value)
let texts value = Json.array value |> List.map Json.string
let attr key (node:R.node) = Option.value ~default:Json.Null (List.assoc_opt key (Json.object_fields node.attributes))
let set values = List.fold_left (fun values value -> Ids.add value values) Ids.empty values
let union values = List.fold_left Ids.union Ids.empty values
let overlap left right = not (Ids.is_empty (Ids.inter left right))
let intersection = function [] -> Ids.empty | first :: rest -> List.fold_left Ids.inter first rest
let map_get map key = Option.value ~default:Ids.empty (Names.find_opt key map)
let map_add map key values = Names.add key (Ids.union values (map_get map key)) map
let mapping refinement = F.source_bindings refinement |> List.map (fun (key,value) -> Identity.Node.to_string key,Identity.Node.to_string value)
let mapped refinement id = match List.assoc_opt id (mapping refinement) with Some value -> value
  | None -> Diagnostic.fail "invalid_architecture_authority" ("Unmapped architecture source node: " ^ id ^ ".")
let target request = match Circuit_request.Profile.target (Circuit_request.profile (Architecture_request.circuit request)) with
  | Some value -> value | None -> Diagnostic.fail "invalid_architecture_authority" "Architecture target authority is missing."
let failures budget action =
  let values = ref [] and seen = Hashtbl.create 32 and bytes = ref 0 in
  let add value =
    Work_budget.charge budget (String.length value + 1);
    if not (Hashtbl.mem seen value) then (
      Diagnostic.require (Hashtbl.length seen < 4096 && String.length value <= Molecular_record.max_text_bytes &&
                          !bytes + String.length value <= 1_000_000)
        "architecture_report_limit" "Independent architecture diagnostics exceed the fixed report budget.";
      Hashtbl.add seen value (); bytes := !bytes + String.length value; values := value :: !values) in
  action add; List.rev !values
let model_correspondence ~budget refinement source_behavior = failures budget (fun fail ->
    let actual = R.behavior_graph ~budget (F.behavior refinement) and expected = R.behavior_graph ~budget source_behavior in
    let bindings = mapping refinement in
    if not (Ids.equal (set (List.map fst bindings)) (set (List.map (fun (node:R.node) -> node.id) (R.nodes actual)))) then fail "model_mapping_inventory";
    if Ids.cardinal (set (List.map snd bindings)) <> List.length bindings then fail "model_mapping_not_injective";
    if not (Ids.subset (set (List.map snd bindings)) (set (List.map (fun (node:R.node) -> node.id) (R.nodes expected)))) then fail "model_mapping_unknown_source";
    if Behavior.profile (F.behavior refinement) <> Behavior.profile source_behavior then fail "model_execution_profile";
    if not (Json.equal (Behavior.policies (F.behavior refinement)) (Behavior.policies source_behavior)) then fail "model_execution_policies";
    List.iter (fun (node:R.node) ->
        Work_budget.charge budget 1;
        match Option.bind (List.assoc_opt node.id bindings) (R.find expected) with
        | None -> ()
        | Some wanted ->
            if List.exists (fun ref -> not (List.mem_assoc ref bindings)) node.inputs ||
               Option.fold ~none:false ~some:(fun role -> not (List.mem_assoc role bindings)) node.role then fail ("model_reference_unmapped:" ^ node.id)
            else (
              let mapped id = List.assoc id bindings in
              let meaning (node:R.node) inputs role = obj ["kind",str node.kind;"inputs",strings inputs;
                "role",(match role with None -> Json.Null | Some value -> str value);"attributes",node.attributes;
                "data_type",node.data_type;"contact_bound",Json.Bool node.contact_bound] in
              if not (Json.equal (meaning node (List.map mapped node.inputs) (Option.map mapped node.role))
                        (meaning wanted wanted.inputs wanted.role)) then fail ("model_operation_mismatch:" ^ node.id ^ ":" ^ wanted.id))) (R.nodes actual))
let refinement_checks ~budget refinement behavior target =
  model_correspondence ~budget refinement behavior @ failures budget (fun fail ->
    let graph = R.behavior_graph ~budget (F.behavior refinement) in
    let nodes = R.nodes graph and lookup = R.lookup graph in
    let owned = F.owned_node_ids refinement |> List.map Identity.Node.to_string |> set in
    let action_references = List.filter (fun (node:R.node) -> node.kind = "action.pulse") nodes |> List.map (fun node -> R.input node 0) |> set in
    List.iter (fun (node:R.node) -> Work_budget.charge budget 1;
        if not (Ids.mem node.id owned) && R.runtime node && not (Ids.mem node.id action_references) then fail ("unowned_executable_" ^ node.kind ^ ":" ^ node.id)) nodes;
    let components = List.fold_left (fun map item -> Names.add (Component.id item) item map) Names.empty (F.components refinement) in
    let modeled = ref Ids.empty in
    let compartments = set (Build_request.Target.compartments target) in
    let interfaces component = List.map Component_contract.Port.to_json (Component.ports component)
        @ List.map Component.Capability.to_json (Component.capabilities component)
        @ List.map Component.Resource.to_json (Component.resources component)
        @ List.map Component.Dependency.to_json (List.filter Component.Dependency.required (Component.dependencies component)) in
    List.iter (fun component ->
        Work_budget.charge budget 1;
        (match Component.classification component with
         | Component.Synthetic_model -> fail ("unsupported_intrinsic_model_refinement:" ^ Component.id component)
         | Component.Modeled_component ->
             if List.exists (fun pin -> Pinned_identity.kind pin = Pinned_identity.Model && Pinned_identity.content_fingerprint pin = Behavior.fingerprint (F.behavior refinement)) (Component.identities component)
             then modeled := Ids.add (Component.id component) !modeled else fail ("component_model_authority:" ^ Component.id component)
         | Component.Sequence_reference -> ());
        if not (List.mem (Build_request.Target.payload_format target) (Component.supported_targets component)) then fail ("component_target:" ^ Component.id component);
        if List.exists (fun item -> Work_budget.charge budget 1; not (Ids.mem (text "compartment" item) compartments)) (interfaces component) then fail ("component_compartment:" ^ Component.id component);
        if Component.resources component <> [] || Component_contract.Operating_domain.constraints (Component.supported_domain component) <> [] then fail ("component_operating_domain_or_resources_unmapped:" ^ Component.id component)) (F.components refinement);
    Ids.iter (fun identity ->
        if R.runtime (lookup identity) && not (List.exists (fun binding -> Work_budget.charge budget 1;
            List.exists (fun id -> Identity.Node.to_string id = identity) (C.Binding.behavior_node_ids binding) &&
            overlap !modeled (set (List.map Identity.Component.to_string (C.Binding.component_ids binding)))) (F.bindings refinement))
        then fail ("executable_material_model_missing:" ^ identity)) owned;
    let placements = List.fold_left (fun values item -> Names.add (C.Placement.id item) item values) Names.empty (F.placements refinement) in
    List.iter (fun item -> if not (Ids.mem (C.Placement.compartment item) compartments) then fail ("placement_compartment:" ^ C.Placement.id item)) (F.placements refinement);
    let binding_roles = ref Names.empty and binding_members = ref Names.empty in
    let material_key template member = Canonical.encode (strings [template;member]) in
    List.iter (fun binding ->
        let roles = C.Binding.behavior_node_ids binding |> List.filter_map (fun id -> (lookup (Identity.Node.to_string id)).role) |> set in
        let placed = List.map (fun id -> Names.find id placements) (C.Binding.placement_ids binding) in
        List.iter (fun id -> Work_budget.charge budget 1;
            let id = Identity.Component.to_string id in
            binding_roles := map_add !binding_roles id roles;
            binding_members := map_add !binding_members id (List.map (fun item -> material_key (C.Placement.template_id item) (C.Placement.member_id item)) placed |> set)) (C.Binding.component_ids binding);
        Ids.iter (fun role -> if not (List.exists (fun item -> Identity.Role.to_string (C.Placement.recipient_role item) = role) placed) then fail ("material_recipient_missing:" ^ C.Binding.id binding ^ ":" ^ role)) roles) (F.bindings refinement);
    List.iter (fun component -> if List.exists (fun item -> Work_budget.charge budget 1;
        not (Ids.mem (text "role" item) (map_get !binding_roles (Component.id component)))) (interfaces component) then fail ("component_recipient_correspondence:" ^ Component.id component)) (F.components refinement);
    let helpers = F.helpers refinement in
    let target_capabilities = Build_request.Target.to_json target |> field "capabilities" |> texts |> set in
    List.iter (fun helper ->
        Work_budget.charge budget 1;
        if not (Ids.mem (C.Helper.compartment helper) compartments) then fail ("helper_compartment:" ^ C.Helper.id helper);
        if List.length (C.Helper.consumer_component_ids helper) > C.Helper.capacity helper ||
           C.Helper.sharing helper = C.Helper.Exclusive && List.length (C.Helper.consumer_component_ids helper) <> 1 then fail ("helper_capacity:" ^ C.Helper.id helper);
        if C.Helper.availability helper = C.Helper.Host && not (Ids.mem (C.Helper.capability helper) target_capabilities) then fail ("host_capability_unavailable:" ^ C.Helper.id helper);
        if C.Helper.availability helper = C.Helper.External then fail ("helper_external_observation_unbound:" ^ C.Helper.id helper);
        if C.Helper.initialization helper = C.Helper.After_trigger then fail ("helper_trigger_authority_missing:" ^ C.Helper.id helper);
        Option.iter (fun id -> let placement = Names.find id placements in
            if C.Placement.recipient_role placement <> C.Helper.recipient_role helper || C.Placement.compartment placement <> C.Helper.compartment helper then fail ("helper_placement:" ^ C.Helper.id helper);
            let key = material_key (C.Placement.template_id placement) (C.Placement.member_id placement) in
            List.iter (fun consumer -> let consumer = Identity.Component.to_string consumer in
                if Ids.mem key (map_get !binding_members consumer) <> (C.Helper.availability helper = C.Helper.Same_rna) then fail ("helper_rna_relationship:" ^ C.Helper.id helper ^ ":" ^ consumer)) (C.Helper.consumer_component_ids helper)) (C.Helper.placement_id helper);
        List.iter (fun consumer -> let consumer = Identity.Component.to_string consumer in
            if not (Ids.mem (Identity.Role.to_string (C.Helper.recipient_role helper)) (map_get !binding_roles consumer)) then fail ("helper_recipient:" ^ C.Helper.id helper ^ ":" ^ consumer)) (C.Helper.consumer_component_ids helper);
        Option.iter (fun id -> let provider = Names.find (Identity.Component.to_string id) components in
            if not (List.exists (fun item -> Work_budget.charge budget 1;
                Component.Capability.id item = C.Helper.capability helper && Component.Capability.role item = Identity.Role.to_string (C.Helper.recipient_role helper) &&
                Component.Capability.compartment item = C.Helper.compartment helper && Component.Capability.scope item = Component.Cell) (Component.capabilities provider))
            then fail ("helper_provider_capability:" ^ C.Helper.id helper)) (C.Helper.provider_component_id helper)) helpers;
    let rec ground grounded_helpers grounded_components =
      let next_helpers = List.filter (fun helper -> Work_budget.charge budget 1;
          Ids.subset (set (C.Helper.depends_on helper)) grounded_helpers && C.Helper.initialization helper <> C.Helper.After_trigger &&
          ((C.Helper.provider_component_id helper = None && C.Helper.initialization helper = C.Helper.Available_at_start) ||
           Option.fold ~none:false ~some:(fun id -> Ids.mem (Identity.Component.to_string id) grounded_components) (C.Helper.provider_component_id helper))) helpers
          |> List.map C.Helper.id |> set in
      let next_components = F.components refinement |> List.filter (fun component -> Work_budget.charge budget 1;
          List.for_all (fun dependency -> not (Component.Dependency.required dependency) || List.exists (fun helper -> Work_budget.charge budget 1;
              Ids.mem (C.Helper.id helper) grounded_helpers && List.exists (fun id -> Identity.Component.to_string id = Component.id component) (C.Helper.consumer_component_ids helper) &&
              C.Helper.capability helper = Component.Dependency.capability dependency && Identity.Role.to_string (C.Helper.recipient_role helper) = Component.Dependency.role dependency &&
              Component.Dependency.scope dependency = Component.Cell && C.Helper.compartment helper = Component.Dependency.compartment dependency) helpers) (Component.dependencies component))
          |> List.map Component.id |> set in
      if Ids.subset next_helpers grounded_helpers && Ids.subset next_components grounded_components then grounded_helpers,grounded_components
      else ground (Ids.union next_helpers grounded_helpers) (Ids.union next_components grounded_components) in
    let grounded_helpers,grounded_components = ground Ids.empty Ids.empty in
    Ids.iter (fun id -> fail ("helper_initialization_ungrounded:" ^ id)) (Ids.diff (List.map C.Helper.id helpers |> set) grounded_helpers);
    Ids.iter (fun id -> fail ("component_dependency_ungrounded:" ^ id)) (Ids.diff (List.map Component.id (F.components refinement) |> set) grounded_components);
    List.iter (fun control ->
        let refs = List.map Identity.Node.to_string (C.Control.behavior_node_ids control) in
        if not (Ids.subset (List.map Identity.Node.to_string (C.Control.controlling_node_ids control) |> set) (R.causal_nodes graph refs |> set)) then fail ("control_input_not_causal:" ^ C.Control.id control);
        let material = F.bindings refinement |> List.filter (fun binding -> Work_budget.charge budget 1;
            overlap (List.map Identity.Node.to_string (C.Binding.behavior_node_ids binding) |> set) (set refs))
            |> List.concat_map C.Binding.component_ids |> List.map Identity.Component.to_string |> set in
        let control_components = List.map Identity.Component.to_string (C.Control.component_ids control) |> set in
        if not (Ids.subset control_components material) || not (overlap !modeled control_components) then fail ("control_material_correspondence:" ^ C.Control.id control);
        if C.Control.kind control = C.Activity_control then (
          let actions = List.filter (fun id -> String.starts_with ~prefix:"action." (lookup id).kind) refs
              @ List.concat_map (fun id -> let node = lookup id in if node.kind = "rule" then (match node.inputs with _ :: _ :: actions -> actions | _ -> []) else []) refs |> set in
          Ids.iter (fun id -> let action = lookup id in let primitive = if action.kind = "action.pulse" then lookup (R.input action 0) else action in
              if not (List.mem primitive.kind ["action.eliminate";"action.engulf";"action.rest"]) ||
                 not (List.exists (fun output -> Work_budget.charge budget 1;
                     List.exists (fun ref -> Identity.Node.to_string ref = id) (C.Output_binding.action_ids output) &&
                     Circuit_request.Product.kind (C.Output_binding.product output) = "biological_activity" && Circuit_request.Lifecycle.mode (C.Output_binding.lifecycle output) = "activity_control") (F.output_contracts refinement))
              then fail ("activity_control_not_realized:" ^ C.Control.id control)) actions;
          if Ids.is_empty actions then fail ("activity_control_action_missing:" ^ C.Control.id control))) (F.controls refinement))
let supplementary_checks ~budget request graph selected =
  let unresolved = ref [] and output = output_budget () and seen = Hashtbl.create 32 in
  let unknown value = Work_budget.charge budget (String.length value + 1);
    if not (Hashtbl.mem seen value) then (Work_budget.reserve_json output (str value); Hashtbl.add seen value (); unresolved := value :: !unresolved) in
  let result = failures budget (fun fail ->
      let source = Architecture_request.source request and nodes = R.nodes graph and lookup = R.lookup graph in
      let declarations = List.fold_left (fun values refinement -> List.fold_left (fun values binding ->
          let id = Identity.Requirement.to_string (C.Output_binding.requirement_id binding) in
          Names.add id (Option.value ~default:[] (Names.find_opt id values) @ [refinement,binding]) values) values (F.output_contracts refinement)) Names.empty selected in
      let requirements = Circuit_request.requirements (Architecture_request.circuit request) in
      Ids.iter (fun id -> fail ("unknown_output_requirement:" ^ id)) (Ids.diff (Names.bindings declarations |> List.map fst |> set) (List.map Circuit_request.Requirement.id requirements |> set));
      let installed = List.filter (fun (node:R.node) -> node.kind = "rule") nodes |> List.concat_map (fun node -> match node.inputs with _ :: _ :: values -> values | _ -> []) |> set in
      let legacy = ref [] and legacy_bindings = ref [] in
      List.iter (fun requirement ->
          let id = Circuit_request.Requirement.id requirement in
          match Option.value ~default:[] (Names.find_opt id declarations) with
          | [refinement,binding] ->
              let actions = C.Output_binding.action_ids binding |> List.map Identity.Node.to_string in
              let mapped_actions = List.map (mapped refinement) actions |> List.sort String.compare in
              if not (Ids.subset (set actions) (F.owned_node_ids refinement |> List.map Identity.Node.to_string |> set)) then fail ("supplementary_output_not_owned:" ^ id);
              if Circuit_request.Product.fingerprint (C.Output_binding.product binding) <> Circuit_request.Product.fingerprint (Circuit_request.Requirement.product requirement) ||
                 Circuit_request.Lifecycle.fingerprint (C.Output_binding.lifecycle binding) <> Circuit_request.Lifecycle.fingerprint (Circuit_request.Requirement.lifecycle requirement)
              then fail ("supplementary_output_authority:" ^ id);
              if not (Ids.subset (set mapped_actions) installed) then fail ("supplementary_output_not_installed:" ^ id);
              let requirement_nodes = Circuit_request.Requirement.source_nodes requirement |> List.map Identity.Node.to_string |> set in
              List.iter (fun identity ->
                  let action = lookup identity in let primitive = if action.kind = "action.pulse" then lookup (R.input action 0) else action in
                  let rules = List.filter (fun (node:R.node) -> Work_budget.charge budget 1;
                      node.kind = "rule" && List.mem identity (match node.inputs with _ :: _ :: values -> values | _ -> [])) nodes in
                  if action.role <> Option.map Identity.Role.to_string (Circuit_request.Requirement.role requirement) || not (Ids.mem identity requirement_nodes) ||
                     not (List.exists (fun (node:R.node) -> Ids.mem node.id requirement_nodes) rules) then fail ("supplementary_source_role_or_lineage:" ^ id);
                  let product = C.Output_binding.product binding in
                  if primitive.kind = "action.secrete" && attr "product" (lookup (R.input primitive 0)) <> str (Circuit_request.Product.id product) then fail ("supplementary_source_product:" ^ id)
                  else if primitive.kind = "action.present" && attr "antigen" primitive <> str (Circuit_request.Product.id product) then fail ("supplementary_source_product:" ^ id)
                  else if List.mem primitive.kind ["action.eliminate";"action.engulf";"action.rest"] && Circuit_request.Requirement.executable_behavior requirement <> None &&
                          Circuit_request.Product.kind product = "biological_activity" && Circuit_request.Lifecycle.mode (C.Output_binding.lifecycle binding) = "activity_control" then ()
                  else if not (List.mem primitive.kind ["action.secrete";"action.present"]) then unknown ("source_output_product_mapping:" ^ id ^ ":" ^ identity)) mapped_actions;
              (match Circuit_request.Requirement.executable_behavior requirement with
               | Some behavior ->
                   if mapped_actions <> (Circuit_request.Requirement.action_ids requirement |> List.map Identity.Node.to_string |> List.sort String.compare) then fail ("supplementary_action_identity:" ^ id);
                   (try ignore (Lowering_check.check ~expected_request:(Human_request.build_request source) ~behavior)
                    with Diagnostic.Error error -> if String.ends_with ~suffix:"_limit" error.code then raise (Diagnostic.Error error)
                      else fail ("supplementary_source_behavior:" ^ id ^ ":" ^ error.code));
                   let raw_behavior = Circuit_request.Requirement.to_json requirement |> field "behavior" in
                   if Json.array (field "inputs" raw_behavior) <> [] || Circuit_request.Requirement.input_bindings requirement <> [] then unknown ("executable_input_observation_mapping:" ^ id)
               | None ->
                   (match mapped_actions with
                    | [action] ->
                        let rules = List.filter (fun (node:R.node) -> Work_budget.charge budget 1;
                            node.kind = "rule" && List.mem action (match node.inputs with _ :: _ :: values -> values | _ -> []) && Ids.mem node.id requirement_nodes) nodes in
                        (match rules with
                         | [rule] -> legacy := requirement :: !legacy;
                             legacy_bindings := Payload_circuit_binding.make ~requirement_id:id ~rule_id:rule.id ~action_id:action
                               ~signals:(Circuit_request.Requirement.input_bindings requirement |> List.map (fun (key,value) -> key,Identity.Node.to_string value)) :: !legacy_bindings
                         | _ -> fail ("supplementary_rule_mapping:" ^ id))
                    | _ -> fail ("boolean_supplementary_output_mapping:" ^ id)));
              List.iter (fun provider -> unknown ("circuit_provider_mapping:" ^ id ^ ":" ^ Circuit_request.Provider.id provider)) (Circuit_request.Requirement.dependencies requirement)
          | _ -> fail ("supplementary_output_inventory:" ^ id)) requirements;
      if !legacy <> [] then (
        let binding_budget = Circuit_binding_check.make_budget ~parent:budget () in
        let diagnostics = Circuit_binding_check.check ~budget:binding_budget ~source ~requirements:(List.rev !legacy) ~bindings:(List.rev !legacy_bindings) () in
        List.iter (fun diagnostic ->
            if String.starts_with ~prefix:"unsupported:circuit_lifecycle:" diagnostic || String.starts_with ~prefix:"unsupported:circuit_provider_mapping:" diagnostic then ()
            else if String.starts_with ~prefix:"unsupported:" diagnostic then unknown (String.sub diagnostic 12 (String.length diagnostic - 12))
            else if String.starts_with ~prefix:"fail:" diagnostic then fail (String.sub diagnostic 5 (String.length diagnostic - 5)) else fail diagnostic) diagnostics)) in
  result,List.rev !unresolved
let control_checks ~budget request graph (inventories:R.inventories) selected = failures budget (fun fail ->
    let controls = inventories.control_domains and grouped = Hashtbl.create 32 in
    List.iter (fun item ->
        let key = Canonical.encode (strings [text "kind" item;text "domain_id" item]) and meaning = Canonical.fingerprint (field "controlling_node_ids" item) in
        (match Hashtbl.find_opt grouped key with Some previous when previous <> meaning -> fail ("shared_control_input_contradiction:" ^ text "domain_id" item) | _ -> ());
        Hashtbl.replace grouped key meaning) controls;
    let physical = ref Names.empty and source_components = ref Names.empty in
    List.iteri (fun index refinement ->
        let prefix = Printf.sprintf "a%03d_" index in
        let templates = F.templates refinement |> List.sort (fun a b -> String.compare (Payload_template.id a) (Payload_template.id b))
            |> List.mapi (fun offset item -> Payload_template.id item,prefix ^ Printf.sprintf "t%03d_" offset) in
        let placements = List.map (fun item -> C.Placement.id item,item) (F.placements refinement) in
        List.iter (fun binding ->
            let placed = List.map (fun id -> List.assoc id placements) (C.Binding.placement_ids binding) in
            List.iter (fun id -> Work_budget.charge budget 1;
                let source = mapped refinement (Identity.Node.to_string id) in
                physical := map_add !physical source (List.map (fun item -> List.assoc (C.Placement.template_id item) templates ^ C.Placement.member_id item) placed |> set);
                source_components := map_add !source_components source (List.map (fun id -> prefix ^ Identity.Component.to_string id) (C.Binding.component_ids binding) |> set)) (C.Binding.behavior_node_ids binding)) (F.bindings refinement))
      (List.sort (fun a b -> String.compare (F.id a) (F.id b)) selected);
    let helpers = List.map (fun item -> text "id" item,item) inventories.helpers and placements = List.map (fun item -> text "id" item,item) inventories.placements in
    let supply helper =
      let values = if field "provider_component_id" helper <> Json.Null then [str "provider";field "provider_component_id" helper]
        else if field "placement_id" helper <> Json.Null then let placement = List.assoc (text "placement_id" helper) placements in
          [str "direct_rna";field "member_id" placement;field "recipient_role" helper;field "compartment" helper]
        else List.map (fun key -> field key helper) ["availability";"capability";"recipient_role";"compartment"] in
      Canonical.encode (arr values) in
    let dependencies components =
      let pending = List.filter_map (fun (id,helper) -> Work_budget.charge budget 1;
          if overlap (field "consumer_component_ids" helper |> texts |> set) components then Some id else None) helpers in
      let rec visit used = function
        | [] -> Ids.elements used |> List.map (fun id -> supply (List.assoc id helpers)) |> set
        | id :: rest when Ids.mem id used -> Work_budget.charge budget 1; visit used rest
        | id :: rest -> Work_budget.charge budget 1; let helper = List.assoc id helpers in
            let more = if field "provider_component_id" helper = Json.Null then [] else
                List.filter_map (fun (id,other) -> Work_budget.charge budget 1;
                    if List.mem (text "provider_component_id" helper) (texts (field "consumer_component_ids" other)) then Some id else None) helpers in
            visit (Ids.add id used) (texts (field "depends_on" helper) @ more @ rest) in
      visit Ids.empty pending in
    let restricted capabilities = List.filter_map (fun (_,helper) -> Work_budget.charge budget 1;
        if List.mem (text "capability" helper) capabilities then Some (supply helper) else None) helpers |> set in
    let pairs action values = List.iteri (fun left first -> List.iteri (fun right second -> if left < right then (Work_budget.charge budget 1; action first second)) values) values in
    let source = Architecture_request.source request in
    let proof_budget = Architecture_controls_check.make_budget ~parent:budget () in
    List.iter (fun requirement ->
        let refs = C.Control_requirement.behavior_node_ids requirement |> List.map Identity.Node.to_string in
        let id = C.Control_requirement.id requirement and kind = C.Control_requirement.kind requirement in
        let shared = C.Control_requirement.relation requirement = C.Control_requirement.Shared in
        if List.exists (fun id -> R.find graph id = None) refs then fail ("unknown_control_requirement_node:" ^ id)
        else if kind = C.Physical_separation || kind = C.Dependency_disjointness then (
          let materials = List.map (map_get !physical) refs and components = List.map (map_get !source_components) refs in
          if List.exists Ids.is_empty materials then fail ("control_material_missing:" ^ id)
          else if kind = C.Physical_separation then (
            if shared && Ids.is_empty (intersection materials) then fail ("shared_physical_material_missing:" ^ id);
            if not shared then let violated = ref false in pairs (fun a b -> if overlap a b then violated := true) materials;
              if !violated then fail ("physical_separation_violated:" ^ id))
          else (
            let values = List.map dependencies components in
            let values = if C.Control_requirement.forbidden_shared_dependencies requirement = [] then values else
                let allowed = restricted (C.Control_requirement.forbidden_shared_dependencies requirement) in List.map (Ids.inter allowed) values in
            if shared && Ids.is_empty (intersection values) then fail ("shared_dependency_missing:" ^ id);
            if not shared then let violated = ref false in pairs (fun a b -> if overlap a b then violated := true) values;
              if !violated then fail ("forbidden_shared_dependency:" ^ id)))
        else (
          let matching = List.map (fun ref -> ref,List.filter (fun item -> Work_budget.charge budget 1;
              text "kind" item = C.control_kind_name kind && List.mem ref (texts (field "behavior_node_ids" item))) controls) refs in
          if List.exists (fun (_,values) -> values = []) matching then fail ("control_requirement_unbound:" ^ id)
          else (
            let extended = List.mem kind [C.Memory_reset;C.Production_adjustment;C.Activity_control] in
            let targets = List.map (fun ref -> ref,if extended then Architecture_controls_check.extended_targets ~budget:proof_budget ~source ~target:ref ~kind () else [ref]) refs in
            List.iter (fun (ref,values) -> List.iter (fun control ->
                if kind = C.Production_adjustment && not (Ids.subset (List.assoc ref targets |> set) (field "behavior_node_ids" control |> texts |> set)) then fail ("control_production_aggregate_unbound:" ^ id ^ ":" ^ ref);
                let proof = Architecture_controls_check.prove_source ~budget:proof_budget ~source ~target:ref ~controlling_node_ids:(texts (field "controlling_node_ids" control)) ~kind () in
                Option.iter (fun reason -> fail ("unsupported_functional_control_requirement:" ^ id ^ ":" ^ ref ^ ":" ^ reason)) (Architecture_controls_check.reason proof)) values) matching;
            let meanings = List.map (fun (ref,values) ->
                let domains = List.map (text "domain_id") values |> set in
                let components = List.concat_map (fun item -> texts (field "component_ids" item)) values |> set in
                let effects = List.assoc ref targets |> List.map (map_get !source_components) |> union in
                let components = if kind = C.Production_adjustment then Ids.union components effects else components in
                let inputs = List.concat_map (fun item -> texts (field "controlling_node_ids" item)) values |> List.concat_map (R.lineage graph)
                    |> List.filter (fun id -> List.mem (R.lookup graph id).kind ["signal";"channel_observation";"state";"memory"]) |> set in
                let influence = R.causal_nodes graph (List.assoc ref targets) |> set in
                domains,components,effects,inputs,influence) matching in
            if shared then (
              if Ids.is_empty (List.map (fun (domains,_,_,_,_) -> domains) meanings |> intersection) then fail ("shared_control_missing:" ^ id))
            else pairs (fun (ld,lc,le,li,lf) (rd,rc,re,ri,rf) ->
                if overlap ld rd || overlap lc rc then fail ("independent_control_coupled:" ^ id);
                if Ids.is_empty li || Ids.is_empty ri || overlap li ri then fail ("independent_control_inputs_coupled:" ^ id);
                if overlap li rf || overlap ri lf then fail ("independent_control_cross_influence:" ^ id);
                if C.Control_requirement.forbidden_shared_dependencies requirement <> [] then
                  let allowed = restricted (C.Control_requirement.forbidden_shared_dependencies requirement) in
                  if not (Ids.is_empty (intersection [dependencies (Ids.union le lc);dependencies (Ids.union re rc);allowed])) then fail ("forbidden_shared_dependency:" ^ id)) meanings)))
      (C.Constraints.control_requirements (Architecture_request.constraints request)))
let channel_checks ~budget request graph (inventories:R.inventories) = failures budget (fun fail ->
    let observed = ref Ids.empty and receivers = Hashtbl.create 16 in
    let records = R.source_channels graph in
    List.iter (fun channel ->
        Work_budget.charge budget 1;
        let identity = text "id" channel in
        let declaration = R.find graph (text "source_channel_id" channel) and receiver = R.find graph (text "receiver_node_id" channel) in
        let sender = match R.find graph (text "sender_node_id" channel) with
          | Some node when node.kind = "action.pulse" -> Some (R.lookup graph (R.input node 0)) | value -> value in
        match declaration,sender,receiver with
        | Some declaration,Some sender,Some receiver when declaration.kind = "channel" && sender.kind = "action.emit" && receiver.kind = "channel_observation" &&
            R.input sender 1 = declaration.id && R.input receiver 1 = declaration.id && sender.role = Some (text "sender_role" channel) && receiver.role = Some (text "receiver_role" channel) ->
            (try ignore (Type_spec.normalize_binding ~expected:(Type_spec.of_json declaration.data_type) (field "initial_value" channel))
             with Diagnostic.Error error -> if String.ends_with ~suffix:"_limit" error.code then raise (Diagnostic.Error error) else fail ("channel_initial_value:" ^ identity));
            let edge = Canonical.encode (strings [declaration.id;text "sender_node_id" channel;receiver.id]) in
            if Ids.mem edge !observed then fail ("duplicate_channel_transport_edge:" ^ identity);
            observed := Ids.add edge !observed;
            let receiver_key = Canonical.encode (strings [declaration.id;receiver.id]) in
            let contract = Canonical.fingerprint (arr [field "aggregation" channel;field "initial_value" channel]) in
            (match Hashtbl.find_opt receivers receiver_key with Some old when old <> contract -> fail ("inconsistent_channel_receiver_contract:" ^ identity) | _ -> ());
            Hashtbl.replace receivers receiver_key contract;
            let record = List.find (fun (record:R.channel) -> record.channel_id = declaration.id) records in
            if text "aggregation" channel = "single_sender" && List.length record.sender_ids <> 1 then fail ("channel_sender_aggregation:" ^ identity);
            if text "failure_mode" channel = "unknown" then fail ("channel_failure_semantics_unknown:" ^ identity)
        | _ -> fail ("channel_source_correspondence:" ^ identity)) inventories.channels;
    let expected = ref Ids.empty and edge_output = output_budget () in
    List.iter (fun (record:R.channel) -> List.iter (fun sender -> List.iter (fun receiver ->
        Work_budget.charge budget 1;
        let edge = strings [record.channel_id;sender;receiver] in
        Work_budget.reserve_json edge_output edge;
        expected := Ids.add (Canonical.encode edge) !expected) record.receiver_ids) record.sender_ids) records;
    if not (Ids.equal !observed !expected) then fail "channel_link_inventory";
    ignore request)
let delivery_dependency_checks ~budget request (inventories:R.inventories) selected = failures budget (fun fail ->
    let placements = List.map (fun item -> text "id" item,item) inventories.placements in
    let groups = List.map (fun item -> C.Delivery_group.id item,item) (C.Constraints.delivery_groups (Architecture_request.constraints request)) in
    let component_placements = ref Names.empty in
    List.iteri (fun index refinement -> let prefix = Printf.sprintf "a%03d_" index in
        List.iter (fun binding -> List.iter (fun id -> Work_budget.charge budget 1;
            component_placements := map_add !component_placements (prefix ^ Identity.Component.to_string id)
              (List.map (fun id -> prefix ^ id) (C.Binding.placement_ids binding) |> set)) (C.Binding.component_ids binding)) (F.bindings refinement))
      (List.sort (fun a b -> String.compare (F.id a) (F.id b)) selected);
    List.iter (fun helper -> if field "placement_id" helper <> Json.Null then (
        let provider = List.assoc (text "placement_id" helper) placements in
        List.iter (fun consumer -> Ids.iter (fun placement_id -> Work_budget.charge budget 1;
            let consumer = List.assoc placement_id placements in
            if field "recipient_role" provider <> field "recipient_role" consumer then fail ("helper_cross_recipient_supply:" ^ text "id" helper);
            if field "member_id" provider <> field "member_id" consumer then (
              let group = List.assoc_opt (text "delivery_group" provider) groups in
              if field "delivery_group" provider <> field "delivery_group" consumer ||
                 not (Option.fold ~none:false ~some:(fun group -> C.Delivery_group.mode group = C.Delivery_group.Co_delivered && C.Delivery_group.same_recipient group) group)
              then fail ("helper_co_delivery_missing:" ^ text "id" helper))) (map_get !component_placements consumer))
          (texts (field "consumer_component_ids" helper)))) inventories.helpers)
let molecule_checks ~budget request construction bundle (inventories:R.inventories) graph = failures budget (fun fail ->
    let molecules = Molecule_set.molecules bundle |> List.map (fun item -> Molecule.id item,item)
    and complexes = Molecule_set.complexes bundle |> List.map (fun item -> Molecule.Complex.id item,item) in
    let constituents id = match List.assoc_opt id molecules with Some _ -> Ids.singleton id | None ->
      (match List.assoc_opt id complexes with None -> Ids.empty | Some value -> Molecule.Complex.constituents value |> List.map Molecule.Constituent.molecule_id |> set) in
    let delivered = ref Ids.empty in
    List.iter (fun requirement ->
        if List.mem (Construction.Member_requirement.category requirement) [Construction.Member_requirement.Payload;Construction.Member_requirement.Delivered_helper] then (
          let id = Option.value ~default:"None" (Construction.Member_requirement.member_id requirement) in
          let members = constituents id in
          if Ids.is_empty members || Ids.exists (fun id -> Work_budget.charge budget 1;
              match List.assoc_opt id molecules with None -> true | Some molecule -> Molecule_coordinates.Space.alphabet (Molecule.space molecule) <> Molecule_coordinates.Rna) members
          then fail ("delivered_member_not_rna:" ^ id);
          delivered := Ids.union members !delivered)) (Construction.Request.requirements construction);
    List.iter (fun (id,molecule) -> if Molecule_coordinates.Space.alphabet (Molecule.space molecule) = Molecule_coordinates.Dna then fail ("final_dna_member:" ^ id)) molecules;
    let lengths = Ids.elements !delivered |> List.filter_map (fun id -> Option.map (fun molecule -> id,String.length (Molecule.sequence molecule)) (List.assoc_opt id molecules)) in
    let constraints = Architecture_request.constraints request and count = Ids.cardinal !delivered in
    let total = List.fold_left (fun sum (_,value) -> sum + value) 0 lengths in
    Option.iter (fun expected -> if count <> expected then fail "exact_rna_count") (C.Constraints.exact_count constraints);
    Option.iter (fun maximum -> if count > maximum then fail "maximum_rna_count") (C.Constraints.max_count constraints);
    Option.iter (fun maximum -> if List.exists (fun (_,length) -> length > maximum) lengths then fail "maximum_rna_member_length") (C.Constraints.max_member_bases constraints);
    Option.iter (fun maximum -> if total > maximum then fail "maximum_rna_total_length") (C.Constraints.max_total_bases constraints);
    let groups = C.Constraints.delivery_groups constraints in
    let roles = R.nodes graph |> List.filter (fun (node:R.node) -> node.kind = "role") |> List.map (fun node -> node.id) |> set in
    let group_members = ref Names.empty and group_roles = ref Names.empty in
    List.iter (fun placement ->
        Work_budget.charge budget 1;
        let id = text "member_id" placement in
        if not (List.mem_assoc id molecules || List.mem_assoc id complexes) then fail ("placement_member_missing:" ^ id);
        if not (Ids.mem (text "recipient_role" placement) roles) then fail ("placement_recipient_unknown:" ^ text "id" placement);
        if not (List.exists (fun item -> Work_budget.charge budget 1;
            Molecule.Role.subject_id item = id && Molecule.Role.compartment item = text "compartment" placement && Molecule.Role.role item = text "recipient_role" placement) (Molecule_set.role_instances bundle))
        then fail ("placement_molecular_compartment:" ^ text "id" placement);
        match List.find_opt (fun group -> C.Delivery_group.id group = text "delivery_group" placement) groups with
        | None -> fail ("delivery_group_missing:" ^ text "delivery_group" placement)
        | Some group ->
            if not (List.exists (fun role -> Identity.Role.to_string role = text "recipient_role" placement) (C.Delivery_group.recipient_roles group)) then fail ("delivery_group_recipient:" ^ text "id" placement);
            group_members := map_add !group_members (C.Delivery_group.id group) (Ids.inter (constituents id) !delivered);
            group_roles := map_add !group_roles (C.Delivery_group.id group) (Ids.singleton (text "recipient_role" placement))) inventories.placements;
    List.iter (fun group ->
        Work_budget.charge budget 1;
        let id = C.Delivery_group.id group in let members = map_get !group_members id in
        if not (Ids.subset (List.map Identity.Role.to_string (C.Delivery_group.recipient_roles group) |> set) roles) then fail ("delivery_group_unknown_source_role:" ^ id);
        if C.Delivery_group.same_recipient group && Ids.cardinal (map_get !group_roles id) > 1 then fail ("delivery_group_same_recipient_conflict:" ^ id);
        Option.iter (fun expected -> if Ids.cardinal members <> expected then fail ("delivery_group_exact_count:" ^ id)) (C.Delivery_group.exact_count group);
        Option.iter (fun maximum -> if Ids.cardinal members > maximum then fail ("delivery_group_maximum_count:" ^ id)) (C.Delivery_group.max_count group);
        Option.iter (fun maximum -> let length = Ids.fold (fun id total -> Work_budget.charge budget 1; total + List.assoc id lengths) members 0 in
            if length > maximum then fail ("delivery_group_maximum_length:" ^ id)) (C.Delivery_group.max_total_bases group)) groups)
let unique values =
  let seen = Hashtbl.create 64 in List.filter (fun value -> if Hashtbl.mem seen value then false else (Hashtbl.add seen value (); true)) values
let check ?budget ~expected_request build =
  let budget = match budget with None -> make_budget () | Some parent -> make_budget ~parent () in
  let request = Architecture_request.of_json (Architecture_request.to_json expected_request) in
  let build = B.of_json (B.to_json build) in
  let unresolved = ref [] and assumptions = ref [] and construction_complete = ref false in
  let output = output_budget () and unresolved_seen = Hashtbl.create 64 in
  let errors = failures budget (fun fail ->
      let extend values = List.iter fail values in
      let unknown value = Work_budget.charge budget (String.length value + 1);
        if not (Hashtbl.mem unresolved_seen value) then (
          Work_budget.reserve_json output (str value); Hashtbl.add unresolved_seen value (); unresolved := value :: !unresolved) in
      try
        if B.request_fingerprint build <> Architecture_request.fingerprint request then fail "request_authority";
        let source = Architecture_request.source request and manifest = B.execution build in
        let checked_source = Source_check.check ~expected_source:source ~manifest in
        extend checked_source.failures; List.iter unknown checked_source.unresolved;
        (match B.plan build with
         | None -> unknown "search_outcome_not_independently_replayed";
             if B.construction build <> None then fail "construction_without_selected_architecture"
         | Some plan ->
             let selected,selection_failures = R.selected_instances ~budget build request in
             extend selection_failures;
             assumptions := R.assumptions request selected;
             Work_budget.reserve_json output (strings !assumptions);
             if B.Plan.assumptions plan <> !assumptions then fail "plan_assumptions";
             let behavior = Source_execution_manifest.behavior manifest in
             (match behavior with None -> fail "selected_architecture_without_executable_source"
              | Some behavior -> List.iter (fun refinement ->
                  refinement_checks ~budget refinement behavior (target request) |> List.iter (fun value -> fail (F.id refinement ^ ":" ^ value))) selected);
             let inventories,documents = R.inventories ~budget selected in
             List.iter (fun (key,actual,expected) -> if not (Json.equal (arr actual) (arr expected)) then fail ("plan_" ^ key))
               ["placements",B.Plan.placements plan,inventories.placements;"helpers",B.Plan.helpers plan,inventories.helpers;
                "channels",B.Plan.channels plan,inventories.channels;"control_domains",B.Plan.control_domains plan,inventories.control_domains;
                "availability",B.Plan.availability plan,inventories.availability];
             let graph = R.source_graph ~budget source in
             let source_complete = behavior <> None && checked_source.unresolved = [] && checked_source.failures = [] in
             let ledger,owners = R.expected_ledger ~budget request graph selected ~assumptions:!assumptions ~source_complete in
             if not (Json.equal (arr (List.map B.Requirement_realization.to_json (B.Plan.ledger plan)))
                       (arr (List.map B.Requirement_realization.to_json ledger))) then fail "plan_requirement_ledger";
             List.iter (fun (node:R.node) -> if R.runtime node && List.length (Option.value ~default:[] (List.assoc_opt node.id owners)) > 1 then fail ("duplicate_runtime_ownership:" ^ node.id)) (R.nodes graph);
             List.iter (fun item -> if B.Requirement_realization.status item = B.Requirement_realization.Unresolved then unknown (B.Requirement_realization.id item)) ledger;
             let extra_failures,extra_unresolved = supplementary_checks ~budget request graph selected in
             extend extra_failures; List.iter unknown extra_unresolved;
             extend (control_checks ~budget request graph inventories selected);
             extend (channel_checks ~budget request graph inventories);
             extend (delivery_dependency_checks ~budget request inventories selected);
             let deployment_budget = Architecture_deployment_check.make_budget ~parent:budget () in
             let deployment_inventory = Architecture_deployment_check.Inventory.make ~placements:inventories.placements ~availability:inventories.availability in
             extend (Architecture_deployment_check.check ~budget:deployment_budget ~request ~inventory:deployment_inventory ()).failures;
             let expected_construction = R.expected_construction ~budget request documents in
             (match B.construction build with
              | None -> unknown "complete_construction_missing"
              | Some construction ->
                  if Construction.Request.fingerprint (Construction_build.request construction) <> Construction.Request.fingerprint expected_construction then fail "construction_template_authority";
                  let candidate = Construction_build.candidate construction in
                  let assessment = Construction_check.check ~expected_request:expected_construction candidate in
                  if Construction_assessment.fingerprint assessment <> Construction_assessment.fingerprint (Construction_build.assessment construction) then fail "construction_assessment_replay";
                  if not (Construction_assessment.passed assessment) then fail "exact_construction_reconstruction"
                  else if not (Construction_assessment.complete assessment) then unknown "complete_construction_missing";
                  (match Construction_artifact.bundle candidate with
                   | None -> unknown "molecule_bundle_missing"
                   | Some bundle ->
                       let molecule_failures = molecule_checks ~budget request expected_construction bundle inventories graph in
                       extend molecule_failures;
                       construction_complete := Construction_assessment.passed assessment && Construction_assessment.complete assessment && molecule_failures = []));
             if C.Constraints.require_complete (Architecture_request.constraints request) && !unresolved <> [] then fail "strict_completeness_violated")
      with
      | Diagnostic.Error error -> if String.ends_with ~suffix:"_limit" error.code then raise (Diagnostic.Error error)
          else fail ("malformed_architecture:" ^ error.code)
      | Not_found -> fail "malformed_architecture:missing_reference") in
  let unresolved = unique (List.rev !unresolved) in
  let complete = B.plan build <> None && !construction_complete && errors = [] && unresolved = [] in
  let errors = if B.status build = B.Compiled && not complete then errors @ ["compiled_status_without_complete_translation"] else errors in
  let construction_complete = errors = [] && !construction_complete in
  let candidates = match B.plan build with None -> [] | Some plan -> B.Plan.selected_refinement_ids plan in
  let diagnostics = List.map (fun code -> Work_budget.charge budget (String.length code + List.length candidates + 1);
      let fields = ["schema_version",str B.Gap.schema_version;"category",str "independent_verification_failure";
        "code",str code;"requirement_ids",arr [];"candidate_ids",strings candidates;
        "message",str ("Independent architecture check rejected " ^ code ^ ".");"conflict_set",arr []] in
      let raw = obj fields in Work_budget.reserve_json output raw; B.Gap.of_json raw) errors in
  E.make ~request_fingerprint:(Architecture_request.fingerprint request) ~build_fingerprint:(B.fingerprint build)
    ~outcome:(if errors = [] then E.Pass else E.Fail) ~translation_complete:complete ~construction_complete ~diagnostics ~unresolved ~assumptions:!assumptions
let replay ?budget ~expected_request ~build assessment =
  let saved = E.of_json (E.to_json assessment) in
  let fresh = check ?budget ~expected_request build in
  Diagnostic.require (E.fingerprint saved = E.fingerprint fresh) "architecture_assessment_mismatch" "Architecture assessment differs from fresh complete authority replay.";
  fresh

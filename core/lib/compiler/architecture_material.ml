open Bioc_wire
open Bioc_domain
module R = Architecture_refinement
module A = Architecture_contract
module B = Architecture_build
module Names = Map.Make (String)
module Ids = Set.Make (String)
let str value = Json.String value
let field key raw = Json.field key (Json.object_fields raw)
let replace replacements raw = Json.Object (List.map (fun (key, value) -> key, Option.value ~default:value (List.assoc_opt key replacements)) (Json.object_fields raw))
let bindings refinement = R.source_bindings refinement |> List.map (fun (left, right) -> Identity.Node.to_string left, Identity.Node.to_string right)
let source refinement identity = List.assoc identity (bindings refinement)
let runtime node = let kind = Behavior.kind_name (Behavior.operation node) in List.mem kind ["rule"; "state"; "memory"] || String.starts_with ~prefix:"action." kind
let sorted_templates refinement = List.sort (fun left right -> String.compare (Payload_template.id left) (Payload_template.id right)) (R.templates refinement)
let output_budget () = Bioc_checker.Work_budget.create_output ~profile:"biocompiler.architecture_material.resources.v1"
    ~error_code:"architecture_material_output_limit" ~max_bytes:(16 * 1024 * 1024) ~max_nodes:250_000 ()
let namespace_template template prefix =
  ignore (Molecular_record.text ~maximum:64 (str prefix));
  let frames = List.map (fun source -> Construction.Root_source.molecule source |> Molecule.space |> Molecule_coordinates.Space.id |> Molecule_coordinates.Space_id.to_string) (Payload_template.sources template)
      @ List.concat_map (fun step -> Construction.Transform_step.ports step |> List.map Construction.Product_port.space_id) (Payload_template.steps template)
      @ List.map Construction.Output_member.space_id (Payload_template.output_members template) |> Ids.of_list in
  let local_schemas = List.map (fun name -> "biocompiler." ^ name ^ ".v0.1") ["payload_template"; "construction_root_source"; "circuit_molecule";
      "construction_transform_step"; "construction_product_port"; "construction_value_ref"; "construction_output_member";
      "construction_member_requirement"; "construction_role_declaration"; "construction_complex_member"; "construction_amount_declaration"] in
  let budget = output_budget () in
  let retain raw = Bioc_checker.Work_budget.reserve_json budget raw; raw in
  let rec rename = function
    | Json.Array values -> Json.Array (List.map rename values)
    | Json.Object fields as original ->
        let schema = Option.value ~default:Json.Null (List.assoc_opt "schema_version" fields) in
        if schema = str Molecular_record.Provenance.schema_version then original
        else (
          let emitted = List.map (fun (key, value) -> key, rename value) fields in
          let set key value fields = (key, retain value) :: List.remove_assoc key fields in
          let emitted = if List.mem schema (List.map str local_schemas)
              || (schema = str "biocompiler.molecule_coordinate_space.v0.1" && Ids.mem (Json.string (field "id" original)) frames)
            then set "id" (str (prefix ^ Json.string (field "id" original))) emitted else emitted in
          let emitted = match List.assoc_opt "space_id" fields with Some (Json.String identity) when Ids.mem identity frames -> set "space_id" (str (prefix ^ identity)) emitted | _ -> emitted in
          let emitted = List.fold_left (fun emitted key -> match List.assoc_opt key fields with Some value when value <> Json.Null -> set key (str (prefix ^ Json.string value)) emitted | _ -> emitted) emitted ["member_id"; "port_id"] in
          let emitted = if List.mem schema [str "biocompiler.chemistry_disposition.v0.1"; str "biocompiler.feature_disposition.v0.1"]
            then set "source_id" (str (prefix ^ Json.string (field "source_id" original))) emitted else emitted in
          let emitted = if schema = str "biocompiler.construction_amount_declaration.v0.1" then (
              let emitted = List.fold_left (fun emitted key -> set key (str (prefix ^ Json.string (field key original))) emitted) emitted ["subject_id"; "preparation_id"] in
              set "role_instance_ids" (Json.array (field "role_instance_ids" original) |> List.map (fun value -> str (prefix ^ Json.string value)) |> fun values -> Json.Array values) emitted) else emitted in
          Json.Object emitted)
    | value -> value in
  let result = rename (Payload_template.to_json template) in
  ignore (retain result); Payload_template.of_json result
let construction_request selected request =
  let budget = output_budget () in
  let templates = List.mapi (fun index refinement ->
      let roles = Behavior.nodes (R.behavior refinement) |> List.filter (fun node -> Behavior.kind_name (Behavior.operation node) = "role")
        |> List.map (fun node -> Identity.Node.to_string (Behavior.node_id node)) |> Ids.of_list in
      List.mapi (fun number template ->
          let raw = Payload_template.to_json template in
          let requirements = Json.array (field "requirements" raw) |> List.map (fun requirement ->
              let roles = Json.array (field "roles" requirement) |> List.map (fun role ->
                  let identity = Json.string (field "role" role) in if Ids.mem identity roles then replace ["role", str (source refinement identity)] role else role) in
              replace ["roles", Json.Array roles] requirement) in
          let template = replace ["requirements", Json.Array requirements] raw |> Payload_template.of_json in
          let result = namespace_template template (Printf.sprintf "a%03d_t%03d_" index number) in
          Bioc_checker.Work_budget.reserve_json budget (Payload_template.to_json result); result) (sorted_templates refinement)) selected |> List.concat in
  Diagnostic.require (List.length templates <= 256) "invalid_architecture_templates" "Invalid selected template inventory.";
  Construction.Request.make ~id:(Architecture_request.id request ^ ".construction") ~circuit:(Architecture_request.circuit request)
    ~sources:(List.concat_map Payload_template.sources templates) ~steps:(List.concat_map Payload_template.steps templates)
    ~output_members:(List.concat_map Payload_template.output_members templates) ~requirements:(List.concat_map Payload_template.requirements templates)
    ~complex_members:(List.concat_map Payload_template.complex_members templates) ~amounts:(List.concat_map Payload_template.amounts templates)
    ~payload_structures:(List.concat_map Payload_template.payload_structures templates) ~mode:Construction.Request.Strict ()

let plan selected execution request instances =
  let budget = output_budget () in
  let retain raw = Bioc_checker.Work_budget.reserve_json budget raw; raw in
  let placements = ref [] and helpers = ref [] and channels = ref [] and controls = ref [] and availability = ref [] in
  let assumptions = ref (Ids.of_list (R.Library.assumptions (Architecture_request.library request))) in
  let add_assumptions values = assumptions := List.fold_left (fun result item -> Ids.add item result) !assumptions values in
  let constraints = Architecture_request.constraints request in
  List.iter (fun group -> add_assumptions (A.Delivery_group.assumptions group)) (A.Constraints.delivery_groups constraints);
  List.iter (fun requirement -> add_assumptions (Architecture_deployment.Requirement.assumptions requirement)) (A.Constraints.deployment_requirements constraints);
  List.iteri (fun index refinement ->
      let prefix = Printf.sprintf "a%03d_" index in
      let template_prefixes = sorted_templates refinement |> List.mapi (fun number template -> Payload_template.id template, prefix ^ Printf.sprintf "t%03d_" number) in
      let remap value = str (source refinement (Json.string value)) in
      let local value = match value with Json.Null -> Json.Null | value -> str (prefix ^ Json.string value) in
      let locals value = Json.Array (Json.array value |> List.map local) in
      let sources value = Json.Array (Json.array value |> List.map remap) in
      add_assumptions (R.assumptions refinement);
      List.iter (fun contract ->
          let raw = Architecture_deployment.Availability.to_json contract in
          availability := retain (replace ["id", local (field "id" raw); "placement_id", local (field "placement_id" raw)] raw) :: !availability;
          add_assumptions (Architecture_deployment.Availability.assumptions contract)) (R.availability refinement);
      List.iter (fun component -> add_assumptions (Component.assumptions component)) (R.components refinement);
      List.iter (fun placement ->
          let raw = A.Placement.to_json placement in
          let template_prefix = List.assoc (A.Placement.template_id placement) template_prefixes in
          placements := retain (replace ["id", local (field "id" raw); "template_id", str (template_prefix ^ A.Placement.template_id placement);
            "member_id", str (template_prefix ^ A.Placement.member_id placement); "recipient_role", remap (field "recipient_role" raw)] raw) :: !placements) (R.placements refinement);
      List.iter (fun helper ->
          let raw = A.Helper.to_json helper in
          helpers := retain (replace ["id", local (field "id" raw); "recipient_role", remap (field "recipient_role" raw);
            "consumer_component_ids", locals (field "consumer_component_ids" raw); "placement_id", local (field "placement_id" raw);
            "provider_component_id", local (field "provider_component_id" raw); "depends_on", locals (field "depends_on" raw)] raw) :: !helpers;
          add_assumptions (A.Helper.assumptions helper)) (R.helpers refinement);
      List.iter (fun channel ->
          let raw = A.Channel.to_json channel in
          let changes = ("id", local (field "id" raw)) :: List.map (fun key -> key, remap (field key raw)) ["source_channel_id"; "sender_role"; "receiver_role"; "sender_node_id"; "receiver_node_id"] in
          channels := retain (replace changes raw) :: !channels; add_assumptions (A.Channel.assumptions channel)) (R.channels refinement);
      List.iter (fun control ->
          let raw = A.Control.to_json control in
          controls := retain (replace ["id", local (field "id" raw); "domain_id", local (field "domain_id" raw);
            "behavior_node_ids", sources (field "behavior_node_ids" raw); "controlling_node_ids", sources (field "controlling_node_ids" raw);
            "component_ids", locals (field "component_ids" raw)] raw) :: !controls;
          add_assumptions (A.Control.assumptions control)) (R.controls refinement)) selected;
  let all_assumptions = Ids.elements !assumptions and identifiers = List.map R.id selected in
  let coverage = List.map (fun refinement -> R.id refinement, Ids.of_list (List.map snd (bindings refinement))) selected in
  let all_covered = List.fold_left (fun values (_, covered) -> Ids.union values covered) Ids.empty coverage in
  let owned = List.fold_left (fun counts refinement -> List.fold_left (fun counts local ->
      let identity = source refinement (Identity.Node.to_string local) in
      Names.add identity (1 + Option.value ~default:0 (Names.find_opt identity counts)) counts) counts (R.owned_node_ids refinement)) Names.empty selected in
  let behavior = match Source_execution_manifest.behavior execution with Some value -> value
    | None -> Diagnostic.fail "invalid_architecture_material" "A candidate plan requires executable source behavior." in
  let runtime_ids = Behavior.nodes behavior |> List.filter runtime |> List.map (fun node -> Identity.Node.to_string (Behavior.node_id node)) |> Ids.of_list in
  let make ~id ~source_node_ids ~refinement_ids ~status ~assumptions ~reasons =
    let value = B.Requirement_realization.make ~id ~source_node_ids ~refinement_ids ~status ~assumptions ~reasons in
    ignore (retain (B.Requirement_realization.to_json value)); value in
  let ledger = Source_execution_manifest.ledger execution |> List.map (fun original ->
      let node_ids = Json.array (field "source_node_ids" original) |> List.map Json.string in
      let members = Ids.of_list node_ids in
      let realizers = List.filter_map (fun (identity, covered) -> if Ids.is_empty (Ids.inter members covered) then None else Some identity) coverage in
      let complete = Ids.subset members all_covered && Ids.for_all (fun identity -> Names.find_opt identity owned = Some 1) (Ids.inter members runtime_ids) in
      let reasons = if complete then [] else ["uncovered_source_requirements"] in
      let complete, reasons = if field "id" original = str "source:complete_authority" && not (Source_execution_manifest.complete execution)
        then false, ["unresolved_source_obligations"] else complete, reasons in
      let assumptions = List.filter (fun refinement -> List.mem (R.id refinement) realizers) selected |> List.concat_map R.assumptions |> Ids.of_list |> Ids.elements in
      make ~id:(Json.string (field "id" original)) ~source_node_ids:node_ids ~refinement_ids:realizers
        ~status:(if complete then B.Requirement_realization.Implemented else B.Requirement_realization.Unresolved) ~assumptions ~reasons) in
  let constraint_row identity nodes = make ~id:identity ~source_node_ids:nodes ~refinement_ids:identifiers ~status:B.Requirement_realization.Implemented ~assumptions:all_assumptions ~reasons:[] in
  let fields = A.Constraints.to_json constraints |> Json.object_fields |> List.filter_map (fun (key, _) -> if key = "schema_version" then None else Some (constraint_row ("constraint:" ^ key) [])) in
  let control_rows = A.Constraints.control_requirements constraints |> List.map (fun control -> constraint_row ("constraint:control:" ^ A.Control_requirement.id control) (A.Control_requirement.behavior_node_ids control |> List.map Identity.Node.to_string)) in
  let group_rows = A.Constraints.delivery_groups constraints |> List.map (fun group -> constraint_row ("constraint:delivery:" ^ A.Delivery_group.id group) (A.Delivery_group.recipient_roles group |> List.map Identity.Role.to_string)) in
  let deployment_rows = A.Constraints.deployment_requirements constraints |> List.map (fun requirement -> constraint_row ("constraint:deployment:" ^ Architecture_deployment.Requirement.id requirement) [Architecture_deployment.Requirement.recipient_role requirement]) in
  B.Plan.make ~selected_refinement_ids:identifiers ~ledger:(ledger @ fields @ control_rows @ group_rows @ deployment_rows)
    ~placements:(List.rev !placements) ~helpers:(List.rev !helpers) ~channels:(List.rev !channels)
    ~control_domains:(List.rev !controls) ~assumptions:all_assumptions ~instances ~availability:(List.rev !availability)

let delivered construction = match Construction_artifact.bundle (Construction_build.candidate construction) with
  | None -> []
  | Some bundle ->
      let molecules = List.fold_left (fun map value -> Names.add (Molecule.id value) value map) Names.empty (Molecule_set.molecules bundle)
      and complexes = List.fold_left (fun map value -> Names.add (Molecule.Complex.id value) value map) Names.empty (Molecule_set.complexes bundle) in
      let identities = Construction.Request.requirements (Construction_build.request construction) |> List.fold_left (fun found requirement ->
          if List.mem (Construction.Member_requirement.category_name (Construction.Member_requirement.category requirement)) ["payload"; "delivered_helper"] then
            match Construction.Member_requirement.member_id requirement with
            | Some identity when Names.mem identity molecules -> Ids.add identity found
            | Some identity -> (match Names.find_opt identity complexes with None -> found | Some value ->
                List.fold_left (fun found part -> Ids.add (Molecule.Constituent.molecule_id part) found) found (Molecule.Complex.constituents value))
            | None -> found
          else found) Ids.empty in
      Ids.elements identities |> List.filter_map (fun identity -> Names.find_opt identity molecules)

open Bioc_wire
module C = Construction
module M = Molecular_record
module N = Molecule
module G = Molecule_coordinates
module Ids = Set.Make (String)
module Names = Map.Make (String)
type t = {
  id : string;
  sources : C.Root_source.t list;
  steps : C.Transform_step.t list;
  output_members : C.Output_member.t list;
  requirements : C.Member_requirement.t list;
  complex_members : C.Complex_member.t list;
  amounts : C.Amount_declaration.t list;
  payload_structures : Payload_structure.t list;
}
let schema_version = "biocompiler.payload_template.v0.1"
let require ?path condition message = Diagnostic.require ?path condition "invalid_payload_template" message
let str value = Json.String value
let array encode values = Json.Array (List.map encode values)
let to_json (value : t) = Json.Object ["schema_version",str schema_version;"id",str value.id;
    "sources",array C.Root_source.to_json value.sources; "steps",array C.Transform_step.to_json value.steps;
    "output_members",array C.Output_member.to_json value.output_members;
    "requirements",array C.Member_requirement.to_json value.requirements;
    "complex_members",array C.Complex_member.to_json value.complex_members;
    "amounts",array C.Amount_declaration.to_json value.amounts;
    "payload_structures",array Payload_structure.to_json value.payload_structures]
let sorted ~path ?(nonempty = false) key values =
  require ~path (not nonempty || values <> []) "Required template inventory is empty.";
  let values = List.sort (fun left right -> String.compare (key left) (key right)) values in
  let rec unique = function first :: (second :: _ as rest) ->
      require ~path (key first <> key second) "Duplicate template inventory identity."; unique rest
    | _ -> () in
  unique values; values
let records ~path ~maximum (decode : ?path:string -> Json.t -> 'a) value =
  M.array ~path ~maximum value |> List.mapi (fun index -> decode ~path:(path ^ "/" ^ string_of_int index))
let validate ~path value =
  require ~path (List.fold_left (fun total source -> total + String.length (N.sequence (C.Root_source.molecule source))) 0 value.sources <= C.max_total_source_residues)
    "Template source residue limit exceeded.";
  require ~path (List.fold_left (fun total step -> total + List.length (C.Transform_step.ports step)) 0 value.steps <= C.max_products)
    "Template product limit exceeded.";
  let available = ref Names.empty and frames = ref Ids.empty in
  List.iter (fun source ->
      let frame = G.Space_id.to_string (G.Space.id (N.space (C.Root_source.molecule source))) in
      require ~path (not (Ids.mem frame !frames)) "Template roots require unique coordinate frames.";
      frames := Ids.add frame !frames;
      available := Names.add (C.Root_source.id source) (C.Value_ref.Root,frame) !available) value.sources;
  let reference ref =
    match Names.find_opt (C.Value_ref.id ref) !available with
    | Some (kind,frame) when kind = C.Value_ref.kind ref -> frame
    | _ -> Diagnostic.fail ~path "invalid_payload_template" "Template refers to an absent, forward or wrongly categorized value." in
  List.iter (fun step ->
      List.iter (fun selection ->
          let frame = reference (C.Selection.value selection) in
          Option.iter (fun path_value -> require ~path (G.Space_id.to_string (G.Path.space_id path_value) = frame)
              "Template selection uses a different coordinate frame.") (C.Selection.path selection))
        (C.operation_selections (C.Transform_step.operation step));
      List.iter (fun port ->
          require ~path (not (Names.mem (C.Product_port.id port) !available)) "Duplicate template product value identity.";
          require ~path (not (Ids.mem (C.Product_port.space_id port) !frames)) "Duplicate template product coordinate frame.";
          available := Names.add (C.Product_port.id port) (C.Value_ref.Product,C.Product_port.space_id port) !available;
          frames := Ids.add (C.Product_port.space_id port) !frames) (C.Transform_step.ports step)) value.steps;
  let members = List.fold_left (fun ids member -> Ids.add (C.Output_member.id member) ids) Ids.empty value.output_members
  and complexes = List.fold_left (fun ids member -> Ids.add (C.Complex_member.id member) ids) Ids.empty value.complex_members in
  require ~path (Ids.is_empty (Ids.inter members complexes)) "Template member and complex identities collide.";
  List.iter (fun member ->
      ignore (reference (C.Output_member.value member));
      require ~path (not (Ids.mem (C.Output_member.space_id member) !frames)) "Duplicate template output coordinate frame.";
      frames := Ids.add (C.Output_member.space_id member) !frames) value.output_members;
  List.iter (fun complex -> List.iter (fun member ->
      require ~path (Ids.mem (C.Complex_constituent.member_id member) members) "Template complex refers to an absent covalent member.")
      (C.Complex_member.constituents complex)) value.complex_members;
  let demanded = ref (List.fold_left (fun ids member ->
      let ref = C.Output_member.value member in
      if C.Value_ref.kind ref = C.Value_ref.Product then Ids.add (C.Value_ref.id ref) ids else ids) Ids.empty value.output_members) in
  List.iter (fun step ->
      require ~path (List.for_all (fun port -> Ids.mem (C.Product_port.id port) !demanded) (C.Transform_step.ports step))
        "Every template product must contribute to an output member.";
      List.iter (fun selection -> let ref = C.Selection.value selection in
          if C.Value_ref.kind ref = C.Value_ref.Product then demanded := Ids.add (C.Value_ref.id ref) !demanded)
        (C.operation_selections (C.Transform_step.operation step))) (List.rev value.steps);
  let subjects = Ids.union members complexes and covered = ref Ids.empty and roles = ref Names.empty in
  List.iter (fun requirement ->
      Option.iter (fun member -> require ~path (Ids.mem member subjects) "Template requirement names an absent member.";
          covered := Ids.add member !covered) (C.Member_requirement.member_id requirement);
      List.iter (fun role ->
          require ~path (not (Names.mem (C.Role.id role) !roles)) "Duplicate template role identity.";
          roles := Names.add (C.Role.id role) (C.Member_requirement.member_id requirement) !roles)
        (C.Member_requirement.roles requirement)) value.requirements;
  require ~path (Names.cardinal !roles <= C.max_role_declarations) "Template role limit exceeded.";
  require ~path (Ids.equal !covered subjects) "Every template member needs an explicit requirement disposition.";
  let preparations = Hashtbl.create C.max_amount_declarations in
  List.iter (fun amount ->
      let subject = C.Amount_declaration.subject_id amount in
      require ~path (Ids.mem subject subjects && List.for_all (fun role -> Names.find_opt role !roles = Some (Some subject))
          (C.Amount_declaration.role_instance_ids amount)) "Template amount must retain its member and role identities.";
      let key = C.Amount_declaration.preparation_id amount,subject in
      require ~path (not (Hashtbl.mem preparations key)) "Duplicate template preparation amount.";
      Hashtbl.add preparations key ()) value.amounts;
  require ~path (List.for_all (fun contract -> Ids.mem (Payload_structure.member_id contract) members) value.payload_structures)
    "Template payload structure names an absent covalent member."
let of_json ?(path = "") raw =
  let fields = M.record ~path schema_version ["id";"sources";"steps";"output_members";"requirements";"complex_members";"amounts";"payload_structures"] raw in
  let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
  let sources = records ~path:(path ^ "/sources") ~maximum:C.max_sources C.Root_source.of_json (get "sources") |> sorted ~path ~nonempty:true C.Root_source.id
  and steps = records ~path:(path ^ "/steps") ~maximum:C.max_steps C.Transform_step.of_json (get "steps")
  and output_members = records ~path:(path ^ "/output_members") ~maximum:C.max_output_members C.Output_member.of_json (get "output_members") |> sorted ~path ~nonempty:true C.Output_member.id
  and requirements = records ~path:(path ^ "/requirements") ~maximum:C.max_member_requirements C.Member_requirement.of_json (get "requirements") |> sorted ~path ~nonempty:true C.Member_requirement.id
  and complex_members = records ~path:(path ^ "/complex_members") ~maximum:C.max_complex_members C.Complex_member.of_json (get "complex_members") |> sorted ~path C.Complex_member.id
  and amounts = records ~path:(path ^ "/amounts") ~maximum:C.max_amount_declarations C.Amount_declaration.of_json (get "amounts") |> sorted ~path C.Amount_declaration.id
  and payload_structures = records ~path:(path ^ "/payload_structures") ~maximum:Payload_structure.max_contracts Payload_structure.of_json (get "payload_structures") |> sorted ~path Payload_structure.member_id in
  ignore (sorted ~path C.Transform_step.id steps);
  let value = {id = M.text ~path:(path ^ "/id") (get "id"); sources;steps;output_members;requirements;complex_members;amounts;payload_structures} in
  validate ~path value; M.check_resources ~path (to_json value); value
let make ?(complex_members = []) ?(amounts = []) ?(payload_structures = []) ~id ~sources ~steps ~output_members ~requirements () =
  ignore (M.bounded_length ~maximum:C.max_sources sources); ignore (M.bounded_length ~maximum:C.max_steps steps);
  ignore (M.bounded_length ~maximum:C.max_output_members output_members); ignore (M.bounded_length ~maximum:C.max_member_requirements requirements);
  ignore (M.bounded_length ~maximum:C.max_complex_members complex_members); ignore (M.bounded_length ~maximum:C.max_amount_declarations amounts);
  ignore (M.bounded_length ~maximum:Payload_structure.max_contracts payload_structures);
  let nodes = ref 1 and bytes = ref 2 in
  let reserve encode values = List.iter (fun value ->
      let raw = encode value in
      bytes := !bytes + M.pretty_size raw;
      Diagnostic.require (!bytes <= M.max_json_bytes) "molecular_resource_limit" "Template children exceed aggregate publication budget.";
      let pending = ref [raw] in
      while !pending <> [] do
        let raw = List.hd !pending in pending := List.tl !pending; incr nodes;
        Diagnostic.require (!nodes <= M.max_items) "molecular_resource_limit" "Template children exceed aggregate item budget.";
        match raw with
        | Json.Object fields -> nodes := !nodes + List.length fields; pending := List.rev_append (List.map snd fields) !pending
        | Json.Array values -> pending := List.rev_append values !pending
        | _ -> ()
      done) values in
  reserve C.Root_source.to_json sources; reserve C.Transform_step.to_json steps;
  reserve C.Output_member.to_json output_members; reserve C.Member_requirement.to_json requirements;
  reserve C.Complex_member.to_json complex_members; reserve C.Amount_declaration.to_json amounts;
  reserve Payload_structure.to_json payload_structures;
  of_json (to_json {id;sources;steps;output_members;requirements;complex_members;amounts;payload_structures})
let fingerprint value = Canonical.fingerprint (to_json value)
let id (value : t) = value.id
let sources (value : t) = value.sources
let steps (value : t) = value.steps
let output_members (value : t) = value.output_members
let requirements (value : t) = value.requirements
let complex_members (value : t) = value.complex_members
let amounts (value : t) = value.amounts
let payload_structures (value : t) = value.payload_structures
let requested_id id fallback = match id with None | Some "" -> fallback | Some value -> value
let from_construction_request ?id request = make ~id:(requested_id id (C.Request.id request)) ~sources:(C.Request.sources request)
    ~steps:(C.Request.steps request) ~output_members:(C.Request.output_members request) ~requirements:(C.Request.requirements request)
    ~complex_members:(C.Request.complex_members request) ~amounts:(C.Request.amounts request) ~payload_structures:(C.Request.payload_structures request) ()
let to_construction_request ?id ?(mode = C.Request.Strict) template circuit =
  C.Request.make ~id:(requested_id id template.id) ~circuit ~sources:template.sources ~steps:template.steps
    ~output_members:template.output_members ~requirements:template.requirements ~complex_members:template.complex_members
    ~amounts:template.amounts ~payload_structures:template.payload_structures ~mode ()

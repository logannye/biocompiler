open Bioc_wire
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module A = Bioc_checker.Policy_admission
let str value = Json.String value
let lower (admitted:A.t) =
  let document=A.document admitted and descriptors=A.descriptors admitted in
  let assessment=A.source_assessment admitted in
  let nodes=List.map (fun (declaration:D.declaration) ->
    (* The dedicated instruction opcode replaces the source discriminator.
       No source field is optimized away in this first checked profile. *)
    let kind=O.text "$type" declaration.value in
    let operands=Json.object_fields declaration.value |> List.filter (fun (key,_) -> key <> "$type") in
    Json.Object ["id",str declaration.id;"kind",str kind;"source_path",str declaration.path;
      "data",Json.Object operands]) (D.declarations document) in
  O.behavior_of_json (Json.Object [
    "schema_version",str O.behavior_schema;"profile",str O.profile;
    "source_document",D.to_json document;"descriptor_bundle",O.descriptors_to_json descriptors;
    "source_artifact_digest",str (D.artifact_digest document);
    "descriptors_digest",str (O.descriptors_digest descriptors);
    "nodes",Json.Array nodes;"source_ledger",O.get "declarations" assessment;
    "requirements_ledger",O.get "requirements" assessment;"assumptions",O.get "assumptions" assessment;
    "unresolved_obligations",O.get "unresolved_obligations" assessment])

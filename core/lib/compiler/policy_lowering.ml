open Bioc_wire
module D = Bioc_domain.Policy_document
module A = Bioc_checker.Policy_admission
module Typed = Bioc_domain.Policy_admitted_ir
let str value = Json.String value
let lower ?(charge=Bioc_checker.Policy_generation_meter.no_charge) (admitted:A.t) =
  let module Meter = Bioc_checker.Policy_generation_meter.Make (struct let charge = charge end) in
  let module List = Meter.List in
  let module Json = Meter.Json in
  let module Canonical = Meter.Canonical in
  let module O = Meter.Operational in

  let document=A.document admitted and descriptors=A.descriptors admitted in
  let assessment=A.source_assessment admitted in
  Meter.serialization (D.to_json document);
  Meter.serialization (O.descriptors_to_json descriptors);
  let nodes=List.map (fun instruction ->
    (* The dedicated instruction opcode replaces the source discriminator.
       No source field is optimized away in this first checked profile. *)
    Meter.preflight (Typed.original_declaration instruction);
    let declaration=Typed.declaration instruction in
    (* Executable operands are reconstructed from typed terms and resolved
       symbols. The separately retained source remains checker authority. *)
    let encoded=Typed.wire_declaration ~charge instruction in
    let operands=Json.object_fields encoded |> List.filter (fun (key,_) -> key <> "$type") in
    Json.Object ["id",str (Typed.name declaration);"kind",str (Typed.kind declaration);
      "source_path",str (Typed.source_path instruction);
      "data",Json.Object operands]) (Typed.instructions (A.typed admitted)) in
  let descriptor_json=O.descriptors_to_json descriptors in
  let behavior=Json.Object [
    "schema_version",str O.behavior_schema;"profile",str O.profile;
    "source_document",D.to_json document;"descriptor_bundle",descriptor_json;
    "source_artifact_digest",str (D.artifact_digest document);
    "descriptors_digest",str (Canonical.fingerprint descriptor_json);
    "nodes",Json.Array nodes;"source_ledger",O.get "declarations" assessment;
    "requirements_ledger",O.get "requirements" assessment;"assumptions",O.get "assumptions" assessment;
    "unresolved_obligations",O.get "unresolved_obligations" assessment] in
  Meter.serialization behavior;
  O.behavior_of_json behavior

open Bioc_wire
module Child = Bioc_realization_checker.Policy_component_material_check
module Context = Bioc_realization_checker.Policy_component_context_check
module Assembly = Bioc_realization_checker.Policy_component_assembly_check
module Structure = Bioc_checker.Policy_mrna_structure_check
module K = Bioc_domain.Construction_content
module N = Bioc_domain.Molecule
type rendered = { members:Json.t list; fasta:string; fasta_sha256:string }

let render ?(charge=fun _ -> ()) checked =
  let content=Structure.content (Assembly.structure (Context.assembly (Child.context checked))) in
  let molecules=match K.inventory content with
    | Some value -> K.Inventory.molecules value
    | None -> Diagnostic.fail "policy_component_material_export_incomplete"
        "Checked material has no exact molecular inventory." in
  let ids=List.map (fun molecule -> let id=N.id molecule in charge (1+String.length id); id) molecules in
  Diagnostic.require (ids=K.member_order content && molecules<>[])
    "policy_component_material_export_incomplete"
    "Exact delivered member order is absent from checked material.";
  charge 1024;
  let fasta=Buffer.create 1024 in
  let members=List.mapi (fun index molecule ->
    charge 32;
    let id=Printf.sprintf "rna_%04d" (index+1) in
    let header=">"^id^" alphabet=RNA\n" in
    charge (String.length header); Buffer.add_string fasta header;
    let sequence=N.sequence molecule in
    let size=String.length sequence in
    charge (size + (size+79)/80);
    let rec lines offset = if offset<size then (
      let count=min 80 (size-offset) in
      Buffer.add_substring fasta sequence offset count;
      Buffer.add_char fasta '\n'; lines (offset+count)) in
    lines 0;
    (* This subtree belonged to the child's already checked complete candidate
       under the fixed 8 MiB / 250,000-node input bound. Reserve that full upper
       bound before the typed-to-JSON conversion; no unmetered size discovery is
       used to fund the conversion after it has already happened. *)
    charge (8_388_608 + 250_000);
    let raw=N.to_json molecule in
    charge size;
    Json.Object ["fasta_id",Json.String id;"member_id",Json.String (N.id molecule);
      "molecule",raw;"sequence_sha256",Json.String (Canonical.sha256 sequence)]) molecules in
  charge (Buffer.length fasta);
  let fasta=Buffer.contents fasta in
  charge (String.length fasta);
  {members;fasta;fasta_sha256=Canonical.sha256 fasta}

open Bioc_wire
module P = Bioc_domain.Payload_structure
module N = Bioc_domain.Molecule
module S = Bioc_domain.Molecule_set
module M = Bioc_domain.Molecular_record
module G = Bioc_domain.Molecule_coordinates
module C = Bioc_domain.Molecule_chemistry
module Names = Set.Make (String)
module By_name = Map.Make (String)
type result = { diagnostics : string list; unsupported : string list }
let invalid_contracts = { diagnostics = ["payload_contract_inventory_invalid"]; unsupported = [] }
let invalid_bundle contracts = { diagnostics = ["payload_bundle_invalid"];
    unsupported = if contracts = [] then ["payload_authority_missing"] else [] }
let inventory contracts =
  ignore (M.bounded_length ~maximum:P.max_contracts contracts);
  let sorted = List.sort (fun a b -> String.compare (P.member_id a) (P.member_id b)) contracts in
  let names = List.map P.member_id sorted in
  Diagnostic.require (List.length names = List.length (List.sort_uniq String.compare names))
    "invalid_payload_contract_inventory" "Duplicate member authority.";
  sorted
let index identity values = List.fold_left (fun map value -> By_name.add (identity value) value map) By_name.empty values
let max_work = 10_000_000
let make_budget ?parent () =
  let profile="biocompiler.payload_structure_check.resources.v1" and error_code="payload_structure_resource_limit" in
  match parent with None -> Work_budget.create ~profile ~error_code ~maximum:max_work ()
  | Some parent -> Work_budget.nested ~parent ~profile ~error_code ~maximum:max_work ()
let inspect budget contracts bundle =
  let diagnostics = ref [] and unsupported = ref [] in
  let output=Work_budget.create_output ~profile:"biocompiler.payload_structure_check.resources.v1"
      ~error_code:"payload_structure_resource_limit" ~max_bytes:M.max_json_bytes ~max_nodes:M.max_items () in
  let emit items value = Work_budget.charge budget (String.length value+1);
    Work_budget.reserve_json output (Json.String value);items := value :: !items in
  let contradict value = emit diagnostics value and unresolved value = emit unsupported value in
  Work_budget.charge budget (List.length contracts+List.length (S.molecules bundle)+List.length (S.complexes bundle)+List.length (S.role_instances bundle));
  if contracts = [] then unresolved "payload_authority_missing";
  let molecules = index N.id (S.molecules bundle) and complexes = index N.Complex.id (S.complexes bundle) in
  let subjects = List.fold_left (fun result role ->
      if N.Role.purpose role = N.Role.Requested_payload then Names.add (N.Role.subject_id role) result else result)
      Names.empty (S.role_instances bundle) in
  let requested = ref Names.empty in
  Names.iter (fun identity ->
      Work_budget.charge budget 1;
      if By_name.mem identity molecules then requested := Names.add identity !requested
      else
        let value = By_name.find identity complexes in
        match N.Complex.kind value with
        | N.Complex.Protein_complex -> unresolved ("payload_complex_modality_unsupported:" ^ identity)
        | N.Complex.Dna_duplex | N.Complex.Rna_complex ->
            List.iter (fun constituent ->
                Work_budget.charge budget 1;
                let molecule_id = N.Constituent.molecule_id constituent in
                requested := Names.add molecule_id !requested;
                if N.Constituent.stoichiometry constituent = None then
                  unresolved ("payload_complex_stoichiometry_unknown:" ^ identity ^ "/" ^ molecule_id))
              (N.Complex.constituents value)) subjects;
  let by_member = index P.member_id contracts in
  let declared = By_name.fold (fun key _ names -> Names.add key names) by_member Names.empty in
  Names.iter (fun name -> unresolved ("payload_authority_missing:" ^ name)) (Names.diff !requested declared);
  Names.iter (fun name -> contradict ("payload_contract_extra:" ^ name)) (Names.diff declared !requested);
  Names.iter (fun identity ->
      Work_budget.charge budget 1;
      let molecule = By_name.find identity molecules in
      let expected_alphabet = match N.form molecule with
        | N.Delivered_rna -> Some G.Rna | N.Delivered_dna -> Some G.Dna
        | N.Deposited_template_record | N.Dna_expression_template | N.Primary_rna
        | N.Processed_rna | N.Edited_rna | N.Protein_precursor | N.Mature_protein -> None in
      (match expected_alphabet with
       | None -> unresolved ("payload_modality_unsupported:" ^ identity)
       | Some alphabet -> if G.Space.alphabet (N.space molecule) <> alphabet then
           contradict ("payload_modality_alphabet:" ^ identity));
      if N.sequence_extent molecule <> C.Complete then unresolved ("payload_extent_incomplete:" ^ identity);
      if not (C.declared_nominal_complete (N.chemistry molecule)) then unresolved ("payload_chemistry_incomplete:" ^ identity);
      match By_name.find_opt identity by_member with
      | None -> ()
      | Some contract ->
          if P.form_name (P.form contract) <> N.form_name (N.form molecule) then contradict ("payload_form_mismatch:" ^ identity);
          if P.topology contract <> G.Space.topology (N.space molecule) then contradict ("payload_topology_mismatch:" ^ identity);
          if M.Provenance.status (P.provenance contract) <> M.Provenance.Declared then unresolved ("payload_authority_undeclared:" ^ identity);
          Work_budget.charge budget (List.length (N.features molecule));
          let features = index N.Feature.id (N.features molecule) in
          List.iter (fun required ->
              Work_budget.charge budget 1;
              let label = identity ^ "/" ^ P.Region.feature_id required in
              match By_name.find_opt (P.Region.feature_id required) features with
              | None -> contradict ("payload_region_missing:" ^ label)
              | Some feature ->
                  if N.Feature.kind feature <> P.Region.kind required then contradict ("payload_region_kind_mismatch:" ^ label);
                  if M.Provenance.status (N.Feature.provenance feature) <> M.Provenance.Declared then
                    unresolved ("payload_boundary_authority_undeclared:" ^ label);
                  match N.Feature.path feature with
                  | None -> unresolved ("payload_region_coordinates_unknown:" ^ label)
                  | Some path when G.Path.length path = 0 -> contradict ("payload_region_empty:" ^ label)
                  | Some path ->
                      Work_budget.charge budget (List.length (G.Path.spans path));
                      (try G.Path.validate_for path (N.space molecule)
                       with Diagnostic.Error _ -> contradict ("payload_region_coordinates_invalid:" ^ label))) (P.regions contract)) !requested;
  { diagnostics = List.sort_uniq String.compare !diagnostics;
    unsupported = List.sort_uniq String.compare !unsupported }
let check_with_parent ~parent ~contracts ~bundle =
  let budget=make_budget ?parent () in
  Work_budget.charge budget 1;
  match inventory contracts with
  | contracts -> inspect budget contracts bundle
  | exception Diagnostic.Error _ -> invalid_contracts
let check_json_with_parent ~parent ~contracts ~bundle =
  let budget=make_budget ?parent () in
  Work_budget.charge budget 1;
  let decode_contracts () =
    match contracts with
    | Json.Null -> []
    | raw -> M.array ~maximum:P.max_contracts raw
        |> List.map (fun value -> P.of_json value) |> inventory in
  match decode_contracts () with
  | exception Diagnostic.Error _ -> invalid_contracts
  | contracts ->
      match S.of_json bundle with
      | bundle -> inspect budget contracts bundle
      | exception Diagnostic.Error _ -> invalid_bundle contracts

let check ~contracts ~bundle = check_with_parent ~parent:None ~contracts ~bundle
let check_json ~contracts ~bundle = check_json_with_parent ~parent:None ~contracts ~bundle

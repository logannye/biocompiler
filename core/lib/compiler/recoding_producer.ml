open Bioc_wire
open Bioc_domain
module C = Construction
module G = Molecule_coordinates
module H = Molecule_chemistry
module R = Molecular_recoding
module T = Molecular_transition
module A = Construction_artifact
module Names = Map.Make (String)

let implementation_version = "biocompiler.ocaml.recoding_producer.v0.1"
type material = Root of Molecule.t | Product of A.Value.t
let space = function Root v -> Molecule.space v | Product v -> A.Value.space v
let sequence = function Root v -> Molecule.sequence v | Product v -> A.Value.sequence v
let chemistry = function Root v -> Molecule.chemistry v | Product v -> A.Value.chemistry v
let features = function Root v -> Molecule.features v | Product v -> A.Value.features v
let sequence_extent = function Root v -> Molecule.sequence_extent v | Product v -> A.Value.sequence_extent v
let input_error message = Diagnostic.fail "invalid_construction_producer_input" message

module Available = struct
  type t = material Names.t
  let maximum = C.max_sources + C.max_products
  let of_bindings bindings =
    ignore (Molecular_record.bounded_length ~maximum bindings);
    List.fold_left (fun map (id,value) ->
        ignore (Molecular_record.text (Json.String id));
        if Names.mem id map then input_error "Duplicate available material identity.";
        Names.add id value map) Names.empty bindings
  let find = Names.find_opt
  let add_products values map =
    ignore (Molecular_record.bounded_length ~maximum:C.max_products values);
    let result = List.fold_left (fun map value ->
        let id = A.Value.id value in
        if Names.mem id map then input_error "Available product would replace existing material authority.";
        Names.add id (Product value) map) map values in
    if Names.cardinal result > maximum then input_error "Available material inventory exceeds its fixed bound.";
    result
end

let max_work = 50_000_000
type budget = {work:Bioc_checker.Work_budget.t; output:Bioc_checker.Work_budget.output; staged:Bioc_checker.Work_budget.output}
exception Budget_exhausted of Diagnostic.t
let protect run = try run () with Budget_exhausted diagnostic -> raise (Diagnostic.Error diagnostic)
let make_budget ?parent ?(maximum=max_work) () =
  Diagnostic.require (maximum >= 0 && maximum <= max_work) "construction_producer_limit" "Invalid native producer work ceiling.";
  let profile="biocompiler.construction_producer.resources.v1" and error_code="construction_producer_limit" in
  let work=match parent with
    | None -> Bioc_checker.Work_budget.create ~profile ~error_code ~maximum ()
    | Some parent -> Bioc_checker.Work_budget.nested ~parent ~profile ~error_code ~maximum () in
  let output ()=Bioc_checker.Work_budget.create_output ~profile ~error_code:"construction_producer_output_limit"
      ~max_bytes:Molecular_record.max_json_bytes ~max_nodes:Molecular_record.max_items () in
  {work;output=output ();staged=output ()}
let charge budget amount =
  try Bioc_checker.Work_budget.charge budget.work amount
  with Diagnostic.Error diagnostic -> raise (Budget_exhausted diagnostic)
let reserve_output budget raw =
  try Bioc_checker.Work_budget.reserve_json budget.output raw
  with Diagnostic.Error diagnostic -> raise (Budget_exhausted diagnostic)
let reserve_staged budget raw =
  try Bioc_checker.Work_budget.reserve_json budget.staged raw
  with Diagnostic.Error diagnostic -> raise (Budget_exhausted diagnostic)
let reserve_json budget raw =
  let rec loop = function
    | [] -> ()
    | `Value (value,depth)::rest ->
        charge budget 1;
        if depth>Molecular_record.max_depth then raise (Budget_exhausted
          {Diagnostic.code="construction_producer_limit";message="Construction work input exceeds its bounded nesting profile.";path=None});
        (match value with
         | Json.String text -> charge budget (String.length text);loop rest
         | Json.Object fields -> loop (`Object (fields,depth+1)::rest)
         | Json.Array values -> loop (`Array (values,depth+1)::rest)
         | Json.Int value -> charge budget (1+Z.numbits value/4);loop rest
         | _ -> loop rest)
    | `Array ([],_)::rest | `Object ([],_)::rest -> loop rest
    | `Array (value::values,depth)::rest -> loop (`Value (value,depth)::`Array (values,depth)::rest)
    | `Object ((key,value)::fields,depth)::rest -> charge budget (String.length key+1);
        loop (`Value (value,depth)::`Object (fields,depth)::rest) in
  loop [`Value (raw,0)]

type result = {values : A.Value.t list; used_residues : int; diagnostic : string option}
exception Problem of string
let require value code = if not value then raise (Problem code)
let obj value = Json.Object value
let str value = Json.String value
let span first last = G.Span.of_json (obj ["schema_version",str "biocompiler.molecule_index_span.v0.1";
    "start",Json.int first;"end",Json.int last])
let path frame spans = G.Path.of_json (obj ["schema_version",str "biocompiler.molecule_coordinate_path.v0.1";
    "space_id",str (G.Space_id.to_string frame);"spans",Json.Array (List.map G.Span.to_json spans);"strand",str "+"])
let selected_path selection source =
  let frame = space source in
  let selected = match C.Selection.path selection with Some value -> value
    | None -> path (G.Space.id frame) [span 0 (G.Space.length frame)] in
  (try G.Path.validate_for selected frame with Diagnostic.Error _ -> raise (Problem "invalid_selection"));
  require (G.Path.length selected > 0) "invalid_selection";
  selected
let relabel_path id value =
  let fields = Json.object_fields (G.Path.to_json value) in
  G.Path.of_json (obj (("space_id",str id)::List.remove_assoc "space_id" fields))
let inherited_chemistry id source =
  let value = chemistry source in
  let tail = H.terminal_tail value in
  match H.Tail.path tail with
  | None -> value
  | Some p ->
      let tail = H.Tail.make ~status:(H.Tail.status tail) ~placement:(H.Tail.placement tail)
          ~length:(H.Tail.length tail) ~path:(Some (relabel_path id p)) ~provenance:(H.Tail.provenance tail) in
      H.make ~cap:(H.cap value) ~start_end:(H.start_end value) ~finish_end:(H.finish_end value)
        ~modifications:(H.modifications value) ~modification_inventory_status:(H.modification_inventory_status value)
        ~modification_inventory_provenance:(H.modification_inventory_provenance value) ~terminal_tail:tail
let output_chemistry port source =
  let transition = C.Product_port.chemistry_transition port in
  match T.Chemistry.mode transition with
  | T.Chemistry.Exact_inheritance -> inherited_chemistry (C.Product_port.space_id port) source
  | T.Chemistry.Explicit_output -> (match T.Chemistry.output transition with Some value -> value
      | None -> raise (Problem "invalid_operation"))
let output_value budget step port source sequence topology segments consumed =
  reserve_json budget (C.Product_port.to_json port);
  reserve_json budget (H.to_json (chemistry source));
  let alphabet = match segments with
    | first::_ when A.Derived_segment.rule first = A.Derived_segment.Translation_codon -> G.Protein
    | _ -> G.Rna in
  require (C.Product_port.alphabet port = alphabet) "unsupported_alphabet";
  require (C.Product_port.topology port = topology) "unsupported_topology";
  charge budget (String.length sequence);
  let frame = G.Space.of_json (obj ["schema_version",str "biocompiler.molecule_coordinate_space.v0.1";
      "id",str (C.Product_port.space_id port);"alphabet",str (if alphabet=G.Protein then "protein" else "RNA");
      "length",Json.int (String.length sequence);"topology",str (if topology=G.Linear then "linear" else "circular");
      "axis",str (if alphabet=G.Protein then "N_to_C" else "5prime_to_3prime")]) in
  let transition = C.Product_port.feature_transition port in
  let features = List.concat_map T.Feature_disposition.outputs (T.Feature.dispositions transition) @ T.Feature.added transition in
  charge budget (List.length features + List.length segments + List.length consumed);
  let value=A.Value.make ~id:(C.Product_port.id port) ~space:frame ~sequence ~chemistry:(output_chemistry port source)
    ~features ~segments ~step_id:(C.Transform_step.id step) ~sequence_extent:H.Complete ~consumed in
  reserve_output budget (A.Value.to_json value);value
let chemical_key parent identity = Option.map (fun value ->
    parent,H.Chemical_identity.namespace value,H.Chemical_identity.accession value,H.Chemical_identity.version value) identity
let modifications budget chemistry =
  let policies = Hashtbl.create 4 and sites = Hashtbl.create 32 in
  List.iter (fun modification ->
      let parent = H.Modification.canonical_base modification in
      let value = chemical_key parent (Some (H.Modification.identity modification)) in
      charge budget 1;
      match H.Modification.scope modification with
      | H.Modification.All_matching_bases -> Hashtbl.replace policies parent value
      | H.Modification.Positions -> List.iter (fun position -> charge budget 1;Hashtbl.replace sites position value)
          (H.Modification.positions modification)) (H.modifications chemistry);
  policies,sites
let at (policies,sites) sequence position =
  match Hashtbl.find_opt sites position with Some value -> value
  | None -> Option.value ~default:None (Hashtbl.find_opt policies sequence.[position])
let edited budget step source input canonical_edits chemical_edits =
  let port = List.hd (C.Transform_step.ports step) in
  require (G.Space.alphabet (space source) = G.Rna) "unsupported_alphabet";
  let before = chemistry source and after = output_chemistry port source in
  require (H.modification_inventory_status before = H.Declared && H.modification_inventory_status after = H.Declared)
    "unsupported_edit_chemistry";
  let old_view = modifications budget before and new_view = modifications budget after in
  List.iter (fun facet -> require (Json.equal (H.Claim.nominal_json (facet before)) (H.Claim.nominal_json (facet after))) "invalid_edit")
    [H.cap;H.start_end;H.finish_end];
  let original = sequence source in
  charge budget (String.length original);
  let letters = Bytes.of_string original and expected = Hashtbl.create 32 in
  List.iter (fun edit ->
      charge budget 1;
      let position = R.Canonical_edit.position edit in
      require (position < Bytes.length letters && Bytes.get letters position = R.Canonical_edit.expected edit) "invalid_edit";
      require (at old_view original position = None) "invalid_edit";
      Bytes.set letters position (R.Canonical_edit.replacement edit);
      Hashtbl.replace expected position None) canonical_edits;
  List.iter (fun edit ->
      charge budget 1;
      let position = R.Chemical_edit.position edit and parent = R.Chemical_edit.parent edit in
      require (position < Bytes.length letters && Bytes.get letters position = parent) "invalid_edit";
      require (at old_view original position = chemical_key parent (R.Chemical_edit.before edit)) "invalid_edit";
      Hashtbl.replace expected position (chemical_key parent (R.Chemical_edit.after edit))) chemical_edits;
  let sequence = Bytes.to_string letters in
  for position=0 to String.length sequence-1 do
    charge budget 1;
    let wanted = match Hashtbl.find_opt expected position with Some value -> value | None -> at old_view original position in
    require (at new_view sequence position = wanted) "invalid_edit"
  done;
  let selected = path (G.Space.id (space source)) [span 0 (String.length sequence)] in
  let segment = A.Derived_segment.make ~destination:(span 0 (String.length sequence))
      ~source_id:(C.Value_ref.id (C.Selection.value input)) ~source_path:selected ~rule:A.Derived_segment.Rna_editing in
  output_value budget step port source sequence (G.Space.topology (space source)) [segment] []
let translation_span budget selection source =
  require (G.Space.alphabet (space source) = G.Rna) "unsupported_alphabet";
  let selected = selected_path selection source in
  charge budget (List.length (G.Path.spans selected));
  require (G.Path.strand selected = G.Forward && List.length (G.Path.spans selected) = 1) "unsupported_translation_path";
  let first = List.hd (G.Path.spans selected) in
  require (G.Path.length selected >= 6 && G.Path.length selected mod 3 = 0 &&
           String.sub (sequence source) (G.Span.start first) 3 = "AUG") "invalid_translation";
  require (H.modification_inventory_status (chemistry source) = H.Declared) "unsupported_translation_chemistry";
  first
let translate budget source selected policy =
  let count = G.Span.length selected / 3 in
  let overrides = Hashtbl.create 16 in
  let sequence = sequence source in
  List.iter (fun entry ->
      charge budget 1;
      let index = R.Codon_recoding.codon_index entry in
      require (index < count && String.sub sequence (G.Span.start selected+3*index) 3 = R.Codon_recoding.expected_triplet entry)
        "invalid_translation";
      Hashtbl.replace overrides index entry) (R.Translation_policy.recodings policy);
  let coverage = modifications budget (chemistry source) in
  charge budget count;
  let residues = Bytes.create count in
  for index=0 to count-1 do
    let start = G.Span.start selected + 3*index in
    let triplet = String.sub sequence start 3 in
    let amino_acid = match Hashtbl.find_opt overrides index with
      | Some entry -> R.Codon_recoding.amino_acid entry
      | None ->
          require (at coverage sequence start=None && at coverage sequence (start+1)=None && at coverage sequence (start+2)=None)
            "unsupported_translation_chemistry";
          List.assoc triplet R.standard_rna_codon_table in
    Bytes.set residues index amino_acid
  done;
  require (Bytes.get residues 0='M' && Bytes.get residues (count-1)='*') "invalid_translation";
  for index=0 to count-2 do require (Bytes.get residues index <> '*') "invalid_translation" done;
  Bytes.sub_string residues 0 (count-1)

let construct_step ?budget ~step ~available ~remaining_residues () = protect (fun () ->
  if remaining_residues < 0 || remaining_residues > C.max_cumulative_produced_residues then
    input_error "Remaining construction residue allowance is outside the fixed profile.";
  let budget = match budget with Some value -> value | None -> make_budget () in
  reserve_json budget (C.Transform_step.to_json step);
  let used = ref 0 in
  try
    let operation = C.Transform_step.operation step in
    let selections = C.operation_selections operation in
    charge budget (List.length selections);
    let get selection = match Available.find (C.Value_ref.id (C.Selection.value selection)) available with
      | Some value -> value | None -> raise (Problem "unavailable_input") in
    require (List.for_all (fun selection -> Available.find (C.Value_ref.id (C.Selection.value selection)) available <> None) selections)
      "unavailable_input";
    require (List.for_all (fun selection -> sequence_extent (get selection) = H.Complete) selections) "incomplete_input";
    List.iter (fun selection -> ignore (selected_path selection (get selection))) selections;
    let specification = C.Operation.specification operation in
    let values = match specification with
      | C.Operation.Base_editing {input;canonical_edits;chemical_edits} ->
          let source = get input and port = List.hd (C.Transform_step.ports step) in
          require (G.Space.alphabet (space source)=G.Rna && C.Product_port.alphabet port=G.Rna) "unsupported_alphabet";
          require (C.Product_port.topology port=G.Space.topology (space source)) "unsupported_topology";
          require (G.Space.length (space source) <= remaining_residues) "residue_budget";
          used := G.Space.length (space source);
          [edited budget step source input canonical_edits chemical_edits]
      | _ ->
          let ports = C.Transform_step.ports step in
          require (List.for_all (fun port -> C.Product_port.alphabet port=G.Protein) ports) "unsupported_alphabet";
          require (List.for_all (fun port -> C.Product_port.topology port=G.Linear) ports) "unsupported_topology";
          let skipping, jobs = match specification with
            | C.Operation.Translation {input;policy} -> false,[Some (C.Product_port.id (List.hd ports)),input,policy]
            | C.Operation.Ribosomal_skipping {input;policy;_} -> true,[None,input,policy]
            | C.Operation.Multi_orf_translation products -> false,List.map (fun product ->
                Some (C.Translation_product.port_id product),C.Translation_product.input product,C.Translation_product.policy product) products
            | C.Operation.Conditional_translation branches -> false,List.filter_map (fun branch ->
                match C.Translation_branch.port_id branch,C.Translation_branch.policy branch with
                | None,_ -> None | Some id,Some policy -> Some (Some id,C.Translation_branch.input branch,policy)
                | Some _,None -> raise (Problem "invalid_operation")) branches
            | _ -> raise (Problem "invalid_operation") in
          let planned = List.map (fun (port,input,policy) ->
              let source = get input in port,input,policy,source,translation_span budget input source) jobs in
          let estimate = List.fold_left (fun size (_,_,_,_,selected) -> size + G.Span.length selected/3-1) 0 planned in
          require (estimate <= remaining_residues) "residue_budget";
          used := estimate;
          let allocations = if skipping then (match specification with
              | C.Operation.Ribosomal_skipping {products;_} ->
                  let allocations = List.map (fun product -> C.Peptide_product.port_id product,C.Peptide_product.residues product) products in
                  let ordered = List.sort compare (List.map (fun (_,part) -> G.Span.start part,G.Span.stop part) allocations) in
                  let cursor = ref 0 in
                  List.iter (fun (first,last) -> require (first = !cursor && last > first && last <= estimate) "invalid_skipping_partition";
                      cursor := last) ordered;
                  require (!cursor=estimate) "invalid_skipping_partition";
                  allocations
              | _ -> assert false) else [] in
          List.concat_map (fun (port,input,policy,source,selected) ->
              let peptide = translate budget source selected policy in
              let allocations = if skipping then allocations else
                  [Option.get port,span 0 (String.length peptide)] in
              List.map (fun (id,part) ->
                  let first = G.Span.start selected+3*G.Span.start part and last = G.Span.start selected+3*G.Span.stop part in
                  let source_path = path (G.Space.id (space source)) [span first last] in
                  let source_id = C.Value_ref.id (C.Selection.value input) in
                  let segment = A.Derived_segment.make ~destination:(span 0 (G.Span.length part)) ~source_id ~source_path
                      ~rule:A.Derived_segment.Translation_codon in
                  let consumed = A.Consumed_segment.make ~source_id ~source_path:(path (G.Space.id (space source))
                      [span (G.Span.stop selected-3) (G.Span.stop selected)]) in
                  let port = List.find (fun item -> C.Product_port.id item=id) ports in
                  output_value budget step port source (String.sub peptide (G.Span.start part) (G.Span.length part))
                    G.Linear [segment] [consumed]) allocations) planned in
    {values;used_residues= !used;diagnostic=None}
  with
  | Problem code -> {values=[];used_residues= !used;diagnostic=Some code}
  | Diagnostic.Error diagnostic as error ->
      if diagnostic.code="construction_producer_limit" then raise error;
      {values=[];used_residues= !used;diagnostic=Some "invalid_operation"})

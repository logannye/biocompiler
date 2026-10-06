open Bioc_wire
open Bioc_domain
module C = Construction
module O = C.Operation
module A = Construction_artifact
module G = Molecule_coordinates
module H = Molecule_chemistry
module N = Molecule
module S = Molecule_set
module R = Molecular_recoding
module T = Molecular_transition
module I = Transition_check.Input
module Names = Map.Make (String)
type transition = {step : C.Transform_step.t; port : C.Product_port.t; inputs : (string * I.t) list; product : A.Value.t}
exception Budget_exhausted of Diagnostic.t
let charge budget amount = try Work_budget.charge budget amount
  with Diagnostic.Error diagnostic -> raise (Budget_exhausted diagnostic)
let reserve_json budget raw =
  let rec loop = function
    | [] -> ()
    | `Value (value,depth)::rest ->
        charge budget 1;
        if depth>Molecular_record.max_depth then raise (Budget_exhausted
          {Diagnostic.code="construction_resource_limit";message="Construction work input exceeds its bounded nesting profile.";path=None});
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

let protect run = try run () with Budget_exhausted diagnostic -> raise (Diagnostic.Error diagnostic)
exception Problem of string
let expect condition code = if not condition then raise (Problem code)
let str value = Json.String value
let obj value = Json.Object value
let span first last = G.Span.of_json (obj ["schema_version",str "biocompiler.molecule_index_span.v0.1";"start",Json.int first;"end",Json.int last])
let space_id space = G.Space_id.to_string (G.Space.id space)
let path ~id ~spans ~strand = G.Path.of_json (obj ["schema_version",str "biocompiler.molecule_coordinate_path.v0.1";"space_id",str id;
    "spans",Json.Array (List.map G.Span.to_json spans);"strand",str (if strand = G.Forward then "+" else "-")])
let whole space = path ~id:(space_id space) ~spans:[span 0 (G.Space.length space)] ~strand:G.Forward
let reframe_path id value = path ~id ~spans:(G.Path.spans value) ~strand:(G.Path.strand value)
let space ~id ~alphabet ~length ~topology = G.Space.of_json (obj ["schema_version",str "biocompiler.molecule_coordinate_space.v0.1";"id",str id;
    "alphabet",str (match alphabet with G.Dna -> "DNA" | G.Rna -> "RNA" | G.Protein -> "protein");"length",Json.int length;
    "topology",str (if topology = G.Linear then "linear" else "circular");"axis",str (if alphabet = G.Protein then "N_to_C" else "5prime_to_3prime")])
let reframe_chemistry chemistry id =
  let tail = H.terminal_tail chemistry in
  match H.Tail.path tail with None -> chemistry | Some old_path ->
    let tail = H.Tail.make ~status:(H.Tail.status tail) ~placement:(H.Tail.placement tail) ~length:(H.Tail.length tail)
        ~path:(Some (reframe_path id old_path)) ~provenance:(H.Tail.provenance tail) in
    H.make ~cap:(H.cap chemistry) ~start_end:(H.start_end chemistry) ~finish_end:(H.finish_end chemistry)
      ~modifications:(H.modifications chemistry) ~modification_inventory_status:(H.modification_inventory_status chemistry)
      ~modification_inventory_provenance:(H.modification_inventory_provenance chemistry) ~terminal_tail:tail
(* Read the closed source schema here. Producer dispatch and its selection
   helper are deliberately not part of the checker's expected-value path. *)
let operands operation =
  let unique values = List.fold_left (fun result value -> if List.exists (fun old -> C.Selection.fingerprint old = C.Selection.fingerprint value) result
        then result else value :: result) [] values |> List.rev in
  match O.specification operation with
  | O.Concatenate inputs -> inputs
  | O.Multi_orf_translation products -> List.map C.Translation_product.input products |> unique
  | O.Conditional_translation branches -> List.map C.Translation_branch.input branches |> unique
  | O.Slice input | O.Transcription input | O.Orientation {input;_} | O.Rna_cleavage {input;_} | O.Rna_splicing {input;_}
  | O.Protein_cleavage {input;_} | O.Protein_splicing {input;_} | O.Circularization {input;_} | O.Base_editing {input;_}
  | O.Translation {input;_} | O.Ribosomal_skipping {input;_} -> [input]
let reference_id selection = C.Value_ref.id (C.Selection.value selection)
let reserve remaining count = expect (count <= !remaining) "residue_budget"; remaining := !remaining - count
let read_path budget source source_path rule =
  let sequence = I.sequence source and alphabet = G.Space.alphabet (I.space source) in
  charge budget (G.Path.length source_path);
  let buffer = Buffer.create (G.Path.length source_path) in
  let emit position =
    let letter = sequence.[position] in
    let letter = match rule with
      | A.Derived_segment.Copy -> letter
      | A.Derived_segment.Transcription -> if letter = 'T' then 'U' else letter
      | A.Derived_segment.Complement -> (match letter with
          | 'A' -> if alphabet = G.Dna then 'T' else 'U' | 'C' -> 'G' | 'G' -> 'C' | 'T' | 'U' -> 'A'
          | _ -> raise (Problem "unsupported_alphabet"))
      | A.Derived_segment.Rna_editing | A.Derived_segment.Translation_codon -> raise (Problem "invalid_operation") in
    Buffer.add_char buffer letter in
  List.iter (fun part -> if G.Path.strand source_path = G.Forward then
        for position = G.Span.start part to G.Span.stop part - 1 do emit position done
      else for position = G.Span.stop part - 1 downto G.Span.start part do emit position done) (G.Path.spans source_path);
  Buffer.contents buffer
let finish_value budget step port source sequence segments consumed =
  charge budget (String.length sequence + List.length segments + List.length consumed);
  reserve_json budget (C.Product_port.to_json port);
  reserve_json budget (H.to_json (I.chemistry source));
  let output_space = space ~id:(C.Product_port.space_id port) ~alphabet:(C.Product_port.alphabet port)
      ~length:(String.length sequence) ~topology:(C.Product_port.topology port) in
  let transition = C.Product_port.chemistry_transition port in
  let chemistry = match T.Chemistry.mode transition, T.Chemistry.output transition with
    | T.Chemistry.Explicit_output, Some value -> value
    | T.Chemistry.Exact_inheritance, None -> reframe_chemistry (I.chemistry source) (space_id output_space)
    | _ -> raise (Problem "invalid_operation") in
  let features = C.Product_port.feature_transition port in
  let features = List.concat_map T.Feature_disposition.outputs (T.Feature.dispositions features) @ T.Feature.added features in
  A.Value.make ~id:(C.Product_port.id port) ~space:output_space ~sequence ~chemistry ~features ~segments
    ~step_id:(C.Transform_step.id step) ~sequence_extent:H.Complete ~consumed
let propose budget step port selections inputs paths rule =
  let cursor = ref 0 and parts = ref [] and segments = ref [] in
  List.iter2 (fun (selection,source) source_path ->
      let last = !cursor + G.Path.length source_path in
      segments := A.Derived_segment.make ~destination:(span !cursor last) ~source_id:(reference_id selection) ~source_path ~rule :: !segments;
      parts := read_path budget source source_path rule :: !parts; cursor := last) (List.combine selections inputs) paths;
  finish_value budget step port (List.hd inputs) (String.concat "" (List.rev !parts)) (List.rev !segments) []
let chemical_sites budget chemistry =
  reserve_json budget (H.to_json chemistry);
  let explicit = Hashtbl.create 64 and policies = Hashtbl.create 4 in
  List.iter (fun modification -> let token = H.Chemical_identity.fingerprint (H.Modification.identity modification) in
      match H.Modification.scope modification with
      | H.Modification.All_matching_bases -> Hashtbl.replace policies (H.Modification.canonical_base modification) token
      | H.Modification.Positions -> List.iter (fun position -> Hashtbl.replace explicit position token) (H.Modification.positions modification)) (H.modifications chemistry);
  explicit, policies
let site (explicit,policies) sequence position = match Hashtbl.find_opt explicit position with
  | Some value -> Some value | None -> Hashtbl.find_opt policies sequence.[position]
let edited_proposals budget step available remaining input canonical_edits chemical_edits =
  let port = List.hd (C.Transform_step.ports step) in
  let source = Names.find (reference_id input) available in
  expect (G.Space.alphabet (I.space source) = G.Rna && C.Product_port.alphabet port = G.Rna) "unsupported_alphabet";
  expect (C.Product_port.topology port = G.Space.topology (I.space source)) "unsupported_topology";
  reserve remaining (G.Space.length (I.space source));
  let transition = C.Product_port.chemistry_transition port in
  let chemistry = match T.Chemistry.output transition with Some value -> value | None -> reframe_chemistry (I.chemistry source) (C.Product_port.space_id port) in
  expect (H.modification_inventory_status (I.chemistry source) = H.Declared && H.modification_inventory_status chemistry = H.Declared) "unsupported_edit_chemistry";
  let before = chemical_sites budget (I.chemistry source) and after = chemical_sites budget chemistry in
  let original = I.sequence source in
  charge budget (2*String.length original+2*List.length canonical_edits+List.length chemical_edits);
  let letters = Bytes.of_string original in
  List.iter (fun edit -> let position = R.Canonical_edit.position edit in
      expect (position < Bytes.length letters && Bytes.get letters position = R.Canonical_edit.expected edit) "invalid_edit";
      expect (site before original position = None) "invalid_edit"; Bytes.set letters position (R.Canonical_edit.replacement edit)) canonical_edits;
  let sequence = Bytes.to_string letters and changed = Hashtbl.create 64 in
  List.iter (fun edit -> let position = R.Canonical_edit.position edit in
      Hashtbl.replace changed position (); expect (site after sequence position = None) "invalid_edit") canonical_edits;
  let pin = Option.map H.Chemical_identity.fingerprint in
  List.iter (fun edit -> let position = R.Chemical_edit.position edit in
      expect (position < String.length sequence && original.[position] = R.Chemical_edit.parent edit) "invalid_edit";
      expect (site before original position = pin (R.Chemical_edit.before edit)) "invalid_edit";
      expect (site after sequence position = pin (R.Chemical_edit.after edit)) "invalid_edit";
      Hashtbl.replace changed position ()) chemical_edits;
  for position = 0 to String.length sequence - 1 do
    if not (Hashtbl.mem changed position) then expect (site before original position = site after sequence position) "invalid_edit"
  done;
  List.iter (fun getter -> expect (Json.equal (H.Claim.nominal_json (getter (I.chemistry source))) (H.Claim.nominal_json (getter chemistry))) "invalid_edit") [H.cap;H.start_end;H.finish_end];
  let segment = A.Derived_segment.make ~destination:(span 0 (String.length sequence)) ~source_id:(reference_id input) ~source_path:(whole (I.space source)) ~rule:A.Derived_segment.Rna_editing in
  [port, finish_value budget step port source sequence [segment] [], [reference_id input,source]]
let translation_specs step = match O.specification (C.Transform_step.operation step) with
  | O.Multi_orf_translation products -> List.map (fun product -> C.Translation_product.port_id product,C.Translation_product.input product,C.Translation_product.policy product) products
  | O.Conditional_translation branches -> List.filter_map (fun branch -> match C.Translation_branch.port_id branch,C.Translation_branch.policy branch with
        | Some id,Some policy -> Some (id,C.Translation_branch.input branch,policy) | _ -> None) branches
  | O.Translation {input;policy} | O.Ribosomal_skipping {input;policy;_} -> [C.Product_port.id (List.hd (C.Transform_step.ports step)),input,policy]
  | _ -> raise (Problem "invalid_operation")
let translated_peptide budget step source source_path policy =
  let first = G.Span.start (List.hd (G.Path.spans source_path)) and length = G.Path.length source_path / 3 in
  let sequence = I.sequence source in
  charge budget (2*length);
  let overrides = Hashtbl.create 16 in
  List.iter (fun entry -> charge budget (1+List.length (C.Transform_step.assumptions step));let index = R.Codon_recoding.codon_index entry in
      expect (index < length && String.sub sequence (first + 3 * index) 3 = R.Codon_recoding.expected_triplet entry
              && List.mem (R.Codon_recoding.condition entry) (C.Transform_step.assumptions step)) "invalid_translation";
      Hashtbl.add overrides index entry) (R.Translation_policy.recodings policy);
  let coverage = chemical_sites budget (I.chemistry source) and residues = Bytes.create length in
  for index = 0 to length - 1 do
    let position = first + 3 * index in
    let modified = site coverage sequence position <> None || site coverage sequence (position + 1) <> None || site coverage sequence (position + 2) <> None in
    let override = Hashtbl.find_opt overrides index in
    expect (not modified || Option.is_some override) "unsupported_translation_chemistry";
    let residue = match override with Some entry -> R.Codon_recoding.amino_acid entry
      | None -> List.assoc (String.sub sequence position 3) R.standard_rna_codon_table in
    Bytes.set residues index residue
  done;
  expect (Bytes.get residues 0 = 'M' && Bytes.get residues (length - 1) = '*') "invalid_translation";
  for index = 0 to length - 2 do expect (Bytes.get residues index <> '*') "invalid_translation" done;
  Bytes.sub_string residues 0 (length - 1)
let translation_proposals budget step available remaining =
  reserve_json budget (C.Transform_step.to_json step);
  let ports = C.Transform_step.ports step and operation = O.specification (C.Transform_step.operation step) in
  expect (List.for_all (fun port -> C.Product_port.alphabet port = G.Protein) ports) "unsupported_alphabet";
  expect (List.for_all (fun port -> C.Product_port.topology port = G.Linear) ports) "unsupported_topology";
  let plans = List.map (fun (port_id,selection,policy) ->
      let source = Names.find (reference_id selection) available in
      expect (G.Space.alphabet (I.space source) = G.Rna) "unsupported_alphabet";
      let source_path = match C.Selection.path selection with None -> whole (I.space source) | Some value -> value in
      G.Path.validate_for source_path (I.space source);
      expect (G.Path.strand source_path = G.Forward && List.length (G.Path.spans source_path) = 1) "unsupported_translation_path";
      let first = G.Span.start (List.hd (G.Path.spans source_path)) in
      expect (G.Path.length source_path >= 6 && G.Path.length source_path mod 3 = 0 && String.sub (I.sequence source) first 3 = "AUG") "invalid_translation";
      expect (H.modification_inventory_status (I.chemistry source) = H.Declared) "unsupported_translation_chemistry";
      port_id,selection,source,source_path,policy,G.Path.length source_path / 3 - 1) (translation_specs step) in
  reserve remaining (List.fold_left (fun count (_,_,_,_,_,length) -> count + length) 0 plans);
  (match operation with
   | O.Ribosomal_skipping {products;_} ->
       let cursor = ref 0 in
       List.sort (fun a b -> Int.compare (G.Span.start (C.Peptide_product.residues a)) (G.Span.start (C.Peptide_product.residues b))) products
       |> List.iter (fun product -> let residues = C.Peptide_product.residues product in
           expect (G.Span.start residues = !cursor && G.Span.length residues > 0) "invalid_skipping_partition"; cursor := G.Span.stop residues);
       let _,_,_,_,_,expected = List.hd plans in expect (!cursor = expected) "invalid_skipping_partition"
   | _ -> ());
  List.concat_map (fun (port_id,selection,source,source_path,policy,residue_count) ->
      let peptide = translated_peptide budget step source source_path policy in
      let source_span = List.hd (G.Path.spans source_path) in
      let stop = A.Consumed_segment.make ~source_id:(reference_id selection)
          ~source_path:(path ~id:(space_id (I.space source)) ~spans:[span (G.Span.stop source_span - 3) (G.Span.stop source_span)] ~strand:G.Forward) in
      let pieces = match operation with O.Ribosomal_skipping {products;_} -> List.map (fun product -> C.Peptide_product.port_id product,C.Peptide_product.residues product) products
        | _ -> [port_id,span 0 residue_count] in
      List.map (fun (id,residues) ->
          let port = List.find (fun port -> C.Product_port.id port = id) ports in
          let segment = A.Derived_segment.make ~destination:(span 0 (G.Span.length residues)) ~source_id:(reference_id selection)
              ~source_path:(path ~id:(space_id (I.space source)) ~spans:[span (G.Span.start source_span + 3 * G.Span.start residues)
                  (G.Span.start source_span + 3 * G.Span.stop residues)] ~strand:G.Forward) ~rule:A.Derived_segment.Translation_codon in
          let product = finish_value budget step port source (String.sub peptide (G.Span.start residues) (G.Span.length residues)) [segment] [stop] in
          port,product,[reference_id selection,source]) pieces) plans
let materialize_member budget member source =
  charge budget (String.length (I.sequence source));
  reserve_json budget (H.to_json (I.chemistry source));
  List.iter (fun feature -> reserve_json budget (N.Feature.to_json feature)) (I.features source);
  Diagnostic.require (C.Output_member.sequence_extent member = I.sequence_extent source) "invalid_construction_finalization" "Finalization cannot change supplied sequence extent.";
  let old_space = I.space source in
  let output_space = space ~id:(C.Output_member.space_id member) ~alphabet:(G.Space.alphabet old_space) ~length:(G.Space.length old_space) ~topology:(G.Space.topology old_space) in
  let features = List.map (fun feature -> N.Feature.make ?reading_frame:(N.Feature.reading_frame feature) ~id:(N.Feature.id feature)
      ~kind:(N.Feature.kind feature) ~path:(Option.map (reframe_path (space_id output_space)) (N.Feature.path feature)) ~provenance:(N.Feature.provenance feature) ()) (I.features source) in
  let origin = N.Assembly_origin.make ~id:(C.Output_member.id member ^ ".origin") ~destination:(whole output_space)
      ~source_space:old_space ~source_path:(whole old_space) ~provenance:(C.Output_member.provenance member) in
  N.make ~id:(C.Output_member.id member) ~form:(C.Output_member.form member) ~space:output_space ~sequence:(I.sequence source)
    ~sequence_extent:(C.Output_member.sequence_extent member) ~coding_status:(C.Output_member.coding_status member) ~assembly:[origin]
    ~features ~chemistry:(reframe_chemistry (I.chemistry source) (space_id output_space)) ~provenance:(C.Output_member.provenance member)
let primitive_proposals budget step selections inputs initial_paths remaining =
  reserve_json budget (C.Transform_step.to_json step);
  let operation = O.specification (C.Transform_step.operation step) and ports = C.Transform_step.ports step in
  let alphabets = List.map (fun input -> G.Space.alphabet (I.space input)) inputs |> List.sort_uniq Stdlib.compare in
  let expected_alphabet,allowed = match operation with
    | O.Rna_cleavage _ | O.Rna_splicing _ | O.Circularization _ -> G.Rna,alphabets = [G.Rna]
    | O.Protein_cleavage _ | O.Protein_splicing _ -> G.Protein,alphabets = [G.Protein]
    | O.Transcription _ -> G.Rna,alphabets = [G.Dna]
    | _ -> let alphabet = G.Space.alphabet (I.space (List.hd inputs)) in
        alphabet, List.length alphabets = 1 && (match operation with O.Orientation _ -> alphabet = G.Dna || alphabet = G.Rna | _ -> true) in
  expect (allowed && List.for_all (fun port -> C.Product_port.alphabet port = expected_alphabet) ports) "unsupported_alphabet";
  (match operation with O.Transcription _ -> let first = List.hd initial_paths in
       expect (G.Path.strand first = G.Forward && List.length (G.Path.spans first) = 1) "unsupported_transcription_path" | _ -> ());
  let expected_topology,allowed_topology = match operation with
    | O.Rna_cleavage _ | O.Rna_splicing _ | O.Protein_cleavage _ | O.Protein_splicing _ | O.Circularization _ ->
        (match operation with O.Circularization _ -> G.Circular | _ -> G.Linear), G.Space.topology (I.space (List.hd inputs)) = G.Linear
    | _ -> (match operation with O.Slice _ | O.Orientation _ when C.Selection.path (List.hd selections) = None -> G.Space.topology (I.space (List.hd inputs)) | _ -> G.Linear),true in
  expect (allowed_topology && List.for_all (fun port -> C.Product_port.topology port = expected_topology) ports) "unsupported_topology";
  let planned,rule = match operation with
    | O.Rna_cleavage {products;_} | O.Rna_splicing {products;_} | O.Protein_cleavage {products;_} | O.Protein_splicing {products;_} ->
        let source_space = I.space (List.hd inputs) in
        (try List.iter (fun recipe -> let path = C.Processing_product.path recipe in G.Path.validate_for path source_space;
             expect (G.Path.length path > 0 && List.for_all (fun span -> G.Span.length span > 0) (G.Path.spans path)) "invalid_selection") products
         with Diagnostic.Error _ -> raise (Problem "invalid_selection"));
        let cursor = ref 0 and valid = ref true in
        let spans = List.concat_map (fun recipe -> G.Path.spans (C.Processing_product.path recipe)) products
            |> List.sort (fun a b -> Stdlib.compare (G.Span.start a,G.Span.stop a) (G.Span.start b,G.Span.stop b)) in
        List.iter (fun span -> if G.Span.start span <> !cursor then valid := false; cursor := G.Span.stop span) spans;
        if !cursor <> G.Space.length source_space then valid := false;
        let rec ordered = function first :: (second :: _ as rest) -> G.Span.stop first <= G.Span.start second && ordered rest | _ -> true in
        List.iter (fun recipe -> if not (ordered (G.Path.spans (C.Processing_product.path recipe))) then valid := false) products;
        expect !valid "invalid_processing_partition";
        List.map (fun port -> let recipe = List.find (fun recipe -> C.Processing_product.port_id recipe = C.Product_port.id port) products in
            port,[C.Processing_product.path recipe]) ports, A.Derived_segment.Copy
    | O.Circularization {origin;_} ->
        let source_space = I.space (List.hd inputs) in let length = G.Space.length source_space in
        expect (origin >= 0 && origin < length) "invalid_selection";
        let spans = [span origin length] @ (if origin = 0 then [] else [span 0 origin]) in
        [List.hd ports,[path ~id:(space_id source_space) ~spans ~strand:G.Forward]],A.Derived_segment.Copy
    | O.Orientation {action;_} ->
        let paths = List.map (fun original -> path ~id:(G.Space_id.to_string (G.Path.space_id original)) ~spans:(List.rev (G.Path.spans original))
            ~strand:(if G.Path.strand original = G.Forward then G.Reverse else G.Forward)) initial_paths in
        [List.hd ports,paths],(if action = O.Reverse_complement then A.Derived_segment.Complement else A.Derived_segment.Copy)
    | O.Transcription _ -> [List.hd ports,initial_paths],A.Derived_segment.Transcription
    | O.Slice _ | O.Concatenate _ -> [List.hd ports,initial_paths],A.Derived_segment.Copy
    | O.Base_editing _ | O.Translation _ | O.Multi_orf_translation _ | O.Conditional_translation _ | O.Ribosomal_skipping _ -> raise (Problem "invalid_operation") in
  reserve remaining (List.fold_left (fun total (_,paths) -> List.fold_left (fun total path -> total + G.Path.length path) total paths) 0 planned);
  let input_values = List.fold_left (fun map (selection,source) -> Names.add (reference_id selection) source map) Names.empty (List.combine selections inputs) |> Names.bindings in
  List.map (fun (port,paths) -> port,propose budget step port selections inputs paths rule,input_values) planned
type recipe = {
  sources:C.Root_source.t list; steps:C.Transform_step.t list;
  output_members:C.Output_member.t list; complex_members:C.Complex_member.t list;
  requirements:C.Member_requirement.t list; amounts:C.Amount_declaration.t list;
}
let reconstruct_recipe ~budget (recipe:recipe) ~authority_json
    ~make_bundle ~bundle_to_json ~validate_bundle ~make_candidate =
  let available = ref (List.fold_left (fun map root -> Names.add (C.Root_source.id root) (I.of_molecule (C.Root_source.molecule root)) map) Names.empty recipe.sources) in
  let products = ref [] and failures = ref [] and transitions = ref [] and remaining = ref C.max_cumulative_produced_residues in
  List.iter (fun step ->
      reserve_json budget (C.Transform_step.to_json step);
      let selections = operands (C.Transform_step.operation step) in
      let reject code = failures := ("step:" ^ C.Transform_step.id step ^ ":" ^ code) :: !failures in
      if List.exists (fun selection -> not (Names.mem (reference_id selection) !available)) selections then reject "unavailable_input"
      else
        let inputs = List.map (fun selection -> Names.find (reference_id selection) !available) selections in
        if List.exists (fun source -> I.sequence_extent source <> H.Complete) inputs then reject "incomplete_input"
        else
          let paths = try Some (List.map2 (fun selection source ->
              let path = match C.Selection.path selection with None -> whole (I.space source) | Some value -> value in
              G.Path.validate_for path (I.space source); expect (G.Path.length path > 0) "invalid_selection"; path) selections inputs)
            with Diagnostic.Error _ | Problem _ -> None in
          match paths with None -> reject "invalid_selection" | Some paths ->
            (* Materialize all proposals before publishing any value. A failed
               step retains consumed work but never exposes staged byproducts. *)
            let proposed = try Some (match O.specification (C.Transform_step.operation step) with
                | O.Base_editing {input;canonical_edits;chemical_edits} -> edited_proposals budget step !available remaining input canonical_edits chemical_edits
                | O.Translation _ | O.Multi_orf_translation _ | O.Conditional_translation _ | O.Ribosomal_skipping _ -> translation_proposals budget step !available remaining
                | _ -> primitive_proposals budget step selections inputs paths remaining)
              with Problem code -> reject code; None | Diagnostic.Error _ -> reject "invalid_operation"; None in
            Option.iter (List.iter (fun (port,product,input_values) ->
                products := product :: !products; available := Names.add (A.Value.id product) (I.of_value product) !available;
                transitions := {step;port;inputs=input_values;product} :: !transitions)) proposed) recipe.steps;
  let candidate ?(amounts = []) bundle missing =
    reserve_json budget (authority_json ());
    List.iter (fun value -> reserve_json budget (A.Value.to_json value)) !products;
    Option.iter (fun value -> reserve_json budget (bundle_to_json value)) bundle;
    make_candidate ~values:(List.rev !products)
      ~bundle ~missing_members:missing ~diagnostics:(List.sort_uniq String.compare !failures) ~experimental_amounts:amounts in
  let final_residues = List.fold_left (fun total member -> match Names.find_opt (C.Value_ref.id (C.Output_member.value member)) !available with
      | None -> total | Some value -> total + G.Space.length (I.space value)) 0 recipe.output_members in
  if final_residues > Molecular_record.max_residues then (
    failures := "bundle:residue_budget" :: !failures;
    candidate None (List.map C.Output_member.id recipe.output_members @ List.map C.Complex_member.id recipe.complex_members), List.rev !transitions
  ) else (
    let members = ref Names.empty and missing = ref [] in
    List.iter (fun member ->
        let id = C.Output_member.id member in
        match Names.find_opt (C.Value_ref.id (C.Output_member.value member)) !available with
        | None -> missing := id :: !missing; failures := ("member:" ^ id ^ ":unavailable_value") :: !failures
        | Some value ->
            (match materialize_member budget member value with
             | molecule -> members := Names.add id molecule !members;
                 if N.complete_nominal_identity molecule = None then failures := ("member:" ^ id ^ ":nominal_incomplete") :: !failures
             | exception Diagnostic.Error _ -> missing := id :: !missing; failures := ("member:" ^ id ^ ":invalid_molecule") :: !failures)) recipe.output_members;
    let complexes = ref Names.empty in
    List.iter (fun plan ->
        reserve_json budget (C.Complex_member.to_json plan);
        let id = C.Complex_member.id plan in
        if List.exists (fun part -> not (Names.mem (C.Complex_constituent.member_id part) !members)) (C.Complex_member.constituents plan) then (
          missing := id :: !missing; failures := ("member:" ^ id ^ ":unavailable_value") :: !failures
        ) else (
          let materialize () = N.Complex.make ~id ~kind:(C.Complex_member.kind plan) ~provenance:(C.Complex_member.provenance plan)
              ~constituents:(List.map (fun part -> let member = Names.find (C.Complex_constituent.member_id part) !members in
                  reserve_json budget (N.to_json member);
                  N.Constituent.make ~molecule_id:(N.id member) ~molecule_fingerprint:(N.fingerprint member) ~stoichiometry:(C.Complex_constituent.stoichiometry part)
                    ~provenance:(C.Complex_constituent.provenance part)) (C.Complex_member.constituents plan)) in
          match materialize () with
          | complex -> complexes := Names.add id complex !complexes;
              if List.exists (fun part -> C.Complex_constituent.stoichiometry part = None || not (N.declared_nominal_complete (Names.find (C.Complex_constituent.member_id part) !members)))
                  (C.Complex_member.constituents plan) then failures := ("member:" ^ id ^ ":nominal_incomplete") :: !failures
          | exception Diagnostic.Error _ -> missing := id :: !missing; failures := ("member:" ^ id ^ ":invalid_molecule") :: !failures
        )) recipe.complex_members;
    let bundle,amounts = if !missing <> [] then None,[] else
      let construct () =
        let subject_fingerprint id = match Names.find_opt id !members with
          | Some member -> reserve_json budget (N.to_json member);N.fingerprint member
          | None -> let value=Names.find id !complexes in reserve_json budget (N.Complex.to_json value);N.Complex.fingerprint value in
        let roles = List.concat_map (fun requirement -> match C.Member_requirement.member_id requirement with None -> [] | Some id ->
            List.map (fun role -> N.Role.make ~id:(C.Role.id role) ~subject_id:id ~subject_fingerprint:(subject_fingerprint id)
                ~role:(C.Role.role role) ~purpose:(C.Role.purpose role) ~compartment:(C.Role.compartment role)) (C.Member_requirement.roles requirement)) recipe.requirements in
        let bundle = make_bundle ~molecules:(Names.bindings !members |> List.map snd)
            ~complexes:(Names.bindings !complexes |> List.map snd) ~role_instances:roles ~form_mappings:[] in
        let amounts = List.map (fun amount ->
            let quantity = match C.Amount_declaration.quantity amount with C.Amount_declaration.Unknown -> S.Amount.Unknown
              | C.Amount_declaration.Integer value -> S.Amount.Integer value | C.Amount_declaration.Real value -> S.Amount.Real value in
            S.Amount.make ~id:(C.Amount_declaration.id amount) ~subject_id:(C.Amount_declaration.subject_id amount)
              ~subject_fingerprint:(subject_fingerprint (C.Amount_declaration.subject_id amount)) ~preparation_id:(C.Amount_declaration.preparation_id amount)
              ~role_instance_ids:(C.Amount_declaration.role_instance_ids amount) ~quantity ~unit:(C.Amount_declaration.unit amount)
              ~provenance:(C.Amount_declaration.provenance amount)) recipe.amounts in
        validate_bundle bundle amounts; Some bundle,amounts in
      match construct () with result -> result | exception Diagnostic.Error _ -> failures := "bundle:invalid_inventory" :: !failures; None,[] in
    candidate ~amounts bundle (List.rev !missing),List.rev !transitions
  )

let reconstruct ~budget request = protect (fun () ->
  let recipe = {sources=C.Request.sources request;steps=C.Request.steps request;
      output_members=C.Request.output_members request;complex_members=C.Request.complex_members request;
      requirements=C.Request.requirements request;amounts=C.Request.amounts request} in
  reconstruct_recipe ~budget recipe ~authority_json:(fun () -> C.Request.to_json request)
    ~make_bundle:(S.make ~id:(C.Request.id request ^ ".molecules") ~request:(C.Request.circuit request))
    ~bundle_to_json:S.to_json
    ~validate_bundle:(fun bundle amounts -> ignore (S.Artifact.make ~bundle ~experimental_amounts:amounts ~run_metadata:[]))
    ~make_candidate:(A.make ~request_fingerprint:(C.Request.fingerprint request)))

let reconstruct_template ~budget ~member_order template = protect (fun () ->
  let module P = Payload_template in
  let module K = Construction_content in
  let authority = K.authority_json ~template ~member_order in
  let recipe = {sources=P.sources template;steps=P.steps template;
      output_members=P.output_members template;complex_members=P.complex_members template;
      requirements=P.requirements template;amounts=P.amounts template} in
  let make_bundle ~molecules ~complexes ~role_instances ~form_mappings =
    let molecules = List.map (fun id -> List.find (fun value -> N.id value = id) molecules) member_order in
    K.Inventory.make ~id:(P.id template ^ ".molecules") ~molecules ~complexes ~role_instances ~form_mappings in
  reconstruct_recipe ~budget recipe ~authority_json:(fun () -> authority)
    ~make_bundle ~bundle_to_json:K.Inventory.to_json ~validate_bundle:K.Inventory.validate_amounts
    ~make_candidate:(fun ~values ~bundle ~missing_members ~diagnostics ~experimental_amounts ->
      K.make ~authority_fingerprint:(Canonical.fingerprint authority) ~member_order ~values ~inventory:bundle
        ~missing_members ~diagnostics ~experimental_amounts))

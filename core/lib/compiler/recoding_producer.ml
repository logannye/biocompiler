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

(* Traverse typed children before a codec allocates their JSON lists. These are
   count-only outer passes; they never debit the historic 50M work owner. *)
module Serialization = struct
  let text charge value = charge (1+String.length value)
  let iter charge f values = List.iter (fun value -> charge 1; f value) values
  let path charge value =
    charge 1; text charge (G.Space_id.to_string (G.Path.space_id value));
    iter charge (fun _ -> charge 2) (G.Path.spans value)
  let provenance charge value =
    let module P = Molecular_record.Provenance in
    charge 1; text charge (P.reason value); Option.iter (text charge) (P.locator value);
    iter charge (fun pin -> text charge (Pinned_identity.id pin); text charge (Pinned_identity.version pin);
      text charge (Pinned_identity.content_fingerprint pin)) (P.authority value)
  let chemical_identity charge value =
    text charge (H.Chemical_identity.namespace value); text charge (H.Chemical_identity.accession value);
    text charge (H.Chemical_identity.version value)
  let chemistry charge value =
    charge 1;
    List.iter (fun facet -> let claim=facet value in charge 1;
      Option.iter (chemical_identity charge) (H.Claim.identity claim);
      provenance charge (H.Claim.provenance claim)) [H.cap;H.start_end;H.finish_end];
    iter charge (fun modification -> text charge (H.Modification.id modification);
      chemical_identity charge (H.Modification.identity modification);
      iter charge (fun _ -> charge 1) (H.Modification.positions modification);
      provenance charge (H.Modification.provenance modification)) (H.modifications value);
    provenance charge (H.modification_inventory_provenance value);
    let tail=H.terminal_tail value in charge 1;
    Option.iter (path charge) (H.Tail.path tail); provenance charge (H.Tail.provenance tail)
  let feature charge value =
    text charge (Molecule.Feature.id value); text charge (Molecule.Feature.kind value);
    Option.iter (path charge) (Molecule.Feature.path value); provenance charge (Molecule.Feature.provenance value)
  let value charge value =
    text charge (A.Value.id value); text charge (A.Value.step_id value);
    text charge (G.Space_id.to_string (G.Space.id (A.Value.space value)));
    text charge (A.Value.sequence value); chemistry charge (A.Value.chemistry value);
    iter charge (feature charge) (A.Value.features value);
    iter charge (fun segment -> charge 2; text charge (A.Derived_segment.source_id segment);
      path charge (A.Derived_segment.source_path segment)) (A.Value.segments value);
    iter charge (fun segment -> text charge (A.Consumed_segment.source_id segment);
      path charge (A.Consumed_segment.source_path segment)) (A.Value.consumed value)
  let molecule charge value =
    text charge (Molecule.id value); text charge (Molecule.sequence value);
    text charge (G.Space_id.to_string (G.Space.id (Molecule.space value)));
    chemistry charge (Molecule.chemistry value); provenance charge (Molecule.provenance value);
    iter charge (feature charge) (Molecule.features value);
    iter charge (fun origin -> text charge (Molecule.Assembly_origin.id origin);
      path charge (Molecule.Assembly_origin.destination origin); path charge (Molecule.Assembly_origin.source_path origin);
      text charge (G.Space_id.to_string (G.Space.id (Molecule.Assembly_origin.source_space origin)));
      provenance charge (Molecule.Assembly_origin.provenance origin)) (Molecule.assembly value)
  let complex charge value =
    text charge (Molecule.Complex.id value); provenance charge (Molecule.Complex.provenance value);
    iter charge (fun constituent -> text charge (Molecule.Constituent.molecule_id constituent);
      text charge (Molecule.Constituent.molecule_fingerprint constituent);
      provenance charge (Molecule.Constituent.provenance constituent)) (Molecule.Complex.constituents value)
  let role charge value = List.iter (fun field -> text charge (field value))
    [Molecule.Role.id;Molecule.Role.subject_id;Molecule.Role.subject_fingerprint;Molecule.Role.role;Molecule.Role.compartment]
  let mapping charge value =
    List.iter (fun field -> text charge (field value)) [Molecule.Form_mapping.id;Molecule.Form_mapping.source_molecule_id;
      Molecule.Form_mapping.source_molecule_fingerprint;Molecule.Form_mapping.destination_molecule_id;
      Molecule.Form_mapping.destination_molecule_fingerprint];
    path charge (Molecule.Form_mapping.source_path value); path charge (Molecule.Form_mapping.destination_path value);
    provenance charge (Molecule.Form_mapping.provenance value)
  let selection charge value =
    text charge (C.Value_ref.id (C.Selection.value value)); Option.iter (path charge) (C.Selection.path value)
  let translation charge policy =
    text charge (R.Translation_policy.genetic_code policy);
    iter charge (fun row -> charge 2; text charge (R.Codon_recoding.expected_triplet row);
      text charge (R.Codon_recoding.condition row)) (R.Translation_policy.recodings policy)
  let operation charge value =
    charge 1;
    let processing input products = selection charge input; iter charge (fun product ->
      text charge (C.Processing_product.port_id product); path charge (C.Processing_product.path product)) products in
    match C.Operation.specification value with
    | C.Operation.Slice input | C.Operation.Transcription input
    | C.Operation.Orientation {input;_} | C.Operation.Circularization {input;_} -> selection charge input
    | C.Operation.Concatenate inputs -> iter charge (selection charge) inputs
    | C.Operation.Rna_cleavage {input;products} | C.Operation.Rna_splicing {input;products}
    | C.Operation.Protein_cleavage {input;products} | C.Operation.Protein_splicing {input;products} -> processing input products
    | C.Operation.Base_editing {input;canonical_edits;chemical_edits} ->
        selection charge input; iter charge (fun _ -> charge 3) canonical_edits;
        iter charge (fun row -> charge 2; Option.iter (chemical_identity charge) (R.Chemical_edit.before row);
          Option.iter (chemical_identity charge) (R.Chemical_edit.after row)) chemical_edits
    | C.Operation.Translation {input;policy} -> selection charge input; translation charge policy
    | C.Operation.Multi_orf_translation products -> iter charge (fun product ->
        text charge (C.Translation_product.port_id product); selection charge (C.Translation_product.input product);
        translation charge (C.Translation_product.policy product)) products
    | C.Operation.Conditional_translation branches -> iter charge (fun branch ->
        text charge (C.Translation_branch.id branch); text charge (C.Translation_branch.condition branch);
        selection charge (C.Translation_branch.input branch); Option.iter (translation charge) (C.Translation_branch.policy branch);
        Option.iter (text charge) (C.Translation_branch.port_id branch)) branches
    | C.Operation.Ribosomal_skipping {input;policy;products;event_id} ->
        selection charge input; translation charge policy; text charge event_id;
        iter charge (fun product -> charge 2; text charge (C.Peptide_product.port_id product)) products
  let port charge value =
    text charge (C.Product_port.id value); text charge (C.Product_port.space_id value);
    let chemistry_rule=C.Product_port.chemistry_transition value in
    Option.iter (chemistry charge) (T.Chemistry.output chemistry_rule);
    provenance charge (T.Chemistry.provenance chemistry_rule);
    iter charge (fun row -> text charge (T.Chemistry_disposition.source_id row);
      text charge (T.Component.to_string (T.Chemistry_disposition.component row));
      iter charge (fun facet -> text charge (T.Component.to_string facet)) (T.Chemistry_disposition.destination_components row);
      provenance charge (T.Chemistry_disposition.provenance row)) (T.Chemistry.dispositions chemistry_rule);
    let feature_rule=C.Product_port.feature_transition value in
    provenance charge (T.Feature.provenance feature_rule);
    iter charge (fun row -> text charge (T.Feature_disposition.source_id row); text charge (T.Feature_disposition.feature_id row);
      iter charge (feature charge) (T.Feature_disposition.outputs row);
      provenance charge (T.Feature_disposition.provenance row)) (T.Feature.dispositions feature_rule);
    iter charge (feature charge) (T.Feature.added feature_rule)
  let step charge value =
    text charge (C.Transform_step.id value); operation charge (C.Transform_step.operation value);
    iter charge (port charge) (C.Transform_step.ports value);
    iter charge (text charge) (C.Transform_step.assumptions value); provenance charge (C.Transform_step.provenance value)
  let template charge value =
    let module P=Payload_template in
    text charge (P.id value);
    iter charge (fun root -> text charge (C.Root_source.id root); molecule charge (C.Root_source.molecule root);
      provenance charge (C.Root_source.provenance root)) (P.sources value);
    iter charge (step charge) (P.steps value);
    iter charge (fun member -> text charge (C.Output_member.id member); text charge (C.Output_member.space_id member);
      text charge (C.Value_ref.id (C.Output_member.value member)); provenance charge (C.Output_member.provenance member)) (P.output_members value);
    iter charge (fun member -> text charge (C.Complex_member.id member); provenance charge (C.Complex_member.provenance member);
      iter charge (fun row -> text charge (C.Complex_constituent.member_id row);
        provenance charge (C.Complex_constituent.provenance row)) (C.Complex_member.constituents member)) (P.complex_members value);
    iter charge (fun row -> text charge (C.Member_requirement.id row);
      (match C.Member_requirement.subject row with C.Member_requirement.Materialized id -> text charge id
        | C.Member_requirement.External {id;fingerprint} -> text charge id; text charge fingerprint);
      iter charge (fun role -> text charge (C.Role.id role); text charge (C.Role.role role);
        text charge (C.Role.compartment role)) (C.Member_requirement.roles row)) (P.requirements value);
    iter charge (fun amount -> text charge (C.Amount_declaration.id amount); text charge (C.Amount_declaration.subject_id amount);
      text charge (C.Amount_declaration.preparation_id amount); text charge (C.Amount_declaration.unit amount);
      iter charge (text charge) (C.Amount_declaration.role_instance_ids amount);
      (match C.Amount_declaration.quantity amount with C.Amount_declaration.Integer n -> charge (1+Z.numbits n) | _ -> charge 1);
      provenance charge (C.Amount_declaration.provenance amount)) (P.amounts value);
    iter charge (fun structure -> text charge (Payload_structure.member_id structure);
      iter charge (fun region -> text charge (Payload_structure.Region.feature_id region);
        text charge (Payload_structure.Region.kind region)) (Payload_structure.regions structure);
      provenance charge (Payload_structure.provenance structure)) (P.payload_structures value)
  let amount charge value =
    let module X = Molecule_set.Amount in
    List.iter (fun field -> text charge (field value)) [X.id;X.subject_id;X.subject_fingerprint;X.preparation_id;X.unit];
    iter charge (text charge) (X.role_instance_ids value); provenance charge (X.provenance value);
    (match X.quantity value with X.Integer n -> charge (1+Z.numbits n) | _ -> charge 1)
end

let input_error message = Diagnostic.fail "invalid_construction_producer_input" message

module Available = struct
  type t = material Names.t
  let maximum = C.max_sources + C.max_products
  let of_bindings ?(charge=Bioc_checker.Policy_generation_meter.no_charge) bindings =
    let module Meter = Bioc_checker.Policy_generation_meter.Make(struct let charge=charge end) in
    let module List = Meter.List in
    (* Preserve the original bounded-prefix rejection even for cyclic native
       lists. A metered caller pays that bounded pass before it runs. *)
    if charge != Bioc_checker.Policy_generation_meter.no_charge then (
      let rec prefix remaining = function
        | [] -> charge 1
        | _::rest -> charge 1; if remaining>0 then prefix (remaining-1) rest in
      prefix maximum bindings);
    ignore (Molecular_record.bounded_length ~maximum bindings);
    List.iter (fun (id,_) -> charge (String.length id)) bindings;
    List.fold_left (fun map (id,value) ->
        ignore (Molecular_record.text (Json.String id));
        Names.iter (fun key _ -> charge (1+String.length key+String.length id)) map;
        if Names.mem id map then input_error "Duplicate available material identity.";
        Names.add id value map) Names.empty bindings
  let find ?(charge=Bioc_checker.Policy_generation_meter.no_charge) id values =
    Names.iter (fun key _ -> charge (1+String.length key+String.length id)) values;
    Names.find_opt id values
  let add_products ?(charge=Bioc_checker.Policy_generation_meter.no_charge) values map =
    let module Meter = Bioc_checker.Policy_generation_meter.Make(struct let charge=charge end) in
    let module List = Meter.List in
    Names.iter (fun key _ -> charge (1+String.length key)) map;
    ignore (Molecular_record.bounded_length ~maximum:C.max_products values);
    let result = List.fold_left (fun map value ->
        let id = A.Value.id value in
        Names.iter (fun key _ -> charge (1+String.length key+String.length id)) map;
        if Names.mem id map then input_error "Available product would replace existing material authority.";
        Names.add id (Product value) map) map values in
    if Names.cardinal result > maximum then input_error "Available material inventory exceeds its fixed bound.";
    result
end

let max_work = 50_000_000
type budget = {outer:int -> unit;work:Bioc_checker.Work_budget.t; output:Bioc_checker.Work_budget.output; staged:Bioc_checker.Work_budget.output}
exception Budget_exhausted of Diagnostic.t
let protect run = try run () with Budget_exhausted diagnostic -> raise (Diagnostic.Error diagnostic)
let make_budget ?parent ?(charge=Bioc_checker.Policy_generation_meter.no_charge) ?(maximum=max_work) () =
  Diagnostic.require (maximum >= 0 && maximum <= max_work) "construction_producer_limit" "Invalid native producer work ceiling.";
  let profile="biocompiler.construction_producer.resources.v1" and error_code="construction_producer_limit" in
  let work=match parent with
    | None -> Bioc_checker.Work_budget.create ~profile ~error_code ~maximum ()
    | Some parent -> Bioc_checker.Work_budget.nested ~parent ~profile ~error_code ~maximum () in
  let output ()=Bioc_checker.Work_budget.create_output ~profile ~error_code:"construction_producer_output_limit"
      ~max_bytes:Molecular_record.max_json_bytes ~max_nodes:Molecular_record.max_items () in
  {outer=charge;work;output=output ();staged=output ()}
let outer_charge budget amount =
  try budget.outer amount with Diagnostic.Error diagnostic -> raise (Budget_exhausted diagnostic)
let outer_meter budget =
  if budget.outer == Bioc_checker.Policy_generation_meter.no_charge then Bioc_checker.Policy_generation_meter.no_charge
  else outer_charge budget
let charge budget amount =
  try Bioc_checker.Work_budget.charge budget.work amount; outer_charge budget amount
  with Diagnostic.Error diagnostic -> raise (Budget_exhausted diagnostic)
let reserve_output budget raw =
  let module Meter=Bioc_checker.Policy_generation_meter.Make(struct let charge=outer_meter budget end) in
  Meter.serialization raw;
  try Bioc_checker.Work_budget.reserve_json budget.output raw
  with Diagnostic.Error diagnostic -> raise (Budget_exhausted diagnostic)
let reserve_staged budget raw =
  let module Meter=Bioc_checker.Policy_generation_meter.Make(struct let charge=outer_meter budget end) in
  Meter.serialization raw;
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

let step_json budget value = Serialization.step (outer_charge budget) value; C.Transform_step.to_json value
let port_json budget value = Serialization.port (outer_charge budget) value; C.Product_port.to_json value
let value_json budget value = Serialization.value (outer_charge budget) value; A.Value.to_json value
let molecule_json budget value = Serialization.molecule (outer_charge budget) value; Molecule.to_json value
let chemistry_json budget value = Serialization.chemistry (outer_charge budget) value; H.to_json value
let feature_json budget value = Serialization.feature (outer_charge budget) value; Molecule.Feature.to_json value
let complex_json budget value = Serialization.complex (outer_charge budget) value; Molecule.Complex.to_json value
let amount_json budget value = Serialization.amount (outer_charge budget) value; Molecule_set.Amount.to_json value

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
  let module Meter=Bioc_checker.Policy_generation_meter.Make(struct let charge=outer_meter budget end) in
  let module List=Meter.List in
  let module String=Meter.String in
  let ( @ ) = List.append in

  reserve_json budget (port_json budget port);
  reserve_json budget (chemistry_json budget (chemistry source));
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
  let chemistry = output_chemistry port source in
  Serialization.chemistry (outer_charge budget) chemistry;
  List.iter (Serialization.feature (outer_charge budget)) features;
  let value=A.Value.make ~id:(C.Product_port.id port) ~space:frame ~sequence ~chemistry
    ~features ~segments ~step_id:(C.Transform_step.id step) ~sequence_extent:H.Complete ~consumed in
  reserve_output budget (value_json budget value);value
let chemical_key parent identity = Option.map (fun value ->
    parent,H.Chemical_identity.namespace value,H.Chemical_identity.accession value,H.Chemical_identity.version value) identity
let chemical_equal budget left right =
  let inspect = function None -> outer_charge budget 1 | Some (_,namespace,accession,version) ->
    outer_charge budget (1+String.length namespace+String.length accession+String.length version) in
  inspect left; inspect right; left=right
let modifications budget chemistry =
  let module Meter=Bioc_checker.Policy_generation_meter.Make(struct let charge=outer_meter budget end) in
  let module List=Meter.List in

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
  let module Meter=Bioc_checker.Policy_generation_meter.Make(struct let charge=outer_meter budget end) in
  let module List=Meter.List in
  let module String=Meter.String in
  let module Json=Meter.Json in

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
      require (chemical_equal budget (at old_view original position) (chemical_key parent (R.Chemical_edit.before edit))) "invalid_edit";
      Hashtbl.replace expected position (chemical_key parent (R.Chemical_edit.after edit))) chemical_edits;
  let sequence = Bytes.to_string letters in
  for position=0 to String.length sequence-1 do
    charge budget 1;
    let wanted = match Hashtbl.find_opt expected position with Some value -> value | None -> at old_view original position in
    require (chemical_equal budget (at new_view sequence position) wanted) "invalid_edit"
  done;
  let selected = path (G.Space.id (space source)) [span 0 (String.length sequence)] in
  let segment = A.Derived_segment.make ~destination:(span 0 (String.length sequence))
      ~source_id:(C.Value_ref.id (C.Selection.value input)) ~source_path:selected ~rule:A.Derived_segment.Rna_editing in
  output_value budget step port source sequence (G.Space.topology (space source)) [segment] []
let translation_span budget selection source =
  let module Meter=Bioc_checker.Policy_generation_meter.Make(struct let charge=outer_meter budget end) in
  let module List=Meter.List in
  let module String=Meter.String in

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
  let module Meter=Bioc_checker.Policy_generation_meter.Make(struct let charge=outer_meter budget end) in
  let module List=Meter.List in
  let module String=Meter.String in

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
  let module Meter=Bioc_checker.Policy_generation_meter.Make(struct let charge=outer_meter budget end) in
  let module List=Meter.List in
  let module String=Meter.String in

  reserve_json budget (step_json budget step);
  let used = ref 0 in
  try
    let operation = C.Transform_step.operation step in
    let selections = C.operation_selections operation in
    charge budget (List.length selections);
    let get selection = match Available.find ~charge:(outer_charge budget) (C.Value_ref.id (C.Selection.value selection)) available with
      | Some value -> value | None -> raise (Problem "unavailable_input") in
    require (List.for_all (fun selection -> Available.find ~charge:(outer_charge budget) (C.Value_ref.id (C.Selection.value selection)) available <> None) selections)
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

open Bioc_wire
open Bioc_domain
module C = Construction
module G = Molecule_coordinates
module H = Molecule_chemistry
module T = Molecular_transition
module A = Construction_artifact
module R = Recoding_producer
let implementation_version = "biocompiler.ocaml.construction_producer.v0.1"
module Limits = struct
  type t = {produced_residues:int; final_residues:int; work:int}
  let make ?(produced_residues=C.max_cumulative_produced_residues)
      ?(final_residues=Molecular_record.max_residues) ?(work=R.max_work) () =
    Diagnostic.require (produced_residues>=0 && produced_residues<=C.max_cumulative_produced_residues &&
        final_residues>=0 && final_residues<=Molecular_record.max_residues && work>=0 && work<=R.max_work)
      "construction_producer_limit" "A producer limit cannot exceed its fixed resource profile.";
    {produced_residues;final_residues;work}
end
exception Problem of string
let require condition code = if not condition then raise (Problem code)
let obj value = Json.Object value
let str value = Json.String value
let set key value fields = obj ((key,value)::List.remove_assoc key (Json.object_fields fields))
let span first last = G.Span.of_json (obj ["schema_version",str "biocompiler.molecule_index_span.v0.1";
    "start",Json.int first;"end",Json.int last])
let path frame spans strand = G.Path.of_json (obj ["schema_version",str "biocompiler.molecule_coordinate_path.v0.1";
    "space_id",str (G.Space_id.to_string frame);"spans",Json.Array (List.map G.Span.to_json spans);
    "strand",str (if strand=G.Forward then "+" else "-")])
let full_path frame = path (G.Space.id frame) [span 0 (G.Space.length frame)] G.Forward
let relabel_path id value = G.Path.of_json (set "space_id" (str id) (G.Path.to_json value))
let relabel_chemistry id value =
  let tail = H.terminal_tail value in
  match H.Tail.path tail with
  | None -> value
  | Some selected ->
      let tail = H.Tail.make ~status:(H.Tail.status tail) ~placement:(H.Tail.placement tail) ~length:(H.Tail.length tail)
          ~path:(Some (relabel_path id selected)) ~provenance:(H.Tail.provenance tail) in
      H.make ~cap:(H.cap value) ~start_end:(H.start_end value) ~finish_end:(H.finish_end value)
        ~modifications:(H.modifications value) ~modification_inventory_status:(H.modification_inventory_status value)
        ~modification_inventory_provenance:(H.modification_inventory_provenance value) ~terminal_tail:tail
let relabel_features id features = List.map (fun feature ->
    match Molecule.Feature.path feature with None -> feature
    | Some selected -> Molecule.Feature.make ~id:(Molecule.Feature.id feature) ~kind:(Molecule.Feature.kind feature)
        ~path:(Some (relabel_path id selected)) ?reading_frame:(Molecule.Feature.reading_frame feature)
        ~provenance:(Molecule.Feature.provenance feature) ()) features
let selected budget sequence selected =
  R.charge budget (G.Path.length selected);
  let output = Bytes.create (G.Path.length selected) and cursor = ref 0 in
  List.iter (fun part ->
      for offset=0 to G.Span.length part-1 do
        let source = if G.Path.strand selected=G.Forward then G.Span.start part+offset else G.Span.stop part-1-offset in
        Bytes.set output !cursor sequence.[source];incr cursor
      done) (G.Path.spans selected);
  Bytes.to_string output
let reverse_path selected = path (G.Path.space_id selected) (List.rev (G.Path.spans selected))
    (if G.Path.strand selected=G.Forward then G.Reverse else G.Forward)
let output_space port length alphabet topology = G.Space.of_json (obj [
    "schema_version",str "biocompiler.molecule_coordinate_space.v0.1";"id",str (C.Product_port.space_id port);
    "alphabet",str (match alphabet with G.Dna->"DNA" | G.Rna->"RNA" | G.Protein->"protein");
    "length",Json.int length;"topology",str (if topology=G.Linear then "linear" else "circular");
    "axis",str (if alphabet=G.Protein then "N_to_C" else "5prime_to_3prime")])
let path_for selection source =
  let selected = match C.Selection.path selection with Some value -> value | None -> full_path (R.space source) in
  (try G.Path.validate_for selected (R.space source) with Diagnostic.Error _ -> raise (Problem "invalid_selection"));
  require (G.Path.length selected > 0) "invalid_selection";
  selected
let complement alphabet = function
  | 'A' -> if alphabet=G.Dna then 'T' else 'U' | 'C' -> 'G' | 'G' -> 'C' | 'T' | 'U' -> 'A'
  | _ -> raise (Problem "invalid_operation")
let regular_step budget step available remaining final_limit used =
  let module Meter=Bioc_checker.Policy_generation_meter.Make(struct let charge=R.outer_meter budget end) in
  let module List=Meter.List in
  let module String=Meter.String in
  let ( @ ) = List.append in

  R.reserve_json budget (R.step_json budget step);
  let operation = C.Transform_step.operation step in
  let selections = C.operation_selections operation in
  R.charge budget (List.length selections);
  require (List.for_all (fun selection -> R.Available.find ~charge:(R.outer_charge budget) (C.Value_ref.id (C.Selection.value selection)) available <> None) selections)
    "unavailable_input";
  let inputs = List.map (fun selection -> Option.get (R.Available.find ~charge:(R.outer_charge budget) (C.Value_ref.id (C.Selection.value selection)) available)) selections in
  require (List.for_all (fun value -> R.sequence_extent value=H.Complete) inputs) "incomplete_input";
  let paths = List.map2 path_for selections inputs in
  let first = List.hd inputs in
  let alphabet = G.Space.alphabet (R.space first) in
  require (List.for_all (fun value -> G.Space.alphabet (R.space value)=alphabet) inputs) "unsupported_alphabet";
  let specification = C.Operation.specification operation in
  let alphabet,topology,rule,recipes = match specification with
    | C.Operation.Rna_cleavage {products;_} | C.Operation.Rna_splicing {products;_}
    | C.Operation.Protein_cleavage {products;_} | C.Operation.Protein_splicing {products;_} ->
        let expected = match specification with C.Operation.Rna_cleavage _ | C.Operation.Rna_splicing _ -> G.Rna | _ -> G.Protein in
        require (alphabet=expected) "unsupported_alphabet";
        require (G.Space.topology (R.space first)=G.Linear) "unsupported_topology";
        List.iter (fun product ->
            let selected = C.Processing_product.path product in
            (try G.Path.validate_for selected (R.space first) with Diagnostic.Error _ -> raise (Problem "invalid_selection"));
            require (G.Path.length selected > 0 && G.Path.strand selected=G.Forward) "invalid_selection") products;
        List.iter (fun product ->
            let rec ordered = function left::(right::_ as tail) ->
                require (G.Span.stop left <= G.Span.start right) "invalid_processing_partition";ordered tail | _ -> () in
            ordered (G.Path.spans (C.Processing_product.path product))) products;
        let intervals = List.concat_map (fun product -> List.map (fun span -> G.Span.start span,G.Span.stop span)
            (G.Path.spans (C.Processing_product.path product))) products |> List.sort compare in
        let cursor = ref 0 and valid = ref true in
        List.iter (fun (first,last) -> if first <> !cursor || last<=first then valid:=false;cursor:=last) intervals;
        require (!valid && !cursor=G.Space.length (R.space first)) "invalid_processing_partition";
        let recipes = List.map (fun product ->
            let port = List.find (fun port -> C.Product_port.id port=C.Processing_product.port_id product) (C.Transform_step.ports step) in
            port,[C.Processing_product.path product]) products in
        alphabet,G.Linear,A.Derived_segment.Copy,recipes
    | C.Operation.Circularization {origin;_} ->
        require (alphabet=G.Rna) "unsupported_alphabet";
        require (G.Space.topology (R.space first)=G.Linear) "unsupported_topology";
        require (origin < G.Space.length (R.space first)) "invalid_selection";
        let spans = span origin (G.Space.length (R.space first)) :: (if origin=0 then [] else [span 0 origin]) in
        alphabet,G.Circular,A.Derived_segment.Copy,[List.hd (C.Transform_step.ports step),[path (G.Space.id (R.space first)) spans G.Forward]]
    | C.Operation.Transcription _ ->
        require (alphabet=G.Dna) "unsupported_alphabet";
        let selected = List.hd paths in
        require (G.Path.strand selected=G.Forward && List.length (G.Path.spans selected)=1) "unsupported_transcription_path";
        G.Rna,G.Linear,A.Derived_segment.Transcription,[List.hd (C.Transform_step.ports step),paths]
    | C.Operation.Orientation {action;_} ->
        require (alphabet=G.Dna || alphabet=G.Rna) "unsupported_alphabet";
        let rule = if action=C.Operation.Reverse_complement then A.Derived_segment.Complement else A.Derived_segment.Copy in
        let topology = if C.Selection.path (List.hd selections)=None then G.Space.topology (R.space first) else G.Linear in
        alphabet,topology,rule,[List.hd (C.Transform_step.ports step),[reverse_path (List.hd paths)]]
    | C.Operation.Slice _ ->
        let topology = if C.Selection.path (List.hd selections)=None then G.Space.topology (R.space first) else G.Linear in
        alphabet,topology,A.Derived_segment.Copy,[List.hd (C.Transform_step.ports step),paths]
    | C.Operation.Concatenate _ -> alphabet,G.Linear,A.Derived_segment.Copy,[List.hd (C.Transform_step.ports step),paths]
    | _ -> raise (Problem "invalid_operation") in
  require (List.for_all (fun (port,_) -> C.Product_port.alphabet port=alphabet) recipes) "unsupported_alphabet";
  require (List.for_all (fun (port,_) -> C.Product_port.topology port=topology) recipes) "unsupported_topology";
  let lengths = List.map (fun (_,paths) -> List.fold_left (fun count path -> count+G.Path.length path) 0 paths) recipes in
  let total = List.fold_left (+) 0 lengths in
  require (List.for_all (fun length -> length <= final_limit) lengths && total<=remaining) "residue_budget";
  used := total;
  try List.map2 (fun (port,paths) length ->
      let cursor = ref 0 in
      let chunks,segments = List.split (List.map2 (fun (selection,value) path ->
          let chunk = selected budget (R.sequence value) path in
          R.charge budget (String.length chunk);
          let chunk = match rule with A.Derived_segment.Complement -> String.map (complement alphabet) chunk
            | A.Derived_segment.Transcription -> String.map (fun value -> if value='T' then 'U' else value) chunk
            | _ -> chunk in
          let destination = span !cursor (!cursor+String.length chunk) in
          cursor := !cursor+String.length chunk;
          chunk,A.Derived_segment.make ~destination ~source_id:(C.Value_ref.id (C.Selection.value selection)) ~source_path:path ~rule)
          (List.combine selections inputs) paths) in
      R.reserve_json budget (R.port_json budget port);
      R.reserve_json budget (R.chemistry_json budget (R.chemistry first));
      let frame = output_space port length alphabet topology in
      let transition = C.Product_port.chemistry_transition port in
      let chemistry = match T.Chemistry.mode transition with
        | T.Chemistry.Exact_inheritance -> relabel_chemistry (C.Product_port.space_id port) (R.chemistry first)
        | T.Chemistry.Explicit_output -> Option.get (T.Chemistry.output transition) in
      let transition = C.Product_port.feature_transition port in
      let features = List.concat_map T.Feature_disposition.outputs (T.Feature.dispositions transition) @ T.Feature.added transition in
      R.charge budget (List.length features + List.length segments + length);
      let value=A.Value.make ~id:(C.Product_port.id port) ~space:frame ~sequence:(String.concat "" chunks) ~chemistry ~features ~segments
        ~step_id:(C.Transform_step.id step) ~sequence_extent:H.Complete ~consumed:[] in
      R.reserve_output budget (R.value_json budget value);value) recipes lengths
  with Diagnostic.Error diagnostic as error ->
    if diagnostic.code="construction_producer_limit" then raise error else raise (Problem "invalid_operation")

type recipe = {
  sources:C.Root_source.t list; steps:C.Transform_step.t list;
  output_members:C.Output_member.t list; complex_members:C.Complex_member.t list;
  requirements:C.Member_requirement.t list; amounts:C.Amount_declaration.t list;
}
let construct_recipe budget (limits:Limits.t) (recipe:recipe) ~authority_json
    ~make_bundle ~bundle_to_json ~subject_complete ~validate_bundle ~make_candidate =
  let module Meter=Bioc_checker.Policy_generation_meter.Make(struct let charge=R.outer_meter budget end) in
  let module List=Meter.List in
  let module String=Meter.String in
  let ( @ ) = List.append in
  let module Names=Meter.Names in

  let available = ref (R.Available.of_bindings ~charge:(R.outer_charge budget) (List.map (fun source -> C.Root_source.id source,R.Root (C.Root_source.molecule source))
      recipe.sources)) in
  let values = ref [] and diagnostics = ref [] and missing = ref [] and work = ref 0 in
  let add value = diagnostics := value :: !diagnostics in
  List.iter (fun step ->
      R.charge budget 1;
      let record code = add ("step:" ^ C.Transform_step.id step ^ ":" ^ code) in
      let remaining = limits.produced_residues - !work in
      match C.Operation.specification (C.Transform_step.operation step) with
      | C.Operation.Base_editing _ | C.Operation.Translation _ | C.Operation.Multi_orf_translation _
      | C.Operation.Conditional_translation _ | C.Operation.Ribosomal_skipping _ ->
          let result = R.construct_step ~budget ~step ~available:!available ~remaining_residues:remaining () in
          work := !work+result.used_residues;
          (match result.diagnostic with Some code -> record code | None ->
              values := List.rev_append result.values !values;available := R.Available.add_products ~charge:(R.outer_charge budget) result.values !available)
      | _ ->
          let used = ref 0 in
          (try
             let staged = regular_step budget step !available remaining limits.final_residues used in
             work := !work + !used;values := List.rev_append staged !values;
             available := R.Available.add_products ~charge:(R.outer_charge budget) staged !available
           with Problem code -> work := !work + !used;record code)) recipe.steps;
  let final_size = List.fold_left (fun count member ->
      match R.Available.find ~charge:(R.outer_charge budget) (C.Value_ref.id (C.Output_member.value member)) !available with
      | None -> count | Some value -> count+G.Space.length (R.space value)) 0 recipe.output_members in
  let finish bundle missing amounts =
    R.reserve_json budget (authority_json ());
    List.iter (fun value -> R.reserve_json budget (R.value_json budget value)) !values;
    Option.iter (fun value -> R.reserve_json budget (bundle_to_json value);R.reserve_output budget (bundle_to_json value)) bundle;
    List.iter (fun value -> R.reserve_output budget (R.amount_json budget value)) amounts;
    make_candidate ~values:(List.rev !values)
      ~bundle ~missing_members:(List.sort_uniq String.compare missing) ~diagnostics:(List.sort_uniq String.compare !diagnostics)
      ~experimental_amounts:amounts in
  if final_size > limits.final_residues then (
    add "bundle:residue_budget";
    finish None (List.map C.Output_member.id recipe.output_members @ List.map C.Complex_member.id recipe.complex_members) [])
  else (
    let molecules = List.filter_map (fun member ->
        let id = C.Output_member.id member in
        let failed code = add ("member:" ^ id ^ ":" ^ code);missing := id :: !missing;None in
        match R.Available.find ~charge:(R.outer_charge budget) (C.Value_ref.id (C.Output_member.value member)) !available with
        | None -> failed "unavailable_value"
        | Some value ->
            R.charge budget (G.Space.length (R.space value));
            R.reserve_json budget (R.chemistry_json budget (R.chemistry value));
            List.iter (fun feature -> R.reserve_json budget (R.feature_json budget feature)) (R.features value);
            try
              require (C.Output_member.sequence_extent member=R.sequence_extent value) "invalid_molecule";
              let space = G.Space.of_json (set "id" (str (C.Output_member.space_id member)) (G.Space.to_json (R.space value))) in
              let origin = Molecule.Assembly_origin.make ~id:(id ^ ".origin") ~destination:(full_path space)
                  ~source_space:(R.space value) ~source_path:(full_path (R.space value)) ~provenance:(C.Output_member.provenance member) in
              let molecule = Molecule.make ~id ~form:(C.Output_member.form member) ~space ~sequence:(R.sequence value)
                  ~sequence_extent:(C.Output_member.sequence_extent member) ~coding_status:(C.Output_member.coding_status member)
                  ~assembly:[origin] ~features:(relabel_features (C.Output_member.space_id member) (R.features value))
                  ~chemistry:(relabel_chemistry (C.Output_member.space_id member) (R.chemistry value)) ~provenance:(C.Output_member.provenance member) in
              R.reserve_staged budget (R.molecule_json budget molecule);
              if not (Molecule.declared_nominal_complete molecule) then add ("member:" ^ id ^ ":nominal_incomplete");
              Some molecule
            with Problem _ | Diagnostic.Error _ -> failed "invalid_molecule") recipe.output_members in
    let by_id = List.fold_left (fun map molecule -> Names.add (Molecule.id molecule) molecule map) Names.empty molecules in
    let complexes = List.filter_map (fun plan ->
        let id = C.Complex_member.id plan in
        let failed code = add ("member:" ^ id ^ ":" ^ code);missing := id :: !missing;None in
        if List.exists (fun item -> not (Names.mem (C.Complex_constituent.member_id item) by_id)) (C.Complex_member.constituents plan)
        then failed "unavailable_value"
        else try
          let constituents = List.map (fun item ->
              let molecule = Names.find (C.Complex_constituent.member_id item) by_id in
              R.reserve_json budget (R.molecule_json budget molecule);
              Molecule.Constituent.make ~molecule_id:(Molecule.id molecule) ~molecule_fingerprint:(Molecule.fingerprint molecule)
                ~stoichiometry:(C.Complex_constituent.stoichiometry item) ~provenance:(C.Complex_constituent.provenance item)) (C.Complex_member.constituents plan) in
          let value=Molecule.Complex.make ~id ~kind:(C.Complex_member.kind plan) ~constituents ~provenance:(C.Complex_member.provenance plan) in
          R.reserve_staged budget (R.complex_json budget value);Some value
        with Diagnostic.Error diagnostic as error -> if diagnostic.code="construction_producer_limit" then raise error else failed "invalid_molecule")
        recipe.complex_members in
    if !missing<>[] then finish None !missing [] else
    let bundle,amounts = try
      let subjects = List.fold_left (fun map item -> Names.add (Molecule.Complex.id item) (Molecule.Complex.fingerprint item) map)
          (Names.map (fun value -> R.reserve_json budget (R.molecule_json budget value);Molecule.fingerprint value) by_id) complexes in
      let roles = List.concat_map (fun requirement -> match C.Member_requirement.member_id requirement with None -> []
          | Some id -> List.map (fun role ->
              R.charge budget 1;
              Molecule.Role.make ~id:(C.Role.id role) ~subject_id:id ~subject_fingerprint:(Names.find id subjects)
                ~role:(C.Role.role role) ~purpose:(C.Role.purpose role) ~compartment:(C.Role.compartment role)) (C.Member_requirement.roles requirement))
          recipe.requirements in
      let bundle = make_bundle ~molecules ~complexes ~role_instances:roles ~form_mappings:[] in
      List.iter (fun item -> if not (subject_complete bundle (Molecule.Complex.id item)) then
          add ("member:" ^ Molecule.Complex.id item ^ ":nominal_incomplete")) complexes;
      let amounts = List.map (fun item ->
          R.charge budget 1;
          let quantity = match C.Amount_declaration.quantity item with
            | C.Amount_declaration.Unknown -> Molecule_set.Amount.Unknown
            | C.Amount_declaration.Integer value -> Molecule_set.Amount.Integer value
            | C.Amount_declaration.Real value -> Molecule_set.Amount.Real value in
          Molecule_set.Amount.make ~id:(C.Amount_declaration.id item) ~subject_id:(C.Amount_declaration.subject_id item)
            ~subject_fingerprint:(Names.find (C.Amount_declaration.subject_id item) subjects) ~preparation_id:(C.Amount_declaration.preparation_id item)
            ~role_instance_ids:(C.Amount_declaration.role_instance_ids item) ~quantity ~unit:(C.Amount_declaration.unit item)
            ~provenance:(C.Amount_declaration.provenance item)) recipe.amounts in
      validate_bundle bundle amounts;
      Some bundle,amounts
    with Diagnostic.Error diagnostic as error ->
      if diagnostic.code="construction_producer_limit" then raise error;
      add "bundle:invalid_inventory";None,[] in
    finish bundle [] amounts)

let construct ?parent ?charge ?(limits=Limits.make ()) original = R.protect (fun () ->
  let budget = R.make_budget ?parent ?charge ~maximum:limits.work () in
  R.charge budget 1;
  R.reserve_json budget (C.Request.to_json original);
  let request = C.Request.of_json (C.Request.to_json original) in
  let recipe = {sources=C.Request.sources request;steps=C.Request.steps request;
      output_members=C.Request.output_members request;complex_members=C.Request.complex_members request;
      requirements=C.Request.requirements request;amounts=C.Request.amounts request} in
  construct_recipe budget limits recipe ~authority_json:(fun () -> C.Request.to_json request)
    ~make_bundle:(Molecule_set.make ~id:(C.Request.id request ^ ".molecules") ~request:(C.Request.circuit request))
    ~bundle_to_json:Molecule_set.to_json ~subject_complete:Molecule_set.subject_complete
    ~validate_bundle:(fun bundle amounts -> ignore (Molecule_set.Artifact.make ~bundle ~experimental_amounts:amounts ~run_metadata:[]))
    ~make_candidate:(A.make ~request_fingerprint:(C.Request.fingerprint request)))

let construct_template ?parent ?charge ?(limits=Limits.make ()) ~member_order original = R.protect (fun () ->
  let module P = Payload_template in
  let module K = Construction_content in
  let budget = R.make_budget ?parent ?charge ~maximum:limits.work () in
  R.charge budget 1;
  let module Meter=Bioc_checker.Policy_generation_meter.Make(struct let charge=R.outer_meter budget end) in
  let module List=Meter.List in
  let module Canonical=Meter.Canonical in
  R.Serialization.template (R.outer_charge budget) original;
  Meter.serialization (P.to_json original);
  List.iter (fun member -> R.outer_charge budget (String.length member)) member_order;
  let authority = K.authority_json ~template:original ~member_order in
  R.reserve_json budget authority;
  let template = P.of_json (P.to_json original) in
  let recipe = {sources=P.sources template;steps=P.steps template;
      output_members=P.output_members template;complex_members=P.complex_members template;
      requirements=P.requirements template;amounts=P.amounts template} in
  let make_bundle ~molecules ~complexes ~role_instances ~form_mappings =
    List.iter (R.Serialization.molecule (R.outer_charge budget)) molecules;
    List.iter (R.Serialization.complex (R.outer_charge budget)) complexes;
    List.iter (R.Serialization.role (R.outer_charge budget)) role_instances;
    List.iter (R.Serialization.mapping (R.outer_charge budget)) form_mappings;
    let by_id = List.map (fun molecule -> Molecule.id molecule,molecule) molecules in
    let molecules = List.map (fun id -> List.assoc id by_id) member_order in
    K.Inventory.make ~id:(P.id template ^ ".molecules") ~molecules ~complexes ~role_instances ~form_mappings in
  construct_recipe budget limits recipe ~authority_json:(fun () -> authority)
    ~make_bundle ~bundle_to_json:(fun inventory ->
      List.iter (R.Serialization.molecule (R.outer_charge budget)) (K.Inventory.molecules inventory);
      List.iter (R.Serialization.complex (R.outer_charge budget)) (K.Inventory.complexes inventory);
      List.iter (R.Serialization.role (R.outer_charge budget)) (K.Inventory.role_instances inventory);
      List.iter (R.Serialization.mapping (R.outer_charge budget)) (K.Inventory.form_mappings inventory);
      K.Inventory.to_json inventory)
    ~subject_complete:K.Inventory.subject_complete
    ~validate_bundle:(fun inventory amounts ->
      List.iter (R.Serialization.amount (R.outer_charge budget)) amounts;
      K.Inventory.validate_amounts inventory amounts)
    ~make_candidate:(fun ~values ~bundle ~missing_members ~diagnostics ~experimental_amounts ->
      Option.iter (fun inventory ->
        List.iter (R.Serialization.molecule (R.outer_charge budget)) (K.Inventory.molecules inventory);
        List.iter (R.Serialization.complex (R.outer_charge budget)) (K.Inventory.complexes inventory);
        List.iter (R.Serialization.role (R.outer_charge budget)) (K.Inventory.role_instances inventory);
        List.iter (R.Serialization.mapping (R.outer_charge budget)) (K.Inventory.form_mappings inventory)) bundle;
      List.iter (R.Serialization.value (R.outer_charge budget)) values;
      List.iter (R.Serialization.amount (R.outer_charge budget)) experimental_amounts;
      List.iter (fun value -> R.outer_charge budget (String.length value)) (missing_members @ diagnostics);
      K.make ~authority_fingerprint:(Canonical.fingerprint authority) ~member_order ~values ~inventory:bundle
        ~missing_members ~diagnostics ~experimental_amounts))

let content_json ?charge content =
  match charge with None -> Construction_content.to_json content | Some charge ->
  let module K=Construction_content in
  let module Meter=Bioc_checker.Policy_generation_meter.Make(struct let charge=charge end) in
  let module List=Meter.List in
  charge 1;
  List.iter (fun value -> charge (String.length value)) (K.member_order content);
  List.iter (R.Serialization.value charge) (K.values content);
  Option.iter (fun inventory ->
    List.iter (R.Serialization.molecule charge) (K.Inventory.molecules inventory);
    List.iter (R.Serialization.complex charge) (K.Inventory.complexes inventory);
    List.iter (R.Serialization.role charge) (K.Inventory.role_instances inventory);
    List.iter (R.Serialization.mapping charge) (K.Inventory.form_mappings inventory)) (K.inventory content);
  List.iter (fun value -> charge (String.length value)) (K.missing_members content);
  List.iter (fun value -> charge (String.length value)) (K.diagnostics content);
  List.iter (R.Serialization.amount charge) (K.experimental_amounts content);
  let raw=K.to_json content in Meter.serialization raw; raw

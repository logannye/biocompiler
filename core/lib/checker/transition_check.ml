open Bioc_wire
open Bioc_domain
module G = Molecule_coordinates
module C = Molecule_chemistry
module T = Molecular_transition
module D = Construction_artifact.Derived_segment
module F = Molecule.Feature
module Iset = Set.Make (Int)
module Imap = Map.Make (Int)
module Sset = Set.Make (String)
module Pset = Set.Make (struct type t = string * string let compare = Stdlib.compare end)
module Input = struct
  type t = { space:G.Space.t; sequence:string; chemistry:C.t; features:F.t list; sequence_extent:C.sequence_extent }
  let of_molecule value = {space=Molecule.space value; sequence=Molecule.sequence value; chemistry=Molecule.chemistry value;
    features=Molecule.features value; sequence_extent=Molecule.sequence_extent value}
  let of_value value = {space=Construction_artifact.Value.space value; sequence=Construction_artifact.Value.sequence value;
    chemistry=Construction_artifact.Value.chemistry value; features=Construction_artifact.Value.features value;
    sequence_extent=Construction_artifact.Value.sequence_extent value}
  let space value = value.space
  let sequence value = value.sequence
  let chemistry value = value.chemistry
  let features value = value.features
  let sequence_extent value = value.sequence_extent
end
let resource_profile = "biocompiler.transition_check.resources.v1"
let default_max_work = 10_000_000
let max_projected_residues = 100_000
let max_derivation_segments = 4096
(* This native execution budget is separate from the preserved legacy projection
   limits. Exhaustion returns no partial semantic resolution. *)
type budget = { mutable remaining:int }
let make_budget ?(max_work=default_max_work) () =
  Diagnostic.require (max_work >= 0) "transition_resource_limit" "Transition work budget must be nonnegative.";
  {remaining=max_work}
let charge budget count =
  Diagnostic.require (count >= 0 && count <= budget.remaining) "transition_resource_limit" "Transition correspondence work budget exhausted.";
  budget.remaining <- budget.remaining - count
exception Invalid of string
exception Projection_limit of string
let require condition message = if not condition then raise (Invalid message)
let bounded_count maximum values =
  let rec count total = function [] -> Some total | _ :: tail -> if total=maximum then None else count (total+1) tail in
  count 0 values
let string_count budget value =
  charge budget (String.length value);
  Json.validate_utf8 value;
  String.fold_left (fun total char -> if Char.code char land 0xc0 <> 0x80 then total+1 else total) 0 value
let path_validate budget path space =
  charge budget (1 + List.length (G.Path.spans path));
  require (G.Space_id.equal (G.Path.space_id path) (G.Space.id space)) "Path names a different coordinate space.";
  require (List.for_all (fun span -> G.Span.stop span <= G.Space.length space) (G.Path.spans path)) "Coordinate path extends beyond its declared coordinate space.";
  require (G.Space.alphabet space <> G.Protein || G.Path.strand path=G.Forward) "Protein coordinate paths must retain N-to-C traversal with '+' strand."
let positions budget path space =
  path_validate budget path space;
  require (G.Path.length path <= max_projected_residues) "Coordinate path exceeds the position-view limit.";
  charge budget (G.Path.length path);
  G.Path.positions ~limit:max_projected_residues path space
(* Compatibility predicates retain the legacy failure text bound into complete
   construction assessments. They do not call a producer or normalize authority. *)
let chemistry_validate budget chemistry space sequence extent =
  let alphabet=G.Space.alphabet space and topology=G.Space.topology space in
  charge budget (String.length sequence);
  require (String.length sequence=G.Space.length space && Molecular_record.valid_sequence alphabet sequence)
    "Sequence must match the coordinate space and its canonical alphabet.";
  let cap=C.cap chemistry and start=C.start_end chemistry and finish=C.finish_end chemistry and tail=C.terminal_tail chemistry in
  if topology=G.Circular then require (List.for_all (fun claim -> C.Claim.status claim=C.Inapplicable) [cap;start;finish] && C.Tail.status tail=C.Inapplicable)
      "Circular molecules have inapplicable caps, free ends and terminal tails."
  else require (List.for_all (fun claim -> List.mem (C.Claim.status claim) [C.Declared;C.Unknown]) [start;finish])
      "Linear terminal groups must be declared or explicitly unknown.";
  if alphabet<>G.Rna then require (C.Claim.status cap=C.Inapplicable && C.Tail.status tail=C.Inapplicable)
      "DNA/protein caps and RNA-style tails must be inapplicable."
  else if topology=G.Linear then (
    require (List.mem (C.Claim.status cap) [C.Declared;C.Unknown;C.Absent]) "Linear RNA cap must be declared, absent or unknown.";
    require (List.mem (C.Tail.status tail) [C.Declared;C.Unknown]) "Linear RNA tail must be declared or explicitly unknown.");
  if alphabet=G.Protein then require (C.modifications chemistry=[]) "Protein records cannot carry nucleotide base modifications."
  else require (C.modification_inventory_status chemistry<>C.Inapplicable) "Nucleotide modification inventories must be declared or unknown.";
  let used=ref Iset.empty and all_matching=Hashtbl.create 5 and explicit=Hashtbl.create 5 in
  List.iter (fun modification ->
    charge budget 1;
    let base=C.Modification.canonical_base modification in
    require (String.contains (Molecular_record.alphabet_symbols alphabet) base) "Modification parent base differs from molecule alphabet.";
    match C.Modification.scope modification with
    | C.Modification.Positions ->
      let sites=C.Modification.positions modification in charge budget (List.length sites);
      require (List.for_all (fun site -> site<String.length sequence) sites) "Modification position is outside the represented sequence.";
      require (List.for_all (fun site -> sequence.[site]=base) sites) "Modification position differs from its declared canonical parent base.";
      require (not (Hashtbl.mem all_matching base)) "Modification declarations overlap an all-matching policy.";
      require (List.for_all (fun site -> not (Iset.mem site !used)) sites) "Modification declarations overlap on represented bases.";
      List.iter (fun site -> used:=Iset.add site !used) sites; Hashtbl.replace explicit base ()
    | C.Modification.All_matching_bases ->
      require (not (Hashtbl.mem all_matching base || Hashtbl.mem explicit base)) "Modification declarations overlap an all-matching policy.";
      Hashtbl.replace all_matching base ()) (C.modifications chemistry);
  if C.Tail.status tail=C.Declared && C.Tail.placement tail=Some C.Tail.Represented_terminal then (
    let path=Option.get (C.Tail.path tail) in path_validate budget path space;
    let exact=match C.Tail_length.mode (Option.get (C.Tail.length tail)) with C.Tail_length.Exact value -> value | _ -> assert false in
    require (G.Path.strand path=G.Forward && List.length (G.Path.spans path)=1 && G.Span.stop (List.hd (G.Path.spans path))=String.length sequence && G.Path.length path=exact)
      "Exact tails require one forward terminal interval with the declared length.";
    let span=List.hd (G.Path.spans path) in charge budget (G.Span.length span);
    for site=G.Span.start span to G.Span.stop span-1 do require (sequence.[site]='A') "An exact poly(A) tail requires literal canonical adenines." done);
  let appended=C.Tail.status tail=C.Declared && C.Tail.placement tail=Some C.Tail.Appended_terminal in
  if appended then require (alphabet=G.Rna && topology=G.Linear && extent=C.Exact_core) "Uncertain appended tails require an exact linear RNA core.";
  if extent=C.Exact_core then require appended "An exact core must explicitly declare its uncertain appended tail."
let facets=["cap";"start_end";"finish_end";"terminal_tail";"modification_inventory"]
let components chemistry = Sset.of_list (facets @ List.map (fun modification -> "modification:" ^ C.Modification.id modification) (C.modifications chemistry))
let validate_derivation budget inputs output_sequence output_space derivation =
  require (match bounded_count 64 inputs with Some count -> count>0 | None -> false) "Expected bounded participating source values.";
  let ids=List.map fst inputs in
  List.iter (fun id -> charge budget (String.length id)) ids;
  require (List.length ids=List.length (List.sort_uniq String.compare ids)) "Expected bounded participating source values.";
  require (string_count budget output_sequence=G.Space.length output_space) "Output spelling and frame disagree.";
  require (match bounded_count max_derivation_segments derivation with Some count -> count>0 | None -> false) "Invalid derivation segment inventory.";
  let cursor=ref 0 and selected=ref Sset.empty and blocks=ref 0 in
  List.iter (fun segment ->
    charge budget 1;
    let destination=D.destination segment and id=D.source_id segment and path=D.source_path segment in
    require (G.Span.start destination= !cursor && G.Span.length destination>0) "Derivation must partition output residues exactly once.";
    require (List.mem_assoc id inputs) "Derivation names an unknown input value.";
    let source=List.assoc id inputs in
    if not (Sset.mem id !selected) then (
      chemistry_validate budget (Input.chemistry source) (Input.space source) (Input.sequence source) (Input.sequence_extent source);
      List.iter (fun feature -> Option.iter (fun path -> path_validate budget path (Input.space source)) (F.path feature)) (Input.features source));
    path_validate budget path (Input.space source);
    blocks:= !blocks+List.length (G.Path.spans path);
    require (!blocks<=max_derivation_segments) "Derivation path-block limit exceeded.";
    let source_alphabet=G.Space.alphabet (Input.space source) and output_alphabet=G.Space.alphabet output_space in
    (match D.rule segment with
    | D.Transcription -> require (source_alphabet=G.Dna && output_alphabet=G.Rna) "Transcription derivation must explicitly bind DNA to RNA."
    | D.Translation_codon ->
      require (source_alphabet=G.Rna && output_alphabet=G.Protein) "Codon translation derivation must explicitly bind RNA to protein.";
      require (G.Path.strand path=G.Forward && List.length (G.Path.spans path)=1) "Codon translation requires contiguous forward source traversal."
    | D.Copy | D.Complement | D.Rna_editing ->
      require (source_alphabet=output_alphabet) "Derivation cannot silently change the alphabet.";
      require (D.rule segment<>D.Rna_editing || source_alphabet=G.Rna) "RNA editing derivation requires the RNA alphabet.";
      require (D.rule segment<>D.Complement || source_alphabet=G.Dna || source_alphabet=G.Rna) "Protein complementation is not a symbol operation.");
    cursor:=G.Span.stop destination; selected:=Sset.add id !selected) derivation;
  require (!cursor=G.Space.length output_space) "Derivation does not cover the complete output.";
  require (Sset.equal !selected (Sset.of_list ids)) "Transition inputs must be exactly the participating derivation sources."
let identity_source budget inputs output_sequence output_space derivation =
  require (List.length inputs=1) "Exact chemistry inheritance requires exactly one source.";
  let source_id,source=List.hd inputs in
  require (Input.sequence_extent source=C.Complete) "Exact inheritance requires a complete source spelling.";
  require (Input.sequence source=output_sequence && G.Space.alphabet (Input.space source)=G.Space.alphabet output_space && G.Space.topology (Input.space source)=G.Space.topology output_space)
    "Exact chemistry inheritance requires unchanged spelling, alphabet and topology.";
  let cursor=ref 0 in
  List.iter (fun segment ->
    charge budget 1;
    require (D.source_id segment=source_id && D.rule segment=D.Copy && G.Path.strand (D.source_path segment)=G.Forward) "Exact inheritance requires unchanged forward traversal.";
    List.iter (fun span -> charge budget 1; require (G.Span.start span= !cursor) "Exact inheritance cannot cut, duplicate or reorder source residues."; cursor:=G.Span.stop span) (G.Path.spans (D.source_path segment))) derivation;
  require (!cursor=G.Space.length (Input.space source)) "Exact inheritance must retain every original residue.";
  let chemistry=Input.chemistry source in
  match C.Tail.path (C.terminal_tail chemistry) with
  | None -> chemistry
  | Some path ->
    let renamed=G.Path.of_json (Json.Object (("space_id",Json.String (G.Space_id.to_string (G.Space.id output_space))) :: List.remove_assoc "space_id" (Json.object_fields (G.Path.to_json path)))) in
    let tail=C.terminal_tail chemistry in
    let tail=C.Tail.make ~status:(C.Tail.status tail) ~placement:(C.Tail.placement tail) ~length:(C.Tail.length tail) ~path:(Some renamed) ~provenance:(C.Tail.provenance tail) in
    C.make ~cap:(C.cap chemistry) ~start_end:(C.start_end chemistry) ~finish_end:(C.finish_end chemistry) ~modifications:(C.modifications chemistry)
      ~modification_inventory_status:(C.modification_inventory_status chemistry) ~modification_inventory_provenance:(C.modification_inventory_provenance chemistry) ~terminal_tail:tail
let selected_blocks budget source_id derivation visit =
  List.iter (fun segment ->
    charge budget 1;
    if D.source_id segment=source_id then (
      require (D.rule segment<>D.Translation_codon) "Codon translation cannot use one-to-one residue projection.";
      let cursor=ref (G.Span.start (D.destination segment)) in
      List.iter (fun span -> charge budget 1; visit span (G.Path.strand (D.source_path segment)) !cursor (D.rule segment); cursor:= !cursor+G.Span.length span) (G.Path.spans (D.source_path segment)))) derivation
let destination span strand cursor site = cursor + (if strand=G.Forward then site-G.Span.start span else G.Span.stop span-1-site)
let bisect values needle =
  let low=ref 0 and high=ref (Array.length values) in
  while !low< !high do let middle= !low+(!high- !low)/2 in if values.(middle)<needle then low:=middle+1 else high:=middle done; !low
let project_positions budget source_id sites derivation =
  require (List.length sites<=max_projected_residues) "Projection input residue limit exceeded.";
  charge budget (List.length sites);
  let ordered=Array.of_list (List.sort Int.compare sites) and result=ref Imap.empty and count=ref 0 in
  selected_blocks budget source_id derivation (fun span strand cursor _ ->
    let first=bisect ordered (G.Span.start span) and last=bisect ordered (G.Span.stop span) in
    if !count+last-first>max_projected_residues then raise (Projection_limit "Projected residue limit exceeded.");
    charge budget (last-first); count:= !count+last-first;
    for index=first to last-1 do let site=ordered.(index) in result:=Imap.add (destination span strand cursor site) site !result done);
  !result
let modification_coverage budget modification sequence = match C.Modification.scope modification with
  | C.Modification.Positions -> charge budget (List.length (C.Modification.positions modification)); Iset.of_list (C.Modification.positions modification)
  | C.Modification.All_matching_bases ->
    charge budget (String.length sequence);
    let result=ref Iset.empty and count=ref 0 in
    String.iteri (fun site base -> if base=C.Modification.canonical_base modification then (
      if !count=max_projected_residues then raise (Projection_limit "Modification coverage limit exceeded."); incr count; result:=Iset.add site !result)) sequence;
    !result
let project_modification budget source_id modification inputs derivation =
  let sequence=Input.sequence (List.assoc source_id inputs) and result=ref Iset.empty and count=ref 0 in
  let explicit=Array.of_list (C.Modification.positions modification) in
  selected_blocks budget source_id derivation (fun span strand cursor rule ->
    require (rule=D.Copy) "Mapped modification inheritance cannot infer chemistry through symbol rewriting.";
    let add site =
      if !count=max_projected_residues then raise (Projection_limit "Mapped modification coverage limit exceeded.");
      incr count; result:=Iset.add (destination span strand cursor site) !result in
    match C.Modification.scope modification with
    | C.Modification.Positions ->
      let first=bisect explicit (G.Span.start span) and last=bisect explicit (G.Span.stop span) in charge budget (last-first);
      for index=first to last-1 do add explicit.(index) done
    | C.Modification.All_matching_bases ->
      charge budget (G.Span.length span);
      for site=G.Span.start span to G.Span.stop span-1 do if sequence.[site]=C.Modification.canonical_base modification then add site done);
  !result
let endpoint_mapped budget source_id facet inputs output_space derivation =
  let source=List.assoc source_id inputs in
  let start=facet="cap" || facet="start_end" in
  if not start && Input.sequence_extent source<>C.Complete then false else
    let site=if start then 0 else G.Space.length (Input.space source)-1 in
    let expected=if start then 0 else G.Space.length output_space-1 in
    let matches=project_positions budget source_id [site] derivation in
    let retained=ref true in
    if Imap.equal Int.equal matches (Imap.singleton expected site) then (
      selected_blocks budget source_id derivation (fun span strand _ rule -> if G.Span.start span<=site && site<G.Span.stop span then retained:= !retained && strand=G.Forward && rule=D.Copy);
      !retained) else false
type messages = { mutable reversed:string list; mutable bytes:int }
let messages () = {reversed=[];bytes=0}
let emit messages text =
  Diagnostic.require (String.length text<=32768 && messages.bytes<=1_000_000-String.length text)
    "transition_resource_limit" "Transition diagnostic output budget exhausted.";
  messages.bytes<-messages.bytes+String.length text; messages.reversed<-text::messages.reversed
let unique_messages messages =
  let seen=Hashtbl.create 16 in
  List.rev messages.reversed |> List.filter (fun text -> if Hashtbl.mem seen text then false else (Hashtbl.add seen text ();true))
let same_option encode left right = match left,right with
  | None,None -> true | Some left,Some right -> Json.equal (encode left) (encode right) | _ -> false
let chemical_equal left right =
  C.Modification.canonical_base left=C.Modification.canonical_base right &&
  Json.equal (C.Chemical_identity.to_json (C.Modification.identity left)) (C.Chemical_identity.to_json (C.Modification.identity right))
let map_keys map = Imap.fold (fun key _ set -> Iset.add key set) map Iset.empty
let explicit_chemistry budget transition inputs output_sequence output_space derivation diagnostics unsupported =
  let output=Option.get (T.Chemistry.output transition) in
  let expected=List.fold_left (fun expected (id,source) -> Sset.fold (fun component expected -> Pset.add (id,component) expected) (components (Input.chemistry source)) expected) Pset.empty inputs in
  let dispositions=T.Chemistry.dispositions transition in
  let supplied=Pset.of_list (List.map (fun item -> T.Chemistry_disposition.source_id item,T.Component.to_string (T.Chemistry_disposition.component item)) dispositions) in
  if not (Pset.equal supplied expected) then (
    emit diagnostics "chemistry_disposition_inventory: every input chemistry facet and modification requires exactly one disposition"; output)
  else (
    let destinations=components output in
    let targeted=Sset.of_list (List.concat_map (fun item -> List.map T.Component.to_string (T.Chemistry_disposition.destination_components item)) dispositions) in
    if not (Sset.equal targeted destinations) then emit diagnostics "chemistry_destination_inventory: every output chemistry component requires an explicit disposition";
    let output_mods=List.map (fun modification -> "modification:" ^ C.Modification.id modification,modification) (C.modifications output) in
    let mapped=Hashtbl.create 16 and mapped_order=ref [] in
    List.iter (fun item ->
      charge budget 1;
      let source_id=T.Chemistry_disposition.source_id item and component=T.Component.to_string (T.Chemistry_disposition.component item) in
      let targets=List.map T.Component.to_string (T.Chemistry_disposition.destination_components item) in
      charge budget (List.length targets);
      let label=source_id ^ "/" ^ component in
      if not (List.for_all (fun component -> Sset.mem component destinations) targets) then emit diagnostics ("chemistry_destination_missing: " ^ label)
      else match T.Chemistry_disposition.decision item with
      | T.Chemistry_disposition.Unknown -> emit unsupported ("unknown_chemistry_disposition: " ^ label)
      | T.Chemistry_disposition.Not_carried | T.Chemistry_disposition.Declared_replacement -> ()
      | T.Chemistry_disposition.Mapped_copy ->
        let source=List.assoc source_id inputs in
        try
          charge budget (List.length derivation);
          require (List.for_all (fun segment -> D.source_id segment<>source_id || (D.rule segment<>D.Rna_editing && D.rule segment<>D.Translation_codon)) derivation)
            "Mapped chemistry cannot infer retention through RNA editing or codon translation.";
          (match T.Chemistry_disposition.component item with
          | T.Component.Modification modification_id ->
            require (List.for_all (fun component -> List.mem_assoc component output_mods) targets) "A mapped base modification must name output modification occurrences.";
            let original=List.find (fun modification -> C.Modification.id modification=modification_id) (C.modifications (Input.chemistry source)) in
            let projected=project_modification budget source_id original inputs derivation and target_coverage=ref Iset.empty in
            List.iter (fun component ->
              charge budget 1;
              let target=List.assoc component output_mods in
              require (chemical_equal target original) "Mapped modification identity or canonical parent changed.";
              let covered=modification_coverage budget target output_sequence in
              charge budget (Iset.cardinal covered+Iset.cardinal projected);
              target_coverage:=Iset.union covered !target_coverage;
              if not (Hashtbl.mem mapped component) then (Hashtbl.add mapped component Iset.empty; mapped_order:=component:: !mapped_order);
              Hashtbl.replace mapped component (Iset.union (Hashtbl.find mapped component) (Iset.inter projected covered))) targets;
            require (Iset.subset projected !target_coverage) "Mapped modification loses selected chemical sites."
          | T.Component.Modification_inventory ->
            require (targets=["modification_inventory"]) "Inventory inheritance must retain the inventory facet.";
            require (C.modification_inventory_status (Input.chemistry source)=C.modification_inventory_status output) "Mapped modification inventory cannot resolve unknown chemistry."
          | T.Component.Terminal_tail ->
            require (targets=["terminal_tail"]) "Tail inheritance must retain the tail facet.";
            let original=C.terminal_tail (Input.chemistry source) and target=C.terminal_tail output in
            require (C.Tail.status original=C.Tail.status target && C.Tail.placement original=C.Tail.placement target &&
              same_option C.Tail_length.to_json (C.Tail.length original) (C.Tail.length target)) "Mapped tail declaration changed.";
            (match C.Tail.path original with
            | None -> ()
            | Some path ->
              if G.Path.length path>max_projected_residues then raise (Projection_limit "Mapped tail residue limit exceeded.");
              let original_positions=positions budget path (Input.space source) in
              let projected=project_positions budget source_id original_positions derivation in
              let target_positions=positions budget (Option.get (C.Tail.path target)) output_space in
              require (Imap.cardinal projected=List.length original_positions && Iset.equal (map_keys projected) (Iset.of_list target_positions)) "Mapped tail has incomplete or changed residue coverage.";
              require (List.map (fun site -> Imap.find site projected) target_positions=original_positions) "Mapped tail traversal changed.");
            if C.Tail.status original<>C.Inapplicable then require (endpoint_mapped budget source_id "finish_end" inputs output_space derivation) "Mapped tail must retain its original terminal boundary."
          | T.Component.Cap | T.Component.Start_end | T.Component.Finish_end ->
            require (targets=[component]) "Mapped terminal chemistry must retain its facet.";
            let getter=match T.Chemistry_disposition.component item with T.Component.Cap -> C.cap | T.Component.Start_end -> C.start_end | _ -> C.finish_end in
            let original=getter (Input.chemistry source) and target=getter output in
            require (Json.equal (C.Claim.nominal_json original) (C.Claim.nominal_json target)) "Mapped terminal chemistry changed its declared identity or knowledge.";
            if C.Claim.status original<>C.Inapplicable then require (endpoint_mapped budget source_id component inputs output_space derivation) "Mapped terminal chemistry must retain its original boundary.")
        with
        | Projection_limit error -> emit unsupported ("chemistry_projection_budget: " ^ label ^ ": " ^ error)
        | Invalid error -> emit diagnostics ("chemistry_mapping: " ^ label ^ ": " ^ error)) dispositions;
    List.iter (fun component ->
      try
        let expected=modification_coverage budget (List.assoc component output_mods) output_sequence in
        if not (Iset.equal (Hashtbl.find mapped component) expected) then emit diagnostics ("chemistry_mapping: " ^ component ^ " has unmapped output chemical sites")
      with Projection_limit error -> emit unsupported ("chemistry_projection_budget: " ^ component ^ ": " ^ error)) (List.rev !mapped_order);
    output)
let resolve_features budget transition inputs output_space derivation diagnostics unsupported =
  let expected=List.concat_map (fun (id,source) -> List.map (fun feature -> (id,F.id feature),feature) (Input.features source)) inputs in
  let supplied=List.map (fun disposition -> (T.Feature_disposition.source_id disposition,T.Feature_disposition.feature_id disposition),disposition) (T.Feature.dispositions transition) in
  charge budget (List.length expected + List.length supplied);
  let expected_index=Hashtbl.create (List.length expected) in
  List.iter (fun (key,value) -> Hashtbl.add expected_index key value) expected;
  if not (Pset.equal (Pset.of_list (List.map fst expected)) (Pset.of_list (List.map fst supplied))) then
    emit diagnostics "feature_disposition_inventory: every source annotation requires exactly one disposition";
  let output_features=T.Feature.added transition @ List.concat_map (fun (_,item) -> T.Feature_disposition.outputs item) supplied |> List.sort (fun left right -> String.compare (F.id left) (F.id right)) in
  List.iter (fun feature -> match F.path feature with
    | None -> emit unsupported ("unknown_output_feature_coordinates: " ^ F.id feature)
    | Some path -> try path_validate budget path output_space with Invalid error -> emit diagnostics ("output_feature_coordinates: " ^ F.id feature ^ ": " ^ error)) output_features;
  let residue_budget=ref 0 in
  List.iter (fun ((source_id,feature_id),disposition) ->
    charge budget 1;
    match Hashtbl.find_opt expected_index (source_id,feature_id) with
    | None -> ()
    | Some original ->
      let label=source_id ^ "/" ^ feature_id in
      match T.Feature_disposition.decision disposition with
      | T.Feature_disposition.Not_carried -> ()
      | T.Feature_disposition.Unknown -> emit unsupported ("unknown_feature_disposition: " ^ label)
      | decision -> match F.path original with
        | None -> emit unsupported ("unresolved_source_feature_geometry: " ^ label)
        | Some path when G.Path.length path=0 -> emit unsupported ("unresolved_source_feature_geometry: " ^ label)
        | Some original_path ->
          residue_budget:= !residue_budget+G.Path.length original_path;
          if !residue_budget>max_projected_residues then emit unsupported "feature_projection_budget: total source feature residue limit exceeded"
          else if decision=T.Feature_disposition.Outside_selection then (
            let intersects=List.exists (fun segment ->
              charge budget 1;
              D.source_id segment=source_id && List.exists (fun left -> List.exists (fun right ->
                charge budget 1; G.Span.start left<G.Span.stop right && G.Span.start right<G.Span.stop left) (G.Path.spans (D.source_path segment))) (G.Path.spans original_path)) derivation in
            if intersects then emit diagnostics ("feature_mapping: " ^ label ^ ": Outside-selection claim intersects selected residues."))
          else if List.exists (fun segment -> charge budget 1; D.source_id segment=source_id && D.rule segment=D.Translation_codon) derivation then
            emit unsupported ("translation_feature_mapping: " ^ label)
          else try
            let original_positions=positions budget original_path (Input.space (List.assoc source_id inputs)) in
            let order=Hashtbl.create (List.length original_positions) in List.iteri (fun index site -> Hashtbl.replace order site index) original_positions;
            let projected=project_positions budget source_id original_positions derivation in
            require (not (Imap.is_empty projected)) "Mapped feature has no selected source residues.";
            let original_coverage=Imap.fold (fun _ site sites -> Iset.add site sites) projected Iset.empty and original_sites=Iset.of_list original_positions in
            (match decision with
            | T.Feature_disposition.Exact | T.Feature_disposition.Split -> require (Iset.equal original_coverage original_sites) "Exact/split mapping cannot silently clip a source feature."
            | _ -> require (Iset.subset original_coverage original_sites && not (Iset.equal original_coverage original_sites)) "Partial mapping must explicitly represent a proper source subset.");
            let observed=ref Iset.empty in
            List.iter (fun feature ->
              charge budget 1;
              require (F.kind feature=F.kind original && F.reading_frame feature=F.reading_frame original) "Mapped feature kind or reading frame changed without an explicit new declaration.";
              require (F.path feature<>None) "Mapped feature output coordinates are unresolved.";
              let sites=positions budget (Option.get (F.path feature)) output_space in
              require (sites<>[] && List.for_all (fun site -> Imap.mem site projected) sites) "Output annotation contains residues outside its source projection.";
              require (List.for_all (fun site -> not (Iset.mem site !observed)) sites) "Mapped output annotations duplicate one projected occurrence.";
              List.iter (fun site -> observed:=Iset.add site !observed) sites;
              let progression=List.map (fun site -> Hashtbl.find order (Imap.find site projected)) sites in
              let rec increasing = function [] | [_] -> true | left :: ((right :: _) as tail) -> left<right && increasing tail in
              require (increasing progression) "Feature mapping changes source traversal order.";
              if decision=T.Feature_disposition.Exact then require (List.length progression=List.length original_positions && List.for_all2 Int.equal progression (List.init (List.length original_positions) Fun.id))
                "Exact feature mapping must preserve one complete occurrence.";
              if (decision=T.Feature_disposition.Partial || decision=T.Feature_disposition.Split) && F.reading_frame original<>None then emit unsupported ("partial_coding_feature_frame: " ^ label)) (T.Feature_disposition.outputs disposition);
            require (Iset.equal !observed (map_keys projected)) "Feature mapping omits selected source annotation residues."
          with
          | Projection_limit error -> emit unsupported ("feature_projection_budget: " ^ label ^ ": " ^ error)
          | Invalid error -> emit diagnostics ("feature_mapping: " ^ label ^ ": " ^ error)) supplied;
  output_features
type result = { chemistry:C.t option; features:F.t list; diagnostics:string list; unsupported:string list }
let chemistry value = value.chemistry
let features value = value.features
let diagnostics value = value.diagnostics
let unsupported value = value.unsupported
let to_json value = Json.Object ["chemistry",(match value.chemistry with None -> Json.Null | Some chemistry -> C.to_json chemistry);
  "features",Json.Array (List.map F.to_json value.features); "diagnostics",Json.Array (List.map (fun text -> Json.String text) value.diagnostics);
  "unsupported",Json.Array (List.map (fun text -> Json.String text) value.unsupported)]
let resolve ?budget transition feature_transition ~inputs ~output_sequence ~output_space ~derivation ~sequence_extent =
  let budget=match budget with Some value -> value | None -> make_budget () in
  charge budget 1;
  let diagnostics=messages () and unsupported=messages () in
  let result =
    match validate_derivation budget inputs output_sequence output_space derivation with
    | exception Invalid error -> {chemistry=None;features=[];diagnostics=["transition_derivation: " ^ error];unsupported=[]}
    | () ->
      let chemistry=match T.Chemistry.mode transition with
        | T.Chemistry.Exact_inheritance ->
          (try Some (identity_source budget inputs output_sequence output_space derivation) with Invalid error -> emit diagnostics ("chemistry_exact_inheritance: " ^ error); None)
        | T.Chemistry.Explicit_output -> Some (explicit_chemistry budget transition inputs output_sequence output_space derivation diagnostics unsupported) in
      Option.iter (fun chemistry ->
        (try chemistry_validate budget chemistry output_space output_sequence sequence_extent with Invalid error -> emit diagnostics ("output_chemistry: " ^ error));
        if not (C.declared_nominal_complete chemistry) then emit unsupported "unknown_output_chemistry: nominal chemistry remains incomplete") chemistry;
      let features=resolve_features budget feature_transition inputs output_space derivation diagnostics unsupported in
      {chemistry;features;diagnostics=unique_messages diagnostics;unsupported=unique_messages unsupported} in
  Molecular_record.check_resources (to_json result);
  result

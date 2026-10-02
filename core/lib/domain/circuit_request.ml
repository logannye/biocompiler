open Bioc_wire

module Names = Set.Make (String)
module Records = Map.Make (String)
type unsupported = { authority : Json.t; reasons : string list }
type 'a decoded = Decoded of 'a | Unsupported of unsupported
let unsupported_authority value = value.authority
let unsupported_reasons value = value.reasons
let require condition message = Diagnostic.require condition "invalid_circuit_record" message
let obj value = Json.object_fields value
let get key value = Json.field key (obj value)
let set key value fields = (key, value) :: List.remove_assoc key fields
let text value = Json.name value
let str value = Json.String value
let strings values = Json.Array (List.map str values)
let values value = Json.array value
let choice allowed value =
  let value = Json.string value in
  require (List.mem value allowed) "Unsupported circuit declaration choice."; value
let schema version fields value =
  let fields_actual = obj value in
  Json.exact_fields ("schema_version" :: fields) fields_actual;
  Diagnostic.require (Json.string (Json.field "schema_version" fields_actual) = version)
    "unsupported_schema" "Unsupported circuit declaration schema.";
  fields_actual
let finite value = ignore (Json.number_to_float value); value
let hash value =
  let value = Json.string value in
  require (String.length value = 64 && String.for_all (function '0' .. '9' | 'a' .. 'f' -> true | _ -> false) value)
    "Expected a lowercase SHA-256 fingerprint."; value
let equal a b = Json.equal a b && Canonical.fingerprint a = Canonical.fingerprint b
let optional parse = function Json.Null -> None | value -> Some (parse value)
let optional_json = function None -> Json.Null | Some value -> value
let option_map_json encode value = optional_json (Option.map encode value)
let no_controls value =
  require (String.for_all (fun c -> Char.code c >= 32 && Char.code c <> 127) value)
    "Circuit text cannot contain control characters."
let unicode_whitespace = ["\009"; "\010"; "\011"; "\012"; "\013"; "\028"; "\029"; "\030"; "\031"; " ";
  "\194\133"; "\194\160"; "\225\154\128"; "\226\128\128"; "\226\128\129"; "\226\128\130";
  "\226\128\131"; "\226\128\132"; "\226\128\133"; "\226\128\134"; "\226\128\135"; "\226\128\136";
  "\226\128\137"; "\226\128\138"; "\226\128\168"; "\226\128\169"; "\226\128\175"; "\226\129\159"; "\227\128\128"]
let observation_text value =
  let value = text value in
  require (String.length value <= 512) "Observation text exceeds its limit.";
  require (not (List.exists (fun whitespace -> String.starts_with ~prefix:whitespace value || String.ends_with ~suffix:whitespace value) unicode_whitespace))
    "Observation text cannot have surrounding whitespace.";
  no_controls value; value
let profile_text value =
  let value = text value in
  require (String.length value <= 16_384) "Circuit text exceeds its limit.";
  no_controls value; value

(* Python's record budgets count object keys as items and include the default
   two-space published representation plus its trailing newline. Wire budgets
   alone are looser and cannot substitute for these record-specific limits. *)
type budget = { code : string; items : int; depth : int; text_bytes : int; bytes : int; observation : bool }
let profile_budget = { code = "profile_resource_limit"; items = 20_000; depth = 64; text_bytes = 16_384; bytes = 1_000_000; observation = false }
let observation_budget = { code = "observation_resource_limit"; items = 512; depth = 12; text_bytes = 512; bytes = 64_000; observation = true }
let boolean_budget = { code = "boolean_resource_limit"; items = 2_048; depth = 8; text_bytes = 256; bytes = 16_384; observation = false }
let bounded budget value =
  Measurement_contract.preflight value;
  let insist condition = Diagnostic.require condition budget.code "Circuit record exceeds its declared resource budget." in
  let pending = ref [value, 0] and count = ref 0 and text_total = ref 0 in
  while !pending <> [] do
    match !pending with
    | [] -> ()
    | (value, depth) :: rest ->
        pending := rest; incr count; insist (!count <= budget.items && depth <= budget.depth);
        (match value with
         | Json.Object fields ->
             insist (2 * List.length fields <= budget.items - !count - List.length rest);
             let names = List.map fst fields in
             Diagnostic.require (List.length names = List.length (List.sort_uniq String.compare names)) "duplicate_key" "Duplicate object key.";
             List.iter (fun (key, value) -> pending := (str key, depth + 1) :: (value, depth + 1) :: !pending) fields
         | Json.Array items ->
             insist (List.length items <= budget.items - !count - List.length rest);
             List.iter (fun value -> pending := (value, depth + 1) :: !pending) items
         | Json.String item ->
             Json.validate_utf8 item; insist (String.length item <= budget.text_bytes);
             text_total := !text_total + String.length item; insist (!text_total <= budget.bytes);
             if budget.observation then ignore (observation_text value)
         | Json.Int _ | Json.Float _ ->
             if budget.observation then ignore (finite value) else ignore (Canonical.encode value)
         | Json.Null | Json.Bool _ -> ())
  done
let published_size budget value =
  let size = ref 1 in
  let add value = size := !size + value; Diagnostic.require (!size <= budget.bytes) budget.code
      "Published circuit record exceeds its byte budget, including the terminal newline." in
  let rec write depth = function
    | Json.Object [] | Json.Array [] -> add 2
    | Json.Object fields ->
        add 2; (* braces *)
        List.iteri (fun index (key, value) ->
            add (1 + 2 * (depth + 1) + (if index = 0 then 0 else 1));
            add (String.length (Canonical.encode (str key)) + 2); write (depth + 1) value) fields;
        add (1 + 2 * depth)
    | Json.Array items ->
        add 2;
        List.iteri (fun index value ->
            add (1 + 2 * (depth + 1) + (if index = 0 then 0 else 1)); write (depth + 1) value) items;
        add (1 + 2 * depth)
    | value -> add (String.length (Canonical.encode value)) in
  write 0 value
let checked budget value = bounded budget value; published_size budget value; value
let record budget version fields value = bounded budget value; schema version fields value
let finish budget fields = checked budget (Json.Object fields)
let named_list ?(nonempty = false) maximum value =
  let result = values value |> List.map profile_text in
  require (List.length result <= maximum && (not nonempty || result <> [])) "Invalid named inventory size.";
  require (List.length result = List.length (List.sort_uniq String.compare result)) "Duplicate named inventory.";
  List.sort String.compare result
let records ?(nonempty = false) ?(key = "id") maximum parse value =
  let result = values value in
  require (List.length result <= maximum && (not nonempty || result <> [])) "Invalid circuit record count.";
  let result = List.map parse result in
  let indexed = List.map (fun value -> text (get key value), value) result in
  require (List.length indexed = List.length (List.sort_uniq String.compare (List.map fst indexed))) "Duplicate circuit record identities.";
  List.sort (fun (a, _) (b, _) -> String.compare a b) indexed |> List.map snd
let pins ?(realization = false) value =
  let fields = schema "biocompiler.component_identity.v0.1" ["kind"; "id"; "version"; "content_fingerprint"] value in
  ignore (choice (if realization then ["model"; "reference"] else ["source"; "evidence"]) (Json.field "kind" fields));
  ignore (text (Json.field "id" fields)); ignore (text (Json.field "version" fields)); ignore (hash (Json.field "content_fingerprint" fields)); value

let interval value =
  let fields = record observation_budget "biocompiler.observation_interval.v0.1" ["lower"; "upper"; "lower_inclusive"; "upper_inclusive"] value in
  let low = finite (Json.field "lower" fields) and high = finite (Json.field "upper" fields) in
  let li = Json.boolean (Json.field "lower_inclusive" fields) and hi = Json.boolean (Json.field "upper_inclusive" fields) in
  let order = Json.number_compare low high in
  require (order < 0 || (order = 0 && li && hi)) "Numeric interval must be nonempty and ordered.";
  finish observation_budget fields
let contains interval value =
  let lower = Json.number_compare value (get "lower" interval) and upper = Json.number_compare value (get "upper" interval) in
  (lower > 0 || lower = 0 && Json.boolean (get "lower_inclusive" interval))
  && (upper < 0 || upper = 0 && Json.boolean (get "upper_inclusive" interval))
let encloses outer inner =
  let low = Json.number_compare (get "lower" outer) (get "lower" inner)
  and high = Json.number_compare (get "upper" outer) (get "upper" inner) in
  (low < 0 || low = 0 && (Json.boolean (get "lower_inclusive" outer) || not (Json.boolean (get "lower_inclusive" inner))))
  && (high > 0 || high = 0 && (Json.boolean (get "upper_inclusive" outer) || not (Json.boolean (get "upper_inclusive" inner))))
let window value =
  let fields = record observation_budget "biocompiler.observation_window.v0.1" ["reference"; "start"; "end"; "unit"; "aggregation"] value in
  let reference = observation_text (Json.field "reference" fields) in
  let aggregation = choice ["instant"; "mean"; "integral"; "any"; "all"; "unknown"] (Json.field "aggregation" fields) in
  let low = Json.field "start" fields and high = Json.field "end" fields in
  if aggregation = "unknown" then
    require (reference = "unknown" && low = Json.Null && high = Json.Null && Json.field "unit" fields = str "unknown") "Unknown timing must remain wholly unknown."
  else (
    require (reference <> "unknown") "Known timing needs a named reference.";
    ignore (choice ["s"; "ms"; "min"; "h"; "d"] (Json.field "unit" fields));
    let order = Json.number_compare (finite low) (finite high) in
    require ((aggregation = "instant" && order = 0) || (aggregation <> "instant" && order < 0)) "Observation timing disagrees with aggregation.");
  finish observation_budget fields
let encoding value =
  let fields = record observation_budget "biocompiler.observation_encoding.v0.1" ["mode"; "unit"; "low"; "high"; "allowed_range"] value in
  let mode = choice ["qualitative"; "numeric"] (Json.field "mode" fields) in
  let unit_name = observation_text (Json.field "unit" fields) in
  let low = optional interval (Json.field "low" fields) and high = optional interval (Json.field "high" fields)
  and allowed = optional interval (Json.field "allowed_range" fields) in
  if mode = "qualitative" then require (unit_name = "qualitative" && low = None && high = None && allowed = None)
      "Qualitative encoding cannot carry numeric units or thresholds."
  else (
    require (unit_name <> "qualitative" && unit_name <> "unknown") "Numeric encoding requires explicit units.";
    match low, high with
    | Some low, Some high ->
        let order = Json.number_compare (get "upper" low) (get "lower" high) in
        require (order < 0 || (order = 0 && not (contains low (get "upper" low) && contains high (get "lower" high))))
          "LOW must precede HIGH without overlap.";
        Option.iter (fun allowed -> require (encloses allowed low && encloses allowed high) "Allowed range must contain LOW and HIGH.") allowed
    | _ -> require false "Numeric encoding requires both LOW and HIGH intervals.");
  finish observation_budget (fields |> set "low" (optional_json low) |> set "high" (optional_json high) |> set "allowed_range" (optional_json allowed))
let entity value =
  let fields = record observation_budget "biocompiler.observation_entity.v0.1" ["namespace"; "accession"; "version"; "isoform"] value in
  List.iter (fun key -> ignore (observation_text (Json.field key fields))) ["namespace"; "accession"; "version"; "isoform"];
  finish observation_budget fields
let observation value =
  let fields = record observation_budget "biocompiler.circuit_observation.v0.1" ["id"; "entity"; "quantity"; "compartment"; "scope"; "window"; "encoding"] value in
  ignore (observation_text (Json.field "id" fields)); ignore (observation_text (Json.field "compartment" fields));
  ignore (choice ["mirna_activity"; "rna_abundance"; "protein_abundance"; "ligand_concentration"; "translation_rate"; "fluorescence"; "downstream_activity"] (Json.field "quantity" fields));
  ignore (choice ["cell_accessible"; "evaluator"; "external"] (Json.field "scope" fields));
  finish observation_budget (fields |> set "entity" (entity (Json.field "entity" fields))
    |> set "window" (window (Json.field "window" fields)) |> set "encoding" (encoding (Json.field "encoding" fields)))
let product value =
  let fields = record observation_budget "biocompiler.circuit_product.v0.1" ["id"; "kind"; "observation"] value in
  ignore (observation_text (Json.field "id" fields));
  let kind = choice ["protein_expression"; "mature_protein_quantity"; "reporter_fluorescence"; "biological_activity"; "rna_product"] (Json.field "kind" fields) in
  let observation = observation (Json.field "observation" fields) in
  let quantity = List.assoc kind ["protein_expression", "translation_rate"; "mature_protein_quantity", "protein_abundance";
      "reporter_fluorescence", "fluorescence"; "biological_activity", "downstream_activity"; "rna_product", "rna_abundance"] in
  require (get "quantity" observation = str quantity) "Product kind and observed quantity differ.";
  finish observation_budget (set "observation" observation fields)
let lifecycle value =
  let fields = record profile_budget "biocompiler.circuit_lifecycle.v0.1" ["mode"; "onset"; "cessation"; "clearance"] value in
  ignore (choice ["production_control"; "abundance_control"; "activity_control"; "readout"] (Json.field "mode" fields));
  finish profile_budget (List.fold_left (fun fields key -> set key (option_map_json Fun.id (optional window (Json.field key fields))) fields) fields ["onset"; "cessation"; "clearance"])
let at_path path decode value =
  try decode value with Diagnostic.Error diagnostic ->
    (match path with
     | None -> raise (Diagnostic.Error diagnostic)
     | Some path -> raise (Diagnostic.Error {diagnostic with path = Some (path ^ Option.value ~default:"" diagnostic.path)}))
module Product = struct
  type t = {json : Json.t; id : string; kind : string; observation : Json.t}
  let schema_version = "biocompiler.circuit_product.v0.1"
  let of_json ?path value =
    let json = at_path path product value in
    {json; id = Json.string (get "id" json); kind = Json.string (get "kind" json); observation = get "observation" json}
  let to_json (value : t) = value.json
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let kind (value : t) = value.kind
  let observation (value : t) = value.observation
end
module Lifecycle = struct
  type t = {json : Json.t; mode : string; onset : Json.t option; cessation : Json.t option; clearance : Json.t option}
  let schema_version = "biocompiler.circuit_lifecycle.v0.1"
  let of_json ?path value =
    let json = at_path path lifecycle value in
    {json; mode = Json.string (get "mode" json); onset = optional Fun.id (get "onset" json);
     cessation = optional Fun.id (get "cessation" json); clearance = optional Fun.id (get "clearance" json)}
  let to_json (value : t) = value.json
  let fingerprint value = Canonical.fingerprint (to_json value)
  let mode (value : t) = value.mode
  let onset (value : t) = value.onset
  let cessation (value : t) = value.cessation
  let clearance (value : t) = value.clearance
end
let provider value =
  let fields = record profile_budget "biocompiler.circuit_provider_requirement.v0.1" ["id"; "entity"; "kind"; "compartment"; "colocation_group"; "availability"] value in
  List.iter (fun key -> ignore (profile_text (Json.field key fields))) ["id"; "compartment"; "colocation_group"];
  require (Json.field "compartment" fields <> str "abstract") "Provider requires a physical compartment.";
  ignore (choice ["host"; "co_delivered"; "external_input"] (Json.field "kind" fields));
  ignore (choice ["unestablished"; "declared"] (Json.field "availability" fields));
  finish profile_budget (set "entity" (entity (Json.field "entity" fields)) fields)
module Provider = struct
  type t = {json : Json.t; id : string; kind : string; compartment : string}
  let schema_version = "biocompiler.circuit_provider_requirement.v0.1"
  let of_json ?path value =
    let json = at_path path provider value in
    {json; id = Json.string (get "id" json); kind = Json.string (get "kind" json); compartment = Json.string (get "compartment" json)}
  let to_json (value : t) = value.json
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let kind (value : t) = value.kind
  let compartment (value : t) = value.compartment
end

let signal value =
  let fields = record boolean_budget "biocompiler.circuit_signal.v0.1" ["id"; "observation_fingerprint"] value in
  let id = Json.string (Json.field "id" fields) in
  let initial = function 'a' .. 'z' | 'A' .. 'Z' | '_' -> true | _ -> false in
  require (String.length id > 0 && String.length id <= 64 && initial id.[0]
           && String.for_all (fun c -> initial c || c >= '0' && c <= '9') id) "Boolean input needs a bounded ASCII identifier.";
  ignore (hash (Json.field "observation_fingerprint" fields)); finish boolean_budget fields
let boolean_spec value =
  let fields = record boolean_budget "biocompiler.boolean_spec.v0.1" ["inputs"; "outputs"] value in
  let original = values (Json.field "inputs" fields) in
  require (List.length original <= 8) "Too many Boolean inputs.";
  let original = List.map signal original in
  let canonical = records 8 signal (Json.Array original) in
  let outputs = values (Json.field "outputs" fields) |> List.map Json.boolean in
  let count = List.length original in
  require (List.length outputs = 1 lsl count) "Boolean table requires exactly 2**input_count rows.";
  let positions = List.map (fun input ->
      let rec find index = function [] -> assert false | item :: tail -> if get "id" input = get "id" item then index else find (index + 1) tail in
      find 0 canonical) original in
  let original_outputs = Array.of_list outputs in
  let outputs = List.init (1 lsl count) (fun row ->
      let projected = List.fold_left (fun projected position -> (projected lsl 1) lor ((row lsr (count - 1 - position)) land 1)) 0 positions in
      Json.Bool original_outputs.(projected)) in
  finish boolean_budget (fields |> set "inputs" (Json.Array canonical) |> set "outputs" (Json.Array outputs))

(* Python structural equality is intentionally separate from canonical identity:
   profile/source target comparison historically accepts equal numeric values
   while recipient pins and same_authority checks bind canonical spellings. *)
let rec structural_equal a b = match a, b with
  | (Json.Int _ | Json.Float _), (Json.Int _ | Json.Float _) -> Json.number_compare a b = 0
  | Json.Bool a, (Json.Int _ | Json.Float _) -> Json.number_compare (Json.int (if a then 1 else 0)) b = 0
  | (Json.Int _ | Json.Float _), Json.Bool b -> Json.number_compare a (Json.int (if b then 1 else 0)) = 0
  | Json.Array a, Json.Array b -> List.length a = List.length b && List.for_all2 structural_equal a b
  | Json.Object a, Json.Object b ->
      let sort = List.sort (fun (a, _) (b, _) -> String.compare a b) in
      let a, b = sort a, sort b in
      List.length a = List.length b && List.for_all2 (fun (ak, av) (bk, bv) -> ak = bk && structural_equal av bv) a b
  | _ -> Json.equal a b

let lineages = ["t_cell"; "b_cell"; "nk_cell"; "monocyte"; "macrophage"; "dendritic_cell"; "neutrophil";
                "eosinophil"; "basophil"; "mast_cell"; "innate_lymphoid_cell"]
module Recipient = struct
  type t = Json.t
  let of_json value =
    let fields = record profile_budget "biocompiler.immune_recipient_identity.v0.1"
        ["lineage"; "target_fingerprint"; "cell_subtype_claim_fingerprint"; "eligibility_basis"; "empirical_support"] value in
    ignore (choice lineages (Json.field "lineage" fields));
    ignore (hash (Json.field "target_fingerprint" fields)); ignore (hash (Json.field "cell_subtype_claim_fingerprint" fields));
    require (Json.field "eligibility_basis" fields = str "declared" && Json.field "empirical_support" fields = str "unestablished")
      "Recipient declarations cannot establish empirical eligibility.";
    finish profile_budget fields
  let to_json value = value
  let fingerprint = Canonical.fingerprint
  let lineage value = Json.string (get "lineage" value)
end

module Experiment = struct
  type t = Json.t
  let of_json value =
    let fields = record profile_budget "biocompiler.human_experiment_context.v0.1"
        ["system"; "immune_classification"; "cell_identity"; "cell_state"; "compartment"; "delivery_mode";
         "sources"; "locator"; "assay_conditions"; "recipient_taxon_id"; "immune_lineage"] value in
    require (Z.equal (Json.integer (Json.field "recipient_taxon_id" fields)) (Z.of_int 9606)) "Human experiments require taxon 9606.";
    ignore (choice ["human_cell_line"; "primary_human_cells"; "human_in_vivo"] (Json.field "system" fields));
    let immune = choice ["immune"; "nonimmune"] (Json.field "immune_classification" fields) in
    (if immune = "immune" then ignore (choice lineages (Json.field "immune_lineage" fields))
     else require (Json.field "immune_lineage" fields = Json.Null) "Nonimmune source context has no immune lineage.");
    ignore (choice ["dna_delivery"; "rna_delivery"; "dna_and_rna_delivery"; "stable_dna_expression"; "not_reported"] (Json.field "delivery_mode" fields));
    List.iter (fun key -> ignore (profile_text (Json.field key fields))) ["cell_identity"; "cell_state"; "compartment"; "locator"];
    require (Json.field "compartment" fields <> str "abstract") "Source experiment requires a physical compartment.";
    let sources = values (Json.field "sources" fields) in
    require (sources <> [] && List.length sources <= 16) "Source experiment requires a bounded nonempty pin inventory.";
    let sources = List.map (fun value ->
        let value = pins value in
        ignore (profile_text (get "id" value)); ignore (profile_text (get "version" value)); value) sources in
    let key value = Json.string (get "kind" value), Json.string (get "id" value), Json.string (get "version" value) in
    require (List.length sources = List.length (List.sort_uniq Stdlib.compare (List.map key sources))) "Duplicate or conflicting experiment pins.";
    let sources = List.sort (fun a b -> Stdlib.compare (key a) (key b)) sources in
    let conditions = values (Json.field "assay_conditions" fields) |> List.map profile_text in
    require (conditions <> [] && List.length conditions <= 32 && List.length conditions = List.length (List.sort_uniq String.compare conditions))
      "Source experiment requires unique bounded assay conditions.";
    finish profile_budget (fields |> set "sources" (Json.Array sources) |> set "assay_conditions" (strings conditions))
  let to_json value = value
  let fingerprint = Canonical.fingerprint
end

(* Complete typed authority remains nested through circuit import. A projection
   is used only for source lookup, never as a replacement serialized request. *)
let source_request = Human_request.of_json

module Profile = struct
  type t = { json : Json.t; target_value : Build_request.Target.t option; source_value : Human_request.t option }
  let of_json value =
    let fields = record profile_budget "biocompiler.circuit_profile_request.v0.1"
        ["purpose"; "mode"; "molecular_form"; "boundary"; "target"; "recipient"; "source_experiment"; "source_request"] value in
    let purpose = choice ["human_immune_payload"; "human_reference"] (Json.field "purpose" fields)
    and mode = choice ["exact_reproduction"; "candidate_design"] (Json.field "mode" fields)
    and form = choice ["DNA"; "RNA"] (Json.field "molecular_form" fields) in
    ignore (choice ["import"; "planning"; "selection"; "verification"; "export"] (Json.field "boundary" fields));
    let target_value = optional (Build_request.Target.of_json ~path:"/target") (Json.field "target" fields)
    and recipient = optional Recipient.of_json (Json.field "recipient" fields)
    and experiment = optional Experiment.of_json (Json.field "source_experiment" fields)
    and source = optional source_request (Json.field "source_request" fields) in
    Option.iter (fun target -> require (Build_request.Target.kind target = Build_request.Human_target) "Circuit targets require the versioned human target contract.") target_value;
    if purpose = "human_reference" then
      require (mode = "exact_reproduction" && experiment <> None && target_value = None && recipient = None && source = None)
        "Human references require source experiment authority and cannot invent therapeutic source or target authority."
    else (
      match target_value, recipient with
      | Some target, Some recipient ->
          let target_json = Build_request.Target.to_json target in
          require (get "payload_format" target_json = str form) "Circuit form must preserve target modality.";
          let recipient_json = Recipient.to_json recipient in
          require (get "target_fingerprint" recipient_json = str (Build_request.Target.fingerprint target)) "Stale recipient target pin.";
          require (get "cell_subtype_claim_fingerprint" recipient_json = str (Canonical.fingerprint (get "cell_subtype" (get "human_target" target_json))))
            "Stale recipient subtype claim pin.";
          Option.iter (fun source ->
              match Build_request.target (Human_request.build_request source) with
              | None -> require false "Circuit source requires the original target."
              | Some source_target -> require (structural_equal source_target target_json) "Circuit target must preserve the complete original source target.") source
      | _ -> require false "Product profiles require original human target and typed immune recipient authority.");
    let source_value = source in
    let json = finish profile_budget (fields
      |> set "target" (option_map_json Build_request.Target.to_json target_value)
      |> set "recipient" (option_map_json Recipient.to_json recipient)
      |> set "source_experiment" (option_map_json Experiment.to_json experiment)
      |> set "source_request" (option_map_json Human_request.to_json source_value)) in
    Decoded { json; target_value; source_value }
  let to_json value = value.json
  let fingerprint value = Canonical.fingerprint value.json
  let purpose value = Json.string (get "purpose" value.json)
  let mode value = Json.string (get "mode" value.json)
  let target value = value.target_value
  let source_request value = value.source_value
  let source_build_request value = Option.map Human_request.build_request value.source_value
  let unimplemented_obligations value =
    ["biological_evidence_admission"]
    @ (if Option.is_some value.target_value then ["target_assumption_validation"] else [])
    @ (if get "source_experiment" value.json <> Json.Null then ["source_experiment_validation"] else [])
    @ (if purpose value = "human_reference" then ["historical_reference_scope"] else [])
    @ (if purpose value = "human_immune_payload" && get "molecular_form" value.json <> str "RNA" then ["non_rna_product"] else [])
    @ (match value.source_value with None -> [] | Some source ->
      let original = source in
      let source = Human_request.build_request source in
      ["source_behavior_correspondence"]
      @ (if List.remove_assoc "execution" (Build_request.implementation_constraints source) = [] then [] else ["uninterpreted_implementation_constraints"])
      @ (if Build_request.preferences source = [] then [] else ["uninterpreted_source_preferences"])
      @ (if Human_request.kind original = Human_request.Build then [] else
          "wrapped_source_obligations" :: Human_request.unimplemented_obligations original))
end

type circuit_behavior = { behavior_json : Json.t; executable : Behavior.t option; actions : Identity.Node.t list }
let action_inventory value =
  (* The existing serialized importer calls tuple(value): retain its accepted
     array, object-key and Unicode-character normalization, then validate every
     resulting identity against Behavior. This is not executable source code. *)
  let items = match value with
    | Json.Array items -> items
    | Json.Object fields -> List.map (fun (key, _) -> str key) fields
    | Json.String text ->
        let rec characters position acc =
          if position = String.length text then List.rev acc else
            let first = Char.code text.[position] in
            let size = if first < 0x80 then 1 else if first < 0xe0 then 2 else if first < 0xf0 then 3 else 4 in
            characters (position + size) (str (String.sub text position size) :: acc) in
        characters 0 []
    | _ -> Json.array value in
  require (items <> [] && List.length items <= 128) "Invalid executable action inventory size.";
  let names = List.map Json.string items in
  require (List.length names = List.length (List.sort_uniq String.compare names)) "Duplicate executable action identities.";
  List.sort String.compare names
let circuit_behavior value =
  let version = Json.string (get "schema_version" value) in
  let executable = match version with
    | "biocompiler.circuit_behavior.v0.1" -> false
    | "biocompiler.circuit_executable_behavior.v0.1" -> true
    | _ -> Diagnostic.fail "unsupported_schema" "Unsupported supplementary circuit behavior schema." in
  let fields = record profile_budget version
      (["inputs"; "response"; "output"; "lifecycle"; "dependencies"] @ if executable then ["action_ids"] else []) value in
  let inputs = records 8 observation (Json.field "inputs" fields)
  and dependencies = records 32 provider (Json.field "dependencies" fields)
  and output = product (Json.field "output" fields)
  and lifecycle = lifecycle (Json.field "lifecycle" fields) in
  List.iter (fun observation -> require (get "scope" observation = str "cell_accessible") "Circuit inputs must be cell-accessible observations.") inputs;
  let expected_mode = List.assoc (Json.string (get "kind" output)) ["protein_expression", "production_control"; "rna_product", "production_control";
      "mature_protein_quantity", "abundance_control"; "biological_activity", "activity_control"; "reporter_fluorescence", "readout"] in
  require (get "mode" lifecycle = str expected_mode) "Output product and lifecycle mode disagree.";
  let response, executable, actions = if executable then
      let behavior = Behavior.of_json (Json.field "response" fields) in
      let actions = action_inventory (Json.field "action_ids" fields) in
      List.iter (fun action -> match Behavior.get behavior (Identity.Node.of_string action) with
          | Some node -> require (String.starts_with ~prefix:"action." (Behavior.kind_name (Behavior.operation node))) "Executable output action must be an action node."
          | None -> require false "Executable output action is absent from Behavior.") actions;
      Behavior.to_json behavior, Some behavior, List.map Identity.Node.of_string actions
    else
      let response = boolean_spec (Json.field "response" fields) in
      let signals = values (get "inputs" response) in
      require (List.map (get "id") inputs = List.map (get "id") signals) "Boolean response must retain every declared observation.";
      List.iter2 (fun observation signal -> require (get "observation_fingerprint" signal = str (Canonical.fingerprint observation)) "Stale nominal Boolean observation pin.") inputs signals;
      require (not (List.exists (fun input -> get "id" input = get "id" (get "observation" output)) inputs)) "Combinational feedback cannot alias an input observation.";
      response, None, [] in
  let fields = fields |> set "inputs" (Json.Array inputs) |> set "dependencies" (Json.Array dependencies)
    |> set "output" output |> set "lifecycle" lifecycle |> set "response" response in
  let fields = if Option.is_some executable then set "action_ids" (strings (List.map Identity.Node.to_string actions)) fields else fields in
  {behavior_json = finish profile_budget fields; executable; actions}

let source_location value =
  let fields = obj value in
  Json.exact_fields ["file"; "line"; "function"] fields;
  ignore (text (Json.field "file" fields)); ignore (text (Json.field "function" fields));
  require (Z.sign (Json.integer (Json.field "line" fields)) > 0) "Source line must be positive."; value
let input_binding value =
  let fields = record profile_budget "biocompiler.circuit_input_binding.v0.1" ["observation_id"; "source_node_id"] value in
  ignore (profile_text (Json.field "observation_id" fields)); ignore (profile_text (Json.field "source_node_id" fields));
  finish profile_budget fields
module Requirement = struct
  type t = { json : Json.t; behavior : circuit_behavior; source_node_ids : Identity.Node.t list; role_id : Identity.Role.t option }
  let of_json value =
    let fields = record profile_budget "biocompiler.circuit_requirement.v0.1"
        ["id"; "behavior"; "role_id"; "source_node_ids"; "source_location"; "input_bindings"] value in
    ignore (profile_text (Json.field "id" fields));
    let behavior = circuit_behavior (Json.field "behavior" fields) in
    let role_id = optional (fun value -> Identity.Role.of_string (profile_text value)) (Json.field "role_id" fields) in
    let nodes = named_list 128 (Json.field "source_node_ids" fields) in
    let location = optional source_location (Json.field "source_location" fields) in
    let bindings = records ~key:"observation_id" 8 input_binding (Json.field "input_bindings" fields) in
    let observations = values (get "inputs" behavior.behavior_json) |> List.map (fun item -> Json.string (get "id" item)) |> Names.of_list
    and source_nodes = Names.of_list nodes in
    List.iter (fun binding ->
        require (Names.mem (Json.string (get "observation_id" binding)) observations) "Input binding refers to an undeclared observation.";
        require (Names.mem (Json.string (get "source_node_id" binding)) source_nodes) "Input binding must retain its source-node reference.") bindings;
    let json = finish profile_budget (fields |> set "behavior" behavior.behavior_json |> set "source_node_ids" (strings nodes)
      |> set "source_location" (optional_json location) |> set "input_bindings" (Json.Array bindings)) in
    { json; behavior; source_node_ids = List.map Identity.Node.of_string nodes; role_id }
  let to_json value = value.json
  let fingerprint value = Canonical.fingerprint value.json
  let id value = Json.string (get "id" value.json)
  let role value = value.role_id
  let source_nodes value = value.source_node_ids
  let executable_behavior value = value.behavior.executable
  let action_ids value = value.behavior.actions
  let dependencies value = values (get "dependencies" value.behavior.behavior_json) |> List.map Provider.of_json
  let output value = get "output" value.behavior.behavior_json
  let product value = Product.of_json (output value)
  let lifecycle value = Lifecycle.of_json (get "lifecycle" value.behavior.behavior_json)
  let boolean_response value = match value.behavior.executable with
    | Some _ -> None
    | None -> let response = get "response" value.behavior.behavior_json in
        Some (List.map (fun item -> Json.string (get "id" item)) (values (get "inputs" response)),
              List.map Json.boolean (values (get "outputs" response)))
  let input_bindings value = values (get "input_bindings" value.json)
    |> List.map (fun item -> Json.string (get "observation_id" item), Identity.Node.of_string (Json.string (get "source_node_id" item)))
  let unimplemented_obligations value =
    ["supplementary_output_source_correspondence"; "output_lifecycle_implementation"]
    @ (if get "inputs" value.behavior.behavior_json = Json.Array [] && input_bindings value = [] then [] else ["executable_input_observation_mapping"])
    @ (if get "dependencies" value.behavior.behavior_json = Json.Array [] then [] else ["circuit_provider_mapping"])
end

let behavior_expectation value =
  let fields = record profile_budget "biocompiler.circuit_behavior_expectation.v0.1" ["requirement_id"; "behavior"] value in
  ignore (profile_text (Json.field "requirement_id" fields));
  finish profile_budget (set "behavior" (circuit_behavior (Json.field "behavior" fields)).behavior_json fields)
let reference_lock value =
  let fields = record profile_budget "biocompiler.circuit_reference_lock.v0.1"
      ["expected_behaviors"; "realization"; "authority"; "source_experiment"; "requested_form"; "fidelity_scope"] value in
  let expected = records ~nonempty:true ~key:"requirement_id" 32 behavior_expectation (Json.field "expected_behaviors" fields)
  and realization = pins ~realization:true (Json.field "realization" fields)
  and authority = records ~nonempty:true 16 (fun value -> pins value) (Json.field "authority" fields)
  and experiment = Experiment.of_json (Json.field "source_experiment" fields) in
  List.iter (fun pin -> require (List.exists (equal pin) authority) "Reference lock must retain experiment source pins.") (values (get "sources" (Experiment.to_json experiment)));
  ignore (choice ["delivered_dna"; "dna_expression_template"; "primary_rna"; "delivered_rna"; "processed_rna"; "circular_rna"] (Json.field "requested_form" fields));
  ignore (choice ["base_identity"; "source_nominal"; "complete_nominal"] (Json.field "fidelity_scope" fields));
  finish profile_budget (fields |> set "expected_behaviors" (Json.Array expected) |> set "realization" realization
    |> set "authority" (Json.Array authority) |> set "source_experiment" (Experiment.to_json experiment))

type t = { json : Json.t; profile_value : Profile.t; requirement_values : Requirement.t list }
let schema_version = "biocompiler.circuit_request.v0.1"
let validation_scope = "circuit-request-complete-source-wrapper-declarations-authority-bindings-v2"
let of_json value =
  let fields = record profile_budget schema_version
      ["profile"; "requirements"; "requested_form"; "fidelity_scope"; "deployment_id"; "selected_realization"; "reference_lock"] value in
  match Profile.of_json (Json.field "profile" fields) with
  | Unsupported unsupported ->
      ignore (checked profile_budget value);
      Unsupported { unsupported with authority = value }
  | Decoded profile_value ->
      let raw_requirements = values (Json.field "requirements" fields) in
      require (raw_requirements <> [] && List.length raw_requirements <= 32) "Circuit request requires a bounded nonempty requirement inventory.";
      let requirements = List.map Requirement.of_json raw_requirements |> List.sort (fun a b -> String.compare (Requirement.id a) (Requirement.id b)) in
      require (List.length requirements = List.length (List.sort_uniq String.compare (List.map Requirement.id requirements))) "Duplicate requirement identities.";
      let products = ref Names.empty and outputs = ref Names.empty and shared = ref Records.empty in
      List.iter (fun requirement ->
          let role = option_map_json (fun role -> str (Identity.Role.to_string role)) (Requirement.role requirement) in
          let key id = Canonical.encode (Json.Array [role; id]) in
          let product = Requirement.output requirement in
          let product_key = key (get "id" product) and output_key = key (get "id" (get "observation" product)) in
          require (not (Names.mem product_key !products)) "Output product IDs must be unique within each role.";
          require (not (Names.mem output_key !outputs)) "Output observation IDs must be unique within each role.";
          products := Names.add product_key !products; outputs := Names.add output_key !outputs;
          List.iter (fun observation ->
              let key = key (get "id" observation) in
              Option.iter (fun previous -> require (equal previous observation) "Shared inputs must retain identical authority within their role.") (Records.find_opt key !shared);
              shared := Records.add key observation !shared)
            (values (get "inputs" (get "behavior" (Requirement.to_json requirement))))) requirements;
      let form = choice ["delivered_dna"; "dna_expression_template"; "primary_rna"; "delivered_rna"; "processed_rna"; "circular_rna"] (Json.field "requested_form" fields) in
      ignore (choice ["base_identity"; "source_nominal"; "complete_nominal"] (Json.field "fidelity_scope" fields));
      require (List.mem form ["delivered_dna"; "dna_expression_template"] = (get "molecular_form" (Profile.to_json profile_value) = str "DNA"))
        "Requested form must preserve original DNA/RNA modality without implicit transcription.";
      let selected = optional (pins ~realization:true) (Json.field "selected_realization" fields)
      and lock = optional reference_lock (Json.field "reference_lock" fields) in
      if Profile.purpose profile_value = "human_immune_payload" then (
        ignore (profile_text (Json.field "deployment_id" fields));
        let original = match Profile.source_request profile_value with
          | Some source -> source
          | None -> Diagnostic.fail "invalid_circuit_record" "Circuit products require the complete original frozen source request." in
        let source = Human_request.build_request original in
        let deployment = Human_request.deployment original in
        Option.iter (fun deployment ->
            require (Json.field "deployment_id" fields = get "id" (Human_contract.Deployment.to_json deployment))
              "Circuit deployment identity must retain original deployment authority.") deployment;
        let nodes = values (get "nodes" (Intent.to_json (Build_request.intent source)))
          |> List.to_seq |> Seq.map (fun node -> Json.string (get "id" node), node) |> Records.of_seq in
        let target = match Profile.target profile_value with Some value -> value | None -> assert false in
        let compartments = values (get "compartments" (Build_request.Target.to_json target)) |> List.map Json.string |> Names.of_list in
        List.iter (fun requirement ->
            let role = match Requirement.role requirement with Some role -> Identity.Role.to_string role | None -> "" in
            Option.iter (fun deployment -> require (role = Human_contract.Deployment.recipient_role deployment)
                "Circuit role must preserve original deployment recipient.") deployment;
            let original_role = Records.find_opt role nodes in
            require (match original_role with Some node -> get "kind" node = str "role" && List.assoc_opt "engineering" (obj (get "attributes" node)) = Some (str "in_vivo") | None -> false)
              "Product requirements must bind an original in-vivo engineered role.";
            let refs = Requirement.source_nodes requirement |> List.map Identity.Node.to_string in
            require (List.mem role refs) "Source bindings must include their original executing role.";
            List.iter (fun ref ->
                require (match Records.find_opt ref nodes with
                    | None -> false
                    | Some node -> ref = role || (get "kind" node <> str "role" && List.mem (get "role" node) [Json.Null; str role]))
                  "Missing or different-role source-node binding.") refs;
            let behavior = get "behavior" (Requirement.to_json requirement) in
            let endpoints = values (get "inputs" behavior) @ [get "observation" (Requirement.output requirement)] @ values (get "dependencies" behavior) in
            List.iter (fun item -> require (Names.mem (Json.string (get "compartment" item)) compartments) "Observation/provider must use a declared target compartment.") endpoints) requirements)
      else (
        require (Json.field "deployment_id" fields = Json.Null) "Human references cannot invent a deployment identity.";
        List.iter (fun requirement -> require (Requirement.role requirement = None && Requirement.source_nodes requirement = [] && Requirement.input_bindings requirement = [])
            "Human references use experiment authority rather than invented therapeutic roles.") requirements);
      if Profile.mode profile_value = "exact_reproduction" then (
        match lock with
        | None -> require false "Exact reproduction requires a complete reference lock."
        | Some lock ->
            require (match selected with Some selected -> equal selected (get "realization" lock) | None -> false) "Selected realization differs from reference lock.";
            let experiment = get "source_experiment" (Profile.to_json profile_value) in
            require (experiment <> Json.Null && equal experiment (get "source_experiment" lock)) "Original experiment context differs from reference lock.";
            require (Json.field "requested_form" fields = get "requested_form" lock && Json.field "fidelity_scope" fields = get "fidelity_scope" lock)
              "Form or fidelity differs from reference lock.";
            let expected = values (get "expected_behaviors" lock) |> List.map (fun item -> Json.string (get "requirement_id" item), get "behavior" item) in
            require (List.map fst expected = List.map Requirement.id requirements) "Reference lock must cover all requirements exactly.";
            List.iter2 (fun (_, expected) requirement -> require (equal expected (get "behavior" (Requirement.to_json requirement))) "Circuit behavior differs from reference lock.") expected requirements)
      else require (lock = None) "Candidate designs cannot retain exact-reference locks.";
      let json = finish profile_budget (fields |> set "profile" (Profile.to_json profile_value)
        |> set "requirements" (Json.Array (List.map Requirement.to_json requirements))
        |> set "selected_realization" (optional_json selected) |> set "reference_lock" (optional_json lock)) in
      Decoded {json; profile_value; requirement_values = requirements}
let to_json value = value.json
let fingerprint value = Canonical.fingerprint value.json
let profile value = value.profile_value
let requirements value = value.requirement_values
let requested_form value = Json.string (get "requested_form" value.json)
let unimplemented_obligations value =
  ["source_execution"; "component_material_correspondence"; "architecture_acceptance"; "molecular_reconstruction"]
  @ Profile.unimplemented_obligations value.profile_value
  @ List.concat_map Requirement.unimplemented_obligations value.requirement_values
  |> List.sort_uniq String.compare

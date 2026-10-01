open Bioc_wire
module M = Molecular_record
module G = Molecule_coordinates
module C = Molecule_chemistry
module N = Molecule
module S = Molecule_set
let str value = Json.String value
let obj value = Json.Object value
let child path name = path ^ "/" ^ name
let check ?path condition message = Diagnostic.require ?path condition "invalid_construction_artifact" message
let array maximum encode values =
  ignore (M.bounded_length ~maximum values);
  let bytes = ref 0 and nodes = ref 0 in
  let reserve json =
    bytes := !bytes + M.pretty_size json;
    Diagnostic.require (!bytes <= M.max_json_bytes) "molecular_resource_limit" "Candidate children exceed the publication budget.";
    let pending = ref [json] in
    while !pending <> [] do
      let value = List.hd !pending in pending := List.tl !pending; incr nodes;
      Diagnostic.require (!nodes <= M.max_items) "molecular_resource_limit" "Candidate children exceed the value budget.";
      match value with
      | Json.Array values -> pending := List.rev_append values !pending
      | Json.Object fields -> nodes := !nodes + List.length fields;
          pending := List.rev_append (List.map snd fields) !pending
      | _ -> ()
    done;
    Diagnostic.require (!nodes <= M.max_items) "molecular_resource_limit" "Candidate children exceed the value budget.";
    json in
  Json.Array (List.map (fun value -> reserve (encode value)) values)
let finish ~path value result = M.check_resources ~path value; result
let decode_list ~path ~maximum decode raw = M.array ~path ~maximum raw
    |> List.mapi (fun index value -> decode ~path:(child path (string_of_int index)) value)
let sorted_unique ~path id values =
  let sorted = List.sort (fun a b -> String.compare (id a) (id b)) values in
  let names = List.map id sorted in
  check ~path (List.length names = List.length (List.sort_uniq String.compare names)) "Duplicate candidate record identity.";
  sorted

module Derived_segment = struct
  type rule = Copy | Complement | Transcription | Rna_editing | Translation_codon
  let rule_name = function Copy -> "copy" | Complement -> "complement" | Transcription -> "dna_coding_to_rna.v1"
    | Rna_editing -> "rna_editing.v1" | Translation_codon -> "translation_codon.v1"
  type t = { destination : G.Span.t; source_id : string; source_path : G.Path.t; rule : rule }
  let schema_version = "biocompiler.circuit_derived_segment.v0.1"
  let to_json value = obj ["schema_version", str schema_version; "destination", G.Span.to_json value.destination;
      "source_id", str value.source_id; "source_path", G.Path.to_json value.source_path; "rule", str (rule_name value.rule)]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["destination"; "source_id"; "source_path"; "rule"] raw in
    let get key = Json.field ~path:(child path key) key fields in
    let rule = match Json.string ~path:(child path "rule") (get "rule") with
      | "copy" -> Copy | "complement" -> Complement | "dna_coding_to_rna.v1" -> Transcription
      | "rna_editing.v1" -> Rna_editing | "translation_codon.v1" -> Translation_codon
      | _ -> Diagnostic.fail ~path "invalid_construction_artifact" "Unsupported derivation rule." in
    let value = { destination = G.Span.of_json ~path:(child path "destination") (get "destination");
      source_id = M.text ~path:(child path "source_id") (get "source_id");
      source_path = G.Path.of_json ~path:(child path "source_path") (get "source_path"); rule } in
    let length = G.Span.length value.destination in
    check ~path (length > 0 && G.Path.length value.source_path = length * (if rule = Translation_codon then 3 else 1))
      "Derivation cardinality disagrees with its explicit residue rule.";
    finish ~path (to_json value) value
  let make ~destination ~source_id ~source_path ~rule = of_json (to_json { destination; source_id; source_path; rule })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let destination value = value.destination
  let source_id value = value.source_id
  let source_path value = value.source_path
  let rule value = value.rule
end

module Consumed_segment = struct
  type t = { source_id : string; source_path : G.Path.t }
  let schema_version = "biocompiler.circuit_consumed_segment.v0.1"
  let to_json value = obj ["schema_version", str schema_version; "source_id", str value.source_id;
      "source_path", G.Path.to_json value.source_path; "reason", str "terminal_stop"]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["source_id"; "source_path"; "reason"] raw in
    let get key = Json.field ~path:(child path key) key fields in
    let value = { source_id = M.text ~path:(child path "source_id") (get "source_id");
      source_path = G.Path.of_json ~path:(child path "source_path") (get "source_path") } in
    check ~path (Json.string ~path:(child path "reason") (get "reason") = "terminal_stop") "Unsupported source consumption reason.";
    check ~path (G.Path.length value.source_path = 3 && G.Path.strand value.source_path = G.Forward)
      "Terminal stop requires three forward source bases.";
    finish ~path (to_json value) value
  let make ~source_id ~source_path = of_json (to_json { source_id; source_path })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let source_id value = value.source_id
  let source_path value = value.source_path
end

module Value = struct
  type t = { id : string; space : G.Space.t; sequence : string; chemistry : C.t;
    features : N.Feature.t list; segments : Derived_segment.t list; step_id : string;
    sequence_extent : C.sequence_extent; consumed : Consumed_segment.t list }
  let schema_version = "biocompiler.circuit_constructed_value.v0.1"
  let extent_name = function C.Complete -> "complete" | C.Exact_core -> "exact_core"
  let to_json value = obj ["schema_version", str schema_version; "id", str value.id;
      "space", G.Space.to_json value.space; "sequence", str value.sequence; "chemistry", C.to_json value.chemistry;
      "features", array 256 N.Feature.to_json value.features; "segments", array 128 Derived_segment.to_json value.segments;
      "step_id", str value.step_id; "sequence_extent", str (extent_name value.sequence_extent);
      "consumed", array 16 Consumed_segment.to_json value.consumed]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "space"; "sequence"; "chemistry"; "features"; "segments";
        "step_id"; "sequence_extent"; "consumed"] raw in
    let get key = Json.field ~path:(child path key) key fields in
    let sequence_extent = match Json.string ~path:(child path "sequence_extent") (get "sequence_extent") with
      | "complete" -> C.Complete | "exact_core" -> C.Exact_core
      | _ -> Diagnostic.fail ~path "invalid_construction_artifact" "Unsupported candidate sequence extent." in
    let features = decode_list ~path:(child path "features") ~maximum:256 (fun ~path raw -> N.Feature.of_json ~path raw) (get "features")
        |> sorted_unique ~path:(child path "features") N.Feature.id in
    let value = { id = M.text ~path:(child path "id") (get "id");
      space = G.Space.of_json ~path:(child path "space") (get "space");
      sequence = Json.string ~path:(child path "sequence") (get "sequence");
      chemistry = C.of_json ~path:(child path "chemistry") (get "chemistry"); features;
      segments = decode_list ~path:(child path "segments") ~maximum:128 (fun ~path raw -> Derived_segment.of_json ~path raw) (get "segments");
      step_id = M.text ~path:(child path "step_id") (get "step_id"); sequence_extent;
      consumed = decode_list ~path:(child path "consumed") ~maximum:16 (fun ~path raw -> Consumed_segment.of_json ~path raw) (get "consumed") } in
    check ~path (M.valid_sequence (G.Space.alphabet value.space) value.sequence && String.length value.sequence = G.Space.length value.space)
      "Constructed spelling and frame disagree.";
    C.validate_for value.chemistry value.space ~sequence:value.sequence ~sequence_extent;
    List.iter (fun feature -> Option.iter (fun path -> G.Path.validate_for path value.space) (N.Feature.path feature)) value.features;
    check ~path (value.segments <> []) "Derivation partition must be nonempty.";
    let cursor = List.fold_left (fun cursor segment ->
        let destination = Derived_segment.destination segment in
        check ~path (G.Span.start destination = cursor) "Derivation partition contains a gap or overlap.";
        G.Span.stop destination) 0 value.segments in
    check ~path (cursor = G.Space.length value.space) "Derivation partition must cover every proposed residue.";
    let consumed_ids = List.map Consumed_segment.fingerprint value.consumed in
    check ~path (List.length consumed_ids = List.length (List.sort_uniq String.compare consumed_ids)) "Duplicate consumed-source correspondence.";
    finish ~path (to_json value) value
  let make ~id ~space ~sequence ~chemistry ~features ~segments ~step_id ~sequence_extent ~consumed =
    of_json (to_json { id; space; sequence; chemistry; features; segments; step_id; sequence_extent; consumed })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id value = value.id
  let space value = value.space
  let sequence value = value.sequence
  let chemistry value = value.chemistry
  let features value = value.features
  let segments value = value.segments
  let step_id value = value.step_id
  let sequence_extent value = value.sequence_extent
  let consumed value = value.consumed
end

type t = { request_fingerprint : string; values : Value.t list; bundle : S.t option;
           missing_members : string list; diagnostics : string list; experimental_amounts : S.Amount.t list }
let schema_version = "biocompiler.circuit_construction_candidate.v0.1"
let to_json value = obj ["schema_version", str schema_version; "request_fingerprint", str value.request_fingerprint;
    "values", array 256 Value.to_json value.values; "bundle", (match value.bundle with None -> Json.Null | Some bundle -> S.to_json bundle);
    "missing_members", array 256 str value.missing_members; "diagnostics", array 1024 str value.diagnostics;
    "experimental_amounts", array 128 S.Amount.to_json value.experimental_amounts]
let of_json ?(path = "") raw =
  let fields = M.record ~path schema_version ["request_fingerprint"; "values"; "bundle"; "missing_members"; "diagnostics"; "experimental_amounts"] raw in
  let get key = Json.field ~path:(child path key) key fields in
  let request_fingerprint = Json.string ~path:(child path "request_fingerprint") (get "request_fingerprint") in
  check ~path (String.length request_fingerprint = 64 && String.for_all (function '0' .. '9' | 'a' .. 'f' -> true | _ -> false) request_fingerprint)
    "Construction request pin requires lowercase SHA-256.";
  let values = decode_list ~path:(child path "values") ~maximum:256 (fun ~path raw -> Value.of_json ~path raw) (get "values")
      |> sorted_unique ~path:(child path "values") Value.id in
  let frames = List.map (fun value -> G.Space.id (Value.space value) |> G.Space_id.to_string) values in
  check ~path (List.length frames = List.length (List.sort_uniq String.compare frames)) "Duplicate constructed coordinate frames.";
  ignore (List.fold_left (fun count value -> let next = count + G.Space.length (Value.space value) in
      check ~path (next <= M.max_residues) "Cumulative constructed residue limit exceeded."; next) 0 values);
  let bundle = match get "bundle" with Json.Null -> None | raw -> Some (S.of_json ~path:(child path "bundle") raw) in
  let experimental_amounts = decode_list ~path:(child path "experimental_amounts") ~maximum:128
      (fun ~path raw -> S.Amount.of_json ~path raw) (get "experimental_amounts")
      |> sorted_unique ~path:(child path "experimental_amounts") S.Amount.id in
  (match bundle with
   | None -> check ~path (experimental_amounts = []) "A missing bundle cannot bind experimental quantities."
   | Some bundle -> ignore (S.Artifact.make ~bundle ~experimental_amounts ~run_metadata:[]));
  let texts key maximum text_limit =
    let path = child path key in
    let values = M.array ~path ~maximum (get key) |> List.map (M.text ~path ~maximum:text_limit) in
    let sorted = List.sort_uniq String.compare values in
    check ~path (List.length values = List.length sorted) "Duplicate candidate diagnostic or missing member."; sorted in
  let value = { request_fingerprint; values; bundle; experimental_amounts;
    missing_members = texts "missing_members" 256 4096; diagnostics = texts "diagnostics" 1024 16_384 } in
  finish ~path (to_json value) value
let make ~request_fingerprint ~values ~bundle ~missing_members ~diagnostics ~experimental_amounts =
  of_json (to_json { request_fingerprint; values; bundle; missing_members; diagnostics; experimental_amounts })
let fingerprint value = Canonical.fingerprint (to_json value)
let request_fingerprint value = value.request_fingerprint
let values value = value.values
let bundle value = value.bundle
let missing_members value = value.missing_members
let diagnostics value = value.diagnostics
let experimental_amounts value = value.experimental_amounts

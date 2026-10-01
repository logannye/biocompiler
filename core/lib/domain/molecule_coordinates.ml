open Bioc_wire

type alphabet = Dna | Rna | Protein
type topology = Linear | Circular
type axis = Five_prime_to_three_prime | N_to_c
type strand = Forward | Reverse

let max_residues = 1_000_000
let max_spans = 128
let require = Diagnostic.require

let whitespace point =
  (point >= 9 && point <= 13) || (point >= 28 && point <= 32)
  || List.mem point [0x85; 0xa0; 0x1680; 0x2028; 0x2029; 0x202f; 0x205f; 0x3000]
  || (point >= 0x2000 && point <= 0x200a)

(* Molecular text is stricter than general graph names: no surrounding Python
   whitespace or ASCII control characters. UTF-8 validation precedes indexing.
   This fixed-shape module cannot reach the general molecular tree/pretty-JSON
   resource limits: its largest record has one 4096-byte name and 128 spans. *)
let text ~path value =
  let value = Json.string ~path value in
  Json.validate_utf8 value;
  require ~path (String.length value > 0 && String.length value <= 4096)
    "invalid_coordinate_text" "Coordinate identity must contain 1 to 4096 UTF-8 bytes.";
  let cursor = ref 0 in
  while !cursor < String.length value do
    let first = Char.code value.[!cursor] in
    let width = if first < 0x80 then 1 else if first < 0xe0 then 2 else if first < 0xf0 then 3 else 4 in
    let point = ref (first land (if width = 1 then 0x7f else if width = 2 then 0x1f else if width = 3 then 0xf else 7)) in
    for offset = 1 to width - 1 do
      point := (!point lsl 6) lor (Char.code value.[!cursor + offset] land 0x3f)
    done;
    require ~path (!point >= 32 && !point <> 127) "invalid_coordinate_text"
      "Coordinate identity contains an ASCII control character.";
    if !cursor = 0 || !cursor + width = String.length value then
      require ~path (not (whitespace !point)) "invalid_coordinate_text"
        "Coordinate identity has surrounding whitespace.";
    cursor := !cursor + width
  done;
  value

let index ~path ~minimum value =
  let value = Json.integer ~path value in
  require ~path (Z.compare value (Z.of_int minimum) >= 0 && Z.compare value (Z.of_int max_residues) <= 0)
    "coordinate_limit" "Coordinate is outside the permitted residue range.";
  Z.to_int value

let record ~path schema keys value =
  let fields = Json.object_fields ~path value in
  Json.exact_fields ~path ("schema_version" :: keys) fields;
  require ~path (Json.string ~path (Json.field "schema_version" fields) = schema)
    "unsupported_schema" "Unsupported molecular coordinate schema.";
  fields

module Space_id = struct
  type t = string
  let to_string value = value
  let equal = String.equal
end

module Space = struct
  type t = { id : Space_id.t; alphabet : alphabet; length : int; topology : topology; axis : axis }
  let schema = "biocompiler.molecule_coordinate_space.v0.1"
  let of_json ?(path = "") value =
    let fields = record ~path schema ["id"; "alphabet"; "length"; "topology"; "axis"] value in
    let get key = Json.field ~path key fields in
    let id = text ~path:(path ^ "/id") (get "id") in
    let alphabet = match Json.string ~path (get "alphabet") with
      | "DNA" -> Dna | "RNA" -> Rna | "protein" -> Protein
      | _ -> Diagnostic.fail ~path "invalid_alphabet" "Unknown molecular alphabet."
    in
    let topology = match Json.string ~path (get "topology") with
      | "linear" -> Linear | "circular" -> Circular
      | _ -> Diagnostic.fail ~path "invalid_topology" "Unknown molecular topology."
    in
    let axis = match Json.string ~path (get "axis") with
      | "5prime_to_3prime" -> Five_prime_to_three_prime | "N_to_C" -> N_to_c
      | _ -> Diagnostic.fail ~path "invalid_axis" "Unknown molecular coordinate axis."
    in
    let length = index ~path:(path ^ "/length") ~minimum:1 (get "length") in
    require ~path (axis = (if alphabet = Protein then N_to_c else Five_prime_to_three_prime))
      "invalid_axis" "Coordinate axis must preserve the molecular alphabet.";
    { id; alphabet; length; topology; axis }
  let to_json (value : t) = Json.Object [
    "schema_version", Json.String schema; "id", Json.String value.id;
    "alphabet", Json.String (match value.alphabet with Dna -> "DNA" | Rna -> "RNA" | Protein -> "protein");
    "length", Json.int value.length;
    "topology", Json.String (match value.topology with Linear -> "linear" | Circular -> "circular");
    "axis", Json.String (match value.axis with Five_prime_to_three_prime -> "5prime_to_3prime" | N_to_c -> "N_to_C")]
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let alphabet (value : t) = value.alphabet
  let length (value : t) = value.length
  let topology (value : t) = value.topology
  let axis (value : t) = value.axis
end

module Span = struct
  type t = { start : int; stop : int }
  let schema = "biocompiler.molecule_index_span.v0.1"
  let of_json ?(path = "") value =
    let fields = record ~path schema ["start"; "end"] value in
    let start = index ~path:(path ^ "/start") ~minimum:0 (Json.field "start" fields) in
    let stop = index ~path:(path ^ "/end") ~minimum:start (Json.field "end" fields) in
    { start; stop }
  let to_json (value : t) = Json.Object ["schema_version", Json.String schema; "start", Json.int value.start; "end", Json.int value.stop]
  let fingerprint value = Canonical.fingerprint (to_json value)
  let start (value : t) = value.start
  let stop (value : t) = value.stop
  let length (value : t) = value.stop - value.start
end

module Path = struct
  type t = { space_id : Space_id.t; spans : Span.t list; strand : strand }
  let schema = "biocompiler.molecule_coordinate_path.v0.1"
  let of_json ?(path = "") value =
    let fields = record ~path schema ["space_id"; "spans"; "strand"] value in
    let space_id = text ~path:(path ^ "/space_id") (Json.field "space_id" fields) in
    let strand = match Json.string ~path (Json.field "strand" fields) with
      | "+" -> Forward | "-" -> Reverse
      | _ -> Diagnostic.fail ~path "invalid_strand" "Unknown molecular coordinate strand."
    in
    let values = Json.array ~path:(path ^ "/spans") (Json.field "spans" fields) in
    require ~path (List.length values >= 1 && List.length values <= max_spans)
      "coordinate_span_limit" "Coordinate path requires 1 to 128 spans.";
    let spans = List.mapi (fun i value -> Span.of_json ~path:(path ^ "/spans/" ^ string_of_int i) value) values in
    require ~path (List.length spans = 1 || List.for_all (fun span -> Span.length span > 0) spans)
      "mixed_boundary_path" "A boundary annotation must be a single empty span.";
    let sorted = List.sort (fun left right ->
      let order = Int.compare (Span.start left) (Span.start right) in
      if order <> 0 then order else Int.compare (Span.stop left) (Span.stop right)) spans in
    let rec disjoint = function
      | left :: (right :: _ as rest) -> Span.stop left <= Span.start right && disjoint rest
      | _ -> true
    in
    require ~path (disjoint sorted) "coordinate_overlap" "A coordinate path cannot overlap itself.";
    { space_id; spans; strand }
  let to_json (value : t) = Json.Object [
    "schema_version", Json.String schema; "space_id", Json.String value.space_id;
    "spans", Json.Array (List.map Span.to_json value.spans);
    "strand", Json.String (match value.strand with Forward -> "+" | Reverse -> "-")]
  let fingerprint value = Canonical.fingerprint (to_json value)
  let space_id (value : t) = value.space_id
  let spans (value : t) = value.spans
  let strand (value : t) = value.strand
  let length (value : t) = List.fold_left (fun total span -> total + Span.length span) 0 value.spans
  let validate_for (value : t) space =
    require (Space_id.equal value.space_id (Space.id space)) "coordinate_space_mismatch" "Path names a different coordinate space.";
    require (List.for_all (fun span -> Span.stop span <= Space.length space) value.spans)
      "coordinate_bounds" "Coordinate path extends beyond its declared space.";
    require (Space.alphabet space <> Protein || value.strand = Forward)
      "protein_orientation" "Protein coordinates require N-to-C traversal with '+' strand."
  let positions ?(limit = 4096) (value : t) space =
    require (limit >= 0 && limit <= 100_000) "position_limit" "Position limit must be between 0 and 100000.";
    validate_for value space;
    require (length value <= limit) "position_limit" "Coordinate path exceeds the position-view limit.";
    let reversed = List.fold_left (fun result span ->
      let result = ref result in
      (match value.strand with
      | Forward -> for position = Span.start span to Span.stop span - 1 do result := position :: !result done
      | Reverse -> for position = Span.stop span - 1 downto Span.start span do result := position :: !result done);
      !result) [] value.spans
    in
    List.rev reversed
end

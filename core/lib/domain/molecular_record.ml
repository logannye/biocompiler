open Bioc_wire

let max_json_bytes = 4_000_000
let max_items = 100_000
let max_depth = 96
let max_residues = 1_000_000
let max_text_bytes = 4096
let require = Diagnostic.require
let limit ?path condition = require ?path condition "molecular_resource_limit" "Molecular record exceeds its bounded resource contract."

let whitespace point =
  (point >= 9 && point <= 13) || (point >= 28 && point <= 32)
  || List.mem point [0x85; 0xa0; 0x1680; 0x2028; 0x2029; 0x202f; 0x205f; 0x3000]
  || (point >= 0x2000 && point <= 0x200a)

let text ?path ?(maximum = max_text_bytes) value =
  let value = Json.string ?path value in
  Json.validate_utf8 value;
  require ?path (String.length value > 0 && String.length value <= maximum)
    "invalid_molecular_text" "Molecular text must be nonempty and within its UTF-8 byte limit.";
  let cursor = ref 0 in
  while !cursor < String.length value do
    let first = Char.code value.[!cursor] in
    let width = if first < 0x80 then 1 else if first < 0xe0 then 2 else if first < 0xf0 then 3 else 4 in
    let point = ref (first land (if width = 1 then 0x7f else if width = 2 then 0x1f else if width = 3 then 0xf else 7)) in
    for offset = 1 to width - 1 do
      point := (!point lsl 6) lor (Char.code value.[!cursor + offset] land 0x3f)
    done;
    require ?path (!point >= 32 && !point <> 127) "invalid_molecular_text" "Molecular text contains an ASCII control character.";
    if !cursor = 0 || !cursor + width = String.length value then
      require ?path (not (whitespace !point)) "invalid_molecular_text" "Molecular text has surrounding whitespace.";
    cursor := !cursor + width
  done;
  value

type visit = Enter of Json.t * int | Leave of Json.t

(* Count only a bounded prefix before traversing an OCaml list spine. Native
   callers can construct cyclic list spines as well as cyclic JSON values. *)
let bounded_length ?path ~maximum values =
  limit ?path (maximum >= 0);
  let rec loop count = function
    | [] -> count
    | _ :: remaining ->
        limit ?path (count < maximum);
        loop (count + 1) remaining
  in
  loop 0 values

let bounded_tree ?path value =
  let pending = ref [Enter (value, 0)] and queued = ref 1 and active = ref [] in
  let count = ref 0 and size = ref 0 in
  while !pending <> [] do
    let item = List.hd !pending in
    pending := List.tl !pending; decr queued;
    match item with
    | Leave parent -> active := List.filter (fun candidate -> candidate != parent) !active
    | Enter (value, depth) ->
        incr count; limit ?path (!count <= max_items && depth <= max_depth);
        (match value with
        | Json.Object fields ->
            require ?path (not (List.exists (fun parent -> parent == value) !active))
              "molecular_cycle" "Cyclic molecular record.";
            let remaining = max_items - !count - !queued in
            let children = 2 * bounded_length ?path ~maximum:(remaining / 2) fields in
            limit ?path (!count + !queued + children <= max_items);
            let keys = List.map fst fields in
            require ?path (List.length keys = List.length (List.sort_uniq String.compare keys))
              "duplicate_key" "Duplicate molecular JSON object key.";
            active := value :: !active;
            pending := Leave value :: !pending; incr queued;
            List.iter (fun (key, child) ->
                pending := Enter (child, depth + 1) :: Enter (Json.String key, depth + 1) :: !pending;
                queued := !queued + 2) fields;
            size := !size + children + 2
        | Json.Array values ->
            require ?path (not (List.exists (fun parent -> parent == value) !active))
              "molecular_cycle" "Cyclic molecular record.";
            let children = bounded_length ?path ~maximum:(max_items - !count - !queued) values in
            limit ?path (!count + !queued + children <= max_items);
            active := value :: !active;
            pending := Leave value :: !pending; incr queued;
            List.iter (fun child -> pending := Enter (child, depth + 1) :: !pending; incr queued) values;
            size := !size + children + 2
        | Json.String value ->
            Json.validate_utf8 value;
            limit ?path (String.length value <= max_residues);
            size := !size + String.length value + 2
        | Json.Int value ->
            limit ?path (Z.numbits value <= 4096);
            size := !size + String.length (Z.to_string value)
        | Json.Float value ->
            require ?path (Float.is_finite value) "nonfinite_number" "Molecular numbers must be finite.";
            size := !size + String.length (Canonical.float_string value)
        | Json.Null | Json.Bool _ -> size := !size + 5);
        limit ?path (!size <= max_json_bytes)
  done

let quoted_size value =
  Json.validate_utf8 value;
  String.fold_left (fun size char -> size + match char with
    | '"' | '\\' | '\b' | '\012' | '\n' | '\r' | '\t' -> 2
    | char when Char.code char < 32 -> 6
    | _ -> 1) 2 value

let pretty_size ?(indent = Some 2) value =
  bounded_tree value;
  (match indent with None -> () | Some width -> require (width >= 0 && width <= 8)
      "invalid_molecular_indent" "Molecular indentation must be absent or between zero and eight.");
  let rec size depth = function
    | Json.Null -> 4 | Json.Bool true -> 4 | Json.Bool false -> 5
    | Json.Int value -> String.length (Z.to_string value)
    | Json.Float value -> String.length (Canonical.float_string value)
    | Json.String value -> quoted_size value
    | Json.Array values -> container depth (List.map (size (depth + 1)) values)
    | Json.Object fields -> container depth (List.map (fun (key, value) -> quoted_size key + 2 + size (depth + 1) value) fields)
  and container depth lengths =
    match lengths with
    | [] -> 2
    | _ ->
        let count = List.length lengths in
        let content = List.fold_left ( + ) 0 lengths in
        match indent with
        | None -> 2 + content + (2 * (count - 1))
        | Some width -> 2 + content + (count - 1) + count * (1 + (depth + 1) * width) + 1 + depth * width
  in
  size 0 value

let check_resources ?path value =
  bounded_tree ?path value;
  limit ?path (pretty_size value + 1 <= max_json_bytes)

let record ?path schema keys value =
  bounded_tree ?path value;
  let fields = Json.object_fields ?path value in
  Json.exact_fields ?path ("schema_version" :: keys) fields;
  require ?path (Json.string ?path (Json.field "schema_version" fields) = schema)
    "unsupported_schema" "Unsupported molecular record schema.";
  fields

let array ?path ~maximum value =
  let values = Json.array ?path value in
  ignore (bounded_length ?path ~maximum:(min maximum max_items) values);
  values

let index ?path ?(maximum = max_residues) value =
  let value = Json.integer ?path value in
  require ?path (Z.sign value >= 0 && Z.compare value (Z.of_int maximum) <= 0)
    "invalid_molecular_index" "Expected a bounded nonnegative molecular integer.";
  Z.to_int value

let alphabet_symbols = function
  | Molecule_coordinates.Dna -> "ACGT"
  | Molecule_coordinates.Rna -> "ACGU"
  | Molecule_coordinates.Protein -> "ACDEFGHIKLMNPQRSTVWYOU"
let valid_sequence alphabet sequence =
  let symbols = alphabet_symbols alphabet in
  String.length sequence > 0 && String.length sequence <= max_residues
  && String.for_all (String.contains symbols) sequence

module Provenance = struct
  type status = Declared | Unknown
  type t = { status : status; authority : Pinned_identity.t list; locator : string option; reason : string }
  let schema_version = "biocompiler.molecular_declaration_provenance.v0.1"
  let to_json (value : t) = Json.Object [
      "schema_version", Json.String schema_version;
      "status", Json.String (match value.status with Declared -> "declared" | Unknown -> "unknown");
      "authority", Json.Array (List.map Pinned_identity.to_json value.authority);
      "locator", (match value.locator with None -> Json.Null | Some value -> Json.String value);
      "reason", Json.String value.reason]
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["status"; "authority"; "locator"; "reason"] value in
    let get key = Json.field ~path key fields in
    let status = match Json.string ~path (get "status") with
      | "declared" -> Declared | "unknown" -> Unknown
      | _ -> Diagnostic.fail ~path "invalid_molecular_provenance" "Unknown declaration provenance status." in
    let authority = array ~path:(path ^ "/authority") ~maximum:16 (get "authority")
      |> List.mapi (fun index -> Pinned_identity.of_json ~path:(path ^ "/authority/" ^ string_of_int index)) in
    let key value = Pinned_identity.kind_name value, Pinned_identity.id value, Pinned_identity.version value in
    let authority = List.sort (fun left right -> Stdlib.compare (key left) (key right)) authority in
    require ~path (List.for_all (fun pin -> List.mem (Pinned_identity.kind pin) [Pinned_identity.Source; Pinned_identity.Evidence]) authority)
      "invalid_molecular_provenance" "Declaration provenance requires source or evidence pins.";
    require ~path (List.length authority = List.length (List.sort_uniq Stdlib.compare (List.map key authority)))
      "invalid_molecular_provenance" "Duplicate or conflicting declaration authority.";
    let locator = match get "locator" with Json.Null -> None | value -> Some (text ~path:(path ^ "/locator") value) in
    require ~path (match status with Declared -> authority <> [] && locator <> None | Unknown -> authority = [] && locator = None)
      "invalid_molecular_provenance" "Declaration status disagrees with authority and locator.";
    let result = {status; authority; locator; reason = text ~path:(path ^ "/reason") (get "reason")} in
    check_resources ~path (to_json result); result
  let fingerprint value = Canonical.fingerprint (to_json value)
  let make ~status ~authority ~locator ~reason =
    ignore (bounded_length ~maximum:16 authority);
    of_json (to_json {status; authority; locator; reason})
  let status (value : t) = value.status
  let authority (value : t) = value.authority
  let locator (value : t) = value.locator
  let reason (value : t) = value.reason
end

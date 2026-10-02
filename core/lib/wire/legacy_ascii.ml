type layout = Compact | Spaced | Indented of int
type size = { nodes : int; bytes : int; depth : int }
let limit ?path condition = Diagnostic.require ?path condition "legacy_ascii_limit"
    "Legacy ASCII JSON exceeds its native resource budget."

(* Validation precedes this iterator, so each UTF-8 sequence is a scalar. *)
let scalars text emit =
  let byte i = Char.code text.[i] in
  let rec loop i =
    if i < String.length text then (
      let first = byte i in
      let scalar, width =
        if first < 0x80 then first, 1
        else if first < 0xe0 then ((first land 0x1f) lsl 6) lor (byte (i + 1) land 0x3f), 2
        else if first < 0xf0 then ((first land 0xf) lsl 12) lor
          ((byte (i + 1) land 0x3f) lsl 6) lor (byte (i + 2) land 0x3f), 3
        else ((first land 7) lsl 18) lor ((byte (i + 1) land 0x3f) lsl 12) lor
          ((byte (i + 2) land 0x3f) lsl 6) lor (byte (i + 3) land 0x3f), 4 in
      emit scalar; loop (i + width)) in
  loop 0
let quoted_size ?path text =
  limit ?path (String.length text <= Limits.max_string_bytes);
  Json.validate_utf8 text;
  let count = ref 2 in
  scalars text (fun code -> count := !count +
      (if List.mem code [8; 9; 10; 12; 13; 34; 92] then 2
       else if code < 32 || code >= 127 then (if code <= 0xffff then 6 else 12) else 1));
  !count
type visit = Enter of Json.t * int | Leave of Json.t
let measure ?(path = "") ?(layout = Compact) value =
  let indent = match layout with Indented value ->
      limit ~path (value >= 0 && value <= Limits.max_response_bytes); Some value
    | Compact | Spaced -> None in
  let bytes = ref 0 and nodes = ref 0 and maximum_depth = ref 0 and queued = ref 1 in
  let add amount = limit ~path (amount >= 0 && amount <= Limits.max_response_bytes - !bytes); bytes := !bytes + amount in
  let length maximum values =
    let rec loop count = function [] -> count | _ :: rest ->
      limit ~path (count < maximum); loop (count + 1) rest in loop 0 values in
  let pending = ref [Enter (value, 0)] and active = ref [] in
  while !pending <> [] do
    let next = List.hd !pending in pending := List.tl !pending;
    match next with
    | Leave value -> active := List.filter (fun item -> item != value) !active
    | Enter (value, depth) ->
        decr queued; incr nodes; maximum_depth := max !maximum_depth depth;
        limit ~path (!nodes <= Limits.max_json_nodes && depth <= Limits.max_depth);
        let enter children count =
          Diagnostic.require ~path (not (List.exists (fun item -> item == value) !active))
            "legacy_ascii_cycle" "Cyclic legacy ASCII JSON value.";
          active := value :: !active; pending := Leave value :: !pending;
          List.iter (fun child -> pending := Enter (child, depth + 1) :: !pending) children;
          queued := !queued + count in
        let punctuation count object_value =
          add (2 + max 0 (count - 1));
          if object_value then add (count * (match layout with Compact -> 1 | Spaced | Indented _ -> 2));
          (match indent with
          | Some width when count > 0 -> add (count * (1 + (depth + 1) * width) + 1 + depth * width)
          | None when layout = Spaced -> add (max 0 (count - 1))
          | _ -> ()) in
        (match value with
        | Json.Null -> add 4
        | Json.Bool flag -> add (if flag then 4 else 5)
        | Json.Int number ->
            limit ~path (Z.numbits number <= 4 * Limits.max_number_chars);
            let text = Z.to_string number in limit ~path (String.length text <= Limits.max_number_chars); add (String.length text)
        | Json.Float number -> add (String.length (Canonical.float_string number))
        | Json.String text -> add (quoted_size ~path text)
        | Json.Array values ->
            let count = length (Limits.max_json_nodes - !nodes - !queued) values in
            punctuation count false; enter values count
        | Json.Object fields ->
            let count = length (Limits.max_json_nodes - !nodes - !queued) fields in
            punctuation count true;
            let seen = Hashtbl.create 16 in
            List.iter (fun (key, _) -> add (quoted_size ~path key);
              Diagnostic.require ~path (not (Hashtbl.mem seen key)) "duplicate_key" "Duplicate legacy ASCII JSON object key.";
              Hashtbl.add seen key ()) fields;
            enter (List.rev_map snd fields) count)
  done;
  {nodes = !nodes; bytes = !bytes; depth = !maximum_depth}
let preflight ?path value = ignore (measure ?path value)
let encode ?(layout = Compact) value =
  let size = measure ~layout value in
  let buffer = Buffer.create (min 4096 size.bytes) in
  let append = Buffer.add_string buffer in
  let quoted text =
    append "\"";
    scalars text (function
      | 8 -> append "\\b" | 9 -> append "\\t" | 10 -> append "\\n"
      | 12 -> append "\\f" | 13 -> append "\\r" | 34 -> append "\\\"" | 92 -> append "\\\\"
      | code when code < 32 || code >= 127 ->
          if code <= 0xffff then append (Printf.sprintf "\\u%04x" code)
          else (let value = code - 0x10000 in
            append (Printf.sprintf "\\u%04x\\u%04x" (0xd800 lor (value lsr 10)) (0xdc00 lor (value land 0x3ff))))
      | code -> Buffer.add_char buffer (Char.chr code));
    append "\"" in
  let newline depth = match layout with Indented width ->
      Buffer.add_char buffer '\n'; append (String.make (depth * width) ' ')
    | Compact | Spaced -> () in
  let rec write depth = function
    | Json.Null -> append "null" | Json.Bool value -> append (if value then "true" else "false")
    | Json.Int value -> append (Z.to_string value) | Json.Float value -> append (Canonical.float_string value)
    | Json.String value -> quoted value
    | Json.Array values -> append "["; sequence depth (write (depth + 1)) values; append "]"
    | Json.Object fields ->
        append "{";
        sequence depth (fun (key, value) -> quoted key;
          append (match layout with Compact -> ":" | Spaced | Indented _ -> ": "); write (depth + 1) value)
          (List.sort (fun (left, _) (right, _) -> String.compare left right) fields);
        append "}"
  and sequence : 'a. int -> ('a -> unit) -> 'a list -> unit = fun depth render values ->
    let first = ref true in
    List.iter (fun value ->
      if !first then first := false else append (match layout with Spaced -> ", " | Compact | Indented _ -> ",");
      newline (depth + 1); render value) values;
    if not !first then newline depth in
  write 0 value;
  Diagnostic.require (Buffer.length buffer = size.bytes) "legacy_ascii_encoding" "Legacy ASCII size accounting mismatch.";
  Buffer.contents buffer
let fingerprint value = Canonical.sha256 (encode value)

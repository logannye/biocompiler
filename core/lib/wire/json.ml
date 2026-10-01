type t =
  | Null
  | Bool of bool
  | Int of Z.t
  | Float of float
  | String of string
  | Array of t list
  | Object of (string * t) list

let int value = Int (Z.of_int value)
let fail = Diagnostic.fail
let require = Diagnostic.require

let utf8_length text offset =
  let length = String.length text in
  let byte index = Char.code text.[index] in
  let first = byte offset in
  let count =
    if first < 0x80 then 1
    else if first >= 0xc2 && first <= 0xdf then 2
    else if first >= 0xe0 && first <= 0xef then 3
    else if first >= 0xf0 && first <= 0xf4 then 4
    else fail "invalid_utf8" "Invalid UTF-8 leading byte."
  in
  require (offset + count <= length) "invalid_utf8" "Truncated UTF-8 sequence.";
  for index = offset + 1 to offset + count - 1 do
    let value = byte index in
    require (value >= 0x80 && value <= 0xbf) "invalid_utf8" "Invalid UTF-8 continuation."
  done;
  if count >= 3 then (
    let second = byte (offset + 1) in
    require
      (not ((first = 0xe0 && second < 0xa0)
            || (first = 0xed && second >= 0xa0)
            || (first = 0xf0 && second < 0x90)
            || (first = 0xf4 && second >= 0x90)))
      "invalid_utf8" "Invalid UTF-8 scalar value.");
  count

let validate_utf8 text =
  let position = ref 0 in
  while !position < String.length text do
    position := !position + utf8_length text !position
  done

let add_codepoint buffer value =
  let add byte = Buffer.add_char buffer (Char.chr byte) in
  if value < 0x80 then add value
  else if value < 0x800 then (
    add (0xc0 lor (value lsr 6)); add (0x80 lor (value land 0x3f)))
  else if value < 0x10000 then (
    add (0xe0 lor (value lsr 12)); add (0x80 lor ((value lsr 6) land 0x3f));
    add (0x80 lor (value land 0x3f)))
  else (
    add (0xf0 lor (value lsr 18)); add (0x80 lor ((value lsr 12) land 0x3f));
    add (0x80 lor ((value lsr 6) land 0x3f)); add (0x80 lor (value land 0x3f)))

let parse text =
  let length = String.length text in
  require (length <= Limits.max_request_bytes) "request_too_large" "JSON exceeds the byte limit.";
  let position = ref 0 and nodes = ref 0 in
  let error message = fail ~path:("byte:" ^ string_of_int !position) "invalid_json" message in
  let skip () =
    while !position < length && List.mem text.[!position] [' '; '\t'; '\r'; '\n'] do
      incr position
    done
  in
  let expect ch =
    if !position >= length || text.[!position] <> ch then error "Unexpected JSON token.";
    incr position
  in
  let hex4 () =
    if !position + 4 > length then error "Incomplete Unicode escape.";
    let value = ref 0 in
    for _ = 1 to 4 do
      let ch = text.[!position] in
      let digit = match ch with
        | '0' .. '9' -> Char.code ch - 48
        | 'a' .. 'f' -> Char.code ch - 87
        | 'A' .. 'F' -> Char.code ch - 55
        | _ -> error "Invalid Unicode escape."
      in
      value := (!value lsl 4) lor digit; incr position
    done;
    !value
  in
  let read_string () =
    expect '"';
    let buffer = Buffer.create 32 in
    let finished = ref false in
    while not !finished do
      if !position >= length then error "Unterminated JSON string.";
      let ch = text.[!position] in
      if ch = '"' then (incr position; finished := true)
      else if ch = '\\' then (
        incr position;
        if !position >= length then error "Unterminated JSON escape.";
        let escaped = text.[!position] in
        incr position;
        match escaped with
        | '"' | '\\' | '/' -> Buffer.add_char buffer escaped
        | 'b' -> Buffer.add_char buffer '\b'
        | 'f' -> Buffer.add_char buffer '\012'
        | 'n' -> Buffer.add_char buffer '\n'
        | 'r' -> Buffer.add_char buffer '\r'
        | 't' -> Buffer.add_char buffer '\t'
        | 'u' ->
            let first = hex4 () in
            if first >= 0xd800 && first <= 0xdbff then (
              expect '\\'; expect 'u';
              let second = hex4 () in
              if second < 0xdc00 || second > 0xdfff then error "Unpaired high surrogate.";
              add_codepoint buffer (0x10000 + ((first - 0xd800) lsl 10) + second - 0xdc00))
            else if first >= 0xdc00 && first <= 0xdfff then error "Unpaired low surrogate."
            else add_codepoint buffer first
        | _ -> error "Unknown JSON escape.")
      else (
        if Char.code ch < 0x20 then error "Unescaped control character.";
        let count = utf8_length text !position in
        Buffer.add_substring buffer text !position count;
        position := !position + count);
      require (Buffer.length buffer <= Limits.max_string_bytes) "string_too_large" "JSON string exceeds the byte limit."
    done;
    Buffer.contents buffer
  in
  let read_number () =
    let start = !position in
    let digit () = !position < length && text.[!position] >= '0' && text.[!position] <= '9' in
    if text.[!position] = '-' then incr position;
    if not (digit ()) then error "Expected a decimal digit.";
    if text.[!position] = '0' then incr position
    else while digit () do incr position done;
    let floating = ref false in
    if !position < length && text.[!position] = '.' then (
      floating := true; incr position;
      if not (digit ()) then error "Expected fractional digits.";
      while digit () do incr position done);
    if !position < length && (text.[!position] = 'e' || text.[!position] = 'E') then (
      floating := true; incr position;
      if !position < length && (text.[!position] = '+' || text.[!position] = '-') then incr position;
      if not (digit ()) then error "Expected exponent digits.";
      while digit () do incr position done);
    require (!position - start <= Limits.max_number_chars) "number_too_large" "JSON number exceeds the digit limit.";
    let token = String.sub text start (!position - start) in
    if !floating then (
      let value = try float_of_string token with Failure _ -> error "Invalid decimal float." in
      require (Float.is_finite value) "nonfinite_number" "JSON numbers must be finite.";
      Float value)
    else Int (Z.of_string token)
  in
  let rec value depth =
    require (depth <= Limits.max_depth) "nesting_limit" "JSON exceeds the nesting limit.";
    incr nodes;
    require (!nodes <= Limits.max_json_nodes) "node_limit" "JSON exceeds the value count limit.";
    skip ();
    if !position >= length then error "Missing JSON value.";
    match text.[!position] with
    | '"' -> String (read_string ())
    | '-' | '0' .. '9' -> read_number ()
    | 'n' -> literal "null" Null
    | 't' -> literal "true" (Bool true)
    | 'f' -> literal "false" (Bool false)
    | '[' ->
        incr position; skip ();
        if !position < length && text.[!position] = ']' then (incr position; Array [])
        else (
          let items = ref [] and finished = ref false in
          while not !finished do
            items := value (depth + 1) :: !items;
            skip ();
            if !position < length && text.[!position] = ']' then (incr position; finished := true)
            else expect ','
          done;
          Array (List.rev !items))
    | '{' ->
        incr position; skip ();
        if !position < length && text.[!position] = '}' then (incr position; Object [])
        else (
          let items = ref [] and seen = Hashtbl.create 16 and finished = ref false in
          while not !finished do
            skip ();
            let key = read_string () in
            require (not (Hashtbl.mem seen key)) "duplicate_key" "Duplicate JSON object key.";
            Hashtbl.add seen key ();
            skip (); expect ':';
            items := (key, value (depth + 1)) :: !items;
            skip ();
            if !position < length && text.[!position] = '}' then (incr position; finished := true)
            else expect ','
          done;
          Object (List.rev !items))
    | _ -> error "Unexpected JSON token."
  and literal word result =
    let count = String.length word in
    if !position + count > length || String.sub text !position count <> word then error "Invalid JSON literal.";
    position := !position + count;
    result
  in
  let result = value 0 in
  skip ();
  if !position <> length then error "Trailing content after JSON value.";
  result

let object_fields ?path = function
  | Object fields -> fields
  | _ -> fail ?path "invalid_type" "Expected a JSON object."

let field ?path key fields =
  match List.assoc_opt key fields with
  | Some value -> value
  | None -> fail ?path "missing_field" ("Missing required field: " ^ key)

let allowed_fields ?path ~required ~optional fields =
  (* Parsed JSON has unique keys, but native callers can also construct [t].
     Hidden domain constructors must not accept conflicting authority through
     such values and then erase the duplicate during normalization. *)
  let keys = List.map fst fields in
  require ?path (List.length keys = List.length (List.sort_uniq String.compare keys))
    "duplicate_key" "Duplicate object key in a decoded record.";
  List.iter (fun key -> ignore (field ?path key fields)) required;
  List.iter (fun (key, _) ->
    require ?path (List.mem key required || List.mem key optional) "unknown_field" ("Unknown field: " ^ key)) fields

let exact_fields ?path expected fields = allowed_fields ?path ~required:expected ~optional:[] fields

let string ?path = function
  | String value -> value
  | _ -> fail ?path "invalid_type" "Expected a JSON string."

let name ?path value =
  let value = string ?path value in
  validate_utf8 value;
  let position = ref 0 and nonspace = ref false in
  while !position < String.length value do
    let length = utf8_length value !position in
    let first = Char.code value.[!position] in
    let point = ref (first land (if length = 1 then 0x7f else if length = 2 then 0x1f else if length = 3 then 0xf else 7)) in
    for offset = 1 to length - 1 do
      point := (!point lsl 6) lor (Char.code value.[!position + offset] land 0x3f)
    done;
    let whitespace =
      (!point >= 9 && !point <= 13) || (!point >= 28 && !point <= 32)
      || List.mem !point [0x85; 0xa0; 0x1680; 0x2028; 0x2029; 0x202f; 0x205f; 0x3000]
      || (!point >= 0x2000 && !point <= 0x200a)
    in
    if not whitespace then nonspace := true;
    position := !position + length
  done;
  require ?path !nonspace "invalid_name" "Expected a nonempty name.";
  value

let array ?path = function
  | Array values -> values
  | _ -> fail ?path "invalid_type" "Expected a JSON array."

let boolean ?path = function
  | Bool value -> value
  | _ -> fail ?path "invalid_type" "Expected a JSON Boolean."

let integer ?path = function
  | Int value -> value
  | _ -> fail ?path "invalid_type" "Expected a JSON integer."

let number ?path = function
  | (Int _ | Float _) as value -> value
  | _ -> fail ?path "invalid_type" "Expected a finite numeric value, not a Boolean."

let number_to_float ?path value =
  let value = match number ?path value with
    | Int value -> Z.to_float value
    | Float value -> value
    | _ -> assert false
  in
  require ?path (Float.is_finite value) "numeric_overflow" "Numeric value does not fit finite binary64.";
  value

let number_compare left right =
  let rational = function
    | Int value -> Q.of_bigint value
    | Float value when Float.is_finite value -> Q.of_float value
    | _ -> fail "invalid_type" "Expected finite numeric values."
  in
  Q.compare (rational left) (rational right)

let rec equal left right = match left, right with
  | Null, Null -> true
  | Bool a, Bool b -> a = b
  | Int a, Int b -> Z.equal a b
  | Float a, Float b -> Int64.equal (Int64.bits_of_float a) (Int64.bits_of_float b)
  | String a, String b -> String.equal a b
  | Array a, Array b -> List.length a = List.length b && List.for_all2 equal a b
  | Object a, Object b ->
      let sort = List.sort (fun (a, _) (b, _) -> String.compare a b) in
      let a, b = sort a, sort b in
      List.length a = List.length b && List.for_all2 (fun (ak, av) (bk, bv) -> ak = bk && equal av bv) a b
  | _ -> false

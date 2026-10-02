(* Find the shortest nearest decimal that round-trips to the exact binary64.
   Decimal rounding is done with arbitrary-precision rational arithmetic, not
   locale-sensitive printf or a platform's default float formatter. Python's
   fixed/scientific presentation thresholds are applied after digit selection. *)
let float_string value =
  Diagnostic.require (Float.is_finite value) "nonfinite_number" "Cannot encode a nonfinite number.";
  let negative = Int64.compare (Int64.bits_of_float value) 0L < 0 in
  let sign = if negative then "-" else "" in
  if value = 0. then sign ^ "0.0"
  else (
    let magnitude = Float.abs value in
    let rational = Q.of_float magnitude in
    let numerator, denominator = Q.num rational, Q.den rational in
    let power exponent = Z.pow (Z.of_int 10) exponent in
    let compare_power exponent =
      if exponent >= 0 then Z.compare numerator (Z.mul denominator (power exponent))
      else Z.compare (Z.mul numerator (power (-exponent))) denominator
    in
    let exponent = ref (String.length (Z.to_string numerator) - String.length (Z.to_string denominator)) in
    while compare_power !exponent < 0 do decr exponent done;
    while compare_power (!exponent + 1) >= 0 do incr exponent done;
    let rec shortest precision =
      Diagnostic.require (precision <= 17) "float_encoding" "No shortest binary64 representation found.";
      let scale = precision - 1 - !exponent in
      let scaled_numerator, scaled_denominator =
        if scale >= 0 then Z.mul numerator (power scale), denominator
        else numerator, Z.mul denominator (power (-scale))
      in
      let quotient, remainder = Z.ediv_rem scaled_numerator scaled_denominator in
      let comparison = Z.compare (Z.mul (Z.of_int 2) remainder) scaled_denominator in
      let rounded =
        if comparison > 0 || (comparison = 0 && Z.testbit quotient 0) then Z.succ quotient else quotient
      in
      let other = if Z.equal rounded quotient then Z.succ quotient else quotient in
      let roundtrips decimal =
        let digits = Z.to_string decimal in
        let actual_exponent = !exponent + String.length digits - precision in
        let length = ref (String.length digits) in
        while !length > 1 && digits.[!length - 1] = '0' do decr length done;
        let digits = String.sub digits 0 !length in
        let candidate =
          String.sub digits 0 1 ^ "." ^ String.sub digits 1 (String.length digits - 1)
          ^ "e" ^ string_of_int actual_exponent
        in
        if Int64.equal (Int64.bits_of_float (float_of_string candidate)) (Int64.bits_of_float magnitude)
        then Some (digits, actual_exponent)
        else None
      in
      (* At powers of two the binary64 rounding interval is asymmetric: the
         nearest decimal can fall outside its short side while the other
         bracketing decimal still round-trips. Test both, nearest first; the
         tie-to-even ordering above preserves Python's closest spelling. *)
      match List.find_map roundtrips [rounded; other] with
      | Some result -> result
      | None -> shortest (precision + 1)
    in
    let digits, exponent = shortest 1 in
    let count = String.length digits in
    let result =
      if exponent < -4 || exponent >= 16 then (
        let mantissa = String.sub digits 0 1 ^ (if count = 1 then "" else "." ^ String.sub digits 1 (count - 1)) in
        let exponent_digits = string_of_int (abs exponent) in
        mantissa ^ "e" ^ (if exponent < 0 then "-" else "+")
        ^ (if String.length exponent_digits < 2 then "0" else "") ^ exponent_digits)
      else (
        let decimal = exponent + 1 in
        if decimal <= 0 then "0." ^ String.make (-decimal) '0' ^ digits
        else if decimal >= count then digits ^ String.make (decimal - count) '0' ^ ".0"
        else String.sub digits 0 decimal ^ "." ^ String.sub digits decimal (count - decimal))
    in
    sign ^ result)

let encode_with_limit ~max_bytes value =
  let buffer = Buffer.create 256 in
  let append text =
    Diagnostic.require (Buffer.length buffer + String.length text <= max_bytes)
      "response_too_large" "Canonical JSON exceeds the response limit.";
    Buffer.add_string buffer text
  in
  let quoted text =
    Json.validate_utf8 text;
    append "\"";
    String.iter (fun character -> match character with
      | '"' -> append "\\\""
      | '\\' -> append "\\\\"
      | '\b' -> append "\\b"
      | '\012' -> append "\\f"
      | '\n' -> append "\\n"
      | '\r' -> append "\\r"
      | '\t' -> append "\\t"
      | value when Char.code value < 0x20 -> append (Printf.sprintf "\\u%04x" (Char.code value))
      | value -> append (String.make 1 value)) text;
    append "\""
  in
  let rec write depth value =
    Diagnostic.require (depth <= Limits.max_depth) "nesting_limit" "Canonical JSON exceeds the nesting limit.";
    match value with
    | Json.Null -> append "null"
    | Json.Bool value -> append (if value then "true" else "false")
    | Json.Int value -> append (Z.to_string value)
    | Json.Float value -> append (float_string value)
    | Json.String value -> quoted value
    | Json.Array values ->
        append "[";
        separated (fun value -> write (depth + 1) value) values;
        append "]"
    | Json.Object fields ->
        let fields = List.sort (fun (a, _) (b, _) -> String.compare a b) fields in
        let previous = ref None in
        List.iter (fun (key, _) ->
          Diagnostic.require (!previous <> Some key) "duplicate_key" "Duplicate object key in canonical value.";
          previous := Some key) fields;
        append "{";
        separated (fun (key, value) -> quoted key; append ":"; write (depth + 1) value) fields;
        append "}"
  and separated : 'a. ('a -> unit) -> 'a list -> unit = fun render values ->
    let first = ref true in
    List.iter (fun value -> if !first then first := false else append ","; render value) values
  in
  write 0 value;
  Buffer.contents buffer

let encode value = encode_with_limit ~max_bytes:Limits.max_response_bytes value

let encode_bounded ~max_bytes value =
  Diagnostic.require (max_bytes >= 0 && max_bytes <= 64 * 1024 * 1024)
    "invalid_json_limits" "Invalid bounded artifact JSON limits.";
  encode_with_limit ~max_bytes value

let sha256 text = Digestif.SHA256.(to_hex (digest_string text))
let fingerprint value = sha256 (encode value)

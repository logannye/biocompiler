open Bioc_wire

let require condition message = if not condition then failwith message

let canonical source expected =
  let actual = Canonical.encode (Json.parse source) in
  require (actual = expected) (Printf.sprintf "Canonical mismatch: %s => %s, expected %s" source actual expected)

let rejected source code =
  match Json.parse source with
  | _ -> failwith ("Accepted invalid JSON: " ^ source)
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code = code) ("Wrong diagnostic: " ^ diagnostic.code ^ ", expected " ^ code)

let () =
  List.iter (fun (input, expected) -> canonical input expected) [
    "null", "null";
    "[true,false,1,1.0,-0,-0.0]", "[true,false,1,1.0,0,-0.0]";
    "9007199254740993", "9007199254740993";
    "12345678901234567890123456789012345678901234567890", "12345678901234567890123456789012345678901234567890";
    "1E+2", "100.0";
    "1e-5", "1e-05";
    "0.0001", "0.0001";
    "1000000000000000.0", "1000000000000000.0";
    "10000000000000000.0", "1e+16";
    "1.2345678901234567", "1.2345678901234567";
    "1.0000000000000002", "1.0000000000000002";
    "1.234567890123456e+20", "1.234567890123456e+20";
    "1e23", "1e+23";
    "6.617444900424222e-24", "6.617444900424222e-24";
    "-5.960464477539063e-08", "-5.960464477539063e-08";
    "6.189700196426902e+26", "6.189700196426902e+26";
    "5.075883674631299e-116", "5.075883674631299e-116";
    "5e-324", "5e-324";
    "2.2250738585072014e-308", "2.2250738585072014e-308";
    "1.7976931348623157e308", "1.7976931348623157e+308";
    "-1e-4000", "-0.0";
    "{\"z\":1,\"a\":[2,3]}", "{\"a\":[2,3],\"z\":1}";
    "\"\\u00b5\\ud83e\\uddec\"", "\"µ🧬\"";
    "\"a\\/b\\n\\t\\u0000\\u001f\"", "\"a/b\\n\\t\\u0000\\u001f\"";
    "{\"🧬\":1,\"\":2,\"µ\":3}", "{\"µ\":3,\"\":2,\"🧬\":1}"
  ];
  List.iter (fun (input, code) -> rejected input code) [
    "", "invalid_json"; " ", "invalid_json"; "01", "invalid_json";
    "+1", "invalid_json"; "1.", "invalid_json"; "1e", "invalid_json";
    "NaN", "invalid_json"; "Infinity", "invalid_json";
    "1e309", "nonfinite_number"; "-1e309", "nonfinite_number";
    "[1,]", "invalid_json"; "{\"a\":1,}", "invalid_json";
    "{}{}", "invalid_json"; "[", "invalid_json";
    "{\"a\":1,\"a\":2}", "duplicate_key";
    "{\"a\":1,\"\\u0061\":2}", "duplicate_key";
    "\"\\ud800\"", "invalid_json"; "\"\\udc00\"", "invalid_json";
    "\"\\ud800\\u0041\"", "invalid_json";
    "\"\001\"", "invalid_json";
    "\"\192\128\"", "invalid_utf8";
    "\"\237\160\128\"", "invalid_utf8";
    "\"\244\144\128\128\"", "invalid_utf8";
    "\239\187\191{}", "invalid_json"
  ];
  rejected (String.make (Limits.max_depth + 1) '[' ^ "0" ^ String.make (Limits.max_depth + 1) ']') "nesting_limit";
  rejected (String.make (Limits.max_number_chars + 1) '1') "number_too_large";
  require (Canonical.sha256 "" = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855") "SHA256 empty vector";
  require (Canonical.sha256 "abc" = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad") "SHA256 abc vector";
  require (not (Json.equal (Json.Bool true) (Json.int 1))) "Boolean conflated with integer";
  require (not (Json.equal (Json.int 1) (Json.Float 1.))) "Integer conflated with float";
  require (Json.number_compare (Json.parse "9007199254740993") (Json.Float 9007199254740992.) > 0) "Large integer numeric comparison lost precision";
  (* Deterministic broad IEEE-bit sample checks roundtrip; Python differential
     fixtures additionally check the chosen shortest spelling. *)
  let state = ref 0x5eeda11ce5eedL in
  for _ = 1 to 10_000 do
    state := Int64.add (Int64.mul !state 6364136223846793005L) 1442695040888963407L;
    let value = Int64.float_of_bits !state in
    if Float.is_finite value then (
      let encoded = Canonical.float_string value in
      let decoded = Json.parse encoded in
      match decoded with
      | Json.Float restored -> require (Int64.equal (Int64.bits_of_float restored) !state) "Binary64 roundtrip changed bits"
      | _ -> failwith "Float canonicalization erased the floating-point type")
  done;
  print_endline "wire: canonical, malformed, Unicode, bounds, SHA256 and binary64 checks passed"

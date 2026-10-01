open Bioc_wire
module N = Bioc_domain.Runtime_number

let require condition message = if not condition then failwith message
let field name value = Json.field name (Json.object_fields value)
let rejected label code operation =
  match operation () with
  | () -> failwith (label ^ ": invalid numeric operation accepted")
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code = code)
        (label ^ ": expected " ^ code ^ ", got " ^ diagnostic.code)
let exact label value expected =
  let actual = Canonical.encode (N.to_json value) in
  require (actual = expected) (label ^ ": expected " ^ expected ^ ", got " ^ actual)
let int value = N.Integer (Z.of_string value)

let literals () =
  let large = int "9007199254740993" in
  require (N.compare large (N.Real 9007199254740992.) > 0) "Mixed comparison lost integer low bit";
  exact "exact integer ratio" (N.div large (N.of_int 3)) "3002399751580331.0";
  exact "signed division zero" (N.div N.zero (N.of_int (-3))) "-0.0";
  exact "first minimum representation" (N.min N.zero (N.Real (-0.))) "0";
  exact "first maximum representation" (N.max (N.Real (-0.)) N.zero) "-0.0";
  exact "sum cancellation" (N.fsum [N.Real 1e16; N.of_int 1; N.Real (-1e16)]) "1.0";
  exact "sum final rounding" (N.fsum [N.Real 9007199254740992.; N.of_int 1; N.of_int 1]) "9007199254740994.0";
  exact "sum zero sign" (N.fsum [N.Real (-0.)]) "0.0";
  exact "sum above tie" (N.fsum [N.Real 1.; N.Real (Float.ldexp 1. (-53)); N.Real (Int64.float_of_bits 1L)]) "1.0000000000000002";
  rejected "nonadvancing timer" "evaluation_nonadvancing_time" (fun () ->
      ignore (N.advance (N.Real 9007199254740992.) (N.of_int 1)));
  rejected "sum intermediate overflow" "evaluation_overflow" (fun () ->
      ignore (N.fsum [N.Real Float.max_float; N.Real Float.max_float; N.Real (-. Float.max_float)]));
  rejected "integer finite result" "evaluation_overflow" (fun () ->
      let value = N.Integer (Z.shift_left Z.one 1023) in ignore (N.add value value));
  List.iter (fun value -> rejected "finite input" "evaluation_nonfinite" (fun () ->
      ignore (N.check_finite value)))
    [N.Real Float.infinity; N.Real Float.neg_infinity; N.Real Float.nan; N.Integer (Z.shift_left Z.one 1024)];
  rejected "Boolean is not number" "evaluation_numeric_type" (fun () -> ignore (N.of_json (Json.Bool true)));
  rejected "summation inventory" "evaluation_number_limit" (fun () ->
      ignore (N.fsum (List.init (Limits.max_json_nodes + 1) (fun _ -> N.zero))));
  print_endline "runtime numbers: literal precision, representation, overflow and boundedness checked"

let execute operation operands =
  let values = List.map N.of_json operands in
  match operation, values with
  | "add", [a; b] -> N.add a b
  | "sub", [a; b] -> N.sub a b
  | "mul", [a; b] -> N.mul a b
  | "div", [a; b] -> N.div a b
  | "neg", [value] -> N.neg value
  | "compare", [a; b] -> N.of_int (let comparison = N.compare a b in if comparison = 0 then 0 else if comparison < 0 then -1 else 1)
  | "min", [a; b] -> N.min a b
  | "max", [a; b] -> N.max a b
  | "advance", [a; b] -> N.advance a b
  | "fsum", values -> N.fsum values
  | _ -> failwith "Malformed retained numeric operation"

let retained filename =
  let channel = open_in_bin filename in
  let data = Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let size = in_channel_length channel in
      require (size <= Limits.max_request_bytes) "Numeric corpus exceeds bounded JSON size";
      Json.parse (really_input_string channel size)) in
  require (Json.string (field "schema_version" data) = "biocompiler.runtime_numbers_conformance.v1")
    "Unknown runtime numeric corpus";
  let cases = Json.array (field "cases" data) in
  require (List.length cases = 1948) "Missing retained numeric cases";
  List.iter (fun case ->
      let label = Json.string (field "id" case) in
      let run () = execute (Json.string (field "operation" case)) (Json.array (field "operands" case)) in
      match List.assoc_opt "code" (Json.object_fields case) with
      | Some value -> rejected label (Json.string value) (fun () -> ignore (run ()))
      | None -> exact label (run ()) (Json.string (field "canonical_json" case))) cases;
  Printf.printf "runtime numbers: %d retained CPython/literal oracle cases checked\n" (List.length cases)

let () =
  match Array.to_list Sys.argv with
  | [_] -> literals ()
  | [_; filename] -> literals (); retained filename
  | _ -> failwith "Usage: test_runtime_number.exe [required-corpus.json]"

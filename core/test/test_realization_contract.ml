open Bioc_wire
open Bioc_domain
module R = Realization_contract
module M = Measurement_contract
module N = Runtime_number
module I = R.Input_domain
module D = R.Operating_domain
module B = R.Behavior_contract
let checks = ref 0
let check condition message = incr checks; if not condition then failwith message
let reject code run =
  incr checks;
  match run () with
  | _ -> failwith ("Realization contract unexpectedly accepted: " ^ code)
  | exception Diagnostic.Error error ->
      if error.code <> code then failwith ("Expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message)
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let set key item value = obj ((key, item) :: List.remove_assoc key (Json.object_fields value))
let remove key value = obj (List.remove_assoc key (Json.object_fields value))
let dtype text = Type_spec.of_json (Json.parse text)
let level = dtype {|{"kind":"scalar","name":"Level"}|}
let duration = dtype {|{"kind":"scalar","name":"Duration","dimensions":{"time":1}}|}
let concentration = dtype {|{"kind":"scalar","name":"Concentration","dimensions":{"amount":1,"length":-3}}|}
let boolean = dtype {|{"kind":"condition","name":"Condition"}|}
let scalar dtype value unit canonical = M.Scalar.of_json (obj ["kind", str "scalar";
    "type", Type_spec.to_json dtype; "value", value; "unit", str unit; "canonical_value", canonical])
let level_int value = scalar level (Json.int value) "1" (Json.int value)
let level_float value = scalar level (Json.Float value) "1" (Json.Float value)
let seconds value = scalar duration (Json.int value) "s" (Json.int value)
let minute = scalar duration (Json.int 1) "min" (Json.int 60)
let nanomolar value = scalar concentration (Json.int value) "nM" (Json.Float (float_of_int value *. 1e-6))
let interval dtype lower upper =
  let name = Json.string (get "name" (Type_spec.to_json dtype)) in
  M.Interval.of_json (obj ["kind", str "interval"; "lower", M.Scalar.to_json lower; "upper", M.Scalar.to_json upper;
      "type", obj ["kind", str "interval"; "name", str ("Interval[" ^ name ^ "]");
                   "dimensions", obj []; "arguments", arr [Type_spec.to_json dtype]]])
let observable = R.Observable.make ~id:"input/concentration" ~dtype:concentration ~role:"role"
    ~scope:R.Observable.Contact ~compartment:"surface" ()
let numeric = I.make ~signal_id:"antigen" ~field:I.Value ~observable
    ~allowed:(I.Range (interval concentration (nanomolar 1) (nanomolar 3)))
let qualitative = I.make ~signal_id:"ready" ~field:I.Present
    ~observable:(R.Observable.make ~id:"presence/β" ~dtype:boolean ~role:"role" ())
    ~allowed:(I.Booleans [true; false])
let domain () = D.make ~id:"domain/β" ~version:"1" ~role:"role" ~inputs:[qualitative; numeric]
    ~minimum_horizon:minute ~max_contacts:(Z.of_string "9007199254740993") ~required_capabilities:["z"; "a"] ()
let response = R.Response.make ~id:"response/β" ~rule_id:"rule" ~specification_id:"pulse"
    ~observable:(R.Observable.make ~id:"output" ~dtype:level ~role:"role" ~compartment:"secreted" ())
    ~active_range:(interval level (level_int 1) (level_int 2))
    ~inactive_range:(interval level (level_float (-0.)) (level_float 0.2))
    ~max_activation_delay:minute ~max_deactivation_delay:(seconds 0)
let contract () = B.make ~id:"contract/β" ~behavior_fingerprint:(String.make 64 'c') ~requirements:[response]

let literals () =
  (* Independent original-Python constructor identities, including Unicode,
     minute/nanomolar units, large exact contact count and signed zero. *)
  List.iter (fun (hash, expected, size, bytes) ->
      check (hash = expected) "Literal realization identity differs";
      check (size = bytes) "Literal canonical byte count differs")
    [R.Observable.fingerprint observable, "d121f9ccc233dee7a21a89e707d0b7e00362cc302a5b4c1c897e87ff7434aacd", R.Observable.canonical_size observable, 233;
     I.fingerprint numeric, "47a9e3ace0f849e64e5158ca42192ec518315883eae5e71835c3d8c9e6b907c8", I.canonical_size numeric, 895;
     I.fingerprint qualitative, "1cadd3213e04c3fbaf95c75c2d41934c980cce43102afab70dba1ea234be9cb4", I.canonical_size qualitative, 325;
     D.fingerprint (domain ()), "5257e45df128b09f18dd019b6c0841cfde85a1d4aa95904bcb1be2b6867745ce", D.canonical_size (domain ()), 1560;
     R.Response.fingerprint response, "762b34d3d19081ac5d5e1dd4c5302e4b63d1ef13fdefaeaa36f441c1ec3f4cb0", R.Response.canonical_size response, 1582;
     B.fingerprint (contract ()), "43b333844444790c2f599c232a57d857d862b05386579f9651873eac799fe88b", B.canonical_size (contract ()), 1764];
  check (D.fingerprint (D.of_json (D.to_json (domain ()))) = D.fingerprint (domain ())) "Domain roundtrip changed identity";
  check (B.fingerprint (B.of_json (B.to_json (contract ()))) = B.fingerprint (contract ())) "Contract roundtrip changed identity";
  check (List.map I.signal_id (D.inputs (domain ())) = ["antigen"; "ready"] && D.required_capabilities (domain ()) = ["a"; "z"])
    "Operating-domain deterministic order changed";
  check (D.max_contacts (domain ()) = Some (Z.of_string "9007199254740993")) "Contact limits were rounded to float";
  check (I.allowed qualitative = I.Booleans [false; true]) "Boolean range was not uniquely sorted";
  check (R.Response.id response = "response/β" && R.Response.rule_id response = "rule" && R.Response.specification_id response = "pulse")
    "Installed specification identity disappeared";
  check (B.id (contract ()) = "contract/β" && B.behavior_fingerprint (contract ()) = String.make 64 'c' && B.role (contract ()) = "role")
    "Contract source authority changed";
  check (R.Observable.role observable = "role" && I.role numeric = "role" && I.scope numeric = R.Observable.Contact
         && I.field numeric = I.Value && I.field_name numeric = "value") "Endpoint context changed";
  check (N.equal (M.Scalar.canonical (D.minimum_horizon (domain ()))) (N.of_int 60)
         && N.equal (M.Scalar.canonical (R.Response.activation response)) (N.of_int 60)
         && N.equal (M.Scalar.canonical (R.Response.deactivation response)) N.zero) "Canonical duration conversion changed";
  check (Json.equal (get "canonical_value" (M.Scalar.to_json (M.Interval.lower_scalar (R.Response.inactive response)))) (Json.Float (-0.)))
    "Signed zero changed in archived response";
  let changed = B.of_json (B.to_json (contract ()) |> set "behavior_fingerprint" (str (String.make 64 'd'))) in
  check (B.fingerprint changed <> B.fingerprint (contract ())) "Contract silently retargeted source identity";
  let raw = R.Observable.to_json observable in
  List.iter (fun (key, value) ->
      let changed = R.Observable.of_json (set key (str value) raw) in
      check (Type_spec.compatible (R.Observable.dtype observable) (R.Observable.dtype changed)
             && R.Observable.fingerprint observable <> R.Observable.fingerprint changed)
        "Compatible dimensions erased endpoint identity")
    ["id", "another"; "role", "another"; "scope", "cell"; "compartment", "another"]

let membership () =
  List.iter (fun sample -> check (I.contains numeric sample) "Closed numeric domain rejected a valid value")
    [R.Number (N.Real 1e-6); R.Number (N.Real 3e-6); R.Scalar (nanomolar 2)];
  List.iter (fun sample -> check (not (I.contains numeric sample)) "Numeric domain accepted wrong value/type/units")
    [R.Boolean true; R.Number (N.Real nan); R.Number (N.Real infinity); R.Number (N.Integer (Z.pow (Z.of_int 10) 1000));
     R.Number N.zero; R.Scalar (nanomolar 4); R.Scalar (level_int 2); R.Other;
     R.sample_of_json (M.Scalar.to_json (nanomolar 2)); R.sample_of_json (str "2")];
  let scalar_raw = M.Scalar.to_json (nanomolar 2) in
  check (I.contains numeric (R.sample_of_scalar_json scalar_raw)) "Tagged scalar lost its typed meaning";
  List.iter (fun raw -> check (not (I.contains numeric (R.sample_of_scalar_json raw)))
      "Malformed tagged scalar became a domain member")
    [set "unit" (str "seconds") scalar_raw; set "canonical_value" (Json.int 2) scalar_raw;
     set "value" (Json.Bool true) scalar_raw; remove "type" scalar_raw;
     set "canonical_value" (Json.Int (Z.pow (Z.of_int 10) 1000)) scalar_raw];
  reject "nonfinite_number" (fun () -> R.sample_of_scalar_json (set "value" (Json.Float nan) scalar_raw));
  reject "invalid_utf8" (fun () -> R.sample_of_scalar_json (set "unit" (str "\255") scalar_raw));
  reject "duplicate_key" (fun () -> R.sample_of_scalar_json (obj (("unit", str "nM") :: Json.object_fields scalar_raw)));
  let rec cyclic_sample = Json.Array [cyclic_sample] in
  reject "realization_contract_cycle" (fun () -> R.sample_of_scalar_json cyclic_sample);
  reject "realization_contract_limit" (fun () -> R.sample_of_scalar_json
      (set "unit" (str (String.make (Limits.max_string_bytes + 1) 'x')) scalar_raw));
  check (I.contains qualitative (R.Boolean false) && I.contains qualitative (R.Boolean true)
         && not (I.contains qualitative (R.Number (N.of_int 1)))) "Boolean observations coerced numeric input";
  List.iter (fun (value, active, expected) ->
      check (R.Response.accepts response (R.Number value) ~active = expected) "Response interval membership changed")
    [N.of_int 1, true, true; N.of_int 2, true, true; N.zero, true, false;
     N.Real 0.2, false, true; N.Real (-0.), false, true; N.Real 0.21, false, false];
  check (R.Response.accepts response (R.Scalar (level_int 1)) ~active:true
         && not (R.Response.accepts response (R.Scalar (seconds 1)) ~active:true)
         && not (R.Response.accepts response (R.Boolean true) ~active:true)) "Typed response membership lost dimensions";
  List.iter (fun field ->
      let input = I.make ~signal_id:"s" ~field ~observable:(I.observable qualitative) ~allowed:(I.Booleans [true]) in
      check (I.contains input (R.Boolean true) && not (I.contains input (R.Boolean false))) "Qualitative field meaning changed")
    [I.Present; I.High; I.Low];
  let alias = R.Observable.of_json (R.Observable.to_json (I.observable qualitative)
      |> set "dtype" (obj ["kind", str "condition"; "name", str "BooleanAlias"])) in
  ignore (I.make ~signal_id:"s" ~field:I.High ~observable:alias ~allowed:(I.Booleans [true]));
  let huge = Z.pow (Z.of_int 10) 1000 in
  let value = D.make ~id:"d" ~version:"1" ~role:"role" ~inputs:[qualitative] ~minimum_horizon:(seconds 1) ~max_contacts:huge () in
  check (D.max_contacts value = Some huge) "Arbitrary-precision contact bound became a runtime number";
  let zero = D.make ~id:"d" ~version:"1" ~role:"role" ~inputs:[qualitative] ~minimum_horizon:(seconds 1) ~max_contacts:Z.zero () in
  check (D.max_contacts zero = Some Z.zero) "A local-only zero contact bound was forbidden";
  let partial = R.Observable.to_json (I.observable qualitative) |> set "dtype" (obj ["kind", str "condition"; "name", str "Condition"]) in
  check (Json.equal (R.Observable.to_json (R.Observable.of_json partial)) (R.Observable.to_json (I.observable qualitative)))
    "Optional type fields did not normalize"

let negatives () =
  let raw = I.to_json qualitative in
  reject "unsupported_schema" (fun () -> I.of_json (set "schema_version" (str "future") raw));
  reject "unknown_field" (fun () -> I.of_json (set "accepted" (Json.Bool true) raw));
  reject "missing_field" (fun () -> I.of_json (remove "allowed" raw));
  reject "invalid_realization_contract" (fun () -> I.of_json (set "field" (str "automatic_threshold") raw));
  reject "invalid_type" (fun () -> I.of_json (set "allowed" (arr [Json.int 0; Json.int 1]) raw));
  List.iter (fun values -> reject "invalid_realization_contract" (fun () ->
      I.make ~signal_id:"s" ~field:I.Present ~observable:(I.observable qualitative) ~allowed:(I.Booleans values)))
    [[]; [true; true]; [false; true; false]];
  reject "invalid_realization_contract" (fun () -> I.make ~signal_id:"s" ~field:I.Value
      ~observable:(I.observable qualitative) ~allowed:(I.Range (R.Response.active response)));
  reject "invalid_realization_contract" (fun () -> I.make ~signal_id:"s" ~field:I.High
      ~observable ~allowed:(I.Booleans [true]));
  reject "type_mismatch" (fun () -> I.make ~signal_id:"s" ~field:I.Value ~observable
      ~allowed:(I.Range (R.Response.active response)));
  let raw = D.to_json (domain ()) in
  List.iter (fun inputs -> reject "invalid_realization_contract" (fun () -> D.of_json (set "inputs" (arr inputs) raw)))
    [[]; [I.to_json qualitative; I.to_json qualitative]];
  let changed key value input = I.of_json (I.to_json input |> set "observable" (set key (str value) (R.Observable.to_json (I.observable input)))) in
  reject "invalid_realization_contract" (fun () -> D.of_json (set "inputs" (arr [I.to_json (changed "role" "other" qualitative)]) raw));
  let high = I.make ~signal_id:"ready" ~field:I.High ~observable:(R.Observable.make ~id:"high" ~dtype:boolean ~role:"role"
      ~scope:R.Observable.Contact ()) ~allowed:(I.Booleans [true]) in
  reject "invalid_realization_contract" (fun () -> D.of_json (set "inputs" (arr [I.to_json qualitative; I.to_json high]) raw));
  let same_endpoint = I.make ~signal_id:"another" ~field:I.Low ~observable:(I.observable qualitative) ~allowed:(I.Booleans [true]) in
  reject "invalid_realization_contract" (fun () -> D.of_json (set "inputs" (arr [I.to_json qualitative; I.to_json same_endpoint]) raw));
  reject "invalid_realization_contract" (fun () -> D.of_json (set "max_contacts" (Json.int 0) raw));
  reject "invalid_realization_contract" (fun () -> D.of_json (set "max_contacts" (Json.int (-1)) raw));
  List.iter (fun value -> reject "invalid_type" (fun () -> D.of_json (set "max_contacts" value raw))) [Json.Bool true; Json.Float 1.5];
  reject "invalid_realization_contract" (fun () -> D.of_json (set "required_capabilities" (arr [str "a"; str "a"]) raw));
  List.iter (fun value -> reject "invalid_measurement_contract" (fun () -> D.of_json (set "minimum_horizon" (M.Scalar.to_json (seconds value)) raw))) [0; -1];
  reject "type_mismatch" (fun () -> D.of_json (set "minimum_horizon" (M.Scalar.to_json (level_int 1)) raw));
  let response_raw = R.Response.to_json response in
  List.iter (fun (lower, upper) ->
      reject "invalid_measurement_contract" (fun () -> R.Response.of_json (set "inactive_range"
          (M.Interval.to_json (interval level (level_float lower) (level_float upper))) response_raw)))
    [0., 1.; 1.2, 1.4; 2., 3.];
  reject "invalid_measurement_contract" (fun () -> R.Response.of_json
      (set "max_activation_delay" (M.Scalar.to_json (seconds (-1))) response_raw));
  reject "canonical_value_mismatch" (fun () -> R.Response.of_json (set "max_activation_delay"
      (set "canonical_value" (Json.int 1) (M.Scalar.to_json minute)) response_raw));
  reject "type_mismatch" (fun () -> R.Response.of_json (set "max_activation_delay" (M.Scalar.to_json (level_int 1)) response_raw));
  let raw = B.to_json (contract ()) in
  List.iter (fun values -> reject "invalid_realization_contract" (fun () -> B.of_json (set "requirements" (arr values) raw)))
    [[]; [response_raw; response_raw]; [response_raw; set "id" (str "other") response_raw]];
  let other = response_raw |> set "id" (str "other") |> set "rule_id" (str "another-rule") in
  reject "invalid_realization_contract" (fun () -> B.of_json (set "requirements" (arr [response_raw; other]) raw));
  let other = other |> set "observable" (R.Observable.to_json (R.Response.observable response) |> set "id" (str "another-output") |> set "role" (str "another-role")) in
  reject "invalid_realization_contract" (fun () -> B.of_json (set "requirements" (arr [response_raw; other]) raw));
  List.iter (fun hash -> reject "invalid_realization_contract" (fun () -> B.of_json (set "behavior_fingerprint" (str hash) raw)))
    [""; String.make 63 'a'; String.make 64 'A'; String.make 64 'z'];
  reject "invalid_name" (fun () -> R.Observable.make ~id:"\194\160" ~dtype:level ~role:"role" ());
  reject "invalid_measurement_contract" (fun () -> R.Observable.make ~id:"event" ~dtype:(dtype {|{"kind":"event","name":"Event"}|}) ~role:"role" ())

let resources () =
  let rec cycle = Json.Array [cycle] in
  reject "realization_contract_cycle" (fun () -> D.of_json cycle);
  let rec spine = Json.Null :: spine in
  reject "realization_contract_limit" (fun () -> D.of_json (arr spine));
  let rec fields = ("x", Json.Null) :: fields in
  reject "realization_contract_limit" (fun () -> B.of_json (obj fields));
  let rec inputs = qualitative :: inputs in
  reject "realization_contract_limit" (fun () -> D.make ~id:"d" ~version:"1" ~role:"role" ~inputs ~minimum_horizon:minute ());
  let rec requirements = response :: requirements in
  reject "realization_contract_limit" (fun () -> B.make ~id:"b" ~behavior_fingerprint:(String.make 64 'c') ~requirements);
  let rec booleans = true :: booleans in
  reject "realization_contract_limit" (fun () -> I.make ~signal_id:"s" ~field:I.High ~observable:(I.observable qualitative) ~allowed:(I.Booleans booleans));
  let rec names = "capability" :: names in
  reject "realization_contract_limit" (fun () -> D.make ~id:"d" ~version:"1" ~role:"role" ~inputs:[qualitative]
      ~minimum_horizon:minute ~required_capabilities:names ());
  let deep = List.fold_left (fun value _ -> arr [value]) Json.Null (List.init (Limits.max_depth + 1) Fun.id) in
  reject "realization_contract_limit" (fun () -> I.of_json deep);
  reject "invalid_type" (fun () -> I.of_json (arr (List.init (Limits.max_json_nodes - 1) (fun _ -> Json.Null))));
  reject "realization_contract_limit" (fun () -> I.of_json (arr (List.init Limits.max_json_nodes (fun _ -> Json.Null))));
  reject "realization_contract_limit" (fun () -> D.make ~id:"d" ~version:"1" ~role:"role" ~inputs:[qualitative]
      ~minimum_horizon:minute ~max_contacts:(Z.pow (Z.of_int 10) Limits.max_number_chars) ());
  let text = String.make Limits.max_string_bytes 'x' in
  let endpoint = R.Observable.make ~id:text ~dtype:boolean ~role:"role" () in
  reject "human_record_limit" (fun () -> R.Observable.make ~id:(text ^ "x") ~dtype:boolean ~role:"role" ());
  let large = I.make ~signal_id:"s" ~field:I.Present ~observable:endpoint ~allowed:(I.Booleans [true]) in
  ignore (D.make ~id:"d" ~version:"1" ~role:"role" ~inputs:[large] ~minimum_horizon:minute ());
  reject "realization_contract_limit" (fun () -> D.make ~id:"d" ~version:"1" ~role:"role" ~inputs:[large; large; large; large]
      ~minimum_horizon:minute ());
  let large_response = R.Response.of_json (R.Response.to_json response |> set "observable"
      (R.Observable.to_json (R.Response.observable response) |> set "id" (str text))) in
  reject "realization_contract_limit" (fun () -> B.make ~id:"b" ~behavior_fingerprint:(String.make 64 'c')
      ~requirements:[large_response; large_response; large_response; large_response]);
  reject "invalid_utf8" (fun () -> I.of_json (I.to_json qualitative |> set "signal_id" (str "\255")));
  reject "nonfinite_number" (fun () -> I.of_json (I.to_json qualitative |> set "allowed" (Json.Float infinity)));
  reject "duplicate_key" (fun () -> I.of_json (obj ["x", Json.Null; "x", Json.Null]));
  check (B.fingerprint (contract ()) = "43b333844444790c2f599c232a57d857d862b05386579f9651873eac799fe88b")
    "Failed bounded construction mutated later authority"

let () =
  if Array.length Sys.argv <> 1 then failwith "test_realization_contract accepts no arguments";
  literals (); membership (); negatives (); resources ();
  Printf.printf "Realization contracts: %d identity, membership, context and resource checks passed\n" !checks

open Bioc_wire
module C = Bioc_domain.Component_contract
module V = C.Value_domain
module O = C.Operating_domain
module P = C.Port
module T = Bioc_domain.Type_spec
module N = Bioc_domain.Runtime_number
module Text = Bioc_domain.Diagnostic_text

let checks = ref 0
let check condition message = incr checks; if not condition then failwith message
let reject code run =
  incr checks;
  match run () with
  | _ -> failwith ("Accepted component record; expected " ^ code)
  | exception Diagnostic.Error diagnostic ->
      if diagnostic.code <> code then failwith ("Expected " ^ code ^ ", received " ^ diagnostic.code)
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let set key replacement value = obj ((key, replacement) :: List.remove_assoc key (Json.object_fields value))
let number = N.of_int
let level = T.of_json (Json.parse {|{"kind":"scalar","name":"Level"}|})
let boolean = T.of_json (Json.parse {|{"kind":"condition","name":"Condition"}|})
let interval low high = V.interval ~lower:low ~upper:high ~dtype:level ~unit:"1"
let yes = V.boolean ~values:[true] ()
let no = V.boolean ~values:[false] ()
let both = V.boolean ()
let unknown = V.unknown ~dtype:boolean ~unit:"1" ~reason:"unobserved"
let port ?(direction = P.Output) ?(meaning = "meaning") ?(timing = P.Stateless) ?(initialization = both) ?(domain = both) () =
  P.make ~id:"port" ~direction ~meaning ~dtype:boolean ~unit:"1" ~role:"role" ~scope:P.Cell ~compartment:"abstract" ~timing ~initialization ~domain
let status expected value = check (C.status value = expected) "Wrong literal contract status"
let infer ?(initialization = false) ?max_contacts operation inputs =
  C.synthetic_output_domain ~operation ~attributes:(obj []) ~inputs ~dtype:boolean ~initialization ?max_contacts () |> Option.get

let literals () =
  check (V.values (V.boolean ~values:[true; false] ()) = [false; true]) "Boolean normalization changed";
  reject "component_contract" (fun () -> V.boolean ~values:[true; true] ());
  reject "component_contract" (fun () -> V.boolean ~values:[] ());
  let scalar = interval (N.Real (-0.)) (number 0) in
  check (Canonical.encode (get "lower" (V.to_json scalar)) = "-0.0") "Signed zero was erased";
  check (Canonical.encode (get "upper" (V.to_json scalar)) = "0") "Integer endpoint became a float";
  reject "component_contract" (fun () -> interval (number 1) (number 0));
  let large = interval (N.Integer (Z.of_string "9007199254740993")) (N.Integer (Z.of_string "9007199254740993")) in
  status C.Fail (C.domain_subset ~required:large ~supported:(interval (N.Real 9007199254740992.) (N.Real 9007199254740992.)));
  status C.Pass (C.domain_subset ~required:yes ~supported:both);
  status C.Fail (C.domain_subset ~required:both ~supported:yes);
  status C.Unknown (C.domain_subset ~required:unknown ~supported:unknown);
  status C.Pass (C.domain_subset ~required:scalar ~supported:scalar);
  let alias = T.of_json (Json.parse {|{"kind":"scalar","name":"Alias"}|}) in
  status C.Fail (C.domain_subset ~required:scalar ~supported:(V.interval ~lower:(number 0) ~upper:(number 0) ~dtype:alias ~unit:"1"));
  let duration = T.of_json (Json.parse {|{"kind":"scalar","name":"Duration","dimensions":{"time":1}}|}) in
  status C.Fail (C.domain_subset ~required:(V.interval ~lower:(number 0) ~upper:(number 1) ~dtype:duration ~unit:"s")
    ~supported:(V.interval ~lower:(number 0) ~upper:(number 1) ~dtype:duration ~unit:"minutes"));
  check (C.canonical_synthetic_unit duration = "s") "Duration canonical unit differs";
  reject "component_contract" (fun () -> C.contract_type (T.of_json (Json.parse {|{"kind":"event","name":"Event"}|})));
  let imported = C.Domain_check.of_json (Json.parse {|{"schema_version":"biocompiler.component_domain_check.v0.1","status":"pass","reasons":["producer says so"]}|}) in
  check (C.Domain_check.claimed_status imported = C.Pass && C.Domain_check.claimed_reasons imported = ["producer says so"])
    "Archived claims were discarded";
  let assessed = C.domain_subset ~required:both ~supported:yes in
  check (not (C.passed assessed) && C.Domain_check.claimed_status (C.Domain_check.of_assessment assessed) = C.Fail)
    "Fresh assessment accepted an incompatible domain";
  let operating = O.make ["z", both; "a", yes] in
  check (List.map fst (O.constraints operating) = ["a"; "z"]) "Operating coordinates not sorted";
  reject "duplicate_key" (fun () -> O.make ["x", yes; "x", no]);
  let failed = C.operating_domain_subset ~required:(O.make ["missing", yes; "x", both]) ~supported:(O.make ["x", no]) in
  status C.Fail failed;
  check (C.reasons failed = ["Operating coordinate 'missing' is unspecified."; "x: Required domain exceeds the supported domain."])
    "Failure priority or diagnostic order changed";
  status C.Pass (C.ports_compatible ~producer:(port ()) ~consumer:(port ~direction:P.Input ()));
  status C.Unknown (C.ports_compatible ~producer:(port ~timing:P.Unknown_timing ()) ~consumer:(port ~direction:P.Input ()));
  let initial = C.ports_compatible ~producer:(port ~initialization:yes ()) ~consumer:(port ~direction:P.Input ~initialization:no ()) in
  check (C.reasons initial = ["Initialization: Required domain exceeds the supported domain."])
    "Initialization obligation was replaced by runtime inclusion";
  ignore (port ~initialization:unknown ());
  reject "component_contract" (fun () -> port ~initialization:yes ~domain:no ());
  check (V.values (infer C.And [no; both]) = [false]) "Conjunction domain incorrect";
  check (V.values (infer C.Or [yes; both]) = [true]) "Disjunction domain incorrect";
  check (V.values (infer C.Not [yes]) = [false]) "Negation domain incorrect";
  check (V.values (infer ~max_contacts:(number 0) C.Any_contact [yes]) = [false]) "Zero contact capacity was ignored";
  check (V.values (infer ~initialization:true C.Held_for [unknown]) = [false]) "Held-for initialization incorrectly propagated unknown";
  check (V.kind (infer C.Held_for [unknown]) = V.Unknown_domain) "Runtime unknown was turned into a known guarantee";
  check (V.values (infer ~initialization:true C.Memory [yes; yes]) = [false]) "Reset does not dominate initialization";
  check (V.values (infer ~initialization:true C.Onset [yes]) = [true]) "Onset initialization changed";
  check (V.values (infer ~initialization:true C.Pulse [yes]) = [true]) "Pulse initialization changed";
  check (V.values (infer C.Compare []) = [false; true]) "Compare invented a narrowed guarantee";
  check (C.synthetic_output_domain ~operation:C.Input ~attributes:(obj []) ~inputs:[] ~dtype:boolean () = None)
    "External input incorrectly inferred a guarantee";
  reject "component_contract" (fun () -> C.synthetic_operation_of_string "delay")

let text_literals () =
  check (C.diagnostic_profile = "python_repr_unicode14.v1" && Text.profile = C.diagnostic_profile) "Missing pinned diagnostic profile";
  List.iter (fun (input, expected) -> check (Text.repr input = expected) "Literal Unicode repr differs") [
    "", "''"; "space x", "'space x'"; "quote'key", "\"quote'key\"";
    "both'\"key", "'both\\'\"key'"; "\\\n\r\t\008\012\000", "'\\\\\\n\\r\\t\\x08\\x0c\\x00'";
    "μ", "'μ'"; "a\194\133", "'a\\x85'"; "a\194\160", "'a\\xa0'";
    "a\226\128\139", "'a\\u200b'"; "a\238\128\128", "'a\\ue000'";
    "a\243\176\128\128", "'a\\U000f0000'";
    "a\240\159\171\168", "'a\\U0001fae8'"; "a\240\159\170\137", "'a\\U0001fa89'";
    "a\244\143\191\191", "'a\\U0010ffff'" ];
  reject "invalid_utf8" (fun () -> Text.repr "\255");
  reject "component_contract_limit" (fun () -> Text.repr (String.make (Limits.max_string_bytes / 4 + 1) '\001'));
  let check_unknown text =
    let result = C.operating_domain_subset ~required:(O.make [text, yes]) ~supported:(O.make []) in
    status C.Unknown result;
    check (C.reasons result = ["Operating coordinate " ^ Text.repr text ^ " is unspecified."])
      "Unicode profile changed a coordinate's semantic status"
  in check_unknown "a\240\159\171\168"; check_unknown "a\240\159\170\137"

let raw_boundary_tests () =
  let json = V.to_json both in
  let scalar = V.to_json (interval (number 0) (number 10)) in
  let unknown = V.to_json unknown in
  (* Forbidden fields are rejected by their domain kind before their leaf type
     is decoded; an unknown domain instead requires a concrete reason string. *)
  List.iter (fun reason ->
      reject "component_contract" (fun () -> V.of_json (set "reason" reason scalar));
      reject "component_contract" (fun () -> V.of_json (set "reason" reason json)))
    [arr []; obj []; Json.Bool false; Json.int 0; str "unexpected"];
  List.iter (fun reason -> reject "invalid_type" (fun () -> V.of_json (set "reason" reason unknown)))
    [Json.Null; arr []; obj []; Json.Bool false; Json.int 0];
  reject "invalid_name" (fun () -> V.of_json (set "reason" (str " ") unknown));
  List.iter (fun bound ->
      reject "component_contract" (fun () -> V.of_json (set "lower" bound unknown));
      reject "component_contract" (fun () -> V.of_json (set "upper" bound json)))
    [arr []; obj []; Json.Bool false; Json.int 0; str "unexpected"];
  reject "missing_field" (fun () -> V.of_json (obj (List.remove_assoc "reason" (Json.object_fields json))));
  reject "unknown_field" (fun () -> V.of_json (set "verified" (Json.Bool true) json));
  reject "duplicate_key" (fun () -> V.of_json (obj (("values", arr []) :: Json.object_fields json)));
  reject "nonfinite_number" (fun () -> V.of_json (set "lower" (Json.Float infinity) json));
  reject "invalid_type" (fun () -> V.of_json (set "values" (arr [Json.int 1]) json));
  reject "invalid_utf8" (fun () -> V.of_json (set "reason" (str "\255") json));
  let oversized = str (String.make (Limits.max_string_bytes + 1) 'x') in
  reject "component_contract_limit" (fun () -> V.of_json (set "reason" oversized json));
  let repeated = str (String.make Limits.max_string_bytes 'x') in
  reject "component_contract_limit" (fun () -> V.of_json (set "reason" (arr (List.init 9 (fun _ -> repeated))) json));
  let deep = List.fold_left (fun value _ -> arr [value]) Json.Null (List.init (Limits.max_depth + 1) Fun.id) in
  reject "component_contract_limit" (fun () -> V.of_json (set "reason" deep json));
  reject "component_contract_limit" (fun () -> V.of_json (set "values" (arr (List.init Limits.max_json_nodes (fun _ -> Json.Null))) json))

let normalize kind value = match kind with
  | "value_domain" -> V.to_json (V.of_json value)
  | "domain_check" -> C.Domain_check.to_json (C.Domain_check.of_json value)
  | "operating_domain" -> O.to_json (O.of_json value)
  | "port" -> P.to_json (P.of_json value)
  | _ -> failwith "Unknown component corpus record kind"
let algebra item =
  let input = get "input" item in
  let field key = get key input in
  match Json.string (get "operation" item) with
  | "domain_subset" -> C.domain_subset ~required:(V.of_json (field "required")) ~supported:(V.of_json (field "supported")) |> C.assessment_to_json
  | "operating_domain_subset" -> C.operating_domain_subset ~required:(O.of_json (field "required")) ~supported:(O.of_json (field "supported")) |> C.assessment_to_json
  | "ports_compatible" -> C.ports_compatible ~producer:(P.of_json (field "producer")) ~consumer:(P.of_json (field "consumer")) |> C.assessment_to_json
  | "canonical_synthetic_unit" -> C.canonical_synthetic_unit (T.of_json (field "dtype")) |> str
  | "synthetic_output_domain" ->
      let max_contacts = match field "max_contacts" with Json.Null -> None | value -> Some (N.of_json value) in
      let result = C.synthetic_output_domain ~operation:(C.synthetic_operation_of_string (Json.string (field "operator")))
          ~attributes:(field "attributes") ~inputs:(Json.array (field "inputs") |> List.map (fun value -> V.of_json value))
          ~dtype:(T.of_json (field "dtype")) ~initialization:(Json.boolean (field "initialization")) ?max_contacts () in
      Option.fold ~none:Json.Null ~some:V.to_json result
  | _ -> failwith "Unknown component algebra operation"
let read_json path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let length = in_channel_length channel in
      if length > Limits.max_request_bytes then failwith "Component corpus exceeds wire input byte bound";
      Json.parse (really_input_string channel length))
let corpus path =
  let document = read_json path in
  check (get "schema_version" document = str "biocompiler.component_contracts_conformance.v1") "Wrong component corpus schema";
  check (get "diagnostic_profile" document = str C.diagnostic_profile) "Wrong diagnostic profile";
  let coverage = get "coverage" document in
  let records = Json.array (get "records" document) and rejections = Json.array (get "rejections" document)
  and cases = Json.array (get "algebra" document) and witnesses = Json.array (get "diagnostic_witnesses" document) in
  let census name minimum items =
    check (List.length items >= minimum) ("Truncated component corpus: " ^ name);
    check (get name coverage = Json.int (List.length items)) ("Incorrect component census: " ^ name) in
  census "record_count" 30 records; census "rejection_count" 35 rejections;
  census "algebra_count" 77 cases; census "diagnostic_witness_count" 3 witnesses;
  let strings key items = List.map (fun item -> Json.string (get key item)) items |> List.sort_uniq String.compare in
  let declared key actual = check (get key coverage = arr (List.map str actual)) ("Wrong manifest: " ^ key) in
  let kinds = strings "record_kind" records in
  check (kinds = ["domain_check"; "operating_domain"; "port"; "value_domain"]) "Missing component records";
  declared "record_kinds" kinds;
  let operations = strings "operation" cases in
  check (operations = ["canonical_synthetic_unit"; "domain_subset"; "operating_domain_subset"; "ports_compatible"; "synthetic_output_domain"])
    "Missing algebra operation";
  declared "algebra_operations" operations;
  let inferred = List.filter (fun item -> get "operation" item = str "synthetic_output_domain") cases in
  let synthetic = List.map (get "input") inferred |> strings "operator" in
  check (synthetic = ["and"; "any_contact"; "compare"; "constant"; "held_for"; "input"; "memory"; "not"; "onset"; "or"; "output"; "pulse"; "select"])
    "Missing closed synthetic operation";
  declared "synthetic_operations" synthetic;
  let literals = List.filter (fun item -> get "evidence" item = str "independent_literal") cases in
  census "literal_algebra_count" 71 literals;
  let seen = Hashtbl.create 149 in
  List.iter (fun item -> let identity = Json.string (get "id" item) in
      check (not (Hashtbl.mem seen identity)) ("Duplicate component fixture " ^ identity); Hashtbl.add seen identity ()) (records @ rejections @ cases @ witnesses);
  let identities = records @ rejections @ cases |> List.map (fun item -> Json.string (get "id" item)) |> List.sort String.compare in
  check (Canonical.fingerprint (arr (List.map str identities)) = "1a961ee9bf62d6968054876d24813f559de96bb12fbe8945f8024fad27fb1c2e") "Changed or missing retained component case inventory";
  List.iter (fun item -> let result = normalize (Json.string (get "record_kind" item)) (get "input" item) in
      check (Canonical.encode result = Canonical.encode (get "normalized" item)) ("Record identity differs: " ^ Json.string (get "id" item));
      check (Canonical.fingerprint result = Json.string (get "fingerprint" item)) "Record fingerprint differs") records;
  List.iter (fun item -> reject (Json.string (get "expected_code" item)) (fun () -> normalize (Json.string (get "record_kind" item)) (get "input" item))) rejections;
  List.iter (fun item -> let result = algebra item in
      check (Canonical.encode result = Canonical.encode (get "expected" item)) ("Algebra differs: " ^ Json.string (get "id" item));
      check (Canonical.fingerprint result = Json.string (get "fingerprint" item)) "Algebra fingerprint differs") cases;
  List.iter (fun item -> check (Text.repr (Json.string (get "text" item)) = Json.string (get "expected_repr" item)) "Versioned diagnostic witness differs") witnesses;
  Printf.printf "component corpus: %d records, %d rejected records, %d algebra cases, %d diagnostic witnesses\n" (List.length records) (List.length rejections) (List.length cases) (List.length witnesses)
let () =
  match Array.to_list Sys.argv with
  | [_] -> literals (); text_literals (); raw_boundary_tests (); Printf.printf "component contract: %d literal checks\n" !checks
  | [_; path] -> corpus path; Printf.printf "component contract: %d corpus checks\n" !checks
  | _ -> failwith "Usage: test_component_contract.exe [component-contracts-v1.json]"

let () =
  let original = P.to_json (port ()) in
  let imported = P.of_json (obj (List.rev (Json.object_fields original))) in
  check (List.map fst (Json.object_fields (P.to_json imported)) =
    ["id";"direction";"meaning";"unit";"role";"scope";"compartment";"timing";
     "schema_version";"dtype";"initialization";"domain"])
    "Port document differs from the original ordered public recipe";
  check (Canonical.encode (P.to_json imported) = Canonical.encode original)
    "Port ordering changed validated interface fields"

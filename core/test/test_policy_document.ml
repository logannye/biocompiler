open Bioc_wire
module P = Bioc_domain.Policy_document
let require condition message = if not condition then failwith message
let obj value = Json.Object value
let str value = Json.String value
let field key value = Json.field key (Json.object_fields value)
let replace key replacement value = obj (List.map (fun (name, item) -> name, if key = name then replacement else item) (Json.object_fields value))
let add key item value = obj ((key, item) :: Json.object_fields value)
let remove key value = obj (List.remove_assoc key (Json.object_fields value))
let rejected label operation = match operation () with
  | _ -> failwith (label ^ ": intended rejection accepted")
  | exception Diagnostic.Error _ -> ()
let rejected_code label code operation = match operation () with
  | _ -> failwith (label ^ ": intended rejection accepted")
  | exception Diagnostic.Error diagnostic -> require (diagnostic.code = code)
      (label ^ ": expected " ^ code ^ ", received " ^ diagnostic.code)
let rejected_representation label operation = match operation () with
  | _ -> failwith (label ^ ": intended representation rejection accepted")
  | exception Diagnostic.Error diagnostic -> require (List.mem diagnostic.code ["policy_document"; "missing_field"])
      (label ^ ": wrong rejection stage " ^ diagnostic.code)
let empty_program = obj ["$type", str "PolicyProgram"; "id", str "literal";
    "semantics", obj ["$type", str "SemanticBundle"; "id", str "literal_bundle";
      "version", str "1"; "definitions", Json.Array []; "profile", str P.profile];
    "declarations", Json.Array []; "source_map", Json.Array []; "profile", str P.profile]
let unit scale = obj ["$type", str "Unit"; "id", str "second"; "dimension", str "time";
    "quantity_kind", str "duration"; "scale", str scale; "reference", Json.Null]
let quantity amount scale = obj ["$type", str "Quantity"; "amount", str amount; "unit", unit scale]
let with_clock amount scale =
  replace "declarations" (Json.Array [obj ["$type", str "Clock"; "id", str "clock";
    "basis", str "availability"; "resolution", quantity amount scale; "simultaneous", str "atomic_batch"]]) empty_program
let source_map = Json.Array [obj ["$type", str "SourceSpan"; "declaration_id", str "literal";
    "file", str "authoring.py"; "line", Json.int 7; "column", Json.int 2; "pattern", str "literal_example"]]

let representation_literals () =
  let value = P.of_json empty_program in
  require (P.kind value = P.Program && P.request value = None) "Program kind changed";
  require (Json.equal (P.to_json value) empty_program) "Program record roundtrip changed";
  require (P.declarations value = []) "Empty declarations gained an occurrence";
  require (List.length Bioc_domain.Policy_schema.records = 45) "Closed wire record census changed without review";
  let sourced = P.of_json (replace "source_map" source_map empty_program) in
  require (P.fingerprint value = P.fingerprint sourced) "Source map changed policy document identity";
  require (P.artifact_digest value <> P.artifact_digest sourced) "Artifact digest discarded source correspondence";
  require (P.document_digest (obj ["value", Json.int 1; "provenance", str "a"]) =
           P.document_digest (obj ["value", Json.int 1; "provenance", str "b"])) "Digest failed precise provenance exclusion";
  require (P.document_digest (obj ["value", Json.Array [Json.int 1; Json.int 2]]) <>
           P.document_digest (obj ["value", Json.Array [Json.int 2; Json.int 1]])) "Digest sorted semantic array order";
  List.iter (fun (label, document) -> rejected label (fun () -> P.of_json document)) [
    "extra field", add "callback" (str "import os") empty_program;
    "missing field", remove "source_map" empty_program;
    "wrong scalar", replace "id" (Json.int 1) empty_program;
    "raw float", replace "id" (Json.Float 1.) empty_program;
    "wrong record tag", replace "$type" (str "os.system") empty_program;
    "draft", add "holes" (Json.Array []) (replace "$type" (str "PolicyDraft") empty_program);
    "unknown profile", replace "profile" (str "other.profile") empty_program;
    "duplicate direct key", add "id" (str "second") empty_program;
    "wrong nested tag", replace "semantics" (replace "$type" (str "PolicyProgram") (field "semantics" empty_program)) empty_program;
  ];
  rejected "duplicate parsed key" (fun () -> Json.parse "{\"$type\":\"PolicyProgram\",\"$type\":\"PolicyProgram\"}");
  rejected "parsed raw float" (fun () -> P.of_json (Json.parse (Canonical.encode (replace "id" (Json.Float 1.) empty_program))));
  let clock = P.of_json (with_clock "0.1" "1e+0") in
  require ((List.hd (P.declarations clock)).kind = P.Clock) "Typed declaration kind lost";
  require ((List.hd (P.declarations clock)).path = "/declarations/0") "Declaration JSON pointer differs";
  require (Q.equal (P.exact_decimal "1e-3") (Q.make Z.one (Z.of_int 1000))) "Exact scale became floating point";
  require (Q.equal (P.exact_decimal "9007199254740993") (Q.of_bigint (Z.of_string "9007199254740993"))) "Large exact integer rounded";
  ignore (P.exact_decimal "1e1024");
  ignore (P.exact_decimal "1e-1024");
  List.iter (fun text -> rejected ("noncanonical quantity " ^ text) (fun () -> P.of_json (with_clock text "1")))
    ["-0"; "0.0"; "1.00"; "1e0"; "01"; "+1"; "NaN"; "Infinity"; "1_0"; "1e1025"; "1e-1025"];
  List.iter (fun text -> rejected ("invalid scale " ^ text) (fun () -> P.of_json (with_clock "1" text)))
    ["NaN"; "1_000"; "01"; "+1"; "1."; ".1"; "1e9999999999999999999999999"; "1e-1025"; String.make 257 '1'];
  ignore (P.of_json (with_clock "-0.01" "-1.25e+2"));
  rejected_code "oversized integer" "policy_document_limit" (fun () -> P.of_json (replace "id" (Json.Int (Z.pow (Z.of_int 10) 256)) empty_program));
  rejected_code "oversized string" "policy_document_limit" (fun () -> P.of_json (replace "id" (str (String.make 262145 'x')) empty_program));
  let rec nested count = if count = 0 then Json.Null else Json.Array [nested (count - 1)] in
  rejected_code "depth" "policy_document_limit" (fun () -> P.document_digest (nested 65));
  rejected_code "node census" "policy_document_limit" (fun () -> P.document_digest (Json.Array (List.init 100000 (fun _ -> Json.Null))));
  rejected_code "aggregate bytes" "policy_document_limit" (fun () -> P.document_digest (Json.Array (List.init 9 (fun _ -> str (String.make 262144 'x')))));
  let rec cyclic = Json.Array [cyclic] in
  rejected_code "cyclic values" "policy_document_limit" (fun () -> P.of_json cyclic);
  let rec spine = Json.Null :: spine in
  rejected_code "cyclic list" "policy_document_limit" (fun () -> P.of_json (Json.Array spine))

(* These literals exercise the two reachable record types absent from the
   eight teaching programs without attributing semantic validity to them. *)
let representation_extensions request =
  let clause = obj ["$type", str "ContractClause"; "kind", str "assumption";
    "description", str "Literal, unproved model premise"; "expression", Json.Null] in
  let program = field "program" request in
  let bundle = field "semantics" program in
  let definitions = Json.array (field "definitions" bundle) in
  let definitions = match definitions with
    | first :: rest -> replace "clauses" (Json.Array [clause]) first :: rest
    | [] -> failwith "Literal bundle unexpectedly empty" in
  let request = replace "program" (replace "semantics" (replace "definitions" (Json.Array definitions) bundle) program) request in
  let role = List.hd (Json.array (field "declarations" program)) in
  let pin = List.hd (Json.array (field "requires" role)) in
  let binding = obj ["$type", str "ImplementationBinding"; "id", str "literal_implementation";
    "version", str "1"; "operation", pin; "realization", pin;
    "chassis", Json.Array [str "illustrative_immune"]; "payload_formats", Json.Array [str "RNA"];
    "dependencies", Json.Array [pin]; "evidence", Json.Array []] in
  let implementations = replace "implementations" (Json.Array [binding]) (field "implementations" request) in
  let parameter = obj ["$type", str "Parameter"; "id", str "literal_parameter";
    "value_type", obj ["$type", str "TypeSpec"; "kind", str "integer"; "unit", Json.Null; "entity_kind", Json.Null];
    "value", Json.int 1; "lower", Json.Null; "upper", Json.Null; "selection", str "fixed"] in
  let program = field "program" request in
  let program = replace "declarations" (Json.Array (Json.array (field "declarations" program) @ [parameter])) program in
  replace "program" program (replace "implementations" implementations request)

let mutation_census documents =
  let seen = Hashtbl.create 45 in
  let rec mutate_first tag transform = function
    | Json.Object fields as value when List.assoc_opt "$type" fields = Some (str tag) -> transform value
    | Json.Object fields -> obj (List.map (fun (key, value) -> key, mutate_first tag transform value) fields)
    | Json.Array values -> Json.Array (List.map (mutate_first tag transform) values)
    | value -> value in
  let rec visit document = function
    | Json.Object fields as record ->
        (match List.assoc_opt "$type" fields with
         | Some (Json.String tag) when not (Hashtbl.mem seen tag) ->
             Hashtbl.add seen tag ();
             List.iter (fun (label, transform) ->
               rejected_representation (tag ^ " " ^ label)
                 (fun () -> P.of_json (mutate_first tag transform document))) [
               "extra field", add "unreviewed_callback" (str "ignored");
               "missing tag", remove "$type";
               "incorrect tag", replace "$type" (str "Executable")];
             let key = List.find (fun (key, _) -> key <> "$type") fields |> fst in
             rejected_representation (tag ^ " missing member")
               (fun () -> P.of_json (mutate_first tag (remove key) document));
             ignore record
         | _ -> ());
        List.iter (fun (_, value) -> visit document value) fields
    | Json.Array values -> List.iter (visit document) values
    | _ -> () in
  List.iter (fun document -> ignore (P.of_json document); visit document document) documents;
  require (Hashtbl.length seen = 41) "Every frozen-document-reachable record kind needs a rejection mutation";
  Printf.printf "Policy representation mutations: %d reachable record kinds\n" (Hashtbl.length seen)

let read_file path =
  let input = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in input) (fun () -> really_input_string input (in_channel_length input))

let corpus path =
  let corpus = Json.parse (read_file path) in
  require (field "fixture_version" corpus = str "biocompiler.policy_native_literals.v0.1") "Wrong policy literal fixture";
  let cases = Json.array (field "cases" corpus) in
  require (List.length cases = 24) "Expected eight programs, requests and submissions";
  List.iter (fun case ->
    let document = field "document" case in
    let label = Json.string (field "name" case) ^ ":" ^ Json.string (field "kind" case) in
    let parsed = P.of_json document in
    require (Json.equal (P.to_json parsed) document) (label ^ " lost frozen fields or order");
    require (P.fingerprint parsed = Json.string (field "fingerprint" case)) (label ^ " document fingerprint differs from frozen Python golden");
    require (P.artifact_digest parsed = Json.string (field "artifact_digest" case)) (label ^ " complete artifact digest differs from frozen Python golden");
    require (P.document_digest document = Json.string (field "document_digest" case)) (label ^ " top-level document digest differs from frozen Python golden");
    let declarations = Json.array (field "declarations" (P.program parsed)) in
    require (List.length declarations = List.length (P.declarations parsed)) (label ^ " declaration occurrences lost");
    List.iter2 (fun value (declaration : P.declaration) ->
      require (Json.equal value declaration.value && field "id" value = str declaration.id) (label ^ " declaration order or identity changed"))
      declarations (P.declarations parsed);
    (match P.kind parsed with
     | P.Submission ->
         List.iter (fun key -> rejected (label ^ " bad " ^ key) (fun () -> P.of_json (replace key (str (String.make 64 '0')) document)))
           ["document_digest"; "program_digest"];
         List.iter (fun key ->
           let pin = field key document in
           rejected (label ^ " bad pin " ^ key) (fun () -> P.of_json (replace key (replace "digest" (str (String.make 64 '0')) pin) document)))
           ["semantic_bundle"; "implementation_catalog"];
         rejected (label ^ " missing dependencies") (fun () -> P.of_json (replace "dependencies" (Json.Array []) document));
         rejected (label ^ " unknown semantics claim") (fun () -> P.of_json (replace "semantic_status" (str "proved") document));
         let dependencies = Json.array (field "dependencies" document) in
         rejected (label ^ " dependency order") (fun () -> P.of_json (replace "dependencies" (Json.Array (List.rev dependencies)) document))
     | _ -> ())) cases;
  let documents = List.map (field "document") cases in
  let request = List.find (fun value -> field "$type" value = str "BuildRequest") documents in
  let program = field "program" request in
  let declarations = Json.array (field "declarations" program) in
  let role = List.hd declarations in
  let reference = List.hd (Json.array (field "requires" role)) in
  List.iter (fun blank ->
    List.iter (fun key ->
      let changed_role = replace "requires" (Json.Array [replace key (str blank) reference]) role in
      let changed_program = replace "declarations" (Json.Array (changed_role :: List.tl declarations)) program in
      rejected_code ("blank DefinitionRef " ^ key) "policy_document"
        (fun () -> P.of_json (replace "program" changed_program request))) ["id";"version"];
    let assurance = replace "assumptions" (Json.Array [str blank]) (field "assurance" request) in
    rejected_code "blank request assumption" "policy_document" (fun () -> P.of_json (replace "assurance" assurance request));
    let assumption_declarations = List.map (fun declaration ->
      if field "$type" declaration = str "Requirement" then
        replace "kind" (str "assumption") (replace "description" (str blank) declaration)
      else declaration) declarations in
    rejected_code "blank assumption requirement" "policy_document"
      (fun () -> P.of_json (replace "program" (replace "declarations" (Json.Array assumption_declarations) program) request));
    let bundle = field "semantics" program in
    let definitions = Json.array (field "definitions" bundle) in
    let definition = replace "assumptions" (Json.Array [str blank]) (List.hd definitions) in
    let changed_bundle = replace "definitions" (Json.Array (definition :: List.tl definitions)) bundle in
    rejected_code "blank definition assumption" "policy_document"
      (fun () -> P.of_json (replace "program" (replace "semantics" changed_bundle program) request)))
    [""; " \t\n"; "\194\160"; "\226\128\131"];
  let extended = representation_extensions request in
  let extended_parsed = P.of_json extended in
  require (List.exists (fun (declaration : P.declaration) -> declaration.kind = P.Parameter) (P.declarations extended_parsed))
    "Parameter declaration kind was lost";
  mutation_census (extended :: documents);
  Printf.printf "Policy frozen document corpus: %d records passed\n" (List.length cases)

let () =
  representation_literals ();
  require (Array.length Sys.argv = 2) "Supply the pinned policy_documents_v01.json fixture path";
  corpus Sys.argv.(1)

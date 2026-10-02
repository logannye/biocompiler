open Bioc_wire
open Bioc_domain
module Check = Bioc_checker.Transition_check
module G = Molecule_coordinates
module C = Molecule_chemistry
module T = Molecular_transition
module A = Construction_artifact
let require value message = if not value then failwith message
let str value = Json.String value
let obj value = Json.Object value
let field key value = Json.field key (Json.object_fields value)
let rejected label code run = match run () with
  | _ -> failwith (label ^ ": intended failure accepted")
  | exception Diagnostic.Error error -> require (error.code=code) (label ^ ": expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message)
let space id length = G.Space.of_json (obj ["schema_version",str "biocompiler.molecule_coordinate_space.v0.1";"id",str id;"alphabet",str "RNA";
  "length",Json.int length;"topology",str "linear";"axis",str "5prime_to_3prime"])
let span start stop = G.Span.of_json (obj ["schema_version",str "biocompiler.molecule_index_span.v0.1";"start",Json.int start;"end",Json.int stop])
let path space spans = G.Path.of_json (obj ["schema_version",str "biocompiler.molecule_coordinate_path.v0.1";"space_id",str (G.Space_id.to_string (G.Space.id space));
  "spans",Json.Array (List.map G.Span.to_json spans);"strand",str "+"])
let literals () =
  let provenance=Molecular_record.Provenance.make ~status:Molecular_record.Provenance.Unknown ~authority:[] ~locator:None ~reason:"Literal unresolved transition." in
  let claim=C.Claim.make ~status:C.Unknown ~identity:None ~provenance in
  let chemistry=C.make ~cap:claim ~start_end:claim ~finish_end:claim ~modifications:[] ~modification_inventory_status:C.Unknown
    ~modification_inventory_provenance:provenance ~terminal_tail:(C.Tail.make ~status:C.Unknown ~placement:None ~length:None ~path:None ~provenance) in
  let source_space=space "source.space" 1 and output_space=space "output.space" 1 in
  let derived=A.Derived_segment.make ~destination:(span 0 1) ~source_id:"x" ~source_path:(path source_space [span 0 1]) ~rule:A.Derived_segment.Copy in
  let value=A.Value.make ~id:"source" ~space:source_space ~sequence:"A" ~chemistry ~features:[] ~segments:[derived] ~step_id:"literal"
    ~sequence_extent:C.Complete ~consumed:[] in
  let source=Check.Input.of_value value in
  require (Check.Input.sequence source="A" && Check.Input.features source=[] && Check.Input.sequence_extent source=C.Complete
    && G.Space.fingerprint (Check.Input.space source)=G.Space.fingerprint source_space
    && C.fingerprint (Check.Input.chemistry source)=C.fingerprint chemistry) "Typed transition input lost authority";
  let transition=T.Chemistry.make ~mode:T.Chemistry.Exact_inheritance ~output:None ~dispositions:[] ~provenance
  and features=T.Feature.make ~dispositions:[] ~added:[] ~provenance in
  let run ?budget ?(inputs=["x",source]) ?(derivation=[derived]) sequence =
    Check.resolve ?budget transition features ~inputs ~output_sequence:sequence ~output_space ~derivation ~sequence_extent:C.Complete in
  let expected=obj ["chemistry",C.to_json chemistry;"features",Json.Array [];"diagnostics",Json.Array [];
    "unsupported",Json.Array [str "unknown_output_chemistry: nominal chemistry remains incomplete"]] in
  let actual=run ~budget:(Check.make_budget ~max_work:10 ()) "A" in
  require (Json.equal (Check.to_json actual) expected && Check.diagnostics actual=[] && Check.features actual=[]
    && Check.chemistry actual<>None && Check.unsupported actual=["unknown_output_chemistry: nominal chemistry remains incomplete"])
    "Independent unknown-chemistry literal differs";
  rejected "one-below exact native work" "transition_resource_limit" (fun () -> run ~budget:(Check.make_budget ~max_work:9 ()) "A");
  let shared=Check.make_budget ~max_work:20 () in
  ignore (run ~budget:shared "A"); ignore (run ~budget:shared "A");
  rejected "cumulative shared work" "transition_resource_limit" (fun () -> run ~budget:shared "A");
  rejected "negative work" "transition_resource_limit" (fun () -> Check.make_budget ~max_work:(-1) ());
  require (Check.resource_profile="biocompiler.transition_check.resources.v1" && Check.default_max_work=10_000_000
    && Check.max_projected_residues=100_000 && Check.max_derivation_segments=4096) "Transition resource profile changed";
  let empty=run ~budget:(Check.make_budget ~max_work:1 ()) ~inputs:[] "A" in
  require (Json.equal (Check.to_json empty) (obj ["chemistry",Json.Null;"features",Json.Array [];"diagnostics",Json.Array [str "transition_derivation: Expected bounded participating source values."];"unsupported",Json.Array []])) "Independent missing-source diagnostic changed";
  let changed=run "C" in
  require (Check.chemistry changed=None && Check.diagnostics changed=["chemistry_exact_inheritance: Exact chemistry inheritance requires unchanged spelling, alphabet and topology."])
    "Changed spelling inherited chemistry";
  let rec inputs=("x",source)::inputs in
  require (Check.diagnostics (run ~inputs "A")=["transition_derivation: Expected bounded participating source values."]) "Cyclic native inputs not bounded";
  let rec derivation=derived::derivation in
  require (Check.diagnostics (run ~derivation "A")=["transition_derivation: Invalid derivation segment inventory."]) "Cyclic native derivation not bounded";
  print_endline "transition checker literals: exact native shared work boundary, independent unresolved results and cyclic input bounds passed"
let rec expand = function
  | Json.Object ["__repeat_ascii__",count] ->
      let count=Z.to_int (Json.integer count) in require (count>=0 && count<=1_000_000) "Invalid runtime spelling recipe"; str (String.make count 'A')
  | Json.Object ["__repeat_segments__",recipe] ->
      let count=Z.to_int (Json.integer (field "count" recipe)) and width=Z.to_int (Json.integer (field "width" recipe)) in
      require (count>=0 && count<=4097 && List.mem width [1;2]) "Invalid runtime derivation recipe";
      let template=field "template" recipe in
      Json.Array (List.init count (fun index ->
        let destination=obj ["schema_version",str "biocompiler.molecule_index_span.v0.1";"start",Json.int (index*width);"end",Json.int ((index+1)*width)] in
        obj (("destination",destination)::List.remove_assoc "destination" (Json.object_fields template))))
  | Json.Object fields -> obj (List.map (fun (key,value) -> key,expand value) fields)
  | Json.Array values -> Json.Array (List.map expand values)
  | value -> value
let decode raw =
  let transition=T.Chemistry.of_json (field "chemistry_transition" raw) and features=T.Feature.of_json (field "feature_transition" raw) in
  let inputs=Json.array (field "inputs" raw) |> List.map (fun item ->
    let input=match Json.string (field "kind" item) with
      | "molecule" -> Molecule.of_json (field "value" item) |> Check.Input.of_molecule
      | "value" -> A.Value.of_json (field "value" item) |> Check.Input.of_value
      | _ -> failwith "Unknown transition input family" in Json.string (field "id" item),input) in
  let output_space=G.Space.of_json (field "output_space" raw) and output_sequence=Json.string (field "output_sequence" raw) in
  let derivation=Json.array (field "derivation" raw) |> List.map A.Derived_segment.of_json in
  let sequence_extent=match Json.string (field "sequence_extent" raw) with "complete" -> C.Complete | "exact_core" -> C.Exact_core | _ -> failwith "Unknown fixture extent" in
  fun () -> Check.resolve transition features ~inputs ~output_sequence ~output_space ~derivation ~sequence_extent
let read_json path =
  require (not (Filename.is_relative path)) "Required transition corpus path must be absolute";
  let channel=open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size=in_channel_length channel in require (size<=Limits.max_request_bytes) "Transition corpus read bound"; Json.parse (really_input_string channel size))
let retained path =
  let corpus=read_json path in
  require (field "schema_version" corpus=str "biocompiler.transition_check_conformance.v1") "Wrong transition corpus schema";
  let cases=Json.array (field "cases" corpus) and negatives=Json.array (field "parser_rejections" corpus)
  and excluded=Json.array (field "typed_unrepresentable" corpus) and runtime=Json.array (field "runtime_cases" corpus) in
  require (List.length cases=125 && List.length negatives=6 && List.length excluded=1 && List.length runtime=11) "Transition corpus census changed";
  let sorted keys cases = List.sort (fun left right -> String.compare (Json.string (field "id" left)) (Json.string (field "id" right))) cases
    |> List.map (fun item -> match keys with [key] -> field key item | _ -> Json.Array (List.map (fun key -> field key item) keys)) |> fun values -> Json.Array values in
  let inventory=obj ["cases",sorted ["id"] cases;"parser_rejections",sorted ["id";"expected_code"] negatives;
    "typed_unrepresentable",sorted ["id"] excluded;"runtime_cases",sorted ["id"] runtime] in
  let expected_inventory="33f2d16cb3d4e03c33fe3b1e4d0ee5fbae0a075046bda8176c9b789bd56f85b7" in
  require (Canonical.fingerprint inventory=expected_inventory && field "inventory_sha256" corpus=str expected_inventory) "Transition case or intended diagnostic inventory changed";
  List.iter (fun (key,expected) -> require (Canonical.fingerprint (field key corpus)=expected) (key ^ ": independent transition scope/expectations changed"))
    ["coverage","34f4b4468d4b86036468f95a2fa61310d74cb7fdb9789136b0325c9533edde06";
     "literal_expectations","c9145f5b6b5cca12c99692a20545ed0421eb3545fd6c142224898b36c2c3cc50";
     "runtime_cases","655dc74a401a932e983e1580f046fcb83de0a4095236c25da5a204c692da16c5";
     "typed_unrepresentable","4a02b420a6f60dd2c9680b3b65f6959739dd80cd903a23dbfbc7fe471b2c8f68"];
  let ids=List.map (fun item -> Json.string (field "id" item)) (cases @ negatives @ excluded @ runtime) in
  require (List.length ids=List.length (List.sort_uniq String.compare ids)) "Duplicate transition fixture identity";
  let documents=field "documents" corpus in
  List.iter (fun (digest,raw) -> require (Canonical.fingerprint raw=digest) "Transition document pin changed") (Json.object_fields documents);
  let document case=field (Json.string (field "document_id" case)) documents in
  let verify case raw =
    let run=decode raw in
    let actual=Check.to_json (run ()) in
    require (Json.equal actual (field "expected" case)) (Json.string (field "id" case) ^ ": complete transition result differs\nexpected=" ^ Canonical.encode (field "expected" case) ^ "\nactual=" ^ Canonical.encode actual);
    require (str (Canonical.fingerprint actual)=field "fingerprint" case) "Transition result identity differs" in
  List.iter (fun case -> verify case (document case)) cases;
  List.iter (fun case ->
      let raw=document case in
      let _prepared=decode (obj (("derivation",Json.Array [])::List.remove_assoc "derivation" (Json.object_fields raw))) in
      rejected (Json.string (field "id" case)) (Json.string (field "expected_code" case))
        (fun () -> Json.array (field "derivation" raw) |> List.map A.Derived_segment.of_json)) negatives;
  List.iter (fun case -> verify case (expand (field "template" case))) runtime;
  List.iter (fun item ->
    let case=List.find (fun case -> field "id" case=field "id" item) cases in
    let run=decode (document case) in
    require (Json.equal (Check.to_json (run ())) (field "expected" item)) "Independent complete transition literal differs") (Json.array (field "literal_expectations" corpus));
  Printf.printf "transition checker: %d full resolutions, %d domain failures, %d runtime projection/geometry boundaries, three independent literals; one foreign malformed Python object excluded by typed Input construction\n" (List.length cases) (List.length negatives) (List.length runtime)
let () = match Array.to_list Sys.argv with
  | [_] -> literals ()
  | [_;path] -> literals (); retained path
  | _ -> failwith "Usage: test_transition_check.exe [<absolute-transition-check-v1.json>]"

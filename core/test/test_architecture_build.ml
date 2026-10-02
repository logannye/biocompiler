open Bioc_wire
open Bioc_domain
module B = Architecture_build
module A = Architecture_assessment
module C = Construction_build
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let field name value = Json.field name (Json.object_fields value)
let require condition message = if not condition then failwith message
let checks = ref 0
let rejected name code operation =
  incr checks;
  match operation () with
  | _ -> failwith (name ^ " unexpectedly accepted")
  | exception Diagnostic.Error diagnostic -> require (diagnostic.code = code) (name ^ ": " ^ diagnostic.code ^ " expected " ^ code)
let gap () = B.Gap.make ~category:B.Gap.Missing_implementation ~code:"declared_gap" ~requirement_ids:["r"]
    ~candidate_ids:[] ~message:"Missing declared realization." ~conflict_set:[]
let realization id = B.Requirement_realization.make ~id ~source_node_ids:["node"] ~refinement_ids:[]
    ~status:B.Requirement_realization.Unresolved ~assumptions:[] ~reasons:["Needs a realization."]
let literal_gap () = obj ["schema_version",str "biocompiler.architecture_gap.v0.1";"category",str "missing_implementation";
    "code",str "declared_gap";"requirement_ids",arr [str "r"];"candidate_ids",arr [];
    "message",str "Missing declared realization.";"conflict_set",arr []]
let literal_realization () = obj ["schema_version",str "biocompiler.requirement_realization.v0.1";"id",str "r";
    "source_node_ids",arr [str "node"];"refinement_ids",arr [];"status",str "unresolved";
    "assumptions",arr [];"reasons",arr [str "Needs a realization."]]
let plan ?(placements=[]) ?(ledger=[realization "r"]) ?(selected=["a"]) ?(instances=[]) () =
  B.Plan.make ~selected_refinement_ids:selected ~ledger ~placements ~helpers:[] ~channels:[] ~control_domains:[]
    ~assumptions:[] ~instances ~availability:[]
let inspect kind raw = match kind with
  | "construction_build" -> C.to_json (C.of_json raw)
  | "gap" -> B.Gap.to_json (B.Gap.of_json raw)
  | "realization" -> B.Requirement_realization.to_json (B.Requirement_realization.of_json raw)
  | "plan" -> B.Plan.to_json (B.Plan.of_json raw)
  | "alternative" -> B.Alternative.to_json (B.Alternative.of_json raw)
  | "build" -> B.to_json (B.of_json raw)
  | "export" -> B.Export.to_json (B.Export.of_json raw)
  | "assessment" -> A.to_json (A.of_json raw)
  | _ -> failwith "Unknown architecture build fixture kind"
let literals () =
  require (Json.equal (B.Gap.to_json (gap ())) (literal_gap ())) "Literal gap differs";
  require (Json.equal (B.Requirement_realization.to_json (realization "r")) (literal_realization ())) "Literal realization differs";
  require (List.map B.Requirement_realization.id (B.Plan.ledger (plan ~ledger:[realization "z";realization "a"] ())) = ["z";"a"]) "Ledger order changed";
  require (B.Alternative.eligible (B.Alternative.make ~refinement_ids:[] ~gaps:[])) "Empty historical alternative differs";
  ignore (B.Alternative.make ~refinement_ids:[] ~gaps:[gap ();gap ()]);
  ignore (B.Export.make ~fasta:">" ~manifest:(obj []));
  rejected "FASTA absent prefix" "invalid_architecture_build" (fun () -> B.Export.make ~fasta:"AU" ~manifest:(obj []));
  rejected "implemented without identity" "invalid_architecture_build" (fun () ->
      B.Requirement_realization.make ~id:"r" ~source_node_ids:[] ~refinement_ids:[] ~status:B.Requirement_realization.Implemented ~assumptions:[] ~reasons:[]);
  ignore (plan ~placements:(List.init 4096 (fun _ -> obj [])) ());
  rejected "placement inventory bound" "molecular_resource_limit" (fun () -> plan ~placements:(List.init 4097 (fun _ -> obj [])) ());
  ignore (plan ~selected:(List.init 256 (fun i -> string_of_int i)) ());
  rejected "selection bound" "molecular_resource_limit" (fun () -> plan ~selected:(List.init 257 (fun i -> string_of_int i)) ());
  rejected "duplicate ledger" "invalid_architecture_build" (fun () -> plan ~ledger:[realization "r";realization "r"] ());
  let report outcome diagnostics = A.make ~request_fingerprint:(String.make 64 'a') ~build_fingerprint:(String.make 64 'b')
      ~outcome ~translation_complete:false ~construction_complete:false ~diagnostics ~unresolved:["open"] ~assumptions:[" a ";"b\n"] in
  let historical = report A.Pass [] in
  require (A.passed historical && not (A.translation_complete historical) && A.unresolved historical = ["open"])
    "Historical PASS was improperly upgraded to translation completion";
  ignore (report A.Fail [gap ();gap ()]);
  rejected "PASS contradiction" "invalid_architecture_assessment" (fun () -> report A.Pass [gap ()]);
  let rec cycle = Json.Array [cycle] in
  let rec spine = obj [] :: spine in
  List.iter (fun kind ->
      rejected (kind ^ " cyclic tree") "molecular_cycle" (fun () -> inspect kind cycle);
      rejected (kind ^ " cyclic spine") "molecular_resource_limit" (fun () -> inspect kind (arr spine));
      rejected (kind ^ " duplicate key") "duplicate_key" (fun () -> inspect kind (obj ["x",Json.Null;"x",Json.Null]));
      rejected (kind ^ " nonfinite") "nonfinite_number" (fun () -> inspect kind (obj ["x",Json.Float nan])))
    ["construction_build";"gap";"realization";"plan";"alternative";"build";"export";"assessment"];
  Printf.printf "architecture build: independent literals and %d rejection/resource checks passed\n" !checks
let rec edit raw path replacement = match path with
  | [] -> (match replacement with Some value -> value | None -> failwith "Cannot delete root")
  | Json.String key :: tail ->
      let fields = Json.object_fields raw in
      if tail = [] then obj (match replacement with Some value -> (key,value)::List.remove_assoc key fields | None -> List.remove_assoc key fields)
      else obj (List.map (fun (name,value) -> name,if name=key then edit value tail replacement else value) fields)
  | Json.Int index :: tail ->
      let index=Z.to_int index and values=Json.array raw in
      require (index >= 0 && index < List.length values) "Invalid edit index";
      arr (List.mapi (fun i value -> if i=index then (if tail=[] && Option.is_none replacement then None else Some (edit value tail replacement)) else Some value) values |> List.filter_map Fun.id)
  | _ -> failwith "Invalid edit path"
let edited raw edits = List.fold_left (fun raw change ->
    let fields = Json.object_fields change in
    let remove = List.assoc_opt "remove" fields = Some (Json.Bool true) in
    edit raw (Json.array (field "path" change)) (if remove then None else Some (field "value" change))) raw (Json.array edits)
let read path =
  require (not (Filename.is_relative path)) "Architecture build corpus requires absolute path";
  let ch=open_in_bin path in Fun.protect ~finally:(fun () -> close_in_noerr ch) (fun () ->
      let bytes=in_channel_length ch in require (bytes <= Limits.max_request_bytes) "Architecture fixture byte bound";
      Json.parse (really_input_string ch bytes))
let corpus path =
  let raw=read path in
  require (field "schema_version" raw = str "biocompiler.architecture_build_conformance.v1") "Architecture build corpus schema";
  let digest="1b93ea91ecb5f6fc35bce14bd9d0ba878c3f96ab9f343f5400d0c4b6f58525bd" in
  let inventory=obj (List.map (fun key -> key,field key raw) ["schema_version";"records";"rejections";"literal_expectations";"coverage"]) in
  require (Canonical.fingerprint inventory=digest && field "inventory_fingerprint" raw=str digest) "Architecture full inventory changed";
  let docs=Json.object_fields (field "documents" raw) and records=Json.array (field "records" raw) and negatives=Json.array (field "rejections" raw) in
  require ((List.length docs,List.length records,List.length negatives)=(50,48,117)) "Incomplete architecture build campaign";
  List.iter (fun (identity,document) -> require (Canonical.fingerprint document=identity) "Architecture document changed") docs;
  let find case key = List.assoc (Json.string (field key case)) docs in
  List.iter (fun case ->
      let input=edited (find case "document") (field "edits" case) in
      let observed=inspect (Json.string (field "kind" case)) input in
      require (Json.equal observed (find case "normalized")) (Json.string (field "id" case) ^ " complete record differs")) records;
  List.iter (fun case -> rejected (Json.string (field "id" case)) (Json.string (field "expected_code" case)) (fun () ->
      inspect (Json.string (field "kind" case)) (edited (find case "document") (field "edits" case)))) negatives;
  List.iter (fun case -> if field "kind" case = str "construction_build" then (
      let v=C.of_json (find case "normalized") in
      let rebuilt=C.make ~request:(C.request v) ~candidate:(C.candidate v) ~assessment:(C.assessment v) in
      require (C.fingerprint v=C.fingerprint rebuilt) "Construction historical make changed authority")) records;
  let literals=field "literal_expectations" raw in
  require (Json.equal (field "gap" literals) (literal_gap ()) && Json.equal (field "realization" literals) (literal_realization ())) "Independent literals changed";
  Printf.printf "architecture build corpus: 48 complete records, 117 intended rejections and all three original case B builds passed\n"
let () = match Array.to_list Sys.argv with [_] -> literals () | [_;path] -> literals ();corpus path | _ -> failwith "Expected optional absolute corpus path"

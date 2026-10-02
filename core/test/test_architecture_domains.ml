open Bioc_wire
module T = Bioc_domain.Payload_template
module R = Bioc_domain.Architecture_refinement
module Q = Bioc_domain.Architecture_request
module A = Bioc_domain.Architecture_contract
module C = Bioc_domain.Construction
module M = Bioc_domain.Molecular_record
module N = Bioc_domain.Molecule
module G = Bioc_domain.Molecule_coordinates
module H = Bioc_domain.Molecule_chemistry
module B = Bioc_domain.Behavior
module I = Bioc_domain.Identity
module Component = Bioc_domain.Component
let checks = ref 0
let require condition message = incr checks; if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let field key value = Json.field key (Json.object_fields value)
let rejected label code operation =
  incr checks;
  match operation () with
  | _ -> failwith (label ^ ": intended rejection accepted")
  | exception Diagnostic.Error diagnostic -> if diagnostic.code <> code then
      failwith (label ^ ": expected " ^ code ^ ", got " ^ diagnostic.code ^ ": " ^ diagnostic.message)
let provenance = M.Provenance.make ~status:M.Provenance.Unknown ~authority:[] ~locator:None ~reason:"Independent artificial native declaration."
let space id length = G.Space.of_json (obj ["schema_version",str "biocompiler.molecule_coordinate_space.v0.1";"id",str id;
    "alphabet",str "RNA";"length",Json.int length;"topology",str "linear";"axis",str "5prime_to_3prime"])
let path frame first last = G.Path.of_json (obj ["schema_version",str "biocompiler.molecule_coordinate_path.v0.1";"space_id",str frame;
    "spans",arr [obj ["schema_version",str "biocompiler.molecule_index_span.v0.1";"start",Json.int first;"end",Json.int last]];"strand",str "+"])
let molecule id length =
  let destination = space (id ^ ".frame") length and source = space (id ^ ".original") length in
  let unknown = H.Claim.make ~status:H.Unknown ~identity:None ~provenance in
  let tail = H.Tail.make ~status:H.Unknown ~placement:None ~length:None ~path:None ~provenance in
  let chemistry = H.make ~cap:unknown ~start_end:unknown ~finish_end:unknown ~modifications:[]
      ~modification_inventory_status:H.Unknown ~modification_inventory_provenance:provenance ~terminal_tail:tail in
  let origin = N.Assembly_origin.make ~id:"origin" ~destination:(path (id ^ ".frame") 0 length)
      ~source_space:source ~source_path:(path (id ^ ".original") 0 length) ~provenance in
  N.make ~id ~form:N.Delivered_rna ~space:destination ~sequence:(String.make length 'A') ~sequence_extent:H.Complete
    ~coding_status:N.Noncoding ~assembly:[origin] ~features:[] ~chemistry ~provenance
let source id length = C.Root_source.make ~id ~molecule:(molecule id length) ~provenance
let output ?(reference = C.Value_ref.make ~kind:C.Value_ref.Root ~id:"source") () =
  C.Output_member.make ~id:"payload" ~value:reference ~space_id:"payload.final" ~form:N.Delivered_rna
    ~sequence_extent:H.Complete ~coding_status:N.Noncoding ~provenance
let required ?(role = "role") ?(category = C.Member_requirement.Delivered_helper) () =
  C.Member_requirement.make ~id:"required" ~category ~subject:(C.Member_requirement.Materialized "payload")
    ~roles:[C.Role.make ~id:role ~role:"cell" ~purpose:(C.Member_requirement.category_purpose category) ~compartment:"cytoplasm"]
let template () = T.make ~id:"template" ~sources:[source "source" 2] ~steps:[] ~output_members:[output ()] ~requirements:[required ()] ()
let primitive_behavior () =
  let node = obj ["id",str "cell";"kind",str "role";"inputs",arr [];
      "attributes",obj ["name",str "cell";"cell_type",str "literal";"engineering",str "in_vivo"];
      "data_type",Json.Null;"role",Json.Null;"source",Json.Null;"contact_bound",Json.Bool false;"requirement_ids",arr []] in
  B.of_json (obj ["schema_version",str "biocompiler.behavior.v0.1";"name",str "literal";"nodes",arr [node];"roots",arr [str "cell"];
      "source_fingerprint",str (String.make 64 '0');"requirements",arr [];"source_links",obj ["cell",arr [str "cell"]];
      "policies",B.execution_policies B.V0_1;"parameter_bindings",obj []])
let primitive_component () =
  let pin = Component.Pinned_identity.make ~kind:Component.Pinned_identity.Model ~id:"model" ~version:"1" ~content_fingerprint:(String.make 64 'a') in
  Component.make ~id:"component" ~version:"1" ~classification:Component.Modeled_component ~implementation_role:"declared"
    ~supported_targets:["human"] ~ports:[] ~supported_domain:(Bioc_domain.Component_contract.Operating_domain.make []) ~identities:[pin]
    ~assumptions:[] ~guarantees:[] ~evidence:[] ~parameters:[] ~dependencies:[] ~capabilities:[] ~resources:[] ~reference_metadata:None ~synthetic_model:None
let refinement ?match_policy ?(source_bindings = [I.Node.of_string "cell",I.Node.of_string "source-role"]) ?(helpers = []) () =
  let placement = A.Placement.make ~id:"placement" ~template_id:"template" ~member_id:"payload" ~recipient_role:(I.Role.of_string "cell")
      ~compartment:"cytoplasm" ~delivery_group:"group" in
  let binding = A.Binding.make ~id:"binding" ~behavior_node_ids:[I.Node.of_string "cell"] ~component_ids:[I.Component.of_string "component"]
      ~template_ids:["template"] ~placement_ids:["placement"] in
  R.make ?match_policy ~id:"refinement" ~version:"1" ~behavior:(primitive_behavior ()) ~source_bindings ~owned_node_ids:[I.Node.of_string "cell"]
    ~components:[primitive_component ()] ~templates:[template ()] ~bindings:[binding] ~placements:[placement] ~assumptions:["Declared only."] ~helpers ()
let budget_literals () =
  let exact_sources = [source "source" 500_000; source "unused" 500_000] in
  let exact = T.make ~id:"exact" ~sources:exact_sources ~steps:[] ~output_members:[output ()] ~requirements:[required ()] () in
  require (List.fold_left (fun n s -> n + String.length (N.sequence (C.Root_source.molecule s))) 0 (T.sources exact) = 1_000_000)
    "Exact aggregate source residue boundary rejected";
  rejected "aggregate source residue overflow" "invalid_payload_template" (fun () -> T.make ~id:"overflow"
      ~sources:[List.hd exact_sources;source "unused" 500_001] ~steps:[] ~output_members:[output ()] ~requirements:[required ()] ());
  let port id = C.Product_port.make ~id ~space_id:(id ^ ".frame") ~alphabet:G.Rna ~topology:G.Linear
      ~chemistry_transition:(Bioc_domain.Molecular_transition.Chemistry.make ~mode:Bioc_domain.Molecular_transition.Chemistry.Exact_inheritance ~output:None ~dispositions:[] ~provenance)
      ~feature_transition:(Bioc_domain.Molecular_transition.Feature.make ~dispositions:[] ~added:[] ~provenance) in
  let selection kind id = C.Selection.make (C.Value_ref.make ~kind ~id) in
  let previous = ref (C.Value_ref.Root,"source","source.frame") and steps = ref [] in
  for index = 0 to 84 do
    let kind,id,frame = !previous in
    let prefix = "step" ^ string_of_int index in
    let a = prefix ^ ".a" and b = prefix ^ ".b" and joined = prefix ^ ".joined" in
    let products = [C.Processing_product.make ~port_id:a ~path:(path frame 0 1);C.Processing_product.make ~port_id:b ~path:(path frame 1 2)] in
    let cleavage = C.Transform_step.make ~id:(prefix ^ ".split")
        ~operation:(C.Operation.make (C.Operation.Rna_cleavage {input=selection kind id;products})) ~ports:[port a;port b] ~assumptions:[] ~provenance in
    let joining = C.Transform_step.make ~id:(prefix ^ ".join")
        ~operation:(C.Operation.make (C.Operation.Concatenate [selection C.Value_ref.Product a;selection C.Value_ref.Product b]))
        ~ports:[port joined] ~assumptions:[] ~provenance in
    steps := joining :: cleavage :: !steps; previous := C.Value_ref.Product,joined,joined ^ ".frame"
  done;
  let _,last,_ = !previous in
  let extra id input = C.Transform_step.make ~id ~operation:(C.Operation.make (C.Operation.Slice (selection C.Value_ref.Product input)))
      ~ports:[port (id ^ ".product")] ~assumptions:[] ~provenance in
  let steps = List.rev !steps @ [extra "exact" last] in
  let build steps final = T.make ~id:"product_budget" ~sources:[source "source" 2] ~steps
      ~output_members:[output ~reference:(C.Value_ref.make ~kind:C.Value_ref.Product ~id:final) ()] ~requirements:[required ()] () in
  let exact = build steps "exact.product" in
  require (List.fold_left (fun count step -> count + List.length (C.Transform_step.ports step)) 0 (T.steps exact) = 256)
    "Exact aggregate product boundary rejected";
  rejected "aggregate product overflow" "invalid_payload_template" (fun () -> build (steps @ [extra "overflow" "exact.product"]) "overflow.product")
let literals () =
  let template = template () in
  require (List.length (T.output_members template) = 1 && C.Member_requirement.category (List.hd (T.requirements template)) = C.Member_requirement.Delivered_helper)
    "Source-independent helper-only template was tightened";
  let literal = obj ["schema_version",str "biocompiler.payload_template.v0.1";"id",str "template";
      "sources",arr [C.Root_source.to_json (List.hd (T.sources template))];"steps",arr [];
      "output_members",arr [C.Output_member.to_json (output ())];"requirements",arr [C.Member_requirement.to_json (required ())];
      "complex_members",arr [];"amounts",arr [];"payload_structures",arr []] in
  require (Canonical.encode (T.to_json template) = Canonical.encode literal) "Independent complete template envelope differs";
  let rec sources = List.hd (T.sources template) :: sources in
  rejected "cyclic template sources" "molecular_resource_limit" (fun () -> T.make ~id:"cycle" ~sources ~steps:[] ~output_members:[output ()] ~requirements:[required ()] ());
  let rec roles = required () :: roles in
  rejected "cyclic template requirements" "molecular_resource_limit" (fun () -> T.make ~id:"cycle" ~sources:(T.sources template) ~steps:[] ~output_members:[output ()] ~requirements:roles ());
  let explicit = refinement () in
  require (List.map (fun (a,b) -> I.Node.to_string a,I.Node.to_string b) (R.source_bindings explicit) = ["cell","source-role"])
    "Complete source correspondence was discarded";
  let policy = A.Match_policy.make ~mode:A.Match_policy.Exact_semantic_subgraph in
  let matched = refinement ~match_policy:policy ~source_bindings:[] () in
  require (R.source_bindings matched = [] && Option.is_some (R.match_policy matched)) "Empty match anchors were tightened";
  rejected "explicit source map cannot be empty" "invalid_architecture_refinement" (fun () -> refinement ~source_bindings:[] ());
  let rec anchors = (I.Node.of_string "cell",I.Node.of_string "source") :: anchors in
  rejected "cyclic native source map" "molecular_resource_limit" (fun () -> refinement ~source_bindings:anchors ());
  rejected "duplicate native source map" "duplicate_key" (fun () -> refinement ~source_bindings:[I.Node.of_string "cell",I.Node.of_string "source";I.Node.of_string "cell",I.Node.of_string "other"] ());
  let helper = A.Helper.make ~id:"helper" ~capability:"supplied" ~consumer_component_ids:[I.Component.of_string "component"] ~recipient_role:(I.Role.of_string "cell")
      ~compartment:"cytoplasm" ~availability:A.Helper.Same_rna ~initialization:A.Helper.After_expression ~sharing:A.Helper.Shared ~capacity:1
      ~assumptions:["Declared only."] ~placement_id:(Some "placement") ~provider_component_id:(Some (I.Component.of_string "component")) ~depends_on:["helper"] in
  require (A.Helper.depends_on (List.hd (R.helpers (refinement ~helpers:[helper] ()))) = ["helper"]) "Helper cycle was silently treated as structural rejection";
  let rec helpers = helper :: helpers in
  rejected "cyclic helper inventory" "molecular_resource_limit" (fun () -> refinement ~helpers ());
  let empty = R.Library.make ~id:"empty" ~refinements:[] () in
  require (Canonical.encode (R.Library.to_json empty) = Canonical.encode (Json.parse {|{"schema_version":"biocompiler.payload_architecture_library.v0.1","id":"empty","refinements":[],"assumptions":[]}|}))
    "Independent empty library literal differs";
  let rec refinements = explicit :: refinements in
  rejected "cyclic library refinement inventory" "molecular_resource_limit" (fun () -> R.Library.make ~id:"cycle" ~refinements ());
  List.iter (fun (name,decode) ->
      let rec raw = Json.Array [raw] in rejected (name ^ " raw cycle") "molecular_cycle" (fun () -> decode raw);
      let rec fields = ("cycle",Json.Null) :: fields in rejected (name ^ " raw object spine") "molecular_resource_limit" (fun () -> decode (obj fields));
      rejected (name ^ " nonfinite") "nonfinite_number" (fun () -> decode (Json.Float Float.infinity));
      rejected (name ^ " duplicate raw key") "duplicate_key" (fun () -> decode (obj ["same",Json.Null;"same",Json.Null])))
    ["template",(fun raw -> ignore (T.of_json raw));"refinement",(fun raw -> ignore (R.of_json raw));"library",(fun raw -> ignore (R.Library.of_json raw));"request",(fun raw -> ignore (Q.of_json raw))];
  budget_literals ();
  Printf.printf "architecture composite literals: %d independent structure/context, aggregate-boundary and native-cycle checks passed\n" !checks
let rec replace_at raw path replacement = match path with
  | [] -> (match replacement with Some value -> value | None -> failwith "Cannot remove document root")
  | Json.String key :: tail ->
      let fields = Json.object_fields raw in
      require (tail = [] && Option.is_some replacement || List.mem_assoc key fields) "Missing edit object path";
      if tail = [] then obj (match replacement with None -> List.remove_assoc key fields | Some value -> (key,value) :: List.remove_assoc key fields)
      else obj (List.map (fun (name,value) -> name,if name = key then replace_at value tail replacement else value) fields)
  | Json.Int index :: tail ->
      let index = Z.to_int index and values = Json.array raw in
      require (index >= 0 && index < List.length values) "Fixture edit index outside array";
      arr (List.mapi (fun i value -> if i = index then (if tail = [] && replacement = None then None else Some (replace_at value tail replacement)) else Some value) values |> List.filter_map Fun.id)
  | _ -> failwith "Invalid fixture edit path"
let edits raw changes = List.fold_left (fun raw change ->
    let replacement = match Json.string (field "op" change) with "set" -> Some (field "value" change) | "remove" -> None | _ -> failwith "Unknown edit operation" in
    replace_at raw (Json.array (field "path" change)) replacement) raw (Json.array changes)
let inspect kind raw = match kind with
  | "template" -> T.to_json (T.of_json raw)
  | "refinement" -> R.to_json (R.of_json raw)
  | "library" -> R.Library.to_json (R.Library.of_json raw)
  | "request" -> Q.to_json (Q.of_json raw)
  | _ -> failwith "Unknown composite fixture kind"
let inventory corpus =
  let rows name keys = Json.array (field name corpus)
      |> List.sort (fun a b -> String.compare (Json.string (field "id" a)) (Json.string (field "id" b)))
      |> List.map (fun item -> arr (List.map (fun key -> field key item) keys)) |> arr in
  Canonical.fingerprint (obj ["records",rows "records" ["id";"kind";"document";"edits";"normalized"];
      "rejections",rows "rejections" ["id";"kind";"document";"edits";"expected_code"];
      "conversions",field "conversions" corpus;"coverage",field "coverage" corpus])
let read path =
  require (not (Filename.is_relative path)) "Composite corpus requires an absolute path";
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let size = in_channel_length channel in require (size <= Limits.max_request_bytes) "Composite corpus read budget";
      Json.parse (really_input_string channel size))
let retained partition expected_counts digest path =
  let corpus = read path in
  require (field "schema_version" corpus = str "biocompiler.architecture_domains_conformance.v1" && field "partition" corpus = str partition)
    "Wrong composite corpus schema or partition";
  let records = Json.array (field "records" corpus) and negatives = Json.array (field "rejections" corpus)
  and conversions = Json.array (field "conversions" corpus) and documents = Json.object_fields (field "documents" corpus) in
  require ((List.length records,List.length negatives,List.length conversions,List.length documents) = expected_counts) "Incomplete composite corpus census";
  require (inventory corpus = digest && field "inventory_sha256" corpus = str digest) "Missing or substituted full composite input/expected/coverage inventory";
  let ids = List.map (fun item -> Json.string (field "id" item)) (records @ negatives) in
  require (List.length ids = List.length (List.sort_uniq String.compare ids)) "Duplicate composite fixture identity";
  List.iter (fun (identity,raw) -> require (Canonical.fingerprint raw = identity) "Changed composite document") documents;
  let used = Hashtbl.create 64 in
  let document reference = let identity = Json.string reference in Hashtbl.replace used identity (); Json.field identity documents in
  List.iter (fun case ->
      let raw = edits (document (field "document" case)) (field "edits" case) in
      let result = inspect (Json.string (field "kind" case)) raw in
      let expected = document (field "normalized" case) in
      require (Canonical.encode result = Canonical.encode expected) (Json.string (field "id" case) ^ ": normalized complete authority differs");
      require (str (Canonical.fingerprint result) = field "normalized" case) "Composite canonical identity differs";
      require (Canonical.encode (inspect (Json.string (field "kind" case)) result) = Canonical.encode result) "Composite replay changed authority") records;
  List.iter (fun case -> rejected (Json.string (field "id" case)) (Json.string (field "expected_code" case)) (fun () ->
      inspect (Json.string (field "kind" case)) (edits (document (field "document" case)) (field "edits" case)))) negatives;
  List.iter (fun case ->
      let template = T.of_json (document (field "template" case)) and request = C.Request.of_json (document (field "request" case)) in
      require (field "expected" case = str "roundtrip") "Unknown conversion expectation";
      require (T.fingerprint (T.from_construction_request request) = T.fingerprint template) "Projection from real construction authority changed declarations";
      require (C.Request.fingerprint (T.to_construction_request ~mode:(C.Request.mode request) template (C.Request.circuit request)) = C.Request.fingerprint request)
        "Materialization changed complete contextual authority";
      require (T.fingerprint (T.from_construction_request ~id:"" request) = T.fingerprint template) "Legacy empty conversion ID fallback differs") conversions;
  require (Hashtbl.length used = List.length documents) "Unreferenced composite fixture document";
  if partition = "architecture" then (
    List.iter (fun case -> if Json.string (field "kind" case) = "request" then (
        let raw = edits (document (field "document" case)) (field "edits" case) in
        let value = Q.of_json raw in
        let original = field "source_request" (field "profile" (field "circuit" raw)) in
        require (Canonical.encode (Bioc_domain.Human_request.to_json (Q.source value)) = Canonical.encode original)
          "Architecture request flattened full wrapped original source";
        let rebuilt = Q.make ~id:(Q.id value) ~circuit:(Q.circuit value) ~library:(Q.library value) ~constraints:(Q.constraints value) () in
        require (Q.fingerprint rebuilt = Q.fingerprint value) "Native request constructor changed authority";
        rejected "helper-only template does not become contextual payload" "invalid_construction"
          (fun () -> T.to_construction_request (template ()) (Q.circuit value)))) records);
  Printf.printf "%s: %d complete records, %d intended rejections and %d real-context conversion pairs passed\n"
    partition (List.length records) (List.length negatives) (List.length conversions)
let () = match Array.to_list Sys.argv with
  | [_] -> literals ()
  | [_;templates;architecture] ->
      literals ();
      retained "templates" (35,58,25,58) "b1fc51bb61712319dc2189b357e8ed8d86dc547dff20fc435b48abc7a345e331" templates;
      retained "architecture" (30,134,0,31) "d7ff0be3f3e9e2190add53584a9079b74a22e385c4f90ebf095e3891884dd785" architecture
  | _ -> failwith "Usage: test_architecture_domains.exe [<absolute-payload-templates-v1.json> <absolute-architecture-domains-v1.json>]"

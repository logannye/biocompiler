open Bioc_wire
module T = Bioc_domain.Molecular_transition
module R = Bioc_domain.Molecular_recoding
module M = Bioc_domain.Molecular_record
module F = Bioc_domain.Molecule.Feature
module C = Bioc_domain.Molecule_chemistry.Chemical_identity
module Q = Bioc_domain.Circuit_request
let require value message = if not value then failwith message
let str value = Json.String value
let obj value = Json.Object value
let field key value = Json.field key (Json.object_fields value)
let replace key value record = obj ((key,value) :: List.remove_assoc key (Json.object_fields record))
let rejected label code run = match run () with
  | _ -> failwith (label ^ ": intended failure accepted")
  | exception Diagnostic.Error error -> require (error.code = code) (label ^ ": expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message)
let provenance = M.Provenance.make ~status:M.Provenance.Unknown ~authority:[] ~locator:None ~reason:"Artificial declared transition; no biochemical evidence."
let feature id = F.make ~id ~kind:"artificial_region" ~path:None ~provenance ()
let recoding index = R.Codon_recoding.make ~codon_index:index ~expected_triplet:"UGA" ~amino_acid:'U' ~condition:"artificial_condition"
let inspect kind = match kind with
  | "chemistry_disposition" -> (fun value -> T.Chemistry_disposition.of_json value |> T.Chemistry_disposition.to_json)
  | "chemistry_transition" -> (fun value -> T.Chemistry.of_json value |> T.Chemistry.to_json)
  | "feature_disposition" -> (fun value -> T.Feature_disposition.of_json value |> T.Feature_disposition.to_json)
  | "feature_transition" -> (fun value -> T.Feature.of_json value |> T.Feature.to_json)
  | "canonical_edit" -> (fun value -> R.Canonical_edit.of_json value |> R.Canonical_edit.to_json)
  | "chemical_edit" -> (fun value -> R.Chemical_edit.of_json value |> R.Chemical_edit.to_json)
  | "codon_recoding" -> (fun value -> R.Codon_recoding.of_json value |> R.Codon_recoding.to_json)
  | "translation_policy" -> (fun value -> R.Translation_policy.of_json value |> R.Translation_policy.to_json)
  | _ -> failwith "Unknown transition corpus family"
let circuit_literals () =
  let observation = Json.parse {|{"schema_version":"biocompiler.circuit_observation.v0.1","id":"rna_observed","entity":{"schema_version":"biocompiler.observation_entity.v0.1","namespace":"fixture","accession":"rna","version":"1","isoform":"unknown"},"quantity":"rna_abundance","compartment":"cytoplasm","scope":"evaluator","window":{"schema_version":"biocompiler.observation_window.v0.1","reference":"unknown","start":null,"end":null,"unit":"unknown","aggregation":"unknown"},"encoding":{"schema_version":"biocompiler.observation_encoding.v0.1","mode":"qualitative","unit":"qualitative","low":null,"high":null,"allowed_range":null}}|} in
  let product = obj ["schema_version",str Q.Product.schema_version;"id",str "product";"kind",str "rna_product";"observation",observation] in
  let lifecycle = Json.parse {|{"schema_version":"biocompiler.circuit_lifecycle.v0.1","mode":"production_control","onset":null,"cessation":null,"clearance":null}|} in
  let provider = obj ["schema_version",str Q.Provider.schema_version;"id",str "host";"entity",field "entity" observation;
      "kind",str "host";"compartment",str "cytoplasm";"colocation_group",str "recipient";"availability",str "unestablished"] in
  let p = Q.Product.of_json product and l = Q.Lifecycle.of_json lifecycle and dependency = Q.Provider.of_json provider in
  require (Q.Product.id p = "product" && Q.Product.kind p = "rna_product" && Json.equal (Q.Product.observation p) observation && Json.equal (Q.Product.to_json p) product) "Exposed product loses checked authority";
  require (Q.Lifecycle.mode l = "production_control" && Q.Lifecycle.onset l = None && Q.Lifecycle.cessation l = None && Q.Lifecycle.clearance l = None && Json.equal (Q.Lifecycle.to_json l) lifecycle) "Exposed lifecycle loses policy";
  require (Q.Provider.id dependency = "host" && Q.Provider.kind dependency = "host" && Q.Provider.compartment dependency = "cytoplasm" && Json.equal (Q.Provider.to_json dependency) provider) "Exposed provider loses complete authority";
  require (Q.Product.fingerprint p = Canonical.fingerprint product && Q.Lifecycle.fingerprint l = Canonical.fingerprint lifecycle && Q.Provider.fingerprint dependency = Canonical.fingerprint provider) "Circuit leaf identity changed";
  let requirement = obj ["schema_version",str "biocompiler.circuit_requirement.v0.1";"id",str "requirement";"role_id",Json.Null;
      "source_node_ids",Json.Array [];"source_location",Json.Null;"input_bindings",Json.Array [];
      "behavior",obj ["schema_version",str "biocompiler.circuit_behavior.v0.1";"inputs",Json.Array [];
        "response",obj ["schema_version",str "biocompiler.boolean_spec.v0.1";"inputs",Json.Array [];"outputs",Json.Array [Json.Bool true]];
        "output",product;"lifecycle",lifecycle;"dependencies",Json.Array [provider]]] |> Q.Requirement.of_json in
  require (List.map Q.Provider.fingerprint (Q.Requirement.dependencies requirement) = [Q.Provider.fingerprint dependency]) "Dependency getter dropped complete provider authority";
  rejected "product quantity" "invalid_circuit_record" (fun () -> Q.Product.of_json (replace "kind" (str "reporter_fluorescence") product));
  rejected "provider compartment" "invalid_circuit_record" (fun () -> Q.Provider.of_json (replace "compartment" (str "abstract") provider));
  rejected "lifecycle mode" "invalid_circuit_record" (fun () -> Q.Lifecycle.of_json (replace "mode" (str "inferred") lifecycle))
let literals () =
  let edit = R.Canonical_edit.make ~position:0 ~expected:'A' ~replacement:'G' in
  require (Json.equal (R.Canonical_edit.to_json edit) (Json.parse {|{"schema_version":"biocompiler.canonical_base_edit.v0.1","position":0,"expected":"A","replacement":"G"}|})) "Independent canonical edit literal differs";
  rejected "exclusive RNA index bound" "invalid_molecular_index" (fun () -> R.Canonical_edit.make ~position:1_000_000 ~expected:'A' ~replacement:'G');
  rejected "canonical no-op" "invalid_canonical_edit" (fun () -> R.Canonical_edit.make ~position:0 ~expected:'A' ~replacement:'A');
  let inosine = C.make ~namespace:"biocompiler.chemical" ~accession:"inosine" ~version:"1" in
  let chemical = R.Chemical_edit.make ~position:0 ~parent:'A' ~before:None ~after:(Some inosine) in
  require (R.Chemical_edit.parent chemical = 'A' && R.Chemical_edit.position chemical = 0) "Chemical edit rewrote the canonical parent";
  rejected "chemical no-op" "invalid_chemical_edit" (fun () -> R.Chemical_edit.make ~position:0 ~parent:'A' ~before:(Some inosine) ~after:(Some inosine));
  rejected "chemical parent" "invalid_chemical_edit" (fun () -> R.Chemical_edit.make ~position:0 ~parent:'G' ~before:None ~after:(Some inosine));
  let table = R.standard_rna_codon_table in
  require (List.length table = 64 && List.length (List.sort_uniq String.compare (List.map fst table)) = 64) "Incomplete codon table";
  let rows = ["A","KNKNTTTTRSRSIIMI";"C","QHQHPPPPRRRRLLLL";"G","EDEDAAAAGGGGVVVV";"U","*Y*YSSSS*CWCLFLF"] in
  List.iter (fun (first,residues) -> String.iteri (fun second b -> String.iteri (fun third c ->
      let codon = first ^ String.make 1 b ^ String.make 1 c in
      require (List.assoc codon table = residues.[second * 4 + third]) ("Independent codon mismatch: " ^ codon)) "ACGU") "ACGU") rows;
  let ordinary = R.Translation_policy.make ~profile:R.Translation_policy.Ordinary_cds () in
  require (R.Translation_policy.genetic_code ordinary = "ncbi_standard_v1" && R.Translation_policy.recodings ordinary = []) "Ordinary policy defaults differ";
  rejected "import requires default field" "missing_field" (fun () -> R.Translation_policy.of_json (obj (List.remove_assoc "recodings" (Json.object_fields (R.Translation_policy.to_json ordinary)))));
  let maximum = List.init R.max_recodings recoding in
  let policy = R.Translation_policy.make ~profile:R.Translation_policy.Conditional_cds ~recodings:(List.rev maximum) () in
  require (List.map R.Codon_recoding.codon_index (R.Translation_policy.recodings policy) = List.init 4096 Fun.id) "Inclusive recoding collection boundary or sorting differs";
  rejected "recoding collection overflow" "molecular_resource_limit" (fun () -> R.Translation_policy.make ~profile:R.Translation_policy.Conditional_cds ~recodings:(recoding 4096 :: maximum) ());
  let large_conditions = List.init 4096 (fun index -> R.Codon_recoding.make ~codon_index:index ~expected_triplet:"UGA" ~amino_acid:'U' ~condition:(String.make 4096 'x')) in
  rejected "aggregate recoding text" "molecular_resource_limit" (fun () -> R.Translation_policy.make ~profile:R.Translation_policy.Conditional_cds ~recodings:large_conditions ());
  let rec cyclic_recodings = recoding 0 :: cyclic_recodings in
  rejected "cyclic recoding spine" "molecular_resource_limit" (fun () -> R.Translation_policy.make ~profile:R.Translation_policy.Conditional_cds ~recodings:cyclic_recodings ());
  let component = T.Component.of_string ("modification:" ^ String.make 4096 'a') in
  require (String.length (T.Component.to_string component) = 4109) "Modification selector lost full occurrence identity";
  rejected "selector length" "invalid_molecular_text" (fun () -> T.Component.of_string (T.Component.to_string component ^ "a"));
  let destinations = List.init 256 (fun index -> T.Component.of_string ("modification:" ^ string_of_int index)) in
  let disposition = T.Chemistry_disposition.make ~source_id:"source" ~component ~decision:T.Chemistry_disposition.Unknown ~destination_components:destinations ~provenance in
  require (List.length (T.Chemistry_disposition.destination_components disposition) = 256) "Exact destination capacity rejected";
  let rec cyclic_destinations = component :: cyclic_destinations in
  rejected "cyclic destination spine" "molecular_resource_limit" (fun () -> T.Chemistry_disposition.make ~source_id:"source" ~component ~decision:T.Chemistry_disposition.Unknown ~destination_components:cyclic_destinations ~provenance);
  let rec cyclic_dispositions = disposition :: cyclic_dispositions in
  rejected "cyclic chemistry disposition spine" "molecular_resource_limit" (fun () -> T.Chemistry.make ~mode:T.Chemistry.Exact_inheritance ~output:None ~dispositions:cyclic_dispositions ~provenance);
  let outputs = List.init 256 (fun index -> feature (string_of_int index)) in
  let split = T.Feature_disposition.make ~source_id:"source" ~feature_id:"original" ~decision:T.Feature_disposition.Split ~outputs ~provenance in
  let transition = T.Feature.make ~dispositions:[split] ~added:[] ~provenance in
  require (List.length (T.Feature_disposition.outputs (List.hd (T.Feature.dispositions transition))) = 256) "Total feature capacity rejected";
  rejected "aggregate output overflow" "invalid_feature_transition" (fun () -> T.Feature.make ~dispositions:[split] ~added:[feature "one_more"] ~provenance);
  let rec cyclic_outputs = feature "cycle" :: cyclic_outputs in
  rejected "cyclic output spine" "molecular_resource_limit" (fun () -> T.Feature_disposition.make ~source_id:"source" ~feature_id:"original" ~decision:T.Feature_disposition.Unknown ~outputs:cyclic_outputs ~provenance);
  let rec cyclic_features = split :: cyclic_features in
  rejected "cyclic feature disposition spine" "molecular_resource_limit" (fun () -> T.Feature.make ~dispositions:cyclic_features ~added:[] ~provenance);
  rejected "cyclic added spine" "molecular_resource_limit" (fun () -> T.Feature.make ~dispositions:[] ~added:cyclic_outputs ~provenance);
  let rec cyclic_json = Json.Array [cyclic_json] in
  rejected "raw native cycle" "molecular_cycle" (fun () -> R.Translation_policy.of_json cyclic_json);
  rejected "raw nonfinite" "nonfinite_number" (fun () -> R.Canonical_edit.of_json (replace "position" (Json.Float infinity) (R.Canonical_edit.to_json edit)));
  rejected "raw duplicate" "duplicate_key" (fun () -> R.Canonical_edit.of_json (obj (("position",Json.int 1) :: Json.object_fields (R.Canonical_edit.to_json edit))));
  circuit_literals ();
  print_endline "molecular transitions: exact edit and 64-codon literals, public circuit leaves, collection boundaries and native cyclic constructors passed"
let read_json path =
  require (not (Filename.is_relative path)) "Required transition corpus path must be absolute";
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size = in_channel_length channel in require (size <= Limits.max_request_bytes) "Transition corpus read bound";
    Json.parse (really_input_string channel size))
let retained path =
  let corpus = read_json path in
  require (field "schema_version" corpus = str "biocompiler.molecular_transitions_conformance.v1") "Unknown transition corpus schema";
  let records = Json.array (field "records" corpus) and negatives = Json.array (field "rejections" corpus)
  and literals = field "literal_expectations" corpus in
  require (List.length records = 153 && List.length negatives = 199 && List.length (Json.array literals) = 6) "Wrong transition corpus census";
  let ids = List.map (fun item -> Json.string (field "id" item)) (records @ negatives) in
  require (List.length ids = List.length (List.sort_uniq String.compare ids)) "Duplicate transition case identity";
  let inventory keys items = List.sort (fun left right -> String.compare (Json.string (field "id" left)) (Json.string (field "id" right))) items
      |> List.map (fun item -> Json.Array (List.map (fun key -> field key item) keys)) |> fun values -> Canonical.fingerprint (Json.Array values) in
  require (inventory ["id";"kind"] records = "193604f8d1e3cee3466430c30f694a0159d08b8be3a4b14549d5e8464af8a737") "Required transition positive inventory changed";
  require (inventory ["id";"kind";"expected_stage";"expected_code"] negatives = "c210da4aa1e67c25666995f25e451366dbde237a1a9a858b9888aec840884f30") "Required transition failure signatures changed";
  require (Canonical.fingerprint literals = "52239f6c1c87841bd1d73f43ab670563223b761a0ac0c3922f9a20516784c7af") "Independent transition literals changed";
  List.iter (fun item ->
      let label = Json.string (field "id" item) and kind = Json.string (field "kind" item) in
      let actual = inspect kind (field "input" item) in
      require (Json.equal actual (field "normalized" item)) (label ^ ": full normalized declaration differs");
      require (str (Canonical.fingerprint actual) = field "fingerprint" item) (label ^ ": declaration identity differs");
      require (Json.equal actual (inspect kind actual)) (label ^ ": repeated import changed authority")) records;
  List.iter (fun item ->
      require (field "expected_stage" item = str "record") "Unknown molecular leaf rejection stage";
      rejected (Json.string (field "id" item)) (Json.string (field "expected_code" item))
        (fun () -> inspect (Json.string (field "kind" item)) (field "input" item))) negatives;
  List.iter (fun item ->
      let source = List.find (fun source -> field "id" source = field "id" item) records in
      let actual = inspect (Json.string (field "kind" source)) (field "input" source) in
      require (Json.equal actual (field "normalized" item)) "Independent complete transition literal differs") (Json.array literals);
  let table = obj (List.map (fun (codon,residue) -> codon,str (String.make 1 residue)) R.standard_rna_codon_table) in
  require (Json.equal table (field "codon_table" corpus)) "Complete retained codon table differs";
  Printf.printf "molecular transitions: %d complete leaf records, %d intended failures, six independent literals and all 64 codons passed\n" (List.length records) (List.length negatives)
let () = match Array.to_list Sys.argv with
  | [_] -> literals ()
  | [_; path] -> literals (); retained path
  | _ -> failwith "Usage: test_molecular_transitions.exe [<absolute-molecular-transitions-v1.json>]"

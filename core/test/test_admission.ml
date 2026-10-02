open Bioc_wire
open Bioc_domain
module A = Admission
module R = A.Request
module S = A.Assessment
module Check = Bioc_checker.Admission_check
module T = Build_request.Target
module E = Build_request.Target_evidence
module P = Pinned_identity
let checks = ref 0
let check condition message = incr checks; if not condition then failwith message
let reject code run =
  incr checks;
  match run () with
  | _ -> failwith ("Accepted admission mutation; expected " ^ code)
  | exception Diagnostic.Error diagnostic -> if diagnostic.code <> code then
      failwith ("Expected " ^ code ^ ", received " ^ diagnostic.code ^ ": " ^ diagnostic.message)
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let set key replacement value = obj ((key,replacement) :: List.remove_assoc key (Json.object_fields value))
let legacy = T.of_json (Json.parse {|{"schema_version":"biocompiler.target.v0.1","context_id":"test","context_version":"1","payload_format":"RNA","capabilities":[],"compartments":["abstract"],"resources":{}}|})
let pin kind id = P.make ~kind ~id ~version:"1" ~content_fingerprint:(String.make 64 'a')
let evidence system =
  let taxon_id = match system with
    | E.Human_in_vivo | E.Primary_human_cells | E.Human_cell_line -> Some (Z.of_int 9606)
    | E.Nonhuman_in_vivo | E.Nonhuman_cells -> Some (Z.of_int 10090)
    | E.Cell_free | E.Software_fixture -> None in
  E.make ~id:(E.system_name system) ~source:(pin P.Source "reference") ~taxon_id ~system
    ~source_context:"declared" ~locator:"fixture" ~limitations:"unvalidated"
let categories = [E.Human_in_vivo; E.Primary_human_cells; E.Human_cell_line; E.Nonhuman_in_vivo; E.Nonhuman_cells; E.Cell_free; E.Software_fixture]
let human evidence =
  let claim = obj ["schema_version",str "biocompiler.target_claim.v0.1"; "description",str "pending";
    "basis",str "unestablished"; "evidence_ids",arr []; "limitations",str "unestablished"] in
  let domain = Component_contract.Value_domain.unknown
      ~dtype:(Type_spec.of_json (Json.parse {|{"kind":"scalar","name":"Level"}|})) ~unit:"1" ~reason:"unestablished" in
  let contract = obj (["schema_version",str "biocompiler.human_target_contract.v0.1"; "recipient_taxon_id",Json.int 9606;
    "engineering",str "in_vivo";
    "host_dependencies",arr [obj ["schema_version",str "biocompiler.human_host_dependency.v0.1";
      "id",str "host"; "capability",str "host_translation"; "compartment",str "cytoplasm"; "support",claim]];
    "operating_conditions",arr [obj ["schema_version",str "biocompiler.human_operating_condition.v0.1";
      "id",str "level"; "observable",str "level"; "compartment",str "cytoplasm";
      "domain",Component_contract.Value_domain.to_json domain; "support",claim]];
    "evidence",arr (List.map E.to_json evidence)] @
    List.map (fun key -> key,claim) ["cell_subtype"; "cell_state"; "tissue_context"; "disease_context"; "population_inclusion"; "population_exclusion"]) in
  T.of_json (obj ["schema_version",str "biocompiler.human_target_context.v0.1"; "context_id",str "human";
    "context_version",str "1"; "payload_format",str "RNA"; "capabilities",arr [];
    "compartments",arr [str "cytoplasm"]; "resources",obj []; "human_target",contract])
let component ?(lower = Runtime_number.of_int 1) ?(classification = Component.Synthetic_model) id =
  let domain = Component_contract.Value_domain.interval ~lower ~upper:(Runtime_number.of_int 10)
      ~dtype:(Type_spec.of_json (Json.parse {|{"kind":"scalar","name":"Level"}|})) ~unit:"1" in
  let reference_metadata, identities = match classification with
    | Component.Sequence_reference -> Some (Component.Sequence_reference.make ~artifact_class:Component.Sequence_reference.Coding_rna
        ~sequence_length:(Z.of_int 3) ~unknown_features:[]), [pin P.Reference "wo2022081694a1.murine-fapcar.cds"]
    | _ -> None, [pin P.Model "model"] in
  Component.make ~id ~version:"1" ~classification ~implementation_role:"sensor" ~supported_targets:["RNA"]
    ~ports:[] ~supported_domain:(Component_contract.Operating_domain.make ["level",domain]) ~identities ~assumptions:[]
    ~guarantees:["declared_sensor_contract"] ~evidence:[] ~parameters:[] ~dependencies:[] ~capabilities:[] ~resources:[]
    ~reference_metadata ~synthetic_model:None
let request ?(target = legacy) ?(intended_use = A.Software_test) ?(boundary = A.Planning) ?(components = []) () =
  R.make ~target ~intended_use ~boundary ~components
let literal_tests () =
  let original = request () in
  check (R.fingerprint original = "677006e5563d4c79f9daabb11cc918ce2330515bac855d4c279b3a5467930aca") "Independent software request hash differs";
  let result = Check.assess original in
  let expected = Json.parse {|{"boundary":"planning","claim_scope":"use_eligibility_only_no_biological_validation","component_fingerprints":[],"decision":"software_only","diagnostics":["software_testing_only_no_human_therapeutic_admission"],"evidence":[],"evidence_status":"declared_not_independently_validated","human_therapeutic_admission":"not_admitted","intended_use":"software_test","policy":"biocompiler.human_admission_policy.v0.1","request_fingerprint":"677006e5563d4c79f9daabb11cc918ce2330515bac855d4c279b3a5467930aca","schema_version":"biocompiler.admission_assessment.v0.1","target_fingerprint":"6681351d91efd04ca428bc296b1afbd3427ad0449b2fc7b83997a5c6dd858b75"}|} in
  check (Json.equal (S.to_json result) expected) "Complete independent software decision differs";
  check (S.fingerprint result = "e8d9d6a342451a045409e5174fa8fdd39f07ec3bdea507c56dcafc9a800753ec") "Independent software result hash differs";
  check (R.canonical_size original = String.length (Canonical.encode (R.to_json original)) &&
         S.canonical_size result = String.length (Canonical.encode (S.to_json result))) "Cached size differs";
  check (S.is_current result original && Check.verify original result) "Fresh decision rejected";
  let historical = S.of_json (set "diagnostics" (arr [str "producer says admitted"]) (S.to_json result)) in
  check (S.is_current historical original && not (Check.verify original historical)) "Identity freshness became policy authority";
  List.iter (fun (key,value) ->
      let changed = S.of_json (set key value (S.to_json result)) in
      check (not (Check.verify original changed)) ("Fresh replay ignored " ^ key))
    ["request_fingerprint",str (String.make 64 'a'); "target_fingerprint",str (String.make 64 'b');
     "component_fingerprints",arr [str (String.make 64 'c')]; "decision",str "not_admitted";
     "boundary",str "export"; "evidence",arr [E.to_json (evidence E.Software_fixture)]];
  let changed = request ~boundary:A.Export () in
  check (not (S.is_current result changed) && not (Check.verify changed result)) "Boundary change retained authority";
  let target = human [] in
  let human_request = request ~target ~intended_use:A.Human_therapeutic ~boundary:A.Verification () in
  let human_result = Check.assess human_request in
  check (R.fingerprint human_request = "8ca6a5f05551a33846d3a78c93a4fd96e3880b8d99403e4869868ab252e5e989") "Independent human request hash differs";
  check (S.fingerprint human_result = "c9fd693da91c9fb7b2a8c7879b9b0a5dec3d5224a4e686ed8082fe4154d2227f") "Independent human decision hash differs";
  check (S.diagnostics human_result = ["human_applicability_not_independently_validated"; "human_in_vivo_evidence_not_declared"; "human_profile_unavailable"])
    "Missing unestablished human obligations";
  List.iter (fun boundary ->
      let human_result = Check.for_target ~target ~boundary ~components:[] in
      check (S.decision human_result = A.Not_admitted && S.intended_use human_result = A.Human_therapeutic) "Human boundary admitted";
      reject "admission_not_admitted" (fun () -> Check.require_software_use ~target ~boundary ~components:[]);
      check (S.decision (Check.require_software_use ~target:legacy ~boundary ~components:[]) = A.Software_only) "Legacy software gate rejected")
    [A.Planning; A.Selection; A.Verification; A.Export];
  let downgraded = Check.assess (request ~target ()) in
  check (S.decision downgraded = A.Not_admitted && List.mem "human_target_cannot_be_downgraded_to_software" (S.diagnostics downgraded)) "Human target downgraded";
  let renamed = T.of_json (T.to_json legacy |> set "context_id" (str "human_in_vivo") |> set "capabilities" (arr [str "human_admitted"])) in
  let unsupported = Check.assess (request ~target:renamed ~intended_use:A.Human_therapeutic ()) in
  check (S.diagnostics unsupported = ["human_in_vivo_evidence_not_declared"; "human_profile_unavailable"; "human_target_contract_missing"])
    "Legacy labels invented human contract";
  check (S.intended_use (Check.for_target ~target:renamed ~boundary:A.Planning ~components:[]) = A.Software_test) "Target use inferred from names";
  let declarations = List.map evidence categories in
  let target = human (List.rev declarations) in
  let components = [component "a"; component ~classification:Component.Modeled_component "b"; component ~classification:Component.Sequence_reference "c"] in
  let all = Check.assess (request ~target ~intended_use:A.Human_therapeutic ~components ()) in
  let reasons = ["cell_free_evidence_does_not_establish_recipient_applicability"; "human_applicability_not_independently_validated";
    "human_cell_line_evidence_does_not_establish_primary_or_in_vivo_applicability"; "human_in_vivo_evidence_requires_independent_review";
    "human_profile_unavailable"; "modeled_component_not_independently_admitted_for_human_use";
    "murine_fap_reference_not_human_implementation"; "nonhuman_cell_evidence_does_not_establish_human_applicability";
    "nonhuman_in_vivo_evidence_does_not_establish_human_applicability"; "primary_human_cell_evidence_does_not_establish_in_vivo_applicability";
    "sequence_reference_not_human_implementation"; "software_fixture_is_not_biological_evidence"; "synthetic_model_not_human_implementation"] in
  check (S.decision all = A.Not_admitted && S.diagnostics all = reasons) "Full category/classification reasons differ";
  check (List.map E.id (S.evidence all) = List.sort String.compare (List.map E.id declarations)) "Evidence order/inventory differs";
  List.iter (fun original -> let restored = E.of_json (E.to_json original) in
      check (Json.equal (E.to_json restored) (E.to_json original)) "Evidence declaration changed";
      let changed = E.of_json (set "limitations" (str "different") (E.to_json original)) in
      let changed_target = human (changed :: List.filter (fun item -> E.id item <> E.id original) declarations) in
      check (not (Check.verify (request ~target:changed_target ~intended_use:A.Human_therapeutic ~components ()) all)) "Evidence change retained assessment") declarations;
  let integer = component "same" and real = component ~lower:(Runtime_number.Real 1.) "same" in
  check (Component.fingerprint integer <> Component.fingerprint real) "Numeric serialization distinction lost";
  let duplicate = request ~components:[integer; real] () in
  check (List.map Component.fingerprint (R.components duplicate) = [Component.fingerprint real]) "Equal duplicate did not preserve final numeric record";
  let reversed = request ~components:[real; integer] () in
  check (List.map Component.fingerprint (R.components reversed) = [Component.fingerprint integer]) "Stable duplicate order changed";
  reject "admission_record" (fun () -> request ~components:[integer; component ~lower:(Runtime_number.of_int 2) "same"] ());
  let a = component "a" and b = component "b" in
  check (List.map Component.id (R.components (request ~components:[b;a;b] ())) = ["a";"b"]) "Component sorting/dedup changed";
  check (T.capabilities renamed = ["human_admitted"] && T.resources legacy = [] && T.evidence legacy = []) "Typed target projection differs";
  let resource = Json.parse {|{"kind":"scalar","type":{"kind":"scalar","name":"Level","dimensions":{},"arguments":[]},"value":3,"unit":"1","canonical_value":3}|} in
  let target = T.of_json (set "resources" (obj ["capacity",resource]) (T.to_json legacy)) in
  check (match T.resources target with ["capacity",value] -> Json.equal (Measurement_contract.Scalar.to_json value) resource | _ -> false)
    "Resource projection dropped a normalized scalar field"
let mutation_tests () =
  let request = request () |> R.to_json in
  let result = Check.assess (R.of_json request) |> S.to_json in
  let malformed decoder json =
    List.iter (fun (key, _) -> reject "missing_field" (fun () -> decoder (obj (List.remove_assoc key (Json.object_fields json))))) (Json.object_fields json);
    reject "unknown_field" (fun () -> decoder (set "accepted" (Json.Bool true) json));
    reject "unsupported_schema" (fun () -> decoder (set "schema_version" (str "future") json));
    reject "duplicate_key" (fun () -> decoder (obj (("schema_version",get "schema_version" json) :: Json.object_fields json))) in
  malformed (fun value -> ignore (R.of_json value)) request;
  malformed (fun value -> ignore (S.of_json value)) result;
  malformed (fun value -> ignore (E.of_json value)) (E.to_json (evidence E.Human_in_vivo));
  List.iter (fun (key, bad) -> reject "admission_record" (fun () -> R.of_json (set key (str bad) request)))
    ["intended_use","clinical"; "boundary","manufacturing"];
  List.iter (fun key -> reject "invalid_type" (fun () -> R.of_json (set key Json.Null request))) ["intended_use";"boundary";"target";"components"];
  List.iter (fun key -> List.iter (fun value -> reject "admission_record" (fun () -> S.of_json (set key value result)))
      [str "admitted";Json.Bool true;Json.Null]) ["policy";"human_therapeutic_admission";"claim_scope";"evidence_status"];
  List.iter (fun key -> reject "admission_record" (fun () -> S.of_json (set key (str "bad") result));
      reject "invalid_type" (fun () -> S.of_json (set key (Json.int 1) result))) ["request_fingerprint";"target_fingerprint"];
  reject "admission_record" (fun () -> S.of_json (set "intended_use" (str "human_therapeutic") result));
  reject "admission_record" (fun () -> S.of_json (set "decision" (str "admitted") result));
  reject "admission_record" (fun () -> S.of_json (set "diagnostics" (arr []) result));
  reject "admission_record" (fun () -> S.of_json (set "diagnostics" (arr [str "x";str "x"]) result));
  reject "invalid_name" (fun () -> S.of_json (set "diagnostics" (arr [str " "]) result));
  reject "admission_record" (fun () -> S.of_json (set "component_fingerprints" (arr [str "bad"]) result));
  reject "admission_record" (fun () -> S.of_json (set "component_fingerprints" (arr [str (String.make 64 'a');str (String.make 64 'a')]) result));
  let item = E.to_json (evidence E.Human_in_vivo) in
  reject "admission_record" (fun () -> S.of_json (set "evidence" (arr [item;item]) result));
  reject "invalid_evidence_taxon" (fun () -> E.of_json (set "taxon_id" (Json.int 10090) item));
  reject "invalid_choice" (fun () -> E.of_json (set "system" (str "verified") item));
  reject "invalid_content_fingerprint" (fun () -> E.of_json (set "source" (set "content_fingerprint" (str "bad") (get "source" item)) item));
  reject "invalid_choice" (fun () -> E.of_json (set "source" (set "kind" (str "model") (get "source" item)) item));
  reject "invalid_utf8" (fun () -> R.of_json (set "boundary" (str "\255") request));
  reject "nonfinite_number" (fun () -> S.of_json (set "decision" (Json.Float nan) result));
  let rec cycle = Json.Array [cycle] in reject "admission_cycle" (fun () -> R.of_json cycle);
  let rec spine = Json.Null :: spine in reject "admission_limit" (fun () -> R.of_json (arr spine));
  let rec object_spine = ("x",Json.Null) :: object_spine in reject "admission_limit" (fun () -> R.of_json (obj object_spine));
  let deep = List.fold_left (fun value _ -> arr [value]) Json.Null (List.init (Limits.max_depth+1) Fun.id) in
  reject "admission_limit" (fun () -> R.of_json (set "boundary" deep request));
  let exact = String.make Limits.max_string_bytes 'x' in
  let large = S.of_json (set "diagnostics" (arr [str exact]) result) in
  check (S.diagnostics large = [exact]) "Exact string boundary rejected";
  reject "admission_limit" (fun () -> S.of_json (set "diagnostics" (arr [str (exact ^ "x")]) result));
  let repeated_component = component "cycle" in
  let rec components = repeated_component :: components in
  reject "admission_limit" (fun () -> R.make ~target:legacy ~intended_use:A.Software_test ~boundary:A.Planning ~components);
  let rec diagnostics = "cycle" :: diagnostics in
  reject "admission_limit" (fun () -> S.make ~request_fingerprint:(String.make 64 'a') ~target_fingerprint:(String.make 64 'b')
      ~intended_use:A.Software_test ~boundary:A.Planning ~decision:A.Software_only ~diagnostics ~component_fingerprints:[] ~evidence:[]);
  reject "admission_limit" (fun () -> S.make ~request_fingerprint:(String.make 64 'a') ~target_fingerprint:(String.make 64 'b')
      ~intended_use:A.Software_test ~boundary:A.Planning ~decision:A.Software_only ~diagnostics:[exact;exact;exact;exact] ~component_fingerprints:[] ~evidence:[])
let () =
  match Array.to_list Sys.argv with
  | [_] -> literal_tests (); mutation_tests (); Printf.printf "admission: %d literal checks\n" !checks
  | _ -> failwith "Usage: test_admission.exe"

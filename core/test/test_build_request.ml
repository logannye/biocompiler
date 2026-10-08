open Bioc_wire
module Request = Bioc_domain.Build_request

let checks = ref 0
let check condition message =
  incr checks; if not condition then failwith message
let str value = Json.String value
let obj values = Json.Object values
let arr values = Json.Array values
let get key value = Json.field key (Json.object_fields value)
let set key value source = obj ((key, value) :: List.remove_assoc key (Json.object_fields source))
let remove key source = obj (List.remove_assoc key (Json.object_fields source))
let rec get_at path value = match path with
  | [] -> value
  | key :: tail -> get_at tail (match value with
      | Json.Array values -> List.nth values (int_of_string key)
      | _ -> get key value)
let rec set_at path replacement value = match path with
  | [] -> replacement
  | key :: tail -> (match value with
      | Json.Array values -> arr (List.mapi (fun index value ->
          if index = int_of_string key then set_at tail replacement value else value) values)
      | _ -> set key (set_at tail replacement (get key value)) value)
let accepted value =
  let result = Request.of_json value in incr checks; result
let rejected code value =
  incr checks;
  match Request.of_json value with
  | _ -> failwith ("Accepted invalid BuildRequest; expected " ^ code)
  | exception Diagnostic.Error diagnostic ->
      if diagnostic.code <> code then
        failwith ("Wrong BuildRequest rejection: " ^ diagnostic.code ^ ", expected " ^ code)
let same expected actual message = check (Json.equal expected actual) message

let duration = Json.parse {|{"kind":"scalar","name":"Duration","dimensions":{"time":1},"arguments":[]}|}
let scalar value = obj ["kind", str "scalar"; "type", duration; "value", Json.int value;
                       "unit", str "s"; "canonical_value", Json.int value]
let metadata = Json.parse {|{"schema_version":"biocompiler.binding_metadata.v0.1","category":"user_selected","provenance":{},"allowed_variation":null}|}
let provenance = Json.parse {|{"schema_version":"biocompiler.elaboration_provenance.v0.1","source_identities":{},"dependency_identities":{},"external_inputs":{},"locations":{},"recorded_at":null}|}
let node ?(kind = "parameter") ?(dtype = duration) ?(attributes = []) id =
  obj ["id", str id; "kind", str kind; "inputs", arr []; "data_type", dtype;
       "attributes", obj attributes; "role", Json.Null; "source", Json.Null]
let program nodes = obj ["schema_version", str "biocompiler.intent.v0.1"; "name", str "request-test";
                         "nodes", arr nodes; "roots", arr []]
let bare = obj ["schema_version", str Request.schema_version; "intent", program [];
  "explicit_overrides", obj []; "resolved_defaults", obj []; "resolved_bindings", obj [];
  "target", Json.Null; "artifact_scope", str "abstract_behavior";
  "behavior_profile", str "biocompiler.behavior.v0.2"; "implementation_constraints", obj [];
  "preferences", obj []; "parameter_metadata", obj []; "provenance", provenance]
let bound ?(dtype = duration) value = bare
  |> set "intent" (program [node ~dtype ~attributes:["name", str "duration"; "bound", Json.Bool true; "default", value] "p"])
  |> set "resolved_defaults" (obj ["duration", value])
  |> set "resolved_bindings" (obj ["duration", value])
  |> set "parameter_metadata" (obj ["duration", metadata])
let overridden ?(dtype = duration) default value = bound ~dtype default
  |> set "explicit_overrides" (obj ["duration", value])
  |> set "resolved_defaults" (obj [])
  |> set "resolved_bindings" (obj ["duration", value])
let interval lower upper = obj ["kind", str "interval"; "lower", scalar lower; "upper", scalar upper;
  "type", obj ["kind", str "interval"; "name", str "Interval[Duration]";
               "dimensions", obj []; "arguments", arr [duration]]]
let with_variation variation request = set_at ["parameter_metadata"; "duration"; "allowed_variation"] variation request
let legacy_target = Json.parse {|{"schema_version":"biocompiler.target.v0.1","context_id":"fixture","context_version":"1","payload_format":"RNA","capabilities":["translation","sensing"],"compartments":["nucleus","cytoplasm"],"resources":{}}|}

let units () =
  let empty = accepted bare in
  same bare (Request.to_json empty) "Empty request round trip changed authority";
  check (Request.behavior_profile empty = Request.V2) "Lost v0.2 profile";
  check (Request.artifact_scope empty = Request.Abstract_behavior) "Lost abstract scope";
  check (List.mem "source_behavior_execution" (Request.unimplemented_obligations empty)) "Decode implied source execution";
  check (Request.target empty = None) "Invented a target";
  rejected "unknown_field" (set "extra" Json.Null bare);
  rejected "unsupported_schema" (set "schema_version" (str "biocompiler.build_request.v999") bare);
  rejected "unsupported_behavior_profile" (set "behavior_profile" (str "unknown") bare);
  rejected "unsupported_artifact_scope" (set "artifact_scope" (str "unknown") bare);
  rejected "missing_target" (set "artifact_scope" (str "complete_payload") bare);
  let default = bound (scalar 2) in
  let decoded = accepted default in
  same default (Request.to_json decoded) "Default request round trip changed authority";
  check (Request.resolved_bindings decoded = ["duration", scalar 2]) "Default binding was not retained";
  check (Request.resolved_defaults decoded = ["duration", scalar 2]) "Default source was not retained";
  check (Request.explicit_overrides decoded = []) "Default became an override";
  let override = overridden (scalar 2) (scalar 3) in
  let decoded = accepted override in
  same override (Request.to_json decoded) "Override request round trip changed authority";
  check (Request.resolved_defaults decoded = []) "Overridden parameter still contributes a default";
  let two_parameters = bare
    |> set "intent" (program [
      node ~attributes:["name", str "first"; "bound", Json.Bool true; "default", scalar 1] "a";
      node ~attributes:["name", str "second"; "bound", Json.Bool true; "default", scalar 2] "b"])
    |> set "explicit_overrides" (obj ["second", scalar 4; "first", scalar 3])
    |> set "resolved_bindings" (obj ["first", scalar 3; "second", scalar 4])
    |> set "parameter_metadata" (obj ["second", metadata; "first", metadata]) in
  let first_order = accepted two_parameters in
  let reverse_mapping key value = set key (obj (List.rev (Json.object_fields (get key value)))) value in
  let second_order = two_parameters |> reverse_mapping "explicit_overrides"
    |> reverse_mapping "resolved_bindings" |> reverse_mapping "parameter_metadata" |> accepted in
  check (Request.fingerprint first_order = Request.fingerprint second_order) "Binding resolution depends on object insertion order";
  rejected "resolved_bindings_mismatch" (set "resolved_bindings" (obj ["first", scalar 4; "second", scalar 3]) two_parameters);
  let unbound = set "intent" (program [node ~attributes:["name", str "duration"; "bound", Json.Bool false] "p"]) bare in
  rejected "unbound_parameter" unbound;
  ignore (accepted (unbound |> set "explicit_overrides" (obj ["duration", scalar 3])
    |> set "resolved_bindings" (obj ["duration", scalar 3]) |> set "parameter_metadata" (obj ["duration", metadata])));
  rejected "unknown_parameter" (set "explicit_overrides" (obj ["typo", scalar 2]) default);
  rejected "parameter_metadata_coverage" (set "parameter_metadata" (obj []) default);
  rejected "parameter_metadata_coverage" (set "parameter_metadata" (obj ["duration", metadata; "extra", metadata]) default);
  rejected "resolved_defaults_mismatch" (set "resolved_defaults" (obj ["duration", scalar 3]) default);
  rejected "resolved_bindings_mismatch" (set "resolved_bindings" (obj ["duration", scalar 3]) default);
  rejected "resolved_defaults_mismatch" (set "resolved_defaults" (obj ["duration", scalar 2]) override);
  rejected "invalid_type" (set_at ["explicit_overrides"; "duration"; "value"] (Json.Bool true) override);
  rejected "canonical_value_mismatch" (set_at ["explicit_overrides"; "duration"; "canonical_value"] (Json.int 4) override);
  rejected "noncanonical_override" (set_at ["explicit_overrides"; "duration"; "canonical_value"] (Json.Float 3.) override);
  let short_type = remove "arguments" duration in
  let raw_default = scalar 2 |> set "type" short_type |> set "canonical_value" (Json.Float 2.) in
  let raw = bound raw_default in
  same raw (Request.to_json (accepted raw)) "Valid source defaults were spuriously canonicalized";
  rejected "noncanonical_override" (overridden (scalar 2) (set "type" short_type (scalar 3)));
  let zero_default = scalar 0 |> set "value" (Json.Float (-0.)) |> set "canonical_value" (Json.Float 0.) in
  ignore (accepted (bound zero_default));
  rejected "noncanonical_override" (overridden (scalar 0) zero_default);
  let at_boundary = with_variation (interval 3 3) override in
  let decoded = accepted at_boundary in
  let item = List.assoc "duration" (Request.parameter_metadata decoded) in
  check (Request.metadata_category item = Request.User_selected) "Lost parameter category";
  check (Request.metadata_provenance item = []) "Invented binding provenance";
  check (Request.metadata_allowed_variation item = Some (interval 3 3)) "Lost allowed variation";
  let raw_variation = interval 3 3
    |> set_at ["lower"; "canonical_value"] (Json.Float 3.)
    |> set_at ["upper"; "type"] short_type in
  let with_raw_variation = with_variation raw_variation override in
  same with_raw_variation (Request.to_json (accepted with_raw_variation))
    "Allowed-variation validation changed retained metadata representation";
  rejected "value_outside_allowed_variation" (with_variation (interval 0 2) override);
  rejected "invalid_interval" (with_variation (interval 4 2) override);
  rejected "invalid_allowed_variation" (with_variation (scalar 3) override);
  rejected "invalid_choice" (set_at ["parameter_metadata"; "duration"; "category"] (str "runtime_observation") override);
  rejected "unknown_field" (set_at ["parameter_metadata"; "duration"] (set "extra" Json.Null metadata) override);
  let alias_duration = set "name" (str "CustomDuration") duration in
  let alias_value = scalar 3 |> set "type" alias_duration |> set "canonical_value" (Json.int 7) |> set "unit" (str "custom") in
  ignore (accepted (overridden (scalar 2) alias_value));
  let interval_value = interval 2 3 in
  let interval_type = get "type" interval_value in
  ignore (accepted (overridden ~dtype:interval_type interval_value interval_value));
  rejected "invalid_allowed_variation" (with_variation interval_value (bound ~dtype:interval_type interval_value));
  let curve_type = obj ["kind", str "curve"; "name", str "Curve[Duration, Duration]";
                       "dimensions", obj []; "arguments", arr [duration; duration]] in
  let curve = obj ["kind", str "curve"; "type", curve_type; "points", arr [arr [scalar 0; scalar 1]; arr [scalar 2; scalar 3]];
                   "interpolation", str "step"; "extrapolation", str "clamp"] in
  ignore (accepted (overridden ~dtype:curve_type curve curve));
  rejected "invalid_curve" (bound ~dtype:curve_type (set "points" (arr [arr [scalar 2; scalar 1]; arr [scalar 2; scalar 3]]) curve));
  let signal = node ~kind:"signal" ~dtype:Json.Null "signal" in
  let channel = node ~kind:"channel_observation" ~dtype:Json.Null "channel" in
  let observed = accepted (set "intent" (program [signal; channel]) bare) in
  check (List.map Bioc_domain.Identity.Node.to_string (Request.runtime_observations observed) = ["signal"; "channel"])
    "Runtime observations must remain separate from design bindings";
  let target = legacy_target |> set "resources" (obj ["time", scalar 2 |> set "type" short_type |> set "canonical_value" (Json.Float 2.)]) in
  let target_request = accepted (set "target" target bare) in
  check (Request.target_kind target_request = Some Request.Legacy_target) "Lost target schema kind";
  let normalized_target = Option.get (Request.target target_request) in
  same (arr [str "sensing"; str "translation"]) (get "capabilities" normalized_target) "Target capabilities not normalized";
  same (arr [str "cytoplasm"; str "nucleus"]) (get "compartments" normalized_target) "Target compartments not normalized";
  same (scalar 2) (get_at ["resources"; "time"] normalized_target) "Target resource was not reconstructed";
  check (List.mem "target_assumption_validation" (Request.unimplemented_obligations target_request)) "Target declaration became truth";
  rejected "invalid_resource" (set "target" (set "resources" (obj ["time", scalar (-1)]) target) bare);
  rejected "invalid_resource" (set "target" (set "resources" (obj ["time", interval 0 2]) target) bare);
  rejected "duplicate_name" (set "target" (set "capabilities" (arr [str "x"; str "x"]) target) bare);
  rejected "invalid_target" (set "target" (set "compartments" (arr []) target) bare);
  List.iter (fun scope -> ignore (accepted (bare |> set "target" target |> set "artifact_scope" (str scope))))
    ["synthetic_realization"; "exact_cds"; "complete_payload"];
  let original = accepted default in
  let location = obj ["file", str "new/location.py"; "line", Json.int 42; "function", str "build"] in
  let archival = default |> set_at ["intent"; "nodes"; "0"; "source"] location
    |> set_at ["provenance"; "locations"] (obj ["source", str "new/location.py"])
    |> set_at ["provenance"; "recorded_at"] (str "2026-10-01T00:00:00Z") |> accepted in
  check (Request.fingerprint original = Request.fingerprint archival) "Archival locations changed semantic authority";
  check (Request.artifact_fingerprint original <> Request.artifact_fingerprint archival) "Archival locations were omitted from artifact identity";
  List.iter (fun key ->
      let changed = default |> set_at ["provenance"; key] (obj ["content", str "changed"]) |> accepted in
      check (Request.fingerprint original <> Request.fingerprint changed) ("Lost semantic provenance " ^ key))
    ["source_identities"; "dependency_identities"; "external_inputs"];
  rejected "invalid_name" (set_at ["provenance"; "source_identities"] (obj ["", str "identity"]) default);
  rejected "invalid_name" (set_at ["provenance"; "recorded_at"] (str " ") default);
  let constraints = obj ["unknown_obligation", obj ["must_enforce", Json.Bool true]] in
  let preferences = obj ["strategy", str "future-search-policy"] in
  let retained = default |> set "implementation_constraints" constraints |> set "preferences" preferences |> accepted in
  same constraints (obj (Request.implementation_constraints retained)) "Unimplemented constraints were discarded";
  same preferences (obj (Request.preferences retained)) "Unimplemented preferences were discarded";
  check (Request.fingerprint original <> Request.fingerprint retained) "Unimplemented obligations were excluded from identity";
  List.iter (fun key -> check (List.mem key (Request.unimplemented_obligations retained)) ("Lost obligation " ^ key))
    ["implementation_constraint_enforcement"; "preference_evaluation"];
  check (Request.validation_scope = Json.string (get "validation_scope" (Request.summary retained))) "Missing structural validation scope";
  let changed_metadata = default |> set_at ["parameter_metadata"; "duration"; "provenance"] (obj ["method", str "assumed"]) |> accepted in
  check (Request.fingerprint original <> Request.fingerprint changed_metadata) "Binding provenance was stripped from semantic identity";
  same default (Request.to_json (accepted (Request.to_json original))) "Canonical roundtrip changed request";
  check (Bioc_domain.Intent.fingerprint (Request.intent original) = Bioc_domain.Intent.fingerprint (Bioc_domain.Intent.of_json (get "intent" default)))
    "Request changed source authority"

let read_json path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in channel) (fun () ->
      really_input_string channel (in_channel_length channel) |> Json.parse)
let fixtures directory =
  let oracle = read_json (Filename.concat directory "current-baseline-oracle.json") |> get "cases" in
  List.iter (fun variant ->
      let path = Filename.concat (Filename.concat directory variant) "request.json" in
      let raw = read_json path |> get_at ["circuit"; "profile"; "source_request"] in
      let result = accepted raw in
      let expected = get variant oracle in
      check (Request.fingerprint result = Json.string (get "source_request_fingerprint" expected)) (variant ^ " semantic fingerprint differs from Python oracle");
      check (Request.artifact_fingerprint result = Json.string (get "source_request_artifact_fingerprint" expected)) (variant ^ " artifact fingerprint differs from Python oracle");
      same raw (Request.to_json result) (variant ^ " full source request changed during decoding");
      check (Request.target_kind result = Some Request.Human_target) "Case B human target was not decoded";
      check (List.mem "biological_evidence_admission" (Request.unimplemented_obligations result)) "Human declaration implied admission";
      let target_path = ["target"; "human_target"] in
      rejected "invalid_human_target" (set_at (target_path @ ["recipient_taxon_id"]) (Json.int 10090) raw);
      rejected "invalid_human_target" (set_at ["target"; "compartments"] (arr [str "abstract"; str "cytoplasm"]) raw);
      rejected "undeclared_compartment" (set_at (target_path @ ["host_dependencies"; "0"; "compartment"]) (str "extracellular") raw);
      rejected "missing_target_inventory" (set_at (target_path @ ["operating_conditions"]) (arr []) raw);
      rejected "invalid_target_claim" (set_at (target_path @ ["cell_subtype"; "basis"]) (str "cited") raw);
      let claim_path = target_path @ ["cell_subtype"] in
      let cited = raw |> set_at (claim_path @ ["basis"]) (str "cited")
        |> set_at (claim_path @ ["evidence_ids"]) (arr [str "publication"]) in
      rejected "unknown_target_evidence" cited;
      let evidence = obj ["schema_version", str "biocompiler.target_evidence.v0.1"; "id", str "publication";
          "source", obj ["schema_version", str "biocompiler.component_identity.v0.1"; "kind", str "source";
                         "id", str "declared-publication"; "version", str "1"; "content_fingerprint", str (String.make 64 'a')];
          "taxon_id", Json.int 9606; "system", str "primary_human_cells"; "source_context", str "declared cells";
          "locator", str "figure 1"; "limitations", str "No admission is established by this declaration."] in
      let with_evidence = set_at (target_path @ ["evidence"]) (arr [evidence]) cited in
      let declared = accepted with_evidence in
      check (Request.fingerprint declared <> Request.fingerprint result) "Changed human evidence did not affect source identity";
      check (List.mem "biological_evidence_admission" (Request.unimplemented_obligations declared)) "Cited evidence was admitted during decode";
      rejected "invalid_type" (set_at (target_path @ ["evidence"; "0"; "taxon_id"]) Json.Null with_evidence);
      rejected "invalid_evidence_taxon" (set_at (target_path @ ["evidence"; "0"; "system"]) (str "nonhuman_cells") with_evidence);
      rejected "invalid_content_fingerprint" (set_at (target_path @ ["evidence"; "0"; "source"; "content_fingerprint"]) (str (String.make 64 'A')) with_evidence);
      rejected "duplicate_target_record" (set_at (target_path @ ["evidence"]) (arr [evidence; evidence]) cited);
      let host = get_at (target_path @ ["host_dependencies"; "0"]) raw in
      rejected "duplicate_target_record" (set_at (target_path @ ["host_dependencies"]) (arr [host; host]) raw);
      let earlier_host = set "id" (str "a-dependency") host in
      let normalized_inventory = accepted (set_at (target_path @ ["host_dependencies"]) (arr [host; earlier_host]) raw) in
      same (arr [earlier_host; host]) (get_at (target_path @ ["host_dependencies"]) (Request.to_json normalized_inventory))
        "Human target inventory order was not normalized by identity";
      let domain_path = target_path @ ["operating_conditions"; "0"; "domain"] in
      rejected "invalid_value_domain" (set_at (domain_path @ ["lower"]) (Json.int 0) raw);
      let domain = Json.parse {|{"schema_version":"biocompiler.component_value_domain.v0.1","kind":"scalar_interval","dtype":{"kind":"scalar","name":"Level"},"unit":"1","values":[],"lower":0,"upper":1,"reason":null}|} in
      let scalar_domain = accepted (set_at domain_path domain raw) in
      check (Json.equal (get_at (domain_path @ ["dtype"; "arguments"]) (Request.to_json scalar_domain)) (arr [])) "Target value-domain type not normalized";
      rejected "invalid_value_domain" (set_at domain_path (set "lower" (Json.int 2) domain) raw);
      let boolean_domain = Json.parse {|{"schema_version":"biocompiler.component_value_domain.v0.1","kind":"boolean","dtype":{"kind":"condition","name":"Condition"},"unit":"1","values":[true,false],"lower":null,"upper":null,"reason":null}|} in
      let decoded_boolean = accepted (set_at domain_path boolean_domain raw) in
      same (arr [Json.Bool false; Json.Bool true]) (get_at (domain_path @ ["values"]) (Request.to_json decoded_boolean)) "Target Boolean domain order not normalized";
      rejected "invalid_value_domain" (set_at domain_path (set "values" (arr [Json.Bool true; Json.Bool true]) boolean_domain) raw);
      rejected "unknown_field" (set_at ["target"] (set "omitted_obligation" (str "must not disappear") (get "target" raw)) raw))
    ["base"; "parameter-default"; "parameter-override"]

let () =
  if Array.length Sys.argv > 2 then failwith "Usage: test_build_request.exe [case-b-fixture-directory]";
  units ();
  let unit_checks = !checks in
  Printf.printf "build request: %d literal authority/normalization/mutation checks passed\n%!" unit_checks;
  if Array.length Sys.argv = 2 then (
    fixtures Sys.argv.(1);
    Printf.printf "build request: %d retained corpus/oracle/mutation checks passed across 3 request fixtures\n%!" (!checks - unit_checks))

let () =
  let keys value = List.map fst (Json.object_fields value) in
  let reversed value = obj (List.rev (Json.object_fields value)) in
  let target = Request.Target.of_json (reversed legacy_target) in
  check (keys (Request.Target.to_json target) =
    ["schema_version";"context_id";"context_version";"payload_format";
     "capabilities";"compartments";"resources"])
    "Target normalization lost the original public field order";
  check (Canonical.encode (Request.Target.to_json target) =
    Canonical.encode (Request.Target.to_json (Request.Target.of_json legacy_target)))
    "Target ordering changed canonical authority";
  let literal = node ~kind:"literal" ~attributes:["value",scalar 1] "literal" in
  let intent = Bioc_domain.Intent.of_json (program [reversed literal]) in
  let stored = List.hd (Json.array (get "nodes" (Bioc_domain.Intent.to_json intent))) in
  check (keys stored = ["id";"kind";"inputs";"attributes";"data_type";"role";"source"])
    "Intent source metadata moved before original node fields"

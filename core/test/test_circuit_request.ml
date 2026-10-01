open Bioc_wire
module Circuit = Bioc_domain.Circuit_request

let checks = ref 0
let check condition message = incr checks; if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let set key replacement value = obj ((key, replacement) :: List.remove_assoc key (Json.object_fields value))
let rec set_at path replacement value = match path with
  | [] -> replacement
  | key :: tail -> (match value with
      | Json.Array items -> arr (List.mapi (fun index item -> if index = int_of_string key then set_at tail replacement item else item) items)
      | _ -> set key (set_at tail replacement (get key value)) value)
type outcome = Parsed of Json.t * string | Deferred of Json.t * string list
let decode kind value = match kind with
  | "recipient" -> let value = Circuit.Recipient.of_json value in Parsed (Circuit.Recipient.to_json value, Circuit.Recipient.fingerprint value)
  | "experiment" -> let value = Circuit.Experiment.of_json value in Parsed (Circuit.Experiment.to_json value, Circuit.Experiment.fingerprint value)
  | "requirement" -> let value = Circuit.Requirement.of_json value in Parsed (Circuit.Requirement.to_json value, Circuit.Requirement.fingerprint value)
  | "profile" -> (match Circuit.Profile.of_json value with
      | Circuit.Decoded value -> Parsed (Circuit.Profile.to_json value, Circuit.Profile.fingerprint value)
      | Circuit.Unsupported value -> Deferred (Circuit.unsupported_authority value, Circuit.unsupported_reasons value))
  | "circuit_request" -> (match Circuit.of_json value with
      | Circuit.Decoded value -> Parsed (Circuit.to_json value, Circuit.fingerprint value)
      | Circuit.Unsupported value -> Deferred (Circuit.unsupported_authority value, Circuit.unsupported_reasons value))
  | _ -> failwith ("Unknown corpus record kind: " ^ kind)
let accepted kind value = match decode kind value with
  | Parsed (value, fingerprint) -> incr checks; value, fingerprint
  | Deferred _ -> failwith ("Unexpected unsupported " ^ kind)
let rejected kind code value =
  incr checks;
  match decode kind value with
  | _ -> failwith ("Accepted malformed " ^ kind ^ "; expected " ^ code)
  | exception Diagnostic.Error diagnostic ->
      if diagnostic.code <> code then failwith ("Wrong " ^ kind ^ " rejection: " ^ diagnostic.code ^ ", expected " ^ code)

let recipient = obj ["schema_version", str "biocompiler.immune_recipient_identity.v0.1"; "lineage", str "t_cell";
  "target_fingerprint", str (String.make 64 'a'); "cell_subtype_claim_fingerprint", str (String.make 64 'b');
  "eligibility_basis", str "declared"; "empirical_support", str "unestablished"]
let pin = obj ["schema_version", str "biocompiler.component_identity.v0.1"; "kind", str "source";
  "id", str "source"; "version", str "1"; "content_fingerprint", str (String.make 64 'c')]
let experiment = obj ["schema_version", str "biocompiler.human_experiment_context.v0.1";
  "system", str "primary_human_cells"; "immune_classification", str "immune"; "cell_identity", str "declared cell";
  "cell_state", str "unestablished"; "compartment", str "cytoplasm"; "delivery_mode", str "rna_delivery";
  "sources", arr [pin]; "locator", str "fixture"; "assay_conditions", arr [str "explicit unknown"];
  "recipient_taxon_id", Json.int 9606; "immune_lineage", str "t_cell"]
let observation = Json.parse {|{"schema_version":"biocompiler.circuit_observation.v0.1","id":"output","entity":{"schema_version":"biocompiler.observation_entity.v0.1","namespace":"fixture","accession":"declared-product","version":"1","isoform":"unknown"},"quantity":"translation_rate","compartment":"cytoplasm","scope":"evaluator","window":{"schema_version":"biocompiler.observation_window.v0.1","reference":"unknown","start":null,"end":null,"unit":"unknown","aggregation":"unknown"},"encoding":{"schema_version":"biocompiler.observation_encoding.v0.1","mode":"qualitative","unit":"qualitative","low":null,"high":null,"allowed_range":null}}|}
let behavior = obj ["schema_version", str "biocompiler.circuit_behavior.v0.1"; "inputs", arr [];
  "response", obj ["schema_version", str "biocompiler.boolean_spec.v0.1"; "inputs", arr []; "outputs", arr [Json.Bool true]];
  "output", obj ["schema_version", str "biocompiler.circuit_product.v0.1"; "id", str "protein"; "kind", str "protein_expression"; "observation", observation];
  "lifecycle", obj ["schema_version", str "biocompiler.circuit_lifecycle.v0.1"; "mode", str "production_control"; "onset", Json.Null; "cessation", Json.Null; "clearance", Json.Null];
  "dependencies", arr []]
let requirement = obj ["schema_version", str "biocompiler.circuit_requirement.v0.1"; "id", str "required-output";
  "behavior", behavior; "role_id", Json.Null; "source_node_ids", arr []; "source_location", Json.Null; "input_bindings", arr []]
let units () =
  let normalized, _ = accepted "recipient" recipient in
  check (Json.equal recipient normalized) "Recipient roundtrip changed authority";
  rejected "recipient" "invalid_circuit_record" (set "empirical_support" (str "validated") recipient);
  rejected "recipient" "duplicate_key" (obj (("lineage", str "b_cell") :: Json.object_fields recipient));
  rejected "recipient" "nonfinite_number" (set "unexpected" (Json.Float infinity) recipient);
  rejected "recipient" "profile_resource_limit" (set "unexpected" (str (String.make 16_385 'x')) recipient);
  let _, _ = accepted "experiment" experiment in
  rejected "experiment" "invalid_type" (set "recipient_taxon_id" (Json.Bool true) experiment);
  rejected "experiment" "invalid_circuit_record" (set "recipient_taxon_id" (Json.int 10090) experiment);
  rejected "experiment" "invalid_circuit_record" (set "sources" (arr [pin; pin]) experiment);
  let requirement_json, requirement_fingerprint = accepted "requirement" requirement in
  check (Json.equal requirement_json requirement) "Requirement roundtrip changed nominal authority";
  let restored, fingerprint = accepted "requirement" requirement_json in
  check (Json.equal restored requirement_json && fingerprint = requirement_fingerprint) "Requirement identity changed on replay";
  let target = ["behavior"; "output"; "observation"] in
  rejected "requirement" "invalid_circuit_record" (set_at ["behavior"; "lifecycle"; "mode"] (str "readout") requirement);
  rejected "requirement" "invalid_type" (set_at ["behavior"; "response"; "outputs"] (arr [Json.int 1]) requirement);
  rejected "requirement" "observation_resource_limit" (set_at (target @ ["entity"; "accession"]) (str (String.make 513 'x')) requirement);
  rejected "requirement" "invalid_circuit_record" (set_at (target @ ["id"]) (str "\194\160output") requirement);
  rejected "requirement" "invalid_circuit_record" (set_at (target @ ["entity"; "accession"]) (str "line\nbreak") requirement);
  let unicode = String.concat "" (List.init 256 (fun _ -> "\194\181")) in
  ignore (accepted "requirement" (set_at (target @ ["entity"; "accession"]) (str unicode) requirement));
  let decoded = Circuit.Requirement.of_json requirement in
  check (Circuit.Requirement.executable_behavior decoded = None) "Invented executable behavior from a Boolean table";
  check (Circuit.Requirement.action_ids decoded = []) "Invented source actions";
  check (List.mem "supplementary_output_source_correspondence" (Circuit.Requirement.unimplemented_obligations decoded)) "Structural decode implied source fidelity";
  let profile = obj ["schema_version", str "biocompiler.circuit_profile_request.v0.1"; "purpose", str "human_reference";
    "mode", str "exact_reproduction"; "molecular_form", str "DNA"; "boundary", str "import";
    "target", Json.Null; "recipient", Json.Null; "source_request", Json.Null; "source_experiment", experiment] in
  let normalized, _ = accepted "profile" profile in
  check (Json.equal normalized profile) "Historical profile changed source context";
  (match Circuit.Profile.of_json profile with
   | Circuit.Decoded value -> check (List.mem "historical_reference_scope" (Circuit.Profile.unimplemented_obligations value)) "Historical DNA expanded the therapeutic target"
   | Circuit.Unsupported _ -> failwith "Historical declarations should decode structurally");
  rejected "profile" "invalid_circuit_record" (set "mode" (str "candidate_design") profile);
  let realization = pin |> set "kind" (str "reference") |> set "id" (str "reference") in
  let lock = obj ["schema_version", str "biocompiler.circuit_reference_lock.v0.1";
    "expected_behaviors", arr [obj ["schema_version", str "biocompiler.circuit_behavior_expectation.v0.1"; "requirement_id", str "required-output"; "behavior", behavior]];
    "realization", realization; "authority", arr [pin]; "source_experiment", experiment;
    "requested_form", str "delivered_dna"; "fidelity_scope", str "complete_nominal"] in
  let request = obj ["schema_version", str Circuit.schema_version; "profile", profile; "requirements", arr [requirement];
    "requested_form", str "delivered_dna"; "fidelity_scope", str "complete_nominal"; "deployment_id", Json.Null;
    "selected_realization", realization; "reference_lock", lock] in
  let normalized, _ = accepted "circuit_request" request in
  check (Json.equal normalized request) "Reference lock authority changed on import";
  rejected "circuit_request" "invalid_circuit_record" (set "reference_lock" Json.Null request);
  rejected "circuit_request" "invalid_circuit_record" (set_at ["requirements"; "0"; "behavior"; "response"; "outputs"] (arr [Json.Bool false]) request)

let read_json path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in channel) (fun () ->
      let length = in_channel_length channel in
      check (length <= Limits.max_request_bytes) "Request corpus exceeds native wire byte budget";
      really_input_string channel length |> Json.parse)
let corpus path =
  let document = read_json path in
  check (get "schema_version" document = str "biocompiler.request_domains_conformance.v1") "Wrong request corpus schema";
  let cases = Json.array (get "cases" document) and rejections = Json.array (get "rejections" document) in
  check (List.length cases >= 46 && List.length rejections >= 65) "Incomplete request conformance corpus";
  let coverage = get "coverage" document in
  let kinds = List.map (fun item -> Json.string (get "record_kind" item)) cases |> List.sort_uniq String.compare in
  let declared key = Json.array (get key coverage) |> List.map Json.string |> List.sort String.compare in
  let supported = List.sort String.compare ["recipient"; "experiment"; "profile"; "requirement"; "circuit_request"] in
  check (kinds = supported && declared "supported_record_kinds" = supported && declared "covered_record_kinds" = kinds)
    "Request corpus omits or misstates a supported record kind";
  let unsupported_cases = List.filter (fun item -> get "expected_outcome" item = str "unsupported") rejections in
  let unsupported_schemas = List.map (fun item -> get "input" item |> get "source_request" |> get "schema_version" |> Json.string) unsupported_cases
    |> List.sort_uniq String.compare in
  let required_wrappers = ["biocompiler.human_acceptance_request.v0.1"; "biocompiler.human_behavior_request.v0.1"; "biocompiler.human_deployment_request.v0.1"] in
  check (unsupported_schemas = required_wrappers && declared "deferred_source_schemas" = required_wrappers)
    "Request corpus omits a deferred source wrapper";
  let variants = get "variants" coverage in
  let count key actual = check (Z.equal (Json.integer (get key variants)) (Z.of_int actual)) ("Incorrect corpus census: " ^ key) in
  count "positive_cases" (List.length cases);
  count "unsupported_cases" (List.length unsupported_cases);
  count "invalid_cases" (List.length rejections - List.length unsupported_cases);
  let identities = List.map (fun item -> Json.string (get "id" item)) (cases @ rejections) in
  check (List.length identities = List.length (List.sort_uniq String.compare identities)) "Duplicate request corpus identity";
  List.iter (fun case ->
      let id = Json.string (get "id" case) and kind = Json.string (get "record_kind" case) in
      let actual, fingerprint = accepted kind (get "input" case) in
      check (Json.equal actual (get "normalized" case)) (id ^ ": normalized authority differs from Python");
      check (fingerprint = Json.string (get "fingerprint" case)) (id ^ ": fingerprint differs from Python");
      let replay, replay_fingerprint = accepted kind actual in
      check (Json.equal actual replay && replay_fingerprint = fingerprint) (id ^ ": replay changed authority")) cases;
  List.iter (fun case ->
      let id = Json.string (get "id" case) and kind = Json.string (get "record_kind" case)
      and expected = Json.string (get "expected_code" case) and input = get "input" case in
      match Json.string (get "expected_outcome" case) with
      | "invalid" -> (try rejected kind expected input with Failure message -> failwith (id ^ ": " ^ message))
      | "unsupported" -> (match decode kind input with
          | Parsed _ -> failwith (id ^ ": unsupported authority constructed a validated value")
          | Deferred (authority, reasons) ->
              check (Json.equal authority input) (id ^ ": unsupported original authority was discarded or normalized");
              check (List.mem expected reasons) (id ^ ": wrong unsupported reason"))
      | _ -> failwith (id ^ ": unknown expected outcome")) rejections;
  Printf.printf "circuit request: %d corpus positives and %d intended invalid/unsupported cases passed\n%!" (List.length cases) (List.length rejections)
let () =
  if Array.length Sys.argv > 2 then failwith "Usage: test_circuit_request.exe [request-domains-v1.json]";
  units ();
  Printf.printf "circuit request: %d literal checks passed\n%!" !checks;
  if Array.length Sys.argv = 2 then corpus Sys.argv.(1)

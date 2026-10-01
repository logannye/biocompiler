open Bioc_wire
module A = Bioc_domain.Architecture_contract
module D = Bioc_domain.Architecture_deployment
module C = Bioc_domain.Circuit_request
module I = Bioc_domain.Identity
let count = ref 0
let check condition message = incr count; if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let field key value = Json.field key (Json.object_fields value)
let reject label code run =
  incr count;
  match run () with
  | _ -> failwith (label ^ ": intended rejection accepted")
  | exception Diagnostic.Error error -> if error.code <> code then failwith
      (label ^ ": expected " ^ code ^ ", received " ^ error.code ^ ": " ^ error.message)
let node = I.Node.of_string
let role = I.Role.of_string
let component = I.Component.of_string
let kinds = ["binding"; "channel"; "connection"; "constraints"; "control"; "control_requirement";
             "delivery_group"; "helper"; "instance"; "match_policy"; "output_binding"; "placement"]
let decode kind raw = match kind with
  | "binding" -> A.Binding.of_json raw |> A.Binding.to_json
  | "connection" -> A.Connection.of_json raw |> A.Connection.to_json
  | "placement" -> A.Placement.of_json raw |> A.Placement.to_json
  | "control" -> A.Control.of_json raw |> A.Control.to_json
  | "control_requirement" -> A.Control_requirement.of_json raw |> A.Control_requirement.to_json
  | "helper" -> A.Helper.of_json raw |> A.Helper.to_json
  | "channel" -> A.Channel.of_json raw |> A.Channel.to_json
  | "output_binding" -> A.Output_binding.of_json raw |> A.Output_binding.to_json
  | "delivery_group" -> A.Delivery_group.of_json raw |> A.Delivery_group.to_json
  | "constraints" -> A.Constraints.of_json raw |> A.Constraints.to_json
  | "match_policy" -> A.Match_policy.of_json raw |> A.Match_policy.to_json
  | "instance" -> A.Instance.of_json raw |> A.Instance.to_json
  | _ -> failwith ("Unknown architecture leaf kind " ^ kind)
let constraint_record ?(groups = []) ?(controls = []) ?(deployment = []) () =
  A.Constraints.make ~exact_count:(Some 0) ~max_count:(Some 0) ~max_member_bases:None ~max_total_bases:(Some 0)
    ~delivery_groups:groups ~control_requirements:controls ~preferred_refinement_ids:["z"; "a"]
    ~max_combinations:1 ~require_complete:false ~max_match_states:1 ~max_match_instances:1 ~deployment_requirements:deployment
let channel initial_value = A.Channel.make ~id:"channel" ~source_channel_id:(node "channel-node")
    ~sender_role:(role "sender") ~receiver_role:(role "receiver") ~sender_node_id:(node "send") ~receiver_node_id:(node "receive")
    ~latency_seconds:(D.Time.of_json (Json.Float (-0.))) ~persistence_seconds:None ~failure_mode:A.Channel.Unknown
    ~aggregation:A.Channel.Single_sender ~initial_value ~assumptions:["supplied"]
let literals () =
  let binding = A.Binding.make ~id:"binding" ~behavior_node_ids:[node "z"; node "a"]
      ~component_ids:[component "component"] ~template_ids:["template"] ~placement_ids:["placement"] in
  check (List.map I.Node.to_string (A.Binding.behavior_node_ids binding) = ["a"; "z"]) "Binding names did not sort";
  let binding_json = A.Binding.to_json binding in
  let connection = A.Connection.make ~id:"connection" ~producer_component_id:(component "same") ~producer_port_id:"port"
      ~consumer_component_id:(component "same") ~consumer_port_id:"port" in
  let connection_literal = Json.parse {|{"schema_version":"biocompiler.architecture_connection.v0.1","id":"connection","producer_component_id":"same","producer_port_id":"port","consumer_component_id":"same","consumer_port_id":"port"}|} in
  check (Canonical.encode (A.Connection.to_json connection) = Canonical.encode connection_literal) "Independent full connection literal differs";
  let placement = A.Placement.make ~id:"placement" ~template_id:"template" ~member_id:"member" ~recipient_role:(role "recipient")
      ~compartment:"abstract" ~delivery_group:"missing-group" in
  check (A.Placement.compartment placement = "abstract") "Placement import performed target feasibility checks";
  let control = A.Control.make ~id:"control" ~kind:A.Shutdown ~behavior_node_ids:[node "action"] ~controlling_node_ids:[]
      ~component_ids:[component "component"] ~domain_id:"domain" ~assumptions:["supplied"] in
  check (A.Control.controlling_node_ids control = []) "Control invents a controlling node";
  let requirement = A.Control_requirement.make ~id:"requirement" ~kind:A.Shutdown ~behavior_node_ids:[node "action"]
      ~relation:A.Control_requirement.Independent ~forbidden_shared_dependencies:["z"; "a"] in
  check (A.Control_requirement.forbidden_shared_dependencies requirement = ["a"; "z"]) "Dependency inventory did not normalize";
  let helper = A.Helper.make ~id:"helper" ~capability:"capability" ~consumer_component_ids:[component "a"; component "b"]
      ~recipient_role:(role "recipient") ~compartment:"abstract" ~availability:A.Helper.Host ~initialization:A.Helper.After_trigger
      ~sharing:A.Helper.Exclusive ~capacity:1 ~assumptions:["supplied"] ~placement_id:None ~provider_component_id:None ~depends_on:["helper"] in
  check (A.Helper.depends_on helper = ["helper"] && List.length (A.Helper.consumer_component_ids helper) > A.Helper.capacity helper)
    "Import silently discharged contextual helper cycle/capacity obligations";
  let initial = obj ["typed_later", arr [Json.Bool false; Json.Null; Json.int 0; Json.Float 0.; Json.Float (-0.)]] in
  let transport = channel initial in
  check (Canonical.encode (A.Channel.initial_value transport) = Canonical.encode initial) "Complete initial declaration changed";
  check (Canonical.encode (D.Time.to_json (A.Channel.latency_seconds transport)) = "-0.0" && A.Channel.persistence_seconds transport = None)
    "Channel numeric kind or unknown persistence changed";
  let product = C.Product.of_json (Json.parse {|{"schema_version":"biocompiler.circuit_product.v0.1","id":"protein","kind":"protein_expression","observation":{"schema_version":"biocompiler.circuit_observation.v0.1","id":"output","entity":{"schema_version":"biocompiler.observation_entity.v0.1","namespace":"fixture","accession":"product","version":"1","isoform":"unknown"},"quantity":"translation_rate","compartment":"cytoplasm","scope":"evaluator","window":{"schema_version":"biocompiler.observation_window.v0.1","reference":"unknown","start":null,"end":null,"unit":"unknown","aggregation":"unknown"},"encoding":{"schema_version":"biocompiler.observation_encoding.v0.1","mode":"qualitative","unit":"qualitative","low":null,"high":null,"allowed_range":null}}}|}) in
  let lifecycle = C.Lifecycle.of_json (Json.parse {|{"schema_version":"biocompiler.circuit_lifecycle.v0.1","mode":"readout","onset":null,"cessation":null,"clearance":null}|}) in
  let output = A.Output_binding.make ~id:"output" ~requirement_id:(I.Requirement.of_string "required") ~action_ids:[node "action"] ~product ~lifecycle in
  check (C.Product.kind (A.Output_binding.product output) = "protein_expression" && C.Lifecycle.mode (A.Output_binding.lifecycle output) = "readout")
    "Output import performed contextual product/lifecycle pairing";
  let group = A.Delivery_group.make ~id:"group" ~recipient_roles:[role "recipient"] ~mode:A.Delivery_group.Independent
      ~same_recipient:false ~assumptions:["supplied"] ~exact_count:(Some 0) ~max_count:(Some 0) ~max_total_bases:(Some 0) in
  check (not (A.Delivery_group.same_recipient group) && A.Delivery_group.exact_count group = Some 0) "False and zero declarations changed";
  let constraints = constraint_record ~groups:[group] ~controls:[requirement] () in
  check (A.Constraints.exact_count constraints = Some 0 && A.Constraints.max_member_bases constraints = None
    && not (A.Constraints.require_complete constraints)) "Unknown, zero and false constraints collapsed";
  reject "duplicate typed delivery identity" "invalid_architecture_contract" (fun () -> constraint_record ~groups:[group;group] ());
  reject "duplicate typed control identity" "invalid_architecture_contract" (fun () -> constraint_record ~controls:[requirement;requirement] ());
  let deployment = D.Requirement.make ~id:"deployment" ~delivery_group_id:"missing" ~recipient_role:"recipient"
      ~compartment:"abstract" ~required_from:D.Time.zero ~required_until:(D.Time.of_json (Json.int 1))
      ~unavailable_after:None ~require_same_recipient:false ~assumptions:["supplied"] in
  reject "duplicate typed deployment identity" "invalid_architecture_contract" (fun () -> constraint_record ~deployment:[deployment;deployment] ());
  let policy = A.Match_policy.make ~mode:A.Match_policy.Exact_semantic_subgraph in
  check (Canonical.encode (A.Match_policy.to_json policy) = {|{"mode":"exact_semantic_subgraph","schema_version":"biocompiler.architecture_match_policy.v0.1"}|})
    "Independent complete match policy differs";
  let instance = A.Instance.make ~id:"instance" ~refinement_id:"refinement" ~source_bindings:[node "z",node "b"; node "a",node "c"] in
  check (List.map (fun (key, value) -> I.Node.to_string key, I.Node.to_string value) (A.Instance.source_bindings instance) = ["a","c";"z","b"])
    "Injective correspondence did not sort";
  reject "noninjective typed mapping" "invalid_architecture_contract" (fun () -> A.Instance.make ~id:"bad" ~refinement_id:"r"
      ~source_bindings:[node "a",node "x"; node "b",node "x"]);
  reject "duplicate typed mapping key" "duplicate_key" (fun () -> A.Instance.make ~id:"bad" ~refinement_id:"r"
      ~source_bindings:[node "a",node "x"; node "a",node "y"]);
  reject "duplicate raw field" "duplicate_key" (fun () -> A.Binding.of_json (obj (("id",str "other") :: Json.object_fields binding_json)));
  reject "nonfinite initial declaration" "nonfinite_number" (fun () -> channel (Json.Float infinity));
  reject "invalid UTF8 initial declaration" "invalid_utf8" (fun () -> channel (str "\255"));
  let rec cycle = Json.Array [cycle] in
  List.iter (fun kind -> reject ("raw cycle " ^ kind) "molecular_cycle" (fun () -> decode kind cycle)) kinds;
  reject "constructor initial value cycle" "molecular_cycle" (fun () -> channel cycle);
  let rec node_spine = node "same" :: node_spine in
  reject "typed node list cycle" "molecular_resource_limit" (fun () -> A.Binding.make ~id:"binding" ~behavior_node_ids:node_spine
      ~component_ids:[component "c"] ~template_ids:["t"] ~placement_ids:["p"]);
  let rec group_spine = group :: group_spine in
  reject "typed group list cycle" "molecular_resource_limit" (fun () -> constraint_record ~groups:group_spine ());
  let rec mapping_spine = (node "a",node "b") :: mapping_spine in
  reject "typed mapping cycle" "molecular_resource_limit" (fun () -> A.Instance.make ~id:"instance" ~refinement_id:"r" ~source_bindings:mapping_spine);
  let repeated = str (String.make 1_000_000 'x') in
  reject "aggregate initial byte expansion" "molecular_resource_limit" (fun () -> channel (arr [repeated;repeated;repeated;repeated]));
  reject "escaping published bytes" "molecular_resource_limit" (fun () -> channel (str (String.make 700_000 '\001')));
  Printf.printf "architecture leaves: %d independent constructor, context-boundary and resource checks passed\n" !count
let read_json path =
  check (not (Filename.is_relative path)) "Architecture corpus path must be absolute";
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let bytes = in_channel_length channel in
      check (bytes <= Limits.max_request_bytes) "Architecture corpus exceeds read limit";
      Json.parse (really_input_string channel bytes))
let retained path =
  let corpus = read_json path in
  check (field "schema_version" corpus = str "biocompiler.architecture_contracts_conformance.v1") "Wrong architecture corpus schema";
  let records = Json.array (field "records" corpus) and rejections = Json.array (field "rejections" corpus)
  and literals = Json.array (field "literal_expectations" corpus) and coverage = field "coverage" corpus in
  check (List.length records = 88 && List.length rejections = 345 && List.length literals = 4) "Incomplete architecture corpus";
  check (field "positive_count" coverage = Json.int 88 && field "rejection_count" coverage = Json.int 345
      && field "independent_literal_count" coverage = Json.int 4) "Incorrect architecture census";
  let actual_kinds = List.map (fun item -> Json.string (field "kind" item)) records |> List.sort_uniq String.compare in
  check (actual_kinds = kinds && field "record_kinds" coverage = arr (List.map str kinds)) "Missing architecture leaf kind";
  let ids = List.map (fun item -> Json.string (field "id" item)) (records @ rejections) in
  check (List.length ids = List.length (List.sort_uniq String.compare ids)) "Duplicate architecture fixture identity";
  let pin key expected value = check (Canonical.fingerprint value = expected && field key corpus = str expected) ("Changed architecture inventory " ^ key) in
  pin "case_ids_sha256" "96f988d6d2fe3d088d6a0301d6928b671c269bd47e399195475fc68418096b8e" (arr (List.sort String.compare ids |> List.map str));
  let signatures = List.map (fun item -> List.map (fun key -> Json.string (field key item)) ["id";"kind";"expected_code"]) rejections
    |> List.sort Stdlib.compare |> List.map (fun row -> arr (List.map str row)) |> arr in
  pin "rejections_sha256" "cf9b3ccf61a6084aeb68c1f0ac2f68d76f3cff82a070d86a552c89489e3c010b" signatures;
  pin "literals_sha256" "32ed4c6ba038b8c2aebc603d2659c3ea0cee5ca5d3a39e0ac6da4d88b9d116a5" (arr literals);
  List.iter (fun item ->
      let identity = Json.string (field "id" item) and kind = Json.string (field "kind" item) in
      let normalized = decode kind (field "input" item) in
      check (Canonical.encode normalized = Canonical.encode (field "normalized" item)) (identity ^ ": full authority differs");
      check (str (Canonical.fingerprint normalized) = field "fingerprint" item) (identity ^ ": fingerprint differs");
      check (Canonical.encode (decode kind normalized) = Canonical.encode normalized) (identity ^ ": repeated import changes authority")) records;
  List.iter (fun item -> reject (Json.string (field "id" item)) (Json.string (field "expected_code" item))
      (fun () -> decode (Json.string (field "kind" item)) (field "input" item))) rejections;
  List.iter (fun literal ->
      let item = List.find (fun item -> field "id" item = field "id" literal) records in
      let actual = decode (Json.string (field "kind" item)) (field "input" item) in
      check (Canonical.encode actual = Canonical.encode (field "normalized" literal)) "Independent complete architecture literal differs") literals;
  print_endline "architecture leaves corpus: 88 complete records, 345 intended failures, four independent literals, all 12 schemas passed"
let () = match Array.to_list Sys.argv with
  | [_] -> literals ()
  | [_; path] -> literals (); retained path
  | _ -> failwith "Usage: test_architecture_contract.exe [<absolute-architecture-contracts-v1.json>]"

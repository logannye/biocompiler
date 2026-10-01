open Bioc_wire
module C = Bioc_domain.Component
module Contracts = Bioc_domain.Component_contract
module V = Contracts.Value_domain
module P = Contracts.Port
module O = Contracts.Operating_domain
module T = Bioc_domain.Type_spec
module N = Bioc_domain.Runtime_number

let count = ref 0
let check condition message = incr count; if not condition then failwith message
let reject code run =
  incr count;
  match run () with
  | _ -> failwith ("Expected component rejection " ^ code)
  | exception Diagnostic.Error diagnostic -> if diagnostic.code <> code then
      failwith ("Expected " ^ code ^ ", received " ^ diagnostic.code)
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let set key replacement value = obj ((key,replacement) :: List.remove_assoc key (Json.object_fields value))
let number = N.of_int
let level = T.of_json (Json.parse {|{"kind":"scalar","name":"Level"}|})
let boolean = T.of_json (Json.parse {|{"kind":"condition","name":"Condition"}|})
let both = V.boolean ()
let no = V.boolean ~values:[false] ()
let pin ?(kind = C.Pinned_identity.Model) identity =
  C.Pinned_identity.make ~kind ~id:identity ~version:"1" ~content_fingerprint:(String.make 64 'a')
let port ?(initialization = both) ?(domain = both) ?(timing = P.Stateless) id direction =
  P.make ~id ~direction ~meaning:"meaning" ~dtype:boolean ~unit:"1" ~role:"cell" ~scope:P.Cell ~compartment:"abstract" ~timing ~initialization ~domain
let component ?(classification = C.Synthetic_model) ?(implementation_role = "historical") ?(ports = []) ?(identities = [pin "model"])
    ?(parameters = []) ?(dependencies = []) ?(capabilities = []) ?(resources = []) ?reference_metadata ?synthetic_model () =
  C.make ~id:"component" ~version:"1" ~classification ~implementation_role ~supported_targets:["RNA";"synthetic"]
    ~ports ~supported_domain:(O.make []) ~identities ~assumptions:["second";"first"] ~guarantees:[] ~evidence:[]
    ~parameters ~dependencies ~capabilities ~resources ~reference_metadata ~synthetic_model
let literals () =
  let shared : Bioc_domain.Pinned_identity.t = pin "same" in
  check (C.Pinned_identity.to_json shared = Bioc_domain.Pinned_identity.to_json shared) "Component pins are not the shared abstract type";
  let historical = component () in
  let historical_literal = Json.parse {|{"schema_version":"biocompiler.component_record.v0.2","id":"component","version":"1","classification":"synthetic_model","implementation_role":"historical","supported_targets":["RNA","synthetic"],"ports":[],"supported_domain":{"schema_version":"biocompiler.component_operating_domain.v0.1","constraints":{}},"identities":[{"schema_version":"biocompiler.component_identity.v0.1","kind":"model","id":"model","version":"1","content_fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}],"assumptions":["second","first"],"guarantees":[],"evidence":[],"parameters":[],"dependencies":[],"capabilities":[],"resources":[],"reference_metadata":null,"synthetic_model":null}|} in
  check (Canonical.encode (C.to_json historical) = Canonical.encode historical_literal) "Complete independent historical literal differs";
  check (C.synthetic_model historical = None && C.classification historical = C.Synthetic_model) "Historical absent executable model was rejected";
  check (C.supported_targets historical = ["RNA";"synthetic"] && C.assumptions historical = ["second";"first"])
    "Order-preserving declarations were sorted";
  let ordered = component ~ports:[port "z" P.Output;port "a" P.Input] ~identities:[pin ~kind:C.Pinned_identity.Source "z";pin "a"] () in
  check (List.map P.id (C.ports ordered) = ["a";"z"] && List.map C.Pinned_identity.id (C.identities ordered) = ["a";"z"])
    "ID-bearing arrays did not normalize";
  check (Option.is_some (C.port ordered "a") && C.port ordered "absent" = None) "Port lookup changed";
  reject "component_record" (fun () -> component ~identities:[pin "same";pin ~kind:C.Pinned_identity.Source "same"] ());
  let reference = C.Sequence_reference.make ~artifact_class:C.Sequence_reference.Coding_rna
      ~sequence_length:(Z.of_string "10000000000000000000000000000000000000000") ~unknown_features:["tail";"promoter"] in
  check (C.Sequence_reference.sequence_length reference = Z.of_string "10000000000000000000000000000000000000000") "Reference length was machine-truncated";
  check (C.Sequence_reference.completeness reference = "CDS-reference-only") "Reference scope changed";
  let parameter = C.Parameter.make ~id:"p" ~value:both ~source:(pin "model") ~method_name:"declared only" in
  let sequence = component ~classification:C.Sequence_reference ~identities:[pin ~kind:C.Pinned_identity.Reference "ref"] ~reference_metadata:reference ~parameters:[parameter] () in
  check (List.length (C.parameters sequence) = 1 && C.Parameter.method_name parameter = "declared only")
    "Historical reference parameter/pin declaration was tightened";
  reject "component_record" (fun () -> component ~classification:C.Sequence_reference ~identities:[pin ~kind:C.Pinned_identity.Reference "ref"] ~reference_metadata:reference ~ports:[port "out" P.Output] ());
  let resource amount = C.Resource.make ~id:"budget" ~resource:"capacity" ~amount ~unit:"custom" ~dtype:level ~reusable:false
      ~role:"cell" ~scope:C.Contact ~compartment:"abstract" in
  check (C.Resource.amount (resource None) = None) "Unknown resource became zero";
  check (Canonical.encode (get "amount" (C.Resource.to_json (resource (Some (N.Real (-0.)))))) = "-0.0") "Resource signed zero was erased";
  reject "component_record" (fun () -> resource (Some (number (-1))));
  let dep = C.Dependency.make ~id:"need" ~capability:"unprovided" ~role:"cell" ~scope:C.Cell ~compartment:"abstract" ~required:true in
  let declared = component ~dependencies:[dep] ~resources:[resource None] () in
  check (C.Dependency.required (List.hd (C.dependencies declared))) "Component parsing silently discharged a provider obligation";
  let declaration = C.Synthetic_operator.make ~operation:Contracts.Constant ~attributes:(obj ["value",str "context pending"])
      ~input_ports:["extra"] ~output_port:"out" in
  check (C.Synthetic_operator.operation declaration = Contracts.Constant) "Standalone declaration was contextually overvalidated";
  reject "component_record" (fun () -> component ~implementation_role:"constant" ~synthetic_model:declaration ~ports:[port "extra" P.Input;port "out" P.Output] ());
  let constant = C.Synthetic_operator.make ~operation:Contracts.Constant ~attributes:(obj ["value",Json.Bool true]) ~input_ports:[] ~output_port:"out" in
  let executable = component ~implementation_role:"constant" ~synthetic_model:constant ~ports:[port "out" P.Output] () in
  let assessments = C.Synthetic_operator.domain_checks constant ~ports:(C.ports executable) ~supported_domain:(C.supported_domain executable) in
  check (List.length assessments = 2 && List.for_all Contracts.passed assessments) "Runtime and initialization checks missing";
  let conflicting_ports = [port ~initialization:no ~domain:no "out" P.Output; port "out" P.Output] in
  reject "component_record" (fun () -> C.Synthetic_operator.validate_ports constant ~ports:conflicting_ports ~supported_domain:(O.make []));
  reject "component_record" (fun () -> C.Synthetic_operator.domain_checks constant ~ports:conflicting_ports ~supported_domain:(O.make []));
  reject "component_record" (fun () -> component ~implementation_role:"constant" ~synthetic_model:constant ~ports:[port ~initialization:no ~domain:no "out" P.Output] ());
  let output = C.Synthetic_operator.make ~operation:Contracts.Output ~attributes:(obj []) ~input_ports:["in"] ~output_port:"out" in
  let unknown = V.unknown ~dtype:boolean ~unit:"1" ~reason:"unobserved" in
  let ports = [port ~initialization:unknown ~domain:unknown "in" P.Input;port "out" P.Output] in
  ignore (component ~implementation_role:"output" ~synthetic_model:output ~ports ());
  check (List.for_all (fun result -> Contracts.status result = Contracts.Unknown)
    (C.Synthetic_operator.domain_checks output ~ports ~supported_domain:(O.make []))) "Unknown became successful proof";
  let onset = C.Synthetic_operator.make ~operation:Contracts.Onset ~attributes:(obj []) ~input_ports:["in"] ~output_port:"out" in
  let ports = [port ~timing:P.Temporal_level "in" P.Input;port ~timing:P.Temporal_event "out" P.Output] in
  ignore (component ~implementation_role:"onset" ~synthetic_model:onset ~ports ());
  reject "component_record" (fun () -> component ~implementation_role:"onset" ~synthetic_model:onset
    ~ports:[port ~timing:P.Temporal_level "in" P.Input;port ~timing:P.Temporal_level "out" P.Output] ());
  let literal = Json.parse {|{"kind":"scalar","type":{"kind":"scalar","name":"Duration","dimensions":{"time":1},"arguments":[]},"value":2,"unit":"min","canonical_value":120.0}|} in
  let duration = T.of_json (get "type" literal) in
  let domain = V.interval ~lower:(number 0) ~upper:(number 200) ~dtype:duration ~unit:"s" in
  let port = P.make ~id:"out" ~direction:P.Output ~meaning:"meaning" ~dtype:duration ~unit:"s" ~role:"cell" ~scope:P.Cell ~compartment:"abstract"
      ~timing:P.Stateless ~initialization:domain ~domain in
  let model = C.Synthetic_operator.make ~operation:Contracts.Constant ~attributes:(obj ["value",literal]) ~input_ports:[] ~output_port:"out" in
  let preserved = component ~implementation_role:"constant" ~synthetic_model:model ~ports:[port] () in
  let attributes = C.synthetic_model preserved |> Option.get |> C.Synthetic_operator.attributes in
  check (Canonical.encode (get "canonical_value" (get "value" attributes)) = "120.0") "Numerically equal canonical spelling was normalized without authority"
let boundary_literals () =
  let value = C.to_json (component ()) in
  reject "missing_field" (fun () -> C.of_json (obj (List.remove_assoc "synthetic_model" (Json.object_fields value))));
  reject "unknown_field" (fun () -> C.of_json (set "accepted" (Json.Bool true) value));
  reject "duplicate_key" (fun () -> C.of_json (obj (("id",str "other") :: Json.object_fields value)));
  reject "invalid_utf8" (fun () -> C.of_json (set "id" (str "\255") value));
  reject "nonfinite_number" (fun () -> C.of_json (set "synthetic_model" (Json.Float nan) value));
  let repeated = str (String.make Limits.max_string_bytes 'x') in
  reject "component_resource_limit" (fun () -> C.of_json (set "assumptions" (arr (List.init 9 (fun _ -> repeated))) value));
  reject "component_resource_limit" (fun () -> C.of_json (set "ports" (arr (List.init Limits.max_json_nodes (fun _ -> Json.Null))) value));
  let deep = List.fold_left (fun value _ -> arr [value]) Json.Null (List.init (Limits.max_depth+1) Fun.id) in
  reject "component_resource_limit" (fun () -> C.of_json (set "reference_metadata" deep value));
  let rec cycle = Json.Object ["cycle",cycle] in
  reject "component_resource_limit" (fun () -> C.of_json (set "synthetic_model" cycle value));
  let rec inputs = "input" :: inputs in
  reject "component_resource_limit" (fun () -> C.Synthetic_operator.make ~operation:Contracts.Input ~attributes:(obj []) ~input_ports:inputs ~output_port:"out")
let normalize kind value = match kind with
  | "pin" -> C.Pinned_identity.to_json (C.Pinned_identity.of_json value), []
  | "synthetic_operator" -> C.Synthetic_operator.to_json (C.Synthetic_operator.of_json value), []
  | "parameter" -> C.Parameter.to_json (C.Parameter.of_json value), []
  | "dependency" -> C.Dependency.to_json (C.Dependency.of_json value), []
  | "capability" -> C.Capability.to_json (C.Capability.of_json value), []
  | "resource" -> C.Resource.to_json (C.Resource.of_json value), []
  | "sequence_reference" -> C.Sequence_reference.to_json (C.Sequence_reference.of_json value), []
  | "component" ->
      let value = C.of_json value in
      let checks = Option.fold ~none:[] ~some:(fun model -> C.Synthetic_operator.domain_checks model ~ports:(C.ports value) ~supported_domain:(C.supported_domain value)) (C.synthetic_model value) in
      C.to_json value, List.map Contracts.assessment_to_json checks
  | _ -> failwith "Unknown component record kind"
let read_json path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let length = in_channel_length channel in
      if length > Limits.max_request_bytes then failwith "Components corpus exceeds byte limit";
      Json.parse (really_input_string channel length))
let corpus path =
  let document = read_json path in
  check (get "schema_version" document = str "biocompiler.components_conformance.v1") "Wrong components corpus schema";
  let cases = Json.array (get "cases" document) and rejected = Json.array (get "rejections" document) and coverage = get "coverage" document in
  check (List.length cases = 60 && List.length rejected = 112) "Truncated components corpus";
  check (get "positive_count" coverage = Json.int 60 && get "rejection_count" coverage = Json.int 112) "Wrong component census";
  let kinds = List.map (fun item -> Json.string (get "record_kind" item)) cases |> List.sort_uniq String.compare in
  check (kinds = ["capability";"component";"dependency";"parameter";"pin";"resource";"sequence_reference";"synthetic_operator"]) "Missing component schema";
  check (get "record_kinds" coverage = arr (List.map str kinds)) "Wrong schema coverage";
  let operations = List.filter_map (fun item ->
      if get "record_kind" item <> str "component" then None
      else match get "synthetic_model" (get "normalized" item) with Json.Null -> None | value -> Some (Json.string (get "operation" value))) cases
    |> List.sort_uniq String.compare in
  check (operations = ["and";"any_contact";"compare";"constant";"held_for";"input";"memory";"not";"onset";"or";"output";"pulse";"select"])
    "Missing executable component operation";
  check (get "executable_operations" coverage = arr (List.map str operations)) "Wrong operation census";
  let identities = List.map (fun item -> Json.string (get "id" item)) (cases @ rejected) in
  check (List.length (List.sort_uniq String.compare identities) = List.length identities) "Duplicate component case";
  check (Canonical.fingerprint (arr (List.sort String.compare identities |> List.map str)) = "72742695a3bc4e4ffccfbfe672d311563fc1ea8bb47984a4d513e8b5acf3644e") "Changed component fixture inventory";
  let rejection_codes = List.map (fun item -> Json.string (get "id" item), Json.string (get "expected_code" item)) rejected
    |> List.sort (fun (a,_) (b,_) -> String.compare a b)
    |> List.map (fun (identity, code) -> arr [str identity;str code]) in
  check (Canonical.fingerprint (arr rejection_codes) = "aa047609532ac9a7aa3e30bdea22d4bf805d245ced830a3cefb43c86546bbf0b") "Changed intended native rejection categories";
  let actual_checks = ref 0 in
  List.iter (fun item -> let normalized, checks = normalize (Json.string (get "record_kind" item)) (get "input" item) in
      let identity = Json.string (get "id" item) in
      check (Canonical.encode normalized = Canonical.encode (get "normalized" item)) ("Complete component differs: " ^ identity);
      check (Canonical.fingerprint normalized = Json.string (get "fingerprint" item)) ("Component hash differs: " ^ identity);
      check (Canonical.encode (arr checks) = Canonical.encode (get "domain_checks" item)) ("Local assessment differs: " ^ identity);
      actual_checks := !actual_checks + List.length checks) cases;
  check (!actual_checks = 42 && get "domain_check_count" coverage = Json.int 42) "Missing local domain assessments";
  List.iter (fun item ->
      try reject (Json.string (get "expected_code" item)) (fun () -> normalize (Json.string (get "record_kind" item)) (get "input" item))
      with Failure message -> failwith (Json.string (get "id" item) ^ ": " ^ message)) rejected;
  Printf.printf "components corpus: 60 records, 112 intended rejections, 42 local domain checks, all 13 executable operations\n"
let () = match Array.to_list Sys.argv with
  | [_] -> literals (); boundary_literals (); Printf.printf "components: %d literal checks\n" !count
  | [_; path] -> corpus path; Printf.printf "components: %d corpus checks\n" !count
  | _ -> failwith "Usage: test_component.exe [components-v1.json]"

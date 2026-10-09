open Bioc_wire
module C = Bioc_domain.Policy_target_capabilities
module P = Bioc_domain.Policy_target_plan_request
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module R = Bioc_domain.Policy_realization_request
module M = Bioc_domain.Policy_component_material_request
module I = Bioc_domain.Policy_implementation
module U = Bioc_domain.Policy_implementation_binding
module H = Bioc_domain.Policy_provider_prerequisites
module Input = Bioc_domain.Policy_material_request
module W = Bioc_checker.Work_budget
module B = Bioc_checker.Policy_implementation_binding_check
let implementation = "biocompiler.ocaml.policy_target_planning.v0.1"
let validation_scope = "policy-target-planning-v0.1"
let resource_profile = "biocompiler.policy_target_planning_resources.v0.1"
let operations = ["plan-policy-target";"replay-policy-target-plan"]
let report_schema = "biocompiler.policy_target_plan.v0.1"
let result_schema = "biocompiler.core.policy_target_plan.v1"
let s value = Json.String value
let o values = Json.Object values
let a values = Json.Array values
let n value = Json.Int (Z.of_int value)
let get key value = Json.field key (Json.object_fields value)
let profile = o ["operations",a (List.map s operations);"request_schema",s P.schema_version;
  "report_schema",s report_schema;"implementation",s implementation;"validation_scope",s validation_scope;
  "resource_profile",s resource_profile;"catalog_fingerprint",s C.catalog_fingerprint;
  "max_result_bytes",n P.ceilings.max_report_bytes;"max_result_nodes",n P.ceilings.max_report_nodes]
let stages = ["source_contracts";"operational_admission";"realization_inputs";"model_lowering";
  "source_binding";"component_arrangement";"provider_dependencies"]
let claims = o ["planning",s "diagnostic_only";"diagnostic_completeness",s "first_blocker";
  "execution",s "not_performed";"preservation",s "unassessed";"requirements",s "unassessed";
  "resource_feasibility",s "unassessed";"material",s "unassessed";"empirical",s "unassessed";
  "artifact",s "withheld";"export",s "withheld"]
exception Blocked

let plan raw =
  (* Envelope decoding has fixed byte/node/depth caps before the caller limit is
     readable. Its entire measured work is then debited, never reset or waived. *)
  let request = P.of_json raw in
  let limits = P.limits request in
  let budget = W.create ~profile:resource_profile ~error_code:"policy_target_plan_resource_limit"
    ~maximum:limits.max_work () in
  let charge = W.charge budget in
  charge (P.decoding_work request);
  let module Meter = Bioc_checker.Policy_generation_meter.Make (struct let charge = charge end) in
  let module List = Meter.List in
  let module Json = Meter.Json in
  let module Canonical = Meter.Canonical in
  let target_id = P.target request in
  let target = C.target target_id in
  let status = ref "planned" and current = ref "source_contracts" in
  let states = ref (List.map (fun name -> name,"not_run") stages) in
  let mark stage value = states := List.map (fun (name,old) -> name,(if name=stage then value else old)) !states in
  let assessment = ref Json.Null and declarations = ref [] and requirements = ref [] in
  let source_declarations = ref [] and diagnostics = ref [] and missing_inputs = ref [] in
  let selected_models = ref [] and selected_components = ref [] and dependencies = ref Json.Null in
  let declaration_id path = match path with
    | None -> Json.Null
    | Some path ->
        (match List.find_opt (fun (decl:D.declaration) ->
          path=decl.path || Meter.String.starts_with ~prefix:(decl.path^"/") path) !source_declarations with
        | None -> Json.Null | Some decl -> s decl.id) in
  let diagnostic category (error:Diagnostic.t) = o ["category",s category;"stage",s !current;
    "code",s error.code;"message",s error.message;
    "path",(match error.path with None->Json.Null|Some path->s path);
    "declaration_id",declaration_id error.path] in
  let block ?(missing=[]) category error =
    status:=category; mark !current "blocked"; missing_inputs:=missing;
    diagnostics:=[diagnostic category error]; raise Blocked in
  let need name = block ~missing:[name] "missing_inputs"
    {Diagnostic.code="policy_target_plan_missing_input";message="Supply the original "^name^" to continue bounded planning.";path=None} in
  let unsupported_codes = ["policy_operational_unsupported";"policy_realization_unsupported";
    "policy_implementation_lowering_unsupported";"policy_staged_lowering_unsupported";
    "policy_network_lowering_unsupported";"policy_realization_network";
    "policy_realization_finite_machine";"policy_realization_two_observation";"policy_realization_multi_product"] in
  let missing_codes = ["policy_implementation_lowering_missing_model";"policy_staged_lowering_missing_model";
    "policy_network_lowering_missing_model"] in
  (* Only explicit expected diagnostic codes become findings. Resource/search
     exhaustion and unexpected producer/checker failures escape without a plan. *)
  let attempt ~fallback action =
    try action () with Diagnostic.Error error ->
      if W.is_exhaustion budget error then raise (Diagnostic.Error error)
      else if List.mem error.code unsupported_codes then block "unsupported_target" error
      else if List.mem error.code missing_codes then
        block ~missing:["implementation_library:model_configuration"] "missing_inputs" error
      else if List.mem error.code ["policy_document_limit";"policy_check_limit";
        "policy_material_work_limit";"policy_target_plan_work_limit";
        "policy_network_binding_resource_limit";"policy_component_lowering_search_exhausted";
        "policy_implementation_lowering_resource";"policy_material_input_limit";
        "policy_component_fragment_limit";"policy_component_material_work_limit";
        "policy_domain_limit";"policy_implementation_limit";"policy_operational_limit";
        "nesting_limit";"node_limit";"molecular_resource_limit"] then
        raise (Diagnostic.Error error)
      else match fallback with Some category -> block category error | None -> raise (Diagnostic.Error error) in
  let same left right = Json.equal left right in
  let compatible ?path condition message = Diagnostic.require ?path condition
    "policy_target_plan_incompatible_inputs" message in
  let bind admitted original implementation proposed =
    if R.is_network original then ignore (B.check_network_metered ~charge ~admitted ~implementation ~proposed)
    else (
      (* The older independent checker retains its fixed closed graph limits.
         Account full inputs before its opaque reconstruction; this metric does
         not assert a native instruction or wall-time ceiling. *)
      Meter.preflight (R.to_json original); Meter.preflight (I.to_json implementation);
      Meter.preflight (U.to_json proposed);
      ignore (B.check ~admitted ~implementation ~proposed)) in
  let models implementation = List.map (fun (node:I.node) ->
    let body = I.model_body_to_json node.model in
    o ["node",s node.node_id;"model",Bioc_domain.Pinned_identity.to_json node.model.identity;
      "configuration_digest",s node.model.configuration_digest;"primitive",get "primitive" body]) (I.nodes implementation) in
  (try
    let document = attempt ~fallback:(Some "invalid_source") (fun () ->
      Meter.preflight (P.document request); D.of_json ~path:"/document" (P.document request)) in
    assessment := attempt ~fallback:None (fun () -> Bioc_checker.Policy_check.check ~charge document);
    source_declarations := D.declarations document;
    declarations := List.map (fun (decl:D.declaration) ->
      o ["id",s decl.id;"kind",get "$type" decl.value;"path",s decl.path]) !source_declarations;
    requirements := List.filter_map (fun (decl:D.declaration) -> if decl.kind<>D.Requirement then None else
      Some (o ["id",s decl.id;"path",s decl.path;"source",decl.value;"status",s "unassessed"])) !source_declarations;
    if get "status" !assessment <> s "valid" then (
      let issues = Json.array (get "diagnostics" !assessment) in
      let first = List.hd issues in
      block "invalid_source" {Diagnostic.code=Json.string (get "code" first);
        message=Json.string (get "message" first);path=Some (Json.string (get "path" first))});
    mark !current "completed";
    current:="operational_admission";
    let definitions = match P.definitions request,P.realization_request request with
      | Some value,_ -> value
      | None,Some original -> attempt ~fallback:(Some "incompatible_inputs") (fun () -> get "definitions" original)
      | None,None -> need "definitions" in
    let source = attempt ~fallback:(Some "incompatible_inputs") (fun () ->
      Meter.preflight definitions;
      let descriptors=O.descriptors_of_json definitions in
      Bioc_checker.Policy_admission.admit_metered ~charge ~document ~descriptors) in
    let behavior = attempt ~fallback:None (fun () -> Bioc_compiler.Policy_lowering.lower ~charge source) in
    mark !current "completed";
    current:="realization_inputs";
    let raw_original = match P.realization_request request with Some value->value|None->need "realization_request" in
    let original = attempt ~fallback:(Some "incompatible_inputs") (fun () ->
      compatible ~path:"/request/realization_request/document" (same (get "document" raw_original) (P.document request))
        "Realization authority must retain the complete original source document.";
      compatible ~path:"/request/realization_request/definitions" (same (get "definitions" raw_original) definitions)
        "Supplied definitions must equal the original realization definitions.";
      compatible (get "schema_version" raw_original=s (C.realization_schema target_id) &&
        get "profile" raw_original=s (C.realization_profile target_id))
        "Realization request schema/profile differs from the selected installed target.";
      Meter.preflight raw_original;
      if C.realization_schema target_id=R.coupled_schema_version then R.of_coupled_json raw_original
      else if C.realization_schema target_id=R.multi_site_schema_version then R.of_multi_site_json raw_original
      else if C.realization_schema target_id=R.network_schema_version then R.of_network_json raw_original
      else if C.realization_schema target_id=R.finite_machine_schema_version then R.of_finite_machine_json raw_original
      else if C.realization_schema target_id=R.multi_product_schema_version then R.of_multi_product_json raw_original
      else if C.realization_schema target_id=R.two_observation_schema_version then R.of_two_observation_json raw_original
      else if C.realization_schema target_id=R.prerequisite_schema_version then R.of_prerequisite_json raw_original
      else R.of_json raw_original) in
    let admitted = attempt ~fallback:(Some "incompatible_inputs") (fun () ->
      Bioc_checker.Policy_realization_admission.admit_metered ~charge ~request:original ~behavior) in
    mark !current "completed";
    current:="model_lowering";
    let library = R.implementation_library original in
    let lowered = attempt ~fallback:None (fun () ->
      Bioc_compiler.Policy_implementation_lowering.lower_metered ~charge ~admitted ~library) in
    current:="source_binding";
    attempt ~fallback:None (fun () -> bind admitted original lowered.implementation lowered.binding);
    selected_models := models lowered.implementation;
    mark "model_lowering" "completed"; mark !current "completed";
    current:="component_arrangement";
    if not (C.is_material target_id) then (
      (match P.material_request request with None -> () | Some _ ->
        block "incompatible_inputs" {Diagnostic.code="policy_target_plan_incompatible_inputs";
          message="Implementation-only planning cannot consume material authority.";path=Some "/request/material_request"});
      mark !current "not_applicable"; mark "provider_dependencies" "not_applicable")
    else (
      let raw_material = match P.material_request request with Some value->value|None->need "material_request" in
      let material = attempt ~fallback:(Some "incompatible_inputs") (fun () ->
        compatible (get "schema_version" raw_material=s (C.request_schema target_id) &&
          get "profile" raw_material=s (C.request_profile target_id))
          "Material request schema/profile differs from the selected installed target.";
        compatible ~path:"/request/material_request/implementation_request"
          (same (get "implementation_request" raw_material) raw_original)
          "Material authority must retain the complete explicit realization request.";
        M.of_json ~charge raw_material) in
      let source_inputs = if M.is_network material || M.is_finite_machine material ||
        M.is_two_observation material || M.is_multi_member material then
          Some (List.map (fun (row:M.input_binding) -> row.source,row.input_id) (M.input_bindings material)) else None in
      let arranged = attempt ~fallback:(Some "incompatible_inputs") (fun () ->
        Bioc_compiler.Policy_component_lowering.arrange ~charge ?source_inputs ~library
          ~rule:(M.composition_rule material) lowered) in
      attempt ~fallback:None (fun () -> bind admitted original arranged.implementation arranged.binding);
      selected_models := models arranged.implementation;
      selected_components := Json.array (get "components" (get "catalog_binding" raw_material));
      mark !current "completed";
      current:="provider_dependencies";
      if not (M.requires_prerequisite_closure material) then mark !current "not_applicable"
      else (let graph = attempt ~fallback:(Some "incompatible_inputs") (fun () ->
        H.derive ~charge ~original ~context:(M.context material) ()) in
      dependencies := H.to_json graph;
      mark !current "completed";
      match H.issues graph with
      | [] -> ()
      | issue::_ ->
          let category,missing = match issue.kind with H.Missing -> "missing_inputs",["provider_dependencies"]
            | H.Cycle | H.Extra | H.Unsupported -> "incompatible_inputs",[] in
          (* A completed static analysis can report an unresolved dependency. *)
          status:=category; missing_inputs:=missing;
          diagnostics := [diagnostic category {Diagnostic.code=issue.code;
            message="Static original provider dependencies contain an unresolved obligation; this does not assess biological availability.";
            path=None}]))
   with Blocked -> ());
  let optional_fingerprint = function None->Json.Null|Some raw->s (Canonical.fingerprint raw) in
  let body = ["schema_version",s report_schema;"status",s !status;"target",target;
    "catalog_fingerprint",s C.catalog_fingerprint;"request_fingerprint",s (P.fingerprint request);
    "document_fingerprint",s (Canonical.fingerprint (P.document request));
    "realization_request_fingerprint",optional_fingerprint (P.realization_request request);
    "material_request_fingerprint",optional_fingerprint (P.material_request request);
    "source_assessment",!assessment;"declarations",a !declarations;"requirements",a !requirements;
    "obligations",a (List.map (fun id -> o ["id",id;"status",s "required";"stage",s "full_pipeline"])
      (Json.array (get "deferred_stages" target)));
    "missing_inputs",a (List.map s !missing_inputs);
    "stages",a (List.map (fun (stage,status)->o ["stage",s stage;"status",s status]) !states);
    "selected_models",a !selected_models;"selected_components",a !selected_components;
    "provider_dependencies",!dependencies;"diagnostics",a !diagnostics;"claims",claims] in
  let report work = o (body @ ["usage",o ["work",n work;"max_work",n limits.max_work]]) in
  let wrap fingerprint report = o ["schema_version",s result_schema;"implementation",s implementation;
    "validation_scope",s validation_scope;"resource_profile",s resource_profile;
    "request_fingerprint",s (P.fingerprint request);"report_fingerprint",s fingerprint;"report",report] in
  (* Reserve with the largest usage spelling before final usage is frozen. The
     charge covers report hashing and final wrapper encoding as bounded passes.
     Actual publication is checked again against the caller's complete-wrapper
     bounds; no partial report survives either resource failure. *)
  let provisional = wrap (String.make 64 '0') (report limits.max_work) in
  let publication = W.create_output ~profile:resource_profile ~error_code:"policy_target_plan_publication_limit"
    ~max_bytes:limits.max_report_bytes ~max_nodes:limits.max_report_nodes () in
  W.reserve_json publication provisional;
  let bytes = Input.preflight ~charge provisional in
  charge (3*bytes);
  let final_report = report (limits.max_work-W.remaining budget) in
  let result = wrap (Bioc_wire.Canonical.fingerprint final_report) final_report in
  Diagnostic.require (not (W.exhausted budget)) "policy_target_plan_resource_limit"
    "An exhausted planning invocation cannot publish a report.";
  let actual = W.create_output ~profile:resource_profile ~error_code:"policy_target_plan_publication_limit"
    ~max_bytes:limits.max_report_bytes ~max_nodes:limits.max_report_nodes () in
  W.reserve_json actual result;
  ignore (Bioc_wire.Canonical.encode_bounded ~max_bytes:limits.max_report_bytes result);
  result

let handle ~operation payload =
  (* Transport/replay framing has a separate fixed bound, independent of plan
     usage, so replay reproduces the complete deterministic original wrapper. *)
  ignore (Input.preflight ~max_bytes:P.max_input_bytes ~max_nodes:P.max_input_nodes
    ~max_depth:P.max_input_depth ~charge:(fun _->()) payload);
  let fields = Json.object_fields ~path:"/payload" payload in
  Diagnostic.require (List.mem operation operations) "policy_target_plan_operation" "Unknown target planning operation.";
  Json.exact_fields ~path:"/payload" (if operation="plan-policy-target" then ["request"] else ["request";"report"]) fields;
  let result = plan (Json.field "request" fields) in
  if operation="replay-policy-target-plan" then (
    let saved = Json.field "report" fields in
    ignore (Input.preflight ~max_bytes:P.ceilings.max_report_bytes ~max_nodes:P.ceilings.max_report_nodes
      ~charge:(fun _->()) saved);
    Diagnostic.require (Canonical.encode result=Canonical.encode saved) "policy_target_plan_replay"
      "Fresh planning differs from the complete retained request-bound report.");
  result

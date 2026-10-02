open Bioc_wire
open Bioc_domain
module S = Component_selection
module R = S.Request
module A = S.Alternative
module Result = S.Result
module Registry = Component_registry
module Lock = Registry.Component_lock
module C = Component_contract
module P = Pinned_identity
module W = Bioc_checker.Work_budget
module Names = Set.Make (String)
let implementation_version = "biocompiler.ocaml.component_selection.v0.1"
let resource_profile = "biocompiler.component_selection_producer.resources.v1"
type limits = {max_work:int;max_components:int;max_input_bytes:int;max_output_bytes:int;max_output_nodes:int}
let make_limits ?(max_work = 50_000_000) ?(max_components = 10_000) ?(max_input_bytes = Limits.max_request_bytes)
    ?(max_output_bytes = Limits.max_response_bytes) ?(max_output_nodes = Limits.max_json_nodes) () =
  List.iter (fun (value,maximum) -> Diagnostic.require (value > 0 && value <= maximum)
    "component_selection_limits" "Selection limits must be positive reductions of the native profile.")
    [max_work,50_000_000;max_components,10_000;max_input_bytes,Limits.max_request_bytes;
     max_output_bytes,Limits.max_response_bytes;max_output_nodes,Limits.max_json_nodes];
  {max_work;max_components;max_input_bytes;max_output_bytes;max_output_nodes}
let default_limits = make_limits ()
let limits_json limits = Json.Object ["profile",Json.String resource_profile;
  "max_work",Json.int limits.max_work;"max_components",Json.int limits.max_components;
  "max_input_bytes",Json.int limits.max_input_bytes;"max_input_nodes",Json.int Limits.max_json_nodes;
  "max_output_bytes",Json.int limits.max_output_bytes;"max_output_nodes",Json.int limits.max_output_nodes;
  "encoding",Json.String "canonical_utf8";"fragment_punctuation",Json.String "one_conservative_separator_byte_per_fragment";
  "work",Json.String "shared_precharged_traversal_comparison_and_publication_units"]
type usage = {work:int;components:int;input_bytes:int;output_bytes:int}
type scope = {limits:limits;work:W.t;input:W.output;output:W.output;
  mutable charged:int;mutable visited:int;mutable input_bytes:int;mutable output_bytes:int}
let create ?parent limits =
  let work = match parent with None -> W.create ~profile:resource_profile ~error_code:"component_selection_work_limit" ~maximum:limits.max_work ()
    | Some parent -> W.nested ~parent ~profile:resource_profile ~error_code:"component_selection_work_limit" ~maximum:limits.max_work () in
  {limits;work;input=W.create_output ~profile:resource_profile ~error_code:"component_selection_input_limit"
     ~max_bytes:limits.max_input_bytes ~max_nodes:Limits.max_json_nodes ();
   output=W.create_output ~profile:resource_profile ~error_code:"component_selection_output_limit"
     ~max_bytes:limits.max_output_bytes ~max_nodes:limits.max_output_nodes ();
   charged=0;visited=0;input_bytes=0;output_bytes=0}
let charge (scope : scope) amount = W.charge scope.work amount; scope.charged <- scope.charged + amount
let usage (scope : scope) = {work=scope.charged;components=scope.visited;input_bytes=scope.input_bytes;output_bytes=scope.output_bytes}
let input (scope : scope) ~size raw =
  (* These abstract records cache exact canonical size. Charge before walking
     authority, including on an already exhausted reusable caller budget.
     Each key/value node occupies at least one byte, so twice size bounds both. *)
  charge scope (2 * (size + 1));
  W.reserve_json scope.input (Json.int 0); W.reserve_json scope.input raw;
  scope.input_bytes <- scope.input_bytes + size + 1
let publication (scope : scope) raw =
  W.reserve_json scope.output (Json.int 0); W.reserve_json scope.output raw;
  let bytes,nodes = S.measure raw in charge scope (bytes + nodes + 1);
  scope.output_bytes <- scope.output_bytes + bytes + 1
let text (scope : scope) value = charge scope (1 + String.length value)
let equal_text (scope : scope) left right = charge scope (1 + String.length left + String.length right); left = right
let set (scope : scope) values = List.fold_left (fun result value -> text scope value; Names.add value result) Names.empty values
let pinned (scope : scope) value = let raw = P.to_json value in let bytes,nodes = S.measure raw in charge scope (bytes + nodes); Canonical.encode raw
let component_class = function Component.Synthetic_model -> "synthetic_model" | Component.Sequence_reference -> "sequence_reference" | Component.Modeled_component -> "modeled_component"
let assess_admission (scope : scope) target components =
  (* Admission reparses the full target/component inventory. Charge its complete
     bounded input before any nested constructor or policy computation. *)
  let target_raw = Build_request.Target.to_json target in
  let target_bytes,target_nodes = S.measure target_raw in
  let bytes,nodes = List.fold_left (fun (bytes,nodes) component ->
    let size,count = S.measure (Component.to_json component) in bytes+size,nodes+count) (target_bytes,target_nodes) components in
  charge scope (3 * (bytes + nodes + 512));
  let assessment = Bioc_checker.Admission_check.for_target ~target ~boundary:Admission.Selection ~components in
  let size,count = S.measure (Admission.Assessment.to_json assessment) in charge scope (size + count);
  assessment
let domain (scope : scope) required supported =
  (* The shared algebra uses sorted coordinate union plus association scans.
     Precharge its worst-case coordinate comparisons before invoking it. *)
  let left = C.Operating_domain.constraints required and right = C.Operating_domain.constraints supported in
  let count = List.length left + List.length right in
  let bytes = List.fold_left (fun amount (key,_) -> amount + String.length key) 0 left
    + List.fold_left (fun amount (key,_) -> amount + String.length key) 0 right in
  let left_bytes,left_nodes = S.measure (C.Operating_domain.to_json required) in
  let right_bytes,right_nodes = S.measure (C.Operating_domain.to_json supported) in
  charge scope ((count + 1) * (bytes + count + 1) + left_bytes + left_nodes + right_bytes + right_nodes);
  C.operating_domain_subset ~required ~supported
let select_in (scope : scope) registry request =
  input scope ~size:(Registry.canonical_size registry) (Registry.to_json registry);
  input scope ~size:(R.canonical_size request) (R.to_json request);
  let components = Registry.components registry in
  Diagnostic.require (List.length components <= scope.limits.max_components) "component_selection_search_limit"
    "Complete component alternative inventory exceeds the native search bound.";
  let target = R.target request in
  let admission = assess_admission scope target components in
  let str value = Json.String value in
  let skeleton = Json.Object ["schema_version",str Result.schema_version;"registry_fingerprint",str (Registry.fingerprint registry);
    "request_fingerprint",str (R.fingerprint request);"selected",Json.Null;"alternatives",Json.Array [];
    "admission",Admission.Assessment.to_json admission] in
  publication scope skeleton;
  let target_compartments = set scope (Build_request.Target.compartments target) in
  let required_guarantees = set scope (R.required_guarantees request) in
  let required_pins = List.map (pinned scope) (R.required_identities request) |> set scope in
  let preferences = Hashtbl.create 16 in
  List.iteri (fun index id -> text scope id; Hashtbl.add preferences id index) (R.preferred_component_ids request);
  let fallback_rank = List.length (R.preferred_component_ids request) in
  let winner = ref None in
  let alternatives = List.map (fun component ->
    charge scope 1; scope.visited <- scope.visited + 1;
    let policy = assess_admission scope target [component] in
    let reasons = ref (if Admission.Assessment.decision policy = Admission.Software_only then [] else List.rev (Admission.Assessment.diagnostics policy)) in
    let reason value = text scope value; reasons := value :: !reasons in
    if not (equal_text scope (Component.implementation_role component) (R.implementation_role request)) then reason "implementation_role_mismatch";
    if not (Names.mem (Build_request.Target.payload_format target) (set scope (Component.supported_targets component))) then reason "unsupported_target";
    let compartments = List.map C.Port.compartment (Component.ports component) |> set scope in
    if not (Names.subset compartments target_compartments) then reason "unsupported_compartment";
    (match R.classification request with Some value when not (equal_text scope value (component_class (Component.classification component))) -> reason "classification_mismatch" | _ -> ());
    (match R.component_id request with Some value when not (equal_text scope value (Component.id component)) -> reason "component_id_mismatch" | _ -> ());
    (match R.component_version request with Some value when not (equal_text scope value (Component.version component)) -> reason "component_version_mismatch" | _ -> ());
    if not (Names.subset required_guarantees (set scope (Component.guarantees component))) then reason "missing_required_guarantee";
    let available = Component.identities component @ Component.evidence component @ List.map Component.Parameter.source (Component.parameters component) in
    let available = List.map (pinned scope) available |> set scope in
    if not (Names.subset required_pins available) then reason "required_dependency_identity_mismatch";
    let domain = domain scope (R.required_domain request) (Component.supported_domain component) in
    if C.status domain = C.Fail then List.iter (fun value -> reason ("domain:" ^ value)) (C.reasons domain);
    let status = if !reasons <> [] then A.Rejected else if C.status domain = C.Unknown then A.Unknown else A.Eligible in
    let preference_rank = match status with
      | A.Eligible -> reasons := List.rev ["all_hard_constraints_satisfied";"preference_rank_applied_after_hard_constraints"];
          text scope (Component.id component);
          Some (Z.of_int (Option.value ~default:fallback_rank (Hashtbl.find_opt preferences (Component.id component))))
      | A.Unknown -> reasons := List.rev (List.map (fun value -> "domain:" ^ value) (C.reasons domain)); None
      | A.Rejected -> None in
    let raw = Json.Object ["schema_version",str A.schema_version;"component_id",str (Component.id component);
      "version",str (Component.version component);"content_fingerprint",str (Component.fingerprint component);
      "status",str (A.status_name status);"reasons",Json.Array (List.map str (List.rev !reasons));
      "preference_rank",(match preference_rank with None -> Json.Null | Some value -> Json.Int value)] in
    publication scope raw;
    let bytes,nodes = S.measure raw in charge scope (2 * (bytes + nodes));
    let alternative = A.of_json raw in
    if status = A.Eligible then (
      text scope (A.component_id alternative); text scope (A.version alternative);
      match !winner with Some previous when A.compare_rank previous alternative <= 0 -> () | _ -> winner := Some alternative);
    alternative) components in
  let selected = Option.map (fun winner ->
    let raw = Json.Object ["schema_version",str Lock.schema_version;"node_id",str (R.instance_id request);
      "component_id",str (A.component_id winner);"version",str (A.version winner);
      "content_fingerprint",str (A.content_fingerprint winner)] in
    publication scope raw; Lock.of_json raw) !winner in
  let raw = Json.Object ["schema_version",str Result.schema_version;"registry_fingerprint",str (Registry.fingerprint registry);
    "request_fingerprint",str (R.fingerprint request);"selected",(match selected with None -> Json.Null | Some value -> Lock.to_json value);
    "alternatives",Json.Array (List.map A.to_json alternatives);"admission",Admission.Assessment.to_json admission] in
  let complete = W.create_output ~profile:resource_profile ~error_code:"component_selection_output_limit"
    ~max_bytes:scope.limits.max_output_bytes ~max_nodes:scope.limits.max_output_nodes () in
  W.reserve_json complete raw;
  let bytes,nodes = S.measure raw in charge scope (3 * (bytes + nodes));
  Result.make ~registry_fingerprint:(Registry.fingerprint registry) ~request_fingerprint:(R.fingerprint request)
    ~selected ~alternatives ~admission
let select_with_usage ?(limits = default_limits) ?parent ~registry ~request () =
  let scope = create ?parent limits in let result = select_in scope registry request in result,usage scope
let select ?limits ?parent ~registry ~request () = fst (select_with_usage ?limits ?parent ~registry ~request ())
let verify_selection_with_usage ?(limits = default_limits) ?parent ~registry ~request supplied =
  let scope = create ?parent limits in
  input scope ~size:(Result.canonical_size supplied) (Result.to_json supplied);
  let expected = select_in scope registry request in
  let raw = Result.to_json supplied in
  let bytes,nodes = S.measure raw in charge scope (bytes + nodes);
  Json.equal (Result.to_json expected) raw,usage scope
let verify_selection ?limits ?parent ~registry ~request supplied =
  fst (verify_selection_with_usage ?limits ?parent ~registry ~request supplied)

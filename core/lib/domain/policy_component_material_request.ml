open Bioc_wire
module R = Policy_realization_request
module L = Policy_component_library
module A = Policy_component_assembly_rule
module X = Policy_component_context
module C = Policy_material_contract
module LC = Policy_component_material
module F = Policy_component_fragment
module I = Policy_implementation
module D = Policy_document
module O = Policy_operating_domain
module P = Pinned_identity
module M = Molecular_record
module Old = Policy_material_request
module PX = Policy_material_context
let schema_version = "biocompiler.policy_component_material_request.v0.1"
let profile = X.profile
let instance_schema_version = "biocompiler.policy_component_material_request.v0.2"
let instance_profile = "biocompiler.policy_instance_component_mrna.v0.1"
let prerequisite_schema_version = "biocompiler.policy_component_material_request.v0.3"
let prerequisite_profile = "biocompiler.policy_instance_prerequisite_mrna.v0.1"
let two_observation_schema_version = "biocompiler.policy_component_material_request.v0.4"
let two_observation_profile = "biocompiler.policy_instance_two_observation_prerequisite_mrna.v0.1"
let multi_member_schema_version = "biocompiler.policy_component_material_request.v0.5"
let multi_member_profile = "biocompiler.policy_multi_member_prerequisite_mrna.v0.1"
let grounded_helper_schema_version = "biocompiler.policy_component_material_request.v0.6"
let grounded_helper_profile = "biocompiler.policy_grounded_helper_prerequisite_mrna.v0.1"
let resource_profile = "biocompiler.policy_component_material_resources.v0.1"
let str value = Json.String value
let obj values = Json.Object values
let get key raw = Json.field key (Json.object_fields raw)
let exact keys raw = Json.exact_fields keys (Json.object_fields raw)
let require condition message = Diagnostic.require condition "policy_component_material_request" message
let text maximum raw = let value = Json.name raw in
  require (String.length value<=maximum) "Composition request identity exceeds its byte bound."; value
let digest raw = let value = Json.string raw in
  require (String.length value=64 && String.for_all (function '0'..'9'|'a'..'f' -> true | _ -> false) value)
    "Composition request requires a lowercase SHA-256 digest."; value
let slot_name = A.slot_name
let slot ~instanced raw =
  if instanced then (
    let id = text 128 raw in
    require (id<>"decision" && id<>"driver") "Instance identities cannot use legacy role slots.";
    A.Instance id)
  else match Json.string raw with "decision" -> A.Decision | "driver" -> A.Driver
  | _ -> Diagnostic.fail "policy_component_material_request" "Unknown original component slot."
let pin_equal left right = Json.equal (P.to_json left) (P.to_json right)
type component_binding = {slot:A.slot;component:P.t}
type catalog_binding = {entry_id:string;entry_version:string;entry_digest:string;
  operation:C.provider_ref;realization:C.provider_ref;components:component_binding list;rule:P.t}
type input_binding = {input_id:string;source:string;provider:C.provider_ref;channel:string}
type resource_owner = Node of {slot:A.slot;node_id:string} | Input of string | Layout
type resource_key = {owner:resource_owner;unit:C.resource_unit;scope:C.resource_scope}
type resource_binding = {key:resource_key;provider:C.provider_ref;capacity_id:string}
let resource_owner_to_json = function
  | Node {slot;node_id} -> obj ["kind",str "node";"slot",str (slot_name slot);"node",str node_id]
  | Input id -> obj ["kind",str "input";"id",str id]
  | Layout -> obj ["kind",str "layout"]
let owner_of_json ~instanced raw = match get "kind" raw with
  | Json.String "node" -> exact ["kind";"slot";"node"] raw; Node {slot=slot ~instanced (get "slot" raw);node_id=text 128 (get "node" raw)}
  | Json.String "input" -> exact ["kind";"id"] raw; Input (text 128 (get "id" raw))
  | Json.String "layout" -> exact ["kind"] raw; Layout
  | _ -> Diagnostic.fail "policy_component_material_request" "Unknown composition resource owner."
let resource_keys rule =
  List.concat_map (fun slot -> List.filter_map (function
    | LC.Input _ -> None
    | LC.Capacity value ->
      let owner = match value.owner with
        | LC.Node node_id -> Node {slot;node_id}
        | LC.External_slot_owner id ->
          let input = List.find (fun (row:A.input_ref) -> row.slot=slot && row.external_slot=id) (A.input_order rule) in
          Input input.input_id in
      Some {owner;unit=value.unit;scope=value.scope}) (LC.provider_requirements (A.component rule slot))) (A.slots rule)
  @ [{owner=Layout;unit=C.Generation_counters;scope=C.Per_encounter_slot};
     {owner=Layout;unit=C.Timer_cells;scope=C.Per_executor};
     {owner=Layout;unit=C.Control_event_records;scope=C.Per_executor}]
type budgets = {max_work:int;max_report_bytes:int;max_report_nodes:int}
type t = {raw:Json.t;identity:string;decoding_work_value:int;original:R.t;library:L.t;rule_value:A.t;
  catalog:catalog_binding;inputs:input_binding list;resources:resource_binding list;context_value:X.t;budget_values:budgets}
let of_json ?(charge=fun _ -> ()) raw =
  let work = ref 0 in
  let spend amount =
    Diagnostic.require (amount>=0 && amount<=max_int- !work) "policy_component_material_work_limit"
      "Composition request logical work counter overflow.";
    charge amount; work := !work+amount in
  let measure raw = Old.preflight ~charge:spend raw in
  let decode parser raw = ignore (measure raw); parser raw in
  let equal left right = let a=measure left and b=measure right in spend (a+b); Json.equal left right in
  let raw_bytes = measure raw in M.check_resources raw;
  exact ["schema_version";"profile";"implementation_request";"component_library";"composition_rule";
    "catalog_binding";"input_bindings";"resource_bindings";"context";"budgets"] raw;
  let grounded_helper = get "schema_version" raw=str grounded_helper_schema_version && get "profile" raw=str grounded_helper_profile in
  let multi_member = grounded_helper || (get "schema_version" raw=str multi_member_schema_version && get "profile" raw=str multi_member_profile) in
  let two_observation = get "schema_version" raw=str two_observation_schema_version && get "profile" raw=str two_observation_profile in
  let prerequisite_closure = multi_member || two_observation || (get "schema_version" raw=str prerequisite_schema_version && get "profile" raw=str prerequisite_profile) in
  let instanced = prerequisite_closure || (get "schema_version" raw=str instance_schema_version && get "profile" raw=str instance_profile) in
  require (instanced || (get "schema_version" raw=str schema_version && get "profile" raw=str profile))
    "Unsupported original component material request profile.";
  let original = decode (if multi_member then R.of_multi_product_json
    else if two_observation then R.of_two_observation_json
    else if prerequisite_closure then R.of_prerequisite_json else R.of_json) (get "implementation_request" raw) in
  let library = decode (L.of_json ~library:(R.implementation_library original)) (get "component_library" raw) in
  let rule_value = decode (A.of_json ~components:library) (get "composition_rule" raw) in
  let context_value = decode X.of_json (get "context" raw) in
  require (A.is_instanced rule_value=instanced && X.is_instanced context_value=instanced)
    "Original request, rule and context instance profiles must agree.";
  require (X.requires_prerequisite_closure context_value=prerequisite_closure &&
    R.requires_prerequisite_closure original=prerequisite_closure)
    "Original request, realization and context prerequisite profiles must agree.";
  require (X.is_two_observation context_value=two_observation && R.is_two_observation original=two_observation)
    "Original request, realization and context observation families must agree.";
  require (A.is_multi_member rule_value=multi_member && X.is_multi_member context_value=multi_member &&
    R.is_multi_product original=multi_member)
    "Original request, realization, assembly and context multi-member profiles must agree.";
  require (A.is_grounded_helper rule_value=grounded_helper && X.is_grounded_helper context_value=grounded_helper)
    "Original request, assembly and context grounded-helper profiles must agree.";
  require (if multi_member then A.is_staged rule_value else not prerequisite_closure || not (A.is_staged rule_value))
    (if multi_member then "Multi-member prerequisite closure requires the explicit multi-product staged family."
     else "Prerequisite closure is limited to the existing truth instance profile.");
  let bridge = get "catalog_binding" raw in
  exact ["entry_id";"entry_version";"entry_digest";"operation";"realization";"components";"rule"] bridge;
  let catalog = {entry_id=text 256 (get "entry_id" bridge);entry_version=text 256 (get "entry_version" bridge);
    entry_digest=digest (get "entry_digest" bridge);operation=C.provider_ref_of_json (get "operation" bridge);
    realization=C.provider_ref_of_json (get "realization" bridge);rule=P.of_json (get "rule" bridge);
    components=List.map (fun row -> exact ["slot";"component"] row;
      {slot=slot ~instanced (get "slot" row);component=P.of_json (get "component" row)}) (M.array ~maximum:(if instanced then A.max_instances else 2) (get "components" bridge))} in
  let selected = match R.catalog_bindings original with
    | [value] -> value | _ -> Diagnostic.fail "policy_component_material_request" "Composition requires exactly one original realization catalog root." in
  require (selected.entry_id=catalog.entry_id && selected.entry_version=catalog.entry_version && selected.entry_digest=catalog.entry_digest)
    "Composition bridge differs from the complete original realization catalog binding.";
  require (equal selected.operation (C.provider_ref_to_json catalog.operation) && equal selected.realization (C.provider_ref_to_json catalog.realization))
    "Composition bridge changes the original operation or realization DefinitionRef.";
  let document = R.document original in
  let definitions = Json.array (get "definitions" (get "semantics" (D.program document))) in
  let resolve (reference:C.provider_ref) =
    spend (List.length definitions);
    let matches = List.filter (fun value -> get "id" value=str reference.definition_id) definitions in
    let definition = match matches with [value] -> value
      | _ -> Diagnostic.fail "policy_component_material_request" "Composition reference does not resolve to one complete original definition." in
    ignore (measure definition);
    require (get "version" definition=str reference.definition_version && D.document_digest definition=reference.definition_digest)
      "Composition DefinitionRef differs from its complete original definition body." in
  resolve catalog.operation; resolve catalog.realization;
  let entries = Json.array (get "implementations" (get "implementations" (D.to_json document))) in
  let entry = match entries with [value] -> value
    | _ -> Diagnostic.fail "policy_component_material_request" "Composition requires exactly one original source catalog entry." in
  let entry_bytes = measure entry in spend (2*entry_bytes);
  require (get "id" entry=str catalog.entry_id && get "version" entry=str catalog.entry_version && Canonical.fingerprint entry=catalog.entry_digest &&
    equal (get "operation" entry) (C.provider_ref_to_json catalog.operation) && equal (get "realization" entry) (C.provider_ref_to_json catalog.realization))
    "Composition bridge does not retain the complete source catalog entry and definitions.";
  require (List.exists (fun (declaration:D.declaration) -> declaration.kind=D.Effect &&
    equal (get "contract" declaration.value) (C.provider_ref_to_json catalog.operation)) (D.declarations document))
    "Composition catalog operation is not an original source effect contract.";
  require (List.map (fun (row:component_binding) -> row.slot) catalog.components=A.slots rule_value &&
    List.for_all2 (fun (row:component_binding) (selection:A.component_selection) -> row.slot=selection.slot && pin_equal row.component selection.identity)
      catalog.components (A.components rule_value) && pin_equal catalog.rule (A.identity rule_value))
    "Composition catalog bridge must pin exactly the selected components and complete original rule in order.";
  require ((instanced || List.length (L.components library)=2) && List.for_all (fun component ->
    List.exists (fun (row:component_binding) -> pin_equal row.component (LC.identity component)) catalog.components) (L.components library))
    (if instanced then "Composition request allows only selected original component definitions, without alternatives or helpers."
     else "Composition request allows only its two selected original components, without alternatives or helpers.");
  List.iter (fun selection -> List.iter (fun (node:F.node) ->
    require (List.exists (pin_equal node.model.identity) selected.models)
      "Selected component primitive lacks the original catalog model membership.") (F.nodes (LC.fragment (A.component rule_value selection)))) (A.slots rule_value);
  let layout = X.record_layout context_value in
  require (not instanced || layout.staged=A.is_staged rule_value)
    "Instance context records must use the original primitive phase profile.";
  let union_raw = X.ordered_union_json rule_value in let union_bytes=measure union_raw in spend (2*union_bytes);
  require (pin_equal layout.rule (A.identity rule_value) && layout.union_digest=Canonical.fingerprint union_raw &&
    layout.domain_digest=O.digest (R.operating_domain original) && layout.slots=(A.layout rule_value).slots)
    "Composition record layout must pin the exact original rule, ordered union, operating domain and slot layout.";
  let providers = X.providers context_value in
  let provider reference =
    match List.find_opt (fun (value:PX.provider) -> equal (C.provider_ref_to_json value.definition) (C.provider_ref_to_json reference)) providers with
    | Some value -> value | None -> Diagnostic.fail "policy_component_material_request" "Composition binding names an absent complete original provider DefinitionRef." in
  let missing_prerequisite reference = prerequisite_closure && not (List.exists
    (fun (value:PX.provider) -> equal (C.provider_ref_to_json value.definition) (C.provider_ref_to_json reference)) providers) in
  List.iter (fun (value:PX.provider) ->
    resolve value.definition;
    match value.body with
    | PX.Interface body -> resolve body.environment;
      (* A missing supplied dependency body remains unresolved in the new
         closure checker. Its source DefinitionRef must still resolve exactly. *)
      if not prerequisite_closure then ignore (provider body.environment)
    | PX.Chassis body ->
      List.iter (fun key -> List.iter (fun raw -> resolve (C.provider_ref_of_json raw)) (Json.array (get key body))) ["capabilities";"interfaces";"environment"];
      resolve (C.provider_ref_of_json (get "operational_model" body))
    | PX.Transport body ->
      require multi_member "Transport providers require the explicit multi-member request family.";
      resolve body.environment
    | PX.Helper body ->
      require grounded_helper "Helper providers require the explicit grounded-helper request family.";
      resolve body.environment; resolve body.delivery
    | PX.Environment _ | PX.Delivery _ -> ()) providers;
  let inputs = List.map (fun row -> exact ["input";"source";"provider";"channel"] row;
    {input_id=text 128 (get "input" row);source=text 256 (get "source" row);provider=C.provider_ref_of_json (get "provider" row);
     channel=text 4096 (get "channel" row)}) (M.array ~maximum:64 (get "input_bindings" raw)) in
  require (List.map (fun (row:input_binding) -> row.input_id) inputs=List.map (fun (row:A.input_ref) -> row.input_id) (A.input_order rule_value))
    "Composition input bindings must retain the complete original global input order.";
  List.iter2 (fun (binding:input_binding) (input:A.input_ref) ->
    resolve binding.provider;
    let slot = List.find (fun (slot:F.external_slot) -> slot.slot_id=input.external_slot)
      (F.external_slots (LC.fragment (A.component rule_value input.slot))) in
    let kind,channel_kind = match slot.input_kind with I.Evidence_input -> D.Observation,PX.Observation | I.Feedback_input -> D.Effect,PX.Feedback in
    require (List.exists (fun (declaration:D.declaration) -> declaration.id=binding.source && declaration.kind=kind) (D.declarations document))
      "Composition input must name an original source observation or effect of the matching kind.";
    if not (missing_prerequisite binding.provider) then (
    let channel = match (provider binding.provider).body with
      | PX.Interface value -> List.find_opt (fun (channel:PX.channel) -> channel.channel_id=binding.channel) value.channels
      | _ -> None in
    require (match channel with Some channel -> channel.source=binding.source && channel.kind=channel_kind | None -> false)
      "Composition input provider must retain the declared channel and exact source/kind relation.")) inputs (A.input_order rule_value);
  let resources = List.map (fun row -> exact ["owner";"unit";"scope";"provider";"capacity"] row;
    {key={owner=owner_of_json ~instanced (get "owner" row);unit=C.resource_unit_of_json (get "unit" row);scope=C.resource_scope_of_json (get "scope" row)};
     provider=C.provider_ref_of_json (get "provider" row);capacity_id=text 4096 (get "capacity" row)})
    (M.array ~maximum:4096 (get "resource_bindings" raw)) in
  require (List.map (fun (row:resource_binding) -> row.key) resources=resource_keys rule_value)
    "Composition resource bindings must retain every local prerequisite and global layout key exactly once in order.";
  List.iter (fun (binding:resource_binding) ->
    resolve binding.provider;
    if not (missing_prerequisite binding.provider) then (
    let capacity = List.find_opt (fun (capacity:PX.capacity) -> capacity.capacity_id=binding.capacity_id) (provider binding.provider).capacities in
    require (match capacity with Some capacity -> capacity.unit=binding.key.unit && capacity.scope=binding.key.scope | None -> false)
      "Composition resource binding must name an original capacity with the exact unit and scope.")) resources;
  let budget = get "budgets" raw in exact ["profile";"max_work";"max_report_bytes";"max_report_nodes"] budget;
  require (get "profile" budget=str resource_profile) "Unsupported composition resource profile.";
  let integer maximum key = let value=Json.integer (get key budget) in
    require (Z.sign value>0 && Z.leq value (Z.of_int maximum)) "Composition resource allowance exceeds its closed bound."; Z.to_int value in
  let budget_values={max_work=integer 1000000000 "max_work";max_report_bytes=integer 8323072 "max_report_bytes";
    max_report_nodes=integer 249968 "max_report_nodes"} in
  spend raw_bytes;
  let encoded=Canonical.encode_bounded ~max_bytes:M.max_json_bytes raw in
  Diagnostic.require (String.length encoded=raw_bytes) "policy_component_material_accounting"
    "Composition preflight byte count differs from the complete original encoding.";
  spend raw_bytes;
  {raw;identity=Canonical.sha256 encoded;decoding_work_value= !work;original;library;rule_value;catalog;inputs;resources;context_value;budget_values}
let to_json value = value.raw
let fingerprint value = value.identity
let decoding_work value = value.decoding_work_value
let implementation_request value = value.original
let component_library value = value.library
let composition_rule value = value.rule_value
let catalog_binding value = value.catalog
let input_bindings value = value.inputs
let resource_bindings value = value.resources
let context value = value.context_value
let budgets value = value.budget_values

let is_instanced value = A.is_instanced value.rule_value
let requires_prerequisite_closure value = R.requires_prerequisite_closure value.original
let is_two_observation value = R.is_two_observation value.original
let is_multi_member value = R.is_multi_product value.original
let is_grounded_helper value = A.is_grounded_helper value.rule_value
let request_profile value = if is_grounded_helper value then grounded_helper_profile
  else if is_multi_member value then multi_member_profile
  else if is_two_observation value then two_observation_profile
  else if requires_prerequisite_closure value then prerequisite_profile
  else if is_instanced value then instance_profile else profile

open Bioc_wire
open Literals
module Original = Bioc_policy_instance_test_support.Requests
include Bioc_policy_instance_test_support.Requests

(* Refresh only independently authored ORIGINAL references after a source edit.
   This is not a transformation of a generated implementation or its authority. *)
let refresh_catalog request =
  let entry=at ["implementation_request";"document";"implementations";"implementations";"0"]request in
  let digest=str(Canonical.fingerprint entry) in
  request
  |> put ["implementation_request";"catalog_bindings";"0";"entry_digest"] digest
  |> put ["catalog_binding";"entry_digest"] digest

let request_literal ?(catalog_only=false) fixture state_reading =
  let original,union=Original.request_literal fixture state_reading in
  let providers=at ["context";"providers"]original |> Json.array in
  let interface_reference=at ["body";"definition"](Original.provider_for "interface" providers) in
  let extra=Original.provider_for "environment" providers
    |> put ["identity";"id"] (str "context.prerequisite_environment")
    |> put ["body";"definition"] environment_reference |> repin in
  let providers=List.map(fun provider->
    if not catalog_only && at ["body";"kind"]provider=str "interface" then
      provider |> put ["body";"environment"] environment_reference |> repin
    else provider)providers @ [extra] in
  let dependency=if catalog_only then environment_reference else interface_reference in
  let request=original
    |> replace "schema_version"(str material_schema) |> replace "profile"(str material_profile)
    |> put ["implementation_request";"schema_version"](str realization_schema)
    |> put ["implementation_request";"profile"](str realization_profile)
    |> edit ["implementation_request";"document";"program";"semantics";"definitions"]
      (fun definitions->arr(Json.array definitions @ [environment_definition]))
    |> put ["implementation_request";"document";"implementations";"implementations";"0";"dependencies"](arr [dependency])
    |> put ["context";"profile"](str material_profile)
    |> put ["context";"providers"](arr providers)
    |> refresh_catalog in
  request,union

let expected_pending request =
  let catalog=at ["implementation_request";"document";"implementations";"implementations";"0"]request in
  arr [obj ["entry_id",str "exclusion.response.primitives.resolved_chassis";
    "entry_digest",str(Canonical.fingerprint catalog);"dependency_index",Json.int 0;
    "definition",List.hd(items "dependencies" catalog)]]

let original_provider request id =
  List.find(fun provider->provider_definition_id provider=str id)
    (at ["context";"providers"]request |> Json.array)
let original_reference request id = at ["body";"definition"](original_provider request id)
let expected_input_allocations request =
  let provider=original_reference request "exclusion.interface" in
  let available=obj ["onset_min",str "0";"onset_max",str "0";
    "duration_min",str "6";"duration_max",str "6"] in
  arr(List.map(fun(input,source,kind)->obj ["input",str input;"source",str source;
    "provider",provider;"channel",str input;"kind",str kind;"observer",str "executor";
    "subject",str "encounter/target";"available",available])
    ["condition","condition","observation";"feedback","response","feedback"])
let expected_resource_allocations request =
  (* Per-owner demands are explicit fixture expectations: one row per input,
     three retained evidence rows, two distinct edge cells, eight active attempt
     records/timers, two retained correlations, and the independently bounded
     34-event queue. Shared truth supply is consumed by two distinct owners. *)
  let quantities=[1;1;2;3;1;1;1;8;2;8;1;1;1;34] in
  let provider=original_reference request "exclusion.chassis" in
  arr(List.map2(fun(owner,unit,scope,capacity)quantity->obj [
    "demand",obj ["owner",owner;"unit",str unit;"scope",str scope;"quantity",Json.int quantity];
    "provider",provider;"capacity",str capacity;"pool",str("executor.pool."^capacity);
    "reserved",Json.int quantity])Original.resource_specs quantities)
let expected_providers request = arr(List.map(fun id->
  let provider=original_provider request id in
  obj ["definition",get "definition"(get "body" provider);"identity",get "identity" provider;
    "body_fingerprint",str(Canonical.fingerprint(get "body" provider))])expected_provider_ids)

(* This oracle authors the original graph, including multiplicity and traversal
   order. It deliberately never calls Policy_provider_prerequisites. *)
let expected_graph ?(catalog_only=false) request =
  let reference=original_reference request in
  let root path id=obj ["origin",obj ["kind",str "source";"path",str path];
    "definition",reference id] in
  let source_roots=List.map(fun(path,id)->root path id)[
    "/deployment/bindings/0/chassis/operational_model","exclusion.chassis";
    "/deployment/bindings/0/chassis/capabilities/0","exclusion.interface";
    "/deployment/bindings/0/chassis/interfaces/0","exclusion.interface";
    "/deployment/bindings/0/chassis/environment/0","exclusion.environment";
    "/deployment/environment/0","exclusion.environment";
    "/program/declarations/0/requires/0","exclusion.interface";
    "/deployment/delivery/arrival","exclusion.delivery";
    "/deployment/delivery/expression","exclusion.delivery";
    "/deployment/delivery/activation","exclusion.delivery";
    "/deployment/delivery/contract","exclusion.delivery"] in
  let pending=List.hd(Json.array(expected_pending request)) in
  let catalog_root=obj ["origin",obj ["kind",str "catalog_dependency";
    "entry_id",get "entry_id" pending;"entry_digest",get "entry_digest" pending;
    "dependency_index",Json.int 0];"definition",get "definition" pending] in
  let node_ids=if catalog_only then ["exclusion.chassis";"exclusion.interface";
    "exclusion.environment";"exclusion.delivery";definition_id]
    else ["exclusion.chassis";"exclusion.interface";definition_id;
      "exclusion.environment";"exclusion.delivery"] in
  let nodes=List.map(fun id->obj ["definition",reference id;
    "provider",get "identity"(original_provider request id)])node_ids in
  let edge source relation target=obj ["source",reference source;"relation",str relation;
    "index",Json.int 0;"target",reference target] in
  obj ["schema_version",str "biocompiler.policy_provider_dependency_graph.v0.1";
    "pending_dependencies",expected_pending request;"roots",arr(source_roots@[catalog_root]);
    "nodes",arr nodes;"edges",arr [
      edge "exclusion.chassis" "chassis_capability" "exclusion.interface";
      edge "exclusion.interface" "interface_environment"
        (if catalog_only then "exclusion.environment" else definition_id);
      edge "exclusion.chassis" "chassis_interface" "exclusion.interface";
      edge "exclusion.chassis" "chassis_environment" "exclusion.environment"];
    "issues",arr []]

(* Complete positive closure fields whose authority exists in original inputs.
   The service tests separately bind the assembly fingerprint to fresh checking;
   an original-only exporter cannot claim an assembly assessment. *)
let expected_closure ?(catalog_only=false) request =
  let selections=at ["composition_rule";"body";"components"]request |> Json.array in
  let definitions=at ["component_library";"components"]request |> Json.array in
  let selection slot=List.find(fun value->get "slot" value=str slot)selections in
  let component slot=get "component"(selection slot) in
  let requirements slot=
    let identity=component slot in
    let definition=List.find(fun value->Json.equal(get "identity" value)identity)definitions in
    at ["body";"provider_requirements"]definition in
  obj ["schema_version",str closure_schema;"profile",str material_profile;
    "status",str "pass";"complete",Json.Bool true;
    "original_request_fingerprint",str(Canonical.fingerprint request);
    "source_catalog",at ["implementation_request";"document";"implementations"]request;
    "pending_dependencies",expected_pending request;
    "instances",arr(List.map(fun slot->obj ["slot",str slot;"component",component slot])expected_instance_names);
    "local_requirements",arr(List.map(fun slot->obj ["slot",str slot;"component",component slot;
      "requirements",requirements slot])expected_instance_names);
    "providers",expected_providers request;"graph",expected_graph ~catalog_only request;
    "operating_domain_fingerprint",str(Canonical.fingerprint(at ["implementation_request";"operating_domain"]request));
    "clock",at ["context";"clock"]request;"recipient",at ["context";"recipient"]request;
    "input_allocations",expected_input_allocations request;"resource_allocations",expected_resource_allocations request;
    "diagnostics",arr [];"empirical",str "unassessed"]

let source_definition request id =
  List.find(fun definition->get "id" definition=str id)
    (at ["implementation_request";"document";"program";"semantics";"definitions"]request |> Json.array)
let rewrite_definition request id transform =
  let original=source_definition request id in
  let updated=transform original in
  let old_reference=definition_reference original and new_reference=definition_reference updated in
  let rec rewrite value =
    if Json.equal value old_reference then new_reference else match value with
    |Json.Array values->arr(List.map rewrite values)
    |Json.Object fields->obj(List.map(fun(key,value)->key,rewrite value)fields)
    |value->value in
  request
  |> edit ["implementation_request";"document";"program";"semantics";"definitions"]
    (fun definitions->arr(List.map(fun value->if get "id" value=str id then updated else value)(Json.array definitions)))
  |> rewrite
  |> edit ["context";"providers"] (fun providers->arr(List.map repin(Json.array providers)))
  |> refresh_catalog

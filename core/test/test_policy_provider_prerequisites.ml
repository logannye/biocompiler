open Bioc_wire
open Bioc_policy_prerequisite_test_support.Literals
open Bioc_policy_prerequisite_test_support.Requests
module RR = Bioc_domain.Policy_realization_request
module R = Bioc_domain.Policy_component_material_request
module X = Bioc_domain.Policy_component_context
module Dependencies = Bioc_domain.Policy_provider_prerequisites

let derive ?charge request =
  Dependencies.derive ?charge
    ~original:(RR.of_prerequisite_json(get "implementation_request" request))
    ~context:(X.of_json(get "context" request)) ()
let graph request=Dependencies.to_json(derive request)
let issue kind code references=obj ["kind",str kind;"code",str code;"references",arr references]
let source_catalog request dependencies = request
  |> put ["implementation_request";"document";"implementations";"implementations";"0";"dependencies"](arr dependencies)
  |> refresh_catalog
let positive ?(catalog_only=false) fixture state_reading =
  let request,_=request_literal ~catalog_only fixture state_reading in
  let parsed=R.of_json request in
  require(Json.equal(R.to_json parsed)request && R.requires_prerequisite_closure parsed)
    "Original prerequisite request changed during typed decoding";
  let count=ref 0 in
  let derived=derive ~charge:(fun n->count:= !count+n) request in
  require(!count>0) "Provider graph traversal omitted work accounting";
  require(Json.equal(Dependencies.to_json derived)(expected_graph ~catalog_only request))
    "Original prerequisite root, edge, identity or traversal inventory changed";
  require(List.length(Dependencies.reachable derived)=5 && List.length(Dependencies.roots derived)=11 &&
    List.length(Dependencies.edges derived)=4 && Dependencies.issues derived=[])
    "Repeated roots became new providers or discarded dependency occurrences";
  require(Json.equal(at ["implementation_request";"document";"program";"declarations"]request)
      (at ["request";"implementation_request";"document";"program";"declarations"]fixture) &&
    Json.equal(at ["implementation_request";"operating_domain"]request)
      (at ["request";"implementation_request";"operating_domain"]fixture))
    "Prerequisite fixture narrowed the original policy or finite operating domain";
  request

let controls request =
  let reference=original_reference request in
  phase "graph: missing and extra original provider bodies";
  let missing=edit ["context";"providers"] (fun providers->arr(List.filter(fun provider->
    provider_definition_id provider<>str definition_id)(Json.array providers)))request in
  let missing_graph=graph missing in
  require(Json.equal(get "issues" missing_graph)(arr [issue "missing" "prerequisite_provider_missing" [reference definition_id]]))
    "Missing transitive prerequisite did not remain an explicit unknown body";
  let missing_node=List.find(fun row->Json.equal(get "definition" row)(reference definition_id))(items "nodes" missing_graph) in
  require(get "provider" missing_node=Json.Null) "Missing prerequisite acquired a fabricated provider pin";
  let extra=repin_provider "exclusion.interface"
    (replace "environment"(reference "exclusion.environment"))request in
  require(Json.equal(get "issues"(graph extra))(arr [issue "extra" "prerequisite_provider_extra" [reference definition_id]]))
    "Unused supplied prerequisite body escaped the exact closure census";
  phase "graph: a cycle cannot discharge itself";
  let cycle=request |> repin_provider "exclusion.interface"
    (replace "environment"(reference "exclusion.interface"))
    |> edit ["context";"providers"] (fun providers->arr(List.filter(fun provider->
      provider_definition_id provider<>str definition_id)(Json.array providers))) in
  require(Json.equal(get "issues"(graph cycle))(arr [issue "cycle" "prerequisite_cycle"
    [reference "exclusion.interface";reference "exclusion.interface"]]))
    "Cyclic provider support became a self-justifying premise";
  phase "graph: source and provider identities stay authoritative";
  let stale_body=modify_provider definition_id
    (put ["body";"recipient";"compartment"](str "nucleus"))request in
  rejected "policy_material_context" "Unpinned prerequisite body cannot enter typed context"
    (fun()->graph stale_body);
  let stale_catalog=put ["implementation_request";"catalog_bindings";"0";"entry_digest"]
    (str(String.make 64 '0'))request in
  rejected "policy_provider_prerequisites" "Stale catalog prerequisite owner cannot resolve"
    (fun()->graph stale_catalog);
  let stale_definition=source_catalog request
    [replace "digest"(str(String.make 64 '0'))(reference "exclusion.interface")] in
  rejected "policy_provider_prerequisites" "Stale prerequisite DefinitionRef cannot resolve"
    (fun()->graph stale_definition);
  phase "graph: duplicate, empty, unsupported and exhausted prerequisites";
  rejected "policy_provider_prerequisites" "Duplicate dependency occurrences cannot inflate a closed inventory"
    (fun()->graph(source_catalog request [reference "exclusion.interface";reference "exclusion.interface"]));
  rejected "policy_provider_prerequisites" "Prerequisite profile cannot silently lose all catalog dependencies"
    (fun()->graph(source_catalog request []));
  let unsupported=rewrite_definition request definition_id (replace "category"(str "operation")) in
  require(Json.equal(get "issues"(graph unsupported))(arr [issue "unsupported" "prerequisite_definition_unsupported"
    [original_reference unsupported definition_id]]))
    "An uninterpreted source category was accepted as an executable prerequisite";
  rejected "fixture_prerequisite_charge" "Exhausted dependency traversal cannot return a graph"
    (fun()->derive ~charge:(fun _->Diagnostic.fail "fixture_prerequisite_charge" "exhausted")request);
  phase "graph: explicit legacy profile boundary";
  rejected "policy_realization_request" "Legacy realization entry cannot decode prerequisite inputs"
    (fun()->RR.of_json(get "implementation_request" request));
  let legacy_context=get "context" request |> replace "profile"
    (str "biocompiler.policy_instance_component_mrna.v0.1") in
  rejected "policy_provider_prerequisites" "Dependency derivation cannot bless a legacy context"
    (fun()->Dependencies.derive
      ~original:(RR.of_prerequisite_json(get "implementation_request" request))
      ~context:(X.of_json legacy_context) ())

let () =
  try
    require(Array.length Sys.argv=3) "Supply the two complete original A/B inputs";
    let a=read Sys.argv.(1) and b=read Sys.argv.(2) in
    phase "graph A: original transitive prerequisite";
    let request=positive a false in
    phase "graph B: original state-reading transitive prerequisite";
    ignore(positive b true);
    phase "graph: catalog-only prerequisite is a distinct root";
    ignore(positive ~catalog_only:true a false);
    controls request;
    Printf.printf "provider prerequisite graph: %d independent controls passed\n" !checks
  with Diagnostic.Error value->
    Printf.eprintf "Diagnostic.Error(code=%s,path=%s,message=%s)\n" value.code
      (match value.path with None->"<none>"|Some path->path)value.message;exit 1

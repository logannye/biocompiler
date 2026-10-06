open Bioc_wire
open Bioc_policy_component_test_support.Literals
open Bioc_policy_component_test_support.Requests
let positive fixture state_reading =
  let raw,expected_union=request_literal fixture state_reading in
  let original=get "request" fixture in
  (* The old source/context/request remain independently decodable and unchanged;
     no old accepted token is imported into the new representation. *)
  ignore (R1.of_json original);ignore (X1.of_json (get "context" original));
  let charged=ref 0 in
  let decoded=R.of_json ~charge:(fun amount -> charged := !charged+amount) raw in
  require (Json.equal raw (R.to_json decoded) && R.fingerprint decoded=Canonical.fingerprint raw)
    "Complete supplied request spelling or identity was lost";
  require (!charged>0 && !charged=R.decoding_work decoded) "Request decoding work was not fully charged";
  let original_inner=get "implementation_request" original in
  require (Json.equal (RR.to_json (R.implementation_request decoded)) original_inner) "New request replaced original realization authority";
  let composition_rule=R.composition_rule decoded in
  require (Json.equal (X.ordered_union_json composition_rule) expected_union) "Reconstructed union differs from independent node/wire/input/group/export literals";
  require (X.ordered_union_digest composition_rule=Canonical.fingerprint expected_union) "Union digest does not pin complete literal graph";
  require (List.length (items "nodes" expected_union)=(if state_reading then 17 else 15) &&
    List.length (items "wires" expected_union)=(if state_reading then 25 else 22) &&
    List.length (items "semantic_exports" expected_union)=(if state_reading then 23 else 21)) "Original union census changed";
  let keys=List.map (fun (key:R.resource_key) -> obj ["owner",R.resource_owner_to_json key.owner;
    "unit",str (RC.resource_unit_name key.unit);"scope",str (RC.resource_scope_name key.scope)]) (R.resource_keys composition_rule) in
  let expected_keys=List.map (fun (owner,unit,scope,_) -> obj ["owner",owner;"unit",str unit;"scope",str scope]) resource_specs in
  require (List.length keys=14 && Json.equal (arr keys) (arr expected_keys)) "Complete resource key/owner/scope order differs from independent prerequisites";
  require (List.map (fun (row:R.input_binding) -> row.input_id,row.source,row.channel) (R.input_bindings decoded)=
    ["condition","condition","condition";"feedback","response","feedback"]) "Complete source input identities changed";
  require (List.length (R.resource_bindings decoded)=14) "Resource bridge omitted an original prerequisite";
  let context=R.context decoded and layout=X.record_layout (R.context decoded) in
  require (Json.equal (X.to_json context) (get "context" raw)) "Complete context/provider bodies were lost";
  require (layout.union_digest=Canonical.fingerprint expected_union &&
    layout.domain_digest=F.digest (RR.operating_domain (R.implementation_request decoded)) &&
    Json.equal (P.to_json layout.rule) (P.to_json (A.identity composition_rule))) "Context transferred across original rule/domain/union";
  require (X.record_layout_fingerprint layout=Canonical.fingerprint (at ["context";"record_layout"] raw)) "Full capacity record identity changed";
  require ((X.delivery_group context).max_total_bases=Some (if state_reading then 18 else 17)) "Independently authored output length ceiling changed";
  require ((R.budgets decoded).max_work=500000000 && (R.budgets decoded).max_report_bytes=8323072 &&
    (R.budgets decoded).max_report_nodes=249968) "Original exploration/publication ceilings changed";
  raw,decoded
let context_controls raw =
  let context=get "context" raw in
  let reject label message transform = rejected ~message "policy_component_context" label (fun () -> X.of_json (transform context)) in
  reject "v1 whole-kernel context is not the new profile" "Unsupported original composition context profile."
    (replace "profile" (str "biocompiler.policy_truth_mrna.v0.1"));
  reject "explicit helper is unsupported" "Composition context does not support executable or delivered helpers."
    (replace "helpers" (arr [Json.Null]));
  reject "complete reason record cannot be truncated" "Composition layout must retain the new profile and complete semantic record shapes."
    (put ["record_layout";"record_shapes";"truth_cells"] (arr [str "defined";str "three_valued_truth"]));
  reject "record width is bounded" "Composition layout count exceeds its finite bound."
    (put ["record_layout";"identifier_bytes"] (Json.int 1000001));
  reject "capacity pins include every record field" "Provider capacity does not pin the complete original composition record layout."
    (put ["record_layout";"identifier_bytes"] (Json.int 513));
  reject "complete provider definitions are unique" "Duplicate composition provider definition identity."
    (edit ["providers"] (fun rows -> let rows=Json.array rows in arr (rows@[List.hd rows])));
  reject "one pool cannot masquerade as two capacities" "Duplicate composition capacity pool identity."
    (fun context -> context |> put ["providers";"0";"body";"capacities";"1";"pool_id"]
      (at ["providers";"0";"body";"capacities";"0";"pool_id"] context) |> refresh_provider_pins);
  rejected "unknown_field" "old kernel pin cannot stand in for original union" (fun () -> X.of_json
    (edit ["record_layout"] (add "kernel_digest" (str (String.make 64 '0'))) context));
  rejected "policy_material_context" "changed capacity body cannot reuse provider identity" (fun () -> X.of_json
    (put ["providers";"0";"body";"capacities";"0";"quantity"] (Json.int 1) context));
  (* Decoding preserves undersized declarations; it is not a sufficiency proof. *)
  let undersized=context |> put ["record_layout";"identifier_bytes"] (Json.int 1)
    |> put ["delivery_group";"max_total_bases"] (Json.int 1) |> refresh_layout_pins |> X.of_json in
  require ((X.record_layout undersized).identifier_bytes=1 && (X.delivery_group undersized).max_total_bases=Some 1)
    "Shape decoder silently supplied capacity/length sufficiency";
  rejected "policy_material_context" "v1 context parser cannot authorize composition" (fun () -> X1.of_json context)
let request_controls raw =
  let reject label message transform = rejected ~message "policy_component_material_request" label (fun () -> R.of_json (transform raw)) in
  reject "whole-graph profile cannot silently route here" "Unsupported original component material request profile."
    (replace "profile" (str "biocompiler.policy_truth_mrna.v0.1"));
  reject "original catalog entry identity" "Composition bridge differs from the complete original realization catalog binding."
    (put ["catalog_binding";"entry_id"] (str "invented.entry"));
  reject "matching bridge hashes do not replace actual source entry"
    "Composition bridge does not retain the complete source catalog entry and definitions."
    (fun raw -> raw |> put ["catalog_binding";"entry_digest"] (str (String.make 64 '0'))
      |> put ["implementation_request";"catalog_bindings";"0";"entry_digest"] (str (String.make 64 '0')));
  reject "original operation reference" "Composition bridge changes the original operation or realization DefinitionRef."
    (put ["catalog_binding";"operation";"digest"] (str (String.make 64 '0')));
  reject "re-pinned bridge reference must still resolve original definition body"
    "Composition DefinitionRef differs from its complete original definition body."
    (fun raw -> raw |> put ["catalog_binding";"operation";"digest"] (str (String.make 64 '0'))
      |> put ["implementation_request";"catalog_bindings";"0";"operation";"digest"] (str (String.make 64 '0')));
  reject "stale complete rule pin" "Composition catalog bridge must pin exactly the selected components and complete original rule in order."
    (put ["catalog_binding";"rule";"content_fingerprint"] (str (String.make 64 '0')));
  reject "one driver cannot replace decision ownership" "Composition catalog bridge must pin exactly the selected components and complete original rule in order."
    (put ["catalog_binding";"components";"0";"component"] (at ["catalog_binding";"components";"1";"component"] raw));
  reject "catalog component order is explicit" "Composition catalog bridge must pin exactly the selected components and complete original rule in order."
    (edit ["catalog_binding";"components"] (fun rows -> arr (List.rev (Json.array rows))));
  reject "complete primitive membership remains original" "Selected component primitive lacks the original catalog model membership."
    (edit ["implementation_request";"catalog_bindings";"0";"models"] (fun rows -> arr (List.filter
      (fun row -> get "id" row<>str "exclusion.primitive.attempt") (Json.array rows))));
  List.iter (fun (field,value) -> reject ("re-pinned context "^field)
    "Composition record layout must pin the exact original rule, ordered union, operating domain and slot layout."
    (edit ["context"] (fun context -> context |> put ["record_layout";field] value |> refresh_layout_pins)))
    ["rule",put ["id"] (str "another.rule") (at ["context";"record_layout";"rule"] raw);
     "union_digest",str (String.make 64 '0');"domain_digest",str (String.make 64 '0');"slots",Json.int 1];
  reject "missing complete input binding" "Composition input bindings must retain the complete original global input order."
    (edit ["input_bindings"] (fun rows -> arr (List.tl (Json.array rows))));
  reject "input order retained" "Composition input bindings must retain the complete original global input order."
    (edit ["input_bindings"] (fun rows -> arr (List.rev (Json.array rows))));
  reject "feedback effect cannot replace observation identity" "Composition input must name an original source observation or effect of the matching kind."
    (put ["input_bindings";"0";"source"] (str "response"));
  reject "channel identity retained" "Composition input provider must retain the declared channel and exact source/kind relation."
    (put ["input_bindings";"0";"channel"] (str "feedback"));
  reject "missing channel cannot be inferred" "Composition input provider must retain the declared channel and exact source/kind relation."
    (put ["input_bindings";"0";"channel"] (str "missing.channel"));
  reject "complete resource inventory" "Composition resource bindings must retain every local prerequisite and global layout key exactly once in order."
    (edit ["resource_bindings"] (fun rows -> arr (List.tl (Json.array rows))));
  reject "local resource owner cannot cross components" "Composition resource bindings must retain every local prerequisite and global layout key exactly once in order."
    (put ["resource_bindings";"1";"owner";"slot"] (str "driver"));
  reject "resource scope is an independent typed key" "Composition resource bindings must retain every local prerequisite and global layout key exactly once in order."
    (put ["resource_bindings";"0";"scope"] (str "per_executor"));
  reject "missing declared capacity" "Composition resource binding must name an original capacity with the exact unit and scope."
    (put ["resource_bindings";"0";"capacity"] (str "absent.capacity"));
  reject "capacity unit cannot stand in for input rows" "Composition resource binding must name an original capacity with the exact unit and scope."
    (put ["resource_bindings";"0";"capacity"] (str "shared.truth"));
  let observation_ref=at ["implementation_request";"document";"program";"declarations";"4";"contract"] raw in
  reject "a valid source definition is not a supplied provider" "Composition binding names an absent complete original provider DefinitionRef."
    (put ["resource_bindings";"0";"provider"] observation_ref);
  reject "provider references close over original definitions" "Composition reference does not resolve to one complete original definition."
    (put ["resource_bindings";"0";"provider";"id"] (str "absent.definition"));
  reject "budget profile is independently versioned" "Unsupported composition resource profile."
    (put ["budgets";"profile"] (str "biocompiler.policy_material_resources.v0.1"));
  reject "declared work ceiling is closed" "Composition resource allowance exceeds its closed bound."
    (put ["budgets";"max_work"] (Json.int 1000000001));
  let extra=at ["component_library";"components";"0"] raw |> put ["identity";"id"] (str "unused.original.component") in
  let extra_raw=edit ["component_library";"components"] (fun rows -> arr (Json.array rows@[extra])) raw in
  ignore (L.of_json ~library:(RR.implementation_library (RR.of_json (get "implementation_request" raw))) (get "component_library" extra_raw));
  reject "valid unused component is still outside the single-rule request" "Composition request allows only its two selected original components, without alternatives or helpers."
    (fun _ -> extra_raw);
  rejected "unknown_field" "candidate cannot be embedded as original authority" (fun () -> R.of_json (add "candidate" Json.Null raw));
  rejected "unknown_field" "serialized PASS cannot confer capability" (fun () -> R.of_json (add "accepted" (Json.Bool true) raw));
  let missing=obj (List.filter (fun (key,_) -> key<>"context") (Json.object_fields raw)) in
  rejected "missing_field" "context cannot default away" (fun () -> R.of_json missing);
  rejected "literal_charge_denied" "budget owner can deny decoding before authority" (fun () ->
    R.of_json ~charge:(fun _ -> Diagnostic.fail "literal_charge_denied" "No decoding allowance.") raw);
  let rec cyclic=Json.Array [cyclic] in
  rejected "policy_material_input_limit" "cycle rejected by bounded preflight" (fun () -> R.of_json cyclic);
  rejected "policy_material_input_limit" "oversized scalar rejected before decode" (fun () ->
    R.of_json (replace "profile" (str (String.make 1000001 'x')) raw));
  rejected "invalid_type" "floating budget is not exact integer authority" (fun () -> R.of_json (put ["budgets";"max_work"] (Json.Float 1.) raw));
  rejected "missing_field" "v1 material request cannot coerce composition authority" (fun () -> R1.of_json raw)
let run first second =
  let raw_a,a=positive first false and raw_b,b=positive second true in
  require (C.fingerprint (A.component (R.composition_rule a) A.Driver)=C.fingerprint (A.component (R.composition_rule b) A.Driver))
    "Reusable driver acquired per-source or per-context identity";
  require (R.fingerprint a<>R.fingerprint b && X.fingerprint (R.context a)<>X.fingerprint (R.context b))
    "Full source/context authority transferred across distinct originals";
  require (at ["context";"providers";"0";"body";"capacities";"0";"quantity"] raw_a=Json.int 2)
    "Shared capacity mutation must start from the literal two-cell pool";
  List.iter context_controls [raw_a;raw_b];request_controls raw_a;
  rejected ~message:"Composition record layout must pin the exact original rule, ordered union, operating domain and slot layout."
    "policy_component_material_request" "A context cannot transfer to complete B request"
    (fun () -> R.of_json (replace "context" (get "context" raw_a) raw_b));
  let b17=R.of_json (put ["context";"delivery_group";"max_total_bases"] (Json.int 17) raw_b) in
  require ((X.delivery_group (R.context b17)).max_total_bases=Some 17)
    "Request shape decoder must leave B length18 versus capacity17 for context sufficiency checking";
  let reordered=R.of_json (edit ["component_library";"components"] (fun rows -> arr (List.rev (Json.array rows))) raw_a) in
  require (R.fingerprint reordered<>R.fingerprint a && A.fingerprint (R.composition_rule reordered)=A.fingerprint (R.composition_rule a))
    "Full library order identity was erased or replaced reusable rule meaning";
  List.iter (fun fixture -> rejected "missing_field" "old v1 request has no original component authority"
    (fun () -> R.of_json (get "request" fixture))) [first;second];
  Printf.printf "component material request: %d independent source/shape controls passed\n" !checks
let () =
  try
    require (Array.length Sys.argv=3) "Supply independent A/B original request fixtures";
    run (read Sys.argv.(1)) (read Sys.argv.(2))
  with Diagnostic.Error value ->
    Printf.eprintf "Diagnostic.Error(code=%s,path=%s,message=%s)\n" value.code
      (Option.value ~default:"<none>" value.path) value.message;
    exit 1

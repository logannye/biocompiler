open Bioc_wire
open Bioc_policy_component_test_support.Literals
open Bioc_policy_component_test_support.Requests
module Originals = Bioc_policy_component_test_support.Selection_requests
module Selection = Bioc_domain.Policy_component_selection_request
module Common = Bioc_realization_checker.Policy_component_selection_common
module W = Bioc_checker.Work_budget

(* Complete original requests and literal expected RNA are authored in the
   private domain-only support module. This suite never compiles a candidate,
   calls an inner checker, or obtains a checked material/selection capability. *)
let budget maximum=W.create ~profile:"literal.selection.common"
  ~error_code:"literal_common_work" ~maximum ()
let check raw =
  let request=Selection.of_json raw and work=budget 1000000000 in
  let ()=Common.check ~budget:work ~request in
  require (W.remaining work<1000000000 && not (W.exhausted work))
    "Common comparison must charge its caller without exhausting the full literal allowance";
  request
let alternative id rank request=obj ["id",str id;"rank",Json.int rank;"request",request]
let child id raw=List.find (fun row -> get "id" row=str id) (items "alternatives" raw) |> get "request"
let change_child id transform=edit ["alternatives"] (fun rows -> arr (List.map (fun row ->
  if get "id" row=str id then edit ["request"] transform row else row) (Json.array rows)))
let refresh_context raw=edit ["context"] refresh_layout_pins raw
let provider index transform=edit ["context";"providers";string_of_int index]
  (fun row -> transform row |> repin)
let changed_component index transform change_rule raw =
  let index=string_of_int index in
  let component=at ["component_library";"components";index] raw |> transform |> repin in
  let rule=get "composition_rule" raw
    |> put ["body";"components";index;"component"] (get "identity" component)
    |> change_rule |> repin in
  raw |> put ["component_library";"components";index] component
    |> replace "composition_rule" rule
    |> put ["catalog_binding";"components"] (at ["body";"components"] rule)
    |> put ["catalog_binding";"rule"] (get "identity" rule)
    |> put ["context";"record_layout";"rule"] (get "identity" rule) |> refresh_context
let changed_product raw =
  (* MM is independently declared as a different supplied product premise.
     Shape admission does not translate the unchanged MA driver. Both the local
     product and the original rule premise are changed and completely pinned. *)
  let product=at ["component_library";"components";"1";"body";"products";"0";"expected"] raw
    |> replace "sequence" (str "MM")
    |> put ["identity";"content_fingerprint"] (str (Canonical.fingerprint (PM.product_content_json "MM"))) in
  changed_component 1 (put ["body";"products";"0";"expected"] product)
    (put ["body";"material_authority";"members";"0";"product"] product) raw
let changed_domain raw =
  let changed=put ["implementation_request";"operating_domain";"logical_limits";"max_source_attempts"] (Json.int 3) raw in
  changed |> put ["context";"record_layout";"domain_digest"]
    (str (Canonical.fingerprint (at ["implementation_request";"operating_domain"] changed))) |> refresh_context

(* A same-length driver UTR change, with an independently supplied full root and
   every affected original pin repaired. The encoded product remains MA; that
   cannot make the changed driver an allowed decision-leader variant. *)
let changed_driver raw =
  let root_raw=root "driver_body" "AUGGCUUAACGAAAA" true in
  let changed_component=at ["component_library";"components";"1"] raw
    |> put ["body";"root"] root_raw |> repin in
  let changed_rule=get "composition_rule" raw
    |> put ["body";"components";"1";"component"] (get "identity" changed_component)
    |> edit ["body";"material_authority";"template";"sources"] (fun rows ->
      arr (List.map (fun row -> if get "id" row=str "driver_body" then root_raw else row) (Json.array rows))) |> repin in
  raw |> put ["component_library";"components";"1"] changed_component
    |> replace "composition_rule" changed_rule
    |> put ["catalog_binding";"components"] (at ["body";"components"] changed_rule)
    |> put ["catalog_binding";"rule"] (get "identity" changed_rule)
    |> put ["context";"record_layout";"rule"] (get "identity" changed_rule) |> refresh_context

let positive fixture =
  let raw=Originals.selection_literal fixture in
  let short=child "short" raw and long=child "long" raw in
  let original,_=request_literal fixture false in
  let components raw=items "components" (get "component_library" raw) in
  require (List.map (fun (row:Originals.case) -> row.id,row.rank,row.expected_sequence) (Originals.cases fixture)=
    ["short",1,"CCAUGGCUUAAGGAAAA";"long",0,"CGCAUGGCUUAAGGAAAA"])
    "Selection originals lost the independently declared rank/base expectations";
  List.iter (fun item ->
    ignore (R.of_json item);
    List.iter (fun field -> require (Json.equal (get field item) (get field original))
      ("Material original changed common "^field))
      ["implementation_request";"input_bindings";"resource_bindings";"budgets"];
    require (at ["context";"delivery_group";"max_total_bases"] item=Json.int 18)
      "Both original inner delivery obligations must remain eighteen";
    require (Json.equal (List.nth (components item) 1) (List.nth (components original) 1))
      "Selection original changed the shared complete driver";
    require (Json.equal (at ["body";"fragment"] (List.hd (components item)))
      (at ["body";"fragment"] (List.hd (components original)))) "Selection original replaced the A decision semantics";
    require (List.map (at ["body";"definition"]) (at ["context";"providers"] item |> Json.array)=
      List.map (at ["body";"definition"]) (at ["context";"providers"] original |> Json.array))
      "Content re-pinning replaced an original provider DefinitionRef") [short;long];
  require (at ["component_library";"components";"0";"body";"root";"molecule";"sequence"] short=str "CC" &&
    at ["component_library";"components";"0";"body";"root";"molecule";"sequence"] long=str "CGC")
    "Leader variants did not retain their independently authored roots";
  let request=check raw in
  require ((Selection.anchor request).id="long")
    "ASCII anchor must be the three-base long original, independently of ranks/input order";
  ignore (check (edit ["alternatives"] (fun rows -> arr (List.rev (Json.array rows))) raw));
  List.iter (fun limit -> ignore (check (put ["predicate";"max_total_nt"] (Json.int limit) raw))) [16;18];
  let equal=Originals.component_request_literal fixture Originals.Equal_length in
  require (Originals.expected_sequence Originals.Equal_length="GGAUGGCUUAAGGAAAA")
    "Equal-length changed-bases expectation must remain a literal";
  ignore (check (replace "alternatives" (arr [alternative "short" 1 short;alternative "other" 0 equal]) raw));
  ignore (check (replace "alternatives" (arr [alternative "z" 0 short;alternative "A" 2 short]) raw));
  ignore (check (replace "alternatives" (arr [alternative "only" 0 short]) raw));
  raw

let controls fixture_b raw =
  let reject label transform =
    (* Decode outside the asserted rejection: these are complete, well-formed
       originals. A shape failure must not impersonate common-meaning checking. *)
    let request=Selection.of_json (change_child "short" transform raw) in
    rejected "policy_component_selection_common" label (fun () ->
      Common.check ~budget:(budget 1000000000) ~request) in
  List.iter (fun (label,transform) -> reject label transform) [
    "original program identity",put ["implementation_request";"document";"program";"id"] (str "another.original.program");
    "weaker source assurance horizon",put ["implementation_request";"document";"assurance";"horizon";"amount"] (str "5");
    "different complete implementation library",put ["implementation_request";"implementation_library";"version"] (str "2");
    "different original operating domain",changed_domain;
    "reduced original exploration work",put ["implementation_request";"budgets";"max_work"] (Json.int 99999999);
    "reduced child work",put ["budgets";"max_work"] (Json.int 499999999);
    "changed complete decision prerequisite minimum",changed_component 0
      (put ["body";"provider_requirements";"1";"minimum"] (Json.int 2)) Fun.id;
    "changed complete driver and rule product premise",changed_product;
    "reduced child publication",put ["budgets";"max_report_bytes"] (Json.int 8323071);
    "relaxed base delivery ceiling",put ["context";"delivery_group";"max_total_bases"] (Json.int 19);
    "changed recipient identity",put ["context";"recipient";"identity"] (str "another.cell");
    "changed placement compartment",put ["context";"placement";"compartment"] (str "nucleus");
    "changed clock relation",put ["context";"clock";"period_seconds"] (str "0.5");
    "re-pinned record numeric bound",(fun value -> value |> put ["context";"record_layout";"identifier_bytes"] (Json.int 513) |> refresh_context);
    "re-pinned provider quantity",provider 0 (put ["body";"capacities";"0";"quantity"] (Json.int 3));
    "re-pinned resource pool",provider 0 (put ["body";"capacities";"0";"pool_id"] (str "another.pool"));
    "re-pinned provider availability",provider 0 (put ["body";"availability";"duration_max"] (str "7"));
    "re-pinned provider recipient",provider 0 (put ["body";"recipient";"identity"] (str "another.cell"));
    "re-pinned channel subject",provider 2 (put ["body";"channels";"0";"subject"] (str "another.subject"));
    "different driver root with the same product and length",changed_driver];
  let b=fst (request_literal fixture_b true) |> put ["context";"delivery_group";"max_total_bases"] (Json.int 18) in
  reject "B is a different program, never the long A material alternative" (fun _ -> b);
  let request=Selection.of_json raw and tiny=budget 1 in
  rejected "literal_common_work" "Common comparison obeys the caller's tiny work ceiling" (fun () ->
    Common.check ~budget:tiny ~request);
  require (W.exhausted tiny) "Common work failure must remain sticky in the caller"

let () =
  try
    require (Array.length Sys.argv=3) "Supply A originals and B only for a different-program negative control";
    let raw=positive (read Sys.argv.(1)) in controls (read Sys.argv.(2)) raw;
    Printf.printf "component selection common: %d independent original/meaning controls passed\n" !checks
  with Diagnostic.Error value ->
    Printf.eprintf "Diagnostic.Error(code=%s,path=%s,message=%s)\n" value.code
      (Option.value ~default:"<none>" value.path) value.message; exit 1

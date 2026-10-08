(* Complete supplied helper originals. Reuse only the independent P4 literal
   authority for the unchanged therapeutic graph, products and finite domain. *)
include Bioc_policy_multi_member_test_support.Literals
module Previous = Bioc_policy_multi_member_test_support.Requests
let material_profile="biocompiler.policy_grounded_helper_prerequisite_mrna.v0.1"
let assembly_profile="biocompiler.policy_grounded_helper_component_assembly.v0.1"
let helper_definition=obj["$type",str "SemanticDefinition";"id",str "fixture.grounded_helper_capacity";
  "version",str "1";"category",str "capability";
  "meaning",str "Supplied source-independent helper expression completion and retained-record capacity; no empirical claim.";
  "parameters",arr [];"result",Json.Null;"clauses",arr [];"assumptions",arr [];
  "executor_kind",Json.Null;"subject_kind",Json.Null]
let helper_reference=reference helper_definition
let helper_source="source_helper"
let helper_member="helper_rna"
let helper_root="root_helper"
let helper_sequence alternate=if alternate then "CCAUGGGUUAAGGAAAA" else "CCAUGGCUUAAGGAAAA"
let helper_peptide alternate=if alternate then "MG" else "MA"
let full_availability=obj["onset_min",str "0";"onset_max",str "0";"duration_min",str "7";"duration_max",str "7"]
let helper_availability=obj["onset_min",str "1";"onset_max",str "1";"duration_min",str "6";"duration_max",str "6"]
let invocation_limits fixture=put["candidate";"max_work"](Json.int 2_000_000)(get "limits" fixture)
let shifted_fixture fixture=
  let rec extend=function
    |Json.Object fields when List.mem_assoc "onset_min" fields && List.mem_assoc "duration_min" fields->full_availability
    |Json.Object fields->obj(List.map(fun(key,value)->key,extend value)fields)
    |Json.Array values->arr(List.map extend values)|value->value in
  fixture |> put["request";"context";"clock";"origin_seconds"](str "2")
    |> edit["request";"context";"providers"](fun raw->arr(List.map(fun value->edit["body"]extend value |> repin)(Json.array raw)))
let helper_molecule fixture alternate ~output=
  let id=if output then helper_member else helper_root in
  let baseline=at["expected";"molecule"]fixture in
  let frame=id^".frame" and root_frame=helper_root^".frame" in
  let value=baseline |> reframe frame |> replace "id"(str id) |> put["space";"id"](str frame)
    |> replace "form"(str(if output then "delivered_rna"else "primary_rna"))
    |> replace "sequence"(str(helper_sequence alternate))in
  let path=at["assembly";"0";"destination"]value in
  let origin=at["assembly";"0"]value |> replace "id"(str(id^(if output then ".origin"else ".self")))
    |> replace "destination" path |> replace "source_path"(reframe root_frame path)
    |> replace "source_space"(get "space" value |> replace "id"(str root_frame))in
  replace "assembly"(arr[origin])value
let helper_product fixture alternate=
  let base=at["request";"composition_rule";"body";"material_authority";"members";"0";"product"]fixture in
  let spelling=helper_peptide alternate in
  let content=obj["schema_version",str "biocompiler.policy_mrna_product_content.v0.1";"alphabet",str "protein";
    "sequence_extent",str "complete";"sequence",str spelling]in
  base |> replace "identity"(pin "source" "helper_rna.artificial.product" content) |> replace "sequence"(str spelling)
let helper_material fixture alternate=
  let baseline=at["request";"composition_rule";"body";"material_authority";"members";"0"]fixture in
  let root=at["body";"root"](List.hd(old_components fixture)) |> replace "id"(str helper_root)
    |> replace "molecule"(helper_molecule fixture alternate ~output:false)in
  let body=obj["root",root;"regions",get "regions" baseline;"product",helper_product fixture alternate;
    "chemistry",get "chemistry"(helper_molecule fixture alternate ~output:false);
    "capability",helper_reference;"prerequisites",arr []]in
  named "grounded_helper.material" body |> add "schema_version"(str "biocompiler.policy_helper_material.v0.1")
    |> add "profile"(str "biocompiler.policy_grounded_helper_rna.v0.1")
let helper_declaration=obj["schema_version",str "biocompiler.architecture_helper.v0.1";
  "id",str "grounded_helper";"capability",str "fixture.grounded_helper_capacity";
  "consumer_component_ids",arr(List.map str slots);"recipient_role",str "executor";"compartment",str "cytoplasm";
  "availability",str "other_rna";"initialization",str "after_expression";"sharing",str "shared";
  "capacity",Json.int 2;"assumptions",arr [];"placement_id",str "helper_rna.placement";
  "provider_component_id",str "grounded_helper.material";"depends_on",arr []]
let source_literal fixture=
  let original=Bioc_policy_multi_member_test_support.Literals.source_literal fixture false in
  let entry=at["document";"implementations";"implementations";"0"]original
    |> replace "dependencies"(arr[transport_reference;helper_reference])in
  original |> edit["document";"program";"semantics";"definitions"](fun raw->arr(Json.array raw@[helper_definition]))
    |> edit["document";"deployment";"payload"](fun row->row |> replace "helper_count"(Json.int 1)
        |> replace "member_count"(Json.int 3) |> replace "orf_count"(Json.int 3) |> replace "product_count"(Json.int 3))
    |> put["document";"implementations";"implementations";"0"]entry
    |> put["catalog_bindings";"0";"entry_digest"](str(Canonical.fingerprint entry))
let material_authority fixture alternate original=
  let helper=helper_material fixture alternate in
  let template=get "template" original in
  let output=List.hd(items "output_members" template) |> replace "id"(str helper_member)
    |> replace "space_id"(str(helper_member^".frame")) |> put["value";"id"](str helper_source)in
  let requirement=List.hd(items "requirements" template) |> replace "id"(str helper_member)
    |> replace "member_id"(str helper_member) |> replace "category"(str "delivered_helper")
    |> edit["roles"](fun raw->arr(List.map(fun role->role |> replace "id"(str "helper_rna.role")
        |> replace "role"(str "helper") |> replace "purpose"(str "helper"))(Json.array raw)))in
  let member=List.hd(items "members" original) |> replace "id"(str helper_member)
    |> replace "product"(helper_product fixture alternate)
    |> replace "chemistry"(get "chemistry"(helper_molecule fixture alternate ~output:true))in
  original |> replace "template"(template
    |> edit["sources"](fun raw->arr(Json.array raw@[at["body";"root"]helper |> replace "id"(str helper_source)]))
    |> edit["output_members"](fun raw->arr(Json.array raw@[output]))
    |> edit["requirements"](fun raw->arr(Json.array raw@[requirement]))
    |> edit["payload_structures"](fun raw->arr(Json.array raw@[List.hd(Json.array raw) |> replace "member_id"(str helper_member)])))
    |> edit["member_order"](fun raw->arr(Json.array raw@[str helper_member]))
    |> edit["members"](fun raw->arr(Json.array raw@[member]))

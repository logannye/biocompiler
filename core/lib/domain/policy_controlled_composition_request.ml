open Bioc_wire
module D=Policy_document
module Domain=Policy_controlled_domain
module Material=Policy_mrna_structure
module M=Molecular_record
module P=Pinned_identity
module Old=Policy_material_request
let schema_version="biocompiler.policy_component_material_request.v0.14"
let profile="biocompiler.policy_controlled_composition_mrna.v0.1"
let resource_profile="biocompiler.policy_controlled_composition_resources.v0.1"
type budgets={max_work:int;max_report_bytes:int;max_report_nodes:int}
type t={original:Json.t;identity:string;work:int;document_value:D.controlled;
  domain_value:Domain.t;material_value:Material.t;budget:budgets}
let get key value=Json.field key(Json.object_fields value)
let exact keys value=Json.exact_fields keys(Json.object_fields value)
let str value=Json.String value
let require condition message=Diagnostic.require condition "controlled_authority_request" message
let text value=M.text ~maximum:4096 value
let integer maximum value=let number=Json.integer value in
  require(Z.sign number>0 && Z.leq number(Z.of_int maximum))"Integer is outside the closed positive resource range.";
  Z.to_int number
let digest value=let value=Json.string value in
  require(String.length value=64 && String.for_all(function '0'..'9'|'a'..'f'->true|_->false)value)
    "Expected exact lowercase SHA-256.";value
let list maximum value=M.array ~maximum value
let texts maximum value=let values=List.map text(list maximum value)in
  require(List.length values=List.length(List.sort_uniq String.compare values))"Duplicate authority text identity.";values
let ref_ kind value=exact["$type";"id";"kind"]value;
  require(get "$type" value=str "Ref" && get "kind" value=str kind)"Wrong typed source reference.";
  ignore(text(get "id" value))
let definition value=exact["$type";"id";"version";"digest"]value;
  require(get "$type" value=str "DefinitionRef")"Expected complete DefinitionRef.";
  ignore(text(get "id" value));ignore(text(get "version" value));ignore(digest(get "digest" value))
let schema expected value=require(get "schema_version" value=str expected)"Unsupported authority schema."
let pair value=let values=list 2 value in require(List.length values=2)"Exactly two ordered records are required.";values
let delays value=exact["onset_ticks";"cessation_ticks";"reactivation_ticks"]value;
  List.iter(fun key->ignore(integer 10000(get key value)))["onset_ticks";"cessation_ticks";"reactivation_ticks"]
let deadlines value=let keys=["onset_ticks";"controller_off_ticks";"antigen_off_ticks";"component_off_ticks";"reactivation_ticks"]in
  exact keys value;List.iter(fun key->ignore(integer 10000(get key value)))keys
let binding with_identity value=
  exact(["product_parameter";"member_id";"cds_id";"product_definition"]@(if with_identity then["product_identity"]else[]))value;
  ref_ "Parameter"(get "product_parameter" value);ignore(text(get "member_id" value));
  ignore(text(get "cds_id" value));definition(get "product_definition" value);
  if with_identity then ignore(P.of_json(get "product_identity" value))
let controller value=exact["definition";"executor";"scope"]value;definition(get "definition" value);
  ref_ "Role"(get "executor" value);require(get "scope" value=str "executor")"Controller requires executor scope."
let contract value=
  exact["schema_version";"profile";"products";"controller";"readout";"actual_delays";"requested_deadlines";"mechanism";"initial_activity"]value;
  schema "biocompiler.policy_controlled_composition_contract.v0.1" value;
  require(get "profile" value=str profile && get "mechanism" value=str "deterministic_delay" && get "initial_activity" value=str "background")
    "Unsupported controlled contract family.";
  List.iter(binding false)(pair(get "products" value));controller(get "controller" value);
  let readout=get "readout" value in exact["activity";"definition";"physical_bands"]readout;
  ref_ "ControlledActivity"(get "activity" readout);definition(get "definition" readout);
  require(get "physical_bands" readout=Json.Array[str "background";str "active"])"Wrong physical activity bands.";
  delays(get "actual_delays" value);deadlines(get "requested_deadlines" value)
let project value=
  exact["project_id";"title";"sources";"assumptions"]value;
  ignore(text(get "project_id" value));ignore(text(get "title" value));
  let sources=list 128(get "sources" value)in require(sources<>[])"Project needs original source provenance.";
  List.iter(fun source->exact["id";"locator";"version";"sha256";"role";"reuse_terms"]source;
    List.iter(fun key->ignore(text(get key source)))["id";"locator";"version";"role";"reuse_terms"];
    ignore(digest(get "sha256" source)))sources;
  ignore(texts 128(Json.Array(List.map(get "id")sources)));
  require(texts 128(get "assumptions" value)<>[])"Conditional authority needs explicit assumptions."
let model value=
  exact["schema_version";"identity";"body"]value;schema "biocompiler.policy_controlled_activity_model.v0.1" value;
  let identity=P.of_json(get "identity" value)in require(P.kind identity=P.Model)"Mechanism identity must be a model.";
  let body=get "body" value in
  exact["operation";"readout";"controller";"products";"components";"ports";"delays";"initial_activity";"clock";"assumptions"]body;
  List.iter(fun key->definition(get key body))["operation";"readout";"controller"];
  List.iter definition(pair(get "products" body));ref_ "Clock"(get "clock" body);delays(get "delays" body);
  require(get "initial_activity" body=str "background")"Initial activity must be background.";
  require(texts 128(get "assumptions" body)<>[])"Mechanism needs explicit conditional premises.";
  let components=pair(get "components" body)in
  List.iter(fun item->exact["id";"member_id";"product_definition";"localization";"model"]item;
    ignore(text(get "id" item));ignore(text(get "member_id" item));
    List.iter(fun key->definition(get key item))["product_definition";"localization";"model"])components;
  ignore(texts 2(Json.Array(List.map(get "id")components)));
  let ports=list 5(get "ports" body)in require(List.length ports=5)"Model requires its complete five-port interface.";
  List.iteri(fun index item->exact["id";"direction";"signal";"scope";"reference"]item;
    let id,direction,signal,scope,kind=List.nth[
      "antigen","input","physical_antigen","encounter_generation","Observation";
      "controller","input","physical_controller","executor","Observation";
      "component-a","input","component_available","executor","Parameter";
      "component-b","input","component_available","executor","Parameter";
      "activity","output","activity_band","executor","ControlledActivity"]index in
    List.iter(fun(key,expected)->require(get key item=str expected)"Unsupported port meaning or ordering.")
      ["id",id;"direction",direction;"signal",signal;"scope",scope];ref_ kind(get "reference" item))ports
let assembly value=exact["schema_version";"policy";"member_order";"product_bindings";"helper_members"]value;
  schema "biocompiler.policy_controlled_composition_assembly.v0.1" value;
  require(get "policy" value=str "supplied_template_only" && get "helper_members" value=Json.Array[])"Unaccounted assembly policy/helper.";
  require(List.length(texts 2(get "member_order" value))=2)"Assembly requires two distinct ordered members.";
  List.iter(binding true)(pair(get "product_bindings" value))
let context value=exact["schema_version";"executor_identity";"slot";"deployment";"co_delivery";"localizations";"availability";"controller";"empirical_assertions"]value;
  schema "biocompiler.policy_controlled_composition_context.v0.1" value;
  ignore(text(get "executor_identity" value));ignore(text(get "slot" value));
  let delivery=get "co_delivery" value in exact["mode";"members";"assumptions"]delivery;
  require(get "mode" delivery=str "same_recipient")"Both members require the same recipient.";
  require(List.length(texts 2(get "members" delivery))=2 && texts 128(get "assumptions" delivery)<>[])"Co-delivery needs complete members and premises.";
  List.iter(fun item->exact["member_id";"rna_compartment";"product_compartment";"definition"]item;
    ignore(text(get "member_id" item));definition(get "definition" item);
    require(get "rna_compartment" item=str "cytoplasm" && get "product_compartment" item=str "cell_surface")"Unsupported declared localization.")
    (pair(get "localizations" value));
  List.iter(fun item->exact["member_id";"rna";"product";"scope"]item;ignore(text(get "member_id" item));
    require(get "rna" item=str "domain" && get "product" item=str "domain" && get "scope" item=str "executor")"Availability must remain separate domain factors.")
    (pair(get "availability" value));controller(get "controller" value);
  let assertions=list 128(get "empirical_assertions" value)in
  List.iter(fun item->exact["id";"claim";"status";"source_ids"]item;ignore(text(get "id" item));ignore(text(get "claim" item));
    require(get "status" item=str "unassessed")"RC3 cannot assert empirical acceptance.";ignore(texts 128(get "source_ids" item)))assertions;
  ignore(texts 128(Json.Array(List.map(get "id")assertions)))
let resources value=let keys=["max_member_rna_nt";"max_total_rna_nt";"controller_records";"evidence_records";"timer_cells";"state_bits"]in
  exact("schema_version"::keys)value;schema resource_profile value;
  List.iter(fun key->ignore(integer(if key="max_total_rna_nt"then 2000000 else 1000000)(get key value)))keys;
  List.iter(fun(key,minimum)->require(Json.integer(get key value)>=Z.of_int minimum)"Insufficient declared controlled capacity.")
    ["controller_records",1;"evidence_records",2;"timer_cells",3;"state_bits",4]
let of_json ?(charge=fun _->()) (original:Json.t) : t=
  let work=ref 0 and ceiling=ref 1000000000 in
  let spend amount=require(amount>=0 && amount<= !ceiling- !work)"Logical work exceeds the supplied budget.";charge amount;work:= !work+amount in
  let bytes=Old.preflight ~charge:spend original in
  exact["schema_version";"profile";"source_authority";"mechanism_model";"operating_domain";"material_authority";"catalog_binding";"assembly";"context";"resources";"budgets"]original;
  schema schema_version original;require(get "profile" original=str profile)"Unsupported controlled request profile.";
  let budget=get "budgets" original in exact["profile";"max_work";"max_report_bytes";"max_report_nodes"]budget;
  require(get "profile" budget=str resource_profile)"Wrong controlled budget profile.";
  let budget:budgets={max_work=integer 1000000000(get "max_work" budget);max_report_bytes=integer 8323072(get "max_report_bytes" budget);
    max_report_nodes=integer 249968(get "max_report_nodes" budget)}in
  ceiling:=budget.max_work;require(!work<= !ceiling)"Original preflight exceeds its supplied work budget.";
  let decode decoder value=ignore(Old.preflight ~charge:spend value);decoder value in
  let same first second=let encode value=let size=Old.preflight ~charge:spend value in spend size;Canonical.encode value in
    encode first=encode second in
  let source=get "source_authority" original in exact["schema_version";"document";"control_contract";"project_context"]source;
  schema "biocompiler.policy_controlled_composition_source_authority.v0.1" source;
  let document_value=decode D.of_controlled_json(get "document" source)in
  decode contract(get "control_contract" source);decode project(get "project_context" source);
  decode model(get "mechanism_model" original);decode assembly(get "assembly" original);decode context(get "context" original);
  decode resources(get "resources" original);
  let binding=get "catalog_binding" original in exact["entry";"model_identity";"component_ids"]binding;
  ignore(P.of_json(get "model_identity" binding));require(List.length(texts 2(get "component_ids" binding))=2)"Missing component inventory.";
  let document_raw=D.controlled_to_json document_value in
  let entries=list 1(get "implementations"(get "implementations" document_raw))in
  require(List.length entries=1 && same(List.hd entries)(get "entry" binding))"Catalog binding must retain the complete sole original entry.";
  require(same(get "deployment"(get "context" original))(get "deployment" document_raw))"Context must retain the complete original deployment.";
  let domain_value=Domain.of_json ~charge:spend(get "operating_domain" original)in
  let material_value=decode Material.of_json(get "material_authority" original)in
  require(List.length(Material.members material_value)=2)"Controlled request requires exactly two full RNA members.";
  spend bytes;let encoded=Canonical.encode_bounded ~max_bytes:M.max_json_bytes original in
  require(String.length encoded=bytes)"Canonical byte accounting disagrees.";
  spend bytes;let identity=Canonical.sha256 encoded in
  require(!work<=budget.max_work)"Request decode exceeds its supplied work budget.";
  {original;identity;work= !work;document_value;domain_value;material_value;budget}
let to_json (value:t)=value.original
let raw=to_json
let fingerprint (value:t)=value.identity
let decoding_work (value:t)=value.work
let document (value:t)=value.document_value
let domain (value:t)=value.domain_value
let material (value:t)=value.material_value
let budgets (value:t)=value.budget

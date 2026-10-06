open Bioc_wire
module M = Molecular_record
module H = Molecule_chemistry
module R = Molecular_recoding
module P = Pinned_identity
let schema_version="biocompiler.policy_mrna_structure_authority.v0.1"
let profile="biocompiler.policy_mrna_completeness.v0.1"
let max_members=16
let str value=Json.String value
let obj values=Json.Object values
let arr values=Json.Array values
let get name value=Json.field name(Json.object_fields value)
let exact names value=Json.exact_fields names(Json.object_fields value)
let require condition message=Diagnostic.require condition "invalid_policy_mrna_structure" message
let unique values=require(List.length values=List.length(List.sort_uniq String.compare values))"Duplicate authority identity."
let product_content_json sequence=obj["schema_version",str "biocompiler.policy_mrna_product_content.v0.1";
  "alphabet",str "protein";"sequence_extent",str "complete";"sequence",str sequence]
type regions={utr5:string;cds:string;utr3:string;poly_a:string}
type product={identity:P.t;sequence:string;translation_policy:R.Translation_policy.t;provenance:M.Provenance.t}
type member={id:string;regions:regions;product:product;chemistry:H.t}
type t={template:Payload_template.t;member_order:string list;members:member list}
let product_json (value:product)=obj["identity",P.to_json value.identity;"sequence",str value.sequence;
  "translation_policy",R.Translation_policy.to_json value.translation_policy;"provenance",M.Provenance.to_json value.provenance]
let member_json (value:member)=obj["id",str value.id;
  "regions",obj["utr5",str value.regions.utr5;"cds",str value.regions.cds;"utr3",str value.regions.utr3;"poly_a",str value.regions.poly_a];
  "product",product_json value.product;"chemistry",H.to_json value.chemistry]
let to_json (value:t)=obj["schema_version",str schema_version;"profile",str profile;
  "template",Payload_template.to_json value.template;"member_order",arr(List.map str value.member_order);
  "members",arr(List.map member_json value.members)]
let of_json raw=
  M.check_resources raw;
  exact["schema_version";"profile";"template";"member_order";"members"]raw;
  require(get "schema_version" raw=str schema_version && get "profile" raw=str profile)"Unknown mRNA structural authority profile.";
  let template=Payload_template.of_json(get "template" raw)in
  let member_order=M.array ~maximum:max_members(get "member_order" raw)|>List.map M.text in
  require(member_order<>[])"Original member inventory is empty.";unique member_order;
  ignore(Construction_content.authority_json ~template ~member_order);
  let members=M.array ~maximum:max_members(get "members" raw)|>List.map(fun value->
    exact["id";"regions";"product";"chemistry"]value;
    let fields=get "regions" value and product=get "product" value in
    exact["utr5";"cds";"utr3";"poly_a"]fields;
    let regions={utr5=M.text(get "utr5" fields);cds=M.text(get "cds" fields);
      utr3=M.text(get "utr3" fields);poly_a=M.text(get "poly_a" fields)}in
    unique[regions.utr5;regions.cds;regions.utr3;regions.poly_a];
    exact["identity";"sequence";"translation_policy";"provenance"]product;
    let sequence=M.text ~maximum:M.max_residues(get "sequence" product)in
    require(String.for_all(String.contains "ACDEFGHIKLMNPQRSTVWY")sequence)"Expected complete product requires canonical amino-acid spelling without a stop symbol.";
    let product={identity=P.of_json(get "identity" product);sequence;
      translation_policy=R.Translation_policy.of_json(get "translation_policy" product);
      provenance=M.Provenance.of_json(get "provenance" product)}in
    {id=M.text(get "id" value);regions;product;chemistry=H.of_json(get "chemistry" value)})in
  require(List.map(fun(member:member)->member.id)members=member_order)"Per-member expectations must preserve the complete original delivered order.";
  let value={template;member_order;members}in M.check_resources(to_json value);value
let fingerprint value=Canonical.fingerprint(to_json value)
let template(value:t)=value.template
let member_order(value:t)=value.member_order
let members(value:t)=value.members

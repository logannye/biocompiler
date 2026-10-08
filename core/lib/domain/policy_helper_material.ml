open Bioc_wire
module M = Molecular_record
module P = Pinned_identity
module PM = Policy_mrna_structure
module C = Policy_material_contract
module N = Molecule
module G = Molecule_coordinates
module H = Molecule_chemistry
let schema_version="biocompiler.policy_helper_material.v0.1"
let profile="biocompiler.policy_grounded_helper_rna.v0.1"
let str value=Json.String value
let obj values=Json.Object values
let get key value=Json.field key(Json.object_fields value)
let exact keys value=Json.exact_fields keys(Json.object_fields value)
let require condition message=Diagnostic.require condition "policy_helper_material" message
type t={identity_value:P.t;root_value:Construction.Root_source.t;regions_value:PM.regions;
  product_value:PM.product;chemistry_value:H.t;capability_value:C.provider_ref}
let body_to_json value=obj["root",Construction.Root_source.to_json value.root_value;
  "regions",PM.regions_to_json value.regions_value;"product",PM.product_to_json value.product_value;
  "chemistry",H.to_json value.chemistry_value;"capability",C.provider_ref_to_json value.capability_value;
  "prerequisites",Json.Array []]
let to_json value=obj["schema_version",str schema_version;"profile",str profile;
  "identity",P.to_json value.identity_value;"body",body_to_json value]
let preflight raw=
  M.check_resources raw;
  let rec walk=function
    |Json.Float _->require false "Raw floats cannot enter a helper material contract."
    |Json.Array values->List.iter walk values
    |Json.Object fields->List.iter(fun(_,value)->walk value)fields
    |_->()in walk raw
let of_json raw=
  preflight raw;
  exact["schema_version";"profile";"identity";"body"]raw;
  require(get "schema_version" raw=str schema_version && get "profile" raw=str profile)
    "Unsupported grounded helper material profile.";
  let identity_value=P.of_json(get "identity" raw)and body=get "body" raw in
  exact["root";"regions";"product";"chemistry";"capability";"prerequisites"]body;
  require(P.kind identity_value=P.Model && P.content_fingerprint identity_value=Canonical.fingerprint body)
    "Helper material identity must pin its complete supplied body.";
  require(get "prerequisites" body=Json.Array [])
    "Grounded helper material does not admit hidden or circular prerequisites.";
  let root_value=Construction.Root_source.of_json(get "root" body)in
  let molecule=Construction.Root_source.molecule root_value in
  let space=N.space molecule in
  require(N.form molecule=N.Primary_rna && N.sequence_extent molecule=H.Complete &&
    G.Space.alphabet space=G.Rna && G.Space.topology space=G.Linear && G.Space.axis space=G.Five_prime_to_three_prime)
    "Helper material requires complete linear five-prime-to-three-prime primary RNA.";
  require(List.length(N.features molecule)=4)"Helper RNA must supply exactly four original region features.";
  let value={identity_value;root_value;regions_value=PM.regions_of_json(get "regions" body);
    product_value=PM.product_of_json(get "product" body);chemistry_value=H.of_json(get "chemistry" body);
    capability_value=C.provider_ref_of_json(get "capability" body)}in
  require(Json.equal raw(to_json value))"Helper material must retain its complete typed body without normalization.";
  preflight(to_json value);value
let fingerprint value=Canonical.fingerprint(to_json value)
let identity value=value.identity_value
let root value=value.root_value
let regions value=value.regions_value
let product value=value.product_value
let chemistry value=value.chemistry_value
let capability value=value.capability_value
let prerequisites _=[]

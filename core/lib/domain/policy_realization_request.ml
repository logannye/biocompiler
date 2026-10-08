open Bioc_wire
module D = Policy_document
module O = Policy_operational
module F = Policy_operating_domain
module I = Policy_implementation
module P = Pinned_identity

let schema_version = "biocompiler.policy_realization_request.v0.1"
let profile = "biocompiler.policy_realization_inputs.v0.1"
let prerequisite_schema_version = "biocompiler.policy_realization_request.v0.2"
let prerequisite_profile = "biocompiler.policy_prerequisite_realization_inputs.v0.1"
let two_observation_schema_version = "biocompiler.policy_realization_request.v0.3"
let two_observation_profile = "biocompiler.policy_two_observation_prerequisite_inputs.v0.1"
let resource_profile = "biocompiler.policy_realization_inputs.resources.v0.1"
type family = Legacy | Prerequisites | Two_observation
let family_schema = function Legacy -> schema_version | Prerequisites -> prerequisite_schema_version
  | Two_observation -> two_observation_schema_version
let family_profile = function Legacy -> profile | Prerequisites -> prerequisite_profile
  | Two_observation -> two_observation_profile
type budgets = { max_prefixes:int; max_transitions:int; max_work:int; max_trace_items:int }
type catalog_binding = {
  entry_id:string; entry_version:string; entry_digest:string;
  operation:Json.t; realization:Json.t; models:P.t list;
}
type t = {
  raw:Json.t; identity:string; family:family; document_value:D.t; definitions_value:O.descriptor_bundle;
  domain_value:F.t; library_value:I.library; binding_values:catalog_binding list;
  bindings_identity:string; budget_values:budgets;
}
let get key value = Json.field key (Json.object_fields value)
let text key value = Json.string (get key value)
let items key value = Json.array (get key value)
let require ?path condition message = Diagnostic.require ?path condition
    "policy_realization_request" message
let exact keys value = Json.exact_fields keys (Json.object_fields value)
let name value =
  let name=Json.name value in
  require (String.length name<=256) "Realization input identity exceeds its bound.";
  name
let digest value =
  let value=Json.string value in
  require (String.length value=64 && String.for_all (function '0'..'9'|'a'..'f'->true|_->false) value)
    "Realization input requires a lowercase SHA-256 digest.";
  value
let unique label values =
  require (List.length values=List.length(List.sort_uniq String.compare values))
    ("Duplicate realization " ^ label ^ " identity.")
let definition_ref value =
  exact ["$type";"id";"version";"digest"] value;
  require (text "$type" value="DefinitionRef") "Catalog bridge requires an exact DefinitionRef.";
  ignore(name(get "id" value));ignore(name(get "version" value));ignore(digest(get "digest" value));
  value
let integer maximum value =
  let value=Json.integer value in
  require (Z.sign value>0 && Z.compare value (Z.of_int maximum)<=0)
    "Realization exploration budget must be a positive bounded integer.";
  Z.to_int value
let decode ~family raw =
  (* The existing strict measurement bounds shared/cyclic list occurrences,
     duplicate keys, depth, scalar sizes and floats before any typed traversal.
     Its metadata-excluding digest is discarded; authority uses the full hash. *)
  ignore(D.document_digest raw);
  exact ["schema_version";"profile";"document";"definitions";"operating_domain";
    "implementation_library";"catalog_bindings";"budgets"] raw;
  require (text "schema_version" raw=family_schema family && text "profile" raw=family_profile family)
    "Unsupported realization input schema/profile.";
  let document_value=D.of_json ~path:"/document" (get "document" raw) in
  require ~path:"/document" (D.kind document_value=D.Request)
    "Realization inputs require the complete original BuildRequest.";
  let definitions_value=O.descriptors_of_json(get "definitions" raw)
  and domain_value=F.of_json(get "operating_domain" raw)
  and library_value=I.library_of_json(get "implementation_library" raw) in
  let raw_bindings=items "catalog_bindings" raw in
  require (List.length raw_bindings<=128) "Realization catalog bridge exceeds its entry bound.";
  let binding_values=List.map (fun value ->
    exact ["entry_id";"entry_version";"entry_digest";"operation";"realization";"models"] value;
    let pins=items "models" value in
    require (pins<>[] && List.length pins<=64) "A catalog bridge requires a nonempty bounded model set.";
    let models=List.map(fun pin->P.of_json pin)pins in
    List.iter (fun pin -> require(P.kind pin=P.Model) "Catalog bridge pins must identify primitive models.") models;
    unique "model pin" (List.map P.fingerprint models);
    {entry_id=name(get "entry_id" value);entry_version=name(get "entry_version" value);
     entry_digest=digest(get "entry_digest" value);operation=definition_ref(get "operation" value);
     realization=definition_ref(get "realization" value);models}) raw_bindings in
  unique "catalog bridge" (List.map (fun binding -> binding.entry_id) binding_values);
  let budget=get "budgets" raw in
  exact ["max_prefixes";"max_transitions";"max_work";"max_trace_items"] budget;
  let budget_values={max_prefixes=integer 1_000_000(get "max_prefixes" budget);
    max_transitions=integer 10_000_000(get "max_transitions" budget);
    max_work=integer 100_000_000(get "max_work" budget);
    max_trace_items=integer 1_000_000(get "max_trace_items" budget)} in
  {raw;identity=Canonical.fingerprint raw;family;document_value;definitions_value;domain_value;library_value;
   binding_values;bindings_identity=Canonical.fingerprint(get "catalog_bindings" raw);budget_values}
let of_json raw = decode ~family:Legacy raw
let of_prerequisite_json raw = decode ~family:Prerequisites raw
let of_two_observation_json raw = decode ~family:Two_observation raw
let requires_prerequisite_closure value = value.family<>Legacy
let is_two_observation value = value.family=Two_observation
let request_profile value = family_profile value.family
let to_json value = value.raw
let fingerprint value = value.identity
let document value = value.document_value
let definitions value = value.definitions_value
let operating_domain value = value.domain_value
let implementation_library value = value.library_value
let catalog_bindings value = value.binding_values
let catalog_bindings_digest value = value.bindings_identity
let budgets value = value.budget_values

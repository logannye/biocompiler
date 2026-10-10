open Bioc_wire
module Bundle = Bioc_domain.Policy_module_bundle
module Document = Bioc_domain.Policy_document
module Link = Bioc_checker.Policy_module_linking_check
module Material = Policy_component_material_service
module Input = Bioc_domain.Policy_material_request
module W = Bioc_checker.Work_budget
let str value=Json.String value
let obj fields=Json.Object fields
let get key value=Json.field key(Json.object_fields value)
let schema_version="biocompiler.core.policy_module_linking.v1"
let implementation="biocompiler.ocaml.policy_module_linking.v0.1"
let validation_scope="policy-exact-module-elaboration-v0.1"
let material_schema_version="biocompiler.core.policy_module_material.v1"
let material_implementation="biocompiler.ocaml.policy_module_material.v0.1"
let material_validation_scope="policy-module-component-mrna-v0.1"
let max_result_bytes=8388608
let max_result_nodes=250000
let linking_operations=["check-policy-module-linking";"replay-policy-module-linking"]
let material_operations=["check-policy-module-material";"replay-policy-module-material";"export-policy-module-material"]
let operations=linking_operations@material_operations
let make_profile operations schema implementation scope artifact=obj[
  "operations",Json.Array(List.map str operations);"schema_version",str schema;
  "implementation",str implementation;"validation_scope",str scope;
  "bundle_schema",str "biocompiler.policy_module_bundle.v0.1";
  "max_result_bytes",Json.int max_result_bytes;"max_result_nodes",Json.int max_result_nodes;
  "artifact",str artifact;"empirical",str "unassessed"]
let profile=make_profile linking_operations schema_version implementation validation_scope "none"
let material_profile=make_profile material_operations material_schema_version material_implementation
  material_validation_scope "fresh_exact_mrna_with_module_lineage"
let producer_profile=make_profile ["compile-policy-module-material"] material_schema_version material_implementation
  material_validation_scope "fresh_exact_mrna_with_module_lineage"
let budget ()=W.create ~profile:validation_scope ~error_code:"policy_module_service_limit" ~maximum:134217728 ()
let preflight budget raw=Input.preflight ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes
  ~max_depth:128 ~charge:(W.charge budget) raw
let validate_input raw=ignore(preflight (budget ()) raw)
let hash budget raw=
  let length=preflight budget raw in
  W.charge budget length;
  let bytes=Canonical.encode_bounded ~max_bytes:max_result_bytes raw in
  Diagnostic.require(String.length bytes=length)"policy_module_service_accounting"
    "Complete module service preflight differs from canonical bytes.";
  W.charge budget length;Canonical.sha256 bytes
let publish budget value=
  ignore(preflight budget value);
  let output=W.create_output ~profile:validation_scope ~error_code:"policy_module_service_publication_limit"
    ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes ()in
  W.reserve_json output(obj["result",value]);
  Diagnostic.require(not(W.exhausted budget))"policy_module_service_limit""Module service work was exhausted.";
  Material.validate_publication value
let link modules program=
  Link.check ~bundle:(Bundle.of_json modules) ~program:(Document.of_json ~path:"/program" program)
let check_linkage ~modules ~request=
  let work=budget ()in
  ignore(preflight work(obj["modules",modules;"request",request]));
  let document=Document.of_json ~path:"/request/implementation_request/document"
    (get "document"(get "implementation_request" request))in
  link modules(Document.program document)
let linked_export budget modules linkage material=
  let original=get "artifact" material in
  Diagnostic.require(original<>Json.Null)"policy_module_material_export_not_accepted"
    "Fresh complete material checking withheld module-aware export.";
  let manifest=obj[
    "schema_version",str "biocompiler.policy_module_mrna_manifest.v0.1";
    "modules",modules;"linkage",linkage;
    "material_manifest",get "manifest" original;
    "material_manifest_sha256",get "manifest_sha256" original;
    "fasta_sha256",get "fasta_sha256" original;
    "claim_scope",str "exact_module_elaboration_and_bounded_conditional_component_material";
    "empirical",str "unassessed"]in
  let manifest_sha=hash budget manifest in
  obj["schema_version",str "biocompiler.policy_module_mrna_export.v0.1";
    "fasta",get "fasta" original;"fasta_sha256",get "fasta_sha256" original;
    "manifest",manifest;"manifest_sha256",str manifest_sha]
let check ~export ~modules ~request ~candidate ~limits=
  let work=budget ()in
  let invocation=obj["modules",modules;"request",request;"candidate",candidate;"limits",limits]in
  ignore(preflight work invocation);
  let linked=check_linkage ~modules ~request in
  (* The child operation is always freshly evaluated with the complete original
     request and candidate. No imported report, linkage JSON or producer token
     can stand in for the child's opaque material acceptance. *)
  let material=try Material.check ~export ~request ~candidate ~limits with
    | Diagnostic.Error diagnostic->raise(Diagnostic.Error(Link.remap_diagnostic linked diagnostic))in
  let linkage=Link.evidence linked in
  let artifact=if export then linked_export work modules linkage material else Json.Null in
  let result=obj["schema_version",str material_schema_version;"implementation",str material_implementation;
    "validation_scope",str material_validation_scope;"modules",modules;"linkage",linkage;
    "material",material;"invocation_fingerprint",str(hash work invocation);"artifact",artifact]in
  publish work result;result
let handle ~operation payload=
  Diagnostic.require(List.mem operation operations)"unsupported_operation"
    "Module service only checks, replays or freshly exports complete original authority.";
  let work=budget ()in
  ignore(preflight work payload);
  let fields=Json.object_fields ~path:"/payload" payload in
  let replay=operation="replay-policy-module-linking" || operation="replay-policy-module-material"in
  let standalone=List.mem operation linking_operations in
  let expected=if standalone then["modules";"program"]else["modules";"request";"candidate";"limits"]in
  Json.exact_fields ~path:"/payload"(expected@(if replay then["report"]else[]))fields;
  let modules=Json.field "modules" fields in
  let result=if not standalone then check ~export:(operation="export-policy-module-material") ~modules
      ~request:(Json.field "request" fields) ~candidate:(Json.field "candidate" fields) ~limits:(Json.field "limits" fields)
    else
      let program=Json.field "program" fields in
      let linked=link modules program in
      obj["schema_version",str schema_version;"implementation",str implementation;
        "validation_scope",str validation_scope;"modules",modules;"program",program;
        "linkage",Link.evidence linked;
        "invocation_fingerprint",str(hash work(obj["modules",modules;"program",program]))]in
  if replay then(
    ignore(preflight work result);
    Diagnostic.require(Json.equal result(Json.field "report" fields))"policy_module_replay"
      "Saved complete module wrapper differs from fresh original-authority checking.");
  publish work result;result

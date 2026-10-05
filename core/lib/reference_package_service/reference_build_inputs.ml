open Bioc_wire
open Bioc_domain
module B=Bioc_artifact.Archive_budget
module I=Bioc_reference_input.Reference_inputs
module C=Verification_exploration.Codec
module G=Bioc_compiler.Reference_construct_producer
type t={owner:B.t;request_value:Reference_construct.Request.t;reference_value:Reference_manifest.t;registry_value:Component_registry.t}
let prepare budget ~alphabet snapshot=
  B.charge budget 1;
  let reference_pin=I.reference_pin budget alphabet in
  I.require_owner budget snapshot;
  let reference=I.manifest snapshot and limits=B.limits budget in
  let codec=C.make_limits ~max_bytes:(min Limits.max_request_bytes limits.max_member_bytes)
    ~max_nodes:(min Limits.max_json_nodes limits.max_json_nodes) ~charge:(B.charge budget)() in
  let size=C.measure ~limits:codec(Reference_manifest.to_json reference) in
  (* The fixed constructor creates one adapted record, one lock/instance and
     one request, copying only bounded manifest-owned declarations. Prepay the
     codec/constructor amplification before any of those allocations. *)
  B.product budget(size.bytes+size.nodes+1)512;
  B.reserve budget(256*size.bytes+1024*size.nodes+65_536);
  let selection=Reference_components.Selection.make ~limits:codec ~manifest:I.manifest_pin ~reference:reference_pin() in
  let component=Reference_components.adapt_reference_component ~limits:codec reference selection in
  let registry=Component_registry.make ~id:"reviewed-cds" ~version:"1" ~components:[component] in
  let lock=Component_registry.lock registry["fap_cds",component] in
  let target=Build_request.Target.of_json(Json.Object[
    "schema_version",Json.String "biocompiler.target.v0.1";
    "context_id",Json.String "reference";"context_version",Json.String "1";
    "payload_format",Json.String(Reference_manifest.alphabet_name alphabet);
    "capabilities",Json.Array[];"compartments",Json.Array[Json.String "abstract"];"resources",Json.Object[]]) in
  let requirements=["preserve_selected_cds"] in
  let instance=Composition.Instance.make ~id:"fap_cds" ~component:(List.hd(Component_registry.Lock.components lock))
    ~required_domain:(Component_contract.Operating_domain.make[]) ~requirement_ids:requirements() in
  let composition=Composition.make ~target ~registry_lock:lock ~instances:[instance] ~requirement_ids:requirements() in
  let request=G.prepare ~parent:(B.work budget) ~manifest:reference ~selection ~composition ~registry() in
  {owner=budget;request_value=request;reference_value=reference;registry_value=registry}
let request value=value.request_value
let reference value=value.reference_value
let registry value=value.registry_value

let require_owner budget value=
  B.guard budget;Diagnostic.require(value.owner==budget) "reference_input_owner"
    "Prepared reference inputs belong to another resource lifetime."
let supplied budget ~request ~reference ~registry=
  B.guard budget;
  let limits=B.limits budget in
  let codec=C.make_limits ~max_bytes:(min Limits.max_request_bytes limits.max_member_bytes)
    ~max_nodes:(min Limits.max_json_nodes limits.max_json_nodes) ~charge:(B.charge budget)() in
  List.iter(fun raw->let size=C.measure ~limits:codec raw in
    B.reserve budget(size.bytes+128*size.nodes+256))
    [Reference_construct.Request.to_json request;Reference_manifest.to_json reference;Component_registry.to_json registry];
  {owner=budget;request_value=request;reference_value=reference;registry_value=registry}

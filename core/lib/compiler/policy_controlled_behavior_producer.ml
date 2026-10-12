open Bioc_wire
module R = Bioc_domain.Policy_controlled_behavior_request
module Original = Bioc_domain.Policy_controlled_composition_request
module C = Bioc_domain.Policy_controlled_behavior_candidate
module I = Bioc_domain.Policy_controlled_activity_implementation
let implementation_version = "biocompiler.ocaml.policy_controlled_behavior_producer.v0.1"
let get key raw = Json.field key (Json.object_fields raw)
let str value = Json.String value
let record fields = Json.Object (List.map (fun (key,value) -> key,str value) fields)
let construct_candidate ~charge (request:R.t) : C.t =
  (* A single enclosing work owner charges construction and all nested codecs.
     There is no private behavior-checked token and no reference evaluation. *)
  charge 1;
  let original = Original.raw (R.original request) in
  let source = get "source_authority" original in
  let model = get "mechanism_model" original in
  let delays = get "delays" (get "body" model) in
  let primitives = Json.Array [
    record ["id","encounter";"op","encounter_live"];
    record ["id","antigen";"op","physical_input";"key","antigen"];
    record ["id","controller";"op","physical_input";"key","controller"];
    record ["id","protein-a";"op","physical_input";"key","protein_a"];
    record ["id","protein-b";"op","physical_input";"key","protein_b"];
    record ["id","gate";"op","all"];
    Json.Object ["id",str "activity";"op",str "delayed_reversible";
      "onset_ticks",get "onset_ticks" delays;"cessation_ticks",get "cessation_ticks" delays;
      "reactivation_ticks",get "reactivation_ticks" delays;"initial_band",str "background";
      "timer_scope",str "executor";"activation_scope",str "encounter_generation"];
    record ["id","readout";"op","activity_band"]] in
  let wires = Json.Array (List.map (fun (source,target,input) ->
    record ["from",source;"to",target;"input",input]) [
    "encounter","gate","live";"antigen","gate","antigen";
    "controller","gate","controller";"protein-a","gate","protein_a";
    "protein-b","gate","protein_b";"gate","activity","enabled";
    "activity","readout","band"]) in
  charge 40;
  let implementation = Json.Object [
    "schema_version",str I.schema_version;"mechanism_model",model;
    "control_contract",get "control_contract" source;
    "semantics",get "semantics" (get "program" (get "document" source));
    "catalog_binding",get "catalog_binding" original;"assembly",get "assembly" original;
    "context",get "context" original;"resources",get "resources" original;
    "primitives",primitives;"wires",wires] in
  C.of_json ~charge (Json.Object ["schema_version",str C.schema_version;
    "request_fingerprint",str (R.fingerprint request);"implementation",implementation])

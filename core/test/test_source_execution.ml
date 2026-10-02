open Bioc_wire
open Bioc_domain
module P = Bioc_compiler.Source_execution
module E = Source_execution_manifest
let require condition message = if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let field key raw = Json.field key (Json.object_fields raw)
let replace key value raw = obj ((key,value) :: List.remove_assoc key (Json.object_fields raw))
let dtype=Json.parse {|{"kind":"scalar","name":"Level","dimensions":{},"arguments":[]}|}
let scalar value=obj ["kind",str "scalar";"value",value;"unit",str "1";"canonical_value",value;"type",dtype]
let location=Json.parse {|{"file":"literal/source.py","line":7,"function":"author"}|}
let node=obj ["id",str "value";"kind",str "literal";"inputs",arr [];"attributes",obj ["value",scalar (Json.Float (-0.0))];
  "data_type",dtype;"role",Json.Null;"source",location]
let intent=obj ["schema_version",str Intent.schema_version;"name",str "literal source";"nodes",arr [node];"roots",arr [str "value"]]
let provenance=Json.parse {|{"schema_version":"biocompiler.elaboration_provenance.v0.1","source_identities":{},"dependency_identities":{},"external_inputs":{},"locations":{},"recorded_at":null}|}
let original=obj ["schema_version",str Build_request.schema_version;"intent",intent;"explicit_overrides",obj [];"resolved_defaults",obj [];"resolved_bindings",obj [];
  "target",Json.Null;"artifact_scope",str "abstract_behavior";"behavior_profile",str "biocompiler.behavior.v0.1";
  "implementation_constraints",obj [];"preferences",obj [];"parameter_metadata",obj [];"provenance",provenance]
let () =
  require (Array.length Sys.argv=1) "Source literal suite accepts no arguments; broad corpus runs in test_architecture_producer";
  let source=Human_request.of_json original in
  let result=P.derive source in
  let behavior=obj ["schema_version",str "biocompiler.behavior.v0.1";"name",str "literal source";
    "nodes",arr [node |> replace "contact_bound" (Json.Bool false) |> replace "requirement_ids" (arr [])];
    "roots",arr [str "value"];"source_fingerprint",str (Intent.fingerprint (Intent.of_json intent));
    "requirements",arr [];"source_links",obj ["value",arr [str "value"]];"policies",Behavior.execution_policies Behavior.V0_1;"parameter_bindings",obj []] in
  let semantics=obj (List.remove_assoc "source" (Json.object_fields node)) in
  let expected=obj ["schema_version",str E.schema_version;"claim_scope",str E.claim_scope;"source",Human_request.to_json source;
    "behavior",behavior;"roles",arr [];"outputs",arr [];
    "ledger",arr [obj ["id",str "source:value";"kind",str "literal";"source_node_ids",arr [str "value"];"semantics",semantics];
      obj ["id",str "source:complete_authority";"kind",str "source_authority";"source_node_ids",arr [str "value"];"semantics",Human_request.to_json source]];
    "role_nodes",obj [];"states",arr [];"channels",arr [];"diagnostics",arr []] in
  require (Json.equal (E.to_json result) expected && E.complete result) "Complete source manifest differs from independent signed-zero literal";
  let report=Bioc_checker.Source_check.check ~expected_source:source ~manifest:result in
  require (report.failures=[] && report.unresolved=[]) "Independent checker rejected produced literal";
  let unknown=replace "kind" (str "future.operation") node |> replace "attributes" (obj []) in
  let unknown_source=replace "intent" (replace "nodes" (arr [unknown]) intent) original |> Human_request.of_json in
  let unsupported=P.derive unknown_source in
  require (not (E.complete unsupported) && E.behavior unsupported=None && List.length (E.diagnostics unsupported)=1) "Unsupported source silently became executable";
  let diagnostic=List.hd (E.diagnostics unsupported) in
  require (E.Diagnostic_record.code diagnostic="source_execution_profile_unsupported" &&
    E.Diagnostic_record.source_node_ids diagnostic=["value"] &&
    E.Diagnostic_record.message diagnostic="Operation 'future.operation' needs an additional execution profile or semantic refinement. [value] at literal/source.py:7") "Legacy unsupported source spelling or coordinates changed";
  let constrained=original |> replace "implementation_constraints" (obj ["z",Json.int 1;"a",Json.Bool true]) |> replace "preferences" (obj ["preference",str "explicit"]) |> Human_request.of_json |> P.derive in
  require (List.map E.Diagnostic_record.code (E.diagnostics constrained)=["uninterpreted_implementation_constraints";"uninterpreted_source_preferences"] &&
    E.Diagnostic_record.message (List.hd (E.diagnostics constrained))="Retained implementation constraints require interpretation: a, z") "Constraint or preference authority lost or reordered";
  print_endline "source execution literals: full authority, signed zero, exact unsupported location, constraints and preferences passed"

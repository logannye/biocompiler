open Bioc_wire
module R = Policy_realization_request
module X = Policy_component_context
module C = Policy_material_contract
module V = Policy_material_context
module D = Policy_document
module M = Molecular_record
module P = Pinned_identity
module Names = Map.Make (String)
let schema_version = "biocompiler.policy_provider_dependency_graph.v0.1"
let max_dependencies = 128
let max_roots = 1024
let max_nodes = 1024
let max_edges = 1024
let str value = Json.String value
let obj values = Json.Object values
let arr encode values = Json.Array (List.map encode values)
let get key raw = Json.field key (Json.object_fields raw)
let require condition message = Diagnostic.require condition "policy_provider_prerequisites" message
let bounded label maximum values =
  ignore (M.bounded_length ~maximum values);
  require (List.length values<=maximum) ("Provider prerequisite "^label^" exceeds its closed bound.")
let rec charge_json charge = function
  | Json.String value -> charge (1+String.length value)
  | Json.Int value -> charge (1+String.length (Z.to_string value))
  | Json.Float _ -> require false "Raw floats cannot enter provider prerequisites."
  | Json.Array values -> charge 1; List.iter (fun value -> charge 1; charge_json charge value) values
  | Json.Object fields -> charge 1; List.iter (fun (key,value) -> charge (1+String.length key); charge_json charge value) fields
  | Json.Bool _ | Json.Null -> charge 1
let reference_key charge reference =
  let raw=C.provider_ref_to_json reference in charge_json charge raw;
  let encoded=Canonical.encode raw in charge (String.length encoded);encoded
let equal_json charge left right =
  charge_json charge left; charge_json charge right;
  let left=Canonical.encode left and right=Canonical.encode right in
  charge (String.length left+String.length right);left=right
let definition_index charge original =
  let values=Json.array (get "definitions" (get "semantics" (D.program (R.document original)))) in
  List.fold_left (fun result value ->
    charge_json charge value;
    let id=Json.string (get "id" value) in
    require (not (Names.mem id result)) "Duplicate original semantic definition identity.";
    Names.add id value result) Names.empty values
let resolve_definition charge definitions (reference:C.provider_ref) =
  charge (1+String.length reference.definition_id);
  let raw=match Names.find_opt reference.definition_id definitions with
    | Some value -> value
    | None -> Diagnostic.fail "policy_provider_prerequisites" "Provider dependency source definition is absent." in
  charge_json charge raw;
  require (get "version" raw=str reference.definition_version && D.document_digest raw=reference.definition_digest)
    "Provider dependency DefinitionRef differs from the complete original source definition.";
  raw
type pending_dependency = {
  entry_id:string; entry_digest:string; dependency_index:int; definition:C.provider_ref;
}
let pending_dependency_to_json (value:pending_dependency) = obj [
  "entry_id",str value.entry_id;"entry_digest",str value.entry_digest;
  "dependency_index",Json.int value.dependency_index;"definition",C.provider_ref_to_json value.definition]
let pending_dependencies ?(charge=fun _ -> ()) original =
  require (R.requires_prerequisite_closure original) "Provider prerequisites require their separate realization input profile.";
  let definitions=definition_index charge original in
  let entries=Json.array (get "implementations" (get "implementations" (D.to_json (R.document original)))) in
  let bindings=R.catalog_bindings original in
  charge (List.length entries+List.length bindings);
  require (List.length entries=List.length bindings)
    "Provider prerequisites require the complete original catalog membership census.";
  let count=ref 0 in
  let rows=List.concat_map (fun (binding:R.catalog_binding) ->
    let matches=List.filter (fun entry -> charge 1; get "id" entry=str binding.entry_id) entries in
    let entry=match matches with [value] -> value
      | _ -> Diagnostic.fail "policy_provider_prerequisites" "Catalog prerequisite owner does not identify one original entry." in
    charge_json charge entry;
    require (get "version" entry=str binding.entry_version && Canonical.fingerprint entry=binding.entry_digest &&
      equal_json charge (get "operation" entry) binding.operation && equal_json charge (get "realization" entry) binding.realization)
      "Catalog prerequisite owner differs from its complete original entry and membership bridge.";
    require (get "evidence" entry=Json.Array []) "Empirical evidence references are not executable provider prerequisites.";
    let dependencies=Json.array (get "dependencies" entry) in
    bounded "dependency inventory" max_dependencies dependencies;
    let seen=ref Names.empty in
    List.mapi (fun dependency_index raw ->
      charge 1; incr count; require (!count<=max_dependencies) "Original catalog prerequisite census exceeds its closed bound.";
      let definition=C.provider_ref_of_json raw in
      ignore (resolve_definition charge definitions definition);
      let key=reference_key charge definition in
      require (not (Names.mem key !seen)) "Duplicate original catalog dependency occurrence.";
      seen:=Names.add key () !seen;
      {entry_id=binding.entry_id;entry_digest=binding.entry_digest;dependency_index;definition}) dependencies)
      bindings in
  require (rows<>[]) "The prerequisite realization profile requires nonempty original catalog dependencies.";
  rows
type origin = Original_path of string | Catalog of pending_dependency
type root = {origin:origin; definition:C.provider_ref}
type relation = Interface_environment | Chassis_capability | Chassis_interface | Chassis_environment
type edge = {source:C.provider_ref; target:C.provider_ref; relation:relation; index:int}
type issue_kind = Missing | Cycle | Extra | Unsupported
type issue = {kind:issue_kind; code:string; references:C.provider_ref list}
type node = {definition:C.provider_ref; provider:P.t option}
type t = {dependency_values:pending_dependency list; root_values:root list; node_values:node list;
  edge_values:edge list; issue_values:issue list}
let relation_name = function Interface_environment -> "interface_environment" | Chassis_capability -> "chassis_capability"
  | Chassis_interface -> "chassis_interface" | Chassis_environment -> "chassis_environment"
let kind_name = function Missing -> "missing" | Cycle -> "cycle" | Extra -> "extra" | Unsupported -> "unsupported"
let root_json (value:root) =
  let origin=match value.origin with
    | Original_path path -> obj ["kind",str "source";"path",str path]
    | Catalog dependency -> obj ["kind",str "catalog_dependency";"entry_id",str dependency.entry_id;
        "entry_digest",str dependency.entry_digest;"dependency_index",Json.int dependency.dependency_index] in
  obj ["origin",origin;"definition",C.provider_ref_to_json value.definition]
let to_json value = obj ["schema_version",str schema_version;
  "pending_dependencies",arr pending_dependency_to_json value.dependency_values;
  "roots",arr root_json value.root_values;
  "nodes",arr (fun (node:node) -> obj ["definition",C.provider_ref_to_json node.definition;
    "provider",(match node.provider with None -> Json.Null | Some pin -> P.to_json pin)]) value.node_values;
  "edges",arr (fun (edge:edge) -> obj ["source",C.provider_ref_to_json edge.source;
    "relation",str (relation_name edge.relation);"index",Json.int edge.index;"target",C.provider_ref_to_json edge.target]) value.edge_values;
  "issues",arr (fun (issue:issue) -> obj ["kind",str (kind_name issue.kind);"code",str issue.code;
    "references",arr C.provider_ref_to_json issue.references]) value.issue_values]
let derive ?(charge=fun _ -> ()) ~original ~context () =
  require (R.requires_prerequisite_closure original && X.requires_prerequisite_closure context)
    "Provider dependency derivation requires matching prerequisite profiles.";
  let dependency_values=pending_dependencies ~charge original in
  let definitions=definition_index charge original in
  let document=D.to_json (R.document original) in
  let deployment=get "deployment" document in
  let roots_rev=ref [] and root_count=ref 0 in
  let root origin definition =
    charge 1; incr root_count; require (!root_count<=max_roots) "Provider dependency roots exceed the closed bound.";
    ignore (resolve_definition charge definitions definition);
    roots_rev:={origin;definition}:: !roots_rev in
  let source path raw=root (Original_path path) (C.provider_ref_of_json raw) in
  let source_rows path raw=List.iteri (fun index value ->
    source (path^"/"^string_of_int index) value) (Json.array raw) in
  List.iteri (fun index binding ->
    let chassis=get "chassis" binding and path="/deployment/bindings/"^string_of_int index^"/chassis" in
    source (path^"/operational_model") (get "operational_model" chassis);
    List.iter (fun key -> source_rows (path^"/"^key) (get key chassis)) ["capabilities";"interfaces";"environment"])
    (Json.array (get "bindings" deployment));
  source_rows "/deployment/environment" (get "environment" deployment);
  List.iteri (fun index (declaration:D.declaration) -> charge 1;
    if declaration.kind=D.Role then source_rows
      ("/program/declarations/"^string_of_int index^"/requires") (get "requires" declaration.value))
    (D.declarations (R.document original));
  List.iter (fun key -> source ("/deployment/delivery/"^key) (get key (get "delivery" deployment)))
    ["arrival";"expression";"activation";"contract"];
  List.iter (fun (dependency:pending_dependency) -> root (Catalog dependency) dependency.definition) dependency_values;
  let root_values=List.rev !roots_rev in
  let supplied=X.providers context in
  let provider_index=List.fold_left (fun index (provider:V.provider) ->
    let key=reference_key charge provider.definition in
    require (not (Names.mem key index)) "Duplicate complete provider DefinitionRef.";
    ignore (resolve_definition charge definitions provider.definition);
    Names.add key provider index) Names.empty supplied in
  let states=ref Names.empty and nodes_rev=ref [] and edges_rev=ref [] and issues_rev=ref [] in
  let node_count=ref 0 and edge_count=ref 0 and issue_count=ref 0 in
  let issue kind code references =
    charge 1; incr issue_count; require (!issue_count<=max_nodes+max_edges) "Provider dependency findings exceed the closed bound.";
    issues_rev:={kind;code;references}:: !issues_rev in
  let rec visit trail reference =
    let key=reference_key charge reference in
    match Names.find_opt key !states with
    | Some true -> ()
    | Some false ->
      let rec until = function
        | [] -> []
        | head::tail -> charge 1;
          if reference_key charge head=key then [head] else head::until tail in
      issue Cycle "prerequisite_cycle" (List.rev (reference::until trail))
    | None ->
      charge 1; incr node_count; require (!node_count<=max_nodes) "Provider dependency nodes exceed the closed bound.";
      let definition=resolve_definition charge definitions reference in
      let provider=Names.find_opt key provider_index in
      nodes_rev:={definition=reference;provider=Option.map (fun (value:V.provider) -> value.identity) provider}:: !nodes_rev;
      states:=Names.add key false !states;
      if not (List.mem (get "category" definition) (List.map str ["model";"environment";"interface";"capability";"delivery"])) then
        issue Unsupported "prerequisite_definition_unsupported" [reference];
      (match provider with
       | None -> issue Missing "prerequisite_provider_missing" [reference]
       | Some provider ->
         let edge relation index target =
           charge 1; incr edge_count; require (!edge_count<=max_edges) "Provider dependency edges exceed the closed bound.";
           ignore (resolve_definition charge definitions target);
           edges_rev:={source=reference;target;relation;index}:: !edges_rev;
           visit (reference::trail) target in
         (match provider.body with
          | V.Interface body -> edge Interface_environment 0 body.environment
          | V.Chassis body ->
            (* operational_model identifies this provider. It is checked against
               the original chassis by the context checker, not traversed as a
               self-justifying prerequisite edge. *)
            List.iter (fun (field,relation) -> List.iteri (fun index raw ->
              edge relation index (C.provider_ref_of_json raw)) (Json.array (get field body)))
              ["capabilities",Chassis_capability;"interfaces",Chassis_interface;"environment",Chassis_environment]
          | V.Environment _ | V.Delivery _ -> ()));
      states:=Names.add key true !states in
  List.iter (fun (root:root) -> visit [] root.definition) root_values;
  List.iter (fun (provider:V.provider) ->
    let key=reference_key charge provider.definition in
    if not (Names.mem key !states) then issue Extra "prerequisite_provider_extra" [provider.definition]) supplied;
  let value={dependency_values;root_values;node_values=List.rev !nodes_rev;
    edge_values=List.rev !edges_rev;issue_values=List.rev !issues_rev} in
  let raw=to_json value in charge_json charge raw; M.check_resources raw;value
let dependencies value = value.dependency_values
let roots value = value.root_values
let reachable value = List.map (fun (node:node) -> node.definition) value.node_values
let edges value = value.edge_values
let issues value = value.issue_values

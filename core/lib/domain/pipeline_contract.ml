open Bioc_wire
module E = Realization_evidence
module Strings = Set.Make(String)
type json = Json.t
type stage = Intent | Behavior | Mechanism | Components | Construct | Molecular
type artifact_status = Partial | Complete
type outcome = E.outcome
type evidence_kind = E.evidence_kind
let resource_profile = "biocompiler.pipeline_contract.records.v1"
(* Reuse the checker-independent, streaming structural walk. Its limits count
   every value/key occurrence and guard cyclic values/list spines before encode. *)
module Codec = Verification_exploration.Codec
let resource_limits = match Codec.limits_json Codec.default_limits with
  | Json.Object fields -> Json.Object (("profile",Json.String resource_profile)::List.remove_assoc "profile" fields)
  | _ -> assert false
let require ?path condition message = Diagnostic.require ?path condition "pipeline_contract" message
let fail ?path message = Diagnostic.fail ?path "pipeline_contract" message
let str value = Json.String value
let stage_name = function
  | Intent -> "typed intent and contracts" | Behavior -> "behavioral IR"
  | Mechanism -> "molecular mechanism IR" | Components -> "selected component IR"
  | Construct -> "construct IR" | Molecular -> "sequence and molecular specification"
let stage_index = function Intent->0 | Behavior->1 | Mechanism->2 | Components->3 | Construct->4 | Molecular->5
let stage_of_json ?path = function
  | Json.String "typed intent and contracts" -> Intent | Json.String "behavioral IR" -> Behavior
  | Json.String "molecular mechanism IR" -> Mechanism | Json.String "selected component IR" -> Components
  | Json.String "construct IR" -> Construct | Json.String "sequence and molecular specification" -> Molecular
  | _ -> fail ?path "Invalid pass stages."
let status_name = function Partial->"partial" | Complete->"complete"
let status_of_json ~path = function Json.String "partial"->Partial | Json.String "complete"->Complete
  | _ -> fail ~path "Invalid pipeline artifact status."
let outcome_name = function E.Pass->"pass" | E.Fail->"fail" | E.Unknown->"unknown" | E.Unsupported->"unsupported"
let outcome_of_json ~path = function
  | Json.String "pass"->E.Pass | Json.String "fail"->E.Fail
  | Json.String "unknown"->E.Unknown | Json.String "unsupported"->E.Unsupported
  | _ -> fail ~path "Invalid check outcome."
let evidence_kind_name = function E.Exact->"exact" | E.Model_conditional->"model_conditional"
  | E.Empirical->"empirical" | E.Unresolved->"unresolved"
let evidence_kind_of_json ~path ~message = function
  | Json.String "exact"->E.Exact | Json.String "model_conditional"->E.Model_conditional
  | Json.String "empirical"->E.Empirical | Json.String "unresolved"->E.Unresolved
  | _ -> fail ~path message
let text ~path raw = match raw with Json.String value->value | _->fail ~path "Pipeline record text must be a string."
let name ~path label raw =
  match raw with Json.String value ->
    (try ignore(Json.name ~path raw) with Diagnostic.Error _->fail ~path (label^" must be a nonempty string."));value
  | _ -> fail ~path (label^" must be a nonempty string.")
let boolean ~path message = function Json.Bool value->value | _->fail ~path message
let optional decode = function Json.Null->None | value->Some(decode value)
let optional_json encode = function None->Json.Null | Some value->encode value
let bounded limits values =
  let maximum = Json.integer (Json.field "max_nodes" (Json.object_fields (Codec.limits_json limits))) |> Z.to_int in
  let rec visit count = function []->values | _::rest -> Codec.charge limits 1;
    require (count < maximum) "Pipeline collection exceeds its structural bound.";visit (count+1) rest in
  visit 0 values
let array limits encode values = Json.Array(List.map encode (bounded limits values))
let raw_array ~path message = function Json.Array values->values | _->fail ~path message
let unique limits ~path ~message values =
  let seen=ref Strings.empty in
  List.iter(fun value->Codec.charge limits (64*(String.length value+1));
    require ~path (not(Strings.mem value !seen)) message;seen:=Strings.add value !seen) values
let names limits ~path label raw =
  let values=raw_array ~path (label^" must be an array.") raw |> List.map(name ~path label) in
  unique limits ~path ~message:(label^" must be unique.") values;values
let texts ~path raw = raw_array ~path "Pipeline record collection must be an array." raw |> List.map(text ~path)
let mapping ~path message raw = match raw with Json.Object _->raw | _->fail ~path message
let dependency_fields ~path raw =
  match raw with Json.Object fields->List.map(fun (key,value)->key,text ~path:(path^"/"^key) value) fields
  | _->fail ~path "Pipeline dependencies must be an object."
let dependencies_json limits values = Json.Object(List.map(fun (key,value)->key,str value)(bounded limits values))
let record limits ~path label keys raw =
  let size=Codec.measure ~limits ~path raw in
  Codec.charge limits(128*(size.bytes+size.nodes+1));
  match raw with
  | Json.Object fields ->
      require ~path (List.sort String.compare (List.map fst fields)=List.sort String.compare keys)
        ("Invalid fields in "^label^".");fields
  | _->fail ~path ("Invalid fields in "^label^".")
let get path fields key = Json.field ~path:(path^"/"^key) key fields
let target limits ~path raw =
  let size=Codec.measure ~limits ~path raw in
  Codec.charge limits (128*(size.bytes+size.nodes+1));Build_request.Target.of_json ~path raw
(* Cached raw content has no authority bit beyond its historical accepted field.
   Fingerprinting neither invokes nor creates a manager. *)
type packed = {json:json;fingerprint:string;size:int}
let pack limits json = let encoded=Codec.encode ~limits json in
  Codec.charge limits(String.length encoded);
  {json;fingerprint=Canonical.sha256 encoded;size=String.length encoded}

module Source_link = struct
  type t = {packed:packed;requirement_id:string;source_node_id:string;target_node_id:string;pass_name:string}
  let encode _limits ~requirement_id ~source_node_id ~target_node_id ~pass_name =
    Json.Object ["requirement_id",str requirement_id;
      "source_node_id",str source_node_id;
      "target_node_id",str target_node_id;
      "pass_name",str pass_name]
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits ~path "Source_link" ["requirement_id";"source_node_id";"target_node_id";"pass_name"] raw in
    let get key=get path fields key in
    let requirement_id=text ~path:(path^"/requirement_id") (get "requirement_id") in
    let source_node_id=text ~path:(path^"/source_node_id") (get "source_node_id") in
    let target_node_id=text ~path:(path^"/target_node_id") (get "target_node_id") in
    let pass_name=text ~path:(path^"/pass_name") (get "pass_name") in
    let packed=pack limits (encode limits ~requirement_id ~source_node_id ~target_node_id ~pass_name) in
    {packed;requirement_id;source_node_id;target_node_id;pass_name}
  let make ?(limits=Codec.default_limits) ~requirement_id ~source_node_id ~target_node_id ~pass_name () =
    of_json ~limits (encode limits ~requirement_id ~source_node_id ~target_node_id ~pass_name)
  let to_json (value:t)=value.packed.json
  let fingerprint (value:t)=value.packed.fingerprint
  let canonical_size (value:t)=value.packed.size
  let requirement_id (value:t)=value.requirement_id
  let source_node_id (value:t)=value.source_node_id
  let target_node_id (value:t)=value.target_node_id
  let pass_name (value:t)=value.pass_name
end

module Producer_obligation = struct
  type t = {packed:packed;requirement_id:string;description:string;evidence_kind:evidence_kind;evidence_refs:string list}
  let encode limits ~requirement_id ~description ~evidence_kind ~evidence_refs =
    Json.Object ["requirement_id",str requirement_id;
      "description",str description;
      "evidence_kind",str(evidence_kind_name evidence_kind);
      "evidence_refs",array limits str evidence_refs]
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits ~path "Producer_obligation" ["requirement_id";"description";"evidence_kind";"evidence_refs"] raw in
    let get key=get path fields key in
    let requirement_id=text ~path:(path^"/requirement_id") (get "requirement_id") in
    let description=text ~path:(path^"/description") (get "description") in
    let evidence_kind=evidence_kind_of_json ~path:(path^"/evidence_kind") ~message:"Invalid evidence kind." (get "evidence_kind") in
    let evidence_refs=texts ~path:(path^"/evidence_refs") (get "evidence_refs") in
    let packed=pack limits (encode limits ~requirement_id ~description ~evidence_kind ~evidence_refs) in
    {packed;requirement_id;description;evidence_kind;evidence_refs}
  let make ?(limits=Codec.default_limits) ~requirement_id ~description ?(evidence_kind=E.Unresolved) ?(evidence_refs=[]) () =
    of_json ~limits (encode limits ~requirement_id ~description ~evidence_kind ~evidence_refs)
  let to_json (value:t)=value.packed.json
  let fingerprint (value:t)=value.packed.fingerprint
  let canonical_size (value:t)=value.packed.size
  let requirement_id (value:t)=value.requirement_id
  let description (value:t)=value.description
  let evidence_kind (value:t)=value.evidence_kind
  let evidence_refs (value:t)=value.evidence_refs
end

module Scoped_obligation = struct
  type t = {packed:packed;id:string;scope:string;evidence_kind:evidence_kind;description:string}
  let encode _limits ~id ~scope ~evidence_kind ~description =
    Json.Object ["id",str id;
      "scope",str scope;
      "evidence_kind",str(evidence_kind_name evidence_kind);
      "description",str description]
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits ~path "Scoped_obligation" ["id";"scope";"evidence_kind";"description"] raw in
    let get key=get path fields key in
    let id=name ~path:(path^"/id") "Obligation" (get "id") in
    let scope=name ~path:(path^"/scope") "Scope" (get "scope") in
    let description=name ~path:(path^"/description") "Description" (get "description") in
    let evidence_kind=evidence_kind_of_json ~path:(path^"/evidence_kind") ~message:"Invalid evidence kind." (get "evidence_kind") in
    let packed=pack limits (encode limits ~id ~scope ~evidence_kind ~description) in
    {packed;id;scope;evidence_kind;description}
  let make ?(limits=Codec.default_limits) ~id ~scope ~evidence_kind ~description () =
    of_json ~limits (encode limits ~id ~scope ~evidence_kind ~description)
  let to_json (value:t)=value.packed.json
  let fingerprint (value:t)=value.packed.fingerprint
  let canonical_size (value:t)=value.packed.size
  let id (value:t)=value.id
  let scope (value:t)=value.scope
  let evidence_kind (value:t)=value.evidence_kind
  let description (value:t)=value.description
end

module Check_spec = struct
  type t = {packed:packed;id:string;evidence_kind:evidence_kind;discharges:string list}
  let encode limits ~id ~evidence_kind ~discharges =
    Json.Object ["id",str id;
      "evidence_kind",str(evidence_kind_name evidence_kind);
      "discharges",array limits str discharges]
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits ~path "Check_spec" ["id";"evidence_kind";"discharges"] raw in
    let get key=get path fields key in
    let id=name ~path:(path^"/id") "Check id" (get "id") in
    let evidence_kind=evidence_kind_of_json ~path:(path^"/evidence_kind") ~message:"Invalid check kind." (get "evidence_kind") in
    require ~path (evidence_kind <> E.Unresolved) "An unresolved claim cannot discharge an obligation.";
    let discharges=names limits ~path:(path^"/discharges") "Discharges" (get "discharges") in
    let packed=pack limits (encode limits ~id ~evidence_kind ~discharges) in
    {packed;id;evidence_kind;discharges}
  let make ?(limits=Codec.default_limits) ~id ~evidence_kind ?(discharges=[]) () =
    of_json ~limits (encode limits ~id ~evidence_kind ~discharges)
  let to_json (value:t)=value.packed.json
  let fingerprint (value:t)=value.packed.fingerprint
  let canonical_size (value:t)=value.packed.size
  let id (value:t)=value.id
  let evidence_kind (value:t)=value.evidence_kind
  let discharges (value:t)=value.discharges
end

module Check_decision = struct
  type t = {packed:packed;outcome:outcome;detail:string;evidence:json}
  let encode _limits ~outcome ~detail ~evidence =
    Json.Object ["outcome",str(outcome_name outcome);
      "detail",str detail;
      "evidence",evidence]
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits ~path "Check_decision" ["outcome";"detail";"evidence"] raw in
    let get key=get path fields key in
    let outcome=outcome_of_json ~path:(path^"/outcome") (get "outcome") in
    let detail=name ~path:(path^"/detail") "Check detail" (get "detail") in
    let evidence=mapping ~path:(path^"/evidence") "Evidence must be an object." (get "evidence") in
    let packed=pack limits (encode limits ~outcome ~detail ~evidence) in
    {packed;outcome;detail;evidence}
  let make ?(limits=Codec.default_limits) ~outcome ~detail ?(evidence=Json.Object []) () =
    of_json ~limits (encode limits ~outcome ~detail ~evidence)
  let to_json (value:t)=value.packed.json
  let fingerprint (value:t)=value.packed.fingerprint
  let canonical_size (value:t)=value.packed.size
  let outcome (value:t)=value.outcome
  let detail (value:t)=value.detail
  let evidence (value:t)=value.evidence
end

module Pass_contract = struct
  type t = {packed:packed;id:string;version:string;input_stage:stage;output_stage:stage;input_schema:string;output_schema:string;profile:string;profile_version:string;supported_operations:string list;checks:Check_spec.t list;dependency_keys:string list;targets:string list;required_capabilities:string list;consumes_requirements:string list;assumptions:string list;introduces:Scoped_obligation.t list;requires_source_map:bool;requires_observation_map:bool;changed_properties:string list;invalidated_analyses:string list;operation_path:string list}
  let encode limits ~id ~version ~input_stage ~output_stage ~input_schema ~output_schema ~profile ~profile_version ~supported_operations ~checks ~dependency_keys ~targets ~required_capabilities ~consumes_requirements ~assumptions ~introduces ~requires_source_map ~requires_observation_map ~changed_properties ~invalidated_analyses ~operation_path =
    Json.Object ["id",str id;
      "version",str version;
      "input_stage",str(stage_name input_stage);
      "output_stage",str(stage_name output_stage);
      "input_schema",str input_schema;
      "output_schema",str output_schema;
      "profile",str profile;
      "profile_version",str profile_version;
      "operation_path",array limits str operation_path;
      "supported_operations",array limits str supported_operations;
      "checks",array limits Check_spec.to_json checks;
      "dependency_keys",array limits str dependency_keys;
      "targets",array limits str targets;
      "required_capabilities",array limits str required_capabilities;
      "consumes_requirements",array limits str consumes_requirements;
      "assumptions",array limits str assumptions;
      "introduces",array limits Scoped_obligation.to_json introduces;
      "requires_source_map",Json.Bool requires_source_map;
      "requires_observation_map",Json.Bool requires_observation_map;
      "changed_properties",array limits str changed_properties;
      "invalidated_analyses",array limits str invalidated_analyses]
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits ~path "Pass_contract" ["id";"version";"input_stage";"output_stage";"input_schema";"output_schema";"profile";"profile_version";"supported_operations";"checks";"dependency_keys";"targets";"required_capabilities";"consumes_requirements";"assumptions";"introduces";"requires_source_map";"requires_observation_map";"changed_properties";"invalidated_analyses";"operation_path"] raw in
    let get key=get path fields key in
    let id=name ~path:(path^"/id") "id" (get "id") in
    let version=name ~path:(path^"/version") "version" (get "version") in
    let input_schema=name ~path:(path^"/input_schema") "input_schema" (get "input_schema") in
    let output_schema=name ~path:(path^"/output_schema") "output_schema" (get "output_schema") in
    let profile=name ~path:(path^"/profile") "profile" (get "profile") in
    let profile_version=name ~path:(path^"/profile_version") "profile_version" (get "profile_version") in
    let input_stage=(try stage_of_json ~path:(path^"/input_stage") (get "input_stage") with Diagnostic.Error _->fail ~path:(path^"/input_stage") "Invalid pass stages.") in
    let output_stage=(try stage_of_json ~path:(path^"/output_stage") (get "output_stage") with Diagnostic.Error _->fail ~path:(path^"/output_stage") "Invalid pass stages.") in
    require ~path (stage_index output_stage=stage_index input_stage+1)
      "A pass must advance exactly one declared compiler stage.";
    let operation_path=names limits ~path:(path^"/operation_path") "operation_path" (get "operation_path") in
    let supported_operations=names limits ~path:(path^"/supported_operations") "supported_operations" (get "supported_operations") in
    let dependency_keys=names limits ~path:(path^"/dependency_keys") "dependency_keys" (get "dependency_keys") in
    let required_capabilities=names limits ~path:(path^"/required_capabilities") "required_capabilities" (get "required_capabilities") in
    let consumes_requirements=names limits ~path:(path^"/consumes_requirements") "consumes_requirements" (get "consumes_requirements") in
    let assumptions=names limits ~path:(path^"/assumptions") "assumptions" (get "assumptions") in
    let changed_properties=names limits ~path:(path^"/changed_properties") "changed_properties" (get "changed_properties") in
    let invalidated_analyses=names limits ~path:(path^"/invalidated_analyses") "invalidated_analyses" (get "invalidated_analyses") in
    let checks=raw_array ~path:(path^"/checks") "Invalid checks." (get "checks") |> List.mapi(fun index raw->Check_spec.of_json ~limits ~path:(path^"/checks/"^string_of_int index) raw) in
    unique limits ~path ~message:"Duplicate checks." (List.map Check_spec.id checks);
    let introduces=raw_array ~path:(path^"/introduces") "Invalid introduces." (get "introduces") |> List.mapi(fun index raw->Scoped_obligation.of_json ~limits ~path:(path^"/introduces/"^string_of_int index) raw) in
    unique limits ~path ~message:"Duplicate introduces." (List.map Scoped_obligation.id introduces);
    require ~path (checks<>[]) "A pass requires at least one independent check.";
    let targets=(match get "targets" with
      | Json.Array values -> List.map(function Json.String value when value="DNA" || value="RNA"->value
          | _->fail ~path "Invalid target applicability.") values
      | _->fail ~path "Invalid target applicability.") in
    require ~path (targets<>[] && List.for_all(fun value->value="DNA" || value="RNA")targets)
      "Invalid target applicability.";
    unique limits ~path ~message:"Invalid target applicability." targets;
    let requires_source_map=boolean ~path:(path^"/requires_source_map") "Mapping requirements must be Boolean." (get "requires_source_map") in
    let requires_observation_map=boolean ~path:(path^"/requires_observation_map") "Mapping requirements must be Boolean." (get "requires_observation_map") in
    let packed=pack limits (encode limits ~id ~version ~input_stage ~output_stage ~input_schema ~output_schema ~profile ~profile_version ~supported_operations ~checks ~dependency_keys ~targets ~required_capabilities ~consumes_requirements ~assumptions ~introduces ~requires_source_map ~requires_observation_map ~changed_properties ~invalidated_analyses ~operation_path) in
    {packed;id;version;input_stage;output_stage;input_schema;output_schema;profile;profile_version;supported_operations;checks;dependency_keys;targets;required_capabilities;consumes_requirements;assumptions;introduces;requires_source_map;requires_observation_map;changed_properties;invalidated_analyses;operation_path}
  let make ?(limits=Codec.default_limits) ~id ~version ~input_stage ~output_stage ~input_schema ~output_schema ~profile ~profile_version ~supported_operations ~checks ?(dependency_keys=[]) ?(targets=["DNA";"RNA"]) ?(required_capabilities=[]) ?(consumes_requirements=[]) ?(assumptions=[]) ?(introduces=[]) ?(requires_source_map=true) ?(requires_observation_map=false) ?(changed_properties=[]) ?(invalidated_analyses=[]) ?(operation_path=[]) () =
    of_json ~limits (encode limits ~id ~version ~input_stage ~output_stage ~input_schema ~output_schema ~profile ~profile_version ~supported_operations ~checks ~dependency_keys ~targets ~required_capabilities ~consumes_requirements ~assumptions ~introduces ~requires_source_map ~requires_observation_map ~changed_properties ~invalidated_analyses ~operation_path)
  let to_json (value:t)=value.packed.json
  let fingerprint (value:t)=value.packed.fingerprint
  let canonical_size (value:t)=value.packed.size
  let id (value:t)=value.id
  let version (value:t)=value.version
  let input_stage (value:t)=value.input_stage
  let output_stage (value:t)=value.output_stage
  let input_schema (value:t)=value.input_schema
  let output_schema (value:t)=value.output_schema
  let profile (value:t)=value.profile
  let profile_version (value:t)=value.profile_version
  let supported_operations (value:t)=value.supported_operations
  let checks (value:t)=value.checks
  let dependency_keys (value:t)=value.dependency_keys
  let targets (value:t)=value.targets
  let required_capabilities (value:t)=value.required_capabilities
  let consumes_requirements (value:t)=value.consumes_requirements
  let assumptions (value:t)=value.assumptions
  let introduces (value:t)=value.introduces
  let requires_source_map (value:t)=value.requires_source_map
  let requires_observation_map (value:t)=value.requires_observation_map
  let changed_properties (value:t)=value.changed_properties
  let invalidated_analyses (value:t)=value.invalidated_analyses
  let operation_path (value:t)=value.operation_path
end

module Pass_context = struct
  type t = {packed:packed;input:json;output:json option;target:Build_request.Target.t;configuration:json;dependencies:(string * string) list;requirements:string list;source_links:Source_link.t list;observation_map:json}
  let encode limits ~input ~output ~target ~configuration ~dependencies ~requirements ~source_links ~observation_map =
    Json.Object ["input",input;
      "output",optional_json (fun value->value) output;
      "target",Build_request.Target.to_json target;
      "configuration",configuration;
      "dependencies",dependencies_json limits dependencies;
      "requirements",array limits str requirements;
      "source_links",array limits Source_link.to_json source_links;
      "observation_map",observation_map]
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits ~path "Pass_context" ["input";"output";"target";"configuration";"dependencies";"requirements";"source_links";"observation_map"] raw in
    let get key=get path fields key in
    let input=(get "input") in
    let output=optional (fun value->value) (get "output") in
    let target=target limits ~path:(path^"/target") (get "target") in
    let configuration=(get "configuration") in
    let dependencies=dependency_fields ~path:(path^"/dependencies") (get "dependencies") in
    let requirements=texts ~path:(path^"/requirements") (get "requirements") in
    let source_links=raw_array ~path:(path^"/source_links") "Pipeline record collection must be an array." (get "source_links") |> List.mapi(fun index raw->Source_link.of_json ~limits ~path:(path^"/source_links/"^string_of_int index) raw) in
    let observation_map=(get "observation_map") in
    let packed=pack limits (encode limits ~input ~output ~target ~configuration ~dependencies ~requirements ~source_links ~observation_map) in
    {packed;input;output;target;configuration;dependencies;requirements;source_links;observation_map}
  let make ?(limits=Codec.default_limits) ~input ~output ~target ~configuration ~dependencies ~requirements ?(source_links=[]) ?(observation_map=Json.Object []) () =
    of_json ~limits (encode limits ~input ~output ~target ~configuration ~dependencies ~requirements ~source_links ~observation_map)
  let to_json (value:t)=value.packed.json
  let fingerprint (value:t)=value.packed.fingerprint
  let canonical_size (value:t)=value.packed.size
  let input (value:t)=value.input
  let output (value:t)=value.output
  let target (value:t)=value.target
  let configuration (value:t)=value.configuration
  let dependencies (value:t)=value.dependencies
  let requirements (value:t)=value.requirements
  let source_links (value:t)=value.source_links
  let observation_map (value:t)=value.observation_map
end

module Component_input_contract = struct
  type t = {packed:packed;id:string;version:string;schema:string;checks:Check_spec.t list;requirements:string list;obligations:Scoped_obligation.t list;dependency_keys:string list;operation_path:string list}
  let encode limits ~id ~version ~schema ~checks ~requirements ~obligations ~dependency_keys ~operation_path =
    Json.Object ["id",str id;
      "version",str version;
      "schema",str schema;
      "stage",str(stage_name Components);
      "checks",array limits Check_spec.to_json checks;
      "requirements",array limits str requirements;
      "obligations",array limits Scoped_obligation.to_json obligations;
      "dependency_keys",array limits str dependency_keys;
      "operation_path",array limits str operation_path]
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits ~path "Component_input_contract" ["id";"version";"schema";"checks";"requirements";"obligations";"dependency_keys";"operation_path";"stage"] raw in
    let get key=get path fields key in
    let id=name ~path:(path^"/id") "id" (get "id") in
    let version=name ~path:(path^"/version") "version" (get "version") in
    let schema=name ~path:(path^"/schema") "schema" (get "schema") in
    let requirements=names limits ~path:(path^"/requirements") "requirements" (get "requirements") in
    let dependency_keys=names limits ~path:(path^"/dependency_keys") "dependency_keys" (get "dependency_keys") in
    let operation_path=names limits ~path:(path^"/operation_path") "operation_path" (get "operation_path") in
    let checks=raw_array ~path:(path^"/checks") "Invalid component admission checks." (get "checks") |> List.mapi(fun index raw->Check_spec.of_json ~limits ~path:(path^"/checks/"^string_of_int index) raw) in
    unique limits ~path ~message:"Invalid component admission checks." (List.map Check_spec.id checks);
    let obligations=raw_array ~path:(path^"/obligations") "Invalid component admission obligations." (get "obligations") |> List.mapi(fun index raw->Scoped_obligation.of_json ~limits ~path:(path^"/obligations/"^string_of_int index) raw) in
    unique limits ~path ~message:"Invalid component admission obligations." (List.map Scoped_obligation.id obligations);
    require ~path (checks<>[]) "Component admission needs independent checks.";
    let inventory=Hashtbl.create(List.length obligations) in
    List.iter(fun value->Hashtbl.add inventory (Scoped_obligation.id value) (Scoped_obligation.evidence_kind value)) obligations;
    List.iter(fun check->List.iter(fun key->
      Codec.charge limits(64*(String.length key+1));
      require ~path (Hashtbl.find_opt inventory key=Some(Check_spec.evidence_kind check))
        "Component admission check cannot discharge an unknown obligation or evidence kind.")
      (Check_spec.discharges check))checks;
    require ~path (get "stage"=str(stage_name Components)) "Invalid component admission stage.";
    let packed=pack limits (encode limits ~id ~version ~schema ~checks ~requirements ~obligations ~dependency_keys ~operation_path) in
    {packed;id;version;schema;checks;requirements;obligations;dependency_keys;operation_path}
  let make ?(limits=Codec.default_limits) ~id ~version ~schema ~checks ~requirements ~obligations ?(dependency_keys=[]) ?(operation_path=[]) () =
    of_json ~limits (encode limits ~id ~version ~schema ~checks ~requirements ~obligations ~dependency_keys ~operation_path)
  let to_json (value:t)=value.packed.json
  let fingerprint (value:t)=value.packed.fingerprint
  let canonical_size (value:t)=value.packed.size
  let id (value:t)=value.id
  let version (value:t)=value.version
  let schema (value:t)=value.schema
  let checks (value:t)=value.checks
  let requirements (value:t)=value.requirements
  let obligations (value:t)=value.obligations
  let dependency_keys (value:t)=value.dependency_keys
  let operation_path (value:t)=value.operation_path
end

module Completion_profile = struct
  type t = {packed:packed;scope:string;stage:stage;schema:string;obligations:string list}
  let encode limits ~scope ~stage ~schema ~obligations =
    Json.Object ["scope",str scope;
      "stage",str(stage_name stage);
      "schema",str schema;
      "obligations",array limits str obligations]
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits ~path "Completion_profile" ["scope";"stage";"schema";"obligations"] raw in
    let get key=get path fields key in
    let scope=name ~path:(path^"/scope") "Completion scope" (get "scope") in
    let schema=name ~path:(path^"/schema") "Completion schema" (get "schema") in
    let stage=(try stage_of_json ~path:(path^"/stage") (get "stage") with Diagnostic.Error _->fail ~path:(path^"/stage") "Invalid completion stage.") in
    let obligations=names limits ~path:(path^"/obligations") "Completion obligations" (get "obligations") in
    require ~path (obligations<>[]) "A completed profile must require explicit obligations.";
    let packed=pack limits (encode limits ~scope ~stage ~schema ~obligations) in
    {packed;scope;stage;schema;obligations}
  let make ?(limits=Codec.default_limits) ~scope ~stage ~schema ~obligations () =
    of_json ~limits (encode limits ~scope ~stage ~schema ~obligations)
  let to_json (value:t)=value.packed.json
  let fingerprint (value:t)=value.packed.fingerprint
  let canonical_size (value:t)=value.packed.size
  let scope (value:t)=value.scope
  let stage (value:t)=value.stage
  let schema (value:t)=value.schema
  let obligations (value:t)=value.obligations
end

module Stage_record = struct
  type t = {packed:packed;id:string;stage:stage;payload:json;requirements:string list;obligations:Scoped_obligation.t list;discharged:string list;dependencies:(string * string) list;parent:string option;pass_id:string option;pass_identity:string option;checks:json;provenance:json;accepted:bool}
  let schema_version = "biocompiler.stage_record.v0.1"
  let encode limits ~id ~stage ~payload ~requirements ~obligations ~discharged ~dependencies ~parent ~pass_id ~pass_identity ~checks ~provenance ~accepted =
    Json.Object ["schema_version",str schema_version;
      "id",str id;
      "stage",str(stage_name stage);
      "payload",payload;
      "requirements",array limits str requirements;
      "obligations",array limits Scoped_obligation.to_json obligations;
      "discharged",array limits str discharged;
      "dependencies",dependencies_json limits dependencies;
      "parent",optional_json str parent;
      "pass_id",optional_json str pass_id;
      "pass_identity",optional_json str pass_identity;
      "checks",checks;
      "provenance",provenance;
      "accepted",Json.Bool accepted]
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits ~path "Stage_record" ["id";"stage";"payload";"requirements";"obligations";"discharged";"dependencies";"parent";"pass_id";"pass_identity";"checks";"provenance";"accepted";"schema_version"] raw in
    let get key=get path fields key in
    require ~path (get "schema_version"=str schema_version) "Unsupported stage-record schema.";
    let id=text ~path:(path^"/id") (get "id") in
    let stage=(try stage_of_json ~path:(path^"/stage") (get "stage") with Diagnostic.Error _->fail ~path:(path^"/stage") "Invalid pass stages.") in
    let payload=(get "payload") in
    let requirements=texts ~path:(path^"/requirements") (get "requirements") in
    let obligations=raw_array ~path:(path^"/obligations") "Pipeline record collection must be an array." (get "obligations") |> List.mapi(fun index raw->Scoped_obligation.of_json ~limits ~path:(path^"/obligations/"^string_of_int index) raw) in
    let discharged=texts ~path:(path^"/discharged") (get "discharged") in
    let dependencies=dependency_fields ~path:(path^"/dependencies") (get "dependencies") in
    let parent=optional (text ~path:(path^"/parent")) (get "parent") in
    let pass_id=optional (text ~path:(path^"/pass_id")) (get "pass_id") in
    let pass_identity=optional (text ~path:(path^"/pass_identity")) (get "pass_identity") in
    let checks=(get "checks") in
    let provenance=(get "provenance") in
    let accepted=boolean ~path:(path^"/accepted") "Historical acceptance must be Boolean." (get "accepted") in
    let packed=pack limits (encode limits ~id ~stage ~payload ~requirements ~obligations ~discharged ~dependencies ~parent ~pass_id ~pass_identity ~checks ~provenance ~accepted) in
    {packed;id;stage;payload;requirements;obligations;discharged;dependencies;parent;pass_id;pass_identity;checks;provenance;accepted}
  let make ?(limits=Codec.default_limits) ~id ~stage ~payload ~requirements ~obligations ~discharged ~dependencies ~parent ~pass_id ~pass_identity ~checks ~provenance ~accepted () =
    of_json ~limits (encode limits ~id ~stage ~payload ~requirements ~obligations ~discharged ~dependencies ~parent ~pass_id ~pass_identity ~checks ~provenance ~accepted)
  let to_json (value:t)=value.packed.json
  let fingerprint (value:t)=value.packed.fingerprint
  let canonical_size (value:t)=value.packed.size
  let id (value:t)=value.id
  let stage (value:t)=value.stage
  let payload (value:t)=value.payload
  let requirements (value:t)=value.requirements
  let obligations (value:t)=value.obligations
  let discharged (value:t)=value.discharged
  let dependencies (value:t)=value.dependencies
  let parent (value:t)=value.parent
  let pass_id (value:t)=value.pass_id
  let pass_identity (value:t)=value.pass_identity
  let checks (value:t)=value.checks
  let provenance (value:t)=value.provenance
  let accepted (value:t)=value.accepted
end

module Pipeline_result = struct
  type t = {packed:packed;status:artifact_status;artifact:Stage_record.t;scope:string;unresolved:Scoped_obligation.t list}
  let encode limits ~status ~artifact ~scope ~unresolved =
    Json.Object ["status",str(status_name status);
      "artifact",Stage_record.to_json artifact;
      "scope",str scope;
      "unresolved",array limits Scoped_obligation.to_json unresolved]
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits ~path "Pipeline_result" ["status";"artifact";"scope";"unresolved"] raw in
    let get key=get path fields key in
    let status=status_of_json ~path:(path^"/status") (get "status") in
    let artifact=Stage_record.of_json ~limits ~path:(path^"/artifact") (get "artifact") in
    let scope=text ~path:(path^"/scope") (get "scope") in
    let unresolved=raw_array ~path:(path^"/unresolved") "Pipeline record collection must be an array." (get "unresolved") |> List.mapi(fun index raw->Scoped_obligation.of_json ~limits ~path:(path^"/unresolved/"^string_of_int index) raw) in
    let packed=pack limits (encode limits ~status ~artifact ~scope ~unresolved) in
    {packed;status;artifact;scope;unresolved}
  let make ?(limits=Codec.default_limits) ~status ~artifact ~scope ~unresolved () =
    of_json ~limits (encode limits ~status ~artifact ~scope ~unresolved)
  let to_json (value:t)=value.packed.json
  let fingerprint (value:t)=value.packed.fingerprint
  let canonical_size (value:t)=value.packed.size
  let status (value:t)=value.status
  let artifact (value:t)=value.artifact
  let scope (value:t)=value.scope
  let unresolved (value:t)=value.unresolved
end

module Pass_result = struct
  type t = {packed:packed;output:json option;obligations:Producer_obligation.t list;source_links:Source_link.t list;observation_map:json;search_status:string}
  let encode limits ~output ~obligations ~source_links ~observation_map ~search_status =
    Json.Object ["output",optional_json (fun value->value) output;
      "obligations",array limits Producer_obligation.to_json obligations;
      "source_links",array limits Source_link.to_json source_links;
      "observation_map",observation_map;
      "search_status",str search_status]
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits ~path "Pass_result" ["output";"obligations";"source_links";"observation_map";"search_status"] raw in
    let get key=get path fields key in
    let output=optional (fun value->value) (get "output") in
    let obligations=raw_array ~path:(path^"/obligations") "Pipeline record collection must be an array." (get "obligations") |> List.mapi(fun index raw->Producer_obligation.of_json ~limits ~path:(path^"/obligations/"^string_of_int index) raw) in
    let source_links=raw_array ~path:(path^"/source_links") "Pipeline record collection must be an array." (get "source_links") |> List.mapi(fun index raw->Source_link.of_json ~limits ~path:(path^"/source_links/"^string_of_int index) raw) in
    let observation_map=(get "observation_map") in
    let search_status=text ~path:(path^"/search_status") (get "search_status") in
    let packed=pack limits (encode limits ~output ~obligations ~source_links ~observation_map ~search_status) in
    {packed;output;obligations;source_links;observation_map;search_status}
  let make ?(limits=Codec.default_limits) ~output ~obligations ~source_links ?(observation_map=Json.Object []) ?(search_status="candidate") () =
    of_json ~limits (encode limits ~output ~obligations ~source_links ~observation_map ~search_status)
  let to_json (value:t)=value.packed.json
  let fingerprint (value:t)=value.packed.fingerprint
  let canonical_size (value:t)=value.packed.size
  let output (value:t)=value.output
  let obligations (value:t)=value.obligations
  let source_links (value:t)=value.source_links
  let observation_map (value:t)=value.observation_map
  let search_status (value:t)=value.search_status
end

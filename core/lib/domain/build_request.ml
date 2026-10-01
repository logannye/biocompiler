open Bioc_wire

module Names = Set.Make (String)
module Bindings = Map.Make (String)

type behavior_profile = V1 | V2
type artifact_scope = Abstract_behavior | Synthetic_realization | Exact_cds | Complete_payload
type target_kind = Legacy_target | Human_target
type binding_category = User_selected | Compiler_selected | Measured | Uncertain
type binding_metadata = {
  category : binding_category;
  binding_provenance : (string * Json.t) list;
  allowed_variation : Json.t option;
  metadata_json : Json.t;
}
type t = {
  source : Intent.t;
  profile : behavior_profile;
  scope : artifact_scope;
  target_declaration : (target_kind * Json.t) option;
  overrides : (string * Json.t) list;
  defaults : (string * Json.t) list;
  bindings : (string * Json.t) list;
  constraints : (string * Json.t) list;
  preferred : (string * Json.t) list;
  metadata : (string * binding_metadata) list;
  elaboration : Json.t;
  observations : Identity.Node.t list;
}

let schema_version = "biocompiler.build_request.v0.1"
let validation_scope = "build-request-structure-target-declarations-bindings-v1"
let require = Diagnostic.require
let fail = Diagnostic.fail
let child path key =
  let escaped = String.concat "~0" (String.split_on_char '~' key) in
  let escaped = String.concat "~1" (String.split_on_char '/' escaped) in
  path ^ "/" ^ escaped
let field path key fields = Json.field ~path:(child path key) key fields
let named path key fields = Json.name ~path:(child path key) (field path key fields)
let replace key value fields = (key, value) :: List.remove_assoc key fields
let object_at path value = Json.object_fields ~path value
let schema path expected keys value =
  let fields = object_at path value in
  Json.exact_fields ~path ("schema_version" :: keys) fields;
  require ~path:(child path "schema_version")
    (Json.string (field path "schema_version" fields) = expected)
    "unsupported_schema" "Unsupported declaration schema.";
  fields
let choice path choices value =
  let value = Json.string ~path value in
  require ~path (List.mem value choices) "invalid_choice" "Unsupported declaration choice.";
  value
let finite path value =
  ignore (Json.number_to_float ~path value); value
let keys values = List.fold_left (fun keys (key, _) -> Names.add key keys) Names.empty values
let indexed values = List.to_seq values |> Bindings.of_seq
let lookup path key values = match Bindings.find_opt key values with
  | Some value -> value
  | None -> fail ~path:(child path key) "missing_field" ("Missing required field: " ^ key)
let names path value =
  let values = Json.array ~path value |> List.mapi (fun index value ->
      Json.name ~path:(child path (string_of_int index)) value) in
  let seen = ref Names.empty in
  List.iter (fun value ->
      require ~path (not (Names.mem value !seen)) "duplicate_name" "Names must be unique.";
      seen := Names.add value !seen) values;
  List.sort String.compare values
let string_array values = Json.Array (List.map (fun value -> Json.String value) values)

(* Target validation is deliberately declarative. Evidence references establish
   identity and completeness of supplied records, not their biological truth. *)
let value_domain path value =
  let fields = schema path "biocompiler.component_value_domain.v0.1"
      ["kind"; "dtype"; "unit"; "values"; "lower"; "upper"; "reason"] value in
  let kind = choice (child path "kind") ["boolean"; "scalar_interval"; "unknown"] (field path "kind" fields) in
  let dtype = Type_spec.of_json ~path:(child path "dtype") (field path "dtype" fields) in
  require ~path (List.mem (Type_spec.kind dtype) [Type_spec.Scalar; Type_spec.Condition])
    "invalid_value_domain" "Value domains require a scalar or condition type.";
  let unit_name = named path "unit" fields in
  let values = Json.array ~path:(child path "values") (field path "values" fields)
    |> List.map (Json.boolean ~path:(child path "values")) in
  require ~path (List.length values = List.length (List.sort_uniq Bool.compare values))
    "invalid_value_domain" "Boolean domain values must be unique.";
  let lower = field path "lower" fields and upper = field path "upper" fields
  and reason = field path "reason" fields in
  if Type_spec.kind dtype = Type_spec.Condition then
    require ~path (unit_name = "1") "invalid_value_domain" "Boolean domains use unit 1.";
  (match kind with
   | "boolean" ->
       require ~path (Type_spec.kind dtype = Type_spec.Condition && values <> []
                      && lower = Json.Null && upper = Json.Null && reason = Json.Null)
         "invalid_value_domain" "Boolean domains require values and no scalar bounds or reason."
   | "scalar_interval" ->
       require ~path (Type_spec.kind dtype = Type_spec.Scalar && values = [] && reason = Json.Null)
         "invalid_value_domain" "Scalar intervals cannot carry Boolean values or an unknown reason.";
       ignore (finite (child path "lower") lower); ignore (finite (child path "upper") upper);
       require ~path (Json.number_compare lower upper <= 0)
         "invalid_value_domain" "Scalar domain lower bound exceeds upper bound."
   | _ ->
       require ~path (values = [] && lower = Json.Null && upper = Json.Null)
         "invalid_value_domain" "Unknown domains cannot carry known bounds or Boolean values.";
       ignore (Json.name ~path:(child path "reason") reason));
  Json.Object (fields |> replace "dtype" (Type_spec.to_json dtype)
    |> replace "values" (Json.Array (List.map (fun value -> Json.Bool value) (List.sort Bool.compare values))))

let target_claim path value =
  let fields = schema path "biocompiler.target_claim.v0.1"
      ["description"; "basis"; "evidence_ids"; "limitations"] value in
  ignore (named path "description" fields); ignore (named path "limitations" fields);
  let basis = choice (child path "basis") ["unestablished"; "assumed"; "cited"] (field path "basis" fields) in
  let ids = names (child path "evidence_ids") (field path "evidence_ids" fields) in
  require ~path ((ids <> []) = (basis = "cited")) "invalid_target_claim"
    "Only cited target claims require nonempty evidence identities.";
  Json.Object (replace "evidence_ids" (string_array ids) fields), ids

let evidence path value =
  let fields = schema path "biocompiler.target_evidence.v0.1"
      ["id"; "source"; "taxon_id"; "system"; "source_context"; "locator"; "limitations"] value in
  List.iter (fun key -> ignore (named path key fields)) ["id"; "source_context"; "locator"; "limitations"];
  let source_path = child path "source" in
  let source = schema source_path "biocompiler.component_identity.v0.1"
      ["kind"; "id"; "version"; "content_fingerprint"] (field path "source" fields) in
  ignore (choice (child source_path "kind") ["source"; "evidence"] (field source_path "kind" source));
  ignore (named source_path "id" source); ignore (named source_path "version" source);
  let digest = Json.string ~path:(child source_path "content_fingerprint") (field source_path "content_fingerprint" source) in
  require ~path:source_path (String.length digest = 64 && String.for_all (function '0' .. '9' | 'a' .. 'f' -> true | _ -> false) digest)
    "invalid_content_fingerprint" "Pinned evidence requires a lowercase SHA-256 content fingerprint.";
  let system = choice (child path "system")
      ["human_in_vivo"; "primary_human_cells"; "human_cell_line"; "nonhuman_in_vivo";
       "nonhuman_cells"; "cell_free"; "software_fixture"] (field path "system" fields) in
  let taxon = field path "taxon_id" fields in
  (match system with
   | "human_in_vivo" | "primary_human_cells" | "human_cell_line" ->
       require ~path (Z.equal (Json.integer ~path:(child path "taxon_id") taxon) (Z.of_int 9606))
         "invalid_evidence_taxon" "Human evidence requires taxon 9606."
   | "nonhuman_in_vivo" | "nonhuman_cells" ->
       let taxon = Json.integer ~path:(child path "taxon_id") taxon in
       require ~path (Z.sign taxon > 0 && not (Z.equal taxon (Z.of_int 9606)))
         "invalid_evidence_taxon" "Non-human evidence requires a positive non-human taxon."
   | _ -> require ~path (taxon = Json.Null) "invalid_evidence_taxon" "Cell-free and software evidence have no recipient taxon.");
  value

let records path decode value =
  let records = Json.array ~path value |> List.mapi (fun index value ->
      let path = child path (string_of_int index) in
      let decoded = decode path value in
      named path "id" (Json.object_fields decoded), decoded) in
  require ~path (Names.cardinal (keys records) = List.length records)
    "duplicate_target_record" "Target record identities must be unique.";
  List.sort (fun (a, _) (b, _) -> String.compare a b) records

let human_contract path ~compartments value =
  let compartments = Names.of_list compartments in
  let claims = ["cell_subtype"; "cell_state"; "tissue_context"; "disease_context";
                "population_inclusion"; "population_exclusion"] in
  let fields = schema path "biocompiler.human_target_contract.v0.1"
      (claims @ ["recipient_taxon_id"; "engineering"; "host_dependencies"; "operating_conditions"; "evidence"]) value in
  require ~path (Z.equal (Json.integer (field path "recipient_taxon_id" fields)) (Z.of_int 9606))
    "invalid_human_target" "Human target recipients require taxon 9606.";
  require ~path (Json.string (field path "engineering" fields) = "in_vivo")
    "invalid_human_target" "Human target engineering must be in vivo.";
  let used_evidence = ref Names.empty in
  let claim path value =
    let normalized, ids = target_claim path value in
    List.iter (fun id -> used_evidence := Names.add id !used_evidence) ids;
    normalized in
  let fields = List.fold_left (fun fields key ->
      replace key (claim (child path key) (field path key fields)) fields) fields claims in
  let dependency operating path value =
    let schema_name, specific = if operating then
        "biocompiler.human_operating_condition.v0.1", ["observable"; "domain"]
      else "biocompiler.human_host_dependency.v0.1", ["capability"] in
    let fields = schema path schema_name (["id"; "compartment"; "support"] @ specific) value in
    ignore (named path "id" fields);
    ignore (named path (if operating then "observable" else "capability") fields);
    require ~path (Names.mem (named path "compartment" fields) compartments)
      "undeclared_compartment" "Target obligation refers to an undeclared compartment.";
    let fields = replace "support" (claim (child path "support") (field path "support" fields)) fields in
    Json.Object (if operating then replace "domain" (value_domain (child path "domain") (field path "domain" fields)) fields else fields) in
  let fields = List.fold_left (fun fields (key, decode, required) ->
      let values = records (child path key) decode (field path key fields) in
      require ~path:(child path key) (not required || values <> []) "missing_target_inventory"
        "Human targets require explicit host dependency and operating condition inventories.";
      replace key (Json.Array (List.map snd values)) fields)
      fields ["host_dependencies", dependency false, true;
              "operating_conditions", dependency true, true;
              "evidence", evidence, false] in
  let evidence_ids = Json.array (field path "evidence" fields)
    |> List.fold_left (fun seen value -> Names.add (named path "id" (Json.object_fields value)) seen) Names.empty in
  require ~path (Names.subset !used_evidence evidence_ids) "unknown_target_evidence"
    "A target claim refers to evidence absent from the supplied inventory.";
  Json.Object fields

let decode_target path value =
  let raw = object_at path value in
  let version = Json.string (field path "schema_version" raw) in
  let kind, extra = match version with
    | "biocompiler.target.v0.1" -> Legacy_target, []
    | "biocompiler.human_target_context.v0.1" -> Human_target, ["human_target"]
    | _ -> fail ~path "unsupported_schema" "Unsupported target context schema." in
  let fields = schema path version
      (["context_id"; "context_version"; "payload_format"; "capabilities"; "compartments"; "resources"] @ extra) value in
  ignore (named path "context_id" fields); ignore (named path "context_version" fields);
  ignore (choice (child path "payload_format") ["DNA"; "RNA"] (field path "payload_format" fields));
  let capabilities = names (child path "capabilities") (field path "capabilities" fields)
  and compartments = names (child path "compartments") (field path "compartments" fields) in
  require ~path (compartments <> []) "invalid_target" "A target requires at least one compartment.";
  let resources_path = child path "resources" in
  let resources = object_at resources_path (field path "resources" fields) |> List.map (fun (key, value) ->
      let path = child resources_path key in
      ignore (Json.name ~path (Json.String key));
      let dtype = Type_spec.of_json ~path:(child path "type") (field path "type" (object_at path value)) in
      require ~path (Type_spec.kind dtype = Type_spec.Scalar) "invalid_resource" "Target resource assumptions require scalar literals.";
      let normalized = Type_spec.normalize_binding ~path ~expected:dtype value in
      require ~path (Json.number_compare (field path "canonical_value" (Json.object_fields normalized)) (Json.int 0) >= 0)
        "invalid_resource" "Target resource assumptions must be nonnegative.";
      key, normalized) in
  let fields = fields |> replace "capabilities" (string_array capabilities)
    |> replace "compartments" (string_array compartments) |> replace "resources" (Json.Object resources) in
  let fields = match kind with
    | Legacy_target -> fields
    | Human_target ->
        require ~path (not (List.mem "abstract" compartments)) "invalid_human_target" "Human targets require explicit physical compartments.";
        replace "human_target" (human_contract (child path "human_target") ~compartments (field path "human_target" fields)) fields in
  kind, Json.Object fields

module Target = struct
  type t = target_kind * Json.t
  let of_json ?(path = "") value = decode_target path value
  let to_json = snd
  let kind = fst
  let fingerprint value = Canonical.fingerprint (to_json value)
end

let decode_provenance path value =
  let fields = schema path "biocompiler.elaboration_provenance.v0.1"
      ["source_identities"; "dependency_identities"; "external_inputs"; "locations"; "recorded_at"] value in
  List.iter (fun key ->
      let path = child path key in
      let mapping = object_at path (Json.field key fields) in
      if key <> "external_inputs" then List.iter (fun (key, value) ->
          ignore (Json.name ~path (Json.String key)); ignore (Json.name ~path:(child path key) value)) mapping)
    ["source_identities"; "dependency_identities"; "external_inputs"; "locations"];
  (match field path "recorded_at" fields with Json.Null -> () | value -> ignore (Json.name ~path:(child path "recorded_at") value));
  value

let decode_metadata path value =
  let fields = schema path "biocompiler.binding_metadata.v0.1" ["category"; "provenance"; "allowed_variation"] value in
  let category = match choice (child path "category") ["user_selected"; "compiler_selected"; "measured"; "uncertain"] (field path "category" fields) with
    | "user_selected" -> User_selected | "compiler_selected" -> Compiler_selected | "measured" -> Measured | _ -> Uncertain in
  let binding_provenance = object_at (child path "provenance") (field path "provenance" fields) in
  let allowed_variation = match field path "allowed_variation" fields with
    | Json.Null -> None
    | value ->
        let path = child path "allowed_variation" in
        let dtype = Type_spec.of_json ~path:(child path "type") (field path "type" (object_at path value)) in
        require ~path (Type_spec.kind dtype = Type_spec.Interval) "invalid_allowed_variation" "Allowed variation must be a typed scalar interval.";
        Type_spec.validate_binding ~path ~expected:dtype value;
        Some value in
  {category; binding_provenance; allowed_variation; metadata_json = value}

let profile_string = function V1 -> "biocompiler.behavior.v0.1" | V2 -> "biocompiler.behavior.v0.2"
let scope_string = function Abstract_behavior -> "abstract_behavior" | Synthetic_realization -> "synthetic_realization" | Exact_cds -> "exact_cds" | Complete_payload -> "complete_payload"
let of_json value =
  (* Also reject non-JSON values built through this OCaml API, before they can
     be hidden by normalization, and bound nesting/encoding. *)
  ignore (Canonical.encode value);
  let fields = schema "" schema_version
      ["intent"; "explicit_overrides"; "resolved_defaults"; "resolved_bindings"; "target";
       "artifact_scope"; "behavior_profile"; "implementation_constraints"; "preferences";
       "parameter_metadata"; "provenance"] value in
  let source = Intent.of_json (field "" "intent" fields) in
  let profile = match Json.string ~path:"/behavior_profile" (field "" "behavior_profile" fields) with
    | "biocompiler.behavior.v0.1" -> V1 | "biocompiler.behavior.v0.2" -> V2
    | _ -> fail ~path:"/behavior_profile" "unsupported_behavior_profile" "Unsupported source behavior profile." in
  let scope = match Json.string ~path:"/artifact_scope" (field "" "artifact_scope" fields) with
    | "abstract_behavior" -> Abstract_behavior | "synthetic_realization" -> Synthetic_realization
    | "exact_cds" -> Exact_cds | "complete_payload" -> Complete_payload
    | _ -> fail ~path:"/artifact_scope" "unsupported_artifact_scope" "Unsupported source artifact scope." in
  let target_declaration = match field "" "target" fields with Json.Null -> None | value -> Some (decode_target "/target" value) in
  require ~path:"/target" (scope = Abstract_behavior || Option.is_some target_declaration)
    "missing_target" "This artifact scope requires an explicit target context.";
  let mapping key = object_at (child "" key) (field "" key fields) in
  let overrides = mapping "explicit_overrides" and defaults = mapping "resolved_defaults"
  and bindings = mapping "resolved_bindings" and constraints = mapping "implementation_constraints"
  and preferred = mapping "preferences" and raw_metadata = mapping "parameter_metadata" in
  require ~path:"/parameter_metadata" (Names.equal (keys raw_metadata) (keys bindings))
    "parameter_metadata_coverage" "Serialized metadata must cover every resolved design parameter exactly.";
  let nodes = Json.array (Json.field "nodes" (Json.object_fields (Intent.to_json source))) in
  let declarations = List.filter_map (fun node ->
      let fields = Json.object_fields node in
      if Json.string (Json.field "kind" fields) <> "parameter" then None else
      let attrs = Json.object_fields (Json.field "attributes" fields) in
      Some (Json.string (Json.field "name" attrs), (fields, attrs))) nodes in
  require ~path:"/explicit_overrides" (Names.subset (keys overrides) (keys declarations))
    "unknown_parameter" "Explicit overrides refer to undeclared design parameters.";
  let overrides_by_name = indexed overrides in
  let calculated_overrides, calculated_defaults, calculated_bindings = List.fold_left
      (fun (overrides_out, defaults_out, bindings_out) (key, (node, attrs)) ->
        match Bindings.find_opt key overrides_by_name with
        | Some value ->
            let path = child "/explicit_overrides" key in
            let dtype = Type_spec.of_json ~path (Json.field "data_type" node) in
            let normalized = Type_spec.normalize_binding ~path ~expected:dtype value in
            (key, normalized) :: overrides_out, defaults_out, (key, normalized) :: bindings_out
        | None ->
            require ~path:(child "/resolved_bindings" key) (Json.boolean (Json.field "bound" attrs))
              "unbound_parameter" "A design parameter must be bound before freezing a build request.";
            (* Frozen source defaults retain their original JSON representation,
               including valid numeric spelling and optional TypeSpec fields. *)
            let default = Json.field "default" attrs in
            overrides_out, (key, default) :: defaults_out, (key, default) :: bindings_out)
      ([], [], []) declarations in
  let same left right = Canonical.fingerprint (Json.Object left) = Canonical.fingerprint (Json.Object right) in
  require ~path:"/explicit_overrides" (same overrides calculated_overrides)
    "noncanonical_override" "Explicit binding encoding disagrees with decoded canonical bindings.";
  require ~path:"/resolved_defaults" (same defaults calculated_defaults)
    "resolved_defaults_mismatch" "Resolved defaults disagree with the frozen intent.";
  require ~path:"/resolved_bindings" (same bindings calculated_bindings)
    "resolved_bindings_mismatch" "Resolved bindings disagree with independent defaults and overrides.";
  let metadata_by_name = indexed raw_metadata and bindings_by_name = indexed bindings in
  let metadata = List.map (fun (key, (node, _)) ->
      let path = child "/parameter_metadata" key in
      let item = decode_metadata path (lookup "/parameter_metadata" key metadata_by_name) in
      (match item.allowed_variation with
       | None -> ()
       | Some variation ->
           let dtype = Type_spec.of_json ~path (Json.field "data_type" node) in
           require ~path (Type_spec.kind dtype = Type_spec.Scalar) "invalid_allowed_variation"
             "Allowed variation requires a scalar design parameter.";
           let interval = Type_spec.of_json (Json.Object ["kind", Json.String "interval"; "name", Json.String "AllowedVariation";
               "arguments", Json.Array [Type_spec.to_json dtype]]) in
           let normalized_variation = Type_spec.normalize_binding ~path ~expected:interval variation in
           let resolved = Type_spec.normalize_binding ~path ~expected:dtype (lookup "/resolved_bindings" key bindings_by_name) |> Json.object_fields in
           let variation_fields = Json.object_fields normalized_variation in
           let canonical key = Json.field "canonical_value" (Json.object_fields (Json.field key variation_fields)) in
           let value = Json.field "canonical_value" resolved in
           require ~path (Json.number_compare (canonical "lower") value <= 0 && Json.number_compare value (canonical "upper") <= 0)
             "value_outside_allowed_variation" "Frozen design binding lies outside its allowed variation.");
      key, item) declarations in
  let elaboration = decode_provenance "/provenance" (field "" "provenance" fields) in
  let observations = List.filter_map (fun node ->
      let fields = Json.object_fields node in
      if List.mem (Json.string (Json.field "kind" fields)) ["signal"; "channel_observation"]
      then Some (Identity.Node.of_string (Json.string (Json.field "id" fields))) else None) nodes in
  { source; profile; scope; target_declaration; overrides; defaults; bindings;
    constraints; preferred; metadata; elaboration; observations }

let document include_provenance value =
  let intent = Intent.to_json value.source in
  let intent = if include_provenance then intent else
      let fields = Json.object_fields intent in
      let nodes = Json.array (Json.field "nodes" fields) |> List.map (fun node ->
          Json.Object (List.remove_assoc "source" (Json.object_fields node))) in
      Json.Object (replace "nodes" (Json.Array nodes) fields) in
  let provenance = if include_provenance then value.elaboration else
      Json.Object (Json.object_fields value.elaboration |> List.remove_assoc "locations" |> List.remove_assoc "recorded_at") in
  Json.Object ["schema_version", Json.String schema_version; "intent", intent;
    "explicit_overrides", Json.Object value.overrides; "resolved_defaults", Json.Object value.defaults;
    "resolved_bindings", Json.Object value.bindings;
    "target", (match value.target_declaration with None -> Json.Null | Some (_, value) -> value);
    "artifact_scope", Json.String (scope_string value.scope); "behavior_profile", Json.String (profile_string value.profile);
    "implementation_constraints", Json.Object value.constraints; "preferences", Json.Object value.preferred;
    "parameter_metadata", Json.Object (List.map (fun (key, value) -> key, value.metadata_json) value.metadata);
    "provenance", provenance]

let to_json value = document true value
let semantic_json value = document false value
let fingerprint value = Canonical.fingerprint (semantic_json value)
let artifact_fingerprint value = Canonical.fingerprint (to_json value)
let intent value = value.source
let behavior_profile value = value.profile
let artifact_scope value = value.scope
let target_kind value = Option.map fst value.target_declaration
let target value = Option.map snd value.target_declaration
let explicit_overrides value = value.overrides
let resolved_defaults value = value.defaults
let resolved_bindings value = value.bindings
let implementation_constraints value = value.constraints
let preferences value = value.preferred
let provenance value = value.elaboration
let parameter_metadata value = value.metadata
let metadata_category value = value.category
let metadata_provenance value = value.binding_provenance
let metadata_allowed_variation value = value.allowed_variation
let runtime_observations value = value.observations
let unimplemented_obligations value =
  ["source_behavior_execution"; "source_to_candidate_preservation"; "candidate_acceptance"]
  @ (if value.constraints = [] then [] else ["implementation_constraint_enforcement"])
  @ (if value.preferred = [] then [] else ["preference_evaluation"])
  @ (if Option.is_none value.target_declaration then [] else ["target_assumption_validation"; "biological_evidence_admission"])
let summary value = Json.Object [
    "schema_version", Json.String schema_version; "validation_scope", Json.String validation_scope;
    "fingerprint", Json.String (fingerprint value); "artifact_fingerprint", Json.String (artifact_fingerprint value);
    "artifact_scope", Json.String (scope_string value.scope); "behavior_profile", Json.String (profile_string value.profile);
    "parameter_count", Json.int (List.length value.bindings);
    "runtime_observations", string_array (List.map Identity.Node.to_string value.observations);
    "unimplemented_obligations", string_array (unimplemented_obligations value)]

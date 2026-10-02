open Bioc_wire
module M = Molecular_record
module I = Architecture_contract.Instance
let require ?path condition message = Diagnostic.require ?path condition "invalid_architecture_build" message
let str value = Json.String value
let obj value = Json.Object value
(* Match the import tree's conservative size measure before accumulating child
   representations. Pretty-printed publication has a separate byte contract. *)
let rec tree_size = function
  | Json.Object fields -> 2 + 2 * List.length fields + List.fold_left (fun n (key,value) -> n + String.length key + 2 + tree_size value) 0 fields
  | Json.Array values -> 2 + List.length values + List.fold_left (fun n value -> n + tree_size value) 0 values
  | Json.String value -> String.length value + 2
  | Json.Int value -> String.length (Z.to_string value)
  | Json.Float value -> String.length (Canonical.float_string value)
  | Json.Null | Json.Bool _ -> 5
let array maximum encode values =
  ignore (M.bounded_length ~maximum values);
  let bytes = ref 2 in
  let converted = List.map (fun value ->
      let raw = encode value in M.bounded_tree raw;
      bytes := !bytes + tree_size raw + 1;
      Diagnostic.require (!bytes <= M.max_json_bytes) "molecular_resource_limit" "Architecture inventory exceeds its cumulative byte bound.";
      raw) values in
  let raw = Json.Array converted in M.bounded_tree raw; raw
let strings maximum values = array maximum str values
let names ~path ?(maximum=4096) ?(nonempty=false) raw =
  let values = M.array ~path ~maximum raw |> List.map (M.text ~path) in
  let sorted = List.sort_uniq String.compare values in
  require ~path (List.length values = List.length sorted && (not nonempty || values <> [])) "Architecture names must be unique and meet inventory bounds.";
  sorted
let records ~path ~maximum decode raw =
  M.array ~path ~maximum raw |> List.mapi (fun i -> decode ?path:(Some (path ^ "/" ^ string_of_int i)))
let objects ~path raw =
  M.array ~path ~maximum:4096 raw |> List.map (fun raw -> ignore (Json.object_fields ~path raw); raw)
let distinct ~path identity values =
  let ids = List.map identity values in
  require ~path (List.length ids = List.length (List.sort_uniq String.compare ids)) "Duplicate architecture record identity."
let instances ~path raw =
  let values = records ~path ~maximum:256 I.of_json raw in
  distinct ~path I.id values;
  List.sort (fun a b -> String.compare (I.id a) (I.id b)) values
let optional encode = function None -> Json.Null | Some value -> encode value
let nullable decode ~path = function Json.Null -> None | raw -> Some (decode ?path:(Some path) raw)
let hash ~path raw =
  let value = Json.string ~path raw in
  require ~path (String.length value = 64 && String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) value) "Expected lowercase SHA-256 architecture identity.";
  value
let finish ~path raw value = M.bounded_tree ~path raw; value

module Gap = struct
type category = Unsupported_semantics | Missing_implementation | Incompatible_composition
  | Contradictory_requirements | Missing_sequence_authority | Search_budget_exhausted | Independent_verification_failure
let category_name = function Unsupported_semantics -> "unsupported_semantics" | Missing_implementation -> "missing_implementation"
  | Incompatible_composition -> "incompatible_composition" | Contradictory_requirements -> "contradictory_requirements"
  | Missing_sequence_authority -> "missing_sequence_authority" | Search_budget_exhausted -> "search_budget_exhausted"
  | Independent_verification_failure -> "independent_verification_failure"
type t = {category:category; code:string; requirement_ids:string list; candidate_ids:string list; message:string; conflict_set:string list}
let schema_version = "biocompiler.architecture_gap.v0.1"
let to_json (value:t) = obj ["schema_version",str schema_version;
    "category",(str (category_name value.category));
    "code",(str value.code);
    "requirement_ids",(strings 4096 value.requirement_ids);
    "candidate_ids",(strings 4096 value.candidate_ids);
    "message",(str value.message);
    "conflict_set",(strings 4096 value.conflict_set)]
let of_json ?(path="") raw =
  let fields = M.record ~path schema_version ["category";"code";"requirement_ids";"candidate_ids";"message";"conflict_set"] raw in
  let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
  let category = let path = path ^ "/category" in (match Json.string ~path (get "category") with "unsupported_semantics" -> Unsupported_semantics | "missing_implementation" -> Missing_implementation | "incompatible_composition" -> Incompatible_composition | "contradictory_requirements" -> Contradictory_requirements | "missing_sequence_authority" -> Missing_sequence_authority | "search_budget_exhausted" -> Search_budget_exhausted | "independent_verification_failure" -> Independent_verification_failure | _ -> Diagnostic.fail ~path "invalid_architecture_build" "Unknown architecture gap category.") in
  let code = let path = path ^ "/code" in M.text ~path (get "code") in
  let requirement_ids = let path = path ^ "/requirement_ids" in names ~path (get "requirement_ids") in
  let candidate_ids = let path = path ^ "/candidate_ids" in names ~path (get "candidate_ids") in
  let message = let path = path ^ "/message" in M.text ~path (get "message") in
  let conflict_set = let path = path ^ "/conflict_set" in names ~path (get "conflict_set") in
  let value = {category;code;requirement_ids;candidate_ids;message;conflict_set} in finish ~path (to_json value) value
let make ~category ~code ~requirement_ids ~candidate_ids ~message ~conflict_set = of_json (to_json {category;code;requirement_ids;candidate_ids;message;conflict_set})
let fingerprint value = Canonical.fingerprint (to_json value)
let category (value:t) = value.category
let code (value:t) = value.code
let requirement_ids (value:t) = value.requirement_ids
let candidate_ids (value:t) = value.candidate_ids
let message (value:t) = value.message
let conflict_set (value:t) = value.conflict_set
end

module Requirement_realization = struct
type status = Implemented | Unresolved
let status_name = function Implemented -> "implemented" | Unresolved -> "unresolved"
type t = {id:string; source_node_ids:string list; refinement_ids:string list; status:status; assumptions:string list; reasons:string list}
let schema_version = "biocompiler.requirement_realization.v0.1"
let to_json (value:t) = obj ["schema_version",str schema_version;
    "id",(str value.id);
    "source_node_ids",(strings 4096 value.source_node_ids);
    "refinement_ids",(strings 4096 value.refinement_ids);
    "status",(str (status_name value.status));
    "assumptions",(strings 4096 value.assumptions);
    "reasons",(strings 4096 value.reasons)]
let of_json ?(path="") raw =
  let fields = M.record ~path schema_version ["id";"source_node_ids";"refinement_ids";"status";"assumptions";"reasons"] raw in
  let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
  let id = let path = path ^ "/id" in M.text ~path (get "id") in
  let source_node_ids = let path = path ^ "/source_node_ids" in names ~path (get "source_node_ids") in
  let refinement_ids = let path = path ^ "/refinement_ids" in names ~path (get "refinement_ids") in
  let status = let path = path ^ "/status" in (match Json.string ~path (get "status") with "implemented" -> Implemented | "unresolved" -> Unresolved | _ -> Diagnostic.fail ~path "invalid_architecture_build" "Unknown requirement realization status.") in
  let assumptions = let path = path ^ "/assumptions" in names ~path (get "assumptions") in
  let reasons = let path = path ^ "/reasons" in names ~path (get "reasons") in
  require ~path (status <> Implemented || refinement_ids <> []) "Implemented source requirements need supplied realizations.";
  let value = {id;source_node_ids;refinement_ids;status;assumptions;reasons} in finish ~path (to_json value) value
let make ~id ~source_node_ids ~refinement_ids ~status ~assumptions ~reasons = of_json (to_json {id;source_node_ids;refinement_ids;status;assumptions;reasons})
let fingerprint value = Canonical.fingerprint (to_json value)
let id (value:t) = value.id
let source_node_ids (value:t) = value.source_node_ids
let refinement_ids (value:t) = value.refinement_ids
let status (value:t) = value.status
let assumptions (value:t) = value.assumptions
let reasons (value:t) = value.reasons
end

module Plan = struct
type t = {selected_refinement_ids:string list; ledger:Requirement_realization.t list; placements:Json.t list; helpers:Json.t list; channels:Json.t list; control_domains:Json.t list; assumptions:string list; instances:I.t list; availability:Json.t list}
let schema_version = "biocompiler.payload_architecture_plan.v0.2"
let to_json (value:t) = obj ["schema_version",str schema_version;
    "selected_refinement_ids",(strings 256 value.selected_refinement_ids);
    "ledger",(array 8192 Requirement_realization.to_json value.ledger);
    "placements",(array 4096 Fun.id value.placements);
    "helpers",(array 4096 Fun.id value.helpers);
    "channels",(array 4096 Fun.id value.channels);
    "control_domains",(array 4096 Fun.id value.control_domains);
    "assumptions",(strings 4096 value.assumptions);
    "instances",(array 256 I.to_json value.instances);
    "availability",(array 4096 Fun.id value.availability)]
let of_json ?(path="") raw =
  let fields = M.record ~path schema_version ["selected_refinement_ids";"ledger";"placements";"helpers";"channels";"control_domains";"assumptions";"instances";"availability"] raw in
  let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
  let selected_refinement_ids = let path = path ^ "/selected_refinement_ids" in names ~path ~maximum:256 ~nonempty:true (get "selected_refinement_ids") in
  let ledger = let path = path ^ "/ledger" in records ~path ~maximum:8192 Requirement_realization.of_json (get "ledger") in
  let placements = let path = path ^ "/placements" in objects ~path (get "placements") in
  let helpers = let path = path ^ "/helpers" in objects ~path (get "helpers") in
  let channels = let path = path ^ "/channels" in objects ~path (get "channels") in
  let control_domains = let path = path ^ "/control_domains" in objects ~path (get "control_domains") in
  let assumptions = let path = path ^ "/assumptions" in names ~path (get "assumptions") in
  let instances = let path = path ^ "/instances" in instances ~path (get "instances") in
  let availability = let path = path ^ "/availability" in objects ~path (get "availability") in
  distinct ~path Requirement_realization.id ledger;
  require ~path (instances = [] || List.map I.id instances = selected_refinement_ids) "Selected architecture instances and refinement identities disagree.";
  let value = {selected_refinement_ids;ledger;placements;helpers;channels;control_domains;assumptions;instances;availability} in finish ~path (to_json value) value
let make ~selected_refinement_ids ~ledger ~placements ~helpers ~channels ~control_domains ~assumptions ~instances ~availability = of_json (to_json {selected_refinement_ids;ledger;placements;helpers;channels;control_domains;assumptions;instances;availability})
let fingerprint value = Canonical.fingerprint (to_json value)
let selected_refinement_ids (value:t) = value.selected_refinement_ids
let ledger (value:t) = value.ledger
let placements (value:t) = value.placements
let helpers (value:t) = value.helpers
let channels (value:t) = value.channels
let control_domains (value:t) = value.control_domains
let assumptions (value:t) = value.assumptions
let instances (value:t) = value.instances
let availability (value:t) = value.availability
end

module Alternative = struct
type t = {refinement_ids:string list; gaps:Gap.t list}
let schema_version = "biocompiler.architecture_alternative.v0.1"
let to_json (value:t) = obj ["schema_version",str schema_version;
    "refinement_ids",(strings 4096 value.refinement_ids);
    "gaps",(array 4096 Gap.to_json value.gaps)]
let of_json ?(path="") raw =
  let fields = M.record ~path schema_version ["refinement_ids";"gaps"] raw in
  let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
  let refinement_ids = let path = path ^ "/refinement_ids" in names ~path (get "refinement_ids") in
  let gaps = let path = path ^ "/gaps" in records ~path ~maximum:4096 Gap.of_json (get "gaps") in
  let value = {refinement_ids;gaps} in finish ~path (to_json value) value
let make ~refinement_ids ~gaps = of_json (to_json {refinement_ids;gaps})
let fingerprint value = Canonical.fingerprint (to_json value)
let refinement_ids (value:t) = value.refinement_ids
let gaps (value:t) = value.gaps
let eligible value = value.gaps = []
end

type status = Compiled | Partial | Unsupported | No_solution | Search_exhausted
let status_name = function Compiled -> "compiled" | Partial -> "partial" | Unsupported -> "unsupported" | No_solution -> "no_solution" | Search_exhausted -> "search_exhausted"
let max_alternatives = 4096 + 256
type t = {request_fingerprint:string; execution:Source_execution_manifest.t; plan:Plan.t option; construction:Construction_build.t option; alternatives:Alternative.t list; diagnostics:Gap.t list; status:status; match_instances:I.t list}
let schema_version = "biocompiler.payload_architecture_build.v0.2"
let to_json (value:t) = obj ["schema_version",str schema_version;
    "request_fingerprint",(str value.request_fingerprint);
    "execution",(Source_execution_manifest.to_json value.execution);
    "plan",(optional Plan.to_json value.plan);
    "construction",(optional Construction_build.to_json value.construction);
    "alternatives",(array max_alternatives Alternative.to_json value.alternatives);
    "diagnostics",(array 4096 Gap.to_json value.diagnostics);
    "status",(str (status_name value.status));
    "match_instances",(array 256 I.to_json value.match_instances)]
let of_json ?(path="") raw =
  let fields = M.record ~path schema_version ["request_fingerprint";"execution";"plan";"construction";"alternatives";"diagnostics";"status";"match_instances"] raw in
  let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
  let request_fingerprint = let path = path ^ "/request_fingerprint" in hash ~path (get "request_fingerprint") in
  let execution = let path = path ^ "/execution" in Source_execution_manifest.of_json ~path (get "execution") in
  let plan = let path = path ^ "/plan" in nullable Plan.of_json ~path (get "plan") in
  let construction = let path = path ^ "/construction" in nullable Construction_build.of_json ~path (get "construction") in
  let alternatives = let path = path ^ "/alternatives" in records ~path ~maximum:max_alternatives Alternative.of_json (get "alternatives") in
  let diagnostics = let path = path ^ "/diagnostics" in records ~path ~maximum:4096 Gap.of_json (get "diagnostics") in
  let status = let path = path ^ "/status" in (match Json.string ~path (get "status") with "compiled" -> Compiled | "partial" -> Partial | "unsupported" -> Unsupported | "no_solution" -> No_solution | "search_exhausted" -> Search_exhausted | _ -> Diagnostic.fail ~path "invalid_architecture_build" "Unknown architecture status.") in
  let match_instances = let path = path ^ "/match_instances" in instances ~path (get "match_instances") in
  require ~path ((status = Compiled || status = Partial) = (Option.is_some plan && Option.is_some construction)) "Architecture status and retained construction disagree.";
  let value = {request_fingerprint;execution;plan;construction;alternatives;diagnostics;status;match_instances} in finish ~path (to_json value) value
let make ~request_fingerprint ~execution ~plan ~construction ~alternatives ~diagnostics ~status ~match_instances = of_json (to_json {request_fingerprint;execution;plan;construction;alternatives;diagnostics;status;match_instances})
let fingerprint value = Canonical.fingerprint (to_json value)
let request_fingerprint (value:t) = value.request_fingerprint
let execution (value:t) = value.execution
let plan (value:t) = value.plan
let construction (value:t) = value.construction
let alternatives (value:t) = value.alternatives
let diagnostics (value:t) = value.diagnostics
let status (value:t) = value.status
let match_instances (value:t) = value.match_instances
let molecules value = match value.construction with None -> None | Some build -> Construction_artifact.bundle (Construction_build.candidate build)

module Export = struct
type t = {fasta:string; manifest:Json.t}
let schema_version = "biocompiler.payload_architecture_export.v0.1"
let to_json (value:t) = obj ["schema_version",str schema_version;
    "fasta",(str value.fasta);
    "manifest",(value.manifest)]
let of_json ?(path="") raw =
  let fields = M.record ~path schema_version ["fasta";"manifest"] raw in
  let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
  let fasta = let path = path ^ "/fasta" in Json.string ~path (get "fasta") in
  let manifest = let path = path ^ "/manifest" in (let value = (get "manifest") in ignore (Json.object_fields ~path value); value) in
  require ~path (String.length fasta > 0 && fasta.[0] = '>') "Export needs RNA FASTA.";
  let value = {fasta;manifest} in finish ~path (to_json value) value
let make ~fasta ~manifest = of_json (to_json {fasta;manifest})
let fingerprint value = Canonical.fingerprint (to_json value)
let fasta (value:t) = value.fasta
let manifest (value:t) = value.manifest
end

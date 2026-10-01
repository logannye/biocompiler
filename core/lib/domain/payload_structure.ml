open Bioc_wire
module M = Molecular_record
module G = Molecule_coordinates
let max_contracts = 64
let max_regions = 256
let profile = "biocompiler.declared_payload_structure.v0.1"
let claim = "correspondence_to_declared_payload_regions"
type form = Delivered_rna | Delivered_dna
let form_name = function Delivered_rna -> "delivered_rna" | Delivered_dna -> "delivered_dna"
let alphabet = function Delivered_rna -> G.Rna | Delivered_dna -> G.Dna
let string value = Json.String value
let child path name = path ^ "/" ^ name
let check ?path condition message = Diagnostic.require ?path condition "invalid_payload_structure" message
let finish ~path value result = M.check_resources ~path value; result

module Region = struct
  type t = { feature_id : string; kind : string }
  let schema_version = "biocompiler.required_payload_region.v0.1"
  let to_json value = Json.Object ["schema_version", string schema_version;
      "feature_id", string value.feature_id; "kind", string value.kind]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["feature_id"; "kind"] value in
    let text key = M.text ~path:(child path key) (Json.field key fields) in
    let result = { feature_id = text "feature_id"; kind = text "kind" } in
    finish ~path (to_json result) result
  let make ~feature_id ~kind = of_json (to_json { feature_id; kind })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let feature_id value = value.feature_id
  let kind value = value.kind
end

type t = { member_id : string; form : form; topology : G.topology;
           regions : Region.t list; provenance : M.Provenance.t }
let schema_version = "biocompiler.payload_structure_contract.v0.1"
let topology_name = function G.Linear -> "linear" | G.Circular -> "circular"
let to_json value =
  ignore (M.bounded_length ~maximum:max_regions value.regions);
  Json.Object ["schema_version", string schema_version;
    "member_id", string value.member_id; "form", string (form_name value.form);
    "topology", string (topology_name value.topology);
    "regions", Json.Array (List.map Region.to_json value.regions);
    "provenance", M.Provenance.to_json value.provenance]
let of_json ?(path = "") value =
  let fields = M.record ~path schema_version ["member_id"; "form"; "topology"; "regions"; "provenance"] value in
  let get key = Json.field ~path:(child path key) key fields in
  let form = match Json.string ~path:(child path "form") (get "form") with
    | "delivered_rna" -> Delivered_rna | "delivered_dna" -> Delivered_dna
    | _ -> Diagnostic.fail ~path:(child path "form") "invalid_payload_structure" "Unsupported final delivered payload form." in
  let topology = match Json.string ~path:(child path "topology") (get "topology") with
    | "linear" -> G.Linear | "circular" -> G.Circular
    | _ -> Diagnostic.fail ~path:(child path "topology") "invalid_payload_structure" "Unsupported final delivered payload topology." in
  let raw_regions = M.array ~path:(child path "regions") ~maximum:max_regions (get "regions") in
  let regions = List.mapi (fun i raw -> Region.of_json ~path:(child (child path "regions") (string_of_int i)) raw) raw_regions in
  check ~path:(child path "regions") (regions <> []) "Required payload regions must be nonempty.";
  let regions = List.sort (fun left right -> String.compare (Region.feature_id left) (Region.feature_id right)) regions in
  let ids = List.map Region.feature_id regions in
  check ~path:(child path "regions") (List.length ids = List.length (List.sort_uniq String.compare ids))
    "Required payload feature identities must be unique.";
  let result = { member_id = M.text ~path:(child path "member_id") (get "member_id"); form; topology; regions;
    provenance = M.Provenance.of_json ~path:(child path "provenance") (get "provenance") } in
  finish ~path (to_json result) result
let make ~member_id ~form ~topology ~regions ~provenance =
  of_json (to_json { member_id; form; topology; regions; provenance })
let fingerprint value = Canonical.fingerprint (to_json value)
let member_id value = value.member_id
let form value = value.form
let topology value = value.topology
let regions value = value.regions
let provenance value = value.provenance

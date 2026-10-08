open Bioc_wire
module R = Policy_component_selection_request
module C = Policy_component_material_candidate
module Child = Policy_component_material_request
module Original = Policy_realization_request
module Input = Policy_material_request
module Names = Set.Make (String)

let schema_version = "biocompiler.policy_component_selection_candidate.v0.1"
let require condition message =
  Diagnostic.require condition "policy_component_selection_candidate" message
let get key raw = Json.field key (Json.object_fields raw)
let exact keys raw = Json.exact_fields keys (Json.object_fields raw)
type alternative = { id:string; candidate:C.t }
type t = {
  raw:Json.t; identity:string; original_identity:string; work:int;
  rows:alternative list; ordered:alternative list; proposed:string option;
}

let of_json ?(charge=fun _ -> ()) ~request raw =
  let work = ref 0 in
  let spend amount =
    Diagnostic.require (amount >= 0 && amount <= max_int - !work)
      "policy_component_selection_candidate_work_limit" "Candidate decoding work counter overflow.";
    charge amount; work := !work + amount in
  let raw_bytes = Input.preflight ~max_bytes:R.max_input_bytes ~max_nodes:R.max_input_nodes
    ~max_depth:R.max_input_depth ~charge:spend raw in
  exact ["schema_version"; "alternatives"; "selected_id"] raw;
  require (get "schema_version" raw = Json.String schema_version)
    "Unsupported complete component selection candidate schema.";
  let originals = R.alternatives request in
  let original id =
    let found = List.find_opt (fun (row:R.alternative) ->
      spend (1 + String.length id + String.length row.id); row.id = id) originals in
    match found with Some value -> value | None ->
      Diagnostic.fail "policy_component_selection_candidate"
        "Candidate ID is absent from the complete original alternative census." in
  let raw_rows = Json.array (get "alternatives" raw) in
  let rec count total = function
    | [] -> total
    | _ :: tail ->
        require (total < R.max_alternatives) "Candidate census exceeds the original profile bound.";
        spend 1; count (total + 1) tail in
  require (count 0 raw_rows = List.length originals)
    "Candidate census must include every original alternative exactly once.";
  let seen = ref Names.empty in
  let rows = List.map (fun row ->
    exact ["id"; "candidate"] row;
    let id = Json.string (get "id" row) in
    let supplied = original id in
    require (not (Names.mem id !seen)) "Duplicate candidate alternative ID.";
    seen := Names.add id !seen;
    let library = Original.implementation_library (Child.implementation_request supplied.request) in
    let candidate = C.of_json ~charge:spend ~library (get "candidate" row) in
    {id; candidate}) raw_rows in
  let proposed = match get "selected_id" raw with
    | Json.Null -> None
    | value -> let id = Json.string value in ignore (original id); Some id in
  let ordered = List.sort (fun (left:alternative) (right:alternative) ->
    spend (1 + String.length left.id + String.length right.id);
    String.compare left.id right.id) rows in
  spend raw_bytes;
  let encoded = Canonical.encode_bounded ~max_bytes:R.max_input_bytes raw in
  Diagnostic.require (String.length encoded = raw_bytes) "policy_component_selection_candidate_accounting"
    "Candidate preflight byte count differs from the complete encoding.";
  spend raw_bytes;
  {raw; identity=Canonical.sha256 encoded; original_identity=R.fingerprint request;
   work= !work; rows; ordered; proposed}

let to_json value = value.raw
let fingerprint value = value.identity
let request_fingerprint value = value.original_identity
let decoding_work value = value.work
let alternatives value = value.rows
let evaluation_order value = value.ordered
let selected_id value = value.proposed

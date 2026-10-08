open Bioc_wire
module R = Policy_component_material_request
module Input = Policy_material_request
module M = Molecular_record
module Names = Set.Make (String)

let schema_version = "biocompiler.policy_component_selection_request.v0.1"
let profile = "biocompiler.policy_component_material_selection.v0.1"
let resource_profile = "biocompiler.policy_component_selection_resources.v0.1"
let publication_resource_profile = "biocompiler.policy_component_selection_resources.v0.2"
let resource_profiles = [resource_profile;publication_resource_profile]
let max_alternatives = 16
let max_input_bytes = 8 * 1024 * 1024
let max_input_nodes = 250_000
let max_input_depth = 128
let max_work = Z.of_string "17000000000"
let max_rank = Z.of_string "2147483647"
let max_report_bytes = Limits.max_response_bytes - 6 * Limits.max_string_bytes - 65536
let max_report_nodes = Limits.max_json_nodes - 32
let max_publication_nodes = 1_000_000
let str value = Json.String value
let get key raw = Json.field key (Json.object_fields raw)
let exact keys raw = Json.exact_fields keys (Json.object_fields raw)
let require condition message = Diagnostic.require condition "policy_component_selection_request" message

type alternative = { id:string; rank:int; request:R.t }
type predicate = { max_total_nt:int }
type budgets = { max_work:int; max_report_bytes:int; max_report_nodes:int }
type t = {
  raw:Json.t; identity:string; decoding_work_value:int;
  alternatives_value:alternative list; ordered:alternative list;
  predicate_value:predicate; budget_values:budgets; resource_profile_value:string;
}

let bounded_integer ~minimum ~maximum raw =
  let value = Json.integer raw in
  require (Z.geq value (Z.of_int minimum) && Z.leq value maximum &&
    Z.leq value (Z.of_int max_int))
    "Selection integer is outside its closed bound or this platform's integer range.";
  Z.to_int value

let identifier raw =
  let value = Json.string raw in
  let alphanumeric = function 'A'..'Z' | 'a'..'z' | '0'..'9' -> true | _ -> false in
  require (String.length value >= 1 && String.length value <= 128 &&
    alphanumeric value.[0] && String.for_all (fun character ->
      alphanumeric character || character = '.' || character = '_' || character = '-') value)
    "Selection alternative ID must be 1..128 ASCII bytes matching [A-Za-z0-9][A-Za-z0-9._-]*.";
  value

let of_json ?(charge=fun _ -> ()) raw =
  let work = ref 0 in
  let spend amount =
    Diagnostic.require (amount >= 0 && amount <= max_int - !work)
      "policy_component_selection_work_limit" "Selection decoding work counter overflow.";
    charge amount; work := !work + amount in
  let raw_bytes = Input.preflight ~max_bytes:max_input_bytes ~max_nodes:max_input_nodes
    ~max_depth:max_input_depth ~charge:spend raw in
  exact ["schema_version"; "profile"; "alternatives"; "predicate"; "budgets"] raw;
  require (get "schema_version" raw = str schema_version && get "profile" raw = str profile)
    "Unsupported original component selection request profile.";
  let rows = Json.array (get "alternatives" raw) in
  let rec count_rows count = function
    | [] -> require (count > 0) "Selection requires a nonempty complete original alternative census."
    | _ :: tail ->
        require (count < max_alternatives) "Selection alternative census exceeds its closed bound.";
        spend 1; count_rows (count + 1) tail in
  count_rows 0 rows;
  let seen = ref Names.empty in
  let alternatives_value = List.map (fun row ->
    exact ["id"; "rank"; "request"] row;
    let id = identifier (get "id" row) in
    require (not (Names.mem id !seen)) "Selection alternative IDs must be unique.";
    seen := Names.add id !seen;
    let rank = bounded_integer ~minimum:0 ~maximum:max_rank (get "rank" row) in
    let request = R.of_json ~charge:spend (get "request" row) in
    {id; rank; request}) rows in
  let predicate_raw = get "predicate" raw in
  exact ["max_total_nt"] predicate_raw;
  let predicate_value = {max_total_nt=bounded_integer ~minimum:0
    ~maximum:(Z.of_int M.max_residues) (get "max_total_nt" predicate_raw)} in
  let budget_raw = get "budgets" raw in
  exact ["profile"; "max_work"; "max_report_bytes"; "max_report_nodes"] budget_raw;
  let resource_raw=get "profile" budget_raw in
  require (List.exists (fun name -> resource_raw=str name) resource_profiles)
    "Unsupported component selection resource profile.";
  let resource_profile_value=Json.string resource_raw in
  let node_ceiling=if resource_profile_value=resource_profile then max_report_nodes
    else max_publication_nodes in
  let budget_values = {
    max_work=bounded_integer ~minimum:1 ~maximum:max_work (get "max_work" budget_raw);
    max_report_bytes=bounded_integer ~minimum:1 ~maximum:(Z.of_int max_report_bytes)
      (get "max_report_bytes" budget_raw);
    max_report_nodes=bounded_integer ~minimum:1 ~maximum:(Z.of_int node_ceiling)
      (get "max_report_nodes" budget_raw)} in
  let ordered = List.sort (fun (left:alternative) (right:alternative) ->
    spend (1 + String.length left.id + String.length right.id);
    String.compare left.id right.id) alternatives_value in
  spend raw_bytes;
  let encoded = Canonical.encode_bounded ~max_bytes:max_input_bytes raw in
  Diagnostic.require (String.length encoded = raw_bytes) "policy_component_selection_accounting"
    "Selection preflight byte count differs from the complete original encoding.";
  spend raw_bytes;
  {raw; identity=Canonical.sha256 encoded; decoding_work_value= !work;
   alternatives_value; ordered; predicate_value; budget_values; resource_profile_value}

let to_json value = value.raw
let fingerprint value = value.identity
let decoding_work value = value.decoding_work_value
let alternatives value = value.alternatives_value
let evaluation_order value = value.ordered
let anchor value = List.hd value.ordered
let predicate value = value.predicate_value
let budgets value = value.budget_values

let resources value = value.resource_profile_value

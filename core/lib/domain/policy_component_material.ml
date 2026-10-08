open Bioc_wire
module F = Policy_component_fragment
module MC = Policy_material_contract
module I = Policy_implementation
module M = Molecular_record
module N = Molecule
module G = Molecule_coordinates
module H = Molecule_chemistry
module R = Molecular_recoding
module PM = Policy_mrna_structure
module Pin = Pinned_identity
module Names = Set.Make (String)

let schema_version = "biocompiler.policy_component_material.v0.1"
let profile = "biocompiler.policy_exact_local_material.v0.1"
let max_carriers = 32768
let max_provider_requirements = 1024

type target = Primitive of string | Configuration of string | Replication of string
  | Local_wire of int | External_slot of string | Boundary_port of string
  | Atomic_group of string | Semantic_export of int | Slot_layout
type site = { root_id:string; feature_id:string; path:G.Path.t }
type carrier = { target:target; sites:site list }
type product = { node_id:string; symbol:string; root_id:string; cds_feature:string; expected:PM.product }
type owner = Node of string | External_slot_owner of string
type provider_requirement =
  | Input of { id:string; external_slot:string }
  | Capacity of { id:string; owner:owner; unit:MC.resource_unit; scope:MC.resource_scope; minimum:int }
type t = {
  identity_value:Pin.t; fragment_value:F.t; root_value:Construction.Root_source.t;
  carrier_values:carrier list; product_values:product list;
  requirement_values:provider_requirement list;
}

let str value = Json.String value
let obj values = Json.Object values
let arr values = Json.Array values
let get key value = Json.field key (Json.object_fields value)
let exact keys value = Json.exact_fields keys (Json.object_fields value)
let require condition message = Diagnostic.require condition "policy_component_material" message
let equal a b = Canonical.encode a = Canonical.encode b
let name ?(maximum=128) value =
  let value = Json.name value in
  require (String.length value <= maximum) "Local material identifier exceeds its byte bound.";
  value
let integer maximum value = M.index ~maximum value
let unique label values =
  ignore (List.fold_left (fun seen value ->
    require (not (Names.mem value seen)) ("Duplicate local material " ^ label ^ " identity.");
    Names.add value seen) Names.empty values)
let preflight raw =
  M.check_resources raw;
  let rec walk = function
    | Json.Float _ -> require false "Raw floats cannot enter a local material contract."
    | Json.Array values -> List.iter walk values
    | Json.Object fields -> List.iter (fun (_, value) -> walk value) fields
    | _ -> () in
  walk raw

let target_to_json = function
  | Primitive id -> obj ["kind",str "primitive";"id",str id]
  | Configuration id -> obj ["kind",str "configuration";"id",str id]
  | Replication id -> obj ["kind",str "replication";"id",str id]
  | Local_wire index -> obj ["kind",str "local_wire";"index",Json.int index]
  | External_slot id -> obj ["kind",str "external_slot";"id",str id]
  | Boundary_port id -> obj ["kind",str "boundary_port";"id",str id]
  | Atomic_group id -> obj ["kind",str "atomic_group";"id",str id]
  | Semantic_export index -> obj ["kind",str "semantic_export";"index",Json.int index]
  | Slot_layout -> obj ["kind",str "slot_layout"]
let target_of_json raw =
  let id () = exact ["kind";"id"] raw; name (get "id" raw) in
  let index () = exact ["kind";"index"] raw; integer 16383 (get "index" raw) in
  match Json.string (get "kind" raw) with
  | "primitive" -> Primitive (id ()) | "configuration" -> Configuration (id ())
  | "replication" -> Replication (id ()) | "local_wire" -> Local_wire (index ())
  | "external_slot" -> External_slot (id ()) | "boundary_port" -> Boundary_port (id ())
  | "atomic_group" -> Atomic_group (id ()) | "semantic_export" -> Semantic_export (index ())
  | "slot_layout" -> exact ["kind"] raw; Slot_layout
  | _ -> Diagnostic.fail "policy_component_material" "Unknown local material carrier target."
let target_inventory fragment =
  List.concat_map (fun (node:F.node) ->
    [Primitive node.node_id;Configuration node.node_id;Replication node.node_id]) (F.nodes fragment) @
  List.mapi (fun index _ -> Local_wire index) (F.wires fragment) @
  List.map (fun (slot:F.external_slot) -> External_slot slot.slot_id) (F.external_slots fragment) @
  List.map (fun (port:F.boundary_port) -> Boundary_port port.boundary_id) (F.boundary_ports fragment) @
  List.map (fun (group:I.atomic_group) -> Atomic_group group.group_id) (F.atomic_groups fragment) @
  List.mapi (fun index _ -> Semantic_export index) (F.semantic_exports fragment) @ [Slot_layout]
let site_json (value:site) = obj ["root",str value.root_id;"feature",str value.feature_id;"path",G.Path.to_json value.path]
let carrier_json (value:carrier) = obj ["target",target_to_json value.target;"sites",arr (List.map site_json value.sites)]
let expected_product_json (value:PM.product) = obj ["identity",Pin.to_json value.identity;
  "sequence",str value.sequence;"translation_policy",R.Translation_policy.to_json value.translation_policy;
  "provenance",M.Provenance.to_json value.provenance]
let product_json (value:product) = obj ["node",str value.node_id;"symbol",str value.symbol;
  "root",str value.root_id;"cds_feature",str value.cds_feature;"expected",expected_product_json value.expected]
let owner_json = function
  | Node id -> obj ["kind",str "node";"id",str id]
  | External_slot_owner id -> obj ["kind",str "external_slot";"id",str id]
let owner_of_json raw =
  exact ["kind";"id"] raw;
  let id = name (get "id" raw) in
  match Json.string (get "kind" raw) with
  | "node" -> Node id | "external_slot" -> External_slot_owner id
  | _ -> Diagnostic.fail "policy_component_material" "Unknown local capacity owner."
let requirement_json = function
  | Input {id;external_slot} -> obj ["kind",str "input";"id",str id;"external_slot",str external_slot]
  | Capacity {id;owner;unit;scope;minimum} -> obj ["kind",str "capacity";"id",str id;
      "owner",owner_json owner;"unit",str (MC.resource_unit_name unit);
      "scope",str (MC.resource_scope_name scope);"minimum",Json.int minimum]
let requirement_of_json raw = match Json.string (get "kind" raw) with
  | "input" -> exact ["kind";"id";"external_slot"] raw;
      Input {id=name (get "id" raw);external_slot=name (get "external_slot" raw)}
  | "capacity" -> exact ["kind";"id";"owner";"unit";"scope";"minimum"] raw;
      let minimum = integer 1000000 (get "minimum" raw) in
      require (minimum >= 1) "Local capacity minimum must be positive.";
      Capacity {id=name (get "id" raw);owner=owner_of_json (get "owner" raw);
        unit=MC.resource_unit_of_json (get "unit" raw);scope=MC.resource_scope_of_json (get "scope" raw);minimum}
  | _ -> Diagnostic.fail "policy_component_material" "Unknown local provider prerequisite."
let body_to_json value = obj ["fragment",F.to_json value.fragment_value;
  "root",Construction.Root_source.to_json value.root_value;
  "carriers",arr (List.map carrier_json value.carrier_values);
  "products",arr (List.map product_json value.product_values);
  "provider_requirements",arr (List.map requirement_json value.requirement_values)]
let to_json value = obj ["schema_version",str schema_version;"profile",str profile;
  "identity",Pin.to_json value.identity_value;"body",body_to_json value]

type requirement_key = Input_key of string | Capacity_key of owner * MC.resource_unit * MC.resource_scope
let static_requirements fragment =
  let slots = F.external_slots fragment in
  let capacity owner unit scope minimum = Capacity_key (owner,unit,scope),minimum in
  List.map (fun (slot:F.external_slot) -> Input_key slot.slot_id,0) slots @
  List.map (fun (slot:F.external_slot) -> capacity (External_slot_owner slot.slot_id) MC.Input_rows_per_tick
    (match slot.input_kind with I.Evidence_input -> MC.Per_encounter_slot | I.Feedback_input -> MC.Per_executor) 1) slots @
  List.concat_map (fun (node:F.node) ->
    let owner = Node node.node_id in
    let per_slot unit minimum = capacity owner unit MC.Per_encounter_slot minimum in
    match node.model.primitive with
    | I.Truth_register _ -> [per_slot MC.Truth_cells 1]
    | I.Machine_bank {states;retained_capacity;_} ->
        let rec bits width bound=if bound>=List.length states then max 1 width else bits (width+1) (bound*2) in
        [per_slot MC.Machine_state_bits (bits 0 1);per_slot MC.Machine_correlation_records retained_capacity]
    | I.Evidence_bank _ -> [per_slot MC.Evidence_records 1;per_slot MC.Timer_cells 1]
    | I.Observed_rising -> [per_slot MC.Edge_history_cells 1]
    | I.Attempt_bank {capacity=count;_} -> [per_slot MC.Active_attempt_records count;
        capacity owner MC.Retained_correlation_records MC.Per_executor 1;per_slot MC.Timer_cells count]
    | _ -> []) (F.nodes fragment)
let check_requirements fragment requirements =
  let id = function Input {id;_} | Capacity {id;_} -> id in
  unique "provider prerequisite" (List.map id requirements);
  let key = function Input {external_slot;_} -> Input_key external_slot
    | Capacity {owner;unit;scope;_} -> Capacity_key (owner,unit,scope) in
  let expected = static_requirements fragment in
  require (List.map key requirements = List.map fst expected)
    "Local provider prerequisites must preserve the complete ordered owner, unit and scope inventory.";
  List.iter2 (fun requirement (_,minimum) -> match requirement with
    | Input _ -> ()
    | Capacity value -> require (value.minimum >= minimum)
        "Local capacity minimum is below its static primitive requirement.") requirements expected

let root_feature root id =
  match List.find_opt (fun feature -> N.Feature.id feature = id)
    (N.features (Construction.Root_source.molecule root)) with
  | Some feature -> feature
  | None -> Diagnostic.fail "policy_component_material" "Local material site names an absent root feature."
let check_site root (site:site) =
  require (site.root_id = Construction.Root_source.id root) "Local material site names a different root.";
  let feature = root_feature root site.feature_id in
  (match N.Feature.path feature with
   | None -> Diagnostic.fail "policy_component_material" "Local material carrier feature has no path."
   | Some path -> require (equal (G.Path.to_json path) (G.Path.to_json site.path))
       "Local material site must equal the complete actual feature path.");
  require (G.Path.length site.path > 0) "Local material carrier path must be nonempty.";
  G.Path.validate_for site.path (N.space (Construction.Root_source.molecule root))
let product_of_json raw =
  exact ["node";"symbol";"root";"cds_feature";"expected"] raw;
  let expected = get "expected" raw in
  exact ["identity";"sequence";"translation_policy";"provenance"] expected;
  let sequence = M.text ~maximum:M.max_residues (get "sequence" expected) in
  require (String.for_all (String.contains "ACDEFGHIKLMNPQRSTVWY") sequence)
    "Local expected product requires complete canonical protein spelling without a stop symbol.";
  let identity = Pin.of_json (get "identity" expected)
  and translation_policy = R.Translation_policy.of_json (get "translation_policy" expected) in
  require (Pin.content_fingerprint identity = Canonical.fingerprint (PM.product_content_json sequence))
    "Local expected product identity must pin its complete declared spelling.";
  require (R.Translation_policy.profile translation_policy = R.Translation_policy.Ordinary_cds &&
    R.Translation_policy.genetic_code translation_policy = R.standard_genetic_code &&
    R.Translation_policy.recodings translation_policy = [])
    "Local product requires ordinary standard-code translation without recoding.";
  {node_id=name (get "node" raw);symbol=name ~maximum:256 (get "symbol" raw);
   root_id=name (get "root" raw);cds_feature=name (get "cds_feature" raw);
   expected={identity;sequence;translation_policy;provenance=M.Provenance.of_json (get "provenance" expected)}}
let check_products fragment root products =
  let expected = List.filter_map (fun (node:F.node) -> match node.model.primitive with
    | I.Product_constant symbol -> Some (node.node_id,symbol) | _ -> None) (F.nodes fragment) in
  require (List.map (fun (value:product) -> value.node_id,value.symbol) products = expected)
    "Local products must preserve every product-constant node and exact symbol in order.";
  require (products = [] || N.coding_status (Construction.Root_source.molecule root) = N.Coding)
    "Local product requires an explicitly coding root.";
  List.iter (fun (value:product) ->
    require (value.root_id = Construction.Root_source.id root) "Local product names a different root.";
    let feature = root_feature root value.cds_feature in
    require (N.Feature.kind feature = "coding_sequence" && N.Feature.reading_frame feature = Some 0)
      "Local product requires a coding-sequence feature with reading frame zero.";
    match N.Feature.path feature with
    | None -> Diagnostic.fail "policy_component_material" "Local product CDS feature has no path."
    | Some path -> require (G.Path.strand path = G.Forward && G.Path.length path > 0)
        "Local product CDS requires a nonempty forward path.") products

let of_json ~library raw =
  preflight raw;
  exact ["schema_version";"profile";"identity";"body"] raw;
  require (get "schema_version" raw = str schema_version && get "profile" raw = str profile)
    "Unsupported local component material profile.";
  let identity_value = Pin.of_json (get "identity" raw) and body = get "body" raw in
  exact ["fragment";"root";"carriers";"products";"provider_requirements"] body;
  require (Pin.kind identity_value = Pin.Model && Pin.content_fingerprint identity_value = Canonical.fingerprint body)
    "Local component identity must pin its complete supplied body.";
  let fragment_value = F.of_json ~library (get "fragment" body) in
  let root_value = Construction.Root_source.of_json (get "root" body) in
  let molecule = Construction.Root_source.molecule root_value in
  let space = N.space molecule in
  require (N.form molecule = N.Primary_rna && N.sequence_extent molecule = H.Complete &&
    G.Space.alphabet space = G.Rna && G.Space.topology space = G.Linear && G.Space.axis space = G.Five_prime_to_three_prime)
    "Local material root requires complete linear five-prime-to-three-prime primary RNA.";
  require (List.length (N.features molecule) <= 4) "Local material root exceeds four features.";
  let carrier_values = M.array ~maximum:max_carriers (get "carriers" body) |> List.map (fun value ->
    exact ["target";"sites"] value;
    let sites = M.array ~maximum:4 (get "sites" value) |> List.map (fun site ->
      exact ["root";"feature";"path"] site;
      {root_id=name (get "root" site);feature_id=name (get "feature" site);path=G.Path.of_json (get "path" site)}) in
    require (sites <> []) "Every local material target requires one to four actual feature sites.";
    unique "carrier site" (List.map (fun site -> Canonical.encode (site_json site)) sites);
    List.iter (check_site root_value) sites;
    {target=target_of_json (get "target" value);sites}) in
  require (List.map (fun (value:carrier) -> value.target) carrier_values = target_inventory fragment_value)
    "Local material carriers must preserve the exhaustive ordered target inventory.";
  let product_values = M.array ~maximum:1 (get "products" body) |> List.map product_of_json in
  check_products fragment_value root_value product_values;
  let requirement_values = M.array ~maximum:max_provider_requirements (get "provider_requirements" body)
    |> List.map requirement_of_json in
  check_requirements fragment_value requirement_values;
  let value = {identity_value;fragment_value;root_value;carrier_values;product_values;requirement_values} in
  require (equal raw (to_json value)) "Local material must preserve its complete canonical typed body without normalization.";
  preflight (to_json value);value
let fingerprint value = Canonical.fingerprint (to_json value)
let identity value = value.identity_value
let model_library_digest value = F.model_library_digest value.fragment_value
let fragment value = value.fragment_value
let root value = value.root_value
let carriers value = value.carrier_values
let products value = value.product_values
let provider_requirements value = value.requirement_values

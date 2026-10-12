open Bioc_wire
module Input = Policy_material_request
let schema_version = "biocompiler.policy_controlled_activity_implementation.v0.1"
type delays = { onset_ticks:int; cessation_ticks:int; reactivation_ticks:int }
type t = { raw:Json.t; identity:string; work:int; delay_values:delays }
let get name raw = Json.field name (Json.object_fields raw)
let exact names raw = Json.exact_fields names (Json.object_fields raw)
let require value message = Diagnostic.require value "controlled_activity_implementation" message
let str value = Json.String value
let fixed fields = Json.Object (List.map (fun (key,value) -> key,str value) fields)
let positive raw =
  let value = Json.integer raw in
  require (Z.sign value > 0 && Z.leq value (Z.of_int 10000))
    "Primitive delay must be a positive integer within the original 10000-tick parameter ceiling.";
  Z.to_int value
let of_json ?(charge=fun _ -> ()) (raw:Json.t) : t =
  let work = ref 0 in
  let spend amount =
    Diagnostic.require (amount >= 0 && amount <= max_int - !work)
      "controlled_activity_implementation_resource" "Implementation work accounting overflow.";
    charge amount; work := !work + amount in
  let bytes = Input.preflight ~charge:spend raw in
  exact ["schema_version";"mechanism_model";"control_contract";"semantics";
    "catalog_binding";"assembly";"context";"resources";"primitives";"wires"] raw;
  require (get "schema_version" raw = str schema_version) "Unsupported primitive implementation schema.";
  (* Full copied bodies are retained without assigning executable meaning to
     empty component SemanticDefinitions. Only the explicit graph below is
     executable. Fresh checking reconstructs every copied body from originals. *)
  List.iter (fun key -> ignore (Json.object_fields (get key raw)))
    ["mechanism_model";"control_contract";"semantics";"catalog_binding";"assembly";"context";"resources"];
  let primitives = Json.array (get "primitives" raw) in
  require (List.length primitives = 8) "The closed graph has exactly eight ordered primitives.";
  let required = [
    fixed ["id","encounter";"op","encounter_live"];
    fixed ["id","antigen";"op","physical_input";"key","antigen"];
    fixed ["id","controller";"op","physical_input";"key","controller"];
    fixed ["id","protein-a";"op","physical_input";"key","protein_a"];
    fixed ["id","protein-b";"op","physical_input";"key","protein_b"];
    fixed ["id","gate";"op","all"]] in
  List.iteri (fun index expected ->
    require (Json.equal (List.nth primitives index) expected)
      "Input adapters and gate must have their exact closed identities and fields.") required;
  let activity = List.nth primitives 6 in
  exact ["id";"op";"onset_ticks";"cessation_ticks";"reactivation_ticks";
    "initial_band";"timer_scope";"activation_scope"] activity;
  require (get "id" activity = str "activity" && get "op" activity = str "delayed_reversible" &&
    get "initial_band" activity = str "background" && get "timer_scope" activity = str "executor" &&
    get "activation_scope" activity = str "encounter_generation")
    "Delayed activity primitive identity, initial band or state ownership is unsupported.";
  let delay_values = {
    onset_ticks=positive (get "onset_ticks" activity);
    cessation_ticks=positive (get "cessation_ticks" activity);
    reactivation_ticks=positive (get "reactivation_ticks" activity)} in
  require (Json.equal (List.nth primitives 7) (fixed ["id","readout";"op","activity_band"]))
    "The readout must retain the physical activity band.";
  let wires = Json.Array (List.map (fun (source,target,input) ->
    fixed ["from",source;"to",target;"input",input]) [
    "encounter","gate","live";"antigen","gate","antigen";
    "controller","gate","controller";"protein-a","gate","protein_a";
    "protein-b","gate","protein_b";"gate","activity","enabled";
    "activity","readout","band"]) in
  require (Json.equal (get "wires" raw) wires)
    "Primitive wiring must preserve every required physical dependency exactly once.";
  spend bytes;
  let encoded = Canonical.encode_bounded ~max_bytes:Molecular_record.max_json_bytes raw in
  require (String.length encoded = bytes) "Implementation canonical byte accounting disagrees.";
  spend bytes;
  {raw;identity=Canonical.sha256 encoded;work= !work;delay_values}
let to_json (value:t) = value.raw
let fingerprint (value:t) = value.identity
let decoding_work (value:t) = value.work
let delays (value:t) = value.delay_values

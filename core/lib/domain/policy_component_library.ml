open Bioc_wire
module C = Policy_component_material
module M = Molecular_record
module Pin = Pinned_identity
module Names = Set.Make (String)

let schema_version = "biocompiler.policy_component_library.v0.1"
let profile = "biocompiler.policy_exact_component_library.v0.1"
let max_components = 16
type t = { component_values:C.t list; library_pin:string }
let require condition message = Diagnostic.require condition "policy_component_library" message
let get key value = Json.field key (Json.object_fields value)
let to_json value = Json.Object ["schema_version",Json.String schema_version;
  "profile",Json.String profile;"components",Json.Array (List.map C.to_json value.component_values)]
let of_json ~library raw =
  M.check_resources raw;
  let rec no_float = function
    | Json.Float _ -> require false "Raw floats cannot enter a component library."
    | Json.Array values -> List.iter no_float values
    | Json.Object fields -> List.iter (fun (_,value) -> no_float value) fields
    | _ -> () in
  no_float raw;
  Json.exact_fields ["schema_version";"profile";"components"] (Json.object_fields raw);
  require (get "schema_version" raw = Json.String schema_version && get "profile" raw = Json.String profile)
    "Unsupported local component library profile.";
  let component_values = M.array ~maximum:max_components (get "components" raw) |> List.map (C.of_json ~library) in
  require (component_values <> []) "Original component library is empty.";
  ignore (List.fold_left (fun seen component ->
    let identity = C.identity component in
    let key = Canonical.encode (Json.Array [Json.String (Pin.kind_name identity);
      Json.String (Pin.id identity);Json.String (Pin.version identity)]) in
    require (not (Names.mem key seen)) "Duplicate component kind, name and version identity.";
    Names.add key seen) Names.empty component_values);
  let value = {component_values;library_pin=Policy_implementation.library_digest library} in
  require (Canonical.encode raw = Canonical.encode (to_json value))
    "Component library must preserve its complete canonical typed inventory without normalization.";
  M.check_resources (to_json value);value
let fingerprint value = Canonical.fingerprint (to_json value)
let model_library_digest value = value.library_pin
let components value = value.component_values
let find value identity = List.find_opt (fun component ->
  Json.equal (Pin.to_json (C.identity component)) (Pin.to_json identity)) value.component_values

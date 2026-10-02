open Bioc_wire
module M = Measurement_contract
module N = Runtime_number
let resource_profile = "biocompiler.realization_contract.resources.v1"
let resource_limits = Json.Object ["profile", Json.String resource_profile;
    "max_bytes", Json.int Limits.max_request_bytes; "max_nodes", Json.int Limits.max_json_nodes;
    "max_depth", Json.int Limits.max_depth; "max_string_bytes", Json.int Limits.max_string_bytes;
    "max_number_chars", Json.int Limits.max_number_chars]
let require ?path condition message = Diagnostic.require ?path condition "invalid_realization_contract" message
let limit ?path condition = Diagnostic.require ?path condition "realization_contract_limit"
    "Realization contract exceeds its native resource boundary."
let preflight ?(path = "") value =
  try M.preflight ~path value with
  | Diagnostic.Error diagnostic when diagnostic.code = "human_record_limit" -> limit ~path false
  | Diagnostic.Error diagnostic when diagnostic.code = "human_record_cycle" ->
      Diagnostic.fail ~path "realization_contract_cycle" "Cyclic realization declaration."
let bounded values =
  let rec count left = function [] -> () | _ :: rest -> limit (left > 0); count (left - 1) rest in
  count Limits.max_json_nodes values; values
let weight value =
  preflight value;
  let pending = ref [value] and nodes = ref 0 in
  while !pending <> [] do
    let value = List.hd !pending in pending := List.tl !pending; incr nodes;
    match value with
    | Json.Array values -> List.iter (fun value -> pending := value :: !pending) values
    | Json.Object fields -> List.iter (fun (_, value) -> pending := value :: !pending) fields
    | _ -> ()
  done;
  String.length (Canonical.encode value), !nodes
type budget = {mutable bytes : int; mutable nodes : int}
let reserve (budget : budget) bytes nodes =
  limit (bytes <= Limits.max_request_bytes - budget.bytes && nodes <= Limits.max_json_nodes - budget.nodes);
  budget.bytes <- budget.bytes + bytes; budget.nodes <- budget.nodes + nodes
let leaf value (budget : budget) = let bytes, nodes = weight value in reserve budget bytes nodes; value
let array encode values (budget : budget) =
  let values = bounded values in reserve budget 2 1;
  Json.Array (List.mapi (fun index value ->
      if index > 0 then reserve budget 1 0;
      leaf (encode value) budget) values)
let str value = Json.String value
let strings values = array str values
let document fields =
  let budget = {bytes = 2; nodes = 1} in
  let result = Json.Object (List.mapi (fun index (key, encode) ->
      let bytes, _ = weight (str key) in reserve budget (bytes + 1 + if index = 0 then 0 else 1) 0;
      key, encode budget) fields) in
  preflight result; result
let record ~path version keys value =
  preflight ~path value;
  let fields = Json.object_fields ~path value in
  Json.exact_fields ~path ("schema_version" :: keys) fields;
  Diagnostic.require ~path (Json.string (Json.field "schema_version" fields) = version)
    "unsupported_schema" "Unsupported realization contract schema.";
  fields
let field path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let name path key fields = Json.name ~path:(path ^ "/" ^ key) (field path key fields)
let unique ~path key values message =
  let seen = Hashtbl.create 16 in
  List.iter (fun value -> let identity = key value in
      require ~path (not (Hashtbl.mem seen identity)) message;
      Hashtbl.add seen identity ()) values
let names ~path value =
  let values = Json.array ~path value |> List.mapi (fun index -> Json.name ~path:(path ^ "/" ^ string_of_int index)) in
  unique ~path Fun.id values "Declared names must be unique."; values
let records ~path decode value = Json.array ~path value |> List.mapi
    (fun index value -> decode ?path:(Some (path ^ "/" ^ string_of_int index)) value)
let frozen json = let canonical = Canonical.encode json in json, Canonical.sha256 canonical, String.length canonical

type sample = Boolean of bool | Number of N.t | Scalar of M.Scalar.t | Other
let sample_of_json = function
  | Json.Bool value -> Boolean value | Json.Int value -> Number (N.Integer value)
  | Json.Float value -> Number (N.Real value) | _ -> Other
let sample_of_scalar_json ?(path = "") value =
  (* Only the explicit typed-scalar entry point permits dictionary decoding.
     Raw wire/resource errors are checked before semantic failure becomes a
     nonmember, matching a malformed supplied ScalarLiteral. *)
  preflight ~path value;
  try Scalar (M.Scalar.of_json ~path value) with
  | Diagnostic.Error diagnostic when List.mem diagnostic.code
      ["invalid_type"; "missing_field"; "unknown_field"; "invalid_name";
       "invalid_type_spec"; "invalid_measurement_contract"; "invalid_binding";
       "type_mismatch"; "unsupported_unit"; "canonical_value_mismatch";
       "numeric_overflow"; "evaluation_nonfinite"] -> Other
let inside interval sample =
  let number = match sample with
    | Number value -> Some value
    | Scalar value ->
        let arguments = M.Interval.dtype interval |> Type_spec.to_json |> M.field "arguments" |> Json.array in
        let expected = Type_spec.of_json (List.hd arguments) in
        if Type_spec.compatible (M.Scalar.dtype value) expected then Some (M.Scalar.canonical value) else None
    | Boolean _ | Other -> None in
  match number with
  | None -> false
  | Some value ->
      (match N.check_finite value with
       | value -> N.compare (M.Interval.lower interval) value <= 0 && N.compare value (M.Interval.upper interval) <= 0
       | exception Diagnostic.Error diagnostic when diagnostic.code = "evaluation_nonfinite" -> false)

module Observable = struct
  include M.Observable
  let canonical_size value = String.length (Canonical.encode (to_json value))
end
module Response = struct
  include M.Response
  let canonical_size value = String.length (Canonical.encode (to_json value))
  let accepts value sample ~active = inside (if active then M.Response.active value else M.Response.inactive value) sample
end

module Input_domain = struct
  type field = Observation_map.field = Value | Present | High | Low
  type allowed = Booleans of bool list | Range of M.Interval.t
  type t = {json : Json.t; hash : string; size : int; signal : string; field : field;
            observable : Observable.t; allowed : allowed}
  let schema_version = "biocompiler.input_domain.v0.1"
  let boolean = Type_spec.of_json (Json.parse {|{"kind":"condition","name":"Condition","dimensions":{},"arguments":[]}|})
  let encode ~signal_id ~field ~observable ~allowed =
    let allowed = match allowed with
      | Booleans values -> array (fun value -> Json.Bool value) values
      | Range value -> leaf (M.Interval.to_json value) in
    document ["schema_version", leaf (str schema_version); "signal_id", leaf (str signal_id);
        "field", leaf (str (Observation_map.field_name field)); "observable", leaf (Observable.to_json observable);
        "allowed", allowed]
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["signal_id"; "field"; "observable"; "allowed"] value in
    let observable = Observable.of_json ~path:(path ^ "/observable") (field path "observable" fields) in
    let signal = name path "signal_id" fields in
    let observation_field = match Json.string ~path:(path ^ "/field") (field path "field" fields) with
      | "value" -> Value | "present" -> Present | "high" -> High | "low" -> Low
      | _ -> Diagnostic.fail ~path "invalid_realization_contract" "Unknown input observation field." in
    let allowed = match observation_field with
      | Value ->
          require ~path (Type_spec.kind (Observable.dtype observable) = Type_spec.Scalar)
            "Numeric observations require a scalar observable.";
          Range (M.Interval.of_json ~path:(path ^ "/allowed") ~expected:(Observable.dtype observable) (field path "allowed" fields))
      | Present | High | Low ->
          require ~path (Type_spec.compatible (Observable.dtype observable) boolean)
            "Qualitative observations require a Boolean observable.";
          let values = Json.array ~path:(path ^ "/allowed") (field path "allowed" fields)
            |> List.mapi (fun index -> Json.boolean ~path:(path ^ "/allowed/" ^ string_of_int index)) in
          require ~path (values <> []) "Qualitative domains require a nonempty Boolean array.";
          unique ~path Fun.id values "Allowed Boolean values must be unique.";
          Booleans (List.sort Bool.compare values) in
    let json, hash, size = encode ~signal_id:signal ~field:observation_field ~observable ~allowed |> frozen in
    {json; hash; size; signal; field = observation_field; observable; allowed}
  let make ~signal_id ~field ~observable ~allowed = encode ~signal_id ~field ~observable ~allowed |> of_json
  let to_json (value : t) = value.json
  let fingerprint (value : t) = value.hash
  let canonical_size (value : t) = value.size
  let signal_id (value : t) = value.signal
  let field (value : t) = value.field
  let field_name (value : t) = Observation_map.field_name value.field
  let observable (value : t) = value.observable
  let allowed (value : t) = value.allowed
  let scope (value : t) = Observable.scope value.observable
  let role (value : t) = Observable.role value.observable
  let contains (value : t) sample = match value.allowed, sample with
    | Range interval, sample -> inside interval sample
    | Booleans values, Boolean value -> List.mem value values
    | Booleans _, (Number _ | Scalar _ | Other) -> false
end

module Operating_domain = struct
  type t = {json : Json.t; hash : string; size : int; id : string; version : string; role : string;
            inputs : Input_domain.t list; minimum_horizon : M.Scalar.t; max_contacts : Z.t option;
            capabilities : string list}
  let schema_version = "biocompiler.operating_domain.v0.1"
  let encode ~id ~version ~role ~inputs ~minimum_horizon ~max_contacts ~required_capabilities =
    document ["schema_version", leaf (str schema_version); "id", leaf (str id); "version", leaf (str version);
        "role", leaf (str role); "inputs", array Input_domain.to_json inputs;
        "minimum_horizon", leaf (M.Scalar.to_json minimum_horizon);
        "max_contacts", leaf (match max_contacts with None -> Json.Null | Some value -> Json.Int value);
        "required_capabilities", strings required_capabilities]
  let input_key value = Input_domain.signal_id value, Input_domain.field_name value
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["id"; "version"; "role"; "inputs"; "minimum_horizon";
                                             "max_contacts"; "required_capabilities"] value in
    let inputs = records ~path:(path ^ "/inputs") Input_domain.of_json (field path "inputs" fields) in
    let minimum_horizon = M.Scalar.duration ~path:(path ^ "/minimum_horizon") ~positive:true (field path "minimum_horizon" fields) in
    let id = name path "id" fields and version = name path "version" fields and role = name path "role" fields in
    require ~path (inputs <> []) "An operating domain requires nonempty input declarations.";
    let inputs = List.sort (fun left right -> Stdlib.compare (input_key left) (input_key right)) inputs in
    unique ~path input_key inputs "Input domains require unique signal/field identities.";
    unique ~path (fun value -> Observable.id (Input_domain.observable value)) inputs "Input endpoint IDs must be unique.";
    require ~path (List.for_all (fun value -> Input_domain.role value = role) inputs)
      "All input domains must belong to the selected role.";
    let signals = Hashtbl.create 16 in
    List.iter (fun value ->
        let meaning = Input_domain.scope value, Observable.compartment (Input_domain.observable value) in
        let identity = Input_domain.signal_id value in
        require ~path (match Hashtbl.find_opt signals identity with None -> true | Some prior -> prior = meaning)
          "Fields of one signal must agree on scope and compartment.";
        Hashtbl.replace signals identity meaning) inputs;
    let max_contacts = match field path "max_contacts" fields with
      | Json.Null -> None
      | value -> let value = Json.integer ~path:(path ^ "/max_contacts") value in
          require ~path (Z.sign value >= 0) "Contact limit must be a nonnegative integer or null."; Some value in
    require ~path (max_contacts <> Some Z.zero ||
        not (List.exists (fun value -> Input_domain.scope value = Observable.Contact) inputs))
      "A contact input domain needs a nonzero allowed contact bound.";
    let capabilities = names ~path:(path ^ "/required_capabilities") (field path "required_capabilities" fields)
      |> List.sort String.compare in
    let json, hash, size = encode ~id ~version ~role ~inputs ~minimum_horizon ~max_contacts
        ~required_capabilities:capabilities |> frozen in
    {json; hash; size; id; version; role; inputs; minimum_horizon; max_contacts; capabilities}
  let make ~id ~version ~role ~inputs ~minimum_horizon ?max_contacts ?(required_capabilities = []) () =
    encode ~id ~version ~role ~inputs ~minimum_horizon ~max_contacts ~required_capabilities |> of_json
  let to_json (value : t) = value.json
  let fingerprint (value : t) = value.hash
  let canonical_size (value : t) = value.size
  let id (value : t) = value.id
  let version (value : t) = value.version
  let role (value : t) = value.role
  let inputs (value : t) = value.inputs
  let minimum_horizon (value : t) = value.minimum_horizon
  let max_contacts (value : t) = value.max_contacts
  let required_capabilities (value : t) = value.capabilities
end

module Behavior_contract = struct
  type t = {json : Json.t; hash : string; size : int; id : string; behavior : string;
            requirements : Response.t list; role : string}
  let schema_version = "biocompiler.behavior_contract.v0.1"
  let encode ~id ~behavior_fingerprint ~requirements =
    document ["schema_version", leaf (str schema_version); "id", leaf (str id);
        "behavior_fingerprint", leaf (str behavior_fingerprint); "requirements", array Response.to_json requirements]
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["id"; "behavior_fingerprint"; "requirements"] value in
    let requirements = records ~path:(path ^ "/requirements") Response.of_json (field path "requirements" fields) in
    let id = name path "id" fields in
    let behavior = Json.string ~path:(path ^ "/behavior_fingerprint") (field path "behavior_fingerprint" fields) in
    require ~path (String.length behavior = 64 && String.for_all
        (function '0'..'9' | 'a'..'f' -> true | _ -> false) behavior) "Behavior fingerprint must be lowercase SHA-256 hex.";
    require ~path (requirements <> []) "A behavior contract requires nonempty response requirements.";
    let requirements = List.sort (fun left right -> String.compare (Response.id left) (Response.id right)) requirements in
    unique ~path Response.id requirements "Response requirement IDs must be unique.";
    unique ~path (fun value -> Response.rule_id value, Response.specification_id value) requirements
      "Each rule/action specification requires one response requirement.";
    unique ~path (fun value -> Observable.id (Response.observable value)) requirements "Response endpoint IDs must be unique.";
    let role = Observable.role (Response.observable (List.hd requirements)) in
    require ~path (List.for_all (fun value -> Observable.role (Response.observable value) = role) requirements)
      "A finite-history contract must select one role.";
    let json, hash, size = encode ~id ~behavior_fingerprint:behavior ~requirements |> frozen in
    {json; hash; size; id; behavior; requirements; role}
  let make ~id ~behavior_fingerprint ~requirements = encode ~id ~behavior_fingerprint ~requirements |> of_json
  let to_json (value : t) = value.json
  let fingerprint (value : t) = value.hash
  let canonical_size (value : t) = value.size
  let id (value : t) = value.id
  let behavior_fingerprint (value : t) = value.behavior
  let requirements (value : t) = value.requirements
  let role (value : t) = value.role
end

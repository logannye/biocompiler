open Bioc_wire
module N = Runtime_number
module Names = Map.Make (String)

type status = Pass | Fail | Unknown
type assessment = { outcome : status; details : string list }
let status value = value.outcome
let reasons value = value.details
let passed value = value.outcome = Pass
let status_name = function Pass -> "pass" | Fail -> "fail" | Unknown -> "unknown"
let require ?path condition message = Diagnostic.require ?path condition "component_contract" message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let option_json encode = function None -> Json.Null | Some value -> encode value

(* Component JsonArtifact has no molecular-specific resource profile. This
   internal native boundary adds the wire limits, before projection/encoding.
   Repeated strings count repeatedly; keys count as nodes. These are execution
   resource limits, not empirical or component eligibility checks. *)
let bounded ~path value =
  let nodes = ref 0 and bytes = ref 0 in
  let limit condition = Diagnostic.require ~path condition "component_contract_limit" "Component contract exceeds its native resource bound." in
  let add amount = limit (amount <= Limits.max_response_bytes - !bytes); bytes := !bytes + amount in
  let node () = incr nodes; limit (!nodes <= Limits.max_json_nodes) in
  let quoted text =
    limit (String.length text <= Limits.max_string_bytes); add 2; add (String.length text);
    String.iter (function '"' | '\\' | '\b' | '\012' | '\n' | '\r' | '\t' -> add 1
      | value when Char.code value < 32 -> add 5 | _ -> ()) text;
    Json.validate_utf8 text in
  let rec visit depth = function
    | value ->
        limit (depth <= Limits.max_depth); node ();
        match value with
        | Json.Null -> add 4 | Json.Bool value -> add (if value then 4 else 5)
        | Json.Int value ->
            limit (Z.numbits value <= 4 * Limits.max_number_chars);
            let text = Z.to_string value in limit (String.length text <= Limits.max_number_chars); add (String.length text)
        | Json.Float value ->
            Diagnostic.require ~path (Float.is_finite value) "nonfinite_number" "Nonfinite component contract number.";
            add (String.length (Canonical.float_string value))
        | Json.String value -> quoted value
        | Json.Array values ->
            add 2; let first = ref true in
            List.iter (fun value -> if !first then first := false else add 1; visit (depth + 1) value) values
        | Json.Object values ->
            add 2; let seen = Hashtbl.create 16 and first = ref true in
            List.iter (fun (key, value) -> node (); quoted key;
                Diagnostic.require ~path (not (Hashtbl.mem seen key)) "duplicate_key" "Duplicate component contract key.";
                Hashtbl.add seen key (); if !first then first := false else add 1;
                add 1; visit (depth + 1) value) values
  in visit 0 value
let record ~path schema keys value =
  bounded ~path value;
  let fields = Json.object_fields ~path value in
  Json.exact_fields ~path ("schema_version" :: keys) fields;
  Diagnostic.require ~path (Json.string (Json.field "schema_version" fields) = schema)
    "unsupported_schema" "Unsupported component contract schema.";
  fields
let get ~path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let names ~path value =
  let values = Json.array ~path value |> List.map (Json.name ~path) in
  require ~path (List.length values = List.length (List.sort_uniq String.compare values)) "Duplicate contract names.";
  values
let strings values = arr (List.map str values)
let exact_type a b = Json.equal (Type_spec.to_json a) (Type_spec.to_json b)
let contract_type value =
  require (List.mem (Type_spec.kind value) [Type_spec.Scalar; Type_spec.Condition]) "Contracts support scalar and condition types only.";
  value
let dtype ~path value = contract_type (Type_spec.of_json ~path value)
let finite ~path value =
  match N.of_json ~path value with
  | value -> value
  | exception Diagnostic.Error _ -> Diagnostic.fail ~path "component_contract" "Domain quantities must be finite integers or floats, not Booleans."
let boolean_type = Type_spec.of_json (obj ["kind", str "condition"; "name", str "Condition";
    "dimensions", obj []; "arguments", arr []])

module Value_domain = struct
  type kind = Boolean | Scalar_interval | Unknown_domain
  type t = { kind : kind; dtype : Type_spec.t; unit : string; values : bool list;
    lower : N.t option; upper : N.t option; reason : string option }
  let schema_version = "biocompiler.component_value_domain.v0.1"
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["kind"; "dtype"; "unit"; "values"; "lower"; "upper"; "reason"] value in
    let field key = get ~path key fields in
    let kind = match Json.string ~path (field "kind") with
      | "boolean" -> Boolean | "scalar_interval" -> Scalar_interval | "unknown" -> Unknown_domain
      | _ -> Diagnostic.fail ~path "component_contract" "Unknown component value domain kind." in
    let dtype = dtype ~path:(path ^ "/dtype") (field "dtype") in
    let unit = Json.name ~path:(path ^ "/unit") (field "unit") in
    let values = Json.array ~path:(path ^ "/values") (field "values") |> List.map (Json.boolean ~path) in
    require ~path (List.length values = List.length (List.sort_uniq Bool.compare values)) "Boolean domain values must be unique.";
    let values = List.sort Bool.compare values in
    require ~path (Type_spec.kind dtype <> Type_spec.Condition || unit = "1") "Boolean domains use unit '1'.";
    let lower, upper, reason = match kind with
     | Boolean ->
         require ~path (Type_spec.kind dtype = Type_spec.Condition && values <> []) "Boolean domains need a condition type and nonempty values.";
         require ~path (field "lower" = Json.Null && field "upper" = Json.Null && field "reason" = Json.Null)
           "Boolean domains cannot carry bounds or unknown reasons.";
         None, None, None
     | Scalar_interval ->
         require ~path (Type_spec.kind dtype = Type_spec.Scalar && values = [] && field "reason" = Json.Null)
           "Scalar intervals need a scalar type and no Boolean values or unknown reason.";
         let lower = finite ~path:(path ^ "/lower") (field "lower") in
         let upper = finite ~path:(path ^ "/upper") (field "upper") in
         require ~path (N.compare lower upper <= 0) "Domain lower bound exceeds upper bound.";
         Some lower, Some upper, None
     | Unknown_domain ->
         require ~path (values = [] && field "lower" = Json.Null && field "upper" = Json.Null)
           "Unknown domains require a reason and no invented values or bounds.";
         None, None, Some (Json.name ~path:(path ^ "/reason") (field "reason")) in
    { kind; dtype; unit; values; lower; upper; reason }
  let to_json value = obj ["schema_version", str schema_version;
    "kind", str (match value.kind with Boolean -> "boolean" | Scalar_interval -> "scalar_interval" | Unknown_domain -> "unknown");
    "dtype", Type_spec.to_json value.dtype; "unit", str value.unit;
    "values", arr (List.map (fun value -> Json.Bool value) value.values);
    "lower", option_json N.to_json value.lower; "upper", option_json N.to_json value.upper;
    "reason", option_json str value.reason]
  let fingerprint value = Canonical.fingerprint (to_json value)
  let boolean ?(values = [false; true]) () =
    of_json (to_json { kind = Boolean; dtype = boolean_type; unit = "1"; values; lower = None; upper = None; reason = None })
  let interval ~lower ~upper ~dtype ~unit =
    of_json (to_json { kind = Scalar_interval; dtype; unit; values = []; lower = Some lower; upper = Some upper; reason = None })
  let unknown ~dtype ~unit ~reason =
    of_json (to_json { kind = Unknown_domain; dtype; unit; values = []; lower = None; upper = None; reason = Some reason })
  let kind value = value.kind
  let dtype value = value.dtype
  let unit value = value.unit
  let values value = value.values
  let lower value = value.lower
  let upper value = value.upper
  let reason value = value.reason
end

module Domain_check = struct
  type t = { claimed : status; reasons : string list }
  let schema_version = "biocompiler.component_domain_check.v0.1"
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["status"; "reasons"] value in
    let claimed = match Json.string ~path (get ~path "status" fields) with
      | "pass" -> Pass | "fail" -> Fail | "unknown" -> Unknown
      | _ -> Diagnostic.fail ~path "component_contract" "Unknown component check status." in
    { claimed; reasons = names ~path:(path ^ "/reasons") (get ~path "reasons" fields) }
  let to_json value = obj ["schema_version", str schema_version; "status", str (status_name value.claimed); "reasons", strings value.reasons]
  let fingerprint value = Canonical.fingerprint (to_json value)
  let claimed_status value = value.claimed
  let claimed_reasons value = value.reasons
  let of_assessment value = { claimed = value.outcome; reasons = value.details }
end
let assessment_to_json value = Domain_check.to_json (Domain_check.of_assessment value)
let fresh outcome details =
  bounded ~path:"/assessment" (obj ["schema_version", str Domain_check.schema_version;
    "status", str (status_name outcome); "reasons", strings details]);
  { outcome; details }
let combine values =
  let outcome = if List.exists (fun value -> value.outcome = Fail) values then Fail
    else if List.exists (fun value -> value.outcome = Unknown) values then Unknown else Pass in
  let _, details = List.fold_left (fun (seen, result) value ->
      List.fold_left (fun (seen, result) reason ->
          if Names.mem reason seen then seen, result
          else Names.add reason () seen, reason :: result) (seen, result) value.details) (Names.empty, []) values in
  fresh outcome (List.rev details)
let domain_subset ~required ~supported =
  let module V = Value_domain in
  if not (exact_type (V.dtype required) (V.dtype supported)) || V.unit required <> V.unit supported then
    fresh Fail ["Domain types or explicit units differ."]
  else if V.kind required = V.Unknown_domain || V.kind supported = V.Unknown_domain then
    fresh Unknown ["Domain inclusion is unresolved because a domain is unknown."]
  else if V.kind required <> V.kind supported then fresh Fail ["Domain kinds differ."]
  else
    let contained = match V.kind required with
      | V.Boolean -> List.for_all (fun value -> List.mem value (V.values supported)) (V.values required)
      | V.Scalar_interval ->
          N.compare (Option.get (V.lower supported)) (Option.get (V.lower required)) <= 0
          && N.compare (Option.get (V.upper required)) (Option.get (V.upper supported)) <= 0
      | V.Unknown_domain -> assert false in
    if contained then fresh Pass [] else fresh Fail ["Required domain exceeds the supported domain."]

module Operating_domain = struct
  type t = (string * Value_domain.t) list
  let schema_version = "biocompiler.component_operating_domain.v0.1"
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["constraints"] value in
    Json.object_fields ~path:(path ^ "/constraints") (get ~path "constraints" fields)
    |> List.map (fun (key, value) -> ignore (Json.name ~path (str key)); key, Value_domain.of_json ~path:(path ^ "/constraints/" ^ key) value)
    |> List.sort (fun (a, _) (b, _) -> String.compare a b)
  let to_json value = obj ["schema_version", str schema_version; "constraints", obj (List.map (fun (key, value) -> key, Value_domain.to_json value) value)]
  let fingerprint value = Canonical.fingerprint (to_json value)
  let make value = of_json (to_json value)
  let constraints value = value
end

let diagnostic_profile = Diagnostic_text.profile
let operating_domain_subset ~required ~supported =
  let required = Operating_domain.constraints required and supported = Operating_domain.constraints supported in
  let keys = List.map fst required @ List.map fst supported |> List.sort_uniq String.compare in
  List.map (fun key -> match List.assoc_opt key required, List.assoc_opt key supported with
      | Some required, Some supported ->
          let check = domain_subset ~required ~supported in
          fresh check.outcome (List.map (fun reason -> key ^ ": " ^ reason) check.details)
      | _ -> fresh Unknown ["Operating coordinate " ^ Diagnostic_text.repr key ^ " is unspecified."]) keys |> combine

module Port = struct
  type direction = Input | Output
  type scope = Cell | Contact
  type timing = Stateless | Temporal_level | Temporal_event | Unknown_timing
  type t = { id : string; direction : direction; meaning : string; dtype : Type_spec.t;
    unit : string; role : string; scope : scope; compartment : string; timing : timing;
    initialization : Value_domain.t; domain : Value_domain.t }
  let schema_version = "biocompiler.component_port.v0.2"
  let timing_name = function Stateless -> "atomic_snapshot_stateless.v0.1" | Temporal_level -> "atomic_discrete_event_level.v0.1"
    | Temporal_event -> "atomic_discrete_event_event.v0.1" | Unknown_timing -> "unknown"
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["id"; "direction"; "meaning"; "dtype"; "unit"; "role"; "scope"; "compartment"; "timing"; "initialization"; "domain"] value in
    let field key = get ~path key fields in
    let name key = Json.name ~path:(path ^ "/" ^ key) (field key) in
    let direction = match Json.string ~path (field "direction") with "input" -> Input | "output" -> Output
      | _ -> Diagnostic.fail ~path "component_contract" "Port direction must be input or output." in
    let scope = match Json.string ~path (field "scope") with "cell" -> Cell | "contact" -> Contact
      | _ -> Diagnostic.fail ~path "component_contract" "Port scope must be cell or contact." in
    let timing = match name "timing" with
      | "atomic_snapshot_stateless.v0.1" -> Stateless | "atomic_discrete_event_level.v0.1" -> Temporal_level
      | "atomic_discrete_event_event.v0.1" -> Temporal_event | "unknown" -> Unknown_timing
      | _ -> Diagnostic.fail ~path "component_contract" "Unsupported component timing profile." in
    let dtype = dtype ~path:(path ^ "/dtype") (field "dtype") and unit = name "unit" in
    require ~path (timing <> Temporal_event || Type_spec.kind dtype = Type_spec.Condition) "Event interfaces require Boolean values.";
    let initialization = Value_domain.of_json ~path:(path ^ "/initialization") (field "initialization")
    and domain = Value_domain.of_json ~path:(path ^ "/domain") (field "domain") in
    List.iter (fun value -> require ~path (exact_type (Value_domain.dtype value) dtype && Value_domain.unit value = unit)
        "Port domain type/unit disagrees with its interface.") [initialization; domain];
    require ~path ((domain_subset ~required:initialization ~supported:domain).outcome <> Fail) "Initial values fall outside the runtime domain.";
    { id = name "id"; direction; meaning = name "meaning"; dtype; unit; role = name "role";
      scope; compartment = name "compartment"; timing; initialization; domain }
  let to_json value = obj ["id", str value.id;
    "direction", str (match value.direction with Input -> "input" | Output -> "output");
    "meaning", str value.meaning; "unit", str value.unit;
    "role", str value.role; "scope", str (match value.scope with Cell -> "cell" | Contact -> "contact");
    "compartment", str value.compartment; "timing", str (timing_name value.timing);
    "schema_version", str schema_version; "dtype", Type_spec.to_json value.dtype;
    "initialization", Value_domain.to_json value.initialization; "domain", Value_domain.to_json value.domain]
  let fingerprint value = Canonical.fingerprint (to_json value)
  let make ~id ~direction ~meaning ~dtype ~unit ~role ~scope ~compartment ~timing ~initialization ~domain =
    of_json (to_json { id; direction; meaning; dtype; unit; role; scope; compartment; timing; initialization; domain })
  let id value = value.id
  let direction value = value.direction
  let meaning value = value.meaning
  let dtype value = value.dtype
  let unit value = value.unit
  let role value = value.role
  let scope value = value.scope
  let compartment value = value.compartment
  let timing value = value.timing
  let initialization value = value.initialization
  let domain value = value.domain
end

let ports_compatible ~producer ~consumer =
  let checks = ref [] in
  let add value = checks := value :: !checks in
  if Port.direction producer <> Port.Output || Port.direction consumer <> Port.Input then
    add (fresh Fail ["Connections require an output producer and input consumer."]);
  List.iter (fun (key, equal) -> if not equal then add (fresh Fail ["Port " ^ key ^ " differs."])) [
    "meaning", Port.meaning producer = Port.meaning consumer;
    "dtype", exact_type (Port.dtype producer) (Port.dtype consumer);
    "unit", Port.unit producer = Port.unit consumer;
    "role", Port.role producer = Port.role consumer;
    "scope", Port.scope producer = Port.scope consumer;
    "compartment", Port.compartment producer = Port.compartment consumer];
  if Port.timing producer = Port.Unknown_timing || Port.timing consumer = Port.Unknown_timing then
    add (fresh Unknown ["Port timing is unknown."])
  else if Port.timing producer <> Port.timing consumer then add (fresh Fail ["Port timing differs."]);
  add (domain_subset ~required:(Port.domain producer) ~supported:(Port.domain consumer));
  let initial = domain_subset ~required:(Port.initialization producer) ~supported:(Port.initialization consumer) in
  add (fresh initial.outcome (List.map (fun reason -> "Initialization: " ^ reason) initial.details));
  combine (List.rev !checks)

let canonical_synthetic_unit value =
  let value = contract_type value in
  let dimensions = Type_spec.to_json value |> Json.object_fields |> Json.field "dimensions" |> Json.object_fields
      |> List.sort (fun (a, _) (b, _) -> String.compare a b) in
  let dimensions = List.map (fun (key, value) -> key, Json.integer value) dimensions in
  let ints values = List.map (fun (key, value) -> key, Z.of_int value) values in
  if dimensions = [] then "1"
  else if dimensions = ints ["time", 1] then "s"
  else if dimensions = ints ["amount", 1; "length", -3] then "mol/m^3"
  else if dimensions = ints ["amount", 1; "length", -2] then "mol/m^2"
  else if dimensions = ints ["amount", 1; "time", -1] then "mol/s"
  else "canonical:" ^ String.concat ";" (List.map (fun (key, power) -> key ^ "^" ^ Z.to_string power) dimensions)

type synthetic_operation = Input | Constant | And | Or | Not | Compare | Select | Any_contact | Output | Held_for | Onset | Pulse | Memory
let synthetic_operation_of_string = function
  | "input" -> Input | "constant" -> Constant | "and" -> And | "or" -> Or | "not" -> Not
  | "compare" -> Compare | "select" -> Select | "any_contact" -> Any_contact | "output" -> Output
  | "held_for" -> Held_for | "onset" -> Onset | "pulse" -> Pulse | "memory" -> Memory
  | _ -> Diagnostic.fail "component_contract" "Unsupported synthetic domain operation."
let synthetic_operation_name = function Input -> "input" | Constant -> "constant" | And -> "and" | Or -> "or" | Not -> "not"
  | Compare -> "compare" | Select -> "select" | Any_contact -> "any_contact" | Output -> "output"
  | Held_for -> "held_for" | Onset -> "onset" | Pulse -> "pulse" | Memory -> "memory"
let synthetic_output_domain ~operation ~attributes ~inputs ~dtype ?(initialization = false) ?max_contacts () =
  let module V = Value_domain in
  bounded ~path:"/attributes" attributes;
  Diagnostic.require (List.length inputs <= Limits.max_json_nodes) "component_contract_limit" "Too many synthetic input domains.";
  let unit = canonical_synthetic_unit dtype in
  let input index = match List.nth_opt inputs index with Some value -> value
    | None -> Diagnostic.fail "component_contract" "Synthetic abstraction lacks a required input domain." in
  let boolean values = V.boolean ~values:(List.sort_uniq Bool.compare values) () in
  let may_be_true value = List.mem true (V.values value) in
  let may_be_false value = List.mem false (V.values value) in
  let result = match operation with
    | Input -> None
    | Constant ->
        let value = Json.field "value" (Json.object_fields attributes) in
        Some (match value with Json.Bool value -> boolean [value]
          | value -> let constant = Json.field "canonical_value" (Json.object_fields value) |> finite ~path:"/attributes/value/canonical_value" in
              V.interval ~lower:constant ~upper:constant ~dtype ~unit)
    | Held_for when initialization -> Some (boolean [false])
    | _ when List.exists (fun value -> V.kind value = V.Unknown_domain) inputs ->
        Some (V.unknown ~dtype ~unit ~reason:"Executable input domain is unknown.")
    | And -> Some (boolean ((if List.exists may_be_false inputs then [false] else []) @ (if List.for_all may_be_true inputs then [true] else [])))
    | Or -> Some (boolean ((if List.exists may_be_true inputs then [true] else []) @ (if List.for_all may_be_false inputs then [false] else [])))
    | Not -> Some (boolean (List.map not (V.values (input 0))))
    | Compare -> Some (boolean [false; true])
    | Any_contact -> Some (boolean (if may_be_true (input 0) && not (Option.fold ~none:false ~some:(fun value -> N.equal value N.zero) max_contacts)
        then [false; true] else [false]))
    | Select ->
        let branches = List.map (fun condition -> input (if condition then 1 else 2)) (V.values (input 0)) in
        if Type_spec.kind dtype = Type_spec.Condition then Some (boolean (List.concat_map V.values branches))
        else (
          let bounds get = List.map (fun branch -> match get branch with Some value -> value
              | None -> Diagnostic.fail "component_contract" "Scalar branch lacks interval bounds.") branches in
          let fold operation = function first :: rest -> List.fold_left operation first rest
            | [] -> Diagnostic.fail "component_contract" "Synthetic selection requires at least one possible branch." in
          Some (V.interval ~lower:(fold N.min (bounds V.lower)) ~upper:(fold N.max (bounds V.upper)) ~dtype ~unit))
    | Output -> Some (input 0)
    | Held_for | Onset | Pulse ->
        if initialization && (operation = Onset || operation = Pulse) then Some (input 0)
        else Some (boolean (if may_be_true (input 0) then [false; true] else [false]))
    | Memory ->
        if initialization then Some (boolean (List.concat_map (fun setting -> List.map (fun resetting -> setting && not resetting)
            (V.values (input 1))) (V.values (input 0))))
        else Some (boolean [false; true])
  in result

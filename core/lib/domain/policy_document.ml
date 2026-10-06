open Bioc_wire
module S = Policy_schema

let profile = "biocompiler.policy.v0.1"
let max_bytes = 2 * 1024 * 1024
let max_nodes = 100_000
let max_depth = 64
let max_string_bytes = 262_144
let max_number_chars = 256
let max_decimal_exponent = 1024
let require ?path condition message = Diagnostic.require ?path condition "policy_document" message
let limit ?path condition = Diagnostic.require ?path condition "policy_document_limit"
    "Policy document exceeds its frozen-source resource limits."
let decimal_require ~path condition message = Diagnostic.require ~path condition "policy_decimal" message
let escape_path text = String.concat "~1" (String.split_on_char '/' (String.concat "~0" (String.split_on_char '~' text)))
let child path key = path ^ "/" ^ escape_path key
let field path key value = Json.field ~path:(child path key) key (Json.object_fields ~path value)
let text_field path key value = Json.string ~path:(child path key) (field path key value)

(* One structural visit per key or value; list spines consume the same budget.
   This bounds shared DAG occurrences and cyclic caller-constructed lists before
   canonical encoding or schema traversal. Recursive containers exhaust depth. *)
let measure ?(path = "") value =
  let nodes = ref 0 and payload = ref 0 in
  let visit path depth =
    incr nodes; limit ~path (!nodes <= max_nodes && depth <= max_depth) in
  let scalar path amount =
    limit ~path (amount <= max_bytes - !payload); payload := !payload + amount in
  let string path value =
    limit ~path (String.length value <= max_string_bytes);
    Json.validate_utf8 value; scalar path (String.length value) in
  let rec loop path depth = function
    | Json.Null -> visit path depth; scalar path 4
    | Json.Bool value -> visit path depth; scalar path (if value then 4 else 5)
    | Json.Int value ->
        visit path depth;
        limit ~path (Z.numbits value <= 4 * max_number_chars);
        let length = String.length (Z.to_string value) in
        limit ~path (length <= max_number_chars); scalar path length
    | Json.Float _ -> require ~path false "Raw floating point values are forbidden; use exact typed decimal text."
    | Json.String value -> visit path depth; string path value
    | Json.Array values ->
        visit path depth;
        let rec items index = function [] -> () | value :: rest ->
          loop (child path (string_of_int index)) (depth + 1) value; items (index + 1) rest in
        items 0 values
    | Json.Object fields ->
        visit path depth;
        let seen = Hashtbl.create 16 in
        let rec items = function [] -> () | (key, value) :: rest ->
          let at = child path key in
          visit at (depth + 1); string at key;
          require ~path:at (not (Hashtbl.mem seen key)) "Duplicate policy object key.";
          Hashtbl.add seen key ();
          loop at (depth + 1) value; items rest in
        items fields in
  loop path 0 value;
  (match Canonical.encode_bounded ~max_bytes value with
   | _ -> ()
   | exception Diagnostic.Error diagnostic when diagnostic.code = "response_too_large" -> limit ~path false)

(* Parse decimal text lexically and retain its coefficient and base-ten exponent.
   Exponents are parsed as Z first, so an oversized exponent never overflows int.
   No binary floating-point conversion participates in decimal interpretation. *)
let decimal_parts ~path text =
  let length = String.length text in
  decimal_require ~path (length > 0 && length <= max_number_chars)
    "Decimal values require bounded finite decimal text.";
  let position = ref 0 in
  let digit () = !position < length && text.[!position] >= '0' && text.[!position] <= '9' in
  let negative = text.[0] = '-' in
  if negative then incr position;
  let start = !position in
  decimal_require ~path (digit ()) "Decimal text requires integer digits.";
  if text.[!position] = '0' then incr position else while digit () do incr position done;
  let whole = String.sub text start (!position - start) in
  let fraction = if !position < length && text.[!position] = '.' then (
      incr position;
      let start = !position in
      decimal_require ~path (digit ()) "Decimal point requires fractional digits.";
      while digit () do incr position done;
      String.sub text start (!position - start)) else "" in
  let exponent = if !position < length && (text.[!position] = 'e' || text.[!position] = 'E') then (
      incr position;
      let start = !position in
      if !position < length && (text.[!position] = '-' || text.[!position] = '+') then incr position;
      decimal_require ~path (digit ()) "Decimal exponent requires digits.";
      while digit () do incr position done;
      Z.of_string (String.sub text start (!position - start))) else Z.zero in
  decimal_require ~path (!position = length) "Decimal text is outside the finite decimal grammar.";
  let exponent = Z.sub exponent (Z.of_int (String.length fraction)) in
  decimal_require ~path (Z.compare (Z.abs exponent) (Z.of_int max_decimal_exponent) <= 0)
    "Decimal value exceeds its finite exponent bound.";
  let digits = whole ^ fraction in
  let coefficient = Z.of_string ((if negative then "-" else "") ^ digits) in
  coefficient, Z.to_int exponent

let exact_decimal ?(path = "") text =
  let coefficient, exponent = decimal_parts ~path text in
  let power = Z.pow (Z.of_int 10) (abs exponent) in
  if exponent >= 0 then Q.of_bigint (Z.mul coefficient power) else Q.make coefficient power

let canonical_quantity ~path text =
  let coefficient, exponent = decimal_parts ~path text in
  if Z.equal coefficient Z.zero then "0" else (
    let digits = Z.to_string (Z.abs coefficient) in
    decimal_require ~path (abs (String.length digits + exponent - 1) <= max_decimal_exponent)
      "Quantity exceeds its adjusted decimal exponent bound.";
    let point = String.length digits + exponent in
    let absolute =
      if point <= 0 then "0." ^ String.make (-point) '0' ^ digits
      else if point >= String.length digits then digits ^ String.make (point - String.length digits) '0'
      else String.sub digits 0 point ^ "." ^ String.sub digits point (String.length digits - point) in
    let absolute = if String.contains absolute '.' then (
        let length = ref (String.length absolute) in
        while !length > 0 && absolute.[!length - 1] = '0' do decr length done;
        if !length > 0 && absolute.[!length - 1] = '.' then decr length;
        String.sub absolute 0 !length) else absolute in
    let result = (if Z.sign coefficient < 0 then "-" else "") ^ absolute in
    decimal_require ~path (String.length result <= max_number_chars)
      "Canonical quantity spelling exceeds its character bound.";
    result)

let valid_digest text = String.length text = 64 &&
  String.for_all (function '0' .. '9' | 'a' .. 'f' -> true | _ -> false) text

(* Match the caller's Unicode whitespace boundary, not only ASCII trim. The
   enclosing document has already passed strict UTF-8 measurement. *)
let nonblank_text value =
  let byte index = Char.code value.[index] in
  let rec visit index =
    if index = String.length value then false else
    let lead = byte index in
    let width, point =
      if lead < 0x80 then 1, lead
      else if lead < 0xe0 then 2, ((lead land 0x1f) lsl 6) lor (byte (index + 1) land 0x3f)
      else if lead < 0xf0 then 3, ((lead land 0x0f) lsl 12) lor ((byte (index + 1) land 0x3f) lsl 6) lor (byte (index + 2) land 0x3f)
      else 4, ((lead land 0x07) lsl 18) lor ((byte (index + 1) land 0x3f) lsl 12) lor ((byte (index + 2) land 0x3f) lsl 6) lor (byte (index + 3) land 0x3f) in
    let whitespace = (point >= 0x09 && point <= 0x0d) || (point >= 0x1c && point <= 0x20)
      || List.mem point [0x85;0xa0;0x1680;0x2028;0x2029;0x202f;0x205f;0x3000]
      || (point >= 0x2000 && point <= 0x200a) in
    if whitespace then visit (index + width) else true in
  visit 0

let rec validate_shape ~path shape value =
  let mismatch () = require ~path false "Policy value does not match its exact declared field type." in
  match shape, value with
  | S.String, Json.String _ | S.Integer, Json.Int _ | S.Boolean, Json.Bool _ | S.Null, Json.Null -> ()
  | S.Literals choices, Json.String value ->
      require ~path (List.mem value choices) "Policy value is outside its declared literal alternatives."
  | S.Many shape, Json.Array values ->
      List.iteri (fun index value -> validate_shape ~path:(child path (string_of_int index)) shape value) values
  | S.Tuple shapes, Json.Array values ->
      require ~path (List.length shapes = List.length values) "Policy tuple has the wrong number of elements.";
      List.iteri (fun index (shape, value) -> validate_shape ~path:(child path (string_of_int index)) shape value)
        (List.combine shapes values)
  | S.Union choices, value ->
      let rec choose = function
        | [] -> mismatch ()
        | shape :: rest ->
            (match validate_shape ~path shape value with () -> ()
             | exception Diagnostic.Error _ -> choose rest) in
      choose choices
  | S.Record name, Json.Object fields ->
      require ~path (name <> "PolicyDraft" && name <> "Hole") "Frozen policy ingress rejects drafts and unresolved holes.";
      let members = match S.find name with Some members -> members
        | None -> Diagnostic.fail ~path "policy_document" "Unknown policy record kind." in
      let expected = "$type" :: List.map fst members in
      require ~path (List.length fields = List.length expected && List.for_all (fun key -> List.mem_assoc key fields) expected)
        "Policy declaration has unknown or missing fields.";
      require ~path (List.assoc "$type" fields = Json.String name) "Unknown or incompatible policy record tag.";
      List.iter (fun (key, shape) -> validate_shape ~path:(child path key) shape (List.assoc key fields)) members;
      if List.mem name ["PolicyProgram"; "BuildRequest"; "CompilationSubmission"; "SemanticBundle"] then
        require ~path:(child path "profile") (List.assoc "profile" fields = Json.String profile)
          "Unsupported policy profile.";
      if name = "Unit" then ignore (exact_decimal ~path:(child path "scale") (text_field path "scale" value));
      if name = "Quantity" then (
        let amount = text_field path "amount" value in
        decimal_require ~path:(child path "amount") (canonical_quantity ~path:(child path "amount") amount = amount)
          "Frozen Quantity.amount requires canonical fixed decimal spelling; normalize during authoring before submission.");
      (match List.assoc_opt "assumptions" fields with
       | Some (Json.Array values) -> List.iteri (fun index item ->
           require ~path:(child (child path "assumptions") (string_of_int index))
             (nonblank_text (Json.string item)) "Assumptions must contain nonblank text.") values
       | _ -> ());
      if name = "Requirement" && text_field path "kind" value = "assumption" then
        require ~path:(child path "description") (nonblank_text (text_field path "description" value))
          "Assumption requirements must contain nonblank text.";
      if name = "DefinitionRef" then (
        List.iter (fun key -> require ~path:(child path key) (nonblank_text (text_field path key value))
          "Definition reference identities and versions must contain nonblank text.") ["id";"version"];
        require ~path:(child path "digest") (valid_digest (text_field path "digest" value))
          "Definition references require a lowercase SHA-256 digest.")
  | _ -> mismatch ()

let document_digest value =
  measure value;
  let rec remove = function
    | Json.Object fields -> Json.Object (List.filter_map (fun (key, value) ->
        if key = "source_map" || key = "provenance" then None else Some (key, remove value)) fields)
    | Json.Array values -> Json.Array (List.map remove values)
    | value -> value in
  Canonical.sha256 (Canonical.encode_bounded ~max_bytes (remove value))

type kind = Program | Request | Submission

type declaration_kind =
  | Role | Subject | Encounter | Spatial_scope | Clock | Observation
  | State_store | Effect | Rule | Machine | Transition | Channel | Message
  | Requirement | Parameter

type declaration = { kind : declaration_kind; id : string; path : string; value : Json.t }
type t = { json : Json.t; document_kind : kind; program_json : Json.t;
  request_json : Json.t option; declaration_values : declaration list;
  document_identity : string; artifact_identity : string }

let declaration_kind = function
  | "Role" -> Role | "Subject" -> Subject | "Encounter" -> Encounter
  | "SpatialScope" -> Spatial_scope | "Clock" -> Clock | "Observation" -> Observation
  | "StateStore" -> State_store | "Effect" -> Effect | "Rule" -> Rule | "Machine" -> Machine
  | "Transition" -> Transition | "Channel" -> Channel | "Message" -> Message
  | "Requirement" -> Requirement | "Parameter" -> Parameter
  | _ -> Diagnostic.fail "policy_document" "Unexpected policy declaration kind."

let dependencies value =
  let refs = ref [] in
  let rec visit = function
    | Json.Object fields as value ->
        if List.assoc_opt "$type" fields = Some (Json.String "DefinitionRef") then
          refs := (text_field "" "id" value, text_field "" "version" value, text_field "" "digest" value) :: !refs
        else List.iter (fun (key, value) -> if key <> "source_map" then visit value) fields
    | Json.Array values -> List.iter visit values
    | _ -> () in
  visit value;
  List.sort_uniq Stdlib.compare !refs

let verify_submission ~path json request program =
  let verified at condition message = Diagnostic.require ~path:at condition "policy_document_digest" message in
  let compare_digest key value =
    let expected = document_digest value in
    verified (child path key) (text_field path key json = expected)
      ("Submission " ^ key ^ " does not identify its contained document.") in
  compare_digest "document_digest" request;
  compare_digest "program_digest" program;
  let pin key value =
    let reference = field path key json in
    verified (child path key)
      (text_field path "id" reference = text_field path "id" value &&
       text_field path "version" reference = text_field path "version" value &&
       text_field path "digest" reference = document_digest value)
      ("Submission " ^ key ^ " pin differs from its contained definition.") in
  pin "semantic_bundle" (field path "semantics" program);
  pin "implementation_catalog" (field path "implementations" request);
  let recorded = Json.array (field path "dependencies" json) |> List.map (fun value ->
      text_field path "id" value, text_field path "version" value, text_field path "digest" value) in
  verified (child path "dependencies") (recorded = dependencies request)
    "Submission dependency pins must exactly match the sorted, unique contained dependency inventory."

let of_json ?(path = "") json =
  measure ~path json;
  let tag = text_field path "$type" json in
  let document_kind = match tag with
    | "PolicyProgram" -> Program | "BuildRequest" -> Request | "CompilationSubmission" -> Submission
    | _ -> Diagnostic.fail ~path "policy_document" "Expected a frozen PolicyProgram, BuildRequest or CompilationSubmission." in
  validate_shape ~path (S.Record tag) json;
  let request_json, program_json, program_path = match document_kind with
    | Program -> None, json, path
    | Request -> Some json, field path "program" json, child path "program"
    | Submission ->
        let request = field path "request" json in
        Some request, field (child path "request") "program" request, child (child path "request") "program" in
  (match document_kind, request_json with
   | Submission, Some request -> verify_submission ~path json request program_json
   | _ -> ());
  let declaration_values = Json.array (field program_path "declarations" program_json) |> List.mapi (fun index value ->
      let path = child (child program_path "declarations") (string_of_int index) in
      {kind = declaration_kind (text_field path "$type" value); id = text_field path "id" value; path; value}) in
  let document_identity = document_digest (match request_json with Some request -> request | None -> program_json) in
  let artifact_identity = Canonical.sha256 (Canonical.encode_bounded ~max_bytes json) in
  {json; document_kind; program_json; request_json; declaration_values; document_identity; artifact_identity}

let to_json value = value.json
let kind value = value.document_kind
let program value = value.program_json
let request value = value.request_json
let declarations value = value.declaration_values
let fingerprint value = value.document_identity
let artifact_digest value = value.artifact_identity

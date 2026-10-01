open Bioc_wire

type kind = Model | Reference | Registry | Source | Evidence
type t = { kind : kind; id : string; version : string; content_fingerprint : string }
let schema_version = "biocompiler.component_identity.v0.1"
let encode_kind = function
  | Model -> "model" | Reference -> "reference" | Registry -> "registry"
  | Source -> "source" | Evidence -> "evidence"
let decode_kind ~path = function
  | "model" -> Model | "reference" -> Reference | "registry" -> Registry
  | "source" -> Source | "evidence" -> Evidence
  | _ -> Diagnostic.fail ~path "invalid_identity_kind" "Unsupported component identity kind."
let bounded_text ~path value =
  let value = Json.string ~path value in
  Diagnostic.require ~path (String.length value <= Limits.max_string_bytes)
    "identity_resource_limit" "Pinned identity text exceeds the native wire string bound.";
  Json.name ~path (Json.String value)
let encoded_string_bytes text =
  String.fold_left (fun total character -> total + (match character with
      | '"' | '\\' | '\b' | '\012' | '\n' | '\r' | '\t' -> 2
      | value when Char.code value < 32 -> 6
      | _ -> 1)) 2 text
let of_json ?(path = "") value =
  let fields = Json.object_fields ~path value in
  let keys = ["schema_version"; "kind"; "id"; "version"; "content_fingerprint"] in
  (* At most five distinct permitted keys can be visited. This also bounds raw
     native cyclic list spines before generic field helpers enumerate them. *)
  let rec preflight seen = function
    | [] -> ()
    | (key, _) :: remaining ->
        Diagnostic.require ~path (List.mem key keys) "unknown_field" "Unknown pinned identity field.";
        Diagnostic.require ~path (not (List.mem key seen)) "duplicate_key" "Duplicate pinned identity field.";
        preflight (key :: seen) remaining in
  preflight [] fields;
  Json.exact_fields ~path keys fields;
  let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
  Diagnostic.require ~path:(path ^ "/schema_version")
    (Json.string (get "schema_version") = schema_version) "unsupported_identity_schema"
    "Unsupported pinned identity schema.";
  let kind = Json.string ~path:(path ^ "/kind") (get "kind") |> decode_kind ~path:(path ^ "/kind") in
  let id = bounded_text ~path:(path ^ "/id") (get "id")
  and version = bounded_text ~path:(path ^ "/version") (get "version") in
  let content_fingerprint = Json.string ~path:(path ^ "/content_fingerprint") (get "content_fingerprint") in
  Diagnostic.require ~path:(path ^ "/content_fingerprint")
    (String.length content_fingerprint = 64 && String.for_all
       (function '0' .. '9' | 'a' .. 'f' -> true | _ -> false) content_fingerprint)
    "invalid_identity_fingerprint" "Pinned identity requires a lowercase SHA-256 content fingerprint.";
  let strings = ["schema_version", schema_version; "kind", encode_kind kind;
    "id", id; "version", version; "content_fingerprint", content_fingerprint] in
  let bytes = List.fold_left (fun total (key, value) ->
      total + encoded_string_bytes key + 1 + encoded_string_bytes value) 6 strings in
  Diagnostic.require ~path (bytes <= Limits.max_response_bytes) "identity_resource_limit"
    "Pinned identity exceeds the native canonical output bound.";
  { kind; id; version; content_fingerprint }
let to_json value = Json.Object [
    "schema_version", Json.String schema_version; "kind", Json.String (encode_kind value.kind);
    "id", Json.String value.id; "version", Json.String value.version;
    "content_fingerprint", Json.String value.content_fingerprint]
let make ~kind ~id ~version ~content_fingerprint =
  of_json (to_json { kind; id; version; content_fingerprint })
let fingerprint value = Canonical.fingerprint (to_json value)
let kind value = value.kind
let kind_name value = encode_kind value.kind
let id value = value.id
let version value = value.version
let content_fingerprint value = value.content_fingerprint

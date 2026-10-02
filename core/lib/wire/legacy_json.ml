type profile = Artifact | Reference
let code = function Artifact->"legacy_artifact_json" | Reference->"legacy_reference_json"
let parse ?on_node ~max_bytes ~max_nodes ~profile text =
  let on_duplicate_key key =
    Diagnostic.fail (code profile) (match profile with
      | Artifact -> "Duplicate JSON key: "^key^"."
      | Reference -> "Invalid reference JSON: Duplicate JSON field: "^key^".") in
  let on_nonfinite token =
    Diagnostic.fail (code profile) (match profile with
      | Artifact -> "Invalid JSON number: "^token^"."
      | Reference -> "Invalid reference JSON: Invalid number: "^token) in
  Json.parse_legacy_artifact ?on_node ~on_duplicate_key ~on_nonfinite ~max_bytes ~max_nodes text

let pretty_utf8 value =
  (* ASCII escaping is at least as large as UTF-8 spelling, giving a safe
     preallocation bound with the same indentation and container structure. *)
  let maximum=Legacy_ascii.measure ~layout:(Legacy_ascii.Indented 2) value in
  let buffer=Buffer.create (min 4096 maximum.bytes) in
  let append text =
    Diagnostic.require (String.length text<=maximum.bytes-Buffer.length buffer)
      "legacy_json_limit" "Legacy UTF-8 JSON exceeds its bounded spelling.";
    Buffer.add_string buffer text in
  let newline depth=append "\n";append (String.make (2*depth) ' ') in
  let rec write depth = function
    | Json.Array values ->
        append "[";sequence depth (write (depth+1)) values;append "]"
    | Json.Object fields ->
        append "{";
        sequence depth (fun (key,value) ->
          append (Canonical.encode (Json.String key));append ": ";write (depth+1) value)
          (List.sort (fun (left,_) (right,_) -> String.compare left right) fields);
        append "}"
    | scalar -> append (Canonical.encode scalar)
  and sequence : 'a. int -> ('a -> unit) -> 'a list -> unit = fun depth emit values ->
    match values with
    | [] -> ()
    | first::rest ->
        newline (depth+1);emit first;
        List.iter (fun value -> append ",";newline (depth+1);emit value) rest;
        newline depth in
  write 0 value;Buffer.contents buffer

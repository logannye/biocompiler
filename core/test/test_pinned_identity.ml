open Bioc_wire
module Pin = Bioc_domain.Pinned_identity

let require condition message = if not condition then failwith message
let get key value = Json.field key (Json.object_fields value)
let set key replacement value = Json.Object ((key, replacement) :: List.remove_assoc key (Json.object_fields value))
let reject label code operation =
  match operation () with
  | _ -> failwith (label ^ ": invalid pin accepted")
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code = code) (label ^ ": expected " ^ code ^ ", got " ^ diagnostic.code)
let literal () =
  Pin.make ~kind:Pin.Source ~id:"retained-source" ~version:"1" ~content_fingerprint:(String.make 64 'a')
let () =
  let pin = literal () in
  let json = Pin.to_json pin in
  require (Pin.kind pin = Pin.Source && Pin.kind_name pin = "source"
    && Pin.id pin = "retained-source" && Pin.version pin = "1"
    && Pin.content_fingerprint pin = String.make 64 'a') "Typed pinned identity changed";
  require (Pin.fingerprint pin = "a0af3016f368c2a2e974c1c7393f51bbeb58aea5cecc9ff9783e146dc86bb504")
    "Literal canonical identity changed";
  List.iter (fun (kind, name) ->
      let pin = Pin.make ~kind ~id:"shared" ~version:"v1" ~content_fingerprint:(String.make 64 '0') in
      require (Pin.kind_name pin = name && Pin.kind (Pin.of_json (Pin.to_json pin)) = kind)
        "Closed kind did not roundtrip")
    [Pin.Model, "model"; Pin.Reference, "reference"; Pin.Registry, "registry"; Pin.Source, "source"; Pin.Evidence, "evidence"];
  List.iter (fun (key, replacement) ->
      let changed = Pin.of_json (set key (Json.String replacement) json) in
      require (Pin.fingerprint changed <> Pin.fingerprint pin) ("Pin identity omitted " ^ key))
    ["kind", "evidence"; "id", "changed"; "version", "2"; "content_fingerprint", String.make 64 'b'];
  let spaced = Pin.make ~kind:Pin.Source ~id:" source " ~version:"\0001 " ~content_fingerprint:(String.make 64 'a') in
  require (Pin.id spaced = " source " && Pin.version spaced = "\0001 ")
    "General pin name was normalized or narrowed to molecular text rules";
  require (Json.equal json (Pin.to_json (Pin.of_json json))) "Full pin roundtrip differs";
  List.iter (fun key ->
      reject ("missing " ^ key) "missing_field" (fun () ->
          Pin.of_json (Json.Object (List.remove_assoc key (Json.object_fields json))));
      reject ("wrong type " ^ key) "invalid_type" (fun () -> Pin.of_json (set key Json.Null json)))
    ["schema_version"; "kind"; "id"; "version"; "content_fingerprint"];
  reject "extra authority" "unknown_field" (fun () -> Pin.of_json (set "verified" (Json.Bool true) json));
  reject "duplicate authority" "duplicate_key" (fun () ->
      Pin.of_json (Json.Object (("id", Json.String "forged") :: Json.object_fields json)));
  reject "cyclic native field spine" "duplicate_key" (fun () ->
      let rec fields = ("id", Json.String "cycle") :: fields in
      Pin.of_json (Json.Object fields));
  reject "unsupported schema" "unsupported_identity_schema" (fun () -> Pin.of_json (set "schema_version" (Json.String "future") json));
  reject "unknown kind" "invalid_identity_kind" (fun () -> Pin.of_json (set "kind" (Json.String "accepted") json));
  List.iter (fun value -> reject "blank identity" "invalid_name" (fun () ->
      Pin.of_json (set "id" (Json.String value) json))) [""; "\194\160\227\128\128"; " \n\t"];
  reject "invalid UTF-8" "invalid_utf8" (fun () -> Pin.of_json (set "id" (Json.String "bad\192\128") json));
  List.iter (fun value -> reject "content pin" "invalid_identity_fingerprint" (fun () ->
      Pin.of_json (set "content_fingerprint" (Json.String value) json)))
    [String.make 64 'A'; String.make 63 'a'; String.make 65 'a'; String.make 64 'g'];
  reject "native string bound" "identity_resource_limit" (fun () ->
      Pin.of_json (set "id" (Json.String (String.make (Limits.max_string_bytes + 1) 'x')) json));
  reject "escaped native output bound" "identity_resource_limit" (fun () ->
      Pin.make ~kind:Pin.Source ~id:(String.make Limits.max_string_bytes '\000')
        ~version:(String.make Limits.max_string_bytes '\000') ~content_fingerprint:(String.make 64 'a'));
  require (get "content_fingerprint" json = Json.String (String.make 64 'a')) "Declared dependency pin was replaced";
  print_endline "pinned identity: all five kinds, exact canonical authority and strict rejection/resource bounds checked"

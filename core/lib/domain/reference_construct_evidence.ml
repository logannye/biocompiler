open Bioc_wire
module Codec = Verification_exploration.Codec
let default_limits = Codec.make_limits ~max_bytes:Limits.max_response_bytes ~max_nodes:Limits.max_json_nodes ()
type status = Realization_evidence.outcome = Pass | Fail | Unknown | Unsupported
let checker_version = "biocompiler.construct_checker.v0.2"
let claim_scope = "Exact layout and source correspondence of the selected whole reference CDS, with component compatibility conditional on locked declarations only. No sequence emission, complete delivered payload, molecular behavior, same-cell coexistence, or empirical efficacy is established."
let status_name = function Pass -> "pass" | Fail -> "fail" | Unknown -> "unknown" | Unsupported -> "unsupported"
let require ?path condition message = Diagnostic.require ?path condition "reference_construct_evidence" message
let status path = function
  | Json.String "pass" -> Pass | Json.String "fail" -> Fail
  | Json.String "unknown" -> Unknown | Json.String "unsupported" -> Unsupported
  | _ -> Diagnostic.fail ~path "reference_construct_evidence" "Invalid construct outcome."
let priority values = if List.mem Fail values then Fail else if List.mem Unsupported values then Unsupported
  else if List.mem Unknown values then Unknown else Pass
let str value = Json.String value
let option encode = function None -> Json.Null | Some value -> encode value
let optional decode = function Json.Null -> None | value -> Some (decode value)
let fields limits path label keys raw = Codec.preflight ~limits ~path raw;
  let fields = match raw with Json.Object fields -> fields | _ ->
    Diagnostic.fail ~path "reference_construct_evidence" ("Invalid fields in "^label^".") in
  require ~path (List.sort String.compare(List.map fst fields)=List.sort String.compare keys)
    ("Invalid fields in "^label^"."); fields
let get path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let name path label raw =
  let failure ()=Diagnostic.fail ~path "reference_construct_evidence" (label^" must be a nonempty string.") in
  match raw with Json.String _->(try Json.name ~path raw with Diagnostic.Error error when error.code="invalid_name"->failure())
  |_->failure()
let names path label raw =
  let values=match raw with Json.Array values->List.map(name path label)values
    |_->Diagnostic.fail ~path "reference_construct_evidence" (label^" must be an array.") in
  let seen=Hashtbl.create 8 in List.iter(fun value->
    require ~path (not(Hashtbl.mem seen value))(label^" must be unique.");Hashtbl.add seen value ())values;values
let hash path label raw =
  let valid=match raw with Json.String value->String.length value=64 && String.for_all(function '0'..'9'|'a'..'f'->true|_->false)value|_->false in
  require ~path valid ("Invalid "^label^" fingerprint.");Json.string raw
type packed = { json:Json.t; fingerprint:string; size:int }
let pack limits json = let encoded = Codec.encode ~limits json in Codec.charge limits (String.length encoded);
  {json;fingerprint=Canonical.sha256 encoded;size=String.length encoded}
let bounded_map limits size encode values =
  let maximum = Json.object_fields (Codec.limits_json limits) in
  let bytes = Z.to_int (Json.integer (Json.field "max_bytes" maximum))
  and nodes = Z.to_int (Json.integer (Json.field "max_nodes" maximum)) in
  let rec loop count used = function [] -> () | value::rest ->
    Codec.charge limits 1;
    Diagnostic.require (count < nodes && size value <= bytes-used) "reference_construct_evidence_limit" "Reference evidence exceeds its bounded array inventory.";
    loop (count+1) (used+size value) rest in
  loop 0 2 values; List.map encode values
let parse_text limits text=
  let bounds=Json.object_fields(Codec.limits_json limits) in
  let max_bytes=Z.to_int(Json.integer(Json.field "max_bytes" bounds)) in
  let max_nodes=Z.to_int(Json.integer(Json.field "max_nodes" bounds)) in
  Diagnostic.require(String.length text<=max_bytes) "reference_text_limit" "Reference JSON text exceeds its byte bound.";
  Codec.charge limits(16*String.length text+8*max_nodes);
  Legacy_json.parse ~max_bytes ~max_nodes ~profile:Legacy_json.Artifact text
module Diagnostic = struct
  type t = { packed:packed; status:status; code:string; message:string; instance_id:string option;
    molecule_id:string option; requirement_ids:string list; source:Behavior.source_location option }
  let of_json ?(limits=default_limits) ?(path="") raw =
    let f = fields limits path "ConstructDiagnostic" ["status";"code";"message";"instance_id";"molecule_id";"requirement_ids";"source"] raw in
    let get key = get path key f in
    let source=Reference_construct.source_of_json ~limits (get "source") in
    let value=match get "status" with Json.String "fail"->Fail|Json.String "unsupported"->Unsupported|Json.String "unknown"->Unknown
      |_->Bioc_wire.Diagnostic.fail ~path "reference_construct_evidence" "Invalid construct diagnostic status." in
    let code=name path "Diagnostic code" (get "code") in
    let message=name path "Diagnostic message" (get "message") in
    let instance_id=optional(name path "instance_id")(get "instance_id") in
    let molecule_id=optional(name path "molecule_id")(get "molecule_id") in
    let requirement_ids=names path "Diagnostic requirements" (get "requirement_ids") in
    {packed=pack limits raw;status=value;code;message;instance_id;molecule_id;requirement_ids;source}
  let make ?(limits=default_limits) ~status ~code ~message ?instance_id ?molecule_id
      ?(requirement_ids=[]) ?source () =
    let ids=bounded_map limits String.length str requirement_ids in
    of_json ~limits (Json.Object ["status",str(status_name status);"code",str code;"message",str message;
      "instance_id",option str instance_id;"molecule_id",option str molecule_id;
      "requirement_ids",Json.Array ids;"source",Reference_construct.source_to_json source])
  let to_json value=value.packed.json
  let canonical_size value=value.packed.size
  let status value=value.status
  let code value=value.code
  let message value=value.message
  let instance_id value=value.instance_id
  let molecule_id value=value.molecule_id
  let requirement_ids value=value.requirement_ids
  let source value=value.source
end
module Dependencies = struct
  type t = packed
  let of_json ?(limits=default_limits) ?(path="") raw =
    let hashes=["request";"candidate";"layout";"composition";"registry";"registry_lock";"target"] in
    let f=fields limits path "Construct dependencies" (hashes@["references";"checker";"linker";"reference_adapter";"admission_policy"]) raw in
    List.iter (fun key->ignore(hash (path^"/"^key) key (get path key f))) hashes;
    List.iter (fun(key,version)->require ~path (Json.equal (get path key f) (str version)) ("Unsupported "^key^" version."))
      ["checker",checker_version;"admission_policy","biocompiler.human_admission_policy.v0.1";
       "linker",Composition_evidence.checker_version;"reference_adapter","biocompiler.reference_component.v0.1"];
    let references=match get path "references" f with Json.Object fields->fields|_->
      Bioc_wire.Diagnostic.fail ~path "reference_construct_evidence" "Reference dependency identities must be a mapping." in
    List.iter(fun(key,value)->ignore(name path "Reference dependency" (str key));ignore(hash path "reference" value))references;
    pack limits raw
  let to_json value=value.json
  let fingerprint value=value.fingerprint
  let canonical_size value=value.size
  let changed ?(limits=default_limits) left right=
    Codec.preflight ~limits left.json;Codec.preflight ~limits right.json;
    Json.object_fields right.json |> List.filter_map(fun(key,value)->
      let actual=Codec.encode ~limits value in
      let expected=Codec.encode ~limits(Json.field key(Json.object_fields left.json)) in
      Codec.charge limits(String.length actual+String.length expected+String.length key+1);
      if String.equal actual expected then None else Some key) |> List.sort String.compare

end
module Result = struct
  type t={packed:packed;outcome:status;dependencies:Dependencies.t;checked_requirement_ids:string list;diagnostics:Diagnostic.t list}
  let schema_version="biocompiler.construct_result.v0.2"
  let of_json ?(limits=default_limits) ?(path="") raw =
    let f=fields limits path "ConstructResult" ["schema_version";"outcome";"dependencies";"checked_requirement_ids";"diagnostics";"claim_scope"] raw in
    let get key=get path key f in
    require ~path (Json.equal (get "schema_version") (str schema_version)) "Unsupported construct result schema.";
    let outcome=status path (get "outcome") in
    let raw_diagnostics=match get "diagnostics" with Json.Array values->values|_->
      Bioc_wire.Diagnostic.fail ~path "reference_construct_evidence" "Construct diagnostics must be an array." in
    let diagnostics=List.map(Diagnostic.of_json ~limits)raw_diagnostics in
    let dependencies=Dependencies.of_json ~limits (get "dependencies") in
    let checked_requirement_ids=names path "Checked requirements" (get "checked_requirement_ids") in
    require ~path (outcome=priority(List.map Diagnostic.status diagnostics)) "Construct outcome disagrees with its diagnostics.";
    require ~path (Json.equal (get "claim_scope") (str claim_scope)) "Invalid construct claim scope.";
    {packed=pack limits raw;outcome;dependencies;checked_requirement_ids;diagnostics}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path(parse_text limits text)
  let make ?(limits=default_limits) ~outcome ~dependencies ~checked_requirement_ids ?(diagnostics=[]) ?(claim_scope=claim_scope) () =
    let ids=bounded_map limits String.length str checked_requirement_ids
    and diagnostics=bounded_map limits Diagnostic.canonical_size Diagnostic.to_json diagnostics in
    of_json ~limits (Json.Object["schema_version",str schema_version;"outcome",str(status_name outcome);
      "dependencies",Dependencies.to_json dependencies;"checked_requirement_ids",Json.Array ids;
      "diagnostics",Json.Array diagnostics;"claim_scope",str claim_scope])
  let to_json value=value.packed.json
  let fingerprint value=value.packed.fingerprint
  let canonical_size value=value.packed.size
  let outcome value=value.outcome
  let passed value=value.outcome=Pass
  let dependencies value=value.dependencies
  let diagnostics value=value.diagnostics
  let checked_requirement_ids value=value.checked_requirement_ids
  let freshness ?limits value current=Realization_evidence.Freshness_report.make(Dependencies.changed ?limits value.dependencies current)
end

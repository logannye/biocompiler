open Bioc_wire
module C = Verification_exploration.Codec
module N = Runtime_number
module F = Execution_data.Input_frame
module S = Execution_data.Sample
module A = Synthetic_authority
let schema_version = "biocompiler.synthetic_build_request.v0.2"
let history_schema_version = "biocompiler.synthetic_history.v0.1"
let str value = Json.String value
let obj value = Json.Object value
let require ?path condition message = Diagnostic.require ?path condition "synthetic_build_request" message
let fail ?path message = Diagnostic.fail ?path "synthetic_build_request" message
let record limits path label keys raw =
  C.preflight ~limits ~path raw;
  match raw with
  | Json.Object fields ->
      C.charge limits (256 * (List.length keys+1));
      require ~path (List.sort String.compare (List.map fst fields)=List.sort String.compare keys)
        ("Invalid fields in " ^ label ^ ".");fields
  | _ -> fail ~path ("Invalid fields in " ^ label ^ ".")
let get path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let evaluation_fail path message = fail ~path ("Invalid SyntheticHistory: " ^ message)
let finite path label = function
  | Json.Int value ->
      if not (Float.is_finite (Z.to_float value)) then evaluation_fail path (label ^ " must be finite.");N.Integer value
  | Json.Float value ->
      if not (Float.is_finite value) then evaluation_fail path (label ^ " must be finite.");N.Real value
  | _ -> evaluation_fail path (label ^ " must be a finite real number, not a Boolean.")
let named path label raw =
  try Json.name ~path raw with Diagnostic.Error error when error.code="invalid_type" || error.code="invalid_name" ->
    fail ~path (label ^ " must be a nonempty string.")
let sample limits path raw =
  let fields = record limits path "SignalSample" ["value";"present";"high";"low"] raw in
  let value = match get path "value" fields with Json.Null -> None | raw -> Some (finite path "Signal value" raw) in
  let band key = match get path key fields with
    | Json.Null -> None | Json.Bool value -> Some value
    | _ -> evaluation_fail path ("Signal " ^ key ^ " must be a Boolean or None.") in
  let present = band "present" in let high = band "high" in let low = band "low" in
  S.make ?value ?present ?high ?low ()
let signals_decode limits path raw = match raw with
  | Json.Object fields -> List.map (fun (key,raw) -> key,sample limits (path^"/"^key) raw) fields
  | _ -> fail ~path "History signals must be an object."
let frame limits path raw =
  let fields = record limits path "InputFrame" ["time";"signals";"contacts"] raw in
  let contacts = match get path "contacts" fields with Json.Object fields -> fields
    | _ -> fail ~path "History contacts must be an object." in
  (* Python evaluates every sample constructor before entering InputFrame. *)
  let signals = signals_decode limits (path^"/signals") (get path "signals" fields) in
  let contacts = List.map (fun (key,raw) -> key,signals_decode limits (path^"/contacts/"^key) raw) contacts in
  let time = finite path "Input time" (get path "time" fields) in
  if N.compare time N.zero<0 then evaluation_fail path "Input time must be nonnegative.";
  let evaluation_name label key = try ignore (Json.name ~path (str key)) with
    Diagnostic.Error error when error.code="invalid_name" -> evaluation_fail path (label ^ " must be a nonempty string.") in
  List.iter (fun (key,_) -> evaluation_name "Signal node ID" key) signals;
  List.iter (fun (key,values) ->
    evaluation_name "Contact identity" key;
    List.iter (fun (key,_) -> evaluation_name "Signal node ID" key) values) contacts;
  F.make ~time ~signals ~contacts ()
let history_decode limits retain_history path raw =
  let fields = record limits path "SyntheticHistory" ["schema_version";"frames"] raw in
  require ~path (get path "schema_version" fields=str history_schema_version) "Unsupported SyntheticHistory schema.";
  let raw_frames = match get path "frames" fields with Json.Array values -> values
    | _ -> fail ~path "History frames must be an array." in
  retain_history (List.length raw_frames);
  let frames = List.mapi (fun index raw -> frame limits (path^"/frames/"^string_of_int index) raw) raw_frames in
  require ~path (frames<>[]) "A synthetic build needs a nonempty history.";
  require ~path (N.equal (F.time (List.hd frames)) N.zero) "A synthetic build history must begin at zero.";
  let rec ordered = function first :: (next :: _ as rest) ->
      require ~path (N.compare (F.time first) (F.time next)<0) "History times must be strictly increasing.";ordered rest
    | _ -> () in
  ordered frames;frames
let config_decode limits path raw =
  let fields = record limits path "SyntheticGeneratorConfig"
    ["schema_version";"profile_version";"generator_version";"catalog_fingerprint";"witness_selection";"conjunction_strategy"] raw in
  require ~path (get path "schema_version" fields=str A.Config.schema_version) "Unsupported generator-config schema.";
  let hash = get path "catalog_fingerprint" fields in
  require ~path (match hash with Json.String value -> String.length value=64 &&
    String.for_all (function '0'..'9'|'a'..'f' -> true | _ -> false) value | _ -> false)
    "Catalog fingerprint must be a SHA-256 identity.";
  let profile = get path "profile_version" fields in
  require ~path (profile=str A.combinational_profile || profile=str A.temporal_profile) "Unsupported synthetic generation profile.";
  require ~path (get path "generator_version" fields=str A.generator_version) "Unsupported synthetic generator version.";
  let catalog = A.catalog_for_profile (Json.string profile) in
  require ~path (hash=str (A.Catalog.fingerprint catalog)) "The selected synthetic catalog is unavailable or stale.";
  require ~path (get path "witness_selection" fields=str "closed_band_lower_endpoint") "Unsupported response witness selection policy.";
  require ~path (get path "conjunction_strategy" fields=str "native" || get path "conjunction_strategy" fields=str "de_morgan")
    "Unsupported conjunction strategy.";
  A.Config.of_json ~path raw
let logical_path path raw =
  let value = named path "Logical source location" raw in
  require ~path (not (String.exists (fun c -> Char.code c<32 || Char.code c=127) value))
    "Logical source location cannot contain control characters.";
  require ~path (not (String.contains value '\\') && not (String.contains value ':') &&
    not (String.starts_with ~prefix:"/" value) &&
    List.for_all (fun part -> not (List.mem part ["";".";".."])) (String.split_on_char '/' value))
    "Logical source location must be a canonical relative POSIX path without traversal."
let portable_sources limits path raw =
  (* The whole value was bounded before this traversal; charge each occurrence,
     including values in fields which have no special source interpretation. *)
  let rec visit pending = match pending with
    | [] -> ()
    | Json.Object fields :: rest ->
        C.charge limits (1+List.length fields);
        if List.sort String.compare (List.map fst fields)=["file";"function";"line"] then
          logical_path path (Json.field "file" fields);
        List.iter (fun (key,_) -> C.charge limits (String.length key+1);Json.validate_utf8 key) fields;
        visit (List.rev_append (List.rev_map snd fields) rest)
    | Json.Array values :: rest -> C.charge limits (1+List.length values);visit (List.rev_append values rest)
    | Json.String value :: rest -> C.charge limits (String.length value+1);Json.validate_utf8 value;visit rest
    | _ :: rest -> C.charge limits 1;visit rest in
  visit [raw]
type t = { json:Json.t;fingerprint:string;size:int;realization:Realization_request.t;
  history:F.t list;until:N.t;config:A.Config.t;profile:string }
let to_json value = value.json
let fingerprint value = value.fingerprint
let canonical_size value = value.size
let realization value = value.realization
let history value = value.history
let until value = value.until
let config value = value.config
let profile value = value.profile
let decode_with_realization ?(limits=C.default_limits) ?(path="") ?(retain_history=fun _ -> ()) ~decode_realization raw =
  let fields = record limits path "SyntheticBuildRequest"
    ["schema_version";"realization";"history";"until";"config";"profile";"intended_use"] raw in
  require ~path (get path "schema_version" fields=str schema_version) "Unsupported SyntheticBuildRequest schema.";
  let realization = decode_realization ~path:(path^"/realization") (get path "realization" fields) in
  let history = history_decode limits retain_history (path^"/history") (get path "history" fields) in
  let config = config_decode limits (path^"/config") (get path "config" fields) in
  let until = match get path "until" fields with Json.Int value -> N.Integer value | Json.Float value -> N.Real value
    | _ -> fail ~path "An explicit finite horizon is required." in
  require ~path ((match until with N.Integer value -> Float.is_finite (Z.to_float value) | N.Real value -> Float.is_finite value) && N.compare until (F.time (List.hd (List.rev history)))>=0)
    "Horizon must be finite and at least the last input time.";
  let profile = get path "profile" fields in
  require ~path (profile=str "synthetic_realization" || profile=str "synthetic_components") "Unsupported synthetic package profile.";
  require ~path (get path "intended_use" fields=str "software_test") "Synthetic builds only support software_test use.";
  require ~path (Build_request.artifact_scope (Realization_request.build_request realization)=Build_request.Synthetic_realization)
    "The source request must select synthetic_realization scope.";
  portable_sources limits path (Realization_request.to_json realization);
  let provenance = Build_request.provenance (Realization_request.build_request realization) |> Json.object_fields in
  require ~path (Json.field "locations" provenance=Json.Object [] && Json.field "recorded_at" provenance=Json.Null)
    "Host locations and run timestamps belong in separate RunMetadata.";
  let json = obj ["schema_version",str schema_version;"realization",Realization_request.to_json realization;
    "history",obj ["schema_version",str history_schema_version;"frames",Json.Array (List.map F.to_json history)];
    "until",N.to_json until;"config",A.Config.to_json config;"profile",profile;"intended_use",str "software_test"] in
  let encoded = C.encode ~limits json in C.charge limits (String.length encoded);
  {json;fingerprint=Canonical.sha256 encoded;size=String.length encoded;realization;history;until;config;profile=Json.string profile}
let of_json ?limits ?path raw = decode_with_realization ?limits ?path
  ~decode_realization:(fun ~path raw -> Realization_request.of_json ~path raw) raw

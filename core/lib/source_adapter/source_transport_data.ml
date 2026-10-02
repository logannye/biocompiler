open Bioc_wire
open Bioc_domain
module D = Execution_data
module N = Runtime_number
module C = Architecture_contract.Channel
module W = Bioc_checker.Work_budget
let boundary_version="biocompiler.native_source_transport_data.v0.1"
let transport_profile="biocompiler.sampled_architecture_transport.v0.1"
let require condition message=Diagnostic.require condition "source_transport_data" message
let obj values=Json.Object values
let arr values=Json.Array values
let str value=Json.String value
let field key value=Json.field key (Json.object_fields value)
let replace key value raw=obj ((key,value)::List.remove_assoc key (Json.object_fields raw))
let output ()=W.create_output ~profile:boundary_version ~error_code:"source_transport_output_limit"
  ~max_bytes:Limits.max_response_bytes ~max_nodes:Limits.max_json_nodes ()
let checked raw = W.reserve_json (output ()) raw;ignore (Canonical.encode raw);raw
let record keys raw=ignore (checked raw);Json.exact_fields keys (Json.object_fields raw)
let list encode values =
  let budget=output () in
  let rec loop result=function
    | [] -> List.rev result
    | value::rest -> let raw=encode value in W.reserve_json budget (arr [raw]);loop (raw::result) rest in
  arr (loop [] values)
let mapping encode values =
  let budget=output () and seen=Hashtbl.create 16 in
  let rec loop result=function
    | [] -> obj (List.rev result)
    | (key,value)::rest ->
        ignore (Json.name (str key));require (not (Hashtbl.mem seen key)) "Duplicate source transport map key.";
        Hashtbl.add seen key ();
        let raw=encode value in W.reserve_json budget (obj [key,raw]);loop ((key,raw)::result) rest in
  loop [] values
let decode_map decode raw=Json.object_fields raw |> List.map (fun (key,value)->ignore (Json.name (str key));key,decode value)
let decode_list decode raw=Json.array raw |> List.map decode
let nonnegative raw=let value=Json.integer raw in require (Z.sign value>=0) "Transport times must be nonnegative integers.";value
let fingerprint raw=let text=Json.string raw in require (String.length text=64 &&
  String.for_all (function '0'..'9'|'a'..'f'->true|_->false) text) "Invalid transport fingerprint.";text
let policies ~max_samples=obj [
  "profile",str transport_profile;"max_samples",Json.int max_samples;"max_role_evaluations",Json.int 10000;
  "channel_sampling",str "settled_action_requests_at_declared_grid_only";
  "delivery",str "prior_queued_outputs_delivered_before_all_current_role_evaluations";
  "latency",str "strictly_positive_integer_grid_multiple";
  "persistence",str "since_latest_delivery_exclusive_expiry; None_means_indefinite";
  "absent_signal",str "declared_initial_value_when_no_active_sender_contribution";
  "failure",str "delivery_tick; clear_discards_contribution; retain_last_freezes_for_failed_tick";
  "aggregation",str "active_sender_contributions; single_sender_sum_or_max_as_declared";
  "qualitative_encoding",str "unsupported_without_explicit_encoding_contract";
  "claim_scope",str "sampled_abstract_execution_under_declared_contracts_no_physiological_prediction"]
module Input = struct
  type t={histories:(string * D.Input_frame.t list) list;until:Json.t;step:Json.t;max_samples:Json.t;
    failed_channels:(string * Json.t list) list;json:Json.t}
  let of_json raw=
    record ["histories";"until";"step";"max_samples";"failed_channels"] raw;
    let histories=decode_map (decode_list D.Input_frame.of_json) (field "histories" raw) in
    let until=field "until" raw and step=field "step" raw and max_samples=field "max_samples" raw in
    let failed_channels=match field "failed_channels" raw with Json.Null->[]|value->decode_map Json.array value in
    let json=checked (obj ["histories",mapping (list D.Input_frame.to_json) histories;
      "until",until;"step",step;"max_samples",max_samples;"failed_channels",mapping (list Fun.id) failed_channels]) in
    {histories;until;step;max_samples;failed_channels;json}
  let make ~histories ~until ~step ?(max_samples=Json.int 1000) ?(failed_channels=[]) ()=
    of_json (obj ["histories",mapping (list D.Input_frame.to_json) histories;"until",until;"step",step;
      "max_samples",max_samples;"failed_channels",mapping (list Fun.id) failed_channels])
  let to_json value=value.json
  let histories value=value.histories
  let until value=value.until
  let step value=value.step
  let max_samples value=value.max_samples
  let failed_channels value=value.failed_channels
end
module Channel_frame = struct
  type sent={value:N.t;delivery_time:Z.t}
  type t={time:Z.t;receiver_values:(string*N.t) list;sent:(string*sent) list;failed_channel_ids:string list;json:Json.t}
  let sent_json value=obj ["value",N.to_json value.value;"delivery_time",Json.Int value.delivery_time]
  let decode_sent raw=
    record ["value";"delivery_time"] raw;
    {value=N.of_json (field "value" raw);delivery_time=nonnegative (field "delivery_time" raw)}
  let of_json raw=
    record ["time";"receiver_values";"sent";"failed_channel_ids"] raw;
    let time=nonnegative (field "time" raw) and receiver_values=decode_map N.of_json (field "receiver_values" raw) in
    let sent=decode_map decode_sent (field "sent" raw) and failed_channel_ids=decode_list Json.name (field "failed_channel_ids" raw) in
    require (failed_channel_ids=List.sort_uniq String.compare failed_channel_ids) "Failure identities must be sorted and unique.";
    {time;receiver_values;sent;failed_channel_ids;json=raw}
  let make ~time ~receiver_values ~sent ~failed_channel_ids=of_json (obj ["time",Json.Int time;
    "receiver_values",mapping N.to_json receiver_values;"sent",mapping sent_json sent;
    "failed_channel_ids",list str failed_channel_ids])
  let to_json value=value.json
  let time value=value.time
  let receiver_values value=value.receiver_values
  let sent value=value.sent
  let failed_channel_ids value=value.failed_channel_ids
end
module Result = struct
  type t={histories:(string*D.Input_frame.t list) list;results:(string*D.Result.t) list;
    channel_frames:Channel_frame.t list;json:Json.t}
  let of_json raw=
    record ["schema_version";"request_fingerprint";"build_fingerprint";"step_seconds";"horizon_seconds";
      "histories";"results";"channel_frames";"channels";"failed_channels";"assumptions";"policies"] raw;
    require (field "schema_version" raw=str "biocompiler.architecture_execution_result.v0.1") "Wrong transport result schema.";
    ignore (fingerprint (field "request_fingerprint" raw));ignore (fingerprint (field "build_fingerprint" raw));
    require (Z.sign (nonnegative (field "step_seconds" raw))>0) "Transport step must be positive.";
    ignore (nonnegative (field "horizon_seconds" raw));
    let history=decode_map (decode_list D.Input_frame.of_json) (field "histories" raw) in
    let results=decode_map D.Result.of_json (field "results" raw) in
    let frames=decode_list Channel_frame.of_json (field "channel_frames" raw) in
    let channels=decode_list C.of_json (field "channels" raw) in
    let failures=decode_map (decode_list nonnegative) (field "failed_channels" raw) in
    ignore (decode_list Json.name (field "assumptions" raw));
    let samples=Json.integer (field "max_samples" (field "policies" raw)) in
    require (Z.compare samples Z.one>=0 && Z.compare samples (Z.of_int 1000)<=0) "Invalid transport sample limit.";
    require (Json.equal (field "policies" raw) (policies ~max_samples:(Z.to_int samples))) "Transport result policies differ.";
    let json=raw
      |> replace "histories" (mapping (list D.Input_frame.to_json) history)
      |> replace "results" (mapping D.Result.to_json results)
      |> replace "channel_frames" (list Channel_frame.to_json frames)
      |> replace "channels" (list C.to_json channels)
      |> replace "failed_channels" (mapping (list (fun value->Json.Int value)) failures)
      |> checked in
    {histories=history;results;channel_frames=frames;json}
  let make ~request_fingerprint ~build_fingerprint ~step_seconds ~horizon_seconds ~histories ~results
      ~channel_frames ~channels ~failed_channels ~assumptions ~max_samples=
    of_json (obj ["schema_version",str "biocompiler.architecture_execution_result.v0.1";
      "request_fingerprint",str request_fingerprint;"build_fingerprint",str build_fingerprint;
      "step_seconds",Json.Int step_seconds;"horizon_seconds",Json.Int horizon_seconds;
      "histories",mapping (list D.Input_frame.to_json) histories;"results",mapping D.Result.to_json results;
      "channel_frames",list Channel_frame.to_json channel_frames;"channels",list C.to_json channels;
      "failed_channels",mapping (list (fun value->Json.Int value)) failed_channels;
      "assumptions",list str assumptions;"policies",policies ~max_samples])
  let to_json value=value.json
  let fingerprint value=Canonical.fingerprint value.json
  let histories value=value.histories
  let results value=value.results
  let channel_frames value=value.channel_frames
end

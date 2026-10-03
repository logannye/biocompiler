open Bioc_wire
module W = Bioc_checker.Work_budget
module C = Bioc_domain.Verification_exploration.Codec

let resource_profile = "biocompiler.reference_producers.resources.v1"
let error_code = "reference_producer_resource_limit"
type limits = {
  max_work : int;
  max_input_bytes : int;
  max_input_nodes : int;
  max_output_bytes : int;
  max_output_nodes : int;
}
let make_limits ?(max_work=256_000_000) ?(max_input_bytes=33_554_432)
    ?(max_input_nodes=1_000_000) ?(max_output_bytes=16_777_216)
    ?(max_output_nodes=1_000_000) () =
  Diagnostic.require (max_work>=0 && max_work<=256_000_000 &&
      max_input_bytes>0 && max_input_bytes<=33_554_432 &&
      max_input_nodes>0 && max_input_nodes<=1_000_000 &&
      max_output_bytes>0 && max_output_bytes<=16_777_216 &&
      max_output_nodes>0 && max_output_nodes<=1_000_000)
    "reference_producer_limits" "Reference producer limits exceed the fixed resource profile.";
  {max_work;max_input_bytes;max_input_nodes;max_output_bytes;max_output_nodes}
let default_limits = make_limits ()
let limits_json limits = Json.Object [
  "profile",Json.String resource_profile;
  "max_work",Json.int limits.max_work;
  "max_input_bytes",Json.int limits.max_input_bytes;
  "max_input_nodes",Json.int limits.max_input_nodes;
  "max_output_bytes",Json.int limits.max_output_bytes;
  "max_output_nodes",Json.int limits.max_output_nodes]
let checker_limits limits =
  (* Every authority has already passed the producer's cumulative input-node
     reservation before checker entry. The independent checker retains its
     stricter fixed 250k per-document input ceiling; no existing ceiling grows.
     Report and intermediate allocations also inherit applicable reductions.
     A zero producer work limit is enforced by its real shared ancestor before
     invocation; the checker API requires a positive local allowance. *)
  Bioc_checker.Reference_construct_check.make_limits
    ~max_work:(max 1 (min 50_000_000 limits.max_work))
    ~max_items:(min 100_000 (min limits.max_input_nodes limits.max_output_nodes))
    ~max_input_bytes:(min Limits.max_request_bytes limits.max_input_bytes)
    ~max_report_bytes:(min Limits.max_response_bytes limits.max_output_bytes)
    ~max_report_nodes:(min Limits.max_json_nodes limits.max_output_nodes) ()

type t = {work : W.t; codec : C.limits; inputs : W.output; outputs : W.output}
let create ?parent limits =
  let work = match parent with
    | None -> W.create ~profile:resource_profile ~error_code ~maximum:limits.max_work ()
    | Some parent -> W.nested ~parent ~profile:resource_profile ~error_code ~maximum:limits.max_work () in
  let codec = C.make_limits ~max_bytes:(max limits.max_input_bytes limits.max_output_bytes)
      ~max_nodes:(max limits.max_input_nodes limits.max_output_nodes) ~charge:(W.charge work) () in
  {work;codec;
   inputs=W.create_output ~profile:resource_profile ~error_code
     ~max_bytes:limits.max_input_bytes ~max_nodes:limits.max_input_nodes ();
   outputs=W.create_output ~profile:resource_profile ~error_code
     ~max_bytes:limits.max_output_bytes ~max_nodes:limits.max_output_nodes ()}
let work budget = budget.work
let codec budget = budget.codec
let charge budget = W.charge budget.work
let charge_product budget count factor =
  Diagnostic.require (count>=0 && factor>=0) "reference_producer_limits"
    "Reference producer work factors must be nonnegative.";
  if factor>0 && count>W.remaining budget.work/factor then
    W.charge budget.work (W.remaining budget.work+1);
  W.charge budget.work (count*factor)
let reserve budget destination value =
  let size = C.measure ~limits:budget.codec value in
  (* The reservation below traverses again; account for that traversal before
     touching cumulative retained-output state. *)
  W.charge budget.work (C.work_bounds size).measure;
  W.reserve_json destination value
let input budget value = reserve budget budget.inputs value
let output budget value = reserve budget budget.outputs value

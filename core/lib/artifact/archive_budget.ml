open Bioc_wire
module W = Bioc_checker.Work_budget
type limits = { max_archive_bytes:int; max_member_bytes:int;
  max_metadata_bytes:int; max_entries:int; max_path_bytes:int;
  max_json_nodes:int; max_json_depth:int; max_retained_bytes:int; max_work:int }
let defaults={max_archive_bytes=67_108_864;max_member_bytes=16_777_216;
  max_metadata_bytes=1_048_576;max_entries=128;max_path_bytes=1024;
  max_json_nodes=250_000;max_json_depth=128;max_retained_bytes=536_870_912;
  max_work=10_000_000_000}
let make_limits ?(max_archive_bytes=defaults.max_archive_bytes)
    ?(max_member_bytes=defaults.max_member_bytes) ?(max_metadata_bytes=defaults.max_metadata_bytes)
    ?(max_entries=defaults.max_entries) ?(max_path_bytes=defaults.max_path_bytes)
    ?(max_json_nodes=defaults.max_json_nodes) ?(max_json_depth=defaults.max_json_depth)
    ?(max_retained_bytes=defaults.max_retained_bytes) ?(max_work=defaults.max_work) () =
  List.iter(fun(value,maximum)->Diagnostic.require(value>=0 && value<=maximum)
    "archive_limits" "Archive limits must be nonnegative reductions.")
    [max_archive_bytes,defaults.max_archive_bytes;max_member_bytes,defaults.max_member_bytes;
     max_metadata_bytes,defaults.max_metadata_bytes;max_entries,defaults.max_entries;
     max_path_bytes,defaults.max_path_bytes;max_json_nodes,defaults.max_json_nodes;
     max_json_depth,defaults.max_json_depth;max_retained_bytes,defaults.max_retained_bytes;
     max_work,defaults.max_work];
  {max_archive_bytes;max_member_bytes;max_metadata_bytes;max_entries;max_path_bytes;
   max_json_nodes;max_json_depth;max_retained_bytes;max_work}
type t={controls:limits;work:W.t;retain_bytes:int->unit;mutable retained:int;mutable closed:bool;owned:bool}
let create ~parent ~retain_bytes ?(limits=defaults) ()=
  let work=W.nested ~parent ~profile:"biocompiler.archive.resources.v1"
    ~error_code:"archive_work_limit" ~maximum:limits.max_work() in
  W.charge work 1;
  Diagnostic.require(limits.max_retained_bytes>=128) "archive_retention_limit"
    "Archive cumulative retention limit exceeded.";
  retain_bytes 128;
  {controls=limits;work;retain_bytes;retained=128;closed=false;owned=false}
let limits state=state.controls
let work state=state.work
let retained state=state.retained
let owns_retention state=state.owned
let guard state=Diagnostic.require(not state.closed && not(W.exhausted state.work))
  "archive_closed" "Archive resource scope is closed."
let charge state amount=guard state;W.charge state.work amount
let product state count factor=
  guard state;Diagnostic.require(count>=0 && factor>=0) "archive_limits" "Negative archive work factor.";
  if factor>0 && count>W.remaining state.work/factor then W.charge state.work(W.remaining state.work+1);
  W.charge state.work(count*factor)
let reserve_storage state amount=
  guard state;
  try
    Diagnostic.require(amount>=0 && amount<=state.controls.max_retained_bytes-state.retained)
      "archive_retention_limit" "Archive cumulative retention limit exceeded.";
    state.retain_bytes amount;state.retained<-state.retained+amount
  with cause->state.closed<-true;raise cause

let reserve state amount=
  guard state;charge state 1;
  if state.owned then W.retain state.work amount else reserve_storage state amount
let create_owner ~parent ~retain_bytes ?(limits=defaults) ()=
  Diagnostic.require(not(W.has_retention parent)) "archive_retention_owner"
    "A new package lifetime cannot replace an existing retention owner.";
  let state=ref None in
  let sink amount=match !state with Some state->reserve_storage state amount|None->
    Diagnostic.fail "archive_retention_owner" "Package retention owner is not initialized." in
  let work=W.nested ~parent ~retain_bytes:sink ~profile:"biocompiler.reference_package.resources.v1"
    ~error_code:"archive_work_limit" ~maximum:limits.max_work() in
  let value={controls=limits;work;retain_bytes;retained=0;closed=false;owned=true} in
  state:=Some value;
  reserve value 128;value

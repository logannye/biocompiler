(** Coupled SOURCE execution under declared sampled transport. Every role replays
    the original complete Behavior prefix. This is neither independent candidate
    execution nor a physiological prediction. Fresh architecture checking is
    mandatory; exhaustion returns no partial receipt. A failed reference-prefix
    replay forfeits the remaining shared work allowance before propagating the
    original error; failed attempts cannot reuse uncharged work. *)
val implementation_version : string
val resource_profile : string
val max_work : int
val max_queued_deliveries : int
val max_replayed_frames : int
val max_replayed_trace_items : int
type budget
val make_budget : ?parent:Bioc_checker.Work_budget.t -> ?maximum:int -> unit -> budget
val remaining_work : budget -> int
val evaluate : ?budget:budget -> expected_request:Bioc_domain.Architecture_request.t ->
  Bioc_domain.Architecture_build.t -> Source_transport_data.Input.t -> Source_transport_data.Result.t

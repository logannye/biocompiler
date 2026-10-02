(** Complete fixed-checker workflow execution and fresh replay. Model mode keeps
    source authority fresh but grants no synthetic provenance acceptance. *)
val implementation_version : string
val resource_profile : string
type limits = Verification_workflow_budget.limits
val make_limits : ?max_work:int -> ?max_monitor_items:int -> ?max_request_bytes:int ->
  ?max_report_bytes:int -> ?max_report_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
type usage = Verification_workflow_budget.usage
(* The *_in seams share one caller-owned budget across staged imports, execution,
   comparison and publication. They never create a fresh aggregate allowance. *)
val decode_request_in : budget:Verification_workflow_budget.t -> ?path:string ->
  Bioc_wire.Json.t -> Bioc_domain.Verification_workflow.Request.t
val decode_record_in : budget:Verification_workflow_budget.t -> ?path:string ->
  Bioc_wire.Json.t -> Bioc_domain.Verification_workflow.Record.t
val run_in : budget:Verification_workflow_budget.t -> Bioc_domain.Verification_workflow.Request.t ->
  Bioc_domain.Verification_workflow.Record.t
val replay_in : budget:Verification_workflow_budget.t -> ?raw_record:Bioc_wire.Json.t ->
  expected_request:Bioc_domain.Verification_workflow.Request.t -> Bioc_domain.Verification_workflow.Record.t ->
  Bioc_domain.Verification_workflow.Record.t
val run_with_usage : ?limits:limits -> ?parent:Bioc_checker.Work_budget.t ->
  Bioc_domain.Verification_workflow.Request.t -> Bioc_domain.Verification_workflow.Record.t * usage
val run : ?limits:limits -> ?parent:Bioc_checker.Work_budget.t ->
  Bioc_domain.Verification_workflow.Request.t -> Bioc_domain.Verification_workflow.Record.t
val replay_with_usage : ?limits:limits -> ?parent:Bioc_checker.Work_budget.t ->
  expected_request:Bioc_domain.Verification_workflow.Request.t -> Bioc_domain.Verification_workflow.Record.t ->
  Bioc_domain.Verification_workflow.Record.t * usage
val replay : ?limits:limits -> ?parent:Bioc_checker.Work_budget.t ->
  expected_request:Bioc_domain.Verification_workflow.Request.t -> Bioc_domain.Verification_workflow.Record.t ->
  Bioc_domain.Verification_workflow.Record.t

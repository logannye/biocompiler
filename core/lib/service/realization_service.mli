(** Bounded native dependency, finite-history checking and complete fresh replay.
    Each route delegates only to a public independent checker. *)
val implementation_version : string
val resource_profile : string
val operations : string list
val profiles : (string * Bioc_wire.Json.t) list
val validation_scopes : string list
type usage = { work_charged : int; request_bytes : int; report_bytes : int; retained_peak : int }
(* Input reductions cover the complete payload. Fixed transport bounds include
   the real request ID and operation; publication includes the full response. *)
val handle_with_usage : ?parent:Bioc_checker.Work_budget.t ->
  executable:Bioc_wire.Protocol.executable -> request_id:string -> operation:string ->
  Bioc_wire.Json.t -> Bioc_wire.Json.t * usage
val handle : ?parent:Bioc_checker.Work_budget.t ->
  executable:Bioc_wire.Protocol.executable -> request_id:string -> operation:string ->
  Bioc_wire.Json.t -> Bioc_wire.Json.t

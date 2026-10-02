(** Core-only bounded deterministic producer boundary. Every result is bound to
    the complete supplied authority and effective typed identities. Ordinary
    generator Unsupported errors retain their message, node and source in a
    non-producing result; they never become successful proposal/acceptance claims.
    The verifier does not link this library. *)
val implementation_version : string
val resource_profile : string
val operations : string list
val validation_scopes : string list
val profiles : (string * Bioc_wire.Json.t) list
type usage = { work_charged:int;request_bytes:int;report_bytes:int;retained_peak:int }
val handle_with_usage : ?parent:Bioc_checker.Work_budget.t ->
  executable:Bioc_wire.Protocol.executable -> request_id:string -> operation:string ->
  Bioc_wire.Json.t -> Bioc_wire.Json.t * usage
val handle : ?parent:Bioc_checker.Work_budget.t ->
  executable:Bioc_wire.Protocol.executable -> request_id:string -> operation:string ->
  Bioc_wire.Json.t -> Bioc_wire.Json.t

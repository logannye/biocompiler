(** Complete original SyntheticBuildRequest authority for the public selection
    command. Fresh source checking precedes history/config import. The nested
    producer is unchanged and shares the complete outer work ancestor. *)
val implementation_version : string
val resource_profile : string
val profile : Bioc_wire.Json.t
val profiles : (string * Bioc_wire.Json.t) list
val operations : string list
val validation_scopes : string list
type usage = {work_charged:int;request_bytes:int;report_bytes:int;retained_peak:int}
val handle_with_usage : ?parent:Bioc_checker.Work_budget.t ->
  executable:Bioc_wire.Protocol.executable -> request_id:string -> operation:string ->
  Bioc_wire.Json.t -> Bioc_wire.Json.t * usage
val handle : ?parent:Bioc_checker.Work_budget.t ->
  executable:Bioc_wire.Protocol.executable -> request_id:string -> operation:string ->
  Bioc_wire.Json.t -> Bioc_wire.Json.t

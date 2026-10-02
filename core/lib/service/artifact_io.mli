(** Private inherited-descriptor transport. No supplied pathname is opened.
    This interface grants byte transport only, never semantic acceptance. *)
type descriptor = { bytes:int; sha256:string }
type t
val operations : string list
val profile : Bioc_wire.Json.t
val max_control_bytes : int
val descriptor_of_json : max_bytes:int -> Bioc_wire.Json.t -> descriptor
val descriptor_json : descriptor -> Bioc_wire.Json.t
val with_fds : authority:string -> retained_record:string -> output:string -> (t -> 'a) -> 'a
val charge_control : t -> budget:Bioc_realization_checker.Verification_workflow_budget.t -> int -> unit
val read_authority : t -> budget:Bioc_realization_checker.Verification_workflow_budget.t -> descriptor -> Bioc_wire.Json.t
val read_record : t -> budget:Bioc_realization_checker.Verification_workflow_budget.t -> descriptor option -> Bioc_wire.Json.t option
val write_output : t -> budget:Bioc_realization_checker.Verification_workflow_budget.t -> limit:int -> string -> descriptor
val read_control : unit -> string

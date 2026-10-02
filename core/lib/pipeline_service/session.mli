(* One live native manager and fixed build per process-local session. Historical
   records cannot install acceptance. Every command uses one lifetime budget. *)
val declaration : Bioc_wire.Json.t
val profile : string
val protocol : string
val maximum_frame_bytes : int
type t
type response = {bytes:string;closed:bool}
val create : unit -> t
val is_closed : t -> bool
(* Reserve the complete input body and nine-byte prefix before allocating or
   reading that body. Exactly one matching handle_frame must follow. *)
val reserve_frame : t -> int -> unit
val handle_frame : t -> string -> response
(* A bounded, prepaid terminal response. It never makes a failed command valid. *)
val abort : ?unbound:bool -> t -> response

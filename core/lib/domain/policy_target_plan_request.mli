(** A bounded advisory envelope. Child source and supplied authority remain raw:
    decoding this envelope establishes no source validity or target support.
    In particular an invalid document is retained for the planner's diagnostic. *)
open Bioc_wire
val schema_version : string
val max_input_bytes : int
val max_input_nodes : int
val max_input_depth : int
type limits = {max_work:int;max_report_bytes:int;max_report_nodes:int}
val ceilings : limits
type t
val of_json : ?charge:(int -> unit) -> Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val decoding_work : t -> int
val target : t -> string
val document : t -> Json.t
val definitions : t -> Json.t option
val realization_request : t -> Json.t option
val material_request : t -> Json.t option
val limits : t -> limits

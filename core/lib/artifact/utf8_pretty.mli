(** Python indent=2, sort_keys=true, ensure_ascii=false, allow_nan=false.
    Scalars retain integer/binary64 identity. Existing encoders are unchanged. *)
val encode : Archive_budget.t -> ?newline:bool -> max_bytes:int -> Bioc_wire.Json.t -> string

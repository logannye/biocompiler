(** Core-only callback application. Channel framing owns bounds, terminal
    failures and uncertain writes. EOF releases the process-local manager. *)
val run : unit -> unit

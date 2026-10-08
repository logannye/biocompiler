(* Core-only persistent entry point. Standard and artifact one-shot modes are
   unchanged. EOF releases authority; there is no reconnect or import route. *)
val run : unit -> unit

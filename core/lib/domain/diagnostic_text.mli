(** Stable diagnostic spelling, using Python repr rules and Unicode 14.0.0
    printability. This profile affects diagnostic text, never acceptance status.
    Unlike host-dependent Python repr, newly assigned characters remain escaped
    until an explicit profile revision. Input must be bounded valid UTF-8. *)
val profile : string
val repr : string -> string

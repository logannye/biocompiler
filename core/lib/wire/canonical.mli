(** Python json.dumps(sort_keys=True, separators=(",", ":"),
    ensure_ascii=False, allow_nan=False) compatibility, with bounded output.
    This is the legacy Biocompiler encoding, not RFC 8785. *)
val float_string : float -> string
val encode : Json.t -> string
val sha256 : string -> string
val fingerprint : Json.t -> string

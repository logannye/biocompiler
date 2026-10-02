(** Python json.dumps(sort_keys=True, separators=(",", ":"),
    ensure_ascii=False, allow_nan=False) compatibility, with bounded output.
    This is the legacy Biocompiler encoding, not RFC 8785. *)
val float_string : float -> string
val encode : Json.t -> string
(* Select an explicit artifact byte limit up to 64 MiB without changing [encode].
    Callers preflight graph/list cycles, node counts and scalar sizes separately,
    as they do for the original encoder. Numeric and UTF-8 encoding are shared. *)
val encode_bounded : max_bytes:int -> Json.t -> string
val sha256 : string -> string
val fingerprint : Json.t -> string

(** Explicit Python [json.dumps(ensure_ascii=True, sort_keys=True)] compatibility.
    This is a legacy identity profile; it does not replace UTF-8 Canonical. Raw
    graphs, list spines, scalar sizes and cumulative output are bounded before
    sorting or allocating the encoded document. *)
type layout = Compact | Spaced | Indented of int
type size = { nodes : int; bytes : int; depth : int }
val measure : ?path:string -> ?layout:layout -> Json.t -> size
val preflight : ?path:string -> Json.t -> unit
val encode : ?layout:layout -> Json.t -> string
val fingerprint : Json.t -> string

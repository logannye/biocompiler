(** Explicit historical reference/record JSON spelling and error profiles.
    These helpers confer no domain or artifact acceptance. *)
type profile = Artifact | Reference
val parse : ?on_node:(unit -> unit) -> max_bytes:int -> max_nodes:int ->
  profile:profile -> string -> Json.t
(* Python json.dumps(sort_keys=True, indent=2, ensure_ascii=False,
   allow_nan=False), without a trailing newline. Input and output are bounded. *)
val pretty_utf8 : Json.t -> string

type scoped_reply = {
  status:Bioc_wire.Protocol.status;
  result:Bioc_wire.Json.t option;
  diagnostics:Bioc_wire.Diagnostic.t list;
  before_encode:Bioc_wire.Json.t -> unit;
}

(** Recognized selection operations require their one-shot guard on the actual
    complete protocol frame. Other operations fall through to the old handler. *)
val scoped_handle : Bioc_wire.Protocol.executable -> Bioc_wire.Protocol.request -> scoped_reply option
val run : ?handler:(Bioc_wire.Protocol.executable -> Bioc_wire.Protocol.request ->
  Bioc_wire.Protocol.status * Bioc_wire.Json.t option * Bioc_wire.Diagnostic.t list) ->
  ?scoped_handler:(Bioc_wire.Protocol.executable -> Bioc_wire.Protocol.request -> scoped_reply option) ->
  Bioc_wire.Protocol.executable -> unit

(** Legacy low-level dispatch. Selection routes use [scoped_handle] through
    [run], so callers cannot omit final-frame admission via this function. *)
val handle : Bioc_wire.Protocol.executable -> Bioc_wire.Protocol.request -> Bioc_wire.Protocol.status * Bioc_wire.Json.t option * Bioc_wire.Diagnostic.t list

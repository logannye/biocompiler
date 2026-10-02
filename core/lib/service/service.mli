val run : ?handler:(Bioc_wire.Protocol.executable -> Bioc_wire.Protocol.request ->
  Bioc_wire.Protocol.status * Bioc_wire.Json.t option * Bioc_wire.Diagnostic.t list) ->
  Bioc_wire.Protocol.executable -> unit
val handle : Bioc_wire.Protocol.executable -> Bioc_wire.Protocol.request -> Bioc_wire.Protocol.status * Bioc_wire.Json.t option * Bioc_wire.Diagnostic.t list

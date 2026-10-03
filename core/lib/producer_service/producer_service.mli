(** Core-only architecture and synthetic production, with fresh checked export. The standalone
    verifier delegates exclusively to the producer-free service. JSON text
    results are canonical UTF-8 content without a publication newline. *)
val validation_scope : string
val profile : Bioc_wire.Json.t
val handle : Bioc_wire.Protocol.executable -> Bioc_wire.Protocol.request ->
  Bioc_wire.Protocol.status * Bioc_wire.Json.t option * Bioc_wire.Diagnostic.t list

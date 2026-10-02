(** Source-backed identity metadata for the three closed fixed producers.
    This observes native results and construction origins; it never imports a
    record, executes a provider, or decides acceptance. The caller must retain
    the actual closure and bind [Retained] keys within that closure only. *)
type origin = Host of string * Bioc_wire.Json.t list | Fresh of string | Retained of string
type site = {kind:string; path:Bioc_wire.Json.t list; origin:origin; value:Bioc_wire.Json.t}
val aliases : charge:(int -> unit) -> reserve:(int -> unit) ->
  request:Bioc_wire.Json.t -> candidate:Bioc_wire.Json.t option -> role:Bioc_pipeline.Synthetic_pipeline.provider_role ->
  Bioc_wire.Json.t -> site list

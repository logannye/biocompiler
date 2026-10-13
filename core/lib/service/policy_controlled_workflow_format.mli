(** Exact paired publication requires a fresh private joined capability.
    Saved child reports, including PASS reports, cannot enter this formatter. *)
open Bioc_wire
val render : charge:(int -> unit) ->
  Bioc_realization_checker.Policy_controlled_workflow_check.checked_controlled_workflow -> Json.t

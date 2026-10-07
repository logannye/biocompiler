(** Formatting starts only from a freshly checked child material capability.
    The optional callback accounts for bounded conversion, sequence traversal,
    FASTA construction and hashing before each corresponding pass. It does not
    establish outer selection or export authority. *)
open Bioc_wire
type rendered = { members:Json.t list; fasta:string; fasta_sha256:string }
val render : ?charge:(int -> unit) ->
  Bioc_realization_checker.Policy_component_material_check.checked_material -> rendered

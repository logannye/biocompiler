(** Independent comparison to separately supplied required-region authority.
    Empty diagnostics grant only declared structural correspondence, never
    source fidelity, regulatory function, complete construction or admission. *)
type result = { diagnostics : string list; unsupported : string list }
val check : contracts:Bioc_domain.Payload_structure.t list -> bundle:Bioc_domain.Molecule_set.t -> result
val check_json : contracts:Bioc_wire.Json.t -> bundle:Bioc_wire.Json.t -> result

(* Explicit parent preserves the legacy all-labelled call shape. *)
val check_with_parent : parent:Work_budget.t option -> contracts:Bioc_domain.Payload_structure.t list -> bundle:Bioc_domain.Molecule_set.t -> result
val check_json_with_parent : parent:Work_budget.t option -> contracts:Bioc_wire.Json.t -> bundle:Bioc_wire.Json.t -> result

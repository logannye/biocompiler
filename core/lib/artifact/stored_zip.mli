(** Deterministic stored-ZIP container integrity only. No semantic acceptance,
    filesystem access, network, extraction, or publication. Strings hold bytes. *)
type diagnostic_profile = Python311 | Python314
type entry = string * string
type member = { path:string; byte_length:int; sha256:string }
val safe_path : Archive_budget.t -> string -> unit
val validate_files : Archive_budget.t -> member list -> entry list -> entry list
val encode : Archive_budget.t -> entry list -> string
val assemble : Archive_budget.t -> manifest:Bioc_wire.Json.t ->
  members:member list -> files:entry list -> ?run_metadata:Bioc_wire.Json.t -> unit -> string
val read : Archive_budget.t -> ?diagnostics:diagnostic_profile -> string -> entry list

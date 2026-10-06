(** Unchecked source-neutral molecular construction content. Parsing establishes
    bounded structural consistency only. No circuit, policy, recipient, provider,
    payload-completeness, implementation or empirical authority is fabricated. *)
val schema_version : string
val authority_schema : string

(** The separately supplied order is an exact permutation of the template's
    covalent output members; template normalization must not choose this order. *)
val authority_json : template:Payload_template.t -> member_order:string list -> Bioc_wire.Json.t
val authority_fingerprint : template:Payload_template.t -> member_order:string list -> string

module Inventory : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val make : id:string -> molecules:Molecule.t list -> complexes:Molecule.Complex.t list ->
    role_instances:Molecule.Role.t list -> form_mappings:Molecule.Form_mapping.t list -> t
  val molecules : t -> Molecule.t list
  val complexes : t -> Molecule.Complex.t list
  val role_instances : t -> Molecule.Role.t list
  val form_mappings : t -> Molecule.Form_mapping.t list
  val subject_complete : t -> string -> bool
  val validate_amounts : t -> Molecule_set.Amount.t list -> unit
end

type t
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val make : authority_fingerprint:string -> member_order:string list ->
  values:Construction_artifact.Value.t list -> inventory:Inventory.t option ->
  missing_members:string list -> diagnostics:string list ->
  experimental_amounts:Molecule_set.Amount.t list -> t
val authority : t -> string
val member_order : t -> string list
val values : t -> Construction_artifact.Value.t list
val inventory : t -> Inventory.t option
val missing_members : t -> string list
val diagnostics : t -> string list
val experimental_amounts : t -> Molecule_set.Amount.t list

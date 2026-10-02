(** Historical architecture candidates and ledgers. These abstract records check
    shape and internal identity only; none constitutes fresh acceptance. *)
module Gap : sig
  type category = Unsupported_semantics | Missing_implementation | Incompatible_composition
    | Contradictory_requirements | Missing_sequence_authority | Search_budget_exhausted
    | Independent_verification_failure
  val category_name : category -> string
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : category:category -> code:string -> requirement_ids:string list -> candidate_ids:string list -> message:string -> conflict_set:string list -> t
  val category : t -> category
  val code : t -> string
  val requirement_ids : t -> string list
  val candidate_ids : t -> string list
  val message : t -> string
  val conflict_set : t -> string list
end
module Requirement_realization : sig
  type status = Implemented | Unresolved
  val status_name : status -> string
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> source_node_ids:string list -> refinement_ids:string list -> status:status -> assumptions:string list -> reasons:string list -> t
  val id : t -> string
  val source_node_ids : t -> string list
  val refinement_ids : t -> string list
  val status : t -> status
  val assumptions : t -> string list
  val reasons : t -> string list
end
module Plan : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : selected_refinement_ids:string list -> ledger:Requirement_realization.t list ->
    placements:Bioc_wire.Json.t list -> helpers:Bioc_wire.Json.t list -> channels:Bioc_wire.Json.t list ->
    control_domains:Bioc_wire.Json.t list -> assumptions:string list -> instances:Architecture_contract.Instance.t list ->
    availability:Bioc_wire.Json.t list -> t
  val selected_refinement_ids : t -> string list
  val ledger : t -> Requirement_realization.t list
  val placements : t -> Bioc_wire.Json.t list
  val helpers : t -> Bioc_wire.Json.t list
  val channels : t -> Bioc_wire.Json.t list
  val control_domains : t -> Bioc_wire.Json.t list
  val assumptions : t -> string list
  val instances : t -> Architecture_contract.Instance.t list
  val availability : t -> Bioc_wire.Json.t list
end
module Alternative : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : refinement_ids:string list -> gaps:Gap.t list -> t
  val refinement_ids : t -> string list
  val gaps : t -> Gap.t list
  val eligible : t -> bool
end
type status = Compiled | Partial | Unsupported | No_solution | Search_exhausted
val status_name : status -> string
val max_alternatives : int
type t
val schema_version : string
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val make : request_fingerprint:string -> execution:Source_execution_manifest.t -> plan:Plan.t option ->
  construction:Construction_build.t option -> alternatives:Alternative.t list -> diagnostics:Gap.t list ->
  status:status -> match_instances:Architecture_contract.Instance.t list -> t
val request_fingerprint : t -> string
val execution : t -> Source_execution_manifest.t
val plan : t -> Plan.t option
val construction : t -> Construction_build.t option
val alternatives : t -> Alternative.t list
val diagnostics : t -> Gap.t list
val status : t -> status
val match_instances : t -> Architecture_contract.Instance.t list
val molecules : t -> Molecule_set.t option
module Export : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : fasta:string -> manifest:Bioc_wire.Json.t -> t
  val fasta : t -> string
  val manifest : t -> Bioc_wire.Json.t
end

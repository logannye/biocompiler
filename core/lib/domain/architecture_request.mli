(** Complete original architecture authority for the declared human immune RNA
    profile. Successful import is not architecture acceptance or permission to
    discharge any wrapped human-source, evidence or admission obligation. *)
type t
val schema_version : string
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val make : ?constraints:Architecture_contract.Constraints.t -> id:string -> circuit:Circuit_request.t ->
  library:Architecture_refinement.Library.t -> unit -> t
val id : t -> string
val circuit : t -> Circuit_request.t
val library : t -> Architecture_refinement.Library.t
val constraints : t -> Architecture_contract.Constraints.t
val source : t -> Human_request.t

(** Finite original local-component inventory. Every entry is decoded against
    the supplied model library; decoding is not component selection or semantic
    acceptance. Contextual model-library identity is excluded from serialization. *)
open Bioc_wire
module C = Policy_component_material
val schema_version : string
val profile : string
val max_components : int
type t
val of_json : library:Policy_implementation.library -> Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val model_library_digest : t -> string
val components : t -> C.t list

(** Complete pinned identity only; a matching name or peptide is insufficient. *)
val find : t -> Pinned_identity.t -> C.t option

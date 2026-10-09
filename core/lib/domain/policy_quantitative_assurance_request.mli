(** Complete original quantitative assurance authority. Decoding grants neither
    mathematical agreement nor empirical compatibility. The material request
    and both optional contracts retain their independent schemas. *)
open Bioc_wire
val schema_version : string
val profile : string
val maximum_work : int
type t
val of_json : ?charge:(int -> unit) -> Json.t -> t
val to_json : t -> Json.t
val material_request : t -> Json.t
val approximation : t -> Policy_approximation_contract.t option
val realization_evidence : t -> Policy_realization_evidence_contract.t option
val max_work : t -> int

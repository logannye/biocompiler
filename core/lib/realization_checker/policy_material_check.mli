(** Fresh conjunction over original source, candidate execution, exact material
    reconstruction and declared context. Saved reports never reconstruct this
    module's private accepted value. The result remains conditional on supplied
    model-to-sequence/provider contracts and grants no empirical claim. *)
open Bioc_wire
module R = Bioc_domain.Policy_material_request
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module U = Bioc_domain.Policy_implementation_binding
module C = Bioc_domain.Policy_material_contract
module K = Bioc_domain.Construction_content
module P = Policy_preservation_check
module X = Policy_material_context_check
val profile : string
val implementation_version : string
val candidate_schema : string
type result
type checked_material

(** Work is an aggregate of explicitly charged JSON value/key/list-edge and
    scalar-byte preflights, exact encoding/hash/publication bytes, and each
    child's declared semantic work. It is not a CPU-instruction ceiling.
    Original decoder hard limits and child budgets remain independently active.
    Exhaustion propagates before private acceptance or report publication. *)
val check : request:R.t -> behavior:O.behavior -> implementation:I.t ->
  proposed:U.t -> material_binding:C.proposal -> candidate:K.t -> limits:P.limits -> result
val report : result -> Json.t
val accepted : result -> checked_material option
val request : checked_material -> R.t
val context : checked_material -> X.checked_context
val evidence : checked_material -> Json.t

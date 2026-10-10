(** Complete fresh conjunction for the separately supplied component profile.
    Original source, catalog, component, composition and deployment authorities
    remain distinct. A saved report never reconstructs the private completion
    token. This bounded result is conditional on supplied models and contracts;
    empirical validity and export remain separate obligations. Finite-machine
    obligation discharge requires complete original-domain correspondence and
    every original hard requirement; retry cycles imply no universal termination
    or progress claim beyond those explicit requirements. *)
open Bioc_wire
module R = Bioc_domain.Policy_component_material_request
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module U = Bioc_domain.Policy_implementation_binding
module Q = Bioc_domain.Policy_component_assembly_proposal
module K = Bioc_domain.Construction_content
module P = Policy_preservation_check
module X = Policy_component_context_check
val profile : string
val implementation_version : string
val candidate_schema : string
type result
type checked_material

(** Aggregate logical preflight/encoding/publication work and child semantic
    work use the original request ceilings. No stage may trim an obligation or
    shrink the source domain to fit a budget. Exhaustion grants no token. *)
val check : request:R.t -> behavior:O.behavior -> implementation:I.t ->
  proposed:U.t -> assembly_proposal:Q.t -> candidate:K.t -> limits:P.limits -> result
val report : result -> Json.t
val accepted : result -> checked_material option
val request : checked_material -> R.t
val context : checked_material -> X.checked_context
val evidence : checked_material -> Json.t
val quantitative : checked_material -> Policy_quantitative_check.checked_quantitative option

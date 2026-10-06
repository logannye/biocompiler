(** Fresh admission of external source/domain/model inputs. The only constructor
    repeats source admission and independently checks the supplied operational
    behavior against complete external authority before domain compatibility.

    This value cannot certify source-to-implementation preservation, whole-domain
    requirements, deployment realization, material construction or export. *)
open Bioc_wire
module R = Bioc_domain.Policy_realization_request
module O = Bioc_domain.Policy_operational
module F = Bioc_domain.Policy_operating_domain
module P = Bioc_domain.Pinned_identity

type admitted_inputs
val admit : request:R.t -> behavior:O.behavior -> admitted_inputs
val request : admitted_inputs -> R.t
val behavior : admitted_inputs -> O.behavior
val operating_domain : admitted_inputs -> F.validated
val authorized_models : admitted_inputs -> P.t list
(** Exact membership only; selecting a permitted model proves no correspondence. *)
val require_model : admitted_inputs -> entry_id:string -> P.t -> unit
val report : admitted_inputs -> Json.t

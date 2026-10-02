(** Producer-side derivation from complete frozen source authority. The resulting
    manifest is a candidate declaration; fresh source/architecture checking is
    independent. Unsupported operations remain explicit, wrapped obligations
    remain attached, and resource exhaustion yields no partial manifest. *)
val implementation_version : string
val diagnostic_profile : string
val derive : Bioc_domain.Human_request.t -> Bioc_domain.Source_execution_manifest.t

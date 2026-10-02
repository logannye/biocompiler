(* Checker-private expected values. Dune must keep this module private: the
   public checker exposes only fresh assessments, never a candidate producer. *)
type transition = {
  step : Bioc_domain.Construction.Transform_step.t;
  port : Bioc_domain.Construction.Product_port.t;
  inputs : (string * Transition_check.Input.t) list;
  product : Bioc_domain.Construction_artifact.Value.t;
}
val reconstruct : Bioc_domain.Construction.Request.t -> Bioc_domain.Construction_artifact.t * transition list

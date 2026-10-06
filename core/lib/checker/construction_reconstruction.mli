(* Checker-private expected values. Dune must keep this module private: the
   public checker exposes only fresh assessments, never a candidate producer. *)
type transition = {
  step : Bioc_domain.Construction.Transform_step.t;
  port : Bioc_domain.Construction.Product_port.t;
  inputs : (string * Transition_check.Input.t) list;
  product : Bioc_domain.Construction_artifact.Value.t;
}
val reserve_json : Work_budget.t -> Bioc_wire.Json.t -> unit
val protect : (unit -> 'a) -> 'a
val reconstruct : budget:Work_budget.t -> Bioc_domain.Construction.Request.t -> Bioc_domain.Construction_artifact.t * transition list
val reconstruct_template : budget:Work_budget.t -> member_order:string list ->
  Bioc_domain.Payload_template.t -> Bioc_domain.Construction_content.t * transition list

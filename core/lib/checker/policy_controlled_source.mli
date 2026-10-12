(** Admission of the closed controlled activity SOURCE only. This token grants
    neither model execution, material correspondence nor publication authority.
    Legacy operational admission and its document type remain unchanged. *)
open Bioc_wire
module D = Bioc_domain.Policy_document

type symbol = private { id : string; path : string; index : int; original : Json.t }
type definition = private { identity : string; path : string; reference : Json.t; body : Json.t }
type input_scope = Executor | Encounter
type observation = private {
  symbol : symbol; scope : input_scope; contract : definition; freshness_ticks : int;
}
type product = private { symbol : symbol; product_identity : string }
type obligation_kind = No_unauthorized_activation | Initial_activation
  | Controller_cessation | Antigen_cessation | Component_cessation | Reactivation
type obligation = private {
  symbol : symbol; kind : obligation_kind; contract : definition; deadline_ticks : int option;
}
type deadlines = private {
  onset_ticks : int; controller_off_ticks : int; antigen_off_ticks : int;
  component_off_ticks : int; reactivation_ticks : int;
}
type source = private {
  executor : symbol; target : symbol; encounter : symbol; clock : symbol;
  tick_resolution : Q.t; tick_unit : Json.t; resolution : Json.t; horizon_ticks : int;
  antigen : observation; controller : observation;
  products : product * product; activity : symbol;
  operation : definition; readout : definition;
  obligations : obligation list; deadlines : deadlines; selected_implementation : Json.t;
}
type t
val schema_version : string
val obligation_tag : obligation_kind -> string

(** Fresh metered admission redecodes the complete original representation and
    resolves all references. Callback exceptions propagate; no partial token is
    returned and no mechanism input is consulted to derive source requirements. *)
val admit : charge:(int -> unit) -> document:D.controlled -> t
val document : t -> D.controlled
val typed : t -> source
val report : t -> Json.t

(** Complete ordered source declaration and definition occurrence mappings.
    These are source lowering correspondences, not producer claims. *)
val correspondence : t -> Json.t

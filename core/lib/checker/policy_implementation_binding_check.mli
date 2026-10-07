(** Independent reconstruction of a closed source/graph binding. The checker
    walks original source expressions against actual primitive configurations
    and wires; it imports neither a lowering producer nor either runtime.
    This first family has one executor/encounter/truth observation/product
    effect, one or two exclusive evidence-rising rules, encounter truth stores,
    no machines/predicate resets, and exactly one effect-initiating rule.

    A result proves only [source_graph_bound]. It does not execute a timeline,
    prove preservation or hard requirements, or authorize material/export. *)
open Bioc_wire
module I = Bioc_domain.Policy_implementation
module B = Bioc_domain.Policy_implementation_binding
module O = Bioc_domain.Policy_operational
module A = Policy_realization_admission

val profile : string
type slot = { identity : string; target : string; start_tick : int }
type environment = { executor : string; slots : slot list; horizon_ticks : int }
type observation = { source : string; bank : string; input : string; observer : string; subject : string }
type state = { source : string; register : string }
(* [product_parameter] is the effect Argument.name, not the name of the fixed
   Parameter declaration from which its value was read. *)
type effect_binding = { source : string; bank : string; feedback : string; initiating_rule : string;
  gate : string; guard : I.endpoint; product_parameter : string }
type rule = { source : string; gate : string; arbiter : string; lane : int; commit : string;
  trigger : I.endpoint; source_trigger : O.expression }
type expression = { source_path : string; source_expression : Json.t; endpoint : I.endpoint }
type checked_binding

val check : admitted:A.admitted_inputs -> implementation:I.t -> proposed:B.t -> checked_binding
val admitted_inputs : checked_binding -> A.admitted_inputs
val implementation : checked_binding -> I.t
val environment : checked_binding -> environment
val observations : checked_binding -> observation list
val states : checked_binding -> state list
val effects : checked_binding -> effect_binding list
val rules : checked_binding -> rule list

(** For independently checked observable projection only. Source expressions
    must never be passed into the candidate runtime as executable callbacks. *)
val expressions : checked_binding -> expression list
val report : checked_binding -> Json.t

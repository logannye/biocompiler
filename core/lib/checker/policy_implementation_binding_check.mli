(** Independent reconstruction of a closed source/graph binding. The checker
    walks original source expressions against actual primitive configurations
    and wires; it imports neither a lowering producer nor either runtime.
    This first family has one executor/encounter/truth observation/product
    effect, one or two exclusive evidence-rising rules, encounter truth stores,
    no machines/predicate resets, and exactly one effect-initiating rule.
    The separately versioned two-observation family independently binds two
    distinct coherence groups in original declaration order to distinct banks
    and inputs, preserving each source observation and freshness bound.
    The separate staged profile binds one encounter machine, five exact ordered
    source state labels, seven transitions and two distinct same-product effects.
    The separate finite-machine profile binds one encounter machine with two
    to sixteen ordered source states, one to thirty-two transitions and one to
    eight same-product effects. Branches and retry cycles preserve exact source
    edges, terminal non-reentry, exclusive lanes and retained attempt identity.
    Each effect has one initiating transition, with at most one request per
    transition; separate rules/stores and alternate state encodings remain
    outside that profile. The original staged topology is unchanged.

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
  gate : string; guard : I.endpoint; product_parameter : string; machine : string option }
type rule = { source : string; gate : string; arbiter : string; lane : int; commit : string;
  trigger : I.endpoint; source_trigger : O.expression }
type machine = { source : string; bank : string }
type transition = { source : string; machine : string; gate : string; arbiter : string; lane : int; commit : string;
  trigger : I.endpoint; source_trigger : O.expression }
type expression = { source_path : string; source_expression : Json.t; endpoint : I.endpoint }
type checked_binding

val check : admitted:A.admitted_inputs -> implementation:I.t -> proposed:B.t -> checked_binding

(** Independent bounded network reconstruction. Preserves complete source policy
    grouping, ordered machine/store writers and all source occurrences; the
    local work ceiling remains enforced when [charge] is a no-op. *)
val check_network_metered : charge:(int -> unit) -> admitted:A.admitted_inputs ->
  implementation:I.t -> proposed:B.t -> checked_binding
val admitted_inputs : checked_binding -> A.admitted_inputs
val implementation : checked_binding -> I.t
val environment : checked_binding -> environment
val observations : checked_binding -> observation list
val states : checked_binding -> state list
val effects : checked_binding -> effect_binding list
val rules : checked_binding -> rule list
val machines : checked_binding -> machine list
val transitions : checked_binding -> transition list

(** Common event/gate view; transition IDs remain source transition IDs and
    [transitions] retains their machine ownership. *)
val activations : checked_binding -> rule list

(** For independently checked observable projection only. Source expressions
    must never be passed into the candidate runtime as executable callbacks. *)
val expressions : checked_binding -> expression list
val report : checked_binding -> Json.t

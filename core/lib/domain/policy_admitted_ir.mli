(** Closed typed elaboration of the existing executable policy subset.
    This neutral domain value is NOT admission or acceptance. Only the checker
    owns the abstract admitted token. Complete original requirements and all
    source fields remain retained; unsupported obligations are never erased.
    Constructors of resolved symbols and expressions are hidden. *)
open Bioc_wire
module O = Policy_operational
module type Symbol = sig
  type t
  val name : t -> string

  (** Zero-based position in the complete original declaration ledger. *)
  val index : t -> int
end
module Role : Symbol
module Subject : Symbol
module Encounter : Symbol
module Clock : Symbol
module Observation : Symbol
module State : Symbol
module Effect : Symbol
module Rule : Symbol
module Machine : Symbol
module Transition : Symbol
module Parameter : Symbol
module Requirement : Symbol

type entity = private Executor of Role.t | Target of Subject.t | Encounter_target of Encounter.t
type scope = private Executor_scope of Role.t | Encounter_scope of Encounter.t
type read = private Observation_read of Observation.t | State_read of State.t | Parameter_read of Parameter.t
type equality = Equal | Not_equal
type comparison = Eq | Ne | Lt | Le | Gt | Ge
type phase = Requested | Initiated | Completed | Failed | Timed_out
type truth_expression
and truth_term = private
  | Truth_literal of O.truth | Truth_read of read
  | All of truth_expression list | Any of truth_expression list | Not of truth_expression
  | Truth_equal of equality * truth_expression * truth_expression
  | Text_equal of equality * text_expression * text_expression
  | Integer_compare of comparison * integer_expression * integer_expression
  | Quantity_compare of comparison * quantity_expression * quantity_expression
and integer_expression
and integer_term = private Integer_literal of Z.t | Integer_read of read
and text_expression
and text_term = private Text_literal of string | Text_read of read
and quantity_expression
and quantity_term = private Quantity_literal of Q.t | Quantity_read of read
type scalar_expression = private Truth of truth_expression | Integer of integer_expression
  | Text of text_expression | Quantity of quantity_expression
type event_expression
and event_term = private Updated of Observation.t | Rising of truth_expression | Effect_event of Effect.t * phase
type assignment = private Truth_assignment of State.t * truth_expression
  | Integer_assignment of State.t * integer_expression | Text_assignment of State.t * text_expression
type arbitration_mode = Exclusive | Priority
type tie = Reject_tie | Declared_order
type conflict = Reject_conflict | Identical_only
type participant = Rule_participant of Rule.t | Transition_participant of Transition.t
type arbitration = { mode : arbitration_mode; tie : tie; conflict : conflict; order : participant list }
type authorization = At_initiation | Continuous
type unknown_response = Continue | Defer
type lifecycle = { authorization : authorization; on_unknown : unknown_response; timeout : Q.t option }
type termination = Explicit_event | Contact_loss
type clock_basis = Logical | Availability
type coverage = Sampled | Event

type declaration = private
  | Role_declaration of Role.t
  | Subject_declaration of { id : Subject.t; executor : Role.t option; encounter : Encounter.t option }
  | Encounter_declaration of { id : Encounter.t; executor : Role.t; target : Subject.t; termination : termination }
  | Clock_declaration of { id : Clock.t; basis : clock_basis; resolution : Q.t }
  | Observation_declaration of { id : Observation.t; observer : Role.t; subject : entity;
      clock : Clock.t; value_type : O.value_type; coverage : coverage; coherence : string; freshness : Q.t }
  | State_declaration of { id : State.t; scope : scope; value_type : O.value_type;
      initial : O.value; capacity : int; reset : truth_expression option }
  | Effect_declaration of { id : Effect.t; executor : Role.t; subject : entity;
      lifecycle : lifecycle; parameters : (string * scalar_expression) list }
  | Rule_declaration of { id : Rule.t; executor : Role.t; on : event_expression;
      guard : truth_expression; effects : Effect.t list; assignments : assignment list; arbitration : arbitration }
  | Machine_declaration of { id : Machine.t; executor : Role.t; scope : scope; states : string list;
      initial : string; terminal : string list; arbitration : arbitration }
  | Transition_declaration of { id : Transition.t; machine : Machine.t; source : string; destination : string;
      on : event_expression; guard : truth_expression; effects : Effect.t list; assignments : assignment list }
  | Parameter_declaration of { id : Parameter.t; value_type : O.value_type; value : O.value }
  (* Requirements are obligations, not executable instructions. Their entire
     original body is retained, including unsupported monitoring expressions. *)
  | Retained_requirement of Requirement.t


type instruction
type t

(** Structural typed elaboration only. Callers must first bound the complete
    source document. The callback charges traversals, resolutions and output
    reconstruction; exceptions propagate without returning a partial value. *)
val elaborate : charge:(int -> unit) -> Policy_document.t -> t
val instructions : t -> instruction list
val declaration : instruction -> declaration
val source_path : instruction -> string
val original_declaration : instruction -> Json.t
val name : declaration -> string
val kind : declaration -> string
val truth_term : truth_expression -> truth_term
val integer_term : integer_expression -> integer_term
val text_term : text_expression -> text_term
val quantity_term : quantity_expression -> quantity_term
val quantity_unit : quantity_expression -> Json.t
val event_term : event_expression -> event_term

(** Exact original expression bodies retained for occurrence identity and
    profile metadata checks. These views do not reconstruct or execute terms. *)
val truth_source : truth_expression -> Json.t
val integer_source : integer_expression -> Json.t
val text_source : text_expression -> Json.t
val quantity_source : quantity_expression -> Json.t
val event_source : event_expression -> Json.t

(** Reconstruct executable fields from closed typed terms and resolved symbols,
    retaining exact source metadata and literal quantity spelling. This codec
    grants no source correspondence or candidate acceptance. *)
val wire_declaration : charge:(int -> unit) -> instruction -> Json.t

(** Closed original environment authority for controlled composition. No source,
    candidate, activity evaluator or requirement verdict enters this module. *)
open Bioc_wire

val schema_version : string
val profile : string
type input_key = Antigen | Controller | Rna_a | Rna_b | Protein_a | Protein_b
type physical = {
  antigen : bool; controller : bool; rna_a : bool; rna_b : bool;
  protein_a : bool; protein_b : bool;
}
type evidence_quality = Valid | Missing | Invalid | Conflicting
type evidence = {
  status : evidence_quality; observed_tick : int option; generation : int option;
}
type effective_evidence = Fresh of evidence_quality | Stale
type lifecycle = None_event | Start | End | Reset
type bindings = {
  clock : string; executor_role : string; executor_identity : string;
  slot : string; encounter_declaration : string; encounter_subject : string;
  antigen_observation : string; controller_observation : string;
  antigen_freshness_ticks : int; controller_freshness_ticks : int;
  member_a : string; member_b : string; product_a : string; product_b : string;
}
type deadlines = {
  onset_ticks : int; controller_off_ticks : int; antigen_off_ticks : int;
  component_off_ticks : int; reactivation_ticks : int;
}
type t
type validated
type metadata = {
  domain_fingerprint : string; fixed_input_count : int;
  physical_factor_count : int; evidence_factor_count : int;
  lifecycle_factor_count : int;
}
val of_json : ?charge:(int -> unit) -> Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val decoding_work : t -> int
val metadata : t -> metadata
val validate_for : ?charge:(int -> unit) -> bindings:bindings -> resolution:Json.t ->
  deadlines:deadlines -> horizon_ticks:int -> t -> validated
val specification : validated -> t

type input_batch = private {
  tick : int; event : lifecycle; live : bool; generation : int;
  generation_started_tick : int; physical : physical;
  evidence : (input_key * evidence) list; origin : string; origin_domain : string;
}
type cursor
val initial : ?charge:(int -> unit) -> validated -> cursor
val cursor_tick : cursor -> int
val finished : validated -> cursor -> bool
val choices : ?charge:(int -> unit) -> validated -> cursor -> input_batch Seq.t
val advance : ?charge:(int -> unit) -> validated -> cursor -> input_batch -> cursor
val effective_evidence : validated -> input_batch -> input_key -> effective_evidence
val batch_to_json : input_batch -> Json.t

type usage = { prefixes : int; transitions : int; histories : int; work : int }
type enumeration = Complete of usage | Exhausted of usage | Cancelled of usage
(** Every callback history is provisional until [Complete]. Contradictions and
    enclosing charge/callback exceptions propagate unchanged. Exhaustion and
    cancellation never establish complete input coverage or admission. *)
val enumerate : ?charge:(int -> unit) -> ?cancelled:(unit -> bool) ->
  ?on_history:(input_batch list -> unit) -> validated -> enumeration

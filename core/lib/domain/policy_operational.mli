(** Dedicated bounded operational-policy representation. Decoding is not admission,
    source correspondence, realization or biological evidence. *)
open Bioc_wire

val profile : string
val descriptor_schema : string
val behavior_schema : string
type truth = True | False | Unknown
type value = Truth of truth | Integer of Z.t | Text of string | Quantity of Q.t * Json.t
type value_type = Truth_type | Integer_type | Text_type | Quantity_type of Json.t
type expression = {
  op : string; value_type : value_type option; args : expression list;
  reference : string option; value : value option; phase : string option;
  scope : string option;
}
type scope = Executor of string | Encounter of string
type arbitration = { mode : string; tie : string; write_conflict : string; order : string list }
type assignment = { state : string; value : expression }
type role = { role_id : string }
type subject = { subject_id : string; encounter : string option; executor : string option }
type encounter = { encounter_id : string; executor : string; target : string; termination : string }
type clock = { clock_id : string; resolution : Q.t }
type observation = {
  observation_id : string; observer : string; subject : string; value_type : value_type;
  clock : string; coverage : string; coherence : string; freshness : Q.t;
}
type state_store = {
  state_id : string; value_type : value_type; scope : scope; initial : value;
  capacity : int; reset : expression option; lifetime : string;
}
type lifecycle = {
  authorization : string; on_loss : string; on_unknown : string;
  timeout : Q.t option;
}
type effect_spec = {
  effect_id : string; executor : string; subject : string; lifecycle : lifecycle;
  parameters : (string * expression) list;
}
type rule = {
  rule_id : string; executor : string; on : expression; guard : expression;
  effects : string list; assignments : assignment list; arbitration : arbitration;
}
type machine = {
  machine_id : string; executor : string; scope : scope; states : string list;
  initial : string; terminal : string list; lifetime : string; arbitration : arbitration;
}
type transition = {
  transition_id : string; machine : string; source : string; destination : string;
  on : expression; guard : expression; effects : string list; assignments : assignment list;
}
type requirement = {
  requirement_id : string; kind : string; scope : scope option;
  condition : expression option; response : expression option; trigger : expression option;
  deadline : Q.t option; horizon : Q.t option; assumptions : string list;
  source : Json.t;
}
type parameter = { parameter_id : string; value : value }
type semantic = Encounter_explicit | Observation_external_evidence | Effect_abstract_attempt
  | Lifecycle_correlated_feedback | Capability_deferred
type definition_ref = private {
  definition_id : string; definition_version : string; definition_digest : string;
  definition_json : Json.t;
}
type descriptor = { definition : definition_ref; semantics : semantic }
type descriptor_bundle
val semantic_tag : semantic -> string
val definition_ref_to_json : definition_ref -> Json.t
val descriptors_of_json : Json.t -> descriptor_bundle
val descriptors_to_json : descriptor_bundle -> Json.t
val descriptors : descriptor_bundle -> descriptor list
val descriptors_digest : descriptor_bundle -> string
type node = { id : string; kind : string; source_path : string; data : Json.t }
type behavior = private {
  raw : Json.t; source_document : Json.t; definitions : descriptor_bundle;
  nodes : node list; source_ledger : Json.t; requirements_ledger : Json.t;
  assumptions : string list; unresolved_obligations : string list;
  roles : role list; subjects : subject list; encounters : encounter list;
  clocks : clock list; observations : observation list; stores : state_store list;
  effects : effect_spec list; rules : rule list; machines : machine list;
  transitions : transition list; requirements : requirement list; parameters : parameter list;
}
val behavior_of_json : Json.t -> behavior
val behavior_to_json : behavior -> Json.t
val value_type : Json.t -> value_type
val value_of_json : value_type -> Json.t -> value
val value_to_json : value -> Json.t
val expression_of_json : Json.t -> expression
val duration : Json.t -> Q.t
val get : string -> Json.t -> Json.t
val text : string -> Json.t -> string
val list : string -> Json.t -> Json.t list
val ref_id : Json.t -> string

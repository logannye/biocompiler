(** Checked abstract Behavior, not a molecular implementation or execution result.
    Constructors are hidden: every value passes operation, policy, ownership,
    constant, contact, lineage and complete requirement validation. *)
type profile = V0_1 | V0_2
type number = Integer of Z.t | Real of float
type state_value = Text of string | Boolean of bool | State_integer of Z.t | State_real of float
type source_location = { file : string; line : Z.t; function_name : string }
type scope = Contact | Environment | Internal | External
type observation = Signal_observation | Marker_observation
type band = Present | High | Low
type comparison = Lt | Le | Gt | Ge | Eq | Ne
type arithmetic = Add | Subtract | Multiply | Divide | Negate
type trigger = Condition_trigger | Event_trigger
type memory_input = Owner | Set_when | Reset_when | Duration_input
type value_mode = Unspecified | Expression
type signature_binding =
  | Bound_input of int
  | Bound_literal of Bioc_wire.Json.t
  | Bound_object of (string * signature_binding) list
  | Bound_array of signature_binding list
type scalar_binding
val binding_json : scalar_binding -> Bioc_wire.Json.t
val binding_value : scalar_binding -> number
type operation =
  | Role of { name : string; cell_type : string }
  | Scope of scope
  | Signal of { name : string; scope : scope; observation : observation }
  | Channel of { name : string; scope : string }
  | Channel_observation
  | Qualitative of band
  | Literal of scalar_binding
  | Parameter of { name : string; default : scalar_binding }
  | And | Or | Not | At_least of int
  | Arithmetic of arithmetic | Compare of comparison
  | Held_for | Recently | Became_true | Followed_by | Integrated
  | Memory of { name : string; input_names : memory_input list }
  | Memory_is_set
  | State of { name : string; values : state_value list; initial : state_value }
  | State_is of state_value
  | Signature of { name : string; module_name : string; qualname : string;
                   bindings : (string * signature_binding) list }
  | Secretion of { name : string; product : string; default : bool }
  | Rule of { trigger : trigger; name : string option }
  | Action_state_set of state_value
  | Action_report of string | Action_pulse | Action_eliminate | Action_engulf
  | Action_secrete of value_mode | Action_emit of value_mode
  | Action_present of string | Action_retain of string option
  | Action_expand | Action_rest | Action_differentiate of string
type node
val node_id : node -> Identity.Node.t
val operation : node -> operation
val kind_name : operation -> string
val inputs : node -> Identity.Node.t list
val attributes : node -> Bioc_wire.Json.t
val data_type : node -> Type_spec.t option
val role : node -> Identity.Role.t option
val source : node -> source_location option
val contact_bound : node -> bool
val requirement_ids : node -> Identity.Requirement.t list
val node_json : ?include_source:bool -> node -> Bioc_wire.Json.t
type requirement_kind = Rule_requirement | State_requirement | Memory_requirement
type requirement
val requirement_id : requirement -> Identity.Requirement.t
val requirement_kind : requirement -> requirement_kind
val requirement_source_node : requirement -> Identity.Node.t
val requirement_lineage : requirement -> Identity.Node.t list
val requirement_source : requirement -> source_location option
val requirement_json : ?include_source:bool -> requirement -> Bioc_wire.Json.t
type t
val schema_version : profile -> string
val max_integral_samples : int
val execution_policies : ?integral_step:Bioc_wire.Json.t -> profile -> Bioc_wire.Json.t
val of_json : Bioc_wire.Json.t -> t
val to_json : ?include_source:bool -> t -> Bioc_wire.Json.t
val fingerprint : t -> string
val summary : t -> Bioc_wire.Json.t
val name : t -> string
val profile : t -> profile
val nodes : t -> node list
val roots : t -> Identity.Node.t list
val get : t -> Identity.Node.t -> node option
val source_fingerprint : t -> string
val requirements : t -> requirement list
val source_links : t -> (Identity.Node.t * Identity.Node.t list) list
val policies : t -> Bioc_wire.Json.t
val parameter_bindings : t -> (string * Bioc_wire.Json.t) list
val constant_value : t -> Identity.Node.t -> number option

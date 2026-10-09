(** Closed structural foundation for supplied truth-only implementation graphs.
    No decoder, identity check or graph check establishes source preservation,
    execution, material realization, requirement satisfaction or export authority.
    Primitive transitions belong to the later independent SM-03 runtime.

    Truth wires preserve [defined], True/False/Unknown and ordered reason codes.
    An unavailable raw observation is undefined; not/all/any produce a defined
    truth (possibly Unknown) even for undefined inputs, retaining reason lists.
    Thus not(missing) and missing must differ at assignment/parameter preflight.

    The profile fixes encounter/evidence/feedback/timeout/reset/authorization/
    rising phases, then atomic settling and settled-tick monitoring. Feedback
    precedes equal-deadline timeout; register writes are atomic and attempt
    creation events enter the next microstep. Candidates cannot choose phases,
    executable source AST operands or a hidden-output projection.

    This first profile requires encounter-slot replication for evidence, state,
    edge memory, events, activation, arbitration, atomic commits and attempts.
    Executor replication is supported only for pure logic and constants. Exact
    source-to-layout binding remains a separate obligation. All-output exports
    are a structural inventory, not the later fixed observable correspondence.

    Attempt-bank capacity means simultaneous active attempts per bank and
    encounter slot. Cumulative allocations, retained old correlation records
    and work have separate runtime bounds. Reset/end invalidates active attempts
    without reusing their identities; authorization loss does not cancel them.
    The initial runtime must reject multiple initiating gates for one bank.
    Activation/attempt tokens retain the actual gate, guard-producing endpoint
    and ordered causes, allowing repeated attempts from the same gate. The
    bank authorization input must correspond to that retained guard endpoint.
    Observed-rising history refreshes once per tick before atomic settling,
    never again for an intermediate register write. These are required runtime
    semantics, not claims established by this structural decoder.

    Selected models still require separately supplied component membership and
    configuration/connection-to-material carrier authority. This module does
    not fabricate those bindings or override an empty source catalog.

    The separately named staged profile adds finite machine banks, transition
    gates and atomic transition commits. Their supplied state labels are a
    bounded alphabet, not executable source syntax. Machine writes cross the
    same atomic phase boundary as register writes. Legacy model bodies retain
    their original profile and exact identity inside a staged library.

    The explicit multi-site profile adds [Attempt_bank_sites]. Ordered request/
    authorization port pairs share one capacity and lifecycle bank. Independent
    admission requires distinct gates and commits under one exclusive arbiter
    and one actual machine bank; each activation retains its initiating site.
    Legacy profiles continue to reject this primitive. *)
open Bioc_wire

val profile : string
val observable_profile : string
val multi_site_profile : string
val multi_site_observable_profile : string
val staged_profile : string
val staged_observable_profile : string
val library_schema : string
val model_schema : string
val candidate_schema : string
val resource_profile : string

type truth = True | False | Unknown
type replication = Executor | Encounter_slots of { layout_id : string; slots : int }
type event_kind = Updated | Rising | Requested | Initiated | Completed | Failed | Timed_out
type authorization = At_initiation | Continuous
type unknown_response = Continue | Defer
type correlation = Unbound | Retained_attempt
type primitive =
  | Truth_constant of truth
  | Product_constant of string
  | Evidence_bank of { freshness_ticks : int }
  | Truth_not | Truth_all of int | Truth_any of int | Truth_equal
  | Truth_register of { initial : truth; writers : int }
  | Observed_rising
  | Event_select of event_kind
  | Activation_gate
  | Exclusive_arbiter of int
  | Priority_arbiter of int list
  | Atomic_commit of { writes : int; requests : int }
  | Attempt_bank of { capacity : int; timeout_ticks : int;
      authorization : authorization; on_unknown : unknown_response }
  | Attempt_bank_sites of { sites:int; capacity:int; timeout_ticks:int;
      authorization:authorization; on_unknown:unknown_response }
  | Machine_bank of { states : string list; initial : string; terminal : string list;
      writers : int; retained_capacity : int }
  | Transition_gate of { source : string; correlation : correlation }
  | Transition_commit of { destination : string; writes : int; requests : int }

type signal_type = Truth_value | Product_symbol | Evidence_batch | Feedback_batch
  | Event_batch | Activation_batch | Truth_write | Effect_request | Attempt_snapshot
  | Machine_snapshot | Machine_write
type direction = Input | Output
type port = { port_id : string; direction : direction; signal_type : signal_type }
type endpoint = { node_id : string; port_id : string }
type wire = { producer : endpoint; consumer : endpoint }
type external_kind = Evidence_input | Feedback_input
type external_input = { input_id : string; input_kind : external_kind; consumer : endpoint }
type occurrence_role = Declaration | Predicate | State_write | Effect_parameter
  | Clock | Lifecycle | Requirement | Metadata
type occurrence_disposition = Executable | Constant | Obligation | Retained_metadata
type occurrence = { source_path : string; role : occurrence_role;
  disposition : occurrence_disposition; targets : endpoint list }
type atomic_group = { group_id : string; arbiter : string; commits : string list }
type slot_layout = { layout_id : string; encounter_id : string; slots : int }
type authority = { source_artifact_digest : string; descriptors_digest : string;
  domain_digest : string; implementation_catalog_digest : string; library_digest : string }

type model = private { identity : Pinned_identity.t; configuration_digest : string;
  primitive : primitive; replication : replication }
type library
val library_of_json : Json.t -> library
val library_to_json : library -> Json.t
val library_profile : library -> string
val library_digest : library -> string
val models : library -> model list
val model_body_to_json : model -> Json.t

type node = private { node_id : string; model : model }
type t
val of_json : library:library -> Json.t -> t
val to_json : t -> Json.t
val implementation_profile : t -> string
val implementation_observable_profile : t -> string
val fingerprint : t -> string
val authority : t -> authority
val slot_layout : t -> slot_layout
val nodes : t -> node list
val wires : t -> wire list
val inputs : t -> external_input list
val atomic_groups : t -> atomic_group list
val semantic_exports : t -> endpoint list
val occurrences : t -> occurrence list
val ports : primitive -> port list
val primitive_name : primitive -> string
val profile_for_primitive : primitive -> string
val observable_profile_for : string -> string

(** Structural equality to independently obtained authority/inventory only.
    The later source checker must derive these arguments from original external
    authority; passing a candidate's own fields cannot establish correspondence. *)
val check_authority : expected:authority -> t -> unit
val check_occurrence_inventory : expected:string list -> t -> unit

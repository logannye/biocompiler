(** Fresh exhaustive checking of the original finite causal domain. This module
    executes source and candidate independently, checks exact correspondence,
    and independently monitors original requirements. It imports no producer. *)
open Bioc_wire
module R = Bioc_domain.Policy_realization_request
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module U = Bioc_domain.Policy_implementation_binding
module B = Bioc_checker.Policy_implementation_binding_check

val profile : string
type limits
val limits_of_json : Json.t -> limits
val limits_to_json : limits -> Json.t
type result
type checked_implementation
type startup_pass = Input | Identity

(** Every invocation freshly repeats original source and graph admission.
    Exhaustion/contradiction/mismatch stops with incomplete coverage and an
    exact retained input prefix. No branch is skipped, merged or pruned using
    candidate outputs or requirement results. Resource limits affect completion
    only; they never shrink the original semantic domain. If the explicit
    publication/work limit cannot hold even the resulting receipt, a resource
    diagnostic is raised and no result or checked implementation is returned. *)
val check : request:R.t -> behavior:O.behavior -> implementation:I.t ->
  proposed:U.t -> limits:limits -> result

(** Identical checker with an enclosing logical-data-work preflight callback
    before each source admission, graph binding, source/runtime initialization
    and initial identity/projection input pass. The callback cannot replace
    those fresh checks. Its exception propagates before a result is returned;
    default [check] invokes a no-op and retains its existing report/accounting.
    Startup charges supplement rather than reinterpret child semantic work. *)
val check_with_startup_charge : startup_charge:(startup_pass -> Json.t -> unit) -> request:R.t ->
  behavior:O.behavior -> implementation:I.t -> proposed:U.t -> limits:limits -> result
val report : result -> Json.t

(** Available only after complete finite-domain preservation and all original
    requested hard requirements pass with the profile's nonvacuity coverage.
    This grants no component/material/target/export authority. *)
val accepted : result -> checked_implementation option
val binding : checked_implementation -> B.checked_binding
val evidence : checked_implementation -> Json.t

(** A process-local, synchronous, bounded continuation channel. It supplies no
    manager implementation or acceptance authority. Application dispatchers must
    explicitly distinguish expected rejection from unexpected internal failure. *)
val protocol : string
val profile : string
val declaration : Bioc_wire.Json.t
val package_profile : string
val package_declaration : Bioc_wire.Json.t

type io = {
  read_header : unit -> string option;
  read_body : int -> string;
  write : string -> unit;
}
(** [read_header] reads at most nine bytes; [read_body n] reads at most [n].
    Return short strings on truncation or raise. [write] receives one complete
    framed message. Any write exception is uncertain: no retry or fatal write
    follows. Injected I/O must not call back into this channel. *)

type command = {
  sequence : int;
  operation : string;
  arguments : Bioc_wire.Json.t;
  body_sha256 : string;
  parent_invocation : int option;
}
type reply = Success of Bioc_wire.Json.t | Rejected of Bioc_wire.Json.t
exception Host_exception of string
(** An opaque host-owned exception token, returned without interpretation. *)

exception Closed
type t
val create : io:io -> application:Bioc_wire.Json.t ->
  dispatch:(t -> command -> reply) -> unit -> t
val run : t -> unit
(** Serve exactly one hello and its commands until close or terminal failure.
    Nested commands are dispatched only while [invoke] is awaiting its own top
    continuation. Unexpected exceptions close the channel, preserving mutations
    already performed by the application but never publishing them as success. *)

val invoke : t -> action:string -> arguments:Bioc_wire.Json.t -> Bioc_wire.Json.t
val is_closed : t -> bool
val budget : t -> Bioc_checker.Work_budget.t
(** One lifetime ancestor, including all nested dispatch and callback traffic. *)

val retain_bytes : t -> int -> unit
(** Reserve application-owned retained bytes before allocating/retaining them.
    Received bodies, application declaration, and callback arguments are charged
    conservatively and never refunded, including completed continuations. *)

val usage : t -> Bioc_wire.Json.t

(** The separately negotiated package profile installs exactly one 512 MiB
    maximum persistent-data owner during hello, before its first successful
    response. Positive reductions apply before owner allocation. Ordinary
    callback sessions remain unchanged at 128 MiB. *)
val create_package : io:io -> application:Bioc_wire.Json.t ->
  dispatch:(t -> command -> reply) -> unit -> t
val package_budget : t -> Bioc_artifact.Archive_budget.t option
(** [None] before package hello or in the ordinary profile. A returned owner is
    the exact ancestry used by subsequent channel and manager operations. *)

(* Trusted package binding: the returned identity is the actual published
   invocation, and active_command is the real dispatcher frame, never host data. *)
val invoke_bound : ?on_open:(int -> unit) -> t -> action:string -> arguments:Bioc_wire.Json.t -> int * Bioc_wire.Json.t
val active_command : t -> command

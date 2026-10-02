(** Strict bounded UTF-8 JSON. Integers retain arbitrary precision and are never
    conflated with Booleans or binary64 floating-point values. *)
type t =
  | Null
  | Bool of bool
  | Int of Z.t
  | Float of float
  | String of string
  | Array of t list
  | Object of (string * t) list

val parse : string -> t
(* Explicit large-artifact parser. The original [parse] retains v1 limits.
    Bytes may be at most 64 MiB and value nodes at most 1,000,000. String,
    numeric and nesting limits are unchanged. Object keys are not value nodes;
    artifact callers additionally enforce their complete key/value budgets. *)
val parse_bounded : max_bytes:int -> max_nodes:int -> string -> t
(* Descriptor artifact decoding counts object keys before allocating them, in
   addition to values. Original parse/parse_bounded node semantics stay intact. *)
val parse_artifact : ?on_node:(unit -> unit) -> max_bytes:int -> max_nodes:int -> string -> t
(* Bounded legacy import hooks. Object-pair duplicate diagnostics run after its
   nested values, matching a post-decoding object hook. Callbacks must reject;
   returning from either callback still fails closed. Strict APIs above retain
   their original token and diagnostic behavior. *)
val parse_legacy_artifact : ?on_node:(unit -> unit) ->
  on_duplicate_key:(string -> unit) -> on_nonfinite:(string -> unit) ->
  max_bytes:int -> max_nodes:int -> string -> t
val validate_utf8 : string -> unit
val object_fields : ?path:string -> t -> (string * t) list
val field : ?path:string -> string -> (string * t) list -> t
val exact_fields : ?path:string -> string list -> (string * t) list -> unit
val allowed_fields : ?path:string -> required:string list -> optional:string list -> (string * t) list -> unit
val string : ?path:string -> t -> string
val name : ?path:string -> t -> string
val array : ?path:string -> t -> t list
val boolean : ?path:string -> t -> bool
val integer : ?path:string -> t -> Z.t
val number : ?path:string -> t -> t
val number_to_float : ?path:string -> t -> float
val number_compare : t -> t -> int
val equal : t -> t -> bool
val int : int -> t

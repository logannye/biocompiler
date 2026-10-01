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

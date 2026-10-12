(** Additive controlled source shapes; representation only, no native admission. *)
val language_sha256 : string
type shape = String | Integer | Boolean | Null | Literals of string list
  | Record of string | Many of shape | Tuple of shape list | Union of shape list
val records : (string * (string * shape) list) list
val find : string -> (string * shape) list option

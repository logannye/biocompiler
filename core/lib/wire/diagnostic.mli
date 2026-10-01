type t = { code : string; message : string; path : string option }
exception Error of t
val fail : ?path:string -> string -> string -> 'a
val require : ?path:string -> bool -> string -> string -> unit

(** Shared checker work accounting. Nested scopes retain their own limits while
    charging every ancestor. Exhaustion raises the scope's contextual resource
    diagnostic before any counters change; a budget grants no semantic authority. *)
type t
val create : profile:string -> error_code:string -> maximum:int -> unit -> t
val nested : parent:t -> profile:string -> error_code:string -> maximum:int -> unit -> t
val charge : t -> int -> unit
(* Minimum unused allowance across the scope and every ancestor. *)
val remaining : t -> int
(* Incremental aggregate publication reservation. Keys count as nodes; bytes
   use canonical UTF-8 JSON spelling. Container/list traversal is itself bounded,
   including cyclic native JSON/list values. Reservation grants no validity. *)
type output
val create_output : profile:string -> error_code:string -> max_bytes:int -> max_nodes:int -> unit -> output
val reserve_json : output -> Bioc_wire.Json.t -> unit

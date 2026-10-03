(** Bounded container work over one supplied ancestor. Structural integrity is
    not compiler, scientific, or export acceptance. Retention is cumulative. *)
module W = Bioc_checker.Work_budget
type limits = private { max_archive_bytes:int; max_member_bytes:int;
  max_metadata_bytes:int; max_entries:int; max_path_bytes:int;
  max_json_nodes:int; max_json_depth:int; max_retained_bytes:int; max_work:int }
val make_limits : ?max_archive_bytes:int -> ?max_member_bytes:int ->
  ?max_metadata_bytes:int -> ?max_entries:int -> ?max_path_bytes:int ->
  ?max_json_nodes:int -> ?max_json_depth:int -> ?max_retained_bytes:int ->
  ?max_work:int -> unit -> limits
val defaults : limits
type t
val create : parent:W.t -> retain_bytes:(int -> unit) -> ?limits:limits -> unit -> t
(* Configure one new cumulative persistent-data owner at package lifetime
   creation. Descendant native managers/builds inherit the same sink. This is
   not a process RSS or cumulative temporary-allocation limit; unchanged child
   input/output/node/item/work/arithmetic profiles bound transient execution. *)
val create_owner : parent:W.t -> retain_bytes:(int -> unit) -> ?limits:limits -> unit -> t
val owns_retention : t -> bool
val limits : t -> limits
val work : t -> W.t
val retained : t -> int
val charge : t -> int -> unit
val product : t -> int -> int -> unit
val reserve : t -> int -> unit
val guard : t -> unit

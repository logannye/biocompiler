(** Bounded original census for material alternatives of a component program.
    Decoding establishes static well-formedness only. It does not establish
    common semantic authority, check any candidate, select a winner or grant
    material/export acceptance. Every complete child request remains original. *)
open Bioc_wire
module R = Policy_component_material_request

val schema_version : string
val profile : string
val resource_profile : string
val max_alternatives : int
val max_input_bytes : int
val max_input_nodes : int
val max_input_depth : int
val max_work : Z.t

type alternative = private { id:string; rank:int; request:R.t }
type predicate = private { max_total_nt:int }
type budgets = private { max_work:int; max_report_bytes:int; max_report_nodes:int }
type t

(** Preflight the complete envelope under fixed aggregate input limits, then
    decode every original child with the same count-only callback. Existing
    per-child molecular and semantic-input limits are unchanged. Encoding and
    hashing are charged before their passes; the declared allowance itself is
    not acceptance or a substitute for the caller's aggregate work owner. *)
val of_json : ?charge:(int -> unit) -> Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val decoding_work : t -> int

(** Original array order is retained in serialization and the fingerprint. *)
val alternatives : t -> alternative list

(** Canonical checking/anchor order is ascending bytewise ASCII ID, independent
    of rank and original array order. The later independent selector must first
    check every child, then apply the predicate and rank/ASCII-ID preference. *)
val evaluation_order : t -> alternative list
val anchor : t -> alternative
val predicate : t -> predicate
val budgets : t -> budgets

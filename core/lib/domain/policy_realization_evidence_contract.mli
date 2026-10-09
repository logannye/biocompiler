(** Independent supplied measurements and criteria. Decoding establishes bounded
    shape and complete content pins, never authenticity or biological validity. *)
open Bioc_wire
val schema_version : string
val profile : string
type quantity = private {raw:Json.t;amount:Q.t;unit:Json.t}
type interval = private {raw:Json.t;lower:quantity;upper:quantity}
type applicability = private {raw:Json.t;recipient:string;deployment:string;clock:string;domain:string;environments:string list}
type artifact = private {raw:Json.t;id:string;digest:string;media_type:string;locator:string}
type origin = Synthetic_fixture | Supplied_experiment
val origin_name : origin -> string
type provenance = private {raw:Json.t;origin:origin;producer:string;recorded_at:string;artifact:artifact}
type requirement = private {raw:Json.t;id:string;instance:string;component:Pinned_identity.t;
  mechanism_fingerprint:string;transfer:string;nominal:quantity;accepted:interval;
  minimum_replicates:int;applicability:applicability}
type protocol = private {raw:Json.t;identity:Pinned_identity.t;period:quantity;procedure:string;provenance:provenance}
type replicate = private {id:string;interval:interval}
type dataset = private {raw:Json.t;identity:Pinned_identity.t;requirement:string;protocol:Pinned_identity.t;
  applicability:applicability;replicates:replicate list;provenance:provenance}
type software = private {raw:Json.t;name:string;version:string;artifact:artifact}
type analysis = private {raw:Json.t;identity:Pinned_identity.t;dataset:Pinned_identity.t;
  replicate_ids:string list;envelope:interval option;software:software;provenance:provenance}
type dossier = private {protocols:protocol list;datasets:dataset list;analyses:analysis list}
type t
val of_json : ?charge:(int -> unit) -> Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val require_compatibility : t -> bool
val requirements : t -> requirement list
val dossier : t -> dossier option
val applicability_of_json : Json.t -> applicability
val applicability_to_json : applicability -> Json.t
val interval_to_json : interval -> Json.t

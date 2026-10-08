(** External original authority for a narrow exact mRNA structural leaf.
    Decoding is bounded shape validation, never construction, implementation,
    recipient or export acceptance. No legacy circuit request is synthesized. *)
open Bioc_wire
val schema_version : string
val profile : string
val max_members : int

(** Normative complete protein body pinned by [product.identity]. The original
    identity remains externally supplied; a matching content hash alone grants
    no component-to-product or policy-to-product correspondence. *)
val product_content_json : string -> Json.t

type regions = { utr5:string; cds:string; utr3:string; poly_a:string }
type product = { identity:Pinned_identity.t; sequence:string;
  translation_policy:Molecular_recoding.Translation_policy.t;
  provenance:Molecular_record.Provenance.t }
type member = { id:string; regions:regions; product:product; chemistry:Molecule_chemistry.t }
type t

(** Shared bounded leaves; callers retain whole-document resource preflight.
    These preserve the structural decoder's syntax without checking translation. *)
val regions_of_json : Json.t -> regions
val regions_to_json : regions -> Json.t
val product_of_json : Json.t -> product
val product_to_json : product -> Json.t

(** Closed bounded decoding preserves all original construction fields and the
    exact supplied covalent-member order. Region and product consistency is
    established only by the independent checker, never by this decoder. *)
val of_json : Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val template : t -> Payload_template.t
val member_order : t -> string list
val members : t -> member list

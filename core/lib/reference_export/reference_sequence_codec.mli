(** Exact FASTA/JSON fidelity to one typed molecular artifact. This codec does
    not establish current reference validity, admission, or export acceptance. *)
module B = Bioc_artifact.Archive_budget
type t
val export_version : string
val fasta_policy : string
val json_policy : string
val line_width_of_json : B.t -> Bioc_wire.Json.t -> int
val of_json : B.t -> Bioc_wire.Json.t -> t
val make : B.t -> fasta:string -> specification:string -> line_width:int ->
  sequence_sha256:string -> molecular_fingerprint:string -> unit -> t
val encode : B.t -> line_width:int -> Bioc_domain.Reference_molecular.Artifact.t -> t
val verify : B.t -> t -> Bioc_domain.Reference_molecular.Artifact.t -> bool
val fasta : t -> string
val specification : t -> string
val line_width : t -> int
val sequence_sha256 : t -> string
val molecular_fingerprint : t -> string
val fasta_sha256 : B.t -> t -> string
val specification_sha256 : B.t -> t -> string

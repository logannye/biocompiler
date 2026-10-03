(** Closed historical reference package declarations. Manifest labels and stored
    stage identities never grant acceptance. All allocations/work share the caller
    archive scope; metadata and request objects retain their own exact identities. *)
module B = Bioc_artifact.Archive_budget
val required_files : (string * string) list
val validate_package_path : B.t -> ?allow_reserved:bool -> Bioc_wire.Json.t -> string
module Request : sig
  type t
  val schema_version : string
  val of_json : B.t -> Bioc_wire.Json.t -> t
  val of_json_text : B.t -> string -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val make : B.t -> construct:Bioc_domain.Reference_construct.Request.t -> ?fasta_line_width:int -> unit -> t
  val construct : t -> Bioc_domain.Reference_construct.Request.t
  val fasta_line_width : t -> int
end
module Run_metadata : sig
  type t
  val schema_version : string
  val of_json : ?runtime:Bioc_artifact.Stored_zip.diagnostic_profile -> B.t -> Bioc_wire.Json.t -> t
  val of_json_text : ?runtime:Bioc_artifact.Stored_zip.diagnostic_profile -> B.t -> string -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val make : ?runtime:Bioc_artifact.Stored_zip.diagnostic_profile -> B.t -> timestamp_utc:string -> machine_label:string -> ?locations:(string * string) list -> unit -> t
  val timestamp_utc : t -> string
  val machine_label : t -> string
  val locations : t -> (string * string) list
end
module File : sig
  type t
  val schema_version : string
  val of_json : B.t -> Bioc_wire.Json.t -> t
  val of_json_text : B.t -> string -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val make : B.t -> path:string -> role:string -> sha256:string -> byte_length:Z.t -> unit -> t
  val path : t -> string
  val role : t -> string
  val sha256 : t -> string
  val byte_length : t -> Z.t
end
module Accepted_stage : sig
  type t
  type stage = Components | Construct | Molecular
  val schema_version : string
  val of_json : B.t -> Bioc_wire.Json.t -> t
  val of_json_text : B.t -> string -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val make : B.t -> stage:stage -> artifact_fingerprint:string -> record_fingerprint:string -> artifact_schema:string -> unit -> t
  val name : stage -> string
  val stage : t -> stage
  val artifact_fingerprint : t -> string
  val record_fingerprint : t -> string
  val artifact_schema : t -> string
end
module Tool : sig
  type t
  val schema_version : string
  val of_json : B.t -> Bioc_wire.Json.t -> t
  val of_json_text : B.t -> string -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val make : B.t -> id:string -> version:string -> content_fingerprint:string -> unit -> t
  val id : t -> string
  val version : t -> string
  val content_fingerprint : t -> string
end
module Manifest : sig
  type t
  val schema_version : string
  val of_json : B.t -> Bioc_wire.Json.t -> t
  val of_json_text : B.t -> string -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val make : B.t -> request_fingerprint:string -> files:File.t list -> accepted_stages:Accepted_stage.t list -> toolchain:Tool.t list -> package_version:string -> unit -> t
  val request_fingerprint : t -> string
  val files : t -> File.t list
  val accepted_stages : t -> Accepted_stage.t list
  val toolchain : t -> Tool.t list
  val package_version : t -> string
end

(** Independent reference-package checking. No compiler, pass manager, producer,
    or package reconstruction service is linked here. Imported records/reports
    are candidate data only. This profile establishes software reference and
    exact member/sequence consistency, never biological or therapeutic validity.
    Current-tool deterministic reconstruction remains a separate Core check. *)
module B = Bioc_artifact.Archive_budget
module D = Bioc_reference_artifact.Reference_package_manifest
val profile : string
val tool_ids : string list
(* Metadata authority is supplied independently at the actual current SDK call
   points, or by a pinned installed release. It is never read from the archive. *)
type authority
val authority : B.t -> package_version:string -> tool_versions:(string * string) list -> authority
val authority_pins : B.t -> package_version:string -> tool_pins:D.Tool.t list -> authority
val authority_json : authority -> Bioc_wire.Json.t
(* Only this actual checker mints a capability. Its exact bytes, independently
   supplied authority and lifetime owner remain inseparable. *)
type checked
val verify : ?runtime:Bioc_artifact.Stored_zip.diagnostic_profile -> B.t ->
  authority:authority -> ?expected_request:D.Request.t ->
  ?expected_build_fingerprint:string -> string -> checked
val require_checked : B.t -> checked -> authority:authority ->
  ?expected_request:D.Request.t -> ?expected_build_fingerprint:string -> string -> unit
val report : checked -> Bioc_wire.Json.t
val archive_sha256 : checked -> string
val build_fingerprint : checked -> string
val request : checked -> D.Request.t

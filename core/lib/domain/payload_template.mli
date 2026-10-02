(** Complete supplied construction fragments before source binding. Checked
    templates may contain only helpers or unresolved external providers; target
    context, reconstruction and biological acceptance remain separate checks. *)
type t
val schema_version : string
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val make : ?complex_members:Construction.Complex_member.t list -> ?amounts:Construction.Amount_declaration.t list ->
  ?payload_structures:Payload_structure.t list -> id:string -> sources:Construction.Root_source.t list ->
  steps:Construction.Transform_step.t list -> output_members:Construction.Output_member.t list ->
  requirements:Construction.Member_requirement.t list -> unit -> t
val id : t -> string
val sources : t -> Construction.Root_source.t list
val steps : t -> Construction.Transform_step.t list
val output_members : t -> Construction.Output_member.t list
val requirements : t -> Construction.Member_requirement.t list
val complex_members : t -> Construction.Complex_member.t list
val amounts : t -> Construction.Amount_declaration.t list
val payload_structures : t -> Payload_structure.t list
(* These conversions retain all declarations. Materialization calls the real
   contextual Construction.Request validator and can reject a valid template. *)
val from_construction_request : ?id:string -> Construction.Request.t -> t
val to_construction_request : ?id:string -> ?mode:Construction.Request.mode -> t -> Circuit_request.t -> Construction.Request.t

(** Complete workflow execution and replay for the bounded artifact channel.
    No producer, stored acceptance label or Python semantic path is consulted. *)
val implementation_version : string
val profile_version : string
val profile : Bioc_wire.Json.t
(* Separately negotiated presentation leaves every v1 profile/receipt unchanged. *)
val presentation_implementation_version : string
val presentation_profile_version : string
val presentation_version : string
val presentation_profile : Bioc_wire.Json.t
val profiles : (string * Bioc_wire.Json.t) list
val operations : string list
val validation_scopes : string list
(* The bounded control payload is decoded before transport allocates its shared
   operation budget. [handle_in] independently checks the same controls. *)
val limits_of_payload : Bioc_wire.Json.t -> Bioc_realization_checker.Verification_workflow_budget.limits
type result = { artifact : string; result : Bioc_wire.Json.t }
(* Transport charges descriptor reads/hash/parse on [budget]. This service owns
   exactly one [reserve_request] for each raw input. Transport must independently
   bound actual input bytes, since semantic inventory uses canonical bytes.
   Receipt bytes are control data; they do not consume artifact publication
   capacity. Both their bounded encoding and all artifact work share [budget].
   Descriptor transports may supply [load_retained_record] instead of an already
   parsed record. It runs only after complete fresh authority decoding, preserving
   historical authority-before-record error precedence. It must charge its read,
   parse and retained lifetime on the same [budget]; it is not a wire callback.
   V2 commands are checked after fresh authority decoding and before execution
   or retained-record loading. Presentation counts share the same work budget. *)
val handle_in : budget:Bioc_realization_checker.Verification_workflow_budget.t ->
  executable:Bioc_wire.Protocol.executable -> request_id:string -> operation:string ->
  payload:Bioc_wire.Json.t -> authority:Bioc_wire.Json.t ->
  ?retained_record:Bioc_wire.Json.t -> ?load_retained_record:(unit -> Bioc_wire.Json.t) -> unit -> result

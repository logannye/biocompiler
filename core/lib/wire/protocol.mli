val version : string
type request = { request_id : string; operation : string; payload : Json.t }
type executable = Core | Verify
type status = Ok | Error | Unsupported
val executable_name : executable -> string
val decode_request : Json.t -> request
val identity : executable -> Json.t
val response : executable:executable -> request:request option -> status:status -> result:Json.t option -> Diagnostic.t list -> Json.t
val limits : Json.t
val read_stdin : unit -> string

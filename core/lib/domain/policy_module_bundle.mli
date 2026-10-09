(** Complete original module authority. Decoding checks bounded structure only;
    it does not establish module elaboration or executable acceptance. *)
open Bioc_wire
val schema_version : string
val profile : string
type limits = private { max_work:int; max_bytes:int; max_depth:int;
  max_instances:int; max_declarations:int; max_ports:int }
type access = Context | Read | Write | Request
type port = private { name:string; declaration:Json.t; access:access; path:string }
type pin = private { id:string; version:string; content_fingerprint:string }
type template = private { raw:Json.t; pin:pin; semantics:Json.t; inputs:port list;
  outputs:port list; declarations:Json.t list; private_refs:Json.t list;
  assumptions:Json.t list; guarantees:Json.t list; source_map:Json.t list; path:string }
type target = Context_ref of Json.t | Output_ref of { instance:string; port:string }
type binding = private { port:string; target:target; path:string }
type instance = private { name:string; template:pin; bindings:binding list;
  assumptions:Json.t list; path:string }
type t
val of_json : Json.t -> t
val to_json : t -> Json.t
val context : t -> Json.t
val templates : t -> template list
val instances : t -> instance list
val limits : t -> limits
val fingerprint : t -> string
val decoding_work : t -> int
val decoding_bytes : t -> int
val pin_to_json : pin -> Json.t
(** Invocation-local accounting shared by decoding and independent checking.
    No accounting operation creates a checked linkage capability. *)
type meter
val meter : t -> meter
val charge : meter -> int -> unit
val inspect : meter -> int -> unit
val scan : meter -> Json.t -> unit
val encode : meter -> Json.t -> string
val hash : meter -> Json.t -> string
val work : meter -> int
val bytes : meter -> int

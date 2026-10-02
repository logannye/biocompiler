(** Reconstruct only from actual locked component contents and execute with the
    independent candidate runtime. No source graph, producer or acceptance
    library supplies operations, parameters, wiring or observations. *)
val implementation_version : string
val reconstruction_version : string
val resource_profile : string
type limits
val make_limits : ?max_preparation_work:int -> ?execution_limits:Synthetic.limits -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
type usage = { preparation_work : int; execution : Synthetic.usage }
(* Preparation and execution have separate explicit bounded allowances. The
   former reserves full authority, sorting and every expanded selected record
   before node construction; the latter is the unchanged synthetic profile.
   A failed stage returns neither a partial mechanism/trace nor success usage. *)
val reconstruct_with_usage : ?limits:limits -> Bioc_domain.Component_assembly.t ->
  Bioc_domain.Mechanism.t * int
val reconstruct : ?limits:limits -> Bioc_domain.Component_assembly.t -> Bioc_domain.Mechanism.t
val run_with_usage : ?until:Bioc_domain.Runtime_number.t -> ?limits:limits ->
  Bioc_domain.Component_assembly.t -> Bioc_domain.Model_execution_data.Input_frame.t list ->
  Bioc_domain.Model_execution_data.Trace.t * usage
val run : ?until:Bioc_domain.Runtime_number.t -> ?limits:limits ->
  Bioc_domain.Component_assembly.t -> Bioc_domain.Model_execution_data.Input_frame.t list ->
  Bioc_domain.Model_execution_data.Trace.t

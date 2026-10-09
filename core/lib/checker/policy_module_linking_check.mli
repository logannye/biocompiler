(** Independent exact elaboration of original module authority. A linkage token
    establishes no execution, material, assumption-discharge or clinical claim. *)
open Bioc_wire
type checked_linkage
val check : bundle:Bioc_domain.Policy_module_bundle.t ->
  program:Bioc_domain.Policy_document.t -> checked_linkage
val evidence : checked_linkage -> Json.t
val bundle : checked_linkage -> Bioc_domain.Policy_module_bundle.t
val program : checked_linkage -> Bioc_domain.Policy_document.t
val remap_diagnostic : checked_linkage -> Diagnostic.t -> Diagnostic.t

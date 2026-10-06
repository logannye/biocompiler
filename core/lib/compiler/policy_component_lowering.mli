(** Bounded untrusted arrangement of a source-produced graph under the supplied
    component composition rule. It neither creates source/material authority nor
    imports a preservation or material checker. Every result needs fresh checks. *)
module I = Bioc_domain.Policy_implementation
module A = Bioc_domain.Policy_component_assembly_rule
module U = Bioc_domain.Policy_implementation_binding
module Q = Bioc_domain.Policy_component_assembly_proposal
type proposal = { implementation:I.t; binding:U.t; assembly:Q.t }
val arrange : library:I.library -> rule:A.t ->
  Policy_implementation_lowering.proposal -> proposal

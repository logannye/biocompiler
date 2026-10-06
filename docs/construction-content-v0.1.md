# Source-neutral exact molecular construction

`Construction_content` separates exact molecular content from the legacy circuit
request and contextual `Molecule_set` envelope. A rich policy can reuse existing
construction rules without inventing a legacy circuit. This leaf does not yet
connect a policy implementation to material or authorize export.

Original authority is the complete supplied `Payload_template` plus an explicit
ordered inventory of every covalent output member. The template normalizes its
member declarations; the separate inventory preserves the original publication
order. It must be an exact permutation, with no duplicates, omissions or extras.
Template requirements, contextual obligations and provider pins remain in the
authority even when this leaf does not discharge their obligations.

The producer's `construct_template` returns untrusted values, derivations,
chemistry, features, final molecular inventory, roles/form mappings and declared
amounts. Partial constructions retain their diagnostics and missing members.
The checker independently reconstructs those contents from the original
template/order, compares every semantic candidate field and rechecks chemistry
and feature transitions. Candidate-recomputed hashes cannot replace the
original inputs. Fresh replay recomputes the complete check before comparing a
saved receipt.

`checked_content` is available only after exact-content PASS. Its scope is
`exact_supplied_template_molecular_content`; `context_status` and
`payload_completeness` remain `unassessed`. In particular, externally supplied
host inputs, recipient/deployment contracts, complete mRNA structure and
implementation-to-material correspondence require their own policy checks.
The leaf does not treat absent empirical evidence as a construction failure or
treat exact bases as evidence for a component's behavior.

Legacy construction entry points retain their original request validation,
contextual constructors, fingerprints and serialization. Producer and checker
each use their own recipe view and finalization path. The new tests include
frozen canonical legacy candidate/assessment bytes, neutral/legacy member-value
equality, literal bases, repinned sequence/derivation mutations, exact member
order, replay forgery, incomplete content and resource limits. All existing
construction/native/installed campaigns remain required alongside these tests.
Source and static review are complete; hosted validation is still required.

# Bounded material selection for one component policy

This is the contract for the bounded component-selection profile. Its public
check/replay/export development run passed at `fbd2230e8`; the current isolated
increment adds metered Core generation and requires its own hosted validation
and independent artifact audit. No prior result accepts the new generation
path. A decoded request or candidate grants no acceptance capability. The
existing component profile retains its own release and actual-main gates.

## Original inputs and supported scope

The request supplies a finite catalog of complete original component-material
requests. Each alternative describes the same policy, operating domain,
assurance, implementation contracts and executable component composition.
Material variants may differ only through an explicitly checked construction
relation. The initial relation varies a decision leader and its induced
coordinates while retaining an identical driver. The profile keeps two
component slots, three boundary links, no helpers and one RNA member.

Every alternative must pass the unchanged inner compiler checker. Only then may
an additional shared length predicate exclude it. A failed, missing, malformed
or incompletely checked child invalidates or leaves the entire selection
incomplete. It cannot become an ineligible alternative merely to produce a
winner. Biological viability is outside this compiler-semantic contract.

## Closed envelopes

The selection request uses schema
`biocompiler.policy_component_selection_request.v0.1` and profile
`biocompiler.policy_component_material_selection.v0.1`. Its exact fields are:

```text
schema_version
profile
alternatives: [{id, rank, request: complete original component request}, ...]
predicate: {max_total_nt}
budgets: {profile, max_work, max_report_bytes, max_report_nodes}
```

There are 1–16 alternatives. IDs are distinct ASCII strings of 1–128 bytes
matching `[A-Za-z0-9][A-Za-z0-9._-]*`. Ranks are integers from zero through
2,147,483,647; the length ceiling is an integer from zero through 1,000,000.
Unknown fields, floats, duplicates and digest-only substitutes are rejected.
The original array order is retained by serialization and input fingerprinting.
Evaluation order and the comparison anchor use ascending ASCII ID order.

The independent selection rule first applies the length predicate, then chooses
the smallest supplied rank, breaking ties by ascending ASCII ID. There is no
caller-selected tie order. Reordering the original array can change its input
fingerprint, but cannot change the selected alternative under a fresh check.

The selection candidate contains exactly `schema_version`,
`alternatives: [{id, candidate}, ...]` and `selected_id` (an ID or null). It must
provide the full original ID census. Its proposed winner is checked independently.
Each nested candidate retains the existing six-field component candidate:
`schema_version`, `behavior`, `implementation`, `binding`, `assembly_proposal`
and `construction`. A neutral domain codec decodes this untrusted data against
the child's original implementation library. It neither invokes a producer nor
returns an accepted token.

Accepted nested candidates must also use the canonical typed spelling retained
by the existing inner checker. The outer codec preserves the original raw
candidate. If decoding normalizes that spelling, a fresh inner capability whose
candidate fingerprint differs from the complete raw candidate is rejected.
Decoding-valid input alone does not satisfy this stricter acceptance identity.

## Common meaning and material correspondence

Common-base checking must compare the complete original implementation request,
including source, definitions, requirements, assurance, domain and implementation
library. It preserves input/resource bindings, child budgets, complete semantic
fragments, prerequisite/product records, component and connection ordering,
provider DefinitionRefs, timing, recipients, sharing and numeric capacity bounds.
Every alternative must independently derive the same ordered semantic union.

The material relation requires closed reconstruction, followed by full equality
against each supplied original. Recompute changed component content identities,
rule component/material bindings and identity, catalog pins, the context's rule
pin and record-layout fingerprint, then affected capacity layout digests and
provider content identities. Preserve all other fields exactly. Dropping
arbitrary digest fields or ignoring the entire material-authority subtree does
not establish common meaning. No reconstruction replaces original source
authority or grants acceptance by itself.

The first literal witness uses one unchanged A policy and decision graph:

| Alternative | Leader | Exact RNA | Rank |
| --- | --- | --- | ---: |
| `short` | `CC` | `CCAUGGCUUAAGGAAAA` | 1 |
| `long` | `CGC` | `CGCAUGGCUUAAGGAAAA` | 0 |

Both inner requests retain a delivery ceiling of 18 bases. An additional outer
ceiling of 17 selects `short`; 18 selects `long`; 16 yields a complete catalog
assessment with no eligible alternative and no artifact. The current A/B
fixtures have different policy graphs and cannot stand in for these alternatives.

## Bounded work and publication

The outer resource profile is
`biocompiler.policy_component_selection_resources.v0.1`. The complete invocation
is bounded by 8 MiB canonical JSON, 250,000 nodes and depth 128, in addition to
each unchanged child decoder's limits. Decode, compare and hash only after
bounded structural preflight. Charge that traversal rather than silently
discarding its cost when the declared allowance becomes available.

The declared work allowance is positive and at most 17,000,000,000 units, parsed
and bounded before conversion to the supported platform's native integer.
The checker conservatively reserves each child's complete original work
allowance before calling its fresh inner check, without refunds or reliance on
serialized usage. At most sixteen 1,000,000,000-unit child reservations and a
separate 1,000,000,000-unit outer-work ceiling account for this maximum. Existing
literal children retain their 500,000,000-unit ceilings. No child domain or
allowance is reduced to make selection finish.

The original resource version `biocompiler.policy_component_selection_resources.v0.1`
retains cumulative publication limits of at most 8,323,072 bytes and 249,968
nodes. The explicit version `biocompiler.policy_component_selection_resources.v0.2`
permits at most 1,000,000 cumulative nodes with the same byte and work ceilings.
A request must supply its exact version and allowances; selecting v0.2 does not
increase a smaller supplied allowance. Existing v0.1 requests keep their limits
and identity. This is a cumulative publication bound: the complete invocation
and each individual publication, including the actual protocol response, still
obey the unchanged 8 MiB, 250,000-node and depth-128 bounds.

The distinction is needed because fresh export publishes child reports, the
complete assessment, the standalone manifest and the actual enclosing protocol
frame. The independently supplied two-alternative example has a source-derived
lower bound of 346,508 cumulative nodes before envelope overhead; its final
frame lower bound is 159,194 nodes. Counting repeated evidence is required even
though it fits in a single transport frame. No child, losing alternative or
original obligation is removed to satisfy a budget.

One original-bound invocation scope cumulatively reserves all these occurrences
and charges checking, comparison, construction of the manifest, encoding and
hashing. Exhaustion permanently poisons the scope. The runner consumes a one-shot
guard on the actual complete response before encoding or writing success; an
error has a null result and cannot reuse the guard. If the full result cannot
fit, no selected/export authority is granted. These logical bounds are not
measurements of OCaml instructions, wall time or a global peak-memory theorem.

## Independent acceptance and fresh export

The independent checker obtains a fresh abstract `checked_material`
capability for every alternative, derives exact RNA through its checked
context/assembly/structure chain, checks the predicate and independently derives
the winner. Only a separate private checked-selection token may authorize
selection output. Reports, producer lengths and winner-only checking are not
substitutes for the complete census.

Fresh outer export must repeat the complete check and bind original inputs,
all candidate/evidence records, predicate, ranks, selected identity, exact RNA
and manifest. A losing-input edit invalidates prior selection evidence even
when the winning RNA stays unchanged. Regression acceptance must cover that
case, changed ranks and predicates, catalog permutations, ties, no eligible
alternative, weaker child obligations, omitted or forged losers, child and
aggregate exhaustion, and stale exports. Hosted native, installed and full
release/main validation remain required before this profile is accepted.

## Result and failure boundary

A completed assessment retains every returned inner report in ascending ID
order. `census_complete` means the checker visited every supplied child and
obtained its result; `all_inner_accepted` separately reports whether every child
granted a fresh capability. An inner rejection produces `inner_not_accepted`
and no winner. A wrong proposed winner produces `proposed_winner_mismatch` and
no token. An entirely checked catalog with no length-eligible alternative
produces `no_eligible_alternative` and no token. Only `checked_selection` grants
the private selection capability after complete work and publication checks.
Exceptions, including any child or aggregate exhaustion, abort the complete
assessment without a selection capability. None establishes global infeasibility.

Public native and Python check/replay/export routes, complete selection manifests
and fresh paired export are implemented in the current source batch, with their
own hosted validation still required. The prior component route and its A/B
exports do not establish those exits. The development lane therefore retains its
original component campaign and adds a separate same-A selection campaign.

## Metered Core generation

`compile-policy-component-selection` accepts exactly the complete original
`request` and preservation `limits`. Its separate
`policy_component_selection_producer` capability retains the complete verification
profile with a single compile operation, `artifact: withheld` and
`generation_work: shared_original_scope`. Verify continues to advertise only
check/replay/export and cannot invoke production. Python's explicit Core client
and `policy.component_selection.compile` negotiate both exact profiles; missing
capabilities, wrong roles, cancellation and native failure have no fallback.

Generation visits every original in ASCII-ID order and proposes a complete
candidate census. It reuses source admission, implementation lowering, component
arrangement and construction, with count-only callbacks charging their actual
traversals, comparisons, attempted matches and serialization passes. The existing
source 8M, arrangement 1M and construction 50M local work ceilings remain active;
newly covered output/staging work charges only the enclosing meter. Calls without
the new callback retain the old local thresholds and diagnostics.

One original-bound scope owns generation, the existing checker and actual-frame
publication. Generation does not consume or replace each child's unchanged
check allowance. Failed searches are charged, caught scope exhaustion remains
terminal, and a final-size debit cannot replace dynamic-work accounting. Any
unsupported child or generation exception aborts the invocation. An incomplete
candidate remains in the census for independent rejection rather than becoming
an excluded loser.

The producer proposes a length/rank/ASCII-ID winner from untrusted candidate
material. The independent checker then checks every child once under the same
scope and determines its own winner. No successful producer label grants
acceptance. `usage.charged_work` continues to describe the checking-phase delta,
so the complete result equals fresh Verify checking/replay of the generated
candidate; earlier generation still counts toward the private shared limits.
Compilation returns no artifact. Exact FASTA/manifest publication requires the
existing fresh export operation.

The hosted witness retains the preceding component campaign and all existing
selection observations except the superseded Core-compile-unsupported control.
Its 35 selection observations add Core generation, exact fresh Verify equality,
17/18-nucleotide winners, no eligible result, original-order and losing-rank
invalidation, and a corrupt losing molecule with refreshed candidate hashes.
Deterministic candidate order does not normalize the authored original array:
permuting originals changes its authority and invalidates saved replay even if
the candidate and RNA remain equal. Pure transport tests and source inventories
do not establish this hosted execution. Installed/offline and full release/main
acceptance remain subsequent gates.

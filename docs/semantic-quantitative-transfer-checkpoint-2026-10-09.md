# Conservative transfer-pair implementation checkpoint

This implements the second quantitative increment of approved roadmap item 4 in
`codex/dev-policy/semantic-foundation-v2`. It builds on the locally implemented
sampled-step/multiple-request-site path. The Git base remains
`999d3f1f93becec018b029e584512f758a899986`; the later source checkpoints remain
uncommitted because the preserved worktree index is offloaded and unreadable.
This is a local implementation checkpoint, not native or installed acceptance.

## Implemented boundary

`ReservoirCompartment` and `SampledTransferPair` describe two named reservoirs
with one shared exact substance, unit and quantum. True transfers forward and
False transfers backward. The actual transfer is the minimum of the declared
step, donor stock and recipient headroom, calculated from the same prestate.
The two amounts update atomically. Unknown and absent samples hold; reset
restores both declared initial amounts. Conservation applies within an encounter
generation and is not asserted across reset.

The native domain has a separate private typed transfer contract. It retains
both coordinates in a complete source-major Cartesian state map. The independent
checker checks every True/False/Unknown row, the exact transferred amount,
conservation, every threshold request site, selected model/component identities
and actual shared-bank wiring. Canonical zero-transfer cases have no source
transition; every moving sample has exactly one. At most sixteen joint states
need at most eighteen moving transitions, reusing existing backend bounds.

Source and independent candidate execution both replace consumed ingress events
with newly created events after each atomic round. A transfer cannot consume the
same observation update twice. This was independently reviewed against the two
engine implementations and the exact observation-to-bank binding.

Material request v0.11, local component v0.4, quantitative assessment v0.3 and
material assessment v0.7 are explicit new families. Existing realization,
primitive, assembly and context profiles are reused. The generic quantitative
checker wraps only a freshly accepted transfer-checker capability. Conservation,
full state-table and crossing evidence remain in the quantitative report pinned
by every discharged obligation and the existing named refinement evidence.
Fresh material checking and exact RNA export remain mandatory.

This is one selected joint component contract. It does not independently realize
two separately selected molecular reservoirs or infer transport from emitted
bases. Future separation needs explicit coupling, ownership, atomicity and
transport premises. General quantitative networks, uncertainty/approximation and
experimental evidence interfaces remain queued.

The planner now has fifteen targets, preserving all fourteen previous descriptor
bodies. The new target is `transfer_pair_material`; the complete catalog hash is
`9c4aed1a1424b2113c6623d5b6ccdf69d610539b3e5926dfc994cad5926c4a8d`.
Its plan remains advisory and leaves quantitative checking, execution, requirement
satisfaction, resource sufficiency and exact export as fresh obligations.

## Evidence and validation

The artificial primary fixture has two capacities of two, quantum one, forward
two, reverse one, destination threshold two and initial pair `(2, 0)`. Its
handwritten 27-row oracle covers the entire nine-state product. Thirteen-tick
keep/reset histories remain on their initial-total slice and exercise two of
three crossing sites; the third is retained and checked in the complete table.
A separate four-by-four Python authoring case covers the maximal sixteen-state
shape with eighteen moving transitions. Exact fractional units are also exercised.

Independent fixture review checked 51 complete body pins, context/domain/union
and layout references, horizon 12 with source tick allowance 13, six cumulative
attempts, shared capacity six, matching storage/providers, four state bits and
the unchanged candidate work ceiling. Fixture SHA-256 is
`a3cac81d4c3907871b2d040aef416c670beda06a888ea4d6b81ec66dbfc28aac`.
The previous scalar and sampled-step fixture bytes remain pinned and unchanged.

Local checks used source-tree CPython 3.11.15 on macOS arm64:

- 180 Python tests passed across transfer, scalar/step quantitative, finite
  machine, planning, public API, migration, named refinement and machine network.
- 34 runner/bundle tests passed using inert commands. The focused census is
  50 suites; complete wiring has 190 suites, 198 executable entries and 32
  original fixtures, with 72 ordered fixture-dependent suites.
- 70 material/kernel inventory controls passed, retaining all fourteen historical
  meaning/classification projections before refreshing current source pins.
- Strict mypy passed for nine source files. Fixture reproduction, migration,
  static dependency boundaries and the unchanged 45-record language schema passed.
- Independent source reviews covered product-state semantics, one-sample event
  consumption, profile isolation, resource and output identities, transport,
  generic evidence composition and all new native regression assertions.

These groups total **284 distinct passing Python tests**. Logs are under
`generated/semantic-foundation-local/`: `transfer-sdk-tests.log`,
`transfer-runner-tests.log`, `transfer-material-coverage-20261009.log`,
`transfer-sdk-mypy.log`, `transfer-sdk-fixture.log` and
`transfer-sdk-migration.log`. Runner messages naming native suites are mocked
scheduling controls, not native execution.

The new native suite contains 29 adversarial controls plus complete
compile/check/replay/refinement/export paths. It rejects a conserved but wrong
transfer amount, incomplete or transposed state maps, omitted counterfactual
crossings and altered material/evidence. Native assertions remain unexecuted.
Source review also corrected the exact native producer-capability test inventory
to include the earlier multi-site/step profiles and the new transfer profile.

Public API coverage is 1,406 entries across 52 files, 265 exports, 31 operation
names and 195 witnesses. Its metadata is
`de1b1202fcbfe2453c78be6fbe40828189fa28f32fc62eede742a0f4fe19225d`, preserving
the exact 1,375-entry/191-witness predecessor projection
`169ff67cf58f5e2d3babb3e9f8c63b55128a2613c2f04e1ad73d3c1884968874`.
Migration coverage is 4,208 entries. Component coverage is 35 families, 145 source
paths and 158 witnesses; whole-kernel coverage is 62 rules, 197 sources and 30
witnesses. Component metadata is
`2f9ff3a35351630b7d0f6e93e536d226e82902ef86b540470afd92c326ac0b00`, preserving
the prior 34-family projection
`9aa04a4372f754fcc7ff3947f25a8bbc773dcf13c3cf06ef49df0ae4d36384ed`.
Inventory coverage is not executed native, empirical or clinical evidence.

## Preservation and continuation

Before editing, all 89 files in the prior checkpoint were verified and archived
to `generated/semantic-foundation-local/item4-preserved-before-quantitative-composition.tar.gz`
(824,001 bytes). The new exact source snapshot is
`generated/semantic-foundation-local/transfer-source-snapshot.json`.
The original index remains 22,128,124 logical bytes with zero allocated blocks
and `dataless` flags. It was not rewritten or reconstructed, and no commit was
recorded. Restore normal index availability before committing these checkpoints.

No local native compilation/execution, extension rebuild, package synchronization,
CI dispatch, push or PR occurred. A coherent hosted checkpoint must compile and
execute the new and previous exact paths, followed by the required installed,
integration and fresh actual-main gates. Those gates remain pending; declared
fixture resource ceilings are not measured native performance evidence.

See the [transfer-pair contract](policy-quantitative-transfer-v0.1.md) for the
interface, atomic law and exact claim boundaries.

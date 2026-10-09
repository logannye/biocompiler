# Reserved transfer-network implementation checkpoint

This implements the third quantitative increment of approved roadmap item 4 in
`codex/dev-policy/semantic-foundation-v2`. The Git base remains
`999d3f1f93becec018b029e584512f758a899986`. This is a local implementation
checkpoint; native compilation, execution and installed acceptance remain pending.

## Implemented boundary

`TransferEdge` and `SampledTransferNetwork` compose two to four named reservoirs
and one to eight ordered directed transfers. All stores use one exact substance,
unit and quantum on a complete Cartesian grid of at most sixteen states. Each
edge explicitly selects True or False samples. The selected joint component owns
the complete atomic state vector.

Enabled edges reserve donor stock and receiver headroom in declared order from
one immutable prestate. Incoming stock and released room cannot fund another
edge in the same sample. All deltas commit together, conserving the total amount
within an encounter generation. Unknown and absent samples hold; reset restores
every initial amount. All-zero allocations omit a source transition; positive
flows with zero net state change retain a self-transition.

A separate private OCaml domain and independent checker preserve every reservoir
coordinate, declared edge and allocation. They check all True/False/Unknown rows,
source transitions, threshold crossings, selected models and actual shared
attempt-bank wiring. The generic quantitative checker wraps only the freshly
accepted network capability. Existing scalar, step and transfer-pair paths retain
their identities; prior pair domain/checker/test/generator/fixture sources remain
byte-identical to the preserved checkpoint.

Material request v0.12, local component v0.5, quantitative assessment v0.4 and
material assessment v0.8 are explicit new families. Existing multi-site
realization, assembly, execution and context machinery is reused. Evidence
retains ordered flow allocations, complete before/after vectors, explicit
arbitration/ownership and conservation scope through named refinement and exact
RNA export. Python transport consistency checks independently reject modified
allocations even when their aggregate state update is unchanged. Crossing reports
use state/True/False order while preserving original request-lane indices.

The planner has sixteen targets. The added `transfer_network_material` descriptor
preserves all fifteen earlier descriptor bodies. Catalog SHA-256 is
`a963318c8eb9ae742b4c8d6d21b860dbb2fd58066f1a3144c760178bb0db2c7a`;
the new descriptor is
`524d289fde18fc53d2d6f00f8a26a92e168fce12c5535fc551790629fe922d9c`.
Planning remains advisory and cannot discharge compilation or export obligations.

This does not independently realize separate molecular reservoirs or edge
transports. Reported flows are exact allocations derived from the supplied law;
the executable comparison observes the corresponding state and effect requests.
Decomposition across component owners needs an explicit reservation/commit
interface, ownership, coupling, transport and coordinator-resource premises.
Uncertainty, approximation and experimental evidence remain separate follow-ups.

## Fixture and source review

The primary artificial fixture has three binary reservoirs, initial vector
`(1,1,0)`, five directed edges and a threshold on the second reservoir. Its
independent literal oracle has 24 rows, seven source transitions, two crossing
sites and 21 assembled nodes. It exercises donor and receiver competition,
no reuse of incoming stock, reverse transfer, Unknown, absent samples and reset.
The complete table includes a crossing unreachable from the initial total-two
slice. A fully repinned positive variant places an outgoing edge first and
confirms that its released room is still unavailable within the same sample.

Independent review checked 46 complete body pins, 39 configuration digests,
75 model references, nine consistent DefinitionRefs, the catalog/model allowlist,
component/rule references and all context/domain/union/layout pins. The graph has
49 wires, 31 semantic exports, twelve boundary ports and six assembly links.
All four combinations of keep/reset over the two encounter slots produce six
cumulative attempts. Horizon 12, source allowance 13 ticks, shared attempt
capacity six and supplied storage/provider bounds remain coherent. Declared work
ceilings are not measured native performance evidence.

Fixture SHA-256 is
`1a8af7b189a66d43e4c143dc472333df16ae9966146f0a35e9be257fd203ee41`.
Additional Python cases cover a sixteen-state four-reservoir chain, priority
reversal, False threshold crossings, exact fractional units and circulating
nonzero flows with a zero-net-change self-transition. The native suite authors
37 rejection controls, two positive metamorphisms, lifecycle traces and complete
compile/check/replay/refinement/export paths. These native assertions remain
unexecuted; the positive-flow self-transition currently has Python coverage and
native source review, not a separately executed native fixture.

## Local validation

All checks ran on Darwin arm64, with interpreter provenance kept distinct:

- **182 Python tests passed on CPython 3.14.6** across transfer-network, pair,
  scalar/step quantitative, finite-machine, planning, public-API, migration and
  named-refinement modules. Log: `network-sdk-tests.log` (identical copy of
  `quantitative-network-sdk-tests.log`).
- **34 runner/bundle tests passed on CPython 3.11.15**, using inert commands.
  Log: `network-runner-tests.log`. The focused census is 51 suites; complete
  wiring has 191 suites, 199 executable entries and 33 original fixtures, with
  73 ordered fixture-dependent suites (70 operational plus three others).
- **73 material/kernel inventory tests passed on CPython 3.11.15**. Log:
  `network-material-coverage-20261009.log`. All sixteen historical metadata
  projections remain preserved.
- Strict mypy passed for nine source files using CPython 3.11.15. Deterministic
  fixture reproduction and migration checks passed. Static dependency boundaries
  and the unchanged 45-record language schema passed.

These are **289 distinct passing Python tests**. Logs are under
`generated/semantic-foundation-local/`; additional logs are
`quantitative-network-sdk-mypy.log`, `quantitative-network-sdk-fixture.log`,
`quantitative-network-sdk-migration.log`, `network-core-boundaries.log` and
`network-language-schema.log`. Runner messages naming native suites are mock
scheduling controls, not native execution. The SDK group used
`/opt/homebrew/opt/python@3.14/bin/python3.14`; the runner/coverage groups and mypy
used the explicitly selected uv CPython 3.11.15 interpreter.

Public API coverage is 1,439 entries across 52 files, 267 exports, 31 operations
and 200 witnesses. Metadata is
`404ab87f1e9deb42ff3c117d84bc7c3da8926036a429beade5b5b933a58737ff`, preserving
the complete prior 1,406-entry/195-witness meaning projection. Migration coverage
is 4,226 entries, preserving the 4,208 previous identity/classification/authority
entries and contracts. Component coverage is 36 families, 149 sources and 162
witnesses; whole-kernel coverage is 62 rules, 201 sources and 30 witnesses.
Component metadata is
`a2d26a5dfa167989898f3953c431a2feb841779453a5199a66dcaa50a360c5f7`.
Inventory coverage is not native, empirical or clinical acceptance.

## Preservation and continuation

Before editing, all 100 prior source-snapshot files were verified and archived to
`generated/semantic-foundation-local/transfer-preserved-before-network.tar.gz`
(873,048 bytes; SHA-256
`5dbf9c9d630c84a466cfab3826dc407a4ebc24fea00c528122cfb2151a711c1d`).
The new exact source snapshot is
`generated/semantic-foundation-local/network-source-snapshot.json`.

The preserved worktree index remains offloaded and unreadable: 22,128,124 logical
bytes, zero allocated blocks, `dataless`. It was not replaced or reconstructed;
no commit was recorded. Restore normal index availability before committing the
preserved checkpoints. No local native compilation/execution, extension rebuild,
package synchronization, CI dispatch, push or PR occurred. A coherent hosted
native batch and the required installed, integration and fresh actual-main gates
remain pending.

See the [network contract](policy-quantitative-network-v0.1.md) and
[roadmap](semantic-next-roadmap-2026-10-09.md) for semantics and remaining work.

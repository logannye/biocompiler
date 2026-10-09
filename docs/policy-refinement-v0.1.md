# Named policy refinement evidence v0.1

Named refinement records distinguish the relations established between the
original source document, admitted operational behavior, implementation graph,
construction content, and deployment context. Exact source occurrence and graph
binding are separate from bounded observable correspondence. Supplied component
material correspondence and conditional deployment context retain their original
premises; they do not establish empirical biological behavior or clinical safety.

The native checker constructs an opaque evidence value only from freshly checked
stage handles. Its closed composition rules derive exact source-to-graph, bounded
source-to-implementation behavior, and conditional source-to-material claims only when complete
artifact endpoints and request/domain/limit identities agree. Conjunction retains
all lower claims and their stage-local scopes. Complete material evidence contains
ten named relations and eighteen premise identities, including the complete fresh
material report. Source identity here hashes the complete original document,
including provenance, rather than the source language's provenance-excluding
semantic digest.

## Python interface

Use the explicit native transport with an existing complete component-material
request, candidate, and preservation limits:

```python
from pathlib import Path
from biocompiler import policy
from biocompiler.core_client import CoreClient
from biocompiler.core_policy_refinement import PolicyRefinementClient

client = PolicyRefinementClient(CoreClient(Path("/path/to/biocompiler-verify"), role="verify"))
checked = policy.refinement.check(
    request, candidate=candidate, limits=limits, client=client,
)
if checked.evidence is not None:
    for claim in checked.evidence.claims:
        print(claim.relation, claim.source.stage, claim.target.stage, claim.scope)

replayed = policy.refinement.replay(
    request, candidate=candidate, limits=limits, report=checked.result, client=client,
)
```

Both operations perform fresh complete native material checking. A rejected
material assessment retains its full report in `checked.material_report` and has
`checked.evidence is None`. Replay additionally compares the entire saved wrapper
with the fresh result. Changed original inputs require fresh checking; neither a
saved report nor its fingerprints authorize acceptance.

`RefinementEvidence`, `RefinementClaim`, `StageIdentity`, `RefinementScope`,
`RefinementPremise`, and `RefinementDerivation` are frozen typed descriptive views.
Claim and premise arrays are tuples, vocabulary uses closed literal types, and
`.to_data()` returns an independent JSON copy. The result's `.result` and
`.material_report` properties also return independent snapshots. Public view
constructors are useful for inspection and cannot construct native capabilities.

The SDK validates the exact negotiated profile, closed shapes, original-input and
fresh-report hashes, all ordered claims and premises, and stage-local limits and
material scopes. It validates the final derivation's shape; child evidence hashes
describe a native derivation whose internal checked handles are not present in
the JSON. Python does not reproduce that proof or execute a policy. Only the
selected fresh native checker establishes the relations. There is no Python
composition, proof-import, candidate-production, or material-export operation on
this interface.

The protocol operations are `check-policy-refinement` and
`replay-policy-refinement`, negotiated under `policy_refinement`, with wrapper
`biocompiler.core.policy_refinement.v1` and evidence
`biocompiler.policy_refinement_evidence.v0.1`. The wrapper retains the entire fresh
component-material assessment and hashes the complete request, candidate,
invocation, and material report. All supported original component-material
profiles use the existing material checker unchanged, including the bounded
finite-machine family. Acceptance remains scoped to its explicit operating domain,
limits, original requirements, supplied models, composition rules, and context.

## Validation boundary for this implementation checkpoint

The focused Python tests use inert protocol peers to exercise transport identity,
typed immutable views, rejection retention, replay, and tamper detection. Strict
Python type checking is separate from native proof checking. These tests do not
establish native execution or empirical material validity. Native checker and
service tests are authored separately and require hosted validation of the exact
revision before native acceptance is claimed.

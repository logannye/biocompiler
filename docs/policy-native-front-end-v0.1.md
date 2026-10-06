# Expressive policy native front end v0.1

This increment connects the immutable `biocompiler.policy` source family to the
OCaml core and standalone verifier. It implements a closed representation and
source-contract assessment at the Layer 3/4 boundary. Native compilation and
execution are validated on hosted CI; source implementation alone is not a
completed migration gate.

The native path consumes complete frozen programs, build requests or compilation
submissions. It does not coerce them into legacy Behavior v0.1/v0.2: doing so
would lose distinctions such as unknown observations, subject correlation,
effect occurrences, scoped memory and required outcomes. Existing executable
profiles retain their separate contracts.

## Public entry points

Choose an installed native executable explicitly:

```python
from pathlib import Path
from biocompiler.core_client import CoreClient
from biocompiler.core_policy import PolicyClient
from biocompiler.policy import native

client = PolicyClient(CoreClient(Path("/absolute/path/to/biocompiler-verify"), role="verify"))
assessment = native.assess(frozen_request, client=client)
replayed = native.replay(frozen_request, assessment=assessment, client=client)
```

`frozen_request` is a `PolicyProgram`, `BuildRequest` or
`CompilationSubmission`. A caller with already frozen JSON can instead use
`PolicyClient.assess(document)` and
`PolicyClient.replay(expected_document=document, assessment=report)`.
The typed bridge serializes; it does not run Python semantic validation first.

```sh
biocompiler policy assess-native request.policy.json \
  --verify /absolute/path/to/biocompiler-verify
```

The CLI also accepts `--core`, an optional `--expected-sha256` executable pin,
and `--timeout`. Exactly one executable selection is required. Exit status is
0 for a source-valid assessment, 1 for source diagnostics, and 2 for an input,
protocol or process error. `check`, `inspect`, `schema` and other ordinary
authoring commands continue to work without importing the native bridge or
discovering a backend. A selected native rejection, crash or timeout never
retries through the Python compiler.

## Operation and authority boundary

| Operation | Input | Result |
| --- | --- | --- |
| `assess-policy` | `{document}` | A fresh source-contract assessment |
| `replay-policy-assessment` | `{expected_document, assessment}` | Recomputed assessment, only when the complete retained assessment matches |

Both operations are exposed by the core and standalone verifier. The latter
retains its producer-free link graph. Shared domain decoding and canonical
hashing are trusted primitives; replay reruns source checking rather than
trusting a saved status, digest or producer report. This is independent of a
policy producer, not a second independently implemented source checker.

The negotiated `policy_frontend` capability pins the document profile,
assessment schema, implementation, resource profile, validation scope and
supported stages. Python verifies the exact profile and response shape, input
and assessment identities, complete ordered declaration and requirement
ledgers, source correspondence and fixed claim boundaries. It does not duplicate
the native semantic rules.

`status=valid` means that the implemented source-contract checks found no
diagnostics. Every result still reports:

```text
semantic_status = unresolved
target_status = unassessed
lowering = unsupported
artifact = withheld
```

Source validity cannot authorize sequence export, deployment or therapeutic
acceptance. A declared capability or implementation binding is supplied data,
not evidence that an implementation realizes an operation.

## Preserved representation and checks

`Policy_document` validates all 45 closed record kinds, exact fields, literal
vocabularies and container types without executing Python. It preserves array
order and every occurrence. The checker retains declaration values, occurrence
IDs and matching source spans, including all requirements whether supported or
unresolved. Diagnostic paths begin at `/document` for stable replay independent
of the request envelope.

The source checker checks reference closure and kinds; lexical subject binding;
observation, executor and target ownership; expression types and exact units;
state scopes, initialization and access; explicit effect lifecycle and event
references; rules, machines and transition declarations; arbitration inventories;
message/channel ownership and payloads; deployment role/chassis/delivery
declarations; and submitted definition pins and feature/dependency inventories.
Diagnostics identify specific source paths. These checks do not interpret
arbitrary semantic-definition prose, prove guards mutually exclusive, simulate
traces or establish progress.

Exact numeric text is interpreted through integer/rational arithmetic, never
binary64. Native ingress accepts frozen canonical `Quantity.amount` spellings;
it rejects alternate spellings such as `-0`, `0.0` or exponent aliases instead
of silently changing supplied bytes. Python constructors may normalize numeric
authoring inputs before freezing. `Unit.scale` retains its original bounded
decimal spelling and is checked exactly.

The resource profile bounds documents to 2 MiB of canonical JSON, depth 64,
100,000 visited key/value nodes, 262,144 UTF-8 bytes per string, 256 characters
per numeric spelling, and decimal exponents of magnitude at most 1,024. Source
checking has a deterministic work budget of 8,000,000 charged operations.
Resource exhaustion is an error, never source validity or proof of infeasibility.
The outer core protocol also applies its existing envelope/process limits.

## Identities and replay

| Identity | Contents |
| --- | --- |
| `program_digest` | Program with source maps and provenance excluded |
| `document_digest` | Selected request or program with source maps and provenance excluded |
| `artifact_digest` | Entire supplied top-level document, including submission metadata and source correspondence |
| `assessment_fingerprint` | Complete emitted native assessment |

A submission retains separate program/request/catalog/semantic-bundle identities
and dependencies. Native ingress checks these pins against supplied records;
the checker recomputes feature and dependency metadata. Two source maps may
share a semantic document digest while differing in artifact identity. Replay
is bound to the original complete document and recomputed complete assessment.
Equal digests establish identity under this canonicalization, not semantic
equivalence or biological validity.

## Validation and remaining migration work

The frozen representation corpus contains eight abstract examples in program,
request and submission form (24 documents), with Python canonical identities.
Native suites cover closed-schema and numeric mutations, source-contract
diagnostics, complete ledgers, service routing and fresh replay. Python tests
use adversarial mock peers to check transport integrity; those are not native
execution evidence.

Hosted installed campaigns run all frozen documents through both executables,
replay complete assessments, reject forged reports and invalid source controls,
and exercise the installed CLI outside the checkout. Import/execution guards
exclude Python compiler/evaluator/verification authority. Receipts retain actual
executable, interpreter, source, fixture and assessment identities. Cross-platform
comparison requires Linux x86_64 and macOS arm64 on Python 3.11 and 3.14. All
existing migration corpora and final release gates remain required.

The next Layer 4/5 increment needs a versioned operational policy IR and source
semantics for three-valued evidence, encounter/target identity, scoped finite
state, event ordering, effect permission/completion/failure, concurrency and
temporal/spatial contracts. Definition meanings currently include prose;
compilation needs explicit executable semantic definitions and compatible
realization contracts. Unsupported definitions must remain unresolved.

Later increments must lower into that IR with complete source correspondence;
check preservation independently; connect catalog realization and target
capability checks; retain exact material artifacts and evidence; and cut over
each public path only after its required parity and installed validation gates.
This front end supplies a lossless checked entry boundary for those steps. It
does not complete LM-21, LM-25, LM-26 or the production cutover.

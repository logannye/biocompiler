# Reference construct pipeline v0.1

This profile turns an independently selected whole DNA or RNA CDS component into
a checked Construct IR layout. It does not emit sequences or infer that the
selected reference realizes a synthetic behavior program.

## Input authority

Load the accepted offline manifest with `load_reference_manifest(path,
expected_fingerprint=...)`. The trusted hash must come from the caller's reviewed
selection, not from the candidate being checked. The loader verifies retained
source and review files. `ReferenceSelection` additionally pins the exact
reference record. Resolve its sequence-reference component through the locked
registry and create a `CompositionRequest` with explicit source requirements.

`prepare_reference_construct(manifest, selection, composition, registry)` freezes
the expected molecule and placement before candidate generation. The supported
layout contains precisely one whole component, forward, at frame zero, spanning
`[0, reference_length)` in both source and molecule coordinates. The component
reference, unknown payload features, assumptions and source requirements survive
unchanged. Delivered topology and localization remain unspecified.

## Checked execution

```python
build = bc.run_construct_pipeline(
    request,
    registry,
    {manifest.reference_set_id: manifest},
)
assert build.result.scope == "reference_construct"
assert build.check_result.passed
```

The manager first admits an independently checked Components root. Its registered
checks validate current reference/registry identity, the supported authority and
conditional composition. This is a structural entry point; no placeholder
Intent, Behavior or Mechanism pass is used.

The Components → Construct pass generates a candidate, then separately checks it
against the frozen request and current registry/reference records. The checker
does not import the generator. Pass source links must match the selected
requirements exactly, and the profile cannot introduce an observation mapping
that implies behavioral evidence. Changed membership, component/reference
versions, orientation, frame, coverage, assumptions or unknown features fail.

The pass declares layout changes and invalidates conditional composition and
biological claims. Composition is freshly checked for the supported layout;
biological claims remain unresolved. Richer features, junctions, regulatory
relationships and multiple molecules are explicit schema records but have no
acceptance rule in this profile.

## Completion and freshness

`reference_construct` completeness requires reference authority, conditional
component linkage and exact layout/source checks. It leaves emitted-sequence
identity, complete delivered-payload features and molecular behavior unresolved.
Neither `exact_cds` nor `complete_payload` is a supported completion scope here.
`run_molecular_pipeline` separately completes the [exact-CDS emission profile](exact-cds-pipeline-v0.1.md). General `compile()` remains unavailable for intent designs.

Before reusing an in-memory result, call
`build.manager.result("construct", scope="reference_construct")` after updating
changed dependency roots. It recursively checks admission and assembly snapshots.
`build.check_result.freshness(request, candidate, registry, manifests)` separately
checks the historical layout report. Changed layout, request, target, composition,
registry, reference, model lock or checker identity makes dependent evidence
stale. Canonical artifact fingerprints include retained source locations; no
sequence-byte identity is claimed by these archival layout hashes.

Manifests are immutable snapshots. Neither API watches local files or remote
registries. Reload changed source files through the pinned loader and supply the
new current identities before reuse. JSON inspection reads historical content;
it cannot grant current acceptance.

See the runnable [DNA/RNA example](../examples/reference_construct.py),
[Construct IR](construct-ir-v0.1.md), [independent checking](construct-checking-v0.1.md)
and [pass manager](pass-manager-v0.1.md).

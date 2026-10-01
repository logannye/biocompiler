# Reproducible synthetic builds v0.1

The synthetic build packages a checked intent → behavior → mechanism workflow,
optionally extended through executable component assembly.
It retains the complete frozen request, finite input history, explicit observation
horizon, selected generator configuration, component catalog and locks, accepted
stage records and independent response checks. This is a software-model package:
no molecular construct, sequence, biological evidence or human therapeutic
admission is created. `molecular_behavior` remains unresolved.

## Build and independently verify

The temporal example authors dwell, repeated pulses and resettable memory using
only deterministic local fixtures:

```sh
PYTHONPATH=src python examples/synthetic_build.py --output generated/synthetic
PYTHONPATH=src python -m biocompiler synthetic-build \
  --request generated/synthetic/request.json --output generated/synthetic/rebuilt.bcb
PYTHONPATH=src python -m biocompiler synthetic-inspect generated/synthetic/rebuilt.bcb
PYTHONPATH=src python -m biocompiler synthetic-verify generated/synthetic/rebuilt.bcb \
  --expected-request generated/synthetic/request.json
```

With an installed package, `biocompiler` replaces `PYTHONPATH=src python -m
biocompiler`. The CLI reads versioned JSON; it never executes user-provided Python
or fetches sources. The example executes authoring code explicitly and saves a
request for subsequent JSON-only builds. The output parent must already exist.
Build failures and unexercised/unknown response obligations cannot publish a
success archive.

`synthetic-verify --expected-build TRUSTED_BUILD_FINGERPRINT` is an alternative
when the canonical fingerprint was retained independently at a prior accepted
build. A fingerprint copied from the same untrusted package is not independent
authority. `synthetic-inspect` checks the container, inventory and hashes, but
labels the result historical. Imported PASS labels never grant current acceptance.

## Frozen input authority

`SyntheticBuildRequest(realization, history, until, config)` is immutable and uses
`biocompiler.synthetic_build_request.v0.2`. `realization` is a fully frozen
`RealizationRequest`; `history` is `SyntheticHistory(tuple_of_InputFrame)`; `until`
is an explicit finite horizon in canonical seconds; `config` preserves the exact
selected `SyntheticGeneratorConfig`. Both combinational and temporal profiles
remain available and use their respective current catalogs.

`profile="synthetic_components"` explicitly requests the further component stage;
the default remains `synthetic_realization`. The source BuildRequest retains its
synthetic-realization authority, and the enclosing build request freezes this
additional completion scope. A changed package profile changes its authority and
identity. Neither profile permits molecular or human completion.

Authored constraints/preferences trigger [bounded implementation selection](synthetic-selection-v0.1.md).
The requested config remains frozen in `inputs/config.json`; the selected
candidate carries its exact chosen config. Both identities and the selection
report are retained. Without authored selection controls, `selection.json`
explicitly records `not_requested`, and generation uses the chosen config directly.

The versioned `SyntheticHistory` JSON contains exactly `schema_version` and
`frames`. Every frame has exactly `time`, `signals` and `contacts`. Signals map
node IDs to complete `SignalSample` objects with `value`, `present`, `high` and
`low` fields, each unused field explicitly null. Contacts map object identities
to these same signal maps. Histories begin at zero, strictly increase and end no
later than `until`. Domain consistency, measurement completeness, response
coverage and minimum observation horizon are established by the independent
checker rather than assumed from JSON validity.

The request fingerprint binds all of these inputs, including exact source
correspondence. Expected realization-only authority is deliberately insufficient:
changing observations, horizon or generator policy changes the build request.
Strict parsing rejects duplicate JSON keys, unknown fields and stale schemas.
History and its nested samples are immutable after construction.

All source locations must already be logical relative POSIX paths when the
request is frozen. The package does not rewrite source locations or repair
fingerprints. The example authors its nodes with the logical path
`examples/temporal_pipeline.py`. Host locations and execution timestamps belong
in optional `RunMetadata`, supplied to the API or through `--run-metadata`.
Build-request provenance locations and timestamps must be empty; portable source
identity and dependency declarations remain in the request.

## Package content and reproducibility

A synthetic `.bcb` is the same bounded, canonical stored-ZIP container used for
reference packages, with a distinct `SyntheticBuildManifest` schema. The shared
archive tool version is `biocompiler.reference_archive.v0.3`; prior saved tool
pins require fresh reconstruction. Its fixed
inventory is:

| Path | Content |
| --- | --- |
| `request.json` | Complete frozen authority |
| `inputs/history.json` | Immutable observation snapshots |
| `inputs/config.json` | Requested generator policy and profile |
| `inputs/catalog.json` | Trusted current digital component catalog |
| `stages/request.json` | Input stage identity and unresolved obligations |
| `stages/behavior.json` | Accepted authoritative lowering and source correspondence |
| `stages/mechanism.json` | Accepted candidate, dependencies and independent checks |
| `candidate.json` | Generated mechanism, observation map, source map and component locks |
| `selection.json` | Exact bounded alternatives/checks/rejections, or explicit selection-not-requested status |
| `checks/realization.json` | Fresh independent finite-history result and dependency identities |
| `result.json` | Scope, input/stage identities, component locks and unresolved obligations |

The explicit `synthetic_components` profile adds exactly four files:
`assembly.json`, `stages/components.json`, `checks/composition.json` and
`checks/component-behavior.json`. These retain executable locked records, actual
wiring and bindings, the structural link result and independent execution of the
reconstructed assembly. Profile-specific exact inventories reject erased stages
or a relabeled completion scope. Manifest and file schemas are now `v0.2`.

The separate `manifest.json` records every inventoried file's exact byte length
and SHA-256, the complete request identity, tool versions and package version.
All file identities and the accepted stage records enter the canonical build
fingerprint. `run.json` is separate and optional; its host paths are informational
and are never opened. Different run metadata changes archive bytes but leaves
canonical build identity unchanged. Without changing run metadata, identical
frozen inputs and trusted toolchain reproduce identical archive bytes even after
relocation. Fixed ZIP timestamps, entry order, file modes and canonical JSON
make that boundary deterministic.

Fresh verification requires the independent full request or expected build
fingerprint, checks software-use admission again, then reruns the current trusted
generator, model, behavior evaluator and checkers with the retained request.
It obtains the current profile-specific catalog from the installed compiler,
not the package's declared catalog. Every reconstructed canonical file and the
entire manifest must match. A modified candidate, forged check, erased obligation,
changed catalog or stale model fails even if its file hashes were recomputed.

## Publication and limits

`build_synthetic_package(request, run_metadata=None)` returns a `SyntheticPackage`.
`verify_synthetic_package(data, expected_request=...,
expected_build_fingerprint=...)` returns the reconstructed package only after
current checks pass. `publish_synthetic_package(package, output)` rechecks it
before writing one sibling temporary archive, syncing it and atomically replacing
the destination. Failed validation or publication preserves the existing complete
archive and removes the temporary file. This provides single-file atomic
visibility, not a guarantee of parent-directory durability after power loss.

The shared archive reader never extracts members. It rejects traversal, duplicate
members, symlinks/executable files, unsupported compression or ZIP metadata,
noncanonical bytes, extra/missing files and oversized inputs. Current limits are
64 MiB per archive, 16 MiB per member, 1 MiB for archive metadata and 128 entries.
CLI input JSON is also bounded to 16 MiB; run metadata is bounded to 1 MiB.
Only the fixed synthetic inventory is admitted, so executable authoring payloads
cannot enter a package. Human targets fail closed at build, reconstruction and
publication boundaries.

The completed scope is the explicitly requested finite-history synthetic
realization or synthetic component assembly. It does not prove
all possible histories, empirical performance or complete-payload feasibility.
See [temporal semantics](synthetic-temporal-v0.1.md) for timer/reset ordering and
[reference packaging](reference-build-v0.1.md) for the separate exact-CDS profile.

Run `PYTHONPATH=src python examples/synthetic_design.py --output generated/design`
to author an operator constraint, select a passing alternate implementation,
reconstruct a component package and explore 100 declared mixed-input histories.
The [verification workflow](synthetic-verification-v0.1.md) separately retains
failed and unknown diagnostic reports; they cannot be published as accepted builds.

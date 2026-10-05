# Expressive policy authoring implementation handoff

Checkpoint date: 2026-10-05. Implementation commit:
`71345fe06c5ed516ee9f31ad82cd3d8ce8553f9f`.
The checks below ran against the source bytes committed at that revision;
the subsequent handoff commit changes documentation and the evidence index only.

Worktree: `work/reference-package-continuations`, branch
`codex/reference-package-continuations`. This increment started from clean
`cecb75f1890a08d163b48900eca52e419f5be481` and retains that prior work.
No push, PR mutation, hosted dispatch or merge was performed.

## Delivered scope

The [language guide](policy-language-v0.1.md) documents the new
`biocompiler.policy.v0.1` family and contains executable Python examples.
The package supplies the Python SDK, file interchange, CLI and notebook
inspection surface. Studio and conversational authoring remain deferred clients.
No lower-layer policy execution or molecular realization was implemented.

- Immutable typed declarations and a mutable `ProgramBuilder`, with draft holes,
  explicit resolution, freezing, source correspondence and named expansion scopes.
- Roles, subjects, encounters, observations and bound quantifiers with explicit
  identity, correlation, visibility, uncertainty and lexical binding.
- Exact numeric declarations, units, clocks, temporal and spatial expressions;
  scoped finite state, counters, reset, lifetime and inheritance declarations.
- Rules and state machines; effect initiation, completion, failure, cancellation,
  attempt identity and authorization lifecycles; concurrency and arbitration.
- Population channels, per-emission message identity, coordination, bounded
  behavior, external controls, safety and progress requirements.
- Versioned semantic definitions, chassis profiles, deployment/delivery and RNA
  cardinality constraints, implementation catalog locks and assurance requests.
- Closed data-only JSON, generated schema, deterministic digests, atomic file
  publication, structured diagnostics, document differences and dependency graphs.
- Escaped notebook previews; `policy check`, `inspect`, `diff`, `export-schema`
  and `export-request`; immutable compiler submissions and caller-supplied
  capability declaration comparison.
- Eight abstract examples spanning gating, secretion, staged cleanup/repair,
  encounter and target memory, local restraint, coordination and lineage.

The guide defines the intended interpretation contracts for future consumers.
Structural completeness is distinct from semantic correctness or implementability:
`semantic_status` stays `unassessed`, and submission export records
`backend_execution: not_performed`. Examples contain no molecular sequences or
therapeutically validated profiles. No automatic conversion to older Behavior
documents or fallback execution discards the new declarations.

## Compatibility changes

The root package now lazily loads its original 524 exports. The isolated
`biocompiler.entrypoint` dispatches policy commands without importing compiler or
native modules; legacy commands initialize the original public surface in its
original order and use the existing CLI.

The original corpora, original test bodies, frozen capture tools and pre-existing
witnesses remain unchanged. A separate exact source counterpart records the
entrypoint changes. Reviewed source projections restore historical bytes only
after checking the actual source; observations, stdout, stderr, exceptions,
callback identities, filesystem contents and order are not normalized.

`core/test/test_reference_contracts_corpus.ml` has a finite source-reader prelude
to read that counterpart. This is test infrastructure, with static restoration
checks only. It has not been compiled or executed natively in this increment.
Python fixtures for native protocol harnesses are not native validation.

The migration inventory records the authoring package as retained Python and
passes its 3,668-entry consistency check. Existing cutover checkboxes remain open.
Hosted CI gained one strict policy typing command in the existing typing step;
the original release checks and their coverage were retained.

## Local validation

| Check | Observed result | Boundary |
|---|---|---|
| Policy suite | 96 tests pass on Python 3.11.15 and 3.14.6 | Python authoring behavior |
| Strict mypy | All 24 policy modules pass with installed mypy 1.20.2 | Hosted pinned version remains to run |
| Documentation | Both Python blocks run on both interpreters in isolated directories | Abstract authoring examples |
| Pure wheel | Built with Python 3.11; 27 relevant members match source bytes; no native libraries | Python packaging only |
| Fresh installations | Python 3.11.15 and 3.14.3: eight examples and 23 real console commands pass per installation | Outside checkout, compiler/native imports blocked |
| Legacy source/control suite | 98 of 99 pass; one capture stops on an occupied exclusive directory | Initial failure log retained |
| Isolated selection recapture | All 72 children pass, 68 console and four module | Full checker replay; not a clean rerun of the 99-test suite |
| Legacy workflow CLI | All 70 children pass within the source/control suite | Frozen original CLI observations |
| Original references | Eight contract and nine pipeline methods pass | Historical original counterparts |
| Whole workflow recapture | 376 uninstrumented and 376 captured methods pass | Exact historical comparison with reviewed source projections |
| Python protocol fixtures | Workflow and 72-child selection fixtures pass | No native executable used |
| Inventory and whitespace | 3,668 inventory entries consistent; `git diff --check` passes | Static checks |

The whole-workflow comparison retains 385 contexts, 69,236 API calls, 9,463
documents and 47,901 prior occurrences, with zero unclassified observations.
It applies 52 reviewed optional-core signature projections and returns
`complete_original_workflow_recapture_equal`.

The pure wheel is
`generated/policy-validation/wheels/biocompiler-0.1.0.dev29-py3-none-any.whl`
(904,885 bytes), SHA-256
`acae25b79cb7a7a58119c0b88bdf32871f3504b55c4c5d30dbac06d493a8fbe4`.
Homebrew Python 3.14.6's wheel-build attempt encountered its existing `pyexpat`
linkage failure; the available managed Python 3.11 interpreter built the pure
wheel successfully. No native rebuild or environment repair was performed.

Fresh-install receipts and the wheel are retained under
`generated/policy-validation/`. Legacy captures, logs and complete receipts are
retained under `generated/migration-next/policy-integration/`. These generated
files are local, ignored evidence, not hosted release artifacts. Their hashes
and interpretation boundaries are indexed in
[policy-authoring-validation.json](../protocol/policy-authoring-validation.json).

## Repeating checks

Run the authoring suite with each desired supported interpreter:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_policy*.py'
python3 -m mypy --config-file tools/mypy-policy.ini
python3 tools/migration_inventory.py --check
git diff --check
```

The installed-package checker installs nothing. Run it from outside the checkout
with the installation's interpreter, package root and real script directory:

```sh
PYTHONPATH="$installed_root" "$installed_python" /absolute/path/to/tools/check_policy_install.py \
  --installed-root "$installed_root" --scripts "$installed_root/bin"
```

Run the complete captures sequentially: their fixed temporary directories require
exclusive ownership, and an occupied directory is a refusal to overwrite it.

```sh
PYTHONPATH=src:tests:. PYTHONHASHSEED=0 python3 tools/check_synthetic_selection_cli_corpus.py \
  --output generated/migration-next/policy-integration/selection-cli-python314.json

PYTHONPATH=src:tests:. PYTHONHASHSEED=0 python3 - <<'PY'
from pathlib import Path
from tools import freeze_realization_workflow as frozen
from tools import check_workflow_routed_recapture as checker
frozen.OUT = Path(
    "generated/migration-next/policy-integration/workflow-capture"
).resolve()
raise SystemExit(checker.main([
    "--check",
    "--output",
    "generated/migration-next/policy-integration/workflow-source-lineage.json",
]))
PY
```

## Outstanding work and next boundary

1. Run the complete hosted release gates against the exact integrated revision
   once remote work is authorized. Local evidence here does not close them.
2. In dedicated lower-layer work, implement the independent OCaml decoder and
   authoritative semantics for this explicit profile: identity and uncertainty,
   time and observation coverage, units, quantified domains, state and lifecycle,
   concurrency, effect/message correlation, progress and assumptions.
3. Add reference execution, target feasibility, compositional obligations,
   realization and lowering, independent checking and acceptance. Validate each
   profile before enabling production dispatch; unsupported features must remain
   explicit failures or unresolved obligations.
4. Connect Studio and conversational clients to these same immutable documents
   in their dedicated work. Neither a visual builder nor an AI authoring service
   is included in this checkpoint.

No OCaml/Rust compilation, native execution or native packaging was performed.
All four migration production cutover gates remain separate and incomplete.

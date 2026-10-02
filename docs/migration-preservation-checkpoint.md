# Migration GitHub preservation checkpoint

2026-10-02. The user requested push/merge before usage credits expire.

The `codex/ocaml-workflow-public-checkpoint` branch now contains a coherent
implementation batch for review and fresh hosted validation: compatible native
workflow presentation v2, independent source preflight, immutable Python views,
and the complete original CLI child-process baseline. See
[the public contracts](../protocol/workflow-public-contracts-v1.md).
Existing PR validation is preserved. No automatic merge is enabled.

The new batch passed focused local Python checks: 42 transport/view tests,
73 static/boundary/CI tests, 22 campaign/lineage tests, strict mypy for ten
modules, and all fourteen original workflow recapture tests (98.109 seconds).
Groups overlap. All 70 CLI children also reproduced the frozen baseline with
actual current-source metadata retained separately. The migration inventory
contains 3,075 entries. Native compilation, 88 native suites, installed campaigns
and the full 36-job gate require hosted execution at the new exact revision.
No local native compilation or execution was performed.

## Existing PR snapshot

No PR below has completed its full gate, so none is ready to merge. Counts are
an observation, not a validation receipt; dependent jobs may not yet exist.

| PR | Exact pushed source | Required jobs | Latest observation |
| --- | --- | --- | --- |
| [#52](https://github.com/logannye/biocompiler/pull/52) | `23b142b42a263227a8565403fb4f62cc8a1d638c` | 31 | [Run 36980274253](https://github.com/logannye/biocompiler/actions/runs/36980274253): 27 passed; remaining gates pending |
| [#53](https://github.com/logannye/biocompiler/pull/53) | `7449f71c89966b9123752a6ed69d6c4d0ae4710b` | 31 | [Run 36980275430](https://github.com/logannye/biocompiler/actions/runs/36980275430): 28 passed; remaining gates pending |
| [#54](https://github.com/logannye/biocompiler/pull/54) | `7098c102ba02fc42f0dad25632cd81fc0fb5886f` | 31 | [Run 36980279079](https://github.com/logannye/biocompiler/actions/runs/36980279079): 27 passed; remaining gates pending |
| [#55](https://github.com/logannye/biocompiler/pull/55) | `d59af59488344812b5d8895b339c37e852411d54` | 31 | [Run 36980282550](https://github.com/logannye/biocompiler/actions/runs/36980282550): 24 passed; remaining gates pending |
| [#56](https://github.com/logannye/biocompiler/pull/56) | `2024d8fdd2a9a8c300ef2dc0980623b820f1997c` | 31 | [Run 36980326616](https://github.com/logannye/biocompiler/actions/runs/36980326616): 21 passed; remaining gates pending |
| [#57](https://github.com/logannye/biocompiler/pull/57) | `11f2a88d6ea98631ec0812c308160c76c4e3f192` | 36 | [Run 36984193045](https://github.com/logannye/biocompiler/actions/runs/36984193045): 12 passed; remaining gates pending |
| [#58](https://github.com/logannye/biocompiler/pull/58) | `166b5a49090223dabb7852a6dd36d91aee2cc3a6` | 36 | [Run 36984199358](https://github.com/logannye/biocompiler/actions/runs/36984199358): 13 passed; remaining gates pending |
| [#59](https://github.com/logannye/biocompiler/pull/59) | `f7b81a1da0236f2b4187e24b1352d49d788296d4` | 36 | [Run 36984201005](https://github.com/logannye/biocompiler/actions/runs/36984201005): 14 passed; remaining gates pending |

The source-lineage correction in PR57–59 retains all original corpus and source
witness pins; it replaces only the obsolete direct-hash assertion with the
existing reviewed lineage verifier. Earlier partial native passes are historical
and cannot validate replacement revisions. Merge in dependency order only after
the exact current revision, full gate and complete artifact/tree checks pass.
The integrated-main receipt for PR51 also remains to be checked.

## Remaining migration scope

The original public workflow functions and CLI still execute the Python route.
Native public routing, complete installed view/CLI conformance, R6 pipelines,
archives and export, distribution, default cutover, Studio/conversational
integration and broader LM exits remain open. The roadmap marks the actual CLI
capture checkpoint complete while leaving these migration exits unchecked.

# Migration GitHub preservation checkpoint

2026-10-02. The user requested push/merge before usage credits expire.

Implementation through PR59 is committed and pushed. The separate
`codex/ocaml-workflow-public-checkpoint` branch preserves the next-work plans
and draft CLI capture tool without restarting existing PR validation.
No PR below has completed its full gate, so none is ready to merge.
No automatic merge has been enabled. This is a status snapshot, not a
validation receipt or completion of the migration.

| PR | Exact pushed source | Required jobs | Latest observation |
| --- | --- | --- | --- |
| [#52](https://github.com/logannye/biocompiler/pull/52) | `23b142b42a263227a8565403fb4f62cc8a1d638c` | 31 | [Run 36980274253](https://github.com/logannye/biocompiler/actions/runs/36980274253): 20 passed; remaining gates pending |
| [#53](https://github.com/logannye/biocompiler/pull/53) | `7449f71c89966b9123752a6ed69d6c4d0ae4710b` | 31 | [Run 36980275430](https://github.com/logannye/biocompiler/actions/runs/36980275430): 27 passed; remaining gates pending |
| [#54](https://github.com/logannye/biocompiler/pull/54) | `7098c102ba02fc42f0dad25632cd81fc0fb5886f` | 31 | [Run 36980279079](https://github.com/logannye/biocompiler/actions/runs/36980279079): 26 passed; remaining gates pending |
| [#55](https://github.com/logannye/biocompiler/pull/55) | `d59af59488344812b5d8895b339c37e852411d54` | 31 | [Run 36980282550](https://github.com/logannye/biocompiler/actions/runs/36980282550): 12 passed; remaining gates pending |
| [#56](https://github.com/logannye/biocompiler/pull/56) | `2024d8fdd2a9a8c300ef2dc0980623b820f1997c` | 31 | [Run 36980326616](https://github.com/logannye/biocompiler/actions/runs/36980326616): 15 passed; remaining gates pending |
| [#57](https://github.com/logannye/biocompiler/pull/57) | `921e984704bc6575f88ad09e389d64beb1411ed2` | 36 | [Run 36980328540](https://github.com/logannye/biocompiler/actions/runs/36980328540): 13 passed; remaining gates pending |
| [#58](https://github.com/logannye/biocompiler/pull/58) | `683c6a23d3ddbecc514c614cd55506df46437057` | 36 | [Run 36981094835](https://github.com/logannye/biocompiler/actions/runs/36981094835): 12 passed; remaining gates pending; failed: unit-tests (3.11, 4) |
| [#59](https://github.com/logannye/biocompiler/pull/59) | `4d14a08b4ebcc7de95b2ef28fd5de74c2760bb2b` | 36 | [Run 36983237687](https://github.com/logannye/biocompiler/actions/runs/36983237687): 0 passed; remaining gates pending |

Some dependent jobs do not exist until prerequisite jobs finish. Observed
check counts must not substitute for the complete required job census.
PR59 Linux compilation passed; its 87-suite test step is running. PR58 Linux
compilation and its 85-suite step passed, but a Python 3.11 shard failed.
These partial observations do not establish either complete gate.

## Resume

1. Diagnose the PR58 Python shard failure and propagate any necessary correction
   through dependent branches without discarding their existing work.
2. Review complete exact-revision CI, aggregate accounting, full artifacts and
   native binary identity before merging PR52 onward in dependency order.
   Preserve all 31/36 required jobs and independently check integrated-main runs.
3. Read the [roadmap](language-migration-roadmap.md),
   [public view plan](migration-workflow-public-view-plan.md), and
   [presentation plan](migration-workflow-presentation-plan.md). The default
   Python workflow/CLI implementations are unchanged.
4. Review and test `tools/freeze_workflow_cli.py`: its 66-case census and syntax
   were inspected, but no actual child cohort, golden baseline or independent
   repeat has run. Do not cite it as conformance evidence.
5. Freeze the original CLI behavior before adding native routes. Resolve compact
   presentation profile compatibility, command-error precedence and structural
   view import/serialization boundaries. Preserve full artifacts and historical
   source lineage; do not narrow the 64 MiB artifact boundary.

Public workflow routing, R6 pipelines/archives/export, distribution, default
cutover, Studio/conversational integration and broader LM exits remain open.
No local native compilation or execution was performed for this checkpoint.

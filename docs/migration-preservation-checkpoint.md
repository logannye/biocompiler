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
| [#57](https://github.com/logannye/biocompiler/pull/57) | `11f2a88d6ea98631ec0812c308160c76c4e3f192` | 36 | [Run 36984193045](https://github.com/logannye/biocompiler/actions/runs/36984193045): replacement full validation pending |
| [#58](https://github.com/logannye/biocompiler/pull/58) | `166b5a49090223dabb7852a6dd36d91aee2cc3a6` | 36 | [Run 36984199358](https://github.com/logannye/biocompiler/actions/runs/36984199358): replacement full validation pending |
| [#59](https://github.com/logannye/biocompiler/pull/59) | `f7b81a1da0236f2b4187e24b1352d49d788296d4` | 36 | [Run 36984201005](https://github.com/logannye/biocompiler/actions/runs/36984201005): replacement full validation pending |

Some dependent jobs do not exist until prerequisite jobs finish. Observed
check counts must not substitute for the complete required job census.
The former PR59 Linux compilation passed; former PR58 Linux compilation and
its 85-suite step passed. Those are historical observations only. PR58's Python
3.11 shard failed because the locked-component corpus still required byte equality
with source from before the optional native routes. The correction applies the
existing strict source-lineage witness to that one assertion: 224 unchanged
sources and exactly three reviewed routes among 227 entries. Six focused census
and lineage tests pass. Frozen corpus bytes/pins and production behavior are
unchanged. The correction is pushed to PR57–59; their replacement runs above
must pass in full. Superseded diagnostic logs are retained locally.

## Resume

1. Follow the replacement PR57–59 validation runs for the pushed source-lineage
   correction. Do not transfer earlier partial successes to the new revisions.
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

# Installed authoring correction and earlier failure feedback

PR #85 source `705480688a7e37e6c0f03447226350684512342f` failed the macOS
Python 3.14 fixed-continuations campaign in [run 37158616787](https://github.com/logannye/biocompiler/actions/runs/37158616787/job/111326572424).
The campaign failed after 2.487294 seconds with zero completed continuation checks.
The fresh-install job reached it only after roughly 67 minutes of earlier work.
The actual tested merge was 69ecd56d2ec408d5a86b5035d57588687a461b72.
This failure is diagnostic evidence, not release acceptance.

The frozen portable-source helper emits the relative label
`examples/temporal_pipeline.py`. The unchanged example resolves that label
against its working directory, so fresh installations outside the checkout
failed before the example could freeze its request. The new campaign adapter
anchors only that label at source construction. The unchanged example then
produces its original logical path. The adapter preserves the process working
directory, every original body, other source labels, callback order and final
request/history bytes. Both original-counterpart capture and native replay use
the bound context. Its source is included in the finite child overlay and
campaign source pins. The separate source delta restores the complete original
14-file installed-path witness; no frozen source or oracle was rebaselined.

Six authoring controls and six diagnostic controls pass on each existing local
Python 3.11.15 / 3.14.6 runtime. The 11 existing and extended CI-plan controls also pass on
both. The independent source review checks all 17 campaigns and 46 original source
and packet paths. These are pure controls; no native work ran locally.

Both short unit-plan jobs now run the new authoring/diagnostic controls before
discovery. Native jobs depend on those plans, so this cheap failure can stop
expensive work early. All tests still execute in their full accounted shards.
The 38-job / 23 ordinary-receipt graph and every original release gate remain.
Failed or timed-out installed commands print at most 64 KiB / 80 lines / 1,000 ASCII
characters per line, with escaped workflow-command/control syntax. Complete
logs remain intact, success output stays retained, and timeout identity is
preserved. This changes feedback latency; it does not establish an end-to-end
speedup or successful installed/native acceptance.

Retained proof files identify their exact source bytes and validation limits.
A fresh exact-source hosted run, both complete PR audits, and actual-main
validation remain required before consolidation and cleanup. PR #86 integration
may overlap actual-main validation under the user's explicit order change.

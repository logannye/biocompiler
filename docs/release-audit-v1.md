# Complete release artifact audit v1

`tools/release_audit.py` prepares and independently checks the current complete
release profile from explicit source and GitHub API authority. The code and
`protocol/release-audit-v1.json` are versioned repository files. Each run produces
only inert input records, a plan and evidence; it does not generate Python helpers.

The tool is supplementary to the full hosted workflow. A successful PR check
still requires owner acceptance, an exact-head normal merge and a separate
complete actual-main run. No result transfers to another source revision or run.
It never performs native compilation, native execution, packaging, test discovery
or the large legacy semantic replays retained by hosted jobs.

## Inputs and authority

Use an independently reviewed, clean tool checkout and pass its full commit as
`--tool-revision`. `--source-root` is a separate clean, complete checkout of the
source being audited. A sparse checkout is sufficient for the tool but not the
source. Read-only Git commands capture each checkout before the process/network
denial guard is installed. All subsequent checks are local and inert. The source
checkout and tool checkout must remain frozen for the duration of the audit.

The caller obtains and authenticates current GitHub API records. An expected
identity copied from the same untrusted records is not independent authority.
Pass the independently reviewed authority JSON digest with `--authority-sha256`
and the authenticated packet digest with `--packet-sha256`; these digests belong
in an external review/invocation record, not inside the files they authenticate.
No network or GitHub mutation is performed by this tool.

The packet schema is `biocompiler.release_api_packet.v1`, with exactly `schema`
and `files`. Each `files` entry has exactly a relative `path` and `sha256`.
Duplicate JSON keys, nonfinite numbers, redirected files and oversized JSON fail.

The PR authority schema `biocompiler.pull_request_identity.v1` names repository
name/ID, main and PR branches, PR number, source H, base B, tested merge C, tree,
previous head, run/attempt, workflow ID/path, suite ID and Actions app ID/slug.
Its packet contains `run`, `commit` (the raw Git commit C), `head_commit` (raw H),
`main_ref`, `merge_ref`, `pr` and `suite`. The checker requires an open unmerged
PR, exact repository identity, PR event, ordered C parents `[B,H]`, equal H/C
trees, exact suite before/after and matching run/suite head tree fields.

The actual-main authority schema `biocompiler.actual_main_identity.v1` instead
names the separately accepted PR head, premerge main P, new merge M and accepted
tree, plus the same run/workflow/repository authorities. Its packet contains
`run`, raw `commit` M, `main_ref`, merged `pr` and `suite`. It requires a push to
main with source=tested=M, ordered parents `[P,accepted PR head]`, the accepted
source tree, the normal merged-PR identity and exact suite before/after. Main
acceptance cannot be synthesized by relabeling a PR receipt.

The exact closed authority fields and literal examples are in
`tools/release_audit_identity.py` and `tests/test_release_audit_identity.py`.

## Prepare, then check

Use absolute paths and a fresh output path under a task-owned ignored evidence
directory. The caller retains the original API responses and downloaded ZIPs.
For example, with independently reviewed values substituted for the uppercase
placeholders:

```sh
python -B tools/release_audit.py prepare \
  --tool-revision TOOL_COMMIT --source-root /absolute/source-checkout \
  --authority /absolute/evidence/authority.json --authority-sha256 AUTHORITY_SHA \
  --packet /absolute/evidence/packet.json --packet-sha256 PACKET_SHA \
  --output /absolute/evidence/plan.json

python -B tools/release_audit.py check \
  --tool-revision TOOL_COMMIT --source-root /absolute/source-checkout \
  --authority /absolute/evidence/authority.json --authority-sha256 AUTHORITY_SHA \
  --packet /absolute/evidence/final-packet.json --packet-sha256 FINAL_PACKET_SHA \
  --plan /absolute/evidence/plan.json --plan-sha256 REVIEWED_PLAN_SHA \
  --jobs /absolute/evidence/jobs.json --artifacts /absolute/evidence/artifacts.json \
  --archive-paths /absolute/evidence/archives.json \
  --output /absolute/evidence/final-check
```

Preparation permits only queued, running or completed-success run/suite states.
It does not accept artifacts. Final checking requires the complete successful
run/suite and all 74 physical jobs. Jobs and artifact metadata must be complete
single JSON objects after pagination, retaining their exact `total_count`.
`archives.json` maps artifact names to existing absolute ZIP paths. Acquisition
is outside this inert tool: retain its authenticated API size/digest and full ZIP
CRC evidence, use the profile's transfer/storage bounds, and never execute ZIP
contents. The audit rehashes original ZIP bytes, validates every central entry,
and reads or extracts only the required inert evidence. CRC is checked for every
member it reads; full acquisition CRC remains an explicit caller premise.

Every final check independently rebuilds the entire source plan and compares it
to the externally pinned plan. Rehashing a substituted plan cannot change the
expected jobs, schemas, source files or native arguments. The whole workflow,
Dune plan, direct-group plan, unit protocol and adapted policy function bodies
have explicit versioned correspondence checks. Tool modules load before source
modules, so source-side older audit tools cannot replace the selected tool version.

## Fixed scope and limits

The profile retains 74 jobs, 59 ordinary receipts, 14 unit artifacts, 102 required
ZIPs and 128 required artifact metadata entries. It covers both native platforms,
151 executable entries plus 23 fixtures, all 149 native suites and 67 direct
command groups; four installed slots with 17 campaigns each and 20 group receipts;
all six architecture/policy comparisons and both prebuilt routes. Successful-run
skips are limited to the two exact failure-only example uploads and 27 exact
inapplicable hosted Python bootstrap steps.

The reviewed workflow selects the frozen source profiles Python 3.11.15 and
3.14.6 while retaining the minor-version matrix and receipt names. Unit consumers
still authenticate and select their plan's exact patch. The profile also requires
the explicit Python setup step before authority recording in each of the three
inline RNA, architecture and circuit comparison jobs. A changed workflow hash
requires a reviewed profile update; pinning the interpreter does not waive source,
runtime, receipt or full-run identity checks.

The workflow at `aeb3c95c7` adds an exact Python 3.11.15 cache bootstrap before
the existing setup action in seven job definitions. The audit checks all 38
expanded bootstrap slots against their reviewed runner, platform, Python minor,
campaign group or wheel tag, step name, literal condition and checkout/setup
ordering. It requires bootstrap success in all eleven macOS ARM64 Python 3.11
slots and a skipped step in the other 27 slots. Missing, duplicated, renamed,
moved or condition-altered bootstrap steps fail; a successful bootstrap on an
inapplicable slot also fails. This condition-specific handling grants no other
skip allowance. The supplementary `python-bootstrap.yml` feedback workflow is
outside release acceptance and cannot substitute for any of the 74 release jobs.

Archive limits remain 640 MiB compressed and 4 GiB expanded per outer ZIP,
512 MiB per member, 300,000 members, 4 GiB total compressed, 20 GiB total declared
expanded, 4 GiB selectively extracted and 2 GiB expanded per nested native bundle.
The acquisition profile retains three transfers and a 900-second per-transfer
bound. Exceeding a bound requires a reviewed profile change; it cannot omit a
required artifact. Extracted data files use mode 0600. Published Core/Verify bytes
are read only to establish their identity; no executable is run.

Large legacy semantic/reproducibility reconstruction and browser/native outcomes
remain explicitly hosted observations. Their complete successful jobs, receipts,
identities, original command plans and relevant owned byte closures stay required.
The proof labels those limits rather than claiming local semantic re-execution.

The focused regression group is:

```sh
python -B -m unittest tests.test_release_audit_identity \
  tests.test_release_audit_units tests.test_release_audit_policy \
  tests.test_release_audit_artifacts tests.test_release_audit_orchestration
```

The tests use literal synthetic API/unit records and small ZIPs; none is real
release evidence. They preserve original identity/unit rejection controls,
source-to-adapter body/dependency correspondence, exact workflow step conditions,
16 comparator schemas, pinned input rejection and boundary/one-over archive checks.

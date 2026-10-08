# Anchored main identity for a versioned release

`biocompiler.anchored_main_identity.v1` is an additive identity route for an
already tested normal merge M after main advances to Q. It does not change the
original PR or actual-main routes: `actual_main_identity.v1` still requires its
supplied current main reference to equal M. All artifact profiles, counts,
source correspondence rules, archive checks and hosted semantic limitations are
unchanged. A new reviewed tool revision and independently reviewed authority,
packet and freshly derived plan are required; old proof hashes are not reused.

The release remains exactly M, its accepted tree, and its fresh automatic main
push run/attempt. No result transfers to Q. This route avoids making later main
work a prerequisite for distributing the independently checked version M.

## Explicit input authority

The authority retains every original actual-main identity field, changes only
its schema to `biocompiler.anchored_main_identity.v1`, and adds exactly:

- `main_anchor_sha256`: SHA-256 of the retained original main-ref response at M.
- `main_anchor_captured_at`: its independently authenticated UTC capture time.
- `observed_main_revision`: full Git revision Q, distinct from M.
- `observed_main_ref_sha256`: SHA-256 of the newly observed main-ref response at Q.
- `observed_main_captured_at`: independently authenticated UTC observation time.
- `ancestry_sha256`: SHA-256 of the authenticated GitHub comparison M...Q.

Times are caller-authenticated acquisition provenance, not timestamps inferred
from a reference object or independently established by this inert checker.
They must use explicit UTC, with merged PR time ≤ anchor time ≤ observed time
and run update time ≤ observed time. A review must bind the historical anchor
to its original acquisition/merge proof. Rehashing an arbitrary old reference
cannot supply that missing external authority.

The packet contains exactly `run`, `commit`, `pr`, `suite`, `main_anchor`,
`main_ref`, and `ancestry`. `main_anchor` holds the unchanged historical raw
reference; `main_ref` holds the newly observed reference. These roles must never
be interchanged or presented as contemporaneous observations. All raw records
are externally authenticated through the packet digest. `read_packet` checks
the exact file hashes and returns the full API pin map. The anchored dispatcher
requires this map and additionally compares the three authority-bound raw
reference/comparison hashes. Acquisition callers must likewise compute pins
from actual raw bytes rather than copy expected values.

`check_anchored_main_identity` reuses the unchanged complete normal-merge/push
identity checker with the explicitly historical anchor, then checks Q and the
comparison separately. The original checks still require exact repository,
normal ordered merge parents, accepted PR/tree, push event, main branch,
run/attempt, workflow, suite before/after, and successful final run/suite states.
Preparation can explicitly retain the existing nonfinal acquisition mode;
it never supplies final acceptance.

## Bounded ancestry observation

The comparison API URL must name the exact repository and full M...Q revisions.
`base_commit.sha` and `merge_base_commit.sha` must equal M, status must be
`ahead`, and `behind_by` must be integer zero. `ahead_by` and `total_commits`
must be equal integers from 1 through 100. The complete commits list must have
that exact length, unique full revisions, and Q as its last entry. Each entry
has one through eight distinct, nonself parent revisions. Its bounded supplied
parent graph must contain a path from Q back to M. Truncated, detached, wrong-tip,
wrong-base and type-confused observations reject.

This is authenticated bounded GitHub metadata, not execution of Git or native
code, independent reconstruction of raw Git object hashes, or validation of
Q's changed files. The observed tip is a point-in-time provenance record; the
result does not assert that it remains the latest branch tip indefinitely.
A comparison outside the stated bounds requires separate reviewed support,
not silent truncation or a generic ancestry fallback.

## Result and retained evidence

The result uses `biocompiler.anchored_main_identity_result.v1` and scope
`anchored_merge_and_push_identity_with_observed_descendant_tip_not_tip_release_acceptance`.
It retains the original source/tested M, tree, ordered merge parents,
run/attempt and `requires_success`, and adds:

- `main_anchor`: M, its capture time and exact raw reference SHA-256.
- `observed_main`: Q, its observation time/raw SHA-256, and
  `release_acceptance: false`.
- `ancestry`: raw comparison SHA-256, base M, head Q, complete bounded commit
  count, and authority `authenticated_bounded_github_comparison_metadata`.

The complete release audit still rebuilds its source plan and checks every
required job, archive, receipt and profile obligation. Owner acceptance must
recognize this distinct identity scope and retain the original anchor proof,
fresh observed reference/comparison and all API pins in release evidence.
The release notes must identify M as the shipped version and distinguish Q's
unvalidated later changes. No native rerun is implied solely by this additional
inert identity route; no existing acceptance is broadened or relabeled.

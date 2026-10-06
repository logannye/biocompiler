# Complete component release artifact audit v1

Select `--profile complete-component-release-v1` explicitly for the component
release. The default remains `complete-release-v1`, whose versioned profile is
unchanged. Both profiles require independently authenticated source/run/API
identity, a clean tool checkout, a separate complete source checkout, and the
full hosted release gate described in `release-audit-v1.md`.

This additive profile is derived from source
`5717cb28885957e07f4f58805160bdc888f42b01`. Its exact workflow SHA-256 is
`2a51ab6a1cdceddf74aca2f42f2bf09a6d2bb9b1aa5d78127d6182cf2487462e`;
its Dune source-plan SHA-256 is
`baab2c4295654235b016ea895153b100f6cacbf00bf2aaa516aba35791780442`.
A source or workflow change requires reviewed correspondence checks and a new
exact-source plan. A prior development or release result cannot transfer.

## Preserved scope and added component evidence

All 74 physical jobs, 59 ordinary receipts, 14 unit artifacts, 102 required ZIPs
and 128 artifact metadata entries remain required. The profile retains all 67
direct command groups, 17 installed campaigns per runtime, 20 installed group
receipts, all six architecture/policy comparisons and both prebuilt routes.
It requires 156 native suites and 158 executable entries plus the original 23
fixture entries. The private original-declaration emitter is not an installed
compiler or a native bundle member.

The exact physical step maps additionally require independent original emission
in both native builds, transport of each platform's originals into the four
existing supplied-wheel slots, and the complete v0.2 prebuilt comparison. All
original material, offline-consumer, wheel ownership, mutation and lifecycle
checks remain required. The additional component checks bind the independently
authored A/B originals, complete installed SDK observations, producer-free offline
Verify observations and exact RNA/manifest ZIPs to the current source and native
roles. The audit reads retained bytes and reconstructs their checks without
running Core, Verify, the declaration emitter or any installed executable.

The same 38 hosted Python bootstrap slots remain exact: eleven applicable
macOS ARM64 Python 3.11.15 slots must succeed, and 27 inapplicable slots must be
skipped. Only those skips and the two original failure-only example uploads are
permitted. The fast development and Python-bootstrap feedback workflows supply
no release acceptance.

## Independent source and function correspondence

Before installing the audit's subprocess/network denial guard, the CLI captures
an additional read-only Git tree catalog for `core`, `src`, `tools`, `protocol`,
`.github` and `pyproject.toml`. The component plan requires every scoped tracked
file exactly once. It checks canonical paths, regular-file Git modes, blob
identities, actual file bytes and executable bits. Each plan record contains
`sha256`, `size`, `git_blob` and `mode`.

The component adapter independently walks those same source roots and rechecks
the complete current census, excluding only `__pycache__` directories and the
native `core/_build` tree. Omitted tracked files, extra source files, changed
bytes or modes and redirected paths fail. The original packaging source archive
catalog keeps its existing scope; `.github` is additional component provenance,
not an inferred change to the original packaging recipe.

Thirteen source-function pins preserve the five original policy-comparison
authorities and all nine component adapter originals, with one overlapping
consumer comparator. Adapter tests independently reverse each narrow authority
substitution and compare the complete function body and imported dependencies
against the current source. The plan includes explicit reviewed counts so final
native checks and reporting use the selected profile. Native checker defaults
retain the old 149-suite/151-executable scope; the component counts must be passed
explicitly. Complete member sets, fixture pins, argument order and log census
remain mandatory for either profile.

## Invocation and acceptance boundary

Use the same authenticated authority, packet and archive inputs as the original
audit. Add the profile selector to both preparation and final checking:

```sh
python -B tools/release_audit.py prepare --profile complete-component-release-v1 \
  --tool-revision TOOL_COMMIT --source-root /absolute/source-checkout \
  --authority /absolute/evidence/authority.json --authority-sha256 AUTHORITY_SHA \
  --packet /absolute/evidence/packet.json --packet-sha256 PACKET_SHA \
  --output /absolute/evidence/component-plan.json
```

Final `check` must use that same selected profile, externally pinned prepared
plan, complete successful API records and exact archive bytes. Existing archive
size, extraction, transfer and metadata limits remain unchanged. The final audit
is supplementary to owner acceptance, an exact-head normal merge and a separate
complete actual-main run. This profile establishes compiler correspondence under
supplied contracts and sequence templates; it does not establish biological
viability, general policy support or production default cutover.

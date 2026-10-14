# ADR 0010: Versioned static-expression obligation dispositions

- Status: implemented in the M1 working branch; focused local checks and direct native workflows passed; hosted/main acceptance pending
- Date: 2026-10-13
- Charter: AC-02, AC-05, AC-06 and AC-07
- Capabilities: CAP-11 static expression and CAP-12 project/package workflows
- Roadmap: M1 / AR-01

## Context

At the v0.1 baseline `18ce1ac64fde799892683460360da008f9e6ae14`, the static
expression checker labeled safety/progress, requested
assurance and expression/material correspondence as discharged when nominal
encoding and length pass. The profile contract instead makes the first
inapplicable and the latter two conditional. The report's top-level conditional
scope and unassessed empirical/human-use fields do not repair incorrect row
meanings. A reader also needs each row's original source occurrence and complete
fresh evidence dependencies.

The v0.1 Python reader validated the child obligation list against itself.
Coherent omission of an original obligation could therefore escape its census
check. The corrected transport check independently reconstructs the mandatory IDs
from the complete original request without becoming a second semantic compiler.

## Decision

Version the assessment, native checker and service implementation identities to
v0.2. Keep the original request, candidate, source profile, resource profile,
validation scope, result envelope, export and manifest schema identities. The
material authority and public operation signatures remain unchanged.

Apply one explicit disposition contract:

- Runtime execution, temporal/uncertainty semantics and safety/progress are
  `not_applicable` under the closed static-source admission, even when the
  separate material conjunction fails.
- The encoding/length objective is `discharged` only when its exact checks pass,
  within the existing conditional profile. It is `unresolved` on failure.
- Realizability, chassis/delivery suitability, catalog applicability, requested
  assurance, the selected implementation and expression/material correspondence
  are `conditional` when the encoding/material/length conjunction passes and
  `unresolved` when it fails. Their evidence binds
  the fresh source admission, fresh structure report and complete original
  expression contract identity.
- Complete recognized normative definitions are `discharged`; other complete,
  reachable supplied definitions remain `conditional`. Each row retains its
  complete original body and reference, source admission and contract identity.
- Unimplemented extra obligations remain `unresolved`, with no invented
  evidence. They prevent closure and export even if encoding alone passes.

Each row contains `obligation`, `path`, `status`, `stage` and `evidence`. A path
locates the primary original occurrence; it is not an exhaustive list of all
semantic dependencies. Row order remains ascending by obligation ID.

The Python reader derives the nine mandatory fixed/instantiated obligations plus
one per original semantic definition. It requires exactly one original catalog
entry and rejects duplicate original definition IDs, mismatched selected catalog
identity, missing or duplicate mandatory IDs,
and a generic child that already claims the reserved expression/material
correspondence ID. The expression layer adds that ID exactly once. Genuine
additional generic obligations remain visible and unresolved. The native source
checker establishes their semantic origin; Python checks retained consistency.

Reject old or mixed report/checker/service versions. Do not provide an automatic
converter or relabel saved evidence. A retained original project may be freshly
compiled and exported to a separate package. Reopening an old package still
performs fresh checking and rejects its old manifest; the original bytes remain
intact. Successful new export preserves exact RNA while changing the report and
its dependent manifest identity.

## Implementation and validation status

The decision is implemented in `codex/m1-obligation-dispositions`. Independent
native literal-ledger regressions first rejected the unchanged v0.1 behavior;
the corrected build and focused native suites then passed. All 61 focused SDK,
project and CAR campaign tests passed on Python 3.11.15 and 3.14.6. The
[roadmap feedback record](../architecture-refactoring-roadmap.md#m1-local-feedback-and-pending-gates)
retains exact receipt identities and the content-bound working-tree scope.
Actual native legacy-package/reopen, mixed-version capability rejection and CAR
compile/export/reopen probes also passed locally, as did both typing configurations,
material/public-API coverage, workflow lineage, core boundaries, complete static
source preflight and the assembled documentation governance/inventory checks.
Hosted integration/installed checks and fresh actual-main acceptance remain
pending. Local evidence does not establish
a committed M1 revision, release acceptance or closure of the separate M2 gap.

## Acceptance and limits

Use independent literal success and failure ledgers, source-order changes,
original-authority mutations, coherent report rehashing, omitted/duplicate IDs,
unknown obligations, version mismatches and frozen legacy packages. Keep native
checks, SDK transport tests and the installed campaign oracle independent of the
production disposition table. Preserve all resource limits and charge new native
source-path lookup work. Required source-bound hosted and actual-main gates
remain in force; local feedback does not replace them.

This correction adds neither runtime behavior nor empirical or human-use
acceptance. A separately reproduced formal-parameter admission gap belongs to
M2; it is not repaired or blessed by M1. The complete original source and
assumptions remain retained, and no successful report establishes physical
expression, delivery or therapeutic benefit.

See the [profile contract](../car-expression-material-profile-design.md),
[roadmap](../architecture-refactoring-roadmap.md),
[capability matrix](../capability-matrix.md) and
[validation protocol](../development-validation.md).

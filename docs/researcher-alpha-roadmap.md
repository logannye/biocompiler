# Researcher alpha: active implementation roadmap

User-approved 2026-10-07. This is the active delivery plan for a lab-free,
researcher-facing workflow over explicitly supplied mRNA implementation contracts.
It complements the semantic compiler plan; it does not close its wider profiles.

## Outcome and scope

A researcher can use documented public Python interfaces to load or author a
versioned project, inspect its input scope, compile with Core, independently
verify with Verify, export exact RNA and its complete manifest, and reproduce
verification from independently retained original inputs outside the repository.
Unsupported meaning and incomplete material must remain visible and prevent
accepted payload export. Structural preflight is not native semantic acceptance.

The first engineering case reuses a complete, explicitly artificial supplied
contract. It tests the public workflow without claiming that its sequence
physically realizes staged behavior. Public research assets are qualified
separately; incomplete CDS references cannot become complete mRNA by filling
unknown regions or assuming a controller. A real research case requires complete
inputs, honest implementation premises, usable source terms and researcher review.

## Delivery checklist

| ID | Work | Exit condition | Status |
| --- | --- | --- | --- |
| RA-01 | Qualify reference assets and select a complete project | Frozen input/provenance packet, independently declared expected outputs, explicit supported and unresolved requirements | Engineering corpus complete; reviewed public candidates do not yet qualify a useful real research project |
| RA-02 | Public immutable project and component-input interfaces | Complete caller authority preserved; documented builders/loaders; no fixture tools or manual hashes required in the user flow | Implemented for complete existing component-material/selection requests; broader input builders remain open |
| RA-03 | Public compile, Verify export and project-authorized reproduction | Source-tree and installed outside-checkout positive/negative/second-case witnesses; independent Verify required | Implemented with 20-observation hosted witnesses; native validation pending |
| RA-04 | Integrate and distribute an accepted installation bundle | Exact-revision required gates, normal integration, fresh actual-main gate, matching SDK/native artifacts and tested installation instructions | Installed gates and candidate starter assembly implemented; accepted release pending |
| RA-05 | Reproducible research handoff | Exact FASTA/manifest, original project, scope summary, tested rerun instructions and review packet | Quickstart and review packet prepared; hosted verified handoff pending; external review deferred to the project owner |

Additional acceptance tasks:

- [x] Freeze an independent expected-output packet and a second input in the same
  supported family before the producer workflow is exercised.
- [ ] Retain incomplete-reference and unsupported-profile controls; reject stale
  original projects, changed candidates and altered exports even with rehashed
  outer metadata.
- [x] Preserve bounded parsing, literal JSON kinds, immutable snapshots, distinct
  Core/Verify roles, execution guards and atomic publication.
- [x] Update source ownership, public API coverage and historical source-closure
  registrations without transferring or weakening previous authority.
- [ ] Run focused pure-Python checks on both supported Python versions, then one
  coherent hosted development batch and an independent inert artifact audit.
- [ ] Exercise installation and the user example outside the source checkout.
- [x] Prepare the independent researcher review packet.
- [ ] Record the verified software rehearsal and complete reproducible handoff.
  An agent rehearsal is software evidence, not an external researcher review.

## Working order and ownership

Implementation is isolated in `work/researcher-alpha`, branch
`codex/dev-policy/researcher-alpha`, initially based on `e47476934`. Preserve the
frozen staged source `9eb3d7bd` and performance evidence at `fdb65bd3`; neither is
acceptance of this new source. Release PR85 and other active worktrees retain
their owners. Integrate current main deliberately after refreshing its identity.

First qualify assets and agree on the public project schema. Implement the API,
independent corpus and registration controls in parallel. Add the documented
outside-checkout workflow, then validate a coherent batch. Resolve release
integration and packaging using existing gates and bounded hosted builds.

No local OCaml/Rust compilation, native execution or native packaging. Keep
local checks pure/static and preserve exact source, run, attempt and artifact
provenance. Follow [development validation](development-validation.md).

The project owner will recruit the independent researcher reviewer, confirmed
2026-10-07, and explicitly deferred that work from the development critical path.
No software implementation, integration or handoff milestone depends on third
party participation. Continue all independently achievable work; record external
review separately when it actually occurs. Local or hosted agent rehearsals
cannot be described as independent researcher feedback.

## Completion boundaries

Track implementation, local tests, hosted development, installed use, release,
actual-main acceptance and researcher review separately. A passing software
reference does not close real-project qualification. A public sequence does not
supply a dynamic realization contract. No biological efficacy, delivery,
manufacturing or general staged-mechanism claim follows from this roadmap.

The qualification record is [reference qualification](researcher-alpha-reference-qualification.md).
The public workflow is documented in the [quickstart](researcher-alpha-quickstart.md);
the [review packet](researcher-alpha-review.md) records the independent usability
tasks and still-unfilled review fields. Native nonacceptance is exposed through
`ResearchProjectRejected` with its complete immutable assessment, rather than
discarding unsupported requirements behind a generic error.
Hosted validation receipts and exact checkpoints are retained under the owning
worktree's ignored `generated/researcher-alpha/` directory as they become available.

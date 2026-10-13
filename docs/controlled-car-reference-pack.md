# Controlled CAR two-RNA reference preparation

The `car197206-rna-v1` reference now supplies one complete nominal two-RNA
design and an explicit controller/readout contract to the existing controlled
`ResearchProject` route. Preparation is complete; fresh hosted Core/Verify
acceptance and the researcher-facing release remain open. The intended use
remains human immune cells engineered in vivo. No experimental result for the
new RNA adaptation is asserted.

The [hosted-validation batch](controlled-car-hosted-validation.md) freezes a
curated complete input at `data/car_controlled_reference/project.json` and
introduces contract version 2's explicit nominal translation premise. The local
checkpoint below records the preceding version 1 preparation; its identity is
historical and does not transfer to the revised original.

## What the pack contains

| Input | Authority and scope |
| --- | --- |
| Exact #197 and #206 products | Patent coding fragments, tags and linkers retained without optimization; 504 and 593 amino acids |
| Complete RNA designs | 1,830 and 2,097 nucleotides, including attributed whole UTRs, one designer-supplied stop and an encoded 110-A tail |
| Nominal chemistry | Explicit designer-adopted cap and modification inventory, plus declared 3′ hydroxyl; no manufactured batch properties |
| Controller | AP21967, identified by joining the patent's catalog number to the manufacturer's catalog |
| Readout | Assumed ordinal receptor/signaling activity, with background and active bands; no cytotoxicity conversion |
| Behavior | Separate requested deadlines and actual delays, six source requirements, a finite two-history domain and supplied software observations |
| Evidence context | Thirteen exact source records, ten explicit assumptions and unassessed empirical claims |

The [material qualification](controlled-car-rna-adaptation-qualification.md)
records source coordinates, independent expected identities and the distinction
between published coding fragments and the new complete transcripts. The
[controller/readout contract](controlled-car-controller-readout-contract.md)
records the public-source join and every uncalibrated scenario parameter.
Both remain original authority in the serialized project. The complete design
is not represented as a previously published two-mRNA experiment.

## Offline reproduction

Use an existing supported Python 3.11 or 3.14 environment. This command performs
bounded source reads, arithmetic checks and typed preparation only. It does not
build or execute native binaries, install packages, download inputs or compile
an accepted payload.

```sh
PYTHONPATH=src python3 -B -m tools.prepare_controlled_car_reference \
  --inputs /path/to/reference-acquisition \
  --original-xml /path/to/23-1871-WO_SequenceListing.xml \
  --reference-pdf /path/to/WO2025096878A9.pdf \
  --controller-catalog /path/to/heteroCitations_FL_633289_0212_IN.pdf \
  --design car197206-rna-v1 \
  --output /path/to/new-controlled-car-project.json
```

The acquisition directory must retain the four original fragment-import inputs
listed in [the acquisition record](car-controlled-reference-acquisition.md),
plus `wu-linked-patent-WO2014127261A1.html` and `wu-2015-pmc.html`. The exact
original XML, newer patent PDF and manufacturer catalog are separate required
inputs. Their locators and hashes are recorded in the material and contract
metadata. A later webpage revision is not interchangeable with the retained
original bytes. No public originals or generated sequence-bearing project are
added to version control by this batch.

The output path must not exist. The command writes one canonical project JSON
atomically and prints a separate preparation receipt. The source inspector
compares every supplied original with the project's current source records.
Its `source_bytes_matched` status establishes byte identity, while
`structurally_ready` establishes inert SDK preparation. Neither is native
acceptance or independent-person review of manual transcription.

The preparation tool reuses the existing fragment reconstruction and RM_61461
original-XML checker. It compares the resulting design with independently
prepared whole-RNA, protein and region hashes, preserves exact product pins,
and binds typed source declarations to the versioned controller/readout
contract. It does not introduce a second compiler or silently infer behavior
from sequence identity.

## This batch's local checkpoint

The owned checkout is `work/public-reference-readiness` on
`codex/public-reference-readiness`, continuing commit
`5452536e671a0b5a5210246896a68ee06ead63ce`. Other active worktrees and their
hosted runs are preserved. Generated local artifacts are retained under
`generated/public-reference-readiness/`:

| Artifact | Identity or result |
| --- | --- |
| `controlled-car-project.json` | 137,399 bytes; SHA-256 `a683620ad5c1ab48d2dc797c2e854e5e80362c1ef7e115585d7a1b040c37a2dc` |
| `controlled-car-preparation.json` | Thirteen matched sources totaling 34,656,879 bytes; native not run; empirical status unassessed |
| `controlled-car-project-py314.json` | Independent preparation invocation on Python 3.14; byte comparison recorded in the validation receipt |
| `controller-contract-audit.json` | Independent static review of final source bindings, assumptions and controller/readout correspondence |
| `controlled-car-independent-audit.json` | Independent arithmetic review of final material against the original sources and frozen expected metadata |
| `second-batch-validation.json` | Source/artifact hashes, local check outcomes and exact validation boundary |

The focused 83-test suite passed on preinstalled macOS aarch64 CPython 3.11.15
and 3.14.3. It covers fragment import, new preparation and workflow guards,
existing controlled material/workflow/project paths, RM_61461 reference checks
and source inspection. The new adversarial cases reject altered originals,
unchanged-protein/changed-UTR designs, region/frame/translation mutations,
chemistry changes and controller/readout relabeling. These are software checks;
they neither run native acceptance nor assess biological performance.

Source-context, material-rule and public-API inventories, the wire-schema
comparison and the migration-inventory check also passed. The regenerated
migration ledger retains the same 4,555 semantic entries; only static test
references changed to account for the two new test files. Both independent
reviews reported no findings in their stated scopes, and the Python 3.11/3.14
project outputs are byte-identical.

## Next hosted and release gates

1. Reconcile with the controlled-workflow owner's accepted revision, preserving
   both work streams. Any changed original invalidates the affected preparation
   and validation receipts.
2. Run the complete prepared project through fresh matching hosted Core and
   Verify binaries. Preserve exact revision/platform/binary/source identities,
   paired RNA export and fresh Verify-only reopen with complete independent
   originals. Do not substitute this batch's preflight for admission.
3. Extend the real-project campaign with independent RNA/protein/member dropout
   and encounter reset/end cases. The present two-history scenario exercises
   controller withdrawal and combined antigen/member loss; it is not exhaustive
   lifecycle coverage. CD8 subtype is a retained premise; native admission
   checks the human immune T-cell lineage, not a measured CD8 phenotype.
4. Build the narrow researcher facade, usable starter/acquisition route and
   source-edit demonstrations. Freeze the integration candidate for the complete
   installed, cross-platform and actual-main gates described by the
   [release roadmap](public-data-release-roadmap.md).

Milestone 5 remains the software release target. Public-data qualification,
including stronger independent source-reading review, continues alongside it.
Wet-lab validation is deferred; delivery, expression, localization, kinetics,
controller response and therapeutic effects of this adaptation remain unassessed.

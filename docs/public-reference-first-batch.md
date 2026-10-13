# Public-reference first implementation batch

Completed local checkpoint, 2026-10-12. This batch begins the
[Milestone 5 release plan](public-data-release-roadmap.md); it does not complete
that milestone or a complete molecular implementation.

## Delivered

- A versioned use-case/support record and authoring-facade specification in the
  release plan. Controller binding and observation interpretation remain open.
- A [public qualification inventory](../data/public_reference_programs/qualification-plan.json)
  prioritizing existing complete RNA references, the selected controlled pair,
  separate mechanism evidence and a targeted study-to-construct identity join.
- The bounded [offline importer](../tools/import_controlled_car_reference.py)
  for the four already recorded original inputs. It performs fresh byte,
  transcription, listing, translation, domain-order and junction checks and
  publishes only an inert metadata receipt, atomically and without overwrite.
- Nine [focused tests](../tests/test_controlled_car_reference_import.py),
  including tampered originals, malformed/colliding records, synonymous changes,
  omitted junctions, added stops, wrong proteins, symlinks/FIFOs, resource bounds
  and failed-publication cleanup. All molecular test fixtures are artificial.

The existing source inventory's import status and acquisition instructions are
updated. The generic source-readiness system, policy semantics, SDK exports and
native capability paths are unchanged. Regenerating the migration inventory
adds the new test file and updates indexed test-reference sets; all 4,555 entry
identities and all entry fields outside test coverage are unchanged.

## Validation and retained evidence

Local environment: Python **3.14.6**, macOS **Darwin 25.2.0, arm64**. The nine
focused tests passed; independent code review found no blocking code issue.
Migration inventory consistency and whitespace checks passed. No native
compilation, executable native tests, extension rebuilds, installation or
packaging was performed.

Fresh real-input replay read four existing files (14,625,734 bytes) from the
active checkout's retained acquisition directory without writing there. It
verified all 16 domains and reconstructed the source fragments:

| Construct | Coding fragment | Product | Termination |
| --- | ---: | ---: | --- |
| #197 | 1,512 nt | 504 aa | Not supplied |
| #206 | 1,779 nt | 593 aa | Not supplied |

The replay receipt is retained locally as
`generated/public-reference-readiness/fragment-import-final.json` (8,779 bytes).
Its identities are:

| Object | SHA-256 |
| --- | --- |
| Importer source | `c6003a6c3db89cae835ae41d87fe158d33fa2b7b020a337b885c7dace5655441` |
| Source inventory | `cea2032bf3e101624191fe2f7676b0703e0b13e2b55b66177f7229c17a683950` |
| Fresh receipt | `c9676d2df99ddb7405b429e05fd8471164569e0c2e58b735e62d11966e6d9c8f` |

Reproduction commands are in the
[acquisition record](car-controlled-reference-acquisition.md). The receipt
pins its original inputs and current tool; it is not reusable acceptance for
changed bytes. Visual transcription remains a trusted, same-operator acquisition
step. This batch supplies neither independent-person transcription review nor
new biological measurements, complete RNAs, native admission or release evidence.

## Preservation and next handoff

All edits are in the owned `codex/public-reference-readiness` worktree at
`Biocompiler 2.0/work/public-reference-readiness`, based on
`17a7352b5e6ed1d087c110bedb365132280152c7`. Existing controlled-CAR, first-MVP,
second-reference and typed-kernel worktrees retain their owners. No other
checkout was edited, no CI was dispatched or canceled, and no historical PASS
was transferred. The original sequence-bearing assets were read in place;
no new bulk acquisition or asset redistribution occurred.

Next implement the real molecular pack only after its independent source/design
authority and contract are complete: exact controller/readout binding, all
transcript regions, termination, chemistry, expected products, deployment and
availability. Reuse the existing RC6 workflow and implement the facade against
that pack. Reconcile the owner's current RC6 and E1 state before integration.
Hosted development, cross-platform/installed acceptance, fresh actual-main
validation, usability and release publication remain future gates.

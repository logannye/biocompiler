# Researcher alpha review packet

Status: review instructions prepared; no external researcher review has occurred.
Use the [quickstart](researcher-alpha-quickstart.md), the independently declared
`expected.json`, complete original inputs and the exact hosted installation
receipts. Record candidate-package testing separately from release acceptance.

## Independent usability walkthrough

The reviewer should work from a new directory outside the source checkout with
the supplied installed wheels and standalone example. Do not provide private
fixture generators or undocumented environment setup to complete the exercise.

1. Record the SDK/native wheel names and hashes, source revision, hosted run,
   operating system and Python version. Confirm these match the handoff.
2. Follow the quickstart to prepare and inspect the staged project. Explain what
   structural preflight establishes and which checks have not run.
3. Compile the project, inspect the paired FASTA/manifest and independently
   verify it from the retained original project. Compare the exact RNA and
   coordinates with the separate expected values.
4. Repeat with the comparison project. Confirm that the output changes as
   specified and that the staged output cannot substitute for it.
5. Review the negative-control receipts. Identify the rejection boundary for
   altered candidate material, altered FASTA, stale originals, insufficient
   machine capacity and completion without required feedback.
6. Explain the strongest supported claim in the manifest, its finite scope and
   the supplied contracts on which it depends. Identify the unresolved physical
   realization and empirical questions.
7. Describe a useful research task that this supported profile could serve,
   the exact inputs the reviewer already has, and the missing inputs or language
   features that prevent using it. Do not replace missing contracts with the
   artificial examples' declarations.

## Review record

Complete these fields after the walkthrough; blank fields are unresolved work.

| Field | Reviewer response |
| --- | --- |
| Reviewer and relevant research role | |
| Review date; package/source/run identity | |
| Platform and Python version | |
| Project and verified bundle hashes | |
| Time to first independently verified output | |
| Steps completed without maintainer help | |
| Setup failures and unclear diagnostics | |
| Explanation of conditional acceptance and unsupported scope | |
| Useful research task and missing prerequisites | |
| Must-fix issues before that task can proceed | |
| Decision: useful now / needs specific fixes / unsuitable | |

A maintainer or agent rehearsal can exercise the software, but does not populate
this record as an external researcher's assessment. No wet-lab result is needed
for this usability review.

## Qualifying the first real project

Request a complete specification through an authorized collaboration, or select
a public source whose contents can be independently inspected and reused. Freeze:

- The original intended behavior, required and prohibited outcomes, explicit
  target/context, finite observation domain and operational assumptions.
- The full delivered RNA design and every region, coordinate, coding sequence,
  chemistry annotation and supplied implementation/provider contract required
  by the selected supported profile.
- Source identities, exact retained bytes, versions and reuse terms; document
  inaccessible or missing data explicitly.
- Expected results specified independently of the compiler, including a second
  project or meaningful input change and the required rejection outcomes.

Qualify support by submitting the complete original project through the public
workflow. A rejected or unsupported assessment is useful feedback, but does not
authorize a payload. A correct translation under supplied premises does not
establish that those premises hold in a human immune cell. Track biological
validation separately when collaborators later supply it.

# Circuit source metadata and gap inventories

This is a **partial R1 implementation** of the
[RNA-circuit plan](rna-circuit-reproduction-plan.md). It provides bounded offline
metadata contracts and independent consistency checks. It does not supply the
reviewed publication corpus, source-format extraction, complete molecule
expectations or measured observations required to finish R1.

## Authority and claims

A source document has two distinct identities: its complete metadata fingerprint
and, when declared available, its retained-byte receipt. A DOI, URL, title or
metadata hash cannot substitute for a source-file hash. A declared receipt is
also not proof that the file is available or that its contents were interpreted
correctly. Inventory checking does not retrieve or execute source files.

Each case has a fixed coverage ledger for construct inventory, input states,
molecule inventory, controls, transcript boundaries, chemistry, component
authority, independent final-molecule authority and observations. Every field
must be present. `not_reviewed`, `not_reported`, `unavailable`, `ambiguous` and
`conflicting` preserve the reason that authority is missing. `provided` records
only declared record availability with content pins and locators; it cannot
establish molecular completeness, independent experimental replication or
therapeutic applicability.

Human experimental context is optional while a source is being inventoried.
Absent context is explicitly unknown, never filled with an invented cell line,
delivery mode or assay. Supplied context retains R0's human-only contract and
must bind its source citations to the inventory's declared byte receipts.
Human immune/nonimmune and in-vitro/in-vivo contexts remain distinct.

Reviews bind the exact source or case metadata fingerprint. They identify the
reviewer as a human or software agent, describe the method and retain findings.
Their disposition is `metadata_review_only`; a review record cannot attest
biological function. Editing a reviewed record makes that review stale. Previous
inventory identity and a change reason record an explicit version transition;
the checker does not claim to authenticate an unavailable previous inventory.

## Checking and replay

`check_circuit_sources(inventory)` checks metadata relationships and reports
per-case unresolved coverage. A metadata consistency PASS can coexist with every
scientific field unresolved. Inconsistent source IDs, source pins or review
subjects return FAIL diagnostics. Molecular readiness stays `unassessed`, source
bytes remain unchecked, empirical support stays unknown and human use is not
admitted.

`verify_circuit_sources(assessment, expected_inventory=inventory)` requires the
complete separately retained inventory and reconstructs the assessment with the
current checker. A saved PASS or a hash copied from it cannot supply authority.
Changing metadata, cases, coverage, reviews or policy invalidates saved results.
Historical inspection and fresh replay remain distinct operations.

## Outstanding R1 work

The Python example and CLI expose the same checked metadata path:

```sh
python examples/circuit_sources.py --output generated/circuit-sources
biocompiler circuit-sources-check --inventory generated/circuit-sources/inventory.json --output generated/circuit-sources/assessment.json
biocompiler circuit-sources-verify generated/circuit-sources/assessment.json --expected-inventory generated/circuit-sources/inventory.json
biocompiler inspect generated/circuit-sources/assessment.json
```

CLI exit 0 means consistent metadata, exit 1 means inconsistent relationships,
and exit 2 means invalid input or mismatched replay authority. The CLI protects
its input inventory from report overwrite. JSON inspection is historical and
never executes supplied code. Author-record metadata can omit a public URL;
no imaginary public link is required for a local record.

Imports enforce fixed fields, versions, enums, finite JSON and content pins.
Metadata has a 4 MB UTF-8 budget including a publication newline, depth 64,
100,000 tree items, 128 sources, 256 cases and 256 reviews. Each case preserves
the fixed nine-field coverage ledger. Source retrieval, sequence interpretation
and biological inference are outside this partial checker.
Assessment JSON has a separate 12 MB budget. Diagnostics are bounded to 4,096
entries of 512 UTF-8 bytes; long IDs use stable metadata references. If more
inconsistencies occur, an explicit omitted-occurrence marker retains FAIL and
the complete original inventory remains available for inspection. Exceeding a
serialization budget fails closed; it never publishes a truncated passing record.

The family identifiers are the scope established in R0, not admitted references.
The example uses non-biological software fixtures and supplies no published case.
R1 still requires the actual human construct/variant inventory, licensed source
retention, reviewed import adapters, independently reconciled component and final
molecule authority, source-linked observations and precise case-specific gaps.
No current fixture may be promoted to satisfy those acceptance gates.

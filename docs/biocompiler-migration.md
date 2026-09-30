# Rename to biocompiler

Version `0.1.0.dev11` renames the project, distribution, Python package, command,
repository and artifact namespace to **biocompiler**. This is an intentional
development-version compatibility break.

Use `import biocompiler as bc`, the `biocompiler` command and
`https://github.com/logannye/biocompiler`. The public base exception is
`BiocompilerError`. The reference-build archive suffix in documentation and
examples is `.bcb` (biocompiler build). Archive contents and schemas determine
validity; changing a filename does not migrate a package.

All current compiler schema and tool identifiers use `biocompiler.*`. Historical
artifacts from the former CellWeave namespace are rejected. There is no parser
alias, automatic JSON replacement or forwarding package that can carry an old
PASS label into the renamed namespace. Re-author/reload the independently trusted
inputs, rebuild with the current version, retain the new identities and rerun
the appropriate checkers. Consumer code must update imports, exception names,
command invocations and artifact paths.

The retained FAP reference manifest changed **only** its top-level schema marker
from `cellweave.reference.v0.1` to `biocompiler.reference.v0.1`. Its new canonical
manifest fingerprint is
`e6bd93305ccf638757844d744c9ce9f8d84bbea4cfed40ba4cb224f28e610102`.
The former manifest fingerprint was
`8d26e8d3e960d8dc0996e1f0582372ddfc9685795ed54131557f101be8849a41`.
The independently pinned DNA, RNA and protein records, sequence hashes, retained
source bytes, source hashes, source-review records and evidence limitations are
unchanged. The checked-in manifest expectation and consuming examples/tests were
updated after comparing the manifests with this single permitted difference;
the expectation is not computed from an emitted candidate at runtime.

This mechanical namespace migration does not constitute a new biological review
or promote the murine reference for human therapeutic use. Historical roadmap
validation records refer to their original revisions and namespaces. Updating
their GitHub links to the renamed repository does not change what those runs
tested. Current namespace/package validation is recorded with M10.4.

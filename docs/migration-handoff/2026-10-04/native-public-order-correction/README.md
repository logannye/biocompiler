# Native public mapping order correction

PR85 run `37169286045`, source `2cf35b440ce9fca6dc951709b27f8122f00b81f7`,
failed the installed `pipeline-fixed-continuations` campaign on both macOS
Python versions. The fresh original Python graph had already matched its frozen
reference. The subsequent native public graph comparison failed in all four
fixture setups. No merge was accepted from this run.

Offline structural reconstruction of the retained macOS 3.14 frames isolated
11 mapping insertion-order patterns. It covered all four failed cases and
preserved physical alias correspondence. Matching mapping keys for diagnosis
left no other value, type, field or alias differences. This diagnostic alignment
does not satisfy the original ordered comparison; that assertion and its frozen
corpus remain unchanged.

The correction emits the original public field order for candidates, signals,
intent and behavior nodes, behavior requirements, targets, ports and check
results. Native settings updates preserve an existing key's position and append
new keys in the original update order. Canonical object content and fingerprints
remain separate from the observable insertion order. The analogous verification
settings update uses the same ordered replacement rule.

The installed graph assertion also gains a bounded first-difference diagnostic
on failure. Successful comparisons retain their existing path and receipt
schema. A finite reversible source witness preserves the historical checker
authority instead of replacing its pin.

Retained evidence is under
`generated/migration-next/resumed-pr85-2cf35b4/failure-37169286045/`.
The complete macOS artifact is SHA256
`e91f7859b6beb20b4d9c7bdd7c8bf004845dae32d23f74cfd7f261e74c37b981`;
the diagnostic packet manifest is
`10578eea3d186d195d178e965decc2b4979a8e655c66fab7205ea84271711441`.
The original graph corpus remains SHA256
`b423e1d60fbe688090bd44787ccb372a10847681cd8a011fd897cface9b9e28e`.

Local work is limited to source review, static checks and pure Python controls.
Nine focused checks passed on Python 3.11.15 and 3.14.6, including seven new
diagnostic/source-restoration controls and the two affected existing source
checks. The dependency-boundary check and refreshed 3,310-entry migration
inventory check passed. Eight native regression blocks were appended to
existing suites, preserving every original test byte and all 118 suites.
Native regressions and the unchanged complete installed campaigns require
fresh hosted validation of the final corrected revision on both platforms.
No old success or offline diagnostic establishes that validation.

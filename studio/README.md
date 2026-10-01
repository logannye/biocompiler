# Studio TypeScript

The two existing browser clients are strict TypeScript modules. Their public
URLs, pages, controls and service semantics remain unchanged. The guided client
still uses the explicitly partial candidate profile; the architecture editor is
a separate roadmap increment.

```sh
npm --prefix studio ci --ignore-scripts
npm --prefix studio run typecheck
npm --prefix studio run build
npm --prefix studio run check:assets
npm --prefix studio test
```

Transport fixtures use the installed Python package by default and assert that
its import is outside `src`. For explicitly local source-only checks, use
`STUDIO_TEST_SOURCE=1 npm --prefix studio test`; this cannot satisfy the installed
package gate. The repository root is exposed only for fixture example modules.

TypeScript is pinned in the lockfile. No bundler, framework, native extension or
runtime npm dependency is required. A matching already-installed `tsc` can run
the typecheck/build without installing packages. Build output is bounded, uses
a temporary directory, and is removed after comparison/publication.

`src/transport.ts` declares and checks only HTTP response shapes used for display.
Unknown artifact payloads remain opaque. `AuthorityText` marks original UTF-8
JSON strings, never browser reserialization. `Fingerprint` is an identity label,
not evidence that the browser has checked a digest or semantic claim. Server
verification still owns all acceptance and export decisions. No client PASS,
schema shape or TypeScript type can authorize compilation or delivery.

The checked-in files under `src/biocompiler/studio/static/` are published release
counterparts, a narrow exception to the rule against generated scratch artifacts.
They keep source installations and existing wheels usable without Node. Edit
`studio/src/*.ts`, never their generated JavaScript. `check:assets` recompiles
with the pinned compiler and rejects any byte mismatch, including the complete
source/config/lock input manifest. CI must run it **before** any build command
that might repair drift, and before package installation. The installed-package
test checks the manifest against every shipped JavaScript file.

The explicit server allowlist serves `/transport.js`; module imports stay local
under the existing CSP. HTML uses `type="module"`, with no inline scripts.
Existing browser acceptance in `tests/browser/studio.cjs` and
`tests/browser/construction.cjs` remains authoritative for UI parity, including
late replies, input revisions, lossless construction saves, hostile text,
keyboard access and the current partial-profile labels. The transport unit tests
supplement those browser checks with malformed response and raw-byte cases.

# OCaml core

This is the first native migration increment. It implements bounded strict JSON,
legacy Python-compatible canonical fingerprints and structural intent/type/literal
validation. It does not yet implement compilation, behavioral execution,
molecular verification, export acceptance or human-use admission. Capabilities
are explicit; unimplemented operations return `unsupported` without fallback.

The protocol is one UTF-8 request on stdin and one response on stdout. Both
executables use `biocompiler.core.v1` and identify their distinct executable role.
Nonzero exit codes accompany structured errors (2) and unsupported operations (3).
There is no Python semantic execution or runtime network request in either binary.

Libraries have explicit dependencies. `bioc_checker` only depends on immutable
domain/wire modules. `bioc_service` exposes that checker; the standalone verifier
has no dependency on a compiler, selector, matcher, assembler or emitter.
The shared JSON codec, canonicalizer, numeric conventions and domain validators
are part of the common trusted base, not independent execution evidence.

## Hosted validation

Native builds run on the approved hosted validation environment. Do not install a
local toolchain or run native builds as a side effect of Python checks.

With OCaml 5.4.0 and dependencies from `biocompiler_core.opam` installed:

```sh
opam exec -- dune build --root core @all
opam exec -- dune runtest --root core
```

Build outputs are `core/_build/default/bin/core/main.exe` and
`core/_build/default/bin/verify/main.exe`. Installed executable names are
`biocompiler-core` and `biocompiler-verify`. Direct dependency versions are pinned;
the hosted solve must retain its full transitive opam lock and platform/build
receipt before a release is considered reproducible.

The wire parser preserves integer/floating-point/Boolean distinctions and
arbitrary-precision integers within the advertised lexical limit. It rejects
duplicate keys, invalid UTF-8 or surrogate escapes, nonfinite numbers, excessive
depth, string length, item counts and bytes. JSON item accounting counts values,
not object keys; root depth is zero. This stricter UTF-8 wire profile is explicit.

Canonicalization follows existing Python JSON representation rather than RFC
8785: integers remain integers; floats use shortest round-trip decimal spelling,
signed floating zero is retained, keys sort by Unicode scalar order and output is
UTF-8. Float digit selection uses exact rational decimal rounding, followed by a
binary64 round-trip check and Python's fixed/scientific thresholds. Cross-language
fixtures must confirm byte and hash parity before production promotion.

Intent validation checks the current intent document schema, graph references,
acyclicity, role targets, names, dimensional types, bound parameters, intervals,
curves, source locations and registered unit conversions. Unknown operation names
remain descriptions just as in the existing `IntentProgram`; this operation does
not validate their behavioral meaning. A successful structural report never
becomes a translation certificate.

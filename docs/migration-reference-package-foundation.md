# Reference package and sequence export migration

This source checkpoint adds OCaml ownership of the reference manifest domains,
structural package container and sequence export primitives. Public package API
routing and release acceptance remain open. Python remains the production
default, and all four session cutoff gates remain open.

## Typed content and structural integrity

`bioc_reference_artifact` defines six closed immutable domains: reference build
request, run metadata, package file, accepted stage, tool pin and build manifest.
It preserves canonical fingerprints, portable source locations, ordered stage
identities, complete file roles and software-use labels. Run metadata remains
outside canonical build identity. An imported accepted-stage record describes
historical content; importing it does not establish current acceptance.

The typed container validates exact inventory, lengths and hashes, then compares
the complete archive against its deterministic reconstruction. Parsing never
extracts files, opens metadata paths or grants export authority. Its dependency
declaration gives it no producer or semantic checker API.

The original Python behavior is retained in 511 observations for each supported
Python minor version. Ten metadata outcomes differ between 3.11 and 3.14,
including midnight timestamps and Windows absolute-path parsing. The native
runtime profile preserves these differences explicitly. Python 3.14 recognizes
a single Unicode scalar as a drive prefix; Python 3.11 uses its older ASCII
drive rule. Canonical request source paths remain relative POSIX paths.

## Fidelity and current export acceptance

`bioc_reference_export` separates sequence serialization fidelity from fresh
export checking. The codec preserves exact FASTA escaping, line wrapping,
alphabet, software-use labels, JSON bytes and both artifact and file identities.
Its fidelity operation checks those encodings against the supplied typed
molecular artifact.

The export operation checks current software-use admission and independently
checks the supplied molecular artifact against the current request, construct,
registry and manifest authority before encoding it. Nested Construct and
Composition checks remain independent of producers. The complete original
140-case corpus contains an internally rehashed sequence change that passes
fidelity but fails fresh export acceptance. Both Python runtimes produce the
same complete sequence corpus bytes.

## Resources and validation

Every operation receives one existing archive resource scope. Parsing and
encoding preflight JSON size, nodes, depth and cycles; retained allocations
charge the caller cumulatively. Nested independent checks share its work
ancestor. Standalone export conservatively reserves the unchanged configured
Molecular, Construct and Composition report/item ceilings before execution.
Insufficient scopes fail; operations neither reset the owner's resources nor
lower checker limits to fit. The package profile has a 512 MiB retention ceiling.
Full package orchestration still needs allocation accounting across its repeated
checks; reserving every check's maximum would reject supported complete builds.

Both local Python versions pass 59 focused authority, dependency, CI and fixture
controls plus a separate Unicode-profile control. That control reconstructs the
runtime's complete decimal-digit ranges and compares both native tables to
their retained authority. Thirteen inventory controls pass on each version.
Both discover 3,240 tests in 317 classes; discovery is not execution.

Two new native suites require complete corpus hashes, runtime slots and unique
case inventories. They also exercise exact and one-short shared work/retention
bounds, sticky exhaustion, reduced depth and cyclic inputs. Hosted validation
requires 114 native suites on Linux x86_64 and macOS arm64 and retains the full
36-job release gate. No native compilation or execution ran locally.

See the [source checkpoint](../protocol/migration-reference-package-foundation-checkpoint.json).
Remaining work includes live package construction, trusted offline inputs,
independent package reconstruction, current export/publication authority, public
routing, complete installed replay and all hosted release gates.

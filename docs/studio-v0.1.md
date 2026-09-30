# Guided design workspace v0.1

The local browser workspace makes the [intent-candidate compiler](intent-candidate-v0.1.md)
usable without writing Python for the first example. It calls the same compiler
and independent validators as the Python API and CLI. It does not broaden their
supported biological scope.

## Start the workspace

After installing the package as described in the [README](../README.md):

```sh
biocompiler studio
```

The command opens your browser and prints its local address. Keep the terminal
running while using the workspace; press Ctrl+C there to stop it. If the default
port is occupied, use `biocompiler studio --port 0` to choose a free port.
`--no-open` prints the address without opening a browser.

From a source checkout, without installing:

```sh
PYTHONPATH=src python3 -m biocompiler studio
```

The server listens only on `127.0.0.1`. The interface, bundled example and compiler
run locally, with no external web resources or runtime dependencies. The workspace
is a local research tool, not a shared hosted service. Reloading starts a fresh
workspace; retain the downloads you want to keep.

## Your first design

1. Start with the guided example. Its request describes a human T cell that should
   secrete a declared product while an external cue is high. The short example
   parts and protein strings are artificial, nonfunctional software fixtures.
2. Choose the example product. This changes the requested product and its matching
   coding part. The cue, human target and complete behavior/deployment contracts
   remain in the source request.
3. Let the compiler choose the shortest eligible architecture, or require the
   compact or extended example architecture. An optional maximum length is a hard
   limit, not a target to optimize toward.
4. Compile and review the selected parts, sequence layout and exact RNA. The
   alternatives explain why each design was selected, left eligible or rejected.
   Expand the independent checks and unresolved requirements for more detail.
5. Download the source request, complete build record and verified FASTA. Keep the
   request separately: later verification needs the original authority. The build
   record retains molecular features and unresolved requirements that FASTA alone
   cannot express.

Try the other product to see a different coding sequence. Require the extended
architecture to see two extra bases at the 5′ end. Set the maximum length to one
nucleotide to see a correctly reported empty search: no sequence is emitted, and
the alternatives retain their rejection reasons. This means neither supplied
design fits that constraint; it is not a claim of biological impossibility.

## Reading the result

- **CDS (coding sequence):** the region whose nucleotide triplets specify the
  declared protein string. The displayed translation is a sequence check, not a
  measured protein or a prediction of therapeutic function.
- **5′ and 3′ UTRs (untranslated regions):** regions before and after the CDS in
  the selected RNA architecture. Their fixture labels establish no regulatory
  function.
- **Poly(A):** the explicitly supplied run of A bases at the end of this example.
- **Structural completion:** the chosen parts and exact bases match the retained
  request, layout and supported molecule profile.
- **Partial therapeutic implementation:** sensing, regulation, secretion, response
  rates, shutdown, delivery and biological evidence still require implementation
  or support. A structurally complete cassette does not fulfill those obligations.

Positions in the displayed molecule use one-based nucleotide numbering. The
underlying machine-readable ranges remain zero-based and half-open, as specified
by the molecular schemas. The JSON build record is the detailed authority for
chemistry, provenance, checks and identities.

## Use an existing request

Import a complete `CandidateRequest` JSON file created with the Python API or
downloaded from this workspace. Imports are validated before use and compiled as
authored. The imported source, library and constraints are read-only in this
version; edit them through the Python API and import the updated request. A build
record, bare FASTA or Python script is not a request file.

Imports are limited to 1 MiB; the encoded operation must fit within 2 MiB.
The browser retains request and build JSON as exact text during compilation and
export, so numeric values are not changed by JavaScript parsing. Read-only
constraints also use the server's exact JSON representation.

The interface never executes uploaded code. Imported strings are displayed as
text. Edits to the guided example invalidate the displayed result immediately;
compile again before downloading. A slow response from an earlier edit cannot
replace the current design. Downloads reverify the build against the complete
current request on the server, so saved PASS labels are not export authority.

## Implementation and validation

`biocompiler.studio.service` provides preparation, compilation and verified export;
`biocompiler.studio.server` serves the packaged interface over loopback HTTP. The
server restricts static paths, request size, host, origin, JSON format and session
token. It exposes no filesystem path or arbitrary execution API. Independent
compiler verification remains outside the presentation code.

The Python suite covers request semantics, export freshness and HTTP boundaries.
The hosted browser workflow installs the package, starts the CLI from outside the
repository, exercises the guided/import/error/download flows and checks responsive
layout. Existing package, source, example and reconstruction gates remain required.
No new human therapeutic admission or biological validation is claimed by the GUI.

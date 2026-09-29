# Independent exact-CDS molecular checking

`check_molecular(request, construct, candidate, registry, manifests)` independently
checks a DNA-CDS or RNA-CDS artifact against the frozen construct authority and
reviewed reference records. It does not import the sequence emitter or accept a
producer's success flag. A fresh construct check runs first, so updating molecular
identity fields cannot conceal changed component selection, coordinates or source
correspondence.

The input manifests are immutable snapshots loaded offline with
`load_reference_manifest(path, expected_fingerprint=trusted_hash)`. That loader
checks retained source and review bytes. The molecular checker validates current
manifest identities through the construct checker. These snapshots do not watch
the filesystem; changing local source files requires loading and checking a new
snapshot before reuse.

The initial profile requires exactly one record for the accepted whole-CDS
placement. Record and molecule IDs, component lock, trusted reference selection,
zero-based half-open ranges, forward orientation, frame zero, source location and
requirement IDs must match that placement. Alphabet, length, artifact class,
coding-only completeness, unknown features and evidence relationships must match
the independently selected reference. Sequence symbols are canonical uppercase
DNA or RNA without whitespace, repair or automatic alphabet conversion.

Four comparisons are reported separately in `MolecularResult.checks`:

| Comparison | Independent expectation |
| --- | --- |
| `canonical_hash` | SHA-256 computed from the emitted nucleotide symbols |
| `exact_reference` | Every nucleotide of the separately curated selected reference |
| `translation_reference` | Standard-code translation compared with the independently curated protein record, including its terminal stop |
| `dna_rna_correspondence` | The independently curated counterpart nucleotide record under the explicit T/U correspondence |

The exact-reference comparison reports the first differing zero-based nucleotide
or the first unexpected end. A synonymous substitution fails this comparison
even when translation passes. Missense changes, missing or extra bases, absent or
premature stops and changed start/frame conventions cannot preserve acceptance.
Translation uses the checker's reference translation implementation, independently
of the emitter. T/U correspondence is only a consistency check between frozen
reference spellings; it establishes no interchangeability of delivered modalities.

The versioned exact-CDS profile defines scoped known, unknown and inapplicable
feature declarations. The checker derives the required declarations from the
independently pinned reference. Delivered-molecule cap, nucleotide modifications,
UTRs, regulatory context, end boundaries and topology remain unknown. Their
inapplicability to an abstract CDS record does not mean they are absent from
experimental material. A domain diagram cannot establish subcomponent nucleotide
coordinates. Added feature coordinates or claims that delivered features are
known fail acceptance.

Reference reproduction fixes the encoding policy to disabled optimization and no
transformations. The schema can retain a future encoding change record, but any
such change remains unsupported by this acceptance profile. The fixed invalidation
policy covers construct, composition, molecular, structural, expression and
behavior analyses; a protein-preservation claim cannot preserve those analyses.

`MolecularResult` is immutable and strict to deserialize. It records the current
request, construct, layout, candidate, registry, registry lock, target, profile,
encoding policy, evidence policy, reference snapshots and checker versions.
`result.freshness(request, construct, candidate, registry, manifests)` reports
changed dependencies. The manifest and registry lock include the linked protein,
DNA and RNA record identities; comparison records additionally retain the exact
expected and observed sequence hashes. Imported results are historical reports
and never authorize a modified artifact or export.

Passing establishes the selected coding-reference spelling and the stated
comparisons. It establishes no complete delivered payload, expression behavior,
empirical function or efficacy.

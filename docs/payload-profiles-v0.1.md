# Complete-molecule readiness profiles v0.1

`check_payload` checks structural completeness of a supplied exact molecule against
a separately pinned `PayloadReference`. A passing result grants neither compiler
admission nor biological reference promotion. This is a new readiness gate; the
exact-reference Construct/Molecular pipelines still support exact CDS references
only. A separate [software molecular-design pipeline](molecular-design-v0.1.md)
now constructs multi-region RNA candidates from frozen fragment/layout authority;
it has a separate candidate checker and grants no biological reference promotion.
The original readiness and exact-reference contracts are unchanged.

The supported classes are deliberately narrow:

| Class | Sequence/topology | Exact contiguous source-mapped regions | Chemistry/end contract |
| --- | --- | --- | --- |
| `mature_linear_rna` | Single-stranded linear RNA | Nonempty 5′ UTR, one forward CDS, nonempty 3′ UTR, optionally an exact poly(A) region | Unmodified nucleotide alphabet, explicit cap (`none`, `cap0`, `cap1`), explicit 5′ terminal state, 3′ hydroxyl, exact tail length or explicit absence |
| `linear_dna` | Double-stranded linear DNA, one represented strand in 5′→3′ order | Nonempty promoter annotation, one forward CDS, nonempty terminator annotation | Unmodified complementary DNA, blunt ends, both strands explicitly have 5′ hydroxyls or phosphates and 3′ hydroxyls |
| `circular_plasmid` | Double-stranded circular DNA, one represented strand with an explicit source-defined coordinate origin | Nonempty promoter annotation, one forward CDS, nonempty terminator and backbone annotations | Unmodified complementary DNA, no free ends; cap, terminal chemistry and poly(A)-tail chemistry are inapplicable |

These region names denote reviewed sequence annotations. The checker does not
establish that a promoter, UTR, terminator, backbone or complete molecule has any
biological function. Circular DNA represents the standard exact complementary
strand; mismatched duplexes, strand-specific modifications, nicks and gaps have no
profile. Circular RNA, transcription templates as distinct conversion artifacts,
packaged vector genomes, reverse or additional coding regions, modified
nucleotides, overhangs and heterogeneous or merely nominal tails are unsupported.
There is no implicit RNA/DNA or template/mature-product conversion.

For capped RNA the 5′ state must be `capped`; uncapped RNA must explicitly specify
`hydroxyl`, `monophosphate` or `triphosphate`. Linear DNA terminal declarations use
`hydroxyl_both_strands` or `phosphate_both_strands` for 5′ ends and
`hydroxyl_both_strands` for 3′ ends. Every required feature has a source locator.
Unknown required chemistry or whole-molecule features yields UNKNOWN. A missing
feature inventory fails. No undocumented chemistry is inferred from A/C/G/T/U.
Here `nucleotide_modifications="none"` means no additional modifications beyond
the separately specified canonical cap chemistry; cap0/cap1 are explicit
chemistry primitives of this profile. Modified internal bases and alternative
cap analogs require a different reviewed profile.

## Authority and independent checks

```python
result = check_payload(
    candidate,
    reference,
    expected_reference_fingerprint=trusted_pin,
    retained_sources=source_bytes_by_id,
)
```

`trusted_pin` must be supplied from a separate review or configuration channel,
not accepted from candidate output. The caller supplies retained bytes, so checking
performs no network access, source-path traversal, authoring execution or file
discovery. A candidate-supplied hash does not establish identity: the checker
compares its entire frozen molecule with the authority, recomputes the sequence
hash, and separately normalizes the retained extraction with the existing narrow
ASCII whitespace/uppercase policy. Each retained primary, extraction and review
source must match its independently pinned hash; extra and missing files fail.

All normalized sequence positions must be covered exactly once by ordered,
nonempty coding/noncoding regions. The molecule boundaries are exactly
`[0, len(sequence))`. Region coordinates use the shared zero-based, half-open,
5′→3′ convention and must match the independent whole-molecule extraction.
Orientation, frame, alphabet, topology, chemistry, source locators and every
unknown-feature declaration participate in exact identity. Each CDS is translated
under the standard code, with one terminal stop retained, and compared with an
independently supplied protein spelling. Translation equality cannot excuse a
synonymous nucleotide change or changed noncoding base.

The primary source's relationship to the extracted sequence and annotations is
an externally reviewed assertion, not a claim that this software can independently
interpret arbitrary papers or patent PDFs. Two retained JSON declarations must
name distinct extraction and independent-review identities, accept the exact
expected molecule and primary/extraction source hashes, and retain the source kind.
`REVIEW_SCHEMA_VERSION` and the example define the strict declaration fields.
This validates the consistency of review declarations; it does not authenticate
human identities or establish that a review actually took place. Those are duties
of external curation and the trusted pin channel.

## Evidence boundary and promotion

`source_kind="software_fixture"` explicitly labels invented control data.
`source_kind="externally_reviewed"` labels a supplied review assertion; it is not
an accepted-reference flag. Both can receive a structural-readiness PASS, and
both always retain `reference_promotion="not_promoted"` and
`compiler_admission=False`. The accepted biological full-payload pin set is
currently empty. No fixture in this implementation changes that set.

Real reference promotion still requires independently verified retained source
material, actual complete molecule boundaries and chemistry, resolved relevant
discrepancies, context/evidence linkage, redistribution review and a separate
curated acceptance change. The FAP coding references cannot be upgraded by
renaming their class or appending guessed UTRs, cap, tail or regulatory sequences.
No biological model, expression, experimental-material identity, therapeutic or
clinical outcome follows from readiness. These unestablished claims are immutable
in the molecule schema and result claim scope.

Receipts bind candidate, reference, caller authority pin, every retained byte
identity, profile, schema and checker version. Any sequence, layout, source,
chemistry or authority edit makes an old receipt stale. Imported results are
inspection artifacts and cannot grant admission. The strict v0.1 importer rejects
receipts with another checker/profile/schema version; recheck original inputs
under the current implementation.

## Executable controls

`PYTHONPATH=src python examples/payload_readiness.py --output DIRECTORY` checks
three nonfunctional, explicitly invented software fixtures, saves their frozen
expectations and retained source declarations, and rejects a changed noncoding
base against the original authority for each modality. Test fixtures also cover
synonymous changes, substituted authority, modified sources/reviews, missing or
overlapping regions, wrong topology, incomplete/unknown chemistry, nominal tails,
unsupported artifact classes, source coordinates, freshness and strict import.
The checker imports neither an emitter nor a reference-promotion factory.

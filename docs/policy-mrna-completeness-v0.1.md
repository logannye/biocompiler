# Exact mRNA completeness for bounded policy realization v0.1

This is the frozen structural contract for SM-01.6 of the
[semantic compilation plan](semantic-mrna-development-plan.md). It defines
the first material profile; implementation and hosted acceptance of its full
checker remain SM-06/08 work. No current operational-policy response gains an
RNA, realization or export claim from this document.

Profile identity: `biocompiler.policy_mrna_completeness.v0.1`.

## Authority and claim

The caller supplies the exact member inventory, component/template identities,
construction roots and transforms, product expectations, required-region
contracts and nominal chemistry. The candidate cannot supply its own expected
authority. Acceptance is exact structural and derivational correspondence under
those inputs. Model-to-material correspondence is an additional independent
requirement; neither structural completeness nor sequence equality establishes
implementation behavior by itself.

The complete artifact is the ordered RNA molecule set together with its manifest.
FASTA carries canonical nucleotide spelling. The manifest also carries chemistry,
features, member identities, product and implementation bindings, source maps and
construction derivation. No chemical identity is inferred from FASTA letters.

## Closed initial structural predicate

Every delivered member, including helpers, must satisfy all rows. Later profiles
may add other layouts; this profile never silently degrades its requirements.

| ID | Required condition |
| --- | --- |
| PM-01 | The original request determines a nonempty, bounded, exact ordered member inventory. Every emitted member has an authorized payload/helper role and recipient binding. Missing, extra, duplicated or substituted members fail. External host providers are retained as separate supplied premises and cannot be counted as delivered RNA. |
| PM-02 | Each member has `Delivered_rna` form, RNA alphabet, linear topology, a 5′-to-3′ coordinate axis and complete sequence extent. Its canonical spelling contains only uppercase A/C/G/U and exactly matches its declared coordinate length. `Exact_core`, circular RNA, DNA and protein outputs are outside this profile. |
| PM-03 | One nonempty 5′ UTR, one nonempty CDS, one nonempty 3′ UTR and one nonempty exact represented terminal poly(A) region partition the complete spelling in that order, without gaps or overlap. Each required region is one forward, zero-based half-open interval. No additional ORF, unmodeled spacer, uncertain appended tail or implicit junction sequence is allowed. Extra annotations may overlap these regions only when explicitly supplied and checked separately. |
| PM-04 | The CDS has an explicit frame-zero start, in-frame termination and whole-region translation under `ordinary_cds`, genetic code `ncbi_standard_v1`, with an empty recoding inventory. The independently supplied complete product spelling must match. Internal stops, unresolved products, modifications inside the CDS and recoding are outside this first profile. Synonymous substitutions still require exact nucleotide authority; equal protein output does not authorize a base edit. |
| PM-05 | Cap and both terminal chemical identities are declared, versioned and nominally complete. Unknown or inapplicable values fail for these required linear-mRNA fields. An absent cap is outside this first profile. These are supplied chemical specifications, not claims about manufactured material. |
| PM-06 | The nucleotide-modification inventory is explicitly complete (`Declared`), possibly empty. Every modification has a complete supplied chemical identity and an exact valid site set or checked all-matching-base rule. Unknown, absent or inapplicable inventory status fails. Parent bases, coordinates and non-overlap agree with canonical spelling. Modification sites must lie outside the CDS under PM-04; canonical-parent translation cannot silently supply a modified-CDS interpretation. |
| PM-07 | Tail status is declared, placement is `Represented_terminal`, length is a positive exact integer and its path equals the PM-03 terminal region. Its canonical bases are all A. A bound, unknown length, absent tail or appended-tail/core-only representation fails. |
| PM-08 | Each required region boundary, chemistry declaration, selected fragment and construction mapping has explicit supplied authority. Existing declarations with unknown provenance/boundaries cannot establish completeness. A locator string alone is not a root identity. |
| PM-09 | Independent reconstruction accounts for every emitted base using pinned roots and authorized transforms. Every source/destination coordinate, orientation, junction and member mapping agrees with the original construction request. No back-translation, optimization, padding or automatic feature repair occurs. |
| PM-10 | Component configuration, encoded products, helpers and every behavior-bearing connection have a complete checked material disposition. Any non-sequence executable configuration resolves to an authorized modeled input or supplied resource. A manifest-only timer, threshold or connection is unresolved. |
| PM-11 | Exact/max member, helper, ORF, product and sequence-length constraints from the original request all hold, with their distinct meanings retained. The full declared recipient, resource and availability contracts remain checked elsewhere in the chain; this predicate cannot waive them. |
| PM-12 | Fresh verification binds the exact current original request, implementation/model authority, construction authority, RNA bytes and complete manifest. Copied PASS fields, recomputed candidate hashes and partial publication cannot establish acceptance. |

This initial profile deliberately supplies a complete tail and chemistry rather
than representing a distribution of physical products. That restriction is a
software contract for exact artifact identity, not a biological viability rule.
All sequence fixtures remain explicitly artificial.

## Reuse boundaries

Reuse the existing typed
[molecules](../core/lib/domain/molecule.mli),
[chemistry](../core/lib/domain/molecule_chemistry.mli),
[coordinates](../core/lib/domain/molecule_coordinates.mli),
[required regions](../core/lib/domain/payload_structure.mli) and
[construction](../core/lib/domain/construction.mli).
Their decoders retain wider cases, including exact cores and unresolved features;
successful decoding is not admission to this narrower profile.

[Payload_structure_check](../core/lib/checker/payload_structure_check.mli)
checks separately supplied region authority and nominal completeness, but its
success alone does not establish PM-01–12. It neither requires this particular
four-region partition nor proves policy implementation or complete product
translation. The policy material adapter must enforce the additional obligations
without fabricating a legacy circuit source or dropping the rich request.

[Construction_check](../core/lib/checker/construction_check.mli) provides
independent reconstruction against original construction authority. Its accepted
result is a dependency of policy material acceptance, not a replacement for
implementation-to-component correspondence or the original assurance request.

## Required distinguishing controls

Freeze a complete positive artificial fixture before material producer work.
Independently authored near-neighbor controls must include:

- Unchanged complete bases with `Exact_core` extent or a bounded/unknown tail.
- Unknown cap/end/modification inventory, absent cap and an unrepresented tail.
- Missing/empty/overlapping/reversed regions, an extra uncovered junction base,
  a shifted CDS frame and an incorrect product or internal stop.
- A changed base preserving protein spelling, with candidate hashes recomputed.
- A missing helper, unauthorized extra member or wrong recipient binding.
- Identical RNA with changed executable configuration lacking a carrier.
- A selected component with the same interface but different transitions.
- Correct structure under the wrong original request or stale model/template pin.

Each result must distinguish contradiction, unsupported profile, unresolved
authority and resource exhaustion. None may become a complete accepted export.
Positive structural controls must retain explicit implementation-unassessed
status until the full SM-04–07 chain is checked.

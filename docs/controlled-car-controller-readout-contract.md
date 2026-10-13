# Controlled CAR controller and readout contract

The [versioned contract](../data/car_controlled_reference/controller-readout-contract.json)
supplies the conditional behavior authority for the two-RNA adaptation of
`WO2014127261A1-197-206`. It connects exact product identities to the existing
[RC5 model](controlled-composition-behavior-v0.1.md); it supplies no calibrated
biological simulation. The intended recipient remains a human CD8 T cell
engineered in vivo. The public experiment context is recorded separately.

## Public controller identity

The [patent](https://patents.google.com/patent/WO2014127261A1/en), Example 1,
paragraphs [00276]-[00277], identifies its rapalog as A/C Heterodimerizer,
Clontech catalog #635055. The [manufacturer's February 2012 catalog](https://takara.co.kr/file/manual/pdf/heteroCitations_FL_633289_0212_IN.pdf),
PDF page 1, maps AP21967 to A/C Heterodimerizer, including #635055. This
source-derived catalog join supports the AP21967 name for the controller. It
does not establish chemical identity of an experimental lot or measured behavior
of the proposed RNA adaptation.

The original catalog PDF is retained only in the owned ignored directory
`generated/public-reference-readiness/`: 553,980 bytes, SHA-256
`7fe04c5c881eec85e64d50fd8604c1bd0fc7d050a146c4c6c1fcbfc9ccc519e3`.
Acquisition was capped at 1 MiB, checked for a PDF signature, and page 1 was
rendered and visually inspected. Existing patent and article inputs were
rehashed read-only. Exact original pins, locators, reuse status and asset
metadata are retained in the contract. These originals are not bundled into
package data or granted redistribution rights by the contract.

## Source endpoints and the modeled readout

Patent Figure 15 and paragraph [00282] associate #197 + #206 with reported
drug-dependent cytotoxicity in engineered primary human CD8 T cells. Paragraph
[00277] describes target-cell survival measurement. This reported endpoint is
not a continuous receptor-activity readout, a complete mRNA experiment, or an
adaptation-specific withdrawal bound.

[Wu et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC4721629/), Figure 2, names
I.b + II.d. Its exact sequence identity with the selected patent pair remains
unresolved. The results describing the on/off/on killing experiment, referencing
Figure S8, use three 36-hour stages. Those observation windows do not determine
receptor shutdown timing and supply none of this contract's numerical values.

The selected software readout is a latent receptor-activity state with
`background` and `active` bands. Both are uncalibrated categories. Background
does not mean zero target-cell killing. The model contains no conversion to
cytotoxicity, cytokine output, or clinical response. Its controller input is
effective AP21967 exposure categorized as `enabled` or `disabled`, with no
numeric exposure threshold or administration meaning.

## Explicit scenario assumptions

The contract freezes the following supplied software scenario. The physical
clock unit remains seconds because that is the admitted profile's clock; the
scale is an arbitrary scenario choice, not an estimate of biological speed.

| Quantity | Supplied value | Meaning |
| --- | --- | --- |
| Clock resolution | 1 second per tick | Uncalibrated software clock |
| Actual onset, cessation, reactivation | 1 tick each | Three mechanism-model assumptions |
| Source onset, controller-off, antigen-off, component-off, reactivation deadlines | 2 ticks each | Five independently authored source requirements |
| Horizon | Tick 10 | Finite assessment boundary |
| Intervention cutoff | Tick 6 | Scenario boundary before the fixed suffix |
| Freshness | 1 tick | All six input channels and activity evidence |
| Initial activity | Background | Initial-state assumption |

Changing these values requires changing the versioned original contract and
fresh checking. The source monitor uses the requested deadlines independently
of the mechanism's actual delays. A mechanism that exceeds a requested
deadline must fail; source requirements are not made true by copying them into
the mechanism. A later requirement for calibrated timing remains unsupported
until appropriate authority and a supported contract are supplied.

The modeled gate combines antigen recognition, effective controller exposure,
and the availability of both functional protein products. Both RNA members
are assigned to the same recipient; cytoplasmic RNA presence and functional
cell-surface protein availability remain distinct inputs. All localization,
expression sufficiency, delivery and adaptation-specific functional premises
are explicit assumptions. Binary availability cannot satisfy requirements for
controller concentration, RNA copy number, protein expression, member ratio,
or molecular stoichiometry. Nominal resource capacities do not close those gaps.

RC5's existing transition semantics remain authoritative: disabling has priority
over activation, committed cessation survives gate restoration, reactivation
has a separate delay, and encounter changes do not reset executor-owned activity.
RNA loss alone does not trigger protein-dependent cessation. The cessation of
this modeled activity does not reverse prior target-cell injury or guarantee
cessation of downstream effects.

## Observation and validation boundary

The finite scenario supplies explicit software evidence at every required tick.
`valid` denotes admitted supplied observation evidence, not laboratory data.
Unknown demanded evidence remains unknown and cannot rewrite the physical
history. Missingness, physical absence, and failed source requirements retain
their separate RC5 meanings.

The JSON distinguishes `measured`, `source_derived`, `designer_assumed`, and
`unresolved` origins. It has no measured records. Public reports are
source-derived observations in their original context; every numerical model
parameter is designer-assumed. Exact molecule construction, finite-domain
behavior checking and empirical qualification remain separate results.

Contract version 2 adds an explicit nominal translation premise as the eleventh
assumption. The selected implementation depends on the exact model definition
`biocompiler.controlled.nominal_translation.v1`: standard-code translation with
one stop, projecting declared N1-methylpseudouridine at canonical U positions
to parent U for nominal sequence comparison. This is a separate conditional
structural interpretation; physical translation, processing and expression
remain unmeasured. The existing ordinary structural route keeps its rejection
of modified coding regions. The RNA and encoded-protein identities are unchanged.

The native helper must preserve complete material product pins, these original
assumptions and the contract's whole-file identity in the researcher project.
The six-field `sources` rows can enter native project context directly; the
separate `source_assets` metadata must remain available for audit. Fresh hosted
Core and Verify checks are required for native acceptance. Saved reports,
source citations and successful local preparation cannot grant it. No human-use
admission or therapeutic efficacy follows from this contract.

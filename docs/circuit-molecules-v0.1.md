# Declared circuit molecules v0.1 (R3)

R3 represents complete supplied strand/chain spellings, partial linear cores,
structured chemistry, overlapping annotations, nominal complexes and molecular
role instances alongside the complete human `CircuitRequest`. It validates those
declarations and their identities. It does not assemble new molecules, verify
source bytes, execute processing, establish circuit function or admit human use.
The R2 API and R3 records remain provisional until R6 exercises a complete
source-backed vertical slice. Existing molecular/payload schemas and their
checkers remain unchanged.

## Molecular forms and human scope

`CircuitMolecule` describes one covalent nucleotide strand or protein chain.
Form, polymer alphabet, coding annotation, topology and circuit role are separate:

- Forms distinguish deposited template records, DNA expression templates,
  delivered DNA, primary/delivered/processed/edited RNA, protein precursors and
  mature proteins. A deposited record is not automatically a delivered payload.
- DNA canonical symbols are ACGT; RNA symbols are ACGU. Protein spelling accepts
  the standard one-letter residues plus U and O. No T/U conversion, codon repair,
  translation, reverse complement or optimization occurs.
- Linear and circular topologies have explicit coordinate frames. Noncoding,
  coding and unknown nucleotide annotations remain distinct; protein coding
  status is inapplicable. Multiple CDS/ORF/uORF annotations and conditional-stop
  features are allowed without forcing ordinary-CDS translation assumptions.
- A partial linear RNA core with an uncertain appended terminal tail retains
  `sequence_extent="exact_core"`; generic truncated DNA/protein records are not
  supported by this profile. Circular
  coordinates require a complete supplied circumference; partial arcs cannot
  invent its length or closing boundary. Chemistry can remain unknown for an
  otherwise complete spelling.

`MolecularComplex` references explicit constituent records and positive integer
stoichiometry, or explicit unknown copy counts. No concatenated peptide or
coordinate space is invented. Fully specified complexes require at least two
constituent copies. A declared DNA duplex contains two separately recorded DNA
strands, each with one copy; no complement, orientation, base pairing or physical
association is inferred. The two records may have identical nominal species.
Protein and RNA complexes likewise describe membership, not proven binding.

A `CircuitMoleculeSet` retains the entire R2 request, including human target,
source locations, input bindings and original behavior/deployment/acceptance
wrappers. Every requested-payload role must match the requested molecular form;
a template, helper or control cannot satisfy it. Requested `circular_rna` means
a circular delivered-RNA member. At least one requested-payload role is required.
Product role compartments must belong to the original human target. Separate
human-reference context stays separate; no organism backend is introduced.

## Coordinates, assembly origins and annotations

`CoordinateSpace(id, alphabet, length, topology, axis)` names an exact frame.
Nucleotides use a 5-prime to 3-prime axis, proteins an N-to-C axis. `IndexSpan`
uses zero-based half-open coordinates. `CoordinatePath(space_id, spans, strand)`
preserves the supplied span order; strand controls traversal within each span.
No sorting, rotation or sequence operation is implicit. A circular crossing is
explicitly segmented, for example `[8,10), [0,3)` on a ten-residue circle.

Spans in one path cannot overlap each other; different feature paths may overlap
freely. A single zero-length span denotes a boundary annotation. Protein paths
use forward orientation. Materializing positions requires a bounded explicit
limit; geometry validation does not expand a whole molecule into a position list.

Assembly is an ordered partition of the supplied spelling. Each `AssemblyOrigin`
has one nonempty forward contiguous destination span, a complete source frame,
an oriented source path and provenance. Destinations cover `[0,length)` exactly
once, with no gaps or duplication. Source and destination counts and alphabets
must agree. The origin is still a declared relationship; the separate
[R4 construction workflow](circuit-construction-v0.1.md) independently checks
actual supplied source bytes and transformations.

`MoleculeFeature` is independent of this partition. Repeated motifs retain
separate occurrence IDs; CDS, regulatory and structural annotations may overlap.
Each feature's explicit provenance applies to its recorded path boundaries;
an unknown path or unknown provenance stays explicit. Reading frames are nominal
annotations. A noncoding declaration cannot also assert one of the recognized coding feature
kinds (`CDS`, `cds`, `ORF`, `orf`, `uORF`, `uorf`); free-text kinds do not acquire
additional inferred semantics.
Coordinate-space IDs must be consistent across all destinations and assembly
sources; different molecule records have distinct destination frame IDs.

`FormCoordinateMapping` pins both complete molecule records and names source and
destination paths, a declared relation and provenance. Unequal path lengths can
represent a declared translation/processing correspondence. R3 checks record
identity and geometry only; it does not prove that relation or execute an edge.
Complexes have constituent frames, not a concatenated complex frame.

## Chemistry and uncertainty

`MoleculeChemistry` records cap, start and finish terminal groups, individual
modifications or documented substitution policies, modification-inventory status
and terminal-tail declarations. Chemistry claims distinguish declared, absent,
unknown and inapplicable. A linear RNA may be explicitly uncapped; unknown cap
chemistry is a different declaration. Circular terminal features are
inapplicable. DNA/protein do not acquire RNA cap/tail assumptions.

`ChemicalIdentity(namespace, accession, version)` is a declared identifier, not
an ontology lookup. The versioned built-in names distinguish inosine,
pseudouridine and N1-methylpseudouridine. Inosine uses canonical A plus a separate
modification declaration; bare I in RNA is rejected and never converted to G.
The two uridine modifications use canonical U with different chemical identities.
Other identifiers remain nominal declarations with no inferred biochemical map.

Modifications name exact positions or an `all_matching_bases` substitution
policy. Parent symbols and bounds must agree with the supplied spelling, and
modification scopes cannot overlap. A declared empty inventory differs from an
unknown inventory. Known modifications may coexist with uncertainty about
additional modifications.

A represented terminal tail must be a forward terminal span containing the
specified exact number of adenines. An internal A-run followed by an extension
is an annotation, not the physical terminal tail. An uncertain appended tail
requires a partial linear RNA core, explicit bounded/unknown length, and no
invented coordinates or symbols. No estimated adenines are appended.

`DeclarationProvenance` records source/evidence pins and a locator for a declared
origin, or an explicit unknown with a reason. Every chemistry declaration keeps
provenance independently of its value. Known chemistry can have unknown source
provenance; good provenance cannot resolve unknown chemistry. Source pins do not
establish retrieval, review, material identity or empirical function.

## Identity layers and multiplicity

| Identity | Includes | Excludes |
| --- | --- | --- |
| `spelling_identity` | Alphabet and exact supplied canonical symbols | Chemistry, topology, labels and provenance |
| `declared_nominal_identity` | Alphabet/axis/topology, spelling, extent and normalized chemistry/uncertainty | Record/frame labels, feature annotations, source provenance and processing-form labels |
| `complete_nominal_identity` | Same nominal identity when the complete declaration is specified | Returns `None` for a partial core or unresolved nominal chemistry |
| `base_rotation_identity` | Canonical base-only circular rotation, computed without changing the stored origin | Reverse-complement equivalence, chemistry and annotations |
| Record `fingerprint` | Every supplied form, coordinate, annotation, policy, reference and provenance field | Nothing in that record |
| `declared_nominal_bundle_identity` | Species inventory and the full multiset of role descriptors, with complex stoichiometry | Archival record/role IDs, amounts, run metadata and source authority |
| `experimental_specification_identity` | Complete bundle/request authority and all declared preparation amounts | Run metadata |
| Artifact `fingerprint` | Complete record including run metadata | Nothing in the archive |

Equivalent complete modification coverage has the same nominal identity whether
written as grouped sites, separate site records or an all-matching policy. The
coverage hash is streamed, without expanding large policies into position JSON.
Policies on an uncertain core remain explicit constraints on its unspecified
continuation. For a complete supplied spelling, moving only a represented tail's
annotation boundary changes archival identity, not its chemical species; adding
or removing actual tail bases changes both spelling and nominal identity.

All full records retain source origin and policy. Rotation equivalence never
replaces exact reference equality. Unknown nominal declarations can be compared
as declarations, but cannot establish identical physical material. Nominal
completeness means the declared fields are specified; it is not chemical-ontology
validation, source fidelity, molecular implementation or human-use evidence.
Unknown coding/function annotations remain a separate obligation from chemistry.

Molecule records, molecular species, role instances and experimental quantities
are separate. One species can fill several explicitly named roles; sorting never
deduplicates those role occurrences. Different records and source forms remain
in the full archive even when they describe the same nominal species. No number
of roles or records is interpreted as dose or experimental copy count.

`ExperimentalAmount` binds one subject/preparation and the roles explicitly
sharing it. Quantity can be numeric or unknown; zero is not unknown. Units are
preserved without conversion or summation. A preparation cannot acquire a second
amount through an alias of the same nominal species. Amount changes invalidate
the experimental specification while leaving the molecular species unchanged.
This is declaration consistency, not experimental mass-balance verification.

## Python, CLI and validation

All records are public Python types. The runnable
[`examples/circuit_molecules.py`](../examples/circuit_molecules.py) uses only tiny,
explicitly artificial strings and source notices. It includes a multi-RNA set,
noncoding RNA, repeated/overlapping features, a post-poly(A) extension, a circle,
conditional-stop annotations, precursor/mature protein records, a complex and
uncertain tail/amount declarations. No published construct is reproduced.

```sh
python examples/circuit_molecules.py --output generated/circuit-molecules
biocompiler inspect generated/circuit-molecules/bundle.json
biocompiler inspect generated/circuit-molecules/record.json
```

Inspection labels source correspondence and assembly unverified, molecular
function unestablished and human admission absent. `compile()` refuses to promote
a molecular set or archival record into a compiled circuit payload. There is no
FASTA exporter or transformation backend for these records at R3.

Strict versioned schemas reject unknown fields, stale references, conflicting
spaces, invalid alphabets, impossible partitions and incompatible forms. Limits
include 64 molecules/complexes, 256 roles/mappings/features/origins per relevant
inventory, one million total supplied residues, 128 spans per path, 128
modifications and 4,096 explicit sites per modification. Documents are bounded to
4 MB including a publication newline, 100,000 structural items and depth 96; the
embedded R2 request also retains its own stricter limits. Streaming serialization
bounds indentation expansion before joining the JSON document.

Tests cover the examples plus hostile imports, partition gaps/overlaps, stale
pins, aliasing, source/wrapper retention, circle/chemistry identities and public
CLI claim boundaries. Hosted CI installs on Python 3.11/3.14 and retains the
example JSON while preserving every existing regression and browser gate.

"""Declared molecular identities and named sets for human circuit requirements.

This profile represents supplied covalent strands/chains and declared complexes.
It does not assemble, transform, translate or prove those molecules implement a
circuit. Geometry, chemistry, source authority and biological function remain
separate. Every nucleotide string is in its nominated 5-prime to 3-prime frame.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import ClassVar

from biocompiler.artifacts.manifest import _hash
from biocompiler.ir.circuit_intent import CircuitRequest
from biocompiler.ir.molecule_records import (
    MAX_RESIDUES,
    CANONICAL_ALPHABETS,
    DeclarationProvenance,
    _MoleculeRecord,
    _choice,
    _decode_records,
    _optional,
    _records,
    _text,
)
from biocompiler.ir.molecule_chemistry import MoleculeChemistry
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.semantics.molecule_coordinates import CoordinatePath, CoordinateSpace


MAX_MOLECULES = 64
MAX_FEATURES = 256
MAX_ORIGINS = 256
MAX_ROLES = 256
MAX_MAPPINGS = 256
FORMS = frozenset(
    {
        "deposited_template_record",
        "dna_expression_template",
        "delivered_dna",
        "primary_rna",
        "delivered_rna",
        "processed_rna",
        "edited_rna",
        "protein_precursor",
        "mature_protein",
    }
)

MAPPING_RELATIONS = frozenset(
    {
        "declared_correspondence",
        "slice",
        "orientation",
        "transcription",
        "rna_processing",
        "base_editing",
        "translation",
        "protein_cleavage",
        "protein_splicing",
        "circularization",
        "ribosomal_skipping",
    }
)


def _provenance(value):
    require(
        isinstance(value, DeclarationProvenance),
        "Expected explicit declaration provenance.",
    )


def _path(value):
    require(isinstance(value, CoordinatePath), "Expected a coordinate path.")


def _least_rotation(sequence):
    """Booth's linear-time minimal rotation; never alter the stored spelling."""
    doubled = sequence + sequence
    n = len(sequence)
    i, j, matched = 0, 1, 0
    while i < n and j < n and matched < n:
        left, right = doubled[i + matched], doubled[j + matched]
        if left == right:
            matched += 1
            continue
        if left > right:
            i = i + matched + 1
            if i <= j:
                i = j + 1
        else:
            j = j + matched + 1
            if j <= i:
                j = i + 1
        matched = 0
    start = min(i, j)
    return doubled[start : start + n]


@dataclass(frozen=True)
class AssemblyOrigin(_MoleculeRecord):
    """One declared geometric origin, independently unverified at R3."""

    id: str
    destination: CoordinatePath
    source_space: CoordinateSpace
    source_path: CoordinatePath
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.assembly_origin.v0.1"
    _decoders: ClassVar[dict] = {
        "destination": CoordinatePath.from_dict,
        "source_space": CoordinateSpace.from_dict,
        "source_path": CoordinatePath.from_dict,
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        _text(self.id, "Assembly occurrence identity")
        _path(self.destination)
        require(
            isinstance(self.source_space, CoordinateSpace),
            "Expected assembly source coordinate space.",
        )
        _path(self.source_path)
        self.source_path.validate_for(self.source_space)
        require(
            self.destination.length == self.source_path.length > 0,
            "Assembly origin must preserve a positive coordinate count.",
        )
        _provenance(self.provenance)
        self._check_resources()


@dataclass(frozen=True)
class MoleculeFeature(_MoleculeRecord):
    """An independent annotation; overlap never duplicates an assembly origin."""

    id: str
    kind: str
    path: CoordinatePath | None
    provenance: DeclarationProvenance
    reading_frame: int | None = None
    schema_version: ClassVar[str] = "biocompiler.molecule_feature.v0.1"
    _decoders: ClassVar[dict] = {
        "path": _optional(CoordinatePath),
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        _text(self.id, "Feature occurrence identity")
        _text(self.kind, "Feature kind")
        require(
            self.path is None or isinstance(self.path, CoordinatePath),
            "Expected feature coordinates or explicit unknown.",
        )
        require(
            self.reading_frame is None
            or (type(self.reading_frame) is int and self.reading_frame in (0, 1, 2)),
            "Invalid reading frame.",
        )
        _provenance(self.provenance)
        self._check_resources()


@dataclass(frozen=True)
class CircuitMolecule(_MoleculeRecord):
    """One covalent strand/chain, not an inferred duplex or complex."""

    id: str
    form: str
    space: CoordinateSpace
    sequence: str
    sequence_extent: str
    coding_status: str
    assembly: tuple[AssemblyOrigin, ...]
    features: tuple[MoleculeFeature, ...]
    chemistry: MoleculeChemistry
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.circuit_molecule.v0.1"
    _decoders: ClassVar[dict] = {
        "space": CoordinateSpace.from_dict,
        "assembly": _decode_records(AssemblyOrigin, MAX_ORIGINS),
        "features": _decode_records(MoleculeFeature, MAX_FEATURES),
        "chemistry": MoleculeChemistry.from_dict,
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        _text(self.id, "Molecule record identity")
        _choice(self.form, FORMS, "molecular form")
        require(
            isinstance(self.space, CoordinateSpace),
            "Expected a molecular coordinate space.",
        )
        require(
            isinstance(self.sequence, str) and 0 < len(self.sequence) <= MAX_RESIDUES,
            "Invalid molecular sequence length.",
        )
        require(
            set(self.sequence) <= CANONICAL_ALPHABETS[self.space.alphabet],
            "Invalid canonical molecular alphabet; modifications are separate declarations.",
        )
        require(
            self.space.length == len(self.sequence),
            "Coordinate space must match the supplied spelling length.",
        )
        _choice(self.sequence_extent, {"complete", "exact_core"}, "sequence extent")
        require(
            self.space.topology != "circular" or self.sequence_extent == "complete",
            "Circular coordinates require a complete supplied circumference, not a partial core.",
        )
        _choice(
            self.coding_status,
            {"coding", "noncoding", "unknown", "inapplicable"},
            "coding annotation status",
        )
        expected_alphabet = (
            "protein"
            if self.form in {"protein_precursor", "mature_protein"}
            else "DNA"
            if self.form
            in {"deposited_template_record", "dna_expression_template", "delivered_dna"}
            else "RNA"
        )
        require(
            self.space.alphabet == expected_alphabet,
            "Molecular form and canonical alphabet disagree.",
        )
        require(
            (self.coding_status == "inapplicable")
            == (self.space.alphabet == "protein"),
            "Protein coding status is inapplicable; nucleotide coding annotations remain explicit.",
        )
        require(
            isinstance(self.assembly, (tuple, list))
            and 0 < len(self.assembly) <= MAX_ORIGINS
            and all(isinstance(item, AssemblyOrigin) for item in self.assembly),
            "Expected bounded nonempty assembly partition.",
        )
        partition = tuple(
            AssemblyOrigin.from_dict(item.to_dict()) for item in self.assembly
        )
        require(
            len({item.id for item in partition}) == len(partition),
            "Duplicate assembly occurrence identities.",
        )
        cursor, source_spaces = 0, {self.space.id: self.space}
        for origin in partition:
            origin.destination.validate_for(self.space)
            require(
                origin.source_space.alphabet == self.space.alphabet,
                "Assembly origins cannot imply an alphabet conversion.",
            )
            require(
                origin.destination.strand == "+" and len(origin.destination.spans) == 1,
                "Assembly destinations require one forward contiguous span.",
            )
            span = origin.destination.spans[0]
            require(
                span.start == cursor and span.end > span.start,
                "Assembly partition must cover each supplied residue exactly once, in order.",
            )
            cursor = span.end
            previous = source_spaces.get(origin.source_space.id)
            require(
                previous is None
                or previous.fingerprint == origin.source_space.fingerprint,
                "Conflicting assembly source coordinate identity.",
            )
            source_spaces[origin.source_space.id] = origin.source_space
        require(
            cursor == len(self.sequence),
            "Assembly partition must cover the complete supplied spelling.",
        )
        object.__setattr__(self, "assembly", partition)
        object.__setattr__(
            self,
            "features",
            _records(
                self.features, MoleculeFeature, MAX_FEATURES, "feature occurrences"
            ),
        )
        for feature in self.features:
            if feature.path is not None:
                feature.path.validate_for(self.space)
            require(
                self.space.alphabet != "protein" or feature.reading_frame is None,
                "Protein annotations have no nucleotide reading frame.",
            )
            require(
                self.coding_status != "noncoding"
                or feature.kind not in {"CDS", "cds", "ORF", "orf", "uORF", "uorf"},
                "Noncoding declaration conflicts with a coding annotation.",
            )
        require(
            isinstance(self.chemistry, MoleculeChemistry),
            "Expected structured molecular chemistry.",
        )
        self.chemistry.validate_for(self.space, self.sequence, self.sequence_extent)
        _provenance(self.provenance)
        self._check_resources()

    @property
    def spelling_identity(self):
        return fingerprint(
            {
                "profile": "canonical_spelling.v0.1",
                "alphabet": self.space.alphabet,
                "sequence": self.sequence,
            }
        )

    def nominal_dict(self):
        chemistry = self.chemistry.nominal_dict()
        # Policy/occurrence grouping is archival authority. The nominal identity
        # of a complete supplied spelling depends on the same chemical coverage,
        # whether expressed as one group, several groups, or a substitution rule.
        # Hash coverage incrementally to avoid a million-position JSON expansion.
        explicit, policies = {}, {}
        for modification in self.chemistry.modifications:
            token = bytes.fromhex(
                fingerprint(
                    {
                        "chemical": modification.identity.to_dict(),
                        "canonical_parent": modification.canonical_base,
                    }
                )
            )
            if modification.scope == "all_matching_bases":
                policies[modification.canonical_base] = token
            else:
                explicit.update(
                    (position, token) for position in modification.positions
                )
        coverage = hashlib.sha256(b"biocompiler.positioned_chemistry.v0.1\0")
        for position, symbol in enumerate(self.sequence):
            token = explicit.get(position, policies.get(symbol))
            if token is not None:
                coverage.update(position.to_bytes(8, "big"))
                coverage.update(token)
        core_policies = []
        if self.sequence_extent == "exact_core":
            # A policy can also constrain unspecified continuation; an explicit
            # site list cannot silently stand in for that unresolved policy.
            core_policies = sorted(
                (
                    item.nominal_dict()
                    for item in self.chemistry.modifications
                    if item.scope == "all_matching_bases"
                ),
                key=fingerprint,
            )
        chemistry["modifications"] = {
            "known_coverage_identity": coverage.hexdigest(),
            "unresolved_core_policies": core_policies,
        }
        if (
            self.sequence_extent == "complete"
            and self.chemistry.terminal_tail.status == "declared"
        ):
            # For a complete spelling, the exact supplied residues already
            # specify a represented tail. Moving only its annotation boundary
            # cannot create a different covalent species or a second dose.
            chemistry["terminal_tail"] = {
                "status": "declared",
                "physical_extent": "included_in_supplied_spelling",
            }
        return {
            "profile": "declared_covalent_species.v0.1",
            "alphabet": self.space.alphabet,
            "axis": self.space.axis,
            "topology": self.space.topology,
            "sequence": self.sequence,
            "sequence_extent": self.sequence_extent,
            "chemistry": chemistry,
        }

    @property
    def declared_nominal_identity(self):
        return fingerprint(self.nominal_dict())

    @property
    def declared_nominal_complete(self):
        return (
            self.sequence_extent == "complete"
            and self.chemistry.declared_nominal_complete
        )

    @property
    def complete_nominal_identity(self):
        return (
            self.declared_nominal_identity if self.declared_nominal_complete else None
        )

    @property
    def base_rotation_identity(self):
        if self.space.topology != "circular":
            return None
        return fingerprint(
            {
                "profile": "base_only_circular_rotation.v0.1",
                "alphabet": self.space.alphabet,
                "sequence": _least_rotation(self.sequence),
            }
        )


@dataclass(frozen=True)
class ComplexConstituent(_MoleculeRecord):
    molecule_id: str
    molecule_fingerprint: str
    stoichiometry: int | None
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.complex_constituent.v0.1"
    _decoders: ClassVar[dict] = {"provenance": DeclarationProvenance.from_dict}

    def __post_init__(self):
        _text(self.molecule_id, "Constituent record identity")
        _hash(self.molecule_fingerprint, "Constituent record")
        require(
            self.stoichiometry is None
            or (
                type(self.stoichiometry) is int
                and 0 < self.stoichiometry <= MAX_RESIDUES
            ),
            "Stoichiometry must be a positive integer or explicit unknown.",
        )
        _provenance(self.provenance)
        self._check_resources()


@dataclass(frozen=True)
class MolecularComplex(_MoleculeRecord):
    id: str
    kind: str
    constituents: tuple[ComplexConstituent, ...]
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.molecular_complex.v0.1"
    _decoders: ClassVar[dict] = {
        "constituents": _decode_records(ComplexConstituent, MAX_MOLECULES),
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        _text(self.id, "Complex record identity")
        _choice(
            self.kind, {"protein_complex", "dna_duplex", "rna_complex"}, "complex kind"
        )
        object.__setattr__(
            self,
            "constituents",
            _records(
                self.constituents,
                ComplexConstituent,
                MAX_MOLECULES,
                "complex constituents",
                key="molecule_id",
                nonempty=True,
            ),
        )
        if all(item.stoichiometry is not None for item in self.constituents):
            require(
                sum(item.stoichiometry for item in self.constituents) >= 2,
                "A noncovalent complex must declare at least two constituent copies; a single-copy wrapper is the original molecule.",
            )
        if self.kind == "dna_duplex":
            require(
                len(self.constituents) == 2
                and all(item.stoichiometry == 1 for item in self.constituents),
                "A declared DNA duplex requires two explicit single-copy strand records.",
            )
        _provenance(self.provenance)
        self._check_resources()


@dataclass(frozen=True)
class MoleculeRoleInstance(_MoleculeRecord):
    id: str
    subject_id: str
    subject_fingerprint: str
    role: str
    purpose: str
    compartment: str
    schema_version: ClassVar[str] = "biocompiler.molecule_role_instance.v0.1"

    def __post_init__(self):
        for key in ("id", "subject_id", "role", "compartment"):
            _text(getattr(self, key), key)
        _hash(self.subject_fingerprint, "Role subject record")
        _choice(
            self.purpose,
            {
                "requested_payload",
                "helper",
                "host_provider",
                "assay_control",
                "external_input",
            },
            "molecular role purpose",
        )
        require(
            self.compartment != "abstract",
            "Molecular roles require a declared physical compartment.",
        )
        self._check_resources()


@dataclass(frozen=True)
class FormCoordinateMapping(_MoleculeRecord):
    id: str
    source_molecule_id: str
    source_molecule_fingerprint: str
    destination_molecule_id: str
    destination_molecule_fingerprint: str
    source_path: CoordinatePath
    destination_path: CoordinatePath
    relation: str
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.form_coordinate_mapping.v0.1"
    _decoders: ClassVar[dict] = {
        "source_path": CoordinatePath.from_dict,
        "destination_path": CoordinatePath.from_dict,
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        for key in ("id", "source_molecule_id", "destination_molecule_id"):
            _text(getattr(self, key), key)
        _hash(self.source_molecule_fingerprint, "Mapping source record")
        _hash(self.destination_molecule_fingerprint, "Mapping destination record")
        _path(self.source_path)
        _path(self.destination_path)
        _choice(self.relation, MAPPING_RELATIONS, "declared coordinate relation")
        _provenance(self.provenance)
        self._check_resources()


def _requested_form_matches(molecule, requested):
    if requested == "circular_rna":
        return (
            molecule.form == "delivered_rna" and molecule.space.topology == "circular"
        )
    return molecule.form == requested


@dataclass(frozen=True)
class CircuitMoleculeSet(_MoleculeRecord):
    id: str
    request: CircuitRequest
    molecules: tuple[CircuitMolecule, ...]
    complexes: tuple[MolecularComplex, ...]
    role_instances: tuple[MoleculeRoleInstance, ...]
    form_mappings: tuple[FormCoordinateMapping, ...]
    schema_version: ClassVar[str] = "biocompiler.circuit_molecule_set.v0.1"
    _decoders: ClassVar[dict] = {
        "request": CircuitRequest.from_dict,
        "molecules": _decode_records(CircuitMolecule, MAX_MOLECULES),
        "complexes": _decode_records(MolecularComplex, MAX_MOLECULES),
        "role_instances": _decode_records(MoleculeRoleInstance, MAX_ROLES),
        "form_mappings": _decode_records(FormCoordinateMapping, MAX_MAPPINGS),
    }

    def __post_init__(self):
        _text(self.id, "Molecular set identity")
        require(
            isinstance(self.request, CircuitRequest),
            "Molecule sets require complete human circuit request authority.",
        )
        object.__setattr__(
            self, "request", CircuitRequest.from_dict(self.request.to_dict())
        )
        for key, cls, maximum in (
            ("molecules", CircuitMolecule, MAX_MOLECULES),
            ("complexes", MolecularComplex, MAX_MOLECULES),
            ("role_instances", MoleculeRoleInstance, MAX_ROLES),
            ("form_mappings", FormCoordinateMapping, MAX_MAPPINGS),
        ):
            object.__setattr__(
                self,
                key,
                _records(
                    getattr(self, key),
                    cls,
                    maximum,
                    key,
                    nonempty=key in {"molecules", "role_instances"},
                ),
            )
        molecules = {item.id: item for item in self.molecules}
        complexes = {item.id: item for item in self.complexes}
        require(
            not (molecules.keys() & complexes.keys()),
            "Molecules and complexes require distinct record identities.",
        )
        require(
            len({item.space.id for item in self.molecules}) == len(molecules),
            "Molecule coordinate-space identities must be unique within a set.",
        )
        all_spaces = {item.space.id: item.space for item in self.molecules}
        for molecule in self.molecules:
            for origin in molecule.assembly:
                previous = all_spaces.get(origin.source_space.id)
                require(
                    previous is None
                    or previous.fingerprint == origin.source_space.fingerprint,
                    "Conflicting coordinate-space identity across molecular declarations.",
                )
                all_spaces[origin.source_space.id] = origin.source_space
        require(
            sum(len(item.sequence) for item in self.molecules) <= MAX_RESIDUES,
            "Molecule set total residue budget exceeded.",
        )
        for complex_ in self.complexes:
            alphabet = {
                "protein_complex": "protein",
                "dna_duplex": "DNA",
                "rna_complex": "RNA",
            }[complex_.kind]
            for constituent in complex_.constituents:
                molecule = molecules.get(constituent.molecule_id)
                require(
                    molecule is not None
                    and molecule.fingerprint == constituent.molecule_fingerprint,
                    "Missing or stale complex constituent record.",
                )
                require(
                    molecule.space.alphabet == alphabet,
                    "Complex kind and constituent polymer disagree.",
                )
        subjects = molecules | complexes
        requested = 0
        for instance in self.role_instances:
            subject = subjects.get(instance.subject_id)
            require(
                subject is not None
                and subject.fingerprint == instance.subject_fingerprint,
                "Missing or stale molecular role subject.",
            )
            if self.request.profile.target is not None:
                require(
                    instance.compartment in self.request.profile.target.compartments,
                    "Molecular role must retain a declared human target compartment.",
                )
            if instance.purpose == "requested_payload":
                requested += 1
                members = (
                    (subject,)
                    if isinstance(subject, CircuitMolecule)
                    else tuple(
                        molecules[item.molecule_id] for item in subject.constituents
                    )
                )
                require(
                    all(
                        _requested_form_matches(member, self.request.requested_form)
                        for member in members
                    ),
                    "Every requested payload member must match the requested molecular form; no template or modality substitution.",
                )
        require(
            requested > 0,
            "Molecule set must name at least one requested-payload role instance.",
        )
        for mapping in self.form_mappings:
            source, destination = (
                molecules.get(mapping.source_molecule_id),
                molecules.get(mapping.destination_molecule_id),
            )
            require(
                source is not None
                and source.fingerprint == mapping.source_molecule_fingerprint
                and destination is not None
                and destination.fingerprint == mapping.destination_molecule_fingerprint,
                "Coordinate mapping binds missing or stale molecule records.",
            )
            mapping.source_path.validate_for(source.space)
            mapping.destination_path.validate_for(destination.space)
        self._check_resources()

    def _nominal_subject_identities(self):
        molecules = {item.id: item.declared_nominal_identity for item in self.molecules}
        subjects = dict(molecules)
        for complex_ in self.complexes:
            # Aggregate known copies by declared species; archival constituent
            # records remain distinct. Unknown copies remain explicit.
            counts, unknowns = {}, {}
            for item in complex_.constituents:
                species = molecules[item.molecule_id]
                if item.stoichiometry is None:
                    unknowns[species] = unknowns.get(species, 0) + 1
                else:
                    counts[species] = counts.get(species, 0) + item.stoichiometry
            subjects[complex_.id] = fingerprint(
                {
                    "profile": "declared_complex_species.v0.1",
                    "kind": complex_.kind,
                    "known_copies": counts,
                    "unknown_terms": unknowns,
                }
            )
        return subjects

    def subject_nominal_identity(self, identity):
        identities = self._nominal_subject_identities()
        require(identity in identities, "Unknown molecular subject.")
        return identities[identity]

    def subject_complete(self, identity):
        molecules = {item.id: item for item in self.molecules}
        if identity in molecules:
            return molecules[identity].declared_nominal_complete
        complex_ = next((item for item in self.complexes if item.id == identity), None)
        require(complex_ is not None, "Unknown molecular subject.")
        return all(
            item.stoichiometry is not None
            and molecules[item.molecule_id].declared_nominal_complete
            for item in complex_.constituents
        )

    @property
    def declared_nominal_complete(self):
        return all(
            self.subject_complete(item.id)
            for item in (*self.molecules, *self.complexes)
        )

    @property
    def declared_nominal_bundle_identity(self):
        # Species are chemical declarations, while role occurrences are a
        # multiplicity-preserving list. Archival record IDs are not doses.
        identities = self._nominal_subject_identities()
        records = sorted(set(identities.values()))
        roles = sorted(
            (
                {
                    "species": identities[item.subject_id],
                    "role": item.role,
                    "purpose": item.purpose,
                    "compartment": item.compartment,
                }
                for item in self.role_instances
            ),
            key=fingerprint,
        )
        return fingerprint(
            {
                "profile": "declared_molecular_bundle.v0.1",
                "records": records,
                "roles": roles,
            }
        )

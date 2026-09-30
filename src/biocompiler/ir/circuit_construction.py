"""Frozen authority for bounded, generic circuit construction software.

Sources are independently supplied records. Output metadata never supplies an
expected output sequence or a generated product fingerprint. Internal references
bind unique declared product IDs; actual frames and spelling require independent
reconstruction. These declarations establish neither biochemical processing nor
circuit function, source fidelity or human admission.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import ClassVar

from biocompiler.artifacts.manifest import _hash
from biocompiler.ir.circuit_intent import CircuitRequest
from biocompiler.ir.circuit_molecules import CircuitMolecule, FORMS
from biocompiler.ir.circuit_payloads import (
    MAX_PAYLOAD_CONTRACTS,
    PayloadStructureContract,
)
from biocompiler.ir.circuit_recoding import (
    MAX_RECODINGS,
    CanonicalBaseEdit,
    ChemicalBaseEdit,
    TranslationPolicy,
)
from biocompiler.ir.circuit_transitions import ChemistryTransition, FeatureTransition
from biocompiler.ir.molecule_records import (
    CANONICAL_ALPHABETS,
    MAX_RESIDUES,
    DeclarationProvenance,
    _MoleculeRecord,
    _choice,
    _decode_records,
    _optional,
    _records,
    _text,
)
from biocompiler.ir.serialization import require
from biocompiler.semantics.molecule_coordinates import CoordinatePath, IndexSpan


CONSTRUCTION_PROFILE_VERSION = "biocompiler.circuit_construction.v0.1"
CAPABILITY_PROFILE_VERSION = "biocompiler.circuit_transform_capabilities.v0.1"
TRANSCRIPTION_MAPPING_PROFILE = "dna_coding_to_rna.v1"
MAX_SOURCES = 64
MAX_STEPS = 256
MAX_SELECTIONS = 128
MAX_PRODUCTS = 256
MAX_PROCESSING_PRODUCTS = 16
MAX_TRANSLATION_PRODUCTS = 16
MAX_TRANSLATION_BRANCHES = 16
MAX_OUTPUT_MEMBERS = 64
MAX_COMPLEX_MEMBERS = 64
MAX_AMOUNT_DECLARATIONS = 128
MAX_MEMBER_REQUIREMENTS = 256
MAX_ROLE_DECLARATIONS = 256
MAX_ASSUMPTIONS = 32
MAX_TOTAL_SOURCE_RESIDUES = MAX_RESIDUES
MAX_CUMULATIVE_PRODUCED_RESIDUES = MAX_RESIDUES
MEMBER_CATEGORIES = frozenset(
    {
        "payload",
        "delivered_helper",
        "encoded_product",
        "host_provider",
        "experimental_input",
        "control",
        "assay_reference",
    }
)
CATEGORY_PURPOSE = MappingProxyType(
    {
        "payload": "requested_payload",
        "delivered_helper": "helper",
        "encoded_product": "helper",
        "host_provider": "host_provider",
        "experimental_input": "external_input",
        "control": "assay_control",
        "assay_reference": "assay_control",
    }
)


def _provenance(value):
    require(
        isinstance(value, DeclarationProvenance),
        "Expected explicit construction provenance.",
    )


@dataclass(frozen=True)
class RootSource(_MoleculeRecord):
    id: str
    molecule: CircuitMolecule
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.construction_root_source.v0.1"
    _decoders: ClassVar[dict] = {
        "molecule": CircuitMolecule.from_dict,
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        _text(self.id, "Construction root identity")
        require(
            isinstance(self.molecule, CircuitMolecule),
            "Expected an independently supplied molecule record.",
        )
        _provenance(self.provenance)
        self._check_resources()


@dataclass(frozen=True)
class ValueRef(_MoleculeRecord):
    kind: str
    id: str
    schema_version: ClassVar[str] = "biocompiler.construction_value_ref.v0.1"

    def __post_init__(self):
        _choice(self.kind, {"root", "product"}, "construction value reference kind")
        _text(self.id, "Construction value identity")
        self._check_resources()


@dataclass(frozen=True)
class ValueSelection(_MoleculeRecord):
    """An explicit whole value (path=None), or an exact ordered coordinate path."""

    value: ValueRef
    path: CoordinatePath | None = None
    schema_version: ClassVar[str] = "biocompiler.construction_value_selection.v0.1"
    _decoders: ClassVar[dict] = {
        "value": ValueRef.from_dict,
        "path": _optional(CoordinatePath),
    }

    def __post_init__(self):
        require(
            isinstance(self.value, ValueRef),
            "Expected a typed construction value reference.",
        )
        require(
            self.path is None or isinstance(self.path, CoordinatePath),
            "Expected an exact selection path or explicit whole value.",
        )
        self._check_resources()


@dataclass(frozen=True)
class ProductPort(_MoleculeRecord):
    """Declared product metadata without an expected sequence, length or hash."""

    id: str
    space_id: str
    alphabet: str
    topology: str
    chemistry_transition: ChemistryTransition
    feature_transition: FeatureTransition
    schema_version: ClassVar[str] = "biocompiler.construction_product_port.v0.1"
    _decoders: ClassVar[dict] = {
        "chemistry_transition": ChemistryTransition.from_dict,
        "feature_transition": FeatureTransition.from_dict,
    }

    def __post_init__(self):
        _text(self.id, "Construction product identity")
        _text(self.space_id, "Product coordinate-space identity")
        _choice(
            self.alphabet, set(CANONICAL_ALPHABETS), "construction product alphabet"
        )
        _choice(self.topology, {"linear", "circular"}, "construction product topology")
        require(
            isinstance(self.chemistry_transition, ChemistryTransition),
            "Expected explicit product chemistry transition authority.",
        )
        require(
            isinstance(self.feature_transition, FeatureTransition),
            "Expected explicit product feature transition authority.",
        )
        self._check_resources()


@dataclass(frozen=True)
class SliceOperation(_MoleculeRecord):
    input: ValueSelection
    schema_version: ClassVar[str] = "biocompiler.construction_slice.v0.1"
    _decoders: ClassVar[dict] = {"input": ValueSelection.from_dict}

    def __post_init__(self):
        require(
            isinstance(self.input, ValueSelection),
            "Slice requires a typed value selection.",
        )
        self._check_resources()


@dataclass(frozen=True)
class ConcatenateOperation(_MoleculeRecord):
    inputs: tuple[ValueSelection, ...]
    schema_version: ClassVar[str] = "biocompiler.construction_concatenate.v0.1"
    _decoders: ClassVar[dict] = {
        "inputs": _decode_records(ValueSelection, MAX_SELECTIONS)
    }

    def __post_init__(self):
        require(
            isinstance(self.inputs, (tuple, list))
            and 1 <= len(self.inputs) <= MAX_SELECTIONS,
            "Concatenation requires a bounded, nonempty ordered selection inventory.",
        )
        require(
            all(isinstance(item, ValueSelection) for item in self.inputs),
            "Concatenation requires typed selections.",
        )
        object.__setattr__(
            self,
            "inputs",
            tuple(ValueSelection.from_dict(item.to_dict()) for item in self.inputs),
        )
        self._check_resources()


@dataclass(frozen=True)
class OrientationOperation(_MoleculeRecord):
    input: ValueSelection
    action: str
    schema_version: ClassVar[str] = "biocompiler.construction_orientation.v0.1"
    _decoders: ClassVar[dict] = {"input": ValueSelection.from_dict}

    def __post_init__(self):
        require(
            isinstance(self.input, ValueSelection),
            "Orientation requires a typed value selection.",
        )
        _choice(self.action, {"reverse", "reverse_complement"}, "orientation action")
        self._check_resources()


@dataclass(frozen=True)
class TranscriptionOperation(_MoleculeRecord):
    input: ValueSelection
    mapping_profile: str = TRANSCRIPTION_MAPPING_PROFILE
    schema_version: ClassVar[str] = "biocompiler.construction_transcription.v0.1"
    _decoders: ClassVar[dict] = {"input": ValueSelection.from_dict}

    def __post_init__(self):
        require(
            isinstance(self.input, ValueSelection),
            "Transcription requires a typed value selection.",
        )
        require(
            type(self.mapping_profile) is str
            and self.mapping_profile == TRANSCRIPTION_MAPPING_PROFILE,
            "Unsupported explicit transcription mapping profile.",
        )
        self._check_resources()


@dataclass(frozen=True)
class ProcessingProduct(_MoleculeRecord):
    """A named residue path; bounds and complete partition require reconstruction."""

    port_id: str
    path: CoordinatePath
    schema_version: ClassVar[str] = "biocompiler.construction_processing_product.v0.1"
    _decoders: ClassVar[dict] = {"path": CoordinatePath.from_dict}

    def __post_init__(self):
        _text(self.port_id, "Processing product port identity")
        require(
            isinstance(self.path, CoordinatePath),
            "Processing products require exact coordinate paths.",
        )
        self._check_resources()


def _whole_input(value):
    require(
        isinstance(value, ValueSelection), "Expected a typed whole-input selection."
    )
    require(
        value.path is None,
        "This operation requires an explicit whole input; use a prior slice for a selected segment.",
    )


@dataclass(frozen=True)
class _ProcessingOperation(_MoleculeRecord):
    input: ValueSelection
    products: tuple[ProcessingProduct, ...]
    _cleavage: ClassVar[bool] = False
    _decoders: ClassVar[dict] = {
        "input": ValueSelection.from_dict,
        "products": _decode_records(ProcessingProduct, MAX_PROCESSING_PRODUCTS),
    }

    def __post_init__(self):
        _whole_input(self.input)
        object.__setattr__(
            self,
            "products",
            _records(
                self.products,
                ProcessingProduct,
                MAX_PROCESSING_PRODUCTS,
                "processing products",
                key="port_id",
                nonempty=True,
            ),
        )
        for product in self.products:
            require(
                product.path.strand == "+",
                "Processing product paths require forward traversal.",
            )
            require(
                not self._cleavage or len(product.path.spans) == 1,
                "Cleavage products require one contiguous span.",
            )
        self._check_resources()


@dataclass(frozen=True)
class RNACleavageOperation(_ProcessingOperation):
    schema_version: ClassVar[str] = "biocompiler.construction_rna_cleavage.v0.1"
    _cleavage: ClassVar[bool] = True


@dataclass(frozen=True)
class RNASplicingOperation(_ProcessingOperation):
    schema_version: ClassVar[str] = "biocompiler.construction_rna_splicing.v0.1"


@dataclass(frozen=True)
class ProteinCleavageOperation(_ProcessingOperation):
    schema_version: ClassVar[str] = "biocompiler.construction_protein_cleavage.v0.1"
    _cleavage: ClassVar[bool] = True


@dataclass(frozen=True)
class ProteinSplicingOperation(_ProcessingOperation):
    schema_version: ClassVar[str] = "biocompiler.construction_protein_splicing.v0.1"


@dataclass(frozen=True)
class CircularizationOperation(_MoleculeRecord):
    input: ValueSelection
    origin: int
    schema_version: ClassVar[str] = "biocompiler.construction_circularization.v0.1"
    _decoders: ClassVar[dict] = {"input": ValueSelection.from_dict}

    def __post_init__(self):
        _whole_input(self.input)
        require(
            type(self.origin) is int and 0 <= self.origin <= MAX_RESIDUES,
            "Circularization origin must be an explicitly bounded integer.",
        )
        self._check_resources()


@dataclass(frozen=True)
class BaseEditingOperation(_MoleculeRecord):
    input: ValueSelection
    canonical_edits: tuple[CanonicalBaseEdit, ...]
    chemical_edits: tuple[ChemicalBaseEdit, ...]
    schema_version: ClassVar[str] = "biocompiler.construction_base_editing.v0.1"
    _decoders: ClassVar[dict] = {
        "input": ValueSelection.from_dict,
        "canonical_edits": _decode_records(CanonicalBaseEdit, MAX_RECODINGS),
        "chemical_edits": _decode_records(ChemicalBaseEdit, MAX_RECODINGS),
    }

    def __post_init__(self):
        _whole_input(self.input)
        require(
            isinstance(self.canonical_edits, (tuple, list))
            and isinstance(self.chemical_edits, (tuple, list)),
            "Editing requires explicit edit inventories.",
        )
        require(
            1 <= len(self.canonical_edits) + len(self.chemical_edits) <= MAX_RECODINGS,
            "Editing requires a bounded, nonempty combined edit inventory.",
        )
        for key, cls in (
            ("canonical_edits", CanonicalBaseEdit),
            ("chemical_edits", ChemicalBaseEdit),
        ):
            object.__setattr__(
                self,
                key,
                _records(getattr(self, key), cls, MAX_RECODINGS, key, key="position"),
            )
        require(
            {edit.position for edit in self.canonical_edits}.isdisjoint(
                edit.position for edit in self.chemical_edits
            ),
            "Canonical and chemical edits cannot overlap at a site.",
        )
        self._check_resources()


def _translation_input(selection, policy):
    require(
        isinstance(selection, ValueSelection),
        "Translation requires an exact typed input selection.",
    )
    require(
        isinstance(policy, TranslationPolicy),
        "Translation requires an explicit typed policy.",
    )


@dataclass(frozen=True)
class TranslationOperation(_MoleculeRecord):
    input: ValueSelection
    policy: TranslationPolicy
    schema_version: ClassVar[str] = "biocompiler.construction_translation.v0.1"
    _decoders: ClassVar[dict] = {
        "input": ValueSelection.from_dict,
        "policy": TranslationPolicy.from_dict,
    }

    def __post_init__(self):
        _translation_input(self.input, self.policy)
        self._check_resources()


@dataclass(frozen=True)
class TranslationProduct(_MoleculeRecord):
    port_id: str
    input: ValueSelection
    policy: TranslationPolicy
    schema_version: ClassVar[str] = "biocompiler.construction_translation_product.v0.1"
    _decoders: ClassVar[dict] = {
        "input": ValueSelection.from_dict,
        "policy": TranslationPolicy.from_dict,
    }

    def __post_init__(self):
        _text(self.port_id, "Translation product port identity")
        _translation_input(self.input, self.policy)
        self._check_resources()


@dataclass(frozen=True)
class MultiORFTranslationOperation(_MoleculeRecord):
    products: tuple[TranslationProduct, ...]
    schema_version: ClassVar[str] = (
        "biocompiler.construction_multi_orf_translation.v0.1"
    )
    _decoders: ClassVar[dict] = {
        "products": _decode_records(TranslationProduct, MAX_TRANSLATION_PRODUCTS)
    }

    def __post_init__(self):
        object.__setattr__(
            self,
            "products",
            _records(
                self.products,
                TranslationProduct,
                MAX_TRANSLATION_PRODUCTS,
                "translation products",
                key="port_id",
                nonempty=True,
            ),
        )
        reference = self.products[0].input.value
        require(
            all(product.input.value == reference for product in self.products),
            "Multi-ORF products must bind the same exact source value.",
        )
        require(
            all(product.input.path is not None for product in self.products),
            "Multi-ORF products require explicit individual ORF paths.",
        )
        self._check_resources()


@dataclass(frozen=True)
class TranslationBranch(_MoleculeRecord):
    """A declared conditional branch, including an explicit no-product outcome."""

    id: str
    condition: str
    input: ValueSelection
    policy: TranslationPolicy | None
    port_id: str | None
    schema_version: ClassVar[str] = "biocompiler.construction_translation_branch.v0.1"
    _decoders: ClassVar[dict] = {
        "input": ValueSelection.from_dict,
        "policy": _optional(TranslationPolicy),
    }

    def __post_init__(self):
        _text(self.id, "Translation branch identity")
        _text(self.condition, "Translation branch condition")
        require(
            isinstance(self.input, ValueSelection),
            "Every translation branch must retain a typed input selection.",
        )
        require(
            (self.policy is None) == (self.port_id is None),
            "Translation branches require both a policy and product port, or neither.",
        )
        if self.policy is not None:
            _translation_input(self.input, self.policy)
            _text(self.port_id, "Translation branch product port identity")
        self._check_resources()


@dataclass(frozen=True)
class ConditionalTranslationOperation(_MoleculeRecord):
    branches: tuple[TranslationBranch, ...]
    schema_version: ClassVar[str] = (
        "biocompiler.construction_conditional_translation.v0.1"
    )
    _decoders: ClassVar[dict] = {
        "branches": _decode_records(TranslationBranch, MAX_TRANSLATION_BRANCHES)
    }

    def __post_init__(self):
        object.__setattr__(
            self,
            "branches",
            _records(
                self.branches,
                TranslationBranch,
                MAX_TRANSLATION_BRANCHES,
                "translation branches",
                nonempty=True,
            ),
        )
        require(
            len({branch.condition for branch in self.branches}) == len(self.branches),
            "Translation branch conditions must be unique.",
        )
        ports = [
            branch.port_id for branch in self.branches if branch.port_id is not None
        ]
        require(
            bool(ports),
            "Conditional translation requires at least one producing branch.",
        )
        require(
            len(set(ports)) == len(ports),
            "Translation branch product port identities must be unique.",
        )
        self._check_resources()


@dataclass(frozen=True)
class PeptideProduct(_MoleculeRecord):
    port_id: str
    residues: IndexSpan
    schema_version: ClassVar[str] = "biocompiler.construction_peptide_product.v0.1"
    _decoders: ClassVar[dict] = {"residues": IndexSpan.from_dict}

    def __post_init__(self):
        _text(self.port_id, "Peptide product port identity")
        require(
            isinstance(self.residues, IndexSpan),
            "Peptide products require exact residue intervals.",
        )
        self._check_resources()


@dataclass(frozen=True)
class RibosomalSkippingOperation(_MoleculeRecord):
    input: ValueSelection
    policy: TranslationPolicy
    products: tuple[PeptideProduct, ...]
    event_id: str
    schema_version: ClassVar[str] = "biocompiler.construction_ribosomal_skipping.v0.1"
    _decoders: ClassVar[dict] = {
        "input": ValueSelection.from_dict,
        "policy": TranslationPolicy.from_dict,
        "products": _decode_records(PeptideProduct, MAX_TRANSLATION_PRODUCTS),
    }

    def __post_init__(self):
        _translation_input(self.input, self.policy)
        object.__setattr__(
            self,
            "products",
            _records(
                self.products,
                PeptideProduct,
                MAX_TRANSLATION_PRODUCTS,
                "skipping peptide products",
                key="port_id",
                nonempty=True,
            ),
        )
        _text(self.event_id, "Declared ribosomal skipping event")
        self._check_resources()


PROCESSING_OPERATION_TYPES = (
    RNACleavageOperation,
    RNASplicingOperation,
    ProteinCleavageOperation,
    ProteinSplicingOperation,
)
OPERATION_TYPES = (
    SliceOperation,
    ConcatenateOperation,
    OrientationOperation,
    TranscriptionOperation,
    *PROCESSING_OPERATION_TYPES,
    CircularizationOperation,
    BaseEditingOperation,
    TranslationOperation,
    MultiORFTranslationOperation,
    ConditionalTranslationOperation,
    RibosomalSkippingOperation,
)
OperationSpec = (
    SliceOperation
    | ConcatenateOperation
    | OrientationOperation
    | TranscriptionOperation
    | RNACleavageOperation
    | RNASplicingOperation
    | ProteinCleavageOperation
    | ProteinSplicingOperation
    | CircularizationOperation
    | BaseEditingOperation
    | TranslationOperation
    | MultiORFTranslationOperation
    | ConditionalTranslationOperation
    | RibosomalSkippingOperation
)


def _operation_from_dict(data):
    from collections.abc import Mapping

    require(isinstance(data, Mapping), "Expected a typed construction operation.")
    cls = next(
        (
            item
            for item in OPERATION_TYPES
            if item.schema_version == data.get("schema_version")
        ),
        None,
    )
    require(cls is not None, "Unsupported construction operation schema.")
    return cls.from_dict(data)


def operation_selections(operation):
    """Read declared operand fields only; no transformation is performed."""
    require(
        isinstance(operation, OPERATION_TYPES), "Expected a supported operation schema."
    )
    if isinstance(operation, ConcatenateOperation):
        return operation.inputs
    if isinstance(operation, MultiORFTranslationOperation):
        selections = tuple(product.input for product in operation.products)
    elif isinstance(operation, ConditionalTranslationOperation):
        selections = tuple(branch.input for branch in operation.branches)
    else:
        return (operation.input,)
    # Repeated selections need one frame resolution; all branch/product records
    # remain authoritative in the operation itself. Concatenation above retains
    # repeated operands because their multiplicity determines output residues.
    return tuple(dict.fromkeys(selections))


def _operation_conditions(operation):
    if isinstance(operation, (TranslationOperation, RibosomalSkippingOperation)):
        policies = (operation.policy,)
    elif isinstance(operation, MultiORFTranslationOperation):
        policies = tuple(product.policy for product in operation.products)
    elif isinstance(operation, ConditionalTranslationOperation):
        policies = tuple(
            branch.policy for branch in operation.branches if branch.policy is not None
        )
    else:
        policies = ()
    conditions = {
        recoding.condition for policy in policies for recoding in policy.recodings
    }
    if isinstance(operation, ConditionalTranslationOperation):
        conditions.update(branch.condition for branch in operation.branches)
    if isinstance(operation, RibosomalSkippingOperation):
        conditions.add(operation.event_id)
    return conditions


@dataclass(frozen=True)
class TransformStep(_MoleculeRecord):
    id: str
    operation: OperationSpec
    ports: tuple[ProductPort, ...]
    assumptions: tuple[str, ...]
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.construction_transform_step.v0.1"
    _decoders: ClassVar[dict] = {
        "operation": _operation_from_dict,
        "ports": _decode_records(ProductPort, MAX_PROCESSING_PRODUCTS),
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        _text(self.id, "Construction step identity")
        require(
            isinstance(self.operation, OPERATION_TYPES),
            "Expected a typed supported operation schema.",
        )
        object.__setattr__(
            self,
            "ports",
            _records(
                self.ports,
                ProductPort,
                MAX_PROCESSING_PRODUCTS,
                "product ports",
                nonempty=True,
            ),
        )
        if isinstance(
            self.operation,
            (
                *PROCESSING_OPERATION_TYPES,
                MultiORFTranslationOperation,
                RibosomalSkippingOperation,
            ),
        ):
            require(
                {product.port_id for product in self.operation.products}
                == {port.id for port in self.ports},
                "Recipe port identities must match exactly the step product ports.",
            )
        elif isinstance(self.operation, ConditionalTranslationOperation):
            require(
                {
                    branch.port_id
                    for branch in self.operation.branches
                    if branch.port_id is not None
                }
                == {port.id for port in self.ports},
                "Producing branch port identities must match exactly the step product ports.",
            )
        else:
            require(
                len(self.ports) == 1,
                "This operation requires exactly one product port.",
            )
        require(
            isinstance(self.assumptions, (tuple, list))
            and len(self.assumptions) <= MAX_ASSUMPTIONS,
            "Invalid construction assumption inventory.",
        )
        for assumption in self.assumptions:
            _text(assumption, "Construction assumption")
        require(
            len(set(self.assumptions)) == len(self.assumptions),
            "Duplicate construction assumptions.",
        )
        object.__setattr__(self, "assumptions", tuple(sorted(self.assumptions)))
        require(
            _operation_conditions(self.operation).issubset(self.assumptions),
            "Every branch condition, recoding condition and skipping event must bind an exact declared assumption.",
        )
        sources = {
            selection.value.id for selection in operation_selections(self.operation)
        }
        for port in self.ports:
            for disposition in (
                *port.chemistry_transition.dispositions,
                *port.feature_transition.dispositions,
            ):
                require(
                    disposition.source_id in sources,
                    "Transition disposition must bind an actual operation input.",
                )
        _provenance(self.provenance)
        self._check_resources()


@dataclass(frozen=True)
class OutputMember(_MoleculeRecord):
    id: str
    value: ValueRef
    space_id: str
    form: str
    sequence_extent: str
    coding_status: str
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.construction_output_member.v0.1"
    _decoders: ClassVar[dict] = {
        "value": ValueRef.from_dict,
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        _text(self.id, "Output member identity", maximum=4080)
        require(
            isinstance(self.value, ValueRef),
            "Expected a resolved-value reference for an output member.",
        )
        _text(self.space_id, "Final output coordinate-space identity")
        _choice(self.form, FORMS, "construction output form")
        _choice(
            self.sequence_extent,
            {"complete", "exact_core"},
            "construction output extent",
        )
        _choice(
            self.coding_status,
            {"coding", "noncoding", "unknown", "inapplicable"},
            "construction coding status",
        )
        _provenance(self.provenance)
        self._check_resources()


@dataclass(frozen=True)
class RoleDeclaration(_MoleculeRecord):
    id: str
    role: str
    purpose: str
    compartment: str
    schema_version: ClassVar[str] = "biocompiler.construction_role_declaration.v0.1"

    def __post_init__(self):
        for key in ("id", "role", "compartment"):
            _text(getattr(self, key), key)
        _choice(
            self.purpose, set(CATEGORY_PURPOSE.values()), "construction role purpose"
        )
        require(
            self.compartment != "abstract",
            "Construction roles require physical compartments.",
        )
        self._check_resources()


@dataclass(frozen=True)
class MemberRequirement(_MoleculeRecord):
    id: str
    category: str
    member_id: str | None
    external_id: str | None
    external_fingerprint: str | None
    roles: tuple[RoleDeclaration, ...]
    schema_version: ClassVar[str] = "biocompiler.construction_member_requirement.v0.1"
    _decoders: ClassVar[dict] = {
        "roles": _decode_records(RoleDeclaration, MAX_ROLE_DECLARATIONS)
    }

    def __post_init__(self):
        _text(self.id, "Required construction member identity")
        _choice(self.category, MEMBER_CATEGORIES, "construction member category")
        materialized = self.member_id is not None
        if materialized:
            _text(self.member_id, "Required output member reference")
            require(
                self.external_id is None and self.external_fingerprint is None,
                "A materialized member cannot also declare an external subject.",
            )
        else:
            _text(self.external_id, "External provider identity")
            _hash(self.external_fingerprint, "Complete external provider authority")
            require(
                self.category not in {"payload", "delivered_helper", "encoded_product"},
                "Payloads, delivered helpers and encoded products require materialized members.",
            )
        object.__setattr__(
            self,
            "roles",
            _records(
                self.roles,
                RoleDeclaration,
                MAX_ROLE_DECLARATIONS,
                "member role declarations",
                nonempty=True,
            ),
        )
        require(
            all(role.purpose == CATEGORY_PURPOSE[self.category] for role in self.roles),
            "Member category and declared role purpose disagree.",
        )
        self._check_resources()


@dataclass(frozen=True)
class ComplexMemberConstituent(_MoleculeRecord):
    member_id: str
    stoichiometry: int | None
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.construction_complex_constituent.v0.1"
    _decoders: ClassVar[dict] = {"provenance": DeclarationProvenance.from_dict}

    def __post_init__(self):
        _text(self.member_id, "Complex covalent member identity")
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
class ComplexMemberPlan(_MoleculeRecord):
    id: str
    kind: str
    constituents: tuple[ComplexMemberConstituent, ...]
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.construction_complex_member.v0.1"
    _decoders: ClassVar[dict] = {
        "constituents": _decode_records(ComplexMemberConstituent, MAX_OUTPUT_MEMBERS),
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        _text(self.id, "Complex member identity")
        _choice(
            self.kind,
            {"protein_complex", "dna_duplex", "rna_complex"},
            "complex member kind",
        )
        object.__setattr__(
            self,
            "constituents",
            _records(
                self.constituents,
                ComplexMemberConstituent,
                MAX_OUTPUT_MEMBERS,
                "complex member constituents",
                key="member_id",
                nonempty=True,
            ),
        )
        if all(item.stoichiometry is not None for item in self.constituents):
            require(
                sum(item.stoichiometry for item in self.constituents) >= 2,
                "A noncovalent complex requires at least two constituent copies.",
            )
        if self.kind == "dna_duplex":
            require(
                len(self.constituents) == 2
                and all(item.stoichiometry == 1 for item in self.constituents),
                "A DNA duplex plan requires two explicit single-copy covalent strand members.",
            )
        _provenance(self.provenance)
        self._check_resources()


@dataclass(frozen=True)
class AmountDeclaration(_MoleculeRecord):
    """An explicit amount without a generated subject fingerprint or inferred dose."""

    id: str
    subject_id: str
    preparation_id: str
    role_instance_ids: tuple[str, ...]
    quantity: int | float | None
    unit: str
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.construction_amount_declaration.v0.1"
    _decoders: ClassVar[dict] = {"provenance": DeclarationProvenance.from_dict}

    def __post_init__(self):
        for key in ("id", "subject_id", "preparation_id", "unit"):
            _text(getattr(self, key), key)
        require(
            isinstance(self.role_instance_ids, (tuple, list))
            and len(self.role_instance_ids) <= MAX_ROLE_DECLARATIONS,
            "Invalid amount role inventory.",
        )
        for identity in self.role_instance_ids:
            _text(identity, "Amount role identity")
        require(
            len(set(self.role_instance_ids)) == len(self.role_instance_ids),
            "Duplicate amount role identity.",
        )
        object.__setattr__(
            self, "role_instance_ids", tuple(sorted(self.role_instance_ids))
        )
        require(
            self.quantity is None or type(self.quantity) in (int, float),
            "Amount requires a numeric declaration or explicit unknown.",
        )
        if type(self.quantity) is int:
            require(
                self.quantity.bit_length() <= 1024, "Amount integer limit exceeded."
            )
        if self.quantity is not None:
            require(
                self.quantity >= 0
                and (type(self.quantity) is int or math.isfinite(self.quantity)),
                "Amount must be finite and nonnegative.",
            )
        _provenance(self.provenance)
        self._check_resources()


def _register_frame(frames, frame):
    previous = frames.get(frame.id)
    require(
        previous is None or previous.fingerprint == frame.fingerprint,
        "Conflicting source coordinate-space authority.",
    )
    frames[frame.id] = frame


def _resolve_ref(reference, available):
    entry = available.get(reference.id)
    require(
        entry is not None and entry[0] == reference.kind,
        "Missing, forward or wrong-kind construction value reference.",
    )
    return entry[1]


@dataclass(frozen=True)
class CircuitConstructionRequest(_MoleculeRecord):
    id: str
    circuit: CircuitRequest
    sources: tuple[RootSource, ...]
    steps: tuple[TransformStep, ...]
    output_members: tuple[OutputMember, ...]
    requirements: tuple[MemberRequirement, ...]
    mode: str
    complex_members: tuple[ComplexMemberPlan, ...] = ()
    amounts: tuple[AmountDeclaration, ...] = ()
    payload_structures: tuple[PayloadStructureContract, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.circuit_construction_request.v0.1"
    _decoders: ClassVar[dict] = {
        "circuit": CircuitRequest.from_dict,
        "sources": _decode_records(RootSource, MAX_SOURCES),
        "steps": _decode_records(TransformStep, MAX_STEPS),
        "output_members": _decode_records(OutputMember, MAX_OUTPUT_MEMBERS),
        "requirements": _decode_records(MemberRequirement, MAX_MEMBER_REQUIREMENTS),
        "complex_members": _decode_records(ComplexMemberPlan, MAX_COMPLEX_MEMBERS),
        "amounts": _decode_records(AmountDeclaration, MAX_AMOUNT_DECLARATIONS),
        "payload_structures": _decode_records(
            PayloadStructureContract, MAX_PAYLOAD_CONTRACTS
        ),
    }

    def __post_init__(self):
        _text(self.id, "Circuit construction identity", maximum=4080)
        require(
            isinstance(self.circuit, CircuitRequest),
            "Construction requires the complete circuit request.",
        )
        object.__setattr__(
            self, "circuit", CircuitRequest.from_dict(self.circuit.to_dict())
        )
        _choice(self.mode, {"strict", "diagnostic"}, "construction mode")
        for key, cls, maximum in (
            ("sources", RootSource, MAX_SOURCES),
            ("output_members", OutputMember, MAX_OUTPUT_MEMBERS),
            ("requirements", MemberRequirement, MAX_MEMBER_REQUIREMENTS),
        ):
            object.__setattr__(
                self,
                key,
                _records(getattr(self, key), cls, maximum, key, nonempty=True),
            )
        for key, cls, maximum in (
            ("complex_members", ComplexMemberPlan, MAX_COMPLEX_MEMBERS),
            ("amounts", AmountDeclaration, MAX_AMOUNT_DECLARATIONS),
        ):
            object.__setattr__(
                self, key, _records(getattr(self, key), cls, maximum, key)
            )
        object.__setattr__(
            self,
            "payload_structures",
            _records(
                self.payload_structures,
                PayloadStructureContract,
                MAX_PAYLOAD_CONTRACTS,
                "payload structure contracts",
                key="member_id",
            ),
        )
        require(
            isinstance(self.steps, (tuple, list)) and len(self.steps) <= MAX_STEPS,
            "Invalid ordered construction step inventory.",
        )
        require(
            all(isinstance(step, TransformStep) for step in self.steps),
            "Expected typed construction steps.",
        )
        steps = tuple(TransformStep.from_dict(step.to_dict()) for step in self.steps)
        require(
            len({step.id for step in steps}) == len(steps),
            "Duplicate construction step identities.",
        )
        object.__setattr__(self, "steps", steps)
        require(
            sum(len(source.molecule.sequence) for source in self.sources)
            <= MAX_TOTAL_SOURCE_RESIDUES,
            "Total supplied source residue limit exceeded.",
        )
        require(
            sum(len(step.ports) for step in steps) <= MAX_PRODUCTS,
            "Construction product inventory limit exceeded.",
        )
        frames, available = {}, {}
        root_frames = set()
        for source in self.sources:
            require(
                source.molecule.space.id not in root_frames,
                "Root molecules require distinct destination coordinate-space identities.",
            )
            root_frames.add(source.molecule.space.id)
            _register_frame(frames, source.molecule.space)
            for origin in source.molecule.assembly:
                _register_frame(frames, origin.source_space)
            available[source.id] = ("root", source.molecule.space)
        reserved_frames = set(frames)
        for step in steps:
            for selection in operation_selections(step.operation):
                frame = _resolve_ref(selection.value, available)
                if selection.path is not None:
                    identity = (
                        frame.id if selection.value.kind == "root" else frame.space_id
                    )
                    require(
                        selection.path.space_id == identity,
                        "Selection path names a different source or product frame.",
                    )
                    if selection.value.kind == "root":
                        selection.path.validate_for(frame)
            if isinstance(step.operation, PROCESSING_OPERATION_TYPES):
                frame = _resolve_ref(step.operation.input.value, available)
                identity = (
                    frame.id
                    if step.operation.input.value.kind == "root"
                    else frame.space_id
                )
                require(
                    all(
                        product.path.space_id == identity
                        for product in step.operation.products
                    ),
                    "Processing product paths must name the whole bound input frame.",
                )
            for port in step.ports:
                require(
                    port.id not in available,
                    "Root and product value identities must be globally unique.",
                )
                require(
                    port.space_id not in reserved_frames,
                    "Product frames must be new, uniquely reserved coordinate identities.",
                )
                reserved_frames.add(port.space_id)
                available[port.id] = ("product", port)
        members = {member.id: member for member in self.output_members}
        complexes = {member.id: member for member in self.complex_members}
        require(
            not members.keys() & complexes.keys(),
            "Covalent and complex members require distinct identities.",
        )
        for complex_ in self.complex_members:
            require(
                all(
                    constituent.member_id in members
                    for constituent in complex_.constituents
                ),
                "Complex constituents must reference final covalent output members only.",
            )
        subjects = members | complexes
        for member in self.output_members:
            _resolve_ref(member.value, available)
            require(
                member.space_id not in reserved_frames,
                "Final output frames must be new, uniquely reserved coordinate identities.",
            )
            reserved_frames.add(member.space_id)
        demanded_products = {
            member.value.id
            for member in self.output_members
            if member.value.kind == "product"
        }
        for step in reversed(steps):
            require(
                all(port.id in demanded_products for port in step.ports),
                "Every executable product port must contribute to an output member.",
            )
            demanded_products.update(
                selection.value.id
                for selection in operation_selections(step.operation)
                if selection.value.kind == "product"
            )
        covered, role_ids, role_subjects = set(), set(), {}
        providers = tuple(
            provider
            for requirement in self.circuit.requirements
            for provider in requirement.behavior.dependencies
        )
        total_roles = 0
        for requirement in self.requirements:
            if requirement.member_id is not None:
                require(
                    requirement.member_id in subjects,
                    "Required member refers to an absent output member.",
                )
                covered.add(requirement.member_id)
            else:
                provider = next(
                    (
                        provider
                        for provider in providers
                        if provider.id == requirement.external_id
                        and provider.fingerprint == requirement.external_fingerprint
                    ),
                    None,
                )
                require(
                    provider is not None,
                    "External requirement must retain a complete original provider identity.",
                )
                expected_kind = {
                    "host_provider": "host",
                    "experimental_input": "external_input",
                }.get(requirement.category)
                require(
                    expected_kind is None or provider.kind == expected_kind,
                    "External member category must retain the original provider kind.",
                )
                require(
                    all(
                        role.compartment == provider.compartment
                        for role in requirement.roles
                    ),
                    "External roles must retain the original provider compartment.",
                )
            for role in requirement.roles:
                require(
                    role.id not in role_ids,
                    "Role declaration IDs must be globally unique.",
                )
                role_ids.add(role.id)
                role_subjects[role.id] = requirement.member_id
                total_roles += 1
                require(
                    total_roles <= MAX_ROLE_DECLARATIONS,
                    "Construction role inventory limit exceeded.",
                )
                if self.circuit.profile.target is not None:
                    require(
                        role.compartment in self.circuit.profile.target.compartments,
                        "Construction roles must retain declared target compartments.",
                    )
        require(
            covered == set(subjects),
            "Every output member and complex must have an explicit required-member disposition.",
        )
        require(
            any(requirement.category == "payload" for requirement in self.requirements),
            "Construction requires an explicit payload member.",
        )
        preparations = set()
        for amount in self.amounts:
            require(
                amount.subject_id in subjects,
                "Amount must reference a final covalent or complex member.",
            )
            require(
                all(
                    role_subjects.get(identity) == amount.subject_id
                    for identity in amount.role_instance_ids
                ),
                "Amount role must refer to the same exact declared subject.",
            )
            key = (amount.preparation_id, amount.subject_id)
            require(
                key not in preparations,
                "A subject/preparation amount must be declared once with all shared roles.",
            )
            preparations.add(key)
        self._check_resources()

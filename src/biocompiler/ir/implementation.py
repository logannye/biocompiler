"""Bounded supplied-sequence precursor architectures, not biological guarantees.

The current family describes one RNA encoding a declared secreted precursor.
Its cleavage relationship and host providers are explicit design assumptions.
They do not establish physical secretion, processing, regulation or human use.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar

from biocompiler.ir.implementation_requirements import source_request_from_dict
from biocompiler.ir.component_contracts import DependencyRequirement, PinnedIdentity
from biocompiler.ir.composition import Provider
from biocompiler.ir.molecular_design import _Record, _decode_records, _records
from biocompiler.ir.payload import PayloadFeature, hash_value, name, names
from biocompiler.ir.serialization import require
from biocompiler.compiler.request import BuildRequest
from biocompiler.semantics.context import TargetContext
from biocompiler.semantics.coordinates import SequenceRange

PROFILE_VERSION = "biocompiler.secreted_precursor_structure.v0.1"
MAX_ARCHITECTURES = 32
MAX_SEQUENCE_BASES = 100_000
DEPENDENCY_COMPARTMENTS = MappingProxyType(
    {
        "host_translation": "cytoplasm",
        "secretory_translocation": "secretory_pathway",
        "precursor_processing": "secretory_pathway",
        "secretion_transport": "secretory_pathway",
    }
)
PLAN_ROLES = (
    ("translation", "encoded_coding_region", "cytoplasm"),
    ("precursor", "encoded_precursor", "secretory_pathway"),
    ("processing", "declared_precursor_processing", "secretory_pathway"),
    ("product", "declared_mature_product", "secretory_pathway"),
    ("export", "declared_extracellular_destination", "extracellular"),
)
PLAN_EDGES = (
    ("translation", "precursor", "encodes"),
    ("precursor", "processing", "declared_processing_input"),
    ("processing", "product", "declared_processing_output"),
    ("product", "export", "requires_transport"),
)


def _protein(value, *, stop=False):
    require(isinstance(value, str) and bool(value), "Expected protein spelling.")
    residues = value[:-1] if stop else value
    require(
        bool(residues)
        and set(residues) <= set("ACDEFGHIKLMNPQRSTVWY")
        and (not stop or value.endswith("*")),
        "Invalid protein spelling.",
    )


def _unique(items, label):
    require(len({item.id for item in items}) == len(items), f"Duplicate {label} IDs.")


@dataclass(frozen=True)
class SequenceAuthority(_Record):
    """Exact supplied RNA and declared provenance; no implicit source review."""

    id: str
    sequence: str
    sequence_sha256: str
    source_locator: str
    provenance: str = "supplied_sequence"
    reference: PinnedIdentity | None = None
    alphabet: str = "RNA"
    schema_version: ClassVar[str] = "biocompiler.sequence_authority.v0.1"
    _decoders: ClassVar[dict] = {
        "reference": lambda value: (
            PinnedIdentity.from_dict(value) if value is not None else None
        ),
    }

    def __post_init__(self):
        name(self.id, "Sequence authority id")
        name(self.source_locator, "Sequence source locator")
        hash_value(self.sequence_sha256, "Sequence authority")
        require(
            self.alphabet == "RNA", "This implementation family requires explicit RNA."
        )
        require(
            isinstance(self.sequence, str)
            and 0 < len(self.sequence) <= MAX_SEQUENCE_BASES
            and set(self.sequence) <= set("ACGU"),
            "Invalid canonical supplied RNA.",
        )
        require(
            self.provenance
            in {"software_fixture", "supplied_sequence", "supplied_reference"},
            "Unsupported sequence provenance; supplied references are not promoted.",
        )
        if self.provenance == "supplied_reference":
            require(
                isinstance(self.reference, PinnedIdentity)
                and self.reference.kind == "reference",
                "A supplied reference requires its declared source-record identity.",
            )
        else:
            require(
                self.reference is None,
                "Reference metadata requires supplied_reference provenance.",
            )


@dataclass(frozen=True)
class CodingSegment(_Record):
    id: str
    kind: str
    sequence: SequenceAuthority
    protein_sequence: str
    schema_version: ClassVar[str] = "biocompiler.coding_segment.v0.1"
    _decoders: ClassVar[dict] = {"sequence": SequenceAuthority.from_dict}

    def __post_init__(self):
        name(self.id, "Coding segment id")
        require(
            self.kind
            in {"signal_peptide", "junction", "mature_product", "terminal_stop"},
            "Unsupported precursor segment kind.",
        )
        require(
            isinstance(self.sequence, SequenceAuthority),
            "Expected supplied sequence authority.",
        )
        if self.kind == "terminal_stop":
            require(
                self.protein_sequence == "*",
                "Stop segment requires exactly a stop expectation.",
            )
        else:
            _protein(self.protein_sequence)


@dataclass(frozen=True)
class CodingJunction(_Record):
    left_segment_id: str
    right_segment_id: str
    policy: str = "concatenate_in_frame"
    schema_version: ClassVar[str] = "biocompiler.coding_junction.v0.1"

    def __post_init__(self):
        name(self.left_segment_id, "Junction left segment")
        name(self.right_segment_id, "Junction right segment")
        require(
            self.left_segment_id != self.right_segment_id
            and self.policy == "concatenate_in_frame",
            "Unsupported coding junction.",
        )


@dataclass(frozen=True)
class ImplementationDependencyBinding(_Record):
    dependency_id: str
    provider_id: str | None
    schema_version: ClassVar[str] = "biocompiler.implementation_dependency_binding.v0.1"

    def __post_init__(self):
        name(self.dependency_id, "Dependency id")
        if self.provider_id is not None:
            name(self.provider_id, "Provider id")


@dataclass(frozen=True)
class SecretedRNAArchitecture(_Record):
    id: str
    version: str
    product: str
    target_fingerprint: str
    five_prime_utr: SequenceAuthority
    three_prime_utr: SequenceAuthority
    segments: tuple[CodingSegment, ...]
    junctions: tuple[CodingJunction, ...]
    precursor_protein: str
    mature_protein: str
    cleavage_after_aa: int
    dependencies: tuple[DependencyRequirement, ...]
    dependency_bindings: tuple[ImplementationDependencyBinding, ...]
    features: tuple[PayloadFeature, ...]
    poly_a: SequenceAuthority | None = None
    family: str = PROFILE_VERSION
    schema_version: ClassVar[str] = "biocompiler.secreted_rna_architecture.v0.1"
    _decoders: ClassVar[dict] = {
        "five_prime_utr": SequenceAuthority.from_dict,
        "three_prime_utr": SequenceAuthority.from_dict,
        "poly_a": lambda value: (
            SequenceAuthority.from_dict(value) if value is not None else None
        ),
        "segments": lambda value: _decode_records(value, CodingSegment),
        "junctions": lambda value: _decode_records(value, CodingJunction),
        "dependencies": lambda value: _decode_records(value, DependencyRequirement),
        "dependency_bindings": lambda value: _decode_records(
            value, ImplementationDependencyBinding
        ),
        "features": lambda value: _decode_records(value, PayloadFeature),
    }

    def __post_init__(self):
        for key in ("id", "version", "product"):
            name(getattr(self, key), key)
        hash_value(self.target_fingerprint, "Architecture intended target")
        require(self.family == PROFILE_VERSION, "Unsupported implementation family.")
        require(
            isinstance(self.five_prime_utr, SequenceAuthority)
            and isinstance(self.three_prime_utr, SequenceAuthority)
            and (self.poly_a is None or isinstance(self.poly_a, SequenceAuthority)),
            "Expected exact UTR/tail sequence authority.",
        )
        for key, cls in (
            ("segments", CodingSegment),
            ("junctions", CodingJunction),
            ("dependencies", DependencyRequirement),
            ("dependency_bindings", ImplementationDependencyBinding),
            ("features", PayloadFeature),
        ):
            object.__setattr__(self, key, _records(getattr(self, key), cls, key))
        _unique(self.segments, "segment")
        require(
            tuple(item.kind for item in self.segments)
            in (
                ("signal_peptide", "mature_product", "terminal_stop"),
                ("signal_peptide", "junction", "mature_product", "terminal_stop"),
            ),
            "Require one signal prefix, optional explicit junction, mature product and terminal stop.",
        )
        require(
            tuple((x.left_segment_id, x.right_segment_id) for x in self.junctions)
            == tuple((a.id, b.id) for a, b in zip(self.segments, self.segments[1:])),
            "Every adjacent coding-segment junction must be supplied explicitly in order.",
        )
        _protein(self.precursor_protein, stop=True)
        _protein(self.mature_protein)
        require(
            type(self.cleavage_after_aa) is int and self.cleavage_after_aa > 0,
            "Declare the precursor cleavage boundary in amino acids.",
        )
        _unique(self.dependencies, "dependency")
        require(
            {x.capability for x in self.dependencies} == set(DEPENDENCY_COMPARTMENTS)
            and len(self.dependencies) == len(DEPENDENCY_COMPARTMENTS),
            "The family must retain every translation/processing/transport dependency.",
        )
        require(
            {x.dependency_id for x in self.dependency_bindings}
            == {x.id for x in self.dependencies}
            and len(self.dependency_bindings) == len(self.dependencies),
            "Every dependency needs exactly one explicit binding or unresolved entry.",
        )
        require(
            len({x.feature for x in self.features}) == len(self.features),
            "Duplicate chemistry features.",
        )
        authorities = self.authorities
        by_id = {}
        for authority in authorities:
            require(
                authority.id not in by_id or by_id[authority.id] == authority,
                "One sequence authority ID cannot denote different records.",
            )
            by_id[authority.id] = authority
        require(
            sum(len(x.sequence) for x in authorities) <= MAX_SEQUENCE_BASES,
            "Assembled architecture exceeds the bounded sequence inventory.",
        )

    @property
    def authorities(self):
        return (
            self.five_prime_utr,
            *(x.sequence for x in self.segments),
            self.three_prime_utr,
            *((self.poly_a,) if self.poly_a else ()),
        )


@dataclass(frozen=True)
class ImplementationLibrary(_Record):
    """Exact product identities retain one mature peptide across architectures.

    A different mature product variant requires a different product identity.
    This consistency rule establishes no biological equivalence or function.
    """

    id: str
    version: str
    architectures: tuple[SecretedRNAArchitecture, ...]
    providers: tuple[Provider, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.implementation_library.v0.1"
    _decoders: ClassVar[dict] = {
        "architectures": lambda value: _decode_records(value, SecretedRNAArchitecture),
        "providers": lambda value: _decode_records(value, Provider),
    }

    def __post_init__(self):
        name(self.id, "Implementation library id")
        name(self.version, "Implementation library version")
        for key, cls in (
            ("architectures", SecretedRNAArchitecture),
            ("providers", Provider),
        ):
            object.__setattr__(self, key, _records(getattr(self, key), cls, key))
            _unique(getattr(self, key), key)
        require(
            len(self.architectures) <= MAX_ARCHITECTURES and len(self.providers) <= 32,
            "Implementation library exceeds the fixed bounded inventory.",
        )
        authorities, products = {}, {}
        for architecture in self.architectures:
            require(
                architecture.product not in products
                or products[architecture.product] == architecture.mature_protein,
                "One product identity must retain the same mature protein; name variants distinctly.",
            )
            products[architecture.product] = architecture.mature_protein
            for authority in architecture.authorities:
                require(
                    authority.id not in authorities
                    or authorities[authority.id] == authority,
                    "A library sequence authority ID cannot denote conflicting records.",
                )
                authorities[authority.id] = authority


@dataclass(frozen=True)
class ImplementationConstraints(_Record):
    allowed_architecture_ids: tuple[str, ...] = ()
    max_length: int | None = None
    preference: str = "shortest"
    require_implementation_complete: bool = False
    schema_version: ClassVar[str] = "biocompiler.implementation_constraints.v0.1"

    def __post_init__(self):
        object.__setattr__(
            self,
            "allowed_architecture_ids",
            names(self.allowed_architecture_ids, "Allowed architectures"),
        )
        require(
            self.max_length is None
            or type(self.max_length) is int
            and self.max_length >= 0,
            "Maximum length must be a nonnegative integer or null.",
        )
        require(
            self.preference in {"shortest", "lexical"},
            "Unsupported selection preference.",
        )
        require(
            type(self.require_implementation_complete) is bool,
            "Implementation completeness mode must be Boolean.",
        )


@dataclass(frozen=True)
class ImplementationRequest(_Record):
    source: object
    library: ImplementationLibrary
    constraints: ImplementationConstraints = ImplementationConstraints()
    schema_version: ClassVar[str] = "biocompiler.implementation_request.v0.1"
    _derived: ClassVar[tuple[str, ...]] = ("nodes",)
    _decoders: ClassVar[dict] = {
        "source": source_request_from_dict,
        "library": ImplementationLibrary.from_dict,
        "constraints": ImplementationConstraints.from_dict,
    }

    def __post_init__(self):
        require(
            hasattr(self.source, "to_dict"), "Expected frozen original source request."
        )
        object.__setattr__(
            self, "source", source_request_from_dict(self.source.to_dict())
        )
        require(
            isinstance(self.library, ImplementationLibrary)
            and isinstance(self.constraints, ImplementationConstraints),
            "Expected a typed library and implementation constraints.",
        )
        require(
            isinstance(self.target, TargetContext),
            "Implementation requests require an explicit original target.",
        )
        require(
            not self.build_request.implementation_constraints
            and not self.build_request.preferences,
            "Source implementation constraints/preferences cannot be ignored; use explicit ImplementationConstraints.",
        )
        require(
            set(self.constraints.allowed_architecture_ids)
            <= {x.id for x in self.library.architectures},
            "Allowed architecture IDs must resolve in the frozen library.",
        )

    @property
    def build_request(self):
        return (
            self.source
            if isinstance(self.source, BuildRequest)
            else self.source.build_request
        )

    @property
    def target(self):
        return self.build_request.target

    @property
    def nodes(self):
        return tuple(node.to_dict() for node in self.build_request.intent.nodes)


@dataclass(frozen=True)
class ImplementationRejection(_Record):
    code: str
    message: str
    status: str = "fail"
    schema_version: ClassVar[str] = "biocompiler.implementation_rejection.v0.1"

    def __post_init__(self):
        name(self.code, "Rejection code")
        name(self.message, "Rejection message")
        require(
            self.status in {"fail", "unsupported", "unknown"},
            "Invalid rejection status.",
        )


@dataclass(frozen=True)
class ImplementationAlternative(_Record):
    architecture_id: str
    architecture_fingerprint: str
    length_nt: int
    rejections: tuple[ImplementationRejection, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.implementation_alternative.v0.1"
    _decoders: ClassVar[dict] = {
        "rejections": lambda value: _decode_records(value, ImplementationRejection)
    }

    def __post_init__(self):
        name(self.architecture_id, "Alternative architecture")
        hash_value(self.architecture_fingerprint, "Alternative architecture")
        require(
            type(self.length_nt) is int and self.length_nt > 0,
            "Invalid alternative length.",
        )
        object.__setattr__(
            self,
            "rejections",
            _records(self.rejections, ImplementationRejection, "rejections"),
        )

    @property
    def eligible(self):
        return not self.rejections


@dataclass(frozen=True)
class ImplementationSelection(_Record):
    request_fingerprint: str
    requirements_fingerprint: str
    alternatives: tuple[ImplementationAlternative, ...]
    selected_architecture_id: str | None
    diagnostics: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.implementation_selection.v0.1"
    _decoders: ClassVar[dict] = {
        "alternatives": lambda value: _decode_records(value, ImplementationAlternative)
    }

    def __post_init__(self):
        hash_value(self.request_fingerprint, "Selection request")
        hash_value(self.requirements_fingerprint, "Selection requirements")
        object.__setattr__(
            self,
            "alternatives",
            _records(self.alternatives, ImplementationAlternative, "alternatives"),
        )
        ids = tuple(x.architecture_id for x in self.alternatives)
        require(
            ids == tuple(sorted(set(ids))) and len(ids) <= MAX_ARCHITECTURES,
            "Alternatives must be unique and sorted within the fixed bound.",
        )
        object.__setattr__(
            self, "diagnostics", names(self.diagnostics, "Selection diagnostics")
        )
        if self.selected_architecture_id is not None:
            require(
                any(
                    x.architecture_id == self.selected_architecture_id and x.eligible
                    for x in self.alternatives
                ),
                "Selected alternative must be eligible.",
            )


@dataclass(frozen=True)
class ImplementationRole(_Record):
    id: str
    kind: str
    compartment: str
    requirement_ids: tuple[str, ...]
    segment_ids: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.implementation_role.v0.1"

    def __post_init__(self):
        require(
            (self.id, self.kind, self.compartment) in PLAN_ROLES,
            "Unsupported implementation role.",
        )
        for key in ("requirement_ids", "segment_ids"):
            object.__setattr__(self, key, names(getattr(self, key), key))


@dataclass(frozen=True)
class ImplementationEdge(_Record):
    source_role_id: str
    destination_role_id: str
    relationship: str
    schema_version: ClassVar[str] = "biocompiler.implementation_edge.v0.1"

    def __post_init__(self):
        require(
            (self.source_role_id, self.destination_role_id, self.relationship)
            in PLAN_EDGES,
            "Unsupported causal design relationship.",
        )


@dataclass(frozen=True)
class ImplementationDependency(_Record):
    requirement: DependencyRequirement
    provider: Provider | None
    functional_support: str = "unestablished"
    schema_version: ClassVar[str] = "biocompiler.implementation_dependency.v0.1"
    _decoders: ClassVar[dict] = {
        "requirement": DependencyRequirement.from_dict,
        "provider": lambda value: (
            Provider.from_dict(value) if value is not None else None
        ),
    }

    def __post_init__(self):
        require(
            isinstance(self.requirement, DependencyRequirement)
            and (self.provider is None or isinstance(self.provider, Provider)),
            "Invalid dependency inventory.",
        )
        require(
            self.functional_support == "unestablished",
            "Provider declarations cannot establish function.",
        )


@dataclass(frozen=True)
class ImplementationPlan(_Record):
    request_fingerprint: str
    requirements_fingerprint: str
    selection_fingerprint: str
    architecture_id: str
    architecture_fingerprint: str
    product_requirement_id: str
    source_ids: tuple[str, ...]
    roles: tuple[ImplementationRole, ...]
    edges: tuple[ImplementationEdge, ...]
    dependencies: tuple[ImplementationDependency, ...]
    unresolved_obligation_ids: tuple[str, ...]
    schema_version: ClassVar[str] = "biocompiler.implementation_plan.v0.1"
    _decoders: ClassVar[dict] = {
        "roles": lambda value: _decode_records(value, ImplementationRole),
        "edges": lambda value: _decode_records(value, ImplementationEdge),
        "dependencies": lambda value: _decode_records(value, ImplementationDependency),
    }

    def __post_init__(self):
        for key in (
            "request_fingerprint",
            "requirements_fingerprint",
            "selection_fingerprint",
            "architecture_fingerprint",
        ):
            hash_value(getattr(self, key), key)
        name(self.architecture_id, "Plan architecture")
        name(self.product_requirement_id, "Product requirement")
        for key in ("source_ids", "unresolved_obligation_ids"):
            object.__setattr__(self, key, names(getattr(self, key), key))
        for key, cls in (
            ("roles", ImplementationRole),
            ("edges", ImplementationEdge),
            ("dependencies", ImplementationDependency),
        ):
            object.__setattr__(self, key, _records(getattr(self, key), cls, key))


@dataclass(frozen=True)
class ImplementationPlacement(_Record):
    id: str
    kind: str
    authority_id: str
    authority_fingerprint: str
    source_range: SequenceRange
    molecule_range: SequenceRange
    protein_range: SequenceRange | None
    requirement_ids: tuple[str, ...]
    role_id: str
    schema_version: ClassVar[str] = "biocompiler.implementation_placement.v0.1"
    _decoders: ClassVar[dict] = {
        "source_range": SequenceRange.from_dict,
        "molecule_range": SequenceRange.from_dict,
        "protein_range": lambda value: (
            SequenceRange.from_dict(value) if value is not None else None
        ),
    }

    def __post_init__(self):
        for key in ("id", "kind", "authority_id", "role_id"):
            name(getattr(self, key), key)
        hash_value(self.authority_fingerprint, "Placement authority")
        require(
            isinstance(self.source_range, SequenceRange)
            and isinstance(self.molecule_range, SequenceRange)
            and (
                self.protein_range is None
                or isinstance(self.protein_range, SequenceRange)
            ),
            "Invalid encoding coordinates.",
        )
        object.__setattr__(
            self,
            "requirement_ids",
            names(self.requirement_ids, "Encoding requirements"),
        )


@dataclass(frozen=True)
class ImplementationConstruct(_Record):
    request_fingerprint: str
    requirements_fingerprint: str
    plan_fingerprint: str
    architecture_id: str
    molecule_id: str
    placements: tuple[ImplementationPlacement, ...]
    precursor_protein: str
    mature_protein: str
    cleavage_after_aa: int
    cleavage_after_nt: int
    junction_coordinates: tuple[int, ...]
    features: tuple[PayloadFeature, ...]
    schema_version: ClassVar[str] = "biocompiler.implementation_construct.v0.1"
    _decoders: ClassVar[dict] = {
        "placements": lambda value: _decode_records(value, ImplementationPlacement),
        "features": lambda value: _decode_records(value, PayloadFeature),
    }

    def __post_init__(self):
        for key in (
            "request_fingerprint",
            "requirements_fingerprint",
            "plan_fingerprint",
        ):
            hash_value(getattr(self, key), key)
        name(self.architecture_id, "Construct architecture")
        name(self.molecule_id, "Construct molecule")
        for key, cls in (
            ("placements", ImplementationPlacement),
            ("features", PayloadFeature),
        ):
            object.__setattr__(self, key, _records(getattr(self, key), cls, key))
        _protein(self.precursor_protein, stop=True)
        _protein(self.mature_protein)
        require(
            type(self.cleavage_after_aa) is int
            and self.cleavage_after_aa > 0
            and type(self.cleavage_after_nt) is int
            and self.cleavage_after_nt > 0,
            "Invalid declared processing coordinates.",
        )
        require(
            isinstance(self.junction_coordinates, (tuple, list))
            and all(type(x) is int and x > 0 for x in self.junction_coordinates),
            "Invalid declared junction coordinates.",
        )
        object.__setattr__(
            self, "junction_coordinates", tuple(self.junction_coordinates)
        )

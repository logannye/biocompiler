"""Frozen source, supplied molecular library and partial research requirements.

The original therapeutic target and every source document remain authority. A
selected coding cassette is a research candidate, never a biological guarantee.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import ClassVar

from biocompiler.artifacts.manifest import (
    _Record,
    _array,
    _decode_array,
    _hash,
    _plain_text,
)
from biocompiler.compiler.acceptance import HumanAcceptanceRequest
from biocompiler.compiler.deployment import HumanDeploymentRequest
from biocompiler.compiler.human_behavior import HumanBehaviorRequest
from biocompiler.compiler.request import BuildRequest
from biocompiler.ir.molecular_design import SequenceFragment
from biocompiler.ir.payload import PayloadFeature
from biocompiler.ir.serialization import fingerprint, names, require
from biocompiler.semantics.context import TargetContext

PROFILE_VERSION = "biocompiler.candidate_requirements_profile.v0.1"
CANDIDATE_SCOPE = "partial_product_cassette_research"
MAX_LIBRARY_RECORDS = 32
MAX_CANDIDATE_COMBINATIONS = 256
PART_KINDS = frozenset({"five_prime_utr", "cds", "three_prime_utr", "poly_a"})

# Versioned requirement descriptions, shared as specification rather than an
# implementation of the producer or independent source-correspondence checker.
OBLIGATION_SPECS = MappingProxyType(
    {
        "secretion_mechanism": (
            "implementation",
            "A selected coding sequence does not implement product processing, localization or secretion.",
        ),
        "conditional_control": (
            "implementation",
            "The source condition remains required; no sensing or conditional control mechanism has been implemented.",
        ),
        "quantitative_response": (
            "implementation",
            "Source response rates, timing and persistence remain unimplemented by coding cassette selection.",
        ),
        "biological_function": (
            "evidence",
            "Exact coding correspondence establishes no biological function or therapeutic effect.",
        ),
        "target_applicability": (
            "evidence",
            "The original cell and target context are retained; applicability and deployment remain unestablished.",
        ),
        "human_therapeutic_admission": (
            "evidence",
            "Human therapeutic use remains not admitted; research candidate generation cannot authorize it.",
        ),
        "human_input_observation": (
            "implementation",
            "The complete human input measurement and cell-access requirements remain unimplemented.",
        ),
        "human_predicate_refinement": (
            "implementation",
            "The original refined predicate and typed threshold remain required without a supplied sensing implementation.",
        ),
        "human_response_contract": (
            "implementation",
            "All human active/inactive ranges, initialization, activation/recovery deadlines, persistence and horizon remain required.",
        ),
        "human_goal_refinement": (
            "evidence",
            "The retained measurable goal refinement does not establish achievement of the original therapeutic goal.",
        ),
        "human_behavior_evidence": (
            "evidence",
            "All human behavior measurement, refinement and response-support claims remain unestablished.",
        ),
        "human_deployment_contract": (
            "implementation",
            "All retained delivery, exposure, expression timing, recipient and co-payload dependencies remain unresolved.",
        ),
        "human_deployment_evidence": (
            "evidence",
            "The retained deployment claims establish no actual delivery, expression or same-cell coexistence.",
        ),
        "human_prohibited_behavior": (
            "implementation",
            "All retained healthy-context, background, peak and maximum-response-duration prohibitions remain required.",
        ),
        "human_input_loss_response": (
            "implementation",
            "The retained cell-input availability and recovery requirements have no implemented detector or response mechanism.",
        ),
        "human_external_shutdown": (
            "implementation",
            "The retained shutdown request, latching and deadline have no implemented actuator or priority override.",
        ),
        "human_acceptance_evidence": (
            "evidence",
            "All required/prohibited human-observation and control claims remain unestablished.",
        ),
    }
)


def _ids(value, label):
    result = names(value, label)
    for item in result:
        _plain_text(item, label)
    return result


def source_request_from_dict(data):
    require(isinstance(data, Mapping), "Candidate source must be a request object.")
    schema = data.get("schema_version")
    require(isinstance(schema, str), "Candidate source requires an explicit schema.")
    cls = {
        item.schema_version: item
        for item in (
            BuildRequest,
            HumanBehaviorRequest,
            HumanDeploymentRequest,
            HumanAcceptanceRequest,
        )
    }.get(schema)
    require(cls is not None, "Unsupported candidate source request schema.")
    return cls.from_dict(data)


class _DerivedRecord(_Record):
    """Carry a strict derived operation inventory for pass-manager provenance."""

    def to_dict(self):
        return super().to_dict() | {"nodes": list(self.nodes)}

    @classmethod
    def from_dict(cls, data):
        require(isinstance(data, Mapping), "Candidate artifact must be an object.")
        require("nodes" in data, "Candidate artifact needs its derived node inventory.")
        result = super().from_dict(
            {key: value for key, value in data.items() if key != "nodes"}
        )
        require(
            fingerprint(data["nodes"]) == fingerprint(result.nodes),
            "Derived candidate nodes differ from authority.",
        )
        return result


@dataclass(frozen=True)
class MolecularPart(_Record):
    id: str
    fragment: SequenceFragment
    kind: str
    schema_version: ClassVar[str] = "biocompiler.molecular_part.v0.1"
    _decoders: ClassVar[dict] = {"fragment": SequenceFragment.from_dict}

    def __post_init__(self):
        _plain_text(self.id, "Molecular part id")
        require(
            isinstance(self.fragment, SequenceFragment),
            "Expected a retained sequence fragment.",
        )
        require(
            self.fragment.alphabet == "RNA",
            "Candidate libraries support explicit RNA parts only.",
        )
        require(
            isinstance(self.kind, str) and self.kind in PART_KINDS,
            "Unsupported molecular part kind.",
        )


@dataclass(frozen=True)
class ProductBinding(_Record):
    product: str
    cds_part_id: str
    protein_sequence: str
    schema_version: ClassVar[str] = "biocompiler.product_binding.v0.1"

    def __post_init__(self):
        _plain_text(self.product, "Source product")
        _plain_text(self.cds_part_id, "Coding part id")
        require(
            isinstance(self.protein_sequence, str)
            and len(self.protein_sequence) >= 2
            and self.protein_sequence.endswith("*")
            and set(self.protein_sequence[:-1]) <= set("ACDEFGHIKLMNPQRSTVWY"),
            "Product binding requires an explicit protein spelling with one terminal stop.",
        )


@dataclass(frozen=True)
class RNAArchitecture(_Record):
    id: str
    version: str
    five_prime_part_id: str
    three_prime_part_id: str
    poly_a_part_id: str | None = None
    features: tuple[PayloadFeature, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.rna_architecture.v0.1"
    _decoders: ClassVar[dict] = {
        "features": lambda value: _decode_array(value, PayloadFeature)
    }

    def __post_init__(self):
        for key in ("id", "version", "five_prime_part_id", "three_prime_part_id"):
            _plain_text(getattr(self, key), key)
        if self.poly_a_part_id is not None:
            _plain_text(self.poly_a_part_id, "Poly(A) part id")
        features = _array(
            self.features, PayloadFeature, "Architecture chemistry features"
        )
        require(
            len({item.feature for item in features}) == len(features),
            "Duplicate architecture chemistry feature.",
        )
        object.__setattr__(self, "features", features)


@dataclass(frozen=True)
class MolecularLibrary(_Record):
    id: str
    version: str
    parts: tuple[MolecularPart, ...]
    products: tuple[ProductBinding, ...]
    architectures: tuple[RNAArchitecture, ...]
    schema_version: ClassVar[str] = "biocompiler.molecular_library.v0.1"
    _decoders: ClassVar[dict] = {
        "parts": lambda value: _decode_array(value, MolecularPart),
        "products": lambda value: _decode_array(value, ProductBinding),
        "architectures": lambda value: _decode_array(value, RNAArchitecture),
    }

    def __post_init__(self):
        _plain_text(self.id, "Molecular library id")
        _plain_text(self.version, "Molecular library version")
        for key, cls in (
            ("parts", MolecularPart),
            ("products", ProductBinding),
            ("architectures", RNAArchitecture),
        ):
            values = _array(getattr(self, key), cls, key)
            require(
                0 < len(values) <= MAX_LIBRARY_RECORDS,
                f"Library {key} must contain one to {MAX_LIBRARY_RECORDS} records.",
            )
            object.__setattr__(self, key, values)
        require(
            len(self.products) * len(self.architectures) <= MAX_CANDIDATE_COMBINATIONS,
            "Library exceeds the bounded candidate combination limit.",
        )
        require(
            len({item.id for item in self.parts}) == len(self.parts),
            "Duplicate molecular part id.",
        )
        require(
            len({item.fragment.id for item in self.parts}) == len(self.parts),
            "Every library part requires a unique fragment id.",
        )
        require(
            len({item.id for item in self.architectures}) == len(self.architectures),
            "Duplicate RNA architecture id.",
        )
        require(
            len({(item.product, item.cds_part_id) for item in self.products})
            == len(self.products),
            "Duplicate product/coding-part binding.",
        )
        parts = {item.id: item for item in self.parts}

        def reference(identity, kind):
            require(
                identity in parts and parts[identity].kind == kind,
                f"Library reference {identity!r} must identify a {kind} part.",
            )

        for item in self.products:
            reference(item.cds_part_id, "cds")
        for item in self.architectures:
            reference(item.five_prime_part_id, "five_prime_utr")
            reference(item.three_prime_part_id, "three_prime_utr")
            if item.poly_a_part_id is not None:
                reference(item.poly_a_part_id, "poly_a")


@dataclass(frozen=True)
class CandidateConstraints(_Record):
    allowed_architecture_ids: tuple[str, ...] = ()
    allowed_cds_part_ids: tuple[str, ...] = ()
    max_length: int | None = None
    preference: str = "shortest"
    schema_version: ClassVar[str] = "biocompiler.candidate_constraints.v0.1"

    def __post_init__(self):
        for key in ("allowed_architecture_ids", "allowed_cds_part_ids"):
            object.__setattr__(self, key, _ids(getattr(self, key), key))
        require(
            self.max_length is None
            or type(self.max_length) is int
            and self.max_length >= 0,
            "Maximum candidate length must be a nonnegative integer or null.",
        )
        require(
            isinstance(self.preference, str)
            and self.preference in {"shortest", "lexical"},
            "Candidate preference must be shortest or lexical.",
        )


@dataclass(frozen=True)
class CandidateRequest(_DerivedRecord):
    source: (
        BuildRequest
        | HumanBehaviorRequest
        | HumanDeploymentRequest
        | HumanAcceptanceRequest
    )
    library: MolecularLibrary
    constraints: CandidateConstraints = field(default_factory=CandidateConstraints)
    schema_version: ClassVar[str] = "biocompiler.candidate_request.v0.1"
    _decoders: ClassVar[dict] = {
        "source": source_request_from_dict,
        "library": MolecularLibrary.from_dict,
        "constraints": CandidateConstraints.from_dict,
    }

    def __post_init__(self):
        require(
            isinstance(
                self.source,
                (
                    BuildRequest,
                    HumanBehaviorRequest,
                    HumanDeploymentRequest,
                    HumanAcceptanceRequest,
                ),
            ),
            "Expected complete frozen source authority.",
        )
        require(
            isinstance(self.library, MolecularLibrary), "Expected MolecularLibrary."
        )
        require(
            isinstance(self.constraints, CandidateConstraints),
            "Expected CandidateConstraints.",
        )
        require(
            isinstance(self.target, TargetContext),
            "Candidate requests require an explicit original target context.",
        )
        require(
            not self.build_request.implementation_constraints
            and not self.build_request.preferences,
            "Source BuildRequest implementation_constraints/preferences cannot be ignored; use explicit CandidateConstraints on a source without these fields.",
        )
        require(
            set(self.constraints.allowed_architecture_ids)
            <= {item.id for item in self.library.architectures},
            "Allowed architecture IDs must resolve in the frozen library.",
        )
        require(
            set(self.constraints.allowed_cds_part_ids)
            <= {item.id for item in self.library.parts if item.kind == "cds"},
            "Allowed coding-part IDs must resolve to frozen CDS parts.",
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
class CandidateObligation(_Record):
    id: str
    source_ids: tuple[str, ...]
    category: str
    description: str
    schema_version: ClassVar[str] = "biocompiler.candidate_obligation.v0.1"

    def __post_init__(self):
        _plain_text(self.id, "Candidate obligation id")
        _plain_text(self.description, "Candidate obligation description")
        object.__setattr__(
            self, "source_ids", _ids(self.source_ids, "Obligation source IDs")
        )
        require(
            bool(self.source_ids),
            "Candidate obligations require source correspondence.",
        )
        require(
            isinstance(self.category, str)
            and self.category in {"implementation", "evidence"},
            "Invalid candidate obligation category.",
        )


@dataclass(frozen=True)
class CandidateRequirements(_DerivedRecord):
    request_fingerprint: str
    role_id: str
    secretion_id: str
    action_id: str
    product: str
    source_node_ids: tuple[str, ...]
    unresolved: tuple[CandidateObligation, ...]
    schema_version: ClassVar[str] = "biocompiler.candidate_requirements.v0.1"
    _decoders: ClassVar[dict] = {
        "unresolved": lambda value: _decode_array(value, CandidateObligation),
    }

    def __post_init__(self):
        _hash(self.request_fingerprint, "Candidate source request")
        for key in ("role_id", "secretion_id", "action_id", "product"):
            _plain_text(getattr(self, key), key)
        ids = _ids(self.source_node_ids, "Candidate source node IDs")
        require(
            {self.role_id, self.secretion_id, self.action_id} <= set(ids),
            "Candidate requirements omitted their selected source nodes.",
        )
        require(
            len({self.role_id, self.secretion_id, self.action_id}) == 3,
            "Candidate source roles must identify distinct nodes.",
        )
        object.__setattr__(self, "source_node_ids", ids)
        obligations = _array(
            self.unresolved, CandidateObligation, "Unresolved candidate obligations"
        )
        require(
            bool(obligations)
            and len({item.id for item in obligations}) == len(obligations),
            "Candidate obligations must be nonempty and unique.",
        )
        require(
            all(set(item.source_ids) <= set(ids) for item in obligations),
            "Candidate obligation refers to an unknown source node.",
        )
        object.__setattr__(self, "unresolved", obligations)

    @property
    def nodes(self):
        return tuple(
            {"id": identity, "kind": "implementation_requirement"}
            for identity in self.source_node_ids
        )

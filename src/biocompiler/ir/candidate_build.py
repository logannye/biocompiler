"""Source-rooted research candidate records, with separate completion scopes."""

from dataclasses import dataclass
from typing import ClassVar

from biocompiler.ir.candidate import (
    CandidateRequest,
    CandidateRequirements,
    MolecularPart,
)
from biocompiler.ir.candidate_selection import CandidateLayout, CandidateSelection
from biocompiler.ir.intent import freeze_json, thaw_json
from biocompiler.ir.payload import PayloadMolecule, hash_value
from biocompiler.ir.serialization import (
    JsonArtifact,
    fields,
    fingerprint,
    names,
    require,
)


@dataclass(frozen=True)
class CandidateComponents(JsonArtifact):
    request_fingerprint: str
    selection_fingerprint: str
    architecture_id: str
    cds_part_id: str
    parts: tuple[MolecularPart, ...]
    schema_version: ClassVar[str] = "biocompiler.candidate_components.v0.1"

    def __post_init__(self):
        hash_value(self.request_fingerprint, "Candidate request")
        hash_value(self.selection_fingerprint, "Candidate selection")
        names((self.architecture_id,), "Architecture")
        names((self.cds_part_id,), "Coding part")
        require(
            isinstance(self.parts, (list, tuple))
            and all(isinstance(part, MolecularPart) for part in self.parts),
            "Invalid selected molecular parts.",
        )
        require(3 <= len(self.parts) <= 4, "Expected one RNA product cassette.")
        object.__setattr__(self, "parts", tuple(self.parts))

    def to_dict(self):
        return dict(
            schema_version=self.schema_version,
            request_fingerprint=self.request_fingerprint,
            selection_fingerprint=self.selection_fingerprint,
            architecture_id=self.architecture_id,
            cds_part_id=self.cds_part_id,
            parts=[part.to_dict() for part in self.parts],
        )

    @classmethod
    def from_dict(cls, data):
        fields(
            data,
            {
                "schema_version",
                "request_fingerprint",
                "selection_fingerprint",
                "architecture_id",
                "cds_part_id",
                "parts",
            },
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version, "Unknown components schema."
        )
        require(isinstance(data["parts"], (list, tuple)), "Parts must be an array.")
        return cls(
            data["request_fingerprint"],
            data["selection_fingerprint"],
            data["architecture_id"],
            data["cds_part_id"],
            tuple(MolecularPart.from_dict(part) for part in data["parts"]),
        )


_STAGE_TYPES = {
    "requirements": CandidateRequirements,
    "selection": CandidateSelection,
    "components": CandidateComponents,
    "layout": CandidateLayout,
    "molecule": PayloadMolecule,
}


@dataclass(frozen=True)
class CandidateStage(JsonArtifact):
    """Carry all source requirements alongside each typed implementation stage.

    These source links mean retained requirements, not implemented behavior.
    Concrete product-to-region correspondence is checked separately.
    """

    request_fingerprint: str
    stage: str
    payload: JsonArtifact
    source_node_ids: tuple[str, ...]
    schema_version: ClassVar[str] = "biocompiler.candidate_stage.v0.1"

    def __post_init__(self):
        hash_value(self.request_fingerprint, "Candidate request")
        require(
            isinstance(self.stage, str) and self.stage in _STAGE_TYPES,
            "Unknown candidate stage.",
        )
        require(
            isinstance(self.payload, _STAGE_TYPES[self.stage]), "Wrong stage payload."
        )
        object.__setattr__(
            self, "source_node_ids", names(self.source_node_ids, "Source nodes")
        )

    @property
    def nodes(self):
        return [
            {"id": node, "kind": "retained_requirement"}
            for node in self.source_node_ids
        ]

    def to_dict(self):
        return dict(
            schema_version=self.schema_version,
            request_fingerprint=self.request_fingerprint,
            stage=self.stage,
            payload=self.payload.to_dict(),
            source_node_ids=list(self.source_node_ids),
            nodes=self.nodes,
        )

    @classmethod
    def from_dict(cls, data):
        fields(
            data,
            {
                "schema_version",
                "request_fingerprint",
                "stage",
                "payload",
                "source_node_ids",
                "nodes",
            },
            cls.__name__,
        )
        require(data["schema_version"] == cls.schema_version, "Unknown stage schema.")
        require(
            isinstance(data["stage"], str) and data["stage"] in _STAGE_TYPES,
            "Unknown candidate stage.",
        )
        result = cls(
            data["request_fingerprint"],
            data["stage"],
            _STAGE_TYPES[data["stage"]].from_dict(data["payload"]),
            data["source_node_ids"],
        )
        require(
            fingerprint(data["nodes"]) == fingerprint(result.nodes),
            "Changed retained source inventory.",
        )
        return result


@dataclass(frozen=True)
class CandidateBuildRecord(JsonArtifact):
    """A reconstructable record; fresh verification needs independent authority."""

    request: CandidateRequest
    requirements: CandidateRequirements
    selection: CandidateSelection
    components: CandidateComponents | None
    layout: CandidateLayout | None
    molecule: PayloadMolecule | None
    checks: dict
    tool_versions: dict
    schema_version: ClassVar[str] = "biocompiler.candidate_build.v0.1"

    def __post_init__(self):
        for item, expected in (
            (self.request, CandidateRequest),
            (self.requirements, CandidateRequirements),
            (self.selection, CandidateSelection),
        ):
            require(isinstance(item, expected), "Wrong candidate build authority.")
        for item, expected in (
            (self.components, CandidateComponents),
            (self.layout, CandidateLayout),
            (self.molecule, PayloadMolecule),
        ):
            require(
                item is None or isinstance(item, expected),
                "Wrong candidate build artifact.",
            )
        present = (
            self.components is not None,
            self.layout is not None,
            self.molecule is not None,
        )
        require(len(set(present)) == 1, "Candidate stages must be retained together.")
        require(
            present[0] == (self.selection.selected is not None),
            "Molecular output disagrees with bounded selection.",
        )
        require(
            isinstance(self.checks, dict) or hasattr(self.checks, "items"),
            "Invalid checks.",
        )
        require(
            isinstance(self.tool_versions, dict)
            or hasattr(self.tool_versions, "items"),
            "Invalid tool versions.",
        )
        object.__setattr__(self, "checks", freeze_json(dict(self.checks)))
        object.__setattr__(self, "tool_versions", freeze_json(dict(self.tool_versions)))

    @property
    def status(self):
        return (
            "candidate_generated" if self.molecule is not None else "no_candidate_found"
        )

    @property
    def source_map(self):
        if self.layout is None:
            return []
        parts = {part.fragment.id: part for part in self.components.parts}
        require(
            all(placement.fragment_id in parts for placement in self.layout.placements),
            "Region correspondence names an unselected fragment.",
        )
        return [
            dict(
                source_requirement_ids=[
                    self.requirements.secretion_id,
                    self.requirements.action_id,
                ],
                correspondence="product_encoding"
                if placement.kind == "cds"
                else "architecture_support",
                architecture_id=self.components.architecture_id,
                part_id=parts[placement.fragment_id].id,
                part_fingerprint=parts[placement.fragment_id].fingerprint,
                region_id=placement.region_id,
                source_range=placement.source_range.to_dict(),
                molecule_range=placement.molecule_range.to_dict(),
            )
            for placement in self.layout.placements
        ]

    def to_dict(self):
        return dict(
            schema_version=self.schema_version,
            request=self.request.to_dict(),
            requirements=self.requirements.to_dict(),
            selection=self.selection.to_dict(),
            components=self.components.to_dict() if self.components else None,
            layout=self.layout.to_dict() if self.layout else None,
            molecule=self.molecule.to_dict() if self.molecule else None,
            checks=thaw_json(self.checks),
            tool_versions=thaw_json(self.tool_versions),
            status=self.status,
            source_map=self.source_map,
            intended_use="research_candidate",
            completion_scope="product_cassette_structure",
            therapeutic_implementation="partial",
            biological_support="unestablished",
            human_therapeutic_admission="not_admitted",
        )

    @classmethod
    def from_dict(cls, data):
        fields(
            data,
            {
                "schema_version",
                "request",
                "requirements",
                "selection",
                "components",
                "layout",
                "molecule",
                "checks",
                "tool_versions",
                "status",
                "source_map",
                "intended_use",
                "completion_scope",
                "therapeutic_implementation",
                "biological_support",
                "human_therapeutic_admission",
            },
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unknown candidate build schema.",
        )
        result = cls(
            CandidateRequest.from_dict(data["request"]),
            CandidateRequirements.from_dict(data["requirements"]),
            CandidateSelection.from_dict(data["selection"]),
            CandidateComponents.from_dict(data["components"])
            if data["components"] is not None
            else None,
            CandidateLayout.from_dict(data["layout"])
            if data["layout"] is not None
            else None,
            PayloadMolecule.from_dict(data["molecule"])
            if data["molecule"] is not None
            else None,
            data["checks"],
            data["tool_versions"],
        )
        require(
            fingerprint(data) == fingerprint(result.to_dict()),
            "Candidate build changed derived correspondence or completion claims.",
        )
        return result

"""Reconstructable research builds; stored checks never confer fresh authority."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from biocompiler.artifacts.manifest import _Record, _hash
from biocompiler.ir.implementation import (
    ImplementationConstruct,
    ImplementationPlan,
    ImplementationRequest,
    ImplementationSelection,
    SecretedRNAArchitecture,
)
from biocompiler.ir.implementation_requirements import ImplementationRequirements
from biocompiler.ir.intent import freeze_json, thaw_json
from biocompiler.ir.payload import PayloadMolecule
from biocompiler.ir.serialization import fields, fingerprint, names, require

COMPLETION_SCOPE = "secreted_precursor_structure"


@dataclass(frozen=True)
class ImplementationPlanning(_Record):
    selection: ImplementationSelection
    plan: ImplementationPlan | None
    schema_version: ClassVar[str] = "biocompiler.implementation_planning.v0.1"
    _decoders: ClassVar[dict] = {
        "selection": ImplementationSelection.from_dict,
        "plan": lambda value: (
            None if value is None else ImplementationPlan.from_dict(value)
        ),
    }

    def __post_init__(self):
        require(
            isinstance(self.selection, ImplementationSelection), "Invalid selection."
        )
        require(
            self.plan is None or isinstance(self.plan, ImplementationPlan),
            "Invalid plan.",
        )
        require(
            (self.plan is not None)
            == (self.selection.selected_architecture_id is not None),
            "A selected architecture must retain its molecular plan.",
        )


@dataclass(frozen=True)
class ImplementationComponents(_Record):
    """The exact selected recipe and source records, not empirical capabilities."""

    request_fingerprint: str
    plan_fingerprint: str
    architecture: SecretedRNAArchitecture
    schema_version: ClassVar[str] = "biocompiler.implementation_components.v0.1"
    _decoders: ClassVar[dict] = {"architecture": SecretedRNAArchitecture.from_dict}

    def __post_init__(self):
        _hash(self.request_fingerprint, "Implementation request")
        _hash(self.plan_fingerprint, "Implementation plan")
        require(
            isinstance(self.architecture, SecretedRNAArchitecture),
            "Invalid architecture.",
        )


_STAGES = {
    "request": ImplementationRequest,
    "requirements": ImplementationRequirements,
    "planning": ImplementationPlanning,
    "components": ImplementationComponents,
    "construct": ImplementationConstruct,
    "molecule": PayloadMolecule,
}


@dataclass(frozen=True)
class ImplementationStage(_Record):
    request_fingerprint: str
    stage: str
    payload: object
    source_node_ids: tuple[str, ...]
    schema_version: ClassVar[str] = "biocompiler.implementation_stage.v0.1"

    def __post_init__(self):
        _hash(self.request_fingerprint, "Implementation request")
        require(isinstance(self.stage, str) and self.stage in _STAGES, "Unknown stage.")
        require(isinstance(self.payload, _STAGES[self.stage]), "Wrong stage payload.")
        object.__setattr__(
            self, "source_node_ids", names(self.source_node_ids, "Source nodes")
        )

    @property
    def nodes(self):
        return tuple(
            {"id": node, "kind": "retained_requirement"}
            for node in self.source_node_ids
        )

    def to_dict(self):
        return super().to_dict() | {"nodes": list(self.nodes)}

    @classmethod
    def from_dict(cls, data):
        data = thaw_json(data)
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
            isinstance(data["stage"], str) and data["stage"] in _STAGES,
            "Unknown stage.",
        )
        result = cls(
            data["request_fingerprint"],
            data["stage"],
            _STAGES[data["stage"]].from_dict(data["payload"]),
            data["source_node_ids"],
        )
        require(
            fingerprint(data["nodes"]) == fingerprint(result.nodes),
            "Changed source inventory.",
        )
        return result


@dataclass(frozen=True)
class ImplementationBuildRecord(_Record):
    request: ImplementationRequest
    requirements: ImplementationRequirements
    selection: ImplementationSelection
    plan: ImplementationPlan | None
    components: ImplementationComponents | None
    construct: ImplementationConstruct | None
    molecule: PayloadMolecule | None
    checks: Mapping
    tool_versions: Mapping
    schema_version: ClassVar[str] = "biocompiler.implementation_build.v0.1"
    _decoders: ClassVar[dict] = {
        "request": ImplementationRequest.from_dict,
        "requirements": ImplementationRequirements.from_dict,
        "selection": ImplementationSelection.from_dict,
        "plan": lambda value: (
            None if value is None else ImplementationPlan.from_dict(value)
        ),
        "components": lambda value: (
            None if value is None else ImplementationComponents.from_dict(value)
        ),
        "construct": lambda value: (
            None if value is None else ImplementationConstruct.from_dict(value)
        ),
        "molecule": lambda value: (
            None if value is None else PayloadMolecule.from_dict(value)
        ),
    }

    def __post_init__(self):
        for value, kind in (
            (self.request, ImplementationRequest),
            (self.requirements, ImplementationRequirements),
            (self.selection, ImplementationSelection),
        ):
            require(isinstance(value, kind), "Invalid implementation build authority.")
        for value, kind in (
            (self.plan, ImplementationPlan),
            (self.components, ImplementationComponents),
            (self.construct, ImplementationConstruct),
            (self.molecule, PayloadMolecule),
        ):
            require(
                value is None or isinstance(value, kind),
                "Invalid implementation artifact.",
            )
        presence = (
            self.plan is not None,
            self.components is not None,
            self.construct is not None,
            self.molecule is not None,
        )
        require(
            len(set(presence)) == 1,
            "Selected molecular stages must be retained together.",
        )
        require(
            presence[0] == (self.selection.selected_architecture_id is not None),
            "Molecular output differs from selection.",
        )
        for key in ("checks", "tool_versions"):
            require(
                isinstance(getattr(self, key), Mapping),
                "Invalid build checks or tools.",
            )
            object.__setattr__(self, key, freeze_json(dict(getattr(self, key))))

    @property
    def status(self):
        return "candidate_built" if self.molecule is not None else "no_candidate_found"

    @property
    def scope(self):
        return COMPLETION_SCOPE

    @property
    def therapeutic_implementation(self):
        return "partial"

    @property
    def human_therapeutic_admission(self):
        return "not_admitted"

    def to_dict(self):
        return super().to_dict() | {
            "status": self.status,
            "scope": self.scope,
            "structural_completion": self.molecule is not None,
            "therapeutic_implementation": self.therapeutic_implementation,
            "physical_function": "unestablished",
            "human_therapeutic_admission": self.human_therapeutic_admission,
        }

    @classmethod
    def from_dict(cls, data):
        derived = {
            "status",
            "scope",
            "structural_completion",
            "therapeutic_implementation",
            "physical_function",
            "human_therapeutic_admission",
        }
        require(
            isinstance(data, Mapping) and derived <= set(data), "Missing build scope."
        )
        result = super().from_dict(
            {key: value for key, value in data.items() if key not in derived}
        )
        expected = result.to_dict()
        require(
            all(
                fingerprint(data[key]) == fingerprint(expected[key]) for key in derived
            ),
            "Changed build completion or evidence boundary.",
        )
        return result

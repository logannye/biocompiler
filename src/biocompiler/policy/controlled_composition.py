"""Inert controlled-composition descriptions and immutable supplied source authority.

No evaluator, native client or complete material request is implemented here.
Preparing these records grants no semantic, material or empirical acceptance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import ClassVar, Literal, cast

from biocompiler.core_client import JsonValue, decode_json, encode_json
from . import model as m
from .serialization import from_data, to_data

CONTRACT_SCHEMA = "biocompiler.policy_controlled_composition_contract.v0.1"
SOURCE_AUTHORITY_SCHEMA = "biocompiler.policy_controlled_composition_source_authority.v0.1"
PROFILE = "biocompiler.policy_controlled_composition_mrna.v0.1"
MAX_DESCRIPTION_TICKS = 10_000


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _object(value: JsonValue, keys: set[str], label: str) -> dict[str, JsonValue]:
    _require(type(value) is dict and set(value) == keys, label + " requires its exact closed fields")
    return cast(dict[str, JsonValue], value)


def _text(value: object, label: str, maximum: int = 256) -> str:
    _require(type(value) is str and bool(value.strip()) and len(value.encode("utf-8")) <= maximum,
             label + " requires nonempty bounded text")
    return cast(str, value)


def _ticks(value: object) -> int:
    _require(type(value) is int and 0 < value <= MAX_DESCRIPTION_TICKS,
             "Description delays/deadlines require positive integral ticks within the representation ceiling")
    return cast(int, value)


def _ref(value: object, kind: str) -> None:
    _require(type(value) is m.Ref and value.kind == kind, "Expected a typed " + kind + " reference")
    _text(cast(m.Ref, value).id, kind + " id")


def _definition(value: object) -> None:
    _require(type(value) is m.DefinitionRef, "Expected a complete typed DefinitionRef")
    reference = cast(m.DefinitionRef, value)
    _text(reference.id, "Definition id")
    _text(reference.version, "Definition version")
    _require(type(reference.digest) is str and len(reference.digest) == 64
             and all(char in "0123456789abcdef" for char in reference.digest),
             "Definition digest requires exact lowercase SHA-256; it is never regenerated")


@dataclass(frozen=True, slots=True)
class ActualActivityDelays:
    onset_ticks: int
    cessation_ticks: int
    reactivation_ticks: int

    def __post_init__(self) -> None:
        for value in (self.onset_ticks, self.cessation_ticks, self.reactivation_ticks):
            _ticks(value)

    def to_data(self) -> dict[str, JsonValue]:
        return {"onset_ticks": self.onset_ticks, "cessation_ticks": self.cessation_ticks,
                "reactivation_ticks": self.reactivation_ticks}

    @classmethod
    def from_data(cls, value: JsonValue) -> ActualActivityDelays:
        row = _object(value, {"onset_ticks", "cessation_ticks", "reactivation_ticks"}, "Actual delays")
        return cls(**{key: _ticks(item) for key, item in row.items()})


@dataclass(frozen=True, slots=True)
class ActivityDeadlines:
    onset_ticks: int
    controller_off_ticks: int
    antigen_off_ticks: int
    component_off_ticks: int
    reactivation_ticks: int

    def __post_init__(self) -> None:
        for value in (self.onset_ticks, self.controller_off_ticks, self.antigen_off_ticks,
                      self.component_off_ticks, self.reactivation_ticks):
            _ticks(value)

    def to_data(self) -> dict[str, JsonValue]:
        return {"onset_ticks": self.onset_ticks, "controller_off_ticks": self.controller_off_ticks,
                "antigen_off_ticks": self.antigen_off_ticks, "component_off_ticks": self.component_off_ticks,
                "reactivation_ticks": self.reactivation_ticks}

    @classmethod
    def from_data(cls, value: JsonValue) -> ActivityDeadlines:
        row = _object(value, {"onset_ticks", "controller_off_ticks", "antigen_off_ticks",
                             "component_off_ticks", "reactivation_ticks"}, "Requested deadlines")
        return cls(**{key: _ticks(item) for key, item in row.items()})


@dataclass(frozen=True, slots=True)
class ActivityReadout:
    activity: m.Ref
    definition: m.DefinitionRef
    physical_bands: tuple[Literal["background"], Literal["active"]] = field(default=("background", "active"), init=False)

    def __post_init__(self) -> None:
        _ref(self.activity, "ControlledActivity")
        _definition(self.definition)

    def to_data(self) -> dict[str, JsonValue]:
        return {"activity": cast(JsonValue, to_data(self.activity)),
                "definition": cast(JsonValue, to_data(self.definition)), "physical_bands": list(self.physical_bands)}

    @classmethod
    def from_data(cls, value: JsonValue) -> ActivityReadout:
        row = _object(value, {"activity", "definition", "physical_bands"}, "Activity readout")
        _require(row["physical_bands"] == ["background", "active"], "Physical activity has exactly background/active bands")
        return cls(from_data(row["activity"], m.Ref), from_data(row["definition"], m.DefinitionRef))


@dataclass(frozen=True, slots=True)
class ProductMemberBinding:
    product_parameter: m.Ref
    member_id: str
    cds_id: str
    product_definition: m.DefinitionRef

    def __post_init__(self) -> None:
        _ref(self.product_parameter, "Parameter")
        _text(self.member_id, "Member id")
        _text(self.cds_id, "CDS id")
        _definition(self.product_definition)

    def to_data(self) -> dict[str, JsonValue]:
        return {"product_parameter": cast(JsonValue, to_data(self.product_parameter)),
                "member_id": self.member_id, "cds_id": self.cds_id,
                "product_definition": cast(JsonValue, to_data(self.product_definition))}

    @classmethod
    def from_data(cls, value: JsonValue) -> ProductMemberBinding:
        row = _object(value, {"product_parameter", "member_id", "cds_id", "product_definition"}, "Product/member binding")
        return cls(from_data(row["product_parameter"], m.Ref), _text(row["member_id"], "Member id"),
                   _text(row["cds_id"], "CDS id"), from_data(row["product_definition"], m.DefinitionRef))


@dataclass(frozen=True, slots=True)
class ControllerBinding:
    definition: m.DefinitionRef
    executor: m.Ref
    scope: Literal["executor"] = field(default="executor", init=False)

    def __post_init__(self) -> None:
        _definition(self.definition)
        _ref(self.executor, "Role")

    def to_data(self) -> dict[str, JsonValue]:
        return {"definition": cast(JsonValue, to_data(self.definition)),
                "executor": cast(JsonValue, to_data(self.executor)), "scope": self.scope}

    @classmethod
    def from_data(cls, value: JsonValue) -> ControllerBinding:
        row = _object(value, {"definition", "executor", "scope"}, "Controller binding")
        _require(row["scope"] == "executor", "Controller scope is executor")
        return cls(from_data(row["definition"], m.DefinitionRef), from_data(row["executor"], m.Ref))


@dataclass(frozen=True, slots=True)
class ControlledCompositionContractDescription:
    """Typed contract inputs, not a checked native realization or material contract."""
    products: tuple[ProductMemberBinding, ProductMemberBinding]
    controller: ControllerBinding
    readout: ActivityReadout
    actual_delays: ActualActivityDelays
    requested_deadlines: ActivityDeadlines
    schema_version: ClassVar[str] = CONTRACT_SCHEMA
    profile: ClassVar[str] = PROFILE
    mechanism: Literal["deterministic_delay"] = field(default="deterministic_delay", init=False)
    initial_activity: Literal["background"] = field(default="background", init=False)

    def __post_init__(self) -> None:
        _require(type(self.products) in (tuple, list) and len(self.products) == 2
                 and all(type(product) is ProductMemberBinding for product in self.products),
                 "Exactly two typed ordered product/member bindings are required")
        object.__setattr__(self, "products", tuple(self.products))
        _require(len({product.member_id for product in self.products}) == 2
                 and len({product.product_parameter.id for product in self.products}) == 2,
                 "Product parameters and member identities must be distinct")
        _require(type(self.controller) is ControllerBinding and type(self.readout) is ActivityReadout
                 and type(self.actual_delays) is ActualActivityDelays and type(self.requested_deadlines) is ActivityDeadlines,
                 "Use typed controller, readout, actual delays and requested deadlines")

    def to_data(self) -> dict[str, JsonValue]:
        return {"schema_version": self.schema_version, "profile": self.profile,
                "products": [product.to_data() for product in self.products],
                "controller": self.controller.to_data(), "readout": self.readout.to_data(),
                "actual_delays": self.actual_delays.to_data(), "requested_deadlines": self.requested_deadlines.to_data(),
                "mechanism": self.mechanism, "initial_activity": self.initial_activity}

    @classmethod
    def from_data(cls, value: JsonValue) -> ControlledCompositionContractDescription:
        row = _object(value, {"schema_version", "profile", "products", "controller", "readout", "actual_delays",
                             "requested_deadlines", "mechanism", "initial_activity"}, "Control description")
        _require((row["schema_version"], row["profile"], row["mechanism"], row["initial_activity"]) ==
                 (CONTRACT_SCHEMA, PROFILE, "deterministic_delay", "background"), "Unsupported control-description family")
        products = row["products"]
        _require(type(products) is list and len(products) == 2, "Exactly two product descriptions are required")
        rows = cast(list[JsonValue], products)
        return cls((ProductMemberBinding.from_data(rows[0]), ProductMemberBinding.from_data(rows[1])),
                   ControllerBinding.from_data(row["controller"]), ActivityReadout.from_data(row["readout"]),
                   ActualActivityDelays.from_data(row["actual_delays"]), ActivityDeadlines.from_data(row["requested_deadlines"]))


def _project_context(value: JsonValue) -> dict[str, JsonValue]:
    from .research_project import SourceRecord
    row = _object(value, {"project_id", "title", "sources", "assumptions"}, "Supplied project context")
    _text(row["project_id"], "Project id", 128)
    _text(row["title"], "Project title", 4096)
    _require(type(row["sources"]) is list and 1 <= len(row["sources"]) <= 128, "Project sources require 1..128 complete records")
    identities: set[str] = set()
    for raw in cast(list[JsonValue], row["sources"]):
        source = _object(raw, {"id", "locator", "version", "sha256", "role", "reuse_terms"}, "Supplied source record")
        record = SourceRecord(**cast(dict[str, str], source))
        _require(record.id not in identities, "Duplicate supplied source identity")
        identities.add(record.id)
    _require(type(row["assumptions"]) is list and len(row["assumptions"]) <= 128, "Assumptions require an explicit bounded list")
    for assumption in cast(list[JsonValue], row["assumptions"]):
        _text(assumption, "Supplied assumption", 4096)
    return row


@dataclass(frozen=True, slots=True, init=False)
class SourceAuthoritySnapshot:
    """Complete snapshot of the supplied source description, not native material authority."""
    _snapshot_json: bytes

    def __init__(self, *, document: m.BuildRequest, control_contract: ControlledCompositionContractDescription,
                 project_context: JsonValue) -> None:
        _require(type(document) is m.BuildRequest and document.profile == m.CONTROLLED_COMPOSITION_SOURCE_PROFILE
                 and type(control_contract) is ControlledCompositionContractDescription,
                 "A typed controlled source BuildRequest and contract description are required")
        # Freeze first, then reconstruct and bind only the detached original wire
        # values. Frozen dataclass declarations alone do not validate wire authority.
        payload: JsonValue = {"schema_version": SOURCE_AUTHORITY_SCHEMA,
                              "document": cast(JsonValue, to_data(document)),
                              "control_contract": control_contract.to_data(), "project_context": project_context}
        frozen = encode_json(payload)
        detached = cast(dict[str, JsonValue], decode_json(frozen))
        captured_document = from_data(detached["document"], m.BuildRequest)
        captured_contract = ControlledCompositionContractDescription.from_data(detached["control_contract"])
        _require(encode_json(cast(JsonValue, to_data(captured_document))) == encode_json(detached["document"])
                 and encode_json(captured_contract.to_data()) == encode_json(detached["control_contract"]),
                 "Original authority cannot be normalized or repaired during capture")
        _project_context(detached["project_context"])
        activities = [item for item in captured_document.program.declarations if type(item) is m.ControlledActivity]
        _require(len(activities) == 1, "Source description requires one ControlledActivity binding")
        activity = activities[0]
        _require(captured_contract.readout.activity == m.Ref(activity.id, "ControlledActivity")
                 and captured_contract.readout.definition == activity.readout
                 and captured_contract.controller.executor == activity.executor
                 and tuple(product.product_parameter for product in captured_contract.products) == activity.products,
                 "Control-description references differ from their original source activity")
        object.__setattr__(self, "_snapshot_json", frozen)

    @classmethod
    def from_data(cls, value: JsonValue) -> SourceAuthoritySnapshot:
        frozen = encode_json(value)
        row = _object(decode_json(frozen), {"schema_version", "document", "control_contract", "project_context"}, "Source authority snapshot")
        _require(row["schema_version"] == SOURCE_AUTHORITY_SCHEMA, "Unsupported source-authority schema")
        result = cls(document=from_data(row["document"], m.BuildRequest),
                     control_contract=ControlledCompositionContractDescription.from_data(row["control_contract"]),
                     project_context=row["project_context"])
        _require(result.canonical_bytes == frozen, "Original authority cannot be normalized or repaired during import")
        return result

    def to_data(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self._snapshot_json))

    @property
    def canonical_bytes(self) -> bytes:
        return self._snapshot_json

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self._snapshot_json).hexdigest()

    @property
    def native_status(self) -> Literal["not_performed"]:
        return "not_performed"

    @property
    def material_status(self) -> Literal["not_performed"]:
        return "not_performed"

    @property
    def document(self) -> m.BuildRequest:
        return from_data(self.to_data()["document"], m.BuildRequest)

    @property
    def control_contract(self) -> ControlledCompositionContractDescription:
        return ControlledCompositionContractDescription.from_data(self.to_data()["control_contract"])

    @property
    def project_context(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.to_data()["project_context"])

    def with_document(self, document: m.BuildRequest) -> SourceAuthoritySnapshot:
        """Replace only source; retain model parameters, provenance and pins unchanged."""
        return SourceAuthoritySnapshot(document=document, control_contract=self.control_contract,
                                       project_context=self.project_context)

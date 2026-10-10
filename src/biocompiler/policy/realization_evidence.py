"""Typed supplied measurement criteria, with no biological acceptance authority.

These immutable values author a separate evidence contract. Native checking
recomputes interval envelopes and binds the target to freshly checked material.
Artifact locators are descriptive; this module never fetches or authenticates
them, computes a confidence interval, or classifies evidence as supported.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import re
from typing import Any, Iterable, Literal, cast

from biocompiler.core_client import CoreProtocolError, JsonValue, encode_json
from . import model as m
from .serialization import to_data

SCHEMA = "biocompiler.policy_realization_evidence_contract.v0.1"
PROFILE = "biocompiler.policy_parameter_measurement_evidence.v0.1"
__all__ = ["EvidenceAuthoringError", "ContentPin", "Interval", "Applicability", "Artifact", "Provenance",
           "Requirement", "Protocol", "Replicate", "Dataset", "AnalysisSoftware", "Analysis", "Dossier",
           "EvidenceContract", "fingerprint", "source_pin", "validate_assessment"]


class EvidenceAuthoringError(ValueError):
    """An invalid authoring record; no native or empirical assessment occurred."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceAuthoringError(message)


def _text(value: str, maximum: int = 256) -> None:
    _require(type(value) is str and bool(value.strip()) and len(value.encode("utf-8")) <= maximum,
             "Use an explicit bounded text identity")


def _hash(value: str) -> None:
    _require(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value),
             "Use a complete lowercase SHA-256 content identity")


def fingerprint(value: JsonValue) -> str:
    return hashlib.sha256(encode_json(value)).hexdigest()


def _decimal(value: str) -> Fraction:
    _require(type(value) is str and len(value) <= 256 and
             re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", value) is not None,
             "Use bounded finite exact decimal text")
    pieces = re.split("[eE]", value)
    exponent = (int(pieces[1]) if len(pieces) == 2 else 0) - len(pieces[0].partition(".")[2])
    _require(abs(exponent) <= 1024, "Exact decimal exponent exceeds its bound")
    return Fraction(value)


def _quantity(value: m.Quantity) -> Fraction:
    _require(type(value) is m.Quantity and type(value.unit) is m.Unit, "Use complete source Quantity and Unit records")
    to_data(value)
    _require(len(value.amount) <= 256 and m.Quantity(value.amount, value.unit).amount == value.amount,
             "Use canonical exact decimal quantities")
    for name in (value.unit.id, value.unit.dimension, value.unit.quantity_kind):
        _text(name)
    _require(_decimal(value.unit.scale) > 0, "Unit scale must be positive")
    if value.unit.reference is not None:
        _text(value.unit.reference)
    return Fraction(value.amount)


def _sequence(owner: object, field: str, values: object, expected: type[Any], maximum: int) -> tuple[Any, ...]:
    _require(type(values) in (tuple, list), "Use a bounded list or tuple of typed records")
    rows = tuple(cast(tuple[Any, ...], values))
    _require(len(rows) <= maximum and all(type(value) is expected for value in rows), "Evidence collection shape or bound changed")
    object.__setattr__(owner, field, rows)
    return rows


def _unique(values: tuple[str, ...]) -> None:
    _require(len(values) == len(set(values)), "Evidence record identities must be unique")


@dataclass(frozen=True, slots=True)
class ContentPin:
    kind: Literal["model", "source"]
    id: str
    version: str
    content_fingerprint: str

    def __post_init__(self) -> None:
        _require(self.kind in ("model", "source"), "Use a model or independent source pin")
        _text(self.id)
        _text(self.version)
        _hash(self.content_fingerprint)

    def to_data(self) -> JsonValue:
        return {"schema_version": "biocompiler.component_identity.v0.1", "kind": self.kind,
                "id": self.id, "version": self.version, "content_fingerprint": self.content_fingerprint}

    @classmethod
    def from_data(cls, raw: JsonValue) -> ContentPin:
        _require(type(raw) is dict, "Use a complete content pin")
        value = cast(dict[str, JsonValue], raw)
        _require(set(value) == {"schema_version", "kind", "id", "version", "content_fingerprint"}
                 and value["schema_version"] == "biocompiler.component_identity.v0.1", "Unknown content pin shape")
        return cls(cast(Literal["model", "source"], value["kind"]), cast(str, value["id"]),
                   cast(str, value["version"]), cast(str, value["content_fingerprint"]))


@dataclass(frozen=True, slots=True)
class Interval:
    lower: m.Quantity
    upper: m.Quantity

    def __post_init__(self) -> None:
        low, high = _quantity(self.lower), _quantity(self.upper)
        _require(self.lower.unit == self.upper.unit and low <= high, "Interval bounds require identical complete units and exact order")

    def to_data(self) -> JsonValue:
        return {"lower": cast(JsonValue, to_data(self.lower)), "upper": cast(JsonValue, to_data(self.upper))}


@dataclass(frozen=True, slots=True)
class Applicability:
    recipient_fingerprint: str
    deployment_fingerprint: str
    clock_fingerprint: str
    operating_domain_fingerprint: str
    environment_fingerprints: tuple[str, ...]

    def __post_init__(self) -> None:
        for value in (self.recipient_fingerprint, self.deployment_fingerprint,
                      self.clock_fingerprint, self.operating_domain_fingerprint):
            _hash(value)
        values = _sequence(self, "environment_fingerprints", self.environment_fingerprints, str, 8)
        for value in values:
            _hash(value)
        _unique(values)

    def to_data(self) -> JsonValue:
        return {"recipient_fingerprint": self.recipient_fingerprint, "deployment_fingerprint": self.deployment_fingerprint,
                "clock_fingerprint": self.clock_fingerprint, "operating_domain_fingerprint": self.operating_domain_fingerprint,
                "environment_fingerprints": list(self.environment_fingerprints)}

    @classmethod
    def from_material_request(cls, raw: JsonValue) -> Applicability:
        """Snapshot original applicability identities; this grants no admission."""
        encode_json(raw)  # Reject callbacks, cycles, nonliteral values and floats.
        request = cast(dict[str, Any], raw)
        context, original = request["context"], request["implementation_request"]
        return cls(fingerprint(context["recipient"]), fingerprint(original["document"]["deployment"]),
                   fingerprint(context["clock"]), fingerprint(original["operating_domain"]),
                   tuple(fingerprint(value["body"]) for value in context["providers"] if value["body"]["kind"] == "environment"))


@dataclass(frozen=True, slots=True)
class Artifact:
    id: str
    sha256: str
    media_type: str
    locator: str

    def __post_init__(self) -> None:
        _text(self.id)
        _hash(self.sha256)
        _text(self.media_type)
        _text(self.locator, 2048)

    def to_data(self) -> JsonValue:
        return {"id": self.id, "sha256": self.sha256, "media_type": self.media_type, "locator": self.locator}


@dataclass(frozen=True, slots=True)
class Provenance:
    origin: Literal["synthetic_fixture", "supplied_experiment"]
    producer: str
    recorded_at: str
    artifact: Artifact

    def __post_init__(self) -> None:
        _require(self.origin in ("synthetic_fixture", "supplied_experiment") and type(self.artifact) is Artifact,
                 "Declare an evidence origin and separate artifact provenance")
        _text(self.producer)
        _text(self.recorded_at)

    def to_data(self) -> JsonValue:
        return {"origin": self.origin, "producer": self.producer, "recorded_at": self.recorded_at, "artifact": self.artifact.to_data()}


@dataclass(frozen=True, slots=True)
class Requirement:
    id: str
    instance: str
    component: ContentPin
    mechanism_fingerprint: str
    transfer: str
    nominal: m.Quantity
    accepted_interval: Interval
    minimum_replicates: int
    applicability: Applicability

    def __post_init__(self) -> None:
        for name in (self.id, self.instance, self.transfer):
            _text(name)
        _require(type(self.component) is ContentPin and self.component.kind == "model", "Target an exact selected model component")
        _hash(self.mechanism_fingerprint)
        _quantity(self.nominal)
        _require(type(self.accepted_interval) is Interval and type(self.applicability) is Applicability, "Use typed criteria and applicability")
        _require(type(self.minimum_replicates) is int and 2 <= self.minimum_replicates <= 32, "Require two-to-thirty-two supplied replicates")

    def to_data(self) -> JsonValue:
        return {"id": self.id, "instance": self.instance, "component": self.component.to_data(),
                "mechanism_fingerprint": self.mechanism_fingerprint, "parameter": {"kind": "transfer_amount", "transfer": self.transfer},
                "nominal": cast(JsonValue, to_data(self.nominal)), "accepted_interval": self.accepted_interval.to_data(),
                "minimum_replicates": self.minimum_replicates, "applicability": self.applicability.to_data()}


def _supplied(identity: ContentPin, body: JsonValue) -> JsonValue:
    _require(identity.kind == "source" and identity.content_fingerprint == fingerprint(body), "Independent source identity must pin its complete body")
    return {"identity": identity.to_data(), "body": body}


def source_pin(id: str, version: str, body: JsonValue) -> ContentPin:
    return ContentPin("source", id, version, fingerprint(body))


@dataclass(frozen=True, slots=True)
class Protocol:
    id: str
    version: str
    sample_period: m.Quantity
    procedure: str
    provenance: Provenance

    def __post_init__(self) -> None:
        _text(self.id)
        _text(self.version)
        _text(self.procedure, 4096)
        _require(_quantity(self.sample_period) > 0 and self.sample_period.unit.dimension == "time"
                 and self.sample_period.unit.quantity_kind == "duration" and self.sample_period.unit.reference is None,
                 "Use an exact positive unreferenced sample duration")
        _require(type(self.provenance) is Provenance, "Use typed protocol provenance")

    def body(self) -> JsonValue:
        return {"quantity_semantics": "amount_per_accepted_sample", "sample_period": cast(JsonValue, to_data(self.sample_period)),
                "procedure": self.procedure, "provenance": self.provenance.to_data()}

    @property
    def identity(self) -> ContentPin:
        return source_pin(self.id, self.version, self.body())

    def to_data(self) -> JsonValue:
        return _supplied(self.identity, self.body())


@dataclass(frozen=True, slots=True)
class Replicate:
    id: str
    interval: Interval

    def __post_init__(self) -> None:
        _text(self.id)
        _require(type(self.interval) is Interval, "Use a supplied typed measurement interval")

    def to_data(self) -> JsonValue:
        return {"id": self.id, "interval": self.interval.to_data()}


@dataclass(frozen=True, slots=True)
class Dataset:
    id: str
    version: str
    requirement: str
    protocol: ContentPin
    applicability: Applicability
    replicates: tuple[Replicate, ...]
    provenance: Provenance

    def __post_init__(self) -> None:
        for name in (self.id, self.version, self.requirement):
            _text(name)
        _require(type(self.protocol) is ContentPin and self.protocol.kind == "source", "Retain the exact independent protocol identity")
        _require(type(self.applicability) is Applicability and type(self.provenance) is Provenance, "Use typed dataset applicability and provenance")
        rows = _sequence(self, "replicates", self.replicates, Replicate, 32)
        _unique(tuple(row.id for row in rows))

    def body(self) -> JsonValue:
        return {"requirement": self.requirement, "protocol": self.protocol.to_data(), "applicability": self.applicability.to_data(),
                "replicates": [row.to_data() for row in self.replicates], "provenance": self.provenance.to_data()}

    @property
    def identity(self) -> ContentPin:
        return source_pin(self.id, self.version, self.body())

    def to_data(self) -> JsonValue:
        return _supplied(self.identity, self.body())


@dataclass(frozen=True, slots=True)
class AnalysisSoftware:
    name: str
    version: str
    artifact: Artifact

    def __post_init__(self) -> None:
        _text(self.name)
        _text(self.version)
        _require(type(self.artifact) is Artifact, "Retain analysis software artifact provenance")

    def to_data(self) -> JsonValue:
        return {"name": self.name, "version": self.version, "artifact": self.artifact.to_data()}


@dataclass(frozen=True, slots=True)
class Analysis:
    id: str
    version: str
    dataset: ContentPin
    replicate_ids: tuple[str, ...]
    envelope: Interval | None
    software: AnalysisSoftware
    provenance: Provenance

    def __post_init__(self) -> None:
        _text(self.id)
        _text(self.version)
        _require(type(self.dataset) is ContentPin and self.dataset.kind == "source", "Bind an independent dataset identity")
        values = _sequence(self, "replicate_ids", self.replicate_ids, str, 32)
        for value in values:
            _text(value)
        _unique(values)
        _require(self.envelope is None or type(self.envelope) is Interval, "Supply the independently calculated envelope explicitly")
        _require(type(self.software) is AnalysisSoftware and type(self.provenance) is Provenance, "Retain analysis software and provenance")

    def body(self) -> JsonValue:
        return {"dataset": self.dataset.to_data(), "method": "replicate_interval_envelope.v0.1", "replicate_ids": list(self.replicate_ids),
                "envelope": None if self.envelope is None else self.envelope.to_data(), "software": self.software.to_data(),
                "provenance": self.provenance.to_data()}

    @property
    def identity(self) -> ContentPin:
        return source_pin(self.id, self.version, self.body())

    def to_data(self) -> JsonValue:
        return _supplied(self.identity, self.body())


@dataclass(frozen=True, slots=True)
class Dossier:
    protocols: tuple[Protocol, ...] = ()
    datasets: tuple[Dataset, ...] = ()
    analyses: tuple[Analysis, ...] = ()

    def __post_init__(self) -> None:
        for name, kind in (("protocols", Protocol), ("datasets", Dataset), ("analyses", Analysis)):
            rows = _sequence(self, name, getattr(self, name), kind, 8)
            _unique(tuple(row.id for row in rows))
        _unique(tuple(row.requirement for row in self.datasets))
        _unique(tuple(fingerprint(row.dataset.to_data()) for row in self.analyses))

    def to_data(self) -> JsonValue:
        return {"protocols": [row.to_data() for row in self.protocols], "datasets": [row.to_data() for row in self.datasets],
                "analyses": [row.to_data() for row in self.analyses]}


@dataclass(frozen=True, slots=True)
class EvidenceContract:
    requirements: tuple[Requirement, ...]
    dossier: Dossier | None = None
    require_compatibility: bool = False

    def __post_init__(self) -> None:
        rows = _sequence(self, "requirements", self.requirements, Requirement, 8)
        _require(bool(rows), "Declare at least one parameter criterion")
        _unique(tuple(row.id for row in rows))
        _require(self.dossier is None or type(self.dossier) is Dossier, "Use a typed dossier or leave evidence absent")
        _require(type(self.require_compatibility) is bool, "Export gating must be explicit")
        encode_json(self.to_data(), limit=1048576)

    def to_data(self) -> JsonValue:
        return {"schema_version": SCHEMA, "profile": PROFILE, "require_compatibility": self.require_compatibility,
                "requirements": [row.to_data() for row in self.requirements],
                "dossier": None if self.dossier is None else self.dossier.to_data()}


def validate_assessment(report: JsonValue, contract: JsonValue, material_request: JsonValue,
                        material_report: JsonValue) -> None:
    """Reject altered serialized evidence; never reconstruct a native capability.

    This independently checks complete transport bindings, exact interval work,
    status consistency and claim boundaries. The caller must obtain the formal
    material assessment through its own fresh native service invocation.
    """
    try:
        _validate_assessment(report, contract, material_request, material_report)
    except CoreProtocolError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, ZeroDivisionError) as error:
        raise CoreProtocolError("Invalid realization evidence assessment transport") from error


def _validate_assessment(report_value: JsonValue, contract_value: JsonValue, material_request: JsonValue,
                         material_report: JsonValue) -> None:
    def require(condition: bool, message: str) -> None:
        if not condition:
            raise CoreProtocolError("Realization evidence: " + message)

    def exact(value: Any, keys: Iterable[str]) -> dict[str, Any]:
        require(type(value) is dict and set(value) == set(keys), "closed schema changed")
        return cast(dict[str, Any], value)

    def sequence(value: Any, maximum: int) -> list[Any]:
        require(type(value) is list and len(value) <= maximum, "bounded inventory changed")
        return cast(list[Any], value)

    def pin(raw: Any, kind: str) -> None:
        value = ContentPin.from_data(raw)
        require(value.kind == kind, "complete identity kind changed")

    def amount(raw: Any) -> tuple[Fraction, dict[str, Any]]:
        exact(raw, ("$type", "amount", "unit"))
        require(raw["$type"] == "Quantity", "complete quantity tag changed")
        unit = exact(raw["unit"], ("$type", "id", "dimension", "quantity_kind", "scale", "reference"))
        require(unit["$type"] == "Unit", "complete unit tag changed")
        for key in ("id", "dimension", "quantity_kind"):
            _text(unit[key])
        require(_decimal(unit["scale"]) > 0, "positive exact scale changed")
        if unit["reference"] is not None:
            _text(unit["reference"])
        return _decimal(raw["amount"]), unit

    def bounds(raw: Any) -> tuple[Fraction, Fraction, dict[str, Any]]:
        exact(raw, ("lower", "upper"))
        low, unit = amount(raw["lower"])
        high, upper_unit = amount(raw["upper"])
        require(unit == upper_unit and low <= high, "interval unit or order changed")
        return low, high, unit

    def application(raw: Any) -> None:
        exact(raw, ("recipient_fingerprint", "deployment_fingerprint", "clock_fingerprint", "operating_domain_fingerprint", "environment_fingerprints"))
        Applicability(**raw)

    def provenance_record(raw: Any) -> None:
        exact(raw, ("origin", "producer", "recorded_at", "artifact"))
        artifact_record(raw["artifact"])
        Provenance(raw["origin"], raw["producer"], raw["recorded_at"], Artifact(**raw["artifact"]))

    def artifact_record(raw: Any) -> None:
        exact(raw, ("id", "sha256", "media_type", "locator"))
        Artifact(**raw)

    def supplied(raw: Any, keys: Iterable[str]) -> dict[str, Any]:
        exact(raw, ("identity", "body"))
        pin(raw["identity"], "source")
        require(raw["identity"]["content_fingerprint"] == fingerprint(raw["body"]), "independent evidence body pin changed")
        exact(raw["body"], keys)
        provenance_record(raw["body"]["provenance"])
        return cast(dict[str, Any], raw["body"])

    for value in (report_value, contract_value, material_request, material_report):
        encode_json(value)
    contract = exact(contract_value, ("schema_version", "profile", "require_compatibility", "requirements", "dossier"))
    require(contract["schema_version"] == SCHEMA and contract["profile"] == PROFILE and type(contract["require_compatibility"]) is bool,
            "contract profile or explicit gating changed")
    requirements = sequence(contract["requirements"], 8)
    require(bool(requirements), "declared criteria absent")
    dossier = contract["dossier"]
    if dossier is None:
        protocols, datasets, analyses = [], [], []
    else:
        exact(dossier, ("protocols", "datasets", "analyses"))
        protocols, datasets, analyses = (sequence(dossier[key], 8) for key in ("protocols", "datasets", "analyses"))
    for target in requirements:
        exact(target, ("id", "instance", "component", "mechanism_fingerprint", "parameter", "nominal", "accepted_interval", "minimum_replicates", "applicability"))
        _text(target["id"])
        _text(target["instance"])
        pin(target["component"], "model")
        _hash(target["mechanism_fingerprint"])
        exact(target["parameter"], ("kind", "transfer"))
        require(target["parameter"]["kind"] == "transfer_amount", "parameter semantics changed")
        _text(target["parameter"]["transfer"])
        amount(target["nominal"])
        bounds(target["accepted_interval"])
        application(target["applicability"])
        require(type(target["minimum_replicates"]) is int and 2 <= target["minimum_replicates"] <= 32, "replicate criterion changed")
    _unique(tuple(row["id"] for row in requirements))
    for protocol in protocols:
        body = supplied(protocol, ("quantity_semantics", "sample_period", "procedure", "provenance"))
        require(body["quantity_semantics"] == "amount_per_accepted_sample", "amount became rate")
        period, unit = amount(body["sample_period"])
        require(period > 0 and unit["dimension"] == "time" and unit["quantity_kind"] == "duration" and unit["reference"] is None,
                "protocol period changed")
        _text(body["procedure"], 4096)
    for dataset in datasets:
        body = supplied(dataset, ("requirement", "protocol", "applicability", "replicates", "provenance"))
        _text(body["requirement"])
        pin(body["protocol"], "source")
        application(body["applicability"])
        for row in sequence(body["replicates"], 32):
            exact(row, ("id", "interval"))
            _text(row["id"])
            bounds(row["interval"])
        _unique(tuple(row["id"] for row in body["replicates"]))
    for analysis in analyses:
        body = supplied(analysis, ("dataset", "method", "replicate_ids", "envelope", "software", "provenance"))
        pin(body["dataset"], "source")
        require(body["method"] == "replicate_interval_envelope.v0.1", "analysis method changed")
        for value in sequence(body["replicate_ids"], 32):
            _text(value)
        _unique(tuple(body["replicate_ids"]))
        if body["envelope"] is not None:
            bounds(body["envelope"])
        software = exact(body["software"], ("name", "version", "artifact"))
        _text(software["name"])
        _text(software["version"])
        artifact_record(software["artifact"])
    for collection in (protocols, datasets, analyses):
        _unique(tuple(row["identity"]["id"] for row in collection))
    _unique(tuple(row["body"]["requirement"] for row in datasets))
    _unique(tuple(fingerprint(row["body"]["dataset"]) for row in analyses))

    current = Applicability.from_material_request(material_request).to_data()
    request = cast(dict[str, Any], material_request)
    selected = request.get("quantitative") if request["profile"] == "biocompiler.policy_sampled_transfer_network_component_mrna.v0.1" else None
    if request["profile"] == "biocompiler.policy_coupled_transfer_network_component_mrna.v0.1":
        selected = request["quantitative"]["network"]
    global_issues, global_states, expected_rows = [], [], []
    for data in datasets:
        if data["body"]["requirement"] not in [row["id"] for row in requirements]:
            global_issues.append("dataset_without_declared_requirement")
            global_states.append("incompatible")
    for analysis in analyses:
        if analysis["body"]["dataset"] not in [row["identity"] for row in datasets]:
            global_issues.append("analysis_without_exact_dataset")
            global_states.append("unassessed")

    def combine(states: list[str]) -> str:
        return "incompatible" if "incompatible" in states else "unassessed" if "unassessed" in states else "supported"

    for target in requirements:
        issues, states = [], []
        def mark(state: str, issue: str) -> None:
            states.append(state)
            issues.append(issue)
        if selected is None:
            mark("unassessed", "selected_mechanism_family_unassessed")
        else:
            selection, law = selected["selection"], selected["mechanism"]
            if target["instance"] != selection["instance"] or target["component"] != selection["component"]:
                mark("incompatible", "selected_component_identity_mismatch")
            if target["mechanism_fingerprint"] != fingerprint(law):
                mark("incompatible", "original_mechanism_identity_mismatch")
            edge = next((row for row in law["transfers"] if row["id"] == target["parameter"]["transfer"]), None)
            if edge is None:
                mark("incompatible", "selected_parameter_absent")
            elif target["nominal"] != edge["amount"]:
                mark("incompatible", "selected_nominal_parameter_mismatch")
            if target["nominal"]["unit"] != law["unit"]:
                mark("incompatible", "complete_parameter_unit_mismatch")
        if target["applicability"] != current:
            mark("incompatible", "original_applicability_identity_mismatch")
        nominal, unit = amount(target["nominal"])
        low, high, accepted_unit = bounds(target["accepted_interval"])
        if unit != accepted_unit or not low <= nominal <= high:
            mark("incompatible", "nominal_outside_declared_criterion")
        data = next((row for row in datasets if row["body"]["requirement"] == target["id"]), None)
        protocol = analysis = computed = None
        count, origins = 0, []
        if data is None:
            mark("unassessed", "measurement_dataset_absent")
        else:
            body = data["body"]
            if body["applicability"] != current:
                mark("unassessed", "measurement_environment_not_applicable")
            protocol = next((row for row in protocols if row["identity"] == body["protocol"]), None)
            if protocol is None:
                mark("unassessed", "exact_measurement_protocol_absent")
            elif selected is not None and protocol["body"]["sample_period"] != selected["mechanism"]["sample_period"]:
                mark("unassessed", "measurement_sampling_period_not_applicable")
            analysis = next((row for row in analyses if row["body"]["dataset"] == data["identity"]), None)
            replicates = body["replicates"]
            unit_ok = all(row["interval"]["lower"]["unit"] == unit for row in replicates)
            if not unit_ok:
                mark("incompatible", "complete_measurement_unit_mismatch")
            elif replicates:
                computed = {"lower": min((row["interval"]["lower"] for row in replicates), key=lambda q: Fraction(q["amount"])),
                            "upper": max((row["interval"]["upper"] for row in replicates), key=lambda q: Fraction(q["amount"]))}
            if analysis is None:
                mark("unassessed", "independent_analysis_absent")
            else:
                if analysis["body"]["replicate_ids"] != [row["id"] for row in replicates]:
                    mark("incompatible", "analysis_replicate_inventory_mismatch")
                declared = analysis["body"]["envelope"]
                if (computed is None) != (declared is None) or (computed is not None and bounds(computed) != bounds(declared)):
                    mark("incompatible", "independently_recomputed_envelope_mismatch")
            count = len(replicates)
            if count < target["minimum_replicates"]:
                mark("unassessed", "insufficient_supplied_replicates")
            applicable = body["applicability"] == current and protocol is not None and selected is not None and \
                protocol["body"]["sample_period"] == selected["mechanism"]["sample_period"]
            if applicable and unit_ok:
                for replicate in replicates:
                    lower, upper, _ = bounds(replicate["interval"])
                    if upper < low or lower > high:
                        mark("incompatible", "measurement_disjoint_from_criterion")
                    elif lower < low or upper > high:
                        mark("unassessed", "measurement_overlaps_criterion_boundary")
            origins = [row["body"]["provenance"]["origin"] for row in (data, protocol, analysis) if row is not None]
        expected_rows.append({"requirement": target, "status": combine(states), "issues": sorted(set(issues)),
            "protocol": protocol, "dataset": data, "analysis": analysis, "recomputed_envelope": computed,
            "replicates": count, "origins": sorted(set(origins))})
    status = combine([row["status"] for row in expected_rows] + global_states)
    expected = {"schema_version": "biocompiler.policy_realization_evidence_assessment.v0.1", "profile": PROFILE,
        "implementation": "biocompiler.ocaml.policy_realization_evidence_check.v0.1", "status": status,
        "claim_scope": "supplied_parameter_interval_compatibility", "request_fingerprint": fingerprint(material_request),
        "material_assessment_fingerprint": fingerprint(material_report), "contract_fingerprint": fingerprint(contract),
        "applicability": current, "require_compatibility": contract["require_compatibility"],
        "export_permitted": not contract["require_compatibility"] or status == "supported", "requirements": expected_rows,
        "issues": sorted(set(global_issues)), "empirical": "unassessed", "authenticity": "unassessed", "artifact_contents": "unassessed",
        "statistical_coverage": "not_inferred", "formal_prerequisites_discharged": []}
    report = exact(report_value, (*expected, "usage"))
    require(all(encode_json(report[key]) == encode_json(value) for key, value in expected.items()),
            "exact original binding, independent interval result or claim scope changed")
    usage = exact(report["usage"], ("unit", "charged_work"))
    require(usage["unit"] == "logical_data_visits_and_exact_interval_work" and type(usage["charged_work"]) is int
            and 0 <= usage["charged_work"] <= 64 * 1024 * 1024, "work accounting changed")

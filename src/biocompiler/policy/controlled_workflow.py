"""Immutable joined originals, explicit edits, and fresh native paired export.

These helpers edit supplied requirements and authority. They do not evaluate
activity, construct molecules, or derive mechanism parameters from desired results.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
import hashlib
from pathlib import Path
from typing import Callable, Iterable, TYPE_CHECKING, cast

from biocompiler.core_client import CoreProtocolError, JsonValue, decode_json, encode_json
from .controlled_behavior import ControlledBehaviorRequest
from .controlled_composition import ActivityDeadlines
from .material import _publish_fresh
from .model import Quantity
from .serialization import from_data, to_data

if TYPE_CHECKING:
    from biocompiler.core_policy_controlled_workflow import PolicyControlledWorkflowClient, PolicyControlledWorkflowResult


def _require(condition: object, message: str) -> None:
    if not condition:
        raise CoreProtocolError(message)


def _record(value: JsonValue) -> dict[str, JsonValue]:
    _require(type(value) is dict, "Controlled workflow authority requires an object")
    return cast(dict[str, JsonValue], value)


def _rows(value: JsonValue) -> list[JsonValue]:
    _require(type(value) is list, "Controlled workflow authority requires an array")
    return cast(list[JsonValue], value)


def _limits(behavior: ControlledBehaviorRequest) -> dict[str, JsonValue]:
    from biocompiler.core_policy_controlled_workflow import LIMITS_SCHEMA
    original = behavior.original.to_request()
    domain = _record(original["operating_domain"])
    return {"schema_version": LIMITS_SCHEMA, "budgets": original["budgets"],
            "domain_limits": domain["limits"], "horizon_tick": domain["horizon_tick"],
            "intervention_cutoff_tick": domain["intervention_cutoff_tick"], "resources": original["resources"]}


def _duration(original: dict[str, JsonValue], ticks: int) -> JsonValue:
    """Spell an edited tick count in the original clock unit without rounding."""
    resolution = from_data(_record(_record(original["operating_domain"])["clock"])["resolution"], Quantity)
    with localcontext() as context:
        context.prec = 300
        amount = Decimal(resolution.amount) * ticks
    return cast(JsonValue, to_data(Quantity(str(amount), resolution.unit)))


@dataclass(frozen=True, slots=True, init=False)
class ControlledWorkflowRequest:
    """Complete original authority; preparation never confers acceptance."""
    _json: bytes

    @classmethod
    def from_behavior(cls, behavior: ControlledBehaviorRequest) -> ControlledWorkflowRequest:
        from biocompiler.core_policy_controlled_workflow import REQUEST_SCHEMA
        _require(type(behavior) is ControlledBehaviorRequest, "An explicit typed behavior request is required")
        return cls.from_request({"schema_version": REQUEST_SCHEMA, "behavior_request": behavior.to_request(),
                                 "limits": _limits(behavior)})

    @classmethod
    def from_request(cls, request: JsonValue) -> ControlledWorkflowRequest:
        from biocompiler.core_policy_controlled_workflow import REQUEST_SCHEMA, _original
        snapshot = encode_json(request)
        row = _record(decode_json(snapshot))
        _require(set(row) == {"schema_version", "behavior_request", "limits"} and row["schema_version"] == REQUEST_SCHEMA,
                 "Controlled workflow request requires its exact versioned fields")
        behavior = ControlledBehaviorRequest.from_request(row["behavior_request"])
        _require(encode_json(row["limits"]) == encode_json(_limits(behavior)),
                 "Workflow limits differ from complete original authority")
        _original(row)
        value = object.__new__(cls)
        object.__setattr__(value, "_json", snapshot)
        return value

    def to_request(self) -> dict[str, JsonValue]:
        return _record(decode_json(self._json))

    @property
    def limits(self) -> dict[str, JsonValue]:
        return _record(self.to_request()["limits"])

    @property
    def behavior(self) -> ControlledBehaviorRequest:
        return ControlledBehaviorRequest.from_request(self.to_request()["behavior_request"])

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self._json).hexdigest()

    @property
    def native_status(self) -> str:
        return "not_performed"

    def with_rna_limits(self, *, max_member_rna_nt: int, max_total_rna_nt: int) -> ControlledWorkflowRequest:
        """Change requested size ceilings; preserve every supplied molecule."""
        behavior = self.behavior.to_request()
        resources = _record(_record(behavior["original"])["resources"])
        for key, value in (("max_member_rna_nt", max_member_rna_nt), ("max_total_rna_nt", max_total_rna_nt)):
            _require(type(value) is int and value > 0, "RNA limits require positive exact integers")
            resources[key] = value
        return self.from_behavior(ControlledBehaviorRequest.from_request(behavior))

    def with_deadlines(self, *, onset_ticks: int | None = None, controller_off_ticks: int | None = None,
                       antigen_off_ticks: int | None = None, component_off_ticks: int | None = None,
                       reactivation_ticks: int | None = None) -> ControlledWorkflowRequest:
        """Edit requested response bounds only; actual mechanism delays stay fixed."""
        behavior = self.behavior.to_request()
        original = _record(behavior["original"])
        source = _record(original["source_authority"])
        contract = _record(source["control_contract"])
        updates = {key: value for key, value in (("onset_ticks", onset_ticks),
            ("controller_off_ticks", controller_off_ticks), ("antigen_off_ticks", antigen_off_ticks),
            ("component_off_ticks", component_off_ticks), ("reactivation_ticks", reactivation_ticks)) if value is not None}
        deadlines = _record(contract["requested_deadlines"])
        deadlines.update(updates)
        ActivityDeadlines.from_data(deadlines)
        program = _record(_record(source["document"])["program"])
        definitions = [_record(raw) for raw in _rows(_record(program["semantics"])["definitions"])]
        markers = {"initial_activation": "onset_ticks", "controller_cessation": "controller_off_ticks",
                   "antigen_cessation": "antigen_off_ticks", "component_cessation": "component_off_ticks",
                   "reactivation": "reactivation_ticks"}
        found: set[str] = set()
        for raw in _rows(program["declarations"]):
            declaration = _record(raw)
            if declaration.get("$type") != "Requirement":
                continue
            reference = _record(declaration["contract"])
            matches = [definition for definition in definitions if definition.get("id") == reference["id"]
                       and definition.get("version") == reference["version"]]
            _require(len(matches) == 1, "Edited requirement must retain one complete definition")
            clauses = _rows(matches[0]["clauses"])
            _require(len(clauses) == 1, "Edited requirement must retain one interpreted clause")
            marker = _record(_record(clauses[0])["expression"]).get("value")
            for kind, key in markers.items():
                if marker == "biocompiler.controlled_source." + kind + ".v0.1" and key in updates:
                    _require(key not in found, "Duplicate edited source requirement")
                    declaration["deadline"] = _duration(original, updates[key])
                    found.add(key)
        _require(found == set(updates), "Requested deadline edit lacks its complete source requirement")
        _record(_record(original["operating_domain"])["source_deadlines"]).update(updates)
        return self.from_behavior(ControlledBehaviorRequest.from_request(behavior))

    def with_horizon(self, horizon_tick: int, *, readout_evidence: JsonValue,
                     operating_domain: JsonValue | None = None) -> ControlledWorkflowRequest:
        """Retain caller-supplied evidence/domain; never prune histories or invent samples."""
        _require(type(horizon_tick) is int and 1 <= horizon_tick <= 64, "Horizon requires an integral tick in 1..64")
        behavior = self.behavior.to_request()
        original = _record(behavior["original"])
        if operating_domain is not None:
            domain = _record(decode_json(encode_json(operating_domain)))
            _require(domain.get("horizon_tick") == horizon_tick, "Explicit domain differs from requested horizon")
            original["operating_domain"] = domain
        else:
            _record(original["operating_domain"])["horizon_tick"] = horizon_tick
        document = _record(_record(original["source_authority"])["document"])
        _record(document["assurance"])["horizon"] = _duration(original, horizon_tick)
        for raw in _rows(_record(document["program"])["declarations"]):
            declaration = _record(raw)
            if declaration.get("$type") == "Requirement":
                declaration["horizon"] = _duration(original, horizon_tick)
        behavior["readout_evidence"] = decode_json(encode_json(readout_evidence))
        return self.from_behavior(ControlledBehaviorRequest.from_request(behavior))

    def with_material_authority(self, authority: JsonValue) -> ControlledWorkflowRequest:
        """Replace complete supplied material; preserve expected products and mechanism."""
        behavior = self.behavior.to_request()
        _record(behavior["original"])["material_authority"] = decode_json(encode_json(authority))
        return self.from_behavior(ControlledBehaviorRequest.from_request(behavior))


def compile(request: ControlledWorkflowRequest, *, client: PolicyControlledWorkflowClient,
            cancelled: Callable[[], bool] | None = None) -> PolicyControlledWorkflowResult:
    return client.compile(request.to_request(), cancelled=cancelled)


def check(request: ControlledWorkflowRequest, *, candidate: JsonValue, client: PolicyControlledWorkflowClient,
          cancelled: Callable[[], bool] | None = None) -> PolicyControlledWorkflowResult:
    return client.check(request.to_request(), candidate, cancelled=cancelled)


def replay(request: ControlledWorkflowRequest, *, candidate: JsonValue, report: JsonValue,
           client: PolicyControlledWorkflowClient, cancelled: Callable[[], bool] | None = None) -> PolicyControlledWorkflowResult:
    return client.replay(request.to_request(), candidate, report, cancelled=cancelled)


def export(request: ControlledWorkflowRequest, *, candidate: JsonValue, client: PolicyControlledWorkflowClient,
           output: Path, input_paths: Iterable[Path] = (), replace: bool = False,
           cancelled: Callable[[], bool] | None = None) -> PolicyControlledWorkflowResult:
    from biocompiler.core_policy_controlled_workflow import ACCEPTED_STATUS, EXPORT
    return _publish_fresh(lambda: client.export(request.to_request(), candidate, cancelled=cancelled),
        operation=EXPORT, status=ACCEPTED_STATUS, output=output, input_paths=input_paths,
        replace=replace, cancelled=cancelled)

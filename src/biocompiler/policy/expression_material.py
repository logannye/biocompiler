"""Typed preparation and fresh publication of conditional static expression.

The supplied source, project declarations, expression contract, and exact
molecular authority remain original inputs. Preparing them establishes neither
native acceptance nor biological expression/localization.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from biocompiler.core_client import JsonValue
    from biocompiler.core_policy_expression_material import PolicyExpressionMaterialClient, PolicyExpressionMaterialResult
    from .model import BuildRequest


@dataclass(frozen=True, slots=True)
class ExpressionBudgets:
    max_work: int = 100_000_000
    max_report_bytes: int = 1_000_000
    max_report_nodes: int = 100_000

    def to_data(self) -> dict[str, JsonValue]:
        from biocompiler.core_policy_expression_material import RESOURCE_PROFILE, MAX_WORK, MAX_RESULT_BYTES, MAX_RESULT_NODES, _integer
        for label, value, maximum in (("max_work", self.max_work, MAX_WORK),
                                     ("max_report_bytes", self.max_report_bytes, MAX_RESULT_BYTES),
                                     ("max_report_nodes", self.max_report_nodes, MAX_RESULT_NODES)):
            _integer(value, label, maximum, minimum=1)
        return {"profile": RESOURCE_PROFILE, "max_work": self.max_work,
                "max_report_bytes": self.max_report_bytes, "max_report_nodes": self.max_report_nodes}


@dataclass(frozen=True, slots=True, init=False)
class ExpressionSelection:
    """Names and complete original implementation pin; never a selected capability."""
    _selection_json: bytes

    def __init__(self, *, objective: str, recipient: str, implementation: JsonValue, member: str, cds: str) -> None:
        from biocompiler.core_client import encode_json
        from biocompiler.core_policy_expression_material import _identity
        from biocompiler.core_policy import _text
        for label, value in (("objective", objective), ("recipient", recipient), ("member", member), ("cds", cds)):
            _text(value, label)
        _identity(implementation, "registry")
        object.__setattr__(self, "_selection_json", encode_json({"objective": objective, "recipient": recipient,
            "implementation": implementation, "member": member, "cds": cds}))

    def to_data(self) -> dict[str, JsonValue]:
        from biocompiler.core_client import decode_json
        return cast("dict[str, JsonValue]", decode_json(self._selection_json))


@dataclass(frozen=True, slots=True, init=False)
class ExpressionMaterialRequest:
    """Immutable complete original request with typed source and explicit premises."""
    _request_json: bytes

    def __init__(self, *, document: BuildRequest, selection: ExpressionSelection,
                 expression_contract: JsonValue, structure_authority: JsonValue,
                 project_context: JsonValue, budgets: ExpressionBudgets = ExpressionBudgets()) -> None:
        from biocompiler.core_client import decode_json, encode_json
        from biocompiler.core_policy_expression_material import REQUEST_SCHEMA, REQUEST_PROFILE, _original
        from .model import BuildRequest
        from .serialization import to_data
        if type(document) is not BuildRequest or type(selection) is not ExpressionSelection or type(budgets) is not ExpressionBudgets:
            raise TypeError("Expression preparation requires typed source, selection and budgets")
        value: JsonValue = {"schema_version": REQUEST_SCHEMA, "profile": REQUEST_PROFILE,
            "document": cast("JsonValue", to_data(document)), "selection": selection.to_data(), "expression_contract": expression_contract,
            "structure_authority": structure_authority, "project_context": project_context, "budgets": budgets.to_data()}
        snapshot = encode_json(value)
        _original(decode_json(snapshot))
        object.__setattr__(self, "_request_json", snapshot)

    @classmethod
    def from_request(cls, request: JsonValue) -> ExpressionMaterialRequest:
        """Import exact original bytes; representation checks grant no acceptance."""
        from biocompiler.core_client import decode_json, encode_json
        from biocompiler.core_policy_expression_material import _original
        from .model import BuildRequest
        from .serialization import from_data
        snapshot = encode_json(request)
        raw = _original(decode_json(snapshot))
        from_data(raw["document"], BuildRequest)
        value = object.__new__(cls)
        object.__setattr__(value, "_request_json", snapshot)
        return value

    def to_request(self) -> dict[str, JsonValue]:
        from biocompiler.core_client import decode_json
        return cast("dict[str, JsonValue]", decode_json(self._request_json))

    @property
    def document(self) -> BuildRequest:
        from .model import BuildRequest
        from .serialization import from_data
        return from_data(self.to_request()["document"], BuildRequest)

    @property
    def selection(self) -> ExpressionSelection:
        from biocompiler.core_policy_expression_material import _record
        raw = _record(self.to_request()["selection"], "Original selection")
        return ExpressionSelection(objective=cast(str, raw["objective"]), recipient=cast(str, raw["recipient"]),
            implementation=raw["implementation"], member=cast(str, raw["member"]), cds=cast(str, raw["cds"]))

    @property
    def budgets(self) -> ExpressionBudgets:
        from biocompiler.core_policy_expression_material import _record
        raw = _record(self.to_request()["budgets"], "Original budgets")
        return ExpressionBudgets(cast(int, raw["max_work"]), cast(int, raw["max_report_bytes"]), cast(int, raw["max_report_nodes"]))


def compile(request: ExpressionMaterialRequest, *, client: PolicyExpressionMaterialClient,
            cancelled: Callable[[], bool] | None = None) -> PolicyExpressionMaterialResult:
    return client.compile(request.to_request(), cancelled=cancelled)


def check(request: ExpressionMaterialRequest, *, candidate: JsonValue, client: PolicyExpressionMaterialClient,
          cancelled: Callable[[], bool] | None = None) -> PolicyExpressionMaterialResult:
    return client.check(request.to_request(), candidate, cancelled=cancelled)


def replay(request: ExpressionMaterialRequest, *, candidate: JsonValue, report: JsonValue,
           client: PolicyExpressionMaterialClient, cancelled: Callable[[], bool] | None = None) -> PolicyExpressionMaterialResult:
    return client.replay(request.to_request(), candidate, report, cancelled=cancelled)


def export(request: ExpressionMaterialRequest, *, candidate: JsonValue, client: PolicyExpressionMaterialClient,
           output: Path, input_paths: Iterable[Path] = (), replace: bool = False,
           cancelled: Callable[[], bool] | None = None) -> PolicyExpressionMaterialResult:
    """Fresh independent native export followed by exact atomic paired publication."""
    from .material import _publish_fresh
    return _publish_fresh(lambda: client.export(request.to_request(), candidate, cancelled=cancelled),
        operation="export-policy-expression-material", status="checked_expression_material", output=output,
        input_paths=input_paths, replace=replace, cancelled=cancelled)

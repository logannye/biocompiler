"""Typed original/readout authority snapshots and native behavior-only operations."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Callable, ClassVar, cast

from ..core_client import JsonValue, decode_json, encode_json
from ..core_policy_controlled_behavior import (
    REQUEST_SCHEMA, PolicyControlledBehaviorClient, PolicyControlledBehaviorResult, _original,
)
from .controlled_material import ControlledCompositionRequest


@dataclass(frozen=True, slots=True, init=False)
class ControlledBehaviorRequest:
    """No-I/O authority wrapper; construction of a snapshot confers no acceptance."""
    _json: bytes
    schema_version: ClassVar[str] = REQUEST_SCHEMA

    @classmethod
    def from_request(cls, request: JsonValue) -> ControlledBehaviorRequest:
        # Detach first; all validation and stored bytes concern the same object.
        detached = decode_json(encode_json(request))
        row = _original(detached)
        ControlledCompositionRequest.from_request(row["original"])
        value = object.__new__(cls)
        object.__setattr__(value, "_json", encode_json(row))
        return value

    @classmethod
    def from_original(cls, original: ControlledCompositionRequest, *, readout_evidence: JsonValue) -> ControlledBehaviorRequest:
        return cls.from_request({"schema_version": REQUEST_SCHEMA, "original": original.to_request(),
                                 "readout_evidence": readout_evidence})

    def to_request(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self._json))

    @property
    def original(self) -> ControlledCompositionRequest:
        return ControlledCompositionRequest.from_request(self.to_request()["original"])

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self._json).hexdigest()

    @property
    def native_status(self) -> str:
        return "not_performed"


def construct_behavior(request: ControlledBehaviorRequest, *, client: PolicyControlledBehaviorClient,
                       cancelled: Callable[[], bool] | None = None) -> PolicyControlledBehaviorResult:
    return client.construct_behavior(request.to_request(), cancelled=cancelled)


def check_behavior(request: ControlledBehaviorRequest, *, candidate: JsonValue, client: PolicyControlledBehaviorClient,
                   cancelled: Callable[[], bool] | None = None) -> PolicyControlledBehaviorResult:
    return client.check_behavior(request.to_request(), candidate, cancelled=cancelled)


def replay_behavior(request: ControlledBehaviorRequest, *, candidate: JsonValue, report: JsonValue,
                    client: PolicyControlledBehaviorClient, cancelled: Callable[[], bool] | None = None) -> PolicyControlledBehaviorResult:
    return client.replay_behavior(request.to_request(), candidate, report, cancelled=cancelled)

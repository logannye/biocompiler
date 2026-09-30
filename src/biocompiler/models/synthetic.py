"""Independent discrete-event runner for the synthetic mechanism fixture.

This bounded digital model is deliberately not a biological simulator. It does
not import, invoke or replay the behavior reference evaluator.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
import math
from numbers import Real
from types import MappingProxyType
from typing import Any, ClassVar

from biocompiler.errors import BiocompilerError
from biocompiler.ir.mechanism import MechanismProgram
from biocompiler.ir.serialization import JsonArtifact, fields, require

MODEL_RUNNER_VERSION = "biocompiler.synthetic.runner.v0.1"


class SyntheticModelError(BiocompilerError, ValueError):
    """Invalid inputs or undefined numerical execution in the synthetic model."""


def _number(value: Any, label: str, *, boolean: bool = False) -> bool | int | float:
    if type(value) is bool and boolean:
        return value
    if isinstance(value, bool) or not isinstance(value, Real):
        raise SyntheticModelError(
            f"{label} must be a finite real number"
            + (" or Boolean." if boolean else ".")
        )
    try:
        finite = math.isfinite(value)
    except (OverflowError, ValueError):
        finite = False
    if not finite:
        raise SyntheticModelError(f"{label} must be finite.")
    return int(value) if isinstance(value, int) else float(value)


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SyntheticModelError(f"{label} must be a nonempty string.")
    return value


def _values(data: Mapping, label: str) -> Mapping:
    if not isinstance(data, Mapping):
        raise SyntheticModelError(f"{label} must map node IDs to canonical values.")
    return MappingProxyType(
        {
            _id(key, "Node ID"): _number(value, "Signal value", boolean=True)
            for key, value in data.items()
        }
    )


@dataclass(frozen=True)
class ModelInputFrame:
    """A full atomic snapshot; numeric values use each port's canonical units."""

    time: float | int
    values: Mapping[str, bool | float | int] = field(default_factory=dict)
    contacts: Mapping[str, Mapping[str, bool | float | int]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        time = _number(self.time, "Model time")
        if time < 0:
            raise SyntheticModelError("Model time must be nonnegative.")
        object.__setattr__(self, "time", time)
        object.__setattr__(self, "values", _values(self.values, "values"))
        if not isinstance(self.contacts, Mapping):
            raise SyntheticModelError(
                "contacts must map object identities to snapshots."
            )
        object.__setattr__(
            self,
            "contacts",
            MappingProxyType(
                {
                    _id(identity, "Contact identity"): _values(values, "Contact values")
                    for identity, values in self.contacts.items()
                }
            ),
        )

    def to_dict(self) -> dict:
        return {
            "time": self.time,
            "values": dict(self.values),
            "contacts": {key: dict(value) for key, value in self.contacts.items()},
        }

    @classmethod
    def from_dict(cls, data: Mapping):
        fields(data, {"time", "values", "contacts"}, cls.__name__)
        return cls(data["time"], data["values"], data["contacts"])


@dataclass(frozen=True)
class ModelFrame(ModelInputFrame):
    """Settled public output values at a model input change, timer or horizon."""


@dataclass(frozen=True)
class ModelTrace(JsonArtifact):
    frames: tuple[ModelFrame, ...]
    horizon: float | int
    program_fingerprint: str
    model_version: str = MODEL_RUNNER_VERSION
    schema_version: ClassVar[str] = "biocompiler.synthetic.trace.v0.1"

    def __post_init__(self) -> None:
        require(
            isinstance(self.frames, (tuple, list)) and bool(self.frames),
            "A model trace needs a nonempty frame array.",
        )
        require(
            all(isinstance(frame, ModelFrame) for frame in self.frames),
            "A model trace requires ModelFrame records.",
        )
        object.__setattr__(self, "frames", tuple(self.frames))
        horizon = _number(self.horizon, "Model horizon")
        require(
            horizon >= 0
            and self.frames[0].time == 0
            and self.frames[-1].time == horizon,
            "A model trace must start at zero and end at its nonnegative horizon.",
        )
        require(
            all(
                left.time < right.time
                for left, right in zip(self.frames, self.frames[1:])
            ),
            "Model trace times must strictly increase.",
        )
        object.__setattr__(self, "horizon", horizon)
        require(
            isinstance(self.program_fingerprint, str)
            and len(self.program_fingerprint) == 64
            and all(char in "0123456789abcdef" for char in self.program_fingerprint),
            "A model trace requires a SHA-256 program fingerprint.",
        )
        require(
            self.model_version == MODEL_RUNNER_VERSION,
            "Unsupported synthetic model runner version.",
        )

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "frames": [frame.to_dict() for frame in self.frames],
            "horizon": self.horizon,
            "program_fingerprint": self.program_fingerprint,
            "model_version": self.model_version,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> ModelTrace:
        fields(
            data,
            {
                "schema_version",
                "frames",
                "horizon",
                "program_fingerprint",
                "model_version",
            },
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported model trace schema.",
        )
        require(
            isinstance(data["frames"], (tuple, list)), "Model frames must be an array."
        )
        return cls(
            tuple(ModelFrame.from_dict(frame) for frame in data["frames"]),
            data["horizon"],
            data["program_fingerprint"],
            data["model_version"],
        )


def _literal(value: Any) -> Any:
    return value["canonical_value"] if isinstance(value, Mapping) else value


class _ModelSession:
    def __init__(self, program: MechanismProgram):
        self.program = program
        self.nodes = {node.id: node for node in program.nodes}
        self.ordered = program.topological_nodes()
        self.inputs = {node.id: node for node in program.find("input")}
        self.snapshot = ModelInputFrame(0)
        self.delayed: dict[tuple[str, str | None], Any] = {}
        self.pending: dict[tuple[str, str | None], tuple[float | int, Any]] = {}

    def update(self, frame: ModelInputFrame) -> None:
        for identity, values in ((None, frame.values), *frame.contacts.items()):
            expected = {
                ref
                for ref, node in self.inputs.items()
                if (node.scope == "contact") == (identity is not None)
            }
            if set(values) != expected:
                missing, extra = (
                    sorted(expected - set(values)),
                    sorted(set(values) - expected),
                )
                raise SyntheticModelError(
                    f"Input snapshot for contact {identity!r} has missing {missing} or unknown/wrong-scope {extra} ports."
                )
            for ref, value in values.items():
                boolean = self.inputs[ref].output.dtype.kind == "condition"
                if boolean != (type(value) is bool):
                    raise SyntheticModelError(
                        f"Input {ref!r} requires {'a Boolean' if boolean else 'a canonical scalar'}, not {type(value).__name__}."
                    )
        disappeared = set(self.snapshot.contacts) - set(frame.contacts)
        for mapping in (self.delayed, self.pending):
            for key in tuple(mapping):
                if key[1] in disappeared:
                    del mapping[key]
        self.snapshot = frame

    def step(self, time: float | int) -> ModelFrame:
        values = {}
        identities = tuple(sorted(self.snapshot.contacts))
        for node in self.ordered:
            bindings = identities if node.scope == "contact" else (None,)
            for binding in bindings:
                key = (node.id, binding)

                def get(ref):
                    other = self.nodes[ref]
                    return values[(ref, binding if other.scope == "contact" else None)]

                if node.kind == "input":
                    value = (
                        self.snapshot.values[node.id]
                        if binding is None
                        else self.snapshot.contacts[binding][node.id]
                    )
                elif node.kind == "constant":
                    value = _literal(node.attributes["value"])
                elif node.kind == "any_contact":
                    value = any(
                        values[(node.inputs[0], identity)] for identity in identities
                    )
                elif node.kind in {"and", "or"}:
                    operands = [get(ref) for ref in node.inputs]
                    value = all(operands) if node.kind == "and" else any(operands)
                elif node.kind == "not":
                    value = not get(node.inputs[0])
                elif node.kind == "compare":
                    left, right = (get(ref) for ref in node.inputs)
                    value = {
                        "lt": lambda: left < right,
                        "le": lambda: left <= right,
                        "gt": lambda: left > right,
                        "ge": lambda: left >= right,
                        "eq": lambda: left == right,
                        "ne": lambda: left != right,
                    }[node.attributes["operator"]]()
                elif node.kind == "select":
                    value = get(
                        node.inputs[1] if get(node.inputs[0]) else node.inputs[2]
                    )
                elif node.kind == "output":
                    value = get(node.inputs[0])
                elif node.kind == "delay":
                    desired = get(node.inputs[0])
                    current = self.delayed.setdefault(
                        key, _literal(node.attributes["initial"])
                    )
                    pending = self.pending.get(key)
                    if desired == current:
                        self.pending.pop(key, None)
                    elif pending is not None and desired == pending[1]:
                        if pending[0] <= time:
                            current = desired
                            self.delayed[key] = desired
                            del self.pending[key]
                    else:
                        duration = node.attributes["duration"]["canonical_value"]
                        deadline = _number(time + duration, "Delay deadline")
                        if deadline <= time:
                            raise SyntheticModelError(
                                "A delay must advance the representable model time."
                            )
                        self.pending[key] = (deadline, desired)
                    value = current
                else:
                    raise SyntheticModelError(
                        f"Unsupported model operation {node.kind!r}."
                    )
                values[key] = value
        cell = {
            ref: values[(ref, None)]
            for ref in self.program.outputs
            if self.nodes[ref].scope == "cell"
        }
        contacts = {
            identity: {
                ref: values[(ref, identity)]
                for ref in self.program.outputs
                if self.nodes[ref].scope == "contact"
            }
            for identity in identities
        }
        return ModelFrame(time, cell, contacts)


def run_model(
    program: MechanismProgram,
    history: Iterable[ModelInputFrame],
    *,
    until: float | int | None = None,
) -> ModelTrace:
    """Run the independent inertial-delay fixture through an inclusive horizon.

    External changes are applied before timers at the same timestamp. Every
    delay starts with its declared value; a pending transition is canceled if
    the driving value returns to that value before or at the deadline. A new
    different value restarts the full delay. Contact disappearance clears the
    corresponding stored values and pending transitions.
    """
    if not isinstance(program, MechanismProgram):
        raise SyntheticModelError("run_model() requires a MechanismProgram.")
    try:
        frames = tuple(history)
    except TypeError as exc:
        raise SyntheticModelError(
            "Model history must be an iterable of ModelInputFrame records."
        ) from exc
    if not frames or any(not isinstance(frame, ModelInputFrame) for frame in frames):
        raise SyntheticModelError(
            "Model history requires ModelInputFrame records starting at zero."
        )
    if frames[0].time != 0 or any(
        left.time >= right.time for left, right in zip(frames, frames[1:])
    ):
        raise SyntheticModelError(
            "Model history must start at zero with strictly increasing times."
        )
    horizon = frames[-1].time if until is None else _number(until, "Model horizon")
    if horizon < 0:
        raise SyntheticModelError("Model horizon must be nonnegative.")
    session = _ModelSession(program)
    results = []
    index = 0
    time: float | int = 0
    while True:
        if index < len(frames) and frames[index].time == time:
            session.update(frames[index])
            index += 1
        results.append(session.step(time))
        if time == horizon:
            break
        candidates = [horizon]
        if index < len(frames) and frames[index].time <= horizon:
            candidates.append(frames[index].time)
        candidates.extend(
            deadline
            for deadline, _ in session.pending.values()
            if time < deadline <= horizon
        )
        time = min(candidates)
    return ModelTrace(tuple(results), horizon, program.fingerprint)

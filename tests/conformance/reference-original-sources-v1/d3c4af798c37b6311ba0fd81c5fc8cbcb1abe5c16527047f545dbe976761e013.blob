"""Finite-trace response checking against an independently executed synthetic model.

This is a bounded acceptance checker for supplied contracts and histories. It is
not universal refinement, a biological model, or an empirical validation tool.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, ClassVar

from biocompiler.errors import BiocompilerError, SerializationError
from biocompiler.ir.behavior import BehaviorProgram
from biocompiler.ir.intent import freeze_json
from biocompiler.ir.mechanism import MechanismProgram
from biocompiler.ir.serialization import JsonArtifact
from biocompiler.models.synthetic import (
    MODEL_RUNNER_VERSION,
    ModelInputFrame,
    run_model,
)
from biocompiler.semantics.context import TargetContext
from biocompiler.semantics.evaluator import (
    InputFrame,
    REFERENCE_EVALUATOR_VERSION,
    evaluate,
)
from biocompiler.semantics.realization import BehaviorContract, OperatingDomain
from biocompiler.semantics.types import BOOLEAN, Interval, TypeSpec
from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION
from biocompiler.verification.admission import admission_for_target
from biocompiler.verification.evidence import (
    CheckDiagnostic,
    CheckOutcome,
    CheckResult,
    Counterexample,
    DependencySnapshot,
    RequirementCoverage,
)

CHECKER_VERSION = "biocompiler.realization_checker.v0.3"
CHECKER_SETTINGS = freeze_json(
    {
        "scope": "supplied_contracts_and_finite_history",
        "intended_use": "software_test",
        "human_admission_policy": ADMISSION_POLICY_VERSION,
        "time": "right_continuous_piecewise_constant",
        "response": "active_inactive_bands_after_transition_deadlines",
        "nonvacuity": "checked_active_and_inactive_deadlines_for_every_response_and_complete_uncancelled_episodes",
        "contact_loss": "cancel_contact_scoped_obligations",
        "coverage": "all_selected_role_ongoing_outputs",
    }
)


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise SerializationError(message)


def _name(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _fields(data: Any, expected: set[str]) -> None:
    _require(
        isinstance(data, Mapping) and set(data) == expected,
        "Invalid observation-map fields.",
    )


def _hash(data: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            data, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class InputBinding:
    signal_id: str
    field: str
    mechanism_input_id: str

    def __post_init__(self) -> None:
        _require(
            _name(self.signal_id) and _name(self.mechanism_input_id),
            "Input binding IDs must be nonempty.",
        )
        _require(
            isinstance(self.field, str)
            and self.field in {"value", "present", "high", "low"},
            "Unknown observation field.",
        )

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "field": self.field,
            "mechanism_input_id": self.mechanism_input_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> InputBinding:
        _fields(data, {"signal_id", "field", "mechanism_input_id"})
        return cls(**data)


@dataclass(frozen=True)
class OutputBinding:
    requirement_id: str
    mechanism_output_id: str

    def __post_init__(self) -> None:
        _require(
            _name(self.requirement_id) and _name(self.mechanism_output_id),
            "Output binding IDs must be nonempty.",
        )

    def to_dict(self) -> dict:
        return {
            "requirement_id": self.requirement_id,
            "mechanism_output_id": self.mechanism_output_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> OutputBinding:
        _fields(data, {"requirement_id", "mechanism_output_id"})
        return cls(**data)


@dataclass(frozen=True)
class ObservationMap(JsonArtifact):
    inputs: tuple[InputBinding, ...]
    outputs: tuple[OutputBinding, ...]
    schema_version: ClassVar[str] = "biocompiler.observation_map.v0.1"

    def __post_init__(self) -> None:
        for name, expected in (("inputs", InputBinding), ("outputs", OutputBinding)):
            values = getattr(self, name)
            _require(
                isinstance(values, (tuple, list))
                and all(isinstance(value, expected) for value in values),
                f"Invalid {name} bindings.",
            )
            object.__setattr__(self, name, tuple(values))

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "inputs": [item.to_dict() for item in self.inputs],
            "outputs": [item.to_dict() for item in self.outputs],
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> ObservationMap:
        _fields(data, {"schema_version", "inputs", "outputs"})
        _require(
            data["schema_version"] == cls.schema_version,
            "Unsupported observation-map schema.",
        )
        _require(
            isinstance(data["inputs"], (list, tuple))
            and isinstance(data["outputs"], (list, tuple)),
            "Bindings must be arrays.",
        )
        return cls(
            tuple(InputBinding.from_dict(item) for item in data["inputs"]),
            tuple(OutputBinding.from_dict(item) for item in data["outputs"]),
        )


def _horizon(history: tuple[InputFrame, ...], until: Any) -> float | int:
    horizon = (history[-1].time if history else 0) if until is None else until
    try:
        valid = (
            type(horizon) in (int, float) and math.isfinite(horizon) and horizon >= 0
        )
    except (OverflowError, ValueError):
        valid = False
    if not valid:
        raise ValueError("Evaluation horizon must be a nonnegative finite number.")
    return horizon


def realization_dependencies(
    behavior: BehaviorProgram,
    contract: BehaviorContract,
    domain: OperatingDomain,
    target: TargetContext,
    mechanism: MechanismProgram,
    observation_map: ObservationMap,
    history: Iterable[InputFrame],
    *,
    until: float | int | None = None,
    core=None,
) -> DependencySnapshot:
    """Recompute the complete dependency identity without re-running the models."""
    frames = tuple(history)
    if any(not isinstance(frame, InputFrame) for frame in frames):
        raise TypeError("History must contain InputFrame objects.")
    if core is not None:
        from biocompiler.realization_backend import check_records
        return check_records(operation="realization-dependencies", core=core,
                             behavior=behavior, contract=contract, domain=domain, target=target,
                             mechanism=mechanism, observation_map=observation_map, history=frames, until=until)
    return DependencySnapshot(
        {
            "behavior": behavior.fingerprint,
            "behavior_artifact": _hash(behavior.to_dict()),
            "contract": contract.fingerprint,
            "domain": domain.fingerprint,
            "target": target.fingerprint,
            "mechanism": mechanism.fingerprint,
            "observation_map": observation_map.fingerprint,
            "history": _hash([frame.to_dict() for frame in frames]),
            "horizon": {"until": until, "effective": _horizon(frames, until)},
            "checker": CHECKER_VERSION,
            "model_runner": MODEL_RUNNER_VERSION,
            "reference_evaluator": REFERENCE_EVALUATOR_VERSION,
            "settings": {**CHECKER_SETTINGS, "max_microsteps": 1000},
        }
    )


def _runtime_observations(behavior: BehaviorProgram, role: str) -> set[tuple[str, str]]:
    nodes = {node.id: node for node in behavior.nodes}
    pending = [ref for ref in behavior.roots if nodes[ref].role in (None, role)]
    live = set()
    while pending:
        ref = pending.pop()
        if ref in live:
            continue
        live.add(ref)
        node = nodes[ref]
        pending.extend(node.inputs[:1] if node.kind == "signature" else node.inputs)
    required = set()
    for ref in live:
        node = nodes[ref]
        if node.role not in (None, role):
            continue
        if node.kind == "qualitative":
            required.add((node.inputs[0], node.attributes["band"]))
        elif node.kind not in {"signature", "scope", "role"}:
            required.update(
                (item, "value") for item in node.inputs if nodes[item].kind == "signal"
            )
    return required


def _same_observable(left: Any, right: Any) -> bool:
    return left.to_dict() == right.to_dict()


def _contains(interval: Interval, value: Any) -> bool:
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and interval.lower.canonical_value <= value <= interval.upper.canonical_value
    )


def check_realization(
    behavior: BehaviorProgram,
    contract: BehaviorContract,
    domain: OperatingDomain,
    target: TargetContext,
    mechanism: MechanismProgram,
    observation_map: ObservationMap,
    history: Iterable[InputFrame],
    *,
    until: float | int | None = None,
    core=None,
) -> CheckResult:
    """Check active/inactive response envelopes on the supplied finite history.

    Contacts preserve identity. Disappearance cancels their pending obligations;
    reappearance begins a new episode. Unexercised active or inactive responses
    and incomplete episodes yield UNKNOWN, never a vacuous PASS. Input-domain failures are UNKNOWN; structurally
    wrong mappings and observed violations are FAIL. Unsupported profiles remain
    explicit. No solver search, sequence generation or empirical claim is made.
    """
    for value, expected in (
        (behavior, BehaviorProgram),
        (contract, BehaviorContract),
        (domain, OperatingDomain),
        (target, TargetContext),
        (mechanism, MechanismProgram),
        (observation_map, ObservationMap),
    ):
        if not isinstance(value, expected):
            raise TypeError(
                f"Expected {expected.__name__}, got {type(value).__name__}."
            )
    frames = tuple(history)
    if core is not None:
        from biocompiler.realization_backend import check_records
        return check_records(operation="verify-realization", core=core,
                             behavior=behavior, contract=contract, domain=domain, target=target,
                             mechanism=mechanism, observation_map=observation_map, history=frames, until=until)
    deps = realization_dependencies(
        behavior,
        contract,
        domain,
        target,
        mechanism,
        observation_map,
        frames,
        until=until,
    )
    horizon = _horizon(frames, until)
    requirements = {item.id: item for item in contract.requirements}
    ids = tuple(requirements)
    nodes = {node.id: node for node in behavior.nodes}
    model_nodes = {node.id: node for node in mechanism.nodes}
    diagnostics = []

    def result(
        outcome, code=None, message=None, *, requirement=None, node=None, examples=()
    ):
        entries = list(diagnostics)
        if code:
            entries.append(
                CheckDiagnostic(
                    code,
                    message,
                    requirement,
                    node.id if node else None,
                    node.source if node else None,
                )
            )
        return CheckResult(outcome, deps, ids, tuple(entries), tuple(examples))

    admission = admission_for_target(target, boundary="verification")
    if admission.decision != "software_only":
        return result(
            CheckOutcome.UNSUPPORTED,
            "human_profile_not_admitted",
            "; ".join(admission.diagnostics),
        )

    if contract.behavior_fingerprint != behavior.fingerprint:
        return result(
            CheckOutcome.FAIL,
            "behavior_identity",
            "The response contract refers to a different BehaviorProgram.",
        )
    if domain.role not in nodes or nodes[domain.role].kind != "role":
        return result(
            CheckOutcome.FAIL,
            "role_identity",
            "OperatingDomain.role must identify an exact behavior role node.",
        )
    domain_inputs = {(item.signal_id, item.field): item for item in domain.inputs}
    if set(domain_inputs) != _runtime_observations(behavior, domain.role):
        return result(
            CheckOutcome.FAIL,
            "input_domain_coverage",
            "Operating-domain inputs must cover exactly the selected role's runtime observations, excluding unused signature metadata.",
        )
    inputs = {(item.signal_id, item.field): item for item in observation_map.inputs}
    if len(inputs) != len(observation_map.inputs) or set(inputs) != set(domain_inputs):
        return result(
            CheckOutcome.FAIL,
            "input_binding_coverage",
            "Input bindings must cover the operating-domain observations exactly once.",
        )
    model_input_ids = {node.id for node in mechanism.nodes if node.kind == "input"}
    mapped_input_ids = [item.mechanism_input_id for item in observation_map.inputs]
    if (
        len(set(mapped_input_ids)) != len(mapped_input_ids)
        or set(mapped_input_ids) != model_input_ids
    ):
        return result(
            CheckOutcome.FAIL,
            "model_input_coverage",
            "Every model input must have one distinct observation binding.",
        )
    for key, item in domain_inputs.items():
        source = nodes.get(item.signal_id)
        if source is None or source.kind != "signal" or source.role != domain.role:
            return result(
                CheckOutcome.FAIL,
                "input_source",
                "Input domain does not identify a signal owned by the selected role.",
            )
        expected_type = (
            TypeSpec.from_dict(source.data_type) if item.field == "value" else BOOLEAN
        )
        if (
            item.observable.role != domain.role
            or item.observable.scope != ("contact" if source.contact_bound else "cell")
            or not item.observable.dtype.compatible(expected_type)
        ):
            return result(
                CheckOutcome.FAIL,
                "input_semantics",
                "Input endpoint role, scope, or type differs from the authored observation.",
                node=source,
            )
        port = model_nodes[inputs[key].mechanism_input_id]
        if not _same_observable(item.observable, port.output):
            return result(
                CheckOutcome.FAIL,
                "input_endpoint",
                "Model input must match the domain's explicit endpoint identity, role, scope, compartment and type.",
                node=source,
            )
    outputs = {item.requirement_id: item for item in observation_map.outputs}
    mapped_output_ids = [item.mechanism_output_id for item in observation_map.outputs]
    if (
        len(outputs) != len(observation_map.outputs)
        or set(outputs) != set(requirements)
        or len(set(mapped_output_ids)) != len(mapped_output_ids)
        or set(mapped_output_ids) != set(mechanism.outputs)
    ):
        return result(
            CheckOutcome.FAIL,
            "output_binding_coverage",
            "Output bindings must match every requirement and declared model output one-to-one.",
        )
    for node in mechanism.nodes:
        if set(node.requirement_ids) - set(requirements):
            return result(
                CheckOutcome.FAIL,
                "unknown_model_requirement",
                f"Mechanism node {node.id!r} refers to an unknown response requirement.",
            )
    pairs = set()
    for requirement in requirements.values():
        rule = nodes.get(requirement.rule_id)
        specification = nodes.get(requirement.specification_id)
        if (
            rule is None
            or rule.kind != "rule"
            or rule.role != domain.role
            or specification is None
            or specification.id not in rule.inputs[2:]
        ):
            return result(
                CheckOutcome.FAIL,
                "requirement_source",
                "Response requirement must identify an installed rule and its exact action specification.",
                requirement=requirement.id,
            )
        pair = (rule.id, specification.id)
        if pair in pairs:
            return result(
                CheckOutcome.FAIL,
                "duplicate_response",
                "One action specification in one rule must have one response requirement.",
                requirement=requirement.id,
                node=rule,
            )
        pairs.add(pair)
        primitive = (
            nodes[specification.inputs[0]]
            if specification.kind == "action.pulse"
            else specification
        )
        if not primitive.attributes.get("ongoing"):
            return result(
                CheckOutcome.UNSUPPORTED,
                "instantaneous_response",
                "This profile checks ongoing requests and explicit pulses, not instantaneous reactions.",
                requirement=requirement.id,
                node=specification,
            )
        if (
            primitive.kind == "action.secrete"
            and primitive.attributes.get("rate") == "expression"
        ):
            return result(
                CheckOutcome.UNSUPPORTED,
                "quantitative_action_law",
                "A dynamic requested output rate needs a quantitative tracking contract beyond activation bands.",
                requirement=requirement.id,
                node=specification,
            )
        expected_scope = "contact" if specification.contact_bound else "cell"
        if (
            requirement.observable.role != domain.role
            or requirement.observable.scope != expected_scope
        ):
            return result(
                CheckOutcome.FAIL,
                "output_semantics",
                "Response endpoint role and scope must match the installed action.",
                requirement=requirement.id,
                node=specification,
            )
        model_output = model_nodes.get(outputs[requirement.id].mechanism_output_id)
        if (
            model_output is None
            or model_output.kind != "output"
            or not _same_observable(requirement.observable, model_output.output)
        ):
            return result(
                CheckOutcome.FAIL,
                "output_endpoint",
                "Model output must match the response's exact endpoint identity, role, scope, compartment and type.",
                requirement=requirement.id,
                node=specification,
            )
        if requirement.id not in model_output.requirement_ids:
            return result(
                CheckOutcome.FAIL,
                "missing_output_lineage",
                "Mapped model output must retain its response requirement identity.",
                requirement=requirement.id,
                node=specification,
            )
    installed = set()
    for rule in behavior.find(kind="rule", role=domain.role):
        for ref in rule.inputs[2:]:
            action = nodes[ref]
            if action.attributes.get("ongoing"):
                installed.add((rule.id, ref))
            elif action.kind != "action.state_set":
                return result(
                    CheckOutcome.UNSUPPORTED,
                    "instantaneous_output",
                    "The selected role has instantaneous output requests outside this response profile.",
                    node=action,
                )
    if pairs != installed:
        return result(
            CheckOutcome.UNSUPPORTED,
            "uncontracted_outputs",
            "The contract must cover every installed ongoing output of the selected role; this profile does not silently accept partial output coverage.",
        )
    capabilities = set(domain.required_capabilities) | set(
        mechanism.required_capabilities
    )
    if capabilities - set(target.capabilities):
        return result(
            CheckOutcome.FAIL,
            "missing_capabilities",
            "Target lacks declared capabilities: "
            + ", ".join(sorted(capabilities - set(target.capabilities))),
        )
    compartments = {node.output.compartment for node in mechanism.nodes}
    if compartments - set(target.compartments):
        return result(
            CheckOutcome.FAIL,
            "missing_compartments",
            "Target does not declare every model endpoint compartment.",
        )
    if any(node.output.role != domain.role for node in mechanism.nodes):
        return result(
            CheckOutcome.UNSUPPORTED,
            "multiple_model_roles",
            "This checker executes one engineered-cell role per finite trace.",
        )
    if not frames:
        return result(
            CheckOutcome.UNKNOWN,
            "empty_history",
            "No input history was supplied; no response was exercised.",
        )
    if frames[0].time != 0 or any(
        right.time <= left.time for left, right in zip(frames, frames[1:])
    ):
        return result(
            CheckOutcome.UNKNOWN,
            "invalid_history",
            "Input snapshots must start at zero and have strictly increasing timestamps.",
        )
    for frame in frames:
        if frame.time > horizon:
            continue
        if (
            domain.max_contacts is not None
            and len(frame.contacts) > domain.max_contacts
        ):
            return result(
                CheckOutcome.UNKNOWN,
                "outside_domain",
                "Input history exceeds the domain's maximum simultaneous contacts.",
            )
        for item in domain.inputs:
            samples = (
                list(frame.contacts.values())
                if item.scope == "contact"
                else [frame.signals]
            )
            for sample_set in samples:
                sample = sample_set.get(item.signal_id)
                value = getattr(sample, item.field, None)
                allowed = (
                    _contains(item.allowed, value)
                    if isinstance(item.allowed, Interval)
                    else type(value) is bool and value in item.allowed
                )
                if not allowed:
                    return result(
                        CheckOutcome.UNKNOWN,
                        "outside_domain",
                        f"Missing or out-of-domain {item.field} observation at time {frame.time}.",
                        node=nodes[item.signal_id],
                    )
    model_history = []
    for frame in frames:
        if frame.time > horizon:
            continue
        values, contacts = {}, {identity: {} for identity in frame.contacts}
        for key, binding in inputs.items():
            item = domain_inputs[key]
            if item.scope == "cell":
                values[binding.mechanism_input_id] = getattr(
                    frame.signals[item.signal_id], item.field
                )
            else:
                for identity, samples in frame.contacts.items():
                    contacts[identity][binding.mechanism_input_id] = getattr(
                        samples[item.signal_id], item.field
                    )
        model_history.append(ModelInputFrame(frame.time, values, contacts))
    try:
        desired = evaluate(behavior, frames, role=domain.role, until=horizon)
        actual = run_model(mechanism, model_history, until=horizon)
    except BiocompilerError as exc:
        return result(
            CheckOutcome.UNKNOWN,
            "execution_unavailable",
            f"The supplied history could not be evaluated: {exc}",
        )
    except (ValueError, ArithmeticError) as exc:
        return result(
            CheckOutcome.UNKNOWN,
            "execution_unavailable",
            f"The supplied history could not be evaluated: {exc}",
        )
    return _monitor(
        behavior,
        contract,
        domain,
        observation_map,
        frames,
        desired,
        actual,
        deps,
        horizon,
    )


def _at(frames, time):
    current = frames[0]
    for frame in frames[1:]:
        if frame.time > time:
            break
        current = frame
    return current


def _monitor(
    behavior,
    contract,
    domain,
    observation_map,
    history,
    desired,
    actual,
    dependencies,
    horizon,
):
    nodes = {node.id: node for node in behavior.nodes}
    outputs = {
        binding.requirement_id: binding.mechanism_output_id
        for binding in observation_map.outputs
    }
    base_times = sorted(
        {
            0,
            horizon,
            *(frame.time for frame in desired.frames),
            *(frame.time for frame in actual.frames),
            *(frame.time for frame in history if frame.time <= horizon),
        }
    )
    diagnostics, counterexamples = [], []
    requirements = tuple(item.id for item in contract.requirements)
    active_covered = {item.id: False for item in contract.requirements}
    counts = {
        item.id: {
            "activation_deadlines_checked": 0,
            "inactive_deadlines_checked": 0,
            "incomplete_episode_count": 0,
            "cancelled_episode_count": 0,
        }
        for item in contract.requirements
    }
    incomplete = set()
    if horizon < domain.minimum_horizon.canonical_value:
        diagnostics.append(
            CheckDiagnostic(
                "short_horizon",
                "The supplied horizon is shorter than the operating domain's required observation interval.",
            )
        )
    for requirement in contract.requirements:
        # Each contact appearance starts a new episode. Entries track desired
        # state, its onset and whether that active/inactive deadline was checked.
        episodes = {}
        times = set(base_times)
        processed = set()
        while times - processed:
            time = min(times - processed)
            processed.add(time)
            input_frame = _at(history, time)
            bindings = (
                set(input_frame.contacts)
                if requirement.observable.scope == "contact"
                else {None}
            )
            for vanished in set(episodes) - bindings:
                # Contact loss cancels pending obligations for that episode.
                if not episodes[vanished][2]:
                    counts[requirement.id]["cancelled_episode_count"] += 1
                del episodes[vanished]
            requests = _at(desired.frames, time).actions
            model_frame = _at(actual.frames, time)
            for binding in sorted(
                bindings, key=lambda value: "" if value is None else value
            ):
                enabled = any(
                    item.rule_id == requirement.rule_id
                    and item.specification_id == requirement.specification_id
                    and item.contact_id == binding
                    for item in requests
                )
                previous = episodes.get(binding)
                if previous is None or previous[0] != enabled:
                    if previous is not None and not previous[2]:
                        incomplete.add(requirement.id)
                        counts[requirement.id]["incomplete_episode_count"] += 1
                    delay = (
                        requirement.max_activation_delay
                        if enabled
                        else requirement.max_deactivation_delay
                    )
                    deadline = time + delay.canonical_value
                    if (
                        not math.isfinite(deadline)
                        or delay.canonical_value > 0
                        and deadline <= time
                    ):
                        diagnostics.append(
                            CheckDiagnostic(
                                "numeric_resolution",
                                "A response delay cannot be represented as a finite later deadline at this timestamp.",
                                requirement.id,
                                requirement.specification_id,
                                nodes[requirement.specification_id].source,
                            )
                        )
                        deadline = math.inf
                    episodes[binding] = [enabled, deadline, False]
                    if deadline <= horizon:
                        times.add(deadline)
                episode = episodes[binding]
                if time < episode[1]:
                    continue
                interval = (
                    requirement.active_range if enabled else requirement.inactive_range
                )
                samples = (
                    model_frame.values
                    if binding is None
                    else model_frame.contacts.get(binding, {})
                )
                value = samples.get(outputs[requirement.id])
                if not episode[2]:
                    counts[requirement.id][
                        "activation_deadlines_checked"
                        if enabled
                        else "inactive_deadlines_checked"
                    ] += 1
                    episode[2] = True
                if enabled:
                    active_covered[requirement.id] = True
                if not _contains(interval, value):
                    counterexamples.append(
                        Counterexample(
                            requirement.id,
                            time,
                            binding,
                            {
                                "state": "active" if enabled else "inactive",
                                "range": interval.to_dict(),
                            },
                            value,
                            requirement.rule_id,
                            requirement.specification_id,
                            nodes[requirement.specification_id].source,
                        )
                    )
        if any(not entry[2] for entry in episodes.values()):
            incomplete.add(requirement.id)
            counts[requirement.id]["incomplete_episode_count"] += sum(
                not entry[2] for entry in episodes.values()
            )
    coverage = tuple(
        RequirementCoverage(item.id, **counts[item.id])
        for item in contract.requirements
    )
    if counterexamples:
        diagnostics.append(
            CheckDiagnostic(
                "response_violation",
                "Independent model outputs violate one or more response envelopes after their deadlines.",
            )
        )
        return CheckResult(
            CheckOutcome.FAIL,
            dependencies,
            requirements,
            tuple(diagnostics),
            tuple(counterexamples),
            coverage=coverage,
        )
    for requirement in contract.requirements:
        if not active_covered[requirement.id]:
            diagnostics.append(
                CheckDiagnostic(
                    "unexercised_response",
                    "No active response deadline was exercised for this requirement.",
                    requirement.id,
                    requirement.specification_id,
                    nodes[requirement.specification_id].source,
                )
            )
        if counts[requirement.id]["inactive_deadlines_checked"] == 0:
            diagnostics.append(
                CheckDiagnostic(
                    "unexercised_inactive_response",
                    "No inactive response deadline was exercised for this requirement.",
                    requirement.id,
                    requirement.specification_id,
                    nodes[requirement.specification_id].source,
                )
            )
        if requirement.id in incomplete:
            diagnostics.append(
                CheckDiagnostic(
                    "incomplete_episode",
                    "A response episode ended or the horizon was reached before its response deadline could be checked.",
                    requirement.id,
                    requirement.specification_id,
                    nodes[requirement.specification_id].source,
                )
            )
    outcome = CheckOutcome.UNKNOWN if diagnostics else CheckOutcome.PASS
    return CheckResult(
        outcome, dependencies, requirements, tuple(diagnostics), coverage=coverage
    )

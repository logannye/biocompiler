"""Frozen human circuit requirements, supplementary to complete source authority.

These contracts preserve declared intent. They do not select mechanisms, emit
molecules, establish source fidelity or admit a therapeutic deployment. Boolean
TRUE/FALSE requests the output observation's declared HIGH/LOW respectively.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from biocompiler.compiler.acceptance import HumanAcceptanceRequest
from biocompiler.compiler.deployment import HumanDeploymentRequest
from biocompiler.compiler.request import BuildRequest
from biocompiler.ir.circuit_logic import BooleanSpec, MAX_BOOLEAN_INPUTS
from biocompiler.ir.circuit_observations import (
    CircuitObservation,
    CircuitProduct,
    ObservationEntity,
    ObservationScope,
    ObservationWindow,
)
from biocompiler.ir.circuit_profile import (
    CircuitProfileRequest,
    HumanExperimentContext,
    _ProfileRecord,
    _choice,
    _optional,
    _text,
)
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.intent import SourceLocation
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.semantics.context import PayloadFormat


MAX_REQUIREMENTS = 32
MAX_PROVIDERS = 32
REQUESTED_FORMS = frozenset(
    {
        "delivered_dna",
        "dna_expression_template",
        "primary_rna",
        "delivered_rna",
        "processed_rna",
        "circular_rna",
    }
)
FIDELITY_SCOPES = frozenset({"base_identity", "source_nominal", "complete_nominal"})


def same_authority(left, right):
    """Compare canonical bytes as well as structure (1 differs from 1.0)."""
    return (
        fingerprint(left.to_dict()) == fingerprint(right.to_dict())
        and left.to_dict() == right.to_dict()
    )


def source_build_request(source):
    return source if isinstance(source, BuildRequest) else source.build_request


def source_deployment(source):
    if isinstance(source, HumanAcceptanceRequest):
        return source.deployment_request.deployment
    if isinstance(source, HumanDeploymentRequest):
        return source.deployment
    return None


def _records(values, cls, maximum, label, *, key="id", nonempty=False):
    require(isinstance(values, (tuple, list)), f"{label} must be an array.")
    require(int(nonempty) <= len(values) <= maximum, f"Invalid {label} count.")
    require(all(isinstance(item, cls) for item in values), f"Invalid {label} type.")
    result = tuple(cls.from_dict(item.to_dict()) for item in values)
    identities = [getattr(item, key) for item in result]
    require(len(set(identities)) == len(identities), f"Duplicate {label} identities.")
    return tuple(sorted(result, key=lambda item: getattr(item, key)))


def _decode_records(cls, maximum):
    def decode(values):
        require(
            isinstance(values, (tuple, list)) and len(values) <= maximum,
            "Invalid circuit record array.",
        )
        return tuple(cls.from_dict(value) for value in values)

    return decode


def _pins(values):
    pins = _records(values, PinnedIdentity, 16, "authority pins", nonempty=True)
    require(
        all(pin.kind in {"source", "evidence"} for pin in pins),
        "Authority requires source/evidence pins.",
    )
    return pins


def _realization(value):
    require(
        isinstance(value, PinnedIdentity) and value.kind in {"reference", "model"},
        "Selected realization requires a reference/model identity.",
    )


def _form(form, fidelity):
    _choice(form, REQUESTED_FORMS, "requested molecular form")
    _choice(fidelity, FIDELITY_SCOPES, "requested fidelity scope")


@dataclass(frozen=True)
class CircuitLifecycle(_ProfileRecord):
    mode: str
    onset: ObservationWindow | None = None
    cessation: ObservationWindow | None = None
    clearance: ObservationWindow | None = None
    schema_version: ClassVar[str] = "biocompiler.circuit_lifecycle.v0.1"
    _decoders: ClassVar[dict] = dict.fromkeys(
        ("onset", "cessation", "clearance"), _optional(ObservationWindow)
    )

    def __post_init__(self):
        _choice(
            self.mode,
            {"production_control", "abundance_control", "activity_control", "readout"},
            "output lifecycle mode",
        )
        for key in ("onset", "cessation", "clearance"):
            value = getattr(self, key)
            require(
                value is None or isinstance(value, ObservationWindow),
                "Expected a declared lifecycle window or unreported None.",
            )
        self._check_resources()


@dataclass(frozen=True)
class CircuitProviderRequirement(_ProfileRecord):
    id: str
    entity: ObservationEntity
    kind: str
    compartment: str
    colocation_group: str
    availability: str = "unestablished"
    schema_version: ClassVar[str] = "biocompiler.circuit_provider_requirement.v0.1"
    _decoders: ClassVar[dict] = {"entity": ObservationEntity.from_dict}

    def __post_init__(self):
        for key in ("id", "compartment", "colocation_group"):
            _text(getattr(self, key), key)
        require(
            isinstance(self.entity, ObservationEntity),
            "Expected provider molecular identity.",
        )
        require(
            self.compartment != "abstract", "Provider requires a physical compartment."
        )
        _choice(self.kind, {"host", "co_delivered", "external_input"}, "provider kind")
        _choice(
            self.availability, {"unestablished", "declared"}, "provider availability"
        )
        self._check_resources()


@dataclass(frozen=True)
class CircuitBehavior(_ProfileRecord):
    inputs: tuple[CircuitObservation, ...]
    response: BooleanSpec
    output: CircuitProduct
    lifecycle: CircuitLifecycle
    dependencies: tuple[CircuitProviderRequirement, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.circuit_behavior.v0.1"
    _decoders: ClassVar[dict] = {
        "inputs": _decode_records(CircuitObservation, MAX_BOOLEAN_INPUTS),
        "response": BooleanSpec.from_dict,
        "output": CircuitProduct.from_dict,
        "lifecycle": CircuitLifecycle.from_dict,
        "dependencies": _decode_records(CircuitProviderRequirement, MAX_PROVIDERS),
    }

    def __post_init__(self):
        object.__setattr__(
            self,
            "inputs",
            _records(
                self.inputs, CircuitObservation, MAX_BOOLEAN_INPUTS, "observations"
            ),
        )
        require(
            isinstance(self.response, BooleanSpec),
            "Expected a canonical Boolean response.",
        )
        require(
            isinstance(self.output, CircuitProduct), "Expected a typed circuit product."
        )
        require(
            isinstance(self.lifecycle, CircuitLifecycle),
            "Expected explicit output lifecycle.",
        )
        object.__setattr__(
            self,
            "dependencies",
            _records(
                self.dependencies,
                CircuitProviderRequirement,
                MAX_PROVIDERS,
                "providers",
            ),
        )
        require(
            tuple(item.id for item in self.inputs)
            == tuple(item.id for item in self.response.inputs),
            "Boolean inputs must bind exactly the declared observations, including unused inputs.",
        )
        for observation, signal in zip(self.inputs, self.response.inputs):
            require(
                observation.fingerprint == signal.observation_fingerprint,
                "Stale or different nominal input observation binding.",
            )
            require(
                observation.scope is ObservationScope.CELL_ACCESSIBLE,
                "Circuit inputs must declare cell-accessible sensing; evaluator/external observations are not cellular sensors.",
            )
        modes = {
            "protein_expression": "production_control",
            "rna_product": "production_control",
            "mature_protein_quantity": "abundance_control",
            "biological_activity": "activity_control",
            "reporter_fluorescence": "readout",
        }
        require(
            self.lifecycle.mode == modes[self.output.kind],
            "Output product and lifecycle mode disagree.",
        )
        require(
            self.output.observation.id not in {item.id for item in self.inputs},
            "Feedback cannot be represented as a combinational observation alias.",
        )
        self._check_resources()


@dataclass(frozen=True)
class CircuitInputBinding(_ProfileRecord):
    """Declared correspondence from one observation to an original source node.

    This retains the author's association, without asserting that the source
    node implements a sensing mechanism or matches the observation physically.
    """

    observation_id: str
    source_node_id: str
    schema_version: ClassVar[str] = "biocompiler.circuit_input_binding.v0.1"

    def __post_init__(self):
        _text(self.observation_id, "Bound circuit observation identity")
        _text(self.source_node_id, "Bound original source node identity")
        self._check_resources()


@dataclass(frozen=True)
class CircuitRequirement(_ProfileRecord):
    id: str
    behavior: CircuitBehavior
    role_id: str | None
    source_node_ids: tuple[str, ...]
    source_location: SourceLocation | None
    input_bindings: tuple[CircuitInputBinding, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.circuit_requirement.v0.1"
    _decoders: ClassVar[dict] = {
        "behavior": CircuitBehavior.from_dict,
        "source_location": _optional(SourceLocation),
        "input_bindings": _decode_records(CircuitInputBinding, MAX_BOOLEAN_INPUTS),
    }

    def __post_init__(self):
        _text(self.id, "Circuit requirement identity")
        require(
            isinstance(self.behavior, CircuitBehavior), "Expected a circuit behavior."
        )
        if self.role_id is not None:
            _text(self.role_id, "Circuit source role")
        require(
            isinstance(self.source_node_ids, (tuple, list))
            and len(self.source_node_ids) <= 128,
            "Invalid source-node inventory.",
        )
        for ref in self.source_node_ids:
            _text(ref, "Source node reference")
        require(
            len(set(self.source_node_ids)) == len(self.source_node_ids),
            "Duplicate source references.",
        )
        object.__setattr__(self, "source_node_ids", tuple(sorted(self.source_node_ids)))
        object.__setattr__(
            self,
            "input_bindings",
            _records(
                self.input_bindings,
                CircuitInputBinding,
                MAX_BOOLEAN_INPUTS,
                "input source bindings",
                key="observation_id",
            ),
        )
        observation_ids = {item.id for item in self.behavior.inputs}
        for binding in self.input_bindings:
            require(
                binding.observation_id in observation_ids,
                "Input source binding must name a declared behavior observation.",
            )
            require(
                binding.source_node_id in self.source_node_ids,
                "Input source binding must retain its original source-node reference.",
            )
        require(
            self.source_location is None
            or isinstance(self.source_location, SourceLocation),
            "Expected source location or explicit unknown.",
        )
        self._check_resources()


@dataclass(frozen=True)
class CircuitBehaviorExpectation(_ProfileRecord):
    requirement_id: str
    behavior: CircuitBehavior
    schema_version: ClassVar[str] = "biocompiler.circuit_behavior_expectation.v0.1"
    _decoders: ClassVar[dict] = {"behavior": CircuitBehavior.from_dict}

    def __post_init__(self):
        _text(self.requirement_id, "Expected requirement identity")
        require(
            isinstance(self.behavior, CircuitBehavior),
            "Expected complete behavior authority.",
        )
        self._check_resources()


@dataclass(frozen=True)
class CircuitReferenceLock(_ProfileRecord):
    """Declared external authority, not certification of a published mechanism."""

    expected_behaviors: tuple[CircuitBehaviorExpectation, ...]
    realization: PinnedIdentity
    authority: tuple[PinnedIdentity, ...]
    source_experiment: HumanExperimentContext
    requested_form: str
    fidelity_scope: str
    schema_version: ClassVar[str] = "biocompiler.circuit_reference_lock.v0.1"
    _decoders: ClassVar[dict] = {
        "expected_behaviors": _decode_records(
            CircuitBehaviorExpectation, MAX_REQUIREMENTS
        ),
        "realization": PinnedIdentity.from_dict,
        "authority": _decode_records(PinnedIdentity, 16),
        "source_experiment": HumanExperimentContext.from_dict,
    }

    def __post_init__(self):
        object.__setattr__(
            self,
            "expected_behaviors",
            _records(
                self.expected_behaviors,
                CircuitBehaviorExpectation,
                MAX_REQUIREMENTS,
                "expected behaviors",
                key="requirement_id",
                nonempty=True,
            ),
        )
        _realization(self.realization)
        object.__setattr__(self, "authority", _pins(self.authority))
        require(
            isinstance(self.source_experiment, HumanExperimentContext),
            "Reference lock requires original human experiment context.",
        )
        require(
            all(
                any(same_authority(pin, known) for known in self.authority)
                for pin in self.source_experiment.sources
            ),
            "Reference lock must retain experiment source pins.",
        )
        _form(self.requested_form, self.fidelity_scope)
        self._check_resources()


@dataclass(frozen=True)
class CircuitRequest(_ProfileRecord):
    profile: CircuitProfileRequest
    requirements: tuple[CircuitRequirement, ...]
    requested_form: str
    fidelity_scope: str
    deployment_id: str | None
    selected_realization: PinnedIdentity | None = None
    reference_lock: CircuitReferenceLock | None = None
    schema_version: ClassVar[str] = "biocompiler.circuit_request.v0.1"
    _decoders: ClassVar[dict] = {
        "profile": CircuitProfileRequest.from_dict,
        "requirements": _decode_records(CircuitRequirement, MAX_REQUIREMENTS),
        "selected_realization": _optional(PinnedIdentity),
        "reference_lock": _optional(CircuitReferenceLock),
    }

    def __post_init__(self):
        require(
            isinstance(self.profile, CircuitProfileRequest),
            "Expected complete human circuit scope authority.",
        )
        object.__setattr__(
            self, "profile", CircuitProfileRequest.from_dict(self.profile.to_dict())
        )
        object.__setattr__(
            self,
            "requirements",
            _records(
                self.requirements,
                CircuitRequirement,
                MAX_REQUIREMENTS,
                "requirements",
                nonempty=True,
            ),
        )
        product_ids = set()
        output_observation_ids = set()
        shared_inputs = {}
        for requirement in self.requirements:
            role = requirement.role_id
            output = requirement.behavior.output
            product_key = (role, output.id)
            observation_key = (role, output.observation.id)
            require(
                product_key not in product_ids,
                "Output product IDs must be unique within each role; express multiple conditions in one BooleanSpec.",
            )
            require(
                observation_key not in output_observation_ids,
                "Output observation IDs must be unique within each role; express multiple conditions in one BooleanSpec.",
            )
            product_ids.add(product_key)
            output_observation_ids.add(observation_key)
            for observation in requirement.behavior.inputs:
                key = (role, observation.id)
                previous = shared_inputs.get(key)
                require(
                    previous is None or same_authority(previous, observation),
                    "Shared input observation IDs must retain identical nominal authority within a role.",
                )
                shared_inputs[key] = observation
        _form(self.requested_form, self.fidelity_scope)
        is_dna = self.requested_form in {"delivered_dna", "dna_expression_template"}
        require(
            is_dna == (self.profile.molecular_form is PayloadFormat.DNA),
            "Requested form must preserve the declared DNA/RNA modality; no implicit transcription.",
        )
        if self.selected_realization is not None:
            _realization(self.selected_realization)
        if self.profile.purpose == "human_immune_payload":
            _text(self.deployment_id, "Explicit intended deployment identity")
            require(
                self.profile.source_request is not None,
                "Circuit products require the complete original frozen source request.",
            )
            source = self.profile.source_request
            nodes = {
                node.id: node for node in source_build_request(source).intent.nodes
            }
            deployment = source_deployment(source)
            if deployment is not None:
                require(
                    self.deployment_id == deployment.id,
                    "Circuit deployment identity must retain original deployment authority.",
                )
            for requirement in self.requirements:
                role = nodes.get(requirement.role_id)
                require(
                    role is not None
                    and role.kind == "role"
                    and role.attributes.get("engineering") == "in_vivo",
                    "Product requirements must bind an original in-vivo engineered role.",
                )
                require(
                    requirement.role_id in requirement.source_node_ids,
                    "Source bindings must include the original executing role.",
                )
                for ref in requirement.source_node_ids:
                    require(
                        ref in nodes
                        and (
                            ref == requirement.role_id
                            or (
                                nodes[ref].kind != "role"
                                and nodes[ref].role in (None, requirement.role_id)
                            )
                        ),
                        "Missing or different-role source-node binding.",
                    )
                if deployment is not None:
                    require(
                        requirement.role_id == deployment.recipient_role,
                        "Circuit role must preserve original deployment recipient.",
                    )
                behavior = requirement.behavior
                for item in (
                    *behavior.inputs,
                    behavior.output.observation,
                    *behavior.dependencies,
                ):
                    require(
                        item.compartment in self.profile.target.compartments,
                        "Circuit observation/provider must use a declared target compartment.",
                    )
        else:
            require(
                self.deployment_id is None,
                "Human references cannot invent a deployment identity.",
            )
            require(
                all(
                    item.role_id is None
                    and not item.source_node_ids
                    and not item.input_bindings
                    for item in self.requirements
                ),
                "Human references use source-experiment authority, not invented therapeutic roles.",
            )
        if self.profile.mode == "exact_reproduction":
            lock = self.reference_lock
            require(
                isinstance(lock, CircuitReferenceLock),
                "Exact reproduction requires a complete declared reference lock.",
            )
            require(
                self.selected_realization is not None
                and same_authority(self.selected_realization, lock.realization),
                "Selected realization differs from locked authority.",
            )
            require(
                self.profile.source_experiment is not None
                and same_authority(
                    self.profile.source_experiment, lock.source_experiment
                ),
                "Original experiment context differs from locked authority.",
            )
            require(
                self.requested_form == lock.requested_form
                and self.fidelity_scope == lock.fidelity_scope,
                "Form or fidelity differs from locked authority.",
            )
            expected = {
                item.requirement_id: item.behavior for item in lock.expected_behaviors
            }
            require(
                set(expected) == {item.id for item in self.requirements},
                "Reference lock must cover exactly all requirements.",
            )
            for item in self.requirements:
                require(
                    same_authority(item.behavior, expected[item.id]),
                    "Circuit behavior differs from declared reference lock; select a candidate mode or retain original behavior.",
                )
        else:
            require(
                self.reference_lock is None,
                "Candidate designs cannot retain exact-reference authority locks.",
            )
        self._check_resources()

"""Checked, in-memory pass orchestration with transitive dependency freshness.

Pass registration is trusted compiler configuration; producer output is not.
Records are inspection artifacts, never imported acceptance certificates. Every
read of an accepted stage rechecks its complete dependency ancestry.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from biocompiler.artifacts.provenance import SourceLink
from biocompiler.compiler.passes import PassResult
from biocompiler.errors import BiocompilerError
from biocompiler.ir.intent import freeze_json, thaw_json
from biocompiler.ir.serialization import fingerprint, name, names, require
from biocompiler.ir.stages import Stage, STAGE_ORDER
from biocompiler.semantics.context import PayloadFormat, TargetContext
from biocompiler.verification.evidence import CheckOutcome, EvidenceKind


class PipelineError(BiocompilerError, ValueError):
    """A stage has missing providers, stale dependencies or failed checks."""


class NoCandidateFound(PipelineError):
    """This configured search found no candidate; infeasibility is not established."""

    def __init__(self, pass_id, configuration, dependencies):
        self.pass_id = pass_id
        self.configuration = freeze_json(configuration)
        self.dependencies = freeze_json(dependencies)
        super().__init__(
            f"No candidate found within search {pass_id!r}; infeasibility is not established."
        )


class ArtifactStatus(StrEnum):
    PARTIAL = "partial"
    COMPLETE = "complete"


def _document(value: Any) -> Mapping:
    data = value if isinstance(value, Mapping) else value.to_dict()
    require(isinstance(data, Mapping), "A pipeline artifact must be an object.")
    name(data.get("schema_version"), "Artifact schema")
    return freeze_json(data)


@dataclass(frozen=True)
class ScopedObligation:
    id: str
    scope: str
    evidence_kind: EvidenceKind
    description: str

    def __post_init__(self):
        for value, label in (
            (self.id, "Obligation"),
            (self.scope, "Scope"),
            (self.description, "Description"),
        ):
            name(value, label)
        require(isinstance(self.evidence_kind, EvidenceKind), "Invalid evidence kind.")

    def to_dict(self):
        return {
            "id": self.id,
            "scope": self.scope,
            "evidence_kind": self.evidence_kind.value,
            "description": self.description,
        }


@dataclass(frozen=True)
class CheckSpec:
    id: str
    evidence_kind: EvidenceKind
    discharges: tuple[str, ...] = ()

    def __post_init__(self):
        name(self.id, "Check id")
        require(isinstance(self.evidence_kind, EvidenceKind), "Invalid check kind.")
        require(
            self.evidence_kind is not EvidenceKind.UNRESOLVED,
            "An unresolved claim cannot discharge an obligation.",
        )
        object.__setattr__(self, "discharges", names(self.discharges, "Discharges"))

    def to_dict(self):
        return {
            "id": self.id,
            "evidence_kind": self.evidence_kind.value,
            "discharges": list(self.discharges),
        }


@dataclass(frozen=True)
class CheckDecision:
    outcome: CheckOutcome
    detail: str
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        require(isinstance(self.outcome, CheckOutcome), "Invalid check outcome.")
        name(self.detail, "Check detail")
        require(isinstance(self.evidence, Mapping), "Evidence must be an object.")
        object.__setattr__(self, "evidence", freeze_json(self.evidence))

    def to_dict(self):
        return {
            "outcome": self.outcome.value,
            "detail": self.detail,
            "evidence": thaw_json(self.evidence),
        }


@dataclass(frozen=True)
class PassContract:
    id: str
    version: str
    input_stage: Stage
    output_stage: Stage
    input_schema: str
    output_schema: str
    profile: str
    profile_version: str
    supported_operations: tuple[str, ...]
    checks: tuple[CheckSpec, ...]
    dependency_keys: tuple[str, ...] = ()
    targets: tuple[PayloadFormat, ...] = (PayloadFormat.DNA, PayloadFormat.RNA)
    required_capabilities: tuple[str, ...] = ()
    consumes_requirements: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    introduces: tuple[ScopedObligation, ...] = ()
    requires_source_map: bool = True
    requires_observation_map: bool = False
    changed_properties: tuple[str, ...] = ()
    invalidated_analyses: tuple[str, ...] = ()
    operation_path: tuple[str, ...] = ()

    def __post_init__(self):
        for key in (
            "id",
            "version",
            "input_schema",
            "output_schema",
            "profile",
            "profile_version",
        ):
            name(getattr(self, key), key)
        require(
            isinstance(self.input_stage, Stage)
            and isinstance(self.output_stage, Stage),
            "Invalid pass stages.",
        )
        require(
            STAGE_ORDER.index(self.output_stage)
            == STAGE_ORDER.index(self.input_stage) + 1,
            "A pass must advance exactly one declared compiler stage.",
        )
        for key in (
            "operation_path",
            "supported_operations",
            "dependency_keys",
            "required_capabilities",
            "consumes_requirements",
            "assumptions",
            "changed_properties",
            "invalidated_analyses",
        ):
            object.__setattr__(self, key, names(getattr(self, key), key))
        for key, cls in (("checks", CheckSpec), ("introduces", ScopedObligation)):
            items = getattr(self, key)
            require(
                isinstance(items, (list, tuple))
                and all(isinstance(x, cls) for x in items),
                f"Invalid {key}.",
            )
            require(len({x.id for x in items}) == len(items), f"Duplicate {key}.")
            object.__setattr__(self, key, tuple(items))
        require(bool(self.checks), "A pass requires at least one independent check.")
        require(
            isinstance(self.targets, (tuple, list))
            and bool(self.targets)
            and all(isinstance(x, PayloadFormat) for x in self.targets)
            and len(set(self.targets)) == len(self.targets),
            "Invalid target applicability.",
        )
        object.__setattr__(self, "targets", tuple(self.targets))
        require(
            type(self.requires_source_map) is bool
            and type(self.requires_observation_map) is bool,
            "Mapping requirements must be Boolean.",
        )

    def to_dict(self):
        return {
            "id": self.id,
            "version": self.version,
            "input_stage": self.input_stage.value,
            "output_stage": self.output_stage.value,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "profile": self.profile,
            "profile_version": self.profile_version,
            "operation_path": list(self.operation_path),
            "supported_operations": list(self.supported_operations),
            "checks": [x.to_dict() for x in self.checks],
            "dependency_keys": list(self.dependency_keys),
            "targets": [x.value for x in self.targets],
            "required_capabilities": list(self.required_capabilities),
            "consumes_requirements": list(self.consumes_requirements),
            "assumptions": list(self.assumptions),
            "introduces": [x.to_dict() for x in self.introduces],
            "requires_source_map": self.requires_source_map,
            "requires_observation_map": self.requires_observation_map,
            "changed_properties": list(self.changed_properties),
            "invalidated_analyses": list(self.invalidated_analyses),
        }

    @property
    def fingerprint(self):
        return fingerprint(self.to_dict())


@dataclass(frozen=True)
class PassContext:
    input: Mapping[str, Any]
    output: Mapping[str, Any] | None
    target: TargetContext
    configuration: Mapping[str, Any]
    dependencies: Mapping[str, str]
    requirements: tuple[str, ...]
    source_links: tuple[SourceLink, ...] = ()
    observation_map: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ComponentInputContract:
    """Trusted admission policy for an independently selected component root.

    This narrow entry point does not assert that a behavior or mechanism was
    realized. Validators must establish current structural input authority.
    """

    id: str
    version: str
    schema: str
    checks: tuple[CheckSpec, ...]
    requirements: tuple[str, ...]
    obligations: tuple[ScopedObligation, ...]
    dependency_keys: tuple[str, ...] = ()
    operation_path: tuple[str, ...] = ()

    def __post_init__(self):
        for key in ("id", "version", "schema"):
            name(getattr(self, key), key)
        for key in ("requirements", "dependency_keys", "operation_path"):
            object.__setattr__(self, key, names(getattr(self, key), key))
        for key, cls in (("checks", CheckSpec), ("obligations", ScopedObligation)):
            values = getattr(self, key)
            require(
                isinstance(values, (list, tuple))
                and all(isinstance(item, cls) for item in values)
                and len({item.id for item in values}) == len(values),
                f"Invalid component admission {key}.",
            )
            object.__setattr__(self, key, tuple(values))
        require(bool(self.checks), "Component admission needs independent checks.")
        obligations = {item.id: item for item in self.obligations}
        for check in self.checks:
            require(
                all(
                    key in obligations
                    and obligations[key].evidence_kind == check.evidence_kind
                    for key in check.discharges
                ),
                "Component admission check cannot discharge an unknown obligation or evidence kind.",
            )

    def to_dict(self):
        return {
            "id": self.id,
            "version": self.version,
            "schema": self.schema,
            "stage": Stage.COMPONENTS.value,
            "checks": [item.to_dict() for item in self.checks],
            "requirements": list(self.requirements),
            "obligations": [item.to_dict() for item in self.obligations],
            "dependency_keys": list(self.dependency_keys),
            "operation_path": list(self.operation_path),
        }

    @property
    def fingerprint(self):
        return fingerprint(self.to_dict())


@dataclass(frozen=True)
class CompletionProfile:
    scope: str
    stage: Stage
    schema: str
    obligations: tuple[str, ...]

    def __post_init__(self):
        name(self.scope, "Completion scope")
        name(self.schema, "Completion schema")
        require(isinstance(self.stage, Stage), "Invalid completion stage.")
        object.__setattr__(
            self, "obligations", names(self.obligations, "Completion obligations")
        )
        require(
            bool(self.obligations),
            "A completed profile must require explicit obligations.",
        )


@dataclass(frozen=True)
class StageRecord:
    id: str
    stage: Stage
    payload: Mapping[str, Any]
    requirements: tuple[str, ...]
    obligations: tuple[ScopedObligation, ...]
    discharged: tuple[str, ...]
    dependencies: Mapping[str, str]
    parent: str | None
    pass_id: str | None
    pass_identity: str | None
    checks: Mapping[str, Any]
    provenance: Mapping[str, Any]
    accepted: bool

    def to_dict(self):
        return {
            "schema_version": "biocompiler.stage_record.v0.1",
            "id": self.id,
            "stage": self.stage.value,
            "payload": thaw_json(self.payload),
            "requirements": list(self.requirements),
            "obligations": [x.to_dict() for x in self.obligations],
            "discharged": list(self.discharged),
            "dependencies": thaw_json(self.dependencies),
            "parent": self.parent,
            "pass_id": self.pass_id,
            "pass_identity": self.pass_identity,
            "checks": thaw_json(self.checks),
            "provenance": thaw_json(self.provenance),
            "accepted": self.accepted,
        }

    @property
    def fingerprint(self):
        return fingerprint(self.to_dict())


@dataclass(frozen=True)
class PipelineResult:
    status: ArtifactStatus
    artifact: StageRecord
    scope: str
    unresolved: tuple[ScopedObligation, ...]


class PassManager:
    """Acceptance is manager-owned; serialized records cannot grant it.

    Dependency values are canonical identities supplied by the caller. Update a
    root through set_dependency whenever its request, registry, model or tool
    changes. A subsequent get/run/complete recursively rejects stale descendants.
    No persistent cache or import-to-acceptance path exists in this profile.
    """

    def __init__(
        self,
        *,
        target: TargetContext,
        dependencies: Mapping[str, str],
        completion_profiles: tuple[CompletionProfile, ...] = (),
    ):
        require(isinstance(target, TargetContext), "A pipeline needs a target context.")
        require(isinstance(dependencies, Mapping), "Dependencies must be a mapping.")
        self._target = target
        self._dependencies = {}
        self._passes = {}
        self._component_inputs = {}
        self._provider_history = {}
        self._records = {}
        self._profiles = {}
        for profile in completion_profiles:
            self.register_completion_profile(profile)
        for key, value in dependencies.items():
            self.set_dependency(key, value)
        if "request" not in self._dependencies:
            raise PipelineError("Missing authoritative request dependency.")
        self.set_dependency("target", target.fingerprint)

    @property
    def target(self):
        return self._target

    def register_completion_profile(self, profile: CompletionProfile):
        """Register an additional scope without replacing an existing promise."""
        require(isinstance(profile, CompletionProfile), "Invalid completion profile.")
        if profile.scope in self._profiles:
            raise PipelineError(
                f"Completion profile {profile.scope!r} is already registered."
            )
        self._profiles[profile.scope] = profile

    def set_dependency(self, key: str, identity: str):
        name(key, "Dependency name")
        name(identity, "Dependency identity")
        require(
            len(identity) == 64 and all(c in "0123456789abcdef" for c in identity),
            "Dependencies require canonical SHA-256 identities.",
        )
        if key == "target" and identity != self.target.fingerprint:
            raise PipelineError(
                "Target dependency must match the pipeline context; create a new manager."
            )
        self._dependencies[key] = identity

    def register(
        self,
        contract: PassContract,
        producer: Callable,
        validators: Mapping[str, Callable],
    ):
        from sys import modules
        native_module = modules.get("biocompiler.core_pipeline_manager")
        native_type = vars(native_module).get("CorePassManager") if native_module is not None else None
        if isinstance(native_type, type) and issubclass(type(self), native_type):
            return native_type._native_register(self, contract, producer, validators)
        require(isinstance(contract, PassContract), "Invalid pass contract.")
        if contract.id in self._component_inputs:
            raise PipelineError("Pass ID collides with a component admission policy.")
        require(
            callable(producer)
            and isinstance(validators, Mapping)
            and all(callable(x) for x in validators.values()),
            "Invalid pass providers.",
        )
        if set(validators) != {check.id for check in contract.checks}:
            raise PipelineError(
                "Every contracted check needs exactly one independent provider."
            )
        if any(validator is producer for validator in validators.values()):
            raise PipelineError("Candidate generation cannot certify itself.")
        previous = self._provider_history.get(contract.fingerprint)
        if previous is not None and previous[0].fingerprint == contract.fingerprint:
            if previous[1] is not producer or dict(previous[2]) != dict(validators):
                raise PipelineError(
                    "Changed pass/check providers must increment the contract version."
                )
        registration = (contract, producer, dict(validators))
        self._passes[contract.id] = registration
        self._provider_history[contract.fingerprint] = registration

    def register_component_input(
        self, contract: ComponentInputContract, validators: Mapping[str, Callable]
    ):
        """Register trusted code that checks a Components-stage input from scratch."""
        require(
            isinstance(contract, ComponentInputContract),
            "Invalid component input contract.",
        )
        require(
            isinstance(validators, Mapping)
            and all(callable(value) for value in validators.values()),
            "Invalid component admission validators.",
        )
        if contract.id in self._passes:
            raise PipelineError("Component admission ID collides with a pass.")
        if set(validators) != {item.id for item in contract.checks}:
            raise PipelineError("Every admission check needs an independent provider.")
        key = ("component_input", contract.fingerprint)
        previous = self._provider_history.get(key)
        if previous is not None and previous[1] != dict(validators):
            raise PipelineError(
                "Changed admission providers must increment the contract version."
            )
        registration = (contract, dict(validators))
        self._component_inputs[contract.id] = registration
        self._provider_history[key] = registration

    def admit_component_input(self, contract_id: str, identity: str, payload: Any):
        """Admit one authoritative structural root, never a serialized receipt.

        The root must match the manager's frozen request identity and pass all
        freshly executed checks. Existing Intent-root pipelines cannot skip into
        Components through this entry point.
        """
        name(identity, "Input artifact id")
        if self._records:
            raise PipelineError(
                "Component admission requires a new pipeline with no existing records."
            )
        if contract_id not in self._component_inputs:
            raise PipelineError("Missing component admission policy.")
        contract, validators = self._component_inputs[contract_id]
        missing = set(contract.dependency_keys) - self._dependencies.keys()
        if missing:
            raise PipelineError(
                "Missing admission dependencies: " + ", ".join(sorted(missing))
            )
        document = _document(payload)
        if document["schema_version"] != contract.schema:
            raise PipelineError(
                "Component input schema does not match admission policy."
            )
        if fingerprint(document) != self._dependencies["request"]:
            raise PipelineError(
                "Component input does not match authoritative request identity."
            )
        if fingerprint(document.get("target")) != self.target.fingerprint:
            raise PipelineError(
                "Component input target differs from the pipeline target."
            )
        inventory = document
        for key in contract.operation_path:
            inventory = inventory.get(key) if isinstance(inventory, Mapping) else None
        nodes = inventory.get("nodes") if isinstance(inventory, Mapping) else None
        if (
            not isinstance(nodes, (tuple, list))
            or not nodes
            or any(
                not isinstance(item, Mapping)
                or item.get("kind") != "component_instance"
                or not isinstance(item.get("id"), str)
                or not item["id"].strip()
                for item in nodes
            )
            or len({item["id"] for item in nodes}) != len(nodes)
        ):
            raise PipelineError(
                "Component admission requires a unique component inventory."
            )
        dependencies = freeze_json(self._dependencies)
        context = PassContext(
            document,
            None,
            self.target,
            freeze_json({}),
            dependencies,
            contract.requirements,
        )
        checks, discharged = {}, set()
        for spec in contract.checks:
            decision = validators[spec.id](context)
            if not isinstance(decision, CheckDecision):
                raise PipelineError(
                    "Admission validator must return an explicit CheckDecision."
                )
            checks[spec.id] = {
                **spec.to_dict(),
                **decision.to_dict(),
                "subject": fingerprint(document),
                "dependencies": thaw_json(dependencies),
            }
            if decision.outcome is CheckOutcome.PASS:
                discharged.update(spec.discharges)
        accepted = all(
            item["outcome"] == CheckOutcome.PASS.value for item in checks.values()
        )
        record = StageRecord(
            identity,
            Stage.COMPONENTS,
            document,
            contract.requirements,
            contract.obligations,
            tuple(sorted(discharged)),
            dependencies,
            None,
            contract.id,
            contract.fingerprint,
            freeze_json(checks),
            freeze_json(
                {
                    "authority": "independently_checked_component_input",
                    "contract": contract.to_dict(),
                }
            ),
            accepted,
        )
        self._records[identity] = record
        if accepted:
            self.get(identity)
        return record

    def add_input(
        self,
        identity: str,
        payload: Any,
        *,
        stage: Stage = Stage.INTENT,
        requirements: tuple[str, ...] = (),
        obligations: tuple[ScopedObligation, ...] = (),
    ):
        name(identity, "Input artifact id")
        require(
            stage is Stage.INTENT,
            "Only authoritative intent inputs can enter a pipeline.",
        )
        if identity in self._records:
            raise PipelineError(f"Artifact {identity!r} already exists.")
        requirements = names(requirements, "Requirements")
        require(
            all(isinstance(x, ScopedObligation) for x in obligations)
            and len({x.id for x in obligations}) == len(obligations),
            "Invalid input obligations.",
        )
        document = _document(payload)
        if (
            getattr(payload, "fingerprint", fingerprint(document))
            != self._dependencies["request"]
        ):
            raise PipelineError(
                "Input artifact does not match the authoritative request identity."
            )
        if (
            document.get("target") is not None
            and fingerprint(document["target"]) != self.target.fingerprint
        ):
            raise PipelineError(
                "Input request target differs from the pipeline target."
            )
        record = StageRecord(
            identity,
            stage,
            document,
            requirements,
            tuple(obligations),
            (),
            freeze_json(self._dependencies),
            None,
            None,
            None,
            freeze_json({}),
            freeze_json({"authority": "frozen_input"}),
            True,
        )
        self._records[identity] = record
        return record

    def get(self, identity: str) -> StageRecord:
        if identity not in self._records:
            raise PipelineError(f"Missing artifact/provider: {identity!r}.")
        record = self._records[identity]
        if not record.accepted:
            raise PipelineError(
                f"Artifact {identity!r} has not passed its acceptance checks."
            )
        if self._dependencies["target"] != self.target.fingerprint:
            raise PipelineError("Target context changed after pipeline creation.")
        changes = [
            key
            for key, value in record.dependencies.items()
            if self._dependencies.get(key) != value
        ]
        if changes:
            raise PipelineError(
                f"Stale artifact {identity!r}; changed dependencies: {', '.join(changes)}."
            )
        if record.parent is not None:
            self.get(record.parent)
            registered = self._passes.get(record.pass_id)
            if registered is None or registered[0].fingerprint != record.pass_identity:
                raise PipelineError(
                    f"Stale artifact {identity!r}; pass contract/provider changed."
                )
        elif record.pass_id is not None:
            registered = self._component_inputs.get(record.pass_id)
            if registered is None or registered[0].fingerprint != record.pass_identity:
                raise PipelineError(
                    f"Stale artifact {identity!r}; component admission policy changed."
                )
        return record

    def run(
        self,
        pass_id: str,
        input_id: str,
        output_id: str,
        *,
        configuration: Mapping | None = None,
    ):
        source = self.get(input_id)
        name(output_id, "Output artifact id")
        if output_id in self._records:
            raise PipelineError(
                f"Artifact {output_id!r} already exists; use a new identity."
            )
        if pass_id not in self._passes:
            raise PipelineError(f"Missing pass provider: {pass_id!r}.")
        contract, producer, validators = self._passes[pass_id]
        if (
            source.stage is not contract.input_stage
            or source.payload["schema_version"] != contract.input_schema
        ):
            raise PipelineError(
                "Pass ordering or input schema does not match the accepted stage."
            )
        if self.target.payload_format not in contract.targets:
            raise PipelineError("Pass does not support the requested target.")
        if not set(contract.required_capabilities) <= set(self.target.capabilities):
            raise PipelineError("Target lacks required pass capabilities.")
        missing = set(contract.dependency_keys) - self._dependencies.keys()
        if missing:
            raise PipelineError(
                f"Unresolved dependency providers: {', '.join(sorted(missing))}."
            )
        if not set(contract.consumes_requirements) <= set(source.requirements):
            raise PipelineError(
                "Pass consumes requirements absent from its authoritative input."
            )
        configuration = freeze_json({} if configuration is None else configuration)
        require(
            isinstance(configuration, Mapping), "Pass configuration must be an object."
        )
        dependencies = freeze_json(self._dependencies)
        context = PassContext(
            source.payload,
            None,
            self.target,
            configuration,
            dependencies,
            source.requirements,
        )
        proposal = producer(context)
        if not isinstance(proposal, PassResult):
            raise PipelineError("Pass must return a candidate PassResult.")
        if proposal.search_status not in {"candidate", "no_candidate_found"}:
            raise PipelineError(
                "Unknown search outcome; no-candidate results cannot prove infeasibility."
            )
        if proposal.search_status == "no_candidate_found":
            if proposal.output is not None:
                raise PipelineError(
                    "A no-candidate search cannot contain candidate output."
                )
            raise NoCandidateFound(pass_id, configuration, dependencies)
        if proposal.output is None:
            raise PipelineError("A successful search must supply a candidate.")
        document = _document(proposal.output)
        if document["schema_version"] != contract.output_schema:
            raise PipelineError(
                "Candidate output schema does not match the destination profile."
            )
        inventory = document
        for key in contract.operation_path:
            inventory = inventory.get(key) if isinstance(inventory, Mapping) else None
        nodes = inventory.get("nodes") if isinstance(inventory, Mapping) else None
        if not isinstance(nodes, (tuple, list)) or any(
            not isinstance(n, Mapping) or "kind" not in n for n in nodes
        ):
            raise PipelineError(
                "This pipeline profile requires an explicit operation inventory in nodes."
            )
        unsupported = sorted(
            {n["kind"] for n in nodes} - set(contract.supported_operations)
        )
        if unsupported:
            raise PipelineError(
                f"Unsupported destination operations: {', '.join(unsupported)}."
            )
        links = tuple(proposal.source_links)
        if not all(
            isinstance(link, SourceLink) and link.pass_name == contract.id
            for link in links
        ):
            raise PipelineError("Invalid source correspondence or pass identity.")
        required = set(source.requirements)
        output_ids = {n.get("id") for n in nodes}
        # Accepted stage wrappers may store their operation inventory below
        # the root (for example SyntheticCandidate.mechanism). Read the same
        # trusted path used when that parent was accepted.
        input_inventory = source.payload
        if source.pass_id is not None:
            registrations = (
                self._passes if source.parent is not None else self._component_inputs
            )
            parent_contract = registrations[source.pass_id][0]
            for key in parent_contract.operation_path:
                input_inventory = input_inventory[key]
        elif "intent" in source.payload:
            input_inventory = source.payload["intent"]
        input_ids = {n.get("id") for n in input_inventory.get("nodes", ())}
        if any(
            link.requirement_id not in required
            or link.target_node_id not in output_ids
            or link.source_node_id not in input_ids
            for link in links
        ):
            raise PipelineError("Source map refers to an unknown requirement or node.")
        if (
            contract.requires_source_map
            and {link.requirement_id for link in links} != required
        ):
            raise PipelineError(
                "Candidate must retain source correspondence for every input requirement."
            )
        if not isinstance(proposal.observation_map, Mapping):
            raise PipelineError("Observation mapping must be an object.")
        observation_map = freeze_json(proposal.observation_map)
        if contract.requires_observation_map and not observation_map:
            raise PipelineError(
                "Candidate is missing its contracted observation mapping."
            )
        introduced = {x.id: x for x in contract.introduces}
        obligations = {x.id: x for x in source.obligations}
        if set(introduced) & set(obligations):
            raise PipelineError("Pass cannot redefine an upstream obligation.")
        obligations.update(introduced)
        # Producers may declare the contracted obligations but cannot substitute,
        # weaken, or add accepted claims through their PassResult.
        if any(
            x.requirement_id not in obligations
            or x.evidence_kind != obligations[x.requirement_id].evidence_kind
            or x.description != obligations[x.requirement_id].description
            or x.evidence_refs
            for x in proposal.obligations
        ):
            raise PipelineError(
                "Candidate changed an authoritative obligation or supplied self-certifying evidence."
            )
        context = PassContext(
            source.payload,
            document,
            self.target,
            configuration,
            dependencies,
            source.requirements,
            links,
            observation_map,
        )
        if not set(contract.invalidated_analyses) <= set(obligations):
            raise PipelineError("Invalidation names an unknown obligation.")
        checks, discharged = (
            {},
            set(source.discharged) - set(contract.invalidated_analyses),
        )
        for spec in contract.checks:
            for obligation_id in spec.discharges:
                if (
                    obligation_id not in obligations
                    or obligations[obligation_id].evidence_kind != spec.evidence_kind
                ):
                    raise PipelineError(
                        "Check scope or evidence kind cannot discharge the claimed obligation."
                    )
            decision = validators[spec.id](context)
            if not isinstance(decision, CheckDecision):
                raise PipelineError(
                    "Independent validator must return an explicit CheckDecision."
                )
            checks[spec.id] = {
                **spec.to_dict(),
                **decision.to_dict(),
                "subject": fingerprint(document),
                "dependencies": thaw_json(dependencies),
            }
            if decision.outcome is CheckOutcome.PASS:
                discharged.update(spec.discharges)
        accepted = all(x["outcome"] == CheckOutcome.PASS.value for x in checks.values())
        record = StageRecord(
            output_id,
            contract.output_stage,
            document,
            source.requirements,
            tuple(obligations.values()),
            tuple(sorted(discharged)),
            dependencies,
            input_id,
            contract.id,
            contract.fingerprint,
            freeze_json(checks),
            freeze_json(
                {
                    "contract": contract.to_dict(),
                    "configuration": thaw_json(configuration),
                    "source_links": [vars(x) for x in links],
                    "observation_map": thaw_json(observation_map),
                    "search": "deterministic; no inference of infeasibility",
                }
            ),
            accepted,
        )
        self._records[output_id] = record
        # A callback may have changed a root during execution; acceptance always
        # resolves against the current graph, not only the pre-run snapshot.
        if accepted:
            self.get(output_id)
        return record

    def result(self, identity: str, *, scope: str) -> PipelineResult:
        artifact = self.get(identity)
        if scope not in self._profiles:
            raise PipelineError(f"Unsupported completion profile: {scope!r}.")
        profile = self._profiles[scope]
        unresolved = tuple(
            x for x in artifact.obligations if x.id not in artifact.discharged
        )
        required = set(profile.obligations) | {
            x.id for x in artifact.obligations if x.scope == scope
        }
        complete = (
            artifact.stage is profile.stage
            and artifact.payload["schema_version"] == profile.schema
            and required <= set(artifact.discharged)
        )
        return PipelineResult(
            ArtifactStatus.COMPLETE if complete else ArtifactStatus.PARTIAL,
            artifact,
            scope,
            unresolved,
        )

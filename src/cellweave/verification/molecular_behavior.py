"""Independent admission of requested behavior-to-molecule correspondence.

This checker rechecks frozen Behavior authority and exact molecular acceptance.
It deliberately has no biological runner: sequence facts and cited evidence do
not discharge calibration, observation mapping or therapeutic obligations.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from cellweave.compiler.behavior import verify_lowering
from cellweave.compiler.request import RealizationRequest
from cellweave.ir.intent import freeze_json, thaw_json
from cellweave.ir.molecular import _Record, _array, _decode_array, _enum, _hash
from cellweave.ir.serialization import fields, fingerprint, name, names, require
from cellweave.semantics.molecular_behavior import (
    MOLECULAR_CONTRACT_PROFILE,
    MolecularImplementationContract,
    _utf8,
)
from cellweave.semantics.types import BOOLEAN, TypeSpec
from cellweave.verification.evidence import CheckOutcome, FreshnessReport
from cellweave.verification.molecular import check_molecular, molecular_dependencies
from cellweave.verification.realization import _runtime_observations

CHECKER_VERSION = "cellweave.molecular_correspondence_checker.v0.1"
CLAIM_SCOPE = (
    "Exact frozen-source, requested-observation and selected-CDS correspondence "
    "only. Molecular response, adapter applicability, calibrated parameters, "
    "experimental-material identity, uncertainty and therapeutic outcomes remain "
    "unestablished. This is not molecular behavior acceptance."
)
_DEPENDENCIES = {
    "contract",
    "realization_request",
    "realization_artifact",
    "build_request",
    "behavior",
    "target",
    "domain",
    "construct_request",
    "construct",
    "molecular",
    "registry",
    "references",
    "molecular_check_inputs",
    "checker",
}


def molecular_behavior_dependencies(
    contract,
    realization_request,
    construct_request,
    construct,
    molecular,
    registry,
    manifests,
):
    require(
        isinstance(contract, MolecularImplementationContract),
        "Expected molecular implementation contract.",
    )
    require(
        isinstance(realization_request, RealizationRequest),
        "Expected authoritative realization request.",
    )
    downstream = molecular_dependencies(
        construct_request, construct, molecular, registry, manifests
    )
    return {
        "contract": contract.fingerprint,
        "realization_request": realization_request.fingerprint,
        "realization_artifact": realization_request.artifact_fingerprint,
        "build_request": realization_request.build_request.fingerprint,
        "behavior": realization_request.behavior.fingerprint,
        "target": realization_request.target.fingerprint,
        "domain": realization_request.domain.fingerprint,
        "construct_request": construct_request.fingerprint,
        "construct": construct.fingerprint,
        "molecular": molecular.fingerprint,
        "registry": registry.fingerprint,
        "references": fingerprint(
            {key: value.fingerprint for key, value in sorted(manifests.items())}
        ),
        "molecular_check_inputs": fingerprint(downstream),
        "checker": CHECKER_VERSION,
    }


@dataclass(frozen=True)
class MolecularBehaviorDiagnostic(_Record):
    status: str
    scope: str
    code: str
    message: str
    requirement_id: str | None = None
    node_id: str | None = None
    schema_version: ClassVar[str] = "cellweave.molecular_behavior_diagnostic.v0.1"

    def __post_init__(self):
        _enum(self.status, {"fail", "unknown", "unsupported"}, "diagnostic status")
        _enum(self.scope, {"linkage", "behavior"}, "diagnostic scope")
        for key in ("code", "message"):
            name(getattr(self, key), key)
        for key in ("requirement_id", "node_id"):
            if getattr(self, key) is not None:
                name(getattr(self, key), key)
        _utf8(self)


def _linkage_outcome(diagnostics):
    statuses = {item.status for item in diagnostics if item.scope == "linkage"}
    for status in (CheckOutcome.FAIL, CheckOutcome.UNSUPPORTED, CheckOutcome.UNKNOWN):
        if status.value in statuses:
            return status
    return CheckOutcome.PASS


def _overall_outcome(diagnostics):
    if any(item.status == "fail" for item in diagnostics):
        return CheckOutcome.FAIL
    if any(item.status == "unsupported" for item in diagnostics):
        return CheckOutcome.UNSUPPORTED
    return CheckOutcome.UNKNOWN


@dataclass(frozen=True)
class MolecularBehaviorResult(_Record):
    outcome: CheckOutcome
    linkage_outcome: CheckOutcome
    dependencies: Mapping
    checked_requirement_ids: tuple[str, ...]
    diagnostics: tuple[MolecularBehaviorDiagnostic, ...]
    claim_scope: str = CLAIM_SCOPE
    schema_version: ClassVar[str] = "cellweave.molecular_behavior_result.v0.1"
    _decoders: ClassVar[dict] = {
        "outcome": CheckOutcome,
        "linkage_outcome": CheckOutcome,
        "diagnostics": lambda value: _decode_array(value, MolecularBehaviorDiagnostic),
    }

    def __post_init__(self):
        require(
            isinstance(self.outcome, CheckOutcome)
            and isinstance(self.linkage_outcome, CheckOutcome),
            "Expected typed outcomes.",
        )
        fields(self.dependencies, _DEPENDENCIES, "Molecular behavior dependencies")
        for key, value in self.dependencies.items():
            if key == "checker":
                require(
                    value == CHECKER_VERSION,
                    "Unsupported molecular correspondence checker.",
                )
            else:
                _hash(value, key)
        object.__setattr__(self, "dependencies", freeze_json(self.dependencies))
        object.__setattr__(
            self,
            "checked_requirement_ids",
            names(self.checked_requirement_ids, "Checked requirements"),
        )
        require(
            bool(self.checked_requirement_ids),
            "Molecular correspondence needs response requirements.",
        )
        object.__setattr__(
            self,
            "diagnostics",
            _array(self.diagnostics, MolecularBehaviorDiagnostic, "diagnostics"),
        )
        require(
            self.linkage_outcome is _linkage_outcome(self.diagnostics),
            "Linkage outcome disagrees with diagnostics.",
        )
        require(
            self.outcome is _overall_outcome(self.diagnostics),
            "Biological acceptance is unavailable in this profile.",
        )
        require(
            any(
                item.scope == "behavior" and item.code == "no_calibrated_adapter"
                for item in self.diagnostics
            ),
            "Missing explicit biological-evidence boundary.",
        )
        require(
            self.claim_scope == CLAIM_SCOPE, "Molecular claim scope cannot be upgraded."
        )
        _utf8(self)

    def to_dict(self):
        return super().to_dict() | {"dependencies": thaw_json(self.dependencies)}

    @property
    def passed(self):
        return False

    def freshness(
        self,
        contract,
        realization_request,
        construct_request,
        construct,
        molecular,
        registry,
        manifests,
    ):
        """Historical equality only; admission still requires the checker to rerun."""
        current = molecular_behavior_dependencies(
            contract,
            realization_request,
            construct_request,
            construct,
            molecular,
            registry,
            manifests,
        )
        return FreshnessReport(
            tuple(
                sorted(
                    key
                    for key in _DEPENDENCIES
                    if self.dependencies[key] != current[key]
                )
            )
        )


def check_molecular_implementation(
    contract,
    realization_request,
    construct_request,
    construct,
    molecular,
    registry,
    manifests,
):
    """Recompute linkage from independent current authority; never simulate a CAR."""
    dependencies = molecular_behavior_dependencies(
        contract,
        realization_request,
        construct_request,
        construct,
        molecular,
        registry,
        manifests,
    )
    diagnostics = []

    def diagnostic(status, scope, code, message, requirement_id=None, node_id=None):
        diagnostics.append(
            MolecularBehaviorDiagnostic(
                status, scope, code, message, requirement_id, node_id
            )
        )

    # Reconstruct source authority rather than accepting caller-provided PASS
    # labels or the candidate's source fingerprint as a lowering certificate.
    verify_lowering(realization_request.build_request, realization_request.behavior)
    exact = check_molecular(
        construct_request, construct, molecular, registry, manifests
    )
    if exact.outcome is not CheckOutcome.PASS:
        diagnostic(
            exact.outcome.value,
            "linkage",
            "molecular_acceptance",
            "Independent exact-CDS acceptance did not pass.",
        )
        for item in exact.diagnostics:
            diagnostic(item.status, "linkage", "molecular:" + item.code, item.message)
    for key, expected in (
        ("realization_request_fingerprint", realization_request.fingerprint),
        ("construct_request_fingerprint", construct_request.fingerprint),
        ("molecular_fingerprint", molecular.fingerprint),
        ("target_fingerprint", realization_request.target.fingerprint),
        ("domain_fingerprint", realization_request.domain.fingerprint),
    ):
        if getattr(contract, key) != expected:
            diagnostic(
                "fail",
                "linkage",
                key,
                "The contract differs from current independent authority.",
            )
    if realization_request.target != construct_request.target:
        diagnostic(
            "fail",
            "linkage",
            "target_context",
            "Behavior and selected molecular inputs have different target contexts.",
        )
    expected_components = construct_request.composition.registry_lock.components
    if sorted(contract.selected_components, key=lambda item: item.node_id) != sorted(
        expected_components, key=lambda item: item.node_id
    ):
        diagnostic(
            "fail",
            "linkage",
            "selected_components",
            "Selected components differ from the independent construct request.",
        )
    # Reference linking resolves content pins. Classification prevents a digital
    # operator from becoming a biological implementation through correspondence.
    try:
        resolved = registry.resolve(construct_request.composition.registry_lock)
    except (ValueError, KeyError) as error:
        diagnostic("fail", "linkage", "component_resolution", str(error))
        resolved = {}
    if any(item.classification == "synthetic_model" for item in resolved.values()):
        diagnostic(
            "unsupported",
            "behavior",
            "synthetic_analogy",
            "Synthetic fixture models are not calibrated molecular adapters.",
        )
    instances = {item.node_id for item in expected_components}
    requirements = {item.id: item for item in realization_request.contract.requirements}
    domain_inputs = {
        (item.signal_id, item.field): item for item in realization_request.domain.inputs
    }
    input_bindings = {
        (item.signal_id, item.field): item for item in contract.input_bindings
    }
    responses = {item.requirement_id: item for item in contract.response_bindings}
    nodes = {item.id: item for item in realization_request.behavior.nodes}
    role = realization_request.domain.role
    if set(domain_inputs) != _runtime_observations(realization_request.behavior, role):
        diagnostic(
            "fail",
            "linkage",
            "domain_coverage",
            "Operating domain must cover all live runtime observations exactly.",
        )
    if set(input_bindings) != set(domain_inputs):
        diagnostic(
            "fail",
            "linkage",
            "input_coverage",
            "Requested input mappings must cover each domain input exactly.",
        )
    if set(responses) != set(requirements):
        diagnostic(
            "fail",
            "linkage",
            "response_coverage",
            "Requested response mappings must cover each contracted requirement exactly.",
        )
    for key, item in input_bindings.items():
        expected = domain_inputs.get(key)
        node = nodes.get(item.signal_id)
        if expected is None:
            continue
        dtype = (
            TypeSpec.from_dict(node.data_type)
            if node is not None and node.kind == "signal" and item.field == "value"
            else BOOLEAN
        )
        if (
            node is None
            or node.kind != "signal"
            or node.role != role
            or item.observable != expected.observable
            or item.observable.role != role
            or item.observable.scope != ("contact" if node.contact_bound else "cell")
            or not item.observable.dtype.compatible(dtype)
        ):
            diagnostic(
                "fail",
                "linkage",
                "input_correspondence",
                "Input identity, type, scope or endpoint differs from the authoritative source/domain.",
                node_id=item.signal_id,
            )
        if item.instance_id not in instances:
            diagnostic(
                "fail",
                "linkage",
                "input_instance",
                "Requested input refers to an unselected component.",
                node_id=item.signal_id,
            )
    for key, item in responses.items():
        expected = requirements.get(key)
        if expected is None:
            continue
        rule = nodes.get(expected.rule_id)
        specification = nodes.get(expected.specification_id)
        if (
            rule is None
            or rule.kind != "rule"
            or rule.role != role
            or specification is None
            or specification.id not in rule.inputs[2:]
        ):
            diagnostic(
                "fail",
                "linkage",
                "requirement_source",
                "Response contract must refer to an installed rule and action specification.",
                key,
                expected.rule_id,
            )
        elif expected.observable.role != role or expected.observable.scope != (
            "contact" if specification.contact_bound else "cell"
        ):
            diagnostic(
                "fail",
                "linkage",
                "response_scope",
                "Response endpoint role/scope differs from the authored action.",
                key,
                specification.id,
            )
        if (item.rule_id, item.specification_id, item.observable) != (
            expected.rule_id,
            expected.specification_id,
            expected.observable,
        ):
            diagnostic(
                "fail",
                "linkage",
                "response_correspondence",
                "Requested response differs from its authoritative requirement and source IDs.",
                key,
                item.specification_id,
            )
        if item.instance_id not in instances:
            diagnostic(
                "fail",
                "linkage",
                "response_instance",
                "Requested response refers to an unselected component.",
                key,
                item.specification_id,
            )
    pairs = {(item.rule_id, item.specification_id) for item in requirements.values()}
    installed = set()
    for rule in realization_request.behavior.find(kind="rule", role=role):
        for ref in rule.inputs[2:]:
            action = nodes[ref]
            if action.attributes.get("ongoing"):
                installed.add((rule.id, ref))
                primitive = (
                    nodes[action.inputs[0]] if action.kind == "action.pulse" else action
                )
                if (
                    primitive.kind == "action.secrete"
                    and primitive.attributes.get("rate") == "expression"
                ):
                    diagnostic(
                        "unsupported",
                        "linkage",
                        "quantitative_action_law",
                        "Activation-band correspondence does not specify quantitative tracking semantics.",
                        node_id=action.id,
                    )
            elif action.kind != "action.state_set":
                diagnostic(
                    "unsupported",
                    "linkage",
                    "instantaneous_output",
                    "Instantaneous outputs require separately specified response semantics.",
                    node_id=action.id,
                )
    if pairs != installed:
        diagnostic(
            "unsupported",
            "linkage",
            "uncontracted_outputs",
            "The contract must cover every installed ongoing output of the selected role exactly.",
        )
    if set(realization_request.domain.required_capabilities) - set(
        realization_request.target.capabilities
    ):
        diagnostic(
            "fail",
            "linkage",
            "missing_capabilities",
            "The target does not declare all domain-required capabilities.",
        )
    requested_compartments = {
        item.observable.compartment for item in domain_inputs.values()
    } | {item.observable.compartment for item in requirements.values()}
    if requested_compartments - set(realization_request.target.compartments):
        diagnostic(
            "fail",
            "linkage",
            "missing_compartments",
            "Requested measurements refer to undeclared target compartments.",
        )
    for item in contract.evidence:
        if item.context_fingerprint != realization_request.target.fingerprint:
            diagnostic(
                "fail",
                "linkage",
                "evidence_context",
                "Cited evidence is attributed to a different target context.",
            )
        diagnostic(
            "unknown",
            "behavior",
            "unvalidated_evidence:" + item.id,
            "A pinned citation records a claim; no loaded validator establishes its material relationship, calibration or therapeutic scope.",
        )
    if contract.model_profile != MOLECULAR_CONTRACT_PROFILE:
        diagnostic(
            "unsupported",
            "behavior",
            "model_profile",
            "This semantic/model profile has no implemented molecular acceptance provider.",
        )
    if contract.adapter is not None:
        diagnostic(
            "unsupported",
            "behavior",
            "adapter_provider",
            "The proposed adapter identity has no implemented calibrated provider.",
        )
    diagnostic(
        "unknown",
        "behavior",
        "no_calibrated_adapter",
        "No context-validated molecular adapter or established observation mapping is available.",
    )
    for claim in contract.unestablished_claims:
        diagnostic(
            "unknown",
            "behavior",
            "unestablished:" + claim,
            "This biological or material claim remains explicitly unestablished.",
        )
    return MolecularBehaviorResult(
        _overall_outcome(diagnostics),
        _linkage_outcome(diagnostics),
        dependencies,
        tuple(sorted(requirements)),
        tuple(diagnostics),
    )

"""Retain therapeutic source authority while requesting one coding cassette.

This pass extracts an explicitly installed product action. It does not equate
coding with secretion, execute a guard, or turn a declaration into expression.
Every remaining source operation and wrapped contract stays unresolved.
"""

from biocompiler.compiler.acceptance import HumanAcceptanceRequest
from biocompiler.compiler.deployment import HumanDeploymentRequest
from biocompiler.compiler.human_behavior import HumanBehaviorRequest
from biocompiler.errors import UnsupportedBehaviorError
from biocompiler.ir.candidate import (
    OBLIGATION_SPECS,
    CandidateObligation,
    CandidateRequest,
    CandidateRequirements,
)
from biocompiler.ir.intent import freeze_json
from biocompiler.ir.serialization import require
from biocompiler.semantics.context import HumanTargetContext
from biocompiler.semantics.types import BOOLEAN, PRODUCTION_RATE, TypeSpec

LOWERER_VERSION = "biocompiler.candidate_requirements_lowerer.v0.1"


class CandidateRequirementsError(UnsupportedBehaviorError):
    """A source shape cannot supply an unambiguous partial coding candidate."""

    def __init__(self, code, message, node=None):
        self.code = code
        super().__init__(
            message,
            node_id=node.id if node is not None else None,
            source=node.source if node is not None else None,
        )
        self.diagnostics = (
            freeze_json({"code": code, "message": message, "node_id": self.node_id}),
        )


def lower_candidate_requirements(request: CandidateRequest) -> CandidateRequirements:
    """Select the sole source product and retain all unimplemented requirements."""
    require(isinstance(request, CandidateRequest), "Expected frozen CandidateRequest.")
    request = CandidateRequest.from_dict(request.to_dict())
    program = request.build_request.intent
    nodes = {node.id: node for node in program.nodes}

    def reject(code, message, node=None):
        raise CandidateRequirementsError(code, message, node)

    def one(kind):
        values = program.find(kind=kind)
        if len(values) != 1:
            reject(
                "source_shape",
                f"Candidate extraction requires exactly one {kind} source node.",
            )
        return values[0]

    if request.target is None:
        reject(
            "target_required",
            "A candidate request must retain an explicit original target context.",
        )
    role, secretion, action, rule = (
        one(kind) for kind in ("role", "secretion", "action.secrete", "rule")
    )
    actions = tuple(node for node in program.nodes if node.kind.startswith("action."))
    if len(actions) != 1:
        reject(
            "multiple_actions",
            "The candidate profile supports one ongoing secretion action; other actions require another profile.",
        )
    if (
        secretion.inputs != (role.id,)
        or secretion.role != role.id
        or secretion.data_type is not None
        or set(secretion.attributes) != {"name", "product", "default", "activity"}
        or not isinstance(secretion.attributes.get("product"), str)
        or not secretion.attributes["product"].strip()
        or type(secretion.attributes.get("default")) is not bool
        or secretion.attributes.get("activity") != "requires_rule_or_controller"
    ):
        reject(
            "secretion_declaration",
            "The selected secretion must declare its exact product and owner, with activity requiring an installed rule.",
            secretion,
        )
    if (
        action.role != role.id
        or action.data_type is not None
        or set(action.attributes) != {"ongoing", "rate"}
        or action.attributes.get("ongoing") is not True
        or action.attributes.get("rate") not in ("unspecified", "expression")
        or len(action.inputs)
        != (1 if action.attributes.get("rate") == "unspecified" else 2)
        or action.inputs[0] != secretion.id
    ):
        reject(
            "secretion_action",
            "Candidate extraction requires one ongoing source secretion action with its exact declaration and rate expression.",
            action,
        )
    if len(action.inputs) == 2:
        rate = nodes[action.inputs[1]]
        if (
            rate.data_type is None
            or TypeSpec.from_dict(rate.data_type) != PRODUCTION_RATE
        ):
            reject(
                "secretion_rate_type",
                "An explicit secretion rate must preserve ProductionRate units; it remains unimplemented.",
                rate,
            )
    if (
        rule.role != role.id
        or rule.data_type is not None
        or not {"trigger", "execution", "priority"} <= set(rule.attributes)
        or set(rule.attributes) - {"trigger", "execution", "priority", "name"}
        or rule.attributes.get("trigger") != "condition"
        or rule.attributes.get("execution") != "concurrent"
        or rule.attributes.get("priority") != "unspecified"
        or len(rule.inputs) != 3
        or rule.inputs[0] != role.id
        or rule.inputs[2] != action.id
    ):
        reject(
            "installed_condition_rule",
            "A secretion declaration alone is insufficient: install the one action in a condition-triggered source rule without invented priority.",
            rule,
        )
    guard = nodes[rule.inputs[1]]
    if guard.data_type is None or TypeSpec.from_dict(guard.data_type) != BOOLEAN:
        reject(
            "condition_type",
            "The installed source guard must retain its Condition type.",
            guard,
        )
    if not {role.id, secretion.id, rule.id} <= set(program.roots):
        reject(
            "source_roots",
            "The original role, secretion declaration and installed rule must remain source roots.",
        )
    source_ids = tuple(node.id for node in program.nodes)
    obligations = []

    def obligation(identity, identities):
        category, description = OBLIGATION_SPECS[identity]
        obligations.append(
            CandidateObligation(
                identity, tuple(dict.fromkeys(identities)), category, description
            )
        )

    obligation("secretion_mechanism", (secretion.id, action.id))
    obligation("conditional_control", (rule.id, guard.id, action.id))
    obligation("quantitative_response", (action.id,))
    obligation("biological_function", (secretion.id, action.id))
    obligation("target_applicability", (role.id,))
    for node in program.nodes:
        if node.id in {role.id, secretion.id, action.id}:
            continue
        goal = node.kind == "goal"
        obligations.append(
            CandidateObligation(
                "source:" + node.id,
                (node.id,),
                "evidence" if goal else "implementation",
                "This source goal remains unestablished by coding candidate selection."
                if goal
                else f"Source operation {node.kind!r} remains unimplemented by coding-only candidate selection.",
            )
        )
    if isinstance(request.target, HumanTargetContext):
        obligation("human_therapeutic_admission", (role.id,))
    source = request.source
    behavior = (
        source.behavior_request
        if isinstance(source, (HumanDeploymentRequest, HumanAcceptanceRequest))
        else source
        if isinstance(source, HumanBehaviorRequest)
        else None
    )
    if behavior is not None:
        contract = behavior.contract
        obligation("human_input_observation", (contract.input_signal_id,))
        obligation("human_predicate_refinement", (contract.predicate.predicate_id,))
        obligation(
            "human_response_contract",
            (contract.response.rule_id, contract.response.specification_id),
        )
        obligation("human_goal_refinement", (contract.goal_id,))
        obligation("human_behavior_evidence", source_ids)
    if isinstance(source, (HumanDeploymentRequest, HumanAcceptanceRequest)):
        obligation("human_deployment_contract", (role.id,))
        obligation("human_deployment_evidence", (role.id,))
    if isinstance(source, HumanAcceptanceRequest):
        obligation("human_prohibited_behavior", (rule.id, action.id))
        obligation("human_input_loss_response", (rule.id, action.id))
        obligation("human_external_shutdown", (rule.id, action.id))
        obligation("human_acceptance_evidence", (role.id, rule.id, action.id))
    return CandidateRequirements(
        request.fingerprint,
        role.id,
        secretion.id,
        action.id,
        secretion.attributes["product"],
        source_ids,
        tuple(obligations),
    )

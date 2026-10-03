"""Analyze retained therapeutic source into explicit unresolved functions.

Analysis is useful outside the first implementation family: unsupported nodes,
contracts and unresolved requirements remain visible rather than being dropped.
"""

from biocompiler.compiler.acceptance import HumanAcceptanceRequest
from biocompiler.compiler.deployment import HumanDeploymentRequest
from biocompiler.compiler.human_behavior import HumanBehaviorRequest
from biocompiler.compiler.request import BuildRequest
from biocompiler.ir.implementation_requirements import (
    DIAGNOSTIC_MESSAGES,
    MAX_SOURCE_NODES,
    OPERATION_KINDS,
    SOURCE_TYPES,
    ImplementationDiagnostic,
    ImplementationObligation,
    ImplementationRequirements,
    ProductRequirement,
    source_request_from_dict,
)
from biocompiler.ir.intent import thaw_json
from biocompiler.ir.serialization import require
from biocompiler.semantics.context import HumanTargetContext
from biocompiler.semantics.types import PRODUCTION_RATE, TypeSpec, decode_binding
from biocompiler.verification.deployment import check_deployment

ANALYZER_VERSION = "biocompiler.implementation_requirements_analyzer.v0.1"


def analyze_implementation_requirements(source):
    """Return a source-authoritative analysis; no mechanism or evidence is inferred."""
    require(
        isinstance(source, SOURCE_TYPES),
        "Expected a frozen source request for requirement analysis.",
    )
    source = source_request_from_dict(source.to_dict())
    build = source if isinstance(source, BuildRequest) else source.build_request
    program, target = build.intent, build.target
    require(
        len(program.nodes) <= MAX_SOURCE_NODES,
        "Implementation analysis exceeds its source-node limit.",
    )
    nodes = {node.id: node for node in program.nodes}
    ids = tuple(nodes)
    roles = program.find(kind="role")
    role_id = roles[0].id if len(roles) == 1 else None
    obligations, diagnostics, products = [], [], []
    behavior = (
        source.behavior_request
        if isinstance(source, (HumanDeploymentRequest, HumanAcceptanceRequest))
        else source
        if isinstance(source, HumanBehaviorRequest)
        else None
    )
    deployment = (
        source.deployment_request
        if isinstance(source, HumanAcceptanceRequest)
        else source
        if isinstance(source, HumanDeploymentRequest)
        else None
    )

    def add(identity, kind, references, operation, arguments, *, role=None, path=None):
        if not references:
            return
        obligations.append(
            ImplementationObligation(
                identity,
                kind,
                tuple(dict.fromkeys(references)),
                {"operation": operation, "arguments": arguments},
                {
                    "role_id": role,
                    "target_fingerprint": target.fingerprint if target else None,
                    "contract_path": path,
                },
            )
        )

    def diagnostic(code, category, references, details):
        diagnostics.append(
            ImplementationDiagnostic(
                code,
                category,
                tuple(dict.fromkeys(references)),
                DIAGNOSTIC_MESSAGES[code],
                details,
            )
        )

    unsupported_operations = {
        "controller",
        "integrated",
        "curve",
        "curve_apply",
        "control_port",
        "channel",
        "channel_observation",
        "gradient",
        "action.migrate_toward",
        "action.emit",
    }
    for node in program.nodes:
        add(
            "source:" + node.id,
            OPERATION_KINDS.get(node.kind, "source_semantics"),
            (node.id,),
            node.kind,
            node.to_dict(include_source=False),
            role=node.role,
        )
        if node.kind not in OPERATION_KINDS:
            diagnostic(
                "unknown_source_operation",
                "unsupported_semantics",
                (node.id,),
                {"operation": node.kind},
            )
        elif (
            node.kind in unsupported_operations
            or node.kind.startswith("action.")
            and node.kind != "action.secrete"
        ):
            diagnostic(
                "operation_profile_unsupported",
                "unsupported_semantics",
                (node.id,),
                {"operation": node.kind},
            )
        if node.kind in {"signal", "channel_observation", "gradient"}:
            diagnostic(
                "sensing_binding_missing",
                "missing_refinement",
                (node.id,),
                {"operation": node.kind, "accessibility": "requires_physical_binding"},
            )
        if node.kind == "qualitative" and (
            behavior is None or behavior.contract.predicate.predicate_id != node.id
        ):
            diagnostic(
                "predicate_refinement_missing",
                "missing_refinement",
                (node.id,),
                {
                    "band": thaw_json(node.attributes.get("band")),
                    "requires": "typed_threshold_and_observation",
                },
            )
        if node.kind == "goal" and (
            behavior is None or behavior.contract.goal_id != node.id
        ):
            diagnostic(
                "goal_refinement_missing",
                "missing_refinement",
                (node.id,),
                {"requires": "measurable_goal_refinement"},
            )
        if OPERATION_KINDS.get(node.kind) == "temporal_state":
            diagnostic(
                "temporal_implementation_missing",
                "missing_refinement",
                (node.id,),
                {"operation": node.kind},
            )

    for action in program.find(kind="action.secrete"):
        declaration = nodes.get(action.inputs[0]) if action.inputs else None
        mode = action.attributes.get("rate")
        valid = (
            declaration is not None
            and declaration.kind == "secretion"
            and isinstance(declaration.attributes.get("product"), str)
            and bool(declaration.attributes["product"].strip())
            and declaration.role is not None
            and action.role == declaration.role
            and declaration.inputs == (declaration.role,)
            and declaration.attributes.get("activity") == "requires_rule_or_controller"
            and action.attributes.get("ongoing") is True
            and isinstance(mode, str)
            and mode in {"unspecified", "expression"}
            and len(action.inputs) == (2 if mode == "expression" else 1)
        )
        rate_id = action.inputs[1] if valid and mode == "expression" else None
        if rate_id is not None:
            dtype = nodes[rate_id].data_type
            valid = dtype is not None and TypeSpec.from_dict(dtype) == PRODUCTION_RATE
        if not valid:
            diagnostic(
                "secretion_action_unresolved",
                "unsupported_semantics",
                (action.id,),
                {"operation": action.kind},
            )
            continue
        installed = tuple(
            rule
            for rule in program.find(kind="rule")
            if len(rule.inputs) >= 3
            and rule.inputs[0] == action.role
            and rule.role == action.role
            and action.id in rule.inputs[2:]
        )
        if not installed:
            diagnostic(
                "secretion_rule_missing",
                "missing_refinement",
                (action.id, declaration.id),
                {"action_id": action.id, "secretion_id": declaration.id},
            )
            continue
        rule_ids = tuple(rule.id for rule in installed)
        guard_ids = tuple(dict.fromkeys(rule.inputs[1] for rule in installed))
        source_ids = tuple(
            dict.fromkeys(
                (
                    action.role,
                    declaration.id,
                    action.id,
                    *rule_ids,
                    *guard_ids,
                    *((rate_id,) if rate_id else ()),
                )
            )
        )
        product = ProductRequirement(
            "product:" + action.id,
            action.role,
            declaration.attributes["product"],
            declaration.id,
            action.id,
            rule_ids,
            guard_ids,
            rate_id,
            source_ids,
        )
        products.append(product)
        add(
            "encoding:" + action.id,
            "encoding",
            source_ids,
            "encode_requested_product",
            {"product_requirement": product.to_dict()},
            role=action.role,
        )
        add(
            "localization:" + action.id,
            "localization_processing",
            source_ids,
            "export_requested_product",
            {
                "product": product.product,
                "localization": "extracellular",
                "processing": "unspecified",
            },
            role=action.role,
        )
        add(
            "response:" + action.id,
            "quantitative",
            source_ids,
            "requested_secretion_response",
            {
                "rate_id": rate_id,
                "rate_expression": nodes[rate_id].to_dict(include_source=False)
                if rate_id
                else None,
                "implementation": "unresolved",
            },
            role=action.role,
        )
        if rate_id is not None:
            rate = nodes[rate_id]
            value = (
                rate.attributes.get("value")
                if rate.kind == "literal"
                else build.resolved_bindings.get(rate.attributes.get("name"))
                if rate.kind == "parameter"
                else None
            )
            if (
                value is not None
                and decode_binding(value, PRODUCTION_RATE).canonical_value < 0
            ):
                diagnostic(
                    "negative_secretion_rate",
                    "contradiction",
                    (action.id, rate_id),
                    {"rate_id": rate_id, "value": thaw_json(value)},
                )

    installed_declarations = {item.secretion_id for item in products}
    for declaration in program.find(kind="secretion"):
        if declaration.id not in installed_declarations and not any(
            node.kind == "action.secrete"
            and node.inputs
            and node.inputs[0] == declaration.id
            for node in program.nodes
        ):
            diagnostic(
                "secretion_rule_missing",
                "missing_refinement",
                (declaration.id,),
                {"action_id": None, "secretion_id": declaration.id},
            )

    add(
        "build:context",
        "source_semantics",
        ids,
        "frozen_build_context",
        {
            "artifact_scope": build.artifact_scope,
            "behavior_profile": build.behavior_profile,
            "resolved_bindings": thaw_json(build.resolved_bindings),
            "parameter_metadata": {
                key: item.to_dict() for key, item in build.parameter_metadata.items()
            },
            "implementation_constraints": thaw_json(build.implementation_constraints),
            "preferences": thaw_json(build.preferences),
        },
        role=role_id,
        path="build_request",
    )
    add(
        "target:context",
        "host_deployment",
        ids,
        "target_context",
        {"target": target.to_dict() if target else None},
        role=role_id,
        path="build_request.target",
    )
    add(
        "evidence:physical_function",
        "evidence_admission",
        ids,
        "physical_function",
        {"support": "unestablished"},
        role=role_id,
    )
    if target is None:
        diagnostic(
            "target_context_missing", "missing_refinement", ids, {"target": None}
        )
    if build.implementation_constraints or build.preferences:
        diagnostic(
            "source_constraints_unsupported",
            "unsupported_semantics",
            ids,
            {
                "implementation_constraints": thaw_json(
                    build.implementation_constraints
                ),
                "preferences": thaw_json(build.preferences),
            },
        )
    if isinstance(target, HumanTargetContext):
        add(
            "evidence:human_admission",
            "evidence_admission",
            ids,
            "human_therapeutic_admission",
            {"admission": "not_admitted"},
            role=role_id,
            path="build_request.target.human_target",
        )
    if behavior is not None:
        add(
            "contract:behavior",
            "quantitative",
            ids,
            "human_behavior",
            behavior.contract.to_dict(),
            role=role_id,
            path="behavior.contract",
        )
    if deployment is not None:
        add(
            "contract:deployment",
            "host_deployment",
            ids,
            "human_deployment",
            deployment.deployment.to_dict(),
            role=role_id,
            path="deployment",
        )
        assessment = check_deployment(deployment)
        for code in assessment.diagnostics:
            if code in {
                "expression_onset_after_behavior_start",
                "expression_duration_does_not_cover_behavior",
            }:
                category, identity = "contradiction", "deployment_contradiction"
            elif code in {
                "deployment_destination_profile_unsupported",
                "same_cell_co_payload_delivery_unsupported",
            }:
                category, identity = "unsupported_semantics", "deployment_unsupported"
            else:
                category, identity = (
                    "missing_refinement",
                    "deployment_missing_refinement",
                )
            diagnostic(
                identity,
                category,
                ids,
                {"deployment_diagnostic": code, "contract_path": "deployment"},
            )
    if isinstance(source, HumanAcceptanceRequest):
        add(
            "contract:acceptance",
            "control",
            ids,
            "human_acceptance",
            source.acceptance.to_dict(),
            role=role_id,
            path="acceptance",
        )
        for code, field in (
            ("healthy_context_control_missing", "healthy_measurement"),
            ("shutdown_control_missing", "shutdown"),
            ("input_loss_control_missing", "input_availability"),
        ):
            diagnostic(
                code,
                "missing_refinement",
                ids,
                {
                    "contract_path": "acceptance." + field,
                    "source_guard_policy": "unchanged_no_implicit_override",
                },
            )

    report = ImplementationRequirements(
        source,
        source.fingerprint,
        ids,
        tuple(products),
        tuple(obligations),
        tuple(diagnostics),
    )
    if report.supported_profile is None:
        diagnostic(
            "source_profile_unsupported",
            "unsupported_semantics",
            ids,
            {"requested_profile": "single_role_conditional_secretion.v0.1"},
        )
        report = ImplementationRequirements(
            source,
            source.fingerprint,
            ids,
            tuple(products),
            tuple(obligations),
            tuple(diagnostics),
        )
    return report

"""Independent replay of source-to-composite-RNA implementation proposals.

This checker imports no requirements analyzer, mechanism selector, constructor,
or emitter. Agreement is exact source/recipe correspondence, never evidence of
physical processing, secretion, therapeutic function, or human-use admission.
"""

from collections.abc import Mapping
from dataclasses import dataclass, fields as dataclass_fields
import hashlib
from types import SimpleNamespace
from typing import ClassVar

from biocompiler.errors import SerializationError
from biocompiler.ir.intent import freeze_json, thaw_json
from biocompiler.ir.implementation_requirements import (
    ImplementationObligation,
    ImplementationRequirements,
    SOURCE_TYPES,
)
from biocompiler.ir.payload import PayloadMolecule, PayloadRegion, hash_value
from biocompiler.ir.serialization import JsonArtifact, fields, fingerprint, require
from biocompiler.verification.evidence import CheckOutcome, FreshnessReport
from biocompiler.verification.molecular_design import (
    CHECKER_VERSION as STRUCTURAL_CHECKER_VERSION,
    structural_rna_diagnostics,
)
from biocompiler.verification.payload import PayloadDiagnostic

CHECKER_VERSION = "biocompiler.implementation_checker.v0.1"
CLAIM_SCOPE = (
    "Exact retained-source analysis, bounded supplied-recipe selection, declared "
    "mechanism correspondence, and composite RNA structure only. Physical "
    "processing, secretion, sensing, regulation, quantitative behavior, human "
    "applicability, and therapeutic function remain unestablished."
)
_STAGES = ("requirements", "selection", "plan", "construct", "molecule")
_CHECKS = (
    "original_source_authority",
    "complete_source_requirements",
    "bounded_alternative_selection",
    "mechanism_plan_correspondence",
    "composite_construct_correspondence",
    "emitted_molecule_correspondence",
)


def _sha(sequence):
    return hashlib.sha256(sequence.encode("ascii")).hexdigest()


def _outcome(diagnostics):
    statuses = {item.status for item in diagnostics}
    return next(
        (
            item
            for item in (
                CheckOutcome.FAIL,
                CheckOutcome.UNSUPPORTED,
                CheckOutcome.UNKNOWN,
            )
            if item.value in statuses
        ),
        CheckOutcome.PASS,
    )


def _checks(stage):
    return _CHECKS[: 2 + _STAGES.index(stage)]


def _schemas():
    from biocompiler.ir.implementation import (
        ImplementationRequest,
        ImplementationLibrary,
        ImplementationSelection,
        ImplementationPlan,
        ImplementationConstruct,
    )

    return {
        "sources": tuple(item.schema_version for item in SOURCE_TYPES),
        "request": ImplementationRequest.schema_version,
        "library": ImplementationLibrary.schema_version,
        "requirements": ImplementationRequirements.schema_version,
        "selection": ImplementationSelection.schema_version,
        "plan": ImplementationPlan.schema_version,
        "construct": ImplementationConstruct.schema_version,
        "molecule": PayloadMolecule.schema_version,
    }


def _profiles():
    from biocompiler.ir.implementation import PROFILE_VERSION
    from biocompiler.ir.implementation_requirements import (
        PROFILE_VERSION as REQUIREMENTS_PROFILE,
    )
    from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION
    from biocompiler.verification.deployment import (
        CHECKER_VERSION as DEPLOYMENT_CHECKER,
    )

    return {
        "requirements": REQUIREMENTS_PROFILE,
        "implementation": PROFILE_VERSION,
        "admission": ADMISSION_POLICY_VERSION,
        "deployment_checker": DEPLOYMENT_CHECKER,
    }


def implementation_dependencies(
    authority,
    requirements,
    selection=None,
    plan=None,
    construct=None,
    candidate=None,
    *,
    expected_source_fingerprint=None,
    expected_request_fingerprint=None,
):
    from biocompiler.ir.implementation import (
        ImplementationRequest,
        ImplementationSelection,
        ImplementationPlan,
        ImplementationConstruct,
    )

    request = authority if isinstance(authority, ImplementationRequest) else None
    source = request.source if request is not None else authority
    require(
        isinstance(source, SOURCE_TYPES), "Expected complete frozen source authority."
    )
    require(
        isinstance(requirements, ImplementationRequirements),
        "Expected implementation requirements.",
    )
    if request is None:
        require(
            expected_request_fingerprint is None,
            "Source-only checking has no implementation request pin.",
        )
        hash_value(expected_source_fingerprint, "Independently expected source")
    else:
        hash_value(
            expected_request_fingerprint,
            "Independently expected implementation request",
        )
        if expected_source_fingerprint is None:
            expected_source_fingerprint = source.fingerprint
        hash_value(expected_source_fingerprint, "Independently expected source")
    for value, cls in (
        (selection, ImplementationSelection),
        (plan, ImplementationPlan),
        (construct, ImplementationConstruct),
        (candidate, PayloadMolecule),
    ):
        require(
            value is None or isinstance(value, cls),
            "Invalid implementation stage artifact.",
        )
    values = (selection, plan, construct, candidate)
    require(
        all(
            value is None
            or (request is not None and all(x is not None for x in values[:index]))
            for index, value in enumerate(values)
        ),
        "Implementation stages require their full preceding authority chain.",
    )
    build = source if hasattr(source, "intent") else source.build_request
    return {
        "source": source.fingerprint,
        "source_artifact": fingerprint(source.to_dict()),
        "expected_source": expected_source_fingerprint,
        "target": build.target.fingerprint if build.target is not None else None,
        "request": request.fingerprint if request is not None else None,
        "expected_request": expected_request_fingerprint,
        "library": request.library.fingerprint if request is not None else None,
        "requirements": requirements.fingerprint,
        "selection": selection.fingerprint if selection is not None else None,
        "plan": plan.fingerprint if plan is not None else None,
        "construct": construct.fingerprint if construct is not None else None,
        "candidate": candidate.fingerprint if candidate is not None else None,
        "checker": CHECKER_VERSION,
        "structural_checker": STRUCTURAL_CHECKER_VERSION,
        "profiles": _profiles(),
        "schemas": _schemas(),
    }


@dataclass(frozen=True)
class ImplementationVerificationResult(JsonArtifact):
    stage: str
    outcome: CheckOutcome
    dependencies: Mapping
    diagnostics: tuple[PayloadDiagnostic, ...]
    checks: tuple[str, ...]
    unresolved: tuple[ImplementationObligation, ...]
    source_node_ids: tuple[str, ...]
    scope: str = "partial_implementation_research"
    physical_function: str = "unestablished"
    therapeutic_implementation: str = "partial"
    human_therapeutic_admission: str = "not_admitted"
    claim_scope: str = CLAIM_SCOPE
    schema_version: ClassVar[str] = (
        "biocompiler.implementation_verification_result.v0.1"
    )

    def __post_init__(self):
        require(
            isinstance(self.stage, str) and self.stage in _STAGES,
            "Invalid implementation check stage.",
        )
        require(
            isinstance(self.outcome, CheckOutcome), "Invalid implementation outcome."
        )
        fields(
            self.dependencies,
            {
                "source",
                "source_artifact",
                "expected_source",
                "target",
                "request",
                "expected_request",
                "library",
                "requirements",
                "selection",
                "plan",
                "construct",
                "candidate",
                "checker",
                "structural_checker",
                "profiles",
                "schemas",
            },
            "Implementation check dependencies",
        )
        for key in ("source", "source_artifact", "expected_source", "requirements"):
            hash_value(self.dependencies[key], key)
        if self.dependencies["target"] is not None:
            hash_value(self.dependencies["target"], "target")
        index = _STAGES.index(self.stage)
        for key in ("request", "expected_request", "library"):
            value = self.dependencies[key]
            require(
                (value is not None) == (index > 0),
                "Implementation request inventory differs from check stage.",
            )
            if value is not None:
                hash_value(value, key)
        for ordinal, key in enumerate(
            ("selection", "plan", "construct", "candidate"), start=1
        ):
            value = self.dependencies[key]
            require(
                (value is not None) == (index >= ordinal),
                "Implementation stage inventory is incomplete.",
            )
            if value is not None:
                hash_value(value, key)
        require(
            self.dependencies["checker"] == CHECKER_VERSION
            and self.dependencies["structural_checker"] == STRUCTURAL_CHECKER_VERSION
            and freeze_json(self.dependencies["profiles"]) == freeze_json(_profiles())
            and freeze_json(self.dependencies["schemas"]) == freeze_json(_schemas()),
            "Historical implementation checks require current-tool reconstruction.",
        )
        object.__setattr__(self, "dependencies", freeze_json(self.dependencies))
        require(
            isinstance(self.diagnostics, (tuple, list))
            and all(isinstance(item, PayloadDiagnostic) for item in self.diagnostics),
            "Invalid implementation diagnostics.",
        )
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        require(
            self.outcome == _outcome(self.diagnostics),
            "Implementation outcome differs from diagnostics.",
        )
        require(
            isinstance(self.checks, (tuple, list))
            and tuple(self.checks) == _checks(self.stage),
            "Incomplete implementation check inventory.",
        )
        object.__setattr__(self, "checks", tuple(self.checks))
        require(
            isinstance(self.unresolved, (tuple, list))
            and all(
                isinstance(item, ImplementationObligation) for item in self.unresolved
            ),
            "Invalid unresolved implementation obligations.",
        )
        object.__setattr__(self, "unresolved", tuple(self.unresolved))
        require(
            isinstance(self.source_node_ids, (tuple, list))
            and all(isinstance(item, str) and item for item in self.source_node_ids)
            and len(set(self.source_node_ids)) == len(self.source_node_ids),
            "Invalid implementation source inventory.",
        )
        object.__setattr__(self, "source_node_ids", tuple(self.source_node_ids))
        source_ids = set(self.source_node_ids)
        require(
            len({item.id for item in self.unresolved}) == len(self.unresolved)
            and all(set(item.source_ids) <= source_ids for item in self.unresolved)
            and source_ids
            <= {identity for item in self.unresolved for identity in item.source_ids},
            "Implementation result obligations must preserve source coverage without duplicate identities.",
        )
        require(
            self.scope == "partial_implementation_research"
            and self.physical_function == "unestablished"
            and self.therapeutic_implementation == "partial"
            and self.human_therapeutic_admission == "not_admitted"
            and self.claim_scope == CLAIM_SCOPE,
            "Implementation correspondence cannot promote physical or therapeutic claims.",
        )

    @property
    def passed(self):
        return self.outcome is CheckOutcome.PASS

    def to_dict(self):
        def encode(value):
            if isinstance(value, (JsonArtifact, PayloadDiagnostic)):
                return value.to_dict()
            if isinstance(value, CheckOutcome):
                return value.value
            if isinstance(value, tuple):
                return [encode(item) for item in value]
            return thaw_json(value)

        return {"schema_version": self.schema_version} | {
            item.name: encode(getattr(self, item.name))
            for item in dataclass_fields(self)
        }

    @classmethod
    def from_dict(cls, data):
        try:
            fields(
                data,
                {item.name for item in dataclass_fields(cls)} | {"schema_version"},
                cls.__name__,
            )
            require(
                data["schema_version"] == cls.schema_version,
                "Unknown implementation result schema.",
            )
            require(
                isinstance(data["outcome"], str)
                and data["outcome"] in {item.value for item in CheckOutcome},
                "Invalid implementation check outcome.",
            )
            values = {
                key: value for key, value in data.items() if key != "schema_version"
            }
            values["outcome"] = CheckOutcome(values["outcome"])
            values["diagnostics"] = tuple(
                PayloadDiagnostic.from_dict(item) for item in values["diagnostics"]
            )
            values["unresolved"] = tuple(
                ImplementationObligation.from_dict(item)
                for item in values["unresolved"]
            )
            return cls(**values)
        except SerializationError:
            raise
        except (TypeError, ValueError, KeyError, AttributeError, RecursionError) as exc:
            raise SerializationError(f"Invalid implementation result: {exc}") from exc

    def freshness(
        self,
        authority,
        requirements,
        selection=None,
        plan=None,
        construct=None,
        candidate=None,
        *,
        expected_source_fingerprint=None,
        expected_request_fingerprint=None,
    ):
        current = implementation_dependencies(
            authority,
            requirements,
            selection,
            plan,
            construct,
            candidate,
            expected_source_fingerprint=expected_source_fingerprint,
            expected_request_fingerprint=expected_request_fingerprint,
        )
        return FreshnessReport(
            tuple(
                sorted(
                    key
                    for key, value in current.items()
                    if freeze_json(value) != self.dependencies[key]
                )
            )
        )

    def is_fresh(self, *args, **kwargs):
        return self.freshness(*args, **kwargs).fresh


def _supported_source(build):
    """Independently recognize the bounded source shape, not a report label."""
    from biocompiler.ir.implementation_requirements import OPERATION_KINDS
    from biocompiler.semantics.types import BOOLEAN, PRODUCTION_RATE, TypeSpec

    program = build.intent
    lookup = {item.id: item for item in program.nodes}
    excluded = {
        "controller",
        "integrated",
        "curve",
        "curve_apply",
        "control_port",
        "channel",
        "channel_observation",
        "gradient",
    }
    if build.implementation_constraints or build.preferences:
        return False
    if any(
        item.kind not in OPERATION_KINDS or item.kind in excluded
        for item in program.nodes
    ):
        return False
    groups = {
        kind: program.find(kind=kind)
        for kind in ("role", "secretion", "action.secrete", "rule")
    }
    if any(len(group) != 1 for group in groups.values()):
        return False
    if sum(item.kind.startswith("action.") for item in program.nodes) != 1:
        return False
    role, declaration, action, rule = (groups[kind][0] for kind in groups)
    if not {role.id, declaration.id, rule.id} <= set(program.roots):
        return False
    attrs = declaration.attributes
    if (
        declaration.inputs != (role.id,)
        or declaration.role != role.id
        or declaration.data_type is not None
    ):
        return False
    if (
        set(attrs) != {"name", "product", "default", "activity"}
        or type(attrs["default"]) is not bool
        or not isinstance(attrs["product"], str)
        or not attrs["product"].strip()
        or attrs["activity"] != "requires_rule_or_controller"
    ):
        return False
    mode = action.attributes.get("rate")
    if (
        action.role != role.id
        or action.data_type is not None
        or set(action.attributes) != {"ongoing", "rate"}
        or action.attributes["ongoing"] is not True
        or not isinstance(mode, str)
        or mode not in ("unspecified", "expression")
    ):
        return False
    if (
        len(action.inputs) != (2 if mode == "expression" else 1)
        or action.inputs[0] != declaration.id
    ):
        return False
    if mode == "expression":
        dtype = lookup[action.inputs[1]].data_type
        if dtype is None or TypeSpec.from_dict(dtype) != PRODUCTION_RATE:
            return False
    attrs = rule.attributes
    if (
        rule.role != role.id
        or rule.data_type is not None
        or set(attrs)
        not in (
            {"trigger", "execution", "priority"},
            {"trigger", "execution", "priority", "name"},
        )
    ):
        return False
    if (
        attrs["trigger"] != "condition"
        or attrs["execution"] != "concurrent"
        or attrs["priority"] != "unspecified"
        or len(rule.inputs) != 3
        or rule.inputs[0] != role.id
        or rule.inputs[2] != action.id
    ):
        return False
    dtype = lookup[rule.inputs[1]].data_type
    return dtype is not None and TypeSpec.from_dict(dtype) == BOOLEAN


def _expected_requirements(source):
    """Reconstruct coverage and obligations directly from original authority."""
    from biocompiler.compiler.acceptance import HumanAcceptanceRequest
    from biocompiler.compiler.deployment import HumanDeploymentRequest
    from biocompiler.compiler.human_behavior import HumanBehaviorRequest
    from biocompiler.compiler.request import BuildRequest
    from biocompiler.ir.implementation_requirements import (
        BOUNDED_SOURCE_PROFILE,
        DIAGNOSTIC_MESSAGES,
        OPERATION_KINDS,
        ImplementationDiagnostic,
        ProductRequirement,
    )
    from biocompiler.semantics.context import HumanTargetContext
    from biocompiler.semantics.types import PRODUCTION_RATE, TypeSpec, decode_binding
    from biocompiler.verification.deployment import check_deployment

    build = source if isinstance(source, BuildRequest) else source.build_request
    program = build.intent
    lookup = {item.id: item for item in program.nodes}
    inventory = tuple(item.id for item in program.nodes)
    roles = program.find(kind="role")
    owner = roles[0].id if len(roles) == 1 else None
    target_pin = build.target.fingerprint if build.target is not None else None
    wrapped_behavior = (
        source.behavior_request
        if isinstance(source, (HumanDeploymentRequest, HumanAcceptanceRequest))
        else source
        if isinstance(source, HumanBehaviorRequest)
        else None
    )
    wrapped_deployment = (
        source.deployment_request
        if isinstance(source, HumanAcceptanceRequest)
        else source
        if isinstance(source, HumanDeploymentRequest)
        else None
    )
    obligations, products, diagnostics = [], [], []

    def append_obligation(
        identity, kind, ids, operation, arguments, role=None, path=None
    ):
        refs = tuple(dict.fromkeys(ids))
        if refs:
            obligations.append(
                ImplementationObligation(
                    identity,
                    kind,
                    refs,
                    {"operation": operation, "arguments": arguments},
                    {
                        "role_id": role,
                        "target_fingerprint": target_pin,
                        "contract_path": path,
                    },
                )
            )

    def append_diagnostic(code, category, ids, details):
        diagnostics.append(
            ImplementationDiagnostic(
                code,
                category,
                tuple(dict.fromkeys(ids)),
                DIAGNOSTIC_MESSAGES[code],
                details,
            )
        )

    excluded = {
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
    for item in program.nodes:
        kind = OPERATION_KINDS.get(item.kind, "source_semantics")
        append_obligation(
            "source:" + item.id,
            kind,
            (item.id,),
            item.kind,
            item.to_dict(include_source=False),
            item.role,
        )
        if item.kind not in OPERATION_KINDS:
            append_diagnostic(
                "unknown_source_operation",
                "unsupported_semantics",
                (item.id,),
                {"operation": item.kind},
            )
        elif (
            item.kind in excluded
            or item.kind.startswith("action.")
            and item.kind != "action.secrete"
        ):
            append_diagnostic(
                "operation_profile_unsupported",
                "unsupported_semantics",
                (item.id,),
                {"operation": item.kind},
            )
        if item.kind in {"signal", "channel_observation", "gradient"}:
            append_diagnostic(
                "sensing_binding_missing",
                "missing_refinement",
                (item.id,),
                {"operation": item.kind, "accessibility": "requires_physical_binding"},
            )
        if item.kind == "qualitative" and (
            wrapped_behavior is None
            or wrapped_behavior.contract.predicate.predicate_id != item.id
        ):
            append_diagnostic(
                "predicate_refinement_missing",
                "missing_refinement",
                (item.id,),
                {
                    "band": thaw_json(item.attributes.get("band")),
                    "requires": "typed_threshold_and_observation",
                },
            )
        if item.kind == "goal" and (
            wrapped_behavior is None or wrapped_behavior.contract.goal_id != item.id
        ):
            append_diagnostic(
                "goal_refinement_missing",
                "missing_refinement",
                (item.id,),
                {"requires": "measurable_goal_refinement"},
            )
        if kind == "temporal_state":
            append_diagnostic(
                "temporal_implementation_missing",
                "missing_refinement",
                (item.id,),
                {"operation": item.kind},
            )

    for action in program.find(kind="action.secrete"):
        declaration = lookup.get(action.inputs[0]) if action.inputs else None
        mode = action.attributes.get("rate")
        accepted = declaration is not None and declaration.kind == "secretion"
        if accepted:
            product_name = declaration.attributes.get("product")
            accepted = (
                isinstance(product_name, str)
                and bool(product_name.strip())
                and declaration.role is not None
                and action.role == declaration.role
                and declaration.inputs == (declaration.role,)
                and declaration.attributes.get("activity")
                == "requires_rule_or_controller"
                and action.attributes.get("ongoing") is True
                and isinstance(mode, str)
                and mode in ("unspecified", "expression")
                and len(action.inputs) == (2 if mode == "expression" else 1)
            )
        rate_id = action.inputs[1] if accepted and mode == "expression" else None
        if rate_id is not None:
            dtype = lookup[rate_id].data_type
            accepted = (
                dtype is not None and TypeSpec.from_dict(dtype) == PRODUCTION_RATE
            )
        if not accepted:
            append_diagnostic(
                "secretion_action_unresolved",
                "unsupported_semantics",
                (action.id,),
                {"operation": action.kind},
            )
            continue
        installed = [
            item
            for item in program.nodes
            if item.kind == "rule"
            and len(item.inputs) >= 3
            and item.inputs[0] == action.role
            and item.role == action.role
            and action.id in item.inputs[2:]
        ]
        if not installed:
            append_diagnostic(
                "secretion_rule_missing",
                "missing_refinement",
                (action.id, declaration.id),
                {"action_id": action.id, "secretion_id": declaration.id},
            )
            continue
        rule_ids = tuple(item.id for item in installed)
        guards = tuple(dict.fromkeys(item.inputs[1] for item in installed))
        product_ids = tuple(
            dict.fromkeys(
                (
                    action.role,
                    declaration.id,
                    action.id,
                    *rule_ids,
                    *guards,
                    *((rate_id,) if rate_id is not None else ()),
                )
            )
        )
        product = ProductRequirement(
            "product:" + action.id,
            action.role,
            product_name,
            declaration.id,
            action.id,
            rule_ids,
            guards,
            rate_id,
            product_ids,
        )
        products.append(product)
        append_obligation(
            "encoding:" + action.id,
            "encoding",
            product_ids,
            "encode_requested_product",
            {"product_requirement": product.to_dict()},
            action.role,
        )
        append_obligation(
            "localization:" + action.id,
            "localization_processing",
            product_ids,
            "export_requested_product",
            {
                "product": product_name,
                "localization": "extracellular",
                "processing": "unspecified",
            },
            action.role,
        )
        append_obligation(
            "response:" + action.id,
            "quantitative",
            product_ids,
            "requested_secretion_response",
            {
                "rate_id": rate_id,
                "rate_expression": lookup[rate_id].to_dict(include_source=False)
                if rate_id is not None
                else None,
                "implementation": "unresolved",
            },
            action.role,
        )
        if rate_id is not None:
            rate = lookup[rate_id]
            closed = (
                rate.attributes.get("value")
                if rate.kind == "literal"
                else build.resolved_bindings.get(rate.attributes.get("name"))
                if rate.kind == "parameter"
                else None
            )
            if (
                closed is not None
                and decode_binding(closed, PRODUCTION_RATE).canonical_value < 0
            ):
                append_diagnostic(
                    "negative_secretion_rate",
                    "contradiction",
                    (action.id, rate_id),
                    {"rate_id": rate_id, "value": thaw_json(closed)},
                )

    represented = {item.secretion_id for item in products}
    referenced = {
        item.inputs[0]
        for item in program.nodes
        if item.kind == "action.secrete" and item.inputs
    }
    for item in program.find(kind="secretion"):
        if item.id not in represented | referenced:
            append_diagnostic(
                "secretion_rule_missing",
                "missing_refinement",
                (item.id,),
                {"action_id": None, "secretion_id": item.id},
            )

    append_obligation(
        "build:context",
        "source_semantics",
        inventory,
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
        owner,
        "build_request",
    )
    append_obligation(
        "target:context",
        "host_deployment",
        inventory,
        "target_context",
        {"target": build.target.to_dict() if build.target is not None else None},
        owner,
        "build_request.target",
    )
    append_obligation(
        "evidence:physical_function",
        "evidence_admission",
        inventory,
        "physical_function",
        {"support": "unestablished"},
        owner,
    )
    if build.target is None:
        append_diagnostic(
            "target_context_missing", "missing_refinement", inventory, {"target": None}
        )
    if build.implementation_constraints or build.preferences:
        append_diagnostic(
            "source_constraints_unsupported",
            "unsupported_semantics",
            inventory,
            {
                "implementation_constraints": thaw_json(
                    build.implementation_constraints
                ),
                "preferences": thaw_json(build.preferences),
            },
        )
    if isinstance(build.target, HumanTargetContext):
        append_obligation(
            "evidence:human_admission",
            "evidence_admission",
            inventory,
            "human_therapeutic_admission",
            {"admission": "not_admitted"},
            owner,
            "build_request.target.human_target",
        )
    if wrapped_behavior is not None:
        append_obligation(
            "contract:behavior",
            "quantitative",
            inventory,
            "human_behavior",
            wrapped_behavior.contract.to_dict(),
            owner,
            "behavior.contract",
        )
    if wrapped_deployment is not None:
        append_obligation(
            "contract:deployment",
            "host_deployment",
            inventory,
            "human_deployment",
            wrapped_deployment.deployment.to_dict(),
            owner,
            "deployment",
        )
        for code in check_deployment(wrapped_deployment).diagnostics:
            if code in {
                "expression_onset_after_behavior_start",
                "expression_duration_does_not_cover_behavior",
            }:
                diagnostic_code, category = "deployment_contradiction", "contradiction"
            elif code in {
                "deployment_destination_profile_unsupported",
                "same_cell_co_payload_delivery_unsupported",
            }:
                diagnostic_code, category = (
                    "deployment_unsupported",
                    "unsupported_semantics",
                )
            else:
                diagnostic_code, category = (
                    "deployment_missing_refinement",
                    "missing_refinement",
                )
            append_diagnostic(
                diagnostic_code,
                category,
                inventory,
                {"deployment_diagnostic": code, "contract_path": "deployment"},
            )
    if isinstance(source, HumanAcceptanceRequest):
        append_obligation(
            "contract:acceptance",
            "control",
            inventory,
            "human_acceptance",
            source.acceptance.to_dict(),
            owner,
            "acceptance",
        )
        for identity, path in (
            ("healthy_context_control_missing", "healthy_measurement"),
            ("shutdown_control_missing", "shutdown"),
            ("input_loss_control_missing", "input_availability"),
        ):
            append_diagnostic(
                identity,
                "missing_refinement",
                inventory,
                {
                    "contract_path": "acceptance." + path,
                    "source_guard_policy": "unchanged_no_implicit_override",
                },
            )
    supported = _supported_source(build)
    if not supported:
        append_diagnostic(
            "source_profile_unsupported",
            "unsupported_semantics",
            inventory,
            {"requested_profile": BOUNDED_SOURCE_PROFILE},
        )
    return ImplementationRequirements(
        source,
        source.fingerprint,
        inventory,
        tuple(products),
        tuple(obligations),
        tuple(diagnostics),
    ), supported


def _structural_expectation(architecture):
    """Represent independently concatenated regions for the neutral RNA kernel."""
    from biocompiler.ir.molecular_design import FragmentPlacement
    from biocompiler.semantics.coordinates import SequenceRange

    coding = "".join(segment.sequence.sequence for segment in architecture.segments)
    regions = [
        (
            "five_prime_utr",
            architecture.five_prime_utr.sequence,
            architecture.five_prime_utr.fingerprint,
        ),
        (
            "cds",
            coding,
            fingerprint([segment.fingerprint for segment in architecture.segments]),
        ),
        (
            "three_prime_utr",
            architecture.three_prime_utr.sequence,
            architecture.three_prime_utr.fingerprint,
        ),
    ]
    if architecture.poly_a is not None:
        regions.append(
            ("poly_a", architecture.poly_a.sequence, architecture.poly_a.fingerprint)
        )
    fragments, placements, position = [], [], 0
    for kind, sequence, pin in regions:
        fragments.append(
            SimpleNamespace(
                id=kind,
                sequence=sequence,
                sequence_sha256=_sha(sequence),
                fingerprint=pin,
                alphabet="RNA",
            )
        )
        placements.append(
            FragmentPlacement(
                kind,
                kind,
                kind,
                pin,
                SequenceRange(0, len(sequence)),
                SequenceRange(position, position + len(sequence)),
                architecture.precursor_protein if kind == "cds" else None,
            )
        )
        position += len(sequence)
    return SimpleNamespace(
        fragments=tuple(fragments),
        placements=tuple(placements),
        features=architecture.features,
        unknown_features=(),
    )


def _expected_selection(request, requirements, supported):
    from biocompiler.ir.implementation import (
        DEPENDENCY_COMPARTMENTS,
        PLAN_ROLES,
        ImplementationAlternative,
        ImplementationRejection,
        ImplementationSelection,
    )
    from biocompiler.registry.references import translate_cds
    from biocompiler.semantics.context import HumanTargetContext, PayloadFormat

    if not supported or len(requirements.products) != 1:
        return ImplementationSelection(
            request.fingerprint,
            requirements.fingerprint,
            (),
            None,
            ("unsupported_source_profile",),
        )
    product = requirements.products[0]
    matching = sorted(
        (
            item
            for item in request.library.architectures
            if item.product == product.product
        ),
        key=lambda item: item.id,
    )
    alternatives = []
    for architecture in matching:
        reasons = []

        def reject(code, message, status="fail"):
            reasons.append(ImplementationRejection(code, message, status))

        target = request.target
        if target is None:
            reject(
                "target_required",
                "An original target context is required.",
                "unsupported",
            )
        elif target.payload_format is not PayloadFormat.RNA:
            reject(
                "unsupported_modality",
                "This family requires RNA; implicit DNA conversion is unsupported.",
                "unsupported",
            )
        if any(item.category == "contradiction" for item in requirements.diagnostics):
            reject(
                "source_contradiction",
                "The retained source contains contradictory required behavior.",
            )
        if request.constraints.require_implementation_complete:
            reject(
                "implementation_incomplete",
                "This structural family leaves required sensing, control and physical function unresolved.",
                "unsupported",
            )
        allowlist = request.constraints.allowed_architecture_ids
        if allowlist and architecture.id not in allowlist:
            reject(
                "architecture_not_allowed",
                "Architecture is outside the authored allowlist.",
            )
        if target is None or architecture.target_fingerprint != target.fingerprint:
            reject(
                "target_mismatch",
                "Architecture declares a different exact target context.",
            )
        if target is not None and not {item[2] for item in PLAN_ROLES} <= set(
            target.compartments
        ):
            reject(
                "target_compartments",
                "Target does not declare every compartment required by this architecture.",
            )
        authorities = (
            architecture.five_prime_utr,
            *(item.sequence for item in architecture.segments),
            architecture.three_prime_utr,
            *((architecture.poly_a,) if architecture.poly_a is not None else ()),
        )
        length = sum(len(item.sequence) for item in authorities)
        if (
            request.constraints.max_length is not None
            and length > request.constraints.max_length
        ):
            reject(
                "max_length_exceeded",
                "Assembled RNA exceeds the authored maximum length.",
            )
        for authority in authorities:
            if _sha(authority.sequence) != authority.sequence_sha256:
                reject(
                    "sequence_hash",
                    f"Sequence authority {authority.id!r} differs from its pinned bases.",
                )
        for segment in architecture.segments:
            bases = segment.sequence.sequence
            if len(bases) % 3 != 0:
                reject(
                    "segment_frame", f"Coding segment {segment.id!r} is not in frame."
                )
            elif segment.kind == "terminal_stop":
                if bases not in ("UAA", "UAG", "UGA"):
                    reject(
                        "segment_translation",
                        f"Coding segment {segment.id!r} is not exactly one stop codon.",
                    )
            else:
                try:
                    translated = translate_cds("AUG" + bases + "UAA", "RNA")[1:-1]
                except SerializationError:
                    reject(
                        "segment_translation",
                        f"Coding segment {segment.id!r} contains invalid translation or stops.",
                    )
                else:
                    if translated != segment.protein_sequence:
                        reject(
                            "segment_translation",
                            f"Coding segment {segment.id!r} differs from its declared peptide.",
                        )
        if (
            "".join(item.protein_sequence for item in architecture.segments)
            != architecture.precursor_protein
        ):
            reject(
                "precursor_correspondence",
                "Declared precursor differs from its ordered segment peptides.",
            )
        mature_index = next(
            index
            for index, item in enumerate(architecture.segments)
            if item.kind == "mature_product"
        )
        mature = architecture.segments[mature_index]
        if mature.protein_sequence != architecture.mature_protein:
            reject(
                "mature_product_correspondence",
                "Declared mature product differs from the mature coding segment.",
            )
        prefix_residues = sum(
            len(item.protein_sequence) for item in architecture.segments[:mature_index]
        )
        if (
            architecture.cleavage_after_aa != prefix_residues
            or architecture.precursor_protein[architecture.cleavage_after_aa : -1]
            != architecture.mature_protein
        ):
            reject(
                "processing_correspondence",
                "The declared cleavage boundary does not yield the exact mature product.",
            )
        for diagnostic in structural_rna_diagnostics(
            _structural_expectation(architecture)
        ):
            reject(diagnostic.code, diagnostic.message, diagnostic.status)
        declared_providers = {item.id: item for item in request.library.providers}
        bindings = {
            item.dependency_id: item.provider_id
            for item in architecture.dependency_bindings
        }
        for dependency in sorted(architecture.dependencies, key=lambda item: item.id):
            if (
                dependency.required is not True
                or dependency.role != product.role_id
                or dependency.scope != "cell"
                or dependency.compartment
                != DEPENDENCY_COMPARTMENTS[dependency.capability]
            ):
                reject(
                    "dependency_context",
                    f"Dependency {dependency.id!r} differs from its required role, scope or compartment.",
                )
            provider = declared_providers.get(bindings[dependency.id])
            if provider is None or provider.kind == "unresolved":
                reject(
                    "dependency_unresolved",
                    f"Dependency {dependency.id!r} has no declared host or external provider.",
                    "unknown",
                )
                continue
            if provider.depends_on:
                reject(
                    "provider_prerequisites_unsupported",
                    f"Provider {provider.id!r} has prerequisites outside this bounded family.",
                    "unsupported",
                )
            if (
                target is not None
                and provider.kind == "host"
                and (
                    dependency.capability not in target.capabilities
                    or dependency.compartment not in target.compartments
                )
            ):
                reject(
                    "host_capability_undeclared",
                    f"Host dependency {dependency.id!r} is not declared by the original target.",
                )
            if (
                isinstance(target, HumanTargetContext)
                and provider.kind == "host"
                and not any(
                    item.capability == dependency.capability
                    and item.compartment == dependency.compartment
                    for item in target.human_target.host_dependencies
                )
            ):
                reject(
                    "human_host_dependency_undeclared",
                    f"Host dependency {dependency.id!r} is absent from the human target contract.",
                )
            capability = (
                dependency.capability,
                dependency.role,
                dependency.scope,
                dependency.compartment,
            )
            if (
                architecture.target_fingerprint not in provider.supported_targets
                or capability
                not in {
                    (item.id, item.role, item.scope, item.compartment)
                    for item in provider.capabilities
                }
            ):
                reject(
                    "dependency_incompatible",
                    f"Provider {provider.id!r} does not declare the exact dependency and target context.",
                )
        alternatives.append(
            ImplementationAlternative(
                architecture.id, architecture.fingerprint, length, tuple(reasons)
            )
        )
    feasible = [item for item in alternatives if not item.rejections]
    key = (
        (lambda item: (item.length_nt, item.architecture_id))
        if request.constraints.preference == "shortest"
        else (lambda item: item.architecture_id)
    )
    selected = min(feasible, key=key).architecture_id if feasible else None
    diagnostics = (
        ()
        if selected is not None
        else ("bounded_candidates_exhausted",)
        if matching
        else ("product_binding_unavailable",)
    )
    return ImplementationSelection(
        request.fingerprint,
        requirements.fingerprint,
        tuple(alternatives),
        selected,
        diagnostics,
    )


def _expected_plan(request, requirements, selection):
    from biocompiler.ir.implementation import (
        PLAN_EDGES,
        PLAN_ROLES,
        ImplementationDependency,
        ImplementationEdge,
        ImplementationPlan,
        ImplementationRole,
    )

    architecture = next(
        item
        for item in request.library.architectures
        if item.id == selection.selected_architecture_id
    )
    product = requirements.products[0]
    role_segments = {
        "translation": tuple(item.id for item in architecture.segments),
        "precursor": tuple(item.id for item in architecture.segments),
        "processing": tuple(
            item.id for item in architecture.segments if item.kind != "terminal_stop"
        ),
        "product": tuple(
            item.id for item in architecture.segments if item.kind == "mature_product"
        ),
        "export": (),
    }
    roles = tuple(
        ImplementationRole(
            identity, kind, compartment, (product.id,), role_segments[identity]
        )
        for identity, kind, compartment in PLAN_ROLES
    )
    provider_by_id = {item.id: item for item in request.library.providers}
    binding_by_id = {
        item.dependency_id: item.provider_id
        for item in architecture.dependency_bindings
    }
    dependencies = tuple(
        ImplementationDependency(item, provider_by_id.get(binding_by_id[item.id]))
        for item in sorted(architecture.dependencies, key=lambda item: item.id)
    )
    return ImplementationPlan(
        request.fingerprint,
        requirements.fingerprint,
        selection.fingerprint,
        architecture.id,
        architecture.fingerprint,
        product.id,
        product.source_ids,
        roles,
        tuple(ImplementationEdge(*item) for item in PLAN_EDGES),
        dependencies,
        tuple(item.id for item in requirements.obligations),
    )


def _expected_construct(request, requirements, plan):
    from biocompiler.ir.implementation import (
        ImplementationConstruct,
        ImplementationPlacement,
    )
    from biocompiler.semantics.coordinates import SequenceRange

    architecture = next(
        item
        for item in request.library.architectures
        if item.id == plan.architecture_id
    )
    placements = []
    base_cursor, residue_cursor = 0, 0

    def place(identity, kind, authority, role, residues=None):
        nonlocal base_cursor
        end = base_cursor + len(authority.sequence)
        placements.append(
            ImplementationPlacement(
                identity,
                kind,
                authority.id,
                authority.fingerprint,
                SequenceRange(0, len(authority.sequence)),
                SequenceRange(base_cursor, end),
                residues,
                (plan.product_requirement_id,),
                role,
            )
        )
        base_cursor = end

    place(
        "five_prime_utr", "five_prime_utr", architecture.five_prime_utr, "translation"
    )
    coding_start = base_cursor
    junctions = []
    for index, segment in enumerate(architecture.segments):
        peptide_length = (
            0 if segment.kind == "terminal_stop" else len(segment.protein_sequence)
        )
        residue_end = residue_cursor + peptide_length
        place(
            "segment:" + segment.id,
            segment.kind,
            segment.sequence,
            "product" if segment.kind == "mature_product" else "precursor",
            SequenceRange(residue_cursor, residue_end),
        )
        residue_cursor = residue_end
        if index < len(architecture.segments) - 1:
            junctions.append(base_cursor)
    place(
        "three_prime_utr",
        "three_prime_utr",
        architecture.three_prime_utr,
        "translation",
    )
    if architecture.poly_a is not None:
        place("poly_a", "poly_a", architecture.poly_a, "translation")
    return ImplementationConstruct(
        request.fingerprint,
        requirements.fingerprint,
        plan.fingerprint,
        architecture.id,
        requirements.build_request.intent.name + ".precursor",
        tuple(placements),
        architecture.precursor_protein,
        architecture.mature_protein,
        architecture.cleavage_after_aa,
        coding_start + 3 * architecture.cleavage_after_aa,
        tuple(junctions),
        architecture.features,
    )


def _expected_molecule(request, requirements, plan, construct):
    from biocompiler.semantics.coordinates import SequenceRange

    architecture = next(
        item
        for item in request.library.architectures
        if item.id == plan.architecture_id
    )
    coding = "".join(item.sequence.sequence for item in architecture.segments)
    locator = "implementation-request:" + request.fingerprint
    pieces = [
        (
            "five_prime_utr",
            architecture.five_prime_utr.sequence,
            architecture.five_prime_utr.source_locator,
        ),
        ("cds", coding, locator + "#composite-cds"),
        (
            "three_prime_utr",
            architecture.three_prime_utr.sequence,
            architecture.three_prime_utr.source_locator,
        ),
    ]
    if architecture.poly_a is not None:
        pieces.append(
            ("poly_a", architecture.poly_a.sequence, architecture.poly_a.source_locator)
        )
    regions, sequence = [], ""
    for kind, bases, source_locator in pieces:
        begin = len(sequence)
        sequence += bases
        regions.append(
            PayloadRegion(
                kind,
                kind,
                SequenceRange(begin, len(sequence)),
                SequenceRange(0, len(bases)),
                source_locator,
                architecture.precursor_protein if kind == "cds" else None,
            )
        )
    return PayloadMolecule(
        construct.molecule_id,
        "mature_linear_rna",
        "RNA",
        sequence,
        _sha(sequence),
        SequenceRange(0, len(sequence)),
        "linear",
        "single",
        tuple(regions),
        architecture.features,
        locator,
    )


def _verify(
    authority,
    requirements,
    selection=None,
    plan=None,
    construct=None,
    candidate=None,
    *,
    expected_source_fingerprint=None,
    expected_request_fingerprint=None,
):
    from biocompiler.ir.implementation import ImplementationRequest
    from biocompiler.ir.implementation_requirements import BOUNDED_SOURCE_PROFILE

    require(
        isinstance(authority, (ImplementationRequest, *SOURCE_TYPES)),
        "Expected complete typed implementation or source authority.",
    )
    authority = type(authority).from_dict(authority.to_dict())
    require(
        isinstance(requirements, ImplementationRequirements),
        "Expected implementation requirements.",
    )
    requirements = ImplementationRequirements.from_dict(requirements.to_dict())
    dependencies = implementation_dependencies(
        authority,
        requirements,
        selection,
        plan,
        construct,
        candidate,
        expected_source_fingerprint=expected_source_fingerprint,
        expected_request_fingerprint=expected_request_fingerprint,
    )
    request = authority if isinstance(authority, ImplementationRequest) else None
    source = request.source if request is not None else authority
    stage = _STAGES[
        max(
            index
            for index, value in enumerate(
                (requirements, selection, plan, construct, candidate)
            )
            if value is not None
        )
    ]
    diagnostics = []

    def reject(code, message):
        diagnostics.append(PayloadDiagnostic("fail", code, message))

    if source.fingerprint != dependencies["expected_source"]:
        reject(
            "source_authority",
            "Original source differs from its independently retained fingerprint.",
        )
    if request is not None and request.fingerprint != dependencies["expected_request"]:
        reject(
            "request_authority",
            "Implementation request differs from its independently retained fingerprint.",
        )
    expected_requirements, supported = _expected_requirements(source)
    if fingerprint(requirements.to_dict()) != fingerprint(
        expected_requirements.to_dict()
    ):
        reject(
            "requirements_correspondence",
            "Requirements, diagnostics or unresolved semantics differ from independent source reconstruction.",
        )
    expected_profile = BOUNDED_SOURCE_PROFILE if supported else None
    if requirements.supported_profile != expected_profile:
        reject(
            "source_profile",
            "Reported source support differs from independently recognized semantics.",
        )
    if selection is not None:
        expected_selection = _expected_selection(
            request, expected_requirements, supported
        )
        if fingerprint(selection.to_dict()) != fingerprint(
            expected_selection.to_dict()
        ):
            reject(
                "selection_correspondence",
                "Alternative inventory, constraints, reasons, pins or ranking differ from independent bounded search.",
            )
        if plan is not None:
            if expected_selection.selected_architecture_id is None:
                reject(
                    "no_selected_implementation",
                    "An empty or unsupported search cannot authorize a molecular implementation plan.",
                )
            else:
                expected_plan = _expected_plan(
                    request, expected_requirements, expected_selection
                )
                if fingerprint(plan.to_dict()) != fingerprint(expected_plan.to_dict()):
                    reject(
                        "plan_correspondence",
                        "Implementation roles, processing relations, providers or unresolved source obligations differ from authority.",
                    )
                if construct is not None:
                    expected_construct = _expected_construct(
                        request, expected_requirements, expected_plan
                    )
                    if fingerprint(construct.to_dict()) != fingerprint(
                        expected_construct.to_dict()
                    ):
                        reject(
                            "construct_correspondence",
                            "Composite source/base/protein ranges, processing boundaries, chemistry or requirement maps differ from authority.",
                        )
                    if candidate is not None:
                        expected_molecule = _expected_molecule(
                            request,
                            expected_requirements,
                            expected_plan,
                            expected_construct,
                        )
                        if fingerprint(candidate.to_dict()) != fingerprint(
                            expected_molecule.to_dict()
                        ):
                            reject(
                                "molecule_correspondence",
                                "Emitted RNA, region annotations, sequence pins or provenance differ from independent exact assembly.",
                            )
    return ImplementationVerificationResult(
        stage,
        _outcome(diagnostics),
        dependencies,
        tuple(diagnostics),
        _checks(stage),
        expected_requirements.obligations,
        expected_requirements.source_node_ids,
    )


def check_implementation_requirements(
    original_source, requirements, *, expected_source_fingerprint
):
    return _verify(
        original_source,
        requirements,
        expected_source_fingerprint=expected_source_fingerprint,
    )


def check_implementation_selection(
    request, requirements, selection, *, expected_request_fingerprint
):
    require(
        selection is not None, "Selection checking requires an actual selection report."
    )
    return _verify(
        request,
        requirements,
        selection,
        expected_request_fingerprint=expected_request_fingerprint,
    )


def check_implementation_plan(
    request, requirements, selection, plan, *, expected_request_fingerprint
):
    require(plan is not None, "Plan checking requires an actual implementation plan.")
    return _verify(
        request,
        requirements,
        selection,
        plan,
        expected_request_fingerprint=expected_request_fingerprint,
    )


def check_implementation_construct(
    request, requirements, selection, plan, construct, *, expected_request_fingerprint
):
    require(construct is not None, "Construct checking requires an actual construct.")
    return _verify(
        request,
        requirements,
        selection,
        plan,
        construct,
        expected_request_fingerprint=expected_request_fingerprint,
    )


def check_implementation(
    request,
    requirements,
    selection,
    plan,
    construct,
    candidate,
    *,
    expected_request_fingerprint,
):
    require(
        candidate is not None, "Molecule checking requires an actual emitted molecule."
    )
    return _verify(
        request,
        requirements,
        selection,
        plan,
        construct,
        candidate,
        expected_request_fingerprint=expected_request_fingerprint,
    )

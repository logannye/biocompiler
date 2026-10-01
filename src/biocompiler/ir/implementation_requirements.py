"""Frozen therapeutic requirements; importing an analysis never validates it.

These records describe requested functions and retained source semantics. They
select no mechanism and cannot establish physical or therapeutic function.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from biocompiler.artifacts.manifest import (
    _Record,
    _array,
    _decode_array,
    _hash,
    _plain_text,
)
from biocompiler.compiler.acceptance import HumanAcceptanceRequest
from biocompiler.compiler.deployment import HumanDeploymentRequest
from biocompiler.compiler.human_behavior import HumanBehaviorRequest
from biocompiler.compiler.request import BuildRequest
from biocompiler.ir.intent import freeze_json, thaw_json
from biocompiler.ir.serialization import names, require
from biocompiler.semantics.types import BOOLEAN, PRODUCTION_RATE, TypeSpec

PROFILE_VERSION = "biocompiler.implementation_requirements_profile.v0.1"
BOUNDED_SOURCE_PROFILE = "single_role_conditional_secretion.v0.1"
EVIDENCE_BOUNDARY = "specification_only_no_physical_function"
MAX_SOURCE_NODES = 1024
MAX_ANALYSIS_RECORDS = 8192
SOURCE_TYPES = (
    BuildRequest,
    HumanBehaviorRequest,
    HumanDeploymentRequest,
    HumanAcceptanceRequest,
)
OBLIGATION_KINDS = frozenset(
    {
        "encoding",
        "localization_processing",
        "sensing",
        "control",
        "temporal_state",
        "quantitative",
        "action",
        "host_deployment",
        "evidence_admission",
        "source_semantics",
    }
)
DIAGNOSTIC_CATEGORIES = frozenset(
    {"unsupported_semantics", "missing_refinement", "contradiction"}
)
DIAGNOSTIC_MESSAGES = freeze_json(
    {
        "unknown_source_operation": "The source operation has no requirement-analysis interpretation in this profile.",
        "operation_profile_unsupported": "This authored operation requires a separate molecular implementation profile.",
        "sensing_binding_missing": "A source observation needs a physical sensing and accessibility binding.",
        "predicate_refinement_missing": "A qualitative predicate needs an explicit physical observation and typed threshold refinement.",
        "goal_refinement_missing": "A therapeutic goal needs an explicit measurable refinement and supporting evidence.",
        "temporal_implementation_missing": "Temporal or state behavior remains a requirement without a molecular implementation.",
        "secretion_action_unresolved": "This secretion action lacks an unambiguous installed product, owner, or rate binding.",
        "secretion_rule_missing": "A declaration or uninstalled action does not request constitutive expression.",
        "negative_secretion_rate": "The closed requested secretion-rate value is negative.",
        "target_context_missing": "Molecular selection needs an explicit target context; none is supplied.",
        "source_constraints_unsupported": "Frozen implementation constraints or preferences require a supported interpretation before selection.",
        "source_profile_unsupported": "The full source is outside the bounded single-role conditional-secretion implementation profile.",
        "healthy_context_control_missing": "The healthy-context readout is evaluator-only; no cellular guard or override is inferred.",
        "shutdown_control_missing": "Shutdown needs an explicit source-control refinement and actuator; it cannot silently override the activation guard.",
        "input_loss_control_missing": "Cell input-access loss needs an explicit detector and response mapping, distinct from missing evaluator observations.",
        "deployment_contradiction": "Known declared expression timing contradicts the required behavior window.",
        "deployment_unsupported": "The frozen deployment contains an unsupported dependency or destination.",
        "deployment_missing_refinement": "The frozen deployment lacks required exposure or expression-window bounds.",
    }
)

# Normative operation taxonomy, not an implementation or biological capability
# catalog. The complete source node accompanies every classification.
OPERATION_KINDS = freeze_json(
    {
        **{key: "host_deployment" for key in ("role",)},
        **{
            key: "sensing"
            for key in ("scope", "signal", "channel_observation", "gradient")
        },
        **{
            key: "control"
            for key in (
                "qualitative",
                "and",
                "or",
                "not",
                "at_least",
                "compare",
                "signature",
                "rule",
                "controller",
            )
        },
        **{
            key: "temporal_state"
            for key in (
                "held_for",
                "recently",
                "became_true",
                "followed_by",
                "memory",
                "memory.is_set",
                "state",
                "state.is",
                "action.state_set",
                "action.pulse",
            )
        },
        **{
            key: "quantitative"
            for key in (
                "literal",
                "parameter",
                "add",
                "subtract",
                "multiply",
                "divide",
                "negate",
                "integrated",
                "curve",
                "curve_apply",
                "control_port",
            )
        },
        "secretion": "localization_processing",
        "goal": "evidence_admission",
        "channel": "sensing",
        **{
            key: "action"
            for key in (
                "action.report",
                "action.eliminate",
                "action.engulf",
                "action.secrete",
                "action.present",
                "action.retain",
                "action.expand",
                "action.rest",
                "action.differentiate",
                "action.emit",
                "action.migrate_toward",
            )
        },
    }
)


def source_request_from_dict(data):
    require(
        isinstance(data, Mapping),
        "Implementation source must be a frozen request object.",
    )
    require(
        isinstance(data.get("schema_version"), str),
        "Implementation source requires an explicit schema.",
    )
    _json(data, "Implementation source")
    cls = {item.schema_version: item for item in SOURCE_TYPES}.get(
        data.get("schema_version")
    )
    require(cls is not None, "Unsupported implementation source request schema.")
    # Existing wrapped contract readers accept ordinary JSON dictionaries. A
    # frozen pass-manager document is equivalent authority, not a different
    # source; thaw containers without rewriting any values or provenance.
    return cls.from_dict(thaw_json(data))


def _ids(value, label):
    result = names(value, label)
    require(len(result) <= MAX_ANALYSIS_RECORDS, f"Too many {label}.")
    for item in result:
        _plain_text(item, label)
    return result


def _json(value, label):
    require(isinstance(value, Mapping), f"{label} must be an object.")
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        require(
            depth <= 64 and count <= 131072, f"{label} exceeds bounded JSON complexity."
        )
        if isinstance(item, Mapping):
            for key in item:
                require(isinstance(key, str), f"{label} keys must be strings.")
                try:
                    key.encode("utf-8")
                except UnicodeError:
                    require(False, f"{label} requires valid UTF-8 keys.")
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, (list, tuple)):
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            require(len(item) <= 1048576, f"{label} contains oversized text.")
            try:
                item.encode("utf-8")
            except UnicodeError:
                require(False, f"{label} requires valid UTF-8.")
    return freeze_json(value)


def _records(value, cls):
    require(isinstance(value, (tuple, list)), "Analysis records must be an array.")
    require(len(value) <= MAX_ANALYSIS_RECORDS, "Too many analysis records.")
    return _decode_array(value, cls)


@dataclass(frozen=True)
class ProductRequirement(_Record):
    id: str
    role_id: str
    product: str
    secretion_id: str
    action_id: str
    rule_ids: tuple[str, ...]
    guard_ids: tuple[str, ...]
    rate_id: str | None
    source_ids: tuple[str, ...]
    requested_localization: str = "extracellular"
    requested_processing: str = "unspecified"
    schema_version: ClassVar[str] = "biocompiler.product_requirement.v0.1"

    def __post_init__(self):
        for key in ("id", "role_id", "product", "secretion_id", "action_id"):
            _plain_text(getattr(self, key), key)
        for key in ("rule_ids", "guard_ids", "source_ids"):
            object.__setattr__(self, key, _ids(getattr(self, key), key))
        require(
            self.rule_ids and self.guard_ids,
            "A product requirement needs installed source rules and guards.",
        )
        require(
            {
                self.role_id,
                self.secretion_id,
                self.action_id,
                *self.rule_ids,
                *self.guard_ids,
            }
            <= set(self.source_ids),
            "Product source correspondence is incomplete.",
        )
        if self.rate_id is not None:
            _plain_text(self.rate_id, "rate_id")
            require(
                self.rate_id in self.source_ids,
                "Rate expression must remain source-linked.",
            )
        require(
            self.requested_localization == "extracellular"
            and self.requested_processing == "unspecified",
            "This product profile describes a secretion request without inventing processing.",
        )


@dataclass(frozen=True)
class ImplementationObligation(_Record):
    id: str
    kind: str
    source_ids: tuple[str, ...]
    semantics: Mapping
    context: Mapping
    evidence_boundary: str = EVIDENCE_BOUNDARY
    status: str = "unresolved"
    schema_version: ClassVar[str] = "biocompiler.implementation_obligation.v0.1"

    def __post_init__(self):
        _plain_text(self.id, "Obligation ID")
        require(
            isinstance(self.kind, str) and self.kind in OBLIGATION_KINDS,
            "Unknown implementation obligation kind.",
        )
        object.__setattr__(
            self, "source_ids", _ids(self.source_ids, "Obligation source IDs")
        )
        require(bool(self.source_ids), "Obligations need source correspondence.")
        semantics, context = (
            _json(self.semantics, "Obligation semantics"),
            _json(self.context, "Obligation context"),
        )
        require(
            set(semantics) == {"operation", "arguments"},
            "Obligation semantics require an operation and arguments.",
        )
        _plain_text(semantics["operation"], "Obligation operation")
        require(
            isinstance(semantics["arguments"], Mapping),
            "Operation arguments must be an object.",
        )
        require(
            set(context) == {"role_id", "target_fingerprint", "contract_path"},
            "Obligation context fields differ from the profile.",
        )
        for key in ("role_id", "contract_path"):
            if context[key] is not None:
                _plain_text(context[key], key)
        if context["target_fingerprint"] is not None:
            _hash(context["target_fingerprint"], "Obligation target")
        object.__setattr__(self, "semantics", semantics)
        object.__setattr__(self, "context", context)
        require(
            self.evidence_boundary == EVIDENCE_BOUNDARY and self.status == "unresolved",
            "Requirement analysis cannot establish physical function or discharge obligations.",
        )


@dataclass(frozen=True)
class ImplementationDiagnostic(_Record):
    code: str
    category: str
    source_ids: tuple[str, ...]
    message: str
    details: Mapping
    schema_version: ClassVar[str] = "biocompiler.implementation_diagnostic.v0.1"

    def __post_init__(self):
        _plain_text(self.code, "Diagnostic code")
        _plain_text(self.message, "Diagnostic message")
        require(
            isinstance(self.category, str) and self.category in DIAGNOSTIC_CATEGORIES,
            "Unknown implementation diagnostic category.",
        )
        object.__setattr__(
            self, "source_ids", _ids(self.source_ids, "Diagnostic source IDs")
        )
        object.__setattr__(self, "details", _json(self.details, "Diagnostic details"))


@dataclass(frozen=True)
class ImplementationRequirements(_Record):
    source: (
        BuildRequest
        | HumanBehaviorRequest
        | HumanDeploymentRequest
        | HumanAcceptanceRequest
    )
    source_fingerprint: str
    source_node_ids: tuple[str, ...]
    products: tuple[ProductRequirement, ...]
    obligations: tuple[ImplementationObligation, ...]
    diagnostics: tuple[ImplementationDiagnostic, ...]
    profile: str = PROFILE_VERSION
    scope: str = "implementation_requirements_only"
    physical_function: str = "unestablished"
    completion: str = "analysis_only"
    schema_version: ClassVar[str] = "biocompiler.implementation_requirements.v0.1"
    _decoders: ClassVar[dict] = {
        "source": source_request_from_dict,
        "products": lambda value: _records(value, ProductRequirement),
        "obligations": lambda value: _records(value, ImplementationObligation),
        "diagnostics": lambda value: _records(value, ImplementationDiagnostic),
    }

    def __post_init__(self):
        require(
            isinstance(self.source, SOURCE_TYPES),
            "Expected complete frozen implementation source.",
        )
        _json(self.source.to_dict(), "Implementation source")
        object.__setattr__(
            self, "source", source_request_from_dict(self.source.to_dict())
        )
        require(
            len(self.build_request.intent.nodes) <= MAX_SOURCE_NODES,
            "Implementation analysis exceeds its source-node limit.",
        )
        _hash(self.source_fingerprint, "Implementation source")
        require(
            self.source_fingerprint == self.source.fingerprint,
            "Implementation analysis source fingerprint differs from retained authority.",
        )
        ids = _ids(self.source_node_ids, "Source node IDs")
        require(
            ids == tuple(node.id for node in self.build_request.intent.nodes),
            "Implementation analysis must preserve every source node in order.",
        )
        object.__setattr__(self, "source_node_ids", ids)
        for key, cls in (
            ("products", ProductRequirement),
            ("obligations", ImplementationObligation),
            ("diagnostics", ImplementationDiagnostic),
        ):
            records = _array(getattr(self, key), cls, key)
            require(len(records) <= MAX_ANALYSIS_RECORDS, f"Too many {key}.")
            require(
                all(set(item.source_ids) <= set(ids) for item in records),
                f"Unknown source correspondence in {key}.",
            )
            if key != "diagnostics":
                require(
                    len({item.id for item in records}) == len(records),
                    f"Duplicate {key} IDs.",
                )
            object.__setattr__(self, key, records)
        require(
            set(ids)
            <= {identity for item in self.obligations for identity in item.source_ids},
            "Implementation obligations omit source nodes.",
        )
        require(
            self.profile == PROFILE_VERSION
            and self.scope == "implementation_requirements_only"
            and self.physical_function == "unestablished"
            and self.completion == "analysis_only",
            "Unsupported implementation analysis scope or promoted claim.",
        )

    @property
    def build_request(self):
        return (
            self.source
            if isinstance(self.source, BuildRequest)
            else self.source.build_request
        )

    @property
    def target(self):
        return self.build_request.target

    @property
    def supported_profile(self):
        """Source-shape eligibility only; never a physical implementation claim.

        This is computed from retained authority, not serialized producer labels.
        General source operations remain inspectable even outside this profile.
        """
        source = self.build_request
        nodes = {node.id: node for node in source.intent.nodes}
        unsupported = {
            "controller",
            "integrated",
            "curve",
            "curve_apply",
            "control_port",
            "channel",
            "channel_observation",
            "gradient",
        }
        if (
            source.implementation_constraints
            or source.preferences
            or any(
                node.kind not in OPERATION_KINDS or node.kind in unsupported
                for node in nodes.values()
            )
        ):
            return None
        groups = [
            source.intent.find(kind=kind)
            for kind in ("role", "secretion", "action.secrete", "rule")
        ]
        if (
            any(len(group) != 1 for group in groups)
            or sum(node.kind.startswith("action.") for node in nodes.values()) != 1
        ):
            return None
        role, secretion, action, rule = (group[0] for group in groups)
        if not {role.id, secretion.id, rule.id} <= set(source.intent.roots):
            return None
        if (
            secretion.inputs != (role.id,)
            or secretion.role != role.id
            or secretion.data_type is not None
            or set(secretion.attributes) != {"name", "product", "default", "activity"}
            or type(secretion.attributes.get("default")) is not bool
            or not isinstance(secretion.attributes.get("product"), str)
            or not secretion.attributes["product"].strip()
            or secretion.attributes.get("activity") != "requires_rule_or_controller"
        ):
            return None
        if (
            action.role != role.id
            or action.data_type is not None
            or set(action.attributes) != {"ongoing", "rate"}
            or action.attributes.get("ongoing") is not True
            or not isinstance(action.attributes.get("rate"), str)
            or action.attributes.get("rate") not in {"unspecified", "expression"}
            or len(action.inputs)
            != (2 if action.attributes.get("rate") == "expression" else 1)
            or action.inputs[0] != secretion.id
        ):
            return None
        if len(action.inputs) == 2:
            rate_type = nodes[action.inputs[1]].data_type
            if rate_type is None or TypeSpec.from_dict(rate_type) != PRODUCTION_RATE:
                return None
        attrs = rule.attributes
        if (
            rule.role != role.id
            or rule.data_type is not None
            or not {"trigger", "execution", "priority"} <= set(attrs)
            or set(attrs) - {"trigger", "execution", "priority", "name"}
            or attrs.get("trigger") != "condition"
            or attrs.get("execution") != "concurrent"
            or attrs.get("priority") != "unspecified"
            or len(rule.inputs) != 3
            or rule.inputs[0] != role.id
            or rule.inputs[2] != action.id
        ):
            return None
        guard = nodes[rule.inputs[1]]
        if guard.data_type is None or TypeSpec.from_dict(guard.data_type) != BOOLEAN:
            return None
        return BOUNDED_SOURCE_PROFILE

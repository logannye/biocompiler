"""Independent R0 scope checks, never molecular or biological verification.

The checker consumes declarations only. It imports no selector, constructor,
emitter or model runner. Fresh replay requires the original complete request
from an independent caller; a saved assessment is historical data, not authority.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from biocompiler.errors import SerializationError
from biocompiler.ir import circuit_profile as circuit_ir
from biocompiler.ir.intent import freeze_json, thaw_json
from biocompiler.ir.payload import hash_value
from biocompiler.ir.serialization import (
    JsonArtifact,
    fields,
    fingerprint,
    name,
    names,
    parse_json,
    require,
)
from biocompiler.semantics import admission
from biocompiler.semantics.context import HumanTargetContext, PayloadFormat
from biocompiler.verification.evidence import CheckOutcome

CHECKER_VERSION = "biocompiler.circuit_profile_checker.v0.1"
CLAIM_SCOPE = (
    "Declared human circuit scope only; no molecule or biological function "
    "is established."
)
ELIGIBILITY_BASIS = "declaration_or_ontology_contract_not_empirical"
_DIMENSIONS = {
    "base_identity": "unsupported",
    "source_nominal_specification": "unsupported",
    "complete_molecule_identity": "unsupported",
    "mechanism_correspondence": "unsupported",
    "model_validation": "unsupported",
    "empirical_validation": "unknown",
    "human_admission": "not_admitted",
}
_FIXED_FIELDS = {
    "claim_scope": CLAIM_SCOPE,
    "eligibility_basis": ELIGIBILITY_BASIS,
    "outcome": "unsupported",
    "molecular_generation": "unimplemented",
    "behavior_compilation": "unimplemented",
    "human_therapeutic_admission": "not_admitted",
}
_IDENTITY_KEYS = (
    "request",
    "target",
    "recipient",
    "source_experiment",
    "source_request",
    "source_request_artifact",
)
_DEPENDENCY_KEYS = {*_IDENTITY_KEYS, "checker", "profile", "admission_policy"}
MAX_ASSESSMENT_JSON_BYTES = 2_000_000
PUBLICATION_NEWLINE_BYTES = 1


def _dependencies(request):
    def identity(value):
        return value.fingerprint if value is not None else None

    return {
        "request": request.fingerprint,
        "target": identity(request.target),
        "recipient": identity(request.recipient),
        "source_experiment": identity(request.source_experiment),
        "source_request": identity(request.source_request),
        "source_request_artifact": (
            fingerprint(request.source_request.to_dict())
            if request.source_request is not None
            else None
        ),
        "checker": CHECKER_VERSION,
        "profile": circuit_ir.PROFILE_VERSION,
        "admission_policy": admission.ADMISSION_POLICY_VERSION,
    }


@dataclass(frozen=True)
class CircuitProfileAssessment(JsonArtifact):
    """Historical scope decision with separate, deliberately unresolved claims."""

    request: circuit_ir.CircuitProfileRequest
    eligibility: str
    dimensions: Mapping
    diagnostics: tuple[str, ...]
    dependencies: Mapping
    schema_version: ClassVar[str] = "biocompiler.circuit_profile_assessment.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.request, circuit_ir.CircuitProfileRequest),
            "A circuit assessment requires its complete request snapshot.",
        )
        object.__setattr__(
            self,
            "request",
            circuit_ir.CircuitProfileRequest.from_dict(self.request.to_dict()),
        )
        require(
            isinstance(self.eligibility, str)
            and self.eligibility
            in {"declared_human_immune_target", "human_reference_only"},
            "Invalid declared circuit eligibility.",
        )
        fields(self.dimensions, set(_DIMENSIONS), "Circuit evidence dimensions")
        require(
            all(
                type(self.dimensions[key]) is str and self.dimensions[key] == value
                for key, value in _DIMENSIONS.items()
            ),
            "R0 cannot establish molecular, model, empirical or admission claims.",
        )
        object.__setattr__(self, "dimensions", freeze_json(self.dimensions))
        require(
            isinstance(self.diagnostics, (tuple, list)) and len(self.diagnostics) <= 32,
            "Circuit assessment diagnostic limit exceeded.",
        )
        diagnostics = names(self.diagnostics, "Circuit scope diagnostics")
        require(bool(diagnostics), "Circuit scope needs explicit limitations.")
        require(
            all(len(item) <= 1024 for item in diagnostics),
            "Circuit assessment diagnostic text limit exceeded.",
        )
        object.__setattr__(self, "diagnostics", tuple(sorted(diagnostics)))
        fields(self.dependencies, _DEPENDENCY_KEYS, "Circuit policy dependencies")
        actual = _dependencies(self.request)
        for key in _IDENTITY_KEYS:
            value = self.dependencies[key]
            if value is not None:
                hash_value(value, f"Circuit dependency {key}")
            require(value == actual[key], f"Circuit dependency {key} differs.")
        for key in ("checker", "profile", "admission_policy"):
            name(self.dependencies[key], f"Circuit dependency {key}")
            require(
                len(self.dependencies[key]) <= 256,
                "Circuit policy identity text limit exceeded.",
            )
        object.__setattr__(self, "dependencies", freeze_json(self.dependencies))
        # Reserve the default published representation, including its final LF.
        # Compact JSON can fit while the indented CLI artifact exceeds the limit.
        self.to_json()

    def to_json(self, *, indent=2):
        try:
            text = super().to_json(indent=indent)
            size = len(text.encode("utf-8"))
        except (ValueError, TypeError, UnicodeError, RecursionError) as error:
            raise SerializationError(
                f"Invalid circuit assessment encoding: {error}"
            ) from error
        require(
            size + PUBLICATION_NEWLINE_BYTES <= MAX_ASSESSMENT_JSON_BYTES,
            "Circuit assessment byte limit exceeded (including publication newline).",
        )
        return text

    @property
    def boundary(self):
        return self.request.boundary

    @property
    def outcome(self):
        return CheckOutcome.UNSUPPORTED

    @property
    def human_therapeutic_admission(self):
        return "not_admitted"

    @property
    def molecular_generation(self):
        return "unimplemented"

    @property
    def behavior_compilation(self):
        return "unimplemented"

    @property
    def eligibility_basis(self):
        return ELIGIBILITY_BASIS

    @property
    def claim_scope(self):
        return CLAIM_SCOPE

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            **_FIXED_FIELDS,
            "request": self.request.to_dict(),
            "eligibility": self.eligibility,
            "dimensions": thaw_json(self.dimensions),
            "diagnostics": list(self.diagnostics),
            "dependencies": thaw_json(self.dependencies),
        }

    @classmethod
    def from_dict(cls, data):
        fields(
            data,
            {
                "schema_version",
                "request",
                "eligibility",
                "dimensions",
                "diagnostics",
                "dependencies",
                *_FIXED_FIELDS,
            },
            "CircuitProfileAssessment",
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported circuit assessment schema.",
        )
        for key, value in _FIXED_FIELDS.items():
            require(
                type(data[key]) is type(value) and data[key] == value,
                f"Invalid circuit assessment {key}.",
            )
        return cls(
            circuit_ir.CircuitProfileRequest.from_dict(data["request"]),
            data["eligibility"],
            data["dimensions"],
            data["diagnostics"],
            data["dependencies"],
        )

    @classmethod
    def from_json(cls, text):
        require(isinstance(text, str), "Circuit assessment JSON must be text.")
        try:
            size = len(text.encode("utf-8"))
        except UnicodeError as error:
            raise SerializationError(
                "Circuit assessment must be valid UTF-8."
            ) from error
        require(
            size <= MAX_ASSESSMENT_JSON_BYTES,
            "Circuit assessment byte limit exceeded.",
        )
        return cls.from_dict(parse_json(text))


def _declared_scope(request):
    """Check the supported declaration contract without inferring biology."""
    require(request.boundary in circuit_ir.BOUNDARIES, "Unknown circuit boundary.")
    require(
        request.molecular_form in (PayloadFormat.DNA, PayloadFormat.RNA),
        "Circuit product scope requires DNA or RNA.",
    )
    experiment = request.source_experiment
    if experiment is not None:
        require(
            experiment.recipient_taxon_id == 9606
            and experiment.system
            in {"human_cell_line", "primary_human_cells", "human_in_vivo"},
            "Circuit references require a human source experiment.",
        )
    if request.purpose == "human_reference":
        require(
            request.mode == "exact_reproduction"
            and experiment is not None
            and request.target is None
            and request.recipient is None
            and request.source_request is None,
            "Human reference context cannot become a deployment target.",
        )
        return "human_reference_only"
    require(
        request.purpose == "human_immune_payload"
        and isinstance(request.target, HumanTargetContext)
        and isinstance(request.recipient, circuit_ir.ImmuneRecipientIdentity),
        "A product request needs its own human immune target declaration.",
    )
    target, recipient = request.target, request.recipient
    contract = target.human_target.to_dict()
    require(
        contract["recipient_taxon_id"] == 9606
        and contract["engineering"] == "in_vivo"
        and target.payload_format == request.molecular_form,
        "Product scope is human in-vivo immune DNA/RNA deployment.",
    )
    require(
        isinstance(recipient.lineage, circuit_ir.ImmuneLineage)
        and recipient.target_fingerprint == target.fingerprint
        and recipient.cell_subtype_claim_fingerprint
        == target.human_target.cell_subtype.fingerprint
        and recipient.eligibility_basis == "declared"
        and recipient.empirical_support == "unestablished",
        "Immune eligibility must bind the exact declared target and subtype claim.",
    )
    if request.source_request is not None:
        require(
            isinstance(request.source_request, circuit_ir.SOURCE_TYPES)
            and request.source_request.target == target,
            "The complete original source must retain the deployment target.",
        )
    return "declared_human_immune_target"


def check_circuit_profile(request):
    """Recheck declarations at this boundary and explicitly refuse generation."""
    require(
        isinstance(request, circuit_ir.CircuitProfileRequest),
        "Expected a complete circuit profile request.",
    )
    request = circuit_ir.CircuitProfileRequest.from_dict(request.to_dict())
    eligibility = _declared_scope(request)
    diagnostics = {
        f"{request.boundary}:r0_molecular_generation_unimplemented",
        f"{request.boundary}:r0_behavior_compilation_unimplemented",
        f"{request.boundary}:human_therapeutic_use_not_admitted",
        "scope_eligibility_is_a_declaration_contract_not_empirical_proof",
        "no_bases_nominal_molecule_mechanism_or_model_checked",
        "empirical_validation_unestablished",
    }
    if eligibility == "human_reference_only":
        diagnostics.add("human_reference_is_subordinate_evidence_not_a_product_target")
    else:
        diagnostics.add("original_human_in_vivo_immune_target_obligations_retained")
        if request.source_request is None:
            diagnostics.add("source_intent_and_wrapped_contracts_not_supplied")
    if request.source_experiment is not None:
        diagnostics.add("source_experiment_does_not_replace_deployment_target")
        diagnostics.add("source_context_and_citations_do_not_establish_function")
        if request.source_experiment.immune_classification == "nonimmune":
            diagnostics.add("nonimmune_source_does_not_establish_immune_applicability")
        if request.source_experiment.system != "human_in_vivo":
            diagnostics.add("in_vitro_source_does_not_establish_in_vivo_applicability")
    return CircuitProfileAssessment(
        request,
        eligibility,
        _DIMENSIONS,
        tuple(sorted(diagnostics)),
        _dependencies(request),
    )


def verify_circuit_profile(assessment, *, expected_request):
    """Reconstruct current policy using separately supplied complete authority.

    Successful replay means only that the historical scope assessment agrees
    with the current checker. Its molecular and behavioral outcomes remain
    unsupported, its empirical dimension unknown, and human use not admitted.
    """
    require(
        isinstance(assessment, CircuitProfileAssessment)
        and isinstance(expected_request, circuit_ir.CircuitProfileRequest),
        "Fresh verification needs an assessment and independent complete request.",
    )
    saved = CircuitProfileAssessment.from_dict(assessment.to_dict())
    request = circuit_ir.CircuitProfileRequest.from_dict(expected_request.to_dict())
    require(
        saved.request.to_dict() == request.to_dict(),
        "Saved circuit assessment differs from the independent expected request.",
    )
    current = check_circuit_profile(request)
    require(
        saved.to_dict() == current.to_dict(),
        "Saved circuit assessment differs from current independent policy checks.",
    )
    return current

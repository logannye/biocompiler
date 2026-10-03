"""Explicit use and evidence context; schema validity is never human admission."""

from dataclasses import dataclass
from typing import ClassVar

from biocompiler.ir.component_contracts import ComponentRecord
from biocompiler.ir.serialization import names, require
from biocompiler.semantics.context import TargetContext
from biocompiler.semantics.human_target import TargetEvidence, _TargetRecord

ADMISSION_POLICY_VERSION = "biocompiler.human_admission_policy.v0.1"
BOUNDARIES = frozenset({"planning", "selection", "verification", "export"})
USES = frozenset({"software_test", "human_therapeutic"})


def _records(data, cls):
    require(isinstance(data, (tuple, list)), "Expected record array.")
    return tuple(cls.from_dict(item) for item in data)


def _hash(value):
    require(
        isinstance(value, str)
        and len(value) == 64
        and set(value) <= set("0123456789abcdef"),
        "Expected SHA-256 identity.",
    )


@dataclass(frozen=True)
class AdmissionRequest(_TargetRecord):
    """Frozen inputs to one use gate, separate from source/biological verification."""

    target: TargetContext
    intended_use: str
    boundary: str
    components: tuple[ComponentRecord, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.admission_request.v0.1"
    _decoders: ClassVar[dict] = {
        "target": TargetContext.from_dict,
        "components": lambda data: _records(data, ComponentRecord),
    }

    def __post_init__(self):
        require(
            isinstance(self.target, TargetContext), "Full target authority required."
        )
        require(
            isinstance(self.intended_use, str) and self.intended_use in USES,
            "Invalid intended use.",
        )
        require(
            isinstance(self.boundary, str) and self.boundary in BOUNDARIES,
            "Invalid admission boundary.",
        )
        require(
            isinstance(self.components, (tuple, list))
            and all(isinstance(item, ComponentRecord) for item in self.components),
            "Expected component records.",
        )
        components = tuple(
            sorted(self.components, key=lambda item: (item.id, item.version))
        )
        unique = {}
        for item in components:
            key = (item.id, item.version)
            require(
                key not in unique or unique[key] == item,
                "Ambiguous admission component identities.",
            )
            unique[key] = item
        object.__setattr__(self, "components", tuple(unique.values()))
        self._check_utf8()


@dataclass(frozen=True)
class AdmissionAssessment(_TargetRecord):
    """A historical use decision, never a reusable permission token."""

    request_fingerprint: str
    target_fingerprint: str
    intended_use: str
    boundary: str
    decision: str
    diagnostics: tuple[str, ...]
    component_fingerprints: tuple[str, ...]
    evidence: tuple[TargetEvidence, ...]
    schema_version: ClassVar[str] = "biocompiler.admission_assessment.v0.1"
    _fixed_fields: ClassVar[dict] = {
        "policy": ADMISSION_POLICY_VERSION,
        "human_therapeutic_admission": "not_admitted",
        "claim_scope": "use_eligibility_only_no_biological_validation",
        "evidence_status": "declared_not_independently_validated",
    }
    _decoders: ClassVar[dict] = {
        "evidence": lambda data: _records(data, TargetEvidence)
    }

    def __post_init__(self):
        _hash(self.request_fingerprint)
        _hash(self.target_fingerprint)
        require(
            isinstance(self.intended_use, str) and self.intended_use in USES,
            "Invalid intended use.",
        )
        require(
            isinstance(self.boundary, str) and self.boundary in BOUNDARIES,
            "Invalid admission boundary.",
        )
        require(
            isinstance(self.decision, str)
            and self.decision in {"software_only", "not_admitted"},
            "Unsupported admission decision.",
        )
        require(
            self.decision != "software_only" or self.intended_use == "software_test",
            "Software use cannot authorize a human therapeutic build.",
        )
        for key in ("diagnostics", "component_fingerprints"):
            object.__setattr__(self, key, tuple(sorted(names(getattr(self, key), key))))
        require(
            bool(self.diagnostics), "Admission decisions need explicit scope/reasons."
        )
        for value in self.component_fingerprints:
            _hash(value)
        require(
            isinstance(self.evidence, (list, tuple))
            and all(isinstance(item, TargetEvidence) for item in self.evidence),
            "Expected declared evidence inventory.",
        )
        require(
            len({item.id for item in self.evidence}) == len(self.evidence),
            "Duplicate evidence IDs.",
        )
        object.__setattr__(
            self, "evidence", tuple(sorted(self.evidence, key=lambda item: item.id))
        )
        self._check_utf8()

    def is_current(self, request):
        """Identity equality only. Use verify_admission for fresh policy evaluation."""
        require(isinstance(request, AdmissionRequest), "Expected AdmissionRequest.")
        return request.fingerprint == self.request_fingerprint

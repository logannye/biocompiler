"""Independent structural checks for supplied-fragment software RNA designs.

The request, supplied separately from producer output, fixes every source base,
placement and chemistry assertion. This checker imports neither the assembler
nor the emitter. A result is structural software evidence, never biological
reference promotion, empirical validation or human-use admission.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
from typing import ClassVar

from biocompiler.errors import SerializationError
from biocompiler.ir.intent import freeze_json, thaw_json
from biocompiler.ir.payload import PayloadMolecule, PayloadRegion, hash_value
from biocompiler.ir.serialization import JsonArtifact, fields, require
from biocompiler.registry.references import translate_cds
from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION
from biocompiler.semantics.context import PayloadFormat
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.verification.admission import admission_for_target
from biocompiler.verification.evidence import CheckOutcome, FreshnessReport
from biocompiler.verification.payload import PayloadDiagnostic

CHECKER_VERSION = "biocompiler.molecular_design_checker.v0.2"
CLAIM_SCOPE = (
    "Exact supplied-fragment identity, assembly correspondence and complete "
    "mature-linear-RNA structure within a frozen software-only request. No "
    "biological function, experimental-material identity, reference promotion, "
    "mechanism realization or human therapeutic admission is established."
)
UNRESOLVED_OBLIGATIONS = (
    "biological_component_function",
    "source_behavior_realization",
    "human_context_applicability",
    "experimental_material_identity",
    "delivery_and_manufacturing_support",
    "therapeutic_efficacy",
)
_CHECKS = {
    "request": (
        "independent_request_authority",
        "software_use_eligibility",
        "fragment_identity",
        "source_and_destination_layout",
        "complete_rna_profile",
        "coding_correspondence",
        "explicit_chemistry",
    ),
    "construct": (
        "independent_request_authority",
        "software_use_eligibility",
        "fragment_identity",
        "source_and_destination_layout",
        "complete_rna_profile",
        "coding_correspondence",
        "explicit_chemistry",
        "construct_correspondence",
    ),
    "molecule": (
        "independent_request_authority",
        "software_use_eligibility",
        "fragment_identity",
        "source_and_destination_layout",
        "complete_rna_profile",
        "coding_correspondence",
        "explicit_chemistry",
        "construct_correspondence",
        "emitted_fragment_slices",
        "emitted_region_and_source_maps",
        "emitted_molecule_identity",
    ),
}


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


def _schemas():
    from biocompiler.ir.molecular_design import (
        FragmentPlacement,
        MolecularDesignArtifact,
        MolecularDesignConstruct,
        MolecularDesignRequest,
        SequenceFragment,
    )

    return {
        "request": MolecularDesignRequest.schema_version,
        "fragment": SequenceFragment.schema_version,
        "placement": FragmentPlacement.schema_version,
        "construct": MolecularDesignConstruct.schema_version,
        "artifact": MolecularDesignArtifact.schema_version,
        "molecule": PayloadMolecule.schema_version,
    }


def molecular_design_dependencies(
    request, construct=None, candidate=None, *, expected_request_fingerprint
):
    """Bind current independent authority and actual inputs, never saved labels."""
    from biocompiler.ir.molecular_design import (
        PROFILE_VERSION,
        MolecularDesignArtifact,
        MolecularDesignConstruct,
        MolecularDesignRequest,
    )

    require(
        isinstance(request, MolecularDesignRequest), "Expected frozen design request."
    )
    require(
        construct is None or isinstance(construct, MolecularDesignConstruct),
        "Expected molecular design construct.",
    )
    require(
        candidate is None or isinstance(candidate, MolecularDesignArtifact),
        "Expected molecular design artifact.",
    )
    require(candidate is None or construct is not None, "Candidate requires construct.")
    hash_value(expected_request_fingerprint, "Independent request authority")
    return {
        "request": request.fingerprint,
        "expected_request": expected_request_fingerprint,
        "target": request.target.fingerprint,
        "construct": construct.fingerprint if construct is not None else None,
        "candidate": candidate.fingerprint if candidate is not None else None,
        "checker": CHECKER_VERSION,
        "profile": PROFILE_VERSION,
        "admission_policy": ADMISSION_POLICY_VERSION,
        "schemas": _schemas(),
    }


@dataclass(frozen=True)
class MolecularDesignResult(JsonArtifact):
    """Historical structural evidence; use current input checks for acceptance."""

    stage: str
    outcome: CheckOutcome
    dependencies: Mapping
    diagnostics: tuple[PayloadDiagnostic, ...]
    checks: tuple[str, ...]
    claim_scope: str = CLAIM_SCOPE
    evidence_boundary: str = "software_fixture"
    reference_promotion: str = "not_promoted"
    human_therapeutic_admission: str = "not_admitted"
    unresolved_obligations: tuple[str, ...] = UNRESOLVED_OBLIGATIONS
    schema_version: ClassVar[str] = "biocompiler.molecular_design_result.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.stage, str) and self.stage in _CHECKS,
            "Invalid molecular design check stage.",
        )
        require(isinstance(self.outcome, CheckOutcome), "Invalid design check outcome.")
        fields(
            self.dependencies,
            {
                "request",
                "expected_request",
                "target",
                "construct",
                "candidate",
                "checker",
                "admission_policy",
                "schemas",
                "profile",
            },
            "Molecular design dependencies",
        )
        for key in ("request", "expected_request", "target"):
            hash_value(self.dependencies[key], key)
        for key in ("construct", "candidate"):
            value = self.dependencies[key]
            if value is not None:
                hash_value(value, key)
        require(
            (self.dependencies["construct"] is not None) == (self.stage != "request")
            and (self.dependencies["candidate"] is not None)
            == (self.stage == "molecule"),
            "Design receipt inputs differ from its check stage.",
        )
        from biocompiler.ir.molecular_design import PROFILE_VERSION

        require(
            isinstance(self.dependencies["schemas"], Mapping),
            "Invalid schema inventory.",
        )
        require(
            self.dependencies["checker"] == CHECKER_VERSION
            and self.dependencies["profile"] == PROFILE_VERSION
            and self.dependencies["admission_policy"] == ADMISSION_POLICY_VERSION
            and dict(self.dependencies["schemas"]) == _schemas(),
            "Design receipts require current tools and schemas; recheck original inputs.",
        )
        object.__setattr__(self, "dependencies", freeze_json(self.dependencies))
        require(
            isinstance(self.diagnostics, (tuple, list))
            and all(isinstance(item, PayloadDiagnostic) for item in self.diagnostics),
            "Invalid molecular design diagnostics.",
        )
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        require(
            isinstance(self.checks, (tuple, list))
            and tuple(self.checks) == _CHECKS[self.stage],
            "Incomplete molecular design check inventory.",
        )
        object.__setattr__(self, "checks", tuple(self.checks))
        require(
            self.outcome == _outcome(self.diagnostics),
            "Outcome differs from diagnostics.",
        )
        require(
            self.claim_scope == CLAIM_SCOPE
            and self.evidence_boundary == "software_fixture"
            and self.reference_promotion == "not_promoted"
            and self.human_therapeutic_admission == "not_admitted"
            and isinstance(self.unresolved_obligations, (tuple, list))
            and tuple(self.unresolved_obligations) == UNRESOLVED_OBLIGATIONS,
            "Software design evidence cannot promote biological or human-use claims.",
        )
        object.__setattr__(
            self, "unresolved_obligations", tuple(self.unresolved_obligations)
        )

    @property
    def passed(self):
        return self.outcome is CheckOutcome.PASS

    def freshness(
        self, request, construct=None, candidate=None, *, expected_request_fingerprint
    ):
        current = molecular_design_dependencies(
            request,
            construct,
            candidate,
            expected_request_fingerprint=expected_request_fingerprint,
        )
        return FreshnessReport(
            tuple(
                sorted(
                    key
                    for key in current
                    if freeze_json(current[key]) != self.dependencies[key]
                )
            )
        )

    def is_fresh(
        self, request, construct=None, candidate=None, *, expected_request_fingerprint
    ):
        return self.freshness(
            request,
            construct,
            candidate,
            expected_request_fingerprint=expected_request_fingerprint,
        ).fresh

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "stage": self.stage,
            "outcome": self.outcome.value,
            "dependencies": thaw_json(self.dependencies),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "checks": list(self.checks),
            "claim_scope": self.claim_scope,
            "evidence_boundary": self.evidence_boundary,
            "reference_promotion": self.reference_promotion,
            "human_therapeutic_admission": self.human_therapeutic_admission,
            "unresolved_obligations": list(self.unresolved_obligations),
        }

    @classmethod
    def from_dict(cls, data):
        fields(
            data,
            {
                "schema_version",
                "stage",
                "outcome",
                "dependencies",
                "diagnostics",
                "checks",
                "claim_scope",
                "evidence_boundary",
                "reference_promotion",
                "human_therapeutic_admission",
                "unresolved_obligations",
            },
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported design result schema.",
        )
        require(
            isinstance(data["diagnostics"], (tuple, list)),
            "Diagnostics must be an array.",
        )
        require(
            isinstance(data["outcome"], str)
            and data["outcome"] in {x.value for x in CheckOutcome},
            "Invalid result outcome.",
        )
        return cls(
            **{
                key: (
                    CheckOutcome(value)
                    if key == "outcome"
                    else tuple(PayloadDiagnostic.from_dict(x) for x in value)
                    if key == "diagnostics"
                    else value
                )
                for key, value in data.items()
                if key != "schema_version"
            }
        )


def _request_diagnostics(request, expected_request_fingerprint):
    diagnostics = []

    def problem(code, message, status="fail"):
        diagnostics.append(PayloadDiagnostic(status, code, message))

    if request.fingerprint != expected_request_fingerprint:
        problem(
            "request_authority",
            "Request differs from separately supplied frozen authority.",
        )
    admission = admission_for_target(request.target, boundary="verification")
    if admission.decision != "software_only":
        problem(
            "human_use_not_admitted",
            "Human targets have no admitted molecular design implementation.",
            "unsupported",
        )
    if request.target.payload_format != PayloadFormat.RNA:
        problem(
            "unsupported_modality",
            "This design profile supports mature linear RNA only.",
            "unsupported",
        )
    if (
        request.target.capabilities
        or request.target.resources
        or request.target.compartments != ("abstract",)
    ):
        problem(
            "unsupported_target_assumptions",
            "Software fragment assembly provides no host capabilities, compartments or resource model.",
            "unsupported",
        )
    diagnostics.extend(structural_rna_diagnostics(request))
    return diagnostics


def structural_rna_diagnostics(request):
    """Check literal RNA structure without making target or use-admission claims.

    Callers must separately establish request authority, allowed purpose, target
    modality and source correspondence. This shared structural kernel admits no
    compiler profile and does not establish any biological implementation.
    """
    diagnostics = []

    def problem(code, message, status="fail"):
        diagnostics.append(PayloadDiagnostic(status, code, message))

    fragments = {item.id: item for item in request.fragments}
    if set(fragments) != {item.fragment_id for item in request.placements}:
        problem(
            "fragment_inventory",
            "Every supplied fragment must be selected; no selected source may be missing.",
        )
    for fragment in request.fragments:
        if fragment.alphabet != "RNA":
            problem(
                "fragment_alphabet",
                "Fragment sources must be RNA; implicit DNA conversion is unsupported.",
                "unsupported",
            )
        if _sha(fragment.sequence) != fragment.sequence_sha256:
            problem(
                "fragment_hash",
                f"Fragment {fragment.id!r} does not match its pinned nucleotide hash.",
            )
    cursor = 0
    kinds = tuple(item.kind for item in request.placements)
    if kinds not in (
        ("five_prime_utr", "cds", "three_prime_utr"),
        ("five_prime_utr", "cds", "three_prime_utr", "poly_a"),
    ):
        problem(
            "unsupported_region_profile",
            "Require one forward CDS between explicit nonempty UTRs and an optional exact tail.",
            "unsupported",
        )
    for placement in request.placements:
        source = fragments.get(placement.fragment_id)
        if source is None:
            continue
        if placement.fragment_fingerprint != source.fingerprint:
            problem(
                "fragment_lock",
                f"Placement {placement.region_id!r} has a changed fragment identity.",
            )
        if (
            placement.source_range.length == 0
            or placement.source_range.end > len(source.sequence)
            or placement.source_range.length != placement.molecule_range.length
        ):
            problem(
                "source_range",
                f"Placement {placement.region_id!r} must select a nonempty in-bounds source interval of the exact destination length.",
            )
        if (
            placement.molecule_range.start != cursor
            or placement.molecule_range.length == 0
        ):
            problem(
                "destination_partition",
                "Placements must cover every destination base exactly once, in order, from zero.",
            )
        cursor = placement.molecule_range.end
        if placement.orientation != "forward" or placement.reading_frame != 0:
            problem(
                "unsupported_traversal",
                "Only forward, frame-zero fragment placement is supported.",
                "unsupported",
            )
        sequence = source.sequence[
            placement.source_range.start : placement.source_range.end
        ]
        if placement.kind == "cds":
            try:
                protein = translate_cds(sequence, "RNA")
            except SerializationError as exc:
                problem("coding_translation", str(exc))
            else:
                if protein != placement.protein_sequence:
                    problem(
                        "protein_correspondence",
                        "CDS translation must match independently requested protein including the terminal stop.",
                    )
        elif placement.protein_sequence is not None:
            problem(
                "noncoding_protein",
                "A noncoding placement cannot declare a protein product.",
            )
    if request.unknown_features:
        problem(
            "unknown_molecule_features",
            "Required whole-molecule features remain unknown: "
            + ", ".join(request.unknown_features),
            "unknown",
        )
    features = {item.feature: item for item in request.features}
    required = {
        "cap": {"none", "cap0", "cap1"},
        "poly_a_tail": None,
        "nucleotide_modifications": {"none"},
        "end_structure": {"single_strand"},
        "five_prime_end": {"capped", "hydroxyl", "monophosphate", "triphosphate"},
        "three_prime_end": {"hydroxyl"},
    }
    if set(features) != set(required):
        problem(
            "feature_inventory",
            "The frozen request must declare exactly the supported chemistry and end-feature inventory.",
        )
    for key, allowed in required.items():
        item = features.get(key)
        if item is None:
            continue
        if item.status == "unknown":
            problem(
                "unknown_chemistry",
                f"Requested {key} chemistry remains unknown.",
                "unknown",
            )
        elif (
            item.status != "known" or allowed is not None and item.value not in allowed
        ):
            problem(
                "unsupported_chemistry",
                f"Requested {key} chemistry has no implemented profile.",
                "unsupported",
            )
    cap, end = features.get("cap"), features.get("five_prime_end")
    if cap is not None and end is not None and cap.status == end.status == "known":
        if (cap.value in {"cap0", "cap1"}) != (end.value == "capped"):
            problem(
                "cap_end_correspondence",
                "Cap and five-prime terminal chemistry disagree.",
            )
    tail = features.get("poly_a_tail")
    if tail is not None and tail.status == "known":
        region = request.placements[-1] if kinds and kinds[-1] == "poly_a" else None
        expected = f"exact:{region.molecule_range.length}" if region else "absent"
        if tail.value != expected:
            problem(
                "tail_length",
                "Tail chemistry must specify the exact placed tail length or explicit absence.",
            )
        if region is not None and region.fragment_id in fragments:
            sequence = fragments[region.fragment_id].sequence[
                region.source_range.start : region.source_range.end
            ]
            if not sequence or set(sequence) != {"A"}:
                problem(
                    "tail_sequence",
                    "An exact poly(A) tail consists only of independently supplied adenines.",
                )
    return diagnostics


def _construct_diagnostics(request, construct):
    diagnostics = []

    def problem(code, message):
        diagnostics.append(PayloadDiagnostic("fail", code, message))

    if construct.request_fingerprint != request.fingerprint:
        problem(
            "construct_request", "Construct is bound to a different frozen request."
        )
    if construct.molecule_id != request.molecule_id:
        problem(
            "construct_molecule_id",
            "Construct molecule identity differs from requested identity.",
        )
    if construct.placements != request.placements:
        problem(
            "construct_placements",
            "Actual construct placements differ from independent source/layout authority.",
        )
    if (
        construct.features != request.features
        or construct.unknown_features != request.unknown_features
    ):
        problem(
            "construct_features",
            "Construct chemistry or unresolved features differ from authority.",
        )
    return diagnostics


def _molecule_diagnostics(request, construct, candidate):
    diagnostics = []

    def problem(code, message):
        diagnostics.append(PayloadDiagnostic("fail", code, message))

    molecule = candidate.molecule
    if candidate.request_fingerprint != request.fingerprint:
        problem("candidate_request", "Candidate binds a different request.")
    if candidate.construct_fingerprint != construct.fingerprint:
        problem("candidate_construct", "Candidate binds a different actual construct.")
    if candidate.source_maps != request.placements:
        problem(
            "candidate_source_maps",
            "Emitted source maps differ from the frozen selected fragments and ranges.",
        )
    if (
        molecule.id != request.molecule_id
        or molecule.artifact_class != "mature_linear_rna"
        or molecule.alphabet != "RNA"
        or molecule.topology != "linear"
        or molecule.strandedness != "single"
        or molecule.completeness != "complete_molecule"
        or molecule.orientation != "5prime-to-3prime"
    ):
        problem(
            "molecule_profile",
            "Emitted molecule must preserve requested identity and the complete mature linear RNA profile.",
        )
    length = request.placements[-1].molecule_range.end if request.placements else 0
    if len(molecule.sequence) != length or molecule.boundaries != SequenceRange(
        0, length
    ):
        problem(
            "molecule_boundaries",
            "Emitted symbols and boundaries must cover exactly the authorized destination layout.",
        )
    if _sha(molecule.sequence) != molecule.sequence_sha256:
        problem("molecule_hash", "Emitted nucleotide hash differs from actual symbols.")
    if molecule.source_locator != "molecular-design-request:" + request.id:
        problem(
            "molecule_provenance",
            "Emitted whole-molecule provenance differs from request identity.",
        )
    if (
        molecule.features != request.features
        or molecule.unknown_features != request.unknown_features
    ):
        problem(
            "molecule_features",
            "Emitted chemistry and unknown features differ from explicit authority.",
        )
    fragments = {item.id: item for item in request.fragments}
    expected_regions = []
    for placement in request.placements:
        source = fragments.get(placement.fragment_id)
        if source is None:
            continue
        expected_regions.append(
            PayloadRegion(
                placement.region_id,
                placement.kind,
                placement.molecule_range,
                placement.source_range,
                source.source_locator,
                placement.protein_sequence,
                placement.orientation,
                placement.reading_frame,
            )
        )
        expected = source.sequence[
            placement.source_range.start : placement.source_range.end
        ]
        actual = molecule.sequence[
            placement.molecule_range.start : placement.molecule_range.end
        ]
        if actual != expected:
            problem(
                "fragment_nucleotides",
                f"Emitted region {placement.region_id!r} differs from its independently supplied source slice.",
            )
        if placement.kind == "cds":
            try:
                translated = translate_cds(actual, molecule.alphabet)
            except SerializationError as exc:
                problem("emitted_coding_translation", str(exc))
            else:
                if translated != placement.protein_sequence:
                    problem(
                        "emitted_protein_correspondence",
                        "Emitted CDS translation differs from the independently requested protein.",
                    )
    if molecule.regions != tuple(expected_regions):
        problem(
            "molecule_regions",
            "Actual region membership, coordinates, provenance or coding annotations differ from authority.",
        )
    return diagnostics


def _check(request, construct, candidate, expected_request_fingerprint):
    from biocompiler.ir.molecular_design import (
        MolecularDesignArtifact,
        MolecularDesignConstruct,
        MolecularDesignRequest,
    )

    # Reparse actual inputs, including immutable scope fields, before evaluating.
    require(
        isinstance(request, MolecularDesignRequest), "Expected frozen design request."
    )
    request = MolecularDesignRequest.from_dict(request.to_dict())
    if construct is not None:
        require(
            isinstance(construct, MolecularDesignConstruct),
            "Expected design construct.",
        )
        construct = MolecularDesignConstruct.from_dict(construct.to_dict())
    if candidate is not None:
        require(
            isinstance(candidate, MolecularDesignArtifact), "Expected design candidate."
        )
        candidate = MolecularDesignArtifact.from_dict(candidate.to_dict())
    dependencies = molecular_design_dependencies(
        request,
        construct,
        candidate,
        expected_request_fingerprint=expected_request_fingerprint,
    )
    diagnostics = _request_diagnostics(request, expected_request_fingerprint)
    if construct is not None:
        diagnostics.extend(_construct_diagnostics(request, construct))
    if candidate is not None:
        diagnostics.extend(_molecule_diagnostics(request, construct, candidate))
    stage = (
        "molecule"
        if candidate is not None
        else "construct"
        if construct is not None
        else "request"
    )
    return MolecularDesignResult(
        stage, _outcome(diagnostics), dependencies, tuple(diagnostics), _CHECKS[stage]
    )


def check_molecular_design_request(request, *, expected_request_fingerprint):
    return _check(request, None, None, expected_request_fingerprint)


def check_molecular_design_construct(
    request, construct, *, expected_request_fingerprint
):
    return _check(request, construct, None, expected_request_fingerprint)


def check_molecular_design(
    request, construct, candidate, *, expected_request_fingerprint
):
    return _check(request, construct, candidate, expected_request_fingerprint)

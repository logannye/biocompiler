"""Independent acceptance of a single pinned reference-CDS construct layout.

The checker reads the caller's frozen selection, the live registry and reviewed
reference records. It does not import the assembler or a producer's certificate.
No sequence is emitted and no complete-payload or biological claim is made.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from biocompiler.errors import SerializationError
from biocompiler.ir.intent import SourceLocation, freeze_json, thaw_json
from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION
from biocompiler.ir.serialization import (
    JsonArtifact,
    fields,
    fingerprint,
    name,
    names,
    require,
)
from biocompiler.registry.components import ComponentRegistry
from biocompiler.registry.reference_components import (
    REFERENCE_COMPONENT_VERSION,
    adapt_reference_component,
)
from biocompiler.registry.references import ReferenceManifest
from biocompiler.verification.components import (
    CHECKER_VERSION as LINKER_VERSION,
    check_composition,
)
from biocompiler.verification.evidence import CheckOutcome, FreshnessReport

CHECKER_VERSION = "biocompiler.construct_checker.v0.2"
CLAIM_SCOPE = (
    "Exact layout and source correspondence of the selected whole reference CDS, "
    "with component compatibility conditional on locked declarations only. "
    "No sequence emission, complete delivered payload, molecular behavior, "
    "same-cell coexistence, or empirical efficacy is established."
)


def _hash(value, label):
    require(
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value),
        f"Invalid {label} fingerprint.",
    )


def _outcome(diagnostics):
    statuses = {item.status for item in diagnostics}
    return next(
        (
            result
            for result in (
                CheckOutcome.FAIL,
                CheckOutcome.UNSUPPORTED,
                CheckOutcome.UNKNOWN,
            )
            if result.value in statuses
        ),
        CheckOutcome.PASS,
    )


@dataclass(frozen=True)
class ConstructDiagnostic:
    status: str
    code: str
    message: str
    instance_id: str | None = None
    molecule_id: str | None = None
    requirement_ids: tuple[str, ...] = ()
    source: SourceLocation | None = None

    def __post_init__(self):
        require(
            isinstance(self.status, str)
            and self.status in {"fail", "unsupported", "unknown"},
            "Invalid construct diagnostic status.",
        )
        name(self.code, "Diagnostic code")
        name(self.message, "Diagnostic message")
        for key in ("instance_id", "molecule_id"):
            if getattr(self, key) is not None:
                name(getattr(self, key), key)
        object.__setattr__(
            self,
            "requirement_ids",
            names(self.requirement_ids, "Diagnostic requirements"),
        )
        require(
            self.source is None or isinstance(self.source, SourceLocation),
            "Invalid diagnostic source.",
        )

    def to_dict(self):
        return {
            "status": self.status,
            "code": self.code,
            "message": self.message,
            "instance_id": self.instance_id,
            "molecule_id": self.molecule_id,
            "requirement_ids": list(self.requirement_ids),
            "source": self.source.to_dict() if self.source else None,
        }

    @classmethod
    def from_dict(cls, data):
        fields(data, set(cls.__dataclass_fields__), cls.__name__)
        values = dict(data)
        if values["source"] is not None:
            values["source"] = SourceLocation.from_dict(values["source"])
        return cls(**values)


@dataclass(frozen=True)
class ConstructResult(JsonArtifact):
    outcome: CheckOutcome
    dependencies: Mapping
    checked_requirement_ids: tuple[str, ...]
    diagnostics: tuple[ConstructDiagnostic, ...] = ()
    claim_scope: str = CLAIM_SCOPE
    schema_version: ClassVar[str] = "biocompiler.construct_result.v0.2"

    def __post_init__(self):
        require(
            isinstance(self.outcome, CheckOutcome), "Invalid construct check outcome."
        )
        hash_keys = {
            "request",
            "candidate",
            "layout",
            "composition",
            "registry",
            "registry_lock",
            "target",
        }
        fields(
            self.dependencies,
            hash_keys
            | {
                "references",
                "checker",
                "linker",
                "reference_adapter",
                "admission_policy",
            },
            "Construct dependencies",
        )
        for key in hash_keys:
            _hash(self.dependencies[key], key)
        for key, expected in (
            ("checker", CHECKER_VERSION),
            ("admission_policy", ADMISSION_POLICY_VERSION),
            ("linker", LINKER_VERSION),
            ("reference_adapter", REFERENCE_COMPONENT_VERSION),
        ):
            require(self.dependencies[key] == expected, f"Unsupported {key} version.")
        refs = self.dependencies["references"]
        require(
            isinstance(refs, Mapping),
            "Reference dependency identities must be a mapping.",
        )
        for key, value in refs.items():
            name(key, "Reference dependency")
            _hash(value, "reference")
        object.__setattr__(self, "dependencies", freeze_json(self.dependencies))
        object.__setattr__(
            self,
            "checked_requirement_ids",
            names(self.checked_requirement_ids, "Checked requirements"),
        )
        require(
            isinstance(self.diagnostics, (tuple, list))
            and all(isinstance(item, ConstructDiagnostic) for item in self.diagnostics),
            "Invalid construct diagnostics.",
        )
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        require(
            self.outcome is _outcome(self.diagnostics),
            "Construct outcome disagrees with its diagnostics.",
        )
        require(self.claim_scope == CLAIM_SCOPE, "Invalid construct claim scope.")

    @property
    def passed(self):
        return self.outcome is CheckOutcome.PASS

    def freshness(self, request, candidate, registry, manifests):
        current = freeze_json(
            construct_dependencies(request, candidate, registry, manifests)
        )
        return FreshnessReport(
            tuple(
                sorted(key for key in current if current[key] != self.dependencies[key])
            )
        )

    def is_fresh(self, request, candidate, registry, manifests):
        return self.freshness(request, candidate, registry, manifests).fresh

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "outcome": self.outcome.value,
            "dependencies": thaw_json(self.dependencies),
            "checked_requirement_ids": list(self.checked_requirement_ids),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "claim_scope": self.claim_scope,
        }

    @classmethod
    def from_dict(cls, data):
        fields(
            data,
            {
                "schema_version",
                "outcome",
                "dependencies",
                "checked_requirement_ids",
                "diagnostics",
                "claim_scope",
            },
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported construct result schema.",
        )
        require(
            isinstance(data["outcome"], str)
            and data["outcome"] in {item.value for item in CheckOutcome},
            "Invalid construct outcome.",
        )
        require(
            isinstance(data["diagnostics"], (tuple, list)),
            "Construct diagnostics must be an array.",
        )
        return cls(
            CheckOutcome(data["outcome"]),
            data["dependencies"],
            data["checked_requirement_ids"],
            tuple(ConstructDiagnostic.from_dict(item) for item in data["diagnostics"]),
            data["claim_scope"],
        )


def construct_dependencies(request, candidate, registry, manifests):
    """Pin current inputs, including actual offline records and every layout edit."""
    from biocompiler.ir.construct import ConstructCandidate, ConstructRequest

    require(isinstance(request, ConstructRequest), "Expected a ConstructRequest.")
    require(isinstance(candidate, ConstructCandidate), "Expected a ConstructCandidate.")
    require(isinstance(registry, ComponentRegistry), "Expected a component registry.")
    require(
        isinstance(manifests, Mapping),
        "Reference manifests must be keyed by reference-set ID.",
    )
    require(
        all(
            isinstance(key, str) and isinstance(value, ReferenceManifest)
            for key, value in manifests.items()
        ),
        "Invalid reference manifest inventory.",
    )
    return {
        "request": request.fingerprint,
        "candidate": candidate.fingerprint,
        "layout": candidate.layout_fingerprint,
        "composition": request.composition.fingerprint,
        "registry": registry.fingerprint,
        "registry_lock": request.composition.registry_lock.fingerprint,
        "target": request.composition.target.fingerprint,
        "references": {
            key: item.fingerprint for key, item in sorted(manifests.items())
        },
        "checker": CHECKER_VERSION,
        "admission_policy": ADMISSION_POLICY_VERSION,
        "linker": LINKER_VERSION,
        "reference_adapter": REFERENCE_COMPONENT_VERSION,
    }


def check_construct_request(request, registry, manifests):
    """Check frozen assembly authority without using any proposed candidate.

    This is suitable for admitting an externally selected Components root. A
    fresh independent candidate check is still required before Construct use.
    Manifests must be loaded offline with ``load_reference_manifest`` and the
    expected fingerprint before freezing this input snapshot.
    """
    from biocompiler.ir.construct import ConstructRequest

    require(isinstance(request, ConstructRequest), "Expected a ConstructRequest.")
    require(isinstance(registry, ComponentRegistry), "Expected a component registry.")
    require(
        isinstance(manifests, Mapping)
        and all(
            isinstance(key, str) and isinstance(item, ReferenceManifest)
            for key, item in manifests.items()
        ),
        "Expected a reference-set ID to ReferenceManifest mapping.",
    )
    diagnostics = []
    composition = request.composition
    instances = {item.id: item for item in composition.instances}

    def diagnostic(status, code, message, instance_id=None, molecule_id=None):
        instance = instances.get(instance_id)
        diagnostics.append(
            ConstructDiagnostic(
                status,
                code,
                message,
                instance_id,
                molecule_id,
                instance.requirement_ids if instance else composition.requirement_ids,
                instance.source if instance else None,
            )
        )

    linkage = check_composition(composition, registry)
    for item in linkage.diagnostics:
        diagnostic(
            item.status, "composition:" + item.code, item.message, item.instance_id
        )
    if len(instances) != 1:
        diagnostic(
            "unsupported",
            "component_count",
            "The exact-CDS profile supports one selected component instance.",
        )
    if any(item.placement != "encoded_here" for item in composition.instances):
        diagnostic(
            "unsupported",
            "co_payload_assembly",
            "Co-payload placement needs a separately supported assembly and coexistence rule.",
        )
    if any(
        getattr(composition, key)
        for key in (
            "connections",
            "providers",
            "dependency_bindings",
            "resource_pools",
            "resource_bindings",
        )
    ):
        diagnostic(
            "unsupported",
            "composition_relationships",
            "The reference-CDS profile cannot establish molecular layout for connections, providers or shared resource bindings.",
        )
    if request.source_request_fingerprint not in (None, composition.fingerprint):
        diagnostic(
            "fail",
            "source_request",
            "Reference construction lineage must identify its exact authoritative composition.",
        )
    if set().union(
        *(set(item.requirement_ids) for item in composition.instances)
    ) != set(composition.requirement_ids):
        diagnostic(
            "fail",
            "requirement_coverage",
            "Selected instances must preserve exactly the authoritative composition requirements.",
        )
    expected_ids = set(instances)
    if {item.instance_id for item in request.references} != expected_ids:
        diagnostic(
            "fail",
            "reference_inventory",
            "Every selected component requires exactly one independently pinned reference selection.",
        )
    if {item.instance_id for item in request.placements} != expected_ids:
        diagnostic(
            "fail",
            "component_inventory",
            "The layout must contain every selected component exactly once and no additional instance.",
        )
    if len(request.molecules) != 1:
        diagnostic(
            "unsupported",
            "molecule_count",
            "Multi-molecule assembly has no acceptance rule in the exact-CDS profile.",
        )
    if request.junctions:
        diagnostic(
            "unsupported",
            "junctions",
            "Junctions and overlaps are represented but have no accepted reference-CDS assembly rule.",
        )
    if request.regulatory_relations:
        diagnostic(
            "unsupported",
            "regulatory_relationships",
            "The pinned coding reference establishes no regulatory relationships.",
        )
    if request.dependencies:
        diagnostic(
            "unsupported",
            "construct_dependencies",
            "Construct and co-payload dependencies remain explicit and unresolved in this profile.",
        )
    try:
        records = registry.resolve(composition.registry_lock)
    except SerializationError as error:
        diagnostic("fail", "registry_lock", str(error))
        records = {}
    resolved = {}
    for selected in request.references:
        instance_id = selected.instance_id
        selection = selected.selection
        manifest = manifests.get(selection.manifest.id)
        if manifest is None:
            diagnostic(
                "unknown",
                "missing_reference",
                "The trusted reference selection has no supplied offline manifest.",
                instance_id,
            )
            continue
        if manifest.reference_set_id != selection.manifest.id:
            diagnostic(
                "fail",
                "reference_inventory_key",
                "The manifest is not the reference set named by the inventory key.",
                instance_id,
            )
            continue
        try:
            expected = adapt_reference_component(manifest, selection)
            reference = manifest.record(selection.reference.id)
        except SerializationError as error:
            diagnostic("fail", "reference_lock", str(error), instance_id)
            continue
        resolved[instance_id] = (reference, expected, selection)
        actual = records.get(instance_id)
        if actual is None or actual.fingerprint != expected.fingerprint:
            diagnostic(
                "fail",
                "reference_component",
                "The selected locked component differs from the independently adapted exact reference record.",
                instance_id,
            )
        if reference.alphabet != composition.target.payload_format.value:
            diagnostic(
                "fail",
                "reference_target",
                "The reference alphabet differs from the authoritative payload target.",
                instance_id,
            )

    expected_assumptions = tuple(
        dict.fromkeys(
            item for _, record, _ in resolved.values() for item in record.assumptions
        )
    )
    if resolved and request.assumptions != expected_assumptions:
        diagnostic(
            "fail",
            "reference_assumptions",
            "The layout must retain exactly the reference component's conditional and unknown-feature assumptions.",
        )
    molecules = {item.id: item for item in request.molecules}
    for placement in request.placements:
        instance_id = placement.instance_id
        instance = instances.get(instance_id)
        molecule = molecules.get(placement.molecule_id)
        if instance is None:
            diagnostic(
                "fail",
                "unexpected_component",
                "A layout placement names an unselected component instance.",
                instance_id,
                placement.molecule_id,
            )
            continue
        if placement.component != instance.component:
            diagnostic(
                "fail",
                "selected_component",
                "Placement changed the selected component ID, version or content hash.",
                instance_id,
                placement.molecule_id,
            )
        if (
            placement.requirement_ids != instance.requirement_ids
            or placement.source != instance.source
        ):
            diagnostic(
                "fail",
                "source_correspondence",
                "Placement changed or omitted selected source/requirement correspondence.",
                instance_id,
                placement.molecule_id,
            )
        if molecule is None:
            diagnostic(
                "fail",
                "molecule_membership",
                "Placement names a molecule absent from the inventory.",
                instance_id,
                placement.molecule_id,
            )
            continue
        if molecule.component_order != (instance_id,):
            diagnostic(
                "fail",
                "component_order",
                "The reference molecule must contain precisely its selected whole-CDS instance in order.",
                instance_id,
                molecule.id,
            )
        if instance_id not in resolved:
            continue
        reference, _, selection = resolved[instance_id]
        if placement.reference != selection.reference:
            diagnostic(
                "fail",
                "placement_reference",
                "The placement reference differs from the trusted selected record identity.",
                instance_id,
                molecule.id,
            )
        if (
            placement.source_range.start,
            placement.source_range.end,
            placement.molecule_range.start,
            placement.molecule_range.end,
        ) != (0, reference.length, 0, reference.length):
            diagnostic(
                "fail",
                "exact_coverage",
                "The whole selected CDS must cover source and molecule exactly from zero to the exclusive reference length, without gaps, clipping or unexplained bases.",
                instance_id,
                molecule.id,
            )
        if placement.orientation != "forward":
            diagnostic(
                "fail",
                "orientation",
                "The selected reference is already 5prime-to-3prime; reversing it changes the selected CDS.",
                instance_id,
                molecule.id,
            )
        if placement.reading_frame != 0:
            diagnostic(
                "fail",
                "reading_frame",
                "The independently reviewed reference specifies frame zero.",
                instance_id,
                molecule.id,
            )
        if (
            molecule.alphabet,
            molecule.artifact_class,
            molecule.length,
            molecule.completeness,
        ) != (
            reference.alphabet,
            reference.artifact_class,
            reference.length,
            reference.completeness,
        ):
            diagnostic(
                "fail",
                "molecule_reference_metadata",
                "Molecule alphabet, artifact class, length and coding-only completeness must match the reviewed reference.",
                instance_id,
                molecule.id,
            )
        if molecule.unknown_features != reference.unknown_features:
            diagnostic(
                "fail",
                "unknown_features",
                "The construct must retain every unknown delivered-payload feature from the reference unchanged.",
                instance_id,
                molecule.id,
            )
        if molecule.topology != "unspecified" or molecule.compartment != "unspecified":
            diagnostic(
                "fail",
                "unproven_molecule_context",
                "A coding reference does not establish delivered-molecule topology or localization.",
                instance_id,
                molecule.id,
            )
    # Whole-CDS placement already carries the only sourced boundaries available
    # in this reference manifest schema. A diagram or free-text citation cannot
    # establish subcomponent nucleotide coordinates.
    if request.features:
        diagnostic(
            "unsupported",
            "feature_boundaries",
            "This reference manifest has no reviewed subcomponent feature-boundary records; retain the whole pinned CDS placement.",
        )
    return tuple(diagnostics)


def check_construct(request, candidate, registry, manifests):
    """Independently accept exact single-CDS membership, coverage and provenance."""
    import sys as _package_sys
    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')
    if _package_backend is not None:
        _package_value = _package_backend.default('check_construct', request, candidate, registry, manifests)
        if _package_value is not _package_backend.UNSELECTED:
            return _package_value
    from biocompiler.ir.construct import ConstructCandidate, ConstructRequest

    require(isinstance(request, ConstructRequest), "Expected a ConstructRequest.")
    require(isinstance(candidate, ConstructCandidate), "Expected a ConstructCandidate.")
    dependencies = construct_dependencies(request, candidate, registry, manifests)
    diagnostics = list(check_construct_request(request, registry, manifests))
    requirement_ids = request.composition.requirement_ids

    def diagnostic(code, message):
        instance = (
            request.composition.instances[0]
            if len(request.composition.instances) == 1
            else None
        )
        diagnostics.append(
            ConstructDiagnostic(
                "fail",
                code,
                message,
                instance.id if instance else None,
                request.molecules[0].id if len(request.molecules) == 1 else None,
                requirement_ids,
                instance.source if instance else None,
            )
        )

    if candidate.request_fingerprint != request.fingerprint:
        diagnostic(
            "request_identity",
            "Candidate does not identify the authoritative frozen construct request.",
        )
    if candidate.composition_fingerprint != request.composition.fingerprint:
        diagnostic(
            "composition_identity",
            "Candidate does not identify the authoritative selected composition.",
        )
    if candidate.registry_lock != request.composition.registry_lock:
        diagnostic(
            "candidate_registry_lock",
            "Candidate changed the selected registry, component, model or reference locks.",
        )
    for key in (
        "molecules",
        "placements",
        "features",
        "junctions",
        "regulatory_relations",
        "dependencies",
        "assumptions",
        "evidence_policy",
    ):
        expected = request.to_dict()[key]
        actual = candidate.to_dict()[key]
        if fingerprint(expected) != fingerprint(actual):
            diagnostic(
                "changed_" + key,
                f"Candidate changed authoritative {key.replace('_', ' ')}.",
            )
    return ConstructResult(
        _outcome(diagnostics), dependencies, requirement_ids, tuple(diagnostics)
    )

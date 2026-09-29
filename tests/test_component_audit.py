"""Independent adversarial checks across the M4 trust boundaries."""

from dataclasses import replace
from pathlib import Path
import unittest

from cellweave.errors import SerializationError
from cellweave.ir.component_contracts import (
    ComponentRecord,
    DependencyRequirement,
    ParameterProvenance,
    PinnedIdentity,
    ProvidedCapability,
    ResourceReservation,
)
from cellweave.ir.composition import (
    CompositionInstance,
    CompositionRequest,
    Connection,
    Provider,
    ResourceBinding,
    ResourcePool,
)
from cellweave.registry.components import ComponentRegistry
from cellweave.registry.reference_components import (
    ReferenceSelection,
    adapt_reference_component,
)
from cellweave.registry.references import load_reference_manifest
from cellweave.semantics.component_contracts import (
    OperatingDomain,
    PortContract,
    ValueDomain,
)
from cellweave.semantics.context import PayloadFormat, TargetContext
from cellweave.semantics.types import LEVEL
from cellweave.verification.components import (
    CompositionResult,
    LinkDiagnostic,
    check_composition,
)


MODEL = PinnedIdentity("model", "audit-model", "1", "a" * 64)


def record(id="component", **kwargs):
    return ComponentRecord(
        id,
        "1",
        "synthetic_model",
        "audit",
        ("RNA",),
        (),
        OperatingDomain(),
        (MODEL,),
        **kwargs,
    )


def composition(records, *, target=None, **kwargs):
    registry = ComponentRegistry("audit-registry", "1", tuple(records.values()))
    lock = registry.lock(records)
    request = CompositionRequest(
        target
        or TargetContext(
            "audit-target",
            "1",
            PayloadFormat.RNA,
            compartments=("abstract", "extracellular"),
        ),
        lock,
        tuple(
            CompositionInstance(item.node_id, item, OperatingDomain())
            for item in lock.components
        ),
        **kwargs,
    )
    return request, registry


def resource_case(*, amount=2, capacity=3, capability_changes=None, count=1):
    capability = ProvidedCapability("energy", "cell", "cell", "abstract")
    if capability_changes:
        capability = replace(capability, **capability_changes)
    provider = Provider("supply", "external", (capability,), ("RNA",))
    reservation = ResourceReservation("demand", "energy", amount, "1")
    records = {
        f"instance:{index}": record(f"component:{index}", resources=(reservation,))
        for index in range(count)
    }
    return composition(
        records,
        providers=(provider,),
        resource_pools=(ResourcePool("pool", "energy", "1", capacity, "supply"),),
        resource_bindings=tuple(
            ResourceBinding(key, "demand", "pool") for key in records
        ),
    )


class ComponentAuditTests(unittest.TestCase):
    def test_stateless_feedback_cannot_establish_its_own_outputs(self):
        value = ValueDomain.interval(0, 1)
        output = PortContract(
            "out",
            "output",
            "signal",
            LEVEL,
            "1",
            "cell",
            "cell",
            "abstract",
            "atomic_snapshot_stateless.v0.1",
            value,
            value,
        )
        input = replace(output, id="in", direction="input")
        components = {
            key: replace(record(key), ports=(input, output)) for key in ("a", "b")
        }
        request, registry = composition(
            components,
            connections=(
                Connection("a", "out", "b", "in"),
                Connection("b", "out", "a", "in"),
            ),
        )
        self.assertFalse(check_composition(request, registry).passed)

    def test_resource_matching_requires_context_not_just_resource_label(self):
        self.assertTrue(check_composition(*resource_case()).passed)
        for changes in (
            {"compartment": "extracellular"},
            {"scope": "contact"},
            {"role": "other"},
        ):
            with self.subTest(changes=changes):
                self.assertFalse(
                    check_composition(*resource_case(capability_changes=changes)).passed
                )

    def test_finite_demands_with_an_overflowing_sum_fail_without_crashing(self):
        request, registry = resource_case(amount=1e308, capacity=1e308, count=2)
        result = check_composition(request, registry)
        self.assertFalse(result.passed)
        self.assertTrue(
            any(item.code == "resource_overallocation" for item in result.diagnostics)
        )

    def test_required_dependency_cannot_use_an_external_self_justification(self):
        dependency = DependencyRequirement("need", "anchor", "cell", "cell", "abstract")
        capability = ProvidedCapability("anchor", "cell", "cell", "abstract")
        provider = Provider(
            "circular", "external", (capability,), ("RNA",), depends_on=("circular",)
        )
        request, registry = composition(
            {"a": record(dependencies=(dependency,))}, providers=(provider,)
        )
        self.assertFalse(check_composition(request, registry).passed)

    def test_target_identity_and_compartments_are_bound_to_acceptance(self):
        request, registry = resource_case()
        accepted = check_composition(request, registry)
        self.assertTrue(accepted.passed)
        changed_version = replace(
            request, target=replace(request.target, context_version="2")
        )
        self.assertFalse(accepted.is_fresh(changed_version, registry))
        changed_space = replace(
            request, target=replace(request.target, compartments=("extracellular",))
        )
        self.assertFalse(check_composition(changed_space, registry).passed)

    def test_parameter_source_identity_conflicts_cannot_enter_a_registry(self):
        source_a = PinnedIdentity("source", "calibration", "1", "b" * 64)
        source_b = replace(source_a, content_fingerprint="c" * 64)
        a = record(
            "a",
            parameters=(
                ParameterProvenance(
                    "p", ValueDomain.interval(1, 1), source_a, "explicit"
                ),
            ),
        )
        b = record(
            "b",
            parameters=(
                ParameterProvenance(
                    "p", ValueDomain.interval(1, 1), source_b, "explicit"
                ),
            ),
        )
        with self.assertRaises(SerializationError):
            ComponentRegistry("conflict", "1", (a, b))

    def test_parameter_source_is_part_of_explicit_dependency_lock(self):
        source = PinnedIdentity("source", "calibration", "1", "b" * 64)
        a = record(
            parameters=(
                ParameterProvenance(
                    "p", ValueDomain.interval(1, 1), source, "explicit"
                ),
            )
        )
        _, registry = composition({"a": a})
        self.assertIn(source, registry.lock({"a": a}).identities)

    def test_imported_result_cannot_claim_pass_with_failed_resource_usage(self):
        request, registry = resource_case(amount=4)
        failure = check_composition(request, registry)
        self.assertFalse(failure.passed)
        data = failure.to_dict()
        data["outcome"] = "pass"
        data["diagnostics"] = []
        with self.assertRaises(SerializationError):
            CompositionResult.from_dict(data)

    def test_imported_result_requires_valid_nested_identity_records(self):
        request, registry = resource_case()
        data = check_composition(request, registry).to_dict()
        data["dependencies"]["identities"] = [{"schema_version": "unknown"}]
        with self.assertRaises(SerializationError):
            CompositionResult.from_dict(data)

    def test_malformed_nested_records_raise_serialization_errors(self):
        pool = ResourcePool("p", "energy", "1", 1, "supply")
        data = pool.to_dict()
        data["dtype"] = {}
        with self.assertRaises(SerializationError):
            ResourcePool.from_dict(data)
        diagnostic = LinkDiagnostic("fail", "error", "Failure")
        data = diagnostic.to_dict()
        data["status"] = []
        with self.assertRaises(SerializationError):
            LinkDiagnostic.from_dict(data)

    def test_unmapped_requirements_cannot_be_reported_as_checked(self):
        request, registry = composition(
            {"a": record()}, requirement_ids=("orphan-requirement",)
        )
        result = check_composition(request, registry)
        self.assertFalse(result.passed)
        self.assertNotIn("orphan-requirement", result.checked_requirement_ids)

    def test_unpromoted_reference_is_rejected_even_with_new_explicit_pins(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "data/references/fap_car/manifest.json"
        )
        manifest = replace(load_reference_manifest(path), status="candidate")
        reference = next(item for item in manifest.records if item.alphabet == "DNA")
        selection = ReferenceSelection(
            PinnedIdentity(
                "reference",
                manifest.reference_set_id,
                manifest.version,
                manifest.fingerprint,
            ),
            PinnedIdentity(
                "reference",
                reference.reference_id,
                reference.version,
                reference.fingerprint,
            ),
        )
        with self.assertRaises(SerializationError):
            adapt_reference_component(manifest, selection)


if __name__ == "__main__":
    unittest.main()

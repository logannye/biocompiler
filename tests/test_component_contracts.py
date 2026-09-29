"""Contract inclusion is exact, directional and explicitly incomplete when unknown."""

from dataclasses import FrozenInstanceError, replace
import unittest

from cellweave.errors import SerializationError
from cellweave.ir.component_contracts import (
    ComponentRecord,
    DependencyRequirement,
    ParameterProvenance,
    PinnedIdentity,
    ProvidedCapability,
    ResourceReservation,
    SequenceReferenceMetadata,
)
from cellweave.semantics.component_contracts import (
    DomainCheck,
    OperatingDomain,
    PortContract,
    ValueDomain,
    domain_subset,
    operating_domain_subset,
    ports_compatible,
)
from cellweave.semantics.types import BOOLEAN, DURATION, LEVEL, TypeSpec


def pinned(kind="model", id="fixture-model"):
    return PinnedIdentity(kind, id, "1", "a" * 64)


def port(direction="output", **changes):
    domain = ValueDomain.interval(0, 1)
    result = PortContract(
        "signal",
        direction,
        "fixture::signal",
        LEVEL,
        "1",
        "cell",
        "contact",
        "abstract",
        "atomic_snapshot_stateless.v0.1",
        ValueDomain.interval(0, 0),
        domain,
    )
    return replace(result, **changes)


def component(**changes):
    result = ComponentRecord(
        "fixture",
        "1",
        "synthetic_model",
        "constant",
        ("synthetic",),
        (port(),),
        OperatingDomain(),
        (pinned(),),
        assumptions=("Known fixture semantics only.",),
        guarantees=("Values lie in the declared exact domain.",),
        parameters=(
            ParameterProvenance(
                "value",
                ValueDomain.interval(0, 0),
                pinned("source", "fixture-source"),
                "explicit",
            ),
        ),
    )
    return replace(result, **changes)


class DomainTests(unittest.TestCase):
    def test_boolean_inclusion_is_directional(self):
        false = ValueDomain.boolean((False,))
        both = ValueDomain.boolean((True, False))
        self.assertTrue(domain_subset(false, both).passed)
        self.assertEqual(domain_subset(both, false).status, "fail")
        self.assertEqual(both.values, (False, True))

    def test_closed_scalar_inclusion_includes_endpoints(self):
        self.assertTrue(
            domain_subset(ValueDomain.interval(1, 2), ValueDomain.interval(1, 2)).passed
        )
        self.assertTrue(
            domain_subset(ValueDomain.interval(2, 2), ValueDomain.interval(1, 2)).passed
        )
        self.assertEqual(
            domain_subset(
                ValueDomain.interval(0, 2), ValueDomain.interval(1, 2)
            ).status,
            "fail",
        )

    def test_dimensional_similarity_does_not_erase_semantic_type(self):
        other = TypeSpec("scalar", "OtherMeaning")
        self.assertEqual(
            domain_subset(
                ValueDomain.interval(0, 1), ValueDomain.interval(0, 1, other)
            ).status,
            "fail",
        )
        self.assertEqual(
            domain_subset(
                ValueDomain.interval(0, 1, DURATION, "s"),
                ValueDomain.interval(0, 60, DURATION, "min"),
            ).status,
            "fail",
        )

    def test_unknown_is_not_a_top_or_bottom_domain(self):
        unknown = ValueDomain.unknown(reason="not measured")
        known = ValueDomain.interval(0, 1)
        for left, right in ((unknown, known), (known, unknown), (unknown, unknown)):
            self.assertEqual(domain_subset(left, right).status, "unknown")
        self.assertEqual(
            domain_subset(ValueDomain.unknown(BOOLEAN), unknown).status, "fail"
        )

    def test_operating_domain_omission_is_unknown_and_failure_dominates(self):
        required = OperatingDomain({"exposure": ValueDomain.interval(0, 2)})
        supported = OperatingDomain(
            {"exposure": ValueDomain.interval(0, 1), "context": ValueDomain.boolean()}
        )
        self.assertEqual(operating_domain_subset(required, supported).status, "fail")
        self.assertEqual(
            operating_domain_subset(OperatingDomain(), supported).status, "unknown"
        )
        self.assertEqual(
            operating_domain_subset(required, OperatingDomain()).status, "unknown"
        )
        self.assertTrue(
            operating_domain_subset(OperatingDomain(), OperatingDomain()).passed
        )

    def test_domains_reject_unsupported_and_nonfinite_inputs(self):
        for lower, upper in (
            (float("nan"), 1),
            (0, float("inf")),
            (True, 1),
            (2, 1),
            (10**400, 10**401),
        ):
            with (
                self.subTest(lower=lower, upper=upper),
                self.assertRaises(SerializationError),
            ):
                ValueDomain.interval(lower, upper)
        for values in ((), (1,), (False, False), "false"):
            with self.subTest(values=values), self.assertRaises(SerializationError):
                ValueDomain.boolean(values)
        with self.assertRaises(SerializationError):
            ValueDomain("open_interval", LEVEL, "1", lower=0, upper=1)

    def test_ports_need_meaning_scope_compartment_role_and_timing(self):
        producer, consumer = port(), port("input")
        self.assertTrue(ports_compatible(producer, consumer).passed)
        for change in (
            {"meaning": "unrelated"},
            {"scope": "cell"},
            {"role": "other"},
            {"compartment": "elsewhere"},
        ):
            with self.subTest(change=change):
                self.assertEqual(
                    ports_compatible(producer, replace(consumer, **change)).status,
                    "fail",
                )
        self.assertEqual(
            ports_compatible(producer, replace(consumer, timing="unknown")).status,
            "unknown",
        )
        self.assertEqual(ports_compatible(producer, producer).status, "fail")
        with self.assertRaises(SerializationError):
            replace(consumer, timing="arbitrary_delay")

    def test_runtime_and_initialization_are_separate_inclusions(self):
        consumer = port("input", initialization=ValueDomain.interval(0, 1))
        self.assertTrue(ports_compatible(port(), consumer).passed)
        self.assertEqual(
            ports_compatible(
                port(initialization=ValueDomain.interval(1, 1)), port("input")
            ).status,
            "fail",
        )
        self.assertEqual(
            ports_compatible(
                port(), port("input", domain=ValueDomain.interval(0, 0))
            ).status,
            "fail",
        )
        self.assertEqual(
            ports_compatible(
                port(initialization=ValueDomain.unknown()), consumer
            ).status,
            "unknown",
        )
        with self.assertRaises(SerializationError):
            port(initialization=ValueDomain.interval(-1, -1))

    def test_contracts_are_deeply_frozen(self):
        values = [False, True]
        domain = ValueDomain.boolean(values)
        constraints = {"enabled": domain}
        operating = OperatingDomain(constraints)
        values.clear()
        constraints.clear()
        self.assertEqual(domain.values, (False, True))
        self.assertIn("enabled", operating.constraints)
        with self.assertRaises(TypeError):
            operating.constraints["new"] = domain
        with self.assertRaises(FrozenInstanceError):
            domain.unit = "other"


class ComponentRecordTests(unittest.TestCase):
    def test_all_schemas_round_trip_and_reject_unknown_fields_versions(self):
        samples = (
            ValueDomain.boolean(),
            ValueDomain.interval(0, 1),
            ValueDomain.unknown(),
            OperatingDomain({"x": ValueDomain.interval(0, 1)}),
            DomainCheck("unknown", ("missing",)),
            port(),
            pinned(),
            component().parameters[0],
            DependencyRequirement("dep", "energy", "cell", "cell", "abstract"),
            ProvidedCapability("energy", "cell", "cell", "abstract"),
            ResourceReservation("r", "capacity", 3, "1"),
            SequenceReferenceMetadata("coding_dna", 3, ("promoter",)),
            component(),
        )
        for sample in samples:
            cls = type(sample)
            with self.subTest(cls=cls.__name__):
                self.assertEqual(cls.from_json(sample.to_json()), sample)
                self.assertEqual(
                    cls.from_json(sample.to_json()).fingerprint, sample.fingerprint
                )
                invalid = sample.to_dict()
                invalid["schema_version"] = "future.v9000"
                with self.assertRaises(SerializationError):
                    cls.from_dict(invalid)
                invalid = sample.to_dict()
                invalid["extra"] = True
                with self.assertRaises(SerializationError):
                    cls.from_dict(invalid)
                with self.assertRaises(SerializationError):
                    cls.from_dict([])

    def test_nested_malformed_fields_raise_serialization_error(self):
        paths = (
            ("ports", None),
            ("identities", {}),
            ("supported_domain", []),
            ("parameters", [None]),
            ("assumptions", 4),
            ("supported_targets", None),
            ("dependencies", "missing"),
            ("resources", [True]),
        )
        for key, value in paths:
            with self.subTest(key=key):
                data = component().to_dict()
                data[key] = value
                with self.assertRaises(SerializationError):
                    ComponentRecord.from_dict(data)
        for malformed in ({}, [], {"kind": "scalar", "name": "x", "dimensions": []}):
            data = port().to_dict()
            data["dtype"] = malformed
            with self.assertRaises(SerializationError):
                PortContract.from_dict(data)

    def test_component_lists_cannot_be_mutated_through_the_caller(self):
        ports = [port()]
        targets = ["synthetic"]
        original = component(ports=ports, supported_targets=targets)
        identity = original.fingerprint
        ports.clear()
        targets.append("dna")
        self.assertEqual(original.fingerprint, identity)
        self.assertEqual(original.supported_targets, ("synthetic",))
        self.assertNotEqual(
            original.fingerprint, replace(original, version="2").fingerprint
        )
        self.assertNotEqual(
            original.fingerprint,
            replace(original, ports=(port(meaning="other"),)).fingerprint,
        )

    def test_model_and_reference_claims_remain_separate(self):
        reference = ComponentRecord(
            "reference.cds",
            "1",
            "sequence_reference",
            "exact_cds",
            ("dna-cds",),
            (),
            OperatingDomain(),
            (pinned("reference", "frozen-dna"),),
            reference_metadata=SequenceReferenceMetadata(
                "coding_dna", 1491, ("promoter", "topology")
            ),
        )
        self.assertEqual(ComponentRecord.from_json(reference.to_json()), reference)
        for change in (
            {"ports": (port(),)},
            {"identities": (pinned(),)},
            {
                "capabilities": (
                    ProvidedCapability("activity", "cell", "cell", "abstract"),
                )
            },
            {"reference_metadata": None},
        ):
            with self.subTest(change=change), self.assertRaises(SerializationError):
                replace(reference, **change)
        with self.assertRaises(SerializationError):
            component(identities=(pinned("reference"),))

    def test_explicit_typed_resource_unknown_is_preserved(self):
        resource = ResourceReservation("r", "synthetic_capacity", None, "1")
        self.assertIsNone(ResourceReservation.from_json(resource.to_json()).amount)
        self.assertNotEqual(
            resource.fingerprint, replace(resource, amount=0).fingerprint
        )
        for amount in (True, -1, float("inf")):
            with self.subTest(amount=amount), self.assertRaises(SerializationError):
                replace(resource, amount=amount)
        with self.assertRaises(SerializationError):
            replace(resource, dtype=BOOLEAN)
        with self.assertRaises(SerializationError):
            replace(resource, scope="unbound")
        self.assertNotEqual(
            resource.fingerprint,
            replace(resource, compartment="extracellular").fingerprint,
        )

    def test_duplicate_port_and_dependency_ids_are_rejected(self):
        with self.assertRaises(SerializationError):
            component(ports=(port(), port("input")))
        dependency = DependencyRequirement("d", "energy", "cell", "cell", "abstract")
        with self.assertRaises(SerializationError):
            component(dependencies=(dependency, dependency))


if __name__ == "__main__":
    unittest.main()

"""Artifact contracts stay typed, immutable and exact about endpoint meaning."""

from dataclasses import FrozenInstanceError, replace
import json
import unittest

from cellweave.errors import DefinitionError, SerializationError, TypeMismatchError
from cellweave.semantics.context import PayloadFormat, TargetContext
from cellweave.semantics.realization import (
    BehaviorContract,
    InputDomain,
    Observable,
    OperatingDomain,
    ResponseRequirement,
)
from cellweave.semantics.types import (
    BOOLEAN,
    Concentration,
    Duration,
    Interval,
    Level,
    ScalarLiteral,
)


def response(**changes):
    values = dict(
        id="response",
        rule_id="rule",
        specification_id="action",
        observable=Observable("requested_output", Level, "role", compartment="output"),
        active_range=Interval(1, 2),
        inactive_range=Interval(0, 0.2),
        max_activation_delay=Duration(2),
        max_deactivation_delay=Duration(1),
    )
    values.update(changes)
    return ResponseRequirement(**values)


def domain(**changes):
    values = dict(
        id="domain",
        version="1",
        role="role",
        inputs=(
            InputDomain(
                "signal",
                "present",
                Observable("input_presence", BOOLEAN, "role"),
                (False, True),
            ),
        ),
        minimum_horizon=Duration(4),
        required_capabilities=("synthetic_execution",),
    )
    values.update(changes)
    return OperatingDomain(**values)


class RealizationContractTests(unittest.TestCase):
    def test_every_artifact_roundtrips_with_stable_fingerprint(self):
        req = response()
        operating = domain()
        target = TargetContext(
            "host",
            "1",
            PayloadFormat.RNA,
            capabilities=("synthetic_execution",),
            compartments=("abstract", "output"),
            resources={"budget": Level(5)},
        )
        artifacts = (
            req.observable,
            operating.inputs[0],
            operating,
            req,
            BehaviorContract("contract", "a" * 64, (req,)),
            target,
        )
        for artifact in artifacts:
            with self.subTest(artifact=type(artifact).__name__):
                restored = type(artifact).from_json(artifact.to_json())
                self.assertEqual(restored, artifact)
                self.assertEqual(restored.fingerprint, artifact.fingerprint)
                self.assertEqual(json.loads(restored.to_json()), artifact.to_dict())
                with self.assertRaises(FrozenInstanceError):
                    artifact.extra = "change"

    def test_exported_data_does_not_alias_artifact(self):
        artifact = domain()
        exported = artifact.to_dict()
        exported["inputs"][0]["allowed"].clear()
        exported["required_capabilities"].append("unexpected")
        self.assertEqual(artifact.inputs[0].allowed, (False, True))
        self.assertEqual(artifact.required_capabilities, ("synthetic_execution",))
        target = TargetContext(
            "host", "1", PayloadFormat.DNA, resources={"budget": Level(3)}
        )
        with self.assertRaises(TypeError):
            target.resources["budget"] = Level(10)

    def test_endpoint_identity_is_distinct_from_dimension_compatibility(self):
        observable = Observable("output_a", Level, "role", compartment="surface")
        for other in (
            replace(observable, id="output_b"),
            replace(observable, role="different_role"),
            replace(observable, scope="contact"),
            replace(observable, compartment="internal"),
        ):
            self.assertTrue(observable.dtype.compatible(other.dtype))
            self.assertNotEqual(observable, other)
            self.assertNotEqual(observable.fingerprint, other.fingerprint)

    def test_typed_numeric_input_range_uses_canonical_units(self):
        observable = Observable("concentration", Concentration, "role")
        values = Interval(
            Concentration(1, unit="nM"), Concentration(3, unit="nM"), type=Concentration
        )
        requirement = InputDomain("signal", "value", observable, values)
        self.assertTrue(requirement.contains(Concentration(2, unit="nM")))
        self.assertTrue(requirement.contains(2e-6))
        self.assertFalse(requirement.contains(Concentration(4, unit="nM")))
        self.assertFalse(requirement.contains(Level(2)))
        self.assertFalse(requirement.contains(True))
        self.assertFalse(requirement.contains(float("nan")))
        self.assertEqual(InputDomain.from_json(requirement.to_json()), requirement)

    def test_qualitative_inputs_are_exact_booleans(self):
        observable = Observable("presence", BOOLEAN, "role")
        requirement = InputDomain("signal", "present", observable, [True, False])
        self.assertEqual(requirement.allowed, (False, True))
        self.assertTrue(requirement.contains(True))
        self.assertFalse(requirement.contains(1))
        for values in ([], (0, 1), (True, True), (False, "yes")):
            with self.subTest(values=values), self.assertRaises(SerializationError):
                InputDomain("signal", "present", observable, values)
        with self.assertRaises(SerializationError):
            InputDomain("signal", "value", observable, Interval(0, 1))

    def test_domain_rejects_inconsistent_identities_and_invalid_bounds(self):
        base = domain()
        bad_inputs = (
            (),
            (base.inputs[0], base.inputs[0]),
            (
                replace(
                    base.inputs[0],
                    observable=replace(base.inputs[0].observable, role="other"),
                ),
            ),
            (
                base.inputs[0],
                InputDomain(
                    "signal",
                    "high",
                    Observable("other", BOOLEAN, "role", scope="contact"),
                    (True,),
                ),
            ),
        )
        for inputs in bad_inputs:
            with self.subTest(inputs=inputs), self.assertRaises(SerializationError):
                domain(inputs=inputs)
        for value in (True, -1, 1.5):
            with self.subTest(bound=value), self.assertRaises(SerializationError):
                domain(max_contacts=value)
        for value in (Duration(0), Duration(-1), Level(1), 5):
            with self.subTest(horizon=value), self.assertRaises(SerializationError):
                domain(minimum_horizon=value)

    def test_response_ranges_closed_disjoint_and_dimension_checked(self):
        req = response()
        self.assertTrue(req.accepts(1, active=True))
        self.assertTrue(req.accepts(2, active=True))
        self.assertFalse(req.accepts(0, active=True))
        self.assertTrue(req.accepts(0.2, active=False))
        for inactive in (Interval(0, 1), Interval(1.2, 1.4), Interval(2, 3)):
            with self.subTest(inactive=inactive), self.assertRaises(SerializationError):
                response(inactive_range=inactive)
        with self.assertRaises(SerializationError):
            response(active_range=Interval(Duration(1), Duration(2), type=Duration))
        with self.assertRaises(SerializationError):
            req.accepts(1, active=1)

    def test_zero_delay_is_explicit_and_negative_or_unitless_delay_rejected(self):
        req = response(max_activation_delay=Duration(0))
        self.assertEqual(req.max_activation_delay.canonical_value, 0)
        for delay in (Duration(-1), Level(1), 2):
            with self.subTest(delay=delay), self.assertRaises(SerializationError):
                response(max_activation_delay=delay)
        self.assertEqual(
            response(
                max_activation_delay=Duration(1, unit="min")
            ).max_activation_delay.canonical_value,
            60,
        )

    def test_contract_requires_complete_unique_response_identity(self):
        req = response()
        for requirements in (
            (),
            (req, req),
            (req, replace(req, id="another")),
            (
                req,
                response(
                    id="other",
                    rule_id="other_rule",
                    observable=replace(req.observable, role="other"),
                ),
            ),
        ):
            with (
                self.subTest(requirements=requirements),
                self.assertRaises(SerializationError),
            ):
                BehaviorContract("contract", "a" * 64, requirements)
        for identity in ("", "a" * 63, "z" * 64, 123):
            with self.subTest(identity=identity), self.assertRaises(SerializationError):
                BehaviorContract("contract", identity, (req,))

    def test_strict_schema_keys_json_numbers_and_typed_values(self):
        artifacts = (
            domain(),
            response(),
            BehaviorContract("contract", "a" * 64, (response(),)),
            TargetContext("host", "1", PayloadFormat.DNA),
        )
        for artifact in artifacts:
            for edit in (
                lambda d: d.update(schema_version="future"),
                lambda d: d.update(extra=True),
            ):
                data = artifact.to_dict()
                edit(data)
                with (
                    self.subTest(artifact=type(artifact).__name__),
                    self.assertRaises(SerializationError),
                ):
                    type(artifact).from_dict(data)
            with self.assertRaises(SerializationError):
                type(artifact).from_json('{"id":"a","id":"b"}')
            with self.assertRaises(SerializationError):
                type(artifact).from_json('{"value":NaN}')
        data = response().to_dict()
        data["max_activation_delay"]["canonical_value"] = 10
        with self.assertRaises(SerializationError):
            ResponseRequirement.from_dict(data)
        data = domain().to_dict()
        data["inputs"][0]["allowed"] = [0, 1]
        with self.assertRaises(SerializationError):
            OperatingDomain.from_dict(data)

    def test_malformed_nested_shapes_report_serialization_errors(self):
        mutations = (
            lambda data: data["observable"].update(dtype=[]),
            lambda data: data["observable"]["dtype"].update(dimensions={"time": True}),
            lambda data: data["observable"]["dtype"].update(arguments={}),
            lambda data: data["active_range"].update(lower=[]),
            lambda data: data["max_activation_delay"].update(canonical_value=True),
            lambda data: data.update(max_deactivation_delay=[]),
        )
        for index, mutate in enumerate(mutations):
            data = response().to_dict()
            mutate(data)
            with self.subTest(mutation=index), self.assertRaises(SerializationError):
                ResponseRequirement.from_dict(data)

    def test_direct_scalar_construction_cannot_smuggle_invalid_units(self):
        malformed = ScalarLiteral(1, Duration._spec, "s", 20)
        with self.assertRaises(SerializationError):
            response(max_activation_delay=malformed)
        with self.assertRaises(SerializationError):
            TargetContext(
                "host", "1", PayloadFormat.DNA, resources={"clock": malformed}
            )

    def test_target_backwards_compatible_constructor_and_explicit_assumptions(self):
        target = TargetContext("host", "1", PayloadFormat.DNA)
        self.assertEqual(target.capabilities, ())
        self.assertEqual(target.compartments, ("abstract",))
        with self.assertRaises(TypeMismatchError):
            TargetContext("host", "1", "DNA")
        with self.assertRaises(DefinitionError):
            TargetContext("", "1", PayloadFormat.DNA)
        for arguments in (
            {"compartments": ()},
            {"capabilities": ("x", "x")},
            {"resources": {"budget": Level(-1)}},
            {"resources": {"budget": 2}},
        ):
            with (
                self.subTest(arguments=arguments),
                self.assertRaises(SerializationError),
            ):
                TargetContext("host", "1", PayloadFormat.RNA, **arguments)


if __name__ == "__main__":
    unittest.main()

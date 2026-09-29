"""Independent hard constraints precede deterministic offline preference ranking."""

import copy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from cellweave.errors import SerializationError
from cellweave.ir.component_contracts import (
    ComponentRecord,
    PinnedIdentity,
    ParameterProvenance,
)
from cellweave.semantics.context import TargetContext, PayloadFormat
from cellweave.registry.components import (
    ComponentRegistry,
    SelectionRequest,
)
from cellweave.semantics.component_contracts import OperatingDomain, ValueDomain
from test_references import json_paths


def component(identifier, lower=0, upper=10, **kwargs):
    values = dict(
        id=identifier,
        version="1",
        classification="synthetic_model",
        implementation_role="sensor",
        supported_targets=("RNA",),
        ports=(),
        supported_domain=OperatingDomain({"level": ValueDomain.interval(lower, upper)}),
        identities=(PinnedIdentity("model", "model", "1", "a" * 64),),
        guarantees=("declared_sensor_contract",),
    )
    values.update(kwargs)
    return ComponentRecord(**values)


class ComponentRegistryTests(unittest.TestCase):
    def setUp(self):
        self.good = component("good")
        self.narrow = component("preferred_narrow", 0, 2)
        self.unknown = component(
            "unknown",
            supported_domain=OperatingDomain({"level": ValueDomain.unknown()}),
        )
        self.registry = ComponentRegistry(
            "offline", "1", (self.unknown, self.narrow, self.good)
        )
        self.request = SelectionRequest(
            "sensor",
            TargetContext("registry_test", "1", PayloadFormat.RNA),
            OperatingDomain({"level": ValueDomain.interval(1, 3)}),
            preferred_component_ids=("preferred_narrow", "unknown", "good"),
        )

    def test_hard_failures_and_unknowns_cannot_win_preference_ranking(self):
        with patch(
            "socket.create_connection", side_effect=AssertionError("network prohibited")
        ):
            result = self.registry.select(self.request)
        self.assertEqual(result.selected.component_id, "good")
        self.assertEqual(result.outcome, "pass")
        alternatives = {item.component_id: item for item in result.alternatives}
        self.assertEqual(alternatives["preferred_narrow"].status, "rejected")
        self.assertIsNone(alternatives["preferred_narrow"].preference_rank)
        self.assertEqual(alternatives["unknown"].status, "unknown")
        self.assertIsNone(alternatives["unknown"].preference_rank)
        self.assertIn("all_hard_constraints_satisfied", alternatives["good"].reasons)
        self.assertTrue(self.registry.verify_selection(self.request, result))

    def test_constraints_are_independent_from_selected_output(self):
        result = self.registry.select(self.request)
        modified_request = replace(
            self.request,
            target=replace(self.request.target, payload_format=PayloadFormat.DNA),
        )
        self.assertFalse(self.registry.verify_selection(modified_request, result))
        self.assertEqual(self.registry.select(modified_request).outcome, "fail")
        forged = replace(result, request_fingerprint=modified_request.fingerprint)
        self.assertFalse(self.registry.verify_selection(modified_request, forged))

    def test_every_supported_hard_constraint_is_checked_before_ranking(self):
        mutations = (
            {"implementation_role": "actuator"},
            {"classification": "sequence_reference"},
            {"required_guarantees": ("unestablished_claim",)},
            {"component_id": "missing"},
            {"component_id": "good", "component_version": "2"},
            {"required_identities": (PinnedIdentity("model", "model", "1", "b" * 64),)},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                result = self.registry.select(replace(self.request, **mutation))
                self.assertIsNone(result.selected)
                self.assertEqual(result.outcome, "fail")
                self.assertTrue(
                    all(item.status == "rejected" for item in result.alternatives)
                )

    def test_unknown_without_eligible_candidates_stays_unknown(self):
        registry = ComponentRegistry("unknown", "1", (self.unknown,))
        self.assertEqual(registry.select(self.request).outcome, "unknown")

    def test_ties_and_input_order_are_deterministic(self):
        first, second = component("a"), component("b")
        registry = ComponentRegistry("tie", "1", (second, first))
        reversed_registry = replace(registry, components=(first, second))
        self.assertEqual(registry.fingerprint, reversed_registry.fingerprint)
        self.assertEqual(
            registry.select(self.request), reversed_registry.select(self.request)
        )
        self.assertEqual(registry.select(self.request).selected.component_id, "a")
        preferred = replace(self.request, preferred_component_ids=("b",))
        self.assertEqual(registry.select(preferred).selected.component_id, "b")

    def test_duplicate_component_or_dependency_identity_is_rejected(self):
        with self.assertRaisesRegex(SerializationError, "ambiguous"):
            ComponentRegistry(
                "ambiguous",
                "1",
                (self.good, replace(self.good, assumptions=("changed",))),
            )
        conflicting = component(
            "conflicting", identities=(PinnedIdentity("model", "model", "1", "b" * 64),)
        )
        with self.assertRaisesRegex(SerializationError, "Ambiguous dependency"):
            ComponentRegistry("ambiguous", "1", (self.good, conflicting))

    def test_locks_reject_registry_component_model_reference_and_evidence_changes(self):
        lock = self.registry.lock({"instance": self.good})
        self.assertEqual(self.registry.resolve(lock), {"instance": self.good})
        for changed in (
            replace(lock, registry_version="changed"),
            replace(lock, registry_fingerprint="0" * 64),
            replace(lock, components=(replace(lock.components[0], version="changed"),)),
            replace(lock, identities=()),
            replace(
                lock,
                identities=(replace(lock.identities[0], content_fingerprint="0" * 64),),
            ),
        ):
            with (
                self.subTest(changed=changed.fingerprint),
                self.assertRaises(SerializationError),
            ):
                self.registry.resolve(changed)
        changed_registry = replace(
            self.registry,
            components=(
                replace(self.good, guarantees=("changed",)),
                self.narrow,
                self.unknown,
            ),
        )
        with self.assertRaises(SerializationError):
            changed_registry.resolve(lock)

    def test_parameter_sources_are_locked_and_conflicts_fail_closed(self):
        source = PinnedIdentity("source", "parameter_measurement", "1", "c" * 64)
        parameter = ParameterProvenance(
            "threshold", ValueDomain.interval(1, 1), source, "authored"
        )
        record = replace(self.good, parameters=(parameter,))
        registry = ComponentRegistry("parameters", "1", (record,))
        lock = registry.lock({"instance": record})
        self.assertIn(source, lock.identities)
        requested = replace(self.request, required_identities=(source,))
        self.assertEqual(registry.select(requested).outcome, "pass")
        conflicting_parameter = replace(
            parameter, source=replace(source, content_fingerprint="d" * 64)
        )
        with self.assertRaisesRegex(SerializationError, "Ambiguous dependency"):
            ComponentRegistry(
                "conflict",
                "1",
                (record, component("other", parameters=(conflicting_parameter,))),
            )

    def test_selection_pins_the_full_target_context(self):
        selected = self.registry.select(self.request)
        changed = replace(
            self.request, target=replace(self.request.target, context_version="2")
        )
        self.assertNotEqual(changed.fingerprint, self.request.fingerprint)
        self.assertFalse(self.registry.verify_selection(changed, selected))

    def test_roundtrips_and_immutable_inputs(self):
        records = [self.good]
        registry = ComponentRegistry("immutable", "1", records)
        records.clear()
        self.assertEqual(len(registry.components), 1)
        for artifact in (
            self.registry,
            self.request,
            self.registry.select(self.request),
            self.registry.lock({"instance": self.good}),
        ):
            restored = type(artifact).from_json(artifact.to_json())
            self.assertEqual(restored.fingerprint, artifact.fingerprint)
            with self.assertRaises(FrozenInstanceError):
                artifact.schema_version = "changed"

    def test_malformed_nested_imports_raise_serialization_errors(self):
        artifacts = (
            self.registry,
            self.request,
            self.registry.select(self.request),
            self.registry.lock({"instance": self.good}),
        )
        for artifact in artifacts:
            original = artifact.to_dict()
            for path in json_paths(original):
                for replacement in (None, [], {}, False, 0, "unexpected"):
                    data = copy.deepcopy(original)
                    if path:
                        parent = data
                        for part in path[:-1]:
                            parent = parent[part]
                        parent[path[-1]] = replacement
                    else:
                        data = replacement
                    with self.subTest(
                        artifact=type(artifact).__name__,
                        path=path,
                        replacement=replacement,
                    ):
                        try:
                            type(artifact).from_dict(data)
                        except SerializationError:
                            pass
                        except Exception as error:
                            self.fail(f"Unexpected {type(error).__name__}: {error}")


if __name__ == "__main__":
    unittest.main()

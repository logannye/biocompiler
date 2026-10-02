"""Native public producer views preserve complete originals without Python authority."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler.core_client import CoreClient, CoreProtocolError
from biocompiler.errors import UnsupportedBehaviorError
from biocompiler.synthetic_producer_backend import (
    NativeSyntheticCandidate, NativeSyntheticSelectionResult, NativeSyntheticComposition,
    NativeProducerDocument, SyntheticProducerCoreError, serializing_legacy_input,
)
from biocompiler.synthesis.synthetic import generate_synthetic, SyntheticCandidate, SyntheticGeneratorConfig
from biocompiler.synthesis.selection import select_synthetic
from biocompiler.synthesis.components import adapt_synthetic_components
from test_core_synthetic_producer import (
    OPERATIONS, capabilities, encoded, envelope, fixture, receipt,
)


class PublicSyntheticProducerTests(unittest.TestCase):
    def setUp(self):
        self.core = CoreClient(Path(sys.executable))
        self.wires = []

    def exchange(self, change=None, negotiate=None):
        def invoke(_executable, raw, _timeout, _cancelled):
            request = json.loads(raw)
            self.wires.append(request)
            operation = request["operation"]
            if operation == "capabilities":
                result = capabilities()
                if negotiate:
                    negotiate()
            else:
                _, original = fixture(operation)
                result = receipt(operation, request["payload"], original)
                if change:
                    change(result)
            return encoded(envelope(request, result)), 0
        return patch("biocompiler.core_client._exchange", side_effect=invoke)

    def call(self, operation, *, transform=lambda x: x):
        payload, _ = fixture(operation)
        request = transform(payload["request"])
        if operation == OPERATIONS[0]:
            return generate_synthetic(request, config=transform(payload["config"]) if payload["config"] else None, core=self.core)
        if operation == OPERATIONS[1]:
            return select_synthetic(request, transform(payload["history"]), until=payload["until"],
                                    config=transform(payload["config"]), core=self.core)
        return adapt_synthetic_components(request, transform(payload["candidate"]), transform(payload["history"]),
                                          until=payload["until"], core=self.core)

    def test_all_public_routes_preserve_complete_mapping_and_raw_byte_results(self):
        for operation, cls in zip(OPERATIONS, (NativeSyntheticCandidate, NativeSyntheticSelectionResult, NativeSyntheticComposition)):
            _, original = fixture(operation)
            for transform in (lambda x: x, encoded):
                with self.subTest(operation=operation, transform=transform), self.exchange():
                    result = self.call(operation, transform=transform)
                self.assertIs(type(result), cls)
                self.assertEqual(result.to_dict(), original)
                self.assertEqual(result.canonical_json, encoded(original))
                self.assertEqual(result.fingerprint, hashlib.sha256(encoded(original)).hexdigest())
                self.assertEqual(result.to_json(indent=None), json.dumps(original, sort_keys=True, ensure_ascii=False))
                result.to_dict().clear()
                self.assertEqual(result.to_dict(), original)
                with self.assertRaises((FrozenInstanceError, TypeError)):
                    result._canonical_json = b"{}"

    def test_nested_candidate_accessors_and_historical_roundtrip_have_no_authority(self):
        with self.exchange():
            result = self.call(OPERATIONS[0])
        _, original = fixture(OPERATIONS[0])
        self.assertEqual(result.generator_config.to_dict(), original["generator_config"])
        self.assertEqual(result.mechanism.outputs, tuple(original["mechanism"]["outputs"]))
        for node in result.mechanism.nodes:
            self.assertIs(result.mechanism.get(node.id), node)
            self.assertIn(node, result.mechanism.find(node.kind))
            self.assertEqual(node.role, node.output.role)
            self.assertEqual(node.data_type["kind"], node.output.dtype.kind)
            self.assertIsInstance(node.output.dtype.dimensions, tuple)
        for node in result.mechanism.find("constant"):
            if isinstance(node.attributes["value"], dict) or hasattr(node.attributes["value"], "keys"):
                self.assertIn("canonical_value", node.attributes["value"])
        restored = type(result).from_json(result.to_json())
        self.assertEqual(restored, result)
        self.assertIsNone(restored.native_result)
        self.assertEqual(restored.generator_config.fingerprint, result.generator_config.fingerprint)
        with self.assertRaises(TypeError):
            result.source_map["changed"] = ()
        with self.assertRaises(KeyError):
            result.mechanism.get("not-present")
        with self.assertRaisesRegex(UnsupportedBehaviorError, "topological"):
            result.mechanism.topological_nodes()

    def test_selection_uses_native_summary_without_recomputing_rank_status_or_counts(self):
        with self.exchange(), patch("biocompiler.synthesis.selection.gate_count", side_effect=AssertionError("Python ranking")), \
                patch("biocompiler.synthesis.selection.policy_for_request", side_effect=AssertionError("Python policy")), \
                patch("biocompiler.synthesis.selection._generate_synthetic", side_effect=AssertionError("Python generation")):
            result = self.call(OPERATIONS[1])
        _, original = fixture(OPERATIONS[1])
        self.assertEqual(result.selected_strategy, original["selected_strategy"])
        self.assertEqual(result.outcome, original["outcome"])
        self.assertEqual(result.checked_candidates, original["checked_candidates"])
        self.assertEqual(result.rejected_candidates, original["rejected_candidates"])
        for alternative, raw in zip(result.alternatives, original["alternatives"]):
            self.assertEqual(alternative.gate_count, raw["gate_count"])
            self.assertEqual(alternative.status, raw["status"])
            self.assertEqual(alternative.constraint_violations, tuple(raw["constraint_violations"]))
            if alternative.check is not None:
                self.assertEqual(alternative.check.outcome.value, raw["check"]["outcome"])
                self.assertEqual(alternative.check.dependencies.values["settings"]["realization_request"], result.request_fingerprint)
        chosen = next(item for item in result.alternatives if item.strategy == result.selected_strategy)
        self.assertIs(result.candidate, chosen.candidate)

    def test_adaptation_exposes_full_nested_records_and_only_attached_lock_inspection(self):
        with self.exchange():
            result = self.call(OPERATIONS[2])
        _, original = fixture(OPERATIONS[2])
        self.assertTrue(result.acceptance.passed)
        self.assertEqual(result.acceptance.outcome.value, "pass")
        self.assertEqual(result.acceptance.fingerprint, hashlib.sha256(json.dumps(original["acceptance"],
            sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest())
        records = result.registry.resolve(result.composition.registry_lock)
        self.assertEqual(set(records), {item.node_id for item in result.composition.registry_lock.components})
        for edge in result.composition.connections:
            producer = records[edge.producer_instance].port(edge.producer_port)
            consumer = records[edge.consumer_instance].port(edge.consumer_port)
            for name in ("meaning", "dtype", "unit", "scope", "role", "compartment", "domain", "initialization"):
                self.assertEqual(getattr(producer, name), getattr(consumer, name))
        records.clear()
        self.assertTrue(result.registry.resolve(result.composition.registry_lock))
        bad_lock = result.composition.registry_lock.to_dict()
        bad_lock["registry_fingerprint"] = "0" * 64
        with self.assertRaisesRegex(UnsupportedBehaviorError, "exact attached"):
            result.registry.resolve(bad_lock)
        with self.assertRaisesRegex(UnsupportedBehaviorError, "freshness"):
            result.acceptance.is_fresh(result.acceptance.dependencies)
        with self.assertRaisesRegex(UnsupportedBehaviorError, "coverage"):
            _ = result.acceptance.exercised_requirement_ids

    def test_authored_inputs_serialize_only_in_marked_input_phase(self):
        from biocompiler.compiler.request import RealizationRequest
        from biocompiler.semantics.evaluator import InputFrame, SignalSample
        payload, _ = fixture(OPERATIONS[2])
        # Construction is authoring before selection of the native route.
        request = RealizationRequest.from_dict(payload["request"])
        candidate = SyntheticCandidate.from_dict(payload["candidate"])
        samples = lambda values: {key: SignalSample(**value) for key, value in values.items()}
        frames = [InputFrame(item["time"], samples(item["signals"]),
            {key: samples(value) for key, value in item["contacts"].items()}) for item in payload["history"]]
        original = RealizationRequest.to_dict
        phases = []
        def checked(value):
            phases.append(serializing_legacy_input())
            return original(value)
        with self.exchange(negotiate=lambda: self.assertFalse(serializing_legacy_input())), \
                patch.object(RealizationRequest, "to_dict", checked), \
                patch.object(SyntheticCandidate, "from_dict", side_effect=AssertionError("output semantic construction")), \
                patch("biocompiler.synthesis.components.check_synthetic_candidate", side_effect=AssertionError("Python acceptance")):
            result = adapt_synthetic_components(request, candidate, iter(frames), until=payload["until"], core=self.core)
        self.assertEqual(phases, [True])
        self.assertFalse(serializing_legacy_input())
        self.assertEqual(self.wires[-1]["payload"]["candidate"], payload["candidate"])
        self.assertEqual(result.to_dict(), fixture(OPERATIONS[2])[1])

    def test_native_view_input_freezes_before_negotiation(self):
        payload, _ = fixture(OPERATIONS[2])
        candidate = NativeSyntheticCandidate.from_dict(payload["candidate"])
        request = deepcopy(payload["request"])
        with self.exchange(negotiate=request.clear):
            result = adapt_synthetic_components(request, candidate, payload["history"], until=payload["until"], core=self.core)
        self.assertEqual(result.native_result.receipt["authority_identities"]["candidate_fingerprint"], candidate.fingerprint)
        self.assertEqual(self.wires[-1]["payload"]["request"], payload["request"])

    def test_full_unsupported_source_and_transport_causes_are_preserved(self):
        detail = {"message": "Original unsupported", "node_id": "node.α", "source":
                  {"file": "source.py", "line": 4, "function": "program"}, "formatted": "Original unsupported [node.α] at source.py:4"}
        def unsupported(result):
            result.update(outcome="unsupported", record=None, record_fingerprint=None, generation_error=detail)
        with self.exchange(unsupported), self.assertRaises(UnsupportedBehaviorError) as error:
            self.call(OPERATIONS[0])
        self.assertEqual(str(error.exception), detail["formatted"])
        self.assertEqual(error.exception.node_id, detail["node_id"])
        self.assertEqual(error.exception.source.to_dict(), detail["source"])
        with patch("biocompiler.core_client._exchange") as exchange, self.assertRaises(SyntheticProducerCoreError) as error:
            generate_synthetic({}, core=CoreClient(Path(sys.executable), role="verify"))
        exchange.assert_not_called()
        self.assertIsInstance(error.exception.core_error, CoreProtocolError)

    def test_native_output_view_construction_executes_no_legacy_semantic_code(self):
        permitted = {"biocompiler.core_client", "biocompiler.core_synthetic_producer", "biocompiler.synthetic_producer_backend"}
        routes = {"generate_synthetic", "select_synthetic", "adapt_synthetic_components"}
        def guard(frame, event, _arg):
            if event == "call":
                module = frame.f_globals.get("__name__", "")
                if module.startswith("biocompiler") and module not in permitted and frame.f_code.co_name not in routes:
                    raise AssertionError("Unexpected Python authority: " + module + "." + frame.f_code.co_name)
        for operation in OPERATIONS:
            previous = sys.getprofile()
            with self.exchange():
                try:
                    sys.setprofile(guard)
                    result = self.call(operation)
                finally:
                    sys.setprofile(previous)
            self.assertIsNotNone(result.native_result)


if __name__ == "__main__":
    unittest.main()

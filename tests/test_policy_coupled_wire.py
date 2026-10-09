"""Pure lossless-transport controls; no native invocation or acceptance claims."""
from copy import deepcopy
import hashlib
import random
import unittest
from unittest.mock import patch

from biocompiler import _policy_coupled_wire as wire
from biocompiler.core_client import CoreProtocolError, encode_json


class CoupledWireTests(unittest.TestCase):
    def setUp(self):
        self.block = patch("subprocess.Popen", side_effect=AssertionError("Native execution forbidden"))
        self.block.start()
        self.addCleanup(self.block.stop)

    def test_independent_literal_postorder_and_complete_identity(self):
        value = {"b": [1, 1], "a": [1, 1]}
        canonical = b'{"a":[1,1],"b":[1,1]}'
        expected = {"schema_version": wire.SCHEMA, "expanded_sha256": hashlib.sha256(canonical).hexdigest(),
                    "root": 2, "nodes": [{"kind": "integer", "value": 1},
                    {"kind": "array", "items": [0, 0]},
                    {"kind": "object", "fields": [["a", 1], ["b", 1]]}]}
        self.assertEqual(wire.pack(value), expected)
        self.assertEqual(wire.canonical_bytes(wire.unpack(expected)), canonical)
        detached = wire.unpack(expected)
        detached["a"].append(2)
        self.assertEqual(detached["b"], [1, 1])
        self.assertEqual(value, {"b": [1, 1], "a": [1, 1]})

    def test_all_kinds_and_authored_reference_shaped_objects_are_plain_data(self):
        value = {"$ref": {"schema_version": wire.SCHEMA, "root": False, "nodes": None},
                 "values": [None, False, True, 0, 1, 1.0, -0.0, "\nβ😀", [], {}]}
        packed = wire.pack(value)
        restored = wire.unpack(packed)
        self.assertEqual(encode_json(restored), encode_json(value))
        self.assertIn({"kind": "integer", "value": 1}, packed["nodes"])
        self.assertIn({"kind": "float", "value": 1.0}, packed["nodes"])
        self.assertEqual(wire.canonical_bytes(restored), encode_json(value))

    def test_small_deterministic_structural_corpus_roundtrips(self):
        rng = random.Random(741)
        def value(depth):
            choices = [None, True, False, 0, 3, -4, 0.0, -0.0, "x", "β"]
            if depth:
                choices += [[value(depth - 1) for _ in range(rng.randrange(4))],
                            {key: value(depth - 1) for key in ("z", "a") if rng.randrange(2)}]
            return rng.choice(choices)
        for _ in range(80):
            original = value(3)
            packet = wire.pack(original)
            self.assertEqual(encode_json(wire.unpack(packet)), encode_json(original))
            self.assertEqual(wire.pack(wire.snapshot(original)), packet)

    def test_missing_unknown_mutated_and_wrong_scalar_fields_fail_closed(self):
        original = wire.pack({"x": [1, 2]})
        changes = [lambda row: row.pop("root"), lambda row: row.update(extra=True),
                   lambda row: row.update(schema_version="unrecognized"),
                   lambda row: row.update(expanded_sha256="0" * 64),
                   lambda row: row.update(root=True),
                   lambda row: row["nodes"][0].update(value=True),
                   lambda row: row["nodes"][0].update(kind="float"),
                   lambda row: row["nodes"][0].update(extra=1),
                   lambda row: row["nodes"][2].update(items=[True, 1]),
                   lambda row: row["nodes"][2].update(items=[2, 1]),
                   lambda row: row["nodes"][2].update(items=[-1, 1]),
                   lambda row: row["nodes"][-1].update(fields=[["x", 2], ["x", 2]])]
        for change in changes:
            mutated = deepcopy(original)
            change(mutated)
            with self.subTest(change=change), self.assertRaises(CoreProtocolError):
                wire.unpack(mutated)

    def test_duplicate_unreachable_unsorted_and_noncanonical_postorder_reject(self):
        original = wire.pack({"a": 1, "b": 2})
        mutations = []
        swapped = deepcopy(original)
        swapped["nodes"][0], swapped["nodes"][1] = swapped["nodes"][1], swapped["nodes"][0]
        swapped["nodes"][-1]["fields"] = [["a", 1], ["b", 0]]
        mutations.append(swapped)
        unsorted = deepcopy(original)
        unsorted["nodes"][-1]["fields"].reverse()
        mutations.append(unsorted)
        unreachable = deepcopy(original)
        unreachable["nodes"].insert(0, {"kind": "null"})
        unreachable["nodes"][-1]["fields"] = [["a", 1], ["b", 2]]
        unreachable["root"] = 3
        mutations.append(unreachable)
        duplicate = deepcopy(unreachable)
        duplicate["nodes"][0] = {"kind": "integer", "value": 1}
        mutations.append(duplicate)
        for mutant in mutations:
            with self.subTest(mutant=mutant), self.assertRaises(CoreProtocolError):
                wire.unpack(mutant)

    def test_expansion_bombs_reject_before_serializing_or_allocating_expanded_tree(self):
        cases = [([{"kind": "null"}], 20, 2),
                 ([{"kind": "string", "value": "x" * 1024}], 15, 2),
                 ([{"kind": "null"}], 129, 1)]
        for nodes, count, repeats in cases:
            for index in range(count):
                nodes.append({"kind": "array", "items": [index] * repeats})
            packet = {"schema_version": wire.SCHEMA, "expanded_sha256": "0" * 64,
                      "root": len(nodes) - 1, "nodes": nodes}
            with self.subTest(count=count, repeats=repeats), patch.object(wire, "canonical_bytes", side_effect=AssertionError("Expansion happened")):
                with self.assertRaisesRegex(CoreProtocolError, "expanded node, byte or depth"):
                    wire.unpack(packet)

    def test_large_repeated_logical_document_fits_only_explicit_wire_profile(self):
        body = {"rows": [{"key": index, "value": index % 3} for index in range(250)]}
        logical = [body] * 400
        with self.assertRaises(CoreProtocolError):
            encode_json(logical)
        packet = wire.pack(logical)
        self.assertLess(len(encode_json(packet)), 80_000)
        restored = wire.unpack(packet)
        self.assertEqual(wire.canonical_bytes(restored), wire.canonical_bytes(logical))

    def test_cycles_nonfinite_values_unicode_and_large_scalars_are_rejected(self):
        cycle = []
        cycle.append(cycle)
        for value in (cycle, float("nan"), float("inf"), "\ud800", {1: "non-string"}, (1, 2)):
            with self.subTest(kind=type(value)), self.assertRaises(CoreProtocolError):
                wire.pack(value)
        with self.assertRaises(CoreProtocolError):
            wire.pack("x" * (4 * 1024 * 1024 + 1))

    def test_named_profile_keeps_physical_limits_and_role_operation_census(self):
        verifier, producer = wire.profile("verify"), wire.profile("core")
        self.assertEqual(verifier["max_packet_nodes"], 249_968)
        self.assertEqual(verifier["max_expanded_nodes"], 1_000_000)
        self.assertEqual(verifier["claims"], "transport_only")
        self.assertEqual(producer["operations"], list(wire.OPERATIONS) + [
            "compile-policy-component-material", "compile-policy-quantitative-assurance"])
        verifier["operations"].clear()
        self.assertEqual(len(wire.profile("verify")["operations"]), 8)


if __name__ == "__main__":
    unittest.main()

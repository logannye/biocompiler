"""Pure lossless-transport controls; no native invocation or acceptance claims."""
from copy import deepcopy
import hashlib
import random
import unittest
from unittest.mock import patch

from biocompiler import _policy_coupled_wire as wire
from biocompiler.core_client import CoreProtocolError, encode_json


def paired_export(report=None, manifest_body=None):
    """Inert closed transport shape, deliberately not an acceptance report."""
    return {"schema_version": "biocompiler.core.policy_quantitative_assurance.v1",
        "implementation": "biocompiler.ocaml.policy_quantitative_assurance.v0.1",
        "validation_scope": "policy-quantitative-assurance-v0.1",
        "request_fingerprint": "a" * 64, "candidate_fingerprint": "b" * 64,
        "invocation_fingerprint": "c" * 64, "report_fingerprint": "d" * 64,
        "candidate": {}, "report": report,
        "artifact": {"schema_version": "biocompiler.policy_quantitative_assurance_export.v0.1",
            "fasta": ">inert\nACGU\n", "fasta_sha256": "e" * 64, "manifest_sha256": "f" * 64,
            "manifest": {"schema_version": "biocompiler.policy_quantitative_assurance_manifest.v0.1", "inert": manifest_body}}}


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

    def test_paired_profile_is_additive_and_base_profile_matches_frozen_authority(self):
        self.assertEqual(wire.MAX_EXPORT_NODES, 2 * wire.MAX_EXPANDED_NODES - 1)
        self.assertEqual(wire.MAX_EXPORT_BYTES, 2 * wire.MAX_EXPANDED_BYTES - 4)
        self.assertEqual(hashlib.sha256(encode_json(wire.PROFILE)).hexdigest(),
                         "599b48d787011bbdf06cc13e5914917228a9f419a8d7c395ca795c181420aebe")
        exported = wire.export_profile()
        self.assertEqual(exported, {**wire.PROFILE, "schema_version": wire.EXPORT_SCHEMA,
            "max_expanded_nodes": 1_999_999, "max_expanded_bytes": 16_646_140,
            "direction": "response", "partition": "base_result_and_artifact",
            "max_part_nodes": 1_000_000, "max_part_bytes": 8_323_072,
            "operations": ["export-policy-quantitative-assurance"]})
        self.assertEqual((exported["max_packet_nodes"], exported["max_packet_bytes"]), (249_968, 8_323_072))
        exported["operations"].clear()
        self.assertEqual(wire.export_profile()["operations"], ["export-policy-quantitative-assurance"])

    def test_paired_export_above_base_byte_bound_preserves_exact_complete_identity(self):
        text = "x" * 2_100_000
        value = paired_export([text, text], [text, text])
        with self.assertRaises(CoreProtocolError): wire.pack(value)
        packet = wire.pack_export(value)
        self.assertTrue(wire.is_export_packet(packet))
        self.assertFalse(wire.is_packet(packet))
        self.assertLess(len(encode_json(packet)), 2_200_000)
        restored = wire.unpack_export(packet)
        canonical = wire.export_canonical_bytes(value)
        self.assertGreater(len(canonical), wire.MAX_EXPANDED_BYTES)
        self.assertEqual(wire.export_canonical_bytes(restored), canonical)
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), packet["expanded_sha256"])
        with self.assertRaises(CoreProtocolError): wire.unpack(packet)
        with self.assertRaises(CoreProtocolError): wire.unpack_export(wire.pack(paired_export()))

    def test_paired_export_above_base_node_bound_detaches_all_occurrences(self):
        part = [[None] * 1000] * 510
        value = paired_export(part, part)
        with self.assertRaises(CoreProtocolError): wire.canonical_bytes(value)
        packet = wire.pack_export(value)
        restored = wire.unpack_export(packet)
        self.assertEqual(wire.export_canonical_bytes(restored), wire.export_canonical_bytes(value))
        restored["report"][0][0] = True
        self.assertIsNone(restored["report"][1][0])
        self.assertIsNone(restored["artifact"]["manifest"]["inert"][0][0])

    def test_paired_export_checks_each_constituent_and_keeps_physical_bounds(self):
        nodes = [[None] * 1000] * 1000
        text = "x" * 3_000_000
        for report, artifact in ((nodes, None), (None, nodes), ([text] * 3, None), (None, [text] * 3)):
            with self.subTest(artifact=artifact is not None), self.assertRaisesRegex(CoreProtocolError, "constituent"):
                wire.pack_export(paired_export(report, artifact))
        # Logical parts fit, but five different large strings cannot be deduplicated
        # into the unchanged physical packet byte allowance.
        values = [str(index) * 1_700_000 for index in range(5)]
        value = paired_export(values[:3], values[3:])
        self.assertGreater(len(wire.export_canonical_bytes(value)), wire.MAX_PACKET_BYTES)
        with self.assertRaises(CoreProtocolError): wire.pack_export(value)

    def test_paired_export_is_closed_and_rejects_oversized_decode_before_expansion(self):
        changes = [lambda row: row.pop("candidate"), lambda row: row.update(extra=True),
            lambda row: row.update(schema_version="legacy"), lambda row: row.update(implementation="other"),
            lambda row: row.update(validation_scope="other"), lambda row: row.update(artifact=None),
            lambda row: row["artifact"].update(extra=True), lambda row: row["artifact"].update(schema_version="other"),
            lambda row: row["artifact"]["manifest"].update(schema_version="other")]
        for change in changes:
            row = paired_export()
            change(row)
            with self.subTest(change=change), self.assertRaises(CoreProtocolError): wire.pack_export(row)
        # Small DAG, exponential expansion: reject before canonical serialization.
        nodes = [{"kind": "null"}]
        for index in range(21): nodes.append({"kind": "array", "items": [index, index]})
        packet = {"schema_version": wire.EXPORT_SCHEMA, "expanded_sha256": "0" * 64,
                  "root": len(nodes) - 1, "nodes": nodes}
        with patch.object(wire, "export_canonical_bytes", side_effect=AssertionError("Expanded allocation")):
            with self.assertRaisesRegex(CoreProtocolError, "expanded node, byte or depth"):
                wire.unpack_export(packet)

    def test_paired_decode_rejects_each_oversized_part_before_digest_or_expansion(self):
        part = [[None] * 1000] * 900
        for path in (("report",), ("artifact", "manifest", "inert")):
            value = paired_export(part if path[0] == "report" else None,
                                  part if path[0] == "artifact" else None)
            packet = wire.pack_export(value)
            ordinal = packet["root"]
            for name in path:
                ordinal = dict(packet["nodes"][ordinal]["fields"])[name]
            row = packet["nodes"][ordinal]
            row["items"] = [row["items"][0]] * 1000
            # The entire altered expansion still fits 1,999,999 nodes. Its
            # 1,001,001-node part must fail before checking the stale digest.
            with self.subTest(path=path), patch.object(wire, "export_canonical_bytes", side_effect=AssertionError("Expansion happened")):
                with self.assertRaisesRegex(CoreProtocolError, "constituent"):
                    wire.unpack_export(packet)


if __name__ == "__main__":
    unittest.main()

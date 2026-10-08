"""Inert whole-AST restoration; updated byte pins cannot hide unrelated edits."""
from __future__ import annotations

import ast
import builtins
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import core_client_encoding_source_lineage as lineage

ROOT = Path(__file__).resolve().parents[1]


class CoreClientEncodingSourceLineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = (ROOT / lineage.PATH).read_bytes()

    def changed(self, before, after):
        self.assertTrue(before in self.raw, "Missing mutation anchor: " + repr(before))
        result = self.raw.replace(before, after, 1)
        self.assertNotEqual(result, self.raw)
        return result

    def verify_rehashed(self, raw):
        # Simulate a reviewer refreshing the current byte pin without changing
        # the independent original AST or the closed allowed-addition shapes.
        with patch.object(lineage, "CURRENT_SHA256", lineage.sha(raw)):
            return lineage.verify_current(raw, lineage.HISTORICAL_SHA256)

    def test_current_route_restores_independently_pinned_whole_original_ast(self):
        proof = lineage.verify_source(ROOT, lineage.PATH, lineage.HISTORICAL_SHA256)
        self.assertEqual(proof["historical_sha256"],
                         "c8d65a42c1f92cbd75cb5edd176a9463657e03509be8ed487496d78b17be00fc")
        self.assertEqual(proof["historical_ast_sha256"],
                         "22a7419ee9b1d2af88631b34c38f28c07bf884a1f4c562e849a48509166411d2")
        self.assertEqual(proof["current_sha256"], lineage.sha(self.raw))
        self.assertNotEqual(proof["historical_sha256"], proof["current_sha256"])
        self.assertEqual(proof["scope"], "exact_source_correspondence_only_no_execution_or_acceptance")

    def test_current_historical_identity_and_path_reject(self):
        for value in (self.raw.decode(), b"x" * (lineage.MAX_SOURCE_BYTES + 1)):
            with self.subTest(kind=type(value)), self.assertRaisesRegex(ValueError, "type/size"):
                lineage.verify_current(value, lineage.HISTORICAL_SHA256)
        with self.assertRaisesRegex(ValueError, "current byte identity"):
            lineage.verify_current(self.raw + b"\n", lineage.HISTORICAL_SHA256)
        with self.assertRaisesRegex(ValueError, "historical byte identity"):
            lineage.verify_current(self.raw, "0" * 64)
        with self.assertRaisesRegex(ValueError, "Unknown encoding source route"):
            lineage.verify_source(ROOT, "src/biocompiler/core_client_extra.py", lineage.HISTORICAL_SHA256)

    def test_rehashed_encoder_validation_options_and_limit_changes_reject(self):
        mutations = (
            (b"validate_json(value, byte_limit=limit)", b"validate_json(value, byte_limit=limit + 1)"),
            (b"ensure_ascii=False, allow_nan=False", b"ensure_ascii=True, allow_nan=False"),
            (b"if len(data) + len(chunk) > limit:", b"if len(data) + len(chunk) >= limit:"),
            (b'data.extend(chunk)', b'data.extend(chunk + b" ")'),
        )
        for before, after in mutations:
            with self.subTest(edit=before), self.assertRaisesRegex(ValueError, "historical transport/encoder AST"):
                self.verify_rehashed(self.changed(before, after))

    def test_rehashed_transport_protocol_signature_and_unrelated_import_reject(self):
        mutations = (
            self.changed(b'PROTOCOL = "biocompiler.core.v1"', b'PROTOCOL = "biocompiler.core.v2"'),
            self.changed(b'executable: Literal["core", "verify"]) -> CoreResponse:',
                         b'executable: Literal["core", "verify"] = "core") -> CoreResponse:'),
            self.changed(b'raise CoreProtocolError("Response protocol or request identity mismatch")', b'pass'),
            self.changed(b'if digest != self.expected_sha256:', b'if False:'),
            self.raw + b"\nimport decimal\n",
        )
        for raw in mutations:
            with self.subTest(edit=lineage.sha(raw)), self.assertRaisesRegex(ValueError, "historical transport/encoder AST"):
                self.verify_rehashed(raw)

    def test_rehashed_cache_ownership_bounds_and_cleanup_changes_reject(self):
        mutations = (
            (b'_OWNED_ENCODING_MAX_ENROLLED = 2_048', b'_OWNED_ENCODING_MAX_ENROLLED = 2_049'),
            (b'type(response) is CoreResponse', b'isinstance(response, CoreResponse)'),
            (b'if len(frame.source) != frame.length:', b'if False:'),
            (b'scope.active = False', b'scope.active = True'),
            (b'_OWNED_ENCODING.reset(token)', b'pass'),
        )
        for before, after in mutations:
            with self.subTest(edit=before), self.assertRaisesRegex(ValueError, "reviewed addition differs"):
                self.verify_rehashed(self.changed(before, after))

    def test_rehashed_cache_hit_store_and_validation_order_changes_reject(self):
        mutations = (
            self.changed(b'entry.value is not value', b'entry.value != value'),
            self.changed(b'if len(entry.data) > limit:', b'if len(entry.data) >= limit:'),
            self.changed(b'scope.cached_bytes += len(encoded)', b'scope.cached_bytes += 1'),
            self.changed(b'    validate_json(value, byte_limit=limit)\n    scope = _OWNED_ENCODING.get()',
                         b'    scope = _OWNED_ENCODING.get()\n    validate_json(value, byte_limit=limit)'),
        )
        for raw in mutations:
            with self.subTest(edit=lineage.sha(raw)), self.assertRaisesRegex(ValueError, "reviewed cache statement"):
                self.verify_rehashed(raw)

    def test_added_import_and_helper_census_are_closed_and_ordered(self):
        mutations = (
            self.changed(b'from collections import deque', b'from collections import deque, Counter'),
            self.changed(b'from dataclasses import dataclass, field', b'from dataclasses import dataclass, field, replace'),
            self.changed(b'from threading import get_ident\nimport time', b'import time\nfrom threading import get_ident'),
            self.changed(b'_OWNED_COPY_MAX_DEPTH = 128\n', b'_OWNED_COPY_MAX_DEPTH = 128\n_extra_encoding = True\n'),
            self.changed(b'_OWNED_COPY_MAX_VISITS = 250_000\n_OWNED_COPY_MAX_CONTAINERS = 50_000',
                         b'_OWNED_COPY_MAX_CONTAINERS = 50_000\n_OWNED_COPY_MAX_VISITS = 250_000'),
        )
        for raw in mutations:
            with self.subTest(edit=lineage.sha(raw)), self.assertRaises(ValueError):
                self.verify_rehashed(raw)

    def test_ast_encoding_preserves_literal_types_and_nonempty_generic_parameters(self):
        self.assertNotEqual(lineage.fingerprint(ast.parse("x = True")), lineage.fingerprint(ast.parse("x = 1")))
        self.assertNotEqual(lineage.fingerprint(ast.parse("x = 1")), lineage.fingerprint(ast.parse("x = 1.0")))
        tree = ast.parse("def f():\n    return b'bytes', ...\n")
        self.assertEqual(lineage.fingerprint(tree), lineage.fingerprint(ast.parse(ast.unparse(tree))))
        if hasattr(tree.body[0], "type_params"):
            plain = lineage.fingerprint(tree)
            tree.body[0].type_params = [ast.Name(id="T", ctx=ast.Load())]
            self.assertNotEqual(plain, lineage.fingerprint(tree))

    def test_route_is_inert_and_does_not_import_product_code(self):
        original = builtins.__import__

        def guarded(name, *args, **kwargs):
            if name == "biocompiler" or name.startswith("biocompiler."):
                self.fail("Source correspondence imported product code")
            return original(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=guarded):
            proof = lineage.verify_source(ROOT, lineage.PATH, lineage.HISTORICAL_SHA256)
        self.assertEqual(proof["kind"], "reviewed_private_owned_encoding_extension")

    def test_missing_symlink_and_oversized_source_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / lineage.PATH
            path.parent.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "missing, redirected or oversized"):
                lineage.verify_source(root, lineage.PATH, lineage.HISTORICAL_SHA256)
            original = root / "original.py"
            original.write_bytes(self.raw)
            path.symlink_to(original)
            with self.assertRaisesRegex(ValueError, "missing, redirected or oversized"):
                lineage.verify_source(root, lineage.PATH, lineage.HISTORICAL_SHA256)
            path.unlink()
            path.write_bytes(b"x" * (lineage.MAX_SOURCE_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "missing, redirected or oversized"):
                lineage.verify_source(root, lineage.PATH, lineage.HISTORICAL_SHA256)

    def test_realization_routes_core_client_as_historical_not_as_an_addition(self):
        from tools import check_realization_workflow_corpus as scope
        from tools import realization_source_lineage as route

        original = {"path": lineage.PATH, "sha256": lineage.HISTORICAL_SHA256}
        current = {"path": lineage.PATH, "sha256": lineage.sha(self.raw)}
        proof = route.verify_captured_source(ROOT, original)
        with patch.object(scope, "historical_sources", return_value=[original]):
            actual = scope.source_scope([current])
        self.assertEqual(actual["historical_sources"], [original])
        self.assertEqual(actual["actual_sources"], [current])
        self.assertEqual(actual["reviewed_routes"], [proof])
        self.assertEqual(actual["reviewed_additions"], [])
        self.assertEqual(actual["denied_modules"], [])
        document = {"source_files": [current], "observations": [{"outcome": False}]}
        projected = scope.historical_projection(document, actual)
        self.assertEqual(projected["source_files"], [original])
        self.assertIs(projected["observations"], document["observations"])
        with patch.object(scope, "historical_sources", return_value=[original]):
            with self.assertRaisesRegex(AssertionError, "source bytes changed"):
                scope.source_scope([{**current, "sha256": "0" * 64}])

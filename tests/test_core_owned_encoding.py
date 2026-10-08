"""Private byte reuse, ownership and unchanged checking against synthetic peers.

These tests execute Python only. They neither generate nor admit native payloads.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import copy_context
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from biocompiler import core_client as core
from biocompiler import core_policy_component_material as material
from biocompiler import core_policy_component_selection as selection
from tests import test_core_policy_component_material as material_peer
from tests import test_core_policy_component_selection as selection_peer


def containers(value):
    result = set()
    pending = [value]
    while pending:
        item = pending.pop()
        if type(item) is list or type(item) is dict:
            if id(item) in result:
                continue
            result.add(id(item))
            pending.extend(item.values() if type(item) is dict else item)
    return result


@contextmanager
def encodings():
    original = json.JSONEncoder.iterencode
    with patch.object(json.JSONEncoder, "iterencode", autospec=True, side_effect=original) as calls:
        yield calls


class OwnedJsonCopyTests(unittest.TestCase):
    def test_copy_is_disjoint_preserves_literal_bytes_and_shared_occurrences(self):
        shared = [{"é": [None, True, False, 1, 1.0, -0.0, "\n\x00😃"]}]
        original = {"first": shared, "second": shared}
        before = core.encode_json(original)
        owned = core._try_owned_json_copy(original)
        self.assertIsNotNone(owned)
        self.assertTrue(containers(original).isdisjoint(containers(owned.value)))
        self.assertIsNot(owned.value["first"], owned.value["second"])
        shared[0]["é"].clear()
        original.clear()
        self.assertEqual(core.encode_json(owned.value), before)

    def test_no_python_subclass_or_conversion_hooks_are_called(self):
        def forbidden(*_args, **_kwargs):
            raise AssertionError("Copy called an untrusted hook")

        class Meta(type):
            __eq__ = forbidden

        class Foreign(metaclass=Meta):
            __deepcopy__ = __iter__ = __str__ = forbidden

        class ForeignList(list):
            __iter__ = __deepcopy__ = forbidden

        class ForeignDict(dict):
            items = __deepcopy__ = forbidden

        class ForeignInt(int):
            __str__ = forbidden

        class ForeignStr(str):
            encode = forbidden

        for item in (Foreign(), ForeignList(), ForeignDict(), ForeignInt(1), ForeignStr("x"), {1: "x"}):
            with self.subTest(kind=type(item).__name__):
                self.assertIsNone(core._try_owned_json_copy(item))
        # Invalid immutable atoms are intentionally left for the old validator.
        for atom in (float("inf"), float("nan"), 1 << 4096, "\ud800"):
            self.assertIs(core._try_owned_json_copy(atom).value, atom)

    def test_cycles_depth_visits_and_container_bounds_only_decline(self):
        cycle = []
        cycle.append(cycle)
        self.assertIsNone(core._try_owned_json_copy(cycle))
        shared = [0, 1]
        for limit, bound, value in (
            ("_OWNED_COPY_MAX_DEPTH", 1, [[0]]),
            ("_OWNED_COPY_MAX_VISITS", 6, [shared, shared]),
            ("_OWNED_COPY_MAX_VISITS", 2, {"x": 1}),
            ("_OWNED_COPY_MAX_CONTAINERS", 2, [[], []]),
        ):
            with self.subTest(limit=limit), patch.object(core, limit, bound):
                self.assertIsNone(core._try_owned_json_copy(value))
        with patch.object(core, "_OWNED_COPY_MAX_VISITS", 3):
            self.assertEqual(core._try_owned_json_copy({"x": 1}).value, {"x": 1})

    def test_structural_mutation_during_copy_declines(self):
        original_frame = core._CopyFrame
        for original in ([[]], {"x": []}):
            def frame(*args):
                created = original_frame(*args)
                if args[0] is not original:
                    original.clear()
                return created
            with self.subTest(kind=type(original)), patch.object(core, "_CopyFrame", side_effect=frame):
                self.assertIsNone(core._try_owned_json_copy(original))


class OwnedEncodingTests(unittest.TestCase):
    def owned(self, value):
        copied = core._try_owned_json_copy(value)
        self.assertIsNotNone(copied)
        return copied

    def test_exact_bytes_and_every_call_validates_including_hits(self):
        owned = self.owned({"é": [True, 1, 1.0, -0.0, 9007199254740993, 1e-7, "\x00\n😃"]})
        expected = core.encode_json(owned.value)
        with encodings() as calls, patch.object(core, "validate_json", wraps=core.validate_json) as validates:
            with core._owned_encoding_scope(owned):
                self.assertEqual(core.encode_json(owned.value), expected)
                self.assertEqual(core.encode_json(owned.value), expected)
                self.assertEqual(calls.call_count, 1)
                self.assertEqual(validates.call_count, 2)
                self.assertEqual(core._OWNED_ENCODING.get().cached_entries, 1)

    def test_hits_recheck_byte_string_node_and_numeric_limits(self):
        owned = self.owned({"a": ["\x00" * 8, 12345]})
        with core._owned_encoding_scope(owned), encodings() as calls:
            expected = core.encode_json(owned.value)
            # Escaping exceeds the validator's byte floor: the hit must still
            # enforce the exact encoded length under a smaller caller limit.
            with self.assertRaisesRegex(core.CoreProtocolError, "byte budget"):
                core.encode_json(owned.value, limit=len(expected) - 1)
            for limits, message in (({"max_string_bytes": 4}, "string budget"),
                                    ({"max_json_nodes": 2}, "node"),
                                    ({"max_number_chars": 4}, "number budget"),
                                    ({"max_depth": 1}, "depth")):
                with self.subTest(limits=limits), patch.dict(core.LIMITS, limits), \
                        self.assertRaisesRegex(core.CoreProtocolError, message):
                    core.encode_json(owned.value)
            self.assertEqual(core.encode_json(owned.value), expected)
            self.assertEqual(calls.call_count, 1)

    def test_invalid_values_never_cache_a_success_or_error(self):
        for value in ([float("nan")], ["\ud800"], [1 << 15000]):
            with self.subTest(kind=type(value[0])), core._owned_encoding_scope(self.owned(value)):
                scope = core._OWNED_ENCODING.get()
                for _ in range(2):
                    with self.assertRaises(core.CoreProtocolError):
                        core.encode_json(next(iter(scope.entries.values())).value)
                self.assertEqual(scope.cached_entries, 0)
                self.assertEqual(scope.cached_bytes, 0)
        owned = self.owned(["\x00" * 8])
        with core._owned_encoding_scope(owned), encodings() as calls:
            with self.assertRaises(core.CoreProtocolError):
                core.encode_json(owned.value, limit=20)
            self.assertEqual(core._OWNED_ENCODING.get().cached_entries, 0)
            core.encode_json(owned.value)
            core.encode_json(owned.value)
            self.assertEqual(calls.call_count, 2)

    def test_only_owned_identity_and_containers_are_cached(self):
        owned = self.owned([{"a": [1]}])
        distinct = deepcopy(owned.value)
        with core._owned_encoding_scope(owned), encodings() as calls:
            for _ in range(2):
                core.encode_json(owned.value)
                core.encode_json(distinct)
                core.encode_json(1)
            self.assertEqual(calls.call_count, 5)
            scope = core._OWNED_ENCODING.get()
            self.assertIs(scope.entries[id(owned.value)].value, owned.value)
            self.assertNotIn(id(distinct), scope.entries)
            # Even a corrupted identity table must never serve another object.
            scope.entries[id(distinct)] = scope.entries[id(owned.value)]
            core.encode_json(distinct)
            self.assertEqual(calls.call_count, 6)

    def test_cache_entry_and_byte_saturation_recomputes_without_rejection(self):
        first, second = self.owned([1]), self.owned([2])
        for cap, amount in (("_OWNED_ENCODING_MAX_ENTRIES", 1), ("_OWNED_ENCODING_MAX_BYTES", 3)):
            with self.subTest(cap=cap), patch.object(core, cap, amount), \
                    core._owned_encoding_scope(first, second), encodings() as calls:
                for _ in range(2):
                    self.assertEqual(core.encode_json(first.value), b"[1]")
                    self.assertEqual(core.encode_json(second.value), b"[2]")
                self.assertEqual(calls.call_count, 3)
                self.assertEqual(core._OWNED_ENCODING.get().cached_entries, 1)
                self.assertEqual(core._OWNED_ENCODING.get().cached_bytes, 3)
        with patch.object(core, "_OWNED_ENCODING_MAX_BYTES", 2), \
                core._owned_encoding_scope(first), encodings() as calls:
            for _ in range(2):
                self.assertEqual(core.encode_json(first.value), b"[1]")
            self.assertEqual(calls.call_count, 2)

    def test_breadth_first_enrollment_is_bounded_and_retains_both_roots(self):
        first, second = self.owned([[[]], [[]], [[]]]), self.owned([[[]]])
        with patch.object(core, "_OWNED_ENCODING_MAX_ENROLLED", 4), core._owned_encoding_scope(first, second):
            entries = core._OWNED_ENCODING.get().entries
            self.assertEqual(set(entries), {id(first.value), id(second.value), id(first.value[0]), id(first.value[1])})
            self.assertEqual(core.encode_json(second.value[0]), b"[[]]")
        with patch.object(core, "_OWNED_ENCODING_MAX_VISITS", 1), core._owned_encoding_scope(first, second):
            self.assertEqual(len(core._OWNED_ENCODING.get().entries), 3)
        large = self.owned([[] for _ in range(2100)])
        with core._owned_encoding_scope(large):
            self.assertEqual(len(core._OWNED_ENCODING.get().entries), 2048)

    def test_nested_scope_restores_parent_and_exception_clears_references(self):
        outer, inner = self.owned([1]), self.owned([2])
        with encodings() as calls:
            with core._owned_encoding_scope(outer):
                parent = core._OWNED_ENCODING.get()
                core.encode_json(outer.value)
                with self.assertRaisesRegex(RuntimeError, "exit"), core._owned_encoding_scope(inner):
                    nested = core._OWNED_ENCODING.get()
                    core.encode_json(inner.value)
                    raise RuntimeError("exit")
                self.assertIs(core._OWNED_ENCODING.get(), parent)
                core.encode_json(outer.value)
                self.assertEqual(calls.call_count, 2)
            for scope in (parent, nested):
                self.assertFalse(scope.active)
                self.assertEqual(scope.entries, {})
                self.assertEqual((scope.cached_entries, scope.cached_bytes), (0, 0))
            self.assertIsNone(core._OWNED_ENCODING.get())
            with core._owned_encoding_scope(outer):
                core.encode_json(outer.value)
                self.assertEqual(calls.call_count, 3)

    def test_inherited_context_cannot_reuse_other_thread_or_closed_scope(self):
        owned = self.owned([1])
        with encodings() as calls:
            with core._owned_encoding_scope(owned):
                core.encode_json(owned.value)
                inherited = copy_context()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    self.assertEqual(pool.submit(inherited.run, core.encode_json, owned.value).result(), b"[1]")
                self.assertEqual(calls.call_count, 2)
                core.encode_json(owned.value)
                self.assertEqual(calls.call_count, 2)
            self.assertEqual(inherited.run(core.encode_json, owned.value), b"[1]")
            self.assertEqual(calls.call_count, 3)
            core.encode_json(owned.value)
            self.assertEqual(calls.call_count, 4)


class OwnedFacadeTests(unittest.TestCase):
    def setUp(self):
        self.peer = selection_peer.PolicyComponentSelectionTransportTests()
        self.peer.setUp()
        self.addCleanup(self.peer.doCleanups)

    def profiles(self, api):
        if api is material:
            return core._capabilities(material_peer.capabilities("core"))
        return core.CoreCapabilities(("capabilities", *selection.OPERATIONS, selection.COMPILE_OPERATION), (),
            (selection.VALIDATION_SCOPE,), "synthetic peer", core.encode_json({
                "policy_component_selection": selection.PROFILE,
                "policy_component_selection_producer": selection.PRODUCER_PROFILE}))

    def fixture(self, api):
        peer = material_peer if api is material else selection_peer
        request = peer.original()
        return peer, {"request": request, "candidate": peer.candidate(request), "limits": deepcopy(self.peer.limits)}

    def response(self, api, payload, operation=None):
        peer = material_peer if api is material else selection_peer
        operation = operation or f"check-policy-component-{'material' if api is material else 'selection'}"
        return core.CoreResponse("literal", operation, "ok", peer.result(payload, export=operation.startswith("export")), (), "core", core.CORE_VERSION)

    @contextmanager
    def transport(self, api, call):
        client_type = material.PolicyComponentMaterialClient if api is material else selection.PolicyComponentSelectionClient
        class Transport:
            role = "core"

            def negotiate(_self, operation, *, cancelled):
                self.assertIsNone(core._OWNED_ENCODING.get())
                return self.profiles(api)

            def call(_self, operation, payload, *, cancelled):
                self.assertIsNone(core._OWNED_ENCODING.get())
                return call(operation, payload)
        yield client_type(Transport())

    def test_private_original_and_response_are_disjoint_from_transport(self):
        for api in (material, selection):
            _peer, payload = self.fixture(api)
            before = core.encode_json(payload)
            retained = {}
            original_result = api._result

            def call(operation, transport_payload):
                retained["payload"] = transport_payload
                retained["response"] = self.response(api, transport_payload, operation)
                return retained["response"]

            def validate(response, snapshot):
                scope = core._OWNED_ENCODING.get()
                self.assertIsNotNone(scope)
                private_ids = containers(snapshot) | containers(response.result)
                self.assertTrue(private_ids.isdisjoint(containers(payload)))
                self.assertTrue(private_ids.isdisjoint(containers(retained["payload"])))
                self.assertTrue(private_ids.isdisjoint(containers(retained["response"].result)))
                self.assertEqual(core.encode_json(snapshot), before)
                retained["payload"].clear()
                retained["response"].result.clear()
                payload.clear()
                return original_result(response, snapshot)

            with self.subTest(api=api.__name__), self.transport(api, call) as client, patch.object(api, "_result", side_effect=validate):
                checked = client.check(**payload)
                expected = core.encode_json(checked.result)
                checked.result.clear()
                self.assertEqual(core.encode_json(checked.result), expected)

    def test_repinned_transport_request_substitution_rejects_with_cache_on_or_off(self):
        for api in (material, selection):
            for disabled in (False, True):
                _peer, payload = self.fixture(api)
                expected = core.encode_json(payload)
                seen = []

                def call(operation, supplied):
                    supplied["request"]["budgets"]["max_work"] -= 1
                    # Every returned outer/request/report pin uses the substitute.
                    changed = self.response(api, supplied, operation)
                    self.assertEqual(changed.result["request_fingerprint"], material_peer.digest(supplied["request"]))
                    seen.append(operation)
                    return changed

                with self.subTest(api=api.__name__, disabled=disabled), self.transport(api, call) as client, \
                        patch.object(core, "_OWNED_ENCODING_MAX_ENTRIES", 0 if disabled else 2048), \
                        self.assertRaisesRegex(core.CoreProtocolError, "original|Original"):
                    client.check(**payload)
                self.assertEqual(len(seen), 1)
                self.assertEqual(core.encode_json(payload), expected)

    def test_valid_copy_decline_preserves_output_and_has_no_active_scope(self):
        for api in (material, selection):
            _peer, payload = self.fixture(api)
            response = self.response(api, payload)
            expected = api._result(response, payload)
            original_result = api._result

            def validate(actual, snapshot):
                self.assertIsNone(core._OWNED_ENCODING.get())
                self.assertIs(actual, response)
                return original_result(actual, snapshot)

            with self.subTest(api=api.__name__), self.transport(api, lambda *_: response) as client, \
                    patch.object(core, "_OWNED_COPY_MAX_CONTAINERS", 0), patch.object(api, "_result", side_effect=validate):
                actual = client.check(**payload)
            self.assertEqual(actual._result_json, expected._result_json)

    def test_response_subclass_keeps_original_validation_without_new_initializer_hook(self):
        initializations = []

        class CustomResponse(core.CoreResponse):
            def __init__(self, *args, **kwargs):
                initializations.append(core._OWNED_ENCODING.get())
                super().__init__(*args, **kwargs)

        for api in (material, selection):
            _peer, payload = self.fixture(api)
            base = self.response(api, payload)
            response = CustomResponse(base.request_id, base.operation, base.status, base.result,
                                      base.diagnostics, base.executable, base.version)
            before_baseline = len(initializations)
            expected = api._result(response, payload)
            baseline_initializations = len(initializations) - before_baseline
            original_result = api._result

            def validate(actual, snapshot):
                self.assertIsNone(core._OWNED_ENCODING.get())
                self.assertIs(actual, response)
                return original_result(actual, snapshot)

            with self.subTest(api=api.__name__), self.transport(api, lambda *_: response) as client, \
                    patch.object(api, "_try_owned_json_copy", side_effect=AssertionError("Subclass must stay uncached")), \
                    patch.object(api, "_result", side_effect=validate):
                before_actual = len(initializations)
                actual = client.check(**payload)
            # Existing child validators also replace responses. Preserve those
            # original hooks, without adding the optimization's replacement.
            self.assertEqual(len(initializations) - before_actual, baseline_initializations)
            self.assertEqual(actual._result_json, expected._result_json)
        self.assertTrue(initializations)
        self.assertTrue(all(scope is None for scope in initializations))

    def test_callback_bearing_metadata_preserves_uncached_outcomes(self):
        callbacks = []

        class HookStr(str):
            def __eq__(self, other):
                callbacks.append(core._OWNED_ENCODING.get())
                return str.__eq__(self, other)

            def __ne__(self, other):
                callbacks.append(core._OWNED_ENCODING.get())
                return str.__ne__(self, other)

            def __hash__(self):
                callbacks.append(core._OWNED_ENCODING.get())
                return str.__hash__(self)

        class HookTuple(tuple):
            def __bool__(self):
                callbacks.append(core._OWNED_ENCODING.get())
                return bool(len(self))

        def outcome(validate):
            try:
                return ("ok", validate()._result_json)
            except core.CoreProtocolError as error:
                return (type(error), str(error))

        for api in (material, selection):
            _peer, payload = self.fixture(api)
            base = self.response(api, payload)
            changes = [{field: HookStr(getattr(base, field))}
                       for field in ("request_id", "operation", "status", "executable", "version")]
            changes += [{"diagnostics": HookTuple()},
                        {"diagnostics": (core.Diagnostic("literal", "literal", None),)}]
            for fields in changes:
                response = replace(base, **fields)
                expected = outcome(lambda: api._result(response, payload))
                original_result = api._result

                def validate(actual, snapshot):
                    self.assertIsNone(core._OWNED_ENCODING.get())
                    self.assertIs(actual, response)
                    return original_result(actual, snapshot)

                with self.subTest(api=api.__name__, field=next(iter(fields))), self.transport(api, lambda *_: response) as client, \
                        patch.object(api, "_try_owned_json_copy", side_effect=AssertionError("Metadata must stay uncached")), \
                        patch.object(api, "_result", side_effect=validate):
                    actual = outcome(lambda: client.check(**payload))
                self.assertEqual(actual, expected)
        self.assertTrue(callbacks)
        self.assertTrue(all(scope is None for scope in callbacks))

    def test_declined_copy_retains_exact_existing_diagnostic_and_order(self):
        for api in (material, selection):
            for bad in ({"extra": 1 << 4096}, {"extra": "x" * (core.LIMITS["max_string_bytes"] + 1)}, {"extra": object()}):
                _peer, payload = self.fixture(api)
                response = replace(self.response(api, payload), result=bad)
                with self.assertRaises(core.CoreProtocolError) as baseline:
                    api._result(response, payload)
                for force_decline in (False, True):
                    with self.subTest(api=api.__name__, bad=type(bad["extra"]), decline=force_decline), \
                            self.transport(api, lambda *_: response) as client, \
                            patch.object(core, "_OWNED_COPY_MAX_CONTAINERS", 0 if force_decline else 50000), \
                            self.assertRaises(core.CoreProtocolError) as actual:
                        client.check(**payload)
                    self.assertEqual(str(actual.exception), str(baseline.exception))

    def test_all_routes_match_bytes_and_usage_with_cache_on_and_off(self):
        for api in (material, selection):
            outputs = []
            for disabled in (False, True):
                _peer, payload = self.fixture(api)
                operations = []

                def call(operation, supplied):
                    operations.append(operation)
                    return self.response(api, supplied, operation)

                with self.subTest(api=api.__name__, disabled=disabled), self.transport(api, call) as client, \
                        patch.object(core, "_OWNED_ENCODING_MAX_ENTRIES", 0 if disabled else 2048):
                    compiled = client.compile(payload["request"], payload["limits"])
                    checked = client.check(payload["request"], compiled.candidate, payload["limits"])
                    replayed = client.replay(payload["request"], compiled.candidate, payload["limits"], checked.result)
                    exported = client.export(payload["request"], compiled.candidate, payload["limits"])
                    outputs.append(tuple(value._result_json for value in (compiled, checked, replayed, exported)))
                self.assertEqual(len(operations), 4)
            self.assertEqual(outputs[0], outputs[1])

    def test_direct_validation_does_not_reuse_encodings(self):
        _peer, payload = self.fixture(material)
        response = self.response(material, payload)
        with encodings() as calls:
            first = material._result(response, payload)
            count = calls.call_count
            second = material._result(response, payload)
            self.assertGreater(count, 1)
            self.assertEqual(calls.call_count, 2 * count)
            self.assertEqual(first._result_json, second._result_json)


if __name__ == "__main__":
    unittest.main()

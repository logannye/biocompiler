"""Transport tests use Python child processes; no local native build is needed."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from biocompiler.core_client import (
    CORE_VERSION, LIMITS, PROTOCOL, CoreCancelled, CoreClient, CoreProtocolError,
    CoreRejected, CoreTimeout, CoreTransportError, CoreUnavailable, CoreUnsupported,
    decode_json, encode_json,
)


CHILD = '''import json, sys
request = json.load(sys.stdin)
response = {
    "protocol": "biocompiler.core.v1", "request_id": request["request_id"],
    "operation": request["operation"], "status": "ok", "result": {"echo": request["payload"]},
    "diagnostics": [], "core": {"implementation": "ocaml", "version": "0.1.0",
    "protocol": "biocompiler.core.v1", "executable": "core"}}
'''


class CoreJsonTests(unittest.TestCase):
    def test_numeric_and_unicode_identity(self):
        value = {"😃": -0.0, "é": [True, 1, 1.0, 9_007_199_254_740_993, 10**200, 1e-7]}
        encoded = encode_json(value)
        self.assertEqual(encoded, json.dumps(value, sort_keys=True, separators=(",", ":"),
                                            ensure_ascii=False, allow_nan=False).encode())
        self.assertEqual(encode_json(decode_json(encoded)), encoded)

    def test_invalid_or_ambiguous_json(self):
        for raw in (b'{"x":1,"x":2}', b'NaN', b'Infinity', b'1e999', b'"\xff"',
                    b'"\\ud800"', b'{} {}', b'\xef\xbb\xbf{}', b'01', b''):
            with self.subTest(raw=raw), self.assertRaises(CoreProtocolError):
                decode_json(raw)

    def test_no_python_object_or_number_coercion(self):
        for value in ({1: "key"}, (1, 2), object(), float("inf"), float("nan"), "\ud800"):
            with self.subTest(kind=type(value)), self.assertRaises(CoreProtocolError):
                encode_json(value)

    def test_cumulative_budgets_and_cycles(self):
        with patch.dict(LIMITS, max_depth=2, max_json_nodes=10, max_string_bytes=8, max_number_chars=4):
            for value in ([[[0]]], [0]*10, "abcde😃", 10000, {str(i): i for i in range(10)}):
                with self.subTest(value=value), self.assertRaises(CoreProtocolError):
                    encode_json(value)
            with self.assertRaises(CoreProtocolError):
                decode_json(b'10000')
        cycle = []
        cycle.append(cycle)
        with self.assertRaises(CoreProtocolError):
            encode_json(cycle)
        with self.assertRaises(CoreProtocolError):
            encode_json({}, limit=1)

    def test_response_string_can_hold_a_canonicalized_request(self):
        with patch.dict(LIMITS, max_string_bytes=8):
            self.assertEqual(decode_json(b'"a canonical request"', limit=100), "a canonical request")
            with self.assertRaises(CoreProtocolError):
                encode_json("a canonical request")

    def test_repeated_shared_strings_and_escaping_stop_before_full_serialization(self):
        # A small object graph must not allocate its arbitrarily large JSON expansion.
        shared = "x" * 10_000
        with self.assertRaises(CoreProtocolError):
            encode_json([shared] * 100_000, limit=50_000)
        # The preflight lower bound alone cannot account for JSON escaping.
        with self.assertRaises(CoreProtocolError):
            encode_json(["\x00" * 100], limit=500)

    def test_integer_budget_is_independent_of_notebook_global_settings(self):
        previous = sys.get_int_max_str_digits()
        try:
            sys.set_int_max_str_digits(0)
            with self.assertRaises(CoreProtocolError):
                encode_json(1 << 1_000_000)
        finally:
            sys.set_int_max_str_digits(previous)


@unittest.skipUnless(os.name == "posix", "Initial transport distribution targets POSIX")
class CoreProcessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "fake-core"

    def client(self, code="", *, raw=False, **kwargs):
        script = code if raw else CHILD + code + '\nprint(json.dumps(response))\n'
        self.path.write_text(f"#!{sys.executable}\n" + script, encoding="utf-8")
        self.path.chmod(0o700)
        return CoreClient(self.path, **kwargs)

    def test_complete_request_roundtrip_and_explicit_identity(self):
        client = self.client()
        result = client.call("canonicalize", {"integer": 2**100, "float": -0.0}, request_id="test")
        self.assertEqual(result.result, {"echo": {"integer": 2**100, "float": -0.0}})
        self.assertEqual(result.request_id, "test")
        self.assertEqual(result.version, CORE_VERSION)
        self.assertEqual(result.executable, "core")

    def test_absent_executable_and_digest_mismatch_never_fallback(self):
        with self.assertRaises(CoreUnavailable):
            CoreClient(self.path).capabilities()
        with self.assertRaises(ValueError):
            CoreClient(Path("biocompiler-core"))
        client = self.client(expected_sha256="0"*64)
        with self.assertRaises(CoreUnavailable):
            client.capabilities()
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.assertEqual(CoreClient(self.path, expected_sha256=digest).capabilities().status, "ok")

    def test_bad_timeout_configuration(self):
        for timeout in (True, 0, -1, float("inf"), float("nan")):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                CoreClient(self.path, timeout_seconds=timeout)

    def test_wrong_response_identity_and_shape(self):
        changes = (
            'response["request_id"] = "stale"',
            'response["operation"] = "compile"',
            'response["protocol"] = "unknown"',
            'response["core"]["executable"] = "verify"',
            'response["core"]["version"] = "next"',
            'response["core"]["implementation"] = "python"',
            'response["core"]["protocol"] = "unknown"',
            'response["extra"] = True',
            'response["result"] = None',
            'response["diagnostics"] = [{"code":"bad","message":"bad","path":None}]',
            'response["status"] = []',
            'response["diagnostics"] = {}',
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaises(CoreProtocolError):
                self.client(change).capabilities()

    def test_error_and_unsupported_are_distinct(self):
        for status, code, exception in (("error", 2, CoreRejected), ("unsupported", 3, CoreUnsupported)):
            child = CHILD + f'''response["status"] = "{status}"
response["result"] = None
response["diagnostics"] = [{{"code":"test.failure","message":"Expected failure","path":"payload"}}]
print(json.dumps(response))
sys.exit({code})
'''
            with self.subTest(status=status), self.assertRaises(exception) as found:
                self.client(child, raw=True).capabilities()
            self.assertEqual(found.exception.response.diagnostics[0].code, "test.failure")

    def test_exit_status_must_match_and_crashes_are_transport_failures(self):
        with self.assertRaises(CoreProtocolError):
            self.client(CHILD + 'print(json.dumps(response)); sys.exit(2)', raw=True).capabilities()
        with self.assertRaises(CoreTransportError):
            self.client(CHILD + 'sys.exit(9)', raw=True).capabilities()

    def test_partial_duplicate_non_utf8_and_multiple_responses_rejected(self):
        outputs = (b'{', b'{"x":1,"x":2}', b'\xff', b'{}\n{}\n')
        for output in outputs:
            with self.subTest(output=output), self.assertRaises(CoreProtocolError):
                self.client(CHILD + f'sys.stdout.buffer.write({output!r})', raw=True).capabilities()

    def test_timeout_and_cancellation_discard_partial_output(self):
        stalled = CHILD + 'import time; print("{", flush=True); time.sleep(30)'
        start = time.monotonic()
        with self.assertRaises(CoreTimeout):
            self.client(stalled, raw=True, timeout_seconds=0.1).capabilities()
        self.assertLess(time.monotonic()-start, 5)
        start = time.monotonic()
        with self.assertRaises(CoreCancelled):
            self.client(stalled, raw=True).call("capabilities", {}, cancelled=lambda: time.monotonic()-start > 0.1)
        self.assertLess(time.monotonic()-start, 5)
        with self.assertRaises(CoreCancelled):
            self.client().call("capabilities", {}, cancelled=lambda: True)

    def test_stdout_and_stderr_are_bounded(self):
        with patch.dict(LIMITS, max_response_bytes=100):
            with self.assertRaises(CoreTransportError):
                self.client(CHILD + 'sys.stdout.write("x"*1000)', raw=True).capabilities()
        with patch("biocompiler.core_client.MAX_STDERR_BYTES", 100):
            with self.assertRaises(CoreTransportError):
                self.client(CHILD + 'sys.stderr.write("x"*1000)', raw=True).capabilities()

    def test_closed_input_and_inherited_pipes_do_not_hang(self):
        with self.assertRaises(CoreTransportError):
            self.client('import sys; sys.exit(4)', raw=True).call("canonicalize", "x"*100000)
        child = CHILD + '''import os, time
if os.fork() == 0:
    time.sleep(30)
else:
    print(json.dumps(response))
'''
        with self.assertRaises(CoreTimeout):
            self.client(child, raw=True, timeout_seconds=0.2).capabilities()


if __name__ == "__main__":
    unittest.main()

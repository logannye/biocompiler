"""Independent HTTP probes of authority, replay, and isolated Studio sessions."""

from copy import deepcopy
import hashlib
from http.client import HTTPConnection
import json
import threading
import unittest

from biocompiler.studio.server import create_server


class StudioAdversarialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(port=0)
        cls.thread = threading.Thread(
            target=cls.server.serve_forever,
            kwargs={"poll_interval": 0.01},
            daemon=True,
        )
        cls.thread.start()
        cls.addClassCleanup(cls.close_server)
        status, body = cls.call("GET", "/api/session")
        if status != 200 or not body.get("ok"):
            raise AssertionError(body)
        cls.request = body["result"]["example"]["request"]
        status, body = cls.call("POST", "/api/compile", {"request": cls.request})
        if status != 200 or not body.get("ok"):
            raise AssertionError(body)
        cls.record = body["result"]["record"]

    @classmethod
    def close_server(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    @classmethod
    def call(cls, method, path, payload=None, *, server=None, token=None):
        server = server or cls.server
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=10)
        headers = {}
        content = None
        if payload is not None:
            content = json.dumps(payload).encode("utf-8")
            headers = {
                "Origin": server.studio_origin,
                "X-Biocompiler-Token": token or server.studio_token,
                "Content-Type": "application/json",
            }
        try:
            connection.request(method, path, body=content, headers=headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def assert_rejected_exports(self, request, record):
        for kind in ("fasta", "build", "request"):
            with self.subTest(format=kind):
                status, body = self.call(
                    "POST",
                    "/api/export",
                    {"request": request, "record": record, "format": kind},
                )
                self.assertEqual(status, 400, body)
                self.assertFalse(body["ok"])
                self.assertNotIn("result", body)
                self.assertNotIn("content", body)

    def test_new_authority_cannot_export_a_previous_build_in_any_format(self):
        changed = deepcopy(self.request)
        changed["constraints"]["max_length"] = 1
        status, prepared = self.call("POST", "/api/prepare", {"request": changed})
        self.assertEqual(status, 200, prepared)
        self.assertEqual(prepared["result"]["request"], changed)
        self.assert_rejected_exports(prepared["result"]["request"], self.record)

        # Preparing another request cannot silently change authority for the old one.
        status, body = self.call(
            "POST",
            "/api/export",
            {"request": self.request, "record": self.record, "format": "request"},
        )
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body["result"]["content"]), self.request)

    def test_rehashed_synonymous_sequence_does_not_reuse_saved_pass(self):
        forged = deepcopy(self.record)
        sequence = "GGAUGGCCUAACCAAAA"
        self.assertNotEqual(sequence, forged["molecule"]["sequence"])
        forged["molecule"]["sequence"] = sequence
        forged["molecule"]["sequence_sha256"] = hashlib.sha256(
            sequence.encode("ascii")
        ).hexdigest()
        self.assert_rejected_exports(self.request, forged)

    def test_stale_tool_and_promoted_claims_cannot_download_json(self):
        stale = deepcopy(self.record)
        stale["tool_versions"]["pipeline"] = "unrecognized-version"
        self.assert_rejected_exports(self.request, stale)
        promoted = deepcopy(self.record)
        promoted["therapeutic_implementation"] = "complete"
        promoted["human_therapeutic_admission"] = "admitted"
        self.assert_rejected_exports(self.request, promoted)

    def test_import_preserves_literal_library_identity_and_download_name(self):
        imported = deepcopy(self.request)
        literal = '../../<img src=x onerror="alert(1)">; $(touch forbidden)'
        imported["library"]["id"] = literal
        status, prepared = self.call("POST", "/api/prepare", {"request": imported})
        self.assertEqual(status, 200, prepared)
        self.assertEqual(prepared["result"]["request"], imported)
        self.assertEqual(prepared["result"]["overview"]["library_name"], literal)
        self.assertFalse(prepared["result"]["overview"]["fixture"])
        status, compiled = self.call("POST", "/api/compile", {"request": imported})
        self.assertEqual(status, 200, compiled)
        record = compiled["result"]["record"]
        self.assertEqual(record["request"], imported)
        self.assertEqual(
            record["molecule"]["sequence"], self.record["molecule"]["sequence"]
        )
        status, exported = self.call(
            "POST",
            "/api/export",
            {"request": imported, "record": record, "format": "build"},
        )
        self.assertEqual(status, 200, exported)
        self.assertRegex(
            exported["result"]["filename"], r"^candidate-[0-9a-f]{12}\.build\.json$"
        )
        self.assertEqual(json.loads(exported["result"]["content"])["request"], imported)

    def test_session_token_does_not_authorize_another_server(self):
        other = create_server(port=0)
        thread = threading.Thread(
            target=other.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        thread.start()
        try:
            self.assertNotEqual(other.studio_token, self.server.studio_token)
            status, body = self.call(
                "POST",
                "/api/prepare",
                {"request": self.request},
                server=other,
                token=self.server.studio_token,
            )
            self.assertEqual(status, 403, body)
            self.assertEqual(body["error"]["code"], "invalid_token")
            status, body = self.call(
                "POST", "/api/prepare", {"request": self.request}, server=other
            )
            self.assertEqual(status, 200, body)
        finally:
            other.shutdown()
            other.server_close()
            thread.join(timeout=2)

    def test_string_import_rejects_duplicate_request_keys(self):
        source = json.dumps(self.request)
        self.assertIn('"max_length": null', source)
        ambiguous = source.replace(
            '"max_length": null', '"max_length": 1, "max_length": 100', 1
        )
        for path in ("/api/prepare", "/api/compile"):
            with self.subTest(path=path):
                status, body = self.call("POST", path, {"request_json": ambiguous})
                self.assertEqual(status, 400, body)
                self.assertFalse(body["ok"])
                self.assertIn("Duplicate JSON key", body["error"]["message"])
                self.assertNotIn("result", body)

    def test_string_transport_preserves_integer_beyond_javascript_precision(self):
        imported = deepcopy(self.request)
        maximum = 9_007_199_254_740_993
        imported["constraints"]["max_length"] = maximum
        status, prepared = self.call(
            "POST", "/api/prepare", {"request_json": json.dumps(imported)}
        )
        self.assertEqual(status, 200, prepared)
        request_json = prepared["result"]["request_json"]
        self.assertEqual(json.loads(request_json), imported)
        self.assertEqual(
            json.loads(prepared["result"]["overview"]["constraints_json"])[
                "max_length"
            ],
            maximum,
        )
        status, compiled = self.call(
            "POST", "/api/compile", {"request_json": request_json}
        )
        self.assertEqual(status, 200, compiled)
        result = compiled["result"]
        self.assertEqual(json.loads(result["request_json"]), imported)
        self.assertEqual(
            json.loads(result["record_json"])["request"]["constraints"]["max_length"],
            maximum,
        )
        for kind in ("request", "build", "fasta"):
            with self.subTest(format=kind):
                status, exported = self.call(
                    "POST",
                    "/api/export",
                    {
                        "request_json": result["request_json"],
                        "record_json": result["record_json"],
                        "format": kind,
                    },
                )
                self.assertEqual(status, 200, exported)
                content = exported["result"]["content"]
                if kind == "fasta":
                    self.assertIn(self.record["molecule"]["sequence"], content)
                else:
                    document = json.loads(content)
                    authority = document if kind == "request" else document["request"]
                    self.assertEqual(authority, imported)


if __name__ == "__main__":
    unittest.main()

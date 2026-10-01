"""HTTP boundaries protect the real compiler service on loopback only."""

from http.client import HTTPConnection
import json
from threading import Thread
import unittest

from biocompiler.studio.server import MAX_BODY_BYTES, create_server


class StudioServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(port=0)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, method="GET", path="/api/session", body=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def headers(self):
        return {
            "Origin": self.server.studio_origin,
            "X-Biocompiler-Token": self.server.studio_token,
            "Content-Type": "application/json",
        }

    def test_session_loopback_security_headers_and_real_build(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        status, headers, content = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        session = json.loads(content)["result"]
        self.assertEqual(session["token"], self.server.studio_token)
        status, _, content = self.request(
            "POST",
            "/api/compile",
            json.dumps({"request": session["example"]["request"]}),
            self.headers(),
        )
        self.assertEqual(status, 200)
        result = json.loads(content)["result"]
        self.assertEqual(result["summary"]["sequence"], "GGAUGGCUUAACCAAAA")
        self.assertEqual(result["summary"]["therapeutic_implementation"], "partial")

    def test_host_origin_and_token_rejections(self):
        for host in (
            "example.org",
            "localhost:" + str(self.server.server_port),
            "127.0.0.1:1",
            self.server.studio_host + ".evil",
        ):
            status, headers, content = self.request(headers={"Host": host})
            self.assertEqual(status, 403)
            self.assertFalse(json.loads(content)["ok"])
            self.assertNotIn("Access-Control-Allow-Origin", headers)
        for key, value in (
            ("Origin", "https://evil.invalid"),
            ("Origin", "null"),
            ("X-Biocompiler-Token", "other"),
            ("X-Biocompiler-Token", "é"),
        ):
            headers = self.headers() | {key: value}
            status, _, content = self.request("POST", "/api/prepare", "{}", headers)
            self.assertEqual(status, 403)
            self.assertFalse(json.loads(content)["ok"])
        for key in ("Origin", "X-Biocompiler-Token"):
            headers = self.headers()
            del headers[key]
            status, _, _ = self.request("POST", "/api/prepare", "{}", headers)
            self.assertEqual(status, 400)
        self.assertEqual(self.request(headers={"Sec-Fetch-Site": "cross-site"})[0], 403)

    def test_json_type_duplicate_keys_depth_and_size_boundaries(self):
        headers = self.headers()
        self.assertEqual(
            self.request(
                "POST", "/api/prepare", "{}", headers | {"Content-Type": "text/plain"}
            )[0],
            415,
        )
        for body in (
            b"\xff",
            b'{"request":{},"request":{}}',
            b'{"x":NaN}',
            b"[]",
            b"{broken",
            ("[" * 70 + "]" * 70).encode(),
            b'{"x":"\\ud800"}',
        ):
            with self.subTest(body=body[:30]):
                status, _, content = self.request("POST", "/api/prepare", body, headers)
                self.assertEqual(status, 400)
                error = json.loads(content)["error"]
                self.assertNotIn("Traceback", error["message"])
        status, _, content = self.request(
            "POST",
            "/api/prepare",
            b"",
            headers | {"Content-Length": str(MAX_BODY_BYTES + 1)},
        )
        self.assertEqual(status, 413)
        self.assertEqual(json.loads(content)["error"]["code"], "body_too_large")
        self.assertEqual(
            self.request(
                "POST", "/api/prepare", "{}", headers | {"Transfer-Encoding": "chunked"}
            )[0],
            400,
        )

    def test_only_allowlisted_routes_and_no_path_api(self):
        for path in (
            "/../data/example-request.json",
            "/%2e%2e/data/example-request.json",
            "/data/example-request.json",
            "/api/session?token=other",
            "/favicon.ico",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.request(path=path)[0], 404)
        self.assertEqual(
            self.request("POST", "/api/read-file", "{}", self.headers())[0], 404
        )
        self.assertEqual(self.request("OPTIONS", "/api/compile")[0], 501)
        self.assertEqual(self.request("PUT", "/api/compile")[0], 501)
        for port in (True, -1, 65536, "8765"):
            with self.assertRaises(ValueError):
                create_server(port)

    def test_duplicate_headers_are_rejected(self):
        for duplicate in ("Host", "Origin", "Content-Length", "X-Biocompiler-Token"):
            connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
            try:
                connection.putrequest("POST", "/api/prepare", skip_host=True)
                headers = self.headers() | {
                    "Host": self.server.studio_host,
                    "Content-Length": "2",
                }
                for key, value in headers.items():
                    connection.putheader(key, value)
                    if key == duplicate:
                        connection.putheader(key, value)
                connection.endheaders(b"{}")
                response = connection.getresponse()
                self.assertEqual(response.status, 400)
                self.assertEqual(
                    json.loads(response.read())["error"]["code"], "invalid_headers"
                )
            finally:
                connection.close()

    def test_construction_routes_retain_session_guards_and_static_policy(self):
        for path in ("/construction", "/construction.css", "/construction.js"):
            status, headers, content = self.request(path=path)
            self.assertEqual(status, 200)
            self.assertTrue(content)
            self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        for path in ("/api/construction/inspect", "/api/construction/save"):
            for override in (
                {"Origin": "https://evil.invalid"},
                {"X-Biocompiler-Token": "wrong"},
                {"Host": "example.org"},
            ):
                status, _, content = self.request(
                    "POST", path, "{}", self.headers() | override
                )
                self.assertEqual(status, 403)
                self.assertFalse(json.loads(content)["ok"])
            status, _, content = self.request("POST", path, "{}", self.headers())
            self.assertEqual(status, 400)
            self.assertNotIn("Traceback", json.loads(content)["error"]["message"])


if __name__ == "__main__":
    unittest.main()

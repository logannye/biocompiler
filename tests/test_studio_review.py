"""Studio reviews current software authority without admitting biological claims."""

from dataclasses import replace
from http.client import HTTPConnection
import json
from threading import Thread
import unittest
from unittest.mock import patch

from examples.circuit_infrastructure import make_infrastructure_requests
from examples.circuit_sources import make_source_inventory
from biocompiler.compiler.circuit_construction import build_circuit_construction
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_sources import CircuitSourceInventory
from biocompiler.studio import construction
from biocompiler.studio.server import create_server
from biocompiler.verification.circuit_evidence import capture_circuit_evidence


class StudioReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request, cls.bindings, cls.evidence = make_infrastructure_requests()
        cls.build = build_circuit_construction(cls.request)
        cls.receipt = capture_circuit_evidence(cls.build, expected_request=cls.evidence)
        cls.inventory = make_source_inventory()

    def payload(self, *, saving=False):
        result = {
            "build_json": self.build.to_json() + "\r\n",
            "expected_request_json": self.request.to_json(),
            "review": {
                "source_inventory_json": self.inventory.to_json(),
                "binding_request_json": self.bindings.to_json(),
                "evidence_request_json": self.evidence.to_json(),
                "evidence_receipt_json": self.receipt.to_json(),
            },
        }
        if saving:
            result["expected_build_fingerprint"] = self.build.fingerprint
        return result

    def test_complete_review_runs_independent_checks_and_keeps_tracks_separate(self):
        with patch(
            "biocompiler.compiler.circuit_construction.construct_circuit_candidate",
            side_effect=AssertionError("Inspection must not use the producer"),
        ):
            report = construction.inspect(self.payload())
        review = report["review"]
        self.assertEqual(review["sources"]["readiness"]["metadata_consistency"], "pass")
        self.assertEqual(
            review["sources"]["readiness"]["cases"][0]["missing_field_count"], 9
        )
        self.assertEqual(review["sources"]["build_correspondence"], "not_established")
        self.assertEqual(review["bindings"]["assessment"]["outcome"], "pass")
        self.assertEqual(review["evidence"]["status"], "current")
        self.assertTrue(
            all(
                row["status"] == "current" for row in review["evidence"]["dependencies"]
            )
        )
        self.assertEqual(
            review["acceptance"],
            {
                "software": "individual_check_results_only",
                "reviewed_reference_correspondence": "not_established",
                "human_biological_applicability": "unassessed",
                "human_therapeutic_admission": "not_admitted",
                "prediction": "unsupported",
            },
        )

    def test_binding_or_evidence_requests_supply_complete_external_authority(self):
        for key in ("binding_request_json", "evidence_request_json"):
            payload = self.payload()
            payload["expected_request_json"] = None
            payload["review"] = dict.fromkeys(payload["review"]) | {
                key: payload["review"][key]
            }
            report = construction.inspect(payload)
            self.assertEqual(
                report["freshness"]["status"], "replayed_external_authority"
            )
            self.assertEqual(
                report["review"]["authority_sources"], [key.removesuffix("_json")]
            )

    def test_missing_review_records_and_counterparts_are_explicit(self):
        payload = self.payload()
        payload["expected_request_json"] = None
        payload["review"] = dict.fromkeys(payload["review"])
        report = construction.inspect(payload)
        self.assertEqual(report["freshness"]["status"], "not_replayed")
        self.assertEqual(report["review"]["sources"]["status"], "missing_inventory")
        self.assertEqual(report["review"]["bindings"]["status"], "missing_authority")
        self.assertEqual(report["review"]["evidence"]["status"], "missing_authority")
        payload["review"]["evidence_receipt_json"] = self.receipt.to_json()
        self.assertEqual(
            construction.inspect(payload)["review"]["evidence"]["status"],
            "missing_authority",
        )
        payload["review"]["evidence_receipt_json"] = None
        payload["review"]["evidence_request_json"] = self.evidence.to_json()
        self.assertEqual(
            construction.inspect(payload)["review"]["evidence"]["status"],
            "missing_receipt",
        )

    def test_disagreeing_authorities_reject_inspection_and_save(self):
        for key, request in (
            ("binding_request_json", self.bindings),
            ("evidence_request_json", self.evidence),
        ):
            changed = replace(
                request, construction=replace(self.request, mode="diagnostic")
            )
            for method, saving in (
                (construction.inspect, False),
                (construction.save, True),
            ):
                payload = self.payload(saving=saving)
                payload["review"][key] = changed.to_json()
                with (
                    self.subTest(key=key, saving=saving),
                    self.assertRaisesRegex(
                        SerializationError, "independent complete authority"
                    ),
                ):
                    method(payload)

    def test_failed_binding_diagnostics_are_preserved_when_saving_history(self):
        payload = self.payload(saving=True)
        payload["review"]["binding_request_json"] = replace(
            self.bindings, bindings=()
        ).to_json()
        report = construction.save(payload)
        self.assertEqual(report["review"]["bindings"]["assessment"]["outcome"], "fail")
        self.assertTrue(report["review"]["bindings"]["assessment"]["diagnostics"])
        self.assertEqual(report["build_json"], payload["build_json"])
        self.assertEqual(
            report["claims"]["human_therapeutic_admission"], "not_admitted"
        )

    def test_changed_evidence_and_source_review_are_freshly_checked_on_save(self):
        payload = self.payload(saving=True)
        payload["review"]["evidence_request_json"] = replace(
            self.evidence, sources=(replace(self.evidence.sources[0], version="2"),)
        ).to_json()
        payload["review"]["source_inventory_json"] = replace(
            self.inventory,
            cases=(replace(self.inventory.cases[0], label="Edited case"),),
        ).to_json()
        report = construction.save(payload)["review"]
        self.assertEqual(report["evidence"]["status"], "stale")
        self.assertEqual(report["sources"]["readiness"]["metadata_consistency"], "fail")
        self.assertTrue(report["sources"]["readiness"]["diagnostics"])

    def test_observation_and_model_uses_remain_distinct_without_predictions(self):
        sources = tuple(
            replace(self.evidence.sources[0], id=kind + "-" + use, kind=kind, use=use)
            for kind, use in (
                ("observation", "calibration"),
                ("observation", "held_out"),
                ("model", "prediction"),
            )
        )
        payload = self.payload()
        payload["review"]["evidence_request_json"] = replace(
            self.evidence, sources=sources
        ).to_json()
        review = construction.inspect(payload)["review"]
        self.assertEqual(
            {(item["kind"], item["use"]) for item in review["evidence"]["sources"]},
            {
                ("observation", "calibration"),
                ("observation", "held_out"),
                ("model", "prediction"),
            },
        )
        self.assertEqual(review["evidence"]["status"], "missing")
        self.assertEqual(review["evidence"]["assessment"]["prediction"], "unsupported")
        self.assertEqual(
            review["evidence"]["assessment"]["empirical_validation"], "unknown"
        )

    def test_empty_inventory_is_not_a_case_and_sources_do_not_supply_build_authority(
        self,
    ):
        payload = self.payload()
        payload["expected_request_json"] = None
        payload["review"] = dict.fromkeys(payload["review"])
        payload["review"]["source_inventory_json"] = CircuitSourceInventory(
            "empty", "1", (), (), ()
        ).to_json()
        report = construction.inspect(payload)
        self.assertEqual(report["freshness"]["status"], "not_replayed")
        self.assertEqual(
            report["review"]["sources"]["readiness"]["case_inventory_status"], "missing"
        )
        self.assertEqual(report["review"]["sources"]["readiness"]["cases"], [])

    def test_strict_review_fields_and_malformed_inputs_are_rejected(self):
        for review in (None, [], {}, {"surprise": True}):
            with self.subTest(review=review), self.assertRaises(SerializationError):
                construction.inspect(self.payload() | {"review": review})
        for key in self.payload()["review"]:
            for value in ({}, "{broken", " ", '{"x":NaN}', "\ud800"):
                payload = self.payload()
                payload["review"][key] = value
                with (
                    self.subTest(key=key, value=value),
                    self.assertRaises(SerializationError),
                ):
                    construction.inspect(payload)


class StudioReviewHTTPTests(unittest.TestCase):
    """Exercise real HTTP serialization and the existing session protections."""

    payload = StudioReviewTests.payload

    @classmethod
    def setUpClass(cls):
        StudioReviewTests.setUpClass.__func__(cls)
        cls.server = create_server(port=0)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_http_review_and_save_apply_current_checks_and_strict_transport(self):
        headers = {
            "Origin": self.server.studio_origin,
            "X-Biocompiler-Token": self.server.studio_token,
            "Content-Type": "application/json",
        }
        for route, saving in (("inspect", False), ("save", True)):
            connection = HTTPConnection(
                "127.0.0.1", self.server.server_port, timeout=60
            )
            try:
                payload = self.payload(saving=saving)
                payload["review"]["evidence_request_json"] = None
                connection.request(
                    "POST", "/api/construction/" + route, json.dumps(payload), headers
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                result = json.loads(response.read())["result"]
                self.assertEqual(
                    result["review"]["evidence"]["status"], "missing_authority"
                )
                self.assertEqual(
                    result["review"]["bindings"]["assessment"]["outcome"], "pass"
                )
                connection.request(
                    "POST",
                    "/api/construction/" + route,
                    json.dumps(
                        payload | {"review": {"url": "https://example.invalid"}}
                    ),
                    headers,
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 400)
                self.assertNotIn(
                    "Traceback", json.loads(response.read())["error"]["message"]
                )
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()

"""Real guided compilation preserves authority, scope and portable fixture data."""

from copy import deepcopy
from dataclasses import replace
from importlib import resources
import json

import unittest

from biocompiler.compiler.candidate import verify_candidate_build
from biocompiler.errors import SerializationError
from biocompiler.ir.candidate import CandidateRequest
from biocompiler.ir.candidate_build import CandidateBuildRecord
from biocompiler.studio import service


class StudioServiceTests(unittest.TestCase):
    def prepare(self, product="declared_product", architecture="auto", max_length=None):
        return service.prepare(
            {
                "example": {
                    "product": product,
                    "architecture": architecture,
                    "max_length": max_length,
                }
            }
        )

    def test_packaged_example_is_portable_exact_and_not_dependent_on_example_imports(
        self,
    ):
        request = service.example_request()
        packaged = (
            resources.files("biocompiler.studio")
            .joinpath("data", "example-request.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(CandidateRequest.from_json(packaged), request)
        for node in request.build_request.intent.nodes:
            self.assertEqual(node.source.file, "examples/human_behavior.py")
            self.assertGreater(node.source.line, 0)
            self.assertEqual(node.source.function, "make_human_behavior")
        session = service.session("test-token")
        self.assertEqual(session["token"], "test-token")
        self.assertTrue(session["example"]["overview"]["fixture"])
        self.assertEqual(session["example"]["request"], request.to_dict())
        self.assertIn(
            "declared_cue.high()", session["example"]["overview"]["source_summary"]
        )

    def test_four_real_compilation_scenarios(self):
        cases = (
            ({}, "GGAUGGCUUAACCAAAA", "MA*", "compact"),
            ({"product": "alternative_product"}, "GGAUGUUUUAACCAAAA", "MF*", "compact"),
            ({"architecture": "extended"}, "GGGGAUGGCUUAACCAAAA", "MA*", "extended"),
            ({"max_length": 1}, None, None, None),
        )
        for controls, sequence, protein, architecture in cases:
            with self.subTest(controls=controls):
                prepared = self.prepare(**controls)
                result = service.compile_request({"request": prepared["request"]})
                request = CandidateRequest.from_dict(result["request"])
                record = CandidateBuildRecord.from_dict(result["record"])
                self.assertEqual(
                    verify_candidate_build(record, expected_request=request), record
                )
                summary = result["summary"]
                self.assertEqual(summary["sequence"], sequence)
                self.assertEqual(summary["protein"], protein)
                self.assertEqual(summary["architecture"], architecture)
                self.assertEqual(
                    summary["length_nt"], len(sequence) if sequence else None
                )
                self.assertEqual(summary["therapeutic_implementation"], "partial")
                self.assertEqual(summary["human_therapeutic_admission"], "not_admitted")
                self.assertEqual(summary["scope"], "product_cassette_structure")
                self.assertEqual(len(summary["unresolved"]), 22)
                self.assertTrue(
                    all(item["outcome"] == "pass" for item in summary["checks"])
                )
                self.assertEqual(len(summary["alternatives"]), 2)
                if sequence:
                    self.assertEqual(
                        "".join(item["sequence"] for item in summary["parts"]), sequence
                    )
                    self.assertEqual(summary["parts"][0]["start"], 0)
                    self.assertEqual(summary["parts"][-1]["end"], len(sequence))
                else:
                    self.assertEqual(summary["status"], "no_candidate_found")
                    self.assertEqual(summary["parts"], [])
                    self.assertTrue(
                        all(
                            item["rejections"][0]["code"] == "max_length_exceeded"
                            for item in summary["alternatives"]
                        )
                    )
                    self.assertEqual(
                        [item["stage"] for item in summary["checks"]],
                        ["requirements", "selection"],
                    )

    def test_import_preserves_original_source_and_does_not_guess_fixture_from_library_id(
        self,
    ):
        original = service.example_request().to_dict()

        def change_locations(value):
            if isinstance(value, dict):
                if set(value) == {"file", "line", "function"}:
                    value["file"] = "/user/chosen/source.py"
                    value["line"] = 87
                for item in value.values():
                    change_locations(item)
            elif isinstance(value, list):
                for item in value:
                    change_locations(item)

        change_locations(original)
        prepared = service.prepare({"request": original})
        self.assertEqual(prepared["request"], original)
        self.assertFalse(prepared["overview"]["fixture"])
        result = service.compile_request({"request": original})
        self.assertEqual(result["request"], original)
        self.assertEqual(result["record"]["request"], original)
        changed_library = replace(
            service.example_request(),
            library=replace(service.example_request().library, version="another"),
        )
        self.assertFalse(service.overview(changed_library)["fixture"])

    def test_exports_are_parseable_and_no_candidate_has_no_fasta(self):
        prepared = self.prepare()
        result = service.compile_request({"request": prepared["request"]})
        for kind in ("fasta", "build", "request"):
            output = service.export(
                {
                    "request": result["request"],
                    "record": result["record"],
                    "format": kind,
                }
            )
            self.assertNotIn("/", output["filename"])
            if kind == "fasta":
                self.assertEqual(
                    "".join(output["content"].splitlines()[1:]),
                    result["summary"]["sequence"],
                )
                self.assertIn("therapeutic_implementation=partial", output["content"])
            else:
                self.assertEqual(
                    json.loads(output["content"]),
                    result["record" if kind == "build" else "request"],
                )
        exhausted = service.compile_request(
            {"request": self.prepare(max_length=1)["request"]}
        )
        with self.assertRaisesRegex(SerializationError, "No molecular candidate"):
            service.export(
                {
                    "request": exhausted["request"],
                    "record": exhausted["record"],
                    "format": "fasta",
                }
            )
        self.assertEqual(
            json.loads(
                service.export(
                    {
                        "request": exhausted["request"],
                        "record": exhausted["record"],
                        "format": "build",
                    }
                )["content"]
            )["status"],
            "no_candidate_found",
        )

    def test_strict_controls_envelopes_and_work_bounds(self):
        for change in (
            {"max_length": True},
            {"max_length": -1},
            {"max_length": 1.5},
            {"product": "invented"},
            {"product": []},
            {"architecture": "unknown"},
            {"architecture": []},
        ):
            with self.subTest(change=change), self.assertRaises(SerializationError):
                self.prepare(**change)
        for payload in (
            {},
            {"example": {}},
            {"request": service.example_request().to_dict(), "example": {}},
            {"path": "/tmp/request.json"},
        ):
            with (
                self.subTest(payload_keys=tuple(payload)),
                self.assertRaises(SerializationError),
            ):
                service.prepare(payload)
        too_many_nodes = service.example_request().to_dict()
        too_many_nodes["nodes"] = [{}] * (service.MAX_SOURCE_NODES + 1)
        with self.assertRaisesRegex(SerializationError, "source nodes"):
            service.prepare({"request": too_many_nodes})
        too_many_bases = service.example_request().to_dict()
        too_many_bases["library"]["parts"][0]["fragment"]["sequence"] = "A" * (
            service.MAX_LIBRARY_BASES + 1
        )
        with self.assertRaisesRegex(SerializationError, "nucleotide symbols"):
            service.compile_request({"request": too_many_bases})
        deep = []
        for _ in range(service.MAX_JSON_DEPTH + 1):
            deep = [deep]
        with self.assertRaisesRegex(SerializationError, "nesting"):
            service.bounded_document(deep)

    def test_stale_saved_checks_do_not_authorize_any_download(self):
        result = service.compile_request({"request": self.prepare()["request"]})
        for key in ("checks", "tool_versions"):
            record = deepcopy(result["record"])
            record[key] = {}
            for kind in ("request", "build", "fasta"):
                with (
                    self.subTest(key=key, kind=kind),
                    self.assertRaises(SerializationError),
                ):
                    service.export(
                        {"request": result["request"], "record": record, "format": kind}
                    )

    def test_json_text_preserves_float_and_large_integer_authority_through_export(self):
        base = service.example_request()
        precise_limit = replace(
            base, constraints=replace(base.constraints, max_length=9007199254740993)
        )
        display = service.prepare({"request_json": precise_limit.to_json()})["overview"]
        self.assertIn('"max_length": 9007199254740993', display["constraints_json"])
        self.assertEqual(
            json.loads(display["constraints_json"]), display["constraints"]
        )
        build = replace(
            base.build_request,
            provenance=replace(
                base.build_request.provenance,
                external_inputs={
                    "float": 1.0,
                    "negative_zero": -0.0,
                    "large_integer": 9007199254740993,
                },
            ),
        )
        request = replace(base, source=build)
        prepared = service.prepare({"request_json": request.to_json()})
        self.assertEqual(prepared["request_json"], request.to_json())
        result = service.compile_request({"request_json": prepared["request_json"]})
        self.assertEqual(
            CandidateRequest.from_json(result["request_json"]).fingerprint,
            request.fingerprint,
        )
        record = CandidateBuildRecord.from_json(result["record_json"])
        self.assertEqual(record.request.fingerprint, request.fingerprint)
        for kind in ("request", "build", "fasta"):
            output = service.export(
                {
                    "request_json": result["request_json"],
                    "record_json": result["record_json"],
                    "format": kind,
                }
            )
            if kind == "request":
                self.assertEqual(output["content"], request.to_json() + "\n")
                values = json.loads(output["content"])["source"]["provenance"][
                    "external_inputs"
                ]
                self.assertIs(type(values["float"]), float)
                self.assertIs(type(values["large_integer"]), int)
                self.assertEqual(values["large_integer"], 9007199254740993)
                self.assertIn('"negative_zero": -0.0', output["content"])
            elif kind == "build":
                self.assertEqual(
                    CandidateBuildRecord.from_json(output["content"]).fingerprint,
                    record.fingerprint,
                )

    def test_json_text_envelopes_reject_duplicates_mixed_authority_and_bad_types(self):
        prepared = self.prepare()
        result = service.compile_request({"request_json": prepared["request_json"]})
        duplicate = prepared["request_json"].replace(
            '"max_length": null', '"max_length": null, "max_length": 1', 1
        )
        for operation in (service.prepare, service.compile_request):
            with self.assertRaisesRegex(SerializationError, "Duplicate JSON key"):
                operation({"request_json": duplicate})
            with self.assertRaises(SerializationError):
                operation(
                    {
                        "request": prepared["request"],
                        "request_json": prepared["request_json"],
                    }
                )
            for invalid in (None, {}, 1):
                with self.assertRaises(SerializationError):
                    operation({"request_json": invalid})
        for patch in (
            {"request": prepared["request"], "record_json": result["record_json"]},
            {"request_json": prepared["request_json"], "record": result["record"]},
            {
                "request_json": prepared["request_json"],
                "record_json": result["record_json"],
                "request": prepared["request"],
            },
            {"request_json": prepared["request_json"], "record_json": {}},
        ):
            with self.assertRaises(SerializationError):
                service.export(patch | {"format": "build"})
        duplicate_record = result["record_json"].replace(
            '"status": "candidate_generated"',
            '"status": "candidate_generated", "status": "candidate_generated"',
            1,
        )
        with self.assertRaisesRegex(SerializationError, "Duplicate JSON key"):
            service.export(
                {
                    "request_json": prepared["request_json"],
                    "record_json": duplicate_record,
                    "format": "build",
                }
            )

    def test_json_text_bounds_are_checked_before_artifact_import(self):
        for value, message in (
            ("[" * 70 + "]" * 70, "nesting"),
            (
                json.dumps({"nodes": [{}] * (service.MAX_SOURCE_NODES + 1)}),
                "source nodes",
            ),
            (" " * (service.MAX_JSON_TEXT_BYTES + 1), "size limit"),
        ):
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(SerializationError, message),
            ):
                service.prepare({"request_json": value})
        document = service.example_request().to_dict()
        document["library"]["parts"][0]["fragment"]["sequence"] = "A" * (
            service.MAX_LIBRARY_BASES + 1
        )
        with self.assertRaisesRegex(SerializationError, "nucleotide symbols"):
            service.compile_request({"request_json": json.dumps(document)})


if __name__ == "__main__":
    unittest.main()

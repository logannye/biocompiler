"""Studio keeps raw historical construction JSON and fresh authority separate."""

from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from biocompiler.artifacts.circuit_construction_build import CircuitConstructionBuild
from biocompiler.compiler.circuit_construction import build_circuit_construction
from biocompiler.errors import SerializationError
from biocompiler.studio import construction, service
from test_circuit_construction_checking import fixture_request
from test_circuit_inspection import amount_request, forged_build


class StudioConstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = fixture_request()
        cls.build = build_circuit_construction(cls.request)

    def payload(self, *, build=None, authority=None, saving=False):
        build = self.build if build is None else build
        payload = {
            "build_json": build.to_json() + "\n",
            "expected_request_json": None if authority is None else authority.to_json(),
        }
        if saving:
            payload["expected_build_fingerprint"] = build.fingerprint
        return payload

    def test_save_and_reopen_preserve_exact_raw_json_and_historical_scope(self):
        payload = self.payload(saving=True)
        raw = (
            " \n"
            + json.dumps(self.build.to_dict(), indent=4, ensure_ascii=False)
            + "\n\t"
        )
        payload["build_json"] = raw
        report = construction.inspect(
            {
                key: value
                for key, value in payload.items()
                if key != "expected_build_fingerprint"
            }
        )
        self.assertEqual(report["build_fingerprint"], self.build.fingerprint)
        saved = construction.save(payload)
        self.assertEqual(saved["build_json"], raw)
        self.assertEqual(saved["freshness"]["status"], "not_replayed")
        self.assertEqual(saved["claims"]["human_therapeutic_admission"], "not_admitted")
        reopened = construction.inspect(
            {"build_json": saved["build_json"], "expected_request_json": None}
        )
        self.assertEqual(reopened, report)
        self.assertEqual(
            CircuitConstructionBuild.from_json(saved["build_json"]), self.build
        )

    def test_optional_external_replay_uses_checker_without_constructing(self):
        with patch(
            "biocompiler.compiler.circuit_construction.construct_circuit_candidate",
            side_effect=AssertionError("Read-only Studio must not construct"),
        ):
            report = construction.inspect(self.payload(authority=self.request))
            saved = construction.save(self.payload(authority=self.request, saving=True))
        self.assertEqual(report["freshness"]["status"], "replayed_external_authority")
        self.assertEqual(saved["freshness"]["assessment"]["outcome"], "pass")

    def test_historical_forged_pass_is_inspectable_but_fresh_authority_rejects_it(self):
        forged = forged_build(self.build)
        report = construction.inspect(self.payload(build=forged))
        self.assertEqual(report["stored_assessment"]["outcome"], "pass")
        self.assertEqual(report["freshness"]["status"], "not_replayed")
        self.assertEqual(
            construction.save(self.payload(build=forged, saving=True))["freshness"][
                "status"
            ],
            "not_replayed",
        )
        for function, saving in (
            (construction.inspect, False),
            (construction.save, True),
        ):
            with self.assertRaisesRegex(SerializationError, "fresh complete replay"):
                function(
                    self.payload(build=forged, authority=self.request, saving=saving)
                )

    def test_stale_build_fingerprint_refuses_save(self):
        payload = self.payload(saving=True)
        payload["build_json"] = forged_build(self.build).to_json()
        with self.assertRaisesRegex(SerializationError, "changed since inspection"):
            construction.save(payload)
        for identity in (None, True, 1, {}, "bad-digest", "a" * 64):
            with self.subTest(identity=identity), self.assertRaises(SerializationError):
                construction.save(
                    self.payload(saving=True) | {"expected_build_fingerprint": identity}
                )

    def test_changed_external_authority_refuses_inspection_and_save(self):
        changed = replace(self.request, mode="diagnostic")
        for function, saving in (
            (construction.inspect, False),
            (construction.save, True),
        ):
            with self.assertRaisesRegex(
                SerializationError, "independent complete authority"
            ):
                function(self.payload(authority=changed, saving=saving))

    def test_partial_and_diagnostic_records_can_be_saved_as_historical_records(self):
        for request in (
            replace(self.request, payload_structures=()),
            replace(self.request, mode="diagnostic"),
        ):
            build = build_circuit_construction(request)
            saved = construction.save(
                self.payload(build=build, authority=request, saving=True)
            )
            self.assertEqual(
                CircuitConstructionBuild.from_json(saved["build_json"]), build
            )
            self.assertEqual(
                saved["freshness"]["assessment"]["outcome"],
                build.assessment.outcome.value,
            )
            self.assertEqual(saved["claims"]["source_fidelity"], "unestablished")

    def test_raw_number_types_and_large_integers_survive_save_reopen(self):
        for quantity in (1, 1.0, 2**53 + 1):
            request = amount_request(quantity)
            build = build_circuit_construction(request)
            payload = self.payload(build=build, authority=request, saving=True)
            saved = construction.save(payload)
            self.assertEqual(saved["build_json"], payload["build_json"])
            restored = CircuitConstructionBuild.from_json(saved["build_json"])
            amount = restored.request.amounts[0].quantity
            self.assertEqual(type(amount), type(quantity))
            self.assertEqual(amount, quantity)
            self.assertEqual(saved["build_fingerprint"], build.fingerprint)

    def test_unknown_or_missing_transport_fields_and_unparsed_objects_are_rejected(
        self,
    ):
        for function, saving in (
            (construction.inspect, False),
            (construction.save, True),
        ):
            payload = self.payload(saving=saving)
            for key in payload:
                changed = dict(payload)
                del changed[key]
                with self.subTest(missing=key), self.assertRaises(SerializationError):
                    function(changed)
            with self.assertRaises(SerializationError):
                function(payload | {"surprise": True})
            for key in ("build_json", "expected_request_json"):
                with self.subTest(field=key), self.assertRaises(SerializationError):
                    function(payload | {key: self.build.to_dict()})
            for invalid in (None, [], "raw-text"):
                with self.assertRaises(SerializationError):
                    function(invalid)

    def test_raw_byte_limits_precede_artifact_decoding(self):
        payload = self.payload()
        with (
            patch.object(service, "MAX_JSON_TEXT_BYTES", 32),
            patch.object(
                CircuitConstructionBuild,
                "from_dict",
                side_effect=AssertionError("Decoded before raw byte preflight"),
            ) as decoder,
        ):
            with self.assertRaisesRegex(SerializationError, "size limit"):
                construction.inspect(payload)
            decoder.assert_not_called()

    def test_duplicate_fields_nonfinite_values_unknown_schema_and_unicode_fail(self):
        documents = (
            self.build.to_json()[:-1] + ', "request": null}',
            '{"value": NaN}',
            '{"schema_version": "unknown"}',
            '{"extra": true}',
            "\ud800",
            " ",
        )
        for text in documents:
            with self.subTest(text=text[:40]), self.assertRaises(SerializationError):
                construction.inspect(self.payload() | {"build_json": text})
        document = self.build.to_dict()
        document["request"]["surprise"] = "not allowed"
        with self.assertRaises(SerializationError):
            construction.inspect(self.payload() | {"build_json": json.dumps(document)})

    def test_deep_raw_json_is_rejected_before_build_decoding(self):
        nested = "null"
        for _ in range(service.MAX_JSON_DEPTH + 2):
            nested = "[" + nested + "]"
        with patch.object(
            CircuitConstructionBuild,
            "from_dict",
            side_effect=AssertionError("Decoded before depth check"),
        ) as decoder:
            with self.assertRaisesRegex(SerializationError, "nesting"):
                construction.inspect(self.payload() | {"build_json": nested})
            decoder.assert_not_called()


if __name__ == "__main__":
    unittest.main()

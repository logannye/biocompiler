"""Historical structural views expose edits without becoming acceptance authority."""

from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from biocompiler.artifacts.circuit_construction_build import CircuitConstructionBuild
from biocompiler.artifacts import circuit_inspection as inspection
from biocompiler.compiler.circuit_construction import build_circuit_construction
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_construction import AmountDeclaration, SliceOperation
from biocompiler.verification.circuit_construction import check_circuit_construction
from examples.circuit_molecules import fixture_provenance
from test_circuit_construction_checking import fixture_request, selection


def forged_build(build):
    value = replace(build.candidate.values[0], sequence="CCCCCC")
    candidate = replace(build.candidate, values=(value,))
    assessment = replace(
        build.assessment,
        candidate_fingerprint=candidate.fingerprint,
        reconstructed_fingerprint=candidate.fingerprint,
    )
    return replace(build, candidate=candidate, assessment=assessment)


def amount_request(quantity):
    request = fixture_request()
    return replace(
        request,
        amounts=(
            AmountDeclaration(
                "amount",
                "payload",
                "preparation",
                ("payload_role",),
                quantity,
                "arbitrary_fixture_unit",
                fixture_provenance("amount"),
            ),
        ),
    )


class CircuitInspectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = fixture_request()
        cls.build = build_circuit_construction(cls.request)

    def diff(self, request, **options):
        return inspection.diff_circuit_constructions(
            self.build, build_circuit_construction(request), **options
        )

    def test_historical_inspection_is_detached_and_never_calls_producer_or_checker(
        self,
    ):
        with (
            patch(
                "biocompiler.compiler.circuit_construction.verify_circuit_construction",
                side_effect=AssertionError("Historical inspection must not replay"),
            ),
            patch(
                "biocompiler.compiler.circuit_construction.construct_circuit_candidate",
                side_effect=AssertionError("Inspection must not construct"),
            ),
        ):
            report = inspection.inspect_circuit_construction(self.build)
            unchanged = inspection.diff_circuit_constructions(self.build, self.build)
        self.assertEqual(
            report["freshness"], {"status": "not_replayed", "assessment": None}
        )
        self.assertEqual(report["stored_assessment"]["outcome"], "pass")
        self.assertTrue(unchanged["identical_content"])
        self.assertEqual(unchanged["total_changes"], 0)
        for records in (report["roots"], report["values"], report["molecules"]):
            for record in records:
                molecule = record.get("molecule", record)
                self.assertNotIn("sequence", molecule)
                self.assertIn("spelling_fingerprint", molecule)
        report["request"]["required_members"].clear()
        self.assertTrue(
            inspection.inspect_circuit_construction(self.build)["request"][
                "required_members"
            ]
        )

    def test_rehashed_historical_pass_is_visible_but_fresh_replay_rejects_it(self):
        forged = forged_build(self.build)
        report = inspection.inspect_circuit_construction(forged)
        self.assertEqual(report["stored_assessment"]["outcome"], "pass")
        self.assertEqual(report["freshness"]["status"], "not_replayed")
        self.assertEqual(report["claims"]["source_fidelity"], "unestablished")
        self.assertEqual(
            report["claims"]["human_therapeutic_admission"], "not_admitted"
        )
        with self.assertRaisesRegex(SerializationError, "fresh complete replay"):
            inspection.inspect_circuit_construction(
                forged, expected_request=self.request
            )
        report = inspection.diff_circuit_constructions(self.build, forged)
        changed = next(
            item for item in report["changes"] if item["section"] == "values"
        )
        self.assertEqual(changed["fields"], ["sequence"])
        self.assertEqual(changed["sequence_interval"]["before"], {"start": 0, "end": 5})

    def test_optional_replay_is_independent_and_requires_both_diff_authorities(self):
        with patch(
            "biocompiler.compiler.circuit_construction.construct_circuit_candidate",
            side_effect=AssertionError("Replay must be independent of producer"),
        ):
            report = inspection.inspect_circuit_construction(
                self.build, expected_request=self.request
            )
            compared = inspection.diff_circuit_constructions(
                self.build,
                self.build,
                expected_before=self.request,
                expected_after=self.request,
            )
        self.assertEqual(report["freshness"]["status"], "replayed_external_authority")
        self.assertEqual(report["freshness"]["assessment"]["outcome"], "pass")
        self.assertEqual(
            compared["freshness"]["after"]["status"], "replayed_external_authority"
        )
        with self.assertRaisesRegex(SerializationError, "both builds"):
            inspection.diff_circuit_constructions(
                self.build, self.build, expected_before=self.request
            )
        with self.assertRaisesRegex(
            SerializationError, "independent complete authority"
        ):
            inspection.inspect_circuit_construction(
                self.build, expected_request=replace(self.request, mode="diagnostic")
            )

    def test_partial_failed_and_diagnostic_records_remain_inspectable(self):
        request = replace(self.request, payload_structures=())
        failed = build_circuit_construction(request)
        report = inspection.inspect_circuit_construction(
            failed, expected_request=request
        )
        self.assertNotEqual(report["stored_assessment"]["outcome"], "pass")
        self.assertTrue(report["molecules"])
        diagnostic = build_circuit_construction(
            replace(self.request, mode="diagnostic")
        )
        self.assertEqual(
            inspection.inspect_circuit_construction(diagnostic)["request"]["mode"],
            "diagnostic",
        )
        candidate = replace(
            self.build.candidate, bundle=None, missing_members=("payload",)
        )
        assessment = check_circuit_construction(
            candidate, expected_request=self.request
        )
        incomplete = CircuitConstructionBuild(self.request, candidate, assessment)
        report = inspection.inspect_circuit_construction(incomplete)
        self.assertEqual(report["molecules"], [])
        self.assertEqual(report["complexes"], [])
        self.assertEqual(report["missing_members"], ["payload"])
        self.assertIsNone(report["nominal_bundle_identity"])
        compared = inspection.diff_circuit_constructions(self.build, incomplete)
        self.assertTrue(
            any(
                item["section"] == "molecules" and item["change"] == "removed"
                for item in compared["changes"]
            )
        )

    def test_chemistry_only_edit_is_distinct_from_spelling(self):
        port = self.request.steps[0].ports[0]
        chemistry = port.chemistry_transition.output
        end = replace(
            chemistry.finish_end,
            identity=replace(
                chemistry.finish_end.identity, accession="other_fixture_end"
            ),
        )
        changed = replace(chemistry, finish_end=end)
        request = fixture_request(output_chemistry=changed)
        compared = self.diff(request)
        value = next(
            item for item in compared["changes"] if item["section"] == "values"
        )
        self.assertEqual(value["fields"], ["chemistry"])
        self.assertNotIn("sequence_interval", value)

    def test_context_only_and_payload_obligation_edits_are_visible(self):
        requirement = self.request.requirements[0]
        context_request = replace(
            self.request,
            requirements=(
                replace(
                    requirement,
                    roles=(replace(requirement.roles[0], compartment="extracellular"),),
                ),
            ),
            circuit=replace(
                self.request.circuit,
                profile=replace(self.request.circuit.profile, boundary="export"),
            ),
        )
        compared = self.diff(context_request)
        circuit = next(
            item for item in compared["changes"] if item["section"] == "circuit"
        )
        self.assertIn("profile", circuit["fields"])
        roles = next(
            item for item in compared["changes"] if item["section"] == "role_instances"
        )
        self.assertEqual(roles["fields"], ["compartment"])
        self.assertFalse(
            any("sequence_interval" in item for item in compared["changes"])
        )
        compared = self.diff(replace(self.request, payload_structures=()))
        self.assertTrue(
            any(
                item["section"] == "authority.payload_structures"
                and item["change"] == "removed"
                for item in compared["changes"]
            )
        )

    def test_numeric_type_amount_edit_changes_canonical_identity(self):
        integer = build_circuit_construction(amount_request(1))
        floating = build_circuit_construction(amount_request(1.0))
        self.assertNotEqual(integer.fingerprint, floating.fingerprint)
        report = inspection.diff_circuit_constructions(integer, floating)
        self.assertFalse(report["identical_content"])
        for section in ("authority.amounts", "experimental_amounts"):
            changed = next(
                item for item in report["changes"] if item["section"] == section
            )
            self.assertEqual(changed["fields"], ["quantity"])

    def test_coordinate_path_order_and_strand_are_not_normalized(self):
        forward = fixture_request(SliceOperation(selection((0, 3), (3, 6))))
        reversed_path = fixture_request(
            SliceOperation(selection((3, 6), (0, 3), strand="-"))
        )
        report = inspection.diff_circuit_constructions(
            build_circuit_construction(forward),
            build_circuit_construction(reversed_path),
        )
        step = next(
            item for item in report["changes"] if item["section"] == "authority.steps"
        )
        self.assertIn("operation", step["fields"])
        value = next(item for item in report["changes"] if item["section"] == "values")
        self.assertIn("segments", value["fields"])
        view = inspection.inspect_circuit_construction(
            build_circuit_construction(reversed_path)
        )
        self.assertEqual(view["steps"][0]["operation"]["input"]["path"]["strand"], "-")
        self.assertEqual(
            view["steps"][0]["operation"]["input"]["path"]["spans"][0]["start"], 3
        )

    def test_diff_limit_reports_omissions_and_rejects_invalid_limits(self):
        changed = forged_build(self.build)
        full = inspection.diff_circuit_constructions(self.build, changed)
        bounded = inspection.diff_circuit_constructions(
            self.build, changed, max_changes=1
        )
        self.assertEqual(len(bounded["changes"]), 1)
        self.assertEqual(bounded["total_changes"], full["total_changes"])
        self.assertEqual(bounded["omitted_changes"], full["total_changes"] - 1)
        self.assertTrue(bounded["truncated"])
        for limit in (True, False, 0, -1, 1.0, 4097, 10**100, None):
            with self.subTest(limit=limit), self.assertRaises(SerializationError):
                inspection.diff_circuit_constructions(
                    self.build, changed, max_changes=limit
                )

    def test_interval_view_is_unaligned_and_preserves_insertions_and_removals(self):
        for before, after, left, right in (
            ("AAAA", "AAAA", None, None),
            ("AC", "ATC", (1, 1), (1, 2)),
            ("ATC", "AC", (1, 2), (1, 1)),
            ("ACGU", "GUAC", (0, 4), (0, 4)),
        ):
            result = inspection._changed_interval(before, after)
            if left is None:
                self.assertIsNone(result)
            else:
                self.assertEqual(result["comparison"], "unaligned_common_prefix_suffix")
                self.assertEqual(result["before"], dict(zip(("start", "end"), left)))
                self.assertEqual(result["after"], dict(zip(("start", "end"), right)))

    def test_inspection_is_deterministic_bounded_and_requires_typed_artifacts(self):
        roundtrip = CircuitConstructionBuild.from_json(self.build.to_json())
        self.assertEqual(
            json.dumps(
                inspection.inspect_circuit_construction(self.build), sort_keys=True
            ),
            json.dumps(
                inspection.inspect_circuit_construction(roundtrip), sort_keys=True
            ),
        )
        for invalid in (None, self.build.to_dict(), self.request):
            with self.assertRaises(SerializationError):
                inspection.inspect_circuit_construction(invalid)
        with patch("biocompiler.ir.molecule_records.MAX_MOLECULE_ITEMS", 10):
            with self.assertRaisesRegex(SerializationError, "item limit"):
                inspection.inspect_circuit_construction(self.build)


if __name__ == "__main__":
    unittest.main()

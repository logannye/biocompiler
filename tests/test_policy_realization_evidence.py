"""Typed authoring and independent artificial measurement literals, without native execution."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from decimal import localcontext
from fractions import Fraction
import json
import unittest

from biocompiler import policy as p
from biocompiler.core_client import CoreProtocolError
from biocompiler.policy import realization_evidence as e
from tools import generate_policy_realization_evidence_fixture as fixture


def artifact(raw):
    return e.Artifact(**raw)


def provenance(raw):
    return e.Provenance(raw["origin"], raw["producer"], raw["recorded_at"], artifact(raw["artifact"]))


def interval(raw):
    return e.Interval(p.from_data(raw["lower"], p.Quantity), p.from_data(raw["upper"], p.Quantity))


def authored(raw):
    requirement = raw["requirements"][0]
    applicability = e.Applicability(**requirement["applicability"])
    target = e.Requirement(requirement["id"], requirement["instance"], e.ContentPin.from_data(requirement["component"]),
        requirement["mechanism_fingerprint"], requirement["parameter"]["transfer"], p.from_data(requirement["nominal"], p.Quantity),
        interval(requirement["accepted_interval"]), requirement["minimum_replicates"], applicability)
    protocol, dataset, analysis = (raw["dossier"][name][0] for name in ("protocols", "datasets", "analyses"))
    pr = protocol["body"]
    protocol = e.Protocol(protocol["identity"]["id"], "1", p.from_data(pr["sample_period"], p.Quantity), pr["procedure"], provenance(pr["provenance"]))
    dr = dataset["body"]
    dataset = e.Dataset(dataset["identity"]["id"], "1", dr["requirement"], e.ContentPin.from_data(dr["protocol"]), applicability,
        tuple(e.Replicate(row["id"], interval(row["interval"])) for row in dr["replicates"]), provenance(dr["provenance"]))
    ar = analysis["body"]
    software = e.AnalysisSoftware(ar["software"]["name"], ar["software"]["version"], artifact(ar["software"]["artifact"]))
    analysis = e.Analysis(analysis["identity"]["id"], "1", e.ContentPin.from_data(ar["dataset"]), tuple(ar["replicate_ids"]),
        interval(ar["envelope"]), software, provenance(ar["provenance"]))
    return e.EvidenceContract((target,), e.Dossier((protocol,), (dataset,), (analysis,)), raw["require_compatibility"])


class RealizationEvidenceAuthoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(fixture.PATH.read_text())
        cls.material = json.loads(fixture.MATERIAL_PATH.read_text())

    def setUp(self):
        self.raw = deepcopy(self.fixture["contract"])
        self.contract = authored(self.raw)

    def test_independent_literal_and_typed_authoring_identity(self):
        self.assertEqual(fixture.build(), self.fixture)
        self.assertEqual(self.contract.to_data(), self.raw)
        self.assertEqual(e.fingerprint(self.material), self.fixture["material_fixture_fingerprint"])
        for family in ("protocols", "datasets", "analyses"):
            for record in self.raw["dossier"][family]:
                self.assertEqual(e.fingerprint(record["body"]), record["identity"]["content_fingerprint"])

    def test_original_complete_applicability_and_no_native_claim(self):
        applicability = e.Applicability.from_material_request(self.material["request"])
        self.assertEqual(applicability.to_data(), self.raw["requirements"][0]["applicability"])
        request = deepcopy(self.material["request"])
        request["context"]["providers"][-1]["body"]["new_field"] = "changes body identity"
        # The complete environment provider body, not only its declared pin, is bound.
        env = next(row for row in request["context"]["providers"] if row["body"]["kind"] == "environment")
        env["body"]["new_field"] = "changes original applicability"
        self.assertNotEqual(applicability, e.Applicability.from_material_request(request))
        self.assertFalse(hasattr(self.contract, "accepted"))
        self.assertFalse(hasattr(self.contract, "status"))
        self.assertFalse(hasattr(e, "evaluate"))

    def test_off_grid_measurements_and_exact_small_intervals(self):
        low = "0.999999999999999999999999999999"
        high = "1.000000000000000000000000000001"
        with localcontext() as context:
            context.prec = 2
            value = e.Interval(p.quantity(low, p.COUNT), p.quantity(high, p.COUNT))
            self.assertEqual(value.to_data()["lower"]["amount"], low)
            self.assertEqual(value.to_data()["upper"]["amount"], high)
        self.assertEqual(e.Interval(p.quantity(-1, p.COUNT), p.quantity(1, p.COUNT)).lower.amount, "-1")
        rows = self.raw["dossier"]["datasets"][0]["body"]["replicates"]
        self.assertEqual(min(Fraction(row["interval"]["lower"]["amount"]) for row in rows), Fraction("0.97"))
        self.assertEqual(max(Fraction(row["interval"]["upper"]["amount"]) for row in rows), Fraction("1.03"))

    def test_complete_units_and_order_reject(self):
        for lower, upper in ((p.quantity(2, p.COUNT), p.quantity(1, p.COUNT)),
                             (p.quantity(0, p.COUNT), p.quantity(1, p.SECOND)),
                             (p.quantity(0, p.COUNT), p.quantity(1, replace(p.COUNT, reference="different")))):
            with self.subTest(lower=lower, upper=upper), self.assertRaises(e.EvidenceAuthoringError):
                e.Interval(lower, upper)
        with self.assertRaises(TypeError):
            p.Quantity(0.97, p.COUNT)

    def test_contract_does_not_infer_or_replace_analysis(self):
        dossier = self.contract.dossier
        wrong = replace(dossier.analyses[0], envelope=e.Interval(p.quantity(0, p.COUNT), p.quantity(2, p.COUNT)))
        supplied = replace(self.contract, dossier=replace(dossier, analyses=(wrong,)))
        self.assertEqual(supplied.to_data()["dossier"]["analyses"][0]["body"]["envelope"]["lower"]["amount"], "0")
        self.assertNotEqual(wrong.identity, dossier.analyses[0].identity)
        self.assertEqual(supplied.dossier.datasets[0].identity, dossier.datasets[0].identity)

    def test_missing_partial_dossier_and_explicit_gating_are_authorable(self):
        self.assertIsNone(replace(self.contract, dossier=None).to_data()["dossier"])
        self.assertEqual(replace(self.contract, dossier=e.Dossier()).to_data()["dossier"],
                         {"protocols": [], "datasets": [], "analyses": []})
        self.assertTrue(replace(self.contract, require_compatibility=True).to_data()["require_compatibility"])
        with self.assertRaises(e.EvidenceAuthoringError):
            replace(self.contract, require_compatibility=1)

    def test_origin_preserved_without_authenticating(self):
        dataset = self.contract.dossier.datasets[0]
        declared = replace(dataset, provenance=replace(dataset.provenance, origin="supplied_experiment"))
        self.assertEqual(declared.to_data()["body"]["provenance"]["origin"], "supplied_experiment")
        self.assertNotEqual(declared.identity, dataset.identity)
        with self.assertRaises(e.EvidenceAuthoringError):
            replace(dataset.provenance, origin="compiler_proved_biology")

    def test_immutable_sequences_and_detached_json(self):
        originals = list(self.contract.requirements)
        copied = replace(self.contract, requirements=originals)
        originals.clear()
        self.assertEqual(len(copied.requirements), 1)
        detached = copied.to_data()
        detached["requirements"][0]["id"] = "mutated"
        self.assertEqual(copied.requirements[0].id, "transport-amount")
        with self.assertRaises(FrozenInstanceError):
            copied.require_compatibility = True

    def test_closed_typed_bounds_and_complete_pins(self):
        requirement = self.contract.requirements[0]
        dataset = self.contract.dossier.datasets[0]
        for action in (lambda: replace(self.contract, requirements=()),
                       lambda: replace(self.contract, requirements=(requirement,) * 9),
                       lambda: replace(requirement, minimum_replicates=True),
                       lambda: replace(requirement, minimum_replicates=33),
                       lambda: replace(requirement, component=replace(requirement.component, kind="source")),
                       lambda: replace(dataset, replicates=(dataset.replicates[0],) * 2),
                       lambda: replace(self.contract.dossier, datasets=(dataset, dataset)),
                       lambda: replace(dataset.protocol, content_fingerprint="F" * 64),
                       lambda: replace(dataset.protocol, id="x" * 257),
                       lambda: e.ContentPin.from_data({**dataset.protocol.to_data(), "extra": True})):
            with self.subTest(action=action), self.assertRaises(e.EvidenceAuthoringError):
                action()


class EvidenceAssessmentTransportTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads(fixture.PATH.read_text())
        self.request = json.loads(fixture.MATERIAL_PATH.read_text())["request"]
        self.contract = self.packet["contract"]
        # Inert transport premise, deliberately not an accepted material result.
        self.material = {"empirical": "unassessed", "notice": "transport test only"}
        dossier = self.contract["dossier"]
        self.row = {"requirement": deepcopy(self.contract["requirements"][0]), "status": "supported", "issues": [],
            "protocol": deepcopy(dossier["protocols"][0]), "dataset": deepcopy(dossier["datasets"][0]),
            "analysis": deepcopy(dossier["analyses"][0]), "recomputed_envelope": deepcopy(self.packet["expected"]["recomputed_envelope"]),
            "replicates": 3, "origins": ["synthetic_fixture"]}
        self.report = {"schema_version": "biocompiler.policy_realization_evidence_assessment.v0.1", "profile": e.PROFILE,
            "implementation": "biocompiler.ocaml.policy_realization_evidence_check.v0.1", "status": "supported",
            "claim_scope": "supplied_parameter_interval_compatibility", "request_fingerprint": e.fingerprint(self.request),
            "material_assessment_fingerprint": e.fingerprint(self.material), "contract_fingerprint": e.fingerprint(self.contract),
            "applicability": deepcopy(self.contract["requirements"][0]["applicability"]), "require_compatibility": False,
            "export_permitted": True, "requirements": [self.row], "issues": [], "empirical": "unassessed",
            "authenticity": "unassessed", "artifact_contents": "unassessed", "statistical_coverage": "not_inferred",
            "formal_prerequisites_discharged": [], "usage": {"unit": "logical_data_visits_and_exact_interval_work", "charged_work": 1}}

    def check(self):
        return e.validate_assessment(self.report, self.contract, self.request, self.material)

    def refresh(self):
        self.report["contract_fingerprint"] = e.fingerprint(self.contract)

    def test_independent_complete_report_and_mutation_rejections(self):
        self.assertIsNone(self.check())
        for key, value in (("status", "incompatible"), ("profile", "other"), ("implementation", "other"),
                           ("claim_scope", "empirical_demonstrated"), ("empirical", "pass"), ("authenticity", "verified"),
                           ("artifact_contents", "verified"), ("statistical_coverage", "95%"),
                           ("formal_prerequisites_discharged", ["biology"]), ("request_fingerprint", "0" * 64),
                           ("contract_fingerprint", "0" * 64), ("material_assessment_fingerprint", "0" * 64),
                           ("export_permitted", False), ("extra", True)):
            with self.subTest(key=key):
                mutated = deepcopy(self.report)
                mutated[key] = value
                with self.assertRaises(CoreProtocolError):
                    e.validate_assessment(mutated, self.contract, self.request, self.material)
        for key, value in (("status", "unassessed"), ("replicates", True), ("origins", ["supplied_experiment"]),
                           ("analysis", None), ("protocol", None), ("dataset", None), ("recomputed_envelope", None), ("issues", ["unjustified"])):
            with self.subTest(key=key):
                mutated = deepcopy(self.report)
                mutated["requirements"][0][key] = value
                with self.assertRaises(CoreProtocolError):
                    e.validate_assessment(mutated, self.contract, self.request, self.material)

    def test_absent_evidence_status_and_explicit_export_gate(self):
        self.contract["dossier"] = None
        self.row.update(status="unassessed", issues=["measurement_dataset_absent"], protocol=None, dataset=None,
                        analysis=None, recomputed_envelope=None, replicates=0, origins=[])
        self.report["status"] = "unassessed"
        self.refresh()
        self.check()
        self.contract["require_compatibility"] = self.report["require_compatibility"] = True
        self.report["export_permitted"] = False
        self.refresh()
        self.check()
        self.report["export_permitted"] = True
        with self.assertRaises(CoreProtocolError):
            self.check()

    def test_repinned_analysis_contradiction_retains_formal_export_by_default(self):
        analysis = self.contract["dossier"]["analyses"][0]
        analysis["body"]["envelope"]["lower"]["amount"] = "0.96"
        analysis["identity"]["content_fingerprint"] = e.fingerprint(analysis["body"])
        self.row.update(analysis=deepcopy(analysis), status="incompatible", issues=["independently_recomputed_envelope_mismatch"])
        self.report["status"] = "incompatible"
        self.refresh()
        self.check()
        self.report["status"] = self.row["status"] = "supported"
        self.row["issues"] = []
        with self.assertRaises(CoreProtocolError):
            self.check()

    def test_nonapplicable_environment_is_unassessed_and_data_stays_bound(self):
        dataset = self.contract["dossier"]["datasets"][0]
        analysis = self.contract["dossier"]["analyses"][0]
        dataset["body"]["applicability"]["clock_fingerprint"] = "0" * 64
        dataset["identity"]["content_fingerprint"] = e.fingerprint(dataset["body"])
        analysis["body"]["dataset"] = deepcopy(dataset["identity"])
        analysis["identity"]["content_fingerprint"] = e.fingerprint(analysis["body"])
        self.row.update(dataset=deepcopy(dataset), analysis=deepcopy(analysis), status="unassessed",
                        issues=["measurement_environment_not_applicable"])
        self.report["status"] = "unassessed"
        self.refresh()
        self.check()
        self.row["dataset"]["body"]["applicability"] = self.row["requirement"]["applicability"]
        with self.assertRaises(CoreProtocolError):
            self.check()

    def test_origin_and_complete_units_cannot_be_laundered(self):
        bad = deepcopy(self.contract)
        bad["dossier"]["datasets"][0]["body"]["provenance"]["origin"] = "supplied_experiment"
        report = deepcopy(self.report)
        report["contract_fingerprint"] = e.fingerprint(bad)
        with self.assertRaises(CoreProtocolError):
            e.validate_assessment(report, bad, self.request, self.material)
        self.row["recomputed_envelope"]["lower"]["unit"]["reference"] = "other"
        with self.assertRaises(CoreProtocolError):
            self.check()

    def test_native_exact_decimal_measurement_spelling_is_preserved(self):
        dataset = self.contract["dossier"]["datasets"][0]
        analysis = self.contract["dossier"]["analyses"][0]
        dataset["body"]["replicates"][0]["interval"]["lower"]["amount"] = "9.7e-1"
        dataset["identity"]["content_fingerprint"] = e.fingerprint(dataset["body"])
        analysis["body"]["dataset"] = deepcopy(dataset["identity"])
        analysis["identity"]["content_fingerprint"] = e.fingerprint(analysis["body"])
        self.row.update(dataset=deepcopy(dataset), analysis=deepcopy(analysis))
        self.row["recomputed_envelope"]["lower"]["amount"] = "9.7e-1"
        self.refresh()
        self.check()
        # Complete Unit scale has its own exact lexical bound, independent of
        # canonical fixed-spelling source Quantity amounts.
        unit = replace(p.COUNT, scale="1e1000")
        self.assertEqual(e.Interval(p.quantity(0, unit), p.quantity(1, unit)).upper.unit, unit)


if __name__ == "__main__":
    unittest.main()

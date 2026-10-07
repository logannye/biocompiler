"""Pure staged witness metadata controls; synthetic records are not native proof.

No native program, policy runtime, compilation, or installation executes here.
Hosted witness orchestration owns all semantic acceptance observations.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from biocompiler.core_client import CORE_VERSION, CoreRejected, CoreResponse, Diagnostic
from biocompiler.core_policy_component_material import ACCEPTED_STATUS, CLAIM_SCOPE, PREMISE
from tools import check_policy_staged_component_material as witness

ROOT = Path(__file__).resolve().parents[1]


def inert_result(fixture, *, exported=False):
    """Deliberately incomplete protocol records exercise only literal metadata.

    They cannot pass the public Core transport validator or run a state machine.
    """
    preservation = {"preservation": "pass", "coverage": {"complete": True, "histories": 25,
        "transitions": 86, "prefixes_started": 87, "matched_prefixes": 87},
        "requirements": [{"id": name, "status": "pass", "nonvacuous": True, "histories": {
            "pass": passed, "fail": 0, "unknown": 0, "not_exercised": unexercised, "unsupported": 0}}
                         for name, passed, unexercised in (("first_initiation", 25, 0), ("second_initiation", 21, 4))],
        "binding": {"profile": "biocompiler.policy_staged_source_graph.v0.1", "state_encoding": "exact_ordered_source_labels"}}
    machine = {"obligation": witness.MACHINE_OBLIGATION, "status": "discharged",
        "stage": "bounded_machine_semantics_and_declared_requirements", "evidence": {
            "preservation": witness.canonical_digest(preservation), "machine_binding": witness.canonical_digest(preservation["binding"]),
            "state_and_terminal_semantics": "exact_bounded_source_correspondence", "prefixes": "complete_original_domain",
            "retained_attempt_identity": "creation_fixed_injective", "universal_termination": "not_claimed", "progress": "declared_requirements_only"}}
    report = {"status": ACCEPTED_STATUS, "claim_scope": CLAIM_SCOPE, "premise": PREMISE,
        "assembly_status": "pass", "context_status": "pass", "all_original_obligations_discharged": True,
        "empirical": "unassessed", "artifact": "withheld", "export": "withheld", "preservation": preservation,
        "obligations": [machine], "assembly": {"link_projections": [None] * 12},
        "context": {"profile": "biocompiler.policy_staged_component_mrna.v0.1"}}
    candidate = {"construction": {"inventory": {"molecules": [deepcopy(fixture["expected"]["molecule"])]}},
        "implementation": {"nodes": [None] * 28, "wires": [None] * 55},
        "binding": {"rules": [], "states": [], "machines": [None], "transitions": [None] * 7}}
    result = {"candidate": candidate, "report": report, "artifact": None}
    if exported:
        manifest = {"request": deepcopy(fixture["request"]), "candidate": candidate, "limits": deepcopy(fixture["limits"]),
            "assessment": report, "bindings": {"assessment_fingerprint": witness.canonical_digest(report)}}
        result["artifact"] = {"fasta": witness.FASTA, "fasta_sha256": hashlib.sha256(witness.FASTA.encode()).hexdigest(),
            "manifest": manifest, "manifest_sha256": witness.canonical_digest(manifest)}
    return result


class StagedComponentSDKTests(unittest.TestCase):
    def setUp(self):
        self.fixture = witness.checked_fixture(ROOT, ROOT / witness.FIXTURE)
        self.original = self.fixture["request"]
        # A test accidentally crossing the native boundary must fail locally.
        self.addCleanup(mock.patch.stopall)
        mock.patch("subprocess.Popen", side_effect=AssertionError("Pure test attempted a process")).start()
        mock.patch("subprocess.run", side_effect=AssertionError("Pure test attempted a process")).start()

    def test_public_python_authoring_preserves_exact_original_authority(self):
        request, record = witness.author_request(self.original)
        self.assertEqual(request, self.original)
        self.assertEqual(record["phase"], "python_authoring_before_native_semantic_guard")
        self.assertEqual(record["runtime_semantics"], "not_executed")
        self.assertEqual(record["request_digest"], witness.canonical_digest(self.original))
        request["context"]["record_layout"]["attempts"] = 999
        self.assertNotEqual(request, self.original)
        self.assertEqual(record["request_digest"], witness.canonical_digest(self.original))

    def test_exact_census_is_separate_from_legacy_witnesses(self):
        from tools import check_policy_component_material as old
        witness.check_census(witness.OBSERVATIONS)
        self.assertEqual(len(witness.OBSERVATIONS), 16)
        self.assertEqual(len(set(witness.OBSERVATIONS)), 16)
        self.assertEqual(len(old.CASE_NAMES), 13)  # Unchanged two-case 26-observation witness.
        for names in (witness.OBSERVATIONS[:-1], witness.OBSERVATIONS[::-1],
                      witness.OBSERVATIONS + (witness.OBSERVATIONS[0],),
                      (witness.OBSERVATIONS[0],) + witness.OBSERVATIONS[:-1]):
            with self.subTest(names=names), self.assertRaisesRegex(AssertionError, "census"):
                witness.check_census(names)

    def test_fixture_does_not_accept_relabelled_expected_counts_or_material(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in witness.INPUTS[:3]:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((ROOT / name).read_bytes())
            path = root / witness.FIXTURE
            for key, value in (("histories", 1), ("transitions", 85), ("prefixes_started", 86),
                               ("requirements", ["first_initiation"]), ("sequence", "A"), ("fasta", ">x\nA\n")):
                altered = deepcopy(self.fixture)
                altered["expected"][key] = value
                path.write_text(json.dumps(altered))
                with self.subTest(key=key), self.assertRaisesRegex(AssertionError, "census"):
                    witness.checked_fixture(root, path)
            with self.assertRaisesRegex(AssertionError, "exact staged"):
                witness.checked_fixture(root, root / "foreign.json")

    def test_inert_positive_metadata_cannot_hide_changed_bounded_claims(self):
        witness.checked_result(inert_result(self.fixture), self.fixture)
        mutations = [
            lambda r: r["report"]["preservation"]["coverage"].update(complete=False),
            lambda r: r["report"]["preservation"]["coverage"].update(histories=24),
            lambda r: r["report"]["preservation"]["requirements"].pop(),
            lambda r: r["report"]["preservation"]["requirements"][0].update(nonvacuous=False),
            lambda r: r["report"]["obligations"][0]["evidence"].update(universal_termination="proved"),
            lambda r: r["report"]["obligations"][0]["evidence"].update(progress="guaranteed_completion"),
            lambda r: r["report"]["obligations"][0]["evidence"].update(machine_binding="0" * 64),
            lambda r: r["report"]["context"].update(profile="biocompiler.policy_component_mrna.v0.1"),
            lambda r: r["candidate"]["construction"]["inventory"]["molecules"][0].update(sequence="A"),
            lambda r: r["candidate"]["binding"]["machines"].clear(),
            lambda r: r["candidate"]["implementation"]["wires"].pop(),
        ]
        for mutate in mutations:
            changed = inert_result(self.fixture)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError):
                witness.checked_result(changed, self.fixture)

    def test_inert_export_metadata_preserves_both_artifacts_and_originals(self):
        result = inert_result(self.fixture, exported=True)
        witness.checked_export(result, self.fixture)
        self.assertEqual([row["name"] for row in witness.archive_receipt(result)["members"]], ["program.fasta", "manifest.json"])
        for mutate in (
            lambda r: r["artifact"].update(fasta=">changed\nA\n"),
            lambda r: r["artifact"]["manifest"]["request"]["budgets"].update(max_work=1),
            lambda r: r["artifact"]["manifest"]["limits"].update(max_step_work=1),
            lambda r: r["artifact"].update(manifest_sha256="0" * 64),
        ):
            changed = deepcopy(result)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError):
                witness.checked_export(changed, self.fixture)

    def test_exact_requirement_histories_preserve_conditional_nonvacuity(self):
        result = inert_result(self.fixture)
        requirements = result["report"]["preservation"]["requirements"]
        self.assertEqual([row["histories"] for row in requirements], [
            {"pass": 25, "fail": 0, "unknown": 0, "not_exercised": 0, "unsupported": 0},
            {"pass": 21, "fail": 0, "unknown": 0, "not_exercised": 4, "unsupported": 0},
        ])
        witness.checked_result(result, self.fixture)
        mutations = [
            ("second falsely exercised everywhere", 1, lambda row: row["histories"].update({"pass": 25, "not_exercised": 0})),
            ("second wholly vacuous", 1, lambda row: row["histories"].update({"pass": 0, "not_exercised": 25})),
            ("first wrongly unexercised", 0, lambda row: row["histories"].update({"pass": 24, "not_exercised": 1})),
            ("nonvacuity lost", 1, lambda row: row.update(nonvacuous=False)),
            ("aggregate status lost", 1, lambda row: row.update(status="unknown")),
            ("history omitted", 1, lambda row: row["histories"].update(not_exercised=3)),
            ("zero category omitted", 1, lambda row: row["histories"].pop("unknown")),
            ("foreign category added", 1, lambda row: row["histories"].update(pending=0)),
            ("float count", 1, lambda row: row["histories"].update({"pass": 21.0})),
            ("boolean count", 1, lambda row: row["histories"].update(unknown=False)),
        ]
        for index, passed in ((0, 25), (1, 21)):
            for category in ("fail", "unknown", "unsupported"):
                mutations.append((f"{index}/{category} hidden by pass aggregate", index,
                    lambda row, category=category, passed=passed: row["histories"].update({"pass": passed - 1, category: 1})))
        for name, index, mutate in mutations:
            changed = deepcopy(result)
            preservation = changed["report"]["preservation"]
            mutate(preservation["requirements"][index])
            # Rehash the surrounding claim so it cannot be the rejection reason.
            changed["report"]["obligations"][0]["evidence"]["preservation"] = witness.canonical_digest(preservation)
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, "finite-domain or nonvacuous"):
                witness.checked_result(changed, self.fixture)

    def test_mutation_recipes_preserve_originals_and_select_actual_owners(self):
        candidate = {"binding": {"transitions": [{"commit": "start"}], "effects": [{"bank": "one"}, {"bank": "two"}]},
            "implementation": {"wires": [
                {"producer": {"node": "start", "port": "machine_write"}, "consumer": {"node": "machine", "port": "write0"}},
                *[{"producer": {"node": "one", "port": "events"}, "consumer": {"node": event, "port": "events"}}
                  for event in ("completed", "failed", "timeout")],
                *[{"producer": {"node": node, "port": "request0"}, "consumer": {"node": bank, "port": "request"}}
                  for node, bank in (("start", "one"), ("handoff", "two"))]]}}
        original = deepcopy(candidate)
        missing = witness.changed_graph(candidate, "missing-machine-wire")
        self.assertEqual(len(missing["implementation"]["wires"]), 5)
        feedback = witness.changed_graph(candidate, "wrong-feedback-bank")
        self.assertEqual([row["producer"]["node"] for row in feedback["implementation"]["wires"][1:4]], ["two"] * 3)
        swapped = witness.changed_graph(candidate, "wrong-request-owner")
        self.assertEqual([row["consumer"]["node"] for row in swapped["implementation"]["wires"][-2:]], ["two", "one"])
        self.assertEqual(candidate, original)
        with self.assertRaises(AssertionError):
            witness.changed_graph(candidate, "unknown")

    def test_capacity_control_repins_full_premise_without_rewriting_source(self):
        original = deepcopy(self.original)
        changed = witness.deficient_capacity(original)
        self.assertEqual(changed["implementation_request"], original["implementation_request"])
        selected = [row for provider in changed["context"]["providers"] for row in provider["body"]["capacities"]
                    if row["unit"] == "machine_state_bits"]
        self.assertEqual([row["quantity"] for row in selected], [2])
        for provider in changed["context"]["providers"]:
            self.assertEqual(provider["identity"]["content_fingerprint"], witness.canonical_digest(provider["body"]))
        self.assertEqual(original, self.original)

    def test_completion_control_changes_requirement_without_inventing_feedback(self):
        changed = witness.completion_request(self.original)
        self.assertEqual(changed["implementation_request"]["operating_domain"], self.original["implementation_request"]["operating_domain"])
        requirement = next(row for row in changed["implementation_request"]["document"]["program"]["declarations"] if row["id"] == "second_initiation")
        self.assertEqual(requirement["response"]["value"], "completed")
        requirement["response"]["value"] = "initiated"
        self.assertEqual(changed, self.original)

    def test_rejection_records_retain_exact_native_error_and_no_result(self):
        for name, code in witness.NEGATIVE_CODES.items():
            def raise_response(*, actual=code, result=None, status="unsupported" if name == "verify-has-no-producer" else "error"):
                raise CoreRejected(CoreResponse("inert-only", "inert-operation", status, result,
                    (Diagnostic(actual, "Synthetic rejection; no native execution", None),), "verify", CORE_VERSION))
            result = witness.rejected(name, raise_response)
            self.assertEqual(result["diagnostics"][0]["code"], code)
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, "unrelated"):
                witness.rejected(name, lambda: raise_response(actual="unrelated"))
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, "unrelated"):
                witness.rejected(name, lambda: raise_response(result={"partial": True}))
        with self.assertRaisesRegex(AssertionError, "acceptance"):
            witness.rejected("forged-replay", lambda: None)

    def test_shared_guard_blocks_python_semantics_even_when_already_imported(self):
        boundary = witness.ComponentBoundary(ROOT / "src/biocompiler")
        for name in ("biocompiler.compiler", "biocompiler.behavior", "biocompiler_core", "_biocompiler"):
            with self.subTest(name=name), self.assertRaises(ImportError):
                boundary.find_spec(name, None)
        for module, function in (("biocompiler.policy.validation", "check"), ("biocompiler.policy.programs", "freeze"),
                                  ("biocompiler.policy.handoff", "prepare_submission")):
            frame = SimpleNamespace(f_globals={"__name__": module}, f_code=SimpleNamespace(co_name=function))
            with self.subTest(module=module), self.assertRaises(AssertionError):
                boundary.trace(frame, "call", None)
        self.assertTrue(boundary.allowed("biocompiler.core_policy_component_material"))
        self.assertTrue(boundary.allowed("biocompiler.policy.component_material"))

    def test_hosted_identity_gate_precedes_any_native_launch(self):
        with mock.patch.object(witness, "identity", side_effect=ValueError("Hosted only")), self.assertRaisesRegex(ValueError, "Hosted only"):
            witness.run(SimpleNamespace())


if __name__ == "__main__":
    unittest.main()

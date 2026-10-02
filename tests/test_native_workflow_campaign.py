"""Complete installed-campaign projection and transport-only harness integrity.

All native exchanges here are test doubles; hosted campaigns execute the pinned
native binaries. Original Python oracle checks are separate from the guard.
"""
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import check_native_workflow as campaign


class WorkflowProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = campaign.Corpus()
        cls.cases = cls.corpus.cases()

    def test_every_original_occurrence_and_explicit_counterpart_remains(self):
        self.assertEqual(len(self.cases), 112)
        original = [case for case in self.cases if case["origin"] == "original"]
        self.assertEqual(len(original), 89)
        self.assertEqual(len({case["id"] for case in original}), 52)
        self.assertEqual(Counter(case["phase"] for case in original),
                         {"original": 50, "fresh-replay": 35, "current-policy-counterpart": 2, "original-stale-policy": 2})
        independent = []
        for context in self.corpus.index["contexts"]:
            for ordinal, row in enumerate(self.corpus.document(context["ledger"])):
                if row["api"] in campaign.OPERATIONS:
                    independent.append((context["id"] + "/api/" + str(ordinal), row))
        self.assertEqual({identity for identity, _ in independent}, {case["id"] for case in original})
        for identity, row in independent:
            siblings = [case for case in original if case["id"] == identity]
            self.assertTrue(siblings)
            self.assertTrue(all(case["source_evidence"]["observation"] == row for case in siblings))
            bound = json.loads(self.corpus.document(row["native"]["input"]))
            authority = bound["request" if row["api"].startswith("run_") else "expected_request"]
            self.assertTrue(all(case["authority"] == campaign.canonical(authority) for case in siblings))
            for case in siblings:
                self.assertEqual(case["source_evidence"]["raw_arguments"], self.corpus.document(row["input"]))
                self.assertEqual(case["source_evidence"]["python_types"], self.corpus.document(row["python_types"]))
        nominal = next(case for case in original if case["id"] == campaign.NOMINAL_ID)
        self.assertEqual(nominal["source_evidence"]["observation"]["error"]["message"],
                         "Fresh replay needs independently trusted complete operation authority.")
        self.assertEqual(nominal["error"], {"code": "verification_workflow", "message":
            "Invalid fields in SyntheticVerificationRequest.", "path": "authority"})

    def test_exact_two_checker_mutants_preserve_full_historical_and_current_artifacts(self):
        cases = [case for case in self.cases if case["id"].startswith(campaign.VERSION_CONTEXT + "/api/")]
        selected = {case["phase"]: case for case in cases if case["id"].endswith("/135")}
        current = json.loads(selected["current-policy-counterpart"]["expected"])
        historical = json.loads(selected["original-stale-policy"]["retained"])
        self.assertEqual(current["result"]["dependencies"]["checker"], campaign.CHECKER_VERSION)
        self.assertEqual(historical["result"]["dependencies"]["checker"], "changed.v999")
        historical["result"]["dependencies"]["checker"] = campaign.CHECKER_VERSION
        self.assertEqual(campaign.canonical(historical), campaign.canonical(current))
        replay = {case["phase"]: case for case in cases if case["id"].endswith("/134")}
        self.assertEqual(replay["current-policy-counterpart"]["expected"], replay["current-policy-counterpart"]["retained"])
        self.assertEqual(replay["original-stale-policy"]["error"]["code"], "synthetic_verification")

    def test_nine_supplemental_full_records_match_literal_and_original_python_run_replay(self):
        source = (campaign.ROOT / "core/test/test_verification_workflow_service.ml").read_text()
        literal = json.loads(re.search(r"\{original\|(.*?)\|original\}", source, re.S).group(1))
        self.assertEqual(literal, self.corpus.supplement["cases"])
        from biocompiler.compiler.verification_workflow import (
            SyntheticVerificationRequest, SyntheticVerificationRecord,
            run_synthetic_verification, replay_synthetic_verification,
        )
        combinations = set()
        for case in literal:
            expected = case["expected"]
            request = SyntheticVerificationRequest.from_dict(expected["request"])
            original = SyntheticVerificationRecord.from_dict(expected)
            self.assertEqual(campaign.canonical(run_synthetic_verification(request).to_dict()), campaign.canonical(expected))
            self.assertEqual(campaign.canonical(replay_synthetic_verification(original, expected_request=request).to_dict()), campaign.canonical(expected))
            self.assertEqual(original.fingerprint, case["fingerprint"])
            combinations.add((request.operation, request.mode))
        self.assertEqual(combinations, {(operation, mode) for operation in ("check", "explore", "reduce") for mode in ("candidate", "model")})

    def test_normalization_and_authority_precedence_are_explicit_distinct_cases(self):
        normalized = next(case for case in self.cases if case["id"] == "boundary/normalized-authority")
        retained = next(case for case in self.cases if case["id"] == "boundary/raw-retained-order")
        from biocompiler.compiler.verification_workflow import SyntheticVerificationRequest, run_synthetic_verification
        request = SyntheticVerificationRequest.from_dict(json.loads(normalized["authority"]))
        self.assertEqual(campaign.canonical(run_synthetic_verification(request).to_dict()), normalized["expected"])
        self.assertNotEqual(campaign.sha(normalized["authority"]), request.fingerprint)
        self.assertNotEqual(retained["retained"], normalized["expected"])
        self.assertEqual(retained["error"]["code"], "synthetic_verification")
        malformed = next(case for case in self.cases if case["origin"] == "authority_precedence")
        self.assertEqual(malformed["retained"], b'{"unfinished":')
        self.assertEqual(malformed["error"]["code"], "lowering_source_identity")

    def test_inventory_profile_and_full_document_tampering_are_rejected(self):
        corpus = campaign.Corpus()
        row = next(context for context in corpus.index["contexts"] if context["api_calls"])
        corpus.document(row["ledger"])
        corpus.cache[row["ledger"]].clear()
        with self.assertRaisesRegex(AssertionError, "content changed"):
            corpus.document(row["ledger"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.json"
            altered = deepcopy(corpus.index); altered["coverage"]["original_methods"] -= 1
            path.write_bytes(campaign.canonical(altered) + b"\n")
            with self.assertRaisesRegex(AssertionError, "inventory changed"): campaign.Corpus(path)
        altered = campaign.Corpus(); altered.supplement["cases"].pop()
        with self.assertRaisesRegex(AssertionError, "projection changed"): altered.cases()

    def test_semantic_guard_denies_imports_and_preloaded_function_calls(self):
        namespace = {"__name__": "biocompiler.compiler.forbidden"}
        exec("def semantic(): return 1", namespace)
        with self.assertRaisesRegex(AssertionError, "semantic execution"), campaign.transport_only():
            namespace["semantic"]()
        with self.assertRaisesRegex(AssertionError, "semantic import"), campaign.transport_only():
            __import__("biocompiler.compiler.verification_workflow")


class WorkflowCampaignHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = campaign.Corpus()
        cls.cases = cls.corpus.cases()

    @contextmanager
    def exchanges(self, corrupt=False):
        from biocompiler.core_client import CAPABILITIES_SCHEMA, CORE_VERSION, LIMITS, PROTOCOL
        from biocompiler.core_artifacts import TRANSPORT_PROFILE
        by_id = {campaign.request_id(role, case): (role, case) for role in ("core", "verify") for case in self.cases}
        def response(request, role, value, diagnostic=None):
            return campaign.canonical({"protocol": PROTOCOL, "request_id": request["request_id"], "operation": request["operation"],
                "status": "ok" if diagnostic is None else "error", "result": value,
                "diagnostics": [] if diagnostic is None else [diagnostic],
                "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": role}}), (0 if diagnostic is None else 2)
        def negotiate(path, raw, _timeout, _cancelled):
            role = "verify" if str(path).endswith("verify") else "core"
            request = json.loads(raw)
            value = {"schema_version": CAPABILITIES_SCHEMA, "operations": ["capabilities", *campaign.OPERATIONS.values()],
                "intent_schemas": [], "canonicalization": "python-json-v1", "limits": LIMITS,
                "validation_scopes": [self.corpus.profile["validation_scope"]], "claim_scope": "Transport fixture only.",
                "profiles": {"artifact_transport": TRANSPORT_PROFILE, "verification_workflow": self.corpus.profile}}
            return response(request, role, value)
        def exchange(core, raw, arguments, files, output, _limit, _cancelled):
            request = json.loads(raw); role, case = by_id[request["request_id"]]
            self.assertEqual(role, core.role)
            self.assertEqual(files[0].read(), case["authority"])
            if case["retained"] is not None: self.assertEqual(files[1].read(), case["retained"])
            if case["error"] is not None: return response(request, role, None, case["error"])
            record = case["expected"]
            if corrupt:
                value = json.loads(record); value["result"]["corrupted_complete_field"] = True
                record = campaign.canonical(value)
            output.write(record); output.flush()
            def descriptor(raw): return {"bytes": len(raw), "sha256": campaign.sha(raw)}
            profile = self.corpus.profile
            authority = json.loads(case["authority"])
            receipt = {"schema_version": "biocompiler.core.verification_workflow_result.v1", "profile": profile["profile"],
                "operation": case["operation"], "executable": role, "request_id": request["request_id"],
                "validation_scope": profile["validation_scope"], "implementation_version": profile["implementation_version"],
                "workflow_version": profile["workflow_version"], "workflow_operation": authority["operation"], "mode": authority["mode"],
                "authority_fingerprint": campaign.digest(authority), "request_fingerprint": campaign.digest(json.loads(record)["request"]),
                "retained_record_fingerprint": None if case["retained"] is None else campaign.digest(json.loads(case["retained"])),
                "record_fingerprint": campaign.sha(record), "resources": campaign.expected_resources(profile, case["limits"])}
            value = {"schema_version": "biocompiler.core.artifact_response.v1", "transport": "biocompiler.core.artifact_transport.v1",
                "authority": descriptor(case["authority"]), "retained_record": None if case["retained"] is None else descriptor(case["retained"]),
                "artifact": descriptor(record), "result": receipt}
            return response(request, role, value)
        with patch("biocompiler.core_client._exchange", side_effect=negotiate), \
             patch("biocompiler.core_artifacts._exchange_artifacts", side_effect=exchange):
            yield

    def test_complete_two_role_campaign_publishes_every_full_artifact_and_error(self):
        from biocompiler.core_client import CoreClient
        with tempfile.TemporaryDirectory() as directory, self.exchanges():
            root = Path(directory)
            receipt = {"_artifact_directory": str(root), "checks": [], "artifacts": {}}
            for role in ("core", "verify"):
                (root / role).write_bytes(b"transport test double; never executed")
                (root / role).chmod(0o755)
            clients = [CoreClient(root / role, role=role) for role in ("core", "verify")]
            campaign.campaign(clients, self.corpus, receipt)
            self.assertEqual(len(receipt["checks"]), 224)
            self.assertEqual(Counter(row["role"] for row in receipt["checks"]), {"core": 112, "verify": 112})
            for role in ("core", "verify"):
                rows = [row for row in receipt["checks"] if row["role"] == role]
                self.assertEqual([(row["id"], row["phase"]) for row in rows], [(case["id"], case["phase"]) for case in self.cases])
                for case, row in zip(self.cases, rows, strict=True):
                    self.assertEqual(row["guard_modules"], sorted(campaign.TRANSPORT_MODULES))
                    self.assertEqual((root / receipt["artifacts"][row["authority"]]["path"]).read_bytes(), case["authority"])
                    wire = json.loads((root / receipt["artifacts"][row["envelope"]]["path"]).read_bytes())
                    self.assertEqual(wire["request_id"], campaign.request_id(role, case))
                    self.assertEqual(wire["core"]["executable"], role)
                    if case["expected"] is not None:
                        self.assertEqual((root / receipt["artifacts"][row["record"]]["path"]).read_bytes(), case["expected"])
                        self.assertIsNone(row["diagnostic"])
                    else:
                        self.assertEqual(wire["diagnostics"], [case["error"]])
            for identity, descriptor in receipt["artifacts"].items():
                raw = (root / descriptor["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), identity)
                self.assertEqual(len(raw), descriptor["bytes"])

    def test_changed_full_record_is_not_accepted_even_with_matching_native_hashes(self):
        from biocompiler.core_client import CoreClient
        with tempfile.TemporaryDirectory() as directory, self.exchanges(corrupt=True):
            receipt = {"_artifact_directory": directory, "checks": [], "artifacts": {}}
            (Path(directory) / "core").write_bytes(b"transport test double; never executed")
            (Path(directory) / "core").chmod(0o755)
            with self.assertRaisesRegex(AssertionError, "Complete original workflow output differs"):
                campaign.campaign([CoreClient(Path(directory) / "core")], self.corpus, receipt)
            self.assertEqual(receipt["checks"], [])

    def test_artifact_paths_are_content_addressed_and_existing_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = {"_artifact_directory": directory, "artifacts": {}}
            value = b'{"complete":true}'
            identity = campaign.sha(value)
            target = Path(directory) / "outside"; target.write_bytes(value)
            (Path(directory) / (identity + ".bin")).symlink_to(target)
            with self.assertRaisesRegex(AssertionError, "Conflicting"): campaign.artifact(receipt, value)

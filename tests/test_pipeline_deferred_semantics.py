"""Exact original deferred access, callback effects and exception identities."""
from copy import deepcopy
import json
import sys
import unittest

from tools import capture_pipeline_deferred_semantics as oracle
from tools import check_pipeline_deferred_runtime as runtime

PIN = "21ff92c3b384a0be705733e768abfc510acc58f529065eff06af63bc77fce444"


def validate(document):
    computed = oracle.sha(oracle.canonical({key: value for key, value in document.items() if key != "inventory_fingerprint"}))
    if document.get("inventory_fingerprint") != PIN or computed != PIN:
        raise AssertionError("Immutable original deferred-semantics inventory changed")


def resign(document):
    document["inventory_fingerprint"] = oracle.sha(oracle.canonical({key: value for key, value in document.items()
        if key != "inventory_fingerprint"}))
    return document


def mapping(value):
    return dict(value["items"])


def fields(case):
    return mapping(case["final_state"])


class PipelineDeferredSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = oracle.OUTPUT.read_bytes()
        cls.value = json.loads(cls.raw)
        validate(cls.value)
        cls.current = oracle.capture()
        cls.cases = {case["id"]: case for case in cls.value["cases"]}

    def accesses(self, identity):
        return [event["access"] for event in self.cases[identity]["access_log"]]

    def event(self, identity, operation="run"):
        return next(event for event in self.cases[identity]["events"] if event["operation"] == operation)

    def records(self, identity):
        return mapping(fields(self.cases[identity])["_records"])

    def test_complete_frozen_original_bytes_sources_and_current_runtime_counterpart(self):
        self.assertEqual(self.raw, oracle.canonical(self.value) + b"\n")
        self.assertEqual(self.value["coverage"], {"cases": 47, "events": 157, "accesses": 290,
            "raised_events": 45, "nested_events": 21, "marker_exceptions": 19})
        self.assertEqual(len(self.cases), 47)
        for path, pin in self.value["source_files"].items():
            self.assertEqual(oracle.sha((oracle.ROOT / path).read_bytes()), pin, path)
        proof = runtime.compare_current(self.value, self.current)
        self.assertEqual(proof["complete_current_case"], proof["independent_original_manager_case"])
        self.assertEqual(proof["exact_paths"]["paths"], ["exception.message", "exception.args.items.0"])
        self.assertEqual(proof["complete_captured_case"], self.cases["proposal:unhashable_status"])
        self.assertEqual(oracle.canonical(proof["comparison_capture"]), oracle.canonical(proof["expected_capture"]))
        self.assertEqual(proof["complete_raw_current"], self.current)
        if self.value["capture_runtime"] == self.current["capture_runtime"] and not proof["frame_correspondences"]:
            self.assertEqual(oracle.canonical(self.current), oracle.canonical(self.value))
        for case in self.cases.values():
            self.assertEqual([event["id"] for event in case["events"]], list(range(len(case["events"]))))
            self.assertEqual([event["ordinal"] for event in case["access_log"]], list(range(len(case["access_log"]))))
            for event in case["events"]:
                self.assertEqual(("exception" in event, "result" in event),
                    (event["outcome"] == "raised", event["outcome"] == "returned"))
                self.assertLessEqual(event["access_start"], event["access_end"])
                if event["parent"] is not None:
                    self.assertLess(event["parent"], event["id"])

    def test_exact_duplicate_getters_and_early_rejection_precedence(self):
        self.assertEqual(self.accesses("proposal:valid"), ["producer.enter", "proposal.search_status",
            "proposal.search_status", "proposal.output", "proposal.output", "output.lookup.to_dict", "output.to_dict",
            "proposal.source_links", "links.iter", "links.yield", "links.exhausted", "proposal.observation_map",
            "proposal.observation_map", "proposal.obligations"])
        self.assertEqual(self.accesses("proposal:not_a_pass_result"), ["producer.enter"])
        for name in ("unknown_status", "unhashable_status"):
            self.assertEqual(self.accesses("proposal:" + name), ["producer.enter", "proposal.search_status"])
        for name in ("no_candidate", "no_candidate_with_output", "missing_candidate"):
            self.assertEqual(self.accesses("proposal:" + name), ["producer.enter", "proposal.search_status",
                "proposal.search_status", "proposal.output"])
        for name in ("wrong_schema", "missing_nodes", "unsupported_nodes", "conversion_raises"):
            self.assertNotIn("proposal.source_links", self.accesses("proposal:" + name))
        self.assertEqual(self.accesses("proposal:output_getter_raises")[-2:], ["proposal.output", "proposal.output"])
        self.assertNotIn("output.to_dict", self.accesses("proposal:output_getter_raises"))
        no_candidate = self.event("proposal:no_candidate")["exception"]
        self.assertEqual(no_candidate["class"], "biocompiler.compiler.pipeline.NoCandidateFound")
        self.assertEqual(set(mapping(no_candidate["attributes"])), {"pass_id", "configuration", "dependencies"})

    def test_links_materialize_before_validation_but_obligations_short_circuit(self):
        links = self.accesses("proposal:all_links_consumed_before_validation")
        self.assertEqual(links[-4:], ["links.iter", "links.yield", "links.yield", "links.exhausted"])
        self.assertNotIn("proposal.observation_map", links)
        obligations = self.accesses("proposal:obligation_access")
        self.assertEqual(obligations[-9:], ["obligations.iter", "obligations.yield", "obligation.requirement_id",
            "obligation.evidence_kind", "obligation.requirement_id", "obligation.description",
            "obligation.requirement_id", "obligation.evidence_refs", "obligations.exhausted"])
        short = self.accesses("proposal:obligation_short_circuit")
        self.assertEqual(short[-3:], ["obligations.iter", "obligations.yield", "obligation.requirement_id"])
        self.assertNotIn("obligations.exhausted", short)
        self.assertEqual(self.accesses("proposal:invalid_observation").count("proposal.observation_map"), 1)
        self.assertEqual(self.accesses("proposal:mapping_access")[-4:],
            ["mapping.iter", "mapping.iter", "mapping.getitem", "proposal.obligations"])
        self.assertNotIn("proposal.obligations", self.accesses("proposal:mapping_raises"))

    def test_input_conversion_precedes_eager_default_hash_and_identity_property(self):
        self.assertEqual(self.accesses("input:valid"), ["input.lookup.to_dict", "input.to_dict", "input.default_fingerprint",
            "input.lookup.fingerprint", "input.fingerprint"])
        self.assertEqual(self.accesses("input:conversion_raises"), ["input.lookup.to_dict", "input.to_dict"])
        self.assertEqual(self.accesses("input:identity_raises"), self.accesses("input:valid"))
        self.assertEqual(self.accesses("input:conversion_reentrant_root").count("input.default_fingerprint"), 2)
        self.assertEqual(set(self.records("input:conversion_reentrant_root")), {"inner", "input"})
        self.assertEqual(set(self.records("input:identity_raises")), set())
        mutated = mapping(self.records("input:identity_mutates")["input"]["fields"]["dependencies"])
        self.assertEqual(mutated["registry"], oracle.fingerprint("mutation"))

    def test_original_exception_object_tail_chains_and_baseexception_survive(self):
        markers = [event["exception"] for case in self.cases.values() for event in case["events"]
            if event["outcome"] == "raised" and event["exception"]["same_marker_object"]]
        self.assertEqual(len(markers), 19)
        self.assertTrue(all(error["retained_original_tail"] and error["required_user_traceback_tail"] for error in markers))
        chained = [error for error in markers if error["same_marker_cause"] is not None]
        self.assertTrue(chained)
        self.assertTrue(all(error["same_marker_cause"] and error["same_marker_context"] and error["suppress_context"] for error in chained))
        reused = [event["exception"] for event in self.cases["callback:exception_reused"]["events"] if event["outcome"] == "raised"]
        self.assertEqual(reused[0]["identity"], reused[1]["identity"])
        self.assertGreater(len(reused[1]["original_traceback"]), len(reused[0]["original_traceback"]))
        for name, kind in (("keyboard_interrupt", "builtins.KeyboardInterrupt"), ("system_exit", "builtins.SystemExit")):
            case = self.cases["callback:" + name]
            self.assertEqual(self.event(case["id"])["exception"]["class"], kind)
            self.assertEqual(case["events"][-1]["outcome"], "returned")
        self.assertEqual(self.event("callback:system_exit")["exception"]["system_exit_code"], "original marker")

    def test_nontransactional_callbacks_keep_inner_work_and_stored_stale_records(self):
        for name in ("producer_nested_run", "validator_nested_run"):
            self.assertEqual(set(self.records("callback:" + name)), {"input", "inner", "output"})
        self.assertEqual(set(self.records("callback:producer_nested_run_raises")), {"input", "inner"})
        self.assertEqual(set(self.records("admission:nested_admission")), {"inner", "outer"})
        self.assertEqual(set(self.records("admission:nested_admission_raises")), {"inner"})
        for name in ("proposal:conversion_mutates", "proposal:links_mutate", "callback:validator_mutates_returns", "callback:validator_registers"):
            self.assertEqual(self.event(name)["outcome"], "raised")
            self.assertTrue(self.records(name)["output"]["fields"]["accepted"])
        self.assertNotIn("output", self.records("callback:validator_mutates_raises"))
        self.assertEqual(mapping(fields(self.cases["callback:validator_mutates_raises"])["_dependencies"])["registry"],
            oracle.fingerprint("mutation"))

    def test_comparison_truth_coercion_can_mutate_raise_or_run_the_old_validator(self):
        self.assertEqual(self.accesses("equality:truthy_object"), ["old.equal", "comparison.truth"])
        self.assertEqual(self.accesses("equality:truth_raises"), ["old.equal", "comparison.truth"])
        self.assertEqual(self.event("equality:truth_raises", "register_replacement")["outcome"], "raised")
        nested = self.cases["equality:nested_run"]
        self.assertIn("old.call", self.accesses(nested["id"]))
        self.assertNotIn("new.call", self.accesses(nested["id"]))
        self.assertEqual(set(self.records(nested["id"])), {"input", "inner"})
        self.assertEqual(self.event(nested["id"], "nested_run")["parent"], self.event(nested["id"], "register_replacement")["id"])

    def test_observation_never_eagerly_runs_user_conversion_access_or_comparison(self):
        capture = oracle.Capture("observer-safety")
        class Explosive:
            def __getattribute__(self, name):
                raise AssertionError("Observer read a user attribute: " + name)
            def __eq__(self, other):
                raise AssertionError("Observer compared a user object")
        value = Explosive()
        observed = capture.safe(value)
        self.assertEqual(capture.safe(value), observed)
        payload = oracle.Payload(capture, "probe", {}, conversion=lambda: capture.raise_marker("unexpected"))
        mapping_value = oracle.TrackedMapping(capture, {}, fail=True)
        iterator = oracle.Items(capture, "probe", [], enter=lambda: capture.raise_marker("unexpected"))
        proposal = oracle.Proposal(capture, output=payload, links=iterator, observation=mapping_value)
        for value in (payload, mapping_value, iterator, proposal):
            self.assertIn("$object", capture.safe(value))
        self.assertEqual(capture.log, [])
        previous = sys.getprofile()
        oracle.input_case("valid")
        self.assertIs(sys.getprofile(), previous)

    def test_self_consistent_mutations_and_broader_runtime_normalization_are_rejected(self):
        for mutation in ("reviewed-message", "nearby-message", "nearby-access", "normalization-scope"):
            forged = deepcopy(self.current)
            cases = {case["id"]: case for case in forged["cases"]}
            if mutation == "reviewed-message":
                cases["proposal:unhashable_status"]["events"][1]["exception"]["message"] = "forged runtime message"
            elif mutation == "nearby-message":
                cases["proposal:unknown_status"]["events"][1]["exception"]["message"] = "forged adjacent rejection"
            elif mutation == "nearby-access":
                cases["proposal:valid"]["access_log"][1]["access"] = "eager_conversion"
            else:
                forged["runtime_counterparts"][0]["paths"].append("exception.class")
            resign(forged)
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                runtime.compare_current(self.value, forged)
            with self.assertRaisesRegex(AssertionError, "Immutable original"):
                validate(forged)


def load_tests(loader, tests, pattern):
    from tools.pipeline_original_counterpart import original_test_suite
    return original_test_suite(loader, tests, pattern, 'test_pipeline_deferred_semantics')


if __name__ == "__main__":
    unittest.main()

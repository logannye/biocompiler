"""Actual Python adapter/broker stack controls, never native acceptance."""
from copy import deepcopy
from functools import partial
import json
from pathlib import Path
import sys
import tempfile
import unittest

from biocompiler.core_client import CoreClient
from biocompiler.core_pipeline_callback_session import CorePipelineCallbackSession, capability_profile
from biocompiler.core_pipeline_manager import CorePassManager, capability_profile as application_profile
from biocompiler.pipeline_callback_objects import CallbackObjects
from tests.test_core_pipeline_callback_session import PEER
from tests.test_pipeline_manager_campaign import reframe
from tools import check_pipeline_manager_install as campaign
from tools import check_pipeline_manager_trace as trace


class PipelineManagerTraceTests(unittest.TestCase):
    def test_all_47_fresh_original_cases_have_closed_manager_segment_recipes(self):
        oracle = campaign.load_oracle(installed=False, deferred=True)
        fresh = oracle.capture()
        self.assertEqual(len(fresh['cases']), 47)
        segments = 0
        for case in fresh['cases']:
            for event in case['events']:
                if event['outcome'] != 'raised':
                    continue
                stack = event['exception']['original_traceback']
                cursor = 0
                while cursor < len(stack):
                    if stack[cursor]['file'] not in (trace.ORIGINAL, 'pipeline.py'):
                        cursor += 1
                        continue
                    start = cursor
                    while cursor < len(stack) and stack[cursor]['file'] in (trace.ORIGINAL, 'pipeline.py'):
                        cursor += 1
                    recipe = tuple((frame['function'], frame['line']) for frame in stack[start:cursor])
                    with self.subTest(case=case['id'], event=event['id'], recipe=recipe):
                        self.assertIn(recipe, set(trace.HOST_SEGMENTS) | trace.REJECTED_SEGMENTS)
                    segments += 1
        # One local immutable-context error has no manager segment; the reused
        # exception retains one additional earlier manager segment.
        self.assertEqual(segments, fresh['coverage']['raised_events'])

    def fixture(self, *, host=False, repeat=False, contains=False, comparison=False):
        directory = tempfile.TemporaryDirectory(prefix="pipeline-trace-")
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        oracle = campaign.load_oracle(installed=False, deferred=True)
        original_capture = oracle.Capture
        witness = campaign.DeferredWitness(oracle)
        objects = CallbackObjects()
        self.addCleanup(objects.close)
        descriptor = {"module": "biocompiler.compiler.pipeline", "type": "PipelineError",
            "message": "Pass returned an unknown search status.", "attributes": {}, "attributes_tree": ["object", []]}
        script = PEER.replace("if operation == 'call-host':", "if operation == 'register':" if comparison else "if operation == 'run':")
        if comparison:
            script = script.replace("elif operation == 'reject':", "elif operation == 'set-dependency':\n        outcome = {'status':'ok','value':None}\n    elif operation == 'reject':")
        script = script.replace("'action': command['arguments']['action'], 'arguments': command['arguments']['arguments']",
            "'action': 'compare', 'arguments': {'left': {'handle':'object/0'}, 'right': {'handle':'object/1'}, 'operator':'eq'}" if comparison else
            "'action': 'contains', 'arguments': {'item': {'handle':'object/0'}, 'container': {'handle':'object/1'}}" if contains else
            "'action': 'call', 'arguments': {'callable': {'handle':'object/0'}, 'args':[], 'kwargs':{}}")
        if not host:
            script = script.replace("outcome = invoke(value, raw)", "outcome = {'status':'rejected', 'value': REJECTION}")
        path = root / "peer"
        path.write_text(f"#!{sys.executable}\nDECLARATION={capability_profile()!r}\nAPPLICATION={application_profile()!r}\nREJECTION={descriptor!r}\n" + script)
        path.chmod(0o700)
        session = CorePipelineCallbackSession(CoreClient(path), application=application_profile(), objects=objects)
        self.addCleanup(session.close)
        manager = object.__new__(CorePassManager)
        manager._objects, manager._session = objects, session
        witness.managers.append(manager)
        with campaign.native_deferred_capture(oracle, None, None,
                retain_event=witness.event, retain_exception=witness.error):
            capture = object.__new__(oracle.Capture)
            capture.native_observer_ready = False
            original_capture.__init__(capture, "trace-control")
            capture.manager = campaign.GuardedManager(manager, set(), witness.observe)
            capture.native_observer_ready = True
            # This fixture validates the real exception stack only. Its state
            # observations are deliberately outside the native conformance gate.
            capture.snapshot = lambda: capture.initial
            witness.captures.append(capture)
            if comparison:
                objects.retain(oracle.EqualValidator(capture, 'old', 'mutation_raises'))
                objects.retain(oracle.EqualValidator(capture, 'new', 'mutation_raises'))
            elif contains:
                objects.retain([])
                objects.retain({'candidate', 'no_candidate_found'})
            else:
                objects.retain(partial(capture.raise_marker, "marker"))
            session.call('initialize-empty', {'target': capture.fixture.target.to_dict(), 'dependencies': [],
                'completion_profiles': [], 'manager_limits': None, 'target_object': objects.retain(capture.fixture.target)})
            if comparison:
                capture.register(partial(capture.raise_marker, 'marker'))
            else:
                capture.run()
            if repeat:
                capture.run("again")
        actual = {"id": "trace-control", "events": capture.events}
        evidence = witness.evidence()
        session.close()
        artifacts = root / "artifacts"
        artifacts.mkdir()
        receipt = {"_artifact_directory": str(artifacts), "artifacts": {}}
        rows = [{"direction": item.direction, "index": item.index,
            "frame": campaign.artifact(receipt, item.frame)} for item in session.traffic]
        details = {}
        campaign.validate_frames(rows, campaign.Artifacts(artifacts, receipt["artifacts"]),
            *campaign.declarations(), details=details, provider_calls=False)
        receipt['process'] = {'frames': rows}
        self.last_transport = receipt, receipt['process'], artifacts
        expected = deepcopy(actual)
        prefix = [{"file": trace.ORACLE, "function": "invoke", "line": 167},
            {"file": trace.ORACLE, "function": "<lambda>", "line": 225 if comparison else 229},
            {"file": trace.ORIGINAL, "function": "register" if comparison else "run", "line": 452 if comparison else 733 if contains else 730 if host else 734}]
        leaf = ([{"file": trace.ORACLE, "function": "__eq__", "line": 534},
            {"file": trace.ORACLE, "function": "raise_marker", "line": 205}] if comparison else
            [{"file": trace.ORACLE, "function": "raise_marker", "line": 210}] if host and not contains else [])
        for index, event in enumerate(expected["events"]):
            if event['outcome'] != 'raised':
                continue
            stack = prefix + leaf
            if index:
                stack += [{"file": trace.ORACLE, "function": "step", "line": 184}] + expected["events"][index-1]["exception"]["original_traceback"]
            event["exception"]["original_traceback"] = stack
            event["exception"]["required_user_traceback_tail"] = stack[3:] if leaf else []
        return actual, expected, evidence, [details]

    def test_actual_logical_adapter_stack_has_one_complete_segment(self):
        values = self.fixture()
        projected, correspondence = trace.projection(*values)
        self.assertEqual(projected, values[1])
        self.assertEqual(len(correspondence[0]["segments"]), 1)

    def test_actual_host_stack_preserves_original_object_and_retained_tail(self):
        values = self.fixture(host=True)
        projected, correspondence = trace.projection(*values)
        self.assertEqual(projected, values[1])
        self.assertEqual(len(correspondence[0]["segments"]), 1)
        host = values[2]["host_exceptions"][0]
        self.assertEqual(host["identity"], "exception/marker")
        self.assertEqual(host["rethrows"], [2])

    def test_actual_reused_exception_keeps_its_prior_request_stack(self):
        values = self.fixture(host=True, repeat=True)
        projected, correspondence = trace.projection(*values)
        self.assertEqual(projected, values[1])
        self.assertEqual(correspondence[-1]["segments"][-1]["prior_event"], 0)

    def test_registration_unit_and_nested_command_cannot_exchange_ownership(self):
        values = self.fixture(host=True, comparison=True)
        self.assertEqual(trace.projection(*values)[0], values[1])
        actual, expected, evidence, details = deepcopy(values)
        nested = next(item for item in details[0]['commands'] if item['operation'] == 'set-dependency')
        self.assertIsNotNone(nested['parent_invocation'])
        node = next(item for item in evidence['errors'][0]['traceback'] if item['qualname'] == 'CorePassManager._call')
        node['binding']['sequence'] = nested['sequence']
        with self.assertRaisesRegex(AssertionError, 'Bridge frame belongs to another command'):
            trace.projection(actual, expected, evidence, details)

    def test_rehashed_action_and_valid_source_site_substitution_is_rejected(self):
        for contains in (False, True):
            actual, expected, evidence, details = self.fixture(host=True, contains=contains)
            self.assertEqual(trace.projection(actual, expected, evidence, details)[0], expected)
            receipt, row, directory = self.last_transport
            def mutate(values):
                invocation = next(value for value in values if value['kind'] == 'invoke')
                invocation['action'] = 'iter'
                invocation['arguments'] = {'object': {'handle': 'object/0'}}
            reframe(receipt, row, mutate)
            repaired = {}
            campaign.validate_frames(row['frames'], campaign.Artifacts(directory, receipt['artifacts']),
                *campaign.declarations(), details=repaired, provider_calls=False)
            # Repair the corresponding pinned executable broker frame as well;
            # the intended rejection must be semantic, after valid framing.
            method = trace.source_nodes(trace.BROKER)['CallbackObjects._evaluate'][0]
            import ast
            line = next(node.lineno for node in ast.walk(method)
                if isinstance(node, ast.Call) and ast.unparse(node) == 'iter(value)')
            for chain in [evidence['errors'][0]['traceback'], evidence['host_exceptions'][0]['traceback']]:
                for node in chain:
                    if node['qualname'] == 'CallbackObjects._evaluate':
                        node['line'] = line
            chain = evidence['errors'][0]['traceback']
            error = actual['events'][0]['exception']
            error['original_traceback'] = [{'file': node['source'], 'function': node['function'], 'line': node['line']} for node in chain]
            error['required_user_traceback_tail'] = error['original_traceback'][evidence['errors'][0]['required_index']:]
            with self.subTest(contains=contains), self.assertRaisesRegex(AssertionError, 'Bridge action differs'):
                trace.projection(actual, expected, evidence, [repaired])

    def test_repaired_raw_frames_cannot_omit_duplicate_or_reorder_bridge(self):
        baseline = self.fixture(host=True)
        for mutation in ("omit", "duplicate", "reorder", "valid-other-site", "owning-request", "callback-parent"):
            actual, expected, evidence, details = deepcopy(baseline)
            chain = evidence["errors"][0]["traceback"]
            offset = next(index for index, item in enumerate(chain) if item["qualname"] == "CorePassManager.run")
            if mutation == "omit":
                chain.pop(offset)
            elif mutation == "duplicate":
                copied = deepcopy(chain[offset]); copied["node"] = "traceback/999"
                chain.insert(offset, copied)
            elif mutation == "reorder":
                chain[offset], chain[offset+1] = chain[offset+1], chain[offset]
            elif mutation == "valid-other-site":
                node = next(node for node in chain if node["qualname"] == "CorePassManager._call")
                method = trace.source_nodes(trace.MANAGER)["CorePassManager._call"][0]
                node["line"] = method.lineno
            else:
                name = "CorePassManager._call" if mutation == "owning-request" else "CallbackObjects.rethrow"
                node = next(node for node in chain if node["qualname"] == name)
                if mutation == "owning-request":
                    node["binding"]["sequence"] = 1  # Real earlier initialize reply.
                else:
                    node["binding"]["invocation"] += 1
            # Repair every corresponding raw frame rather than relying on a
            # checksum or raw/evidence disagreement to reject the mutation.
            error = actual["events"][0]["exception"]
            error["original_traceback"] = [{"file": item["source"], "function": item["function"], "line": item["line"]} for item in chain]
            required = next(index for index, item in enumerate(chain) if item["source"] == trace.ORACLE and item["function"] == "raise_marker")
            evidence["errors"][0]["required_index"] = required
            error["required_user_traceback_tail"] = error["original_traceback"][required:]
            with self.subTest(mutation=mutation), self.assertRaisesRegex(AssertionError, "Bridge"):
                trace.projection(actual, expected, evidence, details)

    def test_host_tail_node_identity_and_cause_are_not_text_projections(self):
        baseline = self.fixture(host=True)
        for mutation in ("tail", "cause", "successor"):
            actual, expected, evidence, details = deepcopy(baseline)
            host = evidence["host_exceptions"][0]
            if mutation == "tail":
                host["traceback"][-1]["node"] = "traceback/999"
            elif mutation == "cause":
                host["cause"] = "exception/other"
            else:
                host["traceback"] = host["traceback"][:-1]
            with self.subTest(mutation=mutation), self.assertRaisesRegex(AssertionError, "tail|successor|cause"):
                trace.projection(actual, expected, evidence, details)


if __name__ == "__main__":
    unittest.main()

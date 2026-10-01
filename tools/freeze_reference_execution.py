"""Retain complete, artificial reference-execution inputs and Python outcomes.

The original execution tests still run their independently authored assertions.
Full traces are labeled Python-oracle evidence; separately authored full-trace
literals and the existing case-B assertions are retained without regeneration.
No native program, molecular compiler, transport model or biological system runs.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import importlib.util
import io
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

import biocompiler as bc
from biocompiler.compiler.behavior import lower_to_behavior
from biocompiler.compiler.request import BuildRequest
from biocompiler.errors import EvaluationError, NonConvergenceError, StateConflictError
from biocompiler.ir.behavior import BehaviorProgram, BEHAVIOR_V2, SUPPORTED_KINDS, EXTENSION_KINDS
from biocompiler.ir.serialization import fingerprint
from biocompiler.semantics.evaluator import InputFrame, SignalSample, evaluate


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/reference-execution-v1.json"
SCHEMA = "biocompiler.reference_execution_conformance.v1"
TEST_FILES = ("tests/test_behavior_execution.py", "tests/test_payload_execution.py")
MAX_BYTES = 16 * 1024 * 1024
REQUIRED_LITERAL_CASES = {"literal/empty_role", "literal/report_onset", "literal/atomic_state_bool_to_int"}
REQUIRED_NUMERIC_CASES = {"numeric/mixed_int_float_compare", "numeric/integral_correct_rounding",
                        "numeric/signed_zero_product"}


def without_sources(program):
    document = program.to_dict()
    for node in document["nodes"] + document["requirements"]:
        node["source"] = None
    return BehaviorProgram.from_dict(document)


def empty_frame(time, *, reactions=None, actions=None, states=None, microsteps=1):
    """Literal frame contract, authored independently of evaluator output."""
    return {"time": time, "actions": [] if actions is None else actions,
            "reactions": [] if reactions is None else reactions, "events": [],
            "states": {} if states is None else states, "memories": {}, "microsteps": microsteps}


def literal_result(program, role, horizon, frames):
    return {"role": role, "horizon": horizon, "behavior_fingerprint": program.fingerprint,
            "source_fingerprint": program.source_fingerprint,
            "execution_profile": program.policies["profile"], "frames": frames}


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def load_module(relative, name):
    specification = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def relocate(value):
    if isinstance(value, dict):
        value = {key: relocate(item) for key, item in value.items()}
        if set(value) == {"file", "line", "function"}:
            path = Path(value["file"])
            if path.is_absolute():
                value["file"] = path.resolve().relative_to(ROOT).as_posix()
        return value
    if isinstance(value, (tuple, list)):
        return [relocate(item) for item in value]
    return value


def frame_from_dict(value):
    def samples(values):
        return {key: SignalSample(**sample) if isinstance(sample, dict) else SignalSample(value=sample)
                for key, sample in values.items()}
    return InputFrame(value["time"], samples(value["signals"]),
                      {key: samples(items) for key, items in value["contacts"].items()})


def options(case):
    return {"role": case["role"], "until": case["until"], "max_microsteps": case["max_microsteps"]}


def error_code(error):
    message = str(error).lower()
    if isinstance(error, StateConflictError): return "evaluation_state_conflict"
    if isinstance(error, NonConvergenceError): return "evaluation_nonconvergence"
    if "10000" in message: return "evaluation_integration_limit"
    if "integration" in message or "integral" in message: return "evaluation_integration"
    if "division by zero" in message or "arithmetic" in message: return "evaluation_arithmetic"
    if "timer" in message or "advance" in message: return "evaluation_timer"
    if "observation scope" in message: return "evaluation_scope"
    if "role" in message and "unknown signal" not in message: return "evaluation_role"
    if "history" in message or "timestamp" in message: return "evaluation_history"
    if "horizon" in message: return "evaluation_horizon"
    if "microsteps" in message: return "evaluation_microsteps"
    if "observation" in message or "unknown signal" in message: return "evaluation_observation"
    raise AssertionError("Unclassified evaluator failure: " + str(error))


class Corpus:
    def __init__(self):
        self.programs = {}
        self.cases = []
        self.rejections = []
        self.parser_rejections = []
        self.source_tests = []
        self.exclusions = []
        self.literal_expectations = []
        self.literal_assertions = []
        self.case_b_assertions = []

    def program(self, value):
        normalized = BehaviorProgram.from_dict(relocate(value.to_dict()))
        require(normalized.fingerprint == value.fingerprint, "Diagnostic relocation changed Behavior semantic identity")
        document = normalized.to_dict()
        identity = fingerprint(document)
        self.programs.setdefault(identity, {"id": identity, "behavior": document,
                                            "behavior_fingerprint": normalized.fingerprint})
        return identity, normalized

    def run(self, identity, program, history, *, evidence="python_oracle", expected=None, **kwargs):
        history = tuple(history)
        program_id, normalized = self.program(program)
        case = {"id": identity, "program_id": program_id, "history": [item.to_dict() for item in history],
                "role": kwargs.get("role"), "until": kwargs.get("until"),
                "max_microsteps": kwargs.get("max_microsteps", 1000), "evidence": evidence}
        try:
            result = evaluate(program, history, **kwargs)
        except EvaluationError as error:
            case.update(expected_stage="evaluation", expected_code=error_code(error),
                        python_error=str(error).replace(str(ROOT) + "/", ""))
            self.rejections.append(case)
            raise
        trace = relocate(result.to_dict())
        require(encoded(evaluate(normalized, history, **kwargs).to_dict()) == encoded(trace),
                "Relocated execution changed complete trace " + identity)
        if expected is not None:
            require(encoded(trace) == encoded(expected), "Independent complete trace literal differs: " + identity)
            self.literal_expectations.append({"case_id": identity, "expected_trace": expected})
        case.update(expected_trace=trace, trace_fingerprint=fingerprint(trace))
        self.cases.append(case)
        return result

    def capture_tests(self):
        for relative in TEST_FILES:
            module = load_module(relative, "reference_execution_" + Path(relative).stem)
            corpus = self
            current = {"id": None, "calls": 0, "data_errors": 0}

            class RecordedResult(unittest.TextTestResult):
                def startTest(self, test):
                    current.update(id=relative + "::" + test.id().split(".", 1)[1], calls=0, data_errors=0)
                    super().startTest(test)

                def stopTest(self, test):
                    corpus.source_tests.append({"id": current["id"], "evaluation_calls": current["calls"],
                                                "data_rejections": current["data_errors"]})
                    if current["calls"] == 0 and current["data_errors"] == 0:
                        corpus.exclusions.append({"source_test": current["id"],
                            "reason": "Original test exercises authoring, manifest or lowering boundaries and makes no evaluator/data invocation; its assertions still pass."})
                    super().stopTest(test)

            def captured(program, history, **kwargs):
                current["calls"] += 1
                return corpus.run("source_test/" + current["id"] + "/" + str(current["calls"]),
                                  program, history, evidence="python_oracle_with_existing_test_assertions", **kwargs)

            def constructor(original, names, defaults, kind):
                def wrapped(*args, **kwargs):
                    try:
                        return original(*args, **kwargs)
                    except EvaluationError as error:
                        current["data_errors"] += 1
                        values = {**defaults, **dict(zip(names, args)), **kwargs}
                        def plain(value):
                            if hasattr(value, "to_dict"): return value.to_dict()
                            if isinstance(value, dict): return {key: plain(item) for key, item in value.items()}
                            return value
                        values = plain(values)
                        text = json.dumps(values, sort_keys=True, ensure_ascii=True, allow_nan=True)
                        raw_nonfinite = any(token in text for token in ("NaN", "Infinity"))
                        if raw_nonfinite:
                            code, stage = "invalid_json", "json"
                        elif kind == "input_frame" and "nonnegative" in str(error):
                            code, stage = "execution_data_time", "decode"
                        elif "not a Boolean" in str(error):
                            code, stage = "evaluation_numeric_type", "decode"
                        else:
                            code, stage = "invalid_type", "decode"
                        corpus.parser_rejections.append({"id": "source_test_data/" + current["id"] + "/" + str(current["data_errors"]),
                            "record_kind": kind, "input_json": text, "expected_stage": stage, "expected_code": code,
                            "python_error": str(error)})
                        raise
                return wrapped

            runner = unittest.TextTestRunner(stream=io.StringIO(), resultclass=RecordedResult, verbosity=0)
            with patch.object(module, "evaluate", captured), \
                 patch.object(module, "SignalSample", constructor(SignalSample,
                    ("value", "present", "high", "low"), dict(value=None, present=None, high=None, low=None), "sample")), \
                 patch.object(module, "InputFrame", constructor(InputFrame, ("time", "signals", "contacts"),
                    dict(signals={}, contacts={}), "input_frame")):
                outcome = runner.run(unittest.defaultTestLoader.loadTestsFromModule(module))
            require(outcome.wasSuccessful(), "Existing independently asserted execution tests failed: " + repr(outcome.errors + outcome.failures))

    def case_b(self):
        expectations = json.loads((ROOT / "tests/conformance/case-b/expectations.json").read_bytes())
        for variant in ("base", "parameter-default", "parameter-override"):
            data = json.loads((ROOT / "tests/conformance/case-b" / variant / "candidate.json").read_bytes())
            program = BehaviorProgram.from_dict(data["execution"]["behavior"])
            signals = {node.attributes["name"]: node.id for node in program.nodes if node.kind == "signal"}
            state = next(node.id for node in program.nodes if node.kind == "state")
            for timeline in expectations["timelines"]:
                history = [InputFrame(frame["time"], {signals[name]: SignalSample(present=value)
                           for name, value in frame["present"].items()}) for frame in timeline["inputs"]]
                identity = "case_b/" + variant + "/" + timeline["id"]
                evidence = ("python_oracle_with_retained_case_b_literals" if variant in timeline["variants"]
                            else "python_oracle_additional_case_b_parameter_combination")
                result = self.run(identity, program, history, until=timeline["horizon"], evidence=evidence)
                if variant in timeline["variants"]:
                    projected = [{"time": frame.time, "state": frame.states[state],
                                  "secretion_count": sum(action.kind == "action.secrete" for action in frame.actions)}
                                 for frame in result.frames]
                    require(encoded(projected) == encoded(timeline["frames"]), "Independent case-B timeline changed")
                    self.case_b_assertions.append({"case_id": identity, "state_id": state,
                                                   "expected": deepcopy(timeline["frames"])})

    def broad(self):
        data = json.loads((ROOT / "tests/conformance/behavior-domains-v1.json").read_bytes())
        for case in data["cases"]:
            program = BehaviorProgram.from_dict(case["behavior"])
            for role in (node for node in program.nodes if node.kind == "role"):
                signals = [node for node in program.nodes if node.role == role.id and node.kind in {"signal", "channel_observation"}]
                history = []
                for time, truth, amount in ((0, True, 1), (1, False, 0), (2, True, 3), (3, True, 0)):
                    local, contact = {}, {}
                    for node in signals:
                        target = contact if node.contact_bound else local
                        target[node.id] = SignalSample(value=amount, present=truth, high=truth, low=not truth)
                    history.append(InputFrame(time, local, {"artificial_contact": contact} if contact else {}))
                self.run("broad/" + case["id"] + "/" + role.id, program, history, role=role.id, until=4)

    def independent_literals(self):
        therapy = bc.Therapy("literal_empty_role")
        cells = therapy.engineer("cell", cell_type="abstract_cell")
        program = without_sources(lower_to_behavior(therapy.freeze()))
        self.run("literal/empty_role", program, [InputFrame(0)], until=2,
                 evidence="independently_authored_complete_trace",
                 expected=literal_result(program, "n000001", 2, [empty_frame(0), empty_frame(2)]))

        therapy = bc.Therapy("literal_report_onset")
        cells = therapy.engineer("cell", cell_type="abstract_cell")
        signal = cells.environment.signal("go")
        report = cells.report("observed")
        cells.when(signal.present()).do(report)
        program = without_sources(lower_to_behavior(therapy.freeze()))
        request = {"action_id": "n000004", "rule_id": "n000006", "kind": "action.report",
                   "contact_id": None, "attributes": {"ongoing": False, "label": "observed"},
                   "values": {}, "requirement_ids": ["requirement:n000006"],
                   "source": None, "rule_source": None, "started_at": 0, "expires_at": None,
                   "specification_id": "n000004", "specification_source": None}
        self.run("literal/report_onset", program,
                 [InputFrame(0, {signal.node_id: SignalSample(present=True)})], until=1,
                 evidence="independently_authored_complete_trace",
                 expected=literal_result(program, "n000001", 1,
                    [empty_frame(0, reactions=[request]), empty_frame(1)]))

        therapy = bc.Therapy("literal_atomic_state")
        cells = therapy.engineer("cell", cell_type="abstract_cell")
        signal = cells.environment.signal("go")
        state = cells.state("phase", values=(False, 0, "ready"), initial=False)
        cells.when(signal.present()).do(state.set(0))
        program = without_sources(lower_to_behavior(therapy.freeze()))
        self.run("literal/atomic_state_bool_to_int", program,
                 [InputFrame(0, {signal.node_id: SignalSample(present=True)})], until=1,
                 evidence="independently_authored_complete_trace",
                 expected=literal_result(program, "n000001", 1,
                    [empty_frame(0, states={"n000004": 0}, microsteps=2),
                     empty_frame(1, states={"n000004": 0})]))

    def numeric_and_boundaries(self):
        def model(name):
            therapy = bc.Therapy(name)
            cells = therapy.engineer("cell", cell_type="abstract_cell")
            return therapy, cells, cells.environment.signal("value")

        therapy, cells, signal = model("literal_mixed_compare")
        report = cells.report("greater")
        cells.when(signal > bc.Level(float(2 ** 53))).do(report)
        program = without_sources(lower_to_behavior(therapy.freeze()))
        result = self.run("numeric/mixed_int_float_compare", program,
                          [InputFrame(0, {signal.node_id: 2 ** 53 + 1})])
        self.assert_reactions("numeric/mixed_int_float_compare", result, [0])

        therapy, cells, signal = model("literal_fsum_integral")
        report = cells.report("exact_sum")
        cells.when(signal.integrated(over=bc.Duration(10)) >= bc.Duration(9007199254740994.0)).do(report)
        request = BuildRequest.freeze(therapy.freeze(), behavior_profile=BEHAVIOR_V2,
            implementation_constraints={"execution": {"integral_step": bc.Duration(1).to_dict()}})
        program = without_sources(lower_to_behavior(request))
        result = self.run("numeric/integral_correct_rounding", program,
                          [InputFrame(0, {signal.node_id: 2 ** 53}),
                           InputFrame(1, {signal.node_id: 1}), InputFrame(2, {signal.node_id: 1})], until=3)
        self.assert_reactions("numeric/integral_correct_rounding", result, [3])

        therapy, cells, signal = model("literal_signed_zero")
        action = cells.secrete("ARTIFICIAL", rate=bc.ProductionRate(1) * signal)
        cells.when(signal >= bc.Level(0)).do(action)
        program = without_sources(lower_to_behavior(therapy.freeze()))
        result = self.run("numeric/signed_zero_product", program, [InputFrame(-0.0, {signal.node_id: -0.0})])
        value = result.to_dict()["frames"][0]["actions"][0]["values"]["rate"]
        require(encoded(value) == b"-0.0\n", "Signed zero was not preserved")
        self.literal_assertions.append({"case_id": "numeric/signed_zero_product",
                                       "projection": "first_action_rate", "expected": -0.0})

        therapy, cells, signal = model("literal_overflow")
        cells.when((signal + bc.Level(2 ** 1023)) > bc.Level(0)).do(cells.rest())
        overflow = without_sources(lower_to_behavior(therapy.freeze()))
        self.reject("numeric/finite_integer_sum_overflow", overflow, [InputFrame(0, {signal.node_id: 2 ** 1023})])

        therapy, cells, signal = model("literal_nonadvancing_timer")
        cells.when(signal.present().held_for(bc.Duration(1))).do(cells.report("deadline"))
        program = without_sources(lower_to_behavior(therapy.freeze()))
        history = [InputFrame(0, {signal.node_id: SignalSample(present=False)}),
                   InputFrame(float(2 ** 53), {signal.node_id: SignalSample(present=True)})]
        self.reject("numeric/nonadvancing_timer", program, history)
        self.reject("boundary/unknown_role", program, history[:1], role="absent")
        self.reject("boundary/negative_horizon", program, history[:1], until=-1)
        self.reject("boundary/zero_microsteps", program, history[:1], max_microsteps=0)
        self.reject("boundary/boolean_microsteps", program, history[:1], max_microsteps=True)
        self.reject("boundary/unknown_observation", program, [InputFrame(0, {"absent": 1})])
        self.reject("boundary/contact_observation_in_local_scope", program,
                    [InputFrame(0, contacts={"contact": {signal.node_id: SignalSample(present=True)}})])

    def reject(self, identity, program, history, **kwargs):
        try:
            self.run(identity, program, history, **kwargs)
        except EvaluationError:
            return
        raise AssertionError("Expected evaluator rejection " + identity)

    def assert_reactions(self, identity, result, expected):
        observed = [frame.time for frame in result.frames for _ in frame.reactions]
        require(encoded(observed) == encoded(expected), "Independent reaction-time assertion failed " + identity)
        self.literal_assertions.append({"case_id": identity, "projection": "reaction_times", "expected": expected})

    def strict_parser_literals(self):
        samples = {"value": None, "present": None, "high": None, "low": None}
        records = [
            ("sample_missing", "sample", {"value": 0}, "decode", "missing_field"),
            ("sample_unknown", "sample", {**samples, "extra": None}, "decode", "unknown_field"),
            ("sample_qualitative_integer", "sample", {**samples, "present": 1}, "decode", "invalid_type"),
            ("frame_missing", "input_frame", {"time": 0, "signals": {}}, "decode", "missing_field"),
            ("frame_boolean_time", "input_frame", {"time": True, "signals": {}, "contacts": {}}, "decode", "evaluation_numeric_type"),
            ("frame_blank_signal", "input_frame", {"time": 0, "signals": {"\u2003": samples}, "contacts": {}}, "decode", "invalid_name"),
            ("frame_blank_contact", "input_frame", {"time": 0, "signals": {}, "contacts": {" ": {}}}, "decode", "invalid_name"),
        ]
        for name, kind, value, stage, code in records:
            self.parser_rejections.append({"id": "strict_data/" + name, "record_kind": kind,
                "input_json": json.dumps(value, sort_keys=True), "expected_stage": stage, "expected_code": code,
                "python_error": None, "evidence": "independently_authored_strict_native_boundary"})
        for name, raw, code in (
            ("sample_duplicate", '{"value":null,"value":0,"present":null,"high":null,"low":null}', "duplicate_key"),
            ("sample_nonfinite_number", '{"value":1e999,"present":null,"high":null,"low":null}', "nonfinite_number"),
        ):
            self.parser_rejections.append({"id": "strict_data/" + name, "record_kind": "sample",
                "input_json": raw, "expected_stage": "json", "expected_code": code,
                "python_error": None, "evidence": "independently_authored_strict_native_boundary"})


def reachable_kinds(program, role):
    nodes = {node.id: node for node in program.nodes}
    seen, pending = set(), [ref for ref in program.roots if nodes[ref].role in (None, role)]
    while pending:
        ref = pending.pop()
        if ref in seen: continue
        seen.add(ref)
        node = nodes[ref]
        pending.extend(node.inputs[:1] if node.kind == "signature" else node.inputs)
    return {node.kind for node in program.nodes if node.id in seen and node.role in (None, role)}


def coverage(document):
    programs = {item["id"]: BehaviorProgram.from_dict(item["behavior"]) for item in document["programs"]}
    reachable, actions = set(), set()
    witnesses = {kind: [] for kind in sorted(SUPPORTED_KINDS | EXTENSION_KINDS)}
    by_profile = {}
    for case in document["cases"]:
        program = programs[case["program_id"]]
        kinds = reachable_kinds(program, case["expected_trace"]["role"])
        reachable.update(kinds)
        by_profile.setdefault(program.schema_version, set()).update(kinds)
        for kind in kinds:
            witnesses[kind].append(case["id"])
        for frame in case["expected_trace"]["frames"]:
            actions.update(action["kind"] for action in frame["actions"] + frame["reactions"])
    return {"supported_kinds": sorted(SUPPORTED_KINDS), "extension_kinds": sorted(EXTENSION_KINDS),
            "reachable_kinds": sorted(reachable), "uncovered_kinds": sorted((SUPPORTED_KINDS | EXTENSION_KINDS) - reachable),
            "emitted_action_kinds": sorted(actions), "profiles": sorted({p.schema_version for p in programs.values()}),
            "operation_witnesses": {kind: sorted(values) for kind, values in witnesses.items()},
            "by_profile": {key: sorted(value) for key, value in sorted(by_profile.items())},
            "independent_complete_trace_count": len(document["literal_expectations"]),
            "independent_projection_count": len(document["literal_assertions"]),
            "program_count": len(programs), "positive_count": len(document["cases"]),
            "evaluation_rejection_count": len(document["rejections"]), "parser_rejection_count": len(document["parser_rejections"]),
            "source_test_count": len(document["source_tests"]), "case_b_count": sum(case["id"].startswith("case_b/") for case in document["cases"])}


def build_corpus():
    corpus = Corpus()
    corpus.capture_tests()
    corpus.case_b()
    corpus.broad()
    corpus.independent_literals()
    corpus.numeric_and_boundaries()
    corpus.strict_parser_literals()
    document = {"schema_version": SCHEMA,
        "claim_scope": "Complete abstract per-role reference execution over supplied artificial observations; no coupled transport, physical implementation, biological validation, architecture acceptance or human admission.",
        "programs": list(corpus.programs.values()), "cases": corpus.cases, "rejections": corpus.rejections,
        "parser_rejections": corpus.parser_rejections, "source_tests": corpus.source_tests,
        "exclusions": corpus.exclusions, "literal_expectations": corpus.literal_expectations,
        "literal_assertions": corpus.literal_assertions, "case_b_assertions": corpus.case_b_assertions}
    document["coverage"] = coverage(document)
    return document


class ParserFailure(ValueError):
    pass


def parser_failure_code(case):
    """Independent shape checks for the new strict, bounded import contract.

    The legacy Python data constructors have defaults instead of exact JSON
    fields; these checks deliberately do not claim legacy import equivalence.
    Semantic field values still use the original Python data constructors.
    """
    def fail(code):
        raise ParserFailure(code)

    def pairs(values):
        result = {}
        for key, value in values:
            if key in result: fail("duplicate_key")
            result[key] = value
        return result

    def finite_float(token):
        result = float(token)
        if not math.isfinite(result): fail("nonfinite_number")
        return result

    try:
        value = json.loads(case["input_json"], object_pairs_hook=pairs, parse_float=finite_float,
                           parse_constant=lambda _: fail("invalid_json"))
    except ParserFailure as error:
        return "json", str(error)
    except json.JSONDecodeError:
        return "json", "invalid_json"
    expected_fields = ({"value", "present", "high", "low"} if case["record_kind"] == "sample"
                       else {"time", "signals", "contacts"})
    if not isinstance(value, dict): return "decode", "invalid_type"
    if set(value) - expected_fields: return "decode", "unknown_field"
    if expected_fields - set(value): return "decode", "missing_field"
    try:
        if case["record_kind"] == "sample":
            SignalSample(**value)
        else:
            frame_from_dict(value)
    except EvaluationError as error:
        message = str(error)
        if "not a Boolean" in message: return "decode", "evaluation_numeric_type"
        if "nonnegative" in message: return "decode", "execution_data_time"
        if "nonempty string" in message: return "decode", "invalid_name"
        return "decode", "invalid_type"
    raise AssertionError("Parser accepted intended rejection " + case["id"])


def resource_usage(document):
    nodes, deepest, largest_string = 0, 0, 0
    pending = [(document, 0)]
    while pending:
        value, depth = pending.pop()
        nodes += 1
        deepest = max(deepest, depth)
        if isinstance(value, dict):
            pending.extend((item, depth + 1) for item in value.values())
            largest_string = max(largest_string, *(len(key.encode("utf-8")) for key in value), 0)
        elif isinstance(value, list):
            pending.extend((item, depth + 1) for item in value)
        elif isinstance(value, str):
            largest_string = max(largest_string, len(value.encode("utf-8")))
    return {"bytes": len(encoded(document)), "nodes": nodes, "depth": deepest, "max_string_bytes": largest_string}


def check_corpus(document):
    require(document["schema_version"] == SCHEMA, "Wrong reference-execution corpus schema")
    programs = {}
    for item in document["programs"]:
        program = BehaviorProgram.from_dict(item["behavior"])
        require(fingerprint(program.to_dict()) == item["id"], "Wrong full program identity")
        require(program.fingerprint == item["behavior_fingerprint"], "Wrong semantic program identity")
        require(item["id"] not in programs, "Duplicate program identity")
        programs[item["id"]] = program
    identities = [case["id"] for field in ("cases", "rejections", "parser_rejections") for case in document[field]]
    require(len(identities) == len(set(identities)), "Duplicate execution fixture identity")
    for case in document["cases"]:
        result = evaluate(programs[case["program_id"]], [frame_from_dict(frame) for frame in case["history"]], **options(case))
        require(encoded(result.to_dict()) == encoded(case["expected_trace"]), "Complete trace mismatch " + case["id"])
        require(fingerprint(result.to_dict()) == case["trace_fingerprint"], "Wrong trace fingerprint " + case["id"])
    for case in document["rejections"]:
        require(case["expected_stage"] == "evaluation", "Wrong evaluator rejection stage")
        try:
            evaluate(programs[case["program_id"]], [frame_from_dict(frame) for frame in case["history"]], **options(case))
        except EvaluationError as error:
            require(error_code(error) == case["expected_code"], "Wrong evaluator failure " + case["id"])
        else:
            raise AssertionError("Evaluator accepted intended rejection " + case["id"])
    for case in document["parser_rejections"]:
        require(case["record_kind"] in {"sample", "input_frame"}, "Unknown data parser record kind")
        require(parser_failure_code(case) == (case["expected_stage"], case["expected_code"]),
                "Wrong data parser failure " + case["id"])
    by_id = {case["id"]: case for case in document["cases"]}
    require({row["case_id"] for row in document["literal_expectations"]} == REQUIRED_LITERAL_CASES,
            "Missing independent complete-trace literals")
    for literal in document["literal_expectations"]:
        case = by_id[literal["case_id"]]
        require(case["evidence"] == "independently_authored_complete_trace", "Wrong literal evidence category")
        require(encoded(literal["expected_trace"]) == encoded(case["expected_trace"]), "Independent trace literal drifted")
    require({row["case_id"] for row in document["literal_assertions"]} == REQUIRED_NUMERIC_CASES,
            "Missing independent numeric assertions")
    for literal in document["literal_assertions"]:
        trace = by_id[literal["case_id"]]["expected_trace"]
        if literal["projection"] == "reaction_times":
            value = [frame["time"] for frame in trace["frames"] for _ in frame["reactions"]]
        else:
            require(literal["projection"] == "first_action_rate", "Unknown independent projection")
            value = trace["frames"][0]["actions"][0]["values"]["rate"]
        require(encoded(value) == encoded(literal["expected"]), "Independent numeric assertion drifted")
    expected_case_b = {case["id"] for case in document["cases"]
                       if case["evidence"] == "python_oracle_with_retained_case_b_literals"}
    require({item["case_id"] for item in document["case_b_assertions"]} == expected_case_b,
            "Missing independent case-B assertions")
    for literal in document["case_b_assertions"]:
        trace = by_id[literal["case_id"]]["expected_trace"]
        projected = [{"time": frame["time"], "state": frame["states"][literal["state_id"]],
                      "secretion_count": sum(action["kind"] == "action.secrete" for action in frame["actions"])}
                     for frame in trace["frames"]]
        require(encoded(projected) == encoded(literal["expected"]), "Independent case-B assertion drifted")
    require(len(document["source_tests"]) == 61, "Missing original source test ledger")
    for test in document["source_tests"]:
        prefix = "source_test/" + test["id"] + "/"
        cases = [case for case in document["cases"] + document["rejections"] if case["id"].startswith(prefix)]
        require(len(cases) == test["evaluation_calls"], "Source test evaluator accounting drifted")
        prefix = "source_test_data/" + test["id"] + "/"
        cases = [case for case in document["parser_rejections"] if case["id"].startswith(prefix)]
        require(len(cases) == test["data_rejections"], "Source test data accounting drifted")
    excluded = {item["id"] for item in document["source_tests"] if not item["evaluation_calls"] and not item["data_rejections"]}
    require(excluded == {item["source_test"] for item in document["exclusions"]}, "Missing source test exclusion ledger")
    require(document["coverage"] == coverage(document), "Execution coverage drifted")
    require(not document["coverage"]["uncovered_kinds"], "Execution operation coverage incomplete")
    require(document["coverage"]["case_b_count"] == 24, "Missing original case-B variant/timeline coverage")
    require(len(document["cases"]) >= 86 and len(document["rejections"]) >= 23
            and len(document["parser_rejections"]) >= 16, "Execution cases missing from mandatory corpus")
    usage = resource_usage(document)
    require(usage["bytes"] < MAX_BYTES and usage["nodes"] <= 250_000 and usage["depth"] <= 128
            and usage["max_string_bytes"] <= 4 * 1024 * 1024, "Execution corpus exceeds native parser budget")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=CORPUS)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    document = build_corpus()
    check_corpus(document)
    content = encoded(document)
    require(len(content) < MAX_BYTES, "Execution corpus exceeds native read budget")
    if args.write: args.output.write_bytes(content)
    else:
        retained = args.output.read_bytes()
        check_corpus(json.loads(retained))
        require(content == retained, "Reference-execution corpus drifted; inspect before refreezing")
    counts = {key: value for key, value in document["coverage"].items() if key.endswith("count")}
    print(json.dumps({"status": "written" if args.write else "checked", **resource_usage(document), **counts,
                      "covered_kinds": len(document["coverage"]["reachable_kinds"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

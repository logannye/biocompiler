"""Observe deferred user-code behavior in the unchanged original Python manager.

Objects under test are retained by identity. Observation never calls their
conversion, iteration, equality, property getters or exception string hooks.
Only the original manager invokes those hooks. The resulting ledger is an
independent comparison oracle, never accepted state or a callback completion
that can be imported to manufacture native acceptance.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import fields, replace
from enum import Enum
import hashlib
import json
from pathlib import Path
import sys
from types import MappingProxyType

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]
from biocompiler.artifacts.provenance import SourceLink
from biocompiler.compiler.passes import PassResult
from biocompiler.compiler import pipeline
from biocompiler.ir.serialization import fingerprint
from biocompiler.verification.evidence import CheckOutcome, EvidenceKind
from test_pipeline import PipelineTests, accepted, document
from test_component_admission import ComponentAdmissionTests

OUTPUT = ROOT / "tests/conformance/pipeline-deferred-semantics-v1.json"
SAFE_CLASSES = {pipeline.ScopedObligation, pipeline.CheckSpec, pipeline.CheckDecision,
    pipeline.PassContract, pipeline.PassContext, pipeline.ComponentInputContract,
    pipeline.CompletionProfile, pipeline.StageRecord, pipeline.PipelineResult,
    SourceLink}
USER_CODES = set()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def qualified(value):
    cls = type(value)
    module = "tools.capture_pipeline_deferred_semantics" if cls.__module__ in ("__main__", __name__) else cls.__module__
    return module + "." + cls.__qualname__


def user(function):
    USER_CODES.add(function.__code__)
    return function


def trace_frames(traceback):
    frames = []
    while traceback is not None:
        code = traceback.tb_frame.f_code
        path = Path(code.co_filename)
        try:
            name = path.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            name = path.name
        frames.append({"file": name, "function": code.co_name, "line": traceback.tb_lineno})
        traceback = traceback.tb_next
    return frames


class MarkerError(ValueError):
    pass


class Capture:
    def __init__(self, name, *, admission=False):
        self.name, self.admission = name, admission
        self.objects, self.log, self.events, self.stack = [], [], [], []
        self.markers, self.marker_tails, self.marker_causes, self.marker_contexts = {}, {}, {}, {}
        self.profiling = False
        self.recipes, self.providers = [], {}
        self.fixture = ComponentAdmissionTests() if admission else PipelineTests()
        self.fixture.setUp()
        self.manager = self.fixture.manager
        self.contract = self.fixture.policy if admission else self.fixture.first
        self.second_contract = replace(self.contract, version="2")
        self.initial = self.snapshot()

    def handle(self, value, label=None):
        for previous, identity in self.objects:
            if previous is value:
                return identity
        identity = label or "object/" + str(len(self.objects))
        if any(previous == identity for _, previous in self.objects):
            raise AssertionError("Duplicate fixture object handle")
        self.objects.append((value, identity))
        return identity

    def safe(self, value):
        if value is None or type(value) in (str, bool, int, float):
            return value
        if issubclass(type(value), Enum):
            return {"$enum": qualified(value), "value": value.value}
        if type(value) in (dict, MappingProxyType):
            return {"$mapping": qualified(value), "items": [[self.safe(key), self.safe(item)] for key, item in value.items()]}
        if type(value) in (list, tuple):
            return {"$sequence": type(value).__name__, "items": [self.safe(item) for item in value]}
        if type(value) in SAFE_CLASSES or type(value) is type(self.fixture.target):
            return {"$dataclass": qualified(value), "fields": {
                field.name: self.safe(object.__getattribute__(value, field.name)) for field in fields(type(value))}}
        return {"$object": self.handle(value), "class": qualified(value)}

    def access(self, name, **values):
        self.log.append({"ordinal": len(self.log), "parent": self.stack[-1] if self.stack else None,
            "access": name, "values": self.safe(values)})

    def snapshot(self):
        return self.safe(vars(self.manager))

    def exception(self, error):
        traceback = object.__getattribute__(error, "__traceback__")
        cause = object.__getattribute__(error, "__cause__")
        context = object.__getattribute__(error, "__context__")
        required = traceback
        while required is not None and required.tb_frame.f_code not in USER_CODES:
            required = required.tb_next
        tail = self.marker_tails.get(id(error))
        current, retained = traceback, False
        while current is not None:
            retained |= current is tail
            current = current.tb_next
        return {"identity": self.handle(error), "class": qualified(error),
            "args": self.safe(object.__getattribute__(error, "args")),
            "attributes": self.safe(object.__getattribute__(error, "__dict__")),
            "system_exit_code": self.safe(object.__getattribute__(error, "code")) if type(error) is SystemExit else None,
            "message": BaseException.__str__(error),
            "cause": None if cause is None else self.handle(cause),
            "context": None if context is None else self.handle(context),
            "suppress_context": object.__getattribute__(error, "__suppress_context__"),
            "original_traceback": trace_frames(traceback), "required_user_traceback_tail": trace_frames(required),
            "same_marker_object": any(error is marker for marker in self.markers.values()),
            "retained_original_tail": retained if tail is not None else None,
            "same_marker_cause": cause is self.marker_causes.get(id(error)) if id(error) in self.marker_causes else None,
            "same_marker_context": context is self.marker_contexts.get(id(error)) if id(error) in self.marker_contexts else None}

    def invoke(self, operation, action, **arguments):
        identity = len(self.events)
        event = {"id": identity, "parent": self.stack[-1] if self.stack else None,
            "operation": operation, "arguments": self.safe(arguments), "before": self.snapshot(),
            "access_start": len(self.log)}
        self.events.append(event)
        self.stack.append(identity)
        previous_profile = sys.getprofile()
        observing = self.name.startswith("input:") and not self.profiling
        def profile(frame, event, result):
            if event == "call" and frame.f_code is fingerprint.__code__ and frame.f_back is not None and \
                    frame.f_back.f_code is pipeline.PassManager.add_input.__code__:
                self.access("input.default_fingerprint", document=frame.f_locals["value"])
            if previous_profile is not None:
                previous_profile(frame, event, result)
        if observing:
            self.profiling = True
            sys.setprofile(profile)
        try:
            result = action()
        except BaseException as error:
            event.update(outcome="raised", exception=self.exception(error))
            raise
        else:
            event.update(outcome="returned", result=self.safe(result))
            return result
        finally:
            if observing:
                sys.setprofile(previous_profile)
                self.profiling = False
            event.update(after=self.snapshot(), access_end=len(self.log))
            assert self.stack.pop() == identity

    def step(self, operation, action, **arguments):
        self.recipes.append({"operation": operation, "arguments": self.safe(arguments)})
        try:
            return self.invoke(operation, action, **arguments)
        except BaseException:
            return None

    def marker(self, label="marker", kind=MarkerError):
        if label not in self.markers:
            error = kind("original " + label)
            self.markers[label] = error
            self.handle(error, "exception/" + label)
        return self.markers[label]

    @user
    def raise_marker(self, label="marker", *, chained=False, kind=MarkerError):
        error = self.marker(label, kind)
        if chained:
            cause, context = self.marker("cause", RuntimeError), self.marker("context", LookupError)
            self.marker_causes[id(error)], self.marker_contexts[id(error)] = cause, context
            try:
                raise context
            except LookupError:
                try:
                    raise error from cause
                except BaseException:
                    self.marker_tails[id(error)] = error.__traceback__
                    raise
        try:
            raise error
        except BaseException:
            self.marker_tails[id(error)] = error.__traceback__
            raise

    def provider(self, label, function):
        self.handle(function, "provider/" + label)
        self.providers[label] = {"identity": self.handle(function), "class": qualified(function)}
        return function

    def register(self, producer, validator=None, *, contract=None):
        contract = self.contract if contract is None else contract
        validator = accepted if validator is None else validator
        self.provider("producer", producer)
        self.provider("validator", validator)
        self.step("register", lambda: self.manager.register(contract, producer,
            {contract.checks[0].id: validator}), contract=contract, producer=producer, validator=validator)

    def run(self, identity="output"):
        return self.step("run", lambda: self.manager.run(self.contract.id, "input", identity),
            pass_id=self.contract.id, input_id="input", output_id=identity)

    def final(self):
        assert not self.stack
        return {"id": self.name, "mode": "admission" if self.admission else "pass", "initial_state": self.initial,
            "recipes": self.recipes, "providers": self.providers, "events": self.events,
            "access_log": self.log, "final_state": self.snapshot(),
            "objects": [{"identity": identity, "class": qualified(value)} for value, identity in self.objects]}


class Payload:
    def __init__(self, capture, label, value, *, conversion=None, identity=None):
        self.capture, self.label, self.value, self.conversion, self.identity = capture, label, value, conversion, identity
        capture.handle(self, "payload/" + label)

    @user
    def __getattribute__(self, name):
        if name in ("to_dict", "fingerprint"):
            object.__getattribute__(self, "capture").access(object.__getattribute__(self, "label") + ".lookup." + name)
        return object.__getattribute__(self, name)

    @user
    def to_dict(self):
        self.capture.access(self.label + ".to_dict")
        if self.conversion is not None:
            self.conversion()
        return self.value

    @property
    @user
    def fingerprint(self):
        self.capture.access(self.label + ".fingerprint")
        return self.identity() if callable(self.identity) else self.identity


class Proposal(PassResult):
    def __init__(self, capture, *, output, links, obligations=(), observation=None, status="candidate", hooks=None):
        super().__init__(output, obligations, links, {} if observation is None else observation, status)
        object.__setattr__(self, "capture", capture)
        object.__setattr__(self, "hooks", {} if hooks is None else hooks)
        object.__setattr__(self, "reads", {})
        capture.handle(self, "proposal")

    @user
    def __getattribute__(self, name):
        if name in ("output", "source_links", "obligations", "observation_map", "search_status"):
            capture = object.__getattribute__(self, "capture")
            reads = object.__getattribute__(self, "reads")
            reads[name] = reads.get(name, 0) + 1
            capture.access("proposal." + name, occurrence=reads[name])
            hook = object.__getattribute__(self, "hooks").get((name, reads[name]))
            if hook is not None:
                hook()
        return object.__getattribute__(self, name)


class Items:
    def __init__(self, capture, label, values, *, enter=None, after=None):
        self.capture, self.label, self.values, self.enter, self.after = capture, label, values, enter, after
        capture.handle(self, "iterator/" + label)

    @user
    def __iter__(self):
        self.capture.access(self.label + ".iter")
        if self.enter is not None:
            self.enter()
        for index, value in enumerate(self.values):
            self.capture.access(self.label + ".yield", index=index)
            yield value
        self.capture.access(self.label + ".exhausted")
        if self.after is not None:
            self.after()


class TrackedMapping(Mapping):
    def __init__(self, capture, values, *, fail=False):
        self.capture, self.values, self.fail = capture, values, fail
        capture.handle(self, "mapping")

    @user
    def __iter__(self):
        self.capture.access("mapping.iter")
        return iter(self.values)

    @user
    def __len__(self):
        self.capture.access("mapping.len")
        return len(self.values)

    @user
    def __getitem__(self, key):
        self.capture.access("mapping.getitem", key=key)
        if self.fail:
            self.capture.raise_marker("mapping")
        return self.values[key]


class TrackedObligation:
    def __init__(self, capture, *, invalid=False):
        self.capture = capture
        self.requirement_id = "absent" if invalid else "identity"
        self.evidence_kind, self.description, self.evidence_refs = EvidenceKind.EXACT, "Preserve value.", ()
        capture.handle(self, "obligation")

    @user
    def __getattribute__(self, name):
        if name in ("requirement_id", "evidence_kind", "description", "evidence_refs"):
            object.__getattribute__(self, "capture").access("obligation." + name)
        return object.__getattribute__(self, name)


def change_dependency(capture):
    capture.invoke("set_dependency", lambda: capture.manager.set_dependency("registry", fingerprint("mutation")),
        key="registry", identity=fingerprint("mutation"))


def proposal_case(name):
    capture = Capture("proposal:" + name)
    payload = Payload(capture, "output", document("behavior.v1"))
    links = Items(capture, "links", [SourceLink("r", "n", "n", capture.contract.id)])
    options = {"output": payload, "links": links}
    if name == "unknown_status":
        options["status"] = "infeasible"
    elif name == "unhashable_status":
        options["status"] = []
    elif name == "no_candidate":
        options.update(status="no_candidate_found", output=None)
    elif name == "no_candidate_with_output":
        options["status"] = "no_candidate_found"
    elif name == "missing_candidate":
        options["output"] = None
    elif name == "output_getter_raises":
        options["hooks"] = {("output", 2): lambda: capture.raise_marker("output")}
    elif name == "wrong_schema":
        payload.value = document("wrong.v1")
    elif name == "missing_nodes":
        payload.value = {"schema_version": "behavior.v1", "nodes": None}
    elif name == "unsupported_nodes":
        payload.value = document("behavior.v1", kind="unimplemented")
    elif name == "conversion_raises":
        payload.conversion = lambda: capture.raise_marker("conversion")
    elif name == "conversion_mutates":
        payload.conversion = lambda: change_dependency(capture)
    elif name == "links_iterator_raises":
        links.enter = lambda: capture.raise_marker("links")
    elif name == "links_exhaustion_raises":
        links.after = lambda: capture.raise_marker("links-end")
    elif name == "all_links_consumed_before_validation":
        links.values = [object(), SourceLink("r", "n", "n", capture.contract.id)]
    elif name == "links_mutate":
        links.enter = lambda: change_dependency(capture)
    elif name == "invalid_observation":
        options["observation"] = ["not a mapping"]
    elif name == "mapping_access":
        options["observation"] = TrackedMapping(capture, {"output": "n"})
    elif name == "mapping_raises":
        options["observation"] = TrackedMapping(capture, {"output": "n"}, fail=True)
    elif name == "obligation_access":
        options["obligations"] = Items(capture, "obligations", [TrackedObligation(capture)])
    elif name == "obligation_short_circuit":
        options["obligations"] = Items(capture, "obligations", [TrackedObligation(capture, invalid=True), object()],
            after=lambda: capture.raise_marker("unreachable"))
    elif name == "obligation_exhaustion_raises":
        options["obligations"] = Items(capture, "obligations", [], after=lambda: capture.raise_marker("obligations-end"))
    elif name not in ("valid", "not_a_pass_result"):
        raise AssertionError(name)
    proposal = object() if name == "not_a_pass_result" else Proposal(capture, **options)
    @user
    def produce(context):
        capture.access("producer.enter", context=context)
        return proposal
    capture.register(produce)
    capture.run()
    capture.step("get-input", lambda: capture.manager.get("input"), identity="input")
    return capture.final()


def input_case(name):
    capture = Capture("input:" + name)
    # A fresh manager permits authoritative root entry. No state is imported.
    capture.manager = pipeline.PassManager(target=capture.fixture.target,
        dependencies={"request": fingerprint(capture.fixture.input), "registry": fingerprint("v1")})
    capture.initial = capture.snapshot()
    payload = Payload(capture, "input", capture.fixture.input, identity=fingerprint(capture.fixture.input))
    if name == "identity_raises":
        payload.identity = lambda: capture.raise_marker("identity")
    elif name == "conversion_raises":
        payload.conversion = lambda: capture.raise_marker("conversion")
    elif name == "wrong_identity":
        payload.identity = fingerprint("different")
    elif name == "conversion_reentrant_root":
        payload.conversion = lambda: capture.invoke("add_input", lambda: capture.manager.add_input("inner", capture.fixture.input), identity="inner")
    elif name == "identity_mutates":
        def identity():
            change_dependency(capture)
            return fingerprint(capture.fixture.input)
        payload.identity = identity
    elif name != "valid":
        raise AssertionError(name)
    capture.step("add_input", lambda: capture.manager.add_input("input", payload), identity="input", payload=payload)
    capture.step("target", lambda: capture.manager.target)
    return capture.final()


def callback_case(name):
    capture = Capture("callback:" + name)
    entered = False
    valid = lambda: PassResult(document("behavior.v1"), (), (SourceLink("r", "n", "n", capture.contract.id),))
    @user
    def produce(context):
        nonlocal entered
        capture.access("producer.enter", context=context)
        if name == "producer_mutates_raises":
            change_dependency(capture)
            capture.raise_marker(chained=True)
        if name in ("producer_nested_run", "producer_nested_run_raises") and not entered:
            entered = True
            capture.invoke("nested_run", lambda: capture.manager.run(capture.contract.id, "input", "inner"), output_id="inner")
            if name.endswith("raises"):
                capture.raise_marker(chained=True)
        if name in ("exception_reused", "keyboard_interrupt", "system_exit"):
            capture.raise_marker(kind={"keyboard_interrupt": KeyboardInterrupt, "system_exit": SystemExit}.get(name, MarkerError))
        return valid()
    @user
    def validate(context):
        nonlocal entered
        capture.access("validator.enter", context=context)
        if name in ("validator_mutates_returns", "validator_mutates_raises"):
            change_dependency(capture)
            if name.endswith("raises"):
                capture.raise_marker(chained=True)
        elif name == "validator_registers":
            capture.invoke("register_version2", lambda: capture.manager.register(capture.second_contract,
                produce, {capture.contract.checks[0].id: validate}), contract=capture.second_contract)
        elif name == "validator_nested_run" and not entered:
            entered = True
            capture.invoke("nested_run", lambda: capture.manager.run(capture.contract.id, "input", "inner"), output_id="inner")
        elif name == "context_immutable":
            capture.step("context_mutation", lambda: context.dependencies.__setitem__("registry", "changed"))
            capture.invoke("target", lambda: capture.manager.target)
            capture.invoke("result", lambda: capture.manager.result("input", scope="synthetic"), identity="input", scope="synthetic")
        return accepted(context)
    capture.register(produce, validate)
    capture.run()
    if name == "exception_reused":
        capture.run("second")
    capture.step("get-input", lambda: capture.manager.get("input"), identity="input")
    return capture.final()


def admission_case(name):
    capture = Capture("admission:" + name, admission=True)
    entered = False
    @user
    def validate(context):
        nonlocal entered
        capture.access("admission_validator.enter", context=context)
        if name in ("nested_admission", "nested_admission_raises") and not entered:
            entered = True
            capture.invoke("nested_admission", lambda: capture.manager.admit_component_input(capture.contract.id,
                "inner", capture.fixture.payload), identity="inner")
            if name.endswith("raises"):
                capture.raise_marker(chained=True)
        elif name == "mutation_raises":
            change_dependency(capture)
            capture.raise_marker(chained=True)
        return accepted(context)
    capture.provider("validator", validate)
    capture.step("register_component_input", lambda: capture.manager.register_component_input(capture.contract,
        {capture.contract.checks[0].id: validate}), contract=capture.contract, validator=validate)
    capture.step("admit_component_input", lambda: capture.manager.admit_component_input(capture.contract.id,
        "outer", capture.fixture.payload), identity="outer", payload=capture.fixture.payload)
    capture.step("target", lambda: capture.manager.target)
    return capture.final()


class Truth:
    def __init__(self, capture, fail):
        self.capture, self.fail = capture, fail
        capture.handle(self, "truth")

    @user
    def __bool__(self):
        self.capture.access("comparison.truth")
        change_dependency(self.capture)
        if self.fail:
            self.capture.raise_marker("truth", chained=True)
        return True


class EqualValidator:
    def __init__(self, capture, label, mode):
        self.capture, self.label, self.mode = capture, label, mode
        capture.provider(label, self)

    @user
    def __eq__(self, other):
        self.capture.access(self.label + ".equal", other=other)
        if self.mode in ("truthy_object", "truth_raises"):
            return Truth(self.capture, self.mode == "truth_raises")
        if self.mode == "nested_run":
            self.capture.invoke("nested_run", lambda: self.capture.manager.run(self.capture.contract.id, "input", "inner"), output_id="inner")
        else:
            change_dependency(self.capture)
            self.capture.raise_marker("equality", chained=True)
        return True

    @user
    def __call__(self, context):
        self.capture.access(self.label + ".call", context=context)
        return accepted(context)


def equality_case(name):
    capture = Capture("equality:" + name)
    @user
    def produce(context):
        capture.access("producer.enter", context=context)
        return PassResult(document("behavior.v1"), (), (SourceLink("r", "n", "n", capture.contract.id),))
    old, new = EqualValidator(capture, "old", name), EqualValidator(capture, "new", name)
    capture.register(produce, old)
    capture.step("register_replacement", lambda: capture.manager.register(capture.contract, produce,
        {capture.contract.checks[0].id: new}), producer=produce, validator=new)
    capture.step("get-input", lambda: capture.manager.get("input"), identity="input")
    return capture.final()


def capture():
    cases = []
    cases.extend(proposal_case(name) for name in (
        "valid", "not_a_pass_result", "unknown_status", "unhashable_status", "no_candidate", "no_candidate_with_output",
        "missing_candidate", "output_getter_raises", "wrong_schema", "missing_nodes", "unsupported_nodes",
        "conversion_raises", "conversion_mutates", "links_iterator_raises", "links_exhaustion_raises",
        "all_links_consumed_before_validation", "links_mutate", "invalid_observation", "mapping_access", "mapping_raises",
        "obligation_access", "obligation_short_circuit", "obligation_exhaustion_raises"))
    cases.extend(input_case(name) for name in ("valid", "identity_raises", "conversion_raises", "wrong_identity",
        "conversion_reentrant_root", "identity_mutates"))
    cases.extend(callback_case(name) for name in ("producer_mutates_raises", "producer_nested_run", "producer_nested_run_raises",
        "validator_mutates_returns", "validator_mutates_raises", "validator_registers", "validator_nested_run",
        "context_immutable", "exception_reused", "keyboard_interrupt", "system_exit"))
    cases.extend(admission_case(name) for name in ("nested_admission", "nested_admission_raises", "mutation_raises"))
    cases.extend(equality_case(name) for name in ("truthy_object", "truth_raises", "nested_run", "mutation_raises"))
    sources = ["tools/capture_pipeline_deferred_semantics.py", "tests/test_pipeline.py", "tests/test_component_admission.py",
        "src/biocompiler/compiler/pipeline.py", "src/biocompiler/compiler/passes.py", "src/biocompiler/artifacts/provenance.py",
        "src/biocompiler/ir/intent.py", "src/biocompiler/ir/serialization.py", "src/biocompiler/ir/stages.py",
        "src/biocompiler/semantics/context.py", "src/biocompiler/verification/evidence.py"]
    result = {"schema_version": "biocompiler.pipeline_deferred_semantics.v1",
        "claim_scope": "actual_unchanged_original_manager_user_callback_order_effects_and_exception_identity_no_native_acceptance",
        "source_files": {path: sha((ROOT / path).read_bytes()) for path in sources}, "cases": cases,
        "capture_runtime": {"implementation": sys.implementation.name, "python": list(sys.version_info[:2])},
        "runtime_counterparts": [{"case": "proposal:unhashable_status", "event": 1,
            "paths": ["exception.message", "exception.args.items.0"],
            "original_operation": "list_membership_in_candidate_status_set",
            "required_authority": "fresh_original_same_runtime_manager_and_primitive_exact_error"}],
        "coverage": {"cases": len(cases), "events": sum(len(case["events"]) for case in cases),
            "accesses": sum(len(case["access_log"]) for case in cases),
            "raised_events": sum(event["outcome"] == "raised" for case in cases for event in case["events"]),
            "nested_events": sum(event["parent"] is not None for case in cases for event in case["events"]),
            "marker_exceptions": sum(event["outcome"] == "raised" and event["exception"]["same_marker_object"] for case in cases for event in case["events"])}}
    result["inventory_fingerprint"] = sha(canonical(result))
    return result


def compare_current(frozen, current):
    """Check all bytes semantically, with one independently executed runtime axis.

    This does not verify a native manager. A later native replay must retain its
    own complete observations and compare them with the fresh original runtime
    counterpart. The immutable captured exception is never overwritten.
    """
    def require(value, message):
        if not value:
            raise AssertionError(message)
    for document in (frozen, current):
        require(document["inventory_fingerprint"] == sha(canonical({key: value for key, value in document.items()
            if key != "inventory_fingerprint"})), "Deferred observation inventory changed")
    require(current["capture_runtime"] == {"implementation": sys.implementation.name, "python": list(sys.version_info[:2])},
            "Fresh original observation has the wrong current runtime")
    required = [{"case": "proposal:unhashable_status", "event": 1,
        "paths": ["exception.message", "exception.args.items.0"],
        "original_operation": "list_membership_in_candidate_status_set",
        "required_authority": "fresh_original_same_runtime_manager_and_primitive_exact_error"}]
    require(frozen["runtime_counterparts"] == current["runtime_counterparts"] == required,
            "Unreviewed deferred exception normalization")
    original = next(case for case in frozen["cases"] if case["id"] == required[0]["case"])
    actual = next(case for case in current["cases"] if case["id"] == required[0]["case"])
    independent = proposal_case("unhashable_status")
    require(canonical(actual) == canonical(independent), "Complete same-runtime original manager counterpart differs")
    try:
        [] in {"candidate", "no_candidate_found"}
    except TypeError as error:
        primitive = {"class": qualified(error), "message": BaseException.__str__(error), "args": list(error.args)}
    else:
        raise AssertionError("Original unhashable membership stopped raising")
    exception = actual["events"][1]["exception"]
    require(exception["class"] == primitive["class"] == "builtins.TypeError" and
        exception["message"] == primitive["message"] and exception["args"] == {"$sequence": "tuple", "items": primitive["args"]},
        "Original manager exception differs from the fresh runtime primitive")
    expected = deepcopy(frozen)
    expected["capture_runtime"] = current["capture_runtime"]
    selected = next(case for case in expected["cases"] if case["id"] == required[0]["case"])["events"][1]["exception"]
    selected["message"] = exception["message"]
    selected["args"]["items"][0] = exception["args"]["items"][0]
    require(canonical({key: value for key, value in expected.items() if key != "inventory_fingerprint"}) ==
        canonical({key: value for key, value in current.items() if key != "inventory_fingerprint"}),
        "Complete original deferred observations changed outside the reviewed runtime fields")
    return {"captured_runtime": frozen["capture_runtime"], "current_runtime": current["capture_runtime"],
        "exact_paths": required[0], "complete_captured_case": original, "complete_current_case": actual,
        "independent_original_manager_case": independent, "runtime_primitive": primitive}


if __name__ == "__main__":
    if OUTPUT.exists():
        raise SystemExit("Refusing to replace the original deferred-semantics oracle")
    value = capture()
    OUTPUT.write_bytes(canonical(value) + b"\n")
    print(json.dumps({"inventory_fingerprint": value["inventory_fingerprint"], **value["coverage"]}, sort_keys=True))

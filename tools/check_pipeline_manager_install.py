"""Installed live-manager replay with complete original identity/order evidence.

Only fresh native sessions decide registration, freshness and acceptance. The
unchanged original case functions execute real host callbacks; saved outcomes
are comparison data only. This additive gate does not close the complete
original manager-context or fixed-registration-interception inventory.
"""
from __future__ import annotations
if __package__:
    from .check_realization_binaries import executable_path as native_executable
else:
    from check_realization_binaries import executable_path as native_executable


import argparse
import builtins
from contextlib import contextmanager
from functools import lru_cache
from copy import deepcopy
from dataclasses import field, make_dataclass
import gzip
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import selectors
import signal
import subprocess
import sys
import time
from types import CodeType, FunctionType, MappingProxyType
from types import SimpleNamespace
from uuid import UUID, uuid4

if __package__:
    from . import check_workflow_reproducibility as r
    from . import check_pipeline_session_install as fixed
    from . import check_pipeline_manager_trace as trace
else:
    import check_workflow_reproducibility as r
    import check_pipeline_session_install as fixed
    import check_pipeline_manager_trace as trace

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "biocompiler.installed_pipeline_manager_conformance.v1"
SCOPE = "five_identity_34_comparison_and_47_deferred_cases_complete_live_evidence_not_full_manager_cutover"
RECEIPT_FILE, ARTIFACT_DIRECTORY = "pipeline-manager.json", "pipeline-manager-artifacts"
ARGUMENT = "--pipeline-callback-session-v1"
CHANNEL_PATH = "protocol/pipeline-callback-channel-v1.json"
APPLICATION_PATH = "protocol/pipeline-callback-manager-v1.json"
ORACLES = {
    "identity": ("pipeline-identity-semantics-v1.json", "7088dd2f6ad6db60f30e2541f770b73691ff0b0d98950839ef7c4c4ed1d50896"),
    "callbacks": ("pipeline-callback-semantics-v1.json", "51df70cc9716117743d550d8f3af6a467da8334e7fd47a30993cfc53f5988ed0"),
    "deferred": ("pipeline-deferred-semantics-v1.json", "df12526c636cf2b3a51856494558080156c45c58573d7dbc2241daed54275129"),
    "full": ("checked-pipeline-full-v1.json", "8c9702c131e19af9a9950402c06a554cb531d81789cd83f51a23f0e5ba0fac44"),
}
TRANSPORT_MODULES = {"biocompiler.core_client", "biocompiler.core_pipeline_session",
    "biocompiler.core_pipeline_callback_session", "biocompiler.pipeline_callback_objects", "biocompiler.core_pipeline_manager",
    "biocompiler.core_pipeline_provider_views", "biocompiler.core_pipeline_build_views"}
LITERAL_MODULES = {"biocompiler.compiler.pipeline", "biocompiler.compiler.passes", "biocompiler.ir.intent",
    "biocompiler.ir.serialization", "biocompiler.ir.stages", "biocompiler.errors", "biocompiler.artifacts.provenance",
    "biocompiler.semantics.context", "biocompiler.verification.evidence"}
# These modules retain their semantic implementations, so they are never literal
# modules. Only the listed serialization roots and their actual nested code are
# available to the installed adapter. The source receipts include every module.
SERIALIZER_ROOTS = {
    "biocompiler.compiler.request": ("BuildRequest.to_dict", "ElaborationProvenance.to_dict",
        "RealizationRequest.target", "RealizationRequest.to_dict"),
    "biocompiler.ir.behavior": ("BehaviorNode.to_dict", "BehaviorProgram.to_dict"),
    "biocompiler.ir.component_assembly": ("ComponentAssembly.to_dict",),
    "biocompiler.ir.component_contracts": ("_Record.to_dict",),
    "biocompiler.ir.components": ("ComponentLock.to_dict",),
    "biocompiler.ir.composition": ("CompositionRequest.to_dict", "_Record.to_dict"),
    "biocompiler.ir.mechanism": ("MechanismNode.to_dict", "MechanismProgram.to_dict"),
    "biocompiler.registry.components": ("ComponentRegistry.to_dict", "RegistryLock.to_dict"),
    "biocompiler.semantics.component_contracts": ("OperatingDomain.to_dict", "PortContract.to_dict", "ValueDomain.to_dict"),
    "biocompiler.semantics.contracts": ("BehaviorRequirement.to_dict",),
    "biocompiler.semantics.evaluator": ("InputFrame.to_dict", "SignalSample.to_dict"),
    "biocompiler.semantics.realization": ("BehaviorContract.to_dict", "InputDomain.to_dict", "Observable.to_dict",
        "OperatingDomain.to_dict", "ResponseRequirement.to_dict"),
    "biocompiler.semantics.types": ("Interval.to_dict", "ScalarLiteral.to_dict", "TypeSpec.to_dict"),
    "biocompiler.synthesis.synthetic": ("SyntheticCandidate.to_dict", "SyntheticGeneratorConfig.to_dict"),
    "biocompiler.verification.realization": ("InputBinding.to_dict", "ObservationMap.to_dict", "OutputBinding.to_dict"),
}
# BehaviorNode.to_dict constructs an IntentNode in the unchanged public model.
# Its incidental type validation is permitted ONLY on that exact conversion
# stack, never as an independently callable Python semantic backend.
CONVERSION_ROOTS = {"biocompiler.semantics.types": (
    "TypeSpec.__post_init__", "TypeSpec.from_dict", "TypeSpec.compatible", "TypeSpec.__init__", "TypeSpec.__eq__",
    "ScalarLiteral.__init__", "_ScalarType.__new__", "_number", "decode_binding", "to_type_spec")}
# Python 3.11 emits these exact comprehension frames; 3.14 inlines them.
# This finite census correspondence is data-only. Live execution still needs
# the actual runtime code object, module globals, and conversion ancestry.
SERIALIZER_CENSUS_COMPREHENSIONS = {
    'biocompiler.compiler.request': (
        'BuildRequest.to_dict.<locals>.<dictcomp>',
    ),
    'biocompiler.ir.behavior': (
        'BehaviorProgram.to_dict.<locals>.<listcomp>',
    ),
    'biocompiler.ir.component_assembly': (
        'ComponentAssembly.to_dict.<locals>.<dictcomp>',
        'ComponentAssembly.to_dict.<locals>.<listcomp>',
    ),
    'biocompiler.ir.component_contracts': (
        '_Record.to_dict.<locals>.<dictcomp>',
        '_Record.to_dict.<locals>.encode.<locals>.<dictcomp>',
        '_Record.to_dict.<locals>.encode.<locals>.<listcomp>',
    ),
    'biocompiler.ir.composition': (
        'CompositionRequest.to_dict.<locals>.<dictcomp>',
        'CompositionRequest.to_dict.<locals>.<dictcomp>.<listcomp>',
        '_Record.to_dict.<locals>.<listcomp>',
    ),
    'biocompiler.ir.mechanism': (
        'MechanismProgram.to_dict.<locals>.<listcomp>',
    ),
    'biocompiler.registry.components': (
        'ComponentRegistry.to_dict.<locals>.<listcomp>',
        'RegistryLock.to_dict.<locals>.<listcomp>',
    ),
    'biocompiler.semantics.component_contracts': (
        'OperatingDomain.to_dict.<locals>.<dictcomp>',
        'PortContract.to_dict.<locals>.<dictcomp>',
    ),
    'biocompiler.semantics.evaluator': (
        'InputFrame.to_dict.<locals>.<dictcomp>',
        'InputFrame.to_dict.<locals>.<dictcomp>.<dictcomp>',
        'SignalSample.to_dict.<locals>.<dictcomp>',
    ),
    'biocompiler.semantics.realization': (
        'BehaviorContract.to_dict.<locals>.<listcomp>',
        'OperatingDomain.to_dict.<locals>.<listcomp>',
    ),
    'biocompiler.semantics.types': (
        'TypeSpec.to_dict.<locals>.<listcomp>',
        'decode_binding.<locals>.<listcomp>',
    ),
    'biocompiler.synthesis.synthetic': (
        'SyntheticCandidate.to_dict.<locals>.<listcomp>',
    ),
    'biocompiler.verification.realization': (
        'ObservationMap.to_dict.<locals>.<listcomp>',
    ),
}
REVIEWED_MODULES = TRANSPORT_MODULES | LITERAL_MODULES | set(SERIALIZER_ROOTS)


SOURCES = ("tools/check_pipeline_manager_install.py", "tests/test_pipeline_manager_campaign.py",
    "tools/check_pipeline_manager_trace.py", "tests/test_pipeline_manager_trace.py",
    "tools/manager_registration_source_lineage.py", "tools/pipeline_original_counterpart.py",
    "tools/pipeline_registration_guard.py", "tests/test_manager_registration_source_lineage.py",
    "tests/test_core_pipeline_registration_interception.py",
    "tests/conformance/manager-registration-runtime-sites-v1.json",
    "tests/conformance/manager-registration-runtime-sites-v2.json",
    "tests/conformance/manager-registration-runtime-sites-v3.json",
    "tests/conformance/manager-registration-runtime-sites-v4.json",
    "tests/conformance/manager-registration-runtime-sites-v5.json",
    "tests/conformance/manager-registration-runtime-sites-v6.json",
    "tests/conformance/reference-manager-source-counterpart-v5.json",
    "tests/conformance/manager-registration-tool-lineage-v1.json",
    "tests/conformance/manager-registration-source-lineage-v1.json",
    "tools/check_pipeline_session_install.py", "tools/check_workflow_reproducibility.py", "tools/check_realization_binaries.py",
    "tools/capture_pipeline_identity_semantics.py", "tests/test_pipeline_identity_semantics.py",
    "tools/capture_pipeline_callback_semantics.py", "tests/test_pipeline_callback_semantics.py",
    "tools/capture_pipeline_deferred_semantics.py", "tests/test_pipeline_deferred_semantics.py",
    "tools/check_pipeline_deferred_runtime.py", "tests/test_pipeline_deferred_runtime.py",
    "tools/check_pipeline_deferred_runtime_receipt.py", "tests/test_pipeline_deferred_runtime_receipt.py", CHANNEL_PATH, APPLICATION_PATH)
CASES = ("run:sharing_and_order", "run:nested_returns", "run:nested_raises",
         "run:validator_mutates_snapshot", "admission:sharing_and_order")
COVERAGE = {"cases": 5, "events": 34, "records": 10}
COMPARISON_COVERAGE = {"cases": 34, "manager_events": 78, "comparison_events": 28, "raised_events": 18}
COMPARISON_ORDINARY = ("identity_shortcut", "default_identity_distinct", "bound_method_equivalent",
    "equal", "unequal", "raises", "reflected_not_implemented", "subclass_reflection", "mutation_true",
    "mutation_raises", "reentrant_reads", "reentrant_registration", "history_restore")
COMPARISON_PRODUCER = ("same_callable_cannot_self_certify", "distinct_callable_roles_skip_equality",
    "distinct_equal_bound_method_roles", "bound_producer_identity_change")
COMPARISON_CASES = tuple(mode + ":" + name for mode in ("pass", "admission") for name in
    (*COMPARISON_ORDINARY, "comparison_order", "comparison_short_circuit")) + tuple("pass:" + name for name in COMPARISON_PRODUCER)
STATE_MAPS = ("dependencies", "passes", "component_inputs", "provider_history", "component_input_history", "records", "profiles")
REGISTRATION_MAPS = ("passes", "component_inputs", "provider_history", "component_input_history")
DEFERRED_COVERAGE = {"cases": 47, "events": 157, "accesses": 290, "raised_events": 45,
    "nested_events": 21, "marker_exceptions": 19}
canonical, require, equal = r.canonical, r.require, fixed.equal
sha = lambda raw: hashlib.sha256(raw).hexdigest()
artifact, Artifacts = fixed.artifact, r.Artifacts


def declarations():
    channel, _ = r.read(ROOT / CHANNEL_PATH)
    application, _ = r.read(ROOT / APPLICATION_PATH)
    require(application["argument"] == ARGUMENT and application["channel"] == channel["protocol"],
            "Manager application and continuation channel disagree")
    return channel, application


class Corpus:
    def __init__(self):
        self.oracles, self.pins, self.original_sources = {}, {}, {}
        for label, (name, pin) in ORACLES.items():
            value, actual = r.read(ROOT / "tests/conformance" / name)
            require(actual == pin, "Original manager oracle changed: " + name)
            if label != "full":
                require(value["inventory_fingerprint"] == r.digest({key: item for key, item in value.items()
                        if key != "inventory_fingerprint"}), "Original manager oracle inventory differs")
                for path, identity in value["source_files"].items():
                    require(not Path(path).is_absolute() and ".." not in Path(path).parts and r.pin(identity),
                            "Unsafe original oracle source")
                    fixed.source_tool("realization_source_lineage").verify_captured_source(ROOT, {"path": path, "sha256": identity})
                    self.original_sources[path] = identity
            self.oracles[label], self.pins[label] = value, {"path": "tests/conformance/" + name, "sha256": actual,
                "inventory_fingerprint": value["inventory_fingerprint"]}
        self.cases = self.oracles["identity"]["cases"]
        self.comparisons = self.oracles["callbacks"]["cases"]
        self.deferred = self.oracles["deferred"]["cases"]
        equal(self.oracles["deferred"]["coverage"], DEFERRED_COVERAGE, "Original deferred census changed")
        require(tuple(case["case"] for case in self.cases) == CASES and self.oracles["identity"]["coverage"] == COVERAGE,
                "Original identity observations were narrowed")
        require(len(self.oracles["callbacks"]["cases"]) == 34 and len(self.oracles["deferred"]["cases"]) == 47,
                "Broader callback observations were dropped")
        require(tuple(case["id"] for case in self.comparisons) == COMPARISON_CASES
            and self.oracles["callbacks"]["coverage"] == COMPARISON_COVERAGE,
            "Original comparison observations were narrowed")
        full = self.oracles["full"]
        archived = r.raw_file(ROOT / "tests/conformance" / full["archive"]["path"])
        require(sha(archived) == full["archive"]["sha256"], "Complete original manager archive changed")
        raw = gzip.decompress(archived)
        require(len(raw) == full["archive"]["uncompressed_bytes"] and sha(raw) == full["archive"]["uncompressed_sha256"],
                "Complete original manager archive content changed")
        complete = r.decode(raw)
        require(len(complete["contexts"]) == 476 and len(complete["events"]) == 91566,
                "Complete original context census differs")
        original_fixed = fixed.Corpus()
        self.original_sources.update(original_fixed.original_sources)
        self.pending = {
            "status": "mandatory_separate_unfinished_full_context_and_fixed_continuation_gates",
            "original_contexts": [entry["id"] for entry in complete["contexts"]],
            "original_context_count": 476, "original_event_count": 91566,
            "fixed_pending": original_fixed.pending(), "fixed_census": original_fixed.census,
            "fixed_unreplayed_observations": 287,
            "callback_cases": [case["id"] for case in self.oracles["callbacks"]["cases"]],
            "callback_case_status": "covered_only_when_all_34_live_comparison_receipts_validate;not_a_substitute_for_full_original_contexts",
            "deferred_cases": [case["id"] for case in self.oracles["deferred"]["cases"]],
            "deferred_case_status": "covered_only_when_all_47_live_deferred_receipts_validate;not_a_substitute_for_full_original_contexts",
            "deferred_runtime_counterparts": self.oracles["deferred"]["runtime_counterparts"],
            "external_native_provider_contexts": "pending_general_import;original_wrappers_use_exact_supplied_context",
            "default_cutover": "not_authorized_by_this_campaign",
        }


def metadata(corpus):
    return {"oracle_pins": corpus.pins, "original_sources": corpus.original_sources,
            "coverage": COVERAGE, "comparison_coverage": COMPARISON_COVERAGE, "deferred_coverage": DEFERRED_COVERAGE,
            "declarations": r.source_pins((CHANNEL_PATH, APPLICATION_PATH))}


def _nested_codes(code):
    yield code
    for value in code.co_consts:
        if type(value) is CodeType:
            yield from _nested_codes(value)


@lru_cache(maxsize=1)
def _serialization_policy():
    # Bind live installed functions to their source, not merely a claimed module
    # or qualname. Generated dataclass methods have closed class/method slots;
    # their live code identity and actual module namespace are retained too.
    entries, roots, compiled = {}, {}, {}
    # Generate only inert reference classes to verify the runtime-generated
    # dataclass method bodies/closures; no product constructor is executed.
    reference_types = {
        "TypeSpec": make_dataclass("TypeSpec", ("kind", "name", "dimensions", "arguments"), frozen=True,
            namespace={"__post_init__": lambda self: None}),
        "ScalarLiteral": make_dataclass("ScalarLiteral", ("value", "dtype", "unit", "canonical_value"), frozen=True),
        "IntentNode": make_dataclass("IntentNode", (("id", object), ("kind", object),
            ("inputs", object, field(default=())), ("attributes", object, field(default_factory=dict)),
            ("data_type", object, field(default=None)), ("role", object, field(default=None)),
            ("source", object, field(default=None))), frozen=True, namespace={"__post_init__": lambda self: None}),
    }
    def bind(module_name, path, category):
        module = importlib.import_module(module_name)
        value = module
        for part in path.split("."):
            value = vars(value)[part]
            if isinstance(value, (classmethod, staticmethod)):
                value = value.__func__
            elif isinstance(value, property):
                value = value.fget
        require(type(value) is FunctionType and value.__globals__ is vars(module),
            "Serializer function has foreign globals: " + module_name + "." + path)
        code = value.__code__
        if path in ("TypeSpec.__init__", "TypeSpec.__eq__", "ScalarLiteral.__init__", "IntentNode.__init__"):
            class_name, method = path.split(".")
            reference = vars(reference_types[class_name])[method]
            closure = tuple(cell.cell_contents for cell in value.__closure__ or ())
            expected_closure = tuple(cell.cell_contents for cell in reference.__closure__ or ())
            require(code == reference.__code__ and len(closure) == len(expected_closure)
                and all(actual is expected for actual, expected in zip(closure, expected_closure)),
                "Serializer generated method differs from its closed dataclass: " + module_name + "." + path)
        else:
            if module_name not in compiled:
                source = Path(module.__file__).resolve()
                compiled[module_name] = tuple(_nested_codes(compile(source.read_bytes(), str(source), "exec", dont_inherit=True)))
            require(code.co_qualname == path and any(code == expected for expected in compiled[module_name])
                and Path(code.co_filename).resolve() == Path(module.__file__).resolve(),
                "Serializer function differs from installed source: " + module_name + "." + path)
        roots[(module_name, path)] = code
        for nested in _nested_codes(code):
            entries[id(nested)] = (nested, vars(module), category)
    for module_name, paths in SERIALIZER_ROOTS.items():
        for path in paths:
            bind(module_name, path, "serializer")
    for module_name, paths in CONVERSION_ROOTS.items():
        for path in paths:
            bind(module_name, path, "conversion")
    for module_name, paths in {
        "biocompiler.ir.intent": ("IntentNode.__init__", "IntentNode.__post_init__"),
        "biocompiler.pipeline_callback_objects": ("CallbackObjects._evaluate", "CallbackObjects.execute"),
        "biocompiler.core_pipeline_manager": ("CorePassManager._fixed",),
    }.items():
        for path in paths:
            bind(module_name, path, "boundary")
    return entries, roots


def permitted(module, qualname):
    if module in TRANSPORT_MODULES:
        return True
    if module in LITERAL_MODULES:
        # Every method/property of the original Python acceptance manager is
        # forbidden while an actual adapter operation is active.
        return not (module == "biocompiler.compiler.pipeline" and qualname.startswith("PassManager."))
    if qualname in SERIALIZER_CENSUS_COMPREHENSIONS.get(module, ()):
        return True
    entries, _ = _serialization_policy()
    return any(namespace.get("__name__") == module and code.co_qualname == qualname
        and category in ("serializer", "conversion") for code, namespace, category in entries.values())


def _reviewed_frame(frame, entries):
    entry = entries.get(id(frame.f_code))
    return entry is not None and entry[0] is frame.f_code and entry[1] is frame.f_globals


def _conversion_ancestry(frame, entries, roots):
    # No arbitrary callback, property, mapping hook, or forged same-name frame
    # may bridge a semantic call to the reviewed serializer ancestor.
    node = roots[("biocompiler.ir.behavior", "BehaviorNode.to_dict")]
    cursor = frame
    while cursor is not None and cursor.f_code is not node:
        if not _reviewed_frame(cursor, entries):
            return False
        if entries[id(cursor.f_code)][2] not in ("conversion", "boundary"):
            return False
        cursor = cursor.f_back
    if cursor is None or not _reviewed_frame(cursor, entries):
        return False
    behavior_module = sys.modules["biocompiler.ir.behavior"]
    if type(cursor.f_locals.get("self")) is not behavior_module.BehaviorNode:
        return False
    cursor = cursor.f_back
    while cursor is not None and _reviewed_frame(cursor, entries):
        if cursor.f_code is roots[("biocompiler.core_pipeline_manager", "CorePassManager._fixed")]:
            return True
        if cursor.f_code is roots[("biocompiler.pipeline_callback_objects", "CallbackObjects._evaluate")]:
            caller = cursor.f_back
            return (cursor.f_locals.get("action") == "document" and caller is not None
                and _reviewed_frame(caller, entries)
                and caller.f_code is roots[("biocompiler.pipeline_callback_objects", "CallbackObjects.execute")])
        if entries[id(cursor.f_code)][2] != "serializer":
            return False
        cursor = cursor.f_back
    return False


def _permitted_frame(frame, entries, roots):
    module, name = frame.f_globals.get("__name__", ""), frame.f_code.co_qualname
    if module in TRANSPORT_MODULES | LITERAL_MODULES:
        return permitted(module, name)
    if not _reviewed_frame(frame, entries):
        return False
    category = entries[id(frame.f_code)][2]
    return category == "serializer" or category == "conversion" and _conversion_ancestry(frame, entries, roots)


@contextmanager
def guarded_execution(seen, observer=None):
    entries, roots = _serialization_policy()
    Recorder = fixed.source_tool("pipeline_registration_guard").Recorder
    delegation = Recorder(seen)
    previous, original_import = sys.getprofile(), builtins.__import__
    external_profile = getattr(previous, "_manager_external_profile", previous)
    profile_failure = None
    def calls(frame, event, result):
        nonlocal profile_failure
        try:
            delegated = delegation.observe(frame, event)
            module = frame.f_globals.get("__name__", "")
            if event == "call" and module.startswith("biocompiler"):
                name = frame.f_code.co_qualname
                require(delegated or _permitted_frame(frame, entries, roots), "Python manager semantic authority is forbidden: " + module + "." + name)
                seen.add((module, name))
            if observer is not None:
                observer(frame, event, result)
            if external_profile is not None:
                external_profile(frame, event, result)
        except BaseException as error:
            profile_failure = error
            raise
    calls._manager_external_profile = external_profile
    def imports(name, *args, **kwargs):
        if name.startswith("biocompiler"):
            require(name in REVIEWED_MODULES, "Unreviewed manager import: " + name)
        return original_import(name, *args, **kwargs)
    builtins.__import__ = imports
    sys.setprofile(calls)
    try:
        yield
    finally:
        try:
            if profile_failure is not None:
                raise profile_failure
            require(sys.getprofile() is calls and builtins.__import__ is imports, "Manager execution guard was disabled")
            delegation.complete()
        finally:
            sys.setprofile(previous)
            builtins.__import__ = original_import


def check_guard(entries, *, initializer="initialize-empty", frames=None, artifacts=None):
    require(type(initializer) is str and initializer in ("initialize-empty", "initialize-synthetic", "initialize-components"),
        "Unknown closed manager guard initializer")
    require(type(entries) is list and entries == sorted(entries) and len({tuple(item) for item in entries}) == len(entries)
        and all(type(item) is list and len(item) == 2 and all(type(value) is str for value in item) for item in entries),
        "Invalid complete manager guard census")
    validate_delegation = fixed.source_tool("pipeline_registration_guard").validate
    filtered = validate_delegation(entries, frames, artifacts)
    require(all(permitted(*item) for item in filtered), "Forbidden Python acceptance execution in guard census")
    initializers = ("CorePassManager.__init__",) if initializer == "initialize-empty" else (
        "CorePassManager._fixed", "CorePassManager.from_" + initializer.removeprefix("initialize-"))
    for name in initializers:
        require(["biocompiler.core_pipeline_manager", name] in entries,
            "Missing actual native manager initializer: " + name)
    for required in (("biocompiler.core_pipeline_callback_session", "CorePipelineCallbackSession.__init__"),
            ("biocompiler.core_pipeline_callback_session", "CorePipelineCallbackSession.call"),
            ("biocompiler.pipeline_callback_objects", "CallbackObjects.execute")):
        require(list(required) in entries, "Missing actual native manager/broker execution: " + required[1])


def installed_modules():
    result = {}
    for name, module in tuple(sys.modules.items()):
        if name == "biocompiler" or name.startswith("biocompiler."):
            origin = getattr(module, "__file__", None)
            require(origin is not None and not Path(origin).resolve().is_relative_to(ROOT), "Source-tree product loaded: " + name)
            result[name] = str(Path(origin).resolve())
    require("biocompiler" in result and TRANSPORT_MODULES <= set(result), "Installed manager modules absent")
    return result


def load_oracle(*, installed=True, comparison=False, deferred=False):
    # Import every product dependency before the unchanged oracle temporarily
    # prepends checkout/src. Only pinned test helpers are intentionally loaded
    # from the checkout. Restore the exact path even if fixture loading fails.
    for name in sorted(REVIEWED_MODULES):
        importlib.import_module(name)
    if installed:
        installed_modules()
    paths = list(sys.path)
    try:
        require(not (comparison and deferred), "Ambiguous original oracle selection")
        name = "deferred" if deferred else "callback" if comparison else "identity"
        spec = importlib.util.spec_from_file_location("_original_manager_" + name + "_cases",
            ROOT / ("tools/capture_pipeline_" + name + "_semantics.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = paths
    for name in ("test_pipeline", "test_component_admission"):
        helper = sys.modules[name]
        require(Path(helper.__file__).resolve() == ROOT / "tests" / (name + ".py"),
                "Original oracle helper was shadowed: " + name)
    if installed:
        installed_modules()
    return module


class GuardedManager:
    def __init__(self, manager, seen, observer=None):
        self.manager, self.seen, self.observer = manager, seen, observer

    def __getattr__(self, name):
        with guarded_execution(self.seen, self.observer):
            value = getattr(self.manager, name)
        if callable(value):
            def invoke(*args, **kwargs):
                with guarded_execution(self.seen, self.observer):
                    return value(*args, **kwargs)
            return invoke
        return value


class Historical:
    def __init__(self, manager):
        self.manager = manager

    def __getitem__(self, identity):
        return self.manager.historical(identity)


def run_case(oracle, index, factory):
    if index == 0:
        return oracle.sharing_case(factory)
    if index in (1, 2):
        return oracle.nested_case(index == 2, factory)
    if index == 3:
        return oracle.stale_case(factory, Historical)
    require(index == 4, "Unknown original identity case")
    return oracle.admission_case(factory)


def campaign(core, corpus, receipt):
    from biocompiler.core_pipeline_manager import CorePassManager
    from biocompiler.core_client import CoreProtocolError
    oracle = load_oracle()
    for index, expected in enumerate(corpus.cases):
        seen, managers = set(), []
        row = {"id": expected["case"], "original": artifact(receipt, canonical(expected)), "frames": []}
        receipt["checks"].append(row)
        def factory(**kwargs):
            with guarded_execution(seen):
                manager = CorePassManager(core, **kwargs)
            managers.append(manager)
            return GuardedManager(manager, seen)
        try:
            actual = run_case(oracle, index, factory)
            row["actual"] = artifact(receipt, canonical(actual))
            equal(actual, expected, "Complete original manager identity/order observation differs: " + expected["case"])
        finally:
            require(len(managers) == 1, "An original case did not retain one actual native manager")
            manager = managers[0]
            with guarded_execution(seen):
                manager.close()
            session = manager.session
            row.update(pid=session.pid, returncode=session.returncode, closed=session.closed,
                invalidated=session.invalidated, executable_sha256=session.executable_sha256,
                stderr=artifact(receipt, canonical({"hex": session.stderr_bytes.hex()})))
            row["frames"] = [{"direction": frame.direction, "index": frame.index,
                "frame": artifact(receipt, frame.frame)} for frame in session.traffic]
        # Public post-close calls must fail without creating another process or
        # publishing another request; this is a real adapter lifecycle check.
        before = len(session.traffic)
        try:
            with guarded_execution(seen):
                manager.get("input")
        except CoreProtocolError as error:
            row["after_close"] = artifact(receipt, canonical({"type": type(error).__name__, "message": str(error),
                "traffic_unchanged": len(session.traffic) == before, "pid_unchanged": session.pid == row["pid"]}))
        else:
            raise AssertionError("Closed native manager resumed")
        row["guard"] = artifact(receipt, canonical([list(item) for item in sorted(seen)]))
    installed_modules()
    receipt["pending"] = artifact(receipt, canonical(corpus.pending))


def inspection_plain(value):
    """Copy only the adapter's immutable JSON views, never arbitrary objects."""
    if type(value) in (dict, MappingProxyType):
        require(all(type(key) is str for key in value), "Inspection has a non-string key")
        return {key: inspection_plain(item) for key, item in value.items()}
    if type(value) in (list, tuple):
        return [inspection_plain(item) for item in value]
    require(value is None or type(value) in (bool, str, int, float), "Inspection contains a host object")
    return value


def comparison_snapshot(raw, aliases, *, previous=None, bound=None):
    """Validate actual native observation before projecting physical labels.

    Aliases originate in the unchanged Capture.label's `is` comparisons with
    real retained providers. The expected state is not an input to this view.
    """
    require(type(raw) is dict and set(raw) == {"snapshot", "order", "providers"}, "Invalid ordered inspection envelope")
    snapshot, order, providers = raw["snapshot"], raw["order"], raw["providers"]
    require(type(snapshot) is dict and set(snapshot) == {"target", *STATE_MAPS}
        and all(type(snapshot[key]) is dict for key in STATE_MAPS), "Incomplete inspected native state")
    require(type(order) is dict and set(order) == {*STATE_MAPS, "combined_provider_history", "validators"},
            "Incomplete native mapping order")
    def keys(actual, wanted):
        require(type(actual) is list and all(type(key) is str for key in actual)
            and len(actual) == len(set(actual)) and set(actual) == set(wanted), "Native order omitted, duplicated or invented a key")
    for key in STATE_MAPS:
        keys(order[key], snapshot[key])
    validator_order = order["validators"]
    require(type(validator_order) is dict and set(validator_order) == set(REGISTRATION_MAPS), "Incomplete validator order maps")
    reachable = set()
    for group in REGISTRATION_MAPS:
        require(type(validator_order[group]) is dict and set(validator_order[group]) == set(snapshot[group]),
                "Validator order omitted a registration")
        for identity, entry in snapshot[group].items():
            fields = {"contract", "validators", "producer"} if group in ("passes", "provider_history") else {"contract", "validators"}
            require(type(entry) is dict and set(entry) == fields and type(entry["validators"]) is dict,
                    "Malformed complete native registration")
            keys(validator_order[group][identity], entry["validators"])
            if "producer" in entry:
                reachable.add(entry["producer"])
            reachable.update(entry["validators"].values())
    require(all(type(value) is str and re.fullmatch(r"provider/[0-9]+", value) for value in reachable),
            "Native registration has an invalid provider token")
    histories = order["combined_provider_history"]
    require(type(histories) is list, "Missing actual provider-history chronology")
    history_keys = []
    for key in histories:
        if type(key) is str:
            require(key in snapshot["provider_history"], "Invented pass history entry")
            history_keys.append(("pass", key))
        else:
            require(type(key) is list and len(key) == 2 and key[0] == "component_input"
                and type(key[1]) is str and key[1] in snapshot["component_input_history"], "Invented admission history entry")
            history_keys.append(tuple(key))
    require(len(history_keys) == len(set(history_keys)) and set(history_keys) ==
        {("pass", key) for key in snapshot["provider_history"]} |
        {("component_input", key) for key in snapshot["component_input_history"]}, "Combined provider history is incomplete")
    require([key for tag, key in history_keys if tag == "pass"] == order["provider_history"]
        and [key for tag, key in history_keys if tag == "component_input"] == order["component_input_history"],
        "Combined history contradicts actual history order")
    require(type(providers) is list and type(aliases) is dict and set(aliases) == reachable
        and all(type(label) is str for label in aliases.values()) and len(set(aliases.values())) == len(aliases),
        "Provider aliases are not a complete physical bijection")
    tokens, handles = set(), set()
    for entry in providers:
        require(type(entry) is dict and set(entry) == {"provider_id", "object"}
            and type(entry["provider_id"]) is str and entry["provider_id"] in reachable, "Unknown inspected provider")
        token, reference = entry["provider_id"], entry["object"]
        require(type(reference) is dict and set(reference) == {"handle"} and type(reference["handle"]) is str
            and re.fullmatch(r"object/[0-9]+", reference["handle"]), "Invalid actual provider reference")
        require(token not in tokens and reference["handle"] not in handles, "Native provider identity is not physically bijective")
        tokens.add(token); handles.add(reference["handle"])
        if bound is not None:
            require(bound.get(token) == reference, "Inspection provider was not bound to this exact actual host callable")
        if previous is not None:
            prior = previous.get(token)
            require(prior is None or prior == (aliases[token], reference["handle"]), "Actual provider identity changed between observations")
            require(all(old_token == token or value[0] != aliases[token] and value[1] != reference["handle"]
                for old_token, value in previous.items()), "A retained callable was assigned another native token")
            previous[token] = (aliases[token], reference["handle"])
    require(tokens == reachable, "Reachable native provider inventory omitted")
    state = deepcopy(snapshot)
    for group in REGISTRATION_MAPS:
        for entry in state[group].values():
            if "producer" in entry:
                entry["producer"] = aliases[entry["producer"]]
            entry["validators"] = {key: aliases[value] for key, value in entry["validators"].items()}
    for identity, envelope in snapshot["records"].items():
        require(type(envelope) is dict and set(envelope) == {"value", "bindings"}
            and type(envelope["value"]) is dict and envelope["value"].get("id") == identity
            and type(envelope["bindings"]) is dict, "Incomplete historical record envelope")
        state["records"][identity] = envelope["value"]
    return {"state": state, "order": deepcopy(order)}


def original_snapshots(case):
    """Exact evaluation order of initial, before/after and final observations."""
    events = case["events"]
    require([event["id"] for event in events] == list(range(len(events))), "Original comparison event order changed")
    children = {}
    for event in events:
        parent = event["parent"]
        require(parent is None or type(parent) is int and 0 <= parent < event["id"], "Original comparison parent differs")
        children.setdefault(parent, []).append(event)
    result = [case["initial_state"]]
    def visit(event):
        result.append(event["before"])
        for child in children.get(event["id"], ()):
            visit(child)
        result.append(event["after"])
    for event in children.get(None, ()):
        visit(event)
    result.append(case["final_state"])
    require(len(result) == 2 * len(events) + 2, "Incomplete original comparison observation traversal")
    return result


def run_comparison_case(oracle, identity):
    mode, name = identity.split(":", 1)
    require(identity in COMPARISON_CASES, "Unknown comparison case")
    if name in COMPARISON_ORDINARY:
        return oracle.ordinary_case(mode, name)
    if name in ("comparison_order", "comparison_short_circuit"):
        return oracle.ordered_case(mode, name == "comparison_short_circuit")
    require(mode == "pass" and name in COMPARISON_PRODUCER, "Unknown original producer comparison case")
    return oracle.producer_case(name)


def live_invocation(session):
    pending = []
    for item in session.traffic:
        value = item.value
        if item.direction == "server" and value["kind"] == "invoke":
            pending.append(value["invocation_id"])
        elif item.direction == "client" and value["kind"] == "continue":
            require(pending and pending.pop() == value["invocation_id"], "Live callback stack differs")
    return pending[-1] if pending else None


@contextmanager
def native_comparison_capture(oracle, factory, retain_observation, retain_event=None, retain_capture=None):
    """Swap only setup/observation; all original case and comparison code runs."""
    from biocompiler.compiler.pipeline import CompletionProfile, ScopedObligation
    from biocompiler.ir.stages import Stage
    from biocompiler.verification.evidence import EvidenceKind
    original = oracle.Capture
    class NativeCapture(original):
        def __init__(self, mode, name):
            self.native_observer_ready = False
            original.__init__(self, mode, name)
            target, dependencies = self.manager.target, dict(self.setup["dependencies"])
            profiles = tuple(CompletionProfile(scope=value["scope"], stage=Stage(value["stage"]),
                schema=value["schema"], obligations=tuple(value["obligations"])) for value in self.setup["profiles"])
            manager = factory(target=target, dependencies=dependencies, completion_profiles=profiles)
            if mode == "pass":
                # This is a fresh authoritative root insertion from fixture
                # authoring fields. No helper accepted record is read/imported.
                obligations = tuple(ScopedObligation(id=value["id"], scope=value["scope"],
                    evidence_kind=EvidenceKind(value["evidence_kind"]), description=value["description"])
                    for value in self.setup["obligations"])
                manager.add_input("input", self.setup["input"], requirements=tuple(self.setup["requirements"]), obligations=obligations)
            self.manager = manager
            self.native_observer_ready = True
            self.initial = self.snapshot()
            if retain_capture is not None:
                retain_capture(self)

        def snapshot(self):
            if not self.native_observer_ready:
                return original.snapshot(self)
            inspected = self.manager.inspect_ordered()
            aliases = {token: self.label(value) for token, value in inspected.providers.items()}
            response = self.manager.session.last_response
            require(response is not None and response.operation == "inspect-ordered", "Native inspection receipt missing")
            raw = response.result
            equal(inspection_plain(inspected.snapshot), raw["snapshot"], "Adapter inspection changed complete native state")
            equal(inspection_plain(inspected.order), raw["order"], "Adapter inspection changed actual native order")
            projected = comparison_snapshot(raw, aliases)
            retain_observation(response.sequence, aliases)
            return projected
        def observe(self, kind, recipe, action):
            identity = len(self.events)
            invocation = live_invocation(self.manager.session) if retain_event is not None else None
            def observed_action():
                before = len(self.manager.session.traffic) if retain_event is not None else 0
                error = None
                try:
                    return action()
                except BaseException as cause:
                    error = cause
                    raise
                finally:
                    if retain_event is not None:
                        session = self.manager.session
                        sequence = session.last_response.sequence if kind == "manager" and recipe["operation"] != "target" else None
                        retain_event({"event": identity, "kind": kind, "sequence": sequence,
                            "invocation": invocation, "before_frames": before, "after_frames": len(session.traffic)}, error)
            return original.observe(self, kind, recipe, observed_action)
    oracle.Capture = NativeCapture
    try:
        yield
    finally:
        oracle.Capture = original


def observe_host_exception(frame, event, result, managers, exceptions):
    if frame.f_globals.get("__name__") == "biocompiler.pipeline_callback_objects" and \
            frame.f_code.co_qualname == "CallbackObjects._capture" and event == "return" and result is not None:
        require(len(managers) == 1 and frame.f_locals["self"] is managers[0]._objects,
            "Exception came from another host broker")
        token = r.decode(result.document)["exception_token"]
        require(token not in exceptions, "Host exception token reused")
        exceptions[token] = {"object": frame.f_locals["exception"], "invocation": live_invocation(managers[0].session)}


def run_deferred_case(oracle, identity):
    mode, name = identity.split(":", 1)
    require(mode in ("proposal", "input", "callback", "admission", "equality"), "Unknown deferred case family")
    return getattr(oracle, mode + "_case")(name)


def retained_manager(value):
    return value.manager if type(value) is GuardedManager else value


def deferred_aliases(state, raw, capture):
    """Read only already-materialized typed inspection tuples and plain maps."""
    aliases = {}
    for group, key in (("passes", "_passes"), ("component_inputs", "_component_inputs"),
                       ("provider_history", "_provider_history"), ("component_input_history", "_provider_history")):
        for identity, entry in raw["snapshot"][group].items():
            original_key = ("component_input", identity) if group == "component_input_history" else identity
            typed = state[key][original_key]
            provider_pairs = [(entry["producer"], typed[1])] if "producer" in entry else []
            provider_pairs.extend((entry["validators"][name], typed[-1][name]) for name in entry["validators"])
            for token, value in provider_pairs:
                label = capture.handle(value)
                require(token not in aliases or aliases[token] == label, "One native provider acquired different original identities")
                aliases[token] = label
    return aliases


@contextmanager
def native_deferred_capture(oracle, factory, retain_observation, *, retain_capture=None,
                            retain_event=None, retain_access=None, retain_exception=None):
    """Preserve every original case body, deferred hook and original observer.

    The local namespace override affects only six explicit replacement-manager
    constructors in this oracle. Test fixture setup still constructs the real
    original manager outside the native guard; no accepted fixture state enters
    a native session. Every actual native construction is retained by factory.
    """
    original, original_pipeline = oracle.Capture, oracle.pipeline
    class NativeCapture(original):
        def __init__(self, name, *, admission=False):
            self.native_observer_ready = False
            original.__init__(self, name, admission=admission)
            self.original_fixture_initial = self.initial
            fixture = self.fixture
            authored = fixture.payload if admission else fixture.input
            dependencies = {"request": oracle.fingerprint(authored),
                "registry": oracle.fingerprint("registry" if admission else "v1")}
            profiles = () if admission else (original_pipeline.CompletionProfile("synthetic",
                original_pipeline.Stage.MECHANISM, "mechanism.v1", ("identity", "response")),)
            self.manager = factory(target=fixture.target, dependencies=dependencies, completion_profiles=profiles)
            if not admission:
                self.manager.add_input("input", fixture.input, requirements=("r",),
                    obligations=(fixture.exact, fixture.biological))
            self.native_observer_ready = True
            if retain_capture is not None:
                retain_capture(self)
            self.initial = self.snapshot()

        def snapshot(self):
            if not self.native_observer_ready:
                return original.snapshot(self)
            state = self.manager.inspection_state()
            safe = self.safe(state)
            response = self.manager.session.last_response
            require(response is not None and response.operation == "inspect-ordered", "Deferred native inspection receipt missing")
            aliases = deferred_aliases(state, response.result, self)
            retain_observation(retained_manager(self.manager), response.sequence, aliases, safe)
            return safe

        def invoke(self, operation, action, **arguments):
            identity = len(self.events)
            manager = retained_manager(self.manager)
            invocation = live_invocation(manager.session) if retain_event is not None else None
            def observed_action():
                before = len(manager.session.traffic) if retain_event is not None else 0
                error = None
                try:
                    return action()
                except BaseException as cause:
                    error = cause
                    raise
                finally:
                    if retain_event is not None:
                        after = len(manager.session.traffic)
                        sequence = manager.session.last_response.sequence if after > before else None
                        retain_event(manager, {"event": identity, "operation": operation, "sequence": sequence,
                            "invocation": invocation, "before_frames": before, "after_frames": after}, error, arguments)
            return original.invoke(self, operation, observed_action, **arguments)

        def access(self, name, **values):
            original.access(self, name, **values)
            if self.native_observer_ready and retain_access is not None:
                manager = retained_manager(self.manager)
                retain_access(manager, len(self.log) - 1, live_invocation(manager.session), values)

        def exception(self, error):
            observed = original.exception(self, error)
            if self.native_observer_ready and retain_exception is not None:
                retain_exception(retained_manager(self.manager), self.stack[-1], error,
                    object.__getattribute__(error, "__traceback__"), observed)
            return observed

    class OriginalConstructor:
        # The unchanged input observer compares this code object. Native hash
        # computation has separate traffic evidence; no Python profile event is
        # forged to pretend the original implementation ran.
        add_input = original_pipeline.PassManager.add_input
        def __call__(self, **kwargs):
            return factory(**kwargs)
    oracle.Capture = NativeCapture
    oracle.pipeline = SimpleNamespace(**{**vars(original_pipeline), "PassManager": OriginalConstructor()})
    try:
        yield
    finally:
        oracle.Capture, oracle.pipeline = original, original_pipeline


def deferred_plain(value):
    """Project only the frozen oracle's closed safe observation vocabulary."""
    if value is None or type(value) in (bool, str, int, float):
        return value
    require(type(value) is dict, "Unexpected deferred observation node")
    if "$object" in value:
        require(set(value) == {"$object", "class"}, "Malformed deferred object identity")
        return value["$object"]
    if "$enum" in value:
        require(set(value) == {"$enum", "value"}, "Malformed deferred enum")
        return value["value"]
    if "$sequence" in value:
        require(set(value) == {"$sequence", "items"} and value["$sequence"] in ("tuple", "list"), "Malformed deferred sequence")
        return [deferred_plain(item) for item in value["items"]]
    if "$mapping" in value:
        require(set(value) == {"$mapping", "items"} and value["$mapping"] in ("builtins.dict", "builtins.mappingproxy"),
            "Malformed deferred mapping")
        result = {}
        for key, item in value["items"]:
            key = deferred_plain(key)
            key = tuple(key) if type(key) is list else key
            require(key not in result, "Repeated deferred mapping key")
            result[key] = deferred_plain(item)
        return result
    require(set(value) == {"$dataclass", "fields"}, "Malformed deferred dataclass")
    result = {key: deferred_plain(item) for key, item in value["fields"].items()}
    kind = value["$dataclass"]
    if kind == "biocompiler.compiler.pipeline.StageRecord":
        result = {"schema_version": "biocompiler.stage_record.v0.1", **result}
    elif kind == "biocompiler.semantics.context.TargetContext":
        result = {"schema_version": "biocompiler.target.v0.1", **result}
    elif kind == "biocompiler.compiler.pipeline.ComponentInputContract":
        result["stage"] = "selected component IR"
    return result


def deferred_snapshot_projection(safe):
    """Bind typed/order observations to the complete native inspection value."""
    state = deferred_plain(safe)
    require(list(state) == ["_target", "_dependencies", "_passes", "_component_inputs",
        "_provider_history", "_records", "_profiles"], "Deferred manager snapshot fields/order differ")
    values = {"target": state["_target"], "dependencies": state["_dependencies"],
        "passes": {}, "component_inputs": {}, "provider_history": {}, "component_input_history": {},
        "records": state["_records"], "profiles": state["_profiles"]}
    validators = {key: {} for key in REGISTRATION_MAPS}
    def registration(group, identity, parts):
        require(type(parts) is list and len(parts) == (3 if group in ("passes", "provider_history") else 2),
            "Deferred registration tuple differs")
        entry = {"contract": parts[0], "validators": parts[-1]}
        if len(parts) == 3:
            entry["producer"] = parts[1]
        values[group][identity] = entry
        validators[group][identity] = list(parts[-1])
    for group in ("passes", "component_inputs"):
        for identity, parts in state["_" + group].items():
            registration(group, identity, parts)
    history = []
    for key, parts in state["_provider_history"].items():
        admission = type(key) is tuple
        require(not admission or len(key) == 2 and key[0] == "component_input", "Deferred history tag differs")
        registration("component_input_history" if admission else "provider_history", key[1] if admission else key, parts)
        history.append(list(key) if admission else key)
    return {"state": values, "order": {**{key: list(values[key]) for key in STATE_MAPS},
        "combined_provider_history": history, "validators": validators}}


class DeferredWitness:
    """Retain actual references at existing observation/transport boundaries.

    This object never calls a user conversion or exception formatting hook.
    Exception descriptors come exclusively from the unchanged original observer.
    """
    def __init__(self, oracle=None):
        self.managers, self.captures, self.inspections, self.events = [], [], [], []
        self.accesses, self.exceptions, self.errors, self.fingerprints = [], {}, [], []
        self.tracebacks = []
        self.user_codes = set() if oracle is None else oracle.USER_CODES
        self.frame_bindings = []

    def manager_index(self, manager):
        for index, actual in enumerate(self.managers):
            if actual is manager:
                return index
        raise AssertionError("Deferred observation came from an unretained native manager")

    def broker_manager(self, broker):
        values = [manager for manager in self.managers if manager._objects is broker]
        require(len(values) == 1, "Deferred exception came from an unknown actual broker")
        return values[0]

    def observe(self, frame, event, result):
        module = frame.f_globals.get("__name__")
        name = frame.f_code.co_qualname
        if ((module == "biocompiler.core_pipeline_manager" and name in ("CorePassManager._call", "CorePassManager._native_register"))
            or (module == "biocompiler.compiler.pipeline" and name == "PassManager.register")) and event == "return":
            manager = frame.f_locals["self"]
            if any(actual is manager for actual in self.managers):
                response = manager.session.last_response
                require(response is not None, "Native stack frame lost its completed command receipt")
                self.frame_bindings.append((frame, {"manager": self.manager_index(manager), "sequence": response.sequence,
                    "invocation": None, "token": None}))
        if module != "biocompiler.pipeline_callback_objects":
            return
        if name in ("CallbackObjects.execute", "CallbackObjects._evaluate") and event == "return":
            manager = self.broker_manager(frame.f_locals["self"])
            invocation = live_invocation(manager.session)
            if invocation is not None:
                invoked = next(item.value for item in manager.session.traffic if item.direction == "server"
                    and item.value["kind"] == "invoke" and item.value["invocation_id"] == invocation)
                self.frame_bindings.append((frame, {"manager": self.manager_index(manager), "sequence": invoked["command_sequence"],
                    "invocation": invocation, "token": None}))
        if name == "CallbackObjects._capture" and event == "return" and result is not None:
            manager = self.broker_manager(frame.f_locals["self"])
            index = self.manager_index(manager)
            token = r.decode(result.document)["exception_token"]
            require((index, token) not in self.exceptions, "Deferred original exception token reused")
            error = frame.f_locals["exception"]
            state = frame.f_locals["self"]._exceptions[token]
            self.exceptions[index, token] = {"object": error, "traceback": state.traceback,
                "cause": state.cause, "context": state.context, "suppress_context": state.suppress_context,
                "invocation": live_invocation(manager.session), "rethrows": []}
        elif name == "CallbackObjects.rethrow" and event == "call":
            manager = self.broker_manager(frame.f_locals["self"])
            key = self.manager_index(manager), frame.f_locals["token"]
            require(key in self.exceptions, "Deferred rethrow lacked the actual prior capture")
            response = manager.session.last_response
            require(response is not None and response.status == "raise", "Original rethrow lacked its native reply")
            self.exceptions[key]["rethrows"].append(response.sequence)
            self.frame_bindings.append((frame, {"manager": key[0], "sequence": response.sequence,
                "invocation": self.exceptions[key]["invocation"], "token": key[1]}))
        elif name == "CallbackObjects.execute" and event == "call" and self.captures:
            action, args = frame.f_locals["action"], frame.f_locals["arguments"]
            capture = self.captures[0]
            if action == "attr-default" and args.get("name") == "fingerprint" and capture.name.startswith("input:"):
                manager = self.broker_manager(frame.f_locals["self"])
                # Only the live case's replacement manager is observed. The
                # bootstrap root and original fixture are separate lifetimes.
                if retained_manager(capture.manager) is manager:
                    self.fingerprints.append({"manager": self.manager_index(manager),
                        "invocation": live_invocation(manager.session), "access_offset": len(capture.log),
                        "parent": capture.stack[-1] if capture.stack else None})

    def inspection(self, manager, sequence, aliases, state):
        self.inspections.append({"manager": self.manager_index(manager), "sequence": sequence,
            "aliases": aliases, "state": state})

    def event(self, manager, link, error, arguments):
        self.events.append(({"manager": self.manager_index(manager), **link}, error, arguments))

    def access(self, manager, ordinal, invocation, values):
        self.accesses.append({"manager": self.manager_index(manager), "ordinal": ordinal, "invocation": invocation,
            "frame_offset": len(manager.session.traffic)})

    def error(self, manager, event, error, traceback, descriptor):
        # Keep live traceback nodes strongly referenced; copied text cannot
        # establish the original tail's identity after a broker rethrow.
        index, cursor = 0, traceback
        while cursor is not None and cursor.tb_frame.f_code not in self.user_codes:
            index += 1
            cursor = cursor.tb_next
        self.errors.append({"manager": self.manager_index(manager), "event": event,
            "object": error, "traceback": traceback, "descriptor": descriptor, "required_index": index})

    def node(self, value):
        if value is None:
            return None
        for index, retained in enumerate(self.tracebacks):
            if retained is value:
                return "traceback/" + str(index)
        self.tracebacks.append(value)
        return "traceback/" + str(len(self.tracebacks) - 1)

    def chain(self, value):
        result = []
        while value is not None:
            code, path = value.tb_frame.f_code, Path(value.tb_frame.f_code.co_filename)
            module = value.tb_frame.f_globals.get("__name__", "")
            if module.startswith("biocompiler."):
                source = "src/" + module.replace(".", "/") + ".py"
                require(path.is_file() and sha(r.raw_file(path)) == sha(r.raw_file(ROOT / source)),
                    "Traceback product frame is not the pinned installed source")
            elif path.is_file() and path.resolve().is_relative_to(ROOT):
                source = path.resolve().relative_to(ROOT).as_posix()
            else:
                source = code.co_filename
            result.append({"node": self.node(value), "source": source, "function": code.co_name,
                "qualname": code.co_qualname, "line": value.tb_lineno,
                "source_sha256": sha(r.raw_file(path)) if path.is_file() else None,
                "binding": next((binding for frame, binding in self.frame_bindings if frame is value.tb_frame), None)})
            value = value.tb_next
        return result

    def evidence(self):
        require(len(self.captures) == 1, "Deferred case capture census differs")
        capture = self.captures[0]
        original_objects = len(capture.objects)
        events = []
        for link, error, arguments in self.events:
            tokens = sorted(token for (index, token), entry in self.exceptions.items()
                if index == link["manager"] and entry["object"] is error)
            events.append({**link, "exception_tokens": tokens})
        events.sort(key=lambda item: item["event"])
        exceptions = []
        for (index, token), entry in self.exceptions.items():
            error = entry["object"]
            exceptions.append({"manager": index, "token": token, "invocation": entry["invocation"],
                "rethrows": entry["rethrows"], "identity": capture.handle(error),
                "cause": None if entry["cause"] is None else capture.handle(entry["cause"]),
                "context": None if entry["context"] is None else capture.handle(entry["context"]),
                "suppress_context": entry["suppress_context"], "traceback": self.chain(entry["traceback"]),
                "events": sorted(item["event"] for item, actual, _ in self.events
                    if item["manager"] == index and actual is error)})
        errors = [{"manager": row["manager"], "event": row["event"], "identity": row["descriptor"]["identity"],
            "traceback": self.chain(row["traceback"]), "required_index": row["required_index"]} for row in self.errors]
        # Only already-labeled original objects receive aliases. Resolving a
        # retained reference is physical identity; it performs no user hooks.
        objects, arguments = [], []
        for manager in self.managers:
            bindings = {}
            for value, label in capture.objects:
                handle = manager._objects._identities.get(id(value))
                if handle is not None:
                    require(manager._objects.resolve({"handle": handle}) is value, "Deferred source object was rebound")
                    bindings[handle] = label
            objects.append(bindings)
            authored = {}
            for item in manager.session.traffic:
                value = item.value
                if item.direction != "client" or value["kind"] != "command":
                    continue
                for argument in value["arguments"].values():
                    references = argument if type(argument) is list else [argument]
                    for reference in references:
                        if type(reference) is dict and set(reference) == {"handle"}:
                            authored[reference["handle"]] = capture.safe(manager._objects.resolve(reference))
            arguments.append(authored)
        require(len(capture.objects) == original_objects, "Deferred receipt observation introduced a new user object")
        return {"inspections": self.inspections, "events": events, "accesses": self.accesses,
            "host_exceptions": exceptions, "errors": errors, "fingerprints": self.fingerprints,
            "objects": objects, "arguments": arguments}


def deferred_campaign(core, corpus, receipt):
    from biocompiler.core_pipeline_manager import CorePassManager
    from biocompiler.core_client import CoreProtocolError
    oracle = load_oracle(deferred=True)
    runtime, retained_runtime = runtime_helpers()
    original_counterpart = fixed.source_tool("pipeline_original_counterpart").run
    counterpart = original_counterpart('deferred')
    fresh, proof = counterpart['value']['capture'], counterpart['value']['proof']
    receipt['deferred_original_counterpart'] = artifact(receipt, canonical(counterpart))
    receipt["fresh_deferred_original"] = artifact(receipt, canonical(fresh))
    receipt["deferred_runtime_authority"] = artifact(receipt, canonical(proof))
    for expected in fresh["cases"]:
        witness, seen = DeferredWitness(oracle), set()
        row = {"id": expected["id"], "original": artifact(receipt, canonical(expected)), "processes": []}
        receipt["deferred_checks"].append(row)
        def factory(**kwargs):
            with guarded_execution(seen, witness.observe):
                manager = CorePassManager(core, **kwargs)
            witness.managers.append(manager)
            return GuardedManager(manager, seen, witness.observe)
        try:
            with native_deferred_capture(oracle, factory, witness.inspection,
                    retain_capture=witness.captures.append, retain_event=witness.event,
                    retain_access=witness.access, retain_exception=witness.error):
                actual = run_deferred_case(oracle, expected["id"])
            row["actual"] = artifact(receipt, canonical(actual))
            row["evidence"] = artifact(receipt, canonical(witness.evidence()))
            row["bootstrap_original"] = artifact(receipt, canonical(witness.captures[0].original_fixture_initial))
        finally:
            require(len(witness.managers) == (2 if expected["id"].startswith("input:") else 1),
                "Deferred native process census differs from the unchanged original constructors")
            for manager in witness.managers:
                with guarded_execution(seen):
                    manager.close()
                session = manager.session
                process = {"pid": session.pid, "returncode": session.returncode, "closed": session.closed,
                    "invalidated": session.invalidated, "executable_sha256": session.executable_sha256,
                    "stderr": artifact(receipt, canonical({"hex": session.stderr_bytes.hex()})),
                    "frames": [{"direction": item.direction, "index": item.index,
                        "frame": artifact(receipt, item.frame)} for item in session.traffic]}
                row["processes"].append(process)
                before = len(session.traffic)
                try:
                    with guarded_execution(seen):
                        manager.get("input")
                except CoreProtocolError as error:
                    process["after_close"] = artifact(receipt, canonical({"type": type(error).__name__, "message": str(error),
                        "traffic_unchanged": len(session.traffic) == before, "pid_unchanged": session.pid == process["pid"]}))
                else:
                    raise AssertionError("Closed deferred manager resumed")
            row["guard"] = artifact(receipt, canonical([list(item) for item in sorted(seen)]))
    installed_modules()


def runtime_helpers():
    """Load pinned tools from an absolute CLI invocation outside the checkout."""
    paths = list(sys.path)
    try:
        sys.path.insert(0, str(ROOT))
        runtime = importlib.import_module("tools.check_pipeline_deferred_runtime")
        retained = importlib.import_module("tools.check_pipeline_deferred_runtime_receipt")
        for module in (runtime, retained):
            require(Path(module.__file__).resolve() == ROOT / (module.__name__.replace(".", "/") + ".py"),
                "Deferred runtime checker was shadowed")
        return runtime, retained
    finally:
        sys.path[:] = paths


def tree_safe(tree):
    require(type(tree) is list and len(tree) == 2, "Malformed ordered deferred tree")
    kind, value = tree
    if kind == "scalar":
        require(value is None or type(value) in (bool, int, float, str), "Malformed ordered scalar")
        return value
    if kind == "array":
        require(type(value) is list, "Malformed ordered array")
        return {"$sequence": "tuple", "items": [tree_safe(item) for item in value]}
    require(kind == "object" and type(value) is list, "Malformed ordered object")
    keys = []
    items = []
    for pair in value:
        require(type(pair) is list and len(pair) == 2 and type(pair[0]) is str and pair[0] not in keys,
            "Duplicate or malformed ordered object key")
        keys.append(pair[0])
        items.append([pair[0], tree_safe(pair[1])])
    return {"$mapping": "builtins.mappingproxy", "items": items}


def deferred_fingerprint_projection(actual, evidence, details):
    """Separate native hash evidence substitutes for one implementation probe.

    The raw capture stays complete and unchanged. This projection is admitted
    only for the frozen input observer's exact direct-Python-call probe, after
    the native document, hash literal and fallback getter are linked in order.
    """
    projected = deepcopy(actual)
    inserted = []
    claimed = set()
    for witness in evidence["fingerprints"]:
        require(type(witness) is dict and set(witness) == {"manager", "invocation", "access_offset", "parent"}
            and actual["id"].startswith("input:") and witness["manager"] == 1,
            "Unexpected deferred native fingerprint witness")
        native = details[witness["manager"]]
        identity = witness["invocation"]
        require(identity in native["invocations"] and identity not in claimed, "Missing or repeated native fingerprint callback")
        claimed.add(identity)
        invocation = native["invocations"][identity]
        command = next(item for item in native["commands"] if item["sequence"] == invocation["command_sequence"])
        require(invocation["action"] == "attr-default" and invocation["arguments"]["name"] == "fingerprint"
            and command["operation"] == "add-input"
            and invocation["arguments"]["object"] == command["arguments"]["payload"],
            "Default fingerprint is detached from the original input payload")
        preceding = [(key, item) for key, item in native["invocations"].items()
            if item["command_sequence"] == command["sequence"] and item["end_frame"] < invocation["start_frame"]]
        require(len(preceding) >= 3, "Native default fingerprint lacks its frozen document and literal")
        _, literal = preceding[-1]
        _, document = preceding[-2]
        _, frozen_document = preceding[-3]
        require(literal["action"] == "literal" and literal["arguments"]["kind"] == "json"
            and literal["outcome"] == {"status": "return", "value": invocation["arguments"]["default"]}
            and document["action"] == "ordered-json" and document["outcome"]["status"] == "return",
            "Native default hash was not computed after the actual ordered document")
        require(frozen_document["action"] == "freeze-json" and frozen_document["outcome"] ==
            {"status": "return", "value": document["arguments"]["object"]}
            and any(item["action"] == "document" and item["arguments"]["object"] == command["arguments"]["payload"]
                and item["outcome"] == {"status": "return", "value": frozen_document["arguments"]["object"]}
                and item["end_frame"] < frozen_document["start_frame"] for _, item in preceding),
            "Native default fingerprint did not hash this payload's actual document and frozen object")
        frozen = tree_safe(document["outcome"]["value"])
        require(type(frozen) is dict and frozen.get("$mapping") == "builtins.mappingproxy",
            "Native default hash document was not frozen")
        equal(literal["arguments"]["value"], sha(canonical(deferred_plain(frozen))), "Native default fingerprint value differs")
        parent = witness["parent"]
        require(type(parent) is int and 0 <= parent < len(evidence["events"]), "Default fingerprint lacks an original event")
        event = evidence["events"][parent]
        require(event["manager"] == 1 and event["sequence"] == command["sequence"], "Default fingerprint belongs to another input event")
        position = witness["access_offset"]
        require(type(position) is int and 0 <= position <= len(actual["access_log"]), "Invalid fingerprint observation position")
        before = [row for row in evidence["accesses"] if row["manager"] == 1 and row["frame_offset"] <= invocation["start_frame"]]
        after = [row for row in evidence["accesses"] if row["manager"] == 1 and row["frame_offset"] > invocation["start_frame"]]
        require(all(row["ordinal"] < position for row in before) and all(row["ordinal"] >= position for row in after),
            "Native fingerprint was moved relative to actual deferred hooks")
        inserted.append((position, invocation["start_frame"], {"ordinal": 0, "parent": parent,
            "access": "input.default_fingerprint", "values": {"$mapping": "builtins.dict", "items": [["document", frozen]]}}))
    wanted = {identity for manager in details[1:] for identity, item in manager["invocations"].items()
        if item["action"] == "attr-default" and item["arguments"]["name"] == "fingerprint"}
    require(claimed == wanted, "Native default fingerprint receipt census differs")
    for offset, (position, _, value) in enumerate(sorted(inserted, key=lambda item: (item[0], item[1]))):
        projected["access_log"].insert(position + offset, value)
    for ordinal, value in enumerate(projected["access_log"]):
        value["ordinal"] = ordinal
    for event in projected["events"]:
        link = evidence["events"][event["id"]]
        for field, frame_field in (("access_start", "before_frames"), ("access_end", "after_frames")):
            event[field] += sum(point < link[frame_field] for _, point, _ in inserted) if link["manager"] == 1 else 0
    return projected


def deferred_trace_projection(actual, expected, evidence, details):
    return trace.projection(actual, expected, evidence, details)


def validate_deferred_events(actual, evidence, details, bootstrap):
    require(type(evidence) is dict and set(evidence) == {"inspections", "events", "accesses", "host_exceptions",
        "errors", "fingerprints", "objects", "arguments"}, "Incomplete deferred observation evidence")
    require(len(evidence["objects"]) == len(evidence["arguments"]) == len(details), "Deferred process/object census differs")
    objects = {entry["identity"]: entry["class"] for entry in actual["objects"]}
    require(len(objects) == len(actual["objects"]), "Deferred original object identity duplicated")
    for aliases in evidence["objects"]:
        require(type(aliases) is dict and len(set(aliases.values())) == len(aliases)
            and all(type(key) is str and re.fullmatch(r"object/[0-9]+", key) and label in objects
                for key, label in aliases.items()), "Deferred original/broker object binding is not a physical bijection")
    used_arguments = [set() for _ in details]
    def argument(index, ref):
        require(type(ref) is dict and set(ref) == {"handle"} and ref["handle"] in evidence["arguments"][index],
            "Deferred source argument is not an actual retained object")
        used_arguments[index].add(ref["handle"])
        value = evidence["arguments"][index][ref["handle"]]
        if type(value) is dict and "$object" in value:
            require(value["class"] == objects.get(value["$object"])
                and evidence["objects"][index].get(ref["handle"]) == value["$object"],
                "Deferred command argument changed actual source object identity")
        return value
    commands = [{item["sequence"]: item for item in item_details["commands"]} for item_details in details]
    claimed = [set() for _ in details]
    initial_states = [bootstrap] if len(details) == 1 else [bootstrap, actual["initial_state"]]
    for index, initial in enumerate(initial_states):
        state = deferred_snapshot_projection(initial)["state"]
        initializers = [item for item in commands[index].values() if item["operation"] == "initialize-empty"]
        require(len(initializers) == 1, "Deferred initialization was omitted or repeated")
        command = initializers[0]
        claimed[index].add(command["sequence"])
        args = command["arguments"]
        equal(args["target"], state["target"], "Deferred initialization changed original target authority")
        equal(deferred_plain(argument(index, args["target_object"])), state["target"], "Deferred supplied target object differs")
        equal(args["dependencies"], [[key, value] for key, value in state["dependencies"].items() if key != "target"],
            "Deferred initialization changed original dependency authority/order")
        equal(args["completion_profiles"], list(state["profiles"].values()), "Deferred initialization changed original completion profiles")
        require(args["manager_limits"] is None and command["outcome"]["status"] == "ok", "Original deferred initialization did not succeed")
        if index == 0 and actual["mode"] == "pass":
            inserted = [item for item in commands[0].values() if item["operation"] == "add-input"]
            require(inserted, "Deferred fixture lacks original authoritative input")
            command = min(inserted, key=lambda item: item["sequence"])
            claimed[0].add(command["sequence"])
            args, root = command["arguments"], state["records"]["input"]
            equal({key: args[key] for key in ("identity", "stage", "requirements", "obligations")},
                {"identity": "input", **{key: root[key] for key in ("stage", "requirements", "obligations")}},
                "Deferred fixture changed original authoritative root declaration")
            equal(deferred_plain(argument(0, args["payload"])), root["payload"], "Deferred fixture imported another payload")
            equal(command["outcome"].get("value", {}).get("value"), root, "Deferred root insertion result differs")
    snapshots = evidence["inspections"]
    wanted = original_snapshots(actual)
    if len(details) == 2:
        wanted.insert(0, bootstrap)
    require(len(snapshots) == len(wanted), "Deferred original inspection census differs")
    aliases_seen = [{} for _ in details]
    snapshot_sequences = [[] for _ in details]
    for row, safe in zip(snapshots, wanted):
        require(type(row) is dict and set(row) == {"manager", "sequence", "aliases", "state"}
            and type(row["manager"]) is int and 0 <= row["manager"] < len(details), "Malformed deferred state observation")
        index, seq = row["manager"], row["sequence"]
        require(seq in details[index]["inspections"], "Deferred snapshot is detached from native inspection")
        snapshot_sequences[index].append(seq)
        claimed[index].add(seq)
        equal(row["state"], safe, "Deferred safe snapshot differs from actual original observation")
        raw = details[index]["inspections"][seq]
        value = comparison_snapshot(raw["value"], row["aliases"], previous=aliases_seen[index], bound=raw["bound"])
        equal(value, deferred_snapshot_projection(safe), "Deferred typed state/order differs from complete native inspection")
        require(all(evidence["objects"][index].get(entry["object"]["handle"]) == row["aliases"][entry["provider_id"]]
            for entry in raw["value"]["providers"]), "Deferred inspection provider aliases lack actual callable identity")
    require(all(sequences == list(native["inspections"]) for sequences, native in zip(snapshot_sequences, details)),
        "Deferred native inspection was duplicated, omitted or reordered")
    event_snapshots = snapshots[1:] if len(details) == 2 else snapshots
    children, slots, cursor = {}, {}, 1
    for event in actual["events"]:
        children.setdefault(event["parent"], []).append(event)
    def visit(event):
        nonlocal cursor
        before = cursor
        cursor += 1
        for child in children.get(event["id"], ()):
            visit(child)
        slots[event["id"]] = before, cursor
        cursor += 1
    for event in children.get(None, ()):
        visit(event)
    require(len(evidence["events"]) == len(actual["events"]), "Deferred original event census differs")
    for event, link in zip(actual["events"], evidence["events"]):
        require(type(link) is dict and set(link) == {"manager", "event", "operation", "sequence", "invocation",
            "before_frames", "after_frames", "exception_tokens"} and link["event"] == event["id"]
            and link["operation"] == event["operation"] and link["manager"] == len(details) - 1,
            "Original deferred event was rebound or omitted")
        index, seq = link["manager"], link["sequence"]
        before, after = [event_snapshots[position] for position in slots[event["id"]]]
        require(before["manager"] == after["manager"] == index, "Event inspections belong to a different manager")
        before, after = commands[index][before["sequence"]], commands[index][after["sequence"]]
        require(before["end_frame"] + 1 == link["before_frames"] and after["start_frame"] == link["after_frames"]
            and before["parent_invocation"] == after["parent_invocation"] == link["invocation"],
            "Deferred action is detached from its own before/after observations")
        operation, authored = event["operation"], deferred_plain(event["arguments"])
        if operation in ("target", "context_mutation"):
            require(seq is None and link["before_frames"] == link["after_frames"], "Local original observation performed an unclaimed native operation")
            if operation == "target":
                equal(deferred_plain(event["result"]), deferred_snapshot_projection(actual["initial_state"])["state"]["target"],
                    "Original cached target changed")
            else:
                require(event["outcome"] == "raised" and event["exception"]["class"] == "builtins.AttributeError"
                    and link["invocation"] in details[index]["invocations"], "Immutable context mutation changed semantics")
            continue
        require(seq in commands[index] and seq not in claimed[index], "Deferred manager event is detached from its command")
        claimed[index].add(seq)
        command = commands[index][seq]
        expected_op = {"get-input": "get", "nested_run": "run", "register_version2": "register",
            "register_replacement": "register", "nested_admission": "admit-component-input"}.get(operation, operation.replace("_", "-"))
        require(command["operation"] == expected_op and command["start_frame"] == link["before_frames"]
            and command["end_frame"] + 1 == link["after_frames"] and command["parent_invocation"] == link["invocation"],
            "Deferred event command sequence, operation or callback parent differs")
        args = command["arguments"]
        prior = deferred_snapshot_projection(event["before"])["state"]
        if expected_op in ("register", "register-component-input"):
            admission = expected_op == "register-component-input"
            previous = prior["component_inputs" if admission else "passes"].get("admit" if admission else "lower")
            contract = authored.get("contract", None if previous is None else previous["contract"])
            equal(args["contract"], contract, "Deferred registration changed the actual authored contract")
            providers = deferred_plain(argument(index, args["validators"]))
            validator = authored.get("validator", None if previous is None else next(iter(previous["validators"].values())))
            equal(providers, {contract["checks"][0]["id"]: validator}, "Deferred registration changed actual validator objects/order")
            if not admission:
                equal(deferred_plain(argument(index, args["producer"])), authored.get("producer", previous["producer"] if previous else None),
                    "Deferred registration changed the actual producer object")
        elif expected_op == "run":
            equal({key: args[key] for key in ("pass_id", "input_id", "output_id")},
                {"pass_id": authored.get("pass_id", "lower"), "input_id": authored.get("input_id", "input"),
                 "output_id": authored["output_id"]}, "Deferred nested run changed original identities")
            equal(args["configuration"], None, "Deferred run changed its authored default configuration")
        elif expected_op in ("get", "set-dependency", "result"):
            equal(args, authored, "Deferred read/mutation changed actual original arguments")
        elif expected_op in ("add-input", "admit-component-input"):
            require(args["identity"] == authored["identity"], "Deferred input identity changed")
            payload = argument(index, args["payload"])
            if "payload" in authored:
                equal(deferred_plain(payload), authored["payload"], "Deferred input eagerly replaced its original payload object")
            else:
                equal(sha(canonical(deferred_plain(payload))), prior["dependencies"]["request"], "Nested root changed original payload authority")
            if expected_op == "admit-component-input":
                require(args["contract_id"] == "admit", "Deferred admission used another contract")
            else:
                equal({key: args[key] for key in ("stage", "requirements", "obligations")},
                    {"stage": "typed intent and contracts", "requirements": [], "obligations": []}, "Deferred root declarations changed")
        else:
            raise AssertionError("Unreviewed deferred original manager operation: " + expected_op)
        outcome = command["outcome"]
        if event["outcome"] == "returned":
            require(outcome["status"] == "ok" and link["exception_tokens"] == [], "Successful deferred operation became an exception")
            value = outcome["value"]
            if expected_op in ("get", "run", "add-input", "admit-component-input", "result"):
                require(type(value) is dict and "value" in value, "Deferred returned value omitted its complete native envelope")
                value = value["value"]
            equal(value, deferred_plain(event["result"]), "Deferred actual return differs from original observation")
        elif outcome["status"] == "rejected":
            error = event["exception"]
            module, name = error["class"].rsplit(".", 1)
            descriptor = outcome["value"]
            require(set(descriptor) == {"module", "type", "message", "attributes", "attributes_tree"}, "Deferred native rejection fields differ")
            equal({key: descriptor[key] for key in ("module", "type", "message", "attributes")},
                {"module": module, "type": name, "message": error["message"], "attributes": deferred_plain(error["attributes"])},
                "Deferred native rejection changed its actual original exception descriptor")
            ordered = tree_safe(descriptor["attributes_tree"])
            require(type(ordered) is dict and ordered.get("$mapping") == "builtins.mappingproxy", "Deferred rejection attributes are not an ordered object")
            ordered["$mapping"] = "builtins.dict"
            equal(ordered, error["attributes"], "Deferred native rejection changed fresh exception container types/order")
        else:
            require(outcome["status"] == "raise" and outcome["token"] in link["exception_tokens"],
                "Deferred original host exception lost its actual native token")
    # Every authored object reference, including collection sidecars, is tied
    # to its full safe source observation; none is inferred from expected output.
    for index, native_commands in enumerate(commands):
        for command in native_commands.values():
            args = command["arguments"]
            for key in ("obligation_objects", "obligations_object", "requirements_object"):
                if key not in args:
                    continue
                if key == "obligation_objects":
                    values = [deferred_plain(argument(index, ref)) for ref in args[key]]
                    declaration = args.get("obligations", args.get("contract", {}).get("introduces",
                        args.get("contract", {}).get("obligations", [])))
                    equal(values, declaration, "Deferred obligation source objects differ from actual native declarations")
                else:
                    declaration = args.get("obligations" if key == "obligations_object" else "requirements",
                        args.get("contract", {}).get("obligations" if key == "obligations_object" else "requirements"))
                    equal(deferred_plain(argument(index, args[key])), declaration, "Deferred source collection sidecar differs")
        require(claimed[index] == set(native_commands), "Unclaimed extra or missing deferred native command")
        require(used_arguments[index] == set(evidence["arguments"][index]), "Unclaimed deferred source argument binding")
    validate_deferred_accesses(actual, evidence, details)


def deferred_context_document(hydration, native):
    """Project the frozen deferred corpus's host SourceLink tuple capability.

    Host links deliberately are absent from the native typed JSON document.
    Recover their fields only from the exact producer/tuple/native-check trace,
    never from the observed context being checked. This finite corpus uses
    singleton membership sets; ambiguous scalar proofs fail closed.
    """
    def reference(value):
        require(type(value) is dict and set(value) == {"handle"}
            and type(value["handle"]) is str and len(value["handle"]) <= 32
            and re.fullmatch(r"object/(0|[1-9][0-9]*)", value["handle"]),
            "Malformed deferred source-link capability reference")
        return value
    def successful_boolean(item):
        outcome = item["outcome"]
        return type(outcome) is dict and set(outcome) == {"status", "value"} \
            and outcome["status"] == "return" and outcome["value"] is True
    args = hydration["arguments"]
    document = deepcopy(args["document"])
    binding = args["bindings"].get("source_links")
    if binding is None:
        return document
    require(type(binding) is dict and set(binding) == {"kind", "object"} and binding["kind"] == "host"
        and document["source_links"] == [], "Deferred source links lack the exact host tuple binding")
    reference(binding["object"])
    sequence = hydration["command_sequence"]
    command = next((item for item in native["commands"] if item["sequence"] == sequence), None)
    require(command is not None and command["operation"] == "run", "Deferred host links belong to another command")
    inspections = [item for item in native["commands"] if item["operation"] == "inspect-ordered"
        and item["end_frame"] < command["start_frame"]]
    require(inspections, "Deferred producer lacks its original registered authority")
    before = max(inspections, key=lambda item: item["end_frame"])
    registered = native["inspections"][before["sequence"]]["value"]["snapshot"]["passes"].get(command["arguments"]["pass_id"])
    require(registered is not None, "Deferred source links refer to an unregistered producer")
    prior = sorted((item for item in native["invocations"].values()
        if item["command_sequence"] == sequence and item["end_frame"] < hydration["start_frame"]
        and item["parent_invocation"] == hydration["parent_invocation"]), key=lambda item: item["start_frame"])
    def returned(item):
        require(type(item["outcome"]) is dict and set(item["outcome"]) == {"status", "value"}
            and item["outcome"]["status"] == "return", "Deferred source-link proof contains a raised primitive")
        return item["outcome"]["value"]
    attributes = [(index,item) for index,item in enumerate(prior)
        if item["action"] == "attr" and item["arguments"]["name"] == "source_links"]
    require(len(attributes) == 1, "Deferred source-link producer attribute is missing or ambiguous")
    index, attribute = attributes[0]
    reference(attribute["arguments"]["object"])
    reference(returned(attribute))
    producers = [item for item in prior[:index] if item["action"] == "call-provider"
        and item["arguments"]["provider_id"] == registered["producer"]
        and item["outcome"] == {"status":"return", "value":attribute["arguments"]["object"]}
        and item["end_frame"] < attribute["start_frame"]]
    require(len(producers) == 1, "Deferred source links are detached from the registered producer result")
    producer = producers[0]
    reference(returned(producer))
    reference(producer["arguments"]["context"])
    contexts = [item for item in prior if item["action"] == "hydrate-context"
        and item["end_frame"] < producer["start_frame"]
        and item["outcome"] == {"status":"return", "value":producer["arguments"]["context"]}]
    require(len(contexts) == 1 and contexts[0]["arguments"]["document"]["output"] is None,
        "Deferred source links do not originate in the actual producer context")
    reference(returned(contexts[0]))
    for field in ("input", "target", "requirements", "configuration", "dependencies"):
        equal(contexts[0]["arguments"]["document"][field], document[field], "Deferred producer and validator contexts differ")
    def step(offset, action, arguments):
        require(offset < len(prior), "Deferred source-link materialization is incomplete")
        item = prior[offset]
        require(item["action"] == action and item["arguments"] == arguments,
            "Deferred source-link materialization changed order or object")
        return returned(item)
    whole = reference(step(index+1, "tuple", {"object":returned(attribute)}))
    equal(whole, binding["object"], "Deferred hydration uses another source-link tuple")
    iterator = reference(step(index+2, "iter", {"object":whole}))
    elements, cursor = [], index+3
    while True:
        value = step(cursor, "next", {"object":iterator}); cursor += 1
        require(type(value) is dict and set(value) == {"exhausted", "object"}
            and type(value["exhausted"]) is bool, "Malformed deferred source-link iterator step")
        if value["exhausted"]:
            require(value["object"] is None, "Deferred exhausted iterator retained an element")
            break
        elements.append(reference(value["object"]))
    checks = prior[cursor:]
    types = [item for item in checks if item["action"] == "is-instance" and item["arguments"]["type"] == "SourceLink"]
    require([item["arguments"]["object"] for item in types] == elements
        and all(successful_boolean(item) for item in types),
        "Deferred source-link element type checks changed order or census")
    for field in ("pass_name", "requirement_id", "target_node_id", "source_node_id"):
        require([item["arguments"]["object"] for item in checks if item["action"] == "attr" and item["arguments"]["name"] == field] == elements,
            "Deferred source-link field reads changed order or census")
    literals = [item for item in checks if item["action"] == "literal" and item["outcome"]["status"] == "return"]
    def scalar(element, field):
        proofs = []
        for attribute in checks:
            if attribute["action"] != "attr" or attribute["arguments"] != {"object":element,"name":field}:
                continue
            scalar_reference = reference(returned(attribute))
            for check in checks:
                if check["start_frame"] <= attribute["end_frame"]:
                    continue
                operands = check["arguments"]
                for literal in literals:
                    if literal["end_frame"] >= check["start_frame"]:
                        continue
                    known = literal["arguments"]
                    literal_reference = reference(returned(literal))
                    if check["action"] == "compare" and operands == {"left":scalar_reference,"operator":"eq","right":literal_reference} \
                        and known["kind"] == "json" and type(known["value"]) is str:
                        require(successful_boolean(check), "Deferred source-link scalar check did not return true")
                        proofs.append(known["value"])
                    elif check["action"] == "contains" and operands == {"container":literal_reference,"item":scalar_reference} \
                        and known["kind"] == "set" and type(known["value"]) is list and len(known["value"]) == 1 \
                        and type(known["value"][0]) is str:
                        require(successful_boolean(check), "Deferred source-link scalar check did not return true")
                        proofs.append(known["value"][0])
        require(proofs and all(value == proofs[0] for value in proofs), "Deferred source-link scalar proof is missing or ambiguous")
        return proofs[0]
    links = []
    for element in elements:
        links.append({field:scalar(element, field) for field in ("requirement_id", "source_node_id", "target_node_id", "pass_name")})
    document["source_links"] = links
    return document


def validate_deferred_accesses(actual, evidence, details):
    require(len(evidence["accesses"]) == len(actual["access_log"]), "Deferred hook/access census differs")
    previous_offsets = {}
    observed_invocations = set()
    def label(index, reference):
        require(type(reference) is dict and set(reference) == {"handle"}, "Deferred callback object reference differs")
        return evidence["objects"][index].get(reference["handle"])
    for original, link in zip(actual["access_log"], evidence["accesses"]):
        require(type(link) is dict and set(link) == {"manager", "ordinal", "invocation", "frame_offset"}
            and link["ordinal"] == original["ordinal"] and type(link["manager"]) is int
            and 0 <= link["manager"] < len(details), "Deferred accessor was reordered or rebound")
        index, identity = link["manager"], link["invocation"]
        native = details[index]
        require(identity in native["invocations"], "Deferred accessor lacks its actual live callback")
        invocation = native["invocations"][identity]
        observed_invocations.add((index, identity))
        require(type(link["frame_offset"]) is int and invocation["start_frame"] < link["frame_offset"] <= invocation["end_frame"]
            and link["frame_offset"] >= previous_offsets.get(index, 0), "Deferred hooks changed actual execution order")
        previous_offsets[index] = link["frame_offset"]
        parent = original["parent"]
        require(type(parent) is int and 0 <= parent < len(evidence["events"]), "Deferred callback lacks its original event")
        owner = evidence["events"][parent]
        require(owner["manager"] == index and owner["sequence"] == invocation["command_sequence"]
            and owner["before_frames"] <= invocation["start_frame"] < invocation["end_frame"] < owner["after_frames"],
            "Deferred accessor is detached from its original manager operation")
        action, args, name = invocation["action"], invocation["arguments"], original["access"]
        values = deferred_plain(original["values"])
        prior = [item for item in native["invocations"].values() if item["end_frame"] < invocation["start_frame"]
            and item["command_sequence"] == invocation["command_sequence"]]
        if name.startswith("proposal."):
            require(action == "attr" and args["name"] == name.split(".", 1)[1] and label(index, args["object"]) == "proposal",
                "Deferred proposal getter was replaced, omitted or moved")
        elif ".lookup." in name or name == "input.fingerprint":
            source, attribute = name.split(".lookup.") if ".lookup." in name else ("input", "fingerprint")
            require(action == ("attr-default" if attribute == "fingerprint" else "document")
                and (attribute == "to_dict" or args["name"] == attribute)
                and label(index, args["object"]) == "payload/" + source,
                "Deferred payload getter has different native authority")
        elif name.endswith(".to_dict"):
            source = name.split(".")[0]
            require(action == "document" and label(index, args["object"]) == "payload/" + source,
                "Deferred conversion was not called through its actual original getter")
        elif name.startswith("links."):
            require(action == "tuple" and label(index, args["object"]) == "iterator/links",
                "Source links were not fully materialized through their actual original iterator")
        elif name.startswith("obligations."):
            # Items.__iter__ is a generator: its first body instruction and
            # its 'iter' log run on the first next(), not while iter() merely
            # creates that generator object.
            require(action == "next" and any(item["action"] == "iter"
                and label(index, item["arguments"]["object"]) == "iterator/obligations"
                and item["outcome"] == {"status": "return", "value": args["object"]} for item in prior),
                "Deferred obligation consumption was eager or detached from the original iterator")
        elif name.startswith("obligation."):
            require(action == "attr" and args["name"] == name.split(".", 1)[1]
                and label(index, args["object"]) == "obligation", "Deferred obligation getter or short circuit changed")
        elif name.startswith("mapping."):
            require(action == "freeze-json" and label(index, args["object"]) == "mapping",
                "Custom mapping was observed outside the actual deferred freeze")
        elif name.endswith(".equal") or name == "comparison.truth":
            require(action == "compare" and args["operator"] == "eq"
                and label(index, args["left"]) == "provider/old" and label(index, args["right"]) == "provider/new",
                "Original equality/truth hook is detached from the exact native provider comparison")
        else:
            require(name in ("producer.enter", "validator.enter", "admission_validator.enter", "old.call", "new.call")
                and action in ("call-provider", "call"), "Unreviewed or substituted deferred host accessor")
            wanted = "provider/" + (name.split(".")[0] if name.endswith(".call") else
                "producer" if name == "producer.enter" else "validator")
            if action == "call-provider":
                refs = [item["arguments"]["object"] for item in prior if item["action"] == "bind-provider"
                    and item["arguments"]["provider_id"] == args["provider_id"] and item["outcome"] == {"status": "return", "value": None}]
                # Provider binding normally belongs to the earlier register
                # command, so inspect the full completed invocation history.
                if not refs:
                    refs = [item["arguments"]["object"] for item in native["invocations"].values()
                        if item["action"] == "bind-provider" and item["end_frame"] < invocation["start_frame"]
                        and item["arguments"]["provider_id"] == args["provider_id"]
                        and item["outcome"] == {"status": "return", "value": None}]
                require(refs and all(label(index, ref) == wanted for ref in refs), "Deferred provider callback used another actual callable")
                context = args["context"]
            else:
                require(label(index, args["callable"]) == wanted and len(args["args"]) == 1 and args["kwargs"] == {},
                    "Deferred producer/validator invocation changed actual callable or arguments")
                context = args["args"][0]
            contexts = [item for item in prior if item["action"] == "hydrate-context"
                and item["outcome"] == {"status": "return", "value": context}]
            require(contexts, "Original callback context lacks its actual native hydration")
            equal(deferred_context_document(contexts[-1], native), values["context"],
                "Deferred callback read a context different from native authority")
    for index, native in enumerate(details):
        for identity, invocation in native["invocations"].items():
            action, args = invocation["action"], invocation["arguments"]
            tracked = False
            if action in ("attr", "attr-default", "document", "tuple", "freeze-json"):
                source = label(index, args["object"])
                tracked = ((action == "attr" and source in ("proposal", "obligation"))
                    or action == "attr-default" and source == "payload/input"
                    or action == "document" and source in ("payload/input", "payload/output")
                    or action == "tuple" and source == "iterator/links"
                    or action == "freeze-json" and source == "mapping")
            elif action == "compare":
                tracked = label(index, args["left"]) == "provider/old" and label(index, args["right"]) == "provider/new"
            if tracked:
                require((index, identity) in observed_invocations, "Native tracked accessor executed without its original hook observation")
    tokens = {(row["manager"], row["token"]): row for row in evidence["host_exceptions"]}
    require(len(tokens) == len(evidence["host_exceptions"]) and set(tokens) == {(index, item["outcome"]["token"])
        for index, native in enumerate(details) for item in native["invocations"].values() if item["outcome"]["status"] == "raise"},
        "Deferred original host-exception census differs")
    for key, entry in tokens.items():
        expected_events = sorted(row["event"] for row in evidence["events"] if row["manager"] == key[0]
            and key[1] in row["exception_tokens"])
        require(entry["events"] == expected_events and expected_events, "Deferred exception object aliases changed")
        for identity in expected_events:
            event = actual["events"][identity]
            require(event["outcome"] == "raised" and event["exception"]["identity"] == entry["identity"],
                "Opaque host exception token was rebound to another actual observed exception")


def comparison_campaign(core, corpus, receipt):
    from biocompiler.core_pipeline_manager import CorePassManager
    from biocompiler.core_client import CoreProtocolError
    oracle = load_oracle(comparison=True)
    original_counterpart = fixed.source_tool("pipeline_original_counterpart").run
    counterpart = original_counterpart('callbacks')
    fresh = counterpart['value']
    receipt['comparison_original_counterpart'] = artifact(receipt, canonical(counterpart))
    equal(fresh, corpus.oracles["callbacks"], "Fresh unchanged original comparison oracle differs")
    receipt["fresh_comparison_original"] = artifact(receipt, canonical(fresh))
    for expected in corpus.comparisons:
        seen, managers, observations, captures, events, exceptions = set(), [], [], [], [], {}
        row = {"id": expected["id"], "original": artifact(receipt, canonical(expected)), "frames": []}
        receipt["comparison_checks"].append(row)
        def observer(frame, event, result):
            observe_host_exception(frame, event, result, managers, exceptions)
        def factory(**kwargs):
            with guarded_execution(seen, observer):
                manager = CorePassManager(core, **kwargs)
            managers.append(manager)
            return GuardedManager(manager, seen, observer)
        def observed(sequence, aliases):
            observations.append({"sequence": sequence, "aliases": dict(aliases)})
        def observed_event(value, error):
            events.append((value, error))
        try:
            with native_comparison_capture(oracle, factory, observed, observed_event, captures.append):
                actual = run_comparison_case(oracle, expected["id"])
            row["actual"] = artifact(receipt, canonical(actual))
            equal(actual, expected, "Complete live comparison differs: " + expected["id"])
        finally:
            links = [{**value, "exception_tokens": sorted(token for token, entry in exceptions.items() if entry["object"] is error)}
                for value, error in events]
            links.sort(key=lambda item: item["event"])
            row["events"] = artifact(receipt, canonical(links))
            row["host_exceptions"] = artifact(receipt, canonical([{"token": token, "invocation": entry["invocation"],
                "events": sorted(value["event"] for value, error in events if error is entry["object"])} for token, entry in exceptions.items()]))
            row["inspections"] = artifact(receipt, canonical(observations))
            require(len(managers) == 1, "Comparison case did not retain exactly one actual native manager")
            manager = managers[0]
            if captures:
                require(len(captures) == 1, "Original comparison capture was replaced mid-case")
                capture = captures[0]
                bindings = {}
                for item in manager.session.traffic:
                    value = item.value
                    if item.direction != "client" or value["kind"] != "command":
                        continue
                    args, operation = value["arguments"], value["operation"]
                    if operation == "initialize-empty":
                        ref = args["target_object"]
                        actual_object = manager._objects.resolve(ref)
                        require(actual_object is manager.target, "Original target object binding changed")
                        bindings[ref["handle"]] = {"kind": "target", "value": oracle.plain(actual_object)}
                    if operation == "add-input":
                        ref = args["payload"]
                        actual_object = manager._objects.resolve(ref)
                        bindings[ref["handle"]] = {"kind": "input", "value": inspection_plain(actual_object)}
                    if operation not in ("register", "register-component-input"):
                        continue
                    for field in (("producer", "validators") if operation == "register" else ("validators",)):
                        ref = args[field]
                        actual_object = manager._objects.resolve(ref)
                        if field == "producer":
                            descriptor = {"kind": "provider", "label": capture.label(actual_object)}
                        else:
                            require(type(actual_object) is dict, "Original comparison validator argument was not its authored plain dict")
                            descriptor = {"kind": "validators", "items": [[key, capture.label(value)] for key, value in actual_object.items()]}
                        previous = bindings.get(ref["handle"])
                        require(previous is None or previous == descriptor, "Original source reference changed")
                        bindings[ref["handle"]] = descriptor
                provider_handles = {}
                for value, label in capture.objects:
                    handle = manager._objects._identities.get(id(value))
                    if handle is not None:
                        require(manager._objects.resolve({"handle": handle}) is value, "Retained source callable identity changed")
                        provider_handles[label] = handle
                row["source_bindings"] = artifact(receipt, canonical({"arguments": bindings, "providers": provider_handles}))
            with guarded_execution(seen):
                manager.close()
            session = manager.session
            row.update(pid=session.pid, returncode=session.returncode, closed=session.closed,
                invalidated=session.invalidated, executable_sha256=session.executable_sha256,
                stderr=artifact(receipt, canonical({"hex": session.stderr_bytes.hex()})))
            row["frames"] = [{"direction": item.direction, "index": item.index,
                "frame": artifact(receipt, item.frame)} for item in session.traffic]
        before = len(session.traffic)
        try:
            with guarded_execution(seen):
                manager.get("input")
        except CoreProtocolError as error:
            row["after_close"] = artifact(receipt, canonical({"type": type(error).__name__, "message": str(error),
                "traffic_unchanged": len(session.traffic) == before, "pid_unchanged": session.pid == row["pid"]}))
        else:
            raise AssertionError("Closed comparison manager resumed")
        row["guard"] = artifact(receipt, canonical([list(item) for item in sorted(seen)]))
    installed_modules()


def frame_body(raw):
    require(type(raw) is bytes and len(raw) >= 10 and re.fullmatch(rb"[0-9a-f]{8}\n", raw[:9])
        and int(raw[:8], 16) == len(raw) - 9, "Malformed complete callback frame")
    value = r.decode(raw[9:])
    require(canonical(value) == raw[9:], "Complete callback body is not canonical")
    return value


def frame(value):
    raw = canonical(value)
    return f"{len(raw):08x}\n".encode() + raw


def json_nodes(value):
    if type(value) is dict:
        return 1 + len(value) + sum(json_nodes(item) for item in value.values())
    if type(value) is list:
        return 1 + sum(json_nodes(item) for item in value)
    return 1


def validate_frames(rows, artifacts, channel, application, *, sessions=None, details=None, provider_calls=True,
                    initializer="initialize-empty"):
    require(type(initializer) is str and initializer in ("initialize-empty", "initialize-synthetic", "initialize-components", "initialize-reference"),
        "Unknown closed manager initializer")
    require(type(rows) is list and rows, "Missing exact live-manager frames")
    sequence = event = commands_count = input_bytes = output_bytes = nodes = 0
    commands, invocations, sent, normalized = [], [], {}, []
    session_id = None
    previous = None
    closed = False
    operations, actions = [], []
    host_bindings = {}
    if details is not None:
        details.update(inspections={}, commands=[], invocations={}, requests={})
    limits = channel["limits"]
    for number, row in enumerate(rows):
        require(type(row) is dict and set(row) == {"direction", "index", "frame"} and type(row["index"]) is int, "Unknown traffic entry fields")
        raw = artifacts.raw(row["frame"])
        value = frame_body(raw)
        require(type(value) is dict and not closed, "Traffic continued after native session closure")
        incoming = row["direction"] == "client"
        require(incoming or row["direction"] == "server", "Unknown frame direction")
        kind = value.get("kind")
        declarations_by_kind = channel["client_fields" if incoming else "server_fields"]
        require(kind in declarations_by_kind and set(value) == set(declarations_by_kind[kind]), "Unknown frame kind or fields")
        if session_id is None:
            require(number == 0 and incoming and kind == "hello", "Channel did not begin with client hello")
            nonce = value.get("session_id")
            try:
                identity = UUID(nonce)
            except (ValueError, TypeError, AttributeError) as error:
                raise AssertionError("Invalid callback session identity") from error
            require(identity.version == 4 and str(identity) == nonce and (sessions is None or nonce not in sessions),
                    "Reused or noncanonical callback session identity")
            session_id = nonce
            if sessions is not None:
                sessions.add(nonce)
        require(value["protocol"] == channel["protocol"] and value["profile"] == channel["profile"]
            and value["session_id"] == session_id, "Cross-session callback frame or changed protocol")
        require(len(raw) - 9 <= limits["max_frame_bytes"], "Callback frame exceeds selected bound")
        frame_nodes = json_nodes(value)
        require(frame_nodes <= min(channel["fixed_limits"]["max_frame_json_nodes"], limits["max_json_nodes"]),
            "Callback frame exceeds selected JSON node bound")
        nodes += frame_nodes
        require(nodes <= limits["max_json_nodes"], "Cumulative JSON node budget exceeded")
        projected = deepcopy(value)
        projected["session_id"] = "<validated-session-uuid4>"
        if incoming:
            input_bytes += len(raw)
            require(type(value["sequence"]) is int and value["sequence"] == sequence and row["index"] == sequence,
                    "Client sequence was replayed, skipped or reordered")
            sent[sequence] = raw[9:]
            sequence += 1
            if kind in ("hello", "command", "close"):
                commands_count += 1
                require(commands_count <= limits["max_commands"], "Native command count exceeded")
                if kind == "hello":
                    require(number == 0, "Repeated hello")
                    equal(value["declaration"], channel, "Hello did not bind complete transport declaration")
                    equal(value["application"], application, "Hello did not bind complete application declaration")
                    require(value["limits"] is None, "Identity campaign unexpectedly reduced limits")
                else:
                    parent = invocations[-1]["invocation_id"] if invocations else None
                    require((value["parent_invocation"] is None or type(value["parent_invocation"]) is int)
                        and value["parent_invocation"] == parent and (not commands or invocations),
                            "Wrong nested-command parent or unsolicited concurrent command")
                    if kind == "close":
                        require(not commands and not invocations, "Close occurred inside a callback")
                    else:
                        operation = value["operation"]
                        require(operation in application["operations"] and type(value["arguments"]) is dict
                            and set(value["arguments"]) == set(application["operations"][operation]["fields"]),
                            "Unknown manager operation or incomplete original authority fields")
                        operations.append(operation)
                commands.append({"sequence": value["sequence"], "body": raw[9:], "kind": kind,
                    "operation": value.get("operation"), "arguments": value.get("arguments"),
                    "start_frame": number, "parent_invocation": value.get("parent_invocation")})
                if details is not None and kind == "command":
                    details["requests"][value["sequence"]] = {"operation": value["operation"], "arguments": value["arguments"],
                        "parent_invocation": value["parent_invocation"], "start_frame": number}
            else:
                require(kind == "continue" and commands and invocations, "Unsolicited callback completion")
                invocation = invocations[-1]
                require(type(value["invocation_id"]) is int and value["invocation_id"] == invocation["invocation_id"]
                    and value["invocation_sha256"] == invocation["body_sha256"]
                    and invocation["command_sequence"] == commands[-1]["sequence"],
                    "Continuation did not bind exact top invocation and active command")
                outcome = value["outcome"]
                require(type(outcome) is dict and outcome.get("status") in channel["continuation_outcomes"]
                    and set(outcome) == set(channel["continuation_outcomes"][outcome["status"]]), "Malformed continuation outcome")
                if outcome["status"] == "raise":
                    require(type(outcome["token"]) is str and 0 < len(outcome["token"].encode()) <= 128,
                            "Invalid opaque host exception token")
                if invocation["action"] == "bind-provider" and outcome["status"] == "return":
                    require(outcome["value"] is None, "Provider binding returned unexpected data")
                    args = invocation["arguments"]
                    token, reference = args["provider_id"], args["object"]
                    require(type(token) is str and re.fullmatch(r"provider/[0-9]+", token)
                        and type(reference) is dict and set(reference) == {"handle"}
                        and type(reference["handle"]) is str and re.fullmatch(r"object/[0-9]+", reference["handle"]),
                        "Malformed actual provider binding")
                    require(token not in host_bindings or host_bindings[token] == reference,
                            "Native provider was rebound to a different physical callable")
                    require(all(old == token or item != reference for old, item in host_bindings.items()),
                            "Same physical callable received different native tokens")
                    host_bindings[token] = reference
                invocations.pop()
                if details is not None:
                    details["invocations"][invocation["invocation_id"]].update(outcome=outcome, end_frame=number)
                projected["invocation_sha256"] = "<validated-exact-invocation-body-sha256>"
        else:
            output_bytes += len(raw)
            require(type(value["event_id"]) is int and value["event_id"] == event and row["index"] == event,
                    "Server event was replayed, skipped or reordered")
            event += 1
            require(kind in ("reply", "invoke") and commands, "Unexpected terminal or unsolicited event in successful case")
            command = commands[-1]
            if kind == "invoke":
                parent = invocations[-1]["invocation_id"] if invocations else None
                require(command["kind"] == "command" and type(value["invocation_id"]) is int
                    and type(value["command_sequence"]) is int
                    and (value["parent_invocation"] is None or type(value["parent_invocation"]) is int)
                    and value["invocation_id"] == value["event_id"]
                    and value["parent_invocation"] == parent and value["command_sequence"] == command["sequence"]
                    and value["command_sha256"] == sha(command["body"]), "Callback invocation binding differs")
                known_actions = {**application["actions"], **application["broker_actions"]}
                require(value["action"] in known_actions and type(value["arguments"]) is dict
                    and set(value["arguments"]) == set(known_actions[value["action"]]["fields"]),
                    "Unknown or malformed original host operation")
                actions.append(value["action"])
                invocations.append({"invocation_id": value["invocation_id"], "command_sequence": command["sequence"],
                    "body_sha256": sha(raw[9:]), "action": value["action"], "arguments": value["arguments"]})
                if details is not None:
                    details["invocations"][value["invocation_id"]] = {"action": value["action"], "arguments": value["arguments"],
                        "command_sequence": command["sequence"], "parent_invocation": value["parent_invocation"], "start_frame": number}
                require(len(invocations) <= limits["max_pending_invocations"], "Callback stack exceeded its bound")
                projected["command_sha256"] = "<validated-exact-command-body-sha256>"
            else:
                require(type(value["sequence"]) is int and value["sequence"] == command["sequence"] and value["request_sha256"] == sha(command["body"])
                    and (not invocations or invocations[-1]["command_sequence"] != command["sequence"]),
                    "Reply did not complete the active command after its callbacks")
                outcome = value["outcome"]
                require(type(outcome) is dict and outcome.get("status") in channel["reply_outcomes"]
                    and set(outcome) == set(channel["reply_outcomes"][outcome["status"]]), "Malformed command reply outcome")
                if outcome["status"] == "raise":
                    require(type(outcome["token"]) is str and 0 < len(outcome["token"].encode()) <= 128,
                            "Native reply lost original exception token")
                require(type(value["closed"]) is bool and value["closed"] == (command["kind"] == "close"),
                        "Command reply closure differs")
                if command["kind"] == "hello":
                    equal(outcome, {"status": "ok", "value": {"declaration": channel, "application": application,
                        "limits": limits}}, "Hello reply changed negotiated authority")
                if value["closed"]:
                    equal(outcome, {"status": "ok", "value": None}, "Close did not return successful null")
                    closed = True
                if details is not None and command["kind"] == "command":
                    details["commands"].append({"sequence": command["sequence"], "operation": command["operation"],
                        "arguments": command["arguments"], "outcome": outcome, "start_frame": command["start_frame"],
                        "end_frame": number, "parent_invocation": command["parent_invocation"]})
                    if command["operation"] == "inspect-ordered":
                        require(outcome["status"] == "ok", "Original comparison inspection failed")
                        details["inspections"][command["sequence"]] = {"value": outcome["value"], "bound": deepcopy(host_bindings)}
                commands.pop()
                projected["request_sha256"] = "<validated-exact-request-body-sha256>"
            usage = value["usage"]
            require(type(usage) is dict and set(usage) == set(channel["usage_fields"])
                and all(type(item) is int and item >= 0 for item in usage.values()), "Malformed cumulative usage")
            require(usage["input_bytes"] == input_bytes and usage["output_bytes"] == output_bytes
                and usage["frames"] == number + 1 and usage["commands"] == commands_count
                and usage["json_nodes"] == nodes and usage["pending_invocations"] == len(invocations),
                "Exact lifetime byte/frame/node/command census differs")
            require(usage["work_charged"] + usage["work_remaining"] == limits["max_work"]
                and usage["work_charged"] >= channel["fixed_limits"]["terminal_work"]
                and usage["retained_bytes"] <= limits["max_retained_bytes"], "Lifetime work or retention bound differs")
            if previous is not None:
                require(all(usage[key] >= previous[key] for key in ("work_charged", "input_bytes", "output_bytes",
                    "frames", "commands", "json_nodes", "retained_bytes"))
                    and usage["work_remaining"] <= previous["work_remaining"], "Lifetime counters reset")
            previous = usage
        require(number + 1 < limits["max_frames"] and input_bytes + output_bytes + channel["fixed_limits"]["terminal_bytes"]
            <= limits["max_total_bytes"], "Channel consumed reserved terminal capacity")
        normalized.append({"direction": row["direction"], "value": projected})
    require(closed and not commands and not invocations, "Incomplete native command or continuation stack")
    initializers = {"initialize-empty", "initialize-synthetic", "initialize-components", "initialize-reference"}
    require(operations and operations[0] == initializer
        and sum(operation in initializers for operation in operations) == 1,
        "A real manager was not initialized exactly once with the declared initializer")
    if provider_calls:
        require("call-provider" in actions or "call" in actions, "Real original provider callbacks were not executed")
    return {"operations": operations, "actions": actions, "frames_sha256": r.digest(normalized), "frames": len(rows)}


def raw_exchange(path, request):
    """Bound actual executable output and process lifetime, including descendants."""
    process = subprocess.Popen([str(path), ARGUMENT], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=True)
    output, errors = bytearray(), bytearray()
    deadline, offset = time.monotonic() + 30, 0
    try:
        with selectors.DefaultSelector() as selector:
            for stream, event, name in ((process.stdin, selectors.EVENT_WRITE, "stdin"),
                    (process.stdout, selectors.EVENT_READ, "stdout"), (process.stderr, selectors.EVENT_READ, "stderr")):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, event, name)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                require(remaining > 0, "Manager role probe exceeded deadline")
                for key, _ in selector.select(min(remaining, .1)):
                    if key.data == "stdin":
                        try:
                            offset += os.write(key.fileobj.fileno(), request[offset:])
                        except BrokenPipeError:
                            offset = len(request)
                        if offset == len(request):
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                    else:
                        raw = os.read(key.fileobj.fileno(), r.CONTROL_BYTES + 1)
                        if not raw:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                        else:
                            (output if key.data == "stdout" else errors).extend(raw)
                            require(len(output) + len(errors) <= r.CONTROL_BYTES, "Manager role probe output exceeded bound")
            code = process.wait(timeout=max(.001, deadline - time.monotonic()))
        return code, bytes(output), bytes(errors)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            if process.poll() is None:
                process.kill()
        process.wait()
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()


def verify_request(channel, application, nonce):
    return {"protocol": channel["protocol"], "profile": channel["profile"], "session_id": nonce,
        "kind": "hello", "sequence": 0, "declaration": channel, "application": application, "limits": None}


def verify_rejection(path, pin, receipt):
    channel, application = declarations()
    request = frame(verify_request(channel, application, str(uuid4())))
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= 256 * 1024 * 1024,
            "Unsafe actual Verify executable")
    with path.open("rb") as executable:
        require(hashlib.file_digest(executable, "sha256").hexdigest() == pin,
                "Verify binary changed before actual role probe")
    code, stdout, stderr = raw_exchange(path, request)
    receipt["verify_rejection"] = {"argv": [str(path), ARGUMENT], "executable_sha256": pin, "returncode": code,
        "request": artifact(receipt, request), "stdout": artifact(receipt, stdout),
        "stderr": artifact(receipt, canonical({"hex": stderr.hex()}))}


def validate_verify(receipt, artifacts, channel, application):
    row = receipt["verify_rejection"]
    require(type(row) is dict and set(row) == {"argv", "executable_sha256", "returncode", "request", "stdout", "stderr"}
        and row["argv"] == [receipt["executables"]["verify"], ARGUMENT] and type(row["returncode"]) is int
        and row["returncode"] == 2 and row["executable_sha256"] == receipt["native_inputs"]["sha256"]["biocompiler-verify"],
        "Actual Verify callback-mode rejection missing")
    request = frame_body(artifacts.raw(row["request"]))
    nonce = request.get("session_id")
    identity = UUID(nonce)
    require(identity.version == 4 and str(identity) == nonce, "Invalid independent Verify request nonce")
    equal(request, verify_request(channel, application, nonce), "Actual Verify received different manager-mode authority")
    expected = {"protocol": "biocompiler.core.v1", "request_id": None, "operation": None, "status": "error",
        "result": None, "diagnostics": [{"code": "unexpected_arguments",
            "message": "Expected standard JSON input or the exact inherited artifact descriptor arguments.", "path": None}],
        "core": {**fixed.CORE, "executable": "verify"}}
    require(artifacts.raw(row["stdout"]) == canonical(expected) + b"\n", "Independent Verify did not reject manager mode exactly")
    equal(artifacts.json(row["stderr"]), {"hex": ""}, "Verify role probe wrote stderr")


def validate_comparison_events(expected, links, source, exceptions, details, snapshots):
    require(type(source) is dict and set(source) == {"arguments", "providers"}
        and type(source["arguments"]) is dict and type(source["providers"]) is dict, "Missing original source object bindings")
    handles = source["providers"]
    require(all(label in expected["providers"] and type(handle) is str and re.fullmatch(r"object/[0-9]+", handle)
        for label, handle in handles.items()) and len(set(handles.values())) == len(handles),
        "Source providers are not physically distinct retained objects")
    reverse = {handle: label for label, handle in handles.items()}
    used_arguments = set()
    def provider(reference):
        require(type(reference) is dict and set(reference) == {"handle"} and reference["handle"] in reverse,
                "Native operation references an unbound original callable")
        return reverse[reference["handle"]]
    def argument(reference, expected_value):
        require(type(reference) is dict and set(reference) == {"handle"} and reference["handle"] in source["arguments"],
                "Original argument lacks actual retained object evidence")
        used_arguments.add(reference["handle"])
        equal(source["arguments"][reference["handle"]], expected_value, "Actual command changed original authored callable arguments")
    initialization = [item for item in details["commands"] if item["operation"] == "initialize-empty"]
    require(len(initialization) == 1, "Comparison initialization authority omitted")
    initial = initialization[0]["arguments"]
    equal(initial["target"], expected["setup"]["target"], "Native initialization target differs from original authoring")
    equal(initial["dependencies"], [[key, expected["setup"]["dependencies"][key]]
        for key in expected["initial_state"]["order"]["dependencies"] if key in expected["setup"]["dependencies"]],
        "Native initialization dependency authority/order differs")
    equal(initial["completion_profiles"], expected["setup"]["profiles"], "Native initialization profiles differ")
    require(initial["manager_limits"] is None and initialization[0]["outcome"]["status"] == "ok", "Original initialization failed or changed bounds")
    argument(initial["target_object"], {"kind": "target", "value": expected["setup"]["target"]})
    inputs = [item for item in details["commands"] if item["operation"] == "add-input"]
    require(len(inputs) == (1 if expected["mode"] == "pass" else 0), "Original authoritative root insertion census differs")
    if inputs:
        args = inputs[0]["arguments"]
        require(args["identity"] == expected["setup"]["input_id"] and args["stage"] == "typed intent and contracts",
                "Native authoritative root identity or stage differs")
        equal(args["requirements"], expected["setup"]["requirements"], "Native input requirements differ")
        equal(args["obligations"], expected["setup"]["obligations"], "Native input obligations differ")
        argument(args["payload"], {"kind": "input", "value": expected["setup"]["input"]})
        require(inputs[0]["outcome"]["status"] == "ok", "Original root insertion failed")
        equal(inputs[0]["outcome"]["value"]["value"], expected["initial_state"]["state"]["records"]["input"],
            "Original authoritative root return differs")
    require(type(links) is list and len(links) == len(expected["events"]), "Original operation I/O census omitted")
    commands = {entry["sequence"]: entry for entry in details["commands"]}
    children, slots, offset = {}, {}, 1
    for event in expected["events"]:
        children.setdefault(event["parent"], []).append(event)
    def locate(event):
        nonlocal offset
        before = offset
        offset += 1
        for child in children.get(event["id"], ()):
            locate(child)
        slots[event["id"]] = (before, offset)
        offset += 1
    for event in children.get(None, ()):
        locate(event)
    require(type(snapshots) is list and len(snapshots) == offset + 1, "Original before/after inspection census differs")
    event_commands, comparison_groups = {}, {}
    for event, link in zip(expected["events"], links):
        require(type(link) is dict and set(link) == {"event", "kind", "sequence", "invocation", "before_frames", "after_frames", "exception_tokens"}
            and type(link["event"]) is int and link["event"] == event["id"] and link["kind"] == event["kind"]
            and all(type(link[key]) is int and link[key] >= 0 for key in ("before_frames", "after_frames"))
            and link["before_frames"] <= link["after_frames"]
            and (link["invocation"] is None or type(link["invocation"]) is int)
            and type(link["exception_tokens"]) is list and all(type(token) is str for token in link["exception_tokens"])
            and link["exception_tokens"] == sorted(set(link["exception_tokens"])), "Invalid actual event/frame binding")
        if event["outcome"] == "returned":
            require(link["exception_tokens"] == [], "Successful original event was assigned an exception")
        before_index, after_index = slots[event["id"]]
        before_sequence, after_sequence = snapshots[before_index]["sequence"], snapshots[after_index]["sequence"]
        require(before_sequence in commands and after_sequence in commands, "Original event inspections are missing")
        before_inspection, after_inspection = commands[before_sequence], commands[after_sequence]
        require(before_inspection["operation"] == after_inspection["operation"] == "inspect-ordered"
            and before_inspection["end_frame"] + 1 == link["before_frames"]
            and after_inspection["start_frame"] == link["after_frames"]
            and before_inspection["parent_invocation"] == after_inspection["parent_invocation"] == link["invocation"],
            "Original event action is detached from its own before/after native inspections")
        recipe = event["recipe"]
        if event["kind"] == "comparison":
            require(link["sequence"] is None and link["invocation"] in details["invocations"], "Comparison has no live native invocation")
            invocation = details["invocations"][link["invocation"]]
            require(invocation["action"] == "compare" and invocation["arguments"]["operator"] == "eq"
                and invocation["start_frame"] < link["before_frames"] <= link["after_frames"] < invocation["end_frame"],
                "Original comparison was not executed inside its native equality invocation")
            pair = [provider(invocation["arguments"][key]) for key in ("left", "right")]
            require(sorted(pair) == sorted([recipe["left"], recipe["right"]]), "Native comparison used different actual callables")
            comparison_groups.setdefault(link["invocation"], []).append(event)
            continue
        require(event["kind"] == "manager", "Unknown original event kind")
        op = recipe["operation"]
        if op == "target":
            require(link["sequence"] is None and link["before_frames"] == link["after_frames"] and event["outcome"] == "returned",
                    "Cached target observation unexpectedly performed I/O")
            equal(event["result"], expected["setup"]["target"], "Cached target changed original authority")
            continue
        seq = link["sequence"]
        require(type(seq) is int and seq in commands and seq not in event_commands, "Original manager action is detached from actual command")
        event_commands[seq] = event
        command = commands[seq]
        require(command["operation"] == op.replace("_", "-") and command["start_frame"] == link["before_frames"]
            and command["end_frame"] + 1 == link["after_frames"] and command["parent_invocation"] == link["invocation"],
            "Original manager action is bound to a different command or callback stack")
        args = command["arguments"]
        if op in ("register", "register_component_input"):
            equal(args["contract"], expected["setup"]["contracts"][recipe["contract"]], "Actual native registration used another contract")
            argument(args["validators"], {"kind": "validators", "items": recipe["validators"]})
            if op == "register":
                argument(args["producer"], {"kind": "provider", "label": recipe["producer"]})
                require(provider(args["producer"]) == recipe["producer"], "Producer argument identity differs")
        elif op == "set_dependency":
            equal(args, {"key": recipe["key"], "identity": recipe["identity"]}, "Actual dependency mutation differs")
        else:
            require(op == "get", "Unreviewed comparison manager operation")
            equal(args, {"identity": recipe["identity"]}, "Actual get requested another artifact")
        outcome = command["outcome"]
        if event["outcome"] == "returned":
            require(outcome["status"] == "ok", "Actual native command failed an original successful operation")
            result = outcome["value"]
            if op == "get":
                require(type(result) is dict and set(result) == {"value", "bindings"}, "Native get omitted its full record")
                result = result["value"]
            equal(result, event["result"], "Actual native returned value differs from original observation")
        elif outcome["status"] == "rejected":
            descriptor = outcome["value"]
            equal(descriptor, {**event["error"], "attributes": {}, "attributes_tree": ["object", []]},
                "Actual native rejection descriptor differs from original error")
        else:
            require(outcome["status"] == "raise" and outcome["token"] in link["exception_tokens"],
                    "Original host exception is detached from actual command token")
    require(used_arguments == set(source["arguments"]), "Unclaimed original source argument evidence")
    wanted_commands = {entry["sequence"] for entry in details["commands"] if entry["operation"] not in ("initialize-empty", "add-input", "inspect-ordered")}
    require(set(event_commands) == wanted_commands, "Unclaimed or missing actual comparison command")
    tokens = {}
    require(type(exceptions) is list, "Missing exact host exception identity evidence")
    for entry in exceptions:
        require(type(entry) is dict and set(entry) == {"token", "invocation", "events"} and type(entry["token"]) is str
            and re.fullmatch(r"exception/[0-9]+", entry["token"]) and entry["token"] not in tokens
            and type(entry["invocation"]) is int and entry["invocation"] in details["invocations"]
            and type(entry["events"]) is list and entry["events"] == sorted(set(entry["events"]))
            and entry["events"] and all(type(identity) is int and 0 <= identity < len(links) for identity in entry["events"]),
            "Malformed retained original exception identity")
        equal(details["invocations"][entry["invocation"]]["outcome"], {"status": "raise", "token": entry["token"]},
            "Actual continuation lost its exact original exception token")
        wanted_events = [link["event"] for link in links if entry["token"] in link["exception_tokens"]]
        equal(entry["events"], wanted_events, "Original exception identity aliases differ")
        descriptors = [expected["events"][identity]["error"] for identity in entry["events"]]
        require(all(item == descriptors[0] for item in descriptors), "Same actual exception acquired different original descriptions")
        tokens[entry["token"]] = entry
    require(set(tokens) == {token for link in links for token in link["exception_tokens"]}, "Unaccounted original host exception")
    require(set(tokens) == {item["outcome"]["token"] for item in details["invocations"].values() if item["outcome"]["status"] == "raise"},
        "Native callback exception lacks actual source identity evidence")
    for identity, events in comparison_groups.items():
        invocation = details["invocations"][identity]
        require(invocation["command_sequence"] in event_commands, "Native comparison was not requested by an original registration")
        owner = event_commands[invocation["command_sequence"]]
        require(owner["recipe"]["operation"] in ("register", "register_component_input"), "Unexpected comparison owner")
        contract = expected["setup"]["contracts"][owner["recipe"]["contract"]]
        group = "provider_history" if owner["recipe"]["operation"] == "register" else "component_input_history"
        old = [entry for entry in owner["before"]["state"][group].values() if entry["contract"] == contract]
        require(len(old) == 1, "Native equality was not against original provider history")
        left, right = (provider(invocation["arguments"][key]) for key in ("left", "right"))
        current = dict(owner["recipe"]["validators"])
        require(any(value == left and current[key] == right for key, value in old[0]["validators"].items()),
                "Native equality reversed or substituted original old/new providers")
        final = events[-1]
        if final["outcome"] == "returned":
            require(type(final["result"]) is bool, "Original reflected comparison did not resolve to boolean")
            equal(invocation["outcome"], {"status": "return", "value": final["result"]}, "Actual comparison continuation differs from original result")
        else:
            require(invocation["outcome"]["status"] == "raise" and invocation["outcome"]["token"] in links[final["id"]]["exception_tokens"],
                    "Actual comparison continuation detached from original exception")
            token = invocation["outcome"]["token"]
            equal(commands[invocation["command_sequence"]]["outcome"], {"status": "raise", "token": token},
                "Owning registration translated the original host exception instead of propagating its token")
            require(token in links[owner["id"]]["exception_tokens"],
                "Owning registration did not rethrow the same actual original exception object")


def validate_existing_checks(receipt, corpus, artifacts, *, sessions=None):
    channel, application = declarations()
    validate_verify(receipt, artifacts, channel, application)
    require(type(receipt.get("completed_checks")) is int and receipt["completed_checks"] == 5
        and type(receipt.get("checks")) is list and len(receipt["checks"]) == 5, "Incomplete five-case original manager campaign")
    equal(artifacts.json(receipt["pending"], r.MAX_ARTIFACT_BYTES), corpus.pending, "Mandatory unreplayed inventory changed or disappeared")
    sessions, projected = set() if sessions is None else sessions, []
    for expected, row in zip(corpus.cases, receipt["checks"]):
        require(type(row) is dict and set(row) == {"id", "original", "actual", "frames", "pid", "returncode", "closed",
            "invalidated", "executable_sha256", "stderr", "guard", "after_close"}
            and row["id"] == expected["case"], "Missing, duplicated or reordered original identity case")
        equal(artifacts.json(row["original"], r.MAX_ARTIFACT_BYTES), expected, "Frozen original case content differs")
        equal(artifacts.json(row["actual"], r.MAX_ARTIFACT_BYTES), expected, "Complete actual case differs from original oracle")
        require(type(row["pid"]) is int and row["pid"] > 0 and type(row["returncode"]) is int and row["returncode"] == 0
            and row["closed"] is True and row["invalidated"] is False
            and row["executable_sha256"] == receipt["native_inputs"]["sha256"]["biocompiler-core"],
            "Real native manager process identity or lifecycle differs")
        equal(artifacts.json(row["stderr"]), {"hex": ""}, "Native manager wrote stderr")
        check_guard(artifacts.json(row["guard"], r.MAX_ARTIFACT_BYTES), frames=row["frames"], artifacts=artifacts)
        equal(artifacts.json(row["after_close"]), {"type": "CoreProtocolError",
            "message": "Callback session is closed; it cannot reconnect", "traffic_unchanged": True, "pid_unchanged": True},
            "Closed manager resumed, retried or changed its rejection")
        traffic = validate_frames(row["frames"], artifacts, channel, application, sessions=sessions)
        required = {"register-component-input", "admit-component-input"} if row["id"].startswith("admission:") else {"add-input", "register", "run"}
        require(required <= set(traffic["operations"]), "Original case did not execute native acceptance operations")
        projected.append({"id": row["id"], "complete_case_sha256": row["actual"], **traffic})
    require(type(receipt.get("completed_comparison_checks")) is int and receipt["completed_comparison_checks"] == 34
        and type(receipt.get("comparison_checks")) is list and len(receipt["comparison_checks"]) == 34,
        "Incomplete 34-case original comparison campaign")
    equal(artifacts.json(receipt["fresh_comparison_original"], r.MAX_ARTIFACT_BYTES), corpus.oracles["callbacks"],
        "Complete fresh original comparison counterpart differs")
    validate_counterpart = fixed.source_tool("pipeline_original_counterpart").validate
    counterpart = artifacts.json(receipt['comparison_original_counterpart'], r.MAX_ARTIFACT_BYTES)
    equal(validate_counterpart(counterpart), corpus.oracles['callbacks'], 'Fresh comparison lost original canonical execution')
    require(counterpart['manifest']['package_root'] == str(Path(receipt['package_path']).parent),
        'Comparison original counterpart source package differs')
    for expected, row in zip(corpus.comparisons, receipt["comparison_checks"]):
        require(type(row) is dict and set(row) == {"id", "original", "actual", "frames", "pid", "returncode", "closed",
            "invalidated", "executable_sha256", "stderr", "guard", "after_close", "inspections", "events", "host_exceptions", "source_bindings"}
            and row["id"] == expected["id"], "Missing, duplicated or reordered original comparison case")
        equal(artifacts.json(row["original"], r.MAX_ARTIFACT_BYTES), expected, "Original comparison case changed")
        equal(artifacts.json(row["actual"], r.MAX_ARTIFACT_BYTES), expected, "Complete actual comparison case differs")
        require(type(row["pid"]) is int and row["pid"] > 0 and type(row["returncode"]) is int and row["returncode"] == 0
            and row["closed"] is True and row["invalidated"] is False
            and row["executable_sha256"] == receipt["native_inputs"]["sha256"]["biocompiler-core"],
            "Actual comparison process identity or lifecycle differs")
        equal(artifacts.json(row["stderr"]), {"hex": ""}, "Comparison native process wrote stderr")
        guard = artifacts.json(row["guard"], r.MAX_ARTIFACT_BYTES)
        check_guard(guard, frames=row["frames"], artifacts=artifacts)
        require(["biocompiler.core_pipeline_manager", "CorePassManager.inspect_ordered"] in guard,
            "Comparison did not inspect actual native manager state")
        equal(artifacts.json(row["after_close"]), {"type": "CoreProtocolError",
            "message": "Callback session is closed; it cannot reconnect", "traffic_unchanged": True, "pid_unchanged": True},
            "Closed comparison manager resumed or changed its rejection")
        details = {}
        traffic = validate_frames(row["frames"], artifacts, channel, application, sessions=sessions,
            details=details, provider_calls=False)
        required = {"register-component-input"} if expected["mode"] == "admission" else {"add-input", "register"}
        require(required <= set(traffic["operations"]) and "callable" in traffic["actions"],
                "Original comparison did not execute live native registration and host callbacks")
        snapshots = artifacts.json(row["inspections"], r.MAX_ARTIFACT_BYTES)
        source = artifacts.json(row["source_bindings"], r.MAX_ARTIFACT_BYTES)
        validate_comparison_events(expected, artifacts.json(row["events"], r.MAX_ARTIFACT_BYTES), source,
            artifacts.json(row["host_exceptions"], r.MAX_ARTIFACT_BYTES), details, snapshots)
        wanted = original_snapshots(expected)
        require(type(snapshots) is list and len(snapshots) == len(wanted), "Original inspection census was narrowed")
        sequences, aliases_seen = [], {}
        for observation, original_state in zip(snapshots, wanted):
            require(type(observation) is dict and set(observation) == {"sequence", "aliases"}
                and type(observation["sequence"]) is int and observation["sequence"] in details["inspections"],
                "Inspection was not bound to a complete native reply")
            sequence, aliases = observation["sequence"], observation["aliases"]
            require(type(aliases) is dict and all(label in expected["providers"] for label in aliases.values()),
                    "Inspection introduced a provider outside the original source recipe")
            sequences.append(sequence)
            native = details["inspections"][sequence]
            actual_state = comparison_snapshot(native["value"], aliases, previous=aliases_seen, bound=native["bound"])
            require(all(source["providers"].get(aliases[item["provider_id"]]) == item["object"]["handle"]
                for item in native["value"]["providers"]), "Native state aliases differ from actual source callable objects")
            equal(actual_state, original_state, "Complete native comparison state/order differs at its original observation")
        require(sequences == list(details["inspections"]) and len(set(sequences)) == len(sequences),
                "Native inspection was duplicated, omitted or reordered")
        projected.append({"id": row["id"], "complete_case_sha256": row["actual"],
            "inspections_sha256": row["inspections"], "events_sha256": row["events"],
            "source_bindings_sha256": row["source_bindings"], "host_exceptions_sha256": row["host_exceptions"],
            "inspections": len(snapshots), **traffic})
    return projected


def validate_deferred_checks(receipt, corpus, artifacts, *, sessions=None):
    require(type(receipt.get("completed_deferred_checks")) is int and receipt["completed_deferred_checks"] == 47
        and type(receipt.get("deferred_checks")) is list and len(receipt["deferred_checks"]) == 47,
        "Incomplete 47-case original deferred campaign")
    _, runtime = runtime_helpers()
    fresh = artifacts.json(receipt["fresh_deferred_original"], r.MAX_ARTIFACT_BYTES)
    proof = artifacts.json(receipt["deferred_runtime_authority"], r.MAX_ARTIFACT_BYTES)
    runtime.validate_retained(corpus.oracles["deferred"], fresh, proof, python_version=receipt["python_version"])
    validate_counterpart = fixed.source_tool("pipeline_original_counterpart").validate
    counterpart = artifacts.json(receipt['deferred_original_counterpart'], r.MAX_ARTIFACT_BYTES)
    value = validate_counterpart(counterpart)
    equal(value, {'capture': fresh, 'proof': proof}, 'Deferred original proof detached from canonical child execution')
    require(counterpart['manifest']['package_root'] == str(Path(receipt['package_path']).parent),
        'Original counterpart is detached from installed package source')
    for logical in ("src/biocompiler/compiler/pipeline.py", "src/biocompiler/ir/intent.py"):
        source = proof["capture_authority"]["sources"][logical]
        row = next(item for item in counterpart['manifest']['sources'] if item['logical'] == logical)
        require(source['path'] == row['path'] and source['sha256'] == row['sha256']
            and row['origin_sha256'] == receipt['python_sources'][logical],
            'Deferred original runtime proof lost exact original/current source distinction')
    channel, application = declarations()
    sessions = set() if sessions is None else sessions
    projected = []
    for expected, frozen, row in zip(fresh["cases"], corpus.deferred, receipt["deferred_checks"]):
        require(type(row) is dict and set(row) == {"id", "original", "actual", "evidence", "bootstrap_original", "processes", "guard"}
            and row["id"] == expected["id"] == frozen["id"], "Missing, duplicated or reordered deferred case")
        equal(artifacts.json(row["original"], r.MAX_ARTIFACT_BYTES), expected, "Complete fresh original deferred case changed")
        actual = artifacts.json(row["actual"], r.MAX_ARTIFACT_BYTES)
        evidence = artifacts.json(row["evidence"], r.MAX_ARTIFACT_BYTES)
        bootstrap = artifacts.json(row["bootstrap_original"], r.MAX_ARTIFACT_BYTES)
        bootstrap_case = next(item for item in fresh["cases"] if item["id"] ==
            ("admission:nested_admission" if expected["mode"] == "admission" else "proposal:valid"))
        equal(bootstrap, bootstrap_case["initial_state"], "Fresh original fixture setup changed outside the unchanged source")
        count = 2 if row["id"].startswith("input:") else 1
        require(type(row["processes"]) is list and len(row["processes"]) == count, "Deferred actual native lifetime census differs")
        details, traffic = [], []
        for process in row["processes"]:
            require(type(process) is dict and set(process) == {"pid", "returncode", "closed", "invalidated",
                "executable_sha256", "stderr", "frames", "after_close"}
                and type(process["pid"]) is int and process["pid"] > 0
                and type(process["returncode"]) is int and process["returncode"] == 0
                and process["closed"] is True and process["invalidated"] is False
                and process["executable_sha256"] == receipt["native_inputs"]["sha256"]["biocompiler-core"],
                "Deferred actual native process authority or lifecycle differs")
            equal(artifacts.json(process["stderr"]), {"hex": ""}, "Deferred native process wrote stderr")
            equal(artifacts.json(process["after_close"]), {"type": "CoreProtocolError",
                "message": "Callback session is closed; it cannot reconnect", "traffic_unchanged": True, "pid_unchanged": True},
                "Closed deferred manager resumed or changed its rejection")
            details.append({})
            traffic.append(validate_frames(process["frames"], artifacts, channel, application,
                sessions=sessions, details=details[-1], provider_calls=False))
        guard = artifacts.json(row["guard"], r.MAX_ARTIFACT_BYTES)
        check_guard(guard, frames=[process["frames"] for process in row["processes"]], artifacts=artifacts)
        require(["biocompiler.core_pipeline_manager", "CorePassManager.inspection_state"] in guard,
            "Deferred snapshot did not use the checked native historical view")
        validate_deferred_events(actual, evidence, details, bootstrap)
        compared = deferred_fingerprint_projection(actual, evidence, details)
        compared, correspondence = deferred_trace_projection(compared, expected, evidence, details)
        equal(compared, expected, "Complete native deferred behavior differs from fresh original authority")
        # Every raw source/runtime/native difference has now been checked. The
        # canonical comparison uses the unchanged frozen case, while the exact
        # current original and actual documents remain mandatory artifacts.
        projected.append({"id": row["id"], "complete_canonical_case_sha256": r.digest(frozen),
            "processes": traffic, "events": len(actual["events"]), "accesses": len(compared["access_log"]),
            "inspections": len(evidence["inspections"]), "exception_correspondences": len(correspondence)})
    require(sum(len(row["processes"]) for row in receipt["deferred_checks"]) == 53,
        "Complete deferred process census differs")
    return projected


def validate_checks(receipt, corpus, artifacts):
    sessions = set()
    result = validate_existing_checks(receipt, corpus, artifacts, sessions=sessions)
    result.extend(validate_deferred_checks(receipt, corpus, artifacts, sessions=sessions))
    require(artifacts.used == set(artifacts.declared), "Unreferenced complete manager evidence")
    return result


def python_sources():
    return r.source_pins("src/" + name.replace(".", "/") + ".py" for name in sorted(REVIEWED_MODULES))


def compare(root, native_root, *, revision, source_revision, run_id):
    require(type(revision) is str and re.fullmatch(r"[0-9a-f]{40}", revision)
        and type(source_revision) is str and re.fullmatch(r"[0-9a-f]{40}", source_revision)
        and type(run_id) is str and run_id, "Missing current manager validation authority")
    root, native_root = Path(root), Path(native_root)
    names = {"realization-" + target + "-py" + python for target in r.PLATFORMS for python in r.PYTHONS}
    require(root.is_dir() and not root.is_symlink() and native_root.is_dir() and not native_root.is_symlink()
        and {path.name for path in root.iterdir() if path.name.startswith("realization-")} == names,
        "Incomplete four-runtime manager matrix")
    corpus, receipts, binaries, reference = Corpus(), {}, {}, None
    for target, (system, machine) in r.PLATFORMS.items():
        native = r.verify_binaries(native_root / target, revision, target)
        binaries[target] = native
        for python in r.PYTHONS:
            name = "realization-" + target + "-py" + python
            directory = root / name
            require(directory.is_dir() and not directory.is_symlink(), "Unsafe manager runtime slot")
            inputs, inputs_pin = r.read(directory / "native-inputs.json", r.CONTROL_BYTES)
            require(all(inputs.get(key) == value for key, value in native.items()) and inputs.get("run_id") == run_id
                and inputs.get("source_revision") == source_revision and type(inputs.get("python_version")) is str
                and inputs["python_version"].startswith(python + "."), "Stale manager native inputs")
            receipt, receipt_pin = r.read(directory / RECEIPT_FILE)
            wanted = {"schema_version": SCHEMA, "status": "success", "scope": SCOPE, "revision": revision,
                "source_revision": source_revision, "run_id": run_id, "python_version": inputs["python_version"],
                "system": system, "machine": machine, "native_platform": target,
                "artifact_directory": ARTIFACT_DIRECTORY, "native_inputs": native,
                "python_sources": python_sources(), "campaign_sources": r.source_pins(SOURCES), **metadata(corpus)}
            for key, value in wanted.items():
                equal(receipt.get(key), value, "Stale or mixed manager receipt: " + key)
            require(type(receipt.get("package_path")) is str and Path(receipt["package_path"]).is_absolute()
                and not Path(receipt["package_path"]).is_relative_to(ROOT), "Manager package was not installed")
            require(type(receipt.get("executables")) is dict and set(receipt["executables"]) == {"core", "verify"}
                and all(type(path) is str and Path(path).is_absolute() and Path(path).name == "biocompiler-" + role
                    for role, path in receipt["executables"].items())
                and Path(receipt["executables"]["core"]).parent == Path(receipt["executables"]["verify"]).parent,
                "Exact manager binary selection absent")
            artifacts = Artifacts(directory / ARTIFACT_DIRECTORY, receipt["artifacts"])
            projected = canonical(validate_checks(receipt, corpus, artifacts))
            require(reference is None or projected == reference, "Complete native manager observations differ across four runtimes")
            reference = projected
            receipts[name] = {"receipt_sha256": receipt_pin, "native_inputs_sha256": inputs_pin,
                              "complete_artifacts": artifacts.verified}
    return {"schema_version": "biocompiler.pipeline_manager_reproducibility.v1", "status": "success", "scope": SCOPE,
        "revision": revision, "source_revision": source_revision, "run_id": run_id, **metadata(corpus),
        "receipts": receipts, "native_inputs": binaries, "complete_results_sha256": sha(reference),
        "projection": "validated_unique_session_UUID4_and_process_PID_only;exact_command_invocation_hash_bindings_verified_before_projection;complete_frames_retained"}


def campaign_main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ("core", "verify"):
        parser.add_argument("--" + role, required=True, type=Path)
        parser.add_argument("--" + role + "-sha256", required=True)
    parser.add_argument("--native-root", required=True, type=Path)
    parser.add_argument("--platform", required=True, choices=r.PLATFORMS)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    import biocompiler
    from biocompiler.core_client import CoreClient
    for name in sorted(REVIEWED_MODULES):
        importlib.import_module(name)
    corpus, directory = Corpus(), args.output.with_name(ARTIFACT_DIRECTORY)
    directory.mkdir(parents=True, exist_ok=True)
    require(not directory.is_symlink() and not any(directory.iterdir()), "Unsafe or nonempty manager artifact directory")
    started = time.monotonic()
    receipt = {"schema_version": SCHEMA, "status": "running", "scope": SCOPE, **metadata(corpus),
        "revision": os.environ.get("GITHUB_SHA"), "source_revision": os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")),
        "run_id": os.environ.get("GITHUB_RUN_ID"), "python_version": platform.python_version(), "system": platform.system(),
        "machine": platform.machine(), "native_platform": args.platform, "package_path": str(Path(biocompiler.__file__).resolve()),
        "checks": [], "comparison_checks": [], "deferred_checks": [], "artifacts": {},
        "artifact_directory": ARTIFACT_DIRECTORY, "_artifact_directory": str(directory)}
    code = 1
    try:
        require(not Path.cwd().resolve().is_relative_to(ROOT), "Run installed manager campaign outside checkout")
        require(receipt["run_id"] and receipt["source_revision"]
            and (platform.system(), platform.machine()) == r.PLATFORMS[args.platform], "Missing or mismatched hosted manager authority")
        installed_modules()
        native = r.verify_binaries(args.native_root, receipt["revision"], args.platform)
        receipt["native_inputs"], receipt["executables"] = native, {}
        for role in ("core", "verify"):
            path, pin = getattr(args, role), getattr(args, role + "_sha256")
            require(path.is_absolute() and path.resolve() == (native_executable(args.native_root, role)).resolve()
                and not path.is_symlink() and os.access(path, os.X_OK) and pin == native["sha256"][path.name], "Unbound manager binary")
            receipt["executables"][role] = str(path)
        receipt["python_sources"] = python_sources()
        for name in sorted(REVIEWED_MODULES):
            relative = "src/" + name.replace(".", "/") + ".py"
            require(sha(r.raw_file(Path(sys.modules[name].__file__))) == receipt["python_sources"][relative],
                    "Installed manager source differs: " + name)
        receipt["campaign_sources"] = r.source_pins(SOURCES)
        client = CoreClient(args.core, role="core", expected_sha256=args.core_sha256, timeout_seconds=300)
        verify_rejection(args.verify, args.verify_sha256, receipt)
        campaign(client, corpus, receipt)
        receipt["completed_checks"] = len(receipt["checks"])
        comparison_campaign(client, corpus, receipt)
        receipt["completed_comparison_checks"] = len(receipt["comparison_checks"])
        deferred_campaign(client, corpus, receipt)
        receipt["completed_deferred_checks"] = len(receipt["deferred_checks"])
        validate_checks(receipt, corpus, Artifacts(directory, receipt["artifacts"]))
        equal(r.verify_binaries(args.native_root, receipt["revision"], args.platform), native, "Manager binaries changed during execution")
        receipt["status"], code = "success", 0
    except Exception as error:
        receipt["status"], receipt["error"] = "failure", type(error).__name__ + ": " + str(error)
        print(receipt["error"], file=sys.stderr)
    receipt["completed_checks"], receipt["duration_seconds"] = len(receipt["checks"]), round(time.monotonic() - started, 6)
    receipt["completed_comparison_checks"] = len(receipt["comparison_checks"])
    receipt["completed_deferred_checks"] = len(receipt["deferred_checks"])
    del receipt["_artifact_directory"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(receipt) + b"\n")
    print("Installed pipeline manager:", receipt["status"], receipt["completed_checks"], "original identity cases,",
        receipt["completed_comparison_checks"], "original comparison cases,", receipt["completed_deferred_checks"], "original deferred cases")
    return code


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--compare" not in arguments:
        return campaign_main(arguments)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare", required=True, action="store_true")
    for name in ("root", "native-root", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    options = parser.parse_args(arguments)
    result = compare(options.root, options.native_root, revision=os.environ.get("GITHUB_SHA"),
        source_revision=os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")), run_id=os.environ.get("GITHUB_RUN_ID"))
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_bytes(canonical(result) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

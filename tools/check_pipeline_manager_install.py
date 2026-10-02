"""Installed live-manager replay with complete original identity/order evidence.

Only fresh native sessions decide registration, freshness and acceptance. The
unchanged original case functions execute real host callbacks; saved outcomes
are comparison data only. This additive gate does not close the older full
manager, callback, deferred-access or fixed-registration-interception inventory.
"""
from __future__ import annotations

import argparse
import builtins
from contextlib import contextmanager
from copy import deepcopy
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
from types import MappingProxyType
from uuid import UUID, uuid4

if __package__:
    from . import check_workflow_reproducibility as r
    from . import check_pipeline_session_install as fixed
else:
    import check_workflow_reproducibility as r
    import check_pipeline_session_install as fixed

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "biocompiler.installed_pipeline_manager_conformance.v1"
SCOPE = "five_identity_cases_and_34_original_comparison_cases_complete_live_evidence_not_full_manager_cutover"
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
    "biocompiler.core_pipeline_callback_session", "biocompiler.pipeline_callback_objects", "biocompiler.core_pipeline_manager"}
LITERAL_MODULES = {"biocompiler.compiler.pipeline", "biocompiler.compiler.passes", "biocompiler.ir.intent",
    "biocompiler.ir.serialization", "biocompiler.ir.stages", "biocompiler.errors", "biocompiler.artifacts.provenance",
    "biocompiler.semantics.context", "biocompiler.verification.evidence"}
SOURCES = ("tools/check_pipeline_manager_install.py", "tests/test_pipeline_manager_campaign.py",
    "tools/check_pipeline_session_install.py", "tools/check_workflow_reproducibility.py", "tools/check_realization_binaries.py",
    "tools/capture_pipeline_identity_semantics.py", "tests/test_pipeline_identity_semantics.py",
    "tools/capture_pipeline_callback_semantics.py", "tests/test_pipeline_callback_semantics.py", CHANNEL_PATH, APPLICATION_PATH)
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
                    require(sha(r.raw_file(ROOT / path)) == identity, "Original oracle source changed: " + path)
                    self.original_sources[path] = identity
            self.oracles[label], self.pins[label] = value, {"path": "tests/conformance/" + name, "sha256": actual,
                "inventory_fingerprint": value["inventory_fingerprint"]}
        self.cases = self.oracles["identity"]["cases"]
        self.comparisons = self.oracles["callbacks"]["cases"]
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
            "status": "mandatory_separate_unfinished_gate_not_replayed_by_this_identity_campaign",
            "original_contexts": [entry["id"] for entry in complete["contexts"]],
            "original_context_count": 476, "original_event_count": 91566,
            "fixed_pending": original_fixed.pending(), "fixed_census": original_fixed.census,
            "fixed_unreplayed_observations": 287,
            "callback_cases": [case["id"] for case in self.oracles["callbacks"]["cases"]],
            "callback_case_status": "covered_only_when_all_34_live_comparison_receipts_validate;not_a_substitute_for_full_original_contexts",
            "deferred_cases": [case["id"] for case in self.oracles["deferred"]["cases"]],
            "deferred_runtime_counterparts": self.oracles["deferred"]["runtime_counterparts"],
            "external_native_provider_contexts": "pending_general_import;original_wrappers_use_exact_supplied_context",
            "default_cutover": "not_authorized_by_this_campaign",
        }


def metadata(corpus):
    return {"oracle_pins": corpus.pins, "original_sources": corpus.original_sources,
            "coverage": COVERAGE, "comparison_coverage": COMPARISON_COVERAGE,
            "declarations": r.source_pins((CHANNEL_PATH, APPLICATION_PATH))}


def permitted(module, qualname):
    if module in TRANSPORT_MODULES:
        return True
    if module not in LITERAL_MODULES:
        return False
    # Literal dataclasses and explicitly native-requested host serialization are
    # allowed. Every method/property of the original Python acceptance manager
    # is forbidden while an actual adapter operation is active.
    return not (module == "biocompiler.compiler.pipeline" and qualname.startswith("PassManager."))


@contextmanager
def guarded_execution(seen, observer=None):
    previous, original_import = sys.getprofile(), builtins.__import__
    def calls(frame, event, result):
        module = frame.f_globals.get("__name__", "")
        if event == "call" and module.startswith("biocompiler"):
            name = frame.f_code.co_qualname
            require(permitted(module, name), "Python manager semantic authority is forbidden: " + module + "." + name)
            seen.add((module, name))
        if observer is not None:
            observer(frame, event, result)
    def imports(name, *args, **kwargs):
        if name.startswith("biocompiler"):
            require(name in TRANSPORT_MODULES | LITERAL_MODULES, "Unreviewed manager import: " + name)
        return original_import(name, *args, **kwargs)
    builtins.__import__ = imports
    sys.setprofile(calls)
    try:
        yield
        require(sys.getprofile() is calls and builtins.__import__ is imports, "Manager execution guard was disabled")
    finally:
        sys.setprofile(previous)
        builtins.__import__ = original_import


def check_guard(entries):
    require(type(entries) is list and entries == sorted(entries) and len({tuple(item) for item in entries}) == len(entries)
        and all(type(item) is list and len(item) == 2 and all(type(value) is str for value in item) for item in entries),
        "Invalid complete manager guard census")
    require(all(permitted(*item) for item in entries), "Forbidden Python acceptance execution in guard census")
    for required in (("biocompiler.core_pipeline_manager", "CorePassManager.__init__"),
            ("biocompiler.core_pipeline_callback_session", "CorePipelineCallbackSession.__init__"),
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


def load_oracle(*, installed=True, comparison=False):
    # Import every product dependency before the unchanged oracle temporarily
    # prepends checkout/src. Only pinned test helpers are intentionally loaded
    # from the checkout. Restore the exact path even if fixture loading fails.
    for name in sorted(TRANSPORT_MODULES | LITERAL_MODULES):
        importlib.import_module(name)
    if installed:
        installed_modules()
    paths = list(sys.path)
    try:
        name = "callback" if comparison else "identity"
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


def comparison_campaign(core, corpus, receipt):
    from biocompiler.core_pipeline_manager import CorePassManager
    from biocompiler.core_client import CoreProtocolError
    oracle = load_oracle(comparison=True)
    fresh = oracle.capture()
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


def validate_frames(rows, artifacts, channel, application, *, sessions=None, details=None, provider_calls=True):
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
        nodes += json_nodes(value)
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
    require(operations and operations[0] == "initialize-empty" and operations.count("initialize-empty") == 1,
            "A real manager was not initialized exactly once")
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
            equal(descriptor, {**event["error"], "attributes": {}}, "Actual native rejection descriptor differs from original error")
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


def validate_checks(receipt, corpus, artifacts):
    channel, application = declarations()
    validate_verify(receipt, artifacts, channel, application)
    require(type(receipt.get("completed_checks")) is int and receipt["completed_checks"] == 5
        and type(receipt.get("checks")) is list and len(receipt["checks"]) == 5, "Incomplete five-case original manager campaign")
    equal(artifacts.json(receipt["pending"], r.MAX_ARTIFACT_BYTES), corpus.pending, "Mandatory unreplayed inventory changed or disappeared")
    sessions, projected = set(), []
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
        check_guard(artifacts.json(row["guard"], r.MAX_ARTIFACT_BYTES))
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
        check_guard(guard)
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
    require(artifacts.used == set(artifacts.declared), "Unreferenced complete manager evidence")
    return projected


def python_sources():
    return r.source_pins("src/" + name.replace(".", "/") + ".py" for name in sorted(TRANSPORT_MODULES | LITERAL_MODULES))


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
    for name in sorted(TRANSPORT_MODULES | LITERAL_MODULES):
        importlib.import_module(name)
    corpus, directory = Corpus(), args.output.with_name(ARTIFACT_DIRECTORY)
    directory.mkdir(parents=True, exist_ok=True)
    require(not directory.is_symlink() and not any(directory.iterdir()), "Unsafe or nonempty manager artifact directory")
    started = time.monotonic()
    receipt = {"schema_version": SCHEMA, "status": "running", "scope": SCOPE, **metadata(corpus),
        "revision": os.environ.get("GITHUB_SHA"), "source_revision": os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")),
        "run_id": os.environ.get("GITHUB_RUN_ID"), "python_version": platform.python_version(), "system": platform.system(),
        "machine": platform.machine(), "native_platform": args.platform, "package_path": str(Path(biocompiler.__file__).resolve()),
        "checks": [], "comparison_checks": [], "artifacts": {}, "artifact_directory": ARTIFACT_DIRECTORY, "_artifact_directory": str(directory)}
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
            require(path.is_absolute() and path.resolve() == (args.native_root / ("biocompiler-" + role)).resolve()
                and not path.is_symlink() and os.access(path, os.X_OK) and pin == native["sha256"][path.name], "Unbound manager binary")
            receipt["executables"][role] = str(path)
        receipt["python_sources"] = python_sources()
        for name in sorted(TRANSPORT_MODULES | LITERAL_MODULES):
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
        validate_checks(receipt, corpus, Artifacts(directory, receipt["artifacts"]))
        equal(r.verify_binaries(args.native_root, receipt["revision"], args.platform), native, "Manager binaries changed during execution")
        receipt["status"], code = "success", 0
    except Exception as error:
        receipt["status"], receipt["error"] = "failure", type(error).__name__ + ": " + str(error)
        print(receipt["error"], file=sys.stderr)
    receipt["completed_checks"], receipt["duration_seconds"] = len(receipt["checks"]), round(time.monotonic() - started, 6)
    receipt["completed_comparison_checks"] = len(receipt["comparison_checks"])
    del receipt["_artifact_directory"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(receipt) + b"\n")
    print("Installed pipeline manager:", receipt["status"], receipt["completed_checks"], "original identity cases,",
        receipt["completed_comparison_checks"], "original comparison cases")
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

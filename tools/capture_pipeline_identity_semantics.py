"""Additive original-manager oracle for retained identity and insertion order.

Every case executes real providers against a fresh, unchanged manager. Values
are never obtained by replaying saved callback decisions. This file also exposes
case functions for a future live native-backed public adapter; that separate
execution must match the frozen original observations and complete records.
"""
from __future__ import annotations

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
from biocompiler.compiler import pipeline
from biocompiler.compiler.passes import PassResult
from biocompiler.ir.serialization import fingerprint
from biocompiler.ir.stages import Stage
from biocompiler.verification.evidence import CheckOutcome, EvidenceKind
from test_pipeline import PipelineTests
from test_component_admission import ComponentAdmissionTests

OUTPUT = ROOT / "tests/conformance/pipeline-identity-semantics-v1.json"
SCHEMA = "biocompiler.pipeline_identity_semantics.v1"
SAFE = {pipeline.StageRecord, pipeline.PassContext, pipeline.ScopedObligation,
    pipeline.PipelineResult, pipeline.PassContract, pipeline.ComponentInputContract,
    pipeline.CheckSpec, pipeline.CheckDecision, pipeline.CompletionProfile, SourceLink}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def plain(value):
    """Only exact trusted container/dataclass types; no arbitrary conversions."""
    if value is None or type(value) in (bool, int, float, str):
        return value
    if isinstance(value, Enum):
        return {"enum": type(value).__module__ + "." + type(value).__qualname__, "value": value.value}
    if type(value) in (dict, MappingProxyType):
        return {"mapping": [[plain(key), plain(item)] for key, item in value.items()]}
    if type(value) in (tuple, list):
        return {"sequence": "tuple" if type(value) is tuple else "list", "items": [plain(item) for item in value]}
    if type(value) in SAFE:
        return {"class": type(value).__module__ + "." + type(value).__qualname__,
                "fields": [[field.name, plain(object.__getattribute__(value, field.name))] for field in fields(value)]}
    raise AssertionError("Unsupported observation type: " + type(value).__name__)


class MarkerError(ValueError):
    pass


class Ledger:
    def __init__(self, name):
        self.name, self.retained, self.events = name, [], []

    def ref(self, value):
        for offset, previous in enumerate(self.retained):
            if previous is value:
                return "object/" + str(offset)
        self.retained.append(value)
        return "object/" + str(len(self.retained) - 1)

    def note(self, event, **values):
        self.events.append({"event": event, **values})

    def context(self, label, context):
        assert type(context) is pipeline.PassContext
        self.note(label, context=self.ref(context), fields={
            name: self.ref(object.__getattribute__(context, name)) for name in
            ("input", "output", "target", "configuration", "dependencies", "requirements", "source_links", "observation_map")},
            input_order=list(context.input), configuration=plain(context.configuration),
            dependencies=plain(context.dependencies), requirements=plain(context.requirements),
            links=plain(context.source_links), observation=plain(context.observation_map))

    def attempt(self, label, function):
        try:
            value = function()
        except (pipeline.PipelineError, MarkerError) as error:
            self.note(label, outcome="raised", type=type(error).__name__, message=str(error), args=plain(error.args))
            return error
        self.note(label, outcome="returned", value=plain(value))
        return value

    def finish(self, authority, records):
        return {"case": self.name, "authority": authority, "events": self.events,
                "records": [plain(record) for record in records], "retained_objects": len(self.retained)}


def fixture(manager_factory):
    original = PipelineTests()
    original.setUp()
    payload = {"schema_version": "intent.v1", "zeta": {"omega": 1, "alpha": 2},
               "nodes": [{"id": "n", "kind": "constant", "value": 1}], "alpha": "root"}
    dependencies = {"zeta": fingerprint("z"), "request": fingerprint(payload),
                    "registry": fingerprint("v1"), "alpha": fingerprint("a")}
    manager = manager_factory(target=original.target, dependencies=dependencies)
    requirements = ("zeta_requirement", "alpha_requirement")
    obligations = (original.exact, original.biological)
    source = manager.add_input("input", payload, requirements=requirements, obligations=obligations)
    contract = replace(original.first, checks=(
        pipeline.CheckSpec("z_check", EvidenceKind.EXACT, ("identity",)),
        pipeline.CheckSpec("a_check", EvidenceKind.EXACT)), introduces=(original.behavioral,))
    configuration = {"zeta": {"omega": 1, "alpha": 2}, "alpha": [3, 1]}
    authority = {"target": original.target.to_dict(), "input": plain(payload),
                 "dependencies": plain(dependencies), "requirements": plain(requirements),
                 "obligations": plain(obligations), "contract": plain(contract), "configuration": plain(configuration)}
    return original, manager, source, contract, configuration, authority, payload, obligations


def proposal(contract):
    output = {"schema_version": "behavior.v1", "zeta": {"omega": 3, "alpha": 4},
              "nodes": [{"id": "n", "kind": "constant", "value": 1}], "alpha": "output"}
    links = (SourceLink("alpha_requirement", "n", "n", contract.id),
             SourceLink("zeta_requirement", "n", "n", contract.id))
    return PassResult(output, (), links, {"zeta": {"omega": "n", "alpha": "n"}, "alpha": "n"})


def decision(context):
    # Execute a real comparison of current independently supplied source and
    # candidate. Saved records never choose this outcome.
    passed = context.output["nodes"][0]["value"] == context.input["nodes"][0]["value"]
    return pipeline.CheckDecision(CheckOutcome.PASS if passed else CheckOutcome.FAIL,
        "Compared original source and candidate values.", {"zeta": "source", "alpha": "candidate"})


def sharing_case(manager_factory=pipeline.PassManager):
    ledger = Ledger("run:sharing_and_order")
    original, manager, source, contract, configuration, authority, payload, obligations = fixture(manager_factory)
    contexts, produced = [], []
    ledger.note("root", target_is_supplied=manager.target is original.target,
        add_return_is_get=source is manager.get("input"), payload_is_original=source.payload is payload,
        source_obligations_tuple_is_supplied=source.obligations is obligations,
        source_obligations_are_supplied=source.obligations[0] is original.exact and source.obligations[1] is original.biological,
        source=ledger.ref(source), payload=ledger.ref(source.payload), target=ledger.ref(manager.target),
        requirements=ledger.ref(source.requirements), dependencies=ledger.ref(source.dependencies))

    def produce(context):
        ledger.context("producer", context)
        contexts.append(context)
        result = proposal(contract)
        produced.append(result)
        ledger.note("proposal", links=ledger.ref(result.source_links), observation=ledger.ref(result.observation_map),
                    output=ledger.ref(result.output))
        return result

    def validate(context):
        ledger.context("validator", context)
        contexts.append(context)
        return decision(context)

    manager.register(contract, produce, {"a_check": validate, "z_check": validate})
    record = manager.run(contract.id, "input", "output", configuration=configuration)
    manager.register_completion_profile(pipeline.CompletionProfile("sharing", Stage.BEHAVIOR, "behavior.v1", ("identity",)))
    first = manager.result("output", scope="sharing")
    second = manager.result("output", scope="sharing")
    producer, validator, validator2 = contexts
    ledger.note("sharing", validators_same_context=validator is validator2,
        producer_is_validator=producer is validator,
        shared_fields={key: object.__getattribute__(producer, key) is object.__getattribute__(validator, key)
                       for key in ("input", "target", "configuration", "dependencies", "requirements")},
        input_is_source=producer.input is source.payload,
        target_is_supplied=validator.target is original.target,
        requirement_tuple_is_source=record.requirements is source.requirements,
        obligations_reuse_source=all(record.obligations[index] is item for index, item in enumerate(source.obligations)),
        introduced_obligation_is_contract=record.obligations[-1] is contract.introduces[0],
        dependencies_are_callback_snapshot=record.dependencies is validator.dependencies,
        output_is_validator_output=record.payload is validator.output,
        links_are_proposal_tuple=validator.source_links is produced[0].source_links,
        links_preserve_elements=all(a is b for a, b in zip(validator.source_links, produced[0].source_links)),
        observation_is_proposal_mapping=validator.observation_map is produced[0].observation_map,
        configuration_is_argument=validator.configuration is configuration,
        run_is_get=record is manager.get("output"), repeated_get_same=manager.get("output") is manager.get("output"),
        results_same=first is second, result_artifact_is_record=first.artifact is record and second.artifact is record,
        unresolved_items_reuse_obligations=all(any(item is source_item for source_item in record.obligations) for item in first.unresolved),
        producer_dependencies_are_root=producer.dependencies is source.dependencies,
        checks_order=list(record.checks), provenance_order=list(record.provenance), output_order=list(record.payload),
        output_nested_order=list(record.payload["zeta"]), configuration_order=list(validator.configuration),
        dependency_order=list(record.dependencies), observation_order=list(validator.observation_map))
    ledger.note("record_fields", payload=ledger.ref(record.payload), dependencies=ledger.ref(record.dependencies),
        requirements=ledger.ref(record.requirements), provenance_configuration=ledger.ref(record.provenance["configuration"]),
        validator_configuration=ledger.ref(validator.configuration))
    return ledger.finish(authority, [source, record])


def nested_case(raises=False, manager_factory=pipeline.PassManager):
    ledger = Ledger("run:nested_raises" if raises else "run:nested_returns")
    original, manager, source, contract, configuration, authority, _, _ = fixture(manager_factory)
    entered, callbacks, inner_records = False, [], []
    marker = MarkerError("outer provider failed after nested acceptance")

    def produce(context):
        nonlocal entered
        ledger.context("producer", context)
        callbacks.append(context)
        if not entered:
            entered = True
            before = (context.input, context.configuration, context.dependencies, context.requirements, context.target)
            inner = manager.run(contract.id, "input", "inner", configuration=configuration)
            inner_records.append(inner)
            ledger.note("after_nested", outer_fields_unchanged=all(before[index] is object.__getattribute__(context, key)
                for index, key in enumerate(("input", "configuration", "dependencies", "requirements", "target"))),
                source_record_unchanged=source is manager.get("input"), inner_return_is_get=inner is manager.get("inner"))
            if raises:
                raise marker
        return proposal(contract)

    def validate(context):
        ledger.context("validator", context)
        callbacks.append(context)
        return decision(context)

    manager.register(contract, produce, {"a_check": validate, "z_check": validate})
    outer = ledger.attempt("outer_run", lambda: manager.run(contract.id, "input", "outer", configuration=configuration))
    ledger.note("nested_sharing", source_input_shared=all(item.input is source.payload for item in callbacks),
        supplied_target_shared=all(item.target is original.target for item in callbacks),
        requirements_shared=all(item.requirements is source.requirements for item in callbacks),
        producer_snapshots_distinct=callbacks[0].dependencies is not callbacks[1].dependencies,
        producer_configurations_distinct=callbacks[0].configuration is not callbacks[1].configuration,
        marker_same=outer is marker if raises else None,
        inner_record_preserved=inner_records[0] is manager.get("inner"))
    if raises:
        ledger.attempt("outer_get", lambda: manager.get("outer"))
    return ledger.finish(authority, [source, inner_records[0]] + ([] if raises else [outer]))


def stale_case(manager_factory=pipeline.PassManager, historical=lambda manager: manager._records):
    ledger = Ledger("run:validator_mutates_snapshot")
    _, manager, source, contract, configuration, authority, _, _ = fixture(manager_factory)
    contexts = []

    def produce(context):
        ledger.context("producer", context)
        return proposal(contract)

    def first(context):
        ledger.context("first_validator", context)
        contexts.append(context)
        manager.set_dependency("registry", fingerprint("changed"))
        return decision(context)

    def second(context):
        ledger.context("second_validator", context)
        contexts.append(context)
        return decision(context)

    manager.register(contract, produce, {"a_check": second, "z_check": first})
    ledger.attempt("run", lambda: manager.run(contract.id, "input", "output", configuration=configuration))
    record = historical(manager)["output"]
    ledger.note("after_stale", validators_same_context=contexts[0] is contexts[1],
        snapshot_value_unchanged=contexts[1].dependencies["registry"] == fingerprint("v1"),
        stored_accepted=record.accepted, stored_output_is_callback_output=record.payload is contexts[0].output,
        stored_dependencies_are_callback_snapshot=record.dependencies is contexts[0].dependencies)
    ledger.attempt("output_get", lambda: manager.get("output"))
    ledger.attempt("source_get", lambda: manager.get("input"))
    return ledger.finish(authority, [source, record])


def admission_case(manager_factory=pipeline.PassManager):
    ledger = Ledger("admission:sharing_and_order")
    original = ComponentAdmissionTests()
    original.setUp()
    manager = manager_factory(target=original.target, dependencies={
        "zeta": fingerprint("z"), "request": fingerprint(original.payload), "registry": fingerprint("registry")})
    policy = replace(original.policy, checks=(*original.policy.checks,
        pipeline.CheckSpec("additional", EvidenceKind.EXACT)))
    contexts = []

    def validate(context):
        ledger.context("validator", context)
        contexts.append(context)
        return original.verify(context)

    manager.register_component_input(policy, {"additional": validate, "selection": validate})
    record = manager.admit_component_input(policy.id, "selected", original.payload)
    ledger.note("sharing", validators_same_context=contexts[0] is contexts[1],
        target_is_supplied=manager.target is original.target and contexts[0].target is original.target,
        record_payload_is_context_input=record.payload is contexts[0].input,
        record_dependencies_is_context_dependencies=record.dependencies is contexts[0].dependencies,
        requirements_are_contract_tuple=record.requirements is policy.requirements and contexts[0].requirements is policy.requirements,
        obligations_are_contract_tuple=record.obligations is policy.obligations,
        admitted_return_is_get=record is manager.get("selected"), output_is_none=contexts[0].output is None,
        checks_order=list(record.checks), dependencies_order=list(record.dependencies))
    return ledger.finish({"target": original.target.to_dict(), "payload": plain(original.payload), "policy": plain(policy)}, [record])


def capture(*, manager_factory=pipeline.PassManager, historical=lambda manager: manager._records):
    cases = [sharing_case(manager_factory), nested_case(manager_factory=manager_factory),
        nested_case(True, manager_factory), stale_case(manager_factory, historical), admission_case(manager_factory)]
    paths = ["tools/capture_pipeline_identity_semantics.py", "src/biocompiler/compiler/pipeline.py",
        "src/biocompiler/compiler/passes.py", "src/biocompiler/ir/serialization.py",
        "src/biocompiler/artifacts/provenance.py", "tests/test_pipeline.py", "tests/test_component_admission.py"]
    result = {"schema_version": SCHEMA, "scope": "original_physical_identity_and_order_observations_not_native_acceptance",
        "source_files": {path: sha((ROOT / path).read_bytes()) for path in paths}, "cases": cases,
        "coverage": {"cases": len(cases), "events": sum(len(case["events"]) for case in cases),
                     "records": sum(len(case["records"]) for case in cases)}}
    result["inventory_fingerprint"] = sha(canonical(result))
    return result


def main():
    if OUTPUT.exists():
        raise SystemExit("Refusing to replace frozen original identity observations")
    result = capture()
    OUTPUT.write_bytes(canonical(result) + b"\n")
    print(json.dumps({"sha256": sha(OUTPUT.read_bytes()), "coverage": result["coverage"]}, sort_keys=True))


if __name__ == "__main__":
    main()

"""Capture independent Python contract literals; never manufacture acceptance.

The complete original lifecycle corpus is separate. These bounded literals cover
each native record codec and the original validated constructor rejections.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass, replace
from enum import Enum
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]
from biocompiler.artifacts.provenance import SourceLink
from biocompiler.compiler.passes import PassResult
from biocompiler.compiler.pipeline import (
    CheckDecision, CheckSpec, ComponentInputContract, PassContext,
)
from biocompiler.ir.serialization import fingerprint
from biocompiler.ir.stages import Stage
from biocompiler.verification.evidence import CheckOutcome, EvidenceKind, Obligation
from test_pipeline import PipelineTests, accepted
from test_component_admission import ComponentAdmissionTests


def plain(value):
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_dict"):
        return plain(value.to_dict())
    if is_dataclass(value):
        return {field.name: plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    if value is None or type(value) in (str, bool, int, float):
        return value
    raise TypeError(type(value).__qualname__)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode()


def capture():
    original = PipelineTests("test_scope_complete_keeps_unresolved_biological_obligation")
    original.setUp()
    original.test_scope_complete_keeps_unresolved_biological_obligation()
    manager = original.manager
    record = manager.get("mechanism")
    result = manager.result("mechanism", scope="synthetic")
    context = PassContext(manager.get("behavior").payload, record.payload, manager.target,
        record.provenance["configuration"], record.dependencies, record.requirements,
        (SourceLink("r", "n", "n", "generate"),), {"output": "n"})
    component = ComponentInputContract("component-input", "1", "components.v1",
        (CheckSpec("identity_check", EvidenceKind.EXACT, ("identity",)),),
        ("r",), (original.exact,), ("registry",), ("assembly",))
    values = {
        "Source_link": SourceLink("r", "n", "n", "lower"),
        "Producer_obligation": Obligation("response", "Exercise the required response.", EvidenceKind.MODEL_CONDITIONAL),
        "Scoped_obligation": original.exact,
        "Check_spec": original.first.checks[0],
        "Check_decision": accepted(None),
        "Pass_contract": original.second,
        "Pass_context": context,
        "Component_input_contract": component,
        "Completion_profile": manager._profiles["synthetic"],
        "Stage_record": record,
        "Pipeline_result": result,
        "Pass_result": original.producer(original.second)(context),
    }
    literals = []
    for kind, value in values.items():
        document = plain(value)
        literals.append({"id": kind, "kind": kind, "document": document,
                         "fingerprint": fingerprint(document), "canonical_bytes": len(canonical(document))})
    unicode = CheckDecision(CheckOutcome.UNKNOWN, "é😀 conditional\nclaim", {
        "é😀": [1, 1.0, -0.0, 10**80, "\t\u0000"], "unresolved": True})
    document = plain(unicode)
    literals.append({"id": "unicode-numeric-kinds", "kind": "Check_decision",
        "document": document, "fingerprint": fingerprint(document), "canonical_bytes": len(canonical(document))})

    recipes = [
        ("Scoped_obligation", original.exact, {"id": " "}),
        ("Scoped_obligation", original.exact, {"description": ""}),
        ("Check_spec", original.first.checks[0], {"evidence_kind": EvidenceKind.UNRESOLVED}),
        ("Check_spec", original.first.checks[0], {"discharges": ("identity", "identity")}),
        ("Check_decision", accepted(None), {"detail": ""}),
        ("Check_decision", accepted(None), {"evidence": []}),
        ("Pass_contract", original.second, {"output_stage": Stage.CONSTRUCT}),
        ("Pass_contract", original.second, {"checks": ()}),
        ("Pass_contract", original.second, {"checks": original.second.checks * 2}),
        ("Pass_contract", original.second, {"targets": ()}),
        ("Pass_contract", original.second, {"targets": original.second.targets * 2}),
        ("Pass_contract", original.second, {"supported_operations": ("constant", "constant")}),
        ("Pass_contract", original.second, {"requires_source_map": 1}),
        ("Component_input_contract", component, {"checks": ()}),
        ("Component_input_contract", component, {"requirements": ("r", "r")}),
        ("Component_input_contract", component, {"obligations": ()}),
        ("Component_input_contract", component, {"checks": (CheckSpec("wrong", EvidenceKind.EMPIRICAL, ("identity",)),)}),
        ("Completion_profile", manager._profiles["synthetic"], {"obligations": ()}),
        ("Completion_profile", manager._profiles["synthetic"], {"schema": " "}),
    ]
    rejections = []
    for ordinal, (kind, value, changes) in enumerate(recipes):
        document = {**plain(value), **plain(changes)}
        try:
            replace(value, **changes)
        except Exception as error:
            rejections.append({"id": f"{kind}-{ordinal}", "kind": kind, "document": document,
                "error": {"module": type(error).__module__, "type": type(error).__name__, "message": str(error)}})
        else:
            raise AssertionError("Original invalid constructor was accepted")
    admission = ComponentAdmissionTests("test_structural_root_records_real_checks_and_discharge")
    admission.setUp()
    admission.test_structural_root_records_real_checks_and_discharge()
    admitted = admission.manager.get("selected")
    source_files = ["src/biocompiler/compiler/pipeline.py", "src/biocompiler/compiler/passes.py",
        "src/biocompiler/artifacts/provenance.py", "src/biocompiler/ir/serialization.py",
        "src/biocompiler/verification/evidence.py", "tests/test_pipeline.py", "tests/test_component_admission.py",
        "tools/capture_pipeline_contract_literals.py"]
    result = {"schema_version": "biocompiler.pipeline_contract_literals.v1",
        "claim_scope": "original_python_contract_literals_no_native_or_live_manager_acceptance",
        "original_assertion": "tests/test_pipeline.py::PipelineTests.test_scope_complete_keeps_unresolved_biological_obligation",
        "assertion_status": "passed", "sources": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_files},
        "literals": literals, "rejections": rejections,
        "manager_baseline": {"target": plain(manager.target), "input": original.input,
            "first": plain(original.first), "second": plain(original.second),
            "initial_obligations": plain((original.exact, original.biological)),
            "initial_dependencies": {key: value for key, value in record.dependencies.items() if key != "target"},
            "completion": plain(manager._profiles["synthetic"]),
            "records": {key: plain(value) for key, value in manager._records.items()}, "result": plain(result)},
        "admission_baseline": {"target": plain(admission.target), "payload": plain(admission.payload),
            "contract": plain(admission.policy), "record": plain(admitted),
            "dependencies": {key: value for key, value in admitted.dependencies.items() if key != "target"},
            "original_assertion": "tests/test_component_admission.py::ComponentAdmissionTests.test_structural_root_records_real_checks_and_discharge",
            "assertion_status": "passed"}}
    result["inventory_fingerprint"] = fingerprint(result)
    return result


if __name__ == "__main__":
    result = capture()
    output = ROOT / "tests/conformance/pipeline-contract-literals-v1.json"
    output.write_bytes(canonical(result) + b"\n")
    print(f"Captured {len(result['literals'])} full records, {len(result['rejections'])} original constructor rejections")

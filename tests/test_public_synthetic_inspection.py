"""Public rich helpers keep original values/errors and native-only decisions."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler.core_client import CoreClient, CoreProtocolError, CoreRejected
from biocompiler.errors import SerializationError, UnsupportedBehaviorError
from biocompiler.synthetic_producer_backend import (
    NativeCheckResult, NativeComponentRegistry, NativeComponentSelectionResult, NativeDependencies,
    NativeFreshnessReport, NativeMechanismProgram, NativeProducerDocument,
    SyntheticProducerCoreError, serializing_legacy_input,
)
import test_core_synthetic_inspection as client_fixtures
from test_core_synthetic_inspection import (
    capabilities, cases, encoded, envelope, receipt, representative,
)
from test_core_synthetic_producer import fixture, receipt as producer_receipt


def invoke(case,core):
    payload,api=case["payload"],case["api"]
    if api.startswith("ComponentRegistry."):
        registry=NativeComponentRegistry.from_dict(payload["registry"],core=core)
        if api.endswith(".lock"):return registry.lock(payload["instances"])
        if api.endswith(".resolve"):return registry.resolve(payload["lock"])
        if api.endswith(".select"):return registry.select(payload["request"])
        return registry.verify_selection(payload["request"],payload["selection"])
    if api.startswith("CheckResult."):
        record=NativeCheckResult.from_dict(payload["record"],core=core)
        if api.endswith(".exercised_requirement_ids"):return record.exercised_requirement_ids
        return getattr(record,api.split(".")[1])(payload["current"])
    if api=="DependencySnapshot.changed":return NativeDependencies.from_dict(payload["previous"],core=core).changed(payload["current"])
    if api=="SelectionResult.outcome":return NativeComponentSelectionResult.from_dict(payload["selection"],core=core).outcome
    if api=="MechanismProgram.topological_nodes":return NativeMechanismProgram.from_dict(payload["mechanism"],core=core).topological_nodes()
    raise AssertionError(api)


def plain(value):
    if isinstance(value,NativeProducerDocument):return value.to_dict()
    if type(value) in (tuple,list):return [plain(item) for item in value]
    if type(value) is dict:return {key:plain(item) for key,item in value.items()}
    return value


class PublicSyntheticInspectionTests(unittest.TestCase):
    exchange=client_fixtures.SyntheticInspectionClientTests.exchange

    def setUp(self):
        self.core=CoreClient(Path(sys.executable));self.calls=[]

    def test_all_original_public_helper_shapes_properties_and_exact_errors(self):
        selected={}
        for case in cases():
            selected.setdefault((case["api"],case["error"] is not None),case)
        for case in selected.values():
            with self.subTest(api=case["api"],error=case["error"]),self.exchange(case):
                if case["error"]:
                    expected=case["expected_public"]["error"]
                    error_type = TypeError if expected["type"] == "TypeError" else SerializationError
                    with self.assertRaises(error_type) as caught:invoke(case,self.core)
                    self.assertEqual({"module":type(caught.exception).__module__,"type":type(caught.exception).__name__,
                                      "message":str(caught.exception)},expected)
                    self.assertIsInstance(caught.exception.core_error,CoreRejected)
                    self.assertIs(caught.exception.__cause__,caught.exception.core_error)
                    continue
                value=invoke(case,self.core)
                public={"value":plain(value),"properties":{key:getattr(value,key) for key in case["expected_public"]["properties"]}}
                self.assertEqual(encoded(public),encoded(case["expected_public"]))
                if isinstance(value,NativeProducerDocument):
                    self.assertIsNone(value.native_result)
                    self.assertIsNotNone(value.native_inspection)
                    self.assertIs(value._core,self.core)
                    with self.assertRaises((FrozenInstanceError,TypeError)):value._core=None

    def test_complete_independently_captured_supplemental_helpers_and_errors(self):
        import hashlib
        path=Path(__file__).resolve().parents[1]/"tests/conformance/synthetic-inspection-supplemental-v1.json"
        raw=path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),"c9b6179b9c36ee56cd11706f4bf5593f23524de054ff9cb245610245170b818d")
        fixtures=json.loads(raw)["cases"]
        self.assertEqual(len(fixtures),28)
        for case in fixtures:
            with self.subTest(case=case["id"]),self.exchange(case):
                if case["error"]:
                    with self.assertRaises((SerializationError,TypeError)) as caught:invoke(case,self.core)
                    public={"error":{"module":type(caught.exception).__module__,"type":type(caught.exception).__name__,
                                     "message":str(caught.exception)}}
                else:
                    value=invoke(case,self.core)
                    public={"value":plain(value),"properties":{key:getattr(value,key) for key in case["expected_public"]["properties"]}}
                self.assertEqual(encoded(public),encoded(case["expected_public"]))

    def test_stale_freshness_report_is_not_used_as_boolean(self):
        case=next(case for case in cases() if case["api"]=="CheckResult.freshness" and not case["expected_value"]["freshness"]["fresh"])
        check=NativeCheckResult.from_dict(case["payload"]["record"],core=self.core)
        with self.exchange(case):
            report=check.freshness(case["payload"]["current"])
            self.assertIs(type(report),NativeFreshnessReport)
            self.assertFalse(report.fresh)
            self.assertEqual(report.status,"stale")
            self.assertTrue(bool(report))
            self.assertFalse(check.is_fresh(case["payload"]["current"]))
        self.assertEqual(report.to_dict(),case["expected_public"]["value"])
        self.assertEqual(report.changed_dependencies,tuple(case["expected_value"]["freshness"]["changed_dependencies"]))
        self.assertEqual(report.native_inspection.value,case["expected_value"])

    def test_historical_views_require_context_and_query_does_not_grant_producer_receipt(self):
        for operation,cls,key,method,args in (
            ("inspect-synthetic-mechanism",NativeMechanismProgram,"mechanism","topological_nodes",()),
            ("resolve-synthetic-registry",NativeComponentRegistry,"registry","resolve",("lock",)),
            ("compare-synthetic-dependencies",NativeDependencies,"previous","changed",("current",))):
            case=representative(operation);view=cls.from_dict(case["payload"][key])
            self.assertIsNone(view.native_result);self.assertIsNone(view.native_inspection)
            with patch("biocompiler.core_client._exchange") as child,self.assertRaisesRegex(UnsupportedBehaviorError,"explicit core context"):
                getattr(view,method)(*(case["payload"][arg] for arg in args))
            child.assert_not_called()
            bound=cls.from_json(view.to_json(),core=self.core)
            with self.exchange(case):result=getattr(bound,method)(*(case["payload"][arg] for arg in args))
            self.assertIsNone(bound.native_result);self.assertIsNone(bound.native_inspection)
            if isinstance(result,NativeProducerDocument):self.assertIsNotNone(result.native_inspection)

    def test_core_handle_propagates_through_actual_producer_views(self):
        from biocompiler.synthesis.synthetic import generate_synthetic
        from biocompiler.synthesis.selection import select_synthetic
        from biocompiler.synthesis.components import adapt_synthetic_components
        operations=("generate-synthetic","select-synthetic","adapt-synthetic-components")
        def exchange(_executable,raw,_timeout,_cancelled):
            request=json.loads(raw);operation=request["operation"]
            if operation=="capabilities":value=capabilities()
            else:value=producer_receipt(operation,request["payload"],fixture(operation)[1])
            return encoded(envelope(request,value)),0
        with patch("biocompiler.core_client._exchange",side_effect=exchange):
            for operation in operations:
                payload,_=fixture(operation)
                if operation==operations[0]:value=generate_synthetic(payload["request"],config=payload["config"],core=self.core)
                elif operation==operations[1]:value=select_synthetic(payload["request"],payload["history"],until=payload["until"],config=payload["config"],core=self.core)
                else:value=adapt_synthetic_components(payload["request"],payload["candidate"],payload["history"],until=payload["until"],core=self.core)
                pending=[value]
                while pending:
                    node=pending.pop()
                    if isinstance(node,NativeProducerDocument):
                        self.assertIs(node._core,self.core)
                        self.assertIs(node.native_result,value.native_result)
                        pending.extend(node._data.values())
                    elif type(node) is tuple:pending.extend(node)
                historical=type(value).from_dict(value.to_dict(),core=self.core)
                self.assertIsNone(historical.native_result)
                self.assertIs(historical._core,self.core)

    def test_native_helpers_execute_no_python_semantic_constructor_or_ranking(self):
        permitted={"biocompiler.core_client","biocompiler.core_synthetic_producer","biocompiler.core_synthetic_inspection","biocompiler.synthetic_producer_backend"}
        def guard(frame,event,_value):
            if event=="call":
                module=frame.f_globals.get("__name__","")
                if module.startswith("biocompiler") and module not in permitted:
                    raise AssertionError("Python authority executed: "+module+"."+frame.f_code.co_qualname)
        for operation in {case["operation"] for case in cases()}:
            case=representative(operation)
            with self.exchange(case):
                previous=sys.getprofile()
                try:
                    sys.setprofile(guard);value=invoke(case,self.core)
                    if case["api"]=="ComponentRegistry.select":self.assertEqual(value.outcome,case["expected_value"]["outcome"])
                finally:sys.setprofile(previous)

    def test_typed_authored_dependency_serialization_is_marked_and_frozen(self):
        from biocompiler.verification.evidence import DependencySnapshot
        case=representative("compare-synthetic-dependencies")
        current=DependencySnapshot(case["payload"]["current"])
        previous=NativeDependencies.from_dict(case["payload"]["previous"],core=self.core)
        original=DependencySnapshot.to_dict;phases=[]
        def to_dict(value):phases.append(serializing_legacy_input());return original(value)
        with self.exchange(case,on_negotiate=lambda:self.assertFalse(serializing_legacy_input())),patch.object(DependencySnapshot,"to_dict",to_dict):
            result=previous.changed(current)
        self.assertEqual(phases,[True]);self.assertEqual(result,tuple(case["expected_value"]["changed_dependencies"]))

    def test_type_rejection_from_native_preserves_exact_error_and_verify_role_never_runs(self):
        original=representative("inspect-synthetic-check-result");case=deepcopy(original)
        case["payload"].update(query="freshness",current=None)
        case["error"]={"code":"synthetic_inspection_type","path":"payload.current","message":"Freshness comparison requires a DependencySnapshot."}
        view=NativeCheckResult.from_dict(case["payload"]["record"],core=self.core)
        with self.exchange(case),self.assertRaises(TypeError) as caught:view.freshness(None)
        self.assertEqual(str(caught.exception),case["error"]["message"])
        self.assertIsInstance(caught.exception.__cause__,CoreRejected)
        case=representative("inspect-synthetic-mechanism")
        view=NativeMechanismProgram.from_dict(case["payload"]["mechanism"],core=CoreClient(Path(sys.executable),role="verify"))
        with patch("biocompiler.core_client._exchange") as child,self.assertRaises(SyntheticProducerCoreError) as caught:view.topological_nodes()
        child.assert_not_called();self.assertIsInstance(caught.exception.core_error,CoreProtocolError)


if __name__=="__main__":unittest.main()

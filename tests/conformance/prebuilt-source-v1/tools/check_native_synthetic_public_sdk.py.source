"""Installed public producer routes with complete original records and wire evidence.

All 1226 public original occurrences run through the selected native SDK. Nine
additional calls cover mapping, typed authoring and historical native views.
Private proposals/injected producers remain explicitly native-library evidence;
rich helper parity, public CLI and pipeline/export cutover remain separate gates.
"""
from __future__ import annotations
import argparse
import builtins
from contextlib import contextmanager
from copy import deepcopy
from functools import lru_cache
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import re
import sys
import time
from uuid import UUID
if __package__:
    from . import check_native_synthetic_producer as base
    from . import check_native_workflow_public_sdk as serializers
    from . import check_workflow_reproducibility as r
else:
    import check_native_synthetic_producer as base
    import check_native_workflow_public_sdk as serializers
    import check_workflow_reproducibility as r
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "biocompiler.native_synthetic_public_sdk_conformance.v1"
SCOPE = "explicit_public_core_routes_complete_original_records_rich_helpers_cli_pipeline_export_separate"
RECEIPT_FILE, ARTIFACT_DIRECTORY = "synthetic-public-sdk.json", "synthetic-public-sdk-artifacts"
CORPUS_PIN, CAPTURE_PIN = base.CORPUS_PIN, base.CAPTURE_PIN
ROLES, PYTHONS, PLATFORMS = r.ROLES, r.PYTHONS, r.PLATFORMS
require, canonical, digest, decode = r.require, r.canonical, r.digest, r.decode
read, Artifacts, source_pins, verify_binaries = r.read, r.Artifacts, r.source_pins, r.verify_binaries
artifact, declaration, expected_semantic = base.artifact, base.declaration, base.expected_semantic
sha = base.sha
ROUTES = {"generate-synthetic": ("biocompiler.synthesis.synthetic", "generate_synthetic"),
          "select-synthetic": ("biocompiler.synthesis.selection", "select_synthetic"),
          "adapt-synthetic-components": ("biocompiler.synthesis.components", "adapt_synthetic_components")}
REQUIRED_TRANSPORT_MODULES = base.TRANSPORT_MODULES | {"biocompiler.synthetic_producer_backend"}
TRANSPORT_MODULES = REQUIRED_TRANSPORT_MODULES | {"biocompiler.core_synthetic_inspection"}
INPUT_MODULES = {"biocompiler.compiler.request", "biocompiler.ir.behavior", "biocompiler.ir.components",
    "biocompiler.ir.intent", "biocompiler.ir.mechanism", "biocompiler.ir.serialization",
    "biocompiler.semantics.context", "biocompiler.semantics.contracts", "biocompiler.semantics.evaluator",
    "biocompiler.semantics.realization", "biocompiler.semantics.types", "biocompiler.synthesis.synthetic",
    "biocompiler.verification.realization"}
SOURCE_MODULES = TRANSPORT_MODULES | INPUT_MODULES | {module for module,_ in ROUTES.values()} | {"biocompiler.errors"}
SOURCES = ("tools/check_native_synthetic_public_sdk.py", "tests/test_native_synthetic_public_sdk_campaign.py",
    "tools/check_native_synthetic_producer.py", "tests/test_native_synthetic_producer_campaign.py",
    "tools/check_native_workflow_public_sdk.py",
    "tools/check_native_workflow.py", "tools/check_native_workflow_presentation.py",
    "tools/check_workflow_reproducibility.py", "tools/check_realization_binaries.py", "protocol/synthetic-producer-v1.json")
# Hosted acceptance for these helpers is tracked by the separate inspection campaign.
# This producer campaign itself establishes no helper acceptance.
PENDING_HELPERS = ["authoritative_mechanism_topological_order", "general_registry_lock_selection_verification",
                   "derived_coverage_summaries", "freshness_decisions"]


def project_cases(original):
    cases = [{**deepcopy(case), "input_kind": "bytes", "origin_id": case["id"]} for case in original]
    for operation in ROUTES:
        positive = [case for case in original if case["operation"] == operation and case["expected"] is not None]
        sample = next((case for case in positive if decode(case["authority"]).get("config") is not None), positive[0])
        for kind in ("mapping", "typed", "native"):
            cases.append({**deepcopy(sample), "id": kind + "/" + sample["id"], "input_kind": kind, "origin_id": sample["id"]})
    require(len(cases) == len(original)+9 and len({case["id"] for case in cases}) == len(cases), "Public producer input-form census differs")
    return cases


class Corpus(base.Corpus):
    def __init__(self):
        super().__init__()
        self.cases = project_cases(self.cases)
        require(len(self.cases) == 1235, "Original public SDK coverage was narrowed")
        self.verify_cases = [{**case, "input_kind": "verify_transport", "origin_id": case["id"]} for case in self.verify_cases]


def input_phase():
    module = sys.modules.get("biocompiler.synthetic_producer_backend")
    return bool(module is not None and module._INPUT_SERIALIZATION.get())


@lru_cache(maxsize=8192)
def allowed_call(module, name, phase, owner):
    if module in TRANSPORT_MODULES:
        return True
    if (module,name) in ROUTES.values() and phase == "output":
        return True
    if module == "biocompiler.errors":
        return phase == "output" and name in ("UnsupportedBehaviorError.__init__", "LoweringError.__init__")
    return phase == "input" and module in INPUT_MODULES and serializers.allowed_call(module,name,"input",owner)


@contextmanager
def routed_execution():
    previous, imported = sys.getprofile(), builtins.__import__
    seen, exchanges = set(), []
    def imports(name,*args,**kwargs):
        if name.startswith("biocompiler"):
            require(name in SOURCE_MODULES, "Unreviewed public producer import: " + name)
        return imported(name,*args,**kwargs)
    def calls(frame,event,result):
        module = frame.f_globals.get("__name__", "")
        if event == "call" and module.startswith("biocompiler"):
            entry = (module,frame.f_code.co_qualname,"input" if input_phase() else "output",
                     "" if module in TRANSPORT_MODULES else serializers.frame_owner(frame))
            require(allowed_call(*entry), "Python producer semantic fallback is forbidden: " + repr(entry))
            seen.add(entry)
        if event == "return" and module == "biocompiler.core_client" and frame.f_code.co_name == "_exchange" and result is not None:
            raw,exit_code=result
            exchanges.append(dict(request=frame.f_locals["request"],response=raw,exit_code=exit_code,
                                  executable=str(frame.f_locals["executable"])))
    builtins.__import__,sys_profile = imports,calls
    sys.setprofile(sys_profile)
    try:
        yield seen,exchanges
        require(sys.getprofile() is calls and builtins.__import__ is imports, "Public producer guard was disabled")
    finally:
        sys.setprofile(previous);builtins.__import__=imported


def check_guard(entries,case,role):
    require(type(entries) is list and entries==sorted(entries) and len({tuple(item) for item in entries})==len(entries), "Invalid public producer guard census")
    for item in entries:
        require(type(item) is list and len(item)==4 and all(type(v) is str for v in item) and
                item[2] in ("input","output") and allowed_call(*item), "Forbidden public producer guard frame")
        require(item[2]!="input" or case["input_kind"]=="typed", "Legacy serializer outside explicit typed-input phase")
    modules = {item[0] for item in entries}
    if role == "verify":
        require(modules=={"biocompiler.core_client"}, "Verifier transport guard differs")
    else:
        require(REQUIRED_TRANSPORT_MODULES <= modules and any(item[:3]==[*ROUTES[case["operation"]],"output"] for item in entries),
                "Missing actual public producer route or native transport")
        if case["input_kind"]=="typed":
            require(any(item[2]=="input" for item in entries), "Typed input bypassed audited serializer phase")


def prepare(case):
    """Author typed input before the guarded native phase; never construct output."""
    payload=decode(case["authority"])
    values={key:value for key,value in payload.items() if key not in ("profile","limits")}
    kind=case["input_kind"]
    if kind=="bytes":
        return {key:canonical(value) if key in ("request","config","candidate","history") and value is not None else value
                for key,value in values.items()}
    if kind=="mapping":return values
    if kind=="native":
        from biocompiler.synthetic_producer_backend import NativeProducerDocument
        return {key:[NativeProducerDocument.from_dict(item) for item in value] if key=="history" else
                NativeProducerDocument.from_dict(value) if key in ("request","config","candidate") and value is not None else value
                for key,value in values.items()}
    require(kind=="typed", "Unknown public producer input form")
    from biocompiler.compiler.request import RealizationRequest
    from biocompiler.synthesis.synthetic import SyntheticCandidate,SyntheticGeneratorConfig
    from biocompiler.semantics.evaluator import InputFrame,SignalSample
    values["request"]=RealizationRequest.from_dict(values["request"])
    if values.get("config") is not None:values["config"]=SyntheticGeneratorConfig.from_dict(values["config"])
    if "candidate" in values:values["candidate"]=SyntheticCandidate.from_dict(values["candidate"])
    if "history" in values:
        values["history"]=[InputFrame(frame["time"],{k:SignalSample(**v) for k,v in frame["signals"].items()},
            {k:{s:SignalSample(**v) for s,v in values.items()} for k,values in frame["contacts"].items()}) for frame in values["history"]]
    return values


def error_view(error):
    from biocompiler.synthetic_producer_backend import SyntheticProducerCoreError
    from biocompiler.errors import UnsupportedBehaviorError
    if isinstance(error,UnsupportedBehaviorError):
        return {"module":type(error).__module__,"type":type(error).__name__,"message":str(error),
                "node_id":error.node_id,"source":None if error.source is None else error.source.to_dict()}
    require(isinstance(error,SyntheticProducerCoreError), "Unexpected public SDK error class")
    return {"module":type(error).__module__,"type":type(error).__name__,"message":str(error),"operation":error.operation,
            "diagnostics":[{"code":d.code,"message":d.message,"path":d.path} for d in error.diagnostics]}


def expected_public(case,role="core"):
    if role=="verify":return None
    if case["generation_error"] is not None:
        error=case["generation_error"]
        return {"error":{"module":"biocompiler.errors","type":"UnsupportedBehaviorError","message":error["formatted"],
                         "node_id":error["node_id"],"source":error["source"]}}
    if case["error"] is not None:
        error=case["error"]
        return {"error":{"module":"biocompiler.synthetic_producer_backend","type":"SyntheticProducerCoreError",
            "message":case["operation"]+" failed: "+error["code"]+": "+error["message"],"operation":case["operation"],"diagnostics":[error]}}
    raw=decode(case["expected"])
    properties=case["evidence"]["properties"]
    return {"record":raw,"fingerprint":sha(case["expected"]),"json":json.dumps(raw,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False),
            "properties":properties}


def public_view(value,case):
    properties=case["evidence"]["properties"]
    if properties is not None:
        properties={key: (None if value.candidate is None else value.candidate.to_dict()) if key=="candidate" else getattr(value,key)
                    for key in properties}
    return {"record":value.to_dict(),"fingerprint":value.fingerprint,"json":value.to_json(),"properties":properties}


def campaign(clients,corpus,receipt):
    from biocompiler.core_client import CoreRejected
    from biocompiler.errors import UnsupportedBehaviorError
    from biocompiler.synthetic_producer_backend import SyntheticProducerCoreError
    clients={client.role:client for client in clients}
    functions={operation:getattr(importlib.import_module(module),name) for operation,(module,name) in ROUTES.items()}
    receipt["library_coverage"]=artifact(receipt,canonical(corpus.library))
    receipt["pending_helpers"]=PENDING_HELPERS
    for (role,_),case in corpus.expected().items():
        values=prepare(case) if role=="core" else None
        with routed_execution() as (seen,exchanges):
            if role=="core":
                try:value=functions[case["operation"]](**values,core=clients[role]);public=public_view(value,case)
                except (UnsupportedBehaviorError,SyntheticProducerCoreError) as error:public={"error":error_view(error)}
                require(canonical(public)==canonical(expected_public(case)), "Complete public SDK record/properties/error differs")
            else:
                public=None
                try:clients[role].call(case["operation"],decode(case["authority"]))
                except CoreRejected:pass
                else:raise AssertionError("Verifier dispatched a producer")
        check_guard([list(item) for item in sorted(seen)],case,role)
        row={"id":case["id"],"origin_id":case["origin_id"],"input_kind":case["input_kind"],"operation":case["operation"],"role":role,
             "authority":artifact(receipt,case["authority"]),"expected":None if case["expected"] is None else artifact(receipt,case["expected"]),
             "evidence":artifact(receipt,canonical(case["evidence"])),"public":None if public is None else artifact(receipt,canonical(public)),
             "guard_frames":[list(item) for item in sorted(seen)],"exchanges":[]}
        for exchange in exchanges:
            row["exchanges"].append({**exchange,"request":artifact(receipt,exchange["request"]),"response":artifact(receipt,exchange["response"])})
        receipt["checks"].append(row)
    with routed_execution() as (seen,exchanges):clients["verify"].capabilities()
    require(len(exchanges)==1 and {entry[0] for entry in seen}=={"biocompiler.core_client"},"Verifier capability witness missing")
    receipt["verify_capabilities"]={**exchanges[0],"request":artifact(receipt,exchanges[0]["request"]),"response":artifact(receipt,exchanges[0]["response"])}


def uuid4_identity(identity,seen):
    try:value=UUID(identity)
    except (ValueError,TypeError,AttributeError) as error:raise AssertionError("Invalid producer request identity") from error
    require(value.version==4 and str(value)==identity and identity not in seen,"Reused or non-v4 producer request identity")
    seen.add(identity)


def validate_checks(receipt,corpus,artifacts):
    expected=corpus.expected()
    require(type(receipt.get("completed_checks")) is int and receipt["completed_checks"]==len(expected) and
            len(receipt.get("checks",[]))==len(expected),"Incomplete public producer occurrences")
    require(receipt.get("pending_helpers")==PENDING_HELPERS,"Pending public helper obligations changed")
    require(artifacts.raw(receipt["library_coverage"])==canonical(corpus.library),"Private/injection coverage changed")
    identities,seen,projected=set(),set(),[]
    for row in receipt["checks"]:
        require(set(row)=={"id","origin_id","input_kind","operation","role","authority","expected","evidence","public","guard_frames","exchanges"},"Unexpected public producer observation fields")
        key=row["role"],row["id"]
        require(key in expected and key not in seen,"Missing duplicate or substituted public occurrence");seen.add(key)
        case,role=expected[key],row["role"]
        require(all(row[k]==case[k] for k in ("origin_id","input_kind","operation")) and artifacts.raw(row["authority"])==case["authority"] and
                (row["expected"] is None if case["expected"] is None else artifacts.raw(row["expected"])==case["expected"]) and
                artifacts.raw(row["evidence"])==canonical(case["evidence"]),"Original public authority/result/evidence changed")
        require(row["public"] is None if role=="verify" else artifacts.raw(row["public"])==canonical(expected_public(case)),"Complete public presentation/error changed")
        check_guard(row["guard_frames"],case,role)
        exchanges=row["exchanges"];require(type(exchanges) is list and len(exchanges)==(2 if role=="core" else 1),"Incomplete public process trace")
        normalized=[]
        for ordinal,exchange in enumerate(exchanges):
            require(set(exchange)=={"request","response","exit_code","executable"} and type(exchange["exit_code"]) is int,"Incomplete public native wire evidence")
            path=Path(exchange["executable"])
            require(path.is_absolute() and path.name=="biocompiler-"+role and str(path)==receipt["executables"][role],"Wrong selected native executable")
            raw_request,raw_response=artifacts.raw(exchange["request"]),artifacts.raw(exchange["response"])
            request,response=decode(raw_request),decode(raw_response)
            if role=="core" and ordinal==0:
                identity,response_projection=base.validate_capability(raw_response,role,corpus,identities)
                require(request=={"protocol":"biocompiler.core.v1","request_id":identity,"operation":"capabilities","payload":{}} and exchange["exit_code"]==0,"Capability request binding differs")
            else:
                identity=request.get("request_id");uuid4_identity(identity,identities)
                require(raw_request==canonical({"protocol":"biocompiler.core.v1","request_id":identity,"operation":case["operation"],"payload":decode(case["authority"])}),"Complete public producer request differs")
                if role=="verify":wanted=base.envelope(role,identity,case["operation"],"unsupported",None,[base.UNSUPPORTED]);exit_code=3
                elif case["error"] is not None:wanted=base.envelope(role,identity,case["operation"],"error",None,[case["error"]]);exit_code=2
                else:wanted=base.envelope(role,identity,case["operation"],"ok",expected_semantic(corpus,case),[]);exit_code=0
                require(canonical(response)==canonical(wanted) and exchange["exit_code"]==exit_code,"Complete public producer native receipt/result/error differs")
                response_projection={**response,"request_id":"<capability-uuid4>"}
            require(raw_request==canonical(request) and raw_response==canonical(response)+b"\n","Noncanonical native public wire bytes")
            normalized.append({"request":{**request,"request_id":"<capability-uuid4>"},"response":response_projection,"exit_code":exchange["exit_code"]})
        # Full runtime-specific guard frames remain in the immutable receipt.
        # They are independently validated before this reviewed guard/UUID projection.
        projected.append({**{k:v for k,v in row.items() if k not in ("guard_frames","exchanges")},"exchanges":normalized})
    require(seen==set(expected),"Original public producer occurrence omitted")
    exchange=receipt["verify_capabilities"]
    require(set(exchange)=={"request","response","exit_code","executable"} and type(exchange["exit_code"]) is int and exchange["exit_code"]==0 and
            exchange["executable"]==receipt["executables"]["verify"],"Missing verifier capability trace")
    raw=artifacts.raw(exchange["response"]);identity,response=base.validate_capability(raw,"verify",corpus,identities)
    require(artifacts.raw(exchange["request"])==canonical({"protocol":"biocompiler.core.v1","request_id":identity,"operation":"capabilities","payload":{}}) and
            raw==canonical(decode(raw))+b"\n","Verifier capability request/response differs")
    require(artifacts.used==set(artifacts.declared),"Unreferenced public producer evidence")
    return {"checks":projected,"verify_capabilities":response,"library_coverage":receipt["library_coverage"],"pending_helpers":PENDING_HELPERS}


def compare(root, native_root, *, revision, source_revision, run_id):
    require(type(revision) is str and re.fullmatch(r"[0-9a-f]{40}", revision) and
            type(source_revision) is str and re.fullmatch(r"[0-9a-f]{40}", source_revision) and
            type(run_id) is str and bool(run_id), "Invalid current producer validation authority")
    root, native_root = Path(root), Path(native_root)
    require(root.is_dir() and not root.is_symlink() and native_root.is_dir() and not native_root.is_symlink(), "Unsafe evidence roots")
    names = {"realization-" + target + "-py" + python for target in PLATFORMS for python in PYTHONS}
    require({path.name for path in root.iterdir() if path.name.startswith("realization-")} == names,
            "Missing or extra producer matrix slot")
    corpus, receipts, natives, reference = Corpus(), {}, {}, None
    transport_sources = source_pins("src/" + name.replace(".", "/") + ".py" for name in sorted(SOURCE_MODULES))
    campaign_sources = source_pins(SOURCES)
    for target, (system, machine) in PLATFORMS.items():
        native_directory = native_root / target
        require(native_directory.is_dir() and not native_directory.is_symlink(), "Unsafe native platform directory")
        native = verify_binaries(native_directory, revision, target)
        natives[target] = native
        for python in PYTHONS:
            name = "realization-" + target + "-py" + python
            directory = root / name
            require(directory.is_dir() and not directory.is_symlink(), "Unsafe producer runtime directory")
            inputs, inputs_pin = read(directory / "native-inputs.json", r.CONTROL_BYTES)
            require(canonical({key: inputs.get(key) for key in native}) == canonical(native) and
                    inputs.get("run_id") == run_id and inputs.get("source_revision") == source_revision and
                    type(inputs.get("python_version")) is str and inputs["python_version"].startswith(python + "."),
                    "Stale or mixed same-run producer native inputs")
            receipt, receipt_pin = read(directory / RECEIPT_FILE)
            fields = {"schema_version": SCHEMA, "status": "success", "scope": SCOPE,
                "revision": revision, "source_revision": source_revision, "run_id": run_id,
                "python_version": inputs["python_version"], "system": system, "machine": machine,
                "native_platform": target, "corpus_pin": CORPUS_PIN, "capture_pin": CAPTURE_PIN,
                "profile_pin": digest(corpus.profiles), "artifact_directory": ARTIFACT_DIRECTORY,
                "native_inputs": native, "transport_sources": transport_sources, "campaign_sources": campaign_sources}
            for key, value in fields.items():
                require(canonical(receipt.get(key)) == canonical(value), "Stale/mixed producer receipt: " + key)
            require(type(receipt.get("package_path")) is str and Path(receipt["package_path"]).is_absolute(),
                    "Missing installed producer package provenance")
            executables = receipt.get("executables")
            require(type(executables) is dict and set(executables) == set(ROLES) and all(
                type(executables[role]) is str and Path(executables[role]).is_absolute() and
                Path(executables[role]).name == "biocompiler-" + role for role in ROLES) and
                Path(executables["core"]).parent == Path(executables["verify"]).parent,
                "Missing exact selected executable paths")
            artifacts = Artifacts(directory / ARTIFACT_DIRECTORY, receipt.get("artifacts"))
            complete = canonical(validate_checks(receipt, corpus, artifacts))
            if reference is None:
                reference = complete
            else:
                require(complete == reference, "Complete four-runtime producer evidence differs after validated UUID/guard projection")
            receipts[name] = {"native_inputs": inputs_pin, "producer": receipt_pin,
                              "complete_artifacts": artifacts.verified}
    require(len(receipts) == 4 and reference is not None, "Incomplete producer runtime matrix")
    return {"schema_version": "biocompiler.synthetic_public_sdk_reproducibility.v1", "status": "success",
        "revision": revision, "source_revision": source_revision, "run_id": run_id,
        "corpus_pin": CORPUS_PIN, "capture_pin": CAPTURE_PIN, "profile_pin": digest(corpus.profiles),
        "receipts": receipts, "native_inputs": natives, "complete_results_sha256": sha(reference),
        "core_occurrences": len(corpus.cases), "verify_role_rejections": len(corpus.verify_cases),
        "native_library_only_occurrences": len(corpus.library), "completed_checks_per_variant": len(corpus.expected())}


def campaign_main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ROLES:
        parser.add_argument("--" + role, required=True, type=Path)
        parser.add_argument("--" + role + "-sha256", required=True)
    parser.add_argument("--native-root", required=True, type=Path)
    parser.add_argument("--platform", required=True, choices=PLATFORMS)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    import biocompiler
    from biocompiler.core_client import CoreClient
    for name in sorted(SOURCE_MODULES):
        importlib.import_module(name)
    started = time.monotonic()
    directory = args.output.with_name(ARTIFACT_DIRECTORY)
    directory.mkdir(parents=True, exist_ok=True)
    require(directory.is_dir() and not directory.is_symlink() and not any(directory.iterdir()), "Unsafe/nonempty producer artifact directory")
    receipt = {"schema_version": SCHEMA, "status": "running", "scope": SCOPE,
        "corpus_pin": CORPUS_PIN, "capture_pin": CAPTURE_PIN, "profile_pin": digest(declaration()),
        "revision": os.environ.get("GITHUB_SHA"), "source_revision": os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")),
        "run_id": os.environ.get("GITHUB_RUN_ID"), "system": platform.system(), "machine": platform.machine(),
        "python_version": platform.python_version(), "native_platform": args.platform,
        "package_path": str(Path(biocompiler.__file__).resolve()), "checks": [], "artifacts": {},
        "artifact_directory": directory.name, "_artifact_directory": str(directory)}
    code = 1
    try:
        require(not Path.cwd().resolve().is_relative_to(ROOT), "Run installed producer campaign outside checkout")
        require(receipt["run_id"] is not None and receipt["source_revision"] is not None, "Same-run hosted metadata required")
        require((platform.system(), platform.machine()) == PLATFORMS[args.platform], "Native/host platform mismatch")
        for name, module in tuple(sys.modules.items()):
            if name == "biocompiler" or name.startswith("biocompiler."):
                origin = getattr(module, "__file__", None)
                require(origin is None or not Path(origin).resolve().is_relative_to(ROOT), "Source-tree product loaded: " + name)
        native = verify_binaries(args.native_root, receipt["revision"], args.platform)
        receipt["native_inputs"] = native
        clients, receipt["executables"] = [], {}
        for role in ROLES:
            path, pin = getattr(args, role), getattr(args, role + "_sha256")
            expected = args.native_root / ("biocompiler-" + role)
            require(path.is_absolute() and path.resolve() == expected.resolve() and not path.is_symlink() and os.access(path, os.X_OK),
                    "Unbound or nonexecutable producer input")
            require(pin == native["sha256"][expected.name], "Explicit binary pin differs from same-run manifest")
            clients.append(CoreClient(path, role=role, expected_sha256=pin, timeout_seconds=300))
            receipt["executables"][role] = str(path)
        receipt["transport_sources"] = {}
        for name in sorted(SOURCE_MODULES):
            path = Path(sys.modules[name].__file__)
            relative = "src/" + name.replace(".", "/") + ".py"
            pin = sha(path.read_bytes())
            require(pin == sha((ROOT / relative).read_bytes()), "Installed producer adapter differs from tested revision")
            receipt["transport_sources"][relative] = pin
        receipt["campaign_sources"] = source_pins(SOURCES)
        corpus = Corpus()
        campaign(clients, corpus, receipt)
        receipt["completed_checks"] = len(receipt["checks"])
        validate_checks(receipt, corpus, Artifacts(directory, receipt["artifacts"]))
        require(canonical(verify_binaries(args.native_root, receipt["revision"], args.platform)) == canonical(native),
                "Native binaries changed during complete producer campaign")
        receipt["status"], code = "success", 0
    except Exception as error:
        receipt["status"], receipt["error"] = "failure", type(error).__name__ + ": " + str(error)
        print(receipt["error"], file=sys.stderr)
    receipt["completed_checks"] = len(receipt["checks"])
    receipt["duration_seconds"] = round(time.monotonic() - started, 6)
    del receipt["_artifact_directory"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(receipt) + b"\n")
    print("Installed public producer SDK:", receipt["status"], receipt["completed_checks"], "complete observations")
    return code


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--compare" not in arguments:
        return campaign_main(arguments)
    parser = argparse.ArgumentParser(description="Compare complete public SDK producer evidence across four runtimes")
    parser.add_argument("--compare", required=True, action="store_true")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--native-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(arguments)
    result = compare(args.root, args.native_root, revision=os.environ.get("GITHUB_SHA"),
        source_revision=os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")), run_id=os.environ.get("GITHUB_RUN_ID"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result) + b"\n")
    print("Complete public producer records/errors match across four required runtimes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

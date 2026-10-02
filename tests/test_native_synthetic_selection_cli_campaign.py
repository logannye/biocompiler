"""Complete native-CLI evidence checks using byte fixtures, never native builds."""
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from tools import check_native_synthetic_selection_cli as c
from test_core_synthetic_producer_public import capabilities

REVISION, SOURCE, RUN = "a"*40, "b"*40, "77"


def role_capabilities(role):
    value = capabilities()
    if role == "verify":
        profiles = c.Oracle().profiles
        value["operations"] = [operation for operation in value["operations"]
            if all(operation not in profile["operations"] for profile in profiles.values())]
        value["validation_scopes"] = [scope for scope in value["validation_scopes"]
            if all(scope != profile["validation_scope"] for profile in profiles.values())]
        for key in profiles: value["profiles"].pop(key,None)
    return value


class NativeSyntheticSelectionCliCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original, cls.old_blobs = c.baseline()
        cls.oracle = c.Oracle()

    def write(self,path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(c.canonical(value)+b"\n")

    def fixture_trace(self,row,audit,store,expected,role):
        if expected is None: return
        def retain(raw):
            descriptor = c.r.descriptor(raw)
            row["native_artifacts"][descriptor["sha256"]] = store.retain(raw)
            return descriptor
        payload,status,result,diagnostics = expected
        for operation,authority,outcome,value,errors,exit_code in (
            ("capabilities",{},"ok",role_capabilities(role),[],0),
            (c.OPERATION,payload,status,result,diagnostics,{"ok":0,"error":2,"unsupported":3}[status])):
            identifier = str(uuid4())
            request = {"protocol":"biocompiler.core.v1","request_id":identifier,"operation":operation,"payload":authority}
            response = c.producer.envelope(role,identifier,operation,outcome,value,errors)
            audit["exchanges"].append({"request":retain(c.canonical(request)),"response":retain(c.canonical(response)+b"\n"),
                "executable":"/installed/biocompiler-"+role,"exit_code":exit_code})
            if operation == c.OPERATION and status == "ok":
                audit["receipts"][identifier] = {"outer":retain(c.canonical(result)),"production":retain(c.canonical(result["production"])),
                    "record":None if result["production"]["record"] is None else retain(c.canonical(result["production"]["record"]))}

    def fixture_receipt(self,*,native=None,target="linux-x86_64",python="3.14"):
        store = c.f.Store()
        def copied(value):
            if type(value) is dict:
                if value.get("kind") in ("blob","repeat"): return store.retain(c.f.restore(value,self.old_blobs))
                return {key:copied(item) for key,item in value.items()}
            if type(value) is list: return [copied(item) for item in value]
            return value
        if native is None: native = {"sha256":{"biocompiler-"+role:("c" if role=="core" else "d")*64 for role in c.ROLES}}
        sources = c.product_sources(); rows = []
        for old in self.original["cases"]:
            row = {key:copied(old[key]) for key in ("id","entrypoint","fault","lineage","files_before","files_after","exit_code")}
            observed = c.counterparts().expected(old,{"exit_code":old["exit_code"],
                **{key:c.f.restore(old[key],self.old_blobs) for key in ("stdout","stderr")}},python)
            row.update({key:store.retain(observed[key]) for key in ("stdout","stderr")})
            row.update(role="core",scope="native_synthetic_selection",argv=[old["argv"][0],"--core-executable",
                "/installed/biocompiler-core","--core-sha256",native["sha256"]["biocompiler-core"],"--core-timeout","300",*old["argv"][1:]],
                console_path="/installed/bin/biocompiler",python_executable="/installed/bin/python3",native_artifacts={})
            frames = [["biocompiler.cli","main","output",""]]
            if self.oracle.trace(old["id"]) is not None:
                frames += [[module,name,"output",""] for module,name in (("biocompiler.cli","_selection_command"),
                    ("biocompiler.synthetic_producer_cli","selection_command"),("biocompiler.core_client","_exchange"),
                    ("biocompiler.core_synthetic_producer_public","SyntheticProducerPublicClient.select_document"))]
            modules = {}
            for module,*_ in frames:
                path = "src/"+module.replace(".","/")+".py"; modules[module] = {"path":path,"sha256":sources[path]}
            audit = {"scope":row["scope"],"guard_active":True,"functions":sorted(frames),"modules":modules,
                "package_path":"/installed/site-packages/biocompiler","exchanges":[],"receipts":{}}
            self.fixture_trace(row,audit,store,self.oracle.trace(old["id"]),"core")
            row["audit"] = store.retain(c.canonical(audit)); rows.append(row)
        witness = {"guard_modules":["biocompiler.core_client"],"exchanges":[],"receipts":{},"native_artifacts":{},
            "module":{"path":"src/biocompiler/core_client.py","sha256":sources["src/biocompiler/core_client.py"],
                      "origin":"/installed/site-packages/biocompiler/core_client.py"}}
        self.fixture_trace(witness,witness,store,(self.oracle.verify_payload,"unsupported",None,[c.producer.UNSUPPORTED]),"verify")
        system,machine = c.PLATFORMS[target]
        return {"schema_version":c.SCHEMA,"scope":c.SCOPE,"status":"success","baseline_pin":c.BASELINE_PIN,
            "runtime_counterpart_sha256":c.COUNTERPART_PIN,"revision":REVISION,"source_revision":SOURCE,"run_id":RUN,
            "python_version":python+".9","system":system,"machine":machine,"native_platform":target,"native_inputs":native,
            "product_sources":sources,"campaign_sources":c.r.source_pins(c.SOURCES),
            "executables":{role:"/installed/biocompiler-"+role for role in c.ROLES},"checks":rows,"completed_checks":72,
            "verify_witness":witness},store.blobs

    def validate(self,receipt,blobs):
        return c.validate(receipt,blobs,self.original,self.old_blobs,oracle=self.oracle)

    def test_complete_original_census_and_separate_verify_boundary(self):
        receipt,blobs = self.fixture_receipt()
        projection = self.validate(receipt,blobs)
        self.assertEqual(len(projection["children"]),72)
        self.assertEqual(len(projection["verify_witness"]),2)
        self.assertEqual(Counter(row["entrypoint"] for row in receipt["checks"]),{"console":68,"module":4})
        self.assertEqual(sum(self.oracle.trace(row["id"]) is not None for row in receipt["checks"]),64)
        for change in (lambda x:x["checks"].pop(),lambda x:x["checks"].append(deepcopy(x["checks"][0])),
            lambda x:x.update(completed_checks=True),lambda x:x["checks"][0].update(role="verify"),
            lambda x:x["checks"][0].update(exit_code=False),lambda x:x["checks"][0].update(extra=True),
            lambda x:x["product_sources"].update({"src/biocompiler/cli.py":"0"*64}),
            lambda x:x["verify_witness"]["exchanges"].pop(),lambda x:x["verify_witness"]["exchanges"][0].update(exit_code=False)):
            forged = deepcopy(receipt); change(forged)
            with self.assertRaises(AssertionError): self.validate(forged,blobs)

    def test_runtime_counterparts_full_actual_bytes_and_rehashed_forgery(self):
        projections=[]
        for python,other in (("3.11","3.14"),("3.14","3.11")):
            receipt,blobs = self.fixture_receipt(python=python)
            projections.append(self.validate(receipt,blobs))
            row = next(row for row in receipt["checks"] if row["id"]=="unknown-flag")
            old = next(row for row in self.original["cases"] if row["id"]=="unknown-flag")
            wrong = c.counterparts().expected(old,{"exit_code":old["exit_code"],
                **{key:c.f.restore(old[key],self.old_blobs) for key in ("stdout","stderr")}},other)
            blobs.pop(row["stderr"]["sha256"])
            store=c.f.Store(); row["stderr"]=store.retain(wrong["stderr"]); blobs.update(store.blobs)
            with self.assertRaisesRegex(AssertionError,"Complete CLI stderr differs"):self.validate(receipt,blobs)
        self.assertEqual(projections[0],projections[1])

    def test_self_consistently_rehashed_wire_receipt_scope_error_and_guard_forgeries(self):
        receipt,blobs=self.fixture_receipt()
        for identifier,field in (("baseline-console","scope"),("baseline-console","record"),("baseline-console","number"),
            ("malformed-frame_fields","diagnostic"),("baseline-console","guard"),("baseline-console","uuid")):
            row=deepcopy(next(row for row in receipt["checks"] if row["id"]==identifier))
            audit=c.r.decode(c.f.restore(row["audit"],blobs)); changed=dict(blobs)
            if field=="guard":
                audit["functions"].append(["biocompiler.synthesis.selection","select_synthetic","output",""])
                audit["functions"].sort()
                with self.assertRaisesRegex(AssertionError,"Forbidden, unbound"):
                    c.validate_audit(row,audit,changed,c.product_sources(),self.oracle)
                continue
            exchange=audit["exchanges"][1]
            response=c.r.decode(c.content(exchange["response"],row,blobs,set()))
            request=c.r.decode(c.content(exchange["request"],row,blobs,set()))
            if field=="scope":response["result"]["claim_scope"]="expanded authority"
            elif field=="record":
                result=response["result"]; result["production"]["record"]["selected_strategy"]="forged"
                result["production"]["record_fingerprint"]=c.digest(result["production"]["record"])
            elif field=="number":response["result"]["presentation"]["exit_code"]=False
            elif field=="diagnostic":response["diagnostics"][0]["path"]="forged/path"
            elif field=="uuid":
                before=response["request_id"]; after="00000000-0000-1000-8000-000000000000"
                request["request_id"]=response["request_id"]=after
                audit["receipts"][after]=audit["receipts"].pop(before)
            store=c.f.Store()
            def replace(old,raw):
                row["native_artifacts"].pop(old["sha256"],None)
                descriptor=c.r.descriptor(raw)
                row["native_artifacts"][descriptor["sha256"]]=store.retain(raw)
                changed.update(store.blobs)
                return descriptor
            exchange["response"]=replace(exchange["response"],c.canonical(response)+b"\n")
            exchange["request"]=replace(exchange["request"],c.canonical(request))
            if response["status"]=="ok":
                retained=audit["receipts"][response["request_id"]]
                for key,value in (("outer",response["result"]),("production",response["result"]["production"]),
                                  ("record",response["result"]["production"]["record"])):
                    if value is not None:retained[key]=replace(retained[key],c.canonical(value))
            with self.assertRaisesRegex(AssertionError,"Complete original native receipt|invalid actual request identity"):
                c.validate_audit(row,audit,changed,c.product_sources(),self.oracle)

    def test_rehashed_verifier_capability_cannot_advertise_production(self):
        receipt,blobs=self.fixture_receipt()
        witness=deepcopy(receipt["verify_witness"])
        exchange=witness["exchanges"][0]
        response=c.r.decode(c.content(exchange["response"],witness,blobs,set()))
        response["result"]["profiles"]["synthetic_producer_public"]=self.oracle.profile
        response["result"]["operations"].append(c.OPERATION)
        response["result"]["validation_scopes"].append(self.oracle.profile["validation_scope"])
        raw=c.canonical(response)+b"\n";descriptor=c.r.descriptor(raw);store=c.f.Store()
        witness["native_artifacts"].pop(exchange["response"]["sha256"])
        witness["native_artifacts"][descriptor["sha256"]]=store.retain(raw)
        exchange["response"]=descriptor
        with self.assertRaisesRegex(AssertionError,"Verifier advertised a producer"):
            c.validate_exchanges(witness,witness,{**blobs,**store.blobs},self.oracle,"/installed/biocompiler-verify",role="verify")

    def fixture_matrix(self,directory):
        root,natives=Path(directory)/"realization",Path(directory)/"native"
        for target,(system,machine) in c.PLATFORMS.items():
            native=natives/target;native.mkdir(parents=True);pins={}
            for role in c.ROLES:
                name="biocompiler-"+role;raw=(target+name+" nonexecutable comparator fixture").encode()
                (native/name).write_bytes(raw);pins[name]=c.f.sha(raw)
            self.write(native/"binaries.json",{"revision":REVISION,"system":system,"machine":machine,"sha256":pins})
            inputs=c.r.verify_binaries(native,REVISION,target)
            for python in c.PYTHONS:
                slot=root/("realization-"+target+"-py"+python)
                self.write(slot/"native-inputs.json",{**inputs,"run_id":RUN,"source_revision":SOURCE,"python_version":python+".9"})
                receipt,blobs=self.fixture_receipt(native=inputs,target=target,python=python)
                receipt.update(artifact_directory=c.ARTIFACT_DIRECTORY,artifacts={})
                for identity,raw in blobs.items():
                    path=slot/c.ARTIFACT_DIRECTORY/(identity+".bin");path.parent.mkdir(exist_ok=True);path.write_bytes(raw)
                    receipt["artifacts"][identity]={"path":path.name,**c.r.descriptor(raw)}
                self.write(slot/c.RECEIPT_FILE,receipt)
        return root,natives

    def test_four_runtime_comparator_full_files_and_same_run_binary_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            root,natives=self.fixture_matrix(directory)
            result=c.compare(root,natives,revision=REVISION,source_revision=SOURCE,run_id=RUN)
            self.assertEqual(len(result["receipts"]),4)
            self.assertEqual(result["children_per_runtime"],72)
            path=root/"realization-linux-x86_64-py3.11"/c.RECEIPT_FILE
            original=json.loads(path.read_bytes())
            for key,value in (("run_id","stale"),("revision","c"*40),("source_revision","c"*40),("python_version","3.14.9")):
                forged=deepcopy(original);forged[key]=value;self.write(path,forged)
                with self.assertRaises(AssertionError):c.compare(root,natives,revision=REVISION,source_revision=SOURCE,run_id=RUN)
            self.write(path,original)
            (natives/"linux-x86_64/biocompiler-core").write_bytes(b"forged native bytes")
            with self.assertRaises(ValueError):c.compare(root,natives,revision=REVISION,source_revision=SOURCE,run_id=RUN)

    def test_actual_installed_python_protocol_children_cover_positive_errors_and_publication(self):
        with tempfile.TemporaryDirectory() as directory,c.selection_paths(),c.f.owned_directories():
            root=Path(directory);site=root/"site";site.mkdir()
            shutil.copytree(c.ROOT/"src/biocompiler",site/"biocompiler",ignore=shutil.ignore_patterns("__pycache__"))
            console=root/"biocompiler";console.write_text("#!"+sys.executable+"\n"+c.f.ENTRYPOINT);console.chmod(0o700)
            table={}
            for case in self.oracle.cases.values():
                trace=self.oracle.trace(case["id"])
                if trace is not None:
                    payload,status,result,diagnostics=trace
                    table[c.digest(payload)]={"status":status,"result":result,"diagnostics":diagnostics,"exit_code":0 if status=="ok" else 2}
            data=root/"fixture.json";self.write(data,{"capabilities":capabilities(),"table":table})
            binary=root/"biocompiler-core"
            binary.write_text("#!"+sys.executable+"\nimport hashlib,json,pathlib,sys\n"+
                "data=json.loads(pathlib.Path("+repr(str(data))+").read_bytes())\nrequest=json.load(sys.stdin)\n"+
                "def encoded(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()\n"+
                "row={'status':'ok','result':data['capabilities'],'diagnostics':[],'exit_code':0} if request['operation']=='capabilities' else data['table'][hashlib.sha256(encoded(request['payload'])).hexdigest()]\n"+
                "response={'protocol':'biocompiler.core.v1','request_id':request['request_id'],'operation':request['operation'],'status':row['status'],'result':row['result'],'diagnostics':row['diagnostics'],'core':{'implementation':'ocaml','version':'0.1.0','protocol':'biocompiler.core.v1','executable':'core'}}\n"+
                "sys.stdout.buffer.write(encoded(response)+b'\\n');sys.exit(row['exit_code'])\n")
            binary.chmod(0o700)
            for name in ("startup","cwd","native-artifacts"):(c.f.CLI_ROOT/name).mkdir()
            (c.f.CLI_ROOT/"startup/sitecustomize.py").write_text("import sys\nsys.path.insert(0,"+repr(str(site))+")\n"+c.STARTUP)
            # All actual original children, including bounded 64 MiB fault cases.
            for case in self.oracle.cases.values():
                with self.subTest(case=case["id"]):
                    store=c.f.Store()
                    with patch.dict(os.environ,{"PATH":str(root)+os.pathsep+os.environ["PATH"]}):
                        row=c.run_case(case,"core",binary,c.f.sha(binary.read_bytes()),store)
                    old=next(item for item in self.original["cases"] if item["id"]==case["id"])
                    c.equal_observations(row,old,store.blobs,self.old_blobs)
                    audit=c.r.decode(c.f.restore(row["audit"],store.blobs))
                    c.validate_audit(row,audit,store.blobs,c.product_sources(),self.oracle)


if __name__=="__main__":unittest.main()

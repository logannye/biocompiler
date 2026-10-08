"""Pure Python process-fixture and four-runtime public producer evidence tests."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from tools import check_native_synthetic_public_sdk as p
from tests import test_native_synthetic_producer_campaign as raw_fixtures
REVISION,SOURCE,RUN=raw_fixtures.REVISION,raw_fixtures.SOURCE,raw_fixtures.RUN


class PublicSyntheticSDKCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full=p.Corpus()
        cls.original=raw_fixtures.SyntheticProducerCampaignTests()
        cls.original.full=cls.full

    def small(self):
        raw=self.original.small()
        # Exercise the exact explicit-config representatives used by the full
        # installed campaign, with all three ordinary failure forms retained.
        parents={row["origin_id"] for row in self.full.cases if row["input_kind"]=="typed"}
        raw.cases=[deepcopy(row) for row in self.full.cases if row["input_kind"]=="bytes" and row["id"] in parents]+raw.cases[3:]
        corpus=object.__new__(p.Corpus)
        corpus.profiles=raw.profiles;corpus.declaration=raw.declaration
        corpus.library=raw.library
        corpus.cases=p.project_cases(raw.cases)
        corpus.verify_cases=[{**case,"input_kind":"verify_transport","origin_id":case["id"]} for case in raw.verify_cases]
        return corpus

    def base_receipt(self,folder):
        artifacts=folder/p.ARTIFACT_DIRECTORY;artifacts.mkdir(parents=True)
        return {"checks":[],"artifacts":{},"_artifact_directory":str(artifacts),
                "executables":{role:str(folder/("biocompiler-"+role)) for role in p.ROLES}}

    def actual(self,folder,corpus):
        from biocompiler.core_client import CoreClient
        for module in p.SOURCE_MODULES:p.importlib.import_module(module)
        receipt=self.base_receipt(folder);table={}
        for (role,_),case in corpus.expected().items():
            wanted,code=self.original.wanted(corpus,role,case)
            table[role+":"+case["operation"]+":"+p.sha(case["authority"])]=[wanted,code]
        raw_fixtures.SyntheticProducerCampaignTests.write(folder/"fixture.json",{"table":table,"capabilities":{role:raw_fixtures.SyntheticProducerCampaignTests.capabilities(corpus,role) for role in p.ROLES}})
        script='''import hashlib,json,pathlib,sys
role=pathlib.Path(sys.argv[0]).name.removeprefix("biocompiler-")
data=json.loads(pathlib.Path(sys.argv[0]).with_name("fixture.json").read_bytes())
request=json.loads(sys.stdin.buffer.read())
def enc(x):return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
if request["operation"]=="capabilities":
 response={"protocol":"biocompiler.core.v1","request_id":request["request_id"],"operation":"capabilities","status":"ok","diagnostics":[],"result":data["capabilities"][role],"core":{"implementation":"ocaml","version":"0.1.0","protocol":"biocompiler.core.v1","executable":role}}
 code=0
else:
 response,code=data["table"][role+":"+request["operation"]+":"+hashlib.sha256(enc(request["payload"])).hexdigest()]
 response["request_id"]=request["request_id"]
sys.stdout.buffer.write(enc(response)+b"\\n")
sys.exit(code)
'''
        clients=[]
        for role in p.ROLES:
            path=Path(receipt["executables"][role]);path.write_text("#!"+sys.executable+"\n"+script);path.chmod(0o700)
            clients.append(CoreClient(path,role=role,expected_sha256=p.sha(path.read_bytes())))
        p.campaign(clients,corpus,receipt)
        receipt["completed_checks"]=len(receipt["checks"])
        p.validate_checks(receipt,corpus,p.Artifacts(folder/p.ARTIFACT_DIRECTORY,receipt["artifacts"]))
        return receipt

    def test_full_original_projection_and_input_form_census(self):
        self.assertEqual(len(self.full.cases),1235)
        self.assertEqual(len(self.full.library),1146)
        self.assertEqual(len(self.full.expected()),1238)
        self.assertEqual(Counter(row["input_kind"] for row in self.full.cases),{"bytes":1226,"mapping":3,"typed":3,"native":3})
        self.assertEqual(sum(row["generation_error"] is not None for row in self.full.cases),33)
        self.assertEqual(sum(row["error"] is not None for row in self.full.cases),5)
        originals={row["id"]:row for row in self.full.cases if row["input_kind"]=="bytes"}
        for row in self.full.cases:
            base=originals[row["origin_id"]]
            for key in ("authority","expected","evidence","generation_error","error"):
                self.assertEqual(row[key],base[key])

    def test_actual_public_routes_all_input_forms_and_error_kinds(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt=self.actual(Path(directory),self.small())
            self.assertEqual(len(receipt["checks"]),18)
            self.assertEqual(sum(len(row["exchanges"]) for row in receipt["checks"])+1,34)
            self.assertEqual({row["input_kind"] for row in receipt["checks"]},{"bytes","mapping","typed","native","verify_transport"})

    def matrix(self,directory):
        directory=Path(directory);corpus=self.small()
        actual=self.actual(directory/"actual",corpus)
        root,natives=directory/"realization",directory/"native"
        import shutil
        for target,(system,machine) in p.PLATFORMS.items():
            native=natives/target;native.mkdir(parents=True)
            pins={}
            for role in p.ROLES:
                path=native/("biocompiler-"+role);path.write_bytes((target+role+"nonexecutable-test-data").encode());pins[path.name]=p.sha(path.read_bytes())
            raw_fixtures.SyntheticProducerCampaignTests.write(native/"binaries.json",dict(revision=REVISION,system=system,machine=machine,sha256=pins))
            inputs=p.verify_binaries(native,REVISION,target)
            for python in p.PYTHONS:
                slot=root/("realization-"+target+"-py"+python);slot.mkdir(parents=True)
                shutil.copytree(directory/"actual"/p.ARTIFACT_DIRECTORY,slot/p.ARTIFACT_DIRECTORY)
                receipt=deepcopy(actual);receipt.pop("_artifact_directory")
                # Full wire UUIDs are regenerated per runtime; no content other
                # than the already permitted UUID field changes.
                artifacts=slot/p.ARTIFACT_DIRECTORY
                exchanges=[e for row in receipt["checks"] for e in row["exchanges"]]+[receipt["verify_capabilities"]]
                used={}
                for exchange in exchanges:
                    identity=str(uuid4())
                    for key,newline in (("request",b""),("response",b"\n")):
                        previous=exchange[key];raw=json.loads((artifacts/(previous+".bin")).read_bytes());raw["request_id"]=identity
                        content=p.canonical(raw)+newline;pin=p.sha(content);(artifacts/(pin+".bin")).write_bytes(content)
                        receipt["artifacts"][pin]={"path":pin+".bin","sha256":pin,"bytes":len(content)};exchange[key]=pin;used[previous]=None
                remaining=p.canonical(receipt["checks"])+p.canonical(receipt["verify_capabilities"])
                for pin in used:
                    if pin.encode() not in remaining:
                        del receipt["artifacts"][pin];(artifacts/(pin+".bin")).unlink()
                receipt["executables"]={role:str(native/("biocompiler-"+role)) for role in p.ROLES}
                for row in receipt["checks"]:
                    for e in row["exchanges"]:e["executable"]=receipt["executables"][row["role"]]
                receipt["verify_capabilities"]["executable"]=receipt["executables"]["verify"]
                raw_fixtures.SyntheticProducerCampaignTests.write(slot/"native-inputs.json",dict(inputs,run_id=RUN,source_revision=SOURCE,python_version=python+".9"))
                receipt.update(schema_version=p.SCHEMA,status="success",scope=p.SCOPE,revision=REVISION,source_revision=SOURCE,run_id=RUN,
                    system=system,machine=machine,native_platform=target,python_version=python+".9",native_inputs=inputs,
                    package_path="/installed/biocompiler/__init__.py",corpus_pin=p.CORPUS_PIN,capture_pin=p.CAPTURE_PIN,
                    profile_pin=p.digest(corpus.profiles),artifact_directory=p.ARTIFACT_DIRECTORY,
                    transport_sources=p.source_pins("src/"+name.replace(".","/")+".py" for name in sorted(p.SOURCE_MODULES)),campaign_sources=p.source_pins(p.SOURCES))
                raw_fixtures.SyntheticProducerCampaignTests.write(slot/p.RECEIPT_FILE,receipt)
        return root,natives,corpus

    def compare(self,root,natives,corpus):
        with patch.object(p,"Corpus",return_value=corpus):return p.compare(root,natives,revision=REVISION,source_revision=SOURCE,run_id=RUN)

    def test_four_runtime_comparator_and_rehashed_semantic_forgeries(self):
        with tempfile.TemporaryDirectory() as directory:
            root,natives,corpus=self.matrix(directory)
            self.assertEqual(self.compare(root,natives,corpus)["status"],"success")
            slot=root/"realization-linux-x86_64-py3.11";path=slot/p.RECEIPT_FILE;original=json.loads(path.read_bytes())
            changes=(lambda x:x.update(source_revision="c"*40),lambda x:x.update(completed_checks=True),lambda x:x["checks"].pop(),
                lambda x:x["checks"][0]["guard_frames"].append(["biocompiler.synthesis.synthetic","_generate_synthetic","output",""]),
                lambda x:x["checks"][0].update(input_kind="typed"),lambda x:x.update(pending_helpers=[]),
                lambda x:x["checks"][0]["exchanges"][1].update(executable="biocompiler-core"),
                lambda x:x["transport_sources"].pop(next(iter(x["transport_sources"]))))
            for mutate in changes:
                receipt=deepcopy(original);mutate(receipt);raw_fixtures.SyntheticProducerCampaignTests.write(path,receipt)
                with self.assertRaises((AssertionError,ValueError)):self.compare(root,natives,corpus)
            raw_fixtures.SyntheticProducerCampaignTests.write(path,original)
            for index,mutate in ((0,lambda x:x["result"]["profiles"]["synthetic_generation"]["resources"]["protocol"].update(max_work=True)),
                                 (1,lambda x:x["result"]["record"].update(intended_use="human_therapeutic")),
                                 (1,lambda x:x["result"]["authority_identities"].update(request_fingerprint="0"*64)),
                                 (1,lambda x:x.update(request_id=str(uuid4())))):
                receipt=deepcopy(original);exchange=receipt["checks"][0]["exchanges"][index];old=exchange["response"]
                old_path=slot/p.ARTIFACT_DIRECTORY/(old+".bin");old_bytes=old_path.read_bytes();wire=json.loads(old_bytes);mutate(wire)
                raw=p.canonical(wire)+b"\n";pin=p.sha(raw);target=slot/p.ARTIFACT_DIRECTORY/(pin+".bin");target.write_bytes(raw)
                del receipt["artifacts"][old];old_path.unlink();receipt["artifacts"][pin]={"path":pin+".bin","sha256":pin,"bytes":len(raw)};exchange["response"]=pin
                raw_fixtures.SyntheticProducerCampaignTests.write(path,receipt)
                with self.assertRaises(AssertionError):self.compare(root,natives,corpus)
                target.unlink();old_path.write_bytes(old_bytes)
            raw_fixtures.SyntheticProducerCampaignTests.write(path,original)

    def test_only_unique_canonical_version_four_request_ids_project(self):
        first=str(uuid4());seen=set()
        p.uuid4_identity(first,seen)
        for value in (first,"00000000-0000-1000-8000-000000000000",first.upper(),True,None):
            with self.assertRaises(AssertionError):p.uuid4_identity(value,seen)

    def test_semantic_and_out_of_phase_serializer_execution_rejected(self):
        for module,name in (("biocompiler.synthesis.synthetic","_generate_synthetic"),("biocompiler.semantics.evaluator","evaluate"),
                            ("biocompiler.compiler.request","RealizationRequest.to_dict")):
            scope={"__name__":module};exec("def forbidden(): return None",scope);scope["forbidden"].__code__=scope["forbidden"].__code__.replace(co_qualname=name)
            with self.assertRaisesRegex(AssertionError,"semantic fallback"):
                with p.routed_execution():scope["forbidden"]()
        with self.assertRaisesRegex(AssertionError,"Unreviewed"):
            with p.routed_execution():__import__("biocompiler.compiler.synthetic")


if __name__=="__main__":unittest.main()

"""Freeze complete construction declarations, never execute molecular recipes."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys
from biocompiler.errors import SerializationError
from biocompiler.ir import circuit_construction as C
from biocompiler.ir.circuit_recoding import CanonicalBaseEdit, ChemicalBaseEdit, CodonRecoding, TranslationPolicy
from biocompiler.ir.circuit_transitions import ChemistryDisposition, FeatureDisposition
from biocompiler.ir.circuit_payloads import PayloadStructureContract, RequiredPayloadRegion
from biocompiler.ir.circuit_intent import CircuitProviderRequirement
from biocompiler.ir.circuit_observations import ObservationEntity
from biocompiler.ir.molecule_chemistry import ChemicalIdentity
from biocompiler.ir.serialization import fingerprint
from biocompiler.semantics.molecule_coordinates import CoordinatePath, IndexSpan
ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/construction-v1.json"
SCHEMA = "biocompiler.construction_conformance.v1"
KINDS = {"root_source": C.RootSource, "value_ref": C.ValueRef, "selection": C.ValueSelection,
         "product_port": C.ProductPort, "processing_product": C.ProcessingProduct,
         "translation_product": C.TranslationProduct, "translation_branch": C.TranslationBranch,
         "peptide_product": C.PeptideProduct, "transform_step": C.TransformStep,
         "output_member": C.OutputMember, "role": C.RoleDeclaration, "member_requirement": C.MemberRequirement,
         "complex_constituent": C.ComplexMemberConstituent, "complex_member": C.ComplexMemberPlan,
         "amount": C.AmountDeclaration, "request": C.CircuitConstructionRequest}
KINDS.update({cls.schema_version.removeprefix("biocompiler.construction_").removesuffix(".v0.1"): cls for cls in C.OPERATION_TYPES})
BY_SCHEMA = {cls.schema_version: kind for kind, cls in KINDS.items()}

def require(value, message):
    if not value: raise AssertionError(message)

def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)+"\n").encode()

def fixture_module():
    if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("construction_domain_authority", ROOT / "tests/test_circuit_construction_ir.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def relocate(value):
    if isinstance(value, list): return [relocate(item) for item in value]
    if isinstance(value, dict):
        result = {key: relocate(item) for key, item in value.items()}
        if set(result) == {"file", "line", "function"} and Path(result["file"]).is_absolute():
            result["file"] = Path(result["file"]).resolve().relative_to(ROOT).as_posix()
        return result
    return value

def edit(path, value): return dict(op="set", path=path, value=value)
def remove(path): return dict(op="remove", path=path)
def apply_edits(value, edits):
    value = deepcopy(value)
    for item in edits:
        target = value
        for key in item["path"][:-1]: target = target[key]
        key = item["path"][-1]
        if item["op"] == "remove": del target[key]
        elif item["op"] == "set": target[key] = deepcopy(item["value"])
        else: raise AssertionError("Unknown construction edit")
    return value

def summary(value):
    result = dict(fingerprint=value.fingerprint)
    if isinstance(value, C.OPERATION_TYPES):
        result["selections"] = [item.to_dict() for item in C.operation_selections(value)]
        result["conditions"] = sorted(C._operation_conditions(value))
    return result

def build_corpus():
    f = fixture_module()
    req = f.request()
    docs, records, rejections, objects = {}, [], [], {}
    def retain(identity, value, edits=(), origin="artificial_declaration"):
        raw = relocate(value.to_dict() if hasattr(value, "to_dict") else value)
        kind = BY_SCHEMA[raw["schema_version"]]
        value = KINDS[kind].from_dict(raw)
        doc = value.to_dict(); digest = fingerprint(doc); docs[digest] = doc
        require(encoded(KINDS[kind].from_dict(apply_edits(doc, edits)).to_dict()) == encoded(doc), "Positive normalization differs " + identity)
        records.append(dict(id=identity, kind=kind, document_id=digest, edits=list(edits), expected=summary(value), origin=origin))
        objects[identity] = value
        return value
    def reject(identity, source, edits, code="invalid_construction"):
        case = next(case for case in records if case["id"] == source)
        try: KINDS[case["kind"]].from_dict(apply_edits(docs[case["document_id"]], edits))
        except SerializationError: pass
        else: raise AssertionError("Python accepted intended construction rejection " + identity)
        rejections.append(dict(id=identity, kind=case["kind"], document_id=case["document_id"], edits=edits, expected_code=code))
    retain("request/base", req)
    whole = req.steps[0].operation.input
    frame = req.sources[0].molecule.space.id
    selected = replace(whole, path=CoordinatePath(frame, (IndexSpan(0, 3),), "+"))
    second = replace(whole, path=CoordinatePath(frame, (IndexSpan(1, 4),), "+"))
    policy = TranslationPolicy("ordinary_cds")
    conditional_policy = TranslationPolicy("conditional_cds", recodings=(CodonRecoding(0, "ACG", "U", "recoding_declared"),))
    operations = [req.steps[0].operation, C.ConcatenateOperation((whole, whole)), C.OrientationOperation(selected, "reverse_complement"),
                  C.TranscriptionOperation(selected), C.CircularizationOperation(whole, 4),
                  C.BaseEditingOperation(whole, (CanonicalBaseEdit(0,"A","G"),),
                      (ChemicalBaseEdit(1,"C",None,ChemicalIdentity("software_fixture","modified_C","1")),)),
                  C.TranslationOperation(selected, policy),
                  C.MultiORFTranslationOperation((C.TranslationProduct("product_A",selected,policy),C.TranslationProduct("product_B",second,policy))),
                  C.ConditionalTranslationOperation((C.TranslationBranch("on","on_declared",whole,conditional_policy,"product_A"),
                                                    C.TranslationBranch("off","off_declared",whole,None,None))),
                  C.RibosomalSkippingOperation(selected,policy,(C.PeptideProduct("product_A",IndexSpan(0,1)),),"skip_declared")]
    for cls in C.PROCESSING_OPERATION_TYPES:
        processing = f.processing_request(cls)
        operations.append(processing.steps[0].operation)
        retain("request/" + BY_SCHEMA[cls.schema_version], processing)
    for operation in operations:
        kind = BY_SCHEMA[operation.schema_version]
        retain("operation/"+kind, operation)
        if not isinstance(operation, C.PROCESSING_OPERATION_TYPES):
            ports = [item.port_id for item in operation.products] if isinstance(operation, (C.MultiORFTranslationOperation,C.RibosomalSkippingOperation)) else ["product_A"]
            step = replace(req.steps[0], operation=operation, ports=tuple(f.port(p) for p in ports), assumptions=tuple(sorted(C._operation_conditions(operation))))
            retain("request/"+kind, replace(req, steps=(step,), output_members=tuple(f.output("output_"+p,p) for p in ports),
                requirements=tuple(f.member("required_"+p,"output_"+p,"payload" if i==0 else "control") for i,p in enumerate(ports))))
    for value in [*req.sources, whole.value, whole, selected, *req.steps[0].ports, *req.steps,
                  *req.output_members, *req.requirements[0].roles, *req.requirements]:
        kind = BY_SCHEMA[value.schema_version]
        retain("leaf/" + kind + ("/path" if value is selected else ""), value)
    retain("operation/orientation_reverse", C.OrientationOperation(whole,"reverse"))
    retain("operation/translation_conditional", C.TranslationOperation(selected,conditional_policy))
    multi = objects["operation/multi_orf_translation"]
    retain("operation/multi_duplicate_selection", replace(multi,products=(multi.products[0],replace(multi.products[0],port_id="product_B"))))
    for value in [objects["operation/rna_cleavage"].products[0], multi.products[0],
                  *objects["operation/conditional_translation"].branches, objects["operation/ribosomal_skipping"].products[0]]:
        kind=BY_SCHEMA[value.schema_version]
        retain("leaf/"+kind+("/"+value.id if isinstance(value,C.TranslationBranch) else ""), value)
    complex_ = C.ComplexMemberPlan("complex_A","rna_complex",(C.ComplexMemberConstituent("output_A",2,f.fixture_provenance("complex")),),f.fixture_provenance("complex"))
    retain("leaf/complex_constituent",complex_.constituents[0]); retain("leaf/complex_member",complex_)
    complex_request=replace(req,complex_members=(complex_,),requirements=(*req.requirements,f.member("complex_required","complex_A","control")))
    retain("request/complex",complex_request)
    for name,quantity in [("integer",1),("unknown",None),("float",1.0),("signed_zero",-0.0),("max_integer",(1<<1024)-1)]:
        amount=C.AmountDeclaration("amount_A","output_A","preparation_A",("required_A.role",),quantity,"fixture_units",f.fixture_provenance("amount"))
        retain("amount/"+name,amount)
    retain("request/amount",replace(complex_request,amounts=(objects["amount/integer"],)))
    retain("request/direct_root",replace(req,steps=(),output_members=(replace(req.output_members[0],value=C.ValueRef("root","source_A")),)))
    retain("request/chain",replace(req,steps=(*req.steps,f.step("step_B","product_A","product","product_B")),
        output_members=(replace(req.output_members[0],value=C.ValueRef("product","product_B")),)))
    retain("request/diagnostic",replace(req,mode="diagnostic"))
    retain("request/unused_source",replace(req,sources=(*req.sources,f.root("unused_source"))))
    contract=PayloadStructureContract("not_yet_materialized","delivered_rna","linear",(RequiredPayloadRegion("region","fixture"),),f.fixture_provenance("contract"))
    retain("request/deferred_payload_structure",replace(req,payload_structures=(contract,)))
    provider=CircuitProviderRequirement("fixture_provider",ObservationEntity("software_fixture","provider","1","unknown"),"host","cytoplasm","fixture_group")
    original=req.circuit.requirements[0]
    circuit=replace(req.circuit,requirements=(replace(original,behavior=replace(original.behavior,dependencies=(provider,))),))
    external=C.MemberRequirement("required_provider","host_provider",None,provider.id,provider.fingerprint,
        (C.RoleDeclaration("provider_role","provider","host_provider","cytoplasm"),))
    retain("leaf/external",external)
    retain("request/provider",replace(req,circuit=circuit,requirements=(*req.requirements,external)))
    for category in sorted(C.MEMBER_CATEGORIES): retain("category/"+category,f.member(category=category))
    retained_case_b=[]
    for variant in ("base","parameter-default","parameter-override"):
        raw=json.loads((ROOT/"tests/conformance/case-b"/variant/"candidate.json").read_bytes())["construction"]["request"]
        retain("case_b/"+variant,raw,origin="retained_case_b_complete_authority")
        retained_case_b.append(dict(id="case_b/"+variant,variant=variant,path=["construction","request"]))
    # One complete strict-field inventory per schema, including constructor defaults.
    for kind in sorted(KINDS):
        case=next(case for case in records if case["kind"]==kind)
        document=docs[case["document_id"]]
        for key in document:
            reject("fields/"+kind+"/missing/"+key,case["id"],[remove([key])],"missing_field")
        reject("fields/"+kind+"/extra",case["id"],[edit(["expected_sequence"],"ACGU")],"unknown_field")
        reject("fields/"+kind+"/version",case["id"],[edit(["schema_version"],document["schema_version"]+".unsupported")],"unsupported_schema")
    reject("operation/empty_concatenation","operation/concatenate",[edit(["inputs"],[])])
    reject("operation/concatenation_limit","operation/concatenate",[edit(["inputs"],[None]*129)],"molecular_resource_limit")
    reject("operation/orientation_unknown","operation/orientation",[edit(["action"],"complement")])
    reject("operation/transcription_unknown","operation/transcription",[edit(["mapping_profile"],"implicit")])
    for kind in ["rna_cleavage","rna_splicing","protein_cleavage","protein_splicing","circularization","base_editing"]:
        reject("operation/"+kind+"_partial","operation/"+kind,[edit(["input"],selected.to_dict())])
    for kind in ["rna_cleavage","rna_splicing","protein_cleavage","protein_splicing"]:
        reject("operation/"+kind+"_reverse","operation/"+kind,[edit(["products",0,"path","strand"],"-")])
        reject("operation/"+kind+"_duplicate","operation/"+kind,[edit(["products",1,"port_id"],"product_A")])
    reject("operation/cleavage_disjoint","operation/rna_cleavage",[edit(["products",0,"path","spans"],[IndexSpan(0,1).to_dict(),IndexSpan(2,3).to_dict()])])
    for name,val,code in [("bool",True,"invalid_type"),("float",1.0,"invalid_type"),("negative",-1,"invalid_molecular_index"),("limit",1_000_001,"invalid_molecular_index")]:
        reject("operation/origin_"+name,"operation/circularization",[edit(["origin"],val)],code)
    reject("operation/empty_edits","operation/base_editing",[edit(["canonical_edits"],[]),edit(["chemical_edits"],[])])
    reject("operation/overlap_edits","operation/base_editing",[edit(["chemical_edits",0,"position"],0)])
    reject("operation/multi_wrong_source","operation/multi_orf_translation",[edit(["products",1,"input","value","id"],"other")])
    reject("operation/multi_whole","operation/multi_orf_translation",[edit(["products",0,"input","path"],None)])
    reject("operation/branch_pair","leaf/translation_branch/on",[edit(["port_id"],None)])
    reject("operation/branch_condition","operation/conditional_translation",[edit(["branches",1,"condition"],"off_declared")])
    reject("operation/branch_no_producer","operation/conditional_translation",[edit(["branches",1,"port_id"],None),edit(["branches",1,"policy"],None)])
    reject("step/missing_assumptions","request/conditional_translation",[edit(["steps",0,"assumptions"],[])])
    reject("step/duplicate_assumptions","leaf/transform_step",[edit(["assumptions"],["x","x"])])
    reject("step/port_mismatch","request/rna_cleavage",[edit(["steps",0,"ports",1,"id"],"other")])
    disposition=ChemistryDisposition("not_input","cap","unknown",(),f.fixture_provenance("disposition"))
    reject("step/chemistry_source","leaf/transform_step",[edit(["ports",0,"chemistry_transition","mode"],"explicit_output"), edit(["ports",0,"chemistry_transition","output"],req.sources[0].molecule.chemistry.to_dict()), edit(["ports",0,"chemistry_transition","dispositions"],[disposition.to_dict()])])
    feature=FeatureDisposition("not_input","feature","unknown",(),f.fixture_provenance("disposition"))
    reject("step/feature_source","leaf/transform_step",[edit(["ports",0,"feature_transition","dispositions"],[feature.to_dict()])])
    reject("request/forward","request/chain",[edit(["steps"],list(reversed(objects["request/chain"].to_dict()["steps"])) )])
    for name,path,val in [("wrong_kind",["steps",0,"operation","input","value","kind"],"product"),
                          ("missing_value",["output_members",0,"value","id"],"missing"),
                          ("product_collision",["steps",0,"ports",0,"id"],"source_A"),
                          ("product_frame",["steps",0,"ports",0,"space_id"],frame),
                          ("output_frame",["output_members",0,"space_id"],frame),
                          ("absent_required",["requirements",0,"member_id"],"missing"),
                          ("abstract_role",["requirements",0,"roles",0,"compartment"],"abstract"),
                          ("unknown_mode",["mode"],"automatic")]:
        reject("request/"+name,"request/base",[edit(path,val)])
    reject("request/unused_product","request/base",[edit(["steps"],[*req.to_dict()["steps"],f.step("unused",product_id="unused_product").to_dict()])])
    reject("request/unused_byproduct","request/rna_cleavage",[edit(["output_members"],[objects["request/rna_cleavage"].to_dict()["output_members"][0]]),edit(["requirements"],[req.requirements[0].to_dict()])])
    reject("request/processing_frame","request/rna_cleavage",[edit(["steps",0,"operation","products",0,"path","space_id"],"other")])
    reject("request/complex_missing","request/complex",[edit(["complex_members",0,"constituents",0,"member_id"],"missing")])
    reject("request/complex_uncovered","request/complex",[edit(["requirements"],[req.requirements[0].to_dict()])])
    reject("request/amount_subject","request/amount",[edit(["amounts",0,"subject_id"],"complex_A")])
    duplicate=replace(objects["amount/integer"],id="amount_B").to_dict()
    reject("request/duplicate_preparation","request/amount",[edit(["amounts"],[objects["amount/integer"].to_dict(),duplicate])])
    reject("request/provider_pin","request/provider",[edit(["requirements",1,"external_fingerprint"],"0"*64)])
    reject("request/provider_compartment","request/provider",[edit(["requirements",1,"roles",0,"compartment"],"nucleus")])
    reject("request/provider_kind","request/provider",[edit(["requirements",1,"category"],"experimental_input"),edit(["requirements",1,"roles",0,"purpose"],"external_input")])
    for name,q,code in [("bool",True,"invalid_type"),("negative",-1,"invalid_construction"),("overflow",1<<1024,"invalid_construction")]:
        reject("amount/invalid_"+name,"amount/integer",[edit(["quantity"],q)],code)
    coverage=dict(record_kinds=sorted(KINDS),operation_schemas=sorted(cls.schema_version for cls in C.OPERATION_TYPES),
                  record_count=len(records),rejection_count=len(rejections),case_b=retained_case_b,
                  rejection_codes=dict(sorted(Counter(case["expected_code"] for case in rejections).items())))
    return dict(schema_version=SCHEMA,claim_scope="Declared construction authority only; no recipe execution, material reconstruction, biological function or acceptance.",
                documents=docs,records=records,rejections=rejections,coverage=coverage)

def check_corpus(corpus):
    require(corpus["schema_version"]==SCHEMA,"Wrong construction corpus schema")
    ids=[case["id"] for case in corpus["records"]+corpus["rejections"]]
    require(len(ids)==len(set(ids)),"Duplicate construction case identity")
    require(corpus["coverage"]["record_kinds"]==sorted(KINDS),"Missing construction schema")
    require({case["kind"] for case in corpus["records"]}==set(KINDS),"Missing actual construction schema")
    for key,records in (("record_count",corpus["records"]),("rejection_count",corpus["rejections"])):
        require(corpus["coverage"][key]==len(records),"Stale construction coverage count")
    for case in corpus["records"]:
        doc=corpus["documents"][case["document_id"]]
        require(fingerprint(doc)==case["document_id"],"Construction document pin differs")
        value=KINDS[case["kind"]].from_dict(apply_edits(doc,case["edits"]))
        require(encoded(value.to_dict())==encoded(doc),"Normalized construction differs")
        require(encoded(summary(value))==encoded(case["expected"]),"Construction expectations differ")
    for case in corpus["rejections"]:
        doc=corpus["documents"][case["document_id"]]
        try: KINDS[case["kind"]].from_dict(apply_edits(doc,case["edits"]))
        except SerializationError: pass
        else: raise AssertionError("Accepted intended construction rejection "+case["id"])
    pending=[(corpus,0)]; nodes=0
    while pending:
        value,depth=pending.pop(); nodes+=1
        require(nodes<=250_000 and depth<=128,"Whole construction corpus exceeds native wire bounds")
        if isinstance(value,dict): pending.extend((v,depth+1) for pair in value.items() for v in pair)
        elif isinstance(value,list): pending.extend((v,depth+1) for v in value)
    require(len(encoded(corpus))<=16*1024*1024,"Construction corpus read bound")
    require(b"/Users/" not in encoded(corpus),"Machine-specific source coordinate")

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--write",action="store_true"); parser.add_argument("--check",action="store_true")
    args=parser.parse_args(argv); corpus=build_corpus(); check_corpus(corpus); content=encoded(corpus)
    if args.write: CORPUS.write_bytes(content)
    else: require(CORPUS.read_bytes()==content,"Construction corpus drifted; inspect before --write")
    print(json.dumps(dict(records=len(corpus["records"]),rejections=len(corpus["rejections"]),bytes=len(content)),sort_keys=True))
if __name__=="__main__": main()

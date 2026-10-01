"""Retain exact molecular transition/edit declarations; no execution authority.

The current Python constructors are a compatibility oracle. Explicit complete
record literals and a separate codon-table census remain independent assertions.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from itertools import product
import json
from pathlib import Path
import sys

from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_molecules import MoleculeFeature
from biocompiler.ir.circuit_transitions import ChemistryDisposition, ChemistryTransition, FeatureDisposition, FeatureTransition
from biocompiler.ir.circuit_recoding import CanonicalBaseEdit, ChemicalBaseEdit, CodonRecoding, TranslationPolicy, STANDARD_RNA_CODON_TABLE
from biocompiler.ir.molecule_chemistry import ChemicalIdentity
from biocompiler.ir.molecule_records import DeclarationProvenance
from biocompiler.ir.serialization import fingerprint
from biocompiler.semantics.molecule_coordinates import CoordinatePath, IndexSpan

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/molecular-transitions-v1.json"
SCHEMA = "biocompiler.molecular_transitions_conformance.v1"
INVENTORIES = {
    "positive": "193604f8d1e3cee3466430c30f694a0159d08b8be3a4b14549d5e8464af8a737",
    "negative": "c210da4aa1e67c25666995f25e451366dbde237a1a9a858b9888aec840884f30",
    "literals": "52239f6c1c87841bd1d73f43ab670563223b761a0ac0c3922f9a20516784c7af",
}
PARSERS = {"chemistry_disposition": ChemistryDisposition, "chemistry_transition": ChemistryTransition,
           "feature_disposition": FeatureDisposition, "feature_transition": FeatureTransition,
           "canonical_edit": CanonicalBaseEdit, "chemical_edit": ChemicalBaseEdit,
           "codon_recoding": CodonRecoding, "translation_policy": TranslationPolicy}
PROVENANCE = {"schema_version": "biocompiler.molecular_declaration_provenance.v0.1", "status": "unknown", "authority": [],
              "locator": None, "reason": "Artificial declared transition; no biochemical evidence."}
# Authored complete expectations, not serialized from the Python objects below.
LITERALS = {
 "literal/canonical": {"schema_version":"biocompiler.canonical_base_edit.v0.1","position":0,"expected":"A","replacement":"G"},
 "literal/chemical": {"schema_version":"biocompiler.chemical_base_edit.v0.1","position":1,"parent":"A","before":None,
     "after":{"schema_version":"biocompiler.chemical_identity.v0.1","namespace":"biocompiler.chemical","accession":"inosine","version":"1"}},
 "literal/recoding": {"schema_version":"biocompiler.codon_recoding.v0.1","codon_index":1,"expected_triplet":"UGA","amino_acid":"U","condition":"artificial_condition"},
 "literal/ordinary": {"schema_version":"biocompiler.translation_policy.v0.1","profile":"ordinary_cds","genetic_code":"ncbi_standard_v1","recodings":[]},
 "literal/inheritance": {"schema_version":"biocompiler.chemistry_transition.v0.1","mode":"exact_inheritance","output":None,"dispositions":[],"provenance":PROVENANCE},
 "literal/features": {"schema_version":"biocompiler.feature_transition.v0.1","dispositions":[],"added":[],"provenance":PROVENANCE},
}

def require(value, message):
    if not value: raise AssertionError(message)

def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()

def build_corpus():
    if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
    from examples.circuit_molecules import fixture_chemistry
    p = DeclarationProvenance("unknown", (), None, PROVENANCE["reason"])
    require(p.to_dict() == PROVENANCE, "Independent provenance literal differs")
    chem = lambda accession="inosine", namespace="biocompiler.chemical", version="1": ChemicalIdentity(namespace, accession, version)
    feature = lambda identity, start=0, end=2: MoleculeFeature(identity, "artificial_region", CoordinatePath("output", (IndexSpan(start,end),), "+"), p)
    recode = lambda index=1, triplet="UGA", amino="U", condition="artificial_condition": CodonRecoding(index, triplet, amino, condition)
    records, rejections = [], []
    def retain(identity, kind, value, raw=None):
        normal = value.to_dict()
        raw = normal if raw is None else raw
        imported = PARSERS[kind].from_dict(raw)
        require(encoded(imported.to_dict()) == encoded(normal), "Bad positive normalization " + identity)
        records.append(dict(id=identity,kind=kind,input=raw,normalized=normal,fingerprint=fingerprint(normal)))
        return normal
    def reject(identity, kind, raw, code, stage="record"):
        try: PARSERS[kind].from_dict(raw)
        except SerializationError as error: message = str(error)
        else: raise AssertionError("Python accepted mutation " + identity)
        rejections.append(dict(id=identity,kind=kind,input=raw,expected_code=code,expected_stage=stage,python_error=message))
    def mutate(identity, base, key, value, code, stage="record"):
        row=next(item for item in records if item["id"]==base)
        raw=deepcopy(row["normalized"]); raw[key]=value
        reject(identity,row["kind"],raw,code,stage)
    retain("literal/canonical","canonical_edit",CanonicalBaseEdit(0,"A","G"))
    retain("literal/chemical","chemical_edit",ChemicalBaseEdit(1,"A",None,chem()))
    retain("literal/recoding","codon_recoding",recode())
    retain("literal/ordinary","translation_policy",TranslationPolicy("ordinary_cds"))
    retain("literal/inheritance","chemistry_transition",ChemistryTransition("exact_inheritance",None,(),p))
    retain("literal/features","feature_transition",FeatureTransition((),(),p))
    for position in (0,999999):
        for expected,replacement in product("ACGU",repeat=2):
            identity=f"canonical/{position}/{expected}/{replacement}"
            if expected==replacement:
                reject(identity,"canonical_edit",dict(LITERALS["literal/canonical"],position=position,expected=expected,replacement=replacement),"invalid_canonical_edit")
            else: retain(identity,"canonical_edit",CanonicalBaseEdit(position,expected,replacement))
    for accession,parent in (("inosine","A"),("pseudouridine","U"),("n1_methylpseudouridine","U")):
        for side in ("before","after"):
            for base in "ACGU":
                raw=dict(LITERALS["literal/chemical"],parent=base,before=None,after=None);raw[side]=chem(accession).to_dict()
                identity=f"chemical/{accession}/{side}/{base}"
                if base==parent: retain(identity,"chemical_edit",ChemicalBaseEdit.from_dict(raw))
                else: reject(identity,"chemical_edit",raw,"invalid_chemical_edit")
    retain("chemical/substitution","chemical_edit",ChemicalBaseEdit(999999,"U",chem("pseudouridine"),chem("n1_methylpseudouridine")))
    for label,identity in (("namespace",chem(namespace="fixture.chemical")),("version",chem(version="2")),("custom",chem("custom")),("unknown",chem("unknown","unknown","unknown"))):
        retain("chemical/unrecognized_"+label,"chemical_edit",ChemicalBaseEdit(0,"C",None,identity))
    for triplet in ("AUG","UAG","GGC"):
        for amino in "ACDEFGHIKLMNPQRSTVWYOU*":
            retain("recoding/"+triplet+"/"+amino,"codon_recoding",recode(triplet=triplet,amino=amino))
    retain("recoding/last_index","codon_recoding",recode(index=333332))
    retain("recoding/text_boundary","codon_recoding",recode(condition="é"*2048))
    policy=TranslationPolicy("conditional_cds",recodings=(recode(index=3,amino="O"),recode()))
    retain("policy/conditional","translation_policy",policy)
    raw=policy.to_dict();raw["recodings"].reverse()
    retain("policy/unsorted","translation_policy",policy,raw)
    destinations=("cap","start_end","finish_end","terminal_tail","modification_inventory","modification:source")
    for component in destinations:
        for decision in ("mapped_copy","declared_replacement","not_carried","unknown"):
            values=() if decision in ("not_carried","unknown") else (component,)
            retain("chemistry/"+component+"/"+decision,"chemistry_disposition",ChemistryDisposition("source",component,decision,values,p))
    retained=ChemistryDisposition("source","cap","unknown",tuple(reversed(destinations)),p)
    raw=retained.to_dict();raw["destination_components"].reverse()
    retain("chemistry/destination_normalization","chemistry_disposition",retained,raw)
    retain("chemistry/selector_boundary","chemistry_disposition",ChemistryDisposition("source","modification:"+"a"*4096,"mapped_copy",("cap",),p))
    dispositions=(ChemistryDisposition("z","cap","declared_replacement",("cap",),p),ChemistryDisposition("a","cap","unknown",(),p))
    transition=ChemistryTransition("explicit_output",fixture_chemistry(),dispositions,p)
    retain("chemistry/explicit","chemistry_transition",transition)
    raw=transition.to_dict();raw["dispositions"].reverse()
    retain("chemistry/order_normalization","chemistry_transition",transition,raw)
    retain("chemistry/explicit_empty","chemistry_transition",replace(transition,dispositions=()))
    outputs=(feature("a"),feature("z",2,4))
    for decision,items in (("exact",outputs[:1]),("partial",outputs[:1]),("split",outputs),("not_carried",()),("outside_selection",()),("unknown",()),("unknown_outputs",outputs)):
        retain("feature/"+decision,"feature_disposition",FeatureDisposition("source","annotation",decision.split("_")[0] if decision=="unknown_outputs" else decision,items,p))
    mapped=FeatureDisposition("source","annotation","split",tuple(reversed(outputs)),p)
    raw=mapped.to_dict();raw["outputs"].reverse()
    retain("feature/output_normalization","feature_disposition",mapped,raw)
    all_features=FeatureTransition((FeatureDisposition("z","old","not_carried",(),p),mapped),(feature("new"),),p)
    retain("feature/transition","feature_transition",all_features)
    raw=all_features.to_dict();raw["dispositions"].reverse()
    retain("feature/transition_normalization","feature_transition",all_features,raw)
    for kind in PARSERS:
        row=next(item for item in records if item["kind"]==kind)
        for key in row["normalized"]:
            raw=deepcopy(row["normalized"]);del raw[key]
            reject("fields/"+kind+"/missing/"+key,kind,raw,"missing_field")
        mutate("fields/"+kind+"/extra",row["id"],"verified",True,"unknown_field")
        mutate("fields/"+kind+"/schema",row["id"],"schema_version","future","unsupported_schema")
    for kind,base,key,limit in (("canonical_edit","literal/canonical","position",1000000),("chemical_edit","literal/chemical","position",1000000),("codon_recoding","literal/recoding","codon_index",333333)):
        for i,value in enumerate((-1,True,False,0.0,None,"1",limit,1<<200)):
            mutate(f"index/{kind}/{i}",base,key,value,"invalid_type" if type(value) is not int else "invalid_molecular_index")
    for i,value in enumerate(("T","I","N","a","AU",""," A","A\n",None,1,["A"])):
        for base,key,code in (("literal/canonical","expected","invalid_canonical_edit"),("literal/canonical","replacement","invalid_canonical_edit"),("literal/chemical","parent","invalid_chemical_edit")):
            mutate(f"symbol/{key}/{i}",base,key,value,code if isinstance(value,str) else "invalid_type")
    mutate("chemical/noop_null","literal/chemical","after",None,"invalid_chemical_edit")
    mutate("chemical/noop_identity","literal/chemical","before",chem().to_dict(),"invalid_chemical_edit")
    for i,value in enumerate(("ATG","AIG","NNN","aug","AU","AUGA"," AUG","AUG\n",None,1)):
        code="invalid_type" if not isinstance(value,str) else "invalid_molecular_text" if len(value)>3 else "invalid_codon_recoding"
        mutate(f"triplet/{i}","literal/recoding","expected_triplet",value,code)
    for i,value in enumerate(("X","B","J","Z","m","Met","UO","",None,1)):
        mutate(f"amino/{i}","literal/recoding","amino_acid",value,"invalid_codon_recoding" if isinstance(value,str) else "invalid_type")
    for i,value in enumerate((""," "," condition","condition ","line\nline","bad\x7f","a"*4097,"é"*2049,None)):
        mutate(f"condition/{i}","literal/recoding","condition",value,"invalid_molecular_text" if isinstance(value,str) else "invalid_type")
    mutate("policy/unknown","literal/ordinary","profile","infer_cds","invalid_translation_policy")
    mutate("policy/code","literal/ordinary","genetic_code","mitochondrial","invalid_translation_policy")
    mutate("policy/code_type","literal/ordinary","genetic_code",1,"invalid_type")
    mutate("policy/missing_recodings","literal/ordinary","profile","conditional_cds","invalid_translation_policy")
    mutate("policy/ordinary_recodings","literal/ordinary","recodings",[recode().to_dict()],"invalid_translation_policy")
    mutate("policy/duplicate","policy/conditional","recodings",[recode().to_dict(),recode(amino="O").to_dict()],"invalid_translation_policy")
    for i,component in enumerate(("missing","modification:","modification: invalid","modification:"+"a"*4097)):
        mutate(f"component/{i}","chemistry/cap/mapped_copy","component",component,"invalid_chemistry_disposition" if i==0 else "invalid_molecular_text")
    mutate("chemistry/source_text","chemistry/cap/mapped_copy","source_id","bad\x7f","invalid_molecular_text")
    mutate("chemistry/decision","chemistry/cap/mapped_copy","decision","preserve_maybe","invalid_chemistry_disposition")
    mutate("chemistry/duplicate_destinations","chemistry/cap/mapped_copy","destination_components",["cap","cap"],"invalid_chemistry_disposition")
    mutate("chemistry/not_carried_destinations","chemistry/cap/mapped_copy","decision","not_carried","invalid_chemistry_disposition")
    mutate("chemistry/missing_destinations","chemistry/cap/mapped_copy","destination_components",[],"invalid_chemistry_disposition")
    mutate("chemistry/explicit_missing","literal/inheritance","mode","explicit_output","invalid_chemistry_transition")
    mutate("chemistry/inheritance_override","chemistry/explicit_empty","mode","exact_inheritance","invalid_chemistry_transition")
    mutate("chemistry/inheritance_dispositions","literal/inheritance","dispositions",[dispositions[0].to_dict()],"invalid_chemistry_transition")
    mutate("chemistry/duplicate_source","chemistry/explicit","dispositions",[dispositions[0].to_dict()]*2,"invalid_chemistry_transition")
    mutate("chemistry/mode","literal/inheritance","mode","inferred","invalid_chemistry_transition")
    for identity,base,key,value,code in (
        ("feature/exact_empty","feature/exact","outputs",[],"invalid_feature_disposition"),
        ("feature/partial_empty","feature/partial","outputs",[],"invalid_feature_disposition"),
        ("feature/split_one","feature/split","outputs",[outputs[0].to_dict()],"invalid_feature_disposition"),
        ("feature/dropped_output","feature/exact","decision","not_carried","invalid_feature_disposition"),
        ("feature/outside_output","feature/exact","decision","outside_selection","invalid_feature_disposition"),
        ("feature/decision","feature/exact","decision","inferred","invalid_feature_disposition"),
        ("feature/duplicate_output","feature/split","outputs",[outputs[0].to_dict()]*2,"invalid_feature_transition"),
        ("feature/duplicate_source","feature/transition","dispositions",[mapped.to_dict()]*2,"invalid_feature_transition"),
        ("feature/duplicate_added","literal/features","added",[outputs[0].to_dict()]*2,"invalid_feature_transition"),
        ("feature/cross_output","feature/transition","added",[outputs[0].to_dict()],"invalid_feature_transition")):
        mutate(identity,base,key,value,code)
    literal_expectations=[dict(id=identity,normalized=value) for identity,value in LITERALS.items()]
    coverage=dict(kinds=sorted(PARSERS),positive_count=len(records),rejection_count=len(rejections),independent_literal_count=len(LITERALS),
                  positive_by_kind=dict(sorted(Counter(item["kind"] for item in records).items())),codon_count=64)
    return dict(schema_version=SCHEMA,claim_scope="Complete declared leaf structure only; source-bound edits, translation, transitions and biological effect are not checked.",
                records=records,rejections=rejections,literal_expectations=literal_expectations,
                codon_table=dict(STANDARD_RNA_CODON_TABLE),coverage=coverage)

def inventories(corpus):
    return {
      "positive":fingerprint(sorted([[item["id"],item["kind"]] for item in corpus["records"]])),
      "negative":fingerprint(sorted([[item["id"],item["kind"],item["expected_stage"],item["expected_code"]] for item in corpus["rejections"]])),
      "literals":fingerprint(corpus["literal_expectations"]),
    }

def check_corpus(corpus):
    require(corpus["schema_version"]==SCHEMA,"Unknown transition corpus")
    ids=[item["id"] for key in ("records","rejections") for item in corpus[key]]
    require(len(ids)==len(set(ids)),"Duplicate transition case identity")
    coverage=corpus["coverage"]
    require(coverage["kinds"]==sorted(PARSERS),"Missing declared family")
    require(coverage["positive_count"]==len(corpus["records"]) and coverage["rejection_count"]==len(corpus["rejections"]),"Incorrect case census")
    require(coverage["positive_by_kind"]==dict(Counter(item["kind"] for item in corpus["records"])),"Wrong family census")
    indexed={}
    for item in corpus["records"]:
        value=PARSERS[item["kind"]].from_dict(item["input"]).to_dict()
        require(encoded(value)==encoded(item["normalized"]),"Normalized declaration drift")
        require(fingerprint(value)==item["fingerprint"],"Declaration identity drift")
        indexed[item["id"]]=value
    for item in corpus["rejections"]:
        try: PARSERS[item["kind"]].from_dict(item["input"])
        except SerializationError as error: require(str(error)==item["python_error"],"Intended Python rejection changed")
        else: raise AssertionError("Intended declaration rejection accepted")
    require(corpus["literal_expectations"]==[dict(id=key,normalized=value) for key,value in LITERALS.items()],"Missing independent complete literals")
    require(inventories(corpus)==INVENTORIES,"Required case inventory or intended diagnostic changed")
    for item in corpus["literal_expectations"]: require(encoded(indexed[item["id"]])==encoded(item["normalized"]),"Independent literal differs")
    # Alternative codon ordering and independently specified amino-acid rows.
    expected={a+b+c:aa for a,row in zip("ACGU",("KNKNTTTTRSRSIIMI","QHQHPPPPRRRRLLLL","EDEDAAAAGGGGVVVV","*Y*YSSSS*CWCLFLF"),strict=True)
              for (b,c),aa in zip(product("ACGU",repeat=2),row,strict=True)}
    require(corpus["codon_table"]==expected,"Independent standard codon table differs")
    pending=[(corpus,0)];count=0
    while pending:
        value,depth=pending.pop();count+=1
        require(count<=250000 and depth<=128,"Corpus exceeds native JSON budget")
        if isinstance(value,dict): pending.extend((x,depth+1) for pair in value.items() for x in pair)
        elif isinstance(value,list):pending.extend((x,depth+1) for x in value)
    require(len(encoded(corpus))<=16*1024*1024,"Corpus exceeds native byte budget")
    return dict(bytes=len(encoded(corpus)),nodes=count,**coverage,**inventories(corpus))

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write",action="store_true");parser.add_argument("--check",action="store_true")
    args=parser.parse_args(argv);value=build_corpus();usage=check_corpus(value);content=encoded(value)
    if args.write: CORPUS.write_bytes(content)
    else: require(CORPUS.read_bytes()==content,"Transition corpus drifted; inspect before --write")
    print(json.dumps(usage,sort_keys=True))
if __name__=="__main__":main()

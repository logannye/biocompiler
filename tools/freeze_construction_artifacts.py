"""Retain unchecked construction records, independent of fresh acceptance."""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys

from biocompiler.artifacts.circuit_construction import DerivedSegment, ConsumedSegment, ConstructedValue, ConstructionCandidate
from biocompiler.artifacts.circuit_molecules import ExperimentalAmount
from biocompiler.backends.circuit_construction import construct_circuit_candidate
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_construction import CircuitConstructionRequest
from biocompiler.ir.serialization import fingerprint
from biocompiler.semantics.molecule_coordinates import CoordinatePath, IndexSpan

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tests.test_circuit_construction_checking import fixture_request, translation_request
from tools.freeze_molecules import relocate, apply_edits

CORPUS = ROOT / "tests/conformance/construction-artifacts-v1.json"
SCHEMA = "biocompiler.construction_artifacts_conformance.v1"
KINDS = dict(derived=DerivedSegment, consumed=ConsumedSegment, value=ConstructedValue, candidate=ConstructionCandidate)
EXPECTED_INVENTORY = "f5af9ec95ba99e66827a374fa46b11dadc20104dba839374eedde4dca286ece4"
EXPECTED_SECTIONS = {
    "literal_expectations": "eb0bc157ec497c183cb98fa6b169c1b31b317c3c98a99c8771d7f278eae36fdb",
    "runtime_cases": "2cd4fea219e92734cd2824a6218174fe420a6ecd6a824decbf510465a923b7bb",
    "relations": "2c1bfe7a50f011f8c3c02d792d689116e7608acc0a5d47d3802885c162116bd5",
}
LITERAL_PROVENANCE = {"schema_version":"biocompiler.molecular_declaration_provenance.v0.1","status":"unknown","authority":[],"locator":None,"reason":"Artificial unchecked record."}
LITERAL_CLAIM = {"schema_version":"biocompiler.chemistry_claim.v0.1","status":"unknown","identity":None,"provenance":LITERAL_PROVENANCE}
LITERAL_PATH = {"schema_version":"biocompiler.molecule_coordinate_path.v0.1","space_id":"unbound.source","spans":[{"schema_version":"biocompiler.molecule_index_span.v0.1","start":0,"end":1}],"strand":"+"}
LITERAL_DERIVED = {"schema_version":"biocompiler.circuit_derived_segment.v0.1","destination":{"schema_version":"biocompiler.molecule_index_span.v0.1","start":0,"end":1},"source_id":"unbound","source_path":LITERAL_PATH,"rule":"copy"}
LITERAL_VALUE = {"schema_version":"biocompiler.circuit_constructed_value.v0.1","id":"literal","space":{"schema_version":"biocompiler.molecule_coordinate_space.v0.1","id":"literal.space","alphabet":"RNA","length":1,"topology":"linear","axis":"5prime_to_3prime"},"sequence":"A",
    "chemistry":{"schema_version":"biocompiler.molecule_chemistry.v0.1","cap":LITERAL_CLAIM,"start_end":LITERAL_CLAIM,"finish_end":LITERAL_CLAIM,"modifications":[],"modification_inventory_status":"unknown","modification_inventory_provenance":LITERAL_PROVENANCE,
       "terminal_tail":{"schema_version":"biocompiler.tail_declaration.v0.1","status":"unknown","placement":None,"length":None,"path":None,"provenance":LITERAL_PROVENANCE}},
    "features":[],"segments":[LITERAL_DERIVED],"step_id":"unbound.step","sequence_extent":"complete","consumed":[]}
LITERALS = {
    "literal/derived": LITERAL_DERIVED,
    "literal/value": LITERAL_VALUE,
    "literal/consumed": {"schema_version":"biocompiler.circuit_consumed_segment.v0.1","source_id":"unbound","source_path":dict(LITERAL_PATH,spans=[{"schema_version":"biocompiler.molecule_index_span.v0.1","start":1,"end":4}]),"reason":"terminal_stop"},
    "literal/candidate": {"schema_version":"biocompiler.circuit_construction_candidate.v0.1","request_fingerprint":"0"*64,"values":[],"bundle":None,"missing_members":[],"diagnostics":[],"experimental_amounts":[]},
}


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()


def inventory(corpus):
    return fingerprint({"records": sorted([x["id"], x["kind"]] for x in corpus["records"]),
                        "rejections": sorted([x["id"], x["kind"], x["expected_code"]] for x in corpus["rejections"])})

def runtime_candidate(lengths):
    values=[]
    for index,length in enumerate(lengths):
        raw=deepcopy(LITERAL_VALUE)
        raw["id"]="value_"+str(index);raw["space"].update(id="space_"+str(index),length=length);raw["sequence"]="A"*length
        raw["segments"][0]["destination"]["end"]=length
        raw["segments"][0]["source_path"]["spans"][0]["end"]=length
        values.append(ConstructedValue.from_dict(raw))
    return ConstructionCandidate("0"*64,tuple(values),None,(),())


def build_corpus():
    records, rejections, documents = [], [], {}
    objects = {}

    def retain(identity, kind, value, edits=()):
        raw = value.to_dict() if hasattr(value, "to_dict") else value
        actual = KINDS[kind].from_dict(raw)
        normalized = actual.to_dict()
        key = fingerprint(normalized); documents[key] = normalized
        assert encoded(KINDS[kind].from_dict(apply_edits(normalized, edits)).to_dict()) == encoded(normalized)
        records.append(dict(id=identity, kind=kind, document_id=key, edits=list(edits), fingerprint=actual.fingerprint))
        objects[identity] = actual
        return actual

    def reject(identity, base, edits, code="invalid_construction_artifact"):
        case = next(x for x in records if x["id"] == base)
        raw = apply_edits(documents[case["document_id"]], edits)
        try:
            KINDS[case["kind"]].from_dict(raw)
        except SerializationError:
            pass
        else:
            raise AssertionError("Accepted intended candidate rejection: " + identity)
        rejections.append(dict(id=identity, kind=case["kind"], document_id=case["document_id"], edits=edits, expected_code=code))

    def edit(path, value):
        return dict(op="set", path=path, value=value)

    def produce(request):
        return construct_circuit_candidate(CircuitConstructionRequest.from_dict(relocate(request.to_dict())))

    base = retain("candidate/base", "candidate", produce(fixture_request(helper=True)))
    translated = retain("candidate/translation", "candidate", produce(translation_request()))
    value = retain("value/base", "value", base.values[0])
    retain("value/translation", "value", translated.values[0])
    derived = retain("derived/base", "derived", value.segments[0])
    consumed = retain("consumed/base", "consumed", translated.values[0].consumed[0])
    for rule in ("copy", "complement", "dna_coding_to_rna.v1", "rna_editing.v1", "translation_codon.v1"):
        retain("derived/rule/" + rule, "derived", DerivedSegment(IndexSpan(0, 2), "source",
            CoordinatePath("source.space", (IndexSpan(0, 6 if rule == "translation_codon.v1" else 2),), "+"), rule))
    retain("derived/reverse", "derived", replace(derived, source_path=replace(derived.source_path, strand="-")))
    retain("consumed/split", "consumed", replace(consumed, source_path=CoordinatePath("source.space", (IndexSpan(1, 2), IndexSpan(4, 6)), "+")))
    retain("candidate/empty", "candidate", ConstructionCandidate("0" * 64, (), None, (), ()))
    retain("candidate/unresolved", "candidate", ConstructionCandidate("0" * 64, (), None, ("z", "a"), ("unknown:z", "unknown:a")))
    retain("candidate/maximum_diagnostic", "candidate", ConstructionCandidate("0" * 64, (), None, (), ("x" * 16384,)))
    retain("candidate/unbound_value", "candidate", replace(base, bundle=None))
    retain("value/changed_sequence_unchecked", "value", replace(value, sequence="ACGAAC"))
    retain("value/changed_source_unchecked", "value", replace(value, segments=(replace(derived, source_id="not_authority"),)))
    retain("value/split_partition", "value", replace(value, segments=(
        DerivedSegment(IndexSpan(0, 2), "root", CoordinatePath("source.space", (IndexSpan(0, 2),), "+"), "copy"),
        DerivedSegment(IndexSpan(2, 6), "root", CoordinatePath("source.space", (IndexSpan(2, 6),), "+"), "copy"))))
    twice = replace(translated.values[0], consumed=(consumed, replace(consumed, source_id="other")))
    retain("value/ordered_consumption", "value", twice)
    retain("value/reversed_consumption", "value", replace(twice, consumed=tuple(reversed(twice.consumed))))
    for identity,raw in LITERALS.items():
        retain(identity,identity.split("/")[1],raw)
    payload=next(item for item in base.bundle.molecules if item.id=="payload")
    helper=next(item for item in base.bundle.molecules if item.id=="helper")
    amount=ExperimentalAmount("amount",payload.id,payload.fingerprint,"preparation",("payload_role",),1,"fixture_unit",payload.provenance)
    retain("candidate/amount","candidate",replace(base,experimental_amounts=(amount,)))
    retain("candidate/amount_float","candidate",replace(base,experimental_amounts=(replace(amount,quantity=1.0),)))
    retain("candidate/amount_unknown","candidate",replace(base,experimental_amounts=(replace(amount,quantity=None),)))
    alias_amount=ExperimentalAmount("second_amount",helper.id,helper.fingerprint,"separate",("helper_role",),None,"fixture_unit",helper.provenance)
    retain("candidate/alias_preparations","candidate",replace(base,experimental_amounts=(amount,alias_amount)))
    normalized=objects["candidate/unresolved"].to_dict()
    retain("candidate/text_normalization","candidate",objects["candidate/unresolved"],edits=[edit(["missing_members"],list(reversed(normalized["missing_members"]))),edit(["diagnostics"],list(reversed(normalized["diagnostics"])) )])
    ordered_values=replace(base,bundle=None,values=(value,replace(ConstructedValue.from_dict(LITERAL_VALUE),id="another")))
    retain("candidate/ordered_values","candidate",ordered_values)
    retain("candidate/value_normalization","candidate",ordered_values,edits=[edit(["values"],list(reversed(ordered_values.to_dict()["values"])) )])
    for variant in ("base", "parameter-default", "parameter-override"):
        original = json.loads((ROOT / f"tests/conformance/case-b/{variant}/candidate.json").read_bytes())
        retain("case_b/" + variant, "candidate", original["construction"]["candidate"])

    for kind in KINDS:
        base_id = kind + "/base"
        original = objects[base_id].to_dict()
        for key in original:
            reject(f"{kind}/missing/{key}", base_id, [dict(op="remove", path=[key])], "missing_field")
        reject(kind + "/extra", base_id, [edit(["accepted"], True)], "unknown_field")
        reject(kind + "/future", base_id, [edit(["schema_version"], "future")], "unsupported_schema")
    for name, base_id, path, changed, code in (
        ("derived/rule_unknown", "derived/base", ["rule"], "implicit", "invalid_construction_artifact"),
        ("derived/cardinality", "derived/base", ["destination", "end"], 5, "invalid_construction_artifact"),
        ("derived/empty", "derived/base", ["destination", "end"], 0, "invalid_construction_artifact"),
        ("derived/bool_rule", "derived/base", ["rule"], True, "invalid_type"),
        ("derived/source_trim", "derived/base", ["source_id"], " root", "invalid_molecular_text"),
        ("consumed/reverse", "consumed/base", ["source_path", "strand"], "-", "invalid_construction_artifact"),
        ("consumed/reason", "consumed/base", ["reason"], "dose", "invalid_construction_artifact"),
        ("consumed/length", "consumed/base", ["source_path", "spans", 0, "end"], consumed.source_path.spans[0].end-1, "invalid_construction_artifact"),
        ("value/wrong_alphabet", "value/base", ["sequence"], "ACGTAC", "invalid_construction_artifact"),
        ("value/short_sequence", "value/base", ["sequence"], "ACGUA", "invalid_construction_artifact"),
        ("value/empty_sequence", "value/base", ["sequence"], "", "invalid_construction_artifact"),
        ("value/unknown_extent", "value/base", ["sequence_extent"], "unknown", "invalid_construction_artifact"),
        ("value/empty_segments", "value/base", ["segments"], [], "invalid_construction_artifact"),
        ("value/too_many_segments", "value/base", ["segments"], [derived.to_dict()] * 129, "molecular_resource_limit"),
        ("value/duplicate_consumed", "value/base", ["consumed"], [consumed.to_dict()] * 2, "invalid_construction_artifact"),
        ("value/too_many_consumed", "value/base", ["consumed"], [consumed.to_dict()] * 17, "molecular_resource_limit"),
        ("value/step_blank", "value/base", ["step_id"], "", "invalid_molecular_text"),
        ("candidate/hash_upper", "candidate/base", ["request_fingerprint"], "A" * 64, "invalid_construction_artifact"),
        ("candidate/duplicate_values", "candidate/base", ["values"], [value.to_dict()] * 2, "invalid_construction_artifact"),
        ("candidate/too_many_values", "candidate/base", ["values"], [value.to_dict()] * 257, "molecular_resource_limit"),
        ("candidate/duplicate_missing", "candidate/base", ["missing_members"], ["a", "a"], "invalid_construction_artifact"),
        ("candidate/too_many_missing", "candidate/base", ["missing_members"], [str(i) for i in range(257)], "molecular_resource_limit"),
        ("candidate/duplicate_diagnostics", "candidate/base", ["diagnostics"], ["a", "a"], "invalid_construction_artifact"),
        ("candidate/long_diagnostic", "candidate/base", ["diagnostics"], ["x" * 16385], "invalid_molecular_text"),
        ("candidate/too_many_diagnostics", "candidate/base", ["diagnostics"], [str(i) for i in range(1025)], "molecular_resource_limit"),
    ):
        reject(name, base_id, [edit(path, changed)], code)
    reject("value/partition_gap", "value/split_partition", [edit(["segments", 1, "destination", "start"], 3),
        edit(["segments", 1, "source_path", "spans", 0, "start"], 3)])
    split=objects["value/split_partition"]
    reject("value/partition_order","value/split_partition",[edit(["segments"],list(reversed(split.to_dict()["segments"])))])
    reject("candidate/duplicate_frames", "candidate/base", [edit(["values"], [value.to_dict(), value.to_dict() | {"id": "other"}])])
    reject("candidate/amount_without_bundle","candidate/amount",[edit(["bundle"],None)])
    reject("candidate/duplicate_amount_identity","candidate/amount",[edit(["experimental_amounts"],[amount.to_dict()]*2)])
    for label,key,replacement in (("stale","subject_fingerprint","f"*64),("missing_subject","subject_id","missing"),("wrong_role","role_instance_ids",["helper_role"]),("missing_role","role_instance_ids",["missing"])):
        reject("candidate/amount_"+label,"candidate/amount",[edit(["experimental_amounts",0,key],replacement)],"invalid_molecule_artifact")
    reject("candidate/alias_preparation","candidate/alias_preparations",[edit(["experimental_amounts",1,"preparation_id"],"preparation")],"invalid_molecule_artifact")
    reject("candidate/short_hash","candidate/base",[edit(["request_fingerprint"],"a"*63)])
    runtime=[]
    for identity,lengths,code in (("cumulative/exact",[500000,500000],None),("cumulative/overflow",[500000,500001],"invalid_construction_artifact")):
        if code is None:
            candidate=runtime_candidate(lengths); digest=candidate.fingerprint
        else:
            try: runtime_candidate(lengths)
            except SerializationError: digest=None
            else: raise AssertionError("Cumulative residue bound accepted")
        runtime.append(dict(id=identity,lengths=lengths,expected_code=code,fingerprint=digest))
    result = dict(schema_version=SCHEMA, claim_scope="unchecked candidate structure only; no independent construction acceptance",
                  records=records, rejections=rejections, documents=documents,
                  literal_expectations=[dict(id=key,normalized=value) for key,value in LITERALS.items()],runtime_cases=runtime,
                  relations=[dict(left="value/ordered_consumption",right="value/reversed_consumption",equal=False),
                             dict(left="candidate/ordered_values",right="candidate/value_normalization",equal=True),
                             dict(left="candidate/unresolved",right="candidate/text_normalization",equal=True),
                             dict(left="candidate/amount",right="candidate/amount_float",equal=False)])
    result["inventory_sha256"] = inventory(result)
    return result


def check_corpus(corpus):
    assert corpus["schema_version"] == SCHEMA
    ids = [x["id"] for key in ("records", "rejections") for x in corpus[key]]
    assert len(ids) == len(set(ids)), "Duplicate artifact case"
    assert corpus["inventory_sha256"] == inventory(corpus) == EXPECTED_INVENTORY, "Changed artifact inventory or intended diagnostic"
    for key, expected in EXPECTED_SECTIONS.items():
        assert fingerprint(corpus[key]) == expected, "Changed independent artifact " + key
    for key, document in corpus["documents"].items():
        assert fingerprint(document) == key, "Changed artifact document pin"
    for case in corpus["records"]:
        doc = corpus["documents"][case["document_id"]]
        actual = KINDS[case["kind"]].from_dict(apply_edits(doc, case["edits"]))
        assert encoded(actual.to_dict()) == encoded(doc), "Changed artifact normalization"
        assert actual.fingerprint == case["fingerprint"], "Changed artifact fingerprint"
    for case in corpus["rejections"]:
        doc = corpus["documents"][case["document_id"]]
        try:
            KINDS[case["kind"]].from_dict(apply_edits(doc, case["edits"]))
        except SerializationError:
            continue
        raise AssertionError("Accepted intended rejection: " + case["id"])
    indexed={item["id"]:item for item in corpus["records"]}
    assert corpus["literal_expectations"]==[dict(id=key,normalized=value) for key,value in LITERALS.items()],"Independent literal inventory changed"
    for item in corpus["literal_expectations"]:
        assert encoded(corpus["documents"][indexed[item["id"]]["document_id"]])==encoded(item["normalized"]),"Independent literal changed"
    for relation in corpus["relations"]:
        assert (indexed[relation["left"]]["fingerprint"]==indexed[relation["right"]]["fingerprint"]) is relation["equal"],"Candidate identity relation changed"
    assert len(corpus["runtime_cases"])==2,"Missing runtime residue boundary"
    for item in corpus["runtime_cases"]:
        try: candidate=runtime_candidate(item["lengths"])
        except SerializationError:
            assert item["expected_code"]=="invalid_construction_artifact" and item["fingerprint"] is None
        else:
            assert item["expected_code"] is None and candidate.fingerprint==item["fingerprint"],"Runtime boundary identity changed"
    pending=[(corpus,0)];nodes=0;maximum_depth=0
    while pending:
        value,depth=pending.pop();nodes+=1;maximum_depth=max(maximum_depth,depth)
        assert nodes<=250000 and depth<=128,"Whole artifact corpus exceeds native JSON budget"
        if isinstance(value,dict):pending.extend((item,depth+1) for pair in value.items() for item in pair)
        elif isinstance(value,list):pending.extend((item,depth+1) for item in value)
        elif isinstance(value,str):assert len(value.encode())<=4*1024*1024,"Artifact corpus string limit"
    assert len(encoded(corpus))<=16*1024*1024,"Artifact corpus byte limit"
    assert b"/Users/" not in encoded(corpus),"Absolute checkout path in artifact corpus"
    return dict(bytes=len(encoded(corpus)),nodes=nodes,depth=maximum_depth)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--write", action="store_true")
    args = parser.parse_args(); corpus = build_corpus(); check_corpus(corpus); data = encoded(corpus)
    if args.write:
        CORPUS.write_bytes(data)
    elif not CORPUS.is_file() or CORPUS.read_bytes() != data:
        raise SystemExit("Construction artifact corpus is stale; review before --write")
    print(json.dumps({"records": len(corpus["records"]), "rejections": len(corpus["rejections"]), "bytes": len(data),
                      "inventory_sha256": corpus["inventory_sha256"]}))


if __name__ == "__main__":
    main()

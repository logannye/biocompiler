"""Freeze artificial molecular declaration/chemistry conformance, without synthesis."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path

from biocompiler.errors import SerializationError
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.molecule_chemistry import ChemicalIdentity, ChemistryClaim, BaseModification, TailLength, TailDeclaration, MoleculeChemistry
from biocompiler.ir.molecule_records import DeclarationProvenance, _text, _bounded_tree
from biocompiler.semantics.molecule_coordinates import CoordinateSpace, CoordinatePath, IndexSpan

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/molecule-chemistry-v1.json"
SCHEMA = "biocompiler.molecule_chemistry_conformance.v1"
KINDS = {"provenance": DeclarationProvenance, "chemical_identity": ChemicalIdentity,
         "claim": ChemistryClaim, "modification": BaseModification, "tail_length": TailLength,
         "tail": TailDeclaration, "chemistry": MoleculeChemistry}


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()


def require(condition, message):
    if not condition: raise AssertionError(message)


def fixture_module():
    spec = importlib.util.spec_from_file_location("chemistry_authority_fixtures", ROOT / "tests/test_molecule_chemistry.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def build_corpus():
    f = fixture_module()
    records, rejections, validations = [], [], []

    def retain(identity, kind, value):
        raw = value.to_dict() if hasattr(value, "to_dict") else value
        result = KINDS[kind].from_dict(raw)
        records.append({"id": identity, "kind": kind, "input": raw, "normalized": result.to_dict(),
            "fingerprint": result.fingerprint,
            "nominal": result.nominal_dict() if hasattr(result, "nominal_dict") else None,
            "declared_nominal_complete": getattr(result, "declared_nominal_complete", None)})
        return result

    def reject(identity, kind, raw, code):
        try: KINDS[kind].from_dict(raw)
        except SerializationError: pass
        else: raise AssertionError("Accepted intended decoding rejection " + identity)
        rejections.append({"id": identity, "kind": kind, "input": raw, "expected_code": code})

    def validate(identity, chemistry_id, space=None, sequence="ACGUAAA", extent="complete", code=None):
        chemistry = next(item for item in records if item["id"] == chemistry_id)
        space = f.space(sequence) if space is None else space
        try: MoleculeChemistry.from_dict(chemistry["normalized"]).validate_for(space, sequence, extent)
        except SerializationError:
            require(code is not None, "Unexpected validation rejection " + identity)
        else: require(code is None, "Accepted intended chemistry rejection " + identity)
        validations.append({"id": identity, "chemistry_id": chemistry_id, "space": space.to_dict(),
            "sequence": sequence, "sequence_extent": extent, "expected_code": code})

    retain("unknown_provenance", "provenance", f.unknown_provenance())
    retain("declared_provenance", "provenance", f.declared_provenance())
    raw = f.declared_provenance().to_dict()
    raw["authority"] = [PinnedIdentity("source", "z", "1", "b" * 64).to_dict(), PinnedIdentity("evidence", "a", "2", "a" * 64).to_dict()]
    retain("sorted_provenance", "provenance", raw)
    for accession in ("inosine", "pseudouridine", "n1_methylpseudouridine", "custom", "unknown"):
        retain("identity_" + accession, "chemical_identity", f.chemical(accession))
    retain("identity_unicode", "chemical_identity", ChemicalIdentity("custom", "人工🧬", "v1"))
    for status in ("declared", "unknown", "inapplicable", "absent"):
        retain("claim_" + status, "claim", f.claim(status))
    retain("claim_unknown_identity", "claim", replace(f.claim(), identity=ChemicalIdentity("unknown", "hydroxyl", "1")))
    retain("modification_positions", "modification", f.modification(positions=(4, 0)))
    raw = f.modification(positions=(0, 4)).to_dict(); raw["positions"] = [4, 0]
    retain("modification_normalized_positions", "modification", raw)
    retain("modification_policy", "modification", f.modification(scope="all_matching_bases", positions=()))
    retain("modification_pseudouridine", "modification", f.modification(accession="pseudouridine", base="U", positions=(3,)))
    for name, length in (("zero", TailLength("exact", exact=0)), ("exact", TailLength("exact", exact=3)),
                         ("bounded", TailLength("bounded", lower=2, upper=4)), ("unknown", TailLength("unknown"))):
        retain("length_" + name, "tail_length", length)
    for status in ("declared", "unknown", "inapplicable"):
        retain("tail_" + status, "tail", f.no_tail(status))
    retain("tail_represented", "tail", f.exact_tail())
    retain("tail_appended_bounded", "tail", TailDeclaration("declared", "appended_terminal", TailLength("bounded", lower=1, upper=5), None, f.unknown_provenance()))
    retain("tail_appended_unknown", "tail", TailDeclaration("declared", "appended_terminal", TailLength("unknown"), None, f.unknown_provenance()))
    base = f.chemistry()
    retain("chemistry_plain", "chemistry", base)
    retain("chemistry_modified", "chemistry", f.chemistry(modifications=(f.modification(),), terminal_tail=f.exact_tail()))
    retain("chemistry_unknown_cap", "chemistry", f.chemistry(cap=f.claim("unknown")))
    retain("chemistry_unknown_inventory", "chemistry", f.chemistry(modifications=(f.modification(),), modification_inventory_status="unknown"))
    retain("chemistry_unknown_tail", "chemistry", f.chemistry(terminal_tail=f.no_tail("unknown")))
    retain("chemistry_unknown_identity", "chemistry", f.chemistry(start_end=replace(f.claim(), identity=f.chemical("unknown"))))
    retain("chemistry_circle", "chemistry", f.chemistry(cap=f.claim("inapplicable"), start_end=f.claim("inapplicable"), finish_end=f.claim("inapplicable"), terminal_tail=f.no_tail("inapplicable")))
    retain("chemistry_dna", "chemistry", f.chemistry(cap=f.claim("inapplicable"), terminal_tail=f.no_tail("inapplicable")))
    retain("chemistry_protein", "chemistry", f.chemistry(cap=f.claim("inapplicable"), terminal_tail=f.no_tail("inapplicable"), modification_inventory_status="inapplicable"))
    retain("chemistry_core", "chemistry", f.chemistry(terminal_tail=TailDeclaration("declared", "appended_terminal", TailLength("bounded", lower=1, upper=5), None, f.unknown_provenance())))
    retain("chemistry_declared_provenance", "chemistry", replace(base, modification_inventory_provenance=f.declared_provenance(), cap=replace(base.cap, provenance=f.declared_provenance())))
    retain("chemistry_modification_policy", "chemistry", f.chemistry(modifications=(f.modification(scope="all_matching_bases", positions=()),)))
    retain("chemistry_overlap_policy", "chemistry", f.chemistry(modifications=(f.modification(id="a"), f.modification(id="b", scope="all_matching_bases", positions=()))))
    retain("chemistry_overlap_sites", "chemistry", f.chemistry(modifications=(f.modification(id="a"), f.modification(id="b"))))
    retain("chemistry_wrong_parent", "chemistry", f.chemistry(modifications=(f.modification(positions=(1,)),)))
    retain("chemistry_outside_site", "chemistry", f.chemistry(modifications=(f.modification(positions=(7,)),)))
    retain("chemistry_wrong_tail_frame", "chemistry", f.chemistry(terminal_tail=f.exact_tail(f.space(id="other"))))
    retain("chemistry_shifted_tail", "chemistry", f.chemistry(terminal_tail=replace(f.exact_tail(), path=CoordinatePath("molecule-space", (IndexSpan(0, 3),), "+"))))
    raw = f.chemistry(modifications=(f.modification(id="a"), f.modification(id="z", accession="pseudouridine", base="U", positions=(3,)))).to_dict()
    raw["modifications"].reverse()
    retain("chemistry_sorted_occurrences", "chemistry", raw)

    for identity in ("plain", "modified", "unknown_cap", "unknown_inventory", "unknown_tail", "unknown_identity", "declared_provenance", "modification_policy", "sorted_occurrences"):
        validate("valid_" + identity, "chemistry_" + identity)
    validate("valid_circle", "chemistry_circle", space=f.space(topology="circular"))
    validate("valid_dna", "chemistry_dna", space=f.space("ACGT", alphabet="DNA"), sequence="ACGT")
    validate("valid_protein_UO", "chemistry_protein", space=f.space("MUO", alphabet="protein"), sequence="MUO")
    validate("valid_exact_core", "chemistry_core", extent="exact_core")
    for identity in ("overlap_policy", "overlap_sites", "wrong_parent", "outside_site", "shifted_tail"):
        validate("invalid_" + identity, "chemistry_" + identity, code="invalid_chemistry")
    validate("invalid_tail_frame", "chemistry_wrong_tail_frame", code="coordinate_space_mismatch")
    validate("invalid_tail_symbols", "chemistry_modified", sequence="ACGUACA", code="invalid_chemistry")
    validate("invalid_rna_alphabet", "chemistry_plain", sequence="ACGTAAA", code="invalid_chemistry")
    validate("invalid_length", "chemistry_plain", space=f.space("ACGU"), code="invalid_chemistry")
    validate("invalid_circle_ends", "chemistry_plain", space=f.space(topology="circular"), code="invalid_chemistry")
    validate("invalid_linear_circle_chemistry", "chemistry_circle", code="invalid_chemistry")
    validate("invalid_dna_rna_cap", "chemistry_plain", space=f.space("ACGT", alphabet="DNA"), sequence="ACGT", code="invalid_chemistry")
    validate("invalid_nucleotide_inventory", "chemistry_protein", space=f.space("ACGT", alphabet="DNA"), sequence="ACGT", code="invalid_chemistry")
    validate("invalid_protein_modification", "chemistry_modified", space=f.space("MUO", alphabet="protein"), sequence="MUO", code="invalid_chemistry")
    validate("invalid_complete_appended", "chemistry_core", code="invalid_chemistry")
    validate("invalid_core_without_appended", "chemistry_plain", extent="exact_core", code="invalid_chemistry")

    representatives = {kind: next(item for item in records if item["kind"] == kind) for kind in KINDS}
    for kind, item in representatives.items():
        for key in item["normalized"]:
            raw = deepcopy(item["normalized"]); del raw[key]
            reject(kind + "_missing_" + key, kind, raw, "missing_field")
        reject(kind + "_unknown_field", kind, {**item["normalized"], "extra": 1}, "unknown_field")
        reject(kind + "_wrong_schema", kind, {**item["normalized"], "schema_version": "future"}, "unsupported_schema")

    def mutate(identity, source, field, value, code="invalid_chemistry"):
        item = next(item for item in records if item["id"] == source)
        raw = deepcopy(item["normalized"]); raw[field] = value
        reject(identity, item["kind"], raw, code)
    for value in (True, 1.0, -1, 1000001):
        mutate("length_value_" + repr(value), "length_exact", "exact", value,
               "invalid_type" if type(value) in (bool, float) else "invalid_molecular_index")
    mutate("length_reversed", "length_bounded", "upper", 1)
    mutate("length_unknown_number", "length_unknown", "exact", 1)
    mutate("claim_declared_without_identity", "claim_declared", "identity", None)
    mutate("claim_unknown_with_identity", "claim_unknown", "identity", f.chemical("inosine").to_dict())
    mutate("tail_absent_status", "tail_declared", "status", "absent")
    mutate("tail_unknown_with_length", "tail_unknown", "length", TailLength("exact", exact=1).to_dict())
    mutate("tail_represented_without_path", "tail_represented", "path", None)
    mutate("modification_duplicate_sites", "modification_positions", "positions", [0, 0])
    mutate("modification_empty_sites", "modification_positions", "positions", [])
    mutate("modification_policy_with_sites", "modification_policy", "positions", [0])
    mutate("modification_wrong_builtin_parent", "modification_positions", "canonical_base", "G")
    mutate("modification_site_boolean", "modification_positions", "positions", [True], "invalid_type")
    mutate("modification_site_excessive", "modification_positions", "positions", [1000000], "invalid_molecular_index")
    mutate("modification_inventory_duplicate", "chemistry_modified", "modifications", [f.modification().to_dict()] * 2)
    mutate("modification_inventory_inapplicable", "chemistry_modified", "modification_inventory_status", "inapplicable")
    mutate("modification_inventory_absent", "chemistry_plain", "modification_inventory_status", "absent")
    mutate("provenance_unknown_with_pin", "unknown_provenance", "authority", f.declared_provenance().to_dict()["authority"], "invalid_molecular_provenance")
    mutate("provenance_declared_without_pin", "declared_provenance", "authority", [], "invalid_molecular_provenance")
    mutate("provenance_wrong_pin_kind", "declared_provenance", "authority", [PinnedIdentity("model", "fixture", "1", "a" * 64).to_dict()], "invalid_molecular_provenance")
    mutate("provenance_duplicate_pin", "declared_provenance", "authority", f.declared_provenance().to_dict()["authority"] * 2, "invalid_molecular_provenance")
    for value in ("", " bad", "bad\u2003", "bad\nname", "bad\x7fname"):
        mutate("identity_invalid_text_" + str(len(rejections)), "identity_custom", "accession", value, "invalid_molecular_text")
    text_cases = []
    for value, maximum in (("plain",4096),("人工🧬",4096),("inner\u2003space",4096),("\u2003bad",4096),("bad\x7f",4096),("a"*8,8),("é"*4,8),("é"*5,8),("\u0085bad",4096),(True,4096)):
        try: _text(value, "Fixture", maximum)
        except SerializationError: accepted=False
        else: accepted=True
        text_cases.append({"value":value,"maximum":maximum,"accepted":accepted})
    pretty_cases = [{"document": value, "indent": indent,
                     "bytes": len(json.dumps(value,sort_keys=True,indent=indent,ensure_ascii=False,allow_nan=False).encode())}
                    for value in ({}, [], {"α": ["\n", "🧬", True, None, 1, -0.0]}, [[],{},["a",{"x":2}]], {"x":"\u001f\b\f\t\r\n\\\""})
                    for indent in (None,*range(9))]
    document = {"schema_version":SCHEMA,"claim_scope":"Nominal chemistry and coordinate consistency only; no transformation, evidence validation or biological acceptance.",
                "records":records,"rejections":rejections,"validations":validations,"text_cases":text_cases,"pretty_cases":pretty_cases}
    document["coverage"] = census(document)
    return document


def census(document):
    return {"kinds":sorted({item["kind"] for item in document["records"]}),
            "records":len(document["records"]),"rejections":len(document["rejections"]),
            "validations":len(document["validations"]),"text_cases":len(document["text_cases"]),
            "pretty_cases":len(document["pretty_cases"])}


def check_corpus(document):
    require(document["schema_version"]==SCHEMA,"Wrong chemistry corpus schema")
    ids=[item["id"] for field in ("records","rejections","validations") for item in document[field]]
    require(len(ids)==len(set(ids)),"Duplicate chemistry case identity")
    records={}
    for item in document["records"]:
        record=KINDS[item["kind"]].from_dict(item["input"]);records[item["id"]]=record
        require(encoded(record.to_dict())==encoded(item["normalized"]),"Chemistry normalization differs")
        require(record.fingerprint==item["fingerprint"],"Chemistry fingerprint differs")
        require(encoded(record.nominal_dict() if hasattr(record,"nominal_dict") else None)==encoded(item["nominal"]),"Chemistry nominal content differs")
        require(getattr(record,"declared_nominal_complete",None)==item["declared_nominal_complete"],"Chemistry completeness differs")
    for item in document["rejections"]:
        try:KINDS[item["kind"]].from_dict(item["input"])
        except SerializationError:pass
        else:raise AssertionError("Accepted intended chemistry decode rejection")
    for item in document["validations"]:
        try:records[item["chemistry_id"]].validate_for(CoordinateSpace.from_dict(item["space"]),item["sequence"],item["sequence_extent"])
        except SerializationError:require(item["expected_code"] is not None,"Unexpected chemistry validation failure")
        else:require(item["expected_code"] is None,"Accepted intended chemistry validation rejection")
    for item in document["text_cases"]:
        try:_text(item["value"],"Fixture",item["maximum"])
        except SerializationError:accepted=False
        else:accepted=True
        require(accepted==item["accepted"],"Molecular text acceptance differs")
    for item in document["pretty_cases"]:
        _bounded_tree(item["document"])
        size=len(json.dumps(item["document"],sort_keys=True,indent=item["indent"],ensure_ascii=False,allow_nan=False).encode())
        require(size==item["bytes"],"Molecular pretty byte size differs")
    require(census(document)==document["coverage"],"Chemistry coverage differs")
    require(document["coverage"]["kinds"]==sorted(KINDS),"Missing chemistry record kind")
    require((len(document["records"]),len(document["rejections"]),len(document["validations"]),len(document["text_cases"]),len(document["pretty_cases"]))==(47,82,29,10,50),"Missing mandatory chemistry cases")
    require(len(encoded(document))<4_000_000,"Chemistry corpus exceeds read budget")


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--write",action="store_true");parser.add_argument("--output",type=Path,default=CORPUS)
    args=parser.parse_args(argv);document=build_corpus();check_corpus(document);content=encoded(document)
    if args.write:args.output.write_bytes(content)
    else:
        retained=args.output.read_bytes();check_corpus(json.loads(retained));require(retained==content,"Chemistry corpus drifted; inspect before refreezing")
    print(json.dumps({"status":"written" if args.write else "checked","bytes":len(content),**document["coverage"]},sort_keys=True))
    return 0


if __name__=="__main__":raise SystemExit(main())

"""Freeze fresh payload-region checks; no producer or biological admission oracle.

The JSON adapter imports serialized declarations before invoking the legacy typed
checker. Raw dictionaries passed directly as Python typed objects are a different
API boundary, retained explicitly below rather than mislabeled parity.
"""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_molecules import CircuitMoleculeSet, ComplexConstituent, MolecularComplex
from biocompiler.ir.circuit_payloads import PayloadStructureContract, RequiredPayloadRegion
from biocompiler.ir.molecule_records import _records
from biocompiler.ir.molecule_chemistry import ChemistryClaim, TailDeclaration, TailLength
from biocompiler.ir.serialization import fingerprint
from biocompiler.verification.circuit_payloads import check_payload_structures
from tests.test_circuit_payloads import bundle, contract, molecule, region, role, unknown_provenance
from examples.circuit_molecules import fixture_provenance, make_molecule

CORPUS = ROOT / "tests/conformance/payload-structure-check-v1.json"
SCHEMA = "biocompiler.payload_structure_check_conformance.v1"
INVENTORY = "329fee52707d64ffa448bf5e54ad3ee2688f9e0d5c6ad38b5df41817af20892d"


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()


def pair(diagnostics=(), unsupported=()):
    return {"diagnostics": sorted(set(diagnostics)), "unsupported": sorted(set(unsupported))}


def check_serialized(contracts, current):
    """Explicit JSON import followed by the unchanged Python typed checker."""
    try:
        if contracts is None:
            imported = ()
        else:
            if not isinstance(contracts, list) or len(contracts) > 64:
                raise SerializationError("Serialized contract inventory must be a bounded array")
            imported = tuple(PayloadStructureContract.from_dict(item) for item in contracts)
        imported = _records(imported, PayloadStructureContract, 64, "contracts", key="member_id")
    except SerializationError:
        return pair(("payload_contract_inventory_invalid",))
    try:
        current = CircuitMoleculeSet.from_dict(current)
    except SerializationError:
        return pair(("payload_bundle_invalid",), () if imported else ("payload_authority_missing",))
    diagnostics, unsupported = check_payload_structures(imported, bundle=current)
    return pair(diagnostics, unsupported)


def relocate(value):
    """Retain source responsibility but replace machine paths with repository paths.

    Python stack line attribution can vary with interpreter versions. The one
    source call used by these artificial fixtures is anchored to its AST call.
    Case B is read unchanged from its already retained source documents.
    """
    source = ROOT / "tests/test_circuit_payloads.py"
    tree = ast.parse(source.read_text())
    function = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == "form_request")
    line = next(item.lineno for item in ast.walk(function)
                if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute) and item.func.attr == "engineer")

    def visit(item):
        if isinstance(item, list):
            return [visit(child) for child in item]
        if isinstance(item, dict):
            result = {key: visit(child) for key, child in item.items()}
            if set(result) == {"file", "line", "function"}:
                path = Path(result["file"])
                if path.is_absolute():
                    result["file"] = path.resolve().relative_to(ROOT).as_posix()
                if result["file"] == "tests/test_circuit_payloads.py" and result["function"] == "form_request":
                    result["line"] = line
            return result
        return item
    return visit(value)


def rehash_candidate(raw):
    """Update all candidate-local pins, retaining the complete source request."""
    molecules = {item["id"]: fingerprint(item) for item in raw["molecules"]}
    complexes = {}
    for item in raw["complexes"]:
        for member in item["constituents"]:
            if member["molecule_id"] in molecules:
                member["molecule_fingerprint"] = molecules[member["molecule_id"]]
        complexes[item["id"]] = fingerprint(item)
    subjects = molecules | complexes
    for item in raw["role_instances"]:
        if item["subject_id"] in subjects:
            item["subject_fingerprint"] = subjects[item["subject_id"]]
    return raw


def inventory(corpus):
    return fingerprint({
        "cases": sorted([item["id"], item["bundle_document"], fingerprint(item["contracts"]),
                         item["expected"], item["source_fingerprint"], item["original_bundle_document"],
                         item["boundary"]] for item in corpus["cases"]),
        "api_boundary": corpus["api_boundary"],
        "coverage": corpus["coverage"],
    })


def build_corpus():
    documents, cases = {}, []

    def document(raw):
        identity = fingerprint(raw)
        documents[identity] = raw
        return identity

    def retain(identity, current, contracts, diagnostics=(), unsupported=(), *, original=None, boundary="typed_and_serialized"):
        raw = relocate(current.to_dict()) if isinstance(current, CircuitMoleculeSet) else deepcopy(current)
        raw_contracts = None if contracts is None else [item.to_dict() if isinstance(item, PayloadStructureContract) else deepcopy(item) for item in contracts] if isinstance(contracts, (list, tuple)) else deepcopy(contracts)
        expected = pair(diagnostics, unsupported)
        actual = check_serialized(raw_contracts, raw)
        assert actual == expected, (identity, expected, actual)
        if original is not None:
            original = relocate(original.to_dict()) if isinstance(original, CircuitMoleculeSet) else deepcopy(original)
            assert raw["request"] == original["request"], identity + ": source authority changed"
        cases.append({"id": identity, "bundle_document": document(raw), "contracts": raw_contracts,
                      "expected": expected, "source_fingerprint": fingerprint(raw["request"]) if isinstance(raw, dict) and "request" in raw else None,
                      "original_bundle_document": document(original) if original is not None else None,
                      "boundary": boundary})

    subject = molecule(); base = bundle(subject); expected = contract(subject)
    for form in ("delivered_rna", "delivered_dna"):
        for topology in ("linear", "circular"):
            item = molecule(form=form, topology=topology)
            retain(f"modality/{form}/{topology}", bundle(item), [contract(item)])
    circular = molecule(topology="circular")
    retain("modality/circular_requested_alias", bundle(circular, requested_form="circular_rna"), [contract(circular)])
    retain("serialized_contract_dicts_are_imported", base, [expected.to_dict()])
    circle = molecule(topology="circular")
    circle = replace(circle, features=(region(circle, "zeta", "invented_regulatory_label", ((5, 6), (0, 3))),
                                      region(circle, "alpha", "invented_regulatory_label", ((1, 5),), strand="-")))
    retain("geometry/overlap_reverse_cross_origin", bundle(circle), [contract(circle)])
    retain("authority/contract_unknown", base, [contract(subject, provenance=unknown_provenance())], unsupported=["payload_authority_undeclared:payload"])
    changed = replace(subject, features=(replace(subject.features[0], provenance=unknown_provenance()), subject.features[1]))
    retain("authority/feature_unknown_rehashed", bundle(changed), [expected], unsupported=["payload_boundary_authority_undeclared:payload/first"], original=base)
    first, second = molecule("first_payload"), molecule("second_payload")
    current = bundle(first, second)
    for name, values in (("null", None), ("empty", [])):
        retain("authority/" + name, current, values, unsupported=["payload_authority_missing", "payload_authority_missing:first_payload", "payload_authority_missing:second_payload"])
    reversed_input = relocate(current.to_dict())
    reversed_input["molecules"].reverse(); reversed_input["role_instances"].reverse()
    for item in reversed_input["molecules"]:
        item["features"].reverse()
    retain("ordering/input_inventory_permutations", reversed_input, [contract(second), contract(first)])
    retain("authority/partial", current, [contract(first)], unsupported=["payload_authority_missing:second_payload"])
    retain("authority/extra", current, [contract(first), contract(second), replace(contract(first), member_id="extra")], ["payload_contract_extra:extra"])
    retain("authority/duplicate", current, [contract(first), contract(first)], ["payload_contract_inventory_invalid"])
    payload, helper = molecule(), molecule("helper")
    helper_bundle = bundle(payload, helper, roles=(role(payload, "one"), role(payload, "two"), role(helper, purpose="helper")))
    retain("roles/repeated_payload_helper_excluded", helper_bundle, [contract(payload)])
    retain("roles/helper_extra_contract", helper_bundle, [contract(payload), contract(helper)], ["payload_contract_extra:helper"])
    for name, change, diagnostic in (
        ("form", replace(expected, form="delivered_dna"), "payload_form_mismatch:payload"),
        ("topology", replace(expected, topology="circular"), "payload_topology_mismatch:payload"),
        ("region_id", replace(expected, regions=(RequiredPayloadRegion("absent", "artificial_control_region"),)), "payload_region_missing:payload/absent"),
        ("region_kind", replace(expected, regions=(RequiredPayloadRegion("first", "different"),)), "payload_region_kind_mismatch:payload/first"),
    ):
        retain("contract/" + name, base, [change], [diagnostic])
    unknown = replace(subject, features=(replace(subject.features[0], path=None), subject.features[1]))
    retain("candidate/unknown_coordinates_rehashed", bundle(unknown), [expected], unsupported=["payload_region_coordinates_unknown:payload/first"], original=base)
    retain("candidate/unrequired_unknown_ignored", bundle(unknown), [replace(expected, regions=(expected.regions[1],))])
    boundary = replace(subject, features=(region(subject, "first", subject.features[0].kind, ((2, 2),)), subject.features[1]))
    retain("candidate/empty_boundary_rehashed", bundle(boundary), [expected], ["payload_region_empty:payload/first"], original=base)
    missing = replace(subject, features=(subject.features[1],))
    retain("candidate/missing_region_rehashed", bundle(missing), [expected], ["payload_region_missing:payload/first"], original=base)
    wrong = replace(subject, features=(replace(subject.features[0], kind="different"), subject.features[1]))
    retain("candidate/changed_kind_rehashed", bundle(wrong), [expected], ["payload_region_kind_mismatch:payload/first"], original=base)
    spelling = replace(subject, sequence="UGCAUG")
    retain("scope/changed_spelling_same_declared_regions", bundle(spelling), [expected], original=base)
    unknown_cap = replace(subject, chemistry=replace(subject.chemistry, cap=ChemistryClaim("unknown", None, unknown_provenance())))
    retain("chemistry/unknown_cap_rehashed", bundle(unknown_cap), [expected], unsupported=["payload_chemistry_incomplete:payload"], original=base)
    tail = TailDeclaration("declared", "appended_terminal", TailLength("unknown"), None, unknown_provenance())
    core = replace(subject, sequence_extent="exact_core", chemistry=replace(subject.chemistry, terminal_tail=tail))
    retain("chemistry/exact_core_rehashed", bundle(core), [expected], unsupported=["payload_extent_incomplete:payload", "payload_chemistry_incomplete:payload"], original=base)
    combined = replace(unknown_cap, features=(replace(subject.features[0], path=None, kind="different", provenance=unknown_provenance()),))
    retain("ordering/multiple_contradictions_and_unknowns", bundle(combined), [replace(expected, form="delivered_dna", topology="circular", provenance=unknown_provenance())],
           ["payload_form_mismatch:payload", "payload_topology_mismatch:payload", "payload_region_kind_mismatch:payload/first", "payload_region_missing:payload/second"],
           ["payload_authority_undeclared:payload", "payload_boundary_authority_undeclared:payload/first", "payload_region_coordinates_unknown:payload/first", "payload_chemistry_incomplete:payload"], original=base)
    for form in ("dna_expression_template", "primary_rna", "processed_rna"):
        item = molecule(form=form)
        retain("unsupported/" + form + "/missing", bundle(item), [], unsupported=["payload_authority_missing", "payload_authority_missing:payload", "payload_modality_unsupported:payload"])
        substitute = PayloadStructureContract(item.id, "delivered_dna" if item.space.alphabet == "DNA" else "delivered_rna", item.space.topology,
                                              (RequiredPayloadRegion("first", item.features[0].kind),), fixture_provenance())
        retain("unsupported/" + form + "/substitution", bundle(item), [substitute], ["payload_form_mismatch:payload"], ["payload_modality_unsupported:payload"])
    for form, kind in (("delivered_rna", "rna_complex"), ("delivered_dna", "dna_duplex")):
        one, two = molecule("one", form=form), molecule("two", form=form)
        complex_ = MolecularComplex("assembly", kind, tuple(ComplexConstituent(item.id, item.fingerprint, 1, fixture_provenance()) for item in (one, two)), fixture_provenance())
        current = bundle(one, two, complexes=(complex_,), roles=(role(complex_), role(one, "also_direct")))
        contracts = [contract(one), contract(two)]
        retain("complex/" + kind + "/complete", current, contracts)
        retain("complex/" + kind + "/missing_member", current, contracts[:1], unsupported=["payload_authority_missing:two"])
        retain("complex/" + kind + "/complex_contract_extra", current, contracts + [replace(contracts[0], member_id="assembly")], ["payload_contract_extra:assembly"])
        raw = relocate(current.to_dict()); raw["complexes"][0]["constituents"][0]["stoichiometry"] = None
        retain("complex/" + kind + "/unknown_stoichiometry_rehashed", rehash_candidate(raw), contracts,
               diagnostics=["payload_bundle_invalid"] if kind == "dna_duplex" else (),
               unsupported=["payload_complex_stoichiometry_unknown:assembly/one"] if kind == "rna_complex" else (),
               original=current, boundary="serialized_import" if kind == "dna_duplex" else "typed_and_serialized")
    complex_ = MolecularComplex("assembly", "rna_complex", (ComplexConstituent(subject.id, subject.fingerprint, 2, fixture_provenance()),), fixture_provenance())
    retain("complex/known_homomer", bundle(subject, complexes=(complex_,), roles=(role(complex_),)), [expected])
    protein = make_molecule("protein", "AC", form="mature_protein")
    protein_complex = MolecularComplex("protein_assembly", "protein_complex", (ComplexConstituent(protein.id, protein.fingerprint, 2, fixture_provenance()),), fixture_provenance())
    proteins = bundle(subject, protein, complexes=(protein_complex,), roles=(role(subject), role(protein_complex, purpose="helper")))
    retain("scope/protein_helper_ignored", proteins, [expected])
    forged = relocate(proteins.to_dict())
    next(item for item in forged["role_instances"] if item["subject_id"] == protein_complex.id)["purpose"] = "requested_payload"
    retain("import/protein_relabelled_payload", forged, [expected], ["payload_bundle_invalid"], original=proteins, boundary="serialized_import")
    original = relocate(base.to_dict())
    bundle_mutations = [
        ("missing_request", lambda raw: raw.pop("request")),
        ("extra_bundle_field", lambda raw: raw.update(accepted=True)),
        ("future_bundle_schema", lambda raw: raw.update(schema_version="future")),
        ("wrong_role_pin", lambda raw: raw["role_instances"][0].update(subject_fingerprint="0" * 64)),
        ("dangling_role", lambda raw: raw["role_instances"][0].update(subject_id="absent")),
        ("duplicate_molecule", lambda raw: raw["molecules"].append(deepcopy(raw["molecules"][0]))),
        ("wrong_coordinate_frame", lambda raw: raw["molecules"][0]["features"][0]["path"].update(space_id="absent")),
        ("coordinate_out_of_range", lambda raw: raw["molecules"][0]["features"][0]["path"]["spans"][0].update(end=7)),
        ("inconsistent_alphabet", lambda raw: raw["molecules"][0]["space"].update(alphabet="DNA")),
        ("unknown_form", lambda raw: raw["molecules"][0].update(form="future")),
    ]
    for name, edit in bundle_mutations:
        raw = deepcopy(original); edit(raw)
        if name != "wrong_role_pin":
            rehash_candidate(raw)
        retain("import/" + name, raw, [expected], ["payload_bundle_invalid"],
               original=original if "request" in raw else None, boundary="serialized_import")
    retain("import/null_bundle_empty_contracts", None, [], ["payload_bundle_invalid"], ["payload_authority_missing"], boundary="serialized_import")
    retain("import/null_bundle_present_contracts", None, [expected], ["payload_bundle_invalid"], boundary="serialized_import")
    retain("import/invalid_contract_precedes_invalid_bundle", None, [expected, expected], ["payload_contract_inventory_invalid"], boundary="serialized_import")
    retain("import/contracts_object", base, {"payload": expected.to_dict()}, ["payload_contract_inventory_invalid"], boundary="serialized_import")
    retain("import/contracts_over_limit", base, [expected] * 65, ["payload_contract_inventory_invalid"], boundary="serialized_import")
    # Every malformed contract boundary is independently retained by its owning
    # domain corpus; the checker must map each one to its inventory diagnostic.
    declarations = json.loads((ROOT / "tests/conformance/payload-structure-v1.json").read_bytes())
    for case in declarations["rejections"]:
        if case["kind"] == "contract":
            retain("import/contract/" + case["id"].removeprefix("contract/"), base, [case["input"]], ["payload_contract_inventory_invalid"], boundary="serialized_import")
    # Exact upper bound is accepted as an inventory; extra authorities are
    # contradictions, not an inventory-overflow error.
    retain("bound/exact64_contracts", base, [expected] + [replace(expected, member_id=f"extra{i:02d}") for i in range(63)],
           [f"payload_contract_extra:extra{i:02d}" for i in range(63)])
    for variant in ("base", "parameter-default", "parameter-override"):
        original_request = json.loads((ROOT / f"tests/conformance/case-b/{variant}/request.json").read_bytes())
        candidate = json.loads((ROOT / f"tests/conformance/case-b/{variant}/candidate.json").read_bytes())
        current = candidate["construction"]["candidate"]["bundle"]
        assert current["request"] == original_request["circuit"]
        # The independently retained source template supplies the contract.
        # This one-template fixture has an explicit, fixed instance-name mapping;
        # candidate construction metadata is cross-checked, never its authority.
        source_contract = deepcopy(original_request["library"]["refinements"][0]["templates"][0]["payload_structures"][0])
        assert source_contract["member_id"] == "payload"
        source_contract["member_id"] = "a000_t000_payload"
        contracts = [source_contract]
        assert contracts == candidate["construction"]["request"]["payload_structures"]
        retain("case_b/" + variant + "/complete", current, contracts)
        changed = deepcopy(current); changed["molecules"][0]["features"][0]["kind"] = "different"
        retain("case_b/" + variant + "/changed_kind_rehashed", rehash_candidate(changed), contracts,
               ["payload_region_kind_mismatch:a000_t000_payload/contract-region"], original=current)
        changed = deepcopy(current); changed["molecules"][0]["features"][0]["path"] = None
        retain("case_b/" + variant + "/unknown_boundary_rehashed", rehash_candidate(changed), contracts,
               unsupported=["payload_region_coordinates_unknown:a000_t000_payload/contract-region"], original=current)
    result = {
        "schema_version": SCHEMA,
        "claim_scope": "Fresh correspondence to supplied payload-region declarations only; no construction replay, source fidelity, regulatory function, empirical evidence or human therapeutic admission is established.",
        "api_boundary": {
            "serialized_import": "Native check_json imports whole bundle and contract JSON, then checks typed declarations. Python oracle here performs the same explicit import before the unchanged typed checker.",
            "typed_dictionary_misuse": {"python_direct": pair(["payload_contract_inventory_invalid"]), "native_serialized": pair(), "witness_case": "serialized_contract_dicts_are_imported"},
            "unreachable_after_checked_import": ["payload_modality_alphabet", "payload_region_coordinates_invalid", "payload_complex_modality_unsupported"],
            "unreachable_reason": "Current molecule/set invariants reject inconsistent form/alphabet, invalid feature frames and requested protein complexes before structural inspection. Forged serialized witnesses expect payload_bundle_invalid; no unsafe typed object construction is used in OCaml.",
        },
        "coverage": {"modalities": ["delivered_dna/circular", "delivered_dna/linear", "delivered_rna/circular", "delivered_rna/linear"],
                     "complexes": ["dna_duplex", "rna_complex", "protein_complex_helper"],
                     "case_b_variants": ["base", "parameter-default", "parameter-override"],
                     "expected_authority": "Every expected diagnostic/unsupported pair is a literal independent assertion checked against Python, not copied from its result.",
                     "source_policy": "Candidate changes retain the whole original CircuitRequest. Source file paths for artificial helper fixtures are repository-relative and their engineer call uses AST source coordinates; retained Case B source bytes are unchanged."},
        "documents": documents, "cases": cases,
    }
    result["inventory_sha256"] = inventory(result)
    return result


def check_corpus(corpus):
    assert corpus["schema_version"] == SCHEMA
    ids = [item["id"] for item in corpus["cases"]]
    assert len(ids) == len(set(ids)), "Duplicate checker case inventory"
    assert inventory(corpus) == corpus["inventory_sha256"], "Changed checker case/expected inventory"
    assert len(corpus["cases"]) == 99 and len(corpus["documents"]) == 48, "Incomplete checker inventory"
    assert inventory(corpus) == INVENTORY, "Missing or substituted checker case/expected inventory"
    used = set()
    for identity, raw in corpus["documents"].items():
        assert fingerprint(raw) == identity, "Changed checker document"
    for case in corpus["cases"]:
        current = corpus["documents"][case["bundle_document"]]; used.add(case["bundle_document"])
        assert check_serialized(case["contracts"], current) == case["expected"], case["id"]
        source = fingerprint(current["request"]) if isinstance(current, dict) and "request" in current else None
        assert source == case["source_fingerprint"], "Changed original request identity"
        if case["original_bundle_document"] is not None:
            original = corpus["documents"][case["original_bundle_document"]]; used.add(case["original_bundle_document"])
            assert current["request"] == original["request"], "Candidate mutation rewrote source authority"
            assert case["bundle_document"] != case["original_bundle_document"], "Candidate mutation is a no-op"
    assert used == set(corpus["documents"]), "Unused checker document"
    assert len(encoded(corpus)) <= 16 * 1024 * 1024, "Checker corpus byte budget"
    pending = [(corpus, 0)]; count = 0
    while pending:
        value, depth = pending.pop(); count += 1
        assert count <= 250_000 and depth <= 128, "Checker corpus structural budget"
        if isinstance(value, dict):
            pending.extend((child, depth + 1) for entry in value.items() for child in entry)
        elif isinstance(value, list):
            pending.extend((child, depth + 1) for child in value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    corpus = build_corpus(); check_corpus(corpus); data = encoded(corpus)
    if args.write:
        CORPUS.write_bytes(data)
    elif not CORPUS.exists() or CORPUS.read_bytes() != data:
        raise SystemExit("Payload checker corpus is stale; review before --write")
    print(json.dumps({"cases": len(corpus["cases"]), "documents": len(corpus["documents"]), "bytes": len(data), "inventory_sha256": inventory(corpus)}))


if __name__ == "__main__":
    main()

"""Retain complete artificial molecule, set and amount domain conformance.

Python declarations supply the compatibility oracle. Explicit identity relations
and native literals remain independent expectations; no native producer is run.
"""
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
from biocompiler.ir.circuit_molecules import (
    AssemblyOrigin, MoleculeFeature, CircuitMolecule, ComplexConstituent,
    MolecularComplex, MoleculeRoleInstance, FormCoordinateMapping, CircuitMoleculeSet,
    FORMS, MAPPING_RELATIONS,
)
from biocompiler.artifacts.circuit_molecules import ExperimentalAmount, CircuitMoleculeRecord
from biocompiler.ir.molecule_records import DeclarationProvenance
from biocompiler.ir.molecule_chemistry import BaseModification, TailDeclaration, TailLength
from biocompiler.ir.circuit_intent import CircuitRequest
from biocompiler.ir.serialization import fingerprint
from biocompiler.semantics.molecule_coordinates import CoordinatePath, IndexSpan

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/molecules-v1.json"
SCHEMA = "biocompiler.molecules_conformance.v1"
KINDS = {"assembly_origin": AssemblyOrigin, "feature": MoleculeFeature, "molecule": CircuitMolecule,
         "constituent": ComplexConstituent, "complex": MolecularComplex, "role": MoleculeRoleInstance,
         "mapping": FormCoordinateMapping, "set": CircuitMoleculeSet, "amount": ExperimentalAmount,
         "artifact": CircuitMoleculeRecord}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def fixture_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("molecule_domain_source_fixtures", ROOT / "tests/test_circuit_molecule_integration.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def relocate(value):
    if isinstance(value, list):
        return [relocate(item) for item in value]
    if isinstance(value, dict):
        result = {key: relocate(item) for key, item in value.items()}
        if set(result) == {"file", "line", "function"}:
            path = Path(result["file"])
            if path.is_absolute():
                result["file"] = path.resolve().relative_to(ROOT).as_posix()
        return result
    return value


def apply_edits(document, edits):
    result = deepcopy(document)
    for edit in edits:
        container = result
        for key in edit["path"][:-1]:
            container = container[key]
        key = edit["path"][-1]
        if edit["op"] == "remove":
            del container[key]
        elif edit["op"] == "set":
            container[key] = deepcopy(edit["value"])
        else:
            raise AssertionError("Unknown molecular fixture edit")
    return result


def summary(value):
    result = {"fingerprint": value.fingerprint}
    if isinstance(value, CircuitMolecule):
        result.update(spelling_identity=value.spelling_identity, nominal=value.nominal_dict(),
                      declared_nominal_identity=value.declared_nominal_identity,
                      declared_nominal_complete=value.declared_nominal_complete,
                      complete_nominal_identity=value.complete_nominal_identity,
                      base_rotation_identity=value.base_rotation_identity)
    elif isinstance(value, CircuitMoleculeSet):
        result.update(declared_nominal_complete=value.declared_nominal_complete,
                      declared_nominal_bundle_identity=value.declared_nominal_bundle_identity,
                      subjects={item.id: {"nominal": value.subject_nominal_identity(item.id),
                                          "complete": value.subject_complete(item.id)}
                                for item in (*value.molecules, *value.complexes)})
    elif isinstance(value, CircuitMoleculeRecord):
        result.update(nominal_bundle_identity=value.nominal_bundle_identity,
                      experimental_specification_identity=value.experimental_specification_identity,
                      artifact_fingerprint=value.artifact_fingerprint)
    return result


def build_corpus():
    f = fixture_module()
    from examples.circuit_molecules import make_molecule_record
    from examples.circuit_intent import make_circuit_requests
    documents, records, rejections, relations = {}, [], [], []
    objects = {}

    def retain(identity, kind, value, *, edits=(), origin="artificial_literal"):
        raw = value.to_dict() if hasattr(value, "to_dict") else value
        normalized = KINDS[kind].from_dict(relocate(raw))
        doc = normalized.to_dict()
        document_id = fingerprint(doc)
        documents[document_id] = doc
        imported = KINDS[kind].from_dict(apply_edits(doc, edits))
        require(encoded(imported.to_dict()) == encoded(doc), "Positive input normalization differs " + identity)
        records.append(dict(id=identity, kind=kind, document_id=document_id, edits=list(edits), expected=summary(normalized), origin=origin))
        objects[identity] = normalized
        return normalized

    def edit(path, value):
        return dict(op="set", path=path, value=value)

    def reject(identity, source, edits, code):
        case = next(item for item in records if item["id"] == source)
        raw = apply_edits(documents[case["document_id"]], edits)
        try:
            KINDS[case["kind"]].from_dict(raw)
        except SerializationError:
            pass
        else:
            raise AssertionError("Python accepted intended molecular rejection " + identity)
        rejections.append(dict(id=identity, kind=case["kind"], document_id=case["document_id"], edits=edits, expected_code=code))

    def relation(left, right, equal=(), different=()):
        a, b = summary(objects[left]), summary(objects[right])
        for key in equal:
            require(encoded(a[key]) == encoded(b[key]), "False equal identity relation " + left + "/" + right + "/" + key)
        for key in different:
            require(encoded(a[key]) != encoded(b[key]), "False distinct identity relation " + left + "/" + right + "/" + key)
        relations.append(dict(left=left, right=right, equal=list(equal), different=list(different)))

    plain_request = CircuitRequest.from_dict(relocate(f.form_request("delivered_rna").to_dict()))

    def bundle(molecules, *, request=plain_request, complexes=(), roles=None, mappings=()):
        return f.bundle(molecules, request=request, complexes=complexes, roles=roles, mappings=mappings)

    base = retain("molecule/plain", "molecule", f.molecule())
    retain("origin/plain", "assembly_origin", base.assembly[0])
    feature = retain("feature/unknown", "feature", MoleculeFeature("unknown", "unresolved_annotation", None, f.provenance("annotation")))
    features = tuple(MoleculeFeature("feature_" + str(i), kind, f.path(base.space), f.provenance(kind), frame)
                     for i, (kind, frame) in enumerate((("CDS", 0), ("uORF", 1), ("overlap", 2)))) + (feature,)
    with_features = retain("molecule/features", "molecule", replace(base, features=features))
    retain("molecule/features_unsorted_import", "molecule", with_features,
           edits=[edit(["features"], list(reversed(with_features.to_dict()["features"])) )])
    for item in features[:-1]:
        retain("feature/" + item.id, "feature", item)
    origin = base.assembly[0]
    partitions = tuple(replace(origin, id="part_" + str(i), destination=f.path(base.space, start, end),
        source_path=f.path(origin.source_space, start, end)) for i, (start, end) in enumerate(((0, 2), (2, 4))))
    partitioned = retain("molecule/partitioned", "molecule", replace(base, assembly=partitions))
    reversed_origin = replace(origin, source_path=replace(origin.source_path, strand="-"))
    retain("molecule/reverse_declared_origin", "molecule", replace(base, assembly=(reversed_origin,)))
    for form in sorted(FORMS):
        alphabet = "protein" if form in {"protein_precursor", "mature_protein"} else "DNA" if form in {
            "deposited_template_record", "dna_expression_template", "delivered_dna"} else "RNA"
        retain("form/" + form, "molecule", f.molecule("form_" + form, "MUO" if alphabet == "protein" else "ACG",
               alphabet=alphabet, form=form, coding_status="inapplicable" if alphabet == "protein" else "coding"))
    noncoding = retain("molecule/noncoding_extension", "molecule", f.molecule("post_tail", "CGAAAACG", coding_status="noncoding"))
    unknown_provenance = DeclarationProvenance("unknown", (), None, "Artificial provenance absent.")
    retain("molecule/unknown_provenance", "molecule", replace(base, provenance=unknown_provenance))
    retain("molecule/unknown_chemistry", "molecule", replace(base, chemistry=replace(base.chemistry, modification_inventory_status="unknown")))
    relation("molecule/plain", "molecule/unknown_provenance", equal=("declared_nominal_identity", "declared_nominal_complete"), different=("fingerprint",))
    retain("molecule/form_alias", "molecule", replace(base, form="primary_rna"))
    relation("molecule/plain", "molecule/form_alias", equal=("declared_nominal_identity", "spelling_identity"), different=("fingerprint",))
    circle = f.molecule("circle", "AACCGU", topology="circular")
    circle_feature = MoleculeFeature("wrap", "recognition", CoordinatePath(circle.space.id, (IndexSpan(4, 6), IndexSpan(0, 2)), "+"), f.provenance())
    retain("molecule/circle", "molecule", replace(circle, features=(circle_feature,)))
    retain("molecule/circle_rotated", "molecule", f.molecule("rotated", "CGUAAC", topology="circular"))
    relation("molecule/circle", "molecule/circle_rotated", equal=("base_rotation_identity",), different=("spelling_identity", "declared_nominal_identity"))
    for spelling in ("A", "AAAA", "ACAC", "GCAUAC"):
        retain("rotation/" + spelling, "molecule", f.molecule("circle_" + spelling, spelling, topology="circular"))
    modified = f.molecule("modified", "AACU")
    group = BaseModification("group", f.chemical("inosine"), "A", "positions", (0, 1), f.provenance())
    split = (replace(group, id="left", positions=(0,)), replace(group, id="right", positions=(1,)))
    policy = replace(group, id="policy", scope="all_matching_bases", positions=())
    for name, items in (("group", (group,)), ("split", split), ("policy", (policy,)), ("site_zero", (split[0],)), ("site_one", (split[1],))):
        retain("chemistry/" + name, "molecule", replace(modified, chemistry=replace(modified.chemistry, modifications=items)))
    for variant in ("split", "policy"):
        relation("chemistry/group", "chemistry/" + variant, equal=("declared_nominal_identity",), different=("fingerprint",))
    relation("chemistry/site_zero", "chemistry/site_one", different=("declared_nominal_identity",))
    no_sites = replace(policy, identity=f.chemical("pseudouridine"), canonical_base="U")
    plain_ac = retain("chemistry/no_sites_plain", "molecule", f.molecule("no_sites", "AACC"))
    retain("chemistry/no_sites_policy", "molecule", replace(plain_ac, chemistry=replace(plain_ac.chemistry, modifications=(no_sites,))))
    relation("chemistry/no_sites_plain", "chemistry/no_sites_policy", equal=("declared_nominal_identity",), different=("fingerprint",))
    long_modified = f.molecule("position_endian", "A" + "C" * 255 + "A")
    retain("chemistry/endian_positions", "molecule", replace(long_modified, chemistry=replace(long_modified.chemistry,
           modifications=(replace(group, positions=(0, 256)),))))
    appended = TailDeclaration("declared", "appended_terminal", TailLength("bounded", lower=2, upper=5), None, f.provenance())
    for name, items in (("sites", (group,)), ("policy", (policy,))):
        retain("core/" + name, "molecule", replace(modified, sequence_extent="exact_core",
               chemistry=replace(modified.chemistry, terminal_tail=appended, modifications=items)))
    relation("core/sites", "core/policy", equal=("spelling_identity",), different=("declared_nominal_identity",))
    tail_molecule = f.molecule("tail", "CGAAA")
    retain("tail/absent", "molecule", tail_molecule)
    for length in (1, 2):
        tail = TailDeclaration("declared", "represented_terminal", TailLength("exact", exact=length), f.path(tail_molecule.space, 5-length, 5), f.provenance())
        retain("tail/" + str(length), "molecule", replace(tail_molecule, chemistry=replace(tail_molecule.chemistry, terminal_tail=tail)))
    relation("tail/1", "tail/2", equal=("declared_nominal_identity",), different=("fingerprint",))
    relation("tail/absent", "tail/1", equal=("declared_nominal_identity",), different=("fingerprint",))

    constituent = retain("constituent/one", "constituent", ComplexConstituent(base.id, base.fingerprint, 1, f.provenance()))
    retain("constituent/unknown", "constituent", replace(constituent, stoichiometry=None))
    retain("constituent/max", "constituent", replace(constituent, stoichiometry=1_000_000))
    homomer = retain("complex/homomer", "complex", MolecularComplex("homomer", "rna_complex", (replace(constituent, stoichiometry=2),), f.provenance()))
    unknown_complex = retain("complex/unknown", "complex", replace(homomer, constituents=(replace(constituent, stoichiometry=None),)))
    for purpose in ("requested_payload", "helper", "host_provider", "assay_control", "external_input"):
        retain("role/" + purpose, "role", f.role(base, identity="role_" + purpose, purpose=purpose))
    mapping = FormCoordinateMapping("mapping", base.id, base.fingerprint, base.id, base.fingerprint,
        f.path(base.space), f.path(base.space, 1, 2), "declared_correspondence", f.provenance())
    for relation_name in sorted(MAPPING_RELATIONS):
        retain("mapping/" + relation_name, "mapping", replace(mapping, relation=relation_name))
    plain_set = retain("set/plain", "set", bundle((base,)))
    alias = retain("molecule/alias", "molecule", f.molecule("alias"))
    roles = (f.role(base),)
    alias_set = retain("set/alias", "set", bundle((base, alias), roles=roles))
    retain("set/role_renamed", "set", replace(plain_set, role_instances=(replace(roles[0], id="renamed"),)))
    retain("set/role_repeated", "set", replace(plain_set, role_instances=(roles[0], replace(roles[0], id="second"))))
    relation("set/plain", "set/alias", equal=("declared_nominal_bundle_identity",), different=("fingerprint",))
    relation("set/plain", "set/role_renamed", equal=("declared_nominal_bundle_identity",), different=("fingerprint",))
    relation("set/plain", "set/role_repeated", different=("declared_nominal_bundle_identity",))
    homomer_set = retain("set/homomer", "set", bundle((base,), complexes=(homomer,)))
    retain("set/unknown_complex", "set", bundle((base,), complexes=(unknown_complex,)))
    known_alias_complex = MolecularComplex("alias_complex", "rna_complex", (constituent,
        ComplexConstituent(alias.id, alias.fingerprint, 1, f.provenance())), f.provenance())
    retain("set/complex_alias_aggregation", "set", bundle((base, alias), complexes=(known_alias_complex,)))
    mixed_alias_complex = replace(known_alias_complex, constituents=tuple(
        replace(item, stoichiometry=None) if item.molecule_id == alias.id else item
        for item in known_alias_complex.constituents))
    retain("set/complex_known_unknown", "set", bundle((base, alias), complexes=(mixed_alias_complex,)))
    retain("set/mapping", "set", bundle((base,), mappings=(mapping,)))
    retain("set/circular_requested", "set", bundle((circle,), request=f.form_request("circular_rna")))
    dna_a = f.molecule("strand_a", "AAC", alphabet="DNA", form="delivered_dna")
    dna_b = f.molecule("strand_b", "AAC", alphabet="DNA", form="delivered_dna")
    duplex = retain("complex/duplex", "complex", MolecularComplex("duplex", "dna_duplex", tuple(
        ComplexConstituent(x.id, x.fingerprint, 1, f.provenance()) for x in (dna_a, dna_b)), f.provenance()))
    retain("set/duplex", "set", bundle((dna_a, dna_b), request=f.form_request("delivered_dna"), complexes=(duplex,), roles=(f.role(duplex),)))
    reference = CircuitRequest.from_dict(relocate(make_circuit_requests()["reference"].to_dict()))
    retain("set/reference", "set", bundle((base,), request=reference))
    example = CircuitMoleculeRecord.from_dict(relocate(make_molecule_record().to_dict()))
    retain("artifact/full_example", "artifact", example, origin="examples/circuit_molecules.py::make_molecule_record")
    retain("set/full_example", "set", example.bundle, origin="examples/circuit_molecules.py::make_molecule_record")
    retain("complex/protein", "complex", example.bundle.complexes[0])
    acceptance = example.bundle.request.profile.source_request
    for name, source in (("behavior", acceptance.behavior_request), ("deployment", acceptance.deployment_request), ("acceptance", acceptance)):
        request = replace(example.bundle.request, profile=replace(example.bundle.request.profile, source_request=source))
        retain("set/wrapper_" + name, "set", bundle((base,), request=request))

    def amount(identity="amount", subject=base, quantity=1, roles=(), preparation="preparation"):
        return ExperimentalAmount(identity, subject.id, subject.fingerprint, preparation, roles, quantity, "fixture_unit", f.provenance())

    for name, quantity in (("unknown", None), ("zero", 0), ("float_zero", 0.0), ("negative_zero", -0.0), ("integer", 1), ("float", 1.0), ("max_integer", (1 << 1024)-1)):
        retain("amount/" + name, "amount", amount(quantity=quantity))
    shared_set = retain("set/shared_roles", "set", bundle((base,), roles=(f.role(base), f.role(base, "helper", "helper"))))
    shared_amount = retain("amount/shared_roles", "amount", amount(roles=("payload", "helper")))
    retain("amount/sorted_roles", "amount", shared_amount, edits=[edit(["role_instance_ids"], ["payload", "helper"])])
    artifact = retain("artifact/plain", "artifact", CircuitMoleculeRecord(plain_set, (amount(),), {"run_id": "one"}))
    retain("artifact/run_changed", "artifact", replace(artifact, run_metadata={"run_id": "two"}))
    retain("artifact/amount_changed", "artifact", replace(artifact, experimental_amounts=(amount(quantity=2),)))
    relation("artifact/plain", "artifact/run_changed", equal=("nominal_bundle_identity", "experimental_specification_identity"), different=("artifact_fingerprint",))
    relation("artifact/plain", "artifact/amount_changed", equal=("nominal_bundle_identity",), different=("experimental_specification_identity",))
    retain("artifact/shared_roles", "artifact", CircuitMoleculeRecord(shared_set, (shared_amount,), {}))
    alias_artifact = retain("artifact/alias_preparations", "artifact", CircuitMoleculeRecord(alias_set,
        (amount("first", base), amount("second", alias, preparation="separate")), {}))
    retain("artifact/homomer", "artifact", CircuitMoleculeRecord(homomer_set, (amount("free"), amount("dimer", homomer)), {}))
    changed_request = deepcopy(example.bundle.request.to_dict())
    changed_request["profile"]["source_request"]["acceptance"]["shutdown"]["controllability"]["limitations"] = "Different unresolved source obligation."
    retain("artifact/source_obligation", "artifact", replace(example, bundle=replace(example.bundle, request=CircuitRequest.from_dict(changed_request))))
    relation("artifact/full_example", "artifact/source_obligation", equal=("nominal_bundle_identity",), different=("experimental_specification_identity", "artifact_fingerprint"))

    case_b_pointers = []
    for variant in ("base", "parameter-default", "parameter-override"):
        raw = json.loads((ROOT / "tests/conformance/case-b" / variant / "candidate.json").read_bytes())
        for suffix, keys, kind in (("root", ["construction", "request", "sources", 0, "molecule"], "molecule"),
                                  ("set", ["construction", "candidate", "bundle"], "set"),
                                  ("final", ["construction", "candidate", "bundle", "molecules", 0], "molecule")):
            value = raw
            for key in keys:
                value = value[key]
            identity = "case_b/" + variant + "/" + suffix
            retain(identity, kind, value, origin="retained_case_b_authority")
            case_b_pointers.append(dict(id=identity, variant=variant, path=keys))

    # Every schema rejects omitted fields, unknown fields, and unknown versions.
    for kind in KINDS:
        representative = next(item for item in records if item["kind"] == kind)
        raw = documents[representative["document_id"]]
        for key in raw:
            reject("fields/" + kind + "/missing/" + key, representative["id"], [dict(op="remove", path=[key])], "missing_field")
        reject("fields/" + kind + "/extra", representative["id"], [edit(["verified"], True)], "unknown_field")
        reject("fields/" + kind + "/schema", representative["id"], [edit(["schema_version"], "future")], "unsupported_schema")
    for name, field, value in (("empty_sequence", "sequence", ""), ("alphabet", "sequence", "ACGT"),
                               ("length", "sequence", "ACG"), ("form", "form", "delivered_dna"),
                               ("coding", "coding_status", "inapplicable"), ("assembly_empty", "assembly", [])):
        reject("molecule/" + name, "molecule/plain", [edit([field], value)], "invalid_molecule")
    reject("molecule/circle_core", "molecule/circle", [edit(["sequence_extent"], "exact_core")], "invalid_molecule")
    reject("molecule/coding_feature", "molecule/features", [edit(["coding_status"], "noncoding")], "invalid_molecule")
    reject("molecule/assembly_reordered", "molecule/partitioned", [edit(["assembly"], list(reversed(partitioned.to_dict()["assembly"])))], "invalid_molecule")
    reject("molecule/assembly_duplicate", "molecule/partitioned", [edit(["assembly", 1, "id"], partitions[0].id)], "invalid_molecule")
    reject("molecule/assembly_reverse", "molecule/plain", [edit(["assembly", 0, "destination", "strand"], "-")], "invalid_molecule")
    reject("molecule/source_frame_conflict", "molecule/plain", [edit(["assembly", 0, "source_space", "id"], base.space.id),
        edit(["assembly", 0, "source_path", "space_id"], base.space.id), edit(["assembly", 0, "source_space", "length"], 5)], "invalid_molecule")
    reject("molecule/feature_duplicate", "molecule/features", [edit(["features", 1, "id"], with_features.features[0].id)], "invalid_molecule")
    for value in (True, 1.0, -1, 3):
        reject("feature/frame_" + repr(value), "feature/unknown", [edit(["reading_frame"], value)], "invalid_type" if type(value) in (bool, float) else "invalid_molecule")
    for value in (True, 1.0, 0, -1, 1_000_001):
        reject("constituent/count_" + repr(value), "constituent/one", [edit(["stoichiometry"], value)], "invalid_type" if type(value) in (bool, float) else "invalid_molecular_complex")
    reject("complex/monomer", "complex/homomer", [edit(["constituents", 0, "stoichiometry"], 1)], "invalid_molecular_complex")
    reject("complex/empty", "complex/homomer", [edit(["constituents"], [])], "invalid_molecular_complex")
    reject("complex/duplex_count", "complex/duplex", [edit(["constituents", 0, "stoichiometry"], 2)], "invalid_molecular_complex")
    reject("role/abstract", "role/helper", [edit(["compartment"], "abstract")], "invalid_molecular_role")
    reject("role/stale_hash_spelling", "role/helper", [edit(["subject_fingerprint"], "A" * 64)], "invalid_molecular_fingerprint")
    reject("mapping/unknown_relation", "mapping/slice", [edit(["relation"], "verified_translation")], "invalid_form_mapping")
    for name, edits in (("missing_payload", [edit(["role_instances", 0, "purpose"], "helper")]),
                         ("missing_subject", [edit(["role_instances", 0, "subject_id"], "missing")]),
                         ("stale_subject", [edit(["role_instances", 0, "subject_fingerprint"], "b" * 64)]),
                         ("target_compartment", [edit(["role_instances", 0, "compartment"], "not_a_target_compartment")])):
        reject("set/" + name, "set/plain", edits, "invalid_molecule_set")
    reject("set/stale_constituent", "set/homomer", [edit(["complexes", 0, "constituents", 0, "molecule_fingerprint"], "b" * 64)], "invalid_molecule_set")
    reject("set/mapping_stale", "set/mapping", [edit(["form_mappings", 0, "source_molecule_fingerprint"], "b" * 64)], "invalid_molecule_set")
    reject("set/mapping_missing", "set/mapping", [edit(["form_mappings", 0, "source_molecule_id"], "missing")], "invalid_molecule_set")
    reject("set/duplicate_destination", "set/alias", [edit(["molecules", 1], alias_set.molecules[0].to_dict()),
        edit(["molecules", 1, "id"], "different_record")], "invalid_molecule_set")
    for name, quantity, code in (("bool", True, "invalid_type"), ("negative", -1, "invalid_experimental_amount"),
                                 ("negative_float", -0.1, "invalid_experimental_amount"), ("too_large", 1 << 1024, "invalid_experimental_amount")):
        reject("amount/" + name, "amount/integer", [edit(["quantity"], quantity)], code)
    reject("amount/duplicate_role", "amount/shared_roles", [edit(["role_instance_ids"], ["payload", "payload"])], "invalid_experimental_amount")
    reject("artifact/stale_amount", "artifact/plain", [edit(["experimental_amounts", 0, "subject_fingerprint"], "b" * 64)], "invalid_molecule_artifact")
    reject("artifact/alias_preparation", "artifact/alias_preparations", [edit(["experimental_amounts", 1, "preparation_id"], "preparation")], "invalid_molecule_artifact")
    reject("artifact/missing_role", "artifact/plain", [edit(["experimental_amounts", 0, "role_instance_ids"], ["missing"])], "invalid_molecule_artifact")
    reject("artifact/metadata_array", "artifact/plain", [edit(["run_metadata"], [])], "invalid_type")
    reject("artifact/metadata_limit", "artifact/plain", [edit(["run_metadata"], {str(i): None for i in range(129)})], "molecular_resource_limit")

    coverage = dict(record_kinds=sorted(KINDS), record_count=len(records), rejection_count=len(rejections),
        relation_count=len(relations), forms=sorted(FORMS), mapping_relations=sorted(MAPPING_RELATIONS),
        source_request_kinds=["build_request", "human_behavior_request", "human_deployment_request", "human_acceptance_request"],
        case_b=case_b_pointers, original_integration_tests=35,
        rejection_codes=dict(sorted(Counter(item["expected_code"] for item in rejections).items())))
    return dict(schema_version=SCHEMA, claim_scope="Declared molecular identity only; no assembly, source correspondence, empirical function or admission.",
                documents=documents, records=records, rejections=rejections, relations=relations, coverage=coverage)


def check_corpus(corpus):
    require(corpus["schema_version"] == SCHEMA, "Wrong molecular corpus schema")
    ids = [item["id"] for item in corpus["records"] + corpus["rejections"]]
    require(len(ids) == len(set(ids)), "Duplicate molecular corpus identity")
    coverage = corpus["coverage"]
    require(coverage["record_kinds"] == sorted(KINDS), "Missing molecular record kind")
    for key, values in (("record_count", corpus["records"]), ("rejection_count", corpus["rejections"]), ("relation_count", corpus["relations"])):
        require(coverage[key] == len(values), "Stale molecular coverage count")
    results = {}
    for case in corpus["records"]:
        document = corpus["documents"][case["document_id"]]
        require(fingerprint(document) == case["document_id"], "Molecular document identity mismatch")
        value = KINDS[case["kind"]].from_dict(apply_edits(document, case["edits"]))
        require(encoded(value.to_dict()) == encoded(document), "Wrong normalized molecular document")
        require(encoded(summary(value)) == encoded(case["expected"]), "Wrong molecular identity expectation")
        results[case["id"]] = summary(value)
    for case in corpus["rejections"]:
        document = corpus["documents"][case["document_id"]]
        try:
            KINDS[case["kind"]].from_dict(apply_edits(document, case["edits"]))
        except SerializationError:
            pass
        else:
            raise AssertionError("Accepted molecular rejection " + case["id"])
    for relation in corpus["relations"]:
        left, right = results[relation["left"]], results[relation["right"]]
        for key in relation["equal"]:
            require(encoded(left[key]) == encoded(right[key]), "Wrong molecular equality relation")
        for key in relation["different"]:
            require(encoded(left[key]) != encoded(right[key]), "Wrong molecular inequality relation")
    pending, count = [(corpus, 0)], 0
    while pending:
        value, depth = pending.pop()
        count += 1
        require(count <= 250_000 and depth <= 128, "Whole molecular corpus exceeds JSON budget")
        if isinstance(value, dict):
            pending.extend((item, depth + 1) for pair in value.items() for item in pair)
        elif isinstance(value, list):
            pending.extend((item, depth + 1) for item in value)
        elif isinstance(value, str):
            require(len(value.encode()) <= 4 * 1024 * 1024, "Corpus string limit")
    require(len(encoded(corpus)) <= 16 * 1024 * 1024, "Corpus byte limit")
    require(b"/Users/" not in encoded(corpus), "Machine-specific source coordinates")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    corpus = build_corpus()
    check_corpus(corpus)
    content = encoded(corpus)
    if args.write:
        CORPUS.write_bytes(content)
    else:
        require(CORPUS.read_bytes() == content, "Molecular corpus drifted; inspect before --write")
    print(json.dumps({"records": len(corpus["records"]), "rejections": len(corpus["rejections"]),
                      "relations": len(corpus["relations"]), "bytes": len(content)}, sort_keys=True))


if __name__ == "__main__":
    main()

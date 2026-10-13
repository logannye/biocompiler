"""Prepare the explicit CAR197/206 RNA adaptation from retained public originals.

Offline maintainer preparation, not a compiler or biological validator. Produces
one complete ResearchProject original for the existing controlled workflow, never
an accepted FASTA payload. Every designed region and scenario premise is explicit.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

from biocompiler.core_client import encode_json
from biocompiler.ir.circuit_construction import MemberRequirement, OutputMember, RoleDeclaration, RootSource, ValueRef
from biocompiler.ir.circuit_molecules import AssemblyOrigin, CircuitMolecule, MoleculeFeature
from biocompiler.ir.circuit_payloads import PayloadStructureContract, RequiredPayloadRegion
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.molecule_chemistry import BaseModification, ChemicalIdentity, ChemistryClaim, MoleculeChemistry, TailDeclaration, TailLength
from biocompiler.ir.molecule_records import DeclarationProvenance
from biocompiler.ir.payload_contracts import PayloadTemplate
from biocompiler.policy.car_reference import REFERENCE_SHA256, reference_data
from biocompiler.policy.project_sources import inspect_project_sources
from biocompiler.policy.research_project import ResearchProject
from biocompiler.semantics.molecule_coordinates import CoordinatePath, CoordinateSpace, IndexSpan
from tools import check_car_rm61461_reference as utr_check
from tools import import_controlled_car_reference as fragments
from tools.controlled_car_workflow import prepare_workflow

ROOT = Path(__file__).resolve().parents[1]
DESIGN = "car197206-rna-v1"
EXPECTED = ROOT / "data/car_controlled_reference/rna-adaptation-expected.json"
CONTRACT = ROOT / "data/car_controlled_reference/controller-readout-contract.json"
EXPECTED_SHA256 = "0d99c83fed06166de5ba8ccc718f9e544c0dc2328bac55f8b8d9911fad763b86"
CONTRACT_SHA256 = "9778b47fd2bf31caf66148b5ca3f9faa31173e19bdfa5adb14c7c66cf506bde7"
CATALOG_SHA256 = "7fe04c5c881eec85e64d50fd8604c1bd0fc7d050a146c4c6c1fcbfc9ccc519e3"
CATALOG_BYTES = 553_980
CATALOG_URL = "https://takara.co.kr/file/manual/pdf/heteroCitations_FL_633289_0212_IN.pdf"
SOURCE_IDS = ("WO2014127261A1", "US20150368342A1", "controlled.figure-transcription", "controlled.listing-transcription")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pinned(path, digest, size=None):
    raw = fragments._read(path, size or fragments.MAX_JSON_BYTES)
    require(sha(raw) == digest and (size is None or len(raw) == size), "Original source identity differs: " + str(path))
    return raw


def _source(identity, raw, locator, role, version="1"):
    return {"id": identity, "locator": locator, "version": version, "sha256": sha(raw),
            "role": role, "reuse_terms": "Explicit local source input; redistribution and patent permission remain unassessed."}


def _pin(row):
    return PinnedIdentity("source", row["id"], row["version"], row["sha256"])


def _path(space, start, end):
    return CoordinatePath(space, (IndexSpan(start, end),), "+")


def check_originals(expected, originals, xml):
    supplied = {**originals, utr_check.XML_NAME: xml}
    rows = expected["original_input_pins"]
    require(len(rows) == len(supplied) and {row["name"] for row in rows} == set(supplied),
            "Independent original input census differs")
    for row in rows:
        raw = supplied[row["name"]]
        require(len(raw) == row["bytes"] and sha(raw) == row["sha256"],
                "Original differs from independent expectation: " + row["name"])


def assemble_material(figures, reference, source_records):
    """Apply exactly the declared cross-source design; no optimization or defaults.

    The caller first checks immutable originals. The independent expectation
    comparison below is separate from construction and cannot be repinned here.
    """
    sources = {row["id"]: _pin(row) for row in source_records}
    design = sources["controlled.car197206.adaptation"]
    original = tuple(sources[key] for key in SOURCE_IDS)
    region_sources = (sources["WO2025096878.sequence-listing"], sources["WO2025096878A9"])
    design_provenance = DeclarationProvenance("declared", (design,), "car197206-rna-v1 complete nominal adaptation",
        "Designer-selected transcript context and chemistry. This complete controlled RNA pair was not reported in the source studies.")
    coding_provenance = DeclarationProvenance("declared", (*original, design), "WO Figures8/9; separate US printed listing; explicit single UAA termination",
        "Literal coding fragments, tags and linkers retained; T-to-U spelling and added UAA are explicit adaptation choices. Manual source reading remains trusted.")
    utr_provenance = DeclarationProvenance("declared", (*region_sources, design), "SEQ11, SEQ34 and SEQ151[1666,1776)",
        "Whole published untranslated regions and encoded 110-A tail transplanted into a new design; performance does not transfer.")
    chemistry_provenance = DeclarationProvenance("declared", (*region_sources, design), "Designer adopts A9[00408] nominal chemistry; explicit designer 3prime hydroxyl",
        "All chemistry is designer-specified for this adaptation, not a measured batch or source-reported property of these two RNAs.")
    records = reference["source_records"]
    utr5, utr3 = records["11"]["rna_sequence"], records["34"]["rna_sequence"]
    tail = records["151"]["rna_sequence"][1666:1776]
    require(len(utr5) == 79 and len(utr3) == 126 and tail == "A" * 110 and utr5.startswith("AG"),
            "Published intact region identities differ")
    by_id = {row["id"]: row for row in figures["records"]}
    roots, outputs, requirements, structures, members = [], [], [], [], []
    for construct, order in fragments.ORDER.items():
        member = "car" + construct
        dna = "".join(by_id[key]["dna"] for key in order)
        protein = "".join(by_id[key]["protein"] for key in order)
        rna = utr5 + dna.replace("T", "U") + "UAA" + utr3 + tail
        coding_end, utr_end = 79 + len(dna) + 3, len(rna) - 110
        regions = (("utr5", "five_prime_utr", 0, 79, utr_provenance),
                   ("cds", "coding_sequence", 79, coding_end, coding_provenance),
                   ("utr3", "three_prime_utr", coding_end, utr_end, utr_provenance),
                   ("poly_a", "poly_a_tail", utr_end, len(rna), utr_provenance))
        root_space = CoordinateSpace(member + ".root.frame", "RNA", len(rna), "linear", "5prime_to_3prime")
        external = CoordinateSpace(member + ".designer.frame", "RNA", len(rna), "linear", "5prime_to_3prime")
        cap = ChemicalIdentity("design.nominal_chemistry", "m7G_5prime_ppp_5prime_2primeOMeA_pG", "1")

        def chemistry(space_id):
            return MoleculeChemistry(
                cap=ChemistryClaim("declared", cap, chemistry_provenance),
                start_end=ChemistryClaim("declared", cap, chemistry_provenance),
                finish_end=ChemistryClaim("declared", ChemicalIdentity("design.nominal_chemistry", "3prime_hydroxyl", "1"), design_provenance),
                modifications=(
                    BaseModification("all_uridines", ChemicalIdentity("biocompiler.chemical", "n1_methylpseudouridine", "1"), "U", "all_matching_bases", (), chemistry_provenance),
                    BaseModification("cap_adjacent_adenosine", ChemicalIdentity("design.nominal_chemistry", "2prime_O_methyladenosine", "1"), "A", "positions", (0,), chemistry_provenance)),
                modification_inventory_status="declared", modification_inventory_provenance=chemistry_provenance,
                terminal_tail=TailDeclaration("declared", "represented_terminal", TailLength("exact", exact=110),
                    _path(space_id, utr_end, len(rna)), utr_provenance))

        molecule = CircuitMolecule(member + ".original", "delivered_rna", root_space, rna, "complete", "coding",
            (AssemblyOrigin(member + ".designed_origin", _path(root_space.id, 0, len(rna)), external,
                _path(external.id, 0, len(rna)), design_provenance),),
            tuple(MoleculeFeature(id=name, kind=kind, path=_path(root_space.id, start, end),
                reading_frame=0 if name == "cds" else None, provenance=provenance)
                for name, kind, start, end, provenance in regions), chemistry(root_space.id), design_provenance)
        roots.append(RootSource(member + ".input", molecule, design_provenance))
        outputs.append(OutputMember(member, ValueRef("root", member + ".input"), member + ".output.frame", "delivered_rna", "complete", "coding", design_provenance))
        requirements.append(MemberRequirement(member + ".payload", "payload", member, None, None,
            (RoleDeclaration(member + ".rna", member, "requested_payload", "cytoplasm"),)))
        structures.append(PayloadStructureContract(member, "delivered_rna", "linear",
            tuple(RequiredPayloadRegion(name, kind) for name, kind, _, _, _ in regions), design_provenance))
        product_body = {"schema_version": "biocompiler.policy_mrna_product_content.v0.1", "alphabet": "protein", "sequence_extent": "complete", "sequence": protein}
        identity = PinnedIdentity("reference", "WO2014127261A1.construct" + construct, "1", sha(encode_json(product_body)))
        members.append({"id": member, "regions": {name: name for name, _, _, _, _ in regions},
            "chemistry": chemistry(member + ".output.frame").to_dict(),
            "product": {"identity": identity.to_dict(), "sequence": protein,
                "translation_policy": {"schema_version": "biocompiler.translation_policy.v0.1", "profile": "ordinary_cds", "genetic_code": "ncbi_standard_v1", "recodings": []},
                "provenance": coding_provenance.to_dict()}})
    template = PayloadTemplate("car197206.nominal_adaptation", tuple(roots), (), tuple(outputs), tuple(requirements), payload_structures=tuple(structures))
    return {"schema_version": "biocompiler.policy_mrna_structure_authority.v0.1", "profile": "biocompiler.policy_mrna_completeness.v0.1",
            "template": template.to_dict(), "member_order": ["car197", "car206"], "members": members}


def check_expected(material, expected):
    """Compare complete designs to the separately prepared fixed molecular oracle."""
    # This checker is only a preparation guard; native reconstruction remains
    # independent and mandatory before accepted material export.
    roots = material["template"]["sources"]
    require(material["member_order"] == ["car197", "car206"] and len(roots) == len(material["members"]) == 2,
            "Expected exactly the original ordered pair")
    for root, member, oracle in zip(roots, material["members"], expected["members"], strict=True):
        molecule, protein = root["molecule"], member["product"]["sequence"]
        rna = molecule["sequence"]
        require(member["id"] == oracle["id"] and root["id"] == oracle["id"] + ".input", "Reference member order differs")
        require(len(rna) == oracle["rna_nt"] and sha(rna.encode()) == oracle["rna_sha256"], "Complete RNA differs from independent expectation")
        require(len(protein) == oracle["protein_aa"] and sha(protein.encode()) == oracle["protein_sha256"], "Protein differs from independent expectation")
        require(member["product"]["identity"]["content_fingerprint"] == oracle["product_content_fingerprint"], "Product content pin differs from independent expectation")
        regions = {row["role"]: row for row in oracle["regions"]}
        for region in regions.values():
            require(sha(rna[region["start"]:region["end"]].encode()) == region["rna_sha256"], "Region differs from independent expectation")
        extents = {"utr5": (0, 79), "cds": (79, regions["single_stop"]["end"]),
                   "utr3": (regions["three_prime_utr"]["start"], regions["three_prime_utr"]["end"]),
                   "poly_a": (regions["encoded_poly_a"]["start"], oracle["rna_nt"])}
        features = {row["id"]: row for row in molecule["features"]}
        require(len(molecule["features"]) == 4 and set(features) == set(extents), "Region inventory differs")
        kinds = {"utr5": "five_prime_utr", "cds": "coding_sequence", "utr3": "three_prime_utr", "poly_a": "poly_a_tail"}
        for name, (start, end) in extents.items():
            path = features[name]["path"]
            require(path == _path(molecule["space"]["id"], start, end).to_dict(), "Declared region coordinates differ")
            require(features[name]["kind"] == kinds[name] and features[name]["reading_frame"] == (0 if name == "cds" else None),
                    "Declared region meaning differs")
        require(member["product"]["translation_policy"] == {"schema_version": "biocompiler.translation_policy.v0.1", "profile": "ordinary_cds",
                "genetic_code": "ncbi_standard_v1", "recodings": []}, "Translation policy differs")
        require(member["regions"] == {name: name for name in extents}, "Member region mapping differs")
        require(rna[regions["single_stop"]["start"]:regions["single_stop"]["end"]] == "UAA", "Single designer termination differs")
        for chemistry, space in ((molecule["chemistry"], molecule["space"]["id"]),
                                 (member["chemistry"], member["id"] + ".output.frame")):
            for name, accession in (("cap", "m7G_5prime_ppp_5prime_2primeOMeA_pG"),
                                    ("start_end", "m7G_5prime_ppp_5prime_2primeOMeA_pG"),
                                    ("finish_end", "3prime_hydroxyl")):
                claim = chemistry[name]
                require(claim["status"] == "declared" and claim["identity"]["accession"] == accession,
                        "Nominal chemistry identity differs")
                require(any(pin["id"] == "controlled.car197206.adaptation" for pin in claim["provenance"]["authority"]),
                        "Adapted chemistry lacks explicit design authority")
            mods = chemistry["modifications"]
            require(chemistry["modification_inventory_status"] == "declared" and len(mods) == 2 and
                [(m["canonical_base"], m["identity"]["accession"], m["scope"], m["positions"]) for m in mods] ==
                [("U", "n1_methylpseudouridine", "all_matching_bases", []),
                 ("A", "2prime_O_methyladenosine", "positions", [0])], "Nominal modification inventory differs")
            tail = chemistry["terminal_tail"]
            require(tail["status"] == "declared" and tail["placement"] == "represented_terminal" and
                    tail["length"] == TailLength("exact", exact=110).to_dict() and
                    tail["path"] == _path(space, *extents["poly_a"]).to_dict(), "Exact encoded tail differs")
        normalized = json.loads(json.dumps(member["chemistry"]))
        normalized["terminal_tail"]["path"]["space_id"] = molecule["space"]["id"]
        require(normalized == molecule["chemistry"], "Root/output chemistry correspondence differs")


def prepare(*, inputs, original_xml, reference_pdf, controller_catalog, design):
    require(design == DESIGN, "Select the explicit car197206-rna-v1 design and its declared assumptions")
    expected_raw = pinned(EXPECTED, EXPECTED_SHA256)
    contract_raw = pinned(CONTRACT, CONTRACT_SHA256)
    expected, contract = fragments.decode(expected_raw), fragments.decode(contract_raw)
    inventory_raw, pins, originals = fragments.load_inputs(inputs)
    figures, listing = (fragments.decode(originals[name]) for name in fragments.ENTRIES)
    fragments.reconstruct(figures, listing, pins)
    reference = reference_data()
    reference_raw = pinned(ROOT / "src/biocompiler/policy/data/car_rm61461_reference_v01.json", REFERENCE_SHA256)
    xml = pinned(original_xml, utr_check.XML_SHA256, utr_check.XML_BYTES)
    check_originals(expected, originals, xml)
    utr_check.check_reference(reference, xml)
    pdf = pinned(reference_pdf, reference["sources"]["pdf"]["sha256"], reference["sources"]["pdf"]["bytes"])
    catalog = pinned(controller_catalog, CATALOG_SHA256, CATALOG_BYTES)
    require(pdf.startswith(b"%PDF-") and catalog.startswith(b"%PDF-"), "Original source lacks PDF signature")
    source_bytes = dict(zip(SOURCE_IDS, (originals[name] for name in fragments.INPUTS)))
    source_bytes.update({"controlled.acquisition.inventory": inventory_raw, "car.rm61461.reference_pack": reference_raw,
        "WO2025096878.sequence-listing": xml, "WO2025096878A9": pdf,
        "controlled.car197206.adaptation": expected_raw, "controlled.car197206.contract": contract_raw})
    locators = {
        "WO2014127261A1": "https://patents.google.com/patent/WO2014127261A1/en",
        "US20150368342A1": "https://patents.google.com/patent/US20150368342A1/en",
        "controlled.figure-transcription": "authorized-input:patent-domain-transcription.json",
        "controlled.listing-transcription": "authorized-input:patent-listing-transcription.json",
        "controlled.acquisition.inventory": "repository:data/car_controlled_reference/source-inventory.json",
        "car.rm61461.reference_pack": "package:biocompiler.policy/data/car_rm61461_reference_v01.json",
        "WO2025096878.sequence-listing": utr_check.ZIP_URL + "#" + utr_check.XML_NAME,
        "WO2025096878A9": utr_check.PDF_URL,
        "controlled.car197206.adaptation": "repository:data/car_controlled_reference/rna-adaptation-expected.json",
        "controlled.car197206.contract": "repository:data/car_controlled_reference/controller-readout-contract.json"}
    source_records = [_source(identity, raw, locators[identity], "Original source or explicit adaptation/scenario authority; biological applicability separately unassessed",
                              version=contract["version"] if identity == "controlled.car197206.contract" else "1")
                      for identity, raw in source_bytes.items()]
    assets = {row["source_id"]: row for row in contract["source_assets"]}
    require(set(assets) == {"wu-linked-patent-WO2014127261A1.html", "wu-2015-pmc.html", "clontech-heterodimerization-citations-2012.pdf"},
            "Controller/readout original source census differs")
    for row in contract["sources"]:
        identity, asset = row["id"], assets[row["id"]]
        require(identity not in source_bytes and asset["asset_name"] == identity, "Source binding differs")
        if identity == "clontech-heterodimerization-citations-2012.pdf":
            raw = catalog
            require(sha(raw) == row["sha256"] and len(raw) == asset["size_bytes"], "Catalog source binding differs")
        else:
            raw = pinned(Path(inputs) / identity, row["sha256"], asset["size_bytes"])
        source_bytes[identity] = raw
        source_records.append(row)
    material = assemble_material(figures, reference, source_records)
    check_expected(material, expected)
    workflow = prepare_workflow(material_authority=material, source_records=source_records, contract=contract)
    project = ResearchProject.from_controlled(workflow)
    inspection = inspect_project_sources(project, source_bytes)
    return project, {"project": asdict(project.preflight()), "sources": asdict(inspection),
        "design": DESIGN, "rna_lengths": [len(root["molecule"]["sequence"]) for root in material["template"]["sources"]],
        "empirical_status": "unassessed", "native_status": "not_run", "output_kind": "complete_original_research_project_not_accepted_payload"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "original-xml", "reference-pdf", "controller-catalog", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--design", required=True, choices=[DESIGN])
    args = parser.parse_args(argv)
    try:
        project, report = prepare(inputs=args.inputs, original_xml=args.original_xml,
            reference_pdf=args.reference_pdf, controller_catalog=args.controller_catalog, design=args.design)
        project.dump(args.output)
        print(json.dumps(report, sort_keys=True, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print("Controlled CAR reference preparation rejected: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

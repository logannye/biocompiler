"""Author the first complete CAR reference design under explicit supplied premises.

This module copies qualified public sequence data. It never invents a missing
sequence, runs a compiler, optimizes bases, or grants biological acceptance.
The required terminal-chemistry argument is a design choice, not a source fact.
"""
from __future__ import annotations

import hashlib
from importlib.resources import files
from typing import Literal, cast

from biocompiler.core_client import JsonValue, decode_json, encode_json
from biocompiler.ir.circuit_construction import MemberRequirement, OutputMember, RoleDeclaration, RootSource, ValueRef
from biocompiler.ir.circuit_molecules import AssemblyOrigin, CircuitMolecule, MoleculeFeature
from biocompiler.ir.circuit_payloads import PayloadStructureContract, RequiredPayloadRegion
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.molecule_chemistry import BaseModification, ChemicalIdentity, ChemistryClaim, MoleculeChemistry, TailDeclaration, TailLength
from biocompiler.ir.molecule_records import DeclarationProvenance
from biocompiler.ir.payload_contracts import PayloadTemplate
from biocompiler.semantics.molecule_coordinates import CoordinatePath, CoordinateSpace, IndexSpan
from . import model as p
from .serialization import to_data
from .expression_material import ExpressionBudgets, ExpressionMaterialRequest, ExpressionSelection

REFERENCE_SHA256 = "dcf0b3fe174ee48f68623785663b16ce96ce87ad2bbacbd851369e9ba1b46079"
RNA_SHA256 = "7a0e872d51987d1c0064accb5197e605943d90ea2c20104d86e9f41f12617335"
PROTEIN_SHA256 = "833bd17e675e9595d01865a0109c9c795d2ba8b78481ab06f12da043019e404d"


def _data(value: p.Record) -> JsonValue:
    """Bridge the source serializer's equivalent JSON alias explicitly."""
    return cast(JsonValue, to_data(value))


def _hash(value: JsonValue) -> str:
    return hashlib.sha256(encode_json(value)).hexdigest()


def _record(value: JsonValue) -> dict[str, JsonValue]:
    if type(value) is not dict:
        raise ValueError("Expected the complete pinned reference record")
    return value


def reference_data() -> dict[str, JsonValue]:
    """Return a detached copy of the pinned factual pack, with no evidence upgrade."""
    raw = files("biocompiler.policy").joinpath("data/car_rm61461_reference_v01.json").read_bytes()
    if len(raw) > 128_000 or hashlib.sha256(raw).hexdigest() != REFERENCE_SHA256:
        raise ValueError("Installed CAR reference differs from its reviewed complete identity")
    return _record(decode_json(raw))


def _pin(kind: str, identity: str, body: JsonValue) -> PinnedIdentity:
    return PinnedIdentity(kind, identity, "1", _hash(body))


def _nominal_definitions() -> tuple[p.SemanticDefinition, p.SemanticDefinition, p.SemanticDefinition]:
    # Native admission requires these exact versioned bodies. Cross-language
    # hosted controls check them; Python definitions never grant interpretation.
    return (
        p.SemanticDefinition("biocompiler.expression.objective.v1", "1", "requirement",
            "Exact source-selected complete product encoding and supplied conditional localization for one declared human immune recipient; no empirical expression or therapeutic function is established."),
        p.SemanticDefinition("biocompiler.expression.encode.v1", "1", "operation",
            "Construct one complete original mRNA encoding the exact supplied product under the explicit expression/localization contract; no runtime action or biological realization is inferred."),
        p.SemanticDefinition("biocompiler.expression.nominal_translation.v1", "1", "model",
            "Decode the explicitly declared canonical parent RNA bases with the standard genetic code and the selected one or two consecutive terminal stop codons; this nominal correspondence does not establish physical translation of modified nucleotides or biological expression."),
    )


def _material(reference: dict[str, JsonValue], terminal_design: p.SemanticDefinition) -> tuple[dict[str, JsonValue], PinnedIdentity]:
    records = _record(reference["source_records"])
    rna = cast(str, _record(records["151"])["rna_sequence"])
    protein = cast(str, _record(records["2"])["original_literal"]).upper()
    if len(rna) != 1776 or hashlib.sha256(rna.encode("ascii")).hexdigest() != RNA_SHA256:
        raise ValueError("Complete reference RNA identity changed")
    if len(protein) != 485 or hashlib.sha256(protein.encode("ascii")).hexdigest() != PROTEIN_SHA256:
        raise ValueError("Complete reference protein identity changed")
    sources = _record(reference["sources"])
    xml = _record(sources["xml"])
    pdf = _record(sources["pdf"])
    xml_pin = PinnedIdentity("source", "WO2025096878.sequence-listing", "2024-10-28", cast(str, xml["sha256"]))
    pdf_pin = PinnedIdentity("source", "WO2025096878A9", "2025-07-10", cast(str, pdf["sha256"]))
    design_pin = _pin("source", terminal_design.id, _data(terminal_design))
    sequence_provenance = DeclarationProvenance("declared", (xml_pin, pdf_pin), "SEQ151; current A9 Figure3C",
        "Exact published nominal sequence and named source parts; no physical batch or human in-vivo acceptance.")
    chemistry_provenance = DeclarationProvenance("declared", (pdf_pin,), "current A9 [00408]",
        "Source-declared Cap-AG and complete uridine replacement; not measured batch chemistry.")
    design_provenance = DeclarationProvenance("declared", (design_pin,), "original source semantic definition " + terminal_design.id,
        "Explicit designer-supplied 3prime hydroxyl; the publication's actual terminal chemistry remains unassessed.")
    root_space = CoordinateSpace("rm61461.root.frame", "RNA", 1776, "linear", "5prime_to_3prime")
    external_space = CoordinateSpace("rm61461.listing.frame", "RNA", 1776, "linear", "5prime_to_3prime")
    def path(space_id: str, start: int, end: int) -> CoordinatePath:
        return CoordinatePath(space_id, (IndexSpan(start, end),), "+")
    cap_identity = ChemicalIdentity("WO2025096878A9.nominal_chemistry", "m7G_5prime_ppp_5prime_2primeOMeA_pG", "1")
    def chemistry(space_id: str) -> MoleculeChemistry:
        return MoleculeChemistry(
            cap=ChemistryClaim("declared", cap_identity, chemistry_provenance),
            start_end=ChemistryClaim("declared", cap_identity, chemistry_provenance),
            finish_end=ChemistryClaim("declared", ChemicalIdentity("design.nominal_chemistry", "3prime_hydroxyl", "1"), design_provenance),
            modifications=(
                BaseModification("all_uridines", ChemicalIdentity("biocompiler.chemical", "n1_methylpseudouridine", "1"),
                    "U", "all_matching_bases", (), chemistry_provenance),
                BaseModification("cap_adjacent_adenosine", ChemicalIdentity("WO2025096878A9.nominal_chemistry", "2prime_O_methyladenosine", "1"),
                    "A", "positions", (0,), chemistry_provenance)),
            modification_inventory_status="declared", modification_inventory_provenance=chemistry_provenance,
            terminal_tail=TailDeclaration("declared", "represented_terminal", TailLength("exact", exact=110),
                path(space_id, 1666, 1776), sequence_provenance))
    regions = (("utr5", "five_prime_utr", 0, 79), ("cds", "coding_sequence", 79, 1540),
               ("utr3", "three_prime_utr", 1540, 1666), ("poly_a", "poly_a_tail", 1666, 1776))
    molecule = CircuitMolecule("rm61461.original", "delivered_rna", root_space, rna, "complete", "coding",
        (AssemblyOrigin("rm61461.listed_origin", path(root_space.id, 0, 1776), external_space,
            path(external_space.id, 0, 1776), sequence_provenance),),
        tuple(MoleculeFeature(id=name, kind=kind, path=path(root_space.id, start, end),
            reading_frame=0 if name == "cds" else None, provenance=sequence_provenance) for name, kind, start, end in regions), chemistry(root_space.id), sequence_provenance)
    template = PayloadTemplate("rm61461.nominal_reference", (RootSource("rm61461.input", molecule, sequence_provenance),), (),
        (OutputMember("payload", ValueRef("root", "rm61461.input"), "rm61461.output.frame", "delivered_rna", "complete", "coding", sequence_provenance),),
        (MemberRequirement("rm61461.payload", "payload", "payload", None, None,
            (RoleDeclaration("rm61461.rna", "payload", "requested_payload", "cytoplasm"),)),),
        payload_structures=(PayloadStructureContract("payload", "delivered_rna", "linear",
            tuple(RequiredPayloadRegion(name, kind) for name, kind, _, _ in regions), sequence_provenance),))
    protein_body: JsonValue = {"schema_version": "biocompiler.policy_mrna_product_content.v0.1", "alphabet": "protein",
        "sequence_extent": "complete", "sequence": protein}
    product = _pin("reference", "WO2025096878.CAR2.SEQ2", protein_body)
    authority: dict[str, JsonValue] = {"schema_version": "biocompiler.policy_mrna_structure_authority.v0.1",
        "profile": "biocompiler.policy_mrna_completeness.v0.1", "template": template.to_dict(), "member_order": ["payload"],
        "members": [{"id": "payload", "regions": {name: name for name, _, _, _ in regions},
            "chemistry": chemistry("rm61461.output.frame").to_dict(),
            "product": {"identity": product.to_dict(), "sequence": protein,
                "translation_policy": {"schema_version": "biocompiler.translation_policy.v0.1", "profile": "ordinary_cds",
                    "genetic_code": "ncbi_standard_v1", "recodings": []}, "provenance": sequence_provenance.to_dict()}}]}
    return authority, product


def rm61461_request(*, maximum_rna_nt: int,
                    three_prime_end: Literal["designer_supplied_hydroxyl"],
                    budgets: ExpressionBudgets = ExpressionBudgets()) -> ExpressionMaterialRequest:
    """Prepare one exact published CAR reference with an explicit terminal choice.

    This is a complete nominal design under supplied expression/localization and
    recipient premises. Public ex-vivo observations do not establish those
    premises in human in-vivo deployment. Native compilation is a separate call.
    """
    if type(maximum_rna_nt) is not int or not 0 < maximum_rna_nt <= 1_000_000:
        raise ValueError("Maximum RNA length must be a positive bounded integer")
    if type(three_prime_end) is not str or three_prime_end != "designer_supplied_hydroxyl":
        raise ValueError("This reference requires an explicit designer-supplied terminal chemistry choice")
    reference = reference_data()
    objective, operation, translation = _nominal_definitions()
    terminal = p.SemanticDefinition("car.rm61461.terminal_design", "1", "model",
        "Designer specifies a 3prime hydroxyl on the nominal complete RNA; this is not a qualified fact about the publication's historical physical material.")
    authority, product = _material(reference, terminal)
    localization = p.SemanticDefinition("car.rm61461.surface_localization", "1", "spatial",
        "Supplied premise: the encoded complete CAR2 product is processed and displayed on the recipient T-cell surface. Sequence correspondence alone does not establish trafficking or display.")
    capability = p.SemanticDefinition("car.rm61461.translation_capability", "1", "capability",
        "Supplied human immune-cell translation capability; actual modified-RNA translation and expression remain empirically unassessed.")
    environment = p.SemanticDefinition("car.rm61461.human_environment", "1", "environment",
        "Intended human in-vivo immune-cell environment. The reference experiments were ex vivo; applicability, safety and clinical effect are unresolved.")
    delivery_def = p.SemanticDefinition("car.rm61461.delivery_premise", "1", "delivery",
        "Conditional premise that this RNA reaches and remains accessible to the declared recipient. No delivery vehicle, dose, tissue specificity, arrival or duration guarantee is supplied.")
    chassis_model = p.SemanticDefinition("car.rm61461.human_t_cell", "1", "model",
        "Declared human T-cell recipient identity. Expression in source-disclosed primary human T cells is contextual evidence, not proof of this in-vivo premise.")
    realization = p.SemanticDefinition("car.rm61461.expression_component", "1", "model",
        "Supplied conditional correspondence from exact complete RM_61461 nominal RNA to CAR2 encoding and declared surface localization; no temporal controller or antigen-dependent behavior is implemented.")
    evidence = p.SemanticDefinition("car.rm61461.reference_evidence", "1", "model",
        "Current corrected WO2025096878A9 and the pinned WIPO listing identify RM_61461, SEQ151 and CAR2 SEQ2. Human T-cell observations are patent-disclosed ex vivo; donor identity in Example3 conflicts. Full evidence/applicability limits remain in the independently pinned factual reference pack.")
    role = p.Role("recipient", (capability.ref,))
    parameters = (p.Parameter("product_id", p.TEXT, value=product.id), p.Parameter("product_version", p.TEXT, value=product.version),
        p.Parameter("product_sha256", p.TEXT, value=product.content_fingerprint), p.Parameter("localization", p.TEXT, value=localization.id),
        p.Parameter("maximum_rna_nt", p.INTEGER, value=maximum_rna_nt))
    requirement = p.Requirement("encode_car", "objective", "Encode the selected complete CAR2 product within the declared RNA length bound.",
        p.Scope("executor", p.declaration_ref(role)), applies_to=(p.declaration_ref(role), *(p.declaration_ref(value) for value in parameters)), contract=objective.ref)
    definitions = (objective, operation, translation, terminal, localization, capability, environment, delivery_def, chassis_model, realization, evidence)
    program = p.PolicyProgram("car.rm61461", p.SemanticBundle("car.rm61461.definitions", "1", definitions),
        (role, *parameters, requirement))
    chassis = p.ChassisProfile("human_t_cell", "1", "lymphoid", "T_cell", (), (), (capability.ref,), chassis_model.ref,
        (environment.ref,), ())
    deployment = p.Deployment("car.rm61461.deployment", (p.RoleBinding(p.declaration_ref(role), chassis),), (environment.ref,),
        p.DeliveryContract("car.rm61461.delivery", (p.declaration_ref(role),), delivery_def.ref, delivery_def.ref, delivery_def.ref,
            "none_required", delivery_def.ref), p.RNAConstraints(design_count=1, member_count=1, helper_count=0, orf_count=1, product_count=1))
    dependencies = (translation.ref, terminal.ref)
    entry = p.ImplementationBinding("car.rm61461.implementation", "1", operation.ref, realization.ref,
        (chassis.id,), ("RNA",), dependencies, (evidence.ref,))
    document = p.BuildRequest(program, deployment, p.ImplementationCatalogLock("car.rm61461.catalog", "1", (entry,)),
        p.AssuranceRequest((requirement.id,), "structural", "not_applicable"), profile=p.EXPRESSION_SOURCE_PROFILE)
    body: dict[str, JsonValue] = {"schema_version": "biocompiler.policy_expression_contract.v0.1",
        "operation": _data(operation.ref), "realization": _data(realization.ref), "product": product.to_dict(),
        "recipient": _data(chassis), "deployment": _data(deployment), "localization": _data(localization),
        "material": {"structure_sha256": _hash(authority), "member": "payload", "cds": "cds"},
        "translation": {"interpretation": "nominal_canonical_parent_bases", "terminal_stop_codons": 2, "model": _data(translation.ref)},
        "dependencies": [_data(value) for value in dependencies], "evidence": [_data(evidence.ref)],
        "claim_scope": "conditional_encoding_and_localization"}
    sources = _record(reference["sources"])
    pdf = _record(sources["pdf"])
    xml = _record(sources["xml"])
    source_records: list[JsonValue] = [
        {"id": "car.rm61461.reference_pack", "locator": "package:biocompiler.policy/data/car_rm61461_reference_v01.json", "version": "1",
         "sha256": REFERENCE_SHA256, "role": "qualified_nominal_reference_and_separate_applicability_limits", "reuse_terms": "public source access; no additional source permission inferred"},
        {"id": "WO2025096878.sequence-listing", "locator": cast(str, xml["archive_url"]) + "#" + cast(str, xml["member"]), "version": "2024-10-28",
         "sha256": xml["sha256"], "role": "complete_original_ST26_listing", "reuse_terms": "public WIPO source; affirmative reuse terms not identified"},
        {"id": "WO2025096878A9", "locator": pdf["url"], "version": "2025-07-10", "sha256": pdf["sha256"],
         "role": "current_corrected_publication_and_source_declared_chemistry", "reuse_terms": "public source access; patent or manufacturing permission not assessed"},
        {"id": terminal.id, "locator": "original:document/program/semantics/definitions/" + terminal.id, "version": "1",
         "sha256": _hash(_data(terminal)), "role": "explicit_designer_terminal_chemistry_choice", "reuse_terms": "user supplied nominal design premise"}]
    context: dict[str, JsonValue] = {"project_id": "car.rm61461.nominal", "title": "RM_61461 CAR nominal reference design",
        "sources": source_records, "assumptions": ["Expression, localization and delivery are supplied conditional premises, not verified biological guarantees.",
            "The 3prime hydroxyl is an explicit designer choice; published historical terminal chemistry remains unassessed.",
            "Nominal parent-base translation does not establish actual translation of modified nucleotides.",
            "Source observations remain ex vivo and patent-disclosed; human in-vivo and clinical applicability are unassessed."]}
    return ExpressionMaterialRequest(document=document,
        selection=ExpressionSelection(objective=requirement.id, recipient=role.id,
            implementation=_pin("registry", entry.id, _data(entry)).to_dict(), member="payload", cds="cds"),
        expression_contract={"identity": _pin("model", "car.rm61461.expression_contract", body).to_dict(), "body": body},
        structure_authority=authority, project_context=context, budgets=budgets)

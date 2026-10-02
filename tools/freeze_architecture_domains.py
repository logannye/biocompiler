"""Retain complete template, refinement, library and request declaration parity.

This source-only corpus imports supplied authority. No architecture producer,
matcher, construction executor or acceptance checker generates its expectations.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from biocompiler.errors import SerializationError
from biocompiler.ir.payload_contracts import PayloadTemplate
from biocompiler.ir.payload_architecture import PayloadArchitectureRefinement, PayloadArchitectureLibrary
from biocompiler.ir.architecture_build import PayloadArchitectureRequest
from biocompiler.ir.circuit_construction import CircuitConstructionRequest
from biocompiler.ir.serialization import fingerprint
from tests.test_payload_contracts import payload_template, executable_component

SCHEMA = "biocompiler.architecture_domains_conformance.v1"
CORPUS = ROOT / "tests/conformance/architecture-domains-v1.json"
KINDS = {"template": PayloadTemplate, "refinement": PayloadArchitectureRefinement,
         "library": PayloadArchitectureLibrary, "request": PayloadArchitectureRequest}
INVENTORIES = {"templates":"b1fc51bb61712319dc2189b357e8ed8d86dc547dff20fc435b48abc7a345e331",
               "architecture":"d7ff0be3f3e9e2190add53584a9079b74a22e385c4f90ebf095e3891884dd785"}
TEMPLATES = ROOT / "tests/conformance/payload-templates-v1.json"


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()


def edit(path, value):
    return {"op": "set", "path": path, "value": value}


def remove(path):
    return {"op": "remove", "path": path}


def apply_edits(raw, edits):
    raw = deepcopy(raw)
    for change in edits:
        container = raw
        for key in change["path"][:-1]:
            container = container[key]
        key = change["path"][-1]
        if change["op"] == "remove":
            del container[key]
        else:
            assert change["op"] == "set"
            if isinstance(container, list):
                assert 0 <= key < len(container)
            container[key] = deepcopy(change["value"])
    return raw


def inventory(corpus):
    return fingerprint({"records": sorted([item["id"], item["kind"], item["document"], item["edits"], item["normalized"]] for item in corpus["records"]),
                        "rejections": sorted([item["id"], item["kind"], item["document"], item["edits"], item["expected_code"]] for item in corpus["rejections"]),
                        "conversions": corpus["conversions"], "coverage": corpus["coverage"]})


def build_corpus():
    documents, records, rejections, conversions = {}, [], [], []
    def document(value):
        identity = fingerprint(value); documents[identity] = value; return identity
    def retain(identity, kind, raw, changes=()):
        raw = raw.to_dict() if hasattr(raw, "to_dict") else deepcopy(raw)
        parsed = KINDS[kind].from_dict(apply_edits(raw, changes))
        normalized = parsed.to_dict()
        records.append({"id": identity, "kind": kind, "document": document(raw), "edits": list(changes), "normalized": document(normalized)})
        return normalized
    def reject(identity, kind, raw, changes, code):
        raw = raw.to_dict() if hasattr(raw, "to_dict") else deepcopy(raw)
        try:
            KINDS[kind].from_dict(apply_edits(raw, changes))
        except SerializationError as exc:
            message = str(exc)
        else:
            raise AssertionError("Accepted intended rejection: " + identity)
        rejections.append({"id": identity, "kind": kind, "document": document(raw), "edits": list(changes), "expected_code": code, "python_error": message})
    def mutate(identity, kind, raw, path, value, code):
        reject(identity, kind, raw, [edit(path, value)], code)

    template = retain("template/direct_root", "template", payload_template())
    construction = json.loads((ROOT / "tests/conformance/construction-v1.json").read_bytes())
    recipes = {item["id"]: construction["documents"][item["document_id"]] for item in construction["records"] if item["kind"] == "request"}
    templates = {}
    for identity, request in recipes.items():
        if identity == "request/deferred_payload_structure":
            continue
        projected = {key: deepcopy(value) for key, value in request.items() if key not in {"circuit", "mode"}}
        projected["schema_version"] = PayloadTemplate.schema_version
        templates[identity] = retain("template/" + identity, "template", projected)
        # Projection is checked independently of Request; conversion is a
        # separate contextual operation, and retains the real supplied circuit.
        conversions.append({"id": identity, "template": document(projected), "request": document(request), "expected": "roundtrip"})
    deferred = recipes["request/deferred_payload_structure"]
    projected = {key: deepcopy(value) for key, value in deferred.items() if key not in {"circuit", "mode"}}
    projected["schema_version"] = PayloadTemplate.schema_version
    reject("template/payload_structure_missing_member", "template", projected, [], "invalid_payload_template")
    helper = deepcopy(template); helper["requirements"][0]["category"] = "delivered_helper"
    helper["requirements"][0]["roles"][0]["purpose"] = "helper"
    retain("template/helper_only", "template", helper)
    external = deepcopy(template)
    external["requirements"].append({"schema_version":"biocompiler.construction_member_requirement.v0.1", "id":"external", "category":"host_provider", "member_id":None,
        "external_id":"undeclared-provider", "external_fingerprint":"a" * 64,
        "roles":[{"schema_version":"biocompiler.construction_role_declaration.v0.1", "id":"external.role", "role":"foreign-role", "purpose":"host_provider", "compartment":"undeclared-compartment"}]})
    retain("template/source_independent_external_provider", "template", external)
    retain("template/source_independent_compartment", "template", helper,
           [edit(["requirements",0,"roles",0,"compartment"], "undeclared-compartment")])
    # Template does not require unused roots to contribute to a final member.
    unused = deepcopy(template["sources"][0]); unused["id"] = "unused"
    unused["molecule"]["id"] = "unused-molecule"; unused["molecule"]["space"]["id"] = "unused.frame"
    for origin in unused["molecule"]["assembly"]:
        origin["destination"]["space_id"] = "unused.frame"
    retain("template/unused_root", "template", template, [edit(["sources"], template["sources"] + [unused])])

    originals = {}
    for variant in ("base", "parameter-default", "parameter-override"):
        original = json.loads((ROOT / f"tests/conformance/case-b/{variant}/request.json").read_bytes())
        originals[variant] = original
        retain("request/case_b/" + variant, "request", original)
        retain("library/case_b/" + variant, "library", original["library"])
        retain("refinement/case_b/" + variant, "refinement", original["library"]["refinements"][0])
        retain("template/case_b_source/" + variant, "template", original["library"]["refinements"][0]["templates"][0])
    request = originals["base"]; refinement = deepcopy(request["library"]["refinements"][0]); library = deepcopy(request["library"])
    empty_library = {"schema_version":PayloadArchitectureLibrary.schema_version, "id":"empty", "refinements":[], "assumptions":[]}
    retain("library/empty", "library", empty_library)
    retain("request/empty_library", "request", request, [edit(["library"], empty_library)])
    match_policy = {"schema_version":"biocompiler.architecture_match_policy.v0.1", "mode":"exact_semantic_subgraph"}
    matched = retain("refinement/empty_match_anchors", "refinement", refinement, [edit(["match_policy"], match_policy), edit(["source_bindings"], {})])
    first_node = next(iter(refinement["source_bindings"]))
    retain("refinement/partial_match_anchors", "refinement", matched, [edit(["source_bindings"], {first_node:"declared_source_anchor"})])
    retain("refinement/changed_source_identity", "refinement", refinement,
           [edit(["source_bindings"], {key:"source_" + value for key,value in refinement["source_bindings"].items()})])
    retain("refinement/matched_maximum_id", "refinement", matched, [edit(["id"], "a" * 4000)])
    retain("refinement/explicit_maximum_id", "refinement", refinement, [edit(["id"], "a" * 4096)])
    role_id = refinement["placements"][0]["recipient_role"]
    component_id = refinement["components"][0]["id"]
    placement_id = refinement["placements"][0]["id"]
    template_id = refinement["templates"][0]["id"]
    helper_record = {"schema_version":"biocompiler.architecture_helper.v0.1", "id":"helper", "capability":"declared", "consumer_component_ids":[component_id],
        "recipient_role":role_id,"compartment":"cytoplasm","availability":"same_rna","initialization":"after_expression","sharing":"shared","capacity":1,
        "assumptions":["Independent artificial helper declaration."],"placement_id":placement_id,"provider_component_id":component_id,"depends_on":["helper"]}
    helper_refinement = retain("refinement/helper_cycle_structural", "refinement", refinement, [edit(["helpers"], [helper_record])])
    control = {"schema_version":"biocompiler.architecture_control.v0.1", "id":"control", "kind":"shutdown",
        "behavior_node_ids":refinement["owned_node_ids"], "controlling_node_ids":[],"component_ids":[component_id], "domain_id":"declared-domain", "assumptions":["Declared only."]}
    controls = retain("refinement/control_without_causality_claim", "refinement", refinement, [edit(["controls"], [control])])
    availability = {"schema_version":"biocompiler.rna_availability_contract.v0.1","id":"window","placement_id":placement_id,
        "onset_min_seconds":0,"onset_max_seconds":1,"duration_min_seconds":1,"duration_max_seconds":2,"clock":"declared_exposure_start","assumptions":["Declared exposure only."]}
    availability_refinement = retain("refinement/availability", "refinement", refinement, [edit(["availability"], [availability])])
    wired = deepcopy(refinement)
    wired["components"][0]["ports"] = executable_component().to_dict()["ports"]
    connection = {"schema_version":"biocompiler.architecture_connection.v0.1", "id":"wire", "producer_component_id":component_id,"producer_port_id":"out", "consumer_component_id":component_id,"consumer_port_id":"in"}
    wired["connections"] = [connection]
    retain("refinement/wiring", "refinement", wired)
    expanded = deepcopy(refinement)
    extra_component = deepcopy(expanded["components"][0]); extra_component["id"] = "extra-component"
    extra_template = deepcopy(expanded["templates"][0]); extra_template["id"] = "extra-template"
    extra_placement = deepcopy(expanded["placements"][0]); extra_placement.update(id="extra-placement", template_id="extra-template")
    expanded["components"].append(extra_component); expanded["templates"].append(extra_template); expanded["placements"].append(extra_placement)
    expanded["bindings"][0]["component_ids"].append("extra-component"); expanded["bindings"][0]["template_ids"].append("extra-template"); expanded["bindings"][0]["placement_ids"].append("extra-placement")
    expanded = retain("refinement/many_to_many_material", "refinement", expanded)
    retain("refinement/reversed_inventories", "refinement", expanded,
        [edit([key], list(reversed(expanded[key]))) for key in ("components","templates","placements")])
    repeated = deepcopy(refinement); repeated["id"] = "second-refinement"
    retain("library/shared_exact_component", "library", library, [edit(["refinements"], [refinement, repeated])])
    different_version = deepcopy(repeated); different_version["components"][0]["version"] = "2"
    retain("library/distinct_component_version", "library", library, [edit(["refinements"], [refinement,different_version])])
    # Retained two-recipient/channel Behavior provides an independently valid
    # graph; this record still makes no execution or model-equivalence claim.
    programs = json.loads((ROOT / "tests/conformance/reference-execution-v1.json").read_bytes())["programs"]
    behavior = next(item["behavior"] for item in programs if item["id"] == "0c8739a7bf10972f37969584695d62a146ef4f01f2f863e6f752b772d9d25e92")
    channel_refinement = deepcopy(refinement); channel_refinement["behavior"] = behavior
    channel_refinement["source_bindings"] = {node["id"]:node["id"] for node in behavior["nodes"]}
    channel_refinement["owned_node_ids"] = [node["id"] for node in behavior["nodes"] if node["kind"].startswith("action.")]
    channel_refinement["bindings"][0]["behavior_node_ids"] = channel_refinement["owned_node_ids"]
    channel_refinement["output_contracts"] = []
    channel_refinement["controls"] = []
    channel_refinement["helpers"] = []
    channel_refinement["channels"] = [{"schema_version":"biocompiler.architecture_channel.v0.1","id":"channel","source_channel_id":"n000003","sender_role":"n000001","receiver_role":"n000002",
        "sender_node_id":"n000007","receiver_node_id":"n000011","latency_seconds":0,"persistence_seconds":0,"failure_mode":"unknown","aggregation":"single_sender",
        "initial_value":{"supplied":"untyped structural declaration"},"assumptions":["Unknown transport remains unresolved."]}]
    channel_refinement = retain("refinement/zero_unknown_untyped_channel_structural", "refinement", channel_refinement)
    molecules = json.loads((ROOT / "tests/conformance/molecules-v1.json").read_bytes())
    sets = {item["id"]: molecules["documents"][item["document_id"]] for item in molecules["records"] if item["kind"] == "set"}
    for kind in ("behavior", "deployment", "acceptance"):
        retain("request/full_wrapped_" + kind, "request", request, [edit(["circuit"], sets["set/wrapper_" + kind]["request"])])

    for kind, original in (("template",template),("refinement",refinement),("library",library),("request",request)):
        for key in original:
            reject(f"{kind}/missing/{key}",kind,original,[remove([key])],"missing_field")
        mutate(kind + "/future_schema",kind,original,["schema_version"],"future","unsupported_schema")
        mutate(kind + "/extra_field",kind,original,["accepted"],True,"unknown_field")
        for name,value,code in (("empty","","invalid_molecular_text"),("trim"," x","invalid_molecular_text"),("control","x\x7f","invalid_molecular_text"),
                                ("max_bytes","🧬" * 1025,"invalid_molecular_text"),("null",None,"invalid_type"),("boolean",True,"invalid_type")):
            mutate(kind + "/id/" + name,kind,original,["id"],value,code)
    for name in ("sources","output_members","requirements"):
        mutate("template/empty/" + name,"template",template,[name],[],"invalid_payload_template")
    for name in ("sources","steps","output_members","requirements","complex_members","amounts","payload_structures"):
        mutate("template/shape/" + name,"template",template,[name],{},"invalid_type")
    for name in ("sources","output_members","requirements"):
        mutate("template/duplicate/" + name,"template",template,[name],[template[name][0],template[name][0]],"invalid_payload_template")
    for identity,path,value in (
        ("missing_output_value",["output_members",0,"value","id"],"absent"),
        ("wrong_output_kind",["output_members",0,"value","kind"],"product"),
        ("output_frame_collision",["output_members",0,"space_id"],template["sources"][0]["molecule"]["space"]["id"]),
        ("absent_requirement_member",["requirements",0,"member_id"],"absent"),
    ):
        mutate("template/" + identity,"template",template,path,value,"invalid_payload_template")
    second_root = deepcopy(template["sources"][0]); second_root["id"] = "another"
    mutate("template/duplicate_root_frame","template",template,["sources"],[template["sources"][0],second_root],"invalid_payload_template")
    extra_member = deepcopy(template["output_members"][0]); extra_member.update(id="extra",space_id="extra.final")
    mutate("template/uncovered_member","template",template,["output_members"],template["output_members"] + [extra_member],"invalid_payload_template")
    second_requirement = deepcopy(template["requirements"][0]); second_requirement["id"] = "second"
    mutate("template/duplicate_role","template",template,["requirements"],template["requirements"] + [second_requirement],"invalid_payload_template")
    base_recipe = templates["request/base"]; chain = templates["request/chain"]
    for identity,path,value in (
        ("duplicate_step",["steps"],[base_recipe["steps"][0]] * 2),
        ("forward_reference",["steps"],list(reversed(chain["steps"]))),
        ("duplicate_product",["steps",0,"ports",0,"id"],base_recipe["sources"][0]["id"]),
        ("product_frame_collision",["steps",0,"ports",0,"space_id"],base_recipe["sources"][0]["molecule"]["space"]["id"]),
    ):
        mutate("template/" + identity,"template",chain if identity == "forward_reference" else base_recipe,path,value,"invalid_payload_template")
    dead = deepcopy(base_recipe); dead["output_members"][0]["value"] = {"schema_version":"biocompiler.construction_value_ref.v0.1","kind":"root","id":dead["sources"][0]["id"]}
    reject("template/unused_product", "template", dead, [], "invalid_payload_template")
    complex_template = templates["request/complex"]
    mutate("template/missing_complex_constituent","template",complex_template,["complex_members",0,"constituents",0,"member_id"],"absent","invalid_payload_template")
    mutate("template/member_complex_collision","template",complex_template,["complex_members",0,"id"],complex_template["output_members"][0]["id"],"invalid_payload_template")
    amount_template = templates["request/amount"]
    mutate("template/missing_amount_subject","template",amount_template,["amounts",0,"subject_id"],"absent","invalid_payload_template")
    mutate("template/missing_amount_role","template",amount_template,["amounts",0,"role_instance_ids"],["absent"],"invalid_payload_template")
    duplicate_amount = deepcopy(amount_template["amounts"][0]); duplicate_amount["id"] = "second-amount"
    mutate("template/duplicate_preparation_subject","template",amount_template,["amounts"],amount_template["amounts"] + [duplicate_amount],"invalid_payload_template")
    for name,maximum in (("sources",64),("steps",256),("output_members",64),("requirements",256),("complex_members",64),("amounts",128),("payload_structures",64)):
        origin = complex_template if name == "complex_members" else amount_template if name == "amounts" else templates["case_b/base"] if name == "payload_structures" else base_recipe
        mutate("template/overflow/" + name,"template",origin,[name],[origin[name][0]] * (maximum+1),"molecular_resource_limit")

    mutate("refinement/missing_source_node","refinement",refinement,["source_bindings"],{},"invalid_architecture_refinement")
    bad_map = deepcopy(refinement["source_bindings"]); keys = list(bad_map); bad_map[keys[0]] = bad_map[keys[1]]
    mutate("refinement/noninjective_sources","refinement",refinement,["source_bindings"],bad_map,"invalid_architecture_refinement")
    mutate("refinement/absent_anchor","refinement",matched,["source_bindings"],{"absent":"source"},"invalid_architecture_refinement")
    mutate("refinement/matched_id_overflow","refinement",matched,["id"],"a" * 4001,"invalid_molecular_text")
    mutate("refinement/owned_absent","refinement",refinement,["owned_node_ids"],["absent"],"invalid_architecture_refinement")
    for name in ("components","templates","bindings","placements","owned_node_ids","assumptions"):
        mutate("refinement/empty/" + name,"refinement",refinement,[name],[],"invalid_architecture_refinement")
    for name in ("components","templates","bindings","placements"):
        mutate("refinement/duplicate/" + name,"refinement",refinement,[name],[refinement[name][0]] * 2,"invalid_architecture_refinement")
    for name in ("components","templates","bindings","placements","connections","controls","helpers","channels","output_contracts","availability"):
        mutate("refinement/shape/" + name,"refinement",refinement,[name],{},"invalid_type")
    for identity,path,value in (
        ("binding_node",["bindings",0,"behavior_node_ids"],["absent"]),
        ("binding_component",["bindings",0,"component_ids"],["absent"]),
        ("binding_template",["bindings",0,"template_ids"],["absent"]),
        ("binding_placement",["bindings",0,"placement_ids"],["absent"]),
        ("owned_uncovered",["bindings",0,"behavior_node_ids"],[role_id]),
        ("placement_member",["placements",0,"member_id"],"absent"),
        ("placement_template",["placements",0,"template_id"],"absent"),
        ("placement_role_absent",["placements",0,"recipient_role"],"absent"),
        ("placement_role_wrong_kind",["placements",0,"recipient_role"],refinement["owned_node_ids"][0]),
    ):
        mutate("refinement/" + identity,"refinement",refinement,path,value,"invalid_architecture_refinement")
    for key in ("components","templates"):
        extra = deepcopy(refinement[key][0]); extra["id"] = "orphan"
        mutate("refinement/unbound_" + key,"refinement",refinement,[key],refinement[key] + [extra],"invalid_architecture_refinement")
    placement_copy = deepcopy(refinement["placements"][0]); placement_copy["id"] = "duplicate-location"
    mutate("refinement/repeated_member_recipient","refinement",refinement,["placements"],refinement["placements"] + [placement_copy],"invalid_architecture_refinement")
    mutate("refinement/unplaced_extra_template","refinement",expanded,["placements"],[expanded["placements"][0]],"invalid_architecture_refinement")
    for identity,path,value in (("control_node",["controls",0,"controlling_node_ids"],["absent"]),("control_component",["controls",0,"component_ids"],["absent"])):
        mutate("refinement/" + identity,"refinement",controls,path,value,"invalid_architecture_refinement")
    for key,value in (("recipient_role","absent"),("consumer_component_ids",["absent"]),("provider_component_id","absent"),("placement_id","absent"),("depends_on",["absent"])):
        mutate("refinement/helper/" + key,"refinement",helper_refinement,["helpers",0,key],value,"invalid_architecture_refinement")
    mutate("refinement/availability_absent","refinement",availability_refinement,["availability",0,"placement_id"],"absent","invalid_architecture_refinement")
    extra_window = deepcopy(availability); extra_window["id"] = "second-window"
    mutate("refinement/availability_duplicate_placement","refinement",availability_refinement,["availability"],[availability,extra_window],"invalid_architecture_refinement")
    for key,value in (("producer_component_id","absent"),("consumer_component_id","absent"),("producer_port_id","absent"),("consumer_port_id","absent"),("producer_port_id","in"),("consumer_port_id","out")):
        mutate("refinement/connection/" + key + "/" + value,"refinement",wired,["connections",0,key],value,"invalid_architecture_refinement")
    duplicate_connection = deepcopy(connection); duplicate_connection["id"] = "second-driver"
    mutate("refinement/multiple_drivers","refinement",wired,["connections"],[connection,duplicate_connection],"invalid_architecture_refinement")
    for key,value in (("sender_role","absent"),("receiver_role","n000004"),("source_channel_id","n000004"),("sender_node_id","absent"),("receiver_node_id","absent")):
        mutate("refinement/channel/" + key,"refinement",channel_refinement,["channels",0,key],value,"invalid_architecture_refinement")
    if refinement["output_contracts"]:
        mutate("refinement/output_absent_action","refinement",refinement,["output_contracts",0,"action_ids"],["absent"],"invalid_architecture_refinement")
        mutate("refinement/output_wrong_node_kind","refinement",refinement,["output_contracts",0,"action_ids"],[role_id],"invalid_architecture_refinement")
        extra_output = deepcopy(refinement["output_contracts"][0]); extra_output["id"] = "second-output"
        mutate("refinement/output_duplicate_requirement","refinement",refinement,["output_contracts"],refinement["output_contracts"] + [extra_output],"invalid_architecture_refinement")
    conflicting = deepcopy(repeated); conflicting["components"][0]["assumptions"] += ["different supplied authority"]
    mutate("library/conflicting_component","library",library,["refinements"],[refinement,conflicting],"invalid_architecture_library")
    mutate("library/duplicate_refinement","library",library,["refinements"],[refinement,refinement],"invalid_architecture_library")
    mutate("library/duplicate_assumptions","library",library,["assumptions"],["same","same"],"invalid_architecture_library")
    mutate("request/historical_not_source_authority","request",request,["circuit"],sets["set/reference"]["request"],"invalid_architecture_request")
    mutate("request/dna_not_rna_profile","request",request,["circuit"],sets["set/duplex"]["request"],"invalid_architecture_request")
    # Additional graph boundaries and intentional structural/context separation.
    structure_template = deepcopy(templates["case_b/base"])
    structure_template["payload_structures"][0]["form"] = "delivered_dna"
    retain("template/payload_modality_is_contextual", "template", structure_template)
    selected = deepcopy(templates["request/slice"])
    selected["steps"][0]["operation"]["input"]["path"] = {"schema_version":"biocompiler.molecule_coordinate_path.v0.1", "space_id":selected["sources"][0]["molecule"]["space"]["id"], "spans":[{"schema_version":"biocompiler.molecule_index_span.v0.1","start":0,"end":1}],"strand":"+"}
    selected = retain("template/explicit_selection", "template", selected)
    mutate("template/selection_frame_mismatch", "template", selected,
           ["steps",0,"operation","input","path","space_id"], "absent", "invalid_payload_template")
    mutate("template/selection_kind_mismatch", "template", selected,
           ["steps",0,"operation","input","value","kind"], "product", "invalid_payload_template")
    processing = templates["request/rna_cleavage"]
    mutate("template/duplicate_output_frame", "template", processing,
           ["output_members",1,"space_id"], processing["output_members"][0]["space_id"], "invalid_payload_template")
    for field in ("owned_node_ids", "assumptions"):
        mutate("refinement/duplicate/" + field,"refinement",refinement,[field],[refinement[field][0]] * 2,"invalid_architecture_refinement")
    mutate("refinement/source_mapping_shape","refinement",refinement,["source_bindings"],[],"invalid_type")
    for identity, original, field in (("controls", controls, "controls"), ("helpers", helper_refinement, "helpers"),
                                      ("channels", channel_refinement, "channels"), ("availability", availability_refinement, "availability"),
                                      ("connections", wired, "connections"), ("output_contracts", refinement, "output_contracts")):
        mutate("refinement/duplicate/" + identity,"refinement",original,[field],[original[field][0]] * 2,"invalid_architecture_refinement")
    changed_binding = deepcopy(expanded)
    changed_binding["bindings"][0]["template_ids"] = [template_id]
    changed_binding["bindings"].append({"schema_version":"biocompiler.architecture_binding.v0.1", "id":"other-binding",
        "behavior_node_ids":[role_id],"component_ids":[component_id],"template_ids":["extra-template"],"placement_ids":["extra-placement"]})
    reject("refinement/binding_placement_wrong_template", "refinement", changed_binding, [], "invalid_architecture_refinement")
    two_roles = deepcopy(channel_refinement)
    placement = deepcopy(two_roles["placements"][0]); placement.update(id="second-recipient", recipient_role="n000002")
    two_roles["placements"].append(placement)
    two_roles["bindings"][0]["placement_ids"].append("second-recipient")
    retain("refinement/same_member_multiple_roles_structural", "refinement", two_roles)
    retain("library/maximum_assumptions", "library", empty_library, [edit(["assumptions"], ["assumption" + str(i) for i in range(64)])])
    mutate("library/assumption_overflow", "library", empty_library, ["assumptions"], ["assumption" + str(i) for i in range(65)], "molecular_resource_limit")
    mutate("refinement/assumption_overflow", "refinement", refinement, ["assumptions"], ["assumption" + str(i) for i in range(65)], "molecular_resource_limit")
    for identity, value in (("false", False), ("null", None)):
        mutate("request/invalid_library/" + identity, "request", request, ["library"], value, "invalid_type")
        mutate("request/invalid_constraints/" + identity, "request", request, ["constraints"], value, "invalid_type")
    result = {"schema_version":SCHEMA, "claim_scope":"Structural supplied architecture authority only; no model refinement, matching, construction, candidate execution or admission is established.",
              "documents":documents,"records":records,"rejections":rejections,"conversions":conversions,
              "coverage":{"record_kinds":sorted(KINDS),"case_b_variants":["base","parameter-default","parameter-override"],
                          "construction_operations":sorted({step["operation"]["schema_version"] for value in templates.values() for step in value["steps"]}),
                          "structural_context_distinction":["helper_only_template","unresolved_external_provider","empty_library","empty_match_anchors","helper_cycle","unknown_zero_channel","full_human_wrappers"]}}
    result["inventory_sha256"] = inventory(result)
    return result


def partition_corpora(corpus):
    result = {}
    for partition, kinds in (("templates", {"template"}), ("architecture", {"refinement", "library", "request"})):
        shard = {key: deepcopy(value) for key, value in corpus.items() if key not in {"documents", "records", "rejections", "conversions", "inventory_sha256"}}
        shard["partition"] = partition
        shard["records"] = [item for item in corpus["records"] if item["kind"] in kinds]
        shard["rejections"] = [item for item in corpus["rejections"] if item["kind"] in kinds]
        shard["conversions"] = corpus["conversions"] if partition == "templates" else []
        shard["coverage"]["record_kinds"] = sorted(kinds)
        used = {item["document"] for item in shard["records"] + shard["rejections"]}
        used.update(item["normalized"] for item in shard["records"])
        used.update(item[key] for item in shard["conversions"] for key in ("template", "request"))
        shard["documents"] = {key: value for key, value in corpus["documents"].items() if key in used}
        shard["inventory_sha256"] = inventory(shard)
        result[partition] = shard
    return result

def check_corpus(corpus):
    assert corpus["schema_version"] == SCHEMA
    ids = [item["id"] for key in ("records","rejections") for item in corpus[key]]
    assert len(ids) == len(set(ids)), "Duplicate composite inventory"
    assert inventory(corpus) == corpus["inventory_sha256"], "Changed composite inventory"
    assert inventory(corpus) == INVENTORIES[corpus["partition"]], "Missing or substituted composite inventory"
    expected_counts = {"templates": (35,58,25,58), "architecture": (30,134,0,31)}
    assert tuple(len(corpus[key]) for key in ("records","rejections","conversions","documents")) == expected_counts[corpus["partition"]], "Incomplete composite census"
    used = {item["document"] for item in corpus["records"] + corpus["rejections"]}
    used.update(item["normalized"] for item in corpus["records"])
    used.update(item[key] for item in corpus["conversions"] for key in ("template", "request"))
    assert used == set(corpus["documents"]), "Unreferenced composite document"
    for identity,document in corpus["documents"].items():
        assert fingerprint(document) == identity, "Changed composite document"
    for case in corpus["records"]:
        raw = apply_edits(corpus["documents"][case["document"]],case["edits"])
        actual = KINDS[case["kind"]].from_dict(raw)
        assert fingerprint(actual.to_dict()) == case["normalized"], case["id"]
        assert actual.to_dict() == corpus["documents"][case["normalized"]]
    for case in corpus["rejections"]:
        try:
            KINDS[case["kind"]].from_dict(apply_edits(corpus["documents"][case["document"]],case["edits"]))
        except SerializationError:
            continue
        raise AssertionError("Accepted composite rejection: " + case["id"])
    for case in corpus["conversions"]:
        template = PayloadTemplate.from_dict(corpus["documents"][case["template"]])
        request = CircuitConstructionRequest.from_dict(corpus["documents"][case["request"]])
        assert PayloadTemplate.from_construction_request(request).to_dict() == template.to_dict()
        assert template.to_construction_request(request.circuit,mode=request.mode).to_dict() == request.to_dict()
    pending = [(corpus,0)]; count = 0
    while pending:
        value,depth = pending.pop(); count += 1
        assert count <= 250_000 and depth <= 128, "Composite fixture structural budget"
        if isinstance(value,dict): pending.extend((child,depth+1) for item in value.items() for child in item)
        elif isinstance(value,list): pending.extend((child,depth+1) for child in value)
    assert len(encoded(corpus)) <= 16*1024*1024, "Composite fixture read budget"


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--write",action="store_true");parser.add_argument("--check",action="store_true");args=parser.parse_args()
    for partition,corpus in partition_corpora(build_corpus()).items():
        check_corpus(corpus);data=encoded(corpus);path=TEMPLATES if partition=="templates" else CORPUS
        if args.write: path.write_bytes(data)
        elif not path.exists() or path.read_bytes()!=data: raise SystemExit("Architecture domains corpus is stale; review before --write")
        print(json.dumps({"partition":partition,"records":len(corpus["records"]),"rejections":len(corpus["rejections"]),"conversions":len(corpus["conversions"]),"documents":len(corpus["documents"]),"bytes":len(data),"inventory_sha256":inventory(corpus)}))
if __name__=="__main__":main()

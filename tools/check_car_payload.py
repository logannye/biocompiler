"""Distinct hosted CAR source campaign and pure retained-evidence audit.

Only explicitly supplied Core/Verify processes interpret the static expression
profile. The independent oracle retains public nominal material and complete
original authority. Passing software checks cannot establish biological function.
No process, source import, network access or campaign runs on module import.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys
import time
import zipfile

try:
    from .check_policy_core import canonical_digest, digest_file, read_json, source_identity
    from .check_policy_development import git, identity, pin, source_snapshot
    from .check_policy_component_material import ComponentBoundary, NATIVE_PATHS, MAX_RECEIPT, MAX_EVIDENCE
    from .check_policy_material import archive_receipt
except ImportError:
    from check_policy_core import canonical_digest, digest_file, read_json, source_identity
    from check_policy_development import git, identity, pin, source_snapshot
    from check_policy_component_material import ComponentBoundary, NATIVE_PATHS, MAX_RECEIPT, MAX_EVIDENCE
    from check_policy_material import archive_receipt

SCHEMA = "biocompiler.car_payload_sdk_development.v0.1"
EXPECTED = "data/car_payload/expected.json"
EXPECTED_SHA256 = "696cd51d54218ead02bc16ca8338bf4d8b58c916dd5b4ceff34d3833bd3abab1"
REFERENCE = "src/biocompiler/policy/data/car_rm61461_reference_v01.json"
EXAMPLE = "examples/car_payload.py"
OUTPUT = "generated/development-feedback/car-payload-sdk-witness.json"
INPUTS = (EXPECTED, EXAMPLE, "src/biocompiler/core_policy_expression_material.py",
          "src/biocompiler/policy/expression_material.py", "src/biocompiler/policy/research_project.py",
          "src/biocompiler/policy/car_reference.py", REFERENCE)
COPY_INPUTS = (EXPECTED, EXAMPLE, REFERENCE)
OBSERVATIONS = ("originals", "typed-roundtrip", "preflight", "compile-core", "export-verify",
    "reverify-verify", "paired-publication", "tight-originals", "tight-compile-core",
    "tight-export-verify", "tight-paired-publication", "short-originals", "short-compile-core",
    "short-no-publication", "changed-candidate", "changed-fasta", "changed-metadata",
    "changed-authority", "forged-replay", "missing-chemistry", "work-exhaustion", "native-actions")
CASE_IDS = ("base", "tight", "short")
EVIDENCE_FILES = tuple(name + ".json" for name in OBSERVATIONS) + tuple(name + "-project.json" for name in CASE_IDS) + (
    "base.zip", "tight.zip", "base-changed-candidate.zip", "base-changed-fasta.zip")
SCOPE = "conditional_exact_public_nominal_CAR_material_not_biological_function"
# Imported immutable IR/type dependencies are closed here. Calls into the
# compiler, verification and registry implementations remain forbidden below.
AUTHORING_MODULES = frozenset("""artifacts artifacts.manifest errors ir ir.behavior ir.circuit_construction ir.circuit_intent ir.circuit_logic ir.circuit_molecules ir.circuit_observations ir.circuit_payloads ir.circuit_profile ir.circuit_recoding ir.circuit_transitions ir.component_contracts ir.components ir.composition ir.construct ir.intent ir.mechanism ir.molecule_chemistry ir.molecule_records ir.payload_contracts ir.serialization semantics semantics.acceptance semantics.admission semantics.component_contracts semantics.context semantics.contracts semantics.coordinates semantics.deployment semantics.human_behavior semantics.human_target semantics.molecule_coordinates semantics.realization semantics.types compiler compiler.acceptance compiler.deployment compiler.human_behavior compiler.request registry registry.components registry.reference_components registry.references verification verification.admission""".split())
REQUIRED_MODULES = {"biocompiler.core_client", "biocompiler.core_policy_expression_material",
    "biocompiler.policy.expression_material", "biocompiler.policy.car_reference", "biocompiler.policy.research_project"}


def require(value, message):
    if not value:
        raise AssertionError(message)


def same(left, right):
    """Exact JSON identity; Python bool/int or float/int equality is insufficient."""
    from biocompiler.core_client import encode_json
    return encode_json(left) == encode_json(right)


class CarBoundary(ComponentBoundary):
    @staticmethod
    def allowed(name):
        return name in {"biocompiler.core_distribution", "biocompiler.core_policy_component_selection",
                        "biocompiler.core_policy_expression_material"} or name.removeprefix("biocompiler.") in AUTHORING_MODULES or ComponentBoundary.allowed(name)

    def trace(self, frame, event, argument):
        super().trace(frame, event, argument)
        module = frame.f_globals.get("__name__", "")
        definition_only = (frame.f_code.co_name in {"<module>", "<listcomp>", "<dictcomp>", "<setcomp>", "<genexpr>"}
            or not frame.f_code.co_flags & 2
            or (frame.f_code.co_name == "__create_fn__" and frame.f_code.co_filename == "<string>"
                and frame.f_back is not None and frame.f_back.f_globals.get("__name__") == "dataclasses")
            or (module == "biocompiler.compiler.request" and frame.f_code.co_name == "_strict_import"
                and frame.f_back is not None and not frame.f_back.f_code.co_flags & 2)
            or (module in {"biocompiler.compiler.human_behavior", "biocompiler.compiler.deployment", "biocompiler.compiler.acceptance"}
                and frame.f_code.co_name == "__annotate__" and frame.f_back is not None
                and frame.f_back.f_globals.get("__name__") == "annotationlib"
                and frame.f_back.f_code.co_name == "_get_dunder_annotations"))
        if event == "call" and not definition_only and module.startswith((
                "biocompiler.compiler.", "biocompiler.verification.", "biocompiler.registry.")):
            self.denied.append("call:" + module + "." + frame.f_code.co_name)
            raise AssertionError("CAR campaign forbids Python compiler/checker/registry execution")


def check_census(names):
    require(tuple(names) == OBSERVATIONS, "Incomplete, duplicate or reordered CAR observation census")


def checked_assets(root, expected_path):
    root, expected_path = Path(root), Path(expected_path)
    require(expected_path.resolve() == (root / EXPECTED).resolve() and not expected_path.is_symlink(), "Use the exact CAR oracle")
    require(expected_path.is_file() and expected_path.stat().st_size <= 256 * 1024
            and not (root / REFERENCE).is_symlink() and (root / REFERENCE).is_file()
            and (root / REFERENCE).stat().st_size <= 128 * 1024, "Unbounded or redirected CAR oracle/reference")
    require(digest_file(expected_path) == EXPECTED_SHA256, "CAR expected literals or complete originals changed")
    expected = read_json(expected_path, 256 * 1024)
    require(expected["schema_version"] == "biocompiler.car_payload_expected.v0.1" and expected["acceptance"] is False,
            "CAR oracle schema/acceptance changed")
    reference = read_json(root / REFERENCE, 128 * 1024)
    require(digest_file(root / REFERENCE) == expected["reference_pack_sha256"], "CAR factual source pack changed")
    m = expected["material"]
    require(m["rna"] == reference["source_records"]["151"]["rna_sequence"]
            and m["protein"] == reference["source_records"]["2"]["original_literal"].upper()
            and len(m["rna"]) == m["rna_nt"] == 1776 and len(m["protein"]) == m["protein_aa"] == 485
            and hashlib.sha256(m["rna"].encode()).hexdigest() == m["rna_sha256"]
            and hashlib.sha256(m["protein"].encode()).hexdigest() == m["protein_sha256"]
            and m["rna"][1534:1540] == m["terminal_stop_codons"] == "UGAUAA"
            and m["rna"][1666:] == "A" * 110, "Independent CAR literal correspondence changed")
    require(canonical_digest(expected["request"]) == expected["request_sha256"], "CAR original identity changed")
    return {"root": root, "expected": expected, "request": deepcopy(expected["request"])}


def request_for(packet, case):
    require(case in CASE_IDS, "Unknown CAR case")
    result = deepcopy(packet["request"])
    rows = [r for r in result["document"]["program"]["declarations"] if r["id"] == "maximum_rna_nt"]
    require(len(rows) == 1, "Missing exact editable source parameter")
    rows[0]["value"] = packet["expected"]["maximum_rna_nt"][case]
    return result


def expected_project(packet, case):
    request = request_for(packet, case)
    return {"schema_version": "biocompiler.research_project.v0.2", **deepcopy(request["project_context"]),
            "route": "expression_material", "request": request, "limits": None}


def changed_utr_sequence(sequence):
    # Interior unmodified 5prime UTR base: preserve Cap-AG, CDS, tail and all
    # explicit chemistry sites. This is a negative integrity control, not design.
    require(type(sequence) is str and len(sequence) == 1776 and sequence[8] == "A",
            "CAR mutation no longer targets the frozen interior UTR base")
    return sequence[:8] + "G" + sequence[9:]


def changed_candidate(candidate, kind="sequence"):
    changed = deepcopy(candidate)
    inventory = changed["construction"]["inventory"]
    require(len(inventory["molecules"]) == 1 and inventory["complexes"] == [] and inventory["form_mappings"] == [],
            "CAR candidate mutation needs one complete original molecule")
    molecule = inventory["molecules"][0]
    old = canonical_digest(molecule)
    require(inventory["role_instances"] and all(row["subject_id"] == molecule["id"] and row["subject_fingerprint"] == old
            for row in inventory["role_instances"]), "Mutation lacks complete candidate-owned pins")
    if kind == "sequence":
        molecule["sequence"] = changed_utr_sequence(molecule["sequence"])
    else:
        require(kind == "chemistry", "Unknown CAR candidate mutation")
        molecule["chemistry"]["finish_end"].update(status="unknown", identity=None)
    for row in inventory["role_instances"]:
        row["subject_fingerprint"] = canonical_digest(molecule)
    return changed


def changed_authority(request):
    result = deepcopy(request)
    molecule = result["structure_authority"]["template"]["sources"][0]["molecule"]
    molecule["sequence"] = changed_utr_sequence(molecule["sequence"])
    body = result["expression_contract"]["body"]
    body["material"]["structure_sha256"] = canonical_digest(result["structure_authority"])
    result["expression_contract"]["identity"]["content_fingerprint"] = canonical_digest(body)
    return result


def forged_replay(result):
    changed = deepcopy(result)
    changed["report"]["empirical"] = "proven"
    changed["report_fingerprint"] = canonical_digest(changed["report"])
    return changed


def mutated_pair(exported, kind):
    from biocompiler.core_client import encode_json
    artifact = exported["artifact"]
    fasta, manifest = artifact["fasta"].encode(), deepcopy(artifact["manifest"])
    if kind == "candidate":
        manifest["candidate"] = changed_candidate(manifest["candidate"])
    else:
        require(kind == "fasta", "Unknown CAR archive mutation")
        lines = fasta.split(b"\n"); lines[1] = (b"G" if lines[1][:1] != b"G" else b"C") + lines[1][1:]
        fasta = b"\n".join(lines)
    return (("program.fasta", fasta), ("manifest.json", encode_json(manifest)))


def write_mutant(path, exported, kind):
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for name, raw in mutated_pair(exported, kind):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3; entry.external_attr = 0o100644 << 16
            archive.writestr(entry, raw)


def checked_result(value, packet, request, *, operation, accepted=True):
    from biocompiler.core_client import CoreResponse, CORE_VERSION
    from biocompiler.core_policy_expression_material import _result
    payload = {"request": request}
    if operation != "compile":
        payload["candidate"] = value["candidate"]
    checked = _result(CoreResponse("retained-car", operation + "-policy-expression-material", "ok", value, (),
        "core" if operation == "compile" else "verify", CORE_VERSION), payload)
    require((checked.status == "checked_expression_material") == accepted and
            checked.report["empirical"] == checked.report["human_use"] == "unassessed", "CAR conditional status changed")
    if accepted:
        m = packet["expected"]["material"]
        molecules = value["candidate"]["construction"]["inventory"]["molecules"]
        require(len(molecules) == 1, "CAR complete molecule census changed")
        molecule = molecules[0]
        require(molecule["id"] == m["molecule_id"] and molecule["sequence"] == m["rna"]
                and molecule["space"]["length"] == m["rna_nt"] and molecule["space"]["alphabet"] == "RNA"
                and molecule["space"]["topology"] == "linear" and same(molecule["chemistry"], m["chemistry"]),
                "CAR exact nominal bases/chemistry differ from independent authority")
        require(all(len(row["path"]["spans"]) == 1 for row in molecule["features"]), "CAR feature shape changed")
        regions = sorted(({"id": row["id"], "start": row["path"]["spans"][0]["start"],
                           "end": row["path"]["spans"][0]["end"]} for row in molecule["features"]), key=lambda row: row["start"])
        require(same(regions, m["regions"]), "CAR four original regions changed")
        leaf = value["report"]["structure"]
        require(leaf["terminal_stop_codons"] == 2 and leaf["members"][0]["expected_product"] == m["protein"]
                and leaf["members"][0]["translated_product"] == m["protein"], "CAR complete nominal protein/two-stop evidence changed")
        req = value["report"]["requirements"]
        require(len(req) == 1 and req[0]["id"] == "encode_car" and req[0]["actual_rna_nt"] == 1776
                and req[0]["status"] == "pass" and req[0]["localization_status"] == "supplied_premise", "CAR source requirement changed")
    if operation == "export":
        fasta = ">rna_0001 alphabet=RNA\n" + "".join(packet["expected"]["material"]["rna"][i:i+80] + "\n" for i in range(0,1776,80))
        require(value["artifact"]["fasta"] == fasta and same(value["artifact"]["manifest"]["request"], request),
                "CAR export lost exact FASTA or complete original metadata")
    return checked


def response_data(response):
    return {"operation": response.operation, "status": response.status, "result": response.result,
            "diagnostics": [asdict(row) for row in response.diagnostics], "executable": response.executable,
            "core_version": response.version}


@contextmanager
def action_log(core, verify, *, installed):
    """Observe every actual transport call; do not replace native evaluation."""
    from biocompiler.core_client import CoreClient, CoreRejected, decode_json, encode_json
    previous = CoreClient.call
    state = {"phase": None, "rows": []}
    def call(client, operation, payload, **kwargs):
        require(client.role in ("core", "verify") and state["phase"] is not None, "Unscoped CAR native action")
        authority = core if client.role == "core" else verify
        require(client.executable.resolve() == authority.executable.resolve() and client.expected_sha256 == authority.expected_sha256,
                "CAR native action escaped independently pinned executable")
        original = decode_json(encode_json(payload))
        try:
            response = previous(client, operation, payload, **kwargs)
        except CoreRejected as error:
            response = error.response
            state["rows"].append({"phase": state["phase"], "role": client.role, "payload": original, "response": response_data(response)})
            raise
        state["rows"].append({"phase": state["phase"], "role": client.role, "payload": original, "response": response_data(response)})
        return response
    CoreClient.call = call
    try:
        yield state
    finally:
        CoreClient.call = previous


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _negative_response(value, code):
    require(type(value) is dict and set(value) == {"operation", "status", "result", "diagnostics", "executable", "core_version"}
            and value["status"] == "error" and value["result"] is None and value["executable"] == "verify"
            and value["diagnostics"] and {row["code"] for row in value["diagnostics"]} == {code},
            "CAR negative lost its exact native rejection")


def expected_actions(values, packet, installed):
    request = packet["request"]; candidate = values["compile-core"]["candidate"]
    rows = []
    def cap(phase, role): rows.append((phase, role, "capabilities", {}, None))
    def operation(phase, role, op, payload, output): rows.append((phase, role, op + "-policy-expression-material", payload, output))
    def build(phase, request, compile_value, export_value):
        if installed: cap(phase,"core"); cap(phase,"verify")
        cap(phase,"core"); operation(phase,"core","compile",{"request":request},compile_value)
        if export_value is not None:
            cap(phase,"verify"); operation(phase,"verify","export",{"request":request,"candidate":compile_value["candidate"]},export_value)
    def reopen(phase, candidate, output):
        if installed: cap(phase,"verify")
        cap(phase,"verify"); operation(phase,"verify","export",{"request":request,"candidate":candidate},output)
    build("base-build",request,values["compile-core"],values["export-verify"])
    reopen("base-reopen",candidate,values["reverify-verify"])
    build("tight-build",request_for(packet,"tight"),values["tight-compile-core"],values["tight-export-verify"])
    build("short-build",request_for(packet,"short"),values["short-compile-core"],None)
    reopen("changed-candidate",changed_candidate(candidate),values["changed-candidate"]["response"])
    reopen("changed-fasta",candidate,values["export-verify"])
    for phase, req, actual, value in (("changed-authority",changed_authority(request),candidate,values["changed-authority"]),
                                    ("missing-chemistry",request,changed_candidate(candidate,"chemistry"),values["missing-chemistry"])):
        cap(phase,"verify"); operation(phase,"verify","check",{"request":req,"candidate":actual},value)
    operation("forged-replay","verify","replay",{"request":request,"candidate":candidate,"report":forged_replay(values["compile-core"])},values["forged-replay"])
    low = deepcopy(request); low["budgets"]["max_work"] = 1
    operation("work-exhaustion","verify","check",{"request":low,"candidate":candidate},values["work-exhaustion"])
    return rows


def check_actions(log, values, packet):
    from biocompiler.core_client import CORE_VERSION, _capabilities
    from biocompiler.core_policy_expression_material import PROFILE, PRODUCER_PROFILE, VALIDATION_SCOPE
    require(type(log) is dict and set(log) == {"schema_version", "resolution", "actions"}
            and log["schema_version"] == "biocompiler.car_native_actions.v0.1"
            and log["resolution"] in ("explicit_pinned", "owned_installed_defaults"), "CAR action log identity changed")
    expected = expected_actions(values,packet,log["resolution"] == "owned_installed_defaults")
    require(type(log["actions"]) is list and len(log["actions"]) == len(expected), "Incomplete or extra CAR native actions")
    for row,(phase,role,operation,payload,output) in zip(log["actions"],expected):
        require(set(row) == {"phase","role","payload","response"} and row["phase"] == phase and row["role"] == role
                and same(row["payload"], payload), "CAR native action original payload/order/role changed")
        response = row["response"]
        require(set(response) == {"operation","status","result","diagnostics","executable","core_version"}
                and response["operation"] == operation and response["executable"] == role and response["core_version"] == CORE_VERSION,
                "CAR native response identity changed")
        if operation == "capabilities":
            require(response["status"] == "ok" and response["diagnostics"] == [], "CAR capability call failed")
            caps = _capabilities(response["result"])
            require(same(caps.profiles.get("policy_expression_material"), PROFILE) and VALIDATION_SCOPE in caps.validation_scopes,
                    "CAR native capability lost exact profile")
            require(same(caps.profiles.get("policy_expression_material_producer"), PRODUCER_PROFILE) == (role == "core"),
                    "CAR producer capability role changed")
            require(set(PROFILE["operations"]) <= set(caps.operations) and
                    (("compile-policy-expression-material" in caps.operations) == (role == "core")),
                    "CAR capability operation escaped the independent executable role")
        elif type(output) is dict and "diagnostics" in output and "core_version" in output:
            require(same(response, output), "CAR rejection action differs from retained original native response")
        else:
            require(response["status"] == "ok" and response["diagnostics"] == [] and same(response["result"], output),
                    "CAR native action is not the complete retained result")


def check_observations(values, packet):
    require(type(values) is dict and tuple(values) == OBSERVATIONS, "Incomplete, duplicate or reordered CAR observation census")
    request = packet["request"]
    for case,key in (("base","originals"),("tight","tight-originals"),("short","short-originals")):
        require(same(values[key], expected_project(packet,case)), "CAR retained complete original project changed")
    require(same(values["typed-roundtrip"], {"project_sha256":canonical_digest(values["originals"]),"request_sha256":canonical_digest(request),
        "source_profile":"biocompiler.policy_expression_source.v0.1","native_status":"not_run","biological_status":"unassessed"}), "CAR typed roundtrip changed")
    require(same(values["preflight"], {"project_sha256":canonical_digest(values["originals"]),"route":"expression_material","source_count":4,
        "status":"structurally_ready","native_status":"not_run","biological_status":"unassessed","provenance_status":"caller_declared"}), "CAR preflight upgraded its scope")
    for name,case,operation in (("compile-core","base","compile"),("export-verify","base","export"),("reverify-verify","base","export"),
                                ("tight-compile-core","tight","compile"),("tight-export-verify","tight","export")):
        checked_result(values[name],packet,request_for(packet,case),operation=operation)
    require(same(values["export-verify"], values["reverify-verify"]), "CAR fresh Verify differs")
    for case,name in (("base","paired-publication"),("tight","tight-paired-publication")):
        exported = values["export-verify" if case == "base" else "tight-export-verify"]
        require(same(values[name], {**archive_receipt(exported),"path":case+".zip"}), "CAR complete archive receipt differs")
    short = values["short-compile-core"]
    checked_result(short,packet,request_for(packet,"short"),operation="compile",accepted=False)
    requirement = short["report"]["requirements"][0]
    require(requirement["id"] == "encode_car" and requirement["maximum_rna_nt"] == 1775 and requirement["actual_rna_nt"] == 1776
            and requirement["status"] == requirement["length_status"] == "fail"
            and {r["code"] for r in requirement["diagnostics"]} == {"expression_rna_length_requirement"}
            and same(values["short-no-publication"], {"status":"not_accepted","artifact":"absent","requirement":"encode_car"}), "CAR length edit lost exact failing source obligation")
    changed = values["changed-candidate"]
    require(set(changed) == {"response","bundle_sha256"}, "CAR candidate control shape changed")
    require(_sha(changed["bundle_sha256"]) and _sha(values["changed-fasta"].get("bundle_sha256")), "CAR mutated archive lacks exact byte identity")
    _negative_response(changed["response"],"policy_expression_export_not_accepted")
    require(same(values["changed-fasta"], {"status":"rejected","boundary":"exact_native_pair_comparison","bundle_sha256":values["changed-fasta"].get("bundle_sha256")}), "CAR FASTA control changed")
    altered = deepcopy(values["originals"]); altered["title"] += " changed"; altered["request"]["project_context"]["title"] = altered["title"]
    require(same(values["changed-metadata"], {"status":"rejected","boundary":"independent_original_authority","changed_project_sha256":canonical_digest(altered)}), "CAR metadata control lost original authority")
    for name,req in (("changed-authority",changed_authority(request)),("missing-chemistry",request)):
        checked_result(values[name],packet,req,operation="check",accepted=False)
        require(values[name]["report"]["structure"]["outcome"] != "pass", "CAR altered material acquired structural acceptance")
    _negative_response(values["forged-replay"],"policy_expression_replay")
    _negative_response(values["work-exhaustion"],"policy_expression_material_work_limit")
    check_actions(values["native-actions"],values,packet)
    return values


def validate_files(values, packet, artifacts, *, projects, publications, native_actions):
    """Join every retained byte to independently checked originals/results; no native call."""
    from biocompiler.core_client import encode_json
    from biocompiler.policy.material import _verify_staged
    artifacts = Path(artifacts)
    check_observations(values,packet)
    require(type(projects) is dict and set(projects) == set(CASE_IDS) and same(native_actions, values["native-actions"]), "CAR project/action census changed")
    require(same(publications, [values["paired-publication"],values["tight-paired-publication"]]), "CAR publication census changed")
    require(not artifacts.is_symlink() and artifacts.is_dir() and {p.name for p in artifacts.iterdir()} == set(EVIDENCE_FILES), "CAR complete retained-file census changed")
    require(all(not (artifacts/name).is_symlink() and (artifacts/name).is_file() for name in EVIDENCE_FILES),
            "CAR retained evidence must be regular files without redirection")
    for name in OBSERVATIONS:
        path=artifacts/(name+".json")
        require(not path.is_symlink() and path.is_file() and path.stat().st_size <= MAX_EVIDENCE and path.read_bytes() == encode_json(values[name]), "CAR retained observation bytes changed")
    for case in CASE_IDS:
        path=artifacts/(case+"-project.json"); raw=encode_json(expected_project(packet,case))
        require(not path.is_symlink() and path.is_file() and path.stat().st_size == len(raw) and path.read_bytes() == raw
                and same(projects[case], {"path":path.name,"sha256":hashlib.sha256(raw).hexdigest(),"project_sha256":canonical_digest(expected_project(packet,case)),"request_sha256":canonical_digest(request_for(packet,case))}), "CAR retained project differs from original authority")
    for case,name in (("base","export-verify"),("tight","tight-export-verify")):
        archive_receipt(values[name],artifacts/(case+".zip"))
    for kind in ("candidate","fasta"):
        path=artifacts/("base-changed-"+kind+".zip")
        _verify_staged(path,mutated_pair(values["export-verify"],kind))
        require(digest_file(path) == values["changed-"+kind]["bundle_sha256"], "CAR declared mutation bytes changed")


def load_example(path):
    spec=importlib.util.spec_from_file_location("car_payload_example",path)
    require(spec is not None and spec.loader is not None,"Missing public CAR example")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def exercise(packet, example, core, verify, retain, artifacts, *, use_installed_defaults=False):
    from biocompiler.core_client import CoreRejected
    from biocompiler.core_policy_expression_material import PolicyExpressionMaterialClient
    from biocompiler.policy.research_project import ResearchProject, ResearchProjectError, ResearchProjectRejected
    require(type(use_installed_defaults) is bool,"Explicit CAR resolution mode required")
    artifacts=Path(artifacts); values={}; projects={}; publications=[]
    def save(name,value):
        require(name == OBSERVATIONS[len(values)],"CAR exercise order changed");values[name]=value;retain(name,value)
    public_core,public_verify=(None,None) if use_installed_defaults else (core,verify)
    with action_log(core,verify,installed=use_installed_defaults) as log:
        def prepare(case):
            path=artifacts/(case+"-project.json")
            project=example.prepare(path,maximum_rna_nt=packet['expected']['maximum_rna_nt'][case],three_prime_end='designer_supplied_hydroxyl')
            require(same(project.data, expected_project(packet,case)) and same(ResearchProject.load(path).expression.to_request(), request_for(packet,case)),"Public CAR preparation changed exact originals")
            projects[case]={"path":path.name,"sha256":digest_file(path),"project_sha256":project.digest,"request_sha256":canonical_digest(project.request)}
            return project,path
        base,path=prepare('base'); save('originals',base.data)
        save('typed-roundtrip',{'project_sha256':base.digest,'request_sha256':canonical_digest(base.request),'source_profile':base.request['document']['profile'],'native_status':'not_run','biological_status':'unassessed'})
        save('preflight',example.preflight(path));log['phase']='base-build'
        built=example.compile_project(path,artifacts/'base.zip',core=public_core,verify=public_verify)
        save('compile-core',built.compiled.result);save('export-verify',built.verified.result)
        log['phase']='base-reopen';fresh=example.verify_project(path,artifacts/'base.zip',verify=public_verify)
        save('reverify-verify',fresh.result);pair={**archive_receipt(fresh.result,artifacts/'base.zip'),'path':'base.zip'}
        save('paired-publication',pair);publications.append(pair)
        tight,tight_path=prepare('tight');save('tight-originals',tight.data);log['phase']='tight-build'
        tightened=example.compile_project(tight_path,artifacts/'tight.zip',core=public_core,verify=public_verify)
        save('tight-compile-core',tightened.compiled.result);save('tight-export-verify',tightened.verified.result)
        pair={**archive_receipt(tightened.verified.result,artifacts/'tight.zip'),'path':'tight.zip'}
        save('tight-paired-publication',pair);publications.append(pair)
        short,short_path=prepare('short');save('short-originals',short.data);log['phase']='short-build'
        try: example.compile_project(short_path,artifacts/'short.zip',core=public_core,verify=public_verify)
        except ResearchProjectRejected as error:
            save('short-compile-core',error.compiled.result)
            require(not (artifacts/'short.zip').exists(),'Rejected CAR edit published output')
            save('short-no-publication',{'status':'not_accepted','artifact':'absent','requirement':'encode_car'})
        else: raise AssertionError('1775nt CAR source bound acquired acceptance')
        for kind in ('candidate','fasta'):
            mutant=artifacts/('base-changed-'+kind+'.zip');write_mutant(mutant,fresh.result,kind);log['phase']='changed-'+kind
            try: example.verify_project(path,mutant,verify=public_verify)
            except CoreRejected as error:
                require(kind=='candidate','FASTA failed at an unrelated native boundary')
                value={'response':response_data(error.response),'bundle_sha256':digest_file(mutant)}
            except ResearchProjectError as error:
                require(kind=='fasta' and 'exact FASTA/manifest pair' in str(error),'CAR mutation failed at an unrelated boundary')
                value={'status':'rejected','boundary':'exact_native_pair_comparison','bundle_sha256':digest_file(mutant)}
            else: raise AssertionError('Changed CAR bundle acquired acceptance')
            save('changed-'+kind,value)
        altered=base.data;altered['title']+=' changed';altered['request']['project_context']['title']=altered['title'];log['phase']='changed-metadata'
        try: ResearchProject.from_data(altered).verify_bundle(artifacts/'base.zip',verify=public_verify)
        except ResearchProjectError as error:
            require('authority differs' in str(error),'CAR original mutation failed at unrelated boundary')
            save('changed-metadata',{'status':'rejected','boundary':'independent_original_authority','changed_project_sha256':canonical_digest(altered)})
        else: raise AssertionError('Changed original metadata reused an old CAR bundle')
        request=base.request;candidate=built.compiled.candidate;client=PolicyExpressionMaterialClient(verify)
        log['phase']='changed-authority';save('changed-authority',client.check(changed_authority(request),candidate).result)
        log['phase']='missing-chemistry';missing=client.check(request,changed_candidate(candidate,'chemistry')).result
        # Execute in action order while retaining the fixed public observation order.
        log['phase']='forged-replay'
        try: verify.call('replay-policy-expression-material',{'request':request,'candidate':candidate,'report':forged_replay(built.compiled.result)})
        except CoreRejected as error: save('forged-replay',response_data(error.response))
        else: raise AssertionError('Forged saved CAR report acquired replay authority')
        save('missing-chemistry',missing)
        low=deepcopy(request);low['budgets']['max_work']=1;log['phase']='work-exhaustion'
        try: verify.call('check-policy-expression-material',{'request':low,'candidate':candidate})
        except CoreRejected as error: save('work-exhaustion',response_data(error.response))
        else: raise AssertionError('CAR work exhaustion acquired acceptance')
    actions={'schema_version':'biocompiler.car_native_actions.v0.1','resolution':'owned_installed_defaults' if use_installed_defaults else 'explicit_pinned','actions':log['rows']}
    save('native-actions',actions);check_observations(values,packet)
    return {'projects':projects,'publications':publications,'native_actions':actions}


def tracked_inputs(root):
    rows=git(root,'ls-tree','-r','-z','HEAD','--',*INPUTS).split(b'\0');result={}
    for row in filter(None,rows):
        head,path=row.split(b'\t',1);mode,kind,blob=head.decode().split();name=path.decode()
        require(name in INPUTS and name not in result and mode in {'100644','100755'} and kind=='blob','Unreviewed CAR input')
        raw=(root/name).read_bytes()
        require(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==blob,'CAR input differs from HEAD')
        result[name]={**pin(root,name),'git_blob':blob}
    require(set(result)==set(INPUTS),'Missing complete CAR source input census');return result


def run(args):
    root=Path(__file__).resolve().parents[1]
    hosted,source,before=identity(root),source_identity(),source_snapshot(root)
    inputs=tracked_inputs(root);packet=checked_assets(root,args.expected)
    paths={role:getattr(args,role).resolve(strict=True) for role in NATIVE_PATHS}
    require(all(path==(root/NATIVE_PATHS[role]).resolve() for role,path in paths.items()),'Use exact current hosted CAR executables')
    binaries={role:pin(root,path,executable=True) for role,path in NATIVE_PATHS.items()}
    output=args.output.resolve();require(output==(root/OUTPUT).resolve() and not args.output.is_symlink() and not output.exists(),'Use a fresh fixed CAR receipt path')
    artifacts=output.with_suffix('');artifacts.mkdir(exist_ok=False)
    result={'schema_version':SCHEMA,'status':'incomplete','acceptance':False,'scope':SCOPE,'identity':hosted,'source_identity':source,
        'python':platform.python_version(),'binary_sha256':binaries,'inputs':inputs,'observations':[],
        'python_semantic_authority':'forbidden','empirical':'unassessed','human_use':'unassessed'}
    previous,boundary,start=sys.getprofile(),None,time.monotonic()
    def save():
        raw=(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();require(len(raw)<=MAX_RECEIPT,'CAR receipt exceeds bound');output.write_bytes(raw)
    def retain(name,value):
        from biocompiler.core_client import encode_json
        require(name==OBSERVATIONS[len(result['observations'])],'CAR sidecar order changed')
        raw=encode_json(value);require(len(raw)<=MAX_EVIDENCE,'CAR observation exceeds bound')
        path=artifacts/(name+'.json')
        with path.open('xb') as stream:stream.write(raw)
        result['observations'].append({'name':name,'path':str(path.relative_to(output.parent)),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)});save()
    try:
        sys.path.insert(0,str(root/'src'));spec=importlib.util.find_spec('biocompiler')
        require(spec is not None and Path(spec.origin).resolve()==root/'src/biocompiler/__init__.py','Foreign CAR SDK')
        boundary=CarBoundary(root/'src/biocompiler');sys.meta_path.insert(0,boundary);sys.setprofile(boundary.trace)
        from biocompiler.core_client import CoreClient
        example=load_example(root/EXAMPLE)
        transports={role:CoreClient(paths[role],role=role,expected_sha256=binaries[role]['sha256'],timeout_seconds=90) for role in NATIVE_PATHS}
        fields=exercise(packet,example,transports['core'],transports['verify'],retain,artifacts)
        values={row['name']:read_json(output.parent/row['path'],MAX_EVIDENCE) for row in result['observations']}
        validate_files(values,packet,artifacts,**fields)
        # Full action evidence is already a separately pinned sidecar; metadata avoids duplicating it.
        result.update(projects=fields['projects'],publications=fields['publications'],native_actions_sha256=canonical_digest(fields['native_actions']))
        result['parent_imports']=boundary.origins();require(REQUIRED_MODULES<=set(result['parent_imports']),'Missing CAR public path imports');result['status']='passed'
    except Exception as error:
        result.update(status='failed',error=f'{type(error).__name__}: {error}');raise
    finally:
        sys.setprofile(previous)
        if boundary is not None:sys.meta_path.remove(boundary)
        result['elapsed_seconds']=round(time.monotonic()-start,3)
        try:
            require(identity(root)==hosted and source_identity()==source and source_snapshot(root)==before and tracked_inputs(root)==inputs and
                {role:pin(root,path,executable=True) for role,path in NATIVE_PATHS.items()}==binaries,'CAR source/executable/identity changed')
            result['source_snapshot_sha256']=canonical_digest(before)
        except Exception as error:result.update(status='failed',source_error=str(error))
        save();require(result['status']=='passed',result.get('source_error',result.get('error','Incomplete CAR campaign')))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('core','verify','expected','output'):parser.add_argument('--'+name,type=Path,required=True)
    print(json.dumps(run(parser.parse_args()),sort_keys=True))


if __name__=='__main__':main()

"""Hosted native campaign for the complete supplied CAR197/206 RNA adaptation.

The frozen project is original authority, never a saved candidate or acceptance
token. Source acquisition is a separate audit and is not replayed here. Importing
this module or inspecting a receipt performs no native execution.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import zipfile
from unittest.mock import patch

from biocompiler.core_client import CoreClient, CoreRejected, PROTOCOL, decode_json, encode_json
from biocompiler.core_policy_controlled_workflow import PolicyControlledWorkflowClient
from biocompiler.policy.controlled_behavior import ControlledBehaviorRequest
from biocompiler.policy.controlled_workflow import ControlledWorkflowRequest
from biocompiler.policy.research_project import ResearchProject, ResearchProjectError
try:
    from . import check_controlled_research_project as shared
    from .check_policy_controlled_behavior import file_pin, imported_modules, require
    from .check_policy_core import source_identity
except ImportError:
    import check_controlled_research_project as shared
    from check_policy_controlled_behavior import file_pin, imported_modules, require
    from check_policy_core import source_identity

ROOT = Path(__file__).resolve().parents[1]
PROJECT_SHA256 = "2d81c496a0f3167fb524ddd1ebc0d59741daebf79a0f3ce8e8a308c2b311fbd6"
EXPECTED = ROOT / "data/car_controlled_reference/rna-adaptation-expected.json"
EXPECTED_SHA256 = "0d99c83fed06166de5ba8ccc718f9e544c0dc2328bac55f8b8d9911fad763b86"
CONTRACT = ROOT / "data/car_controlled_reference/controller-readout-contract.json"
CONTRACT_SHA256 = "9778b47fd2bf31caf66148b5ca3f9faa31173e19bdfa5adb14c7c66cf506bde7"
SCHEMA = "biocompiler.controlled_car_reference_campaign.v0.1"
ACCEPTED = ("baseline", "tight-deadlines", "horizon-eleven")
REJECTED = ("short-member", "short-total", "short-horizon", "stale-controller-contract")
CASES = ACCEPTED + REJECTED
MUTATIONS = ("changed-fasta-a", "changed-fasta-b", "changed-candidate-a", "changed-candidate-b", "changed-manifest")
CONTROLS = ("check-verify", "replay-verify", *MUTATIONS, "stale-project", "verify-producer")
OBSERVATIONS = tuple(case + "-" + stage for case in CASES
    for stage in (("prepared", "compile", "export", "reverify", "publication") if case in ACCEPTED else ("prepared", "compile"))) + CONTROLS
REJECTION = {
    "short-member": ("controlled_authority_admission", "Original RNA length exceeds supplied per-member/total resources."),
    "short-total": ("controlled_authority_admission", "Original RNA length exceeds supplied per-member/total resources."),
    "short-horizon": ("policy_controlled_domain", "Hold suffix cannot cover every original source deadline."),
    "stale-controller-contract": ("policy_controlled_source", "Definition reference differs from the full original body/version/digest."),
}


def digest(value):
    return hashlib.sha256(encode_json(value, limit=16 * 1024 * 1024)).hexdigest()


def load(path):
    file_pin(path, 16 * 1024 * 1024)
    return decode_json(Path(path).read_bytes())


def checked_project(path):
    """Check frozen originals and independent molecular expectations before native I/O."""
    pins = {"project": file_pin(path), "expected": file_pin(EXPECTED), "contract": file_pin(CONTRACT)}
    require([pins[key]["sha256"] for key in ("project", "expected", "contract")] ==
            [PROJECT_SHA256, EXPECTED_SHA256, CONTRACT_SHA256], "Independent project/expectation/contract authority changed")
    project = ResearchProject.load(path)
    expected = load(EXPECTED)
    original = project.request["behavior_request"]["original"]
    context = original["source_authority"]["project_context"]
    require(project.data["sources"] == context["sources"] and project.data["assumptions"] == context["assumptions"],
            "Outer project differs from complete source authority")
    sources = {row["id"]: row for row in context["sources"]}
    local_sources = {}
    for source in sources.values():
        locator = source["locator"]
        if locator.startswith("repository:"):
            relative = locator.removeprefix("repository:")
        elif locator == "package:biocompiler.policy/data/car_rm61461_reference_v01.json":
            relative = "src/biocompiler/policy/data/car_rm61461_reference_v01.json"
        else:
            continue
        current = ROOT / relative
        require(not Path(relative).is_absolute() and ".." not in Path(relative).parts,
                "Local source locator escapes the checkout")
        local_sources[source["id"]] = file_pin(current)
        require(local_sources[source["id"]]["sha256"] == source["sha256"], "Current local source differs from project pin")
    require(set(local_sources) == {"controlled.acquisition.inventory", "car.rm61461.reference_pack",
            "controlled.car197206.adaptation", "controlled.car197206.contract"}, "Local original source census differs")
    pins["local_sources"] = local_sources
    require(sources["controlled.car197206.adaptation"]["sha256"] == EXPECTED_SHA256 and
            sources["controlled.car197206.contract"]["sha256"] == CONTRACT_SHA256,
            "Project molecular/behavior provenance differs from independent frozen originals")
    material = original["material_authority"]
    require(material["member_order"] == [row["id"] for row in expected["members"]] == ["car197", "car206"], "Original RNA order changed")
    roots = {row["id"]: row["molecule"] for row in material["template"]["sources"]}
    outputs = {row["id"]: row for row in material["template"]["output_members"]}
    sequences = []
    for member, oracle in zip(material["members"], expected["members"], strict=True):
        output = outputs[member["id"]]
        require(output["value"]["kind"] == "root", "Original must retain direct complete RNA roots")
        molecule = roots[output["value"]["id"]]
        sequence = molecule["sequence"]
        require(len(sequence) == oracle["rna_nt"] and hashlib.sha256(sequence.encode()).hexdigest() == oracle["rna_sha256"],
                "Original RNA differs from independently prepared complete sequence expectation")
        require(len(member["product"]["sequence"]) == oracle["protein_aa"] and
                hashlib.sha256(member["product"]["sequence"].encode()).hexdigest() == oracle["protein_sha256"] and
                member["product"]["identity"]["content_fingerprint"] == oracle["product_content_fingerprint"],
                "Original product differs from independent protein expectation")
        sequences.append(sequence)
    return {"project": project, "expected": expected, "pins": pins, "sequences": sequences}


def cases(project):
    """Apply public source edits without changing the selected mechanism or RNAs."""
    base = project.controlled
    lengths = base.limits["resources"]
    values = {"baseline": base, "tight-deadlines": base.with_deadlines(
        onset_ticks=1, controller_off_ticks=1, antigen_off_ticks=1, component_off_ticks=1, reactivation_ticks=1)}
    behavior = base.behavior.to_request()
    for name, horizon in (("horizon-eleven", 11), ("short-horizon", 9)):
        domain = deepcopy(behavior["original"]["operating_domain"])
        domain["horizon_tick"] = horizon
        domain["fixed_inputs"] = [row for row in domain["fixed_inputs"] if row["tick"] <= horizon]
        if horizon == 11:
            tail = deepcopy(domain["fixed_inputs"][-1]); tail["tick"] = 11
            for row in tail["evidence"].values():
                row["observed_tick"] = 11
            domain["fixed_inputs"].append(tail)
        readout = deepcopy(behavior["readout_evidence"])
        readout["samples"] = [{"tick": tick, "observed_tick": tick, "status": "valid"} for tick in range(horizon + 1)]
        values[name] = base.with_horizon(horizon, operating_domain=domain, readout_evidence=readout)
    values["short-member"] = base.with_rna_limits(max_member_rna_nt=lengths["max_member_rna_nt"] - 1,
                                                 max_total_rna_nt=lengths["max_total_rna_nt"])
    values["short-total"] = base.with_rna_limits(max_member_rna_nt=lengths["max_member_rna_nt"],
                                                max_total_rna_nt=lengths["max_total_rna_nt"] - 1)
    changed = deepcopy(behavior)
    definitions = changed["original"]["source_authority"]["document"]["program"]["semantics"]["definitions"]
    controller_id = changed["original"]["source_authority"]["control_contract"]["controller"]["definition"]["id"]
    next(row for row in definitions if row["id"] == controller_id)["meaning"] += " Altered unpinned controller interpretation."
    values["stale-controller-contract"] = ControlledWorkflowRequest.from_behavior(ControlledBehaviorRequest.from_request(changed))
    return {name: ResearchProject.from_controlled(values[name]) for name in CASES}


def expected_case(name, original, sequences):
    horizon = original["limits"]["horizon_tick"]
    return {"id": name, "status": "accepted", "horizon_tick": horizon,
            "member_order": ["car197", "car206"], "sequences": sequences,
            "histories": 2, "prefixes": 2 * horizon + 1, "transitions": 2 * horizon}


def expected_fasta(sequences):
    """Literal published representation: fixed ordered IDs and 80-column RNA."""
    require(len(sequences) == 2 and all(type(value) is str and value and set(value) <= set("ACGU") for value in sequences),
            "Exactly two complete canonical RNA strings are required")
    return "".join(">rna_%04d alphabet=RNA\n" % (index + 1) +
                   "".join(sequence[offset:offset + 80] + "\n" for offset in range(0, len(sequence), 80))
                   for index, sequence in enumerate(sequences))


def check_result(value, name, original, sequences, *, exported=False):
    # Reuse the existing strict source-count/nonvacuity/report checker. Full RNA
    # strings have first been checked against independent fixed sequence hashes.
    # Shared checks own the assessment. Validate the real-length exported pair
    # separately because the artificial oracle spells only one short RNA line.
    assessment_view = {**value, "artifact": None} if exported else value
    shared.check_result(assessment_view, expected_case(name, original, sequences), original)
    structure = value["report"]["material"]["structure"]
    source = original["behavior_request"]["original"]
    definitions = source["source_authority"]["document"]["program"]["semantics"]["definitions"]
    nominal = [row for row in definitions if row["id"] == "biocompiler.controlled.nominal_translation.v1"]
    require(len(nominal) == 1 and structure["schema_version"] == "biocompiler.policy_controlled_nominal_structure_assessment.v0.1"
            and structure["profile"] == "biocompiler.policy_controlled_nominal_structure.v0.1"
            and structure["claim_scope"] == "exact_supplied_mrna_structure_under_explicit_controlled_nominal_translation_premise"
            and structure["source_request_fingerprint"] == digest(source)
            and structure["nominal_translation_definition"] == nominal[0]
            and structure["physical_translation_status"] == "unassessed",
            "Nominal structural evidence lost its explicit source premise or empirical boundary")
    if exported:
        artifact = value["artifact"]
        require(artifact is not None and artifact["fasta"] == expected_fasta(sequences), "Exact independently expected wrapped RNA pair differs")
        manifest = artifact["manifest"]
        require(manifest["request"] == original and manifest["limits"] == original["limits"] and
                manifest["candidate"] == value["candidate"] and manifest["report"] == value["report"],
                "Published complete originals/candidate/report changed")
        require([row["member_id"] for row in manifest["members"]] == ["car197", "car206"], "Publication member order changed")


def check_pair(path, value, sequences):
    artifact = value["artifact"]
    require(artifact is not None and artifact["fasta"] == expected_fasta(sequences), "Published FASTA differs from independent RNA oracle")
    with zipfile.ZipFile(path) as archive:
        require(archive.namelist() == ["program.fasta", "manifest.json"] and
                all(row.compress_type == zipfile.ZIP_STORED and not row.flag_bits for row in archive.infolist()),
                "Paired archive representation or member census differs")
        require(archive.read("program.fasta") == artifact["fasta"].encode() and
                archive.read("manifest.json") == encode_json(artifact["manifest"]), "Published bytes differ from fresh Verify")
    return {"path": Path(path).name, **file_pin(path), "fasta_sha256": hashlib.sha256(artifact["fasta"].encode()).hexdigest(),
            "manifest_sha256": digest(artifact["manifest"])}


def check_rejection(value, name):
    require(name in REJECTION and value["status"] == "error" and len(value["diagnostics"]) == 1,
            "Required source edit rejected at an unrelated boundary")
    diagnostic = value["diagnostics"][0]
    require((diagnostic["code"], diagnostic["message"]) == REJECTION[name], "Wrong original-authority rejection diagnostic")
    require(set(diagnostic) == {"code", "message", "path"}, "Rejection diagnostic lost complete provenance")


def changed_candidate(candidate, name):
    """Alter an unmodified UTR base, preserving chemistry decoding for the check."""
    require(name in ("changed-candidate-a", "changed-candidate-b"), "Unknown candidate mutation")
    changed = deepcopy(candidate)
    inventory = changed["material_candidate"]["construction"]["inventory"]
    molecule = inventory["molecules"][0 if name.endswith("a") else 1]
    sequence = molecule["sequence"]
    require(len(sequence) > 8 and sequence[8] == "A", "Independent neutral UTR mutation site differs")
    # Index zero carries declared Am. All-U modifications also remain intact.
    # This A-to-C edit at index eight reaches independent content reconstruction.
    molecule["sequence"] = sequence[:8] + "C" + sequence[9:]
    for role in inventory["role_instances"]:
        if role["subject_id"] == molecule["id"]:
            role["subject_fingerprint"] = digest(molecule)
    return changed


def changed_bundle(source, target, name):
    if name == "changed-manifest":
        shared.changed_bundle(source, target, name)
        return
    with zipfile.ZipFile(source) as archive:
        fasta = archive.read("program.fasta")
        manifest = decode_json(archive.read("manifest.json"))
    if name.startswith("changed-candidate"):
        manifest["candidate"] = changed_candidate(manifest["candidate"], name)
    else:
        fasta = changed_fasta(fasta, name)
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_STORED) as archive:
        for filename, raw in (("program.fasta", fasta), ("manifest.json", encode_json(manifest))):
            info = zipfile.ZipInfo(filename, (1980, 1, 1, 0, 0, 0)); info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)


def changed_fasta(fasta, name):
    require(name in ("changed-fasta-a", "changed-fasta-b"), "Unknown FASTA mutation")
    lines = fasta.split(b"\n")
    header = b">rna_0001 alphabet=RNA" if name.endswith("a") else b">rna_0002 alphabet=RNA"
    require(lines.count(header) == 1, "Exact ordered FASTA member header is absent or duplicated")
    index = lines.index(header) + 1
    require(index < len(lines) and lines[index].startswith(b"A"), "Selected reference RNA first base differs")
    lines[index] = b"G" + lines[index][1:]
    return b"\n".join(lines)


def exercise(packet, core, verify, retain, folder):
    projects = cases(packet["project"])
    published = {}
    for name, project in projects.items():
        path = folder / (name + "-project.json"); project.dump(path)
        retain(name + "-prepared", {"project": project.data, "preflight": asdict(project.preflight())})
        bundle = folder / (name + ".zip")
        try:
            built = project.compile(output=bundle, core=core, verify=verify)
        except CoreRejected as error:
            require(error.response.result is None and name in REJECTED, "Unexpected native admission failure")
            value = {"status": error.response.status, "diagnostics": [asdict(item) for item in error.response.diagnostics]}
            check_rejection(value, name); retain(name + "-compile", value)
            require(not bundle.exists(), "Rejected original published a bundle")
            continue
        require(name in ACCEPTED, "Changed original unexpectedly gained acceptance")
        for stage, result, exported in (("compile", built.compiled, False), ("export", built.verified, True)):
            check_result(result.result, name, project.request, packet["sequences"], exported=exported)
            retain(name + "-" + stage, result.result)
        reopened = ResearchProject.load(path).verify_bundle(bundle, verify=verify)
        require(reopened.result == built.verified.result, "Fresh Verify-only reopen changed complete evidence")
        retain(name + "-reverify", reopened.result)
        pair = check_pair(bundle, reopened.result, packet["sequences"])
        retain(name + "-publication", pair)
        published[name] = built
    baseline = projects["baseline"]; built = published["baseline"]
    client = PolicyControlledWorkflowClient(verify)
    for verb in ("check", "replay"):
        result = (client.check(baseline.request, built.compiled.candidate) if verb == "check" else
                  client.replay(baseline.request, built.compiled.candidate, built.compiled.report))
        require(result.report == built.compiled.report and result.candidate == built.compiled.candidate,
                "Fresh independent Verify check/replay differs")
        retain(verb + "-verify", result.result)
    for name in MUTATIONS:
        target = folder / (name + ".zip")
        changed_bundle(folder / "baseline.zip", target, name)
        try:
            baseline.verify_bundle(target, verify=verify)
        except ResearchProjectError as error:
            expected = ("Independent Verify did not produce an accepted pair" if name.startswith("changed-candidate") else
                        "Bundle differs from the independently verified exact FASTA/manifest pair")
            require(str(error) == expected, "Tampering rejected at an unrelated boundary")
            retain(name, {"status": "rejected", "message": str(error), "bundle": file_pin(target)})
        else:
            raise AssertionError("Tampered paired export acquired acceptance")
    try:
        projects["tight-deadlines"].verify_bundle(folder / "baseline.zip", verify=verify)
    except ResearchProjectError as error:
        require(str(error) == "Bundle original authority differs from the independently supplied current project", "Stale bundle rejected elsewhere")
        retain("stale-project", {"status": "rejected", "message": str(error)})
    else:
        raise AssertionError("Changed source requirements accepted old evidence")
    try:
        verify.call("compile-policy-controlled-workflow", {"request": baseline.request})
    except CoreRejected as error:
        require(error.response.status == "unsupported" and [item.code for item in error.response.diagnostics] == ["unsupported_operation"],
                "Verify producer boundary changed")
        retain("verify-producer", {"status": error.response.status, "diagnostics": [asdict(item) for item in error.response.diagnostics]})
    else:
        raise AssertionError("Independent Verify implemented the producer")


def expected_actions(values):
    actions = []
    def add(role, verb, payload, name, negotiate=True):
        operation = verb + "-policy-controlled-workflow"
        if negotiate:
            actions.append({"role": role, "operation": "capabilities", "payload": {}, "next_operation": operation})
        actions.append({"role": role, "operation": operation, "payload": payload, "name": name})
    for name in CASES:
        request = values[name + "-prepared"]["project"]["request"]
        add("core", "compile", {"request": request}, name + "-compile")
        if name in ACCEPTED:
            payload = {"request": request, "candidate": values[name + "-compile"]["candidate"]}
            add("verify", "export", payload, name + "-export")
            add("verify", "export", payload, name + "-reverify")
    request = values["baseline-prepared"]["project"]["request"]
    candidate = values["baseline-compile"]["candidate"]
    add("verify", "check", {"request": request, "candidate": candidate}, "check-verify")
    add("verify", "replay", {"request": request, "candidate": candidate, "report": values["baseline-compile"]["report"]}, "replay-verify")
    for name in MUTATIONS:
        changed = changed_candidate(candidate, name) if name.startswith("changed-candidate") else deepcopy(candidate)
        add("verify", "export", {"request": request, "candidate": changed}, name)
    add("verify", "compile", {"request": request}, "verify-producer", negotiate=False)
    return actions


def validate_receipt(receipt, folder, packet):
    """Recheck retained bytes and actual invocation correspondence, without execution."""
    from biocompiler.core_client import _response, _capabilities
    from biocompiler.core_policy_controlled_workflow import _result, PROFILE, PRODUCER_PROFILE, VALIDATION_SCOPE
    require(receipt["schema_version"] == SCHEMA and receipt["status"] == "passed" and receipt["release_acceptance"] is False,
            "Incomplete campaign receipt")
    require(receipt["inputs"] == packet["pins"] and tuple(row["name"] for row in receipt["observations"]) == OBSERVATIONS,
            "Missing, reordered or stale observations")
    require(receipt["script"] == file_pin(__file__) and receipt["identity"] == receipt["native_authority"]["identity"],
            "Campaign script or same-run native source identity differs")
    require(receipt["empirical_status"] == receipt["human_use"] == "unassessed" and
            receipt["source_acquisition"] == "separately_audited_not_replayed_hosted", "Campaign evidence scope promoted")
    values = {}
    for row in receipt["observations"]:
        path = folder / (row["name"] + ".json")
        require(row["file"] == path.name and file_pin(path) == {key: row[key] for key in ("sha256", "bytes")}, "Observation bytes changed")
        values[row["name"]] = load(path)
    for name, project in cases(packet["project"]).items():
        require(values[name + "-prepared"] == {"project": project.data, "preflight": asdict(project.preflight())} and
                load(folder / (name + "-project.json")) == project.data, "Prepared complete original changed")
        if name in REJECTED:
            check_rejection(values[name + "-compile"], name)
            require(not (folder / (name + ".zip")).exists(), "Rejected project published a pair")
        else:
            check_result(values[name + "-compile"], name, project.request, packet["sequences"])
            check_result(values[name + "-export"], name, project.request, packet["sequences"], exported=True)
            require(values[name + "-reverify"] == values[name + "-export"], "Fresh reopen evidence changed")
            require(check_pair(folder / (name + ".zip"), values[name + "-export"],
                    packet["sequences"]) == values[name + "-publication"], "Published pair differs")
    actions = expected_actions(values)
    require(len(actions) == len(receipt["native_frames"]) == 41 and
            len({row["request_id"] for row in receipt["native_frames"]}) == 41, "Native invocation census differs")
    for index, (row, action) in enumerate(zip(receipt["native_frames"], actions, strict=True)):
        path = folder / ("native-%03d.json" % index)
        require(row["file"] == path.name and file_pin(path) == {key: row[key] for key in ("sha256", "bytes")}, "Native frame bytes changed")
        wire = load(path); frame = wire["frame"]
        require(set(wire) == {"payload", "frame"} and wire["payload"] == action["payload"] and
                row["operation"] == action["operation"] and row["executable"] == action["role"], "Native payload, operation or role changed")
        raw = encode_json(frame, limit=16 * 1024 * 1024)
        require(hashlib.sha256(raw).hexdigest() == row["response_sha256"], "Decoded response changed")
        response = _response(raw, {"ok": 0, "error": 2, "unsupported": 3}[frame["status"]],
                             row["request_id"], row["operation"], row["executable"])
        if action["operation"] == "capabilities":
            capabilities = _capabilities(response.result); capabilities.require_operation(action["next_operation"])
            require(response.status == "ok" and not response.diagnostics and
                    capabilities.profiles.get("policy_controlled_workflow") == (PRODUCER_PROFILE if action["role"] == "core" else PROFILE)
                    and VALIDATION_SCOPE in capabilities.validation_scopes, "Wrong native capability handshake")
            continue
        name = action["name"]
        if (name.endswith("-compile") and name[:-8] in REJECTED) or name == "verify-producer":
            require(response.result is None and values[name] == {"status": response.status,
                    "diagnostics": [asdict(item) for item in response.diagnostics]}, "Saved rejection differs from actual native frame")
        else:
            checked = _result(response, wire["payload"]).result
            if name in MUTATIONS:
                if name.startswith("changed-candidate"):
                    report = checked["report"]; structure = report["material"]["structure"]
                    require(checked["artifact"] is None and report["outcome"] == "fail" and
                            structure["content_reconstruction"]["diagnostics"] == ["fail:content:inventory"] and
                            report["behavior"] == values["baseline-compile"]["report"]["behavior"], "Molecular tampering rejected elsewhere")
                else:
                    require(checked == values["baseline-export"], "Export-byte mutation changed fresh native evidence")
                expected_message = ("Independent Verify did not produce an accepted pair" if name.startswith("changed-candidate") else
                                    "Bundle differs from the independently verified exact FASTA/manifest pair")
                require(values[name] == {"status": "rejected", "message": expected_message,
                        "bundle": file_pin(folder / (name + ".zip"))}, "Tampering sidecar differs")
            else:
                require(checked == values[name], "Saved result differs from actual native evidence")
    require(values["check-verify"]["report"] == values["replay-verify"]["report"] == values["baseline-compile"]["report"], "Independent check/replay changed report")
    require(values["stale-project"] == {"status": "rejected", "message": "Bundle original authority differs from the independently supplied current project"}, "Stale-project rejection differs")
    require(values["verify-producer"]["status"] == "unsupported" and
            [row["code"] for row in values["verify-producer"]["diagnostics"]] == ["unsupported_operation"], "Verify producer boundary differs")
    from biocompiler.policy.material import _verify_staged
    for name in MUTATIONS:
        artifact = values["baseline-export"]["artifact"]
        fasta, manifest = artifact["fasta"].encode(), deepcopy(artifact["manifest"])
        if name.startswith("changed-fasta"):
            fasta = changed_fasta(fasta, name)
        elif name.startswith("changed-candidate"):
            manifest["candidate"] = next(row["payload"]["candidate"] for row in actions if row.get("name") == name)
        else:
            manifest["report"]["human_use"] = "accepted"
        _verify_staged(folder / (name + ".zip"), (("program.fasta", fasta), ("manifest.json", encode_json(manifest))))
    expected_files = {name + ".json" for name in OBSERVATIONS} | {name + "-project.json" for name in CASES} | {
        name + ".zip" for name in (*ACCEPTED, *MUTATIONS)} | {"native-%03d.json" % index for index in range(41)}
    require(set(receipt["files"]) == expected_files == {path.name for path in folder.iterdir()}, "Campaign artifact census differs")
    require(all(file_pin(folder / name) == pin for name, pin in receipt["files"].items()), "Retained campaign artifact changed")
    return values


def run(args):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Controlled CAR native validation is hosted-only")
    packet = checked_project(args.project)
    output = Path(args.output).absolute()
    require(output.parent.is_dir() and not output.parent.is_symlink() and not output.exists(), "Use a fresh receipt destination")
    folder = output.with_suffix(""); folder.mkdir(exist_ok=False)
    binaries = {role: Path(getattr(args, role)).absolute() for role in ("core", "verify")}
    pins = {role: file_pin(path, 256 * 1024 * 1024) for role, path in binaries.items()}
    identity = source_identity(); authority = shared.native_authority(binaries)
    require(identity["run_id"] != "local", "Native campaign requires hosted source/run identity")
    receipt = {"schema_version": SCHEMA, "status": "incomplete", "release_acceptance": False,
        "identity": identity, "python": platform.python_version(), "platform": platform.system(), "machine": platform.machine(),
        "inputs": packet["pins"], "binaries": pins, "native_authority": authority,
        "source_acquisition": "separately_audited_not_replayed_hosted", "empirical_status": "unassessed", "human_use": "unassessed",
        "observations": [], "native_frames": [], "files": {}, "script": file_pin(__file__)}
    def save():
        output.write_bytes(encode_json(receipt, limit=16 * 1024 * 1024))
    def retain(name, value):
        require(len(receipt["observations"]) < len(OBSERVATIONS) and name == OBSERVATIONS[len(receipt["observations"])], "Observation order changed")
        path = folder / (name + ".json")
        with path.open("xb") as stream:
            stream.write(encode_json(value, limit=16 * 1024 * 1024))
        receipt["observations"].append({"name": name, "file": path.name, **file_pin(path)}); save()
    original_call = CoreClient.call
    def record(response, operation, payload):
        frame = {"protocol": PROTOCOL, "request_id": response.request_id, "operation": response.operation,
            "status": response.status, "result": response.result, "diagnostics": [asdict(item) for item in response.diagnostics],
            "core": {"implementation": "ocaml", "version": response.version, "protocol": PROTOCOL, "executable": response.executable}}
        path = folder / ("native-%03d.json" % len(receipt["native_frames"]))
        with path.open("xb") as stream:
            stream.write(encode_json({"payload": payload, "frame": frame}, limit=16 * 1024 * 1024))
        receipt["native_frames"].append({"file": path.name, **file_pin(path), "response_sha256": digest(frame),
            "request_id": response.request_id, "operation": operation, "executable": response.executable})
    def recording_call(client, operation, payload, **kwargs):
        try:
            response = original_call(client, operation, payload, **kwargs)
        except CoreRejected as error:
            record(error.response, operation, payload); raise
        record(response, operation, payload); return response
    clients = {role: CoreClient(path, role=role, expected_sha256=pins[role]["sha256"], timeout_seconds=300)
               for role, path in binaries.items()}
    try:
        with patch.object(CoreClient, "call", recording_call):
            exercise(packet, clients["core"], clients["verify"], retain, folder)
        require(tuple(row["name"] for row in receipt["observations"]) == OBSERVATIONS, "Incomplete native campaign")
        receipt["imports"] = imported_modules(False)
        shared.unchanged_authority(authority, binaries)
        require(source_identity() == identity and checked_project(args.project)["pins"] == packet["pins"] and
                {role: file_pin(path, 256 * 1024 * 1024) for role, path in binaries.items()} == pins, "Campaign authority changed during execution")
        receipt["files"] = {path.name: file_pin(path) for path in sorted(folder.iterdir())}
        receipt["status"] = "passed"
        validate_receipt(receipt, folder, packet)
    except Exception as error:
        receipt.update(status="failed", error=type(error).__name__ + ": " + str(error)); raise
    finally:
        save()
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--check-inputs", action="store_true")
    for name in ("core", "verify", "output"):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args(argv)
    if args.check_inputs:
        packet = checked_project(args.project)
        print(json.dumps({"status": "original_inputs_checked", "native_status": "not_run",
            "source_acquisition": "separately_audited_not_replayed_hosted", "inputs": packet["pins"],
            "project_sha256": packet["project"].digest}, sort_keys=True))
    else:
        if any(getattr(args, name) is None for name in ("core", "verify", "output")):
            parser.error("Native campaign requires --core, --verify and --output")
        run(args)


if __name__ == "__main__":
    main()

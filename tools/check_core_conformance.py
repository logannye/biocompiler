"""Hosted native conformance: literal expectations, Python oracles, and rejection codes.

Invoke using an installed biocompiler package, with explicit absolute paths to
both native executables. No build, installation, PYTHONPATH change or fallback
occurs here. The pure vector helpers are also exercised by the Python unit suite.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import random
import struct
import subprocess
import sys
import time

import biocompiler
from biocompiler.core_client import (
    CORE_VERSION, LIMITS, PROTOCOL, CoreClient, CoreRejected, CoreUnsupported,
    _exchange, decode_json,
)
from biocompiler.core_architecture import PROFILE as ARCHITECTURE_PROFILE, VALIDATION_SCOPE as ARCHITECTURE_SCOPE
from biocompiler.core_architecture_producer import PROFILE as PRODUCER_PROFILE, VALIDATION_SCOPE as PRODUCER_SCOPE
from biocompiler.core_realization import PROFILES as REALIZATION_PROFILES, OPERATIONS as REALIZATION_OPERATIONS, VALIDATION_SCOPES as REALIZATION_SCOPES
from biocompiler.core_artifacts import TRANSPORT_PROFILE as ARTIFACT_PROFILE
from biocompiler.core_policy import PROFILE as POLICY_PROFILE, VALIDATION_SCOPE as POLICY_SCOPE
from biocompiler.core_policy_operational import (
    PROFILE as OPERATIONAL_PROFILE, PRODUCER_PROFILE as OPERATIONAL_PRODUCER_PROFILE,
    VALIDATION_SCOPE as OPERATIONAL_SCOPE,
)
from biocompiler.core_policy_implementation import (
    PROFILE as IMPLEMENTATION_PROFILE, PRODUCER_PROFILE as IMPLEMENTATION_PRODUCER_PROFILE,
    VALIDATION_SCOPE as IMPLEMENTATION_SCOPE,
)
from biocompiler.core_workflow import capability_profile as workflow_profile, OPERATIONS as WORKFLOW_OPERATIONS
from biocompiler.ir.intent import IntentProgram
from biocompiler.compiler.request import BuildRequest
from biocompiler.ir.behavior import BehaviorProgram


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/core-json-v1.json"
SCOPE = "intent-structure-types-bindings-v1"
LOWERING_SCOPE = "source-to-behavior-correspondence-v1"
LOWERING_CLAIM = "Exact frozen source-to-Behavior correspondence only; no source execution, molecular realization, empirical component function, human therapeutic admission, or complete architecture acceptance."
OBLIGATIONS = ["behavior-lowering", "behavior-execution", "molecular-realization",
               "independent-translation-checking", "human-therapeutic-admission"]


def lowering_cases(root=ROOT):
    """Keep expected source authority separate from supplied Behavior artifacts.

    The broad cases author fresh source only; they do not lower it to manufacture
    the Behavior being checked. Supplied graphs come from retained corpus bytes.
    """
    root = Path(root)
    cases = []
    for name in ("base", "parameter-default", "parameter-override"):
        request = json.loads((root / "tests/conformance/case-b" / name / "request.json").read_text())
        candidate = json.loads((root / "tests/conformance/case-b" / name / "candidate.json").read_text())
        cases.append(("case-b/" + name,
                      request["circuit"]["profile"]["source_request"], candidate["execution"]["behavior"]))
    specification = importlib.util.spec_from_file_location(
        "lowering_conformance_authoring", root / "tools/freeze_behavior_domains.py")
    require(specification is not None and specification.loader is not None, "Missing source authoring fixtures")
    authoring = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(authoring)
    retained = json.loads((root / "tests/conformance/behavior-domains-v1.json").read_text())
    authoring.check_corpus(retained)
    builders = {"algebra": authoring.algebra, "temporal_memory": authoring.temporal_memory,
                "actions_state_signature": authoring.actions_state_signature,
                "sampled_multirole": authoring.sampled_multirole}
    for case in retained["cases"]:
        family = case["id"].rsplit("_", 1)[0]
        source = IntentProgram.from_dict(builders[family]().freeze().to_dict(include_source=False))
        constraints = {} if family != "sampled_multirole" else {
            "execution": {"integral_step": authoring.bc.Duration(1).to_dict()}}
        request = BuildRequest.freeze(source, behavior_profile=case["behavior"]["schema_version"],
                                      implementation_constraints=constraints)
        require(request.intent.fingerprint == case["source_fingerprint"], "Retained source authority drifted")
        cases.append(("broad/" + case["id"], request.to_dict(), case["behavior"]))
    require(len(cases) == 10 and len({name for name, _, _ in cases}) == 10,
            "Incomplete or duplicate lowering corpus")
    return cases


def lowering_expectation(request_document, behavior_document):
    request = BuildRequest.from_dict(request_document)
    behavior = BehaviorProgram.from_dict(behavior_document)
    properties = ["execution_profile", "source_identity", "complete_graph", "parameter_inventory",
                  "authoritative_bindings"]
    for node in request.intent.nodes:
        properties.extend(["operation:" + node.id, "semantics:" + node.id, "source:" + node.id])
    properties.extend(["requirements_and_lineage", "identity_binding"])
    obligations = ["source_behavior_execution", "molecular_realization", "source_to_candidate_preservation",
                   "candidate_acceptance", "empirical_component_function", "human_therapeutic_admission"]
    constraints = dict(request.implementation_constraints)
    if request.behavior_profile == "biocompiler.behavior.v0.2":
        constraints.pop("execution", None)
    if constraints:
        obligations.append("implementation_constraint_enforcement")
    if request.preferences:
        obligations.append("preference_evaluation")
    if request.target is not None:
        obligations.extend(["target_assumption_validation", "biological_evidence_admission"])
    return {
        "schema_version": "biocompiler.lowering_verification.v0.1",
        "checker_version": "biocompiler.ocaml.lowering_check.v0.1",
        "validation_scope": LOWERING_SCOPE, "claim_scope": LOWERING_CLAIM, "passed": True,
        "request_fingerprint": request.fingerprint, "request_artifact_fingerprint": request.artifact_fingerprint,
        "source_fingerprint": request.intent.fingerprint, "behavior_fingerprint": behavior.fingerprint,
        "behavior_artifact_fingerprint": digest(canonical(behavior.to_dict())),
        "behavior_profile": request.behavior_profile, "check_properties": properties,
        "unimplemented_obligations": obligations,
    }


def lowering_mutations(cases):
    """Structurally valid candidates must fail the intended preservation check."""
    _, request, behavior = cases[0]
    changed = deepcopy(behavior)
    changed["name"] += "_different_source"
    result = [("different-source-name", "lowering_source_identity", request, changed)]
    changed = deepcopy(behavior)
    next(node for node in changed["nodes"] if node["kind"] == "and")["kind"] = "or"
    result.append(("changed-operator", "lowering_operation", request, changed))
    changed = deepcopy(behavior)
    node = next(node for node in changed["nodes"] if node["kind"] == "and" and len(node["inputs"]) >= 2)
    node["inputs"] = list(reversed(node["inputs"]))
    result.append(("changed-ordered-edges", "lowering_operation", request, changed))
    changed = deepcopy(behavior)
    literal = next(node for node in changed["nodes"] if node["kind"] == "literal")
    literal["attributes"]["value"]["value"] *= 2
    literal["attributes"]["value"]["canonical_value"] *= 2
    result.append(("changed-time-constant", "lowering_semantics", request, changed))
    changed = deepcopy(behavior)
    literal = next(node for node in changed["nodes"] if node["kind"] == "literal")
    literal["source"] = {"file": "changed.py", "line": 99, "function": "changed"}
    result.append(("changed-source-location", "lowering_source_location", request, changed))
    for name, request, behavior in cases:
        if name == "broad/sampled_multirole_v2":
            changed = deepcopy(behavior)
            # The sampling quantity is a closed policy, independently supplied
            # by the frozen request's execution constraint.
            changed["policies"]["integral_step"]["value"] = 2
            changed["policies"]["integral_step"]["canonical_value"] = 2
            result.append(("changed-sampling-policy", "lowering_execution_profile", request, changed))
    require(len(result) == 6, "Lowering mutation inventory incomplete")
    for name, _, request, behavior in result:
        BuildRequest.from_dict(request)
        BehaviorProgram.from_dict(behavior)
    return result


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def load_corpus(path=CORPUS):
    corpus = json.loads(Path(path).read_text(encoding="utf-8"))
    require(corpus["schema_version"] == "biocompiler.core_json_conformance.v0.1", "Unknown corpus")
    require(len(corpus["literal_vectors"]) >= 10, "Literal corpus is incomplete")
    require(corpus["python_oracle"]["finite_float_count"] >= 2048, "Float coverage below minimum")
    require(1 <= corpus["python_oracle"]["batch_size"] <= 256, "Unbounded float batch")
    require(corpus["python_oracle"].get("binary_boundaries") == {
        "minimum_exponent": -1074, "maximum_exponent": 1023, "ulps_each_side": 4,
    }, "Binary rounding-boundary coverage is incomplete")
    identifiers = []
    for vector in corpus["literal_vectors"]:
        identifiers.append(vector["id"])
        require(digest(vector["canonical_json"]) == vector["sha256"], "Stale literal fingerprint: " + vector["id"])
        # A separate oracle sanity check never changes the stored expectation.
        require(canonical(json.loads(vector["input_json"])) == vector["canonical_json"],
                "Python disagrees with independently retained literal: " + vector["id"])
    identifiers.extend(value["id"] for value in corpus["raw_rejections"])
    require(len(identifiers) == len(set(identifiers)), "Duplicate corpus case identifiers")
    return corpus


def float_patterns(seed, count):
    """Sample bit patterns, not a narrow uniform distribution over small numbers."""
    require(type(count) is int and count >= 2048, "At least 2048 finite patterns are required")
    generator = random.Random(seed)
    patterns = []
    while len(patterns) < count:
        bits = generator.getrandbits(64)
        value = struct.unpack(">d", bits.to_bytes(8, "big"))[0]
        if math.isfinite(value):
            patterns.append((bits, value))
    return patterns


def boundary_floats():
    values = [0.0, -0.0, 5e-324, -5e-324, sys.float_info.min, sys.float_info.max,
              1.0, -1.0, 0.1, 1e-5, 1e-4, 1e15, 1e16]
    for exponent in range(-323, 309):
        value = float("1e" + str(exponent))
        for adjacent in (math.nextafter(value, 0.0), value, math.nextafter(value, math.inf)):
            if math.isfinite(adjacent):
                values.extend((adjacent, -adjacent))
    return values


def binary_boundary_floats(*, minimum_exponent=-1074, maximum_exponent=1023, ulps_each_side=4):
    """Exact powers of two and four adjacent representables on each side.

    Powers of two have asymmetric decimal rounding intervals. A nearest decimal
    that does not round-trip cannot justify ignoring the other adjacent decimal
    at the same precision. Random patterns almost never hit these boundaries.
    Enumerate finite binary64 bit patterns directly, including both signs, and
    deduplicate the overlapping subnormal neighborhoods without collapsing -0.
    """
    require(-1074 <= minimum_exponent <= maximum_exponent <= 1023 and ulps_each_side == 4,
            "Invalid binary boundary campaign")
    seen, values = set(), []
    for exponent in range(minimum_exponent, maximum_exponent + 1):
        center = int.from_bytes(struct.pack(">d", math.ldexp(1.0, exponent)), "big")
        for offset in range(-ulps_each_side, ulps_each_side + 1):
            magnitude = center + offset
            if not 0 <= magnitude < 0x7ff0000000000000:
                continue
            for sign in (0, 1 << 63):
                bits = magnitude | sign
                if bits not in seen:
                    seen.add(bits)
                    values.append(struct.unpack(">d", bits.to_bytes(8, "big"))[0])
    return values


def source_programs(root=ROOT):
    path = Path(root) / "examples/intent_programs.py"
    specification = importlib.util.spec_from_file_location("biocompiler_conformance_examples", path)
    require(specification is not None and specification.loader is not None, "Cannot load authoring examples")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    require(len(module.EXAMPLES) >= 6, "Authoring example inventory is incomplete")
    return {name: factory() for name, factory in module.EXAMPLES.items()}


def source_variants(document):
    altered = deepcopy(document)
    for index, node in enumerate(altered["nodes"]):
        node["source"] = {"file": "relocated/π-source.py", "line": index + 1001, "function": "relocated"}
    omitted = deepcopy(document)
    for node in omitted["nodes"]:
        node.pop("source", None)
    return {"relocated": altered, "omitted": omitted}


def literal_program(binding, dtype=None):
    return {"schema_version": "biocompiler.intent.v0.1", "name": "literal_binding",
            "nodes": [{"id": "value", "kind": "literal", "inputs": [],
                       "attributes": {"value": deepcopy(binding)},
                       "data_type": deepcopy(dtype if dtype is not None else binding["type"]),
                       "role": None}], "roots": ["value"]}


def typed_programs():
    level = {"kind": "scalar", "name": "Level", "dimensions": {}, "arguments": []}
    scalar = lambda value: {"kind": "scalar", "value": value, "unit": "1", "canonical_value": value, "type": deepcopy(level)}
    interval_type = {"kind": "interval", "name": "Interval[Level]", "dimensions": {}, "arguments": [deepcopy(level)]}
    curve_type = {"kind": "curve", "name": "Curve[Level, Level]", "dimensions": {}, "arguments": [deepcopy(level), deepcopy(level)]}
    result = {
        "scalar-zero": literal_program(scalar(0)), "scalar-negative-zero": literal_program(scalar(-0.0)),
        "interval": literal_program({"kind": "interval", "lower": scalar(0), "upper": scalar(1), "type": interval_type}),
        "curve": literal_program({"kind": "curve", "points": [[scalar(0), scalar(0)], [scalar(1), scalar(2)]],
                                   "interpolation": "linear", "extrapolation": "clamp", "type": curve_type}),
    }
    sparse = deepcopy(result["scalar-zero"])
    sparse["nodes"][0]["data_type"] = {"kind": "scalar", "name": "Level"}
    sparse["nodes"][0]["attributes"]["value"]["type"] = {"kind": "scalar", "name": "Level"}
    result["optional-type-fields-omitted"] = sparse
    zero_dimension = deepcopy(result["scalar-zero"])
    zero_dimension["nodes"][0]["data_type"]["dimensions"] = {"retained_zero": 0}
    result["declared-zero-dimension-retained"] = zero_dimension
    return result


def intent_mutations(programs):
    base = programs["contextual_clearance"].to_dict()
    cases = []

    def add(name, expected_code, modify, original=base):
        candidate = deepcopy(original)
        modify(candidate)
        cases.append((name, expected_code, candidate))

    add("top-extra-field", "unknown_field", lambda d: d.update(extra=True))
    add("node-extra-field", "unknown_field", lambda d: d["nodes"][0].update(extra=True))
    add("node-missing-inputs", "missing_field", lambda d: d["nodes"][0].pop("inputs"))
    add("wrong-schema", "unsupported_schema", lambda d: d.update(schema_version="future.intent"))
    add("blank-name", "invalid_name", lambda d: d.update(name="\u2003\t"))
    add("duplicate-node", "duplicate_node", lambda d: d["nodes"].append(deepcopy(d["nodes"][0])))
    add("duplicate-root", "duplicate_root", lambda d: d["roots"].append(d["roots"][0]))
    add("dangling-root", "dangling_root", lambda d: d["roots"].append("missing"))
    add("dangling-input", "dangling_reference", lambda d: d["nodes"][0]["inputs"].append("missing"))
    add("invalid-role", "invalid_role", lambda d: d["nodes"][0].update(role="missing"))
    add("cyclic-input", "cyclic_graph", lambda d: d["nodes"][0]["inputs"].append(d["nodes"][0]["id"]))
    add("source-line-boolean", "invalid_type", lambda d: d["nodes"][0].update(source={"file": "x", "line": True, "function": "f"}))
    add("source-line-zero", "invalid_source", lambda d: d["nodes"][0].update(source={"file": "x", "line": 0, "function": "f"}))
    parameter = programs["priming_and_phases"].to_dict()
    def duplicate_parameter(d):
        values = [node for node in d["nodes"] if node["kind"] == "parameter"]
        values[1]["attributes"]["name"] = values[0]["attributes"]["name"]
    add("duplicate-parameter", "duplicate_parameter", duplicate_parameter, parameter)
    def contradictory_parameter(d):
        node = next(node for node in d["nodes"] if node["kind"] == "parameter")
        node["attributes"]["bound"] = True
        node["attributes"].pop("default", None)
    add("parameter-bound-without-default", "invalid_parameter", contradictory_parameter, parameter)
    typed = typed_programs()
    add("literal-missing-type", "missing_type", lambda d: d["nodes"][0].update(data_type=None), typed["scalar-zero"])
    add("type-extra-field", "unknown_field", lambda d: d["nodes"][0]["data_type"].update(extra=True), typed["scalar-zero"])
    add("scalar-boolean", "invalid_type", lambda d: d["nodes"][0]["attributes"]["value"].update(value=True), typed["scalar-zero"])
    add("scalar-overflow", "numeric_overflow", lambda d: d["nodes"][0]["attributes"]["value"].update(value=10**400), typed["scalar-zero"])
    add("wrong-canonical-value", "canonical_value_mismatch", lambda d: d["nodes"][0]["attributes"]["value"].update(canonical_value=1), typed["scalar-zero"])
    add("unsupported-unit", "unsupported_unit", lambda d: d["nodes"][0]["attributes"]["value"].update(unit="invented"), typed["scalar-zero"])
    def reverse_interval(d):
        value = d["nodes"][0]["attributes"]["value"]
        value["lower"], value["upper"] = value["upper"], value["lower"]
    add("interval-reversed", "invalid_interval", reverse_interval, typed["interval"])
    def repeat_x(d):
        points = d["nodes"][0]["attributes"]["value"]["points"]
        points[1][0] = deepcopy(points[0][0])
    add("curve-nonincreasing", "invalid_curve", repeat_x, typed["curve"])
    add("curve-interpolation", "invalid_curve", lambda d: d["nodes"][0]["attributes"]["value"].update(interpolation="cubic"), typed["curve"])
    add("curve-extrapolation", "invalid_curve", lambda d: d["nodes"][0]["attributes"]["value"].update(extrapolation="extend"), typed["curve"])
    return cases


def request_bytes(payload, request_id="conformance", operation="canonicalize"):
    prefix = '{"protocol":' + canonical(PROTOCOL) + ',"request_id":' + canonical(request_id) + ',"operation":' + canonical(operation) + ',"payload":'
    return prefix.encode() + (payload.encode() if isinstance(payload, str) else payload) + b"}"


def raw_response(client, request):
    output, exit_code = _exchange(client.executable, request, client.timeout_seconds, None)
    response = decode_json(output)
    require(type(response) is dict and set(response) == {"protocol", "request_id", "operation", "status", "result", "diagnostics", "core"}, "Malformed native response envelope")
    require(response["protocol"] == PROTOCOL and response["core"] == {
        "implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": client.role,
    }, "Native executable identity mismatch")
    require(exit_code == {"ok": 0, "error": 2, "unsupported": 3}.get(response["status"]), "Native exit/status mismatch")
    require(type(response["diagnostics"]) is list, "Malformed diagnostic list")
    for diagnostic in response["diagnostics"]:
        require(type(diagnostic) is dict and set(diagnostic) == {"code", "message", "path"}, "Malformed diagnostic")
        require(type(diagnostic["code"]) is str and bool(diagnostic["code"])
                and type(diagnostic["message"]) is str and bool(diagnostic["message"])
                and (diagnostic["path"] is None or type(diagnostic["path"]) is str), "Invalid diagnostic types")
    return response


class Campaign:
    def __init__(self, receipt):
        self.receipt = receipt

    def passed(self, client, group, name, **details):
        self.receipt["checks"].append({"role": client.role, "group": group, "case": name, "status": "pass", **details})

    def codec(self, client, name, value, expected=None, raw=None, group="python_oracle"):
        expected = canonical(value) if expected is None else expected
        if raw is None:
            result = client.canonicalize(value).result
        else:
            response = raw_response(client, request_bytes(raw))
            require(response["request_id"] == "conformance" and response["operation"] == "canonicalize", name + ": missing request correspondence")
            require(response["status"] == "ok" and not response["diagnostics"], name + ": native codec rejected valid JSON")
            result = response["result"]
        require(type(result) is dict and set(result) == {"canonical_json", "sha256"}, name + ": invalid codec result")
        if result["canonical_json"] != expected:
            actual = result["canonical_json"]
            offset = next((index for index, (a, b) in enumerate(zip(expected, actual)) if a != b), min(len(expected), len(actual)))
            raise AssertionError(f"{client.role}/{name}: canonical bytes differ at {offset}: expected {expected[max(0, offset-40):offset+80]!r}, actual {actual[max(0, offset-40):offset+80]!r}")
        require(result["sha256"] == digest(expected), name + ": native SHA-256 differs from expected canonical bytes")
        self.passed(client, group, name, sha256=digest(expected))

    def rejection(self, client, name, request, code):
        response = raw_response(client, request)
        require(response["status"] == "error" and response["result"] is None, name + ": malformed request was not rejected")
        require([value["code"] for value in response["diagnostics"]] == [code], name + ": wrong rejection signature " + str(response["diagnostics"]))
        require(response["request_id"] is None and response["operation"] is None, name + ": parser rejection invented request authority")
        self.passed(client, "raw_rejection", name, error_code=code)

    def intent(self, client, name, document, expected):
        result = client.validate_intent(document).result
        require(type(result) is dict and set(result) == {"validation_scope", "summary", "unimplemented_obligations"}, name + ": invalid intent result")
        require(result["validation_scope"] == SCOPE and result["unimplemented_obligations"] == OBLIGATIONS, name + ": structural validation promoted its scope")
        require(result["summary"] == expected, name + ": native intent summary/fingerprint differs from original authority")
        self.passed(client, "intent", name, fingerprint=expected["fingerprint"])

    def lowering(self, client, name, request, behavior):
        expected = lowering_expectation(request, behavior)
        result = client.verify_lowering(expected_request=request, behavior=behavior).result
        expected_keys = set(expected) - {"check_properties"} | {"checks"}
        require(type(result) is dict and set(result) == expected_keys, name + ": invalid lowering report")
        for key, value in expected.items():
            if key != "check_properties":
                require(canonical(result[key]) == canonical(value), name + ": incorrect lowering " + key)
        checks = result["checks"]
        require(type(checks) is list and all(type(check) is dict and set(check) == {"property", "passed", "detail"}
                and check["passed"] is True and type(check["detail"]) is str and bool(check["detail"])
                for check in checks), name + ": incomplete or failed preservation checks")
        require([check["property"] for check in checks] == expected["check_properties"], name + ": preservation census differs")
        self.passed(client, "lowering", name, request_fingerprint=expected["request_fingerprint"],
                    request_artifact_fingerprint=expected["request_artifact_fingerprint"],
                    behavior_fingerprint=expected["behavior_fingerprint"],
                    behavior_artifact_fingerprint=expected["behavior_artifact_fingerprint"],
                    preservation_checks=len(checks))

    def lowering_rejection(self, client, name, request, behavior, code):
        try:
            client.verify_lowering(expected_request=request, behavior=behavior)
        except CoreRejected as error:
            require(error.response.status == "error" and error.response.result is None,
                    name + ": mismatch confused with unsupported or success")
            require([value.code for value in error.response.diagnostics] == [code],
                    name + ": wrong preservation rejection signature")
            self.passed(client, "lowering_rejection", name, error_code=code)
        else:
            raise AssertionError(name + ": changed lowering accepted")


def run_campaign(clients, corpus, receipt, programs):
    campaign = Campaign(receipt)
    settings = corpus["python_oracle"]
    patterns = float_patterns(settings["seed"], settings["finite_float_count"])
    receipt["float_patterns"] = {**settings, "bits_sha256": digest(b"".join(bits.to_bytes(8, "big") for bits, _ in patterns))}
    boundaries = boundary_floats()
    binary_boundaries = binary_boundary_floats(**settings["binary_boundaries"])
    receipt["binary_boundaries"] = {
        **settings["binary_boundaries"], "value_count": len(binary_boundaries),
        "bits_sha256": digest(b"".join(struct.pack(">d", value) for value in binary_boundaries)),
    }
    mutations = intent_mutations(programs)
    lowering = lowering_cases()
    lowering_changes = lowering_mutations(lowering)
    for client in clients:
        capabilities = client.capabilities().result
        require(type(capabilities) is dict, "Missing capabilities")
        operations = ["canonicalize", "capabilities", "replay-architecture", "validate-intent", "verify-architecture", "verify-lowering"]
        operations += list(OPERATIONAL_PROFILE["operations"])
        operations += list(IMPLEMENTATION_PROFILE["operations"])
        operations += ["assess-policy", "replay-policy-assessment"] + list(REALIZATION_OPERATIONS) + list(WORKFLOW_OPERATIONS)
        workflow = workflow_profile()
        scopes = [SCOPE, LOWERING_SCOPE, ARCHITECTURE_SCOPE, POLICY_SCOPE, OPERATIONAL_SCOPE, IMPLEMENTATION_SCOPE] + list(REALIZATION_SCOPES) + [workflow["validation_scope"]]
        profiles = {"policy_implementation": IMPLEMENTATION_PROFILE, "policy_operational": OPERATIONAL_PROFILE, "architecture": ARCHITECTURE_PROFILE, "policy_frontend": POLICY_PROFILE, **REALIZATION_PROFILES,
                    "artifact_transport": ARTIFACT_PROFILE, "verification_workflow": workflow}
        claim = "Structural intent validation, frozen source-to-Behavior correspondence, supplied architecture contracts and independently executed finite-history model checks. No search completeness, empirical function or human-use admission."
        if client.role == "core":
            operations += ["compile-architecture", "export-architecture", "compile-policy", "compile-policy-implementation"]
            scopes.append(PRODUCER_SCOPE)
            profiles["architecture_producer"] = PRODUCER_PROFILE
            profiles["policy_operational_producer"] = OPERATIONAL_PRODUCER_PROFILE
            profiles["policy_implementation_producer"] = IMPLEMENTATION_PRODUCER_PROFILE
            claim = "Supplied-contract architecture production, independent checking, exact RNA/manifest export and separately scoped finite-history model checks. No search completeness, empirical function or human-use admission is established."
        require(sorted(capabilities["operations"]) == sorted(operations), "Missing or untested advertised operation")
        require(capabilities["canonicalization"] == "python-json-v1" and capabilities["intent_schemas"] == ["biocompiler.intent.v0.1"]
                and capabilities["validation_scopes"] == scopes and capabilities["limits"] == LIMITS
                and capabilities["schema_version"] == "biocompiler.core_capabilities.v1"
                and capabilities["profiles"] == profiles, "Capability contract differs")
        require(capabilities["claim_scope"] == claim, "Capabilities lost limited claim scope")
        campaign.passed(client, "capabilities", "complete-advertised-contract")
        for vector in corpus["literal_vectors"]:
            campaign.codec(client, vector["id"], None, vector["canonical_json"], vector["input_json"], "independent_literal")
        for start in range(0, len(patterns), settings["batch_size"]):
            values = [value for _, value in patterns[start:start + settings["batch_size"]]]
            campaign.codec(client, f"finite-binary64-{start}", values)
        for start in range(0, len(boundaries), settings["batch_size"]):
            campaign.codec(client, f"decimal-threshold-adjacent-{start}", boundaries[start:start + settings["batch_size"]])
        for start in range(0, len(binary_boundaries), settings["batch_size"]):
            campaign.codec(client, f"binary-power-adjacent-{start}", binary_boundaries[start:start + settings["batch_size"]])
        for name, token in (("positive-int-4300", "9" * 4300), ("negative-int-4300", "-" + "9" * 4299)):
            campaign.codec(client, name, None, token, token, "integer_boundary")
        for name, token in (("positive-int-4301", "9" * 4301), ("negative-int-4301", "-" + "9" * 4300)):
            campaign.rejection(client, name, request_bytes(token), "number_too_large")
        # This response's canonical_json string exceeds the request-side 4 MiB
        # string bound. Response validation must use its own total byte budget.
        campaign.codec(client, "maximum-request-string", "a" * LIMITS["max_string_bytes"], group="string_boundary")
        campaign.rejection(client, "oversized-request-string", request_bytes('"' + "a" * (LIMITS["max_string_bytes"] + 1) + '"'), "string_too_large")
        for vector in corpus["raw_rejections"]:
            raw = vector.get("payload_json")
            raw = bytes.fromhex(vector["payload_hex"]) if raw is None else raw
            campaign.rejection(client, vector["id"], request_bytes(raw), vector["error_code"])
        valid = request_bytes("null")
        campaign.rejection(client, "request-bom", b"\xef\xbb\xbf" + valid, "invalid_json")
        campaign.rejection(client, "trailing-document", valid + b"{}", "invalid_json")
        campaign.rejection(client, "duplicate-envelope-key", valid[:-1] + b',"payload":0}', "duplicate_key")
        # Envelope is depth zero and payload is depth one.
        valid_depth = LIMITS["max_depth"] - 1
        nested = "[" * valid_depth + "0" + "]" * valid_depth
        campaign.codec(client, "maximum-envelope-depth", None, nested, nested, "nesting_boundary")
        campaign.rejection(client, "excess-envelope-depth", request_bytes("[" + nested + "]"), "nesting_limit")
        campaign.rejection(client, "value-count-over-budget", request_bytes("[" + ",".join("0" for _ in range(LIMITS["max_json_nodes"])) + "]"), "node_limit")
        for name, program in programs.items():
            original = program.to_dict()
            campaign.intent(client, name, original, program.summary())
            for variant, document in source_variants(original).items():
                campaign.intent(client, name + "/source-" + variant, document, program.summary())
        for name, document in typed_programs().items():
            campaign.intent(client, name, document, IntentProgram.from_dict(document).summary())
        unknown = programs["contextual_clearance"].to_dict()
        unknown["nodes"].append({"id": "future-operation", "kind": "unimplemented.future.operation", "inputs": [], "attributes": {}, "data_type": None, "role": None})
        campaign.intent(client, "unknown-kind-is-structural-only", unknown, IntentProgram.from_dict(unknown).summary())
        for name, code, document in mutations:
            try:
                client.validate_intent(document)
            except CoreRejected as error:
                require([value.code for value in error.response.diagnostics] == [code], name + ": incorrect intent rejection signature")
                campaign.passed(client, "intent_rejection", name, error_code=code)
            else:
                raise AssertionError(name + ": invalid intent was accepted")
        for name, request, behavior in lowering:
            campaign.lowering(client, name, request, behavior)
        for name, code, request, behavior in lowering_changes:
            campaign.lowering_rejection(client, name, request, behavior, code)
        unsupported_source = deepcopy(lowering[0][1])
        unsupported_source["intent"]["nodes"].append({"id": "future-operation", "kind": "future.operation",
                                                     "inputs": [], "attributes": {}, "data_type": None,
                                                     "role": None})
        try:
            client.verify_lowering(expected_request=unsupported_source, behavior=lowering[0][2])
        except CoreUnsupported as error:
            require([value.code for value in error.response.diagnostics] == ["unsupported_lowering_operation"],
                    "Unsupported source lost its explicit capability diagnostic")
            campaign.passed(client, "lowering_unsupported", "unknown-source-operation",
                            error_code="unsupported_lowering_operation")
        else:
            raise AssertionError("Unsupported source was accepted or silently ignored")
        payload = {"expected_request": lowering[0][1], "behavior": lowering[0][2]}
        for name, altered, code in (("extra-authority", {**payload, "accepted": True}, "unknown_field"),
                                    ("missing-independent-authority", {"behavior": lowering[0][2]}, "missing_field")):
            try:
                client.call("verify-lowering", altered)
            except CoreRejected as error:
                require(error.response.status == "error" and [value.code for value in error.response.diagnostics] == [code],
                        name + ": wrong lowering payload rejection")
                campaign.passed(client, "lowering_rejection", name, error_code=code)
            else:
                raise AssertionError(name + ": malformed lowering payload accepted")
        try:
            client.call("unimplemented-test-operation", {})
        except CoreUnsupported as error:
            require([value.code for value in error.response.diagnostics] == ["unsupported_operation"], "Wrong unsupported signature")
            campaign.passed(client, "unsupported", "no-semantic-fallback")
        else:
            raise AssertionError("Unknown operation was accepted")
    require({check["role"] for check in receipt["checks"]} == {"core", "verify"}, "Both executables must be exercised")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--verify", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.monotonic()
    receipt = {"schema_version": "biocompiler.core_conformance.v0.1", "status": "running", "checks": [],
               "platform": platform.platform(), "python_version": platform.python_version(),
               "package_version": biocompiler.__version__, "package_path": str(Path(biocompiler.__file__).resolve()),
               "corpus_sha256": digest(CORPUS.read_bytes()), "executables": {}}
    try:
        revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        require(os.environ.get("GITHUB_SHA", revision) == revision, "Workflow and tested revision differ")
        receipt.update(revision=revision, source_revision=os.environ.get("GITHUB_HEAD_SHA", revision), run_id=os.environ.get("GITHUB_RUN_ID", "local"))
        require(not Path(biocompiler.__file__).resolve().is_relative_to(ROOT), "Conformance requires the installed package outside the checkout")
        clients = []
        for role, binary in (("core", args.core), ("verify", args.verify)):
            require(binary.is_absolute() and binary.is_file() and os.access(binary, os.X_OK), f"Missing absolute executable for {role}: {binary}")
            pin = digest(binary.read_bytes())
            receipt["executables"][role] = {"path": str(binary), "sha256": pin}
            clients.append(CoreClient(binary, role=role, timeout_seconds=60, expected_sha256=pin))
        run_campaign(clients, load_corpus(), receipt, source_programs())
        receipt["status"] = "success"
        return_code = 0
    except Exception as error:
        receipt["status"] = "failure"
        receipt["error"] = type(error).__name__ + ": " + str(error)
        print(receipt["error"], file=sys.stderr)
        return_code = 1
    receipt["duration_seconds"] = round(time.monotonic() - started, 6)
    receipt["completed_checks"] = len(receipt["checks"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Core conformance: {receipt['status']}; {receipt['completed_checks']} completed checks")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())

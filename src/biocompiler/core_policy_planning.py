"""Explicit native target planning transport; diagnostic plans grant no acceptance.

Python checks identities, source occurrence accounting and closed claim boundaries.
Only the native producer interprets source support or derives the diagnostic plan.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, cast

from . import core_policy as source
from . import core_policy_operational as operational
from . import core_policy_implementation as implementation
from .core_client import CoreClient, CoreProtocolError, CoreResponse, JsonValue, _object, decode_json, encode_json

REQUEST_SCHEMA = "biocompiler.policy_target_plan_request.v0.1"
REPORT_SCHEMA = "biocompiler.policy_target_plan.v0.1"
RESULT_SCHEMA = "biocompiler.core.policy_target_plan.v1"
IMPLEMENTATION = "biocompiler.ocaml.policy_target_planning.v0.1"
VALIDATION_SCOPE = "policy-target-planning-v0.1"
RESOURCE_PROFILE = "biocompiler.policy_target_planning_resources.v0.1"
MAX_INPUT_BYTES = 8_388_608
MAX_INPUT_NODES = 250_000
MAX_RESULT_BYTES = 2_097_152
MAX_RESULT_NODES = 100_000
STAGES = ("source_contracts", "operational_admission", "realization_inputs", "model_lowering",
          "source_binding", "component_arrangement", "provider_dependencies")
CLAIMS: dict[str, JsonValue] = {
    "planning": "diagnostic_only", "diagnostic_completeness": "first_blocker", "execution": "not_performed",
    "preservation": "unassessed", "requirements": "unassessed", "resource_feasibility": "unassessed",
    "material": "unassessed", "empirical": "unassessed", "artifact": "withheld", "export": "withheld",
}
CATALOG_FINGERPRINT = "fe414a3f60668dd1466f4a6b1999067f196936aa85df4c2b6747f7190e20d765"
# Reviewed descriptor pins are embedded so installed clients need no source-tree
# protocol file. They bind vocabulary, bounds and caveats, never source support.
TARGET_FINGERPRINTS = {
    'coupled_implementation': '4f7936948cc72e42c67b9c4e4b6e95bd5e8131cf182d5157b0314f6bc47dfed1',
    'coupled_quantitative_material': '61e2006ea03309aba3efa7ad7880655f6de4ff33c2cdb2d36bf11c526fed7024',

    'transfer_network_material': '524d289fde18fc53d2d6f00f8a26a92e168fce12c5535fc551790629fe922d9c',
    'transfer_pair_material': '38f10bf725d465a9120d2531039032134d061c2bcc7ea492e6cab28c6878e5ae',
    'multi_site_implementation': '5c995cfb805919e18eda1fb1a0a07ca71f581e4aad04e1f7c7908e42be420003',
    'step_quantitative_material': '4247c18651d6496f211e625994217453e8a1cb70d9eac8f04cba43b3aabb4349',
    'implementation': '003bba7ea8e3f8f9cf2456a952480f1be9abf743a8fb65529d0423c1f8065d86',
    'finite_machine_implementation': '53e6a6a044cef9a3ebc001b74d415ca65b958a672121d690d86aa37d7c86a2fa',
    'network_implementation': '96cf22a3ba8d2f407531fcd83be5971d7a9478894808d1a50210cd04f12f5559',
    'component_material': 'cb860eaa94f263b71d1ba0d0f9c292b75771952bc679d00850b02f50943a641e',
    'instance_material': '730ddcdba6782d28938be1f2a07937a511e62563e3b2d5cc30c7814174ca615d',
    'prerequisite_material': 'b7a4084a51b9fdc4c8ca8c2374a67ec1840291325af7a37ee03fd4753c5a49e1',
    'two_observation_material': '49112a3201caa0f0781d7e27c772ad7d049ebdc680304c1c36d926bf9d6aa23b',
    'multi_member_material': '5ba9c9f01caaf49b1aa00a67eb60e18f12b8d6cd31a1aabe6316e6d6888fd0ad',
    'grounded_helper_material': '9b3edb2c58417102e6fa64ff4377fba6cd66d7f7d35d6230673f06daa66484c5',
    'finite_machine_material': '7e72844525389393775c384f6355dc1fa1b6041dccb0ed99676eed438bbde569',
    'quantitative_material': 'f46a1069f20f5fc6c5128eae814810e5907271765b87f7c0fc3b7e40a2891699',
    'network_material': '4f86d03bbee8353efa5e838f9986246c67852ee5b8f433f8abf52dab3a4492ca',
}
TargetId = Literal['implementation', 'finite_machine_implementation', 'network_implementation', 'component_material', 'instance_material', 'prerequisite_material', 'two_observation_material', 'multi_member_material', 'grounded_helper_material', 'finite_machine_material', 'quantitative_material', 'network_material', 'multi_site_implementation', 'step_quantitative_material', 'transfer_pair_material', 'transfer_network_material', 'coupled_implementation', 'coupled_quantitative_material']
PROFILE: dict[str, JsonValue] = {
    "operations": ["plan-policy-target", "replay-policy-target-plan"],
    "request_schema": REQUEST_SCHEMA, "report_schema": REPORT_SCHEMA,
    "implementation": IMPLEMENTATION, "validation_scope": VALIDATION_SCOPE,
    "resource_profile": RESOURCE_PROFILE, "catalog_fingerprint": CATALOG_FINGERPRINT,
    "max_result_bytes": MAX_RESULT_BYTES, "max_result_nodes": MAX_RESULT_NODES,
}

PlanStatus = Literal["planned", "invalid_source", "unsupported_target", "missing_inputs", "incompatible_inputs"]
_REQUEST_FIELDS = {"schema_version", "target", "document", "definitions", "realization_request", "material_request", "limits"}
_REPORT_FIELDS = {"schema_version", "status", "target", "catalog_fingerprint", "request_fingerprint", "document_fingerprint",
    "realization_request_fingerprint", "material_request_fingerprint", "source_assessment", "declarations", "requirements",
    "obligations", "missing_inputs", "stages", "selected_models", "selected_components", "provider_dependencies", "diagnostics",
    "claims", "usage"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CoreProtocolError(message)


def _record(value: JsonValue, label: str) -> dict[str, JsonValue]:
    if type(value) is not dict:
        raise CoreProtocolError(label + " must be a record")
    return value


def _rows(value: JsonValue, label: str) -> list[dict[str, JsonValue]]:
    if type(value) is not list or any(type(row) is not dict for row in value):
        raise CoreProtocolError(label + " must be a list of records")
    return cast(list[dict[str, JsonValue]], value)


def _integer(value: JsonValue, minimum: int, maximum: int, label: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise CoreProtocolError(label + " exceeds its closed integer bound")
    return value


def _strings(value: JsonValue, label: str) -> list[str]:
    if type(value) is not list or any(type(item) is not str or not item for item in value):
        raise CoreProtocolError(label + " must be a list of nonempty strings")
    result = cast(list[str], value)
    _require(len(set(result)) == len(result), label + " cannot repeat identities")
    return result


def _measure(value: JsonValue, *, max_bytes: int, max_nodes: int) -> None:
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        _require(depth <= 128 and count + len(pending) <= max_nodes, "Planning data exceeds its depth or node bound")
        if type(item) is dict:
            count += len(item)
            pending.extend((entry, depth + 1) for entry in item.values())
        elif type(item) is list:
            pending.extend((entry, depth + 1) for entry in item)
    _require(count <= max_nodes, "Planning data exceeds its node bound")
    encode_json(value, limit=max_bytes)


def _original(value: JsonValue) -> dict[str, JsonValue]:
    _measure(value, max_bytes=MAX_INPUT_BYTES, max_nodes=MAX_INPUT_NODES)
    request = _object(value, _REQUEST_FIELDS, "Target planning request")
    _require(request["schema_version"] == REQUEST_SCHEMA, "Planning request changed its closed schema")
    source._text(request["target"], "Requested target")
    limits = _object(request["limits"], {"max_work", "max_report_bytes", "max_report_nodes"}, "Planning limits")
    _integer(limits["max_work"], 1, 100_000_000, "Planning work limit")
    _integer(limits["max_report_bytes"], 1, MAX_RESULT_BYTES, "Planning publication byte limit")
    _integer(limits["max_report_nodes"], 1, MAX_RESULT_NODES, "Planning publication node limit")
    for field in ("definitions", "realization_request", "material_request"):
        _require(request[field] is None or type(request[field]) is dict,
                 "Optional planning authority must be an object or explicit null")
    # Original source and supplied authority intentionally remain raw: invalid
    # source or incompatible authority must reach native diagnostic planning.
    return request


def _catalog_target(report: dict[str, JsonValue], request: dict[str, JsonValue]) -> None:
    target = _record(report["target"], "Installed target descriptor")
    requested = source._text(request["target"], "Requested target")
    _require(report["catalog_fingerprint"] == CATALOG_FINGERPRINT
             and target.get("target") == requested and requested in TARGET_FINGERPRINTS,
             "Plan changed its installed target or catalog identity")
    _require(operational._fingerprint(target) == TARGET_FINGERPRINTS[requested],
             "Plan changed the complete installed target descriptor")


def _source_rows(document: JsonValue) -> list[tuple[str, dict[str, JsonValue]]] | None:
    """Extract a representation census only; perform no source admission."""
    if type(document) is not dict:
        return None
    value = document
    path = "/document"
    if value.get("$type") == "CompilationSubmission":
        nested = value.get("request")
        if type(nested) is not dict:
            return None
        value, path = nested, path + "/request"
    if value.get("$type") == "BuildRequest":
        nested = value.get("program")
        if type(nested) is not dict:
            return None
        value, path = nested, path + "/program"
    if value.get("$type") != "PolicyProgram":
        return None
    rows = value.get("declarations")
    if type(rows) is not list or any(type(row) is not dict or type(row.get("id")) is not str
                                    or type(row.get("$type")) is not str for row in rows):
        return None
    return [(f"{path}/declarations/{index}", row) for index, row in enumerate(cast(list[dict[str, JsonValue]], rows))]


def _census(report: dict[str, JsonValue], document: JsonValue) -> None:
    declarations = _rows(report["declarations"], "Planning declarations")
    requirements = _rows(report["requirements"], "Planning requirements")
    expected = _source_rows(document)
    if expected is None or report["source_assessment"] is None:
        _require(not declarations and not requirements, "Undecoded source cannot carry a claimed complete census")
        return
    actual: JsonValue = [{"id": row["id"], "kind": row["$type"], "path": path} for path, row in expected]
    _require(operational._same(cast(JsonValue, declarations), actual), "Plan changed its complete ordered declaration census")
    wanted: JsonValue = [{"id": row["id"], "path": path, "source": row, "status": "unassessed"}
                         for path, row in expected if row["$type"] == "Requirement"]
    _require(operational._same(cast(JsonValue, requirements), wanted), "Plan changed its original ordered unassessed requirements")


def _models(report: dict[str, JsonValue], request: dict[str, JsonValue]) -> None:
    models = _rows(report["selected_models"], "Planning selected models")
    original = request["realization_request"]
    if not models:
        return
    _require(type(original) is dict, "Selected models require original realization authority")
    library = _record(cast(dict[str, JsonValue], original).get("implementation_library"), "Original model library")
    supplied = _rows(library.get("models"), "Original models")
    seen: set[str] = set()
    for value in models:
        row = _object(value, {"node", "model", "configuration_digest", "primitive"}, "Selected model")
        node = source._text(row["node"], "Selected node")
        _require(node not in seen, "Plan repeats a selected node")
        seen.add(node)
        matches = [model for model in supplied if operational._same(model.get("identity"), row["model"])]
        _require(len(matches) == 1, "Plan selected an absent or ambiguous original model")
        model = matches[0]
        body = _record(model.get("body"), "Original model body")
        pin = _record(row["model"], "Original model identity")
        operational._pin(pin.get("content_fingerprint"), body, "Complete original model body")
        _require(row["configuration_digest"] == model.get("configuration_digest") and row["primitive"] == body.get("primitive"),
                 "Plan changed the selected model configuration or primitive")
        source._hash(row["configuration_digest"])


def _provider_graph(raw: JsonValue, request: dict[str, JsonValue]) -> None:
    """Bind dependency records to original identities without proving closure."""
    graph = _object(raw, {"schema_version", "pending_dependencies", "roots", "nodes", "edges", "issues"}, "Provider diagnostic graph")
    original = _record(request["realization_request"], "Original realization request")
    material = _record(request["material_request"], "Original material request")
    target = request["target"]
    version = "v0.3" if target == "grounded_helper_material" else "v0.2" if target == "multi_member_material" else "v0.1"
    _require(graph["schema_version"] == "biocompiler.policy_provider_dependency_graph." + version,
             "Provider graph changed its selected target family")
    pending = implementation._pending_dependencies(original)
    _require(operational._same(graph["pending_dependencies"], pending), "Provider graph changed original catalog dependencies")
    document = _record(original.get("document"), "Original provider document")
    program = _record(document.get("program"), "Original provider program")
    definitions = _rows(_record(program.get("semantics"), "Original semantic bundle").get("definitions"), "Original definitions")
    context = _record(material.get("context"), "Original provider context")
    providers = _rows(context.get("providers"), "Original provider bodies")

    def reference(value: JsonValue) -> None:
        row = _object(value, {"$type", "id", "version", "digest"}, "Provider source reference")
        matches = [definition for definition in definitions if definition.get("id") == row["id"]]
        _require(len(matches) == 1, "Provider reference lost its unique original definition")
        definition = matches[0]
        _require(row["$type"] == "DefinitionRef" and row["version"] == definition.get("version"),
                 "Provider source reference changed its type or version")
        operational._pin(row["digest"], source._semantic(definition), "Complete original provider definition")

    expected_roots: list[JsonValue] = []

    def append_root(path: str, value: JsonValue) -> None:
        reference(value)
        expected_roots.append({"origin": {"kind": "source", "path": path}, "definition": value})

    def append_rows(path: str, value: JsonValue) -> None:
        for index, row in enumerate(_rows(value, "Original source roots")):
            append_root(path + "/" + str(index), row)

    deployment = _record(document.get("deployment"), "Original deployment")
    for index, binding in enumerate(_rows(deployment.get("bindings"), "Original role bindings")):
        chassis = _record(binding.get("chassis"), "Original chassis")
        path = "/deployment/bindings/" + str(index) + "/chassis"
        append_root(path + "/operational_model", chassis.get("operational_model"))
        for field in ("capabilities", "interfaces", "environment"):
            append_rows(path + "/" + field, chassis.get(field))
    append_rows("/deployment/environment", deployment.get("environment"))
    for index, declaration in enumerate(_rows(program.get("declarations"), "Original declarations")):
        if declaration.get("$type") == "Role":
            append_rows("/program/declarations/" + str(index) + "/requires", declaration.get("requires"))
    delivery = _record(deployment.get("delivery"), "Original delivery")
    for field in ("arrival", "expression", "activation", "contract"):
        append_root("/deployment/delivery/" + field, delivery.get(field))
    for dependency in _rows(pending, "Original catalog dependencies"):
        expected_roots.append({"origin": {"kind": "catalog_dependency", **{field: dependency[field]
            for field in ("entry_id", "entry_digest", "dependency_index")}}, "definition": dependency["definition"]})
    _require(operational._same(graph["roots"], expected_roots), "Provider graph changed its complete original root census")
    roots = _rows(graph["roots"], "Provider roots")
    for raw_root in roots:
        root = _object(raw_root, {"origin", "definition"}, "Provider root")
        reference(root["definition"])
        origin = _record(root["origin"], "Provider origin")
        if origin.get("kind") == "catalog_dependency":
            _object(origin, {"kind", "entry_id", "entry_digest", "dependency_index"}, "Catalog root occurrence")
            expected = {"entry_id": origin["entry_id"], "entry_digest": origin["entry_digest"],
                        "dependency_index": origin["dependency_index"], "definition": root["definition"]}
            _require(any(operational._same(row, expected) for row in pending), "Provider root changed its original catalog occurrence")
        else:
            _object(origin, {"kind", "path"}, "Provider source occurrence")
            _require(origin["kind"] == "source", "Unknown provider root origin")
            path = source._text(origin["path"], "Provider source path")
            value: JsonValue = document
            _require(path.startswith("/"), "Provider source root requires an absolute document pointer")
            for part in path[1:].split("/"):
                if type(value) is dict:
                    _require(part in value, "Provider source path is absent from the original document")
                    value = value[part]
                elif type(value) is list:
                    _require(part.isdecimal() and int(part) < len(value), "Provider source path index is outside the original document")
                    value = value[int(part)]
                else:
                    raise CoreProtocolError("Provider source path traverses a non-container")
            _require(operational._same(value, root["definition"]), "Provider root changed its exact original source reference")
    nodes = _rows(graph["nodes"], "Provider graph nodes")
    node_keys: set[bytes] = set()
    for raw_node in nodes:
        node = _object(raw_node, {"definition", "provider"}, "Provider graph node")
        reference(node["definition"])
        key = encode_json(node["definition"])
        _require(key not in node_keys, "Provider graph repeats a source identity")
        node_keys.add(key)
        matches = [provider for provider in providers if operational._same(
            _record(provider.get("body"), "Original provider body").get("definition"), node["definition"])]
        _require(len(matches) <= 1, "Provider graph has ambiguous original bodies")
        if not matches:
            _require(node["provider"] is None, "Absent provider acquired a supplied body")
        else:
            provider = matches[0]
            _require(operational._same(node["provider"], provider.get("identity")), "Provider graph changed its original body pin")
            operational._pin(_record(node["provider"], "Provider identity").get("content_fingerprint"),
                             provider.get("body"), "Complete supplied provider body")
    _require(all(encode_json(root["definition"]) in node_keys for root in roots), "Provider graph omitted a root identity")
    expected_edges: list[JsonValue] = []
    for node in nodes:
        matches = [_record(provider.get("body"), "Original provider body") for provider in providers
                   if operational._same(_record(provider.get("body"), "Original provider body").get("definition"), node["definition"])]
        if not matches:
            continue
        body = matches[0]
        outgoing: list[tuple[str, list[JsonValue]]] = []
        if body.get("kind") == "interface":
            outgoing = [("interface_environment", [body.get("environment")])]
        elif body.get("kind") == "transport" and version in ("v0.2", "v0.3"):
            outgoing = [("transport_environment", [body.get("environment")])]
        elif body.get("kind") == "helper" and version == "v0.3":
            outgoing = [("helper_environment", [body.get("environment")]), ("helper_delivery", [body.get("delivery")])]
        elif body.get("kind") == "chassis":
            chassis = _record(body.get("chassis"), "Original chassis provider")
            for field, relation in (("capabilities", "chassis_capability"), ("interfaces", "chassis_interface"),
                                    ("environment", "chassis_environment")):
                outgoing.append((relation, list(_rows(chassis.get(field), "Original provider references"))))
        for relation, targets in outgoing:
            for index, endpoint in enumerate(targets):
                expected_edges.append({"source": node["definition"], "relation": relation, "index": index, "target": endpoint})
    edges = _rows(graph["edges"], "Provider edges")
    _require(sorted(encode_json(row) for row in edges) == sorted(encode_json(row) for row in expected_edges),
             "Provider graph changed an original dependency occurrence")
    for raw_edge in edges:
        edge = _object(raw_edge, {"source", "relation", "index", "target"}, "Provider edge")
        reference(edge["source"])
        reference(edge["target"])
        _require(encode_json(edge["source"]) in node_keys and encode_json(edge["target"]) in node_keys,
                 "Provider edge lost an original graph endpoint")
        _integer(edge["index"], 0, 1024, "Provider edge occurrence")
        _require(edge["relation"] in ("interface_environment", "chassis_capability", "chassis_interface", "chassis_environment",
                 "transport_environment", "helper_environment", "helper_delivery"), "Unknown provider diagnostic relation")
    codes = {"missing": "prerequisite_provider_missing", "cycle": "prerequisite_cycle", "extra": "prerequisite_provider_extra",
             "unsupported": "prerequisite_definition_unsupported"}
    for raw_issue in _rows(graph["issues"], "Provider issues"):
        issue = _object(raw_issue, {"kind", "code", "references"}, "Provider diagnostic issue")
        kind = source._text(issue["kind"], "Provider issue kind")
        _require(codes.get(kind) == issue["code"], "Unknown provider diagnostic issue")
        refs = _rows(issue["references"], "Provider issue source references")
        _require(bool(refs), "Provider issue omitted its original references")
        for value in refs:
            reference(value)


@dataclass(frozen=True, slots=True)
class PolicyTargetPlan:
    """Immutable diagnostic response snapshot, never a checked target capability."""
    request_id: str
    operation: str
    status: PlanStatus
    request_fingerprint: str
    report_fingerprint: str
    _result_json: bytes

    @property
    def result(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self._result_json))

    @property
    def report(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.result["report"])


def _result(response: CoreResponse, request: dict[str, JsonValue]) -> PolicyTargetPlan:
    _require(response.executable == "core", "Target planning requires the producer executable")
    limits = _record(request["limits"], "Planning limits")
    _measure(response.result, max_bytes=cast(int, limits["max_report_bytes"]), max_nodes=cast(int, limits["max_report_nodes"]))
    wrapper = _object(response.result, {"schema_version", "implementation", "validation_scope", "resource_profile",
        "request_fingerprint", "report_fingerprint", "report"}, "Target planning result")
    _require(wrapper["schema_version"] == RESULT_SCHEMA and wrapper["implementation"] == IMPLEMENTATION
             and wrapper["validation_scope"] == VALIDATION_SCOPE and wrapper["resource_profile"] == RESOURCE_PROFILE,
             "Target planning result changed its negotiated profile")
    request_pin = operational._pin(wrapper["request_fingerprint"], request, "Complete planning request")
    report = _object(wrapper["report"], _REPORT_FIELDS, "Target plan")
    report_pin = operational._pin(wrapper["report_fingerprint"], report, "Complete target plan")
    _require(report["schema_version"] == REPORT_SCHEMA and report["request_fingerprint"] == request_pin,
             "Target plan changed its report schema or original request")
    operational._pin(report["document_fingerprint"], request["document"], "Original source document")
    for field in ("realization_request", "material_request"):
        if request[field] is None:
            _require(report[field + "_fingerprint"] is None, "Plan invented absent original authority")
        else:
            operational._pin(report[field + "_fingerprint"], request[field], "Original " + field)
    status = report["status"]
    _require(status in ("planned", "invalid_source", "unsupported_target", "missing_inputs", "incompatible_inputs"),
             "Plan changed its diagnostic-only status vocabulary")
    _require(operational._same(report["claims"], CLAIMS), "Plan upgraded an execution, requirement, material or export claim")
    _catalog_target(report, request)
    if report["source_assessment"] is not None:
        operational._source_assessment(response, report["source_assessment"], request["document"])
    _census(report, request["document"])
    stage_rows = _rows(report["stages"], "Planning stages")
    _require(len(stage_rows) == len(STAGES), "Plan omitted or added a diagnostic stage")
    states: dict[str, str] = {}
    for stage, raw in zip(STAGES, stage_rows):
        row = _object(raw, {"stage", "status"}, "Planning stage")
        _require(row["stage"] == stage and row["status"] in ("not_run", "completed", "blocked", "not_applicable"),
                 "Plan changed its ordered stage census or status")
        states[stage] = cast(str, row["status"])
    target_kind = _record(report["target"], "Target descriptor")["kind"]
    for stage, stage_status in states.items():
        _require(stage_status != "not_applicable" or (target_kind == "implementation"
                 and stage in ("component_arrangement", "provider_dependencies")) or
                 (stage_status == "not_applicable" and stage == "provider_dependencies"
                  and request["target"] in ("component_material", "instance_material")),
                 "Plan skipped an applicable diagnostic stage")
    _require((states["model_lowering"] == "completed") == (states["source_binding"] == "completed"),
             "Selected lowering must retain completed independent source binding")
    _require((report["provider_dependencies"] is not None) == (states["provider_dependencies"] == "completed"),
             "Completed provider analysis must retain its diagnostic graph")
    blocked = [stage for stage, value in states.items() if value == "blocked"]
    diagnostic_stage = blocked[0] if blocked else "provider_dependencies"
    if blocked:
        position = STAGES.index(blocked[0])
        _require(all(states[stage] == "completed" for stage in STAGES[:position])
                 and all(states[stage] == "not_run" for stage in STAGES[position + 1:]),
                 "Plan continued or skipped stages across its first blocker")
    elif status != "planned":
        _require(all(value == "completed" for value in states.values()),
                 "A completed provider finding requires the complete diagnostic stage prefix")
    if status == "planned":
        _require(all(value in ("completed", "not_applicable") for value in states.values()),
                 "Planned status requires every applicable diagnostic stage to complete")
    else:
        provider_findings = report["provider_dependencies"]
        completed_finding = (states["provider_dependencies"] == "completed" and type(provider_findings) is dict
                             and bool(provider_findings.get("issues")))
        _require(list(states.values()).count("blocked") == (0 if completed_finding else 1),
                 "Plan must retain its first blocked stage or completed provider analysis finding")
    source_assessment = report["source_assessment"]
    if source_assessment is None:
        _require(status == "invalid_source" and states["source_contracts"] == "blocked",
                 "Unassessed source cannot bypass the source-contract stage")
    else:
        source_status = _record(source_assessment, "Source assessment")["status"]
        _require((source_status == "invalid") == (status == "invalid_source")
                 and states["source_contracts"] == ("blocked" if source_status == "invalid" else "completed"),
                 "Plan contradicts its original native source assessment")
    missing = _strings(report["missing_inputs"], "Missing original inputs")
    _require((status == "missing_inputs") == bool(missing), "Plan has inconsistent missing-input status")
    diagnostics = _rows(report["diagnostics"], "Planning diagnostics")
    _require(len(diagnostics) == (0 if status == "planned" else 1), "Plan has inconsistent first-blocker diagnostic census")
    for raw in diagnostics:
        row = _object(raw, {"category", "stage", "code", "message", "path", "declaration_id"}, "Planning diagnostic")
        _require(row["category"] == status and row["stage"] == diagnostic_stage,
                 "Diagnostic category or stage contradicts the first plan finding")
        source._text(row["code"], "Diagnostic code")
        source._text(row["message"], "Diagnostic message")
        if row["path"] is not None:
            path = source._text(row["path"], "Diagnostic path")
            _require(path.startswith("/"), "Diagnostic path must be an absolute source pointer")
        if row["declaration_id"] is not None:
            identity = source._text(row["declaration_id"], "Diagnostic declaration")
            rows = _source_rows(request["document"])
            path_value = row["path"]
            _require(rows is not None and type(path_value) is str and any(original["id"] == identity
                     and (path_value == path or path_value.startswith(path + "/")) for path, original in rows),
                     "Diagnostic lost its original declaration occurrence or exact source path")
    obligations = _rows(report["obligations"], "Required full-pipeline obligations")
    identities: list[str] = []
    for raw in obligations:
        row = _object(raw, {"id", "status", "stage"}, "Planning obligation")
        identities.append(source._text(row["id"], "Obligation identity"))
        _require(row["status"] == "required" and row["stage"] == "full_pipeline", "Planning discharged a full-pipeline obligation")
    _require(identities == _record(report["target"], "Target descriptor")["deferred_stages"],
             "Plan changed or omitted required full-pipeline obligations")
    _require(bool(report["selected_models"]) == (states["model_lowering"] == "completed"),
             "Plan changed its selected-model census at the completed lowering boundary")
    _models(report, request)
    selected = _rows(report["selected_components"], "Selected component census")
    material = request["material_request"]
    if states["component_arrangement"] == "completed":
        original = _record(material, "Original component material authority")
        bridge = _record(original.get("catalog_binding"), "Original component bindings")
        _require(operational._same(cast(JsonValue, selected), bridge.get("components")), "Plan changed its exact selected component census")
    else:
        _require(not selected, "Plan claimed component selection before arrangement completed")
    if report["provider_dependencies"] is not None:
        _provider_graph(report["provider_dependencies"], request)
        _require(material is not None and states["provider_dependencies"] == "completed", "Provider diagnostics lack original material authority or completed analysis")
        issues = _rows(_record(report["provider_dependencies"], "Provider graph")["issues"], "Provider findings")
        _require((status == "planned") == (not issues), "Plan hid or invented provider dependency findings")
        if issues:
            expected_status = "missing_inputs" if issues[0]["kind"] == "missing" else "incompatible_inputs"
            _require(status == expected_status and diagnostics[0]["code"] == issues[0]["code"]
                     and missing == (["provider_dependencies"] if expected_status == "missing_inputs" else []),
                     "Plan changed its first provider dependency finding")
    usage = _object(report["usage"], {"work", "max_work"}, "Planning usage")
    _require(operational._same(usage["max_work"], limits["max_work"]), "Plan changed the original work limit")
    _integer(usage["work"], 0, cast(int, limits["max_work"]), "Planning work usage")
    return PolicyTargetPlan(response.request_id, response.operation, cast(PlanStatus, status), request_pin, report_pin,
                            encode_json(wrapper, limit=MAX_RESULT_BYTES))


@dataclass(frozen=True)
class PolicyTargetPlanningClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *, cancelled: Callable[[], bool] | None) -> PolicyTargetPlan:
        _require(self.transport.role == "core", "Target planning runs only through the native producer")
        snapshot = cast(dict[str, JsonValue], decode_json(encode_json(payload, limit=MAX_INPUT_BYTES)))
        request = _original(snapshot["request"])
        capabilities = self.transport.negotiate(operation, cancelled=cancelled)
        _require(operational._same(capabilities.profiles.get("policy_target_planning"), PROFILE)
                 and VALIDATION_SCOPE in capabilities.validation_scopes,
                 "Selected producer lacks the exact target planning profile")
        result = _result(self.transport.call(operation, snapshot, cancelled=cancelled), request)
        if operation == "replay-policy-target-plan":
            _require(operational._same(result.result, snapshot["report"]), "Fresh planning replay differs from the complete retained wrapper")
        return result

    def plan(self, request: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyTargetPlan:
        return self._call("plan-policy-target", {"request": request}, cancelled=cancelled)

    def replay(self, request: JsonValue, *, report: JsonValue,
               cancelled: Callable[[], bool] | None = None) -> PolicyTargetPlan:
        return self._call("replay-policy-target-plan", {"request": request, "report": report}, cancelled=cancelled)

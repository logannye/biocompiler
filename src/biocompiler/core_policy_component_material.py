"""Immutable native reusable-component transport; no Python semantic fallback.

Every call snapshots all original authority. Evidence is never reused across an
edit: check/export invoke native checking and replay requires exact fresh equality.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, cast

from biocompiler import core_policy_implementation as implementation
from biocompiler import core_policy_material as material
from biocompiler.core_client import (
    CoreClient, CoreProtocolError, CoreResponse, JsonValue, _OwnedJson, _object,
    _owned_encoding_scope, _owned_response_eligible, _try_owned_json_copy, decode_json, encode_json,
)

VALIDATION_SCOPE = "policy-component-mrna-v0.1"
IMPLEMENTATION = "biocompiler.ocaml.policy_component_material.v0.1"
RESOURCE_PROFILE = "biocompiler.policy_component_material_resources.v0.1"
RESULT_SCHEMA = "biocompiler.core.policy_component_material.v1"
CANDIDATE_SCHEMA = "biocompiler.policy_component_material_candidate.v0.1"
REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.1"
REQUEST_PROFILE = "biocompiler.policy_component_mrna.v0.1"
REPORT_SCHEMA = "biocompiler.policy_component_material_assessment.v0.1"
EXPORT_SCHEMA = "biocompiler.policy_component_mrna_export.v0.1"
MANIFEST_SCHEMA = "biocompiler.policy_component_mrna_manifest.v0.1"
CLAIM_SCOPE = "bounded_conditional_policy_via_reusable_components_to_exact_mrna"
PREMISE = "supplied_component_composition_and_provider_contracts"
ACCEPTED_STATUS = "checked_component_material"
MAX_RESULT_BYTES = material.MAX_RESULT_BYTES
MAX_RESULT_NODES = material.MAX_RESULT_NODES
PROFILE: dict[str, JsonValue] = {
    "operations": ["check-policy-component-material", "replay-policy-component-material", "export-policy-component-material"],
    "request_schema": REQUEST_SCHEMA, "candidate_schema": CANDIDATE_SCHEMA,
    "schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION,
    "resource_profile": RESOURCE_PROFILE, "validation_scope": VALIDATION_SCOPE,
    "max_result_bytes": MAX_RESULT_BYTES, "max_result_nodes": MAX_RESULT_NODES,
    "artifact": "on_fresh_export_only", "empirical": "unassessed",
}
PRODUCER_PROFILE: dict[str, JsonValue] = {
    "operations": ["compile-policy-component-material"], "implementation": IMPLEMENTATION, "validation_scope": VALIDATION_SCOPE,
}
_REQUEST_FIELDS = {"schema_version", "profile", "implementation_request", "component_library", "composition_rule",
                   "catalog_binding", "input_bindings", "resource_bindings", "context", "budgets"}
_CANDIDATE_FIELDS = {"schema_version", "behavior", "implementation", "binding", "assembly_proposal", "construction"}
_REPORT_FIELDS = (material._REPORT_FIELDS - {"material", "material_status"}) | {"assembly", "assembly_status"}
_same, _pin, _record, _rows, _count = material._same, material._pin, material._record, material._rows, material._count


def _original(value: JsonValue) -> dict[str, JsonValue]:
    request = _object(value, _REQUEST_FIELDS, "Original component material request")
    if request["schema_version"] != REQUEST_SCHEMA or request["profile"] != REQUEST_PROFILE:
        raise CoreProtocolError("Component material request changed its closed original profile")
    implementation._original(request["implementation_request"])
    for key in ("component_library", "composition_rule", "catalog_binding", "context", "budgets"):
        _record(request[key], "Original " + key)
    for key in ("input_bindings", "resource_bindings"):
        _rows(request[key], "Original " + key)
    return request


def _expect(row: dict[str, JsonValue], expected: dict[str, JsonValue], label: str) -> None:
    if any(not _same(row.get(key), value) for key, value in expected.items()):
        raise CoreProtocolError(label + " changed its declared identity or scope")


def _unique(rows: list[dict[str, JsonValue]], key: str, value: JsonValue, label: str) -> dict[str, JsonValue]:
    matches = [row for row in rows if _same(row.get(key), value)]
    if len(matches) != 1:
        raise CoreProtocolError(label + " lacks one exact original identity")
    return matches[0]


def _projections(request: dict[str, JsonValue], candidate: dict[str, JsonValue], leaf: dict[str, JsonValue]) -> None:
    """Bind retained inventories to originals and candidate; do not reconstruct RNA."""
    rule = _record(_record(request["composition_rule"], "Original rule").get("body"), "Original rule body")
    library = _rows(_record(request["component_library"], "Original library").get("components"), "Original components")
    components: dict[str, dict[str, JsonValue]] = {}
    for row in _rows(rule.get("components"), "Original component selections"):
        slot = row.get("slot")
        if type(slot) is not str or slot in components:
            raise CoreProtocolError("Original component selection has ambiguous slots")
        components[slot] = _record(_unique(library, "identity", row.get("component"), "Selected component").get("body"), "Component body")
    if list(components) != ["decision", "driver"]:
        raise CoreProtocolError("Component evidence changed its closed two-component inventory")
    roots = _rows(rule.get("root_bindings"), "Original root bindings")
    authority = _record(rule.get("material_authority"), "Original material authority")
    member_order = authority.get("member_order")
    if type(member_order) is not list or len(member_order) != 1:
        raise CoreProtocolError("Component evidence lacks its single original member")
    passed = leaf["outcome"] == "pass"
    construction = _record(candidate["construction"], "Construction")
    inventory = _record(construction.get("inventory"), "Checked inventory") if passed else {}
    molecules = _rows(inventory.get("molecules"), "Checked molecules") if passed else []
    features = _rows(_unique(molecules, "id", member_order[0], "Checked member").get("features"), "Checked features") if passed else []

    def site(value: JsonValue, slot: str, original: dict[str, JsonValue]) -> None:
        row = _object(value, {"slot", "root", "source", "feature", "local_path", "member", "path"}, "Retained carrier site")
        _expect(row, {"slot": slot, "root": original.get("root"), "source": _unique(roots, "slot", slot, "Root binding").get("source"),
                      "feature": original.get("feature"), "local_path": original.get("path"), "member": member_order[0]}, "Carrier projection")
        _record(row["path"], "Projected carrier path")
        if passed:
            feature = _unique(features, "id", original.get("feature"), "Projected final feature")
            if not _same(row["path"], feature.get("path")):
                raise CoreProtocolError("Carrier projection differs from the exact checked member feature")

    originals = [(slot, row) for slot, body in components.items() for row in _rows(body.get("carriers"), "Original local carriers")]
    retained = _rows(leaf["carrier_projections"], "Carrier projections")
    if len(retained) > len(originals) or passed and len(retained) != len(originals):
        raise CoreProtocolError("Assembly omitted or added original carrier projections")
    for raw, (slot, original) in zip(retained, originals):
        row = _object(raw, {"slot", "target", "sites"}, "Retained local carrier")
        _expect(row, {"slot": slot, "target": original.get("target")}, "Carrier target/order")
        sites, expected = _rows(row["sites"], "Projected sites"), _rows(original.get("sites"), "Original sites")
        if len(sites) != len(expected):
            raise CoreProtocolError("Assembly omitted an original carrier site")
        for value, supplied in zip(sites, expected):
            site(value, slot, supplied)
    links, returned = _rows(rule.get("link_carriers"), "Original link carriers"), _rows(leaf["link_projections"], "Link projections")
    if len(returned) > len(links) or passed and len(returned) != len(links):
        raise CoreProtocolError("Assembly omitted or added original cross-link projections")
    proposal = _record(candidate["assembly_proposal"], "Assembly proposal")
    bindings = _rows(proposal.get("nodes"), "Proposed node bindings")
    join = _record(rule.get("join"), "Original join")
    for raw, original in zip(returned, links):
        row = _object(raw, {"link", "join", "offset", "producer_endpoint", "consumer_endpoint", "producer", "consumer"}, "Retained cross-link")
        _expect(row, {"link": original.get("link"), "join": original.get("join"), "offset": join.get("offset")}, "Cross-link order/join")
        link = _unique(_rows(rule.get("links"), "Original links"), "id", original.get("link"), "Original link")
        for side in ("producer", "consumer"):
            boundary = _record(link.get(side), "Original boundary")
            slot = boundary.get("slot")
            if type(slot) is not str or slot not in components:
                raise CoreProtocolError("Cross-link lost its original component slot")
            local = components[slot]
            target: JsonValue = {"kind": "boundary_port", "id": boundary.get("boundary")}
            carrier = _unique(_rows(local.get("carriers"), "Local carriers"), "target", target, "Boundary carrier")
            sites = _rows(carrier.get("sites"), "Boundary sites")
            index = _count(original.get(side + "_site"), "Boundary site index")
            if index >= len(sites):
                raise CoreProtocolError("Cross-link references an absent original site")
            site(row[side], slot, sites[index])
            endpoint = _object(row[side + "_endpoint"], {"node", "port"}, "Actual boundary endpoint")
            if passed:
                fragment = _record(local.get("fragment"), "Original fragment")
                port = _unique(_rows(fragment.get("boundary_ports"), "Original boundary ports"), "id", boundary.get("boundary"), "Original boundary port")
                local_endpoint = _record(port.get("endpoint"), "Original local endpoint")
                actual = _unique([value for value in bindings if value.get("slot") == slot], "node", local_endpoint.get("node"), "Proposed endpoint")
                _expect(endpoint, {"node": actual.get("actual"), "port": local_endpoint.get("port")}, "Actual boundary endpoint")


def _context_inventory(request: dict[str, JsonValue], report: dict[str, JsonValue], leaf: dict[str, JsonValue]) -> None:
    material._context_obligations(request, report, leaf)
    context = _record(request["context"], "Original context")
    original_layout = _record(context.get("record_layout"), "Original complete record layout")
    if not _same(leaf["record_layout"], original_layout):
        raise CoreProtocolError("Context changed the complete original record declaration")
    derived = [_object(row, {"owner", "unit", "scope", "quantity"}, "Derived demand") for row in _rows(leaf["derived_demands"], "Derived demands")]
    allocations = _rows(request["resource_bindings"], "Original resource bindings")
    passed = leaf["outcome"] == "pass"
    if derived or passed:
        if len(derived) != len(allocations):
            raise CoreProtocolError("Context omitted the complete original resource inventory")
        for demand, allocation in zip(derived, allocations):
            _expect(demand, {key: allocation.get(key) for key in ("owner", "unit", "scope")}, "Demand identity/order")
            if _count(demand["quantity"], "Derived quantity") <= 0:
                raise CoreProtocolError("Context emitted a nonpositive resource demand")
        minimum = _object(leaf["minimum_record_layout"], set(original_layout), "Derived minimum records")
        variable = {"generations", "attempts", "maximum_tick", "ordered_reason_slots", "ordered_cause_slots", "identifier_bytes"}
        if passed:
            _expect(minimum, {key: value for key, value in original_layout.items() if key not in variable}, "Minimum record authority")
        for key in variable:
            required = _count(minimum[key], "Minimum " + key)
            if passed and required > _count(original_layout[key], "Declared " + key):
                raise CoreProtocolError("Context PASS exceeds an original record bound")
    elif leaf["minimum_record_layout"] is not None:
        raise CoreProtocolError("Context minimum record evidence omitted its derived demands")
    returned = _rows(leaf["resource_allocations"], "Retained allocations")
    if len(returned) > len(derived) or passed and len(returned) != len(derived):
        raise CoreProtocolError("Context omitted or added original allocation reservations")
    providers = [_record(row.get("body"), "Provider body") for row in _rows(context.get("providers"), "Original providers")]
    for row, allocation, demand in zip(returned, allocations, derived):
        provider = _unique(providers, "definition", allocation.get("provider"), "Allocation provider")
        capacity = _unique(_rows(provider.get("capacities"), "Original capacities"), "id", allocation.get("capacity"), "Allocation capacity")
        expected: JsonValue = {"demand": demand, "provider": provider.get("definition"), "capacity": capacity.get("id"),
                               "pool": capacity.get("pool_id"), "reserved": demand["quantity"]}
        if not _same(row, expected):
            raise CoreProtocolError("Context changed an original allocation reservation or its order")


def _leaves(request: dict[str, JsonValue], candidate: dict[str, JsonValue], report: dict[str, JsonValue]) -> None:
    rule = _record(request["composition_rule"], "Original rule")
    body = _record(rule.get("body"), "Original rule body")
    assembly, context = report["assembly"], report["context"]
    if assembly is not None:
        leaf = _object(assembly, {"schema_version", "checker_version", "profile", "original_fingerprint", "components_fingerprint",
            "rule_fingerprint", "implementation_fingerprint", "proposed_fingerprint", "candidate_fingerprint", "outcome", "diagnostics",
            "claim_scope", "premise", "structure", "carrier_projections", "link_projections", "preservation_evidence_fingerprint",
            "catalog_authorization", "context", "resource_capacity", "input_compatibility", "source_obligation_discharge", "empirical", "artifact", "export"}, "Assembly evidence")
        _expect(leaf, {"schema_version": "biocompiler.policy_component_assembly_assessment.v0.1",
            "checker_version": "biocompiler.ocaml.policy_component_assembly_check.v0.1", "profile": "biocompiler.policy_exact_component_assembly.v0.1",
            "claim_scope": "exact_supplied_component_graph_and_material_correspondence", "premise": "supplied_conditional_model_to_sequence_composition_rule",
            **{key: "unassessed" for key in ("catalog_authorization", "context", "resource_capacity", "input_compatibility", "source_obligation_discharge", "empirical")},
            "artifact": "withheld", "export": "withheld"}, "Assembly evidence")
        for key, original in (("original_fingerprint", request["implementation_request"]), ("components_fingerprint", request["component_library"]),
                ("rule_fingerprint", rule), ("implementation_fingerprint", candidate["implementation"]), ("proposed_fingerprint", candidate["assembly_proposal"]),
                ("candidate_fingerprint", candidate["construction"]), ("preservation_evidence_fingerprint", report["preservation"])):
            _pin(leaf[key], original, key)
        material._structure(leaf["structure"], authority=body.get("material_authority"), construction=candidate["construction"], outcome=leaf["outcome"])
        _projections(request, candidate, leaf)
    if context is not None:
        context_profile = _record(request["context"], "Original component context").get("profile")
        if context_profile not in (REQUEST_PROFILE, "biocompiler.policy_staged_component_mrna.v0.1"):
            raise CoreProtocolError("Original component context has an unsupported profile")
        leaf = _object(context, {"schema_version", "profile", "implementation_version", "request_fingerprint", "context_fingerprint", "assembly_fingerprint",
            "outcome", "claim_scope", "record_layout", "minimum_record_layout", "derived_demands", "resource_allocations", "source_obligations", "discharges",
            "diagnostics", "source_receipt_status", "biological_validity", "human_use", "artifact", "export"}, "Component context evidence")
        _expect(leaf, {"schema_version": "biocompiler.policy_component_context_assessment.v0.1", "profile": context_profile,
            "implementation_version": "biocompiler.ocaml.policy_component_context_check.v0.1", "claim_scope": "conditional_component_context_and_complete_record_capacity",
            "source_receipt_status": "unchanged", "biological_validity": "unassessed", "human_use": "unassessed", "artifact": "withheld", "export": "withheld"}, "Context evidence")
        for key, original in (("request_fingerprint", request), ("context_fingerprint", request["context"]), ("assembly_fingerprint", assembly)):
            _pin(leaf[key], original, key)
        _context_inventory(request, report, leaf)
    catalog = report["catalog"]
    if catalog is not None:
        leaf = _object(catalog, {"status", "original_binding", "selected_catalog_entry", "component_library_fingerprint", "rule_fingerprint", "premise"}, "Component catalog bridge")
        original = _record(request["catalog_binding"], "Original component bridge")
        _expect(leaf, {"status": "pass", "original_binding": original, "selected_catalog_entry": original.get("entry_id"),
                      "premise": "supplied_conditional_component_composition_and_provider_contracts"}, "Component catalog bridge")
        _pin(leaf["component_library_fingerprint"], request["component_library"], "Original component library")
        _pin(leaf["rule_fingerprint"], rule, "Original assembly rule")
    for value, key in ((assembly, "assembly_status"), (context, "context_status")):
        expected = "unassessed" if value is None else _record(value, key).get("outcome")
        if expected not in ("unassessed", "pass", "fail", "unknown", "unsupported") or report[key] != expected:
            raise CoreProtocolError("Component stage status contradicts its retained evidence")
    preservation = _record(report["preservation"], "Preservation")
    if (catalog is not None and preservation.get("status") != "checked_implementation"
            or assembly is not None and catalog is None or context is not None and report["assembly_status"] != "pass"):
        raise CoreProtocolError("Component evidence bypassed a required fresh preceding stage")


@dataclass(frozen=True)
class PolicyComponentMaterialResult(material.PolicyMaterialResult):
    """Immutable component evidence; only a fresh export returns paired native bytes."""


def _candidate(value: JsonValue) -> dict[str, JsonValue]:
    candidate = _object(value, _CANDIDATE_FIELDS, "Complete component candidate")
    if candidate["schema_version"] != CANDIDATE_SCHEMA:
        raise CoreProtocolError("Component checking changed the complete supplied candidate")
    proposal = _object(candidate["assembly_proposal"], {"schema_version", "profile", "rule", "nodes"}, "Assembly proposal")
    _expect(proposal, {"schema_version": "biocompiler.policy_component_assembly_proposal.v0.1", "profile": "biocompiler.policy_exact_component_assembly.v0.1"}, "Assembly proposal")
    return candidate


def _report(value: JsonValue) -> dict[str, JsonValue]:
    report = _object(value, _REPORT_FIELDS, "Complete component assessment")
    _expect(report, {"schema_version": REPORT_SCHEMA, "profile": REQUEST_PROFILE,
        "implementation": "biocompiler.ocaml.policy_component_material_check.v0.1", "resource_profile": RESOURCE_PROFILE,
        "claim_scope": CLAIM_SCOPE, "premise": PREMISE, "empirical": "unassessed", "artifact": "withheld", "export": "withheld"}, "Component report")
    return report


def _assessment(response: CoreResponse, request: dict[str, JsonValue], candidate: dict[str, JsonValue],
                report: dict[str, JsonValue], limits: JsonValue) -> None:
    """Check an actual nested assessment, without constructing a child response."""
    invocation: JsonValue = {"request": request, "candidate": candidate, "limits": limits}
    for key, original in (("request_fingerprint", request), ("candidate_fingerprint", candidate), ("invocation_fingerprint", invocation)):
        _pin(report[key], original, key)
    if not _same(report["limits"], limits) or not _same(report["budgets"], request["budgets"]):
        raise CoreProtocolError("Component checking changed original budgets or preservation limits")
    usage = _object(report["usage"], {"unit", "charged_work", "request_decoding_work"}, "Component work accounting")
    budgets = _record(request["budgets"], "Original component budgets")
    charged = _count(usage["charged_work"], "Charged work")
    if (usage["unit"] != "logical_data_visits_and_child_semantic_work" or charged < _count(usage["request_decoding_work"], "Request work")
            or charged > _count(budgets.get("max_work"), "Original maximum work")):
        raise CoreProtocolError("Component work accounting changed its unit or original bound")
    material._preservation(response, request, candidate, report, limits)
    _leaves(request, candidate, report)
    material._obligations(report, material_key="assembly", accepted_status=ACCEPTED_STATUS, conjunction_stage="conditional_component_context_conjunction")


def _result(response: CoreResponse, payload: dict[str, JsonValue]) -> PolicyComponentMaterialResult:
    result = _object(response.result, material._RESULT_FIELDS, "Component material result")
    _expect(result, {"schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION,
                    "resource_profile": RESOURCE_PROFILE, "validation_scope": VALIDATION_SCOPE}, "Negotiated component result")
    request = _original(payload["request"])
    candidate = _object(result["candidate"], _CANDIDATE_FIELDS, "Complete component candidate")
    if candidate["schema_version"] != CANDIDATE_SCHEMA or "candidate" in payload and not _same(candidate, payload["candidate"]):
        raise CoreProtocolError("Component checking changed the complete supplied candidate")
    _candidate(candidate)
    report = _report(result["report"])
    invocation: JsonValue = {"request": request, "candidate": candidate, "limits": payload["limits"]}
    request_hash = _pin(result["request_fingerprint"], request, "Complete original component request")
    candidate_hash = _pin(result["candidate_fingerprint"], candidate, "Complete component candidate")
    invocation_hash = _pin(result["invocation_fingerprint"], invocation, "Complete component invocation")
    report_hash = _pin(result["report_fingerprint"], report, "Complete component report")
    _assessment(response, request, candidate, report, payload["limits"])
    material._artifact(result["artifact"], operation=response.operation, request=request, candidate=candidate, report=report, limits=payload["limits"],
        export_operation="export-policy-component-material", accepted_status=ACCEPTED_STATUS, export_schema=EXPORT_SCHEMA,
        manifest_schema=MANIFEST_SCHEMA, request_profile=REQUEST_PROFILE, claim_scope=CLAIM_SCOPE, premise=PREMISE)
    if response.operation == "replay-policy-component-material" and not _same(result, payload["report"]):
        raise CoreProtocolError("Fresh replay differs from the complete retained component wrapper")
    budgets = _record(request["budgets"], "Original component budgets")
    material._publication(report, _count(budgets.get("max_report_bytes"), "Original report byte ceiling"),
                          _count(budgets.get("max_report_nodes"), "Original report node ceiling"))
    material._publication({"result": result}, MAX_RESULT_BYTES, MAX_RESULT_NODES)
    return PolicyComponentMaterialResult(response.request_id, response.operation, response.executable,
        request_hash, candidate_hash, invocation_hash, report_hash, encode_json(result))


@dataclass(frozen=True)
class PolicyComponentMaterialClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *, cancelled: Callable[[], bool] | None) -> PolicyComponentMaterialResult:
        input_bytes = encode_json(payload)
        snapshot = cast(dict[str, JsonValue], decode_json(input_bytes))
        _original(snapshot["request"])
        if operation == "compile-policy-component-material" and self.transport.role != "core":
            raise CoreProtocolError("Component production requires an explicitly selected Core producer")
        capabilities = self.transport.negotiate(operation, cancelled=cancelled)
        if not _same(capabilities.profiles.get("policy_component_material"), PROFILE) or VALIDATION_SCOPE not in capabilities.validation_scopes:
            raise CoreProtocolError("Selected executable lacks the exact component material profile")
        if operation == "compile-policy-component-material" and not _same(capabilities.profiles.get("policy_component_material_producer"), PRODUCER_PROFILE):
            raise CoreProtocolError("Selected executable lacks the exact component producer profile")
        # Transport never receives the private original authority used below.
        response = self.transport.call(operation, decode_json(input_bytes), cancelled=cancelled)
        if not _owned_response_eligible(response):
            return _result(response, snapshot)
        owned = _try_owned_json_copy(response.result)
        if owned is None:
            return _result(response, snapshot)
        private_response = replace(response, result=owned.value)
        with _owned_encoding_scope(_OwnedJson(snapshot), owned):
            return _result(private_response, snapshot)

    def compile(self, request: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyComponentMaterialResult:
        return self._call("compile-policy-component-material", {"request": request, "limits": limits}, cancelled=cancelled)

    def check(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyComponentMaterialResult:
        return self._call("check-policy-component-material", {"request": request, "candidate": candidate, "limits": limits}, cancelled=cancelled)

    def replay(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, report: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyComponentMaterialResult:
        return self._call("replay-policy-component-material", {"request": request, "candidate": candidate, "limits": limits, "report": report}, cancelled=cancelled)

    def export(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyComponentMaterialResult:
        """Freshly recheck complete original authority before paired export."""
        return self._call("export-policy-component-material", {"request": request, "candidate": candidate, "limits": limits}, cancelled=cancelled)

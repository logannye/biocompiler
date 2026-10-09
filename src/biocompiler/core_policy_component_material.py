"""Immutable native reusable-component transport; no Python semantic fallback.

Every call snapshots all original authority. Evidence is never reused across an
edit: check/export invoke native checking and replay requires exact fresh equality.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from fractions import Fraction
import re
from typing import Callable, Literal, cast

from biocompiler import core_policy_implementation as implementation
from biocompiler import core_policy_material as material
from biocompiler import _policy_coupled_wire as coupled_wire
from biocompiler.core_client import CoreClient, CoreProtocolError, CoreResponse, JsonValue, _object, decode_json, encode_json

VALIDATION_SCOPE = "policy-component-mrna-v0.1"
IMPLEMENTATION = "biocompiler.ocaml.policy_component_material.v0.1"
RESOURCE_PROFILE = "biocompiler.policy_component_material_resources.v0.1"
RESULT_SCHEMA = "biocompiler.core.policy_component_material.v1"
CANDIDATE_SCHEMA = "biocompiler.policy_component_material_candidate.v0.1"
REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.1"
REQUEST_PROFILE = "biocompiler.policy_component_mrna.v0.1"
INSTANCE_REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.2"
INSTANCE_REQUEST_PROFILE = "biocompiler.policy_instance_component_mrna.v0.1"
INSTANCE_ASSEMBLY_PROFILE = "biocompiler.policy_instance_component_assembly.v0.1"
INSTANCE_IMPLEMENTATION = "biocompiler.ocaml.policy_instance_component_material.v0.1"
INSTANCE_VALIDATION_SCOPE = "policy-instance-component-mrna-v0.1"
PREREQUISITE_REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.3"
PREREQUISITE_REQUEST_PROFILE = "biocompiler.policy_instance_prerequisite_mrna.v0.1"
PREREQUISITE_IMPLEMENTATION = "biocompiler.ocaml.policy_instance_prerequisite_material.v0.1"
PREREQUISITE_VALIDATION_SCOPE = "policy-instance-prerequisite-mrna-v0.1"
TWO_OBSERVATION_REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.4"
TWO_OBSERVATION_REQUEST_PROFILE = "biocompiler.policy_instance_two_observation_prerequisite_mrna.v0.1"
TWO_OBSERVATION_IMPLEMENTATION = "biocompiler.ocaml.policy_instance_two_observation_prerequisite_material.v0.1"
TWO_OBSERVATION_VALIDATION_SCOPE = "policy-instance-two-observation-prerequisite-mrna-v0.1"
MULTI_MEMBER_REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.5"
MULTI_MEMBER_REQUEST_PROFILE = "biocompiler.policy_multi_member_prerequisite_mrna.v0.1"
MULTI_MEMBER_ASSEMBLY_PROFILE = "biocompiler.policy_multi_member_component_assembly.v0.1"
MULTI_MEMBER_IMPLEMENTATION = "biocompiler.ocaml.policy_multi_member_prerequisite_material.v0.1"
MULTI_MEMBER_VALIDATION_SCOPE = "policy-multi-member-prerequisite-mrna-v0.1"
GROUNDED_HELPER_REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.6"
GROUNDED_HELPER_REQUEST_PROFILE = "biocompiler.policy_grounded_helper_prerequisite_mrna.v0.1"
GROUNDED_HELPER_ASSEMBLY_PROFILE = "biocompiler.policy_grounded_helper_component_assembly.v0.1"
GROUNDED_HELPER_IMPLEMENTATION = "biocompiler.ocaml.policy_grounded_helper_prerequisite_material.v0.1"
GROUNDED_HELPER_VALIDATION_SCOPE = "policy-grounded-helper-prerequisite-mrna-v0.1"
FINITE_MACHINE_REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.7"
FINITE_MACHINE_REQUEST_PROFILE = "biocompiler.policy_finite_machine_component_mrna.v0.1"
FINITE_MACHINE_IMPLEMENTATION = "biocompiler.ocaml.policy_finite_machine_component_material.v0.1"
FINITE_MACHINE_VALIDATION_SCOPE = "policy-finite-machine-component-mrna-v0.1"
NETWORK_REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.9"
NETWORK_REQUEST_PROFILE = "biocompiler.policy_network_component_mrna.v0.1"
NETWORK_IMPLEMENTATION = "biocompiler.ocaml.policy_network_component_material.v0.1"
NETWORK_VALIDATION_SCOPE = "policy-network-component-mrna-v0.1"
QUANTITATIVE_REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.8"
QUANTITATIVE_REQUEST_PROFILE = "biocompiler.policy_sampled_reservoir_component_mrna.v0.1"
QUANTITATIVE_IMPLEMENTATION = "biocompiler.ocaml.policy_sampled_reservoir_component_material.v0.1"
QUANTITATIVE_VALIDATION_SCOPE = "policy-sampled-reservoir-component-mrna-v0.1"
STEP_QUANTITATIVE_REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.10"
STEP_QUANTITATIVE_REQUEST_PROFILE = "biocompiler.policy_sampled_step_reservoir_component_mrna.v0.1"
STEP_QUANTITATIVE_IMPLEMENTATION = "biocompiler.ocaml.policy_sampled_step_reservoir_component_material.v0.1"
STEP_QUANTITATIVE_VALIDATION_SCOPE = "policy-sampled-step-reservoir-component-mrna-v0.1"
TRANSFER_PAIR_REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.11"
TRANSFER_PAIR_REQUEST_PROFILE = "biocompiler.policy_sampled_transfer_pair_component_mrna.v0.1"
TRANSFER_PAIR_IMPLEMENTATION = "biocompiler.ocaml.policy_sampled_transfer_pair_component_material.v0.1"
TRANSFER_PAIR_VALIDATION_SCOPE = "policy-sampled-transfer-pair-component-mrna-v0.1"
COMPOSITION_REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.13"
COMPOSITION_REQUEST_PROFILE = "biocompiler.policy_coupled_transfer_network_component_mrna.v0.1"
COMPOSITION_IMPLEMENTATION = "biocompiler.ocaml.policy_coupled_quantitative_component_material.v0.1"
COMPOSITION_VALIDATION_SCOPE = "policy-coupled-quantitative-component-mrna-v0.1"
TRANSFER_NETWORK_REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.12"
TRANSFER_NETWORK_REQUEST_PROFILE = "biocompiler.policy_sampled_transfer_network_component_mrna.v0.1"
TRANSFER_NETWORK_IMPLEMENTATION = "biocompiler.ocaml.policy_sampled_transfer_network_component_material.v0.1"
TRANSFER_NETWORK_VALIDATION_SCOPE = "policy-sampled-transfer-network-component-mrna-v0.1"
MULTI_SITE_ASSEMBLY_PROFILE = "biocompiler.policy_multi_site_component_assembly.v0.1"
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
INSTANCE_PROFILE: dict[str, JsonValue] = {
    **PROFILE, "request_schema": INSTANCE_REQUEST_SCHEMA, "implementation": INSTANCE_IMPLEMENTATION,
    "validation_scope": INSTANCE_VALIDATION_SCOPE,
}
INSTANCE_PRODUCER_PROFILE: dict[str, JsonValue] = {
    **PRODUCER_PROFILE, "implementation": INSTANCE_IMPLEMENTATION, "validation_scope": INSTANCE_VALIDATION_SCOPE,
}
PREREQUISITE_PROFILE: dict[str, JsonValue] = {
    **PROFILE, "request_schema": PREREQUISITE_REQUEST_SCHEMA, "implementation": PREREQUISITE_IMPLEMENTATION,
    "validation_scope": PREREQUISITE_VALIDATION_SCOPE,
}
PREREQUISITE_PRODUCER_PROFILE: dict[str, JsonValue] = {
    **PRODUCER_PROFILE, "implementation": PREREQUISITE_IMPLEMENTATION, "validation_scope": PREREQUISITE_VALIDATION_SCOPE,
}
TWO_OBSERVATION_PROFILE: dict[str, JsonValue] = {
    **PROFILE, "request_schema": TWO_OBSERVATION_REQUEST_SCHEMA, "implementation": TWO_OBSERVATION_IMPLEMENTATION,
    "validation_scope": TWO_OBSERVATION_VALIDATION_SCOPE,
}
TWO_OBSERVATION_PRODUCER_PROFILE: dict[str, JsonValue] = {
    **PRODUCER_PROFILE, "implementation": TWO_OBSERVATION_IMPLEMENTATION, "validation_scope": TWO_OBSERVATION_VALIDATION_SCOPE,
}
MULTI_MEMBER_PROFILE: dict[str, JsonValue] = {
    **PROFILE, "request_schema": MULTI_MEMBER_REQUEST_SCHEMA, "implementation": MULTI_MEMBER_IMPLEMENTATION,
    "validation_scope": MULTI_MEMBER_VALIDATION_SCOPE,
}
MULTI_MEMBER_PRODUCER_PROFILE: dict[str, JsonValue] = {
    **PRODUCER_PROFILE, "implementation": MULTI_MEMBER_IMPLEMENTATION, "validation_scope": MULTI_MEMBER_VALIDATION_SCOPE,
}
GROUNDED_HELPER_PROFILE: dict[str, JsonValue] = {
    **PROFILE, "request_schema": GROUNDED_HELPER_REQUEST_SCHEMA, "implementation": GROUNDED_HELPER_IMPLEMENTATION,
    "validation_scope": GROUNDED_HELPER_VALIDATION_SCOPE,
}
GROUNDED_HELPER_PRODUCER_PROFILE: dict[str, JsonValue] = {
    **PRODUCER_PROFILE, "implementation": GROUNDED_HELPER_IMPLEMENTATION, "validation_scope": GROUNDED_HELPER_VALIDATION_SCOPE,
}
FINITE_MACHINE_PROFILE: dict[str, JsonValue] = {
    **PROFILE, "request_schema": FINITE_MACHINE_REQUEST_SCHEMA, "implementation": FINITE_MACHINE_IMPLEMENTATION,
    "validation_scope": FINITE_MACHINE_VALIDATION_SCOPE,
}
FINITE_MACHINE_PRODUCER_PROFILE: dict[str, JsonValue] = {
    **PRODUCER_PROFILE, "implementation": FINITE_MACHINE_IMPLEMENTATION, "validation_scope": FINITE_MACHINE_VALIDATION_SCOPE,
}
NETWORK_PROFILE: dict[str, JsonValue] = {
    **PROFILE, "request_schema": NETWORK_REQUEST_SCHEMA, "implementation": NETWORK_IMPLEMENTATION,
    "validation_scope": NETWORK_VALIDATION_SCOPE,
}
NETWORK_PRODUCER_PROFILE: dict[str, JsonValue] = {
    **PRODUCER_PROFILE, "implementation": NETWORK_IMPLEMENTATION, "validation_scope": NETWORK_VALIDATION_SCOPE,
}
QUANTITATIVE_PROFILE: dict[str, JsonValue] = {
    **PROFILE, "request_schema": QUANTITATIVE_REQUEST_SCHEMA, "implementation": QUANTITATIVE_IMPLEMENTATION,
    "validation_scope": QUANTITATIVE_VALIDATION_SCOPE,
}
QUANTITATIVE_PRODUCER_PROFILE: dict[str, JsonValue] = {
    **PRODUCER_PROFILE, "implementation": QUANTITATIVE_IMPLEMENTATION, "validation_scope": QUANTITATIVE_VALIDATION_SCOPE,
}
STEP_QUANTITATIVE_PROFILE: dict[str, JsonValue] = {
    **PROFILE, "request_schema": STEP_QUANTITATIVE_REQUEST_SCHEMA, "implementation": STEP_QUANTITATIVE_IMPLEMENTATION,
    "validation_scope": STEP_QUANTITATIVE_VALIDATION_SCOPE,
}
STEP_QUANTITATIVE_PRODUCER_PROFILE: dict[str, JsonValue] = {
    **PRODUCER_PROFILE, "implementation": STEP_QUANTITATIVE_IMPLEMENTATION,
    "validation_scope": STEP_QUANTITATIVE_VALIDATION_SCOPE,
}
TRANSFER_PAIR_PROFILE: dict[str, JsonValue] = {
    **PROFILE, "request_schema": TRANSFER_PAIR_REQUEST_SCHEMA, "implementation": TRANSFER_PAIR_IMPLEMENTATION,
    "validation_scope": TRANSFER_PAIR_VALIDATION_SCOPE,
}
TRANSFER_PAIR_PRODUCER_PROFILE: dict[str, JsonValue] = {
    **PRODUCER_PROFILE, "implementation": TRANSFER_PAIR_IMPLEMENTATION,
    "validation_scope": TRANSFER_PAIR_VALIDATION_SCOPE,
}
COMPOSITION_PROFILE: dict[str, JsonValue] = {**PROFILE, "request_schema": COMPOSITION_REQUEST_SCHEMA,
    "implementation": COMPOSITION_IMPLEMENTATION, "validation_scope": COMPOSITION_VALIDATION_SCOPE}
COMPOSITION_PRODUCER_PROFILE: dict[str, JsonValue] = {**PRODUCER_PROFILE, "implementation": COMPOSITION_IMPLEMENTATION,
    "validation_scope": COMPOSITION_VALIDATION_SCOPE}
TRANSFER_NETWORK_PROFILE: dict[str, JsonValue] = {
    **PROFILE, "request_schema": TRANSFER_NETWORK_REQUEST_SCHEMA, "implementation": TRANSFER_NETWORK_IMPLEMENTATION,
    "validation_scope": TRANSFER_NETWORK_VALIDATION_SCOPE,
}
TRANSFER_NETWORK_PRODUCER_PROFILE: dict[str, JsonValue] = {
    **PRODUCER_PROFILE, "implementation": TRANSFER_NETWORK_IMPLEMENTATION,
    "validation_scope": TRANSFER_NETWORK_VALIDATION_SCOPE,
}
_REQUEST_FIELDS = {"schema_version", "profile", "implementation_request", "component_library", "composition_rule",
                   "catalog_binding", "input_bindings", "resource_bindings", "context", "budgets"}
_CANDIDATE_FIELDS = {"schema_version", "behavior", "implementation", "binding", "assembly_proposal", "construction"}
_REPORT_FIELDS = (material._REPORT_FIELDS - {"material", "material_status"}) | {"assembly", "assembly_status"}
_same, _pin, _record, _rows, _count = material._same, material._pin, material._record, material._rows, material._count


def _document_pin(actual: JsonValue, expected: JsonValue, label: str) -> str:
    digest = hashlib.sha256(coupled_wire.canonical_bytes(expected)).hexdigest()
    if actual != digest:
        raise CoreProtocolError(label + " fingerprint does not match complete supplied authority")
    return digest


def _document_same(left: JsonValue, right: JsonValue) -> bool:
    return coupled_wire.canonical_bytes(left) == coupled_wire.canonical_bytes(right)


def _stored_result(data: bytes) -> dict[str, JsonValue]:
    raw = decode_json(data)
    return cast(dict[str, JsonValue], coupled_wire.unpack(raw) if coupled_wire.is_packet(raw) else raw)


def _result_bytes(value: JsonValue, *, coupled: bool) -> bytes:
    return encode_json(coupled_wire.pack(value) if coupled else value)


def _wire_response(response: CoreResponse, *, coupled: bool) -> CoreResponse:
    if coupled != coupled_wire.is_packet(response.result):
        raise CoreProtocolError("Coupled wire response does not match the negotiated original profile")
    return replace(response, result=coupled_wire.unpack(response.result)) if coupled else response


def _wire_capability(profiles: dict[str, JsonValue], role: Literal["core", "verify"]) -> None:
    if not _same(profiles.get("policy_coupled_wire"), coupled_wire.profile(role)):
        raise CoreProtocolError("Selected executable lacks the exact coupled JSON graph wire profile")


def _original(value: JsonValue) -> dict[str, JsonValue]:
    quantitative = _record(value, "Original component material request").get("profile") in (QUANTITATIVE_REQUEST_PROFILE, STEP_QUANTITATIVE_REQUEST_PROFILE, TRANSFER_PAIR_REQUEST_PROFILE, TRANSFER_NETWORK_REQUEST_PROFILE, COMPOSITION_REQUEST_PROFILE)
    request = _object(value, _REQUEST_FIELDS | ({"quantitative"} if quantitative else set()), "Original component material request")
    if (request["schema_version"], request["profile"]) not in ((REQUEST_SCHEMA, REQUEST_PROFILE),
            (INSTANCE_REQUEST_SCHEMA, INSTANCE_REQUEST_PROFILE),
            (PREREQUISITE_REQUEST_SCHEMA, PREREQUISITE_REQUEST_PROFILE),
            (TWO_OBSERVATION_REQUEST_SCHEMA, TWO_OBSERVATION_REQUEST_PROFILE),
            (MULTI_MEMBER_REQUEST_SCHEMA, MULTI_MEMBER_REQUEST_PROFILE),
            (GROUNDED_HELPER_REQUEST_SCHEMA, GROUNDED_HELPER_REQUEST_PROFILE),
            (FINITE_MACHINE_REQUEST_SCHEMA, FINITE_MACHINE_REQUEST_PROFILE),
            (NETWORK_REQUEST_SCHEMA, NETWORK_REQUEST_PROFILE),
            (QUANTITATIVE_REQUEST_SCHEMA, QUANTITATIVE_REQUEST_PROFILE),
            (STEP_QUANTITATIVE_REQUEST_SCHEMA, STEP_QUANTITATIVE_REQUEST_PROFILE),
            (TRANSFER_PAIR_REQUEST_SCHEMA, TRANSFER_PAIR_REQUEST_PROFILE),
            (TRANSFER_NETWORK_REQUEST_SCHEMA, TRANSFER_NETWORK_REQUEST_PROFILE),
            (COMPOSITION_REQUEST_SCHEMA, COMPOSITION_REQUEST_PROFILE)):
        raise CoreProtocolError("Component material request changed its closed original profile")
    decoder = (implementation._coupled_original if _composition(request) else implementation._multi_site_original if _multi_site(request) else implementation._network_original if _network(request) else implementation._finite_machine_original if _finite_machine(request) else implementation._multi_product_original if _multi_member(request) else
               implementation._two_observation_original if _two_observations(request) else
               implementation._prerequisite_original if _prerequisites(request) else implementation._original)
    decoder(request["implementation_request"])
    for key in ("component_library", "composition_rule", "catalog_binding", "context", "budgets"):
        _record(request[key], "Original " + key)
    for key in ("input_bindings", "resource_bindings"):
        _rows(request[key], "Original " + key)
    if quantitative:
        raw_contract = request["quantitative"]
        if _composition(request):
            composed = _object(raw_contract, {"network", "owners", "synchronization"}, "Coupled original contract")
            if composed["synchronization"] != "one_prestate_one_atomic_commit":
                raise CoreProtocolError("Coupled original lost its atomic coordination premise")
            owners = _rows(composed["owners"], "Complete original reservoir owners")
            if not 2 <= len(owners) <= 4:
                raise CoreProtocolError("Coupled original needs two to four explicit private owners")
            for owner in owners:
                _object(owner, {"instance", "component", "contract", "compartment", "state"}, "Reservoir owner")
            raw_contract = composed["network"]
        contract = _object(raw_contract, {"mechanism", "selection", "source"}, "Original quantitative contract")
        mechanism = _record(contract["mechanism"], "Independent original reservoir law")
        _expect(mechanism, {"schema_version": "biocompiler.policy_sampled_transfer_network.v0.1" if (_transfer_network(request) or _composition(request)) else "biocompiler.policy_sampled_transfer_pair.v0.1" if _transfer_pair(request) else "biocompiler.policy_sampled_reservoir.v0.2" if _multi_site(request) else "biocompiler.policy_sampled_reservoir.v0.1",
            "profile": "biocompiler.policy_sampled_reserved_transfer_network.v0.1" if (_transfer_network(request) or _composition(request)) else "biocompiler.policy_sampled_conservative_transfer_pair.v0.1" if _transfer_pair(request) else "biocompiler.policy_sampled_saturating_step_reservoir.v0.1" if _multi_site(request) else "biocompiler.policy_sampled_saturating_reservoir.v0.1"}, "Original quantitative family")
        _object(contract["selection"], {"instance", "component", "contract"}, "Original quantitative selection")
        _object(contract["source"], {"machine", "observation", "effect"}, "Original quantitative source")
    else:
        library = _record(request["component_library"], "Original component library")
        for component in _rows(library.get("components"), "Original local components"):
            if (component.get("schema_version") == "biocompiler.policy_component_material.v0.2"
                    or component.get("profile") == "biocompiler.policy_quantitative_local_material.v0.1"
                    or "quantitative_contracts" in _record(component.get("body"), "Original local component body")):
                raise CoreProtocolError("Quantitative local components require their explicit original material profile")
    return request


def _instanced(request: dict[str, JsonValue]) -> bool:
    return request["profile"] in (INSTANCE_REQUEST_PROFILE, PREREQUISITE_REQUEST_PROFILE, TWO_OBSERVATION_REQUEST_PROFILE,
                                 MULTI_MEMBER_REQUEST_PROFILE, GROUNDED_HELPER_REQUEST_PROFILE, FINITE_MACHINE_REQUEST_PROFILE, QUANTITATIVE_REQUEST_PROFILE, NETWORK_REQUEST_PROFILE, STEP_QUANTITATIVE_REQUEST_PROFILE, TRANSFER_PAIR_REQUEST_PROFILE, TRANSFER_NETWORK_REQUEST_PROFILE, COMPOSITION_REQUEST_PROFILE)


def _prerequisites(request: dict[str, JsonValue]) -> bool:
    return request["profile"] in (PREREQUISITE_REQUEST_PROFILE, TWO_OBSERVATION_REQUEST_PROFILE,
                                 MULTI_MEMBER_REQUEST_PROFILE, GROUNDED_HELPER_REQUEST_PROFILE, FINITE_MACHINE_REQUEST_PROFILE, QUANTITATIVE_REQUEST_PROFILE, NETWORK_REQUEST_PROFILE, STEP_QUANTITATIVE_REQUEST_PROFILE, TRANSFER_PAIR_REQUEST_PROFILE, TRANSFER_NETWORK_REQUEST_PROFILE, COMPOSITION_REQUEST_PROFILE)


def _two_observations(request: dict[str, JsonValue]) -> bool:
    return request["profile"] == TWO_OBSERVATION_REQUEST_PROFILE


def _multi_member(request: dict[str, JsonValue]) -> bool:
    return request["profile"] in (MULTI_MEMBER_REQUEST_PROFILE, GROUNDED_HELPER_REQUEST_PROFILE)


def _grounded_helper(request: dict[str, JsonValue]) -> bool:
    return request["profile"] == GROUNDED_HELPER_REQUEST_PROFILE


def _finite_machine(request: dict[str, JsonValue]) -> bool:
    return request["profile"] in (FINITE_MACHINE_REQUEST_PROFILE, QUANTITATIVE_REQUEST_PROFILE, STEP_QUANTITATIVE_REQUEST_PROFILE, TRANSFER_PAIR_REQUEST_PROFILE, TRANSFER_NETWORK_REQUEST_PROFILE, COMPOSITION_REQUEST_PROFILE)


def _network(request: dict[str, JsonValue]) -> bool:
    return request["profile"] == NETWORK_REQUEST_PROFILE


def _composition(request: dict[str, JsonValue]) -> bool:
    return request["profile"] == COMPOSITION_REQUEST_PROFILE


def _transfer_network(request: dict[str, JsonValue]) -> bool:
    return request["profile"] == TRANSFER_NETWORK_REQUEST_PROFILE


def _transfer_pair(request: dict[str, JsonValue]) -> bool:
    return request["profile"] == TRANSFER_PAIR_REQUEST_PROFILE


def _multi_site(request: dict[str, JsonValue]) -> bool:
    return request["profile"] in (STEP_QUANTITATIVE_REQUEST_PROFILE, TRANSFER_PAIR_REQUEST_PROFILE, TRANSFER_NETWORK_REQUEST_PROFILE, COMPOSITION_REQUEST_PROFILE)


def _quantitative(request: dict[str, JsonValue]) -> bool:
    return request["profile"] in (QUANTITATIVE_REQUEST_PROFILE, STEP_QUANTITATIVE_REQUEST_PROFILE, TRANSFER_PAIR_REQUEST_PROFILE, TRANSFER_NETWORK_REQUEST_PROFILE, COMPOSITION_REQUEST_PROFILE)


def _profile_settings(request: dict[str, JsonValue]) -> tuple[str, dict[str, JsonValue], dict[str, JsonValue], str, str]:
    if _composition(request):
        return ("policy_coupled_quantitative_material", COMPOSITION_PROFILE, COMPOSITION_PRODUCER_PROFILE,
                COMPOSITION_VALIDATION_SCOPE, COMPOSITION_IMPLEMENTATION)
    if _transfer_network(request):
        return ("policy_transfer_network_material", TRANSFER_NETWORK_PROFILE, TRANSFER_NETWORK_PRODUCER_PROFILE,
                TRANSFER_NETWORK_VALIDATION_SCOPE, TRANSFER_NETWORK_IMPLEMENTATION)
    if _transfer_pair(request):
        return ("policy_transfer_pair_material", TRANSFER_PAIR_PROFILE, TRANSFER_PAIR_PRODUCER_PROFILE,
                TRANSFER_PAIR_VALIDATION_SCOPE, TRANSFER_PAIR_IMPLEMENTATION)
    if _multi_site(request):
        return ("policy_step_quantitative_material", STEP_QUANTITATIVE_PROFILE, STEP_QUANTITATIVE_PRODUCER_PROFILE,
                STEP_QUANTITATIVE_VALIDATION_SCOPE, STEP_QUANTITATIVE_IMPLEMENTATION)
    if _network(request):
        return ("policy_network_material", NETWORK_PROFILE, NETWORK_PRODUCER_PROFILE,
                NETWORK_VALIDATION_SCOPE, NETWORK_IMPLEMENTATION)
    if _quantitative(request):
        return ("policy_quantitative_material", QUANTITATIVE_PROFILE, QUANTITATIVE_PRODUCER_PROFILE,
                QUANTITATIVE_VALIDATION_SCOPE, QUANTITATIVE_IMPLEMENTATION)
    if _finite_machine(request):
        return ("policy_finite_machine_material", FINITE_MACHINE_PROFILE, FINITE_MACHINE_PRODUCER_PROFILE,
                FINITE_MACHINE_VALIDATION_SCOPE, FINITE_MACHINE_IMPLEMENTATION)
    if _grounded_helper(request):
        return ("policy_grounded_helper_material", GROUNDED_HELPER_PROFILE, GROUNDED_HELPER_PRODUCER_PROFILE,
                GROUNDED_HELPER_VALIDATION_SCOPE, GROUNDED_HELPER_IMPLEMENTATION)
    if _multi_member(request):
        return ("policy_multi_member_material", MULTI_MEMBER_PROFILE, MULTI_MEMBER_PRODUCER_PROFILE,
                MULTI_MEMBER_VALIDATION_SCOPE, MULTI_MEMBER_IMPLEMENTATION)
    if _two_observations(request):
        return ("policy_two_observation_material", TWO_OBSERVATION_PROFILE, TWO_OBSERVATION_PRODUCER_PROFILE,
                TWO_OBSERVATION_VALIDATION_SCOPE, TWO_OBSERVATION_IMPLEMENTATION)
    if _prerequisites(request):
        return ("policy_prerequisite_material", PREREQUISITE_PROFILE, PREREQUISITE_PRODUCER_PROFILE,
                PREREQUISITE_VALIDATION_SCOPE, PREREQUISITE_IMPLEMENTATION)
    if _instanced(request):
        return ("policy_instance_material", INSTANCE_PROFILE, INSTANCE_PRODUCER_PROFILE,
                INSTANCE_VALIDATION_SCOPE, INSTANCE_IMPLEMENTATION)
    return "policy_component_material", PROFILE, PRODUCER_PROFILE, VALIDATION_SCOPE, IMPLEMENTATION


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
    instanced = _instanced(request)
    multi_member = _multi_member(request)
    rule = _record(_record(request["composition_rule"], "Original rule").get("body"), "Original rule body")
    library = _rows(_record(request["component_library"], "Original library").get("components"), "Original components")
    components: dict[str, dict[str, JsonValue]] = {}
    for row in _rows(rule.get("components"), "Original component selections"):
        slot = row.get("slot")
        if type(slot) is not str or slot in components:
            raise CoreProtocolError("Original component selection has ambiguous slots")
        components[slot] = _record(_unique(library, "identity", row.get("component"), "Selected component").get("body"), "Component body")
    if multi_member and len(components) != 2:
        raise CoreProtocolError("Multi-member evidence requires exactly two original instances")
    if (not instanced and list(components) != ["decision", "driver"]
            or instanced and (not 2 <= len(components) <= 8 or any(slot in ("decision", "driver") for slot in components))):
        raise CoreProtocolError("Component evidence changed its original bounded instance inventory" if instanced
                                    else "Component evidence changed its closed two-component inventory")
    roots = _rows(rule.get("root_bindings"), "Original root bindings")
    authority = _record(rule.get("material_authority"), "Original material authority")
    member_order = authority.get("member_order")
    if type(member_order) is not list or len(member_order) != (3 if _grounded_helper(request) else 2 if multi_member else 1):
        raise CoreProtocolError("Component evidence lacks its single original member")
    passed = leaf["outcome"] == "pass"
    construction = _record(candidate["construction"], "Construction")
    inventory = _record(construction.get("inventory"), "Checked inventory") if passed else {}
    molecules = _rows(inventory.get("molecules"), "Checked molecules") if passed else []
    member_bindings = _rows(rule.get("member_bindings"), "Original member bindings") if multi_member else []

    def site(value: JsonValue, slot: str, original: dict[str, JsonValue]) -> None:
        row = _object(value, {"slot", "root", "source", "feature", "local_path", "member", "path"}
                      | ({"final_feature"} if instanced else set()), "Retained carrier site")
        member = _unique(member_bindings, "slot", slot, "Original member binding").get("member") if multi_member else member_order[0]
        _expect(row, {"slot": slot, "root": original.get("root"), "source": _unique(roots, "slot", slot, "Root binding").get("source"),
                      "feature": original.get("feature"), "local_path": original.get("path"), "member": member}, "Carrier projection")
        _record(row["path"], "Projected carrier path")
        final_feature = encode_json([slot, original.get("feature")]).decode("utf-8") if instanced and not multi_member else original.get("feature")
        if instanced:
            _expect(row, {"final_feature": final_feature}, "Instance-qualified feature identity")
        if passed:
            features = _rows(_unique(molecules, "id", member, "Checked member").get("features"), "Checked features")
            feature = _unique(features, "id", final_feature, "Projected final feature")
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
    join = _record(rule.get("join"), "Original join") if not instanced else {}
    joins = _rows(rule.get("joins"), "Original joins") if instanced else []
    for raw, original in zip(returned, links):
        row = _object(raw, {"link", "producer_endpoint", "consumer_endpoint", "producer", "consumer"}
                      | ({"transport"} if multi_member else {"joins", "offsets"} if instanced else {"join", "offset"}), "Retained cross-link")
        if multi_member:
            transport = _object(original.get("transport"), {"definition", "provider", "producer_member", "consumer_member"}, "Original inter-member transport")
            _expect(row, {"link": original.get("link"), "transport": transport}, "Cross-link transport/order")
        elif instanced:
            path = original.get("joins")
            if type(path) is not list or not path:
                raise CoreProtocolError("Instance cross-link lacks its original join path")
            offsets: list[JsonValue] = [_unique(joins, "id", item, "Crossed original join").get("offset") for item in path]
            _expect(row, {"link": original.get("link"), "joins": path, "offsets": offsets}, "Cross-link path/order")
        else:
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
    if _grounded_helper(request):
        helper = _object(rule.get("helper"), {"source", "member", "material"}, "Original helper selection")
        original_material = _record(helper["material"], "Original helper material")
        helper_body = _record(original_material.get("body"), "Original helper material body")
        projections = _rows(leaf["helper_projections"], "Helper projections")
        structure_checked = _record(leaf["structure"], "Helper structural evidence").get("outcome") == "pass"
        if len(projections) != (1 if structure_checked else 0):
            raise CoreProtocolError("Assembly changed the complete checked helper projection census")
        helper_molecules = _rows(_record(construction.get("inventory"), "Checked helper inventory").get("molecules"), "Checked helper molecules") if structure_checked else []
        for raw in projections:
            row = _object(raw, {"material", "source", "member", "product", "root_fingerprint", "molecule_fingerprint"}, "Helper projection")
            _expect(row, {**helper, "product": helper_body.get("product")}, "Original helper projection")
            _pin(row["root_fingerprint"], helper_body.get("root"), "Complete original helper root")
            _pin(row["molecule_fingerprint"], _unique(helper_molecules, "id", helper["member"], "Checked helper member"), "Complete helper molecule")


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


def _member_transport_inventory(request: dict[str, JsonValue], candidate: dict[str, JsonValue],
                                leaf: dict[str, JsonValue]) -> None:
    """Retain checked material/transport identities without accepting the premise."""
    rule = _record(_record(request["composition_rule"], "Original rule").get("body"), "Original rule body")
    context = _record(request["context"], "Original multi-member context")
    passed = leaf["outcome"] == "pass"
    bindings = _rows(rule.get("member_bindings"), "Original member bindings")
    placements = _rows(context.get("placements"), "Original member placements")
    retained = _rows(leaf["member_allocations"], "Checked member allocations")
    if len(bindings) != 2 or len(placements) != (3 if _grounded_helper(request) else 2) or len(retained) > 2 or passed and len(retained) != 2:
        raise CoreProtocolError("Context changed the bounded two-member allocation census")
    molecules = _rows(_record(_record(candidate["construction"], "Construction").get("inventory"), "Checked inventory").get("molecules"), "Checked molecules")
    document = _record(_record(request["implementation_request"], "Original implementation request").get("document"), "Original source")
    delivery_ref = _record(_record(document.get("deployment"), "Original deployment").get("delivery"), "Original delivery").get("contract")
    providers = _rows(context.get("providers"), "Original transport providers")
    delivery_matches = [provider for provider in providers if _same(_record(provider.get("body"), "Provider body").get("definition"), delivery_ref)]
    delivery: JsonValue = None
    if retained:
        if len(delivery_matches) != 1:
            raise CoreProtocolError("Member allocation lacks its original shared delivery provider")
        delivery_provider = delivery_matches[0]
        delivery = {"definition": delivery_ref, "provider": delivery_provider.get("identity"), "body": delivery_provider.get("body")}
    for supplied, placement, raw in zip(bindings, placements, retained):
        row = _object(raw, {"slot", "source", "member", "placement", "molecule_fingerprint", "delivery"}, "Member allocation")
        _expect(row, {key: supplied.get(key) for key in ("slot", "source", "member")}, "Member allocation identity/order")
        _expect(row, {"placement": placement, "delivery": delivery}, "Original member placement and shared delivery")
        if placement.get("member_id") != supplied.get("member"):
            raise CoreProtocolError("Checked placement changed its original member owner")
        _pin(row["molecule_fingerprint"], _unique(molecules, "id", supplied.get("member"), "Checked member"), "Complete allocated molecule")
    links = _rows(rule.get("links"), "Original links")
    carriers = _rows(rule.get("link_carriers"), "Original link carriers")
    transports = _rows(leaf["transport_allocations"], "Checked inter-member transports")
    if len(transports) > len(carriers) or passed and len(transports) != len(carriers):
        raise CoreProtocolError("Context changed the complete transport allocation census")
    providers = _rows(context.get("providers"), "Original transport providers")
    for supplied, raw in zip(carriers, transports):
        row = _object(raw, {"link", "producer_member", "consumer_member", "provider", "definition", "signal_type", "scope",
                            "transport_profile", "phase_profile", "available"}, "Transport allocation")
        transport = _object(supplied.get("transport"), {"definition", "provider", "producer_member", "consumer_member"}, "Original transport")
        link = _unique(links, "id", supplied.get("link"), "Original link")
        provider = _unique(providers, "identity", transport["provider"], "Original transport provider")
        body = _record(provider.get("body"), "Original transport body")
        _expect(body, {"kind": "transport", "definition": transport["definition"]}, "Transport body identity")
        _expect(row, {"link": supplied.get("link"), **transport,
                      "signal_type": link.get("signal_type"), "scope": link.get("scope"),
                      "transport_profile": "biocompiler.policy_complete_signal_identity_transport.v0.1",
                      "phase_profile": "biocompiler.policy_staged_primitive_execution.v0.1",
                      "available": body.get("availability")}, "Original transport allocation")
        for side in ("producer", "consumer"):
            endpoint = _record(link.get(side), "Original link endpoint")
            member = _unique(bindings, "slot", endpoint.get("slot"), "Transport member owner")
            if row[side + "_member"] != member.get("member"):
                raise CoreProtocolError("Transport changed the original endpoint member owner")


def _helper_inventory(request: dict[str, JsonValue], candidate: dict[str, JsonValue], leaf: dict[str, JsonValue]) -> None:
    """Bind helper receipts to original material, owners and provider bodies."""
    rows = _rows(leaf["helper_allocations"], "Checked helper allocations")
    if len(rows) != (1 if leaf["outcome"] == "pass" else 0):
        raise CoreProtocolError("Context changed the complete checked helper allocation census")
    if not rows:
        return
    rule = _record(_record(request["composition_rule"], "Original rule").get("body"), "Original rule body")
    selection = _object(rule.get("helper"), {"source", "member", "material"}, "Original helper selection")
    original_material = _record(selection["material"], "Original helper material")
    material_body = _record(original_material.get("body"), "Original helper material body")
    context = _record(request["context"], "Original helper context")
    helpers = _rows(context.get("helpers"), "Original helpers")
    placements = _rows(context.get("placements"), "Original placements")
    if len(helpers) != 1 or len(placements) != 3:
        raise CoreProtocolError("Helper evidence lost the original one-helper three-placement inventory")
    placement = placements[2]
    if placement.get("member_id") != selection["member"]:
        raise CoreProtocolError("Helper evidence changed its original member placement")
    providers = _rows(context.get("providers"), "Original helper providers")
    matches = [row for row in providers if _same(_record(row.get("body"), "Provider body").get("definition"), material_body.get("capability"))]
    if len(matches) != 1:
        raise CoreProtocolError("Helper evidence lacks its exact original capability provider")
    provider = matches[0]
    body = _record(provider.get("body"), "Original helper provider body")
    _expect(body, {"kind": "helper", "material": original_material.get("identity")}, "Original helper material provider")
    document = _record(_record(request["implementation_request"], "Original implementation request").get("document"), "Original source")
    delivery_ref = _record(_record(document.get("deployment"), "Original deployment").get("delivery"), "Original delivery").get("contract")
    delivery_matches = [row for row in providers if _same(_record(row.get("body"), "Provider body").get("definition"), delivery_ref)]
    if len(delivery_matches) != 1:
        raise CoreProtocolError("Helper evidence lacks its original shared delivery provider")
    delivery = delivery_matches[0]
    resources = [row for row in _rows(leaf["resource_allocations"], "Checked resources") if _same(row.get("provider"), material_body.get("capability"))]
    consumers: list[JsonValue] = []
    slots = [row.get("slot") for row in _rows(rule.get("components"), "Original instances")]
    for resource in resources:
        demand = _record(resource.get("demand"), "Helper resource demand")
        owner = _object(demand.get("owner"), {"kind", "slot", "node"}, "Qualified helper resource owner")
        if owner["kind"] != "node" or owner["slot"] not in slots:
            raise CoreProtocolError("Helper allocation lost its original named instance owner")
        if owner["slot"] not in consumers:
            consumers.append(owner["slot"])
    if not resources:
        raise CoreProtocolError("Helper allocation lacks the complete original resource consumers")
    row = _object(rows[0], {"helper", "material", "capability", "source", "member", "placement", "molecule_fingerprint",
                            "provider", "provider_body", "bootstrap", "delivery", "consumers", "resource_allocations"}, "Checked helper allocation")
    _expect(row, {"helper": helpers[0], "material": original_material.get("identity"), "capability": material_body.get("capability"),
                  "source": selection["source"], "member": selection["member"], "placement": placement,
                  "provider": provider.get("identity"), "provider_body": body, "bootstrap": body.get("bootstrap"),
                  "delivery": {"definition": delivery_ref, "provider": delivery.get("identity"), "body": delivery.get("body")},
                  "consumers": consumers, "resource_allocations": [cast(JsonValue, value) for value in resources]}, "Original complete helper allocation")
    molecules = _rows(_record(_record(candidate["construction"], "Construction").get("inventory"), "Checked inventory").get("molecules"), "Checked molecules")
    _pin(row["molecule_fingerprint"], _unique(molecules, "id", selection["member"], "Checked helper member"), "Complete allocated helper molecule")


def _prerequisite_evidence(request: dict[str, JsonValue], report: dict[str, JsonValue]) -> None:
    """Bind native closure evidence to original inventories; prove no predicates."""
    from biocompiler.core_policy import _semantic

    multi_member = _multi_member(request)
    grounded_helper = _grounded_helper(request)
    raw, contextual = report["prerequisites"], report["context"]
    if contextual is None:
        if raw is not None or report["prerequisite_status"] != "unassessed":
            raise CoreProtocolError("Prerequisites bypassed the required context stage")
        return
    context_report = _record(contextual, "Prerequisite context")
    if not _same(raw, context_report.get("prerequisite_closure")):
        raise CoreProtocolError("Material and context retained different prerequisite closures")
    closure = _object(raw, {"schema_version", "profile", "status", "complete", "original_request_fingerprint",
        "assembly_fingerprint", "source_catalog", "pending_dependencies", "instances", "local_requirements", "providers",
        "graph", "operating_domain_fingerprint", "clock", "recipient", "input_allocations", "resource_allocations",
        "diagnostics", "empirical"} | ({"member_allocations", "transport_allocations"} if multi_member else set())
        | ({"helper_allocations"} if grounded_helper else set()), "Complete prerequisite closure")
    status = context_report["outcome"]
    _expect(closure, {"schema_version": "biocompiler.policy_provider_prerequisite_closure.v0.3" if grounded_helper else "biocompiler.policy_provider_prerequisite_closure.v0.2" if multi_member else "biocompiler.policy_provider_prerequisite_closure.v0.1",
        "profile": request["profile"], "status": status, "complete": status == "pass",
        "diagnostics": context_report["diagnostics"], "empirical": "unassessed"}, "Prerequisite scope")
    if report["prerequisite_status"] != status:
        raise CoreProtocolError("Prerequisite status contradicts the complete checked context")
    original = (implementation._coupled_original if _composition(request) else implementation._multi_site_original if _multi_site(request) else implementation._network_original if _network(request) else implementation._finite_machine_original if _finite_machine(request) else implementation._multi_product_original if multi_member else implementation._two_observation_original if _two_observations(request) else
                implementation._prerequisite_original)(request["implementation_request"])
    document = _record(original["document"], "Original prerequisite source")
    context = _record(request["context"], "Original prerequisite context")
    rule = _record(_record(request["composition_rule"], "Original rule").get("body"), "Original rule body")
    pending = implementation._pending_dependencies(original)
    _expect(closure, {"source_catalog": document.get("implementations"), "pending_dependencies": pending,
        "instances": rule.get("components"), "clock": context.get("clock"), "recipient": context.get("recipient"),
        "resource_allocations": context_report["resource_allocations"]}, "Prerequisite original inventories")
    if multi_member:
        for key in ("member_allocations", "transport_allocations") + (("helper_allocations",) if grounded_helper else ()):
            if not _same(closure[key], context_report.get(key)):
                raise CoreProtocolError("Closure changed the checked member or transport allocations")
            _rows(closure[key], "Checked " + key)
    _pin(closure["original_request_fingerprint"], request, "Prerequisite request")
    _pin(closure["assembly_fingerprint"], report["assembly"], "Prerequisite assembly")
    _pin(closure["operating_domain_fingerprint"], original["operating_domain"], "Prerequisite domain")
    library = _rows(_record(request["component_library"], "Original component library").get("components"), "Original components")
    expected_requirements: list[JsonValue] = []
    for instance in _rows(rule.get("components"), "Original instances"):
        component = _unique(library, "identity", instance.get("component"), "Original prerequisite component")
        body = _record(component.get("body"), "Original component body")
        expected_requirements.append({"slot": instance.get("slot"), "component": instance.get("component"),
                                      "requirements": body.get("provider_requirements")})
    if not _same(closure["local_requirements"], expected_requirements):
        raise CoreProtocolError("Closure lost or aliased a qualified local prerequisite owner")
    providers = _rows(context.get("providers"), "Original closure providers")
    retained = _rows(closure["providers"], "Retained complete providers")
    if len(providers) != len(retained):
        raise CoreProtocolError("Closure changed the original provider census")
    bodies = [_record(provider.get("body"), "Original provider body") for provider in providers]
    for supplied, body, value in zip(providers, bodies, retained):
        row = _object(value, {"definition", "identity", "body_fingerprint"}, "Pinned prerequisite provider")
        _expect(row, {"definition": body.get("definition"), "identity": supplied.get("identity")}, "Original provider identity")
        _pin(row["body_fingerprint"], body, "Complete original provider body")
    bindings = _rows(request["input_bindings"], "Original input bindings")
    allocations = _rows(closure["input_allocations"], "Checked prerequisite inputs")
    if len(allocations) > len(bindings) or status == "pass" and len(allocations) != len(bindings):
        raise CoreProtocolError("Closure changed the complete input allocation inventory")
    for binding, value in zip(bindings, allocations):
        provider = _unique(bodies, "definition", binding.get("provider"), "Input provider")
        channel = _unique(_rows(provider.get("channels"), "Original interface channels"), "id", binding.get("channel"), "Input channel")
        expected: JsonValue = {"input": binding.get("input"), "source": binding.get("source"),
            "provider": binding.get("provider"), "channel": binding.get("channel"), "kind": channel.get("kind"),
            "observer": channel.get("observer"), "subject": channel.get("subject"), "available": channel.get("availability")}
        if not _same(value, expected):
            raise CoreProtocolError("Closure changed an original input allocation")
    graph = _object(closure["graph"], {"schema_version", "pending_dependencies", "roots", "nodes", "edges", "issues"}, "Original provider dependency graph")
    _expect(graph, {"schema_version": "biocompiler.policy_provider_dependency_graph.v0.3" if grounded_helper else "biocompiler.policy_provider_dependency_graph.v0.2" if multi_member else "biocompiler.policy_provider_dependency_graph.v0.1", "pending_dependencies": pending}, "Provider graph authority")
    program = _record(document.get("program"), "Original prerequisite program")
    definitions = _rows(_record(program.get("semantics"), "Original semantics").get("definitions"), "Original definitions")

    def reference(value: JsonValue) -> None:
        row = _object(value, {"$type", "id", "version", "digest"}, "Original provider DefinitionRef")
        definition = _unique(definitions, "id", row["id"], "Original provider definition")
        _expect(row, {"$type": "DefinitionRef", "version": definition.get("version")}, "Provider definition identity")
        # Match the source's identity convention: provenance and source maps are
        # retained in the request but do not contribute to a DefinitionRef pin.
        _pin(row["digest"], _semantic(definition), "Original provider definition body")

    expected_roots: list[JsonValue] = []

    def source_root(path: str, value: JsonValue) -> None:
        reference(value)
        expected_roots.append({"origin": {"kind": "source", "path": path}, "definition": value})

    def source_rows(path: str, value: JsonValue) -> None:
        for index, row in enumerate(_rows(value, "Original provider roots")):
            source_root(path + "/" + str(index), row)

    deployment = _record(document.get("deployment"), "Original prerequisite deployment")
    for index, binding in enumerate(_rows(deployment.get("bindings"), "Original chassis bindings")):
        chassis = _record(binding.get("chassis"), "Original chassis")
        path = "/deployment/bindings/" + str(index) + "/chassis"
        source_root(path + "/operational_model", chassis.get("operational_model"))
        for key in ("capabilities", "interfaces", "environment"):
            source_rows(path + "/" + key, chassis.get(key))
    source_rows("/deployment/environment", deployment.get("environment"))
    for index, declaration in enumerate(_rows(program.get("declarations"), "Original declarations")):
        if declaration.get("$type") == "Role":
            source_rows("/program/declarations/" + str(index) + "/requires", declaration.get("requires"))
    delivery = _record(deployment.get("delivery"), "Original delivery")
    for key in ("arrival", "expression", "activation", "contract"):
        source_root("/deployment/delivery/" + key, delivery.get(key))
    for value in _rows(pending, "Original pending dependencies"):
        reference(value["definition"])
        expected_roots.append({"origin": {"kind": "catalog_dependency", **{
            key: value[key] for key in ("entry_id", "entry_digest", "dependency_index")}}, "definition": value["definition"]})
    if not _same(graph["roots"], expected_roots):
        raise CoreProtocolError("Provider graph changed an original source or catalog root occurrence")
    for body in bodies:
        reference(body.get("definition"))
    nodes = [_object(row, {"definition", "provider"}, "Provider dependency node") for row in _rows(graph["nodes"], "Provider nodes")]
    for node in nodes:
        reference(node["definition"])
    node_keys = [encode_json(row["definition"]) for row in nodes]
    if len(set(node_keys)) != len(node_keys):
        raise CoreProtocolError("Provider graph duplicated a definition identity")
    if any(encode_json(_record(root, "Provider root")["definition"]) not in node_keys for root in expected_roots):
        raise CoreProtocolError("Provider graph omitted an original root definition")
    expected_edges: list[JsonValue] = []
    for node in nodes:
        matched = [(provider, body) for provider, body in zip(providers, bodies) if _same(body.get("definition"), node["definition"])]
        if not matched:
            if node["provider"] is not None:
                raise CoreProtocolError("Absent provider acquired a body identity")
            continue
        if len(matched) != 1 or not _same(node["provider"], matched[0][0].get("identity")):
            raise CoreProtocolError("Provider graph changed an original body pin")
        body = matched[0][1]
        outgoing: list[tuple[str, list[JsonValue]]] = []
        if body.get("kind") == "interface":
            outgoing = [("interface_environment", [body.get("environment")])]
        elif body.get("kind") == "transport" and multi_member:
            outgoing = [("transport_environment", [body.get("environment")])]
        elif body.get("kind") == "helper" and grounded_helper:
            outgoing = [("helper_environment", [body.get("environment")]), ("helper_delivery", [body.get("delivery")])]
        elif body.get("kind") == "chassis":
            chassis = _record(body.get("chassis"), "Original chassis")
            for key, relation in (("capabilities", "chassis_capability"), ("interfaces", "chassis_interface"), ("environment", "chassis_environment")):
                refs = _rows(chassis.get(key), "Original chassis references")
                outgoing.append((relation, list(refs)))
        for relation, targets in outgoing:
            for index, target in enumerate(targets):
                reference(target)
                if encode_json(target) not in node_keys:
                    raise CoreProtocolError("Provider graph omitted an original dependency target")
                expected_edges.append({"source": node["definition"], "relation": relation, "index": index, "target": target})
    edges = _rows(graph["edges"], "Original provider edges")
    # Bind every retained edge occurrence to its original field/index. Their DFS
    # ordering and actual closure/cycle interpretation remain native authority.
    if sorted(encode_json(row) for row in edges) != sorted(encode_json(row) for row in expected_edges):
        raise CoreProtocolError("Provider graph changed an original dependency occurrence")
    issues = _rows(graph["issues"], "Provider graph diagnostics")
    issue_codes = {"missing": "prerequisite_provider_missing", "cycle": "prerequisite_cycle",
                   "extra": "prerequisite_provider_extra", "unsupported": "prerequisite_definition_unsupported"}
    for value in issues:
        row = _object(value, {"kind", "code", "references"}, "Provider graph issue")
        if type(row["kind"]) is not str or issue_codes.get(row["kind"]) != row["code"]:
            raise CoreProtocolError("Unknown provider graph issue kind")
        references = _rows(row["references"], "Provider issue references")
        if not references:
            raise CoreProtocolError("Provider graph issue omitted its original references")
        for value in references:
            reference(value)
    if status == "pass" and (issues or any(row["provider"] is None for row in nodes)
            or set(node_keys) != {encode_json(body.get("definition")) for body in bodies}):
        raise CoreProtocolError("Complete closure omitted an original provider or retained an unresolved graph issue")


def _leaves(request: dict[str, JsonValue], candidate: dict[str, JsonValue], report: dict[str, JsonValue]) -> None:
    rule = _record(request["composition_rule"], "Original rule")
    body = _record(rule.get("body"), "Original rule body")
    instanced = _instanced(request)
    prerequisites = _prerequisites(request)
    multi_member = _multi_member(request)
    grounded_helper = _grounded_helper(request)
    multi_site = _multi_site(request)
    assembly, context = report["assembly"], report["context"]
    if assembly is not None:
        leaf = _object(assembly, {"schema_version", "checker_version", "profile", "original_fingerprint", "components_fingerprint",
            "rule_fingerprint", "implementation_fingerprint", "proposed_fingerprint", "candidate_fingerprint", "outcome", "diagnostics",
            "claim_scope", "premise", "structure", "carrier_projections", "link_projections", "preservation_evidence_fingerprint",
            "catalog_authorization", "context", "resource_capacity", "input_compatibility", "source_obligation_discharge", "empirical", "artifact", "export"}
            | ({"helper_projections"} if grounded_helper else set()), "Assembly evidence")
        _expect(leaf, {"schema_version": "biocompiler.policy_component_assembly_assessment.v0.1",
            "checker_version": "biocompiler.ocaml.policy_component_assembly_check.v0.5" if multi_site else "biocompiler.ocaml.policy_component_assembly_check.v0.4" if grounded_helper else "biocompiler.ocaml.policy_component_assembly_check.v0.3" if multi_member else "biocompiler.ocaml.policy_component_assembly_check.v0.2" if instanced else "biocompiler.ocaml.policy_component_assembly_check.v0.1",
            "profile": MULTI_SITE_ASSEMBLY_PROFILE if multi_site else GROUNDED_HELPER_ASSEMBLY_PROFILE if grounded_helper else MULTI_MEMBER_ASSEMBLY_PROFILE if multi_member else INSTANCE_ASSEMBLY_PROFILE if instanced else "biocompiler.policy_exact_component_assembly.v0.1",
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
        allowed_contexts = ((FINITE_MACHINE_REQUEST_PROFILE,) if _quantitative(request) else (request["profile"],) if prerequisites else
                            (INSTANCE_REQUEST_PROFILE, "biocompiler.policy_instance_staged_component_mrna.v0.1") if instanced
                            else (REQUEST_PROFILE, "biocompiler.policy_staged_component_mrna.v0.1"))
        if context_profile not in allowed_contexts:
            raise CoreProtocolError("Original component context has an unsupported profile")
        leaf = _object(context, {"schema_version", "profile", "implementation_version", "request_fingerprint", "context_fingerprint", "assembly_fingerprint",
            "outcome", "claim_scope", "record_layout", "minimum_record_layout", "derived_demands", "resource_allocations", "source_obligations", "discharges",
            "diagnostics", "source_receipt_status", "biological_validity", "human_use", "artifact", "export"}
            | ({"prerequisite_closure"} if prerequisites else set())
            | ({"member_allocations", "transport_allocations"} if multi_member else set())
            | ({"helper_allocations"} if grounded_helper else set()), "Component context evidence")
        _expect(leaf, {"schema_version": "biocompiler.policy_component_context_assessment.v0.3" if grounded_helper else "biocompiler.policy_component_context_assessment.v0.2" if multi_member else "biocompiler.policy_component_context_assessment.v0.1", "profile": context_profile,
            "implementation_version": "biocompiler.ocaml.policy_component_context_check.v0.9" if _multi_site(request) else "biocompiler.ocaml.policy_component_context_check.v0.8" if _network(request) else "biocompiler.ocaml.policy_component_context_check.v0.7" if _finite_machine(request) else "biocompiler.ocaml.policy_component_context_check.v0.6" if grounded_helper else "biocompiler.ocaml.policy_component_context_check.v0.5" if multi_member else
            "biocompiler.ocaml.policy_component_context_check.v0.4" if _two_observations(request) else
            "biocompiler.ocaml.policy_component_context_check.v0.3" if prerequisites else
            "biocompiler.ocaml.policy_component_context_check.v0.2" if instanced else "biocompiler.ocaml.policy_component_context_check.v0.1", "claim_scope": "conditional_component_context_and_complete_record_capacity",
            "source_receipt_status": "unchanged", "biological_validity": "unassessed", "human_use": "unassessed", "artifact": "withheld", "export": "withheld"}, "Context evidence")
        for key, original in (("request_fingerprint", request), ("context_fingerprint", request["context"]), ("assembly_fingerprint", assembly)):
            _pin(leaf[key], original, key)
        _context_inventory(request, report, leaf)
        if multi_member:
            _member_transport_inventory(request, candidate, leaf)
        if grounded_helper:
            _helper_inventory(request, candidate, leaf)
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

    @property
    def result(self) -> dict[str, JsonValue]:
        return _stored_result(self._result_json)


def _candidate(value: JsonValue, *, instanced: bool = False, multi_member: bool = False,
               grounded_helper: bool = False, multi_site: bool = False) -> dict[str, JsonValue]:
    if multi_site and (not instanced or multi_member or grounded_helper):
        raise CoreProtocolError("Multiple-site proposal requires its distinct named-instance route")
    if grounded_helper and not (instanced and multi_member):
        raise CoreProtocolError("Grounded helper proposal requires its explicit named-instance multi-member route")
    candidate = _object(value, _CANDIDATE_FIELDS, "Complete component candidate")
    if candidate["schema_version"] != CANDIDATE_SCHEMA:
        raise CoreProtocolError("Component checking changed the complete supplied candidate")
    proposal = _object(candidate["assembly_proposal"], {"schema_version", "profile", "rule", "nodes"}, "Assembly proposal")
    _expect(proposal, {"schema_version": "biocompiler.policy_component_assembly_proposal.v0.5" if multi_site else "biocompiler.policy_component_assembly_proposal.v0.4" if grounded_helper else "biocompiler.policy_component_assembly_proposal.v0.3" if multi_member else "biocompiler.policy_component_assembly_proposal.v0.2" if instanced else "biocompiler.policy_component_assembly_proposal.v0.1",
                      "profile": MULTI_SITE_ASSEMBLY_PROFILE if multi_site else GROUNDED_HELPER_ASSEMBLY_PROFILE if grounded_helper else MULTI_MEMBER_ASSEMBLY_PROFILE if multi_member else INSTANCE_ASSEMBLY_PROFILE if instanced else "biocompiler.policy_exact_component_assembly.v0.1"}, "Assembly proposal")
    return candidate


def _report(value: JsonValue, *, instanced: bool = False, prerequisites: bool = False,
            two_observations: bool = False, multi_member: bool = False,
            grounded_helper: bool = False, finite_machine: bool = False, quantitative: bool = False, network: bool = False, multi_site: bool = False, transfer_pair: bool = False, transfer_network: bool = False, composition: bool = False) -> dict[str, JsonValue]:
    if transfer_network and (not multi_site or transfer_pair):
        raise CoreProtocolError("Transfer network assessment requires its distinct multiple-site route")
    if transfer_pair and not multi_site:
        raise CoreProtocolError("Transfer-pair assessment requires its explicit multiple-site quantitative route")
    if multi_site and (not (finite_machine and quantitative) or network):
        raise CoreProtocolError("Step quantitative assessment requires its explicit multiple-site route")
    if network and (not (instanced and prerequisites) or finite_machine or quantitative or two_observations or multi_member or grounded_helper):
        raise CoreProtocolError("Network assessment requires its distinct prerequisite route")
    if quantitative and not finite_machine:
        raise CoreProtocolError("Quantitative assessment requires the explicit finite-machine backing profile")
    if finite_machine and (not (instanced and prerequisites) or two_observations or multi_member or grounded_helper):
        raise CoreProtocolError("Finite-machine assessment requires its distinct prerequisite route")
    if grounded_helper and not multi_member:
        raise CoreProtocolError("Grounded helper assessment requires its explicit multi-member route")
    if multi_member and (not (instanced and prerequisites) or two_observations):
        raise CoreProtocolError("Multi-member assessment requires its distinct named-instance prerequisite route")
    if two_observations and not (instanced and prerequisites):
        raise CoreProtocolError("Two-observation assessment requires the named-instance prerequisite route")
    report = _object(value, _REPORT_FIELDS | ({"prerequisites", "prerequisite_status"} if prerequisites else set())
                     | ({"quantitative", "quantitative_status"} if quantitative else set()), "Complete component assessment")
    _expect(report, {"schema_version": "biocompiler.policy_component_material_assessment.v0.9" if composition else "biocompiler.policy_component_material_assessment.v0.8" if transfer_network else "biocompiler.policy_component_material_assessment.v0.7" if transfer_pair else "biocompiler.policy_component_material_assessment.v0.6" if multi_site else "biocompiler.policy_component_material_assessment.v0.5" if quantitative else "biocompiler.policy_component_material_assessment.v0.4" if grounded_helper else "biocompiler.policy_component_material_assessment.v0.3" if multi_member else "biocompiler.policy_component_material_assessment.v0.2" if prerequisites else REPORT_SCHEMA,
        "profile": COMPOSITION_REQUEST_PROFILE if composition else TRANSFER_NETWORK_REQUEST_PROFILE if transfer_network else TRANSFER_PAIR_REQUEST_PROFILE if transfer_pair else STEP_QUANTITATIVE_REQUEST_PROFILE if multi_site else NETWORK_REQUEST_PROFILE if network else QUANTITATIVE_REQUEST_PROFILE if quantitative else FINITE_MACHINE_REQUEST_PROFILE if finite_machine else GROUNDED_HELPER_REQUEST_PROFILE if grounded_helper else MULTI_MEMBER_REQUEST_PROFILE if multi_member else TWO_OBSERVATION_REQUEST_PROFILE if two_observations else
        PREREQUISITE_REQUEST_PROFILE if prerequisites else INSTANCE_REQUEST_PROFILE if instanced else REQUEST_PROFILE,
        "implementation": "biocompiler.ocaml.policy_component_material_check.v0.13" if composition else "biocompiler.ocaml.policy_component_material_check.v0.12" if transfer_network else "biocompiler.ocaml.policy_component_material_check.v0.11" if transfer_pair else "biocompiler.ocaml.policy_component_material_check.v0.10" if multi_site else "biocompiler.ocaml.policy_component_material_check.v0.9" if network else "biocompiler.ocaml.policy_component_material_check.v0.8" if quantitative else "biocompiler.ocaml.policy_component_material_check.v0.7" if finite_machine else "biocompiler.ocaml.policy_component_material_check.v0.6" if grounded_helper else "biocompiler.ocaml.policy_component_material_check.v0.5" if multi_member else "biocompiler.ocaml.policy_component_material_check.v0.4" if two_observations else
        "biocompiler.ocaml.policy_component_material_check.v0.3" if prerequisites else
        "biocompiler.ocaml.policy_component_material_check.v0.2" if instanced else "biocompiler.ocaml.policy_component_material_check.v0.1", "resource_profile": RESOURCE_PROFILE,
        "claim_scope": CLAIM_SCOPE, "premise": PREMISE, "empirical": "unassessed", "artifact": "withheld", "export": "withheld"}, "Component report")
    return report


def _quantitative_evidence(request: dict[str, JsonValue], candidate: dict[str, JsonValue], report: dict[str, JsonValue]) -> None:
    """Retain quantitative report identities and source table; native checks the law."""
    step = _multi_site(request)
    composition = _composition(request)
    transfer_network = _transfer_network(request) or composition
    transfer = _transfer_pair(request) or transfer_network
    raw = report["quantitative"]
    status = report["quantitative_status"]
    if raw is None:
        if status != "unassessed" or report["status"] == ACCEPTED_STATUS:
            raise CoreProtocolError("Quantitative acceptance requires its fresh checked report")
        return
    leaf = _object(raw, {"schema_version", "profile", "implementation", "outcome", "claim_scope", "request_fingerprint",
        "mechanism_fingerprint", "selection", "source", "bindings", "table", "sampling", "issues", "usage", "empirical"} | ({"conservation"} if transfer else set()) | ({"arbitration", "ownership"} if transfer_network else set()) | ({"composition", "synchronization", "transport_scope"} if composition else set()), "Quantitative evidence")
    _expect(leaf, {"schema_version": "biocompiler.policy_quantitative_assessment.v0.5" if composition else "biocompiler.policy_quantitative_assessment.v0.4" if transfer_network else "biocompiler.policy_quantitative_assessment.v0.3" if transfer else "biocompiler.policy_quantitative_assessment.v0.2" if step else "biocompiler.policy_quantitative_assessment.v0.1",
        "profile": "biocompiler.policy_atomic_component_transfer_network.v0.1" if composition else "biocompiler.policy_sampled_reserved_transfer_network.v0.1" if transfer_network else "biocompiler.policy_sampled_conservative_transfer_pair.v0.1" if transfer else "biocompiler.policy_sampled_saturating_step_reservoir.v0.1" if step else "biocompiler.policy_sampled_saturating_reservoir.v0.1",
        "implementation": "biocompiler.ocaml.policy_quantitative_check.v0.5" if composition else "biocompiler.ocaml.policy_quantitative_check.v0.4" if transfer_network else "biocompiler.ocaml.policy_quantitative_check.v0.3" if transfer else "biocompiler.ocaml.policy_quantitative_check.v0.2" if step else "biocompiler.ocaml.policy_quantitative_check.v0.1",
        "claim_scope": "exact_atomic_component_transfer_network_under_supplied_coordination_contract" if composition else "exact_sampled_reserved_transfer_network_under_supplied_contract" if transfer_network else "exact_sampled_conservative_transfer_pair_under_supplied_contract" if transfer else "exact_sampled_step_reservoir_under_supplied_contract" if step else "exact_sampled_reservoir_under_supplied_contract", "empirical": "unassessed"}, "Quantitative evidence")
    if transfer_network:
        _expect(leaf, {"arbitration": "declared_order_prestate_reservation", "ownership": "partitioned_reservoir_storage_single_atomic_writer" if composition else "single_atomic_state_owner"}, "Network quantitative evidence")
    if leaf["outcome"] not in ("pass", "fail") or status != leaf["outcome"] or report["status"] == ACCEPTED_STATUS and status != "pass":
        raise CoreProtocolError("Quantitative stage contradicts material acceptance")
    original = _record(request["quantitative"], "Original quantitative contract")
    composed = original
    if composition:
        if not _same(leaf["composition"], original):
            raise CoreProtocolError("Composed quantitative evidence changed its complete owner authority")
        _expect(leaf, {"synchronization": "one_prestate_one_atomic_commit",
                      "transport_scope": "selected_boolean_allocation_signals_under_supplied_component_contracts"}, "Coupled evidence scope")
        original = _record(original["network"], "Original coupled network")
    mechanism = _record(original["mechanism"], "Original reservoir law")
    _pin(leaf["request_fingerprint"], request, "Quantitative complete request")
    _pin(leaf["mechanism_fingerprint"], mechanism, "Independent original quantitative law")
    for key in ("selection", "source"):
        if not _same(leaf[key], original[key]):
            raise CoreProtocolError("Quantitative evidence changed original " + key)
    sampling = _object(leaf["sampling"], {"sample_period", "max_rows_per_slot_tick", "observed_age_ticks", "no_update", "unknown", "reset", "reservation"}, "Quantitative sampling premises")
    expected_sampling: JsonValue = {"sample_period": mechanism.get("sample_period"), "max_rows_per_slot_tick": 1,
        "observed_age_ticks": 0, "no_update": "hold", "unknown": "hold_without_request", "reset": "initial", "reservation": "existing_atomic_reservation"}
    if not _same(sampling, expected_sampling):
        raise CoreProtocolError("Quantitative evidence changed its explicit sampling or reservation premises")
    usage = _object(leaf["usage"], {"unit", "charged_work"}, "Quantitative work accounting")
    budgets = _record(request["budgets"], "Original component budgets")
    if usage["unit"] != "logical_data_visits_and_exact_finite_table_work" or _count(usage["charged_work"], "Quantitative work") > _count(budgets["max_work"], "Original work maximum"):
        raise CoreProtocolError("Quantitative work exceeds its original bounds or changed units")
    issues = leaf["issues"]
    if type(issues) is not list or any(type(item) is not str or not item for item in issues):
        raise CoreProtocolError("Quantitative issues must be explicit ordered text")
    rows = _rows(leaf["table"], "Quantitative transition table")
    if status == "fail":
        if leaf["bindings"] is not None or rows or not issues or transfer and leaf["conservation"] is not None:
            raise CoreProtocolError("Failed quantitative checking must not publish partial bindings or table")
        return
    if issues:
        raise CoreProtocolError("Passing quantitative checking carries unresolved issues")
    selected = _record(original["source"], "Original quantitative source")
    binding = _record(candidate["binding"], "Checked proposed source binding")
    machine = next((row for row in _rows(binding["machines"], "Machine bindings") if row["source"] == selected["machine"]), None)
    observation = next((row for row in _rows(binding["observations"], "Observation bindings") if row["source"] == selected["observation"]), None)
    implementation_request = _record(request["implementation_request"], "Original implementation request")
    document = _record(implementation_request["document"], "Original source document")
    program = _record(document["program"], "Original source program")
    declarations = _rows(program["declarations"], "Original source declarations")
    source_machine = next((row for row in declarations if row.get("$type") == "Machine" and row.get("id") == selected["machine"]), None)
    transitions = [row for row in declarations if row.get("$type") == "Transition"]
    crossing = [row for row in transitions if row.get("effects")]
    if machine is None or observation is None or source_machine is None or not crossing or (not step and len(crossing) != 1):
        raise CoreProtocolError("Quantitative report lacks its exact source and implementation anchors")
    states = source_machine["states"]
    if type(states) is not list or not 2 <= len(states) <= 16:
        raise CoreProtocolError("Quantitative source state census is outside the bounded profile")
    commits = _rows(binding["transitions"], "Transition bindings")
    if step:
        effects = [row for row in _rows(binding["effects"], "Effect bindings") if row["source"] == selected["effect"]]
        if len(effects) != 1:
            raise CoreProtocolError("Step quantitative evidence lacks its single shared attempt bank")
        nodes = _rows(_record(candidate["implementation"], "Implementation graph")["nodes"], "Implementation nodes")
        sites: list[JsonValue] = []
        for state in states:
            ordered_crossings = list(enumerate(crossing))
            if transfer_network:
                ordered_crossings.sort(key=lambda item: _record(item[1]["when"], "Crossing guard")["op"] != "observe")
            for index, transition in ordered_crossings:
                if transition["source"] != state:
                    continue
                commit = _unique(commits, "source", transition["id"], "Crossing transition")
                node = _unique(nodes, "id", commit["commit"], "Crossing commit")
                sites.append({"transition": transition["id"], "source_state": state, "input": _record(transition["when"], "Crossing guard")["op"] == "observe" if transfer_network else True,
                    "request_endpoint": {"node": commit["commit"], "port": "request0"}, "model": node["model"],
                    "attempt_port": "request" + str(index)})
        expected_bindings: JsonValue = {"machine_bank": machine["bank"], "observation_bank": observation["bank"],
            "observation_input": observation["input"], "attempt_bank": effects[0]["bank"], "crossing_sites": sites}
    else:
        commit = _unique(commits, "source", crossing[0]["id"], "Crossing transition")
        expected_bindings = {"machine_bank": machine["bank"], "observation_bank": observation["bank"],
            "observation_input": observation["input"], "crossing_transition": crossing[0]["id"],
            "request_endpoint": {"node": commit["commit"], "port": "request0"}}
    if composition:
        graph = _record(candidate["implementation"], "Actual coupled implementation")
        actual_nodes = _rows(graph["nodes"], "Actual coupled nodes")
        rule_body = _record(_record(request["composition_rule"], "Coupled rule")["body"], "Coupled rule body")
        order = _rows(rule_body["node_order"], "Original coupled node order")
        if len(order) != len(actual_nodes):
            raise CoreProtocolError("Coupled relocation lost its complete node bijection")
        def relocate(instance: JsonValue, identity: JsonValue) -> dict[str, JsonValue]:
            matches = [node for node, local in zip(actual_nodes, order) if local["slot"] == instance and local["node"] == identity]
            if len(matches) != 1:
                raise CoreProtocolError("Coupled local endpoint does not relocate uniquely")
            return matches[0]
        components = _rows(_record(request["component_library"], "Original component library")["components"], "Components")
        def local_contract(selected: dict[str, JsonValue], role: str) -> tuple[dict[str, JsonValue], dict[str, JsonValue]]:
            matches = [component for component in components if _same(component["identity"], selected["component"])]
            if len(matches) != 1:
                raise CoreProtocolError("Coupled component pin is absent or ambiguous")
            body = _record(matches[0]["body"], "Selected component body")
            contract = _unique(_rows(body["quantitative_contracts"], "Selected contracts"), "id", selected["contract"], "Selected coupled contract")
            if contract.get("role") != role:
                raise CoreProtocolError("Coupled component role changed")
            return contract, _record(body["fragment"], "Selected local fragment")
        def boundary_endpoint(instance: JsonValue, fragment: dict[str, JsonValue], boundary: JsonValue) -> dict[str, JsonValue]:
            port = _unique(_rows(fragment["boundary_ports"], "Boundaries"), "id", boundary, "Local boundary")
            endpoint = _record(port["endpoint"], "Local endpoint")
            return {"node": relocate(instance, endpoint["node"])["id"], "port": endpoint["port"]}
        owners: list[JsonValue] = []
        for selected_owner in _rows(composed["owners"], "Original reservoir owners"):
            contract, fragment = local_contract(selected_owner, "owner")
            state = _record(contract["state"], "Owner state")
            register = relocate(selected_owner["instance"], state["node"])
            bound = _unique(_rows(binding["states"], "Original state bindings"), "source", selected_owner["state"], "Private store")
            if bound["register"] != register["id"] or not _same(register["model"], state["model"]):
                raise CoreProtocolError("Coupled owner lost its source/register/model correspondence")
            next_signal = _record(contract["next"], "Owner next signal")
            owners.append({"instance": selected_owner["instance"], "component": selected_owner["component"],
                "contract": selected_owner["contract"], "compartment": selected_owner["compartment"],
                "source_state": selected_owner["state"], "register": register["id"],
                "next": boundary_endpoint(selected_owner["instance"], fragment, next_signal["boundary"])})
        coordinator = _record(original["selection"], "Original coordinator")
        contract, fragment = local_contract(coordinator, "coordinator")
        transfers: list[JsonValue] = [{"transfer": flow["transfer"], "endpoint": boundary_endpoint(coordinator["instance"], fragment, flow["boundary"])}
            for flow in _rows(contract["flows"], "Ordered original transfer signals")]
        _record(expected_bindings, "Expected coupled bindings").update(owners=owners, transfers=transfers)
    if not _same(leaf["bindings"], expected_bindings):
        raise CoreProtocolError("Quantitative binding identities differ from the complete source-to-graph binding")
    expected_rows: list[JsonValue] = []
    for state in states:
        for truth, operation in (("true", "observe"), ("false", "not")):
            matching = [row for row in transitions if row["source"] == state and _record(row["when"], "Original guard")["op"] == operation]
            if len(matching) > 1 or not matching and not transfer:
                raise CoreProtocolError("Quantitative table requires the profile-specific complete sample guard census")
            row = matching[0] if matching else None
            expected_rows.append({"source": state, "input": truth, "destination": state if row is None else row["destination"],
                                  "request": False if row is None else bool(row["effects"])})
        expected_rows.append({"source": state, "input": "unknown", "destination": state, "request": False})
    if transfer:
        selected_component = _record(original["selection"], "Original quantitative selection")
        components = _rows(_record(request["component_library"], "Original component library")["components"], "Original components")
        matched = [value for value in components if _same(value["identity"], selected_component["component"])]
        if len(matched) != 1:
            raise CoreProtocolError("Transfer table lost its selected component")
        contracts = _rows(_record(matched[0]["body"], "Selected component body")["quantitative_contracts"], "Quantitative contracts")
        contract = _unique(contracts, "id", selected_component["contract"], "Selected quantitative contract")
        if composition:
            contract = _record(contract["network"], "Selected coordinator network")
        vectors = _rows(_record(contract["state"], "Selected local state")["values"], "Complete Cartesian map")
        if not _same([value["state"] for value in vectors], states):
            raise CoreProtocolError("Transfer table lost the complete original state order")
        if transfer_network:
            def exact_quantity(value: JsonValue) -> Fraction:
                quantity = _object(value, {"$type", "amount", "unit"}, "Original network Quantity")
                text = quantity["amount"]
                if quantity["$type"] != "Quantity" or not _same(quantity["unit"], mechanism.get("unit")) or type(text) is not str or len(text) > 256:
                    raise CoreProtocolError("Network quantity lost its exact bounded decimal or complete unit")
                match = re.fullmatch(r"(-?)(0|[1-9][0-9]*)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?", text)
                if match is None:
                    raise CoreProtocolError("Network quantity is outside the exact finite decimal grammar")
                sign, whole, fraction, exponent = match.groups()
                places = int(exponent or "0") - len(fraction or "")
                if abs(places) > 1024:
                    raise CoreProtocolError("Network quantity exceeds the exact decimal exponent bound")
                return Fraction(int(sign + whole + (fraction or ""))) * Fraction(10) ** places
            quantum = exact_quantity(mechanism.get("quantum"))
            if quantum <= 0:
                raise CoreProtocolError("Network quantum must be positive")
            def quanta(value: JsonValue) -> int:
                amount = exact_quantity(value) / quantum
                if amount.denominator != 1 or amount < 0:
                    raise CoreProtocolError("Network quantity is not an exact nonnegative grid amount")
                return amount.numerator
            reservoirs = _rows(mechanism.get("reservoirs"), "Original ordered reservoirs")
            edges = _rows(mechanism.get("transfers"), "Original ordered transfers")
            names = [value["compartment"] for value in reservoirs]
            capacities = [quanta(value["capacity"]) for value in reservoirs]
            if not 2 <= len(names) <= 4 or any(type(name) is not str for name in names) or len(set(cast(list[str], names))) != len(names):
                raise CoreProtocolError("Network reservoirs require distinct bounded identities")
            widths = [capacity + 1 for capacity in capacities]
            product = 1
            for width in widths:
                product *= width
            if any(width < 2 for width in widths) or product != len(states) or len(rows) != len(expected_rows):
                raise CoreProtocolError("Network state map or report lost its complete Cartesian grid")
            if not 1 <= len(edges) <= 8 or any(type(edge["id"]) is not str for edge in edges) or len({cast(str, edge["id"]) for edge in edges}) != len(edges):
                raise CoreProtocolError("Network transfers require a complete ordered identity census")
            edge_bounds = []
            for edge in edges:
                if edge["source"] not in names or edge["destination"] not in names or edge["source"] == edge["destination"] or type(edge["when"]) is not bool:
                    raise CoreProtocolError("Network transfers require declared distinct endpoints and an exact Boolean sample")
                source, destination = names.index(edge["source"]), names.index(edge["destination"])
                amount = quanta(edge["amount"])
                if not 0 < amount <= capacities[source]:
                    raise CoreProtocolError("Network transfer amount exceeds its donor grid capacity")
                edge_bounds.append((source, destination, amount, edge["when"]))
            def coordinates(state: JsonValue) -> list[int]:
                ordinal = states.index(state)
                result: list[int] = []
                for width in reversed(widths):
                    result.insert(0, ordinal % width)
                    ordinal //= width
                return result
            for vector in vectors:
                amounts = vector.get("amounts")
                if type(amounts) is not list or [quanta(value) for value in amounts] != coordinates(vector["state"]):
                    raise CoreProtocolError("Network local state map changed its exact ordered quantity coordinates")
            for expected, actual in zip(expected_rows, rows):
                row = _record(expected, "Expected network source row")
                before, after = coordinates(row["source"]), coordinates(row["destination"])
                outgoing, incoming = [0] * len(names), [0] * len(names)
                expected_flows: list[JsonValue] = []
                for edge, (source, destination, maximum, enabled) in zip(edges, edge_bounds):
                    amount = (min(maximum, before[source] - outgoing[source], capacities[destination] - before[destination] - incoming[destination])
                              if row["input"] != "unknown" and enabled == (row["input"] == "true") else 0)
                    outgoing[source] += amount
                    incoming[destination] += amount
                    expected_flows.append({"transfer": edge["id"], "quanta": amount})
                if not _same(actual.get("flows"), expected_flows):
                    raise CoreProtocolError("Network retained flows differ from the original ordered prestate reservations")
                declared = any(value["source"] == row["source"] and _record(value["when"], "Original guard")["op"] ==
                               ("observe" if row["input"] == "true" else "not") for value in transitions) if row["input"] != "unknown" else False
                if after != [amount - out + inc for amount, out, inc in zip(before, outgoing, incoming)] or declared != any(outgoing):
                    raise CoreProtocolError("Network reservations or sparse source transition contradict the retained row")
                row.update(before=cast(JsonValue, before), after=cast(JsonValue, after), flows=expected_flows)
        else:
            width = len({encode_json(value["destination"]) for value in vectors})
            if width < 2 or len(states) % width != 0 or len(states) // width < 2:
                raise CoreProtocolError("Transfer state map is not a bounded two-dimensional Cartesian grid")
            for expected in expected_rows:
                row = _record(expected, "Expected source row")
                before_index = states.index(row["source"])
                after_index = states.index(row["destination"])
                before = [before_index // width, before_index % width]
                after = [after_index // width, after_index % width]
                if sum(before) != sum(after):
                    raise CoreProtocolError("Transfer report source table contradicts its conservation claim")
                row.update(before=cast(JsonValue, before), after=cast(JsonValue, after), transfer_quanta=abs(after[0] - before[0]))
        expected_conservation: JsonValue = {"scope": "accepted_samples_within_encounter_generation",
            "quantity": "sum_all_reservoirs" if transfer_network else "source_plus_destination",
            "reset": "restore_declared_initial_vector" if transfer_network else "restore_declared_initial_pair", "checked_rows": len(expected_rows)}
        if not _same(leaf["conservation"], expected_conservation):
            raise CoreProtocolError("Transfer conservation changed its exact checked scope or complete row census")
    if not _same(cast(JsonValue, rows), expected_rows):
        raise CoreProtocolError("Quantitative table differs from the complete ordered original source transitions")


def _assessment(response: CoreResponse, request: dict[str, JsonValue], candidate: dict[str, JsonValue],
                report: dict[str, JsonValue], limits: JsonValue) -> None:
    """Check an actual nested assessment, without constructing a child response."""
    invocation: JsonValue = {"request": request, "candidate": candidate, "limits": limits}
    pin = _document_pin if _composition(request) else _pin
    if _composition(request):
        budgets = _record(request["budgets"], "Original component budgets")
        material._publication(report, _count(budgets.get("max_report_bytes"), "Original report byte ceiling"),
                              _count(budgets.get("max_report_nodes"), "Original report node ceiling"))
    for key, original in (("request_fingerprint", request), ("candidate_fingerprint", candidate), ("invocation_fingerprint", invocation)):
        pin(report[key], original, key)
    if not _same(report["limits"], limits) or not _same(report["budgets"], request["budgets"]):
        raise CoreProtocolError("Component checking changed original budgets or preservation limits")
    usage = _object(report["usage"], {"unit", "charged_work", "request_decoding_work"}, "Component work accounting")
    budgets = _record(request["budgets"], "Original component budgets")
    charged = _count(usage["charged_work"], "Charged work")
    if (usage["unit"] != "logical_data_visits_and_child_semantic_work" or charged < _count(usage["request_decoding_work"], "Request work")
            or charged > _count(budgets.get("max_work"), "Original maximum work")):
        raise CoreProtocolError("Component work accounting changed its unit or original bound")
    prerequisites = _prerequisites(request)
    material._preservation(response, request, candidate, report, limits, prerequisites=prerequisites,
                           two_observations=_two_observations(request), multi_product=_multi_member(request), finite_machine=_finite_machine(request), network=_network(request), multi_site=_multi_site(request), coupled=_composition(request))
    _leaves(request, candidate, report)
    if prerequisites:
        _prerequisite_evidence(request, report)
    if _quantitative(request):
        _quantitative_evidence(request, candidate, report)
    material._obligations(report, material_key="assembly", accepted_status=ACCEPTED_STATUS,
                          conjunction_stage="conditional_component_context_conjunction",
                          prerequisite_key="prerequisites" if prerequisites else None, multi_product=_multi_member(request),
                          finite_machine=_finite_machine(request), network=_network(request), multi_site=_multi_site(request), coupled=_composition(request), quantitative_key="quantitative" if _quantitative(request) else None)


def _result(response: CoreResponse, payload: dict[str, JsonValue]) -> PolicyComponentMaterialResult:
    request = _original(payload["request"])
    coupled = _composition(request)
    pin = _document_pin if coupled else _pin
    same = _document_same if coupled else _same
    instanced = _instanced(request)
    prerequisites = _prerequisites(request)
    _, _, _, expected_scope, expected_implementation = _profile_settings(request)
    result = _object(response.result, material._RESULT_FIELDS, "Component material result")
    _expect(result, {"schema_version": RESULT_SCHEMA, "implementation": expected_implementation,
                    "resource_profile": RESOURCE_PROFILE, "validation_scope": expected_scope}, "Negotiated component result")
    candidate = _object(result["candidate"], _CANDIDATE_FIELDS, "Complete component candidate")
    if coupled:
        material._publication(candidate, 8_388_608, 250_000)
    if candidate["schema_version"] != CANDIDATE_SCHEMA or "candidate" in payload and not _same(candidate, payload["candidate"]):
        raise CoreProtocolError("Component checking changed the complete supplied candidate")
    _candidate(candidate, instanced=instanced, multi_member=_multi_member(request), grounded_helper=_grounded_helper(request), multi_site=_multi_site(request))
    report = _report(result["report"], instanced=instanced, prerequisites=prerequisites,
                     two_observations=_two_observations(request), multi_member=_multi_member(request), grounded_helper=_grounded_helper(request),
                     finite_machine=_finite_machine(request), quantitative=_quantitative(request), network=_network(request), multi_site=_multi_site(request), transfer_pair=_transfer_pair(request), transfer_network=_transfer_network(request), composition=_composition(request))
    invocation: JsonValue = {"request": request, "candidate": candidate, "limits": payload["limits"]}
    request_hash = pin(result["request_fingerprint"], request, "Complete original component request")
    candidate_hash = pin(result["candidate_fingerprint"], candidate, "Complete component candidate")
    invocation_hash = pin(result["invocation_fingerprint"], invocation, "Complete component invocation")
    report_hash = pin(result["report_fingerprint"], report, "Complete component report")
    _assessment(response, request, candidate, report, payload["limits"])
    material._artifact(result["artifact"], operation=response.operation, request=request, candidate=candidate, report=report, limits=payload["limits"],
        export_operation="export-policy-component-material", accepted_status=ACCEPTED_STATUS, export_schema=EXPORT_SCHEMA,
        manifest_schema=MANIFEST_SCHEMA, request_profile=cast(str, request["profile"]), claim_scope=CLAIM_SCOPE, premise=PREMISE,
        document_encoder=coupled_wire.canonical_bytes if coupled else encode_json)
    if response.operation == "replay-policy-component-material" and not same(result, payload["report"]):
        raise CoreProtocolError("Fresh replay differs from the complete retained component wrapper")
    budgets = _record(request["budgets"], "Original component budgets")
    material._publication(report, _count(budgets.get("max_report_bytes"), "Original report byte ceiling"),
                          _count(budgets.get("max_report_nodes"), "Original report node ceiling"))
    material._publication({"result": coupled_wire.pack(result) if coupled else result}, MAX_RESULT_BYTES, MAX_RESULT_NODES)
    return PolicyComponentMaterialResult(response.request_id, response.operation, response.executable,
        request_hash, candidate_hash, invocation_hash, report_hash, _result_bytes(result, coupled=coupled))


@dataclass(frozen=True)
class PolicyComponentMaterialClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *, cancelled: Callable[[], bool] | None) -> PolicyComponentMaterialResult:
        coupled = _record(payload["request"], "Original request").get("profile") == COMPOSITION_REQUEST_PROFILE
        snapshot = cast(dict[str, JsonValue], coupled_wire.snapshot(payload) if coupled else decode_json(encode_json(payload)))
        request = _original(snapshot["request"])
        if coupled:
            material._publication(request, 8_388_608, 250_000)
            if "candidate" in snapshot:
                material._publication(snapshot["candidate"], 8_388_608, 250_000)
        profile_key, expected_profile, expected_producer, expected_scope, _ = _profile_settings(request)
        if operation == "compile-policy-component-material" and self.transport.role != "core":
            raise CoreProtocolError("Component production requires an explicitly selected Core producer")
        capabilities = self.transport.negotiate(operation, cancelled=cancelled)
        if coupled:
            _wire_capability(capabilities.profiles, self.transport.role)
        if not _same(capabilities.profiles.get(profile_key), expected_profile) or expected_scope not in capabilities.validation_scopes:
            raise CoreProtocolError("Selected executable lacks the exact component material profile")
        if operation == "compile-policy-component-material" and not _same(capabilities.profiles.get(profile_key + "_producer"), expected_producer):
            raise CoreProtocolError("Selected executable lacks the exact component producer profile")
        wire = coupled_wire.pack(snapshot) if coupled else snapshot
        response = self.transport.call(operation, wire, cancelled=cancelled)
        return _result(_wire_response(response, coupled=coupled), snapshot)

    def compile(self, request: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyComponentMaterialResult:
        return self._call("compile-policy-component-material", {"request": request, "limits": limits}, cancelled=cancelled)

    def check(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyComponentMaterialResult:
        return self._call("check-policy-component-material", {"request": request, "candidate": candidate, "limits": limits}, cancelled=cancelled)

    def replay(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, report: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyComponentMaterialResult:
        return self._call("replay-policy-component-material", {"request": request, "candidate": candidate, "limits": limits, "report": report}, cancelled=cancelled)

    def export(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyComponentMaterialResult:
        """Freshly recheck complete original authority before paired export."""
        return self._call("export-policy-component-material", {"request": request, "candidate": candidate, "limits": limits}, cancelled=cancelled)

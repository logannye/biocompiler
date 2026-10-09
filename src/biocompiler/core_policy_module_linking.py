"""Fresh module linkage and linked material transport; no Python proof authority."""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from typing import Callable, Literal, cast

from . import core_policy_component_material as component, core_policy_material as material
from . import core_policy_operational as operational
from .core_client import CoreClient, CoreProtocolError, CoreResponse, JsonValue, _object, decode_json, encode_json
from .policy import model as m
from .policy.module_linking import BUNDLE_SCHEMA, bundle_from_data
from .policy.serialization import from_data

RESULT_SCHEMA = "biocompiler.core.policy_module_linking.v1"
IMPLEMENTATION = "biocompiler.ocaml.policy_module_linking.v0.1"
VALIDATION_SCOPE = "policy-exact-module-elaboration-v0.1"
MATERIAL_SCHEMA = "biocompiler.core.policy_module_material.v1"
MATERIAL_IMPLEMENTATION = "biocompiler.ocaml.policy_module_material.v0.1"
MATERIAL_SCOPE = "policy-module-component-mrna-v0.1"
LINKAGE_SCHEMA = "biocompiler.policy_module_linkage.v0.1"
LINKAGE_IMPLEMENTATION = "biocompiler.ocaml.policy_module_linking_check.v0.1"
MAX_RESULT_BYTES = 8_388_608
MAX_RESULT_NODES = 250_000
PROFILE: dict[str, JsonValue] = {
    "operations": ["check-policy-module-linking", "replay-policy-module-linking"], "schema_version": RESULT_SCHEMA,
    "implementation": IMPLEMENTATION, "validation_scope": VALIDATION_SCOPE, "bundle_schema": BUNDLE_SCHEMA,
    "max_result_bytes": MAX_RESULT_BYTES, "max_result_nodes": MAX_RESULT_NODES, "artifact": "none", "empirical": "unassessed"}
MATERIAL_PROFILE: dict[str, JsonValue] = {**PROFILE,
    "operations": ["check-policy-module-material", "replay-policy-module-material", "export-policy-module-material"],
    "schema_version": MATERIAL_SCHEMA, "implementation": MATERIAL_IMPLEMENTATION, "validation_scope": MATERIAL_SCOPE,
    "artifact": "fresh_exact_mrna_with_module_lineage"}
PRODUCER_PROFILE: dict[str, JsonValue] = {**MATERIAL_PROFILE, "operations": ["compile-policy-module-material"]}
_LINKAGE_FIELDS = {"schema_version", "implementation", "relation", "bundle_fingerprint", "program_fingerprint", "lineage", "usage", "behavior", "empirical"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CoreProtocolError(message)


def _record(raw: JsonValue, label: str) -> dict[str, JsonValue]:
    return component._record(raw, label)


def _program(request: dict[str, JsonValue]) -> dict[str, JsonValue]:
    original = _record(request["implementation_request"], "Original implementation request")
    document = _record(original["document"], "Original source document")
    program = _record(document["program"], "Original source program") if document.get("$type") == "BuildRequest" else document
    from_data(program, m.PolicyProgram)
    return program


def _lineage(modules: dict[str, JsonValue], program: dict[str, JsonValue]) -> list[JsonValue]:
    """Transport census only: body records and semantics remain native obligations."""
    context = _record(modules["context"], "Original module context")
    expected: list[JsonValue] = []
    declarations = component._rows(program["declarations"], "Proposed declarations")
    def append(source_path: str, instance: JsonValue, pin: JsonValue, declaration: JsonValue, expanded: JsonValue) -> None:
        index = len(expected)
        _require(index < len(declarations) and declarations[index].get("id") == expanded,
                 "Linkage declaration census differs from the proposed source")
        expected.append({"source_path": source_path, "flat_path": "/program/declarations/" + str(index),
            "instance": instance, "template": pin, "declaration": declaration, "expanded": expanded})
    for index, row in enumerate(component._rows(context["declarations"], "Context declarations")):
        append("/modules/context/declarations/" + str(index), None, None, row["id"], row["id"])
    templates = component._rows(modules["templates"], "Original templates")
    for instance in component._rows(modules["instances"], "Original instances"):
        pin = _record(instance["template"], "Original template pin")
        matches = [(index, template) for index, template in enumerate(templates)
                   if template["id"] == pin["id"] and template["version"] == pin["version"]]
        _require(len(matches) == 1, "Instance does not retain its original template")
        index, template = matches[0]
        operational._pin(pin["content_fingerprint"], template, "Complete template body")
        for field in ("declarations", "assumptions", "guarantees"):
            for position, row in enumerate(component._rows(template[field], "Template " + field)):
                identifier = row["id"]
                _require(type(identifier) is str and type(instance["name"]) is str, "Lineage identities must be source names")
                append("/modules/templates/" + str(index) + "/" + field + "/" + str(position),
                    instance["name"], pin, identifier, cast(str, instance["name"]) + "/" + cast(str, identifier))
    _require(len(expected) == len(declarations), "Linkage omitted original source occurrences")
    return expected


def _linkage(raw: JsonValue, modules: dict[str, JsonValue], program: dict[str, JsonValue]) -> dict[str, JsonValue]:
    value = _object(raw, _LINKAGE_FIELDS, "Complete module linkage")
    component._expect(value, {"schema_version": LINKAGE_SCHEMA, "implementation": LINKAGE_IMPLEMENTATION,
        "relation": "exact_module_elaboration", "behavior": "unassessed", "empirical": "unassessed"}, "Module linkage profile")
    operational._pin(value["bundle_fingerprint"], modules, "Complete original module bundle")
    operational._pin(value["program_fingerprint"], program, "Complete expanded source")
    _require(operational._same(value["lineage"], _lineage(modules, program)), "Module linkage changed its complete ordered source lineage")
    usage = _object(value["usage"], {"unit", "charged_work", "scanned_bytes"}, "Module usage")
    bounds = _record(modules["limits"], "Original module limits")
    _require(usage["unit"] == "logical_module_work", "Module work unit changed")
    for field, maximum in (("charged_work", "max_work"), ("scanned_bytes", "max_bytes")):
        _require(component._count(usage[field], "Module usage") <= component._count(bounds[maximum], "Original module limit"),
                 "Module report exceeds its original limits")
    return value


@dataclass(frozen=True, slots=True)
class PolicyModuleLinkingResult:
    """Immutable descriptive response snapshot, never native checked linkage."""
    request_id: str
    operation: str
    executable: Literal["core", "verify"]
    invocation_fingerprint: str
    _result_json: bytes

    @property
    def result(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self._result_json))

    @property
    def modules(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.result["modules"])

    @property
    def program(self) -> m.PolicyProgram:
        return from_data(self.result["program"], m.PolicyProgram)

    @property
    def linkage(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.result["linkage"])


@dataclass(frozen=True)
class PolicyModuleMaterialResult(material.PolicyMaterialResult):
    """Linked wrapper; inherited publication writes only its validated exact pair."""
    @property
    def material(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.result["material"])

    @property
    def report(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.material["report"])

    @property
    def candidate(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.material["candidate"])

    @property
    def modules(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.result["modules"])

    @property
    def linkage(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.result["linkage"])


def _result(response: CoreResponse, payload: dict[str, JsonValue]) -> PolicyModuleLinkingResult:
    encode_json(response.result, limit=MAX_RESULT_BYTES)
    result = _object(response.result, {"schema_version", "implementation", "validation_scope", "modules", "program", "linkage", "invocation_fingerprint"}, "Module linking response")
    component._expect(result, {"schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION, "validation_scope": VALIDATION_SCOPE}, "Module response profile")
    modules = _record(payload["modules"], "Original module bundle")
    program = _record(payload["program"], "Original proposed program")
    _require(operational._same(result["modules"], modules) and operational._same(result["program"], program),
             "Module response changed complete original authority")
    _linkage(result["linkage"], modules, program)
    invocation = operational._pin(result["invocation_fingerprint"], {"modules": modules, "program": program}, "Complete module invocation")
    if response.operation == "replay-policy-module-linking":
        _require(operational._same(result, payload["report"]), "Fresh module replay differs from the complete saved wrapper")
    material._publication({"result": result}, MAX_RESULT_BYTES, MAX_RESULT_NODES)
    return PolicyModuleLinkingResult(response.request_id, response.operation, response.executable, invocation, encode_json(result))


def _artifact(raw: JsonValue, *, operation: str, modules: JsonValue, linkage: JsonValue, child: JsonValue) -> None:
    if operation != "export-policy-module-material":
        _require(raw is None, "Linked bytes require fresh export")
        return
    _require(child is not None, "Successful linked export requires a freshly accepted underlying export")
    underlying = _record(child, "Fresh underlying material export")
    artifact = _object(raw, {"schema_version", "fasta", "fasta_sha256", "manifest", "manifest_sha256"}, "Linked export")
    _require(artifact["schema_version"] == "biocompiler.policy_module_mrna_export.v0.1", "Linked export version changed")
    _require(artifact["fasta"] == underlying["fasta"] and artifact["fasta_sha256"] == underlying["fasta_sha256"],
             "Linked export changed exact underlying RNA bytes")
    fasta = artifact["fasta"]
    _require(type(fasta) is str and hashlib.sha256(fasta.encode()).hexdigest() == artifact["fasta_sha256"], "Linked FASTA hash changed")
    expected: JsonValue = {"schema_version": "biocompiler.policy_module_mrna_manifest.v0.1", "modules": modules,
        "linkage": linkage, "material_manifest": underlying["manifest"], "material_manifest_sha256": underlying["manifest_sha256"],
        "fasta_sha256": underlying["fasta_sha256"], "claim_scope": "exact_module_elaboration_and_bounded_conditional_component_material",
        "empirical": "unassessed"}
    _require(operational._same(artifact["manifest"], expected), "Linked manifest changed original authority or exact underlying manifest")
    operational._pin(artifact["manifest_sha256"], expected, "Complete linked manifest")


def _material_result(response: CoreResponse, payload: dict[str, JsonValue]) -> PolicyModuleMaterialResult:
    encode_json(response.result, limit=MAX_RESULT_BYTES)
    result = _object(response.result, {"schema_version", "implementation", "validation_scope", "modules", "linkage", "material", "invocation_fingerprint", "artifact"}, "Linked material response")
    component._expect(result, {"schema_version": MATERIAL_SCHEMA, "implementation": MATERIAL_IMPLEMENTATION, "validation_scope": MATERIAL_SCOPE}, "Linked material profile")
    request = component._original(payload["request"])
    modules = _record(payload["modules"], "Original module bundle")
    _require(operational._same(result["modules"], modules), "Linked material changed the original module bundle")
    _linkage(result["linkage"], modules, _program(request))
    # Validate the exact retained child with its existing transport validator.
    # This projects a fresh native response; it performs no new call or proof.
    child_operation = response.operation.replace("-module-material", "-component-material")
    child_payload = {key: value for key, value in payload.items() if key not in ("modules", "report")}
    if "report" in payload:
        child_payload["report"] = _record(payload["report"], "Saved linked wrapper")["material"]
    child = component._result(replace(response, operation=child_operation, result=result["material"]), child_payload)
    invocation = operational._pin(result["invocation_fingerprint"], {"modules": modules, "request": request,
        "candidate": child.candidate, "limits": payload["limits"]}, "Complete linked material invocation")
    _artifact(result["artifact"], operation=response.operation, modules=modules, linkage=result["linkage"], child=child.artifact)
    if response.operation == "replay-policy-module-material":
        _require(operational._same(result, payload["report"]), "Fresh linked material replay differs from the complete saved wrapper")
    material._publication({"result": result}, MAX_RESULT_BYTES, MAX_RESULT_NODES)
    return PolicyModuleMaterialResult(response.request_id, response.operation, response.executable,
        child.request_fingerprint, child.candidate_fingerprint, invocation, child.report_fingerprint, encode_json(result))


@dataclass(frozen=True)
class PolicyModuleLinkingClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *, cancelled: Callable[[], bool] | None) -> PolicyModuleLinkingResult:
        snapshot = cast(dict[str, JsonValue], decode_json(encode_json(payload)))
        bundle_from_data(snapshot["modules"])
        from_data(snapshot["program"], m.PolicyProgram)
        capabilities = self.transport.negotiate(operation, cancelled=cancelled)
        _require(operational._same(capabilities.profiles.get("policy_module_linking"), PROFILE)
                 and VALIDATION_SCOPE in capabilities.validation_scopes, "Selected executable lacks the exact module-linking profile")
        return _result(self.transport.call(operation, snapshot, cancelled=cancelled), snapshot)

    def check(self, modules: JsonValue, program: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyModuleLinkingResult:
        return self._call("check-policy-module-linking", {"modules": modules, "program": program}, cancelled=cancelled)

    def replay(self, modules: JsonValue, program: JsonValue, report: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyModuleLinkingResult:
        return self._call("replay-policy-module-linking", {"modules": modules, "program": program, "report": report}, cancelled=cancelled)


@dataclass(frozen=True)
class PolicyModuleMaterialClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *, cancelled: Callable[[], bool] | None) -> PolicyModuleMaterialResult:
        snapshot = cast(dict[str, JsonValue], decode_json(encode_json(payload)))
        bundle_from_data(snapshot["modules"])
        component._original(snapshot["request"])
        producer = operation == "compile-policy-module-material"
        _require(not producer or self.transport.role == "core", "Linked material production requires an explicitly selected Core producer")
        capabilities = self.transport.negotiate(operation, cancelled=cancelled)
        _require(operational._same(capabilities.profiles.get("policy_module_material"), MATERIAL_PROFILE)
                 and MATERIAL_SCOPE in capabilities.validation_scopes, "Selected executable lacks the exact linked material profile")
        if producer:
            _require(operational._same(capabilities.profiles.get("policy_module_material_producer"), PRODUCER_PROFILE),
                     "Selected executable lacks the exact linked material producer profile")
        return _material_result(self.transport.call(operation, snapshot, cancelled=cancelled), snapshot)

    def compile(self, modules: JsonValue, request: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyModuleMaterialResult:
        return self._call("compile-policy-module-material", {"modules": modules, "request": request, "limits": limits}, cancelled=cancelled)

    def check(self, modules: JsonValue, request: JsonValue, candidate: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyModuleMaterialResult:
        return self._call("check-policy-module-material", {"modules": modules, "request": request, "candidate": candidate, "limits": limits}, cancelled=cancelled)

    def replay(self, modules: JsonValue, request: JsonValue, candidate: JsonValue, limits: JsonValue, report: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyModuleMaterialResult:
        return self._call("replay-policy-module-material", {"modules": modules, "request": request, "candidate": candidate, "limits": limits, "report": report}, cancelled=cancelled)

    def export(self, modules: JsonValue, request: JsonValue, candidate: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyModuleMaterialResult:
        return self._call("export-policy-module-material", {"modules": modules, "request": request, "candidate": candidate, "limits": limits}, cancelled=cancelled)


__all__ = ["PolicyModuleLinkingResult", "PolicyModuleMaterialResult", "PolicyModuleLinkingClient", "PolicyModuleMaterialClient"]

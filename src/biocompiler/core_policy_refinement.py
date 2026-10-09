"""Fresh native named-refinement transport and immutable descriptive evidence.

Parsed evidence is a view of a checked response, never a native proof capability.
No operation here compiles a candidate, composes proofs, or exports material.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, TypeAlias, cast

from . import core_policy as source
from . import core_policy_component_material as component
from . import core_policy_material as material_transport
from . import core_policy_operational as operational
from .core_client import CoreClient, CoreProtocolError, CoreResponse, JsonValue, _object, decode_json, encode_json

RESULT_SCHEMA = "biocompiler.core.policy_refinement.v1"
EVIDENCE_SCHEMA = "biocompiler.policy_refinement_evidence.v0.1"
IMPLEMENTATION = "biocompiler.ocaml.policy_refinement.v0.1"
VALIDATION_SCOPE = "policy-named-refinement-v0.1"
MAX_RESULT_BYTES = component.MAX_RESULT_BYTES
MAX_RESULT_NODES = component.MAX_RESULT_NODES
PROFILE: dict[str, JsonValue] = {
    "operations": ["check-policy-refinement", "replay-policy-refinement"],
    "schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION, "validation_scope": VALIDATION_SCOPE,
    "evidence_schema": EVIDENCE_SCHEMA, "max_result_bytes": MAX_RESULT_BYTES, "max_result_nodes": MAX_RESULT_NODES,
    "artifact": "none", "empirical": "unassessed",
}

Stage: TypeAlias = Literal["source_document", "operational_behavior", "implementation_graph", "construction_content", "deployment_context"]
Relation: TypeAlias = Literal["exact_source_occurrence", "source_graph_binding", "bounded_observable_correspondence",
    "original_hard_requirements", "supplied_component_material_correspondence", "conditional_deployment_context",
    "complete_original_obligations", "exact_source_graph_correspondence", "bounded_source_observable_correspondence",
    "conditional_source_material_correspondence"]
PremiseKind: TypeAlias = Literal["original_source", "semantic_definitions", "operating_domain", "implementation_catalog",
    "implementation_models", "checker_limits", "component_library", "composition_rule", "material_authority",
    "deployment_context", "material_request", "source_admission", "implementation_binding", "bounded_preservation",
    "component_assembly", "mrna_structure", "component_context", "complete_material_check"]
DerivationRule: TypeAlias = Literal["checked_admission", "checked_binding", "checked_preservation", "checked_assembly",
    "checked_context", "checked_material", "conjunction", "source_graph_chain", "source_behavior_chain", "source_material_chain"]
_STAGES = ("source_document", "operational_behavior", "implementation_graph", "construction_content", "deployment_context")
_RELATIONS = ("exact_source_occurrence", "source_graph_binding", "bounded_observable_correspondence",
    "original_hard_requirements", "supplied_component_material_correspondence", "conditional_deployment_context",
    "complete_original_obligations", "exact_source_graph_correspondence", "bounded_source_observable_correspondence",
    "conditional_source_material_correspondence")
_PREMISES = ("original_source", "semantic_definitions", "operating_domain", "implementation_catalog",
    "implementation_models", "checker_limits", "component_library", "composition_rule", "material_authority",
    "deployment_context", "material_request", "source_admission", "implementation_binding", "bounded_preservation",
    "component_assembly", "mrna_structure", "component_context", "complete_material_check")
_RULES = ("checked_admission", "checked_binding", "checked_preservation", "checked_assembly", "checked_context",
    "checked_material", "conjunction", "source_graph_chain", "source_behavior_chain", "source_material_chain")
_SCOPE_FIELDS = {"implementation_request_fingerprint", "operating_domain_fingerprint", "limits_fingerprint", "material_request_fingerprint"}
_RESULT_FIELDS = {"schema_version", "implementation", "validation_scope", "request_fingerprint", "candidate_fingerprint",
    "invocation_fingerprint", "material_report_fingerprint", "material_report", "evidence"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CoreProtocolError(message)


def _choice(value: JsonValue, allowed: tuple[str, ...], label: str) -> str:
    _require(type(value) is str and value in allowed, "Unknown refinement " + label)
    return cast(str, value)


@dataclass(frozen=True, slots=True)
class StageIdentity:
    stage: Stage
    fingerprint: str

    def __post_init__(self) -> None:
        _choice(self.stage, _STAGES, "stage")
        source._hash(self.fingerprint)

    def to_data(self) -> dict[str, JsonValue]:
        return {"stage": self.stage, "fingerprint": self.fingerprint}


@dataclass(frozen=True, slots=True)
class RefinementScope:
    implementation_request_fingerprint: str
    operating_domain_fingerprint: str
    limits_fingerprint: str | None
    material_request_fingerprint: str | None

    def __post_init__(self) -> None:
        source._hash(self.implementation_request_fingerprint)
        source._hash(self.operating_domain_fingerprint)
        for value in (self.limits_fingerprint, self.material_request_fingerprint):
            if value is not None:
                source._hash(value)

    def to_data(self) -> dict[str, JsonValue]:
        return {"implementation_request_fingerprint": self.implementation_request_fingerprint,
            "operating_domain_fingerprint": self.operating_domain_fingerprint, "limits_fingerprint": self.limits_fingerprint,
            "material_request_fingerprint": self.material_request_fingerprint}


@dataclass(frozen=True, slots=True)
class RefinementClaim:
    relation: Relation
    source: StageIdentity
    target: StageIdentity
    scope: RefinementScope

    def __post_init__(self) -> None:
        _choice(self.relation, _RELATIONS, "relation")
        _require(type(self.source) is StageIdentity and type(self.target) is StageIdentity and type(self.scope) is RefinementScope,
                 "Refinement claims require immutable typed endpoints and scope")

    def to_data(self) -> dict[str, JsonValue]:
        return {"relation": self.relation, "source": self.source.to_data(), "target": self.target.to_data(), "scope": self.scope.to_data()}


@dataclass(frozen=True, slots=True)
class RefinementPremise:
    kind: PremiseKind
    fingerprint: str

    def __post_init__(self) -> None:
        _choice(self.kind, _PREMISES, "premise kind")
        source._hash(self.fingerprint)

    def to_data(self) -> dict[str, JsonValue]:
        return {"kind": self.kind, "fingerprint": self.fingerprint}


@dataclass(frozen=True, slots=True)
class RefinementDerivation:
    rule: DerivationRule
    inputs: tuple[str, ...]

    def __post_init__(self) -> None:
        _choice(self.rule, _RULES, "derivation rule")
        _require(type(self.inputs) is tuple and len(self.inputs) <= 16, "Refinement derivation needs a bounded immutable input census")
        for value in self.inputs:
            source._hash(value)

    def to_data(self) -> dict[str, JsonValue]:
        return {"rule": self.rule, "inputs": list(self.inputs)}


@dataclass(frozen=True, slots=True)
class RefinementEvidence:
    """Immutable descriptive claims, not an accepted native evidence handle."""
    claims: tuple[RefinementClaim, ...]
    premises: tuple[RefinementPremise, ...]
    derivation: RefinementDerivation

    def __post_init__(self) -> None:
        _require(type(self.claims) is tuple and 0 < len(self.claims) <= 32
                 and all(type(value) is RefinementClaim for value in self.claims), "Evidence needs immutable typed claims")
        _require(type(self.premises) is tuple and 0 < len(self.premises) <= 32
                 and all(type(value) is RefinementPremise for value in self.premises), "Evidence needs immutable typed premises")
        _require(type(self.derivation) is RefinementDerivation, "Evidence needs an immutable typed derivation")

    def to_data(self) -> dict[str, JsonValue]:
        claims: list[JsonValue] = [value.to_data() for value in self.claims]
        premises: list[JsonValue] = [value.to_data() for value in self.premises]
        return {"schema_version": EVIDENCE_SCHEMA, "claims": claims, "premises": premises, "derivation": self.derivation.to_data()}


def _endpoint(raw: JsonValue) -> StageIdentity:
    value = _object(raw, {"stage", "fingerprint"}, "Refinement endpoint")
    return StageIdentity(cast(Stage, _choice(value["stage"], _STAGES, "stage")), source._hash(value["fingerprint"]))


def _scope(raw: JsonValue) -> RefinementScope:
    value = _object(raw, _SCOPE_FIELDS, "Refinement scope")
    return RefinementScope(source._hash(value["implementation_request_fingerprint"]), source._hash(value["operating_domain_fingerprint"]),
        None if value["limits_fingerprint"] is None else source._hash(value["limits_fingerprint"]),
        None if value["material_request_fingerprint"] is None else source._hash(value["material_request_fingerprint"]))


def _evidence(raw: JsonValue) -> RefinementEvidence:
    value = _object(raw, {"schema_version", "claims", "premises", "derivation"}, "Named refinement evidence")
    _require(value["schema_version"] == EVIDENCE_SCHEMA, "Refinement evidence changed its version")
    claim_rows = component._rows(value["claims"], "Refinement claims")
    premise_rows = component._rows(value["premises"], "Refinement premises")
    _require(0 < len(claim_rows) <= 32 and 0 < len(premise_rows) <= 32, "Refinement evidence census exceeds its bound")
    claims = []
    for item in claim_rows:
        row = _object(item, {"relation", "source", "target", "scope"}, "Refinement claim")
        claims.append(RefinementClaim(cast(Relation, _choice(row["relation"], _RELATIONS, "relation")),
            _endpoint(row["source"]), _endpoint(row["target"]), _scope(row["scope"])))
    premises = []
    for item in premise_rows:
        row = _object(item, {"kind", "fingerprint"}, "Refinement premise")
        premises.append(RefinementPremise(cast(PremiseKind, _choice(row["kind"], _PREMISES, "premise kind")), source._hash(row["fingerprint"])))
    derivation = _object(value["derivation"], {"rule", "inputs"}, "Refinement derivation")
    inputs = derivation["inputs"]
    _require(type(inputs) is list and len(inputs) <= 16, "Refinement derivation inputs must be a bounded ordered array")
    return RefinementEvidence(tuple(claims), tuple(premises), RefinementDerivation(
        cast(DerivationRule, _choice(derivation["rule"], _RULES, "derivation rule")),
        tuple(source._hash(value) for value in cast(list[JsonValue], inputs))))


def _bindings(evidence: RefinementEvidence, request: dict[str, JsonValue], candidate: dict[str, JsonValue],
              report: dict[str, JsonValue], limits: JsonValue) -> None:
    """Validate retained identities; never reproduce or accept a native proof DAG."""
    original = component._record(request["implementation_request"], "Original implementation request")
    scope = RefinementScope(operational._fingerprint(original), operational._fingerprint(original["operating_domain"]), None, None)
    limited = RefinementScope(scope.implementation_request_fingerprint, scope.operating_domain_fingerprint, operational._fingerprint(limits), None)
    material = RefinementScope(scope.implementation_request_fingerprint, scope.operating_domain_fingerprint, limited.limits_fingerprint,
                               operational._fingerprint(request))
    stage_values: dict[str, JsonValue] = {"source_document": original["document"], "operational_behavior": candidate["behavior"],
        "implementation_graph": candidate["implementation"], "construction_content": candidate["construction"], "deployment_context": request["context"]}
    stages = {name: StageIdentity(cast(Stage, name), operational._fingerprint(value)) for name, value in stage_values.items()}
    pairs = (("source_document", "operational_behavior", scope), ("operational_behavior", "implementation_graph", scope),
        ("operational_behavior", "implementation_graph", limited), ("operational_behavior", "implementation_graph", limited),
        ("implementation_graph", "construction_content", limited), ("construction_content", "deployment_context", material),
        ("source_document", "construction_content", material), ("source_document", "implementation_graph", scope),
        ("source_document", "implementation_graph", limited), ("source_document", "construction_content", material))
    expected = tuple(RefinementClaim(cast(Relation, relation), stages[left], stages[right], bound)
                     for relation, (left, right, bound) in zip(_RELATIONS, pairs))
    _require(evidence.claims == expected, "Named refinement changed its complete ordered claims, stage identities or stage-local scope")
    _premise_bindings(evidence, request, candidate, report, limits)
    _require(evidence.derivation.rule == "conjunction" and len(evidence.derivation.inputs) == 2
             and len(set(evidence.derivation.inputs)) == 2, "Final refinement changed its declared derivation shape")


def _premise_bindings(evidence: RefinementEvidence, request: dict[str, JsonValue], candidate: dict[str, JsonValue],
                      report: dict[str, JsonValue], limits: JsonValue) -> None:
    original = component._record(request["implementation_request"], "Original implementation request")
    document = component._record(original["document"], "Original source document")
    rule = component._record(request["composition_rule"], "Original composition rule")
    rule_body = component._record(rule["body"], "Original composition rule body")
    preservation = component._record(report["preservation"], "Fresh preservation report")
    binding = component._record(preservation["binding"], "Fresh binding report")
    assembly = component._record(report["assembly"], "Fresh assembly report")
    roots = (document, original["definitions"], original["operating_domain"], document["implementations"],
        original["implementation_library"], limits, request["component_library"], rule, rule_body["material_authority"],
        request["context"], request, binding["source_admission"], binding, preservation, assembly,
        assembly["structure"], report["context"], report)
    expected = tuple(RefinementPremise(cast(PremiseKind, kind), operational._fingerprint(value))
                     for kind, value in zip(_PREMISES, roots))
    _require(evidence.premises == expected, "Refinement changed its complete ordered original-input and fresh-report premises")


@dataclass(frozen=True, slots=True)
class PolicyRefinementResult:
    """A fresh native response snapshot; no export or reusable proof capability."""
    request_id: str
    operation: str
    executable: Literal["core", "verify"]
    request_fingerprint: str
    candidate_fingerprint: str
    invocation_fingerprint: str
    material_report_fingerprint: str
    evidence: RefinementEvidence | None
    _result_json: bytes

    @property
    def result(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self._result_json))

    @property
    def material_report(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.result["material_report"])

    @property
    def material_status(self) -> Literal["checked_component_material", "not_accepted"]:
        return cast(Literal["checked_component_material", "not_accepted"], self.material_report["status"])


def _result(response: CoreResponse, payload: dict[str, JsonValue]) -> PolicyRefinementResult:
    result = _object(response.result, _RESULT_FIELDS, "Named refinement response")
    material_transport._publication({"result": result}, MAX_RESULT_BYTES, MAX_RESULT_NODES)
    _require(result["schema_version"] == RESULT_SCHEMA and result["implementation"] == IMPLEMENTATION
             and result["validation_scope"] == VALIDATION_SCOPE, "Refinement response changed its negotiated profile")
    request = component._original(payload["request"])
    candidate = component._candidate(payload["candidate"], instanced=component._instanced(request),
        multi_member=component._multi_member(request), grounded_helper=component._grounded_helper(request), multi_site=component._multi_site(request))
    request_pin = operational._pin(result["request_fingerprint"], request, "Complete refinement request")
    candidate_pin = operational._pin(result["candidate_fingerprint"], candidate, "Complete refinement candidate")
    invocation_pin = operational._pin(result["invocation_fingerprint"], {
        "request": request, "candidate": candidate, "limits": payload["limits"]}, "Complete refinement invocation")
    report = component._report(result["material_report"], instanced=component._instanced(request),
        prerequisites=component._prerequisites(request), two_observations=component._two_observations(request),
        multi_member=component._multi_member(request), grounded_helper=component._grounded_helper(request),
        finite_machine=component._finite_machine(request), quantitative=component._quantitative(request), network=component._network(request), multi_site=component._multi_site(request), transfer_pair=component._transfer_pair(request), transfer_network=component._transfer_network(request), composition=component._composition(request))
    report_pin = operational._pin(result["material_report_fingerprint"], report, "Fresh complete material report")
    component._assessment(response, request, candidate, report, payload["limits"])
    evidence = None if result["evidence"] is None else _evidence(result["evidence"])
    _require((evidence is not None) == (report["status"] == component.ACCEPTED_STATUS),
             "Refinement claims contradict fresh complete material acceptance")
    if evidence is not None:
        _bindings(evidence, request, candidate, report, payload["limits"])
    if response.operation == "replay-policy-refinement":
        _require(operational._same(result, payload["report"]), "Fresh refinement replay differs from the full saved response")
    return PolicyRefinementResult(response.request_id, response.operation, response.executable, request_pin,
        candidate_pin, invocation_pin, report_pin, evidence, encode_json(result))


@dataclass(frozen=True)
class PolicyRefinementClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *, cancelled: Callable[[], bool] | None) -> PolicyRefinementResult:
        snapshot = cast(dict[str, JsonValue], decode_json(encode_json(payload)))
        component._original(snapshot["request"])
        capabilities = self.transport.negotiate(operation, cancelled=cancelled)
        _require(operational._same(capabilities.profiles.get("policy_refinement"), PROFILE)
                 and VALIDATION_SCOPE in capabilities.validation_scopes, "Selected executable lacks the exact named-refinement profile")
        return _result(self.transport.call(operation, snapshot, cancelled=cancelled), snapshot)

    def check(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, *,
              cancelled: Callable[[], bool] | None = None) -> PolicyRefinementResult:
        return self._call("check-policy-refinement", {"request": request, "candidate": candidate, "limits": limits}, cancelled=cancelled)

    def replay(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, report: JsonValue, *,
               cancelled: Callable[[], bool] | None = None) -> PolicyRefinementResult:
        return self._call("replay-policy-refinement", {"request": request, "candidate": candidate, "limits": limits, "report": report}, cancelled=cancelled)


__all__ = ["Stage", "Relation", "PremiseKind", "DerivationRule", "StageIdentity", "RefinementScope", "RefinementClaim",
    "RefinementPremise", "RefinementDerivation", "RefinementEvidence", "PolicyRefinementResult", "PolicyRefinementClient"]

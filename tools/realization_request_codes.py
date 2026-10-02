"""Input-sensitive native diagnostics for the frozen RA-04 source campaign.

Fixture-only projections, never production validation or acceptance. Primitive
checks follow native import order; semantic outcomes use a finite observed
message inventory. New source diagnostics must be reviewed explicitly.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from tools import realization_contract_codes as C


def _get(value: dict, key: str) -> Any:
    C._require(key in value, "missing_field")
    return value[key]


def _boolean(value: Any) -> None:
    C._require(type(value) is bool, "invalid_type")


def _names(value: Any, *, unique: bool = False) -> list:
    values = C._array(value)
    for item in values:
        C._name(item)
    if unique:
        C._require(len(set(values)) == len(values), "duplicate_name")
    return values


def _schema(value: Any, version: str, fields: set[str]) -> dict:
    result = C._fields(value, fields | {"schema_version"})
    C._require(C._string(result["schema_version"]) == version, "unsupported_schema")
    return result


def _same(left: Any, right: Any) -> bool:
    return json.dumps(left, sort_keys=True, ensure_ascii=False) == json.dumps(right, sort_keys=True, ensure_ascii=False)


def _source(value: Any) -> None:
    if value is None:
        return
    fields = C._fields(value, {"file", "line", "function"})
    C._name(fields["file"])
    C._name(fields["function"])
    C._require(type(fields["line"]) is int, "invalid_type")
    C._require(fields["line"] > 0, "invalid_source")


def _binding(value: Any, dtype: dict) -> None:
    kind = dtype["kind"]
    C._require(kind in {"scalar", "interval", "curve"}, "invalid_binding")
    fields = {"kind", "type"} | ({"value", "unit", "canonical_value"} if kind == "scalar" else
        {"lower", "upper"} if kind == "interval" else {"points", "interpolation", "extrapolation"})
    value = C._fields(value, fields)
    C._require(C._string(value["kind"]) == kind, "invalid_binding")
    actual = C._dtype(value["type"])
    C._require(C._compatible(actual, dtype), "type_mismatch")
    if kind == "scalar":
        C._number(value["value"])
        C._number(value["canonical_value"])
        C._name(value["unit"])
        # The original scalar codec uses exactly the native registered factors.
        # It is used only for numeric normalization after native field/type
        # checks, not to produce an acceptance decision or diagnostic fallback.
        from biocompiler.semantics.types import TypeSpec, Level, Duration, Concentration, SurfaceDensity, ProductionRate
        native_type = TypeSpec.from_dict(value["type"])
        units = next((scalar._units for scalar in (Level, Duration, Concentration, SurfaceDensity, ProductionRate)
                      if scalar._spec == native_type), None)
        if units is not None:
            C._require(value["unit"] in units, "unsupported_unit")
            expected = value["value"] * units[value["unit"]]
            C._number(expected)
            C._require(expected == value["canonical_value"], "canonical_value_mismatch")
    elif kind == "interval":
        _binding(value["lower"], actual["arguments"][0])
        _binding(value["upper"], actual["arguments"][0])
        C._require(value["lower"]["canonical_value"] <= value["upper"]["canonical_value"], "invalid_interval")
    else:
        points = C._array(value["points"])
        C._require(len(points) >= 2, "invalid_curve")
        previous = None
        for point in points:
            point = C._array(point)
            C._require(len(point) == 2, "invalid_curve")
            _binding(point[0], actual["arguments"][0])
            _binding(point[1], actual["arguments"][1])
            current = point[0]["canonical_value"]
            C._require(previous is None or previous < current, "invalid_curve")
            previous = current
        C._require(C._string(value["interpolation"]) in {"linear", "step"}, "invalid_curve")
        C._require(C._string(value["extrapolation"]) in {"clamp", "error"}, "invalid_curve")


def _intent(value: Any) -> None:
    value = _schema(value, "biocompiler.intent.v0.1", {"name", "nodes", "roots"})
    C._name(value["name"])
    nodes = C._array(value["nodes"])
    for node in nodes:
        node = C._fields(node, {"id", "kind", "inputs", "attributes", "data_type", "role"}, {"source"})
        C._name(node["id"])
        C._name(node["kind"])
        _names(node["inputs"])
        attrs = C._object(node["attributes"])
        dtype = C._dtype(node["data_type"]) if node["data_type"] is not None else None
        if node["kind"] in {"literal", "parameter"}:
            C._require(dtype is not None, "missing_type")
            if node["kind"] == "parameter":
                C._name(_get(attrs, "name"))
                _boolean(_get(attrs, "bound"))
                C._require(attrs["bound"] == ("default" in attrs), "invalid_parameter")
                if attrs["bound"]:
                    _binding(attrs["default"], dtype)
            else:
                _binding(_get(attrs, "value"), dtype)
        if node["role"] is not None:
            C._name(node["role"])
        _source(node.get("source"))
    roots = _names(value["roots"])
    identities = {node["id"]: node for node in nodes}
    C._require(len(identities) == len(nodes), "duplicate_node")
    seen = set()
    for root in roots:
        C._require(root not in seen, "duplicate_root")
        C._require(root in identities, "dangling_root")
        seen.add(root)
    parameters = set()
    for node in nodes:
        if node["kind"] == "parameter":
            name = node["attributes"]["name"]
            C._require(name not in parameters, "duplicate_parameter")
            parameters.add(name)
        if node["role"] is not None:
            C._require(node["role"] in identities and identities[node["role"]]["kind"] == "role", "invalid_role")
        C._require(all(key in identities for key in node["inputs"]), "dangling_reference")


def _target(value: Any) -> None:
    raw = C._object(value)
    version = C._string(_get(raw, "schema_version"))
    C._require(version in {"biocompiler.target.v0.1", "biocompiler.human_target_context.v0.1"}, "unsupported_schema")
    extra = {"human_target"} if version == "biocompiler.human_target_context.v0.1" else set()
    _schema(raw, version, {"context_id", "context_version", "payload_format", "capabilities", "compartments", "resources"} | extra)
    C._name(raw["context_id"])
    C._name(raw["context_version"])
    C._require(C._string(raw["payload_format"]) in {"DNA", "RNA"}, "invalid_choice")
    _names(raw["capabilities"], unique=True)
    C._require(bool(_names(raw["compartments"], unique=True)), "invalid_target")
    for key, value in C._object(raw["resources"]).items():
        C._name(key)
        dtype = C._dtype(_get(C._object(value), "type"))
        C._require(dtype["kind"] == "scalar", "invalid_resource")
        _binding(value, dtype)
        C._require(value["canonical_value"] >= 0, "invalid_resource")
    # This campaign mutates legacy target leaves only. Full human targets are
    # retained positives; their own exhaustive imports have independent gates.


def _build(value: Any) -> None:
    value = _schema(value, "biocompiler.build_request.v0.1", {"intent", "explicit_overrides", "resolved_defaults", "resolved_bindings", "target", "artifact_scope", "behavior_profile", "implementation_constraints", "preferences", "parameter_metadata", "provenance"})
    _intent(value["intent"])
    C._require(C._string(value["behavior_profile"]) in {"biocompiler.behavior.v0.1", "biocompiler.behavior.v0.2"}, "unsupported_behavior_profile")
    C._require(C._string(value["artifact_scope"]) in {"abstract_behavior", "synthetic_realization", "exact_cds", "complete_payload"}, "unsupported_artifact_scope")
    if value["target"] is not None:
        _target(value["target"])
    C._require(value["artifact_scope"] == "abstract_behavior" or value["target"] is not None, "missing_target")
    for key in ("explicit_overrides", "resolved_defaults", "resolved_bindings", "implementation_constraints", "preferences", "parameter_metadata"):
        C._object(value[key])
    C._require(value["parameter_metadata"].keys() == value["resolved_bindings"].keys(), "parameter_metadata_coverage")
    declarations = {node["attributes"]["name"]: node for node in value["intent"]["nodes"] if node["kind"] == "parameter"}
    C._require(value["explicit_overrides"].keys() <= declarations.keys(), "unknown_parameter")
    defaults, bindings, overrides = {}, {}, {}
    for key, node in declarations.items():
        if key in value["explicit_overrides"]:
            override = value["explicit_overrides"][key]
            _binding(override, C._dtype(node["data_type"]))
            from biocompiler.semantics.types import TypeSpec, decode_binding
            normalized = decode_binding(override, TypeSpec.from_dict(node["data_type"])).to_dict()
            overrides[key] = normalized
            bindings[key] = normalized
        else:
            C._require(node["attributes"]["bound"], "unbound_parameter")
            defaults[key] = bindings[key] = node["attributes"]["default"]
    C._require(_same(value["explicit_overrides"], overrides), "noncanonical_override")
    C._require(_same(value["resolved_defaults"], defaults), "resolved_defaults_mismatch")
    C._require(_same(value["resolved_bindings"], bindings), "resolved_bindings_mismatch")
    for metadata in value["parameter_metadata"].values():
        metadata = _schema(metadata, "biocompiler.binding_metadata.v0.1", {"category", "provenance", "allowed_variation"})
        C._require(C._string(metadata["category"]) in {"user_selected", "compiler_selected", "measured", "uncertain"}, "invalid_choice")
        C._object(metadata["provenance"])
        if metadata["allowed_variation"] is not None:
            raw = C._object(metadata["allowed_variation"])
            dtype = C._dtype(_get(raw, "type"))
            C._require(dtype["kind"] == "interval", "invalid_allowed_variation")
            _binding(raw, dtype)
    provenance = _schema(value["provenance"], "biocompiler.elaboration_provenance.v0.1", {"source_identities", "dependency_identities", "external_inputs", "locations", "recorded_at"})
    for key in ("source_identities", "dependency_identities", "external_inputs", "locations"):
        C._object(provenance[key])
    for key in ("source_identities", "dependency_identities", "locations"):
        for name, identity in provenance[key].items():
            C._name(name)
            C._name(identity)
    if provenance["recorded_at"] is not None:
        C._name(provenance["recorded_at"])


def _operation(node: dict) -> None:
    kind, attrs = node["kind"], node["attributes"]
    if kind == "role":
        C._fields(attrs, {"name", "cell_type", "engineering"})
        C._require(attrs["engineering"] == "in_vivo", "behavior_operation")
        C._name(attrs["name"])
        C._name(attrs["cell_type"])
    elif kind in {"scope", "signal"}:
        C._fields(attrs, {"name", "scope"} | ({"observation"} if kind == "signal" else set()))
        C._require(isinstance(attrs["scope"], str) and attrs["scope"] in {"contact", "environment", "internal", "external"}, "behavior_operation")
        if kind == "scope":
            C._require(attrs["name"] == attrs["scope"], "behavior_operation")
        else:
            C._require(attrs["observation"] == "signal" or (attrs["observation"] == "marker" and attrs["scope"] == "contact"), "behavior_operation")
            C._name(attrs["name"])
    elif kind == "qualitative":
        C._fields(attrs, {"band"})
        C._require(isinstance(attrs["band"], str) and attrs["band"] in {"present", "high", "low"}, "behavior_operation")
    elif kind == "parameter":
        C._fields(attrs, {"name", "bound", "default"})
        C._require(attrs["bound"] is True, "behavior_operation")
        C._name(attrs["name"])
    elif kind == "secretion":
        C._fields(attrs, {"name", "product", "default", "activity"})
        C._require(attrs["activity"] == "requires_rule_or_controller", "behavior_operation")
        C._name(attrs["name"])
        C._name(attrs["product"])
        _boolean(attrs["default"])
    elif kind == "action.secrete":
        C._fields(attrs, {"ongoing", "rate"})
        C._require(attrs["ongoing"] is True, "behavior_operation")
        C._require(isinstance(attrs["rate"], str) and attrs["rate"] in {"unspecified", "expression"}, "behavior_operation")
    elif kind == "rule":
        C._fields(attrs, {"trigger", "execution", "priority", "ongoing_activation", "impulse_activation", "state_assignment"}, {"name", "ongoing_duration"})
        C._require(isinstance(attrs["trigger"], str) and attrs["trigger"] in {"condition", "event"}, "behavior_operation")
        C._require(attrs["execution"] == "concurrent" and attrs["priority"] == "none", "behavior_operation")
        expected = ("level", "onset", "level") if attrs["trigger"] == "condition" else ("explicit_duration", "event", "event")
        C._require(tuple(attrs[key] for key in ("ongoing_activation", "impulse_activation", "state_assignment")) == expected, "behavior_operation")
        C._require(("ongoing_duration" not in attrs) if attrs["trigger"] == "condition" else attrs.get("ongoing_duration") == "explicit", "behavior_operation")
        if "name" in attrs:
            C._name(attrs["name"])


def _behavior(value: Any) -> None:
    value = C._fields(value, {"schema_version", "name", "nodes", "roots", "source_fingerprint", "requirements", "source_links", "policies", "parameter_bindings"})
    C._require(isinstance(value["schema_version"], str) and value["schema_version"] in {"biocompiler.behavior.v0.1", "biocompiler.behavior.v0.2"}, "unsupported_behavior_profile")
    nodes = C._array(value["nodes"])
    for node in nodes:
        C._fields(node, {"id", "kind", "inputs", "attributes", "data_type", "role", "contact_bound", "requirement_ids"}, {"source"})
    _intent({"schema_version": "biocompiler.intent.v0.1", "name": value["name"], "roots": value["roots"],
        "nodes": [{key: item for key, item in node.items() if key not in {"contact_bound", "requirement_ids"}} for node in nodes]})
    for node in nodes:
        _operation(node)
        names = _names(node["requirement_ids"])
        C._require(len(set(names)) == len(names), "behavior_requirements")
        _boolean(node["contact_bound"])
    fingerprint = C._string(value["source_fingerprint"])
    C._require(len(fingerprint) == 64 and all(c in "0123456789abcdef" for c in fingerprint), "behavior_source_fingerprint")
    C._object(value["policies"])
    C._object(value["parameter_bindings"])
    for requirement in C._array(value["requirements"]):
        requirement = C._fields(requirement, {"id", "kind", "source_node_id", "lineage"}, {"source"})
        C._require(isinstance(requirement["kind"], str) and requirement["kind"] in {"rule", "state", "memory"}, "behavior_requirements")
        names = _names(requirement["lineage"])
        C._require(len(set(names)) == len(names), "behavior_requirements")
        C._name(requirement["id"])
        C._name(requirement["source_node_id"])
        _source(requirement.get("source"))
    for lineage in C._object(value["source_links"]).values():
        _names(lineage)


_SEMANTIC = {
    "Behavior roots must include exactly all executable declarations.": "behavior_roots",
    "Incomplete or inconsistent source lineage.": "behavior_lineage",
    "Requirements must preserve every rule, state and memory declaration.": "behavior_requirements",
    "Parameter bindings disagree with the executable graph.": "behavior_bindings",
    "Unknown or modified execution policies.": "behavior_policy",
    "Contract and operating domain must bind the same role.": "realization_request_role",
    "Contract must refer to this exact verified Behavior fingerprint.": "realization_request_behavior_identity",
    "source_identity: The source fingerprint and program identity must match.": "lowering_source_identity",
    "authoritative_bindings: Output bindings must exactly match the frozen input defaults and explicit overrides.": "lowering_authoritative_bindings",
}
for _identity in range(1, 9):
    _node = f"n{_identity:06}"
    _SEMANTIC[f"Incorrect contact binding at {_node}."] = "behavior_contact"
    _SEMANTIC[f"Incorrect requirement mapping at {_node}."] = "behavior_requirements"
    _SEMANTIC[f"source:{_node}: Authoring source location must be retained."] = "lowering_source_location"


def expected_native_code(call: Mapping[str, Any], operation: str, value: Any) -> str | None:
    assert operation == "RealizationRequest", operation
    if call["outcome"] == "returned":
        return None
    assert call["outcome"] == "raised", call["outcome"]
    error = call["error"]
    assert (error["module"], error["type"]) in {
        ("biocompiler.errors", "SerializationError"), ("biocompiler.errors", "LoweringVerificationError"),
        ("biocompiler.errors", "UnsupportedBehaviorError"), ("builtins", "TypeError")}, error
    message = error["message"].removeprefix("Invalid RealizationRequest: ")
    assert message in _OBSERVED_MESSAGES, f"Unclassified request source diagnostic: {message}"
    try:
        raw = _schema(value, "biocompiler.realization_request.v0.1", {"build_request", "behavior", "contract", "domain"})
        _build(raw["build_request"])
        _behavior(raw["behavior"])
        C._record("BehaviorContract", raw["contract"])
        C._record("OperatingDomain", raw["domain"])
    except C._Code as failure:
        return failure.code
    if message in _SEMANTIC:
        return _SEMANTIC[message]
    if message in C._CONTEXT:
        return "invalid_realization_contract"
    if message in C._MEASUREMENT:
        return "invalid_measurement_contract"
    if "canonical value disagrees with its value and unit." in message:
        return "canonical_value_mismatch"
    if message.startswith("n000"):
        assert any(message.startswith(f"n{index:06} ({kind}): ") for index, kind in
            ((1, "role"), (3, "scope"), (4, "signal"), (5, "qualitative"), (6, "secretion"), (7, "action.secrete"), (8, "rule")))
        return "behavior_type" if message.endswith("Incompatible result type.") else "behavior_operation"
    if message.startswith("Unknown source rule execution or priority semantics.") or message.startswith("Unknown source trigger semantics."):
        return "unsupported_lowering_rule_policy"
    if message.startswith("Operation 'unsupported_operation' needs an additional execution profile or semantic refinement."):
        return "unsupported_lowering_operation"
    if message == "cannot use 'mappingproxy' as a set element (unhashable type: 'dict')":
        assert any(node["kind"] == "rule" and isinstance(node["attributes"].get("trigger"), dict)
                   for node in raw["build_request"]["intent"]["nodes"])
        return "unsupported_lowering_rule_policy"
    raise AssertionError(f"Unclassified request native rejection: {message}")


# Exact observed source messages bind this projection to the retained campaign.
# Structural inputs still select native codes above; this inventory never maps
# a source exception generically to a native rejection.
_OBSERVED_MESSAGES = frozenset(
    (
        'A behavior contract requires nonempty response requirements.',
        'A target must declare at least one compartment.',
        'Allowed Boolean values must be unique.',
        'Allowed variation must be an object.',
        'Behavior action specification id must be a nonempty string.',
        'Behavior contract id must be a nonempty string.',
        'Behavior fingerprint must be SHA-256 hex.',
        'Behavior node must be an object.',
        'Behavior roots must include exactly all executable declarations.',
        'Behavior rule id must be a nonempty string.',
        'Behavior signal id must be a nonempty string.',
        'Binding provenance must be an object.',
        'Capabilities must be an array.',
        'Compartments must be a nonempty string.',
        'Compartments must be an array.',
        'Contact binding must be Boolean.',
        'Contract and operating domain must bind the same role.',
        'Contract must refer to this exact verified Behavior fingerprint.',
        'Dangling root reference in intent program.',
        'Each node must be an object.',
        'Incomplete or inconsistent source lineage.',
        'Incorrect contact binding at n000001.',
        'Incorrect contact binding at n000002.',
        'Incorrect contact binding at n000003.',
        'Incorrect contact binding at n000004.',
        'Incorrect contact binding at n000005.',
        'Incorrect contact binding at n000006.',
        'Incorrect contact binding at n000007.',
        'Incorrect contact binding at n000008.',
        'Incorrect requirement mapping at n000001.',
        'Incorrect requirement mapping at n000003.',
        'Incorrect requirement mapping at n000004.',
        'Incorrect requirement mapping at n000005.',
        'Incorrect requirement mapping at n000006.',
        'Incorrect requirement mapping at n000007.',
        'Incorrect requirement mapping at n000008.',
        'Input reference must be a non-empty string.',
        'Intent program must be an object.',
        "Invalid BuildRequest: cannot use 'dict' as a set element (unhashable type: 'dict')",
        "Invalid BuildRequest: cannot use 'list' as a set element (unhashable type: 'list')",
        'Invalid activation delay: A quantity requires a real number, not a Boolean or arbitrary object.',
        'Invalid activation delay: A scalar binding requires a nonempty unit.',
        "Invalid activation delay: A scalar binding's canonical value disagrees with its value and unit.",
        'Invalid activation delay: A serialized binding must be an object.',
        'Invalid activation delay: A serialized scalar binding has invalid fields or kind.',
        'Invalid activation delay: A serialized type has missing or unknown fields.',
        'Invalid activation delay: A serialized type must be an object.',
        'Invalid activation delay: A type requires nonempty kind and name strings.',
        'Invalid activation delay: Dimensions require names and integer powers.',
        'Invalid activation delay: Expected Duration, got Duration.',
        'Invalid activation delay: Type dimensions must be an object and arguments must be an array.',
        'Invalid active range: A quantity requires a real number, not a Boolean or arbitrary object.',
        'Invalid active range: A scalar binding requires a nonempty unit.',
        "Invalid active range: A scalar binding's canonical value disagrees with its value and unit.",
        'Invalid active range: A serialized binding must be an object.',
        'Invalid active range: A serialized interval binding has invalid fields or kind.',
        'Invalid active range: A serialized scalar binding has invalid fields or kind.',
        'Invalid active range: A serialized type has missing or unknown fields.',
        'Invalid active range: A serialized type must be an object.',
        'Invalid active range: A type requires nonempty kind and name strings.',
        'Invalid active range: Type dimensions must be an object and arguments must be an array.',
        'Invalid active range: interval requires 1 scalar type argument(s).',
        'Invalid allowed variation: A serialized type must be an object.',
        'Invalid behavior node fields.',
        "Invalid behavior operation: cannot use 'mappingproxy' as a set element (unhashable type: 'dict')",
        'Invalid behavior program fields.',
        'Invalid data type on node n000001: A serialized type has missing or unknown fields.',
        'Invalid data type on node n000002: A serialized type has missing or unknown fields.',
        'Invalid data type on node n000002: A type requires nonempty kind and name strings.',
        'Invalid data type on node n000002: Type dimensions must be an object and arguments must be an array.',
        'Invalid data type on node n000003: A serialized type has missing or unknown fields.',
        'Invalid data type on node n000004: A serialized type has missing or unknown fields.',
        'Invalid data type on node n000004: A type requires nonempty kind and name strings.',
        'Invalid data type on node n000004: Type dimensions must be an object and arguments must be an array.',
        'Invalid data type on node n000005: A serialized type has missing or unknown fields.',
        'Invalid data type on node n000005: A type requires nonempty kind and name strings.',
        'Invalid data type on node n000005: Type dimensions must be an object and arguments must be an array.',
        'Invalid data type on node n000006: A serialized type has missing or unknown fields.',
        'Invalid data type on node n000007: A serialized type has missing or unknown fields.',
        'Invalid data type on node n000008: A serialized type has missing or unknown fields.',
        'Invalid deactivation delay: A quantity requires a real number, not a Boolean or arbitrary object.',
        'Invalid deactivation delay: A scalar binding requires a nonempty unit.',
        "Invalid deactivation delay: A scalar binding's canonical value disagrees with its value and unit.",
        'Invalid deactivation delay: A serialized binding must be an object.',
        'Invalid deactivation delay: A serialized scalar binding has invalid fields or kind.',
        'Invalid deactivation delay: A serialized type has missing or unknown fields.',
        'Invalid deactivation delay: A serialized type must be an object.',
        'Invalid deactivation delay: A type requires nonempty kind and name strings.',
        'Invalid deactivation delay: Dimensions require names and integer powers.',
        'Invalid deactivation delay: Expected Duration, got Duration.',
        'Invalid deactivation delay: Type dimensions must be an object and arguments must be an array.',
        'Invalid fields in BehaviorContract.',
        'Invalid fields in BindingMetadata.',
        'Invalid fields in BuildRequest.',
        'Invalid fields in ElaborationProvenance.',
        'Invalid fields in InputDomain.',
        'Invalid fields in Observable.',
        'Invalid fields in OperatingDomain.',
        'Invalid fields in ResponseRequirement.',
        'Invalid fields in intent node.',
        'Invalid fields in intent program.',
        'Invalid fields in source location.',
        'Invalid fields in target context.',
        'Invalid inactive range: A quantity requires a real number, not a Boolean or arbitrary object.',
        'Invalid inactive range: A scalar binding requires a nonempty unit.',
        "Invalid inactive range: A scalar binding's canonical value disagrees with its value and unit.",
        'Invalid inactive range: A serialized binding must be an object.',
        'Invalid inactive range: A serialized interval binding has invalid fields or kind.',
        'Invalid inactive range: A serialized scalar binding has invalid fields or kind.',
        'Invalid inactive range: A serialized type has missing or unknown fields.',
        'Invalid inactive range: A serialized type must be an object.',
        'Invalid inactive range: A type requires nonempty kind and name strings.',
        'Invalid inactive range: Type dimensions must be an object and arguments must be an array.',
        'Invalid inactive range: interval requires 1 scalar type argument(s).',
        'Invalid minimum horizon: A quantity requires a real number, not a Boolean or arbitrary object.',
        'Invalid minimum horizon: A scalar binding requires a nonempty unit.',
        "Invalid minimum horizon: A scalar binding's canonical value disagrees with its value and unit.",
        'Invalid minimum horizon: A serialized binding must be an object.',
        'Invalid minimum horizon: A serialized scalar binding has invalid fields or kind.',
        'Invalid minimum horizon: A serialized type has missing or unknown fields.',
        'Invalid minimum horizon: A serialized type must be an object.',
        'Invalid minimum horizon: A type requires nonempty kind and name strings.',
        'Invalid minimum horizon: Dimensions require names and integer powers.',
        'Invalid minimum horizon: Expected Duration, got Duration.',
        'Invalid minimum horizon: Type dimensions must be an object and arguments must be an array.',
        'Invalid observable type: A serialized type has missing or unknown fields.',
        'Invalid observable type: A serialized type must be an object.',
        'Invalid observable type: A type requires nonempty kind and name strings.',
        'Invalid observable type: Type dimensions must be an object and arguments must be an array.',
        'Invalid requirement fields.',
        'Invalid requirement reference.',
        'Invalid target context: 0 is not a valid PayloadFormat',
        'Invalid target context: None is not a valid PayloadFormat',
        'Invalid target context: Target context id and version must be nonempty strings.',
        'Invalid target context: True is not a valid PayloadFormat',
        'Invalid target context: [] is not a valid PayloadFormat',
        'Invalid target context: {} is not a valid PayloadFormat',
        'Invalid typed value on node n000002: A quantity requires a real number, not a Boolean or arbitrary object.',
        'Invalid typed value on node n000002: A scalar binding requires a nonempty unit.',
        "Invalid typed value on node n000002: A scalar binding's canonical value disagrees with its value and unit.",
        'Invalid typed value on node n000002: A serialized binding must be an object.',
        'Invalid typed value on node n000002: A serialized scalar binding has invalid fields or kind.',
        'Invalid typed value on node n000002: A serialized type has missing or unknown fields.',
        'Invalid typed value on node n000002: A serialized type must be an object.',
        'Invalid typed value on node n000002: A type requires nonempty kind and name strings.',
        'Invalid typed value on node n000002: Type dimensions must be an object and arguments must be an array.',
        'Lineage reference must be a nonempty string.',
        'Node attributes must be an object.',
        'Node data_type must be an object or null.',
        'Node id must be a non-empty string.',
        'Node inputs must be an array.',
        'Node kind must be a non-empty string.',
        'Nodes and requirements must be arrays.',
        'Observable compartment must be a nonempty string.',
        'Observable id must be a nonempty string.',
        'Observable role must be a nonempty string.',
        'Observable scope must be cell or contact.',
        'Operating domain id must be a nonempty string.',
        'Operating domain inputs must be an array.',
        'Operating domain requires a nonempty array of InputDomain records.',
        'Operating domain role must be a nonempty string.',
        'Operating domain version must be a nonempty string.',
        "Operation 'unsupported_operation' needs an additional execution profile or semantic refinement. [n000008] at /__biocompiler_capture__/tests/test_build_request.py:49",
        'Parameter bindings disagree with the executable graph.',
        'Parameter bindings must be an object.',
        'Parameter metadata must be an object.',
        'Parameter name must be a non-empty string.',
        'Parameters must declare whether a default is bound.',
        'Program name must be a non-empty string.',
        'Program nodes must be an array.',
        'Program roots must be an array.',
        'Provenance timestamp must be a nonempty string.',
        'Qualitative input domain must be a nonempty array of Booleans.',
        'Required capabilities must be an array.',
        'Requirement id must be a nonempty string.',
        'Requirement ids must be an array.',
        'Requirement lineage must be an array.',
        'Requirement source node must be a nonempty string.',
        'Requirements must preserve every rule, state and memory declaration.',
        'Resolved bindings disagree with independent defaults and overrides.',
        'Resolved defaults disagree with the frozen intent.',
        'Resources must be an object.',
        'Response requirement id must be a nonempty string.',
        'Response requirements must be an array.',
        'Role reference must be a non-empty string.',
        'Root reference must be a non-empty string.',
        'Serialized metadata must cover every design parameter.',
        'Source file must be a non-empty string.',
        'Source fingerprint must be SHA-256 hex.',
        'Source function must be a non-empty string.',
        'Source line must be a positive integer.',
        'Source links must map node ids to lineage arrays.',
        'Source location must be an object.',
        'This artifact scope requires an explicit target context.',
        'Unknown behavior requirement kind.',
        'Unknown design-value category; runtime observations must remain graph signals.',
        'Unknown input observation field.',
        'Unknown or modified execution policies.',
        'Unknown source rule execution or priority semantics. [n000008] at /__biocompiler_capture__/tests/test_build_request.py:49',
        'Unknown source trigger semantics. [n000008] at /__biocompiler_capture__/tests/test_build_request.py:49',
        'Unsupported Behavior execution profile.',
        'Unsupported BehaviorContract schema.',
        'Unsupported BindingMetadata schema.',
        'Unsupported BuildRequest schema.',
        'Unsupported ElaborationProvenance schema.',
        'Unsupported InputDomain schema.',
        'Unsupported Observable schema.',
        'Unsupported OperatingDomain schema.',
        'Unsupported RealizationRequest schema.',
        'Unsupported ResponseRequirement schema.',
        'Unsupported behavior schema.',
        'Unsupported build artifact scope.',
        'Unsupported intent schema: 0.',
        'Unsupported intent schema: None.',
        'Unsupported intent schema: True.',
        'Unsupported intent schema: [].',
        'Unsupported intent schema: {}.',
        'Unsupported target schema.',
        'authoritative_bindings: Output bindings must exactly match the frozen input defaults and explicit overrides.',
        "cannot use 'dict' as a set element (unhashable type: 'dict')",
        "cannot use 'list' as a set element (unhashable type: 'list')",
        "cannot use 'mappingproxy' as a set element (unhashable type: 'dict')",
        'dependency_identities must be an object.',
        'explicit_overrides must be an object.',
        'external_inputs must be an object.',
        'implementation_constraints must be an object.',
        'locations must be an object.',
        'max_contacts must be a nonnegative integer or None.',
        'n000001 (role): Invalid operation attributes.',
        'n000001 (role): Invalid role declaration.',
        'n000003 (scope): Expected 1 inputs.',
        'n000003 (scope): Invalid operation attributes.',
        'n000003 (scope): Operation requires a cell role.',
        'n000003 (scope): Unknown or inconsistent scope.',
        'n000004 (signal): Expected 1 inputs.',
        'n000004 (signal): Incompatible result type.',
        'n000004 (signal): Invalid observation kind.',
        'n000004 (signal): Invalid operation attributes.',
        'n000004 (signal): Invalid signal scope.',
        'n000004 (signal): Operation requires a cell role.',
        'n000005 (qualitative): Expected 1 inputs.',
        'n000005 (qualitative): Incompatible result type.',
        'n000005 (qualitative): Invalid operation attributes.',
        'n000005 (qualitative): Invalid qualitative observation.',
        'n000005 (qualitative): Operation requires a cell role.',
        'n000006 (secretion): Expected 1 inputs.',
        'n000006 (secretion): Invalid operation attributes.',
        'n000006 (secretion): Invalid secretion declaration.',
        'n000006 (secretion): Operation requires a cell role.',
        'n000007 (action.secrete): Expected 1 inputs.',
        'n000007 (action.secrete): Invalid operation attributes.',
        'n000007 (action.secrete): Invalid rate mode.',
        'n000007 (action.secrete): Invalid secretion action.',
        'n000007 (action.secrete): Operation requires a cell role.',
        'n000008 (rule): Invalid operation attributes.',
        'n000008 (rule): Invalid rule activation policies.',
        'n000008 (rule): Invalid rule trigger.',
        'n000008 (rule): Operation requires a cell role.',
        'n000008 (rule): Rule needs a trigger and actions.',
        'n000008 (rule): Unsupported rule concurrency.',
        'parameter nodes require a declared data type.',
        'preferences must be an object.',
        'resolved_defaults must be an object.',
        'source:n000001: Authoring source location must be retained.',
        'source:n000002: Authoring source location must be retained.',
        'source:n000003: Authoring source location must be retained.',
        'source:n000004: Authoring source location must be retained.',
        'source:n000005: Authoring source location must be retained.',
        'source:n000006: Authoring source location must be retained.',
        'source:n000007: Authoring source location must be retained.',
        'source:n000008: Authoring source location must be retained.',
        'source_identities must be an object.',
        'source_identity: The source fingerprint and program identity must match.',
    )
)

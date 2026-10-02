"""Precise fixture-only projections for retained component selection rejections.

Native imports are classified from the actual complete nested rejection leaf;
original exception messages remain in the corpus. Unknown observations fail.
This tool is not an acceptance implementation or a production error adapter.
"""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import fields
from unittest.mock import patch


def _require(value, message):
    if not value:
        raise AssertionError(message)


def _string_code(value, code="invalid_name"):
    return code if isinstance(value, str) else "invalid_type"


def _leaf(operation, value):
    from biocompiler.registry.components import SelectionRequest, SelectionAlternative, SelectionResult
    from biocompiler.semantics.admission import AdmissionAssessment
    from biocompiler.semantics.context import TargetContext
    from biocompiler.semantics.component_contracts import OperatingDomain, ValueDomain
    from biocompiler.semantics.types import TypeSpec
    from biocompiler.ir.component_contracts import PinnedIdentity
    from biocompiler.ir.components import ComponentLock
    classes = (SelectionRequest, SelectionAlternative, SelectionResult, AdmissionAssessment,
               TargetContext, OperatingDomain, ValueDomain, TypeSpec, PinnedIdentity, ComponentLock)
    observed = []
    def wrapper(cls):
        original = cls.from_dict.__func__
        def decode(actual_cls, data):
            try:
                return original(actual_cls, data)
            except Exception as error:
                observed.append((actual_cls, data, str(error)))
                raise
        return classmethod(decode)
    with ExitStack() as patches:
        for cls in classes:
            patches.enter_context(patch.object(cls, "from_dict", wrapper(cls)))
        try:
            next(cls for cls in classes if cls.__name__ == operation).from_dict(value)
        except Exception:
            _require(observed, "Unobserved selection rejection leaf")
            return observed[0]
    return None


def expected_code(call, operation, value):
    if call["outcome"] == "returned":
        return None
    _require(call["outcome"] == "raised", "Unknown selection observation outcome")
    error = call["error"]
    _require(error["module"] == "biocompiler.errors" and error["type"] == "SerializationError", str(error))
    _require((call["api"], error["message"]) in _OBSERVED,
             "Unclassified original selection exception: " + call["api"] + ": " + error["message"])
    _require(operation in {"SelectionRequest", "SelectionAlternative", "SelectionResult"}, operation)
    leaf = _leaf(operation, value)
    if leaf is None:
        _require(call["api"].endswith(".__init__"), "Accepted serialized import rejection")
        return "python_type_boundary"
    cls, data, message = leaf
    kind = cls.__name__
    if kind == "AdmissionAssessment":
        from tools.realization_admission_codes import expected_code as classify
        nested = dict(call, api="AdmissionAssessment.from_dict", error=dict(error, message=message))
        return classify(nested, kind, data)
    if message.startswith("Invalid fields in ") or message == "A serialized type has missing or unknown fields.":
        if not isinstance(data, dict):
            return "invalid_type"
        expected = {field.name for field in fields(cls)}
        if hasattr(cls, "schema_version"):
            expected.add("schema_version")
        if kind == "TargetContext":
            expected = {"schema_version", "context_id", "context_version", "payload_format", "capabilities", "compartments", "resources"}
        required = {"kind", "name"} if kind == "TypeSpec" else expected
        if required - set(data):
            return "missing_field"
        if set(data) - expected:
            return "unknown_field"
        raise AssertionError("No field mismatch at " + kind)
    if message.startswith("Unsupported") and "schema" in message.lower():
        return _string_code(data["schema_version"], "unsupported_identity_schema" if kind == "PinnedIdentity" else "unsupported_schema")
    if kind == "TypeSpec":
        if message in {"A serialized type must be an object.", "Type dimensions must be an object and arguments must be an array."}:
            return "invalid_type"
        if message == "A type requires nonempty kind and name strings.":
            return "invalid_type" if not all(isinstance(data[k], str) for k in ("kind", "name")) else "invalid_type_spec"
        if message == "Unknown type kind: 'unexpected'.":
            return "invalid_type_spec"
    labels = {"Component ID":"component_id", "Component version":"version", "implementation_role":"implementation_role",
              "instance_id":"instance_id", "classification":"classification", "component_id":"component_id",
              "component_version":"component_version", "node_id":"node_id", "version":"version", "Domain unit":"unit"}
    suffix = " must be a nonempty string."
    if message.endswith(suffix):
        label = message[:-len(suffix)]
        if label in labels:
            return _string_code(data[labels[label]])
        arrays = {"Selection reasons":"reasons", "preferred_component_ids":"preferred_component_ids",
                  "required_guarantees":"required_guarantees", "Compartments":"compartments", "Capabilities":"capabilities"}
        if label in arrays:
            invalid = next(item for item in data[arrays[label]] if not isinstance(item, str) or not item.strip())
            return _string_code(invalid)
    hashes = {"Component fingerprint must be a SHA-256 identity.":"content_fingerprint",
              "Registry fingerprint must be a SHA-256 identity.":"registry_fingerprint",
              "Selection request fingerprint must be a SHA-256 identity.":"request_fingerprint",
              "A component lock requires a SHA-256 content identity.":"content_fingerprint"}
    if message in hashes:
        return _string_code(data[hashes[message]], "component_registry" if kind == "ComponentLock" else "component_selection")
    if message == "Invalid alternative status.":
        return _string_code(data["status"], "component_selection")
    if message == "Preferences can rank only eligible alternatives.":
        return "component_selection" if data["preference_rank"] is None or type(data["preference_rank"]) is int else "invalid_type"
    if message in {"Selection alternatives require rationale.", "A hard version pin requires a component ID.",
                   "Selection must choose the deterministically ranked eligible alternative."}:
        return "component_selection"
    if message in {"Registry records must be an array.", "Domain constraints must be an object.", "Domain values must be an array.",
                   "Selection reasons must be an array.", "preferred_component_ids must be an array.",
                   "required_guarantees must be an array.", "Capabilities must be an array.", "Compartments must be an array.",
                   "Resources must be an object."}:
        return "invalid_type"
    if kind == "TargetContext":
        if message == "Invalid target context: Target context id and version must be nonempty strings.":
            invalid = next(data[key] for key in ("context_id", "context_version") if not isinstance(data[key], str) or not data[key].strip())
            return _string_code(invalid)
        if message.startswith("Invalid target context:") and message.endswith("is not a valid PayloadFormat"):
            return _string_code(data["payload_format"], "invalid_choice")
        if message == "A target must declare at least one compartment.":
            return "invalid_target"
    if kind == "ValueDomain":
        if message == "Unsupported value domain kind.":
            return _string_code(data["kind"], "component_contract")
        if message in {"Domain lower bound exceeds upper bound.", "Scalar intervals require a scalar type and no Boolean values/reason.",
                       "Lower domain bound must be a finite number.", "Upper domain bound must be a finite number."}:
            return "component_contract"
    raise AssertionError("Unclassified native selection leaf: " + kind + ": " + message)


# Exact original capture signatures, retained independently of native codes.
_OBSERVED = {('SelectionAlternative.__init__', 'Component ID must be a nonempty string.'),
 ('SelectionAlternative.__init__', 'Component fingerprint must be a SHA-256 identity.'),
 ('SelectionAlternative.__init__', 'Component version must be a nonempty string.'),
 ('SelectionAlternative.__init__', 'Invalid alternative status.'),
 ('SelectionAlternative.__init__', 'Preferences can rank only eligible alternatives.'),
 ('SelectionAlternative.__init__', 'Selection alternatives require rationale.'),
 ('SelectionAlternative.__init__', 'Selection reasons must be a nonempty string.'),
 ('SelectionAlternative.__init__', 'Selection reasons must be an array.'),
 ('SelectionAlternative.from_dict', 'Component ID must be a nonempty string.'),
 ('SelectionAlternative.from_dict', 'Component fingerprint must be a SHA-256 identity.'),
 ('SelectionAlternative.from_dict', 'Component version must be a nonempty string.'),
 ('SelectionAlternative.from_dict', 'Invalid alternative status.'),
 ('SelectionAlternative.from_dict', 'Invalid fields in SelectionAlternative.'),
 ('SelectionAlternative.from_dict', 'Preferences can rank only eligible alternatives.'),
 ('SelectionAlternative.from_dict', 'Selection alternatives require rationale.'),
 ('SelectionAlternative.from_dict', 'Selection reasons must be a nonempty string.'),
 ('SelectionAlternative.from_dict', 'Selection reasons must be an array.'),
 ('SelectionAlternative.from_dict', 'Unsupported registry schema.'),
 ('SelectionRequest.__init__', 'A hard version pin requires a component ID.'),
 ('SelectionRequest.__init__', 'classification must be a nonempty string.'),
 ('SelectionRequest.__init__', 'component_id must be a nonempty string.'),
 ('SelectionRequest.__init__', 'component_version must be a nonempty string.'),
 ('SelectionRequest.__init__', 'implementation_role must be a nonempty string.'),
 ('SelectionRequest.__init__', 'instance_id must be a nonempty string.'),
 ('SelectionRequest.__init__', 'preferred_component_ids must be a nonempty string.'),
 ('SelectionRequest.__init__', 'preferred_component_ids must be an array.'),
 ('SelectionRequest.__init__', 'required_guarantees must be an array.'),
 ('SelectionRequest.from_dict', 'A hard version pin requires a component ID.'),
 ('SelectionRequest.from_dict', 'A target must declare at least one compartment.'),
 ('SelectionRequest.from_dict', 'Capabilities must be an array.'),
 ('SelectionRequest.from_dict', 'Compartments must be a nonempty string.'),
 ('SelectionRequest.from_dict', 'Compartments must be an array.'),
 ('SelectionRequest.from_dict', 'Domain constraints must be an object.'),
 ('SelectionRequest.from_dict', 'Domain lower bound exceeds upper bound.'),
 ('SelectionRequest.from_dict', 'Domain unit must be a nonempty string.'),
 ('SelectionRequest.from_dict', 'Domain values must be an array.'),
 ('SelectionRequest.from_dict',
  'Invalid component contract type: A serialized type has missing or unknown fields.'),
 ('SelectionRequest.from_dict',
  'Invalid component contract type: A serialized type must be an object.'),
 ('SelectionRequest.from_dict',
  'Invalid component contract type: A type requires nonempty kind and name strings.'),
 ('SelectionRequest.from_dict',
  'Invalid component contract type: Type dimensions must be an object and arguments must be an '
  'array.'),
 ('SelectionRequest.from_dict',
  "Invalid component contract type: Unknown type kind: 'unexpected'."),
 ('SelectionRequest.from_dict', 'Invalid fields in OperatingDomain.'),
 ('SelectionRequest.from_dict', 'Invalid fields in SelectionRequest.'),
 ('SelectionRequest.from_dict', 'Invalid fields in ValueDomain.'),
 ('SelectionRequest.from_dict', 'Invalid fields in target context.'),
 ('SelectionRequest.from_dict',
  "Invalid target context: 'unexpected' is not a valid PayloadFormat"),
 ('SelectionRequest.from_dict', 'Invalid target context: 0 is not a valid PayloadFormat'),
 ('SelectionRequest.from_dict', 'Invalid target context: False is not a valid PayloadFormat'),
 ('SelectionRequest.from_dict', 'Invalid target context: None is not a valid PayloadFormat'),
 ('SelectionRequest.from_dict',
  'Invalid target context: Target context id and version must be nonempty strings.'),
 ('SelectionRequest.from_dict', 'Invalid target context: [] is not a valid PayloadFormat'),
 ('SelectionRequest.from_dict', 'Invalid target context: {} is not a valid PayloadFormat'),
 ('SelectionRequest.from_dict', 'Lower domain bound must be a finite number.'),
 ('SelectionRequest.from_dict', 'Registry records must be an array.'),
 ('SelectionRequest.from_dict', 'Resources must be an object.'),
 ('SelectionRequest.from_dict',
  'Scalar intervals require a scalar type and no Boolean values/reason.'),
 ('SelectionRequest.from_dict', 'Unsupported OperatingDomain schema.'),
 ('SelectionRequest.from_dict', 'Unsupported ValueDomain schema.'),
 ('SelectionRequest.from_dict', 'Unsupported registry schema.'),
 ('SelectionRequest.from_dict', 'Unsupported target schema.'),
 ('SelectionRequest.from_dict', 'Unsupported value domain kind.'),
 ('SelectionRequest.from_dict', 'Upper domain bound must be a finite number.'),
 ('SelectionRequest.from_dict', 'classification must be a nonempty string.'),
 ('SelectionRequest.from_dict', 'component_id must be a nonempty string.'),
 ('SelectionRequest.from_dict', 'component_version must be a nonempty string.'),
 ('SelectionRequest.from_dict', 'implementation_role must be a nonempty string.'),
 ('SelectionRequest.from_dict', 'instance_id must be a nonempty string.'),
 ('SelectionRequest.from_dict', 'preferred_component_ids must be a nonempty string.'),
 ('SelectionRequest.from_dict', 'preferred_component_ids must be an array.'),
 ('SelectionRequest.from_dict', 'required_guarantees must be an array.'),
 ('SelectionResult.__init__', 'Registry fingerprint must be a SHA-256 identity.'),
 ('SelectionResult.__init__',
  'Selection must choose the deterministically ranked eligible alternative.'),
 ('SelectionResult.__init__', 'Selection request fingerprint must be a SHA-256 identity.'),
 ('SelectionResult.from_dict', 'A component lock requires a SHA-256 content identity.'),
 ('SelectionResult.from_dict', 'Admission decisions need explicit scope/reasons.'),
 ('SelectionResult.from_dict', 'Component ID must be a nonempty string.'),
 ('SelectionResult.from_dict', 'Component fingerprint must be a SHA-256 identity.'),
 ('SelectionResult.from_dict', 'Component version must be a nonempty string.'),
 ('SelectionResult.from_dict', 'Expected SHA-256 identity.'),
 ('SelectionResult.from_dict', 'Expected record array.'),
 ('SelectionResult.from_dict', 'Invalid admission boundary.'),
 ('SelectionResult.from_dict', 'Invalid alternative status.'),
 ('SelectionResult.from_dict', 'Invalid claim_scope.'),
 ('SelectionResult.from_dict', 'Invalid evidence_status.'),
 ('SelectionResult.from_dict', 'Invalid fields in AdmissionAssessment.'),
 ('SelectionResult.from_dict', 'Invalid fields in ComponentLock.'),
 ('SelectionResult.from_dict', 'Invalid fields in SelectionAlternative.'),
 ('SelectionResult.from_dict', 'Invalid fields in SelectionResult.'),
 ('SelectionResult.from_dict', 'Invalid human_therapeutic_admission.'),
 ('SelectionResult.from_dict', 'Invalid intended use.'),
 ('SelectionResult.from_dict', 'Invalid policy.'),
 ('SelectionResult.from_dict', 'Preferences can rank only eligible alternatives.'),
 ('SelectionResult.from_dict', 'Registry fingerprint must be a SHA-256 identity.'),
 ('SelectionResult.from_dict', 'Registry records must be an array.'),
 ('SelectionResult.from_dict', 'Selection alternatives require rationale.'),
 ('SelectionResult.from_dict',
  'Selection must choose the deterministically ranked eligible alternative.'),
 ('SelectionResult.from_dict', 'Selection reasons must be a nonempty string.'),
 ('SelectionResult.from_dict', 'Selection reasons must be an array.'),
 ('SelectionResult.from_dict', 'Selection request fingerprint must be a SHA-256 identity.'),
 ('SelectionResult.from_dict', 'Unsupported AdmissionAssessment schema.'),
 ('SelectionResult.from_dict', 'Unsupported admission decision.'),
 ('SelectionResult.from_dict', 'Unsupported component-lock schema.'),
 ('SelectionResult.from_dict', 'Unsupported registry schema.'),
 ('SelectionResult.from_dict', 'component_fingerprints must be a nonempty string.'),
 ('SelectionResult.from_dict', 'component_fingerprints must be an array.'),
 ('SelectionResult.from_dict', 'component_id must be a nonempty string.'),
 ('SelectionResult.from_dict', 'diagnostics must be a nonempty string.'),
 ('SelectionResult.from_dict', 'diagnostics must be an array.'),
 ('SelectionResult.from_dict', 'node_id must be a nonempty string.'),
 ('SelectionResult.from_dict', 'version must be a nonempty string.')}

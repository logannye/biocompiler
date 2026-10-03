"""Strict transport for independently checked native realization operations.

This module owns transport shape, identity and resource negotiation only. It
imports no Python authoring, lowering, model evaluator, producer or checker.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Callable, Literal, cast

from biocompiler.core_client import (
    LIMITS, CoreCapabilities, CoreClient, CoreProtocolError, CoreResponse,
    JsonValue, _names, _object, decode_json, encode_json,
)

# Frozen contract from migration-realization-protocol-profiles.json. Keep the
# complete records in the installed package; no checkout-relative runtime I/O.
_PROFILES_JSON = '{"component_assembly":{"assessment_encoding":"python-json-v1","assessment_schema":"biocompiler.component_link_result.v0.3","authority_identity_fields":["request_fingerprint","request_artifact_fingerprint","history_ascii_fingerprint","candidate_fingerprint","assembly_fingerprint"],"claim_scope":"Fresh source, actual synthetic candidate, exact component correspondence, linking and finite-history acceptance only; no search completeness, sequence emission, empirical function or human-use admission.","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"dependency_encoding":"python-json-v1","dependency_schema_version_field":false,"history_codec":{"boundary_version":"biocompiler.native_execution_data.v0.1","frame_fields":["time","signals","contacts"],"numeric_sample_shorthand":true,"sample_fields":["value","present","high","low"],"schema_version_field":false},"implementation":"biocompiler.ocaml.component_assembly_checker.v0.1","input_schemas":{"assembly":["biocompiler.component_assembly.v0.2"],"candidate":["biocompiler.synthetic_candidate.v0.4"],"expected_request":["biocompiler.realization_request.v0.1"]},"limits_fields":["max_work","max_monitor_items","max_request_bytes","max_report_bytes","max_report_nodes"],"limits_null":"fixed_defaults","operations":["verify-component-assembly","replay-component-assembly"],"payload_fields":{"replay-component-assembly":["profile","limits","expected_request","candidate","assembly","history","until","assessment"],"verify-component-assembly":["profile","limits","expected_request","candidate","assembly","history","until"]},"profile":"biocompiler.core.component_assembly.v1","resources":{"checker":{"behavior":{"composition":{"diagnostic_order":"pair_sorted_unknown_dependency_binding_and_unknown_resource_binding_only.v1","intermediate_accounting":"cumulative_no_refunds","max_input_bytes":16777216,"max_input_nodes":250000,"max_rational_bits":8192,"max_report_bytes":33554432,"max_report_nodes":250000,"max_retained_intermediate_items":100000,"max_work":50000000,"profile":"biocompiler.composition_check.resources.v1","rational_arithmetic":"exact_Fraction_of_Python_decimal_spelling"},"profile":"biocompiler.component_behavior_checker.resources.v1","realization":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_translated_history_bytes":16777216,"max_translated_history_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true","translated_history_work":"same_shared_work_utf8_bytes_plus_key_value_nodes_before_import"},"shared":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true"}},"composition":{"diagnostic_order":"pair_sorted_unknown_dependency_binding_and_unknown_resource_binding_only.v1","intermediate_accounting":"cumulative_no_refunds","max_input_bytes":16777216,"max_input_nodes":250000,"max_rational_bits":8192,"max_report_bytes":33554432,"max_report_nodes":250000,"max_retained_intermediate_items":100000,"max_work":50000000,"profile":"biocompiler.composition_check.resources.v1","rational_arithmetic":"exact_Fraction_of_Python_decimal_spelling"},"private_authority":"cumulative_derived_fragments_share_report_bytes_nodes_and_work","profile":"biocompiler.component_assembly_checker.resources.v1","shared":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true"},"synthetic":{"profile":"biocompiler.synthetic_candidate_checker.resources.v1","realization":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_translated_history_bytes":16777216,"max_translated_history_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true","translated_history_work":"same_shared_work_utf8_bytes_plus_key_value_nodes_before_import"},"shared":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true"}}},"protocol":{"max_depth":128,"max_monitor_items":100000,"max_number_chars":4300,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_string_bytes":4194304,"max_work":50000000,"node_accounting":"values_and_object_keys","profile":"biocompiler.core.realization_protocol.resources.v1","report_encoding":"compact_ensure_ascii_true_conservative_outer_reservation_then_utf8_wire","report_scope":"complete_result_and_final_protocol_response","request_encoding":"compact_utf8_plus_one_separator","request_scope":"complete_payload_including_profile_limits_and_replay_assessment","work_accounting":"single_ancestor_for_import_authority_hash_fresh_check_replay_and_publication"}},"result_schemas":{"replay-component-assembly":"biocompiler.core.component_assembly_assessment.v1","verify-component-assembly":"biocompiler.core.component_assembly_assessment.v1"},"semantic_versions":{"component_linker":"biocompiler.component_linker.v0.3","component_reconstruction":"biocompiler.component_model_reconstruction.v0.1","human_admission_policy":"biocompiler.human_admission_policy.v0.1","model_runner":"biocompiler.synthetic.runner.v0.2","realization_checker":"biocompiler.realization_checker.v0.3","reference_evaluator":"biocompiler.behavior.evaluator.v0.2","synthetic_acceptance":"biocompiler.synthetic.acceptance.v0.5","synthetic_catalog":"biocompiler.synthetic.catalog.v0.2","synthetic_generator":"biocompiler.synthetic.generator.v0.4","synthetic_profiles":["biocompiler.synthetic.combinational.v0.1","biocompiler.synthetic.temporal.v0.1"]},"service_implementation":"biocompiler.ocaml.realization_service.v0.1","supplied_authority_encoding":"python-json-v1","supplied_authority_excluded_fields":["assessment"],"until_codec":"null_or_exact_integer_or_finite_binary64_without_early_numeric_coercion","validation_scope":"source-synthetic-component-correspondence-finite-history-v1","wire_encoding":"python-json-v1"},"component_behavior":{"assessment_encoding":"python-json-ascii-v1","assessment_schema":"biocompiler.realization_check.v0.1","authority_identity_fields":["request_fingerprint","request_artifact_fingerprint","history_ascii_fingerprint","assembly_fingerprint"],"claim_scope":"Fresh source lowering and actual locked component reconstruction/linking/finite-history acceptance only; no synthetic candidate correspondence, search completeness, empirical function or human-use admission.","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"dependency_encoding":"python-json-ascii-v1","dependency_schema_version_field":false,"history_codec":{"boundary_version":"biocompiler.native_execution_data.v0.1","frame_fields":["time","signals","contacts"],"numeric_sample_shorthand":true,"sample_fields":["value","present","high","low"],"schema_version_field":false},"implementation":"biocompiler.ocaml.component_behavior_checker.v0.1","input_schemas":{"assembly":["biocompiler.component_assembly.v0.2"],"expected_request":["biocompiler.realization_request.v0.1"]},"limits_fields":["max_work","max_monitor_items","max_request_bytes","max_report_bytes","max_report_nodes"],"limits_null":"fixed_defaults","operations":["verify-component-behavior","replay-component-behavior"],"payload_fields":{"replay-component-behavior":["profile","limits","expected_request","assembly","history","until","assessment"],"verify-component-behavior":["profile","limits","expected_request","assembly","history","until"]},"profile":"biocompiler.core.component_behavior.v1","resources":{"checker":{"composition":{"diagnostic_order":"pair_sorted_unknown_dependency_binding_and_unknown_resource_binding_only.v1","intermediate_accounting":"cumulative_no_refunds","max_input_bytes":16777216,"max_input_nodes":250000,"max_rational_bits":8192,"max_report_bytes":33554432,"max_report_nodes":250000,"max_retained_intermediate_items":100000,"max_work":50000000,"profile":"biocompiler.composition_check.resources.v1","rational_arithmetic":"exact_Fraction_of_Python_decimal_spelling"},"profile":"biocompiler.component_behavior_checker.resources.v1","realization":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_translated_history_bytes":16777216,"max_translated_history_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true","translated_history_work":"same_shared_work_utf8_bytes_plus_key_value_nodes_before_import"},"shared":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true"}},"protocol":{"max_depth":128,"max_monitor_items":100000,"max_number_chars":4300,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_string_bytes":4194304,"max_work":50000000,"node_accounting":"values_and_object_keys","profile":"biocompiler.core.realization_protocol.resources.v1","report_encoding":"compact_ensure_ascii_true_conservative_outer_reservation_then_utf8_wire","report_scope":"complete_result_and_final_protocol_response","request_encoding":"compact_utf8_plus_one_separator","request_scope":"complete_payload_including_profile_limits_and_replay_assessment","work_accounting":"single_ancestor_for_import_authority_hash_fresh_check_replay_and_publication"}},"result_schemas":{"replay-component-behavior":"biocompiler.core.component_behavior_assessment.v1","verify-component-behavior":"biocompiler.core.component_behavior_assessment.v1"},"semantic_versions":{"component_linker":"biocompiler.component_linker.v0.3","component_reconstruction":"biocompiler.component_model_reconstruction.v0.1","human_admission_policy":"biocompiler.human_admission_policy.v0.1","model_runner":"biocompiler.synthetic.runner.v0.2","realization_checker":"biocompiler.realization_checker.v0.3","reference_evaluator":"biocompiler.behavior.evaluator.v0.2"},"service_implementation":"biocompiler.ocaml.realization_service.v0.1","supplied_authority_encoding":"python-json-v1","supplied_authority_excluded_fields":["assessment"],"until_codec":"null_or_exact_integer_or_finite_binary64_without_early_numeric_coercion","validation_scope":"source-locked-component-finite-history-v1","wire_encoding":"python-json-v1"},"realization":{"assessment_encoding":"python-json-ascii-v1","assessment_schema":"biocompiler.realization_check.v0.1","authority_identity_fields":["behavior_fingerprint","behavior_artifact_ascii_fingerprint","contract_fingerprint","domain_fingerprint","target_fingerprint","mechanism_fingerprint","observation_map_fingerprint","history_ascii_fingerprint"],"claim_scope":"Direct supplied Behavior and model authority only; no source lowering, synthetic provenance, search completeness, empirical function or human-use admission.","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"dependency_claim_scope":"Only dependency identities were constructed from the supplied declarations and exact history/horizon; no model execution, acceptance, source lowering or biological claim is established.","dependency_encoding":"python-json-ascii-v1","dependency_schema_version_field":false,"dependency_validation_scope":"supplied-realization-dependencies-only-v1","history_codec":{"boundary_version":"biocompiler.native_execution_data.v0.1","frame_fields":["time","signals","contacts"],"numeric_sample_shorthand":true,"sample_fields":["value","present","high","low"],"schema_version_field":false},"implementation":"biocompiler.ocaml.realization_checker.v0.1","input_schemas":{"behavior":["biocompiler.behavior.v0.1","biocompiler.behavior.v0.2"],"contract":["biocompiler.behavior_contract.v0.1"],"domain":["biocompiler.operating_domain.v0.1"],"mechanism":["biocompiler.mechanism.synthetic.v0.2"],"observation_map":["biocompiler.observation_map.v0.1"],"target":["biocompiler.target.v0.1","biocompiler.human_target_context.v0.1"]},"limits_fields":["max_work","max_monitor_items","max_request_bytes","max_report_bytes","max_report_nodes"],"limits_null":"fixed_defaults","operations":["realization-dependencies","verify-realization","replay-realization"],"payload_fields":{"realization-dependencies":["profile","limits","behavior","contract","domain","target","mechanism","observation_map","history","until"],"replay-realization":["profile","limits","behavior","contract","domain","target","mechanism","observation_map","history","until","assessment"],"verify-realization":["profile","limits","behavior","contract","domain","target","mechanism","observation_map","history","until"]},"profile":"biocompiler.core.realization.v1","resources":{"checker":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_translated_history_bytes":16777216,"max_translated_history_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true","translated_history_work":"same_shared_work_utf8_bytes_plus_key_value_nodes_before_import"},"protocol":{"max_depth":128,"max_monitor_items":100000,"max_number_chars":4300,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_string_bytes":4194304,"max_work":50000000,"node_accounting":"values_and_object_keys","profile":"biocompiler.core.realization_protocol.resources.v1","report_encoding":"compact_ensure_ascii_true_conservative_outer_reservation_then_utf8_wire","report_scope":"complete_result_and_final_protocol_response","request_encoding":"compact_utf8_plus_one_separator","request_scope":"complete_payload_including_profile_limits_and_replay_assessment","work_accounting":"single_ancestor_for_import_authority_hash_fresh_check_replay_and_publication"}},"result_schemas":{"realization-dependencies":"biocompiler.core.realization_dependencies.v1","replay-realization":"biocompiler.core.realization_assessment.v1","verify-realization":"biocompiler.core.realization_assessment.v1"},"semantic_versions":{"human_admission_policy":"biocompiler.human_admission_policy.v0.1","model_runner":"biocompiler.synthetic.runner.v0.2","realization_checker":"biocompiler.realization_checker.v0.3","reference_evaluator":"biocompiler.behavior.evaluator.v0.2"},"service_implementation":"biocompiler.ocaml.realization_service.v0.1","supplied_authority_encoding":"python-json-v1","supplied_authority_excluded_fields":["assessment"],"until_codec":"null_or_exact_integer_or_finite_binary64_without_early_numeric_coercion","validation_scope":"supplied-behavior-finite-history-v1","wire_encoding":"python-json-v1"},"synthetic_candidate":{"assessment_encoding":"python-json-ascii-v1","assessment_schema":"biocompiler.realization_check.v0.1","authority_identity_fields":["request_fingerprint","request_artifact_fingerprint","history_ascii_fingerprint","candidate_fingerprint"],"claim_scope":"Fresh source lowering, synthetic provenance and supplied finite-history acceptance only; no component correspondence, search completeness, empirical function or human-use admission.","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"dependency_encoding":"python-json-ascii-v1","dependency_schema_version_field":false,"history_codec":{"boundary_version":"biocompiler.native_execution_data.v0.1","frame_fields":["time","signals","contacts"],"numeric_sample_shorthand":true,"sample_fields":["value","present","high","low"],"schema_version_field":false},"implementation":"biocompiler.ocaml.synthetic_candidate_checker.v0.1","input_schemas":{"candidate":["biocompiler.synthetic_candidate.v0.4"],"expected_request":["biocompiler.realization_request.v0.1"]},"limits_fields":["max_work","max_monitor_items","max_request_bytes","max_report_bytes","max_report_nodes"],"limits_null":"fixed_defaults","operations":["verify-synthetic-candidate","replay-synthetic-candidate"],"payload_fields":{"replay-synthetic-candidate":["profile","limits","expected_request","candidate","history","until","assessment"],"verify-synthetic-candidate":["profile","limits","expected_request","candidate","history","until"]},"profile":"biocompiler.core.synthetic_candidate.v1","resources":{"checker":{"profile":"biocompiler.synthetic_candidate_checker.resources.v1","realization":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_translated_history_bytes":16777216,"max_translated_history_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true","translated_history_work":"same_shared_work_utf8_bytes_plus_key_value_nodes_before_import"},"shared":{"failure_publication":"request_bounded_capacity_held_outside_engine_allocation","fragment_punctuation":"one_conservative_separator_byte_per_request_or_report_fragment","max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_work":50000000,"profile":"biocompiler.realization_checker.resources.v1","publication_work":"same_shared_work_ascii_bytes_plus_key_value_nodes","report_encoding":"compact_ensure_ascii_true"}},"protocol":{"max_depth":128,"max_monitor_items":100000,"max_number_chars":4300,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_request_nodes":250000,"max_string_bytes":4194304,"max_work":50000000,"node_accounting":"values_and_object_keys","profile":"biocompiler.core.realization_protocol.resources.v1","report_encoding":"compact_ensure_ascii_true_conservative_outer_reservation_then_utf8_wire","report_scope":"complete_result_and_final_protocol_response","request_encoding":"compact_utf8_plus_one_separator","request_scope":"complete_payload_including_profile_limits_and_replay_assessment","work_accounting":"single_ancestor_for_import_authority_hash_fresh_check_replay_and_publication"}},"result_schemas":{"replay-synthetic-candidate":"biocompiler.core.synthetic_candidate_assessment.v1","verify-synthetic-candidate":"biocompiler.core.synthetic_candidate_assessment.v1"},"semantic_versions":{"human_admission_policy":"biocompiler.human_admission_policy.v0.1","model_runner":"biocompiler.synthetic.runner.v0.2","realization_checker":"biocompiler.realization_checker.v0.3","reference_evaluator":"biocompiler.behavior.evaluator.v0.2","synthetic_acceptance":"biocompiler.synthetic.acceptance.v0.5","synthetic_catalog":"biocompiler.synthetic.catalog.v0.2","synthetic_generator":"biocompiler.synthetic.generator.v0.4","synthetic_profiles":["biocompiler.synthetic.combinational.v0.1","biocompiler.synthetic.temporal.v0.1"]},"service_implementation":"biocompiler.ocaml.realization_service.v0.1","supplied_authority_encoding":"python-json-v1","supplied_authority_excluded_fields":["assessment"],"until_codec":"null_or_exact_integer_or_finite_binary64_without_early_numeric_coercion","validation_scope":"source-synthetic-provenance-finite-history-v1","wire_encoding":"python-json-v1"}}'
PROFILES: dict[str, dict[str, Any]] = json.loads(_PROFILES_JSON)
_RESULT_FIELDS = {'assessment_fingerprint', 'supplied_authority_fingerprint', 'implementation', 'validation_scope', 'profile', 'resources', 'service_implementation', 'claim_scope', 'schema_version', 'assessment', 'authority_identities', 'resource_profile'}
_DEPENDENCY_RESULT_FIELDS = {'supplied_authority_fingerprint', 'implementation', 'dependencies', 'dependencies_fingerprint', 'validation_scope', 'profile', 'resources', 'service_implementation', 'claim_scope', 'schema_version', 'authority_identities', 'resource_profile'}
_FAMILIES = ("realization", "synthetic_candidate", "component_behavior", "component_assembly")
OPERATIONS = tuple(operation for family in _FAMILIES for operation in PROFILES[family]["operations"])
VALIDATION_SCOPES = (PROFILES["realization"]["dependency_validation_scope"], *(PROFILES[key]["validation_scope"] for key in _FAMILIES))
_CHECK_SCOPE = "Only the listed contract requirements, supplied input history, operating domain, and finite evaluation horizon were checked; this is not whole-program or universal biological refinement."
_COMPOSITION_SCOPE = "Structural component compatibility under the locked records and declared target, provider, lifecycle, model and resource assumptions only. This is not biological efficacy, sequence emission, or empirical validation."
_DEPENDENCY_FIELDS = {"behavior", "behavior_artifact", "contract", "domain", "target", "mechanism", "observation_map", "history", "horizon", "checker", "model_runner", "reference_evaluator", "settings"}
_IDENTITY_DEPENDENCIES = {"behavior_fingerprint": "behavior", "behavior_artifact_ascii_fingerprint": "behavior_artifact", "contract_fingerprint": "contract", "domain_fingerprint": "domain", "target_fingerprint": "target", "mechanism_fingerprint": "mechanism", "observation_map_fingerprint": "observation_map", "history_ascii_fingerprint": "history"}


def _record(value: JsonValue, fields: set[str], label: str) -> dict[str, Any]:
    # Exact shape and subsequent field guards narrow heterogeneous JSON records.
    return cast(dict[str, Any], _object(value, fields, label))


def _profile(operation: str) -> tuple[str, dict[str, Any]]:
    if type(operation) is not str or operation not in OPERATIONS:
        raise CoreProtocolError("Unknown realization operation")
    profiles = json.loads(_PROFILES_JSON)
    return next((key, profiles[key]) for key in _FAMILIES if operation in profiles[key]["operations"])


def encode_report(value: JsonValue, encoding: str) -> bytes:
    """Bounded report-family canonicalization, retaining exact numeric spelling."""
    validated = encode_json(value, limit=LIMITS["max_response_bytes"])
    if encoding == "python-json-v1":
        return validated
    if encoding != "python-json-ascii-v1":
        raise CoreProtocolError("Unknown realization report encoding")
    result = bytearray()
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    for part in encoder.iterencode(value):
        chunk = part.encode("ascii")
        if len(result) + len(chunk) > LIMITS["max_response_bytes"]:
            raise CoreProtocolError("Realization report byte budget exceeded")
        result.extend(chunk)
    return bytes(result)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hash(value: JsonValue, label: str) -> str:
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise CoreProtocolError(f"{label} must be a lowercase SHA-256 fingerprint")
    return value


def _equal(left: JsonValue, right: JsonValue) -> bool:
    # Dict equality would accept booleans as integers and 1.0 as 1.
    return encode_json(left, limit=LIMITS["max_response_bytes"]) == encode_json(right, limit=LIMITS["max_response_bytes"])


def _limits(profile: dict[str, Any], value: JsonValue) -> dict[str, Any]:
    defaults = cast(dict[str, Any], profile["default_limits"])
    if value is None:
        return defaults
    result = _record(value, set(defaults), "Realization limits")
    if any(type(result[key]) is not int or not 0 < result[key] <= maximum for key, maximum in defaults.items()):
        raise CoreProtocolError("Realization limits must be positive integer reductions")
    return result


def effective_resources(profile: dict[str, Any], limits: JsonValue) -> JsonValue:
    """Map the five public reductions through the pinned nested resource tree."""
    reduced = _limits(profile, limits)
    aliases = {"max_input_bytes": "max_request_bytes", "max_retained_intermediate_items": "max_monitor_items"}
    def visit(value: JsonValue) -> JsonValue:
        if type(value) is dict:
            return {key: reduced[aliases.get(key) or key] if (aliases.get(key) or key) in reduced else visit(item)
                    for key, item in value.items()}
        if type(value) is list:
            return [visit(item) for item in value]
        return value
    return visit(profile["resources"])


def _negotiate(capabilities: CoreCapabilities) -> None:
    expected = json.loads(_PROFILES_JSON)
    profiles = capabilities.profiles
    if (any(key not in profiles or not _equal(profiles[key], value) for key, value in expected.items())
            or any(operation not in capabilities.operations for operation in OPERATIONS)
            or any(scope not in capabilities.validation_scopes for scope in VALIDATION_SCOPES)):
        raise CoreProtocolError("Incompatible realization operations, schemas, policy, resources or scopes")


def _dependencies(value: JsonValue, profile: dict[str, Any], identities: dict[str, Any],
                  payload: dict[str, Any], family: str) -> dict[str, Any]:
    deps = _record(value, _DEPENDENCY_FIELDS, "Realization dependencies")
    for key in _IDENTITY_DEPENDENCIES.values():
        _hash(deps[key], "Dependency " + key)
    versions = cast(dict[str, Any], profile["semantic_versions"])
    for key, version in (("checker", "realization_checker"), ("model_runner", "model_runner"), ("reference_evaluator", "reference_evaluator")):
        if deps[key] != versions[version]:
            raise CoreProtocolError("Realization dependencies changed their fixed semantic versions")
    horizon = _record(deps["horizon"], {"until", "effective"}, "Realization horizon")
    if not _equal(horizon["until"], payload["until"]) or type(horizon["effective"]) not in (int, float) or horizon["effective"] < 0:
        raise CoreProtocolError("Realization dependencies changed the supplied horizon")
    settings = deps["settings"]
    if type(settings) is not dict or not settings or settings.get("human_admission_policy") != versions["human_admission_policy"]:
        raise CoreProtocolError("Invalid realization checker settings")
    if family == "realization":
        if any(deps[key] != identities[name] for name, key in _IDENTITY_DEPENDENCIES.items()):
            raise CoreProtocolError("Realization report dependencies differ from authority identities")
    elif deps["history"] != identities["history_ascii_fingerprint"]:
        raise CoreProtocolError("Realization report history differs from authority identities")
    if family == "synthetic_candidate":
        for key, name in (("synthetic_candidate", "candidate_fingerprint"), ("realization_request", "request_fingerprint")):
            if settings.get(key) != identities[name]:
                raise CoreProtocolError("Synthetic report differs from its supplied authority identities")
        if settings.get("synthetic_acceptance") != versions["synthetic_acceptance"]:
            raise CoreProtocolError("Synthetic report changed its acceptance policy")
    if family == "component_behavior":
        if (settings.get("component_assembly") != identities["assembly_fingerprint"]
                or settings.get("component_reconstruction") != versions["component_reconstruction"]):
            raise CoreProtocolError("Component report differs from its assembly authority or policy")
    return deps


def _text(value: JsonValue, label: str, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if type(value) is not str or not value.strip():
        raise CoreProtocolError(label + " must be a nonempty string")


def _source(value: JsonValue) -> None:
    if value is None:
        return
    source = _record(value, {"file", "line", "function"}, "Diagnostic source")
    _text(source["file"], "Source file")
    _text(source["function"], "Source function")
    if type(source["line"]) is not int or source["line"] < 1:
        raise CoreProtocolError("Source line must be a positive integer")


def _number(value: JsonValue, label: str, *, optional: bool = False, nonnegative: bool = True) -> None:
    if optional and value is None:
        return
    try:
        valid = type(value) in (int, float) and math.isfinite(cast(int | float, value)) and (not nonnegative or cast(int | float, value) >= 0)
    except OverflowError:
        valid = False
    if not valid:
        raise CoreProtocolError(label + " must be a finite number")


def _details(report: dict[str, Any], *, composition: bool) -> None:
    requirements = report["checked_requirement_ids"]
    for item in report["diagnostics"]:
        fields = {"status", "code", "message", "instance_id", "requirement_ids"} if composition else {"code", "message", "requirement_id", "node_id", "source"}
        item = _record(item, fields, "Realization diagnostic")
        for key in ("code", "message"):
            _text(item[key], "Diagnostic " + key)
        if composition:
            if item["status"] not in ("fail", "unknown", "unsupported"):
                raise CoreProtocolError("Invalid composition diagnostic status")
            _text(item["instance_id"], "Diagnostic instance", optional=True)
            _names(item["requirement_ids"], "Diagnostic requirements")
        else:
            _text(item["node_id"], "Diagnostic node", optional=True)
            if item["requirement_id"] is not None and item["requirement_id"] not in requirements:
                raise CoreProtocolError("Diagnostic refers to an unknown requirement")
            _source(item["source"])
    if composition:
        for item in report["resolved_dependencies"]:
            item = _record(item, {"instance_id", "requirement_id", "provider_id", "provider_kind", "status"}, "Resolved dependency")
            for key in ("instance_id", "requirement_id", "provider_id"):
                _text(item[key], "Resolved " + key, optional=key == "provider_id")
            if (item["provider_kind"] not in ("encoded_here", "co_payload", "host", "external", "unresolved")
                    or item["status"] not in ("pass", "fail", "unknown", "unsupported")):
                raise CoreProtocolError("Invalid resolved dependency category")
        for item in report["resource_usage"]:
            item = _record(item, {"pool_id", "peak_reservation", "capacity", "unit", "status"}, "Resource usage")
            for key in ("pool_id", "unit"):
                _text(item[key], "Resource " + key)
            for key in ("peak_reservation", "capacity"):
                _number(item[key], "Resource " + key, optional=True)
            if item["status"] not in ("pass", "fail", "unknown", "unsupported") or report["outcome"] == "pass" and item["status"] != "pass":
                raise CoreProtocolError("Invalid composition resource status")
    else:
        for item in report["counterexamples"]:
            item = _record(item, {"requirement_id", "time", "contact_id", "expected", "actual", "rule_id", "specification_id", "source"}, "Counterexample")
            for key in ("requirement_id", "rule_id", "specification_id", "contact_id"):
                _text(item[key], "Counterexample " + key, optional=key == "contact_id")
            if item["requirement_id"] not in requirements:
                raise CoreProtocolError("Counterexample refers to an unknown requirement")
            _number(item["time"], "Counterexample time")
            _number(item["actual"], "Counterexample actual", optional=True, nonnegative=False)
            expected = _record(item["expected"], {"state", "range"}, "Counterexample expectation")
            if expected["state"] not in ("active", "inactive") or type(expected["range"]) is not dict:
                raise CoreProtocolError("Invalid counterexample expectation")
            _source(item["source"])


def _assessment(value: JsonValue, profile: dict[str, Any], identities: dict[str, Any],
                payload: dict[str, Any], family: str) -> None:
    composition = family == "component_assembly"
    fields = {"schema_version", "outcome", "dependencies", "checked_requirement_ids", "diagnostics", "claim_scope"}
    fields |= {"resolved_dependencies", "resource_usage"} if composition else {"evidence_kind", "counterexamples", "coverage"}
    report = _record(value, fields, "Realization assessment")
    if (report["schema_version"] != profile["assessment_schema"]
            or report["claim_scope"] != (_COMPOSITION_SCOPE if composition else _CHECK_SCOPE)
            or type(report["outcome"]) is not str or report["outcome"] not in ("pass", "fail", "unknown", "unsupported")):
        raise CoreProtocolError("Invalid realization assessment schema, outcome or claim scope")
    requirements = _names(report["checked_requirement_ids"], "Checked requirements")
    arrays = ("diagnostics", "resolved_dependencies", "resource_usage") if composition else ("diagnostics", "counterexamples", "coverage")
    for key in arrays:
        if type(report[key]) is not list or any(type(item) is not dict for item in report[key]):
            raise CoreProtocolError("Realization assessment details must be record arrays")
    if composition:
        deps = _record(report["dependencies"], {"request", "registry", "registry_lock", "target", "checker", "identities", "admission_policy"}, "Composition dependencies")
        for key in ("request", "registry", "registry_lock", "target"):
            _hash(deps[key], "Composition " + key)
        versions = profile["semantic_versions"]
        if deps["checker"] != versions["component_linker"] or deps["admission_policy"] != versions["human_admission_policy"]:
            raise CoreProtocolError("Composition report changed its fixed policy")
        if type(deps["identities"]) is not list:
            raise CoreProtocolError("Composition dependency identities must be an array")
        pins = set()
        for item in deps["identities"]:
            item = _record(item, {"schema_version", "kind", "id", "version", "content_fingerprint"}, "Composition pinned identity")
            for key in ("kind", "id", "version"):
                _text(item[key], "Pinned " + key)
            _hash(item["content_fingerprint"], "Pinned content")
            pin = (item["kind"], item["id"], item["version"])
            if (item["schema_version"] != "biocompiler.component_identity.v0.1"
                    or item["kind"] not in ("model", "reference", "registry", "source", "evidence") or pin in pins):
                raise CoreProtocolError("Invalid or duplicate composition identity")
            pins.add(pin)
    else:
        if report["evidence_kind"] != "model_conditional":
            raise CoreProtocolError("Realization assessment broadened its evidence kind")
        _dependencies(report["dependencies"], profile, identities, payload, family)
        coverage_ids = []
        for item in report["coverage"]:
            coverage = _record(item, {"requirement_id", "activation_deadlines_checked", "inactive_deadlines_checked", "incomplete_episode_count", "cancelled_episode_count"}, "Realization coverage")
            coverage_ids.append(coverage["requirement_id"])
            if coverage["requirement_id"] not in requirements or any(type(value) is not int or value < 0 for key, value in coverage.items() if key != "requirement_id"):
                raise CoreProtocolError("Invalid realization requirement coverage")
        if len(set(coverage_ids)) != len(coverage_ids):
            raise CoreProtocolError("Duplicate realization requirement coverage")
        if report["counterexamples"] and report["outcome"] != "fail":
            raise CoreProtocolError("Counterexamples require a failed outcome")
        if report["outcome"] == "pass" and (not requirements or report["counterexamples"] or set(coverage_ids) != set(requirements)
                or any(item["activation_deadlines_checked"] <= 0 or item["inactive_deadlines_checked"] <= 0 or item["incomplete_episode_count"] != 0 for item in report["coverage"])):
            raise CoreProtocolError("Passing realization report lacks complete exercised coverage")
    _details(report, composition=composition)
    if report["outcome"] == "pass" and report["diagnostics"]:
        raise CoreProtocolError("Passing realization report contains unresolved diagnostics")


@dataclass(frozen=True)
class RealizationResult:
    """Complete immutable native result; stored bytes never confer fresh authority."""
    request_id: str
    operation: str
    executable: Literal["core", "verify"]
    report_fingerprint: str
    report_encoding: str
    report_json: bytes
    _envelope_json: bytes

    @property
    def envelope(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_json(self._envelope_json))

    @property
    def report(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_json(self.report_json))

    @property
    def assessment(self) -> dict[str, Any]:
        if self.operation == "realization-dependencies":
            raise CoreProtocolError("Dependency identity is not an acceptance assessment")
        return self.report

    @property
    def dependencies(self) -> dict[str, Any]:
        return self.report if self.operation == "realization-dependencies" else cast(dict[str, Any], self.report["dependencies"])

    @property
    def assessment_fingerprint(self) -> str | None:
        return None if self.operation == "realization-dependencies" else self.report_fingerprint

    @property
    def dependencies_fingerprint(self) -> str | None:
        return self.report_fingerprint if self.operation == "realization-dependencies" else None

    @property
    def supplied_authority_fingerprint(self) -> str:
        return cast(str, self.envelope["supplied_authority_fingerprint"])

    @property
    def authority_identities(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.envelope["authority_identities"])

    @property
    def outcome(self) -> str | None:
        return None if self.operation == "realization-dependencies" else cast(str, self.report["outcome"])


def _result(response: CoreResponse, payload: dict[str, Any]) -> RealizationResult:
    family, profile = _profile(response.operation)
    dependency = response.operation == "realization-dependencies"
    result = _record(response.result, _DEPENDENCY_RESULT_FIELDS if dependency else _RESULT_FIELDS, "Realization result")
    expected = {
        "schema_version": profile["result_schemas"][response.operation], "profile": profile["profile"],
        "implementation": profile["implementation"], "service_implementation": profile["service_implementation"],
        "resource_profile": profile["resources"]["protocol"]["profile"],
        "resources": effective_resources(profile, payload["limits"]),
        "validation_scope": profile["dependency_validation_scope" if dependency else "validation_scope"],
        "claim_scope": profile["dependency_claim_scope" if dependency else "claim_scope"],
    }
    if any(not _equal(result[key], value) for key, value in expected.items()):
        raise CoreProtocolError("Realization result changed its negotiated profile, resources or scope")
    supplied = _hash(result["supplied_authority_fingerprint"], "Supplied authority")
    if supplied != _sha(encode_json({key: value for key, value in payload.items() if key != "assessment"})):
        raise CoreProtocolError("Realization result is bound to different supplied authority")
    identities = _record(result["authority_identities"], set(profile["authority_identity_fields"]), "Realization authority identities")
    for key, value in identities.items():
        _hash(value, key)
    label = "dependencies" if dependency else "assessment"
    report = result[label]
    if dependency:
        _dependencies(report, profile, identities, payload, family)
    else:
        _assessment(report, profile, identities, payload, family)
    encoding = cast(str, profile["dependency_encoding" if dependency else "assessment_encoding"])
    encoded = encode_report(report, encoding)
    fingerprint = _hash(result[label + "_fingerprint"], "Realization report")
    if fingerprint != _sha(encoded):
        raise CoreProtocolError("Realization report fingerprint mismatch")
    if "assessment" in payload and encode_report(payload["assessment"], encoding) != encoded:
        raise CoreProtocolError("Realization replay returned a different complete historical report")
    return RealizationResult(response.request_id, response.operation, response.executable, fingerprint, encoding,
                             encoded, encode_json(result, limit=LIMITS["max_response_bytes"]))


@dataclass(frozen=True)
class RealizationClient:
    transport: CoreClient

    def call(self, operation: str, payload: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> RealizationResult:
        family, profile = _profile(operation)
        del family
        # Freeze every caller-owned value before capabilities negotiation or I/O.
        snapshot = _record(decode_json(encode_json(payload)), set(profile["payload_fields"][operation]), "Realization payload")
        if snapshot["profile"] != profile["profile"]:
            raise CoreProtocolError("Incompatible realization payload profile")
        _limits(profile, snapshot["limits"])
        if snapshot["until"] is not None and type(snapshot["until"]) not in (int, float):
            raise CoreProtocolError("Realization horizon must be null or an exact JSON number")
        if type(snapshot["history"]) is not list:
            raise CoreProtocolError("Realization history must be an array")
        _negotiate(self.transport.negotiate(operation, cancelled=cancelled))
        return _result(self.transport.call(operation, snapshot, cancelled=cancelled), snapshot)

    def _invoke(self, operation: str, authority: dict[str, Any], limits: JsonValue,
                cancelled: Callable[[], bool] | None) -> RealizationResult:
        _, profile = _profile(operation)
        return self.call(operation, {"profile": profile["profile"], "limits": limits, **authority}, cancelled=cancelled)

    def dependencies(self, *, behavior: JsonValue, contract: JsonValue, domain: JsonValue, target: JsonValue, mechanism: JsonValue, observation_map: JsonValue, history: JsonValue,
            until: JsonValue = None, limits: JsonValue = None, cancelled: Callable[[], bool] | None = None) -> RealizationResult:
        return self._invoke('realization-dependencies', {'behavior': behavior, 'contract': contract, 'domain': domain, 'target': target, 'mechanism': mechanism, 'observation_map': observation_map, 'history': history, 'until': until}, limits, cancelled)

    def verify_realization(self, *, behavior: JsonValue, contract: JsonValue, domain: JsonValue, target: JsonValue, mechanism: JsonValue, observation_map: JsonValue, history: JsonValue,
            until: JsonValue = None, limits: JsonValue = None, cancelled: Callable[[], bool] | None = None) -> RealizationResult:
        return self._invoke('verify-realization', {'behavior': behavior, 'contract': contract, 'domain': domain, 'target': target, 'mechanism': mechanism, 'observation_map': observation_map, 'history': history, 'until': until}, limits, cancelled)

    def replay_realization(self, *, behavior: JsonValue, contract: JsonValue, domain: JsonValue, target: JsonValue, mechanism: JsonValue, observation_map: JsonValue, history: JsonValue, assessment: JsonValue,
            until: JsonValue = None, limits: JsonValue = None, cancelled: Callable[[], bool] | None = None) -> RealizationResult:
        return self._invoke('replay-realization', {'behavior': behavior, 'contract': contract, 'domain': domain, 'target': target, 'mechanism': mechanism, 'observation_map': observation_map, 'history': history, 'assessment': assessment, 'until': until}, limits, cancelled)

    def verify_synthetic_candidate(self, *, expected_request: JsonValue, candidate: JsonValue, history: JsonValue,
            until: JsonValue = None, limits: JsonValue = None, cancelled: Callable[[], bool] | None = None) -> RealizationResult:
        return self._invoke('verify-synthetic-candidate', {'expected_request': expected_request, 'candidate': candidate, 'history': history, 'until': until}, limits, cancelled)

    def replay_synthetic_candidate(self, *, expected_request: JsonValue, candidate: JsonValue, history: JsonValue, assessment: JsonValue,
            until: JsonValue = None, limits: JsonValue = None, cancelled: Callable[[], bool] | None = None) -> RealizationResult:
        return self._invoke('replay-synthetic-candidate', {'expected_request': expected_request, 'candidate': candidate, 'history': history, 'assessment': assessment, 'until': until}, limits, cancelled)

    def verify_component_behavior(self, *, expected_request: JsonValue, assembly: JsonValue, history: JsonValue,
            until: JsonValue = None, limits: JsonValue = None, cancelled: Callable[[], bool] | None = None) -> RealizationResult:
        return self._invoke('verify-component-behavior', {'expected_request': expected_request, 'assembly': assembly, 'history': history, 'until': until}, limits, cancelled)

    def replay_component_behavior(self, *, expected_request: JsonValue, assembly: JsonValue, history: JsonValue, assessment: JsonValue,
            until: JsonValue = None, limits: JsonValue = None, cancelled: Callable[[], bool] | None = None) -> RealizationResult:
        return self._invoke('replay-component-behavior', {'expected_request': expected_request, 'assembly': assembly, 'history': history, 'assessment': assessment, 'until': until}, limits, cancelled)

    def verify_component_assembly(self, *, expected_request: JsonValue, candidate: JsonValue, assembly: JsonValue, history: JsonValue,
            until: JsonValue = None, limits: JsonValue = None, cancelled: Callable[[], bool] | None = None) -> RealizationResult:
        return self._invoke('verify-component-assembly', {'expected_request': expected_request, 'candidate': candidate, 'assembly': assembly, 'history': history, 'until': until}, limits, cancelled)

    def replay_component_assembly(self, *, expected_request: JsonValue, candidate: JsonValue, assembly: JsonValue, history: JsonValue, assessment: JsonValue,
            until: JsonValue = None, limits: JsonValue = None, cancelled: Callable[[], bool] | None = None) -> RealizationResult:
        return self._invoke('replay-component-assembly', {'expected_request': expected_request, 'candidate': candidate, 'assembly': assembly, 'history': history, 'assessment': assessment, 'until': until}, limits, cancelled)

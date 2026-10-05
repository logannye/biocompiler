"""Producer-free Verify transport over private archive descriptors.

The report binds fresh execution by the explicitly selected Verify executable.
It does not replace the separate Core deterministic-reconstruction requirement.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import re
import sys
from typing import Any, Callable, cast
from uuid import uuid4

from biocompiler.core_artifacts import _exchange_artifacts
from biocompiler.core_client import (CORE_VERSION, PROTOCOL, CoreClient, CoreError,
    CoreProtocolError, JsonValue, decode_json, encode_json)
from biocompiler.core_package_files import PackageFiles

PROFILE = 'biocompiler.reference_package_verify.v1'
ARGUMENT = '--verify-reference-package-fds-v1'
OPERATION = 'verify-reference-package'
MAX_RESPONSE = 16_384
LIMITS = {'max_archive_bytes': 67_108_864, 'max_member_bytes': 16_777_216,
    'max_metadata_bytes': 1_048_576, 'max_entries': 128, 'max_path_bytes': 1024,
    'max_json_nodes': 250_000, 'max_json_depth': 128, 'max_retained_bytes': 536_870_912,
    'max_work': 10_000_000_000}
TOOL_IDS = ('reference_build', 'human_admission_policy', 'reference_inputs', 'archive',
    'sequence_export', 'sequence_emitter', 'construct_pipeline', 'molecular_pipeline',
    'reference_adapter', 'construct_generator', 'component_checker', 'construct_checker', 'molecular_checker')
DECLARATION = {'schema': 'biocompiler.reference_package_verify_declaration.v1',
    'profile': PROFILE, 'argument': ARGUMENT, 'protocol': PROTOCOL, 'operation': OPERATION,
    'max_control_bytes': 16_777_216, 'max_response_bytes': MAX_RESPONSE, 'limits': LIMITS,
    'authority_fields': ['package_version', 'tool_pins'],
    'runtime_profiles': ['python311', 'python314'],
    'tool_ids': list(TOOL_IDS), 'archive': 'single_readonly_private_descriptor_exact_length_sha256_and_eof',
    'output': 'private_descriptor_must_remain_empty',
    'acceptance': 'fresh_producer_free_reference_stage_evidence_summary_and_export_check;Core_reconstruction_separately_required'}
DECLARATION_BYTES = encode_json(cast(JsonValue, DECLARATION))
CLAIM = ('Exact reference package, stage evidence and sequence consistency for software use; '
         'no biological or therapeutic claim.')


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CoreProtocolError(message)


def _hash(value: Any) -> bool:
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _object(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == fields, 'Invalid ' + label)
    return cast(dict[str, Any], value)


class PackageVerificationRejected(CoreError):
    """A complete bounded Verify failure; no imported report grants validity."""
    def __init__(self, diagnostics: tuple[tuple[str, str, str | None], ...]):
        self.diagnostics = diagnostics
        super().__init__('; '.join(message for _, message, _ in diagnostics))


@dataclass(frozen=True)
class PackageVerification:
    """Immutable observed receipt, not a reusable public acceptance constructor."""
    archive_sha256: str
    build_fingerprint: str
    request_fingerprint: str
    metadata_authority: str
    request_sha256: str
    _report: bytes

    @property
    def report(self) -> JsonValue:
        return decode_json(self._report)


def verify_package(core: CoreClient, archive: bytes, *, package_version: str,
                   tool_pins: list[JsonValue], expected_request: JsonValue = None,
                   expected_build_fingerprint: str | None = None,
                   limits: dict[str, int] | None = None,
                   cancelled: Callable[[], bool] | None = None) -> PackageVerification:
    _require(type(core) is CoreClient and core.role == 'verify', 'Select the standalone Verify executable')
    _require(sys.version_info[:2] in ((3, 11), (3, 14)), 'Package verification requires Python 3.11 or 3.14')
    runtime = 'python311' if sys.version_info[:2] == (3, 11) else 'python314'
    _require(type(archive) is bytes and bool(archive), 'Package verification requires complete archive bytes')
    _require(expected_request is not None or expected_build_fingerprint is not None,
        'Package verification requires independent request or build authority')
    _require(expected_build_fingerprint is None or _hash(expected_build_fingerprint), 'Invalid expected build identity')
    _require(type(package_version) is str and bool(package_version.strip()), 'Invalid current package version')
    _require(type(tool_pins) is list and len(tool_pins) == len(TOOL_IDS), 'Invalid current tool authority')
    tools = [_object(item, {'schema_version', 'id', 'version', 'content_fingerprint'}, 'current tool pin')
        for item in tool_pins]
    _require(all(item['schema_version'] == 'biocompiler.tool_pin.v0.1'
        and type(item['id']) is str and type(item['version']) is str and bool(item['version'].strip())
        and _hash(item['content_fingerprint']) for item in tools), 'Invalid current tool authority')
    _require(len({item['id'] for item in tools}) == len(TOOL_IDS)
        and {item['id'] for item in tools} == set(TOOL_IDS), 'Incomplete or duplicate current tool authority')
    effective = dict(LIMITS) if limits is None else dict(_object(limits, set(LIMITS), 'package reductions'))
    _require(all(type(effective[key]) is int and 0 <= effective[key] <= ceiling for key, ceiling in LIMITS.items()),
        'Package limits must be nonnegative reductions')
    _require(0 < len(archive) <= effective['max_archive_bytes'], 'Archive exceeds its reduced byte ceiling')
    identifier = str(uuid4())
    authority = {'package_version': package_version, 'tool_pins': tools}
    # Detached ordinary JSON is the declared source authority, with exact type
    # distinctions and complete pin census; no manifest metadata is consulted.
    authority_bytes = encode_json(cast(JsonValue, authority))
    authority_identity = hashlib.sha256(authority_bytes).hexdigest()
    with PackageFiles(archive, max_archive_bytes=effective['max_archive_bytes']) as files:
        args, _ = files.claim_launch()
        arguments = (ARGUMENT, *args[1:])
        descriptor = files.input_descriptor
        request = {'protocol': PROTOCOL, 'profile': PROFILE, 'declaration': decode_json(DECLARATION_BYTES),
            'runtime': runtime,
            'request_id': identifier, 'operation': OPERATION, 'archive': descriptor,
            'authority': authority, 'expected_request': expected_request,
            'expected_build_fingerprint': expected_build_fingerprint, 'limits': effective}
        raw = encode_json(cast(JsonValue, request))
        request_identity = hashlib.sha256(raw).hexdigest()
        streams = (() if files._input is None else (files._input,)) + (files._output,)
        try:
            received, exit_code = _exchange_artifacts(core, raw, arguments, streams, files._output, 0, cancelled)
            files.monitor()
            _require(os.fstat(files._output.fileno()).st_size == 0, 'Verify wrote forbidden producer bytes')
            _require(exit_code == 0 and len(received) <= MAX_RESPONSE, 'Incomplete or oversized package verification reply')
            reply = _object(decode_json(received, limit=MAX_RESPONSE), {
                'protocol', 'profile', 'executable', 'version', 'request_id', 'request_sha256', 'operation',
                'archive', 'status', 'result', 'diagnostics', 'usage'}, 'package verification reply')
            _require(reply['protocol'] == PROTOCOL and reply['profile'] == PROFILE
                and reply['executable'] == 'verify' and reply['version'] == CORE_VERSION
                and reply['operation'] == OPERATION, 'Wrong package verification executable/profile')
            _require(reply['request_id'] == identifier and reply['request_sha256'] == request_identity,
                'Package verification reply is detached from this exact request')
            usage = _object(reply['usage'], {'work', 'retained_bytes'}, 'verification usage')
            _require(type(usage['work']) is int and 0 < usage['work'] <= LIMITS['max_work']
                and type(usage['retained_bytes']) is int and 0 <= usage['retained_bytes'] <= effective['max_retained_bytes'],
                'Verification usage exceeds its lifetime bounds')
            diagnostics = reply['diagnostics']
            _require(type(diagnostics) is list and len(diagnostics) <= 1, 'Invalid verification diagnostic census')
            if reply['status'] == 'error':
                _require(reply['result'] is None and diagnostics and reply['archive'] in (None, descriptor),
                    'Invalid failed package verification reply')
                item = _object(diagnostics[0], {'code', 'message', 'path'}, 'verification diagnostic')
                _require(type(item['code']) is str and bool(item['code']) and type(item['message']) is str
                    and bool(item['message']) and (item['path'] is None or type(item['path']) is str), 'Malformed verification diagnostic')
                raise PackageVerificationRejected(((item['code'], item['message'], item['path']),))
            _require(reply['status'] == 'ok' and not diagnostics and reply['archive'] == descriptor
                and usage['work'] <= effective['max_work'], 'Invalid successful package verification reply')
            report = _object(reply['result'], {'schema_version', 'outcome', 'archive_sha256', 'build_fingerprint',
                'request_fingerprint', 'metadata_authority', 'claim_scope', 'core_reconstruction_required'}, 'independent package report')
            _require(report['schema_version'] == 'biocompiler.reference_package_check.v1' and report['outcome'] == 'pass'
                and report['claim_scope'] == CLAIM and report['core_reconstruction_required'] is True,
                'Package report extends its checked scope')
            _require(report['archive_sha256'] == hashlib.sha256(archive).hexdigest()
                and report['metadata_authority'] == authority_identity and _hash(report['build_fingerprint'])
                and _hash(report['request_fingerprint']), 'Package report authority or archive identity differs')
            _require(expected_build_fingerprint is None or report['build_fingerprint'] == expected_build_fingerprint,
                'Package report changes the independent build identity')
            return PackageVerification(report['archive_sha256'], report['build_fingerprint'],
                report['request_fingerprint'], report['metadata_authority'], request_identity,
                encode_json(cast(JsonValue, report)))
        except BaseException:
            files.invalidate()
            raise

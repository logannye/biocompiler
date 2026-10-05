"""Closed package representation decoders; imported views grant no acceptance."""
from __future__ import annotations

from typing import Any, cast

from biocompiler.artifacts.manifest import (
    ReferenceBuildRequest, RunMetadata, PackageFile, AcceptedStage, ToolPin, BuildManifest,
)
from biocompiler.artifacts.sequences import SequenceExport
from biocompiler.compiler.reference import ReferencePackage
from biocompiler.core_client import JsonValue
from biocompiler.core_pipeline_provider_views import fields, text, integer, mapping, frozen_mapping, allocate, require
from biocompiler.core_pipeline_session import encode_document
from biocompiler.core_reference_views import ReferenceViews


class PackageViews(ReferenceViews):
    def build_request(self, value: JsonValue, *, original: ReferenceBuildRequest | None = None) -> ReferenceBuildRequest:
        d = fields(value, 'construct profile artifact_scope fasta_line_width', 'biocompiler.reference_build_request.v0.1')
        if original is not None:
            require(type(original) is ReferenceBuildRequest, 'Package request view has an unsupported class')
            require(encode_document(cast(Any, original).to_dict()) == encode_document(value), 'Package request changed its authored representation')
            return original
        return self.make(ReferenceBuildRequest, (), value, construct=self.construct_request(d['construct']),
            profile=text(d['profile']), artifact_scope=text(d['artifact_scope']), fasta_line_width=integer(d['fasta_line_width']))

    def metadata(self, value: JsonValue) -> RunMetadata:
        d = fields(value, 'timestamp_utc machine_label locations', 'biocompiler.run_metadata.v0.1')
        for item in mapping(d['locations']).values():
            text(item)
        return self.make(RunMetadata, (), value, timestamp_utc=text(d['timestamp_utc']),
            machine_label=text(d['machine_label']), locations=frozen_mapping(d['locations']))

    def file(self, value: JsonValue, path: tuple[str | int, ...] = ()) -> PackageFile:
        d = fields(value, 'path role sha256 byte_length', 'biocompiler.package_file.v0.1')
        return self.factory(PackageFile, path, value, {'path': text(d['path']), 'role': text(d['role']),
            'sha256': text(d['sha256']), 'byte_length': integer(d['byte_length'])})

    def accepted_stage(self, value: JsonValue, path: tuple[str | int, ...] = ()) -> AcceptedStage:
        d = fields(value, 'stage artifact_fingerprint record_fingerprint artifact_schema', 'biocompiler.accepted_stage.v0.1')
        return self.make(AcceptedStage, path, value, stage=text(d['stage']),
            artifact_fingerprint=text(d['artifact_fingerprint']), record_fingerprint=text(d['record_fingerprint']),
            artifact_schema=text(d['artifact_schema']))

    def tool(self, value: JsonValue, path: tuple[str | int, ...] = ()) -> ToolPin:
        d = fields(value, 'id version content_fingerprint', 'biocompiler.tool_pin.v0.1')
        return self.make(ToolPin, path, value, id=text(d['id']), version=text(d['version']),
            content_fingerprint=text(d['content_fingerprint']))

    def manifest(self, value: JsonValue) -> BuildManifest:
        d = fields(value, 'request_fingerprint files accepted_stages toolchain package_version profile status scope intended_use human_therapeutic_admission',
            'biocompiler.build_manifest.v0.2')
        return self.make(BuildManifest, (), value, request_fingerprint=text(d['request_fingerprint']),
            files=self.sequence(d['files'], self.file, ('files',)),
            accepted_stages=self.sequence(d['accepted_stages'], self.accepted_stage, ('accepted_stages',)),
            toolchain=self.sequence(d['toolchain'], self.tool, ('toolchain',)),
            package_version=text(d['package_version']), profile=text(d['profile']), status=text(d['status']),
            scope=text(d['scope']), intended_use=text(d['intended_use']),
            human_therapeutic_admission=text(d['human_therapeutic_admission']))

    def export(self, value: JsonValue) -> SequenceExport:
        d = fields(value, 'fasta specification line_width sequence_sha256 molecular_fingerprint')
        return self.make(SequenceExport, (), value, fasta=text(d['fasta']), specification=text(d['specification']),
            line_width=integer(d['line_width']), sequence_sha256=text(d['sequence_sha256']),
            molecular_fingerprint=text(d['molecular_fingerprint']))

    def package(self, request: ReferenceBuildRequest, manifest: BuildManifest, data: bytes) -> ReferencePackage:
        require(type(request) is ReferenceBuildRequest and type(manifest) is BuildManifest and type(data) is bytes,
                'Package representation has an unsupported field class')
        return allocate(ReferencePackage, {'request': request, 'manifest': manifest, 'data': data})

"""Closed structural views for native exact-reference operations.

These decoders allocate the existing public records from complete native wire
representations. They never invoke legacy constructors, parsers, normalization,
translation, reference resolution, producers or checkers. A session-supplied
factory owns any source-backed sharing; equal contents never imply identity.
Hydrating a candidate or historical report does not confer acceptance.
"""
from __future__ import annotations

from biocompiler.core_client import JsonValue
from biocompiler.core_pipeline_build_views import BuildViews
from biocompiler.core_pipeline_session import encode_document
from biocompiler.core_pipeline_provider_views import (
    ViewPath, array, boolean, fields, frozen_mapping, integer, mapping, optional,
    require, strings, text,
)
from biocompiler.ir.composition import CompositionRequest
from biocompiler.verification.evidence import CheckOutcome
from biocompiler.semantics.coordinates import (
    SequenceRange,
)
from biocompiler.registry.references import (
    ReferenceRecord, ReferenceManifest,
)
from biocompiler.registry.reference_components import (
    ReferenceSelection,
)
from biocompiler.ir.construct import (
    ConstructReference, ConstructMolecule, ComponentPlacement, ConstructFeature,
    ConstructJunction, RegulatoryRelationship, ConstructDependency,
    LayoutEvidencePolicy, ConstructRequest, ConstructCandidate,
)
from biocompiler.ir.molecular import (
    FeatureStatus, TranslationPolicy, EncodingPolicy, EncodingEvidencePolicy,
    EncodingChange, MolecularRecord, MolecularArtifact,
)
from biocompiler.verification.construct import (
    ConstructDiagnostic, ConstructResult,
)
from biocompiler.verification.molecular import (
    MolecularDiagnostic, MolecularCheck, MolecularResult,
)


def outcome(value: JsonValue) -> CheckOutcome:
    name = text(value)
    choices = {item.value: item for item in CheckOutcome}
    require(name in choices, 'Reference view outcome tag differs')
    return choices[name]


class ReferenceViews(BuildViews):
    """Finite field decoders; no content-based object interning or authority."""

    def reference_composition(self, value: JsonValue, path: ViewPath) -> CompositionRequest:
        d = mapping(value)
        require('target' in d, 'Reference composition target is missing')
        target = self.target(d['target'], (*path, 'target'))
        return self.composition(value, target, path)

    def sequence_range(self, value: JsonValue, path: ViewPath = ()) -> SequenceRange:
        d = fields(value, 'start end convention',
            'biocompiler.sequence_range.v0.1')
        require(d['convention'] == 'zero-based-half-open-reference-5prime-to-3prime.v1',
            'Reference coordinate view convention differs')
        return self.make(SequenceRange, path, value,
            start=integer(d['start']),
            end=integer(d['end']))

    def reference_record(self, value: JsonValue, path: ViewPath = ()) -> ReferenceRecord:
        d = fields(value, 'reference_id variant_id version alphabet artifact_class orientation source_id source_locator raw_sequence_text raw_text_sha256 sequence sequence_sha256 length normalization linked_reference_ids completeness unknown_features evidence_relationships')
        return self.make(ReferenceRecord, path, value,
            reference_id=text(d['reference_id']),
            variant_id=text(d['variant_id']),
            version=text(d['version']),
            alphabet=text(d['alphabet']),
            artifact_class=text(d['artifact_class']),
            orientation=text(d['orientation']),
            source_id=text(d['source_id']),
            source_locator=text(d['source_locator']),
            raw_sequence_text=text(d['raw_sequence_text']),
            raw_text_sha256=text(d['raw_text_sha256']),
            sequence=text(d['sequence']),
            sequence_sha256=text(d['sequence_sha256']),
            length=integer(d['length']),
            normalization=frozen_mapping(d['normalization']),
            linked_reference_ids=strings(d['linked_reference_ids']),
            completeness=text(d['completeness']),
            unknown_features=strings(d['unknown_features']),
            evidence_relationships=strings(d['evidence_relationships']))

    def reference_manifest(self, value: JsonValue, path: ViewPath = ()) -> ReferenceManifest:
        d = fields(value, 'reference_set_id version sources records translation reviews status unresolved_discrepancies redistribution schema_version')
        require(d['schema_version'] == 'biocompiler.reference.v0.1', 'Reference manifest view schema differs')
        return self.make(ReferenceManifest, path, value,
            reference_set_id=text(d['reference_set_id']),
            version=text(d['version']),
            sources=tuple(frozen_mapping(item) for item in array(d['sources'])),
            records=self.sequence(d['records'], self.reference_record, (*path, 'records')),
            translation=frozen_mapping(d['translation']),
            reviews=tuple(frozen_mapping(item) for item in array(d['reviews'])),
            status=text(d['status']),
            unresolved_discrepancies=strings(d['unresolved_discrepancies']),
            redistribution=frozen_mapping(d['redistribution']),
            schema_version=text(d['schema_version']))

    def reference_selection(self, value: JsonValue, path: ViewPath = ()) -> ReferenceSelection:
        d = fields(value, 'manifest reference',
            'biocompiler.reference_selection.v0.1')
        return self.make(ReferenceSelection, path, value,
            manifest=self.identity(d['manifest'], (*path, 'manifest')),
            reference=self.identity(d['reference'], (*path, 'reference')))

    def construct_reference(self, value: JsonValue, path: ViewPath = ()) -> ConstructReference:
        d = fields(value, 'instance_id selection',
            'biocompiler.construct_reference.v0.1')
        return self.make(ConstructReference, path, value,
            instance_id=text(d['instance_id']),
            selection=self.reference_selection(d['selection'], (*path, 'selection')))

    def construct_molecule(self, value: JsonValue, path: ViewPath = ()) -> ConstructMolecule:
        d = fields(value, 'id alphabet artifact_class length component_order topology completeness unknown_features compartment',
            'biocompiler.construct_molecule.v0.1')
        return self.make(ConstructMolecule, path, value,
            id=text(d['id']),
            alphabet=text(d['alphabet']),
            artifact_class=text(d['artifact_class']),
            length=integer(d['length']),
            component_order=strings(d['component_order']),
            topology=text(d['topology']),
            completeness=text(d['completeness']),
            unknown_features=strings(d['unknown_features']),
            compartment=text(d['compartment']))

    def component_placement(self, value: JsonValue, path: ViewPath = ()) -> ComponentPlacement:
        d = fields(value, 'instance_id molecule_id component reference source_range molecule_range orientation reading_frame requirement_ids source',
            'biocompiler.component_placement.v0.1')
        return self.make(ComponentPlacement, path, value,
            instance_id=text(d['instance_id']),
            molecule_id=text(d['molecule_id']),
            component=self.component_lock(d['component'], (*path, 'component')),
            reference=self.identity(d['reference'], (*path, 'reference')),
            source_range=self.sequence_range(d['source_range'], (*path, 'source_range')),
            molecule_range=self.sequence_range(d['molecule_range'], (*path, 'molecule_range')),
            orientation=text(d['orientation']),
            reading_frame=optional(d['reading_frame'], integer),
            requirement_ids=strings(d['requirement_ids']),
            source=self.source(d['source'], (*path, 'source')))

    def construct_feature(self, value: JsonValue, path: ViewPath = ()) -> ConstructFeature:
        d = fields(value, 'id molecule_id kind range source_reference source_range source_locator provenance orientation',
            'biocompiler.construct_feature.v0.1')
        return self.make(ConstructFeature, path, value,
            id=text(d['id']),
            molecule_id=text(d['molecule_id']),
            kind=text(d['kind']),
            range=self.sequence_range(d['range'], (*path, 'range')),
            source_reference=self.identity(d['source_reference'], (*path, 'source_reference')),
            source_range=self.sequence_range(d['source_range'], (*path, 'source_range')),
            source_locator=text(d['source_locator']),
            provenance=self.sequence(d['provenance'], self.identity, (*path, 'provenance')),
            orientation=text(d['orientation']))

    def construct_junction(self, value: JsonValue, path: ViewPath = ()) -> ConstructJunction:
        d = fields(value, 'id molecule_id left_instance right_instance kind range choice provenance',
            'biocompiler.construct_junction.v0.1')
        return self.make(ConstructJunction, path, value,
            id=text(d['id']),
            molecule_id=text(d['molecule_id']),
            left_instance=text(d['left_instance']),
            right_instance=text(d['right_instance']),
            kind=text(d['kind']),
            range=self.sequence_range(d['range'], (*path, 'range')),
            choice=text(d['choice']),
            provenance=self.sequence(d['provenance'], self.identity, (*path, 'provenance')))

    def regulatory_relationship(self, value: JsonValue, path: ViewPath = ()) -> RegulatoryRelationship:
        d = fields(value, 'id kind regulator_instance target_instance provenance assumptions',
            'biocompiler.construct_regulation.v0.1')
        return self.make(RegulatoryRelationship, path, value,
            id=text(d['id']),
            kind=text(d['kind']),
            regulator_instance=text(d['regulator_instance']),
            target_instance=text(d['target_instance']),
            provenance=self.sequence(d['provenance'], self.identity, (*path, 'provenance')),
            assumptions=strings(d['assumptions']))

    def construct_dependency(self, value: JsonValue, path: ViewPath = ()) -> ConstructDependency:
        d = fields(value, 'id consumer_molecule provider_molecule kind assumption requirement_ids',
            'biocompiler.construct_dependency.v0.1')
        return self.make(ConstructDependency, path, value,
            id=text(d['id']),
            consumer_molecule=text(d['consumer_molecule']),
            provider_molecule=text(d['provider_molecule']),
            kind=text(d['kind']),
            assumption=text(d['assumption']),
            requirement_ids=strings(d['requirement_ids']))

    def layout_evidence_policy(self, value: JsonValue, path: ViewPath = ()) -> LayoutEvidencePolicy:
        d = fields(value, 'semantic_properties invalidated_analyses',
            'biocompiler.construct_evidence_policy.v0.1')
        return self.make(LayoutEvidencePolicy, path, value,
            semantic_properties=strings(d['semantic_properties']),
            invalidated_analyses=strings(d['invalidated_analyses']))

    def construct_request(self, value: JsonValue, path: ViewPath = ()) -> ConstructRequest:
        d = fields(value, 'composition references molecules placements features junctions regulatory_relations dependencies assumptions source_request_fingerprint evidence_policy target nodes',
            'biocompiler.construct_request.v0.1')
        composition = mapping(d['composition'])
        require('target' in composition and 'instances' in composition,
            'Reference request composition representation is incomplete')
        require(encode_document(d['target']) == encode_document(composition['target']),
            'Reference request target view differs')
        expected_nodes = [{'id': text(mapping(item).get('id')), 'kind': 'component_instance'}
            for item in array(composition['instances'])]
        require(d['nodes'] == expected_nodes, 'Reference request node inventory view differs')
        return self.make(ConstructRequest, path, value,
            composition=self.reference_composition(d['composition'], (*path, 'composition')),
            references=self.sequence(d['references'], self.construct_reference, (*path, 'references')),
            molecules=self.sequence(d['molecules'], self.construct_molecule, (*path, 'molecules')),
            placements=self.sequence(d['placements'], self.component_placement, (*path, 'placements')),
            features=self.sequence(d['features'], self.construct_feature, (*path, 'features')),
            junctions=self.sequence(d['junctions'], self.construct_junction, (*path, 'junctions')),
            regulatory_relations=self.sequence(d['regulatory_relations'], self.regulatory_relationship, (*path, 'regulatory_relations')),
            dependencies=self.sequence(d['dependencies'], self.construct_dependency, (*path, 'dependencies')),
            assumptions=strings(d['assumptions']),
            source_request_fingerprint=optional(d['source_request_fingerprint'], text),
            evidence_policy=self.layout_evidence_policy(d['evidence_policy'], (*path, 'evidence_policy')))

    def construct_candidate(self, value: JsonValue, path: ViewPath = ()) -> ConstructCandidate:
        d = fields(value, 'request_fingerprint composition_fingerprint registry_lock molecules placements features junctions regulatory_relations dependencies assumptions evidence_policy nodes',
            'biocompiler.construct.v0.1')
        expected_nodes = [{'id': text(mapping(item).get('instance_id')), 'kind': 'component_placement'}
            for item in array(d['placements'])]
        require(d['nodes'] == expected_nodes, 'Reference node inventory view differs')
        return self.make(ConstructCandidate, path, value,
            request_fingerprint=text(d['request_fingerprint']),
            composition_fingerprint=text(d['composition_fingerprint']),
            registry_lock=self.registry_lock(d['registry_lock'], (*path, 'registry_lock')),
            molecules=self.sequence(d['molecules'], self.construct_molecule, (*path, 'molecules')),
            placements=self.sequence(d['placements'], self.component_placement, (*path, 'placements')),
            features=self.sequence(d['features'], self.construct_feature, (*path, 'features')),
            junctions=self.sequence(d['junctions'], self.construct_junction, (*path, 'junctions')),
            regulatory_relations=self.sequence(d['regulatory_relations'], self.regulatory_relationship, (*path, 'regulatory_relations')),
            dependencies=self.sequence(d['dependencies'], self.construct_dependency, (*path, 'dependencies')),
            assumptions=strings(d['assumptions']),
            evidence_policy=self.layout_evidence_policy(d['evidence_policy'], (*path, 'evidence_policy')))

    def feature_status(self, value: JsonValue, path: ViewPath = ()) -> FeatureStatus:
        d = fields(value, 'feature status scope reason value',
            'biocompiler.molecular_feature_status.v0.1')
        return self.make(FeatureStatus, path, value,
            feature=text(d['feature']),
            status=text(d['status']),
            scope=text(d['scope']),
            reason=text(d['reason']),
            value=optional(d['value'], text))

    def translation_policy(self, value: JsonValue, path: ViewPath = ()) -> TranslationPolicy:
        d = fields(value, 'genetic_code start_codon stop_convention protein_length_includes_stop',
            'biocompiler.translation_policy.v0.1')
        return self.make(TranslationPolicy, path, value,
            genetic_code=integer(d['genetic_code']),
            start_codon=text(d['start_codon']),
            stop_convention=text(d['stop_convention']),
            protein_length_includes_stop=boolean(d['protein_length_includes_stop']))

    def encoding_policy(self, value: JsonValue, path: ViewPath = ()) -> EncodingPolicy:
        d = fields(value, 'mode optimization transformations',
            'biocompiler.encoding_policy.v0.1')
        return self.make(EncodingPolicy, path, value,
            mode=text(d['mode']),
            optimization=text(d['optimization']),
            transformations=strings(d['transformations']))

    def encoding_evidence_policy(self, value: JsonValue, path: ViewPath = ()) -> EncodingEvidencePolicy:
        d = fields(value, 'semantic_properties invalidated_analyses',
            'biocompiler.encoding_evidence_policy.v0.1')
        return self.make(EncodingEvidencePolicy, path, value,
            semantic_properties=strings(d['semantic_properties']),
            invalidated_analyses=strings(d['invalidated_analyses']))

    def encoding_change(self, value: JsonValue, path: ViewPath = ()) -> EncodingChange:
        d = fields(value, 'id record_id before_sequence_sha256 after_sequence_sha256 changed_properties reason preservation_claims',
            'biocompiler.encoding_change.v0.1')
        return self.make(EncodingChange, path, value,
            id=text(d['id']),
            record_id=text(d['record_id']),
            before_sequence_sha256=text(d['before_sequence_sha256']),
            after_sequence_sha256=text(d['after_sequence_sha256']),
            changed_properties=strings(d['changed_properties']),
            reason=text(d['reason']),
            preservation_claims=strings(d['preservation_claims']))

    def molecular_record(self, value: JsonValue, path: ViewPath = ()) -> MolecularRecord:
        d = fields(value, 'id instance_id molecule_id alphabet artifact_class sequence sequence_sha256 component reference_selection source_range molecule_range features feature_statuses orientation reading_frame translation_policy completeness unknown_features evidence_relationships requirement_ids source length',
            'biocompiler.molecular_record.v0.1')
        require(integer(d['length']) == len(text(d['sequence'])), 'Reference sequence length view differs')
        return self.make(MolecularRecord, path, value,
            id=text(d['id']),
            instance_id=text(d['instance_id']),
            molecule_id=text(d['molecule_id']),
            alphabet=text(d['alphabet']),
            artifact_class=text(d['artifact_class']),
            sequence=text(d['sequence']),
            sequence_sha256=text(d['sequence_sha256']),
            component=self.component_lock(d['component'], (*path, 'component')),
            reference_selection=self.reference_selection(d['reference_selection'], (*path, 'reference_selection')),
            source_range=self.sequence_range(d['source_range'], (*path, 'source_range')),
            molecule_range=self.sequence_range(d['molecule_range'], (*path, 'molecule_range')),
            features=self.sequence(d['features'], self.construct_feature, (*path, 'features')),
            feature_statuses=self.sequence(d['feature_statuses'], self.feature_status, (*path, 'feature_statuses')),
            orientation=text(d['orientation']),
            reading_frame=optional(d['reading_frame'], integer),
            translation_policy=self.translation_policy(d['translation_policy'], (*path, 'translation_policy')),
            completeness=text(d['completeness']),
            unknown_features=strings(d['unknown_features']),
            evidence_relationships=strings(d['evidence_relationships']),
            requirement_ids=strings(d['requirement_ids']),
            source=self.source(d['source'], (*path, 'source')))

    def molecular_artifact(self, value: JsonValue, path: ViewPath = ()) -> MolecularArtifact:
        d = fields(value, 'request_fingerprint construct_fingerprint layout_fingerprint registry_lock profile records encoding_policy evidence_policy changes source_request_fingerprint artifact_scope intended_use human_therapeutic_admission nodes',
            'biocompiler.molecular.v0.2')
        require(d['intended_use'] == 'software_test' and d['human_therapeutic_admission'] == 'not_admitted',
            'Reference molecular view claim tags differ')
        expected_nodes = [{'id': text(mapping(item).get('instance_id')), 'kind': 'cds_record'}
            for item in array(d['records'])]
        require(d['nodes'] == expected_nodes, 'Reference node inventory view differs')
        return self.make(MolecularArtifact, path, value,
            request_fingerprint=text(d['request_fingerprint']),
            construct_fingerprint=text(d['construct_fingerprint']),
            layout_fingerprint=text(d['layout_fingerprint']),
            registry_lock=self.registry_lock(d['registry_lock'], (*path, 'registry_lock')),
            profile=text(d['profile']),
            records=self.sequence(d['records'], self.molecular_record, (*path, 'records')),
            encoding_policy=self.encoding_policy(d['encoding_policy'], (*path, 'encoding_policy')),
            evidence_policy=self.encoding_evidence_policy(d['evidence_policy'], (*path, 'evidence_policy')),
            changes=self.sequence(d['changes'], self.encoding_change, (*path, 'changes')),
            source_request_fingerprint=optional(d['source_request_fingerprint'], text),
            artifact_scope=text(d['artifact_scope']))

    def construct_diagnostic(self, value: JsonValue, path: ViewPath = ()) -> ConstructDiagnostic:
        d = fields(value, 'status code message instance_id molecule_id requirement_ids source')
        return self.make(ConstructDiagnostic, path, value,
            status=text(d['status']),
            code=text(d['code']),
            message=text(d['message']),
            instance_id=optional(d['instance_id'], text),
            molecule_id=optional(d['molecule_id'], text),
            requirement_ids=strings(d['requirement_ids']),
            source=self.source(d['source'], (*path, 'source')))

    def construct_result(self, value: JsonValue, path: ViewPath = ()) -> ConstructResult:
        d = fields(value, 'outcome dependencies checked_requirement_ids diagnostics claim_scope',
            'biocompiler.construct_result.v0.2')
        return self.make(ConstructResult, path, value,
            outcome=outcome(d['outcome']),
            dependencies=frozen_mapping(d['dependencies']),
            checked_requirement_ids=strings(d['checked_requirement_ids']),
            diagnostics=self.sequence(d['diagnostics'], self.construct_diagnostic, (*path, 'diagnostics')),
            claim_scope=text(d['claim_scope']))

    def molecular_diagnostic(self, value: JsonValue, path: ViewPath = ()) -> MolecularDiagnostic:
        d = fields(value, 'status code message record_id instance_id molecule_id requirement_ids source')
        return self.make(MolecularDiagnostic, path, value,
            status=text(d['status']),
            code=text(d['code']),
            message=text(d['message']),
            record_id=optional(d['record_id'], text),
            instance_id=optional(d['instance_id'], text),
            molecule_id=optional(d['molecule_id'], text),
            requirement_ids=strings(d['requirement_ids']),
            source=self.source(d['source'], (*path, 'source')))

    def molecular_check(self, value: JsonValue, path: ViewPath = ()) -> MolecularCheck:
        d = fields(value, 'record_id check outcome expected_fingerprint actual_fingerprint message')
        return self.make(MolecularCheck, path, value,
            record_id=text(d['record_id']),
            check=text(d['check']),
            outcome=outcome(d['outcome']),
            expected_fingerprint=optional(d['expected_fingerprint'], text),
            actual_fingerprint=optional(d['actual_fingerprint'], text),
            message=text(d['message']))

    def molecular_result(self, value: JsonValue, path: ViewPath = ()) -> MolecularResult:
        d = fields(value, 'outcome dependencies checked_requirement_ids diagnostics checks claim_scope',
            'biocompiler.molecular_result.v0.2')
        return self.make(MolecularResult, path, value,
            outcome=outcome(d['outcome']),
            dependencies=frozen_mapping(d['dependencies']),
            checked_requirement_ids=strings(d['checked_requirement_ids']),
            diagnostics=self.sequence(d['diagnostics'], self.molecular_diagnostic, (*path, 'diagnostics')),
            checks=self.sequence(d['checks'], self.molecular_check, (*path, 'checks')),
            claim_scope=text(d['claim_scope']))

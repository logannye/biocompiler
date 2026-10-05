"""Submission packages remain scoped declarations, never backend execution."""
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.policy import model as m
from biocompiler.policy.handoff import BackendCapabilities, SubmissionError, assess_capabilities, prepare_submission
from biocompiler.policy.serialization import document_digest, from_data, dump, dumps, load, loads, to_data
from biocompiler.policy.validation import check


def request():
    capability = m.SemanticDefinition('capability', '1', 'capability', 'A supplied capability declaration.')
    operational = m.SemanticDefinition('operational', '1', 'model', 'A supplied operational model declaration.')
    delivery = m.SemanticDefinition('delivery', '1', 'delivery', 'A supplied delivery assumption.')
    role = m.Role('worker', (capability.ref,))
    program = m.PolicyProgram('example', m.SemanticBundle('semantics', '1',
        (capability, operational, delivery)), (role,))
    chassis = m.ChassisProfile('immune', '1', 'lymphoid', 'T', (), (),
        (capability.ref,), operational.ref, (), ())
    deployment = m.Deployment('target', (m.RoleBinding(m.Ref('worker', 'Role'), chassis),), (),
        m.DeliveryContract('delivery', (m.Ref('worker', 'Role'),), delivery.ref,
            delivery.ref, delivery.ref, 'same_recipient', delivery.ref,
            ('Supplied delivery applicability remains unestablished.',)), m.RNAConstraints())
    return m.BuildRequest(program, deployment, m.ImplementationCatalogLock('catalog', '1'),
        m.AssuranceRequest((), 'structural', m.Quantity('5', m.Unit('s', 'time', 'duration'))))


class PolicyHandoffTests(unittest.TestCase):
    def test_submission_preserves_request_pins_and_unresolved_scope(self):
        document = request()
        report = check(document)
        self.assertEqual(report.status, 'complete', report.to_dict())
        # Any accidental discovery or compiler dispatch fails this control.
        with patch('subprocess.Popen', side_effect=AssertionError('No backend execution')):
            bundle = prepare_submission(document)
        self.assertEqual(bundle.request, document)
        self.assertEqual(bundle.program, document.program)
        self.assertEqual(bundle.document_digest, document_digest(document))
        self.assertEqual(bundle.program_digest, document_digest(document.program))
        self.assertEqual(bundle.required_features, report.required_features)
        self.assertEqual(bundle.outstanding_obligations, report.deferred_obligations)
        self.assertIn('Supplied delivery applicability remains unestablished.', bundle.assumptions)
        self.assertEqual(bundle.semantic_status, 'unassessed')
        self.assertEqual(bundle.target_status, 'unassessed')
        self.assertEqual(bundle.backend_execution, 'not_performed')
        self.assertEqual([item.id for item in bundle.dependencies], ['capability', 'delivery', 'operational'])

    def test_draft_unbound_program_and_invalid_request_cannot_be_submitted(self):
        document = request()
        values = (
            document.program,
            m.PolicyDraft('draft', document.program.semantics, document.program.declarations),
            replace(document, deployment=replace(document.deployment, bindings=())),
        )
        for value in values:
            with self.subTest(kind=type(value).__name__), self.assertRaises(SubmissionError):
                prepare_submission(value)

    def test_feature_coverage_cannot_claim_acceptance(self):
        document = request()
        features = check(document).required_features
        all_features = BackendCapabilities('explicit-backend', '1', (m.PROFILE,), features)
        with patch('subprocess.Popen', side_effect=AssertionError('No backend execution')):
            covered = assess_capabilities(document, all_features)
        self.assertEqual(covered.status, 'declared_compatible')
        self.assertEqual(covered.unsupported_features, ())
        self.assertEqual(covered.semantic_status, 'unassessed')
        self.assertEqual(covered.target_status, 'unassessed')
        self.assertEqual(covered.backend_execution, 'not_performed')
        missing = assess_capabilities(document, replace(all_features, features=()))
        self.assertEqual(missing.status, 'unsupported')
        self.assertEqual(missing.unsupported_features, tuple(sorted(features)))
        wrong_profile = assess_capabilities(document, replace(all_features, profiles=('different.v1',)))
        self.assertFalse(wrong_profile.profile_supported)
        self.assertEqual(wrong_profile.status, 'unsupported')

    def test_capability_assessment_keeps_unbound_program_target_explicit(self):
        program = request().program
        result = assess_capabilities(program, BackendCapabilities('backend', '1',
            (m.PROFILE,), check(program).required_features))
        self.assertEqual(result.target_status, 'unbound')

    def test_invalid_request_does_not_become_compatible_through_feature_census(self):
        document = request()
        invalid = replace(document, deployment=replace(document.deployment, bindings=()))
        report = check(invalid)
        self.assertEqual(report.status, 'invalid')
        result = assess_capabilities(invalid, BackendCapabilities('backend', '1', (m.PROFILE,), report.required_features))
        self.assertEqual(result.status, 'unsupported')

    def test_capability_declarations_are_bounded_frozen_and_unique(self):
        caller = ['one']
        value = BackendCapabilities('backend', '1', [m.PROFILE], caller)
        caller.append('two')
        self.assertEqual(value.features, ('one',))
        for invalid in (('one', 'one'), (object(),), tuple(str(index) for index in range(4097))):
            with self.subTest(size=len(invalid)), self.assertRaises((ValueError, TypeError)):
                BackendCapabilities('backend', '1', (m.PROFILE,), invalid)

    def test_submission_and_assessment_cannot_mutate_shared_authoring(self):
        document = request()
        original = document_digest(document)
        bundle = prepare_submission(document)
        assessment = assess_capabilities(document, BackendCapabilities('backend', '1',
            (m.PROFILE,), bundle.required_features))
        for value, name, replacement in ((bundle, 'semantic_status', 'accepted'),
                (bundle.request.program, 'id', 'changed'),
                (bundle.semantic_bundle, 'digest', 'changed'),
                (assessment, 'status', 'accepted')):
            with self.subTest(kind=type(value).__name__, name=name), self.assertRaises(FrozenInstanceError):
                setattr(value, name, replacement)
        caller = ['supplied feature']
        copied = replace(bundle, required_features=caller)
        caller.append('late mutation')
        self.assertEqual(copied.required_features, ('supplied feature',))
        detached = to_data(bundle)
        detached['profile'] = 'changed'
        detached['required_features'].append('late mutation')
        self.assertEqual(document_digest(document), original)
        self.assertEqual(bundle.profile, document.profile)
        self.assertNotIn('late mutation', bundle.required_features)
        self.assertEqual(from_data(to_data(assessment), m.CapabilityAssessment), assessment)

    def test_submission_roundtrips_with_closed_import_registry(self):
        bundle = prepare_submission(request())
        self.assertEqual(loads(dumps(bundle), m.CompilationSubmission), bundle)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'submission.json'
            dump(bundle, path)
            self.assertEqual(load(path, m.CompilationSubmission), bundle)
            # Fresh interpreters import either public boundary first. No runtime
            # registration by prepare_submission may be needed for wire reads.
            script = '''
import importlib
from pathlib import Path
import sys
importlib.import_module(sys.argv[1])
from biocompiler.policy.model import CompilationSubmission
from biocompiler.policy.serialization import dump, load, schema
document = load(sys.argv[2], CompilationSubmission)
assert document.semantic_status == 'unassessed'
assert document.backend_execution == 'not_performed'
assert schema(CompilationSubmission)['$ref'] == '#/$defs/CompilationSubmission'
destination = Path(sys.argv[3])
dump(document, destination)
assert load(destination, CompilationSubmission) == document
'''
            for index, first in enumerate(('biocompiler.policy.serialization', 'biocompiler.policy.handoff')):
                with self.subTest(first=first):
                    result = subprocess.run([sys.executable, '-c', script, first, str(path),
                        str(Path(directory) / f'copy-{index}.json')], check=False,
                        capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()

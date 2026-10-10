"""Inert census/lineage mutations; never import policy or start a backend."""
import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import check_policy_public_api_coverage as c


INSTANCE_DEPENDENCIES = frozenset('biocompiler.core_policy_component_material.' + name for name in (
    'INSTANCE_ASSEMBLY_PROFILE', 'INSTANCE_IMPLEMENTATION', 'INSTANCE_PRODUCER_PROFILE',
    'INSTANCE_PROFILE', 'INSTANCE_REQUEST_PROFILE', 'INSTANCE_REQUEST_SCHEMA',
    'INSTANCE_VALIDATION_SCOPE', '_instanced',
))


class PolicyPublicApiCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = c.read_ledger(c.ROOT / c.LEDGER)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.ledger = copy.deepcopy(self.original)
        paths = set(self.ledger['inventory']['files']) | {w['path'] for w in self.ledger['witnesses'].values()}
        paths |= {c.LEDGER, 'protocol/policy-semantic-coverage-v0.1.json'}
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(c.ROOT / relative, target)

    def edit(self, path, before, after, *, repin_file=False):
        target = self.root / path
        source = target.read_text()
        self.assertIn(before, source)
        target.write_text(source.replace(before, after, 1))
        if repin_file:
            self.ledger['inventory']['files'][path] = c.digest(target.read_bytes())

    def test_exact_census_and_scoped_evidence(self):
        result = c.validate(self.root, self.ledger)
        self.assertEqual((result['files'], result['entries'], result['exports'], result['cli_commands'], result['native_operations']), (57, 1688, 305, 17, 35))
        self.assertEqual(result['coverage'], {'compatibility_support': 6, 'dependency': 595,
            'independent_expansion': 28, 'shared_invariant': 708, 'source_only': 351})
        self.assertEqual(len(self.ledger['syntax_links']), 359)
        self.assertEqual(len(self.ledger['witnesses']), 214)
        self.assertEqual(result['status'], 'source_inventory_checked')
        self.assertEqual(result['runtime_protocol_scope'], c.RUNTIME_SCOPE)
        self.assertIn('not an exhaustive runtime-attribute census', result['runtime_protocol_scope'])
        self.assertIn('neither executed coverage', result['claim_scope'])
        self.assertEqual({r['id'].removeprefix('biocompiler.policy.') for r in self.ledger['inventory']['entries'] if r['scope'] == 'compatibility_support'}, c.SUPPORT)

    def test_discovery_is_inert_even_for_source_with_executable_statements(self):
        before = {key for key in sys.modules if key.startswith('biocompiler')}
        marker = self.root / 'must_not_exist'
        path = self.root / c.PACKAGE / 'programs.py'
        with path.open('a') as stream:
            stream.write('\nraise RuntimeError("Do not execute source")\n')
            stream.write(f'open({str(marker)!r}, "w").write("executed")\n')
        found = c.discover(self.root)
        self.assertEqual(len(found['entries']), 1688)
        self.assertFalse(marker.exists())
        self.assertEqual(before, {key for key in sys.modules if key.startswith('biocompiler')})

    def test_reviewed_lazy_facades_preserve_all_explicit_export_targets(self):
        before = {key for key in sys.modules if key.startswith('biocompiler')}
        found = c.discover(self.root)
        self.assertEqual(found['exports'], self.original['inventory']['exports'])
        self.assertEqual(len(found['exports']), 305)
        self.assertEqual(found['exports']['biocompiler.policy.refinement.PolicyRefinementClient'],
                         'biocompiler.core_policy_refinement.PolicyRefinementClient')
        self.assertEqual(found['exports']['biocompiler.policy.quantitative_assurance.PolicyQuantitativeAssuranceResult'],
                         'biocompiler.core_policy_quantitative_assurance.PolicyQuantitativeAssuranceResult')
        self.assertEqual(before, {key for key in sys.modules if key.startswith('biocompiler')})

    def test_lazy_export_discovery_rejects_changed_hooks_aliases_and_conditions(self):
        path = self.root / c.PACKAGE / 'refinement.py'
        original = path.read_text()
        changes = (
            original.replace('if TYPE_CHECKING:', 'if True:', 1),
            original.replace('from biocompiler.core_policy_refinement import (',
                             'from biocompiler.core_policy_material import (', 1),
            original.replace('return getattr(core_policy_refinement, name)', 'return object()', 1),
            original + '\nPolicyRefinementClient = object()\n',
            original + '\nTYPE_CHECKING = True\n',
            original + '\ngetattr = lambda *args: None\n',
            original + '\n_TRANSPORT_EXPORTS.add("unchecked")\n',
            original + '\nglobals()["__getattr__"] = lambda name: None\n',
            original + '\nglobals().update({"RefinementClaim": 7})\n',
            original + '\nlocals()["__getattr__"] = lambda name: None\n',
            original + '\nexec("RefinementClaim = 7")\n',
            original + '\nsetattr(module_alias, "RefinementClaim", 7)\n',
            original + '\ndef sneaky(value=globals().update({"RefinementClaim": 7})):\n    pass\n',
            original + '\nclass Sneaky:\n    globals().update({"RefinementClaim": 7})\n',
            original.replace('def check(request: JsonValue,', 'def check(request: globals().update({"RefinementClaim": 7}),', 1),
            original.replace('def __getattr__(name: str) -> Any:', 'def unchecked(name: str) -> Any:', 1),
        )
        for altered in changes:
            with self.subTest(source=altered):
                path.write_text(altered)
                with self.assertRaises(c.ApiCoverageError):
                    c.discover(self.root)
        path.write_text(original)

    def test_type_checking_imports_without_closed_runtime_shim_do_not_bind_exports(self):
        path = self.root / c.PACKAGE / '__init__.py'
        text = path.read_text()
        start, end = text.index('def __getattr__'), text.index('__all__ =')
        path.write_text(text[:start] + text[end:])
        with self.assertRaises(c.ApiCoverageError):
            c.discover(self.root)

    def test_composition_dependencies_preserve_all_previous_api_classifications_and_witness_meanings(self):
        self.assertEqual(len(c.COMPOSITION_DEPENDENCIES), 60)
        entries = {row['id']: row for row in self.ledger['inventory']['entries']}
        for identity in c.COMPOSITION_DEPENDENCIES:
            self.assertEqual(entries[identity]['scope'], 'dependency')
            self.assertEqual(self.ledger['coverage'][identity]['status'], 'dependency')
            self.assertEqual(self.ledger['coverage'][identity]['witnesses'], [])
        metadata = {
            'witnesses': {key: {name: value[name] for name in ('path', 'symbol', 'role', 'distinction')}
                          for key, value in self.before_typed_modules()['witnesses'].items()},
            'coverage': {key: value for key, value in self.before_typed_modules()['coverage'].items()
                         if key not in c.COMPOSITION_DEPENDENCIES},
        }
        self.assertEqual(len(metadata['coverage']), 845)
        encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')
        self.assertEqual(c.digest(encoded), '1ca37142a2beec20c09db60e709e5aa8273da2f5e2002a104ed21c228d6b7d62')

    def test_grounded_helper_dependencies_preserve_all_896_previous_api_meanings(self):
        self.assertEqual(len(c.GROUNDED_HELPER_DEPENDENCIES), 9)
        self.assertTrue(set(c.GROUNDED_HELPER_DEPENDENCIES) <= set(c.COMPOSITION_DEPENDENCIES))
        entries = {row['id']: row for row in self.ledger['inventory']['entries']}
        for identity in c.GROUNDED_HELPER_DEPENDENCIES:
            self.assertEqual(entries[identity]['scope'], 'dependency')
            self.assertEqual(self.ledger['coverage'][identity]['status'], 'dependency')
            self.assertEqual(self.ledger['coverage'][identity]['witnesses'], [])
        metadata = {
            'witnesses': {key: {name: value[name] for name in ('path', 'symbol', 'role', 'distinction')}
                          for key, value in self.before_typed_modules()['witnesses'].items()},
            'coverage': {key: value for key, value in self.before_typed_modules()['coverage'].items()
                         if key not in c.GROUNDED_HELPER_DEPENDENCIES},
        }
        self.assertEqual(len(metadata['coverage']), 896)
        encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')
        self.assertEqual(c.digest(encoded), '5cc11771578db41f60eca0aca124269cdf66cb4db3034f093151c91ebfd44b09')

    def test_instance_dependencies_remain_private_in_the_combined_inventory(self):
        # The combined ledger uses the same dependency-only scope wording for
        # all composition profiles. The original 845 rows and all witnesses
        # are separately pinned above; none of these eight additions has a
        # runtime witness or an acceptance claim.
        self.assertEqual(len(INSTANCE_DEPENDENCIES), 8)
        self.assertTrue(INSTANCE_DEPENDENCIES <= set(c.COMPOSITION_DEPENDENCIES))
        for identity in INSTANCE_DEPENDENCIES:
            with self.subTest(identity=identity):
                self.assertEqual(self.ledger['coverage'][identity], {
                    'status': 'dependency', 'witnesses': [],
                    'scope': 'Private implementation dependency or versioned protocol constant; '
                             'no independent public API or executed semantic coverage claimed.',
                })

    def test_instance_dependency_cannot_gain_runtime_evidence(self):
        row = self.ledger['coverage']['biocompiler.core_policy_component_material._instanced']
        row.update(status='shared_invariant', witnesses=['component.routes'], scope='Native acceptance.')
        with self.assertRaisesRegex(c.ApiCoverageError, 'Private dependency classification changed'):
            c.validate(self.root, self.ledger)

    def test_grounded_helper_dependency_cannot_become_public_or_semantic_acceptance(self):
        for identity in c.GROUNDED_HELPER_DEPENDENCIES:
            ledger = copy.deepcopy(self.ledger)
            ledger['coverage'][identity].update(status='source_only', scope='Validated helper behavior.')
            with self.subTest(identity=identity), self.assertRaisesRegex(c.ApiCoverageError, 'Private dependency classification changed'):
                c.validate(self.root, ledger)

    def test_file_census_rejects_new_module_even_with_repinned_ledger(self):
        path = c.PACKAGE + '/unreviewed.py'
        (self.root / path).write_text('def public_api(): return 1\n')
        self.ledger['inventory']['files'][path] = c.digest((self.root / path).read_bytes())
        with self.assertRaisesRegex(c.ApiCoverageError, 'file census differs'):
            c.validate(self.root, self.ledger)

    def test_body_and_default_drift_remain_after_file_digest_is_refreshed(self):
        path = c.PACKAGE + '/programs.py'
        self.edit(path, 'termination: Literal["contact_loss", "explicit_event", "contract"] = "contact_loss"',
                  'termination: Literal["contact_loss", "explicit_event", "contract"] = "explicit_event"', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'Source/API inventory drift'):
            c.validate(self.root, self.ledger)

    def test_same_signature_different_body_is_not_signature_coverage(self):
        path = c.PACKAGE + '/programs.py'
        self.edit(path, 'return self.add(m.Clock(self.qualified(identity), basis, resolution))',
                  'return self.add(m.Clock(self.qualified(identity), "logical", resolution))', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'Source/API inventory drift'):
            c.validate(self.root, self.ledger)

    def test_compatibility_alias_cannot_be_repointed_with_new_file_pin(self):
        self.edit(c.PACKAGE + '/inspection.py', 'summary = inspect', 'summary = graph', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'compatibility/display aliases differ'):
            c.validate(self.root, self.ledger)

    def test_root_export_same_name_wrong_owned_target_rejects(self):
        self.edit(c.PACKAGE + '/__init__.py', '    Role,', '    TypeSpec as Role,', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'export target/alias census differs'):
            c.validate(self.root, self.ledger)

    def test_imported_arbitrary_attribute_cannot_become_public_by_repinning(self):
        path = c.PACKAGE + '/__init__.py'
        self.edit(path, "    'Role',", "    'Path',", repin_file=True)
        with (self.root / path).open('a') as stream:
            stream.write('\nfrom pathlib import Path\n')
        self.ledger['inventory']['files'][path] = c.digest((self.root / path).read_bytes())
        with self.assertRaisesRegex(c.ApiCoverageError, 'outside the reviewed owned surface'):
            c.validate(self.root, self.ledger)

    def test_native_route_mutation_rejects_beyond_file_hash(self):
        self.edit('src/biocompiler/core_policy_operational.py',
                  'return self._call("execute-policy",', 'return self._call("check-policy-lowering",', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'Native operation route differs'):
            c.validate(self.root, self.ledger)

    def test_native_dropped_original_input_rejects_beyond_file_hash(self):
        self.edit('src/biocompiler/core_policy_operational.py',
                  '"candidate": candidate, "timeline": timeline}', '"candidate": candidate}', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'original-input inventory differs'):
            c.validate(self.root, self.ledger)

    def before_assurance(self):
        projected = copy.deepcopy(self.ledger)
        projected['coverage'] = {key: row for key, row in projected['coverage'].items()
                                if not key.startswith(c.ASSURANCE_PREFIXES) and key not in c.ASSURANCE_DEPENDENCIES}
        projected['witnesses'] = {key: row for key, row in projected['witnesses'].items() if not key.startswith('assurance.')}
        return projected

    def test_assurance_preserves_all_1439_previous_api_meanings(self):
        previous = self.before_assurance()
        self.assertEqual((len(previous['coverage']), len(previous['witnesses'])), (1439, 200))
        metadata = {'coverage': previous['coverage'], 'witnesses': {
            key: {name: row[name] for name in ('path', 'symbol', 'role', 'distinction')}
            for key, row in previous['witnesses'].items()}}
        encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')
        self.assertEqual(c.digest(encoded), c.BEFORE_ASSURANCE_METADATA_SHA256)
        self.assertEqual(c.BEFORE_ASSURANCE_METADATA_SHA256, '404ab87f1e9deb42ff3c117d84bc7c3da8926036a429beade5b5b933a58737ff')

    def test_assurance_evidence_cannot_promote_native_or_empirical_acceptance(self):
        self.ledger['coverage']['biocompiler.policy.approximation.ApproximationContract']['scope'] = 'Native and biological acceptance.'
        with self.assertRaisesRegex(c.ApiCoverageError, 'metadata differs'):
            c.validate(self.root, self.ledger)

    def before_transfer_network(self):
        projected = self.before_assurance()
        projected['coverage'] = {key: row for key, row in projected['coverage'].items()
                                if not key.startswith(c.TRANSFER_NETWORK_PREFIXES) and key not in c.TRANSFER_NETWORK_DEPENDENCIES}
        projected['witnesses'] = {key: row for key, row in projected['witnesses'].items() if not key.startswith('transfer_network.')}
        return projected

    def test_transfer_network_preserves_all_1406_previous_api_meanings(self):
        previous = self.before_transfer_network()
        self.assertEqual((len(previous['coverage']), len(previous['witnesses'])), (1406, 195))
        metadata = {'witnesses': {key: {name: row[name] for name in ('path', 'symbol', 'role', 'distinction')}
                                 for key, row in previous['witnesses'].items()}, 'coverage': previous['coverage']}
        encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        self.assertEqual(c.digest(encoded), c.BEFORE_TRANSFER_NETWORK_METADATA_SHA256)
        self.assertEqual(c.BEFORE_TRANSFER_NETWORK_METADATA_SHA256, 'de1b1202fcbfe2453c78be6fbe40828189fa28f32fc62eede742a0f4fe19225d')

    def test_transfer_network_cannot_upgrade_python_expansion_to_native_acceptance(self):
        self.ledger['coverage']['biocompiler.policy.quantitative.SampledTransferNetwork']['scope'] = 'Proves native target acceptance.'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)

    def before_transfer_pair(self):
        projected = self.before_transfer_network()
        projected['coverage'] = {key: row for key, row in projected['coverage'].items()
                                if not key.startswith(c.TRANSFER_PAIR_PREFIXES) and key not in c.TRANSFER_PAIR_DEPENDENCIES}
        projected['witnesses'] = {key: row for key, row in projected['witnesses'].items() if not key.startswith('transfer_pair.')}
        return projected

    def test_transfer_pair_preserves_all_1375_previous_api_meanings(self):
        previous = self.before_transfer_pair()
        self.assertEqual((len(previous['coverage']), len(previous['witnesses'])), (1375, 191))
        metadata = {'witnesses': {key: {name: row[name] for name in ('path', 'symbol', 'role', 'distinction')}
                                 for key, row in previous['witnesses'].items()}, 'coverage': previous['coverage']}
        encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        self.assertEqual(c.digest(encoded), c.BEFORE_TRANSFER_PAIR_METADATA_SHA256)
        self.assertEqual(c.BEFORE_TRANSFER_PAIR_METADATA_SHA256, '169ff67cf58f5e2d3babb3e9f8c63b55128a2613c2f04e1ad73d3c1884968874')

    def test_transfer_pair_cannot_upgrade_python_expansion_to_native_acceptance(self):
        self.ledger['coverage']['biocompiler.policy.quantitative.SampledTransferPair']['scope'] = 'Proves native target acceptance.'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)

    def before_step_quantitative(self):
        projected = self.before_transfer_pair()
        projected['coverage'] = {key: row for key, row in projected['coverage'].items()
                                if not key.startswith(c.STEP_QUANTITATIVE_PREFIX) and key not in c.STEP_QUANTITATIVE_DEPENDENCIES}
        projected['witnesses'] = {key: row for key, row in projected['witnesses'].items() if not key.startswith('step_quantitative.')}
        return projected

    def test_step_quantitative_preserves_all_1350_previous_api_meanings(self):
        previous = self.before_step_quantitative()
        self.assertEqual((len(previous['coverage']), len(previous['witnesses'])), (1350, 188))
        metadata = {'witnesses': {key: {name: row[name] for name in ('path', 'symbol', 'role', 'distinction')}
                                 for key, row in previous['witnesses'].items()}, 'coverage': previous['coverage']}
        encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        self.assertEqual(c.digest(encoded), c.BEFORE_STEP_QUANTITATIVE_METADATA_SHA256)
        self.assertEqual(c.BEFORE_STEP_QUANTITATIVE_METADATA_SHA256, '8db45c56f118a7271e7ce6225b7a2bb0940793b3807a016a6442dd6f36c2d3d7')

    def test_step_quantitative_cannot_upgrade_python_expansion_to_native_acceptance(self):
        self.ledger['coverage']['biocompiler.policy.quantitative.SampledStepReservoir']['scope'] = 'Proves native target acceptance.'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)

    def before_target_planning(self):
        projected = self.before_step_quantitative()
        projected['coverage'] = {key: row for key, row in projected['coverage'].items() if not key.startswith(c.TARGET_PLANNING_PREFIXES)}
        projected['witnesses'] = {key: row for key, row in projected['witnesses'].items() if not key.startswith('target_planning.')}
        return projected

    def test_target_planning_preserves_all_1297_previous_api_meanings(self):
        previous = self.before_target_planning()
        self.assertEqual((len(previous['coverage']), len(previous['witnesses'])), (1297, 174))
        metadata = {'witnesses': {key: {name: row[name] for name in ('path', 'symbol', 'role', 'distinction')}
                                 for key, row in previous['witnesses'].items()}, 'coverage': previous['coverage']}
        encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        self.assertEqual(c.digest(encoded), c.BEFORE_TARGET_PLANNING_METADATA_SHA256)
        self.assertEqual(c.BEFORE_TARGET_PLANNING_METADATA_SHA256, '67e9eff1bc5a45833bfa0ab2034d2b64f30d36b51e3f278ccb1c0e993bbc58ec')

    def test_target_planning_cannot_upgrade_diagnostics_to_native_acceptance(self):
        self.ledger['coverage']['biocompiler.core_policy_planning.PolicyTargetPlanningClient.plan']['scope'] = 'Proves native target acceptance.'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)

    def before_network(self):
        projected = self.before_target_planning()
        projected['coverage'] = {key: row for key, row in projected['coverage'].items() if key not in c.NETWORK_DEPENDENCIES}
        return projected

    def test_network_preserves_all_1279_previous_api_meanings(self):
        previous = self.before_network()
        self.assertEqual((len(previous['coverage']), len(previous['witnesses'])), (1279, 174))
        self.assertEqual(len(c.NETWORK_DEPENDENCIES), 18)
        metadata = {'witnesses': {key: {name: row[name] for name in ('path', 'symbol', 'role', 'distinction')}
                                 for key, row in previous['witnesses'].items()}, 'coverage': previous['coverage']}
        encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        self.assertEqual(c.digest(encoded), c.BEFORE_NETWORK_METADATA_SHA256)
        self.assertEqual(c.BEFORE_NETWORK_METADATA_SHA256, 'fb0cae52848ceef5f8d9ee9743846a23647175dc70e8144741aee087f5ca4a40')

    def test_network_dependency_cannot_upgrade_transport_to_native_acceptance(self):
        self.ledger['coverage']['biocompiler.core_policy_implementation._network_anchors']['scope'] = 'Proves native network acceptance.'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)

    def before_module_linking(self):
        projected = self.before_network()
        projected['coverage'] = {key: row for key, row in projected['coverage'].items()
                                 if not key.startswith(c.MODULE_LINKING_PREFIXES)}
        projected['witnesses'] = {key: row for key, row in projected['witnesses'].items()
                                  if not key.startswith('module_linking.')}
        return projected

    def test_module_linking_preserves_all_1187_previous_api_meanings(self):
        previous = self.before_module_linking()
        self.assertEqual((len(previous['coverage']), len(previous['witnesses'])), (1187, 164))
        metadata = {'witnesses': {key: {name: row[name] for name in ('path', 'symbol', 'role', 'distinction')}
                                 for key, row in previous['witnesses'].items()}, 'coverage': previous['coverage']}
        encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        self.assertEqual(c.digest(encoded), c.BEFORE_MODULE_LINKING_METADATA_SHA256)
        self.assertEqual(c.BEFORE_MODULE_LINKING_METADATA_SHA256, '4505ad72eaddb74c56cb7587ebbf2b719cd9b78b2e6c673b76c8820e19335bef')

    def test_module_linking_witness_cannot_upgrade_mocked_transport_to_native_proof(self):
        self.ledger['witnesses']['module_linking.transport']['distinction'] = 'Exact native module elaboration verified.'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)

    def before_quantitative(self):
        projected = self.before_module_linking()
        projected['coverage'] = {key: row for key, row in projected['coverage'].items()
                                 if not key.startswith(c.QUANTITATIVE_PREFIX) and key not in c.QUANTITATIVE_DEPENDENCIES}
        projected['witnesses'] = {key: row for key, row in projected['witnesses'].items()
                                  if not key.startswith('quantitative.')}
        return projected

    def test_quantitative_preserves_all_1157_previous_api_meanings(self):
        previous = self.before_quantitative()
        self.assertEqual((len(previous['coverage']), len(previous['witnesses'])), (1157, 160))
        metadata = {'witnesses': {key: {name: row[name] for name in ('path', 'symbol', 'role', 'distinction')}
                                 for key, row in previous['witnesses'].items()}, 'coverage': previous['coverage']}
        encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        self.assertEqual(c.digest(encoded), c.BEFORE_QUANTITATIVE_METADATA_SHA256)
        self.assertEqual(c.BEFORE_QUANTITATIVE_METADATA_SHA256, '5bf67512edb43be299929b44a147cec8951867fc52bd7fffa169ef2aa10615ad')

    def test_quantitative_export_cannot_alias_untyped_source_quantity(self):
        self.edit('src/biocompiler/policy/quantitative.py', '__all__ = [', 'from .model import Quantity as SampledReservoir\n\n__all__ = [', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'export target/alias census differs'):
            c.validate(self.root, self.ledger)

    def test_quantitative_witness_cannot_upgrade_authoring_to_native_proof(self):
        self.ledger['witnesses']['quantitative.grid']['distinction'] = 'Exact native material-law acceptance.'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)

    def before_refinement(self):
        projected = self.before_quantitative()
        projected['coverage'] = {key: row for key, row in projected['coverage'].items()
                                 if not key.startswith(c.REFINEMENT_PREFIXES)}
        projected['witnesses'] = {key: row for key, row in projected['witnesses'].items()
                                  if not key.startswith('refinement.')}
        return projected

    def test_refinement_preserves_all_1083_previous_api_meanings(self):
        previous = self.before_refinement()
        self.assertEqual(len(previous['coverage']), 1083)
        self.assertEqual(len(previous['witnesses']), 152)
        metadata = {'witnesses': {key: {name: row[name] for name in ('path', 'symbol', 'role', 'distinction')}
                                 for key, row in previous['witnesses'].items()}, 'coverage': previous['coverage']}
        encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        self.assertEqual(c.digest(encoded), c.BEFORE_REFINEMENT_METADATA_SHA256)
        self.assertEqual(c.BEFORE_REFINEMENT_METADATA_SHA256, 'd717a4c1f9cd7d81a90e8c3a71311d445ff46fb79b13233671a7e44fb65c99a1')

    def test_refinement_replay_cannot_drop_saved_report_even_with_file_repin(self):
        self.edit('src/biocompiler/core_policy_refinement.py',
                  '"limits": limits, "report": report}', '"limits": limits}', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'original-input inventory differs'):
            c.validate(self.root, self.ledger)

    def test_refinement_namespace_export_cannot_target_source_check(self):
        self.edit('src/biocompiler/policy/refinement.py',
                  '__all__ = [', 'from .validation import check\n\n__all__ = [', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'export target/alias census differs'):
            c.validate(self.root, self.ledger)

    def test_refinement_witness_cannot_upgrade_to_native_proof_claim(self):
        self.ledger['witnesses']['refinement.derivation']['distinction'] = 'Native proof established from child hashes.'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)

    def before_finite_machine(self):
        projected = self.before_refinement()
        projected['coverage'] = {key: row for key, row in projected['coverage'].items()
                                 if key not in c.FINITE_MACHINE_DEPENDENCIES}
        return projected

    def test_finite_machine_preserves_all_1063_previous_api_meanings(self):
        previous = self.before_finite_machine()
        self.assertEqual(len(previous['coverage']), 1063)
        self.assertEqual(len(c.FINITE_MACHINE_DEPENDENCIES), 20)
        self.assertTrue(all(self.ledger['coverage'][key]['status'] == 'dependency'
                            for key in c.FINITE_MACHINE_DEPENDENCIES))
        metadata = {'witnesses': {key: {name: row[name] for name in ('path', 'symbol', 'role', 'distinction')}
                                 for key, row in previous['witnesses'].items()},
                    'coverage': previous['coverage']}
        encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')
        self.assertEqual(c.digest(encoded), c.BEFORE_FINITE_MACHINE_METADATA_SHA256)

    def before_typed_modules(self):
        projected = self.before_finite_machine()
        projected['coverage'] = {key: row for key, row in projected['coverage'].items()
                                 if not key.startswith(c.TYPED_MODULE_PREFIXES)}
        projected['witnesses'] = {key: row for key, row in projected['witnesses'].items()
                                  if not key.startswith(('typed.', 'modules.'))}
        return projected

    def test_typed_modules_preserve_all_905_previous_api_meanings(self):
        previous = self.before_typed_modules()
        self.assertEqual(len(previous['coverage']), 905)
        self.assertEqual(len(previous['witnesses']), 138)
        metadata = {'witnesses': {key: {name: row[name] for name in ('path', 'symbol', 'role', 'distinction')}
                                 for key, row in previous['witnesses'].items()},
                    'coverage': previous['coverage']}
        encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')
        self.assertEqual(c.digest(encoded), c.BEFORE_TYPED_MODULES_METADATA_SHA256)

    def before_composition_profiles(self):
        projected = self.before_typed_modules()
        self.assertTrue(set(c.COMPOSITION_DEPENDENCIES) <= set(projected['coverage']))
        projected['coverage'] = {key: row for key, row in projected['coverage'].items()
                                 if key not in c.COMPOSITION_DEPENDENCIES}
        return projected

    def before_research_project(self):
        """Remove only the additive researcher-project surface and its witnesses."""
        projected = self.before_composition_profiles()
        projected['coverage'] = {key: row for key, row in projected['coverage'].items()
                                 if not key.startswith('biocompiler.policy.research_project.')}
        projected['witnesses'] = {key: row for key, row in projected['witnesses'].items()
                                  if not key.startswith('research_project.')}
        return projected

    def test_research_project_preserves_every_prior_evidence_meaning(self):
        projected = self.before_research_project()
        metadata = {'witnesses': {key: {name: row[name] for name in ('path', 'symbol', 'role', 'distinction')}
                                 for key, row in projected['witnesses'].items()},
                    'coverage': projected['coverage']}
        self.assertEqual((len(projected['coverage']), len(projected['witnesses'])), (790, 129))
        encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode()
        self.assertEqual(c.digest(encoded),
                         '6379cd7e0a0e92cd6a39d5bb57cd16497288694b662490c23d8a305a4f11f43c')

    def test_research_project_witness_cannot_upgrade_mocked_transport_to_native_proof(self):
        self.ledger['witnesses']['research_project.routes']['distinction'] = 'Native and biological acceptance.'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)

    def before_staged_regimen(self):
        """Restore only the explicitly superseded five-transition witness."""
        projected = self.before_research_project()
        witness = projected['witnesses']['pattern.ordered_effects']
        self.assertEqual(witness['symbol'],
            'PolicyPatternTests.test_ordered_effects_literal_machine_and_all_seven_transitions')
        witness['symbol'] = 'PolicyPatternTests.test_ordered_effects_literal_machine_and_all_five_transitions'
        return projected

    def test_staged_expansion_supersedes_only_its_original_witness(self):
        projected = self.before_staged_regimen()
        metadata = {'witnesses': {key: {name: row[name] for name in ('path', 'symbol', 'role', 'distinction')}
                                 for key, row in projected['witnesses'].items()},
                    'coverage': projected['coverage']}
        encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode()
        self.assertEqual(c.digest(encoded),
                         '59239c96840218569d770e9322cfc0693f7f05a0d79564abde6d1912bc8aab2b')

    def component_projection(self):
        """Remove precisely the selection extension, preserving old meanings."""
        shared_helpers = {
            'biocompiler.core_policy_component_material._assessment',
            'biocompiler.core_policy_component_material._candidate',
            'biocompiler.core_policy_component_material._report',
            'biocompiler.core_policy_material._artifact_members',
        }
        projected = self.before_staged_regimen()
        projected['coverage'] = {key: row for key, row in projected['coverage'].items()
            if not key.startswith(('biocompiler.core_policy_component_selection.',
                                   'biocompiler.policy.component_selection.')) and key not in shared_helpers}
        projected['witnesses'] = {key: row for key, row in projected['witnesses'].items()
                                  if not key.startswith('selection.')}
        return projected

    def test_selection_additions_preserve_all_component_evidence_meanings(self):
        projected = self.component_projection()
        witnesses = {key: {name: row[name] for name in ('path', 'symbol', 'role', 'distinction')}
                     for key, row in projected['witnesses'].items()}
        self.assertEqual((len(projected['coverage']), len(witnesses)), (740, 106))
        original = json.dumps({'witnesses': witnesses, 'coverage': projected['coverage']}, ensure_ascii=True,
                              sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        self.assertEqual(c.digest(original), '2367be4f22a4985eb15fce30dc799abfb254a22ae86f7de665e23fdc7ed800a2')
        self.assertEqual((len(set(c.MODULES) - {'research_project', 'typed', 'modules', 'refinement', 'quantitative', 'module_linking', 'planning', 'quantitative_composition', 'quantitative_assurance', 'approximation', 'realization_evidence'}),
                          len(set(c.CLIENTS) - {'core_policy_refinement', 'core_policy_module_linking', 'core_policy_planning', 'core_policy_quantitative_assurance'})), (30, 6))
        additions = {key: row for key, row in self.before_research_project()['coverage'].items()
                     if key not in projected['coverage']}
        self.assertEqual(len(additions), 50)
        shared = [row for row in additions.values() if row['status'] == 'shared_invariant']
        self.assertEqual(len(shared), 12)
        self.assertTrue(all('synthetic selection transport/publication' in row['scope']
                            and 'no native semantic execution' in row['scope'] for row in shared))

    def test_selection_generation_preserves_prior_metadata_except_explicit_absent_compile_supersession(self):
        projected = self.before_staged_regimen()
        additions = {
            'biocompiler.core_policy_component_selection.COMPILE_OPERATION',
            'biocompiler.core_policy_component_selection.PRODUCER_PROFILE',
            'biocompiler.core_policy_component_selection.PolicyComponentSelectionClient.compile',
            'biocompiler.policy.component_selection.compile',
        }
        for key in additions:
            del projected['coverage'][key]
        new_witnesses = {'selection.compile_' + suffix for suffix in
            ('role', 'routes', 'snapshot', 'losers', 'negotiation', 'failure', 'sdk')}
        for key in new_witnesses:
            del projected['witnesses'][key]
        projected['witnesses']['selection.routes'].update(
            symbol='PolicyComponentSelectionTransportTests.test_all_three_routes_preserve_complete_originals_and_have_no_compile',
            distinction='Three synthetic selection routes retain complete supplied originals and replay wrapper; no selection compile API is exposed.')
        projected['witnesses']['selection.sdk_routes']['distinction'] = (
            'Public selection check and replay wrappers retain the complete saved synthetic result without a compile API.')
        metadata = {'witnesses': {key: {name: row[name] for name in ('path', 'symbol', 'role', 'distinction')}
                                 for key, row in projected['witnesses'].items()},
                    'coverage': projected['coverage']}
        encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        self.assertEqual(c.digest(encoded), '3045dcf7ea8e976ba6d9de2eaec754cba09047cc9978aa6de83597979d3f409d')

    def test_component_additions_preserve_all_original_evidence_meanings(self):
        self.ledger = self.component_projection()
        additional_shared_helpers = {
            'biocompiler.core_policy_material._context_obligations',
            'biocompiler.core_policy_material._structure',
            'biocompiler.policy.material._publish_fresh',
        }
        retained = {key: row for key, row in self.ledger['coverage'].items()
                    if not key.startswith(('biocompiler.core_policy_component_material.',
                                           'biocompiler.policy.component_material.'))
                    and key not in additional_shared_helpers}
        witnesses = {key: {name: row[name] for name in ('path', 'symbol', 'role', 'distinction')}
                     for key, row in self.ledger['witnesses'].items() if not key.startswith('component.')}
        self.assertEqual((len(retained), len(witnesses)), (700, 90))
        original = json.dumps({'witnesses': witnesses, 'coverage': retained}, ensure_ascii=True,
                              sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        self.assertEqual(c.digest(original), 'f16a88c77afaea4f7cbae56e80e38afc8d5a4c894616ca158578b707d393bb4a')
        self.assertEqual((len(set(c.MODULES) - {'component_selection', 'research_project', 'typed', 'modules', 'refinement', 'quantitative', 'module_linking', 'planning', 'quantitative_composition', 'quantitative_assurance', 'approximation', 'realization_evidence'}),
                          len(set(c.CLIENTS) - {'core_policy_component_selection', 'core_policy_refinement', 'core_policy_module_linking', 'core_policy_planning', 'core_policy_quantitative_assurance'})), (29, 5))
        component_rows = [row for key, row in self.ledger['coverage'].items()
                          if key.startswith(('biocompiler.core_policy_component_material.',
                                             'biocompiler.policy.component_material.'))
                          and row['status'] == 'shared_invariant']
        self.assertEqual(len(component_rows), 12)
        self.assertTrue(all('synthetic component transport/publication' in row['scope']
                            and 'no native semantic execution' in row['scope'] for row in component_rows))

    def test_component_cannot_reuse_old_operation_after_file_repin(self):
        self.edit('src/biocompiler/core_policy_component_material.py',
                  'return self._call("export-policy-component-material",',
                  'return self._call("export-policy-material",', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'Native operation route differs'):
            c.validate(self.root, self.ledger)

    def test_component_replay_cannot_drop_complete_report_after_file_repin(self):
        self.edit('src/biocompiler/core_policy_component_material.py',
                  '"limits": limits, "report": report}', '"limits": limits}', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'original-input inventory differs'):
            c.validate(self.root, self.ledger)

    def test_component_result_inherited_contract_is_pinned_without_runtime_enumeration(self):
        self.edit('src/biocompiler/core_policy_component_material.py',
                  'class PolicyComponentMaterialResult(material.PolicyMaterialResult):',
                  'class PolicyComponentMaterialResult(object):', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'Source/API inventory drift'):
            c.validate(self.root, self.ledger)

    def test_component_witness_cannot_gain_native_claim_or_unrelated_owner(self):
        row = self.ledger['witnesses']['component.routes']
        row['distinction'] = 'Native runtime correctness and full release acceptance.'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)
        self.ledger = copy.deepcopy(self.original)
        row = self.ledger['witnesses']['component.routes']
        unrelated = self.ledger['witnesses']['builder.freeze']
        for field in ('path', 'symbol', 'file_sha256', 'syntax_sha256'):
            row[field] = unrelated[field]
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)

    def test_selection_routes_cannot_reuse_inner_operations_or_drop_report(self):
        path = 'src/biocompiler/core_policy_component_selection.py'
        original = (self.root / path).read_bytes()
        for operation in ('compile', 'check', 'replay', 'export'):
            self.edit(path, 'return self._call("' + operation + '-policy-component-selection",',
                      'return self._call("' + operation + '-policy-component-material",', repin_file=True)
            with self.subTest(operation=operation), self.assertRaisesRegex(c.ApiCoverageError, 'Native operation route differs'):
                c.validate(self.root, self.ledger)
            (self.root / path).write_bytes(original)
        self.edit(path, '"limits": limits, "report": report}', '"limits": limits}', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'original-input inventory differs'):
            c.validate(self.root, self.ledger)

    def test_selection_result_and_core_compile_remain_source_bound(self):
        path = 'src/biocompiler/core_policy_component_selection.py'
        original = (self.root / path).read_bytes()
        self.edit(path, 'class PolicyComponentSelectionResult(material.PolicyMaterialResult):',
                  'class PolicyComponentSelectionResult(object):', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'Source/API inventory drift'):
            c.validate(self.root, self.ledger)
        (self.root / path).write_bytes(original)
        self.edit(path,
                  'return self._call("compile-policy-component-selection", {"request": request, "limits": limits}, cancelled=cancelled)',
                  'return self.check(request, {}, limits, cancelled=cancelled)', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'Native route shape differs'):
            c.validate(self.root, self.ledger)

    def test_selection_witness_meaning_owner_and_private_classification_are_pinned(self):
        self.ledger['witnesses']['selection.routes']['distinction'] = 'Native full release acceptance.'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)
        self.ledger = copy.deepcopy(self.original)
        row = self.ledger['witnesses']['selection.routes']
        unrelated = self.ledger['witnesses']['builder.freeze']
        for field in ('path', 'symbol', 'file_sha256', 'syntax_sha256'):
            row[field] = unrelated[field]
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)
        self.ledger = copy.deepcopy(self.original)
        self.ledger['coverage']['biocompiler.core_policy_material._artifact_members']['status'] = 'source_only'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Private dependency classification changed'):
            c.validate(self.root, self.ledger)

    def test_cli_command_cannot_be_silently_renamed(self):
        self.edit(c.PACKAGE + '/cli.py', '("export-schema", "Export the versioned authoring document schema."),',
                  '("export-python", "Export the versioned authoring document schema."),', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'CLI route census differs'):
            c.validate(self.root, self.ledger)

    def test_portable_ast_helper_is_an_explicit_source_dependency(self):
        path = 'tools/check_policy_semantic_coverage.py'
        self.assertIn(path, self.ledger['inventory']['files'])
        self.edit(path, '"FunctionDef": {"type_params": []}', '"FunctionDef": {"type_params": ["unreviewed"]}')
        with self.assertRaisesRegex(c.ApiCoverageError, 'Source/API inventory drift'):
            c.validate(self.root, self.ledger)

    def test_new_builder_method_cannot_replace_old_same_sized_inventory(self):
        self.edit(c.PACKAGE + '/programs.py', 'def qualified(self, identity: str)', 'def quietly_rename(self, identity: str)', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'builder method census differs'):
            c.validate(self.root, self.ledger)

    def test_missing_symbol_and_new_schema_fields_are_not_hash_coverage(self):
        self.ledger['inventory']['entries'].pop()
        with self.assertRaisesRegex(c.ApiCoverageError, 'Source/API inventory drift'):
            c.validate(self.root, self.ledger)
        self.ledger = copy.deepcopy(self.original)
        self.ledger['accepted'] = True
        with self.assertRaisesRegex(c.ApiCoverageError, 'unexpected or missing fields'):
            c.validate(self.root, self.ledger)

    def test_source_only_schema_cannot_claim_runtime_acceptance(self):
        self.ledger['claim_scope'] = 'Every exposed API is runtime verified.'
        with self.assertRaisesRegex(c.ApiCoverageError, 'acceptance claim'):
            c.validate(self.root, self.ledger)
        self.ledger = copy.deepcopy(self.original)
        self.ledger['coverage']['biocompiler.policy.model.declaration_ref']['status'] = 'source_only'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Compatibility support'):
            c.validate(self.root, self.ledger)
        self.ledger = copy.deepcopy(self.original)
        self.ledger['runtime_protocol_scope'] = 'All Python runtime methods are inventoried and symbolically evaluated.'
        with self.assertRaisesRegex(c.ApiCoverageError, 'runtime protocol scope must remain explicit'):
            c.validate(self.root, self.ledger)
        self.ledger = copy.deepcopy(self.original)
        self.ledger['known_gaps'] = []
        with self.assertRaisesRegex(c.ApiCoverageError, 'limitations must remain'):
            c.validate(self.root, self.ledger)

    def test_dropped_witness_is_distinct_from_malformed_witness(self):
        del self.ledger['witnesses']['builder.holes']
        with self.assertRaisesRegex(c.ApiCoverageError, 'Dropped required expansion witness'):
            c.validate(self.root, self.ledger)
        self.ledger = copy.deepcopy(self.original)
        self.ledger['witnesses']['builder.holes']['role'] = 'passing_runtime_proof'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Malformed witness distinction'):
            c.validate(self.root, self.ledger)

    def test_repinned_expansion_witness_cannot_point_to_unrelated_test(self):
        wrong = self.ledger['witnesses']['builder.holes']
        source = self.ledger['witnesses']['builder.freeze']
        wrong['symbol'], wrong['syntax_sha256'] = source['symbol'], source['syntax_sha256']
        with self.assertRaisesRegex(c.ApiCoverageError, 'Repinned expansion witness points to the wrong test'):
            c.validate(self.root, self.ledger)

    def test_shared_witness_cannot_be_repointed_with_all_current_source_pins(self):
        row = self.ledger['witnesses']['shared.immutable_snapshots.1']
        wrong = self.ledger['witnesses']['builder.freeze']
        for name in ('path', 'symbol', 'file_sha256', 'syntax_sha256'):
            row[name] = wrong[name]
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)

    def test_source_only_row_cannot_gain_unrelated_shared_evidence(self):
        row = self.ledger['coverage']['biocompiler.policy.material.replay']
        self.assertEqual(row['status'], 'source_only')
        row.update(status='shared_invariant', witnesses=['builder.holes'], scope='Invented full replay coverage')
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)

    def test_witness_body_and_file_must_both_match(self):
        path = 'tests/test_policy_builders.py'
        self.edit(path, 'self.assertEqual(builder.snapshot().holes, ())', 'self.assertEqual(builder.snapshot().holes, ())  # review change')
        with self.assertRaisesRegex(c.ApiCoverageError, 'Stale witness source'):
            c.validate(self.root, self.ledger)
        for witness in self.ledger['witnesses'].values():
            if witness['path'] == path:
                witness['file_sha256'] = c.digest((self.root / path).read_bytes())
        # A comment-only change preserves every AST; a semantically changed test does not.
        c.validate(self.root, self.ledger)
        self.edit(path, 'self.assertEqual(builder.snapshot().holes, ())', 'self.assertEqual(builder.snapshot().holes, (slot,))')
        for witness in self.ledger['witnesses'].values():
            if witness['path'] == path:
                witness['file_sha256'] = c.digest((self.root / path).read_bytes())
        with self.assertRaisesRegex(c.ApiCoverageError, 'Stale witness source'):
            c.validate(self.root, self.ledger)

    def test_dropping_specific_expansion_link_cannot_hide_in_shared_status(self):
        row = self.ledger['coverage']['biocompiler.policy.programs.ProgramBuilder.resolve']
        row['status'] = 'shared_invariant'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Missing independent builder expansion'):
            c.validate(self.root, self.ledger)
        self.ledger = copy.deepcopy(self.original)
        row = self.ledger['coverage']['biocompiler.policy.programs.ProgramBuilder.resolve']
        row['witnesses'] = ['builder.defaults']
        with self.assertRaisesRegex(c.ApiCoverageError, 'Missing independent builder expansion'):
            c.validate(self.root, self.ledger)

    def test_existing_syntax_field_links_cannot_be_dropped_or_forged(self):
        links = self.ledger['syntax_links']
        links['biocompiler.policy.model.Clock.basis'] = 'field:Clock.simultaneous'
        with self.assertRaisesRegex(c.ApiCoverageError, 'syntax-ledger links'):
            c.validate(self.root, self.ledger)

    def test_syntax_link_target_cannot_keep_id_and_change_source_owner(self):
        path = self.root / 'protocol/policy-semantic-coverage-v0.1.json'
        original = json.loads(path.read_text())
        row = next(row for row in original['entries'] if row['id'] == 'field:Clock.basis')
        row['source']['symbol'] = 'Clock.simultaneous'
        path.write_text(json.dumps(original))
        with self.assertRaisesRegex(c.ApiCoverageError, 'another source owner'):
            c.validate(self.root, self.ledger)

    def test_bounded_decoder_duplicate_numbers_depth_nodes_and_paths(self):
        target = self.root / 'bad.json'
        for raw in ('{"a":1,"a":2}', '{"a":1.25}', '{"a":NaN}', '[' * 80 + '0' + ']' * 80):
            with self.subTest(raw=raw[:30]):
                target.write_text(raw)
                with self.assertRaises(c.ApiCoverageError):
                    c.read_ledger(target)
        with self.assertRaisesRegex(c.ApiCoverageError, 'array limit'):
            c.bounded([0] * 4097)
        with patch.object(c, 'MAX_NODES', 4), self.assertRaisesRegex(c.ApiCoverageError, 'node limit'):
            c.bounded({'a': [1, 2, 3]})
        with patch.object(c, 'MAX_LEDGER', 4):
            target.write_text('{"valid":true}')
            with self.assertRaisesRegex(c.ApiCoverageError, 'byte limit'):
                c.read_ledger(target)
        for path in ('../outside', '/absolute', ''):
            with self.subTest(path=path), self.assertRaises(c.ApiCoverageError):
                c.read_bytes(self.root, path)
        target = self.root / 'link.py'
        target.symlink_to(c.ROOT / 'src/biocompiler/policy/model.py')
        with self.assertRaisesRegex(c.ApiCoverageError, 'escaping'):
            c.read_bytes(self.root, 'link.py')

    def test_cli_has_no_regeneration_or_acceptance_switch(self):
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(c.main(['--root', str(self.root)]), 0)
        self.assertEqual(json.loads(output.getvalue())['status'], 'source_inventory_checked')
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            c.main(['--regenerate'])
        self.edit(c.PACKAGE + '/logic.py', 'def literal(value:', 'def literal(renamed:')
        with redirect_stderr(io.StringIO()) as error:
            self.assertEqual(c.main(['--root', str(self.root)]), 1)
        self.assertIn('inventory drift', error.getvalue())


if __name__ == '__main__':
    unittest.main()

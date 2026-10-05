"""Exact cross-language declarations and immutable original package32 census."""
import hashlib
import json
from pathlib import Path
import re
import tarfile
import unittest

from biocompiler.artifacts.manifest import ReferenceBuildRequest
from biocompiler.core_pipeline_manager import capability_profile
from biocompiler.core_reference_package_protocol import ACTIONS, declaration

ROOT = Path(__file__).resolve().parents[1]
PACKET = 'generated/migration-next/reference-package-campaign-draft/'
PINS = {
    'original-311.json': '3db5514a955e04e9fad05bdb14cb8f7e8261e0b70937fb9e67e27423df71065d',
    'original-314.json': 'aa88e9fcdf4a9fd6ea3f1ef12364e4c997dd7c6045ee3fff93a50283b891d450',
    'frozen/sources.json': '2175314b615bfe6d7360a4e205d12da4dd55add8c5c05903a05f0ff36a439e94',
    'package/tools/capture_reference_package_workflows.py': '268283f56943abc8b887f6584ce465794f4425782bf434433acc90da6d7cecda',
}


class ReferencePackageApplicationTests(unittest.TestCase):
    def source(self):
        return (ROOT / 'core/lib/reference_package_session/reference_package_session.ml').read_text()

    def test_complete_native_application_literal_matches_detached_python_declaration(self):
        literal = self.source().split('{application|', 1)[1].split('|application}', 1)[0]
        native = json.loads(literal)
        self.assertEqual(native, declaration())
        self.assertEqual(native, json.loads((ROOT / 'protocol/reference-package-application-v1.json').read_bytes()))
        self.assertEqual(native['manager'], capability_profile())
        self.assertEqual(tuple(native['actions']), ACTIONS)
        changed = declaration()
        changed['operations'].clear()
        self.assertEqual(native, declaration())

    def test_native_dispatch_operations_and_exact_field_lists_match_declaration(self):
        source = self.source()
        operation_list = re.search(r'let operation_names=\[(.*?)\]', source, re.S)
        self.assertIsNotNone(operation_list)
        names = re.findall(r'"([^"]+)"', operation_list.group(1))
        operations = declaration()['operations']
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), set(operations))
        dispatch = source.split('let dispatch_value ', 1)[1].split('let expected_codes=', 1)[0]
        branches = list(re.finditer(r'^  \|"([^"]+)"->', dispatch, re.M))
        self.assertEqual(len(branches), len(names))
        self.assertEqual({branch.group(1) for branch in branches}, set(names))
        for index, branch in enumerate(branches):
            end = branches[index + 1].start() if index + 1 < len(branches) else len(dispatch)
            body = dispatch[branch.end():end]
            fields = re.search(r'let data=fields\[(.*?)\]raw', body, re.S)
            self.assertIsNotNone(fields, 'Missing exact fields for ' + branch.group(1))
            self.assertEqual(re.findall(r'"([^"]+)"', fields.group(1)),
                             operations[branch.group(1)]['fields'])

    def test_declared_request_result_matches_actual_native_and_python_domain_schema(self):
        declared = declaration()['results']['reference_build_request']
        self.assertEqual(declared, ReferenceBuildRequest.schema_version)
        source = (ROOT / 'core/lib/reference_artifact/reference_package_manifest.ml').read_text()
        self.assertIn('let schema_version="' + declared + '"', source)


class OriginalReferencePackageCampaignPreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Read tracked frozen evidence directly. This works in a fresh checkout
        # without restoring ignored drafts or depending on another worktree.
        archive = ROOT / 'docs/migration-handoff/2026-10-02/drafts.tar.gz'
        cls.packet = {}
        with tarfile.open(archive, 'r:gz') as source:
            for member in source:
                if member.name.startswith(PACKET):
                    logical = member.name[len(PACKET):]
                    if logical in PINS or logical.startswith('frozen/sources/'):
                        if not member.isfile() or logical in cls.packet or member.size > 32 * 1024 * 1024:
                            raise AssertionError('Malformed frozen package32 member')
                        cls.packet[logical] = source.extractfile(member).read()

    def test_whole_original_corpora_capture_and_source_index_bytes_are_unchanged(self):
        for name, pin in PINS.items():
            self.assertEqual(hashlib.sha256(self.packet[name]).hexdigest(), pin, name)

    def test_all_518_original_source_blobs_are_bound_to_exact_index(self):
        index = json.loads(self.packet['frozen/sources.json'])['sources']
        self.assertEqual(len(index), 518)
        self.assertEqual(sum(entry['bytes'] for entry in index.values()), 7_339_356)
        for logical, row in index.items():
            raw = self.packet['frozen/sources/' + row['sha256'] + '.blob']
            self.assertEqual(len(raw), row['bytes'], logical)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'], logical)

    def test_complete_original_method_census_and_actual_test_sources_are_retained(self):
        inventories = []
        for minor in ('311', '314'):
            value = json.loads(self.packet['original-' + minor + '.json'])
            self.assertEqual(value['scope'], 'original_public_package_values_not_native_acceptance')
            self.assertEqual(value['coverage']['methods'], 32)
            self.assertEqual(value['coverage']['events'], 270)
            self.assertEqual(value['coverage']['documents'], 3984)
            self.assertEqual(value['coverage']['document_bytes'], 10_546_404)
            methods = value['observed']['methods']
            inventories.append([row['id'] for row in methods])
            self.assertEqual(len(set(inventories[-1])), 32)
            self.assertEqual(value['baseline']['methods'], methods)
            self.assertEqual(value['baseline']['results'], value['observed']['results'])
            for row in methods:
                raw = (ROOT / row['source']['file']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), row['source']['sha256'])
        self.assertEqual(inventories[0], inventories[1])


if __name__ == '__main__':
    unittest.main()

"""Complete original package bytes supply representation, never native acceptance."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
from biocompiler import core_reference_package_views as module
from biocompiler.artifacts.manifest import ReferenceBuildRequest, RunMetadata, BuildManifest, PackageFile, AcceptedStage, ToolPin
from biocompiler.artifacts.sequences import SequenceExport
from biocompiler.compiler.reference import ReferencePackage
from biocompiler.core_client import CoreProtocolError
from biocompiler.core_pipeline_session import encode_document


class PackageViewsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = json.loads((REPO / 'tests/conformance/reference-packages-314.json').read_bytes())
        cls.rows = [row for row in cls.corpus['cases'] if row['outcome']['status'] == 'return']

    def test_all_original_packages_and_fresh_roots(self):
        decoder = module.PackageViews()
        self.assertEqual(len(self.rows), 7)
        for row in self.rows:
            raw = row['outcome']['value']
            with self.subTest(case=row['id']):
                request, manifest = decoder.build_request(raw['request']), decoder.manifest(raw['manifest'])
                package = decoder.package(request, manifest, bytes.fromhex(raw['data']))
                self.assertIs(type(package), ReferencePackage)
                self.assertIs(package.request, request)
                self.assertIs(package.manifest, manifest)
                self.assertEqual(request.to_dict(), raw['request'])
                self.assertEqual(manifest.to_dict(), raw['manifest'])
                self.assertEqual(package.build_fingerprint, raw['build_fingerprint'])
                self.assertEqual(package.archive_sha256, raw['archive_sha256'])
                other = decoder.manifest(raw['manifest'])
                self.assertIsNot(other, manifest)
                self.assertIsNot(other.files[0], manifest.files[0])
                self.assertIsNot(other.toolchain[0], manifest.toolchain[0])
                self.assertIs(decoder.build_request(raw['request'], original=request), request)

    def test_no_legacy_constructors_or_parsers(self):
        raw = self.rows[0]['outcome']['value']
        from contextlib import ExitStack
        classes = (ReferenceBuildRequest, RunMetadata, BuildManifest, PackageFile, AcceptedStage, ToolPin, SequenceExport, ReferencePackage)
        with ExitStack() as stack:
            for cls in classes:
                stack.enter_context(patch.object(cls, '__init__', side_effect=AssertionError('semantic constructor')))
                if hasattr(cls, 'from_dict'):
                    stack.enter_context(patch.object(cls, 'from_dict', side_effect=AssertionError('semantic parser')))
            decoder = module.PackageViews()
            request = decoder.build_request(raw['request'])
            manifest = decoder.manifest(raw['manifest'])
            self.assertEqual(decoder.package(request, manifest, bytes.fromhex(raw['data'])).manifest.to_dict(), raw['manifest'])
            metadata = next(row['input']['run_metadata'] for row in self.rows if row['input']['run_metadata'] is not None)
            self.assertEqual(decoder.metadata(metadata).to_dict(), metadata)

    def test_source_request_exact_scalar_identity(self):
        raw = self.rows[0]['outcome']['value']['request']
        request = module.PackageViews().build_request(raw)
        changed = copy.deepcopy(raw)
        changed['fasta_line_width'] = float(changed['fasta_line_width'])
        with self.assertRaises(CoreProtocolError):
            module.PackageViews().build_request(changed, original=request)
        changed = copy.deepcopy(raw)
        changed['extra'] = 1
        with self.assertRaises(CoreProtocolError):
            module.PackageViews().build_request(changed)

    def test_metadata_frozen_and_export_shape(self):
        decoder = module.PackageViews()
        value = {'schema_version': 'biocompiler.run_metadata.v0.1', 'timestamp_utc': '2026-10-01T00:00:00Z',
                 'machine_label': 'source', 'locations': {'z': 'one'}}
        result = decoder.metadata(value)
        value['locations']['z'] = 'two'
        self.assertEqual(result.locations['z'], 'one')
        with self.assertRaises(TypeError):
            result.locations['z'] = 'three'
        export = {'fasta': '>source\nAU\n', 'specification': '{}\n', 'line_width': 80,
                  'sequence_sha256': 'a'*64, 'molecular_fingerprint': 'b'*64}
        first, second = decoder.export(export), decoder.export(export)
        self.assertIsNot(first, second)
        self.assertEqual(first.fasta_bytes, export['fasta'].encode())
        for key, value in (('line_width', True), ('fasta', 3), ('specification', None)):
            with self.subTest(key=key), self.assertRaises(CoreProtocolError):
                decoder.export({**export, key: value})
        self.assertEqual(result.to_dict()['locations'], {'z': 'one'})


if __name__ == '__main__':
    unittest.main()

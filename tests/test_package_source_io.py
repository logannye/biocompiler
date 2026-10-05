"""Actual bounded filesystem callbacks; no native execution or acceptance claim."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from biocompiler import core_reference_package_io as module
from biocompiler.core_client import CoreProtocolError
from biocompiler.errors import SerializationError

class PackageSourceIOTests(unittest.TestCase):
    def root(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);(root/'manifest.json').write_bytes(b'{\r\n"test": 1\r}\n')
        (root/'source.txt').write_bytes(b'first')
        return root

    def test_separate_actual_reads_and_universal_newlines(self):
        root=self.root();reader=module.ReferenceReader(root)
        self.assertEqual(reader.read('manifest-first','manifest.json'),b'{\r\n"test": 1\r}\n')
        self.assertEqual(reader.read('retained-first','source.txt'),b'first')
        (root/'source.txt').write_bytes(b'second')
        self.assertEqual(reader.read('manifest-second','manifest.json'),b'{\n"test": 1\n}\n')
        self.assertEqual(reader.read('source-second','source.txt'),b'second')
        self.assertEqual(reader.read('review-second','source.txt'),b'second')
        with self.assertRaises(CoreProtocolError):reader.read('source-second','source.txt')

    def test_directory_and_read_are_deferred_and_original_error_cause_retained(self):
        error=FileNotFoundError('actual missing directory')
        with patch.object(module.reference_builds,'_directory',side_effect=error) as call:
            reader=module.ReferenceReader('missing');call.assert_not_called()
            with self.assertRaises(SerializationError) as raised:reader.read('manifest-first','manifest.json')
            self.assertIs(raised.exception.__cause__,error);call.assert_called_once_with('missing')
        root=self.root();(root/'manifest.json').write_bytes(b'\xff')
        with self.assertRaises(SerializationError) as raised:module.ReferenceReader(root).read('manifest-first','manifest.json')
        self.assertIsInstance(raised.exception.__cause__,UnicodeDecodeError)

    def test_no_parsers_or_adaptation_and_stop_on_read_failure(self):
        root=self.root();reader=module.ReferenceReader(root)
        with patch('biocompiler.registry.references.ReferenceManifest.from_json',side_effect=AssertionError('legacy parser')):
            reader.read('manifest-first','manifest.json');reader.read('manifest-second','manifest.json')
        with self.assertRaises(SerializationError):reader.read('source-second','../outside')
        with self.assertRaises(CoreProtocolError):module.ReferenceReader(root).read('manifest-second','manifest.json')

    def test_second_read_has_actual_bounded_read(self):
        root=self.root();reader=module.ReferenceReader(root);reader.read('manifest-first','manifest.json')
        reader.read('manifest-second','manifest.json')
        (root/'source.txt').write_bytes(b'long')
        with patch.object(module,'_MAX',3),self.assertRaises(CoreProtocolError):reader.read('source-second','source.txt')

if __name__=='__main__':unittest.main()

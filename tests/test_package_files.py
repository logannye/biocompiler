"""Filesystem-only transport tests; no executable or semantic checker runs."""
import hashlib
import os
from pathlib import Path
import sys
import threading
import unittest

from biocompiler import core_package_files as files


def descriptor(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


class PackageFilesTests(unittest.TestCase):
    def test_actual_readonly_input_private_output_and_full_bytes(self):
        data = b'PK\0\xff\r\n' * 100
        with files.PackageFiles(data) as owner:
            arguments, descriptors = owner.claim_launch()
            self.assertEqual(arguments[0], files.ARGUMENT)
            self.assertEqual(tuple(map(int, arguments[1:])), descriptors)
            self.assertEqual(owner.input_descriptor, descriptor(data))
            self.assertEqual(os.read(descriptors[0], len(data)), data)
            with self.assertRaises(OSError):
                os.write(descriptors[0], b'forged')
            os.write(descriptors[1], data)
            self.assertEqual(owner.read_output(descriptor(data)), data)
            with self.assertRaisesRegex(files.CoreProtocolError, 'one launched'):
                owner.read_output(descriptor(data))
        for value in descriptors:
            with self.assertRaises(OSError):
                os.fstat(value)

    def test_absent_input_and_single_launch(self):
        with files.PackageFiles(None) as owner:
            arguments, descriptors = owner.claim_launch()
            self.assertEqual(arguments[1], '-')
            self.assertEqual(len(descriptors), 1)
            self.assertIsNone(owner.input_descriptor)
            with self.assertRaisesRegex(files.CoreProtocolError, 'one launch'):
                owner.claim_launch()

    def test_prelaunch_write_is_rejected(self):
        with files.PackageFiles(None) as owner:
            os.write(owner._output.fileno(), b'prefix')
            with self.assertRaisesRegex(files.CoreProtocolError, 'empty output'):
                owner.claim_launch()

    def test_wrong_descriptors_consume_the_lease(self):
        for wrong in ({'bytes': 3, 'sha256': '0'*64}, {'bytes': 2, 'sha256': hashlib.sha256(b'abc').hexdigest()},
                      {'bytes': True, 'sha256': '0'*64}, {'bytes': 3, 'sha256': 'A'*64}):
            with files.PackageFiles(None) as owner:
                _, descriptors = owner.claim_launch()
                os.write(descriptors[0], b'abc')
                with self.assertRaises(files.CoreProtocolError):
                    owner.read_output(wrong)
                with self.assertRaisesRegex(files.CoreProtocolError, 'one launched'):
                    owner.read_output(descriptor(b'abc'))

    def test_trailing_bytes_and_reduced_limits(self):
        with files.PackageFiles(None, max_archive_bytes=3) as owner:
            _, descriptors = owner.claim_launch()
            os.write(descriptors[0], b'abcd')
            with self.assertRaisesRegex(files.CoreProtocolError, 'byte bounds'):
                owner.monitor()
        for value in (b'', b'abcd', bytearray(b'a')):
            with self.assertRaises(files.CoreProtocolError):
                files.PackageFiles(value, max_archive_bytes=3)
        with files.PackageFiles(None) as owner:
            _, descriptors = owner.claim_launch()
            os.write(descriptors[0], b'abc-extra')
            with self.assertRaisesRegex(files.CoreProtocolError, 'size differs'):
                owner.read_output(descriptor(b'abc'))

    def test_thread_owner_invalidation_and_close(self):
        with files.PackageFiles(None) as owner:
            errors = []
            def foreign():
                try:
                    owner.claim_launch()
                except files.CoreProtocolError as error:
                    errors.append(error)
            thread = threading.Thread(target=foreign)
            thread.start()
            thread.join()
            self.assertEqual(len(errors), 1)
            owner.claim_launch()
            owner.invalidate()
            with self.assertRaisesRegex(files.CoreProtocolError, 'invalidated'):
                owner.read_output(descriptor(b'abc'))
        owner.close()
        with self.assertRaisesRegex(files.CoreProtocolError, 'closed'):
            owner.monitor()


if __name__ == '__main__':
    unittest.main()

"""RC4 atomic structural publication; peer tests grant no native acceptance."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from biocompiler.core_client import CoreCancelled, CoreProtocolError, CoreTransportError, encode_json
from biocompiler.policy import controlled_material as sdk
from tests.test_core_policy_controlled_material import Peer, original, literal, api


class ControlledPublicationTests(unittest.TestCase):
    def publish(self,path,**kwargs):
        return sdk.publish_material(original(),candidate=literal()['literal_candidate'],
            client=api.PolicyControlledMaterialClient(Peer()),output=path,**kwargs)

    def test_fresh_native_pair_and_deterministic_atomic_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            one,two=(Path(directory)/name for name in ('one.zip','two.zip'))
            first=self.publish(one);self.publish(two)
            self.assertEqual(one.read_bytes(),two.read_bytes())
            with zipfile.ZipFile(one) as archive:
                self.assertEqual(archive.namelist(),['program.fasta','manifest.json'])
                self.assertEqual(archive.read('program.fasta'),literal()['expected']['fasta'].encode())
                self.assertEqual(archive.read('manifest.json'),encode_json(first.artifact['manifest']))
            self.assertFalse(list(Path(directory).glob('.controlled-material-*')))

    def test_original_alias_and_implicit_replacement_rejected_before_native(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'original.zip';source.write_bytes(b'original')
            hard=Path(directory)/'hard.zip';os.link(source,hard)
            symbolic=Path(directory)/'symbolic.zip';symbolic.symlink_to(source)
            with patch.object(api.PolicyControlledMaterialClient,'publish_material',side_effect=AssertionError('no native call')):
                with self.assertRaises(FileExistsError):self.publish(source)
                for destination in (source,hard,symbolic):
                    with self.subTest(destination=destination),self.assertRaises(ValueError):
                        self.publish(destination,input_paths=[source],replace=True)
            self.assertEqual(source.read_bytes(),b'original')

    def test_native_failure_incomplete_material_and_io_failure_preserve_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'result.zip';path.write_bytes(b'original')
            targets=['biocompiler.policy.controlled_material.zipfile.ZipFile.writestr',
                     'biocompiler.policy.controlled_material.os.fsync','biocompiler.policy.controlled_material.os.replace']
            for target in targets:
                with self.subTest(target=target),patch(target,side_effect=OSError('injected IO failure')),self.assertRaises(OSError):
                    self.publish(path,replace=True)
                self.assertEqual(path.read_bytes(),b'original');self.assertFalse(list(Path(directory).glob('.controlled-material-*')))
            with patch.object(api.PolicyControlledMaterialClient,'publish_material',side_effect=CoreTransportError('native failure')),self.assertRaises(CoreTransportError):
                self.publish(path,replace=True)
            self.assertEqual(path.read_bytes(),b'original')
            with patch.object(api.PolicyControlledMaterialClient,'publish_material',return_value=api.PolicyControlledMaterialClient(Peer()).check_material(original(),literal()['literal_candidate'])),self.assertRaises(CoreProtocolError):
                self.publish(path,replace=True)
            self.assertEqual(path.read_bytes(),b'original')

    def test_cancellation_after_staged_readback_preserves_output_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'result.zip';path.write_bytes(b'original');done=False
            verify=sdk._verify_staged
            def readback(*args):
                nonlocal done
                verify(*args);done=True
            with patch.object(sdk,'_verify_staged',side_effect=readback),self.assertRaises(CoreCancelled):
                self.publish(path,replace=True,cancelled=lambda:done)
            self.assertTrue(done);self.assertEqual(path.read_bytes(),b'original')
            self.assertFalse(list(Path(directory).glob('.controlled-material-*')))

    def test_staged_corruption_and_exclusive_destination_race_do_not_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'result.zip';path.write_bytes(b'original');fsync=os.fsync
            def corrupt(fd):
                fsync(fd);os.lseek(fd,30+len('program.fasta'),os.SEEK_SET);os.write(fd,b'!')
            with patch.object(sdk.os,'fsync',side_effect=corrupt),self.assertRaises(CoreProtocolError):self.publish(path,replace=True)
            self.assertEqual(path.read_bytes(),b'original')
            path.unlink();link=os.link
            def race(source,destination):
                Path(destination).write_bytes(b'other writer');return link(source,destination)
            with patch.object(sdk.os,'link',side_effect=race),self.assertRaises(FileExistsError):self.publish(path)
            self.assertEqual(path.read_bytes(),b'other writer');self.assertFalse(list(Path(directory).glob('.controlled-material-*')))

    def test_precancelled_publication_never_calls_native(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(api.PolicyControlledMaterialClient,'publish_material',side_effect=AssertionError('no native call')):
            with self.assertRaises(CoreCancelled):self.publish(Path(directory)/'result.zip',cancelled=lambda:True)


if __name__=='__main__':unittest.main()

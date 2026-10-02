"""The complete previous CLI AST survives exactly three additive routing nodes."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import synthetic_selection_cli_source_lineage as c
from tools import workflow_source_lineage as previous
from tools.realization_source_lineage import verify_captured_source


class SyntheticSelectionCliSourceLineageTests(unittest.TestCase):
    def test_exact_whole_parent_and_current_bytes_contiguous_original_chain(self):
        entry=c.load_witness(); old=previous.load_witness()[c.CLI]
        self.assertEqual(entry['historical_source'],old['routed_source'])
        self.assertEqual(c.sha(previous.WITNESS.read_bytes()),previous.WITNESS_SHA256)
        current=(c.ROOT/c.CLI).read_bytes()
        self.assertEqual(current,entry['routed_source'].encode())
        latest=c.verify_source(c.ROOT,c.HISTORICAL_SHA256)
        chain=verify_captured_source(c.ROOT,{'path':c.CLI,'sha256':old['historical_sha256']})
        self.assertEqual(chain['lineage'][1],latest)
        self.assertEqual(chain['lineage'][0],previous.verify_extension(old,entry['historical_source'].encode(),old['historical_sha256']))
        self.assertEqual(chain['current_sha256'],c.sha(current))
        self.assertEqual(chain['lineage'][0]['current_sha256'],chain['lineage'][1]['historical_sha256'])

    def test_rehashed_helper_branch_registration_or_original_semantics_changes_fail(self):
        entry=c.load_witness();raw=entry['routed_source'].encode()
        substitutions=(
            (c.HELPER.encode(),c.HELPER.replace('argparse.SUPPRESS','"visible flag"',1).encode()),
            (b'"core_executable", "core_sha256", "core_timeout"',b'"core_executable"'),
            (b'return selection_command(args, bounded_text=_bounded_text, publish_report=_publish_report)',b'return selection_command(args, bounded_text=None, publish_report=_publish_report)'),
            (b'    _synthetic_producer_core_arguments(selection)\n',b'    _synthetic_producer_core_arguments(replay)\n'),
            (b'    _synthetic_producer_core_arguments(selection)\n',b'    _synthetic_producer_core_arguments(selection)\n    _synthetic_producer_core_arguments(selection)\n'),
            (b'Atomic selection report destination',b'Changed original report destination'),
        )
        for before,after in substitutions:
            changed=raw.replace(before,after,1);self.assertNotEqual(changed,raw)
            forged=deepcopy(entry);forged.update(routed_source=changed.decode(),routed_sha256=c.sha(changed))
            with self.subTest(before=before),self.assertRaises(ValueError):
                c.verify_extension(forged,changed,c.HISTORICAL_SHA256)
        changed=raw+b'\nimport os\n';forged=deepcopy(entry)
        forged.update(routed_source=changed.decode(),routed_sha256=c.sha(changed))
        with self.assertRaisesRegex(ValueError,'default implementation AST differs'):
            c.verify_extension(forged,changed,c.HISTORICAL_SHA256)

    def test_wrong_parent_current_unknown_history_and_witness_fail_closed(self):
        entry=c.load_witness();raw=entry['routed_source'].encode()
        with self.assertRaisesRegex(ValueError,'Current selection CLI route bytes differ'):
            c.verify_extension(entry,raw+b'\n',c.HISTORICAL_SHA256)
        forged=deepcopy(entry);forged['historical_source']+='\n'
        with self.assertRaisesRegex(ValueError,'Historical selection CLI bytes differ'):
            c.verify_extension(forged,raw,c.HISTORICAL_SHA256)
        with self.assertRaisesRegex(ValueError,'Unreviewed historical'):
            c.verify_source(c.ROOT,'0'*64)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'witness.json';path.write_bytes(c.WITNESS.read_bytes()+b' ')
            with patch.object(c,'WITNESS',path),self.assertRaisesRegex(ValueError,'witness bytes differ'):
                c.load_witness()
            with self.assertRaisesRegex(ValueError,'Missing or linked'):
                c.verify_source(Path(directory),c.HISTORICAL_SHA256)

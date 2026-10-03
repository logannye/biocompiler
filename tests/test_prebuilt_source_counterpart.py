"""Finite installed-path source restoration; no old corpus or producer is edited."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

DRAFT=Path(__file__).resolve().parents[1]
SOURCE=DRAFT if (DRAFT/'core/dune-project').is_file() else DRAFT.parents[2]
BASE=DRAFT/'tests/conformance/prebuilt-source-v1'
spec=importlib.util.spec_from_file_location('prebuilt_draft_lineage',DRAFT/'tools/manager_registration_source_lineage.py')
lineage=importlib.util.module_from_spec(spec);spec.loader.exec_module(lineage)


class InstalledHelperCounterpartTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        for origin,name in ((DRAFT,lineage.INSTALLED_TOOL_WITNESS),(SOURCE,lineage.TOOL_WITNESS),
                (SOURCE,'tests/conformance/pipeline-fixed-build-semantics-v1.json')):
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((origin/name).read_bytes())
        self.enterContext(patch.object(lineage,'ROOT',self.root))
        self.current=(DRAFT/lineage.TOOL_PATH).read_bytes()

    def test_actual_complete_chain_retains_both_raw_source_authorities(self):
        old=lineage.restore_installed_tool(self.current)
        self.assertEqual(old,Path(str(BASE/lineage.TOOL_PATH)+'.source').read_bytes())
        proof=lineage.verify_tool_source(self.current)
        self.assertEqual(proof['current_sha256'],lineage.sha(self.current))
        self.assertEqual(proof['historical_sha256'],lineage.TOOL_HISTORICAL)
        self.assertEqual(proof['installed_layout'],{'previous_sha256':lineage.sha(old),
            'current_sha256':lineage.sha(self.current),'witness_sha256':lineage.INSTALLED_TOOL_SHA256})
        restored=old.replace(lineage.TOOL_LOADER.encode(),b'',1).replace(lineage.TOOL_CHECK.encode(),b'',1).replace(lineage.TOOL_NEW_LINE.encode(),lineage.TOOL_OLD_LINE.encode(),1)
        self.assertEqual(restored,lineage.original_tool_source())

    def test_stale_unlisted_or_omitted_path_edits_reject(self):
        for raw in (Path(str(BASE/lineage.TOOL_PATH)+'.source').read_bytes(),self.current+b'\n# extra\n',
                self.current.replace(lineage.INSTALLED_TOOL_AFTER.encode(),lineage.INSTALLED_TOOL_BEFORE.encode(),1)):
            with self.subTest(pin=lineage.sha(raw)),self.assertRaisesRegex(ValueError,'whole source'):
                lineage.restore_installed_tool(raw)

    def test_rehashed_extra_semantic_change_still_fails_exact_recipe(self):
        path=self.root/lineage.INSTALLED_TOOL_WITNESS;entry=json.loads(path.read_bytes())
        changed=self.current+b'\n# unlisted source extension\n';entry.update(current_source=changed.decode(),current_sha256=lineage.sha(changed))
        raw=(json.dumps(entry,sort_keys=True,separators=(',',':'))+'\n').encode();path.write_bytes(raw)
        with patch.object(lineage,'INSTALLED_TOOL_SHA256',lineage.sha(raw)),self.assertRaisesRegex(ValueError,'entire preceding'):
            lineage.restore_installed_tool(changed)

    def test_overlay_explicitly_copies_both_witnesses_and_old_assertions_remain(self):
        before=(BASE/'tools/pipeline_original_counterpart.py.source').read_text();after=(DRAFT/'tools/pipeline_original_counterpart.py').read_text()
        self.assertEqual(after.replace('lineage.TOOL_WITNESS, lineage.INSTALLED_TOOL_WITNESS,','lineage.TOOL_WITNESS,'),before)
        before=(BASE/'tests/test_manager_registration_source_lineage.py.source').read_text();after=(DRAFT/'tests/test_manager_registration_source_lineage.py').read_text()
        self.assertEqual(after.replace('        current=lineage.restore_installed_tool(current)\n','',1),before)
        self.assertIn("proof = verify_tool_extension(entry, previous, historical_sha256)",(DRAFT/'tools/manager_registration_source_lineage.py').read_text())


if __name__=='__main__':unittest.main()

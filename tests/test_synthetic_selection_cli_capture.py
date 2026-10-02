"""All72 complete default CLI observations, exact lineage and runtime mutations."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from tools import check_synthetic_selection_cli_corpus as c


class SyntheticSelectionCliCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original,cls.blobs=c.load_baseline()

    def fixture(self,version='3.14'):
        actual=deepcopy(self.original);blobs=dict(self.blobs)
        scope=actual['source_scope']=c.frozen.source_scope()
        current={row['path']:row['sha256'] for row in scope['actual_sources']}
        for row in actual['cases']:
            for item in row['import_audit']['modules'].values():item['sha256']=current[item['path']]
        raw=(c.ROOT/c.routes.CLI).read_bytes();old=actual['retained_source_bytes'][c.routes.CLI]
        del blobs[old['sha256']];store=c.frozen.f.Store()
        actual['retained_source_bytes'][c.routes.CLI]=store.retain(raw);blobs.update(store.blobs)
        old=next(row for row in self.original['cases'] if row['id']=='unknown-flag')
        row=next(row for row in actual['cases'] if row['id']==old['id'])
        expected=c.counterparts().expected(old,{'exit_code':old['exit_code'],
            **{field:c.frozen.f.restore(old[field],self.blobs) for field in ('stdout','stderr')}},version)
        if expected['stderr'] != c.frozen.f.restore(old['stderr'],self.blobs):
            del blobs[row['stderr']['sha256']];store=c.frozen.f.Store()
            row['stderr']=store.retain(expected['stderr']);blobs.update(store.blobs)
        self.rehash(actual)
        return actual,blobs

    def rehash(self,actual):
        actual['inventory_fingerprint']=c.digest({key:value for key,value in actual.items() if key!='inventory_fingerprint'})

    def test_complete_baseline_original_method_and_full_authority_error_census(self):
        self.assertEqual(self.original['inventory_fingerprint'],c.CORPUS_PIN)
        self.assertEqual(len(self.blobs),113)
        self.assertEqual(self.original['coverage'],{'actual_children':72,'original_occurrences':1,
            'entrypoints':{'console':68,'module':4},'exits':{'0':9,'1':2,'2':61}})
        originals=[row for row in self.original['cases'] if row['origin']=='original_occurrence']
        self.assertEqual(len(originals),1)
        self.assertEqual(originals[0]['id'],c.frozen.ORIGINAL_METHOD)
        self.assertTrue(originals[0]['original_full_observation_equal'])
        malformed=[row for row in self.original['cases'] if row['id'].startswith('malformed-')]
        self.assertEqual(len(malformed),42)
        for row in malformed:
            self.assertEqual(row['exit_code'],2)
            self.assertEqual(row['files_before'],row['files_after'])
            self.assertEqual(c.frozen.f.restore(row['stdout'],self.blobs),b'')
            self.assertEqual(c.frozen.f.restore(row['stderr'],self.blobs),
                ('biocompiler: '+row['lineage']['original_error_message']+'\n').encode())

    def test_both_exact_runtime_counterparts_keep_full_actual_source_and_bytes(self):
        for version in ('3.11.16','3.14.9'):
            actual,blobs=self.fixture(version);before=deepcopy(actual)
            receipt=c.verify_recapture(actual,blobs,python_version=version)
            self.assertEqual(receipt['status'],'complete_original_selection_cli_recapture_equal')
            self.assertEqual(receipt['projected_inventory_fingerprint'],c.CORPUS_PIN)
            self.assertEqual(receipt['actual_capture'],before);self.assertEqual(actual,before)
            self.assertEqual(receipt['content_documents'],len(blobs))
            self.assertEqual(receipt['actual_retained_route_source'],(c.ROOT/c.routes.CLI).read_text())
            self.assertEqual(len(receipt['runtime_counterpart']['changes']),int(version.startswith('3.11.')))

    def test_rehashed_observation_scope_imports_case_and_runtime_mutations_fail(self):
        actual,blobs=self.fixture('3.11')
        for mutate in (
            lambda value:value['cases'].pop(),lambda value:value['cases'].append(deepcopy(value['cases'][0])),
            lambda value:value['cases'][0].update(exit_code=9),lambda value:value['cases'][0].update(files_after={}),
            lambda value:value['cases'][0]['import_audit'].update(guard_active=False),
            lambda value:value['source_scope']['denied_modules'].clear(),
            lambda value:value['source_scope']['actual_sources'][0].update(sha256='0'*64),
            lambda value:value['capture_environment'].update(hash_seed='9'),
        ):
            changed=deepcopy(actual);mutate(changed);self.rehash(changed)
            with self.assertRaises(AssertionError):c.verify_recapture(changed,blobs,python_version='3.11')
        for version in ('3.14','3.12','3.13','4.0'):
            with self.assertRaises(AssertionError):c.verify_recapture(actual,blobs,python_version=version)
        for identifier in ('unknown-flag',self.original['cases'][0]['id']):
            changed=deepcopy(actual);content=dict(blobs);row=next(row for row in changed['cases'] if row['id']==identifier)
            before=row['stderr'];raw=c.frozen.f.restore(before,content);store=c.frozen.f.Store()
            row['stderr']=store.retain(raw+b' ');content.update(store.blobs)
            if identifier=='unknown-flag':del content[before['sha256']]
            self.rehash(changed)
            with self.assertRaises(AssertionError):c.verify_recapture(changed,content,python_version='3.11')
        with patch.object(c,'COUNTERPART_SHA256','0'*64),self.assertRaisesRegex(AssertionError,'counterpart bytes changed'):
            c.verify_recapture(actual,blobs,python_version='3.11')

    def test_additive_sources_require_individual_pins_and_cannot_enter_children(self):
        actual,blobs=self.fixture('3.11')
        receipt=c.verify_recapture(actual,blobs,python_version='3.11')
        additions=receipt['reviewed_unused_source_additions']
        self.assertTrue(additions)
        before=c.inventory(self.original['source_scope']['actual_sources'])
        current=c.inventory(actual['source_scope']['actual_sources'])
        self.assertEqual({row['path'] for row in additions},set(current)-set(before))
        for row in additions:
            self.assertEqual(c.sha(row['source'].encode()),row['sha256'])
            with patch.dict(c.REVIEWED_ADDITIONS,{row['path']:'0'*64}):
                with self.assertRaisesRegex(AssertionError,'Unreviewed selection CLI source addition'):
                    c.verify_recapture(actual,blobs,python_version='3.11')
            changed=deepcopy(actual)
            changed['cases'][0]['import_audit']['modules'][row['path'][4:-3].replace('/','.')]=dict(
                path=row['path'],sha256=row['sha256'])
            self.rehash(changed)
            with self.assertRaisesRegex(AssertionError,'imported unpinned source'):
                c.verify_recapture(changed,blobs,python_version='3.11')
        unused=receipt['reviewed_unused_source_change']
        self.assertEqual(c.sha(unused['historical_source'].encode()),before[unused['path']])
        self.assertEqual(c.sha(unused['current_source'].encode()),current[unused['path']])
        with patch.object(c,'UNUSED_SOURCE_SHA256','0'*64):
            with self.assertRaisesRegex(AssertionError,'Unused transport lineage bytes changed'):
                c.verify_recapture(actual,blobs,python_version='3.11')
        with patch.dict(c.REVIEWED_ADDITIONS,{unused['path']:'0'*64}):
            with self.assertRaisesRegex(AssertionError,'Unused transport source lineage differs'):
                c.verify_recapture(actual,blobs,python_version='3.11')
        with patch.dict(c.REVIEWED_ADDITIONS,{},clear=True):
            with self.assertRaisesRegex(AssertionError,'Unreviewed selection CLI source addition'):
                c.verify_recapture(actual,blobs,python_version='3.11')
        for mode in ('extra','deleted'):
            changed=deepcopy(actual);scope=changed['source_scope'];rows=scope['actual_sources']
            if mode=='extra':rows.append({'path':'src/biocompiler/unreviewed.py','sha256':'f'*64})
            else:rows[:]=[row for row in rows if row['path']!=c.routes.CLI]
            rows.sort(key=lambda row:row['path']);scope['source_inventory_sha256']=c.digest(rows)
            self.rehash(changed)
            with patch.object(c.frozen,'source_scope',return_value=scope),self.assertRaises(AssertionError):
                c.verify_recapture(changed,blobs,python_version='3.11')

    def test_independent_complete_seventy_two_child_recapture_is_byte_exact(self):
        actual,blobs=c.frozen.capture()
        receipt=c.verify_recapture(actual,blobs)
        self.assertEqual(receipt['status'],'complete_original_selection_cli_recapture_equal')
        self.assertEqual(receipt['coverage']['actual_children'],72)
        self.assertEqual(receipt['projected_inventory_fingerprint'],c.CORPUS_PIN)
        self.assertEqual(receipt['actual_capture'],actual)

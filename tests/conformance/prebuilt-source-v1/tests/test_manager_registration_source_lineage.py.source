from copy import deepcopy
import ast
import json
from pathlib import Path
import tempfile
import unittest

from tools import manager_registration_source_lineage as lineage
from tools import pipeline_original_counterpart as original


class ManagerRegistrationLineageTests(unittest.TestCase):
    def test_exact_prefix_restores_complete_original_bytes_and_ast(self):
        entry = lineage.load_witness()
        old, new = entry['historical_source'].encode(), entry['routed_source'].encode()
        self.assertEqual(new.replace(lineage.PREFIX.encode(), b'', 1), old)
        self.assertEqual(len(lineage.PREFIX.splitlines()), 5)
        lineage.verify_extension(entry, new, lineage.HISTORICAL[lineage.PATH])
        for change in (new.replace(b'issubclass(type(self), native_type)', b'true', 1),
            new.replace(b'            return native_type._native_register', b'            native_type._native_register', 1),
            new + b'\n# unrelated edit\n', new.replace(b'Previous', b'Altered', 1)):
            if change == new:
                continue
            with self.subTest(change=change[:20]), self.assertRaises(ValueError):
                lineage.verify_extension(entry, change, lineage.HISTORICAL[lineage.PATH])
        forged = deepcopy(entry)
        forged['routed_source'] += '\n# rehashed arbitrary addition\n'
        forged['routed_sha256'] = lineage.sha(forged['routed_source'].encode())
        with self.assertRaisesRegex(ValueError, 'entire original'):
            lineage.verify_extension(forged, forged['routed_source'].encode(), lineage.HISTORICAL[lineage.PATH])

    def test_real_canonical_child_executes_complete_original_and_rejects_forged_origins(self):
        result = original.run()
        value = original.validate(result)
        self.assertEqual(len(value['capture']['cases']), 47)
        self.assertEqual(value['capture']['source_files'][lineage.PATH], lineage.HISTORICAL[lineage.PATH])
        self.assertEqual(value['proof']['complete_raw_current'], value['capture'])
        self.assertEqual(value['proof']['independent_raw_current'], value['capture'])
        module = result['modules']['biocompiler.compiler.pipeline']
        self.assertEqual(module['namespace'], 'biocompiler.compiler.pipeline')
        self.assertEqual(module['sha256'], lineage.HISTORICAL[lineage.PATH])
        for kind in ('namespace', 'path', 'substitution', 'missing', 'extra'):
            changed = deepcopy(result)
            if kind == 'namespace': changed['modules']['biocompiler.compiler.pipeline']['namespace'] = 'copy.pipeline'
            if kind == 'path': changed['modules']['biocompiler.compiler.pipeline']['path'] += '.forged'
            if kind == 'substitution':
                row = next(item for item in changed['manifest']['sources'] if item['logical'] == lineage.PATH)
                row['sha256'] = row['origin_sha256']
            if kind == 'missing': changed['manifest']['sources'].pop()
            if kind == 'extra': changed['modules']['biocompiler.evil'] = dict(module)
            with self.subTest(kind=kind), self.assertRaises(AssertionError): original.validate(changed)

    def test_complete_bridge_module_census_preserves_all_original_classes_and_ids(self):
        import importlib
        from tools.test_shards import flatten
        before=[];after=[]
        for name in original.TEST_MODULES:
            module=importlib.import_module('tests.'+name)
            classes=[value for value in vars(module).values() if isinstance(value,type)
                and issubclass(value,unittest.TestCase) and value.__module__==module.__name__]
            raw=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in classes)
            mapped=original.original_test_suite(unittest.defaultTestLoader,raw,None,module.__name__)
            key=lambda case:(case.id(),type(case).__module__+'.'+type(case).__qualname__)
            expected=[key(case) for case in flatten(raw)]
            actual=[key(case) for case in flatten(mapped)]
            self.assertTrue(all(left is right for left,right in zip(flatten(raw),flatten(mapped))))
            with self.subTest(module=name):self.assertEqual(actual,expected)
            before.extend(expected);after.extend(actual)
        self.assertEqual(after,before)
        self.assertEqual(len(after),len({identity for identity,_ in after}))
        self.assertEqual(len({classname for _,classname in after}),len(original.TEST_MODULES))

    def test_exact_helper_archive_and_every_substitution_are_required(self):
        entry=lineage.tool_witness()
        current=(lineage.ROOT/lineage.TOOL_PATH).read_bytes()
        lineage.verify_tool_extension(entry,current,lineage.TOOL_HISTORICAL)
        restored=current.replace(lineage.TOOL_LOADER.encode(),b'',1).replace(lineage.TOOL_CHECK.encode(),b'',1)            .replace(lineage.TOOL_NEW_LINE.encode(),lineage.TOOL_OLD_LINE.encode(),1)
        self.assertEqual(restored,lineage.original_tool_source())
        for kind in ('stale','extra','omitted-check'):
            changed=deepcopy(entry)
            raw=restored if kind=='stale' else current+b'\n# unlisted helper change\n' if kind=='extra' else current.replace(lineage.TOOL_CHECK.encode(),b'',1)
            changed['current_source']=raw.decode();changed['current_sha256']=lineage.sha(raw)
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'entire original'):
                lineage.verify_tool_extension(changed,raw,lineage.TOOL_HISTORICAL)
        receipt=original.run('fixed-provider-original')
        self.assertEqual([row['logical'] for row in receipt['manifest']['sources'] if row['substituted']],
            [lineage.PATH,lineage.TOOL_PATH])
        for kind in ('stale','unlisted','proof'):
            changed=deepcopy(receipt)
            row=next(item for item in changed['manifest']['sources'] if item['logical']==lineage.TOOL_PATH)
            if kind=='stale':row['sha256']=row['origin_sha256'];row['substituted']=False
            if kind=='unlisted':row['logical']='tools/unlisted.py'
            if kind=='proof':changed['manifest']['tool_route']=None
            with self.subTest(kind=kind),self.assertRaises(AssertionError):original.validate(changed)

    def test_test_bridge_preserves_every_original_test_id_and_class(self):
        from tools import pipeline_original_counterpart as bridge
        from unittest.mock import patch
        import tests.test_pipeline_deferred_runtime as module
        expected=unittest.defaultTestLoader.loadTestsFromTestCase(module.PipelineDeferredRuntimeTests)
        ids=[case.id() for case in expected]
        transformed=bridge.original_test_suite(unittest.defaultTestLoader,expected,None,'test_pipeline_deferred_runtime')
        self.assertEqual([case.id() for case in transformed],ids)
        self.assertEqual([(type(case).__module__,type(case).__qualname__) for case in transformed],
            [(type(case).__module__,type(case).__qualname__) for case in expected])
        classname=module.PipelineDeferredRuntimeTests.__module__+'.'+module.PipelineDeferredRuntimeTests.__qualname__
        value={'test_ids':ids,'tests':len(ids),'outcomes':[{'id':name,'class':classname,'status':'success','detail':None} for name in ids]}
        bridge.validate_test_outcomes(value,ids,classname)
        for kind in ('missing','duplicate','class','count'):
            changed=deepcopy(value)
            if kind=='missing': changed['outcomes'].pop()
            if kind=='duplicate': changed['outcomes'][1]=deepcopy(changed['outcomes'][0])
            if kind=='class': changed['outcomes'][0]['class']='another.Class'
            if kind=='count': changed['tests']-=1
            with self.subTest(kind=kind),self.assertRaises(AssertionError): bridge.validate_test_outcomes(changed,ids,classname)
        changed=deepcopy(value);changed['outcomes'][0].update(status='failure',detail='actual child failure')
        with patch.object(bridge,'run',return_value={'value':changed}):
            suite=bridge.original_test_suite(unittest.defaultTestLoader,expected,None,'test_pipeline_deferred_runtime')
            result=unittest.TestResult();suite.run(result)
        self.assertEqual(result.testsRun,len(ids));self.assertEqual(len(result.failures),1)
        self.assertIn('actual child failure',result.failures[0][1])
        for status,field in (('error','errors'),('expected-failure','expectedFailures'),
                ('unexpected-success','unexpectedSuccesses'),('skipped','skipped')):
            changed=deepcopy(value);changed['outcomes'][0].update(status=status,detail='actual child '+status)
            with patch.object(bridge,'run',return_value={'value':changed}):
                suite=bridge.original_test_suite(unittest.defaultTestLoader,expected,None,'test_pipeline_deferred_runtime')
                result=unittest.TestResult();suite.run(result)
            with self.subTest(status=status):
                self.assertEqual(result.testsRun,len(ids));self.assertEqual(len(getattr(result,field)),1)
                self.assertEqual(len(result.failures),0)


if __name__ == '__main__':
    unittest.main()

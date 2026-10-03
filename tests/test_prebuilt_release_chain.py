"""Whole release plans over inert bytes; no wheel/archive build or installation."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
with patch.object(sys,'path',[str(ROOT/'tools'),str(ROOT/'tests'),*sys.path]):
    build=importlib.import_module('build_prebuilt_core')
    verify=importlib.import_module('check_prebuilt_core_release')
    materials=importlib.import_module('prebuilt_core_materials')
    pipeline=importlib.import_module('prebuilt_release_pipeline')
    sources=importlib.import_module('prebuilt_sources')
    fixtures=importlib.import_module('test_prebuilt_core_materials')
    policy=importlib.import_module('test_prebuilt_core_release')
    sdk_fixtures=importlib.import_module('test_prebuilt_sdk_matrix')
    importlib.import_module('check_realization_binaries')


class WholeReleaseTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.MaterialsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.temp=self.enterContext(tempfile.TemporaryDirectory());self.root=Path(self.temp).resolve()
        self.native=self.root/'native';self.native.mkdir()
        raw=bytearray(64);raw[:6]=b'\x7fELF\x02\x01';raw[16:18]=(3).to_bytes(2,'little');raw[18:20]=(62).to_bytes(2,'little')
        binaries={}
        for name in build.ROLES:
            value=bytes(raw)+name.encode();(self.native/name).write_bytes(value);binaries[name]=materials.digest(value)
        self.expected={'source_revision':'1'*40,'tested_revision':'2'*40,'run_id':'123','native_platform':'linux-x86_64'}
        (self.native/'binaries.json').write_text(json.dumps({'revision':'2'*40,'system':'Linux','machine':'x86_64','sha256':{key:row['sha256'] for key,row in binaries.items()}},sort_keys=True,indent=2)+'\n')
        for name in build.EVIDENCE:(self.native/name).write_bytes(b'actual synthetic dependency lock\n' if name=='dependencies.opam.locked' else b'evidence\n')
        self.fixture.expected['binaries']=binaries;self.fixture.document['binaries']=deepcopy(binaries)
        self.companion={'schema_version':'biocompiler.core_material_companion.v1','filename':'biocompiler-core-materials-linux-x86_64.zip',
            'sha256':'a'*64,'size':123,'materials_sha256':build.sha(build.canonical(self.fixture.document)),
            'format':'zip-stored-1980-regular0644-v1','entries':len(self.fixture.document['files'])}
        def audit(tool,path,target):return {'argv':[str(tool),'--dynamic','--program-headers','--version-info','--notes','--wide',str(path)],
            'tool_sha256':'b'*64,'stdout':policy.ELF,'returncode':0,'policy':build.elf_policy(policy.ELF)}
        with patch.object(build,'audit',side_effect=audit):
            self.files,self.receipt=build.plan(self.native,target='linux-x86_64',source_revision='1'*40,tested_revision='2'*40,run_id='123',
                audit_tool=Path('/usr/bin/readelf'),material_root=self.fixture.root,material_document=self.fixture.document,
                material_authority=self.fixture.expected,material_sha256=self.companion['materials_sha256'],companion=self.companion)

    def verify(self,files=None,receipt=None,authority=None):
        return verify.validate_native(build.wheel_entries(self.files if files is None else files,'linux-x86_64'),
            expected=self.expected,material_authority=self.fixture.expected if authority is None else authority,
            material_sha256=self.companion['materials_sha256'],packaging=self.receipt if receipt is None else receipt)

    def rehash(self,files):
        manifest=json.loads(files['distribution.json'])
        manifest['files']={name:materials.digest(raw) for name,raw in files.items() if name!='distribution.json'}
        files['distribution.json']=build.canonical(manifest)
        receipt=deepcopy(self.receipt);receipt.update(distribution=manifest,distribution_sha256=build.sha(files['distribution.json']))
        return receipt

    def test_whole_native_entry_plan_contains_exact_notices_sources_and_link_audit(self):
        with patch.object(build.subprocess,'run',side_effect=AssertionError('no native execution')):
            result=self.verify()
        self.assertEqual(result['materials'],self.fixture.document)
        self.assertEqual(set(self.files),build.FILES|{'distribution.json'})
        self.assertGreater(len(result['notices']['entries']),5)
        self.assertEqual(materials.companion_entries(result['materials']),{name:{key:row[key] for key in ('sha256','size')} for name,row in self.fixture.document['files'].items()})

    def test_rehashed_dynamic_linkage_or_wrong_final_binary_does_not_pass(self):
        files=dict(self.files);raw=json.loads(files['linkage-receipt.json'])
        raw['audits']['biocompiler-core']['stdout']=policy.ELF.replace('libm.so.6','libgmp.so.10')
        files['linkage-receipt.json']=build.canonical(raw);receipt=self.rehash(files);receipt['audits']=raw['audits']
        with self.assertRaisesRegex(ValueError,'unbundled'):self.verify(files,receipt)
        files=dict(self.files);files['bin/biocompiler-core']+=b'changed';receipt=self.rehash(files)
        with self.assertRaisesRegex(ValueError,'Native manifest differs'):self.verify(files,receipt)

    def test_rehashed_stale_source_and_material_index_are_rejected(self):
        files=dict(self.files);raw=json.loads(files['distribution.json']);raw['run_id']='124';files['distribution.json']=build.canonical(raw)
        with self.assertRaisesRegex(ValueError,'external CI'):self.verify(files)
        files=dict(self.files);raw=json.loads(files['materials.json']);raw['components']['gmp']['version']='99.0'
        files['materials.json']=build.canonical(raw);receipt=self.rehash(files)
        with self.assertRaisesRegex(ValueError,'independently supplied'):self.verify(files,receipt)

    def test_companion_binding_and_wheel_modes_cannot_be_detached(self):
        files=dict(self.files);raw=json.loads(files['materials-companion.json']);raw['materials_sha256']='0'*64
        files['materials-companion.json']=build.canonical(raw);receipt=self.rehash(files);receipt['companion']=raw
        with self.assertRaisesRegex(ValueError,'Companion binding'):self.verify(files,receipt)
        entries=build.wheel_entries(self.files,'linux-x86_64');key='biocompiler_core/bin/biocompiler-core';entries[key]=(entries[key][0],0o644)
        with self.assertRaisesRegex(ValueError,'modes'):
            verify.validate_native(entries,expected=self.expected,material_authority=self.fixture.expected,
                material_sha256=self.companion['materials_sha256'],packaging=self.receipt)

    def test_duplicate_control_keys_and_record_omission_reject(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):verify.document(b'{"x":1,"x":2}\n')
        entries=build.wheel_entries(self.files,'linux-x86_64');del entries['biocompiler_core/notices.json']
        with self.assertRaisesRegex(ValueError,'RECORD census'):verify.validate_record(entries)


class HostedPlanTests(unittest.TestCase):
    def test_static_recipe_is_baseline_pic_no_assembly_and_real_check(self):
        for target in build.TARGETS:
            plan=sources.build_plan(target,Path('/source/gmp'),Path('/prefix'),Path('/usr/bin/cc'),Path('/usr/bin/make'))
            self.assertIn('--disable-shared',plan['commands'][0]);self.assertIn('--disable-assembly',plan['commands'][0])
            self.assertEqual(plan['commands'][2],['/usr/bin/make','check']);self.assertIn('-fPIC',plan['environment']['CFLAGS'])
            self.assertNotIn('native',plan['environment']['CFLAGS'])

    def test_all_current_conformance_campaigns_are_preserved_and_use_owned_paths(self):
        source=ROOT/'tests/conformance/prebuilt-source-v1';text=(source/'.github/workflows/ci.yml.source').read_text();section=text.split('  realization-conformance:',1)[1].split('  realization-core-reproducibility:',1)[0]
        import re
        actual=re.findall(r'python "\$GITHUB_WORKSPACE/tools/([^/]+)\.py"',section)
        self.assertEqual(actual,[name for name,_ in pipeline.CAMPAIGNS])
        owned={'package_root':'/fresh/site/biocompiler_core','source_revision':'a'*40,'tested_revision':'b'*40,
            'native_platform':'linux-x86_64','files':{f'bin/biocompiler-{role}':{'path':f'/fresh/site/biocompiler_core/bin/biocompiler-{role}','sha256':role} for role in ('core','verify')}}
        rows=pipeline.campaign_plan(source,Path('/fresh/bin/python'),owned,Path('/evidence'))
        self.assertEqual(len(rows),17)
        for _,command in rows:
            self.assertIn('/fresh/site/biocompiler_core/bin/biocompiler-core',command)
            self.assertNotIn('artifacts/native',' '.join(command))

    def test_install_has_no_source_resolution_and_clears_loader_overrides(self):
        sdk=Path('/wheelhouse/biocompiler-'+build.VERSION+'-py3-none-any.whl')
        native=Path('/wheelhouse/biocompiler_core-'+build.VERSION+'-'+build.TARGETS['linux-x86_64'][2]+'.whl')
        plan=pipeline.install_plan(Path('/python'),Path('/fresh/bin/python'),sdk,native)
        self.assertIn('--no-index',plan);self.assertIn('--only-binary=:all:',plan);self.assertNotIn('.',plan)
        env=pipeline.clean_environment({'PYTHONPATH':'/source','LD_LIBRARY_PATH':'/gmp','DYLD_INSERT_LIBRARIES':'/foreign','PATH':'/bin'})
        self.assertNotIn('PYTHONPATH',env);self.assertNotIn('LD_LIBRARY_PATH',env);self.assertNotIn('DYLD_INSERT_LIBRARIES',env)
        with self.assertRaisesRegex(ValueError,'reviewed wheels'):pipeline.install_plan(Path('/python'),Path('/fresh/bin/python'),Path('/wheelhouse/source.tar.gz'),native)

    def test_locked_upstream_sources_have_complete_pinned_license_census(self):
        lock=json.loads(sources.LOCK.read_bytes())
        self.assertEqual(len(lock['sources']),7)
        self.assertEqual(sum(len(row['notices']) for row in lock['sources'].values()),27)
        for row in lock['sources'].values():
            self.assertTrue(row['url'].startswith('https://'))
            self.assertGreater(row['size'],0)
            self.assertEqual(len(row['sha256']),64)
            self.assertTrue(row['notices'])


if __name__=='__main__':unittest.main()

class ArchiveBoundaryTests(unittest.TestCase):
    @staticmethod
    def fixture():
        # One inert data member, assembled as ZIP record grammar only. This is
        # neither a wheel nor a package build and contains no executable bytes.
        import struct,zlib
        name=b'notice.txt';value=b'original notice\n';crc=zlib.crc32(value)
        local=struct.pack('<I5H3I2H',0x04034b50,20,0,0,0,33,crc,len(value),len(value),len(name),0)+name+value
        central=struct.pack('<I6H3I5H2I',0x02014b50,3*256+20,20,0,0,0,33,crc,len(value),len(value),len(name),0,0,0,0,0o100644<<16,0)+name
        end=struct.pack('<I4H2IH',0x06054b50,0,0,1,1,len(central),len(local),0)
        return local+central+end

    def members(self,raw):
        import io,zipfile
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            return verify.archive_members(archive,maximum_files=2,maximum_total=1024,maximum_file=1024,stored=True)

    def test_closed_inert_archive_local_central_end_census(self):
        self.assertEqual(set(self.members(self.fixture())),{'notice.txt'})

    def test_ignored_prefix_trailing_and_local_authority_mutants_fail(self):
        raw=self.fixture()
        for value in (b'prefix'+raw,raw+b'trailing',raw[:14]+b'\0\0\0\0'+raw[18:],raw[:10]+b'\x01\x00'+raw[12:]):
            with self.subTest(size=len(value)),self.assertRaises(ValueError):self.members(value)


class SdkBackendCanonicalizationTests(unittest.TestCase):
    """Inert ZIP grammar fixtures only: no SDK build, install or native process."""
    def setUp(self):
        fixture=sdk_fixtures.SdkWheelTests();fixture.setUp()
        self.entries=fixture.entries;self.sources=fixture.sources;self.release=fixture.release
        self.record='biocompiler-'+build.VERSION+'.dist-info/RECORD'
        raw,_=self.entries[self.record];self.entries[self.record]=(raw,0o664)

    @staticmethod
    def archive(entries, *, deflated=False):
        import struct,zlib
        local,central=bytearray(),bytearray()
        for name,(value,mode) in entries.items():
            name=name.encode();crc=zlib.crc32(value)
            if deflated:
                compressor=zlib.compressobj(wbits=-15);packed=compressor.compress(value)+compressor.flush()
            else:packed=value
            method=8 if deflated else 0;offset=len(local)
            local.extend(struct.pack('<I5H3I2H',0x04034b50,20,0,method,0,33,crc,len(packed),len(value),len(name),0)+name+packed)
            central.extend(struct.pack('<I6H3I5H2I',0x02014b50,3*256+20,20,0,method,0,33,crc,len(packed),len(value),len(name),0,0,0,0,(0o100000|mode)<<16,offset)+name)
        return bytes(local+central+struct.pack('<I4H2IH',0x06054b50,0,0,len(entries),len(entries),len(central),len(local),0))

    def canonical(self,raw):
        return pipeline.sdk_canonical_bytes(raw,source_files=self.sources,release=self.release)

    def test_pinned_backend_record_mode_changes_only_central_mode_bytes(self):
        import io,zipfile
        for deflated in (False,True):
            with self.subTest(deflated=deflated):
                raw=self.archive(self.entries,deflated=deflated)
                with zipfile.ZipFile(io.BytesIO(raw)) as archive,self.assertRaisesRegex(ValueError,'Invalid archive mode'):
                    verify.archive_members(archive,maximum_files=10000,maximum_total=1024*1024,maximum_file=1024*1024)
                final,receipt=self.canonical(raw)
                self.assertEqual(len(final),len(raw));self.assertEqual(len(receipt['changes']),1)
                change=receipt['changes'][0];offset=change['offset']
                self.assertEqual(change['member'],self.record)
                self.assertEqual(raw[:offset],final[:offset]);self.assertEqual(raw[offset+4:],final[offset+4:])
                self.assertEqual(receipt['backend']['sha256'],build.sha(raw))
                self.assertEqual(receipt['canonical']['sha256'],build.sha(final))
                with zipfile.ZipFile(io.BytesIO(final)) as archive:
                    rows=verify.archive_members(archive,maximum_files=10000,maximum_total=1024*1024,maximum_file=1024*1024)
                    self.assertEqual({name:archive.read(row) for name,row in rows.items()},
                        {name:value for name,(value,_) in self.entries.items()})
                    self.assertEqual(archive.read(self.record),self.entries[self.record][0])
                again,second=self.canonical(final)
                self.assertEqual(again,final);self.assertEqual(second['changes'],[])

    def test_other_modes_and_symlinks_are_not_canonicalized(self):
        for name,mode in ((self.record,0o666),(self.record,0o755),('biocompiler/py.typed',0o664),('biocompiler/py.typed',0o755)):
            changed=dict(self.entries);changed[name]=(changed[name][0],mode)
            with self.subTest(name=name,mode=mode),self.assertRaises(ValueError):self.canonical(self.archive(changed))
        import struct
        raw=self.archive(self.entries);start=raw.index(b'PK\x01\x02');changed=bytearray(raw)
        struct.pack_into('<I',changed,start+38,0o120644<<16)
        with self.assertRaisesRegex(ValueError,'nonregular'):self.canonical(bytes(changed))

    def test_bad_record_unknown_members_and_changed_source_or_pins_are_not_repaired(self):
        changed=dict(self.entries);changed['biocompiler/py.typed']=(b'changed',0o644)
        with self.assertRaisesRegex(ValueError,'RECORD byte identity'):self.canonical(self.archive(changed))
        for name,value,message in (('biocompiler/py.typed',b'changed','source/resource'),
            ('biocompiler-'+build.VERSION+'.dist-info/unknown',b'unreviewed','unreviewed distribution'),
            ('biocompiler/_core_release.json',build.canonical({**self.release,'run_id':'999'}),'release pins')):
            changed=dict(self.entries);changed[name]=(value,0o644);sdk_fixtures.record(changed)
            changed[self.record]=(changed[self.record][0],0o664)
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,message):self.canonical(self.archive(changed))

    def test_malformed_zip_metadata_and_unclaimed_bytes_remain_rejected(self):
        import struct
        raw=self.archive(self.entries)
        mutants=[b'prefix'+raw,raw+b'trailing',raw[:14]+b'\0\0\0\0'+raw[18:]]
        central=raw.index(b'PK\x01\x02')
        for offset,value in ((6,1),(central+8,1),(central+12,1)):
            changed=bytearray(raw);struct.pack_into('<H',changed,offset,value);mutants.append(bytes(changed))
        for changed in mutants:
            with self.subTest(size=len(changed)),self.assertRaises(ValueError):self.canonical(changed)
        changed=dict(self.entries);changed['biocompiler/py.typEd']=changed['biocompiler/py.typed']
        duplicate=self.archive(changed).replace(b'biocompiler/py.typEd',b'biocompiler/py.typed')
        with self.assertRaisesRegex(ValueError,'Repeated'):self.canonical(duplicate)

    def test_atomic_staging_preserves_original_on_failed_final_validation(self):
        raw=self.archive(self.entries)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/('biocompiler-'+build.VERSION+'-py3-none-any.whl');path.write_bytes(raw)
            with patch.object(verify,'read_wheel',side_effect=ValueError('final validation failed')):
                with self.assertRaisesRegex(ValueError,'final validation failed'):
                    pipeline.canonicalize_sdk(path,source_files=self.sources,release=self.release)
            self.assertEqual(path.read_bytes(),raw);self.assertEqual(list(path.parent.iterdir()),[path])
            receipt=pipeline.canonicalize_sdk(path,source_files=self.sources,release=self.release)
            verify.validate_sdk(verify.read_wheel(path),source_files=self.sources,release=self.release)
            self.assertEqual(build.sha(path.read_bytes()),receipt['canonical']['sha256'])

    def test_sdk_driver_records_canonicalization_after_backend_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output=root/'wheelhouse';events=[]
            def backend(*args,**kwargs):
                events.append('backend');return {'returncode':0}
            def canonicalize(*args,**kwargs):
                self.assertEqual(events,['backend']);events.append('canonicalize')
                self.assertEqual(args,(output/('biocompiler-'+build.VERSION+'-py3-none-any.whl'),))
                self.assertEqual(kwargs,{'source_files':self.sources,'release':self.release})
                return {'checked':True}
            argv=['prebuilt_release_pipeline.py','sdk','--checkout',str(root/'source'),'--manifests',str(root/'linux.json'),str(root/'macos.json'),
                '--staging',str(root/'stage'),'--output',str(output)]
            with patch.object(sys,'argv',argv),patch.object(pipeline,'sdk_stage',return_value=self.release),\
                patch.object(pipeline,'run',side_effect=backend),patch.object(verify,'source_package',return_value=self.sources),\
                patch.object(pipeline,'canonicalize_sdk',side_effect=canonicalize):
                pipeline.main()
            self.assertEqual(events,['backend','canonicalize'])
            self.assertEqual(json.loads((output/'build-sdk.json').read_bytes()),{'returncode':0,'sdk_canonicalization':{'checked':True}})

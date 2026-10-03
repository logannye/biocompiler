"""Original Python evidence only; no native compilation or execution."""
import hashlib,importlib.util,json,re,sys,unicodedata,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('package_capture',ROOT/'tools/capture_reference_package_domains.py')
authority=importlib.util.module_from_spec(spec);spec.loader.exec_module(authority)
class PackageAuthorityTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.current=authority.capture();cls.frozen={v:json.loads((ROOT/f'tests/conformance/reference-package-domains-{v}.json').read_bytes()) for v in ('311','314')}
 def test_complete_actual_original_capture(self):
  self.assertEqual(self.current,self.frozen[self.current['python_minor'].replace('.','')])
  self.assertEqual(len(self.current['cases']),511)
  self.assertEqual(len({r['id']for r in self.current['cases']}),511)
 def test_exact_closed_sources(self):
  for path,pin in self.current['sources'].items():self.assertEqual(hashlib.sha256((authority.ROOT/path).read_bytes()).hexdigest(),pin)
  self.assertEqual(self.frozen['311']['sources'],self.frozen['314']['sources'])
 def test_timestamp_unicode_profiles_match_actual_runtime_and_native_tables(self):
  raw=(ROOT/'tests/conformance/reference-package-timestamp-unicode-authority.json').read_bytes()
  self.assertEqual(hashlib.sha256(raw).hexdigest(),'b7a7776d40e40a4ff7362eba6c54dc45d7b7050d1af71a44b9d65846cbd471be')
  profiles=json.loads(raw)
  current=profiles['Python'+self.current['python_minor'].replace('.','')]
  self.assertEqual(current['unicode'],unicodedata.unidata_version)
  decimal=re.compile(r'\d').fullmatch
  ranges=[]
  for scalar in range(sys.maxunicode+1):
   if decimal(chr(scalar)):
    if ranges and scalar==ranges[-1][1]+1:ranges[-1][1]=scalar
    else:ranges.append([scalar,scalar])
  self.assertEqual(ranges,current['ranges'])
  source=(ROOT/'core/lib/reference_artifact/manifest_unicode.ml').read_text()
  for minor in ('311','314'):
   table=re.search(r'let python'+minor+r' = \[\|(.*?)\|\]',source).group(1)
   self.assertEqual([[int(a),int(b)]for a,b in re.findall(r'\((\d+),(\d+)\)',table)],profiles['Python'+minor]['ranges'])
 def test_runtime_differences_are_complete_retained_metadata_cases(self):
  changes=[]
  for a,b in zip(self.frozen['311']['cases'],self.frozen['314']['cases']):
   self.assertEqual({k:v for k,v in a.items()if k!='outcome'},{k:v for k,v in b.items()if k!='outcome'})
   if a!=b:changes.append(a['id']);self.assertEqual(a['operation'],'RunMetadata')
  self.assertEqual(changes,['Run:date:2','Run:date:13','Run:date:23','Run:path:5','Run:path:8','Run:path:11','Run:path:15','Run:path:16','Run:path:17','Run:path:18'])
  for index in (19,20):
   for corpus in self.frozen.values():
    row=next(r for r in corpus['cases']if r['id']==f'Run:path:{index}')
    self.assertEqual(row['outcome']['status'],'raise')
 def test_six_domains_and_real_archive_bytes_are_present(self):
  names={r['operation']for r in self.current['cases']}
  self.assertEqual(names,{'ReferenceBuildRequest','RunMetadata','PackageFile','AcceptedStage','ToolPin','BuildManifest','ReferenceBuildRequest-text','RunMetadata-text','PackageFile-text','AcceptedStage-text','ToolPin-text','BuildManifest-text','path','assemble','read'})
  rows={r['id']:r for r in self.current['cases']}
  for label in ('False','True'):
   data=bytes.fromhex(rows['assemble:'+label]['outcome']['value'])
   m,f,r=authority.archive.read_archive(data)
   self.assertEqual(m.to_dict(),rows['read:'+label]['outcome']['value']['manifest'])
   self.assertEqual(data,authority.archive.assemble_archive(m,f,r))
  self.assertEqual(rows['read:invalid-utf8']['outcome']['message'],'Archive metadata is not UTF-8 JSON.')
 def test_manifest_sorting_and_error_precedence_are_observed(self):
  rows={r['id']:r for r in self.current['cases']}
  self.assertEqual(rows['Manifest:reverse-files']['outcome'],rows['BuildManifest:valid']['outcome'])
  self.assertEqual(rows['Manifest:bad-nested-before-use']['outcome']['message'],'Invalid fields in PackageFile.')
  self.assertEqual(rows['Manifest:bad-stage-before-file-census']['outcome']['message'],'Invalid fields in AcceptedStage.')
  self.assertEqual(rows['Manifest:bad-tool-before-root-hash']['outcome']['message'],'Invalid fields in ToolPin.')
if __name__=='__main__':unittest.main()

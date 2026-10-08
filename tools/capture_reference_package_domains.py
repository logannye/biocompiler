"""Additive original-only six-record and reference-container byte authority."""
from pathlib import Path
import copy,hashlib,importlib,json,sys
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from biocompiler.artifacts import manifest as original
from biocompiler.artifacts import archive
from biocompiler.artifacts import archive_container
from tests.test_build_manifest import request_fixture,manifest_fixture
from tests.test_build_archive import archive_fixture

def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def capture():
 rows=[]
 def row(identity,operation,data,function):
  value={'id':identity,'operation':operation,'input':data}
  try:result=function();value['outcome']={'status':'return','value':result}
  except Exception as error:value['outcome']={'status':'raise','module':type(error).__module__,'type':type(error).__qualname__,'message':str(error)}
  rows.append(value)
 def decoded(cls,data):
  result=cls.from_dict(data)
  return {'value':result.to_dict(),'fingerprint':result.fingerprint,'json':result.to_json()}
 request=request_fixture();manifest=manifest_fixture()
 examples=[request,original.RunMetadata('2026-10-02T12:30:59.123456Z','host',{'source.py':'C:\\author\\source.py'}),manifest.files[0],manifest.accepted_stages[0],manifest.toolchain[0],manifest]
 for instance in examples:
  cls=type(instance);base=instance.to_dict()
  row(cls.__name__+':valid',cls.__name__,base,lambda cls=cls,base=base:decoded(cls,base))
  for number,value in enumerate([None,True,1,[],{},'wrong']):
   row(cls.__name__+':root:'+str(number),cls.__name__,value,lambda cls=cls,value=value:decoded(cls,value))
  for key in base:
   for number,value in enumerate([None,True,0,1.0,[],{},'', 'wrong']):
    data=copy.deepcopy(base);data[key]=value
    row(cls.__name__+':field:'+key+':'+str(number),cls.__name__,data,lambda cls=cls,data=data:decoded(cls,data))
   data={k:v for k,v in base.items() if k!=key}
   row(cls.__name__+':missing:'+key,cls.__name__,data,lambda cls=cls,data=data:decoded(cls,data))
  data=base|{'extra':True}
  row(cls.__name__+':extra',cls.__name__,data,lambda cls=cls,data=data:decoded(cls,data))
  for suffix,text in [('duplicate',json.dumps(base)[:-1]+',"schema_version":"future"}'),('nan','{"value":NaN}'),('duplicate-nan','{"schema_version":1,"schema_version":NaN}')]:
   def parse(cls=cls,text=text):
    result=cls.from_json(text);return {'value':result.to_dict(),'fingerprint':result.fingerprint,'json':result.to_json()}
   row(cls.__name__+':text:'+suffix,cls.__name__+'-text',{'text':text},parse)
 for alphabet in ('DNA','RNA'):
  data=request_fixture(alphabet).to_dict();row('Request:'+alphabet,'ReferenceBuildRequest',data,lambda data=data:decoded(original.ReferenceBuildRequest,data))
 for label,width in [('one',1),('upper',10000),('large',10001),('negative',-1)]:
  data=request.to_dict()|{'fasta_line_width':width};row('Request:width:'+label,'ReferenceBuildRequest',data,lambda data=data:decoded(original.ReferenceBuildRequest,data))
 paths=['a','references/x/source.txt','../file','/file','a//b','a/./b','a/../b','a/','C:/x','C:\\x','a\x00b','a\x7fb','manifest.json','run.json','', ' ', '\u2003', 'é/🧬', 'a\u2028b']
 for i,path in enumerate(paths):
  for allow in (False,True):row(f'path:{i}:{allow}','path',{'path':path,'allow_reserved':allow},lambda path=path,allow=allow:original.validate_package_path(path,allow_reserved=allow))
 for index,path in enumerate(paths):
  if not path.strip():continue
  from biocompiler.ir.intent import SourceLocation
  data=request.to_dict();data['construct']=replace(request.construct,placements=(replace(request.construct.placements[0],source=SourceLocation(path,7,'build')),)).to_dict()
  row('Request:source:'+str(index),'ReferenceBuildRequest',data,lambda data=data:decoded(original.ReferenceBuildRequest,data))
 times=['9999-12-31T24:00:00Z','2026-01-01T24:00:00.000001Z','2026-01-01T24:00:00.000000Z','2026-01-01T24:00:01Z','2024-02-29T00:00:00Z','1900-02-29T00:00:00Z','2000-02-29T23:59:59Z','0000-01-01T00:00:00Z','9999-12-31T23:59:59Z','2026-13-01T00:00:00Z','2026-00-01T00:00:00Z','2026-01-00T00:00:00Z','2026-04-31T00:00:00Z','2026-01-01T24:00:00Z','2026-01-01T00:60:00Z','2026-01-01T00:00:60Z','2026-01-01T00:00:00.Z','2026-01-01T00:00:00.1Z','2026-01-01T00:00:00.1234567Z','2026-01-01t00:00:00Z','2026-01-01T00:00:00+00:00','٢٠٢٦-01-01T00:00:00Z','2026-01-01T00:00:00.١Z','\U00010d40\U00010d41\U00010d42\U00010d43-01-01T00:00:00Z']
 for i,stamp in enumerate(times):
  data=examples[1].to_dict()|{'timestamp_utc':stamp};row('Run:date:'+str(i),'RunMetadata',data,lambda data=data:decoded(original.RunMetadata,data))
 locations=['/a','//','C:\\a','C:/a','C:a','1:/a','\\a','\\\\host\\share','\\\\host','\\\\host\\','\\\\?\\C:\\a','\\\\?\\C:','\\\\.\\pipe\\x','relative','/a\n','é:/root','🧬:/root','é:\\root','é:/','é:relative','e\u0301:/root']
 for i,path in enumerate(locations):
  data=examples[1].to_dict()|{'locations':{'source.py':path}};row('Run:path:'+str(i),'RunMetadata',data,lambda data=data:decoded(original.RunMetadata,data))
 base=manifest.to_dict()
 variants={
  'reverse-files':base|{'files':list(reversed(base['files']))},
  'reverse-stages':base|{'accepted_stages':list(reversed(base['accepted_stages']))},
  'duplicate-files':base|{'files':base['files']*2},
  'duplicate-tools':base|{'toolchain':base['toolchain']*2},
  'missing-reference':base|{'files':[v for v in base['files']if v['role']!='reference-input']},
  'bad-nested-before-use':base|{'files':[None],'intended_use':'bad'},
  'bad-stage-before-file-census':base|{'files':[],'accepted_stages':[None]},
  'bad-tool-before-root-hash':base|{'toolchain':[None],'request_fingerprint':'bad'},
 }
 for i in range(len(base['files'])):variants['missing-file:'+str(i)]=base|{'files':base['files'][:i]+base['files'][i+1:]}
 for key,data in variants.items():row('Manifest:'+key,'BuildManifest',data,lambda data=data:decoded(original.BuildManifest,data))
 m,files=archive_fixture()
 metadata=examples[1]
 inputs={'manifest':m.to_dict(),'files':[[k,v.hex()]for k,v in files.items()],'metadata':metadata.to_dict()}
 for include in (False,True):
  data=inputs|{'metadata':metadata.to_dict()if include else None}
  row('assemble:'+str(include),'assemble',data,lambda include=include:archive.assemble_archive(m,files,metadata if include else None).hex())
  encoded=archive.assemble_archive(m,files,metadata if include else None)
  def read(encoded=encoded):
   m,f,r=archive.read_archive(encoded);return {'manifest':m.to_dict(),'files':[[k,v.hex()]for k,v in f.items()],'metadata':r.to_dict()if r else None}
  row('read:'+str(include),'read',{'bytes':encoded.hex()},read)
 def raw_read(name,entries):
  data=archive_container._canonical_zip(entries)
  def call():
   m,f,r=archive.read_archive(data);return {'manifest':m.to_dict(),'files':[[k,v.hex()]for k,v in f.items()],'metadata':r.to_dict()if r else None}
  row('read:'+name,'read',{'bytes':data.hex()},call)
 raw_read('no-manifest',{'a':b'x'})
 for label,value in [('array',[]),('no-schema',{}),('bad-schema',{'schema_version':True}),('unsupported',{'schema_version':'future'}),('bad-fields',{'schema_version':m.schema_version})]:
  raw_read(label,{'manifest.json':json.dumps(value).encode()})
 raw_read('invalid-utf8',{'manifest.json':b'\xff'})
 raw_read('duplicate-schema',{'manifest.json':b'{"schema_version":1,"schema_version":2}'})
 entries={'manifest.json':m.to_json().encode(),**files}
 raw_read('no-terminal-newline',entries)
 entries['manifest.json']=(m.to_json()+'\n').encode();entries['sequence.fasta']=b'changed';raw_read('file-mismatch',entries)
 sources={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['src/biocompiler/artifacts/manifest.py','src/biocompiler/artifacts/archive.py','src/biocompiler/artifacts/archive_container.py','src/biocompiler/ir/serialization.py','tests/test_build_manifest.py','tests/test_build_archive.py','examples/reference_construct.py']}
 for cls in [type(v)for v in examples]:
  assert cls.__module__==original.__name__
 return {'schema':'biocompiler.reference_package_domains.v1','python_minor':f'{sys.version_info.major}.{sys.version_info.minor}','sources':sources,'cases':rows}
if __name__=='__main__':Path(sys.argv[1]).write_bytes(canonical(capture())+b'\n')

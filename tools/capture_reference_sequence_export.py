"""Actual original sequence construction/fidelity/current-authority observations."""
from pathlib import Path
from dataclasses import replace
import copy,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT),str(ROOT/'tests')]
from biocompiler.artifacts import sequences as source
from tests.test_sequence_export import export_fixture
from tools.reference_package_source_lineage import source_identity

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def fields(bundle):return {name:getattr(bundle,name)for name in ('fasta','specification','line_width','sequence_sha256','molecular_fingerprint')}
def output(bundle):return fields(bundle)|{'fasta_sha256':bundle.fasta_sha256,'specification_sha256':bundle.specification_sha256}
def capture():
 rows=[]
 def row(identity,operation,data,call):
  item={'id':identity,'operation':operation,'input':data}
  try:
   result=call();item['outcome']={'status':'return','value':output(result)if isinstance(result,source.SequenceExport)else result}
  except Exception as error:item['outcome']={'status':'raise','module':type(error).__module__,'type':type(error).__qualname__,'message':str(error)}
  rows.append(item)
 for alphabet in ('DNA','RNA'):
  request,construct,artifact,registry,manifests,bundle=export_fixture(alphabet)
  authority={'request':request.to_dict(),'construct':construct.to_dict(),'artifact':artifact.to_dict(),'registry':registry.to_dict(),'manifests':[[k,v.to_dict()]for k,v in manifests.items()]}
  for width in (1,60,80,10000,0,-1,10001,True,1.5,'80',None):
   row(alphabet+':export-width:'+repr(width),'export',authority|{'line_width':width},lambda width=width:source.export_reference_sequence(request,construct,artifact,registry,manifests,line_width=width))
  row(alphabet+':verify','verify',{'artifact':artifact.to_dict(),'bundle':fields(bundle)},lambda:source.verify_sequence_export(bundle,artifact))
  for key in fields(bundle):
   for i,value in enumerate([None,True,0,[],{},'', 'x']):
    data=fields(bundle)|{key:value};row(alphabet+':make:'+key+':'+str(i),'make',data,lambda data=data:source.SequenceExport(**data))
  lines=bundle.fasta.split('\n');header=lines[0]
  variants={
   'no-newline':bundle.fasta[:-1],'crlf':bundle.fasta.replace('\n','\r\n'),'non-ascii':bundle.fasta+'é',
   'no-header':bundle.fasta[1:],'header-only':header+'\n','empty-sequence':header+'\n\n',
   'double-space':bundle.fasta.replace(' alphabet','  alphabet',1),'lowercase':header+'\n'+ '\n'.join(lines[1:]).lower(),
   'short-first':header+'\n'+lines[1][:-1]+'\n'+'\n'.join(lines[2:]),'extra-record':bundle.fasta+'>second\nACGT\n',
   'scope':bundle.fasta.replace('scope=CDS-reference-only','scope=complete'),'use':bundle.fasta.replace('use=software_test','use=human_therapeutic'),
   'reference-percent':bundle.fasta.replace('>'+header[1],'>%'+format(ord(header[1]),'02x'),1),
   'reference-invalid-utf8':'>%FF '+' '.join(header[1:].split(' ')[1:])+'\n'+'\n'.join(lines[1:]),
  }
  for label,text in variants.items():
   changed=replace(bundle,fasta=text);row(alphabet+':fasta:'+label,'verify',{'artifact':artifact.to_dict(),'bundle':fields(changed)},lambda changed=changed:source.verify_sequence_export(changed,artifact))
  for label,spec in [('no-newline',bundle.specification[:-1]),('compact',json.dumps(artifact.to_dict(),sort_keys=True,separators=(',',':'))+'\n'),('duplicate','{"records":[],"records":[]}'),('nan','{"x":NaN}'),('wrong-identity','{}')]:
   changed=replace(bundle,specification=spec);row(alphabet+':spec:'+label,'verify',{'artifact':artifact.to_dict(),'bundle':fields(changed)},lambda changed=changed:source.verify_sequence_export(changed,artifact))
  for key in ('sequence_sha256','molecular_fingerprint'):
   changed=replace(bundle,**{key:'0'*64});row(alphabet+':identity:'+key,'verify',{'artifact':artifact.to_dict(),'bundle':fields(changed)},lambda changed=changed:source.verify_sequence_export(changed,artifact))
  record=artifact.records[0];sequence=record.sequence[:6]+('A'if record.sequence[6]!='A'else'C')+record.sequence[7:]
  changed_record=replace(record,sequence=sequence,sequence_sha256=hashlib.sha256(sequence.encode()).hexdigest())
  changed_artifact=replace(artifact,records=(changed_record,))
  changed_bundle=replace(bundle,fasta=header+'\n'+'\n'.join(sequence[i:i+bundle.line_width]for i in range(0,len(sequence),bundle.line_width))+'\n',specification=changed_artifact.to_json()+'\n',sequence_sha256=changed_record.sequence_sha256,molecular_fingerprint=changed_artifact.fingerprint)
  row(alphabet+':self-rehashed-fidelity','verify',{'artifact':changed_artifact.to_dict(),'bundle':fields(changed_bundle)},lambda:source.verify_sequence_export(changed_bundle,changed_artifact))
  row(alphabet+':self-rehashed-current-check','export',authority|{'artifact':changed_artifact.to_dict(),'line_width':80},lambda:source.export_reference_sequence(request,construct,changed_artifact,registry,manifests))
 sources={p:source_identity(ROOT,p)for p in ['src/biocompiler/artifacts/sequences.py','src/biocompiler/backends/reference.py','src/biocompiler/verification/molecular.py','tests/test_sequence_export.py','tests/test_construct_checker.py']}
 return {'schema':'biocompiler.reference_sequence_export_literals.v1','sources':sources,'cases':rows}
if __name__=='__main__':Path(sys.argv[1]).write_bytes(canonical(capture())+b'\n')

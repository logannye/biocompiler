"""Additive actual-Python byte/error authority for the shared container draft.

No original source, tests, package schema, or accepted artifact is changed. The
native test consumes only declared inputs; full actual outputs are comparisons.
"""
from pathlib import Path
import hashlib
import importlib
import inspect
import io
import json
import stat
import struct
import sys
import warnings
import zipfile
from types import CodeType, FunctionType, SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
original = importlib.import_module('biocompiler.artifacts.archive_container')

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()

def unchecked(entries, **options):
    result = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        with zipfile.ZipFile(result, 'w', compression=options.get('compression', 0)) as archive:
            archive.comment = options.get('comment', b'')
            for path, payload in entries:
                info = zipfile.ZipInfo(path, options.get('timestamp', (1980, 1, 1, 0, 0, 0)))
                info.create_system = options.get('system', 3)
                info.external_attr = options.get('mode', stat.S_IFREG | 0o644) << 16
                info.internal_attr = options.get('internal', 0)
                info.compress_type = options.get('compression', 0)
                info.extra = options.get('extra', b'')
                archive.writestr(info, payload)
    return result.getvalue()

def source_authority():
    """Bind actual installed or checkout code to unchanged original bytes."""
    logical = 'src/biocompiler/artifacts/archive_container.py'
    source = ROOT / logical
    actual = Path(original.__file__).resolve()
    raw = source.read_bytes()
    assert original.__name__ == 'biocompiler.artifacts.archive_container'
    assert sys.modules.get(original.__name__) is original
    assert actual.read_bytes() == raw, 'Installed archive source differs from original'
    def codes(code):
        yield code
        for value in code.co_consts:
            if type(value) is CodeType:
                yield from codes(value)
    compiled = list(codes(compile(raw, str(actual), 'exec', dont_inherit=True)))
    for name in ('_safe_path','validate_files','_canonical_zip','assemble_container','_preflight','read_container'):
        function = getattr(original, name)
        assert type(function) is FunctionType
        assert function.__module__ == original.__name__ and function.__qualname__ == name
        assert Path(function.__code__.co_filename).resolve() == actual
        assert function.__globals__ is vars(original)
        assert any(function.__code__ == code for code in compiled), 'Loaded archive code differs from original'
    return {'path': logical, 'sha256': hashlib.sha256(raw).hexdigest()}

def capture():
    authority = source_authority()
    rows = []
    def row(identity, operation, inputs, function, limits=None):
        observed = {'id': identity, 'operation': operation, 'input': inputs, 'limits': limits or {}}
        names = {'max_archive_bytes':'MAX_ARCHIVE_BYTES', 'max_member_bytes':'MAX_MEMBER_BYTES',
                 'max_metadata_bytes':'MAX_METADATA_BYTES', 'max_entries':'MAX_ENTRIES', 'max_path_bytes':'MAX_PATH_BYTES'}
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            from contextlib import ExitStack
            with ExitStack() as stack:
                for name, value in (limits or {}).items(): stack.enter_context(patch.object(original, names[name], value))
                try:
                    value = function()
                    if isinstance(value, bytes): value = {'bytes': value.hex()}
                    elif isinstance(value, dict): value = {'entries': [[key, val.hex()] for key,val in value.items()]}
                    observed['outcome'] = {'status':'return', 'value':value}
                except Exception as error:
                    observed['outcome'] = {'status':'raise', 'module':type(error).__module__,
                                           'type':type(error).__qualname__, 'message':str(error)}
        rows.append(observed)
    examples = [ [('a', b'')], [('z/file.bin', b'\x00\xffabc'), ('a.json', b'{"a": 1}\n')],
                [('caf\u00e9/\U0001f9ec.json', 'literal\u2028\u007f'.encode()), ('name\'".bin', b'raw')],
                [('manifest.json', b'{\n  "x": 1.0\n}\n'), ('run.json', b'{}\n'), ('payload.txt', b'ACGT')]]
    for i, entries in enumerate(examples):
        encoded = original._canonical_zip(dict(entries))
        raw = [[name, value.hex()] for name,value in entries]
        row(f'encode:{i}', 'encode', {'entries':raw}, lambda entries=entries:original._canonical_zip(dict(entries)))
        row(f'read:{i}', 'read', {'bytes':encoded.hex()}, lambda encoded=encoded:original.read_container(encoded))
    row('encode:empty','encode',{'entries':[]},lambda:original._canonical_zip({}))
    base=original._canonical_zip({'a.txt':b'payload', 'b.bin':b'second'})
    central=base.index(b'PK\x01\x02'); footer=len(base)-22
    def read_case(name, data, limits=None):
        row('read:'+name,'read',{'bytes':data.hex()},lambda:original.read_container(data),limits)
    def changed(offset, fmt, value):
        data=bytearray(base);struct.pack_into(fmt,data,offset,value);return bytes(data)
    for name,data in [('empty',b''),('short',b'PK'),('trailing',base+b'X'),('prefix',b'X'+base),
                      ('truncated',base[:-1]),('reversed',unchecked([('b.bin',b'second'),('a.txt',b'payload')]))]:read_case(name,data)
    for name,offset,fmt,value in [
        ('footer-signature',footer,'<I',0),('disk',footer+4,'<H',1),('directory-disk',footer+6,'<H',1),
        ('disk-count',footer+8,'<H',1),('member-count',footer+10,'<H',0),('directory-size',footer+12,'<I',1),
        ('directory-offset',footer+16,'<I',0),('comment-length',footer+20,'<H',1),
        ('directory-signature',central,'<I',0),('zero-name',central+28,'<H',0),('long-name',central+28,'<H',1025),
        ('extra',central+30,'<H',1),('member-comment',central+32,'<H',1),
        ('version',central+6,'<H',99),('system',central+5,'<B',0),('executable',central+38,'<I',0x81ed0000),
        ('internal',central+36,'<H',1),('compression',central+10,'<H',8),('compressed-size',central+20,'<I',8),
        ('encrypted',central+8,'<H',1),('central-time',central+12,'<H',2),('central-date',central+14,'<H',34),
        ('crc',central+16,'<I',0),('local-offset',central+42,'<I',len(base)-10),('local-signature',0,'<I',0),
        ('local-crc',14,'<I',0),('local-time',10,'<H',1),('local-extra',28,'<H',1),
        ('local-name-size',26,'<H',4),('local-flags',6,'<H',1),('create-version',central+4,'<B',21),
        ('extract-version',central+6,'<B',21),('volume',central+34,'<H',1)]:read_case(name,changed(offset,fmt,value))
    for field in (8,10):
        data=bytearray(base);struct.pack_into('<H',data,footer+field,3)
        struct.pack_into('<H',data,footer+(10 if field==8 else 8),3)
        read_case('lying-count-'+str(field),bytes(data))
    read_case('payload-crc',base[:35]+b'X'+base[36:])
    read_case('local-name',base[:30]+b'z'+base[31:])
    read_case('nul-name',base.replace(b'a.txt',b'a\0txt'))
    second=central+46+5
    read_case('overlap',changed(second+42,'<I',0))
    empty=bytearray(original._canonical_zip({'a':b'', 'b':b''}))
    empty_central=empty.index(b'PK\x01\x02')
    struct.pack_into('<I',empty,empty_central+47+42,0)
    struct.pack_into('<H',empty,28,65535)
    read_case('overlap-empty-beyond-input',bytes(empty))
    def packed(data, offset, fmt, value):
        data=bytearray(data);struct.pack_into(fmt,data,offset,value);return bytes(data)
    badpath=bytearray(base);badpath[central+46:central+51]=b'../..'
    read_case('order-version-before-path',packed(badpath,second+6,'<H',99))
    badutf=bytearray(changed(central+38,'<I',0));badutf[second+46]=255
    read_case('order-utf8-before-mode',packed(badutf,second+8,'<H',0x800))
    read_case('order-footer-before-directory',packed(changed(central,'<I',0),footer+4,'<H',1))
    read_case('order-preflight-before-version',packed(changed(central+28,'<H',0),second+6,'<H',99))
    badsize=packed(packed(base,second+20,'<I',16777217),second+24,'<I',16777217)
    read_case('order-crc-before-next-size',packed(badsize,central+16,'<I',0))
    read_case('order-mode-before-size',packed(changed(central+38,'<I',0),central+24,'<I',16777217))
    read_case('order-policy-before-size',packed(changed(central+8,'<H',1),central+24,'<I',16777217))
    read_case('order-crc-before-canonical',packed(changed(14,'<I',0),second+16,'<I',0))
    # A locator hidden in the preflight-visible filename makes ZipFile inspect
    # a second, source-controlled directory. Inputs remain bounded byte strings.
    def zip64_catalog(catalog=None, *, record_change=None, locator_change=None):
        payload=base[:central]
        catalog=base[central:footer] if catalog is None else catalog
        record_at=len(payload)+len(catalog)
        outer=bytearray(base[central:central+46]);struct.pack_into('<H',outer,28,20)
        locator=bytearray(struct.pack('<4sLQL',b'PK\x06\x07',0,record_at,1))
        record=bytearray(struct.pack('<4sQ2H2L4Q',b'PK\x06\x06',90,45,45,0,0,2,2,len(catalog),len(payload)))
        if record_change: record_change(record)
        if locator_change: locator_change(locator)
        data=payload+catalog+record+outer+locator
        footer64=struct.pack('<4s4H2LH',b'PK\x05\x06',0,0,1,1,len(outer)+len(locator),record_at+len(record),0)
        return bytes(data+footer64)
    read_case('zip64-alternate-valid',zip64_catalog())
    read_case('zip64-disk',zip64_catalog(locator_change=lambda value:struct.pack_into('<L',value,4,1)))
    read_case('zip64-offset',zip64_catalog(locator_change=lambda value:struct.pack_into('<Q',value,8,2**64-1)))
    read_case('zip64-record-missing',zip64_catalog(record_change=lambda value:value.__setitem__(slice(0,4),b'XXXX')))
    read_case('zip64-record-size',zip64_catalog(record_change=lambda value:struct.pack_into('<Q',value,4,44)))
    read_case('zip64-record-directory',zip64_catalog(record_change=lambda value:struct.pack_into('<Q',value,48,0)))
    read_case('zip64-empty',zip64_catalog(b''))
    read_case('zip64-central-short',zip64_catalog(b'PK\x01\x02'))
    read_case('zip64-central-magic',zip64_catalog(b'X'*46))
    read_case('zip64-central-name-short',zip64_catalog(base[central:central+46]))
    read_case('zip64-central-version',zip64_catalog(packed(base[central:footer],6,'<H',99)))
    for label,extra in [('unknown',struct.pack('<HH',999,0)),('short',struct.pack('<HH',999,8)),
                        ('zip64-missing',struct.pack('<HH',1,0)),('unicode-short',struct.pack('<HH',0x7075,1)+b'x')]:
        cat=bytearray(base[central:central+51]);struct.pack_into('<H',cat,30,len(extra))
        if label=='zip64-missing':struct.pack_into('<I',cat,24,0xffffffff)
        cat.extend(extra)
        read_case('zip64-extra-'+label,zip64_catalog(cat))
    for invalid in (b'\xff',b'\xc2',b'\xe1\x80',b'\xed\xa0',b'\xf0\x80',b'\xe1A'):
        data=bytearray(base);struct.pack_into('<H',data,central+8,0x800)
        data[central+46:central+46+len(invalid)]=invalid
        read_case('utf8-'+invalid.hex(),bytes(data))
    for path in ('../escape','/absolute','folder/../escape','folder//file','folder\\file','C:/drive',
                 'folder/./file','folder/','bad\nname','bad\x7fname'):
        read_case('path-'+path,unchecked([('a',b''),(path,b'bad')]))
    read_case('duplicate',unchecked([('a',b'first'),('a',b'next')]))
    for label,name in [('unicode-crc','caf\u00e9'),('repr-control','x\x80'),('repr-newunicode','\u1c89'),('repr-quotes',"both'\"")]:
        raw=original._canonical_zip({name:b'payload'});at=raw.index(b'PK\x01\x02')
        bad=bytearray(raw);struct.pack_into('<I',bad,at+16,0)
        read_case(label,bytes(bad))
    for name,limits in [('total',{'max_archive_bytes':len(base)-1}),('member',{'max_member_bytes':6}),
                        ('count',{'max_entries':1}),('path-bytes',{'max_path_bytes':4})]:read_case('reduced-'+name,base,limits)
    read_case('metadata-size',original._canonical_zip({'manifest.json':b'{}\n'}),{'max_metadata_bytes':2})
    for data in [None, {}, [], {'z':-0.0,'a':7,'b':7.0,'empty':[]},
                 {'\U0001f9ec':'\x00\b\f\n\r\t"\\\u007f\u0080\u2028','\u00e9':[True,False,None]},
                 [5e-324,1.7976931348623157e308,1e-5,1e-4,1e15,1e16,0.1],
                 {'arrays':[[1],{},[[],{}]],'obj':{'b':2,'a':1}}]:
        row('pretty:'+str(len(rows)),'pretty',{'document':data},
            lambda data=data:(json.dumps(data,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())
    class Metadata:
        def __init__(self, document, members):
            self.document = document
            self.files = tuple(SimpleNamespace(**member) for member in members)
        def to_json(self, indent=2):
            return json.dumps(self.document, sort_keys=True, indent=indent, ensure_ascii=False, allow_nan=False)
    files = [('payload.bin', b'ACGT')]
    declared = [{'path':'payload.bin','byte_length':4,'sha256':hashlib.sha256(b'ACGT').hexdigest()}]
    validations = [ ('valid', declared, files, {}),
        ('duplicate-manifest', declared + declared, files, {}),
        ('missing', declared, [], {}), ('extra', declared, files + [('extra', b'')], {}),
        ('size', [dict(declared[0], byte_length=3)], files, {}),
        ('hash', [dict(declared[0], sha256='0'*64)], files, {}),
        ('reserved', declared, [('manifest.json', b'')], {}),
        ('unsafe-first', [], [('../bad', b'')], {}),
        ('member-limit', declared, files, {'max_member_bytes':3}),
        ('total-limit', declared, files, {'max_archive_bytes':3})]
    for name, members, payloads, limits in validations:
        metadata = Metadata({'kind':'container-control'}, members)
        row('validate:'+name, 'validate-files', {'members':members,'entries':[[k,v.hex()] for k,v in payloads]},
            lambda metadata=metadata,payloads=payloads:original.validate_files(metadata,dict(payloads)), limits)
    for label, run, limits in [('ordinary', None, {}), ('run', {'timestamp':'opaque', 'z':7.0}, {}),
                                ('metadata-limit',None,{'max_metadata_bytes':1}), ('count-limit',None,{'max_entries':1})]:
        document = {'z':7.0,'a':'café','files':declared}
        manifest = Metadata(document, declared)
        run_metadata = None if run is None else Metadata(run, [])
        row('assemble:'+label,'assemble',{'manifest':document,'members':declared,
            'entries':[[k,v.hex()] for k,v in files], 'run_metadata':run},
            lambda manifest=manifest,run_metadata=run_metadata:original.assemble_container(manifest,dict(files),run_metadata),limits)
    assert source_authority() == authority, 'Archive source changed during original observation'
    return {'schema':'biocompiler.archive_container_literals.v1','python_minor':f'{sys.version_info.major}.{sys.version_info.minor}',
            'source':authority,
            'cases':rows}

def runtime_authority():
    import platform
    import unicodedata
    selected = {
        'zipfile._EndRecData':zipfile._EndRecData,
        'zipfile._EndRecData64':zipfile._EndRecData64,
        'zipfile.ZipFile._RealGetContents':zipfile.ZipFile._RealGetContents,
        'zipfile.ZipFile.open':zipfile.ZipFile.open,
        'zipfile.ZipInfo._decodeExtra':zipfile.ZipInfo._decodeExtra,
        'zipfile.ZipExtFile._read1':zipfile.ZipExtFile._read1,
        'zipfile.ZipExtFile._read2':zipfile.ZipExtFile._read2,
        'json.encoder._make_iterencode':json.encoder._make_iterencode,
    }
    return {'schema':'biocompiler.archive_stdlib_authority.v1',
            'python':platform.python_version(),'unicode':unicodedata.unidata_version,
            'source_profile':'Python'+str(sys.version_info.major)+str(sys.version_info.minor),
            'modules':{module.__name__:{'path':str(Path(module.__file__).resolve()),
                'sha256':hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()}
                for module in (zipfile,json.encoder)},
            'functions':{name:{'sha256':hashlib.sha256(inspect.getsource(function).encode()).hexdigest(),
                'source':inspect.getsource(function)} for name,function in selected.items()}}

if __name__=='__main__':
    target=Path(sys.argv[1]);target.write_bytes(canonical(capture())+b'\n')
    if len(sys.argv)>2:Path(sys.argv[2]).write_bytes(canonical(runtime_authority())+b'\n')

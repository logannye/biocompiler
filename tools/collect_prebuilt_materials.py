"""Collect actual hosted final-binary source, notices and relinking materials.

The source lock is checked in; final binary/run identities come from CI, never
from captured expected semantic outputs. This performs no native execution.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile

if __package__:
    from . import prebuilt_sources as sources, prebuilt_core_materials as materials, build_prebuilt_core as build
else:
    import prebuilt_sources as sources
    import prebuilt_core_materials as materials
    import build_prebuilt_core as build

require=build.require


def collect(args):
    require(os.environ.get('GITHUB_ACTIONS')=='true','Material collection is a hosted release operation')
    require(not args.output.exists(),'Material output must be fresh');args.output.mkdir(parents=True)
    files={};components={};root=args.output/'files';root.mkdir()
    def add(name,component,role,raw):
        materials.logical(name);require(name not in files and 0<len(raw)<=materials.MAX_FILE,'Invalid or repeated retained material')
        require(sum(row['size'] for row in files.values())+len(raw)<=materials.MAX_TOTAL,'Complete materials exceed retained bound')
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        files[name]={'component':component,'role':role,**materials.digest(raw)}
    def copy(name,component,role,path):add(name,component,role,build.regular(path,materials.MAX_FILE))
    lock=json.loads(sources.LOCK.read_bytes());sources.inspect_sources(lock,args.sources)
    actual=subprocess.check_output([str(args.opam),'list','--installed','--columns=name,version','--color=never'],text=True)
    installed=dict(re.findall(r'^([A-Za-z0-9_-]+)\s+(\S+)\s*$',actual,re.M))
    for origin,row in sorted(lock['sources'].items()):
        name='ocaml' if origin=='ocaml-compiler' else origin
        if name!='gmp':require(installed.get(origin)==row['version'],'Actual opam package differs from retained source: '+origin)
        components[name]={'version':row['version'],'linked':name in ('ocaml','gmp','zarith','digestif','eqaf')}
        copy(name+'/source.archive',name,'source',args.sources/row['path'])
        archive,members=sources.archive_index(args.sources/row['path'])
        try:
            for member in members:
                if member.name in row['notices'] and member.size:
                    add(name+'/notices/'+member.name,name,'license',archive.extractfile(member).read())
        finally:archive.close()
        # The exact upstream opam build recipe and checksum is an independently
        # pinned source file; GMP uses our complete recorded configure/build plan.
        if name!='gmp':
            metadata=(args.checkout/'protocol/core-release-opam'/str(origin+'.'+row['version']+'.opam'))
            require(hashlib.sha256(metadata.read_bytes()).hexdigest()==row['opam_sha256'],'Upstream opam recipe changed')
            copy(name+'/build.opam',name,'build-recipe',metadata)
    components['biocompiler']={'version':build.VERSION,'linked':True}
    # Retain source directly from the tested Git object, not mutable build outputs.
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=args.checkout,text=True).strip()
    require(revision==args.tested_revision,'Material source differs from actually tested checkout')
    project=subprocess.check_output(['git','archive','--format=tar',revision,'core','src','protocol','tools','pyproject.toml'],cwd=args.checkout)
    add('biocompiler/source.tar','biocompiler','source',project)
    copy('biocompiler/ownership.opam','biocompiler','notice',args.checkout/'core/biocompiler_core.opam')
    for name in ('collect_prebuilt_materials.py','prebuilt_sources.py','prepare_static_gmp.py','build_prebuilt_core.py'):
        copy('biocompiler/recipes/'+name,'biocompiler','build-recipe',args.checkout/'tools'/name)
    copy('biocompiler/recipes/relink.sh','biocompiler','build-recipe',args.checkout/'tools/relink_prebuilt_core.sh')
    copy('biocompiler/dependencies.opam.locked','biocompiler','dependency-lock',args.native_root/'dependencies.opam.locked')
    copy('biocompiler/switch.export','biocompiler','build-receipt',args.native_root/'switch.export')
    add('biocompiler/actual-packages.txt','biocompiler','build-receipt',actual.encode())
    configuration=args.static_root/'configuration'
    static=json.loads((configuration/'input.json').read_bytes())
    add('gmp/input.json','gmp','build-receipt',build.canonical(static))
    copy('gmp/gmp.pc','gmp','pkg-config',configuration/'gmp.pc')
    copy('gmp/libgmp.a','gmp','link-input',Path(static['archive']['path']))
    copy('gmp/gmp.h','gmp','header',Path(static['header']['path']))
    copy('gmp/build.json','gmp','build-recipe',args.static_root/'build.json')
    copy('gmp/config.log','gmp','build-receipt',args.static_root/'build/config.log')
    copy('gmp/relink-libgmp.a','gmp','relink-input',Path(static['archive']['path']))
    # Preserve all compiled native libraries/objects actually available to final
    # linking, including the OCaml runtime and project main objects. No executable
    # is run and no semantic acceptance is imported from these materials.
    suffixes={'.a','.o','.cmx','.cmxa','.cmi'}
    for component,directory in [('biocompiler',args.checkout/'core/_build/default/lib'),
        ('biocompiler',args.checkout/'core/_build/default/bin'),('ocaml',args.switch/'lib/ocaml'),
        ('zarith',args.switch/'lib/zarith'),('digestif',args.switch/'lib/digestif'),('eqaf',args.switch/'lib/eqaf')]:
        require(directory.is_dir(),'Missing actual relinking input directory: '+str(directory))
        for path in sorted(directory.rglob('*')):
            if path.is_file() and path.suffix in suffixes:
                relative=path.relative_to(directory).as_posix()
                label=directory.relative_to(args.checkout/'core/_build/default').as_posix() if component=='biocompiler' else directory.name
                copy(component+'/relink/'+label+'/'+relative,component,'relink-input',path.resolve(strict=True))
    binaries=json.loads((args.native_root/'binaries.json').read_bytes())
    authority={'source_revision':args.source_revision,'tested_revision':args.tested_revision,'run_id':args.run_id,
        'native_platform':args.platform,'components':components,'static_gmp_receipt':materials.digest(build.canonical(static)),
        'binaries':{name:materials.digest((args.native_root/name).read_bytes()) for name in build.ROLES}}
    require(binaries['revision']==args.tested_revision and binaries['sha256']=={name:pin['sha256'] for name,pin in authority['binaries'].items()},'Material binaries differ from tested inputs')
    manifest={'schema_version':materials.SCHEMA,**authority,'files':files,'dependency_lock':'biocompiler/dependencies.opam.locked',
        'recipes':{'build':'biocompiler/recipes/prebuilt_sources.py','relink':'biocompiler/recipes/relink.sh'},
        'static_gmp':{'receipt':'gmp/input.json','pkg_config':'gmp/gmp.pc','archive':'gmp/libgmp.a','header':'gmp/gmp.h'}}
    raw=build.canonical(manifest);pin=hashlib.sha256(raw).hexdigest()
    materials.verify(root,manifest,authority,dependency_lock=materials.digest((args.native_root/'dependencies.opam.locked').read_bytes()),manifest_sha256=pin)
    (args.output/'materials.json').write_bytes(raw);(args.output/'authority.json').write_bytes(build.canonical(authority))
    (args.output/'manifest.sha256').write_text(pin+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('checkout','sources','static-root','native-root','switch','opam','output'):parser.add_argument('--'+key,type=Path,required=True)
    for key in ('source-revision','tested-revision','run-id','platform'):parser.add_argument('--'+key,required=True)
    collect(parser.parse_args())


if __name__=='__main__':main()

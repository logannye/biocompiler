"""Fetch exact official/locked sources and prepare one hosted portable GMP build.

Fetch/inspect are source-only. The separate static-build operation is authorized
only on the matching hosted runner; local controls never invoke it.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request

if __package__:
    from . import build_prebuilt_core as release, prepare_static_gmp as gmp, prebuilt_core_materials as materials
else:
    import build_prebuilt_core as release
    import prepare_static_gmp as gmp
    import prebuilt_core_materials as materials

ROOT=Path(__file__).resolve().parents[1]
LOCK=ROOT/'protocol/core-release-sources-v1.json'
require=release.require


def fetch(url,pin,output):
    require(url.startswith('https://') and not output.exists(),'Source download requires HTTPS and a fresh path')
    temporary=output.with_suffix(output.suffix+'.part'); size=0; digest=hashlib.sha256()
    try:
        with urllib.request.urlopen(url,timeout=60) as response,temporary.open('xb') as stream:
            require(response.geturl().startswith('https://'),'Source redirect downgraded TLS')
            while chunk:=response.read(1024*1024):
                size+=len(chunk);require(size<=pin['size'],'Upstream source exceeds exact pinned size');digest.update(chunk);stream.write(chunk)
        require(size==pin['size'] and digest.hexdigest()==pin['sha256'],'Upstream source bytes differ from locked checksum')
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def archive_index(path):
    """Bound complete source archive before extracting; no links/special files execute."""
    archive=tarfile.open(path); rows=[];seen=set();size=0
    try:
        for member in archive:
            name=member.name.removeprefix('./').rstrip('/')
            require(name and not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
                and name not in seen,'Source archive path is unsafe or repeated')
            seen.add(name);require(len(seen)<=100000,'Source archive count exceeds bound')
            require(member.isfile() or member.isdir() or member.issym() or member.islnk(),'Source archive contains a special file')
            if member.isfile():
                size+=member.size;require(0<=member.size<=64*1024*1024 and size<=512*1024*1024,'Source archive expansion exceeds bound')
            if member.issym() or member.islnk():
                # Links are retained as source data, but never traversed while writing.
                target=PurePosixPath(member.linkname)
                require(not target.is_absolute(),'Source archive link is absolute')
                joined=(PurePosixPath(name).parent/target) if member.issym() else target
                normalized=os.path.normpath(str(joined))
                require(not normalized.startswith('../') and normalized!='..','Source archive link escapes root')
            rows.append(member)
        return archive,rows
    except BaseException:
        archive.close();raise


def inspect_sources(lock,root):
    require(set(lock)=={'schema_version','opam_repository','sources'} and lock['opam_repository']=='ac27950e5eac6c981ad809dff370c937820b7893', 'Source repository authority differs')
    result={}
    for name,row in sorted(lock['sources'].items()):
        path=root/row['path'];materials.read_pin(path,row)
        found={}
        archive,members=archive_index(path)
        try:
            for member in members:
                if member.name in row['notices']:
                    require(member.isfile(),'Notice is not a source file')
                    raw=archive.extractfile(member).read()
                    require(materials.digest(raw)==row['notices'][member.name],'Retained upstream notice differs')
                    found[member.name]=materials.digest(raw)
            require(found==row['notices'],'Source archive omits pinned notices')
        finally:archive.close()
        result[name]={'version':row['version'],'source':materials.digest(path.read_bytes()),'notices':found}
    return result


def extract_source(path,output):
    require(not output.exists(),'Source extraction root must be fresh');output.mkdir(parents=True)
    archive,members=archive_index(path)
    try:
        # Reject any pathname nested below an archive link before extraction.
        links={PurePosixPath(m.name) for m in members if m.issym() or m.islnk()}
        require(all(not any(parent in links for parent in PurePosixPath(m.name).parents) for m in members),'Source member traverses an archive link')
        for member in members:
            target=output/member.name
            if member.isdir():target.mkdir(parents=True,exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True,exist_ok=True)
                with archive.extractfile(member) as source,target.open('xb') as dest:shutil.copyfileobj(source,dest,1024*1024)
                target.chmod(0o755 if member.mode&0o111 else 0o644)
        for member in members:
            target=output/member.name
            if member.issym():target.parent.mkdir(parents=True,exist_ok=True);target.symlink_to(member.linkname)
            elif member.islnk():
                source=output/member.linkname
                require(source.is_file() and not source.is_symlink(),'Source hardlink target is not a regular member')
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    finally:archive.close()
    roots=list(output.iterdir());require(len(roots)==1 and roots[0].is_dir() and not roots[0].is_symlink(),'Source archive has no unique package root')
    return roots[0]


def build_plan(target,source,prefix,compiler,make):
    require(target in release.TARGETS and all(path.is_absolute() for path in (source,prefix,compiler,make)),'Invalid static build paths')
    flags='-O2 -fPIC -march=x86-64 -mtune=generic' if target=='linux-x86_64' else '-O2 -fPIC -march=armv8-a -mmacosx-version-min=14.0'
    return {'environment':{'CC':str(compiler),'CFLAGS':flags,'CPPFLAGS':'','LDFLAGS':'','LC_ALL':'C',
            **({'MACOSX_DEPLOYMENT_TARGET':'14.0'} if target=='macos-arm64' else {})},
        'commands':[[str(source/'configure'),'--prefix='+str(prefix),'--disable-shared','--enable-static','--with-pic','--disable-assembly','--disable-cxx'],
                    [str(make),'-j2'],[str(make),'check'],[str(make),'install']]}


def static_build(args,lock):
    require(os.environ.get('GITHUB_ACTIONS')=='true' and (platform.system(),platform.machine())==release.TARGETS[args.platform][:2], 'Static compilation is hosted-only on matching platform')
    inspect_sources(lock,args.sources)
    source=extract_source(args.sources/lock['sources']['gmp']['path'],args.output/'source')
    prefix=(args.output/'prefix').resolve();build_dir=args.output/'build';build_dir.mkdir()
    compiler=args.compiler.resolve(strict=True);make=args.make.resolve(strict=True)
    plan=build_plan(args.platform,source,prefix,compiler,make);environment=dict(os.environ,**plan['environment'])
    from importlib import import_module
    pipeline=import_module((__package__+'.' if __package__ else '')+'prebuilt_release_pipeline')
    commands=[pipeline.run(command,cwd=build_dir,environment=environment,log=args.output/f'command-{i}.log',timeout=1800) for i,command in enumerate(plan['commands'])]
    receipt={'schema_version':'biocompiler.static_gmp_build.v1','source':lock['sources']['gmp'],'plan':plan,'commands':commands,
        'compiler':{'path':str(compiler),**materials.digest(compiler.read_bytes())},'make':{'path':str(make),**materials.digest(make.read_bytes())},
        'archive':materials.digest((prefix/'lib/libgmp.a').read_bytes()),'header':materials.digest((prefix/'include/gmp.h').read_bytes())}
    (args.output/'build.json').write_bytes(release.canonical(receipt))
    # Feed the real installed static archive through the reviewed pkg-config probe.
    env=dict(environment,PKG_CONFIG_PATH=str(prefix/'lib/pkgconfig'),PKG_CONFIG_LIBDIR=str(prefix/'lib/pkgconfig'))
    subprocess.run([sys.executable,str(ROOT/'tools/prepare_static_gmp.py'),'--pkg-config',str(args.pkg_config.resolve()),
        '--output',str(args.output/'configuration')],check=True,env=env)


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='operation',required=True)
    download=commands.add_parser('fetch');download.add_argument('--output',type=Path,required=True)
    compile=commands.add_parser('static-build')
    for name in ('sources','output','compiler','make','pkg-config'):compile.add_argument('--'+name,type=Path,required=True)
    compile.add_argument('--platform',choices=tuple(release.TARGETS),required=True)
    args=parser.parse_args();lock=json.loads(LOCK.read_bytes())
    if args.operation=='fetch':
        require(not args.output.exists(),'Source capture root already exists');args.output.mkdir(parents=True)
        for row in lock['sources'].values():fetch(row['url'],row,args.output/row['path'])
        (args.output/'source-receipt.json').write_bytes(release.canonical(inspect_sources(lock,args.output)))
    else:static_build(args,lock)


if __name__=='__main__':
    import sys
    main()

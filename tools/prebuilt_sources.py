"""Fetch exact official/locked sources and prepare one hosted portable GMP build.

Fetch/inspect are source-only. The separate static-build operation is authorized
only on the matching hosted runner; local controls never invoke it.
"""
from __future__ import annotations
import argparse
import errno
import http.client
import hashlib
import json
import math
import os
from pathlib import Path,PurePosixPath
import platform
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
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


# Mirrors are transport alternatives, never new source authority. The sole
# fallback was source-only verified against the unchanged locked GMP bytes.
REVIEWED_URLS = {
    'digestif': 'https://github.com/mirage/digestif/releases/download/v1.3.0/digestif-1.3.0.tbz',
    'dune': 'https://github.com/ocaml/dune/releases/download/3.20.2/dune-3.20.2.tbz',
    'eqaf': 'https://github.com/mirage/eqaf/releases/download/v0.10/eqaf-0.10.tbz',
    'gmp': 'https://ftp.gnu.org/gnu/gmp/gmp-6.3.0.tar.xz',
    'ocaml-compiler': 'https://github.com/ocaml/ocaml/releases/download/5.4.0/ocaml-5.4.0.tar.gz',
    'ocamlfind': 'https://github.com/ocaml/ocamlfind/archive/refs/tags/findlib-1.9.8.tar.gz',
    'zarith': 'https://github.com/ocaml/Zarith/archive/release-1.14.tar.gz',
}
FALLBACKS = {REVIEWED_URLS['gmp']: ('https://mirrors.kernel.org/gnu/gmp/gmp-6.3.0.tar.xz',)}
ATTEMPTS_PER_URL = 2
SOCKET_TIMEOUT = 12
STREAM_DEADLINE = 30
FETCH_SCHEMA = 'biocompiler.prebuilt_source_fetch.v1'
SOURCE_MTIME_MAX = 2**32 - 1


class FetchError(RuntimeError):
    """Sanitized failure; raw upstream errors may contain signed redirect URLs."""


def secure_url(url):
    require(type(url) is str and len(url) <= 16384, 'Invalid source URL')
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == 'https' and bool(parsed.hostname) and parsed.username is None
            and parsed.password is None and parsed.port in (None, 443), 'Source redirect or URL is not credential-free HTTPS')
    return parsed


def public_url(url):
    parsed = secure_url(url)
    # GitHub's release redirect has a signed query. Never log that query.
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))


class HttpsRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        secure_url(newurl)
        return super().redirect_request(request, response, code, message, headers, newurl)


def error_summary(error):
    reason = getattr(error, 'reason', error)
    result = {'type': type(error).__name__, 'reason_type': type(reason).__name__}
    if isinstance(error, urllib.error.HTTPError):
        result['http_status'] = error.code
    if type(getattr(reason, 'errno', None)) is int:
        result['errno'] = reason.errno
    return result


def network_failure(error):
    if isinstance(error, urllib.error.HTTPError):
        return error.code in (408, 429, 500, 502, 503, 504)
    reason = getattr(error, 'reason', error)
    if isinstance(reason, ssl.SSLError):
        return False
    if isinstance(reason, (TimeoutError, socket.gaierror, ConnectionError, http.client.RemoteDisconnected)):
        return True
    return isinstance(reason, OSError) and reason.errno in {
        errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ETIMEDOUT, errno.ECONNRESET,
        errno.ECONNREFUSED, errno.ECONNABORTED, errno.EPIPE,
    }


def fetch_once(url, pin, output):
    secure_url(url)
    require(not output.exists() and not output.is_symlink(), 'Source destination already exists')
    temporary = output.with_suffix(output.suffix + '.part')
    require(not temporary.exists() and not temporary.is_symlink(), 'Source partial destination already exists')
    size = 0; digest = hashlib.sha256(); created = False
    started = time.monotonic()
    try:
        opener = urllib.request.build_opener(HttpsRedirect())
        with opener.open(url, timeout=SOCKET_TIMEOUT) as response:
            final_url = public_url(response.geturl())
            with temporary.open('xb') as stream:
                created = True
                while True:
                    require(time.monotonic() - started <= STREAM_DEADLINE, 'Source stream exceeded its elapsed-time allowance')
                    chunk = response.read1(min(65536, pin['size'] + 1 - size))
                    require(time.monotonic() - started <= STREAM_DEADLINE, 'Source stream exceeded its elapsed-time allowance')
                    if not chunk:
                        break
                    size += len(chunk)
                    require(size <= pin['size'], 'Upstream source exceeds exact pinned size')
                    digest.update(chunk); stream.write(chunk)
        require(size == pin['size'] and digest.hexdigest() == pin['sha256'], 'Upstream source bytes differ from locked checksum')
        # Atomic no-replace publication: a destination appearing during fetch is
        # never overwritten. Both paths are in the same source directory.
        os.link(temporary, output)
        return {'url': url, 'final_url': final_url, 'sha256': digest.hexdigest(), 'size': size}
    finally:
        if created:
            temporary.unlink(missing_ok=True)


def fetch(url, pin, output, *, source=None, notify=None):
    require(url in REVIEWED_URLS.values(), 'Source URL is outside the reviewed locked URL inventory')
    require(type(pin.get('size')) is int and 0 < pin['size'] <= 64 * 1024 * 1024
            and type(pin.get('sha256')) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256']), 'Invalid locked source byte pin')
    require(not output.exists() and not output.is_symlink(), 'Source download requires a fresh path')
    source = source or next(name for name, selected in REVIEWED_URLS.items() if selected == url)
    require(REVIEWED_URLS.get(source) == url, 'Named source differs from its reviewed URL')
    def publish(record):
        print(json.dumps({'source': source, **record}, sort_keys=True), flush=True)
        if notify is not None:
            notify({'source': source, **record})
    urls = (url, *FALLBACKS.get(url, ()))
    for ordinal in range(1, ATTEMPTS_PER_URL + 1):
        for selected in urls:
            record = {'url': selected, 'attempt': ordinal, 'status': 'started'}
            publish(record)
            try:
                value = fetch_once(selected, pin, output)
            except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException) as error:
                retry = network_failure(error)
                record.update(status='network_error' if retry else 'rejected', error=error_summary(error))
                publish(record)
                if isinstance(error, urllib.error.HTTPError):
                    error.close()
                if not retry:
                    raise FetchError('Locked source rejected: ' + source + ' (' + type(error).__name__ + ')') from None
                if ordinal < ATTEMPTS_PER_URL and selected == urls[-1]:
                    time.sleep(0.25)
            else:
                record.update(status='verified', sha256=value['sha256'], size=value['size'], final_url=value['final_url'])
                publish(record)
                return {'source': source, 'selected_url': selected, 'attempt': ordinal, **value}
    raise FetchError('All bounded source network attempts failed: ' + source) from None


def fetch_sources(lock, output):
    require(not output.exists() and not output.is_symlink(), 'Source capture root already exists')
    require(set(lock['sources']) == set(REVIEWED_URLS) and all(row['url'] == REVIEWED_URLS[name]
            and Path(row['path']).name == row['path'] for name, row in lock['sources'].items()),
            'Locked source URL/path inventory differs from reviewed inputs')
    output.mkdir(parents=True)
    receipt = {'schema_version': FETCH_SCHEMA, 'status': 'running', 'lock_sha256': release.sha(release.canonical(lock)),
               'limits': {'attempts_per_url': ATTEMPTS_PER_URL, 'socket_timeout_seconds': SOCKET_TIMEOUT,
                          'stream_deadline_seconds': STREAM_DEADLINE},
               'sources': {name: {key: row[key] for key in ('url', 'path', 'sha256', 'size')} for name, row in lock['sources'].items()},
               'attempts': [], 'completed': {}}
    receipt_path = output / 'fetch-receipt.json'
    def save():
        temporary = output / 'fetch-receipt.json.part'
        temporary.write_bytes(release.canonical(receipt)); temporary.replace(receipt_path)
    def notice(record):
        rows = receipt['attempts']
        if record['status'] == 'started':
            rows.append(record)
        else:
            require(rows and all(rows[-1][key] == record[key] for key in ('source', 'url', 'attempt')),
                    'Fetch result is detached from its recorded attempt')
            rows[-1] = record
        save()
    save()
    try:
        for name, row in lock['sources'].items():
            receipt['completed'][name] = fetch(row['url'], row, output / row['path'], source=name, notify=notice)
            save()
        (output / 'source-receipt.json').write_bytes(release.canonical(inspect_sources(lock, output)))
    except BaseException as error:
        receipt.update(status='failed', error=error_summary(error)); save()
        raise
    receipt['status'] = 'complete'; save()
    return receipt


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
            require(type(member.mtime) in (int,float) and 0<=member.mtime<=SOURCE_MTIME_MAX
                and math.isfinite(member.mtime),'Source archive timestamp is outside bound')
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
        regulars={PurePosixPath(m.name) for m in members if m.isfile()}
        require(all(PurePosixPath(m.linkname) in regulars for m in members if m.islnk()),
            'Source hardlink target is not an indexed regular member')
        for member in members:
            target=output/member.name
            if member.isdir():target.mkdir(parents=True,exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True,exist_ok=True)
                with archive.extractfile(member) as source,target.open('xb') as dest:shutil.copyfileobj(source,dest,1024*1024)
                target.chmod(0o755 if member.mode&0o111 else 0o644)
                # Release archives contain generated files whose dependency age
                # must survive extraction rather than follow archive write order.
                os.utime(target,(member.mtime,member.mtime),follow_symlinks=False)
        for member in members:
            target=output/member.name
            if member.issym():target.parent.mkdir(parents=True,exist_ok=True);target.symlink_to(member.linkname)
            elif member.islnk():
                source=output/member.linkname
                require(source.is_file() and not source.is_symlink(),'Source hardlink target is not a regular member')
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
                os.utime(target,(member.mtime,member.mtime),follow_symlinks=False)
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
        fetch_sources(lock,args.output)
    else:static_build(args,lock)


if __name__=='__main__':
    import sys
    main()

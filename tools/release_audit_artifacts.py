"""Bounded inert access to exact-run artifact ZIPs; never executes contents."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import shutil
import stat
import zipfile

MAX_ARCHIVE = 640 * 1024**2
MAX_EXPANDED = 4 * 1024**3
MAX_MEMBER = 512 * 1024**2
MAX_ALL_COMPRESSED = 4 * 1024**3
MAX_ALL_EXPANDED = 20 * 1024**3
MAX_EXTRACTED = 2560 * 1024**2


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def decode(raw):
    def unique(items):
        value = {}
        for key, item in items:
            require(key not in value, 'Duplicate JSON key: ' + key)
            value[key] = item
        return value
    def invalid(value):
        raise AssertionError('Nonfinite JSON: ' + value)
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def read_json(path, maximum=64 * 1024**2):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= maximum, 'Unsafe or oversized JSON: ' + str(path))
    return decode(path.read_bytes())


class ArtifactStore:
    def __init__(self, *, metadata, paths, required, run, head, started_at):
        require(set(required) <= set(metadata) and set(required) <= set(paths), 'Missing required artifact download or metadata')
        self.archives = {}; self.proof = []; self.extracted = 0
        compressed_total = expanded_total = 0
        for name in sorted(required):
            meta, path = metadata[name], Path(paths[name])
            require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= MAX_ARCHIVE, 'Missing or oversized archive: ' + name)
            require(meta['name'] == name and not meta['expired'] and meta['workflow_run']['id'] == run and meta['workflow_run']['head_sha'] == head and meta['created_at'] >= started_at, 'Stale or foreign artifact: ' + name)
            require(path.stat().st_size == meta['size_in_bytes'] and 'sha256:' + sha(path) == meta['digest'], 'Artifact ZIP bytes differ: ' + name)
            compressed_total += path.stat().st_size
            archive = zipfile.ZipFile(path)
            entries = archive.infolist(); all_names = [entry.filename for entry in entries]
            require(0 < len(entries) <= 300000 and len(set(all_names)) == len(all_names), 'Duplicate or oversized ZIP census: ' + name)
            expanded = sum(entry.file_size for entry in entries); expanded_total += expanded
            require(expanded <= MAX_EXPANDED and compressed_total <= MAX_ALL_COMPRESSED and expanded_total <= MAX_ALL_EXPANDED, 'Prepared archive budget exceeded; review actual sizes, never omit required evidence')
            for entry in entries:
                relative = PurePosixPath(entry.filename)
                require(relative.parts and relative.as_posix() == entry.filename.rstrip('/') and not relative.is_absolute() and '..' not in relative.parts and '\\' not in entry.filename and not entry.flag_bits & 1 and not stat.S_ISLNK(entry.external_attr >> 16) and entry.file_size <= MAX_MEMBER, 'Unsafe ZIP member: ' + entry.filename)
            self.archives[name] = archive
            self.proof.append({'name': name, 'id': meta['id'], 'zip_sha256': meta['digest'].removeprefix('sha256:'), 'compressed_bytes': path.stat().st_size, 'declared_expanded_bytes': expanded, 'members': len(entries)})

    def names(self, artifact):
        return {entry.filename for entry in self.archives[artifact].infolist() if not entry.is_dir()}

    def read(self, artifact, name, maximum=128 * 1024**2):
        archive = self.archives[artifact]; entry = archive.getinfo(name)
        require(not entry.is_dir() and entry.file_size <= maximum, 'Selected member exceeds inspection bound: ' + artifact + '/' + name)
        raw = archive.read(entry)
        require(len(raw) == entry.file_size, 'ZIP member truncated')
        return raw

    def json(self, artifact, name, maximum=64 * 1024**2):
        return decode(self.read(artifact, name, maximum))

    def extract(self, artifact, destination, names=None, *, allow_identical_existing=False):
        destination = Path(destination)
        wanted = self.names(artifact) if names is None else set(names)
        require(wanted <= self.names(artifact), 'Missing selected extraction members')
        destination.mkdir(parents=True, exist_ok=True)
        for name in sorted(wanted):
            archive = self.archives[artifact]; entry = archive.getinfo(name)
            target = destination / name
            require(not target.is_symlink() and target.is_relative_to(destination), 'Unsafe extraction destination')
            if target.exists():
                require(allow_identical_existing and target.is_file() and target.stat().st_size == entry.file_size, 'Unexpected extraction overlap')
                with archive.open(entry) as source:
                    require(hashlib.file_digest(source, 'sha256').hexdigest() == sha(target), 'Merged workflow artifact member bytes differ')
                continue
            self.extracted += entry.file_size
            require(self.extracted <= MAX_EXTRACTED, 'Prepared extraction budget exceeded')
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as source, target.open('xb') as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            require(target.stat().st_size == entry.file_size, 'Extracted byte size differs')
            target.chmod(0o600)
        return destination

    def close(self):
        for archive in self.archives.values():
            archive.close()

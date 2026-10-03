"""Bounded Python reconstruction peer for already validated native receipts.

This peer performs no compilation, checking or acceptance. It emits only retained
server bytes after the current client emits each exact retained client frame.
Real executable/process/source evidence must be validated independently before
using this mechanical reconstruction as evidence of Python object identities.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from unittest.mock import patch
from uuid import UUID


SCHEMA = 'biocompiler.reference_transcript_reconstruction.v1'
MAX_FRAME = 32 * 1024 * 1024
MAX_SESSION = 256 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_PROCESSES = 128
MAX_FRAMES = 1_000_000
MAX_INDEX = 128 * 1024


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def executable_source(*, interpreter, source, source_sha256, directory, index_sha256):
    require(all(type(value) is str and Path(value).is_absolute() and '\n' not in value
        for value in (interpreter, source, directory)), 'Transcript executable origin path is malformed')
    require(all(type(value) is str and len(value) == 64 and all(char in '0123456789abcdef' for char in value)
        for value in (source_sha256, index_sha256)), 'Transcript executable origin hash is malformed')
    return ('#!' + interpreter + '\nimport hashlib, pathlib, runpy\n'
        + 'source = pathlib.Path(' + repr(source) + ')\n'
        + 'assert hashlib.sha256(source.read_bytes()).hexdigest() == ' + repr(source_sha256) + '\n'
        + 'runpy.run_path(str(source), init_globals={"TRANSCRIPT_DIRECTORY": ' + repr(directory)
        + ', "TRANSCRIPT_INDEX_SHA256": ' + repr(index_sha256) + '}, run_name="__main__")\n').encode()


def validate_executable(raw, origin, *, source_path, source_sha256, index_sha256):
    require(type(origin) is dict and set(origin) == {'interpreter', 'source', 'source_sha256', 'directory', 'index_sha256'}
        and origin['source'] == source_path and origin['source_sha256'] == source_sha256
        and origin['index_sha256'] == index_sha256
        and type(origin['directory']) is str and Path(origin['directory']).name.startswith('reference-transcript-'),
        'Saved peer source/runtime origin differs')
    require(raw == executable_source(**origin),
            'Saved peer executable differs from the exact current source-bound wrapper')


def body(raw):
    require(type(raw) is bytes and 9 < len(raw) <= MAX_FRAME + 9 and raw[8:9] == b'\n'
        and all(value in b'0123456789abcdef' for value in raw[:8]), 'Invalid retained transcript frame')
    size = int(raw[:8], 16)
    require(size == len(raw) - 9, 'Retained transcript frame length differs')
    value = json.loads(raw[9:])
    require(type(value) is dict and canonical(value) == raw[9:], 'Retained frame is not canonical JSON')
    return value


def checked_file(directory, name, size, identity):
    require(type(name) is str and name == Path(name).name and name not in ('', '.', '..'),
            'Transcript member escaped its directory')
    path = directory / name
    info = path.lstat()
    require(type(size) is int and type(identity) is str and len(identity) == 64 and
            stat.S_ISREG(info.st_mode) and info.st_size == size and 0 < size <= MAX_SESSION,
            'Transcript member is missing, linked, oversized or changed')
    with path.open('rb') as stream:
        require(hashlib.file_digest(stream, 'sha256').hexdigest() == identity, 'Transcript member bytes changed')
    return path


class TranscriptPeer:
    """Temporary, explicitly nonnative peer plus a scoped recorded-nonce supply.

    Each process is represented by a complete ordered list of
    ``(client|server, actual_framed_bytes)``. No expected biological documents or
    results are accepted by this API. The surrounding campaign owns validation
    of the real native provenance and the semantic original-oracle comparison.
    """
    def __init__(self, processes):
        require(type(processes) is list and 0 < len(processes) <= MAX_PROCESSES,
                'Transcript process census is outside its bound')
        self.processes, self.nonces, self.members = [], [], []
        total = 0
        for rows in processes:
            require(type(rows) is list and 0 < len(rows) <= MAX_FRAMES, 'Transcript frame census is outside its bound')
            require(rows[0][0] == 'client', 'Transcript does not begin with client hello')
            initial = body(rows[0][1])
            nonce = initial.get('session_id')
            parsed = UUID(nonce)
            require(parsed.version == 4 and str(parsed) == nonce and nonce not in self.nonces
                and initial.get('kind') == 'hello' and initial.get('sequence') == 0,
                'Transcript nonce or first hello differs')
            size = 0
            for direction, raw in rows:
                require(direction in ('client', 'server'), 'Unknown transcript direction')
                require(body(raw).get('session_id') == nonce, 'Transcript crosses native sessions')
                size += 1 + len(raw)
            require(size <= MAX_SESSION, 'Transcript lifetime bytes exceed bound')
            total += size
            require(total <= MAX_TOTAL, 'Transcript complete bytes exceed bound')
            self.processes.append(tuple(rows)); self.nonces.append(nonce)
        self.scope = None
        self.directory = None
        self.executable = None
        self.executable_sha256 = None
        self.nonce_calls = 0

    def __enter__(self):
        self.scope = tempfile.TemporaryDirectory(prefix='reference-transcript-')
        self.directory = Path(self.scope.__enter__())
        try:
            for number, rows in enumerate(self.processes):
                raw = b''.join((b'C' if direction == 'client' else b'S') + raw for direction, raw in rows)
                path = self.directory / (str(number) + '.frames')
                path.write_bytes(raw)
                self.members.append({'path': path.name, 'bytes': len(raw), 'sha256': sha(raw),
                    'frames': len(rows), 'nonce': self.nonces[number]})
            index = canonical({'schema': SCHEMA, 'members': self.members})
            require(len(index) <= MAX_INDEX, 'Transcript index exceeds its bound')
            (self.directory / 'index.json').write_bytes(index)
            source = Path(__file__).resolve()
            self.origin = {'interpreter': sys.executable, 'source': str(source), 'source_sha256': sha(source.read_bytes()),
                'directory': str(self.directory), 'index_sha256': sha(index)}
            executable = executable_source(**self.origin)
            self.executable = self.directory / 'recorded-peer'
            self.executable.write_bytes(executable)
            self.executable.chmod(0o700)
            self.executable_sha256 = sha(executable)
            return self
        except BaseException:
            self.scope.__exit__(*sys.exc_info())
            raise

    def __exit__(self, *error):
        require(self.scope is not None, 'Transcript peer was not entered')
        self.scope.__exit__(*error)

    def _nonce(self):
        require(self.nonce_calls < len(self.nonces), 'Transcript reconstruction created an extra process')
        result = UUID(self.nonces[self.nonce_calls])
        self.nonce_calls += 1
        return result

    @contextmanager
    def recorded_nonces(self):
        from biocompiler import core_pipeline_callback_session as transport
        previous = transport.uuid4
        require(self.nonce_calls == 0, 'Recorded nonces cannot be replayed twice')
        with patch.object(transport, 'uuid4', self._nonce):
            try:
                yield
            finally:
                require(transport.uuid4 == self._nonce, 'Reconstruction nonce source was replaced')
        require(transport.uuid4 is previous, 'Reconstruction nonce scope was not restored')
        require(self.nonce_calls == len(self.nonces), 'Transcript reconstruction omitted a process')

    def evidence(self, sessions):
        from biocompiler.core_pipeline_callback_session import CorePipelineCallbackSession
        require(self.nonce_calls == len(self.nonces), 'Transcript process consumption is incomplete')
        require(type(sessions) is list and len(sessions) == len(self.processes),
                'Transcript completed process census differs')
        seen, completed = set(), []
        for number, (session, expected) in enumerate(zip(sessions, self.processes)):
            require(type(session) is CorePipelineCallbackSession and type(session.pid) is int and
                session.pid > 0 and session.pid not in seen, 'Transcript reconstructed process is missing or repeated')
            seen.add(session.pid)
            require(session.closed and not session.invalidated and session.returncode == 0 and
                session.stderr_bytes == b'' and session.executable_sha256 == self.executable_sha256,
                'Transcript reconstructed process did not completely finish its exact peer')
            require(tuple((row.direction, row.frame) for row in session.traffic) == expected,
                'Transcript reconstructed process traffic differs from its complete tape')
            completed.append({'tape': number, 'pid': session.pid, 'returncode': session.returncode,
                              'frames': len(session.traffic), 'executable_sha256': session.executable_sha256})
        return {'schema': SCHEMA, 'native_execution': False, 'processes': self.members,
            'peer_sha256': self.executable_sha256, 'python': sys.version, 'completed_processes': completed,
            'origin': self.origin,
            'scope': 'current client/callback object reconstruction from independently validated real-native frame bytes'}


def read_exact(stream, count):
    result = bytearray()
    while len(result) < count:
        chunk = stream.read(count - len(result))
        require(bool(chunk), 'Transcript stream ended before its exact frame')
        result.extend(chunk)
    return bytes(result)


def read_frame(stream):
    header = read_exact(stream, 9)
    require(header[8:] == b'\n' and all(value in b'0123456789abcdef' for value in header[:8]),
            'Transcript client emitted an invalid header')
    size = int(header[:8], 16)
    require(0 < size <= MAX_FRAME, 'Transcript client frame exceeds bound')
    return header + read_exact(stream, size)


def worker(directory, index_sha256):
    require(sys.argv[1:] == ['--pipeline-callback-session-v1'], 'Transcript peer received different arguments')
    directory = Path(directory)
    index_file = directory / 'index.json'
    require(index_file.is_file() and not index_file.is_symlink() and index_file.stat().st_size <= MAX_INDEX,
            'Transcript index is missing, linked or oversized')
    raw = index_file.read_bytes()
    require(sha(raw) == index_sha256, 'Transcript index bytes changed')
    index = json.loads(raw)
    require(canonical(index) == raw and set(index) == {'schema', 'members'} and index['schema'] == SCHEMA
        and type(index['members']) is list and 0 < len(index['members']) <= MAX_PROCESSES, 'Unknown transcript index')
    first = read_frame(sys.stdin.buffer)
    nonce = body(first).get('session_id')
    matches = [member for member in index['members'] if member['nonce'] == nonce]
    require(len(matches) == 1, 'Transcript client selected an unknown or repeated nonce')
    member = matches[0]
    require(set(member) == {'path', 'bytes', 'sha256', 'frames', 'nonce'}
        and type(member['frames']) is int and 0 < member['frames'] <= MAX_FRAMES, 'Invalid transcript member')
    path = checked_file(directory, member['path'], member['bytes'], member['sha256'])
    with path.open('rb') as tape:
        for number in range(member['frames']):
            direction = read_exact(tape, 1)
            require(direction in (b'C', b'S'), 'Transcript frame direction changed')
            expected = read_frame(tape)
            if direction == b'C':
                actual = first if number == 0 else read_frame(sys.stdin.buffer)
                require(actual == expected, 'Current client frame differs from recorded native execution at frame ' + str(number))
            else:
                require(number > 0, 'Transcript began with server output')
                sys.stdout.buffer.write(expected)
                sys.stdout.buffer.flush()
        require(tape.read(1) == b'', 'Transcript contains extra unclaimed frames')
    require(sys.stdin.buffer.read(1) == b'', 'Current client emitted extra traffic after transcript exhaustion')


if __name__ == '__main__':
    require('TRANSCRIPT_DIRECTORY' in globals() and 'TRANSCRIPT_INDEX_SHA256' in globals(),
            'Transcript worker requires its explicitly generated bounded wrapper')
    worker(globals()['TRANSCRIPT_DIRECTORY'], globals()['TRANSCRIPT_INDEX_SHA256'])

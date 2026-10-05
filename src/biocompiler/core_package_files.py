"""Private inherited archive descriptors. Transport identity is not acceptance."""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import os
import re
import stat
import tempfile
import threading
from typing import Any, BinaryIO

from biocompiler.core_artifacts import _input_file
from biocompiler.core_client import CoreProtocolError, CoreUnavailable

MAX_ARCHIVE_BYTES = 67_108_864
ARGUMENT = '--reference-package-fds-v1'


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CoreProtocolError(message)


class PackageFiles:
    """One private input/output pair owned by this thread/process and launch.

    Bytes may be read only after the caller validates the complete protocol
    response. The returned bytes still require both the independent checker and
    current reconstruction receipts before public export can be authorized.
    """

    def __init__(self, archive: bytes | None, *, max_archive_bytes: int = MAX_ARCHIVE_BYTES):
        if os.name != 'posix':
            raise CoreUnavailable('Package descriptors currently require POSIX')
        _require(type(max_archive_bytes) is int and 0 < max_archive_bytes <= MAX_ARCHIVE_BYTES,
            'Package archive ceiling requires a positive reduction')
        _require(archive is None or (type(archive) is bytes and 0 < len(archive) <= max_archive_bytes),
            'Package input is empty or exceeds its declared byte bound')
        self.maximum = max_archive_bytes
        self._pid, self._thread = os.getpid(), threading.current_thread()
        self._closed = self._claimed = self._invalid = self._consumed = False
        self._stack = ExitStack()
        self._input: BinaryIO | None = None
        try:
            if archive is not None:
                self._input = self._stack.enter_context(_input_file(archive))
            self._output = self._stack.enter_context(tempfile.TemporaryFile(mode='w+b'))
            self._output_identity = self._identity(self._output)
            self._input_identity = None if self._input is None else self._identity(self._input)
            self._descriptor = None if archive is None else {
                'bytes': len(archive), 'sha256': hashlib.sha256(archive).hexdigest()}
            self.monitor()
        except BaseException:
            self._stack.close()
            self._closed = True
            raise

    @staticmethod
    def _identity(stream: BinaryIO) -> tuple[int, int]:
        details = os.fstat(stream.fileno())
        _require(stat.S_ISREG(details.st_mode), 'Package transport requires regular files')
        return details.st_dev, details.st_ino

    def _owner(self) -> None:
        _require(os.getpid() == self._pid and threading.current_thread() is self._thread,
            'Package descriptors belong to their creating thread and process')
        _require(not self._closed and not self._invalid, 'Package descriptors are closed or invalidated')

    def monitor(self) -> None:
        self._owner()
        _require(self._identity(self._output) == self._output_identity,
            'Private package output descriptor changed')
        details = os.fstat(self._output.fileno())
        _require(details.st_mode & 0o077 == 0 and details.st_nlink <= 1
            and details.st_size <= self.maximum, 'Private package output exceeded its mode or byte bounds')
        if self._input is not None:
            _require(self._identity(self._input) == self._input_identity
                and self._descriptor is not None
                and os.fstat(self._input.fileno()).st_size == self._descriptor['bytes'],
                'Private package input descriptor changed')

    @property
    def input_descriptor(self) -> dict[str, Any] | None:
        self._owner()
        return None if self._descriptor is None else dict(self._descriptor)

    def claim_launch(self) -> tuple[tuple[str, ...], tuple[int, ...]]:
        self.monitor()
        _require(not self._claimed and os.fstat(self._output.fileno()).st_size == 0,
            'Package descriptors require one launch with empty output')
        self._claimed = True
        source = '-' if self._input is None else str(self._input.fileno())
        descriptors = (() if self._input is None else (self._input.fileno(),)) + (self._output.fileno(),)
        _require(all(value > 2 for value in descriptors) and len(set(descriptors)) == len(descriptors),
            'Package descriptors must be distinct nonstandard numbers')
        return (ARGUMENT, source, str(self._output.fileno())), descriptors

    def read_output(self, descriptor: Any) -> bytes:
        self.monitor()
        _require(self._claimed and not self._consumed, 'Package output must belong to one launched response')
        self._consumed = True
        _require(type(descriptor) is dict and set(descriptor) == {'bytes', 'sha256'}
            and type(descriptor['bytes']) is int and 0 < descriptor['bytes'] <= self.maximum
            and type(descriptor['sha256']) is str
            and re.fullmatch('[0-9a-f]{64}', descriptor['sha256']) is not None,
            'Invalid package output descriptor')
        _require(os.fstat(self._output.fileno()).st_size == descriptor['bytes'],
            'Package output size differs from the completed response')
        self._output.seek(0)
        value = self._output.read(descriptor['bytes'] + 1)
        self.monitor()
        _require(len(value) == descriptor['bytes']
            and os.fstat(self._output.fileno()).st_size == descriptor['bytes']
            and hashlib.sha256(value).hexdigest() == descriptor['sha256'],
            'Package output bytes differ from the completed response')
        return value

    def invalidate(self) -> None:
        _require(os.getpid() == self._pid and threading.current_thread() is self._thread,
            'Cannot invalidate another package descriptor owner')
        self._invalid = True

    def close(self) -> None:
        _require(os.getpid() == self._pid and threading.current_thread() is self._thread,
            'Cannot close another package descriptor owner')
        if not self._closed:
            self._closed = True
            self._stack.close()

    def __enter__(self) -> PackageFiles:
        self._owner()
        return self

    def __exit__(self, kind: Any, value: Any, traceback: Any) -> None:
        self.close()

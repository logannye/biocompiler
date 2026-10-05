"""Byte-only reference callbacks; all manifest, hash and adaptation checks are native."""
from __future__ import annotations

from pathlib import Path
from collections.abc import Callable
from typing import Any, cast

from biocompiler.core_package_owner import PackageBoundaryError
from biocompiler.errors import SerializationError
from biocompiler.registry import reference_builds

_MAX = 16 * 1024 * 1024


class ReferenceReader:
    """One original load/collect call, with reads requested in native source order."""
    def __init__(self, directory: Any):
        self.directory = directory
        self.root: Path | None = None
        self.second_root: Path | None = None
        self.phase = 'new'

    @staticmethod
    def _bounded(path: Path, *, text: bool = False) -> bytes:
        # Keep the second loader's path-resolution policy, but bound the actual
        # read rather than relying on an earlier, raceable stat result.
        with path.open('rb') as stream:
            value = stream.read(_MAX + 1)
        if len(value) > _MAX:
            raise PackageBoundaryError('Reference byte callback exceeded its bounded input size')
        if text:
            # Path.read_text uses universal newline conversion. No JSON parser
            # or manifest constructor is run on the host.
            value = value.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')
        return value

    def read(self, kind: str, name: str) -> bytes:
        try:
            if kind == 'manifest-first' and self.phase == 'new' and name == 'manifest.json':
                self.root = cast(Callable[[Any], Path], reference_builds._directory)(self.directory)
                value = cast(Callable[[Path, str], bytes], reference_builds._read_file)(self.root, name)
                value.decode('utf-8')
                self.phase = 'first'
                return bytes(value)
            if self.root is None:
                raise PackageBoundaryError('Reference read preceded its actual directory initialization')
            if kind == 'retained-first' and self.phase == 'first':
                return bytes(cast(Callable[[Path, str], bytes], reference_builds._read_file)(self.root, name))
            if kind == 'manifest-second' and self.phase == 'first' and name == 'manifest.json':
                value = self._bounded(self.root / name, text=True)
                self.second_root = (self.root / name).parent.resolve()
                self.phase = 'sources'
                return value
            if kind in ('source-second', 'review-second') and self.phase in ('sources', 'reviews'):
                if kind == 'source-second' and self.phase == 'reviews':
                    raise PackageBoundaryError('Reference source read followed review iteration')
                root = self.second_root
                if root is None:
                    raise PackageBoundaryError('Reference second-read root is missing')
                path = (root / name).resolve()
                if not path.is_relative_to(root):
                    raise SerializationError('Source path escapes reference directory.' if kind == 'source-second'
                                             else 'Review evidence path escapes reference directory.')
                if kind == 'review-second':
                    self.phase = 'reviews'
                return self._bounded(path)
            raise PackageBoundaryError('Reference byte callback has a stale or unknown read phase')
        except (OSError, UnicodeError) as error:
            raise SerializationError(f'Cannot read pinned offline reference inputs: {error}') from error

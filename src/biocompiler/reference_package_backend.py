"""Explicit package selection and scoped default-call continuations.

The original public function aliases enter this module through finite prefixes.
No selection discovers a binary, creates acceptance from a view, or falls back to
Python package/check/export semantics after a native failure.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Any

from biocompiler.core_client import CoreClient, JsonValue
from biocompiler.core_pipeline_session import decode_document, encode_document

_SELECTED: ContextVar[PackageRoute | None] = ContextVar('reference_package_core', default=None)
_DEFAULT: ContextVar[tuple[str, Callable[..., Any]] | None] = ContextVar('reference_package_default', default=None)
UNSELECTED = object()


def current() -> PackageRoute | None:
    return _SELECTED.get()


def default(name: str, *args: Any, **kwargs: Any) -> Any:
    selected = _DEFAULT.get()
    if selected is None or selected[0] != name:
        return UNSELECTED
    return selected[1](*args, **kwargs)


@contextmanager
def at_default(name: str, callback: Callable[..., Any]) -> Iterator[None]:
    token = _DEFAULT.set((name, callback))
    try:
        yield
    finally:
        _DEFAULT.reset(token)


@dataclass(frozen=True, eq=False)
class PackageRoute:
    core: CoreClient
    verify: CoreClient
    _limits: bytes

    def prepare(self, alphabet: Any, directory: Any, *, fasta_line_width: Any = 80) -> Any:
        from biocompiler.core_reference_package_route import prepare
        return prepare(self, alphabet, directory, fasta_line_width=fasta_line_width)

    def build(self, request: Any, directory: Any, *, run_metadata: Any = None) -> Any:
        from biocompiler.core_reference_package_route import build
        return build(self, request, directory, run_metadata=run_metadata)

    def reconstruct(self, data: Any, *, expected_request: Any = None, expected_build_fingerprint: Any = None) -> Any:
        from biocompiler.core_reference_package_route import reconstruct
        return reconstruct(self, data, expected_request=expected_request,
                           expected_build_fingerprint=expected_build_fingerprint)

    def publish(self, package: Any, output: Any) -> Any:
        from biocompiler.core_reference_package_route import publish
        return publish(self, package, output)

    def export(self, request: Any, construct: Any, artifact: Any, registry: Any, manifests: Any,
               *, line_width: Any = 80) -> Any:
        from biocompiler.core_reference_package_route import export
        return export(self, request, construct, artifact, registry, manifests, line_width=line_width)

    @property
    def limits(self) -> JsonValue:
        return decode_document(self._limits)


@contextmanager
def reference_package_core(core: CoreClient, verify: CoreClient, *, timeout: float = 120.0,
                           limits: JsonValue = None) -> Iterator[PackageRoute]:
    if type(core) is not CoreClient or core.role != 'core' or type(verify) is not CoreClient or verify.role != 'verify':
        raise TypeError('Package routing requires explicit Core and standalone Verify clients.')
    # Existing explicit executable/digest authority is retained. No PATH or
    # installation search runs here, and timeout validation remains CoreClient's.
    route = PackageRoute(replace(core, timeout_seconds=timeout), replace(verify, timeout_seconds=timeout), encode_document(limits))
    token = _SELECTED.set(route)
    try:
        yield route
    finally:
        _SELECTED.reset(token)

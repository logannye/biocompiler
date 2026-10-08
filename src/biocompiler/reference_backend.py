"""Explicit reference manager selection; this context does not route package export.

The selected Core owns checks and acceptance. Exiting the selection context does
not close the managers returned to callers, and failures never run Python as a
fallback. The original pipeline function signatures and captured aliases remain
unchanged. Public package/export migration has a separate acceptance gate.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from biocompiler.compiler.construct import ConstructBuild
from biocompiler.compiler.molecular import MolecularBuild
from biocompiler.core_client import CoreClient, CoreProtocolError, JsonValue
from biocompiler.core_pipeline_session import decode_document, encode_document
from biocompiler.core_reference_manager import ReferenceCorePassManager
from biocompiler.errors import SerializationError


@dataclass(frozen=True, eq=False)
class _Upstream:
    route: ReferenceRoute
    request: Any
    registry: Any
    snapshot: Mapping[str, Any]


_SELECTED: ContextVar[ReferenceRoute | None] = ContextVar('reference_core_selection', default=None)
_UPSTREAM: ContextVar[_Upstream | None] = ContextVar('reference_core_upstream', default=None)


@dataclass(frozen=True, eq=False)
class ReferenceRoute:
    """One explicit client selection; returned managers have their own lifetimes."""
    core: CoreClient
    _limits: bytes
    _manager_limits: bytes

    def construct(self, request: Any, registry: Any, manifests: Any) -> ConstructBuild:
        upstream = _UPSTREAM.get()
        if (upstream is None or upstream.route is not self or request is not upstream.request
                or registry is not upstream.registry or manifests is not upstream.snapshot):
            return ReferenceCorePassManager.from_construct(self.core, request, registry, manifests,
                limits=decode_document(self._limits), manager_limits=decode_document(self._manager_limits))
        manager = ReferenceCorePassManager._initialize(self.core, request, registry, manifests,
            molecular=True, limits=decode_document(self._limits), manager_limits=decode_document(self._manager_limits),
            _molecular_snapshot=upstream.snapshot)
        return manager._complete_construct()

    def molecular(self, request: Any, registry: Any, manifests: Any) -> MolecularBuild:
        if not isinstance(manifests, Mapping):
            raise SerializationError('Expected a reference manifest mapping.')
        # This is the original outer snapshot and precedes the dynamic upstream
        # global. The selected Construct entry makes its distinct inner snapshot.
        snapshot = MappingProxyType(dict(manifests))
        invocation = _Upstream(self, request, registry, snapshot)
        token = _UPSTREAM.set(invocation)
        try:
            from biocompiler.compiler import molecular
            upstream = molecular.run_construct_pipeline(request, registry, snapshot)
        finally:
            _UPSTREAM.reset(token)
        manager = upstream.manager
        if type(manager) is not ReferenceCorePassManager:
            raise CoreProtocolError('Reference upstream manager has no native authority; Python-manager continuation remains unsupported')
        # The original source observes this manager once. Its later two candidate
        # reads remain deferred to native final-check and return boundaries.
        return manager.complete_molecular_public(upstream, request, registry, snapshot)



def current() -> ReferenceRoute | None:
    """Read only the selection in this context; never discover a default binary."""
    return _SELECTED.get()


@contextmanager
def reference_core(core: CoreClient, *, limits: JsonValue = None,
                   manager_limits: JsonValue = None) -> Iterator[ReferenceRoute]:
    """Select an explicit Core for the existing Construct/Molecular SDK calls.

    Selection is scoped to this ContextVar and restores on all exits. Keep and
    close returned Build.manager objects explicitly after their last use. This
    context does not advertise native package/export authority.
    """
    if not isinstance(core, CoreClient):
        raise TypeError('Reference native routing requires an explicit CoreClient.')
    route = ReferenceRoute(core, encode_document(limits), encode_document(manager_limits))
    token = _SELECTED.set(route)
    try:
        yield route
    finally:
        _SELECTED.reset(token)

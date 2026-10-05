"""One private package session; never attaches a larger owner to an old manager."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from biocompiler.core_client import CoreClient, CoreProtocolError, JsonValue
from biocompiler.core_package_files import PackageFiles
from biocompiler.core_pipeline_callback_session import CorePipelineCallbackSession, _BROKER_ACTIONS
from biocompiler.core_pipeline_session import encode_document
from biocompiler.pipeline_callback_objects import CallbackObjects, HostCompletion

_ACTIVE: ContextVar[PackageOwner | None] = ContextVar('reference_package_owner', default=None)


class PackageBoundaryError(CoreProtocolError):
    """Private adapter violation; user callback exceptions remain opaque values."""


def current() -> PackageOwner | None:
    return _ACTIVE.get()


class PackageOwner:
    def __init__(self, core: CoreClient, *, files: PackageFiles, application: JsonValue,
                 actions: tuple[str, ...], handler: Callable[[str, JsonValue], JsonValue],
                 limits: JsonValue = None):
        from biocompiler.core_reference_manager import ReferenceCorePassManager
        self.core, self.files, self.handler = core, files, handler
        self.objects = CallbackObjects()
        self.manager: Any = None
        self._requested: Any = None
        self._active = 0
        self.actions = frozenset(actions)
        allowed = _BROKER_ACTIONS + ReferenceCorePassManager._EXTRA_ACTIONS + actions
        self.session = CorePipelineCallbackSession(core, application=application, objects=self.objects,
            limits=limits, allowed_actions=allowed, invocation_handler=self._invoke, _package_files=files)

    def _invoke(self, action: str, arguments: JsonValue) -> HostCompletion:
        if action not in self.actions:
            if self.manager is None:
                raise PackageBoundaryError('Manager callback arrived before package-owned initialization')
            return self.manager._invoke(action, arguments)  # type: ignore[no-any-return]
        try:
            value = self.handler(action, arguments)
        except PackageBoundaryError:
            raise
        except BaseException as exception:
            return self.objects._capture(exception)
        return HostCompletion('ok', encode_document(value, max_bytes=self.objects.limits.max_document_bytes,
            max_nodes=self.objects.limits.max_document_nodes))

    def objects_for(self, manager: Any, core: CoreClient, application: JsonValue) -> CallbackObjects:
        from biocompiler.core_reference_manager import ReferenceCorePassManager
        from biocompiler.core_pipeline_manager import capability_profile
        if (current() is not self or self._active != 1 or type(manager) is not ReferenceCorePassManager
                or core is not self.core or self.manager is not None or self._requested is not None
                or encode_document(application) != encode_document(capability_profile())):
            raise PackageBoundaryError('Package manager initialization changed its exact owner or class')
        self.objects.counts
        self._requested = manager
        return self.objects

    def bind(self, manager: Any) -> CorePipelineCallbackSession:
        if current() is not self or self._requested is not manager or self.manager is not None:
            raise PackageBoundaryError('Package manager initialization is absent or repeated')
        self.manager = manager
        self._requested = None
        return self.session

    @contextmanager
    def initialize(self) -> Iterator[None]:
        if current() is not None or self.manager is not None or self._active:
            raise PackageBoundaryError('Package manager must be initialized once on its original owner')
        self._active = 1
        token = _ACTIVE.set(self)
        try:
            yield
        finally:
            _ACTIVE.reset(token)
            self._active = 0

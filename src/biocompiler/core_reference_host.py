"""Source-bound authoring callbacks for the native reference pipelines.

This module does not generate or check a construct or molecular artifact. The
unchanged producer functions are identity witnesses only and are never called.
Actual replacements execute as untrusted proposals, preserving their ordinary
Python argument, output and exception identities.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import importlib
from pathlib import Path
import sys
from types import CodeType, FunctionType, MappingProxyType, ModuleType
from typing import Any

import biocompiler
from biocompiler.artifacts.provenance import SourceLink
from biocompiler.compiler.passes import PassResult
from biocompiler.core_client import CoreProtocolError
from biocompiler.ir.molecular import (
    EncodingEvidencePolicy, EncodingPolicy, MolecularArtifact, MolecularRecord,
    TranslationPolicy,
)


def _require(value: bool, message: str) -> None:
    if not value:
        raise CoreProtocolError(message)


@dataclass(frozen=True)
class _Default:
    module: ModuleType
    function: FunctionType
    path: Path
    sha256: str
    name: str
    code: CodeType

    def verify(self) -> None:
        namespace = vars(self.module)
        qualified = 'biocompiler.' + self.path.relative_to(_PACKAGE).with_suffix('').as_posix().replace('/', '.')
        _require(sys.modules.get(qualified) is self.module
            and namespace.get('__name__') == qualified
            and namespace.get('__package__') == qualified.rpartition('.')[0]
            and Path(namespace.get('__file__', '')).resolve() == self.path,
            'Reference default module origin differs')
        _require(hashlib.sha256(self.path.read_bytes()).hexdigest() == self.sha256,
            'Reference default source bytes differ')
        function = self.function
        _require(function.__globals__ is namespace and function.__module__ == qualified
            and function.__name__ == self.name and function.__qualname__ == self.name
            and function.__code__ == self.code
            and function.__code__.co_filename == str(self.path)
            and function.__defaults__ is None and function.__kwdefaults__ is None
            and function.__closure__ is None,
            'Reference default code or globals differ')


_PACKAGE = Path(biocompiler.__file__).resolve().parent


def _default(suffix: str, name: str, pin: str) -> _Default:
    module = importlib.import_module('biocompiler.' + suffix)
    path = _PACKAGE / (suffix.replace('.', '/') + '.py')
    raw = path.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == pin, 'Reference default source bytes differ')
    function = vars(module)[name]
    _require(type(function) is FunctionType, 'Reference canonical default is not its original function')
    codes = [item for item in compile(raw, str(path), 'exec').co_consts
             if isinstance(item, CodeType) and item.co_name == name]
    _require(len(codes) == 1, 'Reference default source function census differs')
    result = _Default(module, function, path, pin, name, codes[0])
    result.verify()
    return result


_GENERATOR = _default('synthesis.construct', 'generate_construct',
    'e7b225856472c0012f79ea7ee0374d38a9818084c580bcb486d7c39720d74eee')
_EMITTER = _default('backends.reference', 'emit_reference_sequence',
    '0333282a5b30c21bceea459c791b0b8c3733c02db47916060076785b53a7f78f')
_CONSTRUCT = importlib.import_module('biocompiler.compiler.construct')
_MOLECULAR = importlib.import_module('biocompiler.compiler.molecular')
_POLICIES = {
    'translation_policy': (MolecularRecord, 'translation_policy', TranslationPolicy),
    'encoding_policy': (MolecularArtifact, 'encoding_policy', EncodingPolicy),
    'evidence_policy': (MolecularArtifact, 'evidence_policy', EncodingEvidencePolicy),
}
_POLICY_VALUES = {name: vars(owner)[attribute] for name, (owner, attribute, _) in _POLICIES.items()}


class NativeDefault(Enum):
    """A request to execute the corresponding native default producer."""
    GENERATE = 'generate'
    EMIT = 'emit'


@dataclass(frozen=True, eq=False, repr=False)
class HostValue:
    """An actual replacement's output; storing it performs no observation."""
    output: Any
    _owner: object


@dataclass(frozen=True, eq=False, repr=False)
class ReferenceHost:
    """Original authoring roots, after the facade's source-order preflight.

    The facade supplies each freshly parsed invocation input. These helpers do
    not parse it or infer acceptance. Molecular's outer map and Construct's
    nested copy are distinct immutable snapshots with the same manifest values.
    """
    request: Any
    registry: Any
    construct_manifests: Mapping[str, Any]
    molecular_manifests: Mapping[str, Any] | None
    _owner: object = field(default_factory=object)

    @classmethod
    def for_construct(cls, request: Any, registry: Any,
                      manifests: Mapping[str, Any]) -> ReferenceHost:
        return cls(request, registry, MappingProxyType(dict(manifests)), None)

    @classmethod
    def for_molecular(cls, request: Any, registry: Any,
                      manifests: Mapping[str, Any]) -> ReferenceHost:
        molecular = MappingProxyType(dict(manifests))
        return cls(request, registry, MappingProxyType(dict(molecular)), molecular)

    def generate(self, bound_request: Any) -> NativeDefault | HostValue:
        function = vars(_CONSTRUCT)['generate_construct']
        if function is _GENERATOR.function:
            _GENERATOR.verify()
            return NativeDefault.GENERATE
        return HostValue(function(bound_request), self._owner)

    def emit(self, bound_construct: Any) -> NativeDefault | HostValue:
        _require(self.molecular_manifests is not None, 'Molecular callback lacks its original snapshot')
        function = vars(_MOLECULAR)['emit_reference_sequence']
        if function is _EMITTER.function:
            _EMITTER.verify()
            return NativeDefault.EMIT
        return HostValue(function(self.request, bound_construct, self.registry,
                                  self.molecular_manifests), self._owner)

    def proposal(self, value: HostValue, source_links: tuple[SourceLink, ...]) -> PassResult[Any]:
        """Called only after native source links are ready; never inspect output."""
        _require(type(value) is HostValue and value._owner is self._owner,
            'Reference output belongs to another callback owner')
        _require(type(source_links) is tuple, 'Reference source links must be the supplied tuple')
        return PassResult(value.output, (), source_links)

    def origin(self, name: str) -> Any:
        """Closed original roots for structural views; no reflective path API."""
        if name == 'request':
            return self.request
        if name == 'registry':
            return self.registry
        if name == 'construct_manifests':
            return self.construct_manifests
        if name == 'molecular_manifests':
            _require(self.molecular_manifests is not None, 'Molecular origin lacks its original snapshot')
            return self.molecular_manifests
        _require(name in _POLICIES, 'Unknown reference authoring origin')
        owner, attribute, expected = _POLICIES[name]
        value = vars(owner)[attribute]
        declared = vars(owner)['__dataclass_fields__'][attribute].default
        _require(type(value) is expected and value is _POLICY_VALUES[name] and value is declared,
            'Reference class-default origin changed')
        return value


def sorted_source_links_equal(actual: Iterable[Any], expected: Iterable[Any]) -> bool:
    """Original expected-first sorted four-tuples, retaining duplicates/errors."""
    expected_values = sorted((link.requirement_id, link.source_node_id,
                              link.target_node_id, link.pass_name) for link in expected)
    actual_values = sorted((link.requirement_id, link.source_node_id,
                            link.target_node_id, link.pass_name) for link in actual)
    return not (actual_values != expected_values)

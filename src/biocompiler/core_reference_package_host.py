"""Current-module package call points; host data never conveys acceptance.

Native defaults are source-bound sentinels. Actual replacements execute once,
with the original objects, and retain their output/exception identity. The
package service must independently check every returned declaration/report and
must accept only a live build on its existing owner, never a saved record.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
import hashlib
import importlib
from pathlib import Path
import sys
from types import CodeType, FunctionType, ModuleType
from typing import Any

import biocompiler
from biocompiler.core_package_owner import PackageBoundaryError
from biocompiler.core_reference_package_source import check_source

_PACKAGE = Path(biocompiler.__file__).resolve().parent


def _require(value: bool, message: str) -> None:
    if not value:
        raise PackageBoundaryError(message)


def _literal(value: Any) -> tuple[type, Any]:
    _require(type(value) in (str, int, float, bool, type(None)), 'Unsupported package default literal')
    return type(value), value


@dataclass(frozen=True)
class _Source:
    module: ModuleType
    function: FunctionType
    path: Path
    pin: str
    name: str
    code: CodeType
    defaults: tuple[tuple[type, Any], ...]
    keyword_defaults: tuple[tuple[str, tuple[type, Any]], ...]

    def verify(self) -> None:
        namespace = vars(self.module)
        qualified = 'biocompiler.' + self.path.relative_to(_PACKAGE).with_suffix('').as_posix().replace('/', '.')
        function = self.function
        _require(sys.modules.get(qualified) is self.module and namespace.get('__name__') == qualified
            and namespace.get('__package__') == qualified.rpartition('.')[0]
            and Path(namespace.get('__file__', '')).resolve() == self.path,
            'Package default module origin differs')
        raw = self.path.read_bytes()
        check_source(self.path, raw)
        _require(hashlib.sha256(raw).hexdigest() == self.pin,
            'Package default source bytes differ')
        _require(function.__globals__ is namespace and function.__module__ == qualified
            and function.__name__ == self.name and function.__qualname__ == self.name
            and function.__code__ == self.code and function.__code__.co_filename == str(self.path)
            and function.__closure__ is None,
            'Package default code or globals differ')
        actual = function.__defaults__
        keyword = function.__kwdefaults__
        _require(actual is None or type(actual) is tuple, 'Package positional defaults differ')
        _require(keyword is None or type(keyword) is dict, 'Package keyword defaults differ')
        _require(tuple(_literal(value) for value in (actual or ())) == self.defaults
            and tuple((name, _literal(value)) for name, value in (keyword or {}).items()) == self.keyword_defaults,
            'Package default argument values differ')


def _source(module_name: str, name: str, pin: str) -> _Source:
    module = importlib.import_module('biocompiler.' + module_name)
    path = _PACKAGE / (module_name.replace('.', '/') + '.py')
    raw = path.read_bytes()
    _require(hashlib.sha256(check_source(path, raw)).hexdigest() == pin, 'Package original default source bytes differ')
    function = vars(module)[name]
    _require(type(function) is FunctionType, 'Package canonical default is not the original function')
    codes = [value for value in compile(raw, str(path), 'exec').co_consts
             if isinstance(value, CodeType) and value.co_name == name]
    syntax = [value for value in ast.parse(raw).body if isinstance(value, ast.FunctionDef) and value.name == name]
    _require(len(codes) == 1 and len(syntax) == 1, 'Package default source function census differs')
    arguments = syntax[0].args
    result = _Source(module, function, path, hashlib.sha256(raw).hexdigest(), name, codes[0],
        tuple(_literal(ast.literal_eval(value)) for value in arguments.defaults),
        tuple((argument.arg, _literal(ast.literal_eval(value)))
              for argument, value in zip(arguments.kwonlyargs, arguments.kw_defaults) if value is not None))
    result.verify()
    return result


_REFERENCE_PIN = '61a1ec4412112c1443bfc4f548d4de0b620b9384a0d9acab67a46639a7353527'
_REFERENCE = importlib.import_module('biocompiler.compiler.reference')
_SEQUENCES = importlib.import_module('biocompiler.artifacts.sequences')
_DEFAULTS = {
    'load_reference_inputs': _source('registry.reference_builds', 'load_reference_inputs',
        '5fe58bb430fb3d0870161815f9bca232910751fcd6698b4a83bb1cf8ee256c96'),
    'collect_reference_files': _source('registry.reference_builds', 'collect_reference_files',
        '5fe58bb430fb3d0870161815f9bca232910751fcd6698b4a83bb1cf8ee256c96'),
    'run_molecular_pipeline': _source('compiler.molecular', 'run_molecular_pipeline',
        '040d85262f0b96f00e20276237a42bba9f68de8bd61e06148621432417ce4166'),
    'export_reference_sequence': _source('artifacts.sequences', 'export_reference_sequence',
        'e5240d52aa7a2d97453b1e57cf84af159ed880015d0892f80e8fb1dfc587ed03'),
    'check_composition': _source('verification.components', 'check_composition',
        '1112dfd60791cb55eac6343c8e7a08d59f3b9f11a1618dc1fb1a82654da3af4a'),
    'check_construct': _source('verification.construct', 'check_construct',
        '370686f2379158303e5b059882205350ebabd200499dffa105c58d56dde891cc'),
    'check_molecular': _source('verification.molecular', 'check_molecular',
        '0a12ceba4dadcea95b90770ec640edd30df95b854829d1e5307e809b09fc056c'),
    '_tools': _source('compiler.reference', '_tools', _REFERENCE_PIN),
}


@dataclass(frozen=True, eq=False, repr=False)
class NativeCall:
    name: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    owner: object


@dataclass(frozen=True, eq=False, repr=False)
class HostValue:
    value: Any
    owner: object


@dataclass(frozen=True, eq=False, repr=False)
class PackageHost:
    """One adapter owner; scope and source order belong to the native workflow."""
    _owner: object = field(default_factory=object)

    def verify_default(self, name: str) -> FunctionType:
        """Return the source-verified captured default, preserving current aliases."""
        _require(name in _DEFAULTS, 'Unknown package source call point')
        source = _DEFAULTS[name]
        source.verify()
        return source.function

    def call(self, name: str, *args: Any, **kwargs: Any) -> NativeCall | HostValue:
        _require(name in _DEFAULTS, 'Unknown package source call point')
        source = _DEFAULTS[name]
        current = vars(_SEQUENCES if name == 'check_molecular' else _REFERENCE)[name]
        if current is source.function:
            source.verify()
            return NativeCall(name, args, kwargs, self._owner)
        return HostValue(current(*args, **kwargs), self._owner)

    def unwrap(self, value: HostValue) -> Any:
        _require(type(value) is HostValue and value.owner is self._owner,
            'Package callback output belongs to another owner')
        return value.value

    def package_version(self) -> Any:
        # Deliberately late, at the original local import immediately before
        # _tools. Do not cache or coerce the current module attribute.
        return biocompiler.__version__

    def tool_versions(self, call: NativeCall) -> tuple[tuple[str, Any], ...]:
        _require(type(call) is NativeCall and call.owner is self._owner and call.name == '_tools'
            and not call.args and not call.kwargs, 'Package tool request has a foreign source call')
        _DEFAULTS['_tools'].verify()
        names = (
            ('reference_build', 'REFERENCE_BUILD_VERSION'),
            ('human_admission_policy', 'ADMISSION_POLICY_VERSION'),
            ('reference_inputs', 'REFERENCE_BUILD_INPUTS_VERSION'), ('archive', 'ARCHIVE_VERSION'),
            ('sequence_export', 'SEQUENCE_EXPORT_VERSION'), ('sequence_emitter', 'EMITTER_VERSION'),
            ('construct_pipeline', 'CONSTRUCT_PIPELINE_VERSION'), ('molecular_pipeline', 'MOLECULAR_PIPELINE_VERSION'),
            ('reference_adapter', 'REFERENCE_COMPONENT_VERSION'), ('construct_generator', 'CONSTRUCT_GENERATOR_VERSION'),
            ('component_checker', 'COMPONENT_CHECKER_VERSION'), ('construct_checker', 'CONSTRUCT_CHECKER_VERSION'),
            ('molecular_checker', 'MOLECULAR_CHECKER_VERSION'),
        )
        # Native code creates/hashes ToolPins. Reading these closed module values
        # performs no Python compiler/checker/semantic constructor call.
        return tuple((key, vars(_REFERENCE)[name]) for key, name in names)

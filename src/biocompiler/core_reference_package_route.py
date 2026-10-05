"""Explicit reference package orchestration over one native package lifetime.

Python calls the current public functions and performs bounded byte IO. Core owns
construction, checks, identities and canonical bytes; standalone Verify is a
separate producer-free execution. No native rejection retries Python semantics.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path, PurePosixPath
import tempfile
import sys
from typing import Any, Iterator, cast

from biocompiler.artifacts.manifest import ReferenceBuildRequest
from biocompiler.compiler import reference
from biocompiler.core_client import CoreProtocolError, JsonValue
from biocompiler.core_package_files import PackageFiles
from biocompiler.core_package_owner import PackageBoundaryError, PackageOwner
from biocompiler.core_pipeline_callback_session import CallbackRejected
from biocompiler.core_pipeline_manager import CorePassManager
from biocompiler.core_pipeline_session import encode_document
from biocompiler.core_reference_package_io import ReferenceReader
from biocompiler.core_reference_package_views import PackageViews
from biocompiler.errors import SerializationError
from biocompiler.reference_package_backend import PackageRoute, at_default

_ACTIVE: ContextVar[_Runtime | None] = ContextVar('reference_package_runtime', default=None)
_PUBLICATION: ContextVar[list[object] | None] = ContextVar('reference_package_publication', default=None)


def _runtime_profile() -> str:
    if sys.version_info[:2] == (3, 11):
        return 'python311'
    if sys.version_info[:2] == (3, 14):
        return 'python314'
    raise PackageBoundaryError('Reference package routing requires Python 3.11 or 3.14')


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PackageBoundaryError(message)


def _fields(value: Any, names: str) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == set(names.split()), 'Invalid package continuation fields')
    return cast(dict[str, Any], value)


def _document(value: Any) -> JsonValue:
    # This observes the actual public object at the original call boundary. It
    # does not run a constructor, parser, producer, admission rule or checker.
    return cast(JsonValue, value.to_dict())


def _trusted_decode(callback: Any, *args: Any, **kwargs: Any) -> Any:
    """Malformed native views invalidate the owner; user callbacks stay opaque."""
    try:
        return callback(*args, **kwargs)
    except PackageBoundaryError:
        raise
    except CoreProtocolError as error:
        raise PackageBoundaryError(str(error)) from error


def _same(value: Any, expected: Any, label: str) -> None:
    _require(encode_document(value) == encode_document(expected), label + ' changed its native declaration')


def _native_exception(raw: JsonValue) -> tuple[BaseException, UnicodeDecodeError | None]:
    value = _fields(raw, 'module type message attributes attributes_tree' +
        (' cause_utf8_bytes_hex' if type(raw) is dict and 'cause_utf8_bytes_hex' in raw else ''))
    descriptor = dict(value)
    has_cause = 'cause_utf8_bytes_hex' in descriptor
    encoded = descriptor.pop('cause_utf8_bytes_hex', None)
    error = CorePassManager._exception(cast(CorePassManager, None), descriptor)
    if not has_cause:
        return error, None
    _require(type(error) is SerializationError and str(error) == 'Packaged request must be UTF-8 JSON.',
             'Unexpected native UTF-8 failure boundary')
    _require(type(encoded) is str and 0 < len(encoded) <= 2 * 16_777_216 and len(encoded) % 2 == 0
             and all(c in '0123456789abcdef' for c in encoded), 'Invalid native UTF-8 cause bytes')
    try:
        bytes.fromhex(encoded).decode('utf-8')
    except UnicodeDecodeError as cause:
        return error, cause
    raise PackageBoundaryError('Native UTF-8 failure supplied valid UTF-8 bytes')


def _members(value: Any) -> list[tuple[str, bytes]]:
    _require(type(value) is list and len(value) <= 128, 'Invalid retained package member census')
    result: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    total = 0
    for pair in value:
        _require(type(pair) is list and len(pair) == 2, 'Invalid retained package member')
        name, encoded = pair
        _require(type(name) is str and 0 < len(name.encode('utf-8')) <= 1024 and '\\' not in name,
                 'Invalid retained package member path')
        path = PurePosixPath(name)
        _require(not path.is_absolute() and path.as_posix() == name and
                 all(part not in ('', '.', '..') for part in path.parts) and name not in seen,
                 'Unsafe or duplicate retained package member')
        _require(type(encoded) is str and len(encoded) <= 2 * 16_777_216 and len(encoded) % 2 == 0
                 and all(c in '0123456789abcdef' for c in encoded), 'Invalid retained package member bytes')
        total += len(encoded) // 2
        _require(total <= 67_108_864, 'Retained package members exceed their byte ceiling')
        seen.add(name)
        result.append((name, bytes.fromhex(encoded)))
    return result


class _Runtime:
    def __init__(self, route: PackageRoute, files: PackageFiles):
        from biocompiler.core_reference_package_protocol import declaration, ACTIONS
        from biocompiler.core_reference_package_host import PackageHost
        _runtime_profile()
        self.route, self.files = route, files
        self.host = PackageHost()
        self.views = PackageViews()
        self.directory: Any = None
        self.request: Any = None
        self.reference: Any = None
        self.registry: Any = None
        self.manifests: Any = None
        self.build: Any = None
        self.construct: Any = None
        self.export_arguments: tuple[Any, ...] | None = None
        self.export_width: Any = None
        self.reader: ReferenceReader | None = None
        self.loaded: list[tuple[object, str]] = []
        self.collected: list[tuple[object, str]] = []
        self.exports: list[tuple[object, str]] = []
        self.packages: list[tuple[object, str]] = []
        self.authorities: list[tuple[object, Any, Any]] = []
        self.rebuilt: Any = None
        self.package_version: Any = None
        self.tool_pins: Any = None
        self.retained_bytes = 0
        self.owner = PackageOwner(route.core, files=files, application=declaration(),
            actions=ACTIONS, handler=self.invoke, limits=route.limits)

    def reserve(self, value: JsonValue) -> None:
        from biocompiler.core_pipeline_callback_session import _nodes
        self.retained_bytes += len(encode_document(value)) + 256 * _nodes(value) + 256
        _require(self.retained_bytes <= self.owner.session._limits['max_retained_bytes'],
                 'Package host representations exceeded their lifetime retention ceiling')

    def call(self, operation: str, arguments: JsonValue) -> Any:
        response = None
        failed = False
        rejection: JsonValue = None
        try:
            response = self.owner.session.call(operation, arguments)
        except CallbackRejected as rejected:
            rejection = rejected.response.result
            failed = True
        # Leave the transport handler before constructing public exceptions.
        # Otherwise its internal rejection leaks into the public cause graph.
        if failed:
            error, cause = _trusted_decode(_native_exception, rejection)
            if cause is not None:
                try:
                    raise cause
                except UnicodeDecodeError:
                    raise error from cause
            raise error
        _require(response is not None, 'Package command omitted its completed response')
        assert response is not None
        result = response.result
        self.reserve(result)
        return result

    def actual(self, name: str, native: Any, *args: Any, **kwargs: Any) -> Any:
        with at_default(name, lambda *a, **k: self.default(name, native, a, k, self.host.verify_default)):
            return getattr(reference, name)(*args, **kwargs)

    @staticmethod
    def default(name: str, callback: Any, args: Any, kwargs: Any, verify: Any) -> Any:
        verify(name)
        return callback(*args, **kwargs)

    @staticmethod
    def capability(value: object, entries: list[tuple[object, str]]) -> str | None:
        return next((token for actual, token in reversed(entries) if actual is value), None)

    def load_default(self, alphabet: Any, directory: Any) -> Any:
        from biocompiler.core_reference_package_origins import input_roots
        previous = self.reader
        self.reader = ReferenceReader(directory)
        try:
            raw = _fields(self.call('package-inputs', {'alphabet': alphabet}), 'capability request reference registry')
        finally:
            self.reader = previous
        value = _trusted_decode(input_roots, alphabet, raw['request'], raw['reference'], raw['registry'])
        self.loaded.append((value, raw['capability']))
        return value

    def load(self, alphabet: Any, directory: Any) -> tuple[Any, str]:
        value = self.actual('load_reference_inputs', self.load_default, alphabet, directory)
        # Unpacking is an actual source operation, preserving a replacement's
        # iteration and exception behavior. Its returned values stay authoritative.
        construct, manifest, registry = value
        token = self.capability(value, self.loaded)
        if token is None:
            raw = self.call('package-import-inputs', {'request': _document(construct),
                'reference': _document(manifest), 'registry': _document(registry)})
            token = _fields(raw, 'capability request reference registry')['capability']
        return (construct, manifest, registry), token

    def collect_default(self, directory: Any, manifest: Any) -> Any:
        previous = self.reader
        self.reader = ReferenceReader(directory)
        try:
            raw = _fields(self.call('package-collect', {'reference': _document(manifest)}), 'capability files')
        finally:
            self.reader = previous
        value = dict(_members(raw['files']))
        self.collected.append((value, raw['capability']))
        return value

    def checker(self, name: str, raw: Any) -> Any:
        name_map = {'composition': 'check_composition', 'construct': 'check_construct',
                    'export-molecular': 'check_molecular'}
        if name == 'molecular':
            value = self.build.check_result
        else:
            public = name_map[name]
            args: tuple[Any, ...]
            if name == 'composition':
                args = (self.request.construct.composition, self.registry)
                expected = {'request': _document(args[0]), 'registry': _document(args[1])}
            elif name == 'construct':
                args = (self.request.construct, self.construct, self.registry, self.manifests)
                expected = {'request': _document(args[0]), 'construct': _document(args[1]),
                    'registry': _document(args[2]), 'manifests': [[k, _document(v)] for k, v in args[3].items()]}
            else:
                _require(self.export_arguments is not None, 'Export checker lost its current arguments')
                assert self.export_arguments is not None
                args = self.export_arguments
                expected = {'request': _document(args[0]), 'construct': _document(args[1]),
                    'artifact': _document(args[2]), 'registry': _document(args[3]),
                    'manifests': [[k, _document(v)] for k, v in args[4].items()], 'line_width': self.export_width}
            _same(raw['arguments'], expected, 'Package checker')
            used = False
            def native(*actual: Any, **keywords: Any) -> Any:
                nonlocal used
                _require(not keywords and len(actual) == len(args), 'Native checker argument census differs')
                if not used and all(a is b for a, b in zip(actual, args)):
                    used = True
                    value = self.call('package-check-native', {'check_id': raw['check_id']})
                else:
                    # A wrapper can call its captured default again or with
                    # changed roots. Run that actual check afresh on this owner;
                    # its output still grants no authority to the outer package.
                    if name == 'composition':
                        declared = {'request': _document(actual[0]), 'registry': _document(actual[1])}
                    elif name == 'construct':
                        declared = {'request': _document(actual[0]), 'construct': _document(actual[1]),
                            'registry': _document(actual[2]),
                            'manifests': [[k, _document(v)] for k, v in actual[3].items()]}
                    else:
                        declared = {'request': _document(actual[0]), 'construct': _document(actual[1]),
                            'candidate': _document(actual[2]), 'registry': _document(actual[3]),
                            'manifests': [[k, _document(v)] for k, v in actual[4].items()]}
                    value = self.call('package-check-evaluate', {'check_id': raw['check_id'],
                        'name': 'molecular' if name == 'export-molecular' else name, 'arguments': declared})
                if name == 'composition':
                    return _trusted_decode(self.views.link_result, value)
                if name == 'construct':
                    return _trusted_decode(self.views.construct_result, value)
                return _trusted_decode(self.views.molecular_result, value)
            if name == 'export-molecular':
                from biocompiler.artifacts import sequences
                with at_default(public, lambda *a, **k: self.default(public, native, a, k, self.host.verify_default)):
                    value = sequences.check_molecular(*args)
            else:
                value = self.actual(public, native, *args)
        return {'kind': 'host', 'value': self.owner.objects.retain(value)}

    def invoke(self, action: str, arguments: JsonValue) -> JsonValue:
        token: Any
        if action == 'package-read':
            d = _fields(arguments, 'kind path')
            _require(self.reader is not None, 'Package read has no current public loader')
            assert self.reader is not None
            return self.reader.read(d['kind'], d['path']).hex()
        if action == 'package-load':
            d = _fields(arguments, 'alphabet')
            roots, token = self.load(d['alphabet'], self.directory)
            _, self.reference, self.registry = roots
            return {'capability': token}
        if action == 'package-collect':
            _same(arguments, _document(self.reference), 'Reference collection')
            value = self.actual('collect_reference_files', self.collect_default, self.directory, self.reference)
            token = self.capability(value, self.collected)
            if token is None:
                raw = self.call('package-import-files', {'files': [[key, content.hex()] for key, content in value.items()]})
                token = _fields(raw, 'capability')['capability']
            return {'capability': token}
        if action == 'package-run':
            d = _fields(arguments, 'request registry manifests')
            self.manifests = {self.reference.reference_set_id: self.reference}
            _same(d, {'request': _document(self.request.construct), 'registry': _document(self.registry),
                'manifests': [[k, _document(v)] for k, v in self.manifests.items()]}, 'Package pipeline')
            from biocompiler.reference_backend import reference_core
            with self.owner.initialize(), reference_core(self.route.core, limits=self.route.limits):
                self.build = reference.run_molecular_pipeline(self.request.construct, self.registry, self.manifests)
            manager = self.build.manager
            _require(manager is self.owner.manager, 'Package build returned a foreign manager')
            matches = [key for key, entry in manager._reference_build_views.builds.items() if entry.value is self.build]
            _require(len(matches) == 1, 'Package build is not its actual native result')
            return {'build_id': matches[0]}
        if action == 'package-construct':
            self.construct = self.build.construct
            return _document(self.construct)
        if action == 'package-export':
            d = _fields(arguments, 'request construct artifact registry manifests line_width')
            args = (self.request.construct, self.construct, self.build.candidate, self.registry, self.manifests)
            _same(d, {'request': _document(args[0]), 'construct': _document(args[1]), 'artifact': _document(args[2]),
                'registry': _document(args[3]), 'manifests': [[k, _document(v)] for k, v in args[4].items()],
                'line_width': self.request.fasta_line_width}, 'Package export')
            value = reference.export_reference_sequence(*args, line_width=self.request.fasta_line_width)
            token = self.capability(value, self.exports)
            if token is not None:
                return {'kind': 'native', 'value': {'capability': token}}
            return {'kind': 'host', 'value': {'fasta': value.fasta, 'specification': value.specification,
                'line_width': value.line_width, 'sequence_sha256': value.sequence_sha256,
                'molecular_fingerprint': value.molecular_fingerprint}}
        if action in ('package-get', 'package-result'):
            d = _fields(arguments, 'identity' if action == 'package-get' else 'identity scope')
            manager = self.build.manager
            _require(manager is self.owner.manager, 'Package observation changed its manager')
            if action == 'package-get':
                value = manager.get(d['identity'])
                response = manager.session.last_response
                _require(manager._records.get(d['identity']) is value and response is not None
                    and response.operation == 'get' and response.status == 'ok', 'Package get lost its actual returned capability')
                sequence = response.sequence
            else:
                value = manager.result(d['identity'], scope=d['scope'])
                receipt = manager._result_receipts.get(id(value))
                _require(receipt is not None and receipt[0] is value, 'Package result lost its actual returned capability')
                sequence = receipt[1]
            return {'sequence': sequence}
        if action == 'package-check':
            d = _fields(arguments, 'name arguments check_id')
            return cast(JsonValue, self.checker(d['name'], d))
        if action == 'package-check-value':
            raise PackageBoundaryError('Package default checker must execute through its actual public call')
        if action.startswith('package-report-'):
            value = self.owner.objects.resolve(arguments)
            if action == 'package-report-passed':
                return bool(value.passed)
            if action == 'package-report-document':
                return cast(JsonValue, value.to_dict())
            if action == 'package-report-export':
                passed = value.passed
                codes = [item.code for item in value.diagnostics]
                # The original eagerly builds the diagnostic message before
                # require() asks for the report's truth value.
                '; '.join(codes)
                return {'passed': bool(passed), 'diagnostics': codes}
        if action == 'package-version':
            self.package_version = self.host.package_version()
            return cast(JsonValue, self.package_version)
        if action == 'package-tools':
            def native() -> Any:
                from biocompiler.core_reference_package_host import NativeCall
                call = NativeCall('_tools', (), {}, self.host._owner)
                raw = self.call('package-tools-native', {'versions': [list(pair) for pair in self.host.tool_versions(call)]})
                return tuple(_trusted_decode(self.views.tool, item) for item in raw)
            self.tool_pins = self.actual('_tools', native)
            return [item.to_dict() for item in self.tool_pins]
        if action == 'package-rebuild':
            d = _fields(arguments, 'request files run_metadata')
            request = _trusted_decode(self.views.build_request, d['request'])
            metadata = None if d['run_metadata'] is None else _trusted_decode(self.views.metadata, d['run_metadata'])
            members = _members(d['files'])
            with tempfile.TemporaryDirectory(prefix='biocompiler-reference-') as temporary:
                root = Path(temporary)
                for name, content in members:
                    destination = root / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(content)
                self.rebuilt = reference.build_reference_package(request, root, run_metadata=metadata)
            token = self.capability(self.rebuilt, self.packages)
            _require(token is not None, 'Current public reconstruction returned no same-owner native package')
            return {'capability': token}
        raise PackageBoundaryError('Unknown package continuation action')

    def built(self, request: Any, directory: Any, metadata: Any) -> Any:
        fields = ('request', 'directory', 'reference', 'registry', 'manifests', 'build',
                  'construct', 'package_version', 'tool_pins', 'export_arguments', 'export_width')
        old = tuple(getattr(self, name) for name in fields)
        self.request, self.directory = request, directory
        try:
            raw = _fields(self.call('package-build', {'request': _document(request),
                'run_metadata': None if metadata is None else _document(metadata), 'runtime': _runtime_profile()}),
                'capability request manifest archive build_fingerprint')
            returned = _trusted_decode(self.views.build_request, raw['request'], original=request)
            manifest = _trusted_decode(self.views.manifest, raw['manifest'])
            descriptor = self.call('package-output', {'capability': raw['capability']})
            _same(descriptor, raw['archive'], 'Package output')
            data = self.files.read_output(descriptor)
            package = self.views.package(returned, manifest, data)
            _require(raw['build_fingerprint'] == package.build_fingerprint, 'Native package build identity differs')
            self.packages.append((package, raw['capability']))
            self.authorities.append((package, self.package_version, self.tool_pins))
            return package
        finally:
            for name, value in zip(fields, old):
                setattr(self, name, value)

    def exported(self, args: tuple[Any, ...], line_width: Any) -> Any:
        old = self.export_arguments, self.export_width
        self.export_arguments, self.export_width = args, line_width
        try:
            raw = _fields(self.call('package-export', {'request': _document(args[0]), 'construct': _document(args[1]),
                'artifact': _document(args[2]), 'registry': _document(args[3]),
                'manifests': [[k, _document(v)] for k, v in args[4].items()], 'line_width': line_width}), 'capability value')
            value = _trusted_decode(self.views.export, raw['value'])
            self.exports.append((value, raw['capability']))
            return value
        finally:
            self.export_arguments, self.export_width = old


@contextmanager
def _runtime(route: PackageRoute, archive: bytes | None = None) -> Iterator[_Runtime]:
    active = _ACTIVE.get()
    if active is not None:
        _require(active.route is route and archive is None, 'Nested package operation changed its owner')
        yield active
        return
    with PackageFiles(archive) as files:
        runtime = _Runtime(route, files)
        token = _ACTIVE.set(runtime)
        try:
            with runtime.owner.session:
                yield runtime
        finally:
            _ACTIVE.reset(token)
            runtime.owner.objects.close()


def prepare(route: PackageRoute, alphabet: Any, directory: Any, *, fasta_line_width: Any = 80) -> Any:
    if not isinstance(alphabet, str) or alphabet not in ('DNA', 'RNA'):
        raise SerializationError('The reviewed reference build supports only DNA or RNA.')
    with _runtime(route) as runtime:
        (construct, _, _), token = runtime.load(alphabet, directory)
        raw = runtime.call('package-prepare', {'inputs': token, 'line_width': fasta_line_width})
        request = _trusted_decode(runtime.views.build_request, raw)
        _same(_document(request.construct), _document(construct), 'Prepared package construct origin')
        object.__setattr__(request, 'construct', construct)
        return request


def build(route: PackageRoute, request: Any, directory: Any, *, run_metadata: Any = None) -> Any:
    if not isinstance(request, ReferenceBuildRequest):
        raise SerializationError('Expected a frozen ReferenceBuildRequest; general intent compilation is unsupported.')
    with _runtime(route) as runtime:
        return runtime.built(request, directory, run_metadata)


def reconstruct(route: PackageRoute, data: Any, *, expected_request: Any = None,
                expected_build_fingerprint: Any = None) -> Any:
    if expected_request is None and expected_build_fingerprint is None:
        raise SerializationError('Fresh verification requires an independently trusted request or build fingerprint.')
    if expected_request is not None and not isinstance(expected_request, ReferenceBuildRequest):
        raise SerializationError('Expected a frozen ReferenceBuildRequest.')
    with _runtime(route, data) as runtime:
        raw = _fields(runtime.call('package-reconstruct', {'archive': runtime.files.input_descriptor,
            'expected_request': None if expected_request is None else _document(expected_request),
            'expected_build_fingerprint': expected_build_fingerprint, 'runtime': _runtime_profile()}),
            'capability request manifest archive build_fingerprint')
        package = runtime.rebuilt
        _require(package is not None and runtime.capability(package, runtime.packages) is not None,
                 'Core reconstruction omitted its current public build')
        _require(raw['capability'] == runtime.capability(package, runtime.packages),
                 'Core reconstruction changed its actual package capability')
        _require(raw['build_fingerprint'] == package.build_fingerprint,
                 'Core reconstruction changed its actual build fingerprint')
        _same(raw['request'], _document(package.request), 'Reconstructed request')
        _same(raw['manifest'], _document(package.manifest), 'Reconstructed manifest')
        _same(raw['archive'], {'bytes': len(package.data), 'sha256': package.archive_sha256}, 'Reconstructed archive')
        from biocompiler.core_reference_package_verify import verify_package
        authority = next((entry for entry in runtime.authorities if entry[0] is package), None)
        _require(authority is not None, 'Reconstruction lost its actual current tool authority')
        assert authority is not None
        verify_package(route.verify, data, package_version=authority[1],
            tool_pins=[item.to_dict() for item in authority[2]],
            expected_request=None if expected_request is None else _document(expected_request),
            expected_build_fingerprint=expected_build_fingerprint)
        publication = _PUBLICATION.get()
        if publication is not None:
            publication.append(package)
        return package


def publish(route: PackageRoute, package: Any, output: Any) -> Any:
    if not isinstance(package, reference.ReferencePackage):
        raise SerializationError('Expected a reference package.')
    verified: list[object] = []
    token = _PUBLICATION.set(verified)
    try:
        checked = reference.verify_reference_package(package.data, expected_request=package.request,
            expected_build_fingerprint=package.manifest.build_fingerprint)
        _require(any(value is checked for value in verified), 'Current public verify returned no fresh native verification')
        return reference.write_archive_atomic(output, checked.data)
    finally:
        _PUBLICATION.reset(token)


def export(route: PackageRoute, request: Any, construct: Any, artifact: Any, registry: Any,
           manifests: Any, *, line_width: Any = 80) -> Any:
    if type(line_width) is not int or not 1 <= line_width <= 10000:
        raise SerializationError('FASTA line width must be an integer from 1 to 10000.')
    with _runtime(route) as runtime:
        return runtime.exported((request, construct, artifact, registry, manifests), line_width)

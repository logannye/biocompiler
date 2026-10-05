"""Closed Python execution proof for the selected reference workflow campaign.

Authoring outside a selected operation remains Python. Inside actual public
routes and Core methods only the reviewed transport and structural conversion
code may execute. This is an execution receipt, never native acceptance.
"""
from __future__ import annotations

import builtins
from collections import Counter
from contextlib import contextmanager
from dataclasses import MISSING, fields, field, is_dataclass, make_dataclass
import dis
import hashlib
import importlib
import json
from pathlib import Path
import sys
from types import CodeType, FunctionType

if __package__:
    from . import check_pipeline_manager_install as manager
else:
    import check_pipeline_manager_install as manager

registration = manager.fixed.source_tool('pipeline_registration_guard')

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'biocompiler.reference_execution_guard.v2'
PREFIX_WITNESS = 'tests/conformance/reference-public-routing-source-counterpart-v1.json'
PREFIX_PIN = '949bd00942bbaa8c6107c490692e38007e41309b0d8f22b0bccd4d8f8514f074'
TRANSPORT = manager.TRANSPORT_MODULES | {
    'biocompiler.core_reference_host', 'biocompiler.core_reference_views',
    'biocompiler.core_reference_provider_views', 'biocompiler.core_reference_manager',
    'biocompiler.reference_backend',
}
SERIALIZERS = {**manager.SERIALIZER_ROOTS,
    'biocompiler.ir.construct': ('_Record.to_dict', 'ConstructRequest.to_dict',
        'ConstructCandidate.to_dict', 'ConstructRequest.target', 'ConstructRequest.registry_lock'),
    'biocompiler.ir.molecular': ('_Record.to_dict', 'MolecularRecord.to_dict',
        'MolecularRecord.length', 'MolecularArtifact.to_dict'),
    'biocompiler.registry.references': ('ReferenceRecord.to_dict', 'ReferenceManifest.to_dict'),
    'biocompiler.registry.reference_components': ('ReferenceSelection.to_dict',),
    'biocompiler.semantics.coordinates': ('SequenceRange.to_dict',),
    'biocompiler.verification.construct': ('ConstructDiagnostic.to_dict', 'ConstructResult.to_dict'),
    'biocompiler.verification.molecular': ('MolecularDiagnostic.to_dict', 'MolecularCheck.to_dict', 'MolecularResult.to_dict'),
    'biocompiler.semantics.context': ('TargetContext.to_dict', 'HumanTargetContext.to_dict'),
    'biocompiler.compiler.pipeline': ('ScopedObligation.to_dict', 'CheckSpec.to_dict',
        'CheckDecision.to_dict', 'PassContract.to_dict', 'ComponentInputContract.to_dict', 'StageRecord.to_dict'),
    'biocompiler.ir.intent': ('freeze_json', 'thaw_json', 'SourceLocation.to_dict'),
}
# These are data mechanics invoked by the inherited transport, not parsers,
# checker entrypoints, manager acceptance, or producer implementations.
MECHANICS = {
    'biocompiler.ir.serialization': ('require', 'name', 'names'),
    'biocompiler.compiler.pipeline': ('CheckDecision.__post_init__',),
    'biocompiler.verification.evidence': ('CheckDiagnostic.to_dict', 'DependencySnapshot.to_dict'),
}
DATA_CLASSES = {
    'biocompiler.compiler.pipeline': ('ScopedObligation', 'CheckSpec', 'CheckDecision', 'PassContract',
        'PassContext', 'ComponentInputContract', 'CompletionProfile', 'StageRecord', 'PipelineResult'),
    'biocompiler.compiler.passes': ('PassResult',),
    'biocompiler.artifacts.provenance': ('SourceLink',),
}
PUBLIC = {'biocompiler.compiler.construct': 'run_construct_pipeline',
          'biocompiler.compiler.molecular': 'run_molecular_pipeline'}
# These exact source spans perform one check/read per OS readiness turn or
# received chunk. The same helpers' other call sites remain exact counts.
SCHEDULING_MODULE = 'biocompiler.core_pipeline_callback_session'
SCHEDULING_SOURCE_SHA256 = 'd24cb3b78df7b7c85d0bbec5cd3c7634ca4756c5e8b0e113a8a3ba7258229a54'
SCHEDULING_SITES = (
    ('exchange-deadline', '_exchange', '_check_time', (320, 320, 12, 38)),
    ('exchange-read', '_exchange', '_read', (333, 333, 28, 43)),
    ('exchange-aggregate', '_exchange', '_require', (337, 338, 20, 78)),
    ('exchange-trailing', '_exchange', '_require', (346, 346, 24, 112)),
    ('quiet-read', '_quiet', '_read', (295, 295, 24, 39)),
)


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def code_pin(code):
    """Deterministic typed code content, independent of marshal sharing flags."""
    def constant(value):
        kind=type(value)
        if kind is CodeType: return ['code',document(value)]
        if value is Ellipsis: return ['ellipsis']
        if kind is bytes: return ['bytes',value.hex()]
        if kind is slice: return ['slice',constant(value.start),constant(value.stop),constant(value.step)]
        if kind is tuple: return ['tuple',[constant(item) for item in value]]
        if kind is frozenset: return ['frozenset',sorted((constant(item) for item in value),key=canonical)]
        if kind is complex: return ['complex',value.real.hex(),value.imag.hex()]
        if kind is float: return ['float',value.hex()]
        require(value is None or kind in (bool,int,str), 'Unknown compiled source constant')
        return [kind.__name__,value]
    def document(value):
        return {'arguments':[value.co_argcount,value.co_posonlyargcount,value.co_kwonlyargcount],
            'locals':value.co_nlocals,'stack':value.co_stacksize,'flags':value.co_flags,
            'bytecode':value.co_code.hex(),'constants':[constant(item) for item in value.co_consts],
            'names':list(value.co_names),'variables':list(value.co_varnames),'free':list(value.co_freevars),
            'cells':list(value.co_cellvars),'name':value.co_name,'qualname':value.co_qualname,
            'first_line':value.co_firstlineno,'lines':value.co_linetable.hex(),'exceptions':value.co_exceptiontable.hex()}
    return sha(canonical(document(code)))


def unwrap(value):
    if isinstance(value, (staticmethod, classmethod)):
        return value.__func__
    if isinstance(value, property):
        return value.fget
    return value


class Policy:
    def __init__(self):
        import biocompiler
        self.package = Path(biocompiler.__file__).resolve().parent
        self.entries, self.sources, self.modules, self.public, self.keys = {}, {}, {}, {}, {}
        self.module_code = {}
        for name in sorted(TRANSPORT):
            module = self.module(name)
            for value in vars(module).values():
                if type(value) is FunctionType and value.__module__ == name:
                    self.bind(getattr(value, '__wrapped__', value), name, 'transport')
                elif isinstance(value, type) and value.__module__ == name:
                    for item in vars(value).values():
                        item = unwrap(item)
                        if (type(item) is FunctionType and item.__module__ == name and item.__code__.co_filename != '<string>'
                                and not (item.__name__ == '__repr__' and item.__globals__.get('__name__') in ('dataclasses','reprlib'))):
                            self.bind(item, name, 'transport')
                    if is_dataclass(value): self.generated(value, name, 'transport')
        for table, category in ((SERIALIZERS, 'serializer'), (MECHANICS, 'mechanics')):
            for name, paths in table.items():
                for path in paths:
                    self.bind(self.lookup(name, path), name, category)
        # The pre-existing narrow BehaviorNode serializer conversion proof is
        # reused, including its generated TypeSpec/IntentNode constructor pins.
        self.conversion_entries, self.conversion_roots = manager._serialization_policy()
        for code, namespace, category in self.conversion_entries.values():
            if category == 'conversion' or (namespace.get('__name__') == 'biocompiler.ir.intent'
                    and code.co_qualname in ('IntentNode.__post_init__', '__create_fn__.<locals>.__init__')):
                self.module(namespace['__name__'])
                self.add(code, namespace, 'conversion')
        for name, classes in DATA_CLASSES.items():
            for cls in classes: self.generated(vars(self.module(name))[cls], name, 'data')
        self.prefixes()
        self.scheduling_policy()

    def scheduling_policy(self):
        require(self.sources[SCHEDULING_MODULE]['sha256'] == SCHEDULING_SOURCE_SHA256,
                'Reference scheduling call sites require their exact reviewed source')
        self.scheduling_sites, self.scheduling_lookup = [], {}
        self.scheduling_callees = set()
        for name, caller_name, callee_name, position in SCHEDULING_SITES:
            caller = self.lookup(SCHEDULING_MODULE, 'CorePipelineCallbackSession.' + caller_name).__code__
            callee = self.lookup(SCHEDULING_MODULE, callee_name if callee_name == '_require'
                                 else 'CorePipelineCallbackSession.' + callee_name).__code__
            instructions = list(dis.get_instructions(caller, show_caches=True))
            matches = [index for index, instruction in enumerate(instructions)
                if instruction.opname == 'CALL' and tuple(instruction.positions) == position]
            require(len(matches) == 1, 'Reference scheduling call instruction changed')
            index = matches[0]
            site = {'name': name, 'source': self.sources[SCHEDULING_MODULE],
                'caller': self.entries[id(caller)][2], 'callee': self.entries[id(callee)][2],
                'position': list(position), 'instruction': instructions[index].offset}
            self.scheduling_sites.append(site)
            self.scheduling_callees.add(id(callee))
            # 3.11 reports the last CALL cache offset; 3.14 reports CALL itself.
            for instruction in instructions[index:]:
                if instruction is not instructions[index] and instruction.opname != 'CACHE': break
                self.scheduling_lookup[(id(caller), instruction.offset, id(callee))] = site

    def scheduling_entry(self, frame):
        caller = frame.f_back
        if caller is None: return None
        site = self.scheduling_lookup.get((id(caller.f_code), caller.f_lasti, id(frame.f_code)))
        if site is None: return None
        require(self.entry(caller) is site['caller'] and self.entry(frame) is site['callee'],
                'Reference scheduling call site has foreign code or globals')
        return site['name']

    def module(self, name):
        if name in self.modules: return self.modules[name]
        module = importlib.import_module(name)
        path = self.package / (name.removeprefix('biocompiler.').replace('.', '/') + '.py')
        require(Path(module.__file__).resolve() == path and sys.modules.get(name) is module
            and vars(module).get('__name__') == name, 'Reference guard mixed product module origins')
        raw = path.read_bytes()
        self.sources[name] = {'file': 'src/biocompiler/' + path.relative_to(self.package).as_posix(), 'sha256': sha(raw)}
        self.modules[name] = module
        self.module_code[name] = tuple(manager._nested_codes(compile(raw, str(path), 'exec', dont_inherit=True)))
        return module

    def lookup(self, name, path):
        value = self.module(name)
        for part in path.split('.'):
            require(part in vars(value), 'Missing closed reference member: ' + name + '.' + path)
            value = unwrap(vars(value)[part])
        return value

    def add(self, code, namespace, category):
        descriptor = {'module': namespace['__name__'], 'qualname': code.co_qualname,
            'line': code.co_firstlineno, 'code_sha256': code_pin(code), 'category': category}
        self.entries[id(code)] = (code, namespace, descriptor)
        self.keys[id(code)] = canonical(descriptor).decode()

    def bind(self, function, name, category):
        module = self.module(name)
        require(type(function) is FunctionType and function.__globals__ is vars(module)
            and function.__module__ == name and any(function.__code__ == item for item in self.module_code[name])
            and Path(function.__code__.co_filename).resolve() == Path(module.__file__).resolve(),
            'Reference guard callable differs from actual source or globals: ' + name)
        for code in manager._nested_codes(function.__code__): self.add(code, vars(module), category)

    def generated(self, cls, name, category):
        # Recreate inert dataclass mechanics from exact declared fields. No
        # constructor or post-init of the product class is executed here.
        specs = []
        for item in fields(cls):
            kw = {'init': item.init, 'repr': item.repr, 'hash': item.hash, 'compare': item.compare, 'kw_only': item.kw_only}
            if item.default is not MISSING: kw['default'] = item.default
            if item.default_factory is not MISSING: kw['default_factory'] = item.default_factory
            specs.append((item.name, item.type, field(**kw)))
        params = cls.__dataclass_params__
        reference = make_dataclass(cls.__name__, specs, frozen=params.frozen, eq=params.eq,
            namespace={'__post_init__': lambda self: None} if hasattr(cls, '__post_init__') else {})
        for method in ('__init__', '__eq__', '__hash__'):
            function = vars(cls).get(method)
            if type(function) is not FunctionType or function.__code__.co_filename != '<string>': continue
            expected = vars(reference).get(method)
            require(type(expected) is FunctionType and function.__code__ == expected.__code__
                and function.__globals__ is vars(self.module(name)), 'Reference generated dataclass method changed')
            closure = tuple(cell.cell_contents for cell in function.__closure__ or ())
            expected_closure = tuple(cell.cell_contents for cell in expected.__closure__ or ())
            require(len(closure) == len(expected_closure) and all(a is b for a, b in zip(closure, expected_closure)),
                'Reference generated dataclass closure changed')
            self.add(function.__code__, vars(self.modules[name]), category)

    def prefixes(self):
        raw = (ROOT / PREFIX_WITNESS).read_bytes()
        require(sha(raw) == PREFIX_PIN, 'Reference routing prefix witness changed')
        witness = json.loads(raw)
        for name, slot in PUBLIC.items():
            module = self.module(name)
            function = vars(module)[slot]
            self.bind(function, name, 'public-prefix')
            entry = witness['entrypoint_prefixes'][self.sources[name]['file']]
            source = Path(module.__file__).read_bytes()
            insertion = entry['insertion']; prefix = insertion['text'].encode(); offset = insertion['byte_offset']
            require(sha(source) == entry['current_sha256'] and source[offset:offset+len(prefix)] == prefix
                and sha(source[:offset]+source[offset+len(prefix):]) == entry['original_sha256'],
                'Reference public route did not restore its whole original source')
            start = source[:offset].count(b'\n') + 1
            self.public[id(function.__code__)] = (function.__code__, start, start + 4)
            # Nested old-body closures must not inherit prefix permission.
            for code in tuple(manager._nested_codes(function.__code__))[1:]: self.entries.pop(id(code), None)

    def entry(self, frame):
        row = self.entries.get(id(frame.f_code))
        if row is None: return None
        code, namespace, descriptor = row
        require(code is frame.f_code and namespace is frame.f_globals
            and sys.modules.get(descriptor['module']) is self.modules[descriptor['module']],
            'Reference guard frame has foreign globals or replaced module')
        return descriptor

    def product(self, frame):
        name = frame.f_globals.get('__name__', '')
        return name == 'biocompiler' or name.startswith('biocompiler.') or frame.f_code.co_filename.startswith(str(self.package) + '/')

    def starts(self, frame, entry):
        if entry is None: return False
        module, name = entry['module'], entry['qualname']
        return (entry['category'] == 'public-prefix' or
            module in ('biocompiler.core_pipeline_manager', 'biocompiler.core_reference_manager')
                and name.startswith(('CorePassManager.', 'ReferenceCorePassManager.')) or
            module == 'biocompiler.reference_backend' and name in ('ReferenceRoute.construct', 'ReferenceRoute.molecular'))


class RegistrationRecorder(registration.Recorder):
    """Retain the owning pair before a trace observer issues later inspections."""
    def observe(self, frame, event):
        if self.is_base(frame) and event == 'return':
            found=[row for row in self.pending if row['frame'] is frame]
            require(len(found)==1 and found[0]['entered'], 'Native delegation omitted its private entry')
            row=found[0]
            if row['call_entered']:
                require('guard_pair' in row, 'Native delegation lost its actual owning registration pair')
                request,reply=row['guard_pair']
                record=registration.proof(request.value,reply.value)
                record['request_sha256']=sha(request.frame[9:])
                record['reply_sha256']=sha(reply.frame[9:])
                self.seen.add((registration.TAG,canonical(record).decode()))
                self.pending.remove(row)
                return False
        return super().observe(frame,event)


class Guard:
    def __init__(self, observer=None):
        self.policy, self.observer = Policy(), observer
        self.seen, self.counts, self.active, self.routed = set(), Counter(), {}, []
        self.scheduling_counts = Counter()
        self.commands, self.pending = [], {}
        self.host_frames, self.overrides = {}, []
        self.observing = 0
        self.observation_count = 0
        self.observation_source = None
        self.delegation = RegistrationRecorder(self.seen)
        self.failure = None
        self.finished = False

    def observation(self, function, arguments):
        """Make real inspector frames visible from a trace callback on both runtimes.

        CPython3.11 needs its cached tracing flag refreshed inside call_tracing;
        reapplying the identical profiler does that without disabling the guard.
        """
        require(sys.getprofile() is self.callback, 'Reference observation lost its exact profiler')
        from biocompiler.core_reference_manager import ReferenceCorePassManager
        source = ROOT / 'tools/check_pipeline_reference_install.py'
        raw = source.read_bytes()
        module = sys.modules.get(getattr(function, '__module__', None))
        codes = tuple(manager._nested_codes(compile(raw, str(source), 'exec', dont_inherit=True)))
        require(type(function) is FunctionType and module is not None
            and Path(module.__file__).resolve() == source and function.__globals__ is vars(module)
            and vars(module).get('observed_inspection') is function
            and function.__qualname__ == 'observed_inspection'
            and function.__defaults__ is None and function.__kwdefaults__ is None and function.__closure__ is None
            and any(function.__code__ == code for code in codes),
            'Reference observation requires its exact source-bound inspection helper')
        require(type(arguments) is tuple and len(arguments) == 1 and type(arguments[0]) is ReferenceCorePassManager,
            'Reference observation requires its actual native manager')
        owner=arguments[0]
        for method in ('inspect_ordered_references','_inspection_state'):
            value=getattr(owner,method)
            expected=self.policy.lookup('biocompiler.core_pipeline_manager','CorePassManager.'+method)
            require(getattr(value,'__self__',None) is owner and getattr(value,'__func__',None) is expected,
                'Reference observation changed its actual native inspection method')
        descriptor={'file':'tools/check_pipeline_reference_install.py','sha256':sha(raw),
            'code_sha256':code_pin(function.__code__)}
        require(self.observation_source is None or self.observation_source==descriptor,
            'Reference observation source changed during execution')
        self.observation_source=descriptor
        self.observation_count+=1
        def invoke():
            sys.setprofile(self.callback)
            self.observing += 1
            try:
                return function(*arguments)
            finally:
                self.observing -= 1
                require(sys.getprofile() is self.callback, 'Reference observation replaced its profiler')
        return sys.call_tracing(invoke, ())

    def route_trace(self, frame):
        code, first, last = self.policy.public[id(frame.f_code)]
        previous = frame.f_trace
        row = {'module': frame.f_globals['__name__'], 'qualname': code.co_qualname,
            'lines': [], 'outcome': None}
        self.routed.append(row)
        def trace(current, event, argument):
            nonlocal previous
            try:
                require(current is frame and current.f_code is code, 'Reference route trace frame changed')
                if event == 'line':
                    require(first <= current.f_lineno <= last, 'Reference public route entered its original Python body')
                    row['lines'].append(current.f_lineno)
                if previous is not None: previous = previous(current, event, argument)
                if event == 'return': row['outcome'] = 'finished'
                return trace
            except BaseException as error:
                self.failure = error
                raise
        frame.f_trace = trace
        frame.f_trace_lines = True
        # No global trace may be set (focused controls). Installing an inert
        # one enables this local frame trace; the campaign owns its own tracer.
        if sys.gettrace() is None: sys.settrace(self.idle_trace)

    @staticmethod
    def idle_trace(frame, event, argument):
        return None

    def host_entry(self, frame):
        # Only the real helper's dynamic call can open the proposal lane.
        # A copied default is a replacement, not native semantic authority.
        host = self.policy.modules['biocompiler.core_reference_host']
        caller = frame.f_back
        if caller is None or caller.f_globals is not vars(host): return False
        role = ('generate' if caller.f_code is host.ReferenceHost.generate.__code__ else
                'emit' if caller.f_code is host.ReferenceHost.emit.__code__ else None)
        if role is None: return False
        function = caller.f_locals.get('function')
        expected = vars(host._CONSTRUCT if role == 'generate' else host._MOLECULAR)[
            'generate_construct' if role == 'generate' else 'emit_reference_sequence']
        default = host._GENERATOR.function if role == 'generate' else host._EMITTER.function
        if function is None or function is not expected or function is default: return False
        if type(function) is FunctionType:
            matches = frame.f_code is function.__code__ and frame.f_globals is function.__globals__
        else:
            # Callable instances (the original corpus uses Mock) must enter
            # their actual __call__ with that exact instance as self.
            method = next((vars(cls)['__call__'] for cls in type(function).__mro__ if '__call__' in vars(cls)), None)
            matches = (type(method) is FunctionType and frame.f_code is method.__code__
                and frame.f_globals is method.__globals__ and frame.f_locals.get('self') is function)
        if not matches: return False
        owners = []
        cursor = caller
        while cursor is not None:
            row = self.pending.get(id(cursor))
            if row is not None: owners.append(row)
            cursor = cursor.f_back
        require(owners, 'Reference host replacement lacks its owning native command')
        owner = owners[0][1]
        invocations = owner.session._handlers
        require(invocations, 'Reference host replacement lacks its actual native invocation')
        invocation = invocations[-1]
        row = {'role':role, 'session':owner.session._nonce,
            'command_sequence':invocation.sequence,
            'invocation_id':owner.session._invocations[-1], 'source':[]}
        self.host_frames[id(frame)] = (frame,row)
        self.overrides.append(row)
        return True

    def proposal_lane(self, frame):
        cursor = frame
        while cursor is not None:
            if id(cursor) in self.host_frames: return self.host_frames[id(cursor)][1]
            if id(cursor) in self.active: return False
            cursor = cursor.f_back
        return False

    def profile(self, frame, event, argument):
        try:
            if event == 'c_call' and argument is sys.setprofile:
                require(frame.f_globals is globals(), 'Reference execution guard was disabled')
            if event == 'c_call' and argument is sys.settrace and self.active:
                require(frame.f_globals is globals(), 'Reference public route tracing was disabled')
            if event == 'call' and (self.active or self.observing): self.host_entry(frame)
            entry = self.policy.entry(frame)
            if event == 'call' and self.policy.starts(frame, entry):
                self.active[id(frame)] = frame
                if entry['category'] == 'public-prefix': self.route_trace(frame)
            proposal = self.proposal_lane(frame)
            if (entry is not None and entry['module'] == 'biocompiler.core_pipeline_manager'
                    and entry['qualname'] == 'CorePassManager._call'):
                if event == 'call':
                    owner = frame.f_locals['self']
                    self.pending[id(frame)] = (frame, owner, len(owner.session.traffic), frame.f_locals['operation'])
                elif event == 'return':
                    current, owner, offset, operation = self.pending.pop(id(frame))
                    require(current is frame, 'Reference command frame identity changed')
                    response = owner.session.last_response
                    traffic = owner.session.traffic[offset:]
                    requests = [item for item in traffic if item.direction == 'client' and item.value['kind'] == 'command'
                        and response is not None and item.value['sequence'] == response.sequence]
                    replies = [item for item in traffic if item.direction == 'server' and item.value['kind'] == 'reply'
                        and response is not None and item.value['sequence'] == response.sequence]
                    require(len(requests) == len(replies) == 1 and requests[0].value['operation'] == operation,
                        'Reference command lacks its complete owning native reply')
                    request, reply = requests[0], replies[0]
                    if operation == 'register':
                        caller=frame.f_back
                        parents=[row for row in self.delegation.pending if caller is not None and caller.f_back is row['native_frame']]
                        require(len(parents)==1 and 'guard_pair' not in parents[0], 'Reference registration pair lacks its exact private caller')
                        parents[0]['guard_pair']=(request,reply)
                    self.commands.append({'session':request.value['session_id'], 'sequence':response.sequence,
                        'operation':operation, 'request_sha256':sha(request.frame[9:]), 'reply_sha256':sha(reply.frame[9:])})
            if self.active or self.observing:
                delegated = self.delegation.observe(frame, event)
                if event == 'call' and self.policy.product(frame):
                    require(proposal or delegated or entry is not None, 'Legacy Python reference authority is forbidden: ' +
                        str(frame.f_globals.get('__name__')) + '.' + frame.f_code.co_qualname)
                    if proposal and (entry is None or entry['category'] == 'conversion'):
                        path = Path(frame.f_code.co_filename)
                        source = {'module':frame.f_globals.get('__name__'), 'qualname':frame.f_code.co_qualname,
                            'code_sha256':code_pin(frame.f_code), 'file':str(path),
                            'source_sha256':sha(path.read_bytes()) if path.is_relative_to(self.policy.package) and path.is_file() else None}
                        proposal['source'].append(source)
                    elif not delegated:
                        if entry['category'] == 'conversion':
                            require(manager._conversion_ancestry(frame, self.policy.conversion_entries,
                                self.policy.conversion_roots), 'Reference semantic conversion lacks reviewed serializer ancestry')
                        self.counts[self.policy.keys[id(frame.f_code)]] += 1
                        if id(frame.f_code) in self.policy.scheduling_callees:
                            site = self.policy.scheduling_entry(frame)
                            if site is not None: self.scheduling_counts[site] += 1
                    self.seen.add((frame.f_globals.get('__name__'), frame.f_code.co_qualname))
            if event == 'return':
                self.active.pop(id(frame), None)
                self.host_frames.pop(id(frame), None)
            if self.previous_profile is not None: self.previous_profile(frame, event, argument)
        except BaseException as error:
            self.failure = error
            raise

    def evidence(self):
        require(self.finished and self.failure is None, 'Reference execution guard has no completed proof')
        return {'schema': SCHEMA, 'runtime': list(sys.version_info[:2]), 'python_version':sys.version, 'sources': self.policy.sources,
            'prefix_witness': PREFIX_PIN, 'commands': self.commands, 'inspection':{'source':self.observation_source,'count':self.observation_count}, 'host_overrides':self.overrides, 'calls': [{'frame': json.loads(key), 'count': count}
                for key, count in sorted(self.counts.items())], 'routes': self.routed,
            'scheduling': {'sites': self.policy.scheduling_sites,
                'counts': [{'site': name, 'count': count} for name, count in sorted(self.scheduling_counts.items())]},
            'delegation': [list(row) for row in sorted(self.seen) if row[0] == registration.TAG or row == registration.BASE]}


@contextmanager
def execution(observer=None):
    guard = Guard(observer)
    previous_import, previous_trace = builtins.__import__, sys.gettrace()
    guard.previous_profile = sys.getprofile()
    def imports(name, *args, **kwargs):
        if (guard.active or guard.observing) and (name == 'biocompiler' or name.startswith('biocompiler.')):
            require(name in guard.policy.modules or name in ('biocompiler', 'biocompiler.compiler'),
                'Unreviewed reference execution import: ' + name)
        return previous_import(name, *args, **kwargs)
    callback = guard.profile
    guard.callback = callback
    if observer is not None:
        require(vars(observer).get('guarded_observation') is None, 'Reference observer already has a guard owner')
        observer.guarded_observation = guard.observation
    builtins.__import__ = imports
    sys.setprofile(callback)
    try:
        yield guard
    finally:
        try:
            if guard.failure is not None: raise guard.failure
            require(sys.getprofile() is callback and builtins.__import__ is imports, 'Reference execution guard was disabled')
            require(not guard.active and not guard.pending and not guard.host_frames and not guard.observing, 'Reference execution guard has unclosed operation frames')
            guard.delegation.complete()
            require(all(row['outcome'] == 'finished' and row['lines'] for row in guard.routed),
                'Reference public route lacks its complete line proof')
            guard.finished = True
        finally:
            sys.setprofile(guard.previous_profile)
            builtins.__import__ = previous_import
            if observer is not None: observer.guarded_observation = None
            if sys.gettrace() == guard.idle_trace: sys.settrace(previous_trace)


def validate_scheduling(evidence, policy):
    """Authenticate the call-site subcensus without removing any raw counts."""
    require(evidence.get('schema') == SCHEMA, 'Reference scheduling requires the current guard schema')
    value = evidence.get('scheduling')
    require(type(value) is dict and set(value) == {'sites', 'counts'}
        and value['sites'] == policy.scheduling_sites and type(value['counts']) is list,
        'Reference scheduling call-site authority differs')
    sites = {site['name']: site for site in policy.scheduling_sites}
    totals = {}
    for row in evidence['calls']:
        require(type(row) is dict and set(row) == {'frame', 'count'}
            and type(row['count']) is int and row['count'] > 0, 'Malformed reference raw call count')
        key = canonical(row['frame']).decode()
        require(key not in totals, 'Repeated reference raw call count')
        totals[key] = row['count']
    reductions, names = Counter(), []
    for row in value['counts']:
        require(type(row) is dict and set(row) == {'site', 'count'} and type(row['site']) is str
            and row['site'] in sites and type(row['count']) is int and row['count'] > 0,
            'Malformed reference scheduling count')
        names.append(row['site'])
        require(canonical(sites[row['site']]['caller']).decode() in totals,
                'Reference scheduling site lacks its actual source-bound caller')
        key = canonical(sites[row['site']]['callee']).decode()
        reductions[key] += row['count']
        require(key in totals and reductions[key] <= totals[key],
                'Reference scheduling count exceeds its actual source-bound calls')
    require(names == sorted(set(names)), 'Repeated or unordered reference scheduling site')
    return reductions


def scheduling_projection(evidence):
    """Subtract only authenticated I/O-site occurrences from a validated guard.

    Every raw descriptor remains, including a zero residual for pure I/O helpers.
    The complete original census and call-site counts remain in the raw receipt.
    """
    reductions = validate_scheduling(evidence, Policy())
    result = json.loads(canonical(evidence))
    for row in result['calls']:
        row['count'] -= reductions[canonical(row['frame']).decode()]
    result['scheduling']['counts'] = []
    return result


def validate(evidence, frames, artifacts):
    require(type(evidence) is dict and set(evidence) == {'schema','runtime','python_version','sources','prefix_witness','commands','inspection','host_overrides','calls','routes','delegation','scheduling'}
        and evidence['schema'] == SCHEMA and evidence['runtime'] in ([3,11],[3,14])
        and evidence['runtime'] == list(sys.version_info[:2])
        and type(evidence['python_version']) is str and evidence['python_version'].startswith('.'.join(map(str,evidence['runtime'])) + '.'),
        'Reference execution proof schema/runtime differs')
    policy = Policy()
    require(evidence['sources'] == policy.sources and evidence['prefix_witness'] == PREFIX_PIN,
        'Reference execution proof source authority differs')
    allowed = {canonical(row[2]).decode() for row in policy.entries.values()}
    seen = set()
    for row in evidence['calls']:
        require(type(row) is dict and set(row) == {'frame','count'} and type(row['count']) is int and row['count'] > 0,
            'Malformed reference execution frame count')
        descriptor=row['frame']
        require(type(descriptor) is dict and set(descriptor)=={'module','qualname','line','code_sha256','category'}
            and type(descriptor['code_sha256']) is str and len(descriptor['code_sha256'])==64
            and all(char in '0123456789abcdef' for char in descriptor['code_sha256'])
            and type(descriptor['line']) is int, 'Malformed reference source/code frame')
        key = canonical(descriptor).decode()
        known = key in allowed
        require(known and key not in seen, 'Unknown or repeated reference execution frame')
        seen.add(key)
    validate_scheduling(evidence, policy)
    for row in evidence['routes']:
        require(type(row) is dict and set(row) == {'module','qualname','lines','outcome'} and row['module'] in PUBLIC
            and row['qualname'] == PUBLIC[row['module']] and row['outcome'] == 'finished', 'Malformed reference public route proof')
        code = vars(policy.modules[row['module']])[row['qualname']].__code__
        _, first, last = policy.public[id(code)]
        require(type(row['lines']) is list and row['lines'] == list(range(first,last+1)) and all(type(line) is int for line in row['lines']),
            'Reference public route proof includes original semantic body')
    for module,qualname,count in [('biocompiler.core_pipeline_manager','CorePassManager._call',len(evidence['commands']))] + [
            (module,qualname,sum(row['module']==module for row in evidence['routes'])) for module,qualname in PUBLIC.items()]:
        observed=sum(row['count'] for row in evidence['calls'] if row['frame']['module']==module and row['frame']['qualname']==qualname)
        require(observed==count, 'Reference guarded entry count differs from command/route receipts')
    inspection=evidence['inspection']
    require(type(inspection) is dict and set(inspection)=={'source','count'} and type(inspection['count']) is int
        and inspection['count']>=0, 'Malformed reference inspection proof')
    if inspection['count']:
        source=ROOT / 'tools/check_pipeline_reference_install.py'
        raw=source.read_bytes()
        codes=[code for code in manager._nested_codes(compile(raw,str(source),'exec',dont_inherit=True))
            if code.co_qualname=='observed_inspection']
        descriptor=inspection['source']
        require(type(descriptor) is dict and set(descriptor)=={'file','sha256','code_sha256'}
            and descriptor['file']=='tools/check_pipeline_reference_install.py' and descriptor['sha256']==sha(raw)
            and len(codes)==1 and descriptor['code_sha256']==code_pin(codes[0]),
            'Reference inspection helper source differs')
        require(sum(row['operation']=='inspect-ordered-references' for row in evidence['commands'])>=inspection['count'],
            'Reference observation lacks its actual native inspection commands')
    else:
        require(inspection['source'] is None, 'Unused reference observation source')
    expected, expected_overrides, all_invocations, all_outcomes = [], [], {}, {}
    for group in frames:
        rows = [(item['direction'], artifacts.raw(item['frame'])) for item in group]
        values = [(side, json.loads(raw[9:]), raw[9:]) for side,raw in rows]
        for side, request, raw in values:
            if side == 'server' and request['kind'] == 'invoke' and request['action'] in ('reference-generate','reference-emit'):
                key = (request['session_id'],request['invocation_id'])
                require(key not in all_invocations, 'Repeated reference host invocation')
                all_invocations[key] = request
                completions=[value for direction,value,_ in values if direction=='client' and value['kind']=='continue'
                    and value['invocation_id']==request['invocation_id']]
                require(len(completions)==1, 'Reference host invocation lacks its continuation')
                outcome=completions[0]['outcome']
                all_outcomes[key]=outcome
                if outcome['status']=='return' and type(outcome['value']) is dict and outcome['value'].get('kind')=='host':
                    expected_overrides.append(key)
            if side != 'client' or request['kind'] != 'command': continue
            replies = [(value, body) for direction,value,body in values if direction == 'server'
                and value['kind'] == 'reply' and value['session_id'] == request['session_id']
                and value['sequence'] == request['sequence']]
            require(len(replies) == 1 and replies[0][0]['request_sha256'] == sha(raw),
                'Reference guard command has no exact owning reply')
            expected.append({'session':request['session_id'], 'sequence':request['sequence'],
                'operation':request['operation'], 'request_sha256':sha(raw), 'reply_sha256':sha(replies[0][1])})
    require(sorted(map(canonical, evidence['commands'])) == sorted(map(canonical, expected)),
        'Reference guard command proof differs from complete native traffic')
    found=[]
    for row in evidence['host_overrides']:
        require(type(row) is dict and set(row)=={'role','session','command_sequence','invocation_id','source'}
            and row['role'] in ('generate','emit') and type(row['command_sequence']) is int
            and type(row['invocation_id']) is int, 'Malformed reference host proposal proof')
        key=(row['session'],row['invocation_id'])
        require(key in all_invocations and key not in found, 'Reference host proposal belongs to another invocation')
        request=all_invocations[key]
        outcome=all_outcomes[key]
        require(outcome['status']=='raise' or (outcome['status']=='return' and type(outcome['value']) is dict
            and outcome['value'].get('kind')=='host'), 'Reference proposal proof points at a native-default continuation')
        require(request['command_sequence']==row['command_sequence'] and request['action']=='reference-'+row['role'],
            'Reference host proposal changed its owning command or role')
        found.append(key)
        require(type(row['source']) is list, 'Malformed reference proposal source census')
        for source in row['source']:
            require(type(source) is dict and set(source)=={'module','qualname','code_sha256','file','source_sha256'},
                'Malformed untrusted proposal source frame')
            require(type(source['code_sha256']) is str and len(source['code_sha256'])==64,
                'Malformed untrusted proposal code identity')
            # These frames are explicitly proposal-only. They never receive a
            # transport/serializer permission or an acceptance claim.
    require(set(expected_overrides) <= set(found), 'Reference host output lacks its actual callback execution proof')
    registration.validate(evidence['delegation'], frames, artifacts)
    return evidence

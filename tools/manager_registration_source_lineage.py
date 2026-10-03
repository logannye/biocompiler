"""One exact native-delegation prefix; the complete old manager stays pinned."""
from __future__ import annotations
import ast
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys
from types import FunctionType

ROOT = Path(__file__).resolve().parents[1]
PATH = 'src/biocompiler/compiler/pipeline.py'
HISTORICAL = {PATH: '2b1dea35ac3c861f1e933cf7808a241f1f6596e59cc04ceb0ec32e4a54d27331'}
WITNESS = ROOT / 'tests/conformance/manager-registration-source-lineage-v1.json'
WITNESS_SHA256 = 'f00be511bd184aa4e4d743f2f9cf86ae819ff09c7fd795cd740bce8c9c3db157'
PREFIX = '''        from sys import modules
        native_module = modules.get("biocompiler.core_pipeline_manager")
        native_type = vars(native_module).get("CorePassManager") if native_module is not None else None
        if isinstance(native_type, type) and issubclass(type(self), native_type):
            return native_type._native_register(self, contract, producer, validators)
'''
ANCHOR = '''    def register(
        self,
        contract: PassContract,
        producer: Callable,
        validators: Mapping[str, Callable],
    ):
'''


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def load_witness():
    raw = WITNESS.read_bytes()
    require(sha(raw) == WITNESS_SHA256, 'Manager registration witness bytes differ')
    entry = json.loads(raw)
    require(set(entry) == {'schema', 'path', 'historical_sha256', 'historical_source',
        'routed_sha256', 'routed_source', 'prefix', 'anchor'} and
        entry['schema'] == 'biocompiler.manager-registration-source-lineage.v1' and
        entry['path'] == PATH and entry['prefix'] == PREFIX and entry['anchor'] == ANCHOR,
        'Manager registration witness inventory differs')
    verify_extension(entry, entry['routed_source'].encode(), HISTORICAL[PATH])
    return entry


def verify_extension(entry, current, historical_sha256):
    old, new = entry['historical_source'].encode(), entry['routed_source'].encode()
    require(historical_sha256 == HISTORICAL[PATH] == entry['historical_sha256'] == sha(old),
        'Historical manager registration bytes differ')
    require(current == new and sha(current) == entry['routed_sha256'], 'Routed manager registration bytes differ')
    require(old.count(ANCHOR.encode()) == 1 and PREFIX.encode() not in old and
        new == old.replace(ANCHOR.encode(), (ANCHOR + PREFIX).encode(), 1) and
        new.count(PREFIX.encode()) == 1 and new.replace(PREFIX.encode(), b'', 1) == old,
        'Manager registration prefix does not recover the entire original source')
    verify_structure(old, new)
    return {'path': PATH, 'historical_sha256': historical_sha256, 'current_sha256': sha(current),
        'kind': 'reviewed_native_manager_registration_prefix', 'witness_sha256': WITNESS_SHA256}


@lru_cache(maxsize=4)
def verify_structure(old, new):
    before, after = ast.parse(old), ast.parse(new)
    classes = [node for node in after.body if isinstance(node, ast.ClassDef) and node.name == 'PassManager']
    require(len(classes) == 1, 'Manager class census differs')
    methods = [node for node in classes[0].body if isinstance(node, ast.FunctionDef) and node.name == 'register']
    require(len(methods) == 1, 'Manager registration census differs')
    expected = ast.parse('def route():\n' + PREFIX).body[0].body
    require(ast.dump(ast.Module(body=methods[0].body[:4], type_ignores=[])) ==
        ast.dump(ast.Module(body=expected, type_ignores=[])), 'Manager registration route AST differs')
    del methods[0].body[:4]
    require(ast.dump(before) == ast.dump(after), 'Entire historical manager AST differs')


def verify_source(root, path, historical_sha256):
    require(path == PATH and historical_sha256 == HISTORICAL[PATH], 'Unreviewed manager registration source')
    current = (Path(root) / path).read_bytes()
    if sha(current) == historical_sha256:
        return {'path': path, 'historical_sha256': historical_sha256,
            'current_sha256': historical_sha256, 'kind': 'identical_bytes'}
    return verify_extension(load_witness(), current, historical_sha256)


def original_source():
    return load_witness()['historical_source'].encode()


def routed():
    return sha((ROOT / PATH).read_bytes()) != HISTORICAL[PATH]


@lru_cache(maxsize=16)
def compiled_source(raw, filename, optimize):
    from tools.check_pipeline_deferred_runtime import codes
    return tuple(codes(compile(raw, filename, 'exec', dont_inherit=True, optimize=optimize)))


def installed_route():
    """Bind the real routed function, its canonical namespace and installed code."""
    from tools.check_pipeline_deferred_runtime import codes, same_code
    module = sys.modules['biocompiler.compiler.pipeline']
    core = sys.modules['biocompiler.core_pipeline_manager']
    package = Path(sys.modules['biocompiler'].__file__).resolve().parent
    require(module.__name__ == 'biocompiler.compiler.pipeline' and core.__name__ == 'biocompiler.core_pipeline_manager'
        and Path(module.__file__).resolve() == package / 'compiler/pipeline.py'
        and Path(core.__file__).resolve() == package / 'core_pipeline_manager.py',
        'Installed registration modules escaped their canonical package')
    raw = Path(module.__file__).resolve().read_bytes()
    entry = load_witness()
    verify_extension(entry, raw, HISTORICAL[PATH])
    # A patched public slot is legitimate; the captured original code is found
    # from this exact source. The live frame must separately carry these globals.
    compiled = compiled_source(raw, str(module.__file__), sys.flags.optimize)
    matches = [code for code in compiled if code.co_qualname == 'PassManager.register']
    require(len(matches) == 1 and core.CorePassManager.__mro__[1] is module.PassManager,
        'Installed native registration class lineage differs')
    function = vars(core.CorePassManager)['_native_register']
    require(type(function) is FunctionType and function.__globals__ is vars(core),
        'Installed native registration entry has foreign globals')
    core_raw = Path(core.__file__).resolve().read_bytes()
    require(core_raw == (ROOT / 'src/biocompiler/core_pipeline_manager.py').read_bytes(),
        'Installed native registration source differs from reviewed source')
    actual = [code for code in compiled_source(core_raw, str(core.__file__), sys.flags.optimize)
        if code.co_qualname == function.__code__.co_qualname]
    require(len(actual) == 1 and same_code(actual[0], function.__code__),
        'Installed native registration entry differs from its source')
    return module, core, matches[0], function.__code__


# This helper is separately pinned by the immutable original build graph. It
# remains current for installed validation; only original-only child execution
# restores its exact historical implementation.
TOOL_PATH = 'tools/check_pipeline_session_install.py'
TOOL_HISTORICAL = 'd6ef07ae02b60130dafd0226be68631ef3f4003296e359849f444e44810271cd'
TOOL_WITNESS = 'tests/conformance/manager-registration-tool-lineage-v1.json'
TOOL_WITNESS_SHA256 = '635f083aa69afb240da3f3c15de50f31cc6672e404b0cd41ea3fb574731af474'
TOOL_LOADER = 'def source_tool(name):\n    """Load finite checkout proof tools without replacing installed products."""\n    require(name in (\'realization_source_lineage\', \'manager_registration_source_lineage\',\n        \'pipeline_registration_guard\', \'pipeline_original_counterpart\'), \'Unreviewed source proof tool\')\n    paths = list(sys.path)\n    try:\n        sys.path.insert(0, str(ROOT))\n        module = importlib.import_module(\'tools.\' + name)\n    finally:\n        sys.path[:] = paths\n    require(Path(module.__file__).resolve() == ROOT / \'tools\' / (name + \'.py\'),\n        \'Source proof tool origin differs\')\n    return module\n\n\n'
TOOL_OLD_LINE = '                self.original_sources[path] = sha(r.raw_file(ROOT / path))\n'
TOOL_NEW_LINE = '                self.original_sources[path] = pin\n'
TOOL_CHECK = '            source_tool("realization_source_lineage").verify_captured_source(ROOT, {"path": path, "sha256": pin})\n'


def verify_tool_extension(entry, current, historical_sha256):
    if current != entry['current_source'].encode():
        previous = restore_installed_tool(current)
        proof = verify_tool_extension(entry, previous, historical_sha256)
        return {**proof, 'current_sha256': sha(current), 'installed_layout': {
            'previous_sha256': sha(previous), 'current_sha256': sha(current),
            'witness_sha256': INSTALLED_TOOL_SHA256}}
    old, new = entry['historical_source'].encode(), entry['current_source'].encode()
    require(entry['schema'] == 'biocompiler.manager_registration_tool_lineage.v1'
        and entry['path'] == TOOL_PATH and historical_sha256 == TOOL_HISTORICAL == entry['historical_sha256'] == sha(old),
        'Original session helper identity differs')
    require(current == new and sha(current) == entry['current_sha256'], 'Current session helper bytes differ')
    require(old.count(TOOL_OLD_LINE.encode()) == 1 and TOOL_LOADER.encode() not in old and TOOL_CHECK.encode() not in old
        and new.count(TOOL_LOADER.encode()) == new.count(TOOL_CHECK.encode()) == new.count(TOOL_NEW_LINE.encode()) == 1
        and new.replace(TOOL_LOADER.encode(), b'', 1).replace(TOOL_CHECK.encode(), b'', 1)
            .replace(TOOL_NEW_LINE.encode(), TOOL_OLD_LINE.encode(), 1) == old,
        'Session helper extension does not recover the entire original source')
    return {'path': TOOL_PATH, 'historical_sha256': historical_sha256, 'current_sha256': sha(current),
        'kind': 'reviewed_original_source_helper_counterpart', 'witness_sha256': TOOL_WITNESS_SHA256}


def tool_witness():
    raw = (ROOT / TOOL_WITNESS).read_bytes()
    require(sha(raw) == TOOL_WITNESS_SHA256, 'Session helper witness bytes differ')
    entry = json.loads(raw)
    require(set(entry) == {'schema','path','historical_sha256','current_sha256','historical_source','current_source',
        'historical_revision','original_corpus','original_corpus_sha256'}
        and entry['historical_revision'] == 'b8120bfb1bb20ef89e8f722a7a425d8ae8a90a25'
        and entry['original_corpus'] == 'tests/conformance/pipeline-fixed-build-semantics-v1.json',
        'Session helper witness inventory differs')
    corpus_raw = (ROOT / entry['original_corpus']).read_bytes()
    require(sha(corpus_raw) == entry['original_corpus_sha256']
        and json.loads(corpus_raw)['source_files'][TOOL_PATH] == TOOL_HISTORICAL,
        'Original build corpus session helper pin differs')
    verify_tool_extension(entry, entry['current_source'].encode(), TOOL_HISTORICAL)
    return entry


def original_tool_source():
    return tool_witness()['historical_source'].encode()


def verify_tool_source(current, historical_sha256=TOOL_HISTORICAL):
    return verify_tool_extension(tool_witness(), current, historical_sha256)


# A separate exact counterpart preserves the first immutable helper witness.
INSTALLED_TOOL_WITNESS = 'tests/conformance/prebuilt-session-helper-lineage-v1.json'
INSTALLED_TOOL_SHA256 = '6c56211e5cb8bd779458b4f92a51fbb7d0d3c838fbd3be724eebf3a36edca38c'
INSTALLED_TOOL_INSERT = 'if __package__:\n    from .check_realization_binaries import executable_path as native_executable\nelse:\n    from check_realization_binaries import executable_path as native_executable\n\n'
INSTALLED_TOOL_BEFORE = '(args.native_root / ("biocompiler-" + role))'
INSTALLED_TOOL_AFTER = '(native_executable(args.native_root, role))'


def restore_installed_tool(current):
    raw = (ROOT / INSTALLED_TOOL_WITNESS).read_bytes()
    require(sha(raw) == INSTALLED_TOOL_SHA256, 'Installed session helper witness bytes differ')
    entry = json.loads(raw)
    require(set(entry) == {'schema','path','previous_sha256','current_sha256','previous_source','current_source','insert','before','after'}
        and entry['schema'] == 'biocompiler.prebuilt_session_helper_lineage.v1' and entry['path'] == TOOL_PATH
        and entry['insert'] == INSTALLED_TOOL_INSERT and entry['before'] == INSTALLED_TOOL_BEFORE
        and entry['after'] == INSTALLED_TOOL_AFTER, 'Installed helper counterpart inventory differs')
    old, new = entry['previous_source'].encode(), entry['current_source'].encode()
    require(current == new and sha(current) == entry['current_sha256']
        and sha(old) == entry['previous_sha256'], 'Installed helper whole source differs')
    require(old.count(INSTALLED_TOOL_BEFORE.encode()) == 1 and INSTALLED_TOOL_INSERT.encode() not in old
        and new.count(INSTALLED_TOOL_INSERT.encode()) == new.count(INSTALLED_TOOL_AFTER.encode()) == 1
        and new.replace(INSTALLED_TOOL_INSERT.encode(), b'', 1).replace(INSTALLED_TOOL_AFTER.encode(), INSTALLED_TOOL_BEFORE.encode(), 1) == old,
        'Installed helper extension does not recover the entire preceding source')
    require(old == tool_witness()['current_source'].encode(), 'Installed helper preceding authority differs')
    return old

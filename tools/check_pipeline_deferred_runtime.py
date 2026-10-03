"""Closed runtime correspondences for the immutable deferred Python oracle.

The raw captures are never rewritten. Installed source paths and two interpreter
frame differences receive separate, independently executed evidence. This is an
original-Python oracle check; it establishes no native-manager compatibility.
"""
from collections.abc import Mapping
from copy import deepcopy
import dis
from pathlib import Path
import sys
from types import CodeType, FunctionType

_import_path = list(sys.path)
try:
    from tools import capture_pipeline_deferred_semantics as original
finally:
    sys.path[:] = _import_path

PIN = "21ff92c3b384a0be705733e768abfc510acc58f529065eff06af63bc77fce444"
SOURCE_PATHS = {
    "biocompiler.compiler.pipeline": "src/biocompiler/compiler/pipeline.py",
    "biocompiler.ir.intent": "src/biocompiler/ir/intent.py",
}
TRACE_FIELDS = ("original_traceback", "required_user_traceback_tail")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def codes(code):
    yield code
    for constant in code.co_consts:
        if type(constant) is CodeType:
            yield from codes(constant)


def frame_name(filename, oracle):
    path = Path(filename)
    try:
        return path.resolve().relative_to(oracle.ROOT).as_posix()
    except ValueError:
        return path.name


def code_evidence(code, oracle):
    return {"name": code.co_name, "qualname": code.co_qualname,
        "first_line": code.co_firstlineno, "filename": code.co_filename,
        "bytecode_sha256": oracle.sha(code.co_code),
        "line_table_sha256": oracle.sha(code.co_linetable)}


def same_code(left, right):
    # CodeType equality deliberately ignores some execution metadata, including
    # stack size. Bind every public execution field and nested code explicitly.
    fields = ("co_argcount", "co_posonlyargcount", "co_kwonlyargcount", "co_nlocals",
        "co_stacksize", "co_flags", "co_code", "co_names", "co_varnames", "co_filename",
        "co_name", "co_qualname", "co_firstlineno", "co_linetable", "co_exceptiontable",
        "co_freevars", "co_cellvars")
    return all(getattr(left, name) == getattr(right, name) for name in fields) and \
        len(left.co_consts) == len(right.co_consts) and all(
            same_code(a, b) if type(a) is type(b) is CodeType else type(a) is type(b) and a == b
            for a, b in zip(left.co_consts, right.co_consts))


def oracle_authority(frozen, oracle):
    """Bind the actual comparison producer, not merely its on-disk namesake."""
    logical = "tools/capture_pipeline_deferred_semantics.py"
    path = Path(oracle.__file__).resolve()
    raw = path.read_bytes()
    require(oracle.sha(raw) == frozen["source_files"][logical], "Loaded oracle source changed")
    compiled = compile(raw, str(oracle.__file__), "exec", dont_inherit=True, optimize=sys.flags.optimize)
    verified = []
    def function(value, code):
        if isinstance(value, property):
            value = value.fget
        require(type(value) is FunctionType and value.__globals__ is vars(oracle)
            and Path(value.__code__.co_filename).resolve() == path
            and same_code(value.__code__, code), "Loaded oracle function differs from its frozen source")
        verified.append(code_evidence(value.__code__, oracle))
    for code in compiled.co_consts:
        if type(code) is not CodeType:
            continue
        value = vars(oracle).get(code.co_name)
        if code.co_flags & 2:  # CO_NEWLOCALS identifies a function, unlike a class body.
            function(value, code)
        else:
            require(isinstance(value, type), "Loaded oracle class was replaced")
            for method in code.co_consts:
                if type(method) is CodeType:
                    function(vars(value).get(method.co_name), method)
    require(verified, "Loaded oracle has no source-bound functions")
    return {"path": str(path), "sha256": oracle.sha(raw), "codes": verified}


def source_authority(frozen, oracle):
    origins, layout, source_codes = {}, {}, {}
    for module_name, logical in SOURCE_PATHS.items():
        module = sys.modules[module_name]
        path = Path(module.__file__).resolve()
        raw = path.read_bytes()
        require(oracle.sha(raw) == frozen["source_files"][logical],
            "Loaded original module differs from its frozen source: " + module_name)
        roots = [module.freeze_json] if module_name.endswith("intent") else [module._document,
            *(value.fget if isinstance(value, property) else value
              for value in vars(module.PassManager).values()
              if isinstance(value, property) or type(value) is FunctionType)]
        require(all(function.__globals__ is vars(module) for function in roots),
            "Loaded original function uses substituted module globals")
        actual = [code for function in roots for code in codes(function.__code__)]
        compiled = list(codes(compile(raw, str(module.__file__), "exec", dont_inherit=True, optimize=sys.flags.optimize)))
        for code in actual:
            require(Path(code.co_filename).resolve() == path,
                "Loaded original code points outside its verified source")
            matching = [item for item in compiled if item.co_qualname == code.co_qualname
                and item.co_firstlineno == code.co_firstlineno]
            require(len(matching) == 1 and same_code(matching[0], code),
                "Loaded original function differs from same-runtime source compilation")
        label = frame_name(str(path), oracle)
        require(label in (logical, Path(logical).name), "Unexpected original source installation label")
        require(label not in layout, "Ambiguous original source frame origin")
        layout[label] = logical
        source_codes[logical] = actual
        origins[logical] = {"module": module_name, "path": str(path), "frame_label": label,
            "sha256": oracle.sha(raw), "codes": [code_evidence(code, oracle) for code in actual]}
    return origins, layout, source_codes


def traceback_nodes(error):
    current = BaseException.__dict__["__traceback__"].__get__(error)
    result = []
    while current is not None:
        result.append(current)
        current = current.tb_next
    return result


def instruction(node):
    candidates = [item for item in dis.get_instructions(node.tb_frame.f_code, show_caches=True)
        if item.offset == node.tb_lasti]
    require(len(candidates) == 1, "Runtime traceback has no corresponding bytecode instruction")
    value = candidates[0]
    require(value.positions.lineno == node.tb_lineno, "Traceback line disagrees with runtime instruction position")
    return {"offset": value.offset, "opname": value.opname, "line": value.positions.lineno,
        "end_line": value.positions.end_lineno, "column": value.positions.col_offset,
        "end_column": value.positions.end_col_offset}


def runtime_primitives(oracle):
    from biocompiler.ir.intent import freeze_json
    import _collections_abc
    class ProbeError(Exception):
        pass
    class BrokenMapping(Mapping):
        def __iter__(self):
            return iter(("x",))
        def __len__(self):
            return 1
        def __getitem__(self, key):
            raise ProbeError("mapping lookup")
    try:
        freeze_json(BrokenMapping())
    except ProbeError as error:
        mapping_nodes = traceback_nodes(error)
        mapping_raw = oracle.trace_frames(error.__traceback__)
    else:
        raise AssertionError("Independent mapping primitive stopped raising")
    items_code = _collections_abc.ItemsView.__iter__.__code__
    library = Path(_collections_abc.__file__).resolve()
    library_raw = library.read_bytes()
    library_codes = list(codes(compile(library_raw, items_code.co_filename, "exec", dont_inherit=True,
        optimize=sys.flags.optimize)))
    matches = [code for code in library_codes if code.co_qualname == items_code.co_qualname]
    require(len(matches) == 1 and same_code(matches[0], items_code),
        "Loaded mapping iterator differs from the bound standard-library source")
    freeze_codes = list(codes(freeze_json.__code__))
    selected = [index for index, node in enumerate(mapping_nodes)
        if node.tb_frame.f_code in freeze_codes or node.tb_frame.f_code is items_code]
    require(selected and selected == list(range(selected[0], selected[-1] + 1)),
        "Independent mapping primitive has an unexpected intermediate frame")
    segment = [mapping_raw[index] for index in selected]
    expected_names = ["freeze_json", "<dictcomp>", "__iter__"] if sys.version_info[:2] == (3, 11) else ["freeze_json", "__iter__"]
    require([frame["function"] for frame in segment] == expected_names,
        "Unreviewed runtime mapping frame shape")
    require(all(frame["line"] == 31 for frame in segment[:-1]), "Mapping source expression moved")
    mapping_proof = {"raw_traceback": mapping_raw, "segment": segment,
        "instructions": [instruction(mapping_nodes[index]) for index in selected],
        "stdlib": {"path": str(library), "sha256": oracle.sha(library_raw),
            "code": code_evidence(items_code, oracle)}}

    generators = [code for code in codes(oracle.pipeline.PassManager.run.__code__)
        if code.co_name == "<genexpr>" and code.co_firstlineno == 817]
    require(len(generators) == 1 and generators[0].co_freevars == ("obligations",),
        "Original obligation generator changed")
    class BrokenIterator:
        def __iter__(self):
            return self
        def __next__(self):
            raise ProbeError("obligation iteration")
    def cell(value):
        return (lambda: value).__closure__[0]
    generator = FunctionType(generators[0], vars(oracle.pipeline), closure=(cell({}),))
    try:
        next(generator(iter(BrokenIterator())))
    except ProbeError as error:
        generator_nodes = traceback_nodes(error)
        generator_raw = oracle.trace_frames(error.__traceback__)
    else:
        raise AssertionError("Independent original generator stopped raising")
    selected = [index for index, node in enumerate(generator_nodes) if node.tb_frame.f_code is generators[0]]
    require(len(selected) == 1, "Independent generator frame was omitted or duplicated")
    position = instruction(generator_nodes[selected[0]])
    require(position["opname"] == "FOR_ITER", "Obligation exception moved from iterator advancement")
    require(position["line"] == (817 if sys.version_info[:2] == (3, 11) else 822),
        "Unreviewed obligation generator instruction position")
    return {"mapping": mapping_proof, "obligations": {"raw_traceback": generator_raw,
        "frame": generator_raw[selected[0]], "instruction": position,
        "code": code_evidence(generators[0], oracle)}}


def compare_current(frozen, current, *, oracle=original):
    """Return raw evidence and the exact, closed comparison correspondence."""
    def digest(document):
        return oracle.sha(oracle.canonical({key: value for key, value in document.items()
            if key != "inventory_fingerprint"}))
    require(frozen.get("inventory_fingerprint") == digest(frozen) == PIN,
        "Immutable original deferred-semantics inventory changed")
    require(current.get("inventory_fingerprint") == digest(current), "Current deferred inventory changed")
    require(sys.implementation.name == "cpython" and sys.version_info[:2] in ((3, 11), (3, 14)),
        "Unreviewed deferred-oracle Python runtime")
    require(current["capture_runtime"] == {"implementation": sys.implementation.name,
        "python": list(sys.version_info[:2])}, "Current oracle has another runtime")
    require(current["source_files"] == frozen["source_files"], "Original source inventory changed")
    for path, pin in frozen["source_files"].items():
        require(oracle.sha((oracle.ROOT / path).read_bytes()) == pin, "Frozen original source changed: " + path)
    oracle_origin = oracle_authority(frozen, oracle)
    independent = oracle.capture()
    require(oracle.canonical(current) == oracle.canonical(independent),
        "Complete current original capture differs from independent same-runtime execution")
    required = frozen["runtime_counterparts"]
    require(current["runtime_counterparts"] == required, "Original runtime allowance changed")
    origins, layout, source_codes = source_authority(frozen, oracle)
    primitives = runtime_primitives(oracle)
    projected, expected = deepcopy(current), deepcopy(frozen)
    correspondences = []
    for case in projected["cases"]:
        for event in case["events"]:
            if event["outcome"] != "raised":
                continue
            for field in TRACE_FIELDS:
                for index, frame in enumerate(event["exception"][field]):
                    if frame["file"] not in layout:
                        continue
                    logical = layout[frame["file"]]
                    require(any(code.co_name == frame["function"] and frame["line"] in
                        {line for _, _, line in code.co_lines()} for code in source_codes[logical]),
                        "Original traceback names an unbound source function or line")
                    if frame["file"] != logical:
                        before = deepcopy(frame)
                        frame["file"] = logical
                        correspondences.append({"case": case["id"], "event": event["id"], "field": field,
                            "index": index, "rule": "verified_installed_source_path", "actual": before,
                            "captured": deepcopy(frame), "source": logical})
    def trace(document, identity):
        return next(case for case in document["cases"] if case["id"] == identity)["events"][1]["exception"]["original_traceback"]
    def logical(frame):
        return {**frame, "file": layout.get(frame["file"], frame["file"])}
    actual = trace(projected, "proposal:mapping_raises")
    captured = trace(frozen, "proposal:mapping_raises")
    segment = list(map(logical, primitives["mapping"]["segment"]))
    require(actual[3:3+len(segment)] == segment and captured[3:5] == [
        {"file": SOURCE_PATHS["biocompiler.ir.intent"], "function": "freeze_json", "line": 31},
        {"file": "<frozen _collections_abc>", "function": "__iter__", "line": 883}],
        "Mapping traceback differs from its independent runtime primitive")
    if segment != captured[3:5]:
        correspondences.append({"case": "proposal:mapping_raises", "event": 1,
            "field": "original_traceback", "index": 3, "rule": "independent_mapping_iteration",
            "actual": deepcopy(segment), "captured": deepcopy(captured[3:5]), "primitive": "mapping"})
        actual[3:3+len(segment)] = deepcopy(captured[3:5])
    actual = trace(projected, "proposal:obligation_exhaustion_raises")
    captured = trace(frozen, "proposal:obligation_exhaustion_raises")
    require(actual[3] == logical(primitives["obligations"]["frame"]) and captured[3] ==
        {"file": SOURCE_PATHS["biocompiler.compiler.pipeline"], "function": "<genexpr>", "line": 822},
        "Obligation traceback differs from its independent runtime instruction")
    if actual[3] != captured[3]:
        correspondences.append({"case": "proposal:obligation_exhaustion_raises", "event": 1,
            "field": "original_traceback", "index": 3, "rule": "independent_generator_instruction",
            "actual": deepcopy(actual[3]), "captured": deepcopy(captured[3]), "primitive": "obligations"})
        actual[3] = deepcopy(captured[3])
    current_case = next(case for case in current["cases"] if case["id"] == "proposal:unhashable_status")
    try:
        [] in {"candidate", "no_candidate_found"}
    except TypeError as error:
        primitive = {"class": oracle.qualified(error), "message": BaseException.__str__(error), "args": list(error.args)}
    else:
        raise AssertionError("Original unhashable primitive stopped raising")
    exception = current_case["events"][1]["exception"]
    require(exception["class"] == primitive["class"] == "builtins.TypeError" and
        exception["message"] == primitive["message"] and exception["args"] ==
        {"$sequence": "tuple", "items": primitive["args"]}, "Original exception differs from the independent primitive")
    expected["capture_runtime"] = deepcopy(current["capture_runtime"])
    selected = next(case for case in expected["cases"] if case["id"] == "proposal:unhashable_status")["events"][1]["exception"]
    selected["message"], selected["args"]["items"][0] = exception["message"], exception["args"]["items"][0]
    projected["inventory_fingerprint"] = digest(projected)
    expected["inventory_fingerprint"] = digest(expected)
    require(oracle.canonical(projected) == oracle.canonical(expected),
        "Complete original observations differ outside the closed runtime correspondences")
    return {"captured_runtime": frozen["capture_runtime"], "current_runtime": current["capture_runtime"],
        "exact_paths": required[0], "complete_captured_case": next(case for case in frozen["cases"]
            if case["id"] == "proposal:unhashable_status"), "complete_current_case": current_case,
        "independent_original_manager_case": next(case for case in independent["cases"]
            if case["id"] == "proposal:unhashable_status"), "runtime_primitive": primitive,
        "complete_raw_current": deepcopy(current), "independent_raw_current": independent,
        "source_origins": origins, "oracle_origin": oracle_origin, "frame_correspondences": correspondences,
        "runtime_primitives": primitives, "comparison_capture": projected, "expected_capture": expected}

"""Offline verification of the closed, source-bound deferred runtime receipt.

Foreign interpreter execution remains a claim of the pinned hosted producer and
its tested revision/run/runtime receipt. This verifier independently rehashes
retained source/code evidence and reconstructs the complete comparison; it does
not infer execution from a supplied PASS or from a self-supplied projection.
"""
from copy import deepcopy
import dis
import hashlib
import json
from pathlib import Path
import platform
import re
import sys

_import_path = list(sys.path)
try:
    if __package__:
        from . import check_pipeline_deferred_runtime as runtime
    else:
        # The frozen runtime checker imports its source-bound oracle through
        # the tools package. Supply only this checkout's root for that import,
        # then restore the caller's path (including absolute CLI invocations).
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from tools import check_pipeline_deferred_runtime as runtime
finally:
    sys.path[:] = _import_path

SCHEMA = "biocompiler.pipeline_deferred_runtime_authority.v1"
# Generated from the source-bound CPython 3.11.15 and 3.14.6 interpreters. These
# are finite compiler-site authorities, not open-ended runtime normalizations.
# Other patch versions must reproduce these exact sites in hosted validation.
CODE_PINS = {'3.11': {'oracle_code_census': '27e0aa91a24fe3ef4178a12fddf2053096766540f5f23e36146785bc81cd9123',
          'primitive_sites': '0b6f5cd89a2d73548133a3f1234029398a677350745801d3587f0ae6d130ed2f',
          'selected_code': {'freeze_dictcomp': 'd6188f800fc11ea097c3900b9cbde91fd1f489ccef1c9a48db7f444c3c01ccde',
                            'freeze_json': 'ee44d52bd1a5964676adcbf01e1f309e3092422efe87e70f8f65708bd285c259',
                            'mapping_iterator': '941153c76d96842d70bdf3bbd6388eced403630878065f3b60d2de777a2fcf5e',
                            'obligation_generator': '14286a1a2b1fa827d3d732ccb4c31ab29afaa06c4268dabfc6275efe3ef718eb'},
          'source_code_census': 'b040631aebea16a5332acb709b8a66f01514f691510ac4b5b36ada73fd09f66c',
          'stdlib_source': 'ec646ef7e27aae261adef3c57b9d18822c6526b3e9562dabb9f3cb4e6803066c'},
 '3.14': {'oracle_code_census': 'a433ab9f3d95a272df31fc6b62b866284a90c269f788237a16a7c33d68dc397a',
          'primitive_sites': 'abe385114f7c32a354e57fbeb08fa3bdf760de455f0a706a8dd98568988e2d55',
          'selected_code': {'freeze_json': 'f96dabcd25ec57b8890200943591a087c02195601c368302c1829b7e3fec8c83',
                            'mapping_iterator': 'cf8cd77959e600e79208323729aa139c93fed892a9373b3d7aa64562cc0f50ec',
                            'obligation_generator': 'be7a126e6fe4dade4ccb19cdecdb67559f5d5f189172dd6945b9f74f0e0f01dd'},
          'source_code_census': 'c185ba6f2ecf588d240099f9c21e70c097893dcd8561363626bd7b604e71d33d',
          'stdlib_source': '50b68b76687edc29824e5d735914b9c9ebb5145b663ba4ab7fce273283356a1c'}}
MESSAGES = {"3.11": "unhashable type: 'list'",
    "3.14": "cannot use 'list' as a set element (unhashable type: 'list')"}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def raw_digest(value):
    return hashlib.sha256(value).hexdigest()


def code_capture(code):
    instructions = []
    for item in dis.get_instructions(code, show_caches=True):
        position = item.positions
        instructions.append({"offset": item.offset, "opcode": item.opcode, "opname": item.opname,
            "argument": item.arg, "line": position.lineno, "end_line": position.end_lineno,
            "column": position.col_offset, "end_column": position.end_col_offset})
    return {"name": code.co_name, "qualname": code.co_qualname, "first_line": code.co_firstlineno,
        "filename": code.co_filename, "bytecode": code.co_code.hex(), "line_table": code.co_linetable.hex(),
        "exception_table": code.co_exceptiontable.hex(), "instructions": instructions}


def without_filename(code):
    return {key: value for key, value in code.items() if key != "filename"}


def census(codes):
    return [without_filename(code) for code in codes]


def capture_authority(*, oracle=None):
    """Retain actual bytes; call only on the runtime that executed the oracle."""
    import _collections_abc
    from biocompiler.ir import intent
    oracle = runtime.original if oracle is None else oracle
    frozen = json.loads(oracle.OUTPUT.read_bytes())
    oracle_origin = runtime.oracle_authority(frozen, oracle)
    origins, _, _ = runtime.source_authority(frozen, oracle)
    sources = {}
    for logical, module in [(logical, sys.modules[name]) for name, logical in runtime.SOURCE_PATHS.items()] + [
        ("tools/capture_pipeline_deferred_semantics.py", oracle),
        ("tools/check_pipeline_deferred_runtime.py", runtime),
        ("stdlib/_collections_abc.py", _collections_abc)]:
        path = Path(module.__file__).resolve()
        raw = path.read_bytes()
        sources[logical] = {"path": str(path), "filename": str(module.__file__),
            "sha256": raw_digest(raw), "hex": raw.hex()}
    generator = next(code for code in runtime.codes(oracle.pipeline.PassManager.run.__code__)
        if code.co_name == "<genexpr>" and code.co_firstlineno == 817)
    selected = {"freeze_json": code_capture(intent.freeze_json.__code__),
        "mapping_iterator": code_capture(_collections_abc.ItemsView.__iter__.__code__),
        "obligation_generator": code_capture(generator)}
    dictionaries = [code for code in runtime.codes(intent.freeze_json.__code__) if code.co_name == "<dictcomp>"]
    if dictionaries:
        require(len(dictionaries) == 1, "Unexpected freeze_json comprehension inventory")
        selected["freeze_dictcomp"] = code_capture(dictionaries[0])
    primitives = runtime.runtime_primitives(oracle)
    return {"schema": SCHEMA, "python_version": platform.python_version(),
        "implementation": sys.implementation.name, "root": str(oracle.ROOT.resolve()),
        "sources": sources, "selected_code": selected,
        "primitive_sites": {"mapping": primitives["mapping"]["instructions"],
            "obligations": primitives["obligations"]["instruction"]},
        "source_code_census": {logical: census(origin["codes"]) for logical, origin in origins.items()},
        "oracle_code_census": census(oracle_origin["codes"])}


def pin_authority(authority):
    """Recipe for review-time generation of the closed table, never acceptance."""
    return {"selected_code": {name: digest(without_filename(code)) for name, code in authority["selected_code"].items()},
        "source_code_census": digest(authority["source_code_census"]),
        "oracle_code_census": digest(authority["oracle_code_census"]),
        "primitive_sites": digest(authority["primitive_sites"]),
        "stdlib_source": authority["sources"]["stdlib/_collections_abc.py"]["sha256"]}


def inventory(value):
    return digest({key: item for key, item in value.items() if key != "inventory_fingerprint"})


def current_frame(code, line, authority):
    filename = code["filename"]
    root = authority["root"].rstrip("/") + "/"
    return {"file": filename[len(root):] if filename.startswith(root) else filename.rsplit("/", 1)[-1],
        "function": code["name"], "line": line}


def verify_code_evidence(evidence, code):
    expected = {"name": code["name"], "qualname": code["qualname"], "first_line": code["first_line"],
        "filename": code["filename"], "bytecode_sha256": raw_digest(bytes.fromhex(code["bytecode"])),
        "line_table_sha256": raw_digest(bytes.fromhex(code["line_table"]))}
    require(evidence == expected, "Runtime primitive code evidence differs from retained pinned code")


def verify_instruction(instruction, code):
    matches = [item for item in code["instructions"] if item["offset"] == instruction.get("offset")]
    require(len(matches) == 1, "Primitive instruction is absent from the pinned position table")
    expected = {key: value for key, value in matches[0].items() if key not in ("opcode", "argument")}
    require(instruction == expected, "Primitive instruction differs from pinned bytecode position")


def validate_retained(frozen, current, proof, *, python_version):
    """Rebuild a foreign-runtime comparison using closed checked evidence only."""
    require(type(python_version) is str and re.fullmatch(r"3\.(11|14)\.[0-9]+", python_version),
        "Unreviewed foreign Python runtime")
    minor = ".".join(python_version.split(".")[:2])
    require(frozen.get("inventory_fingerprint") == inventory(frozen) == runtime.PIN,
        "Immutable original deferred oracle changed")
    require(current.get("inventory_fingerprint") == inventory(current), "Retained raw oracle inventory changed")
    expected_proof_fields = {"captured_runtime", "current_runtime", "exact_paths", "complete_captured_case",
        "complete_current_case", "independent_original_manager_case", "runtime_primitive", "complete_raw_current",
        "independent_raw_current", "source_origins", "oracle_origin", "frame_correspondences", "runtime_primitives",
        "comparison_capture", "expected_capture", "capture_authority"}
    require(type(proof) is dict and set(proof) == expected_proof_fields, "Retained runtime proof fields changed")
    require(current == proof["complete_raw_current"] == proof["independent_raw_current"],
        "Complete raw and independent original captures differ")
    require(current["source_files"] == frozen["source_files"] and current["runtime_counterparts"] == frozen["runtime_counterparts"],
        "Original source inventory or exception allowance changed")
    actual_runtime = {"implementation": "cpython", "python": list(map(int, minor.split(".")))}
    require(current["capture_runtime"] == proof["current_runtime"] == actual_runtime
        and proof["captured_runtime"] == frozen["capture_runtime"], "Foreign runtime metadata contradicts its matrix slot")
    authority = proof["capture_authority"]
    require(type(authority) is dict and set(authority) == {"schema", "python_version", "implementation", "root", "sources",
        "selected_code", "source_code_census", "oracle_code_census", "primitive_sites"} and authority["schema"] == SCHEMA
        and authority["python_version"] == python_version and authority["implementation"] == "cpython"
        and type(authority["root"]) is str and authority["root"].startswith("/"), "Foreign capture authority is incomplete")
    expected_sources = {*runtime.SOURCE_PATHS.values(), "tools/capture_pipeline_deferred_semantics.py",
        "tools/check_pipeline_deferred_runtime.py", "stdlib/_collections_abc.py"}
    require(type(authority["sources"]) is dict and set(authority["sources"]) == expected_sources,
        "Retained source byte inventory changed")
    source_bytes = {}
    for logical, source in authority["sources"].items():
        require(type(source) is dict and set(source) == {"path", "filename", "sha256", "hex"}
            and all(type(value) is str for value in source.values()) and source["path"].startswith("/")
            and source["filename"].startswith("/"), "Malformed retained source origin")
        require(len(source["hex"]) <= 2_000_000 and re.fullmatch(r"(?:[0-9a-f]{2})*", source["hex"]),
            "Retained source bytes are malformed or unbounded")
        raw = bytes.fromhex(source["hex"])
        require(raw_digest(raw) == source["sha256"], "Retained source byte hash differs")
        if logical in frozen["source_files"]:
            require(source["sha256"] == frozen["source_files"][logical], "Retained original source differs from frozen authority")
        elif logical == "tools/check_pipeline_deferred_runtime.py":
            require(raw == Path(runtime.__file__).read_bytes(), "Retained runtime producer differs from this pinned verifier")
        source_bytes[logical] = raw
    require(minor in CODE_PINS and pin_authority(authority) == CODE_PINS[minor],
        "Foreign bytecode, position table or source-code census differs from reviewed runtime pins")
    codes = authority["selected_code"]
    require(set(codes) == {"freeze_json", "mapping_iterator", "obligation_generator"} |
        ({"freeze_dictcomp"} if minor == "3.11" else set()), "Foreign selected-code inventory differs")
    code_sources = {"freeze_json": "src/biocompiler/ir/intent.py", "freeze_dictcomp": "src/biocompiler/ir/intent.py",
        "obligation_generator": "src/biocompiler/compiler/pipeline.py"}
    for name, code in codes.items():
        if name == "mapping_iterator":
            require(code["filename"] == "<frozen _collections_abc>", "Standard-library code origin changed")
        else:
            require(code["filename"] == authority["sources"][code_sources[name]]["filename"], "Selected code uses another source origin")
    # Both supported runtimes execute exactly this standard-library expression.
    # Its line is independently tied to retained bytes and pinned instructions.
    library_lines = source_bytes["stdlib/_collections_abc.py"].decode().splitlines()
    iterator_line = 861 if minor == "3.11" else 883
    require(library_lines[iterator_line-3:iterator_line] == ["    def __iter__(self):",
        "        for key in self._mapping:", "            yield (key, self._mapping[key])"],
        "Retained mapping iterator source or line changed")
    origins = proof["source_origins"]
    require(type(origins) is dict and set(origins) == set(runtime.SOURCE_PATHS.values()), "Original loaded source origins changed")
    layout = {}
    for module, logical in runtime.SOURCE_PATHS.items():
        origin, source = origins[logical], authority["sources"][logical]
        require(type(origin) is dict and set(origin) == {"module", "path", "frame_label", "sha256", "codes"}
            and origin["module"] == module and origin["path"] == source["path"] and origin["sha256"] == source["sha256"],
            "Original module origin is not bound to retained source bytes")
        root = authority["root"].rstrip("/") + "/"
        label = source["path"][len(root):] if source["path"].startswith(root) else logical.rsplit("/", 1)[-1]
        require(label in (logical, logical.rsplit("/", 1)[-1]) and origin["frame_label"] == label,
            "Loaded source pathname correspondence changed")
        require(census(origin["codes"]) == authority["source_code_census"][logical]
            and all(code["filename"] == source["filename"] for code in origin["codes"]), "Loaded source code census changed")
        layout[label] = logical
    oracle_origin = proof["oracle_origin"]
    oracle_source = authority["sources"]["tools/capture_pipeline_deferred_semantics.py"]
    require(type(oracle_origin) is dict and set(oracle_origin) == {"path", "sha256", "codes"}
        and oracle_origin["path"] == oracle_source["path"] and oracle_origin["sha256"] == oracle_source["sha256"]
        and census(oracle_origin["codes"]) == authority["oracle_code_census"]
        and all(code["filename"] == oracle_source["filename"] for code in oracle_origin["codes"]),
        "Original independent observer code census changed")
    primitives = proof["runtime_primitives"]
    require(type(primitives) is dict and set(primitives) == {"mapping", "obligations"}, "Runtime primitive inventory changed")
    mapping = primitives["mapping"]
    require(type(mapping) is dict and set(mapping) == {"raw_traceback", "segment", "instructions", "stdlib"},
        "Retained mapping primitive is incomplete")
    selected = ["freeze_json"] + (["freeze_dictcomp"] if minor == "3.11" else []) + ["mapping_iterator"]
    mapping_segment = [current_frame(codes[name], iterator_line if name == "mapping_iterator" else 31, authority) for name in selected]
    require(mapping["segment"] == mapping_segment and len(mapping["instructions"]) == len(selected),
        "Mapping primitive frame segment differs from its pinned sites")
    require(mapping["instructions"] == authority["primitive_sites"]["mapping"],
        "Mapping exception selected a different pinned-code instruction")
    for name, position in zip(selected, mapping["instructions"]):
        verify_instruction(position, codes[name])
    library = mapping["stdlib"]
    require(type(library) is dict and set(library) == {"path", "sha256", "code"}
        and library["path"] == authority["sources"]["stdlib/_collections_abc.py"]["path"]
        and library["sha256"] == authority["sources"]["stdlib/_collections_abc.py"]["sha256"], "Standard-library primitive source was rebound")
    verify_code_evidence(library["code"], codes["mapping_iterator"])
    obligations = primitives["obligations"]
    require(type(obligations) is dict and set(obligations) == {"raw_traceback", "frame", "instruction", "code"},
        "Retained obligation primitive is incomplete")
    generator_line = 817 if minor == "3.11" else 822
    generator_frame = current_frame(codes["obligation_generator"], generator_line, authority)
    require(obligations["frame"] == generator_frame and obligations["instruction"]["opname"] == "FOR_ITER",
        "Obligation primitive moved from its pinned iterator site")
    require(obligations["instruction"] == authority["primitive_sites"]["obligations"],
        "Obligation exception selected a different pinned-code instruction")
    verify_instruction(obligations["instruction"], codes["obligation_generator"])
    verify_code_evidence(obligations["code"], codes["obligation_generator"])
    # The producer helper is source-pinned above. Derive its three exact trace
    # sites from that source, preserving the complete primitive traceback too.
    producer_lines = source_bytes["tools/check_pipeline_deferred_runtime.py"].decode().splitlines()
    def line_of(fragment):
        matches = [index+1 for index, line in enumerate(producer_lines) if line.strip() == fragment]
        require(len(matches) == 1, "Pinned primitive source site is ambiguous")
        return matches[0]
    producer_file = "tools/check_pipeline_deferred_runtime.py"
    def helper_frame(name, fragment):
        return {"file": producer_file, "function": name, "line": line_of(fragment)}
    require(mapping["raw_traceback"] == [helper_frame("runtime_primitives", "freeze_json(BrokenMapping())"),
        *mapping_segment, helper_frame("__getitem__", 'raise ProbeError("mapping lookup")')],
        "Complete mapping primitive traceback changed")
    require(obligations["raw_traceback"] == [helper_frame("runtime_primitives", "next(generator(iter(BrokenIterator())))"),
        generator_frame, helper_frame("__next__", 'raise ProbeError("obligation iteration")')],
        "Complete obligation primitive traceback changed")
    projected, expected = deepcopy(current), deepcopy(frozen)
    changes = []
    for case in projected["cases"]:
        for event in case["events"]:
            if event["outcome"] != "raised":
                continue
            for field in runtime.TRACE_FIELDS:
                for index, frame in enumerate(event["exception"][field]):
                    logical = layout.get(frame["file"])
                    if logical is not None and frame["file"] != logical:
                        before = deepcopy(frame)
                        frame["file"] = logical
                        changes.append({"case": case["id"], "event": event["id"], "field": field, "index": index,
                            "rule": "verified_installed_source_path", "actual": before, "captured": deepcopy(frame), "source": logical})
    def case(document, identity):
        return next(value for value in document["cases"] if value["id"] == identity)
    def trace(document, identity):
        return case(document, identity)["events"][1]["exception"]["original_traceback"]
    actual, captured = trace(projected, "proposal:mapping_raises"), trace(frozen, "proposal:mapping_raises")
    segment = [{**frame, "file": layout.get(frame["file"], frame["file"])} for frame in mapping_segment]
    require(actual[3:3+len(segment)] == segment, "Original mapping exception differs from its independent primitive")
    if segment != captured[3:5]:
        changes.append({"case": "proposal:mapping_raises", "event": 1, "field": "original_traceback", "index": 3,
            "rule": "independent_mapping_iteration", "actual": deepcopy(segment), "captured": deepcopy(captured[3:5]), "primitive": "mapping"})
        actual[3:3+len(segment)] = deepcopy(captured[3:5])
    actual, captured = trace(projected, "proposal:obligation_exhaustion_raises"), trace(frozen, "proposal:obligation_exhaustion_raises")
    require(actual[3] == {**generator_frame, "file": layout.get(generator_frame["file"], generator_frame["file"])},
        "Original obligation exception differs from the pinned runtime primitive")
    if actual[3] != captured[3]:
        changes.append({"case": "proposal:obligation_exhaustion_raises", "event": 1, "field": "original_traceback", "index": 3,
            "rule": "independent_generator_instruction", "actual": deepcopy(actual[3]), "captured": deepcopy(captured[3]), "primitive": "obligations"})
        actual[3] = deepcopy(captured[3])
    message = MESSAGES[minor]
    primitive = {"class": "builtins.TypeError", "message": message, "args": [message]}
    require(proof["runtime_primitive"] == primitive, "Runtime TypeError primitive differs from the reviewed interpreter site")
    current_case = case(current, "proposal:unhashable_status")
    error = current_case["events"][1]["exception"]
    require(error["class"] == primitive["class"] and error["message"] == message and
        error["args"] == {"$sequence": "tuple", "items": [message]}, "Original runtime exception differs from its primitive")
    selected = case(expected, "proposal:unhashable_status")["events"][1]["exception"]
    selected["message"], selected["args"]["items"][0] = message, message
    expected["capture_runtime"] = actual_runtime
    expected["inventory_fingerprint"], projected["inventory_fingerprint"] = inventory(expected), inventory(projected)
    require(projected == expected, "Complete retained observations differ outside the independently rebuilt correspondence")
    require(proof["frame_correspondences"] == changes and proof["comparison_capture"] == projected
        and proof["expected_capture"] == expected, "Supplied comparison projection or correspondence was forged")
    require(proof["exact_paths"] == frozen["runtime_counterparts"][0]
        and proof["complete_captured_case"] == case(frozen, "proposal:unhashable_status")
        and proof["complete_current_case"] == proof["independent_original_manager_case"] == current_case,
        "Retained whole-case counterpart evidence changed")
    return {"comparison_capture": projected, "expected_capture": expected,
        "frame_correspondences": changes, "python_version": python_version,
        "execution_authority": "source_and_run_bound_hosted_producer;offline_rehash_and_closed_comparison_reconstruction"}

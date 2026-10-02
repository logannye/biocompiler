#!/usr/bin/env python3
"""Check the reviewed OCaml link graph and fail closed on dependency expansion.

This static gate does not build OCaml or prove semantic independence. It records
actual Dune edges, their transitive closure, and source identities; a native build
and the independent conformance/mutation suite remain required hosted gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_LIBRARIES = frozenset({"digestif", "zarith", "unix"})
# New libraries/dependencies require deliberate policy review, even when harmless.
LIBRARIES = {
    "bioc_synthetic_producer": ("lib/synthetic_producer/dune", {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "zarith"}, "producer"),
    "bioc_realization_checker": ("lib/realization_checker/dune", {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_semantics", "bioc_candidate_runtime", "zarith"}, "checker"),
    "bioc_candidate_runtime": ("lib/candidate_runtime/dune", {"bioc_wire", "bioc_domain", "zarith"}, "candidate_runtime"),
    "bioc_producer_service": ("lib/producer_service/dune", {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_compiler", "bioc_service"}, "producer"),
    "bioc_wire": ("lib/wire/dune", {"digestif", "zarith"}, "trusted_primitive"),
    "bioc_domain": ("lib/domain/dune", {"bioc_wire", "zarith", "digestif"}, "trusted_domain"),
    "bioc_semantics": ("lib/semantics/dune", {"bioc_wire", "bioc_domain", "zarith"}, "source_semantics"),
    "bioc_source_adapter": ("lib/source_adapter/dune", {"bioc_wire", "bioc_domain", "bioc_semantics", "bioc_checker", "zarith"}, "source_semantics"),
    "bioc_compiler": ("lib/compiler/dune", {"bioc_wire", "bioc_domain", "bioc_checker", "zarith"}, "compiler"),
    "bioc_checker": ("lib/checker/dune", {"bioc_wire", "bioc_domain", "zarith"}, "checker"),
    "bioc_service": ("lib/service/dune", {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "zarith", "unix"}, "checker_service"),
}
EXECUTABLES = {
    "biocompiler-core": ("bin/core/dune", {"bioc_wire", "bioc_service", "bioc_producer_service"}, "core_entrypoint"),
    "biocompiler-verify": ("bin/verify/dune", {"bioc_wire", "bioc_service"}, "verifier"),
}
TESTS = {
    "test_verification_workflow_authority": {"bioc_wire", "bioc_service", "bioc_domain", "bioc_checker", "bioc_realization_checker", "zarith"},
    "test_artifact_io": {"bioc_wire", "bioc_service", "bioc_checker", "bioc_realization_checker", "unix", "zarith"},
    "test_verification_workflow_service": {"bioc_wire", "bioc_service", "bioc_domain", "bioc_checker", "bioc_realization_checker", "zarith"},
    "test_synthetic_generator": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "bioc_synthetic_producer", "zarith"},
    "test_synthetic_selection": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "bioc_synthetic_producer", "zarith"},
    "test_synthetic_components": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "bioc_synthetic_producer", "zarith"},
    "test_synthetic_producers_corpus": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "bioc_synthetic_producer", "zarith"},

    "test_synthetic_candidate_check": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "zarith"},
    "test_synthetic_provenance": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "zarith"},
    "test_component_assembly_check": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "zarith"},
    "test_synthetic_acceptance_corpus": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "zarith"},

    'test_synthetic_authority': {'bioc_domain', 'zarith', 'bioc_wire'},
    'test_synthetic_authority_corpus': {'bioc_domain', 'zarith', 'bioc_wire'},
    'test_composition_evidence': {'bioc_domain', 'zarith', 'bioc_wire'},
    'test_composition_check': {'bioc_domain', 'zarith', 'bioc_checker', 'bioc_wire'},
    'test_component_selection': {'bioc_domain', 'zarith', 'bioc_compiler', 'bioc_checker', 'bioc_wire'},
    'test_component_behavior_check': {'bioc_domain', 'zarith', 'bioc_realization_checker', 'bioc_checker', 'bioc_wire', 'bioc_candidate_runtime'},
    'test_component_acceptance_corpus': {'bioc_domain', 'zarith', 'bioc_compiler', 'bioc_realization_checker', 'bioc_checker', 'bioc_wire'},

    "test_realization_request": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "zarith"},
    "test_realization_check": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "zarith"},
    "test_realization_monitor": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "zarith"},
    "test_realization_checks_corpus": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "zarith"},
    "test_mechanism": {"bioc_wire", "bioc_domain", "zarith"},
    "test_model_execution_data": {"bioc_wire", "bioc_domain", "zarith"},
    "test_synthetic_model": {"bioc_wire", "bioc_domain", "bioc_candidate_runtime", "zarith"},
    "test_candidate_runtime_corpus": {"bioc_wire", "bioc_domain", "bioc_candidate_runtime", "zarith"},
    "test_component_registry": {"bioc_wire", "bioc_domain", "zarith"},
    "test_realization_contract": {"bioc_wire", "bioc_domain", "zarith"},
    "test_realization_evidence": {"bioc_wire", "bioc_domain", "zarith"},
    "test_admission": {"bioc_wire", "bioc_domain", "bioc_checker", "zarith"},
    "test_realization_foundation_corpus": {"bioc_wire", "bioc_domain", "bioc_checker", "zarith"},
    "test_observation_map": {"bioc_wire", "bioc_domain"},
    "test_composition": {"bioc_wire", "bioc_domain", "zarith"},
    "test_component_assembly": {"bioc_wire", "bioc_domain"},
    "test_component_execution": {"bioc_wire", "bioc_domain", "bioc_candidate_runtime"},
    "test_component_runtime_corpus": {"bioc_wire", "bioc_domain", "bioc_candidate_runtime", "zarith"},
    "test_producer_protocol": {"bioc_wire", "bioc_domain", "bioc_service", "bioc_producer_service"},
    "test_construction_producer": {"bioc_wire", "bioc_domain", "bioc_compiler", "bioc_checker", "zarith"},
    "test_source_execution": {"bioc_wire", "bioc_domain", "bioc_compiler", "bioc_checker", "zarith"},
    "test_architecture_matching": {"bioc_wire", "bioc_domain", "bioc_compiler", "bioc_checker", "zarith"},
    "test_architecture_producer": {"bioc_wire", "bioc_domain", "bioc_compiler", "bioc_checker", "zarith"},
    "test_source_transport": {"bioc_wire", "bioc_domain", "bioc_semantics", "bioc_checker", "bioc_source_adapter", "zarith"},
    "test_architecture_check": {"bioc_wire", "bioc_domain", "bioc_checker", "zarith"},
    "test_work_budget": {"bioc_wire", "bioc_checker", "zarith"},
    "test_architecture_build": {"bioc_wire", "bioc_domain", "zarith"},
    "test_circuit_bindings": {"bioc_wire", "bioc_domain", "bioc_checker", "zarith"},
    "test_architecture_controls_check": {"bioc_wire", "bioc_domain", "bioc_checker", "zarith"},
    "test_architecture_deployment_check": {"bioc_wire", "bioc_domain", "bioc_checker", "zarith"},
    "test_wire": {"bioc_wire", "zarith"},
    "test_workflow_wire": {"bioc_wire"},
    "test_verification_workflow_records": {"bioc_wire", "bioc_domain", "zarith"},
    "test_verification_exploration": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "zarith"},
    "test_synthetic_verification_workflow": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "zarith"},
    "test_realization_workflow_corpus": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "bioc_synthetic_producer", "zarith"},
    "test_intent": {"bioc_wire", "bioc_domain", "bioc_checker"},
    "test_protocol": {"bioc_wire", "bioc_service"},
    "test_realization_protocol": {"bioc_service", "bioc_wire", "bioc_checker", "zarith"},
    "test_domain": {"bioc_wire", "bioc_domain"},
    "test_build_request": {"bioc_wire", "bioc_domain", "zarith"},
    "test_behavior": {"bioc_wire", "bioc_domain", "zarith"},
    "test_molecule_coordinates": {"bioc_wire", "bioc_domain", "zarith"},
    "test_circuit_request": {"bioc_wire", "bioc_domain", "zarith"},
    "test_lowering_check": {"bioc_wire", "bioc_domain", "bioc_checker", "zarith"},
    "test_runtime_number": {"bioc_wire", "bioc_domain", "zarith"},
    "test_execution_data": {"bioc_wire", "bioc_domain", "zarith"},
    "test_reference": {"bioc_wire", "bioc_domain", "bioc_semantics", "zarith"},
    "test_pinned_identity": {"bioc_wire", "bioc_domain"},
    "test_component_contract": {"bioc_wire", "bioc_domain", "zarith"},
    "test_molecular_record": {"bioc_wire", "bioc_domain", "zarith"},
    "test_molecule_chemistry": {"bioc_wire", "bioc_domain"},
    "test_lowering": {"bioc_wire", "bioc_domain", "bioc_compiler", "bioc_checker"},
    "test_architecture_deployment": {"bioc_wire", "bioc_domain", "zarith"},
    "test_component": {"bioc_wire", "bioc_domain", "zarith"},
    "test_human_wrappers": {"bioc_wire", "bioc_domain", "zarith"},
    "test_molecule": {"bioc_wire", "bioc_domain", "zarith"},
    "test_molecule_set": {"bioc_wire", "bioc_domain", "zarith"},
    "test_payload_structure": {"bioc_wire", "bioc_domain"},
    "test_architecture_contract": {"bioc_wire", "bioc_domain", "zarith"},
    "test_molecular_transitions": {"bioc_wire", "bioc_domain", "zarith"},
    "test_construction": {"bioc_wire", "bioc_domain", "zarith"},
    "test_construction_artifact": {"bioc_wire", "bioc_domain", "zarith"},
    "test_payload_structure_check": {"bioc_wire", "bioc_domain", "bioc_checker", "zarith"},
    'test_architecture_domains': {'bioc_wire', 'bioc_domain', 'zarith'},
    'test_transition_check': {'bioc_wire', 'bioc_domain', 'bioc_checker', 'zarith'},
    'test_construction_assessment': {'bioc_wire', 'bioc_domain'},
    'test_construction_check': {'bioc_wire', 'bioc_domain', 'bioc_checker', 'zarith'},
    'test_source_manifest': {'bioc_wire', 'bioc_domain', 'zarith'},
    'test_source_check': {'bioc_wire', 'bioc_domain', 'bioc_checker', 'zarith'},
}
# One reviewed POSIX primitive duplicates inherited descriptors and verifies
# their original access flags. No paths, processes or dynamic code are exposed.
ARTIFACT_STUB = "core/lib/service/artifact_fd_stubs.c"
ARTIFACT_STUB_SHA256 = "e03ea4cf89ec58e218a67948c30559197f71856d4d7f882effb9311d2b067a2d"
ARTIFACT_EXTERNAL = 'external duplicate_checked : int -> int -> bool -> Unix.file_descr = "bioc_artifact_duplicate_checked"'
ARTIFACT_UNIX = frozenset({"file_descr", "Unix_error", "close", "fstat", "S_REG", "st_kind", "st_size",
                          "st_dev", "st_ino", "lseek", "SEEK_SET", "read", "single_write_substring"})
ARTIFACT_TEST_UNIX = ARTIFACT_UNIX | frozenset({"openfile", "O_RDONLY", "O_WRONLY", "O_RDWR", "O_CREAT",
    "O_TRUNC", "O_APPEND", "O_CLOEXEC", "O_NONBLOCK", "write", "stat", "unlink", "pipe", "link"})

PRODUCER_ROLES = frozenset({"compiler", "matcher", "selection", "emitter", "assembler", "producer"})
# Reconstruction is an independent checker's implementation detail. Consumers
# can request assessment/replay, but cannot obtain an expected candidate to emit.
PRIVATE_MODULES = {"bioc_checker": ["construction_reconstruction", "architecture_reconstruction"],
                   "bioc_realization_checker": ["realization_monitor", "synthetic_provenance", "synthetic_component_authority"]}
TOKEN = re.compile(r'\s+|;[^\n]*(?:\n|$)|\(|\)|"(?:\\.|[^"\\])*"|[^\s();"]+')
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_']*|\.")


class BoundaryError(ValueError):
    """The current source graph exceeds the reviewed boundary policy."""


def sexps(text):
    """Parse Dune's ordinary atoms/lists; dynamic forms are rejected downstream."""
    tokens, offset = [], 0
    while offset < len(text):
        match = TOKEN.match(text, offset)
        if match is None:
            raise BoundaryError(f"Unsupported Dune syntax at offset {offset}")
        token = match.group()
        offset = match.end()
        if token.isspace() or token.startswith(";"):
            continue
        if token.startswith('"'):
            try:
                token = json.loads(token)
            except json.JSONDecodeError as exc:
                raise BoundaryError("Unsupported Dune quoted atom") from exc
        tokens.append(token)
    root, stack = [], []
    current = root
    for token in tokens:
        if token == "(":
            child = []
            current.append(child)
            stack.append(current)
            current = child
        elif token == ")":
            if not stack:
                raise BoundaryError("Unmatched Dune closing parenthesis")
            current = stack.pop()
        else:
            current.append(token)
    if stack:
        raise BoundaryError("Unclosed Dune list")
    if any(not isinstance(item, list) or not item for item in root):
        raise BoundaryError("Dune requires nonempty top-level stanzas")
    return root


def fields(stanza, allowed):
    result = {}
    for field in stanza[1:]:
        if not isinstance(field, list) or not field or not isinstance(field[0], str):
            raise BoundaryError("Malformed Dune field")
        key = field[0]
        if key not in allowed or key in result:
            raise BoundaryError(f"Unreviewed or duplicate Dune field: {key}")
        if any(not isinstance(value, str) or "%{" in value for value in field[1:]):
            raise BoundaryError(f"Dynamic Dune field requires review: {key}")
        result[key] = field[1:]
    return result


def one(values, key):
    value = values.get(key, [])
    if len(value) != 1:
        raise BoundaryError(f"Expected exactly one Dune {key}")
    return value[0]


def validate_graph(graph, roles, external=EXTERNAL_LIBRARIES):
    """Enforce semantic roles on transitive dependencies, not name substrings."""
    if set(graph) != set(roles):
        raise BoundaryError("Every graph node needs exactly one reviewed role")
    closure, visiting = {}, set()

    def visit(name):
        if name in closure:
            return closure[name]
        if name in visiting:
            raise BoundaryError(f"Cyclic Dune dependency at {name}")
        visiting.add(name)
        found = set()
        for dependency in graph[name]:
            found.add(dependency)
            if dependency in graph:
                found.update(visit(dependency))
            elif dependency not in external:
                raise BoundaryError(f"Unreviewed external or missing local dependency: {dependency}")
        visiting.remove(name)
        closure[name] = found
        return found

    for name in sorted(graph):
        dependencies = visit(name)
        dependency_roles = {roles[dependency] for dependency in dependencies if dependency in roles}
        role = roles[name]
        if role in {"checker", "checker_service", "verifier"} and dependency_roles & PRODUCER_ROLES:
            raise BoundaryError(f"{name} transitively depends on a producer: {sorted(dependencies)}")
        if role == "candidate_runtime" and "source_semantics" in dependency_roles:
            raise BoundaryError(f"{name} depends on source reference execution")
        if role == "candidate_runtime" and dependency_roles & (PRODUCER_ROLES | {"checker", "checker_service", "verifier", "core_entrypoint"}):
            raise BoundaryError(f"{name} depends on producer or acceptance authority")
        if role == "source_semantics" and "candidate_runtime" in dependency_roles:
            raise BoundaryError(f"{name} depends on reconstructed candidate execution")
    return {name: sorted(dependencies) for name, dependencies in sorted(closure.items())}


def ocaml_tokens(text):
    """Ignore strings and nested comments before checking escape/module tokens."""
    result, index = [], 0
    while index < len(text):
        if text.startswith("(*", index):
            depth, index = 1, index + 2
            while index < len(text) and depth:
                if text.startswith("(*", index):
                    depth, index = depth + 1, index + 2
                elif text.startswith("*)", index):
                    depth, index = depth - 1, index + 2
                else:
                    index += 1
            if depth:
                raise BoundaryError("Unclosed OCaml comment")
        elif text[index] == '"':
            index += 1
            while index < len(text) and text[index] != '"':
                index += 2 if text[index] == "\\" else 1
            if index >= len(text):
                raise BoundaryError("Unclosed OCaml string")
            index += 1
        elif text[index] == "{" and re.match(r"\{[a-z_]*\|", text[index:]):
            opening = re.match(r"\{([a-z_]*)\|", text[index:])
            closing = "|" + opening.group(1) + "}"
            end = text.find(closing, index + len(opening.group()))
            if end < 0:
                raise BoundaryError("Unclosed OCaml quoted string")
            index = end + len(closing)
        elif text[index] == "'" and re.match(r"'(?:\\(?:[0-9]{3}|x[0-9a-fA-F]{2}|.|)|[^'\\])'", text[index:]):
            # Character literals are not identifiers; type variables remain tokens.
            char = re.match(r"'(?:\\(?:[0-9]{3}|x[0-9a-fA-F]{2}|.|)|[^'\\])'", text[index:])
            index += len(char.group())
        else:
            match = IDENTIFIER.match(text, index)
            if match:
                result.append(match.group())
                index = match.end()
            else:
                index += 1
    return result


def source_boundary(path, allowed_libraries, *, owner=None):
    source = path.read_text(encoding="utf-8")
    tokens = ocaml_tokens(source)
    referenced = set()
    for index, token in enumerate(tokens):
        for library, modules in PRIVATE_MODULES.items():
            for module in modules:
                public_spelling = module[:1].upper() + module[1:]
                if token == public_spelling and owner != library:
                    raise BoundaryError(f"Private checker reconstruction referenced outside {library} in {path.name}")
                if token == public_spelling and path.suffix == ".mli" and path.stem not in modules:
                    raise BoundaryError(f"Private checker reconstruction leaked through public interface {path.name}")
        if token == "external":
            if (owner != "bioc_service" or path.name != "artifact_io.ml" or tokens.count("external") != 1
                    or re.findall(r"(?ms)^external .*?(?=^let |^module |^type |\Z)", source)
                    != [ARTIFACT_EXTERNAL + "\n"]):
                raise BoundaryError(f"Unreviewed native/process/dynamic-code escape {token} in {path.name}")
        if token in {"Dynlink", "Obj", "Marshal"}:
            raise BoundaryError(f"Unreviewed native/process/dynamic-code escape {token} in {path.name}")
        if token == "Unix":
            members = (ARTIFACT_UNIX if owner == "bioc_service" and path.name == "artifact_io.ml"
                       else ARTIFACT_TEST_UNIX if owner == "test:test_artifact_io" else frozenset())
            if (tokens[index:index + 2] != ["Unix", "."] or index + 2 >= len(tokens)
                    or tokens[index + 2] not in members):
                raise BoundaryError(f"Unreviewed native/process/dynamic-code escape Unix in {path.name}")
        if token == "Sys":
            reviewed = {"argv"}
            if owner in {"test:test_architecture_check", "test:test_source_transport", "test:test_architecture_producer", "test:test_construction_producer", "test:test_candidate_runtime_corpus", "test:test_component_runtime_corpus", "test:test_realization_foundation_corpus", "test:test_realization_checks_corpus", "test:test_component_acceptance_corpus", "test:test_synthetic_authority_corpus", "test:test_synthetic_acceptance_corpus", "test:test_synthetic_producers_corpus", "test:test_realization_workflow_corpus"}:
                # The test-only document corpus must reject undeclared files.
                # Production code gains no filesystem or process permission.
                reviewed.add("readdir")
            if tokens[index:index + 2] != ["Sys", "."] or index + 2 >= len(tokens) or tokens[index + 2] not in reviewed:
                raise BoundaryError(f"Unreviewed Sys access in {path.name}")
        if token.startswith("Bioc_"):
            library = token[:1].lower() + token[1:]
            if library not in allowed_libraries:
                raise BoundaryError(f"Undeclared local module dependency {token} in {path.name}")
            referenced.add(library)
    return sorted(referenced)


def check_boundaries(root: Path):
    root = root.resolve()
    core = root / "core"
    project_path = core / "dune-project"
    project = sexps(project_path.read_text(encoding="utf-8"))
    implicit = [stanza for stanza in project if stanza[0] == "implicit_transitive_deps"]
    if implicit != [["implicit_transitive_deps", "false"]]:
        raise BoundaryError("Dune must explicitly disable implicit_transitive_deps")
    allowed_project = {"lang", "name", "generate_opam_files", "implicit_transitive_deps", "package"}
    if any(stanza[0] not in allowed_project for stanza in project):
        raise BoundaryError("Unreviewed Dune project extension")
    graph, roles, locations, tests = {}, {}, {}, {}
    source_files = {"core/dune-project": hashlib.sha256(project_path.read_bytes()).hexdigest()}
    dune_paths = sorted(path for path in core.rglob("dune") if "_build" not in path.relative_to(core).parts)
    for path in dune_paths:
        relative = path.relative_to(core).as_posix()
        source_files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        for stanza in sexps(path.read_text(encoding="utf-8")):
            kind = stanza[0]
            if kind == "env":
                if relative != "dune" or stanza != ["env", ["_", ["flags", [":standard", "-w", "+a-4-40-42-44-45-48-70", "-warn-error", "+a-4-40-42-44-45-48-70"]]]]:
                    raise BoundaryError("Unreviewed Dune environment flags")
                continue
            if kind not in {"library", "executable", "test"}:
                raise BoundaryError(f"Unreviewed Dune stanza {kind} in {relative}")
            allowed = {"name", "libraries", "private_modules"} if kind == "library" else {"name", "public_name", "package", "libraries"} if kind == "executable" else {"name", "modules", "libraries"}
            actions = []
            if kind == "test":
                actions = [field for field in stanza[1:]
                           if isinstance(field, list) and field and field[0] == "action"]
                stanza = [stanza[0], *(field for field in stanza[1:] if field not in actions)]
            if kind == "library" and relative == "lib/service/dune":
                stubs = [field for field in stanza[1:] if isinstance(field, list) and field and field[0] == "foreign_stubs"]
                if stubs != [["foreign_stubs", ["language", "c"], ["names", "artifact_fd_stubs"]]]:
                    raise BoundaryError("Changed reviewed artifact descriptor primitive")
                stanza = [stanza[0], *(field for field in stanza[1:] if field not in stubs)]
            values = fields(stanza, allowed)
            dependencies = values.get("libraries", [])
            if len(dependencies) != len(set(dependencies)):
                raise BoundaryError(f"Duplicate Dune dependency in {relative}")
            dependencies = set(dependencies)
            name = one(values, "name")
            if kind == "library":
                if name not in LIBRARIES:
                    raise BoundaryError(f"Unreviewed Dune library: {name}")
                expected_path, expected_dependencies, role = LIBRARIES[name]
                if values.get("private_modules", []) != PRIVATE_MODULES.get(name, []):
                    raise BoundaryError(f"Changed private module boundary for {name}")
                key = name
            elif kind == "executable":
                public_name = one(values, "public_name")
                if public_name not in EXECUTABLES or name != "main" or one(values, "package") != "biocompiler_core":
                    raise BoundaryError(f"Unreviewed Dune executable: {public_name}")
                expected_path, expected_dependencies, role = EXECUTABLES[public_name]
                key = "executable:" + public_name
            else:
                if relative != "test/dune" or name not in TESTS or values.get("modules") != [name]:
                    raise BoundaryError(f"Unreviewed native test stanza: {name}")
                fixture_variables = {
                    "test_candidate_runtime_corpus": "%{env:BIOCOMPILER_CANDIDATE_RUNTIME_CORPUS=missing}",
                    "test_component_runtime_corpus": "%{env:BIOCOMPILER_COMPONENT_RUNTIME_CORPUS=missing}",
                    "test_realization_foundation_corpus": "%{env:BIOCOMPILER_REALIZATION_FOUNDATION_CORPUS=missing}",
                    "test_realization_checks_corpus": "%{env:BIOCOMPILER_REALIZATION_CHECKS_CORPUS=missing}",
                    "test_component_acceptance_corpus": "%{env:BIOCOMPILER_COMPONENT_ACCEPTANCE_CORPUS=missing}",
                    "test_synthetic_authority_corpus": "%{env:BIOCOMPILER_SYNTHETIC_AUTHORITY_CORPUS=missing}",
                    "test_synthetic_acceptance_corpus": "%{env:BIOCOMPILER_SYNTHETIC_ACCEPTANCE_CORPUS=missing}",
                    "test_synthetic_producers_corpus": "%{env:BIOCOMPILER_SYNTHETIC_PRODUCERS_CORPUS=missing}",
                    "test_realization_workflow_corpus": "%{env:BIOCOMPILER_REALIZATION_WORKFLOW_CORPUS=missing}",
                }
                expected_actions = ([["action", ["run", "%{test}", fixture_variables[name]]]]
                                    if name in fixture_variables else [])
                if actions != expected_actions:
                    raise BoundaryError(f"Changed native test action: {name}")
                if name in tests or dependencies != TESTS[name]:
                    raise BoundaryError(f"Duplicate or changed native test dependencies: {name}")
                tests[name] = sorted(dependencies)
                continue
            if relative != expected_path or dependencies != expected_dependencies or key in graph:
                raise BoundaryError(f"Changed/duplicate Dune boundary for {key}: {relative} -> {sorted(dependencies)}")
            graph[key], roles[key], locations[path.parent] = sorted(dependencies), role, key
    expected_nodes = set(LIBRARIES) | {"executable:" + name for name in EXECUTABLES}
    if set(graph) != expected_nodes or set(tests) != set(TESTS):
        raise BoundaryError("Missing reviewed libraries, executables or native tests")
    closure = validate_graph(graph, roles)
    native_files = [path for path in core.rglob("*") if "_build" not in path.relative_to(core).parts
                    and path.suffix in {".c", ".h", ".cc", ".cpp", ".S", ".s"}]
    if [path.relative_to(root).as_posix() for path in native_files] != [ARTIFACT_STUB]:
        raise BoundaryError("Unreviewed native artifact primitive source inventory")
    stub_digest = hashlib.sha256(native_files[0].read_bytes()).hexdigest()
    if stub_digest != ARTIFACT_STUB_SHA256:
        raise BoundaryError("Changed reviewed artifact descriptor primitive source")
    source_files[ARTIFACT_STUB] = stub_digest
    references = {}
    for path in sorted(core.rglob("*")):
        if "_build" in path.relative_to(core).parts or path.suffix not in {".ml", ".mli"}:
            continue
        relative = path.relative_to(root).as_posix()
        source_files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        owner = locations.get(path.parent)
        if owner:
            allowed = set(graph[owner]) | ({owner} if owner in LIBRARIES else set())
        elif path.parent == core / "test" and path.stem in tests:
            allowed = set(tests[path.stem])
            owner = "test:" + path.stem
        else:
            raise BoundaryError(f"OCaml source has no reviewed Dune owner: {relative}")
        references[relative] = source_boundary(path, allowed, owner=owner)
    for library, modules in PRIVATE_MODULES.items():
        directory = core / Path(LIBRARIES[library][0]).parent
        for module in modules:
            if any(not (directory / (module + suffix)).is_file() for suffix in (".ml", ".mli")):
                raise BoundaryError(f"Private module needs an explicit implementation and interface: {module}")
    return {"schema_version": "biocompiler.core_boundaries.v0.1", "status": "pass",
            "claim_scope": "static_declared_link_graph_and_source_escape_policy_only",
            "native_build_and_semantic_independence": "separate_hosted_validation_required",
            "libraries_and_executables": graph, "roles": roles, "transitive_dependencies": closure,
            "external_trusted_dependencies": sorted(EXTERNAL_LIBRARIES),
            "shared_trusted_base": ["bioc_wire", "bioc_domain"],
            "private_modules": PRIVATE_MODULES,
            "native_tests": tests, "source_module_references": references,
            "source_sha256": dict(sorted(source_files.items()))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = check_boundaries(args.root.resolve())
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("Core dependency boundaries passed: verifier/checker have no producer dependencies; shared TCB recorded")
        return 0
    except (BoundaryError, OSError, UnicodeError) as exc:
        print(f"core dependency boundary: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

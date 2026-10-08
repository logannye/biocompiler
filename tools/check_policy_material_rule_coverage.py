"""Check a reviewed contextual-rule inventory without running policy semantics.

Whole-source pins and lexical censuses are review tripwires. They cannot prove
that prose describes OCaml correctly, that a witness distinguishes a rule, or
that any test has executed. Updating the ledger requires human/source review;
this tool deliberately has no baseline regeneration mode.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = "protocol/policy-material-rule-coverage-v0.1.json"
SCHEMA = "biocompiler.policy_material_rule_coverage.v0.1"
CLAIM = "reviewed_contextual_rule_and_witness_source_inventory_only"
STAGES = {"authoring", "operational", "implementation", "material", "context", "export"}
MAX_BYTES = 8 * 1024 * 1024
# Deliberately fixed review census, independent of the supplied ledger.
RULE_IDS = tuple("""
authoring.canonical_boundary
operational.source_identity operational.descriptor_identity operational.effect_signature operational.clock
operational.executor_subject operational.observation operational.coherence
operational.finite_state operational.scope_closure operational.expressions
operational.rising operational.lifecycle operational.arbitration
operational.extended_declarations
implementation.assurance implementation.catalog implementation.chassis
implementation.model_membership implementation.domain_grammar
implementation.domain_causality implementation.source_family implementation.types
implementation.replication implementation.evidence implementation.state
implementation.expression_wiring implementation.edge_identity
implementation.attempts implementation.rule_order implementation.atomic_writes
implementation.occurrences implementation.graph_closure implementation.runtime_phases
implementation.requirements implementation.nonvacuity implementation.bounds
material.original_request material.catalog_bridge material.kernel
material.carriers material.product material.construction material.member_inventory
material.regions material.translation material.chemistry material.coordinates
material.provenance context.counts context.recipient context.provider_closure
context.time context.delivery context.inputs context.record_resources
context.capacity material.obligations export.freshness export.publication
export.paired_archive export.standalone
""".split())
EXTRA_SOURCES = (
    "core/lib/domain/construction_content.ml", "core/lib/domain/construction_content.mli",
    "core/lib/compiler/construction_producer.ml", "core/lib/compiler/construction_producer.mli",
    "core/lib/checker/construction_reconstruction.ml", "core/lib/checker/construction_reconstruction.mli",
    "core/lib/checker/construction_check.ml", "core/lib/checker/construction_check.mli",
    "src/biocompiler/core_policy_material.py", "src/biocompiler/policy/material.py",
    "tools/policy_material_authoring_witness.py",
    "core/lib/service/service.ml", "core/lib/service/service.mli",
    "core/lib/producer_service/producer_service.ml", "core/lib/producer_service/producer_service.mli",
    "core/lib/wire/protocol.ml", "core/lib/wire/protocol.mli",
    "core/lib/wire/limits.ml", "core/lib/wire/limits.mli",
    "core/bin/core/main.ml", "core/bin/verify/main.ml",
    "src/biocompiler/core_client.py", "src/biocompiler/policy/cli.py",
    "src/biocompiler/entrypoint.py", "src/biocompiler/__main__.py",
    "src/biocompiler/core_distribution.py",
)
# Closed exceptions concern separate public routes; they are still fully pinned.
ROUTE_EXCEPTIONS = {
    f"core/lib/{directory}/{name}.{suffix}": "Separate source/operational public route; no complete material admission authority."
    for directory, name in (
        ("service", "policy_service"), ("service", "policy_operational_service"),
        ("producer_service", "policy_operational_producer"),
    ) for suffix in ("ml", "mli")
}


# Components form a separately negotiated composition route, not the original
# whole-kernel profile. Keep this path census closed and independently reviewed.
COMPONENT_MODULES = (
    ("domain", "policy_provider_prerequisites"),
    ("compiler", "policy_component_lowering"),
    ("domain", "policy_component_assembly_proposal"), ("domain", "policy_component_assembly_rule"),
    ("domain", "policy_component_context"), ("domain", "policy_component_fragment"),
    ("domain", "policy_component_library"), ("domain", "policy_component_material"),
    ("domain", "policy_component_material_candidate"),
    ("domain", "policy_component_material_request"),
    ("domain", "policy_component_selection_request"),
    ("domain", "policy_component_selection_candidate"),
    ("producer_service", "policy_component_material_producer"),
    ("producer_service", "policy_component_selection_producer"),
    ("realization_checker", "policy_component_assembly_check"),
    ("realization_checker", "policy_component_context_check"),
    ("realization_checker", "policy_component_material_check"),
    ("realization_checker", "policy_component_selection_common"),
    ("realization_checker", "policy_component_selection_check"),
    ("service", "policy_component_material_service"),
    ("service", "policy_component_material_format"),
    ("service", "policy_component_selection_service"),
)
COMPONENT_ROUTE_SOURCES = tuple(sorted(
    [f"core/lib/{directory}/{name}.{suffix}" for directory, name in COMPONENT_MODULES for suffix in ("ml", "mli")]
    + ["src/biocompiler/core_policy_component_material.py", "src/biocompiler/policy/component_material.py",
       "src/biocompiler/core_policy_component_selection.py", "src/biocompiler/policy/component_selection.py"]))
COMPONENT_SHARED_SOURCES = ("core/lib/service/service.ml", "core/lib/service/service.mli",
                            "src/biocompiler/core_policy_material.py")
COMPONENT_GENERATION_SHARED_SOURCES = (
    'core/bin/core/main.ml',
    'core/lib/checker/policy_admission.ml',
    'core/lib/checker/policy_admission.mli',
    'core/lib/checker/policy_check.ml',
    'core/lib/checker/policy_check.mli',
    'core/lib/checker/policy_correspondence.ml',
    'core/lib/checker/policy_correspondence.mli',
    'core/lib/checker/policy_generation_meter.ml',
    'core/lib/checker/policy_generation_meter.mli',
    'core/lib/checker/policy_realization_admission.ml',
    'core/lib/checker/policy_realization_admission.mli',
    'core/lib/compiler/construction_producer.ml',
    'core/lib/compiler/construction_producer.mli',
    'core/lib/compiler/policy_implementation_lowering.ml',
    'core/lib/compiler/policy_implementation_lowering.mli',
    'core/lib/compiler/policy_lowering.ml',
    'core/lib/compiler/policy_lowering.mli',
    'core/lib/compiler/recoding_producer.ml',
    'core/lib/compiler/recoding_producer.mli',
    'core/lib/domain/policy_operating_domain.ml',
    'core/lib/domain/policy_operating_domain.mli',
    'core/lib/producer_service/producer_service.ml',
    'core/lib/producer_service/producer_service.mli',
)
COMPONENT_SHARED_SOURCES += COMPONENT_GENERATION_SHARED_SOURCES + (
    "core/lib/domain/policy_realization_request.ml", "core/lib/domain/policy_realization_request.mli",
    "src/biocompiler/policy/implementation.py",
)
# This additive, versioned staged route preserves the original whole-kernel
# and selection-generation inventories and their historical projections.
COMPONENT_STAGED_SOURCES = tuple(sorted([
    *[f"core/lib/{directory}/{name}.{suffix}" for directory, name in (
        ("compiler", "policy_staged_lowering"), ("candidate_runtime", "policy_primitives"),
        ("checker", "policy_implementation_binding_check"),
        ("domain", "policy_implementation"), ("domain", "policy_implementation_binding"),
        ("domain", "policy_material_contract"),
        ("realization_checker", "policy_trace_correspondence"),
        ("realization_checker", "policy_requirement_monitor"),
    ) for suffix in ("ml", "mli")],
    "src/biocompiler/core_policy_implementation.py", "src/biocompiler/policy/patterns.py",
]))
COMPONENT_SOURCES = tuple(sorted((*COMPONENT_ROUTE_SOURCES, *COMPONENT_SHARED_SOURCES, *COMPONENT_STAGED_SOURCES)))
COMPONENT_REASON = "Separate reusable-component material route; not original whole-kernel profile authority. Indexed independently in policy-component-rule-coverage-v0.1.json."
ROUTE_EXCEPTIONS.update({path: COMPONENT_REASON for path in COMPONENT_ROUTE_SOURCES})
ROUTE_EXCEPTIONS.update({f"core/lib/compiler/policy_staged_lowering.{suffix}":
    "Separate versioned staged component route; no original whole-kernel material admission authority."
    for suffix in ("ml", "mli")})
EXTRA_SOURCES += ("core/lib/compiler/recoding_producer.ml", "core/lib/compiler/recoding_producer.mli",
                  "src/biocompiler/core_policy_component_material.py", "src/biocompiler/policy/component_material.py",
                  "src/biocompiler/core_policy_component_selection.py", "src/biocompiler/policy/component_selection.py",
                  "src/biocompiler/core_policy_implementation.py", "src/biocompiler/policy/patterns.py",
                  "src/biocompiler/policy/implementation.py")
COMPONENT_LEDGER = "protocol/policy-component-rule-coverage-v0.1.json"
COMPONENT_RULE_IDS = ("component.fragment", "component.local_material", "component.assembly_rule", "component.ordered_union",
    "component.original_request", "component.context", "component.conjunction", "component.production", "component.export", "component.sdk",
    "component.selection_request_codec", "component.material_candidate_codec",
    "component.selection_candidate_codec", "component.selection_common_authority", "component.checked_selection",
    "component.selection_publication_resources", "component.selection_scope", "component.selection_export", "component.selection_sdk",
    "component.selection_generation", "component.staged_regimen", "component.instance_composition", "component.prerequisite_closure", "component.two_observation_composition")
COMPONENT_INSTANCE_WITNESSES = tuple(sorted([
    "core/test/test_policy_instance_assembly_rule.ml",
    "core/test/test_policy_instance_material_service.ml",
    "core/test/policy_instance_support/literals.ml",
    "core/test/policy_instance_support/requests.ml",
    "core/test/instance_fixture_export/main.ml",
    "tests/test_policy_instance_material.py",
    "tools/check_policy_instance_material.py",
    "tools/check_policy_instance_fixture.py",
    "tests/test_policy_instance_fixture.py",
    "tools/check_policy_instance_material_installed.py",
    "tests/test_policy_instance_material_installed.py",
    "tools/check_policy_instance_prebuilt.py",
    "tests/test_policy_instance_prebuilt.py",
]))
COMPONENT_PREREQUISITE_WITNESSES = tuple(sorted([
    "core/test/test_policy_provider_prerequisites.ml",
    "core/test/test_policy_prerequisite_material_service.ml",
    "core/test/policy_prerequisite_support/literals.ml",
    "core/test/policy_prerequisite_support/requests.ml",
    "core/test/prerequisite_fixture_export/main.ml",
    "tools/check_policy_prerequisite_material.py",
    "tools/check_policy_prerequisite_fixture.py",
    "tools/check_policy_prerequisite_material_installed.py",
    "tools/check_policy_prerequisite_prebuilt.py",
    "tests/test_policy_prerequisite_material.py",
    "tests/test_policy_prerequisite_evidence.py",
    "tests/test_policy_prerequisite_fixture.py",
    "tests/test_policy_prerequisite_campaign.py",
    "tests/test_policy_prerequisite_material_installed.py",
    "tests/test_policy_prerequisite_prebuilt.py",
]))
COMPONENT_TWO_OBSERVATION_WITNESSES = tuple(sorted([
    'core/test/policy_two_observation_support/literals.ml',
    'core/test/policy_two_observation_support/requests.ml',
    'core/test/test_policy_two_observation_material_service.ml',
    'core/test/two_observation_fixture_export/main.ml',
    'tests/test_policy_two_observation_campaign.py',
    'tests/test_policy_two_observation_fixture.py',
    'tests/test_policy_two_observation_material.py',
    'tests/test_policy_two_observation_material_installed.py',
    'tests/test_policy_two_observation_prebuilt.py',
    'tools/check_policy_two_observation_fixture.py',
    'tools/check_policy_two_observation_material.py',
    'tools/check_policy_two_observation_material_installed.py',
    'tools/check_policy_two_observation_prebuilt.py',
]))
COMPONENT_STAGED_WITNESSES = tuple(sorted([
    *[f"core/test/test_policy_staged_{name}.ml" for name in
      ("regimen_source", "primitives", "binding", "generation", "component_material")],
    "core/test/policy_staged_support/literals.ml",
    *[f"core/test/data/policy_staged_{name}_v01.json" for name in
      ("regimen_source", "realization_request", "material", "material_seed")],
    "tests/test_policy_patterns.py", "tests/test_policy_staged_regimen_source.py", "tests/test_policy_staged_material.py",
    "tests/test_policy_staged_component_sdk.py",
    "tools/check_policy_staged_material_installed.py", "tests/test_policy_staged_material_installed.py",
    "tools/generate_policy_staged_regimen_fixture.py", "tools/generate_policy_staged_material_fixture.py",
    "tools/check_policy_staged_regimen_source.py", "tools/check_policy_staged_component_material.py",
]))
COMPONENT_WITNESSES = tuple(sorted([
    *COMPONENT_INSTANCE_WITNESSES,
    *COMPONENT_PREREQUISITE_WITNESSES,
    *COMPONENT_TWO_OBSERVATION_WITNESSES,
    *COMPONENT_STAGED_WITNESSES,
    *[f"core/test/test_policy_component_{name}.ml" for name in ("fragment", "material", "assembly_rule", "assembly_check", "material_request", "context_check", "material_service")],
    "core/test/test_policy_component_selection_request.ml", "core/test/test_policy_component_material_candidate.ml",
    "core/test/test_policy_component_selection_candidate.ml", "core/test/test_policy_component_selection_common.ml",
    "core/test/test_policy_component_selection_check.ml", "core/test/policy_component_support/selection_requests.ml",
    "core/test/test_policy_generation_admission.ml", "core/test/test_policy_generation_producers.ml",
    "core/test/test_policy_component_selection_producer.ml",
    "core/test/test_policy_component_selection_scope.ml", "core/test/test_policy_component_selection_service.ml",
    "tests/test_core_policy_component_selection.py", "tests/test_policy_component_selection.py",
    "tools/check_policy_component_selection.py", "tests/test_policy_component_selection_witness.py",
    "core/test/policy_component_support/literals.ml", "core/test/policy_component_support/requests.ml",
    "core/test/component_fixture_export/main.ml", "tools/check_policy_component_material.py",
    "tests/test_core_policy_component_material.py", "tests/test_policy_component_material.py",
    "tools/check_policy_component_fixture.py", "tests/test_policy_component_fixture.py",
    "tests/test_policy_component_install.py", "tests/test_policy_component_material_campaign.py",
    "tools/check_policy_material_consumer.py", "tests/test_policy_material_consumer.py",
    "tools/check_policy_material_prebuilt.py", "tests/test_policy_material_prebuilt.py",
    "core/test/data/policy_material_request_v01.json", "core/test/data/policy_material_state_v01.json",
]))
# Fixed reviewed meaning/provenance projection, excluding source-body hashes and
# lexical counts. Re-pinning changed files cannot reassign witness meaning.
COMPONENT_METADATA_SHA256 = "bc75eed03cb41e26ca2e27d2614bdf7ac420d83d4a2ee4d923b373adc9ccaf3f"


class CoverageError(ValueError):
    """A reviewed contextual inventory is malformed, incomplete or stale."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CoverageError(message)


def closed(value: Any, keys: set[str], label: str) -> None:
    require(type(value) is dict and set(value) == keys, label + ": missing or extra fields")


def words(value: Any, label: str) -> None:
    require(type(value) is str and bool(value.strip()), label + ": nonempty text required")


def source(root: Path, name: str) -> Path:
    words(name, "path")
    path = root / name
    require(not Path(name).is_absolute() and ".." not in Path(name).parts
            and path.resolve().is_relative_to(root.resolve()), "Reference escapes repository: " + name)
    require(path.is_file(), "Missing referenced source: " + name)
    return path


def read(root: Path, name: str) -> bytes:
    with source(root, name).open("rb") as handle:
        value = handle.read(MAX_BYTES + 1)
    require(len(value) <= MAX_BYTES, "Source exceeds static inventory bound: " + name)
    return value


def decode(raw: bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            require(key not in value, "Duplicate ledger key: " + key)
            value[key] = item
        return value
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(CoverageError("Nonfinite JSON: " + value)))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise CoverageError("Invalid bounded ledger JSON: " + str(error)) from error


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def ml_lexical(text: str) -> tuple[list[str], list[str]]:
    """Collect identifiers/strings; skip nested comments, never parse OCaml."""
    identifiers: list[str] = []
    strings: list[str] = []
    index = 0
    while index < len(text):
        if text.startswith("(*", index):
            depth = 1
            index += 2
            while depth and index < len(text):
                if text.startswith("(*", index):
                    depth += 1
                    index += 2
                elif text.startswith("*)", index):
                    depth -= 1
                    index += 2
                else:
                    index += 1
            require(depth == 0, "Unterminated OCaml comment in reviewed source")
        elif text[index] == "'" and (character := re.match(r"'(?:\\(?:[0-9]{3}|x[0-9A-Fa-f]{2}|.)|[^'\\])'", text[index:])):
            # Character literals such as '\"' are not string delimiters;
            # ordinary type variables ('a) do not match this closed spelling.
            index += len(character.group())
        elif text[index] == '"':
            start = index
            index += 1
            while index < len(text) and text[index] != '"':
                index += 2 if text[index] == "\\" else 1
            require(index < len(text), "Unterminated OCaml string in reviewed source")
            strings.append(text[start + 1:index])
            index += 1
        elif (match := re.match(r"[A-Za-z_][A-Za-z_0-9']*(?:\.[A-Za-z_][A-Za-z_0-9']*)*", text[index:])):
            identifiers.append(match.group())
            index += len(match.group())
        else:
            index += 1
    return identifiers, strings


def census(path: str, raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8")
    if path.endswith(".py"):
        tree = ast.parse(text, filename=path)
        counts = Counter(type(node).__name__ for node in ast.walk(tree)
                         if isinstance(node, (ast.Assert, ast.Raise, ast.FunctionDef, ast.ClassDef)))
        strings = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and type(node.value) is str]
        kind = "python_ast_node_census"
    else:
        tokens, strings = ml_lexical(text)
        counts = Counter(token for token in tokens if token in {
            "Diagnostic.require", "Diagnostic.fail", "require", "supported", "fail", "verify", "unsupported", "reject",
        })
        kind = "ocaml_lexical_guard_identifier_census_not_calls"
    profiles = Counter(value for value in strings if value.startswith("biocompiler.") and re.fullmatch(r"[A-Za-z0-9_.-]+", value))
    return {"kind": kind, "guards": dict(sorted(counts.items())), "profile_literals": dict(sorted(profiles.items()))}


def discover(root: Path) -> list[str]:
    paths = {path.relative_to(root).as_posix() for pattern in ("core/lib/**/policy_*.ml", "core/lib/**/policy_*.mli")
             for path in root.glob(pattern)}
    return sorted(paths | set(EXTRA_SOURCES))


def component_metadata(ledger: dict[str, Any]) -> dict[str, Any]:
    """Reviewed meaning/provenance, separate from current body/lexical pins."""
    return {**{key: value for key, value in ledger.items() if key not in {"sources", "witness_sources"}},
            "source_paths": [row["path"] for row in ledger["sources"]],
            "witness_paths": [row["path"] for row in ledger["witness_sources"]]}


def check_component(root: Path = ROOT, ledger: Any | None = None) -> dict[str, Any]:
    if ledger is None:
        ledger = decode(read(root, COMPONENT_LEDGER))
    closed(ledger, {"schema_version", "profile", "claim_scope", "sources", "witness_sources", "rules",
                    "limitations", "historical_development_feedback"}, "component ledger")
    require(ledger["schema_version"] == "biocompiler.policy_component_rule_coverage.v0.1"
            and ledger["profile"] == "policy-component-mrna-v0.1"
            and ledger["claim_scope"] == "reviewed_component_route_and_witness_source_inventory_only",
            "Changed separate component coverage claim")
    texts: dict[str, str] = {}
    for key, expected in (("sources", COMPONENT_SOURCES), ("witness_sources", COMPONENT_WITNESSES)):
        rows = ledger[key]
        require(type(rows) is list and all(type(row) is dict for row in rows), "Component inventory must be records")
        require([row.get("path") for row in rows] == list(expected), "Changed component " + key + " census")
        for row in rows:
            closed(row, {"path", "sha256", "census"} if key == "sources" else {"path", "sha256"}, "component source")
            raw = read(root, row["path"])
            require(row["sha256"] == digest(raw), "Stale component source hash: " + row["path"])
            if key == "sources":
                require(row["census"] == census(row["path"], raw), "Changed component guard/profile census")
            texts[row["path"]] = raw.decode("utf-8")
    rules = ledger["rules"]
    require(type(rules) is list and all(type(row) is dict for row in rules)
            and [row.get("id") for row in rules] == list(COMPONENT_RULE_IDS), "Changed component rule census")
    for row in rules:
        closed(row, {"id", "owners", "positive", "negative", "scope", "limits", "evidence_scope"}, "component rule")
        require(row["evidence_scope"] == "source_only_not_executed_by_this_gate", "Component witness upgraded to execution proof")
        for key in ("scope", "limits"):
            words(row[key], "component " + key)
        for key in ("owners", "positive", "negative"):
            require(type(row[key]) is list and row[key], "Missing component owner or distinguishing witness")
            for pointer in row[key]:
                closed(pointer, {"path", "anchor", "occurrence"}, "component pointer")
                allowed = COMPONENT_SOURCES if key == "owners" else COMPONENT_WITNESSES
                require(type(pointer["path"]) is str and pointer["path"] in allowed, "Unclassified component pointer")
                words(pointer["anchor"], "component anchor")
                require(type(pointer["occurrence"]) is int and pointer["occurrence"] >= 1
                        and texts[pointer["path"]].count(pointer["anchor"]) >= pointer["occurrence"],
                        "Missing component source anchor")
    metadata = json.dumps(component_metadata(ledger), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    require(digest(metadata) == COMPONENT_METADATA_SHA256, "Changed reviewed component meaning/witness/provenance metadata")
    return {"rules": len(rules), "sources": len(COMPONENT_SOURCES), "witness_sources": len(COMPONENT_WITNESSES),
            "status": "source_inventory_current", "semantic_proof": "not_established", "test_execution": "not_performed",
            "historical_feedback": "reference_only_not_reauthenticated_or_transferred"}


def check(root: Path = ROOT, ledger: Any | None = None) -> dict[str, Any]:
    if ledger is None:
        ledger = decode(read(root, LEDGER))
    closed(ledger, {"schema_version", "profile", "claim_scope", "syntax_ledger", "scope", "limitations",
                    "sources", "witness_sources", "rules", "known_gaps"}, "ledger")
    require(ledger["schema_version"] == SCHEMA and ledger["profile"] == "policy-truth-mrna-v0.1"
            and ledger["claim_scope"] == CLAIM, "Wrong contextual coverage claim/profile")
    require(ledger["syntax_ledger"] == "protocol/policy-semantic-coverage-v0.1.json", "Syntax ledger must remain complementary")
    syntax = decode(read(root, ledger["syntax_ledger"]))
    require(syntax.get("schema_version") == "biocompiler.policy_semantic_coverage.v0.1" and len(syntax.get("entries", [])) >= 612,
            "Complementary syntax inventory is missing")
    words(ledger["scope"], "scope")
    require(type(ledger["limitations"]) is list and len(ledger["limitations"]) >= 3, "Explicit limitations required")
    for value in ledger["limitations"]:
        words(value, "limitation")
    sources = ledger["sources"]
    require(type(sources) is list and all(type(row) is dict for row in sources), "Source inventory must be records")
    require([row.get("path") for row in sources] == discover(root), "Unclassified, omitted or reordered pipeline source")
    by_path: dict[str, dict[str, Any]] = {}
    texts: dict[str, str] = {}
    for row in sources:
        closed(row, {"path", "sha256", "census", "disposition", "reason"}, "source row")
        name = row["path"]
        raw = read(root, name)
        require(row["sha256"] == digest(raw), "Stale reviewed source hash: " + name)
        require(row["census"] == census(name, raw), "Changed guard/profile census: " + name)
        require(row["disposition"] in {"rule_owner", "dependency", "outside_route"}, "Unclassified pipeline source disposition")
        if name in ROUTE_EXCEPTIONS:
            require(row["disposition"] == "outside_route" and row["reason"] == ROUTE_EXCEPTIONS[name], "Changed route exception")
        else:
            require(row["disposition"] != "outside_route", "Unreviewed pipeline exception")
        words(row["reason"], "source reason")
        by_path[name] = row
        texts[name] = raw.decode("utf-8")
    witnesses = ledger["witness_sources"]
    require(type(witnesses) is list and all(type(row) is dict for row in witnesses), "Witness sources must be records")
    witness_paths = [row.get("path") for row in witnesses]
    require(all(type(path) is str for path in witness_paths), "Witness paths must be strings")
    require(witness_paths == sorted(set(witness_paths)), "Duplicate or unordered witness source")
    for row in witnesses:
        closed(row, {"path", "sha256"}, "witness source")
        raw = read(root, row["path"])
        require(row["sha256"] == digest(raw), "Stale witness source hash: " + row["path"])
        texts[row["path"]] = raw.decode("utf-8")
    used_owners: set[str] = set()
    used_witnesses: set[str] = set()

    def pointer(value: Any, allowed: set[str], label: str) -> None:
        closed(value, {"path", "anchor", "occurrence"}, label)
        words(value["path"], label + " path")
        require(value["path"] in allowed, label + ": unclassified reference")
        words(value["anchor"], label + " anchor")
        require(type(value["occurrence"]) is int and value["occurrence"] >= 1
                and texts[value["path"]].count(value["anchor"]) >= value["occurrence"], label + ": missing exact source anchor")

    rules = ledger["rules"]
    require(type(rules) is list and all(type(row) is dict for row in rules), "Rules must be records")
    require([row.get("id") for row in rules] == list(RULE_IDS), "Reviewed contextual rule census changed")
    pending = 0
    for rule in rules:
        closed(rule, {"id", "stage", "owners", "admitted_context", "outside_context", "positive", "negative", "witness_status", "gaps"}, "rule")
        require(type(rule["stage"]) is str and rule["stage"] in STAGES, "Unknown contextual stage")
        words(rule["admitted_context"], "admitted context")
        closed(rule["outside_context"], {"disposition", "description"}, "outside context")
        require(rule["outside_context"]["disposition"] in {"rejected", "unsupported", "incomplete", "withheld", "mixed"}, "Outside context has no explicit outcome")
        words(rule["outside_context"]["description"], "outside context description")
        require(type(rule["owners"]) is list and rule["owners"], "Rule lacks an owner")
        for value in rule["owners"]:
            pointer(value, set(by_path), "owner")
            require(by_path[value["path"]]["disposition"] == "rule_owner", "Owner mislabeled as dependency")
            used_owners.add(value["path"])
        for kind in ("positive", "negative"):
            require(type(rule[kind]) is list, "Witness inventory must be a list")
            for value in rule[kind]:
                closed(value, {"source", "context", "evidence_scope"}, "witness")
                pointer(value["source"], set(witness_paths), "witness")
                words(value["context"], "witness context")
                require(value["evidence_scope"] == "source_only_not_executed_by_this_gate", "Witness upgraded to execution proof")
                used_witnesses.add(value["source"]["path"])
        require(type(rule["gaps"]) is list, "Missing gap inventory")
        for gap in rule["gaps"]:
            words(gap, "witness gap")
        partial = bool(rule["gaps"])
        require(rule["witness_status"] == ("partial_source_witnesses" if partial else "source_witnesses_present"), "Witness status contradicts gaps")
        require(bool(rule["positive"] and rule["negative"]) or partial, "Missing witness must remain pending")
        pending += partial
    require(used_owners == {name for name, row in by_path.items() if row["disposition"] == "rule_owner"}, "Unassigned rule owner")
    require(used_witnesses == set(witness_paths), "Unreferenced witness source")
    require(type(ledger["known_gaps"]) is list and ledger["known_gaps"], "Global acceptance gaps must remain explicit")
    for gap in ledger["known_gaps"]:
        words(gap, "known gap")
    return {"schema_version": SCHEMA, "status": "source_inventory_current", "claim_scope": CLAIM,
            "rules": len(rules), "sources": len(sources), "witness_sources": len(witnesses),
            "rules_with_pending_witnesses": pending, "semantic_proof": "not_established", "test_execution": "not_performed",
            "component_route": check_component(root)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        result = check(args.root)
    except (CoverageError, OSError, SyntaxError, UnicodeError) as error:
        print("material-rule-coverage: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

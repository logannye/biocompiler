"""Bounded AST-only inventory of the reviewed rich-policy Python API.

This checks source drift and exact witness linkage, not witness execution,
semantic completeness, native acceptance, or arbitrary Python import safety.
There is deliberately no regenerate/accept-current-source command.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

try:
    from tools.check_policy_semantic_coverage import syntax
except ModuleNotFoundError as error:  # Also support isolated direct-script invocation.
    if error.name not in ("tools", "tools.check_policy_semantic_coverage"):
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_policy_semantic_coverage import syntax

ROOT = Path(__file__).resolve().parents[1]
LEDGER = "protocol/policy-public-api-coverage-v0.1.json"
SCHEMA = "biocompiler.policy_public_api_coverage.v0.1"
CLAIM = "Static public-source inventory and reviewed witness links only; neither executed coverage nor semantic/native/material/release acceptance."
RUNTIME_SCOPE = "Entries count authored AST declarations, fields and methods. Generated or inherited dataclass runtime protocols are represented by reviewed decorator/field/base contracts, not an exhaustive runtime-attribute census; Python record equality is not symbolic policy comparison."
# Reviewed separately from source-body pins. This literal binds all witness
# meanings/owners and coverage classifications, so refreshing file/AST
# hashes cannot reassign evidence or upgrade a source-only row. It is not a
# proof that the tests pass or that their claims establish runtime semantics.
# Revise only with explicit independent review; no regeneration mode exists.
REVIEWED_METADATA_SHA256 = "d2f6e39a1a7078d9ca33bf1d0f7c03021b42d92a53db18e3f0fdfb6dec9f2834"
BEFORE_TYPED_MODULES_METADATA_SHA256 = "2a9ce2139ab87bd5b5288357249a2433bba232c5e1a9fceef6b248c1325aab68"
TYPED_MODULE_PREFIXES = ("biocompiler.policy.typed.", "biocompiler.policy.modules.")
GROUNDED_HELPER_DEPENDENCIES = (
    "biocompiler.core_policy_component_material.GROUNDED_HELPER_ASSEMBLY_PROFILE",
    "biocompiler.core_policy_component_material.GROUNDED_HELPER_IMPLEMENTATION",
    "biocompiler.core_policy_component_material.GROUNDED_HELPER_PRODUCER_PROFILE",
    "biocompiler.core_policy_component_material.GROUNDED_HELPER_PROFILE",
    "biocompiler.core_policy_component_material.GROUNDED_HELPER_REQUEST_PROFILE",
    "biocompiler.core_policy_component_material.GROUNDED_HELPER_REQUEST_SCHEMA",
    "biocompiler.core_policy_component_material.GROUNDED_HELPER_VALIDATION_SCOPE",
    "biocompiler.core_policy_component_material._grounded_helper",
    "biocompiler.core_policy_component_material._helper_inventory",
)
COMPOSITION_DEPENDENCIES = (
    *GROUNDED_HELPER_DEPENDENCIES,
    'biocompiler.core_policy_component_material.INSTANCE_ASSEMBLY_PROFILE',
    'biocompiler.core_policy_component_material.INSTANCE_IMPLEMENTATION',
    'biocompiler.core_policy_component_material.INSTANCE_PRODUCER_PROFILE',
    'biocompiler.core_policy_component_material.INSTANCE_PROFILE',
    'biocompiler.core_policy_component_material.INSTANCE_REQUEST_PROFILE',
    'biocompiler.core_policy_component_material.INSTANCE_REQUEST_SCHEMA',
    'biocompiler.core_policy_component_material.INSTANCE_VALIDATION_SCOPE',
    'biocompiler.core_policy_component_material.MULTI_MEMBER_ASSEMBLY_PROFILE',
    'biocompiler.core_policy_component_material.MULTI_MEMBER_IMPLEMENTATION',
    'biocompiler.core_policy_component_material.MULTI_MEMBER_PRODUCER_PROFILE',
    'biocompiler.core_policy_component_material.MULTI_MEMBER_PROFILE',
    'biocompiler.core_policy_component_material.MULTI_MEMBER_REQUEST_PROFILE',
    'biocompiler.core_policy_component_material.MULTI_MEMBER_REQUEST_SCHEMA',
    'biocompiler.core_policy_component_material.MULTI_MEMBER_VALIDATION_SCOPE',
    'biocompiler.core_policy_component_material.PREREQUISITE_IMPLEMENTATION',
    'biocompiler.core_policy_component_material.PREREQUISITE_PRODUCER_PROFILE',
    'biocompiler.core_policy_component_material.PREREQUISITE_PROFILE',
    'biocompiler.core_policy_component_material.PREREQUISITE_REQUEST_PROFILE',
    'biocompiler.core_policy_component_material.PREREQUISITE_REQUEST_SCHEMA',
    'biocompiler.core_policy_component_material.PREREQUISITE_VALIDATION_SCOPE',
    'biocompiler.core_policy_component_material.TWO_OBSERVATION_IMPLEMENTATION',
    'biocompiler.core_policy_component_material.TWO_OBSERVATION_PRODUCER_PROFILE',
    'biocompiler.core_policy_component_material.TWO_OBSERVATION_PROFILE',
    'biocompiler.core_policy_component_material.TWO_OBSERVATION_REQUEST_PROFILE',
    'biocompiler.core_policy_component_material.TWO_OBSERVATION_REQUEST_SCHEMA',
    'biocompiler.core_policy_component_material.TWO_OBSERVATION_VALIDATION_SCOPE',
    'biocompiler.core_policy_component_material._instanced',
    'biocompiler.core_policy_component_material._member_transport_inventory',
    'biocompiler.core_policy_component_material._multi_member',
    'biocompiler.core_policy_component_material._prerequisite_evidence',
    'biocompiler.core_policy_component_material._prerequisites',
    'biocompiler.core_policy_component_material._profile_settings',
    'biocompiler.core_policy_component_material._two_observations',
    'biocompiler.core_policy_implementation.MULTI_PRODUCT_BINDING_PROFILE',
    'biocompiler.core_policy_implementation.MULTI_PRODUCT_BINDING_REPORT_SCHEMA',
    'biocompiler.core_policy_implementation.MULTI_PRODUCT_BINDING_SCHEMA',
    'biocompiler.core_policy_implementation.MULTI_PRODUCT_REQUEST_PROFILE',
    'biocompiler.core_policy_implementation.MULTI_PRODUCT_REQUEST_SCHEMA',
    'biocompiler.core_policy_implementation.PREREQUISITE_REQUEST_PROFILE',
    'biocompiler.core_policy_implementation.PREREQUISITE_REQUEST_SCHEMA',
    'biocompiler.core_policy_implementation.TWO_OBSERVATION_BINDING_PROFILE',
    'biocompiler.core_policy_implementation.TWO_OBSERVATION_BINDING_REPORT_SCHEMA',
    'biocompiler.core_policy_implementation.TWO_OBSERVATION_BINDING_SCHEMA',
    'biocompiler.core_policy_implementation.TWO_OBSERVATION_REQUEST_PROFILE',
    'biocompiler.core_policy_implementation.TWO_OBSERVATION_REQUEST_SCHEMA',
    'biocompiler.core_policy_implementation._multi_product_anchors',
    'biocompiler.core_policy_implementation._multi_product_original',
    'biocompiler.core_policy_implementation._pending_dependencies',
    'biocompiler.core_policy_implementation._prerequisite_original',
    'biocompiler.core_policy_implementation._two_observation_anchors',
    'biocompiler.core_policy_implementation._two_observation_original',
)
PACKAGE = "src/biocompiler/policy"
MODULES = tuple("__init__ behavior catalog chassis cli component_material component_selection coordination deployment effects entities examples handoff implementation inspection logic material model modules native observations operational patterns programs requirements research_project serialization space state time typed validation values".split())
CLIENTS = ("core_policy", "core_policy_operational", "core_policy_implementation", "core_policy_material", "core_policy_component_material", "core_policy_component_selection")
PRIMARY = tuple(sorted([f"{PACKAGE}/{name}.py" for name in MODULES] + [f"src/biocompiler/{name}.py" for name in CLIENTS]))
BOUNDARIES = ("src/biocompiler/__init__.py", "src/biocompiler/__main__.py", "src/biocompiler/entrypoint.py", "src/biocompiler/core_client.py", "pyproject.toml", "tools/check_policy_semantic_coverage.py")
# These names remain compatible support surfaces, not cellular runtime APIs.
SUPPORT = frozenset("model.declaration_ref serialization.DEFAULT_LIMITS serialization.JSONValue operational.FrozenPolicy inspection.summary examples.RATE".split())
BUILDER_METHODS = tuple("__init__ qualified namespace add hole resolve executor subject encounter clock observe state effect rule machine transition channel require snapshot freeze".split())
PATTERNS = tuple("bounded_response context_gate once_per_scope ordered_effects persistence_gate population_handoff".split())
CLI = tuple("check inspect diff export-schema export-request assess-native compile-native check-lowering-native execute-native replay-execution-native compile-implementation-native check-implementation-native replay-implementation-native compile-material-native check-material-native replay-material-native export-material-native".split())
OPERATIONS = {
    "core_policy.PolicyClient.assess": ("assess-policy", ("document",)),
    "core_policy.PolicyClient.replay": ("replay-policy-assessment", ("expected_document", "assessment")),
    "core_policy_operational.OperationalPolicyClient.compile": ("compile-policy", ("document", "definitions")),
    "core_policy_operational.OperationalPolicyClient.check_lowering": ("check-policy-lowering", ("document", "definitions", "candidate")),
    "core_policy_operational.OperationalPolicyClient.execute": ("execute-policy", ("document", "definitions", "candidate", "timeline")),
    "core_policy_operational.OperationalPolicyClient.replay": ("replay-policy-execution", ("document", "definitions", "candidate", "timeline", "report")),
    "core_policy_implementation.PolicyImplementationClient.compile": ("compile-policy-implementation", ("request", "limits")),
    "core_policy_implementation.PolicyImplementationClient.check": ("check-policy-implementation", ("request", "candidate", "limits")),
    "core_policy_implementation.PolicyImplementationClient.replay": ("replay-policy-implementation", ("request", "candidate", "limits", "report")),
    "core_policy_material.PolicyMaterialClient.compile": ("compile-policy-material", ("request", "limits")),
    "core_policy_material.PolicyMaterialClient.check": ("check-policy-material", ("request", "candidate", "limits")),
    "core_policy_material.PolicyMaterialClient.replay": ("replay-policy-material", ("request", "candidate", "limits", "report")),
    "core_policy_material.PolicyMaterialClient.export": ("export-policy-material", ("request", "candidate", "limits")),
    "core_policy_component_material.PolicyComponentMaterialClient.compile": ("compile-policy-component-material", ("request", "limits")),
    "core_policy_component_material.PolicyComponentMaterialClient.check": ("check-policy-component-material", ("request", "candidate", "limits")),
    "core_policy_component_material.PolicyComponentMaterialClient.replay": ("replay-policy-component-material", ("request", "candidate", "limits", "report")),
    "core_policy_component_material.PolicyComponentMaterialClient.export": ("export-policy-component-material", ("request", "candidate", "limits")),
    "core_policy_component_selection.PolicyComponentSelectionClient.compile": ("compile-policy-component-selection", ("request", "limits")),
    "core_policy_component_selection.PolicyComponentSelectionClient.check": ("check-policy-component-selection", ("request", "candidate", "limits")),
    "core_policy_component_selection.PolicyComponentSelectionClient.replay": ("replay-policy-component-selection", ("request", "candidate", "limits", "report")),
    "core_policy_component_selection.PolicyComponentSelectionClient.export": ("export-policy-component-selection", ("request", "candidate", "limits")),
}
# Reviewed access names and canonical owners, independent of the ledger file pins.
REVIEWED_EXPORT_GROUPS = (('biocompiler.policy',
  'biocompiler.policy',
  'behavior catalog chassis coordination deployment effects entities logic modules observations patterns requirements '
  'space state time typed values'),
 ('biocompiler.policy', 'biocompiler.policy.handoff', 'SubmissionError assess_capabilities prepare_submission'),
 ('biocompiler.policy', 'biocompiler.policy.inspection', 'diff graph inspect'),
 ('biocompiler.policy',
  'biocompiler.policy.logic',
  'FALSE TRUE UNKNOWN all_of any_of arithmetic call compare count distinct entity exists forall literal not_ '
  'rising'),
 ('biocompiler.policy',
  'biocompiler.policy.model',
  'Arbitration Argument Assignment AssuranceRequest BackendCapabilities BuildRequest CapabilityAssessment Channel '
  'ChassisProfile Clock CompilationSubmission ContractClause Declaration DefinitionRef DeliveryContract Deployment '
  'Document EVENT Effect EffectLifecycle Encounter Expr Hole INTEGER ImplementationBinding '
  'ImplementationCatalogLock Machine Message Observation PROFILE Parameter PolicyDraft PolicyProgram Quantity '
  'RNAConstraints Record Ref Requirement Role RoleBinding Rule Scope SemanticBundle SemanticDefinition SourceSpan '
  'SpatialScope StateStore Subject TEXT TRUTH Transition TypeSpec Unit'),
 ('biocompiler.policy', 'biocompiler.policy.programs', 'AuthoringError ProgramBuilder ref'),
 ('biocompiler.policy',
  'biocompiler.policy.serialization',
  'PolicySerializationError SerializationLimits document_digest dump dumps from_data load loads schema to_data'),
 ('biocompiler.policy', 'biocompiler.policy.validation', 'CheckReport Diagnostic check'),
 ('biocompiler.policy', 'biocompiler.policy.values', 'COUNT DIMENSIONLESS MINUTE SECOND from_float quantity'),
 ('biocompiler.policy.behavior', 'biocompiler.policy.model', 'Arbitration Machine Rule Transition'),
 ('biocompiler.policy.catalog',
  'biocompiler.policy.model',
  'ContractClause DefinitionRef ImplementationBinding ImplementationCatalogLock SemanticBundle SemanticDefinition'),
 ('biocompiler.policy.chassis', 'biocompiler.policy.model', 'ChassisProfile RoleBinding'),
 ('biocompiler.policy.coordination', 'biocompiler.policy.model', 'Channel Message'),
 ('biocompiler.policy.deployment',
  'biocompiler.policy.model',
  'DeliveryContract Deployment RNAConstraints RoleBinding'),
 ('biocompiler.policy.effects', 'biocompiler.policy.model', 'Argument Effect EffectLifecycle'),
 ('biocompiler.policy.entities', 'biocompiler.policy.model', 'Encounter Ref Role Scope Subject'),
 ('biocompiler.policy.observations', 'biocompiler.policy.model', 'Expr Observation TypeSpec'),
 ('biocompiler.policy.requirements', 'biocompiler.policy.model', 'AssuranceRequest Requirement'),
 ('biocompiler.policy.space', 'biocompiler.policy.model', 'Scope SpatialScope'),
 ('biocompiler.policy.state', 'biocompiler.policy.model', 'Assignment Scope StateStore'),
 ('biocompiler.policy.typed', 'biocompiler.policy.typed',
  'TypedAuthoringError TruthExpr IntegerExpr TextExpr QuantityExpr EventExpr ScalarExpression EffectPhase '
  'Observation State Parameter Assignment Effect truth unknown integer text quantity guard trigger '
  'all_of any_of not_ rising argument truth_observation integer_observation text_observation quantity_observation '
  'truth_state integer_state text_state quantity_state truth_parameter integer_parameter text_parameter quantity_parameter rule transition'),
 ('biocompiler.policy.modules', 'biocompiler.policy.modules',
  'Access ModuleError ModuleLimits InputPort OutputPort ModuleOutput ModuleBinding Footprint ModuleTemplate ModuleInstance instantiate compose_modules'),
 ('biocompiler.policy.values',
  'biocompiler.policy.model',
  'EVENT INTEGER Parameter Quantity TEXT TRUTH TypeSpec Unit'),
 ('biocompiler.policy.values',
  'biocompiler.policy.values',
  'COUNT DIMENSIONLESS MINUTE SECOND compatible from_float quantity'))

# Exact expansion witnesses are independently reviewed test methods, not labels
# a ledger may repoint to an unrelated passing test.
BUILDER_WITNESSES = {
    "constructor": "test_constructor_namespace_mutation_and_snapshot_authority",
    "defaults": "test_named_convenience_defaults_and_encounter_order",
    "options": "test_optional_authority_fields_are_preserved_literal",
    "copies": "test_copying_methods_only_change_own_id",
    "ownership": "test_add_ref_ownership_errors_are_atomic",
    "holes": "test_hole_resolve_has_no_implicit_rebinding",
    "freeze": "test_freeze_keeps_exact_declarations_and_caller_source",
    "compare": "test_compare_protocol_and_exact_value_stages",
}
PATTERN_WITNESSES = dict(zip(PATTERNS, (
    "test_bounded_response_literal_counter_guard_and_write", "test_context_gate_literal_expansion",
    "test_once_per_scope_literal_expansion", "test_ordered_effects_literal_machine_and_all_seven_transitions",
    "test_persistence_gate_literal_clock_duration_and_coverage", "test_population_handoff_literal_sender_receiver_and_message",
)))
BUILDER_LINKS = {
    "__init__": "constructor", "qualified": "constructor", "namespace": "constructor",
    "add": "ownership", "hole": "holes", "resolve": "holes", "executor": "defaults",
    "subject": "defaults", "encounter": "defaults", "clock": "defaults", "observe": "defaults",
    "state": "copies", "effect": "defaults", "rule": "defaults", "machine": "defaults",
    "transition": "defaults", "channel": "copies", "require": "copies", "snapshot": "constructor", "freeze": "freeze",
    "name": "constructor", "semantics": "constructor",
}
BOUNDARY_WITNESSES = {
    "encounter_second_collision": "test_encounter_second_identity_collision_keeps_complete_draft",
    "encounter_target_collision": "test_encounter_target_identity_collision_keeps_complete_draft",
    "encounter_ingress": "test_encounter_invalid_second_record_does_not_add_target",
    "encounter_pair": "test_encounter_pair_preserves_literal_order_source_and_owned_target",
    "copy_foreign": "test_copy_helpers_reject_foreign_outer_ownership_without_mutation",
    "copy_import": "test_copy_helpers_accept_same_builder_namespace_and_explicit_data_import",
}
MAX_SOURCE = 2 * 1024 * 1024
MAX_LEDGER = 4 * 1024 * 1024
MAX_NODES = 150000
MAX_TOTAL_SOURCE = 16 * 1024 * 1024


class ApiCoverageError(ValueError):
    """Unreviewed, malformed or overclaimed public-source inventory."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ApiCoverageError(message)


def closed(value: Any, keys: set[str], label: str) -> None:
    require(type(value) is dict and set(value) == keys, label + ": unexpected or missing fields")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def fingerprint(node: ast.AST) -> str:
    return digest(syntax(node).encode("utf-8"))


def bounded(value: Any) -> None:
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        require(count <= MAX_NODES and depth <= 64, "Inventory depth/node limit exceeded")
        require(type(item) in (dict, list, str, int, bool, type(None)), "Inventory must be inert exact JSON")
        if type(item) is dict:
            require(all(type(key) is str for key in item), "Inventory keys must be strings")
            pending.extend((child, depth + 1) for pair in item.items() for child in pair)
        elif type(item) is list:
            require(len(item) <= 4096, "Inventory array limit exceeded")
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            require(len(item.encode("utf-8")) <= 65536, "Inventory string limit exceeded")


def read_bytes(root: Path, relative: str, limit: int = MAX_SOURCE) -> bytes:
    require(type(relative) is str and relative and not Path(relative).is_absolute()
            and ".." not in Path(relative).parts, "Invalid repository-relative path")
    path = root / relative
    require(path.resolve().is_relative_to(root.resolve()) and path.is_file(), "Missing/escaping source: " + relative)
    with path.open("rb") as stream:
        value = stream.read(limit + 1)
    require(len(value) <= limit, "Source byte limit exceeded: " + relative)
    return value


def read_ledger(path: Path) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            require(key not in result, "Duplicate JSON key: " + key)
            result[key] = value
        return result

    def invalid_number(value: str) -> None:
        raise ApiCoverageError("Nonexact JSON number: " + value)

    with path.open("rb") as stream:
        raw = stream.read(MAX_LEDGER + 1)
    require(len(raw) <= MAX_LEDGER, "Ledger byte limit exceeded")
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_float=invalid_number, parse_constant=invalid_number)
        bounded(value)
    except (UnicodeError, RecursionError, json.JSONDecodeError, ValueError) as error:
        raise ApiCoverageError("Invalid bounded ledger: " + str(error)) from error
    require(type(value) is dict, "Ledger must be an object")
    return value


def parse(raw: bytes, path: str) -> ast.Module:
    try:
        tree = ast.parse(raw.decode("utf-8"), filename=path)
        require(sum(1 for _ in ast.walk(tree)) <= MAX_NODES, "Source AST node limit exceeded")
        return tree
    except (SyntaxError, UnicodeError, RecursionError) as error:
        raise ApiCoverageError("Invalid source AST: " + path) from error


def symbols(tree: ast.Module) -> dict[str, ast.AST]:
    result: dict[str, ast.AST] = {}
    def walk(body: list[ast.stmt], prefix: str = "") -> None:
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                key = prefix + node.name
                # Overloads have separate inventory rows; the implementation owns the ordinary anchor.
                result[key] = node
                if isinstance(node, ast.ClassDef):
                    walk(node.body, key + ".")
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        result[prefix + target.id] = node
    walk(tree.body)
    return result


def module_name(path: str) -> str:
    return path.removeprefix("src/").removesuffix(".py").replace("/", ".").removesuffix(".__init__")


def discover(root: Path) -> dict[str, Any]:
    paths_list = []
    for path in (root / PACKAGE).rglob("*.py"):
        paths_list.append(path.relative_to(root).as_posix())
        require(len(paths_list) <= len(MODULES), "Reviewed policy file census differs")
    paths = tuple(sorted(paths_list))
    require(paths == tuple(path for path in PRIMARY if path.startswith(PACKAGE + "/")), "Reviewed policy file census differs")
    native_list = []
    for path in (root / "src/biocompiler").glob("core_policy*.py"):
        native_list.append(path.relative_to(root).as_posix())
        require(len(native_list) <= len(CLIENTS), "Reviewed native-client file census differs")
    native = tuple(sorted(native_list))
    require(native == tuple(path for path in PRIMARY if not path.startswith(PACKAGE + "/")), "Reviewed native-client file census differs")
    sources = {path: read_bytes(root, path) for path in PRIMARY + BOUNDARIES}
    require(sum(map(len, sources.values())) <= MAX_TOTAL_SOURCE, "Aggregate source byte limit exceeded")
    trees = {path: parse(sources[path], path) for path in PRIMARY}
    rows: list[dict[str, Any]] = []
    local: dict[str, dict[str, str]] = {}
    exports: dict[str, list[str]] = {}
    imports: list[dict[str, Any]] = []
    aliases: dict[str, str] = {}

    def add(path: str, name: str, kind: str, node: ast.AST, scope: str = "public_api") -> None:
        module = module_name(path)
        short = (module + "." + name).removeprefix("biocompiler.policy.")
        if short in SUPPORT:
            scope = "compatibility_support"
        signature = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            signature = ast.unparse(node.args) + (" -> " + ast.unparse(node.returns) if node.returns else "")
        elif isinstance(node, ast.AnnAssign):
            signature = ast.unparse(node.annotation) + (" = " + ast.unparse(node.value) if node.value else "")
        rows.append({"id": module + "." + name, "kind": kind, "scope": scope,
                     "source": {"path": path, "symbol": name.split("@", 1)[0]},
                     "signature": signature, "syntax_sha256": fingerprint(node)})

    for path, tree in trees.items():
        module = module_name(path)
        bindings: dict[str, str] = {}
        local[module] = bindings
        overloads: Counter[str] = Counter()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                package = module if path.endswith("/__init__.py") else module.rsplit(".", 1)[0]
                parts = package.split(".")[:len(package.split(".")) - node.level + 1] if node.level else []
                origin = ".".join(parts + ([node.module] if node.module else []))
                for item in node.names:
                    require(item.name != "*", "Wildcard API imports need explicit scope review")
                    bindings[item.asname or item.name] = origin + "." + item.name
            elif isinstance(node, ast.Import):
                for item in node.names:
                    bindings[item.asname or item.name.split(".")[0]] = item.name
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if not isinstance(target, ast.Name):
                        continue
                    name = target.id
                    if name == "__all__":
                        try:
                            values = ast.literal_eval(node.value)
                        except (ValueError, TypeError) as error:
                            raise ApiCoverageError("Exports must be an explicit literal list") from error
                        require(type(values) is list and all(type(v) is str for v in values)
                                and len(values) == len(set(values)), "Duplicate/malformed explicit exports")
                        exports[module] = values
                    else:
                        bindings[name] = bindings.get(node.value.id, module + "." + node.value.id) if isinstance(node.value, ast.Name) else module + "." + name
                        if not name.startswith("_"):
                            alias = bindings[name] != module + "." + name
                            add(path, name, "alias" if alias else "value", node, "dependency")
                            if alias:
                                aliases[module + "." + name] = bindings[name]
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bindings[node.name] = module + "." + node.name
                public = not node.name.startswith("_")
                if isinstance(node, ast.ClassDef):
                    add(path, node.name, "class", node, "public_api" if public else "dependency")
                    if not public:
                        continue
                    for child in node.body:
                        if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                            add(path, node.name + "." + child.target.id, "field", child,
                                "dependency" if child.target.id.startswith("_") else "public_api")
                        elif isinstance(child, ast.FunctionDef):
                            name = child.name
                            kind = "property" if any(isinstance(x, ast.Name) and x.id == "property" for x in child.decorator_list) else "method"
                            scope = "public_api" if not name.startswith("_") or name in ("__init__", "__bool__", "__and__", "__or__", "__invert__", "_repr_html_") else "dependency"
                            add(path, node.name + "." + name, kind, child, scope)
                            if node.name == "ProgramBuilder" and name == "__init__":
                                for statement in child.body:
                                    if isinstance(statement, ast.Assign):
                                        for target in statement.targets:
                                            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self" and not target.attr.startswith("_"):
                                                add(path, node.name + "." + target.attr, "attribute", statement)
                else:
                    if any(isinstance(x, ast.Name) and x.id == "overload" for x in node.decorator_list):
                        overloads[node.name] += 1
                        add(path, node.name + "@overload" + str(overloads[node.name]), "overload", node)
                    else:
                        add(path, node.name, "function", node, "public_api" if public else "dependency")
        for node in ast.walk(tree):
            if isinstance(node, (ast.ImportFrom, ast.Import)):
                imports.append({"path": path, "syntax_sha256": fingerprint(node)})

    def resolve(value: str) -> str:
        seen: set[str] = set()
        while value not in seen:
            seen.add(value)
            module, _, name = value.rpartition(".")
            target = local.get(module, {}).get(name, value)
            if target == value:
                return value
            value = target
        raise ApiCoverageError("Cyclic public alias")

    access: dict[str, str] = {}
    for module, names in exports.items():
        for name in names:
            require(name in local[module], "Unbound explicit export: " + name)
            access[module + "." + name] = resolve(local[module][name])
    aliases = {name: resolve(target) for name, target in aliases.items()}
    targets = set(access.values())
    for row in rows:
        if row["kind"] in ("value", "alias") and row["id"] in targets and row["scope"] != "compatibility_support":
            row["scope"] = "public_api"
        if row["id"] in ("biocompiler.policy.examples.NAMES", "biocompiler.policy.inspection.render_html"):
            row["scope"] = "public_api"
    known = {row["id"] for row in rows} | set(local)
    require(targets <= known, "Public export resolves outside the reviewed owned surface")
    reviewed_access = {module + "." + name: owner + "." + name
                       for module, owner, names in REVIEWED_EXPORT_GROUPS for name in names.split()}
    require(access == reviewed_access, "Reviewed export target/alias census differs")
    require(len(exports.get("biocompiler.policy", [])) == 114 and len(access) == 216,
            "Reviewed explicit export census differs")
    require(aliases == {"biocompiler.policy.inspection.summary": "biocompiler.policy.inspection.inspect",
                        "biocompiler.policy.inspection.render_html": "biocompiler.policy.inspection.to_html"}, "Reviewed compatibility/display aliases differ")
    require({r["id"].removeprefix("biocompiler.policy.") for r in rows if r["scope"] == "compatibility_support"} == SUPPORT,
            "Compatibility support census differs")
    require(tuple(r["source"]["symbol"].split(".")[-1] for r in rows if r["id"].startswith("biocompiler.policy.programs.ProgramBuilder.") and r["kind"] == "method" and r["scope"] == "public_api") == BUILDER_METHODS,
            "Reviewed builder method census differs")
    require({r["source"]["symbol"] for r in rows if r["kind"] == "attribute"} == {"ProgramBuilder.name", "ProgramBuilder.semantics"}, "Reviewed builder attribute census differs")
    require(tuple(sorted(r["source"]["symbol"] for r in rows if r["source"]["path"] == PACKAGE + "/patterns.py" and r["scope"] == "public_api" and r["kind"] == "function")) == PATTERNS,
            "Reviewed six-pattern census differs")
    parser = symbols(trees[PACKAGE + "/cli.py"])["_parser"]
    loops = [n for n in parser.body if isinstance(n, ast.For)]
    require(len(loops) == 1, "CLI command declaration shape changed")
    try:
        commands = ast.literal_eval(loops[0].iter)
    except (ValueError, TypeError) as error:
        raise ApiCoverageError("CLI commands must be literal") from error
    require(tuple(x[0] for x in commands) == CLI, "Reviewed CLI route census differs")
    operations = []
    for owner, (operation, keys) in OPERATIONS.items():
        module, symbol = owner.split(".", 1)
        node = symbols(trees["src/biocompiler/" + module + ".py"])[symbol]
        calls = [x for x in ast.walk(node) if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr == "_call"]
        require(len(calls) == 1 and len(calls[0].args) == 2, "Native route shape differs: " + owner)
        call = calls[0]
        require(isinstance(call.args[0], ast.Constant) and call.args[0].value == operation
                and isinstance(call.args[1], ast.Dict), "Native operation route differs: " + owner)
        require(tuple(ast.literal_eval(k) for k in call.args[1].keys) == keys, "Native original-input inventory differs: " + owner)
        operations.append({"owner": "biocompiler." + owner, "operation": operation, "payload_fields": list(keys)})
    rows.sort(key=lambda row: row["id"])
    require(len(rows) == len({row["id"] for row in rows}), "Duplicate API symbol identity")
    return {"files": {path: digest(data) for path, data in sorted(sources.items())}, "entries": rows,
            "exports": dict(sorted(access.items())), "aliases": aliases, "imports": imports,
            "cli_commands": list(CLI), "operations": operations}


def syntax_links(entries: list[dict[str, Any]]) -> dict[str, str]:
    """Reuse exact existing model vocabulary; do not duplicate its dispositions."""
    result = {}
    for row in entries:
        if row["source"]["path"] != PACKAGE + "/model.py":
            continue
        name, kind = row["source"]["symbol"], row["kind"]
        prefix = ("record:" if kind == "class" else "field:" if kind == "field" else
                  "alias:" if name in ("Declaration", "Document") else
                  "constant:" if name in ("PROFILE", "TRUTH", "EVENT", "INTEGER", "TEXT") else None)
        if prefix:
            result[row["id"]] = prefix + name
    return result


def validate(root: Path, ledger: dict[str, Any]) -> dict[str, Any]:
    bounded(ledger)
    closed(ledger, {"schema_version", "claim_scope", "runtime_protocol_scope", "inventory", "syntax_links", "witnesses", "coverage", "known_gaps"}, "ledger")
    require(ledger["schema_version"] == SCHEMA and ledger["claim_scope"] == CLAIM, "Invalid schema or acceptance claim")
    require(ledger["runtime_protocol_scope"] == RUNTIME_SCOPE, "Authored-AST/runtime protocol scope must remain explicit")
    expected = discover(root)
    require(ledger["inventory"] == expected, "Source/API inventory drift; review bodies, signatures, aliases, routes and dependencies")
    entries = {row["id"]: row for row in expected["entries"]}
    syntax_ledger = read_ledger(root / "protocol/policy-semantic-coverage-v0.1.json")
    require(syntax_ledger.get("schema_version") == "biocompiler.policy_semantic_coverage.v0.1" and
            syntax_ledger.get("source_profile") == "biocompiler.policy.v0.1", "Wrong syntax-ledger authority")
    existing = {row["id"]: row for row in syntax_ledger["entries"]}
    require(len(existing) == len(syntax_ledger["entries"]), "Duplicate syntax-ledger identity")
    links = syntax_links(expected["entries"])
    require(ledger["syntax_links"] == links and all(link in existing for link in links.values()), "Incomplete existing syntax-ledger links")
    for identity, link in links.items():
        require(existing[link]["source"] == entries[identity]["source"] and
                existing[link]["kind"] == link.split(":", 1)[0], "Syntax link names another source owner")
    witnesses = ledger["witnesses"]
    require(type(witnesses) is dict and 0 < len(witnesses) <= 256, "Missing/bounded witness inventory")
    witness_files: dict[str, tuple[bytes, dict[str, ast.AST]]] = {}
    witness_bytes = 0
    for identity, witness in witnesses.items():
        closed(witness, {"path", "symbol", "syntax_sha256", "file_sha256", "role", "distinction"}, "witness " + identity)
        require(all(type(value) is str and bool(value) for value in witness.values()), "Malformed witness value")
        require(witness["role"] in ("positive", "rejection", "mixed") and type(witness["distinction"]) is str and bool(witness["distinction"]), "Malformed witness distinction")
        require(witness["path"].startswith("tests/test_policy") or witness["path"].startswith("tests/test_core_policy"), "Witness must be a reviewed policy test")
        if witness["path"] not in witness_files:
            raw = read_bytes(root, witness["path"])
            witness_bytes += len(raw)
            require(witness_bytes <= MAX_TOTAL_SOURCE, "Aggregate witness byte limit exceeded")
            witness_files[witness["path"]] = (raw, symbols(parse(raw, witness["path"])))
        raw, nodes = witness_files[witness["path"]]
        node = nodes.get(witness["symbol"])
        require(isinstance(node, ast.FunctionDef) and node.name.startswith("test_"), "Missing actual witness method: " + identity)
        require(digest(raw) == witness["file_sha256"] and fingerprint(node) == witness["syntax_sha256"], "Stale witness source: " + identity)
    required_witnesses = {
        **{"builder." + key: ("tests/test_policy_builders.py", "PolicyBuilderLiteralTests." + method)
           for key, method in BUILDER_WITNESSES.items()},
        **{"pattern." + key: ("tests/test_policy_patterns.py", "PolicyPatternTests." + method)
           for key, method in PATTERN_WITNESSES.items()},
        **{"boundary." + key: ("tests/test_policy_builder_boundaries.py", "PolicyBuilderBoundaryTests." + method)
           for key, method in BOUNDARY_WITNESSES.items()},
    }
    for key, original in required_witnesses.items():
        require(key in witnesses, "Dropped required expansion witness: " + key)
        require((witnesses[key]["path"], witnesses[key]["symbol"]) == original,
                "Repinned expansion witness points to the wrong test: " + key)
    coverage = ledger["coverage"]
    require(type(coverage) is dict and set(coverage) == set(entries), "Missing/extra API evidence classifications")
    used: set[str] = set()
    for identity, row in coverage.items():
        closed(row, {"status", "witnesses", "scope"}, "coverage " + identity)
        require(row["status"] in ("independent_expansion", "shared_invariant", "source_only", "compatibility_support", "dependency"), "Unknown evidence status")
        require(type(row["scope"]) is str and bool(row["scope"]), "Missing evidence limitation")
        refs = row["witnesses"]
        require(type(refs) is list and all(type(ref) is str for ref in refs) and len(refs) == len(set(refs)) and all(ref in witnesses for ref in refs), "Dropped/malformed witness link")
        require(bool(refs) == (row["status"] in ("independent_expansion", "shared_invariant")), "Witness status contradicts its evidence")
        if row["status"] == "independent_expansion":
            require(identity.startswith("biocompiler.policy.programs.ProgramBuilder.") or
                    identity in {"biocompiler.policy.patterns." + name for name in PATTERNS},
                    "Independent expansion claim outside reviewed builder/pattern scope")
        required = entries[identity]["scope"]
        require((row["status"] == "compatibility_support") == (required == "compatibility_support"), "Compatibility support must not become runtime API")
        require((row["status"] == "dependency") == (required == "dependency"), "Private dependency classification changed")
        used.update(refs)
    require(used == set(witnesses), "Unlinked witness can conceal missing evidence")
    # These exact owned expansions are the committed purpose of this narrow batch.
    for name in PATTERNS:
        row = coverage["biocompiler.policy.patterns." + name]
        require(row["status"] == "independent_expansion" and "pattern." + name in row["witnesses"], "Missing independent pattern expansion: " + name)
    for name, witness in BUILDER_LINKS.items():
        row = coverage["biocompiler.policy.programs.ProgramBuilder." + name]
        require(row["status"] == "independent_expansion" and "builder." + witness in row["witnesses"], "Missing independent builder expansion: " + name)
    for name in ("encounter", "state", "channel", "require"):
        needed = {"boundary." + key for key in BOUNDARY_WITNESSES
                  if key.startswith("encounter_") == (name == "encounter")}
        require(needed <= set(coverage["biocompiler.policy.programs.ProgramBuilder." + name]["witnesses"]),
                "Missing original-ownership/atomic-expansion witness: " + name)
    require(ledger["known_gaps"] == ["shared_controls_do_not_prove_every_api_combination", "source_census_is_not_native_or_release_acceptance"], "Source-only limitations must remain explicit")
    metadata = {
        "witnesses": {key: {name: value[name] for name in ("path", "symbol", "role", "distinction")}
                      for key, value in witnesses.items()},
        "coverage": coverage,
    }
    encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    require(digest(encoded) == REVIEWED_METADATA_SHA256,
            "Reviewed API witness/coverage metadata differs; independent scope review is required")
    previous = {
        "witnesses": {key: value for key, value in metadata["witnesses"].items()
                      if not key.startswith(("typed.", "modules."))},
        "coverage": {key: value for key, value in coverage.items()
                     if not key.startswith(TYPED_MODULE_PREFIXES)},
    }
    encoded_previous = json.dumps(previous, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    require(len(previous["coverage"]) == 905 and digest(encoded_previous) == BEFORE_TYPED_MODULES_METADATA_SHA256,
            "Typed facade and modules must preserve every previous API evidence meaning")
    return {"status": "source_inventory_checked", "claim_scope": CLAIM, "runtime_protocol_scope": RUNTIME_SCOPE, "files": len(expected["files"]),
            "entries": len(entries), "exports": len(expected["exports"]), "cli_commands": len(CLI),
            "native_operations": len(OPERATIONS), "compatibility_support": len(SUPPORT),
            "coverage": dict(sorted(Counter(row["status"] for row in coverage.values()).items()))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(validate(args.root, read_ledger(args.root / LEDGER)), sort_keys=True))
        return 0
    except (ApiCoverageError, OSError, KeyError, TypeError, ValueError, RecursionError) as error:
        print("Policy API inventory: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

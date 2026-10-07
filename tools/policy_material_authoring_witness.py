"""Rebuild the material witness with public Python declarations, without execution.

The policy recipe is reviewed source, not generated/evaluated Python. Catalogs,
domains, models and sequences remain separately supplied original authority.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path

try:
    from generate_policy_exclusion_fixture import build_request
except ModuleNotFoundError:
    from tools.generate_policy_exclusion_fixture import build_request


def build(original: dict) -> tuple[dict, dict]:
    from biocompiler import policy as p
    from biocompiler.core_client import encode_json
    from biocompiler.policy.implementation import prepare_request as implementation_request
    from biocompiler.policy.material import prepare_request as material_request

    def digest(value):
        return hashlib.sha256(encode_json(value)).hexdigest()

    # Construction-time structural checks are permitted here. Native semantic
    # checking begins only after the campaign installs its execution guard.
    authored = build_request()
    supplied = original["implementation_request"]
    definitions = supplied["document"]["program"]["semantics"]["definitions"]
    old_definitions = p.to_data(authored.program.semantics)["definitions"]
    if (definitions[:len(old_definitions)] != old_definitions or len(definitions) != len(old_definitions) + 1
            or definitions[-1]["id"] != "fixture.realization.primitives"):
        raise AssertionError("Supplied realization definition changed the independently authored source definitions")
    semantics = replace(authored.program.semantics,
        definitions=(*authored.program.semantics.definitions, p.from_data(definitions[-1], p.SemanticDefinition)))
    authored = replace(authored, program=replace(authored.program, semantics=semantics),
        implementations=p.from_data(supplied["document"]["implementations"], p.ImplementationCatalogLock))
    document = p.to_data(authored)
    if document != supplied["document"]:
        raise AssertionError("Python builder source differs from the separately retained original policy")
    implementation = implementation_request(authored, **{key: deepcopy(supplied[key]) for key in
        ("definitions", "operating_domain", "implementation_library", "catalog_bindings", "budgets")})
    result = material_request(implementation_request=implementation, **{key: deepcopy(original[key]) for key in
        ("material_contract", "context", "catalog_binding", "budgets")})
    if result != original:
        raise AssertionError("Public request preparation changed complete original material authority")
    return result, {"schema_version": "biocompiler.policy_material_authoring_witness.v0.1",
        "phase": "python_construction_before_native_semantic_guard", "runtime_semantics": "not_executed",
        "recipe_sha256": hashlib.sha256(Path(build_request.__code__.co_filename).read_bytes()).hexdigest(),
        "adapter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "declaration_count": len(authored.program.declarations), "source_document_digest": p.document_digest(authored),
        "source_artifact_digest": digest(document), "implementation_request_digest": digest(implementation),
        "material_request_digest": digest(result)}

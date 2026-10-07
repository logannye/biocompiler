#!/usr/bin/env python3
"""Explicit source-addition lineage for the immutable whole-workflow corpus.

This is a capture-only scope witness. It grants no product authority and never
relabels current source metadata as historical metadata. Historical bytes stay
pinned; two exactly witnessed routes preserve the complete original default AST.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.abc
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/realization-workflow-v1.json"
CORPUS_PIN = "2f5e7636977f559e046776c1bb92bebf67c8f0e733ca463927f8d3a1aee3d77b"
# Each addition requires a fresh explicit review and hash. Wildcards and amended
# hashes for historical source files are deliberately unsupported.
REVIEWED_EXAMPLES = frozenset({"examples/expressive_policies.py", "examples/researcher_alpha.py", "examples/author_staged_research_project.py"})
REVIEWED_ADDITIONS = {
    # Research-project authoring and the installed example stay excluded from
    # the immutable original workflow cohort and confer no historical authority.
    'src/biocompiler/policy/research_project.py': 'fa89ae920fc5bb76893ab06244cc24f9be9c5f836749b51778122eb348acb07c',
    'src/biocompiler/policy/component_inputs.py': '4ccc28475ca07699d4af8e5266edcb94ec34e92ddacc2f7d57bfd12d4253e3f7',
    'examples/author_staged_research_project.py': 'b0ba5562773df57f4a3921ef3c01f0855def5409f198c684e0a96739a4244d4a',
    'examples/researcher_alpha.py': '63d862d55e22de38ba633f901d37c28c7a6fab3cb77ed8604d7fc07df0aac313',
    'src/biocompiler/core_policy_component_selection.py': '3044333719406f253edd8aa2add161fc0d1f6691a5be067bbb4373cee2c583e2',
    'src/biocompiler/policy/component_selection.py': '10d6bcfa36283c57f01e952aecb71d6c9206aa8d119ae8503a669f059ffa5e80',
    "src/biocompiler/core_distribution.py": "10c772076ee0ecfcb0c61a1a3410ae6014313d2e05617f30bc77f6df55485459",
    "src/biocompiler/core_pipeline_build_views.py": "85492c4f77b3104af2dae9d9180a0518bfd4fb61c9d6143880e6e58e10a77382",
    "src/biocompiler/core_pipeline_provider_views.py": "ea18d951f8170b1e1da4fbe6636d40e83f54ebda2ebdce187b0e08cf257b9c35",
    "src/biocompiler/core_pipeline_manager.py": "44eeed2c22a9d07ff254dcd5b1e1edd26cf7e6bcfc29918ae20da39c2fbb544c",
    "src/biocompiler/reference_backend.py": "f390f40bb7f176e2cd45acde4db84e7aa987d8a7125269a1ceba37ea59b26358",
    "src/biocompiler/core_reference_host.py": "a31be5b73f1440d92cf8076fdad9d69ec9ae8605217d400af20d47f5d4e4305e",
    "src/biocompiler/core_reference_manager.py": "cd75fca7e114b76ea42dfe433c399f175e6402ea7270f00e5ed5982d584bbd31",
    "src/biocompiler/core_reference_provider_views.py": "1b4989571d71292eaa9998787f249fd7d60439958cbc8da6f36c2acca39c6bce",
    "src/biocompiler/core_reference_views.py": "a295b4583be057a743959d077add14ae7c5424086f7edddd322dfb188786d9f9",
    "src/biocompiler/core_pipeline_callback_session.py": "d24cb3b78df7b7c85d0bbec5cd3c7634ca4756c5e8b0e113a8a3ba7258229a54",
    "src/biocompiler/pipeline_callback_objects.py": "ac5198795c3e80cff511e0fe372dc578a983d8be947e41dd9debd9f719da9eec",
    "src/biocompiler/core_pipeline_session.py": "8de06056804e4e58350fa562c438acf2b6306a462edd9df3a1da2070f298d169",
    "src/biocompiler/core_synthetic_inspection.py": "5ab68d6f1dac300af1e0d7431f5ba45aa2df493c1f446a8ccd67b56ae831178f",
    "src/biocompiler/core_synthetic_producer_public.py": "15db52841e774d4fdf42ed937dfe173ca844cae920fb6419bbc54eec70c31082",
    "src/biocompiler/synthetic_producer_cli.py": "4e500dd094e41841fa15635b1be6a805a0b3b992de574dda888f4d91fa881221",
    "src/biocompiler/core_synthetic_producer.py": "233ae7ffd5a10e7158b1ac833194aa4b5b05de5334e73adf77aad9d081fb1917",
    "src/biocompiler/synthetic_producer_backend.py": "99584aaa6be87849ebf1cc5eea0ba0821b86f4ca03abc190b0261a8903647db3",
    "src/biocompiler/core_workflow.py": "43b57b87a2d89db200463d8aed8b7eea7e262cf1c4ea02c772843598dbda90df",
    "src/biocompiler/core_artifacts.py": "77cf4dc31efb782c7fbb44fe8e79714a60e2e20374f9e7569fdce8f70d8ec59a",
    "src/biocompiler/workflow_backend.py": "81958a4fc1147b2ea10eae7c7bac15a68338b1cb21b738805ae04538c7bdc1db",
    "src/biocompiler/core_workflow_authority.py": "ded29c7cd4c16241812bd7f677b0c962d185a724fef1cd7294c7e899c7c32d66",
    "src/biocompiler/workflow_cli.py": "641cf7f6451e52c5dd4a09a28c75c89329191aa373aed36cc9dc92c573207bd5",
    # Independently reviewed policy transports remain outside original authority.
    'src/biocompiler/policy/component_material.py': '24da1db993f5f56ff516ad3b2d14667731f681ebe9f1c9ae6898d0728bd5eaba',
    'src/biocompiler/core_policy_component_material.py': 'e5645b27e70f39a4979fee53638007044c44d37bec4f1a8af7e866f95a38f9e0',
    'src/biocompiler/policy/material.py': '5893a53e408ff4b408049b9bdb370ebb20a77688d8b5b4b825f308d2a40fdd79',
    'src/biocompiler/core_policy_material.py': 'bc8d44be6b6aa7a6d56d4352c85d6a2f8c9201ab626e6ebe1bcc265487b46704',
    'src/biocompiler/policy/implementation.py': '4e1de0535cf852885169328aaae035caff9178b367b84f204c1e68eaae478515',
    'src/biocompiler/core_policy_implementation.py': 'ca0815363676dd8fd112b91b8d1adf303bedabb0f543ef2305d5f59c433906cd',
    # Explicit operational-policy transport and CLI stay excluded from the
    # original workflow cohort; these pins do not broaden historical authority.
    'src/biocompiler/core_policy_operational.py': '089805c81bf6f84e5cf5e264b6ed89babedc3d692e2a7605429aa388e6d5ed02',
    'src/biocompiler/policy/operational.py': 'b3db654830b8477c29de9fc13a9fd05cf6337a512cfcd86dde9391146cf4efee',
    'src/biocompiler/policy/native.py': '956e33656d6b5ee332fae215a56d667d7b88019d7853426440aa5502777dc9f0',
    'src/biocompiler/core_policy.py': '9af5592f01bfb721965376ec0051b0eeaba9bfcb38ba6db3a3c56351b708044e',
    'examples/expressive_policies.py': 'face2b9c24b039da9931b4af4e4fc26ad4fcec94b9aa338196c2c7455d789bec',
    'src/biocompiler/entrypoint.py': '7158963ef6435bcd8d8dbbb4952b185c6a64414fe01f8651b6e3dccff5492ed8',
    'src/biocompiler/policy/__init__.py': 'd9dd6be96e54f316bd087c0953d4cfce8214d170112e674b4c58edf81d28697b',
    'src/biocompiler/policy/behavior.py': '691b7710b8e915665526e57ba41f3b2df3fe1519ec22371d47441050c37e34bf',
    'src/biocompiler/policy/catalog.py': '96bd1729202b96c12fcaea35e2ca1560011bed7a5dd712e2fc8d0a5fc9ff3e30',
    'src/biocompiler/policy/chassis.py': '21960a5498db0934150ab5288eb6de30c2eb63062fe9e06a2c57a0214c811ab1',
    'src/biocompiler/policy/cli.py': 'beaff7cf4994019f24fab7361e588a3702b32bb16d357bda42e16000a5060d0f',
    'src/biocompiler/policy/coordination.py': 'ce597e5c05dc1f64b73bbeb4b60ae9863b26c645155ce03ea46a827135b009c9',
    'src/biocompiler/policy/deployment.py': 'cddace3d45f04ecd722a47849325c9ff6a41fc166b0e23253c2377f037eae29f',
    'src/biocompiler/policy/effects.py': '2e228309b98defa71730cac3e2b8883a9e86c9f63f0d5c25b37bf70b27a02578',
    'src/biocompiler/policy/entities.py': 'f38a35089b5c5c7522b012729f95a2b17f45fd2a56c1affe168aa526fb1d7f18',
    'src/biocompiler/policy/examples.py': '36f4e4ba467ae48bc2bfb1d1f54455533a7981dcd8a2c659227d34d06807017a',
    'src/biocompiler/policy/handoff.py': 'a51200b3bb412ebc65cc43df3d69435ea37a7f48a75ba2eba5b7fbafd2479a51',
    'src/biocompiler/policy/inspection.py': '7eca4c5bf12aab21899bb7c9e54b64f8255bae9759e7ebd6a4858bf0f5e76caf',
    'src/biocompiler/policy/logic.py': 'cc0a0fe952f9c8aa16fb5714d0cd1972296154cf1e5e5deed4e7ea9ece3ddf4f',
    'src/biocompiler/policy/model.py': '7197696399733e610b7a5c458aebf0ddc4b0df997f190cb53fa1659c419b6038',
    'src/biocompiler/policy/observations.py': '24400413e0b42fad132d02d0841cfdc3f9307c452e64ec1b2283be7f389f5a26',
    'src/biocompiler/policy/patterns.py': '9640080fa505e361b09a2dd9a644938365549b37c8be3a8ce547bc1391044b48',
    'src/biocompiler/policy/programs.py': 'ef2823520e47f29f666c8c6bec8f30d43a21195ab5379ae82e0a062563f686fd',
    'src/biocompiler/policy/requirements.py': '80579a127424a9d179d67406e2eecd6bc875ed2b6edcc7fc19f823cf4e7beb3b',
    'src/biocompiler/policy/serialization.py': 'd0e2feb4e8dd3fe65a10793d20c06144ad6fec396d99e6107f3485682ee570bf',
    'src/biocompiler/policy/space.py': 'c32bc67b86370f471fcabe54fdb61332f746130bc23e22d5a2ce7e08666b97c9',
    'src/biocompiler/policy/state.py': '94ef54313d4475428ca678258dfe59727c8dbbe8d327e26b79ba819dcc20d22d',
    'src/biocompiler/policy/time.py': '115fad72c39fa62587d1253e78a374162b0e1543ba146d8634773bab5d41b969',
    'src/biocompiler/policy/validation.py': '00be9fc170771f06ee7fae34c17ec9a47fcd1c1741efb34fd64044a114d7c5b8',
    'src/biocompiler/policy/values.py': '56b36e3e4cc8d2caad0bbd26e7ef626eed0b694a50731911e537f4454555bca5',
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def require(value, message):
    if not value:
        raise AssertionError(message)


def historical_sources():
    index = json.loads(CORPUS.read_bytes())
    require(index["inventory_fingerprint"] == CORPUS_PIN and digest(canonical(
        {key: value for key, value in index.items() if key != "inventory_fingerprint"})) == CORPUS_PIN,
        "Immutable workflow source-scope inventory changed")
    return index["source_files"]


def addition_counterparts(additions):
    """Retain the exact reviewed Core revision proof; never admit new hashes."""
    from tools import reference_original_counterpart as reference
    from tools import reference_attempt_source as attempt
    if attempt.SOURCE in additions:
        require(additions[attempt.SOURCE] == REVIEWED_ADDITIONS[attempt.SOURCE] == attempt.TARGET_CURRENT,
                'Unreviewed current Molecular facade addition identity')
        attempt.restore((ROOT / attempt.SOURCE).read_bytes())
    if reference.CALLBACK_SOURCE in additions:
        require(additions[reference.CALLBACK_SOURCE] == REVIEWED_ADDITIONS[reference.CALLBACK_SOURCE]
                == reference.CALLBACK_CURRENT_SHA, 'Unreviewed current callback addition identity')
        reference.callback_source_witness((ROOT / reference.CALLBACK_SOURCE).read_bytes())
    if reference.CORE_SOURCE not in additions:
        return []
    require(additions[reference.CORE_SOURCE] == REVIEWED_ADDITIONS[reference.CORE_SOURCE]
            == reference.CORE_CURRENT_SHA, "Unreviewed current Core addition identity")
    _, proof = reference.core_source_witness((ROOT / reference.CORE_SOURCE).read_bytes())
    return [proof]


def addition_module(path):
    require(path.endswith(".py") and (path.startswith("src/biocompiler/") or path in REVIEWED_EXAMPLES),
            "Unreviewed addition import shape")
    relative = path[4:] if path.startswith("src/") else path
    return relative[:-3].replace("/", ".").removesuffix(".__init__")


def source_scope(actual, *, allow_missing_tests=False):
    historical = historical_sources()
    before = {row["path"]: row["sha256"] for row in historical}
    current = {row["path"]: row["sha256"] for row in actual}
    require(len(current) == len(actual), "Duplicate current workflow source")
    missing = set(before) - set(current)
    require(not missing or allow_missing_tests and all(path.startswith("tests/") for path in missing),
            "Historical workflow authority source is missing")
    from tools.policy_entrypoint_source_lineage import PATHS as POLICY_ROUTES, ENTRYPOINT, verify_entrypoint
    routes = []
    for path in sorted(set(before) & set(current)):
        if before[path] != current[path]:
            from tools.workflow_source_lineage import HISTORICAL
            from tools.synthetic_producer_source_lineage import HISTORICAL as PRODUCERS
            from tools.manager_registration_source_lineage import HISTORICAL as MANAGERS
            from tools.realization_source_lineage import verify_captured_source, REFERENCE_ROUTES
            require(path in HISTORICAL or path in PRODUCERS or path in MANAGERS or path in REFERENCE_ROUTES or path in POLICY_ROUTES, "Historical workflow source bytes changed: " + path)
            require(digest((ROOT / path).read_bytes()) == current[path],
                    "Historical workflow source bytes changed: " + path)
            try:
                route = verify_captured_source(ROOT, {"path": path, "sha256": before[path]})
            except ValueError as error:
                raise AssertionError("Historical workflow source bytes changed: " + path) from error
            require(route["current_sha256"] == current[path], "Historical workflow source bytes changed: " + path)
            routes.append(route)
    additions = {path: current[path] for path in sorted(set(current) - set(before))}
    for path, sha in additions.items():
        require(REVIEWED_ADDITIONS.get(path) == sha, "Unreviewed workflow source addition: " + path)
        require(digest((ROOT / path).read_bytes()) == sha, "Reviewed addition bytes changed")
    if ENTRYPOINT in additions:
        require(verify_entrypoint()["sha256"] == additions[ENTRYPOINT], "Unreviewed authoring dispatch module")
    modules = []
    for path in additions:
        if path != ENTRYPOINT:
            modules.append(addition_module(path))
    result = {
        "schema_version": "biocompiler.realization_workflow_source_scope.v2" if routes else "biocompiler.realization_workflow_source_scope.v1",
        "historical_corpus_pin": CORPUS_PIN,
        "historical_sources": historical,
        "actual_sources": actual,
        "historical_source_inventory_sha256": digest(canonical(historical)),
        "actual_source_inventory_sha256": digest(canonical(actual)),
        "reviewed_additions": [{"path": path, "sha256": sha} for path, sha in additions.items()],
        "reviewed_source_routes": routes,
        "denied_modules": modules,
        "omitted_tests_for_focused_instrumentation": sorted(missing),
        "comparison": "exact_original_observations_and_documents_after_explicit_historical_source_projection_only",
        "reviewed_addition_counterparts": addition_counterparts(additions),
    }
    if routes:
        result["reviewed_routes"] = routes
    return result


@contextmanager
def deny_added_modules(scope):
    modules = tuple(scope["denied_modules"])
    require(all(name not in sys.modules for name in modules),
            "Reviewed added transport module was imported before original cohort capture")

    class Deny(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if any(fullname == name or fullname.startswith(name + ".") for name in modules):
                raise AssertionError("Original cohort tried to import excluded source addition: " + fullname)
            return None

    finder = Deny()
    sys.meta_path.insert(0, finder)
    try:
        yield
        require(all(name not in sys.modules for name in modules),
                "Original cohort imported a reviewed excluded transport module")
    finally:
        sys.meta_path.remove(finder)


def historical_projection(document, scope):
    require(document["source_files"] == scope["actual_sources"],
            "Source-scope receipt does not describe the actual capture")
    require(not scope["omitted_tests_for_focused_instrumentation"],
            "Focused capture cannot become a whole-corpus source projection")
    return {**document, "source_files": scope["historical_sources"]}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    sys.path[:0] = [str(ROOT), str(ROOT / "src")]
    from tools.freeze_realization_workflow import source_inventory
    scope = source_scope(source_inventory())
    args.output.write_bytes(canonical({"status": "source_lineage_verified",
        "native_execution": False, "scope": scope}) + b"\n")

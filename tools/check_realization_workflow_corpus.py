#!/usr/bin/env python3
"""Explicit source-addition lineage for the immutable whole-workflow corpus.

This is a capture-only scope witness. It grants no product authority and never
relabels current source metadata as historical metadata. Existing source files
must retain every pinned byte; only separately reviewed additions are allowed.
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
REVIEWED_EXAMPLES = frozenset({"examples/expressive_policies.py"})
REVIEWED_ADDITIONS = {
    'src/biocompiler/policy/material.py': '2ab58d3597b47147f989da073c024f5fede97f7842ce1d7c6efa311abd8544fd',
    'src/biocompiler/core_policy_material.py': 'b3a28a1f40d475de8848cc6cea45d4c0975042da17b2c90977facca7f2d9100c',
    'src/biocompiler/policy/implementation.py': '4e1de0535cf852885169328aaae035caff9178b367b84f204c1e68eaae478515',
    'src/biocompiler/core_policy_implementation.py': 'b0a1c56ed960e146153dcb1f89ac28cc0f809a79716a7f7c1e096496b4bcf556',
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
    'src/biocompiler/policy/cli.py': '2eab649fbcf2223e26312b4987a842bf251425b1779ce795a3542fa8ab97cc60',
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
    'src/biocompiler/policy/patterns.py': 'a906a7acc9ca55aa0feee855d56a39c9b1d6b80bba8a502ba13beeff35de21be',
    'src/biocompiler/policy/programs.py': '86e983e87902407d30ee1b6146a7494298b072f9f70fae60825b050423784296',
    'src/biocompiler/policy/requirements.py': '80579a127424a9d179d67406e2eecd6bc875ed2b6edcc7fc19f823cf4e7beb3b',
    'src/biocompiler/policy/serialization.py': 'd0e2feb4e8dd3fe65a10793d20c06144ad6fec396d99e6107f3485682ee570bf',
    'src/biocompiler/policy/space.py': 'c32bc67b86370f471fcabe54fdb61332f746130bc23e22d5a2ce7e08666b97c9',
    'src/biocompiler/policy/state.py': '94ef54313d4475428ca678258dfe59727c8dbbe8d327e26b79ba819dcc20d22d',
    'src/biocompiler/policy/time.py': '115fad72c39fa62587d1253e78a374162b0e1543ba146d8634773bab5d41b969',
    'src/biocompiler/policy/validation.py': '00be9fc170771f06ee7fae34c17ec9a47fcd1c1741efb34fd64044a114d7c5b8',
    'src/biocompiler/policy/values.py': '56b36e3e4cc8d2caad0bbd26e7ef626eed0b694a50731911e537f4454555bca5',
    "src/biocompiler/core_workflow.py": "c2e1a16518756f89f6bb84437e2f77634be2983986376e837b548d51047df9d0",
    "src/biocompiler/core_artifacts.py": "9cf24948c12d617dc783317b4f16330e1be69feba64cfec70767288556011e4e",
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
    from tools.policy_entrypoint_source_lineage import PATHS, ENTRYPOINT, verify_entrypoint, verify_source
    routes = []
    for path in sorted(set(before) & set(current)):
        if before[path] != current[path]:
            require(path in PATHS and digest((ROOT / path).read_bytes()) == current[path],
                    "Historical workflow source bytes changed: " + path)
            try:
                routes.append(verify_source(ROOT, path, before[path]))
            except ValueError as error:
                raise AssertionError("Historical workflow source bytes changed: " + path) from error
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
    return {
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
    }


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

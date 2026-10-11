"""Compose pinned packaging and policy dispatch edits over original CLI bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = "pyproject.toml"
WITNESS = "tests/conformance/package-metadata-source-counterpart-v1.json"
WITNESS_SHA256 = "13f1ef0b3af5fd6b0310dacd6763244aae008c8fd8252e0c61428deef1b99fc1"
HISTORICAL_SHA256 = "e472f2690706a91859854e2e057fec201390b3742fb8840c02306f0356b4f690"
CURRENT_SHA256 = "be0a8547356afa58d67f4b8c7629ab37d85a80dedef600f3a9b9a00cfdf08b85"
CHANGES = (
    ("[project.scripts]\n", '[project.optional-dependencies]\ncore = ["biocompiler-core==0.1.0.dev29"]\n\n[project.scripts]\n'),
    ('biocompiler = ["py.typed", "studio/static/*", "studio/data/*.json"]',
     'biocompiler = ["_core_release.json", "py.typed", "studio/static/*", "studio/data/*.json"]'),
)

CAR_DATA_CHANGES = (
    ('"studio/data/*.json"]', '"studio/data/*.json", "policy/data/*.json"]'),
)
CAR_CURRENT_SHA256 = "75c25fee15af61614d4c60649f723fafe58bcc6d2c58357a4ec29546b8f407b4"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def counterpart(root=ROOT, *, current=None):
    root = Path(root)
    path = root / WITNESS
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 16384,
            "Package metadata witness is missing, redirected or oversized")
    raw = path.read_bytes()
    require(sha(raw) == WITNESS_SHA256, "Package metadata witness bytes changed")
    entry = json.loads(raw)
    require(set(entry) == {"schema_version", "path", "base_revision", "scope",
                          "historical_sha256", "current_sha256", "historical_source",
                          "current_source", "changes"}
            and entry["schema_version"] == "biocompiler.package_metadata_source_counterpart.v1"
            and entry["path"] == PATH
            and entry["base_revision"] == "56c710a47560297969b2f7159a430340d2feeafe"
            and entry["historical_sha256"] == HISTORICAL_SHA256
            and entry["current_sha256"] == CURRENT_SHA256
            and entry["changes"] == [{"before": before, "after": after} for before, after in CHANGES],
            "Package metadata counterpart is outside its exact recipe")
    historical = entry["historical_source"].encode()
    proposed = entry["current_source"].encode()
    require(sha(historical) == HISTORICAL_SHA256 and sha(proposed) == CURRENT_SHA256,
            "Package metadata whole source identity changed")
    expected = historical
    for before, after in CHANGES:
        require(expected.count(before.encode()) == 1, "Package metadata edit is not unique")
        expected = expected.replace(before.encode(), after.encode(), 1)
    require(expected == proposed, "Package metadata has an unlisted whole-source change")
    from tools import policy_entrypoint_source_lineage as policy
    policy_entry = policy.witness(root)["sources"][PATH]
    policy_current = policy_entry["after_source"].encode()
    restored, policy_proof = policy.restore(PATH, policy_current, root=root)
    require(restored == historical,
            "Packaging and policy dispatch witnesses do not share exact original metadata")
    composed = policy_current
    for before, after in CHANGES:
        require(composed.count(before.encode()) == 1, "Composed package metadata edit is not unique")
        composed = composed.replace(before.encode(), after.encode(), 1)
    packaging_dispatch = composed
    for before, after in CAR_DATA_CHANGES:
        require(composed.count(before.encode()) == 1, "CAR package data edit is not unique")
        composed = composed.replace(before.encode(), after.encode(), 1)
    require(sha(composed) == CAR_CURRENT_SHA256,
            "CAR package metadata exceeds its reviewed complete source identity")
    if current is None:
        path = root / PATH
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 4096,
                "Current package metadata is missing, redirected or oversized")
        current = path.read_bytes()
    require(type(current) is bytes and current == composed,
            "Current package metadata differs from its exact whole-source counterpart")
    return historical, {"schema_version": "biocompiler.package_metadata_source_counterpart.v3", "path": PATH,
        "historical_sha256": HISTORICAL_SHA256, "current_sha256": sha(current),
        "witness_sha256": WITNESS_SHA256, "current_source": current.decode(),
        "changes": entry["changes"], "packaging_source_sha256": CURRENT_SHA256,
        "policy_entrypoint_counterpart": policy_proof,
        "composition": "exact_packaging_dispatch_and_car_data_changes",
        "packaging_dispatch_sha256": sha(packaging_dispatch),
        "car_data_changes": [{"before": before, "after": after} for before, after in CAR_DATA_CHANGES]}

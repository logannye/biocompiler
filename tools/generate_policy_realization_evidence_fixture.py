"""Independent synthetic off-grid measurement literals; never empirical proof."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "core/test/data/policy_realization_evidence_v01.json"
MATERIAL_PATH = ROOT / "core/test/data/policy_quantitative_network_v01.json"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def source(identity, body):
    return {"identity": {"schema_version": "biocompiler.component_identity.v0.1", "kind": "source", "id": identity,
                         "version": "1", "content_fingerprint": digest(body)}, "body": body}


def artifact(identity):
    return {"id": identity, "sha256": hashlib.sha256(("artificial fixture: " + identity).encode()).hexdigest(),
            "media_type": "text/plain", "locator": "synthetic-fixture:" + identity}


def provenance(identity):
    return {"origin": "synthetic_fixture", "producer": "independent-literal-fixture", "recorded_at": "2026-10-09",
            "artifact": artifact(identity)}


def build():
    material = json.loads(MATERIAL_PATH.read_text())
    request = material["request"]
    law = request["quantitative"]["mechanism"]
    context, original = request["context"], request["implementation_request"]
    applicability = {"recipient_fingerprint": digest(context["recipient"]),
        "deployment_fingerprint": digest(original["document"]["deployment"]), "clock_fingerprint": digest(context["clock"]),
        "operating_domain_fingerprint": digest(original["operating_domain"]),
        "environment_fingerprints": [digest(provider["body"]) for provider in context["providers"] if provider["body"]["kind"] == "environment"]}
    def quantity(amount):
        return {"$type": "Quantity", "amount": amount, "unit": deepcopy(law["unit"])}
    def interval(lower, upper):
        return {"lower": quantity(lower), "upper": quantity(upper)}
    target = {"id": "transport-amount", "instance": "control", "component": deepcopy(request["quantitative"]["selection"]["component"]),
        "mechanism_fingerprint": digest(law), "parameter": {"kind": "transfer_amount", "transfer": "a_to_b"},
        "nominal": quantity("1"), "accepted_interval": interval("0.9", "1.1"), "minimum_replicates": 3,
        "applicability": applicability}
    protocol = source("fixture.protocol", {"quantity_semantics": "amount_per_accepted_sample", "sample_period": deepcopy(law["sample_period"]),
        "procedure": "Artificial isolated transfer amount intervals for one accepted sample. No physical procedure was performed.",
        "provenance": provenance("protocol")})
    dataset = source("fixture.dataset", {"requirement": "transport-amount", "protocol": deepcopy(protocol["identity"]),
        "applicability": deepcopy(applicability), "replicates": [
            {"id": "r1", "interval": interval("0.97", "1.02")},
            {"id": "r2", "interval": interval("0.99", "1.03")},
            {"id": "r3", "interval": interval("0.98", "1.01")}], "provenance": provenance("raw-dataset")})
    # Independently specified extrema; no authoring evaluator or checker generates this oracle.
    envelope = interval("0.97", "1.03")
    analysis = source("fixture.analysis", {"dataset": deepcopy(dataset["identity"]), "method": "replicate_interval_envelope.v0.1",
        "replicate_ids": ["r1", "r2", "r3"], "envelope": envelope,
        "software": {"name": "independent-literal-analysis", "version": "1", "artifact": artifact("analysis-software")},
        "provenance": provenance("analysis")})
    return {"schema_version": "biocompiler.policy_realization_evidence_literals.v0.1",
        "notice": "Synthetic interval compatibility test data. No experiment, artifact authenticity, statistical coverage or biological validity is established.",
        "material_fixture_fingerprint": digest(material),
        "contract": {"schema_version": "biocompiler.policy_realization_evidence_contract.v0.1",
            "profile": "biocompiler.policy_parameter_measurement_evidence.v0.1", "require_compatibility": False,
            "requirements": [target], "dossier": {"protocols": [protocol], "datasets": [dataset], "analyses": [analysis]}},
        "expected": {"status": "supported", "recomputed_envelope": deepcopy(envelope), "empirical": "unassessed", "origins": ["synthetic_fixture"]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = json.dumps(build(), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"
    if args.check:
        assert PATH.read_text() == encoded, "Evidence fixture changed; inspect independent premises"
    else:
        PATH.write_text(encoded)


if __name__ == "__main__":
    main()

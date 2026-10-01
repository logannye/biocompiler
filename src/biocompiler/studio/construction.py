"""Read-only construction views; browser transport keeps authoritative JSON text."""

from biocompiler.artifacts.circuit_construction_build import CircuitConstructionBuild
from biocompiler.artifacts.circuit_inspection import inspect_circuit_construction
from biocompiler.ir.circuit_construction import CircuitConstructionRequest
from biocompiler.ir.serialization import fields, require
from biocompiler.studio.service import _json_document


def _load(payload, *, saving=False):
    keys = {"build_json", "expected_request_json"}
    if saving:
        keys.add("expected_build_fingerprint")
    fields(payload, keys, "construction inspection")
    # Validate bytes/depth before decoding. Never evaluate source code or fetch a
    # provenance URL. Raw text avoids JavaScript integer/float normalization.
    build = CircuitConstructionBuild.from_dict(
        _json_document(payload["build_json"], "Construction build")
    )
    text = payload["expected_request_json"]
    require(text is None or isinstance(text, str), "Expected authority JSON text or null.")
    authority = None if text is None else CircuitConstructionRequest.from_dict(
        _json_document(text, "Independent construction authority")
    )
    if saving:
        require(build.fingerprint == payload["expected_build_fingerprint"],
                "Construction changed since inspection; inspect the current build again.")
    return build, authority


def inspect(payload):
    build, authority = _load(payload)
    return inspect_circuit_construction(build, expected_request=authority)


def save(payload):
    """Losslessly return the original retained artifact after checking current inputs.

    This saves a historical record, not a newly admitted deployment or synthesis
    artifact. With supplied authority the same independent replay is required.
    """
    build, authority = _load(payload, saving=True)
    report = inspect_circuit_construction(build, expected_request=authority)
    return {"build_json": payload["build_json"], "build_fingerprint": build.fingerprint,
            "freshness": report["freshness"], "claims": report["claims"]}

"""Current Python transport responses for the TypeScript boundary tests.

These artificial software fixtures exercise display contracts only. They are
generated afresh rather than maintaining a second hand-authored response schema.
"""

import json
import os
from pathlib import Path

import biocompiler

_source_root = Path(__file__).resolve().parents[2] / "src"
_using_source = Path(biocompiler.__file__).resolve().is_relative_to(_source_root)
assert _using_source == (os.environ.get("STUDIO_TEST_SOURCE") == "1"), (
    "Studio fixtures must use the installed package unless STUDIO_TEST_SOURCE=1 explicitly selects source checks."
)

from examples.circuit_infrastructure import make_infrastructure_requests
from examples.circuit_sources import make_source_inventory
from biocompiler.compiler.circuit_construction import build_circuit_construction
from biocompiler.studio import construction, service
from biocompiler.verification.circuit_evidence import capture_circuit_evidence


session = service.session("transport-test-session")
prepared = service.prepare({"request_json": session["example"]["request_json"]})
compiled = service.compile_request({"request_json": prepared["request_json"]})
exported = service.export({
    "request_json": compiled["request_json"], "record_json": compiled["record_json"],
    "format": "fasta",
})
request, bindings, evidence = make_infrastructure_requests()
build = build_circuit_construction(request)
payload = {"build_json": build.to_json() + "\r\n", "expected_request_json": None}
historical = construction.inspect(payload)
payload["expected_request_json"] = request.to_json()
payload["review"] = {
    "source_inventory_json": make_source_inventory().to_json(),
    "binding_request_json": bindings.to_json(),
    "evidence_request_json": evidence.to_json(),
    "evidence_receipt_json": capture_circuit_evidence(build, expected_request=evidence).to_json(),
}
reviewed = construction.inspect(payload)
saved = construction.save({**payload, "expected_build_fingerprint": build.fingerprint})
print(json.dumps({
    "session": session, "prepared": prepared, "compiled": compiled,
    "exported": exported, "historical": historical, "reviewed": reviewed, "saved": saved,
}, ensure_ascii=False, allow_nan=False))

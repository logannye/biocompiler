"""Frozen request preparation, real compilation, and independently checked exports.

The bundled example is an artificial software fixture with repository-relative
source filenames and retained line/function coordinates. Imported authority is
never rewritten to resemble that fixture.
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import replace
from functools import lru_cache
from importlib import resources
import json

from biocompiler import __version__
from biocompiler.compiler.candidate import (
    compile_candidate,
    export_candidate_fasta,
    verify_candidate_build,
)
from biocompiler.compiler.candidate_requirements import lower_candidate_requirements
from biocompiler.ir.candidate import CandidateConstraints, CandidateRequest
from biocompiler.ir.candidate_build import CandidateBuildRecord
from biocompiler.ir.intent import IntentProgram
from biocompiler.ir.serialization import fields, fingerprint, parse_json, require
from biocompiler.errors import SerializationError

MAX_SOURCE_NODES = 512
MAX_LIBRARY_BASES = 100_000
MAX_JSON_DEPTH = 64
MAX_JSON_TEXT_BYTES = 2 * 1024 * 1024


def bounded_document(document):
    """Reject deep or oversized operation inventories before artifact decoding."""
    pending = [(document, 0)]
    while pending:
        value, depth = pending.pop()
        require(
            depth <= MAX_JSON_DEPTH, "Studio JSON nesting exceeds the supported depth."
        )
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeError as exc:
                raise SerializationError(
                    "Studio JSON must contain valid Unicode text."
                ) from exc
        elif isinstance(value, Mapping):
            nodes = value.get("nodes")
            require(
                not isinstance(nodes, (list, tuple)) or len(nodes) <= MAX_SOURCE_NODES,
                f"Studio requests support at most {MAX_SOURCE_NODES} source nodes.",
            )
            pending.extend((item, depth + 1) for item in value.values())
            pending.extend((item, depth + 1) for item in value)
        elif isinstance(value, (list, tuple)):
            pending.extend((item, depth + 1) for item in value)


@lru_cache(maxsize=1)
def example_request():
    """Read installed package data; no import or execution of repository examples."""
    document = (
        resources.files("biocompiler.studio")
        .joinpath("data", "example-request.json")
        .read_text(encoding="utf-8")
    )
    return CandidateRequest.from_json(document)


@lru_cache(maxsize=2)
def _example_product(product):
    require(
        isinstance(product, str)
        and product in {"declared_product", "alternative_product"},
        "Choose a supplied example product.",
    )
    request = example_request()
    if product == "declared_product":
        return request
    source = request.source
    behavior = source.behavior_request
    intent = behavior.build_request.intent.to_dict()
    for node in intent["nodes"]:
        if node["kind"] == "secretion":
            node["attributes"]["product"] = product
    build = replace(behavior.build_request, intent=IntentProgram.from_dict(intent))
    behavior = replace(
        behavior,
        build_request=build,
        contract=replace(behavior.contract, product=product),
    )
    source = replace(
        source,
        deployment_request=replace(
            source.deployment_request, behavior_request=behavior
        ),
        acceptance=replace(
            source.acceptance, behavior_fingerprint=behavior.fingerprint
        ),
    )
    return replace(request, source=source)


def _request(document):
    bounded_document(document)
    if isinstance(document, Mapping) and isinstance(document.get("library"), Mapping):
        parts = document["library"].get("parts")
        if isinstance(parts, (tuple, list)):
            bases = sum(
                len(part["fragment"]["sequence"])
                for part in parts
                if isinstance(part, Mapping)
                and isinstance(part.get("fragment"), Mapping)
                and isinstance(part["fragment"].get("sequence"), str)
            )
            require(
                bases <= MAX_LIBRARY_BASES,
                f"Studio libraries support at most {MAX_LIBRARY_BASES} total nucleotide symbols.",
            )
    request = CandidateRequest.from_dict(document)
    require(
        len(request.build_request.intent.nodes) <= MAX_SOURCE_NODES,
        f"Studio requests support at most {MAX_SOURCE_NODES} source nodes.",
    )
    require(
        sum(len(part.fragment.sequence) for part in request.library.parts)
        <= MAX_LIBRARY_BASES,
        f"Studio libraries support at most {MAX_LIBRARY_BASES} total nucleotide symbols.",
    )
    return request


def _json_document(text, label):
    """Keep browser number coercion outside authoritative artifact transport."""
    require(isinstance(text, str), f"{label} must be a JSON string.")
    require(len(text) <= MAX_JSON_TEXT_BYTES, f"{label} exceeds the Studio JSON size limit.")
    try:
        size = len(text.encode("utf-8"))
    except UnicodeError as exc:
        raise SerializationError(f"{label} must contain valid Unicode text.") from exc
    require(size <= MAX_JSON_TEXT_BYTES, f"{label} exceeds the Studio JSON size limit.")
    document = parse_json(text)
    bounded_document(document)
    return document


def _request_payload(payload, label):
    require(isinstance(payload, Mapping), f"{label} must be an object.")
    if set(payload) == {"request_json"}:
        return _request(_json_document(payload["request_json"], "Request JSON"))
    fields(payload, {"request"}, label)
    return _request(payload["request"])


def overview(request):
    """Describe actual retained intent without treating a guard as implemented."""
    requirements = lower_candidate_requirements(request)
    nodes = {node.id: node for node in request.build_request.intent.nodes}
    role = nodes[requirements.role_id]
    rule = request.build_request.intent.find(kind="rule")[0]
    guard = nodes[rule.inputs[1]]
    signals = request.build_request.intent.find(kind="signal")
    cue = ", ".join(str(node.attributes.get("name", node.id)) for node in signals)
    if guard.kind == "qualitative" and len(guard.inputs) == 1:
        signal = nodes[guard.inputs[0]]
        condition = (
            str(signal.attributes.get("name", signal.id))
            + "."
            + str(guard.attributes.get("band", "qualitative"))
            + "()"
        )
    else:
        condition = guard.kind + " [" + guard.id + "]"
    products = defaultdict(set)
    for binding in request.library.products:
        products[binding.product].add(binding.protein_sequence)
    base = example_request()
    fixture = request.library.fingerprint == base.library.fingerprint and any(
        fingerprint(request.source.to_dict())
        == fingerprint(_example_product(product).source.to_dict())
        for product in ("declared_product", "alternative_product")
    )
    constraints = {
        key: value
        for key, value in request.constraints.to_dict().items()
        if key != "schema_version"
    }
    return {
        "product": requirements.product,
        "cell_type": str(role.attributes.get("cell_type", "Unspecified cell type")),
        "cue": cue or "No named signal in retained source",
        "target_name": request.target.context_id,
        "architecture_options": [
            {"id": item.id, "label": item.id.replace("_", " ")}
            for item in sorted(request.library.architectures, key=lambda item: item.id)
        ],
        "product_options": [
            {
                "id": product,
                "label": product.replace("_", " "),
                "protein": " / ".join(sorted(proteins)),
            }
            for product, proteins in sorted(products.items())
        ],
        "constraints": constraints,
        "constraints_json": json.dumps(constraints, sort_keys=True, indent=2),
        "source_summary": (
            f"When {condition}, the source requests ongoing secretion of {requirements.product}. "
            "Sensing, control and secretion remain unimplemented by this coding-cassette profile."
        ),
        "library_name": request.library.id,
        "fixture": fixture,
    }


def session(token):
    request = example_request()
    return {
        "token": token,
        "version": __version__,
        "example": {
            "request": request.to_dict(),
            "request_json": request.to_json(),
            "overview": overview(request),
        },
    }


def prepare(payload):
    require(isinstance(payload, dict), "Preparation must be a JSON object.")
    if set(payload) in ({"request"}, {"request_json"}):
        request = _request_payload(payload, "Studio preparation")
    else:
        fields(payload, {"example"}, "Studio preparation")
        controls = payload["example"]
        fields(controls, {"product", "architecture", "max_length"}, "Example controls")
        require(
            isinstance(controls["architecture"], str)
            and controls["architecture"] in {"auto", "compact", "extended"},
            "Choose auto, compact or extended architecture.",
        )
        require(
            isinstance(controls["product"], str), "Example product must be a string."
        )
        architecture = controls["architecture"]
        constraints = CandidateConstraints(
            allowed_architecture_ids=() if architecture == "auto" else (architecture,),
            max_length=controls["max_length"],
        )
        request = replace(
            _example_product(controls["product"]), constraints=constraints
        )
    return {
        "request": request.to_dict(),
        "request_json": request.to_json(),
        "overview": overview(request),
    }


def _summary(record):
    molecule = record.molecule
    parts = []
    if record.layout is not None:
        by_fragment = {part.fragment.id: part for part in record.components.parts}
        for placement in record.layout.placements:
            part = by_fragment[placement.fragment_id]
            parts.append(
                {
                    "id": part.id,
                    "kind": part.kind,
                    "sequence": part.fragment.sequence[
                        placement.source_range.start : placement.source_range.end
                    ],
                    "start": placement.molecule_range.start,
                    "end": placement.molecule_range.end,
                }
            )
    document = record.to_dict()
    return {
        "status": record.status,
        "sequence": molecule.sequence if molecule else None,
        "length_nt": len(molecule.sequence) if molecule else None,
        "protein": next(
            (
                region.protein_sequence
                for region in molecule.regions
                if region.kind == "cds"
            ),
            None,
        )
        if molecule
        else None,
        "architecture": record.selection.selected.architecture_id
        if record.selection.selected
        else None,
        "parts": parts,
        "alternatives": [
            {
                "architecture_id": item.architecture_id,
                "cds_part_id": item.cds_part_id,
                "length_nt": item.sequence_length,
                "selected": item.id == record.selection.selected_alternative_id,
                "rejections": [
                    {"code": reason.code, "message": reason.message}
                    for reason in item.rejections
                ],
            }
            for item in record.selection.alternatives
        ],
        "checks": [
            {"stage": stage, "outcome": value["outcome"], "detail": value["detail"]}
            for stage, value in document["checks"].items()
        ],
        "unresolved": [
            {"id": item.id, "category": item.category, "description": item.description}
            for item in record.requirements.unresolved
        ],
        "scope": document["completion_scope"],
        "therapeutic_implementation": document["therapeutic_implementation"],
        "human_therapeutic_admission": document["human_therapeutic_admission"],
        "build_fingerprint": record.fingerprint,
    }


def compile_request(payload):
    request = _request_payload(payload, "Studio compilation")
    record = compile_candidate(
        request, expected_request_fingerprint=request.fingerprint
    ).record
    verify_candidate_build(record, expected_request=request)
    return {
        "request": request.to_dict(),
        "request_json": request.to_json(),
        "record": record.to_dict(),
        "record_json": record.to_json(),
        "summary": _summary(record),
    }


def export(payload):
    require(isinstance(payload, Mapping), "Studio export must be an object.")
    bounded_document(payload)
    if set(payload) == {"request_json", "record_json", "format"}:
        request_document = _json_document(payload["request_json"], "Request JSON")
        record_document = _json_document(payload["record_json"], "Build JSON")
    else:
        fields(payload, {"request", "record", "format"}, "Studio export")
        request_document, record_document = payload["request"], payload["record"]
    require(
        isinstance(payload["format"], str)
        and payload["format"] in {"fasta", "build", "request"},
        "Export format must be fasta, build or request.",
    )
    request = _request(request_document)
    record = CandidateBuildRecord.from_dict(record_document)
    verify_candidate_build(record, expected_request=request)
    kind = payload["format"]
    if kind == "fasta":
        content, mime_type = (
            export_candidate_fasta(record, expected_request=request),
            "text/plain",
        )
    else:
        content = (record if kind == "build" else request).to_json() + "\n"
        mime_type = "application/json"
    # Generated names cannot introduce paths or browser download metadata.
    filename = f"candidate-{record.fingerprint[:12]}." + (
        "fasta" if kind == "fasta" else kind + ".json"
    )
    return {"filename": filename, "content": content, "mime_type": mime_type}

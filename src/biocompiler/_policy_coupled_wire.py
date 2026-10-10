"""Lossless bounded transport for coupled evidence, never checking authority.

Every JSON kind has an explicit node tag. Authored objects are data, so neither
``$ref`` nor any other authored field is interpreted as a graph reference.
Ordinary protocol limits apply to the packet; a separate closed bound applies
to its logical expansion. Legacy operation encodings are unaffected.
"""
from __future__ import annotations

import hashlib
import json
from typing import cast

from .core_client import CoreProtocolError, JsonValue, encode_json, validate_json

SCHEMA = "biocompiler.policy_coupled_json_graph.v0.1"
MAX_EXPANDED_NODES = 1_000_000
MAX_EXPANDED_BYTES = 8_323_072
MAX_DEPTH = 128
MAX_PACKET_NODES = 249_968
MAX_PACKET_BYTES = 8_323_072
EXPORT_SCHEMA = "biocompiler.policy_coupled_export_json_graph.v0.1"
# Sum of two original parts, minus the base result's replaced JSON null.
MAX_EXPORT_NODES = 1_999_999
MAX_EXPORT_BYTES = 16_646_140
OPERATIONS = (
    "check-policy-component-material", "replay-policy-component-material", "export-policy-component-material",
    "check-policy-quantitative-assurance", "replay-policy-quantitative-assurance", "export-policy-quantitative-assurance",
    "check-policy-refinement", "replay-policy-refinement",
)
PRODUCER_OPERATIONS = OPERATIONS + ("compile-policy-component-material", "compile-policy-quantitative-assurance")
PROFILE: dict[str, JsonValue] = {
    "schema_version": SCHEMA, "encoding": "lossless_typed_postorder_dag",
    "expanded_identity": "sha256_canonical_json", "expanded_node_count": "values_and_object_keys",
    "max_expanded_bytes": MAX_EXPANDED_BYTES, "max_expanded_nodes": MAX_EXPANDED_NODES,
    "max_packet_bytes": MAX_PACKET_BYTES, "max_packet_nodes": MAX_PACKET_NODES,
    "max_depth": MAX_DEPTH, "max_string_bytes": 4_194_304, "max_number_chars": 4300,
    "claims": "transport_only",
}
EXPORT_PROFILE: dict[str, JsonValue] = {
    **PROFILE, "schema_version": EXPORT_SCHEMA,
    "max_expanded_nodes": MAX_EXPORT_NODES, "max_expanded_bytes": MAX_EXPORT_BYTES,
    "direction": "response", "partition": "base_result_and_artifact",
    "max_part_nodes": MAX_EXPANDED_NODES, "max_part_bytes": MAX_EXPANDED_BYTES,
    "operations": ["export-policy-quantitative-assurance"],
}


def export_profile() -> dict[str, JsonValue]:
    return {**EXPORT_PROFILE, "operations": ["export-policy-quantitative-assurance"]}


def profile(role: str) -> dict[str, JsonValue]:
    _require(role in ("core", "verify"), "unknown executable role")
    return {**PROFILE, "operations": list(PRODUCER_OPERATIONS if role == "core" else OPERATIONS)}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CoreProtocolError("Coupled evidence graph: " + message)


def is_packet(value: JsonValue) -> bool:
    return type(value) is dict and value.get("schema_version") == SCHEMA


def is_export_packet(value: JsonValue) -> bool:
    return type(value) is dict and value.get("schema_version") == EXPORT_SCHEMA


def _export_artifact(value: JsonValue) -> dict[str, JsonValue]:
    _require(type(value) is dict and set(value) == {
        "schema_version", "implementation", "validation_scope", "request_fingerprint", "candidate_fingerprint",
        "invocation_fingerprint", "report_fingerprint", "candidate", "report", "artifact"},
        "paired export requires the complete closed assurance result")
    root = cast(dict[str, JsonValue], value)
    _require(root["schema_version"] == "biocompiler.core.policy_quantitative_assurance.v1"
             and root["implementation"] == "biocompiler.ocaml.policy_quantitative_assurance.v0.1"
             and root["validation_scope"] == "policy-quantitative-assurance-v0.1",
             "paired export assurance identity differs")
    artifact = root["artifact"]
    _require(type(artifact) is dict and set(artifact) == {
        "schema_version", "fasta", "fasta_sha256", "manifest", "manifest_sha256"},
        "paired export requires the complete nonnull artifact")
    artifact = cast(dict[str, JsonValue], artifact)
    _require(artifact["schema_version"] == "biocompiler.policy_quantitative_assurance_export.v0.1"
             and type(artifact["manifest"]) is dict
             and artifact["manifest"].get("schema_version") == "biocompiler.policy_quantitative_assurance_manifest.v0.1",
             "paired export artifact identity differs")
    return artifact


def _export_part_metrics(root: tuple[int, int, int], artifact: tuple[int, int, int]) -> None:
    # Replacing one artifact occurrence by JSON null gives the base response.
    # Repeated references elsewhere still contribute their complete cost.
    _require(artifact[0] <= MAX_EXPANDED_NODES and artifact[1] <= MAX_EXPANDED_BYTES
             and root[0] - artifact[0] + 1 <= MAX_EXPANDED_NODES
             and root[1] - artifact[1] + 4 <= MAX_EXPANDED_BYTES,
             "paired export constituent exceeds the unchanged base bound")


def _scalar_bytes(value: JsonValue) -> bytes:
    # The existing codec independently enforces exact scalar kinds, Unicode,
    # number spelling/length and the original per-string ceiling.
    return encode_json(value, limit=MAX_EXPANDED_BYTES)


def _bounded_metrics(value: JsonValue, *, paired_export: bool = False) -> tuple[int, int, int]:
    """Count expanded keys/values and exact bytes before serialization/allocation."""
    cached: dict[int, tuple[int, int, int]] = {}
    active: set[int] = set()
    artifact = _export_artifact(value) if paired_export else None
    max_nodes = MAX_EXPORT_NODES if paired_export else MAX_EXPANDED_NODES
    max_bytes = MAX_EXPORT_BYTES if paired_export else MAX_EXPANDED_BYTES

    def visit(item: JsonValue, depth: int) -> tuple[int, int, int]:
        _require(depth <= MAX_DEPTH, "expanded depth exceeds its fixed bound")
        kind = type(item)
        if kind not in (dict, list):
            _require(item is None or kind in (bool, int, float, str), "non-JSON scalar")
            raw = _scalar_bytes(item)
            return 1, len(raw), 0
        identity = id(item)
        _require(identity not in active, "cyclic authored JSON")
        previous = cached.get(identity)
        if previous is not None:
            _require(depth + previous[2] <= MAX_DEPTH, "expanded depth exceeds its fixed bound")
            return previous
        active.add(identity)
        nodes, size, height = 1, 2, 0
        if kind is dict:
            obj = cast(dict[str, JsonValue], item)
            _require(all(type(key) is str for key in obj), "non-string object key")
            children = [(child, len(_scalar_bytes(key)) + 1) for key, child in obj.items()]
            nodes += len(obj)
        else:
            children = [(child, 0) for child in cast(list[JsonValue], item)]
        size += max(0, len(children) - 1)
        _require(nodes + len(children) <= max_nodes, "expanded node bound exceeded")
        for child, overhead in children:
            count, length, child_height = visit(child, depth + 1)
            nodes += count
            size += overhead + length
            height = max(height, child_height + 1)
            _require(nodes <= max_nodes and size <= max_bytes,
                     "expanded node or byte bound exceeded")
        active.remove(identity)
        result = nodes, size, height
        cached[identity] = result
        return result

    result = visit(value, 0)
    if artifact is not None:
        _export_part_metrics(result, cached[id(artifact)])
    return result


def canonical_bytes(value: JsonValue) -> bytes:
    """Canonical complete logical bytes under the explicit expansion profile."""
    return _canonical_bytes(value, paired_export=False)


def export_canonical_bytes(value: JsonValue) -> bytes:
    """Complete paired export bytes; neither constituent gains a larger bound."""
    return _canonical_bytes(value, paired_export=True)


def _canonical_bytes(value: JsonValue, *, paired_export: bool) -> bytes:
    _, expected, _ = _bounded_metrics(value, paired_export=paired_export)
    maximum = MAX_EXPORT_BYTES if paired_export else MAX_EXPANDED_BYTES
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    output = bytearray()
    for part in encoder.iterencode(value):
        raw = part.encode("utf-8")
        _require(len(output) + len(raw) <= maximum, "expanded byte bound exceeded")
        output.extend(raw)
    _require(len(output) == expected, "canonical byte accounting differs")
    return bytes(output)


def snapshot(value: JsonValue) -> JsonValue:
    """Return a detached logical snapshot without widening ordinary JSON limits."""
    return cast(JsonValue, json.loads(canonical_bytes(value)))


def _packet_limits(packet: JsonValue) -> None:
    validate_json(packet, byte_limit=MAX_PACKET_BYTES)
    count, _, _ = _bounded_metrics(packet)
    _require(count <= MAX_PACKET_NODES, "physical packet node bound exceeded")


def pack(value: JsonValue) -> dict[str, JsonValue]:
    """Encode a deterministic complete document; hashes never decide equality."""
    return _pack(value, paired_export=False)


def pack_export(value: JsonValue) -> dict[str, JsonValue]:
    """Encode only the explicitly paired assurance export response."""
    return _pack(value, paired_export=True)


def _pack(value: JsonValue, *, paired_export: bool) -> dict[str, JsonValue]:
    expanded = export_canonical_bytes(value) if paired_export else canonical_bytes(value)
    rows: list[JsonValue] = []
    exact: dict[bytes, int] = {}
    containers: dict[int, int] = {}

    def visit(item: JsonValue) -> int:
        kind = type(item)
        identity = id(item)
        if kind in (dict, list) and identity in containers:
            return containers[identity]
        node: dict[str, JsonValue]
        if item is None:
            node = {"kind": "null"}
        elif kind is bool:
            node = {"kind": "boolean", "value": item}
        elif kind is int:
            node = {"kind": "integer", "value": item}
        elif kind is float:
            node = {"kind": "float", "value": item}
        elif kind is str:
            node = {"kind": "string", "value": item}
        elif kind is list:
            node = {"kind": "array", "items": [visit(child) for child in cast(list[JsonValue], item)]}
        else:
            obj = cast(dict[str, JsonValue], item)
            node = {"kind": "object", "fields": [[key, visit(obj[key])] for key in sorted(obj)]}
        key = encode_json(node, limit=MAX_PACKET_BYTES)
        index = exact.get(key)
        if index is None:
            index = len(rows)
            rows.append(node)
            exact[key] = index
        if kind in (dict, list):
            containers[identity] = index
        return index

    root = visit(value)
    packet: dict[str, JsonValue] = {"schema_version": EXPORT_SCHEMA if paired_export else SCHEMA, "expanded_sha256": hashlib.sha256(expanded).hexdigest(),
                                   "root": root, "nodes": rows}
    _packet_limits(packet)
    _require(len(encode_json(packet, limit=MAX_PACKET_BYTES)) <= MAX_PACKET_BYTES, "wire byte bound exceeded")
    return packet


def unpack(packet: JsonValue) -> JsonValue:
    """Check graph closure and expansion cost before materializing its JSON tree."""
    return _unpack(packet, paired_export=False)


def unpack_export(packet: JsonValue) -> JsonValue:
    """Decode the response-only graph with both original constituent bounds."""
    return _unpack(packet, paired_export=True)


def _unpack(packet: JsonValue, *, paired_export: bool) -> JsonValue:
    _packet_limits(packet)
    _require(type(packet) is dict and set(packet) == {"schema_version", "expanded_sha256", "root", "nodes"},
             "packet fields differ")
    obj = cast(dict[str, JsonValue], packet)
    _require(obj["schema_version"] == (EXPORT_SCHEMA if paired_export else SCHEMA), "unknown graph version")
    max_nodes = MAX_EXPORT_NODES if paired_export else MAX_EXPANDED_NODES
    max_bytes = MAX_EXPORT_BYTES if paired_export else MAX_EXPANDED_BYTES
    digest = obj["expanded_sha256"]
    _require(type(digest) is str and len(digest) == 64 and all(char in "0123456789abcdef" for char in digest),
             "invalid expanded digest")
    rows = obj["nodes"]
    _require(type(rows) is list and bool(rows), "nodes must be a nonempty array")
    rows = cast(list[JsonValue], rows)
    _require(type(obj["root"]) is int and obj["root"] == len(rows) - 1, "root must be the final node")
    metrics: list[tuple[int, int, int]] = []
    references: list[list[int]] = []
    exact: set[bytes] = set()
    # Scalar values and graph-shaped containers are retained only after each
    # node's full expanded contribution fits. Repeated edges never hide cost.
    values: list[JsonValue] = []
    scalar_kinds = {"boolean": bool, "integer": int, "float": float, "string": str}
    for index, raw in enumerate(rows):
        _require(type(raw) is dict, "node must be a record")
        row = cast(dict[str, JsonValue], raw)
        kind = row.get("kind")
        _require(type(kind) is str, "node kind must be explicit")
        key = encode_json(row, limit=MAX_PACKET_BYTES)
        _require(key not in exact, "duplicate node")
        exact.add(key)
        refs: list[int] = []
        if kind == "null":
            _require(set(row) == {"kind"}, "null fields differ")
            value: JsonValue = None
            count, size, height = 1, 4, 0
        elif kind in scalar_kinds:
            _require(set(row) == {"kind", "value"} and type(row["value"]) is scalar_kinds[cast(str, kind)],
                     "scalar kind or fields differ")
            value = row["value"]
            count, size, height = 1, len(_scalar_bytes(value)), 0
        else:
            _require(kind in ("array", "object"), "unknown node kind")
            name = "items" if kind == "array" else "fields"
            _require(set(row) == {"kind", name} and type(row[name]) is list, "container fields differ")
            items = cast(list[JsonValue], row[name])
            keys: list[str] = []
            for item in items:
                if kind == "object":
                    _require(type(item) is list and len(item) == 2 and type(item[0]) is str, "invalid object entry")
                    pair = cast(list[JsonValue], item)
                    object_key = cast(str, pair[0])
                    _scalar_bytes(object_key)
                    _require(not keys or keys[-1] < object_key, "object keys must be strictly sorted")
                    keys.append(object_key)
                    item = pair[1]
                _require(type(item) is int and 0 <= item < index, "reference must point strictly backward")
                refs.append(cast(int, item))
            count = 1 + (len(keys) if kind == "object" else 0)
            size = 2 + max(0, len(refs) - 1) + sum(len(_scalar_bytes(key)) + 1 for key in keys)
            height = 0
            for ref in refs:
                child_count, child_size, child_height = metrics[ref]
                count += child_count
                size += child_size
                height = max(height, child_height + 1)
                _require(count <= max_nodes and size <= max_bytes and height <= MAX_DEPTH,
                         "expanded node, byte or depth bound exceeded")
            value = [values[ref] for ref in refs] if kind == "array" else {key: values[ref] for key, ref in zip(keys, refs)}
        metrics.append((count, size, height))
        references.append(refs)
        values.append(value)
    reached: set[int] = set()
    pending = [len(rows) - 1]
    while pending:
        index = pending.pop()
        if index not in reached:
            reached.add(index)
            pending.extend(references[index])
    _require(len(reached) == len(rows), "unreachable node")
    if paired_export:
        _export_artifact(values[-1])
        root_row = cast(dict[str, JsonValue], rows[-1])
        fields = cast(list[list[JsonValue]], root_row["fields"])
        artifact_ref = next(cast(int, pair[1]) for pair in fields if pair[0] == "artifact")
        _export_part_metrics(metrics[-1], metrics[artifact_ref])
    expanded = export_canonical_bytes(values[-1]) if paired_export else canonical_bytes(values[-1])
    _require(hashlib.sha256(expanded).hexdigest() == digest, "expanded digest differs")
    rebuilt = pack_export(values[-1]) if paired_export else pack(values[-1])
    _require(encode_json(rebuilt, limit=MAX_PACKET_BYTES) == encode_json(packet, limit=MAX_PACKET_BYTES),
             "node order is not canonical postorder")
    # A JSON value has independent object occurrences. Do not expose internal
    # graph aliasing through the public descriptive result views.
    return cast(JsonValue, json.loads(expanded))

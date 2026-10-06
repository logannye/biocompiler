"""Detached policy inspection and declaration diffs; never replay or execute."""
from __future__ import annotations

from collections import Counter
from dataclasses import fields
from html import escape
import json

from . import model as m
from .serialization import document_digest, to_data
from .validation import check


def _program(document: m.Record) -> m.PolicyProgram | m.PolicyDraft | None:
    if isinstance(document, m.BuildRequest):
        return document.program
    return document if isinstance(document, (m.PolicyProgram, m.PolicyDraft)) else None


def _graph(document: m.Record) -> dict[str, object]:
    """Inventory a graph already bounded and shape-checked by to_data."""
    program = _program(document)
    nodes: list[dict[str, object]] = [{"key": "document:", "namespace": "document",
        "origin": "declared", "path": "", "kind": type(document).__name__,
        "id": getattr(document, "id", getattr(program, "id", type(document).__name__))}]
    edges: list[dict[str, object]] = []
    node_at: dict[str, str] = {"": "document:"}
    declarations: dict[tuple[str, str], list[str]] = {}
    declaration_kinds: dict[str, set[str]] = {}
    definitions: dict[tuple[str, str, str], list[str]] = {}
    placeholders: dict[tuple[str, ...], str] = {}
    if program is not None:
        base = "/program" if isinstance(document, m.BuildRequest) else ""
        for index, declaration in enumerate(program.declarations):
            path = base + "/declarations/" + str(index)
            key, kind = "declaration:" + path, type(declaration).__name__
            nodes.append({"key": key, "namespace": "declaration", "origin": "declared",
                          "path": path, "id": declaration.id, "kind": kind})
            node_at[path] = key
            declarations.setdefault((declaration.id, kind), []).append(key)
            declaration_kinds.setdefault(declaration.id, set()).add(kind)
        for index, definition in enumerate(program.semantics.definitions):
            path = base + "/semantics/definitions/" + str(index)
            key, digest = "definition:" + path, document_digest(definition)
            nodes.append({"key": key, "namespace": "definition", "origin": "declared",
                          "path": path, "id": definition.id, "kind": "SemanticDefinition",
                          "version": definition.version, "digest": digest})
            node_at[path] = key
            definitions.setdefault((definition.id, definition.version, digest), []).append(key)

    def reference(value: m.Ref | m.DefinitionRef, path: str, source: str) -> None:
        identity: tuple[str, ...]
        if isinstance(value, m.Ref):
            namespace = "declaration"
            identity = (namespace, value.id, value.kind)
            candidates = declarations.get((value.id, value.kind), [])
            missing = "kind_mismatch" if value.id in declaration_kinds else "missing"
        else:
            namespace = "definition"
            identity = (namespace, value.id, value.version, value.digest)
            candidates = definitions.get((value.id, value.version, value.digest), [])
            missing = "missing"
        match = "unique" if len(candidates) == 1 else "ambiguous" if candidates else missing
        if len(candidates) == 1:
            target = candidates[0]
        elif identity in placeholders:
            target = placeholders[identity]
        else:
            target = namespace + "-reference:" + path
            placeholders[identity] = target
            node: dict[str, object] = {"key": target, "namespace": namespace, "origin": "reference",
                "path": path, "id": value.id, "match": match, "candidates": list(candidates)}
            if isinstance(value, m.Ref):
                node.update({"kind": value.kind,
                             "available_kinds": sorted(declaration_kinds.get(value.id, set()))})
            else:
                node.update({"kind": "SemanticDefinition", "version": value.version, "digest": value.digest})
            nodes.append(node)
        edges.append({"source": source, "target": target, "namespace": namespace,
                      "path": path, "reference": to_data(value), "match": match})

    def visit(value: object, path: str, source: str) -> None:
        source = node_at.get(path, source)
        if isinstance(value, (m.Ref, m.DefinitionRef)):
            reference(value, path, source)
        elif isinstance(value, m.Record):
            for item in fields(value):
                if item.name not in ("source_map", "provenance"):
                    visit(getattr(value, item.name), path + "/" + item.name, source)
        elif isinstance(value, tuple):
            for index, child in enumerate(value):
                visit(child, path + "/" + str(index), source)

    visit(document, "", "document:")
    return {"schema_version": "biocompiler.policy_reference_graph.v0.1", "nodes": nodes, "edges": edges,
            "reference_count": len(edges),
            "unmatched_reference_count": sum(edge["match"] != "unique" for edge in edges),
            "scope": "Typed reference occurrences matched to top-level declarations and exact pinned definition bodies; no binding, execution, entailment or realization is inferred.",
            "semantic_status": "unassessed", "target_status": "unassessed"}


def graph(document: m.Record) -> dict[str, object]:
    """Return a detached reference inventory, retaining every occurrence/path.

    Nodes use occurrence paths, so invalid duplicate IDs are never collapsed.
    Ambiguous references share one candidate inventory rather than multiplying
    every candidate for every occurrence. Definition matches require full pins.
    """
    to_data(document)
    return _graph(document)


def inspect(document: m.Record) -> dict[str, object]:
    """Return a detached, JSON-compatible view of current declarations."""
    report = check(document)
    try:
        data = to_data(document)
        digest: str | None = document_digest(document)
    except (ValueError, TypeError, RecursionError, OverflowError):
        data, digest = None, None
    program = _program(document)
    rows: list[dict[str, object]] = []
    counts: Counter[str] = Counter()
    if program is not None and data is not None:
        for declaration in program.declarations:
            kind = type(declaration).__name__
            counts[kind] += 1
            rows.append({"id": declaration.id, "kind": kind,
                         "declaration": to_data(declaration),
                         "sources": [to_data(source) for source in program.source_map
                                     if source.declaration_id == declaration.id]})
    return {"schema_version": "biocompiler.policy_inspection.v0.1",
            "document_type": type(document).__name__, "document_digest": digest,
            "identity_scope": "declaration_content_identity_not_semantic_equivalence",
            "check": report.to_dict(), "declaration_count": len(rows),
            "declaration_counts": dict(sorted(counts.items())), "declarations": rows,
            "graph": _graph(document) if data is not None else None,
            "document": data, "semantic_status": "unassessed", "target_status": "unassessed"}


summary = inspect


def to_html(document: m.Record) -> str:
    """Render inert notebook/file HTML; every authored string is escaped."""
    view = inspect(document)
    report = view["check"]
    assert isinstance(report, dict)
    rows = view["declarations"]
    assert isinstance(rows, list)
    title = str(getattr(document, "id", getattr(_program(document), "id", type(document).__name__)))
    output = ["<section class=\"biocompiler-policy\" aria-label=\"Policy authoring inspection\">",
              "<h2>" + escape(title) + "</h2>",
              "<p>Authoring structure: <strong>" + escape(str(report["status"])) + "</strong>. "
              "Semantic behavior and target suitability are unassessed.</p>",
              "<table><caption>Policy declarations</caption><thead><tr><th scope=\"col\">Identity</th>"
              "<th scope=\"col\">Kind</th></tr></thead><tbody>"]
    for row in rows:
        output.append("<tr><td>" + escape(str(row["id"])) + "</td><td>" + escape(str(row["kind"])) + "</td></tr>")
    output.append("</tbody></table>")
    dependency_graph = view["graph"]
    if isinstance(dependency_graph, dict):
        graph_nodes, graph_edges = dependency_graph["nodes"], dependency_graph["edges"]
        assert isinstance(graph_nodes, list) and isinstance(graph_edges, list)
        by_key = {node["key"]: node for node in graph_nodes}
        output.append("<details><summary>Declaration reference graph</summary><p>Typed reference inventory only; "
                      "no execution, binding or realization is inferred.</p><table><caption>Reference dependencies</caption>"
                      "<thead><tr><th scope=\"col\">Source occurrence</th><th scope=\"col\">Field path</th>"
                      "<th scope=\"col\">Target identity</th><th scope=\"col\">Inventory match</th></tr></thead><tbody>")
        for edge in graph_edges[:500]:
            target = by_key[edge["target"]]
            identity = str(target["namespace"]) + ": " + str(target["id"])
            identity = identity if len(identity) <= 256 else identity[:253] + "..."
            output.append("<tr>" + "".join("<td>" + escape(str(value)) + "</td>" for value in
                (edge["source"], edge["path"], identity, edge["match"])) + "</tr>")
        output.append("</tbody></table>")
        if len(graph_edges) > 500:
            output.append("<p>Showing the first 500 of " + str(len(graph_edges)) +
                          " references. The graph API retains every occurrence.</p>")
        output.append("</details>")
    output.append("<details><summary>Structural diagnostics and deferred obligations</summary><pre>")
    output.append(escape(json.dumps(report, ensure_ascii=False, indent=2)))
    output.append("</pre></details><details><summary>Complete declarations and provenance</summary><pre>")
    output.append(escape(json.dumps(view["document"], ensure_ascii=False, indent=2)))
    output.append("</pre></details></section>")
    return "".join(output)


render_html = to_html


def _changes(before: object, after: object, path: str = "") -> list[dict[str, object]]:
    if type(before) is not type(after):
        return [{"path": path, "before": before, "after": after}]
    if isinstance(before, dict) and isinstance(after, dict):
        result: list[dict[str, object]] = []
        for key in sorted(before.keys() | after.keys()):
            child = path + "/" + str(key).replace("~", "~0").replace("/", "~1")
            if key not in before or key not in after:
                result.append({"path": child, "before_present": key in before, "after_present": key in after,
                               "before": before.get(key), "after": after.get(key)})
            else:
                result.extend(_changes(before[key], after[key], child))
        return result
    # Declaration IDs are handled by diff(); other arrays retain their actual
    # order. No semantic commutativity or graph equivalence is inferred.
    return [] if before == after else [{"path": path, "before": before, "after": after}]


def diff(before: m.Record, after: m.Record) -> dict[str, object]:
    """Compare declaration identities while retaining document/order/provenance edits."""
    left, right = to_data(before), to_data(after)
    first, second = _program(before), _program(after)
    declarations: list[dict[str, object]] = []
    duplicate_ids: list[str] = []
    order_changed = False
    if first is not None and second is not None:
        left_counts = Counter(item.id for item in first.declarations)
        right_counts = Counter(item.id for item in second.declarations)
        duplicate_ids = sorted({key for key, count in left_counts.items() if count > 1}
                               | {key for key, count in right_counts.items() if count > 1})
        # Never silently collapse invalid duplicated identities into a map.
        if not duplicate_ids:
            old = {item.id: item for item in first.declarations}
            new = {item.id: item for item in second.declarations}
            for identity in sorted(old.keys() | new.keys()):
                if identity not in old:
                    declarations.append({"id": identity, "change": "added", "after": to_data(new[identity])})
                elif identity not in new:
                    declarations.append({"id": identity, "change": "removed", "before": to_data(old[identity])})
                else:
                    changes = _changes(to_data(old[identity]), to_data(new[identity]))
                    if changes:
                        declarations.append({"id": identity, "change": "modified",
                                             "before_kind": type(old[identity]).__name__,
                                             "after_kind": type(new[identity]).__name__, "fields": changes})
        order_changed = [item.id for item in first.declarations] != [item.id for item in second.declarations]
    changes = _changes(left, right)
    provenance = [change for change in changes if "/source_map" in str(change["path"]) or "/provenance" in str(change["path"])]
    return {"schema_version": "biocompiler.policy_diff.v0.1",
            "before_digest": document_digest(before), "after_digest": document_digest(after),
            "identical_document": left == right,
            "identical_declaration_content": document_digest(before) == document_digest(after),
            "identity_scope": "declaration_content_identity_not_semantic_equivalence",
            "declaration_changes": declarations, "declaration_order_changed": order_changed,
            "ambiguous_declaration_ids": duplicate_ids, "changes": changes,
            "provenance_changes": provenance, "semantic_status": "unassessed", "target_status": "unassessed"}

"""Authenticate the complete actual GitHub job census for the running final gate.

This pure validator consumes retained REST data; it fetches nothing and grants no
native or release qualification. The caller separately checks receipts against
the selected jobs' actual attempts and retains the unmodified run/pages evidence.
"""
from __future__ import annotations

from copy import deepcopy
import re

SCHEMA = "biocompiler.ci_job_census.v0.1"
FINAL = "Validation complete"
ROUTING = frozenset(("change-scope", "docs-validation"))
MAX_PAGES = 100
MAX_JOBS = 10_000
IDENTITY_FIELDS = ("run_id", "run_attempt", "source_revision", "repository", "event", "workflow_path")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def names(value, label):
    require(type(value) in (set, frozenset) and value and
            all(type(name) is str and name and name.strip() == name for name in value),
            "Invalid expected " + label)
    return set(value)


def validate_census(payload, *, expected, scope, full_job_names, skipped_job_keys):
    """Return selected actual jobs; reject missing, mixed or unsuccessful work.

    ``source_revision`` is REST's head SHA, deliberately distinct from the tested
    synthetic merge revision. Retry selection uses greatest actual attempt for
    each name, including failed/cancelled attempts; it never selects by success.
    The current final job must still be running, so post-run acceptance remains
    the responsibility of the independent completed-run audit.
    """
    require(type(expected) is dict and all(key in expected for key in IDENTITY_FIELDS),
            "Missing expected run identity")
    for field in ("run_id", "run_attempt"):
        require(type(expected[field]) is str and re.fullmatch(r"[1-9][0-9]*", expected[field]) is not None,
                "Invalid expected " + field)
    require(type(expected["source_revision"]) is str and
            re.fullmatch(r"[0-9a-f]{40}", expected["source_revision"]) is not None,
            "Invalid expected source revision")
    require(all(type(expected[key]) is str and expected[key] for key in ("repository", "event", "workflow_path")),
            "Invalid expected repository/event/workflow")
    require(scope in ("full", "docs_only"), "Unknown validation scope")
    full = names(full_job_names, "full job names")
    skipped = names(skipped_job_keys, "skipped job keys")
    require(FINAL in full and not (full & ROUTING) and not (skipped & (ROUTING | {FINAL})),
            "Routing and original job registries overlap")
    if scope == "full":
        success, skip = (full - {FINAL}) | {"change-scope"}, {"docs-validation"}
    else:
        success, skip = set(ROUTING), skipped
    wanted = success | skip | {FINAL}
    require(type(payload) is dict and set(payload) == {"run", "pages"}, "Incomplete run/pages evidence")
    run, pages = payload["run"], payload["pages"]
    require(type(run) is dict and type(run.get("repository")) is dict, "Malformed run metadata")
    current, run_id = int(expected["run_attempt"]), int(expected["run_id"])
    require(type(run.get("id")) is int and run["id"] == run_id and
            type(run.get("run_attempt")) is int and run["run_attempt"] == current and
            run.get("head_sha") == expected["source_revision"] and
            run["repository"].get("full_name") == expected["repository"] and
            run.get("event") == expected["event"] and run.get("path") == expected["workflow_path"],
            "Run metadata differs from current authority")
    require(run.get("status") == "in_progress" and run.get("conclusion") is None,
            "Final gate requires the current running workflow")
    require(type(pages) is list and 0 < len(pages) <= MAX_PAGES, "Missing or oversized job pagination")
    total, rows = None, []
    for page in pages:
        require(type(page) is dict and type(page.get("total_count")) is int and
                0 < page["total_count"] <= MAX_JOBS and type(page.get("jobs")) is list and
                0 < len(page["jobs"]) <= 100, "Malformed or oversized job page")
        total = page["total_count"] if total is None else total
        require(page["total_count"] == total, "Job pagination total changed")
        rows.extend(page["jobs"])
        require(len(rows) <= total, "Job pagination exceeds declared total")
    require(len(rows) == total, "Incomplete job pagination")
    ids, attempts, selected = set(), set(), {}
    for row in rows:
        require(type(row) is dict and type(row.get("id")) is int and row["id"] > 0 and
                type(row.get("name")) is str and row["name"] in wanted,
                "Unknown or malformed actual job")
        require(type(row.get("run_id")) is int and row["run_id"] == run_id and
                type(row.get("run_attempt")) is int and 1 <= row["run_attempt"] <= current and
                row.get("head_sha") == expected["source_revision"], "Job belongs to another run/source/attempt")
        key = (row["name"], row["run_attempt"])
        require(row["id"] not in ids and key not in attempts, "Duplicate actual job ID or name/attempt")
        ids.add(row["id"]); attempts.add(key)
        previous = selected.get(row["name"])
        if previous is None or row["run_attempt"] > previous["run_attempt"]:
            selected[row["name"]] = row
    require(set(selected) == wanted, "Incomplete actual job name census")
    for name, row in selected.items():
        if name == FINAL:
            require(row["run_attempt"] == current and row.get("status") == "in_progress" and
                    row.get("conclusion") is None, "Current final job is absent or not running")
        else:
            conclusion = "success" if name in success else "skipped"
            require(row.get("status") == "completed" and row.get("conclusion") == conclusion,
                    "Latest actual job has wrong outcome: " + name)
    chosen = {row["id"] for row in selected.values()}
    return {"schema_version": SCHEMA, "status": "pass", "scope": scope,
            "identity": {key: expected[key] for key in IDENTITY_FIELDS},
            "job_count": len(rows), "selected_count": len(selected),
            "selected": {name: deepcopy(selected[name]) for name in sorted(selected)},
            "superseded": [deepcopy(row) for row in sorted(rows, key=lambda row: (row["name"], row["run_attempt"]))
                           if row["id"] not in chosen]}

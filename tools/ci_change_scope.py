"""Closed README-only CI routing and inert documentation checks.

Only exact Git objects and authenticated workflow identity choose the route.
Unknown change shapes select full validation; this module never grants package,
native or release qualification and never evaluates documentation contents.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

PLAN_SCHEMA = "biocompiler.ci_change_scope.v0.1"
DOCS_SCHEMA = "biocompiler.docs_validation.v0.1"
REPOSITORY = "logannye/biocompiler"
WORKFLOW = ".github/workflows/ci.yml"
POLICY_FILES = (WORKFLOW, "tools/ci_change_scope.py", "tools/ci_validation.py", "tools/ci_job_census.py")
ALLOWLIST = ("README.md",)
MAX_JSON = 8 * 1024 * 1024
MAX_DIFF = 4 * 1024 * 1024
MAX_ROWS = 10_000
MAX_POLICY = 1024 * 1024
MAX_DOCUMENT = 256 * 1024
ZERO = "0" * 40
SHA = re.compile(r"[0-9a-f]{40}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def byte_pin(raw):
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def document(raw):
    require(len(raw) <= MAX_JSON, "Oversized scope document")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate scope JSON key")
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError("Nonfinite scope JSON: " + value)
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)


def read_json(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_JSON,
            "Missing, redirected or oversized scope document")
    with path.open("rb") as stream:
        return document(stream.read(MAX_JSON + 1))


class GitUnavailable(ValueError):
    """A missing object or bounded unavailable comparison requires full checks."""


def git_bytes(root, *args, maximum=MAX_DIFF):
    """Run fixed read-only Git operations with bounded retained stdout."""
    command = ["git", "--no-pager", "-c", "core.fsmonitor=false", *args]
    environment = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1",
                   "GIT_OPTIONAL_LOCKS": "0"}
    process = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, env=environment)
    chunks, size = [], 0
    try:
        while True:
            chunk = process.stdout.read(min(64 * 1024, maximum + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > maximum:
                raise GitUnavailable("Git output exceeds scope bound")
        if process.wait() != 0:
            raise GitUnavailable("Git object or comparison unavailable")
        return b"".join(chunks)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()


def _sha(value, *, zero=False):
    return type(value) is str and SHA.fullmatch(value) is not None and (zero or value != ZERO)


def _tree(root, revision):
    require(_sha(revision), "Invalid tree revision")
    value = git_bytes(root, "rev-parse", "--verify", revision + "^{tree}", maximum=128).decode().strip()
    require(_sha(value), "Invalid Git tree identity")
    return value


def _event(env, event):
    if event is None:
        event = read_json(env.get("GITHUB_EVENT_PATH", ""))
    require(type(event) is dict, "Invalid workflow event document")
    require(type(event.get("repository")) is dict and event["repository"].get("full_name") == REPOSITORY,
            "Workflow event belongs to another repository")
    return event


def identity(root, *, env=None, event=None):
    env = os.environ if env is None else env
    root = Path(root).resolve()
    event = _event(env, event)
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Scope routing requires GitHub-hosted execution")
    require(env.get("GITHUB_REPOSITORY") == REPOSITORY
            and Path(env.get("GITHUB_WORKSPACE", "")).resolve() == root,
            "Wrong scope repository or workspace")
    revision, ref = env.get("GITHUB_SHA"), env.get("GITHUB_REF", "")
    require(_sha(revision), "Invalid workflow revision")
    require(git_bytes(root, "rev-parse", "HEAD", maximum=128).decode().strip() == revision,
            "Scope checkout differs from workflow revision")
    require(env.get("GITHUB_WORKFLOW_REF") == f"{REPOSITORY}/{WORKFLOW}@{ref}"
            and env.get("GITHUB_WORKFLOW_SHA") == revision, "Wrong scope workflow identity")
    run_id, attempt = env.get("GITHUB_RUN_ID"), env.get("GITHUB_RUN_ATTEMPT")
    require(all(type(value) is str and re.fullmatch(r"[1-9][0-9]{0,19}", value)
                for value in (run_id, attempt)), "Invalid scope run or attempt")
    name = env.get("GITHUB_EVENT_NAME")
    require(name in ("pull_request", "push", "workflow_dispatch"), "Unsupported workflow event")
    base, source = None, revision
    if name == "pull_request":
        pull = event.get("pull_request")
        number = event.get("number")
        require(type(pull) is dict and type(number) is int and number > 0
                and ref == f"refs/pull/{number}/merge", "Wrong pull request merge identity")
        require(type(pull.get("base")) is dict and type(pull.get("head")) is dict
                and type(pull["base"].get("repo")) is dict, "Malformed pull request source/base")
        base, source = pull["base"].get("sha"), pull["head"].get("sha")
        require(_sha(base) and _sha(source)
                and pull.get("base", {}).get("repo", {}).get("full_name") == REPOSITORY,
                "Invalid pull request source/base authority")
        parents = git_bytes(root, "show", "-s", "--format=%P", revision, maximum=256).decode().strip().split()
        require(parents == [base, source], "Tested merge parents differ from event source/base")
    elif name == "push":
        require(ref == "refs/heads/main" and event.get("ref") == ref
                and event.get("after") == revision and event.get("deleted") is False,
                "Wrong main push identity")
        base = event.get("before")
        require(_sha(base, zero=True), "Invalid main before revision")
    else:
        require(re.fullmatch(r"refs/heads/[A-Za-z0-9][A-Za-z0-9._/-]*", ref) is not None,
                "Invalid dispatched branch")
    return {"revision": revision, "tree": _tree(root, revision), "source_revision": source,
            "base_revision": base, "repository": REPOSITORY, "workflow": WORKFLOW,
            "workflow_ref": env["GITHUB_WORKFLOW_REF"], "event": name, "ref": ref,
            "run_id": run_id, "run_attempt": attempt}


def parse_raw_diff(raw):
    """Parse complete --raw -z --no-renames output, without a filename heuristic."""
    require(type(raw) is bytes and len(raw) <= MAX_DIFF, "Oversized Git diff")
    if not raw:
        return []
    require(raw.endswith(b"\0"), "Truncated Git diff")
    pieces = raw[:-1].split(b"\0")
    require(len(pieces) % 2 == 0 and len(pieces) // 2 <= MAX_ROWS, "Unsupported Git diff census")
    rows, seen = [], set()
    pattern = re.compile(rb":([0-7]{6}) ([0-7]{6}) ([0-9a-f]{40}) ([0-9a-f]{40}) ([A-Z])")
    for index in range(0, len(pieces), 2):
        match = pattern.fullmatch(pieces[index])
        require(match is not None, "Unsupported Git diff record")
        path = pieces[index + 1].decode("utf-8")
        require(path and len(pieces[index + 1]) <= 4096 and path not in seen, "Unsafe or repeated Git diff path")
        seen.add(path)
        mode_before, mode_after, old, new, status = (part.decode("ascii") for part in match.groups())
        rows.append({"path": path, "old_mode": mode_before, "new_mode": mode_after,
                     "old_blob": old, "new_blob": new, "status": status})
    return rows


def classify_rows(rows):
    """Return conservative full-scope reasons; an empty list means eligible."""
    if not rows:
        return ["empty_diff"]
    if len(rows) != 1 or rows[0]["path"] not in ALLOWLIST:
        return ["changed_path_outside_readme_allowlist"]
    row = rows[0]
    if (row["status"] != "M" or row["old_mode"] != "100644" or row["new_mode"] != "100644"
            or not _sha(row["old_blob"]) or not _sha(row["new_blob"])
            or row["old_blob"] == row["new_blob"]):
        return ["unsupported_readme_change_shape"]
    return []


def _comparison(root, base, revision, label):
    raw = git_bytes(root, "diff-tree", "--no-commit-id", "-r", "--raw", "--no-renames",
                    "--no-ext-diff", "--no-abbrev", "-z", base, revision, "--")
    rows = parse_raw_diff(raw)
    return {"kind": label, "base_revision": base, "base_tree": _tree(root, base),
            "revision": revision, "tree": _tree(root, revision), "raw_diff": byte_pin(raw), "changes": rows}


def _entry(root, revision, path):
    raw = git_bytes(root, "ls-tree", "-z", "--full-tree", revision, "--", path, maximum=8192)
    if not raw:
        raise GitUnavailable("Scope policy absent from comparison base")
    match = re.fullmatch(rb"([0-7]{6}) blob ([0-9a-f]{40})\t([^\0]+)\0", raw)
    require(match is not None and match[3].decode() == path, "Unsupported scope policy tree entry")
    return {"mode": match[1].decode(), "blob": match[2].decode()}


def _blob(root, blob, maximum):
    require(_sha(blob), "Invalid blob identity")
    size = git_bytes(root, "cat-file", "-s", blob, maximum=32).decode().strip()
    require(size.isdecimal() and int(size) <= maximum, "Git blob exceeds scope bound")
    raw = git_bytes(root, "cat-file", "blob", blob, maximum=maximum)
    require(len(raw) == int(size) and hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == blob,
            "Git blob identity changed")
    return raw


def _working_bytes(root, relative, maximum):
    path = root / relative
    require(path.is_file() and not path.is_symlink()
            and all(not parent.is_symlink() for parent in path.parents if parent != root.parent)
            and path.stat().st_size <= maximum and not path.stat().st_mode & 0o111,
            "Missing, redirected, executable or oversized checked file: " + relative)
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    require(len(raw) <= maximum, "Checked file exceeds bound")
    return raw


def derive_plan(root, *, env=None, event=None):
    root = Path(root).resolve()
    current = identity(root, env=env, event=event)
    reasons, comparisons, policy = [], [], []
    base = current["base_revision"]
    if current["event"] == "workflow_dispatch":
        reasons.append("manual_dispatch_requires_full")
    elif base == ZERO:
        reasons.append("new_history_requires_full")
    else:
        try:
            if current["event"] == "push":
                # No network or implicit shallow fetch. A missing/nonancestor base
                # cannot be mistaken for an empty documentation change.
                git_bytes(root, "merge-base", "--is-ancestor", base, current["revision"], maximum=1)
            comparisons.append(_comparison(root, base, current["revision"], "tested"))
            if current["source_revision"] != current["revision"]:
                comparisons.append(_comparison(root, base, current["source_revision"], "source"))
            for comparison in comparisons:
                reasons.extend(comparison["kind"] + ":" + reason for reason in classify_rows(comparison["changes"]))
            if not reasons:
                for relative in POLICY_FILES:
                    before = _entry(root, base, relative)
                    after = _entry(root, current["revision"], relative)
                    if before != after or before["mode"] != "100644":
                        reasons.append("routing_policy_changed:" + relative)
                        continue
                    raw = _blob(root, after["blob"], MAX_POLICY)
                    require(_working_bytes(root, relative, MAX_POLICY) == raw, "Routing policy working bytes changed")
                    policy.append({"path": relative, **after, **byte_pin(raw)})
        except (GitUnavailable, UnicodeError) as error:
            reasons.append("comparison_unavailable:" + str(error))
        except ValueError as error:
            # Invalid workflow identity was rejected above. Unfamiliar object
            # shapes cannot narrow the otherwise mandatory full validation.
            reasons.append("comparison_unsupported:" + str(error))
    return {"schema_version": PLAN_SCHEMA, "status": "planned", "acceptance": False,
            "scope": "full" if reasons else "docs_only", "identity": current,
            "allowlist": list(ALLOWLIST), "policy": policy, "comparisons": comparisons,
            "reasons": sorted(set(reasons)), "native_validation": "not_run",
            "installed_validation": "not_run", "package_release_qualified": False}


def _recorded_attempt(expected, retained):
    require(type(retained) is dict and type(retained.get("identity")) is dict, "Missing retained scope identity")
    recorded = retained["identity"].get("run_attempt")
    current = expected["identity"]["run_attempt"]
    require(type(recorded) is str and re.fullmatch(r"[1-9][0-9]{0,19}", recorded)
            and int(recorded) <= int(current), "Invalid or future retained scope attempt")
    result = deepcopy(expected)
    result["identity"]["run_attempt"] = recorded
    return result


def validate_plan(root, plan, *, env=None, event=None):
    """Re-derive, preserving a successful same-run earlier producing attempt.

    The outer CI gate separately authenticates that actual producing job and
    rejects a newer failed execution; a receipt alone never proves job success.
    """
    expected = _recorded_attempt(derive_plan(root, env=env, event=event), plan)
    require(encode(plan) == encode(expected), "Scope plan differs from fresh source/event authority")
    return expected


def check_document(raw):
    require(0 < len(raw) <= MAX_DOCUMENT, "README size outside documentation bound")
    text = raw.decode("utf-8")
    require(text.endswith("\n") and not text.startswith("\ufeff"), "README must be UTF-8 text with a final newline")
    require(all(character in "\n\t" or ord(character) >= 32 and ord(character) != 127 for character in text),
            "README contains unsupported control characters")
    for line in text.split("\n"):
        clean = line.rstrip(" \t")
        # Two spaces are Markdown's intentional hard-line-break notation.
        require(line == clean or clean and line == clean + "  ", "README contains trailing whitespace")
    return {"utf8": "pass", "bounded_text": "pass", "final_newline": "pass",
            "control_characters": "pass", "markdown_whitespace": "pass",
            "snippets_executed": False, "network_links_followed": False}


def derive_docs(root, plan, *, env=None, event=None):
    root = Path(root).resolve()
    checked = validate_plan(root, plan, env=env, event=event)
    require(checked["scope"] == "docs_only", "Documentation checks require a freshly eligible docs-only plan")
    current = identity(root, env=env, event=event)
    row = checked["comparisons"][0]["changes"][0]
    raw = _blob(root, row["new_blob"], MAX_DOCUMENT)
    require(_working_bytes(root, "README.md", MAX_DOCUMENT) == raw, "README working bytes differ from tested Git object")
    checks = check_document(raw)
    # Recheck identity, policy and document after inspection before sealing.
    validate_plan(root, plan, env=env, event=event)
    require(identity(root, env=env, event=event) == current
            and _working_bytes(root, "README.md", MAX_DOCUMENT) == raw, "Documentation authority changed during checking")
    return {"schema_version": DOCS_SCHEMA, "status": "pass", "scope": "docs_only", "acceptance": False,
            "identity": current, "plan_sha256": hashlib.sha256(encode(plan)).hexdigest(),
            "documents": [{"path": "README.md", "mode": "100644", "git_blob": row["new_blob"], **byte_pin(raw)}],
            "checks": checks, "native_validation": "not_run", "installed_validation": "not_run",
            "package_release_qualified": False}


def validate_docs(root, plan, receipt, *, env=None, event=None):
    expected = _recorded_attempt(derive_docs(root, plan, env=env, event=event), receipt)
    require(int(expected["identity"]["run_attempt"]) >= int(plan["identity"]["run_attempt"]),
            "Documentation receipt predates its plan")
    require(encode(receipt) == encode(expected), "Documentation receipt differs from fresh checked bytes")
    return expected


def _save(path, value):
    path = Path(path)
    require(not any(parent.is_symlink() for parent in (path, *path.parents)), "Redirected scope output")
    raw = json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n"
    require(len(raw) <= MAX_JSON, "Scope output exceeds bound")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--output", required=True)
    plan_parser.add_argument("--github-output")
    docs_parser = sub.add_parser("docs")
    docs_parser.add_argument("--plan", required=True)
    docs_parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        result = derive_plan(root) if args.command == "plan" else derive_docs(root, read_json(args.plan))
        _save(args.output, result)
        if args.command == "plan" and args.github_output:
            require(args.github_output == os.environ.get("GITHUB_OUTPUT"), "Wrong GitHub output file")
            target = Path(args.github_output)
            require(target.is_file() and not target.is_symlink(), "Unsafe GitHub output file")
            with target.open("a", encoding="utf-8") as stream:
                stream.write("scope=" + result["scope"] + "\n")
        print(json.dumps({"scope": result["scope"], "status": result["status"], "acceptance": False}, sort_keys=True))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

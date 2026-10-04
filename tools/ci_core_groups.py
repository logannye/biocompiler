"""Run the complete original direct-core command groups with bounded overlap."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import time

try:
    from . import ci_validation as ci
    from .ci_native_bundle import manifest_document, require
except ImportError:
    import ci_validation as ci
    from ci_native_bundle import manifest_document, require

PLAN_SHA256 = "27c418288415ea541d684b3ef92657c1882a1bcf05e8ddd8945bd68863352189"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def log_pin(path):
    with path.open("rb") as stream:
        pin = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": path.name, "size": path.stat().st_size, "sha256": pin}


def load_plan(root):
    raw = (root / "tools/ci_core_groups.json").read_bytes()
    require(digest(raw) == PLAN_SHA256, "Direct-core command plan changed")
    plan = manifest_document(raw)
    require(plan["schema"] == "biocompiler.ci_core_groups.v1", "Unknown direct-core plan")
    groups = plan["groups"]
    require([row["id"] for row in groups] == [f"group-{i:02d}" for i in range(67)],
            "Incomplete direct-core group census")
    return groups


def run_group(root, output, group, timeout=None):
    """Keep a former Actions step intact, including cwd, pipes and command order."""
    name = group["id"]
    environment = dict(os.environ)
    for key, source in group["environment"].items():
        require(source == "source" and key == "GITHUB_HEAD_SHA", "Unknown group environment")
        require(bool(environment.get(key)), "Missing direct-core source revision")
    # The workflow supplies GITHUB_HEAD_SHA once; expose it only to the same
    # original groups that previously declared it at step scope.
    if "GITHUB_HEAD_SHA" not in group["environment"]:
        environment.pop("GITHUB_HEAD_SHA", None)
    started = time.monotonic()
    log_path = output / (name + ".log")
    status, code = "error", None
    print("Direct-core started: " + group["name"], flush=True)
    with log_path.open("xb") as log:
        try:
            child = subprocess.Popen(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail",
                                      "-c", group["run"]], cwd=root, env=environment,
                                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                # Production retains each original transport deadline and the
                # hosted job deadline. CoreClient owns detached native sessions;
                # killing only this shell could bypass the client's cleanup.
                # An explicit short timeout is used only by inert unit controls.
                code = child.wait(timeout=timeout)
                status = "pass" if code == 0 else "fail"
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
                status = "timeout"
        except OSError as error:
            log.write((type(error).__name__ + ": " + str(error) + "\n").encode())
    row = {"id": name, "name": group["name"], "run_sha256": digest(group["run"].encode()),
           "status": status, "returncode": code, "duration_seconds": round(time.monotonic() - started, 6),
           "log": log_pin(log_path)}
    print(f"Direct-core completed: {name} ({row['duration_seconds']}s, {status})", flush=True)
    if status != "pass":
        with log_path.open("rb") as log:
            log.seek(max(0, log_path.stat().st_size - 8192))
            tail = log.read(8192)
        print("Direct-core failure tail: " + json.dumps(tail.decode(errors="replace")), flush=True)
    return row


def execute_groups(root, output, groups, workers):
    require(type(workers) is int and workers in (1, 2), "Direct-core workers must be 1 or 2")
    output.mkdir(parents=True, exist_ok=False)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        # map keeps receipt order identical to the original step order while
        # workers independently complete every group, including after failures.
        return list(executor.map(lambda group: run_group(root, output, group), groups))


def run(root, output, workers):
    groups = load_plan(root)
    identity = ci.identity()
    rows = execute_groups(root, output, groups, workers)
    document = {"schema": "biocompiler.ci_core_groups_receipt.v1", **identity,
                "source_revision": os.environ.get("GITHUB_HEAD_SHA", identity["revision"]),
                "system": platform.system(), "machine": platform.machine(),
                "plan_sha256": PLAN_SHA256, "workers": workers, "groups": rows}
    ci.write_json(output / "receipt.json", document)
    check(root, output)
    return document


def check(root, output):
    groups = load_plan(root)
    document = manifest_document((output / "receipt.json").read_bytes())
    identity = ci.identity()
    require(document.get("schema") == "biocompiler.ci_core_groups_receipt.v1"
            and all(document.get(key) == value for key, value in identity.items())
            and document.get("source_revision") == os.environ.get("GITHUB_HEAD_SHA", identity["revision"])
            and (document.get("system"), document.get("machine")) == (platform.system(), platform.machine())
            and document.get("plan_sha256") == PLAN_SHA256
            and type(document.get("workers")) is int and document["workers"] in (1, 2),
            "Stale or invalid direct-core receipt")
    rows = document.get("groups", [])
    require(len(rows) == len(groups), "Incomplete direct-core receipt census")
    require({p.name for p in output.iterdir()} == {"receipt.json", *(g["id"] + ".log" for g in groups)},
            "Unexpected direct-core log census")
    for group, row in zip(groups, rows):
        path = output / (group["id"] + ".log")
        require(path.is_file() and not path.is_symlink(), "Missing direct-core log")
        require(row.get("id") == group["id"] and row.get("name") == group["name"]
                and row.get("run_sha256") == digest(group["run"].encode())
                and row.get("status") == "pass" and type(row.get("returncode")) is int and row["returncode"] == 0
                and row.get("log") == log_pin(path),
                "Failed, reordered or changed direct-core group: " + group["id"])
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("run", "check"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.operation == "run":
        run(args.root.resolve(), args.output, args.workers)
    else:
        check(args.root.resolve(), args.output)


if __name__ == "__main__":
    main()

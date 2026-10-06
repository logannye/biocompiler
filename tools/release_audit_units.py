"""Pure verification of fourteen externally authenticated hosted unit artifacts.

This module neither imports/discovers tests nor imports tools/test_shards.py. It
has no network, subprocess, filesystem-read or publication behavior. The caller
must first authenticate artifact ZIP metadata/digests, complete run-attempt/job
identity and clean source/checkout tree equivalence. This helper checks supplied
byte maps and complete retained records against that explicit external authority.
Successful record verification is not local rediscovery or full CI acceptance.
"""
from collections import Counter
import hashlib
import json
import math
import re

MINORS = ("3.11", "3.14")
SHARDS = 5
SUCCESS = {"success", "skipped", "expected_failure"}
PLAN_SCHEMA = "biocompiler.unittest_shard_plan.v1"
RESULT_SCHEMA = "biocompiler.unittest_shard_result.v1"
ACCOUNTING_SCHEMA = "biocompiler.unittest_shard_accounting.v1"
PROTOCOL_PATH = "tools/test_shards.py"
WEIGHTS_PATH = "tools/test_shard_weights.json"
PROTOCOL_SHA256 = "d8068f4b6ade70a72f783deaf39d416f0b4b3f5ef6423aab687a005ae1a84e2b"
WEIGHTS_SHA256 = "1779a3bda266adaf0d73c542e2fb1646037bc45ac43a3168752771e25b4dc519"
# Exact function source (ast.get_source_segment, UTF-8) copied from the pinned
# protocol, including its six-decimal accumulation/fixture timing behavior.
COPIED_FUNCTIONS = {"summarize_classes": "4c246352cd07204f95b73722f725d63b4aba56fc376efbce16e165deb0c975d0"}
# The rest is a separate inert rederivation. These frozen source anchors explain
# which producer/verification protocol it checks; they are never executed here.
REVIEWED_FUNCTIONS = {
    "digest": "21aec19f4adbe409fd3416440298ad1ce62b1aa3b8f4b9f188a86767bbbef557",
    "make_plan": "2ceb2d7e3eb901258e813eed6239386b76791bbda0feeb3b3f6ba7a54c0823f9",
    "validate_plan": "a6696967f22246bd9b0c015036e9ef56d5133b1456e3040bc68ca14ca722764c",
    "plan_runtime": "e080eb0f9dd8a3993dadcde692dff97a9b62bbe5487978bc035e5bb408d6fb39",
    "TimedResult": "d9ba8ce4f54b33df96d0a45ef9f2b6b58564feb67102af60a735aec6e8d15863",
    "verify_results": "e92b55f77bda148baf08bec0cad1fba84cfdbe18291dc5eb029afa2597d96ae9",
}
AUTHORITY_KEYS = {"head_revision", "revision", "head_tree", "tree", "run_id", "run_attempt"}
PROVENANCE_KEYS = {"head_revision", "revision", "run_id", "run_attempt", "artifact_id", "zip_sha256"}


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(raw):
    require(type(raw) is bytes, "Expected inert bytes")
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def same(left, right):
    return digest(left) == digest(right)


def finite(value, label):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
            "Invalid nonnegative duration: " + label)


def hex_string(value, length):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value) is not None


def relative_path(value):
    return (type(value) is str and bool(value) and not value.startswith("/") and
            "\\" not in value and "\x00" not in value and
            all(part not in {"", ".", ".."} for part in value.split("/")))


def source_map(value):
    require(type(value) is dict and bool(value) and all(relative_path(k) and hex_string(v, 64)
            for k, v in value.items()), "Invalid independent source inventory")


def decode(raw, maximum):
    require(type(raw) is bytes and 0 < len(raw) <= maximum, "JSON bytes exceed bound or are absent")

    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, "Duplicate JSON key: " + key)
            out[key] = value
        return out

    def invalid(value):
        raise AssertionError("Nonfinite JSON value: " + value)

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid)
    # Additional inspection bound; does not alter any execution/discovery domain.
    stack = [(value, 0)]; visited = 0
    while stack:
        item, depth = stack.pop(); visited += 1
        require(depth <= 64 and visited <= 2_000_000, "JSON inspection node/depth bound exceeded")
        if type(item) is dict:
            stack.extend((v, depth + 1) for v in item.values())
        elif type(item) is list:
            stack.extend((v, depth + 1) for v in item)
    return value


def summarize_classes(records, fixtures=None):
    classes = {}
    for record in records:
        row = classes.setdefault(record["class_id"], {"tests": 0, "seconds": 0.0,
                                "test_seconds": 0.0, "fixture_seconds": 0.0, "statuses": {}})
        row["tests"] += 1
        row["seconds"] = round(row["seconds"] + record["seconds"], 6)
        row["test_seconds"] = row["seconds"]
        status = record["status"]
        row["statuses"][status] = row["statuses"].get(status, 0) + 1
    for identity, seconds in (fixtures or {}).items():
        row = classes.setdefault(identity, {"tests": 0, "seconds": 0.0,
                                 "test_seconds": 0.0, "fixture_seconds": 0.0, "statuses": {}})
        row["fixture_seconds"] = seconds
        row["seconds"] = round(row["test_seconds"] + seconds, 6)
    return classes


def expected_assignments(classes, weights):
    """Recompute the frozen balancing algorithm from original weight bytes."""
    require(type(weights) is dict and type(weights.get("classes", {})) is dict, "Malformed original weights")
    hints = weights.get("classes", {})
    default = weights.get("unknown_seconds_per_test", 2.0)
    finite(default, "unknown test weight"); require(default > 0, "Nonpositive unknown test weight")
    costs = []
    for name, members in classes.items():
        seconds = default * len(members)
        if name in hints:
            h = hints[name]
            require(type(h) is dict and type(h.get("tests")) is int and h["tests"] > 0,
                    "Malformed original class weight")
            finite(h.get("seconds"), "class weight")
            seconds = h["seconds"] * min(len(members), h["tests"]) / h["tests"]
            seconds += default * max(0, len(members) - h["tests"])
        costs.append((max(0.001, seconds), name))
    buckets = [{"index": n, "class_ids": [], "test_ids": [], "estimated_seconds": 0.0} for n in range(SHARDS)]
    for cost, name in sorted(costs, key=lambda row: (-row[0], row[1])):
        chosen = min(buckets, key=lambda row: (row["estimated_seconds"], row["index"]))
        chosen["class_ids"].append(name); chosen["estimated_seconds"] += cost
    for row in buckets:
        row["class_ids"].sort()
        row["test_ids"] = [test for name in row["class_ids"] for test in classes[name]]
        row["estimated_seconds"] = round(row["estimated_seconds"], 6)
    return buckets


def expected_artifacts():
    return {**{f"unit-plan-py{m}": "plan.json" for m in MINORS},
            **{f"unit-result-py{m}-shard-{i}": f"shard-{i}.json" for m in MINORS for i in range(SHARDS)},
            **{f"unit-accounting-py{m}": f"accounting-py{m}.json" for m in MINORS}}


def audit_unit_evidence(artifacts, *, authority, expected_source_inventory,
                        shard_protocol_source, weights_source):
    """Return complete retained-record proof; never discover or execute tests.

    artifacts: exactly fourteen names -> {files: {exact member: bytes},
      provenance: {head_revision, revision, run_id, run_attempt, artifact_id,
                   zip_sha256}}. Provenance is supplied ONLY after the caller
      authenticates ZIP bytes/metadata and current full run-attempt/job closure.
    authority: {head_revision:H, revision:C, head_tree:HT, tree:CT,
                run_id:positive int, run_attempt:positive int}; HT must equal CT.
    expected_source_inventory: independently obtained complete clean H/C tree
      path -> SHA256 mapping, including the frozen tools/weights below.
    shard_protocol_source/weights_source: original file bytes from that tree.

    Neither this record format nor an invocation can independently authenticate
    GitHub without the caller's preceding evidence audit. The returned scope
    makes this reliance explicit; no opaque PASS or old PR evidence is accepted.
    """
    require(type(authority) is dict and set(authority) == AUTHORITY_KEYS, "Malformed external unit authority")
    require(all(hex_string(authority[k], 40) for k in ("head_revision", "revision", "head_tree", "tree")),
            "Malformed external source/checkout/tree identity")
    require(authority["head_tree"] == authority["tree"], "Source and tested checkout trees differ")
    require(all(type(authority[k]) is int and authority[k] > 0 for k in ("run_id", "run_attempt")),
            "Malformed external run/attempt identity")
    source_map(expected_source_inventory)
    require(sha(shard_protocol_source) == PROTOCOL_SHA256 == expected_source_inventory.get(PROTOCOL_PATH),
            "Frozen shard protocol source differs")
    require(sha(weights_source) == WEIGHTS_SHA256 == expected_source_inventory.get(WEIGHTS_PATH),
            "Frozen shard weight source differs")
    weights = decode(weights_source, 20_000_000)
    wanted = expected_artifacts()
    require(type(artifacts) is dict and set(artifacts) == set(wanted), "Fourteen unit artifact inventory differs")
    parsed = {}; artifact_rows = []; artifact_ids = []
    for name, member in sorted(wanted.items()):
        supplied = artifacts[name]
        require(type(supplied) is dict and set(supplied) == {"files", "provenance"}, "Malformed unit artifact envelope")
        files, provenance = supplied["files"], supplied["provenance"]
        require(type(files) is dict and set(files) == {member}, "Unit artifact exact member census differs: " + name)
        require(type(provenance) is dict and set(provenance) == PROVENANCE_KEYS,
                "Malformed externally verified artifact provenance")
        require(all(type(provenance[k]) is type(authority[k]) and provenance[k] == authority[k]
                    for k in ("head_revision", "revision", "run_id", "run_attempt")), "Foreign artifact run/checkout authority")
        require(type(provenance["artifact_id"]) is int and provenance["artifact_id"] > 0 and hex_string(provenance["zip_sha256"], 64),
                "Malformed externally verified artifact ID/ZIP digest")
        artifact_ids.append(provenance["artifact_id"])
        raw = files[member]
        parsed[name] = decode(raw, 64 * 1024 * 1024 if name.startswith("unit-plan-") else 20_000_000)
        artifact_rows.append({"artifact": name, "member": member, "bytes": len(raw), "sha256": sha(raw), **provenance})
    require(len(set(artifact_ids)) == 14, "Duplicate unit artifact identity")
    cohort_reports = []; manifests = []
    for minor in MINORS:
        plan = parsed[f"unit-plan-py{minor}"]
        require(type(plan) is dict and set(plan) == {"schema", "environment", "discovery", "shard_count", "weights_digest", "shards", "fingerprint"}, "Malformed complete unit plan")
        require(plan["schema"] == PLAN_SCHEMA and hex_string(plan["fingerprint"], 64) and plan["fingerprint"] == digest({k:v for k,v in plan.items() if k != "fingerprint"}), "Plan schema/fingerprint differs")
        env = plan["environment"]
        require(type(env) is dict and set(env) == {"revision", "python", "implementation"}, "Malformed unit environment")
        require(env["revision"] == authority["revision"] and env["implementation"] == "CPython", "Unit runtime implementation/checkout differs")
        require(type(env["python"]) is str and re.fullmatch(r"3\.(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})", env["python"]) is not None and env["python"].rsplit(".",1)[0] == minor, "Invalid exact CPython cohort version")
        discovery = plan["discovery"]
        require(type(discovery) is dict and set(discovery) == {"start_directory", "pattern", "test_ids", "classes", "source_files", "digest"}, "Malformed complete discovery manifest")
        require(discovery["start_directory"] == "tests" and discovery["pattern"] == "test*.py", "Frozen discovery scope differs")
        require(hex_string(discovery["digest"],64) and discovery["digest"] == digest({k:v for k,v in discovery.items() if k != "digest"}), "Discovery digest differs")
        source_map(discovery["source_files"])
        require(discovery["source_files"] == expected_source_inventory, "Discovery source inventory differs from independently verified source tree")
        ids, classes = discovery["test_ids"], discovery["classes"]
        require(type(ids) is list and bool(ids) and all(type(x) is str and x for x in ids) and ids == sorted(set(ids)), "Discovered IDs not exact sorted unique strings")
        require(type(classes) is dict and bool(classes), "Missing class inventory")
        class_of = {}
        for name, members in classes.items():
            require(type(name) is str and bool(name) and type(members) is list and bool(members) and all(type(x) is str and x for x in members) and members == sorted(set(members)), "Malformed discovered class members")
            for identity in members:
                require(identity not in class_of, "Test belongs to duplicate classes")
                class_of[identity] = name
        require(set(class_of) == set(ids), "Class/test inventory differs")
        require(type(plan["shard_count"]) is int and plan["shard_count"] == SHARDS and type(plan["shards"]) is list and len(plan["shards"]) == SHARDS, "Five-shard plan inventory differs")
        require(plan["weights_digest"] == digest(weights), "Plan uses different original weights")
        assignments = expected_assignments(classes, weights)
        require(same(plan["shards"], assignments), "Full independently rederived five-shard assignment differs")
        selected_all = [identity for shard in assignments for identity in shard["test_ids"]]
        require(Counter(selected_all) == Counter(ids), "Selected ID union differs")
        statuses = Counter(); substatuses = Counter(); executed = []; results = []; shard_rows = []
        for index, assignment in enumerate(assignments):
            receipt = parsed[f"unit-result-py{minor}-shard-{index}"]
            require(type(receipt) is dict and set(receipt) == {"schema", "plan_fingerprint", "environment", "discovery_digest", "shard_index", "status", "selected_ids", "tests", "classes", "class_fixture_seconds", "fixture_errors", "errors", "elapsed_seconds"}, "Malformed complete shard result")
            require(receipt["schema"] == RESULT_SCHEMA and type(receipt["shard_index"]) is int and receipt["shard_index"] == index, "Shard schema/index differs")
            require(same(receipt["environment"],env) and receipt["plan_fingerprint"] == plan["fingerprint"] and receipt["discovery_digest"] == discovery["digest"], "Stale result environment or authority")
            require(receipt["selected_ids"] == assignment["test_ids"], "Result selected IDs differ from plan")
            require(receipt["status"] == "success" and receipt["fixture_errors"] == [] and receipt["errors"] == [], "Unsuccessful/incomplete shard or fixture")
            finite(receipt["elapsed_seconds"], "shard elapsed")
            fixtures = receipt["class_fixture_seconds"]
            require(type(fixtures) is dict and set(fixtures) <= set(assignment["class_ids"]), "Invalid class fixture inventory")
            for value in fixtures.values(): finite(value,"fixture")
            records = receipt["tests"]
            require(type(records) is list, "Missing executed records")
            for record in records:
                require(type(record) is dict and set(record) == {"id", "class_id", "status", "seconds", "subtests"}, "Malformed executed record")
                require(type(record["id"]) is str and record["id"] in class_of and record["class_id"] == class_of[record["id"]], "Executed test class identity differs")
                require(type(record["status"]) is str and record["status"] in SUCCESS, "Unsuccessful executed test")
                finite(record["seconds"],"test")
                require(type(record["subtests"]) is list, "Malformed subtest inventory")
                for subtest in record["subtests"]:
                    require(type(subtest) is dict and set(subtest) == {"id","status"} and type(subtest["id"]) is str and bool(subtest["id"]) and type(subtest["status"]) is str and subtest["status"] in SUCCESS, "Failed/malformed retained subtest")
                    substatuses[subtest["status"]] += 1
                statuses[record["status"]] += 1
            actual_ids = [record["id"] for record in records]
            require(Counter(actual_ids) == Counter(assignment["test_ids"]), "Executed IDs missing/extra/duplicate")
            require(same(receipt["classes"],summarize_classes(records,fixtures)), "Full class summary differs")
            executed.extend(actual_ids); results.append(receipt)
            shard_rows.append({"index":index,"selected":len(assignment["test_ids"]),"executed":len(actual_ids),"result_digest":digest(receipt),"status":receipt["status"]})
        require(Counter(executed) == Counter(ids), "Executed union missing/extra/duplicate")
        expected = {"schema":ACCOUNTING_SCHEMA,"status":"pass","environment":env,
                    "revision":env["revision"],"python_version":env["python"],
                    "total_tests":len(executed),"shard_count":SHARDS,
                    "shard_seconds":{str(r["shard_index"]):r["elapsed_seconds"] for r in results},
                    "plan_fingerprint":plan["fingerprint"],"discovery_digest":discovery["digest"],
                    "expected_shards":SHARDS,"verified_shards":list(range(SHARDS)),
                    "discovered_count":len(ids),"executed_count":len(executed),
                    "executed_ids":sorted(executed),"result_digests":sorted(digest(r) for r in results)}
        account = parsed[f"unit-accounting-py{minor}"]
        require(same(account,expected), "Complete independent accounting reconstruction differs")
        cohort_reports.append({"python":env["python"],"discovered":len(ids),"selected":len(selected_all),"executed":len(executed),
            "classes":len(classes),"source_files":len(discovery["source_files"]),"duplicates":0,"omissions":0,
            "statuses":dict(sorted(statuses.items())),"subtest_statuses":dict(sorted(substatuses.items())),
            "plan_fingerprint":plan["fingerprint"],"discovery_digest":discovery["digest"],"accounting_digest":digest(account),"shards":shard_rows})
        manifests.append(discovery)
    require(same(manifests[0],manifests[1]), "Python cohort discovery manifests differ")
    return {"schema":"pr85.inert_unit_record_audit.v1","status":"pass_for_stated_scope",**authority,
        "scope":"Independent retained-record, source-inventory, assignment and accounting checks; no local rediscovery, execution, complete CI or merge acceptance",
        "external_premises":"Caller authenticated original API/run-attempt/job identities, ZIP digests/member maps and complete clean source H/tested C tree equality before this invocation",
        "shard_protocol_source_sha256":PROTOCOL_SHA256,"weights_source_sha256":WEIGHTS_SHA256,
        "copied_function_source_sha256":COPIED_FUNCTIONS,"reviewed_source_functions":REVIEWED_FUNCTIONS,
        "source_inventory_digest":digest(expected_source_inventory),"unit_artifacts":artifact_rows,
        "allowed_test_statuses":sorted(SUCCESS),"same_discovery_manifest_across_versions":True,"versions":cohort_reports}

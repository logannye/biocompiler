"""Pure-Python integrity controls for the installed native manager gate.

The fabricated frames below test a comparator, never acceptance or native
parity. Actual pinned native execution is required separately in hosted CI.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from tools import check_pipeline_manager_install as campaign


def fake_inspection(original, tokens):
    snapshot = deepcopy(original["state"])
    reachable = set()
    for group in campaign.REGISTRATION_MAPS:
        for entry in snapshot[group].values():
            if "producer" in entry:
                entry["producer"] = tokens[entry["producer"]]
                reachable.add(entry["producer"])
            entry["validators"] = {key: tokens[label] for key, label in entry["validators"].items()}
            reachable.update(entry["validators"].values())
    snapshot["records"] = {key: {"value": value, "bindings": {"record_id": "record/"+str(index)}}
        for index, (key, value) in enumerate(snapshot["records"].items())}
    aliases = {token: label for label, token in tokens.items() if token in reachable}
    providers = [{"provider_id": token, "object": {"handle": token.replace("provider/", "object/")}} for token in sorted(reachable)]
    return {"snapshot": snapshot, "order": deepcopy(original["order"]), "providers": providers}, aliases


def fake_frames(receipt, *, admission=False, comparison=None):
    channel, application = campaign.declarations()
    nonce = str(uuid4())
    rows, sequence, event = [], 0, 0
    input_bytes = output_bytes = nodes = count = commands = pending = 0
    bodies = {}
    put = lambda raw: campaign.artifact(receipt, raw)
    def client(kind, fields):
        nonlocal sequence, input_bytes, nodes, count, commands, pending
        value = {"protocol": channel["protocol"], "profile": channel["profile"], "session_id": nonce,
            "kind": kind, "sequence": sequence, **fields}
        body = campaign.canonical(value)
        raw = campaign.frame(value)
        bodies[sequence] = body
        rows.append({"direction": "client", "index": sequence, "frame": put(raw)})
        sequence += 1
        input_bytes += len(raw)
        nodes += campaign.json_nodes(value)
        count += 1
        if kind == "continue":
            pending -= 1
        else:
            commands += 1
        return sequence - 1
    def server(kind, fields):
        nonlocal event, output_bytes, nodes, count, pending
        if kind == "invoke":
            pending += 1
        value = {"protocol": channel["protocol"], "profile": channel["profile"], "session_id": nonce,
            "kind": kind, "event_id": event, **fields, "usage": {key: 0 for key in channel["usage_fields"]}}
        count += 1
        nodes += campaign.json_nodes(value)
        value["usage"].update(input_bytes=input_bytes, output_bytes=output_bytes, frames=count,
            commands=commands, json_nodes=nodes, pending_invocations=pending, retained_bytes=10_000+count,
            work_charged=1_000_000+count*100, work_remaining=10**12-1_000_000-count*100)
        while True:
            raw = campaign.frame(value)
            expected = output_bytes + len(raw)
            if value["usage"]["output_bytes"] == expected:
                break
            value["usage"]["output_bytes"] = expected
        rows.append({"direction": "server", "index": event, "frame": put(raw)})
        output_bytes += len(raw)
        event += 1
        return value, raw[9:]
    def reply(sequence, value=None, *, closed=False, outcome=None):
        return server("reply", {"sequence": sequence, "request_sha256": campaign.sha(bodies[sequence]),
            "outcome": {"status": "ok", "value": value} if outcome is None else outcome, "closed": closed})
    seq = client("hello", {"declaration": channel, "application": application, "limits": None})
    reply(seq, {"declaration": channel, "application": application, "limits": channel["limits"]})
    def invoke(seq, action, arguments, value):
        invocation, body = server("invoke", {"invocation_id": event, "parent_invocation": None,
            "command_sequence": seq, "command_sha256": campaign.sha(bodies[seq]), "action": action, "arguments": arguments})
        client("continue", {"invocation_id": invocation["invocation_id"], "invocation_sha256": campaign.sha(body),
            "outcome": {"status": "return", "value": value}})
    if comparison is not None:
        tokens = {label: "provider/"+str(index) for index, label in enumerate(comparison["providers"])}
        handles = {label: token.replace("provider/", "object/") for label, token in tokens.items()}
        source = {"arguments": {}, "providers": handles}
        events, inspections, exceptions, live = [None]*len(comparison["events"]), [], {}, []
        ref = lambda label: {"handle": handles[label]}
        parent = lambda: live[-1] if live else None
        def command(operation, args):
            return client("command", {"parent_invocation": parent(), "operation": operation, "arguments": args})
        def inspect(original):
            value, aliases = fake_inspection(original, tokens)
            seq = command("inspect-ordered", {})
            reply(seq, value)
            inspections.append({"sequence": seq, "aliases": aliases})
        setup = comparison["setup"]
        source["arguments"]["object/100000"] = {"kind": "target", "value": setup["target"]}
        seq = command("initialize-empty", {"target": setup["target"], "dependencies": [[key, setup["dependencies"][key]]
            for key in comparison["initial_state"]["order"]["dependencies"] if key in setup["dependencies"]],
            "completion_profiles": setup["profiles"], "manager_limits": None, "target_object": {"handle": "object/100000"}})
        reply(seq, {"kind": "empty", "manager": True, "artifacts": [], "target": {"value": setup["target"], "binding": {}}})
        if comparison["mode"] == "pass":
            source["arguments"]["object/100001"] = {"kind": "input", "value": setup["input"]}
            seq = command("add-input", {"identity": "input", "stage": "typed intent and contracts", "requirements": setup["requirements"],
                "obligations": setup["obligations"], "payload": {"handle": "object/100001"},
                "obligations_object": {"handle": "object/100002"},
                "obligation_objects": [{"handle": "object/"+str(100003+i)} for i in range(len(setup["obligations"]))]})
            reply(seq, {"value": comparison["initial_state"]["state"]["records"]["input"], "bindings": {"record_id": "record/1"}})
        bound = False
        children = {}
        for original in comparison["events"]:
            children.setdefault(original["parent"], []).append(original)
        def manager_event(original):
            nonlocal bound
            identity, recipe, enclosing = original["id"], original["recipe"], parent()
            inspect(original["before"])
            start = len(rows)
            op = recipe["operation"]
            seq = token = None
            if op != "target":
                if op in ("register", "register_component_input"):
                    mapping_ref = "object/"+str(200000+identity)
                    source["arguments"][mapping_ref] = {"kind": "validators", "items": recipe["validators"]}
                    args = {"contract": setup["contracts"][recipe["contract"]], "validators": {"handle": mapping_ref}, "obligation_objects": []}
                    if op == "register":
                        args["producer"] = ref(recipe["producer"])
                        source["arguments"][handles[recipe["producer"]]] = {"kind": "provider", "label": recipe["producer"]}
                    else:
                        args.update(obligations_object={"handle": "object/300000"}, requirements_object={"handle": "object/300001"})
                elif op == "set_dependency":
                    args = {"key": recipe["key"], "identity": recipe["identity"]}
                else:
                    args = {"identity": recipe["identity"]}
                seq = command(op.replace("_", "-"), args)
                if op in ("register", "register_component_input"):
                    invocation, body = server("invoke", {"invocation_id": event, "parent_invocation": parent(),
                        "command_sequence": seq, "command_sha256": campaign.sha(bodies[seq]),
                        "action": "callable", "arguments": {"object": ref("producer")}})
                    client("continue", {"invocation_id": invocation["invocation_id"], "invocation_sha256": campaign.sha(body),
                        "outcome": {"status": "return", "value": True}})
                    if not bound:
                        for label, provider_token in tokens.items():
                            invocation, body = server("invoke", {"invocation_id": event, "parent_invocation": parent(),
                                "command_sequence": seq, "command_sha256": campaign.sha(bodies[seq]),
                                "action": "bind-provider", "arguments": {"provider_id": provider_token, "object": ref(label)}})
                            client("continue", {"invocation_id": invocation["invocation_id"], "invocation_sha256": campaign.sha(body),
                                "outcome": {"status": "return", "value": None}})
                        bound = True
                nested = children.get(identity, [])
                offset = 0
                while offset < len(nested):
                    first = nested[offset]
                    assert first["kind"] == "comparison"
                    group = [first]
                    offset += 1
                    while offset < len(nested) and sorted(nested[offset]["recipe"].values()) == sorted(first["recipe"].values()):
                        group.append(nested[offset]); offset += 1
                    contract = setup["contracts"][recipe["contract"]]
                    history = "provider_history" if op == "register" else "component_input_history"
                    previous = next(value for value in original["before"]["state"][history].values() if value["contract"] == contract)
                    current = dict(recipe["validators"])
                    left, right = next((value,current[key]) for key,value in previous["validators"].items()
                        if sorted((value,current[key])) == sorted(first["recipe"].values()))
                    invocation, body = server("invoke", {"invocation_id": event, "parent_invocation": parent(),
                        "command_sequence": seq, "command_sha256": campaign.sha(bodies[seq]), "action": "compare",
                        "arguments": {"left": ref(left), "right": ref(right), "operator": "eq"}})
                    invocation_id = invocation["invocation_id"]
                    live.append(invocation_id)
                    for comparison_event in group:
                        inspect(comparison_event["before"])
                        begin = len(rows)
                        for child in children.get(comparison_event["id"], []):
                            manager_event(child)
                        events[comparison_event["id"]] = {"event": comparison_event["id"], "kind": "comparison", "sequence": None,
                            "invocation": invocation_id, "before_frames": begin, "after_frames": len(rows), "exception_tokens": []}
                        inspect(comparison_event["after"])
                    final = group[-1]
                    if final["outcome"] == "raised":
                        token = "exception/"+str(len(exceptions))
                        exceptions[token] = {"token": token, "invocation": invocation_id, "events": [identity, final["id"]]}
                        events[final["id"]]["exception_tokens"] = [token]
                        outcome = {"status": "raise", "token": token}
                    else:
                        outcome = {"status": "return", "value": final["result"]}
                    live.pop()
                    client("continue", {"invocation_id": invocation_id, "invocation_sha256": campaign.sha(body), "outcome": outcome})
                if original["outcome"] == "returned":
                    result = original["result"]
                    if op == "get": result = {"value": result, "bindings": {"record_id": "record/1"}}
                    outcome = {"status": "ok", "value": result}
                elif token is not None:
                    outcome = {"status": "raise", "token": token}
                else:
                    outcome = {"status": "rejected", "value": {**original["error"], "attributes": {}, "attributes_tree": ["object", []]}}
                reply(seq, outcome=outcome)
            events[identity] = {"event": identity, "kind": "manager", "sequence": seq, "invocation": enclosing,
                "before_frames": start, "after_frames": len(rows), "exception_tokens": [] if token is None else [token]}
            inspect(original["after"])
        inspect(comparison["initial_state"])
        for original in children[None]:
            manager_event(original)
        inspect(comparison["final_state"])
        seq = client("close", {"parent_invocation": None})
        reply(seq, closed=True)
        return rows, inspections, events, list(exceptions.values()), source
    operations = ["initialize-empty", "register-component-input", "admit-component-input"] if admission else ["initialize-empty", "add-input", "register", "run"]
    for operation in operations:
        seq = client("command", {"parent_invocation": None, "operation": operation,
            "arguments": {field: None for field in application["operations"][operation]["fields"]}})
        if operation == operations[-1]:
            invocation, body = server("invoke", {"invocation_id": event, "parent_invocation": None,
                "command_sequence": seq, "command_sha256": campaign.sha(bodies[seq]),
                "action": "call-provider", "arguments": {"provider_id": "provider/1", "context": {"handle": "object/1"}}})
            client("continue", {"invocation_id": invocation["invocation_id"], "invocation_sha256": campaign.sha(body),
                "outcome": {"status": "return", "value": {"handle": "object/2"}}})
        reply(seq)
    seq = client("close", {"parent_invocation": None})
    reply(seq, closed=True)
    return rows


def fixture(directory, corpus):
    path = directory / campaign.ARTIFACT_DIRECTORY
    path.mkdir(parents=True)
    receipt = {"_artifact_directory": str(path), "artifacts": {}, "checks": [],
        "native_inputs": {"sha256": {"biocompiler-core": "a"*64, "biocompiler-verify": "b"*64}},
        "executables": {"core": "/native/biocompiler-core", "verify": "/native/biocompiler-verify"},
        "completed_checks": 5, "comparison_checks": [], "completed_comparison_checks": 34}
    put = lambda value: campaign.artifact(receipt, campaign.canonical(value))
    channel, application = campaign.declarations()
    stdout = {"protocol": "biocompiler.core.v1", "request_id": None, "operation": None, "status": "error", "result": None,
        "diagnostics": [{"code": "unexpected_arguments", "message": "Expected standard JSON input or the exact inherited artifact descriptor arguments.", "path": None}],
        "core": {**campaign.fixed.CORE, "executable": "verify"}}
    receipt["verify_rejection"] = {"argv": [receipt["executables"]["verify"], campaign.ARGUMENT], "executable_sha256": "b"*64,
        "returncode": 2, "request": campaign.artifact(receipt, campaign.frame(campaign.verify_request(channel, application, str(uuid4())))),
        "stdout": campaign.artifact(receipt, campaign.canonical(stdout)+b"\n"), "stderr": put({"hex": ""})}
    guard = sorted([["biocompiler.core_pipeline_manager", "CorePassManager.__init__"],
        ["biocompiler.core_pipeline_callback_session", "CorePipelineCallbackSession.__init__"],
        ["biocompiler.core_pipeline_callback_session", "CorePipelineCallbackSession.call"],
        ["biocompiler.pipeline_callback_objects", "CallbackObjects.execute"]])
    for case in corpus.cases:
        receipt["checks"].append({"id": case["case"], "original": put(case), "actual": put(case),
            "pid": 123, "returncode": 0, "closed": True, "invalidated": False, "executable_sha256": "a"*64,
            "stderr": put({"hex": ""}), "guard": put(guard),
            "after_close": put({"type": "CoreProtocolError", "message": "Callback session is closed; it cannot reconnect",
                "traffic_unchanged": True, "pid_unchanged": True}),
            "frames": fake_frames(receipt, admission=case["case"].startswith("admission:"))})
    comparison_guard = sorted([*guard, ["biocompiler.core_pipeline_manager", "CorePassManager.inspect_ordered"]])
    receipt["fresh_comparison_original"] = put(corpus.oracles["callbacks"])
    for case in corpus.comparisons:
        frames, inspections, events, exceptions, source = fake_frames(receipt, comparison=case)
        receipt["comparison_checks"].append({"id": case["id"], "original": put(case), "actual": put(case),
            "pid": 124, "returncode": 0, "closed": True, "invalidated": False, "executable_sha256": "a"*64,
            "stderr": put({"hex": ""}), "guard": put(comparison_guard),
            "after_close": put({"type": "CoreProtocolError", "message": "Callback session is closed; it cannot reconnect",
                "traffic_unchanged": True, "pid_unchanged": True}), "frames": frames, "inspections": put(inspections),
            "events": put(events), "host_exceptions": put(exceptions), "source_bindings": put(source)})
    receipt["pending"] = put(corpus.pending)
    return receipt


def validate(receipt, corpus):
    artifacts = campaign.Artifacts(Path(receipt["_artifact_directory"]), receipt["artifacts"])
    result = campaign.validate_existing_checks(receipt, corpus, artifacts)
    campaign.require(artifacts.used == set(artifacts.declared), "Unreferenced complete manager evidence")
    return result


def edit_artifact(receipt, row, field, mutate, *, framed=False):
    old = row[field]
    path = Path(receipt["_artifact_directory"]) / (old + ".bin")
    value = campaign.frame_body(path.read_bytes()) if framed else json.loads(path.read_bytes())
    mutate(value)
    row[field] = campaign.artifact(receipt, campaign.frame(value) if framed else campaign.canonical(value))
    # Old evidence may still be referenced (original=actual); keep it only when
    # some other current receipt field refers to the old identity.
    control = {key: value for key, value in receipt.items() if key not in ("artifacts", "_artifact_directory")}
    if old not in campaign.canonical(control).decode():
        del receipt["artifacts"][old]
        path.unlink()


def reframe(receipt, row, mutate):
    """Repair all byte/hash/resource envelopes after a semantic mutation."""
    directory = Path(receipt["_artifact_directory"])
    values = [campaign.frame_body((directory/(item["frame"]+".bin")).read_bytes()) for item in row["frames"]]
    mutate(values)
    channel, _ = campaign.declarations()
    input_bytes = output_bytes = nodes = commands = pending = 0
    requests, invocations, new_rows = {}, {}, []
    for count, value in enumerate(values, 1):
        incoming = "sequence" in value and value["kind"] in channel["client_fields"]
        if incoming:
            if value["kind"] == "continue":
                value["invocation_sha256"] = campaign.sha(invocations[value["invocation_id"]])
                pending -= 1
            else:
                commands += 1
            raw = campaign.frame(value)
            input_bytes += len(raw)
            nodes += campaign.json_nodes(value)
            requests[value["sequence"]] = raw[9:]
        else:
            if value["kind"] == "invoke":
                value["command_sha256"] = campaign.sha(requests[value["command_sequence"]])
                pending += 1
            else:
                value["request_sha256"] = campaign.sha(requests[value["sequence"]])
            nodes += campaign.json_nodes(value)
            value["usage"].update(input_bytes=input_bytes, output_bytes=output_bytes, frames=count,
                commands=commands, json_nodes=nodes, pending_invocations=pending, retained_bytes=10_000+count,
                work_charged=1_000_000+count*100, work_remaining=10**12-1_000_000-count*100)
            while True:
                raw = campaign.frame(value)
                wanted = output_bytes + len(raw)
                if value["usage"]["output_bytes"] == wanted: break
                value["usage"]["output_bytes"] = wanted
            output_bytes += len(raw)
            if value["kind"] == "invoke": invocations[value["invocation_id"]] = raw[9:]
        new_rows.append({"direction": "client" if incoming else "server",
            "index": value["sequence"] if incoming else value["event_id"], "frame": campaign.artifact(receipt, raw)})
    row["frames"] = new_rows
    control = campaign.canonical({key: value for key, value in receipt.items() if key not in ("artifacts", "_artifact_directory")}).decode()
    for identity in list(receipt["artifacts"]):
        if identity not in control:
            del receipt["artifacts"][identity]
            (directory/(identity+".bin")).unlink()


def case_row(receipt, identity):
    return next(row for row in receipt["comparison_checks"] if row["id"] == identity)


def assert_valid_frames(receipt, row):
    channel, application = campaign.declarations()
    return campaign.validate_frames(row["frames"], campaign.Artifacts(Path(receipt["_artifact_directory"]), receipt["artifacts"]),
        channel, application, provider_calls=False)


def deferred_rejection_fixture(directory, case):
    """Handcrafted protocol controls only; never used by installed acceptance."""
    path = directory / campaign.ARTIFACT_DIRECTORY
    path.mkdir()
    receipt = {"_artifact_directory": str(path), "artifacts": {}, "test_case": {"frames": []}}
    row, frames = receipt["test_case"], []
    channel, application = campaign.declarations()
    nonce, sequence, event_id = str(uuid4()), 0, 0
    evidence = {"inspections": [], "events": [], "accesses": [], "host_exceptions": [], "errors": [],
        "fingerprints": [], "objects": [{}], "arguments": [{}]}
    safe_map = lambda items: {"$mapping": "builtins.dict", "items": list(items)}
    safe_tuple = lambda items: {"$sequence": "tuple", "items": list(items)}
    def ref(number, value=None, label=None):
        handle = "object/" + str(number)
        if value is not None:
            evidence["arguments"][0][handle] = value
        if label is not None:
            evidence["objects"][0][handle] = label
        return {"handle": handle}
    providers = {value["identity"]: {"$object": value["identity"], "class": value["class"]}
        for value in case["objects"] if value["identity"].startswith("provider/")}
    tokens = {name: "provider/" + str(index) for index, name in enumerate(providers)}
    references = {name: ref(index, label=name) for index, name in enumerate(providers)}
    def client(kind, **fields):
        nonlocal sequence
        value = {"protocol": channel["protocol"], "profile": channel["profile"], "session_id": nonce,
            "kind": kind, "sequence": sequence, **fields}
        frames.append(value)
        sequence += 1
        return sequence - 1
    def server(kind, **fields):
        nonlocal event_id
        value = {"protocol": channel["protocol"], "profile": channel["profile"], "session_id": nonce,
            "kind": kind, "event_id": event_id, **fields, "usage": {key: 0 for key in channel["usage_fields"]}}
        frames.append(value)
        event_id += 1
        return value
    def reply(seq, value=None, *, outcome=None, closed=False):
        server("reply", sequence=seq, request_sha256="0"*64,
            outcome={"status": "ok", "value": value} if outcome is None else outcome, closed=closed)
    def command(operation, args):
        return client("command", parent_invocation=None, operation=operation, arguments=args)
    def invoke(seq, action, args, value, ordinal=None):
        identifier = event_id
        server("invoke", invocation_id=identifier, parent_invocation=None, command_sequence=seq,
            command_sha256="0"*64, action=action, arguments=args)
        if ordinal is not None:
            evidence["accesses"].append({"manager": 0, "ordinal": ordinal, "invocation": identifier, "frame_offset": len(frames)})
        client("continue", invocation_id=identifier, invocation_sha256="0"*64, outcome={"status": "return", "value": value})
    def inspect(safe):
        raw, aliases = fake_inspection(campaign.deferred_snapshot_projection(safe), tokens)
        # fake_inspection's physical refs follow native tokens, as above.
        seq = command("inspect-ordered", {})
        reply(seq, raw)
        evidence["inspections"].append({"manager": 0, "sequence": seq, "aliases": aliases, "state": safe})
    seq = client("hello", declaration=channel, application=application, limits=None)
    reply(seq, {"declaration": channel, "application": application, "limits": channel["limits"]})
    initial = dict(case["initial_state"]["items"])
    initial_plain = campaign.deferred_snapshot_projection(case["initial_state"])["state"]
    target = ref(100, initial["_target"])
    seq = command("initialize-empty", {"target": initial_plain["target"], "target_object": target,
        "dependencies": [[key, value] for key, value in initial_plain["dependencies"].items() if key != "target"],
        "completion_profiles": list(initial_plain["profiles"].values()), "manager_limits": None})
    reply(seq, {"kind": "empty", "manager": True, "artifacts": [], "target": {"value": initial_plain["target"], "binding": {}}})
    root_safe = dict(initial["_records"]["items"])["input"]["fields"]
    root = initial_plain["records"]["input"]
    seq = command("add-input", {"identity": "input", "stage": root["stage"], "requirements": root["requirements"],
        "obligations": root["obligations"], "payload": ref(101, root_safe["payload"]),
        "obligations_object": ref(102, root_safe["obligations"]),
        "obligation_objects": [ref(103+i, value) for i, value in enumerate(root_safe["obligations"]["items"])]})
    reply(seq, {"value": root, "bindings": {"record_id": "record/0"}})
    inspect(case["initial_state"])
    for original in case["events"]:
        inspect(original["before"])
        start = len(frames)
        args = campaign.deferred_plain(original["arguments"])
        op = original["operation"]
        if op == "register":
            producer, validator = "provider/producer", "provider/validator"
            evidence["arguments"][0][references[producer]["handle"]] = providers[producer]
            seq = command("register", {"contract": args["contract"], "producer": references[producer],
                "validators": ref(200, safe_map([("identity_check", providers[validator])])), "obligation_objects": []})
            for label, token in tokens.items():
                invoke(seq, "bind-provider", {"provider_id": token, "object": references[label]}, None)
            outcome = {"status": "ok", "value": None}
        elif op == "run":
            seq = command("run", {**args, "configuration": None})
            context = campaign.deferred_plain(case["access_log"][0]["values"])["context"]
            invoke(seq, "hydrate-context", {"context_id": "context/0", "document": context, "bindings": {}}, ref(300))
            proposal = ref(301, label="proposal")
            invoke(seq, "call-provider", {"provider_id": tokens["provider/producer"], "context": ref(300)}, proposal, 0)
            invoke(seq, "attr", {"object": proposal, "name": "search_status"}, ref(302), 1)
            error = original["exception"]
            module, name = error["class"].rsplit(".", 1)
            outcome = {"status": "rejected", "value": {"module": module, "type": name,
                "message": error["message"], "attributes": {}, "attributes_tree": ["object", []]}}
        else:
            assert op == "get-input"
            seq = command("get", args)
            outcome = {"status": "ok", "value": {"value": campaign.deferred_plain(original["result"]), "bindings": {"record_id": "record/0"}}}
        reply(seq, outcome=outcome)
        evidence["events"].append({"manager": 0, "event": original["id"], "operation": op, "sequence": seq,
            "invocation": None, "before_frames": start, "after_frames": len(frames), "exception_tokens": []})
        inspect(original["after"])
    inspect(case["final_state"])
    seq = client("close", parent_invocation=None)
    reply(seq, closed=True)
    row["frames"] = [{"direction": "client" if value["kind"] in channel["client_fields"] else "server",
        "index": value.get("sequence") if value["kind"] in channel["client_fields"] else value["event_id"],
        "frame": campaign.artifact(receipt, campaign.frame(value))} for value in frames]
    reframe(receipt, row, lambda values: None)
    return receipt, row, evidence


def matrix_fixture(root, corpus):
    revision, source_revision, run_id = "a"*40, "b"*40, "manager-test-run"
    native_root, runtime_root = root/"native", root/"realization"
    native_root.mkdir(); runtime_root.mkdir()
    for target, (system, machine) in campaign.r.PLATFORMS.items():
        native_path = native_root/target
        native_path.mkdir()
        pins = {}
        for role in ("core", "verify"):
            path = native_path/("biocompiler-"+role)
            path.write_bytes(("NONEXECUTABLE UNIT FIXTURE " + target + " " + role).encode())
            pins[path.name] = campaign.sha(path.read_bytes())
        (native_path/"binaries.json").write_bytes(campaign.canonical({"revision": revision,
            "system": system, "machine": machine, "sha256": pins})+b"\n")
        native = campaign.r.verify_binaries(native_path, revision, target)
        for python in campaign.r.PYTHONS:
            directory = runtime_root/("realization-"+target+"-py"+python)
            receipt = fixture(directory, corpus)
            receipt.update(schema_version=campaign.SCHEMA, status="success", scope=campaign.SCOPE,
                revision=revision, source_revision=source_revision, run_id=run_id,
                python_version=python+".9", system=system, machine=machine, native_platform=target,
                artifact_directory=campaign.ARTIFACT_DIRECTORY, native_inputs=native,
                python_sources=campaign.python_sources(), campaign_sources=campaign.r.source_pins(campaign.SOURCES),
                package_path="/installed/site-packages/biocompiler/__init__.py", **campaign.metadata(corpus))
            receipt["executables"] = {role: str(native_path/("biocompiler-"+role)) for role in ("core", "verify")}
            receipt["verify_rejection"]["argv"][0] = receipt["executables"]["verify"]
            receipt["verify_rejection"]["executable_sha256"] = pins["biocompiler-verify"]
            for row in [*receipt["checks"], *receipt["comparison_checks"]]:
                row["executable_sha256"] = pins["biocompiler-core"]
            del receipt["_artifact_directory"]
            (directory/campaign.RECEIPT_FILE).write_bytes(campaign.canonical(receipt)+b"\n")
            (directory/"native-inputs.json").write_bytes(campaign.canonical({**native, "run_id": run_id,
                "source_revision": source_revision, "python_version": python+".9"})+b"\n")
    return runtime_root, native_root, dict(revision=revision, source_revision=source_revision, run_id=run_id)


class PipelineManagerCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = campaign.Corpus()

    def test_full_original_and_pending_census(self):
        self.assertEqual(tuple(case["case"] for case in self.corpus.cases), campaign.CASES)
        pending = self.corpus.pending
        self.assertEqual(len(pending["original_contexts"]), 476)
        self.assertEqual(pending["original_event_count"], 91566)
        self.assertEqual(pending["fixed_unreplayed_observations"], 287)
        self.assertEqual(pending["fixed_census"]["excluded_calls"], 10)
        self.assertEqual(len(pending["callback_cases"]), 34)
        self.assertEqual(len(pending["deferred_cases"]), 47)
        self.assertEqual(tuple(case["id"] for case in self.corpus.comparisons), campaign.COMPARISON_CASES)
        self.assertEqual(sum(len(campaign.original_snapshots(case)) for case in self.corpus.comparisons), 280)

    def test_original_comparison_bodies_run_through_observational_swap(self):
        """A Python-only view tests harness glue; it is not native acceptance."""
        from biocompiler.compiler.pipeline import PassManager
        oracle = campaign.load_oracle(installed=False, comparison=True)
        original_capture = oracle.Capture
        class PythonView:
            def __init__(self, **kwargs):
                self.actual = PassManager(**kwargs)
                self.values, self.observations = [], 0
                self.session = SimpleNamespace(last_response=None)
            def __getattr__(self, name):
                return getattr(self.actual, name)
            def label(self, value):
                for index, item in enumerate(self.values):
                    if item is value: return "provider/"+str(index)
                self.values.append(value)
                return "provider/"+str(len(self.values)-1)
            def inspect_ordered(self):
                observed = original_capture.snapshot(SimpleNamespace(manager=self.actual, label=self.label))
                tokens = {"provider/"+str(index): "provider/"+str(index) for index in range(len(self.values))}
                raw, _ = fake_inspection(observed, tokens)
                objects = {item["provider_id"]: self.values[int(item["provider_id"].split("/")[1])] for item in raw["providers"]}
                self.session.last_response = SimpleNamespace(operation="inspect-ordered", sequence=self.observations, result=raw)
                self.observations += 1
                return SimpleNamespace(snapshot=raw["snapshot"], order=raw["order"], providers=objects)
        count = 0
        for expected in self.corpus.comparisons:
            observed = []
            with campaign.native_comparison_capture(oracle, PythonView, lambda *args: observed.append(args)):
                actual = campaign.run_comparison_case(oracle, expected["id"])
            self.assertIs(oracle.Capture, original_capture)
            self.assertEqual(actual, expected)
            self.assertEqual(len(observed), 2*len(expected["events"])+2)
            count += len(observed)
        self.assertEqual(count, 280)
        self.assertEqual(oracle.capture(), self.corpus.oracles["callbacks"])

    def test_deferred_original_bodies_and_replacement_constructors_are_preserved(self):
        """Original Python managers exercise observation glue, never native parity."""
        from biocompiler.compiler.pipeline import PassManager
        oracle = campaign.load_oracle(installed=False, deferred=True)
        comparison = campaign.load_oracle(installed=False, comparison=True)
        original_capture, original_pipeline = oracle.Capture, oracle.pipeline
        managers = []
        class PythonView:
            def __init__(self, **kwargs):
                self.actual = PassManager(**kwargs)
                self.values, self.observations = [], 0
                self.session = SimpleNamespace(last_response=None)
                managers.append(self)
            def __getattr__(self, name):
                return getattr(self.actual, name)
            def label(self, value):
                for index, previous in enumerate(self.values):
                    if previous is value: return "provider/" + str(index)
                self.values.append(value)
                return "provider/" + str(len(self.values) - 1)
            def inspection_state(self):
                observed = comparison.Capture.snapshot(SimpleNamespace(manager=self.actual, label=self.label))
                raw, _ = fake_inspection(observed, {"provider/" + str(index): "provider/" + str(index)
                    for index in range(len(self.values))})
                self.session.last_response = SimpleNamespace(operation="inspect-ordered", sequence=self.observations, result=raw)
                self.observations += 1
                return dict(vars(self.actual))
        snapshots = 0
        for frozen in self.corpus.deferred:
            expected = campaign.run_deferred_case(oracle, frozen["id"])
            observed = []
            with campaign.native_deferred_capture(oracle, PythonView, lambda *args: observed.append(args)):
                actual = campaign.run_deferred_case(oracle, frozen["id"])
            self.assertIs(oracle.Capture, original_capture)
            self.assertIs(oracle.pipeline, original_pipeline)
            # The added observer call frames are verified separately by the
            # traceback receipt checker; do not mistake this original-manager
            # glue control for a native stack-equivalence assertion.
            for value in (actual, expected):
                for event in value["events"]:
                    if event["outcome"] == "raised":
                        event["exception"].pop("original_traceback")
                        event["exception"].pop("required_user_traceback_tail")
            self.assertEqual(actual, expected, frozen["id"])
            wanted = campaign.original_snapshots(expected)
            if frozen["id"].startswith("input:"):
                self.assertEqual(observed[0][3], self.corpus.deferred[0]["initial_state"])
                observed = observed[1:]
            self.assertEqual([item[3] for item in observed], wanted)
            snapshots += len(observed)
            for manager, sequence, aliases, state in observed:
                # All source dataclasses and nested container kinds remain in
                # the full safe state, while its document view is closed.
                projected = campaign.deferred_snapshot_projection(state)
                self.assertEqual(set(projected), {"state", "order"})
        self.assertEqual(len(managers), 53)
        self.assertEqual(snapshots, 408)

    def test_deferred_repaired_frames_still_reject_semantic_substitution(self):
        case = next(item for item in self.corpus.deferred if item["id"] == "proposal:unknown_status")
        def run(receipt, row, evidence):
            details = {}
            channel, application = campaign.declarations()
            campaign.validate_frames(row["frames"], campaign.Artifacts(Path(receipt["_artifact_directory"]), receipt["artifacts"]),
                channel, application, details=details, provider_calls=False)
            campaign.validate_deferred_events(case, evidence, [details], case["initial_state"])
            return details
        with tempfile.TemporaryDirectory() as directory:
            receipt, row, evidence = deferred_rejection_fixture(Path(directory), case)
            run(receipt, row, evidence)
        def altered_message(values):
            next(value for value in values if value["kind"] == "reply" and value["outcome"]["status"] == "rejected")["outcome"]["value"]["message"] += " altered"
        def altered_getter(values):
            next(value for value in values if value["kind"] == "invoke" and value["action"] == "attr")["arguments"]["name"] = "output"
        def altered_context(values):
            next(value for value in values if value["kind"] == "invoke" and value["action"] == "hydrate-context")["arguments"]["document"]["requirements"] = []
        def altered_provider(values):
            next(value for value in values if value["kind"] == "invoke" and value["action"] == "call-provider")["arguments"]["provider_id"] = "provider/1"
        def altered_attributes(values):
            next(value for value in values if value["kind"] == "reply" and value["outcome"]["status"] == "rejected")["outcome"]["value"]["attributes_tree"] = ["array", []]
        for mutate, diagnostic in ((altered_message, "exception descriptor"), (altered_getter, "proposal getter"),
                (altered_context, "context different"), (altered_provider, "another actual callable"),
                (altered_attributes, "attributes are not an ordered object")):
            with self.subTest(diagnostic=diagnostic), tempfile.TemporaryDirectory() as directory:
                receipt, row, evidence = deferred_rejection_fixture(Path(directory), case)
                reframe(receipt, row, mutate)
                assert_valid_frames(receipt, row)
                with self.assertRaisesRegex(AssertionError, diagnostic):
                    run(receipt, row, evidence)

        for mutate, diagnostic in ((lambda value: value["events"][1].update(sequence=value["events"][2]["sequence"]), "command sequence"),
                (lambda value: value["accesses"].reverse(), "accessor was reordered"),
                (lambda value: value["inspections"].pop(), "inspection census"),
                (lambda value: value["objects"][0].update({"object/0": "provider/validator"}), "physical bijection")):
            with self.subTest(diagnostic=diagnostic), tempfile.TemporaryDirectory() as directory:
                receipt, row, evidence = deferred_rejection_fixture(Path(directory), case)
                mutate(evidence)
                assert_valid_frames(receipt, row)
                with self.assertRaisesRegex(AssertionError, diagnostic):
                    run(receipt, row, evidence)

    def test_deferred_native_fingerprint_witness_binds_full_object_chain_and_order(self):
        expected = next(item for item in self.corpus.deferred if item["id"] == "input:valid")
        actual = deepcopy(expected)
        removed = next(item for item in actual["access_log"] if item["access"] == "input.default_fingerprint")
        offset = removed["ordinal"]
        actual["access_log"].remove(removed)
        for ordinal, item in enumerate(actual["access_log"]):
            item["ordinal"] = ordinal
        for event in actual["events"]:
            for key in ("access_start", "access_end"):
                event[key] -= event[key] > offset
        document = dict(removed["values"]["items"])["document"]
        def tree(safe):
            if type(safe) is dict and "$mapping" in safe:
                return ["object", [[key, tree(value)] for key, value in safe["items"]]]
            if type(safe) is dict and "$sequence" in safe:
                return ["array", [tree(value) for value in safe["items"]]]
            return ["scalar", safe]
        ref = lambda number: {"handle": "object/" + str(number)}
        actions = [("document", {"object": ref(1)}, ref(2)),
            ("freeze-json", {"object": ref(2)}, ref(3)),
            ("ordered-json", {"object": ref(3)}, tree(document)),
            ("literal", {"kind": "json", "value": campaign.sha(campaign.canonical(campaign.deferred_plain(document)))}, ref(4)),
            ("attr-default", {"object": ref(1), "name": "fingerprint", "default": ref(4)}, ref(5))]
        invocations = {index: {"action": name, "arguments": args, "outcome": {"status": "return", "value": result},
            "command_sequence": 1, "start_frame": 2+index*2, "end_frame": 3+index*2}
            for index, (name, args, result) in enumerate(actions)}
        details = [{"invocations": {}}, {"invocations": invocations,
            "commands": [{"sequence": 1, "operation": "add-input", "arguments": {"payload": ref(1)}}]}]
        evidence = {"fingerprints": [{"manager": 1, "invocation": 4, "access_offset": offset, "parent": 0}],
            "events": [{"manager": 1, "event": 0, "sequence": 1, "before_frames": 1, "after_frames": 30},
                {"manager": 1, "event": 1, "sequence": None, "before_frames": 32, "after_frames": 32}],
            "accesses": [{"manager": 1, "ordinal": item["ordinal"], "frame_offset": 3 if item["ordinal"] < offset else 11}
                for item in actual["access_log"]]}
        self.assertEqual(campaign.deferred_fingerprint_projection(actual, evidence, details), expected)
        for mutate, diagnostic in ((lambda value: value[1]["invocations"][2]["arguments"].update(object=ref(999)), "actual document and frozen"),
                (lambda value: value[1]["invocations"][1]["arguments"].update(object=ref(999)), "actual document and frozen"),
                (lambda value: value[1]["invocations"][0]["arguments"].update(object=ref(999)), "actual document and frozen"),
                (lambda value: value[1]["invocations"][3]["arguments"].update(value="0"*64), "fingerprint value")):
            changed = deepcopy(details)
            mutate(changed)
            with self.assertRaisesRegex(AssertionError, diagnostic):
                campaign.deferred_fingerprint_projection(actual, evidence, changed)
        changed = deepcopy(evidence)
        changed["fingerprints"][0]["access_offset"] += 1
        with self.assertRaisesRegex(AssertionError, "moved relative"):
            campaign.deferred_fingerprint_projection(actual, changed, details)

    def test_deferred_trace_correspondence_retains_exact_user_frames(self):
        oracle = campaign.load_oracle(installed=False, deferred=True)
        expected = oracle.proposal_case("unknown_status")
        with tempfile.TemporaryDirectory() as directory:
            receipt, row, evidence = deferred_rejection_fixture(Path(directory), expected)
            details = {}
            channel, application = campaign.declarations()
            campaign.validate_frames(row["frames"], campaign.Artifacts(Path(receipt["_artifact_directory"]), receipt["artifacts"]),
                channel, application, details=details, provider_calls=False)
            actual = deepcopy(expected)
            error = actual["events"][1]["exception"]
            original_frames = [value for value in error["original_traceback"] if value["file"] != "src/biocompiler/compiler/pipeline.py"]
            source = "src/biocompiler/core_pipeline_manager.py"
            lines = (campaign.ROOT/source).read_text().splitlines()
            bridge_line = next(index for index, value in enumerate(lines, 1) if value.strip() == "raise error")
            actual_frames = [*original_frames, {"file": source, "function": "_call", "line": bridge_line}]
            error["original_traceback"] = actual_frames
            nodes = []
            for index, frame in enumerate(actual_frames):
                sites = campaign.source_code_sites(frame["file"])
                candidates = [name for name, values in sites.items() if name.split(".")[-1] == frame["function"] and frame["line"] in values]
                self.assertEqual(len(candidates), 1)
                nodes.append({"node": "traceback/"+str(index), "source": frame["file"], "function": frame["function"],
                    "qualname": candidates[0], "line": frame["line"], "source_sha256": campaign.sha((campaign.ROOT/frame["file"]).read_bytes())})
            evidence["errors"] = [{"manager": 0, "event": 1, "identity": error["identity"], "traceback": nodes,
                "required_index": len(nodes)}]
            compared, correspondence = campaign.deferred_trace_projection(actual, expected, evidence, [details])
            self.assertEqual(compared, expected)
            self.assertEqual(len(correspondence), 2)
            changed, proof = deepcopy(actual), deepcopy(evidence)
            changed["events"][1]["exception"]["original_traceback"].pop(0)
            proof["errors"][0]["traceback"].pop(0)
            proof["errors"][0]["required_index"] -= 1
            with self.assertRaisesRegex(AssertionError, "user/leaf traceback frames"):
                campaign.deferred_trace_projection(changed, expected, proof, [details])
            changed, proof = deepcopy(actual), deepcopy(evidence)
            changed["events"][1]["exception"]["original_traceback"][-1]["line"] = 1
            proof["errors"][0]["traceback"][-1]["line"] = 1
            with self.assertRaisesRegex(AssertionError, "executable site"):
                campaign.deferred_trace_projection(changed, expected, proof, [details])

    def test_deferred_observer_retains_live_tail_nodes_and_exception_relationships(self):
        from biocompiler.pipeline_callback_objects import CallbackObjects
        oracle = campaign.load_oracle(installed=False, deferred=True)
        capture = oracle.Capture("callback:exception_reused")
        calls = []
        class Unobservable(ValueError):
            def __str__(self):
                calls.append("str")
                raise AssertionError("Extra exception hook executed")
        original = capture.marker(kind=Unobservable)
        def callback():
            capture.raise_marker(chained=True, kind=Unobservable)
        capture.provider("producer", callback)
        broker = CallbackObjects()
        session = SimpleNamespace(traffic=(SimpleNamespace(direction="server", value={"kind": "invoke", "invocation_id": 7, "command_sequence": 11}),),
            last_response=SimpleNamespace(status="raise", sequence=11))
        manager = SimpleNamespace(_objects=broker, session=session)
        witness = campaign.DeferredWitness(oracle)
        witness.managers.append(manager)
        witness.captures.append(capture)
        previous = sys.getprofile()
        with campaign.guarded_execution(set(), witness.observe):
            completion = broker.execute("call", {"callable": broker.retain(callback), "args": [], "kwargs": {}})
            token = completion.value["exception_token"]
            retained_tail = witness.exceptions[0, token]["traceback"]
            try:
                broker.rethrow(token)
            except Unobservable as error:
                self.assertIs(error, original)
                descriptor = capture.exception(error)
                witness.error(manager, 0, error, error.__traceback__, descriptor)
                witness.event(manager, {"event": 0, "operation": "run", "sequence": 11, "invocation": None,
                    "before_frames": 0, "after_frames": 1}, error, {})
        self.assertIs(sys.getprofile(), previous)
        evidence = witness.evidence()
        host, observed = evidence["host_exceptions"][0], evidence["errors"][0]
        self.assertIs(witness.exceptions[0, token]["traceback"], retained_tail)
        self.assertEqual([item["node"] for item in observed["traceback"]][-len(host["traceback"]):],
            [item["node"] for item in host["traceback"]])
        self.assertEqual(host["rethrows"], [11])
        self.assertEqual(host["identity"], "exception/marker")
        self.assertEqual((host["cause"], host["context"]), ("exception/cause", "exception/context"))
        self.assertTrue(host["suppress_context"])
        self.assertNotIn(token, broker._exceptions)
        self.assertEqual(calls, [])
        broker.close()

    def test_profiler_retains_actual_consumed_exception_without_observation_hooks(self):
        from biocompiler.pipeline_callback_objects import CallbackObjects
        calls = []
        class Unobservable(ValueError):
            def __str__(self):
                calls.append("str")
                raise AssertionError("Observer called user exception formatting")
        broker = CallbackObjects()
        session = SimpleNamespace(traffic=(SimpleNamespace(direction="server", value={"kind": "invoke", "invocation_id": 7}),))
        managers = [SimpleNamespace(_objects=broker, session=session)]
        retained, seen = {}, set()
        observer = lambda frame, event, result: campaign.observe_host_exception(frame, event, result, managers, retained)
        original = Unobservable("original")
        previous = sys.getprofile()
        with campaign.guarded_execution(seen, observer):
            with campaign.guarded_execution(seen, observer):
                result = broker._capture(original)
            token = campaign.r.decode(result.document)["exception_token"]
            try:
                broker.rethrow(token)
            except Unobservable as error:
                self.assertIs(error, original)
        self.assertIs(sys.getprofile(), previous)
        self.assertIs(retained[token]["object"], original)
        self.assertEqual(retained[token]["invocation"], 7)
        self.assertNotIn(token, broker._exceptions)
        self.assertEqual(calls, [])
        broker.close()

    def test_nested_guard_chains_external_profiler_once_and_checks_raised_exits(self):
        import builtins
        observed = []
        def marker():
            return None
        def external(frame, event, result):
            if event == "call" and frame.f_code is marker.__code__:
                observed.append("marker")
        previous, importer = sys.getprofile(), builtins.__import__
        sys.setprofile(external)
        try:
            with self.assertRaisesRegex(ValueError, "original"):
                with campaign.guarded_execution(set()):
                    with campaign.guarded_execution(set()):
                        marker()
                        raise ValueError("original")
            self.assertEqual(observed, ["marker"])
            self.assertIs(sys.getprofile(), external)
            self.assertIs(builtins.__import__, importer)
            with self.assertRaisesRegex(AssertionError, "guard was disabled"):
                with campaign.guarded_execution(set()):
                    sys.setprofile(None)
                    raise ValueError("must not hide disabled guard")
            self.assertIs(sys.getprofile(), external)
            self.assertIs(builtins.__import__, importer)
        finally:
            sys.setprofile(previous)

    def test_order_and_physical_provider_inventory_mutations_fail(self):
        case = next(value for value in self.corpus.comparisons if value["id"] == "pass:comparison_order")
        tokens = {label: "provider/"+str(index) for index,label in enumerate(case["providers"])}
        original = case["final_state"]
        raw, aliases = fake_inspection(original, tokens)
        self.assertEqual(campaign.comparison_snapshot(raw, aliases), original)
        changed = deepcopy(raw)
        changed["order"]["validators"]["passes"]["lower"].reverse()
        self.assertNotEqual(campaign.comparison_snapshot(changed, aliases), original)
        for mutate in (lambda value: value["providers"].pop(),
                lambda value: value["providers"][1].update(object=value["providers"][0]["object"]),
                lambda value: value["order"]["passes"].append("invented"),
                lambda value: value["order"]["combined_provider_history"].clear()):
            changed = deepcopy(raw); mutate(changed)
            with self.assertRaises(AssertionError): campaign.comparison_snapshot(changed, aliases)
        changed_aliases = dict(aliases)
        changed_aliases[next(iter(changed_aliases))] = next(iter(list(changed_aliases.values())[1:]))
        with self.assertRaisesRegex(AssertionError, "physical bijection"):
            campaign.comparison_snapshot(raw, changed_aliases)
        previous = {}
        campaign.comparison_snapshot(raw, aliases, previous=previous)
        changed = deepcopy(raw)
        old = changed["providers"][0]["provider_id"]
        fresh = "provider/99999"
        changed["providers"][0]["provider_id"] = fresh
        for group in campaign.REGISTRATION_MAPS:
            for entry in changed["snapshot"][group].values():
                if entry.get("producer") == old: entry["producer"] = fresh
                entry["validators"] = {key: fresh if value == old else value for key,value in entry["validators"].items()}
        renamed = {fresh if key == old else key: value for key,value in aliases.items()}
        with self.assertRaisesRegex(AssertionError, "another native token"):
            campaign.comparison_snapshot(changed, renamed, previous=previous)

    def test_complete_comparator_fixture_and_nonce_projection(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first, second = fixture(Path(a), self.corpus), fixture(Path(b), self.corpus)
            self.assertEqual(validate(first, self.corpus), validate(second, self.corpus))
            self.assertEqual(len(validate(first, self.corpus)), 39)

    def test_complete_case_mutations_are_rejected_even_with_new_content_hash(self):
        mutations = [lambda value: value["events"][0].update(target_is_supplied=False),
            lambda value: value["records"].pop(), lambda value: value["events"].pop(),
            lambda value: value.update(retained_objects=value["retained_objects"]+1)]
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                receipt = fixture(Path(directory), self.corpus)
                edit_artifact(receipt, receipt["checks"][0], "actual", mutation)
                with self.assertRaises(AssertionError):
                    validate(receipt, self.corpus)

    def test_rehashed_native_reply_and_comparison_semantics_cannot_detach(self):
        def rejected_message(values):
            reply = next(value for value in values if value["kind"] == "reply" and value["outcome"]["status"] == "rejected")
            reply["outcome"]["value"]["message"] += " changed"
        def rejection_class(values):
            reply = next(value for value in values if value["kind"] == "reply" and value["outcome"]["status"] == "rejected")
            reply["outcome"]["value"]["type"] = "ValueError"
        def changed_get(values):
            seq = next(value["sequence"] for value in values if value["kind"] == "command" and value["operation"] == "get")
            reply = next(value for value in values if value["kind"] == "reply" and value["sequence"] == seq)
            reply["outcome"]["value"]["value"]["payload"]["nodes"][0]["value"] = 999
        def wrong_action(values):
            invoke = next(value for value in values if value["kind"] == "invoke" and value["action"] == "compare")
            invoke["action"] = "contains"
            invoke["arguments"] = {"container": invoke["arguments"]["left"], "item": invoke["arguments"]["right"]}
        def wrong_contract(values):
            command = next(value for value in values if value["kind"] == "command" and value["operation"] == "register")
            command["arguments"]["contract"]["version"] = "wrong"
        def wrong_compare_value(values):
            invoke = next(value for value in values if value["kind"] == "invoke" and value["action"] == "compare")
            result = next(value for value in values if value["kind"] == "continue" and value["invocation_id"] == invoke["invocation_id"])
            result["outcome"]["value"] = not result["outcome"]["value"]
        controls = [("pass:unequal", rejected_message, "rejection descriptor"),
            ("pass:unequal", rejection_class, "rejection descriptor"),
            ("pass:reentrant_reads", changed_get, "returned value"),
            ("pass:equal", wrong_action, "native equality invocation"),
            ("pass:equal", wrong_contract, "another contract"),
            ("pass:equal", wrong_compare_value, "comparison continuation differs")]
        for case, mutation, diagnostic in controls:
            with self.subTest(case=case, diagnostic=diagnostic), tempfile.TemporaryDirectory() as directory:
                receipt = fixture(Path(directory), self.corpus)
                row = case_row(receipt, case)
                reframe(receipt, row, mutation)
                assert_valid_frames(receipt, row)
                with self.assertRaisesRegex(AssertionError, diagnostic): validate(receipt, self.corpus)

    def test_rehashed_exception_translation_and_token_substitution_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = fixture(Path(directory), self.corpus)
            row = case_row(receipt, "pass:raises")
            expected = next(case for case in self.corpus.comparisons if case["id"] == row["id"])
            manager = next(event for event in expected["events"] if event["kind"] == "manager" and event["outcome"] == "raised")
            def translated(values):
                reply = next(value for value in values if value["kind"] == "reply" and value["outcome"]["status"] == "raise")
                reply["outcome"] = {"status": "rejected", "value": {**manager["error"], "attributes": {}, "attributes_tree": ["object", []]}}
            reframe(receipt, row, translated)
            edit_artifact(receipt, row, "events", lambda value: value[manager["id"]].update(exception_tokens=[]))
            edit_artifact(receipt, row, "host_exceptions", lambda value: value[0]["events"].remove(manager["id"]))
            assert_valid_frames(receipt, row)
            with self.assertRaisesRegex(AssertionError, "translated the original host exception"):
                validate(receipt, self.corpus)
        with tempfile.TemporaryDirectory() as directory:
            receipt = fixture(Path(directory), self.corpus)
            row = case_row(receipt, "pass:raises")
            def substituted(values):
                for value in values:
                    if value["kind"] in ("reply", "continue") and value["outcome"]["status"] == "raise":
                        value["outcome"]["token"] = "exception/99999"
            reframe(receipt, row, substituted)
            assert_valid_frames(receipt, row)
            with self.assertRaisesRegex(AssertionError, "detached from actual command token"):
                validate(receipt, self.corpus)

    def test_swapped_equal_actions_and_extra_commands_have_no_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = fixture(Path(directory), self.corpus)
            row = case_row(receipt, "pass:identity_shortcut")
            def swap(values):
                keys = ("sequence", "before_frames", "after_frames")
                first, second = [{key: value[key] for key in keys} for value in values]
                values[0].update(second); values[1].update(first)
            edit_artifact(receipt, row, "events", swap)
            assert_valid_frames(receipt, row)
            with self.assertRaisesRegex(AssertionError, "its own before/after"):
                validate(receipt, self.corpus)
        with tempfile.TemporaryDirectory() as directory:
            receipt = fixture(Path(directory), self.corpus)
            row = case_row(receipt, "pass:identity_shortcut")
            def extra(values):
                close, reply = values[-2:]
                command = {**close, "kind": "command", "operation": "target", "arguments": {}}
                response = {**deepcopy(reply), "closed": False, "outcome": {"status": "ok", "value": None}}
                close["sequence"] += 1
                reply["sequence"] += 1
                reply["event_id"] += 1
                values[-2:] = [command, response, close, reply]
            reframe(receipt, row, extra)
            assert_valid_frames(receipt, row)
            with self.assertRaisesRegex(AssertionError, "Unclaimed or missing actual comparison command"):
                validate(receipt, self.corpus)

    def test_comparison_case_event_and_inspection_census_cannot_shrink(self):
        for mutate, diagnostic in ((lambda receipt: receipt["comparison_checks"].pop(), "34-case"),
                (lambda receipt: receipt.update(completed_comparison_checks=33), "34-case"),
                (lambda receipt: receipt["comparison_checks"].__setitem__(1, receipt["comparison_checks"][0]), "reordered original comparison")):
            with tempfile.TemporaryDirectory() as directory:
                receipt = fixture(Path(directory), self.corpus); mutate(receipt)
                with self.assertRaisesRegex(AssertionError, diagnostic): validate(receipt, self.corpus)
        with tempfile.TemporaryDirectory() as directory:
            receipt = fixture(Path(directory), self.corpus)
            row = case_row(receipt, "pass:equal")
            edit_artifact(receipt, row, "inspections", lambda value: value.pop())
            with self.assertRaisesRegex(AssertionError, "inspection census"):
                validate(receipt, self.corpus)

    def test_session_binding_usage_and_lifo_mutations_are_rejected(self):
        changes = [("invoke", lambda value: value.update(command_sha256="0"*64)),
            ("invoke", lambda value: value.update(invocation_id=999)),
            ("invoke", lambda value: value.update(parent_invocation=0)),
            ("continue", lambda value: value.update(invocation_sha256="0"*64)),
            ("continue", lambda value: value.update(sequence=0)),
            ("reply", lambda value: value.update(request_sha256="0"*64)),
            ("reply", lambda value: value["usage"].update(json_nodes=value["usage"]["json_nodes"]+1)),
            ("reply", lambda value: value["usage"].update(frames=value["usage"]["frames"]-1)),
            ("reply", lambda value: value.update(event_id=100)),
            ("reply", lambda value: value.update(extra=None))]
        for kind, mutation in changes:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                receipt = fixture(Path(directory), self.corpus)
                row = next(row for row in receipt["checks"][0]["frames"] if campaign.frame_body(
                    (Path(receipt["_artifact_directory"]) / (row["frame"]+".bin")).read_bytes())["kind"] == kind)
                edit_artifact(receipt, row, "frame", mutation, framed=True)
                with self.assertRaises(AssertionError):
                    validate(receipt, self.corpus)

    def test_missing_duplicate_cases_and_pending_claim_changes_fail(self):
        for mutation in (lambda receipt: receipt["checks"].pop(),
                lambda receipt: receipt["checks"].__setitem__(1, receipt["checks"][0]),
                lambda receipt: receipt.update(completed_checks=4),
                lambda receipt: receipt["checks"][0].update(invalidated=True),
                lambda receipt: receipt["checks"][0].update(executable_sha256="c"*64)):
            with tempfile.TemporaryDirectory() as directory:
                receipt = fixture(Path(directory), self.corpus)
                mutation(receipt)
                with self.assertRaises(AssertionError):
                    validate(receipt, self.corpus)
        with tempfile.TemporaryDirectory() as directory:
            receipt = fixture(Path(directory), self.corpus)
            edit_artifact(receipt, receipt, "pending", lambda value: value.update(fixed_unreplayed_observations=0))
            with self.assertRaises(AssertionError):
                validate(receipt, self.corpus)

    def test_whole_byte_inventory_and_actual_verify_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = fixture(Path(directory), self.corpus)
            identity = receipt["checks"][0]["frames"][0]["frame"]
            path = Path(receipt["_artifact_directory"]) / (identity+".bin")
            path.write_bytes(path.read_bytes()+b" ")
            with self.assertRaises(AssertionError):
                validate(receipt, self.corpus)
        with tempfile.TemporaryDirectory() as directory:
            receipt = fixture(Path(directory), self.corpus)
            receipt["verify_rejection"]["argv"][-1] = "--pipeline-session-v1"
            with self.assertRaises(AssertionError):
                validate(receipt, self.corpus)
        with tempfile.TemporaryDirectory() as directory:
            receipt = fixture(Path(directory), self.corpus)
            campaign.artifact(receipt, b"unreferenced")
            with self.assertRaises(AssertionError):
                validate(receipt, self.corpus)

    def test_guard_forbids_original_manager_and_native_semantic_fallback(self):
        from biocompiler.compiler.pipeline import PassManager
        for module, name in (("biocompiler.compiler.pipeline", "PassManager.run"),
                ("biocompiler.compiler.pipeline", "PassManager.get"),
                ("biocompiler.compiler.synthetic", "run_synthetic_pipeline"),
                ("biocompiler.synthesis.generator", "generate"),
                ("biocompiler.verification.realization", "check")):
            self.assertFalse(campaign.permitted(module, name))
        seen = set()
        with self.assertRaisesRegex(AssertionError, "semantic authority"):
            with campaign.guarded_execution(seen):
                PassManager.__init__(object(), target=None, dependencies={})
        self.assertIsNone(sys.getprofile())

    def test_frozen_oracle_loading_restores_import_path(self):
        from unittest.mock import patch
        before = list(sys.path)
        oracle = campaign.load_oracle(installed=False)
        self.assertEqual(sys.path, before)
        self.assertEqual(oracle.capture()["cases"], self.corpus.cases)
        # CI loads the installed package; local source checks load checkout/src.
        # Arrange the forbidden origin explicitly in either environment.
        name, package = next((name, module) for name, module in sys.modules.items()
            if name == "biocompiler" or name.startswith("biocompiler."))
        origin = package.__file__
        with patch.object(package, "__file__", str(campaign.ROOT / "src/biocompiler/__init__.py")):
            with self.assertRaises(AssertionError) as raised:
                campaign.installed_modules()
            self.assertEqual(str(raised.exception), "Source-tree product loaded: " + name)
        self.assertEqual(package.__file__, origin)

    def test_complete_four_runtime_matrix_rehashes_receipts_and_binaries(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime, native, authority = matrix_fixture(Path(directory), self.corpus)
            # This unchanged 39-case frame fixture isolates shared matrix,
            # source, executable and artifact-integrity machinery. The real
            # gate requires deferred47; a separate control rejects omission.
            with patch.object(campaign, "validate_deferred_checks", return_value=[]):
                result = campaign.compare(runtime, native, **authority)
            self.assertEqual(result["status"], "success")
            self.assertEqual(len(result["receipts"]), 4)
            path = native/"linux-x86_64"/"biocompiler-core"
            path.write_bytes(path.read_bytes()+b" changed")
            with self.assertRaises(ValueError):
                campaign.compare(runtime, native, **authority)

    def test_complete_gate_requires_all_deferred_cases_in_addition_to_existing_39(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = fixture(Path(directory), self.corpus)
            with self.assertRaisesRegex(AssertionError, "Incomplete 47-case"):
                campaign.validate_checks(receipt, self.corpus,
                    campaign.Artifacts(Path(receipt["_artifact_directory"]), receipt["artifacts"]))
        with tempfile.TemporaryDirectory() as directory:
            runtime, native, authority = matrix_fixture(Path(directory), self.corpus)
            path = runtime/"realization-macos-arm64-py3.14"/campaign.RECEIPT_FILE
            receipt = json.loads(path.read_bytes())
            receipt["run_id"] = "older-run"
            path.write_bytes(campaign.canonical(receipt)+b"\n")
            with self.assertRaisesRegex(AssertionError, "mixed manager"):
                with patch.object(campaign, "validate_deferred_checks", return_value=[]):
                    campaign.compare(runtime, native, **authority)

    def test_python_only_role_probe_fixture_uses_actual_flag_and_bounded_io(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"python-probe-fixture"
            path.write_text("#!"+sys.executable+"\nimport sys\nprint(sys.argv[1])\nprint(sys.stdin.read())\nraise SystemExit(2)\n")
            path.chmod(0o755)
            code, stdout, stderr = campaign.raw_exchange(path, b"original input")
            self.assertEqual((code, stdout, stderr), (2, (campaign.ARGUMENT+"\noriginal input\n").encode(), b""))
            path.write_text("#!"+sys.executable+"\nprint('x'*70000)\n")
            with self.assertRaisesRegex(AssertionError, "output exceeded"):
                campaign.raw_exchange(path, b"x")

    def test_four_runtime_comparison_rejects_incomplete_or_stale_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"realization").mkdir()
            (root/"native").mkdir()
            with self.assertRaisesRegex(AssertionError, "four-runtime"):
                campaign.compare(root/"realization", root/"native", revision="a"*40, source_revision="b"*40, run_id="123")
            with self.assertRaisesRegex(AssertionError, "current manager"):
                campaign.compare(root/"realization", root/"native", revision="a"*40, source_revision="b"*40, run_id="")


if __name__ == "__main__":
    unittest.main()

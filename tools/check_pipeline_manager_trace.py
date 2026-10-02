"""Closed, source-bound traceback correspondence for the deferred manager gate.

This validates retained raw stacks. It never treats an arbitrary collection of
allowed frames as an implementation stack: each original manager segment has
one complete adapter/transport/broker recipe, bound to its actual command.
"""
from copy import deepcopy
import ast
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ORACLE = "tools/capture_pipeline_deferred_semantics.py"
CAMPAIGN = "tools/check_pipeline_manager_install.py"
MANAGER = "src/biocompiler/core_pipeline_manager.py"
SESSION = "src/biocompiler/core_pipeline_callback_session.py"
BROKER = "src/biocompiler/pipeline_callback_objects.py"
ORIGINAL = "src/biocompiler/compiler/pipeline.py"
PIPELINE_PIN = "2b1dea35ac3c861f1e933cf7808a241f1f6596e59cc04ceb0ec32e4a54d27331"
SITES = {
    "<genexpr>": {817, 822}, "_document": {47}, "add_input": {613, 615, 618},
    "admit_component_input": {550}, "get": {662, 669}, "register": {452},
    "run": {730, 732, 733, 734, 739, 742, 744, 745, 747, 757, 764, 767, 772, 804, 805, 817, 824, 852, 893},
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def equal(left, right, message):
    encode = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    require(encode(left) == encode(right), message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_nodes(path):
    """Structural source sites also cover 3.11 comprehensions on a 3.14 host."""
    result = {}
    def visit(node, scope="", function=False):
        name = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
        elif isinstance(node, ast.Lambda):
            name = "<lambda>"
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            name = {ast.ListComp: "<listcomp>", ast.SetComp: "<setcomp>", ast.DictComp: "<dictcomp>", ast.GeneratorExp: "<genexpr>"}[type(node)]
        if name is not None:
            scope = (scope + (".<locals>." if function else ".") if scope else "") + name
            function = not isinstance(node, ast.ClassDef)
            result.setdefault(scope, []).append(node)
        for child in ast.iter_child_nodes(node):
            visit(child, scope, function)
    visit(ast.parse((ROOT / path).read_bytes(), filename=path))
    return result


def projection(actual, expected, evidence, details):
    require(sha((ROOT / ORIGINAL).read_bytes()) == PIPELINE_PIN, "Original manager trace source changed")
    projected = deepcopy(actual)
    errors = {entry["event"]: entry for entry in evidence["errors"]}
    require(len(errors) == len(evidence["errors"]) and set(errors) ==
        {event["id"] for event in actual["events"] if event["outcome"] == "raised"},
        "Deferred exception traceback census differs")
    nodes, successors, sources, correspondences = {}, {}, {}, []
    commands = [{entry["sequence"]: entry for entry in native["commands"]} for native in details]
    hosts = {(entry["manager"], entry["token"]): entry for entry in evidence["host_exceptions"]}
    require(len(hosts) == len(evidence["host_exceptions"]), "Duplicate retained host exception")

    def bound(index, sequence):
        require(type(index) is int and 0 <= index < len(details) and type(sequence) is int
            and sequence in commands[index], "Bridge frame lacks its actual native command")
        return commands[index][sequence]

    def frames(chain):
        require(type(chain) is list, "Missing full retained traceback chain")
        result, identities = [], []
        for offset, item in enumerate(chain):
            require(type(item) is dict and set(item) == {"node", "source", "function", "qualname", "line", "source_sha256", "binding"}
                and type(item["node"]) is str and re.fullmatch(r"traceback/[0-9]+", item["node"])
                and type(item["line"]) is int, "Malformed actual traceback node")
            require(item["node"] not in identities, "Repeated/cyclic actual traceback node")
            identities.append(item["node"])
            descriptor = {key: value for key, value in item.items() if key != "node"}
            require(item["node"] not in nodes or nodes[item["node"]] == descriptor, "Actual traceback node was rebound")
            nodes[item["node"]] = descriptor
            following = chain[offset + 1]["node"] if offset + 1 < len(chain) else None
            require(item["node"] not in successors or successors[item["node"]] == following,
                "Actual traceback node changed its retained successor")
            successors[item["node"]] = following
            source = item["source"]
            if source.startswith(("src/", "tools/")):
                require(not Path(source).is_absolute() and ".." not in Path(source).parts
                    and item["source_sha256"] == sha((ROOT / source).read_bytes()), "Traceback source bytes changed")
                if source not in sources:
                    sources[source] = source_nodes(source)
                require(item["qualname"] in sources[source] and any(node.lineno <= item["line"] <= node.end_lineno
                    for node in sources[source][item["qualname"]]), "Actual traceback frame is not a source construct")
                require(item["function"] == item["qualname"].split(".")[-1], "Traceback function/qualified name disagree")
            else:
                require(source == "<frozen _collections_abc>" and item["function"] == "__iter__"
                    and item["source_sha256"] is None and item["binding"] is None, "Unreviewed runtime traceback source")
            binding = item["binding"]
            if binding is not None:
                require(type(binding) is dict and set(binding) == {"manager", "sequence", "invocation", "token"},
                    "Malformed actual frame command binding")
                bound(binding["manager"], binding["sequence"])
            result.append({"file": source, "function": item["function"], "line": item["line"]})
        return result

    def raw_frames(value, chain):
        require(len(value) == len(chain), "Raw actual traceback differs from retained nodes")
        for raw, node in zip(value, chain):
            labels = {node["source"]}
            if node["source"].startswith("src/biocompiler/"):
                labels.add(Path(node["source"]).name)
            require(set(raw) == {"file", "function", "line"} and raw["file"] in labels
                and raw["function"] == node["function"] and raw["line"] == node["line"],
                "Raw actual traceback differs from retained nodes")

    def normalized(value):
        aliases = {"pipeline.py": ORIGINAL, "intent.py": "src/biocompiler/ir/intent.py"}
        return [{**item, "file": aliases.get(item["file"], item["file"])} for item in value]

    def site(item, source, qualname, expression):
        require(item["source"] == source and item["qualname"] == qualname,
            "Bridge segment has missing, duplicated or reordered frames")
        candidates = sources[source][qualname]
        matches = [node for root in candidates for node in ast.walk(root)
            if isinstance(node, (ast.Call, ast.Raise, ast.Compare)) and ast.unparse(node) == expression]
        require(matches and any(node.lineno <= item["line"] <= node.end_lineno for node in matches),
            "Bridge frame is not its exact source call/raise site")

    def take(chain, cursor, source, qualname, expression, binding=None):
        require(cursor < len(chain), "Bridge segment was omitted or truncated")
        item = chain[cursor]
        site(item, source, qualname, expression)
        equal(item["binding"], binding, "Bridge frame belongs to another command/invocation/token")
        return cursor + 1

    def call_expression(source, qualname, callable_name):
        # One exact syntactic call is required; arguments remain source-pinned.
        values = {ast.unparse(node) for root in sources[source][qualname] for node in ast.walk(root)
            if isinstance(node, ast.Call) and ast.unparse(node.func) == callable_name}
        require(len(values) == 1, "Ambiguous bridge source call recipe")
        return next(iter(values))

    def segment(chain, cursor, original, index, sequence):
        command = bound(index, sequence)
        method = original[0]["function"]
        require(command["operation"].replace("-", "_") == method, "Original manager segment belongs to another command")
        for value in original:
            require(value["line"] in SITES.get(value["function"], set()), "Unreviewed original manager traceback site")
        cursor = take(chain, cursor, CAMPAIGN, "GuardedManager.__getattr__.<locals>.invoke", "value(*args, **kwargs)")
        qualname = "CorePassManager." + method
        target = "self._unit" if method in ("register", "register_component_input", "set_dependency", "register_completion_profile") else "self._call"
        cursor = take(chain, cursor, MANAGER, qualname, call_expression(MANAGER, qualname, target))
        if target == "self._unit":
            cursor = take(chain, cursor, MANAGER, "CorePassManager._unit", "self._call(operation, arguments)")
        outcome = command["outcome"]
        require(outcome["status"] in ("raise", "rejected"), "Exception bridge is bound to a successful command")
        owner = {"manager": index, "sequence": sequence, "invocation": None, "token": None}
        cursor = take(chain, cursor, MANAGER, "CorePassManager._call",
            "raise error" if outcome["status"] == "rejected" else "self._session.call(operation, arguments)", owner)
        if outcome["status"] == "rejected":
            return cursor
        token = outcome["token"]
        require((index, token) in hosts, "Host bridge has no actual captured exception")
        host = hosts[index, token]
        invocation = details[index]["invocations"][host["invocation"]]
        require(invocation["command_sequence"] == sequence and invocation["outcome"] == outcome,
            "Host bridge callback belongs to another command/token")
        cursor = take(chain, cursor, SESSION, "CorePipelineCallbackSession.call",
            call_expression(SESSION, "CorePipelineCallbackSession.call", "self._request"))
        cursor = take(chain, cursor, SESSION, "CorePipelineCallbackSession._request", "self.objects.rethrow(token)")
        callback = {**owner, "invocation": host["invocation"]}
        cursor = take(chain, cursor, BROKER, "CallbackObjects.rethrow",
            "raise BaseException.with_traceback(exception, state.traceback)", {**callback, "token": token})
        cursor = take(chain, cursor, BROKER, "CallbackObjects.execute", "self._evaluate(action, arguments)", callback)
        action = invocation["action"]
        expressions = {"document": "value.to_dict()", "attr": "getattr(value, name)",
            "attr-default": "getattr(value, name, self.resolve(args['default']))", "tuple": "tuple(value)",
            "iter": "iter(value)", "next": "next(value)", "freeze-json": "freeze_json(value)",
            "contains": "self.resolve(args['item']) in self.resolve(args['container'])",
            "call": "function(*positional, **keywords)", "call-provider": "provider(self.resolve(args['context']))"}
        if action == "compare":
            require(invocation["arguments"]["operator"] == "eq", "Unreviewed exceptional comparison operation")
            expression = "bool(left == right)"
        else:
            require(action in expressions, "Unreviewed exceptional broker action")
            expression = expressions[action]
        return take(chain, cursor, BROKER, "CallbackObjects._evaluate", expression, callback)

    for event in projected["events"]:
        if event["outcome"] != "raised":
            continue
        identity = event["id"]
        row, link = errors[identity], evidence["events"][identity]
        require(set(row) == {"manager", "event", "identity", "traceback", "required_index"}
            and row["manager"] == link["manager"] and row["identity"] == event["exception"]["identity"],
            "Actual error trace was detached from its original event/object")
        chain = row["traceback"]
        actual_frames = frames(chain)
        raw_frames(event["exception"]["original_traceback"], chain)
        required = row["required_index"]
        require(type(required) is int and 0 <= required <= len(chain), "Invalid retained user traceback start")
        raw_frames(event["exception"]["required_user_traceback_tail"], chain[required:])
        original = normalized(expected["events"][identity]["exception"]["original_traceback"])
        cursor = position = 0
        locations = {len(chain): len(original)}
        segments = []
        while position < len(original):
            value = original[position]
            if value["file"] == ORIGINAL:
                end = position + 1
                while end < len(original) and original[end]["file"] == ORIGINAL:
                    end += 1
                start = cursor
                cursor = segment(chain, cursor, original[position:end], link["manager"], link["sequence"])
                segments.append({"original": [position, end], "actual": [start, cursor],
                    "manager": link["manager"], "sequence": link["sequence"]})
                position = end
                continue
            require(cursor < len(chain), "Original user/leaf traceback frame was omitted")
            equal(actual_frames[cursor], value, "Original user/leaf traceback frames changed, disappeared or reordered")
            require(chain[cursor]["binding"] is None, "Original leaf frame acquired a bridge command binding")
            locations[cursor] = position
            cursor += 1
            position += 1
            if value == {"file": ORACLE, "function": "invoke", "line": 167}:
                cursor = take(chain, cursor, CAMPAIGN,
                    "native_deferred_capture.<locals>.NativeCapture.invoke.<locals>.observed_action", "action()")
            elif value == {"file": ORACLE, "function": "step", "line": 184}:
                cursor = take(chain, cursor, CAMPAIGN, "native_deferred_capture.<locals>.NativeCapture.invoke",
                    "original.invoke(self, operation, observed_action, **arguments)")
                prior = [key for key in errors if key < identity
                    and errors[key]["identity"] == row["identity"]
                    and original[position:] == normalized(expected["events"][key]["exception"]["original_traceback"])
                    and [node["node"] for node in chain[cursor:]] == [node["node"] for node in errors[key]["traceback"]]]
                require(len(prior) == 1, "Reused exception tail lost its exact prior event/node chain")
                old = prior[0]
                # The prior full chain is validated separately, including its
                # own command, rather than reassigning it to the current run.
                if required >= cursor:
                    locations[required] = position + locations.get(required, 0)
                    equal(normalized(event["exception"]["required_user_traceback_tail"]),
                        normalized(expected["events"][identity]["exception"]["required_user_traceback_tail"]),
                        "Reused user tail changed")
                segments.append({"prior_event": old, "actual": [cursor, len(chain)]})
                cursor, position = len(chain), len(original)
        require(cursor == len(chain), "Bridge segment contains extra or reordered frames")
        require(required in locations, "Required user traceback starts inside an implementation segment")
        equal(original[locations[required]:], normalized(expected["events"][identity]["exception"]["required_user_traceback_tail"]),
            "Required user traceback start differs from the original")
        correspondences.append({"event": identity, "manager": link["manager"], "sequence": link["sequence"], "segments": segments})
        for field in ("original_traceback", "required_user_traceback_tail"):
            event["exception"][field] = deepcopy(expected["events"][identity]["exception"][field])

    for (index, token), entry in hosts.items():
        require(set(entry) == {"manager", "token", "invocation", "rethrows", "identity", "cause", "context",
            "suppress_context", "traceback", "events"}, "Incomplete captured original exception evidence")
        frames(entry["traceback"])
        require(len(entry["rethrows"]) == 1 and entry["traceback"], "Original exception was retried, discarded or lost its tail")
        command = bound(index, entry["rethrows"][0])
        invocation = details[index]["invocations"][entry["invocation"]]
        equal(command["outcome"], {"status": "raise", "token": token}, "Original exception was translated instead of rethrown")
        require(invocation["command_sequence"] == command["sequence"] and invocation["outcome"] == command["outcome"],
            "Exception token was reassigned to another command")
        matches = [row for row in evidence["events"] if row["manager"] == index and row["sequence"] == command["sequence"]]
        require(len(matches) == 1 and matches[0]["event"] in errors, "Actual rethrow has no original observed exception")
        event = matches[0]["event"]
        error = actual["events"][event]["exception"]
        equal({key: error[key] for key in ("identity", "cause", "context", "suppress_context")},
            {key: entry[key] for key in ("identity", "cause", "context", "suppress_context")},
            "Rethrow changed actual original exception/cause/context identity")
        tail = [item["node"] for item in entry["traceback"]]
        chain = [item["node"] for item in errors[event]["traceback"]]
        require(len(chain) >= len(tail) and chain[-len(tail):] == tail, "Original traceback tail nodes were replaced during rethrow")
    return projected, correspondences

"""Freeze/check artificial Behavior domain examples for OCaml conformance.

This imports the caller's selected Python biocompiler package and uses existing
public authoring/lowering APIs only. It does not execute an OCaml binary, simulate
a biological implementation, or produce molecular material or acceptance.
Source locations are omitted before enclosing request authority is frozen.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import biocompiler as bc
from biocompiler.compiler.behavior import lower_to_behavior, verify_lowering
from biocompiler.compiler.request import BuildRequest
from biocompiler.ir.behavior import (
    BEHAVIOR_V2, EXTENSION_KINDS, SCHEMA_VERSION, SUPPORTED_KINDS, BehaviorProgram,
)
from biocompiler.ir.intent import IntentProgram


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/behavior-domains-v1.json"
SCHEMA = "biocompiler.behavior_domains_conformance.v1"


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def model(name):
    therapy = bc.Therapy("artificial_behavior_domain_" + name)
    return therapy, therapy.engineer("observer", cell_type="abstract_cell")


def algebra():
    """Adapt the symbolic arithmetic patterns from tests/test_expressions.py."""
    therapy, cells = model("algebra")
    gain = therapy.parameter("gain", type=bc.Level, default=2)
    signal = cells.internal.signal("numeric_input", type=bc.Level)
    arithmetic = -(signal * gain + 1 - 2) / 2
    conditions = [arithmetic < 1, arithmetic <= 1, arithmetic > 1,
                  arithmetic >= 1, arithmetic == 1, arithmetic != 1]
    for index, condition in enumerate(conditions):
        cells.when(condition, name=f"comparison_{index}").do(cells.report(f"comparison_{index}"))
    selected = bc.at_least(2, signal.present(), signal.high(), ~signal.low())
    cells.when((selected | conditions[0]) & conditions[1]).do(cells.rest())
    # Include constant arithmetic as well as runtime scalar expressions.
    cells.when(((gain + 3 - 1) * 2 / 4) >= -gain).do(cells.report("constant_expression"))
    return therapy


def temporal_memory():
    """Use every existing memory shape and the temporal-response example ops."""
    therapy, cells = model("temporal_memory")
    dwell = therapy.parameter("dwell", type=bc.Duration, default=bc.Duration(2))
    observed = cells.environment.signal("context").present()
    reset = cells.external.signal("reset").present()
    sustained = observed.held_for(dwell)
    recent = observed.recently(within=bc.Duration(3))
    ordered = observed.became_true().followed_by(reset.became_true(), within=bc.Duration(4))
    memories = [
        cells.memory("set_only", set_when=sustained),
        cells.memory("resettable", set_when=recent, reset_when=reset),
        cells.memory("expiring", set_when=observed, duration=bc.Duration(5)),
        cells.memory("resettable_expiring", set_when=observed,
                     reset_when=reset, duration=bc.Duration(6)),
    ]
    for memory in memories:
        cells.when(memory.is_set()).do(cells.report("memory_is_set"))
    cells.on(ordered, name="ordered_event").do(cells.rest().for_(bc.Duration(2)),
                                               cells.report("ordered_event"))
    return therapy


def signature_predicate(condition, metadata):
    """The descriptor argument is retained without influencing the predicate."""
    del metadata
    return condition


# The definition's nominal identity must not depend on importing this tool as a
# module versus invoking it as __main__. This is an artificial fixture identity.
signature_predicate.__module__ = "biocompiler.conformance.behavior_domains"
signature_predicate.__qualname__ = "signature_predicate"
inspectable_signature = bc.signature(signature_predicate)


def actions_state_signature():
    """Use existing actions/state/signature patterns with artificial labels."""
    therapy, cells = model("actions_state_signature")
    context = cells.environment.signal("context").present()
    contacted = cells.contact.marker("ARTIFICIAL_MARKER").present()
    phase = cells.state("typed_phase", values=(False, 0, 0.0, "ready"), initial=False)
    for value in (False, 0, 0.0, "ready"):
        phase.is_(value)
    cells.when(context & phase.is_(False)).do(phase.set("ready"))
    metadata = {"handles": [cells.contact], "values": [None, True, 1, 1.0, -0.0, "symbol"],
                "quantity": bc.Duration(2)}
    recognized = inspectable_signature(context, metadata)
    rate = therapy.parameter("rate", type=bc.ProductionRate, default=bc.ProductionRate(2))
    explicit = cells.secretion("declared_output", product="ARTIFICIAL_PRODUCT")
    cells.when(recognized).do(cells.report("recognized"), explicit.produce(rate=rate),
                              cells.secrete("ARTIFICIAL_UNSPECIFIED"), cells.present("ARTIFICIAL_ANTIGEN"),
                              cells.retain("declared_location"), cells.retain(cells.internal),
                              cells.expand(), cells.rest(), cells.differentiate("artificial_state"))
    cells.when(contacted).do(cells.eliminate(cells.contact), cells.engulf(cells.contact),
                             cells.eliminate(cells.contact).for_(bc.Duration(2)))
    return therapy


def sampled_multirole():
    """Use receiver-local channels and sampled integration from payload tests."""
    therapy, sender = model("sampled_multirole")
    receiver = therapy.engineer("receiver", cell_type="abstract_cell")
    channel = therapy.channel("ARTIFICIAL_CHANNEL", scope="local", type=bc.Level)
    observed = sender.environment.signal("observed_value", type=bc.Level)
    area = observed.integrated(over=bc.Duration(3))
    sender.when(area < bc.Duration(4)).do(sender.emit(channel), sender.emit(channel, value=observed))
    received = receiver.sense(channel)
    receiver.when(received.present() | received.high() | received.low()).do(receiver.report("received"))
    return therapy


def freeze_case(identity, therapy, profile, *, step=None):
    original = therapy.freeze()
    source = IntentProgram.from_dict(original.to_dict(include_source=False))
    require(source.fingerprint == original.fingerprint, "Source-location omission changed semantic intent identity")
    constraints = {} if step is None else {"execution": {"integral_step": bc.Duration(step).to_dict()}}
    request = BuildRequest.freeze(source, behavior_profile=profile, implementation_constraints=constraints)
    behavior = lower_to_behavior(request)
    require(verify_lowering(request, behavior).passed, f"Python lowering preservation failed for {identity}")
    normalized = BehaviorProgram.from_dict(behavior.to_dict(include_source=False))
    require(normalized.fingerprint == behavior.fingerprint, "Source-location omission changed Behavior identity")
    document = normalized.to_dict()
    require(BehaviorProgram.from_dict(document).to_dict() == document, "Behavior fixture is not normalized")
    return {"id": identity, "behavior": document, "fingerprint": normalized.fingerprint,
            "source_fingerprint": normalized.source_fingerprint,
            "operation_counts": dict(sorted(Counter(node.kind for node in normalized.nodes).items()))}


def coverage_for(cases):
    by_profile = defaultdict(set)
    variants = defaultdict(set)
    for case in cases:
        behavior = case["behavior"]
        for node in behavior["nodes"]:
            kind, attributes = node["kind"], node["attributes"]
            by_profile[behavior["schema_version"]].add(kind)
            if kind == "compare": variants["comparison_operators"].add(attributes["operator"])
            if kind == "qualitative": variants["qualitative_bands"].add(attributes["band"])
            if kind == "scope": variants["observation_scopes"].add(attributes["scope"])
            if kind == "memory": variants["memory_input_shapes"].add(",".join(attributes["input_names"]))
            if kind == "rule": variants["rule_triggers"].add(attributes["trigger"])
            if kind == "action.secrete": variants["secretion_rate_modes"].add(attributes["rate"])
            if kind == "action.emit": variants["emission_value_modes"].add(attributes["value"])
            if kind == "action.retain": variants["retention_forms"].add("named_location" if "location" in attributes else "scope_input")
            if kind == "state": variants["state_value_types"].update(type(value).__name__ for value in attributes["values"])
            if kind == "secretion": variants["secretion_declarations"].add("default" if attributes["default"] else "explicit")
    covered = set().union(*by_profile.values())
    return {"supported_kinds": sorted(SUPPORTED_KINDS), "extension_kinds": sorted(EXTENSION_KINDS),
            "covered_kinds": sorted(covered), "uncovered_kinds": sorted((SUPPORTED_KINDS | EXTENSION_KINDS) - covered),
            "by_profile": {profile: sorted(kinds) for profile, kinds in sorted(by_profile.items())},
            "variants": {key: sorted(values) for key, values in sorted(variants.items())}}


def build_corpus():
    cases = []
    for identity, builder in (("algebra", algebra), ("temporal_memory", temporal_memory),
                              ("actions_state_signature", actions_state_signature)):
        for profile, label in ((SCHEMA_VERSION, "v1"), (BEHAVIOR_V2, "v2")):
            cases.append(freeze_case(identity + "_" + label, builder(), profile))
    cases.append(freeze_case("sampled_multirole_v2", sampled_multirole(), BEHAVIOR_V2, step=1))
    coverage = coverage_for(cases)
    require(not coverage["uncovered_kinds"], "Behavior corpus omits operations: " + repr(coverage["uncovered_kinds"]))
    require(set(coverage["by_profile"][SCHEMA_VERSION]) == SUPPORTED_KINDS, "Legacy corpus does not cover its complete operation set")
    require(set(coverage["by_profile"][BEHAVIOR_V2]) == SUPPORTED_KINDS | EXTENSION_KINDS, "V2 corpus does not cover its complete operation set")
    return {"schema_version": SCHEMA,
            "claim_scope": "Artificial abstract Behavior import and canonical-identity conformance only; no reference-execution parity, molecular realization, or candidate acceptance.",
            "source_references": ["tests/test_expressions.py", "tests/test_behavior_ir.py", "tests/test_behavior_execution.py",
                                  "tests/test_payload_execution.py", "examples/intent_programs.py"],
            "source_location_policy": "Omitted before BuildRequest freezing; retained normalized documents carry null node/requirement source locations. Semantic fingerprints exclude locations.",
            "coverage": coverage, "cases": cases}


def check_corpus(document):
    require(document["schema_version"] == SCHEMA, "Unknown Behavior conformance schema")
    for case in document["cases"]:
        program = BehaviorProgram.from_dict(case["behavior"])
        require(encoded(program.to_dict()) == encoded(case["behavior"]), "Non-normalized Behavior fixture " + case["id"])
        require(program.fingerprint == case["fingerprint"], "Wrong Behavior fingerprint " + case["id"])
        require(program.source_fingerprint == case["source_fingerprint"], "Wrong source fingerprint " + case["id"])
        require(dict(sorted(Counter(node.kind for node in program.nodes).items())) == case["operation_counts"], "Wrong operation counts " + case["id"])
    require(document["coverage"] == coverage_for(document["cases"]), "Coverage manifest disagrees with retained documents")
    require(not document["coverage"]["uncovered_kinds"], "Behavior operation coverage is incomplete")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=CORPUS)
    parser.add_argument("--write", action="store_true", help="Write the deterministic corpus; otherwise verify its exact bytes.")
    args = parser.parse_args(argv)
    corpus = build_corpus()
    check_corpus(corpus)
    content = encoded(corpus)
    require(len(content) < 4_000_000, "Behavior corpus exceeds its fixture byte budget")
    if args.write:
        args.output.write_bytes(content)
    else:
        retained = args.output.read_bytes()
        check_corpus(json.loads(retained))
        require(retained == content, "Behavior domain corpus has drifted; inspect changes before refreezing")
    print(json.dumps({"status": "written" if args.write else "checked", "cases": len(corpus["cases"]),
                      "covered_operations": len(corpus["coverage"]["covered_kinds"]), "uncovered": corpus["coverage"]["uncovered_kinds"],
                      "bytes": len(content)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

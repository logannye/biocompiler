"""Synthetic retained-authority controls; no native or biological acceptance.

These hand-authored records isolate the evidence decoder. They are not complete
native compiler requests, and no generated receipt supplies their expectations.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from biocompiler import core_policy_component_material as api
from biocompiler import core_policy_implementation as implementation
from biocompiler.core_client import CoreProtocolError, encode_json


def pin(value):
    return hashlib.sha256(encode_json(value)).hexdigest()


def records():
    definitions = [
        {"$type": "SemanticDefinition", "id": name, "version": "1", "category": kind,
         "source_map": [{"note": "retained but excluded from definition identity"}], "provenance": []}
        for name, kind in (("chassis", "model"), ("interface", "interface"), ("environment", "environment"),
                           ("prerequisite", "environment"), ("delivery", "delivery"), ("unused", "environment"))
    ]
    refs = {row["id"]: {"$type": "DefinitionRef", "id": row["id"], "version": "1",
             "digest": pin({key: value for key, value in row.items() if key not in ("source_map", "provenance")})}
            for row in definitions}
    chassis = {"operational_model": refs["chassis"], "capabilities": [refs["interface"]],
               "interfaces": [refs["interface"]], "environment": [refs["environment"]]}
    available = {"onset_min": "0", "onset_max": "0", "duration_min": "6", "duration_max": "6"}
    channel = {"id": "condition", "kind": "observation", "source": "condition", "observer": "executor",
               "subject": "encounter/target", "availability": available}
    providers = [
        {"identity": {"id": name}, "body": {"definition": refs[name], "kind": kind, **fields}}
        for name, kind, fields in (
            ("chassis", "chassis", {"chassis": chassis}),
            ("interface", "interface", {"environment": refs["prerequisite"], "channels": [channel]}),
            ("environment", "environment", {}), ("prerequisite", "environment", {}), ("delivery", "delivery", {}))
    ]
    entry = {"id": "catalog", "version": "1", "dependencies": [refs["interface"]], "evidence": []}
    catalog = {"implementations": [entry]}
    document = {"$type": "BuildRequest", "implementations": catalog,
        "program": {"semantics": {"definitions": definitions}, "declarations": [
            {"$type": "Role", "id": "executor", "requires": [refs["interface"]]},
            {"$type": "Observation", "id": "condition"},
            {"$type": "Role", "id": "target", "requires": [refs["interface"]]}]},
        "deployment": {"bindings": [{"chassis": chassis}], "environment": [refs["environment"]],
                       "delivery": {key: refs["delivery"] for key in ("arrival", "expression", "activation", "contract")}}}
    original = {key: {} for key in implementation._REQUEST_FIELDS}
    original.update(schema_version=implementation.PREREQUISITE_REQUEST_SCHEMA,
        profile=implementation.PREREQUISITE_REQUEST_PROFILE, document=document, operating_domain={"horizon": 6},
        catalog_bindings=[{"entry_id": "catalog", "entry_digest": pin(entry)}])
    selections = [{"slot": slot, "component": {"id": "same.component"}} for slot in ("left", "right")]
    requirements = [{"kind": "capacity", "owner": "state"}]
    context = {"clock": {"origin": "0"}, "recipient": {"identity": "executor"}, "providers": providers}
    request = {key: {} for key in api._REQUEST_FIELDS}
    request.update(schema_version=api.PREREQUISITE_REQUEST_SCHEMA, profile=api.PREREQUISITE_REQUEST_PROFILE,
        implementation_request=original, component_library={"components": [
            {"identity": {"id": "same.component"}, "body": {"provider_requirements": requirements}}]},
        composition_rule={"body": {"components": selections}}, context=context,
        input_bindings=[{"input": "condition", "source": "condition", "provider": refs["interface"], "channel": "condition"}])
    pending = [{"entry_id": "catalog", "entry_digest": pin(entry), "dependency_index": 0, "definition": refs["interface"]}]
    root_specs = [
        ("/deployment/bindings/0/chassis/operational_model", "chassis"),
        ("/deployment/bindings/0/chassis/capabilities/0", "interface"),
        ("/deployment/bindings/0/chassis/interfaces/0", "interface"),
        ("/deployment/bindings/0/chassis/environment/0", "environment"),
        ("/deployment/environment/0", "environment"),
        ("/program/declarations/0/requires/0", "interface"),
        ("/program/declarations/2/requires/0", "interface"),
        *[("/deployment/delivery/" + key, "delivery") for key in ("arrival", "expression", "activation", "contract")],
    ]
    roots = [{"origin": {"kind": "source", "path": path}, "definition": refs[name]} for path, name in root_specs]
    roots.append({"origin": {"kind": "catalog_dependency", "entry_id": "catalog", "entry_digest": pin(entry),
                             "dependency_index": 0}, "definition": refs["interface"]})
    graph = {"schema_version": "biocompiler.policy_provider_dependency_graph.v0.1", "pending_dependencies": pending,
        "roots": roots, "nodes": [{"definition": refs[name], "provider": {"id": name}} for name in
                                   ("chassis", "interface", "prerequisite", "environment", "delivery")],
        "edges": [{"source": refs[source], "relation": relation, "index": 0, "target": refs[target]}
                  for source, relation, target in (("chassis", "chassis_capability", "interface"),
                    ("interface", "interface_environment", "prerequisite"),
                    ("chassis", "chassis_interface", "interface"), ("chassis", "chassis_environment", "environment"))],
        "issues": []}
    assembly = {"synthetic_assembly": "authority-decoder-only"}
    closure = {"schema_version": "biocompiler.policy_provider_prerequisite_closure.v0.1",
        "profile": api.PREREQUISITE_REQUEST_PROFILE, "status": "pass", "complete": True,
        "original_request_fingerprint": pin(request), "assembly_fingerprint": pin(assembly),
        "source_catalog": catalog, "pending_dependencies": pending, "instances": selections,
        "local_requirements": [{**row, "requirements": requirements} for row in selections],
        "providers": [{"definition": row["body"]["definition"], "identity": row["identity"],
                       "body_fingerprint": pin(row["body"])} for row in providers],
        "graph": graph, "operating_domain_fingerprint": pin(original["operating_domain"]),
        "clock": context["clock"], "recipient": context["recipient"],
        "input_allocations": [{"input": "condition", "source": "condition", "provider": refs["interface"],
            "channel": "condition", "kind": "observation", "observer": "executor", "subject": "encounter/target", "available": available}],
        "resource_allocations": [], "diagnostics": [], "empirical": "unassessed"}
    report = {"assembly": assembly, "prerequisites": closure, "prerequisite_status": "pass",
        "context": {"outcome": "pass", "diagnostics": [], "resource_allocations": [], "prerequisite_closure": deepcopy(closure)}}
    return deepcopy(request), deepcopy(report)


def sync(report):
    report["context"]["prerequisite_closure"] = deepcopy(report["prerequisites"])


def outcome(report, status, diagnostic):
    report["prerequisite_status"] = status
    report["context"].update(outcome=status, diagnostics=[diagnostic])
    report["prerequisites"].update(status=status, complete=False, diagnostics=[diagnostic])
    sync(report)


class PolicyPrerequisiteEvidenceTests(unittest.TestCase):
    def quantitative_records(self, family):
        # Only the real fixture's declared profile identities are reused. The
        # hand-authored records remain decoder controls, not native acceptance.
        path = Path(__file__).resolve().parents[1] / "core/test/data" / ("policy_quantitative" + family + "_v01.json")
        declared = json.loads(path.read_text())["request"]
        request, report = records()
        for key in ("schema_version", "profile"):
            request[key] = declared[key]
            request["implementation_request"][key] = declared["implementation_request"][key]
            request["context"][key] = declared["context"][key]
        # Independent literal from the native context contract: every current
        # quantitative family keeps this context and closure scope unchanged.
        context_profile = "biocompiler.policy_finite_machine_component_mrna.v0.1"
        self.assertEqual(request["context"]["profile"], context_profile)
        self.assertNotEqual(request["profile"], context_profile)
        report["context"]["profile"] = context_profile
        report["prerequisites"].update(profile=context_profile, original_request_fingerprint=pin(request))
        sync(report)
        return request, report

    def test_quantitative_closures_retain_native_context_scope_for_every_family(self):
        for family in ("", "_step", "_transfer", "_network", "_composition"):
            request, report = self.quantitative_records(family)
            with self.subTest(family=family):
                api._prerequisite_evidence(request, report)

    def test_quantitative_closure_rejects_outer_law_and_other_scope_substitution(self):
        for family in ("", "_step", "_transfer", "_network", "_composition"):
            request, original = self.quantitative_records(family)
            for profile in (request["profile"], api.PREREQUISITE_REQUEST_PROFILE,
                            api.NETWORK_REQUEST_PROFILE, "invented.context.profile"):
                report = deepcopy(original)
                report["prerequisites"]["profile"] = profile
                sync(report)
                with self.subTest(family=family, profile=profile), self.assertRaisesRegex(CoreProtocolError, "Prerequisite scope"):
                    api._prerequisite_evidence(request, report)

    def test_quantitative_native_scope_does_not_relax_original_authority_or_status(self):
        mutations = [lambda closure: closure.update(original_request_fingerprint="0" * 64),
            lambda closure: closure.update(assembly_fingerprint="0" * 64),
            lambda closure: closure.update(operating_domain_fingerprint="0" * 64),
            lambda closure: closure["local_requirements"].pop(),
            lambda closure: closure["providers"][0].update(body_fingerprint="0" * 64),
            lambda closure: closure.update(status="unknown"), lambda closure: closure.update(complete=False),
            lambda closure: closure.update(diagnostics=["invented"]),
            lambda closure: closure.update(empirical="verified")]
        for family in ("", "_step", "_transfer", "_network", "_composition"):
            request, original = self.quantitative_records(family)
            for mutation in mutations:
                report = deepcopy(original)
                mutation(report["prerequisites"])
                sync(report)
                with self.subTest(family=family, mutation=mutation), self.assertRaises(CoreProtocolError):
                    api._prerequisite_evidence(request, report)

    def test_exact_inventory_preserves_repeated_roots_and_distinct_instance_owners(self):
        request, report = records()
        api._prerequisite_evidence(request, report)
        self.assertEqual(len(report["prerequisites"]["graph"]["roots"]), 12)
        self.assertEqual([row["slot"] for row in report["prerequisites"]["local_requirements"]], ["left", "right"])

    def test_original_source_root_occurrence_path_order_and_definition_are_bound(self):
        mutations = [lambda roots: roots.pop(0), lambda roots: roots.reverse(),
            lambda roots: roots[0]["origin"].update(path="/invented"),
            lambda roots: roots[0].update(definition=deepcopy(roots[1]["definition"])),
            lambda roots: roots.append(deepcopy(roots[1])),
            lambda roots: roots[-1]["origin"].update(dependency_index=1),
            lambda roots: roots[0]["origin"].update(extra="ignored")]
        for mutation in mutations:
            request, report = records()
            mutation(report["prerequisites"]["graph"]["roots"])
            sync(report)
            with self.subTest(mutation=mutation), self.assertRaises(CoreProtocolError):
                api._prerequisite_evidence(request, report)

    def test_missing_provider_receipt_retains_exact_definition_without_a_body(self):
        request, report = records()
        closure = report["prerequisites"]
        missing = closure["graph"]["nodes"][2]
        request["context"]["providers"] = [row for row in request["context"]["providers"] if row["identity"]["id"] != "prerequisite"]
        closure["providers"] = [row for row in closure["providers"] if row["identity"]["id"] != "prerequisite"]
        missing["provider"] = None
        closure["graph"]["issues"] = [{"kind": "missing", "code": "prerequisite_provider_missing", "references": [deepcopy(missing["definition"])]}]
        closure["input_allocations"] = []
        closure["original_request_fingerprint"] = pin(request)
        outcome(report, "unknown", "prerequisite_provider_missing")
        api._prerequisite_evidence(request, report)
        for key, value in (("id", "invented"), ("version", "stale"), ("digest", "0" * 64)):
            mutated = deepcopy(report)
            mutated["prerequisites"]["graph"]["nodes"][2]["definition"][key] = value
            sync(mutated)
            with self.subTest(key=key), self.assertRaises(CoreProtocolError):
                api._prerequisite_evidence(request, mutated)

    def test_early_fail_and_unsupported_receipts_keep_complete_graph_with_empty_allocations(self):
        for status, diagnostic in (("fail", "provider_executor_or_compartment"),
                                    ("unsupported", "unimplemented_original_provider_clauses")):
            request, report = records()
            report["prerequisites"]["input_allocations"] = []
            outcome(report, status, diagnostic)
            api._prerequisite_evidence(request, report)

    def test_extra_provider_negative_is_retained_without_claiming_it_is_reachable(self):
        request, report = records()
        definition = next(row for row in request["implementation_request"]["document"]["program"]["semantics"]["definitions"] if row["id"] == "unused")
        reference = {"$type": "DefinitionRef", "id": "unused", "version": "1",
                     "digest": pin({key: value for key, value in definition.items() if key not in ("source_map", "provenance")})}
        provider = {"identity": {"id": "unused"}, "body": {"definition": reference, "kind": "environment"}}
        request["context"]["providers"].append(provider)
        closure = report["prerequisites"]
        closure["providers"].append({"definition": reference, "identity": provider["identity"], "body_fingerprint": pin(provider["body"])})
        closure["graph"]["issues"] = [{"kind": "extra", "code": "prerequisite_provider_extra", "references": [reference]}]
        closure["input_allocations"] = []
        closure["original_request_fingerprint"] = pin(request)
        outcome(report, "fail", "prerequisite_provider_extra")
        api._prerequisite_evidence(request, report)

    def test_graph_nodes_targets_and_issue_definition_pins_are_retained_on_negatives(self):
        mutations = [lambda graph: graph["nodes"].pop(0), lambda graph: graph["nodes"].pop(2),
            lambda graph: graph["nodes"].append(deepcopy(graph["nodes"][0])),
            lambda graph: graph["issues"][0]["references"][0].update(digest="0" * 64),
            lambda graph: graph["issues"][0].update(code="invented"),
            lambda graph: graph["issues"][0].update(references=[]),
            lambda graph: graph["edges"][0].update(index=1)]
        for mutation in mutations:
            request, report = records()
            graph = report["prerequisites"]["graph"]
            graph["issues"] = [{"kind": "unsupported", "code": "prerequisite_definition_unsupported", "references": [deepcopy(graph["nodes"][1]["definition"])]}]
            outcome(report, "unsupported", "prerequisite_definition_unsupported")
            mutation(graph)
            sync(report)
            with self.subTest(mutation=mutation), self.assertRaises(CoreProtocolError):
                api._prerequisite_evidence(request, report)

    def test_all_closure_authority_fields_and_owner_inventory_are_bound(self):
        mutations = [lambda closure: closure.update(original_request_fingerprint="0" * 64),
            lambda closure: closure.update(assembly_fingerprint="0" * 64),
            lambda closure: closure.update(operating_domain_fingerprint="0" * 64),
            lambda closure: closure.update(clock={}), lambda closure: closure.update(recipient={}),
            lambda closure: closure.update(source_catalog={}), lambda closure: closure.update(pending_dependencies=[]),
            lambda closure: closure["local_requirements"].pop(), lambda closure: closure["instances"].reverse(),
            lambda closure: closure["providers"][0].update(body_fingerprint="0" * 64),
            lambda closure: closure["input_allocations"][0].update(subject="other"),
            lambda closure: closure.update(complete=False)]
        for mutation in mutations:
            request, report = records()
            mutation(report["prerequisites"])
            sync(report)
            with self.subTest(mutation=mutation), self.assertRaises(CoreProtocolError):
                api._prerequisite_evidence(request, report)

    def test_context_not_reached_retains_unassessed_and_no_closure(self):
        request, report = records()
        report.update(context=None, prerequisites=None, prerequisite_status="unassessed")
        api._prerequisite_evidence(request, report)
        for status in ("pass", "unknown"):
            report["prerequisite_status"] = status
            with self.assertRaises(CoreProtocolError):
                api._prerequisite_evidence(request, report)

    def test_context_receipt_always_requires_a_complete_graph_object(self):
        request, report = records()
        report["prerequisites"]["graph"] = None
        outcome(report, "unknown", "synthetic_exhaustion_does_not_authorize_a_partial_graph")
        with self.assertRaises(CoreProtocolError):
            api._prerequisite_evidence(request, report)


if __name__ == "__main__":
    unittest.main()

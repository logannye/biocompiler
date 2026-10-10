"""Inert coupled wire boundaries and descriptive views; no native acceptance."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from biocompiler import _policy_coupled_wire as wire
from biocompiler import core_policy_component_material as component
from biocompiler import core_policy_material as material
from biocompiler import core_policy_quantitative_assurance as assurance
from biocompiler import core_policy_refinement as refinement
from biocompiler.core_client import CORE_VERSION, CoreProtocolError, CoreResponse, encode_json
from tests import test_core_policy_material as old
from tests.test_policy_coupled_wire import paired_export
from tools import generate_policy_quantitative_composition_fixture as fixture


def large_tree(blocks=130):
    return [[None] * 1000] * blocks


class InertTransport:
    """Only wire negotiation/encoding is under test; results grant no proof."""
    role = "core"

    def __init__(self):
        self.calls = []
        self.packed = True
        self.response = None
        self.capabilities = SimpleNamespace(profiles={
            "policy_coupled_quantitative_material": component.COMPOSITION_PROFILE,
            "policy_coupled_quantitative_material_producer": component.COMPOSITION_PRODUCER_PROFILE,
            "policy_quantitative_assurance": assurance.PROFILE,
            "policy_quantitative_assurance_producer": assurance.PRODUCER_PROFILE,
            "policy_refinement": refinement.PROFILE,
            "policy_coupled_wire": wire.profile(self.role),
            "policy_coupled_assurance_export_wire": wire.export_profile()}, validation_scopes=[
                component.COMPOSITION_VALIDATION_SCOPE, assurance.VALIDATION_SCOPE, refinement.VALIDATION_SCOPE])

    def negotiate(self, operation, *, cancelled=None):
        return self.capabilities

    def call(self, operation, payload, *, cancelled=None):
        encode_json({"payload": payload})  # The unchanged physical protocol cap.
        self.calls.append((operation, deepcopy(payload)))
        value = self.response if self.response is not None else {"notice": "inert wire observation"}
        packet = (wire.pack_export(value) if operation == "export-policy-quantitative-assurance" else wire.pack(value)) if self.packed else value
        return CoreResponse("inert-coupled", operation, "ok", packet,
                            (), self.role, CORE_VERSION)


class CoupledTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(fixture.PATH.read_text())

    def clients(self):
        original = self.fixture["request"]
        wrapper = {"schema_version": assurance.REQUEST_SCHEMA, "profile": assurance.REQUEST_PROFILE,
            "material_request": original, "approximation": None, "realization_evidence": None, "max_work": assurance.MAX_WORK}
        return ((component, component.PolicyComponentMaterialClient, original),
                (assurance, assurance.PolicyQuantitativeAssuranceClient, wrapper),
                (refinement, refinement.PolicyRefinementClient, original))

    def test_three_clients_pack_complete_payload_and_unpack_only_outer_response(self):
        for api, constructor, request in self.clients():
            transport = InertTransport()
            payload = {"request": request, "candidate": {"supplied": "untrusted"}, "limits": self.fixture["limits"]}
            operation = api.PROFILE["operations"][0]
            with self.subTest(api=api.__name__), patch.object(api, "_result", side_effect=lambda response, original: (response.result, original)):
                logical, snapshot = constructor(transport)._call(operation, payload, cancelled=None)
            self.assertEqual(logical, {"notice": "inert wire observation"})
            self.assertEqual(snapshot, payload)
            self.assertTrue(wire.is_packet(transport.calls[0][1]))
            self.assertEqual(wire.unpack(transport.calls[0][1]), payload)
            self.assertIsNot(snapshot["request"], payload["request"])

    def test_exact_role_capability_and_packed_response_are_required(self):
        for api, constructor, request in self.clients():
            payload = {"request": request, "candidate": {}, "limits": self.fixture["limits"]}
            operation = api.PROFILE["operations"][0]
            for mutation in ("absent", "wrong_role", "logical_response"):
                transport = InertTransport()
                if mutation == "absent": transport.capabilities.profiles.pop("policy_coupled_wire")
                elif mutation == "wrong_role": transport.capabilities.profiles["policy_coupled_wire"] = wire.profile("verify")
                else: transport.packed = False
                with self.subTest(api=api.__name__, mutation=mutation), self.assertRaises(CoreProtocolError), patch.object(api, "_result"):
                    constructor(transport)._call(operation, payload, cancelled=None)

    def test_replay_snapshot_can_exceed_physical_nodes_without_relaxing_candidate_limit(self):
        api, constructor, request = self.clients()[0]
        repeated = large_tree()
        payload = {"request": request, "candidate": {}, "limits": self.fixture["limits"],
                   "report": {"left": repeated, "right": repeated}}
        with self.assertRaises(CoreProtocolError): encode_json(payload)
        transport = InertTransport()
        with patch.object(api, "_result", side_effect=lambda response, original: original):
            logical = constructor(transport)._call("replay-policy-component-material", payload, cancelled=None)
        self.assertEqual(logical, payload)
        self.assertEqual(wire.unpack(transport.calls[0][1]), payload)
        payload["candidate"] = {"oversized": large_tree(251)}
        with self.assertRaises(CoreProtocolError):
            constructor(InertTransport())._call("check-policy-component-material", payload, cancelled=None)

    def test_result_views_remain_detached_and_logical_above_physical_node_bound(self):
        repeated = large_tree()
        logical = {"candidate": {"cells": repeated}, "report": {"cells": repeated}, "artifact": None}
        with self.assertRaises(CoreProtocolError): encode_json(logical)
        stored = component._result_bytes(logical, coupled=True)
        results = (component.PolicyComponentMaterialResult("id", "check", "verify", "a", "b", "c", "d", stored),
            assurance.PolicyQuantitativeAssuranceResult("id", "check", "verify", stored),
            refinement.PolicyRefinementResult("id", "check", "verify", "a", "b", "c", "d", None, stored))
        for result in results:
            view = result.result
            self.assertEqual(view, logical)
            view["candidate"]["cells"][0][0] = True
            self.assertIsNone(view["report"]["cells"][0][0])
            self.assertIsNone(result.result["candidate"]["cells"][0][0])

    def test_wire_packet_cannot_cross_a_legacy_result_boundary(self):
        response = CoreResponse("id", "check", "ok", wire.pack({"notice": "data"}), (), "verify", CORE_VERSION)
        with self.assertRaises(CoreProtocolError): component._wire_response(response, coupled=False)
        ordinary = CoreResponse("id", "check", "ok", {"notice": "data"}, (), "verify", CORE_VERSION)
        self.assertIs(component._wire_response(ordinary, coupled=False), ordinary)

    def test_paired_export_requires_additional_exact_capability_and_operation(self):
        api, constructor, request = self.clients()[1]
        payload = {"request": request, "candidate": {}, "limits": self.fixture["limits"]}
        operation = "export-policy-quantitative-assurance"
        transport = InertTransport()
        transport.response = paired_export()
        with patch.object(api, "_result", side_effect=lambda response, original: response.result):
            self.assertEqual(constructor(transport)._call(operation, payload, cancelled=None), paired_export())
        self.assertTrue(wire.is_packet(transport.calls[0][1]))  # Inputs retain v0.1.
        for mutation in ("absent", "input_direction", "larger_part", "other_operation"):
            transport = InertTransport()
            transport.response = paired_export()
            profile = transport.capabilities.profiles["policy_coupled_assurance_export_wire"]
            if mutation == "absent": transport.capabilities.profiles.pop("policy_coupled_assurance_export_wire")
            elif mutation == "input_direction": profile["direction"] = "request"
            elif mutation == "larger_part": profile["max_part_bytes"] += 1
            else: profile["operations"] = ["check-policy-quantitative-assurance"]
            with self.subTest(mutation=mutation), self.assertRaises(CoreProtocolError):
                constructor(transport)._call(operation, payload, cancelled=None)
            self.assertEqual(transport.calls, [])
        packet = wire.pack_export(paired_export())
        for name in (operation, "check-policy-quantitative-assurance", "export-policy-component-material", "check-policy-refinement"):
            response = CoreResponse("id", name, "ok", packet, (), "verify", CORE_VERSION)
            with self.subTest(name=name), self.assertRaises(CoreProtocolError):
                component._wire_response(response, coupled=True)
            with self.assertRaises(CoreProtocolError): component._wire_response(response, coupled=False)
            if name != operation:
                with self.assertRaises(CoreProtocolError): component._wire_response(response, coupled=True, paired_export=True)
        ordinary = CoreResponse("id", operation, "ok", wire.pack(paired_export()), (), "verify", CORE_VERSION)
        with self.assertRaises(CoreProtocolError): component._wire_response(ordinary, coupled=True, paired_export=True)

    def test_paired_export_storage_is_explicit_detached_and_not_a_replay_input(self):
        value = paired_export(large_tree(510), large_tree(510))
        stored = component._result_bytes(value, coupled=True, paired_export=True)
        result = assurance.PolicyQuantitativeAssuranceResult("id", "export-policy-quantitative-assurance", "verify", stored)
        self.assertEqual(result.result, value)
        view = result.result
        view["report"][0][0] = True
        self.assertIsNone(view["report"][1][0])
        self.assertIsNone(result.report[0][0])
        with self.assertRaises(CoreProtocolError): component._stored_result(stored)
        with self.assertRaises(CoreProtocolError): component._result_bytes(value, coupled=False, paired_export=True)
        api, constructor, request = self.clients()[1]
        payload = {"request": request, "candidate": {}, "limits": self.fixture["limits"], "report": value}
        with self.assertRaises(CoreProtocolError):
            constructor(InertTransport())._call("replay-policy-quantitative-assurance", payload, cancelled=None)

    def test_expanded_hash_is_exact_and_legacy_hash_remains_bounded(self):
        value = {"left": large_tree(), "right": large_tree()}
        digest = hashlib.sha256(wire.canonical_bytes(value)).hexdigest()
        self.assertEqual(component._document_pin(digest, value, "Original"), digest)
        with self.assertRaises(CoreProtocolError): material._pin(digest, value, "Original")
        value["left"][0][0] = True
        with self.assertRaises(CoreProtocolError): component._document_pin(digest, value, "Original")

    def test_expanded_artifact_validation_retains_every_original_and_exact_molecule(self):
        request = old.original()
        candidate = old.candidate(request)
        limits = old.fixture()["limits"]
        report = {"status": "checked_material", "witness": large_tree()}
        # Two individually bounded originals exceed the ordinary whole-manifest
        # node limit together. This tests transport identity, not native proof.
        request["retained_witness"] = large_tree()
        digest = lambda value: hashlib.sha256(wire.canonical_bytes(value)).hexdigest()
        with patch.object(old, "digest", side_effect=digest):
            artifact = old.artifact(request, candidate, limits, report)
        arguments = {"operation": "export-policy-material", "request": request,
                     "candidate": candidate, "report": report, "limits": limits}
        with self.assertRaises(CoreProtocolError): material._artifact(artifact, **arguments)
        material._artifact(artifact, **arguments, document_encoder=wire.canonical_bytes)
        artifact["manifest"]["request"]["retained_witness"][0][0] = True
        artifact["manifest_sha256"] = digest(artifact["manifest"])
        with self.assertRaises(CoreProtocolError):
            material._artifact(artifact, **arguments, document_encoder=wire.canonical_bytes)


if __name__ == "__main__":
    unittest.main()

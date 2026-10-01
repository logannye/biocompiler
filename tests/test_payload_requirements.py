"""Source meaning, declared-contract graphs and independent execution regressions."""

from dataclasses import replace
import unittest
from unittest.mock import patch

import biocompiler as bc
from biocompiler.compiler.request import BuildRequest
from biocompiler.errors import SerializationError, UnsupportedBehaviorError
from biocompiler.ir.circuit_logic import CircuitSignal
from biocompiler.models.synthetic import ModelInputFrame, run_model
from biocompiler.semantics.payload_requirements import (
    PayloadRequirements, derive_boolean_response, extract_payload_requirements,
    validate_boolean_mapping,
)
from biocompiler.semantics.types import ProductionRate


def author(name="payload_source"):
    therapy = bc.Therapy(name)
    cell = therapy.engineer("recipient", cell_type="declared human T cell")
    return therapy, cell


def mapped_frames(report, frames):
    result = []
    for frame in frames:
        values, contacts = {}, {identity: {} for identity in frame.contacts}
        for binding in report.observation_map.inputs:
            node = report.behavior.get(binding.signal_id)
            if node.contact_bound:
                for identity, samples in frame.contacts.items():
                    contacts[identity][binding.mechanism_input_id] = getattr(samples[binding.signal_id], binding.field)
            else:
                values[binding.mechanism_input_id] = getattr(frame.signals[binding.signal_id], binding.field)
        result.append(ModelInputFrame(frame.time, values, contacts))
    return result


def timeline(report, frames, until):
    model = run_model(report.mechanism, mapped_frames(report, frames), until=until)
    source = bc.evaluate(report.behavior, frames, until=until)
    output = report.outputs[0]
    actual = [(frame.time, frame.values[output.id]) for frame in model.frames]
    expected = [(frame.time, any(action.rule_id == output.rule_id
                                 and action.specification_id == output.action_id
                                 for action in frame.actions)) for frame in source.frames]
    return actual, expected


class PayloadRequirementsTests(unittest.TestCase):
    def test_complete_source_and_multiple_distinct_output_meanings(self):
        therapy, cell = author()
        first, second = cell.internal.signal("A"), cell.internal.signal("B")
        cell.when(first.present() & ~second.present()).do(
            cell.secrete("artificial_product_A"), cell.secrete("artificial_product_B"), cell.rest())
        request = BuildRequest.freeze(therapy.freeze())
        report = extract_payload_requirements(request)
        self.assertEqual(report.source.to_dict(), request.to_dict())
        self.assertEqual(report.build_request.target, request.target)
        self.assertEqual(len(report.outputs), 3)
        self.assertEqual({item.product for item in report.outputs}, {None, "artificial_product_A", "artificial_product_B"})
        self.assertEqual(len(report.mechanism.outputs), 3)
        self.assertEqual(len(report.observation_map.outputs), 3)
        self.assertEqual(report.diagnostics, ())
        self.assertEqual({item["id"] for item in report.requirements},
                         {"source:" + node.id for node in request.intent.nodes} | {"source:complete_authority"})
        for output in report.outputs:
            self.assertEqual(output.semantics["primitive_action"]["kind"], output.action_kind)
            self.assertIn(output.action_id, output.lineage)
            self.assertIn(output.guard_id, output.lineage)
        self.assertEqual(PayloadRequirements.from_json(report.to_json()).fingerprint, report.fingerprint)
        with self.assertRaises(TypeError):
            report.outputs[0].semantics["action"]["kind"] = "action.rest"

    def test_import_is_structural_and_never_calls_producer(self):
        therapy, cell = author()
        cell.when(cell.internal.signal("A").present()).do(cell.rest())
        report = extract_payload_requirements(BuildRequest.freeze(therapy.freeze()))
        with patch("biocompiler.semantics.payload_requirements.extract_payload_requirements",
                   side_effect=AssertionError("producer invoked during import")):
            restored = PayloadRequirements.from_json(report.to_json())
        self.assertEqual(restored, report)

    def test_source_and_table_contradiction_rejected_and_no_band_complements_inferred(self):
        therapy, cell = author()
        first, second = cell.internal.signal("A"), cell.internal.signal("B")
        cell.when(first.high() | second.high()).do(cell.rest())
        request = BuildRequest.freeze(therapy.freeze())
        rule = request.intent.find(kind="rule")[0]
        a, b = CircuitSignal("A", "a" * 64), CircuitSignal("B", "b" * 64)
        bindings = {first.node_id: a, second.node_id: b}
        expected = derive_boolean_response(request, rule.id, bindings)
        self.assertEqual(expected.outputs, (False, True, True, True))
        self.assertEqual(validate_boolean_mapping(request, rule.id, bindings, a | b), expected)
        with self.assertRaisesRegex(SerializationError, "contradicts"):
            validate_boolean_mapping(request, rule.id, bindings, a & b)
        with self.assertRaisesRegex(SerializationError, "Missing explicit"):
            derive_boolean_response(request, rule.id, {first.node_id: a})

    def test_mixed_bands_have_independent_predicate_bindings(self):
        therapy, cell = author()
        signal = cell.internal.signal("A")
        cell.when(signal.high() | signal.low()).do(cell.rest())
        request = BuildRequest.freeze(therapy.freeze())
        rule = request.intent.find(kind="rule")[0]
        a, b = CircuitSignal("HIGH", "a" * 64), CircuitSignal("LOW", "b" * 64)
        with self.assertRaisesRegex(SerializationError, "Mixed qualitative"):
            derive_boolean_response(request, rule.id, {signal.node_id: a})
        predicates = request.intent.find(kind="qualitative")
        result = derive_boolean_response(request, rule.id, {predicates[0].id: a, predicates[1].id: b})
        self.assertEqual(result.outputs, (False, True, True, True))

    def test_guard_and_product_edits_change_graph_or_action_contract(self):
        reports = []
        for negated, product in ((False, "product_A"), (True, "product_A"), (False, "product_B")):
            therapy, cell = author()
            condition = cell.internal.signal("A").present()
            cell.when(~condition if negated else condition).do(cell.secrete(product))
            reports.append(extract_payload_requirements(BuildRequest.freeze(therapy.freeze())))
        self.assertNotEqual(reports[0].mechanism.fingerprint, reports[1].mechanism.fingerprint)
        self.assertNotEqual(reports[0].outputs[0].fingerprint, reports[2].outputs[0].fingerprint)
        self.assertNotEqual(reports[0].fingerprint, reports[2].fingerprint)

    def test_bound_duration_and_source_shutdown_are_preserved(self):
        therapy, cell = author()
        delay = therapy.parameter("delay", type=bc.Duration)
        ready, shutdown = cell.internal.signal("ready"), cell.internal.signal("shutdown")
        cell.when(ready.present().held_for(delay) & ~shutdown.present()).do(cell.secrete("artificial_product"))
        request = BuildRequest.freeze(therapy.freeze(), parameters={"delay": bc.Duration(2)})
        report = extract_payload_requirements(request)
        frames = (
            bc.InputFrame(0, {ready.node_id: bc.SignalSample(present=True), shutdown.node_id: bc.SignalSample(present=False)}),
            bc.InputFrame(3, {ready.node_id: bc.SignalSample(present=True), shutdown.node_id: bc.SignalSample(present=True)}),
        )
        actual, expected = timeline(report, frames, 4)
        self.assertEqual(actual, expected)
        self.assertEqual(actual, [(0, False), (2, True), (3, False), (4, False)])
        self.assertEqual(report.mechanism.find("held_for")[0].attributes["duration"]["canonical_value"], 2)
        rule = request.intent.find(kind="rule")[0]
        with self.assertRaises(UnsupportedBehaviorError):
            derive_boolean_response(request, rule.id, {})

    def test_memory_set_reset_expiry_priorities_match_reference_execution(self):
        therapy, cell = author()
        setting, resetting = cell.internal.signal("set"), cell.internal.signal("reset")
        memory = cell.memory("latched", set_when=setting.present(), reset_when=resetting.present(), duration=bc.Duration(2))
        cell.when(memory.is_set()).do(cell.secrete("artificial_latched_product"))
        report = extract_payload_requirements(BuildRequest.freeze(therapy.freeze()))
        for simultaneous_reset in (False, True):
            frames = tuple(bc.InputFrame(time, {
                setting.node_id: bc.SignalSample(present=value),
                resetting.node_id: bc.SignalSample(present=reset),
            }) for time, value, reset in ((0, True, False), (1, False, False),
                                        (2, True, simultaneous_reset), (3, True, False), (4, False, False)))
            actual, expected = timeline(report, frames, 5)
            self.assertEqual(actual, expected)
            self.assertEqual(dict(actual)[2], not simultaneous_reset)

    def test_contact_memory_onset_precedes_aggregation_and_refreshes(self):
        therapy, cell = author()
        setting = cell.contact.marker("A")
        memory = cell.memory("latched", set_when=setting.present(), duration=bc.Duration(2))
        cell.when(memory.is_set()).do(cell.rest())
        report = extract_payload_requirements(BuildRequest.freeze(therapy.freeze()))
        sample = {setting.node_id: bc.SignalSample(present=True)}
        frames = (bc.InputFrame(0, contacts={"a": sample}),
                  bc.InputFrame(1, contacts={"a": sample, "b": sample}))
        actual, expected = timeline(report, frames, 4)
        self.assertEqual(actual, expected)
        self.assertEqual(actual, [(0, True), (1, True), (3, False), (4, False)])

    def test_cell_pulse_aggregation_precedes_onset_new_contact_does_not_retrigger(self):
        therapy, cell = author()
        signal = cell.contact.marker("A")
        cell.when(signal.present()).do(cell.rest().for_(bc.Duration(2)))
        report = extract_payload_requirements(BuildRequest.freeze(therapy.freeze()))
        sample = {signal.node_id: bc.SignalSample(present=True)}
        frames = (bc.InputFrame(0, contacts={"a": sample}),
                  bc.InputFrame(1, contacts={"a": sample, "b": sample}))
        actual, expected = timeline(report, frames, 4)
        self.assertEqual(actual, expected)
        self.assertEqual(actual, [(0, True), (1, True), (2, False), (4, False)])

    def test_event_pulse_has_exact_duration_without_stateless_collapse(self):
        therapy, cell = author()
        signal = cell.internal.signal("A")
        cell.on(signal.present().became_true()).do(cell.rest().for_(bc.Duration(2)))
        report = extract_payload_requirements(BuildRequest.freeze(therapy.freeze()))
        frames = (bc.InputFrame(0, {signal.node_id: bc.SignalSample(present=True)}),)
        actual, expected = timeline(report, frames, 3)
        self.assertEqual(actual, expected)
        self.assertEqual(actual, [(0, True), (2, False), (3, False)])

    def test_quantitative_rate_is_retained_and_cannot_claim_boolean_implementation(self):
        therapy, cell = author()
        cell.when(cell.internal.signal("A").present()).do(cell.secrete("artificial_product", rate=ProductionRate(2)))
        report = extract_payload_requirements(BuildRequest.freeze(therapy.freeze()))
        self.assertIsNotNone(report.behavior)
        self.assertIsNone(report.mechanism)
        self.assertTrue(any("Quantitative" in item.message for item in report.unsupported))
        self.assertEqual(report.outputs[0].semantics["primitive_action"]["attributes"]["rate"], "expression")

    def test_unused_state_is_explicitly_retained_unsupported(self):
        therapy, cell = author()
        state = cell.state("future", values=("idle", "ready"), initial="idle")
        cell.when(cell.internal.signal("A").present()).do(cell.rest())
        report = extract_payload_requirements(BuildRequest.freeze(therapy.freeze()))
        self.assertIsNotNone(report.mechanism)
        self.assertTrue(any(item.code == "unrepresented_source_operation" and state.node_id in item.source_node_ids
                            for item in report.unsupported))
        self.assertIn("source:" + state.node_id, {item["id"] for item in report.requirements})

    def test_unknown_source_operation_retains_complete_original_authority(self):
        therapy, cell = author()
        cell.when(cell.internal.signal("A").present()).do(cell.rest())
        request = BuildRequest.freeze(therapy.freeze())
        rule = request.intent.find(kind="rule")[0]
        changed = replace(request, intent=replace(request.intent, nodes=tuple(
            replace(node, kind="future_rule") if node.id == rule.id else node for node in request.intent.nodes)))
        report = extract_payload_requirements(changed)
        self.assertIsNone(report.behavior)
        self.assertIsNone(report.mechanism)
        self.assertEqual(report.source.to_dict(), changed.to_dict())
        self.assertTrue(any(rule.id in item.source_node_ids for item in report.unsupported))

    def test_circuit_supplementary_and_table_cannot_override_source_or(self):
        from test_circuit_intent_checking import mapped_product_request
        with self.assertRaisesRegex(SerializationError, "contradicts"):
            extract_payload_requirements(mapped_product_request())


    def test_scoped_retention_keeps_target_authority_but_is_explicitly_unsupported(self):
        for location in ("environment", "internal"):
            therapy, cell = author()
            action = cell.retain(getattr(cell, location))
            cell.when(cell.internal.signal("A").present()).do(action)
            report = extract_payload_requirements(BuildRequest.freeze(therapy.freeze()))
            self.assertIsNone(report.mechanism)
            self.assertTrue(any("Scope-valued retention" in item.message for item in report.unsupported))
            self.assertTrue(any(action.node_id in item.source_node_ids for item in report.unsupported))
            primitive = report.outputs[0].semantics["primitive_action"]
            target = next(item for item in report.outputs[0].semantics["dependencies"]
                          if item["id"] == primitive["inputs"][1])
            self.assertEqual(target["attributes"]["scope"], location)
        therapy, cell = author()
        cell.when(cell.internal.signal("A").present()).do(cell.retain("declared_location"))
        literal = extract_payload_requirements(BuildRequest.freeze(therapy.freeze()))
        self.assertIsNotNone(literal.mechanism)
        self.assertEqual(literal.outputs[0].semantics["primitive_action"]["attributes"]["location"], "declared_location")

    def test_unused_impulse_and_scope_action_requirements_cannot_disappear(self):
        therapy, cell = author()
        report_action = cell.report("uninstalled_request")
        scope_action = cell.retain(cell.environment)
        cell.when(cell.internal.signal("A").present()).do(cell.rest(), report_action, scope_action)
        frozen = therapy.freeze()
        # Imported source may retain declarations which no rule currently uses;
        # retain those records while uninstalling both extra actions explicitly.
        frozen = replace(frozen, nodes=tuple(replace(node, inputs=node.inputs[:3])
                                             if node.kind == "rule" else node for node in frozen.nodes))
        report = extract_payload_requirements(BuildRequest.freeze(frozen))
        self.assertIsNotNone(report.mechanism)
        unsupported = {ref for item in report.unsupported for ref in item.source_node_ids}
        self.assertTrue({report_action.node_id, scope_action.node_id} <= unsupported)


class PayloadDependencyGroundingTests(unittest.TestCase):
    """Declared prerequisites must have a finite grounded explanation."""

    def check_dependencies(self, declarations, providers=(), host_capabilities=()):
        from types import SimpleNamespace
        from biocompiler.compiler.executable_payload import _connections_and_dependencies
        from biocompiler.ir.component_contracts import DependencyRequirement, ProvidedCapability
        from biocompiler.semantics.context import PayloadFormat

        selected = {
            identity: SimpleNamespace(component=SimpleNamespace(
                capabilities=tuple(ProvidedCapability(cap, "recipient", "cell", "cytoplasm") for cap in supplied),
                dependencies=tuple(DependencyRequirement(cap, cap, "recipient", "cell", "cytoplasm") for cap in needed)))
            for identity, supplied, needed in declarations
        }
        target = SimpleNamespace(payload_format=PayloadFormat.RNA, compartments=("cytoplasm",),
                                 capabilities=host_capabilities)
        return _connections_and_dependencies(selected, SimpleNamespace(nodes=()),
                                             SimpleNamespace(providers=providers), target)

    def test_alternative_provider_avoids_greedy_cycle(self):
        # A lexicographically first provider of X depends on Y; the later
        # provider supplies X without a prerequisite and grounds both peers.
        self.assertEqual(self.check_dependencies((
            ("a_cyclic", ("X",), ("Y",)),
            ("b_consumer", ("Y",), ("X",)),
            ("z_grounded", ("X",), ()),
        )), ())

    def test_self_supply_and_mutual_cycles_cannot_bootstrap(self):
        self.assertIn("ungrounded_dependency:self:X", self.check_dependencies((("self", ("X",), ("X",)),)))
        reasons = self.check_dependencies((("first", ("X",), ("Y",)), ("second", ("Y",), ("X",))))
        self.assertEqual(set(reasons), {"ungrounded_dependency:first:Y", "ungrounded_dependency:second:X"})
        self.assertEqual(self.check_dependencies((("consumer", (), ("missing",)),)),
                         ("missing_dependency:consumer:missing",))

    def test_external_provider_prerequisites_and_host_capability_are_required(self):
        from biocompiler.ir.component_contracts import ProvidedCapability
        from biocompiler.ir.composition import Provider

        capability = ProvidedCapability("X", "recipient", "cell", "cytoplasm")
        host = Provider("host", "host", (capability,), ("RNA",))
        self.assertTrue(self.check_dependencies((("consumer", (), ("X",)),), (host,)))
        self.assertEqual(self.check_dependencies((("consumer", (), ("X",)),), (host,), ("X",)), ())
        external = Provider("external", "external", (capability,), ("RNA",), ("base",))
        base = Provider("base", "external", (), ("RNA",))
        self.assertEqual(self.check_dependencies((("consumer", (), ("X",)),), (external, base)), ())
        circular_base = replace(base, depends_on=("external",))
        self.assertTrue(self.check_dependencies((("consumer", (), ("X",)),), (external, circular_base)))


if __name__ == "__main__":
    unittest.main()

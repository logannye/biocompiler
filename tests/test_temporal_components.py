"""Temporal component contracts and execution from actual assembly contents."""

from dataclasses import replace
import unittest
from unittest.mock import patch

import biocompiler as bc
from biocompiler.compiler.components import (
    check_component_assembly, check_component_behavior, run_component_pipeline,
)
from biocompiler.compiler.pipeline import PipelineError
from biocompiler.ir.component_assembly import ComponentAssembly
from biocompiler.ir.component_contracts import (
    ComponentRecord, SyntheticOperatorModel, PinnedIdentity,
)
from biocompiler.ir.serialization import fingerprint
from biocompiler.models.components import (
    COMPONENT_MODEL_VERSION, reconstruct_component_mechanism, run_component_model,
)
from biocompiler.models.synthetic import MODEL_RUNNER_VERSION, ModelInputFrame
from biocompiler.semantics.component_contracts import (
    TEMPORAL_EVENT_TIMING, TEMPORAL_LEVEL_TIMING, ports_compatible,
    OperatingDomain, PortContract, ValueDomain, canonical_synthetic_unit,
)
from biocompiler.semantics.types import BOOLEAN, DURATION
from biocompiler.verification.components import check_composition
from examples.temporal_pipeline import build_request
from test_temporal_generation import temporal_config, cell_model, freeze


def relock(assembly, records, *, connections=None):
    registry = replace(assembly.registry, components=tuple(records.values()))
    lock = registry.lock(records)
    locks = {item.node_id: item for item in lock.components}
    composition = replace(
        assembly.composition, registry_lock=lock,
        instances=tuple(replace(item, component=locks[item.id])
                        for item in assembly.composition.instances),
        connections=assembly.composition.connections if connections is None else connections,
    )
    return replace(assembly, registry=registry, composition=composition)


def mapped(assembly, request, frames):
    domains = {(item.signal_id, item.field): item for item in request.domain.inputs}
    result = []
    for frame in frames:
        values, contacts = {}, {identity: {} for identity in frame.contacts}
        for binding in assembly.observation_map.inputs:
            domain = domains[binding.signal_id, binding.field]
            if domain.scope == "cell":
                values[binding.mechanism_input_id] = getattr(
                    frame.signals[binding.signal_id], binding.field)
            else:
                for identity, samples in frame.contacts.items():
                    contacts[identity][binding.mechanism_input_id] = getattr(
                        samples[binding.signal_id], binding.field)
        result.append(ModelInputFrame(frame.time, values, contacts))
    return result


class TemporalComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request, cls.history = build_request()
        cls.build = run_component_pipeline(
            cls.request, cls.history, until=9, config=temporal_config())

    def test_temporal_pipeline_completes_components_with_two_distinct_checks(self):
        build = self.build
        self.assertEqual(build.result.scope, "synthetic_components")
        self.assertEqual(build.result.status.value, "complete")
        self.assertTrue(build.link_result.passed and build.behavior_result.passed)
        self.assertEqual([item.id for item in build.result.unresolved], ["molecular_behavior"])
        self.assertEqual(build.assembly.observation_map, build.candidate.observation_map)
        self.assertEqual(
            build.behavior_result.dependencies.values["settings"]["component_reconstruction"],
            COMPONENT_MODEL_VERSION,
        )
        self.assertNotEqual(
            reconstruct_component_mechanism(build.assembly).fingerprint,
            build.candidate.mechanism.fingerprint,
        )
        restored = ComponentAssembly.from_json(build.assembly.to_json())
        self.assertEqual(restored.fingerprint, build.assembly.fingerprint)
        self.assertTrue(check_component_assembly(
            self.request, build.candidate, restored, iter(self.history), until=9).passed)

    def test_reconstruction_and_model_execution_never_call_source_adapter_or_evaluator(self):
        with (
            patch("biocompiler.synthesis.components.adapt_synthetic_components",
                  side_effect=AssertionError("source adapter called")),
            patch("biocompiler.semantics.evaluator.evaluate",
                  side_effect=AssertionError("behavior evaluator called")),
        ):
            trace = run_component_model(
                self.build.assembly, mapped(self.build.assembly, self.request, self.history),
                until=9,
            )
        self.assertEqual(trace.frames[-1].time, 9)
        self.assertTrue(any(any(frame.values.values()) for frame in trace.frames))

    def test_rehashed_changed_durations_affect_actual_execution_and_fail_behavior(self):
        original = self.build.assembly
        for operation, duration in (("held_for", 3), ("pulse", 1), ("memory", 0.5)):
            records = original.registry.resolve(original.composition.registry_lock)
            identity = next(key for key, record in records.items()
                            if record.implementation_role == operation)
            record = records[identity]
            model = replace(record.synthetic_model,
                            attributes={"duration": bc.Duration(duration).to_dict()})
            records[identity] = replace(record, synthetic_model=model)
            changed = relock(original, records)
            with self.subTest(operation=operation):
                self.assertTrue(check_composition(changed.composition, changed.registry).passed)
                self.assertEqual(check_component_behavior(
                    self.request, changed, self.history, until=9).outcome, bc.CheckOutcome.FAIL)
                with self.assertRaisesRegex(PipelineError, "source correspondence"):
                    check_component_assembly(
                        self.request, self.build.candidate, changed, self.history, until=9)

    def test_actual_rewired_output_fails_independent_behavior_despite_compatible_ports(self):
        assembly = self.build.assembly
        records = assembly.registry.resolve(assembly.composition.registry_lock)
        output = assembly.observation_map.outputs[0].mechanism_output_id
        inactive = next(key for key in records if key.startswith("inactive:"))
        output_record = records[output]
        records[output] = replace(output_record, ports=tuple(
            replace(records[inactive].port("out"), id=port.id, direction="input")
            if port.direction == "input" else port for port in output_record.ports
        ))
        connections = tuple(replace(edge, producer_instance=inactive)
                            if edge.consumer_instance == output else edge
                            for edge in assembly.composition.connections)
        changed = relock(assembly, records, connections=connections)
        self.assertTrue(check_composition(changed.composition, changed.registry).passed)
        self.assertEqual(check_component_behavior(
            self.request, changed, self.history, until=9).outcome, bc.CheckOutcome.FAIL)

    def test_event_level_confusion_and_false_initial_hold_are_rejected(self):
        records = self.build.assembly.registry.resolve(self.build.assembly.composition.registry_lock)
        onset = next(record for record in records.values() if record.implementation_role == "onset")
        event = onset.port("out")
        self.assertEqual(event.timing, TEMPORAL_EVENT_TIMING)
        level_input = replace(event, direction="input", timing=TEMPORAL_LEVEL_TIMING)
        self.assertEqual(ports_compatible(event, level_input).status, "fail")
        with self.assertRaisesRegex(bc.SerializationError, "event/level"):
            replace(onset, ports=tuple(replace(port, timing=TEMPORAL_LEVEL_TIMING)
                                      if port.id == "out" else port for port in onset.ports))
        memory = next(record for record in records.values() if record.implementation_role == "memory")
        with self.assertRaisesRegex(bc.SerializationError, "event/level"):
            replace(memory, synthetic_model=replace(memory.synthetic_model,
                                                   input_ports=tuple(reversed(memory.synthetic_model.input_ports))))
        dwell = next(record for record in records.values() if record.implementation_role == "held_for")
        self.assertEqual(dwell.port("out").initialization.values, (False,))
        self.assertEqual(dwell.port("out").domain.values, (False, True))
        # This fixture sets memory only through a fresh held_for timer, which
        # cannot already qualify at startup. Other memory controls can set at 0.
        self.assertEqual(memory.port("out").initialization.values, (False,))

    def test_startup_memory_contact_loss_and_reset_have_literal_output_timeline(self):
        therapy, cell = cell_model("component_startup_memory")
        signal, reset = cell.contact.marker("set"), cell.environment.signal("reset")
        memory = cell.memory("latched", set_when=signal.present(), reset_when=reset.present())
        action = cell.rest()
        rule = cell.when(memory.is_set()).do(action)
        request = freeze(therapy, cell, ((signal, "contact"), (reset, "cell")),
                         (("remembered", rule, action, "cell"),))
        frames = (
            bc.InputFrame(0, {reset.node_id: bc.SignalSample(present=False)},
                          {"x": {signal.node_id: bc.SignalSample(present=True)}}),
            bc.InputFrame(1, {reset.node_id: bc.SignalSample(present=False)}),
            bc.InputFrame(2, {reset.node_id: bc.SignalSample(present=True)}),
        )
        build = run_component_pipeline(request, frames, until=3, config=temporal_config())
        trace = run_component_model(build.assembly, mapped(build.assembly, request, frames), until=3)
        output = build.assembly.observation_map.outputs[0].mechanism_output_id
        self.assertEqual([(frame.time, frame.values[output]) for frame in trace.frames],
                         [(0, 1), (1, 1), (2, 0), (3, 0)])

    def test_reset_set_and_expiry_precedence_survive_component_reconstruction(self):
        therapy, cell = cell_model("component_memory_priority")
        signal, reset = cell.environment.signal("set"), cell.environment.signal("reset")
        memory = cell.memory("latched", set_when=signal.present(),
                             reset_when=reset.present(), duration=bc.Duration(2))
        action = cell.rest()
        rule = cell.when(memory.is_set()).do(action)
        request = freeze(therapy, cell, ((signal, "cell"), (reset, "cell")),
                         (("remembered", rule, action, "cell"),))
        for reset_at_expiry in (False, True):
            frames = tuple(bc.InputFrame(time, {
                signal.node_id: bc.SignalSample(present=setting),
                reset.node_id: bc.SignalSample(present=resetting),
            }) for time, setting, resetting in (
                (0, True, False), (1, False, False), (2, True, reset_at_expiry),
                (3, True, False), (4, False, False),
            ))
            with self.subTest(reset_at_expiry=reset_at_expiry):
                build = run_component_pipeline(request, frames, until=5, config=temporal_config())
                trace = run_component_model(build.assembly,
                                            mapped(build.assembly, request, frames), until=5)
                output = build.assembly.observation_map.outputs[0].mechanism_output_id
                expected = 0 if reset_at_expiry else 1
                self.assertEqual([(frame.time, frame.values[output]) for frame in trace.frames],
                                 [(0, 1), (1, 1), (2, expected), (3, expected), (4, 0), (5, 0)])

    def test_missing_models_and_bindings_cannot_execute_or_link_as_known_dynamics(self):
        assembly = self.build.assembly
        records = assembly.registry.resolve(assembly.composition.registry_lock)
        identity = next(key for key, record in records.items()
                        if record.implementation_role == "memory")
        records[identity] = replace(records[identity], synthetic_model=None)
        changed = relock(assembly, records)
        self.assertEqual(check_composition(changed.composition, changed.registry).outcome,
                         bc.CheckOutcome.UNKNOWN)
        with self.assertRaisesRegex(bc.SerializationError, "lacks an executable"):
            reconstruct_component_mechanism(changed)
        with self.assertRaisesRegex(bc.SerializationError, "every executable input"):
            reconstruct_component_mechanism(replace(
                assembly, observation_map=replace(assembly.observation_map, inputs=())))
        with self.assertRaisesRegex(bc.SerializationError, "every executable output"):
            reconstruct_component_mechanism(replace(
                assembly, observation_map=replace(assembly.observation_map, outputs=())))

    def test_new_dependencies_invalidate_component_acceptance(self):
        build = run_component_pipeline(self.request, self.history, until=9, config=temporal_config())
        build.manager.set_dependency("component_model", fingerprint("changed reconstructor"))
        with self.assertRaisesRegex(PipelineError, "Stale"):
            build.manager.result("components", scope="synthetic_components")

    def test_operator_identity_and_schema_are_strict_immutable_and_versioned(self):
        records = self.build.assembly.registry.components
        record = next(item for item in records if item.implementation_role == "held_for")
        self.assertEqual(ComponentRecord.from_json(record.to_json()), record)
        with self.assertRaises(TypeError):
            record.synthetic_model.attributes["duration"]["canonical_value"] = 9
        for modification in (
            {"extra": True}, {"policy": "future"}, {"operation": "eval"},
            {"input_ports": ["in:0", "in:0"]}, {"schema_version": "future"},
        ):
            with self.subTest(modification=modification), self.assertRaises(bc.SerializationError):
                SyntheticOperatorModel.from_dict({**record.synthetic_model.to_dict(), **modification})
        changed = replace(record, synthetic_model=replace(record.synthetic_model,
                          attributes={"duration": bc.Duration(4).to_dict()}))
        self.assertNotEqual(record.fingerprint, changed.fingerprint)
        assembly = self.build.assembly
        with self.assertRaises(bc.SerializationError):
            replace(assembly, registry=replace(assembly.registry, components=tuple(
                changed if item.id == record.id else item for item in records)))
        with self.assertRaises(bc.SerializationError):
            ComponentAssembly.from_dict({**assembly.to_dict(),
                                         "schema_version": "biocompiler.component_assembly.v0.1"})

    def test_executable_units_are_canonical_without_restricting_generic_contracts(self):
        domain = ValueDomain.interval(0, 10, DURATION, "s")
        port = PortContract("out", "output", "clock", DURATION, "s", "observer",
                            "cell", "abstract", TEMPORAL_LEVEL_TIMING, domain, domain)
        record = ComponentRecord(
            "clock", "1", "synthetic_model", "input", ("RNA",), (port,),
            OperatingDomain(),
            (PinnedIdentity("model", "synthetic.program", MODEL_RUNNER_VERSION, "0" * 64),),
            synthetic_model=SyntheticOperatorModel("input"),
        )
        self.assertEqual(ComponentRecord.from_json(record.to_json()), record)
        self.assertEqual(canonical_synthetic_unit(DURATION), "s")
        self.assertEqual(canonical_synthetic_unit(BOOLEAN), "1")
        for unit in ("min", "minute", "invented-unit"):
            wrong_port = replace(port, unit=unit,
                                 domain=replace(domain, unit=unit),
                                 initialization=replace(domain, unit=unit))
            with self.subTest(unit=unit):
                with self.assertRaisesRegex(bc.SerializationError, "canonical units"):
                    replace(record, ports=(wrong_port,))
                # Ordinary declared contracts retain exact unit comparison;
                # the new restriction belongs only to executable digital models.
                generic = replace(record, synthetic_model=None, ports=(wrong_port,))
                self.assertEqual(generic.port("out").unit, unit)

        boolean = ValueDomain.boolean()
        boolean_port = replace(port, dtype=BOOLEAN, unit="1",
                               initialization=boolean, domain=boolean)
        self.assertEqual(replace(record, ports=(boolean_port,)).port("out").unit, "1")

    def test_relabeling_all_numeric_model_port_units_cannot_survive_import(self):
        from test_synthetic_generation import fixture
        from biocompiler.synthesis.synthetic import generate_synthetic
        from biocompiler.synthesis.components import adapt_synthetic_components

        request, sample = fixture(numeric=True)
        candidate = generate_synthetic(request)
        history = (
            bc.InputFrame(0, contacts={"x": sample(1, True)}),
            bc.InputFrame(1, contacts={"x": sample(3, True)}),
            bc.InputFrame(5, contacts={"x": sample(2, True)}),
        )
        adapted = adapt_synthetic_components(request, candidate, history, until=7)
        rejected = 0
        for record in adapted.registry.components:
            data = record.to_dict()
            changed = False
            for port in data["ports"]:
                if port["dtype"]["dimensions"]:
                    port["unit"] = "invented-unit"
                    port["domain"]["unit"] = "invented-unit"
                    port["initialization"]["unit"] = "invented-unit"
                    changed = True
            if changed:
                with self.subTest(record=record.id), self.assertRaisesRegex(
                    bc.SerializationError, "canonical units"
                ):
                    ComponentRecord.from_dict(data)
                rejected += 1
        self.assertGreater(rejected, 0)

    def test_fixed_startup_and_literal_guarantees_cannot_be_forged(self):
        records = self.build.assembly.registry.components
        for operation in ("held_for", "onset", "pulse", "memory"):
            record = next(item for item in records if item.implementation_role == operation)
            with self.subTest(operation=operation), self.assertRaisesRegex(
                bc.SerializationError, "exclude possible operator values"
            ):
                replace(record, ports=tuple(
                    replace(port, initialization=ValueDomain.boolean((True,)))
                    if port.direction == "output" else port for port in record.ports
                ))
        record = next(item for item in records if item.id.startswith("synthetic.instance:active:"))
        false_band = ValueDomain.interval(0, 0, record.port("out").dtype, "1")
        with self.assertRaisesRegex(bc.SerializationError, "exclude possible operator values"):
            replace(record, ports=(replace(record.port("out"), domain=false_band,
                                           initialization=false_band),))

    def test_boolean_runtime_guarantees_cannot_exclude_possible_outputs(self):
        record = next(item for item in self.build.assembly.registry.components
                      if item.implementation_role == "and")
        with self.assertRaisesRegex(bc.SerializationError, "exclude possible operator values"):
            replace(record, ports=tuple(
                replace(port, domain=ValueDomain.boolean((False,)),
                        initialization=ValueDomain.boolean((False,)))
                if port.direction == "output" else port for port in record.ports
            ))
        # Both false and true remain possible through ordinary Boolean logic;
        # neither a NOT nor OR record can claim it always returns false here.
        for operation, inputs in (("not", ("in:0",)), ("or", ("in:0", "in:1"))):
            ports = tuple(port for port in record.ports
                          if port.id in {*inputs, "out"})
            with self.subTest(operation=operation), self.assertRaisesRegex(
                bc.SerializationError, "exclude possible operator values"
            ):
                replace(record, implementation_role=operation,
                        synthetic_model=SyntheticOperatorModel(operation, input_ports=inputs),
                        ports=tuple(replace(port, domain=ValueDomain.boolean((False,)),
                                            initialization=ValueDomain.boolean((False,)))
                                    if port.direction == "output" else port for port in ports))

    def test_unknown_executable_guarantees_remain_unknown_in_behavior_acceptance(self):
        assembly = self.build.assembly
        records = assembly.registry.resolve(assembly.composition.registry_lock)
        identity = next(key for key, item in records.items()
                        if item.implementation_role == "held_for")
        record = records[identity]
        unknown = ValueDomain.unknown(BOOLEAN, "1", "unspecified guarantee")
        records[identity] = replace(record, ports=tuple(
            replace(port, domain=unknown, initialization=unknown)
            if port.direction == "output" else port for port in record.ports
        ))
        changed = relock(assembly, records)
        self.assertEqual(check_composition(changed.composition, changed.registry).outcome,
                         bc.CheckOutcome.UNKNOWN)
        self.assertEqual(check_component_behavior(self.request, changed, self.history, until=9).outcome,
                         bc.CheckOutcome.UNKNOWN)


if __name__ == "__main__":
    unittest.main()

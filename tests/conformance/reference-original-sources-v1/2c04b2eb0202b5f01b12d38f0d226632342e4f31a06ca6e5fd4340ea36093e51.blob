"""Automatically generated digital candidates must pass an independent checker."""

from dataclasses import replace
import itertools
import unittest

import biocompiler as bc
from biocompiler.compiler.request import BuildRequest, RealizationRequest
from biocompiler.registry.synthetic import SYNTHETIC_CATALOG
from biocompiler.semantics.types import BOOLEAN
from biocompiler.synthesis.synthetic import (
    SyntheticGeneratorConfig,
    check_synthetic_candidate,
    generate_synthetic,
)
from examples.realization_check import with_delay


def fixture(*, contact=False, temporal=False, numeric=False, negate=False):
    therapy = bc.Therapy("generated_fixture")
    cell = therapy.engineer("cell", cell_type="abstract_cell")
    a, b = cell.contact.marker("A"), cell.contact.marker("B")
    if numeric:
        condition = (a > bc.SurfaceDensity(2)) & b.present()
    else:
        condition = a.present() & (~b.present() if negate else b.present())
    if temporal is True or temporal == "held_for":
        condition = condition.held_for(bc.Duration(1))
    elif temporal == "recently":
        condition = condition.recently(within=bc.Duration(1))
    elif temporal == "memory":
        condition = cell.memory("observed", set_when=condition).is_set()
    elif temporal == "state":
        condition = condition & cell.state(
            "phase", values=("off", "on"), initial="off"
        ).is_("on")
    action = cell.eliminate(cell.contact) if contact else cell.rest()
    if temporal == "pulse":
        action = action.for_(bc.Duration(1))
    elif temporal == "became_true":
        condition = condition.became_true()
        action = action.for_(bc.Duration(1))
    rule = (
        cell.on(condition) if temporal == "became_true" else cell.when(condition)
    ).do(action)
    target = bc.TargetContext(
        "synthetic", "1", bc.PayloadFormat.RNA, capabilities=("synthetic_signal_graph",)
    )
    build = BuildRequest.freeze(
        therapy.freeze(), target=target, artifact_scope="synthetic_realization"
    )
    behavior = bc.lower_to_behavior(build)
    output = bc.Observable(
        "abstract_request", bc.Level, cell.role, scope="contact" if contact else "cell"
    )
    response = bc.ResponseRequirement(
        "response",
        rule.node_id,
        action.node_id,
        output,
        bc.Interval(0.9, 1.1),
        bc.Interval(0, 0.1),
        bc.Duration(0.5),
        bc.Duration(0.5),
    )
    contract = bc.BehaviorContract("contract", behavior.fingerprint, (response,))
    first = bc.InputDomain(
        a.node_id,
        "value" if numeric else "present",
        bc.Observable(
            "A", bc.SurfaceDensity if numeric else BOOLEAN, cell.role, scope="contact"
        ),
        bc.Interval(bc.SurfaceDensity(0), bc.SurfaceDensity(10), type=bc.SurfaceDensity)
        if numeric
        else (False, True),
    )
    second = bc.InputDomain(
        b.node_id,
        "present",
        bc.Observable("B", BOOLEAN, cell.role, scope="contact"),
        (False, True),
    )
    domain = bc.OperatingDomain(
        "two_contacts", "1", cell.role, (first, second), bc.Duration(7), max_contacts=2
    )
    request = RealizationRequest.freeze(build, behavior, contract, domain)

    def sample(first, second):
        return {
            a.node_id: bc.SignalSample(value=first)
            if numeric
            else bc.SignalSample(present=first),
            b.node_id: bc.SignalSample(present=second),
        }

    return request, sample


def exercised_history(sample):
    return (
        bc.InputFrame(0, contacts={"x": sample(True, False), "y": sample(False, True)}),
        bc.InputFrame(1, contacts={"x": sample(True, True), "y": sample(False, True)}),
        bc.InputFrame(
            5, contacts={"x": sample(False, False), "y": sample(False, False)}
        ),
    )


class SyntheticGenerationTests(unittest.TestCase):
    def setUp(self):
        self.request, self.sample = fixture()
        self.candidate = generate_synthetic(self.request)
        self.history = exercised_history(self.sample)

    def check(self, candidate=None, history=None, until=7):
        return check_synthetic_candidate(
            self.request,
            candidate or self.candidate,
            self.history if history is None else history,
            until=until,
        )

    def direct_check(self, request, mechanism, mapping, history, until=7):
        return bc.check_realization(
            request.behavior,
            request.contract,
            request.domain,
            request.target,
            mechanism,
            mapping,
            history,
            until=until,
        )

    def test_generated_candidate_passes_and_retains_requirements_and_sources(self):
        self.assertEqual(self.check().outcome, bc.CheckOutcome.PASS)
        self.assertEqual(self.candidate.request_fingerprint, self.request.fingerprint)
        carried = {
            item
            for values in self.candidate.behavior_requirement_ids.values()
            for item in values
        }
        self.assertEqual(
            carried, {item.id for item in self.request.behavior.requirements}
        )
        rule = self.request.contract.requirements[0].rule_id
        self.assertIn(
            rule, self.candidate.source_map[self.candidate.mechanism.outputs[0]]
        )
        self.assertEqual(
            self.candidate.component_locks,
            SYNTHETIC_CATALOG.lock(self.candidate.mechanism),
        )
        self.assertFalse(self.candidate.mechanism.find("delay"))

    def test_generation_and_serialization_are_deterministic(self):
        regenerated = generate_synthetic(
            RealizationRequest.from_json(self.request.to_json())
        )
        self.assertEqual(self.candidate.to_dict(), regenerated.to_dict())
        for artifact in (
            self.candidate,
            self.candidate.generator_config,
            SYNTHETIC_CATALOG,
        ):
            restored = type(artifact).from_json(artifact.to_json())
            self.assertEqual(restored.to_dict(), artifact.to_dict())
            self.assertEqual(restored.fingerprint, artifact.fingerprint)
        with self.assertRaises(TypeError):
            self.candidate.source_map["extra"] = ()

    def test_witness_levels_are_selected_from_authored_bands(self):
        constants = self.candidate.mechanism.find("constant")
        self.assertEqual(
            {item.attributes["value"]["canonical_value"] for item in constants},
            {0, 0.9},
        )
        self.assertEqual(
            self.candidate.generator_config.witness_selection,
            "closed_band_lower_endpoint",
        )

    def test_silent_generated_candidate_fails_independent_response_check(self):
        model = replace(
            self.candidate.mechanism,
            nodes=tuple(
                replace(node, inputs=("inactive:response",))
                if node.kind == "output"
                else node
                for node in self.candidate.mechanism.nodes
            ),
        )
        result = self.check(replace(self.candidate, mechanism=model))
        self.assertEqual(result.outcome, bc.CheckOutcome.FAIL)
        self.assertEqual(result.counterexamples[0].time, 1.5)

    def test_late_candidate_fails_exact_deadline(self):
        result = self.direct_check(
            self.request,
            with_delay(self.candidate.mechanism, 2),
            self.candidate.observation_map,
            self.history,
        )
        self.assertEqual(result.outcome, bc.CheckOutcome.FAIL)
        self.assertEqual(result.counterexamples[0].time, 1.5)

    def test_wrong_contact_aggregation_fails_on_split_objects(self):
        model = self.candidate.mechanism
        inputs = [
            item.mechanism_input_id for item in self.candidate.observation_map.inputs
        ]
        aggregate = model.find("any_contact")[0]
        extras = tuple(
            bc.MechanismNode(
                f"any{index}",
                "any_contact",
                bc.Observable(f"any{index}", BOOLEAN, self.request.domain.role),
                (ref,),
            )
            for index, ref in enumerate(inputs)
        )
        wrong = replace(
            model,
            nodes=tuple(
                replace(node, kind="and", inputs=("any0", "any1"))
                if node.id == aggregate.id
                else node
                for node in model.nodes
            )
            + extras,
        )
        result = self.direct_check(
            self.request, wrong, self.candidate.observation_map, self.history
        )
        self.assertEqual(result.outcome, bc.CheckOutcome.FAIL)
        self.assertEqual(result.counterexamples[0].expected["state"], "inactive")

    def test_contact_outputs_preserve_object_identity_and_reject_broadcast(self):
        request, sample = fixture(contact=True)
        candidate = generate_synthetic(request)
        history = exercised_history(sample)
        self.assertEqual(
            check_synthetic_candidate(request, candidate, history, until=7).outcome,
            bc.CheckOutcome.PASS,
        )
        selected = candidate.mechanism.find("select")[0]
        aggregate = bc.MechanismNode(
            "wrong_any",
            "any_contact",
            bc.Observable("wrong_any", BOOLEAN, request.domain.role),
            (selected.inputs[0],),
        )
        wrong = replace(
            candidate.mechanism,
            nodes=tuple(
                replace(node, inputs=(aggregate.id, *node.inputs[1:]))
                if node.id == selected.id
                else node
                for node in candidate.mechanism.nodes
            )
            + (aggregate,),
        )
        result = self.direct_check(request, wrong, candidate.observation_map, history)
        self.assertEqual(result.outcome, bc.CheckOutcome.FAIL)
        self.assertEqual(result.counterexamples[0].contact_id, "y")

    def test_wrongly_scoped_output_fails_endpoint_check(self):
        wrong = replace(
            self.candidate.mechanism,
            nodes=tuple(
                replace(node, output=replace(node.output, scope="contact"))
                if node.kind == "output"
                else node
                for node in self.candidate.mechanism.nodes
            ),
        )
        result = self.check(replace(self.candidate, mechanism=wrong))
        self.assertEqual(result.outcome, bc.CheckOutcome.FAIL)
        self.assertEqual(result.diagnostics[0].code, "output_endpoint")

    def test_temporal_and_state_operations_are_rejected_with_source_location(self):
        for operation in (
            "held_for",
            "recently",
            "memory",
            "state",
            "pulse",
            "became_true",
        ):
            with self.subTest(operation=operation):
                request, _ = fixture(temporal=operation)
                with self.assertRaises(bc.UnsupportedBehaviorError) as error:
                    generate_synthetic(request)
                self.assertIsNotNone(error.exception.node_id)
                self.assertIsNotNone(error.exception.source)

    def test_forged_candidate_cannot_hide_unsupported_source_profile(self):
        request, sample = fixture(temporal=True)
        forged = replace(self.candidate, request_fingerprint=request.fingerprint)
        result = check_synthetic_candidate(
            request, forged, exercised_history(sample), until=7
        )
        self.assertEqual(result.outcome, bc.CheckOutcome.UNSUPPORTED)
        self.assertEqual(result.diagnostics[0].code, "unsupported_generation_profile")

    def test_numeric_comparison_and_negation_have_independent_checks(self):
        request, sample = fixture(numeric=True)
        candidate = generate_synthetic(request)
        history = (
            bc.InputFrame(0, contacts={"x": sample(1, True)}),
            bc.InputFrame(1, contacts={"x": sample(3, True)}),
            bc.InputFrame(5, contacts={"x": sample(2, True)}),
        )
        self.assertEqual(
            check_synthetic_candidate(request, candidate, history, until=7).outcome,
            bc.CheckOutcome.PASS,
        )
        request, sample = fixture(negate=True)
        self.assertEqual(
            check_synthetic_candidate(
                request, generate_synthetic(request), exercised_history(sample), until=7
            ).outcome,
            bc.CheckOutcome.PASS,
        )

    def test_unexercised_and_short_histories_are_unknown(self):
        self.assertEqual(self.check(history=()).outcome, bc.CheckOutcome.UNKNOWN)
        inactive = (bc.InputFrame(0, contacts={"x": self.sample(False, False)}),)
        self.assertEqual(self.check(history=inactive).outcome, bc.CheckOutcome.UNKNOWN)
        self.assertEqual(self.check(until=1.2).outcome, bc.CheckOutcome.UNKNOWN)
        active = (bc.InputFrame(0, contacts={"x": self.sample(True, True)}),)
        result = self.check(history=active)
        self.assertEqual(result.outcome, bc.CheckOutcome.UNKNOWN)
        self.assertEqual(result.diagnostics[0].code, "unexercised_inactive_response")

    def test_changed_source_correspondence_cannot_establish_acceptance(self):
        source_map = dict(self.candidate.source_map)
        source_map[self.candidate.mechanism.outputs[0]] = (self.request.domain.role,)
        result = self.check(replace(self.candidate, source_map=source_map))
        self.assertEqual(result.outcome, bc.CheckOutcome.FAIL)
        self.assertEqual(result.diagnostics[0].code, "candidate_lineage")

    def test_startup_active_and_contact_removal_reappearance(self):
        history = (
            bc.InputFrame(0, contacts={"x": self.sample(True, True)}),
            bc.InputFrame(2, contacts={}),
            bc.InputFrame(3, contacts={"x": self.sample(False, False)}),
            bc.InputFrame(4, contacts={"x": self.sample(True, True)}),
            bc.InputFrame(6, contacts={"x": self.sample(False, False)}),
        )
        self.assertEqual(self.check(history=history).outcome, bc.CheckOutcome.PASS)

    def test_unknown_observations_and_unbounded_domain_are_rejected(self):
        first = self.request.domain.inputs[0]
        missing = replace(self.request.domain, inputs=self.request.domain.inputs[1:])
        with self.assertRaises(bc.UnsupportedBehaviorError):
            generate_synthetic(replace(self.request, domain=missing))
        unbounded = replace(self.request.domain, max_contacts=None)
        with self.assertRaises(bc.UnsupportedBehaviorError):
            generate_synthetic(replace(self.request, domain=unbounded))
        self.assertEqual(first.scope, "contact")

    def test_stale_component_lock_and_wrong_request_are_rejected(self):
        locks = list(self.candidate.component_locks)
        locks[0] = replace(locks[0], version="obsolete")
        result = self.check(replace(self.candidate, component_locks=locks))
        self.assertEqual(result.diagnostics[0].code, "candidate_component")
        wrong = replace(self.candidate, request_fingerprint="0" * 64)
        self.assertEqual(
            self.check(wrong).diagnostics[0].code, "candidate_request_identity"
        )
        with self.assertRaises(bc.SerializationError):
            SyntheticGeneratorConfig(catalog_fingerprint="0" * 64)

    def test_bounded_exhaustive_two_object_boolean_transitions(self):
        # All 16 four-bit input states followed by all 16 states. A separately
        # fixed active/inactive suffix exercises both response obligations.
        states = tuple(itertools.product((False, True), repeat=4))
        for left, right in itertools.product(states, repeat=2):
            frames = []
            for time, state in (
                (0, left),
                (2, right),
                (4, (True,) * 4),
                (6, (False,) * 4),
            ):
                frames.append(
                    bc.InputFrame(
                        time,
                        contacts={
                            "x": self.sample(*state[:2]),
                            "y": self.sample(*state[2:]),
                        },
                    )
                )
            result = self.check(history=frames, until=7)
            self.assertEqual(
                result.outcome, bc.CheckOutcome.PASS, (left, right, result.to_dict())
            )


if __name__ == "__main__":
    unittest.main()

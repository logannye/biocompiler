"""Original approximation authoring and independent fixture checks; no native proof."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
import hashlib
import json
import unittest

from biocompiler import policy as p
from biocompiler.core_client import CoreProtocolError
from biocompiler.policy import approximation as a, quantitative as q
from tools import generate_policy_approximation_fixture as generator
from tools import generate_policy_quantitative_network_fixture as previous


def target():
    return q.SampledTransferNetwork("fixture.reservoir.amount", p.COUNT, p.quantity(1, p.COUNT),
        (q.ReservoirCompartment("a", p.quantity(2, p.COUNT), p.quantity(2, p.COUNT)),
         q.ReservoirCompartment("b", p.quantity(2, p.COUNT), p.quantity(0, p.COUNT))),
        (q.TransferEdge("forward", "a", "b", p.quantity(2, p.COUNT), True),
         q.TransferEdge("reverse", "b", "a", p.quantity(2, p.COUNT), False)),
        "b", p.quantity(1, p.COUNT), p.quantity(1, p.SECOND))


def contract():
    actual = target()
    reference = replace(actual, transfers=(replace(actual.transfers[0], amount=p.quantity(1, p.COUNT)), actual.transfers[1]))
    source = a.ApproximationEndpoint(reference, ("a", "b"))
    endpoint = a.ApproximationEndpoint(actual, ("a", "b"))
    first = a.ApproximationLink("uncertain_reference", source, endpoint, a.RationalErrorBound(1, 1, p.COUNT),
        (a.ParameterInterval("transfer_amount", "forward", 1, 2), a.ParameterInterval("initial", "a", 1, 2)))
    last = a.ApproximationLink("exact_target", endpoint, endpoint, a.RationalErrorBound(0, 1, p.COUNT))
    return a.ApproximationContract(13, ("donor", "receiver"), first.then(last), a.RationalErrorBound(1, 1, p.COUNT))


def transport_fixture(packet):
    """Handwritten transport witness only; this does not substitute for native checking."""
    original = contract()
    request = deepcopy(packet["material_request"])
    digest = generator.shared.digest
    material = {"status": "checked_component_material", "request_fingerprint": digest(request),
        "assembly": {"candidate_fingerprint": "f" * 64}}
    rational = lambda value: a.RationalErrorBound(value, 1, p.COUNT).to_data()
    first_envelope = [{"round": index, "coordinates": [rational(1), rational(0 if index == 0 else 1)]} for index in range(14)]
    zero_envelope = [{"round": index, "coordinates": [rational(0), rational(0)]} for index in range(14)]
    scope = {"horizon_steps": 13, "metric": "coordinatewise_absolute_prefix_error", "coordinates": ["donor", "receiver"],
        "unit": p.to_data(p.COUNT), "sample_period": p.to_data(p.quantity(1, p.SECOND))}
    cases = [replace(original.chain.links[0].source.mechanism,
        transfers=(replace(target().transfers[0], amount=p.quantity(amount, p.COUNT)), target().transfers[1]),
        reservoirs=(replace(target().reservoirs[0], initial=p.quantity(initial, p.COUNT)), target().reservoirs[1]))
        for amount, initial in ((1, 1), (1, 2), (2, 1), (2, 2))]
    links = []
    for index, link in enumerate(original.chain.links):
        current_cases = cases if index == 0 else [target()]
        envelope = first_envelope if index == 0 else zero_envelope
        links.append({"id": link.id, "relation": "bounded_sampled_observation_error", "source_fingerprint": digest(link.source.to_data()),
            "target_fingerprint": digest(link.target.to_data()), "scope": deepcopy(scope),
            "uncertainty_cases": [{"mechanism_fingerprint": digest(law.to_data()), "visited_pair_rounds": 14, "checked_transition_rows": 104} for law in current_cases],
            "case_count": len(current_cases), "envelope": deepcopy(envelope), "coordinate_bounds": deepcopy(envelope[-1]["coordinates"]),
            "maximum_error": rational(1 if index == 0 else 0), "declared_maximum_error": link.maximum_error.to_data(),
            "request_labels": "exact_on_all_checked_synchronized_transitions"})
    selected = request["quantitative"]
    composition = {"relation": "conditional_approximate_source_material_correspondence", "rule": "monotone_triangle_error_chain_with_exact_material",
        "source_fingerprint": digest(original.chain.links[0].source.to_data()), "target_fingerprint": material["assembly"]["candidate_fingerprint"],
        "material_request_fingerprint": digest(request), "material_report_fingerprint": digest(material),
        "selected_mechanism_fingerprint": digest(selected["mechanism"]), "selection": deepcopy(selected["selection"]), "source": deepcopy(selected["source"]),
        "scope": dict(scope, operating_domain_fingerprint=digest(request["implementation_request"]["operating_domain"]),
            samples=["true", "false", "unknown", "no_update"], lifecycle="synchronized_reset_before_each_sample_or_keep",
            uncertainty="all_closed_grid_cases_fixed_within_each_encounter_generation"),
        "inputs": [digest(link) for link in links], "envelope": deepcopy(first_envelope), "coordinate_bounds": [rational(1), rational(1)],
        "maximum_error": rational(1), "declared_maximum_error": rational(1)}
    report = {"schema_version": "biocompiler.policy_approximation_assessment.v0.1", "profile": a.PROFILE,
        "implementation": "biocompiler.ocaml.policy_approximation_check.v0.1", "outcome": "pass",
        "contract_fingerprint": digest(original.to_data()), "material_request_fingerprint": digest(request), "material_report_fingerprint": digest(material),
        "claim_scope": "bounded_model_conditional_observation_error_and_exact_request_labels", "links": links, "composition": composition, "issues": [],
        "empirical": "unassessed", "artifact": "withheld", "export": "withheld", "usage": {"unit": "logical_data_visits_and_synchronized_product_work", "charged_work": 10000}}
    return report, original.to_data(), request, material


class ApproximationAuthoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(generator.PATH.read_text())

    def test_typed_contract_matches_independent_original_fixture(self):
        self.assertEqual(contract().to_data(), self.packet["approximation"])
        self.assertEqual(target().to_data(), self.packet["material_request"]["quantitative"]["mechanism"])
        self.assertEqual(generator.build(), self.packet)
        self.assertNotIn("ApproximationContract", p.schema()["$defs"])
        self.assertFalse(isinstance(contract(), p.Record))
        with self.assertRaises(FrozenInstanceError): contract().horizon_steps = 1

    def test_exact_rational_budget_has_no_decimal_rounding(self):
        bound = a.RationalErrorBound(2, 6, p.COUNT)
        self.assertEqual(bound.to_data(), {"numerator": "1", "denominator": "3", "unit": p.to_data(p.COUNT)})
        self.assertEqual(Fraction(bound.numerator, bound.denominator), Fraction(1, 3))
        self.assertEqual(a.RationalErrorBound(0, 32, p.COUNT).denominator, 1)
        for numerator, denominator in ((-1, 1), (1, 0), (True, 1), (1, False), (0.1, 1), (1, 1.0)):
            with self.assertRaises((ValueError, TypeError)): a.RationalErrorBound(numerator, denominator, p.COUNT)

    def test_complete_closed_uncertainty_grid_is_bounded_and_nominal(self):
        link = contract().chain.links[0]
        self.assertEqual(self.packet["expected"]["uncertainty_cases"], [[1, 1], [1, 2], [2, 1], [2, 2]])
        with self.assertRaises(ValueError): replace(link, uncertainty=(a.ParameterInterval("transfer_amount", "forward", 2, 2),))
        with self.assertRaises(ValueError): replace(link, uncertainty=(a.ParameterInterval("initial", "absent", 0, 1),))
        with self.assertRaises(ValueError): replace(link, uncertainty=link.uncertainty + (link.uncertainty[0],))
        with self.assertRaises(ValueError): replace(link, uncertainty=(a.ParameterInterval("initial", "a", 0, 2),
            a.ParameterInterval("initial", "b", 0, 2)))
        for arguments in (("continuous", "forward", 1, 2), ("transfer_amount", "forward", 0, 2),
                          ("initial", "a", True, 2), ("initial", "a", 0, 16)):
            with self.assertRaises(ValueError): a.ParameterInterval(*arguments)

    def test_chain_rejects_spliced_model_map_unit_and_clock(self):
        value = contract()
        first, last = value.chain.links
        changed = replace(last.source, observation=("b", "a"))
        with self.assertRaises(ValueError): first.then(replace(last, source=changed))
        changed_law = replace(target(), threshold=p.quantity(2, p.COUNT))
        with self.assertRaises(ValueError): first.then(replace(last, source=a.ApproximationEndpoint(changed_law, ("a", "b"))))
        with self.assertRaises(ValueError): replace(first, maximum_error=a.RationalErrorBound(1, 1, replace(p.COUNT, id="other")))
        with self.assertRaises(ValueError): replace(first, target=a.ApproximationEndpoint(replace(target(), sample_period=p.quantity(2, p.SECOND)), ("a", "b")))
        with self.assertRaises(ValueError): first.then(replace(last, uncertainty=(a.ParameterInterval("initial", "a", 1, 2),)))
        with self.assertRaises(ValueError): first.then(first)

    def test_horizon_coordinate_bounds_and_inert_snapshots(self):
        value = contract()
        for horizon in (0, 65, True, 1.5):
            with self.assertRaises(ValueError): replace(value, horizon_steps=horizon)
        with self.assertRaises(ValueError): replace(value, coordinates=("donor",))
        with self.assertRaises(ValueError): replace(value, coordinates=("donor", "donor"))
        with self.assertRaises(ValueError): a.ApproximationEndpoint(target(), ("a", "missing"))
        original = value.to_data()
        original["links"][0]["source"]["mechanism"]["transfers"][0]["amount"]["amount"] = "2"
        self.assertNotEqual(original, value.to_data())
        # A declarative zero bound is permitted but is not a checked assertion.
        unproved = replace(value, maximum_error=a.RationalErrorBound(0, 1, p.COUNT))
        self.assertEqual(unproved.to_data()["maximum_error"]["numerator"], "0")

    def test_exact_target_source_expansion_and_selected_payload_pins(self):
        request = self.packet["material_request"]
        document = p.from_data(request["implementation_request"]["document"], p.BuildRequest)
        self.assertEqual(p.check(document).status, "complete")
        machine = next(row for row in document.program.declarations if isinstance(row, p.Machine))
        observation = next(row for row in document.program.declarations if isinstance(row, p.Observation))
        effect = next(row for row in document.program.declarations if isinstance(row, p.Effect))
        expected = tuple(replace(row, id="target/" + row.id) for row in document.program.declarations if isinstance(row, p.Transition))
        self.assertEqual(target().transitions(machine, observation, effect, prefix="target"), expected)
        self.assertEqual(len(expected), 8)
        self.assertEqual(self.packet["expected"]["sequence"], "CCAUGGCUUAAGGAAAA")
        self.assertEqual(self.packet["expected"]["molecule"]["sequence"], self.packet["expected"]["sequence"])
        for component in request["component_library"]["components"]:
            self.assertEqual(generator.shared.digest(component["body"]), component["identity"]["content_fingerprint"])
        self.assertEqual(generator.shared.digest(request["composition_rule"]["body"]), request["composition_rule"]["identity"]["content_fingerprint"])
        self.assertEqual(generator.shared.digest(self.packet["expected"]["ordered_union"]), request["context"]["record_layout"]["union_digest"])
        for provider in request["context"]["providers"]:
            self.assertEqual(generator.shared.digest(provider["body"]), provider["identity"]["content_fingerprint"])
        self.assertEqual(self.packet["approximation"]["horizon_steps"], request["implementation_request"]["operating_domain"]["horizon_ticks"] + 1)
        self.assertGreater(self.packet["limits"]["source"]["max_ticks"], request["implementation_request"]["operating_domain"]["horizon_ticks"])

    def test_independent_literals_distinguish_nonzero_error_and_exact_requests(self):
        # Separate handwritten reference/target sample outcomes, not the compiler.
        reference = [(2, 0), (1, 1), (0, 2), (2, 0)]
        target_values = [(2, 0), (0, 2), (0, 2), (2, 0)]
        reference_requests = [False, True, False, False]
        target_requests = [False, True, False, False]
        self.assertEqual(reference_requests, target_requests)
        self.assertEqual(max(abs(a - b) for x, y in zip(reference, target_values) for a, b in zip(x, y)), 1)
        self.assertEqual(self.packet["expected"]["initial_error"], [1, 0])
        self.assertEqual(self.packet["expected"]["prefix_error_after_one_sample"], [1, 1])

    def test_previous_network_fixture_bytes_stay_frozen(self):
        self.assertEqual(hashlib.sha256(previous.PATH.read_bytes()).hexdigest(), "1a8af7b189a66d43e4c143dc472333df16ae9966146f0a35e9be257fd203ee41")

    def test_closed_original_decoder_roundtrip_and_rejections(self):
        original = self.packet["approximation"]
        self.assertEqual(a.ApproximationContract.from_data(original), contract())
        def changed(path, value):
            result = deepcopy(original)
            owner = result
            for key in path[:-1]: owner = owner[key]
            owner[path[-1]] = value
            return result
        for path, value in ((["maximum_error", "denominator"], "0"), (["maximum_error", "numerator"], "01"),
            (["maximum_error", "numerator"], 1), (["links", 0, "source", "mechanism", "arbitration"], "sequential"),
            (["links", 0, "source", "mechanism", "transfers", 0, "when"], 1), (["links", 0, "source", "observation"], ["a", "a"]),
            (["horizon_steps"], True), (["links", 0, "uncertainty", 0, "parameter"], "continuous")):
            with self.subTest(path=path), self.assertRaises((ValueError, CoreProtocolError)):
                a.ApproximationContract.from_data(changed(path, value))

    def test_strict_transport_accepts_scoped_error_evidence_without_minting_authority(self):
        report, original, request, material = transport_fixture(self.packet)
        self.assertIsNone(a.validate_assessment(report, original, request, material))
        failed = deepcopy(report)
        failed.update(outcome="fail", links=[], composition=None, issues=["Exact request labels differ"])
        self.assertIsNone(a.validate_assessment(failed, original, request, material))
        failed["composition"] = report["composition"]
        with self.assertRaises(CoreProtocolError): a.validate_assessment(failed, original, request, material)

    def test_transport_rejects_case_clipping_error_cancellation_and_claim_mutation(self):
        report, original, request, material = transport_fixture(self.packet)
        mutations = [(["links", 0, "case_count"], 3), (["links", 0, "uncertainty_cases"], report["links"][0]["uncertainty_cases"][:-1]),
            (["links", 0, "uncertainty_cases", 0, "mechanism_fingerprint"], "0" * 64),
            (["links", 0, "request_labels"], "approximately_equal"), (["links", 0, "envelope", 0, "coordinates", 0, "numerator"], "0"),
            (["links", 0, "envelope", 5, "coordinates", 0, "numerator"], "0"),
            (["links", 0, "coordinate_bounds", 0, "numerator"], "0"), (["links", 0, "maximum_error", "numerator"], "2"),
            (["links", 0, "envelope"], report["links"][0]["envelope"][:-1]), (["links", 0, "scope", "horizon_steps"], 12),
            (["composition", "envelope", 1, "coordinates", 0, "numerator"], "0"), (["composition", "inputs"], []),
            (["composition", "selected_mechanism_fingerprint"], "0" * 64), (["composition", "target_fingerprint"], "0" * 64),
            (["composition", "scope", "lifecycle"], "no_reset"), (["usage", "charged_work"], True),
            (["empirical"], "verified"), (["export"], "permitted"), (["material_report_fingerprint"], "0" * 64)]
        for path, value in mutations:
            mutant = deepcopy(report)
            owner = mutant
            for key in path[:-1]: owner = owner[key]
            owner[path[-1]] = value
            # Refreshed child identities do not hide altered scope or error arithmetic.
            mutant["composition"]["inputs"] = [generator.shared.digest(link) for link in mutant["links"]] if path != ["composition", "inputs"] else []
            with self.subTest(path=path), self.assertRaises(CoreProtocolError):
                a.validate_assessment(mutant, original, request, material)


if __name__ == "__main__": unittest.main()

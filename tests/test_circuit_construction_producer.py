"""Literal artificial positive controls for the untrusted construction producer."""

from dataclasses import replace
from unittest.mock import patch
import unittest

from biocompiler.artifacts.circuit_construction import ConstructionCandidate
from biocompiler.backends.circuit_construction import construct_circuit_candidate
from biocompiler.ir.circuit_construction import ValueRef, ValueSelection
from biocompiler.semantics.molecule_coordinates import CoordinatePath, IndexSpan
from examples.circuit_construction import make_construction_request


class ConstructionProducerTests(unittest.TestCase):
    def test_four_primitives_match_literal_expected_strings(self):
        request = make_construction_request()
        candidate = construct_circuit_candidate(request)
        self.assertEqual(candidate.diagnostics, ())
        self.assertEqual(
            {value.id: value.sequence for value in candidate.values},
            {
                "oriented": "TAACGT",
                "transcript": "UAACGU",
                "selected": "AACG",
                "joined": "AACGUA",
            },
        )
        self.assertEqual(candidate.bundle.molecules[0].sequence, "AACGUA")
        self.assertEqual(candidate.bundle.request.to_dict(), request.circuit.to_dict())
        self.assertEqual(
            ConstructionCandidate.from_json(candidate.to_json()), candidate
        )

    def test_source_change_reaches_output_without_an_expected_output_string(self):
        request = make_construction_request()
        source = request.sources[0]
        changed = replace(
            request,
            sources=(
                replace(source, molecule=replace(source.molecule, sequence="ACCTTA")),
            ),
        )
        candidate = construct_circuit_candidate(changed)
        self.assertEqual(candidate.bundle.molecules[0].sequence, "AAGGUA")
        self.assertNotEqual(candidate.request_fingerprint, request.fingerprint)
        # Output metadata remains identical; it cannot supply the expected bases.
        self.assertEqual(changed.output_members, request.output_members)

    def test_orientation_and_junction_maps_keep_original_source_coordinates(self):
        candidate = construct_circuit_candidate(make_construction_request())
        values = {value.id: value for value in candidate.values}
        oriented = values["oriented"].segments[0]
        self.assertEqual(
            (oriented.source_id, oriented.source_path.strand, oriented.rule),
            ("source", "-", "complement"),
        )
        joined = values["joined"].segments
        self.assertEqual(
            [
                (segment.destination.start, segment.destination.end, segment.source_id)
                for segment in joined
            ],
            [(0, 4, "selected"), (4, 6, "transcript")],
        )
        molecule = candidate.bundle.molecules[0]
        self.assertEqual(molecule.assembly[0].source_space, values["joined"].space)
        self.assertNotEqual(molecule.space.id, values["joined"].space.id)

    def test_transcription_never_infers_reverse_coding_strand(self):
        request = make_construction_request()
        step = request.steps[1]
        selection = ValueSelection(
            ValueRef("product", "oriented"),
            CoordinatePath("oriented.frame", (IndexSpan(0, 6),), "-"),
        )
        changed = replace(
            request,
            steps=(
                request.steps[0],
                replace(step, operation=replace(step.operation, input=selection)),
                *request.steps[2:],
            ),
        )
        candidate = construct_circuit_candidate(changed)
        self.assertIn(
            "step:transcribe:unsupported_transcription_path", candidate.diagnostics
        )
        self.assertIn("step:slice:unavailable_input", candidate.diagnostics)
        self.assertIsNone(candidate.bundle)
        self.assertEqual(candidate.missing_members, ("artificial-output",))

    def test_work_budget_stops_expansion_before_downstream_construction(self):
        request = make_construction_request()
        with patch(
            "biocompiler.backends.circuit_construction.MAX_CUMULATIVE_PRODUCED_RESIDUES",
            6,
        ):
            candidate = construct_circuit_candidate(request)
        self.assertEqual(tuple(value.id for value in candidate.values), ("oriented",))
        self.assertIn("step:transcribe:residue_budget", candidate.diagnostics)
        self.assertIsNone(candidate.bundle)

    def test_unknown_chemistry_does_not_acquire_nominal_completeness(self):
        request = make_construction_request()
        step = request.steps[-1]
        port = step.ports[0]
        chemistry = port.chemistry_transition.output
        changed_chemistry = replace(chemistry, modification_inventory_status="unknown")
        changed_port = replace(
            port,
            chemistry_transition=replace(
                port.chemistry_transition, output=changed_chemistry
            ),
        )
        changed = replace(
            request, steps=(*request.steps[:-1], replace(step, ports=(changed_port,)))
        )
        candidate = construct_circuit_candidate(changed)
        self.assertIn(
            "member:artificial-output:nominal_incomplete", candidate.diagnostics
        )
        self.assertIsNone(candidate.bundle.molecules[0].complete_nominal_identity)


if __name__ == "__main__":
    unittest.main()

"""Immutable assembly authority, coordinate semantics and strict import boundaries."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest

from biocompiler.errors import SerializationError
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.construct import (
    ConstructCandidate,
    ConstructDependency,
    ConstructFeature,
    ConstructJunction,
    ConstructRequest,
    LayoutEvidencePolicy,
    RegulatoryRelationship,
)
from biocompiler.semantics.coordinates import COORDINATE_CONVENTION, SequenceRange
from biocompiler.synthesis.construct import (
    generate_construct,
    prepare_reference_construct,
)
from test_construct_assembly import reference_inputs


def fixture():
    request = prepare_reference_construct(*reference_inputs())
    return request, generate_construct(request)


class ConstructSchemaTests(unittest.TestCase):
    def test_coordinate_convention_is_explicit_zero_based_half_open(self):
        interval = SequenceRange(4, 9)
        self.assertEqual(interval.length, 5)
        self.assertEqual(interval.to_dict()["convention"], COORDINATE_CONVENTION)
        self.assertEqual(SequenceRange.from_json(interval.to_json()), interval)
        self.assertEqual(SequenceRange(4, 4).length, 0)
        for start, end in ((-1, 4), (5, 4), (True, 4), (0, False), (0, 4.0)):
            with (
                self.subTest(start=start, end=end),
                self.assertRaises(SerializationError),
            ):
                SequenceRange(start, end)
        for convention in ("one-based-inclusive", None, [], 0):
            with self.subTest(convention=convention):
                data = interval.to_dict() | {"convention": convention}
                with self.assertRaises(SerializationError):
                    SequenceRange.from_dict(data)

    def test_roundtrip_keeps_authority_and_candidate_separate(self):
        request, candidate = fixture()
        self.assertEqual(ConstructRequest.from_json(request.to_json()), request)
        self.assertEqual(ConstructCandidate.from_json(candidate.to_json()), candidate)
        self.assertEqual(request.layout_dict(), candidate.layout_dict())
        self.assertEqual(request.layout_fingerprint, candidate.layout_fingerprint)
        self.assertNotEqual(request.fingerprint, candidate.fingerprint)
        self.assertEqual(request.target, request.composition.target)
        self.assertEqual(request.registry_lock, request.composition.registry_lock)
        self.assertNotIn("sequence", candidate.to_dict())
        self.assertNotIn("accepted", candidate.to_dict())

    def test_nested_imports_reject_wrong_shapes_with_public_serialization_error(self):
        request, candidate = fixture()
        for artifact in (request, candidate):
            cls = type(artifact)
            for key in artifact.to_dict():
                for bad in (None, 1, True, {}, []):
                    original = artifact.to_dict()
                    if original[key] == bad:
                        continue
                    if isinstance(original[key], list) and bad == []:
                        continue  # An empty inventory is a checker concern.
                    if key == "source_request_fingerprint" and bad is None:
                        continue  # An omitted archival origin is explicit.
                    data = deepcopy(original)
                    data[key] = bad
                    with self.subTest(artifact=cls.__name__, key=key, bad=bad):
                        with self.assertRaises(SerializationError):
                            cls.from_dict(data)
            for key in ("molecules", "placements"):
                for bad in (None, 1, True, [], "bad"):
                    data = artifact.to_dict()
                    data[key] = [bad]
                    with self.subTest(artifact=cls.__name__, key=key, bad=bad):
                        with self.assertRaises(SerializationError):
                            cls.from_dict(data)

    def test_nested_coordinate_source_and_component_imports_are_strict(self):
        _, candidate = fixture()
        for key in (
            "source_range",
            "molecule_range",
            "source",
            "component",
            "reference",
        ):
            for bad in (1, True, [], {}, "bad"):
                data = candidate.to_dict()
                data["placements"][0][key] = bad
                with (
                    self.subTest(key=key, bad=bad),
                    self.assertRaises(SerializationError),
                ):
                    ConstructCandidate.from_dict(data)
        for key, bad in (
            ("orientation", []),
            ("reading_frame", True),
            ("reading_frame", 3),
        ):
            data = candidate.to_dict()
            data["placements"][0][key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(SerializationError):
                ConstructCandidate.from_dict(data)

    def test_derived_node_inventory_and_target_cannot_be_forged(self):
        request, candidate = fixture()
        for artifact in (request, candidate):
            for replacement in (
                [],
                [{"id": "different", "kind": "component_placement"}],
            ):
                data = artifact.to_dict() | {"nodes": replacement}
                with (
                    self.subTest(artifact=type(artifact).__name__),
                    self.assertRaisesRegex(
                        SerializationError, "Derived construct nodes"
                    ),
                ):
                    type(artifact).from_dict(data)
        data = request.to_dict()
        data["target"]["context_version"] = "other"
        with self.assertRaisesRegex(SerializationError, "Derived construct target"):
            ConstructRequest.from_dict(data)

    def test_unknown_keys_and_schemas_do_not_silently_disappear(self):
        request, candidate = fixture()
        for artifact in (request, candidate):
            for change in ({"accepted": True}, {"schema_version": "future"}):
                with (
                    self.subTest(artifact=type(artifact).__name__),
                    self.assertRaises(SerializationError),
                ):
                    type(artifact).from_dict(artifact.to_dict() | change)
        text = candidate.to_json(indent=None)
        with self.assertRaisesRegex(SerializationError, "Duplicate JSON"):
            ConstructCandidate.from_json(text[:-1] + ',"molecules":[]}')

    def test_layout_edits_change_layout_and_artifact_identity(self):
        _, candidate = fixture()
        placement = candidate.placements[0]
        molecule = candidate.molecules[0]
        mutations = (
            replace(candidate, placements=(replace(placement, orientation="reverse"),)),
            replace(candidate, placements=(replace(placement, reading_frame=1),)),
            replace(
                candidate,
                placements=(replace(placement, source_range=SequenceRange(1, 1491)),),
            ),
            replace(candidate, molecules=(replace(molecule, compartment="cytosol"),)),
            replace(candidate, molecules=(replace(molecule, topology="circular"),)),
            replace(candidate, assumptions=candidate.assumptions + ("New dependency",)),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation.layout_fingerprint):
                self.assertNotEqual(
                    candidate.layout_fingerprint, mutation.layout_fingerprint
                )
                self.assertNotEqual(candidate.fingerprint, mutation.fingerprint)
        changed_root = replace(candidate, request_fingerprint="0" * 64)
        self.assertEqual(candidate.layout_fingerprint, changed_root.layout_fingerprint)
        self.assertNotEqual(candidate.fingerprint, changed_root.fingerprint)

    def test_sources_and_requirements_remain_immutable_lineage(self):
        request, candidate = fixture()
        source_requirements = list(candidate.placements[0].requirement_ids)
        placement = replace(
            candidate.placements[0], requirement_ids=source_requirements
        )
        source_requirements.append("forged")
        self.assertEqual(
            placement.requirement_ids, candidate.placements[0].requirement_ids
        )
        with self.assertRaises(FrozenInstanceError):
            placement.orientation = "reverse"
        with self.assertRaises(FrozenInstanceError):
            request.composition.instances[0].id = "forged"
        mutable = candidate.to_dict()
        mutable["placements"][0]["source"]["line"] = 99
        self.assertEqual(candidate.placements[0].source.line, 7)

    def test_multimolecule_dependencies_and_junction_choices_are_explicit(self):
        request, candidate = fixture()
        first = candidate.molecules[0]
        second = replace(first, id="helper", component_order=("helper-component",))
        dependency = ConstructDependency(
            "same-cell",
            first.id,
            second.id,
            "same_cell",
            "Both payloads enter the same cell",
        )
        direct = ConstructJunction(
            "junction",
            first.id,
            "cds",
            "helper-component",
            "direct",
            SequenceRange(1491, 1491),
            "Explicit boundary choice, pending evidence",
        )
        relationship = RegulatoryRelationship(
            "regulation",
            "activation",
            "helper-component",
            "cds",
            assumptions=("Regulation has not been characterized",),
        )
        richer = replace(
            candidate,
            molecules=(first, second),
            dependencies=(dependency,),
            junctions=(direct,),
            regulatory_relations=(relationship,),
        )
        self.assertEqual(ConstructCandidate.from_json(richer.to_json()), richer)
        self.assertNotEqual(request.layout_fingerprint, richer.layout_fingerprint)
        self.assertIn("same cell", richer.dependencies[0].assumption)
        with self.assertRaises(SerializationError):
            replace(dependency, assumption="")
        with self.assertRaises(SerializationError):
            replace(direct, kind="overlap")

    def test_subcomponent_boundaries_require_pinned_source_or_review_provenance(self):
        _, candidate = fixture()
        reference = candidate.placements[0].reference
        evidence = PinnedIdentity("evidence", "reviewed-boundary", "1", "a" * 64)
        feature = ConstructFeature(
            "domain",
            candidate.molecules[0].id,
            "reviewed_domain",
            SequenceRange(0, 30),
            reference,
            SequenceRange(0, 30),
            "Reviewed coordinate table, row 1",
            (evidence,),
        )
        self.assertEqual(ConstructFeature.from_json(feature.to_json()), feature)
        with self.assertRaisesRegex(SerializationError, "pinned provenance"):
            replace(feature, provenance=())
        with self.assertRaisesRegex(SerializationError, "source or review"):
            replace(feature, provenance=(reference,))
        with self.assertRaises(SerializationError):
            replace(feature, range=SequenceRange(0, 0))

    def test_policy_cannot_claim_prior_composition_or_behavior_evidence_survives(self):
        policy = LayoutEvidencePolicy()
        self.assertEqual(policy.invalidated_analyses, ("composition", "behavior"))
        for change in (
            {"invalidated_analyses": []},
            {"invalidated_analyses": ["composition"]},
            {"semantic_properties": ["orientation"]},
        ):
            with (
                self.subTest(change=change),
                self.assertRaisesRegex(SerializationError, "cannot be weakened"),
            ):
                LayoutEvidencePolicy.from_dict(policy.to_dict() | change)


if __name__ == "__main__":
    unittest.main()

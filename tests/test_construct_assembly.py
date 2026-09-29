"""Reference preparation pins scope and origin before candidate generation."""

from dataclasses import replace
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from cellweave.errors import SerializationError
from cellweave.ir.component_contracts import PinnedIdentity
from cellweave.ir.composition import CompositionInstance, CompositionRequest, Provider
from cellweave.ir.construct import ConstructCandidate, ConstructRequest, SequenceRange
from cellweave.ir.intent import SourceLocation
from cellweave.registry.components import ComponentRegistry
from cellweave.registry.reference_components import (
    ReferenceSelection,
    adapt_reference_component,
)
from cellweave.registry.references import load_reference_manifest
from cellweave.semantics.component_contracts import OperatingDomain
from cellweave.semantics.context import PayloadFormat, TargetContext
from cellweave.synthesis.construct import (
    generate_construct,
    prepare_reference_construct,
)

FIXTURE = Path(__file__).resolve().parents[1] / "data/references/fap_car/manifest.json"
MANIFEST = PinnedIdentity(
    "reference",
    "wo2022081694a1.murine-fapcar.cds",
    "1",
    "8d26e8d3e960d8dc0996e1f0582372ddfc9685795ed54131557f101be8849a41",
)
REFERENCE_PINS = {
    "DNA": PinnedIdentity(
        "reference",
        "wo2022081694a1.murine-fapcar.seq2",
        "1",
        "be64d2c4e6a5887a78c193be6f3aa747460487fa3e0a3a479784a95f58bcad90",
    ),
    "RNA": PinnedIdentity(
        "reference",
        "wo2022081694a1.murine-fapcar.seq3",
        "1",
        "8c4deb2c377aa04b1586abdef9eda951418ea3dc04b3146dba2a2bef5b40a5d5",
    ),
}


def reference_inputs(alphabet="DNA", *, path=FIXTURE):
    """Identity expectations are constants independent of the fixture being read."""
    manifest = load_reference_manifest(
        path, expected_fingerprint=MANIFEST.content_fingerprint
    )
    selection = ReferenceSelection(MANIFEST, REFERENCE_PINS[alphabet])
    component = adapt_reference_component(manifest, selection)
    registry = ComponentRegistry("reviewed-cds", "1", (component,))
    lock = registry.lock({"cds": component})
    requirements = ("reference.identity", "reference.whole_cds")
    composition = CompositionRequest(
        TargetContext("reference", "1", PayloadFormat(alphabet)),
        lock,
        (
            CompositionInstance(
                "cds",
                lock.components[0],
                OperatingDomain(),
                requirement_ids=requirements,
                source=SourceLocation("reference-request.py", 7, "build"),
            ),
        ),
        requirement_ids=requirements,
    )
    return manifest, selection, composition, registry


class ConstructAssemblyTests(unittest.TestCase):
    def test_dna_and_rna_preserve_whole_cds_scope_without_emitting_sequence(self):
        for alphabet in ("DNA", "RNA"):
            with self.subTest(alphabet=alphabet):
                manifest, selection, composition, registry = reference_inputs(alphabet)
                request = prepare_reference_construct(
                    manifest, selection, composition, registry
                )
                candidate = generate_construct(request)
                record = manifest.record(selection.reference.id)
                molecule, placement = candidate.molecules[0], candidate.placements[0]
                self.assertEqual(molecule.alphabet, alphabet)
                self.assertEqual(molecule.artifact_class, record.artifact_class)
                self.assertEqual(molecule.completeness, "CDS-reference-only")
                self.assertEqual(molecule.unknown_features, record.unknown_features)
                self.assertEqual(molecule.topology, "unspecified")
                self.assertEqual(molecule.compartment, "unspecified")
                self.assertEqual(molecule.component_order, ("cds",))
                self.assertEqual(molecule.length, 1491)
                self.assertEqual(placement.source_range, SequenceRange(0, 1491))
                self.assertEqual(placement.molecule_range, SequenceRange(0, 1491))
                self.assertEqual(placement.orientation, "forward")
                self.assertEqual(placement.reading_frame, 0)
                self.assertEqual(placement.reference, selection.reference)
                self.assertEqual(
                    placement.component, composition.instances[0].component
                )
                self.assertEqual(placement.source, composition.instances[0].source)
                self.assertEqual(
                    set(placement.requirement_ids), set(composition.requirement_ids)
                )
                self.assertEqual(
                    candidate.composition_fingerprint, composition.fingerprint
                )
                self.assertEqual(candidate.registry_lock, composition.registry_lock)
                self.assertEqual(
                    request.source_request_fingerprint, composition.fingerprint
                )
                self.assertEqual(candidate.request_fingerprint, request.fingerprint)
                self.assertEqual(
                    candidate.assumptions, registry.components[0].assumptions
                )
                self.assertFalse(
                    candidate.features
                    or candidate.junctions
                    or candidate.regulatory_relations
                    or candidate.dependencies
                )
                self.assertNotIn(record.sequence, candidate.to_json())
                self.assertEqual(ConstructRequest.from_json(request.to_json()), request)
                self.assertEqual(
                    ConstructCandidate.from_json(candidate.to_json()), candidate
                )

    def test_generation_is_deterministic_offline_and_does_not_self_certify(self):
        inputs = reference_inputs()
        with patch("socket.create_connection", side_effect=AssertionError("offline")):
            request = prepare_reference_construct(*inputs)
            first = generate_construct(request)
            second = generate_construct(ConstructRequest.from_json(request.to_json()))
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertFalse(hasattr(first, "passed"))
        self.assertFalse(hasattr(first, "accepted"))
        self.assertFalse(hasattr(first, "outcome"))

    def test_relocated_reference_files_do_not_change_construct_identity(self):
        original = generate_construct(prepare_reference_construct(*reference_inputs()))
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "reference"
            shutil.copytree(FIXTURE.parent, destination)
            relocated = generate_construct(
                prepare_reference_construct(
                    *reference_inputs(path=destination / "manifest.json")
                )
            )
        self.assertEqual(original.fingerprint, relocated.fingerprint)

    def test_source_authority_cannot_be_supplied_as_an_arbitrary_success_identity(self):
        inputs = reference_inputs()
        with self.assertRaisesRegex(SerializationError, "source authority"):
            prepare_reference_construct(*inputs, source_request_fingerprint="0" * 64)
        request = prepare_reference_construct(
            *inputs, source_request_fingerprint=inputs[2].fingerprint
        )
        self.assertEqual(request.source_request_fingerprint, inputs[2].fingerprint)

    def test_stale_and_swapped_selections_and_modality_mismatch_fail_preparation(self):
        manifest, selection, composition, registry = reference_inputs()
        for changed in (
            replace(selection, reference=REFERENCE_PINS["RNA"]),
            replace(selection, reference=replace(selection.reference, version="2")),
            replace(
                selection, manifest=replace(MANIFEST, content_fingerprint="0" * 64)
            ),
        ):
            with self.subTest(selection=changed), self.assertRaises(SerializationError):
                prepare_reference_construct(manifest, changed, composition, registry)
        wrong_target = replace(
            composition,
            target=replace(composition.target, payload_format=PayloadFormat.RNA),
        )
        with self.assertRaisesRegex(SerializationError, "target modality"):
            prepare_reference_construct(manifest, selection, wrong_target, registry)

    def test_selected_component_must_be_exact_and_its_current_registry_must_match(self):
        manifest, selection, composition, registry = reference_inputs()
        with self.assertRaisesRegex(SerializationError, "Registry identity"):
            prepare_reference_construct(
                manifest, selection, composition, replace(registry, version="2")
            )
        altered = replace(
            registry.components[0], assumptions=("Invented biological claim",)
        )
        changed_registry = replace(registry, components=(altered,))
        changed_lock = changed_registry.lock({"cds": altered})
        changed_composition = replace(
            composition,
            registry_lock=changed_lock,
            instances=(
                replace(composition.instances[0], component=changed_lock.components[0]),
            ),
        )
        with self.assertRaisesRegex(SerializationError, "independently pinned"):
            prepare_reference_construct(
                manifest, selection, changed_composition, changed_registry
            )

    def test_missing_requirement_coverage_and_co_payload_placement_are_rejected(self):
        manifest, selection, composition, registry = reference_inputs()
        for instance in (
            replace(composition.instances[0], requirement_ids=("reference.identity",)),
            replace(composition.instances[0], placement="co_payload"),
        ):
            with self.subTest(instance=instance), self.assertRaises(SerializationError):
                prepare_reference_construct(
                    manifest,
                    selection,
                    replace(composition, instances=(instance,)),
                    registry,
                )

    def test_multiple_components_and_external_supply_need_another_profile(self):
        manifest, selection, composition, registry = reference_inputs()
        instance = composition.instances[0]
        component = registry.components[0]
        lock = registry.lock({"cds": component, "second_cds": component})
        multiple = replace(
            composition,
            registry_lock=lock,
            instances=(
                instance,
                replace(instance, id="second_cds", component=lock.components[1]),
            ),
        )
        external = replace(
            composition,
            providers=(Provider("supply", "external", (), ("DNA",)),),
        )
        for unsupported in (multiple, external):
            with (
                self.subTest(composition=unsupported),
                self.assertRaises(SerializationError),
            ):
                prepare_reference_construct(manifest, selection, unsupported, registry)

    def test_named_molecule_changes_layout_identity_without_changing_origin(self):
        inputs = reference_inputs()
        original = generate_construct(prepare_reference_construct(*inputs))
        renamed = generate_construct(
            prepare_reference_construct(*inputs, molecule_id="reviewed_cds")
        )
        self.assertNotEqual(original.layout_fingerprint, renamed.layout_fingerprint)
        self.assertNotEqual(original.fingerprint, renamed.fingerprint)
        self.assertEqual(
            original.placements[0].reference, renamed.placements[0].reference
        )
        self.assertEqual(
            original.placements[0].component, renamed.placements[0].component
        )
        self.assertEqual(renamed.placements[0].molecule_id, "reviewed_cds")

    def test_generator_refuses_changed_supported_layout(self):
        request = prepare_reference_construct(*reference_inputs())
        for mutation in (
            {"placements": (replace(request.placements[0], orientation="reverse"),)},
            {"placements": (replace(request.placements[0], reading_frame=1),)},
            {
                "placements": (
                    replace(request.placements[0], source_range=SequenceRange(1, 1491)),
                )
            },
            {"molecules": (replace(request.molecules[0], topology="circular"),)},
            {"molecules": (replace(request.molecules[0], compartment="cytoplasm"),)},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(SerializationError):
                generate_construct(replace(request, **mutation))


if __name__ == "__main__":
    unittest.main()

"""Adversarial construction checks independent of the assembly producer."""

from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir.composition import CompositionInstance, CompositionRequest
from biocompiler.ir.construct import (
    ComponentPlacement,
    ConstructCandidate,
    ConstructDependency,
    ConstructFeature,
    ConstructJunction,
    ConstructMolecule,
    ConstructReference,
    ConstructRequest,
    RegulatoryRelationship,
)
from biocompiler.ir.intent import SourceLocation
from biocompiler.registry.components import ComponentRegistry
from biocompiler.registry.reference_components import (
    ReferenceSelection,
    adapt_reference_component,
)
from biocompiler.registry.references import load_reference_manifest
from biocompiler.semantics.component_contracts import OperatingDomain
from biocompiler.semantics.context import PayloadFormat, TargetContext
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.verification.construct import (
    ConstructResult,
    check_construct,
    check_construct_request,
)
from biocompiler.verification.evidence import CheckOutcome
from test_component_adapters import DNA, MANIFEST, RNA


def candidate_for(request):
    """Construct by schema alone; acceptance tests never invoke the producer."""
    return ConstructCandidate(
        request.fingerprint,
        request.composition.fingerprint,
        request.composition.registry_lock,
        request.molecules,
        request.placements,
        request.features,
        request.junctions,
        request.regulatory_relations,
        request.dependencies,
        request.assumptions,
        request.evidence_policy,
    )


def fixture(alphabet="DNA"):
    manifest = load_reference_manifest(
        Path(__file__).resolve().parents[1] / "data/references/fap_car/manifest.json",
        expected_fingerprint=MANIFEST.content_fingerprint,
    )
    selected = DNA if alphabet == "DNA" else RNA
    selection = ReferenceSelection(MANIFEST, selected)
    component = adapt_reference_component(manifest, selection)
    reference = manifest.record(selected.id)
    registry = ComponentRegistry("reference-fixture", "1", (component,))
    lock = registry.lock({"cds": component})
    source = SourceLocation("reference_build.py", 12)
    instance = CompositionInstance(
        "cds",
        lock.components[0],
        OperatingDomain(),
        requirement_ids=("exact_reference",),
        source=source,
    )
    composition = CompositionRequest(
        TargetContext("reference", "1", PayloadFormat(alphabet)),
        lock,
        (instance,),
        requirement_ids=instance.requirement_ids,
    )
    molecule = ConstructMolecule(
        "payload",
        reference.alphabet,
        reference.artifact_class,
        reference.length,
        ("cds",),
        topology="unspecified",
        completeness=reference.completeness,
        unknown_features=reference.unknown_features,
    )
    placement = ComponentPlacement(
        "cds",
        molecule.id,
        instance.component,
        selected,
        SequenceRange(0, reference.length),
        SequenceRange(0, reference.length),
        requirement_ids=instance.requirement_ids,
        source=source,
    )
    request = ConstructRequest(
        composition,
        (ConstructReference("cds", selection),),
        (molecule,),
        (placement,),
        assumptions=component.assumptions,
        source_request_fingerprint=composition.fingerprint,
    )
    return (
        request,
        candidate_for(request),
        registry,
        {manifest.reference_set_id: manifest},
    )


class ConstructCheckerTests(unittest.TestCase):
    def test_dna_and_rna_exact_whole_cds_pass_without_producer_or_network(self):
        for alphabet in ("DNA", "RNA"):
            request, candidate, registry, manifests = fixture(alphabet)
            with patch(
                "socket.create_connection", side_effect=AssertionError("offline only")
            ):
                result = check_construct(request, candidate, registry, manifests)
            self.assertEqual(result.outcome, CheckOutcome.PASS)
            self.assertEqual(result.checked_requirement_ids, ("exact_reference",))
            self.assertEqual(check_construct_request(request, registry, manifests), ())
            self.assertTrue(result.is_fresh(request, candidate, registry, manifests))
            self.assertEqual(ConstructResult.from_json(result.to_json()), result)
            self.assertIn("No sequence emission", result.claim_scope)
            self.assertEqual(
                request.molecules[0].unknown_features,
                manifests[MANIFEST.id]
                .record((DNA if alphabet == "DNA" else RNA).id)
                .unknown_features,
            )

    def test_changed_candidate_cannot_redefine_authority(self):
        request, candidate, registry, manifests = fixture()
        mutations = (
            replace(candidate, request_fingerprint="0" * 64),
            replace(candidate, composition_fingerprint="0" * 64),
            replace(candidate, assumptions=()),
            replace(
                candidate,
                placements=(replace(candidate.placements[0], orientation="reverse"),),
            ),
            replace(
                candidate,
                molecules=(replace(candidate.molecules[0], unknown_features=()),),
            ),
        )
        for changed in mutations:
            with self.subTest(changed=changed.fingerprint):
                self.assertFalse(
                    check_construct(request, changed, registry, manifests).passed
                )

    def test_matching_invalid_authority_and_candidate_are_independently_rejected(self):
        request, _, registry, manifests = fixture()
        placement = request.placements[0]
        molecule = request.molecules[0]
        mutations = (
            replace(request, placements=(replace(placement, orientation="reverse"),)),
            replace(request, placements=(replace(placement, reading_frame=1),)),
            replace(
                request,
                placements=(replace(placement, source_range=SequenceRange(1, 1491)),),
            ),
            replace(
                request,
                placements=(replace(placement, molecule_range=SequenceRange(0, 1490)),),
            ),
            replace(request, molecules=(replace(molecule, length=1492),)),
            replace(request, molecules=(replace(molecule, topology="circular"),)),
            replace(request, molecules=(replace(molecule, compartment="cytoplasm"),)),
            replace(request, molecules=(replace(molecule, unknown_features=()),)),
            replace(request, assumptions=()),
            replace(request, source_request_fingerprint="0" * 64),
            replace(request, placements=(replace(placement, source=None),)),
            replace(request, placements=(replace(placement, requirement_ids=()),)),
        )
        for changed in mutations:
            with self.subTest(changed=changed.fingerprint):
                result = check_construct(
                    changed, candidate_for(changed), registry, manifests
                )
                self.assertEqual(result.outcome, CheckOutcome.FAIL)
                self.assertTrue(result.diagnostics)

    def test_reference_identity_cannot_be_changed_even_with_updated_producer_roots(
        self,
    ):
        request, _, registry, manifests = fixture()
        for selected in (
            replace(
                request.references[0].selection, manifest=replace(MANIFEST, version="2")
            ),
            ReferenceSelection(MANIFEST, RNA),
        ):
            changed = replace(
                request, references=(ConstructReference("cds", selected),)
            )
            result = check_construct(
                changed, candidate_for(changed), registry, manifests
            )
            self.assertEqual(result.outcome, CheckOutcome.FAIL)

    def test_selected_record_is_reconstructed_from_reference_not_trusted_registry_claim(
        self,
    ):
        request, _, registry, manifests = fixture()
        changed_component = replace(
            registry.components[0],
            guarantees=(*registry.components[0].guarantees, "fabricated-behavior"),
        )
        changed_registry = replace(registry, components=(changed_component,))
        lock = changed_registry.lock({"cds": changed_component})
        composition = replace(
            request.composition,
            registry_lock=lock,
            instances=(
                replace(request.composition.instances[0], component=lock.components[0]),
            ),
        )
        changed = replace(
            request,
            composition=composition,
            placements=(replace(request.placements[0], component=lock.components[0]),),
            source_request_fingerprint=composition.fingerprint,
        )
        result = check_construct(
            changed, candidate_for(changed), changed_registry, manifests
        )
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertIn("reference_component", {item.code for item in result.diagnostics})

    def test_missing_manifest_stale_registry_and_target_change_do_not_pass(self):
        request, candidate, registry, manifests = fixture()
        self.assertEqual(
            check_construct(request, candidate, registry, {}).outcome,
            CheckOutcome.UNKNOWN,
        )
        self.assertEqual(
            check_construct(
                request, candidate, replace(registry, version="2"), manifests
            ).outcome,
            CheckOutcome.FAIL,
        )
        composition = replace(
            request.composition,
            target=replace(
                request.composition.target, payload_format=PayloadFormat.RNA
            ),
        )
        changed = replace(
            request,
            composition=composition,
            source_request_fingerprint=composition.fingerprint,
        )
        self.assertEqual(
            check_construct(
                changed, candidate_for(changed), registry, manifests
            ).outcome,
            CheckOutcome.FAIL,
        )

    def test_semantic_layout_registry_reference_and_authority_edits_stale_receipt(self):
        request, candidate, registry, manifests = fixture()
        result = check_construct(request, candidate, registry, manifests)
        changed = replace(
            candidate, placements=(replace(candidate.placements[0], reading_frame=1),)
        )
        stale = result.freshness(request, changed, registry, manifests)
        self.assertIn("layout", stale.changed_dependencies)
        self.assertIn("candidate", stale.changed_dependencies)
        self.assertIn(
            "registry",
            result.freshness(
                request, candidate, replace(registry, version="2"), manifests
            ).changed_dependencies,
        )
        self.assertIn(
            "references",
            result.freshness(request, candidate, registry, {}).changed_dependencies,
        )
        self.assertIn(
            "request",
            result.freshness(
                replace(request, assumptions=()), candidate, registry, manifests
            ).changed_dependencies,
        )

    def test_diagnostic_retains_selected_source_and_requirements(self):
        request, _, registry, manifests = fixture()
        changed = replace(
            request, placements=(replace(request.placements[0], orientation="reverse"),)
        )
        result = check_construct(changed, candidate_for(changed), registry, manifests)
        diagnostic = next(
            item for item in result.diagnostics if item.code == "orientation"
        )
        self.assertEqual(diagnostic.source, request.composition.instances[0].source)
        self.assertEqual(diagnostic.requirement_ids, ("exact_reference",))

    def test_missing_extra_wrong_order_and_wrong_membership_are_rejected(self):
        request, _, registry, manifests = fixture()
        placement = request.placements[0]
        molecule = request.molecules[0]
        mutations = (
            replace(request, placements=()),
            replace(request, references=()),
            replace(
                request, placements=(placement, replace(placement, instance_id="extra"))
            ),
            replace(request, placements=(replace(placement, molecule_id="other"),)),
            replace(request, molecules=(replace(molecule, component_order=()),)),
            replace(
                request,
                molecules=(replace(molecule, component_order=("other", "cds")),),
            ),
            replace(request, placements=(replace(placement, reference=RNA),)),
            replace(
                request,
                placements=(
                    replace(
                        placement, component=replace(placement.component, version="2")
                    ),
                ),
            ),
        )
        for changed in mutations:
            with self.subTest(changed=changed.fingerprint):
                result = check_construct(
                    changed, candidate_for(changed), registry, manifests
                )
                self.assertEqual(result.outcome, CheckOutcome.FAIL)

    def test_explicit_features_junctions_regulation_and_dependencies_remain_unsupported(
        self,
    ):
        request, _, registry, manifests = fixture()
        source = registry.components[0].evidence[0]
        feature = ConstructFeature(
            "inferred-domain",
            "payload",
            "binding-domain",
            SequenceRange(10, 100),
            DNA,
            SequenceRange(10, 100),
            "domain-diagram",
            (source,),
        )
        junction = ConstructJunction(
            "junction",
            "payload",
            "cds",
            "cds",
            "overlap",
            SequenceRange(100, 103),
            "intentional overlap",
        )
        regulation = RegulatoryRelationship("regulation", "expression", "cds", "cds")
        dependency = ConstructDependency(
            "coexistence",
            "payload",
            "co-payload",
            "same_cell",
            "Co-delivery would need separate evidence.",
        )
        mutations = (
            replace(request, features=(feature,)),
            replace(request, junctions=(junction,)),
            replace(request, regulatory_relations=(regulation,)),
            replace(request, dependencies=(dependency,)),
            replace(
                request,
                molecules=(
                    *request.molecules,
                    replace(request.molecules[0], id="co-payload", component_order=()),
                ),
            ),
        )
        for changed in mutations:
            with self.subTest(changed=changed.fingerprint):
                result = check_construct(
                    changed, candidate_for(changed), registry, manifests
                )
                self.assertEqual(result.outcome, CheckOutcome.UNSUPPORTED)
        composition = replace(
            request.composition,
            instances=(
                replace(request.composition.instances[0], placement="co_payload"),
            ),
        )
        changed = replace(
            request,
            composition=composition,
            source_request_fingerprint=composition.fingerprint,
        )
        self.assertEqual(
            check_construct(
                changed, candidate_for(changed), registry, manifests
            ).outcome,
            CheckOutcome.UNSUPPORTED,
        )

    def test_coordinate_convention_and_derived_inventory_cannot_be_forged(self):
        request, candidate, _, _ = fixture()
        for artifact in (request, candidate):
            for altered in ("convention", "nodes"):
                data = artifact.to_dict()
                if altered == "convention":
                    data["placements"][0]["source_range"]["convention"] = (
                        "one-based-inclusive"
                    )
                else:
                    data["nodes"] = []
                with (
                    self.subTest(artifact=type(artifact).__name__, altered=altered),
                    self.assertRaises(SerializationError),
                ):
                    type(artifact).from_dict(data)

    def test_result_is_frozen_and_strictly_deserialized(self):
        request, candidate, registry, manifests = fixture()
        result = check_construct(request, candidate, registry, manifests)
        with self.assertRaises(TypeError):
            result.dependencies["request"] = "0" * 64
        for field, value in (
            ("outcome", "proven"),
            ("diagnostics", {}),
            ("dependencies", []),
            ("checked_requirement_ids", "exact_reference"),
            ("claim_scope", "universal biological efficacy"),
        ):
            data = result.to_dict()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(SerializationError):
                ConstructResult.from_dict(data)
        data = result.to_dict()
        data["outcome"] = "unknown"
        with self.assertRaises(SerializationError):
            ConstructResult.from_dict(data)


if __name__ == "__main__":
    unittest.main()

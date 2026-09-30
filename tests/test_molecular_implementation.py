"""Bounded precursor construction over independently specified artificial bases."""

from dataclasses import replace
import hashlib
import unittest

import biocompiler as bc
from biocompiler.backends.implementation import emit_implementation
from biocompiler.compiler.implementation_requirements import (
    analyze_implementation_requirements,
)
from biocompiler.errors import SerializationError
from biocompiler.ir.component_contracts import (
    DependencyRequirement,
    PinnedIdentity,
    ProvidedCapability,
)
from biocompiler.ir.composition import Provider
from biocompiler.ir.implementation import (
    DEPENDENCY_COMPARTMENTS,
    CodingJunction,
    CodingSegment,
    ImplementationConstraints,
    ImplementationDependencyBinding,
    ImplementationLibrary,
    ImplementationRequest,
    SecretedRNAArchitecture,
    SequenceAuthority,
)
from biocompiler.ir.payload import PayloadFeature
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.synthesis.implementation import (
    derive_implementation_construct,
    derive_implementation_plan,
    select_implementation,
)


def authority(identity, sequence, provenance="software_fixture"):
    return SequenceAuthority(
        identity,
        sequence,
        hashlib.sha256(sequence.encode()).hexdigest(),
        "test-fixture:" + identity,
        provenance,
    )


def request_fixture():
    therapy = bc.Therapy("precursor_encoding")
    cell = therapy.engineer("recipient", cell_type="T_cell")
    cell.when(cell.external.signal("cue").present()).do(cell.secrete("product"))
    target = bc.TargetContext(
        "declared_software_context",
        "1",
        bc.PayloadFormat.RNA,
        capabilities=tuple(DEPENDENCY_COMPARTMENTS),
        compartments=("cytoplasm", "secretory_pathway", "extracellular"),
    )
    source = bc.BuildRequest.freeze(therapy.freeze(), target=target)
    dependencies = tuple(
        DependencyRequirement(cap, cap, cell.role, "cell", compartment)
        for cap, compartment in DEPENDENCY_COMPARTMENTS.items()
    )
    provider = Provider(
        "host",
        "host",
        tuple(
            ProvidedCapability(x.capability, x.role, x.scope, x.compartment)
            for x in dependencies
        ),
        (target.fingerprint,),
    )
    segments = (
        CodingSegment("signal", "signal_peptide", authority("signal", "AUGGCU"), "MA"),
        CodingSegment("mature", "mature_product", authority("mature", "UUU"), "F"),
        CodingSegment("stop", "terminal_stop", authority("stop", "UAA"), "*"),
    )
    features = tuple(
        PayloadFeature(key, "known", "test-fixture:chemistry", value)
        for key, value in (
            ("cap", "cap1"),
            ("poly_a_tail", "exact:4"),
            ("nucleotide_modifications", "none"),
            ("end_structure", "single_strand"),
            ("five_prime_end", "capped"),
            ("three_prime_end", "hydroxyl"),
        )
    )
    architecture = SecretedRNAArchitecture(
        "compact",
        "1",
        "product",
        target.fingerprint,
        authority("front", "GG"),
        authority("back", "CC"),
        segments,
        (CodingJunction("signal", "mature"), CodingJunction("mature", "stop")),
        "MAF*",
        "F",
        2,
        dependencies,
        tuple(ImplementationDependencyBinding(x.id, "host") for x in dependencies),
        features,
        authority("tail", "AAAA"),
    )
    extended = replace(
        architecture,
        id="extended",
        segments=(
            replace(
                segments[0],
                sequence=authority("extended_signal", "AUGGCUGCU"),
                protein_sequence="MAA",
            ),
            *segments[1:],
        ),
        precursor_protein="MAAF*",
        cleavage_after_aa=3,
    )
    return ImplementationRequest(
        source,
        ImplementationLibrary(
            "artificial_precursors", "1", (extended, architecture), (provider,)
        ),
    )


def chain(request):
    requirements = analyze_implementation_requirements(request.source)
    selection = select_implementation(request, requirements)
    plan = derive_implementation_plan(request, requirements, selection)
    construct = derive_implementation_construct(request, requirements, plan)
    molecule = emit_implementation(request, construct)
    return requirements, selection, plan, construct, molecule


class MolecularImplementationTests(unittest.TestCase):
    def setUp(self):
        self.request = request_fixture()

    def selection(self, request):
        return select_implementation(
            request, analyze_implementation_requirements(request.source)
        )

    def changed_architecture(self, **changes):
        architecture = next(
            x for x in self.request.library.architectures if x.id == "compact"
        )
        return replace(
            self.request,
            library=replace(
                self.request.library, architectures=(replace(architecture, **changes),)
            ),
        )

    def test_exact_precursor_and_full_source_correspondence(self):
        requirements, selection, plan, construct, molecule = chain(self.request)
        self.assertEqual(selection.selected_architecture_id, "compact")
        self.assertEqual(molecule.sequence, "GGAUGGCUUUUUAACCAAAA")
        self.assertEqual(construct.precursor_protein, "MAF*")
        self.assertEqual(construct.mature_protein, "F")
        self.assertEqual(construct.cleavage_after_nt, 8)
        self.assertEqual(construct.junction_coordinates, (8, 11))
        self.assertEqual(
            [x.molecule_range for x in construct.placements],
            [
                SequenceRange(0, 2),
                SequenceRange(2, 8),
                SequenceRange(8, 11),
                SequenceRange(11, 14),
                SequenceRange(14, 16),
                SequenceRange(16, 20),
            ],
        )
        self.assertEqual(construct.placements[3].protein_range, SequenceRange(3, 3))
        self.assertEqual(plan.source_ids, requirements.products[0].source_ids)
        self.assertEqual(
            plan.unresolved_obligation_ids,
            tuple(x.id for x in requirements.obligations),
        )
        self.assertTrue(
            all(x.functional_support == "unestablished" for x in plan.dependencies)
        )
        self.assertTrue(
            all(
                x.requirement_ids == (requirements.products[0].id,)
                for x in construct.placements
            )
        )

    def test_architecture_constraint_changes_signal_and_exact_bases(self):
        modified = replace(
            self.request,
            constraints=ImplementationConstraints(
                allowed_architecture_ids=("extended",)
            ),
        )
        _, selection, _, construct, molecule = chain(modified)
        self.assertEqual(selection.selected_architecture_id, "extended")
        self.assertEqual(molecule.sequence, "GGAUGGCUGCUUUUUAACCAAAA")
        self.assertEqual(construct.cleavage_after_aa, 3)
        self.assertEqual(construct.cleavage_after_nt, 11)
        self.assertEqual(
            selection.alternatives[0].rejections[0].code, "architecture_not_allowed"
        )

    def test_bounded_rejection_and_strict_completeness(self):
        for constraints, code in (
            (ImplementationConstraints(max_length=1), "max_length_exceeded"),
            (
                ImplementationConstraints(require_implementation_complete=True),
                "implementation_incomplete",
            ),
        ):
            with self.subTest(code=code):
                result = self.selection(replace(self.request, constraints=constraints))
                self.assertIsNone(result.selected_architecture_id)
                self.assertTrue(
                    all(
                        code in {x.code for x in item.rejections}
                        for item in result.alternatives
                    )
                )
                self.assertEqual(result.diagnostics, ("bounded_candidates_exhausted",))

    def test_supplied_sequence_and_reference_remain_declared_authority(self):
        architecture = self.request.library.architectures[1]
        supplied = replace(architecture.five_prime_utr, provenance="supplied_sequence")
        request = self.changed_architecture(five_prime_utr=supplied)
        self.assertEqual(chain(request)[-1].sequence, "GGAUGGCUUUUUAACCAAAA")
        reference = replace(
            supplied,
            provenance="supplied_reference",
            reference=PinnedIdentity("reference", "declared-record", "1", "1" * 64),
        )
        self.assertNotEqual(reference.fingerprint, supplied.fingerprint)
        self.assertEqual(SequenceAuthority.from_json(reference.to_json()), reference)
        self.assertEqual(
            chain(self.changed_architecture(five_prime_utr=reference))[-1].sequence,
            "GGAUGGCUUUUUAACCAAAA",
        )
        with self.assertRaises(SerializationError):
            replace(supplied, provenance="supplied_reference")

    def test_explicit_junction_peptide_and_processing_boundary(self):
        architecture = self.request.library.architectures[1]
        junction = CodingSegment("join", "junction", authority("join", "GGC"), "G")
        segments = (architecture.segments[0], junction, *architecture.segments[1:])
        request = self.changed_architecture(
            segments=segments,
            junctions=tuple(
                CodingJunction(a.id, b.id) for a, b in zip(segments, segments[1:])
            ),
            precursor_protein="MAGF*",
            cleavage_after_aa=3,
        )
        _, _, _, construct, molecule = chain(request)
        self.assertEqual(molecule.sequence, "GGAUGGCUGGCUUUUAACCAAAA")
        self.assertEqual(construct.junction_coordinates, (8, 11, 14))
        self.assertEqual(construct.cleavage_after_nt, 11)

    def test_invalid_translation_processing_and_chemistry_are_rejections(self):
        architecture = self.request.library.architectures[1]
        cases = [
            ({"precursor_protein": "MAY*"}, "precursor_correspondence"),
            ({"mature_protein": "Y"}, "mature_product_correspondence"),
            ({"cleavage_after_aa": 1}, "processing_correspondence"),
            (
                {
                    "five_prime_utr": replace(
                        architecture.five_prime_utr, sequence_sha256="0" * 64
                    )
                },
                "sequence_hash",
            ),
            ({"features": architecture.features[:-1]}, "feature_inventory"),
            (
                {
                    "segments": (
                        replace(
                            architecture.segments[0],
                            sequence=authority("signal", "AUGG"),
                        ),
                        *architecture.segments[1:],
                    )
                },
                "segment_frame",
            ),
            (
                {
                    "segments": (
                        replace(
                            architecture.segments[0],
                            sequence=authority("signal", "AUGUAA"),
                        ),
                        *architecture.segments[1:],
                    )
                },
                "segment_translation",
            ),
            (
                {
                    "segments": (
                        *architecture.segments[:-1],
                        replace(
                            architecture.segments[-1], sequence=authority("stop", "UUU")
                        ),
                    )
                },
                "segment_translation",
            ),
        ]
        for changes, code in cases:
            with self.subTest(code=code, changes=changes):
                result = self.selection(self.changed_architecture(**changes))
                self.assertIsNone(result.selected_architecture_id)
                self.assertIn(code, {x.code for x in result.alternatives[0].rejections})

    def test_provider_unknown_context_and_prerequisites(self):
        provider = self.request.library.providers[0]
        cases = [
            ((), "dependency_unresolved"),
            ((replace(provider, kind="unresolved"),), "dependency_unresolved"),
            ((replace(provider, capabilities=()),), "dependency_incompatible"),
            (
                (replace(provider, supported_targets=("0" * 64,)),),
                "dependency_incompatible",
            ),
            (
                (replace(provider, depends_on=("host",)),),
                "provider_prerequisites_unsupported",
            ),
        ]
        for providers, code in cases:
            with self.subTest(code=code):
                request = replace(
                    self.request,
                    library=replace(self.request.library, providers=providers),
                )
                result = self.selection(request)
                self.assertIsNone(result.selected_architecture_id)
                self.assertIn(code, {x.code for x in result.alternatives[0].rejections})

    def test_target_scope_is_authoritative(self):
        target = replace(self.request.target, capabilities=())
        source = replace(self.request.source, target=target)
        architectures = tuple(
            replace(x, target_fingerprint=target.fingerprint)
            for x in self.request.library.architectures
        )
        providers = tuple(
            replace(x, supported_targets=(target.fingerprint,))
            for x in self.request.library.providers
        )
        request = replace(
            self.request,
            source=source,
            library=replace(
                self.request.library, architectures=architectures, providers=providers
            ),
        )
        self.assertIn(
            "host_capability_undeclared",
            {x.code for x in self.selection(request).alternatives[0].rejections},
        )
        dna = replace(
            self.request.source,
            target=replace(self.request.target, payload_format=bc.PayloadFormat.DNA),
        )
        result = self.selection(replace(self.request, source=dna))
        self.assertIn(
            "unsupported_modality", {x.code for x in result.alternatives[0].rejections}
        )

    def test_roundtrip_stale_authority_and_strict_import(self):
        requirements, selection, plan, construct, _ = chain(self.request)
        for item in (self.request, selection, plan, construct):
            self.assertEqual(type(item).from_json(item.to_json()), item)
            malformed = item.to_dict() | {"promoted": True}
            with self.assertRaises(SerializationError):
                type(item).from_dict(malformed)
        changed = replace(
            self.request, constraints=ImplementationConstraints(max_length=21)
        )
        with self.assertRaises(SerializationError):
            derive_implementation_plan(changed, requirements, selection)
        with self.assertRaises(SerializationError):
            derive_implementation_construct(
                self.request, requirements, replace(plan, unresolved_obligation_ids=())
            )
        with self.assertRaises(SerializationError):
            emit_implementation(changed, construct)
        changed_nodes = self.request.to_dict()
        changed_nodes["nodes"] = []
        with self.assertRaises(SerializationError):
            ImplementationRequest.from_dict(changed_nodes)

    def test_request_does_not_drop_constraints_or_invent_parts(self):
        for kwargs in (
            {
                "constraints": ImplementationConstraints(
                    allowed_architecture_ids=("missing",)
                )
            },
            {
                "source": replace(
                    self.request.source, implementation_constraints={"unknown": True}
                )
            },
            {"source": replace(self.request.source, preferences={"unhandled": 1})},
            {"source": replace(self.request.source, target=None)},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(SerializationError):
                replace(self.request, **kwargs)
        architecture = self.request.library.architectures[1]
        with self.assertRaises(SerializationError):
            replace(architecture, junctions=())
        with self.assertRaises(SerializationError):
            replace(
                self.request.library,
                architectures=(
                    architecture,
                    replace(
                        architecture,
                        id="other",
                        five_prime_utr=authority("front", "GGGG"),
                    ),
                ),
            )

    def test_ordering_and_missing_product_are_explicit(self):
        reversed_library = replace(
            self.request.library,
            architectures=tuple(reversed(self.request.library.architectures)),
        )
        left = self.selection(self.request)
        right = self.selection(replace(self.request, library=reversed_library))
        self.assertEqual(left.alternatives, right.alternatives)
        self.assertEqual(left.selected_architecture_id, right.selected_architecture_id)
        missing = replace(
            self.request,
            library=replace(
                self.request.library,
                architectures=tuple(
                    replace(x, product="unavailable")
                    for x in self.request.library.architectures
                ),
            ),
        )
        self.assertEqual(
            self.selection(missing).diagnostics, ("product_binding_unavailable",)
        )

    def test_architecture_choice_cannot_redefine_a_product_identity(self):
        architecture = self.request.library.architectures[1]
        segments = (
            architecture.segments[0],
            replace(
                architecture.segments[1],
                sequence=authority("mature_variant", "UAU"),
                protein_sequence="Y",
            ),
            architecture.segments[2],
        )
        variant = replace(
            architecture,
            id="variant",
            segments=segments,
            precursor_protein="MAY*",
            mature_protein="Y",
        )
        with self.assertRaisesRegex(SerializationError, "product identity"):
            replace(self.request.library, architectures=(architecture, variant))
        # A distinctly requested identity is a valid alternative library entry;
        # it cannot replace the original requested product during selection.
        variant = replace(variant, product="product_variant")
        library = replace(self.request.library, architectures=(architecture, variant))
        selection = self.selection(replace(self.request, library=library))
        self.assertEqual(selection.selected_architecture_id, "compact")
        self.assertEqual(len(selection.alternatives), 1)


if __name__ == "__main__":
    unittest.main()

"""Independent mutations of source, mechanism and composite sequence authority."""

from dataclasses import replace
import hashlib
import unittest
from unittest.mock import patch

from examples.molecular_implementation import make_implementation_request
from biocompiler.backends.implementation import emit_implementation
from biocompiler.compiler.implementation_requirements import (
    analyze_implementation_requirements,
)
from biocompiler.errors import SerializationError
from biocompiler.ir.implementation import (
    ImplementationConstraints,
    ImplementationDependency,
)
from biocompiler.ir.intent import IntentNode
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.synthesis.implementation import (
    derive_implementation_construct,
    derive_implementation_plan,
    select_implementation,
)
from biocompiler.verification.implementation import (
    ImplementationVerificationResult,
    check_implementation,
    check_implementation_construct,
    check_implementation_plan,
    check_implementation_requirements,
    check_implementation_selection,
)


def build_stages(request):
    requirements = analyze_implementation_requirements(request.source)
    selection = select_implementation(request, requirements)
    if selection.selected_architecture_id is None:
        return requirements, selection
    plan = derive_implementation_plan(request, requirements, selection)
    construct = derive_implementation_construct(request, requirements, plan)
    return (
        requirements,
        selection,
        plan,
        construct,
        emit_implementation(request, construct),
    )


class ImplementationVerificationTests(unittest.TestCase):
    def setUp(self):
        self.request = make_implementation_request()
        self.requirements, self.selection, self.plan, self.construct, self.molecule = (
            build_stages(self.request)
        )

    def check(self, **changes):
        values = dict(
            request=self.request,
            requirements=self.requirements,
            selection=self.selection,
            plan=self.plan,
            construct=self.construct,
            candidate=self.molecule,
            expected_request_fingerprint=self.request.fingerprint,
        )
        values.update(changes)
        return check_implementation(**values)

    def test_precise_composite_and_human_source_pass_only_partial_scope(self):
        self.assertEqual(self.molecule.sequence, "GGAUGGCUUUUUAACCAAAA")
        self.assertEqual(self.construct.precursor_protein, "MAF*")
        self.assertEqual(self.construct.mature_protein, "F")
        self.assertEqual(self.construct.cleavage_after_nt, 8)
        self.assertEqual(self.construct.junction_coordinates, (8, 11))
        self.assertEqual(
            self.construct.placements[2].molecule_range, SequenceRange(8, 11)
        )
        self.assertEqual(
            self.construct.placements[2].protein_range, SequenceRange(2, 3)
        )
        self.assertEqual(
            self.construct.placements[3].protein_range, SequenceRange(3, 3)
        )
        results = (
            check_implementation_requirements(
                self.request.source,
                self.requirements,
                expected_source_fingerprint=self.request.source.fingerprint,
            ),
            check_implementation_selection(
                self.request,
                self.requirements,
                self.selection,
                expected_request_fingerprint=self.request.fingerprint,
            ),
            check_implementation_plan(
                self.request,
                self.requirements,
                self.selection,
                self.plan,
                expected_request_fingerprint=self.request.fingerprint,
            ),
            check_implementation_construct(
                self.request,
                self.requirements,
                self.selection,
                self.plan,
                self.construct,
                expected_request_fingerprint=self.request.fingerprint,
            ),
            self.check(),
        )
        for result in results:
            with self.subTest(stage=result.stage):
                self.assertTrue(result.passed, result.diagnostics)
                self.assertEqual(result.physical_function, "unestablished")
                self.assertEqual(result.therapeutic_implementation, "partial")
                self.assertEqual(result.human_therapeutic_admission, "not_admitted")
                self.assertEqual(result.unresolved, self.requirements.obligations)
                self.assertEqual(
                    ImplementationVerificationResult.from_json(result.to_json()), result
                )
        self.assertEqual(
            self.check().dependencies["target"], self.request.source.target.fingerprint
        )

    def test_report_cannot_omit_source_semantics_or_reclassify_obligations(self):
        source_obligation = self.requirements.obligations[0]
        changes = (
            replace(self.requirements, obligations=self.requirements.obligations[1:]),
            replace(
                self.requirements,
                obligations=(
                    replace(source_obligation, kind="encoding"),
                    *self.requirements.obligations[1:],
                ),
            ),
            replace(self.requirements, diagnostics=self.requirements.diagnostics[:-1]),
            replace(
                self.requirements,
                products=(
                    replace(self.requirements.products[0], product="different_product"),
                ),
            ),
        )
        for report in changes:
            with self.subTest(report=report.fingerprint):
                checked = check_implementation_requirements(
                    self.request.source,
                    report,
                    expected_source_fingerprint=self.request.source.fingerprint,
                )
                self.assertFalse(checked.passed)
                self.assertIn(
                    "requirements_correspondence",
                    {item.code for item in checked.diagnostics},
                )
        self.assertFalse(
            check_implementation_requirements(
                self.request.source,
                self.requirements,
                expected_source_fingerprint="f" * 64,
            ).passed
        )

    def test_every_alternative_and_declared_ranking_are_independently_replayed(self):
        self.assertEqual(
            tuple(item.architecture_id for item in self.selection.alternatives),
            ("compact", "extended"),
        )
        for selection in (
            replace(self.selection, selected_architecture_id="extended"),
            replace(self.selection, alternatives=self.selection.alternatives[:1]),
            replace(
                self.selection,
                alternatives=(
                    replace(self.selection.alternatives[0], length_nt=1),
                    self.selection.alternatives[1],
                ),
            ),
            replace(
                self.selection,
                alternatives=(
                    replace(
                        self.selection.alternatives[0],
                        architecture_fingerprint="a" * 64,
                    ),
                    self.selection.alternatives[1],
                ),
            ),
        ):
            self.assertFalse(
                check_implementation_selection(
                    self.request,
                    self.requirements,
                    selection,
                    expected_request_fingerprint=self.request.fingerprint,
                ).passed
            )
        changed = replace(
            self.request,
            constraints=ImplementationConstraints(
                allowed_architecture_ids=("extended",)
            ),
        )
        requirements, selection, plan, construct, molecule = build_stages(changed)
        self.assertEqual(molecule.sequence, "GGAUGGCUGCUUUUUAACCAAAA")
        self.assertTrue(
            check_implementation(
                changed,
                requirements,
                selection,
                plan,
                construct,
                molecule,
                expected_request_fingerprint=changed.fingerprint,
            ).passed
        )
        self.assertFalse(
            check_implementation(
                changed,
                requirements,
                selection,
                plan,
                construct,
                molecule,
                expected_request_fingerprint=self.request.fingerprint,
            ).passed
        )

    def test_empty_and_unknown_search_pass_correspondence_without_a_molecule(self):
        cases = (
            replace(self.request, constraints=ImplementationConstraints(max_length=1)),
            replace(
                self.request,
                constraints=ImplementationConstraints(
                    require_implementation_complete=True
                ),
            ),
            replace(self.request, library=replace(self.request.library, providers=())),
            replace(
                self.request, library=replace(self.request.library, architectures=())
            ),
        )
        for request in cases:
            with self.subTest(request=request.fingerprint):
                requirements, selection = build_stages(request)
                self.assertIsNone(selection.selected_architecture_id)
                checked = check_implementation_selection(
                    request,
                    requirements,
                    selection,
                    expected_request_fingerprint=request.fingerprint,
                )
                self.assertTrue(checked.passed, checked.diagnostics)
                self.assertEqual(checked.stage, "selection")
                self.assertIsNone(checked.dependencies["candidate"])
        no_provider = cases[2]
        _, selected = build_stages(no_provider)
        self.assertTrue(
            all(
                reason.status == "unknown"
                for item in selected.alternatives
                for reason in item.rejections
            )
        )

    def test_plan_cannot_discard_controls_or_relabel_external_host_support(self):
        dependency = self.plan.dependencies[0]
        provider = replace(dependency.provider, kind="external")
        plans = (
            replace(
                self.plan,
                unresolved_obligation_ids=self.plan.unresolved_obligation_ids[:-1],
            ),
            replace(self.plan, source_ids=self.plan.source_ids[:-1]),
            replace(self.plan, edges=self.plan.edges[:-1]),
            replace(
                self.plan,
                roles=(
                    replace(self.plan.roles[0], segment_ids=()),
                    *self.plan.roles[1:],
                ),
            ),
            replace(
                self.plan,
                dependencies=(
                    ImplementationDependency(dependency.requirement, provider),
                    *self.plan.dependencies[1:],
                ),
            ),
        )
        for plan in plans:
            with self.subTest(plan=plan.fingerprint):
                self.assertFalse(
                    check_implementation_plan(
                        self.request,
                        self.requirements,
                        self.selection,
                        plan,
                        expected_request_fingerprint=self.request.fingerprint,
                    ).passed
                )

    def test_construct_codon_processing_and_source_maps_are_not_self_authorizing(self):
        placement = self.construct.placements[1]
        maps = (
            replace(placement, source_range=SequenceRange(1, 7)),
            replace(placement, molecule_range=SequenceRange(3, 9)),
            replace(placement, protein_range=SequenceRange(0, 1)),
            replace(placement, authority_fingerprint="b" * 64),
            replace(placement, role_id="product"),
        )
        constructs = [
            replace(
                self.construct,
                placements=(
                    self.construct.placements[0],
                    item,
                    *self.construct.placements[2:],
                ),
            )
            for item in maps
        ]
        constructs.extend(
            (
                replace(self.construct, cleavage_after_aa=1, cleavage_after_nt=5),
                replace(self.construct, junction_coordinates=(5, 11)),
                replace(self.construct, mature_protein="A"),
            )
        )
        for construct in constructs:
            with self.subTest(construct=construct.fingerprint):
                self.assertFalse(
                    check_implementation_construct(
                        self.request,
                        self.requirements,
                        self.selection,
                        self.plan,
                        construct,
                        expected_request_fingerprint=self.request.fingerprint,
                    ).passed
                )

    def test_rehashed_molecule_preserving_protein_still_fails_exact_authority(self):
        synonymous = self.molecule.sequence.replace("GCU", "GCC", 1)
        mutated = replace(
            self.molecule,
            sequence=synonymous,
            sequence_sha256=hashlib.sha256(synonymous.encode("ascii")).hexdigest(),
        )
        self.assertFalse(self.check(candidate=mutated).passed)
        regions = list(self.molecule.regions)
        regions[1] = replace(
            regions[1],
            source_locator="another-source",
            source_range=SequenceRange(1, 13),
        )
        self.assertFalse(
            self.check(candidate=replace(self.molecule, regions=tuple(regions))).passed
        )
        features = tuple(
            replace(item, value="cap0") if item.feature == "cap" else item
            for item in self.molecule.features
        )
        self.assertFalse(
            self.check(candidate=replace(self.molecule, features=features)).passed
        )

    def test_unsupported_extra_source_is_retained_and_cannot_create_a_plan(self):
        build = self.request.source.build_request
        extra = IntentNode("future:operation", "future.mechanism")
        source = replace(
            build, intent=replace(build.intent, nodes=(*build.intent.nodes, extra))
        )
        request = replace(self.request, source=source)
        requirements, selection = build_stages(request)
        self.assertEqual(selection.diagnostics, ("unsupported_source_profile",))
        self.assertIn(extra.id, requirements.source_node_ids)
        self.assertTrue(
            check_implementation_selection(
                request,
                requirements,
                selection,
                expected_request_fingerprint=request.fingerprint,
            ).passed
        )
        self.assertFalse(
            check_implementation_plan(
                request,
                requirements,
                selection,
                self.plan,
                expected_request_fingerprint=request.fingerprint,
            ).passed
        )

    def test_current_pins_and_exact_scope_are_required_for_result_reuse(self):
        result = self.check()
        args = (
            self.request,
            self.requirements,
            self.selection,
            self.plan,
            self.construct,
            self.molecule,
        )
        self.assertTrue(
            result.is_fresh(
                *args, expected_request_fingerprint=self.request.fingerprint
            )
        )
        self.assertFalse(result.is_fresh(*args, expected_request_fingerprint="f" * 64))
        with patch("biocompiler.ir.implementation.PROFILE_VERSION", "changed-family"):
            self.assertIn(
                "profiles",
                result.freshness(
                    *args, expected_request_fingerprint=self.request.fingerprint
                ).changed_dependencies,
            )
            with self.assertRaises(SerializationError):
                ImplementationVerificationResult.from_dict(result.to_dict())
        for changes in (
            {"stage": []},
            {"outcome": []},
            {"physical_function": "established"},
            {"therapeutic_implementation": "complete"},
            {"human_therapeutic_admission": "admitted"},
            {"checks": []},
            {"unresolved": []},
        ):
            with self.subTest(changes=changes), self.assertRaises(SerializationError):
                ImplementationVerificationResult.from_dict(result.to_dict() | changes)
        with self.assertRaises(SerializationError):
            self.check(candidate=None)
        with self.assertRaises(SerializationError):
            check_implementation_plan(
                self.request,
                self.requirements,
                self.selection,
                None,
                expected_request_fingerprint=self.request.fingerprint,
            )

    def test_standalone_source_provenance_change_invalidates_exact_replay(self):
        source = self.request.source.build_request
        requirements = analyze_implementation_requirements(source)
        checked = check_implementation_requirements(
            source, requirements, expected_source_fingerprint=source.fingerprint
        )
        original_node = source.intent.nodes[0]
        changed_node = replace(
            original_node,
            source=replace(original_node.source, file="relocated/source.py"),
        )
        changed = replace(
            source,
            intent=replace(
                source.intent, nodes=(changed_node, *source.intent.nodes[1:])
            ),
        )
        self.assertEqual(source.fingerprint, changed.fingerprint)
        self.assertNotEqual(source.artifact_fingerprint, changed.artifact_fingerprint)
        freshness = checked.freshness(
            changed, requirements, expected_source_fingerprint=source.fingerprint
        )
        self.assertEqual(freshness.changed_dependencies, ("source_artifact",))
        self.assertFalse(
            check_implementation_requirements(
                changed, requirements, expected_source_fingerprint=source.fingerprint
            ).passed
        )

    def test_checker_imports_no_producer_as_replay_oracle(self):
        targets = (
            "biocompiler.compiler.implementation_requirements.analyze_implementation_requirements",
            "biocompiler.synthesis.implementation.select_implementation",
            "biocompiler.synthesis.implementation.derive_implementation_plan",
            "biocompiler.synthesis.implementation.derive_implementation_construct",
            "biocompiler.backends.implementation.emit_implementation",
        )
        from contextlib import ExitStack

        with ExitStack() as stack:
            for target in targets:
                stack.enter_context(
                    patch(
                        target,
                        side_effect=AssertionError("producer invoked by checker"),
                    )
                )
            self.assertTrue(self.check().passed)


if __name__ == "__main__":
    unittest.main()

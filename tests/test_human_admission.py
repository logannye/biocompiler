"""Independent admission attacks; biological labels never authorize payloads."""

from contextlib import redirect_stdout
from dataclasses import FrozenInstanceError, replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import biocompiler as bc
from biocompiler.artifacts.archive import assemble_archive, read_archive
from biocompiler.artifacts.sequences import (
    export_reference_sequence,
    verify_sequence_export,
)
from biocompiler.cli import main as cli_main
from biocompiler.compiler.reference import (
    build_reference_package,
    prepare_reference_build,
    publish_reference_package,
    verify_reference_package,
)
from biocompiler.registry.components import ComponentRegistry, SelectionRequest
from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION, BOUNDARIES
from biocompiler.semantics.component_contracts import OperatingDomain
from biocompiler.synthesis.synthetic import (
    generate_synthetic,
    check_synthetic_candidate,
)
from biocompiler.verification.admission import admission_for_target
from biocompiler.verification.components import check_composition
from biocompiler.verification.construct import check_construct
from biocompiler.verification.evidence import CheckOutcome
from biocompiler.verification.molecular import check_molecular
from biocompiler.verification.realization import check_realization
from examples.checked_pipeline import build_request
from examples.human_acceptance import make_human_acceptance, example_trace
from examples.human_target import make_human_target
from test_build_manifest import manifest_fixture
from test_component_registry import component
from test_construct_checker import candidate_for
from test_human_target import fixture_evidence
from test_molecular_checker import fixture

REFERENCE = Path(__file__).resolve().parents[1] / "data/references/fap_car"


def evidence_inventory():
    """Artificial declarations testing category retention, not empirical sources."""
    return tuple(
        fixture_evidence(id=system, system=system, taxon_id=taxon)
        for system, taxon in (
            ("human_in_vivo", 9606),
            ("primary_human_cells", 9606),
            ("human_cell_line", 9606),
            ("nonhuman_in_vivo", 10090),
            ("nonhuman_cells", 10090),
            ("cell_free", None),
            ("software_fixture", None),
        )
    )


def human_construct(request):
    target = replace(make_human_target(), payload_format=request.target.payload_format)
    composition = replace(request.composition, target=target)
    return replace(
        request,
        composition=composition,
        source_request_fingerprint=composition.fingerprint,
    )


class AdmissionRecordTests(unittest.TestCase):
    def setUp(self):
        self.target = make_human_target()
        self.request = bc.AdmissionRequest(self.target, "human_therapeutic", "planning")

    def test_roundtrip_immutable_and_strict_required_fields(self):
        for artifact in (self.request, bc.assess_admission(self.request)):
            self.assertEqual(type(artifact).from_json(artifact.to_json()), artifact)
            with self.assertRaises(FrozenInstanceError):
                artifact.boundary = "export"
            for key in artifact.to_dict():
                data = artifact.to_dict()
                del data[key]
                with self.subTest(key=key), self.assertRaises(bc.SerializationError):
                    type(artifact).from_dict(data)
            for changes in ({"validated": True}, {"schema_version": "future"}):
                with self.assertRaises(bc.SerializationError):
                    type(artifact).from_dict(artifact.to_dict() | changes)

    def test_invalid_use_boundary_and_nonrecords_rejected(self):
        for changes in (
            {"intended_use": "clinical"},
            {"intended_use": []},
            {"boundary": "manufacturing"},
            {"boundary": None},
            {"target": self.target.to_dict()},
            {"components": ("x",)},
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaises(bc.SerializationError),
            ):
                replace(self.request, **changes)

    def test_fixed_fields_cannot_promote_or_change_policy(self):
        result = bc.assess_admission(self.request)
        for key, value in (
            ("policy", "old"),
            ("human_therapeutic_admission", "admitted"),
            ("claim_scope", "clinical"),
            ("evidence_status", "validated"),
            ("decision", "admitted"),
            ("decision", "software_only"),
        ):
            with self.subTest(key=key), self.assertRaises(bc.SerializationError):
                bc.AdmissionAssessment.from_dict(result.to_dict() | {key: value})

    def test_duplicate_json_fields_rejected(self):
        with self.assertRaises(bc.SerializationError):
            bc.AdmissionRequest.from_json(
                self.request.to_json()[:-1] + ', "boundary": "export"}'
            )

    def test_component_order_and_repeated_instances_have_one_inventory(self):
        a, b = component("a"), component("b")
        first = replace(self.request, components=(b, a, b))
        self.assertEqual(first, replace(self.request, components=(a, b)))
        with self.assertRaisesRegex(bc.SerializationError, "Ambiguous"):
            replace(
                self.request, components=(a, replace(a, assumptions=("different",)))
            )

    def test_all_boundaries_fail_closed(self):
        for boundary in BOUNDARIES:
            result = bc.assess_admission(replace(self.request, boundary=boundary))
            self.assertEqual(result.decision, "not_admitted")
            self.assertIn("human_profile_unavailable", result.diagnostics)

    def test_generic_target_cannot_request_human_use(self):
        legacy = bc.TargetContext(
            "human_in_vivo", "1", bc.PayloadFormat.RNA, capabilities=("human_admitted",)
        )
        result = bc.assess_admission(replace(self.request, target=legacy))
        self.assertEqual(result.decision, "not_admitted")
        self.assertIn("human_target_contract_missing", result.diagnostics)
        software = admission_for_target(legacy, boundary="selection")
        self.assertEqual(software.intended_use, "software_test")
        self.assertEqual(
            software.to_dict()["human_therapeutic_admission"], "not_admitted"
        )

    def test_human_contract_cannot_be_downgraded_to_software(self):
        result = bc.assess_admission(
            replace(self.request, intended_use="software_test")
        )
        self.assertEqual(result.decision, "not_admitted")
        self.assertIn(
            "human_target_cannot_be_downgraded_to_software", result.diagnostics
        )

    def test_declared_evidence_preserves_all_categories_and_limitations(self):
        evidence = evidence_inventory()
        target = replace(
            self.target,
            human_target=replace(self.target.human_target, evidence=evidence),
        )
        result = bc.assess_admission(replace(self.request, target=target))
        self.assertEqual(set(result.evidence), set(evidence))
        self.assertEqual(len({item.system for item in result.evidence}), 7)
        self.assertEqual(result.decision, "not_admitted")
        self.assertIn(
            "human_in_vivo_evidence_requires_independent_review", result.diagnostics
        )
        restored = bc.AdmissionAssessment.from_json(result.to_json())
        self.assertEqual(restored.evidence, result.evidence)
        self.assertEqual(
            result.to_dict()["evidence_status"], "declared_not_independently_validated"
        )

    def test_evidence_category_and_context_changes_invalidate_assessment(self):
        original = fixture_evidence(system="human_cell_line", taxon_id=9606)
        target = replace(
            self.target,
            human_target=replace(self.target.human_target, evidence=(original,)),
        )
        request = replace(self.request, target=target)
        result = bc.assess_admission(request)
        for changes in (
            {"system": "primary_human_cells"},
            {"system": "human_in_vivo"},
            {"source_context": "Different context"},
            {"limitations": "Different limitation"},
            {"source": replace(original.source, content_fingerprint="b" * 64)},
            {"system": "nonhuman_cells", "taxon_id": 10090},
        ):
            changed = replace(
                target,
                human_target=replace(
                    target.human_target, evidence=(replace(original, **changes),)
                ),
            )
            authority = replace(request, target=changed)
            self.assertFalse(result.is_current(authority))
            self.assertFalse(bc.verify_admission(authority, result))
            self.assertEqual(bc.assess_admission(authority).decision, "not_admitted")

    def test_saved_current_identity_is_not_fresh_verification(self):
        result = bc.assess_admission(self.request)
        forged = replace(result, diagnostics=("all_checks_passed",))
        self.assertTrue(forged.is_current(self.request))
        self.assertFalse(bc.verify_admission(self.request, forged))
        self.assertTrue(bc.verify_admission(self.request, result))

    def test_component_identity_or_boundary_change_invalidates_report(self):
        request = replace(self.request, components=(component("a"),))
        result = bc.assess_admission(request)
        for changed in (
            replace(request, boundary="export"),
            replace(request, components=(component("b"),)),
        ):
            self.assertFalse(bc.verify_admission(changed, result))

    def test_inspection_is_historical_and_retains_evidence(self):
        result = bc.assess_admission(self.request)
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "assessment.json"
            file.write_text(result.to_json())
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(cli_main(["inspect", str(file)]), 0)
            self.assertIn("not_admitted", output.getvalue())
            self.assertIn("historical", output.getvalue().lower())


class AdmissionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.target = make_human_target()

    def test_planning_surfaces_policy_and_never_enables_compilation(self):
        request, _ = build_request()
        plan = bc.plan(
            request.build_request.intent, profile=bc.BuildProfile(target=self.target)
        )
        self.assertFalse(plan.ready)
        self.assertEqual(plan.to_dict()["admission"]["decision"], "not_admitted")
        self.assertIn(
            "human_profile_unavailable", {item.code for item in plan.unresolved}
        )

    def test_reference_and_synthetic_and_modeled_records_cannot_be_human_implementations(
        self,
    ):
        _, _, _, reference_registry, _ = fixture("RNA")
        records = (
            *reference_registry.components,
            component("synthetic"),
            component("modeled", classification="modeled_component"),
        )
        for record in records:
            registry = ComponentRegistry("admission-test", "1", (record,))
            selection = SelectionRequest(
                record.implementation_role,
                self.target,
                record.supported_domain,
                preferred_component_ids=(record.id,),
            )
            result = registry.select(selection)
            self.assertEqual(result.outcome, "unsupported")
            self.assertIsNone(result.selected)
            self.assertIsNone(result.alternatives[0].preference_rank)
            self.assertIn("human_profile_unavailable", result.alternatives[0].reasons)
            self.assertTrue(registry.verify_selection(selection, result))
        result = admission_for_target(
            self.target, boundary="selection", components=records
        )
        self.assertIn(
            "murine_fap_reference_not_human_implementation", result.diagnostics
        )

    def test_renamed_reference_cannot_bypass_global_policy(self):
        _, _, _, registry, _ = fixture("RNA")
        record = registry.components[0]
        renamed = replace(
            record,
            id="asserted_human_component",
            identities=tuple(
                replace(pin, id=f"renamed_{i}")
                for i, pin in enumerate(record.identities)
            ),
        )
        result = admission_for_target(
            self.target, boundary="selection", components=(renamed,)
        )
        self.assertEqual(result.decision, "not_admitted")
        self.assertIn("sequence_reference_not_human_implementation", result.diagnostics)

    def test_empty_registry_reports_unsupported_human_profile(self):
        result = ComponentRegistry("empty", "1", ()).select(
            SelectionRequest("sensor", self.target, OperatingDomain())
        )
        self.assertEqual(result.outcome, "unsupported")
        self.assertEqual(result.alternatives, ())

    def test_software_selection_and_unknown_domains_remain_scoped(self):
        record = component("fixture")
        registry = ComponentRegistry("software", "1", (record,))
        target = bc.TargetContext("software", "1", bc.PayloadFormat.RNA)
        request = SelectionRequest("sensor", target, record.supported_domain)
        result = registry.select(request)
        self.assertEqual(result.outcome, "pass")
        self.assertEqual(result.admission.decision, "software_only")
        # Missing model domain information cannot become a satisfied constraint.
        unknown = replace(record, supported_domain=OperatingDomain())
        self.assertEqual(
            replace(registry, components=(unknown,)).select(request).outcome, "unknown"
        )

    def test_reidentified_saved_selection_cannot_authorize_human_target(self):
        record = component("fixture")
        registry = ComponentRegistry("software", "1", (record,))
        software = SelectionRequest(
            "sensor",
            bc.TargetContext("software", "1", bc.PayloadFormat.RNA),
            record.supported_domain,
        )
        saved = registry.select(software)
        human = replace(software, target=self.target)
        forged = replace(saved, request_fingerprint=human.fingerprint)
        self.assertFalse(registry.verify_selection(human, forged))

    def test_locked_composition_is_rechecked_for_human_use(self):
        request, _, _, registry, _ = fixture("RNA")
        human = human_construct(request)
        result = check_composition(human.composition, registry)
        self.assertEqual(result.outcome, CheckOutcome.UNSUPPORTED)
        self.assertIn(
            "human_profile_not_admitted", {item.code for item in result.diagnostics}
        )
        self.assertEqual(
            result.dependencies["admission_policy"], ADMISSION_POLICY_VERSION
        )

    def test_coordinated_construct_and_molecular_hash_changes_do_not_bypass(self):
        request, _, artifact, registry, manifests = fixture("RNA")
        human = human_construct(request)
        construct = candidate_for(human)
        molecular = replace(
            artifact,
            request_fingerprint=human.fingerprint,
            construct_fingerprint=construct.fingerprint,
            source_request_fingerprint=human.source_request_fingerprint,
        )
        for result in (
            check_construct(human, construct, registry, manifests),
            check_molecular(human, construct, molecular, registry, manifests),
        ):
            self.assertNotEqual(result.outcome, CheckOutcome.PASS)
            self.assertIn("human_profile_not_admitted", str(result.diagnostics))

    def test_export_gate_precedes_even_a_stubbed_passing_checker(self):
        request, construct, artifact, registry, manifests = fixture("RNA")
        with patch("biocompiler.artifacts.sequences.check_molecular") as checker:
            checker.return_value.passed = True
            with self.assertRaisesRegex(bc.SerializationError, "not admitted"):
                export_reference_sequence(
                    human_construct(request), construct, artifact, registry, manifests
                )
            checker.assert_not_called()

    def test_reference_build_gate_precedes_reference_io(self):
        request = prepare_reference_build("RNA", REFERENCE)
        human = replace(request, construct=human_construct(request.construct))
        with patch("biocompiler.compiler.reference.load_reference_inputs") as loader:
            with self.assertRaisesRegex(bc.SerializationError, "not admitted"):
                build_reference_package(human, REFERENCE)
            loader.assert_not_called()

    def test_rehashed_archive_and_saved_pass_cannot_bypass_current_gate(self):
        request = prepare_reference_build("RNA", REFERENCE)
        package = build_reference_package(request, REFERENCE)
        human = replace(request, construct=human_construct(request.construct))
        manifest, files, metadata = read_archive(package.data)
        files = dict(files)
        files["request.json"] = (human.to_json() + "\n").encode()
        entries = tuple(
            replace(
                entry,
                sha256=hashlib.sha256(files[entry.path]).hexdigest(),
                byte_length=len(files[entry.path]),
            )
            for entry in manifest.files
        )
        manifest = replace(
            manifest, request_fingerprint=human.fingerprint, files=entries
        )
        data = assemble_archive(manifest, files, metadata)
        forged = replace(package, request=human, manifest=manifest, data=data)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.bcb"
            output.write_bytes(b"previous artifact")
            with patch(
                "biocompiler.compiler.reference.tempfile.TemporaryDirectory"
            ) as scratch:
                for authority in (
                    {"expected_request": human},
                    {"expected_build_fingerprint": manifest.build_fingerprint},
                ):
                    with self.assertRaisesRegex(bc.SerializationError, "not admitted"):
                        verify_reference_package(data, **authority)
                with self.assertRaisesRegex(bc.SerializationError, "not admitted"):
                    publish_reference_package(forged, output)
                scratch.assert_not_called()
            self.assertEqual(output.read_bytes(), b"previous artifact")
            self.assertEqual(list(Path(directory).iterdir()), [output])

    def test_synthetic_generator_cannot_implement_human_target(self):
        request, _ = build_request()
        human = replace(
            request, build_request=replace(request.build_request, target=self.target)
        )
        with self.assertRaisesRegex(bc.UnsupportedBehaviorError, "not admitted"):
            generate_synthetic(human)

    def test_synthetic_candidate_and_direct_checker_reject_reidentified_human_request(
        self,
    ):
        request, history = build_request()
        candidate = generate_synthetic(request)
        human = replace(
            request, build_request=replace(request.build_request, target=self.target)
        )
        forged = replace(candidate, request_fingerprint=human.fingerprint)
        result = check_synthetic_candidate(human, forged, history, until=7)
        self.assertEqual(result.outcome, CheckOutcome.UNSUPPORTED)
        direct = check_realization(
            request.behavior,
            request.contract,
            request.domain,
            self.target,
            candidate.mechanism,
            candidate.observation_map,
            history,
            until=7,
        )
        self.assertEqual(direct.outcome, CheckOutcome.UNSUPPORTED)
        self.assertIn(
            "human_profile_not_admitted", {item.code for item in direct.diagnostics}
        )

    def test_supplied_human_trace_pass_is_separate_from_admission(self):
        request = make_human_acceptance()
        result = bc.check_human_acceptance(request, example_trace())
        self.assertEqual(result.outcome, "pass")
        target = request.behavior_request.build_request.target
        self.assertEqual(
            admission_for_target(target, boundary="verification").decision,
            "not_admitted",
        )

    def test_artifact_labels_are_fixed_and_not_promotable(self):
        _, _, molecular, _, _ = fixture("RNA")
        request, _ = build_request()
        for artifact in (molecular, generate_synthetic(request), manifest_fixture()):
            self.assertEqual(artifact.to_dict()["intended_use"], "software_test")
            self.assertEqual(
                artifact.to_dict()["human_therapeutic_admission"], "not_admitted"
            )
            for changes in (
                {"intended_use": "human_therapeutic"},
                {"human_therapeutic_admission": "admitted"},
            ):
                with self.assertRaises(bc.SerializationError):
                    type(artifact).from_dict(artifact.to_dict() | changes)

    def test_fasta_labels_are_part_of_export_integrity(self):
        inputs = fixture("RNA")
        bundle = export_reference_sequence(*inputs)
        self.assertIn("use=software_test human_admission=not_admitted", bundle.fasta)
        self.assertTrue(verify_sequence_export(bundle, inputs[2]))
        self.assertEqual(
            json.loads(bundle.specification)["intended_use"], "software_test"
        )
        for altered in (
            bundle.fasta.replace("use=software_test", "use=human_therapeutic"),
            bundle.fasta.replace(" human_admission=not_admitted", ""),
        ):
            with self.assertRaises(bc.SerializationError):
                verify_sequence_export(replace(bundle, fasta=altered), inputs[2])

    def test_reference_package_pins_policy_and_labels_scope(self):
        package = build_reference_package(
            prepare_reference_build("RNA", REFERENCE), REFERENCE
        )
        manifest, files, _ = read_archive(package.data)
        policy = next(
            item for item in manifest.toolchain if item.id == "human_admission_policy"
        )
        self.assertEqual(policy.version, ADMISSION_POLICY_VERSION)
        self.assertEqual(manifest.intended_use, "software_test")
        self.assertEqual(
            json.loads(files["result.json"])["human_therapeutic_admission"],
            "not_admitted",
        )

    def test_policy_change_invalidates_all_implementation_check_snapshots(self):
        request, construct, molecular, registry, manifests = fixture("RNA")
        checks = (
            (
                "components",
                check_composition(request.composition, registry),
                (request.composition, registry),
            ),
            (
                "construct",
                check_construct(request, construct, registry, manifests),
                (request, construct, registry, manifests),
            ),
            (
                "molecular",
                check_molecular(request, construct, molecular, registry, manifests),
                (request, construct, molecular, registry, manifests),
            ),
        )
        for module, result, inputs in checks:
            self.assertTrue(result.is_fresh(*inputs))
            with patch(
                f"biocompiler.verification.{module}.ADMISSION_POLICY_VERSION", "future"
            ):
                self.assertFalse(result.is_fresh(*inputs))
            data = result.to_dict()
            data["dependencies"]["admission_policy"] = "old"
            with self.assertRaises(bc.SerializationError):
                type(result).from_dict(data)

    def test_changed_schema_cannot_reuse_pre_admission_artifacts(self):
        request, _, molecular, registry, _ = fixture("RNA")
        software, _ = build_request()
        result = registry.select(
            SelectionRequest(
                registry.components[0].implementation_role,
                request.target,
                registry.components[0].supported_domain,
            )
        )
        for artifact in (
            molecular,
            registry,
            result,
            manifest_fixture(),
            generate_synthetic(software),
        ):
            legacy_schema = artifact.schema_version.rsplit(".v", 1)[0] + ".v0.1"
            self.assertNotEqual(artifact.schema_version, legacy_schema)
            data = artifact.to_dict()
            data["schema_version"] = legacy_schema
            with self.assertRaises(bc.SerializationError):
                type(artifact).from_dict(data)

    def test_policy_dependency_change_invalidates_accepted_pipeline_output(self):
        from biocompiler.compiler.molecular import run_molecular_pipeline
        from biocompiler.compiler.pipeline import PipelineError
        from biocompiler.ir.serialization import fingerprint

        request, _, _, registry, manifests = fixture("RNA")
        build = run_molecular_pipeline(request, registry, manifests)
        build.manager.set_dependency(
            "human_admission_policy", fingerprint("changed policy")
        )
        with self.assertRaises(PipelineError):
            build.manager.result("molecular", scope="exact_cds")


if __name__ == "__main__":
    unittest.main()

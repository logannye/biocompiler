"""Requirement analysis retains intent and never promotes physical claims."""

from dataclasses import FrozenInstanceError, replace
import unittest

from biocompiler.compiler.implementation_requirements import (
    analyze_implementation_requirements,
)
from biocompiler.compiler.request import BuildRequest, ElaborationProvenance
from biocompiler.errors import SerializationError
from biocompiler.frontend.api import Therapy
from biocompiler.ir.implementation_requirements import (
    BOUNDED_SOURCE_PROFILE,
    EVIDENCE_BOUNDARY,
    MAX_ANALYSIS_RECORDS,
    ImplementationRequirements,
    ImplementationObligation,
    ImplementationDiagnostic,
)
from biocompiler.ir.intent import (
    IntentNode,
    IntentProgram,
    SourceLocation,
    freeze_json,
    thaw_json,
)
from biocompiler.semantics.context import PayloadFormat, TargetContext
from biocompiler.semantics.types import ProductionRate
from examples.human_acceptance import make_human_acceptance
from examples.human_behavior import make_human_behavior
from examples.human_deployment import (
    make_human_deployment,
    seconds,
    with_fixture_bounds,
)


def source(product="fixture_product", *, band="high", rate=None, target=True):
    therapy = Therapy("implementation_requirements_fixture")
    cell = therapy.engineer("recipient", cell_type="software_fixture")
    guard = getattr(cell.external.signal("cue"), band)()
    cell.when(guard).do(cell.secrete(product, rate=rate))
    return BuildRequest.freeze(
        therapy.freeze(),
        target=TargetContext("uncharacterized_fixture", "1", PayloadFormat.RNA)
        if target
        else None,
        artifact_scope="complete_payload",
    )


def edit_node(request, kind, **changes):
    return replace(
        request,
        intent=replace(
            request.intent,
            nodes=tuple(
                replace(node, **changes) if node.kind == kind else node
                for node in request.intent.nodes
            ),
        ),
    )


class ImplementationRequirementsTests(unittest.TestCase):
    def test_complete_source_nodes_and_typed_function_obligations_are_retained(self):
        request = source()
        report = analyze_implementation_requirements(request)
        self.assertEqual(report.supported_profile, BOUNDED_SOURCE_PROFILE)
        self.assertEqual(report.source.to_dict(), request.to_dict())
        self.assertEqual(report.source_fingerprint, request.fingerprint)
        self.assertEqual(
            report.source_node_ids, tuple(node.id for node in request.intent.nodes)
        )
        obligations = {item.id: item for item in report.obligations}
        for node in request.intent.nodes:
            obligation = obligations["source:" + node.id]
            self.assertEqual(
                thaw_json(obligation.semantics["arguments"]),
                node.to_dict(include_source=False),
            )
            self.assertEqual(obligation.context["role_id"], node.role)
            self.assertEqual(
                obligation.context["target_fingerprint"], request.target.fingerprint
            )
        product = report.products[0]
        self.assertEqual(product.product, "fixture_product")
        self.assertEqual(product.requested_localization, "extracellular")
        self.assertEqual(product.requested_processing, "unspecified")
        self.assertEqual(obligations["encoding:" + product.action_id].kind, "encoding")
        self.assertEqual(
            obligations["localization:" + product.action_id].kind,
            "localization_processing",
        )
        self.assertEqual(
            obligations["response:" + product.action_id].kind, "quantitative"
        )
        self.assertTrue(
            all(
                item.status == "unresolved"
                and item.evidence_boundary == EVIDENCE_BOUNDARY
                for item in report.obligations
            )
        )
        self.assertEqual(report.physical_function, "unestablished")
        self.assertEqual(report.completion, "analysis_only")

    def test_product_and_guard_edits_change_authority_without_inventing_mechanisms(
        self,
    ):
        original = analyze_implementation_requirements(source())
        product = analyze_implementation_requirements(source("other_product"))
        guard = analyze_implementation_requirements(source(band="low"))
        self.assertEqual(
            len({original.fingerprint, product.fingerprint, guard.fingerprint}), 3
        )
        self.assertNotEqual(original.products[0].product, product.products[0].product)
        self.assertEqual(original.products[0].product, guard.products[0].product)
        original_predicate = next(
            item
            for item in original.obligations
            if item.semantics["operation"] == "qualitative"
        )
        edited_predicate = next(
            item
            for item in guard.obligations
            if item.semantics["operation"] == "qualitative"
        )
        self.assertEqual(
            original_predicate.semantics["arguments"]["attributes"]["band"], "high"
        )
        self.assertEqual(
            edited_predicate.semantics["arguments"]["attributes"]["band"], "low"
        )

    def test_wrapped_contracts_and_original_provenance_survive_exact_roundtrip(self):
        for request in (
            source(),
            make_human_behavior(),
            make_human_deployment(),
            make_human_acceptance(),
        ):
            with self.subTest(schema=request.schema_version):
                report = analyze_implementation_requirements(request)
                rebuilt = ImplementationRequirements.from_json(report.to_json())
                self.assertEqual(rebuilt.to_dict(), report.to_dict())
                self.assertEqual(rebuilt.source.to_dict(), request.to_dict())
                self.assertEqual(rebuilt.fingerprint, report.fingerprint)
                frozen = ImplementationRequirements.from_dict(
                    freeze_json(report.to_dict())
                )
                self.assertEqual(frozen.to_dict(), report.to_dict())
                self.assertEqual(frozen.source.to_dict(), request.to_dict())
        request = make_human_acceptance()
        report = analyze_implementation_requirements(request)
        obligations = {item.id: item for item in report.obligations}
        self.assertEqual(
            thaw_json(obligations["contract:behavior"].semantics["arguments"]),
            request.behavior_request.contract.to_dict(),
        )
        self.assertEqual(
            thaw_json(obligations["contract:deployment"].semantics["arguments"]),
            request.deployment_request.deployment.to_dict(),
        )
        self.assertEqual(
            thaw_json(obligations["contract:acceptance"].semantics["arguments"]),
            request.acceptance.to_dict(),
        )
        self.assertEqual(
            obligations["evidence:human_admission"].semantics["arguments"]["admission"],
            "not_admitted",
        )

    def test_acceptance_labels_never_rewrite_source_guard_or_invent_conflicts(self):
        request = make_human_acceptance()
        report = analyze_implementation_requirements(request)
        self.assertEqual(
            report.build_request.intent.to_dict(),
            request.build_request.intent.to_dict(),
        )
        codes = {item.code for item in report.diagnostics}
        self.assertTrue(
            {
                "healthy_context_control_missing",
                "shutdown_control_missing",
                "input_loss_control_missing",
            }
            <= codes
        )
        self.assertFalse(
            any(item.category == "contradiction" for item in report.diagnostics)
        )
        for item in report.diagnostics:
            if item.code.endswith("control_missing"):
                self.assertEqual(
                    item.details["source_guard_policy"],
                    "unchanged_no_implicit_override",
                )

    def test_explicit_rate_units_and_closed_negative_contradiction(self):
        positive = analyze_implementation_requirements(
            source(rate=ProductionRate(2, unit="molecules/s"))
        )
        self.assertEqual(positive.supported_profile, BOUNDED_SOURCE_PROFILE)
        product = positive.products[0]
        self.assertIsNotNone(product.rate_id)
        self.assertIn(product.rate_id, product.source_ids)
        response = next(
            item
            for item in positive.obligations
            if item.id == "response:" + product.action_id
        )
        self.assertEqual(
            response.semantics["arguments"]["rate_expression"]["attributes"]["value"][
                "value"
            ],
            2,
        )
        negative = analyze_implementation_requirements(
            source(rate=ProductionRate(-1, unit="molecules/s"))
        )
        diagnostic = next(
            item
            for item in negative.diagnostics
            if item.code == "negative_secretion_rate"
        )
        self.assertEqual(diagnostic.category, "contradiction")
        self.assertEqual(diagnostic.details["value"]["value"], -1)

    def test_bound_parameter_value_not_default_is_authoritative(self):
        therapy = Therapy("parameterized_requirement")
        cell = therapy.engineer("cell", cell_type="fixture")
        rate = therapy.parameter("rate", type=ProductionRate, default=ProductionRate(1))
        cell.when(cell.external.signal("cue").present()).do(
            cell.secrete("product", rate=rate)
        )
        request = BuildRequest.freeze(
            therapy.freeze(), parameters={"rate": ProductionRate(-2)}
        )
        report = analyze_implementation_requirements(request)
        context = next(
            item for item in report.obligations if item.id == "build:context"
        )
        self.assertEqual(
            context.semantics["arguments"]["resolved_bindings"]["rate"][
                "canonical_value"
            ],
            -2,
        )
        self.assertIn(
            "negative_secretion_rate", {item.code for item in report.diagnostics}
        )

    def test_known_deployment_timing_contradiction_and_unknown_are_distinct(self):
        unknown = analyze_implementation_requirements(make_human_deployment())
        self.assertFalse(
            any(item.category == "contradiction" for item in unknown.diagnostics)
        )
        self.assertIn(
            "deployment_missing_refinement", {item.code for item in unknown.diagnostics}
        )
        request = with_fixture_bounds(make_human_deployment())
        short = replace(
            request,
            deployment=replace(
                request.deployment,
                timing=replace(request.deployment.timing, duration=seconds(10, 15)),
            ),
        )
        report = analyze_implementation_requirements(short)
        contradictions = [
            item for item in report.diagnostics if item.category == "contradiction"
        ]
        self.assertEqual(len(contradictions), 1)
        self.assertEqual(
            contradictions[0].details["deployment_diagnostic"],
            "expression_duration_does_not_cover_behavior",
        )

    def test_multiple_roles_and_products_remain_analyzable_and_unsupported(self):
        therapy = Therapy("two_roles")
        for name in ("first", "second"):
            cell = therapy.engineer(name, cell_type="fixture")
            cell.when(cell.external.signal("cue").high()).do(
                cell.secrete(name + "_product")
            )
        request = BuildRequest.freeze(therapy.freeze())
        report = analyze_implementation_requirements(request)
        self.assertEqual(
            {item.product for item in report.products},
            {"first_product", "second_product"},
        )
        self.assertIsNone(report.supported_profile)
        self.assertIn(
            "source_profile_unsupported", {item.code for item in report.diagnostics}
        )
        self.assertEqual(
            set(report.source_node_ids),
            {identity for item in report.obligations for identity in item.source_ids},
        )

    def test_temporal_and_nonsecretion_actions_remain_explicit_obligations(self):
        therapy = Therapy("temporal_effect")
        cell = therapy.engineer("cell", cell_type="fixture")
        cue = cell.contact.marker("A").present()
        memory = cell.memory("encounter", set_when=cue)
        cell.when(memory.is_set()).do(
            cell.eliminate(cell.contact), cell.secrete("product")
        )
        report = analyze_implementation_requirements(
            BuildRequest.freeze(therapy.freeze())
        )
        self.assertIsNone(report.supported_profile)
        self.assertEqual(len(report.products), 1)
        self.assertTrue(
            any(item.kind == "temporal_state" for item in report.obligations)
        )
        self.assertTrue(
            any(
                item.code == "operation_profile_unsupported"
                and item.details["operation"] == "action.eliminate"
                for item in report.diagnostics
            )
        )

    def test_controller_is_retained_without_becoming_a_secretory_implementation(self):
        therapy = Therapy("controller")
        cell = therapy.engineer("cell", cell_type="fixture")
        output = cell.secretion("output", product="product")
        observed = cell.internal.signal("observed")
        cell.regulate(
            "controller",
            observed=observed,
            target=1,
            actuator=output.rate,
            effect="increase_observed",
        )
        report = analyze_implementation_requirements(
            BuildRequest.freeze(therapy.freeze())
        )
        self.assertFalse(report.products)
        self.assertIsNone(report.supported_profile)
        controller = next(
            item
            for item in report.obligations
            if item.semantics["operation"] == "controller"
        )
        self.assertEqual(controller.kind, "control")
        self.assertIn(
            "secretion_rule_missing", {item.code for item in report.diagnostics}
        )

    def test_declaration_and_empty_program_do_not_imply_expression(self):
        therapy = Therapy("declaration")
        cell = therapy.engineer("cell", cell_type="fixture")
        cell.secretion("output", product="product")
        report = analyze_implementation_requirements(
            BuildRequest.freeze(therapy.freeze())
        )
        self.assertFalse(report.products)
        self.assertIsNone(report.supported_profile)
        self.assertIn(
            "secretion_rule_missing", {item.code for item in report.diagnostics}
        )
        empty = analyze_implementation_requirements(
            BuildRequest.freeze(IntentProgram("empty", (), ()))
        )
        self.assertFalse(empty.obligations)
        self.assertFalse(empty.source_node_ids)
        self.assertIsNone(empty.supported_profile)
        self.assertTrue(empty.diagnostics)
        self.assertEqual(
            empty.to_dict(),
            ImplementationRequirements.from_json(empty.to_json()).to_dict(),
        )

    def test_unknown_operations_and_malformed_action_attributes_report_without_crashing(
        self,
    ):
        request = source()
        extra = IntentNode("future_node", "future.sense", attributes={"mode": "new"})
        request = replace(
            request,
            intent=replace(
                request.intent,
                nodes=(*request.intent.nodes, extra),
                roots=(*request.intent.roots, extra.id),
            ),
        )
        report = analyze_implementation_requirements(request)
        self.assertIsNone(report.supported_profile)
        obligation = next(
            item for item in report.obligations if item.id == "source:future_node"
        )
        self.assertEqual(obligation.kind, "source_semantics")
        self.assertIn(
            "unknown_source_operation", {item.code for item in report.diagnostics}
        )
        for malformed in ({}, [], None, 3):
            with self.subTest(rate=malformed):
                request = edit_node(
                    source(),
                    "action.secrete",
                    attributes={"ongoing": True, "rate": malformed},
                )
                report = analyze_implementation_requirements(request)
                self.assertIsNone(report.supported_profile)
                self.assertFalse(report.products)
                self.assertIn(
                    "secretion_action_unresolved",
                    {item.code for item in report.diagnostics},
                )

    def test_opaque_constraints_are_preserved_and_block_profile_selection(self):
        request = replace(
            source(),
            implementation_constraints={"unrecognized_limit": 42},
            preferences={"custom": "choice"},
        )
        report = analyze_implementation_requirements(request)
        self.assertIsNone(report.supported_profile)
        diagnostic = next(
            item
            for item in report.diagnostics
            if item.code == "source_constraints_unsupported"
        )
        self.assertEqual(
            thaw_json(diagnostic.details["implementation_constraints"]),
            {"unrecognized_limit": 42},
        )
        self.assertEqual(report.build_request.to_dict(), request.to_dict())

    def test_authored_shutdown_priority_cannot_be_silently_accepted_or_inserted(self):
        request = source()
        rule = request.intent.find(kind="rule")[0]
        changed = edit_node(
            request,
            "rule",
            attributes={**rule.attributes, "priority": "shutdown_dominates"},
        )
        report = analyze_implementation_requirements(changed)
        self.assertIsNone(report.supported_profile)
        self.assertIn(
            "source_profile_unsupported", {item.code for item in report.diagnostics}
        )
        retained = next(
            item for item in report.obligations if item.id == "source:" + rule.id
        )
        self.assertEqual(
            retained.semantics["arguments"]["attributes"]["priority"],
            "shutdown_dominates",
        )
        unchanged = analyze_implementation_requirements(request)
        self.assertEqual(
            unchanged.build_request.intent.find(kind="rule")[0].attributes["priority"],
            "unspecified",
        )

    def test_event_source_and_mistyped_rate_are_reported_without_losing_authority(self):
        therapy = Therapy("event_source")
        cell = therapy.engineer("cell", cell_type="fixture")
        cell.on(cell.external.signal("cue").present().became_true()).do(
            cell.secrete("product")
        )
        request = BuildRequest.freeze(therapy.freeze())
        report = analyze_implementation_requirements(request)
        self.assertIsNone(report.supported_profile)
        self.assertEqual(report.source.to_dict(), request.to_dict())
        self.assertEqual(report.products[0].product, "product")
        request = source(rate=ProductionRate(1))
        action = request.intent.find(kind="action.secrete")[0]
        cue = request.intent.find(kind="signal")[0]
        wrong_rate = edit_node(
            request, "action.secrete", inputs=(action.inputs[0], cue.id)
        )
        invalid = analyze_implementation_requirements(wrong_rate)
        self.assertIsNone(invalid.supported_profile)
        self.assertFalse(invalid.products)
        self.assertIn(
            "secretion_action_unresolved",
            {item.code for item in invalid.diagnostics},
        )

    def test_provenance_is_never_normalized_away(self):
        request = source()
        node = request.intent.nodes[0]
        location = SourceLocation("/original/author/workspace/spec.py", 73, "author")
        request = replace(
            request,
            intent=replace(
                request.intent,
                nodes=(replace(node, source=location), *request.intent.nodes[1:]),
            ),
            provenance=ElaborationProvenance(
                locations={"source": "/original/author/workspace/spec.py"}
            ),
        )
        report = analyze_implementation_requirements(request)
        self.assertEqual(report.source.intent.nodes[0].source, location)
        self.assertEqual(
            report.source.provenance.locations, request.provenance.locations
        )
        self.assertEqual(
            ImplementationRequirements.from_json(report.to_json()).source.to_dict(),
            request.to_dict(),
        )

    def test_strict_records_reject_promotion_missing_nodes_and_unknown_fields(self):
        report = analyze_implementation_requirements(source())
        for key, value in (
            ("physical_function", "verified"),
            ("completion", "therapeutic_payload"),
            ("scope", "human_therapy"),
            ("source_fingerprint", "0" * 64),
            ("source_node_ids", []),
            ("supported_profile", BOUNDED_SOURCE_PROFILE),
        ):
            with self.subTest(field=key):
                document = report.to_dict()
                document[key] = value
                with self.assertRaises(SerializationError):
                    ImplementationRequirements.from_dict(document)
        with self.assertRaises(SerializationError):
            replace(report.obligations[0], status="implemented")
        with self.assertRaises(SerializationError):
            replace(report.obligations[0], evidence_boundary="empirical")
        with self.assertRaises(SerializationError):
            ImplementationRequirements.from_json(
                report.to_json().replace('"scope":', '"scope": "fake", "scope":', 1)
            )

    def test_recursive_immutability_and_bounded_imports(self):
        report = analyze_implementation_requirements(source())
        with self.assertRaises(FrozenInstanceError):
            report.source_fingerprint = "0" * 64
        with self.assertRaises(TypeError):
            report.obligations[0].semantics["arguments"]["attributes"]["cell_type"] = (
                "altered"
            )
        document = report.to_dict()
        document["obligations"][0]["semantics"]["arguments"]["attributes"][
            "cell_type"
        ] = "altered"
        self.assertNotEqual(
            report.obligations[0].semantics["arguments"]["attributes"]["cell_type"],
            "altered",
        )
        document = report.to_dict()
        document["diagnostics"] = [document["diagnostics"][0]] * (
            MAX_ANALYSIS_RECORDS + 1
        )
        with self.assertRaises(SerializationError):
            ImplementationRequirements.from_dict(document)
        deep = {}
        for _ in range(66):
            deep = {"nested": deep}
        with self.assertRaises(SerializationError):
            ImplementationDiagnostic(
                "deep", "missing_refinement", (), "Bounded diagnostics.", deep
            )
        with self.assertRaises(SerializationError):
            ImplementationObligation(
                "invalid",
                "encoding",
                (report.source_node_ids[0],),
                {"operation": "encode", "arguments": {}},
                {"role_id": None, "target_fingerprint": None, "contract_path": None},
                evidence_boundary="verified",
            )


if __name__ == "__main__":
    unittest.main()

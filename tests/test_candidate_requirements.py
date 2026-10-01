"""Source-derived product requests retain every unresolved therapeutic obligation."""

from dataclasses import FrozenInstanceError, replace
import hashlib
import unittest

from biocompiler.compiler.candidate_requirements import (
    CandidateRequirementsError,
    lower_candidate_requirements,
)
from biocompiler.compiler.request import BuildRequest
from biocompiler.errors import SerializationError
from biocompiler.frontend.api import Therapy
from biocompiler.ir.candidate import (
    CandidateConstraints,
    CandidateObligation,
    CandidateRequest,
    MolecularLibrary,
    MolecularPart,
    ProductBinding,
    RNAArchitecture,
)
from biocompiler.ir.intent import freeze_json
from biocompiler.ir.molecular_design import SequenceFragment
from biocompiler.ir.payload import PayloadFeature
from biocompiler.semantics.context import PayloadFormat, TargetContext
from biocompiler.semantics.types import LEVEL, ProductionRate
from examples.human_acceptance import make_human_acceptance
from examples.human_behavior import make_human_behavior
from examples.human_deployment import make_human_deployment


def library():
    """Invented literal fixtures with explicit names, not inferred functions."""
    parts = tuple(
        MolecularPart(
            identity,
            SequenceFragment(
                "fragment:" + identity,
                sequence,
                hashlib.sha256(sequence.encode("ascii")).hexdigest(),
                "invented-software-fixture:" + identity,
            ),
            kind,
        )
        for identity, kind, sequence in (
            ("utr5", "five_prime_utr", "GG"),
            ("coding_a", "cds", "AUGGCUUAA"),
            ("coding_a2", "cds", "AUGGCCUAA"),
            ("coding_b", "cds", "AUGGUUUAA"),
            ("utr3", "three_prime_utr", "CC"),
            ("tail", "poly_a", "AAAA"),
        )
    )
    features = tuple(
        PayloadFeature(key, "known", "invented-software-feature:" + key, value)
        for key, value in (
            ("cap", "cap1"),
            ("poly_a_tail", "exact:4"),
            ("nucleotide_modifications", "none"),
            ("end_structure", "single_strand"),
            ("five_prime_end", "capped"),
            ("three_prime_end", "hydroxyl"),
        )
    )
    return MolecularLibrary(
        "invented_coding_library",
        "1",
        parts,
        (
            ProductBinding("product_a", "coding_a", "MA*"),
            ProductBinding("product_a", "coding_a2", "MA*"),
            ProductBinding("product_b", "coding_b", "MV*"),
            ProductBinding("declared_product", "coding_a", "MA*"),
        ),
        (RNAArchitecture("linear_rna", "1", "utr5", "utr3", "tail", features),),
    )


def source(product="product_a", *, rate=None, extra=False, install=True):
    therapy = Therapy("candidate_source")
    cell = therapy.engineer("recipient", cell_type="software_fixture")
    cue = cell.external.signal("cue")
    condition = cue.high()
    if install:
        cell.when(condition).do(cell.secrete(product, rate=rate))
    else:
        cell.secretion("output", product=product)
    if extra:
        therapy.goal("requested_benefit", description="Retain this requested goal.")
        cell.memory("remember_cue", set_when=condition)
    return BuildRequest.freeze(
        therapy.freeze(),
        target=TargetContext("candidate_fixture", "1", PayloadFormat.RNA),
        artifact_scope="complete_payload",
    )


def changed_node(request, kind, **changes):
    intent = request.build_request.intent
    changed = replace(
        intent,
        nodes=tuple(
            replace(node, **changes) if node.kind == kind else node
            for node in intent.nodes
        ),
    )
    return replace(request, source=replace(request.build_request, intent=changed))


class CandidateRequirementsTests(unittest.TestCase):
    def setUp(self):
        self.library = library()
        self.request = CandidateRequest(source(extra=True), self.library)

    def test_product_is_derived_from_installed_source_and_every_node_is_retained(self):
        requirements = lower_candidate_requirements(self.request)
        intent = self.request.build_request.intent
        self.assertEqual(requirements.product, "product_a")
        self.assertEqual(requirements.role_id, intent.find(kind="role")[0].id)
        self.assertEqual(requirements.secretion_id, intent.find(kind="secretion")[0].id)
        self.assertEqual(
            requirements.action_id, intent.find(kind="action.secrete")[0].id
        )
        self.assertEqual(
            requirements.source_node_ids, tuple(node.id for node in intent.nodes)
        )
        self.assertEqual(requirements.request_fingerprint, self.request.fingerprint)
        self.assertEqual(
            {
                identity
                for item in requirements.unresolved
                for identity in item.source_ids
            },
            set(requirements.source_node_ids),
        )
        obligations = {item.id: item for item in requirements.unresolved}
        goal = intent.find(kind="goal")[0]
        memory = intent.find(kind="memory")[0]
        self.assertEqual(obligations["source:" + goal.id].category, "evidence")
        self.assertEqual(obligations["source:" + memory.id].category, "implementation")
        self.assertIn("conditional_control", obligations)
        self.assertIn("secretion_mechanism", obligations)
        self.assertIn("biological_function", obligations)
        self.assertNotIn("human_therapeutic_admission", obligations)
        alternate = CandidateRequest(source("product_b"), self.library)
        other = lower_candidate_requirements(alternate)
        self.assertEqual(other.product, "product_b")
        self.assertNotEqual(other.fingerprint, requirements.fingerprint)

    def test_declaration_alone_cannot_be_interpreted_as_constitutive_expression(self):
        request = CandidateRequest(source(install=False), self.library)
        with self.assertRaises(CandidateRequirementsError) as raised:
            lower_candidate_requirements(request)
        self.assertEqual(raised.exception.code, "source_shape")
        self.assertIn("action.secrete", str(raised.exception))
        self.assertEqual(raised.exception.diagnostics[0]["code"], "source_shape")

    def test_explicit_rate_is_retained_with_units_and_remains_unimplemented(self):
        request = CandidateRequest(
            source(rate=ProductionRate(2, unit="molecules/s")), self.library
        )
        requirements = lower_candidate_requirements(request)
        action = request.build_request.intent.find(kind="action.secrete")[0]
        rate_id = action.inputs[1]
        obligations = {item.id: item for item in requirements.unresolved}
        self.assertIn("source:" + rate_id, obligations)
        self.assertIn("quantitative_response", obligations)
        self.assertEqual(
            CandidateRequest.from_json(request.to_json()).source.to_dict(),
            request.source.to_dict(),
        )
        cue = request.build_request.intent.find(kind="signal")[0]
        wrong_type = changed_node(
            request, "action.secrete", inputs=(action.inputs[0], cue.id)
        )
        with self.assertRaises(CandidateRequirementsError) as raised:
            lower_candidate_requirements(wrong_type)
        self.assertEqual(raised.exception.code, "secretion_rate_type")

    def test_uninstalled_misowned_mistyped_and_unimplemented_rule_modes_reject(self):
        intent = self.request.build_request.intent
        action = intent.find(kind="action.secrete")[0]
        secretion = intent.find(kind="secretion")[0]
        rule = intent.find(kind="rule")[0]
        cases = (
            (
                changed_node(
                    self.request,
                    "secretion",
                    attributes={**secretion.attributes, "activity": "constitutive"},
                ),
                "secretion_declaration",
            ),
            (
                changed_node(
                    self.request,
                    "action.secrete",
                    attributes={**action.attributes, "ongoing": False},
                ),
                "secretion_action",
            ),
            (
                changed_node(self.request, "action.secrete", inputs=(rule.inputs[1],)),
                "secretion_action",
            ),
            (
                changed_node(
                    self.request,
                    "rule",
                    attributes={**rule.attributes, "trigger": "event"},
                ),
                "installed_condition_rule",
            ),
            (
                changed_node(
                    self.request,
                    "rule",
                    attributes={**rule.attributes, "priority": "override"},
                ),
                "installed_condition_rule",
            ),
            (
                changed_node(self.request, "qualitative", data_type=LEVEL.to_dict()),
                "condition_type",
            ),
            (
                replace(
                    self.request,
                    source=replace(
                        self.request.build_request,
                        intent=replace(
                            intent,
                            roots=tuple(
                                identity
                                for identity in intent.roots
                                if identity != rule.id
                            ),
                        ),
                    ),
                ),
                "source_roots",
            ),
        )
        for request, code in cases:
            with (
                self.subTest(code=code),
                self.assertRaises(CandidateRequirementsError) as raised,
            ):
                lower_candidate_requirements(request)
            self.assertEqual(raised.exception.code, code)

    def test_multiple_products_actions_rules_and_roles_are_explicitly_unsupported(self):
        for extra in ("product", "action", "rule", "role"):
            therapy = Therapy("unsupported_candidate")
            cell = therapy.engineer("recipient", cell_type="software_fixture")
            condition = cell.external.signal("cue").high()
            action = cell.secrete("product_a")
            if extra == "action":
                cell.when(condition).do(action, cell.present("another_action"))
            else:
                cell.when(condition).do(action)
            if extra == "product":
                cell.secretion("other_output", product="product_b")
            elif extra == "rule":
                cell.when(condition).do(action)
            else:
                therapy.engineer("another_recipient", cell_type="software_fixture")
            request = CandidateRequest(
                BuildRequest.freeze(therapy.freeze(), target=self.request.target),
                self.library,
            )
            with (
                self.subTest(extra=extra),
                self.assertRaises(CandidateRequirementsError) as raised,
            ):
                lower_candidate_requirements(request)
            self.assertIn(raised.exception.code, {"source_shape", "multiple_actions"})

    def test_all_human_source_wrappers_retain_original_context_and_obligations(self):
        wrappers = (
            make_human_behavior(),
            make_human_deployment(),
            make_human_acceptance(),
        )
        previous = set()
        for wrapped in wrappers:
            request = CandidateRequest(wrapped, self.library)
            restored = CandidateRequest.from_json(request.to_json())
            requirements = lower_candidate_requirements(restored)
            self.assertIsInstance(restored.source, type(wrapped))
            self.assertEqual(restored.source.to_dict(), wrapped.to_dict())
            self.assertEqual(restored.target, wrapped.target)
            obligations = {item.id for item in requirements.unresolved}
            self.assertTrue(previous <= obligations)
            previous = obligations
            self.assertIn("human_therapeutic_admission", obligations)
            self.assertIn("human_input_observation", obligations)
            self.assertIn("human_response_contract", obligations)
        self.assertTrue(
            {
                "human_deployment_contract",
                "human_prohibited_behavior",
                "human_input_loss_response",
                "human_external_shutdown",
                "human_acceptance_evidence",
            }
            <= previous
        )
        bare = CandidateRequest(wrappers[0].build_request, self.library)
        self.assertIn(
            "human_therapeutic_admission",
            {item.id for item in lower_candidate_requirements(bare).unresolved},
        )

    def test_request_never_ignores_original_policy_or_absent_target(self):
        for key in ("implementation_constraints", "preferences"):
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(SerializationError, "cannot be ignored"),
            ):
                CandidateRequest(
                    replace(
                        self.request.build_request, **{key: {"request": "retained"}}
                    ),
                    self.library,
                )
        with self.assertRaisesRegex(SerializationError, "explicit original target"):
            CandidateRequest(
                replace(
                    self.request.build_request,
                    target=None,
                    artifact_scope="abstract_behavior",
                ),
                self.library,
            )
        constrained = replace(
            self.request,
            constraints=CandidateConstraints(
                ("linear_rna",), ("coding_a2",), 30, "lexical"
            ),
        )
        self.assertNotEqual(constrained.fingerprint, self.request.fingerprint)
        self.assertEqual(constrained.target, self.request.target)

    def test_strict_roundtrips_and_frozen_mapping_pass_manager_input(self):
        requirements = lower_candidate_requirements(self.request)
        artifacts = (
            self.request,
            requirements,
            self.library,
            *self.library.parts,
            *self.library.products,
            *self.library.architectures,
            self.request.constraints,
            *requirements.unresolved,
        )
        for artifact in artifacts:
            cls = type(artifact)
            with self.subTest(artifact=cls.__name__):
                self.assertEqual(cls.from_json(artifact.to_json()), artifact)
                self.assertEqual(
                    cls.from_dict(freeze_json(artifact.to_dict())), artifact
                )
                for key in artifact.to_dict():
                    document = artifact.to_dict()
                    del document[key]
                    with self.assertRaises(SerializationError):
                        cls.from_dict(document)
                for patch in ({"schema_version": "future"}, {"verified": True}):
                    with self.assertRaises(SerializationError):
                        cls.from_dict(artifact.to_dict() | patch)
        for artifact in (self.request, requirements):
            for replacement in (
                [],
                [{"id": "fabricated", "kind": "implementation_requirement"}],
                None,
            ):
                with self.assertRaises(SerializationError):
                    type(artifact).from_dict(
                        artifact.to_dict() | {"nodes": replacement}
                    )

    def test_immutable_arrays_and_strict_constraint_types(self):
        mutable = ["linear_rna"]
        constraints = CandidateConstraints(mutable, ["coding_a"])
        mutable.append("mutated")
        self.assertEqual(constraints.allowed_architecture_ids, ("linear_rna",))
        with self.assertRaises(FrozenInstanceError):
            self.library.id = "changed"
        for patch in (
            {"max_length": True},
            {"max_length": -1},
            {"max_length": 2.5},
            {"preference": "best"},
            {"preference": []},
            {"allowed_architecture_ids": "linear_rna"},
            {"allowed_cds_part_ids": ["coding_a", "coding_a"]},
        ):
            with self.subTest(patch=patch), self.assertRaises(SerializationError):
                CandidateConstraints(**patch)
        for constraints in (
            CandidateConstraints(("missing",)),
            CandidateConstraints(allowed_cds_part_ids=("utr5",)),
        ):
            with self.assertRaises(SerializationError):
                replace(self.request, constraints=constraints)

    def test_library_references_identity_and_size_are_bounded(self):
        part = self.library.parts[0]
        architecture = self.library.architectures[0]
        mutations = (
            {"parts": (*self.library.parts, part)},
            {"parts": (*self.library.parts, replace(part, id="other"))},
            {"products": (*self.library.products, self.library.products[0])},
            {"products": (ProductBinding("bad", "utr5", "MA*"),)},
            {"architectures": (replace(architecture, five_prime_part_id="coding_a"),)},
            {"architectures": (replace(architecture, poly_a_part_id="missing"),)},
            {"architectures": (architecture, architecture)},
            {"products": ()},
            {
                "parts": tuple(
                    replace(part, id=str(i), fragment=replace(part.fragment, id=str(i)))
                    for i in range(33)
                )
            },
            {
                "products": tuple(
                    ProductBinding(str(i), "coding_a", "MA*") for i in range(17)
                ),
                "architectures": tuple(
                    replace(architecture, id=str(i)) for i in range(16)
                ),
            },
        )
        for mutation in mutations:
            with (
                self.subTest(fields=tuple(mutation)),
                self.assertRaises(SerializationError),
            ):
                replace(self.library, **mutation)
        self.assertEqual(
            [
                item.cds_part_id
                for item in self.library.products
                if item.product == "product_a"
            ],
            ["coding_a", "coding_a2"],
        )

    def test_imported_wrong_types_and_forged_obligation_correspondence_reject(self):
        requirements = lower_candidate_requirements(self.request)
        for document in (
            self.request.to_dict() | {"source": []},
            self.request.to_dict() | {"library": []},
            self.request.to_dict() | {"constraints": []},
        ):
            with self.assertRaises(SerializationError):
                CandidateRequest.from_dict(document)
        for malformed in ("*", "MA", "MA**", "MZ*", None, [], ""):
            with self.assertRaises(SerializationError):
                ProductBinding("product", "coding_a", malformed)
        for obligation in (
            CandidateObligation(
                "new", ("unknown",), "evidence", "Not an actual source node."
            ),
            requirements.unresolved[0],
        ):
            with self.assertRaises(SerializationError):
                replace(requirements, unresolved=(*requirements.unresolved, obligation))


if __name__ == "__main__":
    unittest.main()

"""Adversarial checks of assembly acceptance beyond interface compatibility."""

from contextlib import redirect_stdout
from dataclasses import replace
import io
import unittest
from unittest.mock import patch

import cellweave as cw
from cellweave.compiler.pipeline import PassManager, PipelineError
from cellweave.ir.serialization import fingerprint
from cellweave.semantics.component_contracts import ValueDomain
from examples.checked_pipeline import build_request
from examples.component_linking import main as example


class ComponentPipelineAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request, cls.history = build_request()
        cls.build = cw.run_component_pipeline(cls.request, cls.history, until=7)

    def run_with_metadata_mutation(self, mutation):
        original_register = PassManager.register

        def register(manager, contract, producer, validators):
            if contract.id == "synthetic_to_components":
                source_producer = producer

                def producer(context):
                    return mutation(source_producer(context), context)

            return original_register(manager, contract, producer, validators)

        with patch.object(PassManager, "register", register):
            return cw.run_component_pipeline(self.request, self.history, until=7)

    def test_nonempty_forged_observation_map_cannot_pass(self):
        with self.assertRaisesRegex(PipelineError, "provenance"):
            self.run_with_metadata_mutation(
                lambda result, context: replace(
                    result, observation_map={"forged": "endpoint"}
                )
            )

    def test_valid_but_wrong_source_links_cannot_pass(self):
        def mutate(result, context):
            # These node IDs and requirement IDs all exist. Only their semantic
            # correspondence is wrong, so inventory membership cannot reject it.
            replacement_id = context.input["mechanism"]["nodes"][-1]["id"]
            changed = tuple(
                replace(link, source_node_id=replacement_id)
                if link.source_node_id != replacement_id
                else link
                for link in result.source_links
            )
            self.assertNotEqual(result.source_links, changed)
            return replace(result, source_links=changed)

        with self.assertRaisesRegex(PipelineError, "provenance"):
            self.run_with_metadata_mutation(mutate)

    def test_duplicate_source_links_cannot_hide_a_provenance_error(self):
        with self.assertRaisesRegex(PipelineError, "provenance"):
            self.run_with_metadata_mutation(
                lambda result, context: replace(
                    result, source_links=(*result.source_links, result.source_links[0])
                )
            )

    def test_changed_literal_provenance_can_link_but_is_not_source_preserving(self):
        assembly = self.build.assembly
        records = assembly.registry.resolve(assembly.composition.registry_lock)
        node_id = next(key for key, record in records.items() if record.parameters)
        record = records[node_id]
        old = record.parameters[0]
        changed = replace(
            old,
            value=ValueDomain.interval(
                old.value.lower + 1,
                old.value.upper + 1,
                old.value.dtype,
                old.value.unit,
            ),
        )
        records[node_id] = replace(record, parameters=(changed,))
        registry = replace(assembly.registry, components=tuple(records.values()))
        lock = registry.lock(records)
        locked = {item.node_id: item for item in lock.components}
        composition = replace(
            assembly.composition,
            registry_lock=lock,
            instances=tuple(
                replace(instance, component=locked[instance.id])
                for instance in assembly.composition.instances
            ),
        )
        tampered = replace(assembly, registry=registry, composition=composition)
        self.assertTrue(cw.check_composition(composition, registry).passed)
        with self.assertRaisesRegex(PipelineError, "source correspondence"):
            cw.check_component_assembly(
                self.request, self.build.candidate, tampered, self.history, until=7
            )

    def test_remaining_upstream_roots_invalidate_component_acceptance(self):
        for key in (
            "request_artifact",
            "realization_artifact",
            "generator",
            "checker",
            "synthetic_acceptance",
            "evaluator",
        ):
            with self.subTest(key=key):
                build = cw.run_component_pipeline(self.request, self.history, until=7)
                build.manager.set_dependency(key, fingerprint("changed:" + key))
                with self.assertRaisesRegex(PipelineError, "Stale"):
                    build.manager.result("components", scope="synthetic_components")

    def test_assembly_reuse_rechecks_finite_history_and_horizon(self):
        for history, until in ((self.history[:1], 7), (self.history, 1.2)):
            with self.subTest(until=until, frames=len(history)):
                with self.assertRaisesRegex(
                    cw.SerializationError, "passing synthetic acceptance"
                ):
                    cw.check_component_assembly(
                        self.request,
                        self.build.candidate,
                        self.build.assembly,
                        history,
                        until=until,
                    )
        unresolved = self.build.result.unresolved[0]
        self.assertEqual(unresolved.id, "molecular_behavior")
        self.assertEqual(unresolved.evidence_kind, cw.EvidenceKind.EMPIRICAL)
        self.assertIn("not biological", self.build.link_result.claim_scope)

    def test_documented_example_uses_full_target_selection(self):
        captured = io.StringIO()
        with redirect_stdout(captured):
            example()
        self.assertIn("synthetic_components; status: complete", captured.getvalue())
        self.assertIn("CDS-reference-only", captured.getvalue())
        self.assertIn("Dynamic ports: 0", captured.getvalue())


if __name__ == "__main__":
    unittest.main()

"""Source-preserving component lowering and transitive acceptance freshness."""

from contextlib import redirect_stdout
from dataclasses import replace
import io
from pathlib import Path
import tempfile
import unittest

import cellweave as cw
from cellweave.cli import main
from cellweave.compiler.pipeline import ArtifactStatus, PipelineError
from cellweave.ir.serialization import fingerprint
from examples.checked_pipeline import build_request


class ComponentPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request, cls.history = build_request()
        cls.build = cw.run_component_pipeline(cls.request, cls.history, until=7)

    def check(self, assembly):
        return cw.check_component_assembly(
            self.request, self.build.candidate, assembly, self.history, until=7
        )

    def test_checked_component_scope_preserves_upstream_evidence_and_sources(self):
        build = self.build
        self.assertEqual(build.result.status, ArtifactStatus.COMPLETE)
        self.assertEqual(build.result.scope, "synthetic_components")
        self.assertTrue(build.link_result.passed)
        self.assertEqual(
            [item.id for item in build.result.unresolved], ["molecular_behavior"]
        )
        self.assertEqual(build.assembly.behavior_sources, build.candidate.source_map)
        record = build.manager.get("components")
        self.assertEqual(
            record.to_dict()["provenance"]["observation_map"],
            build.candidate.observation_map.to_dict(),
        )
        self.assertEqual(record.checks["composition"]["evidence"]["outcome"], "pass")
        source_ids = {node.id for node in build.candidate.mechanism.nodes}
        for link in record.to_dict()["provenance"]["source_links"]:
            self.assertIn(link["source_node_id"], source_ids)
        self.assertEqual(
            build.manager.result("mechanism", scope="synthetic_realization").status,
            ArtifactStatus.COMPLETE,
        )

    def test_import_roundtrip_preserves_locked_artifact(self):
        request = cw.RealizationRequest.from_json(self.request.to_json())
        restored = cw.ComponentAssembly.from_json(self.build.assembly.to_json())
        repeated = cw.run_component_pipeline(request, self.history, until=7)
        self.assertEqual(restored.fingerprint, repeated.assembly.fingerprint)
        self.assertEqual(
            self.build.result.artifact.fingerprint, repeated.result.artifact.fingerprint
        )
        self.assertTrue(self.check(restored).passed)
        with self.assertRaises(TypeError):
            restored.behavior_sources["new"] = ("fake",)

    def test_every_dependency_invalidates_components_transitively(self):
        for key in (
            "component_registry",
            "component_lock",
            "composition_request",
            "component_checker",
            "component_adapter",
            "component_registry_policy",
            "model",
            "catalog",
            "request",
            "realization_request",
            "history",
            "horizon",
        ):
            with self.subTest(key=key):
                build = cw.run_component_pipeline(self.request, self.history, until=7)
                build.manager.set_dependency(key, fingerprint("changed:" + key))
                with self.assertRaisesRegex(PipelineError, "Stale"):
                    build.manager.result("components", scope="synthetic_components")

    def test_rewired_compatible_graph_does_not_preserve_behavior(self):
        assembly = self.build.assembly
        output = self.build.candidate.mechanism.outputs[0]
        inactive = next(
            node.id
            for node in self.build.candidate.mechanism.nodes
            if node.id.startswith("inactive:")
        )
        connections = tuple(
            replace(edge, producer_instance=inactive)
            if edge.consumer_instance == output
            else edge
            for edge in assembly.composition.connections
        )
        selected = assembly.registry.resolve(assembly.composition.registry_lock)
        selected[output] = replace(
            selected[output],
            ports=tuple(
                replace(selected[inactive].port("out"), id=port.id, direction="input")
                if port.direction == "input"
                else port
                for port in selected[output].ports
            ),
        )
        registry = replace(assembly.registry, components=tuple(selected.values()))
        lock = registry.lock(selected)
        by_instance = {item.node_id: item for item in lock.components}
        composition = replace(
            assembly.composition,
            registry_lock=lock,
            instances=tuple(
                replace(item, component=by_instance[item.id])
                for item in assembly.composition.instances
            ),
            connections=connections,
        )
        wrong = replace(assembly, registry=registry, composition=composition)
        self.assertTrue(cw.check_composition(wrong.composition, wrong.registry).passed)
        with self.assertRaisesRegex(PipelineError, "source correspondence"):
            self.check(wrong)

    def test_changed_source_or_missing_connection_is_rejected(self):
        assembly = self.build.assembly
        sources = dict(assembly.behavior_sources)
        first = next(iter(sources))
        sources[first] = ("fabricated-source",)
        for wrong in (
            replace(assembly, behavior_sources=sources),
            replace(assembly, request_fingerprint="0" * 64),
            replace(assembly, candidate_fingerprint="0" * 64),
            replace(
                assembly,
                composition=replace(
                    assembly.composition,
                    connections=assembly.composition.connections[1:],
                ),
            ),
        ):
            with self.assertRaisesRegex(PipelineError, "source correspondence"):
                self.check(wrong)

    def test_imported_inventory_cannot_hide_or_add_components(self):
        for value in (
            None,
            {},
            "nodes",
            [],
            [{"id": "extra", "kind": "component_instance"}],
        ):
            document = self.build.assembly.to_dict()
            document["nodes"] = value
            with self.assertRaises(cw.SerializationError):
                cw.ComponentAssembly.from_dict(document)

    def test_unknown_history_cannot_be_promoted_by_linking(self):
        with self.assertRaisesRegex(PipelineError, "not passed"):
            cw.run_component_pipeline(self.request, self.history[:1], until=7)

    def test_component_scope_cannot_complete_molecular_payload(self):
        with self.assertRaises(PipelineError):
            self.build.manager.result("components", scope="complete_payload")
        with self.assertRaises(cw.CompilationUnavailableError):
            cw.compile(self.request.build_request)

    def test_cli_inspection_roundtrips_without_asserting_current_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "components.json"
            for artifact in (
                self.build.assembly,
                self.build.link_result,
                self.build.assembly.registry,
                self.build.assembly.composition,
            ):
                path.write_text(artifact.to_json())
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(["inspect", str(path)]), 0)
                self.assertIn(artifact.fingerprint, output.getvalue())


if __name__ == "__main__":
    unittest.main()

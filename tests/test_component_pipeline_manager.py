"""Component-stage pass integration preserves nested source inventories."""

from dataclasses import replace
import unittest

from biocompiler.artifacts.provenance import SourceLink
from biocompiler.compiler.passes import PassResult
from biocompiler.compiler.pipeline import (
    ArtifactStatus,
    CheckSpec,
    CompletionProfile,
    PassContract,
    PipelineError,
)
from biocompiler.ir.stages import Stage
from biocompiler.verification.evidence import EvidenceKind
import test_pipeline as fixtures


class ComponentStageManagerTests(unittest.TestCase):
    def test_nested_mechanism_inventory_is_authoritative_for_source_links(self):
        fixture = fixtures.PipelineTests()
        fixture.setUp()
        fixture.install_first()
        generation = replace(fixture.second, operation_path=("mechanism",))

        def produce(_):
            return PassResult(
                {
                    "schema_version": generation.output_schema,
                    "mechanism": fixtures.document("mechanism.v1"),
                },
                (),
                (SourceLink("r", "n", "n", generation.id),),
                {"output": "n"},
            )

        fixture.manager.register(
            generation, produce, {"response_check": fixtures.accepted}
        )
        fixture.manager.run(generation.id, "behavior", "mechanism")
        contract = PassContract(
            "link",
            "1",
            Stage.MECHANISM,
            Stage.COMPONENTS,
            "mechanism.v1",
            "components.v1",
            "components",
            "1",
            ("component",),
            (CheckSpec("linkage", EvidenceKind.EXACT),),
        )

        def link(_):
            return PassResult(
                fixtures.document("components.v1", kind="component"),
                (),
                (SourceLink("r", "n", "n", contract.id),),
            )

        fixture.manager.register(contract, link, {"linkage": fixtures.accepted})
        fixture.manager.register_completion_profile(
            CompletionProfile(
                "components",
                Stage.COMPONENTS,
                "components.v1",
                ("identity", "response"),
            )
        )
        fixture.manager.run(contract.id, "mechanism", "components")
        self.assertEqual(
            fixture.manager.result("components", scope="components").status,
            ArtifactStatus.COMPLETE,
        )

    def test_completion_profile_cannot_weaken_existing_scope(self):
        fixture = fixtures.PipelineTests()
        fixture.setUp()
        with self.assertRaisesRegex(PipelineError, "already registered"):
            fixture.manager.register_completion_profile(
                CompletionProfile("synthetic", Stage.INTENT, "intent.v1", ("identity",))
            )


if __name__ == "__main__":
    unittest.main()

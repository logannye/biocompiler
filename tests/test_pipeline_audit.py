"""Independent regressions for request integration and manager freshness."""

from dataclasses import replace
import unittest

from biocompiler import Therapy
from biocompiler.compiler.pipeline import PassManager, PipelineError
from biocompiler.compiler.request import BuildRequest
from biocompiler.errors import SerializationError
from biocompiler.semantics.context import PayloadFormat, TargetContext
import test_pipeline as fixtures


class PipelineAuditTests(unittest.TestCase):
    def fixture(self):
        fixture = fixtures.PipelineTests()
        fixture.setUp()
        return fixture

    def test_actual_build_request_target_matches_manager(self):
        target = TargetContext("host", "1", PayloadFormat.RNA)
        request = BuildRequest.freeze(Therapy("request").freeze(), target=target)
        manager = PassManager(
            target=target, dependencies={"request": request.fingerprint}
        )
        record = manager.add_input("request", request)
        self.assertTrue(record.accepted)

    def test_target_cannot_change_behind_freshness_dependencies(self):
        fixture = self.fixture()
        fixture.install_both()
        try:
            fixture.manager.target = replace(
                fixture.target, payload_format=PayloadFormat.DNA
            )
        except (AttributeError, PipelineError):
            return
        with self.assertRaises(PipelineError):
            fixture.manager.get("mechanism")

    def test_provider_rollback_cannot_revalidate_old_records_with_new_code(self):
        fixture = self.fixture()
        fixture.install_both()
        second_version = replace(fixture.first, version="2")
        fixture.manager.register(
            second_version,
            fixture.producer(second_version),
            {"identity_check": fixtures.accepted},
        )
        try:
            fixture.manager.register(
                fixture.first,
                fixture.producer(fixture.first, value=9),
                {"identity_check": lambda _: None},
            )
        except PipelineError:
            return
        with self.assertRaises(PipelineError):
            fixture.manager.get("mechanism")

    def test_observation_map_requires_mapping_even_when_nonempty(self):
        fixture = self.fixture()
        fixture.install_first()
        fixture.manager.register(
            fixture.second,
            fixture.producer(fixture.second, mapping=["not_a_mapping"]),
            {"response_check": fixtures.accepted},
        )
        with self.assertRaises((PipelineError, SerializationError)):
            fixture.manager.run("generate", "behavior", "mechanism")


if __name__ == "__main__":
    unittest.main()

"""Cross-layer regression checks for the public realization workflow."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import cellweave as cw
from cellweave.cli import main
from cellweave.semantics.types import BOOLEAN
from examples.realization_check import build_example, run_example


class RealizationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.args = build_example()

    def check(self, *args, until=7):
        return cw.check_realization(*(args or self.args), until=until)

    def test_public_workflow_exposes_success_counterexamples_and_staleness(self):
        results, changed = run_example()
        self.assertEqual(results["responsive"].outcome, cw.CheckOutcome.PASS)
        for label in ("silent", "late"):
            self.assertEqual(results[label].outcome, cw.CheckOutcome.FAIL)
            counterexample = results[label].counterexamples[0]
            self.assertEqual(counterexample.time, 1.5)
            self.assertEqual(counterexample.actual, 0)
            self.assertEqual(counterexample.source.function, "build_example")
        self.assertFalse(results["responsive"].is_fresh(changed))

    def test_aggregate_before_conjunction_is_detected_on_split_objects(self):
        behavior, contract, domain, target, candidate, mapping, history = self.args
        cell_boolean = cw.Observable("aggregated_a", BOOLEAN, domain.role)
        first, second = (item.mechanism_input_id for item in mapping.inputs)
        aggregate = candidate.find("any_contact")[0].id
        extra = (
            cw.MechanismNode("any_a", "any_contact", cell_boolean, (first,)),
            cw.MechanismNode(
                "any_b",
                "any_contact",
                replace(cell_boolean, id="aggregated_b"),
                (second,),
            ),
        )
        wrong = replace(
            candidate,
            nodes=tuple(
                replace(node, kind="and", inputs=("any_a", "any_b"))
                if node.id == aggregate
                else node
                for node in candidate.nodes
            )
            + extra,
        )
        result = self.check(behavior, contract, domain, target, wrong, mapping, history)
        self.assertEqual(result.outcome, cw.CheckOutcome.FAIL)
        self.assertEqual(result.counterexamples[0].time, 0.5)
        self.assertEqual(result.counterexamples[0].expected["state"], "inactive")

    def test_artifacts_roundtrip_and_inspect_without_executing_authoring(self):
        artifacts = (*self.args[:-1], self.check())
        with tempfile.TemporaryDirectory(prefix="cellweave-inspect-") as directory:
            path = Path(directory) / "artifact.json"
            for artifact in artifacts:
                with self.subTest(schema=artifact.schema_version):
                    restored = type(artifact).from_json(artifact.to_json())
                    self.assertEqual(restored.to_dict(), artifact.to_dict())
                    self.assertEqual(restored.fingerprint, artifact.fingerprint)
                    path.write_text(artifact.to_json(), encoding="utf-8")
                    out, err = io.StringIO(), io.StringIO()
                    with redirect_stdout(out), redirect_stderr(err):
                        code = main(["inspect", str(path), "--json"])
                    self.assertEqual(code, 0, err.getvalue())
                    self.assertEqual(json.loads(out.getvalue()), artifact.to_dict())

    def test_malformed_artifact_fields_produce_library_diagnostics(self):
        # Exercise the saved-artifact boundary rather than duplicating individual
        # constructor checks. Valid field mutations are allowed; invalid shapes
        # must never leak AttributeError, KeyError, or unhashable-type tracebacks.
        for artifact in (*self.args[1:-1], self.check()):
            for key in artifact.to_dict():
                for value in (None, [], {}, True, 1, "unexpected"):
                    document = artifact.to_dict()
                    document[key] = value
                    with self.subTest(
                        schema=artifact.schema_version, key=key, value=value
                    ):
                        try:
                            type(artifact).from_json(json.dumps(document))
                        except cw.SerializationError:
                            pass

    def test_plan_retains_context_assumptions_and_molecular_boundary(self):
        therapy = cw.Therapy("planning_context")
        cell = therapy.engineer("responder", cell_type="abstract_cell")
        cell.when(cell.internal.signal("A").present()).do(cell.rest())
        target = replace(self.args[3], resources={"abstract_budget": cw.Level(5)})
        plan = cw.plan(therapy.freeze(), profile=cw.BuildProfile(target))
        self.assertEqual(plan.to_dict()["target"], target.to_dict())
        self.assertFalse(plan.ready)
        with self.assertRaises(cw.CompilationUnavailableError):
            cw.compile(plan)

    def test_evidence_is_reproducible_across_hash_seeds(self):
        root = Path(__file__).resolve().parents[1]
        script = (
            "import json; from examples.realization_check import run_example; "
            "results, dependencies = run_example(); "
            "print(json.dumps({key: value.fingerprint for key, value in results.items()}, sort_keys=True))"
        )
        outputs = []
        for seed in ("1", "37"):
            process = subprocess.run(
                [sys.executable, "-c", script],
                cwd=root,
                env={
                    **os.environ,
                    "PYTHONPATH": str(root / "src"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONHASHSEED": seed,
                },
                capture_output=True,
                text=True,
                check=True,
            )
            outputs.append(process.stdout)
        self.assertEqual(outputs[0], outputs[1])


if __name__ == "__main__":
    unittest.main()

"""Human target authority survives serialization without promoting evidence."""

from contextlib import redirect_stdout
from dataclasses import FrozenInstanceError, replace
import io
import json
from pathlib import Path
import tempfile
import unittest

import cellweave as cw
from cellweave.cli import main as cli_main
from cellweave.ir.serialization import fingerprint
from examples.human_target import make_human_target


def fixture_evidence(**changes):
    values = {
        "id": "source_fixture",
        "source": cw.PinnedIdentity(
            "source", "artificial-target-description", "1", "a" * 64
        ),
        "taxon_id": None,
        "system": "software_fixture",
        "source_context": "Artificial software fixture, not an experiment.",
        "locator": "fixture:target-description",
        "limitations": "No empirical applicability or validated human biology.",
    }
    values.update(changes)
    return cw.TargetEvidence(**values)


class HumanTargetTests(unittest.TestCase):
    def setUp(self):
        self.target = make_human_target()
        self.contract = self.target.human_target

    def test_legacy_wire_identity_stays_exact(self):
        expected = {
            "schema_version": "cellweave.target.v0.1",
            "context_id": "legacy",
            "context_version": "1",
            "payload_format": "RNA",
            "capabilities": [],
            "compartments": ["abstract"],
            "resources": {},
        }
        target = cw.TargetContext("legacy", "1", cw.PayloadFormat.RNA)
        self.assertEqual(target.to_dict(), expected)
        self.assertEqual(target.fingerprint, fingerprint(expected))
        self.assertEqual(cw.TargetContext.from_dict(expected), target)

    def test_human_context_roundtrip_preserves_complete_authority(self):
        for cls in (cw.TargetContext, cw.HumanTargetContext):
            with self.subTest(cls=cls):
                restored = cls.from_json(self.target.to_json())
                self.assertIsInstance(restored, cw.HumanTargetContext)
                self.assertEqual(restored, self.target)
                self.assertEqual(restored.fingerprint, self.target.fingerprint)
        self.assertEqual(self.contract.to_dict()["recipient_taxon_id"], 9606)
        self.assertEqual(self.contract.to_dict()["engineering"], "in_vivo")

    def test_every_required_scope_must_be_explicit(self):
        for key in (
            "cell_subtype",
            "cell_state",
            "tissue_context",
            "disease_context",
            "population_inclusion",
            "population_exclusion",
            "host_dependencies",
            "operating_conditions",
            "evidence",
        ):
            with self.subTest(key=key):
                data = self.contract.to_dict()
                del data[key]
                with self.assertRaises(cw.SerializationError):
                    cw.HumanTargetContract.from_dict(data)
                with self.assertRaises(cw.SerializationError):
                    replace(self.contract, **{key: None})

    def test_empty_operating_or_host_inventory_is_not_universal_applicability(self):
        for key in ("host_dependencies", "operating_conditions"):
            with self.subTest(key=key), self.assertRaises(cw.SerializationError):
                replace(self.contract, **{key: ()})
        self.assertEqual(self.contract.evidence, ())
        self.assertEqual(len(self.contract.unresolved_evidence), 8)
        self.assertEqual(self.contract.operating_conditions[0].domain.kind, "unknown")

    def test_recipient_species_and_in_vivo_mode_cannot_be_relabelled(self):
        for key, value in (
            ("recipient_taxon_id", 10090),
            ("recipient_taxon_id", "9606"),
            ("recipient_taxon_id", True),
            ("engineering", "ex_vivo"),
        ):
            with self.subTest(key=key, value=value):
                data = self.contract.to_dict()
                data[key] = value
                with self.assertRaises(cw.SerializationError):
                    cw.HumanTargetContract.from_dict(data)

    def test_unknown_fields_versions_and_downgrade_are_rejected(self):
        mutations = (
            {"schema_version": "cellweave.target.v0.1"},
            {"schema_version": "cellweave.human_target_context.v9"},
            {"human_target": None},
            {"biologically_verified": True},
        )
        for change in mutations:
            with self.subTest(change=change):
                data = self.target.to_dict()
                data.update(change)
                with self.assertRaises(cw.SerializationError):
                    cw.TargetContext.from_dict(data)
        data = self.target.to_dict()
        del data["human_target"]
        with self.assertRaises(cw.SerializationError):
            cw.TargetContext.from_dict(data)

    def test_abstract_and_undeclared_compartments_are_rejected(self):
        for compartments in (("abstract",), ("nucleus",), ()):
            with (
                self.subTest(compartments=compartments),
                self.assertRaises(cw.SerializationError),
            ):
                replace(self.target, compartments=compartments)

    def test_unknown_evidence_reference_rejects_contract(self):
        cited = replace(
            self.contract.cell_subtype, basis="cited", evidence_ids=("missing",)
        )
        with self.assertRaises(cw.SerializationError):
            replace(self.contract, cell_subtype=cited)

    def test_citations_never_discharge_applicability(self):
        for system, taxon_id in (
            ("software_fixture", None),
            ("human_cell_line", 9606),
            ("primary_human_cells", 9606),
            ("human_in_vivo", 9606),
            ("nonhuman_in_vivo", 10090),
        ):
            with self.subTest(system=system):
                evidence = fixture_evidence(system=system, taxon_id=taxon_id)
                cited = replace(
                    self.contract.cell_subtype,
                    basis="cited",
                    evidence_ids=(evidence.id,),
                )
                contract = replace(
                    self.contract, cell_subtype=cited, evidence=(evidence,)
                )
                restored = cw.HumanTargetContract.from_json(contract.to_json())
                self.assertEqual(restored.evidence[0].system, system)
                self.assertEqual(
                    restored.unresolved_evidence, self.contract.unresolved_evidence
                )
                self.assertFalse(hasattr(restored, "passed"))

    def test_claim_cannot_self_declare_verification(self):
        for basis in ("verified", "validated", "pass", "", [], None):
            with self.subTest(basis=basis), self.assertRaises(cw.SerializationError):
                replace(self.contract.cell_state, basis=basis)
        for changes in (
            {"basis": "cited", "evidence_ids": ()},
            {"basis": "assumed", "evidence_ids": ("evidence",)},
            {"limitations": ""},
            {"description": ""},
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaises(cw.SerializationError),
            ):
                replace(self.contract.cell_state, **changes)

    def test_evidence_species_and_system_are_consistent(self):
        for changes in (
            {"system": "human_in_vivo", "taxon_id": 10090},
            {"system": "nonhuman_cells", "taxon_id": 9606},
            {"system": "human_cell_line", "taxon_id": None},
            {"system": "software_fixture", "taxon_id": 9606},
            {"system": "cell_free", "taxon_id": True},
            {"system": "clinical_proof"},
            {"source": cw.PinnedIdentity("model", "model", "1", "a" * 64)},
            {"source": None},
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaises(cw.SerializationError),
            ):
                fixture_evidence(**changes)

    def test_nested_caller_collections_are_frozen_and_duplicates_rejected(self):
        hosts = list(self.contract.host_dependencies)
        conditions = list(self.contract.operating_conditions)
        evidence = [fixture_evidence()]
        contract = replace(
            self.contract,
            host_dependencies=hosts,
            operating_conditions=conditions,
            evidence=evidence,
        )
        identity = contract.fingerprint
        hosts.clear()
        conditions.clear()
        evidence.clear()
        self.assertEqual(contract.fingerprint, identity)
        with self.assertRaises(FrozenInstanceError):
            contract.cell_state = self.contract.cell_subtype
        for key, items in (
            ("host_dependencies", contract.host_dependencies),
            ("operating_conditions", contract.operating_conditions),
            ("evidence", contract.evidence),
        ):
            with self.subTest(key=key), self.assertRaises(cw.SerializationError):
                replace(contract, **{key: items * 2})

    def test_all_applicability_dimensions_change_build_identity(self):
        therapy = cw.Therapy("identity")
        therapy.engineer("recipient", cell_type="T_cell")
        source = therapy.freeze()
        original = cw.BuildRequest.freeze(source, target=self.target)
        variants = []
        for key in self.contract._claim_fields:
            claim = replace(
                getattr(self.contract, key),
                description="Different explicit requirement",
            )
            variants.append(
                replace(
                    self.target, human_target=replace(self.contract, **{key: claim})
                )
            )
        variants.extend(
            (
                replace(self.target, payload_format=cw.PayloadFormat.DNA),
                replace(
                    self.target,
                    human_target=replace(
                        self.contract,
                        host_dependencies=(
                            replace(
                                self.contract.host_dependencies[0],
                                capability="different_host_dependency",
                            ),
                        ),
                    ),
                ),
                replace(
                    self.target,
                    human_target=replace(
                        self.contract,
                        operating_conditions=(
                            replace(
                                self.contract.operating_conditions[0],
                                domain=cw.ValueDomain.interval(0, 1),
                            ),
                        ),
                    ),
                ),
                replace(
                    self.target,
                    human_target=replace(self.contract, evidence=(fixture_evidence(),)),
                ),
            )
        )
        for target in variants:
            with self.subTest(target=target.fingerprint):
                changed = cw.BuildRequest.freeze(source, target=target)
                self.assertNotEqual(changed.fingerprint, original.fingerprint)
                restored = cw.BuildRequest.from_json(changed.to_json())
                self.assertIsInstance(restored.target, cw.HumanTargetContext)
                self.assertEqual(restored.fingerprint, changed.fingerprint)
                self.assertEqual(restored.target, target)

    def test_duplicate_json_invalid_numbers_and_nested_schema_edits_rejected(self):
        text = self.target.to_json()
        bad = text.replace(
            '"payload_format": "RNA"',
            '"payload_format": "RNA", "payload_format": "DNA"',
        )
        with self.assertRaises(cw.SerializationError):
            cw.TargetContext.from_json(bad)
        for data in ([], None, 42, "target"):
            with self.subTest(data=data), self.assertRaises(cw.SerializationError):
                cw.HumanTargetContext.from_dict(data)
        for cls, artifact in (
            (cw.HumanTargetContract, self.contract),
            (cw.TargetClaim, self.contract.cell_state),
            (cw.TargetEvidence, fixture_evidence()),
            (cw.HumanHostDependency, self.contract.host_dependencies[0]),
            (cw.HumanOperatingCondition, self.contract.operating_conditions[0]),
        ):
            data = artifact.to_dict()
            data["schema_version"] = "unexpected.v0.1"
            with self.subTest(cls=cls), self.assertRaises(cw.SerializationError):
                cls.from_dict(data)
        domain = self.contract.operating_conditions[0].to_dict()
        domain["domain"].update(
            kind="scalar_interval", lower=0, upper=float("inf"), reason=None
        )
        with self.assertRaises(cw.SerializationError):
            cw.HumanOperatingCondition.from_dict(domain)

    def test_evidence_edits_change_identity_even_when_claim_text_is_unchanged(self):
        original = replace(self.contract, evidence=(fixture_evidence(),))
        changed = replace(
            original,
            evidence=(
                fixture_evidence(
                    source=cw.PinnedIdentity(
                        "source", "artificial-target-description", "2", "b" * 64
                    )
                ),
            ),
        )
        self.assertNotEqual(original.fingerprint, changed.fingerprint)
        self.assertEqual(original.cell_subtype, changed.cell_subtype)

    def test_planning_and_compilation_keep_human_applicability_unresolved(self):
        therapy = cw.Therapy("human_plan")
        cell = therapy.engineer("recipient", cell_type="T_cell")
        cell.when(cell.external.signal("symbolic_input").present()).do(cell.rest())
        plan = cw.plan(therapy.freeze(), profile=cw.BuildProfile(self.target))
        self.assertFalse(plan.ready)
        self.assertIn(
            "human_target_applicability_unestablished",
            {item.code for item in plan.diagnostics},
        )
        request = plan.freeze_request(artifact_scope="complete_payload")
        for item in (plan, cw.BuildRequest.from_json(request.to_json())):
            with (
                self.subTest(item=type(item)),
                self.assertRaises(cw.CompilationUnavailableError) as error,
            ):
                cw.compile(item)
            self.assertIn(
                "human_target_applicability_unestablished",
                {d.code for d in error.exception.diagnostics},
            )

    def test_cli_inspection_preserves_unresolved_status(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "target.json"
            path.write_text(self.target.to_json())
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(cli_main(["inspect", str(path)]), 0)
            summary = json.loads(output.getvalue())
            self.assertEqual(summary["fingerprint"], self.target.fingerprint)
            self.assertEqual(len(summary["unresolved_evidence"]), 8)
            self.assertIn("no biological or payload admission", summary["inspection"])

    def test_evidence_and_host_order_are_canonical(self):
        extra_host = replace(self.contract.host_dependencies[0], id="another")
        sources = [fixture_evidence(id="a"), fixture_evidence(id="b")]
        first = replace(
            self.contract,
            host_dependencies=(*self.contract.host_dependencies, extra_host),
            evidence=sources,
        )
        second = replace(
            self.contract,
            host_dependencies=(extra_host, *self.contract.host_dependencies),
            evidence=list(reversed(sources)),
        )
        self.assertEqual(first.to_json(), second.to_json())

    def test_invalid_unicode_rejected_at_construction(self):
        with self.assertRaises(cw.SerializationError):
            replace(self.contract.cell_state, description="invalid\ud800")


if __name__ == "__main__":
    unittest.main()

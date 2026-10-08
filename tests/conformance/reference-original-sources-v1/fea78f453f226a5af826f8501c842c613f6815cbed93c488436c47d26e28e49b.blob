"""Synthetic behavior evidence and coding-only references stay distinct."""

from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

import biocompiler as bc
from biocompiler.errors import SerializationError
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.registry.components import ComponentRegistry
from biocompiler.registry.reference_components import (
    ReferenceSelection,
    adapt_reference_component,
)
from biocompiler.registry.references import load_reference_manifest
from biocompiler.synthesis.components import adapt_synthetic_components
from biocompiler.synthesis.synthetic import generate_synthetic
from biocompiler.verification.components import check_composition
from test_synthetic_generation import exercised_history, fixture

FIXTURE = Path(__file__).resolve().parents[1] / "data/references/fap_car/manifest.json"
MANIFEST = PinnedIdentity(
    "reference",
    "wo2022081694a1.murine-fapcar.cds",
    "1",
    "e6bd93305ccf638757844d744c9ce9f8d84bbea4cfed40ba4cb224f28e610102",
)
DNA = PinnedIdentity(
    "reference",
    "wo2022081694a1.murine-fapcar.seq2",
    "1",
    "be64d2c4e6a5887a78c193be6f3aa747460487fa3e0a3a479784a95f58bcad90",
)
RNA = PinnedIdentity(
    "reference",
    "wo2022081694a1.murine-fapcar.seq3",
    "1",
    "8c4deb2c377aa04b1586abdef9eda951418ea3dc04b3146dba2a2bef5b40a5d5",
)


class ComponentAdapterTests(unittest.TestCase):
    def test_accepted_synthetic_ports_and_edges_preserve_exact_meaning(self):
        for contact in (False, True):
            request, sample = fixture(contact=contact)
            candidate = generate_synthetic(request)
            assembled = adapt_synthetic_components(
                request, candidate, exercised_history(sample), until=7
            )
            self.assertEqual(
                check_composition(assembled.composition, assembled.registry).outcome,
                bc.CheckOutcome.PASS,
            )
            records = assembled.registry.resolve(assembled.composition.registry_lock)
            self.assertEqual(
                set(records), {node.id for node in candidate.mechanism.nodes}
            )
            for edge in assembled.composition.connections:
                producer = records[edge.producer_instance].port(edge.producer_port)
                consumer = records[edge.consumer_instance].port(edge.consumer_port)
                self.assertEqual(
                    producer.meaning,
                    candidate.mechanism.get(edge.producer_instance).output.id,
                )
                for key in (
                    "meaning",
                    "dtype",
                    "unit",
                    "scope",
                    "role",
                    "compartment",
                    "domain",
                    "initialization",
                ):
                    self.assertEqual(getattr(producer, key), getattr(consumer, key))
            self.assertTrue(all(not record.resources for record in records.values()))
            self.assertFalse(assembled.composition.resource_pools)
            again = adapt_synthetic_components(
                request, candidate, exercised_history(sample), until=7
            )
            self.assertEqual(assembled.registry.fingerprint, again.registry.fingerprint)
            self.assertEqual(
                assembled.composition.fingerprint, again.composition.fingerprint
            )

    def test_numeric_input_bounds_and_constant_provenance_are_concrete(self):
        request, sample = fixture(numeric=True)
        candidate = generate_synthetic(request)
        history = (
            bc.InputFrame(0, contacts={"x": sample(1, True)}),
            bc.InputFrame(1, contacts={"x": sample(3, True)}),
            bc.InputFrame(5, contacts={"x": sample(2, True)}),
        )
        assembled = adapt_synthetic_components(request, candidate, history, until=7)
        records = assembled.registry.resolve(assembled.composition.registry_lock)
        source = next(
            node
            for node in candidate.mechanism.find("input")
            if node.output.dtype.kind == "scalar"
        )
        port = records[source.id].port("out")
        coordinates = next(iter(records.values())).supported_domain.constraints
        self.assertEqual(
            set(coordinates),
            {
                *(
                    f"observation:{item.signal_id}:{item.field}"
                    for item in request.domain.inputs
                ),
                "concurrent_contacts",
            },
        )
        self.assertEqual(
            (port.domain.lower, port.domain.upper, port.unit), (0, 10, "mol/m^2")
        )
        for node in candidate.mechanism.find("constant"):
            parameter = records[node.id].parameters[0]
            self.assertEqual(
                parameter.value.lower, node.attributes["value"]["canonical_value"]
            )
            self.assertEqual(parameter.value.upper, parameter.value.lower)
            self.assertEqual(parameter.source.content_fingerprint, request.fingerprint)
        self.assertEqual(
            check_composition(assembled.composition, assembled.registry).outcome,
            bc.CheckOutcome.PASS,
        )

    def test_stale_unexercised_and_silent_candidates_cannot_be_adapted(self):
        request, sample = fixture()
        candidate = generate_synthetic(request)
        history = exercised_history(sample)
        for mutation in (
            replace(candidate, request_fingerprint="0" * 64),
            replace(
                candidate,
                mechanism=replace(
                    candidate.mechanism,
                    nodes=tuple(
                        replace(node, inputs=("inactive:response",))
                        if node.kind == "output"
                        else node
                        for node in candidate.mechanism.nodes
                    ),
                ),
            ),
        ):
            with self.assertRaisesRegex(
                SerializationError, "passing synthetic acceptance"
            ):
                adapt_synthetic_components(request, mutation, history, until=7)
        with self.assertRaisesRegex(SerializationError, "passing synthetic acceptance"):
            adapt_synthetic_components(request, candidate, (), until=7)

    def test_fap_reference_adapter_locks_identity_and_keeps_coding_only_scope(self):
        manifest = load_reference_manifest(
            FIXTURE, expected_fingerprint=MANIFEST.content_fingerprint
        )
        for selected in (DNA, RNA):
            with patch(
                "socket.create_connection",
                side_effect=AssertionError("network prohibited"),
            ):
                component = adapt_reference_component(
                    manifest, ReferenceSelection(MANIFEST, selected)
                )
            self.assertEqual(component.classification, "sequence_reference")
            self.assertEqual(
                component.reference_metadata.completeness, "CDS-reference-only"
            )
            self.assertEqual(component.reference_metadata.sequence_length, 1491)
            self.assertIn(
                "full-delivered-molecule-boundaries",
                component.reference_metadata.unknown_features,
            )
            self.assertFalse(
                component.ports
                or component.capabilities
                or component.resources
                or component.dependencies
            )
            self.assertNotIn("model", {item.kind for item in component.identities})
            self.assertIn(selected, component.identities)
            self.assertTrue(
                {source["id"] for source in manifest.sources}
                <= {item.id for item in component.identities}
            )
            self.assertEqual(type(component).from_json(component.to_json()), component)
            registry = ComponentRegistry("reference", "1", (component,))
            self.assertEqual(
                registry.resolve(registry.lock({"cds": component}))["cds"], component
            )

    def test_reference_manifest_version_record_choice_and_hash_mutations_fail(self):
        manifest = load_reference_manifest(FIXTURE)
        selection = ReferenceSelection(MANIFEST, DNA)
        for changed in (
            replace(manifest, version="2"),
            replace(manifest, status="candidate"),
        ):
            with self.assertRaises(SerializationError):
                adapt_reference_component(changed, selection)
        for changed in (
            replace(
                selection, manifest=replace(MANIFEST, content_fingerprint="0" * 64)
            ),
            replace(selection, reference=replace(DNA, version="2")),
            replace(selection, reference=replace(DNA, id=RNA.id)),
            replace(selection, reference=replace(DNA, content_fingerprint="0" * 64)),
        ):
            with self.assertRaises(SerializationError):
                adapt_reference_component(manifest, changed)
        self.assertEqual(ReferenceSelection.from_json(selection.to_json()), selection)


if __name__ == "__main__":
    unittest.main()

"""Circuit scope authority survives imports without promoting biological claims."""

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
import json
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir import circuit_profile as profile_ir
from biocompiler.ir.circuit_profile import (
    BOUNDARIES,
    MAX_ASSAY_CONDITIONS,
    MAX_PROFILE_DEPTH,
    MAX_PROFILE_ITEMS,
    MAX_PROFILE_JSON_BYTES,
    MAX_PROFILE_TEXT_BYTES,
    MAX_SOURCE_PINS,
    PUBLICATION_NEWLINE_BYTES,
    CircuitProfileRequest,
    HumanExperimentContext,
    ImmuneLineage,
    ImmuneRecipientIdentity,
)
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.semantics.context import PayloadFormat, TargetContext
from examples.human_acceptance import make_human_acceptance
from examples.human_target import make_human_target


def recipient_for(target, lineage=ImmuneLineage.T_CELL):
    return ImmuneRecipientIdentity(
        lineage,
        target.fingerprint,
        target.human_target.cell_subtype.fingerprint,
    )


def source_context(**changes):
    # This fixture exercises declared human context; the pin is artificial and
    # conveys no retrieved publication, experimental result or applicability.
    values = {
        "system": "human_cell_line",
        "immune_classification": "nonimmune",
        "cell_identity": "Illustrative human cell-line identity",
        "cell_state": "Source-declared state requiring evidence review",
        "compartment": "cytoplasm",
        "delivery_mode": "rna_delivery",
        "sources": (PinnedIdentity("source", "artificial-context", "1", "a" * 64),),
        "locator": "fixture:context-declaration",
        "assay_conditions": ("Illustrative source conditions; no empirical data.",),
    }
    values.update(changes)
    return HumanExperimentContext(**values)


def product_request(target=None, **changes):
    target = make_human_target() if target is None else target
    values = {
        "purpose": "human_immune_payload",
        "mode": "candidate_design",
        "molecular_form": target.payload_format,
        "boundary": "planning",
        "target": target,
        "recipient": recipient_for(target),
    }
    values.update(changes)
    return CircuitProfileRequest(**values)


def reference_request(**changes):
    values = {
        "purpose": "human_reference",
        "mode": "exact_reproduction",
        "molecular_form": PayloadFormat.RNA,
        "boundary": "import",
        "source_experiment": source_context(),
    }
    values.update(changes)
    return CircuitProfileRequest(**values)


class CircuitProfileTests(unittest.TestCase):
    def test_immutable_strict_roundtrips_preserve_full_identity(self):
        product = product_request()
        artifacts = (
            product.recipient,
            source_context(),
            product,
            reference_request(),
        )
        for original in artifacts:
            with self.subTest(artifact=type(original).__name__):
                restored = type(original).from_json(original.to_json())
                self.assertEqual(restored, original)
                self.assertEqual(restored.to_dict(), original.to_dict())
                self.assertEqual(restored.fingerprint, original.fingerprint)
                field = next(
                    key for key in original.to_dict() if key != "schema_version"
                )
                with self.assertRaises(FrozenInstanceError):
                    setattr(original, field, None)
        self.assertIsInstance(product.recipient.lineage, ImmuneLineage)
        self.assertEqual(product.recipient.eligibility_basis, "declared")
        self.assertEqual(product.recipient.empirical_support, "unestablished")

    def test_every_import_schema_rejects_missing_unknown_or_changed_fields(self):
        artifacts = (product_request().recipient, source_context(), product_request())
        for artifact in artifacts:
            for key in artifact.to_dict():
                with self.subTest(artifact=type(artifact).__name__, missing=key):
                    data = artifact.to_dict()
                    del data[key]
                    with self.assertRaises(SerializationError):
                        type(artifact).from_dict(data)
            for extra in ({"extra": True}, {"schema_version": "unrecognized.v99"}):
                with self.subTest(artifact=type(artifact).__name__, extra=extra):
                    with self.assertRaises(SerializationError):
                        type(artifact).from_dict(artifact.to_dict() | extra)

    def test_python_lineage_and_modality_require_typed_values(self):
        recipient = product_request().recipient
        for value in ("t_cell", "immune", "hepatocyte", True, None):
            with self.subTest(lineage=value), self.assertRaises(SerializationError):
                replace(recipient, lineage=value)
        for value in ("RNA", "protein", True, None):
            with self.subTest(form=value), self.assertRaises(SerializationError):
                replace(product_request(), molecular_form=value)
        data = product_request().to_dict()
        data["recipient"]["lineage"] = "hepatocyte"
        with self.assertRaises(SerializationError):
            CircuitProfileRequest.from_dict(data)

    def test_no_metadata_can_promote_declared_recipient_eligibility(self):
        recipient = product_request().recipient
        for field, value in (
            ("eligibility_basis", "empirically_validated"),
            ("empirical_support", "pass"),
            ("empirical_support", True),
        ):
            with self.subTest(field=field), self.assertRaises(SerializationError):
                replace(recipient, **{field: value})
        data = recipient.to_dict() | {"validated": True}
        with self.assertRaises(SerializationError):
            ImmuneRecipientIdentity.from_dict(data)

    def test_product_requires_human_target_and_typed_recipient_at_every_boundary(self):
        for boundary in BOUNDARIES:
            request = product_request(boundary=boundary)
            self.assertEqual(request.boundary, boundary)
            for changes in (
                {"target": None},
                {"recipient": None},
                {"target": TargetContext("mouse", "1", PayloadFormat.RNA)},
                {"target": TargetContext("human", "1", PayloadFormat.RNA)},
            ):
                with self.subTest(boundary=boundary, changes=changes):
                    with self.assertRaises(SerializationError):
                        replace(request, **changes)

    def test_product_preserves_human_taxon_in_vivo_and_target_modality(self):
        request = product_request()
        for field, value in (("recipient_taxon_id", 10090), ("engineering", "ex_vivo")):
            data = request.to_dict()
            data["target"]["human_target"][field] = value
            with self.subTest(field=field), self.assertRaises(SerializationError):
                CircuitProfileRequest.from_dict(data)
        with self.assertRaises(SerializationError):
            replace(request, molecular_form=PayloadFormat.DNA)
        dna_target = replace(request.target, payload_format=PayloadFormat.DNA)
        dna = product_request(dna_target)
        self.assertEqual(dna.molecular_form, PayloadFormat.DNA)
        self.assertNotEqual(dna.fingerprint, request.fingerprint)

    def test_recipient_pins_invalidate_on_target_or_subtype_changes(self):
        request = product_request()
        for target in (
            replace(request.target, context_version="2"),
            replace(
                request.target,
                human_target=replace(
                    request.target.human_target,
                    cell_subtype=replace(
                        request.target.human_target.cell_subtype,
                        description="Changed human subtype declaration",
                    ),
                ),
            ),
        ):
            with self.subTest(target=target), self.assertRaises(SerializationError):
                replace(request, target=target)
        stale_claim = replace(
            request.recipient, cell_subtype_claim_fingerprint="f" * 64
        )
        with self.assertRaisesRegex(SerializationError, "cell-subtype binding"):
            replace(request, recipient=stale_claim)
        for field in ("target_fingerprint", "cell_subtype_claim_fingerprint"):
            with self.subTest(field=field), self.assertRaises(SerializationError):
                replace(request.recipient, **{field: "not-a-hash"})

    def test_reference_needs_source_context_without_therapeutic_wrapper(self):
        product = product_request()
        for boundary in BOUNDARIES:
            request = reference_request(boundary=boundary)
            self.assertIsNone(request.target)
            self.assertIsNone(request.recipient)
            self.assertIsNone(request.source_request)
            for changes in (
                {"mode": "candidate_design"},
                {"source_experiment": None},
                {"target": product.target},
                {"recipient": product.recipient},
            ):
                with self.subTest(boundary=boundary, changes=changes):
                    with self.assertRaises(SerializationError):
                        replace(request, **changes)
        with self.assertRaises(SerializationError):
            reference_request(source_request=make_human_acceptance())

    def test_source_context_stays_distinct_from_product_target(self):
        original = product_request()
        with_context = replace(original, source_experiment=source_context())
        self.assertEqual(with_context.target, original.target)
        self.assertEqual(with_context.recipient, original.recipient)
        self.assertEqual(
            with_context.source_experiment.immune_classification, "nonimmune"
        )
        self.assertNotEqual(with_context.fingerprint, original.fingerprint)
        altered = replace(
            with_context,
            source_experiment=replace(
                source_context(), cell_state="Another source state"
            ),
        )
        self.assertNotEqual(altered.fingerprint, with_context.fingerprint)
        self.assertEqual(altered.target, original.target)
        self.assertEqual(altered.recipient.empirical_support, "unestablished")

    def test_actual_human_experiment_system_and_classification_are_bounded(self):
        for system in ("human_cell_line", "primary_human_cells", "human_in_vivo"):
            context = source_context(system=system)
            self.assertEqual(context.recipient_taxon_id, 9606)
        for changes in (
            {"recipient_taxon_id": 10090},
            {"recipient_taxon_id": "9606"},
            {"recipient_taxon_id": True},
            {"system": "software_fixture"},
            {"system": "nonhuman_cells"},
            {"system": "cell_free"},
            {"immune_classification": "unknown"},
            {"immune_classification": "immune"},
            {"immune_lineage": ImmuneLineage.T_CELL},
            {"compartment": "abstract"},
            {"delivery_mode": "unspecified_default"},
        ):
            with self.subTest(changes=changes), self.assertRaises(SerializationError):
                source_context(**changes)
        immune = source_context(
            immune_classification="immune",
            immune_lineage=ImmuneLineage.T_CELL,
        )
        self.assertEqual(HumanExperimentContext.from_json(immune.to_json()), immune)
        self.assertEqual(
            source_context(delivery_mode="not_reported").delivery_mode, "not_reported"
        )

    def test_source_context_requires_pins_locator_state_and_conditions(self):
        context = source_context()
        for changes in (
            {"sources": ()},
            {"sources": (replace(context.sources[0], kind="model"),)},
            {"sources": context.sources * 2},
            {
                "sources": (
                    context.sources[0],
                    replace(context.sources[0], content_fingerprint="b" * 64),
                )
            },
            {"locator": ""},
            {"cell_state": ""},
            {"assay_conditions": ()},
            {"assay_conditions": ("same", "same")},
            {"cell_identity": "not\na plain label"},
            {"locator": "bad\ud800"},
        ):
            with self.subTest(changes=changes), self.assertRaises(SerializationError):
                replace(context, **changes)

    def test_source_inventory_copies_mutable_inputs_and_has_stable_order(self):
        first = source_context().sources[0]
        second = replace(first, id="second", content_fingerprint="b" * 64)
        sources = [second, first]
        conditions = ["Explicit conditions requiring review"]
        context = source_context(sources=sources, assay_conditions=conditions)
        saved = context.fingerprint
        sources.clear()
        conditions.append("Later external change")
        self.assertEqual(len(context.sources), 2)
        self.assertEqual(len(context.assay_conditions), 1)
        self.assertEqual(context.fingerprint, saved)
        self.assertEqual(
            context, replace(context, sources=tuple(reversed(context.sources)))
        )

    def test_all_original_source_wrappers_survive_roundtrip(self):
        acceptance = make_human_acceptance()
        for source in (
            acceptance.build_request,
            acceptance.behavior_request,
            acceptance.deployment_request,
            acceptance,
        ):
            with self.subTest(source=type(source).__name__):
                request = product_request(source.target, source_request=source)
                restored = CircuitProfileRequest.from_json(request.to_json())
                self.assertIs(type(restored.source_request), type(source))
                self.assertEqual(restored.source_request.to_dict(), source.to_dict())
                self.assertEqual(restored.target.to_dict(), source.target.to_dict())
                self.assertEqual(restored.fingerprint, request.fingerprint)
        self.assertEqual(
            restored.source_request.acceptance.to_dict(),
            acceptance.acceptance.to_dict(),
        )
        self.assertEqual(
            restored.source_request.deployment_request.deployment.to_dict(),
            acceptance.deployment_request.deployment.to_dict(),
        )

    def test_original_source_target_cannot_be_silently_replaced(self):
        source = make_human_acceptance()
        target = replace(source.target, context_version="different")
        with self.assertRaisesRegex(SerializationError, "full original source target"):
            product_request(target, source_request=source)
        with self.assertRaises(SerializationError):
            product_request(source_request={"target": "unsupported source"})
        data = product_request(source.target, source_request=source).to_dict()
        data["source_request"]["schema_version"] = "future-unhandled-wrapper.v1"
        with self.assertRaises(SerializationError):
            CircuitProfileRequest.from_dict(data)

    def test_full_source_provenance_changes_profile_identity(self):
        source = make_human_acceptance().build_request
        original = product_request(source.target, source_request=source)
        changed_source = replace(
            source,
            provenance=replace(source.provenance, recorded_at="2026-09-30T00:00:00Z"),
        )
        changed = replace(original, source_request=changed_source)
        self.assertNotEqual(changed.fingerprint, original.fingerprint)
        self.assertEqual(changed.source_request.to_dict(), changed_source.to_dict())

    def test_scope_fields_and_operation_boundaries_cannot_be_invented(self):
        request = product_request()
        for field, value in (
            ("purpose", "nonhuman_reference"),
            ("purpose", "general_cell_engineering"),
            ("mode", "optimized_reproduction"),
            ("boundary", "deployment"),
            ("boundary", "skip_checks"),
        ):
            with (
                self.subTest(field=field, value=value),
                self.assertRaises(SerializationError),
            ):
                replace(request, **{field: value})
        for field in ("molecules", "biological_support", "human_therapeutic_admission"):
            with self.subTest(field=field), self.assertRaises(SerializationError):
                CircuitProfileRequest.from_dict(request.to_dict() | {field: "pass"})

    def test_resource_limits_bound_source_inventories_and_text(self):
        pin = source_context().sources[0]
        with self.assertRaises(SerializationError):
            source_context(
                sources=tuple(
                    replace(pin, id=f"source-{i}") for i in range(MAX_SOURCE_PINS + 1)
                )
            )
        with self.assertRaises(SerializationError):
            source_context(
                assay_conditions=tuple(
                    f"condition-{i}" for i in range(MAX_ASSAY_CONDITIONS + 1)
                )
            )
        with self.assertRaisesRegex(SerializationError, "text limit"):
            source_context(cell_identity="x" * (MAX_PROFILE_TEXT_BYTES + 1))
        with self.assertRaisesRegex(SerializationError, "byte limit"):
            CircuitProfileRequest.from_json(" " * (MAX_PROFILE_JSON_BYTES + 1))

    def test_resource_limits_precede_nested_authority_decode(self):
        deep = None
        for _ in range(MAX_PROFILE_DEPTH + 1):
            deep = [deep]
        with self.assertRaisesRegex(SerializationError, "nesting limit"):
            CircuitProfileRequest.from_dict({"nested": deep})
        with self.assertRaisesRegex(SerializationError, "item limit"):
            CircuitProfileRequest.from_dict({"many": [None] * (MAX_PROFILE_ITEMS + 1)})
        with self.assertRaisesRegex(SerializationError, "UTF-8"):
            CircuitProfileRequest.from_dict({"text": "\ud800"})

    def test_pending_items_are_budgeted_before_nested_container_expansion(self):
        class MappingTrap(Mapping):
            def __len__(self):
                return 2

            def __iter__(self):
                raise AssertionError("Oversized mapping must not be expanded.")

            def __getitem__(self, key):
                raise AssertionError("Oversized mapping must not be read.")

        class SequenceTrap(list):
            def __iter__(self):
                raise AssertionError("Oversized sequence must not be expanded.")

        with patch.object(profile_ir, "MAX_PROFILE_ITEMS", 12):
            # This exact-budget ordinary tree remains valid. For each trap,
            # seven siblings already pending leave only three child slots.
            profile_ir._bounded_tree([None] * 11)
            for nested in (MappingTrap(), SequenceTrap([None] * 4)):
                with self.subTest(container=type(nested).__name__):
                    with self.assertRaisesRegex(SerializationError, "item limit"):
                        CircuitProfileRequest.from_dict([None] * 7 + [nested])

    def test_near_limit_pretty_experiment_roundtrip_includes_publication_newline(self):
        data = source_context().to_dict()
        pin = data["sources"][0]
        data["sources"] = [
            pin | {"id": f"p{i:02}" + "i" * 14497, "version": "v" * 14500}
            for i in range(MAX_SOURCE_PINS)
        ]
        data["assay_conditions"] = [
            f"c{i:02}" + "a" * 15977 for i in range(MAX_ASSAY_CONDITIONS)
        ]
        data["cell_identity"] = "c" * 16000

        def published_size():
            return (
                len(
                    json.dumps(
                        data, sort_keys=True, indent=2, ensure_ascii=False
                    ).encode()
                )
                + PUBLICATION_NEWLINE_BYTES
            )

        remaining = MAX_PROFILE_JSON_BYTES - published_size()
        self.assertGreater(remaining, 0)
        self.assertLessEqual(len(data["locator"]) + remaining, MAX_PROFILE_TEXT_BYTES)
        data["locator"] += "l" * remaining
        context = HumanExperimentContext.from_dict(data)
        published = context.to_json() + "\n"
        self.assertEqual(len(published.encode()), MAX_PROFILE_JSON_BYTES)
        self.assertEqual(HumanExperimentContext.from_json(published), context)
        self.assertEqual(
            HumanExperimentContext.from_json(context.to_json(indent=None)), context
        )
        with self.assertRaisesRegex(SerializationError, "byte limit"):
            context.to_json(indent=4)
        with self.assertRaisesRegex(SerializationError, "byte limit"):
            HumanExperimentContext.from_json(published + " ")
        data["locator"] += "l"
        with self.assertRaisesRegex(SerializationError, "byte limit"):
            HumanExperimentContext.from_dict(data)

    def test_full_wrapped_source_has_one_complete_pretty_json_budget(self):
        source = make_human_acceptance()
        data = product_request(source.target, source_request=source).to_dict()
        build = data["source_request"]["deployment_request"]["behavior_request"][
            "build_request"
        ]
        # Archival locations remain part of the full profile identity without
        # changing the behavior fingerprint locked by the acceptance wrapper.
        padding = build["provenance"]["locations"]
        padding.update({"last": "x", "last_extra": "x"})

        def published_size():
            return (
                len(
                    json.dumps(
                        data, sort_keys=True, indent=2, ensure_ascii=False
                    ).encode()
                )
                + PUBLICATION_NEWLINE_BYTES
            )

        base_size = published_size()
        padding["padding-000"] = "x" * MAX_PROFILE_TEXT_BYTES
        block_size = published_size() - base_size
        blocks = (MAX_PROFILE_JSON_BYTES - base_size) // block_size
        padding.update(
            {f"padding-{i:03}": "x" * MAX_PROFILE_TEXT_BYTES for i in range(blocks)}
        )
        remaining = MAX_PROFILE_JSON_BYTES - published_size()
        self.assertGreaterEqual(remaining, 0)
        self.assertLessEqual(remaining, (MAX_PROFILE_TEXT_BYTES - 1) * 2)
        padding["last"] += "x" * min(remaining, MAX_PROFILE_TEXT_BYTES - 1)
        padding["last_extra"] += "x" * max(remaining - MAX_PROFILE_TEXT_BYTES + 1, 0)
        request = CircuitProfileRequest.from_dict(data)
        published = request.to_json() + "\n"
        self.assertEqual(len(published.encode()), MAX_PROFILE_JSON_BYTES)
        restored = CircuitProfileRequest.from_json(published)
        self.assertEqual(restored.fingerprint, request.fingerprint)
        self.assertEqual(restored.source_request.acceptance, source.acceptance)
        self.assertEqual(
            restored.source_request.build_request.provenance.locations, padding
        )
        padding["last_extra"] += "x"
        with self.assertRaisesRegex(SerializationError, "byte limit"):
            CircuitProfileRequest.from_dict(data)

    def test_import_rejects_duplicate_json_keys_and_nonfinite_numbers(self):
        for text in (
            '{"purpose":"human_reference","purpose":"human_immune_payload"}',
            '{"x":NaN}',
        ):
            with self.subTest(text=text), self.assertRaises(SerializationError):
                CircuitProfileRequest.from_json(text)


if __name__ == "__main__":
    unittest.main()

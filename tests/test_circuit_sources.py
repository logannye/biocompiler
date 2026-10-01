"""Metadata-only source authority, coverage gaps and immutable provenance."""

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
import json
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir import circuit_sources as source_ir
from biocompiler.ir.circuit_profile import HumanExperimentContext
from biocompiler.ir.circuit_sources import (
    COVERAGE_FIELDS,
    FAMILY_IDS,
    GAP_STATUSES,
    MAX_DECLARED_BYTE_SIZE,
    MAX_METADATA_DEPTH,
    MAX_METADATA_ITEMS,
    MAX_METADATA_TEXT_BYTES,
    MAX_RECORD_PINS,
    MAX_REVIEW_FINDINGS,
    MAX_SOURCE_CASES,
    MAX_SOURCE_DOCUMENTS,
    MAX_SOURCE_IDS,
    MAX_SOURCE_JSON_BYTES,
    MAX_SOURCE_REVIEWS,
    CircuitSourceCase,
    CircuitSourceInventory,
    SourceDocument,
    SourceGap,
    SourceReview,
)
from biocompiler.ir.component_contracts import PinnedIdentity


def document(**changes):
    values = dict(
        id="source-1",
        version="1",
        title="Artificial metadata fixture; no publication retrieved",
        url="https://example.invalid/source-1",
        record_kind="article",
        access_status="not_retrieved",
        reuse_status="unreviewed",
        reuse_locator=None,
        correction_status="not_checked",
    )
    values.update(changes)
    return SourceDocument(**values)


def receipt_document(**changes):
    # A declared receipt is an artificial string fixture. No file is fetched,
    # embedded or presented as a biological source in these tests.
    return document(
        **(
            dict(
                access_status="retrieved",
                byte_sha256="a" * 64,
                byte_size=123,
                retrieved_at="2026-09-30T00:00:00Z",
            )
            | changes
        )
    )


def gap(field="construct_inventory", **changes):
    return SourceGap(
        **(
            dict(
                field=field, status="not_reviewed", note="Source material not reviewed."
            )
            | changes
        )
    )


def case(**changes):
    return CircuitSourceCase(
        **(
            dict(
                id="case-1",
                family_id="wroblewska_2015_mrna",
                label="Artificial metadata case, no reconstructed circuit",
                source_ids=("source-1",),
                coverage=tuple(gap(field) for field in COVERAGE_FIELDS),
            )
            | changes
        )
    )


def review(**changes):
    return SourceReview(
        **(
            dict(
                id="review-1",
                subject_kind="source",
                subject_fingerprint=document().fingerprint,
                reviewer_kind="software_agent",
                reviewer_id="test-agent",
                method="Declared schema and metadata review only",
                findings=("All availability and biological claims remain unreviewed.",),
            )
            | changes
        )
    )


def inventory(**changes):
    return CircuitSourceInventory(
        **(
            dict(
                id="fixture-inventory",
                version="1",
                sources=(document(),),
                cases=(case(),),
                reviews=(review(),),
            )
            | changes
        )
    )


class CircuitSourceTests(unittest.TestCase):
    def test_indentation_is_bounded_before_serialization(self):
        value = document()
        for indent in (True, False, -1, 9, 10**100, 1.0, " ", " " * 10000, []):
            with (
                self.subTest(indent_type=type(indent).__name__),
                patch.object(
                    SourceDocument,
                    "to_dict",
                    side_effect=AssertionError(
                        "Allocated before indentation validation"
                    ),
                ),
                self.assertRaisesRegex(SerializationError, "indentation"),
            ):
                value.to_json(indent=indent)
        for indent in (None, 0, 1, 8):
            self.assertEqual(
                SourceDocument.from_json(value.to_json(indent=indent)), value
            )

    def test_json_character_preflight_precedes_utf8_allocation(self):
        class EncodingTrap(str):
            def encode(self, *args, **kwargs):
                raise AssertionError("Oversized text was encoded before preflight")

        with patch.object(source_ir, "MAX_SOURCE_JSON_BYTES", 32):
            with self.assertRaisesRegex(SerializationError, "byte limit"):
                SourceDocument.from_json(EncodingTrap(" " * 33))
        with self.assertRaisesRegex(SerializationError, "text limit"):
            SourceDocument.from_dict(
                {"huge": EncodingTrap("x" * (MAX_METADATA_TEXT_BYTES + 1))}
            )
        with self.assertRaisesRegex(SerializationError, "integer exceeds"):
            SourceDocument.from_dict({"huge": 2**65})

    def test_streaming_output_budget_stops_before_remaining_chunks(self):
        value = document()

        def chunks(*args, **kwargs):
            yield " " * 5000
            raise AssertionError("Encoder continued beyond publication budget")

        with (
            patch.object(source_ir, "MAX_SOURCE_JSON_BYTES", 5000),
            patch.object(source_ir.json.JSONEncoder, "iterencode", side_effect=chunks),
            self.assertRaisesRegex(SerializationError, "publication newline"),
        ):
            value.to_json()

    def test_strict_immutable_roundtrips_for_every_record(self):
        for record in (
            document(),
            receipt_document(),
            gap(),
            case(),
            review(),
            inventory(),
        ):
            with self.subTest(record=type(record).__name__):
                restored = type(record).from_json(record.to_json() + "\n")
                self.assertEqual(restored, record)
                self.assertEqual(restored.fingerprint, record.fingerprint)
                self.assertEqual(restored.to_dict(), record.to_dict())
                field = next(
                    key
                    for key in record.to_dict()
                    if key not in {"schema_version", "claim_scope"}
                )
                with self.assertRaises(FrozenInstanceError):
                    setattr(record, field, "changed")

    def test_missing_extra_and_wrong_schema_fields_are_rejected(self):
        for record in (document(), gap(), case(), review(), inventory()):
            for key in record.to_dict():
                data = record.to_dict()
                del data[key]
                with self.subTest(record=type(record).__name__, missing=key):
                    with self.assertRaises(SerializationError):
                        type(record).from_dict(data)
            for change in ({"extra": True}, {"schema_version": "future.v1"}):
                with self.subTest(record=type(record).__name__, change=change):
                    with self.assertRaises(SerializationError):
                        type(record).from_dict(record.to_dict() | change)

    def test_retrieval_receipts_are_all_or_none_without_implying_review(self):
        complete = receipt_document()
        self.assertEqual(complete.reuse_status, "unreviewed")
        self.assertEqual(complete.correction_status, "not_checked")
        for field in ("byte_sha256", "byte_size", "retrieved_at"):
            with self.subTest(missing=field), self.assertRaises(SerializationError):
                replace(complete, **{field: None})
        for status in ("not_retrieved", "unavailable", "restricted"):
            self.assertIsNone(document(access_status=status).byte_sha256)
            with self.subTest(status=status), self.assertRaises(SerializationError):
                replace(complete, access_status=status)
            for field in ("byte_sha256", "byte_size", "retrieved_at"):
                with (
                    self.subTest(status=status, field=field),
                    self.assertRaises(SerializationError),
                ):
                    document(access_status=status, **{field: getattr(complete, field)})

    def test_receipt_hash_size_and_timezone_are_strict_metadata(self):
        for changes in (
            {"byte_sha256": "not-a-digest"},
            {"byte_sha256": "A" * 64},
            {"byte_size": True},
            {"byte_size": -1},
            {"byte_size": 1.0},
            {"byte_size": MAX_DECLARED_BYTE_SIZE + 1},
            {"retrieved_at": "2026-09-30"},
            {"retrieved_at": "2026-09-30T12:00:00"},
            {"retrieved_at": "2026-99-30T12:00:00Z"},
        ):
            with self.subTest(changes=changes), self.assertRaises(SerializationError):
                receipt_document(**changes)
        self.assertEqual(receipt_document(byte_size=0).byte_size, 0)
        self.assertEqual(
            receipt_document(retrieved_at="2026-09-30T12:00:00-07:00").retrieved_at,
            "2026-09-30T12:00:00-07:00",
        )

    def test_metadata_identity_changes_without_relabeling_declared_byte_hash(self):
        source = receipt_document()
        changed = replace(source, title="Changed metadata title")
        self.assertNotEqual(source.fingerprint, source.byte_sha256)
        self.assertNotEqual(source.fingerprint, changed.fingerprint)
        self.assertEqual(source.byte_sha256, changed.byte_sha256)
        for changes in (
            {"url": "https://example.invalid/another-location"},
            {"correction_status": "retracted"},
            {"byte_sha256": "b" * 64},
            {"byte_size": 124},
            {"retrieved_at": "2026-09-30T00:00:01Z"},
        ):
            with self.subTest(changes=changes):
                self.assertNotEqual(
                    replace(source, **changes).fingerprint, source.fingerprint
                )

    def test_source_statuses_url_and_reuse_require_explicit_declarations(self):
        for changes in (
            {"record_kind": "sequence_payload"},
            {"access_status": "probably_public"},
            {"reuse_status": "public_so_permitted"},
            {"correction_status": "validated"},
            {"reuse_status": "permitted"},
            {"reuse_status": "restricted"},
            {"url": "file:///local/path"},
            {"url": "not a URL"},
            {"url": "https://name:secret@example.invalid/source"},
            {"url": "https://example.invalid/a b"},
            {"url": "https://example.invalid:invalid/source"},
        ):
            with self.subTest(changes=changes), self.assertRaises(SerializationError):
                document(**changes)
        for status in ("permitted", "restricted"):
            self.assertEqual(
                document(
                    reuse_status=status,
                    reuse_locator="Declared terms at source page section 2",
                ).reuse_status,
                status,
            )

    def test_author_record_can_preserve_missing_public_url(self):
        source = document(
            record_kind="author_record", url=None, access_status="restricted"
        )
        self.assertIsNone(source.url)
        self.assertEqual(SourceDocument.from_json(source.to_json()), source)
        received = receipt_document(record_kind="author_record", url=None)
        self.assertIsNone(received.url)
        for kind in ("article", "supplement", "deposit"):
            with self.subTest(kind=kind), self.assertRaises(SerializationError):
                document(record_kind=kind, url=None)

    def test_provided_coverage_needs_pinned_located_availability(self):
        pin = PinnedIdentity("source", "source-1", "1", "a" * 64)
        available = gap(
            status="provided",
            source_ids=("source-1",),
            locator="Table S1",
            record_pins=(pin,),
        )
        self.assertEqual(available.status, "provided")
        for changes in (
            {"source_ids": ()},
            {"locator": None},
            {"record_pins": ()},
            {"note": ""},
        ):
            with self.subTest(changes=changes), self.assertRaises(SerializationError):
                replace(available, **changes)
        with self.assertRaises(SerializationError):
            replace(available, record_pins=(replace(pin, kind="model"),))
        for status in GAP_STATUSES - {"provided"}:
            unresolved = gap(status=status)
            self.assertEqual(unresolved.source_ids, ())
            self.assertIsNone(unresolved.locator)
        with self.assertRaises(SerializationError):
            gap(status="complete")

    def test_cases_require_exact_coverage_inventory_and_frozen_human_families(self):
        original = case()
        self.assertEqual({item.field for item in original.coverage}, COVERAGE_FIELDS)
        for family in FAMILY_IDS:
            self.assertEqual(replace(original, family_id=family).family_id, family)
        for changes in (
            {"family_id": "bacterial_general_backend"},
            {"source_ids": ()},
            {"source_ids": ("source-1", "source-1")},
            {"coverage": original.coverage[:-1]},
            {"coverage": original.coverage[:-1] + (original.coverage[0],)},
            {"coverage": original.coverage + (original.coverage[0],)},
        ):
            with self.subTest(changes=changes), self.assertRaises(SerializationError):
                replace(original, **changes)

    def test_unknown_context_stays_unknown_and_declared_context_stays_separate(self):
        original = case()
        self.assertIsNone(original.context)
        context = HumanExperimentContext(
            "human_cell_line",
            "nonimmune",
            "Illustrative cell line",
            "State unreviewed",
            "cytoplasm",
            "not_reported",
            (PinnedIdentity("source", "source-1", "1", "a" * 64),),
            "Artificial context declaration",
            ("Conditions unreviewed",),
        )
        declared = replace(original, context=context)
        restored = CircuitSourceCase.from_json(declared.to_json())
        self.assertEqual(restored.context, context)
        self.assertNotEqual(declared.fingerprint, original.fingerprint)
        self.assertEqual(restored.context.immune_classification, "nonimmune")
        self.assertNotIn("target", declared.to_dict())

    def test_review_scope_cannot_promote_sources_or_biology(self):
        original = review()
        for changes in (
            {"subject_kind": "molecule"},
            {"subject_fingerprint": "invalid"},
            {"reviewer_kind": "authenticated_expert"},
            {"reviewer_id": ""},
            {"method": ""},
            {"findings": ()},
            {"disposition": "validated"},
        ):
            with self.subTest(changes=changes), self.assertRaises(SerializationError):
                replace(original, **changes)
        for reviewer_kind in ("human", "software_agent"):
            self.assertEqual(
                replace(original, reviewer_kind=reviewer_kind).disposition,
                "metadata_review_only",
            )
        with self.assertRaises(SerializationError):
            SourceReview.from_dict(
                original.to_dict() | {"claim_scope": "biological_validation"}
            )
        changed_subject = replace(document(), title="Changed source title")
        self.assertNotEqual(original.subject_fingerprint, changed_subject.fingerprint)

    def test_inventory_history_needs_explicit_link_and_change_reason(self):
        original = inventory()
        for changes in (
            {"previous_inventory_fingerprint": original.fingerprint},
            {"change_reason": "An edit without prior identity"},
            {"previous_inventory_fingerprint": "invalid", "change_reason": "An edit"},
            {
                "previous_inventory_fingerprint": original.fingerprint,
                "change_reason": "",
            },
        ):
            with self.subTest(changes=changes), self.assertRaises(SerializationError):
                replace(original, **changes)
        revised = replace(
            original,
            version="2",
            previous_inventory_fingerprint=original.fingerprint,
            change_reason="Explicit metadata correction",
        )
        self.assertEqual(revised.previous_inventory_fingerprint, original.fingerprint)
        self.assertNotEqual(revised.fingerprint, original.fingerprint)
        self.assertNotEqual(
            replace(revised, change_reason="Another reason").fingerprint,
            revised.fingerprint,
        )

    def test_unresolved_refs_and_duplicate_inventory_ids_remain_checker_inputs(self):
        source = document()
        unresolved = case(source_ids=("missing-source",))
        duplicate = replace(source, title="Conflicting metadata with the same ID")
        record = inventory(
            sources=(source, duplicate),
            cases=(unresolved, unresolved),
            reviews=(review(), review()),
        )
        restored = CircuitSourceInventory.from_json(record.to_json())
        self.assertEqual(restored, record)
        self.assertEqual(len(restored.sources), 2)
        self.assertEqual(restored.cases[0].source_ids, ("missing-source",))
        empty = inventory(sources=(), cases=(), reviews=())
        self.assertEqual(empty.sources, ())
        self.assertNotIn("complete", empty.to_dict())

    def test_inventory_order_is_canonical_and_mutable_inputs_are_copied(self):
        sources = [document(), document(id="source-2")]
        cases = [case(), case(id="case-2")]
        reviews = [review(), review(id="review-2")]
        original = inventory(sources=sources, cases=cases, reviews=reviews)
        reversed_inventory = inventory(
            sources=list(reversed(sources)),
            cases=list(reversed(cases)),
            reviews=list(reversed(reviews)),
        )
        self.assertEqual(original.to_dict(), reversed_inventory.to_dict())
        self.assertEqual(original.fingerprint, reversed_inventory.fingerprint)
        sources.clear()
        cases.clear()
        reviews.clear()
        self.assertEqual(len(original.sources), 2)
        self.assertEqual(
            replace(
                original.cases[0], coverage=tuple(reversed(original.cases[0].coverage))
            ),
            original.cases[0],
        )

    def test_gap_pins_and_review_findings_do_not_alias_callers(self):
        pins = [PinnedIdentity("source", "source-1", "1", "a" * 64)]
        ids = ["source-1"]
        available = gap(
            status="provided", source_ids=ids, locator="Table 1", record_pins=pins
        )
        findings = ["Availability remains a declaration."]
        reviewed = review(findings=findings)
        pins.clear()
        ids.clear()
        findings.clear()
        self.assertEqual(len(available.record_pins), 1)
        self.assertEqual(available.source_ids, ("source-1",))
        self.assertEqual(len(reviewed.findings), 1)

    def test_no_sequence_payload_or_empirical_fields_are_admitted(self):
        for record in (document(), gap(), case(), review(), inventory()):
            for field in (
                "sequence",
                "molecules",
                "empirical_validation",
                "human_admission",
                "complete_payload",
            ):
                with (
                    self.subTest(record=type(record).__name__, field=field),
                    self.assertRaises(SerializationError),
                ):
                    type(record).from_dict(record.to_dict() | {field: "not permitted"})

    def test_array_and_text_limits_are_enforced(self):
        for changes in (
            {"sources": (document(),) * (MAX_SOURCE_DOCUMENTS + 1)},
            {"cases": (case(),) * (MAX_SOURCE_CASES + 1)},
            {"reviews": (review(),) * (MAX_SOURCE_REVIEWS + 1)},
        ):
            with (
                self.subTest(changes=next(iter(changes))),
                self.assertRaises(SerializationError),
            ):
                inventory(**changes)
        for call in (
            lambda: gap(
                record_pins=(PinnedIdentity("source", "s", "1", "a" * 64),)
                * (MAX_RECORD_PINS + 1)
            ),
            lambda: case(source_ids=tuple(f"s{i}" for i in range(MAX_SOURCE_IDS + 1))),
            lambda: review(findings=("A finding",) * (MAX_REVIEW_FINDINGS + 1)),
            lambda: document(title="x" * (MAX_METADATA_TEXT_BYTES + 1)),
        ):
            with self.assertRaises(SerializationError):
                call()

    def test_invalid_text_numbers_duplicate_keys_and_structure_are_bounded(self):
        for text in ('{"id":"first","id":"second"}', '{"x":NaN}'):
            with self.assertRaises(SerializationError):
                CircuitSourceInventory.from_json(text)
        for changes in ({"title": "bad\ud800"}, {"title": "bad\nlabel"}):
            with self.assertRaises(SerializationError):
                document(**changes)
        deep = None
        for _ in range(MAX_METADATA_DEPTH + 1):
            deep = [deep]
        for data, message in (
            ({"deep": deep}, "nesting limit"),
            ({"many": [None] * (MAX_METADATA_ITEMS + 1)}, "item limit"),
            ({"number": float("inf")}, "finite"),
        ):
            with self.assertRaisesRegex(SerializationError, message):
                CircuitSourceInventory.from_dict(data)
        with self.assertRaisesRegex(SerializationError, "byte limit"):
            CircuitSourceInventory.from_json(" " * (MAX_SOURCE_JSON_BYTES + 1))

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

        with patch.object(source_ir, "MAX_METADATA_ITEMS", 12):
            source_ir._bounded_metadata([None] * 11)
            for nested in (MappingTrap(), SequenceTrap([None] * 4)):
                with self.subTest(container=type(nested).__name__):
                    with self.assertRaisesRegex(SerializationError, "item limit"):
                        CircuitSourceInventory.from_dict([None] * 7 + [nested])

    def test_near_limit_inventory_publishes_and_roundtrips_pretty_json(self):
        data = inventory(sources=(), cases=(), reviews=()).to_dict()
        source_data = document().to_dict() | {"title": "t" * 16000}
        data["sources"] = [
            source_data | {"id": f"source-{i:03}"} for i in range(MAX_SOURCE_DOCUMENTS)
        ]
        padded_review = review().to_dict() | {
            "id": "last",
            "method": "x",
            "findings": ["x"],
        }
        data["reviews"] = [padded_review]

        def published_size():
            return (
                len(
                    json.dumps(
                        data, sort_keys=True, indent=2, ensure_ascii=False
                    ).encode()
                )
                + 1
            )

        base_size = published_size()
        regular = review().to_dict() | {
            "id": "r000",
            "findings": ["f" * MAX_METADATA_TEXT_BYTES],
        }
        data["reviews"].append(regular)
        block_size = published_size() - base_size
        count = (MAX_SOURCE_JSON_BYTES - base_size) // block_size
        self.assertLessEqual(count + 1, MAX_SOURCE_REVIEWS)
        data["reviews"] = [padded_review] + [
            regular | {"id": f"r{i:03}"} for i in range(count)
        ]
        remaining = MAX_SOURCE_JSON_BYTES - published_size()
        self.assertGreaterEqual(remaining, 0)
        self.assertLessEqual(remaining, (MAX_METADATA_TEXT_BYTES - 1) * 2)
        padded_review["method"] += "x" * min(remaining, MAX_METADATA_TEXT_BYTES - 1)
        padded_review["findings"][0] += "x" * max(
            remaining - MAX_METADATA_TEXT_BYTES + 1, 0
        )
        record = CircuitSourceInventory.from_dict(data)
        published = record.to_json() + "\n"
        self.assertEqual(len(published.encode()), MAX_SOURCE_JSON_BYTES)
        self.assertEqual(
            CircuitSourceInventory.from_json(published).fingerprint, record.fingerprint
        )
        self.assertEqual(
            CircuitSourceInventory.from_json(record.to_json(indent=None)), record
        )
        with self.assertRaisesRegex(SerializationError, "byte limit"):
            record.to_json(indent=4)
        with self.assertRaisesRegex(SerializationError, "byte limit"):
            CircuitSourceInventory.from_json(published + " ")
        padded_review["findings"][0] += "x"
        with self.assertRaisesRegex(SerializationError, "byte limit"):
            CircuitSourceInventory.from_dict(data)


if __name__ == "__main__":
    unittest.main()

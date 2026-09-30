"""Tiny artificial symbol/annotation transitions, never biological evidence."""

from dataclasses import FrozenInstanceError, dataclass, replace
from types import SimpleNamespace
import unittest

from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_molecules import MoleculeFeature
from biocompiler.ir.circuit_transitions import (
    CHEMISTRY_FACETS,
    MAX_DISPOSITIONS,
    ChemistryDisposition,
    ChemistryTransition,
    FeatureDisposition,
    FeatureTransition,
)
from biocompiler.ir.molecule_chemistry import (
    BaseModification,
    ChemicalIdentity,
    ChemistryClaim,
    TailDeclaration,
    TailLength,
)
from biocompiler.ir.molecule_records import DeclarationProvenance
from biocompiler.semantics.molecule_coordinates import (
    CoordinatePath,
    CoordinateSpace,
    IndexSpan,
)
from biocompiler.verification.circuit_transitions import resolve_transitions
from examples.circuit_molecules import fixture_chemistry, make_molecule


def provenance():
    return DeclarationProvenance(
        "unknown", (), None, "Artificial fixture; no biochemical fate is established."
    )


def path(space, *spans, strand="+"):
    return CoordinatePath(space.id, tuple(IndexSpan(*span) for span in spans), strand)


def frame(length, alphabet="RNA", topology="linear", id="output.space"):
    return CoordinateSpace(
        id,
        alphabet,
        length,
        topology,
        "N_to_C" if alphabet == "protein" else "5prime_to_3prime",
    )


def annotation(
    space,
    id="feature",
    *spans,
    strand="+",
    kind="artificial_region",
    reading_frame=None,
):
    return MoleculeFeature(
        id, kind, path(space, *spans, strand=strand), provenance(), reading_frame
    )


def mod(id="mod", positions=(0,), scope="positions", base="A", accession="inosine"):
    return BaseModification(
        id,
        ChemicalIdentity("biocompiler.chemical", accession, "1"),
        base,
        scope,
        positions,
        provenance(),
    )


@dataclass(frozen=True)
class Segment:
    destination: IndexSpan
    source_id: str
    source_path: CoordinatePath
    rule: str = "copy"


def segment(source, start=0, end=None, destination=0, *, strand="+", rule="copy"):
    end = source.space.length if end is None else end
    return Segment(
        IndexSpan(destination, destination + end - start),
        source.id,
        path(source.space, (start, end), strand=strand),
        rule,
    )


def replacements(inputs, output, changes=()):
    """All facets explicitly redeclared; this does not claim preservation."""
    values = {
        (id, facet): ChemistryDisposition(
            id, facet, "declared_replacement", (facet,), provenance()
        )
        for id in inputs
        for facet in CHEMISTRY_FACETS
    }
    for id, source in inputs.items():
        for item in source.chemistry.modifications:
            key = "modification:" + item.id
            values[id, key] = ChemistryDisposition(
                id, key, "not_carried", (), provenance()
            )
    for item in changes:
        values[item.source_id, item.component] = item
    return ChemistryTransition(
        "explicit_output", output, tuple(values.values()), provenance()
    )


def disposition(source, component, decision="mapped_copy", destinations=None):
    return ChemistryDisposition(
        source.id,
        component,
        decision,
        (component,) if destinations is None else destinations,
        provenance(),
    )


def features(*values, added=()):
    return FeatureTransition(values, added, provenance())


def feature_map(source, decision, outputs=(), feature_id="feature"):
    return FeatureDisposition(source.id, feature_id, decision, outputs, provenance())


def inherited():
    return ChemistryTransition("exact_inheritance", None, (), provenance())


class CircuitTransitionTests(unittest.TestCase):
    def resolve(
        self,
        source,
        spelling,
        *,
        transition=None,
        feature_transition=None,
        output_space=None,
        derivation=None,
        sequence_extent="complete",
    ):
        inputs = source if isinstance(source, dict) else {source.id: source}
        output_space = frame(len(spelling)) if output_space is None else output_space
        if derivation is None:
            derivation = (segment(next(iter(inputs.values()))),)
        return resolve_transitions(
            inherited() if transition is None else transition,
            features() if feature_transition is None else feature_transition,
            inputs=inputs,
            output_sequence=spelling,
            output_space=output_space,
            derivation=derivation,
            sequence_extent=sequence_extent,
        )

    def assert_clean(self, result):
        self.assertEqual(result.diagnostics, ())
        self.assertEqual(result.unsupported, ())

    def test_strict_frozen_roundtrips_and_canonical_disposition_order(self):
        source = make_molecule("source", "ACGU")
        chemistry = replacements({source.id: source}, fixture_chemistry())
        output = annotation(frame(4), "out", (0, 4))
        feature = features(feature_map(source, "exact", (output,)))
        for item in (
            chemistry,
            chemistry.dispositions[0],
            feature,
            feature.dispositions[0],
            inherited(),
        ):
            with self.subTest(type=type(item).__name__):
                restored = type(item).from_json(item.to_json())
                self.assertEqual(item, restored)
                self.assertEqual(item.fingerprint, restored.fingerprint)
                with self.assertRaises(FrozenInstanceError):
                    item.provenance = provenance()
                for key in item.to_dict():
                    data = item.to_dict()
                    del data[key]
                    with self.assertRaises(SerializationError):
                        type(item).from_dict(data)
                with self.assertRaises(SerializationError):
                    type(item).from_dict(item.to_dict() | {"extra": 1})
        self.assertEqual(
            chemistry,
            replace(chemistry, dispositions=tuple(reversed(chemistry.dispositions))),
        )

    def test_constructor_bounds_cardinality_and_duplicate_authority(self):
        source = make_molecule("source", "ACGU")
        item = disposition(source, "cap")
        for call in (
            lambda: replace(item, component="missing"),
            lambda: replace(item, component="modification: invalid"),
            lambda: replace(item, component="modification:"),
            lambda: replace(item, source_id="bad\x7f"),
            lambda: replace(item, decision="preserve_maybe"),
            lambda: replace(item, destination_components=("cap", "cap")),
            lambda: replace(item, decision="not_carried"),
            lambda: ChemistryTransition("explicit_output", None, (), provenance()),
            lambda: ChemistryTransition(
                "exact_inheritance", fixture_chemistry(), (), provenance()
            ),
            lambda: ChemistryTransition(
                "explicit_output", fixture_chemistry(), (item, item), provenance()
            ),
            lambda: ChemistryTransition(
                "explicit_output",
                fixture_chemistry(),
                (item,) * (MAX_DISPOSITIONS + 1),
                provenance(),
            ),
            lambda: feature_map(source, "exact"),
            lambda: feature_map(
                source, "split", (annotation(frame(4), "one", (0, 4)),)
            ),
            lambda: features(
                feature_map(source, "not_carried"),
                feature_map(source, "outside_selection"),
            ),
            lambda: features(
                added=(
                    annotation(frame(4), "same", (0, 2)),
                    annotation(frame(4), "same", (2, 4)),
                )
            ),
        ):
            with self.subTest(call=call), self.assertRaises(SerializationError):
                call()

    def test_modification_selector_keeps_full_valid_occurrence_identity(self):
        occurrence = "a" * 4096
        selected = "modification:" + occurrence
        item = ChemistryDisposition(
            "source", selected, "mapped_copy", (selected,), provenance()
        )
        self.assertEqual(ChemistryDisposition.from_json(item.to_json()), item)
        with self.assertRaises(SerializationError):
            replace(item, component=selected + "a")

    def test_lists_are_snapshotted_and_hostile_json_is_bounded(self):
        source = make_molecule("source", "ACGU")
        items = [disposition(source, "cap")]
        value = ChemistryTransition(
            "explicit_output", fixture_chemistry(), items, provenance()
        )
        items.clear()
        self.assertEqual(len(value.dispositions), 1)
        for bad_indent in (True, -1, 9, 1.5, " " * 1000):
            with self.assertRaises(SerializationError):
                value.to_json(indent=bad_indent)
        cyclic = value.to_dict()
        cyclic["provenance"] = cyclic
        with self.assertRaises(SerializationError):
            ChemistryTransition.from_dict(cyclic)
        data = value.to_dict()
        data["dispositions"] = [value.dispositions[0].to_dict()] * (
            MAX_DISPOSITIONS + 1
        )
        with self.assertRaises(SerializationError):
            ChemistryTransition.from_dict(data)

    def test_exact_identity_relabels_tail_without_dropping_chemistry(self):
        source = make_molecule("source", "CGAAA")
        tail = TailDeclaration(
            "declared",
            "represented_terminal",
            TailLength("exact", exact=3),
            path(source.space, (2, 5)),
            provenance(),
        )
        source = replace(
            source, chemistry=replace(source.chemistry, terminal_tail=tail)
        )
        result = self.resolve(source, source.sequence)
        self.assert_clean(result)
        self.assertEqual(result.chemistry.terminal_tail.path.space_id, "output.space")
        self.assertEqual(
            result.chemistry.nominal_dict(), source.chemistry.nominal_dict()
        )
        self.assertNotEqual(result.chemistry.fingerprint, source.chemistry.fingerprint)

    def test_exact_inheritance_rejects_cuts_and_palindromic_reverse(self):
        source = make_molecule("source", "ACCA")
        for spelling, spans, output_space in (
            ("CC", (segment(source, 1, 3),), frame(2)),
            ("ACCA", (segment(source, strand="-"),), frame(4)),
            ("ACCA", (segment(source),), frame(4, topology="circular")),
            ("ACCA", (segment(source, 0, 2), segment(source, 0, 2, 2)), frame(4)),
        ):
            with self.subTest(spelling=spelling, spans=spans):
                result = self.resolve(
                    source, spelling, derivation=spans, output_space=output_space
                )
                self.assertIsNone(result.chemistry)
                self.assertTrue(result.diagnostics)

    def test_exact_inheritance_rejects_alphabet_rewrite(self):
        source = make_molecule("source", "ACTA", form="delivered_dna")
        result = self.resolve(
            source, "ACUA", derivation=(segment(source, rule="dna_coding_to_rna.v1"),)
        )
        self.assertTrue(
            any("chemistry_exact_inheritance" in item for item in result.diagnostics)
        )

    def test_unknown_chemistry_stays_unknown_and_is_not_strict_success(self):
        source = make_molecule("source", "ACGU")
        source = replace(
            source,
            chemistry=replace(
                source.chemistry, cap=ChemistryClaim("unknown", None, provenance())
            ),
        )
        result = self.resolve(source, source.sequence)
        self.assertEqual(result.diagnostics, ())
        self.assertEqual(result.chemistry.cap.status, "unknown")
        self.assertTrue(
            any("unknown_output_chemistry" in item for item in result.unsupported)
        )

    def test_explicit_replacements_allow_cut_and_many_sources_to_one_facet(self):
        first, second = make_molecule("first", "ACGU"), make_molecule("second", "UA")
        inputs = {first.id: first, second.id: second}
        result = self.resolve(
            inputs,
            "CGUA",
            transition=replacements(inputs, fixture_chemistry()),
            derivation=(segment(first, 1, 3), segment(second, 0, 2, 2)),
        )
        self.assert_clean(result)
        self.assertEqual(result.chemistry, fixture_chemistry())

    def test_mapped_terminal_claim_must_retain_correct_original_boundary(self):
        source = make_molecule("source", "ACGU")
        for facet in ("cap", "start_end"):
            transition = replacements(
                {source.id: source}, fixture_chemistry(), (disposition(source, facet),)
            )
            result = self.resolve(
                source,
                "CGU",
                transition=transition,
                derivation=(segment(source, 1, 4),),
            )
            self.assertTrue(
                any("original boundary" in item for item in result.diagnostics)
            )
        for facet in ("finish_end", "terminal_tail"):
            transition = replacements(
                {source.id: source}, fixture_chemistry(), (disposition(source, facet),)
            )
            result = self.resolve(
                source,
                "ACG",
                transition=transition,
                derivation=(segment(source, 0, 3),),
            )
            self.assertTrue(result.diagnostics)

    def test_mapped_end_identity_and_reverse_are_checked(self):
        source = make_molecule("source", "ACGU")
        changed = replace(
            source.chemistry,
            start_end=ChemistryClaim(
                "declared", ChemicalIdentity("fixture", "other", "1"), provenance()
            ),
        )
        transition = replacements(
            {source.id: source}, changed, (disposition(source, "start_end"),)
        )
        self.assertTrue(
            self.resolve(source, source.sequence, transition=transition).diagnostics
        )
        transition = replacements(
            {source.id: source}, source.chemistry, (disposition(source, "start_end"),)
        )
        self.assertTrue(
            self.resolve(
                source,
                "UGCA",
                transition=transition,
                derivation=(segment(source, strand="-"),),
            ).diagnostics
        )

    def test_chemistry_inventory_is_exhaustive_and_unknown_is_preserved(self):
        source = make_molecule("source", "ACGU")
        transition = replacements({source.id: source}, source.chemistry)
        missing = replace(transition, dispositions=transition.dispositions[:-1])
        self.assertTrue(
            any(
                "disposition_inventory" in item
                for item in self.resolve(
                    source, source.sequence, transition=missing
                ).diagnostics
            )
        )
        drop = replacements(
            {source.id: source},
            source.chemistry,
            (disposition(source, "cap", "not_carried", ()),),
        )
        self.assertTrue(
            any(
                "destination_inventory" in item
                for item in self.resolve(
                    source, source.sequence, transition=drop
                ).diagnostics
            )
        )
        unresolved = replacements(
            {source.id: source},
            source.chemistry,
            (disposition(source, "cap", "unknown"),),
        )
        result = self.resolve(source, source.sequence, transition=unresolved)
        self.assertEqual(result.diagnostics, ())
        self.assertTrue(
            any("unknown_chemistry_disposition" in item for item in result.unsupported)
        )

    def test_mapped_modifications_follow_selected_sites_and_chemical_identity(self):
        source = make_molecule(
            "source",
            "ACAA",
            chemistry=replace(
                fixture_chemistry(), modifications=(mod(positions=(0, 2, 3)),)
            ),
        )
        mapped = disposition(
            source, "modification:mod", destinations=("modification:result",)
        )
        output = replace(fixture_chemistry(), modifications=(mod("result", (1, 2)),))
        result = self.resolve(
            source,
            "CAA",
            transition=replacements({source.id: source}, output, (mapped,)),
            derivation=(segment(source, 1, 4),),
        )
        self.assert_clean(result)
        for bad in (
            mod("result", (2,)),
            mod("result", (0, 1, 2)),
            replace(
                mod("result", (1, 2)),
                identity=ChemicalIdentity("fixture", "other", "1"),
            ),
        ):
            transition = replacements(
                {source.id: source}, replace(output, modifications=(bad,)), (mapped,)
            )
            self.assertTrue(
                self.resolve(
                    source,
                    "CAA",
                    transition=transition,
                    derivation=(segment(source, 1, 4),),
                ).diagnostics
            )

    def test_all_matching_policy_maps_only_selected_core_sites(self):
        source = make_molecule(
            "source",
            "AACAA",
            chemistry=replace(
                fixture_chemistry(),
                modifications=(mod(positions=(), scope="all_matching_bases"),),
            ),
        )
        mapped = disposition(
            source, "modification:mod", destinations=("modification:result",)
        )
        output = replace(fixture_chemistry(), modifications=(mod("result", (0, 2)),))
        result = self.resolve(
            source,
            "ACA",
            transition=replacements({source.id: source}, output, (mapped,)),
            derivation=(segment(source, 1, 4),),
        )
        self.assert_clean(result)

    def test_separate_source_modifications_can_merge_into_one_output_occurrence(self):
        first = make_molecule(
            "first",
            "AA",
            chemistry=replace(
                fixture_chemistry(), modifications=(mod(positions=(0,)),)
            ),
        )
        second = make_molecule(
            "second",
            "AA",
            chemistry=replace(
                fixture_chemistry(), modifications=(mod(positions=(1,)),)
            ),
        )
        inputs = {first.id: first, second.id: second}
        output = replace(fixture_chemistry(), modifications=(mod("merged", (0, 3)),))
        changes = tuple(
            disposition(
                source, "modification:mod", destinations=("modification:merged",)
            )
            for source in inputs.values()
        )
        result = self.resolve(
            inputs,
            "AAAA",
            transition=replacements(inputs, output, changes),
            derivation=(segment(first), segment(second, destination=2)),
        )
        self.assert_clean(result)

    def test_rewriting_cannot_claim_automatic_modified_chemistry_inheritance(self):
        source = make_molecule(
            "source",
            "AC",
            form="delivered_dna",
            chemistry=replace(fixture_chemistry("DNA"), modifications=(mod(),)),
        )
        output = replace(fixture_chemistry(), modifications=(mod("result"),))
        mapped = disposition(
            source, "modification:mod", destinations=("modification:result",)
        )
        result = self.resolve(
            source,
            "AC",
            transition=replacements({source.id: source}, output, (mapped,)),
            derivation=(segment(source, rule="dna_coding_to_rna.v1"),),
        )
        self.assertTrue(any("symbol rewriting" in item for item in result.diagnostics))
        explicit = replace(mapped, decision="declared_replacement")
        self.assert_clean(
            self.resolve(
                source,
                "AC",
                transition=replacements({source.id: source}, output, (explicit,)),
                derivation=(segment(source, rule="dna_coding_to_rna.v1"),),
            )
        )

    def test_mapped_inventory_cannot_resolve_unknown_status(self):
        source = make_molecule(
            "source",
            "ACGU",
            chemistry=replace(
                fixture_chemistry(), modification_inventory_status="unknown"
            ),
        )
        transition = replacements(
            {source.id: source},
            fixture_chemistry(),
            (disposition(source, "modification_inventory"),),
        )
        self.assertTrue(
            self.resolve(source, source.sequence, transition=transition).diagnostics
        )

    def test_tail_mapping_requires_exact_coverage_and_terminal_position(self):
        source = make_molecule("source", "CGAAA")
        tail = TailDeclaration(
            "declared",
            "represented_terminal",
            TailLength("exact", exact=3),
            path(source.space, (2, 5)),
            provenance(),
        )
        source = replace(
            source, chemistry=replace(source.chemistry, terminal_tail=tail)
        )
        output = replace(
            fixture_chemistry(),
            terminal_tail=replace(tail, path=path(frame(4), (1, 4))),
        )
        mapped = disposition(source, "terminal_tail")
        self.assert_clean(
            self.resolve(
                source,
                "GAAA",
                transition=replacements({source.id: source}, output, (mapped,)),
                derivation=(segment(source, 1, 5),),
            )
        )
        output = replace(
            output,
            terminal_tail=replace(
                tail, length=TailLength("exact", exact=2), path=path(frame(3), (1, 3))
            ),
        )
        self.assertTrue(
            self.resolve(
                source,
                "GAA",
                transition=replacements({source.id: source}, output, (mapped,)),
                derivation=(segment(source, 1, 4),),
            ).diagnostics
        )

    def test_exact_core_is_not_an_exact_molecule_or_a_known_terminal_boundary(self):
        tail = TailDeclaration(
            "declared", "appended_terminal", TailLength("unknown"), None, provenance()
        )
        source = make_molecule(
            "source",
            "ACG",
            chemistry=replace(fixture_chemistry(), terminal_tail=tail),
            sequence_extent="exact_core",
        )
        self.assertTrue(
            self.resolve(source, "ACG", sequence_extent="exact_core").diagnostics
        )
        transition = replacements(
            {source.id: source},
            fixture_chemistry(),
            (disposition(source, "finish_end"),),
        )
        self.assertTrue(self.resolve(source, "ACG", transition=transition).diagnostics)

    def test_exact_feature_mapping_and_reading_frame_preserve_geometry(self):
        source = make_molecule("source", "ACGUAC")
        original = annotation(
            source.space, "feature", (1, 4), kind="CDS", reading_frame=1
        )
        source = replace(source, features=(original,))
        mapped = replace(original, id="mapped", path=path(frame(6), (1, 4)))
        result = self.resolve(
            source,
            source.sequence,
            feature_transition=features(feature_map(source, "exact", (mapped,))),
        )
        self.assert_clean(result)
        self.assertEqual(result.features, (mapped,))
        for changed in (
            replace(mapped, path=path(frame(6), (2, 5))),
            replace(mapped, kind="other"),
            replace(mapped, reading_frame=2),
        ):
            self.assertTrue(
                self.resolve(
                    source,
                    source.sequence,
                    feature_transition=features(
                        feature_map(source, "exact", (changed,))
                    ),
                ).diagnostics
            )

    def test_partial_feature_requires_proper_subset_and_preserved_order(self):
        source = make_molecule("source", "ACGUAC")
        source = replace(
            source, features=(annotation(source.space, "feature", (1, 5)),)
        )
        mapped = annotation(frame(3), "mapped", (0, 3))
        transition = replacements({source.id: source}, fixture_chemistry())
        result = self.resolve(
            source,
            "GUA",
            transition=transition,
            derivation=(segment(source, 2, 5),),
            feature_transition=features(feature_map(source, "partial", (mapped,))),
        )
        self.assert_clean(result)
        self.assertTrue(
            self.resolve(
                source,
                "GUA",
                transition=transition,
                derivation=(segment(source, 2, 5),),
                feature_transition=features(feature_map(source, "exact", (mapped,))),
            ).diagnostics
        )
        whole = annotation(frame(6), "mapped", (1, 5))
        self.assertTrue(
            self.resolve(
                source,
                source.sequence,
                feature_transition=features(feature_map(source, "partial", (whole,))),
            ).diagnostics
        )

    def test_split_feature_must_cover_every_selected_occurrence(self):
        source = make_molecule("source", "ACGU")
        source = replace(
            source, features=(annotation(source.space, "feature", (0, 2)),)
        )
        first, second = (
            annotation(frame(4), "first", (0, 2)),
            annotation(frame(4), "second", (2, 4)),
        )
        derivation = (segment(source, 0, 2), segment(source, 0, 2, 2))
        transition = replacements({source.id: source}, fixture_chemistry())
        result = self.resolve(
            source,
            "ACAC",
            transition=transition,
            derivation=derivation,
            feature_transition=features(feature_map(source, "split", (first, second))),
        )
        self.assert_clean(result)
        bad = replace(second, path=path(frame(4), (2, 3)))
        self.assertTrue(
            self.resolve(
                source,
                "ACAC",
                transition=transition,
                derivation=derivation,
                feature_transition=features(feature_map(source, "split", (first, bad))),
            ).diagnostics
        )

    def test_reverse_and_cross_origin_feature_mapping_respect_explicit_traversal(self):
        source = make_molecule("source", "ACGU")
        source = replace(
            source, features=(annotation(source.space, "feature", (0, 3)),)
        )
        mapped = annotation(frame(4), "mapped", (1, 4), strand="-")
        transition = replacements({source.id: source}, fixture_chemistry())
        self.assert_clean(
            self.resolve(
                source,
                "UGCA",
                transition=transition,
                derivation=(segment(source, strand="-"),),
                feature_transition=features(feature_map(source, "exact", (mapped,))),
            )
        )
        wrong = replace(mapped, path=replace(mapped.path, strand="+"))
        self.assertTrue(
            self.resolve(
                source,
                "UGCA",
                transition=transition,
                derivation=(segment(source, strand="-"),),
                feature_transition=features(feature_map(source, "exact", (wrong,))),
            ).diagnostics
        )
        circle = make_molecule("circle", "ACGU", topology="circular")
        circle = replace(
            circle, features=(annotation(circle.space, "feature", (3, 4), (0, 2)),)
        )
        mapped = annotation(frame(3), "mapped", (0, 3))
        selected = Segment(
            IndexSpan(0, 3), circle.id, path(circle.space, (3, 4), (0, 2))
        )
        self.assert_clean(
            self.resolve(
                circle,
                "UAC",
                transition=replacements({circle.id: circle}, fixture_chemistry()),
                derivation=(selected,),
                feature_transition=features(feature_map(circle, "exact", (mapped,))),
            )
        )

    def test_outside_selection_requires_real_disjointness_but_not_carried_is_explicit(
        self,
    ):
        source = make_molecule("source", "ACGU")
        source = replace(
            source, features=(annotation(source.space, "feature", (2, 4)),)
        )
        transition = replacements({source.id: source}, fixture_chemistry())
        outside = features(feature_map(source, "outside_selection"))
        self.assert_clean(
            self.resolve(
                source,
                "AC",
                transition=transition,
                derivation=(segment(source, 0, 2),),
                feature_transition=outside,
            )
        )
        self.assertTrue(
            self.resolve(
                source, source.sequence, feature_transition=outside
            ).diagnostics
        )
        self.assert_clean(
            self.resolve(
                source,
                source.sequence,
                feature_transition=features(feature_map(source, "not_carried")),
            )
        )

    def test_feature_inventory_unknown_boundaries_and_partial_coding_are_explicit(self):
        source = make_molecule("source", "ACGU")
        original = annotation(
            source.space, "feature", (0, 4), kind="CDS", reading_frame=0
        )
        source = replace(source, features=(original,))
        self.assertTrue(self.resolve(source, source.sequence).diagnostics)
        unknown = self.resolve(
            source,
            source.sequence,
            feature_transition=features(feature_map(source, "unknown")),
        )
        self.assertEqual(unknown.diagnostics, ())
        self.assertTrue(unknown.unsupported)
        mapped = replace(original, id="mapped", path=path(frame(2), (0, 2)))
        partial = self.resolve(
            source,
            "AC",
            transition=replacements({source.id: source}, fixture_chemistry()),
            derivation=(segment(source, 0, 2),),
            feature_transition=features(feature_map(source, "partial", (mapped,))),
        )
        self.assertEqual(partial.diagnostics, ())
        self.assertTrue(
            any("partial_coding_feature_frame" in item for item in partial.unsupported)
        )
        boundary = replace(
            source, features=(annotation(source.space, "feature", (2, 2)),)
        )
        result = self.resolve(
            boundary,
            boundary.sequence,
            feature_transition=features(feature_map(boundary, "outside_selection")),
        )
        self.assertTrue(
            any(
                "unresolved_source_feature_geometry" in item
                for item in result.unsupported
            )
        )

    def test_new_features_are_explicit_and_unknown_or_wrong_frames_refuse_success(self):
        source = make_molecule("source", "ACGU")
        added = annotation(frame(4), "new", (0, 2))
        self.assert_clean(
            self.resolve(
                source, source.sequence, feature_transition=features(added=(added,))
            )
        )
        wrong = replace(added, path=replace(added.path, space_id="different"))
        self.assertTrue(
            self.resolve(
                source, source.sequence, feature_transition=features(added=(wrong,))
            ).diagnostics
        )
        unknown = replace(added, path=None)
        result = self.resolve(
            source, source.sequence, feature_transition=features(added=(unknown,))
        )
        self.assertTrue(result.unsupported)

    def test_derivation_rejects_missing_extra_unbounded_or_invalid_source_values(self):
        source = make_molecule("source", "ACGU")
        first = segment(source)
        other = make_molecule("other", "ACGU")
        for inputs, derivation in (
            ({}, (first,)),
            ({source.id: source, other.id: other}, (first,)),
            ({source.id: source}, (replace(first, source_id="absent"),)),
            ({source.id: source}, (replace(first, destination=IndexSpan(1, 4)),)),
            ({source.id: source}, (replace(first, rule="implicit_translation"),)),
            (
                {source.id: source},
                (replace(first, source_path=path(frame(4), (0, 4))),),
            ),
            ({source.id: SimpleNamespace(space=source.space)}, (first,)),
        ):
            with self.subTest(inputs=inputs):
                result = self.resolve(inputs, "ACGU", derivation=derivation)
                self.assertTrue(
                    any("transition_derivation" in item for item in result.diagnostics)
                )

    def test_editing_rule_preserves_coordinate_geometry_but_not_chemistry_claims(self):
        source = make_molecule("source", "ACGU")
        source = replace(
            source, features=(annotation(source.space, "feature", (0, 4)),)
        )
        mapped = annotation(frame(4), "mapped", (0, 4))
        feature_transition = features(feature_map(source, "exact", (mapped,)))
        derivation = (segment(source, rule="rna_editing.v1"),)
        self.assert_clean(
            self.resolve(
                source,
                "GCGU",
                transition=replacements({source.id: source}, fixture_chemistry()),
                feature_transition=feature_transition,
                derivation=derivation,
            )
        )
        for facet in CHEMISTRY_FACETS:
            transition = replacements(
                {source.id: source},
                fixture_chemistry(),
                (disposition(source, facet),),
            )
            result = self.resolve(
                source,
                "GCGU",
                transition=transition,
                feature_transition=feature_transition,
                derivation=derivation,
            )
            self.assertTrue(
                any(
                    "RNA editing or codon translation" in item
                    for item in result.diagnostics
                )
            )

    def test_translation_rule_requires_three_to_one_rna_to_protein_geometry(self):
        source = make_molecule("source", "AUGGCUUAA")
        target = frame(2, alphabet="protein")
        derived = Segment(
            IndexSpan(0, 2),
            source.id,
            path(source.space, (0, 6)),
            "translation_codon.v1",
        )
        transition = replacements({source.id: source}, fixture_chemistry("protein"))
        self.assert_clean(
            self.resolve(
                source,
                "MA",
                transition=transition,
                output_space=target,
                derivation=(derived,),
            )
        )
        for changed in (
            replace(derived, source_path=path(source.space, (0, 2))),
            replace(derived, source_path=path(source.space, (0, 6), strand="-")),
            replace(derived, source_path=path(source.space, (0, 3), (6, 9))),
            replace(derived, rule="copy"),
            replace(derived, rule="rna_editing.v1"),
        ):
            result = self.resolve(
                source,
                "MA",
                transition=transition,
                output_space=target,
                derivation=(changed,),
            )
            self.assertTrue(
                any("transition_derivation" in item for item in result.diagnostics)
            )
        dna = make_molecule("dna", "ATGGCTTAA", form="delivered_dna")
        result = self.resolve(
            dna,
            "MA",
            transition=replacements({dna.id: dna}, fixture_chemistry("protein")),
            output_space=target,
            derivation=(
                replace(derived, source_id=dna.id, source_path=path(dna.space, (0, 6))),
            ),
        )
        self.assertTrue(result.diagnostics)

    def test_translation_never_copies_molecular_chemistry_facets(self):
        source = make_molecule("source", "AUGGCUUAA")
        derived = Segment(
            IndexSpan(0, 2),
            source.id,
            path(source.space, (0, 6)),
            "translation_codon.v1",
        )
        for facet in CHEMISTRY_FACETS:
            transition = replacements(
                {source.id: source},
                fixture_chemistry("protein"),
                (disposition(source, facet),),
            )
            result = self.resolve(
                source,
                "MA",
                transition=transition,
                output_space=frame(2, alphabet="protein"),
                derivation=(derived,),
            )
            self.assertTrue(
                any(
                    "RNA editing or codon translation" in item
                    for item in result.diagnostics
                )
            )

    def test_translation_annotation_mapping_is_unsupported_without_positional_inference(
        self,
    ):
        source = make_molecule("source", "AUGGCUUAA")
        source = replace(
            source, features=(annotation(source.space, "feature", (0, 6)),)
        )
        target = frame(2, alphabet="protein")
        derived = Segment(
            IndexSpan(0, 2),
            source.id,
            path(source.space, (0, 6)),
            "translation_codon.v1",
        )
        transition = replacements({source.id: source}, fixture_chemistry("protein"))
        mapped = annotation(target, "mapped", (0, 2))
        for decision, outputs in (
            ("exact", (mapped,)),
            ("partial", (mapped,)),
            (
                "split",
                (annotation(target, "one", (0, 1)), annotation(target, "two", (1, 2))),
            ),
        ):
            result = self.resolve(
                source,
                "MA",
                transition=transition,
                output_space=target,
                derivation=(derived,),
                feature_transition=features(feature_map(source, decision, outputs)),
            )
            self.assertEqual(result.diagnostics, ())
            self.assertTrue(
                any(
                    "translation_feature_mapping" in item for item in result.unsupported
                )
            )
        self.assert_clean(
            self.resolve(
                source,
                "MA",
                transition=transition,
                output_space=target,
                derivation=(derived,),
                feature_transition=features(
                    feature_map(source, "not_carried"), added=(mapped,)
                ),
            )
        )

    def test_translation_outside_selection_is_checked_in_original_source_coordinates(
        self,
    ):
        source = make_molecule("source", "AUGGCUUAA")
        source = replace(
            source, features=(annotation(source.space, "feature", (6, 9)),)
        )
        derived = Segment(
            IndexSpan(0, 2),
            source.id,
            path(source.space, (0, 6)),
            "translation_codon.v1",
        )
        transition = replacements({source.id: source}, fixture_chemistry("protein"))
        outside = features(feature_map(source, "outside_selection"))
        self.assert_clean(
            self.resolve(
                source,
                "MA",
                transition=transition,
                output_space=frame(2, alphabet="protein"),
                derivation=(derived,),
                feature_transition=outside,
            )
        )
        overlapping = replace(
            source, features=(annotation(source.space, "feature", (5, 9)),)
        )
        result = self.resolve(
            overlapping,
            "MA",
            transition=transition,
            output_space=frame(2, alphabet="protein"),
            derivation=(derived,),
            feature_transition=outside,
        )
        self.assertTrue(any("Outside-selection" in item for item in result.diagnostics))

    def test_editing_rule_requires_rna_and_one_to_one_residue_count(self):
        for source in (
            make_molecule("dna", "ACGT", form="delivered_dna"),
            make_molecule("protein", "ACGT", form="mature_protein"),
        ):
            result = self.resolve(
                source,
                "ACGT",
                transition=replacements({source.id: source}, source.chemistry),
                output_space=frame(4, alphabet=source.space.alphabet),
                derivation=(segment(source, rule="rna_editing.v1"),),
            )
            self.assertTrue(result.diagnostics)
        source = make_molecule("rna", "ACGU")
        derived = replace(
            segment(source, rule="rna_editing.v1"), destination=IndexSpan(0, 3)
        )
        result = self.resolve(
            source,
            "CGU",
            transition=replacements({source.id: source}, source.chemistry),
            derivation=(derived,),
        )
        self.assertTrue(result.diagnostics)


if __name__ == "__main__":
    unittest.main()

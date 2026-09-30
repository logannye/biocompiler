"""Producer-only declared editing and translation; no biological interpretation.

The independent checker must not import this module. Codon rules apply only to
explicit supplied spans and bound conditional readouts, never inferred ORFs.
"""

from dataclasses import replace

from biocompiler.artifacts.circuit_construction import (
    ConstructedValue,
    ConsumedSegment,
    DerivedSegment,
)
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_construction import (
    BaseEditingOperation,
    ConditionalTranslationOperation,
    MultiORFTranslationOperation,
    RibosomalSkippingOperation,
    TranslationOperation,
)
from biocompiler.ir.circuit_recoding import STANDARD_RNA_CODON_TABLE
from biocompiler.semantics.molecule_coordinates import (
    CoordinatePath,
    CoordinateSpace,
    IndexSpan,
)


class _Problem(Exception):
    pass


def _require(value, code):
    if not value:
        raise _Problem(code)


def _path(selection, value):
    path = selection.path or CoordinatePath(
        value.space.id, (IndexSpan(0, value.space.length),), "+"
    )
    try:
        path.validate_for(value.space)
    except SerializationError as error:
        raise _Problem("invalid_selection") from error
    _require(path.length > 0, "invalid_selection")
    return path


def _chemical_key(identity, parent):
    return (
        None
        if identity is None
        else (parent, identity.namespace, identity.accession, identity.version)
    )


def _modifications(chemistry):
    policies, sites = {}, {}
    for modification in chemistry.modifications:
        value = _chemical_key(modification.identity, modification.canonical_base)
        if modification.scope == "all_matching_bases":
            policies[modification.canonical_base] = value
        else:
            sites.update((position, value) for position in modification.positions)
    return policies, sites


def _at(view, sequence, position):
    policies, sites = view
    return sites.get(position, policies.get(sequence[position]))


def _chemistry(port, source):
    transition = port.chemistry_transition
    if transition.mode == "explicit_output":
        return transition.output
    tail = source.chemistry.terminal_tail
    if tail.path is not None:
        tail = replace(tail, path=replace(tail.path, space_id=port.space_id))
    return replace(source.chemistry, terminal_tail=tail)


def _value(step, port, source, sequence, topology, segments, consumed=()):
    alphabet = "protein" if segments[0].rule == "translation_codon.v1" else "RNA"
    _require(port.alphabet == alphabet, "unsupported_alphabet")
    _require(port.topology == topology, "unsupported_topology")
    frame = CoordinateSpace(
        port.space_id,
        alphabet,
        len(sequence),
        topology,
        "N_to_C" if alphabet == "protein" else "5prime_to_3prime",
    )
    features = (
        tuple(
            feature
            for disposition in port.feature_transition.dispositions
            for feature in disposition.outputs
        )
        + port.feature_transition.added
    )
    return ConstructedValue(
        port.id,
        frame,
        sequence,
        _chemistry(port, source),
        features,
        tuple(segments),
        step.id,
        consumed=tuple(consumed),
    )


def _edited(step, source):
    operation, port = step.operation, step.ports[0]
    _require(source.space.alphabet == "RNA", "unsupported_alphabet")
    target_chemistry = _chemistry(port, source)
    _require(
        source.chemistry.modification_inventory_status
        == target_chemistry.modification_inventory_status
        == "declared",
        "unsupported_edit_chemistry",
    )
    old_view, new_view = (
        _modifications(source.chemistry),
        _modifications(target_chemistry),
    )
    for facet in ("cap", "start_end", "finish_end"):
        _require(
            getattr(source.chemistry, facet).nominal_dict()
            == getattr(target_chemistry, facet).nominal_dict(),
            "invalid_edit",
        )
    letters = list(source.sequence)
    expected_changes = {}
    for edit in operation.canonical_edits:
        _require(
            edit.position < len(letters) and letters[edit.position] == edit.expected,
            "invalid_edit",
        )
        _require(_at(old_view, source.sequence, edit.position) is None, "invalid_edit")
        letters[edit.position] = edit.replacement
        expected_changes[edit.position] = None
    for edit in operation.chemical_edits:
        _require(
            edit.position < len(letters) and letters[edit.position] == edit.parent,
            "invalid_edit",
        )
        _require(
            _at(old_view, source.sequence, edit.position)
            == _chemical_key(edit.before, edit.parent),
            "invalid_edit",
        )
        expected_changes[edit.position] = _chemical_key(edit.after, edit.parent)
    sequence = "".join(letters)
    for position in range(len(sequence)):
        before = _at(old_view, source.sequence, position)
        _require(
            _at(new_view, sequence, position) == expected_changes.get(position, before),
            "invalid_edit",
        )
    path = CoordinatePath(source.space.id, (IndexSpan(0, len(sequence)),), "+")
    segment = DerivedSegment(
        IndexSpan(0, len(sequence)), operation.input.value.id, path, "rna_editing.v1"
    )
    return _value(step, port, source, sequence, source.space.topology, (segment,))


def _translation_span(selection, source):
    _require(source.space.alphabet == "RNA", "unsupported_alphabet")
    path = _path(selection, source)
    _require(
        path.strand == "+" and len(path.spans) == 1, "unsupported_translation_path"
    )
    _require(path.length >= 6 and path.length % 3 == 0, "invalid_translation")
    return path.spans[0]


def _translate(source, span, policy):
    _require(
        source.chemistry.modification_inventory_status == "declared",
        "unsupported_translation_chemistry",
    )
    _require(
        source.sequence[span.start : span.start + 3] == "AUG", "invalid_translation"
    )
    codon_count = span.length // 3
    overrides = {item.codon_index: item for item in policy.recodings}
    _require(all(index < codon_count for index in overrides), "invalid_translation")
    coverage = _modifications(source.chemistry)
    residues = []
    for index, start in enumerate(range(span.start, span.end, 3)):
        triplet = source.sequence[start : start + 3]
        override = overrides.get(index)
        if override is not None:
            _require(triplet == override.expected_triplet, "invalid_translation")
            amino_acid = override.amino_acid
        else:
            _require(
                all(
                    _at(coverage, source.sequence, site) is None
                    for site in range(start, start + 3)
                ),
                "unsupported_translation_chemistry",
            )
            amino_acid = STANDARD_RNA_CODON_TABLE[triplet]
        residues.append(amino_acid)
    _require(
        residues[0] == "M" and residues[-1] == "*" and "*" not in residues[:-1],
        "invalid_translation",
    )
    return "".join(residues[:-1])


def construct_recoding_step(step, available, remaining_budget):
    """Return all proposed values atomically, work used, and an optional code."""
    used = 0
    try:
        operation = step.operation
        if isinstance(operation, BaseEditingOperation):
            source = available.get(operation.input.value.id)
            _require(source is not None, "unavailable_input")
            _require(source.sequence_extent == "complete", "incomplete_input")
            _require(source.space.length <= remaining_budget, "residue_budget")
            used = source.space.length
            return (_edited(step, source),), used, None
        ports = {port.id: port for port in step.ports}
        skipping = isinstance(operation, RibosomalSkippingOperation)
        if isinstance(operation, (TranslationOperation, RibosomalSkippingOperation)):
            jobs = [
                (
                    None if skipping else step.ports[0].id,
                    operation.input,
                    operation.policy,
                )
            ]
        elif isinstance(operation, MultiORFTranslationOperation):
            jobs = [
                (product.port_id, product.input, product.policy)
                for product in operation.products
            ]
        elif isinstance(operation, ConditionalTranslationOperation):
            jobs = []
            for branch in operation.branches:
                source = available.get(branch.input.value.id)
                _require(source is not None, "unavailable_input")
                _require(source.sequence_extent == "complete", "incomplete_input")
                _path(branch.input, source)
                if branch.port_id is not None:
                    jobs.append((branch.port_id, branch.input, branch.policy))
        else:
            raise _Problem("invalid_operation")
        planned = []
        for port_id, selection, policy in jobs:
            source = available.get(selection.value.id)
            _require(source is not None, "unavailable_input")
            _require(source.sequence_extent == "complete", "incomplete_input")
            span = _translation_span(selection, source)
            planned.append((port_id, selection, policy, source, span))
        estimated = sum(span.length // 3 - 1 for _, _, _, _, span in planned)
        _require(estimated <= remaining_budget, "residue_budget")
        used = estimated
        values = []
        for port_id, selection, policy, source, span in planned:
            peptide = _translate(source, span, policy)
            if skipping:
                allocations = [
                    (product.port_id, product.residues)
                    for product in operation.products
                ]
                ordered = sorted((part.start, part.end) for _, part in allocations)
                cursor = 0
                for begin, end in ordered:
                    _require(
                        begin == cursor and end > begin and end <= len(peptide),
                        "invalid_skipping_partition",
                    )
                    cursor = end
                _require(cursor == len(peptide), "invalid_skipping_partition")
            else:
                allocations = [(port_id, IndexSpan(0, len(peptide)))]
            for identity, part in allocations:
                source_path = CoordinatePath(
                    source.space.id,
                    (
                        IndexSpan(
                            span.start + 3 * part.start, span.start + 3 * part.end
                        ),
                    ),
                    "+",
                )
                segments = (
                    DerivedSegment(
                        IndexSpan(0, part.length),
                        selection.value.id,
                        source_path,
                        "translation_codon.v1",
                    ),
                )
                consumed = (
                    ConsumedSegment(
                        selection.value.id,
                        CoordinatePath(
                            source.space.id, (IndexSpan(span.end - 3, span.end),), "+"
                        ),
                        "terminal_stop",
                    ),
                )
                values.append(
                    _value(
                        step,
                        ports[identity],
                        source,
                        peptide[part.start : part.end],
                        "linear",
                        segments,
                        consumed,
                    )
                )
        return tuple(values), used, None
    except _Problem as error:
        return (), used, str(error)
    except SerializationError:
        return (), used, "invalid_operation"

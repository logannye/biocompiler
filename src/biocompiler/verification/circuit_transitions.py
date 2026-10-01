"""Independent geometry/chemistry correspondence for declared transitions.

The producer must not import this module. Inputs and derivation segments come
from the checker's independent symbol reconstruction. A declared replacement
specifies desired product chemistry; it never proves biochemical fate.
"""

from bisect import bisect_left
from collections.abc import Mapping
from dataclasses import dataclass, replace

from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_molecules import MoleculeFeature
from biocompiler.ir.circuit_transitions import (
    CHEMISTRY_FACETS,
    ChemistryTransition,
    FeatureTransition,
)
from biocompiler.ir.molecule_chemistry import MoleculeChemistry
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.semantics.molecule_coordinates import (
    CoordinatePath,
    CoordinateSpace,
    IndexSpan,
)


MAX_PROJECTED_RESIDUES = 100_000
MAX_DERIVATION_SEGMENTS = 4096


@dataclass(frozen=True)
class TransitionResolution:
    chemistry: MoleculeChemistry | None
    features: tuple[MoleculeFeature, ...]
    diagnostics: tuple[str, ...]
    unsupported: tuple[str, ...]


class _ProjectionLimit(Exception):
    pass


def _components(chemistry):
    return set(CHEMISTRY_FACETS) | {
        "modification:" + item.id for item in chemistry.modifications
    }


def _selected_blocks(source_id, derivation):
    for segment in derivation:
        if segment.source_id != source_id:
            continue
        require(
            segment.rule != "translation_codon.v1",
            "Codon translation cannot use one-to-one residue projection.",
        )
        cursor = segment.destination.start
        for span in segment.source_path.spans:
            yield span, segment.source_path.strand, cursor, segment.rule
            cursor += span.length


def _project_positions(source_id, positions, derivation):
    """Destination position -> original source position, retaining every copy."""
    ordered = tuple(sorted(positions))
    require(
        len(ordered) <= MAX_PROJECTED_RESIDUES,
        "Projection input residue limit exceeded.",
    )
    result = {}
    for span, strand, cursor, _ in _selected_blocks(source_id, derivation):
        left, right = bisect_left(ordered, span.start), bisect_left(ordered, span.end)
        if len(result) + right - left > MAX_PROJECTED_RESIDUES:
            raise _ProjectionLimit("Projected residue limit exceeded.")
        for position in ordered[left:right]:
            destination = cursor + (
                position - span.start if strand == "+" else span.end - 1 - position
            )
            result[destination] = position
    return result


def _modification_coverage(modification, sequence):
    if modification.scope == "positions":
        return modification.positions
    result = []
    for position, symbol in enumerate(sequence):
        if symbol == modification.canonical_base:
            if len(result) == MAX_PROJECTED_RESIDUES:
                raise _ProjectionLimit("Modification coverage limit exceeded.")
            result.append(position)
    return tuple(result)


def _project_modification(source_id, modification, inputs, derivation):
    """Project selected sites without expanding a policy over an entire source."""
    sequence = inputs[source_id].sequence
    result = set()
    for span, strand, cursor, rule in _selected_blocks(source_id, derivation):
        require(
            rule == "copy",
            "Mapped modification inheritance cannot infer chemistry through symbol rewriting.",
        )
        if modification.scope == "positions":
            sites = modification.positions
            positions = sites[
                bisect_left(sites, span.start) : bisect_left(sites, span.end)
            ]
        else:
            positions = (
                position
                for position in range(span.start, span.end)
                if sequence[position] == modification.canonical_base
            )
        for position in positions:
            if len(result) == MAX_PROJECTED_RESIDUES:
                raise _ProjectionLimit("Mapped modification coverage limit exceeded.")
            result.add(
                cursor
                + (position - span.start if strand == "+" else span.end - 1 - position)
            )
    return result


def _chemical_token(modification):
    return fingerprint(
        {
            "identity": modification.identity.to_dict(),
            "parent": modification.canonical_base,
        }
    )


def _validate_derivation(inputs, output_sequence, output_space, derivation):
    require(
        isinstance(inputs, Mapping) and 0 < len(inputs) <= 64,
        "Expected bounded participating source values.",
    )
    require(
        isinstance(output_space, CoordinateSpace), "Expected output coordinate space."
    )
    require(
        isinstance(output_sequence, str)
        and len(output_sequence) == output_space.length,
        "Output spelling and frame disagree.",
    )
    require(
        isinstance(derivation, (tuple, list))
        and 0 < len(derivation) <= MAX_DERIVATION_SEGMENTS,
        "Invalid derivation segment inventory.",
    )
    cursor = 0
    selected = set()
    checked_sources = set()
    blocks = 0
    for segment in derivation:
        require(
            isinstance(segment.destination, IndexSpan)
            and segment.destination.start == cursor
            and segment.destination.length > 0,
            "Derivation must partition output residues exactly once.",
        )
        require(segment.source_id in inputs, "Derivation names an unknown input value.")
        source = inputs[segment.source_id]
        require(
            isinstance(source.space, CoordinateSpace)
            and isinstance(source.chemistry, MoleculeChemistry),
            "Invalid transition source value.",
        )
        if segment.source_id not in checked_sources:
            source.chemistry.validate_for(
                source.space,
                source.sequence,
                getattr(source, "sequence_extent", "complete"),
            )
            require(
                isinstance(source.features, (tuple, list))
                and len(source.features) <= 256
                and all(
                    isinstance(feature, MoleculeFeature) for feature in source.features
                ),
                "Invalid source feature inventory.",
            )
            require(
                len({feature.id for feature in source.features})
                == len(source.features),
                "Duplicate source feature identities.",
            )
            for feature in source.features:
                if feature.path is not None:
                    feature.path.validate_for(source.space)
            checked_sources.add(segment.source_id)
        require(
            isinstance(segment.source_path, CoordinatePath),
            "Invalid derivation source coordinates.",
        )
        segment.source_path.validate_for(source.space)
        blocks += len(segment.source_path.spans)
        require(
            blocks <= MAX_DERIVATION_SEGMENTS, "Derivation path-block limit exceeded."
        )
        require(
            segment.rule
            in {
                "copy",
                "complement",
                "dna_coding_to_rna.v1",
                "rna_editing.v1",
                "translation_codon.v1",
            },
            "Unsupported derivation symbol rule.",
        )
        ratio = 3 if segment.rule == "translation_codon.v1" else 1
        require(
            segment.source_path.length == segment.destination.length * ratio,
            "Derivation source and destination lengths do not match the declared symbol ratio.",
        )
        if segment.rule == "dna_coding_to_rna.v1":
            require(
                source.space.alphabet == "DNA" and output_space.alphabet == "RNA",
                "Transcription derivation must explicitly bind DNA to RNA.",
            )
        elif segment.rule == "translation_codon.v1":
            require(
                source.space.alphabet == "RNA" and output_space.alphabet == "protein",
                "Codon translation derivation must explicitly bind RNA to protein.",
            )
            require(
                segment.source_path.strand == "+"
                and len(segment.source_path.spans) == 1,
                "Codon translation requires contiguous forward source traversal.",
            )
        else:
            require(
                source.space.alphabet == output_space.alphabet,
                "Derivation cannot silently change the alphabet.",
            )
            require(
                segment.rule != "rna_editing.v1" or source.space.alphabet == "RNA",
                "RNA editing derivation requires the RNA alphabet.",
            )
            require(
                segment.rule != "complement" or source.space.alphabet in {"DNA", "RNA"},
                "Protein complementation is not a symbol operation.",
            )
        cursor = segment.destination.end
        selected.add(segment.source_id)
    require(
        cursor == output_space.length, "Derivation does not cover the complete output."
    )
    require(
        selected == set(inputs),
        "Transition inputs must be exactly the participating derivation sources.",
    )


def _identity_source(inputs, output_sequence, output_space, derivation):
    require(
        len(inputs) == 1, "Exact chemistry inheritance requires exactly one source."
    )
    source_id, source = next(iter(inputs.items()))
    require(
        getattr(source, "sequence_extent", "complete") == "complete",
        "Exact inheritance requires a complete source spelling.",
    )
    require(
        source.sequence == output_sequence
        and source.space.alphabet == output_space.alphabet
        and source.space.topology == output_space.topology,
        "Exact chemistry inheritance requires unchanged spelling, alphabet and topology.",
    )
    cursor = 0
    for segment in derivation:
        require(
            segment.source_id == source_id
            and segment.rule == "copy"
            and segment.source_path.strand == "+",
            "Exact inheritance requires unchanged forward traversal.",
        )
        for span in segment.source_path.spans:
            require(
                span.start == cursor,
                "Exact inheritance cannot cut, duplicate or reorder source residues.",
            )
            cursor = span.end
    require(
        cursor == source.space.length,
        "Exact inheritance must retain every original residue.",
    )
    tail = source.chemistry.terminal_tail
    if tail.path is not None:
        tail = replace(tail, path=replace(tail.path, space_id=output_space.id))
    return replace(source.chemistry, terminal_tail=tail)


def _endpoint_mapped(source_id, facet, inputs, output_space, derivation):
    source = inputs[source_id]
    if (
        facet not in {"cap", "start_end"}
        and getattr(source, "sequence_extent", "complete") != "complete"
    ):
        return False
    source_position = 0 if facet in {"cap", "start_end"} else source.space.length - 1
    expected = 0 if facet in {"cap", "start_end"} else output_space.length - 1
    matches = _project_positions(source_id, (source_position,), derivation)
    return matches == {expected: source_position} and all(
        strand == "+" and rule == "copy"
        for span, strand, _, rule in _selected_blocks(source_id, derivation)
        if span.start <= source_position < span.end
    )


def _resolve_explicit_chemistry(
    transition,
    inputs,
    output_sequence,
    output_space,
    derivation,
    diagnostics,
    unsupported,
):
    output = transition.output
    expected = {
        (identity, component)
        for identity, value in inputs.items()
        for component in _components(value.chemistry)
    }
    supplied = {(item.source_id, item.component) for item in transition.dispositions}
    if supplied != expected:
        diagnostics.append(
            "chemistry_disposition_inventory: every input chemistry facet and modification requires exactly one disposition"
        )
        return output
    destinations = _components(output)
    targeted = {
        component
        for item in transition.dispositions
        for component in item.destination_components
    }
    if targeted != destinations:
        diagnostics.append(
            "chemistry_destination_inventory: every output chemistry component requires an explicit disposition"
        )
    output_mods = {"modification:" + item.id: item for item in output.modifications}
    mapped_modifications = {}
    for disposition in transition.dispositions:
        label = f"{disposition.source_id}/{disposition.component}"
        if not set(disposition.destination_components) <= destinations:
            diagnostics.append(f"chemistry_destination_missing: {label}")
            continue
        if disposition.decision == "unknown":
            unsupported.append(f"unknown_chemistry_disposition: {label}")
            continue
        if disposition.decision in {"not_carried", "declared_replacement"}:
            continue
        source = inputs[disposition.source_id]
        try:
            require(
                all(
                    segment.rule not in {"rna_editing.v1", "translation_codon.v1"}
                    for segment in derivation
                    if segment.source_id == disposition.source_id
                ),
                "Mapped chemistry cannot infer retention through RNA editing or codon translation.",
            )
            if disposition.component.startswith("modification:"):
                require(
                    all(
                        component in output_mods
                        for component in disposition.destination_components
                    ),
                    "A mapped base modification must name output modification occurrences.",
                )
                original = next(
                    item
                    for item in source.chemistry.modifications
                    if "modification:" + item.id == disposition.component
                )
                projected = _project_modification(
                    disposition.source_id, original, inputs, derivation
                )
                target_coverage = set()
                for component in disposition.destination_components:
                    target = output_mods[component]
                    require(
                        _chemical_token(target) == _chemical_token(original),
                        "Mapped modification identity or canonical parent changed.",
                    )
                    covered = set(_modification_coverage(target, output_sequence))
                    target_coverage.update(covered)
                    mapped_modifications.setdefault(component, set()).update(
                        projected.intersection(covered)
                    )
                require(
                    projected <= target_coverage,
                    "Mapped modification loses selected chemical sites.",
                )
            elif disposition.component == "modification_inventory":
                require(
                    disposition.destination_components == ("modification_inventory",),
                    "Inventory inheritance must retain the inventory facet.",
                )
                require(
                    source.chemistry.modification_inventory_status
                    == output.modification_inventory_status,
                    "Mapped modification inventory cannot resolve unknown chemistry.",
                )
            elif disposition.component == "terminal_tail":
                require(
                    disposition.destination_components == ("terminal_tail",),
                    "Tail inheritance must retain the tail facet.",
                )
                original, target = source.chemistry.terminal_tail, output.terminal_tail
                require(
                    original.status == target.status
                    and original.placement == target.placement
                    and original.length == target.length,
                    "Mapped tail declaration changed.",
                )
                if original.path is not None:
                    if original.path.length > MAX_PROJECTED_RESIDUES:
                        raise _ProjectionLimit("Mapped tail residue limit exceeded.")
                    positions = original.path.positions(
                        source.space, limit=MAX_PROJECTED_RESIDUES
                    )
                    projected = _project_positions(
                        disposition.source_id, positions, derivation
                    )
                    target_positions = target.path.positions(
                        output_space, limit=MAX_PROJECTED_RESIDUES
                    )
                    require(
                        len(projected) == len(positions)
                        and set(projected) == set(target_positions),
                        "Mapped tail has incomplete or changed residue coverage.",
                    )
                    require(
                        tuple(projected[position] for position in target_positions)
                        == positions,
                        "Mapped tail traversal changed.",
                    )
                if original.status != "inapplicable":
                    require(
                        _endpoint_mapped(
                            disposition.source_id,
                            "finish_end",
                            inputs,
                            output_space,
                            derivation,
                        ),
                        "Mapped tail must retain its original terminal boundary.",
                    )
            else:
                require(
                    disposition.destination_components == (disposition.component,),
                    "Mapped terminal chemistry must retain its facet.",
                )
                original, target = (
                    getattr(source.chemistry, disposition.component),
                    getattr(output, disposition.component),
                )
                require(
                    original.nominal_dict() == target.nominal_dict(),
                    "Mapped terminal chemistry changed its declared identity or knowledge.",
                )
                if original.status != "inapplicable":
                    require(
                        _endpoint_mapped(
                            disposition.source_id,
                            disposition.component,
                            inputs,
                            output_space,
                            derivation,
                        ),
                        "Mapped terminal chemistry must retain its original boundary.",
                    )
        except _ProjectionLimit as error:
            unsupported.append(f"chemistry_projection_budget: {label}: {error}")
        except SerializationError as error:
            diagnostics.append(f"chemistry_mapping: {label}: {error}")
    for component, projected in mapped_modifications.items():
        try:
            expected_coverage = set(
                _modification_coverage(output_mods[component], output_sequence)
            )
            if projected != expected_coverage:
                diagnostics.append(
                    f"chemistry_mapping: {component} has unmapped output chemical sites"
                )
        except _ProjectionLimit as error:
            unsupported.append(f"chemistry_projection_budget: {component}: {error}")
    return output


def _resolve_features(
    transition, inputs, output_space, derivation, diagnostics, unsupported
):
    expected = {
        (identity, feature.id): feature
        for identity, value in inputs.items()
        for feature in value.features
    }
    supplied = {
        (item.source_id, item.feature_id): item for item in transition.dispositions
    }
    if set(expected) != set(supplied):
        diagnostics.append(
            "feature_disposition_inventory: every source annotation requires exactly one disposition"
        )
    output_features = tuple(
        sorted(
            (
                *transition.added,
                *(
                    feature
                    for item in transition.dispositions
                    for feature in item.outputs
                ),
            ),
            key=lambda item: item.id,
        )
    )
    for feature in output_features:
        if feature.path is None:
            unsupported.append(f"unknown_output_feature_coordinates: {feature.id}")
        else:
            try:
                feature.path.validate_for(output_space)
            except SerializationError as error:
                diagnostics.append(f"output_feature_coordinates: {feature.id}: {error}")
    budget = 0
    for key, disposition in supplied.items():
        if key not in expected:
            continue
        original = expected[key]
        label = f"{key[0]}/{key[1]}"
        if disposition.decision == "not_carried":
            continue
        if disposition.decision == "unknown":
            unsupported.append(f"unknown_feature_disposition: {label}")
            continue
        if original.path is None or original.path.length == 0:
            unsupported.append(f"unresolved_source_feature_geometry: {label}")
            continue
        budget += original.path.length
        if budget > MAX_PROJECTED_RESIDUES:
            unsupported.append(
                "feature_projection_budget: total source feature residue limit exceeded"
            )
            continue
        if disposition.decision == "outside_selection":
            intersects = any(
                left.start < right.end and right.start < left.end
                for segment in derivation
                if segment.source_id == key[0]
                for left in original.path.spans
                for right in segment.source_path.spans
            )
            if intersects:
                diagnostics.append(
                    f"feature_mapping: {label}: Outside-selection claim intersects selected residues."
                )
            continue
        if any(
            segment.source_id == key[0] and segment.rule == "translation_codon.v1"
            for segment in derivation
        ):
            unsupported.append(f"translation_feature_mapping: {label}")
            continue
        try:
            original_positions = original.path.positions(
                inputs[key[0]].space, limit=MAX_PROJECTED_RESIDUES
            )
            order = {
                position: index for index, position in enumerate(original_positions)
            }
            projected = _project_positions(key[0], original_positions, derivation)
            require(bool(projected), "Mapped feature has no selected source residues.")
            original_coverage = set(projected.values())
            if disposition.decision in {"exact", "split"}:
                require(
                    original_coverage == set(original_positions),
                    "Exact/split mapping cannot silently clip a source feature.",
                )
            else:
                require(
                    original_coverage < set(original_positions),
                    "Partial mapping must explicitly represent a proper source subset.",
                )
            observed = set()
            for feature in disposition.outputs:
                require(
                    feature.kind == original.kind
                    and feature.reading_frame == original.reading_frame,
                    "Mapped feature kind or reading frame changed without an explicit new declaration.",
                )
                require(
                    feature.path is not None,
                    "Mapped feature output coordinates are unresolved.",
                )
                positions = feature.path.positions(
                    output_space, limit=MAX_PROJECTED_RESIDUES
                )
                require(
                    positions and all(position in projected for position in positions),
                    "Output annotation contains residues outside its source projection.",
                )
                require(
                    not observed.intersection(positions),
                    "Mapped output annotations duplicate one projected occurrence.",
                )
                observed.update(positions)
                progression = tuple(
                    order[projected[position]] for position in positions
                )
                require(
                    all(
                        left < right
                        for left, right in zip(progression, progression[1:])
                    ),
                    "Feature mapping changes source traversal order.",
                )
                if disposition.decision == "exact":
                    require(
                        progression == tuple(range(len(original_positions))),
                        "Exact feature mapping must preserve one complete occurrence.",
                    )
                if (
                    disposition.decision in {"partial", "split"}
                    and original.reading_frame is not None
                ):
                    unsupported.append(f"partial_coding_feature_frame: {label}")
            require(
                observed == set(projected),
                "Feature mapping omits selected source annotation residues.",
            )
        except _ProjectionLimit as error:
            unsupported.append(f"feature_projection_budget: {label}: {error}")
        except SerializationError as error:
            diagnostics.append(f"feature_mapping: {label}: {error}")
    return output_features


def resolve_transitions(
    chemistry_transition,
    feature_transition,
    *,
    inputs,
    output_sequence,
    output_space,
    derivation,
    sequence_extent="complete",
):
    """Resolve declarations against independently reconstructed coordinate maps.

    ``diagnostics`` are contradictions; ``unsupported`` prevents strict success
    for unknowns or unsupported geometry. Proposed explicit values remain
    inspectable but neither category permits a successful strict construction.
    """
    require(
        isinstance(chemistry_transition, ChemistryTransition),
        "Expected chemistry transition authority.",
    )
    require(
        isinstance(feature_transition, FeatureTransition),
        "Expected feature transition authority.",
    )
    chemistry_transition = ChemistryTransition.from_dict(chemistry_transition.to_dict())
    feature_transition = FeatureTransition.from_dict(feature_transition.to_dict())
    diagnostics, unsupported = [], []
    try:
        _validate_derivation(inputs, output_sequence, output_space, derivation)
    except (SerializationError, AttributeError, TypeError, KeyError) as error:
        return TransitionResolution(None, (), (f"transition_derivation: {error}",), ())
    if chemistry_transition.mode == "exact_inheritance":
        try:
            chemistry = _identity_source(
                inputs, output_sequence, output_space, derivation
            )
        except SerializationError as error:
            diagnostics.append(f"chemistry_exact_inheritance: {error}")
            chemistry = None
    else:
        chemistry = _resolve_explicit_chemistry(
            chemistry_transition,
            inputs,
            output_sequence,
            output_space,
            derivation,
            diagnostics,
            unsupported,
        )
    if chemistry is not None:
        try:
            chemistry.validate_for(output_space, output_sequence, sequence_extent)
        except SerializationError as error:
            diagnostics.append(f"output_chemistry: {error}")
        if not chemistry.declared_nominal_complete:
            unsupported.append(
                "unknown_output_chemistry: nominal chemistry remains incomplete"
            )
    features = _resolve_features(
        feature_transition, inputs, output_space, derivation, diagnostics, unsupported
    )
    return TransitionResolution(
        chemistry,
        features,
        tuple(dict.fromkeys(diagnostics)),
        tuple(dict.fromkeys(unsupported)),
    )

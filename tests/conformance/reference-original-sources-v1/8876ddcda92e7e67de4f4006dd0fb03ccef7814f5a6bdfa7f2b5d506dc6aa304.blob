"""Propose deterministic constructions from explicit supplied sequence authority.

This producer is deliberately independent of the reconstruction checker. A
candidate, including one with no diagnostics, is not a verification result.
"""

from dataclasses import replace

from biocompiler.artifacts.circuit_construction import (
    ConstructionCandidate,
    ConstructedValue,
    DerivedSegment,
)
from biocompiler.artifacts.circuit_molecules import (
    CircuitMoleculeRecord,
    ExperimentalAmount,
)
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_construction import (
    CircuitConstructionRequest,
    ConcatenateOperation,
    RNACleavageOperation,
    RNASplicingOperation,
    ProteinCleavageOperation,
    ProteinSplicingOperation,
    CircularizationOperation,
    BaseEditingOperation,
    TranslationOperation,
    MultiORFTranslationOperation,
    ConditionalTranslationOperation,
    RibosomalSkippingOperation,
    OrientationOperation,
    SliceOperation,
    TranscriptionOperation,
    MAX_CUMULATIVE_PRODUCED_RESIDUES,
)
from biocompiler.ir.circuit_molecules import (
    AssemblyOrigin,
    CircuitMolecule,
    CircuitMoleculeSet,
    MoleculeRoleInstance,
    MolecularComplex,
    ComplexConstituent,
)
from biocompiler.ir.molecule_records import MAX_RESIDUES
from biocompiler.semantics.molecule_coordinates import (
    CoordinateSpace,
    CoordinatePath,
    IndexSpan,
)


def _full_path(space):
    return CoordinatePath(space.id, (IndexSpan(0, space.length),), "+")


def _relabel_chemistry(chemistry, frame_id):
    tail = chemistry.terminal_tail
    if tail.path is not None:
        tail = replace(tail, path=replace(tail.path, space_id=frame_id))
        return replace(chemistry, terminal_tail=tail)
    return chemistry


def _relabel_features(features, frame_id):
    return tuple(
        replace(item, path=replace(item.path, space_id=frame_id))
        if item.path is not None
        else item
        for item in features
    )


def _selected(sequence, path):
    pieces = []
    for span in path.spans:
        piece = sequence[span.start : span.end]
        pieces.append(piece if path.strand == "+" else piece[::-1])
    return "".join(pieces)


def _reverse_path(path):
    return replace(
        path,
        spans=tuple(reversed(path.spans)),
        strand="-" if path.strand == "+" else "+",
    )


def construct_circuit_candidate(
    request: CircuitConstructionRequest,
) -> ConstructionCandidate:
    """Execute only the explicit v0.1 software operations, without admission."""
    request = CircuitConstructionRequest.from_dict(request.to_dict())
    available = {source.id: source.molecule for source in request.sources}
    values, diagnostics, missing = [], [], []
    work = 0
    for step in request.steps:
        operation = step.operation
        if isinstance(
            operation,
            (
                BaseEditingOperation,
                TranslationOperation,
                MultiORFTranslationOperation,
                ConditionalTranslationOperation,
                RibosomalSkippingOperation,
            ),
        ):
            from biocompiler.backends.circuit_recoding import construct_recoding_step

            staged, used, code = construct_recoding_step(
                step, available, MAX_CUMULATIVE_PRODUCED_RESIDUES - work
            )
            work += used
            if code is not None:
                diagnostics.append(f"step:{step.id}:{code}")
            else:
                values.extend(staged)
                available.update((value.id, value) for value in staged)
            continue
        selections = (
            operation.inputs
            if isinstance(operation, ConcatenateOperation)
            else (operation.input,)
        )
        if any(selection.value.id not in available for selection in selections):
            diagnostics.append(f"step:{step.id}:unavailable_input")
            continue
        inputs = [available[selection.value.id] for selection in selections]
        if any(value.sequence_extent != "complete" for value in inputs):
            diagnostics.append(f"step:{step.id}:incomplete_input")
            continue
        paths = []
        try:
            for selection, value in zip(selections, inputs):
                path = (
                    selection.path
                    if selection.path is not None
                    else _full_path(value.space)
                )
                path.validate_for(value.space)
                if path.length == 0:
                    raise SerializationError("Empty material selection.")
                paths.append(path)
        except SerializationError:
            diagnostics.append(f"step:{step.id}:invalid_selection")
            continue
        alphabet = inputs[0].space.alphabet
        if any(value.space.alphabet != alphabet for value in inputs):
            diagnostics.append(f"step:{step.id}:unsupported_alphabet")
            continue
        topology, rule = "linear", "copy"
        processing_types = (
            RNACleavageOperation,
            RNASplicingOperation,
            ProteinCleavageOperation,
            ProteinSplicingOperation,
        )
        recipes = None
        if isinstance(operation, processing_types):
            expected_alphabet = (
                "RNA"
                if isinstance(operation, (RNACleavageOperation, RNASplicingOperation))
                else "protein"
            )
            if alphabet != expected_alphabet:
                diagnostics.append(f"step:{step.id}:unsupported_alphabet")
                continue
            if inputs[0].space.topology != "linear":
                diagnostics.append(f"step:{step.id}:unsupported_topology")
                continue
            try:
                for recipe in operation.products:
                    recipe.path.validate_for(inputs[0].space)
                    if recipe.path.length == 0 or recipe.path.strand != "+":
                        raise SerializationError(
                            "Processing requires positive forward paths."
                        )
            except SerializationError:
                diagnostics.append(f"step:{step.id}:invalid_selection")
                continue
            if any(
                any(
                    left.end > right.start
                    for left, right in zip(recipe.path.spans, recipe.path.spans[1:])
                )
                for recipe in operation.products
            ):
                diagnostics.append(f"step:{step.id}:invalid_processing_partition")
                continue
            intervals = sorted(
                (span.start, span.end)
                for recipe in operation.products
                for span in recipe.path.spans
            )
            cursor = 0
            valid = True
            for begin, end in intervals:
                if begin != cursor or end <= begin:
                    valid = False
                cursor = end
            if not valid or cursor != inputs[0].space.length:
                diagnostics.append(f"step:{step.id}:invalid_processing_partition")
                continue
            # All released products are retained, including excised fragments.
            ports = {port.id: port for port in step.ports}
            recipes = [
                (ports[recipe.port_id], (recipe.path,)) for recipe in operation.products
            ]
        elif isinstance(operation, CircularizationOperation):
            if alphabet != "RNA":
                diagnostics.append(f"step:{step.id}:unsupported_alphabet")
                continue
            if inputs[0].space.topology != "linear":
                diagnostics.append(f"step:{step.id}:unsupported_topology")
                continue
            if operation.origin >= inputs[0].space.length:
                diagnostics.append(f"step:{step.id}:invalid_selection")
                continue
            origin = operation.origin
            spans = (IndexSpan(origin, inputs[0].space.length),)
            if origin:
                spans += (IndexSpan(0, origin),)
            paths = [CoordinatePath(inputs[0].space.id, spans, "+")]
            topology = "circular"
        elif isinstance(operation, TranscriptionOperation):
            if alphabet != "DNA":
                diagnostics.append(f"step:{step.id}:unsupported_alphabet")
                continue
            if paths[0].strand != "+" or len(paths[0].spans) != 1:
                diagnostics.append(f"step:{step.id}:unsupported_transcription_path")
                continue
            alphabet, rule = "RNA", "dna_coding_to_rna.v1"
        elif isinstance(operation, OrientationOperation):
            if alphabet not in {"DNA", "RNA"}:
                diagnostics.append(f"step:{step.id}:unsupported_alphabet")
                continue
            paths = [_reverse_path(paths[0])]
            if operation.action == "reverse_complement":
                rule = "complement"
            if selections[0].path is None:
                topology = inputs[0].space.topology
        elif isinstance(operation, SliceOperation):
            if selections[0].path is None:
                topology = inputs[0].space.topology
        if recipes is None:
            recipes = [(step.ports[0], paths)]
        if any(port.alphabet != alphabet for port, _ in recipes):
            diagnostics.append(f"step:{step.id}:unsupported_alphabet")
            continue
        if any(port.topology != topology for port, _ in recipes):
            diagnostics.append(f"step:{step.id}:unsupported_topology")
            continue
        lengths = [
            sum(path.length for path in recipe_paths) for _, recipe_paths in recipes
        ]
        if (
            max(lengths) > MAX_RESIDUES
            or work + sum(lengths) > MAX_CUMULATIVE_PRODUCED_RESIDUES
        ):
            diagnostics.append(f"step:{step.id}:residue_budget")
            continue
        work += sum(lengths)
        staged = []
        try:
            for (port, recipe_paths), length in zip(recipes, lengths):
                chunks, segments, cursor = [], [], 0
                for selection, value, path in zip(selections, inputs, recipe_paths):
                    chunk = _selected(value.sequence, path)
                    if rule == "complement":
                        table = (
                            str.maketrans("ACGT", "TGCA")
                            if alphabet == "DNA"
                            else str.maketrans("ACGU", "UGCA")
                        )
                        chunk = chunk.translate(table)
                    elif rule == "dna_coding_to_rna.v1":
                        chunk = chunk.replace("T", "U")
                    chunks.append(chunk)
                    segments.append(
                        DerivedSegment(
                            IndexSpan(cursor, cursor + len(chunk)),
                            selection.value.id,
                            path,
                            rule,
                        )
                    )
                    cursor += len(chunk)
                space = CoordinateSpace(
                    port.space_id,
                    alphabet,
                    length,
                    topology,
                    "N_to_C" if alphabet == "protein" else "5prime_to_3prime",
                )
                transition = port.chemistry_transition
                chemistry = (
                    _relabel_chemistry(inputs[0].chemistry, space.id)
                    if transition.mode == "exact_inheritance"
                    else transition.output
                )
                features = (
                    tuple(
                        feature
                        for disposition in port.feature_transition.dispositions
                        for feature in disposition.outputs
                    )
                    + port.feature_transition.added
                )
                staged.append(
                    ConstructedValue(
                        port.id,
                        space,
                        "".join(chunks),
                        chemistry,
                        features,
                        tuple(segments),
                        step.id,
                    )
                )
        except SerializationError:
            diagnostics.append(f"step:{step.id}:invalid_operation")
            continue
        for product in staged:
            values.append(product)
            available[product.id] = product
    final_size = sum(
        available[member.value.id].space.length
        for member in request.output_members
        if member.value.id in available
    )
    if final_size > MAX_RESIDUES:
        diagnostics.append("bundle:residue_budget")
        omitted = tuple(member.id for member in request.output_members) + tuple(
            plan.id for plan in request.complex_members
        )
        return ConstructionCandidate(
            request.fingerprint,
            tuple(values),
            None,
            tuple(sorted(omitted)),
            tuple(sorted(set(diagnostics))),
        )
    molecules = []
    for member in request.output_members:
        value = available.get(member.value.id)
        if value is None:
            diagnostics.append(f"member:{member.id}:unavailable_value")
            missing.append(member.id)
            continue
        try:
            if member.sequence_extent != value.sequence_extent:
                raise SerializationError(
                    "Finalization cannot change known molecular extent."
                )
            space = replace(value.space, id=member.space_id)
            molecule = CircuitMolecule(
                member.id,
                member.form,
                space,
                value.sequence,
                member.sequence_extent,
                member.coding_status,
                (
                    AssemblyOrigin(
                        member.id + ".origin",
                        _full_path(space),
                        value.space,
                        _full_path(value.space),
                        member.provenance,
                    ),
                ),
                _relabel_features(value.features, space.id),
                _relabel_chemistry(value.chemistry, space.id),
                member.provenance,
            )
            if not molecule.declared_nominal_complete:
                diagnostics.append(f"member:{member.id}:nominal_incomplete")
            molecules.append(molecule)
        except SerializationError:
            diagnostics.append(f"member:{member.id}:invalid_molecule")
            missing.append(member.id)
    bundle = None
    amounts = ()
    by_id = {molecule.id: molecule for molecule in molecules}
    complexes = []
    for plan in getattr(request, "complex_members", ()):
        if any(item.member_id not in by_id for item in plan.constituents):
            diagnostics.append(f"member:{plan.id}:unavailable_value")
            missing.append(plan.id)
            continue
        try:
            constituents = tuple(
                ComplexConstituent(
                    item.member_id,
                    by_id[item.member_id].fingerprint,
                    item.stoichiometry,
                    item.provenance,
                )
                for item in plan.constituents
            )
            complexes.append(
                MolecularComplex(plan.id, plan.kind, constituents, plan.provenance)
            )
        except SerializationError:
            diagnostics.append(f"member:{plan.id}:invalid_molecule")
            missing.append(plan.id)
    if not missing:
        try:
            subjects = {**by_id, **{item.id: item for item in complexes}}
            roles = []
            for requirement in request.requirements:
                if requirement.member_id is None:
                    continue
                subject = subjects[requirement.member_id]
                roles.extend(
                    MoleculeRoleInstance(
                        role.id,
                        subject.id,
                        subject.fingerprint,
                        role.role,
                        role.purpose,
                        role.compartment,
                    )
                    for role in requirement.roles
                )
            bundle = CircuitMoleculeSet(
                request.id + ".molecules",
                request.circuit,
                tuple(molecules),
                tuple(complexes),
                tuple(roles),
                (),
            )
            for item in complexes:
                if not bundle.subject_complete(item.id):
                    diagnostics.append(f"member:{item.id}:nominal_incomplete")
            amounts = tuple(
                ExperimentalAmount(
                    item.id,
                    item.subject_id,
                    subjects[item.subject_id].fingerprint,
                    item.preparation_id,
                    item.role_instance_ids,
                    item.quantity,
                    item.unit,
                    item.provenance,
                )
                for item in getattr(request, "amounts", ())
            )
            CircuitMoleculeRecord(bundle, amounts, {})
        except SerializationError:
            diagnostics.append("bundle:invalid_inventory")
            bundle, amounts = None, ()
    return ConstructionCandidate(
        request.fingerprint,
        tuple(values),
        bundle,
        tuple(sorted(set(missing))),
        tuple(sorted(set(diagnostics))),
        amounts,
    )

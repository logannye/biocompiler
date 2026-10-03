"""Independent reconstruction of the bounded, supplied construction profile.

No generator, backend or candidate supplies expected residues or source maps.
The operations checked here establish software correspondence to separately
retained authority, not biochemical processing, circuit function or admission.
"""

from dataclasses import dataclass, replace
from typing import ClassVar

from biocompiler.artifacts.circuit_construction import (
    ConsumedSegment,
    ConstructedValue,
    ConstructionCandidate,
    DerivedSegment,
)
from biocompiler.artifacts.manifest import _hash
from biocompiler.artifacts.circuit_molecules import (
    CircuitMoleculeRecord,
    ExperimentalAmount,
)
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_construction import (
    CAPABILITY_PROFILE_VERSION,
    CONSTRUCTION_PROFILE_VERSION,
    MAX_CUMULATIVE_PRODUCED_RESIDUES,
    PROCESSING_OPERATION_TYPES,
    BaseEditingOperation,
    CircuitConstructionRequest,
    CircularizationOperation,
    ConcatenateOperation,
    ConditionalTranslationOperation,
    MultiORFTranslationOperation,
    OrientationOperation,
    ProteinCleavageOperation,
    ProteinSplicingOperation,
    RNACleavageOperation,
    RNASplicingOperation,
    RibosomalSkippingOperation,
    SliceOperation,
    TranscriptionOperation,
    TranslationOperation,
)
from biocompiler.ir.circuit_recoding import STANDARD_RNA_CODON_TABLE
from biocompiler.ir.circuit_molecules import (
    AssemblyOrigin,
    CircuitMolecule,
    CircuitMoleculeSet,
    ComplexConstituent,
    MolecularComplex,
    MoleculeRoleInstance,
)
from biocompiler.ir.molecule_records import MAX_RESIDUES, _MoleculeRecord, _text
from biocompiler.ir.serialization import require
from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION
from biocompiler.semantics.molecule_coordinates import (
    CoordinatePath,
    CoordinateSpace,
    IndexSpan,
)
from biocompiler.verification.evidence import CheckOutcome


CHECKER_VERSION = "biocompiler.circuit_construction_checker.v0.1"
CLAIM_SCOPE = (
    "Exact correspondence of supplied sources, declared software operations, "
    "derived coordinates, chemistry and annotations; no biological processing, "
    "circuit implementation, independently reviewed source fidelity or human "
    "therapeutic admission is established."
)
MAX_ASSESSMENT_DIAGNOSTICS = 4096
MAX_DIAGNOSTIC_BYTES = 32_768
MAX_ASSESSMENT_DIAGNOSTIC_BYTES = 1_000_000


class _DiagnosticInventory:
    """Bound aggregate reporting while preserving every omitted severity."""

    def __init__(self):
        self._items = {}
        self._bytes = 0
        self._omitted_status = None

    def append(self, diagnostic):
        if diagnostic in self._items:
            return
        size = (
            len(diagnostic.encode("utf-8"))
            if len(diagnostic) <= MAX_DIAGNOSTIC_BYTES
            else MAX_DIAGNOSTIC_BYTES + 1
        )
        if (
            size > MAX_DIAGNOSTIC_BYTES
            or len(self._items) >= MAX_ASSESSMENT_DIAGNOSTICS - 1
            or self._bytes + size > MAX_ASSESSMENT_DIAGNOSTIC_BYTES
        ):
            status = diagnostic.split(":", 1)[0]
            severity = {None: 0, "unknown": 1, "unsupported": 2, "fail": 3}
            if severity[status] > severity[self._omitted_status]:
                self._omitted_status = status
            return
        self._items[diagnostic] = None
        self._bytes += size

    def extend(self, diagnostics):
        for diagnostic in diagnostics:
            self.append(diagnostic)

    def __iter__(self):
        yield from self._items
        if self._omitted_status is not None:
            yield f"{self._omitted_status}:assessment_diagnostic_budget"

    def __bool__(self):
        return bool(self._items) or self._omitted_status is not None


def _whole(space):
    return CoordinatePath(space.id, (IndexSpan(0, space.length),), "+")


def _reframe_chemistry(chemistry, frame_id):
    tail = chemistry.terminal_tail
    if tail.path is None:
        return chemistry
    return replace(
        chemistry,
        terminal_tail=replace(tail, path=replace(tail.path, space_id=frame_id)),
    )


def _operands(operation):
    # Read the closed schema directly, independently of producer dispatch.
    if isinstance(operation, ConcatenateOperation):
        return operation.inputs
    if isinstance(
        operation, (MultiORFTranslationOperation, ConditionalTranslationOperation)
    ):
        entries = (
            operation.products
            if isinstance(operation, MultiORFTranslationOperation)
            else operation.branches
        )
        selected = {}
        for entry in entries:
            selected.setdefault(entry.input.fingerprint, entry.input)
        return tuple(selected.values())
    require(
        isinstance(
            operation,
            (
                SliceOperation,
                OrientationOperation,
                TranscriptionOperation,
                CircularizationOperation,
                BaseEditingOperation,
                TranslationOperation,
                RibosomalSkippingOperation,
                *PROCESSING_OPERATION_TYPES,
            ),
        ),
        "Unsupported construction operation in independent reconstruction.",
    )
    return (operation.input,)


def _read_path(source, path, rule):
    """Traverse each declared segment in order; orientation is already explicit."""
    pieces = []
    for span in path.spans:
        if path.strand == "+":
            indices = range(span.start, span.end)
        else:
            indices = range(span.end - 1, span.start - 1, -1)
        pieces.append("".join(source.sequence[index] for index in indices))
    spelling = "".join(pieces)
    if rule == "copy":
        return spelling
    if rule == "dna_coding_to_rna.v1":
        return "".join("U" if symbol == "T" else symbol for symbol in spelling)
    complement = (
        {"A": "T", "C": "G", "G": "C", "T": "A"}
        if source.space.alphabet == "DNA"
        else {"A": "U", "C": "G", "G": "C", "U": "A"}
    )
    return "".join(complement[symbol] for symbol in spelling)


def _propose_value(step, port, selections, inputs, paths, rule):
    """Reconstruct the declared proposal without treating transitions as proven."""
    segments, parts, cursor = [], [], 0
    for selection, source, path in zip(selections, inputs, paths, strict=True):
        segments.append(
            DerivedSegment(
                IndexSpan(cursor, cursor + path.length), selection.value.id, path, rule
            )
        )
        parts.append(_read_path(source, path, rule))
        cursor += path.length
    return _finish_value(step, port, inputs[0], "".join(parts), tuple(segments))


def _finish_value(step, port, source, sequence, segments, consumed=()):
    space = CoordinateSpace(
        port.space_id,
        port.alphabet,
        len(sequence),
        port.topology,
        "N_to_C" if port.alphabet == "protein" else "5prime_to_3prime",
    )
    chemistry = (
        port.chemistry_transition.output
        if port.chemistry_transition.mode == "explicit_output"
        else _reframe_chemistry(source.chemistry, space.id)
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
        space,
        sequence,
        chemistry,
        features,
        segments,
        step.id,
        consumed=consumed,
    )


class _ConstructionProblem(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _expect(condition, code):
    if not condition:
        raise _ConstructionProblem(code)


def _reserve(residues, remaining):
    _expect(residues <= remaining[0], "residue_budget")
    remaining[0] -= residues


def _chemical_sites(chemistry):
    explicit, policies = {}, {}
    for modification in chemistry.modifications:
        token = modification.identity.fingerprint
        if modification.scope == "all_matching_bases":
            policies[modification.canonical_base] = token
        else:
            explicit.update((position, token) for position in modification.positions)
    return explicit, policies


def _site(coverage, sequence, position):
    explicit, policies = coverage
    return explicit.get(position, policies.get(sequence[position]))


def _edited_proposals(step, available, remaining):
    operation, port = step.operation, step.ports[0]
    source = available[operation.input.value.id]
    _expect(
        source.space.alphabet == "RNA" and port.alphabet == "RNA",
        "unsupported_alphabet",
    )
    _expect(port.topology == source.space.topology, "unsupported_topology")
    _reserve(source.space.length, remaining)
    chemistry = (
        port.chemistry_transition.output
        if port.chemistry_transition.mode == "explicit_output"
        else _reframe_chemistry(source.chemistry, port.space_id)
    )
    _expect(
        source.chemistry.modification_inventory_status == "declared"
        and chemistry.modification_inventory_status == "declared",
        "unsupported_edit_chemistry",
    )
    before, after = _chemical_sites(source.chemistry), _chemical_sites(chemistry)
    letters = list(source.sequence)
    for edit in operation.canonical_edits:
        _expect(
            edit.position < len(letters) and letters[edit.position] == edit.expected,
            "invalid_edit",
        )
        _expect(_site(before, source.sequence, edit.position) is None, "invalid_edit")
        letters[edit.position] = edit.replacement
    sequence = "".join(letters)
    changed_sites = {edit.position for edit in operation.canonical_edits}
    for edit in operation.canonical_edits:
        _expect(_site(after, sequence, edit.position) is None, "invalid_edit")
    for edit in operation.chemical_edits:
        _expect(
            edit.position < len(sequence)
            and source.sequence[edit.position] == edit.parent,
            "invalid_edit",
        )
        _expect(
            _site(before, source.sequence, edit.position)
            == (None if edit.before is None else edit.before.fingerprint),
            "invalid_edit",
        )
        _expect(
            _site(after, sequence, edit.position)
            == (None if edit.after is None else edit.after.fingerprint),
            "invalid_edit",
        )
        changed_sites.add(edit.position)
    for position in range(len(sequence)):
        if position not in changed_sites:
            _expect(
                _site(before, source.sequence, position)
                == _site(after, sequence, position),
                "invalid_edit",
            )
    for facet in ("cap", "start_end", "finish_end"):
        _expect(
            getattr(source.chemistry, facet).nominal_dict()
            == getattr(chemistry, facet).nominal_dict(),
            "invalid_edit",
        )
    segment = DerivedSegment(
        IndexSpan(0, len(sequence)),
        operation.input.value.id,
        _whole(source.space),
        "rna_editing.v1",
    )
    product = _finish_value(step, port, source, sequence, (segment,))
    return ((port, product, {operation.input.value.id: source}),)


_TRANSLATION_OPERATIONS = (
    TranslationOperation,
    MultiORFTranslationOperation,
    ConditionalTranslationOperation,
    RibosomalSkippingOperation,
)


def _translation_specs(step):
    operation = step.operation
    if isinstance(operation, MultiORFTranslationOperation):
        return tuple(
            (entry.port_id, entry.input, entry.policy) for entry in operation.products
        )
    if isinstance(operation, ConditionalTranslationOperation):
        return tuple(
            (branch.port_id, branch.input, branch.policy)
            for branch in operation.branches
            if branch.port_id is not None
        )
    return ((step.ports[0].id, operation.input, operation.policy),)


def _translated_peptide(step, source, path, policy):
    span = path.spans[0]
    triplets = tuple(
        source.sequence[index : index + 3] for index in range(span.start, span.end, 3)
    )
    overrides = {entry.codon_index: entry for entry in policy.recodings}
    for index, entry in overrides.items():
        _expect(
            index < len(triplets)
            and triplets[index] == entry.expected_triplet
            and entry.condition in step.assumptions,
            "invalid_translation",
        )
    coverage = _chemical_sites(source.chemistry)
    residues = []
    for index, triplet in enumerate(triplets):
        position = span.start + 3 * index
        modified = any(
            _site(coverage, source.sequence, position + offset) is not None
            for offset in range(3)
        )
        _expect(not modified or index in overrides, "unsupported_translation_chemistry")
        residues.append(
            overrides[index].amino_acid
            if index in overrides
            else STANDARD_RNA_CODON_TABLE[triplet]
        )
    _expect(
        residues[0] == "M" and residues[-1] == "*" and "*" not in residues[:-1],
        "invalid_translation",
    )
    return "".join(residues[:-1])


def _translation_proposals(step, available, remaining):
    operation = step.operation
    ports = {port.id: port for port in step.ports}
    _expect(
        all(port.alphabet == "protein" for port in step.ports), "unsupported_alphabet"
    )
    _expect(
        all(port.topology == "linear" for port in step.ports), "unsupported_topology"
    )
    plans = []
    total_length = 0
    for port_id, selection, policy in _translation_specs(step):
        source = available[selection.value.id]
        _expect(source.space.alphabet == "RNA", "unsupported_alphabet")
        path = _whole(source.space) if selection.path is None else selection.path
        path.validate_for(source.space)
        _expect(
            path.strand == "+" and len(path.spans) == 1, "unsupported_translation_path"
        )
        span = path.spans[0]
        _expect(
            path.length >= 6
            and path.length % 3 == 0
            and source.sequence[span.start : span.start + 3] == "AUG",
            "invalid_translation",
        )
        _expect(
            source.chemistry.modification_inventory_status == "declared",
            "unsupported_translation_chemistry",
        )
        residue_count = path.length // 3 - 1
        total_length += residue_count
        plans.append((port_id, selection, source, path, policy, residue_count))
    _reserve(total_length, remaining)
    if isinstance(operation, RibosomalSkippingOperation):
        cursor = 0
        for item in sorted(operation.products, key=lambda item: item.residues.start):
            _expect(
                item.residues.start == cursor and item.residues.length > 0,
                "invalid_skipping_partition",
            )
            cursor = item.residues.end
        _expect(cursor == plans[0][-1], "invalid_skipping_partition")
    proposals = []
    for port_id, selection, source, path, policy, residue_count in plans:
        peptide = _translated_peptide(step, source, path, policy)
        span = path.spans[0]
        stop = ConsumedSegment(
            selection.value.id,
            CoordinatePath(source.space.id, (IndexSpan(span.end - 3, span.end),), "+"),
            "terminal_stop",
        )
        pieces = (
            tuple((item.port_id, item.residues) for item in operation.products)
            if isinstance(operation, RibosomalSkippingOperation)
            else ((port_id, IndexSpan(0, residue_count)),)
        )
        for identity, residues in pieces:
            port = ports[identity]
            segment = DerivedSegment(
                IndexSpan(0, residues.length),
                selection.value.id,
                CoordinatePath(
                    source.space.id,
                    (
                        IndexSpan(
                            span.start + 3 * residues.start,
                            span.start + 3 * residues.end,
                        ),
                    ),
                    "+",
                ),
                "translation_codon.v1",
            )
            product = _finish_value(
                step,
                port,
                source,
                peptide[residues.start : residues.end],
                (segment,),
                (stop,),
            )
            proposals.append((port, product, {selection.value.id: source}))
    return tuple(proposals)


def _materialize_member(member, value):
    require(
        member.sequence_extent == value.sequence_extent,
        "Finalization cannot change supplied sequence extent.",
    )
    space = replace(value.space, id=member.space_id)
    features = tuple(
        replace(
            feature,
            path=None
            if feature.path is None
            else replace(feature.path, space_id=space.id),
        )
        for feature in value.features
    )
    return CircuitMolecule(
        member.id,
        member.form,
        space,
        value.sequence,
        member.sequence_extent,
        member.coding_status,
        (
            AssemblyOrigin(
                member.id + ".origin",
                _whole(space),
                value.space,
                _whole(value.space),
                member.provenance,
            ),
        ),
        features,
        _reframe_chemistry(value.chemistry, space.id),
        member.provenance,
    )


def _reconstruct(request):
    available = {root.id: root.molecule for root in request.sources}
    products, failures, transition_inputs = [], [], []
    remaining = [MAX_CUMULATIVE_PRODUCED_RESIDUES]
    for step in request.steps:
        operation = step.operation
        selections = _operands(operation)

        def reject(code):
            failures.append(f"step:{step.id}:{code}")

        if any(selection.value.id not in available for selection in selections):
            reject("unavailable_input")
            continue
        inputs = tuple(available[selection.value.id] for selection in selections)
        if any(value.sequence_extent != "complete" for value in inputs):
            reject("incomplete_input")
            continue
        try:
            paths = tuple(
                (
                    _whole(value.space) if selection.path is None else selection.path
                ).validate_for(value.space)
                for selection, value in zip(selections, inputs, strict=True)
            )
            require(
                all(path.length > 0 for path in paths), "Empty construction selection."
            )
        except SerializationError:
            reject("invalid_selection")
            continue
        if isinstance(operation, (BaseEditingOperation, *_TRANSLATION_OPERATIONS)):
            try:
                proposals = (
                    _edited_proposals(step, available, remaining)
                    if isinstance(operation, BaseEditingOperation)
                    else _translation_proposals(step, available, remaining)
                )
            except _ConstructionProblem as error:
                reject(error.code)
                continue
            except SerializationError:
                reject("invalid_operation")
                continue
            for port, product, input_values in proposals:
                products.append(product)
                available[product.id] = product
                transition_inputs.append((step, port, input_values, product))
            continue
        alphabets = {value.space.alphabet for value in inputs}
        if isinstance(
            operation,
            (RNACleavageOperation, RNASplicingOperation, CircularizationOperation),
        ):
            expected_alphabet = "RNA"
            allowed = alphabets == {"RNA"}
        elif isinstance(
            operation, (ProteinCleavageOperation, ProteinSplicingOperation)
        ):
            expected_alphabet = "protein"
            allowed = alphabets == {"protein"}
        elif isinstance(operation, TranscriptionOperation):
            expected_alphabet = "RNA"
            allowed = alphabets == {"DNA"}
        else:
            expected_alphabet = inputs[0].space.alphabet
            allowed = len(alphabets) == 1
            if isinstance(operation, OrientationOperation):
                allowed = allowed and expected_alphabet in {"DNA", "RNA"}
        if not allowed or any(
            port.alphabet != expected_alphabet for port in step.ports
        ):
            reject("unsupported_alphabet")
            continue
        if isinstance(operation, TranscriptionOperation) and (
            paths[0].strand != "+" or len(paths[0].spans) != 1
        ):
            reject("unsupported_transcription_path")
            continue
        if isinstance(
            operation, (*PROCESSING_OPERATION_TYPES, CircularizationOperation)
        ):
            expected_topology = (
                "circular"
                if isinstance(operation, CircularizationOperation)
                else "linear"
            )
            allowed_topology = inputs[0].space.topology == "linear"
        else:
            expected_topology = (
                inputs[0].space.topology
                if isinstance(operation, (SliceOperation, OrientationOperation))
                and selections[0].path is None
                else "linear"
            )
            allowed_topology = True
        if not allowed_topology or any(
            port.topology != expected_topology for port in step.ports
        ):
            reject("unsupported_topology")
            continue
        rule = "copy"
        if isinstance(operation, PROCESSING_OPERATION_TYPES):
            recipes = {recipe.port_id: recipe.path for recipe in operation.products}
            try:
                for recipe in recipes.values():
                    recipe.validate_for(inputs[0].space)
                    require(
                        recipe.length > 0
                        and all(span.length > 0 for span in recipe.spans),
                        "Empty processing selection.",
                    )
                planned_paths = tuple(
                    (port, (recipes[port.id],)) for port in step.ports
                )
            except SerializationError:
                reject("invalid_selection")
                continue
            spans = sorted(
                (span.start, span.end)
                for path in recipes.values()
                for span in path.spans
            )
            cursor, partition_valid = 0, True
            for start, end in spans:
                if start != cursor:
                    partition_valid = False
                cursor = end
            if cursor != inputs[0].space.length:
                partition_valid = False
            if any(
                any(
                    left.end > right.start
                    for left, right in zip(path.spans, path.spans[1:])
                )
                for path in recipes.values()
            ):
                partition_valid = False
            if not partition_valid:
                reject("invalid_processing_partition")
                continue
        elif isinstance(operation, CircularizationOperation):
            length = inputs[0].space.length
            if not 0 <= operation.origin < length:
                reject("invalid_selection")
                continue
            spans = (IndexSpan(operation.origin, length),)
            if operation.origin:
                spans += (IndexSpan(0, operation.origin),)
            paths = (CoordinatePath(inputs[0].space.id, spans, "+"),)
            planned_paths = ((step.ports[0], paths),)
        else:
            if isinstance(operation, OrientationOperation):
                paths = tuple(
                    replace(
                        path,
                        spans=tuple(reversed(path.spans)),
                        strand="-" if path.strand == "+" else "+",
                    )
                    for path in paths
                )
                if operation.action == "reverse_complement":
                    rule = "complement"
            elif isinstance(operation, TranscriptionOperation):
                rule = "dna_coding_to_rna.v1"
            planned_paths = ((step.ports[0], paths),)
        length = sum(
            path.length for _, product_paths in planned_paths for path in product_paths
        )
        # This guard precedes path traversal, reversal and all output allocation.
        if length > remaining[0]:
            reject("residue_budget")
            continue
        remaining[0] -= length
        try:
            proposed = tuple(
                _propose_value(step, port, selections, inputs, product_paths, rule)
                for port, product_paths in planned_paths
            )
        except SerializationError:
            reject("invalid_operation")
            continue
        for port, product in zip(step.ports, proposed, strict=True):
            products.append(product)
            available[product.id] = product
            transition_inputs.append(
                (
                    step,
                    port,
                    {
                        selection.value.id: value
                        for selection, value in zip(selections, inputs, strict=True)
                    },
                    product,
                )
            )

    if (
        sum(
            available[member.value.id].space.length
            for member in request.output_members
            if member.value.id in available
        )
        > MAX_RESIDUES
    ):
        failures.append("bundle:residue_budget")
        missing = tuple(
            member.id for member in (*request.output_members, *request.complex_members)
        )
        return ConstructionCandidate(
            request.fingerprint,
            tuple(products),
            None,
            missing,
            tuple(sorted(set(failures))),
        ), tuple(transition_inputs)
    members, missing = {}, []
    for member in request.output_members:
        value = available.get(member.value.id)
        if value is None:
            missing.append(member.id)
            failures.append(f"member:{member.id}:unavailable_value")
            continue
        try:
            molecule = _materialize_member(member, value)
        except SerializationError:
            missing.append(member.id)
            failures.append(f"member:{member.id}:invalid_molecule")
            continue
        members[member.id] = molecule
        if molecule.complete_nominal_identity is None:
            failures.append(f"member:{member.id}:nominal_incomplete")
    complexes = {}
    for plan in request.complex_members:
        if any(part.member_id not in members for part in plan.constituents):
            missing.append(plan.id)
            failures.append(f"member:{plan.id}:unavailable_value")
            continue
        try:
            complex_ = MolecularComplex(
                plan.id,
                plan.kind,
                tuple(
                    ComplexConstituent(
                        part.member_id,
                        members[part.member_id].fingerprint,
                        part.stoichiometry,
                        part.provenance,
                    )
                    for part in plan.constituents
                ),
                plan.provenance,
            )
        except SerializationError:
            missing.append(plan.id)
            failures.append(f"member:{plan.id}:invalid_molecule")
            continue
        complexes[plan.id] = complex_
        if any(
            part.stoichiometry is None
            or not members[part.member_id].declared_nominal_complete
            for part in plan.constituents
        ):
            failures.append(f"member:{plan.id}:nominal_incomplete")
    subjects = members | complexes
    bundle, amounts = None, ()
    if not missing:
        try:
            roles = tuple(
                MoleculeRoleInstance(
                    role.id,
                    member.id,
                    member.fingerprint,
                    role.role,
                    role.purpose,
                    role.compartment,
                )
                for requirement in request.requirements
                if requirement.member_id is not None
                for member in (subjects[requirement.member_id],)
                for role in requirement.roles
            )
            bundle = CircuitMoleculeSet(
                request.id + ".molecules",
                request.circuit,
                tuple(members.values()),
                tuple(complexes.values()),
                roles,
                (),
            )
            amounts = tuple(
                ExperimentalAmount(
                    amount.id,
                    amount.subject_id,
                    subjects[amount.subject_id].fingerprint,
                    amount.preparation_id,
                    amount.role_instance_ids,
                    amount.quantity,
                    amount.unit,
                    amount.provenance,
                )
                for amount in request.amounts
            )
            CircuitMoleculeRecord(bundle, amounts, {})
        except SerializationError:
            failures.append("bundle:invalid_inventory")
            bundle, amounts = None, ()
    return (
        ConstructionCandidate(
            request.fingerprint,
            tuple(products),
            bundle,
            tuple(missing),
            tuple(sorted(set(failures))),
            amounts,
        ),
        tuple(transition_inputs),
    )


def reconstruct_for_check(request):
    """Checker-private expected candidate; never an authoring or backend API."""
    require(
        isinstance(request, CircuitConstructionRequest),
        "Expected frozen construction authority.",
    )
    request = CircuitConstructionRequest.from_dict(request.to_dict())
    return _reconstruct(request)[0]


@dataclass(frozen=True)
class CircuitConstructionAssessment(_MoleculeRecord):
    request_fingerprint: str
    candidate_fingerprint: str
    reconstructed_fingerprint: str
    outcome: CheckOutcome
    complete: bool
    diagnostics: tuple[str, ...]
    checker_version: str = CHECKER_VERSION
    capability_version: str = CAPABILITY_PROFILE_VERSION
    construction_profile: str = CONSTRUCTION_PROFILE_VERSION
    admission_policy: str = ADMISSION_POLICY_VERSION
    claim_scope: str = CLAIM_SCOPE
    biological_function: str = "unestablished"
    empirical_validation: str = "unknown"
    human_therapeutic_admission: str = "not_admitted"
    schema_version: ClassVar[str] = "biocompiler.circuit_construction_assessment.v0.1"
    _decoders: ClassVar[dict] = {"outcome": CheckOutcome}

    def __post_init__(self):
        for key in (
            "request_fingerprint",
            "candidate_fingerprint",
            "reconstructed_fingerprint",
        ):
            _hash(getattr(self, key), key)
        require(
            isinstance(self.outcome, CheckOutcome),
            "Expected typed construction outcome.",
        )
        require(
            type(self.complete) is bool, "Construction completeness must be Boolean."
        )
        require(
            isinstance(self.diagnostics, (tuple, list))
            and len(self.diagnostics) <= MAX_ASSESSMENT_DIAGNOSTICS,
            "Invalid construction assessment diagnostics.",
        )
        for diagnostic in self.diagnostics:
            _text(
                diagnostic, "Construction assessment diagnostic", MAX_DIAGNOSTIC_BYTES
            )
        require(
            len(set(self.diagnostics)) == len(self.diagnostics),
            "Duplicate construction assessment diagnostics.",
        )
        object.__setattr__(self, "diagnostics", tuple(sorted(self.diagnostics)))
        require(
            self.checker_version == CHECKER_VERSION
            and self.capability_version == CAPABILITY_PROFILE_VERSION
            and self.construction_profile == CONSTRUCTION_PROFILE_VERSION
            and self.admission_policy == ADMISSION_POLICY_VERSION,
            "Construction assessment requires current checker, capability and policy versions.",
        )
        require(
            self.claim_scope == CLAIM_SCOPE
            and self.biological_function == "unestablished"
            and self.empirical_validation == "unknown"
            and self.human_therapeutic_admission == "not_admitted",
            "Structural construction cannot promote biological or human-use claims.",
        )
        require(
            self.complete == (self.outcome is CheckOutcome.PASS)
            and (self.outcome is not CheckOutcome.PASS or not self.diagnostics),
            "Construction completeness and diagnostics disagree with the outcome.",
        )
        self._check_resources()

    @property
    def passed(self):
        return self.outcome is CheckOutcome.PASS


def _candidate_differences(actual, expected):
    diagnostics = _DiagnosticInventory()
    if actual.request_fingerprint != expected.request_fingerprint:
        diagnostics.append("fail:candidate_request_authority")
    observed = {value.id: value for value in actual.values}
    wanted = {value.id: value for value in expected.values}
    if observed.keys() != wanted.keys():
        diagnostics.append("fail:constructed_value_inventory")
    for identity in sorted(observed.keys() & wanted.keys()):
        left, right = observed[identity], wanted[identity]
        for field in (
            "space",
            "sequence",
            "chemistry",
            "features",
            "segments",
            "consumed",
            "step_id",
            "sequence_extent",
        ):
            first, second = getattr(left, field), getattr(right, field)
            if hasattr(first, "fingerprint"):
                equal = first.fingerprint == second.fingerprint
            elif isinstance(first, tuple):
                equal = tuple(item.fingerprint for item in first) == tuple(
                    item.fingerprint for item in second
                )
            else:
                equal = first == second
            if not equal:
                diagnostics.append(f"fail:value:{identity}:{field}")
    if (None if actual.bundle is None else actual.bundle.fingerprint) != (
        None if expected.bundle is None else expected.bundle.fingerprint
    ):
        diagnostics.append("fail:final_molecule_inventory_or_authority")
    if actual.missing_members != expected.missing_members:
        diagnostics.append("fail:missing_member_inventory")
    if actual.diagnostics != expected.diagnostics:
        diagnostics.append("fail:construction_diagnostic_inventory")
    if tuple(item.fingerprint for item in actual.experimental_amounts) != tuple(
        item.fingerprint for item in expected.experimental_amounts
    ):
        diagnostics.append("fail:experimental_amount_authority")
    if actual.fingerprint != expected.fingerprint and not diagnostics:
        diagnostics.append("fail:complete_candidate_identity")
    return diagnostics


def check_circuit_construction(candidate, *, expected_request):
    """Reconstruct from complete independent authority and compare the actual artifact."""
    require(
        isinstance(expected_request, CircuitConstructionRequest),
        "Expected complete independent construction request.",
    )
    require(
        isinstance(candidate, ConstructionCandidate),
        "Expected a construction candidate.",
    )
    request = CircuitConstructionRequest.from_dict(expected_request.to_dict())
    actual = ConstructionCandidate.from_dict(candidate.to_dict())
    expected, transitions = _reconstruct(request)
    diagnostics = _candidate_differences(actual, expected)
    for step in request.steps:
        if isinstance(step.operation, ConditionalTranslationOperation):
            diagnostics.extend(
                f"unsupported:step:{step.id}:no_product_branch_semantics:{branch.id}"
                for branch in step.operation.branches
                if branch.port_id is None
            )
    for code in expected.diagnostics:
        if code.endswith(":nominal_incomplete"):
            status = "unknown"
        elif code.rsplit(":", 1)[-1].startswith("invalid_"):
            status = "fail"
        else:
            status = "unsupported"
        diagnostics.append(f"{status}:{code}")
    from biocompiler.verification.circuit_transitions import resolve_transitions

    for step, port, inputs, product in transitions:
        resolution = resolve_transitions(
            port.chemistry_transition,
            port.feature_transition,
            inputs=inputs,
            output_sequence=product.sequence,
            output_space=product.space,
            derivation=product.segments,
            sequence_extent=product.sequence_extent,
        )
        diagnostics.extend(
            f"fail:step:{step.id}:{item}" for item in resolution.diagnostics
        )
        diagnostics.extend(
            f"unsupported:step:{step.id}:{item}" for item in resolution.unsupported
        )
    if expected.bundle is not None:
        from biocompiler.verification.circuit_payloads import check_payload_structures

        payload_errors, payload_unsupported = check_payload_structures(
            request.payload_structures, bundle=expected.bundle
        )
        diagnostics.extend(f"fail:{item}" for item in payload_errors)
        diagnostics.extend(f"unsupported:{item}" for item in payload_unsupported)
    if expected.bundle is None and not diagnostics:
        diagnostics.append("fail:missing_final_bundle")
    statuses = {diagnostic.split(":", 1)[0] for diagnostic in diagnostics}
    outcome = next(
        (
            value
            for value in (
                CheckOutcome.FAIL,
                CheckOutcome.UNSUPPORTED,
                CheckOutcome.UNKNOWN,
            )
            if value.value in statuses
        ),
        CheckOutcome.PASS,
    )
    return CircuitConstructionAssessment(
        request.fingerprint,
        actual.fingerprint,
        expected.fingerprint,
        outcome,
        outcome is CheckOutcome.PASS,
        tuple(sorted(set(diagnostics))),
    )


def verify_circuit_construction_assessment(assessment, candidate, *, expected_request):
    """Historical labels grant no acceptance; compare the entire fresh assessment."""
    require(
        isinstance(assessment, CircuitConstructionAssessment),
        "Expected a historical construction assessment.",
    )
    saved = CircuitConstructionAssessment.from_dict(assessment.to_dict())
    fresh = check_circuit_construction(candidate, expected_request=expected_request)
    require(
        saved.fingerprint == fresh.fingerprint,
        "Construction assessment differs from fresh complete replay.",
    )
    return fresh

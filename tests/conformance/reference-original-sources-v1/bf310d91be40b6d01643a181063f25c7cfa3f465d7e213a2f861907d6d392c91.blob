"""Independent consistency checks for declared circuit intent.

Only complete source requests, nominal observation contracts and Boolean tables
are checked here. No compiler, authoring builder, mechanism constructor, sequence
emitter or biological evaluator supplies expected values. Historical assessment
records require fresh replay against independently retained complete authority.
"""

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import ClassVar

from biocompiler.artifacts.manifest import (
    _Record,
    _array,
    _decode_array,
    _hash,
    _plain_text,
)
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_intent import CircuitRequest
from biocompiler.ir.circuit_profile import ImmuneLineage
from biocompiler.ir.intent import freeze_json, thaw_json
from biocompiler.ir.serialization import (
    JsonArtifact,
    fields,
    fingerprint,
    names,
    parse_json,
    require,
)
from biocompiler.semantics import admission
from biocompiler.verification.evidence import CheckOutcome


CHECKER_VERSION = "biocompiler.circuit_intent_checker.v0.1"
CLAIM_SCOPE = "Typed circuit intent consistency only; no molecular implementation or biological function is established."
MAX_ASSESSMENT_JSON_BYTES = 4_000_000
MAX_RECEIPTS = 2048
MAX_DIAGNOSTICS = 4096
MAX_ASSESSMENT_ITEMS = 100_000
MAX_ASSESSMENT_DEPTH = 72
MAX_RECEIPT_TEXT_BYTES = 16_384
# A diagnostic may join a requirement ID and a provider ID with fixed text.
MAX_DIAGNOSTIC_TEXT_BYTES = 2 * MAX_RECEIPT_TEXT_BYTES + 128
_FIXED_FIELDS = {
    "claim_scope": CLAIM_SCOPE,
    "intent_consistency": "consistent",
    "outcome": "unsupported",
    "molecular_implementation": "unimplemented",
    "empirical_validation": "unknown",
    "human_therapeutic_admission": "not_admitted",
}


def _text(value, label, maximum=MAX_RECEIPT_TEXT_BYTES):
    require(
        isinstance(value, str) and len(value) <= maximum,
        f"{label} exceeds its text limit.",
    )
    _plain_text(value, label)
    require(len(value.encode("utf-8")) <= maximum, f"{label} exceeds its text limit.")


def _bounded_document(value):
    """Reject oversized or cyclic authority before decoding or JSON allocation."""
    pending = [(value, 0, False)]
    active = set()
    count = 0
    byte_count = 0
    while pending:
        item, depth, closing = pending.pop()
        if closing:
            active.remove(id(item))
            continue
        count += 1
        require(
            count <= MAX_ASSESSMENT_ITEMS, "Circuit assessment item limit exceeded."
        )
        require(
            depth <= MAX_ASSESSMENT_DEPTH, "Circuit assessment nesting limit exceeded."
        )
        if isinstance(item, (Mapping, tuple, list)):
            require(
                id(item) not in active, "Circuit assessment cannot contain cyclic data."
            )
            child_count = 2 * len(item) if isinstance(item, Mapping) else len(item)
            require(
                count + len(pending) + child_count <= MAX_ASSESSMENT_ITEMS,
                "Circuit assessment pending item limit exceeded.",
            )
            active.add(id(item))
            pending.append((item, depth, True))
            if isinstance(item, Mapping):
                for key, child in item.items():
                    require(
                        isinstance(key, str),
                        "Circuit assessment JSON keys must be strings.",
                    )
                    pending.extend(((key, depth + 1, False), (child, depth + 1, False)))
            else:
                pending.extend((child, depth + 1, False) for child in item)
            byte_count += child_count + 2
        elif isinstance(item, str):
            require(
                len(item) <= MAX_DIAGNOSTIC_TEXT_BYTES,
                "Circuit assessment text limit exceeded.",
            )
            try:
                size = len(item.encode("utf-8"))
            except UnicodeError as error:
                raise SerializationError(
                    "Circuit assessment text must be UTF-8."
                ) from error
            require(
                size <= MAX_DIAGNOSTIC_TEXT_BYTES,
                "Circuit assessment text limit exceeded.",
            )
            byte_count += size + 2
        elif type(item) is int:
            require(
                item.bit_length() <= 4096, "Circuit assessment integer limit exceeded."
            )
            byte_count += len(str(item))
        elif type(item) is float:
            require(math.isfinite(item), "Circuit assessment numbers must be finite.")
            byte_count += len(repr(item))
        else:
            require(
                item is None or type(item) is bool,
                "Circuit assessment requires JSON values.",
            )
            byte_count += 5
        require(
            byte_count <= MAX_ASSESSMENT_JSON_BYTES,
            "Circuit assessment aggregate byte limit exceeded.",
        )


def _bounded_receipts(value, kind, label):
    require(isinstance(value, (tuple, list)), f"{label} must be an array.")
    require(len(value) <= MAX_RECEIPTS, f"{label} exceeds its record limit.")
    return _array(value, kind, label)


@dataclass(frozen=True)
class CircuitSourceReceipt(_Record):
    """One complete original node, including its authored source location."""

    id: str
    kind: str
    role: str | None
    node_fingerprint: str
    schema_version: ClassVar[str] = "biocompiler.circuit_source_receipt.v0.1"

    def __post_init__(self):
        _text(self.id, "Source node identity")
        _text(self.kind, "Source operation")
        if self.role is not None:
            _text(self.role, "Source role")
        _hash(self.node_fingerprint, "Complete source node")


@dataclass(frozen=True)
class CircuitContractReceipt(_Record):
    """An unchanged source wrapper or build-context authority."""

    path: str
    contract_fingerprint: str
    schema_version: ClassVar[str] = "biocompiler.circuit_contract_receipt.v0.1"

    def __post_init__(self):
        _text(self.path, "Contract path")
        _hash(self.contract_fingerprint, "Complete source contract")


@dataclass(frozen=True)
class CircuitRequirementReceipt(_Record):
    """Requirement identity and its full declared nominal behavior bindings."""

    id: str
    role_id: str | None
    source_node_ids: tuple[str, ...]
    requirement_fingerprint: str
    behavior_fingerprint: str
    logic_fingerprint: str
    output_fingerprint: str
    schema_version: ClassVar[str] = "biocompiler.circuit_requirement_receipt.v0.1"

    def __post_init__(self):
        _text(self.id, "Circuit requirement identity")
        if self.role_id is not None:
            _text(self.role_id, "Circuit role")
        refs = names(self.source_node_ids, "Circuit source node identities")
        require(len(refs) <= MAX_RECEIPTS, "Too many circuit source node identities.")
        for ref in refs:
            _text(ref, "Circuit source node identity")
        object.__setattr__(self, "source_node_ids", refs)
        for key in (
            "requirement_fingerprint",
            "behavior_fingerprint",
            "logic_fingerprint",
            "output_fingerprint",
        ):
            _hash(getattr(self, key), key)


def _dependencies(request):
    source = request.profile.source_request
    return {
        "request": request.fingerprint,
        "profile": request.profile.fingerprint,
        "source_artifact": fingerprint(source.to_dict())
        if source is not None
        else None,
        "checker": CHECKER_VERSION,
        "request_schema": CircuitRequest.schema_version,
        "admission_policy": admission.ADMISSION_POLICY_VERSION,
    }


@dataclass(frozen=True)
class CircuitIntentAssessment(JsonArtifact):
    """Replayable historical intent consistency; implementation stays unresolved."""

    request: CircuitRequest
    source_inventory: tuple[CircuitSourceReceipt, ...]
    contract_inventory: tuple[CircuitContractReceipt, ...]
    requirement_inventory: tuple[CircuitRequirementReceipt, ...]
    diagnostics: tuple[str, ...]
    dependencies: Mapping
    schema_version: ClassVar[str] = "biocompiler.circuit_intent_assessment.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.request, CircuitRequest),
            "Expected complete circuit authority.",
        )
        object.__setattr__(
            self, "request", CircuitRequest.from_dict(self.request.to_dict())
        )
        for key, kind, identity in (
            ("source_inventory", CircuitSourceReceipt, "id"),
            ("contract_inventory", CircuitContractReceipt, "path"),
            ("requirement_inventory", CircuitRequirementReceipt, "id"),
        ):
            values = _bounded_receipts(getattr(self, key), kind, key)
            require(
                len({getattr(item, identity) for item in values}) == len(values),
                f"Duplicate {key} identities.",
            )
            object.__setattr__(self, key, values)
        require(
            bool(self.requirement_inventory),
            "Circuit assessment requires a requirement inventory.",
        )
        require(
            isinstance(self.diagnostics, (tuple, list))
            and 0 < len(self.diagnostics) <= MAX_DIAGNOSTICS,
            "Invalid circuit assessment diagnostics.",
        )
        diagnostics = names(self.diagnostics, "Circuit intent diagnostics")
        for item in diagnostics:
            _text(item, "Circuit intent diagnostic", MAX_DIAGNOSTIC_TEXT_BYTES)
        object.__setattr__(self, "diagnostics", tuple(sorted(diagnostics)))
        actual = _dependencies(self.request)
        fields(self.dependencies, set(actual), "Circuit assessment dependencies")
        for key in ("request", "profile", "source_artifact"):
            value = self.dependencies[key]
            if value is not None:
                _hash(value, f"Circuit dependency {key}")
            require(
                value == actual[key], f"Circuit dependency {key} differs from request."
            )
        for key in ("checker", "request_schema", "admission_policy"):
            _text(self.dependencies[key], f"Circuit policy {key}")
        object.__setattr__(self, "dependencies", freeze_json(self.dependencies))
        _bounded_document(self.to_dict())
        self.to_json()

    @property
    def outcome(self):
        return CheckOutcome.UNSUPPORTED

    @property
    def claim_scope(self):
        return CLAIM_SCOPE

    @property
    def intent_consistency(self):
        return "consistent"

    @property
    def molecular_implementation(self):
        return "unimplemented"

    @property
    def empirical_validation(self):
        return "unknown"

    @property
    def human_therapeutic_admission(self):
        return "not_admitted"

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            **_FIXED_FIELDS,
            "request": self.request.to_dict(),
            "source_inventory": [item.to_dict() for item in self.source_inventory],
            "contract_inventory": [item.to_dict() for item in self.contract_inventory],
            "requirement_inventory": [
                item.to_dict() for item in self.requirement_inventory
            ],
            "diagnostics": list(self.diagnostics),
            "dependencies": thaw_json(self.dependencies),
        }

    @classmethod
    def from_dict(cls, data):
        _bounded_document(data)
        fields(
            data,
            {
                "schema_version",
                "request",
                "source_inventory",
                "contract_inventory",
                "requirement_inventory",
                "diagnostics",
                "dependencies",
                *_FIXED_FIELDS,
            },
            "CircuitIntentAssessment",
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported circuit intent assessment schema.",
        )
        for key, value in _FIXED_FIELDS.items():
            require(
                type(data[key]) is type(value) and data[key] == value,
                f"Invalid circuit assessment {key}.",
            )
        for key in ("source_inventory", "contract_inventory", "requirement_inventory"):
            require(
                isinstance(data[key], (tuple, list)) and len(data[key]) <= MAX_RECEIPTS,
                f"Invalid {key} inventory.",
            )
        return cls(
            CircuitRequest.from_dict(data["request"]),
            _decode_array(data["source_inventory"], CircuitSourceReceipt),
            _decode_array(data["contract_inventory"], CircuitContractReceipt),
            _decode_array(data["requirement_inventory"], CircuitRequirementReceipt),
            data["diagnostics"],
            data["dependencies"],
        )

    def to_json(self, *, indent=2):
        require(
            indent is None or (type(indent) is int and 0 <= indent <= 8),
            "Invalid circuit assessment JSON indentation.",
        )
        _bounded_document(self.to_dict())
        try:
            text = super().to_json(indent=indent)
            size = len(text.encode("utf-8"))
        except (TypeError, ValueError, UnicodeError, RecursionError) as error:
            raise SerializationError(
                f"Invalid circuit assessment encoding: {error}"
            ) from error
        require(
            size + 1 <= MAX_ASSESSMENT_JSON_BYTES,
            "Circuit assessment byte limit exceeded (including publication newline).",
        )
        return text

    @classmethod
    def from_json(cls, text):
        require(isinstance(text, str), "Circuit assessment JSON must be text.")
        require(
            len(text) <= MAX_ASSESSMENT_JSON_BYTES,
            "Circuit assessment byte limit exceeded.",
        )
        try:
            size = len(text.encode("utf-8"))
        except UnicodeError as error:
            raise SerializationError(
                "Circuit assessment JSON must be UTF-8."
            ) from error
        require(
            size <= MAX_ASSESSMENT_JSON_BYTES, "Circuit assessment byte limit exceeded."
        )
        return cls.from_dict(parse_json(text))


def _source_receipts(source):
    """Inventory original nodes and wrappers without the requirement analyzer."""
    if source is None:
        return (), (), None
    document = source.to_dict()
    contracts = []
    current = document
    while current["schema_version"] != "biocompiler.build_request.v0.1":
        schema = current["schema_version"]
        if schema == "biocompiler.human_acceptance_request.v0.1":
            path, field, child = "acceptance", "acceptance", "deployment_request"
        elif schema == "biocompiler.human_deployment_request.v0.1":
            path, field, child = "deployment", "deployment", "behavior_request"
        elif schema == "biocompiler.human_behavior_request.v0.1":
            path, field, child = "behavior.contract", "contract", "build_request"
        else:
            raise SerializationError("Unsupported original circuit source wrapper.")
        contracts.append(CircuitContractReceipt(path, fingerprint(current[field])))
        current = current[child]
    build = current
    context = {key: value for key, value in build.items() if key != "intent"}
    contracts.append(
        CircuitContractReceipt("build_request.context", fingerprint(context))
    )
    intent = build["intent"]
    structure = {key: value for key, value in intent.items() if key != "nodes"}
    contracts.append(
        CircuitContractReceipt("build_request.intent_structure", fingerprint(structure))
    )
    contracts.append(
        CircuitContractReceipt("build_request.target", fingerprint(build["target"]))
    )
    nodes = tuple(
        CircuitSourceReceipt(item["id"], item["kind"], item["role"], fingerprint(item))
        for item in intent["nodes"]
    )
    return nodes, tuple(sorted(contracts, key=lambda item: item.path)), build


def _same_authority(left, right):
    return left.fingerprint == right.fingerprint and left.to_dict() == right.to_dict()


def _check_scope(request, build):
    profile = request.profile
    form_modalities = {
        "delivered_dna": "DNA",
        "dna_expression_template": "DNA",
        "primary_rna": "RNA",
        "delivered_rna": "RNA",
        "processed_rna": "RNA",
        "circular_rna": "RNA",
    }
    require(
        request.requested_form in form_modalities
        and form_modalities[request.requested_form] == profile.molecular_form,
        "Requested molecular form must preserve the declared DNA/RNA modality.",
    )
    require(
        request.fidelity_scope
        in {"base_identity", "source_nominal", "complete_nominal"},
        "Unrecognized circuit fidelity scope.",
    )
    experiment = profile.source_experiment
    if experiment is not None:
        require(
            type(experiment.recipient_taxon_id) is int
            and experiment.recipient_taxon_id == 9606,
            "Circuit experiment must declare a human recipient.",
        )
    if profile.purpose == "human_reference":
        require(
            build is None
            and profile.source_request is None
            and profile.target is None
            and profile.recipient is None
            and experiment is not None
            and profile.mode == "exact_reproduction",
            "Reference scope cannot replace a human deployment target.",
        )
        require(
            request.deployment_id is None,
            "Human reference cannot declare a deployment identity.",
        )
        return
    require(
        profile.purpose == "human_immune_payload"
        and build is not None
        and profile.target is not None
        and profile.recipient is not None,
        "Circuit product needs full original source and human immune target.",
    )
    target = profile.target
    human = target.human_target
    declared = human.to_dict()
    require(
        type(declared["recipient_taxon_id"]) is int
        and declared["recipient_taxon_id"] == 9606
        and declared["engineering"] == "in_vivo",
        "Circuit product target must retain human in-vivo scope.",
    )
    require(
        isinstance(profile.recipient.lineage, ImmuneLineage)
        and profile.recipient.target_fingerprint == target.fingerprint
        and profile.recipient.cell_subtype_claim_fingerprint
        == human.cell_subtype.fingerprint,
        "Circuit recipient must bind the original immune target.",
    )
    require(
        fingerprint(build["target"]) == target.fingerprint
        and build["target"] == target.to_dict(),
        "Original complete source target differs from circuit target.",
    )
    require(
        target.payload_format == profile.molecular_form,
        "Circuit source modality differs from target.",
    )
    _text(request.deployment_id, "Circuit deployment identity")


def _deployment_authority(source):
    if source is None:
        return None
    data = source.to_dict()
    if data["schema_version"] == "biocompiler.human_acceptance_request.v0.1":
        data = data["deployment_request"]
    if data["schema_version"] == "biocompiler.human_deployment_request.v0.1":
        return data["deployment"]
    return None


def _check_behavior(behavior):
    observations = {item.id: item for item in behavior.inputs}
    require(
        len(observations) == len(behavior.inputs),
        "Circuit input identities must be unique.",
    )
    signals = behavior.response.inputs
    require(
        {item.id for item in signals} == set(observations)
        and len(signals) == len(observations),
        "Every declared input must retain a Boolean signal binding.",
    )
    require(
        tuple(item.id for item in signals) == tuple(sorted(observations)),
        "Boolean signal order must be canonical.",
    )
    for signal in signals:
        require(
            signal.observation_fingerprint == observations[signal.id].fingerprint,
            "Boolean signal differs from its complete observation contract.",
        )
    require(
        all(item.scope == "cell_accessible" for item in behavior.inputs),
        "Circuit Boolean inputs require cell-accessible observation scope.",
    )
    require(
        len(behavior.response.outputs) == 2 ** len(signals)
        and all(type(value) is bool for value in behavior.response.outputs),
        "Circuit Boolean table must cover every input state.",
    )
    output = behavior.output
    quantity_for_product = {
        "protein_expression": "translation_rate",
        "mature_protein_quantity": "protein_abundance",
        "reporter_fluorescence": "fluorescence",
        "biological_activity": "downstream_activity",
        "rna_product": "rna_abundance",
    }
    require(
        output.kind in quantity_for_product
        and output.observation.quantity == quantity_for_product[output.kind],
        "Circuit product and output quantity express different requirements.",
    )
    require(
        output.observation.id not in observations,
        "Circuit input and output observation identities must be distinct.",
    )
    lifecycle_for_product = {
        "protein_expression": "production_control",
        "rna_product": "production_control",
        "mature_protein_quantity": "abundance_control",
        "biological_activity": "activity_control",
        "reporter_fluorescence": "readout",
    }
    require(
        behavior.lifecycle.mode == lifecycle_for_product[output.kind],
        "Circuit output product and lifecycle requirements differ.",
    )
    require(
        len({item.id for item in behavior.dependencies}) == len(behavior.dependencies),
        "Provider dependency identities must be unique.",
    )


def _check_lock(request):
    if request.profile.mode == "candidate_design":
        require(
            request.reference_lock is None,
            "Candidate design cannot reuse an exact reproduction lock.",
        )
        return
    require(
        request.profile.mode == "exact_reproduction"
        and request.reference_lock is not None,
        "Exact reproduction requires complete declared lock authority.",
    )
    lock = request.reference_lock
    require(
        bool(lock.authority)
        and all(pin.kind in {"source", "evidence"} for pin in lock.authority)
        and all(
            any(_same_authority(source_pin, retained) for retained in lock.authority)
            for source_pin in lock.source_experiment.sources
        ),
        "Exact lock must retain original source experiment authority pins.",
    )
    require(
        request.selected_realization is not None
        and _same_authority(request.selected_realization, lock.realization),
        "Selected circuit realization differs from exact lock.",
    )
    require(
        request.profile.source_experiment is not None
        and _same_authority(request.profile.source_experiment, lock.source_experiment),
        "Exact circuit source experiment differs from lock.",
    )
    require(
        request.requested_form == lock.requested_form
        and request.fidelity_scope == lock.fidelity_scope,
        "Exact circuit form or fidelity scope differs from lock.",
    )
    expected = {item.requirement_id: item.behavior for item in lock.expected_behaviors}
    require(
        len(expected) == len(lock.expected_behaviors)
        and set(expected) == {item.id for item in request.requirements},
        "Exact lock must cover every circuit requirement once.",
    )
    for requirement in request.requirements:
        require(
            _same_authority(requirement.behavior, expected[requirement.id]),
            "Circuit requirement differs from its locked nominal observations, Boolean table or output lifecycle.",
        )


def _check_requirement_scope(requirements):
    """Reject declared cross-requirement conflicts without physical inference."""
    products, outputs, inputs = set(), set(), {}
    for requirement in requirements:
        behavior = requirement.behavior
        product_key = (requirement.role_id, behavior.output.id)
        output_key = (requirement.role_id, behavior.output.observation.id)
        require(
            product_key not in products and output_key not in outputs,
            "Each role needs unique output product and observation identities across circuit requirements.",
        )
        products.add(product_key)
        outputs.add(output_key)
        for observation in behavior.inputs:
            key = (requirement.role_id, observation.id)
            require(
                key not in inputs or _same_authority(inputs[key], observation),
                "A shared circuit input identity must retain one exact nominal observation contract per role.",
            )
            inputs[key] = observation


def check_circuit_intent(request):
    """Check declaration consistency while retaining every original obligation."""
    require(
        isinstance(request, CircuitRequest),
        "Expected complete circuit intent authority.",
    )
    request = CircuitRequest.from_dict(request.to_dict())
    source_inventory, contract_inventory, build = _source_receipts(
        request.profile.source_request
    )
    _check_scope(request, build)
    _check_lock(request)
    _check_requirement_scope(request.requirements)
    diagnostics = {
        "molecular_implementation_unimplemented",
        "empirical_validation_unestablished",
        "human_therapeutic_use_not_admitted",
        "nominal_bindings_and_truth_tables_do_not_establish_physical_correspondence",
        "cross_requirement_physical_satisfiability_unestablished",
    }
    nodes = (
        {} if build is None else {item["id"]: item for item in build["intent"]["nodes"]}
    )
    deployment = _deployment_authority(request.profile.source_request)
    if build is None:
        contract_inventory = (
            CircuitContractReceipt(
                "source_experiment", request.profile.source_experiment.fingerprint
            ),
        )
        diagnostics.add("human_reference_context_is_not_a_deployment_contract")
    else:
        contract_inventory = (
            *contract_inventory,
            CircuitContractReceipt(
                "circuit.deployment_identity", fingerprint(request.deployment_id)
            ),
        )
        diagnostics.add(
            "circuit_requirements_are_additional_obligations_not_source_replacements"
        )
        if deployment is None:
            diagnostics.add(
                "declared_deployment_identity_needs_physical_deployment_refinement"
            )
        else:
            require(
                request.deployment_id == deployment["id"],
                "Circuit deployment identity differs from full source deployment authority.",
            )
        for node in source_inventory:
            diagnostics.add(
                f"source_node:{node.id}:{node.kind}:implementation_unresolved"
            )
        for contract in contract_inventory:
            diagnostics.add(
                f"source_contract:{contract.path}:implementation_unresolved"
            )
    if request.reference_lock is not None:
        diagnostics.add(
            "reference_lock_consistency_is_not_source_or_mechanism_validation"
        )
    if request.profile.source_experiment is not None:
        diagnostics.add(
            "source_context_does_not_establish_human_immune_or_in_vivo_applicability"
        )
    receipts = []
    require(
        len({item.id for item in request.requirements}) == len(request.requirements),
        "Circuit requirements must have distinct identities.",
    )
    for requirement in request.requirements:
        behavior = requirement.behavior
        _check_behavior(behavior)
        bindings = requirement.input_bindings
        observation_ids = {item.id for item in behavior.inputs}
        require(
            len(bindings) <= 8
            and len({item.observation_id for item in bindings}) == len(bindings),
            "Circuit input bindings require bounded unique observation identities.",
        )
        for binding in bindings:
            require(
                binding.observation_id in observation_ids
                and binding.source_node_id in requirement.source_node_ids,
                "Circuit input binding differs from declared input or retained source inventory.",
            )
        if build is None:
            require(
                requirement.role_id is None
                and not requirement.source_node_ids
                and not bindings,
                "Reference requirement cannot fabricate a therapeutic source role.",
            )
        else:
            role = nodes.get(requirement.role_id)
            require(
                role is not None
                and role["kind"] == "role"
                and role["attributes"].get("engineering") == "in_vivo",
                "Circuit requirement must bind an original in-vivo source role.",
            )
            require(
                requirement.role_id in requirement.source_node_ids,
                "Circuit source bindings must retain the owner role.",
            )
            if deployment is not None:
                require(
                    requirement.role_id == deployment["recipient_role"],
                    "Circuit role differs from original deployment recipient.",
                )
            for ref in requirement.source_node_ids:
                node = nodes.get(ref)
                require(
                    node is not None
                    and (node["role"] in (None, requirement.role_id))
                    and (node["kind"] != "role" or node["id"] == requirement.role_id),
                    "Circuit source reference is missing or belongs to another role.",
                )
            for binding in bindings:
                node = nodes.get(binding.source_node_id)
                require(
                    node is not None
                    and (node["role"] in (None, requirement.role_id))
                    and (node["kind"] != "role" or node["id"] == requirement.role_id),
                    "Circuit input binding must retain an original same-role source node.",
                )
            compartments = request.profile.target.compartments
            require(
                all(item.scope == "cell_accessible" for item in behavior.inputs),
                "Product circuit inputs must retain cell-accessible observation scope.",
            )
            require(
                all(
                    item.compartment in compartments and item.compartment != "abstract"
                    for item in (*behavior.inputs, behavior.output.observation)
                ),
                "Circuit observations require original physical target compartments.",
            )
            require(
                all(
                    item.compartment in compartments and item.compartment != "abstract"
                    for item in behavior.dependencies
                ),
                "Circuit providers require original physical target compartments.",
            )
        for observation in behavior.inputs:
            diagnostics.add(
                f"requirement:{requirement.id}:input:{observation.id}:sensing_unimplemented"
            )
            if build is not None and observation.id not in {
                item.observation_id for item in bindings
            }:
                diagnostics.add(
                    f"requirement:{requirement.id}:input:{observation.id}:source_correspondence_unspecified"
                )
            if observation.scope != "cell_accessible":
                diagnostics.add(
                    f"requirement:{requirement.id}:input:{observation.id}:cell_accessibility_unresolved"
                )
            if observation.window.aggregation == "unknown":
                diagnostics.add(
                    f"requirement:{requirement.id}:input:{observation.id}:timing_unspecified"
                )
        diagnostics.add(f"requirement:{requirement.id}:output_lifecycle_unimplemented")
        for name in ("onset", "cessation", "clearance"):
            if getattr(behavior.lifecycle, name) is None:
                diagnostics.add(
                    f"requirement:{requirement.id}:lifecycle:{name}:unspecified"
                )
        for provider in behavior.dependencies:
            diagnostics.add(
                f"requirement:{requirement.id}:provider:{provider.id}:availability_and_colocation_unestablished"
            )
        receipts.append(
            CircuitRequirementReceipt(
                requirement.id,
                requirement.role_id,
                requirement.source_node_ids,
                requirement.fingerprint,
                behavior.fingerprint,
                behavior.response.fingerprint,
                behavior.output.fingerprint,
            )
        )
    return CircuitIntentAssessment(
        request,
        source_inventory,
        contract_inventory,
        tuple(receipts),
        tuple(sorted(diagnostics)),
        _dependencies(request),
    )


def verify_circuit_intent(assessment, *, expected_request):
    """Replay using complete independently retained source and circuit authority."""
    require(
        isinstance(assessment, CircuitIntentAssessment)
        and isinstance(expected_request, CircuitRequest),
        "Fresh circuit replay needs an assessment and independent complete request.",
    )
    saved = CircuitIntentAssessment.from_dict(assessment.to_dict())
    authority = CircuitRequest.from_dict(expected_request.to_dict())
    require(
        _same_authority(saved.request, authority),
        "Saved circuit assessment differs from independent complete authority.",
    )
    current = check_circuit_intent(authority)
    require(
        saved.to_dict() == current.to_dict(),
        "Saved circuit assessment differs from current independent checks.",
    )
    return current

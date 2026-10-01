"""Executable, supplied component-to-molecule contracts.

These records bind a closed executable model to exact supplied construction
authority. They establish a conditional translation contract, never an empirical
claim that a molecule implements its model in a patient. In particular, no
sequence is inferred from an operator name or a Boolean truth table.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from biocompiler.ir.circuit_construction import (
    MAX_AMOUNT_DECLARATIONS,
    MAX_COMPLEX_MEMBERS,
    MAX_MEMBER_REQUIREMENTS,
    MAX_OUTPUT_MEMBERS,
    MAX_PRODUCTS,
    MAX_ROLE_DECLARATIONS,
    MAX_SOURCES,
    MAX_STEPS,
    MAX_TOTAL_SOURCE_RESIDUES,
    AmountDeclaration,
    CircuitConstructionRequest,
    ComplexMemberPlan,
    MemberRequirement,
    OutputMember,
    RootSource,
    TransformStep,
    operation_selections,
)
from biocompiler.ir.circuit_payloads import MAX_PAYLOAD_CONTRACTS, PayloadStructureContract
from biocompiler.ir.circuit_intent import CircuitLifecycle
from biocompiler.ir.circuit_observations import CircuitProduct
from biocompiler.ir.component_contracts import ComponentRecord
from biocompiler.ir.composition import Provider
from biocompiler.ir.intent import freeze_json
from biocompiler.ir.molecule_records import (
    _MoleculeRecord,
    _decode_records,
    _optional,
    _records,
    _text,
)
from biocompiler.ir.serialization import require


MAX_PAYLOAD_CONTRACTS_IN_LIBRARY = 256
MAX_PAYLOAD_BINDINGS = 256
MAX_PAYLOAD_PROVIDERS = 256
MAX_PAYLOAD_ASSUMPTIONS = 64


def _assumptions(values):
    require(isinstance(values, (tuple, list)) and len(values) <= MAX_PAYLOAD_ASSUMPTIONS,
            "Invalid executable payload assumption inventory.")
    for value in values:
        _text(value, "Executable payload assumption")
    require(len(set(values)) == len(values), "Duplicate executable payload assumptions.")
    return tuple(sorted(values))


@dataclass(frozen=True)
class PayloadTemplate(_MoleculeRecord):
    """A complete reusable construction fragment, before source binding.

    Sequence, chemistry, regulatory regions and processing relationships retain
    their ordinary construction IR. A helper-only fragment is permitted; the
    combined construction must still contain a requested payload. Source-scoped
    external providers and target compartments are checked when materialized
    against the independently supplied circuit request.
    """

    id: str
    sources: tuple[RootSource, ...]
    steps: tuple[TransformStep, ...]
    output_members: tuple[OutputMember, ...]
    requirements: tuple[MemberRequirement, ...]
    complex_members: tuple[ComplexMemberPlan, ...] = ()
    amounts: tuple[AmountDeclaration, ...] = ()
    payload_structures: tuple[PayloadStructureContract, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.payload_template.v0.1"
    _decoders: ClassVar[dict] = {
        "sources": _decode_records(RootSource, MAX_SOURCES),
        "steps": _decode_records(TransformStep, MAX_STEPS),
        "output_members": _decode_records(OutputMember, MAX_OUTPUT_MEMBERS),
        "requirements": _decode_records(MemberRequirement, MAX_MEMBER_REQUIREMENTS),
        "complex_members": _decode_records(ComplexMemberPlan, MAX_COMPLEX_MEMBERS),
        "amounts": _decode_records(AmountDeclaration, MAX_AMOUNT_DECLARATIONS),
        "payload_structures": _decode_records(PayloadStructureContract, MAX_PAYLOAD_CONTRACTS),
    }

    def __post_init__(self):
        _text(self.id, "Payload template identity")
        for key, cls, maximum, nonempty in (
            ("sources", RootSource, MAX_SOURCES, True),
            ("output_members", OutputMember, MAX_OUTPUT_MEMBERS, True),
            ("requirements", MemberRequirement, MAX_MEMBER_REQUIREMENTS, True),
            ("complex_members", ComplexMemberPlan, MAX_COMPLEX_MEMBERS, False),
            ("amounts", AmountDeclaration, MAX_AMOUNT_DECLARATIONS, False),
        ):
            object.__setattr__(self, key, _records(
                getattr(self, key), cls, maximum, key, nonempty=nonempty))
        object.__setattr__(self, "payload_structures", _records(
            self.payload_structures, PayloadStructureContract, MAX_PAYLOAD_CONTRACTS,
            "payload structures", key="member_id"))
        require(isinstance(self.steps, (tuple, list)) and len(self.steps) <= MAX_STEPS,
                "Invalid ordered payload template steps.")
        require(all(isinstance(step, TransformStep) for step in self.steps),
                "Payload template steps require construction records.")
        steps = tuple(TransformStep.from_dict(step.to_dict()) for step in self.steps)
        require(len({step.id for step in steps}) == len(steps),
                "Duplicate payload template step identities.")
        object.__setattr__(self, "steps", steps)
        require(sum(len(source.molecule.sequence) for source in self.sources)
                <= MAX_TOTAL_SOURCE_RESIDUES, "Payload template source residue limit exceeded.")
        require(sum(len(step.ports) for step in steps) <= MAX_PRODUCTS,
                "Payload template product limit exceeded.")

        # Validate the source-independent reference graph now. The ordinary
        # construction request performs the complete contextual validation when
        # a compiler binds this fragment to an original source request.
        available = {source.id: ("root", source.molecule.space.id) for source in self.sources}
        frames = {source.molecule.space.id for source in self.sources}
        require(len(frames) == len(self.sources), "Template roots require unique coordinate frames.")
        for step in steps:
            for selection in operation_selections(step.operation):
                ref = selection.value
                require(ref.id in available and available[ref.id][0] == ref.kind,
                        "Template operation refers to an absent or forward value.")
                require(selection.path is None or selection.path.space_id == available[ref.id][1],
                        "Template selection uses a different coordinate frame.")
            for port in step.ports:
                require(port.id not in available, "Duplicate template product value identity.")
                require(port.space_id not in frames, "Duplicate template product coordinate frame.")
                available[port.id] = ("product", port.space_id)
                frames.add(port.space_id)
        members = {member.id: member for member in self.output_members}
        complexes = {member.id: member for member in self.complex_members}
        require(not members.keys() & complexes.keys(), "Template member and complex identities collide.")
        for member in self.output_members:
            ref = member.value
            require(ref.id in available and available[ref.id][0] == ref.kind,
                    "Template member refers to an absent construction value.")
            require(member.space_id not in frames, "Duplicate template output coordinate frame.")
            frames.add(member.space_id)
        for complex_ in self.complex_members:
            require(all(item.member_id in members for item in complex_.constituents),
                    "Template complex refers to an absent covalent member.")
        demanded = {member.value.id for member in self.output_members if member.value.kind == "product"}
        for step in reversed(steps):
            require(all(port.id in demanded for port in step.ports),
                    "Every template product must contribute to an output member.")
            demanded.update(selection.value.id for selection in operation_selections(step.operation)
                            if selection.value.kind == "product")
        subjects = set(members) | set(complexes)
        covered, roles = set(), {}
        for requirement in self.requirements:
            if requirement.member_id is not None:
                require(requirement.member_id in subjects, "Template requirement names an absent member.")
                covered.add(requirement.member_id)
            for role in requirement.roles:
                require(role.id not in roles, "Duplicate template role identity.")
                roles[role.id] = requirement.member_id
        require(len(roles) <= MAX_ROLE_DECLARATIONS, "Template role limit exceeded.")
        require(covered == subjects, "Every template member needs an explicit requirement disposition.")
        preparations = set()
        for amount in self.amounts:
            require(amount.subject_id in subjects and all(
                roles.get(identity) == amount.subject_id for identity in amount.role_instance_ids),
                "Template amount must retain its member and role identities.")
            key = (amount.preparation_id, amount.subject_id)
            require(key not in preparations, "Duplicate template preparation amount.")
            preparations.add(key)
        require(all(structure.member_id in members for structure in self.payload_structures),
                "Template payload structure names an absent covalent member.")
        self._check_resources()

    @classmethod
    def from_construction_request(cls, request: CircuitConstructionRequest, *, id=None):
        require(isinstance(request, CircuitConstructionRequest), "Expected construction authority.")
        return cls(id or request.id, request.sources, request.steps, request.output_members,
                   request.requirements, request.complex_members, request.amounts,
                   request.payload_structures)

    def to_construction_request(self, circuit, *, id=None, mode="strict"):
        return CircuitConstructionRequest(
            id or self.id, circuit, self.sources, self.steps, self.output_members,
            self.requirements, mode, self.complex_members, self.amounts, self.payload_structures)


@dataclass(frozen=True)
class PayloadPortBinding(_MoleculeRecord):
    """Associate one executable port with material or an external observation."""

    port_id: str
    member_id: str | None
    compartment: str
    feature_id: str | None = None
    external_id: str | None = None
    schema_version: ClassVar[str] = "biocompiler.payload_port_binding.v0.1"

    def __post_init__(self):
        _text(self.port_id, "Payload port identity")
        _text(self.compartment, "Payload port compartment")
        require((self.member_id is None) != (self.external_id is None),
                "A payload port binds exactly one material member or external observation.")
        if self.member_id is not None:
            _text(self.member_id, "Payload port member")
        if self.external_id is not None:
            _text(self.external_id, "Payload external observation")
            require(self.feature_id is None, "An external observation has no template feature.")
        if self.feature_id is not None:
            _text(self.feature_id, "Payload port feature")
        self._check_resources()


@dataclass(frozen=True)
class PayloadCapabilityBinding(_MoleculeRecord):
    """Make a component's provided capability depend on a supplied member."""

    capability_id: str
    member_id: str
    compartment: str
    schema_version: ClassVar[str] = "biocompiler.payload_capability_binding.v0.1"

    def __post_init__(self):
        for key in ("capability_id", "member_id", "compartment"):
            _text(getattr(self, key), key)
        self._check_resources()


@dataclass(frozen=True)
class PayloadComponentContract(_MoleculeRecord):
    """Exact executable behavior, interfaces and its independently supplied bases.

    ``synthetic_model`` names the existing closed software semantics, including
    temporal state and reset behavior; it does not classify the sequence as a
    demonstrated biological implementation. Assumptions are mandatory so this
    conditional interpretation cannot be silently omitted.

    Supplementary product/readout and lifecycle meaning, when supplied, is
    separately pinned in typed records. A shared product label never supplies
    that correspondence by itself.
    """

    id: str
    component: ComponentRecord
    template: PayloadTemplate | None
    port_bindings: tuple[PayloadPortBinding, ...]
    assumptions: tuple[str, ...]
    capability_bindings: tuple[PayloadCapabilityBinding, ...] = ()
    effect: Mapping[str, Any] | None = None
    output_product: CircuitProduct | None = None
    output_lifecycle: CircuitLifecycle | None = None
    schema_version: ClassVar[str] = "biocompiler.payload_component_contract.v0.1"
    _decoders: ClassVar[dict] = {
        "component": ComponentRecord.from_dict,
        "template": _optional(PayloadTemplate),
        "port_bindings": _decode_records(PayloadPortBinding, MAX_PAYLOAD_BINDINGS),
        "capability_bindings": _decode_records(PayloadCapabilityBinding, MAX_PAYLOAD_BINDINGS),
        "output_product": _optional(CircuitProduct),
        "output_lifecycle": _optional(CircuitLifecycle),
    }

    def __post_init__(self):
        _text(self.id, "Payload component contract identity")
        require(isinstance(self.component, ComponentRecord), "Payload contracts require a typed component.")
        component = ComponentRecord.from_dict(self.component.to_dict())
        require(component.synthetic_model is not None,
                "Payload contracts require a closed executable component model.")
        object.__setattr__(self, "component", component)
        require(self.template is None or isinstance(self.template, PayloadTemplate),
                "Payload contracts require supplied typed construction templates.")
        if self.template is not None:
            object.__setattr__(self, "template", PayloadTemplate.from_dict(self.template.to_dict()))
        object.__setattr__(self, "port_bindings", _records(
            self.port_bindings, PayloadPortBinding, MAX_PAYLOAD_BINDINGS,
            "payload port bindings", key="port_id", nonempty=True))
        object.__setattr__(self, "capability_bindings", _records(
            self.capability_bindings, PayloadCapabilityBinding, MAX_PAYLOAD_BINDINGS,
            "payload capability bindings", key="capability_id"))
        object.__setattr__(self, "assumptions", _assumptions(self.assumptions))
        require(bool(self.assumptions), "An executable-to-molecule contract requires explicit assumptions.")
        require((self.output_product is None) == (self.output_lifecycle is None),
                "Supplementary output contracts require both a product and lifecycle declaration.")
        if self.output_product is not None:
            require(component.synthetic_model.operation == "output",
                    "Only an output component may declare supplementary output semantics.")
            require(isinstance(self.output_product, CircuitProduct)
                    and isinstance(self.output_lifecycle, CircuitLifecycle),
                    "Supplementary output semantics require typed product and lifecycle authority.")
            object.__setattr__(self, "output_product", CircuitProduct.from_dict(self.output_product.to_dict()))
            object.__setattr__(self, "output_lifecycle", CircuitLifecycle.from_dict(self.output_lifecycle.to_dict()))
        if self.effect is not None:
            require(component.synthetic_model.operation == "output",
                    "Only an output component may declare an action effect.")
            require(isinstance(self.effect, Mapping) and set(self.effect) == {"kind", "attributes", "product"},
                    "An action effect requires exact kind, attributes and product fields.")
            _text(self.effect["kind"], "Payload action kind")
            require(isinstance(self.effect["attributes"], Mapping), "Payload action attributes must be an object.")
            if self.effect["product"] is not None:
                _text(self.effect["product"], "Payload action product")
            object.__setattr__(self, "effect", freeze_json(dict(self.effect)))
        require({binding.port_id for binding in self.port_bindings} == {port.id for port in component.ports},
                "Payload bindings must cover exactly every executable component port.")
        require({binding.capability_id for binding in self.capability_bindings}
                == {capability.id for capability in component.capabilities},
                "Payload bindings must cover exactly every provided capability.")
        members = set() if self.template is None else (
            {member.id for member in self.template.output_members}
            | {member.id for member in self.template.complex_members})
        covalent = set() if self.template is None else {member.id for member in self.template.output_members}
        member_compartments = {}
        if self.template is not None:
            for requirement in self.template.requirements:
                if requirement.member_id is not None:
                    member_compartments.setdefault(requirement.member_id, set()).update(
                        role.compartment for role in requirement.roles)
        for binding in self.port_bindings:
            port = component.port(binding.port_id)
            require(binding.compartment == port.compartment,
                    "Payload binding and executable port compartments disagree.")
            if binding.member_id is not None:
                require(binding.member_id in members, "Payload port names an absent template member.")
                require(binding.compartment in member_compartments[binding.member_id],
                        "Payload port compartment lacks a matching material role.")
                require(binding.feature_id is None or binding.member_id in covalent,
                        "Payload port features require a covalent member.")
            else:
                require(port.direction == "input" or component.synthetic_model.operation == "input",
                        "An executable output requires a material binding.")
                require(binding.external_id == port.meaning,
                        "External observation must retain the exact executable port meaning.")
        for binding in self.capability_bindings:
            capability = next(item for item in component.capabilities if item.id == binding.capability_id)
            require(binding.member_id in members, "Payload capability names an absent template member.")
            require(binding.compartment == capability.compartment
                    and binding.compartment in member_compartments[binding.member_id],
                    "Payload capability and material compartments disagree.")
        if self.template is None:
            require(component.synthetic_model.operation == "input"
                    and all(binding.external_id is not None for binding in self.port_bindings)
                    and not component.capabilities,
                    "Only an explicit external input adapter may omit its sequence template.")
        self._check_resources()


def namespace_payload_template(template: PayloadTemplate, prefix: str) -> PayloadTemplate:
    """Rename local construction identities without changing supplied meaning.

    ``prefix`` is literal (the pipeline uses ``p000_``, ``p001_``, ...).
    Source/evidence pins, source-origin frames, features within a molecule,
    chemistry, model meaning, role names, assumptions and external providers
    are retained. Only local identities and references to them are renamed.
    """
    require(isinstance(template, PayloadTemplate), "Expected a payload template.")
    _text(prefix, "Payload template namespace", 64)
    frames = {source.molecule.space.id for source in template.sources}
    frames.update(port.space_id for step in template.steps for port in step.ports)
    frames.update(member.space_id for member in template.output_members)
    local_identity_schemas = {
        "biocompiler.payload_template.v0.1",
        "biocompiler.construction_root_source.v0.1",
        "biocompiler.circuit_molecule.v0.1",
        "biocompiler.construction_transform_step.v0.1",
        "biocompiler.construction_product_port.v0.1",
        "biocompiler.construction_value_ref.v0.1",
        "biocompiler.construction_output_member.v0.1",
        "biocompiler.construction_member_requirement.v0.1",
        "biocompiler.construction_role_declaration.v0.1",
        "biocompiler.construction_complex_member.v0.1",
        "biocompiler.construction_amount_declaration.v0.1",
    }

    def rename(value):
        if isinstance(value, list):
            return [rename(item) for item in value]
        if not isinstance(value, dict):
            return value
        schema = value.get("schema_version")
        if schema == "biocompiler.molecular_declaration_provenance.v0.1":
            return value
        result = {key: rename(item) for key, item in value.items()}
        if schema in local_identity_schemas:
            result["id"] = prefix + value["id"]
        if schema == "biocompiler.molecule_coordinate_space.v0.1" and value["id"] in frames:
            result["id"] = prefix + value["id"]
        if "space_id" in value and value["space_id"] in frames:
            result["space_id"] = prefix + value["space_id"]
        # These references occur only inside typed construction records. Feature
        # IDs are molecule-local, so their spellings deliberately stay intact.
        for key in ("member_id", "port_id"):
            if value.get(key) is not None:
                result[key] = prefix + value[key]
        if schema in {"biocompiler.chemistry_disposition.v0.1", "biocompiler.feature_disposition.v0.1"}:
            result["source_id"] = prefix + value["source_id"]
        if schema == "biocompiler.construction_amount_declaration.v0.1":
            for key in ("subject_id", "preparation_id"):
                result[key] = prefix + value[key]
            result["role_instance_ids"] = [prefix + identity for identity in value["role_instance_ids"]]
        return result

    return PayloadTemplate.from_dict(rename(template.to_dict()))


def merge_payload_templates(templates, circuit, *, id, mode="strict"):
    """Combine already namespaced selected fragments through construction IR.

    This is a producer utility, not independent verification authority. Checkers
    must reconstruct this merge from the original supplied component library.
    """
    require(isinstance(templates, (tuple, list)) and len(templates) <= MAX_PAYLOAD_CONTRACTS_IN_LIBRARY,
            "Invalid selected template inventory.")
    require(all(isinstance(template, PayloadTemplate) for template in templates),
            "Selected templates require typed authority.")
    inventories = {key: tuple(item for template in templates for item in getattr(template, key))
                   for key in ("sources", "steps", "output_members", "requirements", "complex_members", "amounts", "payload_structures")}
    return CircuitConstructionRequest(id=id, circuit=circuit, mode=mode, **inventories)


@dataclass(frozen=True)
class PayloadContractLibrary(_MoleculeRecord):
    """Full independent component/template authority and declared providers."""

    id: str
    contracts: tuple[PayloadComponentContract, ...]
    providers: tuple[Provider, ...] = ()
    assumptions: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.payload_contract_library.v0.1"
    _decoders: ClassVar[dict] = {
        "contracts": _decode_records(PayloadComponentContract, MAX_PAYLOAD_CONTRACTS_IN_LIBRARY),
        "providers": _decode_records(Provider, MAX_PAYLOAD_PROVIDERS),
    }

    def __post_init__(self):
        _text(self.id, "Payload contract library identity")
        object.__setattr__(self, "contracts", _records(
            self.contracts, PayloadComponentContract, MAX_PAYLOAD_CONTRACTS_IN_LIBRARY,
            "payload component contracts"))
        object.__setattr__(self, "providers", _records(
            self.providers, Provider, MAX_PAYLOAD_PROVIDERS, "payload providers"))
        object.__setattr__(self, "assumptions", _assumptions(self.assumptions))
        # A component identity is never allowed to stand for divergent executable
        # models in the same authority inventory. Distinct templates may realize
        # one identical model and remain independent selection alternatives.
        identities = {}
        for contract in self.contracts:
            component = contract.component
            key = (component.id, component.version)
            require(key not in identities or identities[key] == component.fingerprint,
                    "Conflicting component authority for one component identity.")
            identities[key] = component.fingerprint
        provider_ids = {provider.id for provider in self.providers}
        require(all(set(provider.depends_on) <= provider_ids for provider in self.providers),
                "External provider prerequisite names an absent provider.")
        self._check_resources()

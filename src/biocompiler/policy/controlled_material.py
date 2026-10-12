"""Immutable complete controlled authority, without a biological evaluator.

This preparation layer checks closed representation and reuses typed molecular
records. It neither repairs caller pins nor constructs, executes or accepts RNA.
Native admission is a separate operation; construction and behavior remain RC4/5.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import ClassVar, cast

from biocompiler.core_client import JsonValue, decode_json, encode_json
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.circuit_recoding import TranslationPolicy
from biocompiler.ir.molecule_chemistry import MoleculeChemistry
from biocompiler.ir.molecule_records import DeclarationProvenance, _bounded_tree
from biocompiler.ir.payload_contracts import PayloadTemplate
from . import model as m
from .controlled_composition import (
    PROFILE, SOURCE_AUTHORITY_SCHEMA, ActualActivityDelays, ActivityDeadlines,
    ControllerBinding, ProductMemberBinding, SourceAuthoritySnapshot,
    _object, _require, _text,
)
from .serialization import from_data

REQUEST_SCHEMA = "biocompiler.policy_component_material_request.v0.14"
RESOURCE_PROFILE = "biocompiler.policy_controlled_composition_resources.v0.1"
ROOT_FIELDS = frozenset({"schema_version", "profile", "source_authority", "mechanism_model",
    "operating_domain", "material_authority", "catalog_binding", "assembly", "context", "resources", "budgets"})


def _record(value: JsonValue, fields: str, label: str) -> dict[str, JsonValue]:
    return _object(value, set(fields.split()), label)


def _array(value: JsonValue, maximum: int, *, exact: int | None = None) -> list[JsonValue]:
    _require(type(value) is list and len(value) <= maximum
             and (exact is None or len(value) == exact), "Invalid closed authority array")
    return cast(list[JsonValue], value)


def _texts(value: JsonValue, maximum: int = 128) -> list[str]:
    values = [_text(item, "Authority text", 4096) for item in _array(value, maximum)]
    _require(len(set(values)) == len(values), "Duplicate authority identifier")
    return values


def _integer(value: object, maximum: int, minimum: int = 1) -> int:
    _require(type(value) is int and minimum <= value <= maximum, "Invalid exact integer resource limit")
    return cast(int, value)


def _ref(value: JsonValue, kind: str) -> m.Ref:
    result = from_data(value, m.Ref)
    _require(result.kind == kind, "Unexpected reference kind")
    return result


def _definition(value: JsonValue) -> m.DefinitionRef:
    from .controlled_composition import _definition as check
    result = from_data(value, m.DefinitionRef)
    check(result)
    return result


@dataclass(frozen=True, slots=True)
class ControlledBudgets:
    max_work: int = 100_000_000
    max_report_bytes: int = 1_000_000
    max_report_nodes: int = 100_000

    def to_data(self) -> dict[str, JsonValue]:
        return {"profile": RESOURCE_PROFILE,
                "max_work": _integer(self.max_work, 1_000_000_000),
                "max_report_bytes": _integer(self.max_report_bytes, 8_323_072),
                "max_report_nodes": _integer(self.max_report_nodes, 249_968)}

    @classmethod
    def from_data(cls, value: JsonValue) -> ControlledBudgets:
        row = _record(value, "profile max_work max_report_bytes max_report_nodes", "Budgets")
        _require(row["profile"] == RESOURCE_PROFILE, "Wrong controlled budget profile")
        return cls(_integer(row["max_work"], 1_000_000_000),
                   _integer(row["max_report_bytes"], 8_323_072), _integer(row["max_report_nodes"], 249_968))


def _material(value: JsonValue) -> PayloadTemplate:
    row = _record(value, "schema_version profile template member_order members", "Full molecular authority")
    _require(row["schema_version"] == "biocompiler.policy_mrna_structure_authority.v0.1"
             and row["profile"] == "biocompiler.policy_mrna_completeness.v0.1", "Wrong molecular authority")
    template = PayloadTemplate.from_dict(row["template"])
    order = _texts(row["member_order"], 2)
    _require(len(order) == 2, "Exactly two distinct original RNA members required")
    members = _array(row["members"], 2, exact=2)
    for member in members:
        item = _record(member, "id regions product chemistry", "Original RNA member")
        _text(item["id"], "Member id")
        regions = _record(item["regions"], "utr5 cds utr3 poly_a", "Complete region authority")
        _require(len({_text(value, "Region id") for value in regions.values()}) == 4,
                 "Complete region identities must be distinct")
        product = _record(item["product"], "identity sequence translation_policy provenance", "Complete product authority")
        PinnedIdentity.from_dict(product["identity"])
        sequence = _text(product["sequence"], "Complete protein sequence", 1_000_000)
        _require(set(sequence) <= set("ACDEFGHIKLMNPQRSTVWY"), "Protein must use canonical amino acids without stop")
        TranslationPolicy.from_dict(product["translation_policy"])
        DeclarationProvenance.from_dict(product["provenance"])
        MoleculeChemistry.from_dict(item["chemistry"])
    _require([cast(dict[str, JsonValue], item)["id"] for item in members] == order,
             "Member expectations must preserve full supplied order")
    return template


def _model(value: JsonValue) -> None:
    row = _record(value, "schema_version identity body", "Mechanism model")
    _require(row["schema_version"] == "biocompiler.policy_controlled_activity_model.v0.1", "Wrong model schema")
    pin = PinnedIdentity.from_dict(row["identity"])
    _require(pin.kind == "model", "Mechanism requires a model identity")
    body = _record(row["body"], "operation readout controller products components ports delays initial_activity clock assumptions", "Model body")
    for key in ("operation", "readout", "controller"):
        _definition(body[key])
    for item in _array(body["products"], 2, exact=2):
        _definition(item)
    _ref(body["clock"], "Clock")
    ActualActivityDelays.from_data(body["delays"])
    _require(body["initial_activity"] == "background" and bool(_texts(body["assumptions"])), "Explicit initial activity and assumptions required")
    for component in _array(body["components"], 2, exact=2):
        item = _record(component, "id member_id product_definition localization model", "Model component")
        _text(item["id"], "Component id"); _text(item["member_id"], "Member id")
        for key in ("product_definition", "localization", "model"):
            _definition(item[key])
    expected = (("antigen", "input", "physical_antigen", "encounter_generation", "Observation"),
                ("controller", "input", "physical_controller", "executor", "Observation"),
                ("component-a", "input", "component_available", "executor", "Parameter"),
                ("component-b", "input", "component_available", "executor", "Parameter"),
                ("activity", "output", "activity_band", "executor", "ControlledActivity"))
    for port, (id_, direction, signal, scope, kind) in zip(_array(body["ports"], 5, exact=5), expected, strict=True):
        item = _record(port, "id direction signal scope reference", "Model port")
        _require(tuple(item[key] for key in ("id", "direction", "signal", "scope")) == (id_, direction, signal, scope),
                 "Unsupported model interface meaning or order")
        _ref(item["reference"], kind)


def _domain(value: JsonValue) -> None:
    """Closed finite-domain representation only; no expansion or timing evaluator."""
    row = _record(value, "schema_version profile clock executor encounter inputs source_deadlines intervention_cutoff_tick horizon_tick suffix_policy initial physical_factors evidence_factors lifecycle_factors fixed_inputs limits", "Operating domain")
    _require(row["schema_version"] == "biocompiler.policy_controlled_composition_domain.v0.1" and row["profile"] == PROFILE,
             "Wrong controlled domain schema")
    clock = _record(row["clock"], "id resolution", "Domain clock")
    _text(clock["id"], "Clock"); from_data(clock["resolution"], m.Quantity)
    for key, fields in (("executor", "role identity"), ("encounter", "slot declaration subject")):
        for item in _record(row[key], fields, key).values():
            _text(item, key)
    keys = ("antigen", "controller", "rna_a", "rna_b", "protein_a", "protein_b")
    for index, input_ in enumerate(_array(row["inputs"], 6, exact=6)):
        item = _record(input_, "key reference scope freshness_ticks", "Domain input")
        _require(item["key"] == keys[index] and item["scope"] == ("encounter" if index == 0 else "executor"), "Wrong domain input census")
        _ref(item["reference"], ("Observation", "Observation", "MaterialMember", "MaterialMember", "Parameter", "Parameter")[index])
        _integer(item["freshness_ticks"], 64, 0)
    ActivityDeadlines.from_data(row["source_deadlines"])
    _integer(row["intervention_cutoff_tick"], 32, 0); _integer(row["horizon_tick"], 64)
    _require(row["suffix_policy"] == "hold_last_physical_inputs_no_encounter_events", "Wrong finite suffix policy")
    def frame(value: JsonValue) -> None:
        item = _record(value, "physical evidence", "Physical/evidence frame")
        physical = _record(item["physical"], " ".join(keys), "Physical factors")
        for key, state in physical.items():
            _require(state in (("disabled", "enabled") if key == "controller" else ("absent", "present")), "Invalid physical factor")
        evidence = _record(item["evidence"], " ".join(keys), "Evidence factors")
        for data in evidence.values():
            record = _record(data, "status observed_tick generation", "Evidence")
            _require(record["status"] in ("valid", "missing", "invalid", "conflicting"), "Invalid evidence status")
            for key in ("observed_tick", "generation"):
                if record[key] is not None:
                    _integer(record[key], 64, 0)
    frame(row["initial"])
    for factor in _array(row["physical_factors"], 6):
        item = _record(factor, "input ticks values", "Physical factor")
        _require(item["input"] in keys, "Unknown physical input"); _texts(item["values"], 2)
        for tick in _array(item["ticks"], 33): _integer(tick, 32, 0)
    for factor in _array(row["evidence_factors"], 6):
        item = _record(factor, "input ticks statuses age_ticks", "Evidence factor")
        _require(item["input"] in keys, "Unknown evidence input"); _texts(item["statuses"], 4)
        for key in ("ticks", "age_ticks"):
            for tick in _array(item[key], 65): _integer(tick, 64, 0)
    for factor in _array(row["lifecycle_factors"], 33):
        item = _record(factor, "ticks actions", "Lifecycle factor"); _texts(item["actions"], 3)
        for tick in _array(item["ticks"], 33): _integer(tick, 32, 0)
    for fixed in _array(row["fixed_inputs"], 65):
        item = _record(fixed, "tick event physical evidence", "Fixed domain input")
        _integer(item["tick"], 64, 0)
        _require(item["event"] in ("none", "start", "end", "reset"), "Invalid lifecycle event")
        frame({"physical": item["physical"], "evidence": item["evidence"]})
    limits = _record(row["limits"], "max_generations max_prefixes max_transitions max_histories max_work", "Domain limits")
    for key, maximum in (("max_generations", 16), ("max_prefixes", 1_000_000), ("max_transitions", 1_000_000),
                         ("max_histories", 65536), ("max_work", 16_000_000)):
        _integer(limits[key], maximum)


def _validate(value: JsonValue) -> dict[str, JsonValue]:
    _bounded_tree(value)
    row = _object(value, set(ROOT_FIELDS), "Complete original controlled request")
    _require(row["schema_version"] == REQUEST_SCHEMA and row["profile"] == PROFILE, "Wrong request schema/profile")
    SourceAuthoritySnapshot.from_data(row["source_authority"])
    _model(row["mechanism_model"]); _domain(row["operating_domain"]); _material(row["material_authority"])
    binding = _record(row["catalog_binding"], "entry model_identity component_ids", "Full catalog binding")
    from_data(binding["entry"], m.ImplementationBinding); PinnedIdentity.from_dict(binding["model_identity"])
    _require(len(_texts(binding["component_ids"], 2)) == 2, "Both model components required")
    assembly = _record(row["assembly"], "schema_version policy member_order product_bindings helper_members", "Assembly")
    _require(assembly["schema_version"] == "biocompiler.policy_controlled_composition_assembly.v0.1"
             and assembly["policy"] == "supplied_template_only" and assembly["helper_members"] == [], "Wrong assembly family")
    _require(len(_texts(assembly["member_order"], 2)) == 2, "Both members required")
    for product in _array(assembly["product_bindings"], 2, exact=2):
        item = _record(product, "product_parameter member_id cds_id product_definition product_identity", "Assembly product")
        ProductMemberBinding.from_data({key: value for key, value in item.items() if key != "product_identity"})
        PinnedIdentity.from_dict(item["product_identity"])
    context = _record(row["context"], "schema_version executor_identity slot deployment co_delivery localizations availability controller empirical_assertions", "Context")
    _require(context["schema_version"] == "biocompiler.policy_controlled_composition_context.v0.1", "Wrong context schema")
    _text(context["executor_identity"], "Executor identity"); _text(context["slot"], "Slot")
    from_data(context["deployment"], m.Deployment); ControllerBinding.from_data(context["controller"])
    delivery = _record(context["co_delivery"], "mode members assumptions", "Co-delivery")
    _require(delivery["mode"] == "same_recipient" and len(_texts(delivery["members"], 2)) == 2
             and bool(_texts(delivery["assumptions"])), "Explicit two-member co-delivery required")
    for localization in _array(context["localizations"], 2, exact=2):
        item = _record(localization, "member_id rna_compartment product_compartment definition", "Localization")
        _text(item["member_id"], "Member id"); _definition(item["definition"])
        _require(item["rna_compartment"] == "cytoplasm" and item["product_compartment"] == "cell_surface", "Unsupported localization")
    for availability in _array(context["availability"], 2, exact=2):
        item = _record(availability, "member_id rna product scope", "Availability")
        _text(item["member_id"], "Member id")
        _require(item["rna"] == item["product"] == "domain" and item["scope"] == "executor", "Availability remains an independent domain input")
    for assertion in _array(context["empirical_assertions"], 128):
        item = _record(assertion, "id claim status source_ids", "Empirical assertion")
        _text(item["id"], "Assertion id"); _text(item["claim"], "Claim", 4096); _texts(item["source_ids"])
        _require(item["status"] == "unassessed", "Preparation cannot assert empirical acceptance")
    resources = _record(row["resources"], "schema_version max_member_rna_nt max_total_rna_nt controller_records evidence_records timer_cells state_bits", "Resources")
    _require(resources["schema_version"] == RESOURCE_PROFILE, "Wrong resource schema")
    for key, maximum, minimum in (("max_member_rna_nt", 1_000_000, 1), ("max_total_rna_nt", 2_000_000, 1),
                                  ("controller_records", 1_000_000, 1), ("evidence_records", 1_000_000, 2),
                                  ("timer_cells", 1_000_000, 3), ("state_bits", 1_000_000, 4)):
        _integer(resources[key], maximum, minimum)
    ControlledBudgets.from_data(row["budgets"])
    return row


@dataclass(frozen=True, slots=True, init=False)
class ControlledCompositionRequest:
    """Complete supplied authority snapshot; preparing it grants no acceptance."""
    _json: bytes
    schema_version: ClassVar[str] = REQUEST_SCHEMA
    profile: ClassVar[str] = PROFILE

    @classmethod
    def from_request(cls, request: JsonValue) -> ControlledCompositionRequest:
        _validate(request)
        snapshot = encode_json(request)
        _require(len(snapshot) <= 4_000_000, "Original request byte ceiling exceeded")
        value = object.__new__(cls)
        object.__setattr__(value, "_json", snapshot)
        return value

    def to_request(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self._json))

    @property
    def source_authority(self) -> SourceAuthoritySnapshot:
        return SourceAuthoritySnapshot.from_data(self.to_request()["source_authority"])

    @property
    def template(self) -> PayloadTemplate:
        return _material(self.to_request()["material_authority"])

    @property
    def budgets(self) -> ControlledBudgets:
        return ControlledBudgets.from_data(self.to_request()["budgets"])

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self._json).hexdigest()

    @property
    def native_status(self) -> str:
        return "not_performed"

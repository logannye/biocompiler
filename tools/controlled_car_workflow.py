"""Prepare the controlled-CAR conditional workflow without executing native code.

The source is authored afresh from typed records. The finite scenario is a
software exercise, not fitted experimental kinetics or a measurement schedule.
Complete supplied material and original source pins remain native authority.
"""
from __future__ import annotations

import hashlib

from biocompiler.core_client import encode_json
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.policy import model as p
from biocompiler.policy.controlled_behavior import ControlledBehaviorRequest
from biocompiler.policy.controlled_composition import (
    PROFILE, ActivityDeadlines, ActivityReadout, ActualActivityDelays,
    ControlledCompositionContractDescription, ControllerBinding,
    ProductMemberBinding, SourceAuthoritySnapshot,
)
from biocompiler.policy.controlled_material import ControlledBudgets, ControlledCompositionRequest
from biocompiler.policy.controlled_workflow import ControlledWorkflowRequest
from biocompiler.policy.serialization import to_data

MEMBERS = ("car197", "car206")
PRODUCTS = ("WO2014127261A1.construct197", "WO2014127261A1.construct206")
PREFIX = "car.controlled197206"
CONTRACT_CANONICAL_SHA256 = "a03d8f272fd89530a52d6d7d7a403e777d5c842d133d215ced80265c1c1f8f35"
KEYS = ("antigen", "controller", "rna_a", "rna_b", "protein_a", "protein_b")
SCENARIO = {
    "clock_seconds_per_tick": 1, "horizon_tick": 10,
    "intervention_cutoff_tick": 6, "freshness_ticks": 1,
    "initial_activity": "background",
    "actual_delays": {"onset_ticks": 1, "cessation_ticks": 1, "reactivation_ticks": 1},
    "requested_deadlines": {"onset_ticks": 2, "controller_off_ticks": 2,
                           "antigen_off_ticks": 2, "component_off_ticks": 2,
                           "reactivation_ticks": 2},
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _hash(value):
    return hashlib.sha256(encode_json(value)).hexdigest()


def _ref(kind, identity):
    return p.Ref(identity, kind)


def _definition(identity, category, meaning, *, marker=None, result=None, parameters=()):
    clauses = () if marker is None else (p.ContractClause(
        "postcondition", meaning,
        p.Expr("literal", p.TEXT, value="biocompiler.controlled_source." + marker + ".v0.1")),)
    return p.SemanticDefinition(PREFIX + "." + identity, "1", category, meaning,
                                parameters=parameters, result=result, clauses=clauses)


def _domain(clock, deadlines):
    """Two software histories: unchanged or withdrawn controller at tick two."""
    def physical(present=True):
        return {key: ("enabled" if key == "controller" else "present" if present else "absent")
                for key in KEYS}

    def evidence(tick, *, missing=False):
        return {key: {"status": "missing" if missing else "valid",
                      "observed_tick": None if missing else tick,
                      "generation": 1 if key == "antigen" and not missing else None} for key in KEYS}

    initial = physical()
    initial.update(antigen="absent", controller="disabled")
    references = ((_ref("Observation", "antigen")), (_ref("Observation", "controller")),
                  _ref("MaterialMember", MEMBERS[0]), _ref("MaterialMember", MEMBERS[1]),
                  _ref("Parameter", "product-a"), _ref("Parameter", "product-b"))
    return {
        "schema_version": "biocompiler.policy_controlled_composition_domain.v0.1", "profile": PROFILE,
        "clock": {"id": clock.id, "resolution": to_data(clock.resolution)},
        "executor": {"role": "tcell", "identity": PREFIX + ".executor"},
        "encounter": {"slot": PREFIX + ".encounter", "declaration": "contact", "subject": "target"},
        "inputs": [{"key": key, "reference": to_data(ref),
                    "scope": "encounter" if i == 0 else "executor",
                    "freshness_ticks": 1}
                   for i, (key, ref) in enumerate(zip(KEYS, references, strict=True))],
        "source_deadlines": deadlines.to_data(), "intervention_cutoff_tick": 6,
        "horizon_tick": 10, "suffix_policy": "hold_last_physical_inputs_no_encounter_events",
        "initial": {"physical": initial, "evidence": evidence(None, missing=True)},
        "physical_factors": [{"input": "controller", "ticks": [2], "values": ["disabled"]}],
        "evidence_factors": [], "lifecycle_factors": [],
        "fixed_inputs": [{"tick": tick, "event": "start" if tick == 0 else "none",
                          "physical": physical(tick != 5), "evidence": evidence(tick)}
                         for tick in range(11) if tick != 2],
        "limits": {"max_generations": 4, "max_prefixes": 10000,
                   "max_transitions": 10000, "max_histories": 256, "max_work": 1000000},
    }


def prepare_workflow(*, material_authority: dict, source_records: list, contract: dict) -> ControlledWorkflowRequest:
    """Create an inert original for later hosted Core/Verify compilation.

The caller supplies complete material and freshly bound original source records.
This helper performs no I/O, source retrieval, biological inference or acceptance.
The current discrete scenario intentionally refuses automatic timing calibration.
"""
    _require(type(contract) is dict and contract.get("schema_version") == "biocompiler.controlled_car_reference_contract.v0.1"
             and contract.get("id") == "WO2014127261A1-197-206-rna-adaptation-control"
             and contract.get("version") == "2"
             and contract.get("reference_identity") == "WO2014127261A1-197-206"
             and contract.get("claim_scope") == "supplied_conditional_receptor_activity_model_only",
             "Unsupported original contract identity or claim scope")
    # The root importer additionally pins the literal file bytes. This canonical
    # pin closes the no-I/O helper itself: a changed controller, readout, context,
    # source record or empirical label cannot be silently reinterpreted here.
    _require(_hash(contract) == CONTRACT_CANONICAL_SHA256,
             "Original controller/readout contract changed; no empirical relabeling or implicit adaptation is supported")
    _require(type(contract.get("scenario")) is dict
             and encode_json(contract["scenario"]) == encode_json(SCENARIO),
             "Unsupported scenario: timing is the explicit uncalibrated software scenario")
    assumptions = contract.get("assumptions")
    _require(type(assumptions) is list and 1 <= len(assumptions) <= 128
             and all(type(item) is str and item.strip() for item in assumptions),
             "Explicit controller/readout assumptions are required")
    _require(type(material_authority) is dict and material_authority.get("member_order") == list(MEMBERS)
             and type(material_authority.get("members")) is list
             and len(material_authority["members"]) == 2, "Exactly the ordered car197/car206 material is required")
    material_members = material_authority["members"]
    product_pins = []
    for row, member, identity in zip(material_members, MEMBERS, PRODUCTS, strict=True):
        _require(row["id"] == member and row["product"]["identity"]["id"] == identity
                 and row["product"]["identity"]["version"] == "1", "Unexpected original product/member identity")
        product_pins.append(row["product"]["identity"])

    # Markers select the existing narrow native semantics. The meaningful text
    # preserves source facts, explicit assumptions and the limited readout scope.
    capability = _definition("capability", "capability",
        "Supplied human T-cell capability; actual delivery, expression and function remain unassessed.", marker="human_t_cell")
    encounter_def = _definition("encounter", "encounter",
        "Explicit encounter lifecycle for one target cell; no contact kinetics are inferred.", marker="encounter")
    antigen_def = _definition("antigen", "observation",
        "Assumed binary effective CD19 engagement at the target encounter; no density threshold or affinity model.",
        marker="antigen", result=p.TRUTH)
    controller_def = _definition("controller", "observation",
        "Assumed binary effective AP21967 controller availability in the executor. The source drug identity does not establish two-RNA exposure, dose response or clearance.",
        marker="controller", result=p.TRUTH)
    operation = _definition("activity", "operation",
        "Conditional reversible receptor/signaling activity gated by antigen, controller and both functional proteins; no expression or target-killing endpoint.", marker="activity")
    readout = _definition("readout", "observation",
        "Supplied abstract background/active receptor-signaling bands. Software evidence frames are not experimental samples, calibrated thresholds or cytotoxicity measurements.",
        marker="readout", result=p.TEXT)
    descriptors = tuple(_definition("product" + number, "model",
        "Exact complete tagged patent-derived product retained in the supplied nominal design; functional availability is assumed.",
        parameters=tuple(p.Parameter(key, p.TEXT, value=value) for key, value in (
            ("product_identity", pin["id"]), ("product_version", pin["version"]),
            ("product_sha256", pin["content_fingerprint"]))))
        for number, pin in zip(("197", "206"), product_pins, strict=True))
    chassis_def = _definition("chassis", "model", "Declared human CD8 T-cell recipient of lymphoid lineage. A mature expression/signaling-capable state is a supplied premise, not a measured phenotype; in-vivo applicability remains unassessed.")
    delivery_def = _definition("delivery", "delivery", "Both designed RNAs are assumed to reach the same human CD8 T-cell recipient and supply functional expression; no vehicle, dose or probability is specified.")
    localization = _definition("localization", "interface", "Both products are assumed available in functional membrane-associated form; trafficking and co-localization are unmeasured.")
    realization = _definition("mechanism", "model",
        "Uncalibrated deterministic one-tick onset, cessation and reactivation scenario; no quantitative expression, stoichiometry or drug washout prediction.")
    projection = contract["nominal_translation"]
    nominal_translation = p.SemanticDefinition(projection["definition_id"], projection["definition_version"],
        projection["category"], projection["meaning"])
    role = p.Role("tcell", (capability.ref,))
    target = p.Subject("target", "cell", "encounter", executor=p.declaration_ref(role), encounter=_ref("Encounter", "contact"))
    encounter = p.Encounter("contact", p.declaration_ref(role), p.declaration_ref(target), encounter_def.ref, "explicit_event")
    unit = p.Unit("second", "time", "duration")
    quantity = lambda ticks: p.Quantity(str(ticks), unit)
    clock = p.Clock("clock", "logical", quantity(1))
    observations = tuple(p.Observation(identity, p.declaration_ref(role), subject, p.TRUTH, definition.ref,
        p.declaration_ref(clock), "cell", "sampled", "atomic_frame", quantity(1))
        for identity, subject, definition in (("antigen", p.declaration_ref(target), antigen_def),
                                             ("controller", p.declaration_ref(role), controller_def)))
    products = tuple(p.Parameter("product-" + letter, p.TEXT, value=identity)
                     for letter, identity in zip(("a", "b"), PRODUCTS, strict=True))
    gate = p.Expr("all", p.TRUTH, args=tuple(p.Expr("observe", p.TRUTH, ref=p.declaration_ref(item), scope=item.subject)
                                           for item in observations))
    activity = p.ControlledActivity("activity", p.declaration_ref(role), p.declaration_ref(target),
        p.declaration_ref(clock), operation.ref, gate, tuple(p.declaration_ref(item) for item in products), readout.ref)
    requirement_rows = (("safety", "no_unauthorized_activation", None, None),
        ("onset", "initial_activation", "active", 2),
        ("controller-off", "controller_cessation", "background", 2),
        ("antigen-off", "antigen_cessation", "background", 2),
        ("component-off", "component_cessation", "background", 2),
        ("reactivation", "reactivation", "active", 2))
    requirements, obligation_defs = [], []
    for identity, marker, band, deadline in requirement_rows:
        definition = _definition("requirement." + identity, "requirement",
            "Require " + marker + " within the declared software domain; no measured therapeutic guarantee.", marker=marker)
        obligation_defs.append(definition)
        response = None if band is None else p.Expr("eq", p.TRUTH,
            args=(activity.band(), p.Expr("literal", p.TEXT, value=band)))
        requirements.append(p.Requirement(identity, "safety" if deadline is None else "progress",
            definition.meaning, p.Scope("executor", p.declaration_ref(role)), response=response,
            deadline=None if deadline is None else quantity(deadline), horizon=quantity(10),
            applies_to=(p.declaration_ref(activity),), contract=definition.ref, clock=p.declaration_ref(clock)))
    definitions = (capability, encounter_def, antigen_def, controller_def, operation, readout,
                   *obligation_defs, chassis_def, delivery_def, localization, realization, nominal_translation, *descriptors)
    declarations = (role, target, encounter, clock, *observations, *products, activity, *requirements)
    locations = {"tcell": (7, "/intended_target"), "target": (116, "/mechanism"),
        "contact": (116, "/mechanism/semantics"), "clock": (134, "/scenario"),
        "antigen": (116, "/mechanism/antigen_identity"), "controller": (72, "/controller"),
        "product-a": (5, "/reference_identity"), "product-b": (5, "/reference_identity"),
        "activity": (97, "/readout")}
    def source_span(item):
        line, pointer = locations.get(item.id, (134, "/scenario/requested_deadlines"))
        return p.SourceSpan(item.id, "data/car_controlled_reference/controller-readout-contract.json",
                            line, pattern="json:" + pointer)

    source_map = tuple(source_span(item) for item in declarations)
    program = p.PolicyProgram(PREFIX, p.SemanticBundle(PREFIX + ".definitions", "1", definitions),
        declarations, source_map=source_map, profile=p.CONTROLLED_COMPOSITION_SOURCE_PROFILE)
    chassis = p.ChassisProfile(PREFIX + ".human_cd8_tcell", "1", "T_cell", "CD8_T_cell",
        ("assumed_expression_and_signaling_capable",), ("assumed_mature_CD8_T_cell",),
        (capability.ref,), chassis_def.ref, (), ())
    deployment = p.Deployment(PREFIX + ".deployment", (p.RoleBinding(p.declaration_ref(role), chassis),), (),
        p.DeliveryContract(PREFIX + ".delivery", (p.declaration_ref(role),), delivery_def.ref,
            delivery_def.ref, delivery_def.ref, "same_recipient", delivery_def.ref),
        p.RNAConstraints(design_count=1, member_count=2, helper_count=0, orf_count=2, product_count=2))
    entry = p.ImplementationBinding(PREFIX + ".implementation", "1", operation.ref, realization.ref,
        (chassis.id,), ("RNA",), (localization.ref, nominal_translation.ref, *(item.ref for item in descriptors)), ())
    document = p.BuildRequest(program, deployment, p.ImplementationCatalogLock(PREFIX + ".catalog", "1", (entry,)),
        p.AssuranceRequest(tuple(item.id for item in requirements), "bounded", quantity(10)),
        profile=p.CONTROLLED_COMPOSITION_SOURCE_PROFILE)
    actual = ActualActivityDelays(**SCENARIO["actual_delays"])
    deadlines = ActivityDeadlines(**SCENARIO["requested_deadlines"])
    product_bindings = tuple(ProductMemberBinding(p.declaration_ref(parameter), member,
        material["regions"]["cds"], descriptor.ref) for parameter, member, material, descriptor in
        zip(products, MEMBERS, material_members, descriptors, strict=True))
    controller = ControllerBinding(controller_def.ref, p.declaration_ref(role))
    control = ControlledCompositionContractDescription(product_bindings, controller,
        ActivityReadout(p.declaration_ref(activity), readout.ref), actual, deadlines)
    context = {"project_id": PREFIX + ".nominal", "title": "Controlled CAR 197/206 nominal two-RNA reference",
        "sources": source_records, "assumptions": assumptions}
    source = SourceAuthoritySnapshot(document=document, control_contract=control, project_context=context)
    component_ids = [PREFIX + ".component197", PREFIX + ".component206"]
    ports = [("antigen", "input", "physical_antigen", "encounter_generation", p.declaration_ref(observations[0])),
             ("controller", "input", "physical_controller", "executor", p.declaration_ref(observations[1])),
             ("component-a", "input", "component_available", "executor", p.declaration_ref(products[0])),
             ("component-b", "input", "component_available", "executor", p.declaration_ref(products[1])),
             ("activity", "output", "activity_band", "executor", p.declaration_ref(activity))]
    model_body = {"operation": to_data(operation.ref), "readout": to_data(readout.ref),
        "controller": to_data(controller_def.ref), "products": [to_data(item.ref) for item in descriptors],
        "components": [{"id": identity, "member_id": member, "product_definition": to_data(descriptor.ref),
                        "localization": to_data(localization.ref), "model": to_data(realization.ref)}
                       for identity, member, descriptor in zip(component_ids, MEMBERS, descriptors, strict=True)],
        "ports": [{"id": identity, "direction": direction, "signal": signal, "scope": scope, "reference": to_data(ref)}
                  for identity, direction, signal, scope, ref in ports],
        "delays": actual.to_data(), "initial_activity": "background", "clock": to_data(p.declaration_ref(clock)),
        "assumptions": assumptions}
    model_pin = PinnedIdentity("model", PREFIX + ".deterministic_delay", "1", _hash(model_body)).to_dict()
    lengths = [len(row["molecule"]["sequence"]) for row in material_authority["template"]["sources"]]
    original = ControlledCompositionRequest.from_request({
        "schema_version": ControlledCompositionRequest.schema_version, "profile": PROFILE,
        "source_authority": source.to_data(),
        "mechanism_model": {"schema_version": "biocompiler.policy_controlled_activity_model.v0.1",
                            "identity": model_pin, "body": model_body},
        "operating_domain": _domain(clock, deadlines), "material_authority": material_authority,
        "catalog_binding": {"entry": to_data(entry), "model_identity": model_pin, "component_ids": component_ids},
        "assembly": {"schema_version": "biocompiler.policy_controlled_composition_assembly.v0.1",
            "policy": "supplied_template_only", "member_order": list(MEMBERS), "helper_members": [],
            "product_bindings": [dict(binding.to_data(), product_identity=pin)
                                 for binding, pin in zip(product_bindings, product_pins, strict=True)]},
        "context": {"schema_version": "biocompiler.policy_controlled_composition_context.v0.1",
            "executor_identity": PREFIX + ".executor", "slot": PREFIX + ".encounter",
            "deployment": to_data(deployment), "controller": controller.to_data(),
            "co_delivery": {"mode": "same_recipient", "members": list(MEMBERS), "assumptions": assumptions},
            "localizations": [{"member_id": member, "rna_compartment": "cytoplasm",
                               "product_compartment": "cell_surface", "definition": to_data(localization.ref)} for member in MEMBERS],
            "availability": [{"member_id": member, "rna": "domain", "product": "domain", "scope": "executor"} for member in MEMBERS],
            "empirical_assertions": [{"id": PREFIX + ".behavior_applicability",
                "claim": "The nominal two-RNA design realizes the supplied controller, availability and activity contract in the intended human recipient.",
                "status": "unassessed", "source_ids": [row["id"] for row in source_records]}]},
        "resources": {"schema_version": "biocompiler.policy_controlled_composition_resources.v0.1",
            "max_member_rna_nt": max(lengths), "max_total_rna_nt": sum(lengths),
            "controller_records": 1, "evidence_records": 7, "timer_cells": 3, "state_bits": 4},
        "budgets": ControlledBudgets().to_data(),
    })
    readout_evidence = {"freshness_ticks": 1, "samples": [
        {"tick": tick, "status": "valid", "observed_tick": tick} for tick in range(11)]}
    return ControlledWorkflowRequest.from_behavior(ControlledBehaviorRequest.from_original(
        original, readout_evidence=readout_evidence))

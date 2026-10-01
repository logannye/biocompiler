"""Freeze Python-authoritative request records for hosted OCaml conformance.

All new examples are artificial declarations. Import/correspondence success is
not biological evidence, reference execution, molecular construction or export
acceptance. The caller selects the Python package; no native program is run.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys

import biocompiler as bc
from biocompiler.compiler.behavior import lower_to_behavior, verify_lowering
from biocompiler.compiler.request import BuildRequest
from biocompiler.ir.behavior import BehaviorProgram, BEHAVIOR_V2, SCHEMA_VERSION as BEHAVIOR_V1
from biocompiler.ir.circuit_intent import CircuitRequest, CircuitRequirement
from biocompiler.ir.circuit_profile import (
    CircuitProfileRequest, HumanExperimentContext, ImmuneRecipientIdentity,
)
from biocompiler.ir.intent import IntentProgram, SourceLocation
from biocompiler.ir.serialization import fingerprint


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/request-domains-v1.json"
SCHEMA = "biocompiler.request_domains_conformance.v1"
PARSERS = {"recipient": ImmuneRecipientIdentity, "experiment": HumanExperimentContext,
           "profile": CircuitProfileRequest, "requirement": CircuitRequirement,
           "circuit_request": CircuitRequest}
WRAPPER_SCHEMAS = sorted("biocompiler." + name + "_request.v0.1" for name in
                  ("human_behavior", "human_deployment", "human_acceptance"))


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def read_case_b(variant):
    path = ROOT / "tests/conformance/case-b" / variant / "request.json"
    return CircuitRequest.from_dict(json.loads(path.read_bytes())["circuit"])


def observation(identity, *, quantity=bc.QuantityKind.MIRNA_ACTIVITY,
                scope=bc.ObservationScope.CELL_ACCESSIBLE, numeric=False):
    encoding = (bc.ObservationEncoding("numeric", "artificial_unit",
                    bc.NumericInterval(-0.0, 1, True, False),
                    bc.NumericInterval(1.0, 2.0), bc.NumericInterval(0, 3))
                if numeric else bc.ObservationEncoding("qualitative", "qualitative"))
    return bc.CircuitObservation(identity,
        bc.ObservationEntity("software_fixture", identity, "unknown", "unknown"),
        quantity, "cytoplasm", scope,
        bc.ObservationWindow("unknown", None, None, "unknown", "unknown"), encoding)


def experiment(**changes):
    values = dict(system="human_cell_line", immune_classification="nonimmune",
                  cell_identity="artificial_human_context", cell_state="unestablished",
                  compartment="cytoplasm", delivery_mode="rna_delivery",
                  sources=(bc.PinnedIdentity("source", "z_artificial_context", "1", "a" * 64),
                           bc.PinnedIdentity("evidence", "a_artificial_declaration", "1", "b" * 64)),
                  locator="fixture:request-domains", assay_conditions=("No empirical data.", "Artificial declarations only."))
    values.update(changes)
    return HumanExperimentContext(**values)


PRODUCTS = (("protein_expression", bc.QuantityKind.TRANSLATION_RATE, "production_control"),
            ("rna_product", bc.QuantityKind.RNA_ABUNDANCE, "production_control"),
            ("mature_protein_quantity", bc.QuantityKind.PROTEIN_ABUNDANCE, "abundance_control"),
            ("biological_activity", bc.QuantityKind.DOWNSTREAM_ACTIVITY, "activity_control"),
            ("reporter_fluorescence", bc.QuantityKind.FLUORESCENCE, "readout"))


def boolean_requirement(*, product_index=4, numeric=False, input_count=2):
    kind, quantity, mode = PRODUCTS[product_index]
    inputs = tuple(observation(chr(65 + i), numeric=numeric) for i in range(input_count))
    signals = tuple(bc.CircuitSignal(item.id, item.fingerprint) for item in inputs)
    # Deliberately asymmetric table: first listed input is the most significant
    # row bit; unused inputs remain independently bound nominal observations.
    response = bc.BooleanSpec(signals, tuple(bool(row & (1 << (input_count - 1)))
                                           for row in range(1 << input_count)))
    output = bc.CircuitProduct("artificial_output", bc.ProductKind(kind),
        observation("Output", quantity=quantity, scope=bc.ObservationScope.EVALUATOR, numeric=numeric))
    providers = tuple(bc.CircuitProviderRequirement("provider_" + str(i),
        bc.ObservationEntity("software_fixture", "provider_" + str(i), "1", "unknown"),
        provider, "cytoplasm", "artificial_colocation", availability)
        for i, (provider, availability) in enumerate((("host", "unestablished"),
                   ("co_delivered", "declared"), ("external_input", "unestablished"))))
    behavior = bc.CircuitBehavior(inputs, response, output, bc.CircuitLifecycle(mode), providers)
    refs = tuple("source_" + item.id for item in inputs)
    bindings = tuple(bc.CircuitInputBinding(item.id, ref) for item, ref in zip(inputs, refs))
    return CircuitRequirement("artificial_requirement", behavior, None, refs,
                              SourceLocation("fixtures/request_domains.py", 7, "literal"), bindings)


def reference_request(requirement, *, form="delivered_rna"):
    requirement = replace(requirement, role_id=None, source_node_ids=(), input_bindings=())
    profile = CircuitProfileRequest("human_reference", "exact_reproduction",
        bc.PayloadFormat.DNA if form in {"delivered_dna", "dna_expression_template"} else bc.PayloadFormat.RNA,
        "import", source_experiment=experiment())
    realization = bc.PinnedIdentity("reference", "artificial_reference", "1", requirement.behavior.fingerprint)
    lock = bc.CircuitReferenceLock((bc.CircuitBehaviorExpectation(requirement.id, requirement.behavior),),
        realization, profile.source_experiment.sources, profile.source_experiment, form, "source_nominal")
    return CircuitRequest(profile, (requirement,), form, "source_nominal", None, realization, lock)


def relocated_sources(value):
    """Relocate diagnostic paths before re-importing enclosing source authority."""
    if isinstance(value, list):
        return [relocated_sources(item) for item in value]
    if isinstance(value, dict):
        result = {key: relocated_sources(item) for key, item in value.items()}
        if set(result) == {"file", "line", "function"} and isinstance(result["file"], str):
            path = Path(result["file"])
            if path.is_absolute():
                result["file"] = path.resolve().relative_to(ROOT).as_posix()
        return result
    return value


def wrapper_profiles():
    # Existing source examples supply complete valid wrapper authority. The
    # examples path never selects src/ or replaces the caller's Python package.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from examples.human_acceptance import make_human_acceptance
    acceptance = make_human_acceptance()
    for source in (acceptance.behavior_request, acceptance.deployment_request, acceptance):
        restored = type(source).from_dict(relocated_sources(source.to_dict()))
        require(restored.fingerprint == source.fingerprint, "Source relocation changed wrapper semantic identity")
        recipient = ImmuneRecipientIdentity(bc.ImmuneLineage.T_CELL, restored.target.fingerprint,
                                           restored.target.human_target.cell_subtype.fingerprint)
        yield CircuitProfileRequest("human_immune_payload", "candidate_design", bc.PayloadFormat.RNA,
                                    "planning", restored.target, recipient, source_request=restored)


def domain_cases():
    cases, rejections = [], []

    def add(identity, kind, value):
        raw = value.to_dict() if hasattr(value, "to_dict") else deepcopy(value)
        normalized = PARSERS[kind].from_dict(raw)
        cases.append(dict(id=identity, record_kind=kind, input=raw,
                          normalized=normalized.to_dict(), fingerprint=normalized.fingerprint))
        return normalized

    def reject(identity, kind, value, change=None, *, code="invalid_circuit_record"):
        raw = value.to_dict() if hasattr(value, "to_dict") else deepcopy(value)
        if change is not None:
            change(raw)
        try:
            PARSERS[kind].from_dict(raw)
        except (bc.SerializationError, ValueError, TypeError) as error:
            message = str(error)
        else:
            raise AssertionError("Python accepted intended invalid fixture " + identity)
        rejections.append(dict(id=identity, record_kind=kind, input=raw,
                               expected_outcome="invalid", expected_code=code,
                               python_error=message))

    bases = {variant: read_case_b(variant) for variant in ("base", "parameter-default", "parameter-override")}
    base = bases["base"]
    for variant, circuit in bases.items():
        add("case_b_" + variant, "circuit_request", circuit)
    for lineage in bc.ImmuneLineage:
        add("recipient_" + lineage.value, "recipient", replace(base.profile.recipient, lineage=lineage))
    for boundary in ("import", "planning", "selection", "verification", "export"):
        add("profile_" + boundary, "profile", replace(base.profile, boundary=boundary))
    for index, delivery in enumerate(("dna_delivery", "rna_delivery", "dna_and_rna_delivery", "stable_dna_expression", "not_reported")):
        immune = index % 2 == 1
        item = experiment(system=("human_cell_line", "primary_human_cells", "human_in_vivo")[index % 3],
            delivery_mode=delivery, immune_classification="immune" if immune else "nonimmune",
            immune_lineage=bc.ImmuneLineage.NK_CELL if immune else None)
        raw = item.to_dict()
        raw["sources"].reverse()
        add("experiment_" + delivery, "experiment", raw)
    add("executable_requirement", "requirement", base.requirements[0])
    object_actions = base.requirements[0].to_dict()
    object_actions["behavior"]["action_ids"] = dict.fromkeys(object_actions["behavior"]["action_ids"])
    add("executable_action_object_keys", "requirement", object_actions)
    for index, (kind, _, _) in enumerate(PRODUCTS):
        add("requirement_" + kind, "requirement", boolean_requirement(product_index=index))
    numeric = boolean_requirement(numeric=True)
    add("numeric_requirement", "requirement", numeric)
    unicode_boundary = boolean_requirement().to_dict()
    unicode_boundary["behavior"]["output"]["observation"]["entity"]["accession"] = "\U0001f52c" * 128
    add("observation_unicode_512_byte_boundary", "requirement", unicode_boundary)
    for aggregation, start, end, unit in (("instant", -0.0, 0, "s"), ("mean", 0, 1.0, "ms"),
            ("integral", 0, 1, "min"), ("any", 1.0, 2.0, "h"), ("all", 0, 1, "d")):
        raw = numeric.to_dict()
        raw["behavior"]["output"]["observation"]["window"] = bc.ObservationWindow(
            "artificial_reference", start, end, unit, aggregation).to_dict()
        # Output timing has no Boolean-input binding to update.
        raw["behavior"]["lifecycle"]["onset"] = bc.ObservationWindow("artificial_reference", 0, 1, "s", "any").to_dict()
        raw["behavior"]["lifecycle"]["cessation"] = bc.ObservationWindow("artificial_reference", 1, 2, "s", "all").to_dict()
        raw["behavior"]["lifecycle"]["clearance"] = bc.ObservationWindow("artificial_reference", 2, 3, "s", "mean").to_dict()
        add("window_" + aggregation, "requirement", raw)
    unordered = boolean_requirement().to_dict()
    unordered["behavior"]["inputs"].reverse()
    unordered["behavior"]["dependencies"].reverse()
    unordered["source_node_ids"].reverse()
    unordered["input_bindings"].reverse()
    unordered["behavior"]["response"]["inputs"].reverse()
    unordered["behavior"]["response"]["outputs"] = [False, True, False, True]
    add("boolean_input_permutation", "requirement", unordered)
    add("boolean_eight_inputs", "requirement", boolean_requirement(input_count=8))
    for form in ("delivered_dna", "dna_expression_template", "primary_rna", "delivered_rna", "processed_rna", "circular_rna"):
        add("reference_" + form, "circuit_request", reference_request(boolean_requirement(), form=form))

    specimens = {"recipient": base.profile.recipient, "experiment": experiment(),
                 "profile": base.profile, "requirement": boolean_requirement(), "circuit_request": base}
    for kind, specimen in specimens.items():
        reject(kind + "_unknown_field", kind, specimen, lambda d: d.update(extra=True), code="unknown_field")
        reject(kind + "_missing_schema", kind, specimen, lambda d: d.pop("schema_version"), code="missing_field")
        reject(kind + "_wrong_schema", kind, specimen, lambda d: d.update(schema_version="unknown.v99"), code="unsupported_schema")
    reject("profile_text_resource_limit", "recipient", base.profile.recipient,
           lambda d: d.update(oversized="x" * 16_385), code="profile_resource_limit")
    reject("observation_text_resource_limit", "requirement", boolean_requirement(),
           lambda d: d["behavior"]["output"]["observation"]["entity"].update(accession="\u754c" * 171),
           code="observation_resource_limit")
    reject("boolean_text_resource_limit", "requirement", boolean_requirement(),
           lambda d: d["behavior"]["response"]["inputs"][0].update(id="x" * 257),
           code="boolean_resource_limit")
    for field, value in (("eligibility_basis", "validated"), ("empirical_support", "pass"), ("lineage", "hepatocyte")):
        reject("recipient_" + field, "recipient", base.profile.recipient, lambda d, k=field, v=value: d.update({k: v}))
    for field in ("target_fingerprint", "cell_subtype_claim_fingerprint"):
        reject("profile_stale_" + field, "profile", base.profile,
               lambda d, k=field: d["recipient"].update({k: "0" * 64}))
    reject("profile_target_modality", "profile", base.profile, lambda d: d.update(molecular_form="DNA"))
    reject("profile_changed_source_target", "profile", base.profile,
           lambda d: d["source_request"]["target"]["compartments"].append("extracellular"))
    for value in (True, 9606.0, 10090):
        reject("experiment_taxon_" + repr(value), "experiment", experiment(), lambda d, v=value: d.update(recipient_taxon_id=v),
               code="invalid_type" if type(value) is not int else "invalid_circuit_record")
    reject("experiment_missing_immune_lineage", "experiment", experiment(), lambda d: d.update(immune_classification="immune"), code="invalid_type")
    reject("experiment_duplicate_source", "experiment", experiment(), lambda d: d["sources"].append(deepcopy(d["sources"][0])))
    reject("experiment_duplicate_condition", "experiment", experiment(), lambda d: d["assay_conditions"].append(d["assay_conditions"][0]))
    reject("experiment_abstract_compartment", "experiment", experiment(), lambda d: d.update(compartment="abstract"))
    standard = boolean_requirement()
    reject("requirement_duplicate_source", "requirement", standard, lambda d: d["source_node_ids"].append(d["source_node_ids"][0]))
    reject("requirement_dangling_binding", "requirement", standard, lambda d: d["input_bindings"][0].update(source_node_id="missing"))
    reject("requirement_unknown_observation", "requirement", standard, lambda d: d["input_bindings"][0].update(observation_id="missing"))
    reject("requirement_duplicate_binding", "requirement", standard, lambda d: d["input_bindings"].append(deepcopy(d["input_bindings"][0])))
    reject("requirement_duplicate_provider", "requirement", standard, lambda d: d["behavior"]["dependencies"].append(deepcopy(d["behavior"]["dependencies"][0])))
    reject("requirement_noncellular_input", "requirement", standard, lambda d: d["behavior"]["inputs"][0].update(scope="evaluator"))
    reject("requirement_stale_observation_pin", "requirement", standard, lambda d: d["behavior"]["response"]["inputs"][0].update(observation_fingerprint="0" * 64))
    reject("requirement_product_lifecycle", "requirement", standard, lambda d: d["behavior"]["lifecycle"].update(mode="production_control"))
    reject("requirement_product_quantity", "requirement", standard, lambda d: d["behavior"]["output"]["observation"].update(quantity="rna_abundance"))
    reject("requirement_boolean_nonboolean", "requirement", standard, lambda d: d["behavior"]["response"]["outputs"].__setitem__(0, 0), code="invalid_type")
    reject("requirement_boolean_rows", "requirement", standard, lambda d: d["behavior"]["response"]["outputs"].pop())
    reject("numeric_overlapping_regions", "requirement", numeric, lambda d: d["behavior"]["output"]["observation"]["encoding"]["low"].update(upper_inclusive=True))
    reject("numeric_empty_interval", "requirement", numeric, lambda d: d["behavior"]["output"]["observation"]["encoding"]["low"].update(lower=1))
    reject("numeric_range_excludes_high", "requirement", numeric, lambda d: d["behavior"]["output"]["observation"]["encoding"]["allowed_range"].update(upper=1))
    reject("numeric_boolean_bound", "requirement", numeric, lambda d: d["behavior"]["output"]["observation"]["encoding"]["high"].update(upper=True), code="invalid_type")
    reject("unknown_window_partial", "requirement", standard, lambda d: d["behavior"]["output"]["observation"]["window"].update(start=0))
    executable = base.requirements[0]
    reject("executable_missing_action", "requirement", executable, lambda d: d["behavior"].update(action_ids=["missing"]))
    reject("executable_duplicate_action", "requirement", executable, lambda d: d["behavior"]["action_ids"].append(d["behavior"]["action_ids"][0]))
    for field, value in (("deployment_id", None), ("requested_form", "delivered_dna"), ("requirements", [])):
        reject("circuit_" + field, "circuit_request", base, lambda d, k=field, v=value: d.update({k: v}),
               code="invalid_type" if field == "deployment_id" else "invalid_circuit_record")
    reject("circuit_missing_role", "circuit_request", base, lambda d: d["requirements"][0].update(role_id="missing"))
    reject("circuit_source_unknown", "circuit_request", base, lambda d: d["requirements"][0]["source_node_ids"].append("missing"))
    reject("circuit_duplicate_requirement", "circuit_request", base, lambda d: d["requirements"].append(deepcopy(d["requirements"][0])))
    reject("circuit_output_compartment", "circuit_request", base, lambda d: d["requirements"][0]["behavior"]["output"]["observation"].update(compartment="undeclared"))
    reference = reference_request(standard)
    reject("reference_missing_lock", "circuit_request", reference, lambda d: d.update(reference_lock=None))
    reject("reference_changed_realization", "circuit_request", reference, lambda d: d["selected_realization"].update(content_fingerprint="0" * 64))
    reject("reference_invented_deployment", "circuit_request", reference, lambda d: d.update(deployment_id="invented"))
    reject("reference_missing_expected_behavior", "circuit_request", reference, lambda d: d["reference_lock"]["expected_behaviors"][0].update(requirement_id="other"))
    reject("reference_changed_boolean", "circuit_request", reference, lambda d: d["requirements"][0]["behavior"]["response"].update(outputs=[False, False, False, True]))
    for profile in wrapper_profiles():
        source_schema = profile.source_request.schema_version
        add("wrapped_" + source_schema, "profile", profile)
    return cases, rejections


def coverage_for(cases, rejections):
    return {"supported_record_kinds": sorted(PARSERS),
            "covered_record_kinds": sorted({case["record_kind"] for case in cases}),
            "wrapped_source_schemas": WRAPPER_SCHEMAS,
            "variants": {"positive_cases": len(cases), "invalid_cases": sum(r["expected_outcome"] == "invalid" for r in rejections),
                         "unsupported_cases": sum(r["expected_outcome"] == "unsupported" for r in rejections),
                         "immune_lineages": sorted(item.value for item in bc.ImmuneLineage),
                         "product_lifecycle_pairs": [list(row) for row in PRODUCTS]}}


def load_behavior_examples():
    specification = importlib.util.spec_from_file_location("request_domains_behavior_examples",
                                                           ROOT / "tools/freeze_behavior_domains.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def lowering_cases():
    examples = load_behavior_examples()
    cases, rejected = [], []

    def pair(identity, request, behavior):
        # Re-import independently before recording expected bytes; candidate
        # construction is never used by the hosted native checker.
        request = BuildRequest.from_dict(request.to_dict())
        behavior = BehaviorProgram.from_dict(behavior.to_dict())
        return dict(id=identity, request=request.to_dict(), behavior=behavior.to_dict(),
                    request_fingerprint=request.fingerprint,
                    request_artifact_fingerprint=request.artifact_fingerprint,
                    behavior_fingerprint=behavior.fingerprint,
                    behavior_artifact_fingerprint=fingerprint(behavior.to_dict()))

    def add(identity, request, behavior=None):
        behavior = lower_to_behavior(request) if behavior is None else behavior
        require(verify_lowering(request, behavior).passed, "Invalid positive lowering " + identity)
        cases.append(pair(identity, request, behavior))
        return request, behavior

    def reject(identity, request, behavior, code, *, outcome="invalid"):
        try:
            verify_lowering(request, behavior)
        except (bc.LoweringVerificationError, bc.UnsupportedBehaviorError, bc.SerializationError) as error:
            detail = str(error)
        else:
            raise AssertionError("Python accepted intended lowering rejection " + identity)
        if code.startswith("lowering_"):
            expected = code.removeprefix("lowering_")
            if expected == "source_location":
                expected = "source"
            require(detail.startswith(expected + ":"),
                    f"Lowering rejection {identity} reached {detail!r}, expected {code}")
        item = pair(identity, request, behavior)
        item.update(expected_outcome=outcome, expected_code=code, python_error=detail)
        rejected.append(item)

    def frozen(therapy, profile, step=None):
        intent = IntentProgram.from_dict(therapy.freeze().to_dict(include_source=False))
        constraints = {} if step is None else {"execution": {"integral_step": bc.Duration(step).to_dict()}}
        return BuildRequest.freeze(intent, behavior_profile=profile, implementation_constraints=constraints)

    retained = json.loads((ROOT / "tests/conformance/behavior-domains-v1.json").read_bytes())
    old_fingerprints = {case["id"]: case["fingerprint"] for case in retained["cases"]}
    broad = {}
    for label, builder in (("algebra", examples.algebra), ("temporal_memory", examples.temporal_memory),
                           ("actions_state_signature", examples.actions_state_signature)):
        for suffix, profile in (("v1", BEHAVIOR_V1), ("v2", BEHAVIOR_V2)):
            identity = label + "_" + suffix
            request, behavior = add(identity, frozen(builder(), profile))
            require(behavior.fingerprint == old_fingerprints[identity], "Broad Behavior identity changed: " + identity)
            broad[identity] = (request, behavior)
    identity = "sampled_multirole_v2"
    request, behavior = add(identity, frozen(examples.sampled_multirole(), BEHAVIOR_V2, step=1))
    require(behavior.fingerprint == old_fingerprints[identity], "Sampled Behavior identity changed")
    broad[identity] = (request, behavior)
    for variant in ("base", "parameter-default", "parameter-override"):
        circuit = read_case_b(variant)
        add("case_b_" + variant, circuit.profile.source_request)

    base_request, base_behavior = broad["algebra_v1"]
    annotated = replace(base_request.intent, nodes=tuple(replace(node,
        source=SourceLocation("fixtures/request_domains.py", index + 1, "source_correspondence"))
        for index, node in enumerate(base_request.intent.nodes)))
    located_request, located_behavior = add("explicit_source_locations", BuildRequest.freeze(annotated))
    require(located_behavior.fingerprint == base_behavior.fingerprint,
            "Diagnostic source coordinates changed Behavior semantic identity")
    rename = {node.id: "alpha_" + str(index) for index, node in enumerate(base_request.intent.nodes)}

    def renamed(value):
        if isinstance(value, dict):
            return {key: renamed(item) for key, item in value.items()}
        if isinstance(value, list):
            return [renamed(item) for item in value]
        return rename.get(value, value) if isinstance(value, str) else value

    alpha = IntentProgram.from_dict(renamed(base_request.intent.to_dict()))
    add("coordinated_alpha_rename", BuildRequest.freeze(alpha))
    sampled_request, sampled_behavior = broad["sampled_multirole_v2"]
    policy = sampled_behavior.to_dict()
    policy["policies"]["integral_step"] = bc.Duration(1.0).to_dict()
    add("numeric_policy_equality", sampled_request, BehaviorProgram.from_dict(policy))
    # Full source constraints/preferences survive successful correspondence;
    # this pass does not claim they have been implemented or empirically met.
    retained_obligations = BuildRequest.freeze(base_request.intent,
        implementation_constraints={"artificial_unresolved_constraint": True},
        preferences={"artificial_preference": 1})
    add("retained_uninterpreted_obligations", retained_obligations)

    foreign_profile = lower_to_behavior(BuildRequest.freeze(base_request.intent, behavior_profile=BEHAVIOR_V2))
    reject("different_execution_profile", base_request, foreign_profile, "lowering_execution_profile")
    changed = base_behavior.to_dict()
    changed["name"] = "foreign_program_name"
    reject("changed_program_name", base_request, BehaviorProgram.from_dict(changed), "lowering_source_identity")
    changed = base_behavior.to_dict()
    changed["nodes"].reverse()
    # Program node order is authority; the derived requirement inventory follows
    # the new order and is internally valid before the correspondence check.
    changed["requirements"].reverse()
    for node in changed["nodes"]:
        node["requirement_ids"].reverse()
    reject("reordered_graph", base_request, BehaviorProgram.from_dict(changed), "lowering_complete_graph")
    changed = base_behavior.to_dict()
    changed["roots"].reverse()
    reject("reordered_roots", base_request, BehaviorProgram.from_dict(changed), "lowering_complete_graph")

    # Every following candidate is a valid Behavior model of an independently
    # edited source. Keep the original source claim so exact correspondence,
    # rather than a trivial stale hash check, must expose the changed meaning.
    def edited_candidate(request, edit):
        raw = request.intent.to_dict()
        edit(raw)
        altered = IntentProgram.from_dict(raw)
        candidate = lower_to_behavior(BuildRequest.freeze(altered, behavior_profile=request.behavior_profile,
                                    implementation_constraints=dict(request.implementation_constraints)))
        data = candidate.to_dict()
        data["source_fingerprint"] = request.intent.fingerprint
        return BehaviorProgram.from_dict(data)

    def first_node(data, kind):
        return next(node for node in data["nodes"] if node["kind"] == kind)

    changed = edited_candidate(base_request, lambda d: first_node(d, "and").update(kind="or"))
    reject("same_arity_changed_operator", base_request, changed, "lowering_operation")
    changed = edited_candidate(base_request, lambda d: first_node(d, "and")["inputs"].reverse())
    reject("reordered_input_edge", base_request, changed, "lowering_operation")
    changed = edited_candidate(base_request, lambda d: first_node(d, "literal")["attributes"].update(value=bc.Level(9).to_dict()))
    reject("changed_literal", base_request, changed, "lowering_semantics")
    forged_request = BuildRequest.freeze(base_request.intent, parameters={"gain": 3})
    reject("coherently_forged_parameter_binding", base_request, lower_to_behavior(forged_request), "lowering_authoritative_bindings")
    moved = replace(located_request.intent, nodes=tuple(replace(node,
        source=replace(node.source, file="fixtures/other_location.py")) for node in located_request.intent.nodes))
    moved_behavior = lower_to_behavior(BuildRequest.freeze(moved))
    require(moved_behavior.fingerprint == located_behavior.fingerprint, "Source-only mutation unexpectedly changed semantic hash")
    reject("changed_diagnostic_source_only", located_request, moved_behavior, "lowering_source_location")

    for identity, kind, fields, code in (
        ("unknown_source_operation", "add", {"kind": "artificial.unknown"}, "unsupported_lowering_operation"),
        ("unknown_source_rule_policy", "rule", {"attributes": {"trigger": "condition", "execution": "sequential", "priority": "unspecified"}}, "unsupported_lowering_rule_policy"),
    ):
        raw = base_request.intent.to_dict()
        first_node(raw, kind).update(fields)
        source = BuildRequest.freeze(IntentProgram.from_dict(raw))
        reject(identity, source, base_behavior, code, outcome="unsupported")
    state_request, state_behavior = broad["actions_state_signature_v1"]
    raw = state_request.intent.to_dict()
    first_node(raw, "state")["attributes"]["arbitration"] = "first_writer"
    reject("unknown_source_state_policy", BuildRequest.freeze(IntentProgram.from_dict(raw)), state_behavior,
           "unsupported_lowering_state_policy", outcome="unsupported")
    sampled_request, sampled_behavior = broad["sampled_multirole_v2"]
    reject("missing_integral_step", BuildRequest.freeze(sampled_request.intent, behavior_profile=BEHAVIOR_V2),
           sampled_behavior, "unsupported_lowering_integral_step", outcome="unsupported")
    malformed_policy = BuildRequest.freeze(sampled_request.intent, behavior_profile=BEHAVIOR_V2,
                                           implementation_constraints={"execution": {"unknown": True}})
    reject("unknown_execution_policy", malformed_policy, sampled_behavior, "invalid_lowering_execution_policy")
    return cases, rejected


def build_corpus():
    cases, rejections = domain_cases()
    pairs, pair_rejections = lowering_cases()
    return {"schema_version": SCHEMA,
            "claim_scope": "Artificial structural request and source-correspondence conformance only; no reference execution, molecular realization, biological validation, admission or export acceptance.",
            "cases": cases, "rejections": rejections, "coverage": coverage_for(cases, rejections),
            "lowering_cases": pairs, "lowering_rejections": pair_rejections}


def check_corpus(document):
    require(document["schema_version"] == SCHEMA, "Unknown request conformance schema")
    for collection in ("cases", "rejections", "lowering_cases", "lowering_rejections"):
        ids = [case["id"] for case in document[collection]]
        require(len(set(ids)) == len(ids), "Duplicate fixture identities in " + collection)
    for case in document["cases"]:
        restored = PARSERS[case["record_kind"]].from_dict(case["input"])
        require(encoded(restored.to_dict()) == encoded(case["normalized"]), "Wrong normalized request " + case["id"])
        require(restored.fingerprint == case["fingerprint"], "Wrong request fingerprint " + case["id"])
    for case in document["rejections"]:
        if case["expected_outcome"] == "unsupported":
            restored = PARSERS[case["record_kind"]].from_dict(case["input"])
            require(restored.source_request.schema_version in WRAPPER_SCHEMAS, "Unsupported case is not a valid deferred wrapper")
        else:
            try:
                PARSERS[case["record_kind"]].from_dict(case["input"])
            except (bc.SerializationError, ValueError, TypeError):
                pass
            else:
                raise AssertionError("Python accepted intended rejection " + case["id"])
    require(document["coverage"] == coverage_for(document["cases"], document["rejections"]), "Request coverage manifest drifted")
    for collection in ("lowering_cases", "lowering_rejections"):
        for case in document[collection]:
            request = BuildRequest.from_dict(case["request"])
            behavior = BehaviorProgram.from_dict(case["behavior"])
            for actual, key in ((request.fingerprint, "request_fingerprint"),
                                (request.artifact_fingerprint, "request_artifact_fingerprint"),
                                (behavior.fingerprint, "behavior_fingerprint"),
                                (fingerprint(behavior.to_dict()), "behavior_artifact_fingerprint")):
                require(actual == case[key], "Wrong lowering fixture identity " + case["id"] + ":" + key)
            if collection == "lowering_cases":
                require(verify_lowering(request, behavior).passed, "Positive correspondence failed " + case["id"])
            else:
                try:
                    verify_lowering(request, behavior)
                except (bc.LoweringVerificationError, bc.UnsupportedBehaviorError, bc.SerializationError):
                    pass
                else:
                    raise AssertionError("Python accepted intended correspondence rejection " + case["id"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=CORPUS)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    corpus = build_corpus()
    check_corpus(corpus)
    content = encoded(corpus)
    require(len(content) < 8_000_000, "Request corpus exceeds its bounded fixture budget")
    if args.write:
        args.output.write_bytes(content)
    else:
        retained = args.output.read_bytes()
        check_corpus(json.loads(retained))
        require(retained == content, "Request domain corpus drifted; inspect before refreezing")
    print(json.dumps({"status": "written" if args.write else "checked", "cases": len(corpus["cases"]),
        "rejections": len(corpus["rejections"]), "lowering_cases": len(corpus["lowering_cases"]),
        "lowering_rejections": len(corpus["lowering_rejections"]), "bytes": len(content)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

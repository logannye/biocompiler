"""Bounded search over supplied composite implementations and RNA partitions."""

from itertools import combinations, islice
import json

from biocompiler.compiler.circuit_construction import build_circuit_construction
from biocompiler.errors import BiocompilerError, SerializationError
from biocompiler.ir.architecture_build import (
    ArchitectureAlternative, ArchitectureGap, PayloadArchitectureBuild,
    PayloadArchitectureExport, PayloadArchitecturePlan, PayloadArchitectureRequest,
    RequirementRealization,
)
from biocompiler.ir.intent import thaw_json
from biocompiler.ir.molecule_records import MAX_MOLECULE_ITEMS, MAX_MOLECULE_JSON_BYTES
from biocompiler.ir.payload_contracts import PayloadTemplate, merge_payload_templates, namespace_payload_template
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.semantics.payload_execution import derive_source_execution


# Candidate explanations are part of the output artifact, not an unbounded log.
# Reserve space for the original authority and a precise terminating diagnostic.
MAX_RETAINED_DIAGNOSTIC_ITEMS = 50_000
MAX_RETAINED_DIAGNOSTIC_BYTES = 1_000_000


def _receipt_cost(document, *, nested=False):
    pending, count = [document], 0
    while pending:
        value = pending.pop()
        count += 1
        if isinstance(value, dict):
            pending.extend(value.keys())
            pending.extend(value.values())
        elif isinstance(value, (tuple, list)):
            pending.extend(value)
    encoded = json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    # An alternative appears inside the build's alternatives array, four spaces
    # deeper than a standalone record. Include separators and a trailing newline.
    size = len(encoded.encode("utf-8")) + (4 * (encoded.count("\n") + 1) + 16 if nested else 1)
    return count, size


def _gap(category, code, requirements=(), candidates=(), message=None, conflict_set=()):
    return ArchitectureGap(category, code, tuple(requirements), tuple(candidates),
                           message or code.replace("_", " "), tuple(conflict_set))


def _runtime(node):
    return node.kind in {"rule", "state", "memory"} or node.kind.startswith("action.")


def _pattern_gaps(refinement, execution):
    source = {node.id: node for node in execution.behavior.nodes}
    mapping = refinement.source_bindings
    gaps = []
    if fingerprint(refinement.behavior.policies) != fingerprint(execution.behavior.policies):
        gaps.append(_gap("incompatible_composition", "execution_policy_mismatch", (), (refinement.id,)))
    for node in refinement.behavior.nodes:
        identity = mapping[node.id]
        wanted = source.get(identity)
        if wanted is None:
            gaps.append(_gap("missing_implementation", "absent_source_correspondence", ("source:" + identity,),
                             (refinement.id,)))
            continue
        actual = {"kind": node.kind, "inputs": tuple(mapping[ref] for ref in node.inputs),
                  "role": None if node.role is None else mapping[node.role],
                  "attributes": node.attributes, "data_type": node.data_type,
                  "contact_bound": node.contact_bound}
        expected = {key: getattr(wanted, key) for key in actual}
        if fingerprint(actual) != fingerprint(expected):
            gaps.append(_gap("incompatible_composition", "source_model_meaning_mismatch", ("source:" + identity,),
                             (refinement.id,), "The supplied model changes the source operation, inputs, type, role or parameters."))
    return gaps


def _coverage_gaps(selected, execution):
    covered = {identity for refinement in selected for identity in refinement.source_bindings.values()}
    owned = {}
    for refinement in selected:
        for local in refinement.owned_node_ids:
            owned.setdefault(refinement.source_bindings[local], []).append(refinement.id)
    gaps, identities = [], tuple(item.id for item in selected)
    for node in execution.behavior.nodes:
        if node.id not in covered or (_runtime(node) and node.id not in owned):
            gaps.append(_gap("missing_implementation", "uncovered_source_requirement", ("source:" + node.id,), identities))
        elif _runtime(node) and len(owned.get(node.id, ())) != 1:
            gaps.append(_gap("incompatible_composition", "duplicate_runtime_ownership", ("source:" + node.id,),
                             owned[node.id], "Runtime rules and stores need one supplied owner; label or byte identity cannot merge them."))
    return gaps


def _plan(selected, execution, request):
    placements, helpers, channels, controls = [], [], [], []
    assumptions = set(request.library.assumptions)
    for group in request.constraints.delivery_groups:
        assumptions.update(group.assumptions)
    for index, refinement in enumerate(selected):
        prefix = f"a{index:03d}_"
        mapping = refinement.source_bindings
        template_prefixes = {template.id: prefix + f"t{number:03d}_"
                             for number, template in enumerate(sorted(refinement.templates, key=lambda item: item.id))}
        assumptions.update(refinement.assumptions)
        for component in refinement.components:
            assumptions.update(component.assumptions)
        for placement in refinement.placements:
            record = placement.to_dict()
            record.update(id=prefix + placement.id,
                          template_id=template_prefixes[placement.template_id] + placement.template_id,
                          member_id=template_prefixes[placement.template_id] + placement.member_id,
                          recipient_role=mapping[placement.recipient_role])
            placements.append(record)
        for helper in refinement.helpers:
            record = helper.to_dict()
            record.update(id=prefix + helper.id, recipient_role=mapping[helper.recipient_role],
                          consumer_component_ids=[prefix + ref for ref in helper.consumer_component_ids],
                          placement_id=None if helper.placement_id is None else prefix + helper.placement_id,
                          provider_component_id=None if helper.provider_component_id is None else prefix + helper.provider_component_id,
                          depends_on=[prefix + ref for ref in helper.depends_on])
            helpers.append(record)
            assumptions.update(helper.assumptions)
        for channel in refinement.channels:
            record = channel.to_dict()
            record["id"] = prefix + channel.id
            for key in ("source_channel_id", "sender_role", "receiver_role", "sender_node_id", "receiver_node_id"):
                record[key] = mapping[record[key]]
            channels.append(record)
            assumptions.update(channel.assumptions)
        for control in refinement.controls:
            record = control.to_dict()
            record.update(id=prefix + control.id, domain_id=prefix + control.domain_id,
                          behavior_node_ids=[mapping[ref] for ref in control.behavior_node_ids],
                          controlling_node_ids=[mapping[ref] for ref in control.controlling_node_ids],
                          component_ids=[prefix + ref for ref in control.component_ids])
            controls.append(record)
            assumptions.update(control.assumptions)
    all_assumptions = tuple(sorted(assumptions))
    coverage = {ref.id: set(ref.source_bindings.values()) for ref in selected}
    owned = {}
    for refinement in selected:
        for local in refinement.owned_node_ids:
            owned.setdefault(refinement.source_bindings[local], []).append(refinement.id)
    runtime = {node.id for node in execution.behavior.nodes if _runtime(node)}
    all_covered = set().union(*coverage.values())
    ledger = []
    for original in execution.ledger:
        nodes = tuple(original["source_node_ids"])
        realizers = tuple(ref.id for ref in selected if coverage[ref.id].intersection(nodes))
        complete = set(nodes) <= all_covered and all(len(owned.get(ref, ())) == 1 for ref in set(nodes) & runtime)
        reasons = () if complete else ("uncovered_source_requirements",)
        if original["id"] == "source:complete_authority" and not execution.complete:
            complete, reasons = False, ("unresolved_source_obligations",)
        ledger.append(RequirementRealization(original["id"], nodes, realizers,
            "implemented" if complete else "unresolved",
            tuple(sorted({item for ref in selected if ref.id in realizers for item in ref.assumptions})), reasons))
    for key in request.constraints.to_dict():
        if key != "schema_version":
            ledger.append(RequirementRealization("constraint:" + key, (), tuple(ref.id for ref in selected),
                                                  "implemented", all_assumptions))
    for control in request.constraints.control_requirements:
        ledger.append(RequirementRealization("constraint:control:" + control.id, control.behavior_node_ids,
                      tuple(ref.id for ref in selected), "implemented", all_assumptions))
    for group in request.constraints.delivery_groups:
        ledger.append(RequirementRealization("constraint:delivery:" + group.id, group.recipient_roles,
                      tuple(ref.id for ref in selected), "implemented", all_assumptions))
    return PayloadArchitecturePlan(tuple(ref.id for ref in selected), tuple(ledger), tuple(placements),
                                   tuple(helpers), tuple(channels), tuple(controls), all_assumptions)


def _construct(selected, request):
    templates = []
    for index, refinement in enumerate(selected):
        for number, template in enumerate(sorted(refinement.templates, key=lambda item: item.id)):
            data = template.to_dict()
            roles = {node.id for node in refinement.behavior.nodes if node.kind == "role"}
            for requirement in data["requirements"]:
                for role in requirement["roles"]:
                    if role["role"] in roles:
                        role["role"] = refinement.source_bindings[role["role"]]
            template = PayloadTemplate.from_dict(data)
            templates.append(namespace_payload_template(template, f"a{index:03d}_t{number:03d}_"))
    authority = merge_payload_templates(templates, request.circuit, id=request.id + ".construction", mode="strict")
    return build_circuit_construction(authority)


def _delivered(construction):
    bundle = construction.candidate.bundle
    if bundle is None:
        return ()
    molecules = {item.id: item for item in bundle.molecules}
    complexes = {item.id: item for item in bundle.complexes}
    identities = set()
    for item in construction.request.requirements:
        if item.category in {"payload", "delivered_helper"}:
            if item.member_id in molecules:
                identities.add(item.member_id)
            elif item.member_id in complexes:
                identities.update(part.molecule_id for part in complexes[item.member_id].constituents)
    return tuple(molecules[identity] for identity in sorted(identities) if identity in molecules)


def _candidate_gaps(receipt, selected, request):
    """Explain candidate ineligibility separately from a corrupted build receipt."""
    result = []
    constraints = {"exact_rna_count": "exact_count", "maximum_rna_count": "max_count",
                   "maximum_rna_member_length": "max_member_bases", "maximum_rna_total_length": "max_total_bases"}
    for diagnostic in receipt.diagnostics:
        code, implicated = diagnostic.code, set(diagnostic.requirement_ids)
        category = "incompatible_composition"
        if code in constraints:
            implicated.add("constraint:" + constraints[code])
        for control in request.constraints.control_requirements:
            if control.id in code:
                implicated.add("constraint:control:" + control.id)
        for group in request.constraints.delivery_groups:
            if group.id in code:
                implicated.add("constraint:delivery:" + group.id)
        for refinement in selected:
            for local, original in refinement.source_bindings.items():
                if code.endswith(":" + local) or code.endswith(":" + original):
                    implicated.add("source:" + original)
            for helper in refinement.helpers:
                if helper.id in code or helper.capability in code:
                    implicated.update("source:" + refinement.source_bindings[ref]
                        for binding in refinement.bindings
                        if set(binding.component_ids).intersection(helper.consumer_component_ids)
                        for ref in binding.behavior_node_ids)
        if "unsupported" in code or "external_observation_unbound" in code or any(
            token in code for token in ("unowned_executable_state", "unowned_executable_memory", "unowned_executable_action")
        ):
            category = "unsupported_semantics"
        if any(token in code for token in ("construction_", "molecule_", "template_", "delivered_member_not_rna")):
            category = "missing_sequence_authority"
        if code.startswith(("plan_", "source_manifest", "request_authority", "malformed_architecture")):
            category = "independent_verification_failure"
        result.append(_gap(category, code, tuple(sorted(implicated)), tuple(ref.id for ref in selected),
                           diagnostic.message, tuple(sorted(implicated))))
    return result


def compile_payload_architecture(request):
    """Select complete supplied architectures; never infer sequence from intent."""
    require(isinstance(request, PayloadArchitectureRequest), "Expected complete RNA architecture authority.")
    request = PayloadArchitectureRequest.from_dict(request.to_dict())
    execution = derive_source_execution(request.source)
    diagnostics = tuple(_gap("unsupported_semantics" if item.category != "contradiction" else "contradictory_requirements",
                             item.code, tuple("source:" + ref for ref in item.source_node_ids), (), item.message)
                        for item in execution.diagnostics)
    alternatives = []
    prefiltered = explored = retained_items = retained_bytes = 0
    baseline = PayloadArchitectureBuild(request.fingerprint, execution, None, None, (), diagnostics, "search_exhausted")
    # A source ledger which cannot itself fit cannot be made reviewable by
    # truncating candidate explanations. Preserve the existing strict boundary.
    baseline.to_json()
    baseline_items, baseline_bytes = _receipt_cost(baseline.to_dict())
    item_budget = min(MAX_RETAINED_DIAGNOSTIC_ITEMS, max(0, MAX_MOLECULE_ITEMS - baseline_items - 4096))
    byte_budget = min(MAX_RETAINED_DIAGNOSTIC_BYTES, max(0, MAX_MOLECULE_JSON_BYTES - baseline_bytes - 64_000))

    def finish(status, plan=None, construction=None, extra=()):
        build = PayloadArchitectureBuild(request.fingerprint, execution, plan, construction,
                                         tuple(alternatives), (*diagnostics, *extra), status)
        try:
            build.to_json()
        except SerializationError as error:
            if plan is None:
                raise
            # A selected construction can exceed the enclosing receipt budget
            # even when its constituent artifacts are individually bounded.
            budget_gap = _gap("search_budget_exhausted", "architecture_selected_output_budget_exhausted", (),
                plan.selected_refinement_ids,
                "The selected construction exceeds the bounded reviewable output; retained candidate records remain available. "
                + str(error))
            build = PayloadArchitectureBuild(request.fingerprint, execution, None, None,
                tuple(alternatives), (*diagnostics, budget_gap), "search_exhausted")
            build.to_json()
        from biocompiler.verification.payload_architecture import check_payload_architecture
        receipt = check_payload_architecture(build, expected_request=request)
        require(receipt.passed, "Independent architecture verification failed: " + str(receipt.diagnostics))
        return build

    def retain(alternative):
        nonlocal retained_items, retained_bytes
        items, size = _receipt_cost(alternative.to_dict(), nested=True)
        if retained_items + items > item_budget or retained_bytes + size > byte_budget:
            return False
        alternatives.append(alternative)
        retained_items += items
        retained_bytes += size
        return True

    def retention_exhausted(candidate_ids):
        return finish("search_exhausted", extra=(_gap("search_budget_exhausted", "architecture_record_budget_exhausted", (),
            candidate_ids,
            f"Examined {prefiltered} of {len(request.library.refinements)} supplied refinement patterns and {explored} candidate subsets; "
            f"retained {len(alternatives)} complete alternative records. The next record exceeds the retained diagnostic budget "
            f"of {item_budget} JSON items or {byte_budget} serialized bytes. No infeasibility or optimality claim."),))

    if execution.behavior is None or (diagnostics and request.constraints.require_complete):
        return finish("unsupported")
    choices = []
    for refinement in request.library.refinements:
        prefiltered += 1
        gaps = _pattern_gaps(refinement, execution)
        if gaps:
            if not retain(ArchitectureAlternative((refinement.id,), tuple(gaps))):
                return retention_exhausted((refinement.id,))
        else:
            choices.append(refinement)
    total = (1 << len(choices)) - 1
    candidates = (selected for size in range(1, len(choices) + 1) for selected in combinations(choices, size))
    winner = None
    for selected in islice(candidates, request.constraints.max_combinations):
        explored += 1
        identifiers = tuple(ref.id for ref in selected)
        gaps = _coverage_gaps(selected, execution)
        plan = construction = None
        if not gaps:
            try:
                plan = _plan(selected, execution, request)
                construction = _construct(selected, request)
                if not construction.assessment.passed or not construction.assessment.complete:
                    gaps.append(_gap("missing_sequence_authority", "incomplete_construction", (), identifiers,
                                     str(construction.assessment.diagnostics)))
                else:
                    from biocompiler.verification.payload_architecture import check_payload_architecture
                    trial = PayloadArchitectureBuild(request.fingerprint, execution, plan, construction, (), diagnostics,
                                                     "partial")
                    receipt = check_payload_architecture(trial, expected_request=request)
                    if not receipt.passed:
                        gaps.extend(_candidate_gaps(receipt, selected, request))
                    elif receipt.unresolved:
                        if request.constraints.require_complete:
                            gaps.append(_gap("unsupported_semantics", "unresolved_architecture_obligations", (), identifiers,
                                             "; ".join(receipt.unresolved)))
            except (BiocompilerError, ValueError, KeyError) as error:
                gaps.append(_gap("missing_sequence_authority", "construction_authority_rejected", (), identifiers, str(error)))
        if not retain(ArchitectureAlternative(identifiers, tuple(gaps))):
            return retention_exhausted(identifiers)
        if not gaps:
            preference = request.constraints.preferred_refinement_ids
            delivered = _delivered(construction)
            score = (sum(preference.index(ref.id) if ref.id in preference else len(preference) for ref in selected),
                     len(delivered), sum(len(member.sequence) for member in delivered), identifiers)
            if winner is None or score < winner[0]:
                winner = (score, plan, construction, receipt)
    if total > request.constraints.max_combinations:
        return finish("search_exhausted", extra=(_gap("search_budget_exhausted", "architecture_search_budget_exhausted", (), (),
            f"Examined {request.constraints.max_combinations} of {total} compatible-model subsets; no optimality or infeasibility claim."),))
    if winner is None:
        implicated = tuple(sorted({identity for alternative in alternatives for gap in alternative.gaps
                                   for identity in gap.requirement_ids}))
        return finish("no_solution", extra=(_gap("missing_implementation", "no_supplied_architecture_satisfies_requirements", implicated,
            tuple(ref.id for ref in choices), "No examined supplied architecture met all source, composition and construction requirements; the identified conflict set is not claimed minimal.",
            implicated),))
    _, plan, construction, receipt = winner
    return finish("partial" if diagnostics or receipt.unresolved else "compiled", plan, construction)


def export_payload_architecture(build, *, expected_request):
    """Freshly check and export delivered RNA with its inseparable full manifest."""
    from biocompiler.verification.payload_architecture import check_payload_architecture
    receipt = check_payload_architecture(build, expected_request=expected_request)
    require(receipt.passed and receipt.construction_complete and build.construction is not None,
            "Architecture export requires fresh independent construction verification.")
    lines = []
    for member in _delivered(build.construction):
        require(member.space.alphabet == "RNA", "Every delivered genetic member must be RNA.")
        lines.append(">" + member.id + " alphabet=RNA")
        lines.extend(member.sequence[index:index + 80] for index in range(0, len(member.sequence), 80))
    require(bool(lines), "No delivered RNA payloads in this architecture.")
    manifest = {"request_fingerprint": expected_request.fingerprint,
                "build": build.to_dict(), "verification": receipt.to_dict(),
                "delivered_member_ids": [member.id for member in _delivered(build.construction)],
                "source_authority": "Retain the independently supplied request separately."}
    return PayloadArchitectureExport("\n".join(lines) + "\n", thaw_json(manifest))

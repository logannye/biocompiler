"""Independent checks of supplied RNA architecture refinements.

The original program and separately supplied executable contracts are the
authorities. Architecture names, coverage labels and stored PASS records do not
establish correspondence. Exact equality under a declared execution profile is
a conditional language claim; it is not evidence of behavior in a patient.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import ClassVar

from biocompiler.artifacts.manifest import _hash
from biocompiler.compiler.behavior import verify_lowering
from biocompiler.errors import BiocompilerError
from biocompiler.ir.architecture_build import ArchitectureGap, RequirementRealization
from biocompiler.ir.behavior import BEHAVIOR_V2, lineage_for
from biocompiler.ir.circuit_intent import source_build_request
from biocompiler.ir.molecule_records import _MoleculeRecord, _decode_records
from biocompiler.ir.serialization import fingerprint, names, require
from biocompiler.verification.circuit_construction import check_circuit_construction
from biocompiler.verification.evidence import CheckOutcome


CHECKER_VERSION = "biocompiler.payload_architecture_checker.v0.2"
CLAIM_SCOPE = (
    "Exact source and supplied composite execution-contract correspondence, "
    "explicit functional requirements under the asserted Boolean control profile, "
    "declared physical composition and complete RNA construction only. "
    "No empirical component function or human therapeutic admission is established."
)


@dataclass(frozen=True)
class PayloadArchitectureVerification(_MoleculeRecord):
    request_fingerprint: str
    build_fingerprint: str
    outcome: CheckOutcome
    translation_complete: bool
    construction_complete: bool
    diagnostics: tuple[ArchitectureGap, ...]
    unresolved: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    checker_version: str = CHECKER_VERSION
    claim_scope: str = CLAIM_SCOPE
    search_verified: bool = False
    empirical_validation: str = "unknown"
    human_therapeutic_admission: str = "not_admitted"
    schema_version: ClassVar[str] = "biocompiler.payload_architecture_verification.v0.1"
    _decoders: ClassVar[dict] = {
        "outcome": CheckOutcome,
        "diagnostics": _decode_records(ArchitectureGap, 4096),
    }

    def __post_init__(self):
        _hash(self.request_fingerprint, "Architecture authority")
        _hash(self.build_fingerprint, "Architecture build")
        require(isinstance(self.outcome, CheckOutcome), "Invalid architecture check outcome.")
        for key in ("translation_complete", "construction_complete"):
            require(type(getattr(self, key)) is bool, "Invalid completeness flag.")
        require(isinstance(self.diagnostics, (tuple, list))
                and all(isinstance(item, ArchitectureGap) for item in self.diagnostics),
                "Invalid independent architecture diagnostics.")
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        for key in ("unresolved", "assumptions"):
            object.__setattr__(self, key, names(getattr(self, key), key))
        require(self.checker_version == CHECKER_VERSION and self.claim_scope == CLAIM_SCOPE
                and self.search_verified is False and self.empirical_validation == "unknown"
                and self.human_therapeutic_admission == "not_admitted", "Invalid checker claim scope.")
        require(self.outcome is not CheckOutcome.PASS or not self.diagnostics,
                "Passing architecture check cannot contain contradictions.")
        require(not self.translation_complete or self.construction_complete and not self.unresolved,
                "A complete translation cannot retain unresolved obligations.")

    @property
    def passed(self):
        return self.outcome is CheckOutcome.PASS


def _source_manifest_checks(manifest, source):
    """Reconstruct every retained source record without the manifest producer."""
    failures, unresolved = [], []
    original = source_build_request(source)
    nodes = {node.id: node for node in original.intent.nodes}
    if fingerprint(manifest.source.to_dict()) != fingerprint(source.to_dict()):
        failures.append("source_authority")
    roles = tuple(node.id for node in nodes.values() if node.kind == "role")
    outputs = []
    for rule in nodes.values():
        if rule.kind != "rule":
            continue
        for identity in rule.inputs[2:]:
            action = nodes[identity]
            primitive = nodes[action.inputs[0]] if action.kind == "action.pulse" else action
            trigger = rule.attributes.get("trigger")
            activation = (
                "explicit_duration" if action.kind == "action.pulse" else
                "level" if primitive.attributes.get("ongoing") or
                primitive.kind == "action.state_set" and trigger == "condition" else
                "event" if trigger == "event" else "onset"
            )
            outputs.append({
                "id": f"output:{rule.id}:{identity}", "rule_id": rule.id,
                "action_id": identity, "guard_id": rule.inputs[1], "role_id": rule.role,
                "action_kind": primitive.kind, "lineage": list(lineage_for(nodes, rule.id)),
                "trigger": trigger, "activation": activation,
                "product": (nodes[primitive.inputs[0]].attributes.get("product")
                            if primitive.kind == "action.secrete" else None),
                "semantics": {
                    "action": action.to_dict(include_source=False),
                    "primitive_action": primitive.to_dict(include_source=False),
                    "dependencies": [nodes[ref].to_dict(include_source=False)
                                     for ref in lineage_for(nodes, identity)],
                },
            })
    ledger = [{"id": "source:" + node.id, "kind": node.kind,
               "source_node_ids": [node.id], "semantics": node.to_dict(include_source=False)}
              for node in nodes.values()]
    ledger.append({"id": "source:complete_authority", "kind": "source_authority",
                   "source_node_ids": list(nodes), "semantics": source.to_dict()})
    states, channels = [], []
    for node in nodes.values():
        if node.kind == "state":
            assignments = []
            for output in outputs:
                primitive = output["semantics"]["primitive_action"]
                if output["action_kind"] == "action.state_set" and primitive["inputs"][0] == node.id:
                    assignments.append({"output_id": output["id"], "rule_id": output["rule_id"],
                                        "action_id": output["action_id"], "guard_id": output["guard_id"],
                                        "value": primitive["attributes"]["value"]})
            states.append({"id": node.id, "declaration": node.to_dict(include_source=False),
                           "assignments": assignments})
        if node.kind == "channel":
            senders = []
            for output in outputs:
                primitive = output["semantics"]["primitive_action"]
                if output["action_kind"] == "action.emit" and primitive["inputs"][1] == node.id:
                    senders.append({"output_id": output["id"], "role_id": output["role_id"],
                                    "rule_id": output["rule_id"], "action_id": output["action_id"],
                                    "value_id": primitive["inputs"][2] if len(primitive["inputs"]) == 3 else None})
            channels.append({"id": node.id, "declaration": node.to_dict(include_source=False),
                             "senders": senders,
                             "receivers": [{"observation_id": item.id, "role_id": item.role}
                                           for item in nodes.values()
                                           if item.kind == "channel_observation" and item.inputs[1] == node.id],
                             "transport": "requires_explicit_architecture_contract"})
    authority = {
        "roles": roles, "outputs": outputs, "ledger": ledger,
        "role_nodes": {role: tuple(node.id for node in nodes.values() if node.role in (None, role))
                       for role in roles},
        "states": states, "channels": channels,
    }
    for key, value in authority.items():
        supplied = getattr(manifest, key)
        if key == "outputs":
            supplied = [{name: item for name, item in output.to_dict().items() if name != "schema_version"}
                        for output in supplied]
        if fingerprint(supplied) != fingerprint(value):
            failures.append("source_manifest_" + key)
    if manifest.behavior is None:
        unresolved.append("source_execution_unavailable")
    else:
        try:
            verify_lowering(original, manifest.behavior)
        except BiocompilerError as error:
            failures.append("source_behavior:" + str(error))
    constraints = set(original.implementation_constraints)
    if original.behavior_profile == BEHAVIOR_V2:
        constraints.discard("execution")
    if constraints:
        unresolved.append("uninterpreted_implementation_constraints")
    if original.preferences:
        unresolved.append("uninterpreted_source_preferences")
    if not isinstance(source, type(original)):
        unresolved.append("wrapped_source_obligations")
    return failures, unresolved, authority


def _model_correspondence(model, node_map, source_behavior):
    """Compare actual supplied operations and edges after explicit alpha mapping.

    Source locations, graph names and requirement labels are provenance; every
    executable attribute, type, binding and policy remains semantic authority.
    The mapping cannot omit a hidden rule, action or automatic state store.
    """
    problems = []
    actual = {node.id: node for node in model.nodes}
    expected = {node.id: node for node in source_behavior.nodes}
    if set(node_map) != set(actual):
        problems.append("model_mapping_inventory")
    if len(set(node_map.values())) != len(node_map):
        problems.append("model_mapping_not_injective")
    if set(node_map.values()) - set(expected):
        problems.append("model_mapping_unknown_source")
    if fingerprint(model.policies) != fingerprint(source_behavior.policies):
        problems.append("model_execution_policies")
    for identity, node in actual.items():
        target = expected.get(node_map.get(identity))
        if target is None:
            continue
        if any(ref not in node_map for ref in node.inputs) or (
            node.role is not None and node.role not in node_map
        ):
            problems.append("model_reference_unmapped:" + identity)
            continue
        emitted = {
            "kind": node.kind,
            "inputs": [node_map[ref] for ref in node.inputs],
            "role": node_map[node.role] if node.role is not None else None,
            "attributes": node.attributes,
            "data_type": node.data_type,
            "contact_bound": node.contact_bound,
        }
        authority = {
            "kind": target.kind,
            "inputs": target.inputs,
            "role": target.role,
            "attributes": target.attributes,
            "data_type": target.data_type,
            "contact_bound": target.contact_bound,
        }
        if fingerprint(emitted) != fingerprint(authority):
            problems.append("model_operation_mismatch:" + identity + ":" + target.id)
    return problems


def _namespace_template(template, prefix):
    """Reconstruct local identities without importing the producer namespace pass."""
    document = template.to_dict()
    local_types = {
        "payload_template", "construction_root_source", "circuit_molecule",
        "construction_transform_step", "construction_product_port", "construction_value_ref",
        "construction_output_member", "construction_member_requirement",
        "construction_role_declaration", "construction_complex_member",
        "construction_amount_declaration",
    }
    frames = {source.molecule.space.id for source in template.sources}
    frames.update(port.space_id for step in template.steps for port in step.ports)
    frames.update(member.space_id for member in template.output_members)
    pending = [document]
    while pending:
        value = pending.pop()
        if isinstance(value, list):
            pending.extend(value)
            continue
        if not isinstance(value, dict):
            continue
        schema = value.get("schema_version", "")
        kind = schema.removeprefix("biocompiler.").rsplit(".v", 1)[0]
        if kind == "molecular_declaration_provenance":
            continue
        pending.extend(child for child in value.values() if isinstance(child, (dict, list)))
        if kind in local_types or (kind == "molecule_coordinate_space" and value.get("id") in frames):
            value["id"] = prefix + value["id"]
        if value.get("space_id") in frames:
            value["space_id"] = prefix + value["space_id"]
        for key in ("member_id", "port_id"):
            if value.get(key) is not None:
                value[key] = prefix + value[key]
        if kind in {"chemistry_disposition", "feature_disposition"}:
            value["source_id"] = prefix + value["source_id"]
        if kind == "construction_amount_declaration":
            for key in ("subject_id", "preparation_id"):
                value[key] = prefix + value[key]
            value["role_instance_ids"] = [prefix + item for item in value["role_instance_ids"]]
    return document


def _inventories(selected):
    result = {key: [] for key in ("placements", "helpers", "channels", "control_domains")}
    templates = []
    for index, refinement in enumerate(sorted(selected, key=lambda item: item.id)):
        prefix = f"a{index:03d}_"
        template_prefix = {template.id: prefix + f"t{offset:03d}_"
                           for offset, template in enumerate(sorted(refinement.templates, key=lambda item: item.id))}
        remap = refinement.source_bindings
        for template in sorted(refinement.templates, key=lambda item: item.id):
            document = _namespace_template(template, template_prefix[template.id])
            local_roles = {node.id for node in refinement.behavior.nodes if node.kind == "role"}
            for requirement in document["requirements"]:
                for role in requirement["roles"]:
                    if role["role"] in local_roles:
                        role["role"] = remap[role["role"]]
            templates.append(document)
        for original in refinement.placements:
            value = original.to_dict()
            value.update(id=prefix + original.id,
                         template_id=template_prefix[original.template_id] + original.template_id,
                         member_id=template_prefix[original.template_id] + original.member_id,
                         recipient_role=remap[original.recipient_role])
            result["placements"].append(value)
        for original in refinement.helpers:
            value = original.to_dict()
            value.update(id=prefix + original.id,
                         recipient_role=remap[original.recipient_role],
                         consumer_component_ids=[prefix + item for item in original.consumer_component_ids],
                         provider_component_id=(prefix + original.provider_component_id
                                                if original.provider_component_id is not None else None),
                         placement_id=prefix + original.placement_id if original.placement_id is not None else None,
                         depends_on=[prefix + item for item in original.depends_on])
            result["helpers"].append(value)
        for original in refinement.channels:
            value = original.to_dict()
            value["id"] = prefix + original.id
            for key in ("source_channel_id", "sender_role", "receiver_role", "sender_node_id", "receiver_node_id"):
                value[key] = remap[getattr(original, key)]
            result["channels"].append(value)
        for original in refinement.controls:
            value = original.to_dict()
            value.update(id=prefix + original.id, domain_id=prefix + original.domain_id,
                         behavior_node_ids=[remap[item] for item in original.behavior_node_ids],
                         controlling_node_ids=[remap[item] for item in original.controlling_node_ids],
                         component_ids=[prefix + item for item in original.component_ids])
            result["control_domains"].append(value)
    return result, templates


def _expected_construction(request, documents):
    from biocompiler.ir.circuit_construction import CircuitConstructionRequest
    keys = ("sources", "steps", "output_members", "requirements", "complex_members", "amounts", "payload_structures")
    return CircuitConstructionRequest.from_dict({
        "schema_version": CircuitConstructionRequest.schema_version,
        "id": request.id + ".construction", "circuit": request.circuit.to_dict(), "mode": "strict",
        **{key: [item for document in documents for item in document[key]] for key in keys},
    })


def _runtime(node):
    return node.kind in {"rule", "state", "memory"} or node.kind.startswith("action.")


def _causal_nodes(nodes, identities):
    # Stores and transported observations have causal edges which are absent
    # from the expression DAG. Keep every installed writer/sender as a possible
    # influence; neither a current guard value nor a library label proves that
    # a dynamic path cannot affect an output.
    installations = {}
    for rule in nodes.values():
        if rule.kind != "rule":
            continue
        for identity in rule.inputs[2:]:
            installations.setdefault(identity, set()).add(rule.id)
            action = nodes[identity]
            if action.kind == "action.pulse":
                installations.setdefault(action.inputs[0], set()).add(rule.id)
    causal = set()
    for identity in identities:
        causal.update(lineage_for(nodes, identity))
        for rule_id in installations.get(identity, ()):
            causal.update(lineage_for(nodes, rule_id))
    visited_states, visited_channels = set(), set()
    while True:
        states = {identity for identity in causal if nodes[identity].kind == "state"} - visited_states
        channels = {nodes[identity].inputs[1] for identity in causal
                    if nodes[identity].kind == "channel_observation"} - visited_channels
        if not states and not channels:
            break
        visited_states.update(states)
        visited_channels.update(channels)
        writers = {node.id for node in nodes.values()
                   if node.kind == "action.state_set" and node.inputs[0] in states
                   or node.kind == "action.emit" and node.inputs[1] in channels}
        for writer in writers:
            for rule_id in installations.get(writer, ()):
                causal.update(lineage_for(nodes, rule_id))
    return causal


def _expected_ledger(request, source_ledger, source_nodes, selected, assumptions, source_complete):
    owners, covered = {}, {}
    for refinement in selected:
        for node_id in refinement.source_bindings.values():
            covered.setdefault(node_id, set()).add(refinement.id)
        for identity in refinement.owned_node_ids:
            owners.setdefault(refinement.source_bindings[identity], set()).add(refinement.id)
    ledger = []
    for item in source_ledger:
        refs = tuple(item["source_node_ids"])
        candidates = tuple(sorted({candidate for ref in refs for candidate in covered.get(ref, ())}))
        fulfilled = all(ref in covered and (not _runtime(source_nodes[ref]) or len(owners.get(ref, ())) == 1)
                        for ref in refs)
        authority = item["id"] == "source:complete_authority"
        if authority:
            fulfilled = fulfilled and source_complete
        item_assumptions = tuple(sorted({value for refinement in selected if refinement.id in candidates
                                         for value in refinement.assumptions}))
        ledger.append(RequirementRealization(
            item["id"], refs, candidates, "implemented" if fulfilled else "unresolved", item_assumptions,
            () if fulfilled else ("unresolved_source_obligations" if authority and not source_complete
                                  else "uncovered_source_requirements",),
        ))
    for key in request.constraints.to_dict():
        if key != "schema_version":
            ledger.append(RequirementRealization("constraint:" + key, (), tuple(item.id for item in selected),
                                                 "implemented", assumptions))
    for requirement in request.constraints.control_requirements:
        ledger.append(RequirementRealization("constraint:control:" + requirement.id,
                      requirement.behavior_node_ids, tuple(item.id for item in selected), "implemented", assumptions))
    for group in request.constraints.delivery_groups:
        ledger.append(RequirementRealization("constraint:delivery:" + group.id,
                      group.recipient_roles, tuple(item.id for item in selected), "implemented", assumptions))
    return ledger, owners


def _refinement_checks(refinement, behavior, target):
    failures = _model_correspondence(refinement.behavior, refinement.source_bindings, behavior)
    nodes = {item.id: item for item in refinement.behavior.nodes}
    owned = set(refinement.owned_node_ids)
    action_references = {node.inputs[0] for node in nodes.values() if node.kind == "action.pulse"}
    for node in nodes.values():
        if node.id not in owned and _runtime(node) and node.id not in action_references:
            failures.append("unowned_executable_" + node.kind + ":" + node.id)
    components = {item.id: item for item in refinement.components}
    modeled = set()
    for component in components.values():
        if component.classification == "synthetic_model":
            failures.append("unsupported_intrinsic_model_refinement:" + component.id)
        elif component.classification == "modeled_component":
            if any(pin.kind == "model" and pin.content_fingerprint == refinement.behavior.fingerprint
                   for pin in component.identities):
                modeled.add(component.id)
            else:
                failures.append("component_model_authority:" + component.id)
        if target.payload_format.value not in component.supported_targets:
            failures.append("component_target:" + component.id)
        physical = (*component.ports, *component.capabilities, *component.resources,
                    *(item for item in component.dependencies if item.required))
        if any(item.compartment not in target.compartments for item in physical):
            failures.append("component_compartment:" + component.id)
        if component.resources or component.supported_domain.constraints:
            failures.append("component_operating_domain_or_resources_unmapped:" + component.id)
    for identity in owned:
        if _runtime(nodes[identity]) and not any(identity in binding.behavior_node_ids
                and modeled.intersection(binding.component_ids) for binding in refinement.bindings):
            failures.append("executable_material_model_missing:" + identity)
    placements = {item.id: item for item in refinement.placements}
    for placement in placements.values():
        if placement.compartment not in target.compartments:
            failures.append("placement_compartment:" + placement.id)
    binding_roles, binding_members = {}, {}
    for binding in refinement.bindings:
        roles = {nodes[item].role for item in binding.behavior_node_ids if nodes[item].role is not None}
        bound_placements = [placements[item] for item in binding.placement_ids]
        for component_id in binding.component_ids:
            binding_roles.setdefault(component_id, set()).update(roles)
            binding_members.setdefault(component_id, set()).update(
                (item.template_id, item.member_id) for item in bound_placements)
        for role in roles:
            if not any(item.recipient_role == role for item in bound_placements):
                failures.append("material_recipient_missing:" + binding.id + ":" + role)
    for component in components.values():
        interfaces = (*component.ports, *component.capabilities, *component.resources,
                      *(item for item in component.dependencies if item.required))
        if any(item.role not in binding_roles.get(component.id, ()) for item in interfaces):
            failures.append("component_recipient_correspondence:" + component.id)
    helpers = {item.id: item for item in refinement.helpers}
    for helper in helpers.values():
        if helper.compartment not in target.compartments:
            failures.append("helper_compartment:" + helper.id)
        if len(helper.consumer_component_ids) > helper.capacity or (
            helper.sharing == "exclusive" and len(helper.consumer_component_ids) != 1
        ):
            failures.append("helper_capacity:" + helper.id)
        if helper.availability == "host" and helper.capability not in target.capabilities:
            failures.append("host_capability_unavailable:" + helper.id)
        if helper.availability == "external":
            failures.append("helper_external_observation_unbound:" + helper.id)
        if helper.initialization == "after_trigger":
            failures.append("helper_trigger_authority_missing:" + helper.id)
        if helper.placement_id is not None:
            placement = placements[helper.placement_id]
            if (placement.recipient_role, placement.compartment) != (helper.recipient_role, helper.compartment):
                failures.append("helper_placement:" + helper.id)
            physical = (placement.template_id, placement.member_id)
            for consumer in helper.consumer_component_ids:
                same = physical in binding_members.get(consumer, ())
                if same != (helper.availability == "same_rna"):
                    failures.append("helper_rna_relationship:" + helper.id + ":" + consumer)
        for consumer in helper.consumer_component_ids:
            if helper.recipient_role not in binding_roles.get(consumer, ()):
                failures.append("helper_recipient:" + helper.id + ":" + consumer)
        if helper.provider_component_id is not None:
            provider = components[helper.provider_component_id]
            if not any(item.id == helper.capability and item.role == helper.recipient_role
                       and item.compartment == helper.compartment and item.scope == "cell"
                       for item in provider.capabilities):
                failures.append("helper_provider_capability:" + helper.id)
    # Ground both helpers and their producing components. Cyclic declarations
    # cannot create a capability before one real starting supply is available.
    grounded_helpers, grounded_components = set(), set()
    while True:
        next_helpers = {
            item.id for item in helpers.values() if set(item.depends_on) <= grounded_helpers
            and item.initialization != "after_trigger"
            and ((item.provider_component_id is None and item.initialization == "available_at_start")
                 or item.provider_component_id in grounded_components)
        }
        next_components = {
            component.id for component in components.values() if all(
                any(helper.id in grounded_helpers and component.id in helper.consumer_component_ids
                    and helper.capability == dependency.capability
                    and helper.recipient_role == dependency.role and dependency.scope == "cell"
                    and helper.compartment == dependency.compartment for helper in helpers.values())
                for dependency in component.dependencies if dependency.required)
        }
        if next_helpers <= grounded_helpers and next_components <= grounded_components:
            break
        grounded_helpers.update(next_helpers)
        grounded_components.update(next_components)
    for identity in sorted(helpers.keys() - grounded_helpers):
        failures.append("helper_initialization_ungrounded:" + identity)
    for identity in sorted(components.keys() - grounded_components):
        failures.append("component_dependency_ungrounded:" + identity)
    for control in refinement.controls:
        # State writers are dynamic causal edges, absent from the expression DAG.
        causal = _causal_nodes(nodes, control.behavior_node_ids)
        if not set(control.controlling_node_ids) <= causal:
            failures.append("control_input_not_causal:" + control.id)
        material = {component for binding in refinement.bindings
                    if set(binding.behavior_node_ids).intersection(control.behavior_node_ids)
                    for component in binding.component_ids}
        if not set(control.component_ids) <= material or not modeled.intersection(control.component_ids):
            failures.append("control_material_correspondence:" + control.id)
        if control.kind == "activity_control":
            controlled_actions = {identity for identity in control.behavior_node_ids
                                  if nodes[identity].kind.startswith("action.")}
            controlled_actions.update(action for identity in control.behavior_node_ids if nodes[identity].kind == "rule"
                                      for action in nodes[identity].inputs[2:])
            supported_actions = {"action.eliminate", "action.engulf", "action.rest"}
            for identity in controlled_actions:
                action = nodes[identity]
                primitive = nodes[action.inputs[0]] if action.kind == "action.pulse" else action
                if (primitive.kind not in supported_actions or not any(identity in output.action_ids
                    and output.product.kind == "biological_activity" and output.lifecycle.mode == "activity_control"
                    for output in refinement.output_contracts)):
                    failures.append("activity_control_not_realized:" + control.id)
            if not controlled_actions:
                failures.append("activity_control_action_missing:" + control.id)
    return failures


def _supplementary_checks(request, selected):
    from types import SimpleNamespace
    from biocompiler.ir.circuit_intent import ExecutableCircuitBehavior
    from biocompiler.ir.executable_payload import PayloadCircuitBinding
    from biocompiler.verification.executable_payload import _check_circuit_bindings

    failures, unresolved = [], []
    source = source_build_request(request.source)
    nodes = {node.id: node for node in source.intent.nodes}
    by_requirement = {}
    for refinement in selected:
        for binding in refinement.output_contracts:
            by_requirement.setdefault(binding.requirement_id, []).append((refinement, binding))
    original_ids = {item.id for item in request.circuit.requirements}
    for identity in sorted(by_requirement.keys() - original_ids):
        failures.append("unknown_output_requirement:" + identity)
    legacy, legacy_bindings = [], []
    installed = {action for node in nodes.values() if node.kind == "rule" for action in node.inputs[2:]}
    for requirement in request.circuit.requirements:
        declarations = by_requirement.get(requirement.id, ())
        if len(declarations) != 1:
            failures.append("supplementary_output_inventory:" + requirement.id)
            continue
        refinement, binding = declarations[0]
        mapped = tuple(sorted(refinement.source_bindings[ref] for ref in binding.action_ids))
        if not set(binding.action_ids) <= set(refinement.owned_node_ids):
            failures.append("supplementary_output_not_owned:" + requirement.id)
        if (binding.product.fingerprint != requirement.behavior.output.fingerprint or
            binding.lifecycle.fingerprint != requirement.behavior.lifecycle.fingerprint):
            failures.append("supplementary_output_authority:" + requirement.id)
        if not set(mapped) <= installed:
            failures.append("supplementary_output_not_installed:" + requirement.id)
        for identity in mapped:
            action = nodes[identity]
            primitive = nodes[action.inputs[0]] if action.kind == "action.pulse" else action
            rules = [node for node in nodes.values() if node.kind == "rule" and identity in node.inputs[2:]]
            if (action.role != requirement.role_id or identity not in requirement.source_node_ids
                or not any(rule.id in requirement.source_node_ids for rule in rules)):
                failures.append("supplementary_source_role_or_lineage:" + requirement.id)
            if primitive.kind == "action.secrete" and nodes[primitive.inputs[0]].attributes["product"] != binding.product.id:
                failures.append("supplementary_source_product:" + requirement.id)
            elif primitive.kind == "action.present" and primitive.attributes["antigen"] != binding.product.id:
                failures.append("supplementary_source_product:" + requirement.id)
            elif primitive.kind not in {"action.secrete", "action.present"}:
                unresolved.append("source_output_product_mapping:" + requirement.id + ":" + identity)
        if isinstance(requirement.behavior, ExecutableCircuitBehavior):
            if mapped != tuple(sorted(requirement.behavior.action_ids)):
                failures.append("supplementary_action_identity:" + requirement.id)
            try:
                verify_lowering(source, requirement.behavior.response)
            except BiocompilerError as error:
                failures.append("supplementary_source_behavior:" + requirement.id + ":" + str(error))
            if requirement.behavior.inputs or requirement.input_bindings:
                unresolved.append("executable_input_observation_mapping:" + requirement.id)
        elif len(mapped) == 1:
            rules = [node for node in nodes.values() if node.kind == "rule"
                     and mapped[0] in node.inputs[2:] and node.id in requirement.source_node_ids]
            if len(rules) != 1:
                failures.append("supplementary_rule_mapping:" + requirement.id)
            else:
                legacy.append(requirement)
                legacy_bindings.append(PayloadCircuitBinding(requirement.id, rules[0].id, mapped[0],
                    {entry.observation_id: entry.source_node_id for entry in requirement.input_bindings}))
        else:
            failures.append("boolean_supplementary_output_mapping:" + requirement.id)
        for provider in requirement.behavior.dependencies:
            unresolved.append("circuit_provider_mapping:" + requirement.id + ":" + provider.id)
    if legacy:
        checked = _check_circuit_bindings(SimpleNamespace(source=request.source,
            circuit=SimpleNamespace(requirements=tuple(legacy)), circuit_bindings=tuple(legacy_bindings)))
        for diagnostic in checked:
            if diagnostic.startswith(("unsupported:circuit_lifecycle:", "unsupported:circuit_provider_mapping:")):
                continue
            if diagnostic.startswith("unsupported:"):
                unresolved.append(diagnostic.removeprefix("unsupported:"))
            else:
                failures.append(diagnostic.removeprefix("fail:"))
    return failures, unresolved


def _functional_control_proof(nodes, target, control, kind):
    """Prove a source gate, never infer a functional kind from its label.

    Exactly one cell-local, explicitly Boolean condition denotes assertion.
    Shutdown assertion or activation deassertion must veto every installation.
    Pure control predicates have at most eight observation atoms; all other
    guard subexpressions are opaque. Three-valued cofactors overapproximate
    their possible values, so only a forced-false guard establishes the gate.
    """
    if kind not in {"activation", "shutdown"}:
        return "kind_not_implemented"
    refs = control["controlling_node_ids"]
    if len(refs) != 1:
        return "requires_one_boolean_condition"
    identity = refs[0]
    if nodes[identity].kind == "signal":
        predicates = [node.id for node in nodes.values()
                      if node.kind == "qualitative" and node.inputs == (identity,)]
        if len(predicates) != 1:
            return "ambiguous_signal_predicate"
        identity = predicates[0]

    def atom(node):
        return (node.inputs[0], fingerprint(node.attributes))

    atoms, pending, seen = set(), [identity], set()
    while pending:
        ref = pending.pop()
        if ref in seen:
            continue
        seen.add(ref)
        node = nodes[ref]
        if node.data_type is None or node.data_type.get("kind") != "condition":
            return "non_boolean_control"
        if node.kind == "qualitative":
            signal = nodes[node.inputs[0]]
            if (signal.kind != "signal" or signal.attributes.get("scope") == "contact"
                    or nodes[signal.inputs[0]].attributes.get("scope") == "contact"):
                return "non_cell_local_control"
            atoms.add(atom(node))
        elif node.kind == "signature":
            pending.append(node.inputs[0])
        elif node.kind in {"not", "and", "or"}:
            pending.extend(node.inputs)
        else:
            return "unsupported_control_expression"
    if not atoms or len(atoms) > 8:
        return "boolean_control_proof_bound"

    actions = tuple(nodes[target].inputs[2:]) if nodes[target].kind == "rule" else (target,)
    if not actions or any(not nodes[ref].kind.startswith("action.") for ref in actions):
        return "target_not_installed_ongoing_action"
    guards = []
    for action_id in actions:
        action = nodes[action_id]
        if (action.kind in {"action.pulse", "action.state_set"}
                or action.attributes.get("ongoing") is not True):
            return "persistent_or_nonongoing_action"
        uses = []
        for rule in nodes.values():
            if rule.kind != "rule":
                continue
            for installed_id in rule.inputs[2:]:
                installed = nodes[installed_id]
                primitive = installed
                while primitive.kind == "action.pulse":
                    primitive = nodes[primitive.inputs[0]]
                if installed_id == action_id or primitive.id == action_id:
                    uses.append((rule, installed))
        if not uses:
            return "target_not_installed_ongoing_action"
        for rule, installed in uses:
            if installed.kind == "action.pulse" or rule.attributes.get("trigger") != "condition":
                return "persistent_or_event_installation"
            guards.append(rule.inputs[1])

    def cofactor(ref, values, cache):
        if ref in cache:
            return cache[ref]
        node = nodes[ref]
        value = None
        if node.kind == "qualitative":
            value = values.get(atom(node))
        elif node.kind in {"not", "signature"}:
            child = cofactor(node.inputs[0], values, cache)
            value = (not child if node.kind == "not" else child) if child is not None else None
        elif node.kind in {"and", "or"}:
            children = [cofactor(child, values, cache) for child in node.inputs]
            if node.kind == "and":
                value = False if False in children else True if all(child is True for child in children) else None
            else:
                value = True if True in children else False if all(child is False for child in children) else None
        cache[ref] = value
        return value

    # Both states must be attainable: an always-true/false purported controller
    # cannot establish a non-vacuous assertion/deassertion contract.
    observed_states = set()
    required = kind == "shutdown"
    for bits in product((False, True), repeat=len(atoms)):
        values = dict(zip(sorted(atoms), bits))
        cache = {}
        asserted = cofactor(identity, values, cache)
        observed_states.add(asserted)
        if asserted is required and any(cofactor(guard, values, cache) is not False for guard in guards):
            return "assertion_does_not_veto" if required else "deassertion_does_not_gate"
    return None if observed_states == {False, True} else "vacuous_control_condition"


def _control_checks(request, inventories, selected):
    failures = []
    controls = inventories["control_domains"]
    grouped = {}
    for item in controls:
        key = (item["kind"], item["domain_id"])
        meaning = fingerprint(item["controlling_node_ids"])
        if key in grouped and grouped[key] != meaning:
            failures.append("shared_control_input_contradiction:" + item["domain_id"])
        grouped[key] = meaning
    source = source_build_request(request.source)
    nodes = {node.id: node for node in source.intent.nodes}
    physical, source_components = {}, {}
    for index, refinement in enumerate(sorted(selected, key=lambda item: item.id)):
        prefix = f"a{index:03d}_"
        templates = {item.id: prefix + f"t{offset:03d}_"
                     for offset, item in enumerate(sorted(refinement.templates, key=lambda item: item.id))}
        placements = {item.id: item for item in refinement.placements}
        for binding in refinement.bindings:
            placed = [placements[identity] for identity in binding.placement_ids]
            for identity in binding.behavior_node_ids:
                physical.setdefault(refinement.source_bindings[identity], set()).update(
                    templates[item.template_id] + item.member_id for item in placed)
                source_components.setdefault(refinement.source_bindings[identity], set()).update(
                    prefix + item for item in binding.component_ids)
    helper_records = {item["id"]: item for item in inventories["helpers"]}
    placement_records = {item["id"]: item for item in inventories["placements"]}

    def supply_identity(helper):
        # Separately modeled providers may share one RNA while preserving
        # functional dependency independence. Physical separation is a separate
        # requirement. A direct RNA supply has no finer supplied identity.
        if helper["provider_component_id"] is not None:
            return ("provider", helper["provider_component_id"])
        if helper["placement_id"] is not None:
            placement = placement_records[helper["placement_id"]]
            return ("direct_rna", placement["member_id"], helper["recipient_role"], helper["compartment"])
        return (helper["availability"], helper["capability"], helper["recipient_role"], helper["compartment"])

    def dependencies(component_set):
        pending = [identity for identity, helper in helper_records.items()
                   if set(helper["consumer_component_ids"]).intersection(component_set)]
        used = set()
        while pending:
            identity = pending.pop()
            if identity in used:
                continue
            used.add(identity)
            helper = helper_records[identity]
            pending.extend(helper["depends_on"])
            provider = helper["provider_component_id"]
            if provider is not None:
                pending.extend(other_id for other_id, other in helper_records.items()
                               if provider in other["consumer_component_ids"])
        return {supply_identity(helper_records[identity]) for identity in used}

    for requirement in request.constraints.control_requirements:
        refs = requirement.behavior_node_ids
        if not set(refs) <= nodes.keys():
            failures.append("unknown_control_requirement_node:" + requirement.id)
            continue
        if requirement.kind in {"physical_separation", "dependency_disjointness"}:
            materials = [physical.get(ref, set()) for ref in refs]
            components = [source_components.get(ref, set()) for ref in refs]
            if any(not item for item in materials):
                failures.append("control_material_missing:" + requirement.id)
                continue
            if requirement.kind == "physical_separation":
                if requirement.relation == "shared" and not set.intersection(*materials):
                    failures.append("shared_physical_material_missing:" + requirement.id)
                if requirement.relation == "independent" and any(materials[left].intersection(materials[right])
                    for left in range(len(refs)) for right in range(left + 1, len(refs))):
                    failures.append("physical_separation_violated:" + requirement.id)
            else:
                declared_dependencies = [dependencies(component_set) for component_set in components]
                if requirement.forbidden_shared_dependencies:
                    restricted = {supply_identity(helper) for helper in helper_records.values()
                                  if helper["capability"] in requirement.forbidden_shared_dependencies}
                    declared_dependencies = [values.intersection(restricted) for values in declared_dependencies]
                if requirement.relation == "shared" and not set.intersection(*declared_dependencies):
                    failures.append("shared_dependency_missing:" + requirement.id)
                if requirement.relation == "independent" and any(declared_dependencies[left].intersection(declared_dependencies[right])
                    for left in range(len(refs)) for right in range(left + 1, len(refs))):
                    failures.append("forbidden_shared_dependency:" + requirement.id)
            continue
        matching = {ref: [item for item in controls if item["kind"] == requirement.kind
                          and ref in item["behavior_node_ids"]] for ref in refs}
        if any(not value for value in matching.values()):
            failures.append("control_requirement_unbound:" + requirement.id)
            continue
        for ref, declarations in matching.items():
            for control in declarations:
                reason = _functional_control_proof(nodes, ref, control, requirement.kind)
                if reason is not None:
                    failures.append("unsupported_functional_control_requirement:" + requirement.id
                                    + ":" + ref + ":" + reason)
        domains = [{item["domain_id"] for item in matching[ref]} for ref in refs]
        components = [{identity for item in matching[ref] for identity in item["component_ids"]}
                      for ref in refs]
        input_meanings = [{ancestor for item in matching[ref] for identity in item["controlling_node_ids"]
                           for ancestor in lineage_for(nodes, identity)
                           if nodes[ancestor].kind in {"signal", "channel_observation", "state", "memory"}}
                          for ref in refs]
        influence = [_causal_nodes(nodes, (ref,)) for ref in refs]
        if requirement.relation == "shared":
            if not set.intersection(*domains):
                failures.append("shared_control_missing:" + requirement.id)
        else:
            for left in range(len(refs)):
                for right in range(left + 1, len(refs)):
                    if domains[left].intersection(domains[right]) or components[left].intersection(components[right]):
                        failures.append("independent_control_coupled:" + requirement.id)
                    if (not input_meanings[left] or not input_meanings[right]
                        or input_meanings[left].intersection(input_meanings[right])):
                        failures.append("independent_control_inputs_coupled:" + requirement.id)
                    if (input_meanings[left].intersection(influence[right])
                        or input_meanings[right].intersection(influence[left])):
                        failures.append("independent_control_cross_influence:" + requirement.id)
                    if requirement.kind == "physical_separation" and physical.get(refs[left], set()).intersection(
                        physical.get(refs[right], set())
                    ):
                        failures.append("physical_separation_violated:" + requirement.id)
                    if requirement.forbidden_shared_dependencies:
                        restricted = {supply_identity(helper) for helper in helper_records.values()
                                      if helper["capability"] in requirement.forbidden_shared_dependencies}
                        left_dependencies = dependencies(source_components.get(refs[left], set()))
                        right_dependencies = dependencies(source_components.get(refs[right], set()))
                        if left_dependencies.intersection(right_dependencies, restricted):
                            failures.append("forbidden_shared_dependency:" + requirement.id)
    return failures


def _channel_checks(request, inventories, source_records):
    from biocompiler.semantics.types import TypeSpec, decode_binding
    failures = []
    nodes = {node.id: node for node in source_build_request(request.source).intent.nodes}
    observed_edges, receiver_contracts = set(), {}
    for channel in inventories["channels"]:
        identity = channel["id"]
        declaration = nodes.get(channel["source_channel_id"])
        sender, receiver = nodes.get(channel["sender_node_id"]), nodes.get(channel["receiver_node_id"])
        if sender is not None and sender.kind == "action.pulse":
            sender = nodes[sender.inputs[0]]
        if (declaration is None or declaration.kind != "channel" or sender is None or receiver is None
            or sender.kind != "action.emit" or receiver.kind != "channel_observation"
            or sender.inputs[1] != declaration.id or receiver.inputs[1] != declaration.id
            or sender.role != channel["sender_role"] or receiver.role != channel["receiver_role"]):
            failures.append("channel_source_correspondence:" + identity)
            continue
        try:
            decode_binding(channel["initial_value"], TypeSpec.from_dict(declaration.data_type))
        except (BiocompilerError, ValueError, TypeError):
            failures.append("channel_initial_value:" + identity)
        edge = (declaration.id, channel["sender_node_id"], receiver.id)
        if edge in observed_edges:
            failures.append("duplicate_channel_transport_edge:" + identity)
        observed_edges.add(edge)
        receiver_key = (declaration.id, receiver.id)
        receiver_contract = fingerprint((channel["aggregation"], channel["initial_value"]))
        if receiver_key in receiver_contracts and receiver_contracts[receiver_key] != receiver_contract:
            failures.append("inconsistent_channel_receiver_contract:" + identity)
        receiver_contracts[receiver_key] = receiver_contract
        record = next(item for item in source_records if item["id"] == declaration.id)
        if channel["aggregation"] == "single_sender" and len(record["senders"]) != 1:
            failures.append("channel_sender_aggregation:" + identity)
        if channel["failure_mode"] == "unknown":
            failures.append("channel_failure_semantics_unknown:" + identity)
    expected_edges = {(record["id"], sender["action_id"], receiver["observation_id"])
                      for record in source_records for sender in record["senders"] for receiver in record["receivers"]}
    if observed_edges != expected_edges:
        failures.append("channel_link_inventory")
    return failures


def _delivery_dependency_checks(request, inventories, selected):
    failures = []
    placements = {item["id"]: item for item in inventories["placements"]}
    groups = {item.id: item for item in request.constraints.delivery_groups}
    component_placements = {}
    for index, refinement in enumerate(sorted(selected, key=lambda item: item.id)):
        prefix = f"a{index:03d}_"
        for binding in refinement.bindings:
            for identity in binding.component_ids:
                component_placements.setdefault(prefix + identity, set()).update(
                    prefix + placement for placement in binding.placement_ids)
    for helper in inventories["helpers"]:
        if helper["placement_id"] is None:
            continue
        provider = placements[helper["placement_id"]]
        for consumer in helper["consumer_component_ids"]:
            for placement_id in component_placements.get(consumer, ()):
                consumer_placement = placements[placement_id]
                if provider["recipient_role"] != consumer_placement["recipient_role"]:
                    failures.append("helper_cross_recipient_supply:" + helper["id"])
                if provider["member_id"] == consumer_placement["member_id"]:
                    continue
                group = groups.get(provider["delivery_group"])
                if (provider["delivery_group"] != consumer_placement["delivery_group"] or group is None
                    or group.mode != "co_delivered" or not group.same_recipient):
                    failures.append("helper_co_delivery_missing:" + helper["id"])
    return failures


def _molecule_checks(request, construction, bundle, inventories):
    failures = []
    molecules = {item.id: item for item in bundle.molecules}
    complexes = {item.id: item for item in bundle.complexes}
    delivered = set()

    def constituents(identity):
        if identity in molecules:
            return {identity}
        if identity in complexes:
            return {item.molecule_id for item in complexes[identity].constituents}
        return set()

    for requirement in construction.requirements:
        if requirement.category not in {"payload", "delivered_helper"}:
            continue
        members = constituents(requirement.member_id)
        if not members or any(identity not in molecules or molecules[identity].space.alphabet != "RNA"
                              for identity in members):
            failures.append("delivered_member_not_rna:" + str(requirement.member_id))
        delivered.update(members)
    for member in molecules.values():
        if member.space.alphabet == "DNA":
            failures.append("final_dna_member:" + member.id)
    lengths = {identity: len(molecules[identity].sequence) for identity in delivered if identity in molecules}
    constraints = request.constraints
    if constraints.exact_count is not None and len(delivered) != constraints.exact_count:
        failures.append("exact_rna_count")
    if constraints.max_count is not None and len(delivered) > constraints.max_count:
        failures.append("maximum_rna_count")
    if constraints.max_member_bases is not None and any(value > constraints.max_member_bases for value in lengths.values()):
        failures.append("maximum_rna_member_length")
    if constraints.max_total_bases is not None and sum(lengths.values()) > constraints.max_total_bases:
        failures.append("maximum_rna_total_length")
    groups = {item.id: item for item in constraints.delivery_groups}
    roles = {node.id for node in source_build_request(request.source).intent.find(kind="role")}
    group_members, group_roles = {}, {}
    for placement in inventories["placements"]:
        identity = placement["member_id"]
        if identity not in molecules and identity not in complexes:
            failures.append("placement_member_missing:" + identity)
        if placement["recipient_role"] not in roles:
            failures.append("placement_recipient_unknown:" + placement["id"])
        if not any(item.subject_id == identity and item.compartment == placement["compartment"]
                   and item.role == placement["recipient_role"]
                   for item in bundle.role_instances):
            failures.append("placement_molecular_compartment:" + placement["id"])
        group = groups.get(placement["delivery_group"])
        if group is None:
            failures.append("delivery_group_missing:" + placement["delivery_group"])
            continue
        if placement["recipient_role"] not in group.recipient_roles:
            failures.append("delivery_group_recipient:" + placement["id"])
        group_members.setdefault(group.id, set()).update(constituents(identity).intersection(delivered))
        group_roles.setdefault(group.id, set()).add(placement["recipient_role"])
    for group in groups.values():
        members = group_members.get(group.id, set())
        if not set(group.recipient_roles) <= roles:
            failures.append("delivery_group_unknown_source_role:" + group.id)
        if group.same_recipient and len(group_roles.get(group.id, ())) > 1:
            failures.append("delivery_group_same_recipient_conflict:" + group.id)
        if group.exact_count is not None and len(members) != group.exact_count:
            failures.append("delivery_group_exact_count:" + group.id)
        if group.max_count is not None and len(members) > group.max_count:
            failures.append("delivery_group_maximum_count:" + group.id)
        if group.max_total_bases is not None and sum(lengths[identity] for identity in members) > group.max_total_bases:
            failures.append("delivery_group_maximum_length:" + group.id)
    return failures


def _assumptions(request, selected):
    values = set(request.library.assumptions)
    for group in request.constraints.delivery_groups:
        values.update(group.assumptions)
    for refinement in selected:
        values.update(refinement.assumptions)
        for item in (*refinement.components, *refinement.controls, *refinement.helpers, *refinement.channels):
            values.update(item.assumptions)
    return tuple(sorted(values))


def _diagnostic(code, candidates=()):
    return ArchitectureGap("independent_verification_failure", code, (), tuple(candidates),
                           "Independent architecture check rejected " + code + ".")


def check_payload_architecture(build, *, expected_request):
    """Freshly verify a retained plan against independent complete authority.

    The checker reconstructs selected material templates and exact source/model
    correspondence. Candidate ranking and claims about exhausting the search are
    explicitly outside this receipt's scope.
    """
    failures, unresolved, assumptions = [], [], ()
    construction_complete = False
    try:
        if build.request_fingerprint != expected_request.fingerprint:
            failures.append("request_authority")
        source_failures, source_unresolved, authority = _source_manifest_checks(build.execution, expected_request.source)
        failures.extend(source_failures)
        unresolved.extend(source_unresolved)
        if build.plan is None:
            unresolved.append("search_outcome_not_independently_replayed")
            if build.construction is not None:
                failures.append("construction_without_selected_architecture")
        else:
            library = {item.id: item for item in expected_request.library.refinements}
            unknown = set(build.plan.selected_refinement_ids) - library.keys()
            if unknown:
                failures.append("selected_refinement_authority")
            selected = tuple(library[identity] for identity in build.plan.selected_refinement_ids if identity in library)
            assumptions = _assumptions(expected_request, selected)
            if tuple(build.plan.assumptions) != assumptions:
                failures.append("plan_assumptions")
            behavior = build.execution.behavior
            if behavior is None:
                failures.append("selected_architecture_without_executable_source")
            else:
                for refinement in selected:
                    failures.extend(refinement.id + ":" + value for value in
                                    _refinement_checks(refinement, behavior, expected_request.circuit.profile.target))
            inventories, documents = _inventories(selected)
            for key, value in inventories.items():
                if fingerprint(getattr(build.plan, key)) != fingerprint(value):
                    failures.append("plan_" + key)
            nodes = {node.id: node for node in source_build_request(expected_request.source).intent.nodes}
            ledger, owners = _expected_ledger(expected_request, authority["ledger"], nodes, selected,
                                               assumptions, behavior is not None and not source_unresolved and not source_failures)
            if fingerprint([item.to_dict() for item in build.plan.ledger]) != fingerprint([item.to_dict() for item in ledger]):
                failures.append("plan_requirement_ledger")
            for node in nodes.values():
                if _runtime(node) and len(owners.get(node.id, ())) > 1:
                    failures.append("duplicate_runtime_ownership:" + node.id)
            unresolved.extend(item.id for item in ledger if item.status == "unresolved")
            extra_failures, extra_unresolved = _supplementary_checks(expected_request, selected)
            failures.extend(extra_failures)
            unresolved.extend(extra_unresolved)
            failures.extend(_control_checks(expected_request, inventories, selected))
            failures.extend(_channel_checks(expected_request, inventories, authority["channels"]))
            failures.extend(_delivery_dependency_checks(expected_request, inventories, selected))
            expected_construction = _expected_construction(expected_request, documents)
            if build.construction is None:
                unresolved.append("complete_construction_missing")
            else:
                construction = build.construction
                if construction.request.fingerprint != expected_construction.fingerprint:
                    failures.append("construction_template_authority")
                assessment = check_circuit_construction(construction.candidate, expected_request=expected_construction)
                if fingerprint(assessment.to_dict()) != fingerprint(construction.assessment.to_dict()):
                    failures.append("construction_assessment_replay")
                if not assessment.passed:
                    failures.append("exact_construction_reconstruction")
                elif not assessment.complete:
                    unresolved.append("complete_construction_missing")
                bundle = construction.candidate.bundle
                if bundle is None:
                    unresolved.append("molecule_bundle_missing")
                else:
                    molecule_failures = _molecule_checks(expected_request, expected_construction, bundle, inventories)
                    failures.extend(molecule_failures)
                    construction_complete = assessment.passed and assessment.complete and not molecule_failures
            if expected_request.constraints.require_complete and unresolved:
                failures.append("strict_completeness_violated")
    except (BiocompilerError, KeyError, ValueError, TypeError, AttributeError) as error:
        failures.append("malformed_architecture:" + str(error))
    failures = tuple(dict.fromkeys(failures))
    unresolved = tuple(dict.fromkeys(unresolved))
    complete = bool(build.plan is not None and construction_complete and not failures and not unresolved)
    if build.status == "compiled" and not complete:
        failures += ("compiled_status_without_complete_translation",)
    if failures:
        construction_complete = False
    return PayloadArchitectureVerification(
        expected_request.fingerprint, build.fingerprint,
        CheckOutcome.FAIL if failures else CheckOutcome.PASS,
        complete, construction_complete,
        tuple(_diagnostic(item, build.plan.selected_refinement_ids if build.plan else ()) for item in failures),
        unresolved, assumptions,
    )


check_payload_architecture_build = check_payload_architecture


def verify_payload_architecture(receipt, build, *, expected_request):
    fresh = check_payload_architecture(build, expected_request=expected_request)
    require(fingerprint(receipt.to_dict()) == fingerprint(fresh.to_dict()),
            "Stored architecture verification does not match fresh independent authority replay.")
    return fresh

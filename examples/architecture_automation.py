"""Automatically bind supplied artificial contracts and enforce RNA timing.

All sequence material and timing are software fixtures. The two alternative
supplier models come from the separately authored contract programs in the A–F
example. No supplied contract contains a source-node mapping in this example.
"""

from dataclasses import replace

import biocompiler as bc
from examples.payload_architectures import _circuit, make_architecture_request


TIMING_ASSUMPTION = "Artificial exposure-clock window; human expression kinetics remain unestablished."


def make_automation_request():
    original = make_architecture_request(variants=("one_rna", "one_rna_helper"))
    # An imported therapeutic program can have entirely different node IDs.
    # Change source identities only; keep all supplied model graphs untouched.
    source = original.source
    names = {node.id: "design." + node.id for node in source.intent.nodes}
    intent = replace(source.intent,
        nodes=tuple(replace(node, id=names[node.id], inputs=tuple(names[ref] for ref in node.inputs),
                            role=None if node.role is None else names[node.role]) for node in source.intent.nodes),
        roots=tuple(names[ref] for ref in source.intent.roots))
    source = replace(source, intent=intent)
    refinements = []
    for original_contract in original.library.refinements:
        helpers = {item.placement_id for item in original_contract.helpers if item.placement_id is not None}
        availability = tuple(bc.RNAAvailabilityContract("window." + item.id, item.id,
            3 if item.id in helpers else 0, 4 if item.id in helpers else 1,
            10, 12, (TIMING_ASSUMPTION,)) for item in original_contract.placements)
        refinements.append(replace(original_contract, source_bindings={},
            match_policy=bc.ArchitectureMatchPolicy(), availability=availability))
    groups = tuple(replace(group, recipient_roles=tuple(names[ref] for ref in group.recipient_roles))
                   for group in original.constraints.delivery_groups)
    required = tuple(bc.RNADeploymentRequirement("execution." + group.id, group.id,
        group.recipient_roles[0], "cytoplasm", 1, 10, (TIMING_ASSUMPTION,),
        unavailable_after_seconds=13) for group in groups)
    preferred = next(item.id for item in refinements if item.helpers)
    constraints = replace(original.constraints, delivery_groups=groups,
                          deployment_requirements=required, preferred_refinement_ids=(preferred,),
                          require_complete=True)
    return replace(original, id="automatic-contract-matching-and-deployment",
                   circuit=_circuit(source), library=replace(original.library, refinements=tuple(refinements)),
                   constraints=constraints)


def make_automatic_case(case):
    """Match an original A–F supplier model without any source-node anchors.

    The independently authored source and supplied Behavior models, exact
    material, output identities and physical declarations remain unchanged.
    """
    original = make_architecture_request(case)
    refinements = tuple(replace(contract, source_bindings={}, match_policy=bc.ArchitectureMatchPolicy())
                        for contract in original.library.refinements)
    return replace(original, id="automatic-" + original.id,
                   library=replace(original.library, refinements=refinements))


if __name__ == "__main__":
    request = make_automation_request()
    build = bc.compile(request)
    assert build.status == "compiled", build.diagnostics
    checked = bc.check_payload_architecture(build, expected_request=request)
    assert checked.translation_complete
    print(bc.export_payload_architecture(build, expected_request=request).fasta, end="")
